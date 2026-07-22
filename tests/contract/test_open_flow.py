"""US1 open flow (spec FR-001, FR-002, FR-005, AS-3, AS-4; contracts/
lifecycle-protocol.md "Open-flow order", "Marker lifecycle"; research R2,
R15; edge cases "Catalog resolution fails", "Alert fetch fails at open").

Drives ``lifecycle_flows.open_command`` against ``bb-mock-mcp`` with fixture
catalog/verdict data, asserting purely on the mock's write log, the returned
row/outcome, and the local ``marker.json``/``staging/checkpoints.jsonl``
files — never prose (Constitution VIII).
"""

import json

from helpers import lifecycle_fixtures, lifecycle_flows, store_flows

CATALOG = lifecycle_fixtures.load_catalog()

CHECKOUT_ALERT = {
    "alert_id": "ALERT-123",
    "service_hint": "checkout",
    "description": "checkout latency spike",
    "fired_at": "2026-07-21T09:10:00+00:00",
}


def _seed_checkout_alert(mock):
    mock.alerting.alerts[CHECKOUT_ALERT["alert_id"]] = dict(CHECKOUT_ALERT)


def _ops_from(mock, start):
    return [(e["capability"], e["op"]) for e in mock.write_log.entries[start:]]


def _open(mock, tmp_path, verdict_candidates, source_id="ALERT-123", **overrides):
    fields = dict(
        session_type="page",
        source_id=source_id,
        opened_date="2026-07-21",
        started_at="2026-07-21T09:14:00+00:00",
        responder="alice @ 2026-07-21T09:14:00+00:00",
        verdict_candidates=verdict_candidates,
        catalog=CATALOG,
    )
    fields.update(overrides)
    return lifecycle_flows.open_command(
        mock,
        tmp_path,
        fields["session_type"],
        fields["source_id"],
        fields["opened_date"],
        fields["started_at"],
        fields["responder"],
        fields["verdict_candidates"],
        fields["catalog"],
        shell=fields.get("shell"),
        rung_answers=fields.get("rung_answers"),
    )


# ---------------------------------------------------------------------------
# session-ID format + row fields + status open (AS-3)
# ---------------------------------------------------------------------------


def test_session_id_format_row_fields_status_open(mock_mcp, tmp_path):
    _seed_checkout_alert(mock_mcp)
    verdict = lifecycle_fixtures.load_verdict("valid-known-issue")

    out = _open(mock_mcp, tmp_path, [verdict])

    assert out["session_id"] == "page-ALERT-123-2026-07-21"
    row = out["row"]
    assert row["session_id"] == out["session_id"]
    assert row["session_type"] == "page"
    assert row["status"] == "open"
    assert row["catalog_resolved"] is True
    assert row["services"] == ["checkout"]
    assert row["severity"] == "sev3"  # from the verdict, per R2
    assert row["responder"] == "alice @ 2026-07-21T09:14:00+00:00"
    assert row["started_at"] == "2026-07-21T09:14:00+00:00"
    assert set(row) <= set(store_flows.COLUMN_NAMES)


# ---------------------------------------------------------------------------
# marker false -> true only after read-back; write-log ordering
# ---------------------------------------------------------------------------


def test_marker_confirmed_true_only_after_readback_write_ordering(mock_mcp, tmp_path):
    _seed_checkout_alert(mock_mcp)
    verdict = lifecycle_fixtures.load_verdict("valid-known-issue")

    segment_start = len(mock_mcp.write_log.entries)
    out = _open(mock_mcp, tmp_path, [verdict])

    marker = json.loads((tmp_path / "marker.json").read_text(encoding="utf-8"))
    assert marker["open_write_confirmed"] is True
    assert marker["session_id"] == out["session_id"]
    assert out["readback_confirmed"] is True

    ops = _ops_from(mock_mcp, segment_start)
    assert ops.count(("storage", "append_record")) == 1
    assert ("storage", "update_record") not in ops
    # append lands before the flow can possibly confirm the marker — the
    # only mutating write in this segment is the append itself.
    assert ops == [("storage", "append_record")]


# ---------------------------------------------------------------------------
# history line written with seq 0
# ---------------------------------------------------------------------------


