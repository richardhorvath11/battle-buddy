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
import socket
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


# ---------------------------------------------------------------------------
# Degraded backend (FR-003) — the default, and the universal fallback
# ---------------------------------------------------------------------------


class DegradedBackend(object):
    """Every call is a printed link or message (§6.3, FR-026, R-1).

    Not an error path and not a stub: this is the non-Mac path and the one
    guaranteed on every platform. URLs are printed bare and unwrapped so a
    terminal's own link detection can make them clickable — being able to click
    through at 3am is the whole value of degraded mode.
    """

    def __init__(self, out=None):
        self.out = out if out is not None else sys.stdout

    def _emit(self, text):
        self.out.write(text + "\n")
        return {"ok": True, "detail": text, "degraded": True}

    def open_pane(self, target, workspace=None):
        # §3.2 step 3 calls this a no-op in degraded mode; the spec's own pin
        # (which this slice owns) says print — including for the command form,
        # since that is how the agent terminal pane itself is opened.
        suffix = "  [workspace: %s]" % workspace if workspace else ""
        return self._emit("bb-shell: open %s%s" % (target, suffix))

    def navigate_pane(self, pane, url):
        return self._emit("bb-shell: %s  (pane %s)" % (url, pane))

    def notify(self, message, level=DEFAULT_LEVEL):
        return self._emit("bb-shell: [%s] %s" % (level, message))

    def close_workspace(self, session_id):
        return self._emit("bb-shell: close workspace %s" % session_id)


# ---------------------------------------------------------------------------
# cmux backend (FR-004) — see bb-shell.cmux.md
# ---------------------------------------------------------------------------


class BackendError(Exception):
    """A backend call did not succeed. Always fails soft (FR-005)."""


#: Applied to connect and to every recv. A wedged app must not add perceptible
#: latency to the 3am path (NFR-1); a healthy local IPC reply is sub-millisecond.
#: Named so a test can assert a timeout is set at all — an unset timeout is the
#: actual hang risk SC-003 forbids.
SOCKET_TIMEOUT_SECONDS = 2.0

DEFAULT_SOCKET_RELPATH = os.path.join(".local", "state", "cmux", "cmux.sock")


def resolve_socket_path(env=None):
    """Resolve the cmux socket path. Returns ``(path_or_None, notices)``.

    Order (research R2): ``CMUX_SOCKET_PATH``, else the documented default.
    ``CMUX_SOCKET`` is a deprecated alias; cmux's own CLI fails when both are
    set and differ, so a disagreeing pair returns ``None`` — degraded with a
    notice rather than a nonzero exit, because a mistyped env var is not a
    caller bug in the FR-005 sense and bricking a session over it would invert
    the requirement's intent.

    Undocumented tagged/debug socket auto-discovery is deliberately *not*
    reimplemented (research R2's stated gap): teams whose socket is tagged set
    CMUX_SOCKET_PATH, which is cmux's own supported override.
    """
    notices = []
    if env is None:
        env = os.environ
    canonical = env.get("CMUX_SOCKET_PATH")
    deprecated = env.get("CMUX_SOCKET")
    if canonical and deprecated and canonical != deprecated:
        notices.append(
            "CMUX_SOCKET_PATH and the deprecated CMUX_SOCKET disagree; "
            "using degraded mode until one is removed"
        )
        return None, notices
    path = canonical or deprecated
    if path:
        return path, notices
    return os.path.join(os.path.expanduser("~"), DEFAULT_SOCKET_RELPATH), notices


def _is_url(target):
    return target.startswith(URL_SCHEMES)


