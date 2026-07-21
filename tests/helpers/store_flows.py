"""The session-store conventions' executable form (research R4).

Dev-only: nothing here ships (FR-012, Constitution I) — this module exists solely so
the documented conventions in ``skills/session-store/`` can be *exercised* by hermetic
contract tests against ``bb-mock-mcp``, rather than asserted on prose. Each flow
function's steps carry a comment citing the skill section they execute; later slice-3
tasks (T008, T012, T017, T021) grow the flow functions themselves (``open_session``,
``retrieve_candidates``, ``write_checkpoint``, ``take_over``, ``close_session``,
``merge_duplicates``) on top of the constants and helpers this base task defines.

Column data mirrors ``skills/session-store/references/schema.md`` exactly; the SC-006
contract test (``tests/contract/test_store_schema_doc.py``) mechanically cross-checks
the two never drift apart.
"""

import json
import re
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Schema version (schema.md "Schema version")
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "bb.schema.v1"

# ---------------------------------------------------------------------------
# Column table (schema.md "Column table") — ordered (name, mutation class) pairs.
# Mutation classes: "A" = write-once at append, "M" = enumerated mid-session
# mutable, "C" = close-time field group (FR-002).
# ---------------------------------------------------------------------------

COLUMNS = (
    ("session_id", "A"),
    ("session_type", "M"),
    ("status", "M"),
    ("fingerprint", "A"),
    ("catalog_resolved", "A"),
    ("alert_signature", "A"),
    ("services", "A"),
    ("severity", "M"),
    ("responder", "M"),
    ("started_at", "A"),
    ("closed_at", "C"),
    ("triage_verdict", "M"),
    ("latest_checkpoint", "M"),
    ("timeline", "C"),
    ("root_cause", "C"),
    ("resolution", "C"),
    ("links", "C"),
    ("runbook_refs", "C"),
    ("diary_url", "C"),
    ("diary_pending", "C"),
    ("report_url", "C"),
    ("artifacts_folder_url", "C"),
)

COLUMN_NAMES = tuple(name for name, _cls in COLUMNS)
WRITE_ONCE = tuple(name for name, cls in COLUMNS if cls == "A")
MUTABLE_MID_SESSION = tuple(name for name, cls in COLUMNS if cls == "M")
CLOSE_TIME_GROUP = tuple(name for name, cls in COLUMNS if cls == "C")

# ---------------------------------------------------------------------------
# Enum constants (schema.md column table's `session_type` / `status` cells)
# ---------------------------------------------------------------------------

STATUS_VALUES = ("open", "closed", "handoff", "superseded")
SESSION_TYPES = ("incident", "page", "test")
NON_TERMINAL_STATUSES = ("open", "handoff")


# ---------------------------------------------------------------------------
# session_id parsing (schema.md "session_id — row key format and source-ID
# parse rule")
# ---------------------------------------------------------------------------

_DATE_SUFFIX_RE = re.compile(r"^(?P<rest>.+)-(?P<date>\d{4}-\d{2}-\d{2})$")


def parse_source_id(session_id):
    """Recover the source ID from a ``session_id`` per schema.md's parse rule.

    ``session_id`` format is ``{type}-{source-id}-{ISO date}`` (D-8). Strips the
    leading ``{type}-`` (``type`` is a closed ``session_type`` enum value) and the
    trailing ``-{YYYY-MM-DD}``; everything between is the source ID verbatim —
    hyphens inside it are legal, e.g. ``page-ALERT-123-2026-07-19`` -> ``ALERT-123``.

    Raises ``ValueError`` on anything that doesn't fit that shape: unknown/missing
    type prefix, missing or malformed trailing date, or an empty source ID.
    """
    if not isinstance(session_id, str) or not session_id:
        raise ValueError("malformed session_id: %r" % (session_id,))

    prefix = None
    for session_type in SESSION_TYPES:
        candidate = session_type + "-"
        if session_id.startswith(candidate):
            prefix = candidate
            break
    if prefix is None:
        raise ValueError(
            "malformed session_id (no known session_type prefix): %r" % (session_id,)
        )

    remainder = session_id[len(prefix):]
    match = _DATE_SUFFIX_RE.match(remainder)
    if match is None:
        raise ValueError(
            "malformed session_id (missing/invalid trailing YYYY-MM-DD date): %r"
            % (session_id,)
        )

    source_id = match.group("rest")
    date_str = match.group("date")

    try:
        date.fromisoformat(date_str)
    except ValueError as exc:
        raise ValueError(
            "malformed session_id (invalid date %r): %r" % (date_str, session_id)
        ) from exc

    if not source_id:
        raise ValueError("malformed session_id (empty source ID): %r" % (session_id,))

    return source_id


