"""US1: the deny hook, gated by the two-corpus suite (SC-001, FR-005).

Every fixture in tests/fixtures/misbehaviors/ must block with its expected
class; every fixture in tests/fixtures/benign/ must pass. Adding a fixture
*is* extending the gate (research R3). Fault corpus proves fail-open (SC-007).
"""

import json
from pathlib import Path

import pytest

import _state
import guardrail_deny
from conftest import FIXTURES_DIR
from helpers import failopen

MISBEHAVIOR_FILES = sorted((FIXTURES_DIR / "misbehaviors").glob("*.json"))
BENIGN_FILES = sorted((FIXTURES_DIR / "benign").glob("*.json"))


def run_fixture(fixture_path, tmp_path):
    with open(str(fixture_path), encoding="utf-8") as f:
        fixture = json.load(f)
    root = tmp_path / "workspace"
    root.mkdir(exist_ok=True)
    for outcome in fixture.get("trace_outcomes", []):
        _state.append_trace(
            root,
            {"agent": "agent-prior", "tool": "Bash", "summary": "prior call",
             "outcome": outcome},
        )
    payload = dict(fixture["hook_payload"])
    payload.setdefault("cwd", str(root))
    payload.setdefault("session_id", "corpus-session")
    payload.setdefault("transcript_path", str(tmp_path / "t.jsonl"))
    exit_code, stdout, stderr = guardrail_deny.run(json.dumps(payload))
    return fixture, root, exit_code, stdout, stderr


def corpus_size_guard():
    # The suites below parametrize over the directories; if both corpora
    # vanished the gate would pass vacuously. Pin non-emptiness.
    assert MISBEHAVIOR_FILES and BENIGN_FILES


def test_corpora_are_non_empty():
    corpus_size_guard()


@pytest.mark.parametrize(
    "fixture_path", MISBEHAVIOR_FILES, ids=[p.stem for p in MISBEHAVIOR_FILES]
)
def test_every_misbehavior_fixture_is_blocked(fixture_path, tmp_path):
    fixture, root, exit_code, stdout, stderr = run_fixture(fixture_path, tmp_path)
    assert fixture["expected"] == "block", "misbehavior fixtures must expect block"
    assert exit_code == 2, (
        "%s was not blocked (exit %r)" % (fixture["name"], exit_code)
    )
    # The block message names the matched pattern class (spec US1 AS-1).
    assert fixture["expected_class"] in stderr


@pytest.mark.parametrize(
    "fixture_path", MISBEHAVIOR_FILES, ids=[p.stem for p in MISBEHAVIOR_FILES]
)
def test_every_block_appends_its_denied_trace_line(fixture_path, tmp_path):
    fixture, root, exit_code, stdout, stderr = run_fixture(fixture_path, tmp_path)
    trace_path = root / ".bb-session" / "trace.jsonl"
    lines = [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
    ]
    denied = [l for l in lines if l["outcome"].startswith("denied:guardrail:")]
    assert len(denied) == 1
    assert denied[0]["outcome"] == "denied:guardrail:" + fixture["expected_class"]
    assert denied[0]["tool"] == fixture["hook_payload"]["tool_name"]
    assert denied[0]["agent"].startswith("agent-")


@pytest.mark.parametrize(
    "fixture_path", BENIGN_FILES, ids=[p.stem for p in BENIGN_FILES]
)
def test_every_benign_fixture_is_allowed(fixture_path, tmp_path):
    fixture, root, exit_code, stdout, stderr = run_fixture(fixture_path, tmp_path)
    assert fixture["expected"] == "allow", "benign fixtures must expect allow"
    assert exit_code == 0, (
        "%s was blocked: %r" % (fixture["name"], stderr)
    )


# --- credential_scan context rule (spec Assumption; T009 window cases) ------


CREDS_PAYLOAD = {
    "hook_event_name": "PreToolUse",
    "tool_name": "Bash",
    "tool_input": {"command": "cat ~/.aws/credentials"},
}


def run_creds(root, tmp_path):
    payload = dict(CREDS_PAYLOAD, cwd=str(root),
                   transcript_path=str(tmp_path / "t.jsonl"))
    return guardrail_deny.run(json.dumps(payload))


def seed_trace(root, outcomes):
    for outcome in outcomes:
        _state.append_trace(
            root, {"agent": "a", "tool": "Bash", "summary": "x", "outcome": outcome}
        )


def test_auth_error_in_window_blocks(tmp_path):
    seed_trace(tmp_path, ["ok", "error:auth", "ok"])
    exit_code, _, stderr = run_creds(tmp_path, tmp_path)
    assert exit_code == 2 and "credential_scan" in stderr


def test_clean_window_allows(tmp_path):
    seed_trace(tmp_path, ["ok"] * 5)
    exit_code, _, stderr = run_creds(tmp_path, tmp_path)
    assert exit_code == 0


def test_stale_auth_error_beyond_10_line_window_allows(tmp_path):
    seed_trace(tmp_path, ["error:auth"] + ["ok"] * 10)
    exit_code, _, _ = run_creds(tmp_path, tmp_path)
    assert exit_code == 0


