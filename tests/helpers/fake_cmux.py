"""Fake cmux backend for the slice-9 unit layer (spec 009 FR-008, research R7).

A **real** ``AF_UNIX`` listener on a tmp socket file — not a monkeypatched
``socket`` module. That choice is the point: framing, partial reads, and
connection teardown are exercised for real, so the captured frames in
``captured`` are bytes that actually crossed a socket. Everything stays
hermetic — no network, no cmux, no credentials.

Six fault modes, one per row of the slice's fault matrix (data-model.md §6)::

    absent           the socket path does not exist        (cmux never ran)
    refused          path exists, nothing listening        (stale socket, app dead)
    timeout          accept, then never reply              (app wedged)
    mid_write_death  accept, read part, close              (app crashed mid-call)
    error_response   reply {"ok": false, "error": {...}}   (method/params rejected)
    malformed_line   reply non-JSON bytes                  (protocol drift)

Responses are emitted with **deliberately varied JSON key order** (research R1:
cmux's own response key order is not stable), so a positional-parsing regression
fails here rather than in production.

Dev-only test helper — never shipped.
"""

import json
import os
import shutil
import socket
import tempfile
import threading

#: AF_UNIX paths are capped by ``sun_path`` — 104 bytes on macOS, 108 on Linux.
#: pytest's ``tmp_path`` is far too long to hold a socket, so the fake owns a
#: short directory of its own instead of accepting one. Getting this wrong
#: fails as a bare "AF_UNIX path too long" OSError with no hint of the cause.
SUN_PATH_LIMIT = 100


def _short_tempdir():
    """A temp dir short enough for a socket path. Prefers /tmp on macOS, whose
    default TMPDIR (/var/folders/...) already eats most of the budget."""
    for base in ("/tmp", None):
        if base is not None and not os.path.isdir(base):
            continue
        try:
            path = tempfile.mkdtemp(prefix="bbsh-", dir=base)
        except OSError:
            continue
        if len(os.path.join(path, "s.sock")) <= SUN_PATH_LIMIT:
            return path
        shutil.rmtree(path, ignore_errors=True)
    raise RuntimeError("no temp directory short enough for an AF_UNIX socket")

# Every fake response is built from these keys in one of two orders, alternating
# per response, because the real server was observed emitting both.
_KEY_ORDERS = (("id", "ok", "payload"), ("ok", "payload", "id"))

DEFAULT_WORKSPACE_ID = "WS-0000-FAKE"
DEFAULT_SURFACE_ID = "SF-0000-FAKE"

# Fault mode names (also the accepted values of FakeCmux(fault=...)).
ABSENT = "absent"
REFUSED = "refused"
TIMEOUT = "timeout"
MID_WRITE_DEATH = "mid_write_death"
ERROR_RESPONSE = "error_response"
MALFORMED_LINE = "malformed_line"
WRONG_SHAPE = "wrong_shape"

#: The classes every verb must degrade on — data-model.md §6's matrix.
ALL_FAULTS = (ABSENT, REFUSED, TIMEOUT, MID_WRITE_DEATH, ERROR_RESPONSE, MALFORMED_LINE)

#: WRONG_SHAPE is deliberately *not* in ALL_FAULTS: a reply whose `result` is
#: not an object is harmless to verbs that never read the result (notify,
#: navigate-pane succeed correctly), and only reaches the verbs that resolve a
#: workspace. Folding it into the every-verb matrix would assert a fallback that
#: should not happen. It gets targeted tests instead.
ALL_FAULT_MODES = ALL_FAULTS + (WRONG_SHAPE,)


