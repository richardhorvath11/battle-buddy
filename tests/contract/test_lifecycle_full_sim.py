"""SC-007 full open->close simulation (spec FR-001..FR-013, SC-007; contracts/
lifecycle-protocol.md end to end; Constitution VIII) -- T020 (Polish).

Composes the full ``/page`` open -> mid-session checkpoint -> ``/incident``
promotion -> ``/close`` sequence in one hermetic run against ``bb-mock-mcp``,
re-checking the load-bearing artifact assertions each story suite already
proves in isolation (marker lifecycle, checkpoint-zero-rides-the-append,
briefing evidence, dual-write ordering, artifact/timeline shape, read-back-
gated deletion, shell close-last) -- never re-deriving new invariants, only
proving they still hold when the flows run back-to-back over the same local
state directory and store. Join-vs-separate, merge-at-close, and ownership
displacement are each already exercised end to end in their own dedicated
suites (``test_join_separate.py``, ``test_close_merge_ownership.py``) and are
deliberately not re-run here (T020's scope is the single-session open->close
spine, per tasks.md).

**Contract-boundary mechanism (FR-012/SC-007's "zero operations outside the
operation contract")**: ``bb_mock_mcp.MockMcp.invoke()`` already rejects any
``(capability, op)`` pair absent from ``contract.json`` *before* dispatch --
``schema_registry.operation(capability, op) is None`` short-circuits straight
to an ``{"error": {"code": "unknown_op", ...}}`` envelope, and the pair never
reaches the dispatch table (``tools/bb-mock-mcp/bb_mock_mcp/__init__.py``
``invoke()``). So the contract-boundary property doesn't need a second,
independent enforcement mechanism -- it needs *visibility* into every call
the simulation made, reads included (the write log alone only records
mutating ops that successfully dispatched; reads and rejected calls are
invisible to it). ``_AllOpsRecorder`` below wraps the mock and records every
``invoke()`` call (capability, op, result) in call order; every other
attribute (``alerting``, ``artifacts``, ``write_log``, ``schema_registry``,
...) forwards straight to the wrapped mock so seeding/inspection works
exactly as it would against a bare ``MockMcp``. The end-of-sim assertion then
checks, for every recorded call: (a) ``schema_registry.operation(capability,
op)`` resolves (the op is genuinely in the contract) and (b) the call's own
result never carries ``error.code == "unknown_op"`` -- belt-and-suspenders on
the *same* mechanism, not two independent checks.
"""

import json

from conftest import fixture_path
from helpers import (
    doctor_fixtures,
    doctor_flows,
    lifecycle_fixtures,
    lifecycle_flows,
    store_flows,
)

PLUGIN_VERSION = "0.4.0"
AT = "2026-07-21T08:00:00Z"

_ROSTER_TEXT = json.dumps(
    {
        "mcpServers": {
            "mycorp_sheets": {
                "command": "npx",
                "args": ["-y", "@mycorp-sheets/mcp-server"],
                "env": {"MYCORP_SHEETS_TOKEN": "${MYCORP_SHEETS_TOKEN}"},
            }
        }
    }
)

CATALOG = lifecycle_fixtures.load_catalog()

ALERT = {
    "alert_id": "ALERT-123",
    "service_hint": "checkout",
    "description": "checkout latency spike",
    "fired_at": "2026-07-21T09:10:00+00:00",
}

STARTED_AT = "2026-07-21T09:14:00+00:00"
RESPONDER = "alice @ {}".format(STARTED_AT)

CAUSAL_PROPOSALS = dict(
    root_cause="deploy rollback race",
    contributing_factors=["insufficient canary bake time"],
    action_items=["extend canary window to 15m"],
)

CLOSE_FIELDS = dict(
    status="closed",
    closed_at="2026-07-21T10:30:00+00:00",
    root_cause="deploy rollback race",
    resolution="rolled back to previous revision",
    runbook_refs=[],
    report_url=None,
)


