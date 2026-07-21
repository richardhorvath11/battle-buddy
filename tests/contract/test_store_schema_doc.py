"""SC-006: mechanical cross-check between schema.md and store_flows constants.

The schema documentation (``skills/session-store/references/schema.md``) is the
human-readable deliverable; ``tests/helpers/store_flows.py`` is its executable form
(research R4/R5). This module parses the doc's column table and asserts it agrees with
the test-side constants — name set, order, and mutation class — in both directions, so
neither can drift from the other silently. It also asserts the FR-002 mutable/close-time
enumeration, the ``bb.schema.v1`` version tag, and the FR-013 stability commitment, plus
unit-style checks on ``parse_source_id`` and ``build_row``.
"""

from pathlib import Path

import pytest

from conftest import REPO_ROOT
from helpers import store_flows

SCHEMA_DOC = REPO_ROOT / "skills" / "session-store" / "references" / "schema.md"

FR_002_MUTABLE_MID_SESSION = {
    "status",
    "session_type",
    "responder",
    "severity",
    "triage_verdict",
    "latest_checkpoint",
}

FR_002_CLOSE_TIME_GROUP = {
    "closed_at",
    "timeline",
    "root_cause",
    "resolution",
    "links",
    "runbook_refs",
    "diary_url",
    "diary_pending",
    "report_url",
    "artifacts_folder_url",
}


# ---------------------------------------------------------------------------
# Doc parser
# ---------------------------------------------------------------------------


def _split_row(line):
    """Split one markdown table row into stripped cells (outer pipes dropped)."""
    cells = [c.strip() for c in line.strip().split("|")]
    if cells and cells[0] == "":
        cells = cells[1:]
    if cells and cells[-1] == "":
        cells = cells[:-1]
    return cells


def _strip_backticks(value):
    return value.strip().strip("`").strip()


def parse_column_table(doc_path):
    """Extract the first markdown table whose header row contains 'Column'.

    Returns an ordered list of ``(name, mutation)`` pairs read from that table's
    Column and Mutation columns, with backticks stripped (SC-006's parse target).
    """
    lines = Path(doc_path).read_text(encoding="utf-8").splitlines()

    header_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("|") and "Column" in stripped:
            header_idx = i
            break
    if header_idx is None:
        raise AssertionError(
            "no markdown table with a 'Column' header found in %s" % doc_path
        )

    header_cells = _split_row(lines[header_idx])
    assert "Column" in header_cells and "Mutation" in header_cells, (
        "schema table header must contain both 'Column' and 'Mutation': %r"
        % header_cells
    )
    name_idx = header_cells.index("Column")
    mutation_idx = header_cells.index("Mutation")

    # header_idx + 1 is the '|---|---|...' separator row; data starts after it.
    rows = []
    for line in lines[header_idx + 2 :]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            break
        cells = _split_row(line)
        if len(cells) <= max(name_idx, mutation_idx):
            break
        name = _strip_backticks(cells[name_idx])
        mutation = _strip_backticks(cells[mutation_idx])
        rows.append((name, mutation))
    return rows


@pytest.fixture(scope="module")
def doc_columns():
    return parse_column_table(SCHEMA_DOC)


# ---------------------------------------------------------------------------
# SC-006: doc <-> store_flows.COLUMNS cross-check
# ---------------------------------------------------------------------------


def test_doc_column_names_match_store_flows_both_directions(doc_columns):
    doc_names = [name for name, _mutation in doc_columns]
    test_names = list(store_flows.COLUMN_NAMES)

    only_in_doc = [n for n in doc_names if n not in test_names]
    only_in_tests = [n for n in test_names if n not in doc_names]
    assert not only_in_doc and not only_in_tests, (
        "schema.md columns and store_flows.COLUMN_NAMES diverge:\n"
        "  only in doc:   %r\n"
        "  only in tests: %r\n"
        "  doc order:     %r\n"
        "  test order:    %r" % (only_in_doc, only_in_tests, doc_names, test_names)
    )
    assert doc_names == test_names, (
        "schema.md column order diverges from store_flows.COLUMN_NAMES:\n"
        "  doc:   %r\n"
        "  tests: %r" % (doc_names, test_names)
    )


