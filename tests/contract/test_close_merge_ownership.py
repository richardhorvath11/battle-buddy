"""US4 merge-at-close + close-time ownership displacement (spec AS-5, Edge
Case "Ownership lost before close"; contracts/lifecycle-protocol.md "Close
order (FR-008) and ordering-claim scope", "Marker lifecycle" close-time
ownership scope; research R12, R13).

Drives ``lifecycle_flows.close_command`` against the ``merge-duplicates``
and ``ownership-displaced`` seed fixtures, asserting purely on the mock's
write log, the store's row state, and the local ``marker.json``/
``.bb-session/`` directory — never prose (Constitution VIII).
``test_close_command.py`` (T016) covers every other close-flow behavior;
every scenario here specifically exercises R12's merge-first canonical
retarget and R13's close-time ownership re-read.

**The realistic scenario, and the bug the earlier version of this file
masked**: the closing session is the **duplicate**'s own — carol opened the
later of two true-race rows, her local marker names her own session, and
her own token (``responder``) is what `/close` runs with. The earlier
version of this test instead passed ``canonical_row["responder"]`` (bob's
token) as the closer's identity while the marker named carol's session — a
combination no real open flow ever produces, and one that happened to paper
over a false-denial bug: comparing the *canonical* row's responder against
the *closer's own* token unconditionally, which false-denies exactly this
ordinary "straggler closes first" case (the row a real carol authenticates
as is her own, never bob's). ``close_command`` now checks ownership in two
places that each compare the right pair: this session's own (marker-named)
row against the closer's token, immediately after approval and before any
write at all — and, separately, canonical's row (at the close-time update,
inside ``store_flows.close_session``) against canonical's own responder as
observed during detection — never the closer's token when the two rows
differ.
"""

import json

from helpers import lifecycle_fixtures, lifecycle_flows, store_flows

CLOSE_FIELDS = dict(
    status="closed",
    closed_at="2026-07-20T12:00:00+00:00",
    root_cause="two responders paged the same alert before either saw the other",
    resolution="merged into the earlier session; incident resolved there",
    runbook_refs=[],
    report_url=None,
)


def _write_marker(tmp_path, session_id, source_id, opened_at):
    tmp_path.mkdir(parents=True, exist_ok=True)
    marker = {
        "protocol": "bb.local.v1",
        "session_id": session_id,
        "source_id": source_id,
        "opened_at": opened_at,
        "open_write_confirmed": True,
    }
    (tmp_path / "marker.json").write_text(json.dumps(marker), encoding="utf-8")
    return marker


def _ops_from(mock, start):
    return [(e["capability"], e["op"]) for e in mock.write_log.entries[start:]]


def _seed_merge_duplicates(mock):
    lifecycle_fixtures.write_seed(mock, "merge-duplicates")
    rows = lifecycle_fixtures.load_seed_fixture("merge-duplicates")
    canonical_row, duplicate_row = rows[0], rows[1]
    assert canonical_row["started_at"] < duplicate_row["started_at"]
    return canonical_row, duplicate_row


# ---------------------------------------------------------------------------
# AS-5 / R12: merge-at-close, the realistic scenario — the DUPLICATE's own
# closer (carol) runs /close with her own marker and her own token. Earliest
# canonical, duplicate superseded, links + artifacts folder folded,
# dual-write targets canonical, carol's own marker cleared on canonical's
# read-back even though her own row was superseded.
# ---------------------------------------------------------------------------


