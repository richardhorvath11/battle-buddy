"""US5: the session guard — marker states, transcript staging, config warning.

Table-driven over tests/fixtures/markers/ (the four marker states plus
transcript and config payload fixtures); fault corpus proves fail-open
(SC-007). Warnings fire on exactly the two marker-present states (US5
Independent Test) and the guard never blocks (exit 0 everywhere).
"""

import json
import os
import stat
from pathlib import Path

import pytest

import session_guard
from conftest import FIXTURES_DIR, load_fixture
from helpers import failopen

MARKERS_DIR = FIXTURES_DIR / "markers"
MARKER_FILES = sorted(MARKERS_DIR.glob("marker-*.json"))
TRANSCRIPT_FILES = sorted(MARKERS_DIR.glob("transcript-*.json"))
CONFIG_FILES = sorted(MARKERS_DIR.glob("config-*.json"))


def make_root(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir(exist_ok=True)
    return root


def run_end(root, transcript_path):
    payload = {
        "hook_event_name": "SessionEnd",
        "cwd": str(root),
        "session_id": "us5-session",
        "transcript_path": transcript_path,
    }
    return session_guard.run(json.dumps(payload))


def run_start(root):
    payload = {
        "hook_event_name": "SessionStart",
        "cwd": str(root),
        "session_id": "us5-session",
        "transcript_path": "/tmp/t.jsonl",
    }
    return session_guard.run(json.dumps(payload))


# --- corpus guards ----------------------------------------------------------


def test_fixture_corpora_are_non_empty():
    assert len(MARKER_FILES) == 4
    assert len(TRANSCRIPT_FILES) == 3
    assert len(CONFIG_FILES) == 2


# --- FR-011: the four marker states -----------------------------------------


@pytest.mark.parametrize(
    "fixture_path", MARKER_FILES, ids=[p.stem for p in MARKER_FILES]
)
def test_marker_states_warn_on_exactly_the_present_ones(fixture_path, tmp_path):
    with open(str(fixture_path), encoding="utf-8") as f:
        fixture = json.load(f)
    root = make_root(tmp_path)
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text("{}\n", encoding="utf-8")
    marker_path = root / ".bb-session" / "marker.json"
    if fixture["marker"] is not None:
        marker_path.parent.mkdir(exist_ok=True)
        marker_path.write_text(json.dumps(fixture["marker"]), encoding="utf-8")
    if fixture.get("delete_before_end"):
        marker_path.unlink()  # a confirmed close clears by deletion
    exit_code, stdout, stderr = run_end(root, str(transcript))
    assert exit_code == 0  # the guard warns, it never blocks
    if fixture["expected_warning"]:
        assert "session row not persisted" in stderr
        assert "run /close" in stderr  # the exact remedial instruction
        # "Loudly" means the responder actually sees it: the warning also
        # rides the runtime's user-visible systemMessage channel (exit-0
        # stderr alone is debug-log-only).
        message = json.loads(stdout)["systemMessage"]
        assert "session row not persisted" in message
    else:
        assert "session row not persisted" not in stderr
        assert stdout == ""


def test_warning_names_the_session_when_the_marker_is_readable(tmp_path):
    fixture = load_fixture("markers", "marker-open-unconfirmed.json")
    root = make_root(tmp_path)
    state = root / ".bb-session"
    state.mkdir()
    (state / "marker.json").write_text(json.dumps(fixture["marker"]),
                                       encoding="utf-8")
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("{}\n", encoding="utf-8")
    _, _, stderr = run_end(root, str(transcript))
    assert fixture["marker"]["session_id"] in stderr


def test_unreadable_marker_content_still_warns_on_presence(tmp_path):
    # FR-011's trigger is presence, not content: a corrupt marker file is
    # still an uncleared marker.
    root = make_root(tmp_path)
    state = root / ".bb-session"
    state.mkdir()
    (state / "marker.json").write_text("{corrupt", encoding="utf-8")
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("{}\n", encoding="utf-8")
    exit_code, _, stderr = run_end(root, str(transcript))
    assert exit_code == 0
    assert "session row not persisted" in stderr


# --- FR-012: transcript staging ---------------------------------------------


@pytest.mark.parametrize(
    "fixture_path", TRANSCRIPT_FILES, ids=[p.stem for p in TRANSCRIPT_FILES]
)
def test_transcript_staging_per_scenario(fixture_path, tmp_path):
    with open(str(fixture_path), encoding="utf-8") as f:
        fixture = json.load(f)
    root = make_root(tmp_path)
    source = tmp_path / "native-transcript.jsonl"
    if fixture["transcript"] == "present":
        source.write_text('{"role":"user"}\n', encoding="utf-8")
    elif fixture["transcript"] == "unreadable":
        source.write_text('{"role":"user"}\n', encoding="utf-8")
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            pytest.skip("chmod-based unreadable fault is a no-op as root")
        os.chmod(str(source), 0)
    try:
        exit_code, _, stderr = run_end(root, str(source))
    finally:
        if fixture["transcript"] == "unreadable":
            os.chmod(str(source), stat.S_IRUSR | stat.S_IWUSR)
    assert exit_code == 0  # degrade, never a session-ending failure
    staged = root / ".bb-session" / "staging" / "transcript.md"
    if fixture["expect_staged"]:
        assert staged.read_text(encoding="utf-8") == source.read_text(
            encoding="utf-8"
        )
    else:
        assert not staged.exists()
    if fixture["expect_notice"]:
        assert "staging failed" in stderr


def test_missing_transcript_path_field_degrades_to_notice(tmp_path):
    root = make_root(tmp_path)
    payload = {"hook_event_name": "SessionEnd", "cwd": str(root)}
    exit_code, _, stderr = session_guard.run(json.dumps(payload))
    assert exit_code == 0
    assert "no transcript_path" in stderr


def test_missing_source_does_not_conjure_state_dir(tmp_path):
    # Staging a transcript that does not exist must not create .bb-session/
    # in a workspace that never had one (protocol: created lazily by the
    # first writer — a failed copy wrote nothing).
    root = make_root(tmp_path)
    run_end(root, str(tmp_path / "never-existed.jsonl"))
    assert not (root / ".bb-session").exists()


# --- FR-015: SessionStart config-presence warning ---------------------------


@pytest.mark.parametrize(
    "fixture_path", CONFIG_FILES, ids=[p.stem for p in CONFIG_FILES]
)
def test_config_presence_warning(fixture_path, tmp_path):
    with open(str(fixture_path), encoding="utf-8") as f:
        fixture = json.load(f)
    root = make_root(tmp_path)
    if fixture["config_present"]:
        claude = root / ".claude"
        claude.mkdir()
        (claude / "settings.json").write_text(
            json.dumps({"battleBuddy": {}}), encoding="utf-8"
        )
    exit_code, stdout, stderr = run_start(root)
    assert exit_code == 0  # non-blocking (FR-015)
    if fixture["expected_warning"]:
        assert "workspace repo" in stderr
        assert "workspace repo" in json.loads(stdout)["systemMessage"]
    else:
        assert "workspace repo" not in stderr
        assert stdout == ""


def test_malformed_config_surfaces_notice_and_names_the_real_cause(tmp_path):
    # A settings file that EXISTS but cannot be parsed is not a missing
    # block: the user-visible warning must name the broken file, not
    # prescribe "run from the workspace repo" (which would not help).
    root = make_root(tmp_path)
    claude = root / ".claude"
    claude.mkdir()
    (claude / "settings.json").write_text("{not json", encoding="utf-8")
    exit_code, stdout, stderr = run_start(root)
    assert exit_code == 0
    assert "config notice" in stderr  # fail-open visibility (R13)
    assert "could not be read" in stderr
    assert "workspace repo" not in stderr  # the wrong remedy, not offered
    assert "could not be read" in json.loads(stdout)["systemMessage"]


# --- fail-open under fault injection (SC-007) -------------------------------


def test_fault_corpus_is_non_empty():
    assert len(failopen.fault_cases()) >= 5


@pytest.mark.parametrize(
    "fault_path", failopen.fault_cases(), ids=failopen.fault_ids()
)
def test_fail_open_on_fault_corpus(fault_path, tmp_path, monkeypatch):
    failopen.run_fault(
        session_guard, fault_path, tmp_path, monkeypatch,
        exception_target="_dispatch",
    )


def test_seeded_exception_at_session_end_fails_open(tmp_path):
    # The shared fault corpus seeds its exception on a PreToolUse payload
    # (a no-op event for this guard); prove the same property on the guard's
    # own live path too.
    root = make_root(tmp_path)

    def _raiser(payload, r):
        raise RuntimeError("seeded session-end fault")

    orig = session_guard._session_end
    session_guard._session_end = _raiser
    try:
        exit_code, _, stderr = run_end(root, str(tmp_path / "t.jsonl"))
    finally:
        session_guard._session_end = orig
    assert exit_code == 0
    assert "fail-open" in stderr


# --- registration -----------------------------------------------------------


def test_hook_is_registered_for_both_session_events():
    hooks_json = json.loads(
        (Path(session_guard.__file__).parent / "hooks.json").read_text(
            encoding="utf-8"
        )
    )
    for event in ("SessionStart", "SessionEnd"):
        commands = [
            h["command"]
            for entry in hooks_json["hooks"][event]
            for h in entry["hooks"]
            if h["type"] == "command"
        ]
        assert any("session_guard.py" in c for c in commands), event
    # SessionEnd only for the marker check — a Stop registration would nag a
    # legitimately-open session every turn (protocol doc's event-binding note).
    assert "Stop" not in hooks_json["hooks"]


# --- round-1 convergence additions ------------------------------------------


def test_unstattable_marker_state_warns_conservatively(tmp_path, capsys):
    # The D-11 backstop must not fail silent in the no-warning direction: a
    # state path that cannot be statted cannot rule out an uncleared marker,
    # so the guard warns (Constitution II).
    root = make_root(tmp_path)
    (root / ".bb-session").write_text("a file where a dir should be",
                                      encoding="utf-8")
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("{}\n", encoding="utf-8")
    capsys.readouterr()
    exit_code, stdout, stderr = run_end(root, str(transcript))
    assert exit_code == 0
    assert "session row not persisted" in stderr
    assert "session row not persisted" in json.loads(stdout)["systemMessage"]
    assert "marker" in capsys.readouterr().err  # the bb-state cause diagnostic


def test_warning_omits_label_for_non_string_session_id(tmp_path):
    root = make_root(tmp_path)
    state = root / ".bb-session"
    state.mkdir()
    (state / "marker.json").write_text(
        json.dumps({"protocol": "bb.local.v1", "session_id": 42}),
        encoding="utf-8",
    )
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("{}\n", encoding="utf-8")
    _, _, stderr = run_end(root, str(transcript))
    assert "session row not persisted" in stderr
    assert "for session" not in stderr  # unusable id ⇒ no label, no crash


def test_staging_destination_failure_is_not_blamed_on_the_source(
    tmp_path, capsys
):
    # .bb-session as a file breaks the staging write; the source exists and
    # is readable — the notice must not claim it is missing/unreadable, and
    # the real cause lands on the bb-state diagnostic.
    root = make_root(tmp_path)
    (root / ".bb-session").write_text("a file where a dir should be",
                                      encoding="utf-8")
    source = tmp_path / "t.jsonl"
    source.write_text("{}\n", encoding="utf-8")
    capsys.readouterr()
    _, _, stderr = run_end(root, str(source))
    assert "staging failed" in stderr
    assert "source exists" in stderr
    assert "missing source" not in stderr
    assert "staging failed" in capsys.readouterr().err  # underlying OSError


def test_unrecognized_event_leaves_a_breadcrumb(tmp_path):
    root = make_root(tmp_path)
    payload = {"hook_event_name": "SomeFutureEvent", "cwd": str(root)}
    exit_code, _, stderr = session_guard.run(json.dumps(payload))
    assert exit_code == 0
    assert "unrecognized hook_event_name" in stderr


def test_tool_events_are_a_quiet_no_op(tmp_path):
    # The shared fault corpus drives this hook with tool events; those are
    # not session-scoped and produce neither warning nor breadcrumb.
    root = make_root(tmp_path)
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
               "cwd": str(root)}
    assert session_guard.run(json.dumps(payload)) == (0, "", "")


