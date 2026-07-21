"""US1 preflight (spec FR-001, AS-1/AS-2; contracts/lifecycle-protocol.md
"Preflight decision table"; research R8, R11).

Drives ``lifecycle_flows.preflight`` — never the command prose — against
fixture config blocks, a real ``doctor_flows``-written green stamp, and a
local ``marker.json`` file, asserting purely on the returned outcome dict and
on-disk artifacts (stamp bytes, marker bytes, mock write log), never prose
(Constitution VIII).

The happy-path test proves SC-002's "zero probe calls" *structurally*, not
just by assertion: ``preflight`` doesn't even take a ``mock``/``responder_
mode_fn`` reference in that call, so there is no route by which it could
reach the mock at all when the stamp is already fresh — if the implementation
ever mistakenly tried to auto-run responder-mode on a fresh stamp, the call
would raise (``responder_mode_fn`` is None) rather than silently probing.
"""

import json

from helpers import doctor_fixtures, doctor_flows, lifecycle_flows, setup_flows

PLUGIN_VERSION = "0.4.0"
AT = "2026-07-21T08:00:00Z"

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


def _valid_config():
    return doctor_fixtures.load_config_fixture("config-valid.json")


def _malformed_config():
    try:
        return doctor_fixtures.load_config_fixture("config-malformed.json")
    except json.JSONDecodeError as exc:
        return exc


def _fresh_stamp(tmp_path):
    """A stamp file matching PLUGIN_VERSION/roster hash exactly — built with
    the real ``doctor_flows.write_stamp``, never hand-written JSON."""
    roster_hash_value = doctor_flows.roster_hash(_ROSTER_TEXT)
    stamp_path = tmp_path / ".bb-doctor-stamp.json"
    doctor_flows.write_stamp(stamp_path, PLUGIN_VERSION, roster_hash_value, AT)
    return stamp_path, roster_hash_value


# ---------------------------------------------------------------------------
# Happy path: valid config + fresh stamp -> zero probes, no doctor report,
# stamp byte-unchanged (SC-002).
# ---------------------------------------------------------------------------


def test_happy_path_zero_probes_stamp_unchanged_no_doctor_report(mock_mcp, tmp_path):
    state_dir = tmp_path / "session"
    stamp_path, roster_hash_value = _fresh_stamp(tmp_path)
    stamp_bytes_before = stamp_path.read_bytes()
    write_log_before = list(mock_mcp.write_log.entries)

    # No mock/responder_mode_fn passed at all — structurally proves preflight
    # cannot have reached the mock on this path (see module docstring).
    result = lifecycle_flows.preflight(
        config=_valid_config(),
        state_dir=state_dir,
        stamp_path=stamp_path,
        plugin_version=PLUGIN_VERSION,
        current_roster_hash=roster_hash_value,
    )

    assert result["proceed"] is True
    assert result["responder_mode_ran"] is False
    assert result["stamp_state"] == "fresh"
    assert result["stopped_reason"] is None

    assert stamp_path.read_bytes() == stamp_bytes_before
    assert mock_mcp.write_log.entries == write_log_before
    assert not (state_dir / "marker.json").exists()
    assert not state_dir.exists()  # preflight creates no session artifacts


# ---------------------------------------------------------------------------
# Row 1: no config -> stop naming /setup, zero session artifacts.
# ---------------------------------------------------------------------------


def test_missing_config_stops_naming_setup_zero_artifacts(mock_mcp, tmp_path):
    state_dir = tmp_path / "session"
    stamp_path = tmp_path / ".bb-doctor-stamp.json"
    write_log_before = list(mock_mcp.write_log.entries)

    result = lifecycle_flows.preflight(
        config=None,
        state_dir=state_dir,
        stamp_path=stamp_path,
        plugin_version=PLUGIN_VERSION,
        current_roster_hash="0" * 16,
    )

    assert result["proceed"] is False
    assert "/setup" in result["stopped_reason"]
    assert result["responder_mode_ran"] is False
    assert not state_dir.exists()
    assert mock_mcp.write_log.entries == write_log_before


