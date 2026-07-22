"""US3 join-vs-separate (spec FR-002, FR-004, AS-1, AS-2, AS-3, SC-004;
contracts/lifecycle-protocol.md "Join-vs-separate (FR-004)", "Marker
lifecycle" state 3; research R7, R1).

Seeds ``join-open-yesterday.json``'s "base"/"overflow_variant" row (same
source ID, dated yesterday) and drives ``lifecycle_flows.open_command``,
``join_session``, and ``open_separate`` against ``bb-mock-mcp``, asserting
purely on the mock's write log, the store's row state, and the local
``marker.json`` file — never prose (Constitution VIII).
"""

import json

from helpers import lifecycle_fixtures, lifecycle_flows, store_flows

CATALOG = lifecycle_fixtures.load_catalog()

# The opening responder's own token throughout — matches the "<me> @ <ts>"
# convention every other lifecycle test/flow uses for the responder cell.
BOB = "bob @ 2026-07-21T09:20:00+00:00"
CAROL = "carol @ 2026-07-21T09:20:00+00:00"


def _ops_from(mock, start):
    return [(e["capability"], e["op"]) for e in mock.write_log.entries[start:]]


def _open_page_today(mock, tmp_path, source_id, responder=BOB, **overrides):
    """Drives ``open_command`` with the same shape ``test_open_flow.py``/
    ``test_incident_flows.py`` use, opened today (2026-07-21) — the seed
    row's own ``session_id`` is dated yesterday (2026-07-20), so a hit here
    can only ever be by parsed source ID + non-terminal status, never a
    recomputed session_id (spec US3's own point)."""
    fields = dict(
        session_type="page",
        opened_date="2026-07-21",
        started_at="2026-07-21T09:20:00+00:00",
        verdict_candidates=[lifecycle_fixtures.load_verdict("valid-known-issue")],
    )
    fields.update(overrides)
    return lifecycle_flows.open_command(
        mock,
        tmp_path,
        fields["session_type"],
        source_id,
        fields["opened_date"],
        fields["started_at"],
        responder,
        fields["verdict_candidates"],
        CATALOG,
        shell=fields.get("shell"),
        rung_answers=fields.get("rung_answers"),
    )


# ---------------------------------------------------------------------------
# Join offer surfaced by parsed source ID + non-terminal status, never a
# recomputed session_id; zero mutating store ops before the choice
# (AS-1, SC-004).
# ---------------------------------------------------------------------------


def test_join_offer_surfaced_by_parsed_source_id_zero_writes_before_choice(
    mock_mcp, tmp_path
):
    seed_row = lifecycle_fixtures.load_join_seed_variant("base")
    lifecycle_fixtures.write_seed_rows(mock_mcp, [seed_row])
    source_id = store_flows.parse_source_id(seed_row["session_id"])

    write_log_before = list(mock_mcp.write_log.entries)
    out = _open_page_today(mock_mcp, tmp_path, source_id)

    assert out["proceed"] is False
    offer_ids = [row["session_id"] for row in out["join_offer"]]
    assert seed_row["session_id"] in offer_ids
    # The seed's own session_id embeds yesterday's date; this open computed
    # today's — the match can only be by parsed source ID + non-terminal
    # status, never by a recomputed/matching session_id.
    assert out["session_id"] == "page-{}-2026-07-21".format(source_id)
    assert out["session_id"] != seed_row["session_id"]

    # SC-004 / AS-1: zero mutating store ops before the explicit choice — the
    # halt writes only the local marker.json (local state, not a store op);
    # the mock's write log is untouched by everything up to and including it.
    assert mock_mcp.write_log.entries == write_log_before


def test_handoff_status_row_also_joinable(mock_mcp, tmp_path):
    # A non-terminal status other than "open" is joinable too — detection is
    # status-class based (NON_TERMINAL_STATUSES), never "open" specifically.
    seed_row = dict(lifecycle_fixtures.load_join_seed_variant("base"))
    seed_row["status"] = "handoff"
    lifecycle_fixtures.write_seed_rows(mock_mcp, [seed_row])
    source_id = store_flows.parse_source_id(seed_row["session_id"])

    out = _open_page_today(mock_mcp, tmp_path, source_id)

    assert out["proceed"] is False
    offer_ids = [row["session_id"] for row in out["join_offer"]]
    assert seed_row["session_id"] in offer_ids


# ---------------------------------------------------------------------------
# Join: rehydrate from latest_checkpoint (+ overflow variant), take-over
# writes responder, marker rewritten to the joined identity, confirmed only
# by the take-over read-back (AS-2, R7, FR-002).
# ---------------------------------------------------------------------------


