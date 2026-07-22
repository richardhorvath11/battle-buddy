"""Fail-soft: a dead shell never takes the investigation with it.

Covers spec 009 FR-005, FR-006, FR-009 and SC-003/SC-004 — the 24-case fault
matrix (6 classes × 4 verbs, data-model.md §6), per-invocation independence,
concurrency, and the credential-surface scan over captured traffic.

Every fault case asserts **all three** properties together — degraded output,
exit 0, and a diagnostic note. A case asserting only the exit code would pass
on silence, which SC-003 explicitly forbids.
"""

import io
import json
import threading
import time

import pytest

import bb_shell
from helpers.fake_cmux import ALL_FAULTS, FakeCmux, workspace_entry


def write_cmux_settings(root):
    claude_dir = root / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "settings.json").write_text(
        json.dumps({"battleBuddy": {"shell": "cmux"}}), encoding="utf-8"
    )


def run_cmux(argv, root, socket_path):
    out, err = io.StringIO(), io.StringIO()
    code = bb_shell.main(
        argv, root=str(root), env={"CMUX_SOCKET_PATH": socket_path},
        out=out, err=err,
    )
    return code, out.getvalue(), err.getvalue()


#: The four verbs and the degraded output each must fall back to.
VERB_CASES = {
    "open-pane": (
        ["open-pane", "https://x/y", "--workspace", "page-A-2026-07-22"],
        "bb-shell: open https://x/y  [workspace: page-A-2026-07-22]\n",
    ),
    "navigate-pane": (
        ["navigate-pane", "surface:4", "https://x/y"],
        "bb-shell: https://x/y  (pane surface:4)\n",
    ),
    "notify": (
        ["notify", "the thing broke"],
        "bb-shell: [info] the thing broke\n",
    ),
    "close-workspace": (
        ["close-workspace", "page-A-2026-07-22"],
        "bb-shell: close workspace page-A-2026-07-22\n",
    ),
}


# ---------------------------------------------------------------------------
# SC-003 — the 24-case matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fault", ALL_FAULTS)
@pytest.mark.parametrize("case", VERB_CASES.values(), ids=VERB_CASES)
def test_every_verb_degrades_on_every_fault(case, fault, tmp_path):
    argv, expected_output = case
    write_cmux_settings(tmp_path)
    started = time.time()
    with FakeCmux(fault=fault) as fake:
        code, out, err = run_cmux(argv, tmp_path, fake.path)
    elapsed = time.time() - started

    assert code == bb_shell.EXIT_OK == 0, "a shell failure is never a session error"
    assert out == expected_output, "the degraded output is the fallback, not silence"
    assert err.strip(), "the fallback must be visible in diagnostics"
    assert elapsed < 10, "no fault case may hang"


def test_the_timeout_fault_is_the_clients_timeout_not_a_closed_connection(tmp_path):
    """Regression guard for a real bug in this fixture: if the fake closes a
    wedged connection itself, the client sees a mid-write death and the timeout
    class silently becomes a duplicate — leaving the shim's own socket timeout,
    the thing SC-003's no-hang property actually depends on, untested.

    The distinguishing evidence is wall clock: a closed connection fails
    immediately, a wedged one costs the full timeout."""
    write_cmux_settings(tmp_path)
    started = time.time()
    with FakeCmux(fault="timeout") as fake:
        code, _, _ = run_cmux(["notify", "m"], tmp_path, fake.path)
    elapsed = time.time() - started

    assert code == 0
    assert elapsed >= bb_shell.SOCKET_TIMEOUT_SECONDS * 0.9, (
        "the wedged-backend case returned in %.2fs, faster than the %.1fs socket "
        "timeout — the client timeout did not fire, so this fault class is not "
        "testing what it claims" % (elapsed, bb_shell.SOCKET_TIMEOUT_SECONDS)
    )


def test_the_mid_write_death_fault_is_fast_by_contrast(tmp_path):
    """The other half of the distinction above."""
    write_cmux_settings(tmp_path)
    started = time.time()
    with FakeCmux(fault="mid_write_death") as fake:
        code, _, _ = run_cmux(["notify", "m"], tmp_path, fake.path)
    elapsed = time.time() - started
    assert code == 0
    assert elapsed < bb_shell.SOCKET_TIMEOUT_SECONDS * 0.9