def test_history_line_written_with_seq_zero(mock_mcp, tmp_path):
    _seed_checkout_alert(mock_mcp)
    verdict = lifecycle_fixtures.load_verdict("valid-known-issue")

    _open(mock_mcp, tmp_path, [verdict])

    history_path = tmp_path / "staging" / "checkpoints.jsonl"
    lines = [json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 1
    assert lines[0]["seq"] == 0
    assert lines[0]["document"]["session_id"] == verdict["session_id"]


# ---------------------------------------------------------------------------
# Over-guard verdict: put_file BEFORE append_record, cell holds overflow ptr.
# ---------------------------------------------------------------------------


def _huge_verdict():
    return {
        "schema": "bb.verdict.v1",
        "session_id": "page-ALERT-555-2026-07-21",
        "candidates": [
            {
                "statement": "huge candidate for the overflow test",
                "confidence": 0.5,
                "provenance": "fresh",
                "evidence": [
                    {
                        "url": "https://grafana.example.com/d/huge",
                        "excerpt": "x" * 50000,
                    }
                ],
            }
        ],
        "severity": "sev3",
        "no_strong_signal": False,
        "budget_spent": {"turns": 1, "seconds": 1},
    }


def test_over_guard_verdict_overflows_before_append_cell_holds_pointer(mock_mcp, tmp_path):
    verdict = _huge_verdict()
    serialized_len = len(store_flows._serialize_checkpoint(verdict))
    assert serialized_len > mock_mcp.schema_registry.constants["single_field_limit_chars"]

    segment_start = len(mock_mcp.write_log.entries)
    out = _open(mock_mcp, tmp_path, [verdict], source_id="ALERT-555")

    assert out["verdict_overflowed"] is True
    ops = _ops_from(mock_mcp, segment_start)
    assert ops.index(("artifacts", "put_file")) < ops.index(("storage", "append_record"))

    cell = json.loads(out["row"]["triage_verdict"])
    assert cell["seq"] == 0
    assert cell["overflow"] == out["overflow_link"]


# ---------------------------------------------------------------------------
# Validation paths: valid / invalid-then-valid / invalid-twice
# ---------------------------------------------------------------------------


def test_valid_verdict_schema_valid_true(mock_mcp, tmp_path):
    verdict = lifecycle_fixtures.load_verdict("valid-known-issue")
    out = _open(mock_mcp, tmp_path, [verdict])
    assert out["verdict_valid"] is True


def test_invalid_then_valid_reprompt_persists_second_valid_doc(mock_mcp, tmp_path):
    candidates = lifecycle_fixtures.load_verdict_candidates("invalid-then-valid")
    out = _open(mock_mcp, tmp_path, candidates, source_id="ALERT-456")

    assert out["verdict_valid"] is True
    persisted = json.loads(out["row"]["triage_verdict"])
    assert persisted["candidates"][0]["statement"]  # the 2nd (valid) candidate won


def test_invalid_twice_persists_flagged_and_surfaces(mock_mcp, tmp_path):
    candidates = lifecycle_fixtures.load_verdict_candidates("invalid-twice")
    out = _open(mock_mcp, tmp_path, candidates, source_id="ALERT-999")

    assert out["verdict_valid"] is False  # surfaced in the outcome
    persisted = json.loads(out["row"]["triage_verdict"])
    assert persisted["schema_valid"] is False  # persisted flagged, never dropped


# ---------------------------------------------------------------------------
# Alert-fetch not_found -> session still opens, degraded (R15)
# ---------------------------------------------------------------------------


def test_alert_not_found_session_still_opens_degraded(mock_mcp, tmp_path):
    # No alert seeded for this ID -> get_alert returns not_found.
    verdict = lifecycle_fixtures.load_verdict("valid-no-signal")
    out = _open(mock_mcp, tmp_path, [verdict], source_id="ALERT-777")

    assert out["alert_context_available"] is False
    assert out["row"]["alert_signature"] == "ALERT-777"  # degraded to the alert id
    assert out["readback_confirmed"] is True  # the session still opened
    assert "alert context unavailable" in out["briefing"]["notes"]


# ---------------------------------------------------------------------------
# Catalog miss + rung_answers -> catalog_resolved False, briefing downgrade
# ---------------------------------------------------------------------------


def test_catalog_miss_with_rung_answers_downgrades_catalog_resolved(mock_mcp, tmp_path):
    mock_mcp.alerting.alerts["ALERT-888"] = {
        "alert_id": "ALERT-888",
        "service_hint": "unknown-service",
        "description": "mystery alert",
        "fired_at": "2026-07-21T09:00:00+00:00",
    }
    verdict = lifecycle_fixtures.load_verdict("valid-no-signal")

    out = _open(
        mock_mcp,
        tmp_path,
        [verdict],
        source_id="ALERT-888",
        rung_answers={"responder_name": "some-team"},
    )

    assert out["row"]["catalog_resolved"] is False
    assert any("downgrad" in note.lower() for note in out["briefing"]["notes"])
