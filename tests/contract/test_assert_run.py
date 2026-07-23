"""Contract tests for the scenario assertion script (test-plan B-4).

``assert_run.py`` is the judge every Tier 2 verdict trusts, so it is tested
like any other instrument (Constitution VIII): against hand-authored state
files describing a known-good run and seven deliberate corruptions of it —
each corruption must fail exactly the check that owns that invariant.

Hermetic: no live session, no stdio server — the state dict and workspace are
built in tmp_path, and the script's helpers are driven as pure functions.
"""

import json
import os
import sys

import pytest

from conftest import TESTS_DIR, load_fixture

SCENARIOS_DIR = os.path.join(str(TESTS_DIR), "scenarios")
if SCENARIOS_DIR not in sys.path:
    sys.path.insert(0, SCENARIOS_DIR)

import assert_run  # noqa: E402

SESSION_ID = "page-ALERT-123-2026-07-23"
FINGERPRINT = "1e53817cc27fbd48"  # bb-fingerprint("checkout", "HighLatency p99")


# --------------------------------------------------------------------------- #
# builders — one known-good run, corrupted per test
# --------------------------------------------------------------------------- #
def good_verdict():
    doc = load_fixture("validate", "valid-verdict.json")["document"]
    return dict(doc, session_id=SESSION_ID)


def good_state():
    seeded = {
        "session_id": "page-ALERT-777-2026-06-20",
        "status": "closed",
        "fingerprint": FINGERPRINT,
    }
    row = {
        "session_id": SESSION_ID,
        "session_type": "page",
        "status": "closed",
        "fingerprint": FINGERPRINT,
        "triage_verdict": json.dumps(good_verdict()),  # cells hold JSON text
        "diary_url": "diary://2",
    }
    return {
        "records": [seeded, row],
        "write_log": [
            {"seq": 1, "capability": "storage", "op": "append_record",
             "summary": "session_id={}".format(SESSION_ID)},
            {"seq": 2, "capability": "diary", "op": "append_entry",
             "summary": "-> diary://2"},
            {"seq": 3, "capability": "storage", "op": "update_record",
             "summary": "session_id={} fields={}".format(
                 SESSION_ID, sorted(["status", "closed_at", "diary_url"]))},
        ],
    }


def good_workspace(tmp_path):
    bb = tmp_path / ".bb-session"
    bb.mkdir()
    (bb / "trace.jsonl").write_text(
        "\n".join(json.dumps({"seq": i, "tool": "t"}) for i in (1, 2, 3)) + "\n")
    # no marker.json: a confirmed close deleted it (D-11 cleared state)
    return str(tmp_path)


def scenario():
    return assert_run.load_scenario("known-issue")


def by_id(checks):
    return {c["id"]: c for c in checks}


# --------------------------------------------------------------------------- #
# the known-good run passes everything
# --------------------------------------------------------------------------- #
def test_good_run_passes_every_check(tmp_path):
    checks = assert_run.run_checks(good_state(), good_workspace(tmp_path), scenario())
    failed = [c for c in checks if not c["pass"]]
    assert failed == [], failed
    # ledger-anchored is skipped (triage-only run, optional for this scenario)
    assert by_id(checks)["ledger-anchored"].get("skipped") is True


# --------------------------------------------------------------------------- #
# each corruption fails exactly its own check
# --------------------------------------------------------------------------- #
def test_missing_session_row_is_the_first_and_only_failure(tmp_path):
    state = good_state()
    state["records"] = state["records"][:1]  # only the seeded prior remains
    checks = assert_run.run_checks(state, good_workspace(tmp_path), scenario())
    assert len(checks) == 1
    assert checks[0]["id"] == "session-row-present" and not checks[0]["pass"]


def test_invalid_verdict_fails_checkpoint_zero(tmp_path):
    state = good_state()
    bad = good_verdict()
    bad["candidates"][0]["evidence"] = [{"excerpt": "prose only, no url"}]
    state["records"][1]["triage_verdict"] = json.dumps(bad)
    checks = by_id(assert_run.run_checks(state, good_workspace(tmp_path), scenario()))
    assert not checks["checkpoint-zero-valid"]["pass"]
    assert "bb-validate" in checks["checkpoint-zero-valid"]["expected"]