class _AllOpsRecorder:
    """See the module docstring's "Contract-boundary mechanism" note. Wraps a
    ``MockMcp`` instance, logging every ``invoke()`` call (reads and writes
    alike) in order so the whole simulation's operation surface can be
    checked against the contract at the end -- not just the mutating write
    log, which is blind to reads and to any call that never reaches
    dispatch."""

    def __init__(self, mock):
        self._mock = mock
        self.calls = []

    def invoke(self, capability, op, payload=None):
        result = self._mock.invoke(capability, op, payload)
        self.calls.append({"capability": capability, "op": op, "result": result})
        return result

    def describe(self):
        return self._mock.describe()

    def __getattr__(self, name):
        # Anything not defined on the recorder itself (schema_registry,
        # write_log, alerting, artifacts, diary, records, ...) passes
        # through to the wrapped mock, exactly as
        # lifecycle_fixtures.TransientFaultInjector does for its own
        # wrap-and-pass-through shape.
        return getattr(self._mock, name)


def _assert_every_call_is_a_contract_op(recorder):
    """FR-012/SC-007: zero operations outside the operation contract."""
    assert recorder.calls  # a vacuous pass (no calls at all) would prove nothing
    for entry in recorder.calls:
        capability, op = entry["capability"], entry["op"]
        assert recorder.schema_registry.operation(capability, op) is not None, (
            "{}.{} is not an operation-contract-v1 op".format(capability, op)
        )
        result = entry["result"]
        if isinstance(result, dict) and "error" in result:
            assert result["error"].get("code") != "unknown_op", (
                "{}.{} returned unknown_op -- outside the operation "
                "contract".format(capability, op)
            )


def _fresh_stamp(tmp_path):
    """A stamp file matching PLUGIN_VERSION/roster hash exactly -- built with
    the real ``doctor_flows.write_stamp``, mirroring
    ``test_page_preflight.py``'s own helper."""
    roster_hash_value = doctor_flows.roster_hash(_ROSTER_TEXT)
    stamp_path = tmp_path / ".bb-doctor-stamp.json"
    doctor_flows.write_stamp(stamp_path, PLUGIN_VERSION, roster_hash_value, AT)
    return stamp_path, roster_hash_value


def _ops_from(mock, start):
    return [(e["capability"], e["op"]) for e in mock.write_log.entries[start:]]


def _load_valid_ledger_document():
    """A real ``bb.ledger.v1`` document that genuinely passes ``bb_validate``
    (task T020: "valid ledger fixture from tests/fixtures/validate/
    valid-ledger-*.json") -- the mid-session (seq 1) checkpoint's candidate
    for ``store_flows.write_checkpoint``. The fixture file wraps the document
    under a ``"document"`` key alongside a validator-harness ``name``/
    ``expected_rules`` (tests/unit/test_validate.py's own shape); only the
    document itself is what ``write_checkpoint`` (and ``bb_validate``)
    consume."""
    path = fixture_path("validate", "valid-ledger-deep-dive.json")
    with open(str(path), encoding="utf-8") as f:
        fixture = json.load(f)
    return fixture["document"]


