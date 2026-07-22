"""FR-003, US2 scenario 4: `/doctor`'s verification checks
(``tests/helpers/doctor_flows.py`` ``check_config``/``check_versions``/
``check_shell``/``run_probes``, T006/T008).

Coverage:

- Benign-probe outcomes (storage/diary/alerting pass on an empty mock — empty
  result is a pass; artifacts is schema-match-only skip; an injected
  responder-credential failure fails only its designated capability) —
  asserted via the returned check-dict artifact itself, since the write log
  can't see reads (FR-011's "the oracle read-shaped probes need").
- Store header create-vs-validate (doctor-side): matching header passes with
  zero writes; an empty store fails naming it; a mismatched header fails
  naming the exact gap (missing column / extra column / wrong sentinel,
  each in its own targeted case) — zero writes in every case.
- Diary readability and catalog parseability ok/fail.
- Config-block well-formedness: the malformed fixture is a repair case, never
  treated as absent — the other three config checks still run.
- Version-seam compatibility: a valid config passes both seam checks; the
  future-version fixture fails both with the exact migration-string format
  (US2 scenario 4).
- Shell notify round-trip: answering -> ok, not answering -> fail, no
  adapter/no "shell" key -> skip (never failed), and a skip never reds an
  assembled report's outcome.

Assertions are on the returned artifacts only (BINDING CONSTRAINTS), never
prose.
"""

import json

from helpers import doctor_fixtures, doctor_flows

# ---------------------------------------------------------------------------
# run_probes: empty-mock pass, artifacts schema-match-only skip, injected fail
# ---------------------------------------------------------------------------


def test_probes_pass_on_empty_mock(mock_mcp):
    checks = doctor_flows.run_probes(mock_mcp)
    by_capability = {c["capability"]: c for c in checks}

    for capability in ("storage", "diary", "alerting"):
        check = by_capability[capability]
        assert check["kind"] == "probe"
        assert check["status"] == "ok", "{} probe should pass on an empty mock".format(
            capability
        )


def test_artifacts_probe_is_schema_match_only_skip(mock_mcp):
    checks = doctor_flows.run_probes(mock_mcp)
    by_capability = {c["capability"]: c for c in checks}

    artifacts_check = by_capability["artifacts"]
    assert artifacts_check["kind"] == "probe"
    assert artifacts_check["status"] == "skip"
    assert "schema-match" in artifacts_check["detail"]


def test_failing_probe_injector_fails_only_its_designated_capability(mock_mcp):
    injector = doctor_fixtures.FailingProbeInjector(mock_mcp, failing_capability="alerting")

    checks = doctor_flows.run_probes(injector)
    by_capability = {c["capability"]: c for c in checks}

    failed = by_capability["alerting"]
    assert failed["status"] == "fail"
    # the envelope's message is carried into detail (FailingProbeInjector's
    # documented stand-in message for a responder-credential/permission
    # failure — data-model.md "Fixture surfaces").
    assert "responder credentials rejected" in failed["detail"]

    for capability in ("storage", "diary"):
        assert by_capability[capability]["status"] == "ok"


# ---------------------------------------------------------------------------
# check_config helpers
# ---------------------------------------------------------------------------


def _config_checks(mock, header_store, catalog_path=None, config=None):
    if catalog_path is None:
        catalog_path = doctor_fixtures.config_fixture_path("catalog-valid.json")
    if config is None:
        config = doctor_fixtures.load_config_fixture("config-valid.json")
    return doctor_flows.check_config(mock, config, header_store, catalog_path)


def _check_by_id(checks, check_id):
    matches = [c for c in checks if c["id"] == check_id]
    assert len(matches) == 1, "expected exactly one {!r} check, got {!r}".format(
        check_id, matches
    )
    return matches[0]


# ---------------------------------------------------------------------------
# check_config -> store header (create-vs-validate, doctor-side: zero writes)
# ---------------------------------------------------------------------------


def test_header_validate_pass_is_ok_with_zero_writes(mock_mcp):
    header_store = doctor_fixtures.FixtureHeaderStore(
        header=list(doctor_fixtures.EXPECTED_HEADER)
    )

    checks = _config_checks(mock_mcp, header_store)

    check = _check_by_id(checks, "config.store_header")
    assert check["status"] == "ok"
    assert header_store.write_log == []


def test_header_absent_fails_naming_it(mock_mcp):
    header_store = doctor_fixtures.FixtureHeaderStore()  # empty store, header=None

    checks = _config_checks(mock_mcp, header_store)

    check = _check_by_id(checks, "config.store_header")
    assert check["status"] == "fail"
    assert "missing" in check["detail"] or "empty" in check["detail"]
    assert header_store.write_log == []


