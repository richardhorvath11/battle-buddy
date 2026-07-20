"""Conformance: alerting ops — seeded get_alert, list_alert_history filters
newest-first, not_found (contracts/operations.md; SC-003).

Alerting is seed-only (no mutating contract ops), so tests arrange state via
the direct state-access surface (FR-006).
"""


def seed_alerting(mock):
    mock.alerting.alerts["al-1"] = {
        "alert_id": "al-1",
        "service_hint": "checkout",
        "description": "p99 latency breach",
        "fired_at": "2026-07-01T10:00:00+00:00",
    }
    # history is stored oldest -> newest; listed newest first
    for i, service in enumerate(["checkout", "checkout", "search"], start=1):
        mock.alerting.history.append(
            {
                "alert_id": "al-1" if service == "checkout" else "al-2",
                "service_hint": service,
                "description": "firing #{}".format(i),
                "fired_at": "2026-07-01T0{}:00:00+00:00".format(i),
            }
        )


def test_get_alert_by_id(mock_mcp):
    seed_alerting(mock_mcp)
    out = mock_mcp.invoke("alerting", "get_alert", {"alert_id": "al-1"})
    alert = out["alert"]
    assert alert["alert_id"] == "al-1"
    for required in ("alert_id", "service_hint", "description", "fired_at"):
        assert required in alert


def test_get_alert_unknown_id_is_not_found(mock_mcp):
    result = mock_mcp.invoke("alerting", "get_alert", {"alert_id": "nope"})
    assert result["error"]["op"] == "alerting.get_alert"
    assert result["error"]["code"] == "not_found"
    assert "nope" in result["error"]["message"]


def test_list_alert_history_newest_first(mock_mcp):
    seed_alerting(mock_mcp)
    out = mock_mcp.invoke("alerting", "list_alert_history", {"filter": {}})
    assert [a["description"] for a in out["alerts"]] == ["firing #3", "firing #2", "firing #1"]


def test_list_alert_history_filters_by_alert_id(mock_mcp):
    seed_alerting(mock_mcp)
    out = mock_mcp.invoke("alerting", "list_alert_history", {"filter": {"alert_id": "al-1"}})
    assert [a["description"] for a in out["alerts"]] == ["firing #2", "firing #1"]


def test_list_alert_history_filters_by_service_hint(mock_mcp):
    seed_alerting(mock_mcp)
    out = mock_mcp.invoke("alerting", "list_alert_history", {"filter": {"service_hint": "search"}})
    assert [a["description"] for a in out["alerts"]] == ["firing #3"]


def test_list_alert_history_non_map_filter_rejected(mock_mcp):
    result = mock_mcp.invoke("alerting", "list_alert_history", {"filter": "checkout"})
    assert result["error"]["code"] == "invalid_input"
    assert "filter" in result["error"]["message"]