# ---------------------------------------------------------------------------
# Row builder (contract-shaped records — schema.md's column set)
# ---------------------------------------------------------------------------


def build_row(**fields):
    """Build a contract-shaped session-row record from keyword fields.

    Requires a non-empty ``session_id``. Rejects (``ValueError``) any field name
    that isn't in ``COLUMN_NAMES`` — no silent typo-tolerant writes. Fills nothing
    in silently: the returned record contains exactly the fields the caller passed.
    """
    if not fields.get("session_id"):
        raise ValueError("build_row requires a non-empty 'session_id'")

    unknown = sorted(set(fields) - set(COLUMN_NAMES))
    if unknown:
        raise ValueError("build_row: unknown column(s) not in schema.md: %r" % unknown)

    return dict(fields)


# ---------------------------------------------------------------------------
# Retrieval (references/retrieval.md, FR-007) — T008 (US1). Remaining flow
# functions land in later slice-3 tasks (T012, T017, T021): open_session,
# write_checkpoint, take_over, close_session, merge_duplicates.
# ---------------------------------------------------------------------------

# retrieval.md "Stage 3 — cap and hand-off": the candidate cap.
CANDIDATE_CAP = 20


def _retrieval_excluded(row):
    """retrieval.md "Stage 0 — exclusions (apply before every stage's match)"."""
    return row.get("session_type") == "test" or row.get("status") == "superseded"


def retrieve_candidates(
    mock, fingerprint, catalog_resolved, services, alert_signature, severity
):
    """Execute retrieval.md's three-stage flow for an incoming session described
    by ``fingerprint``/``catalog_resolved`` (from ``bin/bb-fingerprint`` and the
    service-resolution ladder — the incoming session's row isn't written yet, so
    these are passed in rather than read back) plus ``services``/``alert_signature``/
    ``severity``. Returns retrieval.md's surfacing shape: ``{"candidates": [...],
    "classification": "known_issue" | "candidate" | None, "truncated": bool,
    "total_matched": int}``.
    """
    # retrieval.md "Stage 1 — fingerprint exact match": the one stage allowed a
    # store-side filter; exclusions still apply client-side to the result.
    stage1 = mock.invoke(
        "storage", "read_records", {"filter": {"fingerprint": fingerprint}}
    )
    stage1_rows = [r for r in stage1["records"] if not _retrieval_excluded(r)]

    if stage1_rows:
        # retrieval.md stage 1 "Hit, no downgrade" / "Hit, downgraded": either
        # side of the match — the incoming session or any surviving matched
        # row — carrying catalog_resolved: false downgrades the classification.
        downgraded = (not catalog_resolved) or any(
            not row.get("catalog_resolved", True) for row in stage1_rows
        )
        matched = stage1_rows
        classification = "candidate" if downgraded else "known_issue"
    else:
        # retrieval.md "Stage 2 — keyword overlap (only when stage 1 found
        # nothing)": full read, client-side exclusions, client-side overlap —
        # the contract has no server-side keyword filter.
        all_rows = mock.invoke("storage", "read_records", {})["records"]
        surviving = [r for r in all_rows if not _retrieval_excluded(r)]
        incoming_services = set(services or [])
        matched = [
            row
            for row in surviving
            if (incoming_services & set(row.get("services") or []))
            or (
                alert_signature is not None
                and row.get("alert_signature") == alert_signature
            )
            or (severity is not None and row.get("severity") == severity)
        ]
        classification = "candidate" if matched else None

    # retrieval.md "Stage 3 — cap and hand-off": first CANDIDATE_CAP matches in
    # insertion order; truncation stated, never silent.
    total_matched = len(matched)
    return {
        "candidates": matched[:CANDIDATE_CAP],
        "classification": classification,
        "truncated": total_matched > CANDIDATE_CAP,
        "total_matched": total_matched,
    }


