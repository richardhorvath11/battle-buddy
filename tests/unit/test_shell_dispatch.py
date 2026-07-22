"""bb-shell argument grammar, usage errors, and config selection.

Covers spec 009 FR-001 (the four verbs), FR-002 (backend selection), FR-005's
*loud* half and SC-006 (usage errors exit nonzero), plus the FR-006 structural
assertion that the interface cannot express a credential operation.

The grammar is exercised as a pure function — ``parse_args`` returns a value and
never acts — which is the property FR-009 rests on. Later phases extend this
module with the documentation gates (US4).
"""

import argparse
import json
import re

import pytest

import bb_shell
from conftest import REPO_ROOT


# ---------------------------------------------------------------------------
# FR-001 — the four verbs, and only the four verbs
# ---------------------------------------------------------------------------


def test_open_pane_parses_target_and_optional_workspace():
    args = bb_shell.parse_args(["open-pane", "https://grafana.example/d/a"])
    assert args.verb == "open-pane"
    assert args.target == "https://grafana.example/d/a"
    assert args.workspace is None

    args = bb_shell.parse_args(
        ["open-pane", "htop", "--workspace", "page-A-2026-07-22"]
    )
    assert args.target == "htop"
    assert args.workspace == "page-A-2026-07-22"


def test_navigate_pane_parses_two_positionals():
    args = bb_shell.parse_args(["navigate-pane", "surface:4", "https://example.com"])
    assert (args.verb, args.pane, args.url) == (
        "navigate-pane",
        "surface:4",
        "https://example.com",
    )


def test_close_workspace_parses_session_id():
    args = bb_shell.parse_args(["close-workspace", "page-A-2026-07-22"])
    assert (args.verb, args.session_id) == ("close-workspace", "page-A-2026-07-22")


# ---------------------------------------------------------------------------
# FR-001 / research R5 — --level is optional, defaulting to info
# ---------------------------------------------------------------------------


def test_notify_level_defaults_to_info():
    """Slice 4's landed doctor round-trip calls notify with no level at all
    (tests/helpers/doctor_flows.py::check_shell). A mandatory flag would break
    it, so the default is load-bearing, not a convenience."""
    args = bb_shell.parse_args(["notify", "triage complete"])
    assert args.message == "triage complete"
    assert args.level == "info"


@pytest.mark.parametrize("level", ["info", "warn", "approval"])
def test_notify_accepts_every_level_in_the_closed_set(level):
    args = bb_shell.parse_args(["notify", "m", "--level", level])
    assert args.level == level


def test_notify_rejects_a_level_outside_the_closed_set():
    """Absent level -> default (above). *Unrecognized* level -> usage error:
    the same absent-vs-unrecognized split FR-002 draws for the config value."""
    with pytest.raises(bb_shell.UsageError):
        bb_shell.parse_args(["notify", "m", "--level", "critical"])


# ---------------------------------------------------------------------------
# SC-006 / FR-005 (loud half) — every usage-error class exits 2, loudly
# ---------------------------------------------------------------------------

USAGE_ERROR_CASES = {
    "unknown-verb": ["frobnicate", "x"],
    "no-verb": [],
    "open-pane-missing-target": ["open-pane"],
    "open-pane-extra-positional": ["open-pane", "a", "b"],
    "navigate-pane-missing-url": ["navigate-pane", "surface:4"],
    "notify-missing-message": ["notify"],
    "notify-bad-level": ["notify", "m", "--level", "critical"],
    "close-workspace-missing-id": ["close-workspace"],
    "unknown-option": ["notify", "m", "--shout"],
}


@pytest.mark.parametrize("argv", USAGE_ERROR_CASES.values(), ids=USAGE_ERROR_CASES)
def test_usage_errors_exit_two_with_usage_on_stderr(argv, capsys):
    code = bb_shell.main(argv)
    captured = capsys.readouterr()
    assert code == bb_shell.EXIT_USAGE == 2
    assert "usage" in captured.err.lower()
    assert captured.out == "", "usage errors belong on stderr, not stdout"


@pytest.mark.parametrize("argv", USAGE_ERROR_CASES.values(), ids=USAGE_ERROR_CASES)
def test_usage_errors_never_escape_as_systemexit(argv):
    """argparse's default error path calls sys.exit(2) from under main(). The
    exit code must be main()'s return value, not argparse's process exit, or
    the shim's contract belongs to argparse."""
    assert bb_shell.main(argv) == bb_shell.EXIT_USAGE


def test_valid_invocation_is_not_a_usage_error(capsys):
    assert bb_shell.main(["notify", "hello"]) == bb_shell.EXIT_OK
    assert "usage" not in capsys.readouterr().err.lower()


