"""US4 optimistic ownership (spec AS-1..AS-4, Edge Cases, FR-009, SC-004).

Drives ``store_flows.take_over`` / ``detect_open_session`` / ``merge_duplicates`` —
the executable form of ``skills/session-store/SKILL.md``'s "Session ownership"
section — against the mock store, seeded via
``tests/fixtures/store/seed-ownership.json``. Asserts on the mock's write log, row
contents, and ``store_flows.write_checkpoint``'s outcome shape — never prose.

Fixture rows (see the JSON file for exact fields):

- ``incident-HND-77-2026-07-19`` — open, owned by ALICE, opened *yesterday* relative
  to this suite's "today" (2026-07-20) — the take-over + cross-day join scenarios.
- ``incident-HND-88-2026-07-18`` — ``handoff`` status, source ``HND-88`` — proves
  handoff rows are joinable too.
- ``incident-HND-99-2026-07-15`` — ``closed`` (terminal) status, source ``HND-99`` —
  must never join.
- ``incident-HND-55-2026-07-18`` / ``incident-HND-55-2026-07-19`` — a same-source,
  same-fingerprint duplicate-open pair (distinct ``started_at``) — the merge scenario.
"""

import json

from conftest import fixture_path
from helpers import store_flows

SEED_PATH = fixture_path("store", "seed-ownership.json")
CHECKPOINTS_DIR = ("store", "checkpoints")

ALICE = "alice @ 2026-07-19T22:00:00Z"
BOB = "bob @ 2026-07-20T10:00:00Z"

HND_77 = "incident-HND-77-2026-07-19"
HND_88 = "incident-HND-88-2026-07-18"
HND_99 = "incident-HND-99-2026-07-15"
HND_55_CANONICAL = "incident-HND-55-2026-07-18"
HND_55_DUPLICATE = "incident-HND-55-2026-07-19"


def _seed(mock):
    mock.load_seed(SEED_PATH)


def _row(mock, session_id):
    return mock.invoke(
        "storage", "read_records", {"filter": {"session_id": session_id}}
    )["records"][0]


def _load_checkpoint(name):
    with open(str(fixture_path(*CHECKPOINTS_DIR, name)), encoding="utf-8") as f:
        return json.load(f)


def _history_lines(tmp_path):
    path = tmp_path / "staging" / "checkpoints.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# ---------------------------------------------------------------------------
# AS-1: take-over is a single write; row's responder becomes B's; outcome
# reports the displaced (previous) responder.
# ---------------------------------------------------------------------------


def test_as1_take_over_is_single_write_reporting_displaced_owner(mock_mcp):
    _seed(mock_mcp)
    segment_start = len(mock_mcp.write_log.entries)

    outcome = store_flows.take_over(mock_mcp, HND_77, BOB)

    written = mock_mcp.write_log.entries[segment_start:]
    assert len(written) == 1
    assert written[0]["capability"] == "storage"
    assert written[0]["op"] == "update_record"

    assert outcome["previous_responder"] == ALICE
    assert outcome["new_responder"] == BOB
    assert "error" not in outcome["update_result"]

    row = _row(mock_mcp, HND_77)
    assert row["responder"] == BOB


# ---------------------------------------------------------------------------
# AS-2: after take-over, the displaced session's checkpoint pre-read fails —
# no write performed, outcome names the new responder, zero mutating ops.
# ---------------------------------------------------------------------------


def test_as2_displaced_session_checkpoint_write_denied_no_mutation(mock_mcp, tmp_path):
    _seed(mock_mcp)
    store_flows.take_over(mock_mcp, HND_77, BOB)
    doc = _load_checkpoint("valid-ledger.json")

    segment_start = len(mock_mcp.write_log.entries)
    outcome = store_flows.write_checkpoint(
        mock_mcp, tmp_path, HND_77, [doc], responder=ALICE, seq=1
    )

    assert outcome == {
        "written": False,
        "read_only": True,
        "taken_over_by": BOB,
    }
    # zero mutating ops performed by the displaced session after take-over.
    assert mock_mcp.write_log.entries[segment_start:] == []
    row = _row(mock_mcp, HND_77)
    assert "latest_checkpoint" not in row
    assert _history_lines(tmp_path) == []


# ---------------------------------------------------------------------------
# AS-3 + cross-day edge: join-at-open finds the yesterday-dated open row (a
# recomputed today-ID lookup would miss it); handoff-status rows are also
# joinable; a terminal (closed) row's source never joins.
# ---------------------------------------------------------------------------


def test_as3_join_at_open_cross_day_handoff_and_terminal_exclusion(mock_mcp):
    _seed(mock_mcp)

    # Cross-day: HND-77 was opened yesterday (2026-07-19); a session opening
    # on this source "today" (2026-07-20) would compute this session_id if it
    # recomputed rather than parsed — prove that ID differs from the seeded
    # row's actual session_id, yet detect_open_session still finds it.
    todays_recomputed_id = "incident-HND-77-2026-07-20"
    assert HND_77 != todays_recomputed_id

    matches = store_flows.detect_open_session(mock_mcp, "HND-77")
    assert [row["session_id"] for row in matches] == [HND_77]
    assert matches[0]["session_id"] != todays_recomputed_id

    # Handoff-status row on a second source is joinable too.
    handoff_matches = store_flows.detect_open_session(mock_mcp, "HND-88")
    assert [row["session_id"] for row in handoff_matches] == [HND_88]
    assert handoff_matches[0]["status"] == "handoff"

    # A terminal (closed) row's source never triggers a join.
    terminal_matches = store_flows.detect_open_session(mock_mcp, "HND-99")
    assert terminal_matches == []


