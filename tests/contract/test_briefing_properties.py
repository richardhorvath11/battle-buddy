"""US1 briefing structural properties (spec FR-006, Constitution IV;
contracts/lifecycle-protocol.md "Briefing artifact" -> ``bb.briefing.v1``;
research R16).

Drives ``lifecycle_flows.open_command`` with the ``valid-known-issue.json``
fixture verdict (two candidates whose evidence cites one dashboard URL twice
and a second once — R16's worked 2-vs-1 tie-break case) across
shell-configured / degraded / failing-adapter branches, asserting purely on
the returned ``bb.briefing.v1`` artifact and the shell adapter's/printed
output's own call records (Constitution VIII).
"""

from helpers import lifecycle_fixtures, lifecycle_flows

CATALOG = lifecycle_fixtures.load_catalog()

TOP_CITED = "https://grafana.example.com/d/checkout-latency"  # cited twice
SECOND_CITED = "https://grafana.example.com/d/checkout-errors"  # cited once


def _seed_checkout_alert(mock, alert_id="ALERT-123"):
    mock.alerting.alerts[alert_id] = {
        "alert_id": alert_id,
        "service_hint": "checkout",
        "description": "checkout latency spike",
        "fired_at": "2026-07-21T09:10:00+00:00",
    }


def _open(mock, tmp_path, shell=None, source_id="ALERT-123"):
    _seed_checkout_alert(mock, source_id)
    verdict = lifecycle_fixtures.load_verdict("valid-known-issue")
    return lifecycle_flows.open_command(
        mock,
        tmp_path,
        "page",
        source_id,
        "2026-07-21",
        "2026-07-21T09:14:00+00:00",
        "alice @ 2026-07-21T09:14:00+00:00",
        [verdict],
        CATALOG,
        shell=shell,
    )


# ---------------------------------------------------------------------------
# Every claim carries >=1 {url, excerpt} evidence pair, both non-empty.
# ---------------------------------------------------------------------------


def test_every_claim_has_non_empty_url_excerpt_evidence(mock_mcp, tmp_path):
    out = _open(mock_mcp, tmp_path)
    claims = out["briefing"]["claims"]
    assert claims  # non-vacuous: valid-known-issue.json has 2 candidates w/ evidence
    for claim in claims:
        assert claim["evidence"]
        for entry in claim["evidence"]:
            assert entry["url"].strip()
            assert entry["excerpt"].strip()


# ---------------------------------------------------------------------------
# Top-cited dashboard: R16 tie rule over valid-known-issue.json's 2-vs-1
# citation counts.
# ---------------------------------------------------------------------------


def test_top_cited_dashboard_is_the_2x_cited_url(mock_mcp, tmp_path):
    out = _open(mock_mcp, tmp_path)
    assert out["briefing"]["top_cited_dashboard"] == TOP_CITED


# ---------------------------------------------------------------------------
# Shell configured -> exactly one navigate_pane call to the top-cited URL.
# ---------------------------------------------------------------------------


def test_shell_configured_navigates_once_to_top_cited(mock_mcp, tmp_path):
    shell = lifecycle_fixtures.RecordingShellAdapter()
    out = _open(mock_mcp, tmp_path, shell=shell)

    nav_calls = [c for c in shell.calls if c["method"] == "navigate_pane"]
    assert len(nav_calls) == 1
    assert nav_calls[0]["url"] == TOP_CITED
    assert out["briefing"]["degraded"] is False
    assert out["briefing"]["printed_links"] == []


# ---------------------------------------------------------------------------
# Degraded (shell None) -> same URL in printed_links, zero adapter calls.
# ---------------------------------------------------------------------------


def test_degraded_mode_prints_top_cited_zero_adapter_calls(mock_mcp, tmp_path):
    out = _open(mock_mcp, tmp_path, shell=None)

    assert out["shell_calls"] is None  # no adapter to have called at all
    assert out["briefing"]["degraded"] is True
    assert out["briefing"]["printed_links"] == [TOP_CITED]
    assert TOP_CITED in [e["url"] for e in out["printed"] if e["kind"] == "link"]


# ---------------------------------------------------------------------------
# FailingShellAdapter mid-flow -> flow completes, printed fallback recorded.
# ---------------------------------------------------------------------------


def test_failing_shell_adapter_flow_completes_printed_fallback(mock_mcp, tmp_path):
    shell = lifecycle_fixtures.FailingShellAdapter()
    out = _open(mock_mcp, tmp_path, shell=shell)

    assert out["readback_confirmed"] is True  # the flow completed regardless
    assert out["briefing"]["degraded"] is True
    assert out["briefing"]["printed_links"] == [TOP_CITED]
    link_entries = [e for e in out["printed"] if e["kind"] == "link"]
    assert any(e["url"] == TOP_CITED for e in link_entries)
    message_entries = [e for e in out["printed"] if e["kind"] == "message"]
    assert message_entries  # the open_pane failure was also recorded, printed


# ---------------------------------------------------------------------------
# open_pane recorded with the session-named workspace when adapter present;
# printed message in degraded mode.
# ---------------------------------------------------------------------------


def test_open_pane_session_named_workspace_when_adapter_present(mock_mcp, tmp_path):
    shell = lifecycle_fixtures.RecordingShellAdapter()
    out = _open(mock_mcp, tmp_path, shell=shell)

    open_calls = [c for c in shell.calls if c["method"] == "open_pane"]
    assert len(open_calls) == 1
    assert open_calls[0]["target"] == out["session_id"]
    assert open_calls[0]["workspace"] == out["session_id"]


def test_open_pane_printed_message_in_degraded_mode(mock_mcp, tmp_path):
    out = _open(mock_mcp, tmp_path, shell=None)

    message_entries = [e for e in out["printed"] if e["kind"] == "message"]
    assert any(out["session_id"] in e["text"] for e in message_entries)
