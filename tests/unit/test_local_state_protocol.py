"""One test per assertion of contracts/local-state-protocol.md (FR-013).

The protocol document is the contract slices 3 and 5 build on; this file is
its executable form. Section comments below name the protocol-doc section each
group of tests exercises.
"""

import json
import multiprocessing
import os

import pytest

import _state
from conftest import load_fixture


# --- Location & lifecycle ---------------------------------------------------


def test_state_lives_in_bb_session_at_workspace_root(tmp_path):
    assert _state.state_dir(tmp_path) == str(tmp_path / ".bb-session")


def test_state_dir_is_created_lazily_by_first_writer(tmp_path):
    assert not (tmp_path / ".bb-session").exists()
    _state.append_trace(tmp_path, {"agent": "agent-x", "tool": "Bash",
                                   "summary": "ls", "outcome": "ok"})
    assert (tmp_path / ".bb-session").is_dir()


def test_readers_do_not_create_the_state_dir(tmp_path):
    # get_turns is a PreToolUse read (cap check); it must not litter a
    # .bb-session in a workspace that never opened a session (CR2).
    _state.tail_trace(tmp_path)
    _state.read_roles(tmp_path)
    _state.read_marker(tmp_path)
    assert _state.get_turns(tmp_path, "agent-x") == 0
    assert not (tmp_path / ".bb-session").exists()


# --- marker.json ------------------------------------------------------------


MARKER = {
    "protocol": "bb.local.v1",
    "session_id": "page-ALERT-123-2026-07-20",
    "source_id": "ALERT-123",
    "opened_at": "2026-07-20T03:12:00+00:00",
    "open_write_confirmed": False,
}


def write_marker(root, marker=MARKER):
    state = root / ".bb-session"
    state.mkdir(exist_ok=True)
    (state / "marker.json").write_text(json.dumps(marker), encoding="utf-8")


def test_marker_round_trips_documented_fields(tmp_path):
    write_marker(tmp_path)
    assert _state.read_marker(tmp_path) == MARKER


def test_marker_present_regardless_of_confirmation_state(tmp_path):
    # Trigger is "file present at SessionEnd ⇒ warn", regardless of
    # open_write_confirmed (spec FR-011 / protocol lifecycle).
    write_marker(tmp_path, dict(MARKER, open_write_confirmed=True))
    assert _state.marker_present(tmp_path)
    write_marker(tmp_path, dict(MARKER, open_write_confirmed=False))
    assert _state.marker_present(tmp_path)


def test_marker_deletion_is_the_cleared_state(tmp_path):
    # No resting "closed" state exists on disk — deletion *is* cleared.
    write_marker(tmp_path)
    (tmp_path / ".bb-session" / "marker.json").unlink()
    assert not _state.marker_present(tmp_path)
    assert _state.read_marker(tmp_path) is None


def test_unreadable_marker_still_counts_as_present(tmp_path):
    state = tmp_path / ".bb-session"
    state.mkdir()
    (state / "marker.json").write_text("{corrupt", encoding="utf-8")
    assert _state.marker_present(tmp_path)
    assert _state.read_marker(tmp_path) is None


# --- trace.jsonl: line shapes -----------------------------------------------


def read_trace(root):
    path = root / ".bb-session" / "trace.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_call_line_carries_documented_fields_and_no_event(tmp_path):
    _state.append_trace(
        tmp_path,
        {"agent": "agent-3f2a", "tool": "mcp__sheets__append_row",
         "capability": "storage", "summary": "append_record session_id=x",
         "outcome": "ok"},
    )
    (line,) = read_trace(tmp_path)
    assert line["protocol"] == "bb.local.v1"
    assert line["seq"] == 1
    assert line["agent"] == "agent-3f2a"
    assert line["tool"] == "mcp__sheets__append_row"
    assert line["capability"] == "storage"
    assert line["outcome"] == "ok"
    assert "at" in line
    assert "event" not in line  # call lines have no event field


