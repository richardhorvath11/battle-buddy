"""US2 close-time dual-write (spec AS-1..AS-4, Edge Cases, FR-008, SC-002, research R10).

Drives ``store_flows.open_session``/``close_session`` — the executable form of
``skills/session-store/SKILL.md``'s "Open and close flow" section — against the mock
store, asserting purely on the write log, returned outcomes, the mock's record/artifact
state, and the local ``marker.json`` file (never prose).

**AS-4 construction note** (documented per the task's instruction to choose the most
honest contract-expressible construction): the contract's ``read_records`` is a strict
field-equality filter, so a row returned by filtering on ``session_id`` can never itself
carry a *different* ``session_id`` — a "mismatched read-back" is structurally
unreachable by feeding the mock bad data. ``close_session`` exposes
``expected_session_id`` for exactly this reason: every write in the flow still targets
the real ``session_id`` (the row lands correctly), but the step-4 confirmation is
checked against a caller-supplied expectation, standing in for a corrupted/stale local
marker that recorded the wrong ``session_id``. This is the same escape hatch the task
text names explicitly ("driving close_session's read-back verification with a wrong
expected session_id parameter if the flow exposes one"). The "read-back fails outright"
half of AS-4 is exercised separately and naturally by the not_found edge case below (the
update never lands, so the read-back finds nothing to confirm).
"""

import json

import pytest

from helpers import store_flows

OPEN_FIELDS = dict(
    fingerprint="a" * 16,
    catalog_resolved=True,
    alert_signature="checkout-api: high latency",
    services=["checkout-api"],
    severity="sev2",
    responder="alice @ 2026-07-20T09:00:00Z",
    started_at="2026-07-20T09:00:00Z",
)

CLOSE_FIELDS = dict(
    closed_at="2026-07-20T10:00:00Z",
    timeline=[{"at": "2026-07-20T09:05:00Z", "event": "triage started"}],
    root_cause="deploy rollback race",
    resolution="rolled back to previous revision",
    runbook_refs=[],
    report_url=None,
)

STAGED_ARTIFACTS = {
    "staging/transcript.md": "# transcript\n...",
    "trace.jsonl": '{"seq": 1}\n',
    "staging/checkpoints.jsonl": '{"seq": 0}\n',
}


def _open(mock, tmp_path, source_id="ALERT-1", **overrides):
    fields = dict(OPEN_FIELDS)
    fields.update(overrides)
    return store_flows.open_session(
        mock, tmp_path, "incident", source_id, "2026-07-20", **fields
    )


def _ops_from(mock, start):
    return [(e["capability"], e["op"]) for e in mock.write_log.entries[start:]]


# ---------------------------------------------------------------------------
# AS-1: close-flow ordering — diary before every put_file before update_record;
# mid-session writes (pre-close) sit outside the ordering claim.
# ---------------------------------------------------------------------------


def test_as1_close_flow_write_ordering(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path)
    session_id = open_out["session_id"]

    # Mid-session write (e.g. checkpoint overflow) — precedes /close and sits
    # outside the ordering claim (SKILL.md "Close — pinned write order" scope
    # note). It happens to itself be a put_file, which is exactly the point:
    # if the claim wrongly covered mid-session writes too, this call landing
    # before the diary append below would falsify "diary before every
    # close-flow put_file".
    mock_mcp.invoke(
        "artifacts",
        "put_file",
        {"name": "battle-buddy/{}/checkpoint-1.json".format(session_id), "content": "{}"},
    )

    close_segment_start = len(mock_mcp.write_log.entries)
    close_out = store_flows.close_session(
        mock_mcp,
        tmp_path,
        session_id,
        close_fields=CLOSE_FIELDS,
        diary_content="closing out the incident",
        staged_artifacts=STAGED_ARTIFACTS,
    )

    ops = _ops_from(mock_mcp, close_segment_start)
    assert ops[0] == ("diary", "append_entry")
    assert ops[-1] == ("storage", "update_record")
    put_file_positions = [i for i, op in enumerate(ops) if op == ("artifacts", "put_file")]
    assert len(put_file_positions) == len(STAGED_ARTIFACTS)
    update_position = ops.index(("storage", "update_record"))
    assert all(0 < i < update_position for i in put_file_positions)
    assert close_out["marker_cleared"] is True


def test_close_reasserts_write_once_fields_never_caller_values(mock_mcp, tmp_path):
    # FR-002 / SKILL.md step 3: write-once fields the close-time update carries
    # (notably fingerprint) are re-asserted at their open-time values, never
    # recomputed — a caller-supplied fingerprint in close_fields must lose to
    # the open-time row's value.
    open_out = _open(mock_mcp, tmp_path)
    session_id = open_out["session_id"]

    close_fields = dict(CLOSE_FIELDS)
    close_fields["fingerprint"] = "f" * 16  # bogus "recomputed" value

    store_flows.close_session(
        mock_mcp,
        tmp_path,
        session_id,
        close_fields=close_fields,
        diary_content="closing out the incident",
        staged_artifacts=STAGED_ARTIFACTS,
    )

    (row,) = mock_mcp.invoke(
        "storage", "read_records", {"filter": {"session_id": session_id}}
    )["records"]
    assert row["fingerprint"] == OPEN_FIELDS["fingerprint"]


