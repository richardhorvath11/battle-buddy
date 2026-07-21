"""US1 scenarios 1-4, SC-003/SC-004/SC-007, FR-007: `/setup`'s team-mode
sequence (``tests/helpers/setup_flows.py`` ``team_mode``/``smoke_test``/
``scaffold_workspace``, T012) against the real ``manifest/capabilities.json``
and ``bb-mock-mcp``.

Coverage:

- Full-sequence order, both via the returned step trace and the mock's own
  ordered write log (binding resolution before header create; header create
  before config write; doctor+smoke last).
- Header created through the resolved storage binding, matching the
  documented column set exactly (SC-003 create path).
- Existing-correct store validates with zero writes (SC-003 validate path).
- Mismatched store: exact mismatch reported, zero writes, nothing
  re-created, run not green (US1 scenario 4).
- Config block: ``configVersion``, every contract-table key.
- Scaffold: exactly four files, settings.json carries the battleBuddy block,
  .mcp.json tokens are ``${ENV_VAR}`` refs with no opaque secret literals,
  .gitignore lines present, zero upstream content.
- Smoke test: `session_type: test` / `status: closed` row, all four
  documented paths exercised (write log), artifact link recorded on the row,
  read-back happened, and the row appears in no retrieval candidate set
  (SC-004, driven through slice-3's own ``store_flows.retrieve_candidates``).
- Single invocation from empty fixture state reaches green (SC-007).

Assertions are on the returned artifacts (steps, write log, files, report,
row dicts) only, never prose (BINDING CONSTRAINTS).
"""

import json
import re

import pytest

from helpers import doctor_fixtures, setup_flows, store_flows

PLUGIN_VERSION = "0.4.0"


def _fresh_workspace(tmp_path, header=None):
    header_store = doctor_fixtures.FixtureHeaderStore(header=header)
    return setup_flows.Workspace(tmp_path=tmp_path, header_store=header_store)


# ---------------------------------------------------------------------------
# SC-007: single invocation from empty fixture state reaches green
# ---------------------------------------------------------------------------


def test_single_invocation_from_empty_state_reaches_green_sc007(mock_mcp, tmp_path):
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    workspace = _fresh_workspace(tmp_path)

    result = setup_flows.team_mode(mock_mcp, workspace, roster, {}, PLUGIN_VERSION)

    assert result["green"] is True
    assert result["failure"] is None
    assert result["report"]["outcome"] == "green"


# ---------------------------------------------------------------------------
# Full sequence order: step trace AND mock write log
# ---------------------------------------------------------------------------


def test_full_sequence_step_order_and_write_log_order(mock_mcp, tmp_path):
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    workspace = _fresh_workspace(tmp_path)

    result = setup_flows.team_mode(mock_mcp, workspace, roster, {}, PLUGIN_VERSION)

    step_names = [s["step"] for s in result["steps"]]
    assert step_names == [
        "resolve_bindings",
        "store_header",
        "artifact_root",
        "diary_catalog_prompts",
        "config_write",
        "scaffold",
        "doctor",
        "smoke_test",
    ]
    assert step_names.index("resolve_bindings") < step_names.index("store_header")
    assert step_names.index("store_header") < step_names.index("config_write")
    assert step_names[-2:] == ["doctor", "smoke_test"]

    # The mock's write log only ever sees the smoke test's mutating ops (the
    # header lives on the FixtureHeaderStore, not the mock; every doctor/
    # binding-resolution step is read-only) — in the smoke test's own pinned
    # order.
    ops = [(e["capability"], e["op"]) for e in mock_mcp.write_log.entries]
    assert ops == [
        ("storage", "append_record"),
        ("artifacts", "put_file"),
        ("storage", "update_record"),
        ("diary", "append_entry"),
    ]


# ---------------------------------------------------------------------------
# Header creation through the resolved storage binding (SC-003 create path)
# ---------------------------------------------------------------------------


def test_header_created_through_storage_binding_matches_documented_columns(
    mock_mcp, tmp_path
):
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    workspace = _fresh_workspace(tmp_path)

    result = setup_flows.team_mode(mock_mcp, workspace, roster, {}, PLUGIN_VERSION)

    create_step = next(s for s in result["steps"] if s["step"] == "store_header")
    assert create_step["action"] == "create"
    assert create_step["via_binding"] == result["bindings"]["storage.append_record"]
    assert list(create_step["header"]) == list(doctor_fixtures.EXPECTED_HEADER)
    assert workspace.header_store.header == list(doctor_fixtures.EXPECTED_HEADER)
    assert workspace.header_store.write_log == [list(doctor_fixtures.EXPECTED_HEADER)]