def test_tripwire_event_line_carries_event_and_consumes_a_seq(tmp_path):
    _state.append_trace(tmp_path, {"agent": "a", "tool": "Bash",
                                   "summary": "x", "outcome": "ok"})
    _state.append_trace(
        tmp_path,
        {"event": "tripwire", "agent": "a", "tool": "mcp__opsgenie__get_alert",
         "matched": "instruction_override"},
    )
    _state.append_trace(tmp_path, {"agent": "a", "tool": "Bash",
                                   "summary": "y", "outcome": "ok"})
    lines = read_trace(tmp_path)
    assert [l["seq"] for l in lines] == [1, 2, 3]
    assert lines[1]["event"] == "tripwire"
    assert lines[1]["matched"] == "instruction_override"
    # Consumers counting *calls* filter on the absence of `event`.
    assert len([l for l in lines if "event" not in l]) == 2


def test_denied_line_shape_matches_protocol_example(tmp_path):
    _state.append_trace(
        tmp_path,
        {"agent": "agent-3f2a", "tool": "Bash",
         "summary": "kubectl delete deploy payments",
         "outcome": "denied:guardrail:destructive_infra"},
    )
    (line,) = read_trace(tmp_path)
    assert line["outcome"].startswith(_state.OUTCOME_DENIED_GUARDRAIL_PREFIX)


def test_outcome_vocabulary_matches_protocol_doc(tmp_path):
    assert _state.FIXED_OUTCOMES == (
        "ok", "error:auth", "error:timeout", "error:other", "denied:turn_cap",
    )
    assert _state.OUTCOME_DENIED_GUARDRAIL_PREFIX == "denied:guardrail:"


# --- trace.jsonl: seq semantics ---------------------------------------------


def test_seq_is_monotonic_and_file_order_equals_seq_order(tmp_path):
    for i in range(20):
        _state.append_trace(tmp_path, {"agent": "a", "tool": "Bash",
                                       "summary": str(i), "outcome": "ok"})
    lines = read_trace(tmp_path)
    assert [l["seq"] for l in lines] == list(range(1, 21))


def test_append_never_reads_or_rewrites_the_trace(tmp_path):
    # O(1) appends: poison the existing trace file; appending still works and
    # leaves prior bytes untouched (the appender never parses what's there).
    _state.append_trace(tmp_path, {"agent": "a", "tool": "Bash",
                                   "summary": "first", "outcome": "ok"})
    trace_path = tmp_path / ".bb-session" / "trace.jsonl"
    poisoned = trace_path.read_bytes() + b"NOT JSON AT ALL\n"
    trace_path.write_bytes(poisoned)
    _state.append_trace(tmp_path, {"agent": "a", "tool": "Bash",
                                   "summary": "second", "outcome": "ok"})
    assert trace_path.read_bytes().startswith(poisoned)


def _parallel_appender(args):
    hooks_dir, root, worker, count = args
    import sys

    if hooks_dir not in sys.path:
        sys.path.insert(0, hooks_dir)
    import _state as state_mod

    for i in range(count):
        state_mod.append_trace(
            root,
            {"agent": "agent-%d" % worker, "tool": "Bash",
             "summary": "w%d-%d" % (worker, i), "outcome": "ok"},
        )
    return worker


def test_parallel_appends_are_unique_gap_free_and_ordered(tmp_path):
    # R11 / spec edge case: concurrent tool calls from parallel subagents —
    # every call lands exactly once, seq never duplicates, file order = seq
    # order (append-time assignment under one flock).
    hooks_dir = os.path.dirname(_state.__file__)
    workers, per_worker = 4, 25
    args = [(hooks_dir, str(tmp_path), w, per_worker) for w in range(workers)]
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(workers) as pool:
        pool.map(_parallel_appender, args)
    lines = read_trace(tmp_path)
    seqs = [l["seq"] for l in lines]
    assert len(lines) == workers * per_worker
    assert seqs == sorted(seqs)  # file order = seq order
    assert seqs == list(range(1, workers * per_worker + 1))  # unique, gap-free


# --- counters.json ----------------------------------------------------------


