"""Local-state protocol helpers — ``bb.local.v1`` (contracts/local-state-protocol.md).

Not a hook: shipped beside its consumers (guardrail_deny, tool_trace,
session_guard). This module is the *only* code that touches ``.bb-session/``;
the protocol document is the contract, this is its one implementation.

Invariants implemented here, per the protocol doc:
- ``seq`` is a line sequence assigned atomically at append time from
  ``counters.json`` under ``fcntl.flock``; the trace append happens under the
  same lock, so file order == seq order (gap-free absent a crash between
  counter-increment and append — a crash can skip a value, never duplicate).
- The trace appender never reads ``trace.jsonl``; counts live in the sidecar.
- Turn accounting: checked at PreToolUse, incremented at PostToolUse — callers
  use ``get_turns`` / ``increment_turn``; only executed calls consume a turn.
- Actor identity is derived: stable hash-suffix of the payload's
  ``transcript_path``; roles are registered by convention in ``agents.json``
  (unregistered actor ⇒ caller applies no cap — fail open).

Python 3.9-compatible, stdlib only. POSIX-only locking (macOS/Linux — the
supported runtime platforms).
"""

import contextlib
import fcntl
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone

PROTOCOL = "bb.local.v1"
STATE_DIR_NAME = ".bb-session"
MARKER_NAME = "marker.json"
TRACE_NAME = "trace.jsonl"
COUNTERS_NAME = "counters.json"
AGENTS_NAME = "agents.json"
STAGING_DIR_NAME = "staging"
STAGED_TRANSCRIPT_NAME = "transcript.md"
# Uploaded under this artifact name at close (design §5.3); local name differs.
UPLOADED_TRACE_NAME = "tool-trace.jsonl"

# Auth-context window: consumers of "recent" trace context read this many lines.
AUTH_CONTEXT_WINDOW = 10

# outcome vocabulary (protocol doc). denied:guardrail:<class> is a prefix form.
OUTCOME_OK = "ok"
OUTCOME_ERROR_AUTH = "error:auth"
OUTCOME_ERROR_TIMEOUT = "error:timeout"
OUTCOME_ERROR_OTHER = "error:other"
OUTCOME_DENIED_TURN_CAP = "denied:turn_cap"
OUTCOME_DENIED_GUARDRAIL_PREFIX = "denied:guardrail:"
FIXED_OUTCOMES = (
    OUTCOME_OK,
    OUTCOME_ERROR_AUTH,
    OUTCOME_ERROR_TIMEOUT,
    OUTCOME_ERROR_OTHER,
    OUTCOME_DENIED_TURN_CAP,
)

_TAIL_READ_BYTES = 65536  # bounded tail read: O(1) in trace size (SC-002)


def state_dir(root):
    return os.path.join(str(root), STATE_DIR_NAME)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def actor_key(transcript_path):
    """Stable derived actor identity: hash-suffix of the transcript path.

    The transcript path is the one identity signal the runtime reliably
    provides per agent instance (research R10); no payload field names agents.
    """
    digest = hashlib.sha256(str(transcript_path).encode("utf-8")).hexdigest()
    return "agent-" + digest[:8]