def test_duplicate_owner_closes_merge_targets_canonical_marker_cleared(mock_mcp, tmp_path):
    canonical_row, duplicate_row = _seed_merge_duplicates(mock_mcp)

    # carol's own marker, naming her own (later-started, soon-to-be-
    # superseded) session — exactly what a real open flow produces.
    _write_marker(
        tmp_path, duplicate_row["session_id"], "ALERT-555", duplicate_row["started_at"]
    )

    draft = {"approved": True, "rendered_entry": "closing out the race"}
    segment_start = len(mock_mcp.write_log.entries)
    out = lifecycle_flows.close_command(
        mock_mcp,
        tmp_path,
        None,
        draft,
        CLOSE_FIELDS,
        duplicate_row["responder"],  # carol's OWN token — never bob's.
    )

    assert out["merged"] is True
    assert out["canonical_id"] == canonical_row["session_id"]
    assert out["superseded_ids"] == [duplicate_row["session_id"]]
    assert out["read_only"] is False

    # Duplicate superseded, never deleted.
    dup_after = mock_mcp.invoke(
        "storage", "read_records", {"filter": {"session_id": duplicate_row["session_id"]}}
    )["records"][0]
    assert dup_after["status"] == "superseded"

    # Exactly one non-superseded row for the source ID (AS-5).
    all_rows = mock_mcp.invoke("storage", "read_records", {})["records"]
    same_source = [
        r for r in all_rows if store_flows.parse_source_id(r["session_id"]) == "ALERT-555"
    ]
    non_superseded = [r for r in same_source if r["status"] != "superseded"]
    assert len(non_superseded) == 1
    assert non_superseded[0]["session_id"] == canonical_row["session_id"]

    # Links: duplicate's own links + its artifacts folder, folded into
    # canonical's as {url, excerpt} pairs — survive to the final closed row.
    canonical_after = non_superseded[0]
    urls = [entry["url"] for entry in canonical_after["links"]]
    assert canonical_row["links"][0]["url"] in urls
    assert duplicate_row["links"][0]["url"] in urls
    assert duplicate_row["artifacts_folder_url"] in urls
    for entry in canonical_after["links"]:
        assert entry["url"] and entry["excerpt"]

    # Dual-write targeted canonical, never carol's own (by-then-superseded)
    # session — the close-time update_record's summary names canonical.
    ops_segment = mock_mcp.write_log.entries[segment_start:]
    update_summaries = [e["summary"] for e in ops_segment if e["op"] == "update_record"]
    assert "session_id={}".format(canonical_row["session_id"]) in update_summaries[-1]

    # Carol's own marker (naming the now-superseded duplicate) is still
    # cleared — gated on canonical's read-back, not the duplicate's.
    assert out["readback_confirmed"] is True
    assert out["marker_cleared"] is True
    assert not tmp_path.exists()


# ---------------------------------------------------------------------------
# R13, first checkpoint: this session's own row was taken over (by a third
# responder) before it gets to close — duplicates exist, but the pre-merge
# ownership check (immediately after approval, before any close-flow write)
# catches the displacement before merge ever runs. Zero writes at all.
# ---------------------------------------------------------------------------


def test_own_row_displaced_before_merge_zero_writes(mock_mcp, tmp_path):
    canonical_row, duplicate_row = _seed_merge_duplicates(mock_mcp)

    # dave takes carol's own row over before she gets to close it — a real
    # mutating take-over write, not a contrived seed value.
    store_flows.take_over(mock_mcp, duplicate_row["session_id"], "dave")

    _write_marker(
        tmp_path, duplicate_row["session_id"], "ALERT-555", duplicate_row["started_at"]
    )

    draft = {"approved": True, "rendered_entry": "closing out"}
    segment_start = len(mock_mcp.write_log.entries)  # after the take-over above
    out = lifecycle_flows.close_command(
        mock_mcp,
        tmp_path,
        None,
        draft,
        CLOSE_FIELDS,
        duplicate_row["responder"],  # carol's original token — no longer current
    )

    assert out["merged"] is False  # merge never starts
    assert out["read_only"] is True
    assert out["taken_over_by"] == "dave"

    # No merge write, no diary write, no artifact write, no row update —
    # the R13 first checkpoint fires before any close-flow write at all.
    ops = _ops_from(mock_mcp, segment_start)
    assert ops == []

    # The duplicate row is exactly as dave's take-over left it — not
    # superseded, since merge never ran.
    dup_after = mock_mcp.invoke(
        "storage", "read_records", {"filter": {"session_id": duplicate_row["session_id"]}}
    )["records"][0]
    assert dup_after["status"] != "superseded"
    assert dup_after["responder"] == "dave"

    assert out["readback_confirmed"] is False
    assert out["marker_cleared"] is False
    assert (tmp_path / "marker.json").exists()
    assert tmp_path.exists()


# ---------------------------------------------------------------------------
# SC-006 / Constitution V, with duplicates in play: an unapproved draft
# performs zero writes even when merge-eligible duplicates exist — the
# approval gate covers the merge, not only the dual-write.
# ---------------------------------------------------------------------------


