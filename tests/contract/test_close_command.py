"""US4 `/close` dual-write, draft structure, and derived-timeline behavior
(spec FR-007..FR-010, AS-1..AS-4, AS-6, AS-7, SC-005, SC-006; contracts/
lifecycle-protocol.md "Diary draft artifact — bb.draft.v1", "Close order
(FR-008) and ordering-claim scope", "Transcript capture at close", "Timeline
derivation"; research R5, R9, R10).

Drives ``lifecycle_flows.draft_close``/``close_command`` against
``bb-mock-mcp`` with a fixture session and fixture trace/checkpoint/
transcript inputs, asserting purely on the mock's write log, artifact
store, returned row, and the local ``.bb-session/`` directory — never prose
(Constitution VIII). Merge-at-close and close-time ownership displacement
are exercised separately in ``test_close_merge_ownership.py`` (T017); every
scenario in this file is a single-row, no-merge close.

**Ownership-checkpoint construction note** (``test_failed_readback_leaves_directory_intact``
below): ``close_command``'s own first ownership checkpoint (immediately
after approval, before any close-flow write — R13's first checkpoint)
always runs and always compares — there is no "skip" sentinel for it. That
test passes ``responder=None`` for a marker naming a session with **no
matching row at all**: the checkpoint's fresh read finds no row
(``current_own_responder`` reads back ``None`` too), so ``None == None``
passes the check legitimately, not by suppressing it — this isolates the
genuine ``not_found`` row-write failure the test wants to exercise from an
ownership-mismatch outcome, without contriving a responder string that
would coincidentally already match nothing.
"""

import json

from helpers import lifecycle_fixtures, lifecycle_flows, store_flows

RESPONDER = "alice @ 2026-07-21T09:14:00+00:00"

OPEN_FIELDS = dict(
    fingerprint="a" * 16,
    catalog_resolved=True,
    alert_signature="checkout-api: high latency",
    services=["checkout-api"],
    severity="sev2",
    responder=RESPONDER,
    started_at="2026-07-21T09:14:00+00:00",
)

CAUSAL_PROPOSALS = dict(
    root_cause="deploy rollback race",
    contributing_factors=["insufficient canary bake time"],
    action_items=["extend canary window to 15m"],
)

CLOSE_FIELDS = dict(
    status="closed",
    closed_at="2026-07-21T10:00:00+00:00",
    root_cause="deploy rollback race",
    resolution="rolled back to previous revision",
    runbook_refs=[],
    report_url=None,
)


def _ops_from(mock, start):
    return [(e["capability"], e["op"]) for e in mock.write_log.entries[start:]]


def _open(mock, tmp_path, source_id="ALERT-1", session_type="incident", **overrides):
    fields = dict(OPEN_FIELDS)
    fields.update(overrides)
    return store_flows.open_session(
        mock, tmp_path, session_type, source_id, "2026-07-21", **fields
    )


def _build_draft(mock, row, timeline, approved=True, rendered_entry=None):
    row = dict(row)
    row["closed_at"] = CLOSE_FIELDS["closed_at"]
    draft = lifecycle_flows.draft_close(mock, {}, row, timeline, CAUSAL_PROPOSALS)
    draft["approved"] = approved
    if rendered_entry is not None:
        draft["rendered_entry"] = rendered_entry
    return draft


# ---------------------------------------------------------------------------
# Draft structure (SC-006, AS-4): causal values only under proposals.*, each
# proposal-labeled; factual carries no causal key.
# ---------------------------------------------------------------------------


def test_draft_structure_causal_values_only_under_proposals(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path)
    row = dict(open_out["row"], closed_at=CLOSE_FIELDS["closed_at"])

    draft = lifecycle_flows.draft_close(mock_mcp, {}, row, [], CAUSAL_PROPOSALS)

    assert draft["schema"] == "bb.draft.v1"
    assert draft["approved"] is False
    for key in ("root_cause", "contributing_factors", "action_items"):
        assert draft["proposals"][key]["proposal"] is True
        assert draft["proposals"][key]["value"] == CAUSAL_PROPOSALS[key]
    assert set(CAUSAL_PROPOSALS).isdisjoint(draft["factual"])
    assert "[PROPOSAL]" in draft["rendered_entry"]


