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


# --- every seed-validation branch fails loudly, naming the offending entry ---

_ALERT = {
    "alert_id": "al-1",
    "service_hint": "checkout",
    "description": "d",
    "fired_at": "2026-07-01T00:00:00+00:00",
}

BAD_SEEDS = [
    ("top-level-non-map", ["not", "a", "map"], "top level must be a map"),
    ("unknown-top-level-key", {"artefacts": []}, "unknown top-level key 'artefacts'"),
    ("records-non-list", {"records": {}}, "records: must be a list"),
    ("record-non-map", {"records": ["x"]}, "records[0]"),
    ("record-missing-session-id", {"records": [{"note": "n"}]}, "session_id"),
    (
        "record-oversized-field",
        {"records": [{"session_id": "s1", "blob": "x" * 45001}]},
        "D-3",
    ),
    ("artifact-non-map", {"artifacts": ["x"]}, "artifacts[0]"),
    ("artifact-empty-name", {"artifacts": [{"name": "", "content": "c"}]}, "name"),
    ("artifact-missing-content", {"artifacts": [{"name": "f"}]}, "content"),
    ("diary-non-string-entry", {"diary": [1]}, "diary[0]"),
    ("alerts-non-map", {"alerts": []}, "must be a map"),
    ("alerts-unknown-key", {"alerts": {"alarm": []}}, "unknown key 'alarm'"),
    (
        "alert-missing-required-field",
        {"alerts": {"alerts": [{"alert_id": "a1"}]}},
        "missing required field",
    ),
    (
        "alert-empty-id",
        {"alerts": {"alerts": [dict(_ALERT, alert_id="")]}},
        "alert_id",
    ),
    (
        "alert-duplicate-id",
        {"alerts": {"alerts": [dict(_ALERT), dict(_ALERT)]}},
        "duplicate alert_id",
    ),
]


def _assert_untouched(mock):
    assert mock.records.records == []
    assert mock.artifacts.files == {}
    assert mock.diary.entries == []
    assert mock.alerting.alerts == {}
    assert mock.alerting.history == []


@pytest.mark.parametrize(
    "seed,substring", [(s, m) for _, s, m in BAD_SEEDS], ids=[i for i, _, _ in BAD_SEEDS]
)
def test_bad_seed_fails_naming_the_entry(mock_mcp, tmp_path, seed, substring):
    import json

    from bb_mock_mcp import SeedError

    path = tmp_path / "bad-seed.json"
    path.write_text(json.dumps(seed))
    with pytest.raises(SeedError) as excinfo:
        mock_mcp.load_seed(path)
    assert substring in str(excinfo.value)
    _assert_untouched(mock_mcp)


def test_unparseable_seed_file_fails_loudly(mock_mcp, tmp_path):
    from bb_mock_mcp import SeedError

    path = tmp_path / "not-json.json"
    path.write_text("{not json")
    with pytest.raises(SeedError) as excinfo:
        mock_mcp.load_seed(path)
    assert "not valid JSON" in str(excinfo.value)
    _assert_untouched(mock_mcp)


def test_apply_failure_rolls_back_all_state(mock_mcp, tmp_path, monkeypatch):
    """All-or-nothing must hold mechanically even if a store check tightens
    without the seed validator mirroring it (simulated drift)."""
    import json

    from bb_mock_mcp import ContractViolation, SeedError

    def drifted_store_check(name, content):
        raise ContractViolation("invalid_input", "simulated drifted store check")

    monkeypatch.setattr(mock_mcp.artifacts, "put_file", drifted_store_check)
    path = tmp_path / "seed.json"
    path.write_text(
        json.dumps(
            {
                "records": [{"session_id": "s1"}],
                "artifacts": [{"name": "f", "content": "c"}],
            }
        )
    )
    with pytest.raises(SeedError) as excinfo:
        mock_mcp.load_seed(path)
    assert "no state applied" in str(excinfo.value)
    _assert_untouched(mock_mcp)