# ---------------------------------------------------------------------------
# Row 2: malformed config -> repair stop.
# ---------------------------------------------------------------------------


def test_malformed_config_repair_stop(tmp_path):
    state_dir = tmp_path / "session"
    stamp_path = tmp_path / ".bb-doctor-stamp.json"

    result = lifecycle_flows.preflight(
        config=_malformed_config(),
        state_dir=state_dir,
        stamp_path=stamp_path,
        plugin_version=PLUGIN_VERSION,
        current_roster_hash="0" * 16,
    )

    assert result["proceed"] is False
    assert "malformed" in result["stopped_reason"].lower()
    assert not state_dir.exists()


# ---------------------------------------------------------------------------
# Row 5: missing stamp -> responder_mode_ran True, then proceeds.
# ---------------------------------------------------------------------------


def _team_scope_workspace(mock, tmp_path):
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


def test_missing_stamp_auto_runs_responder_mode_then_proceeds(mock_mcp, tmp_path):
    state_dir = tmp_path / "session"
    stamp_path = tmp_path / ".bb-doctor-stamp.json"
    assert not stamp_path.exists()

    workspace = _team_scope_workspace(mock_mcp, tmp_path)
    responder_mode_fn = lifecycle_flows.default_responder_mode_fn(
        mock_mcp, workspace, PLUGIN_VERSION, AT
    )
    roster_hash_value = doctor_flows.roster_hash(_ROSTER_TEXT)

    result = lifecycle_flows.preflight(
        config=_valid_config(),
        state_dir=state_dir,
        stamp_path=stamp_path,
        plugin_version=PLUGIN_VERSION,
        current_roster_hash=roster_hash_value,
        responder_mode_fn=responder_mode_fn,
    )

    assert result["responder_mode_ran"] is True
    assert result["proceed"] is True
    assert result["stamp_state"] == "fresh"
    assert stamp_path.exists()


# ---------------------------------------------------------------------------
# Row 5: stale stamp (version/hash mismatch) -> same.
# ---------------------------------------------------------------------------


def test_stale_stamp_version_mismatch_auto_runs_responder_mode_then_proceeds(
    mock_mcp, tmp_path
):
    state_dir = tmp_path / "session"
    stamp_path = tmp_path / ".bb-doctor-stamp.json"
    stale_roster_hash = doctor_flows.roster_hash(_ROSTER_TEXT)
    doctor_flows.write_stamp(stamp_path, "0.1.0", stale_roster_hash, AT)  # old plugin version

    workspace = _team_scope_workspace(mock_mcp, tmp_path)
    responder_mode_fn = lifecycle_flows.default_responder_mode_fn(
        mock_mcp, workspace, PLUGIN_VERSION, AT
    )

    result = lifecycle_flows.preflight(
        config=_valid_config(),
        state_dir=state_dir,
        stamp_path=stamp_path,
        plugin_version=PLUGIN_VERSION,
        current_roster_hash=stale_roster_hash,
        responder_mode_fn=responder_mode_fn,
    )

    assert result["responder_mode_ran"] is True
    assert result["proceed"] is True
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    assert stamp["plugin_version"] == PLUGIN_VERSION  # rewritten by responder_mode


# ---------------------------------------------------------------------------
# Row 3: confirmed marker -> stop offering close; marker untouched.
# ---------------------------------------------------------------------------