class CmuxBackend(object):
    """Speaks cmux's socket API: ``cmux-socket`` v2 (research R1–R3).

    Newline-delimited JSON over AF_UNIX — one request line, one response line::

        {"id", "method", "params"} -> {"id", "ok", "result"|"error"}

    Response key order is **not** stable on the real server, so responses are
    parsed as JSON and never by position.
    """

    def __init__(self, socket_path, timeout=SOCKET_TIMEOUT_SECONDS, env=None):
        self.socket_path = socket_path
        self.timeout = timeout
        self.env = os.environ if env is None else env
        self._sock = None
        self._call_count = 0

    # -- transport ---------------------------------------------------------

    def _connect(self):
        if self._sock is not None:
            return self._sock
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self.socket_path)
        self._sock = sock
        return sock

    def close(self):
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def call(self, method, params):
        """Send one request, return its ``result``. Raises BackendError."""
        sock = self._connect()
        self._call_count += 1
        request = {"id": "bb-%d" % self._call_count, "method": method,
                   "params": params}
        sock.sendall(json.dumps(request).encode("utf-8") + b"\n")

        buf = b""
        while b"\n" not in buf:
            # Must loop: a single recv() is the classic partial-read bug, and a
            # backend dying mid-write is one of the fault classes (FR-005).
            chunk = sock.recv(65536)
            if not chunk:
                raise BackendError("cmux closed the connection mid-response")
            buf += chunk
        line = buf.split(b"\n", 1)[0]
        try:
            response = json.loads(line.decode("utf-8"))
        except ValueError as exc:
            raise BackendError("cmux sent an unparseable response (%s)" % exc)
        if not isinstance(response, dict):
            raise BackendError("cmux sent a non-object response")
        if not response.get("ok"):
            error = response.get("error") or {}
            raise BackendError(
                "cmux rejected %s: %s (%s)"
                % (method, error.get("message", "no message"),
                   error.get("code", "no code"))
            )
        return response.get("result") or {}

    # -- verbs -------------------------------------------------------------

    def open_pane(self, target, workspace=None):
        params = self._surface_params(target)
        if workspace is not None:
            params["workspace_id"] = self._workspace_id_for(workspace, create=True)
        self.call("surface.create", params)
        return {"ok": True, "detail": target, "degraded": False}

    def navigate_pane(self, pane, url):
        # cmux's browser.navigate addresses a *surface*; a cmux pane is a split
        # container holding surfaces. The interface says "pane" because that is
        # the backend-independent word (and slice 5 already calls it that) —
        # the mapping lives here and in bb-shell.cmux.md (research R6).
        self.call("browser.navigate", {"surface_id": pane, "url": url})
        return {"ok": True, "detail": url, "degraded": False}

    def notify(self, message, level=DEFAULT_LEVEL):
        # cmux's notification.create has no level/priority/urgency field, so the
        # level rides in `title` — the field cmux renders most prominently and
        # the one notification.list always returns populated, which is what makes
        # "the level reached the backend" checkable against captured traffic
        # (research R4). `subtitle` was rejected: optional in cmux's model and
        # observed empty on real notifications.
        self.call("notification.create",
                  {"title": "battle-buddy: %s" % level, "body": message})
        return {"ok": True, "detail": message, "degraded": False}

    def close_workspace(self, session_id):
        workspace_id = self._workspace_id_for(session_id, create=False)
        self.call("workspace.close", {"workspace_id": workspace_id})
        return {"ok": True, "detail": session_id, "degraded": False}

    # -- helpers -----------------------------------------------------------

    def _surface_params(self, target):
        if _is_url(target):
            return {"type": "browser", "url": target}
        return {"type": "terminal", "command": target}

    def _workspace_id_for(self, session_id, create):
        """Resolve a session-named workspace, optionally creating it.

        This is the reattach path (§6.3 "workspaces survive restarts"): the
        backend's own truth is read on **every** invocation, so the shim keeps
        no workspace state and concurrent invocations cannot disagree (FR-009).
        """
        listed = self.call("workspace.list", {})
        for entry in listed.get("workspaces") or []:
            if isinstance(entry, dict) and entry.get("title") == session_id:
                return self._extract_workspace_id(entry)
        if not create:
            raise BackendError("no cmux workspace titled %r" % (session_id,))
        return self._extract_workspace_id(
            self.call("workspace.create", {"name": session_id})
        )

    @staticmethod
    def _extract_workspace_id(payload):
        """Pull a workspace id out of a list entry or a create result.

        Defensive by design: `workspace.create`'s exact result shape is research
        R11's stated unverified gap, so the three plausible shapes are all
        accepted rather than guessing one and failing opaquely at 3am.
        """
        if isinstance(payload, dict):
            for key in ("workspace_id", "id"):
                value = payload.get(key)
                if isinstance(value, str) and value:
                    return value
            nested = payload.get("workspace")
            if isinstance(nested, dict):
                return CmuxBackend._extract_workspace_id(nested)
        raise BackendError("cmux returned no workspace id (%r)" % (payload,))


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def _invoke(backend, args):
    """Call the verb ``args`` names on ``backend``."""
    if args.verb == "open-pane":
        return backend.open_pane(args.target, args.workspace)
    if args.verb == "navigate-pane":
        return backend.navigate_pane(args.pane, args.url)
    if args.verb == "notify":
        return backend.notify(args.message, args.level)
    return backend.close_workspace(args.session_id)


def main(argv=None, root=None, env=None, out=None, err=None):
    """Entry point. Returns the process exit code."""
    if argv is None:
        argv = sys.argv[1:]
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err

    try:
        args = parse_args(argv)
    except UsageError as exc:
        err.write("bb-shell: %s\n%s" % (exc, usage_text()))
        return EXIT_USAGE

    backend_name, notices = select_backend(root)
    degraded = DegradedBackend(out=out)

    if backend_name == BACKEND_CMUX:
        socket_path, path_notices = resolve_socket_path(env)
        notices.extend(path_notices)
        if socket_path is not None:
            cmux = CmuxBackend(socket_path, env=env)
            try:
                _invoke(cmux, args)
                _write_notices(err, notices)
                return EXIT_OK
            except _SOFT_FAILURES as exc:
                # FR-005: any backend failure becomes the degraded output, with
                # a note, and exit success. Phase 4 widens the assertions; the
                # seam lands here so no intermediate commit can crash on a dead
                # socket.
                notices.append("shell backend unavailable (%s); printed instead" % exc)
            finally:
                cmux.close()

    _invoke(degraded, args)
    _write_notices(err, notices)
    return EXIT_OK


#: Everything the fail-soft seam absorbs. OSError covers socket.error,
#: ConnectionRefusedError, FileNotFoundError, BrokenPipeError,
#: ConnectionResetError and socket.timeout; ValueError covers json decoding.
_SOFT_FAILURES = (BackendError, OSError, ValueError)


def _write_notices(err, notices):
    for notice in notices:
        err.write("bb-shell: %s\n" % notice)
