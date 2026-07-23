#!/usr/bin/env python3
"""Scenario assertion script (test-plan B-4; design §10).

Judges a finished interactive run by its artifacts — never its prose. Reads the
state file the bb-mock-mcp stdio server persisted (``--state``) plus the local
session droppings (``--workspace``/.bb-session/), runs the structural checks
below, and exits 0 only if every enabled check passes.

The checks are design §10's five plus the two slice 2 unlocked:

  1. checkpoint-zero-valid   row's triage_verdict passes bin/bb-validate
  2. fingerprint-correct     row fingerprint == bb-fingerprint(service, alert_type)
  3. recall-validated        every non-fresh hypothesis/candidate carries
                             VALIDATED/INVALIDATED (Constitution VI; SM-4)
  4. diary-before-row        write_log: diary.append_entry precedes the
                             close-time storage.update_record (FR-4b)
  5. ledger-anchored         >=3 live hypotheses, >=1 fresh (Constitution VI)
  6. trace-captured          .bb-session/trace.jsonl exists, seqs strictly
                             increasing (D-12)
  7. marker-cleared          session marker deleted by a confirmed close (D-11)

Model output varies run to run; these structural invariants must not. Output:
one JSON report on stdout (machine-readable, artifact-anchored), a human
summary on stderr, exit 0 all-pass / 1 any-fail / 2 usage error.

Dev tooling — never shipped (Constitution I; the packaging test fences
``tests/``). Python 3.9-compatible, stdlib only, reusing the *shipped*
``bin/bb-validate`` and ``bin/bb-fingerprint`` as subprocesses so the harness
judges with exactly the implementations responders get.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

SCENARIOS_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(SCENARIOS_DIR))
BIN_DIR = os.path.join(REPO_ROOT, "bin")

VALIDATED_SET = ("VALIDATED", "INVALIDATED")


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #
def load_scenario(name_or_path):
    """A scenario config: from fixtures/<name>/scenario.json or a direct path."""
    path = name_or_path
    if not os.path.isfile(path):
        path = os.path.join(SCENARIOS_DIR, "fixtures", name_or_path, "scenario.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_session_row(records, scenario):
    """The scenario session's row: session_id embeds the source ID (D-8) and is
    not a pre-seeded row. Latest match wins (join/open-separately can leave
    more than one; the run under judgment is the last append)."""
    source_id = scenario["source_id"]
    seeded = set(scenario.get("seeded_session_ids", []))
    matches = [
        r for r in records
        if source_id in r.get("session_id", "") and r.get("session_id") not in seeded
    ]
    return matches[-1] if matches else None


def as_document(value):
    """A checkpoint field as a dict: cells may hold JSON text or a real map."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return None
    return value if isinstance(value, dict) else None