def test_counters_sidecar_shape(tmp_path):
    _state.append_trace(tmp_path, {"agent": "a", "tool": "Bash",
                                   "summary": "x", "outcome": "ok"})
    _state.increment_turn(tmp_path, "agent-3f2a")
    counters = json.loads(
        (tmp_path / ".bb-session" / "counters.json").read_text(encoding="utf-8")
    )
    assert counters["protocol"] == "bb.local.v1"
    assert counters["seq"] == 1
    assert counters["turns"] == {"agent-3f2a": 1}


def test_turns_checked_at_pre_incremented_at_post(tmp_path):
    # Reading the count never consumes a turn (check-at-Pre); only
    # increment_turn (the PostToolUse path — executed calls) consumes one.
    assert _state.get_turns(tmp_path, "agent-x") == 0
    assert _state.get_turns(tmp_path, "agent-x") == 0
    assert _state.increment_turn(tmp_path, "agent-x") == 1
    assert _state.get_turns(tmp_path, "agent-x") == 1
    assert _state.increment_turn(tmp_path, "agent-x") == 2
    assert _state.get_turns(tmp_path, "agent-x") == 2


def test_turns_are_per_actor(tmp_path):
    _state.increment_turn(tmp_path, "agent-a")
    _state.increment_turn(tmp_path, "agent-a")
    _state.increment_turn(tmp_path, "agent-b")
    assert _state.get_turns(tmp_path, "agent-a") == 2
    assert _state.get_turns(tmp_path, "agent-b") == 1


def test_denied_lines_do_not_consume_turns(tmp_path):
    # A denied call appends its line but never reaches PostToolUse, so its
    # actor's turn count is untouched (protocol "finding A" resolution).
    _state.append_trace(
        tmp_path,
        {"agent": "agent-a", "tool": "Bash", "summary": "rm -rf /",
         "outcome": "denied:guardrail:destructive_filesystem"},
    )
    assert _state.get_turns(tmp_path, "agent-a") == 0


def test_corrupt_counters_with_no_trace_starts_at_one(tmp_path):
    state = tmp_path / ".bb-session"
    state.mkdir()
    (state / "counters.json").write_text("{broken", encoding="utf-8")
    assert _state.get_turns(tmp_path, "agent-a") == 0
    line = _state.append_trace(tmp_path, {"agent": "a", "tool": "Bash",
                                          "summary": "x", "outcome": "ok"})
    assert line["seq"] == 1


def test_corrupt_counters_recover_seq_from_trace_tail_never_duplicating(
    tmp_path, capsys
):
    # SF1: the failure that must not be silent. An existing trace at seq 7 with
    # a corrupt counters.json must NOT reset the next append to seq 1 (that
    # would duplicate seqs and falsify the audit log). Recover from the tail
    # and surface a diagnostic.
    for _ in range(7):
        _state.append_trace(tmp_path, {"agent": "a", "tool": "Bash",
                                       "summary": "x", "outcome": "ok"})
    counters_path = tmp_path / ".bb-session" / "counters.json"
    counters_path.write_text("{truncated mid-write", encoding="utf-8")
    capsys.readouterr()  # clear
    line = _state.append_trace(tmp_path, {"agent": "a", "tool": "Bash",
                                          "summary": "y", "outcome": "ok"})
    assert line["seq"] == 8  # continues past the tail — no duplicate of 1..7
    assert "corrupt" in capsys.readouterr().err  # not silent (FR-004)
    all_seqs = [l["seq"] for l in read_trace(tmp_path)]
    assert len(all_seqs) == len(set(all_seqs))  # no duplicates anywhere


def test_crash_window_seq_skip_is_bounded_never_duplicated(tmp_path):
    # TA7: a crash between counter-increment and trace append can skip a seq
    # value at most (counters ahead of the trace) — never duplicate. Simulate
    # by advancing the counter past the trace, then assert monotonic-unique.
    _state.append_trace(tmp_path, {"agent": "a", "tool": "Bash",
                                   "summary": "x", "outcome": "ok"})
    counters_path = tmp_path / ".bb-session" / "counters.json"
    counters_path.write_text(
        json.dumps({"protocol": "bb.local.v1", "seq": 5, "turns": {}}),
        encoding="utf-8",
    )
    line = _state.append_trace(tmp_path, {"agent": "a", "tool": "Bash",
                                          "summary": "y", "outcome": "ok"})
    assert line["seq"] == 6  # skipped 2..5, never reused seq 1
    seqs = [l["seq"] for l in read_trace(tmp_path)]
    assert seqs == [1, 6] and len(seqs) == len(set(seqs))