# ---------------------------------------------------------------------------
# Existing-correct store validates with zero writes (SC-003 validate path)
# ---------------------------------------------------------------------------


def test_existing_correct_store_validates_with_zero_writes(mock_mcp, tmp_path):
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    workspace = _fresh_workspace(tmp_path, header=list(doctor_fixtures.EXPECTED_HEADER))

    result = setup_flows.team_mode(mock_mcp, workspace, roster, {}, PLUGIN_VERSION)

    validate_step = next(s for s in result["steps"] if s["step"] == "store_header")
    assert validate_step["action"] == "validate"
    assert validate_step["check"]["status"] == "ok"
    assert workspace.header_store.write_log == []
    assert result["green"] is True


# ---------------------------------------------------------------------------
# Mismatched store: exact mismatch, zero writes, nothing re-created
# (US1 scenario 4)
# ---------------------------------------------------------------------------


def test_mismatched_store_reports_exact_mismatch_zero_writes_nothing_recreated(
    mock_mcp, tmp_path
):
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    bad_header = [c for c in doctor_fixtures.EXPECTED_HEADER if c != "root_cause"]
    workspace = _fresh_workspace(tmp_path, header=bad_header)

    result = setup_flows.team_mode(mock_mcp, workspace, roster, {}, PLUGIN_VERSION)

    assert result["green"] is False
    assert "root_cause" in result["failure"]

    # Zero writes, nothing re-created — the run is over.
    assert workspace.header_store.write_log == []
    assert workspace.header_store.header == bad_header
    assert mock_mcp.write_log.entries == []

    step_names = [s["step"] for s in result["steps"]]
    assert step_names == ["resolve_bindings", "store_header"]
    assert result["config"] is None
    assert result["scaffold_paths"] is None
    assert result["report"] is None
    assert result["smoke"] is None


# ---------------------------------------------------------------------------
# Config block: configVersion + every contract-table key
# ---------------------------------------------------------------------------


def test_config_block_has_config_version_and_contract_table_keys(mock_mcp, tmp_path):
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    workspace = _fresh_workspace(tmp_path)

    result = setup_flows.team_mode(
        mock_mcp, workspace, roster, {"shell_adapter_name": "cmux"}, PLUGIN_VERSION
    )

    config = result["config"]
    assert config["configVersion"] == "bb.config.v1"
    for key in (
        "configVersion",
        "pluginPin",
        "store",
        "diary",
        "catalog",
        "artifactRoot",
        "bindings",
        "budgets",
        "shell",
    ):
        assert key in config, key

    assert config["pluginPin"] == PLUGIN_VERSION
    assert config["store"]["schemaVersion"] == store_flows.SCHEMA_VERSION
    assert config["budgets"]["triageTurnCap"] == 15
    assert config["shell"] == {"adapter": "cmux"}
    # workspace.config mirrors the just-written block (derive_mode reads this).
    assert workspace.config == config
    # An unconfigured shell *adapter* still only skips (never fails) even
    # though the config block names one — this run is still green.
    assert result["green"] is True


# ---------------------------------------------------------------------------
# Scaffold: exactly four files, expected shapes, zero upstream content
# ---------------------------------------------------------------------------


