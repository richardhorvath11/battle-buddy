"""US4 scenarios 1-2, FR-009, SC-005: `/setup`'s idempotence-by-inspection —
already-green validates and reports with zero writes, partial state does
only what's missing, and a malformed config is always the repair case, never
treated as absent (``tests/helpers/setup_flows.py`` ``validate_existing``/
``resume_partial``/``repair_report``, T020) against the real
``manifest/capabilities.json`` and ``bb-mock-mcp``.

Coverage:

- A full team_mode run to green, then a second run over the resulting state:
  ``derive_mode`` reads "already-set-up" (config present, header present,
  stamp fresh); ``validate_existing`` reports green and performs zero
  mutating operations — mock write log, header-store write log, and every
  file under the workspace are all unchanged (SC-005).
- Partial state (config present, store header missing): ``derive_mode``
  reads "team-partial"; ``resume_partial`` creates ONLY the header, through
  the config's already-committed storage binding (the trace names the
  binding's tool); no config write, no scaffold write, no smoke test; a
  second ``resume_partial`` afterwards is a no-op (write logs unchanged).
- Malformed config: ``derive_mode`` reads "repair"; ``repair_report`` names
  the parse error, performs zero operations, and — the spec edge case's
  exact trap — creates no team-mode resource even though the header store is
  EMPTY (the state that would otherwise select team mode if malformed were
  wrongly treated as absent).
- ``derive_mode`` discrimination retest: config present + header missing (+
  a roster) is "team-partial", never "responder"; config present + all team
  scope green + stamp missing is still "responder" (unchanged T012/T017
  behavior).

Assertions are on the returned artifacts (mode strings, step traces, report
dicts, write logs, on-disk file contents) only, never prose.
"""

import json

from helpers import doctor_fixtures, setup_flows

PLUGIN_VERSION = "0.4.0"


def _all_file_contents(tmp_path):
    """Every file under ``tmp_path``, by relative path, mapped to its text
    content — a content-based snapshot (not mtimes, which can be flaky at
    filesystem-timestamp resolution) used to assert "untouched" across a
    read-only run."""
    return {
        str(p.relative_to(tmp_path)): p.read_text(encoding="utf-8")
        for p in tmp_path.rglob("*")
        if p.is_file()
    }


# ---------------------------------------------------------------------------
# Already-set-up: second run is zero mutating ops + green (SC-005,
# US4 scenario 1)
# ---------------------------------------------------------------------------


def test_second_run_over_green_workspace_is_already_set_up_zero_mutating_ops_sc005(
    mock_mcp, tmp_path
):
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    header_store = doctor_fixtures.FixtureHeaderStore()
    workspace = setup_flows.Workspace(tmp_path=tmp_path, header_store=header_store)

    first = setup_flows.team_mode(mock_mcp, workspace, roster, {}, PLUGIN_VERSION)
    assert first["green"] is True

    # Snapshot post-run state before the second "run".
    write_log_before = list(mock_mcp.write_log.entries)
    header_write_log_before = list(workspace.header_store.write_log)
    files_before = _all_file_contents(tmp_path)

    # Construct the workspace to reflect what a caller would observe on a
    # second invocation: config present (already true — team_mode wrote it
    # onto workspace.config), store header present (already true), and the
    # stamp fresh (team_mode's doctor step just wrote a green stamp for
    # exactly this plugin_version/roster).
    workspace.stamp_state = "fresh"

    assert setup_flows.derive_mode(workspace) == "already-set-up"

    result = setup_flows.validate_existing(mock_mcp, workspace, PLUGIN_VERSION)

    assert result["mode"] == "already-set-up"
    assert result["green"] is True
    assert result["report"]["schema"] == "bb.doctor.report.v1"
    assert result["report"]["outcome"] == "green"

    # Zero mutating operations anywhere (SC-005).
    assert list(mock_mcp.write_log.entries) == write_log_before
    assert list(workspace.header_store.write_log) == header_write_log_before
    assert _all_file_contents(tmp_path) == files_before


# ---------------------------------------------------------------------------
# Partial state: config present, store header missing ⇒ team-partial;
# resume_partial creates ONLY the header (US4 scenario 2)
# ---------------------------------------------------------------------------