# ---------------------------------------------------------------------------
# Open/close flow (SKILL.md "Open and close flow", FR-008, research R10) —
# T012 (US2). ``state_dir`` is a caller-supplied local state directory (a
# ``pathlib.Path`` or path-like) standing in for local-state protocol v1's
# ``.bb-session/`` — these flows write/read ``marker.json`` directly under it,
# matching the protocol's lazily-created semantics rather than assuming a
# fixed runtime location.
# ---------------------------------------------------------------------------

# SKILL.md "Close, in pinned order" step 2 — local-state protocol v1's
# staging-name -> uploaded-artifact-name mapping, restated here. A local name
# absent from this map uploads verbatim (covers the generated report, which
# has no local-staged counterpart).
_UPLOAD_NAME_MAP = {
    "staging/transcript.md": "transcript.md",
    "trace.jsonl": "tool-trace.jsonl",
    "staging/checkpoints.jsonl": "checkpoints.jsonl",
}

_NO_OVERRIDE = object()


def _safe_parse_source_id(session_id):
    """``parse_source_id`` for rows that might not fit the shape (relocate
    scan candidates) — a non-matching row is simply not a relocate hit."""
    try:
        return parse_source_id(session_id)
    except ValueError:
        return None


def open_session(mock, state_dir, session_type, source_id, opened_date, **row_fields):
    """SKILL.md "Open and close flow" -> "Open — append, then read back".

    Computes ``session_id`` per schema.md's row-key format, ``append_record``s
    the row (``status`` defaults to ``"open"``), reads it back via
    ``read_records`` filtered on ``session_id``, and writes ``marker.json``
    (local-state protocol v1 shape) under ``state_dir`` with
    ``open_write_confirmed`` set **only** on a confirmed single-row match.

    ``row_fields`` may include an explicit ``session_id`` override (e.g.
    ``""``) — used by tests to force the real ``append_record`` rejection
    (empty/missing ``session_id`` -> ``invalid_input``) for the open-twin
    failure path (FR-008; no monkeypatching — the mock's own check rejects
    it). When absent, ``session_id`` is computed normally from
    ``session_type``/``source_id``/``opened_date``.

    Returns an outcome dict: ``{"session_id", "row", "append_result",
    "readback_confirmed", "marker", "marker_path"}``.
    """
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    # Local-state protocol v1's staging/ area — lazily created here so a test
    # or a later step can stage files under it without a separate mkdir.
    (state_dir / "staging").mkdir(parents=True, exist_ok=True)

    session_id = row_fields.pop("session_id", _NO_OVERRIDE)
    if session_id is _NO_OVERRIDE:
        session_id = "{}-{}-{}".format(session_type, source_id, opened_date)

    row = {"session_id": session_id, "session_type": session_type}
    row["status"] = row_fields.pop("status", "open")
    row.update(row_fields)
    unknown = sorted(set(row) - set(COLUMN_NAMES))
    if unknown:
        raise ValueError("open_session: unknown column(s) not in schema.md: %r" % unknown)

    # SKILL.md open step 1: append_record the row.
    append_result = mock.invoke("storage", "append_record", {"record": row})

    # SKILL.md open step 2: read the row back; only a confirmed single-row
    # match (by session_id) sets open_write_confirmed.
    readback = mock.invoke(
        "storage", "read_records", {"filter": {"session_id": session_id}}
    )
    records = readback["records"]
    confirmed = len(records) == 1 and records[0].get("session_id") == session_id

    marker = {
        "protocol": "bb.local.v1",
        "session_id": session_id,
        "source_id": source_id,
        "opened_at": row.get("started_at"),
        "open_write_confirmed": confirmed,
    }
    marker_path = state_dir / "marker.json"
    marker_path.write_text(json.dumps(marker, indent=2), encoding="utf-8")

    return {
        "session_id": session_id,
        "row": row,
        "append_result": append_result,
        "readback_confirmed": confirmed,
        "marker": marker,
        "marker_path": marker_path,
    }