def _run_full_sim(mock_mcp, tmp_path, shell):
    """Executes preflight -> open -> mid-session checkpoint -> promotion ->
    draft -> close exactly once, threading ``shell`` (an adapter instance or
    ``None`` for degraded mode) through both the open and the close call --
    the same adapter instance a real single session would hold open
    throughout. Returns every intermediate outcome the two test functions
    below assert against."""
    recorder = _AllOpsRecorder(mock_mcp)
    state_dir = tmp_path / "session"

    # --- Preflight: valid config + a fresh stamp -> zero probes, proceed. --
    stamp_path, roster_hash_value = _fresh_stamp(tmp_path)
    config = doctor_fixtures.load_config_fixture("config-valid.json")
    preflight_result = lifecycle_flows.preflight(
        config=config,
        state_dir=state_dir,
        stamp_path=stamp_path,
        plugin_version=PLUGIN_VERSION,
        current_roster_hash=roster_hash_value,
    )
    assert preflight_result["proceed"] is True
    assert preflight_result["responder_mode_ran"] is False
    assert not state_dir.exists()  # preflight creates no session artifacts

    # --- Open (/page ALERT-123): marker, checkpoint zero, briefing. --------
    mock_mcp.alerting.alerts[ALERT["alert_id"]] = dict(ALERT)
    verdict = lifecycle_fixtures.load_verdict("valid-known-issue")

    open_segment_start = len(mock_mcp.write_log.entries)
    open_out = lifecycle_flows.open_command(
        recorder,
        state_dir,
        "page",
        ALERT["alert_id"],
        "2026-07-21",
        STARTED_AT,
        RESPONDER,
        [verdict],
        CATALOG,
        shell=shell,
    )
    session_id = open_out["session_id"]

    # Captured immediately -- every step below (checkpoint, promotion, close)
    # appends further to mock_mcp.write_log, so a segment slice or an
    # on-disk read that means "just this stage" must be taken right here,
    # not after the whole chain finishes (close deletes the state_dir
    # outright on a confirmed marker clearance).
    open_ops = _ops_from(mock_mcp, open_segment_start)
    marker_after_open = json.loads((state_dir / "marker.json").read_text(encoding="utf-8"))
    history_path = state_dir / "staging" / "checkpoints.jsonl"
    history_after_open = [
        json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines()
    ]

    # --- Mid-session checkpoint (seq 1) via store_flows.write_checkpoint. --
    ledger_document = _load_valid_ledger_document()
    checkpoint_out = store_flows.write_checkpoint(
        recorder, state_dir, session_id, [ledger_document], RESPONDER, seq=1
    )

    # --- Promotion (/incident inside the already-open page session). ------
    promote_segment_start = len(mock_mcp.write_log.entries)
    promote_out = lifecycle_flows.promote_session(recorder, state_dir)
    promote_ops = _ops_from(mock_mcp, promote_segment_start)  # captured now, see note above

    row_after_promotion = recorder.invoke(
        "storage", "read_records", {"filter": {"session_id": session_id}}
    )["records"][0]

    # --- Timeline inputs: a fixture trace.jsonl alongside the two
    # checkpoint-history lines already on disk (seq 0 from open, seq 1 from
    # the mid-session checkpoint above). ---
    call_lines = lifecycle_fixtures.write_trace_fixture(state_dir)
    timeline = lifecycle_flows.derive_timeline(state_dir)

    # --- Draft + approve. ---------------------------------------------------
    row_for_draft = dict(row_after_promotion, closed_at=CLOSE_FIELDS["closed_at"])
    draft = lifecycle_flows.draft_close(recorder, {}, row_for_draft, timeline, CAUSAL_PROPOSALS)
    draft["approved"] = True

    # --- Close (the last flow call -- nothing further is written to
    # mock_mcp.write_log after this, so close_ops needs no inline capture). --
    close_segment_start = len(mock_mcp.write_log.entries)
    close_out = lifecycle_flows.close_command(
        recorder,
        state_dir,
        str(lifecycle_fixtures.TRANSCRIPT_PATH),
        draft,
        CLOSE_FIELDS,
        RESPONDER,
        shell=shell,
    )
    close_ops = _ops_from(mock_mcp, close_segment_start)

    return {
        "recorder": recorder,
        "state_dir": state_dir,
        "session_id": session_id,
        "open_out": open_out,
        "open_ops": open_ops,
        "marker_after_open": marker_after_open,
        "history_after_open": history_after_open,
        "checkpoint_out": checkpoint_out,
        "promote_out": promote_out,
        "promote_ops": promote_ops,
        "row_after_promotion": row_after_promotion,
        "call_lines": call_lines,
        "timeline": timeline,
        "draft": draft,
        "close_out": close_out,
        "close_ops": close_ops,
    }


# ---------------------------------------------------------------------------
# The full simulation, shell-configured: preflight -> open -> checkpoint ->
# promotion -> draft -> close, re-checking every story suite's load-bearing
# artifact assertion end to end, plus the contract-boundary property.
# ---------------------------------------------------------------------------