def _partial_team_workspace(mock, tmp_path):
    """Config present (config-valid.json), a roster whose fixture tool
    names/shapes match its committed ``bindings`` map exactly, and the
    scaffold files already on disk (a team workspace that was fully
    scaffolded and committed, but whose store — e.g. a recreated Sheet — has
    since lost its header) — but the store header itself is EMPTY. This is
    the exact partial state US4 scenario 2 and the contract doc's "Partial
    team state" note describe."""
    config = doctor_fixtures.load_config_fixture("config-valid.json")
    roster = doctor_fixtures.build_full_roster(mock)
    header_store = doctor_fixtures.FixtureHeaderStore()  # empty — missing header
    workspace = setup_flows.Workspace(
        config=config,
        header_store=header_store,
        roster=roster,
        tmp_path=tmp_path,
    )
    # The scaffold is already committed team state — pre-populate it so this
    # fixture reflects "config present" honestly (config being present
    # implies the workspace was already scaffolded).
    setup_flows.scaffold_workspace(tmp_path, config, roster)
    return workspace, config, roster


def test_partial_state_header_missing_is_team_partial_creates_only_header(
    mock_mcp, tmp_path
):
    workspace, config, roster = _partial_team_workspace(mock_mcp, tmp_path)

    # Discrimination hardening (review finding): point the committed binding
    # at a second, shape-identical roster tool. The committed map stays valid
    # (drift re-validation passes), but a FRESH resolution over this roster
    # would now see two candidates for storage.append_record and go
    # ambiguous — it could never silently produce this specific pick. The
    # via_binding assertion below therefore passes ONLY via the committed map.
    mycorp_tool = doctor_fixtures.REQUIRED_FIXTURE_TOOL_NAMES[
        ("storage", "append_record")
    ]
    roster["legacy_committed.append_row"] = dict(roster[mycorp_tool])
    workspace.roster = roster
    config["bindings"]["storage.append_record"] = "legacy_committed.append_row"

    assert setup_flows.derive_mode(workspace) == "team-partial"

    mock_write_log_before = list(mock_mcp.write_log.entries)
    scaffold_files_before = _all_file_contents(tmp_path)

    result = setup_flows.resume_partial(mock_mcp, workspace, roster, {}, PLUGIN_VERSION)

    assert result["mode"] == "team-partial"

    header_step = next(s for s in result["steps"] if s["step"] == "store_header")
    assert header_step["action"] == "create"
    # The trace names the binding's tool — the config's already-committed
    # binding, never a fresh resolution (the name is deliberately absent from
    # the roster, see above).
    assert header_step["via_binding"] == "legacy_committed.append_row"
    assert list(header_step["header"]) == list(doctor_fixtures.EXPECTED_HEADER)
    assert workspace.header_store.header == list(doctor_fixtures.EXPECTED_HEADER)
    assert workspace.header_store.write_log == [list(doctor_fixtures.EXPECTED_HEADER)]

    # No config write, no scaffold write (every scaffold file already
    # existed, so all four are "validated," none "created"), no smoke test.
    scaffold_step = next(s for s in result["steps"] if s["step"] == "scaffold")
    assert scaffold_step["created"] == []
    assert set(scaffold_step["validated"]) == {
        ".claude/settings.json",
        ".mcp.json",
        "README.md",
        ".gitignore",
    }
    assert not any(s["step"] == "smoke_test" for s in result["steps"])
    assert not any(s["step"] == "config_write" for s in result["steps"])

    # Zero mock-mutating operations, and every scaffold file's content is
    # byte-for-byte unchanged (only the header store — not the mock, not the
    # filesystem — was written to).
    assert list(mock_mcp.write_log.entries) == mock_write_log_before
    assert _all_file_contents(tmp_path) == scaffold_files_before

    assert result["report"]["schema"] == "bb.doctor.report.v1"
    assert result["green"] is True