def close_session(
    mock,
    state_dir,
    session_id,
    close_fields,
    diary_content,
    staged_artifacts,
    expected_session_id=None,
):
    """SKILL.md "Open and close flow" -> "Close — pinned write order".

    Executes the close flow's pinned writes in order — diary ``append_entry``
    (1), one ``put_file`` per staged artifact (2), the close-time
    ``update_record`` re-asserting the open-time row's write-once fields (3),
    and a ``read_records`` read-back that gates ``marker.json`` deletion (4)
    — tolerating per-step failures exactly as SKILL.md documents: a diary
    failure sets ``diary_pending: true`` and the flow continues; a per-file
    artifact failure omits that artifact's link and continues; the row write
    itself is never blocked by either. Mid-session writes are not this
    function's concern — callers may perform them before calling this (see
    SKILL.md's ordering-claim scope note).

    ``close_fields``: close-time field-group overrides (e.g. ``closed_at``,
    ``timeline``, ``root_cause``, ``resolution``, ``runbook_refs``,
    ``report_url``, ``links``). ``diary_url``/``diary_pending``/
    ``artifacts_folder_url`` are computed by this flow, not passed in; any
    ``links`` entries supplied here are preserved, with successfully uploaded
    artifacts' links appended after them.

    ``staged_artifacts``: an ordered ``{local_name: content}`` map. Each
    ``local_name`` is looked up in the local-state-protocol-v1 -> uploaded
    name mapping (SKILL.md step 2); an unmapped name uploads verbatim. If the
    resolved uploaded name is empty, this flow does **not** fabricate a
    folder-qualified name to paper over it — it calls ``put_file`` with that
    empty name so the real contract's non-empty check rejects it (the
    artifact-failure edge case; no monkeypatching).

    ``expected_session_id``: the ``session_id`` the step-4 read-back must
    match to clear the marker; defaults to ``session_id``. Exists so a test
    can simulate a corrupted/stale local marker recording the wrong
    ``session_id`` (spec US2 AS-4) without touching the mock's internals —
    every write in this flow still targets the real ``session_id``; only the
    read-back confirmation is checked against a possibly-different
    expectation (the contract's ``read_records`` is a strict equality filter,
    so a returned row's ``session_id`` can never itself differ from the
    filter used to find it — this parameter is the honest, contract-valid way
    to exercise the "confirmation fails" branch).

    Returns an outcome dict: ``{"diary_link", "diary_pending", "uploaded":
    {local_name: {"uploaded_name", "link"}}, "omitted_artifacts":
    [local_name, ...], "update_result", "not_found_reconciliation",
    "readback_confirmed", "marker_cleared"}``.
    """
    state_dir = Path(state_dir)
    if expected_session_id is None:
        expected_session_id = session_id

    # Prep read (not a close-flow write — outside the ordering claim): the
    # open-time row's write-once fields, re-asserted verbatim at close
    # (SKILL.md step 3; schema.md mutation policy).
    existing = mock.invoke(
        "storage", "read_records", {"filter": {"session_id": session_id}}
    )
    open_row = existing["records"][0] if existing["records"] else {}
    write_once_reassert = {name: open_row[name] for name in WRITE_ONCE if name in open_row}

    # Step 1 (SKILL.md close step 1 — diary): append_entry; tolerate failure
    # by continuing with diary_pending: true (R10 — the flag IS the queue).
    diary_result = mock.invoke("diary", "append_entry", {"content": diary_content})
    if "error" in diary_result:
        diary_link = None
        diary_pending = True
    else:
        diary_link = diary_result["link"]
        diary_pending = False

    # Step 2 (SKILL.md close step 2 — artifacts): one put_file per staged
    # file, folder-qualified under battle-buddy/<session_id>/<uploaded-name>;
    # per-file failures are tolerated — omit the link, surface the gap, never
    # block the row write.
    uploaded = {}
    omitted_artifacts = []
    artifact_links = []
    for local_name, content in staged_artifacts.items():
        uploaded_name = _UPLOAD_NAME_MAP.get(local_name, local_name)
        full_name = (
            "battle-buddy/{}/{}".format(session_id, uploaded_name)
            if uploaded_name
            else uploaded_name
        )
        result = mock.invoke("artifacts", "put_file", {"name": full_name, "content": content})
        if "error" in result:
            omitted_artifacts.append(local_name)
        else:
            uploaded[local_name] = {"uploaded_name": uploaded_name, "link": result["link"]}
            artifact_links.append({"url": result["link"], "excerpt": uploaded_name})

    # Step 3 (SKILL.md close step 3 — row update): close-time field group +
    # the re-asserted write-once values, plus the diary/artifact fields this
    # flow computed above.
    fields = dict(close_fields)
    unknown = sorted(set(fields) - set(COLUMN_NAMES))
    if unknown:
        raise ValueError("close_session: unknown close_fields column(s): %r" % unknown)
    fields["diary_pending"] = diary_pending
    if diary_link is not None:
        fields["diary_url"] = diary_link
    if uploaded:
        fields["artifacts_folder_url"] = "battle-buddy/{}/".format(session_id)
    prior_links = fields.get("links") or []
    fields["links"] = list(prior_links) + artifact_links

    fields.update(write_once_reassert)

    update_result = mock.invoke(
        "storage", "update_record", {"session_id": session_id, "fields": fields}
    )

    not_found_reconciliation = None
    if "error" in update_result and update_result["error"].get("code") == "not_found":
        # SKILL.md "update_record returns not_found": never retry blind;
        # re-locate by source ID + non-terminal status and reconcile.
        source_id = parse_source_id(session_id)
        all_rows = mock.invoke("storage", "read_records", {})["records"]
        relocated = [
            row
            for row in all_rows
            if row.get("status") in NON_TERMINAL_STATUSES
            and _safe_parse_source_id(row.get("session_id")) == source_id
        ]
        not_found_reconciliation = {"source_id": source_id, "relocated": relocated}

    # Step 4 (SKILL.md close step 4 — read-back): only a confirmed
    # session_id match clears the local marker (deletion-is-cleared,
    # protocol v1).
    readback = mock.invoke(
        "storage", "read_records", {"filter": {"session_id": session_id}}
    )
    readback_records = readback["records"]
    confirmed = (
        len(readback_records) == 1
        and readback_records[0].get("session_id") == expected_session_id
    )

    marker_path = state_dir / "marker.json"
    marker_cleared = False
    if confirmed:
        if marker_path.exists():
            marker_path.unlink()
        marker_cleared = True

    return {
        "diary_link": diary_link,
        "diary_pending": diary_pending,
        "uploaded": uploaded,
        "omitted_artifacts": omitted_artifacts,
        "update_result": update_result,
        "not_found_reconciliation": not_found_reconciliation,
        "readback_confirmed": confirmed,
        "marker_cleared": marker_cleared,
    }
