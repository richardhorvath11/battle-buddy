"""FR-004, US2 scenario 3: `/doctor`'s structured report
(``tests/helpers/doctor_flows.py`` ``assemble_report``, T008) against
``manifest/capabilities.json``.

Coverage:

- `schema` field.
- One `binding` check per manifest required op; one `probe` check per
  capability.
- Outcome rule: `red` iff a required op is unresolved (missing-op roster) or
  an ambiguity is left unresolved (multi-match, no choice); an ambiguity
  resolved by an explicit choice is `green`.
- Optional-missing capabilities never red the outcome — they populate
  `reduced_features` with the manifest's own `enables` lists, loaded and
  compared rather than hardcoded (US2 scenario 3).
- `candidates` appears only on `ambiguous` checks, scanned across every
  check the assembled report carries.
- `migrations` mirrors every `version`-check failure's detail exactly.
- A fully-green path (full roster incl. optional, valid config, matching
  header, answering shell) is `green` with empty `reduced_features` and
  empty `migrations`.

Only the real manifest (`manifest/capabilities.json`) is used here — this is
a contract test, not a fixture smoke test. Assertions are on the returned
report dict only (BINDING CONSTRAINTS), never prose.
"""

import json

from conftest import REPO_ROOT
from helpers import doctor_fixtures, doctor_flows

MANIFEST_PATH = REPO_ROOT / "manifest" / "capabilities.json"
PLUGIN_VERSION = "0.4.0"


def _load_manifest():
    with open(str(MANIFEST_PATH), encoding="utf-8") as f:
        return json.load(f)


def _green_config_checks(mock):
    header_store = doctor_fixtures.FixtureHeaderStore(
        header=list(doctor_fixtures.EXPECTED_HEADER)
    )
    catalog_path = doctor_fixtures.config_fixture_path("catalog-valid.json")
    config = doctor_fixtures.load_config_fixture("config-valid.json")
    return doctor_flows.check_config(mock, config, header_store, catalog_path)


def _green_version_checks():
    config = doctor_fixtures.load_config_fixture("config-valid.json")
    return doctor_flows.check_versions(config, PLUGIN_VERSION)


def _green_shell_check():
    config = doctor_fixtures.load_config_fixture("config-valid.json")
    adapter = doctor_fixtures.FixtureShellAdapter(answering=True)
    return doctor_flows.check_shell(config, adapter)


# ---------------------------------------------------------------------------
# Schema field
# ---------------------------------------------------------------------------


