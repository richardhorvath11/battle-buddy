"""Unit-layer selftest: demonstrates the table-driven fixture pattern (FR-007).

Slice-2+ hooks/helpers are specified as pure ``(input payload, local state) ->
(exit code, output)`` functions (design §10 layer 1). This module proves the
harness supports that pattern end-to-end — JSON fixture table in, parametrized
verdicts out — using a small reference gate function.

Must stay Python 3.9-compatible: the unit layer runs on the shipped-code floor
(design D-1, research R2).
"""

import pytest

from conftest import load_fixture

CASES = load_fixture("unit", "selftest.json")["cases"]


def deny_gate(payload, state):
    """Reference pure function in the slice-2 hook shape.

    Fails open when its state is unavailable (Constitution III: a broken gate
    must never brick a session).
    """
    if not isinstance(payload, dict) or "op" not in payload:
        return 1, "invalid payload: missing op"
    if "denied_ops" not in state:
        return 0, "ok (state unavailable — failing open)"
    if payload["op"] in state["denied_ops"]:
        return 2, "denied: " + payload["op"]
    return 0, "ok"


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_payload_state_to_exit_output(case):
    exit_code, output = deny_gate(case["payload"], case["state"])
    assert exit_code == case["expect"]["exit_code"]
    assert output == case["expect"]["output"]
