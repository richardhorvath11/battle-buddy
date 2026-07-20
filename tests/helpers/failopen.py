"""Shared fault-corpus runner: fail-open under fault injection (SC-007).

Every hook's test file reuses this against ``tests/fixtures/faults/*.json``.
A hook is exercised through its pure entry point ``run(stdin_text) ->
(exit_code, stdout, stderr)``; the corpus seeds malformed stdin, broken local
state, and internal exceptions, and asserts the constitutional property: the
call/session always proceeds (exit 0), with the failure visible in
diagnostics — never silent *and* blocking (Constitution III, spec FR-004).
"""

import json
import os
import stat
from pathlib import Path

FAULTS_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "faults"


def fault_cases():
    """All fault fixtures, sorted by filename — for pytest parametrize."""
    return sorted(FAULTS_DIR.glob("*.json"), key=lambda p: p.name)


def fault_ids():
    return [p.stem for p in fault_cases()]


def run_fault(hook_module, fixture_path, tmp_path, monkeypatch, exception_target=None):
    """Run one fault fixture against a hook module's ``run`` entry point.

    - ``hook_module``: the imported hook module (must expose ``run``)
    - ``exception_target``: attribute name of the module's inner evaluation
      function to replace with a raiser for ``seed_exception`` fixtures
    Asserts fail-open (exit 0) and, where the fixture demands it, a visible
    diagnostic on stderr.
    """
    with open(str(fixture_path), encoding="utf-8") as f:
        fault = json.load(f)
    setup = fault.get("setup", {})

    root = tmp_path / "workspace"
    root.mkdir(exist_ok=True)
    state = root / ".bb-session"

    restore_mode = None
    if setup.get("unreadable_state_dir"):
        state.mkdir()
        # chmod(0) does not restrict root — under a root CI container the dir
        # stays readable and the fault would be a no-op (vacuous pass). Skip
        # rather than assert nothing (SF9).
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            import pytest

            pytest.skip("chmod-based unreadable-dir fault is a no-op as root")
        restore_mode = state.stat().st_mode
        os.chmod(str(state), 0)
    elif setup.get("state_dir_is_file"):
        state.write_text("not a directory\n", encoding="utf-8")

    if setup.get("seed_exception"):
        if exception_target is None:
            raise AssertionError(
                "fixture %s needs an exception_target" % fixture_path.name
            )

        def _raiser(*args, **kwargs):
            raise RuntimeError("seeded fault-injection exception")

        monkeypatch.setattr(hook_module, exception_target, _raiser)

    if "stdin" in fault:
        stdin_text = fault["stdin"]
    else:
        payload = dict(fault["payload"])
        payload.setdefault("cwd", str(root))
        payload.setdefault("session_id", "fault-corpus-session")
        payload.setdefault("transcript_path", str(tmp_path / "transcript.jsonl"))
        stdin_text = json.dumps(payload)

    try:
        exit_code, stdout, stderr = hook_module.run(stdin_text)
    finally:
        if restore_mode is not None:
            os.chmod(str(state), stat.S_IMODE(restore_mode) or 0o700)

    assert exit_code == 0, (
        "fail-open violated by %s: exit %r, stderr %r"
        % (fixture_path.name, exit_code, stderr)
    )
    if fault.get("expect_diagnostic"):
        assert stderr.strip(), (
            "%s: failure was silent — diagnostics must be visible" % fixture_path.name
        )
    return exit_code, stdout, stderr
