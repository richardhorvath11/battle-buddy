"""US1 retrieval flow (spec AS-1..AS-5, Edge Cases, FR-003, FR-007, SC-003).

Drives ``store_flows.retrieve_candidates`` — the executable form of
``skills/session-store/references/retrieval.md`` — against the seeded mock store,
asserting the three-stage flow, the exclusions, the catalog_resolved downgrade, and
the candidate cap purely on returned artifacts (never prose).

The "incoming" fingerprint for each scenario is computed by the test through the
same helper the rows themselves were fingerprinted with (mirrors
``tests/contract/test_seeds.py``'s pattern) — nothing here hand-writes a hex string.
"""

import pytest

import bb_fingerprint
from conftest import fixture_path
from helpers import store_flows

# ---------------------------------------------------------------------------
# service/alert_type pairs used when tests/fixtures/store/seed-retrieval.json's
# rows were fingerprinted — recomputed here, never hand-copied, so drift in either
# the fixture or the helper trips a test rather than silently mismatching.
# ---------------------------------------------------------------------------

CASE_A_ARGS = ("checkout-api", "High latency")  # exact-match "known issue" row + its
# excluded test/superseded siblings (same fingerprint)
CASE_D_ARGS = ("payments-api", "Elevated errors")  # catalog_resolved: false exact match

# incoming queries with no stored-row fingerprint collision (verified at fixture
# generation time) — used to force the stage 1 miss -> stage 2 path.
AS2_INCOMING_ARGS = ("orders-api-frontend", "Timeout burst spike")
AS5_INCOMING_ARGS = ("cap-query-service", "Cap scenario alert trigger")


def _fp(service, alert_type):
    return bb_fingerprint.fingerprint(service, alert_type)["fingerprint"]


@pytest.fixture
def seeded_mock(mock_mcp):
    mock_mcp.load_seed(fixture_path("store", "seed-retrieval.json"))
    return mock_mcp


def _ids(result):
    return [row["session_id"] for row in result["candidates"]]


# ---------------------------------------------------------------------------
# AS-1: exact fingerprint match -> known_issue
# ---------------------------------------------------------------------------


def test_as1_exact_fingerprint_match_is_known_issue(seeded_mock):
    result = store_flows.retrieve_candidates(
        seeded_mock,
        fingerprint=_fp(*CASE_A_ARGS),
        catalog_resolved=True,
        services=["checkout-api"],
        alert_signature="checkout-api: high latency",
        severity="sev2",
    )
    assert _ids(result) == ["incident-CKO-101-2026-07-10"]
    assert result["classification"] == "known_issue"
    assert result["truncated"] is False
    assert result["total_matched"] == 1


def test_stage2_does_not_run_on_stage1_hit(seeded_mock):
    # incident-CKO-102-... overlaps the query on services (checkout-api) and is
    # not excluded — if stage 2 ran despite the stage-1 hit and unioned its
    # matches, it would appear here (retrieval.md: stage 2 runs only when
    # stage 1 finds nothing).
    result = store_flows.retrieve_candidates(
        seeded_mock,
        fingerprint=_fp(*CASE_A_ARGS),
        catalog_resolved=True,
        services=["checkout-api"],
        alert_signature="checkout-api: high latency",
        severity="sev2",
    )
    assert "incident-CKO-102-2026-07-13" not in _ids(result)
    assert _ids(result) == ["incident-CKO-101-2026-07-10"]


# ---------------------------------------------------------------------------
# AS-2: no exact hit -> exactly the keyword-overlapping rows (one per field)
# ---------------------------------------------------------------------------


def test_as2_no_exact_hit_returns_keyword_overlap_rows(seeded_mock):
    result = store_flows.retrieve_candidates(
        seeded_mock,
        fingerprint=_fp(*AS2_INCOMING_ARGS),  # no stored row shares this fingerprint
        catalog_resolved=True,
        services=["orders-api"],
        alert_signature="orders-api: timeout burst",
        severity="sev1",
    )
    # b1 overlaps via services, b2 via alert_signature, b3 via severity — insertion
    # order preserved, and none of them is a stage-1 exact hit.
    assert _ids(result) == [
        "incident-ORD-301-2026-07-06",
        "incident-UNR-302-2026-07-06",
        "incident-UNR-303-2026-07-06",
    ]
    assert result["classification"] == "candidate"
    assert result["truncated"] is False
    assert result["total_matched"] == 3


# ---------------------------------------------------------------------------
# AS-3: session_type: test / status: superseded never surface — both stage-1
# (exact-match) and stage-2 (keyword-overlap) exclusion paths.
# ---------------------------------------------------------------------------


def test_as3_test_and_superseded_excluded_at_stage1(seeded_mock):
    # test-CKO-101-... and incident-CKO-101-2026-07-12 (superseded) share
    # CASE_A_ARGS's fingerprint and would otherwise exact-match alongside it.
    result = store_flows.retrieve_candidates(
        seeded_mock,
        fingerprint=_fp(*CASE_A_ARGS),
        catalog_resolved=True,
        services=["checkout-api"],
        alert_signature="checkout-api: high latency",
        severity="sev2",
    )
    ids = _ids(result)
    assert "test-CKO-101-2026-07-11" not in ids
    assert "incident-CKO-101-2026-07-12" not in ids
    assert ids == ["incident-CKO-101-2026-07-10"]