# --- round-2 convergence additions ------------------------------------------


def run_start_with(root, source):
    payload = {
        "hook_event_name": "SessionStart",
        "cwd": str(root),
        "session_id": "us5-session",
        "source": source,
    }
    return session_guard.run(json.dumps(payload))


def test_stale_marker_at_session_start_warns(tmp_path):
    # D-11 mirror: a marker already present when a session STARTS is the
    # skipped-/close state, warned at a point where rendering is unambiguous.
    root = make_root(tmp_path)
    state = root / ".bb-session"
    state.mkdir()
    (state / "marker.json").write_text(
        json.dumps({"protocol": "bb.local.v1",
                    "session_id": "page-ALERT-9-2026-07-20"}),
        encoding="utf-8",
    )
    exit_code, stdout, stderr = run_start_with(root, "startup")
    assert exit_code == 0
    assert "run /close" in stderr
    message = json.loads(stdout)["systemMessage"]
    assert "session row not persisted" in message
    assert "page-ALERT-9-2026-07-20" in message


def test_resume_with_open_marker_does_not_nag(tmp_path):
    # Resuming a legitimately-open session is not the stale case — the
    # false-nag exemption that kept the check off the Stop event applies.
    root = make_root(tmp_path)
    claude = root / ".claude"
    claude.mkdir()
    (claude / "settings.json").write_text(
        json.dumps({"battleBuddy": {}}), encoding="utf-8"
    )  # config present, so only the marker logic is under test
    state = root / ".bb-session"
    state.mkdir()
    (state / "marker.json").write_text(
        json.dumps({"protocol": "bb.local.v1", "session_id": "x"}),
        encoding="utf-8",
    )
    exit_code, stdout, stderr = run_start_with(root, "resume")
    assert exit_code == 0
    assert "run /close" not in stderr
    assert stdout == ""