def test_wrong_fingerprint_fails_with_both_values_named(tmp_path):
    state = good_state()
    state["records"][1]["fingerprint"] = "deadbeefdeadbeef"
    checks = by_id(assert_run.run_checks(state, good_workspace(tmp_path), scenario()))
    c = checks["fingerprint-correct"]
    assert not c["pass"]
    assert c["expected"] == FINGERPRINT and c["actual"] == "deadbeefdeadbeef"


def test_unvalidated_recall_candidate_fails_recall_validated(tmp_path):
    state = good_state()
    verdict = good_verdict()
    del verdict["candidates"][0]["validation"]  # provenance: recall, unmarked
    state["records"][1]["triage_verdict"] = json.dumps(verdict)
    checks = by_id(assert_run.run_checks(state, good_workspace(tmp_path), scenario()))
    assert not checks["recall-validated"]["pass"]


def test_row_update_before_diary_fails_write_ordering(tmp_path):
    state = good_state()
    log = state["write_log"]
    log[1]["seq"], log[2]["seq"] = 3, 2  # close update now precedes diary write
    checks = by_id(assert_run.run_checks(state, good_workspace(tmp_path), scenario()))
    assert not checks["diary-before-row"]["pass"]


def test_missing_close_update_fails_write_ordering(tmp_path):
    state = good_state()
    state["write_log"] = state["write_log"][:2]  # diary written, row never updated
    checks = by_id(assert_run.run_checks(state, good_workspace(tmp_path), scenario()))
    assert not checks["diary-before-row"]["pass"]


def test_underanchored_ledger_fails_when_present(tmp_path):
    state = good_state()
    ledger = {
        "schema": "bb.ledger.v1", "seq": 2, "phase": "deep-dive",
        "hypotheses": [
            {"id": "h1", "status": "live", "provenance": "triage",
             "validation": "VALIDATED"},
            {"id": "h2", "status": "live", "provenance": "recall",
             "validation": "INVALIDATED"},
        ],
    }
    state["records"][1]["latest_checkpoint"] = json.dumps(ledger)
    checks = by_id(assert_run.run_checks(state, good_workspace(tmp_path), scenario()))
    c = checks["ledger-anchored"]
    assert not c["pass"] and "2 live, 0 fresh" in c["actual"]


def test_anchored_ledger_passes(tmp_path):
    state = good_state()
    ledger = {
        "schema": "bb.ledger.v1", "seq": 2, "phase": "deep-dive",
        "hypotheses": [
            {"id": "h1", "status": "live", "provenance": "triage",
             "validation": "VALIDATED"},
            {"id": "h2", "status": "live", "provenance": "fresh"},
            {"id": "h3", "status": "live", "provenance": "fresh"},
        ],
    }
    state["records"][1]["latest_checkpoint"] = json.dumps(ledger)
    checks = by_id(assert_run.run_checks(state, good_workspace(tmp_path), scenario()))
    c = checks["ledger-anchored"]
    assert c["pass"] and not c.get("skipped")
    # the ledger's non-fresh hypotheses also feed recall-validated
    assert checks["recall-validated"]["pass"]


def test_missing_trace_fails_trace_captured(tmp_path):
    workspace = good_workspace(tmp_path)
    os.unlink(os.path.join(workspace, ".bb-session", "trace.jsonl"))
    checks = by_id(assert_run.run_checks(good_state(), workspace, scenario()))
    assert not checks["trace-captured"]["pass"]


def test_nonmonotonic_trace_seq_fails_trace_captured(tmp_path):
    workspace = good_workspace(tmp_path)
    path = os.path.join(workspace, ".bb-session", "trace.jsonl")
    with open(path, "w") as f:
        for seq in (1, 3, 2):
            f.write(json.dumps({"seq": seq}) + "\n")
    checks = by_id(assert_run.run_checks(good_state(), workspace, scenario()))
    assert not checks["trace-captured"]["pass"]


def test_lingering_marker_fails_marker_cleared(tmp_path):
    workspace = good_workspace(tmp_path)
    marker = os.path.join(workspace, ".bb-session", "marker.json")
    with open(marker, "w") as f:
        json.dump({"session_id": SESSION_ID, "open_write_confirmed": True}, f)
    checks = by_id(assert_run.run_checks(good_state(), workspace, scenario()))
    assert not checks["marker-cleared"]["pass"]