# ---------------------------------------------------------------------------
# FR-006 — the boundary is structural, not a runtime check
# ---------------------------------------------------------------------------

CREDENTIAL_SHAPED_ARGS = [
    ["navigate-pane", "surface:4", "https://x", "--cookie", "session=abc"],
    ["navigate-pane", "surface:4", "https://x", "--header", "Authorization: t"],
    ["open-pane", "https://x", "--token", "secret"],
    ["open-pane", "https://x", "--eval", "document.cookie"],
    ["notify", "m", "--password", "hunter2"],
]


@pytest.mark.parametrize("argv", CREDENTIAL_SHAPED_ARGS)
def test_grammar_cannot_express_a_credential_operation(argv):
    """The captured-traffic scan (US3) only proves the *tested* calls stayed
    clean. This proves nothing else is expressible at all."""
    with pytest.raises(bb_shell.UsageError):
        bb_shell.parse_args(argv)


def test_verb_set_is_exactly_the_documented_four():
    parser = bb_shell.build_parser()
    subparser_actions = [
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ]
    assert len(subparser_actions) == 1
    assert set(subparser_actions[0].choices) == {
        "open-pane",
        "navigate-pane",
        "notify",
        "close-workspace",
    }


# ---------------------------------------------------------------------------
# FR-002 — backend selection, row by row (data-model.md §3)
# ---------------------------------------------------------------------------


def write_settings(root, payload):
    """Write .claude/settings.json under ``root``; ``payload`` may be raw text."""
    claude_dir = root / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    target = claude_dir / "settings.json"
    if isinstance(payload, str):
        target.write_text(payload, encoding="utf-8")
    else:
        target.write_text(json.dumps(payload), encoding="utf-8")
    return root


def test_absent_key_selects_degraded_silently(tmp_path):
    """Absence is the documented normal state for shell-less teams, so it is
    silent. This is the row most likely to be collapsed into a single
    'not cmux -> degraded' branch, taking the notice with it."""
    write_settings(tmp_path, {"battleBuddy": {"sheetUrl": "https://x"}})
    backend, notices = bb_shell.select_backend(str(tmp_path))
    assert backend == bb_shell.BACKEND_NONE
    assert notices == []


def test_absent_settings_file_selects_degraded_silently(tmp_path):
    backend, notices = bb_shell.select_backend(str(tmp_path))
    assert backend == bb_shell.BACKEND_NONE
    assert notices == []


def test_absent_battlebuddy_block_selects_degraded_silently(tmp_path):
    write_settings(tmp_path, {"otherTool": {}})
    backend, notices = bb_shell.select_backend(str(tmp_path))
    assert backend == bb_shell.BACKEND_NONE
    assert notices == []


def test_none_selects_degraded_silently(tmp_path):
    write_settings(tmp_path, {"battleBuddy": {"shell": "none"}})
    backend, notices = bb_shell.select_backend(str(tmp_path))
    assert backend == bb_shell.BACKEND_NONE
    assert notices == []


def test_cmux_selects_the_cmux_backend_silently(tmp_path):
    write_settings(tmp_path, {"battleBuddy": {"shell": "cmux"}})
    backend, notices = bb_shell.select_backend(str(tmp_path))
    assert backend == bb_shell.BACKEND_CMUX
    assert notices == []


@pytest.mark.parametrize("value", ["cmuxx", "tmux", "CMUX", ""])
def test_unrecognized_value_selects_degraded_with_a_notice(tmp_path, value):
    """A probable typo must be visible — the difference from the absent row."""
    write_settings(tmp_path, {"battleBuddy": {"shell": value}})
    backend, notices = bb_shell.select_backend(str(tmp_path))
    assert backend == bb_shell.BACKEND_NONE
    assert len(notices) == 1
    assert "shell" in notices[0]


@pytest.mark.parametrize("value", [True, 3, {}, [], None])
def test_wrong_typed_value_selects_degraded_with_a_notice(tmp_path, value):
    write_settings(tmp_path, {"battleBuddy": {"shell": value}})
    backend, notices = bb_shell.select_backend(str(tmp_path))
    assert backend == bb_shell.BACKEND_NONE
    assert len(notices) == 1


def test_non_object_battlebuddy_block_is_noticed(tmp_path):
    write_settings(tmp_path, {"battleBuddy": "yes please"})
    backend, notices = bb_shell.select_backend(str(tmp_path))
    assert backend == bb_shell.BACKEND_NONE
    assert len(notices) == 1


def test_malformed_settings_file_is_noticed_not_raised(tmp_path):
    write_settings(tmp_path, "{not json at all")
    backend, notices = bb_shell.select_backend(str(tmp_path))
    assert backend == bb_shell.BACKEND_NONE
    assert len(notices) == 1
    assert "unreadable" in notices[0]


