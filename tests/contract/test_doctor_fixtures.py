"""Smoke test for the slice-4 fixture surfaces (tests/helpers/doctor_fixtures.py,
T004) and the T005 config-block fixtures — Constitution VIII: this new dev-only
surface ships with its own tests in the same change, and later doctor/setup tasks
(T006+) lean on these builders directly.

Not a test of the doctor/setup protocol itself (that lands with doctor_flows.py /
setup_flows.py in later tasks) — only that every fixture surface produces the shape
its docstring promises.
"""

import json

import pytest

from helpers import doctor_fixtures

# A literal manifest fragment shaped like bb.capabilities.v1's optional half
# (design §7.1 / research R7) — manifest/capabilities.json itself is a later task
# (T002); this is a fixture-only stand-in exercising build_roster_with_optional's
# "shapes come from the manifest, not describe()" contract.
OPTIONAL_MANIFEST = {
    "optional": {
        "code": {
            "ops": {
                "read_file": {
                    "input": {"path": {"type": "str", "required": True}},
                    "output": {"content": {"type": "str", "required": True}},
                },
                "list_commits": {
                    "input": {"window": {"type": "int", "required": True}},
                    "output": {"commits": {"type": "list", "required": True}},
                },
                "search": {
                    "input": {"query": {"type": "str", "required": True}},
                    "output": {"matches": {"type": "list", "required": True}},
                },
            },
            "enables": ["deploy correlation", "catalog", "runbook fetch"],
        },
        "observability": {
            "ops": {
                "query_metrics": {
                    "input": {"query": {"type": "str", "required": True}},
                    "output": {"points": {"type": "list", "required": True}},
                },
                "search_logs": {
                    "input": {"query": {"type": "str", "required": True}},
                    "output": {"lines": {"type": "list", "required": True}},
                },
            },
            "enables": ["metric reads", "evidence deep-links"],
        },
    }
}


# ---------------------------------------------------------------------------
# Roster builders (R8)
# ---------------------------------------------------------------------------


def test_build_full_roster_shapes_equal_describe(mock_mcp):
    surface = mock_mcp.describe()
    roster = doctor_fixtures.build_full_roster(mock_mcp)

    # One fixture tool per required op, names distinct from op names.
    assert len(roster) == len(doctor_fixtures.REQUIRED_FIXTURE_TOOL_NAMES)
    for (capability, op), tool_name in doctor_fixtures.REQUIRED_FIXTURE_TOOL_NAMES.items():
        assert tool_name != op, "fixture tool name must not equal the op name"
        assert tool_name in roster
        assert roster[tool_name] == surface[capability][op]

    # artifacts.get_file is test-only harness surface, excluded from the roster.
    assert ("artifacts", "get_file") not in doctor_fixtures.REQUIRED_FIXTURE_TOOL_NAMES
    assert surface["artifacts"]["get_file"] not in roster.values()


def test_required_bindings_matches_config_valid_fixture():
    config = doctor_fixtures.load_config_fixture("config-valid.json")
    assert config["bindings"] == doctor_fixtures.required_bindings()


def test_build_roster_missing_drops_exactly_that_tool(mock_mcp):
    roster = doctor_fixtures.build_roster_missing(mock_mcp, "storage", "append_record")
    missing_tool = doctor_fixtures.REQUIRED_FIXTURE_TOOL_NAMES[("storage", "append_record")]
    assert missing_tool not in roster
    # every other required tool is still present
    full = doctor_fixtures.build_full_roster(mock_mcp)
    assert set(full) - {missing_tool} == set(roster)


def test_build_roster_multi_match_adds_identical_second_tool(mock_mcp):
    roster = doctor_fixtures.build_roster_multi_match(mock_mcp, "diary", "append_entry")
    original = doctor_fixtures.REQUIRED_FIXTURE_TOOL_NAMES[("diary", "append_entry")]
    candidates = [name for name, shape in roster.items() if shape == roster[original]]
    assert len(candidates) == 2
    assert original in candidates


def test_build_roster_with_optional_adds_manifest_shaped_tools(mock_mcp):
    roster = doctor_fixtures.build_roster_with_optional(mock_mcp, OPTIONAL_MANIFEST)

    full = doctor_fixtures.build_full_roster(mock_mcp)
    assert set(full) <= set(roster)  # every required tool still present

    for (capability, op), tool_name in doctor_fixtures.OPTIONAL_FIXTURE_TOOL_NAMES.items():
        expected_shape = OPTIONAL_MANIFEST["optional"][capability]["ops"][op]
        assert roster[tool_name] == {
            "input": expected_shape["input"],
            "output": expected_shape["output"],
        }


def test_build_roster_drifted_removes_bound_tool(mock_mcp):
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    bindings = doctor_fixtures.required_bindings()
    drifted = doctor_fixtures.build_roster_drifted(roster, bindings, "storage", "append_record")

    bound_tool = bindings["storage.append_record"]
    assert bound_tool not in drifted
    # original roster untouched
    assert bound_tool in roster


def test_build_roster_drifted_can_rename_instead_of_remove(mock_mcp):
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    bindings = doctor_fixtures.required_bindings()
    bound_tool = bindings["storage.append_record"]
    original_shape = roster[bound_tool]

    drifted = doctor_fixtures.build_roster_drifted(
        roster, bindings, "storage", "append_record", rename_to="renamed_tool.op"
    )
    assert bound_tool not in drifted
    assert drifted["renamed_tool.op"] == original_shape