# --------------------------------------------------------------------------- #
# staged-checkpoint fallback
# --------------------------------------------------------------------------- #
def test_ledger_read_from_staging_when_cell_holds_overflow(tmp_path):
    workspace = good_workspace(tmp_path)
    state = good_state()
    state["records"][1]["latest_checkpoint"] = json.dumps(
        {"overflow": "art://9", "seq": 4})  # not a ledger document
    staging = os.path.join(workspace, ".bb-session", "staging")
    os.makedirs(staging)
    ledger = {
        "schema": "bb.ledger.v1", "seq": 4, "phase": "deep-dive",
        "hypotheses": [
            {"id": "h1", "status": "live", "provenance": "fresh"},
            {"id": "h2", "status": "live", "provenance": "fresh"},
            {"id": "h3", "status": "live", "provenance": "triage",
             "validation": "VALIDATED"},
        ],
    }
    with open(os.path.join(staging, "checkpoints.jsonl"), "w") as f:
        f.write(json.dumps(ledger) + "\n")
    checks = by_id(assert_run.run_checks(state, workspace, scenario()))
    assert checks["ledger-anchored"]["pass"]


# --------------------------------------------------------------------------- #
# CLI surface
# --------------------------------------------------------------------------- #
def test_main_exits_zero_on_a_good_run(tmp_path, capsys):
    workspace = good_workspace(tmp_path)
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(good_state()))
    rc = assert_run.main(["--state", str(state_path), "--workspace", workspace])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["failed"] == 0
    assert {c["id"] for c in report["checks"]} >= {
        "checkpoint-zero-valid", "fingerprint-correct", "recall-validated",
        "diary-before-row", "ledger-anchored", "trace-captured", "marker-cleared"}


def test_main_exits_one_and_names_the_artifact_on_failure(tmp_path, capsys):
    workspace = good_workspace(tmp_path)
    state = good_state()
    state["records"][1]["fingerprint"] = "deadbeefdeadbeef"
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state))
    rc = assert_run.main(["--state", str(state_path), "--workspace", workspace])
    assert rc == 1
    out = capsys.readouterr()
    report = json.loads(out.out)
    failing = [c for c in report["checks"] if not c["pass"]]
    assert [c["id"] for c in failing] == ["fingerprint-correct"]
    assert failing[0]["artifact"] == "row.fingerprint"
    assert "FAIL fingerprint-correct" in out.err


def test_main_exits_two_on_unreadable_state(tmp_path, capsys):
    rc = assert_run.main(["--state", str(tmp_path / "nope.json"),
                          "--workspace", str(tmp_path)])
    assert rc == 2
    assert "assert_run:" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# fixture-bundle integrity
# --------------------------------------------------------------------------- #
def test_known_issue_fixture_is_internally_consistent(mock_mcp):
    """The seed loads, the seeded fingerprint matches the scenario's declared
    inputs, and the bindings name exactly the server's default tools."""
    import subprocess

    scen = scenario()
    fixture_dir = os.path.join(SCENARIOS_DIR, "fixtures", "known-issue")
    mock_mcp.load_seed(os.path.join(fixture_dir, "seed.json"))
    seeded = {r["session_id"] for r in mock_mcp.records.records}
    assert seeded == set(scen["seeded_session_ids"])

    proc = subprocess.run(
        [sys.executable, os.path.join(assert_run.BIN_DIR, "bb-fingerprint"),
         scen["service"], scen["alert_type"]],
        stdout=subprocess.PIPE)
    fp = json.loads(proc.stdout)["fingerprint"]
    assert mock_mcp.records.records[0]["fingerprint"] == fp

    with open(os.path.join(fixture_dir, "bindings.json"), encoding="utf-8") as f:
        bindings = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    sys.path.insert(0, str(assert_run.REPO_ROOT + "/tools/bb-mock-mcp"))
    import server as mock_server
    assert set(bindings.values()) <= set(mock_server.DEFAULT_NAMES)
    for op_ref, tool in bindings.items():
        assert mock_server.DEFAULT_NAMES[tool] == op_ref