def test_header_mismatch_names_a_missing_column(mock_mcp):
    header = [c for c in doctor_fixtures.EXPECTED_HEADER if c != "root_cause"]
    header_store = doctor_fixtures.FixtureHeaderStore(header=header)

    checks = _config_checks(mock_mcp, header_store)

    check = _check_by_id(checks, "config.store_header")
    assert check["status"] == "fail"
    assert "root_cause" in check["detail"]
    assert header_store.write_log == []


def test_header_mismatch_names_an_extra_column(mock_mcp):
    header = list(doctor_fixtures.EXPECTED_HEADER)
    header.insert(3, "unexpected_column")
    header_store = doctor_fixtures.FixtureHeaderStore(header=header)

    checks = _config_checks(mock_mcp, header_store)

    check = _check_by_id(checks, "config.store_header")
    assert check["status"] == "fail"
    assert "unexpected_column" in check["detail"]
    assert header_store.write_log == []


def test_header_mismatch_names_misordered_columns(mock_mcp):
    # Same column set, two schema columns transposed — no missing, no extra:
    # only the order-deviation branch can catch this (SC-003 exact mismatch).
    header = list(doctor_fixtures.EXPECTED_HEADER)
    header[0], header[1] = header[1], header[0]
    header_store = doctor_fixtures.FixtureHeaderStore(header=header)

    checks = _config_checks(mock_mcp, header_store)

    check = _check_by_id(checks, "config.store_header")
    assert check["status"] == "fail"
    assert "order" in check["detail"].lower()
    assert header_store.write_log == []


def test_header_mismatch_names_the_wrong_sentinel(mock_mcp):
    header = list(doctor_fixtures.EXPECTED_HEADER)
    header[-1] = "bb.schema.v2"
    header_store = doctor_fixtures.FixtureHeaderStore(header=header)

    checks = _config_checks(mock_mcp, header_store)

    check = _check_by_id(checks, "config.store_header")
    assert check["status"] == "fail"
    assert "bb.schema.v2" in check["detail"]
    assert "bb.schema.v1" in check["detail"]
    assert header_store.write_log == []


# ---------------------------------------------------------------------------
# check_config -> diary readability
# ---------------------------------------------------------------------------


def test_diary_check_ok_on_healthy_mock(mock_mcp):
    header_store = doctor_fixtures.FixtureHeaderStore(
        header=list(doctor_fixtures.EXPECTED_HEADER)
    )

    checks = _config_checks(mock_mcp, header_store)

    check = _check_by_id(checks, "config.diary")
    assert check["status"] == "ok"
    assert "append_entry" in check["detail"]


def test_diary_check_fails_under_injected_credential_failure(mock_mcp):
    injector = doctor_fixtures.FailingProbeInjector(mock_mcp, failing_capability="diary")
    header_store = doctor_fixtures.FixtureHeaderStore(
        header=list(doctor_fixtures.EXPECTED_HEADER)
    )

    checks = _config_checks(injector, header_store)

    check = _check_by_id(checks, "config.diary")
    assert check["status"] == "fail"
    assert "responder credentials rejected" in check["detail"]


# ---------------------------------------------------------------------------
# check_config -> catalog parseability
# ---------------------------------------------------------------------------


def test_catalog_check_ok_on_parseable_fixture(mock_mcp):
    header_store = doctor_fixtures.FixtureHeaderStore(
        header=list(doctor_fixtures.EXPECTED_HEADER)
    )
    catalog_path = doctor_fixtures.config_fixture_path("catalog-valid.json")

    checks = _config_checks(mock_mcp, header_store, catalog_path=catalog_path)

    check = _check_by_id(checks, "config.catalog")
    assert check["status"] == "ok"


def test_catalog_check_fails_naming_the_parse_problem(mock_mcp):
    header_store = doctor_fixtures.FixtureHeaderStore(
        header=list(doctor_fixtures.EXPECTED_HEADER)
    )
    catalog_path = doctor_fixtures.config_fixture_path("catalog-broken.json")

    checks = _config_checks(mock_mcp, header_store, catalog_path=catalog_path)

    check = _check_by_id(checks, "config.catalog")
    assert check["status"] == "fail"
    assert "catalog" in check["detail"]
    assert str(catalog_path) in check["detail"]


# ---------------------------------------------------------------------------
# check_config -> config-block well-formedness (malformed sentinel)
# ---------------------------------------------------------------------------


def test_config_wellformed_ok_on_valid_fixture(mock_mcp):
    header_store = doctor_fixtures.FixtureHeaderStore(
        header=list(doctor_fixtures.EXPECTED_HEADER)
    )

    checks = _config_checks(mock_mcp, header_store)

    check = _check_by_id(checks, "config.wellformed")
    assert check["status"] == "ok"