def test_report_schema_field(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    bindings, binding_checks = doctor_flows.resolve_bindings(manifest, roster)

    report = doctor_flows.assemble_report(
        binding_checks, [], [], [], None, manifest, bindings
    )

    assert report["schema"] == "bb.doctor.report.v1"


# ---------------------------------------------------------------------------
# One binding check per manifest required op; one probe check per capability
# ---------------------------------------------------------------------------


def test_one_binding_check_per_required_op_and_one_probe_per_capability(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    bindings, binding_checks = doctor_flows.resolve_bindings(manifest, roster)
    probe_checks = doctor_flows.run_probes(mock_mcp)

    report = doctor_flows.assemble_report(
        binding_checks, probe_checks, [], [], None, manifest, bindings
    )

    required_ops = {
        "{}.{}".format(capability, op)
        for capability, cap_block in manifest["required"].items()
        for op in cap_block["ops"]
    }
    binding_kind = [c for c in report["checks"] if c["kind"] == "binding"]
    assert len(binding_kind) == len(required_ops)

    probe_kind = [c for c in report["checks"] if c["kind"] == "probe"]
    assert len(probe_kind) == 4
    assert {c["capability"] for c in probe_kind} == {
        "storage",
        "diary",
        "alerting",
        "artifacts",
    }


# ---------------------------------------------------------------------------
# Outcome rule: red iff required fail, or unresolved ambiguous
# ---------------------------------------------------------------------------


def test_missing_required_op_roster_reds_the_outcome(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_roster_missing(mock_mcp, "storage", "append_record")
    bindings, binding_checks = doctor_flows.resolve_bindings(manifest, roster)

    report = doctor_flows.assemble_report(
        binding_checks, [], [], [], None, manifest, bindings
    )

    assert report["outcome"] == "red"


def test_unresolved_ambiguous_reds_the_outcome(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_roster_multi_match(mock_mcp, "diary", "append_entry")
    bindings, binding_checks = doctor_flows.resolve_bindings(manifest, roster)

    report = doctor_flows.assemble_report(
        binding_checks, [], [], [], None, manifest, bindings
    )

    assert report["outcome"] == "red"
    assert any(c["status"] == "ambiguous" for c in report["checks"])


def test_ambiguous_resolved_by_explicit_choice_is_green(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_roster_multi_match(mock_mcp, "diary", "append_entry")
    original = doctor_fixtures.REQUIRED_FIXTURE_TOOL_NAMES[("diary", "append_entry")]
    bindings, binding_checks = doctor_flows.resolve_bindings(
        manifest, roster, choices={"diary.append_entry": original}
    )

    report = doctor_flows.assemble_report(
        binding_checks, [], [], [], None, manifest, bindings
    )

    assert report["outcome"] == "green"
    assert not any(c["status"] == "ambiguous" for c in report["checks"])


# ---------------------------------------------------------------------------
# Optional-missing -> green + exact reduced_features enables lists
# ---------------------------------------------------------------------------


def test_optional_missing_stays_green_with_exact_reduced_features(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_full_roster(mock_mcp)  # required-only roster
    bindings, binding_checks = doctor_flows.resolve_bindings(manifest, roster)

    report = doctor_flows.assemble_report(
        binding_checks, [], [], [], None, manifest, bindings
    )

    assert report["outcome"] == "green"
    assert manifest["optional"]  # sanity: the manifest actually has an optional half
    by_capability = {rf["capability"]: rf for rf in report["reduced_features"]}
    assert set(by_capability) == set(manifest["optional"])
    for capability, cap_block in manifest["optional"].items():
        # Loaded and compared, never hardcoded (US2 scenario 3).
        assert by_capability[capability]["disabled"] == cap_block["enables"]


# ---------------------------------------------------------------------------
# candidates key present only on ambiguous checks
# ---------------------------------------------------------------------------


def test_optional_multi_match_stays_green_with_ambiguity_surfaced(mock_mcp):
    """An unresolvable *optional* ambiguity never reds the run (contracts/
    doctor-protocol.md "Outcome rule"): the ambiguous check is surfaced for a
    later explicit choice, the outcome stays green, and the capability's
    reduced_features membership follows the none-resolved rule."""
    manifest = _load_manifest()
    roster = doctor_fixtures.build_roster_with_optional(mock_mcp, manifest)
    # Duplicate one optional op's shape under a second tool name -> multi-match.
    cap, op = "code", "read_file"
    shape = manifest["optional"][cap]["ops"][op]
    roster["othercorp_scm.fetch_blob"] = {
        "input": shape["input"],
        "output": shape["output"],
    }

    bindings, binding_checks = doctor_flows.resolve_bindings(manifest, roster)
    report = doctor_flows.assemble_report(
        binding_checks, [], [], [], None, manifest, bindings
    )

    ambiguous = [c for c in report["checks"] if c["status"] == "ambiguous"]
    assert [c["id"] for c in ambiguous] == ["binding.code.read_file"]
    assert report["outcome"] == "green"
    # code's other ops (list_commits, search) resolved, so the capability is
    # not reduced; observability resolved fully and is not reduced either.
    assert report["reduced_features"] == []


def test_candidates_key_present_only_on_ambiguous_checks(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_roster_multi_match(mock_mcp, "diary", "append_entry")
    bindings, binding_checks = doctor_flows.resolve_bindings(manifest, roster)
    probe_checks = doctor_flows.run_probes(mock_mcp)
    config_checks = _green_config_checks(mock_mcp)
    version_checks = _green_version_checks()
    shell_check = _green_shell_check()

    report = doctor_flows.assemble_report(
        binding_checks,
        probe_checks,
        config_checks,
        version_checks,
        shell_check,
        manifest,
        bindings,
    )

    ambiguous = [c for c in report["checks"] if c["status"] == "ambiguous"]
    assert ambiguous  # the multi-match roster guarantees at least one

    for check in report["checks"]:
        if check["status"] == "ambiguous":
            assert "candidates" in check
        else:
            assert "candidates" not in check


# ---------------------------------------------------------------------------
# migrations mirrors version-check failures exactly
# ---------------------------------------------------------------------------


def test_migrations_mirrors_version_check_failures_exactly(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    bindings, binding_checks = doctor_flows.resolve_bindings(manifest, roster)
    future_config = doctor_fixtures.load_config_fixture("config-future-version.json")
    version_checks = doctor_flows.check_versions(future_config, PLUGIN_VERSION)

    report = doctor_flows.assemble_report(
        binding_checks, [], [], version_checks, None, manifest, bindings
    )

    # Literal expectation — pins content independently of assemble_report's
    # own mirroring expression (review finding: avoid the tautology).
    assert report["migrations"] == [
        "config block bb.config.v2 → bb.config.v1: run /setup --migrate",
        "store schema bb.schema.v2 → bb.schema.v1: run /setup --migrate",
    ]
    assert report["migrations"] == [
        c["detail"] for c in version_checks if c["status"] == "fail"
    ]


def test_migrations_empty_when_versions_all_ok(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    bindings, binding_checks = doctor_flows.resolve_bindings(manifest, roster)
    version_checks = _green_version_checks()

    report = doctor_flows.assemble_report(
        binding_checks, [], [], version_checks, None, manifest, bindings
    )

    assert report["migrations"] == []


# ---------------------------------------------------------------------------
# Fully-green path
# ---------------------------------------------------------------------------


def test_fully_green_path(mock_mcp):
    manifest = _load_manifest()
    roster = doctor_fixtures.build_roster_with_optional(mock_mcp, manifest)
    bindings, binding_checks = doctor_flows.resolve_bindings(manifest, roster)
    probe_checks = doctor_flows.run_probes(mock_mcp)
    config_checks = _green_config_checks(mock_mcp)
    version_checks = _green_version_checks()
    shell_check = _green_shell_check()

    report = doctor_flows.assemble_report(
        binding_checks,
        probe_checks,
        config_checks,
        version_checks,
        shell_check,
        manifest,
        bindings,
    )

    assert report["outcome"] == "green"
    assert report["reduced_features"] == []
    assert report["migrations"] == []
    assert not any(c["status"] == "fail" for c in report["checks"])
    assert not any(c["status"] == "ambiguous" for c in report["checks"])