def test_session_start_without_marker_stays_quiet_on_markers(tmp_path):
    root = make_root(tmp_path)
    claude = root / ".claude"
    claude.mkdir()
    (claude / "settings.json").write_text(
        json.dumps({"battleBuddy": {}}), encoding="utf-8"
    )
    exit_code, stdout, stderr = run_start_with(root, "startup")
    assert exit_code == 0
    assert stdout == ""
    assert "run /close" not in stderr


# --- round-3 convergence additions: the SessionStart source matrix ----------


def _root_with_marker_and_config(tmp_path):
    root = make_root(tmp_path)
    claude = root / ".claude"
    claude.mkdir()
    (claude / "settings.json").write_text(
        json.dumps({"battleBuddy": {}}), encoding="utf-8"
    )
    state = root / ".bb-session"
    state.mkdir()
    (state / "marker.json").write_text(
        json.dumps({"protocol": "bb.local.v1", "session_id": "x"}),
        encoding="utf-8",
    )
    return root


def test_compact_with_open_marker_does_not_nag(tmp_path):
    # Auto-compaction fires SessionStart mid-session with NO preceding
    # SessionEnd — the marker is legitimately open; a warning here would be
    # the false-nag failure that keeps this check off the Stop event.
    root = _root_with_marker_and_config(tmp_path)
    exit_code, stdout, stderr = run_start_with(root, "compact")
    assert exit_code == 0
    assert stdout == ""
    assert "run /close" not in stderr


