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

import re
from datetime import date

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
