"""US3 scenarios 1-3, FR-008: responder-mode `/setup`
(``tests/helpers/setup_flows.py`` ``responder_mode``, T017) against the real
``manifest/capabilities.json`` and ``bb-mock-mcp``.

Coverage:

- From valid-team-scope state (the T005 ``config-valid.json`` fixture, a
  matching header store), ``derive_mode`` selects ``"responder"`` when the
  stamp is missing (US3 scenario 1).
- ``responder_mode`` over a plain mock: per-capability probe outcomes land in
  the report (storage/diary/alerting ``ok``, artifacts ``skip``), the run is
  green, the stamp is written with all three ``bb.stamp.v1`` fields, and the
  mock's ``write_log`` is provably unchanged (zero mutating ops) — this mode
  creates no team resources (US3 scenario 1-2).
- ``responder_mode`` over a ``FailingProbeInjector`` (designating ``diary``):
  the report is ``red``, the failing check has kind ``"probe"`` — never
  ``"binding"`` — no stamp is written, and the write log is still unchanged.
- Distinctness (spec edge case: "Probe fails under this responder's
  credentials while the committed binding map is valid"): in that same
  failing run, the binding-kind checks (included via the optional drift
  re-check judgment call, since this workspace carries both a committed
  binding map and a matching roster) are all ``ok`` while the probe-kind
  check fails — the report distinguishes a responder-scope failure from a
  team-scope one in the same run.

Assertions are on the returned artifacts (the report dict, the on-disk
stamp, the mock's write log) only, never prose.
"""

import json
from pathlib import Path

from helpers import doctor_fixtures, setup_flows

PLUGIN_VERSION = "0.4.0"
AT = "2026-02-01T08:00:00Z"

_ROSTER_TEXT = json.dumps(
    {
        "mcpServers": {
            "mycorp_sheets": {
                "command": "npx",
                "args": ["-y", "@mycorp-sheets/mcp-server"],
                "env": {"MYCORP_SHEETS_TOKEN": "${MYCORP_SHEETS_TOKEN}"},
            }
        }
    }
)


def _team_scope_workspace(mock, tmp_path):
    """Valid team scope: config-valid.json's committed bindings, a matching
    store header, and a roster whose fixture tool names/shapes are exactly
    what config-valid.json's ``bindings`` map names (doctor_fixtures'
    ``REQUIRED_FIXTURE_TOOL_NAMES``) — so the committed binding map is
    genuinely still valid against this roster (the edge case's own premise).
    Responder scope (stamp) is absent — the T012 default."""
    config = doctor_fixtures.load_config_fixture("config-valid.json")
    header_store = doctor_fixtures.FixtureHeaderStore(
        header=list(doctor_fixtures.EXPECTED_HEADER)
    )
    roster = doctor_fixtures.build_full_roster(mock)
    return setup_flows.Workspace(
        config=config,
        header_store=header_store,
        roster=roster,
        roster_file_text=_ROSTER_TEXT,
        tmp_path=tmp_path,
    )


# ---------------------------------------------------------------------------
# derive_mode: valid team scope + absent responder scope ⇒ responder
# (US3 scenario 1)
# ---------------------------------------------------------------------------


def test_derive_mode_from_valid_team_scope_stamp_missing_is_responder(mock_mcp, tmp_path):
    workspace = _team_scope_workspace(mock_mcp, tmp_path)

    assert workspace.stamp_state == "missing"  # T012 default, unset here
    assert setup_flows.derive_mode(workspace) == "responder"


# ---------------------------------------------------------------------------
# responder_mode over a plain mock: probe outcomes, green, stamp written,
# write log unchanged
# ---------------------------------------------------------------------------


def test_responder_mode_plain_mock_probe_outcomes_green_stamp_written_write_log_unchanged(
    mock_mcp, tmp_path
):
    workspace = _team_scope_workspace(mock_mcp, tmp_path)
    write_log_before = list(mock_mcp.write_log.entries)

    result = setup_flows.responder_mode(mock_mcp, workspace, PLUGIN_VERSION, AT)

    write_log_after = list(mock_mcp.write_log.entries)
    assert write_log_before == [] == write_log_after

    report = result["report"]
    assert report["outcome"] == "green"

    probe_by_capability = {
        c["capability"]: c for c in report["checks"] if c["kind"] == "probe"
    }
    assert probe_by_capability["storage"]["status"] == "ok"
    assert probe_by_capability["diary"]["status"] == "ok"
    assert probe_by_capability["alerting"]["status"] == "ok"
    assert probe_by_capability["artifacts"]["status"] == "skip"

    assert result["stamp_wrote"] is True
    stamp_path = Path(result["stamp_path"])
    assert stamp_path.exists()
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    assert set(stamp.keys()) == {"schema", "at", "plugin_version", "roster_hash"}
    assert stamp["schema"] == "bb.stamp.v1"
    assert stamp["plugin_version"] == PLUGIN_VERSION
    assert stamp["roster_hash"] == result["roster_hash"]
    assert stamp["at"] == AT

    # Creates no team resources whatsoever.
    assert workspace.header_store.write_log == []
    assert workspace.config == doctor_fixtures.load_config_fixture("config-valid.json")


