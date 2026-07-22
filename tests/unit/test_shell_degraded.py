"""Degraded-mode output for every verb, on every selection path.

Covers spec 009 FR-003 and SC-002: four verbs × three selection paths
(``none`` / absent / unrecognized), one behavior — plus the notice-scoping
split that distinguishes them (FR-002).

Degraded mode is asserted on its *exact* text, not merely on "something was
printed": an assertion that only checks for non-empty output passes on a bare
newline, which would be a fully broken 3am path.
"""

import io
import json

import pytest

import bb_shell


def run(argv, tmp_path, settings=None):
    """Invoke main() with captured streams. Returns (code, stdout, stderr)."""
    if settings is not None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        (claude_dir / "settings.json").write_text(
            json.dumps(settings), encoding="utf-8"
        )
    out, err = io.StringIO(), io.StringIO()
    code = bb_shell.main(argv, root=str(tmp_path), env={}, out=out, err=err)
    return code, out.getvalue(), err.getvalue()


# The three selection paths that all resolve to degraded mode (SC-002).
SELECTION_PATHS = {
    "explicit-none": {"battleBuddy": {"shell": "none"}},
    "absent-key": {"battleBuddy": {"sheetUrl": "https://x"}},
    "unrecognized": {"battleBuddy": {"shell": "tmux"}},
}

VERB_CASES = {
    "open-pane-url": (
        ["open-pane", "https://grafana.example/d/abc"],
        "bb-shell: open https://grafana.example/d/abc\n",
    ),
    "open-pane-command": (
        ["open-pane", "htop"],
        "bb-shell: open htop\n",
    ),
    "open-pane-with-workspace": (
        ["open-pane", "https://x/y", "--workspace", "page-A-2026-07-22"],
        "bb-shell: open https://x/y  [workspace: page-A-2026-07-22]\n",
    ),
    "navigate-pane": (
        ["navigate-pane", "surface:4", "https://splunk.example/s?q=1"],
        "bb-shell: https://splunk.example/s?q=1  (pane surface:4)\n",
    ),
    "notify-default-level": (
        ["notify", "triage complete"],
        "bb-shell: [info] triage complete\n",
    ),
    "notify-approval": (
        ["notify", "approve restart?", "--level", "approval"],
        "bb-shell: [approval] approve restart?\n",
    ),
    "close-workspace": (
        ["close-workspace", "page-A-2026-07-22"],
        "bb-shell: close workspace page-A-2026-07-22\n",
    ),
}


@pytest.mark.parametrize("path_name", SELECTION_PATHS)
@pytest.mark.parametrize("case", VERB_CASES.values(), ids=VERB_CASES)
def test_every_verb_prints_the_same_thing_on_every_degraded_path(
    case, path_name, tmp_path
):
    """SC-002: three selection paths, one behavior."""
    argv, expected = case
    code, out, _ = run(argv, tmp_path, SELECTION_PATHS[path_name])
    assert code == bb_shell.EXIT_OK == 0
    assert out == expected


# ---------------------------------------------------------------------------
# FR-002 notice scoping — what separates the three paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("settings", [
    {"battleBuddy": {"shell": "none"}},
    {"battleBuddy": {"sheetUrl": "https://x"}},
    {"otherTool": {}},
])
def test_silent_paths_emit_no_diagnostics(settings, tmp_path):
    """An explicit `none` and a wholly absent key are both normal states; a
    per-call notice for a normal state is noise, not diagnostics."""
    code, out, err = run(["notify", "m"], tmp_path, settings)
    assert code == 0
    assert out
    assert err == ""


def test_no_settings_file_at_all_is_silent(tmp_path):
    """The shell-less team that never ran /setup still gets a working shim."""
    code, out, err = run(["notify", "m"], tmp_path)
    assert (code, err) == (0, "")
    assert out == "bb-shell: [info] m\n"


@pytest.mark.parametrize("value", ["tmux", "cmuxx", "", 3, None])
def test_unrecognized_value_is_noticed_but_still_works(value, tmp_path):
    """A probable typo must be visible — and must not cost the responder the
    feature. Both halves are the requirement."""
    code, out, err = run(["notify", "m"], tmp_path, {"battleBuddy": {"shell": value}})
    assert code == 0
    assert out == "bb-shell: [info] m\n"
    assert "shell" in err


def test_notices_go_to_stderr_never_stdout(tmp_path):
    """A caller capturing stdout must get exactly the responder-facing artifact."""
    _, out, err = run(["open-pane", "https://x"], tmp_path,
                      {"battleBuddy": {"shell": "wat"}})
    assert out == "bb-shell: open https://x\n"
    assert err.strip().startswith("bb-shell:")


def test_urls_print_bare_so_terminals_can_linkify_them(tmp_path):
    """No quoting, no angle brackets, no trailing punctuation glued on: at 3am
    the value of degraded mode is that the link is still clickable."""
    _, out, _ = run(["navigate-pane", "surface:1", "https://x/y?a=1&b=2"], tmp_path,
                    {"battleBuddy": {"shell": "none"}})
    assert "https://x/y?a=1&b=2" in out
    assert "<https://" not in out
    assert '"https://' not in out


def test_degraded_backend_is_usable_directly():
    """The backend object is the D-2 interface; it must stand alone."""
    out = io.StringIO()
    backend = bb_shell.DegradedBackend(out=out)
    result = backend.notify("m", "warn")
    assert result["ok"] is True and result["degraded"] is True
    assert out.getvalue() == "bb-shell: [warn] m\n"