def test_full_open_checkpoint_promote_close_simulation(mock_mcp, tmp_path):
    shell = lifecycle_fixtures.RecordingShellAdapter()
    result = _run_full_sim(mock_mcp, tmp_path, shell)

    state_dir = result["state_dir"]
    session_id = result["session_id"]
    open_out = result["open_out"]

    # --- Open invariants -----------------------------------------------------
    assert session_id == "page-ALERT-123-2026-07-21"

    # Marker: created unconfirmed, confirmed only after the open-time
    # append's read-back (FR-002). Read at open time -- close deletes the
    # whole state_dir on a confirmed marker clearance (see _run_full_sim).
    marker = result["marker_after_open"]
    assert marker["open_write_confirmed"] is True
    assert marker["session_id"] == session_id
    assert open_out["readback_confirmed"] is True

    # Row landed, status open; checkpoint zero rides the append (R2) --
    # exactly one append_record in this segment, no update_record.
    assert result["open_ops"] == [("storage", "append_record")]
    assert open_out["row"]["status"] == "open"
    assert open_out["row"]["session_id"] == session_id
    assert open_out["verdict_valid"] is True
    assert open_out["verdict_overflowed"] is False

    # Checkpoint zero: exactly one history line, seq 0, matching the
    # verdict's own session_id field.
    verdict = lifecycle_fixtures.load_verdict("valid-known-issue")
    assert [line["seq"] for line in result["history_after_open"]] == [0]
    assert result["history_after_open"][0]["document"]["session_id"] == verdict["session_id"]

    # Briefing evidence: every claim carries >=1 non-empty {url, excerpt}
    # pair (Constitution IV); shell configured -> exactly one navigate_pane
    # to the top-cited dashboard.
    briefing = open_out["briefing"]
    assert briefing["claims"]
    for claim in briefing["claims"]:
        assert claim["evidence"]
        for entry in claim["evidence"]:
            assert entry["url"].strip()
            assert entry["excerpt"].strip()
    assert briefing["top_cited_dashboard"] is not None
    nav_calls = [c for c in shell.calls if c["method"] == "navigate_pane"]
    assert len(nav_calls) == 1
    assert nav_calls[0]["url"] == briefing["top_cited_dashboard"]

    # --- Mid-session checkpoint invariants -----------------------------------
    checkpoint_out = result["checkpoint_out"]
    assert checkpoint_out["written"] is True
    assert checkpoint_out["schema_valid"] is True
    assert checkpoint_out["overflowed"] is False
    assert checkpoint_out["cell"] == "latest_checkpoint"
    assert checkpoint_out["history_line_count"] == 2

    # --- Promotion invariants (update, not append -- SC-003) -----------------
    promote_out = result["promote_out"]
    assert promote_out["session_id"] == session_id
    assert promote_out["retagged"] is True
    assert promote_out["deep_launched"] is True
    assert result["promote_ops"] == [("storage", "update_record")]
    assert ("storage", "append_record") not in result["promote_ops"]

    row_after_promotion = result["row_after_promotion"]
    assert row_after_promotion["session_type"] == "incident"
    assert row_after_promotion["responder"] == RESPONDER  # untouched by promotion

    # --- Timeline: 1:1 over the trace call lines + the two checkpoint
    # history entries (seq 0, seq 1) -- never the transcript. ---
    call_line_count = sum(1 for line in result["call_lines"] if "event" not in line)
    timeline = result["timeline"]
    assert len(timeline) == call_line_count + checkpoint_out["history_line_count"]
    assert all(event["source"] in ("trace", "checkpoint") for event in timeline)
    for event in timeline:
        assert "transcript" not in json.dumps(event)

    # --- Draft invariants (SC-006): causal values only under proposals.*. ---
    draft = result["draft"]
    for key in ("root_cause", "contributing_factors", "action_items"):
        assert draft["proposals"][key]["proposal"] is True
        assert draft["proposals"][key]["value"] == CAUSAL_PROPOSALS[key]
    assert set(CAUSAL_PROPOSALS).isdisjoint(draft["factual"])
    assert draft["approved"] is True

    # --- Close invariants (AS-1, AS-6, SC-005) --------------------------------
    close_out = result["close_out"]
    close_ops = result["close_ops"]
    assert close_ops[0] == ("diary", "append_entry")
    assert close_ops[-1] == ("storage", "update_record")
    put_positions = [i for i, op in enumerate(close_ops) if op == ("artifacts", "put_file")]
    assert len(put_positions) == 4  # transcript, trace, checkpoints, report
    update_position = close_ops.index(("storage", "update_record"))
    assert all(0 < i < update_position for i in put_positions)

    uploaded = close_out["uploaded"]
    assert uploaded["staging/transcript.md"]["uploaded_name"] == "transcript.md"
    assert uploaded["trace.jsonl"]["uploaded_name"] == "tool-trace.jsonl"
    assert uploaded["staging/checkpoints.jsonl"]["uploaded_name"] == "checkpoints.jsonl"
    assert uploaded["report.md"]["uploaded_name"] == "report.md"

    assert close_out["timeline"] == timeline  # close_command's own derivation agrees

    assert close_out["diary_link"] is not None
    assert close_out["diary_pending"] is False
    recorder = result["recorder"]
    final_row = recorder.invoke(
        "storage", "read_records", {"filter": {"session_id": session_id}}
    )["records"][0]
    assert final_row["status"] == "closed"
    assert final_row["diary_url"] == close_out["diary_link"]
    assert final_row["links"]
    for link in final_row["links"]:
        assert link["url"] and link["excerpt"]

    # Marker + state dir gone only on confirmed read-back -- deletion IS the
    # cleared state (local-state protocol v1).
    assert close_out["readback_confirmed"] is True
    assert close_out["marker_cleared"] is True
    assert not state_dir.exists()

    # Shell close called last.
    assert shell.calls[-1] == {
        "method": "close_workspace",
        "session_id": close_out["canonical_id"],
    }

    # --- FR-012/SC-007: every operation invoked across the whole simulation
    # (reads and writes alike) is an operation-contract-v1 op. ---
    _assert_every_call_is_a_contract_op(recorder)