# ---------------------------------------------------------------------------
# AS-4 + SC-004: merge-at-close — earliest canonical, exact fold-in shape,
# duplicate superseded, exactly one non-superseded row per source ID, and the
# superseded row never surfaces at retrieval.
# ---------------------------------------------------------------------------


def test_as4_merge_at_close_folds_in_and_excludes_superseded_from_retrieval(mock_mcp):
    _seed(mock_mcp)
    canonical_before = _row(mock_mcp, HND_55_CANONICAL)
    duplicate_before = _row(mock_mcp, HND_55_DUPLICATE)
    assert canonical_before["started_at"] < duplicate_before["started_at"]

    outcome = store_flows.merge_duplicates(mock_mcp, "HND-55")

    assert outcome == {
        "canonical_id": HND_55_CANONICAL,
        "superseded_ids": [HND_55_DUPLICATE],
    }

    canonical_after = _row(mock_mcp, HND_55_CANONICAL)
    duplicate_after = _row(mock_mcp, HND_55_DUPLICATE)

    # Duplicate is superseded, never deleted; canonical's own status/other
    # fields are untouched by the merge.
    assert duplicate_after["status"] == "superseded"
    assert canonical_after["status"] == "open"

    # Exact fold-in shape: duplicate's links entries + its artifacts_folder_url
    # wrapped as {url, excerpt}, appended after the canonical's own links —
    # nothing else moves.
    expected_links = (
        list(canonical_before["links"])
        + list(duplicate_before["links"])
        + [
            {
                "url": duplicate_before["artifacts_folder_url"],
                "excerpt": "artifacts folder of {}".format(HND_55_DUPLICATE),
            }
        ]
    )
    assert canonical_after["links"] == expected_links

    # "Nothing else moves" — full-row check: the canonical row differs from its
    # pre-merge state in links ONLY, and the duplicate in status ONLY.
    assert canonical_after == {**canonical_before, "links": expected_links}
    assert duplicate_after == {**duplicate_before, "status": "superseded"}

    # Exactly one non-superseded row remains for this source ID (SC-004).
    all_rows = mock_mcp.invoke("storage", "read_records", {})["records"]
    same_source = [
        row
        for row in all_rows
        if store_flows._safe_parse_source_id(row.get("session_id")) == "HND-55"
    ]
    non_superseded = [row for row in same_source if row["status"] != "superseded"]
    assert [row["session_id"] for row in non_superseded] == [HND_55_CANONICAL]

    # Tie to retrieval exclusions (retrieval.md stage-0): a fingerprint query
    # that would match both rows now surfaces only the canonical one — the
    # superseded row never surfaces.
    retrieval = store_flows.retrieve_candidates(
        mock_mcp,
        fingerprint=canonical_after["fingerprint"],
        catalog_resolved=canonical_after["catalog_resolved"],
        services=canonical_after["services"],
        alert_signature=canonical_after["alert_signature"],
        severity=canonical_after["severity"],
    )
    assert [row["session_id"] for row in retrieval["candidates"]] == [HND_55_CANONICAL]
    assert retrieval["classification"] == "known_issue"


# ---------------------------------------------------------------------------
# Race-bound edge: a checkpoint write already past its pre-read lands before
# take-over observes it; every subsequent write from the displaced session is
# denied — the row's latest_checkpoint ends up B's, not alice's.
# ---------------------------------------------------------------------------


def test_race_bound_one_stale_checkpoint_lands_then_denied_after_take_over(
    mock_mcp, tmp_path
):
    _seed(mock_mcp)
    alice_doc = _load_checkpoint("valid-ledger.json")
    bob_doc = dict(alice_doc, tool_call_count=99)
    assert bob_doc != alice_doc

    # Alice's checkpoint write lands before B's take-over — the accepted
    # stale-checkpoint bound (at most one).
    before_outcome = store_flows.write_checkpoint(
        mock_mcp, tmp_path, HND_77, [alice_doc], responder=ALICE, seq=1
    )
    assert before_outcome["written"] is True

    take_over_outcome = store_flows.take_over(mock_mcp, HND_77, BOB)
    assert take_over_outcome["previous_responder"] == ALICE
    assert take_over_outcome["new_responder"] == BOB

    # Alice's next attempt, still on her stale token, is denied.
    after_outcome = store_flows.write_checkpoint(
        mock_mcp, tmp_path, HND_77, [alice_doc], responder=ALICE, seq=2
    )
    assert after_outcome == {
        "written": False,
        "read_only": True,
        "taken_over_by": BOB,
    }

    # B writes her own checkpoint after taking over — it lands.
    bob_outcome = store_flows.write_checkpoint(
        mock_mcp, tmp_path, HND_77, [bob_doc], responder=BOB, seq=2
    )
    assert bob_outcome["written"] is True

    row = _row(mock_mcp, HND_77)
    assert json.loads(row["latest_checkpoint"]) == bob_doc

    # Exactly one alice checkpoint landed (her pre-take-over write) plus B's —
    # her post-take-over attempt contributed no history line.
    lines = _history_lines(tmp_path)
    assert len(lines) == 2
    assert lines[0]["document"] == alice_doc
    assert lines[1]["document"] == bob_doc
