"""US2 `/incident` flows (spec FR-003, AS-1, AS-2, SC-003; contracts/
lifecycle-protocol.md "Promotion"; research R14).

Two independent behaviors, per spec.md's US2 Independent Test:

1. A fresh `/incident` opens exactly like `/page` (``lifecycle_flows.
   open_command``, already exercised end to end by ``test_open_flow.py``)
   but with ``session_type: incident`` and ``deep_proposed`` true — plus the
   deep-investigation launch confirmation gate (R14): unlaunched without
   confirmation, launched on explicit confirmation, launched unconfirmed
   when ``battleBuddy.autoLaunchDeep`` is configured true.
2. `/incident` invoked inside an already-open page session promotes it in
   place (``lifecycle_flows.promote_session``) — one ``update_record``
   re-tag, no ``append_record``, marker and every other row field untouched.

Asserts purely on the mock's write log, read-back rows, and the local
``marker.json`` file — never prose (Constitution VIII).
"""

import json

from helpers import lifecycle_fixtures, lifecycle_flows, store_flows

CATALOG = lifecycle_fixtures.load_catalog()


def _ops_from(mock, start):
    return [(e["capability"], e["op"]) for e in mock.write_log.entries[start:]]


def _open(mock, tmp_path, verdict_candidates, session_type="incident", source_id="INC-1", **overrides):
    fields = dict(
        session_type=session_type,
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
        auto_launch_deep=fields.get("auto_launch_deep", False),
        deep_confirmed=fields.get("deep_confirmed", False),
    )


# ---------------------------------------------------------------------------
# Fresh /incident: row lands session_type incident, deep_proposed True (AS-1)
# ---------------------------------------------------------------------------


def test_fresh_incident_row_lands_incident_type_deep_proposed(mock_mcp, tmp_path):
    verdict = lifecycle_fixtures.load_verdict("valid-known-issue")

    out = _open(mock_mcp, tmp_path, [verdict], source_id="INC-1")

    assert out["session_id"] == "incident-INC-1-2026-07-21"
    assert out["row"]["session_type"] == "incident"
    assert out["deep_proposed"] is True

    # Read back from the mock, never trust the returned row alone.
    readback = mock_mcp.invoke(
        "storage", "read_records", {"filter": {"session_id": out["session_id"]}}
    )
    assert len(readback["records"]) == 1
    assert readback["records"][0]["session_type"] == "incident"


def test_fresh_page_never_proposes_deep_investigation(mock_mcp, tmp_path):
    # Boundary control (contracts doc "Promotion": "/page sessions never
    # propose deep investigation at all") — even with auto_launch_deep/
    # deep_confirmed set, a page-type open never proposes or launches.
    verdict = lifecycle_fixtures.load_verdict("valid-known-issue")

    out = _open(
        mock_mcp,
        tmp_path,
        [verdict],
        session_type="page",
        source_id="ALERT-1",
        auto_launch_deep=True,
        deep_confirmed=True,
    )

    assert out["deep_proposed"] is False
    assert out["deep_launched"] is False


# ---------------------------------------------------------------------------
# Confirmation gate (R14): no confirmation -> False; explicit confirmation
# -> True; autoLaunchDeep config, unconfirmed -> True.
# ---------------------------------------------------------------------------


def test_deep_launched_false_without_confirmation_or_auto_launch(mock_mcp, tmp_path):
    verdict = lifecycle_fixtures.load_verdict("valid-known-issue")

    out = _open(mock_mcp, tmp_path, [verdict], source_id="INC-2")

    assert out["deep_proposed"] is True
    assert out["deep_launched"] is False


def test_deep_launched_true_with_explicit_confirmation(mock_mcp, tmp_path):
    verdict = lifecycle_fixtures.load_verdict("valid-known-issue")

    out = _open(
        mock_mcp, tmp_path, [verdict], source_id="INC-3", deep_confirmed=True
    )

    assert out["deep_proposed"] is True
    assert out["deep_launched"] is True


def test_deep_launched_true_with_auto_launch_deep_config_unconfirmed(mock_mcp, tmp_path):
    # Stands in for battleBuddy.autoLaunchDeep: true (contracts doc additive
    # config key) — the caller resolves the config key into this bool, same
    # convention preflight's marker_confirm already uses for a responder
    # decision (no flow function reads the config block itself).
    verdict = lifecycle_fixtures.load_verdict("valid-known-issue")

    out = _open(
        mock_mcp,
        tmp_path,
        [verdict],
        source_id="INC-4",
        auto_launch_deep=True,
        deep_confirmed=False,
    )

    assert out["deep_proposed"] is True
    assert out["deep_launched"] is True


# ---------------------------------------------------------------------------
# Promotion: /incident inside an open page session (AS-2, SC-003)
# ---------------------------------------------------------------------------