# ---------------------------------------------------------------------------
# FixtureHeaderStore (R5)
# ---------------------------------------------------------------------------


def test_fixture_header_store_starts_empty():
    store = doctor_fixtures.FixtureHeaderStore()
    assert store.read_header() is None
    assert store.write_log == []


def test_fixture_header_store_create_then_read_round_trips():
    store = doctor_fixtures.FixtureHeaderStore()
    written = store.create_header(doctor_fixtures.EXPECTED_HEADER)
    assert written == doctor_fixtures.EXPECTED_HEADER
    assert store.read_header() == doctor_fixtures.EXPECTED_HEADER
    assert store.write_log == [doctor_fixtures.EXPECTED_HEADER]


def test_expected_header_is_columns_then_sentinel():
    from helpers import store_flows

    # Construction-independent: schema columns fill the first cells in order,
    # and the literal sentinel sits exactly one column past the last of them.
    n = len(store_flows.COLUMN_NAMES)
    assert tuple(doctor_fixtures.EXPECTED_HEADER[:n]) == store_flows.COLUMN_NAMES
    assert len(doctor_fixtures.EXPECTED_HEADER) == n + 1
    assert doctor_fixtures.EXPECTED_HEADER[n] == "bb.schema.v1"


def test_fixture_header_store_preexisting_header_is_read_only():
    store = doctor_fixtures.FixtureHeaderStore(header=list(doctor_fixtures.EXPECTED_HEADER))
    assert store.read_header() == doctor_fixtures.EXPECTED_HEADER
    assert store.write_log == []  # constructing with a header is not a write


# ---------------------------------------------------------------------------
# FixtureShellAdapter (R12)
# ---------------------------------------------------------------------------


def test_fixture_shell_adapter_answering_echoes():
    adapter = doctor_fixtures.FixtureShellAdapter(answering=True)
    assert adapter.notify("ping") == "ping"
    assert adapter.calls == ["ping"]


def test_fixture_shell_adapter_not_answering_raises():
    adapter = doctor_fixtures.FixtureShellAdapter(answering=False)
    with pytest.raises(Exception):
        adapter.notify("ping")


# ---------------------------------------------------------------------------
# FailingProbeInjector
# ---------------------------------------------------------------------------


def test_failing_probe_injector_fails_only_designated_capability(mock_mcp):
    injector = doctor_fixtures.FailingProbeInjector(mock_mcp, failing_capability="storage")

    result = injector.invoke("storage", "read_records", {"filter": {}})
    assert "error" in result
    assert result["error"]["op"] == "storage.read_records"

    # every other capability passes through unchanged
    diary_result = injector.invoke("diary", "read_recent", {"n": 1})
    assert "error" not in diary_result
    assert diary_result == mock_mcp.invoke("diary", "read_recent", {"n": 1})


def test_failing_probe_injector_passthrough_reaches_real_mock_state(mock_mcp):
    injector = doctor_fixtures.FailingProbeInjector(mock_mcp, failing_capability="alerting")

    # a non-failing capability's mutating call really reaches the wrapped mock
    result = injector.invoke(
        "diary", "append_entry", {"content": "note via injector"}
    )
    assert "error" not in result
    assert mock_mcp.diary.entries[-1]["content"] == "note via injector"

    # attribute passthrough exposes the same inspection surface as the real mock
    assert injector.write_log.entries == mock_mcp.write_log.entries


def test_failing_probe_injector_describe_passes_through(mock_mcp):
    injector = doctor_fixtures.FailingProbeInjector(mock_mcp, failing_capability="storage")
    assert injector.describe() == mock_mcp.describe()


# ---------------------------------------------------------------------------
# Config-block fixture loaders (T005)
# ---------------------------------------------------------------------------


def test_config_valid_fixture_has_full_protocol_v1_shape():
    config = doctor_fixtures.load_config_fixture("config-valid.json")
    assert config["configVersion"] == "bb.config.v1"
    assert config["store"]["schemaVersion"] == "bb.schema.v1"
    assert config["artifactRoot"] == "battle-buddy/"
    assert config["budgets"]["triageTurnCap"] == 15
    assert config["shell"]["adapter"] == "cmux"
    assert set(config["bindings"]) == set(doctor_fixtures.required_bindings())


def test_config_future_version_fixture_bumps_only_the_version_seam():
    valid = doctor_fixtures.load_config_fixture("config-valid.json")
    future = doctor_fixtures.load_config_fixture("config-future-version.json")

    assert future["configVersion"] == "bb.config.v2"
    assert future["store"]["schemaVersion"] == "bb.schema.v2"

    # everything else matches the valid fixture (only the version seam bumped)
    for key in ("pluginPin", "diary", "catalog", "artifactRoot", "bindings", "budgets", "shell"):
        assert future[key] == valid[key]


def test_config_malformed_fixture_raises_on_load():
    path = doctor_fixtures.config_fixture_path("config-malformed.json")
    with open(str(path), encoding="utf-8") as f:
        with pytest.raises(json.JSONDecodeError):
            json.load(f)

    with pytest.raises(json.JSONDecodeError):
        doctor_fixtures.load_config_fixture("config-malformed.json")
