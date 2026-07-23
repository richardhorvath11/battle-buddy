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
import stat
import sys
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

# Input fields whose string values are commands. Shared by every hook so the
# summary on a trace line is derived identically everywhere — concurrent
# PreToolUse hooks denying the same call produce denied lines with the same
# tool-call identity (agent, tool, summary), which is what the protocol's
# double-deny dedup keys on.
COMMAND_FIELDS = ("command", "cmd", "script", "code", "sql", "query", "statement")
SUMMARY_LIMIT = 120


def state_dir(root):
    return os.path.join(str(root), STATE_DIR_NAME)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def command_texts(tool_input):
    """Command-shaped string values, recursively; data fields never scanned."""
    texts = []

    def walk(node, key=None):
        if isinstance(node, dict):
            for child_key, value in node.items():
                walk(value, child_key)
        elif isinstance(node, list):
            for value in node:
                walk(value, key)
        elif isinstance(node, str) and key in COMMAND_FIELDS:
            texts.append(node)

    walk(tool_input)
    return texts


def summarize_tool_input(tool_input):
    """The trace line's ``summary`` field, derived one way for every hook.

    Command-shaped input summarizes to its first command text; anything else
    to compact sorted JSON — deterministic, so two hooks denying the same call
    emit the same summary (the protocol's dedup identity).
    """
    if isinstance(tool_input, dict):
        texts = command_texts(tool_input)
        if texts:
            return texts[0][:SUMMARY_LIMIT]
        try:
            return json.dumps(
                tool_input, separators=(",", ":"), sort_keys=True, default=str
            )[:SUMMARY_LIMIT]
        except (TypeError, ValueError):
            return ""
    return ""


def count_calls(lines):
    """Count tool calls in parsed trace lines, per the protocol's rules.

    Event lines (``event`` present) are not calls and do not break the
    adjacency of the call lines around them. Two ``denied:*`` lines for one
    call (the protocol's bounded double-deny case) count once, keyed exactly
    on ``call_id`` (the runtime's tool_use_id) when both lines carry one;
    the ``call_id``-less fallback — identical ``agent``+``tool``+``summary``
    on adjacent denied call lines — is best-effort and documented as such in
    the protocol (an interleaved parallel append can double-count, an
    identical immediate retry can under-count).
    """
    count = 0
    seen_denied_call_ids = set()
    previous_denied_identity = None
    for line in lines:
        if not isinstance(line, dict) or "event" in line:
            continue
        outcome = line.get("outcome")
        if not (isinstance(outcome, str) and outcome.startswith("denied:")):
            previous_denied_identity = None
            count += 1
            continue
        call_id = line.get("call_id")
        if isinstance(call_id, str) and call_id:
            previous_denied_identity = None
            if call_id in seen_denied_call_ids:
                continue
            seen_denied_call_ids.add(call_id)
        else:
            identity = (line.get("agent"), line.get("tool"), line.get("summary"))
            if identity == previous_denied_identity:
                continue
            previous_denied_identity = identity
        count += 1
    return count


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
    """Return (data, corrupt): parsed counters, and whether the on-disk bytes
    were unusable. On corruption the caller re-seeds seq from the trace tail
    rather than silently resetting to 0 (which would duplicate seq values —
    the one thing the protocol promises never happens)."""
    os.lseek(fd, 0, os.SEEK_SET)
    chunks = []
    while True:
        chunk = os.read(fd, 65536)
        if not chunk:
            break
        chunks.append(chunk)
    raw = b"".join(chunks)
    corrupt = False
    try:
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("counters.json is not an object")
    except ValueError:
        # Empty file at first-create is normal, not corruption.
        corrupt = bool(raw.strip())
        data = {}
    else:
        # A non-empty counters file that parses but has no seq is not a state
        # any writer produces — treat as corrupt so seq recovers from the tail
        # rather than silently resetting to 0.
        if bool(raw.strip()) and "seq" not in data:
            corrupt = True
    data.setdefault("protocol", PROTOCOL)
    if not isinstance(data.get("seq"), int) or isinstance(data.get("seq"), bool):
        if data.get("seq") is not None:
            corrupt = True
        data["seq"] = 0
    if not isinstance(data.get("turns"), dict):
        if data.get("turns") is not None:
            corrupt = True
        data["turns"] = {}
    return data, corrupt


def _max_trace_seq(root):
    """Highest seq anywhere in the bounded trace tail (0 if none), plus the
    tail's trustworthiness. Used only on the cold counters-recovery path —
    never on the hot append path. Scans the whole window (not just the last
    line) and takes the max, so a torn trailing line — the natural co-symptom
    of the crash that corrupted the counter — cannot under-recover seq to 0
    and reintroduce duplicates."""
    highest = 0
    lines, trustworthy = tail_trace_status(root, n=None)
    for line in lines:
        seq = line.get("seq")
        if isinstance(seq, int) and not isinstance(seq, bool) and seq > highest:
            highest = seq
    return highest, trustworthy


