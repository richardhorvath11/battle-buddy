"""US2 scenarios 1/2/5, SC-002, FR-002: `/doctor`'s binding-resolution protocol
(``tests/helpers/doctor_flows.py``, T006) against ``manifest/capabilities.json``.

Scenario/scoring-criteria coverage:

- US2 scenario 1 (full roster resolves) / SC-002 (100% required-op resolution):
  ``test_full_roster_*``.
- US2 scenario 2 (a missing required op fails loudly, naming it):
  ``test_missing_op_roster_*``.
- Multi-match ambiguity, explicit-choice binding, and the invalid-choice guard:
  ``test_multi_match_*``.
- US2 scenario 5 (drift re-validation flags stale entries by name):
  ``test_drifted_roster_*``.
- Optional-half resolution (present resolves; absent produces no fail check):
  ``test_optional_*``.

Only the real manifest (``manifest/capabilities.json``) is used here — this is a
contract test, not a fixture smoke test (that's ``test_doctor_fixtures.py``).
Assertions are on the returned artifacts (``bindings`` dicts, ``checks`` dicts)
only, never on prose (BINDING CONSTRAINTS).
"""

import json

from conftest import REPO_ROOT
from helpers import doctor_fixtures, doctor_flows

MANIFEST_PATH = REPO_ROOT / "manifest" / "capabilities.json"


def _load_manifest():
    with open(str(MANIFEST_PATH), encoding="utf-8") as f:
        return json.load(f)


def _binding_checks(checks):
    return [c for c in checks if c["kind"] == "binding"]


# ---------------------------------------------------------------------------
# Full roster -> one entry per required op, protocol-v1 key format, all ok
# ---------------------------------------------------------------------------