def test_close_command_unapproved_draft_zero_writes(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path, source_id="ALERT-2")
    draft = _build_draft(mock_mcp, open_out["row"], [], approved=False)

    write_log_before = list(mock_mcp.write_log.entries)
    out = lifecycle_flows.close_command(
        mock_mcp, tmp_path, None, draft, CLOSE_FIELDS, RESPONDER
    )

    assert out["approved"] is False
    assert "reason" in out and out["reason"]
    assert mock_mcp.write_log.entries == write_log_before
    assert (tmp_path / "marker.json").exists()


# ---------------------------------------------------------------------------
# AS-1 / SC-005: approved close — write-log ordering diary -> artifacts ->
# row update.
# ---------------------------------------------------------------------------


def test_approved_close_write_ordering_diary_then_artifacts_then_update(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path, source_id="ALERT-3")
    session_id = open_out["session_id"]

    lifecycle_fixtures.write_trace_fixture(tmp_path)
    lifecycle_fixtures.write_checkpoint_history_fixture(tmp_path)
    timeline = lifecycle_flows.derive_timeline(tmp_path)
    draft = _build_draft(mock_mcp, open_out["row"], timeline)

    segment_start = len(mock_mcp.write_log.entries)
    out = lifecycle_flows.close_command(
        mock_mcp,
        tmp_path,
        str(lifecycle_fixtures.TRANSCRIPT_PATH),
        draft,
        CLOSE_FIELDS,
        RESPONDER,
    )

    ops = _ops_from(mock_mcp, segment_start)
    assert ops[0] == ("diary", "append_entry")
    assert ops[-1] == ("storage", "update_record")
    put_file_positions = [i for i, op in enumerate(ops) if op == ("artifacts", "put_file")]
    assert len(put_file_positions) == 4  # transcript, trace, checkpoints, report
    update_position = ops.index(("storage", "update_record"))
    assert all(0 < i < update_position for i in put_file_positions)

    assert out["diary_link"] is not None
    assert out["readback_confirmed"] is True
    assert out["marker_cleared"] is True
    assert not tmp_path.exists()

    final_row = mock_mcp.invoke(
        "storage", "read_records", {"filter": {"session_id": session_id}}
    )["records"][0]
    assert final_row["diary_url"] == out["diary_link"]
    assert len(final_row["links"]) == 4
    assert final_row["status"] == "closed"


# ---------------------------------------------------------------------------
# AS-6: artifact names, transcript copied from the fixture path, trace ->
# tool-trace.jsonl mapping.
# ---------------------------------------------------------------------------


def test_artifact_names_and_transcript_trace_mapping(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path, source_id="ALERT-4")
    session_id = open_out["session_id"]

    lifecycle_fixtures.write_trace_fixture(tmp_path)
    lifecycle_fixtures.write_checkpoint_history_fixture(tmp_path)
    timeline = lifecycle_flows.derive_timeline(tmp_path)
    draft = _build_draft(mock_mcp, open_out["row"], timeline)

    transcript_text = lifecycle_fixtures.TRANSCRIPT_PATH.read_text(encoding="utf-8")

    out = lifecycle_flows.close_command(
        mock_mcp,
        tmp_path,
        str(lifecycle_fixtures.TRANSCRIPT_PATH),
        draft,
        CLOSE_FIELDS,
        RESPONDER,
    )

    uploaded = out["uploaded"]
    assert uploaded["staging/transcript.md"]["uploaded_name"] == "transcript.md"
    assert uploaded["trace.jsonl"]["uploaded_name"] == "tool-trace.jsonl"
    assert uploaded["staging/checkpoints.jsonl"]["uploaded_name"] == "checkpoints.jsonl"
    assert uploaded["report.md"]["uploaded_name"] == "report.md"

    prefix = "battle-buddy/{}/".format(session_id)
    for entry in uploaded.values():
        stored = mock_mcp.artifacts.files[entry["link"]]
        assert stored["name"] == prefix + entry["uploaded_name"]

    transcript_link = uploaded["staging/transcript.md"]["link"]
    assert mock_mcp.artifacts.files[transcript_link]["content"] == transcript_text