def test_second_resume_partial_after_header_created_is_a_no_op(mock_mcp, tmp_path):
    workspace, config, roster = _partial_team_workspace(mock_mcp, tmp_path)
    assert setup_flows.derive_mode(workspace) == "team-partial"

    first = setup_flows.resume_partial(mock_mcp, workspace, roster, {}, PLUGIN_VERSION)
    header_step_1 = next(s for s in first["steps"] if s["step"] == "store_header")
    assert header_step_1["action"] == "create"

    # Now the header is present — a second resume_partial must be a no-op.
    header_write_log_before = list(workspace.header_store.write_log)
    mock_write_log_before = list(mock_mcp.write_log.entries)
    files_before = _all_file_contents(tmp_path)

    second = setup_flows.resume_partial(mock_mcp, workspace, roster, {}, PLUGIN_VERSION)

    header_step_2 = next(s for s in second["steps"] if s["step"] == "store_header")
    assert header_step_2["action"] == "validate"
    assert header_step_2["check"]["status"] == "ok"

    scaffold_step_2 = next(s for s in second["steps"] if s["step"] == "scaffold")
    assert scaffold_step_2["created"] == []

    assert list(workspace.header_store.write_log) == header_write_log_before
    assert list(mock_mcp.write_log.entries) == mock_write_log_before
    assert _all_file_contents(tmp_path) == files_before
    assert second["green"] is True


# ---------------------------------------------------------------------------
# Malformed config ⇒ repair: names the parse error, zero ops, no team-mode
# resource creation even with an EMPTY header store (the edge case's trap)
# ---------------------------------------------------------------------------


def test_malformed_config_is_repair_names_parse_error_zero_ops_no_team_mode_creation(
    mock_mcp, tmp_path
):
    try:
        doctor_fixtures.load_config_fixture("config-malformed.json")
        assert False, "config-malformed.json fixture must fail to parse"
    except json.JSONDecodeError as exc:
        malformed = exc

    # The exact trap: an EMPTY header store — the state that WOULD select
    # team mode if the malformed config were (wrongly) treated as absent.
    header_store = doctor_fixtures.FixtureHeaderStore()
    workspace = setup_flows.Workspace(
        config=malformed, header_store=header_store, tmp_path=tmp_path
    )

    assert setup_flows.derive_mode(workspace) == "repair"

    mock_write_log_before = list(mock_mcp.write_log.entries)

    result = setup_flows.repair_report(workspace)

    assert result["mode"] == "repair"
    assert result["green"] is False
    assert result["check"]["kind"] == "config"
    assert result["check"]["status"] == "fail"
    # Names the exact parse error, never a generic "setup failed" message.
    assert str(malformed) in result["check"]["detail"]

    # Zero operations of any kind — and clearly not team mode: the header
    # store stays exactly as empty as it started; nothing was created.
    assert list(mock_mcp.write_log.entries) == mock_write_log_before
    assert workspace.header_store.write_log == []
    assert workspace.header_store.header is None
    assert list(tmp_path.rglob("*")) == []


# ---------------------------------------------------------------------------
# derive_mode discrimination retest
# ---------------------------------------------------------------------------


def test_derive_mode_config_present_header_missing_with_roster_is_team_partial(
    mock_mcp, tmp_path
):
    config = doctor_fixtures.load_config_fixture("config-valid.json")
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    header_store = doctor_fixtures.FixtureHeaderStore()  # missing

    workspace = setup_flows.Workspace(
        config=config, header_store=header_store, roster=roster, tmp_path=tmp_path
    )

    assert setup_flows.derive_mode(workspace) == "team-partial"
    assert setup_flows.derive_mode(workspace) != "responder"


def test_derive_mode_config_present_all_team_scope_green_stamp_missing_is_still_responder(
    mock_mcp, tmp_path
):
    config = doctor_fixtures.load_config_fixture("config-valid.json")
    roster = doctor_fixtures.build_full_roster(mock_mcp)
    header_store = doctor_fixtures.FixtureHeaderStore(
        header=list(doctor_fixtures.EXPECTED_HEADER)
    )

    workspace = setup_flows.Workspace(
        config=config,
        header_store=header_store,
        roster=roster,
        tmp_path=tmp_path,
        stamp_state="missing",
    )

    # Team scope (header + roster/bindings) is complete here — unchanged
    # T012/T017 behavior: still responder, never team-partial.
    assert setup_flows.derive_mode(workspace) == "responder"