@contextlib.contextmanager
def _locked_counters(root):
    """EX-flock on counters.json; yields the open fd. Creates the state dir."""
    directory = state_dir(root)
    os.makedirs(directory, exist_ok=True)
    fd = os.open(os.path.join(directory, COUNTERS_NAME), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield fd
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _read_counters_fd(fd):
    os.lseek(fd, 0, os.SEEK_SET)
    chunks = []
    while True:
        chunk = os.read(fd, 65536)
        if not chunk:
            break
        chunks.append(chunk)
    try:
        data = json.loads(b"".join(chunks).decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("counters.json is not an object")
    except ValueError:
        data = {}
    data.setdefault("protocol", PROTOCOL)
    if not isinstance(data.get("seq"), int) or isinstance(data.get("seq"), bool):
        data["seq"] = 0
    if not isinstance(data.get("turns"), dict):
        data["turns"] = {}
    return data


def _write_counters_fd(fd, data):
    payload = json.dumps(data, separators=(",", ":")).encode("utf-8")
    os.lseek(fd, 0, os.SEEK_SET)
    os.ftruncate(fd, 0)
    os.write(fd, payload)


def append_trace(root, fields):
    """Append one trace line, assigning the next seq atomically. Returns the line.

    ``fields`` supplies everything but ``protocol`` and ``seq`` (and ``at``,
    filled if absent). The append happens under the counters lock so file
    order == seq order; the appender never reads the trace file.
    """
    with _locked_counters(root) as fd:
        counters = _read_counters_fd(fd)
        counters["seq"] += 1
        _write_counters_fd(fd, counters)
        line = {"protocol": PROTOCOL, "seq": counters["seq"]}
        line.update(fields)
        line.setdefault("at", now_iso())
        encoded = (json.dumps(line, separators=(",", ":")) + "\n").encode("utf-8")
        with open(os.path.join(state_dir(root), TRACE_NAME), "ab") as trace:
            trace.write(encoded)
    return line


def tail_trace(root, n=AUTH_CONTEXT_WINDOW):
    """Last ``n`` parsed trace lines (bounded read; [] when no trace exists)."""
    path = os.path.join(state_dir(root), TRACE_NAME)
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - _TAIL_READ_BYTES))
            raw = f.read()
    except OSError:
        return []
    lines = []
    for text in raw.decode("utf-8", errors="replace").splitlines()[-n:]:
        try:
            parsed = json.loads(text)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            lines.append(parsed)
    return lines


def get_turns(root, actor):
    """Executed-call count for one actor (checked at PreToolUse)."""
    try:
        with _locked_counters(root) as fd:
            counters = _read_counters_fd(fd)
    except OSError:
        return 0
    turns = counters["turns"].get(actor)
    if isinstance(turns, bool) or not isinstance(turns, int):
        return 0
    return turns


def increment_turn(root, actor):
    """Consume one turn for ``actor`` (called at PostToolUse only — executed
    calls consume turns; guardrail- or cap-denied calls never do)."""
    with _locked_counters(root) as fd:
        counters = _read_counters_fd(fd)
        current = counters["turns"].get(actor)
        if isinstance(current, bool) or not isinstance(current, int):
            current = 0
        counters["turns"][actor] = current + 1
        _write_counters_fd(fd, counters)
        return counters["turns"][actor]


def read_roles(root):
    """agents.json role map ``{actor_key: role}``; {} when absent/malformed."""
    path = os.path.join(state_dir(root), AGENTS_NAME)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    roles = data.get("roles") if isinstance(data, dict) else None
    return roles if isinstance(roles, dict) else {}


def role_for(root, actor):
    """Registered role for an actor, or None (unregistered ⇒ caller applies
    no cap — enforcement without identity would cap the wrong agents)."""
    role = read_roles(root).get(actor)
    return role if isinstance(role, str) else None


def marker_present(root):
    """The session-guard trigger: marker file present ⇒ not cleared (deletion
    *is* the cleared state; no resting "closed" state exists on disk)."""
    return os.path.exists(os.path.join(state_dir(root), MARKER_NAME))


def read_marker(root):
    """Parsed marker.json, or None when absent/unreadable (use
    ``marker_present`` for the warn trigger — content is secondary)."""
    path = os.path.join(state_dir(root), MARKER_NAME)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def stage_transcript(root, transcript_path):
    """Copy the runtime's transcript into staging/. Returns the staged path,
    or None when the source is missing/unreadable (caller logs a notice —
    never a session-ending failure)."""
    staging = os.path.join(state_dir(root), STAGING_DIR_NAME)
    destination = os.path.join(staging, STAGED_TRANSCRIPT_NAME)
    try:
        os.makedirs(staging, exist_ok=True)
        shutil.copyfile(str(transcript_path), destination)
    except OSError:
        return None
    return destination