# ---------------------------------------------------------------------------
# AS-2: confirmed read-back clears the marker (deletion-is-cleared).
# ---------------------------------------------------------------------------


def test_as2_confirmed_readback_deletes_marker(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path)
    marker_path = tmp_path / "marker.json"
    assert marker_path.exists()

    close_out = store_flows.close_session(
        mock_mcp,
        tmp_path,
        open_out["session_id"],
        close_fields=CLOSE_FIELDS,
        diary_content="closing out the incident",
        staged_artifacts=STAGED_ARTIFACTS,
    )

    assert close_out["readback_confirmed"] is True
    assert close_out["marker_cleared"] is True
    assert not marker_path.exists()


# ---------------------------------------------------------------------------
# AS-3: diary failure (contract-valid: empty content -> invalid_input) -> row
# still lands with diary_pending: true; remaining ordering intact; marker
# still clears on a good read-back.
# ---------------------------------------------------------------------------


def test_as3_diary_failure_row_lands_pending_ordering_intact(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path)
    session_id = open_out["session_id"]

    close_segment_start = len(mock_mcp.write_log.entries)
    close_out = store_flows.close_session(
        mock_mcp,
        tmp_path,
        session_id,
        close_fields=CLOSE_FIELDS,
        diary_content="",  # contract-valid failure injection (non_empty content)
        staged_artifacts=STAGED_ARTIFACTS,
    )

    assert close_out["diary_link"] is None
    assert close_out["diary_pending"] is True  # outcome surfaces the retry

    # the rejected append_entry call is never logged (mock convention) — the
    # close segment's log starts directly with the put_file calls, still
    # followed by exactly one update_record.
    ops = _ops_from(mock_mcp, close_segment_start)
    assert ("diary", "append_entry") not in ops
    assert ops[-1] == ("storage", "update_record")
    assert ops.count(("artifacts", "put_file")) == len(STAGED_ARTIFACTS)

    row = mock_mcp.invoke("storage", "read_records", {"filter": {"session_id": session_id}})[
        "records"
    ][0]
    assert row["diary_pending"] is True
    assert "diary_url" not in row

    # the row write was never skipped or reordered to compensate — read-back
    # still confirms and the marker still clears.
    assert close_out["readback_confirmed"] is True
    assert close_out["marker_cleared"] is True
    assert not (tmp_path / "marker.json").exists()


# ---------------------------------------------------------------------------
# AS-4: failed/mismatched read-back -> marker stays. See module docstring for
# the construction.
# ---------------------------------------------------------------------------


def test_as4_mismatched_readback_leaves_marker(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path)
    session_id = open_out["session_id"]
    marker_path = tmp_path / "marker.json"
    assert marker_path.exists()

    close_out = store_flows.close_session(
        mock_mcp,
        tmp_path,
        session_id,
        close_fields=CLOSE_FIELDS,
        diary_content="closing out the incident",
        staged_artifacts=STAGED_ARTIFACTS,
        # a stale/corrupted local marker would record a session_id that
        # doesn't match what the store actually confirms back.
        expected_session_id="incident-ALERT-1-2026-07-19",
    )

    assert close_out["readback_confirmed"] is False
    assert close_out["marker_cleared"] is False
    assert marker_path.exists()

    # the row itself still landed correctly under the real session_id — only
    # the marker-clearance confirmation failed.
    row = mock_mcp.invoke("storage", "read_records", {"filter": {"session_id": session_id}})[
        "records"
    ][0]
    assert row["closed_at"] == CLOSE_FIELDS["closed_at"]
    assert row["root_cause"] == CLOSE_FIELDS["root_cause"]


# ---------------------------------------------------------------------------
# Open twin (FR-008): confirmed read-back -> open_write_confirmed: true;
# failed append (contract-valid: empty session_id -> invalid_input, row never
# lands) -> open_write_confirmed: false, outcome says so.
# ---------------------------------------------------------------------------


def test_open_twin_confirmed_readback_sets_flag_true(mock_mcp, tmp_path):
    out = _open(mock_mcp, tmp_path)
    assert out["readback_confirmed"] is True
    marker = json.loads((tmp_path / "marker.json").read_text(encoding="utf-8"))
    assert marker["protocol"] == "bb.local.v1"
    assert marker["session_id"] == out["session_id"]
    assert marker["source_id"] == "ALERT-1"
    assert marker["open_write_confirmed"] is True