class FakeCmux(object):
    """Context manager yielding a socket path a CmuxBackend can connect to.

    ``fault=None`` is the healthy server. ``workspaces`` seeds what
    ``workspace.list`` reports, so create-vs-reattach can be driven both ways.
    ``captured`` holds every decoded request frame in send order.
    """

    def __init__(self, fault=None, workspaces=None, results=None):
        if fault is not None and fault not in ALL_FAULT_MODES:
            raise ValueError("unknown fault mode: %r" % (fault,))
        self._dir = _short_tempdir()
        self.path = os.path.join(self._dir, "s.sock")
        self.fault = fault
        self.workspaces = list(workspaces or [])
        self.results = dict(results or {})
        self.captured = []
        self._server = None
        self._thread = None
        self._stop = threading.Event()
        self._response_count = 0

    # -- lifecycle ---------------------------------------------------------

    def __enter__(self):
        if self.fault == ABSENT:
            # Nothing to create: the path must simply not exist.
            return self
        if self.fault == REFUSED:
            # A real socket inode with no listener behind it — what a crashed
            # app leaves on disk. Binding and closing (without unlinking) is
            # what makes connect() raise ECONNREFUSED; a plain regular file
            # would raise ENOTSOCK instead, which is a different bug entirely
            # and would let a shim that only catches ConnectionRefusedError
            # pass this fixture while failing in production.
            stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            stale.bind(self.path)
            stale.close()
            return self
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(self.path)
        self._server.listen(8)
        self._server.settimeout(0.25)
        self._thread = threading.Thread(target=self._serve, name="fake-cmux")
        self._thread.daemon = True
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._stop.set()
        if self._server is not None:
            self._server.close()
        if self._thread is not None:
            # Hard bound: a wedged fake must never hang CI.
            self._thread.join(timeout=5.0)
        try:
            os.unlink(self.path)
        except OSError:
            pass
        shutil.rmtree(self._dir, ignore_errors=True)
        return False

    # -- server loop -------------------------------------------------------

    def _serve(self):
        while not self._stop.is_set():
            try:
                conn, _ = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            threading.Thread(target=self._handle, args=(conn,)).start()

    def _handle(self, conn):
        conn.settimeout(1.0)
        buf = b""
        try:
            while not self._stop.is_set():
                try:
                    chunk = conn.recv(65536)
                except (socket.timeout, OSError):
                    return
                if not chunk:
                    return
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    if not self._reply(conn, line):
                        return
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def _reply(self, conn, line):
        """Handle one request frame. Returns False to drop the connection."""
        try:
            request = json.loads(line.decode("utf-8"))
        except ValueError:
            return False
        self.captured.append(request)

        if self.fault == TIMEOUT:
            # A wedged app: the connection stays *open* and no reply ever comes,
            # so the client's own socket timeout is what has to fire. Simply
            # returning here would let the handler's recv time out and close the
            # connection, which the client sees as a mid-write death — a
            # different fault class, silently making this one a duplicate.
            self._stop.wait(timeout=30.0)
            return False
        if self.fault == MID_WRITE_DEATH:
            conn.sendall(b'{"id": "partial", "ok": tr')  # truncated mid-frame
            return False
        if self.fault == MALFORMED_LINE:
            conn.sendall(b"not json at all\n")
            return True
        if self.fault == WRONG_SHAPE:
            # Parses cleanly, ok:true — but `result` is not an object. The
            # nastiest shape: nothing fails until a caller reads a field.
            conn.sendall(self._frame(request.get("id"), True, ["unexpected"]))
            return True

        request_id = request.get("id")
        if self.fault == ERROR_RESPONSE:
            conn.sendall(self._frame(request_id, False,
                                     {"code": "invalid_params",
                                      "message": "fake: injected error response"}))
            return True

        conn.sendall(self._frame(request_id, True, self._result_for(request)))
        return True

    def _result_for(self, request):
        method = request.get("method")
        if method in self.results:
            return self.results[method]
        if method == "workspace.list":
            return {"workspaces": list(self.workspaces)}
        if method == "workspace.create":
            return {"id": DEFAULT_WORKSPACE_ID,
                    "title": (request.get("params") or {}).get("name")}
        if method == "surface.create":
            return {"id": DEFAULT_SURFACE_ID}
        return {}

    def _frame(self, request_id, ok, payload):
        """Serialize a response line, alternating key order (research R1)."""
        order = _KEY_ORDERS[self._response_count % len(_KEY_ORDERS)]
        self._response_count += 1
        parts = []
        for key in order:
            if key == "id":
                parts.append(('"id"', json.dumps(request_id)))
            elif key == "ok":
                parts.append(('"ok"', "true" if ok else "false"))
            else:
                parts.append(('"result"' if ok else '"error"', json.dumps(payload)))
        body = ", ".join("%s: %s" % (k, v) for k, v in parts)
        return ("{" + body + "}\n").encode("utf-8")

    # -- assertions helpers ------------------------------------------------

    def methods(self):
        """Method names of every captured frame, in send order."""
        return [frame.get("method") for frame in self.captured]

    def params_for(self, method):
        """Params of the first captured frame naming ``method`` (or None)."""
        for frame in self.captured:
            if frame.get("method") == method:
                return frame.get("params")
        return None


def workspace_entry(title, workspace_id=DEFAULT_WORKSPACE_ID, index=0):
    """A ``workspace.list`` entry shaped like the real server's (research R3)."""
    return {"id": workspace_id, "title": title, "index": index,
            "workspace_ref": "workspace:%d" % index, "selected": index == 0}