def test_join_rehydrates_takes_over_rewrites_marker_confirmed_by_readback(
    mock_mcp, tmp_path
):
    seed_row = lifecycle_fixtures.load_join_seed_variant("base")
    lifecycle_fixtures.write_seed_rows(mock_mcp, [seed_row])
    source_id = store_flows.parse_source_id(seed_row["session_id"])

    halted = _open_page_today(mock_mcp, tmp_path, source_id)
    assert halted["proceed"] is False
    join_row = halted["join_offer"][0]
    assert join_row["session_id"] == seed_row["session_id"]

    segment_start = len(mock_mcp.write_log.entries)
    out = lifecycle_flows.join_session(mock_mcp, tmp_path, join_row, BOB)

    # Rehydration equals the seed's own latest_checkpoint document exactly.
    assert out["rehydrated_checkpoint"] == json.loads(seed_row["latest_checkpoint"])

    # Take-over: exactly one update_record (SC-004 "join writes exactly the
    # ownership take-over") — nothing else mutates.
    ops = _ops_from(mock_mcp, segment_start)
    assert ops == [("storage", "update_record")]

    # The row itself now names the joining responder.
    readback = mock_mcp.invoke(
        "storage", "read_records", {"filter": {"session_id": seed_row["session_id"]}}
    )["records"]
    assert len(readback) == 1
    assert readback[0]["responder"] == BOB
    assert out["takeover_result"]["previous_responder"] == seed_row["responder"]
    assert out["takeover_result"]["new_responder"] == BOB

    # Marker rewritten wholesale to the JOINED identity — never the halted
    # open's own (not-yet-opened) session — and confirmed only because the
    # take-over read-back matched the new responder.
    marker = json.loads((tmp_path / "marker.json").read_text(encoding="utf-8"))
    assert marker["protocol"] == "bb.local.v1"
    assert marker["session_id"] == seed_row["session_id"]
    assert marker["source_id"] == source_id
    assert marker["opened_at"] == seed_row["started_at"]
    assert marker["open_write_confirmed"] is True

    assert out["marker_rewritten"] is True
    assert out["marker_confirmed"] is True
    assert out["session_id"] == seed_row["session_id"]


def test_join_overflow_variant_rehydrates_full_document_via_artifact_store(
    mock_mcp, tmp_path
):
    fixture = lifecycle_fixtures.load_seed_fixture("join-open-yesterday")
    seed_row = fixture["overflow_variant"]

    # Seed the overflow artifact BEFORE the row so read_latest_checkpoint's
    # overflow-follow path actually resolves it (lifecycle_fixtures'
    # documented ordering requirement).
    lifecycle_fixtures.seed_join_overflow_artifact(mock_mcp)
    lifecycle_fixtures.write_seed_rows(mock_mcp, [seed_row])
    source_id = store_flows.parse_source_id(seed_row["session_id"])

    halted = _open_page_today(mock_mcp, tmp_path, source_id)
    join_row = halted["join_offer"][0]

    out = lifecycle_flows.join_session(mock_mcp, tmp_path, join_row, BOB)

    # Rehydration resolves the overflow pointer to the FULL document fetched
    # through the artifact store — never the bare {"overflow", "seq"} cell.
    expected = json.loads(fixture["overflow_artifact"]["content"])
    assert out["rehydrated_checkpoint"] == expected
    assert "overflow" not in out["rehydrated_checkpoint"]

    assert out["marker_confirmed"] is True
    marker = json.loads((tmp_path / "marker.json").read_text(encoding="utf-8"))
    assert marker["session_id"] == seed_row["session_id"]


# ---------------------------------------------------------------------------
# Separate: exactly one new append_record; new row's session_id carries
# today's date; marker tracks the new session only (AS-3).
# ---------------------------------------------------------------------------


def test_open_separate_appends_one_new_row_marker_tracks_new_session_only(
    mock_mcp, tmp_path
):
    seed_row = lifecycle_fixtures.load_join_seed_variant("base")
    lifecycle_fixtures.write_seed_rows(mock_mcp, [seed_row])
    source_id = store_flows.parse_source_id(seed_row["session_id"])

    segment_start = len(mock_mcp.write_log.entries)
    out = lifecycle_flows.open_separate(
        mock_mcp,
        tmp_path,
        "page",
        source_id,
        "2026-07-21",
        "2026-07-21T09:20:00+00:00",
        CAROL,
        [lifecycle_fixtures.load_verdict("valid-known-issue")],
        CATALOG,
    )

    assert out["proceed"] is True
    assert out["session_id"] == "page-{}-2026-07-21".format(source_id)
    assert out["session_id"] != seed_row["session_id"]
    # The candidate was seen, not hidden — merely bypassed by explicit choice.
    assert [r["session_id"] for r in out["join_offer"]] == [seed_row["session_id"]]

    # Exactly one new append_record; no update_record (never a join/take-over).
    ops = _ops_from(mock_mcp, segment_start)
    assert ops.count(("storage", "append_record")) == 1
    assert ("storage", "update_record") not in ops

    # The marker tracks the NEW session only.
    marker = json.loads((tmp_path / "marker.json").read_text(encoding="utf-8"))
    assert marker["session_id"] == out["session_id"]
    assert marker["session_id"] != seed_row["session_id"]
    assert marker["open_write_confirmed"] is True

    # Both rows now coexist, non-terminal, sharing the source ID — the old
    # session was never silently duplicated over or dropped.
    all_rows = mock_mcp.invoke("storage", "read_records", {})["records"]
    same_source_open = [
        r
        for r in all_rows
        if store_flows.parse_source_id(r["session_id"]) == source_id
        and r["status"] in store_flows.NON_TERMINAL_STATUSES
    ]
    assert len(same_source_open) == 2
    assert seed_row["session_id"] in [r["session_id"] for r in same_source_open]
    assert out["session_id"] in [r["session_id"] for r in same_source_open]

    # The old row is completely untouched by the separate open.
    old_row_after = mock_mcp.invoke(
        "storage", "read_records", {"filter": {"session_id": seed_row["session_id"]}}
    )["records"][0]
    assert old_row_after == seed_row