def test_no_trace_degrades_to_pattern_only_block(tmp_path):
    exit_code, _, stderr = run_creds(tmp_path, tmp_path)
    assert exit_code == 2 and "credential_scan" in stderr


def test_degraded_block_message_is_honest_about_missing_context(tmp_path):
    # SF4: in pattern-only degraded mode the block must NOT claim "after an
    # auth error" it cannot see — it says the trace context was unavailable.
    exit_code, _, stderr = run_creds(tmp_path, tmp_path)
    assert exit_code == 2
    assert "no trace context" in stderr
    assert "after an auth error" not in stderr


def test_quoted_credential_path_still_matches(tmp_path):
    # O2: quoting a credential path does not make the read safe — the class
    # still fires (blocked here because there is no clean window to clear it).
    payload = dict(CREDS_PAYLOAD, cwd=str(tmp_path),
                   tool_input={"command": 'cat "$HOME/.aws/credentials"'},
                   transcript_path=str(tmp_path / "t.jsonl"))
    exit_code, _, stderr = guardrail_deny.run(json.dumps(payload))
    assert exit_code == 2 and "credential_scan" in stderr


def test_unreadable_state_blocks_conservatively_not_silently(tmp_path):
    # SF4: an unreadable state dir yields no auth context; the credential class
    # blocks conservatively (over-match direction) rather than allowing on an
    # infra error, and the block is loud, not silent.
    root = tmp_path / "workspace"
    root.mkdir()
    (root / ".bb-session").write_text("file where a dir should be", encoding="utf-8")
    exit_code, _, stderr = run_creds(root, tmp_path)
    assert exit_code == 2
    assert "no trace context" in stderr


# --- Y2: denied line carries capability when the binding map classifies it ---


def test_denied_line_carries_capability_from_bindings(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    claude = root / ".claude"
    claude.mkdir()
    (claude / "settings.json").write_text(
        json.dumps({"battleBuddy": {"bindings": {
            "observability.run_query": "mcp__grafana__delete_dashboard"}}}),
        encoding="utf-8",
    )
    payload = {"hook_event_name": "PreToolUse",
               "tool_name": "mcp__grafana__delete_dashboard",
               "tool_input": {"command": "terraform destroy -auto-approve"},
               "cwd": str(root), "transcript_path": str(tmp_path / "t.jsonl")}
    exit_code, _, _ = guardrail_deny.run(json.dumps(payload))
    assert exit_code == 2
    lines = [
        json.loads(l)
        for l in (root / ".bb-session" / "trace.jsonl").read_text().splitlines()
    ]
    assert lines[-1]["capability"] == "observability"


def test_denied_line_omits_capability_when_no_bindings(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
               "tool_input": {"command": "rm -rf /"},
               "cwd": str(root), "transcript_path": str(tmp_path / "t.jsonl")}
    guardrail_deny.run(json.dumps(payload))
    line = json.loads(
        (root / ".bb-session" / "trace.jsonl").read_text().splitlines()[-1]
    )
    assert "capability" not in line


# --- fail-open under fault injection (SC-007) -------------------------------


def test_fault_corpus_is_non_empty():
    # TA5: an emptied/renamed faults/ dir would make every fail-open test
    # vanish as an empty parametrize (skipped, suite green) — pin it.
    assert len(failopen.fault_cases()) >= 5


@pytest.mark.parametrize(
    "fault_path", failopen.fault_cases(), ids=failopen.fault_ids()
)
def test_fail_open_on_fault_corpus(fault_path, tmp_path, monkeypatch):
    failopen.run_fault(
        guardrail_deny, fault_path, tmp_path, monkeypatch,
        exception_target="_evaluate",
    )


def test_unreadable_state_never_downgrades_a_deny(tmp_path):
    # Trace bookkeeping failure must not turn a block into an allow — the
    # deny verdict stands, the append failure is a visible diagnostic.
    root = tmp_path / "workspace"
    root.mkdir()
    state = root / ".bb-session"
    state.write_text("a file where a directory should be", encoding="utf-8")
    payload = dict(CREDS_PAYLOAD, cwd=str(root),
                   tool_input={"command": "rm -rf /"},
                   transcript_path=str(tmp_path / "t.jsonl"))
    exit_code, _, stderr = guardrail_deny.run(json.dumps(payload))
    assert exit_code == 2
    assert "destructive_filesystem" in stderr
    assert "append failed" in stderr


# --- registration -----------------------------------------------------------


def test_hook_is_registered_for_pretooluse(tmp_path):
    hooks_json = json.loads(
        (Path(guardrail_deny.__file__).parent / "hooks.json").read_text(
            encoding="utf-8"
        )
    )
    registrations = hooks_json["hooks"]["PreToolUse"]
    commands = [
        h["command"]
        for entry in registrations
        for h in entry["hooks"]
        if h["type"] == "command"
    ]
    assert any("guardrail_deny.py" in c for c in commands)
    # Registered for Bash and MCP tools (design §3.5 layer 1).
    matchers = [entry["matcher"] for entry in registrations]
    assert any("Bash" in m and "mcp__" in m for m in matchers)