def test_confirmed_marker_stops_offering_close_marker_untouched(tmp_path):
    state_dir = tmp_path / "session"
    state_dir.mkdir(parents=True)
    marker_path = state_dir / "marker.json"
    marker = {
        "protocol": "bb.local.v1",
        "session_id": "page-ALERT-1-2026-07-20",
        "source_id": "ALERT-1",
        "opened_at": "2026-07-20T09:00:00Z",
        "open_write_confirmed": True,
    }
    marker_path.write_text(json.dumps(marker, indent=2), encoding="utf-8")
    marker_bytes_before = marker_path.read_bytes()

    stamp_path, roster_hash_value = _fresh_stamp(tmp_path)

    result = lifecycle_flows.preflight(
        config=_valid_config(),
        state_dir=state_dir,
        stamp_path=stamp_path,
        plugin_version=PLUGIN_VERSION,
        current_roster_hash=roster_hash_value,
    )

    assert result["proceed"] is False
    assert "/close" in result["stopped_reason"]
    assert result["marker_state"] == "confirmed_open"
    assert marker_path.read_bytes() == marker_bytes_before


# ---------------------------------------------------------------------------
# Row 4: unconfirmed marker, declined -> stop, marker untouched.
# ---------------------------------------------------------------------------


def test_unconfirmed_marker_declined_stops_marker_untouched(tmp_path):
    state_dir = tmp_path / "session"
    state_dir.mkdir(parents=True)
    marker_path = state_dir / "marker.json"
    marker = {
        "protocol": "bb.local.v1",
        "session_id": "page-ALERT-1-2026-07-20",
        "source_id": "ALERT-1",
        "opened_at": "2026-07-20T09:00:00Z",
        "open_write_confirmed": False,
    }
    marker_path.write_text(json.dumps(marker, indent=2), encoding="utf-8")
    marker_bytes_before = marker_path.read_bytes()

    stamp_path, roster_hash_value = _fresh_stamp(tmp_path)

    result = lifecycle_flows.preflight(
        config=_valid_config(),
        state_dir=state_dir,
        stamp_path=stamp_path,
        plugin_version=PLUGIN_VERSION,
        current_roster_hash=roster_hash_value,
        marker_confirm=False,
    )

    assert result["proceed"] is False
    assert result["marker_state"] == "crash_residue"
    assert marker_path.read_bytes() == marker_bytes_before


# ---------------------------------------------------------------------------
# Row 4: unconfirmed marker, confirmed -> proceeds; a subsequent open_command
# call rewrites the marker to the new session (never a standalone delete).
# ---------------------------------------------------------------------------


def test_unconfirmed_marker_confirmed_proceeds_and_new_open_rewrites_marker(
    mock_mcp, tmp_path
):
    state_dir = tmp_path / "session"
    state_dir.mkdir(parents=True)
    marker_path = state_dir / "marker.json"
    crash_marker = {
        "protocol": "bb.local.v1",
        "session_id": "page-ALERT-1-2026-07-20",
        "source_id": "ALERT-1",
        "opened_at": "2026-07-20T09:00:00Z",
        "open_write_confirmed": False,
    }
    marker_path.write_text(json.dumps(crash_marker, indent=2), encoding="utf-8")

    stamp_path, roster_hash_value = _fresh_stamp(tmp_path)

    result = lifecycle_flows.preflight(
        config=_valid_config(),
        state_dir=state_dir,
        stamp_path=stamp_path,
        plugin_version=PLUGIN_VERSION,
        current_roster_hash=roster_hash_value,
        marker_confirm=True,
    )

    assert result["proceed"] is True
    assert result["marker_state"] == "crash_residue_confirmed"

    # Prove the rewrite: opening a brand new session overwrites the crash
    # residue's marker with the new session's identity.
    from helpers import lifecycle_fixtures

    catalog = lifecycle_fixtures.load_catalog()
    verdict = lifecycle_fixtures.load_verdict("valid-no-signal")
    open_out = lifecycle_flows.open_command(
        mock_mcp,
        state_dir,
        "page",
        "ALERT-999",
        "2026-07-21",
        "2026-07-21T09:00:00Z",
        "alice @ 2026-07-21T09:00:00Z",
        [verdict],
        catalog,
    )

    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    assert marker["session_id"] == open_out["session_id"]
    assert marker["session_id"] != crash_marker["session_id"]
    assert marker["open_write_confirmed"] is True