def test_scaffold_exactly_four_files_with_expected_shapes(mock_mcp, tmp_path):
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    workspace = _fresh_workspace(tmp_path)

    result = setup_flows.team_mode(mock_mcp, workspace, roster, {}, PLUGIN_VERSION)
    assert result["green"] is True

    # Exactly the four *scaffold* files scaffold_workspace itself writes.
    scaffold_files = set(result["scaffold_paths"].values())
    assert len(scaffold_files) == 4

    # FR-005 (T016): a green doctor run also writes the local, gitignored,
    # never-committed `.bb-doctor-stamp.json` runtime dropping at the
    # workspace root (contracts/doctor-protocol.md "Green stamp") — team_mode
    # wires this in right after its doctor step reports green. That stamp
    # sits outside scaffold_workspace's own four-file output (it is never one
    # of the paths that function returns, and .gitignore already excludes it
    # from the repo below), so the workspace directory as a whole now holds
    # the four scaffold files *plus* this one uncommitted stamp — five files,
    # not four. Updating this expectation (rather than leaving it at 4) is
    # the narrowly-scoped, justified exception T016 calls for.
    all_files = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert len(all_files) == 5
    stamp_path = tmp_path / ".bb-doctor-stamp.json"
    assert stamp_path.exists()
    assert stamp_path not in scaffold_files
    assert set(all_files) == scaffold_files | {stamp_path}

    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert settings["battleBuddy"]["configVersion"] == "bb.config.v1"
    assert settings["battleBuddy"] == result["config"]

    mcp_text = (tmp_path / ".mcp.json").read_text()
    mcp = json.loads(mcp_text)
    assert "mcpServers" in mcp
    assert mcp["mcpServers"], "full roster must yield at least one server entry"

    token_pattern = re.compile(r"^\$\{[A-Z0-9_]+\}$")
    opaque_secret_pattern = re.compile(r'"[A-Za-z0-9+/=]{20,}"')
    for server in mcp["mcpServers"].values():
        for value in server.get("env", {}).values():
            assert token_pattern.match(value), "not an ${ENV_VAR} ref: {!r}".format(value)
    assert not opaque_secret_pattern.search(mcp_text), "opaque literal secret-looking value found"

    gitignore_lines = (tmp_path / ".gitignore").read_text().splitlines()
    for line in (".bb-session/", ".bb-doctor-stamp.json", "*.local.jsonl"):
        assert line in gitignore_lines

    readme_text = (tmp_path / "README.md").read_text()
    assert "private" in readme_text.lower()


# ---------------------------------------------------------------------------
# Smoke test: session_type/status, write-log paths, artifact link, read-back
# ---------------------------------------------------------------------------


def test_smoke_test_row_session_type_test_and_status_closed(mock_mcp, tmp_path):
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    workspace = _fresh_workspace(tmp_path)

    result = setup_flows.team_mode(mock_mcp, workspace, roster, {}, PLUGIN_VERSION)

    smoke = result["smoke"]
    assert smoke["green"] is True
    row = smoke["row"]
    assert row["session_type"] == "test"
    assert row["status"] == "closed"

    ops_seen = {(e["capability"], e["op"]) for e in mock_mcp.write_log.entries}
    assert ("storage", "append_record") in ops_seen
    assert ("artifacts", "put_file") in ops_seen
    assert ("diary", "append_entry") in ops_seen


def test_smoke_test_artifact_link_recorded_on_row_and_readback_happened(mock_mcp, tmp_path):
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    workspace = _fresh_workspace(tmp_path)

    result = setup_flows.team_mode(mock_mcp, workspace, roster, {}, PLUGIN_VERSION)

    smoke = result["smoke"]
    link = smoke["artifact_link"]
    assert link is not None
    row = smoke["row"]
    assert any(entry["url"] == link for entry in row["links"])

    # get_file is harness surface only — an extra oracle, never the
    # documented smoke path itself (contract doc "Smoke test").
    fetched = mock_mcp.invoke("artifacts", "get_file", {"link": link})
    assert "error" not in fetched

    read_ops = [t for t in smoke["trace"] if t["op"] == "storage.read_records"]
    assert len(read_ops) == 1
    assert read_ops[0]["result"]["records"][0]["session_id"] == smoke["session_id"]


def test_smoke_row_appears_in_no_retrieval_candidate_set_sc004(mock_mcp, tmp_path):
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    workspace = _fresh_workspace(tmp_path)

    result = setup_flows.team_mode(mock_mcp, workspace, roster, {}, PLUGIN_VERSION)
    row = result["smoke"]["row"]

    # A "matching-ish" query built from the smoke row's own fields — if the
    # session_type: test exclusion (slice-3 retrieval.md stage 0) weren't
    # applied, this exact query would otherwise stage-1-hit its own row.
    retrieval = store_flows.retrieve_candidates(
        mock_mcp,
        fingerprint=row["fingerprint"],
        catalog_resolved=row["catalog_resolved"],
        services=row["services"],
        alert_signature=row["alert_signature"],
        severity=row["severity"],
    )

    ids = [r["session_id"] for r in retrieval["candidates"]]
    assert row["session_id"] not in ids
    assert retrieval["total_matched"] == 0


