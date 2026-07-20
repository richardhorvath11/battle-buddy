"""SchemaRegistry — the mock's inspectable tool-schema surface (FR-011).

Loads ``contract.json`` (the machine-readable operation contract, research R5)
at instance creation and never mutates it. ``describe()`` exposes every
capability's operation names and input/output shapes without any operation
having been invoked — the surface binding-resolution tests (slice 4) match
against.
"""

import copy
import json
from pathlib import Path

DEFAULT_CONTRACT_PATH = Path(__file__).resolve().parent.parent / "contract.json"


class SchemaRegistry:
    def __init__(self, contract_path=None):
        path = Path(contract_path) if contract_path is not None else DEFAULT_CONTRACT_PATH
        with open(str(path), encoding="utf-8") as f:
            self._contract = json.load(f)

    @property
    def constants(self):
        return dict(self._contract["constants"])

    @property
    def error_codes(self):
        return list(self._contract["error_codes"])

    def capabilities(self):
        return list(self._contract["capabilities"])

    def operation(self, capability, op):
        """The contract entry for one operation, or None if unknown."""
        cap = self._contract["capabilities"].get(capability)
        if cap is None:
            return None
        return cap.get("ops", {}).get(op)

    def describe(self):
        """{capability: {op: {input, output}}} for every contract operation."""
        surface = {}
        for cap_name, cap in self._contract["capabilities"].items():
            surface[cap_name] = {}
            for op_name, op in cap.get("ops", {}).items():
                surface[cap_name][op_name] = {
                    "input": copy.deepcopy(op["input"]),
                    "output": copy.deepcopy(op["output"]),
                }
        return surface
