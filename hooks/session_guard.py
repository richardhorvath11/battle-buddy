#!/usr/bin/env python3
"""Session guard — unpersisted-record detection + transcript staging (US5).

One script, two event bindings (research R1), dispatching on
``hook_event_name``:

- **SessionStart** — the config-presence warning (FR-015, design §2.1): a
  session-scoped event firing in a directory without the workspace
  ``battleBuddy`` config block warns "run from the workspace repo" without
  blocking. Config-read notices surface here too (fail-open visibility, R13).

The two spec-required warnings (FR-011's marker warning, FR-015's config
warning) are addressed to the *responder*, and an exit-0 hook's stderr never
reaches the responder in normal operation — so they additionally ride the
runtime's documented user-visible channel, a ``systemMessage`` JSON object on
stdout. Fail-open and degraded-mode *diagnostics* stay stderr-only per R13;
the split is deliberate (spec warnings must be loud, diagnostics must be
visible-in-debug).
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
    "The session marker%s was not cleared by a confirmed close: the session "
    "record in storage is missing or was never finalized. Reopen the "
    "workspace and run /close so the record is written and artifacts are "
    "uploaded.\n"
)

CONFIG_WARNING = (
    "battle-buddy: no workspace config block found (.claude/settings.json -> "
    "battleBuddy). Run battle-buddy sessions from your team workspace repo "
    "(scaffolded by /setup) so bindings and budgets apply; continuing with "
    "deterministic defaults (design §2.1).\n"
)

BROKEN_CONFIG_WARNING = (
    "battle-buddy: the workspace config (.claude/settings.json) exists but "
    "could not be read — bindings and budgets fall back to deterministic "
    "defaults. Fix the settings file (parse details are in the "
    "session_guard config notice); re-running from another directory will "
    "not help.\n"
)

STALE_MARKER_WARNING = (
    "battle-buddy session guard: a previous session's marker%s was not "
    "cleared by a confirmed close — session row not persisted; run /close. "
    "A prior session in this workspace ended without closing, so its record "
    "in storage is missing or was never finalized. Run /close to persist "
    "and clear it before starting new work.\n"
)


def _root_of(payload):
    root = payload.get("cwd")
    if not isinstance(root, str) or not root:
        root = os.getcwd()
    return root


def _warning_stdout(message):
    """The runtime's user-visible channel: systemMessage JSON on stdout
    (exit-0 stderr is debug-log-only — a warning there would reach nobody)."""
    return json.dumps({"systemMessage": message.strip()})


def _marker_label(root):
    marker = _state.read_marker(root)
    if marker and isinstance(marker.get("session_id"), str):
        return " for session %s" % marker["session_id"]
    return ""


def _session_start(payload, root):
    cfg = _config.load_config(root)
    stderr = ""
    warnings = []
    for notice in cfg.notices:
        stderr += "session_guard config notice: %s\n" % notice
    if not cfg.config_present:
        # A broken settings file is not a missing block: prescribing
        # "run from the workspace repo" for a parse error sends the
        # responder to the wrong remedy.
        warnings.append(
            BROKEN_CONFIG_WARNING if cfg.settings_error else CONFIG_WARNING
        )
    # Stale-marker mirror of the SessionEnd check (D-11): a marker already
    # present at a FRESH startup means a prior session ended without a
    # confirmed close — and SessionStart is a point where the runtime
    # reliably renders warnings (SessionEnd rendering happens while the
    # session is tearing down). Only `startup` warns: `resume`, `clear`, and
    # `compact` all fire mid-session with the marker legitimately open
    # (compaction has no preceding SessionEnd at all), and an unknown future
    # source is likelier another mid-session event than a fresh start —
    # false nags on the responder-visible channel are worse than deferring
    # to the SessionEnd check.
    if payload.get("source", "startup") == "startup" \
            and _state.marker_present(root):
        warnings.append(STALE_MARKER_WARNING % _marker_label(root))
    stderr += "".join(warnings)
    stdout = _warning_stdout("\n".join(w.strip() for w in warnings)) \
        if warnings else ""
    return 0, stdout, stderr


def _session_end(payload, root):
    stdout = ""
    stderr = ""
    if _state.marker_present(root):
        warning = MARKER_WARNING % _marker_label(root)
        stderr += warning
        stdout = _warning_stdout(warning)
    transcript = payload.get("transcript_path")
    if isinstance(transcript, str) and transcript:
        if _state.stage_transcript(root, transcript) is None:
            # Distinguish the causes rather than guessing one: a truly
            # missing source is named here; anything else (unreadable source,
            # staging-side write failure) already put the underlying error on
            # bb-state stderr — pointing at the wrong file is worse than
            # pointing at the diagnostic.
            if os.path.exists(transcript):
                stderr += (
                    "session_guard notice: transcript staging failed "
                    "(source exists: %s; cause on the bb-state "
                    "diagnostic)\n" % transcript
                )
            else:
                stderr += (
                    "session_guard notice: transcript staging failed "
                    "(missing source: %s)\n" % transcript
                )
    else:
        stderr += (
            "session_guard notice: no transcript_path in the hook payload; "
            "nothing staged\n"
        )
    return 0, stdout, stderr


def _dispatch(payload):
    event = payload.get("hook_event_name")
    root = _root_of(payload)
    if event == "SessionStart":
        return _session_start(payload, root)
    if event == "SessionEnd":
        return _session_end(payload, root)
    if event in ("PreToolUse", "PostToolUse"):
        # Shared fault-corpus payloads (and any mis-registration) hit this
        # hook with tool events; a quiet no-op is correct — these are not
        # session-scoped, nothing was skipped.
        return 0, "", ""
    return 0, "", (
        "session_guard: ignoring unrecognized hook_event_name %r "
        "(expected SessionStart/SessionEnd)\n" % (event,)
    )


def run(stdin_text):
    """Pure entry point: stdin text -> (exit_code, stdout, stderr).

    Always exit 0 — the guard warns loudly, it never blocks a session
    (FR-011 as a loud warning; fail open everywhere, FR-004).
    """
    try:
        payload = json.loads(stdin_text)
        if not isinstance(payload, dict):
            raise ValueError("hook payload is not a JSON object")
    except (ValueError, RecursionError) as exc:
        # RecursionError: a pathologically nested payload must fail open like
        # any other unreadable one, not escape run() as a traceback.
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
    try:
        if stdout:
            sys.stdout.write(stdout)
        if stderr:
            sys.stderr.write(stderr)
        sys.stdout.flush()
        sys.stderr.flush()
    except OSError:
        pass  # broken pipe on a dying runtime — keep the intended exit code
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