def _seed_open_page_with_marker(mock, tmp_path):
    """Seeds the promotion-open-page fixture row and writes a matching,
    confirmed local marker naming it — the "already-open page session" the
    spec's promotion Independent Test assumes."""
    lifecycle_fixtures.write_seed(mock, "promotion-open-page")
    seed_row = lifecycle_fixtures.load_seed_fixture("promotion-open-page")[0]

    marker = {
        "protocol": "bb.local.v1",
        "session_id": seed_row["session_id"],
        "source_id": store_flows.parse_source_id(seed_row["session_id"]),
        "opened_at": seed_row["started_at"],
        "open_write_confirmed": True,
    }
    tmp_path.mkdir(parents=True, exist_ok=True)
    marker_path = tmp_path / "marker.json"
    marker_path.write_text(json.dumps(marker, indent=2), encoding="utf-8")
    return seed_row, marker_path


def test_promotion_retags_same_row_one_update_no_append_no_context_loss(mock_mcp, tmp_path):
    seed_row, marker_path = _seed_open_page_with_marker(mock_mcp, tmp_path)
    marker_bytes_before = marker_path.read_bytes()

    segment_start = len(mock_mcp.write_log.entries)
    out = lifecycle_flows.promote_session(mock_mcp, tmp_path)

    # Same session_id (SC-003) — no new row.
    assert out["session_id"] == seed_row["session_id"]
    assert out["retagged"] is True
    assert out["deep_launched"] is True

    # Exactly one update_record for the whole promotion; no append_record
    # (SC-003's "the store shows an update... and no second row").
    ops = _ops_from(mock_mcp, segment_start)
    assert ops == [("storage", "update_record")]
    assert ("storage", "append_record") not in ops

    # The row itself: session_type re-tagged, everything else untouched.
    readback = mock_mcp.invoke(
        "storage", "read_records", {"filter": {"session_id": seed_row["session_id"]}}
    )
    assert len(readback["records"]) == 1
    row = readback["records"][0]
    assert row["session_type"] == "incident"

    row_minus_type = {k: v for k, v in row.items() if k != "session_type"}
    seed_minus_type = {k: v for k, v in seed_row.items() if k != "session_type"}
    assert row_minus_type == seed_minus_type

    # Still exactly one (non-terminal) row for this source ID — the same
    # scan detect_open_session (join detection) uses.
    source_id = store_flows.parse_source_id(seed_row["session_id"])
    matching = store_flows.detect_open_session(mock_mcp, source_id)
    assert len(matching) == 1

    # The marker is untouched — promotion re-tags the row it already names,
    # it never rewrites the marker (contrast a join's marker rewrite, R7).
    assert marker_path.read_bytes() == marker_bytes_before


def test_promotion_with_no_marker_no_writes_retagged_false(mock_mcp, tmp_path):
    write_log_before = list(mock_mcp.write_log.entries)

    out = lifecycle_flows.promote_session(mock_mcp, tmp_path)

    assert out["session_id"] is None
    assert out["retagged"] is False
    assert out["deep_launched"] is False
    assert "reason" in out
    assert mock_mcp.write_log.entries == write_log_before
    assert not (tmp_path / "marker.json").exists()


def test_promotion_update_not_found_surfaced_not_swallowed(mock_mcp, tmp_path):
    # Marker names a session the store doesn't know (stale/mistyped) — the
    # update's not_found error must surface in the outcome, never retried
    # blind and never silently dropped (promote_session's documented
    # posture; SKILL.md's not_found rule scoped to promotion's single-named
    # session).
    marker = {
        "protocol": "bb.local.v1",
        "session_id": "page-GHOST-9-2026-07-20",
        "source_id": "GHOST-9",
        "opened_at": "2026-07-20T02:00:00+00:00",
        "open_write_confirmed": True,
    }
    (tmp_path / "marker.json").write_text(json.dumps(marker), encoding="utf-8")
    write_log_before = list(mock_mcp.write_log.entries)

    out = lifecycle_flows.promote_session(mock_mcp, tmp_path)

    assert out["retagged"] is False
    assert out["update_error"]["code"] == "not_found"
    # The failed update logs nothing — the store shows no promotion write.
    assert mock_mcp.write_log.entries == write_log_before


def test_incident_open_halted_by_join_offer_sets_no_deep_flags(mock_mcp, tmp_path):
    # A join-halted incident open stops before the verdict gate — the deep
    # flags must be unset (None), not a misleading True (R14's flags are
    # computed only after triage validates).
    seed_row = lifecycle_fixtures.load_join_seed_variant("base")
    lifecycle_fixtures.write_seed_rows(mock_mcp, [seed_row])
    write_log_before = list(mock_mcp.write_log.entries)

    out = _open(
        mock_mcp,
        tmp_path,
        lifecycle_fixtures.load_verdict_candidates("valid-known-issue"),
        source_id=store_flows.parse_source_id(seed_row["session_id"]),
        auto_launch_deep=True,
        deep_confirmed=True,
    )

    assert out["join_offer"]
    assert out["deep_proposed"] is None
    assert out["deep_launched"] is None
    # Halted before any store write (FR-004's stop-before-choice).
    assert mock_mcp.write_log.entries == write_log_before