def test_missing_transcript_source_notice_and_close_continues(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path, source_id="ALERT-5")
    draft = _build_draft(mock_mcp, open_out["row"], [])

    missing_path = tmp_path / "does-not-exist.md"
    out = lifecycle_flows.close_command(
        mock_mcp, tmp_path, str(missing_path), draft, CLOSE_FIELDS, RESPONDER
    )

    assert out["transcript_notice"] is not None
    assert "staging/transcript.md" not in out["uploaded"]
    assert out["readback_confirmed"] is True
    assert out["marker_cleared"] is True


# ---------------------------------------------------------------------------
# AS-3: seeded diary failure -> row lands diary_pending: true, ordering of
# the remaining writes preserved.
# ---------------------------------------------------------------------------


def test_diary_failure_row_lands_diary_pending_ordering_preserved(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path, source_id="ALERT-6")
    session_id = open_out["session_id"]
    draft = _build_draft(mock_mcp, open_out["row"], [], rendered_entry="")

    segment_start = len(mock_mcp.write_log.entries)
    out = lifecycle_flows.close_command(
        mock_mcp, tmp_path, None, draft, CLOSE_FIELDS, RESPONDER
    )

    assert out["diary_link"] is None
    assert out["diary_pending"] is True

    ops = _ops_from(mock_mcp, segment_start)
    assert ("diary", "append_entry") not in ops  # rejected call isn't logged
    assert ops[-1] == ("storage", "update_record")
    assert ops.count(("artifacts", "put_file")) == 1  # report.md only

    final_row = mock_mcp.invoke(
        "storage", "read_records", {"filter": {"session_id": session_id}}
    )["records"][0]
    assert final_row["diary_pending"] is True
    assert "diary_url" not in final_row

    assert out["readback_confirmed"] is True
    assert out["marker_cleared"] is True


# ---------------------------------------------------------------------------
# FR-008: transient row-write failure -> retried, row lands, marker
# deletion still read-back-gated.
# ---------------------------------------------------------------------------


def test_transient_row_write_failure_retried_marker_still_gated(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path, source_id="ALERT-7")
    draft = _build_draft(mock_mcp, open_out["row"], [])

    injector = lifecycle_fixtures.TransientFaultInjector(
        mock_mcp, "storage", "update_record", times=1
    )
    out = lifecycle_flows.close_command(
        injector, tmp_path, None, draft, CLOSE_FIELDS, RESPONDER, row_write_retries=1
    )

    assert injector.failures_injected == 1
    assert out["readback_confirmed"] is True
    assert out["marker_cleared"] is True
    assert not tmp_path.exists()


def test_exhausted_row_write_retry_never_false_confirms(mock_mcp, tmp_path):
    # FR-008's other half: when the bounded retry is EXHAUSTED and the row
    # update still errors, the read-back must not confirm on the open row's
    # mere existence — local state survives for the slice-2 session guard,
    # and the store row stays open (the close did not land).
    open_out = _open(mock_mcp, tmp_path, source_id="ALERT-77")
    draft = _build_draft(mock_mcp, open_out["row"], [])

    injector = lifecycle_fixtures.TransientFaultInjector(
        mock_mcp, "storage", "update_record", times=5
    )
    out = lifecycle_flows.close_command(
        injector, tmp_path, None, draft, CLOSE_FIELDS, RESPONDER, row_write_retries=2
    )

    assert injector.failures_injected == 3  # initial attempt + 2 retries
    assert "error" in out["update_result"]
    assert out["readback_confirmed"] is False
    assert out["marker_cleared"] is False
    assert (tmp_path / "marker.json").exists()  # guard evidence intact
    row = mock_mcp.invoke(
        "storage",
        "read_records",
        {"filter": {"session_id": open_out["session_id"]}},
    )["records"][0]
    assert row["status"] == "open"