def test_doc_mutation_classes_match_store_flows_per_column(doc_columns):
    doc_map = dict(doc_columns)
    test_map = dict(store_flows.COLUMNS)

    all_names = set(doc_map) | set(test_map)
    mismatches = {
        name: (doc_map.get(name), test_map.get(name))
        for name in sorted(all_names)
        if doc_map.get(name) != test_map.get(name)
    }
    assert not mismatches, (
        "doc vs store_flows mutation-class mismatches (doc, test): %r" % mismatches
    )


def test_mutation_classes_are_closed_set(doc_columns):
    for name, mutation in doc_columns:
        assert mutation in ("A", "M", "C"), (
            "column %r has non-A/M/C mutation class %r" % (name, mutation)
        )


# ---------------------------------------------------------------------------
# FR-002: the documented mutable enumeration is exactly this
# ---------------------------------------------------------------------------


def test_store_flows_mutable_mid_session_matches_fr_002():
    assert set(store_flows.MUTABLE_MID_SESSION) == FR_002_MUTABLE_MID_SESSION


def test_store_flows_close_time_group_matches_fr_002():
    assert set(store_flows.CLOSE_TIME_GROUP) == FR_002_CLOSE_TIME_GROUP


def test_store_flows_write_once_is_everything_else():
    enumerated = FR_002_MUTABLE_MID_SESSION | FR_002_CLOSE_TIME_GROUP
    assert set(store_flows.WRITE_ONCE) == set(store_flows.COLUMN_NAMES) - enumerated


def test_doc_mutable_and_close_sets_match_fr_002_directly(doc_columns):
    doc_map = dict(doc_columns)
    doc_m = {name for name, cls in doc_map.items() if cls == "M"}
    doc_c = {name for name, cls in doc_map.items() if cls == "C"}
    doc_a = {name for name, cls in doc_map.items() if cls == "A"}

    assert doc_m == FR_002_MUTABLE_MID_SESSION
    assert doc_c == FR_002_CLOSE_TIME_GROUP
    assert doc_a == set(doc_map) - FR_002_MUTABLE_MID_SESSION - FR_002_CLOSE_TIME_GROUP


# ---------------------------------------------------------------------------
# Version + stability commitment
# ---------------------------------------------------------------------------


def test_schema_version_declared_in_doc():
    text = SCHEMA_DOC.read_text(encoding="utf-8")
    assert "bb.schema.v1" in text
    assert store_flows.SCHEMA_VERSION == "bb.schema.v1"


def test_stability_commitment_present_in_doc():
    text = SCHEMA_DOC.read_text(encoding="utf-8")
    assert "migration-stable" in text


# ---------------------------------------------------------------------------
# parse_source_id
# ---------------------------------------------------------------------------


def test_parse_source_id_hyphenated_source_id():
    assert store_flows.parse_source_id("page-ALERT-123-2026-07-19") == "ALERT-123"


@pytest.mark.parametrize("session_type", store_flows.SESSION_TYPES)
def test_parse_source_id_each_session_type_prefix(session_type):
    session_id = "%s-svc-42-2026-01-05" % session_type
    assert store_flows.parse_source_id(session_id) == "svc-42"


@pytest.mark.parametrize(
    "malformed",
    [
        "",
        None,
        "unknown-svc-2026-07-19",  # not a known session_type prefix
        "page-svc-2026-13-40",  # trailing shape matches but isn't a real date
        "page-svc-notadate",  # no trailing YYYY-MM-DD at all
        "page-2026-07-19",  # nothing between prefix and date (no source id)
    ],
)
def test_parse_source_id_malformed_inputs_raise(malformed):
    with pytest.raises(ValueError):
        store_flows.parse_source_id(malformed)


# ---------------------------------------------------------------------------
# build_row
# ---------------------------------------------------------------------------


def test_build_row_requires_session_id():
    with pytest.raises(ValueError):
        store_flows.build_row(status="open")


def test_build_row_rejects_empty_session_id():
    with pytest.raises(ValueError):
        store_flows.build_row(session_id="", status="open")


def test_build_row_rejects_unknown_field():
    with pytest.raises(ValueError):
        store_flows.build_row(
            session_id="incident-svc-2026-07-19", bogus_field="nope"
        )


def test_build_row_builds_contract_shaped_record():
    row = store_flows.build_row(session_id="incident-svc-2026-07-19", status="open")
    assert row == {"session_id": "incident-svc-2026-07-19", "status": "open"}