# ---------------------------------------------------------------------------
# responder_mode over FailingProbeInjector(diary): red, probe-kind (not
# binding-kind) failure, no stamp, write log unchanged
# ---------------------------------------------------------------------------


def test_responder_mode_failing_probe_injector_reports_red_probe_kind_not_binding(
    mock_mcp, tmp_path
):
    workspace = _team_scope_workspace(mock_mcp, tmp_path)
    injector = doctor_fixtures.FailingProbeInjector(mock_mcp, failing_capability="diary")
    write_log_before = list(mock_mcp.write_log.entries)

    result = setup_flows.responder_mode(injector, workspace, PLUGIN_VERSION, AT)

    write_log_after = list(mock_mcp.write_log.entries)
    assert write_log_before == [] == write_log_after

    report = result["report"]
    assert report["outcome"] == "red"

    failing_checks = [c for c in report["checks"] if c["status"] == "fail"]
    assert failing_checks, "expected at least one failing check"
    diary_probe_failures = [
        c for c in failing_checks if c["kind"] == "probe" and c["capability"] == "diary"
    ]
    assert len(diary_probe_failures) == 1
    assert "responder credentials rejected" in diary_probe_failures[0]["detail"]

    # The failure is responder-scope (probe-kind), never binding-kind.
    assert not any(c["kind"] == "binding" for c in failing_checks)

    assert result["stamp_wrote"] is False
    assert not Path(result["stamp_path"]).exists()


# ---------------------------------------------------------------------------
# Distinctness (spec edge case): binding-kind checks ok/present while the
# probe-kind check fails, in the very same run
# ---------------------------------------------------------------------------


def test_distinctness_binding_kind_ok_while_probe_kind_fails_same_run(mock_mcp, tmp_path):
    workspace = _team_scope_workspace(mock_mcp, tmp_path)
    injector = doctor_fixtures.FailingProbeInjector(mock_mcp, failing_capability="diary")

    result = setup_flows.responder_mode(injector, workspace, PLUGIN_VERSION, AT)
    report = result["report"]

    binding_checks = [c for c in report["checks"] if c["kind"] == "binding"]
    # This workspace's roster/config were built so the committed binding map
    # is still genuinely valid (the edge case's own premise) — the optional
    # drift re-check (setup_flows.responder_mode judgment call) is included
    # because workspace.config carries bindings and workspace.roster is
    # non-empty, so it must be non-empty and entirely "ok" here.
    assert binding_checks, "expected binding-kind checks to be included"
    assert all(c["status"] == "ok" for c in binding_checks)

    probe_checks = [
        c for c in report["checks"] if c["kind"] == "probe" and c["capability"] == "diary"
    ]
    assert len(probe_checks) == 1
    assert probe_checks[0]["status"] == "fail"

    # The report holds both in the same run, distinguishable by kind.
    assert report["outcome"] == "red"


# ---------------------------------------------------------------------------
# No binding-kind checks when the workspace carries no roster (judgment-call
# branch: the optional drift re-check is skipped entirely, never required)
# ---------------------------------------------------------------------------


def test_no_binding_checks_when_workspace_carries_no_roster(mock_mcp, tmp_path):
    config = doctor_fixtures.load_config_fixture("config-valid.json")
    header_store = doctor_fixtures.FixtureHeaderStore(
        header=list(doctor_fixtures.EXPECTED_HEADER)
    )
    workspace = setup_flows.Workspace(
        config=config,
        header_store=header_store,
        roster_file_text=_ROSTER_TEXT,
        tmp_path=tmp_path,
        # roster left at the Workspace default: {} (empty).
    )

    result = setup_flows.responder_mode(mock_mcp, workspace, PLUGIN_VERSION, AT)
    report = result["report"]

    assert not [c for c in report["checks"] if c["kind"] == "binding"]
    assert report["outcome"] == "green"