# ---------------------------------------------------------------------------
# derive_mode — FR-006 / US1 acceptance scenario 1 (mode by inspection,
# never a stored done-flag) + the malformed-config repair discrimination
# (review finding: the derivation table itself must be under test)
# ---------------------------------------------------------------------------


def test_derive_mode_no_config_is_team(tmp_path):
    workspace = setup_flows.Workspace(config=None, tmp_path=tmp_path)
    assert setup_flows.derive_mode(workspace) == "team"


def test_derive_mode_malformed_config_is_repair_never_team(tmp_path):
    try:
        json.loads("{ this is not json")
    except json.JSONDecodeError as exc:
        malformed = exc
    workspace = setup_flows.Workspace(config=malformed, tmp_path=tmp_path)
    assert setup_flows.derive_mode(workspace) == "repair"


def test_derive_mode_config_present_stamp_missing_is_responder(tmp_path):
    config = doctor_fixtures.load_config_fixture("config-valid.json")
    workspace = setup_flows.Workspace(
        config=config, tmp_path=tmp_path, probes_ok=True, stamp_state="missing"
    )
    assert setup_flows.derive_mode(workspace) == "responder"


def test_derive_mode_everything_green_is_already_set_up(tmp_path):
    config = doctor_fixtures.load_config_fixture("config-valid.json")
    workspace = setup_flows.Workspace(
        config=config, tmp_path=tmp_path, probes_ok=True, stamp_state="fresh"
    )
    assert setup_flows.derive_mode(workspace) == "already-set-up"


# ---------------------------------------------------------------------------
# Loud-failure guardrails (SC-003 "through the resolved storage binding" as a
# hard guarantee, not a hope). Header creation is exercised through team_mode
# (it fails at step (b), before the smoke test is ever reached); smoke_test's
# own guardrails are exercised directly below, since inside team_mode a
# missing binding reds the run earlier.
# ---------------------------------------------------------------------------


def test_header_creation_without_storage_binding_fails_loudly(mock_mcp, tmp_path):
    roster = doctor_fixtures.build_roster_missing(
        mock_mcp, "storage", "append_record"
    )
    workspace = _fresh_workspace(tmp_path)  # empty header store -> create path

    with pytest.raises(RuntimeError):
        setup_flows.team_mode(mock_mcp, workspace, roster, {}, PLUGIN_VERSION)


def test_smoke_test_without_storage_binding_raises(mock_mcp):
    with pytest.raises(RuntimeError):
        setup_flows.smoke_test(mock_mcp, {}, "battle-buddy/", "2026-07-21")


def _full_bindings():
    return dict(doctor_fixtures.required_bindings())


def test_smoke_test_mutating_op_error_is_loud_and_specific(mock_mcp):
    # A binding that resolved fine but whose tool errors at runtime is
    # exactly the case the smoke test exists to catch (the probes could only
    # schema-match mutating ops). Fail the artifacts capability -> put_file
    # errors -> the failure names that path specifically.
    failing = doctor_fixtures.FailingProbeInjector(mock_mcp, "artifacts")

    outcome = setup_flows.smoke_test(
        failing, _full_bindings(), "battle-buddy/", "2026-07-21"
    )

    assert outcome["green"] is False
    assert "put_file failed" in outcome["failure"]


def test_smoke_test_readback_error_is_loud_and_specific(mock_mcp):
    # Error only on storage.read_records (append must succeed first), so the
    # read-back error-envelope branch is the one that fires.
    class _ReadbackFails:
        def __init__(self, wrapped):
            self._wrapped = wrapped

        def invoke(self, capability, op, payload):
            if capability == "storage" and op == "read_records":
                return {
                    "error": {
                        "op": op,
                        "code": "invalid_input",
                        "message": "simulated read-back outage",
                    }
                }
            return self._wrapped.invoke(capability, op, payload)

        def __getattr__(self, name):
            return getattr(self._wrapped, name)

    outcome = setup_flows.smoke_test(
        _ReadbackFails(mock_mcp), _full_bindings(), "battle-buddy/", "2026-07-21"
    )

    assert outcome["green"] is False
    assert "read_records failed: simulated read-back outage" == outcome["failure"]