def _write_counters_fd(fd, data):
    payload = json.dumps(data, separators=(",", ":")).encode("utf-8")
    os.lseek(fd, 0, os.SEEK_SET)
    written = 0
    while written < len(payload):
        n = os.write(fd, payload[written:])
        if n <= 0:
            raise OSError("short write to counters.json")
        written += n
    os.ftruncate(fd, written)  # write-then-truncate: never exposes an empty file
    try:
        os.fsync(fd)  # counter durable before the trace append that depends on it
    except OSError as exc:
        # Fail-open (a hook must not die on fsync), but visible: a lost fsync
        # can leave stale-but-valid counters behind the trace after a crash,
        # which would duplicate seqs with no corruption breadcrumb (FR-004).
        sys.stderr.write(
            "bb-state: counters fsync failed (%s); a crash may now duplicate "
            "seq values\n" % exc
        )


def _recover_seq(root, counters):
    """Re-seed a corrupt counter's seq from the trace tail so the next append
    never duplicates an existing seq. Returns a diagnostic notice."""
    tail_max, tail_trustworthy = _max_trace_seq(root)
    recovered = max(counters["seq"], tail_max)
    counters["seq"] = recovered
    notice = (
        "counters.json was corrupt; recovered seq from trace tail (>=%d). "
        "Surviving per-actor turn counts (if any) were preserved." % recovered
    )
    if not tail_trustworthy:
        notice += (
            " The recovery tail itself contained unparseable lines; the"
            " recovered seq is a best-effort lower bound."
        )
    return notice


def append_trace(root, fields):
    """Append one trace line, assigning the next seq atomically. Returns the line.

    ``fields`` supplies everything but ``protocol`` and ``seq`` (and ``at``,
    filled if absent). The append happens under the counters lock so file
    order == seq order; the appender never reads the trace file (except the
    cold corruption-recovery path, which must restore monotonicity).
    """
    with _locked_counters(root) as fd:
        counters, corrupt = _read_counters_fd(fd)
        if corrupt:
            sys.stderr.write("bb-state: " + _recover_seq(root, counters) + "\n")
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
    lines, _ = tail_trace_status(root, n=n)
    return lines


def tail_trace_status(root, n=AUTH_CONTEXT_WINDOW):
    """Return ``(lines, trustworthy)`` for the bounded trace tail.

    ``trustworthy`` is False when the trace is absent, unreadable, or any
    non-empty line in the considered window failed to parse — a consumer that
    must not be fooled by a torn line (the credential-scan auth window) treats
    an untrustworthy window as uncertain and acts conservatively. ``n=None``
    considers every line in the 64 KiB window (recovery scan)."""
    path = os.path.join(state_dir(root), TRACE_NAME)
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            start = max(0, size - _TAIL_READ_BYTES)
            f.seek(start)
            raw = f.read()
    except OSError:
        return [], False
    texts = raw.decode("utf-8", errors="replace").splitlines()
    if start > 0 and texts:
        # The seek can land mid-line; the leading fragment is a boundary
        # artifact, not corruption — drop it before judging trustworthiness.
        texts = texts[1:]
    window = texts if n is None else texts[-n:]
    lines = []
    trustworthy = True
    for text in window:
        if not text.strip():
            continue
        try:
            parsed = json.loads(text)
        except ValueError:
            trustworthy = False
            continue
        if isinstance(parsed, dict):
            lines.append(parsed)
        else:
            trustworthy = False
    return lines, trustworthy


def get_turns(root, actor):
    """Executed-call count for one actor (checked at PreToolUse).

    A pure read: it never creates ``.bb-session/`` or ``counters.json`` (the
    protocol's "created lazily by the first writer" invariant — a PreToolUse
    cap check in a workspace that never opened a session must leave no trace)."""
    path = os.path.join(state_dir(root), COUNTERS_NAME)
    if not os.path.exists(path):
        return 0
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError as exc:
        # Present-but-unreadable is a diagnosable failure that lifts the cap
        # for this call — the silent sibling of the loud corrupt-parse branch
        # below would hide it (FR-004 visibility).
        sys.stderr.write(
            "bb-state: counters.json unreadable at turn-cap read (%s); "
            "returning 0 turns for this check\n" % exc
        )
        return 0
    try:
        fcntl.flock(fd, fcntl.LOCK_SH)
        counters, corrupt = _read_counters_fd(fd)
    except OSError as exc:
        sys.stderr.write(
            "bb-state: counters.json read failed at turn-cap read (%s); "
            "returning 0 turns for this check\n" % exc
        )
        return 0
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        except OSError:
            pass
    if corrupt:
        # Not silent (FR-004): the next writer recovers seq. Surviving turns
        # are still returned below — the message must not claim otherwise.
        sys.stderr.write(
            "bb-state: counters.json corrupt at turn-cap read; returning "
            "best-effort surviving turn count, seq recovers on next write\n"
        )
    turns = counters["turns"].get(actor)
    if isinstance(turns, bool) or not isinstance(turns, int):
        return 0
    return turns