# ---------------------------------------------------------------------------
# AS-2: read-back success -> directory deleted; failed read-back -> intact.
# ---------------------------------------------------------------------------


def test_failed_readback_leaves_directory_intact(mock_mcp, tmp_path):
    marker = {
        "protocol": "bb.local.v1",
        "session_id": "incident-ALERT-8-2026-07-19",
        "source_id": "ALERT-8",
        "opened_at": "2026-07-19T09:00:00+00:00",
        "open_write_confirmed": True,
    }
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "marker.json").write_text(json.dumps(marker), encoding="utf-8")

    draft = {"approved": True, "rendered_entry": "closing out"}
    out = lifecycle_flows.close_command(
        mock_mcp, tmp_path, None, draft, CLOSE_FIELDS, None
    )

    assert out["readback_confirmed"] is False
    assert out["marker_cleared"] is False
    assert (tmp_path / "marker.json").exists()
    assert tmp_path.exists()


# ---------------------------------------------------------------------------
# AS-6 / R10: timeline is a 1:1, ordered map over trace call lines +
# checkpoint history — event lines skipped, no transcript-derived events.
# ---------------------------------------------------------------------------


def test_timeline_derivation_1to1_ordering_no_transcript_events(tmp_path):
    call_lines = lifecycle_fixtures.write_trace_fixture(tmp_path)
    checkpoint_entries = lifecycle_fixtures.write_checkpoint_history_fixture(tmp_path)

    timeline = lifecycle_flows.derive_timeline(tmp_path)

    call_line_count = sum(1 for line in call_lines if "event" not in line)
    assert len(timeline) == call_line_count + len(checkpoint_entries)
    assert all(event["source"] in ("trace", "checkpoint") for event in timeline)

    ats = [event["at"] for event in timeline]
    assert ats == sorted(ats)

    for event in timeline:
        assert "transcript" not in json.dumps(event)


# ---------------------------------------------------------------------------
# AS-7: shell close_workspace called last / degraded printed message.
# ---------------------------------------------------------------------------


def test_shell_close_workspace_called_last(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path, source_id="ALERT-9")
    draft = _build_draft(mock_mcp, open_out["row"], [])
    shell = lifecycle_fixtures.RecordingShellAdapter()

    out = lifecycle_flows.close_command(
        mock_mcp, tmp_path, None, draft, CLOSE_FIELDS, RESPONDER, shell=shell
    )

    assert shell.calls[-1] == {
        "method": "close_workspace",
        "session_id": out["canonical_id"],
    }
    assert out["shell_calls"] is shell.calls


def test_shell_absent_close_workspace_degraded_printed(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path, source_id="ALERT-10")
    draft = _build_draft(mock_mcp, open_out["row"], [])

    out = lifecycle_flows.close_command(
        mock_mcp, tmp_path, None, draft, CLOSE_FIELDS, RESPONDER
    )

    assert out["shell_calls"] is None
    assert any("close workspace" in entry.get("text", "") for entry in out["printed"])


# ---------------------------------------------------------------------------
# Edge: no open session -> zero writes.
# ---------------------------------------------------------------------------


def test_no_marker_close_zero_writes(mock_mcp, tmp_path):
    write_log_before = list(mock_mcp.write_log.entries)
    draft = {"approved": True, "rendered_entry": "x"}

    out = lifecycle_flows.close_command(
        mock_mcp, tmp_path, None, draft, CLOSE_FIELDS, RESPONDER
    )

    assert out["canonical_id"] is None
    assert "reason" in out and out["reason"]
    assert mock_mcp.write_log.entries == write_log_before
