"""cmux backend: protocol framing and the verb→method mapping.

Covers spec 009 FR-004 against the fake socket (research R1–R3, R7). Every
assertion is on the **captured request frames** — bytes that actually crossed a
Unix socket — never on the backend's return value alone: a backend that returned
success without sending anything would pass the weaker check.
"""

import io
import json

import pytest

import bb_shell
from helpers.fake_cmux import (
    DEFAULT_WORKSPACE_ID,
    FakeCmux,
    workspace_entry,
)


def run_cmux(argv, tmp_path, fake, workspaces=None):
    """Invoke main() with `shell: cmux` pointed at the fake socket."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "settings.json").write_text(
        json.dumps({"battleBuddy": {"shell": "cmux"}}), encoding="utf-8"
    )
    out, err = io.StringIO(), io.StringIO()
    code = bb_shell.main(
        argv,
        root=str(tmp_path),
        env={"CMUX_SOCKET_PATH": fake.path},
        out=out,
        err=err,
    )
    return code, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# Request envelope (research R1)
# ---------------------------------------------------------------------------


def test_request_envelope_is_id_method_params_newline_terminated(tmp_path):
    with FakeCmux() as fake:
        code, out, err = run_cmux(["notify", "hello"], tmp_path, fake)
    assert code == 0
    assert len(fake.captured) == 1
    frame = fake.captured[0]
    assert set(frame) == {"id", "method", "params"}
    assert isinstance(frame["id"], str) and frame["id"]
    assert isinstance(frame["params"], dict)


def test_backend_success_prints_nothing_and_notices_nothing(tmp_path):
    """A working backend is silent: the pane/notification *is* the output."""
    with FakeCmux() as fake:
        code, out, err = run_cmux(["notify", "hello"], tmp_path, fake)
    assert (code, out, err) == (0, "", "")


def test_response_key_order_does_not_matter(tmp_path):
    """The real server emits both {"id","ok",...} and {"ok",...,"id"}; the fake
    alternates deliberately. Several calls in one invocation therefore see both
    orders, and a positional parser would fail here."""
    listed = [workspace_entry("page-A-2026-07-22")]
    with FakeCmux(workspaces=listed) as fake:
        code, _, err = run_cmux(
            ["open-pane", "https://x", "--workspace", "page-A-2026-07-22"],
            tmp_path, fake,
        )
    assert (code, err) == (0, "")
    assert fake.methods() == ["workspace.list", "surface.create"]


# ---------------------------------------------------------------------------
# Verb → method mapping (data-model.md §5)
# ---------------------------------------------------------------------------


def test_notify_maps_to_notification_create_with_level_in_the_title(tmp_path):
    """cmux has no level field, so the level rides in `title` (research R4).
    US1 AS4 asserts the level reaches the backend — this is where that is true."""
    with FakeCmux() as fake:
        run_cmux(["notify", "approve restart?", "--level", "approval"], tmp_path, fake)
    assert fake.methods() == ["notification.create"]
    params = fake.params_for("notification.create")
    assert params == {"title": "battle-buddy: approval", "body": "approve restart?"}


def test_notify_default_level_also_reaches_the_backend(tmp_path):
    with FakeCmux() as fake:
        run_cmux(["notify", "m"], tmp_path, fake)
    assert fake.params_for("notification.create")["title"] == "battle-buddy: info"


def test_navigate_pane_maps_to_browser_navigate_with_surface_id(tmp_path):
    with FakeCmux() as fake:
        run_cmux(["navigate-pane", "surface:4", "https://ev.example/x"], tmp_path, fake)
    assert fake.methods() == ["browser.navigate"]
    assert fake.params_for("browser.navigate") == {
        "surface_id": "surface:4",
        "url": "https://ev.example/x",
    }


def test_open_pane_without_workspace_creates_a_surface_in_place(tmp_path):
    with FakeCmux() as fake:
        run_cmux(["open-pane", "https://x/y"], tmp_path, fake)
    assert fake.methods() == ["surface.create"]
    assert fake.params_for("surface.create") == {"type": "browser", "url": "https://x/y"}


# ---------------------------------------------------------------------------
# Target typing (data-model.md §4)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("target,expected", [
    ("https://x/y", {"type": "browser", "url": "https://x/y"}),
    ("http://x/y", {"type": "browser", "url": "http://x/y"}),
    ("file:///tmp/a.log", {"type": "browser", "url": "file:///tmp/a.log"}),
    ("htop", {"type": "terminal", "command": "htop"}),
    ("tail -f /var/log/x", {"type": "terminal", "command": "tail -f /var/log/x"}),
])
def test_open_pane_types_the_target_by_scheme(target, expected, tmp_path):
    """The command form is not an edge case: it is how the agent terminal pane
    itself is opened (§6.3)."""
    with FakeCmux() as fake:
        run_cmux(["open-pane", target], tmp_path, fake)
    assert fake.params_for("surface.create") == expected


# ---------------------------------------------------------------------------
# Workspace create vs reattach (FR-004, spec edge case)
# ---------------------------------------------------------------------------


def test_open_pane_creates_the_session_named_workspace_when_absent(tmp_path):
    with FakeCmux(workspaces=[]) as fake:
        code, _, err = run_cmux(
            ["open-pane", "htop", "--workspace", "page-A-2026-07-22"], tmp_path, fake
        )
    assert (code, err) == (0, "")
    assert fake.methods() == ["workspace.list", "workspace.create", "surface.create"]
    assert fake.params_for("workspace.create") == {"name": "page-A-2026-07-22"}
    assert fake.params_for("surface.create")["workspace_id"] == DEFAULT_WORKSPACE_ID


def test_open_pane_reattaches_instead_of_duplicating(tmp_path):
    """Workspaces survive restarts (§6.3): a second open on an existing session
    workspace must add a pane, never create a second workspace."""
    listed = [workspace_entry("page-A-2026-07-22", workspace_id="WS-EXISTING")]
    with FakeCmux(workspaces=listed) as fake:
        run_cmux(["open-pane", "htop", "--workspace", "page-A-2026-07-22"],
                 tmp_path, fake)
    assert "workspace.create" not in fake.methods()
    assert fake.methods() == ["workspace.list", "surface.create"]
    assert fake.params_for("surface.create")["workspace_id"] == "WS-EXISTING"


def test_reattach_matches_on_title_not_on_position(tmp_path):
    listed = [
        workspace_entry("some-other-session", workspace_id="WS-OTHER", index=0),
        workspace_entry("page-A-2026-07-22", workspace_id="WS-MINE", index=1),
    ]
    with FakeCmux(workspaces=listed) as fake:
        run_cmux(["open-pane", "htop", "--workspace", "page-A-2026-07-22"],
                 tmp_path, fake)
    assert fake.params_for("surface.create")["workspace_id"] == "WS-MINE"


def test_close_workspace_resolves_the_title_then_closes_by_id(tmp_path):
    listed = [workspace_entry("page-A-2026-07-22", workspace_id="WS-MINE")]
    with FakeCmux(workspaces=listed) as fake:
        code, _, err = run_cmux(["close-workspace", "page-A-2026-07-22"], tmp_path, fake)
    assert (code, err) == (0, "")
    assert fake.methods() == ["workspace.list", "workspace.close"]
    assert fake.params_for("workspace.close") == {"workspace_id": "WS-MINE"}


def test_closing_an_unknown_workspace_degrades_rather_than_failing(tmp_path):
    """Never a session error — the workspace may already be gone (FR-005)."""
    with FakeCmux(workspaces=[]) as fake:
        code, out, err = run_cmux(["close-workspace", "gone"], tmp_path, fake)
    assert code == 0
    assert out == "bb-shell: close workspace gone\n"
    assert "unavailable" in err


# ---------------------------------------------------------------------------
# Socket path resolution (research R2)
# ---------------------------------------------------------------------------


def test_cmux_socket_path_env_wins():
    path, notices = bb_shell.resolve_socket_path({"CMUX_SOCKET_PATH": "/tmp/a.sock"})
    assert (path, notices) == ("/tmp/a.sock", [])


def test_default_path_when_no_env_is_set():
    path, notices = bb_shell.resolve_socket_path({})
    assert path.endswith("/.local/state/cmux/cmux.sock")
    assert notices == []


def test_deprecated_alias_is_accepted_alone():
    path, notices = bb_shell.resolve_socket_path({"CMUX_SOCKET": "/tmp/b.sock"})
    assert (path, notices) == ("/tmp/b.sock", [])


def test_agreeing_env_vars_are_not_a_conflict():
    path, notices = bb_shell.resolve_socket_path(
        {"CMUX_SOCKET_PATH": "/tmp/a.sock", "CMUX_SOCKET": "/tmp/a.sock"}
    )
    assert (path, notices) == ("/tmp/a.sock", [])


def test_disagreeing_env_vars_degrade_with_a_notice():
    """cmux's own CLI fails here. We degrade with a notice instead: a mistyped
    env var is not a caller bug in FR-005's sense, and bricking a session over
    one would invert the requirement (research R2)."""
    path, notices = bb_shell.resolve_socket_path(
        {"CMUX_SOCKET_PATH": "/tmp/a.sock", "CMUX_SOCKET": "/tmp/b.sock"}
    )
    assert path is None
    assert len(notices) == 1 and "disagree" in notices[0]


def test_disagreeing_env_vars_still_produce_working_output(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "settings.json").write_text(
        json.dumps({"battleBuddy": {"shell": "cmux"}}), encoding="utf-8"
    )
    out, err = io.StringIO(), io.StringIO()
    code = bb_shell.main(
        ["notify", "m"],
        root=str(tmp_path),
        env={"CMUX_SOCKET_PATH": "/tmp/a.sock", "CMUX_SOCKET": "/tmp/b.sock"},
        out=out, err=err,
    )
    assert code == 0
    assert out.getvalue() == "bb-shell: [info] m\n"
    assert "disagree" in err.getvalue()


# ---------------------------------------------------------------------------
# Workspace-id extraction (research R11's disclosed gap)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("payload,expected", [
    ({"workspace_id": "W1"}, "W1"),
    ({"id": "W2"}, "W2"),
    ({"workspace": {"id": "W3"}}, "W3"),
    ({"workspace_id": "W4", "id": "ignored"}, "W4"),
])
def test_workspace_id_is_extracted_from_any_plausible_shape(payload, expected):
    """workspace.create's exact result shape is an unverified gap (R11), so all
    three plausible shapes are accepted rather than guessing one and failing
    opaquely at 3am."""
    assert bb_shell.CmuxBackend._extract_workspace_id(payload) == expected


@pytest.mark.parametrize("payload", [{}, {"id": ""}, {"title": "x"}, None, []])
def test_missing_workspace_id_raises_a_backend_error(payload):
    """Which then fails soft — but it must be a BackendError, not a KeyError."""
    with pytest.raises(bb_shell.BackendError):
        bb_shell.CmuxBackend._extract_workspace_id(payload)


# ---------------------------------------------------------------------------
# Timeout (research R7) — the no-hang precondition
# ---------------------------------------------------------------------------


def test_socket_timeout_constant_is_a_positive_float():
    assert isinstance(bb_shell.SOCKET_TIMEOUT_SECONDS, float)
    assert 0 < bb_shell.SOCKET_TIMEOUT_SECONDS <= 5


def test_timeout_is_actually_applied_to_the_socket(tmp_path):
    """An unset timeout is the real hang risk: asserting the constant exists
    proves nothing on its own."""
    with FakeCmux() as fake:
        backend = bb_shell.CmuxBackend(fake.path)
        sock = backend._connect()
        try:
            assert sock.gettimeout() == bb_shell.SOCKET_TIMEOUT_SECONDS
        finally:
            backend.close()