def increment_turn(root, actor):
    """Consume one turn for ``actor`` (called at PostToolUse only — executed
    calls consume turns; guardrail- or cap-denied calls never do)."""
    with _locked_counters(root) as fd:
        counters, corrupt = _read_counters_fd(fd)
        if corrupt:
            sys.stderr.write("bb-state: " + _recover_seq(root, counters) + "\n")
        current = counters["turns"].get(actor)
        if isinstance(current, bool) or not isinstance(current, int):
            current = 0
        counters["turns"][actor] = current + 1
        _write_counters_fd(fd, counters)
        return counters["turns"][actor]


def notice_once(root, key):
    """True the first time ``key`` is recorded this session; False after.

    Session-scoped once-only diagnostics dedup (e.g. the tripwire's
    one-disabled-notice-per-session). Rides the counters sidecar — the
    protocol's home for "everything that must not require scanning the trace"
    — as the additive ``notices`` object: no consumer-parse change, wrong-typed
    ``notices`` resets rather than flagging corruption (protocol doc).
    """
    with _locked_counters(root) as fd:
        counters, corrupt = _read_counters_fd(fd)
        if corrupt:
            sys.stderr.write("bb-state: " + _recover_seq(root, counters) + "\n")
        notices = counters.get("notices")
        if not isinstance(notices, dict):
            notices = {}
        first = not notices.get(key)
        if first:
            notices[key] = True
        counters["notices"] = notices
        # Persist on a first notice — and also whenever recovery ran, so the
        # "recovered" diagnostic never claims a repair the file doesn't have
        # (an unwritten recovery would re-announce itself on every read).
        if first or corrupt:
            _write_counters_fd(fd, counters)
        return first


def read_roles(root):
    """agents.json role map ``{actor_key: role}``; {} when absent or broken.

    Absent is the normal pre-registration state and stays silent. A file
    that exists but cannot be read/parsed is a distinct, enforcement-relevant
    failure — it silently lifts every turn cap — so it is loud (FR-004): the
    fallback is still {} (fail open, R10), but never without a diagnostic.
    """
    path = os.path.join(state_dir(root), AGENTS_NAME)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        sys.stderr.write(
            "bb-state: agents.json unreadable or malformed (%s); all actors "
            "treated as unregistered — no turn cap applies\n" % exc
        )
        return {}
    roles = data.get("roles") if isinstance(data, dict) else None
    if not isinstance(roles, dict):
        sys.stderr.write(
            "bb-state: agents.json has no usable roles map; all actors "
            "treated as unregistered — no turn cap applies\n"
        )
        return {}
    return roles


def role_for(root, actor):
    """Registered role for an actor, or None (unregistered ⇒ caller applies
    no cap — enforcement without identity would cap the wrong agents)."""
    role = read_roles(root).get(actor)
    return role if isinstance(role, str) else None


def marker_present(root):
    """The session-guard trigger: marker file present ⇒ not cleared (deletion
    *is* the cleared state; no resting "closed" state exists on disk).

    Only a definite absence clears the trigger. An unstattable marker path
    (permissions drift, state dir replaced by a file) cannot rule out an
    uncleared marker, and a backstop must not fail silent in the no-warning
    direction — treat it as present, loudly (Constitution II)."""
    path = os.path.join(state_dir(root), MARKER_NAME)
    try:
        os.stat(path)
    except FileNotFoundError:
        return False
    except OSError as exc:
        sys.stderr.write(
            "bb-state: marker state unreadable (%s); treating the marker as "
            "present — cannot rule out an unpersisted session record\n" % exc
        )
        return True
    return True


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
    or None on failure (caller logs a notice — never a session-ending
    failure). Distinct failure modes stay distinguishable (FR-004): a missing
    source is silent here (the caller's message covers it); an unreadable
    source or a staging-side write failure emits the underlying error, so the
    diagnostic points at the actual cause, not a guessed one."""
    staging = os.path.join(state_dir(root), STAGING_DIR_NAME)
    destination = os.path.join(staging, STAGED_TRANSCRIPT_NAME)
    source = str(transcript_path)
    # Non-blocking readability probe before creating anything: a source we
    # cannot read must not conjure .bb-session/ into a workspace that never
    # had one ("created lazily by the first writer"), and the probe must
    # never hang — O_NONBLOCK means a FIFO (or similar special file) opens
    # immediately instead of blocking the hook until the runtime kills it,
    # which would also swallow every warning computed before this point.
    try:
        fd = os.open(source, os.O_RDONLY | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError as exc:
        sys.stderr.write("bb-state: transcript source unreadable (%s)\n" % exc)
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            sys.stderr.write(
                "bb-state: transcript source is not a regular file (%s); "
                "not staged\n" % source
            )
            return None
        # Copy from the probed fd itself — no re-open, no TOCTOU window
        # between probe and copy.
        with os.fdopen(fd, "rb") as src:
            fd = -1  # ownership transferred to the file object
            os.makedirs(staging, exist_ok=True)
            with open(destination, "wb") as dst:
                shutil.copyfileobj(src, dst)
    except OSError as exc:
        sys.stderr.write("bb-state: transcript staging failed (%s)\n" % exc)
        return None
    finally:
        if fd != -1:
            try:
                os.close(fd)
            except OSError:
                pass
    return destination