def test_unapproved_draft_with_duplicates_seeded_zero_writes(mock_mcp, tmp_path):
    canonical_row, duplicate_row = _seed_merge_duplicates(mock_mcp)
    _write_marker(
        tmp_path, duplicate_row["session_id"], "ALERT-555", duplicate_row["started_at"]
    )

    draft = {"approved": False, "rendered_entry": "closing out"}
    write_log_before = list(mock_mcp.write_log.entries)
    out = lifecycle_flows.close_command(
        mock_mcp, tmp_path, None, draft, CLOSE_FIELDS, duplicate_row["responder"]
    )

    assert out["approved"] is False
    assert out["merged"] is False
    # The read-only detection step still reports what canonical WOULD be —
    # describing, never writing.
    assert out["canonical_id"] == canonical_row["session_id"]
    assert mock_mcp.write_log.entries == write_log_before
    assert (tmp_path / "marker.json").exists()

    dup_after = mock_mcp.invoke(
        "storage", "read_records", {"filter": {"session_id": duplicate_row["session_id"]}}
    )["records"][0]
    assert dup_after["status"] != "superseded"


# ---------------------------------------------------------------------------
# Edge (R13, single-row — no merge in play): ownership displaced from this
# session's own row before any close-flow write; marker intact.
#
# NOTE on the canonical-takeover-mid-close race (finding 3b): a take-over of
# the *canonical* row landing strictly between step 2's read-only detection
# and step 8's close-time update — the second ownership checkpoint's actual
# window — cannot be simulated end-to-end through close_command without
# test-only reentrancy hooks. The checkpoint's *mechanism* is instead
# exercised directly below (test_close_session_owned_by_mismatch_denies):
# store_flows.close_session with a mismatching owned_by, standing in for
# exactly that mid-window canonical take-over.
# ---------------------------------------------------------------------------


def test_close_session_owned_by_mismatch_denies_row_write(mock_mcp, tmp_path):
    # Checkpoint 2's denial branch, called directly: the canonical row's
    # responder no longer matches the owned_by observed at detection time —
    # the D-18 stand-in for a canonical take-over landing mid-close.
    lifecycle_fixtures.write_seed(mock_mcp, "ownership-displaced")
    seed_row = lifecycle_fixtures.load_seed_fixture("ownership-displaced")[0]
    write_log_before = list(mock_mcp.write_log.entries)

    out = store_flows.close_session(
        mock_mcp,
        tmp_path,
        seed_row["session_id"],
        {"closed_at": "2026-07-21T12:00:00+00:00", "status": "closed"},
        "closing entry",
        {},
        owned_by="carol @ 2026-07-21T09:00:00+00:00",
    )

    assert out["read_only"] is True
    assert out["taken_over_by"] == seed_row["responder"]
    assert out["update_result"] is None
    assert out["marker_cleared"] is False
    # The diary write (step 1) precedes checkpoint 2 by design — only the
    # row update and everything after it are denied.
    ops = [(e["capability"], e["op"]) for e in mock_mcp.write_log.entries[len(write_log_before):]]
    assert ("storage", "update_record") not in ops


def test_ownership_displaced_before_close_no_row_writes_marker_intact(mock_mcp, tmp_path):
    lifecycle_fixtures.write_seed(mock_mcp, "ownership-displaced")
    seed_row = lifecycle_fixtures.load_seed_fixture("ownership-displaced")[0]
    marker = _write_marker(
        tmp_path, seed_row["session_id"], "ALERT-999", seed_row["started_at"]
    )

    draft = {"approved": True, "rendered_entry": "closing out"}
    segment_start = len(mock_mcp.write_log.entries)
    out = lifecycle_flows.close_command(
        mock_mcp,
        tmp_path,
        None,
        draft,
        CLOSE_FIELDS,
        "alice @ 2026-07-20T09:00:00+00:00",  # != seed_row["responder"] ("dave")
    )

    assert out["merged"] is False  # only one row for this source — no merge at all
    assert out["read_only"] is True
    assert out["taken_over_by"] == seed_row["responder"]

    # Under the adjudicated order, the ownership pre-read runs immediately
    # after approval, before any close-flow write at all — so a displaced
    # close (merge or not) now performs ZERO writes, not just "no row
    # update": no diary write, no artifact write either.
    ops = _ops_from(mock_mcp, segment_start)
    assert ops == []

    assert out["readback_confirmed"] is False
    assert out["marker_cleared"] is False
    assert (tmp_path / "marker.json").exists()
    assert json.loads((tmp_path / "marker.json").read_text(encoding="utf-8")) == marker
    assert tmp_path.exists()
