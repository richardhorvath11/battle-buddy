"""Seed-fixture loading (spec Story 3 AS-1/AS-2, FR-008).

The synthetic incident seed loads exactly; the corrupted seed fails naming the
offending entry with nothing partially applied; seeds bypass the write log.
"""

import pytest

from conftest import fixture_path, load_fixture
from helpers.assertions import assert_seeded_state, assert_write_sequence


def test_synthetic_incident_seed_loads_exactly(mock_mcp):
    seed = load_fixture("seeds", "synthetic-incident.json")
    mock_mcp.load_seed(fixture_path("seeds", "synthetic-incident.json"))
    assert_seeded_state(mock_mcp, seed)
    assert mock_mcp.write_log.entries == []  # seeds bypass the write log


def test_seeded_state_supports_fingerprint_recall(mock_mcp):
    """The seed's promise: the live alert's fingerprint matches exactly one
    prior session record (the recall path later slices test against)."""
    mock_mcp.load_seed(fixture_path("seeds", "synthetic-incident.json"))
    alert = mock_mcp.invoke("alerting", "get_alert", {"alert_id": "al-checkout-latency-p99"})["alert"]
    matches = mock_mcp.invoke(
        "storage", "read_records", {"filter": {"fingerprint": alert["fingerprint"]}}
    )["records"]
    assert [r["session_id"] for r in matches] == ["bb-2026-07-01-checkout-latency"]


def test_corrupted_seed_fails_naming_the_entry(mock_mcp):
    from bb_mock_mcp import SeedError

    with pytest.raises(SeedError) as excinfo:
        mock_mcp.load_seed(fixture_path("seeds", "corrupted.json"))
    assert "records[1]" in str(excinfo.value)
    assert "session_id" in str(excinfo.value)
    # all-or-nothing: nothing partially loaded
    assert mock_mcp.records.records == []
    assert mock_mcp.artifacts.files == {}
    assert mock_mcp.diary.entries == []
    assert mock_mcp.alerting.alerts == {}


def test_scenario_writes_after_seed_are_the_only_logged_ops(mock_mcp):
    mock_mcp.load_seed(fixture_path("seeds", "synthetic-incident.json"))
    mock_mcp.invoke("diary", "append_entry", {"content": "recalled prior incident"})
    mock_mcp.invoke("storage", "append_record", {"record": {"session_id": "s-new"}})
    assert_write_sequence(
        mock_mcp,
        [("diary", "append_entry"), ("storage", "append_record")],
    )