def test_clear_with_open_marker_does_not_nag_twice(tmp_path):
    # /clear fires SessionEnd (which already warned) then SessionStart in
    # the same workspace — the start side must not duplicate the warning.
    root = _root_with_marker_and_config(tmp_path)
    exit_code, stdout, stderr = run_start_with(root, "clear")
    assert exit_code == 0
    assert stdout == ""
    assert "run /close" not in stderr


def test_unknown_future_source_does_not_nag(tmp_path):
    # An unknown source value is likelier a future mid-session event than a
    # fresh start — false nags on the loud channel are worse than deferring
    # to the SessionEnd check.
    root = _root_with_marker_and_config(tmp_path)
    exit_code, stdout, stderr = run_start_with(root, "some-future-source")
    assert exit_code == 0
    assert stdout == ""
    assert "run /close" not in stderr


def test_missing_source_field_is_treated_as_startup(tmp_path):
    # Older/simple harnesses may omit source; a fresh start is the common
    # case there, and the warning is truthful for it.
    root = _root_with_marker_and_config(tmp_path)
    payload = {"hook_event_name": "SessionStart", "cwd": str(root),
               "session_id": "s"}
    exit_code, stdout, stderr = session_guard.run(json.dumps(payload))
    assert exit_code == 0
    assert "run /close" in stderr
    assert "session row not persisted" in json.loads(stdout)["systemMessage"]