def run_helper(helper, argv_tail):
    """Run a shipped bin/ helper; returns (exit_code, stdout)."""
    proc = subprocess.run(
        [sys.executable, os.path.join(BIN_DIR, helper)] + argv_tail,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


# --------------------------------------------------------------------------- #
# checks — each returns {id, pass, artifact, expected, actual}
# --------------------------------------------------------------------------- #
def _check(check_id, passed, artifact, expected, actual):
    return {"id": check_id, "pass": bool(passed), "artifact": artifact,
            "expected": expected, "actual": actual}


def _skip(check_id, why):
    return {"id": check_id, "pass": True, "skipped": True, "artifact": None,
            "expected": None, "actual": why}


def check_checkpoint_zero_valid(row):
    verdict = as_document(row.get("triage_verdict"))
    if verdict is None:
        return _check("checkpoint-zero-valid", False, "row.triage_verdict",
                      "a bb.verdict.v1 document", "absent or unparseable")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(verdict, f)
        path = f.name
    try:
        code, out = run_helper("bb-validate", [path])
    finally:
        os.unlink(path)
    return _check("checkpoint-zero-valid", code == 0, "row.triage_verdict",
                  "bb-validate exit 0", "exit {}: {}".format(code, out.strip()[:300]))


def check_fingerprint_correct(row, scenario):
    code, out = run_helper(
        "bb-fingerprint", [scenario["service"], scenario["alert_type"]])
    if code != 0:
        return _check("fingerprint-correct", False, "row.fingerprint",
                      "bb-fingerprint exit 0", "exit {}".format(code))
    expected = json.loads(out)["fingerprint"]
    actual = row.get("fingerprint")
    return _check("fingerprint-correct", actual == expected, "row.fingerprint",
                  expected, actual)


def _unvalidated(items, provenance_key="provenance"):
    """Non-fresh entries lacking a VALIDATED/INVALIDATED mark."""
    bad = []
    for item in items:
        if item.get(provenance_key, "fresh") == "fresh":
            continue
        if item.get("validation") not in VALIDATED_SET:
            bad.append(item.get("id") or item.get("statement", "?")[:40])
    return bad


def check_recall_validated(row):
    verdict = as_document(row.get("triage_verdict")) or {}
    bad = _unvalidated(verdict.get("candidates", []))
    known = verdict.get("known_issue")
    if isinstance(known, dict) and known.get("validation") not in VALIDATED_SET:
        bad.append("known_issue")
    ledger = as_document(row.get("latest_checkpoint"))
    if ledger and ledger.get("schema") == "bb.ledger.v1":
        bad.extend(_unvalidated(ledger.get("hypotheses", [])))
    return _check("recall-validated", not bad,
                  "verdict.candidates / known_issue / ledger.hypotheses",
                  "every non-fresh entry marked VALIDATED or INVALIDATED",
                  "unvalidated: {}".format(bad) if bad else "all marked")


def check_diary_before_row(write_log, session_id):
    """The dual-write order (FR-4b): the diary append must precede the
    close-time row update — identified as an update_record on this session
    whose summary names the diary_url field."""
    diary_seqs = [e["seq"] for e in write_log
                  if e["capability"] == "diary" and e["op"] == "append_entry"]
    close_seqs = [
        e["seq"] for e in write_log
        if e["capability"] == "storage" and e["op"] == "update_record"
        and "session_id={}".format(session_id) in e["summary"]
        and "diary_url" in e["summary"]
    ]
    if not diary_seqs or not close_seqs:
        return _check("diary-before-row", False, "state.write_log",
                      "one diary.append_entry and one close-time update_record "
                      "carrying diary_url",
                      "diary seqs {}, close seqs {}".format(diary_seqs, close_seqs))
    return _check("diary-before-row", max(diary_seqs) < min(close_seqs),
                  "state.write_log",
                  "diary.append_entry seq < close update_record seq",
                  "diary {} vs close {}".format(max(diary_seqs), min(close_seqs)))


def check_ledger_anchored(row, workspace, optional):
    ledger = as_document(row.get("latest_checkpoint"))
    if not ledger or ledger.get("schema") != "bb.ledger.v1":
        ledger = _last_staged_ledger(workspace)
    if not ledger:
        if optional:
            return _skip("ledger-anchored",
                         "no ledger checkpoint (triage-only run); check optional "
                         "for this scenario")
        return _check("ledger-anchored", False, "row.latest_checkpoint",
                      "a bb.ledger.v1 checkpoint", "absent")
    hyps = ledger.get("hypotheses", [])
    live = [h for h in hyps if h.get("status") == "live"]
    fresh = [h for h in live if h.get("provenance") == "fresh"]
    ok = len(live) >= 3 and len(fresh) >= 1
    return _check("ledger-anchored", ok, "ledger.hypotheses",
                  ">=3 live and >=1 fresh",
                  "{} live, {} fresh".format(len(live), len(fresh)))


def _last_staged_ledger(workspace):
    path = os.path.join(workspace, ".bb-session", "staging", "checkpoints.jsonl")
    if not os.path.isfile(path):
        return None
    last = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
            except ValueError:
                continue
            if isinstance(doc, dict) and doc.get("schema") == "bb.ledger.v1":
                last = doc
    return last


def check_trace_captured(workspace):
    path = os.path.join(workspace, ".bb-session", "trace.jsonl")
    if not os.path.isfile(path):
        return _check("trace-captured", False, ".bb-session/trace.jsonl",
                      "hook-captured trace present", "file absent")
    seqs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                seqs.append(json.loads(line)["seq"])
            except (ValueError, KeyError, TypeError):
                return _check("trace-captured", False, ".bb-session/trace.jsonl",
                              "every line a JSON object with seq",
                              "unparseable line")
    increasing = all(b > a for a, b in zip(seqs, seqs[1:]))
    return _check("trace-captured", bool(seqs) and increasing,
                  ".bb-session/trace.jsonl",
                  ">=1 line, seqs strictly increasing",
                  "{} lines, increasing={}".format(len(seqs), increasing))


def check_marker_cleared(workspace):
    """D-11: only a confirmed close deletes the marker. Presence after a
    completed scenario means the must-not-lose write was never confirmed."""
    path = os.path.join(workspace, ".bb-session", "marker.json")
    present = os.path.exists(path)
    return _check("marker-cleared", not present, ".bb-session/marker.json",
                  "absent (cleared by confirmed /close)",
                  "present — session row write never confirmed" if present
                  else "absent")


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #
def run_checks(state, workspace, scenario):
    records = state.get("records", [])
    write_log = state.get("write_log", [])
    optional = set(scenario.get("optional_checks", []))
    row = find_session_row(records, scenario)
    if row is None:
        return [_check("session-row-present", False, "state.records",
                       "a row whose session_id embeds '{}'".format(
                           scenario["source_id"]),
                       "no such row — the run never persisted its session")]
    checks = [
        _check("session-row-present", True, "state.records",
               "row present", row.get("session_id")),
        check_checkpoint_zero_valid(row),
        check_fingerprint_correct(row, scenario),
        check_recall_validated(row),
        check_diary_before_row(write_log, row.get("session_id")),
        check_ledger_anchored(row, workspace, "ledger-anchored" in optional),
        check_trace_captured(workspace),
        check_marker_cleared(workspace),
    ]
    return checks


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="assert_run",
        description="Judge a finished scenario run by its artifacts (design §10).")
    parser.add_argument("--state", required=True,
                        help="state file the mock stdio server persisted")
    parser.add_argument("--workspace", required=True,
                        help="the session workspace (holds .bb-session/)")
    parser.add_argument("--scenario", default="known-issue",
                        help="fixture name under fixtures/, or a scenario.json path")
    args = parser.parse_args(argv)

    try:
        with open(args.state, encoding="utf-8") as f:
            state = json.load(f)
        scenario = load_scenario(args.scenario)
    except (OSError, ValueError) as exc:
        sys.stderr.write("assert_run: {}\n".format(exc))
        return 2

    checks = run_checks(state, args.workspace, scenario)
    passed = [c for c in checks if c["pass"]]
    failed = [c for c in checks if not c["pass"]]
    report = {
        "scenario": scenario.get("name", args.scenario),
        "checks": checks,
        "passed": len(passed),
        "failed": len(failed),
    }
    print(json.dumps(report, indent=2))
    for c in checks:
        mark = "SKIP" if c.get("skipped") else ("PASS" if c["pass"] else "FAIL")
        sys.stderr.write("{:4} {:24} {}\n".format(
            mark, c["id"],
            "" if c["pass"] and not c.get("skipped")
            else "expected {} — got {}".format(c["expected"], c["actual"])))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