def test_select_backend_never_writes(tmp_path):
    """Read-only, always: hooks/_config.py's posture, reimplemented (R10)."""
    write_settings(tmp_path, {"battleBuddy": {"shell": "cmux"}})
    before = sorted(p.name for p in tmp_path.rglob("*"))
    bb_shell.select_backend(str(tmp_path))
    assert sorted(p.name for p in tmp_path.rglob("*")) == before


# ---------------------------------------------------------------------------
# FR-007 / US4 — the interface is documented, backend-independently
# ---------------------------------------------------------------------------

CONTRACT_DOC = REPO_ROOT / "bin" / "bb-shell.md"
BACKEND_DOC = REPO_ROOT / "bin" / "bb-shell.cmux.md"

VERBS = ("open-pane", "navigate-pane", "notify", "close-workspace")

#: Shell products whose names must not leak out of the backend document.
#: Same shape as slice 7's DENY_PATTERNS scan in
#: tests/contract/test_skill_capability_naming.py — reused rather than reinvented.
SHELL_PRODUCT_PATTERNS = {
    "cmux": re.compile(r"\bcmux\b", re.IGNORECASE),
    "tmux": re.compile(r"\btmux\b", re.IGNORECASE),
    "wmux": re.compile(r"\bwmux\b", re.IGNORECASE),
    "iterm": re.compile(r"\biterm2?\b", re.IGNORECASE),
    "ghostty": re.compile(r"\bghostty\b", re.IGNORECASE),
    "screen": re.compile(r"\bgnu screen\b", re.IGNORECASE),
}


def test_contract_document_exists_and_is_substantial():
    assert CONTRACT_DOC.is_file(), "FR-007 requires the contract to ship"
    assert len(CONTRACT_DOC.read_text(encoding="utf-8")) > 1000


@pytest.mark.parametrize("verb", VERBS)
def test_contract_document_defines_every_verb(verb):
    text = CONTRACT_DOC.read_text(encoding="utf-8")
    assert verb in text, "%s is undocumented" % verb


@pytest.mark.parametrize("topic", [
    "degraded", "exit", "usage error", "--level", "--workspace", "reattach",
])
def test_contract_document_covers_the_required_semantics(topic):
    """US4 AS1: arguments, semantics, degraded behavior, failure behavior."""
    assert topic.lower() in CONTRACT_DOC.read_text(encoding="utf-8").lower()


def test_contract_document_names_no_shell_product():
    """US4 AS1: a future shell reads this document; a product name in it would
    make the contract describe one backend instead of the interface."""
    text = CONTRACT_DOC.read_text(encoding="utf-8")
    hits = sorted(
        name for name, pattern in SHELL_PRODUCT_PATTERNS.items()
        if pattern.search(text)
    )
    assert hits == [], "bb-shell.md names shell product(s): %s" % ", ".join(hits)


def test_backend_document_exists_and_is_the_single_exception():
    """The mapping has to live somewhere; concentrating it in one file is what
    makes the scan above expressible at all."""
    assert BACKEND_DOC.is_file()
    assert SHELL_PRODUCT_PATTERNS["cmux"].search(
        BACKEND_DOC.read_text(encoding="utf-8")
    )


def _plugin_prose_files():
    """Command/skill/agent deliverables of every slice."""
    paths = []
    for subdir in ("commands", "skills", "agents"):
        root = REPO_ROOT / subdir
        if root.is_dir():
            paths.extend(sorted(root.rglob("*.md")))
    return paths


def test_the_prose_scan_sees_actual_files():
    """A scan over an empty file set is vacuously green."""
    assert len(_plugin_prose_files()) > 5


@pytest.mark.parametrize(
    "path", _plugin_prose_files(), ids=lambda p: str(p.relative_to(REPO_ROOT))
)
def test_no_command_skill_or_agent_names_a_shell_product(path):
    """US4 AS2: shell interaction appears only as `bb-shell` invocations —
    nothing in the core knows which shell answers (FR-22)."""
    text = path.read_text(encoding="utf-8")
    hits = sorted(
        name for name, pattern in SHELL_PRODUCT_PATTERNS.items()
        if pattern.search(text)
    )
    assert hits == [], "%s names shell product(s): %s" % (
        path.relative_to(REPO_ROOT), ", ".join(hits),
    )


def test_the_product_scan_can_actually_fail():
    """Positive control: a scan that cannot fail proves nothing."""
    planted = "we drive the pane with cmux's socket API"
    hits = [n for n, p in SHELL_PRODUCT_PATTERNS.items() if p.search(planted)]
    assert hits == ["cmux"]