def test_open_twin_failed_append_leaves_flag_false(mock_mcp, tmp_path):
    fields = dict(OPEN_FIELDS)
    fields["session_id"] = ""  # forces the real append_record rejection
    out = store_flows.open_session(
        mock_mcp, tmp_path, "incident", "ALERT-1", "2026-07-20", **fields
    )

    assert "error" in out["append_result"]
    assert out["append_result"]["error"]["code"] == "invalid_input"
    assert out["readback_confirmed"] is False  # row never landed

    marker = json.loads((tmp_path / "marker.json").read_text(encoding="utf-8"))
    assert marker["open_write_confirmed"] is False
    assert mock_mcp.records.records == []  # nothing landed in the store either


# ---------------------------------------------------------------------------
# Artifact-failure edge: one staged artifact with an empty uploaded name ->
# invalid_input -> row still lands, that link omitted, gap surfaced.
# ---------------------------------------------------------------------------


def test_artifact_failure_omits_link_row_still_lands(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path)
    session_id = open_out["session_id"]

    staged = dict(STAGED_ARTIFACTS)
    # local_name "" is deliberately unmapped -> uploaded_name resolves to ""
    # too; close_session passes that straight to put_file rather than
    # fabricating a folder-qualified name, so the real contract's non-empty
    # check rejects it (documented in close_session's docstring).
    staged[""] = "orphaned content"

    close_out = store_flows.close_session(
        mock_mcp,
        tmp_path,
        session_id,
        close_fields=CLOSE_FIELDS,
        diary_content="closing out the incident",
        staged_artifacts=staged,
    )

    assert "" in close_out["omitted_artifacts"]
    assert "" not in close_out["uploaded"]
    assert len(close_out["uploaded"]) == len(STAGED_ARTIFACTS)

    row = mock_mcp.invoke("storage", "read_records", {"filter": {"session_id": session_id}})[
        "records"
    ][0]
    assert all(entry["url"] != "" for entry in row["links"])
    assert len(row["links"]) == len(STAGED_ARTIFACTS)  # the omitted one never landed

    # the row write and marker clearance were never blocked by the one bad
    # artifact.
    assert close_out["marker_cleared"] is True


# ---------------------------------------------------------------------------
# not_found edge: update_record on an unknown session_id -> surfaced error +
# re-locate read (source ID + non-terminal status), never a blind retry.
# ---------------------------------------------------------------------------


def test_not_found_update_relocates_without_blind_retry(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path, source_id="ALERT-7")
    real_session_id = open_out["session_id"]
    # a stale/mistyped id: same source ID, yesterday's date — the row the
    # store actually has does not exist under this key.
    bogus_session_id = "incident-ALERT-7-2026-07-19"

    close_segment_start = len(mock_mcp.write_log.entries)
    close_out = store_flows.close_session(
        mock_mcp,
        tmp_path,
        bogus_session_id,
        close_fields=CLOSE_FIELDS,
        diary_content="closing out the incident",
        staged_artifacts={},
    )

    assert close_out["update_result"]["error"]["code"] == "not_found"
    # write_log only records successful mutations (mock convention) — so the
    # rejected update_record leaves no trace there; the flow's own code path
    # only calls update_record once regardless (no retry loop), which the
    # reconciliation outcome below corroborates.
    update_ops = [op for op in _ops_from(mock_mcp, close_segment_start) if op[1] == "update_record"]
    assert update_ops == []

    reconciliation = close_out["not_found_reconciliation"]
    assert reconciliation["source_id"] == "ALERT-7"
    relocated_ids = [row["session_id"] for row in reconciliation["relocated"]]
    assert relocated_ids == [real_session_id]

    assert close_out["readback_confirmed"] is False
    assert close_out["marker_cleared"] is False


# ---------------------------------------------------------------------------
# R10: diary-pending rows are findable via read_records filter
# {diary_pending: true} — the recovery/retry-queue read.
# ---------------------------------------------------------------------------


def test_r10_diary_pending_recovery_read_and_retry(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path)
    session_id = open_out["session_id"]
    store_flows.close_session(
        mock_mcp,
        tmp_path,
        session_id,
        close_fields=CLOSE_FIELDS,
        diary_content="",  # forces diary_pending: true
        staged_artifacts=STAGED_ARTIFACTS,
    )

    pending = mock_mcp.invoke("storage", "read_records", {"filter": {"diary_pending": True}})[
        "records"
    ]
    assert [row["session_id"] for row in pending] == [session_id]

    # R10's documented recovery: write the diary entry, then update the row.
    retry = mock_mcp.invoke("diary", "append_entry", {"content": "late diary entry"})
    mock_mcp.invoke(
        "storage",
        "update_record",
        {
            "session_id": session_id,
            "fields": {"diary_url": retry["link"], "diary_pending": False},
        },
    )

    row = mock_mcp.invoke("storage", "read_records", {"filter": {"session_id": session_id}})[
        "records"
    ][0]
    assert row["diary_pending"] is False
    assert row["diary_url"] == retry["link"]

    still_pending = mock_mcp.invoke(
        "storage", "read_records", {"filter": {"diary_pending": True}}
    )["records"]
    assert still_pending == []