def test_as3_test_and_superseded_excluded_at_stage2(seeded_mock):
    # test-ORD-304-... (services overlap) and incident-UNR-305-... (superseded,
    # severity overlap) would otherwise keyword-match this query.
    result = store_flows.retrieve_candidates(
        seeded_mock,
        fingerprint=_fp(*AS2_INCOMING_ARGS),
        catalog_resolved=True,
        services=["orders-api"],
        alert_signature="orders-api: timeout burst",
        severity="sev1",
    )
    ids = _ids(result)
    assert "test-ORD-304-2026-07-06" not in ids
    assert "incident-UNR-305-2026-07-06" not in ids


# ---------------------------------------------------------------------------
# AS-4: either-side catalog_resolved: false downgrades known_issue -> candidate
# ---------------------------------------------------------------------------


def test_as4_downgrade_when_incoming_side_unresolved(seeded_mock):
    # stored row (case a) is catalog_resolved: true; the incoming session's own
    # resolution is what's unresolved here.
    result = store_flows.retrieve_candidates(
        seeded_mock,
        fingerprint=_fp(*CASE_A_ARGS),
        catalog_resolved=False,
        services=["checkout-api"],
        alert_signature="checkout-api: high latency",
        severity="sev2",
    )
    assert _ids(result) == ["incident-CKO-101-2026-07-10"]
    assert result["classification"] == "candidate"


def test_as4_downgrade_when_stored_side_unresolved(seeded_mock):
    # incoming side is resolved; the matched stored row (case d) carries
    # catalog_resolved: false.
    result = store_flows.retrieve_candidates(
        seeded_mock,
        fingerprint=_fp(*CASE_D_ARGS),
        catalog_resolved=True,
        services=["payments-api"],
        alert_signature="payments-api: elevated errors",
        severity="sev3",
    )
    assert _ids(result) == ["incident-PAY-202-2026-07-05"]
    assert result["classification"] == "candidate"


# ---------------------------------------------------------------------------
# AS-5: cap at 20, first-20-in-insertion-order, truncation surfaced
# ---------------------------------------------------------------------------


def test_as5_cap_truncates_to_20_first_in_insertion_order(seeded_mock):
    result = store_flows.retrieve_candidates(
        seeded_mock,
        fingerprint=_fp(*AS5_INCOMING_ARGS),  # no stored row shares this fingerprint
        catalog_resolved=True,
        services=["cap-svc"],
        alert_signature=None,
        severity=None,
    )
    assert result["total_matched"] == 25
    assert result["truncated"] is True
    assert len(result["candidates"]) == 20
    assert _ids(result) == [
        "incident-CAP-{:02d}-2026-07-01".format(i) for i in range(1, 21)
    ]
    assert result["classification"] == "candidate"


# ---------------------------------------------------------------------------
# Edge cases (spec Edge Cases, SC-003): empty / all-excluded store -> zero
# candidates, never an error.
# ---------------------------------------------------------------------------


def test_empty_store_returns_no_candidates_not_error(mock_mcp):
    result = store_flows.retrieve_candidates(
        mock_mcp,
        fingerprint="0" * 16,
        catalog_resolved=True,
        services=["svc"],
        alert_signature="sig",
        severity="sev1",
    )
    assert result == {
        "candidates": [],
        "classification": None,
        "truncated": False,
        "total_matched": 0,
    }


def test_all_excluded_store_returns_no_candidates_not_error(mock_mcp):
    incoming_fp = _fp("iso-svc", "Isolated alert type")
    # both rows would otherwise match at stage 1 (exact fingerprint) AND stage 2
    # (services/alert_signature/severity overlap) — excluded either way.
    mock_mcp.invoke(
        "storage",
        "append_record",
        {
            "record": {
                "session_id": "test-ISO-1-2026-07-01",
                "session_type": "test",
                "status": "open",
                "fingerprint": incoming_fp,
                "catalog_resolved": True,
                "services": ["iso-svc"],
                "alert_signature": "iso sig",
                "severity": "sev1",
            }
        },
    )
    mock_mcp.invoke(
        "storage",
        "append_record",
        {
            "record": {
                "session_id": "incident-ISO-2-2026-07-02",
                "session_type": "incident",
                "status": "superseded",
                "fingerprint": incoming_fp,
                "catalog_resolved": True,
                "services": ["iso-svc"],
                "alert_signature": "iso sig",
                "severity": "sev1",
            }
        },
    )
    result = store_flows.retrieve_candidates(
        mock_mcp,
        fingerprint=incoming_fp,
        catalog_resolved=True,
        services=["iso-svc"],
        alert_signature="iso sig",
        severity="sev1",
    )
    assert result == {
        "candidates": [],
        "classification": None,
        "truncated": False,
        "total_matched": 0,
    }
