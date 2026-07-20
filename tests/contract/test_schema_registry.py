"""Conformance: the schema registry surface (FR-011, Story 2 AS-5).

``describe()`` must enumerate every contract operation with its input/output
shapes on a fresh mock — zero invocations beforehand — and be rich enough for
a binding-resolution-style matcher (slice 4's hermetic target) to pair every
required operation with a tool in a roster.
"""

import json
from pathlib import Path

CONTRACT_PATH = (
    Path(__file__).resolve().parents[2] / "tools" / "bb-mock-mcp" / "contract.json"
)


def test_describe_enumerates_every_contract_op_without_invocation(mock_mcp):
    assert mock_mcp.write_log.entries == []  # nothing has been invoked

    with open(str(CONTRACT_PATH), encoding="utf-8") as f:
        contract = json.load(f)

    surface = mock_mcp.describe()
    assert set(surface) == set(contract["capabilities"])
    for cap_name, cap in contract["capabilities"].items():
        assert set(surface[cap_name]) == set(cap["ops"])
        for op_name, op in cap["ops"].items():
            described = surface[cap_name][op_name]
            assert set(described["input"]) == set(op["input"])
            assert set(described["output"]) == set(op["output"])
            for field, spec in described["input"].items():
                assert "type" in spec, "{}.{} input '{}' lacks a type".format(
                    cap_name, op_name, field
                )

    assert mock_mcp.write_log.entries == []  # describe() itself invokes nothing


def test_binding_resolution_style_matching(mock_mcp):
    """A matcher can bind every operation to exactly one tool in a conforming
    roster using only the described names and required input fields."""
    surface = mock_mcp.describe()

    roster = [
        {
            "tool_name": "acme_{}_{}".format(cap, op),
            "capability": cap,
            "op": op,
            "input_fields": sorted(spec["input"]),
        }
        for cap, ops in surface.items()
        for op, spec in ops.items()
    ]

    for cap, ops in surface.items():
        for op, spec in ops.items():
            required = {f for f, s in spec["input"].items() if s.get("required")}
            matches = [
                t
                for t in roster
                if t["capability"] == cap
                and t["op"] == op
                and required <= set(t["input_fields"])
            ]
            assert len(matches) == 1, "no unique binding for {}.{}".format(cap, op)
