"""FR-001: the capability manifest (`manifest/capabilities.json`, `bb.capabilities.v1`)
— contracts/doctor-protocol.md § "Capability manifest".

The required half is the shipped projection of operation contract v1
(``tools/bb-mock-mcp/contract.json``): same capability set, same op names per
capability, and per-op input/output shapes structurally equal to the contract —
loaded and compared from both files (never hardcoded copies), so drift in either
file fails here. ``artifacts.get_file`` is test-only harness surface (per
doctor-protocol.md) and must be absent from the manifest while remaining present
in the contract. The optional half (``code``, ``observability``) is authored
directly in the manifest per design §7.1 / research R7 — this test only pins its
op names, non-empty shapes, and the exact ``enables`` lists.
"""

import json

from conftest import REPO_ROOT

MANIFEST_PATH = REPO_ROOT / "manifest" / "capabilities.json"
CONTRACT_PATH = REPO_ROOT / "tools" / "bb-mock-mcp" / "contract.json"

EXCLUDED_TEST_ONLY_OPS = {
    "artifacts": {"get_file"},
}

EXPECTED_OPTIONAL_OPS = {
    "code": {"read_file", "list_commits", "search"},
    "observability": {"query_metrics", "search_logs"},
}

EXPECTED_ENABLES = {
    "code": ["deploy correlation", "catalog", "runbook fetch"],
    "observability": ["metric reads", "evidence deep-links"],
}


def _load(path):
    with open(str(path), encoding="utf-8") as f:
        return json.load(f)


def _contract_required_capabilities(contract):
    return {
        name: cap
        for name, cap in contract["capabilities"].items()
        if cap.get("required")
    }


# ---------------------------------------------------------------------------
# Schema field
# ---------------------------------------------------------------------------


def test_manifest_schema_field():
    manifest = _load(MANIFEST_PATH)
    assert manifest["schema"] == "bb.capabilities.v1"


# ---------------------------------------------------------------------------
# Required-half fidelity vs contract.json — both directions
# ---------------------------------------------------------------------------


def test_required_capability_set_matches_contract_both_directions():
    manifest = _load(MANIFEST_PATH)
    contract = _load(CONTRACT_PATH)

    contract_required = set(_contract_required_capabilities(contract))
    manifest_required = set(manifest["required"])

    only_in_contract = contract_required - manifest_required
    only_in_manifest = manifest_required - contract_required
    assert not only_in_contract and not only_in_manifest, (
        "required capability set diverges from contract.json:\n"
        "  only in contract: %r\n"
        "  only in manifest: %r" % (only_in_contract, only_in_manifest)
    )


def test_required_op_names_match_contract_per_capability_both_directions():
    manifest = _load(MANIFEST_PATH)
    contract = _load(CONTRACT_PATH)
    contract_required = _contract_required_capabilities(contract)

    for cap_name, cap in contract_required.items():
        contract_ops = set(cap["ops"]) - EXCLUDED_TEST_ONLY_OPS.get(cap_name, set())
        manifest_ops = set(manifest["required"][cap_name]["ops"])

        only_in_contract = contract_ops - manifest_ops
        only_in_manifest = manifest_ops - contract_ops
        assert not only_in_contract and not only_in_manifest, (
            "%s op set diverges from contract.json (post test-only exclusion):\n"
            "  only in contract: %r\n"
            "  only in manifest: %r" % (cap_name, only_in_contract, only_in_manifest)
        )


def test_required_op_shapes_structurally_equal_to_contract():
    manifest = _load(MANIFEST_PATH)
    contract = _load(CONTRACT_PATH)
    contract_required = _contract_required_capabilities(contract)

    mismatches = []
    for cap_name, cap in contract_required.items():
        excluded = EXCLUDED_TEST_ONLY_OPS.get(cap_name, set())
        for op_name, op in cap["ops"].items():
            if op_name in excluded:
                continue
            manifest_op = manifest["required"][cap_name]["ops"][op_name]
            if manifest_op["input"] != op["input"]:
                mismatches.append(
                    "%s.%s input: manifest=%r contract=%r"
                    % (cap_name, op_name, manifest_op["input"], op["input"])
                )
            if manifest_op["output"] != op["output"]:
                mismatches.append(
                    "%s.%s output: manifest=%r contract=%r"
                    % (cap_name, op_name, manifest_op["output"], op["output"])
                )
    assert not mismatches, "shape mismatches vs contract.json:\n" + "\n".join(mismatches)


def test_artifacts_get_file_excluded_from_manifest_but_present_in_contract():
    manifest = _load(MANIFEST_PATH)
    contract = _load(CONTRACT_PATH)

    assert "get_file" in contract["capabilities"]["artifacts"]["ops"], (
        "test setup assumption broken: contract.json no longer has artifacts.get_file"
    )
    assert "get_file" not in manifest["required"]["artifacts"]["ops"], (
        "manifest/capabilities.json must exclude artifacts.get_file — it is "
        "test-only harness surface per contracts/doctor-protocol.md, not an "
        "integration requirement"
    )


# ---------------------------------------------------------------------------
# Optional half — authored in the manifest per research R7
# ---------------------------------------------------------------------------


def test_optional_capabilities_present():
    manifest = _load(MANIFEST_PATH)
    assert set(manifest["optional"]) == set(EXPECTED_OPTIONAL_OPS)


def test_optional_ops_present_with_non_empty_shapes():
    manifest = _load(MANIFEST_PATH)
    for cap_name, expected_ops in EXPECTED_OPTIONAL_OPS.items():
        cap = manifest["optional"][cap_name]
        assert set(cap["ops"]) == expected_ops, (
            "%s optional ops diverge from the expected set: %r vs %r"
            % (cap_name, set(cap["ops"]), expected_ops)
        )
        for op_name, op in cap["ops"].items():
            assert op.get("input"), "%s.%s has an empty/missing input shape" % (
                cap_name,
                op_name,
            )
            assert op.get("output"), "%s.%s has an empty/missing output shape" % (
                cap_name,
                op_name,
            )


def test_optional_enables_lists_are_exact():
    manifest = _load(MANIFEST_PATH)
    for cap_name, expected_enables in EXPECTED_ENABLES.items():
        assert manifest["optional"][cap_name]["enables"] == expected_enables