# ---------------------------------------------------------------------------
# The same full simulation, degraded (no shell adapter): completes with
# printed records in place of adapter calls, at both open and close.
# ---------------------------------------------------------------------------


def test_full_simulation_degraded_no_shell(mock_mcp, tmp_path):
    result = _run_full_sim(mock_mcp, tmp_path, shell=None)

    open_out = result["open_out"]
    close_out = result["close_out"]

    # No adapter to have called at all, at either end of the session.
    assert open_out["shell_calls"] is None
    assert close_out["shell_calls"] is None

    # Open-time: workspace-pane-open printed, briefing degraded with the
    # top-cited dashboard printed instead of navigated.
    assert any(
        result["session_id"] in entry["text"]
        for entry in open_out["printed"]
        if entry["kind"] == "message"
    )
    briefing = open_out["briefing"]
    assert briefing["degraded"] is True
    assert briefing["top_cited_dashboard"] is not None  # same fixture verdict as test 1
    assert briefing["printed_links"] == [briefing["top_cited_dashboard"]]

    # Close-time: close_workspace printed instead of called through an
    # adapter.
    assert any(
        "close workspace" in entry.get("text", "") for entry in close_out["printed"]
    )

    # The flow still completes fully despite the missing adapter throughout
    # (full function, no shell -- Constitution VII/FR-006/FR-011).
    assert open_out["readback_confirmed"] is True
    assert result["checkpoint_out"]["written"] is True
    assert result["promote_out"]["retagged"] is True
    assert close_out["readback_confirmed"] is True
    assert close_out["marker_cleared"] is True
    assert not result["state_dir"].exists()

    # The contract-boundary property holds in degraded mode too -- the
    # missing shell adapter changes nothing about the mock's operation
    # surface.
    _assert_every_call_is_a_contract_op(result["recorder"])