def test_config_malformed_is_a_repair_case_never_treated_as_absent(mock_mcp):
    # doctor_fixtures.load_config_fixture raises json.JSONDecodeError
    # unchanged for the malformed T005 fixture (test_doctor_fixtures.py
    # already pins this) — a caller catches it and passes the exception
    # itself through as the malformed sentinel (see doctor_flows.check_config
    # module comment: "malformed-config representation").
    try:
        doctor_fixtures.load_config_fixture("config-malformed.json")
        raise AssertionError("config-malformed.json fixture unexpectedly parsed")
    except json.JSONDecodeError as exc:
        config = exc

    header_store = doctor_fixtures.FixtureHeaderStore(
        header=list(doctor_fixtures.EXPECTED_HEADER)
    )
    catalog_path = doctor_fixtures.config_fixture_path("catalog-valid.json")

    checks = doctor_flows.check_config(mock_mcp, config, header_store, catalog_path)

    wellformed = _check_by_id(checks, "config.wellformed")
    assert wellformed["status"] == "fail"
    assert "line" in wellformed["detail"]  # json's own parse-error message

    # Repair case, never absent: the other three config checks still ran.
    assert len(checks) == 4
    assert _check_by_id(checks, "config.store_header")["status"] == "ok"
    assert _check_by_id(checks, "config.diary")["status"] == "ok"
    assert _check_by_id(checks, "config.catalog")["status"] == "ok"
    assert header_store.write_log == []


# ---------------------------------------------------------------------------
# check_versions: exact-match seam, migration-string format (US2 scenario 4)
# ---------------------------------------------------------------------------

PLUGIN_VERSION = "0.4.0"


def test_check_versions_ok_on_valid_config():
    config = doctor_fixtures.load_config_fixture("config-valid.json")

    checks = doctor_flows.check_versions(config, PLUGIN_VERSION)

    assert len(checks) == 2
    assert all(c["kind"] == "version" for c in checks)
    assert all(c["status"] == "ok" for c in checks)


def test_check_versions_future_version_fails_both_with_exact_migration_strings():
    config = doctor_fixtures.load_config_fixture("config-future-version.json")

    checks = doctor_flows.check_versions(config, PLUGIN_VERSION)
    by_id = {c["id"]: c for c in checks}

    assert by_id["version.config"]["status"] == "fail"
    assert (
        by_id["version.config"]["detail"]
        == "config block bb.config.v2 → bb.config.v1: run /setup --migrate"
    )

    assert by_id["version.store_schema"]["status"] == "fail"
    assert (
        by_id["version.store_schema"]["detail"]
        == "store schema bb.schema.v2 → bb.schema.v1: run /setup --migrate"
    )


# ---------------------------------------------------------------------------
# check_shell: ok / fail / skip; a skip never affects an assembled outcome
# ---------------------------------------------------------------------------


def test_check_shell_ok_when_answering():
    config = doctor_fixtures.load_config_fixture("config-valid.json")
    adapter = doctor_fixtures.FixtureShellAdapter(answering=True)

    check = doctor_flows.check_shell(config, adapter)

    assert check["kind"] == "shell"
    assert check["status"] == "ok"


def test_check_shell_fails_when_not_answering():
    config = doctor_fixtures.load_config_fixture("config-valid.json")
    adapter = doctor_fixtures.FixtureShellAdapter(answering=False)

    check = doctor_flows.check_shell(config, adapter)

    assert check["status"] == "fail"


def test_check_shell_skips_when_adapter_absent():
    config = doctor_fixtures.load_config_fixture("config-valid.json")

    check = doctor_flows.check_shell(config, None)

    assert check["status"] == "skip"


def test_check_shell_skips_when_config_has_no_shell_key():
    config = dict(doctor_fixtures.load_config_fixture("config-valid.json"))
    del config["shell"]
    adapter = doctor_fixtures.FixtureShellAdapter(answering=True)

    check = doctor_flows.check_shell(config, adapter)

    assert check["status"] == "skip"


def test_shell_skip_never_reds_an_assembled_report():
    manifest = {"required": {}, "optional": {}}
    shell_check = doctor_flows.check_shell({}, None)
    assert shell_check["status"] == "skip"

    report = doctor_flows.assemble_report(
        binding_checks=[],
        probe_checks=[],
        config_checks=[],
        version_checks=[],
        shell_check=shell_check,
        manifest=manifest,
        bindings={},
    )

    assert report["outcome"] == "green"


def test_check_versions_tolerates_non_dict_store_block():
    # Converge round 1: a malformed (non-dict) store sub-block must degrade to
    # a version-check fail, never raise (loud-not-crashed discipline).
    config = {"configVersion": "bb.config.v1", "store": "not-a-dict"}

    checks = doctor_flows.check_versions(config, "0.4.0")

    schema_check = next(c for c in checks if c["id"] == "version.store_schema")
    assert schema_check["status"] == "fail"