@pytest.mark.parametrize("argv,expected", [
    (["open-pane", "htop", "--workspace", "W"],
     "bb-shell: open htop  [workspace: W]\n"),
    (["close-workspace", "W"], "bb-shell: close workspace W\n"),
])
def test_a_well_formed_reply_of_the_wrong_shape_still_degrades(argv, expected, tmp_path):
    """Review finding: `malformed_line` covers bytes that do not parse. It does
    NOT cover a reply that parses cleanly, says ok:true, and carries a `result`
    that is not an object — the nastiest shape, because nothing fails until a
    caller reads a field. That crashed with an uncaught AttributeError, i.e. a
    shell failure surfacing as a session error, which FR-005 forbids outright.
    Only the verbs that read a result can reach it."""
    write_cmux_settings(tmp_path)
    with FakeCmux(fault="wrong_shape") as fake:
        code, out, err = run_cmux(argv, tmp_path, fake.path)
    assert code == 0
    assert out == expected
    assert err.strip()


@pytest.mark.parametrize("argv", [
    ["notify", "m"],
    ["navigate-pane", "surface:4", "https://x"],
])
def test_verbs_that_ignore_the_result_are_unaffected_by_its_shape(argv, tmp_path):
    """The other half of the finding, and why wrong_shape is not in the
    every-verb matrix: these calls genuinely succeeded, so asserting a fallback
    here would assert a bug."""
    write_cmux_settings(tmp_path)
    with FakeCmux(fault="wrong_shape") as fake:
        code, out, err = run_cmux(argv, tmp_path, fake.path)
    assert (code, out, err) == (0, "", "")


@pytest.mark.parametrize("payload", [["a"], "text", 7, True])
def test_non_object_results_are_normalized_at_the_boundary(payload, tmp_path):
    """Fixed where the shape enters the program, not by broadening the except
    clause — a stray AttributeError elsewhere would be our bug, and should stay
    loud in development."""
    class _Sock(object):
        def __init__(self):
            self.sent = b""

        def sendall(self, data):
            self.sent += data

        def recv(self, _size):
            return json.dumps(
                {"id": "bb-1", "ok": True, "result": payload}
            ).encode() + b"\n"

    backend = bb_shell.CmuxBackend("/unused")
    backend._sock = _Sock()
    assert backend.call("workspace.list", {}) == {}


@pytest.mark.parametrize("fault", ALL_FAULTS)
def test_the_diagnostic_note_names_the_failure(fault, tmp_path):
    """'Noted in diagnostics' means a responder can tell *why* they are looking
    at a printed link instead of a driven pane."""
    write_cmux_settings(tmp_path)
    with FakeCmux(fault=fault) as fake:
        _, _, err = run_cmux(["notify", "m"], tmp_path, fake.path)
    assert "unavailable" in err
    assert "printed instead" in err


# ---------------------------------------------------------------------------
# FR-009 / US2 AS3 — per-invocation independence
# ---------------------------------------------------------------------------


def test_repeated_failures_are_identical_no_lockout_no_backoff(tmp_path):
    """The shim is stateless about backend health, so failure N looks exactly
    like failure 1 — no lockout, no retry storm, no widening backoff."""
    write_cmux_settings(tmp_path)
    outcomes = []
    with FakeCmux(fault="refused") as fake:
        for _ in range(5):
            outcomes.append(run_cmux(["notify", "m"], tmp_path, fake.path))
    assert len(set(outcomes)) == 1, "every failed invocation must be identical"
    assert outcomes[0][0] == 0


def test_recovery_is_automatic_when_the_socket_returns(tmp_path):
    """The point of holding no health memory: the next call after cmux comes
    back uses it, with no reset step anywhere."""
    write_cmux_settings(tmp_path)
    with FakeCmux(fault="refused") as dead:
        dead_code, dead_out, dead_err = run_cmux(["notify", "m"], tmp_path, dead.path)
    with FakeCmux() as alive:
        live_code, live_out, live_err = run_cmux(["notify", "m"], tmp_path, alive.path)
        assert alive.methods() == ["notification.create"]

    assert (dead_code, live_code) == (0, 0)
    assert dead_out == "bb-shell: [info] m\n" and dead_err.strip()
    assert (live_out, live_err) == ("", ""), "a healthy backend prints nothing"


