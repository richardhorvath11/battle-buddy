"""R8 timing tripwire: p95 hook latency < 100ms per invocation (SC-002).

Hooks run on every tool call, so latency is responder-facing. This is a
categorical tripwire, not a benchmark: it fails only on gross regressions
(accidental subprocess spawns, unbounded trace reads, heavy imports), which
it catches reliably on any hardware with the generous 100ms bound.
"""

import json
import time

import pytest

import guardrail_deny
import session_guard
import tool_trace

INVOCATIONS = 100
P95_BUDGET_SECONDS = 0.100


def p95_of(run, stdin_text):
    timings = []
    for _ in range(INVOCATIONS):
        start = time.perf_counter()
        run(stdin_text)
        timings.append(time.perf_counter() - start)
    return sorted(timings)[int(INVOCATIONS * 0.95) - 1]


def payload(event, root, **extra):
    base = {
        "hook_event_name": event,
        "tool_name": "Bash",
        "tool_input": {"command": "kubectl get pods -n prod"},
        "cwd": str(root),
        "session_id": "latency-session",
        "transcript_path": str(root / "transcript.jsonl"),
    }
    base.update(extra)
    return json.dumps(base)


def _capped_pre(root):
    # The expensive PreToolUse shape: a REGISTERED triage actor, so every
    # invocation pays the role lookup and the flock-guarded counters read —
    # the uncapped early return would otherwise never time them.
    import _state

    state = root / ".bb-session"
    state.mkdir(exist_ok=True)
    actor = _state.actor_key(str(root / "transcript.jsonl"))
    (state / "agents.json").write_text(
        json.dumps({"protocol": "bb.local.v1", "roles": {actor: "triage"}}),
        encoding="utf-8",
    )
    return tool_trace.run, payload("PreToolUse", root)


CASES = [
    ("guardrail_deny-pre", lambda root: (guardrail_deny.run,
                                         payload("PreToolUse", root))),
    ("tool_trace-pre", lambda root: (tool_trace.run,
                                     payload("PreToolUse", root))),
    ("tool_trace-pre-capped", _capped_pre),
    ("tool_trace-post", lambda root: (tool_trace.run,
                                      payload("PostToolUse", root,
                                              tool_response="3 pods Running"))),
    ("session_guard-start", lambda root: (session_guard.run,
                                          payload("SessionStart", root))),
    ("session_guard-end", lambda root: (session_guard.run,
                                        payload("SessionEnd", root))),
]


@pytest.mark.parametrize("case", CASES, ids=[name for name, _ in CASES])
def test_p95_latency_under_budget(case, tmp_path):
    name, make = case
    root = tmp_path / "workspace"
    root.mkdir()
    run, stdin_text = make(root)
    # tool_trace-post grows the trace across 100 appends — exactly the shape
    # that must stay O(1) (the appender never reads the trace it appends to).
    p95 = p95_of(run, stdin_text)
    assert p95 < P95_BUDGET_SECONDS, (
        "%s p95 %.1fms breaches the %.0fms budget"
        % (name, p95 * 1000, P95_BUDGET_SECONDS * 1000)
    )