def test_full_roster_yields_one_binding_entry_per_required_op(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_full_roster(mock_mcp)

    bindings, checks = doctor_flows.resolve_bindings(manifest, roster)

    required_ops = {
        "{}.{}".format(capability, op)
        for capability, cap_block in manifest["required"].items()
        for op in cap_block["ops"]
    }
    assert set(bindings) == required_ops


def test_full_roster_binding_keys_parse_under_protocol_format(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_full_roster(mock_mcp)

    bindings, _checks = doctor_flows.resolve_bindings(manifest, roster)

    for key, tool_name in bindings.items():
        capability, op = key.split(".", 1)
        assert capability in manifest["required"]
        assert op in manifest["required"][capability]["ops"]
        assert tool_name != op, "bound tool name must not equal the op name"
        assert tool_name in roster.values() or tool_name in roster


def test_full_roster_every_value_is_a_roster_tool_name(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_full_roster(mock_mcp)

    bindings, _checks = doctor_flows.resolve_bindings(manifest, roster)

    for tool_name in bindings.values():
        assert tool_name in roster


def test_full_roster_all_checks_ok_sc_002(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_full_roster(mock_mcp)

    bindings, checks = doctor_flows.resolve_bindings(manifest, roster)

    required_ops = {
        "{}.{}".format(capability, op)
        for capability, cap_block in manifest["required"].items()
        for op in cap_block["ops"]
    }
    binding_checks = _binding_checks(checks)
    assert len(binding_checks) == len(required_ops)
    assert all(c["status"] == "ok" for c in binding_checks)
    # SC-002: 100% of required ops resolve.
    assert len(bindings) == len(required_ops)


# ---------------------------------------------------------------------------
# Missing-op roster -> loud fail naming exactly that op; others still resolve
# (US2 scenario 2)
# ---------------------------------------------------------------------------


def test_missing_op_roster_fails_naming_exactly_that_op(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_roster_missing(mock_mcp, "storage", "append_record")

    bindings, checks = doctor_flows.resolve_bindings(manifest, roster)

    assert "storage.append_record" not in bindings
    binding_checks = _binding_checks(checks)
    fails = [c for c in binding_checks if c["status"] == "fail"]
    assert len(fails) == 1
    fail = fails[0]
    assert fail["id"] == "binding.storage.append_record"
    assert fail["capability"] == "storage"
    assert fail["op"] == "append_record"
    assert "storage.append_record" in fail["detail"]


def test_missing_op_roster_other_ops_still_resolve(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_roster_missing(mock_mcp, "storage", "append_record")

    bindings, checks = doctor_flows.resolve_bindings(manifest, roster)

    required_ops = {
        "{}.{}".format(capability, op)
        for capability, cap_block in manifest["required"].items()
        for op in cap_block["ops"]
    }
    other_ops = required_ops - {"storage.append_record"}
    assert other_ops <= set(bindings)

    binding_checks = _binding_checks(checks)
    ok_ids = {c["id"] for c in binding_checks if c["status"] == "ok"}
    assert all("binding.{}".format(op) in ok_ids for op in other_ops)


# ---------------------------------------------------------------------------
# Multi-match: ambiguous + both candidates, no entry without a choice; valid
# choice binds; invalid choice must not silently bind
# ---------------------------------------------------------------------------


def test_multi_match_ambiguous_with_both_candidates_no_entry(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_roster_multi_match(mock_mcp, "diary", "append_entry")

    bindings, checks = doctor_flows.resolve_bindings(manifest, roster)

    assert "diary.append_entry" not in bindings
    binding_checks = _binding_checks(checks)
    ambiguous = [c for c in binding_checks if c["id"] == "binding.diary.append_entry"]
    assert len(ambiguous) == 1
    check = ambiguous[0]
    assert check["status"] == "ambiguous"

    original = doctor_fixtures.REQUIRED_FIXTURE_TOOL_NAMES[("diary", "append_entry")]
    second = original + "__second"
    assert set(check["candidates"]) == {original, second}


def test_multi_match_explicit_valid_choice_binds_ok(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_roster_multi_match(mock_mcp, "diary", "append_entry")
    original = doctor_fixtures.REQUIRED_FIXTURE_TOOL_NAMES[("diary", "append_entry")]

    bindings, checks = doctor_flows.resolve_bindings(
        manifest, roster, choices={"diary.append_entry": original}
    )

    assert bindings["diary.append_entry"] == original
    binding_checks = _binding_checks(checks)
    resolved = [c for c in binding_checks if c["id"] == "binding.diary.append_entry"]
    assert len(resolved) == 1
    assert resolved[0]["status"] == "ok"


def test_multi_match_invalid_choice_does_not_silently_bind(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_roster_multi_match(mock_mcp, "diary", "append_entry")

    bindings, checks = doctor_flows.resolve_bindings(
        manifest, roster, choices={"diary.append_entry": "not_a_real_candidate"}
    )

    assert "diary.append_entry" not in bindings
    binding_checks = _binding_checks(checks)
    check = [c for c in binding_checks if c["id"] == "binding.diary.append_entry"][0]
    assert check["status"] in ("ambiguous", "fail")
    assert check["status"] != "ok"


# ---------------------------------------------------------------------------
# Drifted roster: revalidate_bindings flags exactly the stale entries by name
# (US2 scenario 5)
# ---------------------------------------------------------------------------


def test_drifted_roster_flags_exactly_the_stale_entry_removed(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    bindings, _checks = doctor_flows.resolve_bindings(manifest, roster)

    drifted_roster = doctor_fixtures.build_roster_drifted(
        roster, bindings, "storage", "append_record"
    )

    checks = doctor_flows.revalidate_bindings(bindings, drifted_roster, manifest)

    fails = [c for c in checks if c["status"] == "fail"]
    assert len(fails) == 1
    fail = fails[0]
    assert fail["id"] == "binding.storage.append_record"
    stale_tool = bindings["storage.append_record"]
    assert stale_tool in fail["detail"]

    oks = [c for c in checks if c["status"] == "ok"]
    assert len(oks) == len(bindings) - 1


def test_drifted_roster_flags_exactly_the_stale_entry_renamed(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    bindings, _checks = doctor_flows.resolve_bindings(manifest, roster)

    drifted_roster = doctor_fixtures.build_roster_drifted(
        roster, bindings, "diary", "read_recent", rename_to="renamed_tool.op"
    )

    checks = doctor_flows.revalidate_bindings(bindings, drifted_roster, manifest)

    fails = [c for c in checks if c["status"] == "fail"]
    assert len(fails) == 1
    assert fails[0]["id"] == "binding.diary.read_recent"

    oks = [c for c in checks if c["status"] == "ok"]
    assert len(oks) == len(bindings) - 1
    assert all(c["status"] == "ok" for c in oks)


def test_undrifted_roster_all_entries_ok(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    bindings, _checks = doctor_flows.resolve_bindings(manifest, roster)

    checks = doctor_flows.revalidate_bindings(bindings, roster, manifest)

    assert len(checks) == len(bindings)
    assert all(c["status"] == "ok" for c in checks)


def test_revalidate_bindings_never_mutates_bindings(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    bindings, _checks = doctor_flows.resolve_bindings(manifest, roster)
    before = dict(bindings)

    drifted_roster = doctor_fixtures.build_roster_drifted(
        roster, bindings, "storage", "append_record"
    )
    doctor_flows.revalidate_bindings(bindings, drifted_roster, manifest)

    assert bindings == before


# ---------------------------------------------------------------------------
# Optional-present roster: optional entries resolve; optional-absent produces
# no fail checks
# ---------------------------------------------------------------------------


def test_optional_present_roster_optional_entries_resolve(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_roster_with_optional(mock_mcp, manifest)

    bindings, checks = doctor_flows.resolve_bindings(manifest, roster)

    optional_ops = {
        "{}.{}".format(capability, op)
        for capability, cap_block in manifest["optional"].items()
        for op in cap_block["ops"]
    }
    assert optional_ops <= set(bindings)

    binding_checks = _binding_checks(checks)
    ok_ids = {c["id"] for c in binding_checks if c["status"] == "ok"}
    assert all("binding.{}".format(op) in ok_ids for op in optional_ops)
    # No fail checks anywhere — every optional op the manifest declares has a
    # matching fixture tool in this roster.
    assert not [c for c in binding_checks if c["status"] == "fail"]


def test_optional_absent_produces_no_fail_checks(mock_mcp):
    manifest = _load_manifest()
    # build_full_roster covers only the required half — every optional op is
    # unresolved here.
    roster = doctor_fixtures.build_full_roster(mock_mcp)

    bindings, checks = doctor_flows.resolve_bindings(manifest, roster)

    optional_ops = {
        "{}.{}".format(capability, op)
        for capability, cap_block in manifest["optional"].items()
        for op in cap_block["ops"]
    }
    assert not (optional_ops & set(bindings))

    binding_checks = _binding_checks(checks)
    assert not [c for c in binding_checks if c["status"] == "fail"]
    # Only the required ops produced checks at all.
    assert {c["id"].split(".", 2)[1] for c in binding_checks} <= set(
        manifest["required"]
    )
