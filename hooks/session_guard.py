#!/usr/bin/env python3
"""Session guard — unpersisted-record detection + transcript staging (US5).

One script, two event bindings (research R1), dispatching on
``hook_event_name``:

- **SessionStart** — the config-presence warning (FR-015, design §2.1): a
  session-scoped event firing in a directory without the workspace
  ``battleBuddy`` config block warns "run from the workspace repo" without
  blocking. Config-read notices surface here too (fail-open visibility, R13).
- **SessionEnd** — the D-11 deterministic backstop (FR-011): the session
  marker's *presence* is the trigger — a marker exists until a confirmed
  close deletes it (deletion is the cleared state), so both the
  open-unconfirmed and the open-confirmed-never-closed (skipped ``/close``)
  states warn loudly with the remedial instruction, regardless of
  ``open_write_confirmed``. SessionEnd, not Stop: Stop would nag a
  legitimately-open session after every turn (protocol doc's event-binding
  note); a blocking variant is deferred until the runtime has a clean
  blocking end-of-session point. The runtime transcript is also copied into
  ``.bb-session/staging/`` (FR-012), degrading to a logged notice on a
  missing/unreadable source — never a session-ending failure.

The guard warns, it never blocks: every path exits 0 with diagnostics on
stderr (FR-004, decision R13). Python 3.9-compatible, stdlib only.
"""

import json
import os
import sys

import _config
import _state

MARKER_WARNING = (
    "battle-buddy session guard: session row not persisted — run /close. "
    "The session marker%s is still present, meaning no confirmed close "
    "cleared it: the session record in storage is missing or was never "
    "finalized. Reopen the workspace and run /close so the record is "
    "written and artifacts are uploaded.\n"
)

CONFIG_WARNING = (
    "battle-buddy: no workspace config block found (.claude/settings.json -> "
    "battleBuddy). Run battle-buddy sessions from your team workspace repo "
    "(scaffolded by /setup) so bindings and budgets apply; continuing with "
    "deterministic defaults (design §2.1).\n"
)


def _root_of(payload):
    root = payload.get("cwd")
    if not isinstance(root, str) or not root:
        root = os.getcwd()
    return root


def _session_start(payload, root):
    cfg = _config.load_config(root)
    stderr = ""
    for notice in cfg.notices:
        stderr += "session_guard config notice: %s\n" % notice
    if not cfg.config_present:
        stderr += CONFIG_WARNING
    return 0, "", stderr


def _session_end(payload, root):
    stderr = ""
    if _state.marker_present(root):
        marker = _state.read_marker(root)
        label = ""
        if marker and isinstance(marker.get("session_id"), str):
            label = " for session %s" % marker["session_id"]
        stderr += MARKER_WARNING % label
    transcript = payload.get("transcript_path")
    if isinstance(transcript, str) and transcript:
        if _state.stage_transcript(root, transcript) is None:
            stderr += (
                "session_guard notice: transcript staging failed "
                "(missing/unreadable source: %s)\n" % transcript
            )
    else:
        stderr += (
            "session_guard notice: no transcript_path in the hook payload; "
            "nothing staged\n"
        )
    return 0, "", stderr


def _dispatch(payload):
    event = payload.get("hook_event_name")
    root = _root_of(payload)
    if event == "SessionStart":
        return _session_start(payload, root)
    if event == "SessionEnd":
        return _session_end(payload, root)
    return 0, "", ""


def run(stdin_text):
    """Pure entry point: stdin text -> (exit_code, stdout, stderr).

    Always exit 0 — the guard warns loudly, it never blocks a session
    (FR-011 as a loud warning; fail open everywhere, FR-004).
    """
    try:
        payload = json.loads(stdin_text)
        if not isinstance(payload, dict):
            raise ValueError("hook payload is not a JSON object")
    except ValueError as exc:
        return 0, "", "session_guard fail-open: unreadable payload (%s)\n" % exc
    try:
        return _dispatch(payload)
    except Exception as exc:  # any internal error must not end the session
        return 0, "", "session_guard fail-open: internal error (%s)\n" % exc


def main():
    try:
        stdin_text = sys.stdin.read()
    except Exception as exc:
        sys.stderr.write("session_guard fail-open: stdin unreadable (%s)\n" % exc)
        sys.exit(0)
    exit_code, stdout, stderr = run(stdin_text)
    if stdout:
        sys.stdout.write(stdout)
    if stderr:
        sys.stderr.write(stderr)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
