#!/usr/bin/env python3
"""bb-shell — the shell adapter (design §6.3, §3.1, §11 D-2, D-9).

Four verbs, one config-selected backend, and a fail-soft rule::

    bb-shell open-pane <url|command> [--workspace <session-id>]
    bb-shell navigate-pane <pane> <url>
    bb-shell notify <message> [--level <info|warn|approval>]
    bb-shell close-workspace <session-id>

Three implementations sit behind one dispatcher:

* ``DegradedBackend`` — prints a link or message for every verb. The default,
  the non-Mac path (R-1), and the universal fallback. Fully functional
  (FR-003, FR-026); never an error state.
* ``CmuxBackend`` — speaks cmux's socket API (``cmux-socket`` v2: newline-
  delimited JSON over AF_UNIX). See ``bb-shell.cmux.md``.
* the fail-soft wrapper — any backend failure (socket absent, refused, timed
  out, died mid-write, error response, malformed reply) becomes the degraded
  output, with a diagnostic note on stderr and exit success (FR-005, §9's R-2
  row). A shell failure must never brick a session.

The one loud path is a **usage error** (unknown verb, malformed arguments):
those are caller bugs, not availability events, and exit 2.

The shim is a pure function of (arguments, config, socket behavior) ->
(exit code, output, protocol traffic): no persistent state, no backend-health
memory, no reads beyond config and its socket (FR-009). Repeated failures are
therefore independent, and recovery is automatic.

Python 3.9-compatible, stdlib only (Constitution Platform Constraints, D-1).
"""

import argparse
import json
import os
import sys

EXIT_OK = 0
EXIT_USAGE = 2

#: The closed set of notification levels. ``--level`` is **optional**, defaulting
#: to ``info``: slice 4's doctor round-trip calls ``notify`` with no level at all
#: (``tests/helpers/doctor_flows.py::check_shell``), so a mandatory flag would
#: break a landed slice. An *unrecognized* level is still a usage error — the
#: same absent-vs-unrecognized split FR-002 draws for the config value.
LEVELS = ("info", "warn", "approval")
DEFAULT_LEVEL = "info"

#: Recognized backends. Anything else selects degraded mode with a notice.
BACKEND_CMUX = "cmux"
BACKEND_NONE = "none"

SETTINGS_RELPATH = os.path.join(".claude", "settings.json")

#: URL schemes that make an ``open-pane`` target a browser surface rather than a
#: command. Anything else is a command (the agent terminal pane is opened that
#: way, so the command form is not an edge case — it is half the verb).
URL_SCHEMES = ("http://", "https://", "file://")


class UsageError(Exception):
    """A caller bug: unknown verb, malformed arguments. The one loud path.

    Deliberately distinct from any backend failure: FR-005 makes backend
    *availability* fail soft, and makes caller bugs stay loud. Raising these
    before a backend is ever constructed is what keeps the two from colliding.
    """


class _Parser(argparse.ArgumentParser):
    """ArgumentParser that raises instead of calling ``sys.exit``.

    argparse's default error path exits the process from under ``main()``,
    which would make the exit code argparse's business rather than ours and
    would bypass the usage-error contract above.
    """

    def error(self, message):
        raise UsageError(message)


def build_parser():
    """The complete argument surface (spec 009 data-model.md §1).

    This function *is* the FR-006 credential boundary: the interface admits no
    credential, cookie, session-state, or page-content operation, and cannot be
    made to express one without editing this grammar.
    """
    parser = _Parser(prog="bb-shell", add_help=True)
    subparsers = parser.add_subparsers(dest="verb")

    open_pane = subparsers.add_parser("open-pane", add_help=True)
    open_pane.add_argument("target")
    open_pane.add_argument("--workspace", default=None)

    navigate = subparsers.add_parser("navigate-pane", add_help=True)
    navigate.add_argument("pane")
    navigate.add_argument("url")

    notify = subparsers.add_parser("notify", add_help=True)
    notify.add_argument("message")
    notify.add_argument("--level", default=DEFAULT_LEVEL, choices=LEVELS)

    close = subparsers.add_parser("close-workspace", add_help=True)
    close.add_argument("session_id")

    return parser


def parse_args(argv):
    """Parse ``argv`` into a namespace. Raises UsageError; never exits.

    Kept separate from anything that acts, so the grammar is testable as a pure
    function (FR-009).
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "verb", None):
        raise UsageError("a verb is required")
    return args


def usage_text():
    return build_parser().format_usage()


# ---------------------------------------------------------------------------
# Config selection (FR-002)
# ---------------------------------------------------------------------------


def select_backend(root=None):
    """Resolve ``battleBuddy.shell`` to a backend name plus diagnostic notices.

    Returns ``(backend_name, notices)``. Never raises, never writes — the
    posture ``hooks/_config.py`` documents, reimplemented here rather than
    imported because ``bin/`` shims put only their own directory on sys.path
    and neither landed ``bin/`` module imports a local sibling (research R10).

    FR-002's split, which is three behaviors and not one:

    * key absent          -> degraded, **silent** (the shell-less team's normal
      state; a per-call notice for a normal state is noise)
    * ``none`` / ``cmux`` -> that backend, silent
    * unrecognized value  -> degraded, **with a notice** (a probable typo must
      be visible)
    """
    notices = []
    if root is None:
        root = os.getcwd()
    settings = _read_settings(root, notices)
    block = settings.get("battleBuddy") if isinstance(settings, dict) else None

    if block is None:
        return BACKEND_NONE, notices
    if not isinstance(block, dict):
        notices.append("battleBuddy config block is not an object; treated as absent")
        return BACKEND_NONE, notices

    if "shell" not in block:
        return BACKEND_NONE, notices  # silent: absence is the normal state

    value = block.get("shell")
    if value in (BACKEND_CMUX, BACKEND_NONE):
        return value, notices
    notices.append(
        "battleBuddy.shell %r is not a recognized shell adapter; "
        "using degraded mode" % (value,)
    )
    return BACKEND_NONE, notices


def _read_settings(root, notices):
    path = os.path.join(str(root), SETTINGS_RELPATH)
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        notices.append("workspace config unreadable (%s); treated as absent" % exc)
        return {}


def main(argv=None):
    """Entry point. Returns the process exit code."""
    if argv is None:
        argv = sys.argv[1:]
    try:
        parse_args(argv)
    except UsageError as exc:
        sys.stderr.write("bb-shell: %s\n%s" % (exc, usage_text()))
        return EXIT_USAGE
    return EXIT_OK