def test_concurrent_invocations_are_independent(tmp_path):
    """Spec edge case: parallel agents citing evidence. Each invocation is its
    own process with its own connection and no shared state in the shim."""
    write_cmux_settings(tmp_path)
    results = {}

    def invoke(index, socket_path):
        results[index] = run_cmux(["notify", "m%d" % index], tmp_path, socket_path)

    with FakeCmux() as fake:
        threads = [
            threading.Thread(target=invoke, args=(i, fake.path)) for i in range(6)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        bodies = sorted(
            frame["params"]["body"] for frame in fake.captured
            if frame.get("method") == "notification.create"
        )

    assert len(results) == 6
    assert all(code == 0 for code, _, _ in results.values())
    assert bodies == sorted("m%d" % i for i in range(6)), "every call reached cmux"


def test_invocation_writes_no_files(tmp_path):
    """FR-009: no reads beyond config and its socket, and no writes at all."""
    write_cmux_settings(tmp_path)
    before = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
    with FakeCmux() as fake:
        run_cmux(["notify", "m"], tmp_path, fake.path)
    with FakeCmux(fault="refused") as fake:
        run_cmux(["notify", "m"], tmp_path, fake.path)
    after = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
    assert before == after


# ---------------------------------------------------------------------------
# SC-003 — usage errors stay loud even when the backend is dead
# ---------------------------------------------------------------------------


def test_usage_errors_stay_loud_with_a_dead_backend(tmp_path):
    """The two halves of FR-005 must never collide: fail-soft covers backend
    *availability*, never a caller bug. Usage errors are raised before a backend
    is constructed, which is the mechanism that keeps them apart."""
    write_cmux_settings(tmp_path)
    with FakeCmux(fault="refused") as fake:
        code, out, err = run_cmux(["frobnicate", "x"], tmp_path, fake.path)
    assert code == bb_shell.EXIT_USAGE == 2
    assert out == ""
    assert "usage" in err.lower()


# ---------------------------------------------------------------------------
# SC-004 / FR-006 — the credential-surface scan
# ---------------------------------------------------------------------------

#: Everything the shim is allowed to ever call (data-model.md §5). cmux's socket
#: exposes 221 methods including browser.eval, browser.cookies.get and
#: browser.storage.*; the boundary that matters is which of them the shim can
#: name at all.
ALLOWED_METHODS = {
    "workspace.list",
    "workspace.create",
    "workspace.close",
    "surface.create",
    "browser.navigate",
    "notification.create",
}

DENIED_VOCABULARY = (
    "cookie", "password", "token", "credential", "session_state",
    "localstorage", "eval", "script", "html", "screenshot", "snapshot",
)


def drive_every_verb(root, socket_path):
    for argv, _ in VERB_CASES.values():
        run_cmux(argv, root, socket_path)


def test_captured_traffic_names_only_allowed_methods(tmp_path):
    write_cmux_settings(tmp_path)
    listed = [workspace_entry("page-A-2026-07-22")]
    with FakeCmux(workspaces=listed) as fake:
        drive_every_verb(tmp_path, fake.path)
        methods = set(fake.methods())
    assert methods, "the scan must not pass vacuously on zero traffic"
    assert methods <= ALLOWED_METHODS


def test_captured_traffic_carries_no_credential_vocabulary(tmp_path):
    write_cmux_settings(tmp_path)
    listed = [workspace_entry("page-A-2026-07-22")]
    with FakeCmux(workspaces=listed) as fake:
        drive_every_verb(tmp_path, fake.path)
        blob = json.dumps(fake.captured).lower()
    assert blob.strip("[]"), "the scan must not pass vacuously on zero traffic"
    for word in DENIED_VOCABULARY:
        assert word not in blob, "captured traffic mentions %r" % word


def test_the_scan_can_actually_fail(tmp_path):
    """Positive control: a scan that cannot fail proves nothing."""
    planted = [{"method": "browser.cookies.get", "params": {"cookie": "session=1"}}]
    blob = json.dumps(planted).lower()
    assert not set(f["method"] for f in planted) <= ALLOWED_METHODS
    assert any(word in blob for word in DENIED_VOCABULARY)


def test_password_env_var_never_reaches_the_wire(tmp_path):
    """The shim passes auth to the socket layer, never into a request frame."""
    write_cmux_settings(tmp_path)
    with FakeCmux() as fake:
        out, err = io.StringIO(), io.StringIO()
        bb_shell.main(
            ["notify", "m"],
            root=str(tmp_path),
            env={"CMUX_SOCKET_PATH": fake.path, "CMUX_SOCKET_PASSWORD": "hunter2"},
            out=out, err=err,
        )
        blob = json.dumps(fake.captured)
    assert "hunter2" not in blob
    assert "hunter2" not in err.getvalue()