# --- Auth-context window ----------------------------------------------------


def test_tail_returns_last_10_lines_the_protocol_window(tmp_path):
    assert _state.AUTH_CONTEXT_WINDOW == 10
    for i in range(25):
        _state.append_trace(tmp_path, {"agent": "a", "tool": "Bash",
                                       "summary": str(i), "outcome": "ok"})
    tail = _state.tail_trace(tmp_path)
    assert len(tail) == 10
    assert [l["seq"] for l in tail] == list(range(16, 26))


def test_tail_of_absent_trace_is_empty(tmp_path):
    assert _state.tail_trace(tmp_path) == []


def test_tail_skips_corrupt_lines_without_failing(tmp_path):
    _state.append_trace(tmp_path, {"agent": "a", "tool": "Bash",
                                   "summary": "x", "outcome": "ok"})
    with open(str(tmp_path / ".bb-session" / "trace.jsonl"), "ab") as f:
        f.write(b"garbage line\n")
    _state.append_trace(tmp_path, {"agent": "a", "tool": "Bash",
                                   "summary": "y", "outcome": "ok"})
    tail = _state.tail_trace(tmp_path)
    assert [l["seq"] for l in tail] == [1, 2]


# --- agents.json: actor identity and roles ----------------------------------


def test_actor_key_is_stable_and_distinct_per_transcript_path(tmp_path):
    probe = load_fixture("unit", "transcript-path-probe.json")
    main = probe["observed_payloads"]["main_session"]["transcript_path"]
    sub = probe["observed_payloads"]["subagent"]["transcript_path"]
    assert main != sub  # the recorded R10 probe finding
    assert _state.actor_key(main) == _state.actor_key(main)
    assert _state.actor_key(main) != _state.actor_key(sub)
    assert _state.actor_key(main).startswith("agent-")


def test_role_lookup_reads_registered_convention(tmp_path):
    state = tmp_path / ".bb-session"
    state.mkdir()
    (state / "agents.json").write_text(
        json.dumps({"protocol": "bb.local.v1", "roles": {"agent-3f2a": "triage"}}),
        encoding="utf-8",
    )
    assert _state.role_for(tmp_path, "agent-3f2a") == "triage"


def test_unregistered_actor_has_no_role(tmp_path):
    # Fail open: no registration ⇒ no cap applies (R10) — the caller treats
    # None as "uncapped".
    assert _state.role_for(tmp_path, "agent-anon") is None
    state = tmp_path / ".bb-session"
    state.mkdir()
    (state / "agents.json").write_text("{malformed", encoding="utf-8")
    assert _state.role_for(tmp_path, "agent-anon") is None


# --- staging/ ---------------------------------------------------------------


def test_transcript_stages_under_documented_name(tmp_path):
    source = tmp_path / "native-transcript.jsonl"
    source.write_text("transcript body\n", encoding="utf-8")
    staged = _state.stage_transcript(tmp_path, source)
    assert staged == str(tmp_path / ".bb-session" / "staging" / "transcript.md")
    with open(staged, encoding="utf-8") as f:
        assert f.read() == "transcript body\n"


def test_missing_transcript_degrades_to_none_never_raises(tmp_path):
    assert _state.stage_transcript(tmp_path, tmp_path / "nope.jsonl") is None


def test_uploaded_trace_artifact_name_mapping(tmp_path):
    # Local trace.jsonl uploads as tool-trace.jsonl (design §5.3); the name
    # mapping is part of the protocol.
    assert _state.TRACE_NAME == "trace.jsonl"
    assert _state.UPLOADED_TRACE_NAME == "tool-trace.jsonl"
