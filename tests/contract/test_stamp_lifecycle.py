"""FR-005, SC-006, US3 scenarios 2-3: the green stamp's lifecycle
(``tests/helpers/doctor_flows.py`` ``roster_hash``/``write_stamp``/
``write_stamp_if_green``/``evaluate_stamp``, T016).

Coverage:

- A green report ⇒ ``write_stamp_if_green`` writes; the stamp JSON has
  exactly the four ``bb.stamp.v1`` fields with correct values (SC-006).
- A red report ⇒ no write at all.
- ``evaluate_stamp``: fresh on an exact match; stale on a changed
  ``plugin_version``; stale on a changed roster (the recomputed hash differs
  AND ``evaluate_stamp`` says stale); a timestamp difference alone is never
  stale (two stamps, different ``at``, same version+hash, both fresh);
  stale on a missing file; stale on a corrupt (non-JSON) file; stale on a
  wrong ``schema`` value.
- ``roster_hash`` stability: identical text ⇒ identical hash; key-order
  insensitivity (same ``mcpServers`` content, different key order at every
  nesting level ⇒ the SAME hash — canonicalization); ``${ENV_VAR}`` refs are
  hashed as the literal strings they are, never resolved.
- The stamp path is the workspace-root ``.bb-doctor-stamp.json``, is listed
  in the repo's own ``.gitignore`` (pinning FR-005's "never committed"), and
  never appears among ``scaffold_workspace``'s four committed files.

Assertions are on the returned artifacts (stamp dicts, on-disk JSON,
``evaluate_stamp``'s ``(status, reason)`` tuple) only, never prose.
"""

import json
from pathlib import Path

from helpers import doctor_flows, setup_flows

PLUGIN_VERSION = "0.4.0"
AT_A = "2026-01-15T09:30:00Z"
AT_B = "2026-06-01T12:00:00Z"

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


def _green_report():
    return {"schema": "bb.doctor.report.v1", "outcome": "green", "checks": [],
            "reduced_features": [], "migrations": []}


def _red_report():
    return {
        "schema": "bb.doctor.report.v1",
        "outcome": "red",
        "checks": [{"id": "binding.storage.append_record", "kind": "binding",
                    "capability": "storage", "op": "append_record", "status": "fail",
                    "detail": "no roster tool satisfies storage.append_record"}],
        "reduced_features": [],
        "migrations": [],
    }


# ---------------------------------------------------------------------------
# write_stamp_if_green: green writes all three (four incl. schema) fields
# ---------------------------------------------------------------------------


def test_green_report_writes_stamp_with_exact_fields_sc006(tmp_path):
    path = tmp_path / ".bb-doctor-stamp.json"
    roster_hash_value = doctor_flows.roster_hash(_ROSTER_TEXT)

    wrote = doctor_flows.write_stamp_if_green(
        _green_report(), path, PLUGIN_VERSION, roster_hash_value, AT_A
    )

    assert wrote is True
    assert path.exists()
    stamp = json.loads(path.read_text(encoding="utf-8"))
    assert set(stamp.keys()) == {"schema", "at", "plugin_version", "roster_hash"}
    assert stamp["schema"] == "bb.stamp.v1"
    assert stamp["at"] == AT_A
    assert stamp["plugin_version"] == PLUGIN_VERSION
    assert stamp["roster_hash"] == roster_hash_value


def test_write_stamp_directly_returns_the_same_dict_it_writes(tmp_path):
    path = tmp_path / ".bb-doctor-stamp.json"
    roster_hash_value = doctor_flows.roster_hash(_ROSTER_TEXT)

    stamp = doctor_flows.write_stamp(path, PLUGIN_VERSION, roster_hash_value, AT_A)

    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert stamp == on_disk


# ---------------------------------------------------------------------------
# write_stamp_if_green: red ⇒ no write
# ---------------------------------------------------------------------------


def test_red_report_writes_nothing(tmp_path):
    path = tmp_path / ".bb-doctor-stamp.json"
    roster_hash_value = doctor_flows.roster_hash(_ROSTER_TEXT)

    wrote = doctor_flows.write_stamp_if_green(
        _red_report(), path, PLUGIN_VERSION, roster_hash_value, AT_A
    )

    assert wrote is False
    assert not path.exists()


# ---------------------------------------------------------------------------
# evaluate_stamp: fresh on exact match
# ---------------------------------------------------------------------------


def test_evaluate_stamp_fresh_on_exact_match(tmp_path):
    path = tmp_path / ".bb-doctor-stamp.json"
    roster_hash_value = doctor_flows.roster_hash(_ROSTER_TEXT)
    doctor_flows.write_stamp(path, PLUGIN_VERSION, roster_hash_value, AT_A)

    status, reason = doctor_flows.evaluate_stamp(path, PLUGIN_VERSION, roster_hash_value)

    assert status == "fresh"
    assert reason


# ---------------------------------------------------------------------------
# evaluate_stamp: stale on changed plugin_version
# ---------------------------------------------------------------------------


def test_evaluate_stamp_stale_on_changed_plugin_version(tmp_path):
    path = tmp_path / ".bb-doctor-stamp.json"
    roster_hash_value = doctor_flows.roster_hash(_ROSTER_TEXT)
    doctor_flows.write_stamp(path, PLUGIN_VERSION, roster_hash_value, AT_A)

    status, reason = doctor_flows.evaluate_stamp(path, "0.5.0", roster_hash_value)

    assert status == "stale"
    assert "plugin_version" in reason


# ---------------------------------------------------------------------------
# evaluate_stamp: stale on changed roster (hash differs AND evaluate is stale)
# ---------------------------------------------------------------------------


def test_evaluate_stamp_stale_on_changed_roster(tmp_path):
    original_text = _ROSTER_TEXT
    changed_text = json.dumps(
        {
            "mcpServers": {
                "mycorp_sheets": {
                    "command": "npx",
                    "args": ["-y", "@mycorp-sheets/mcp-server"],
                    "env": {"MYCORP_SHEETS_TOKEN": "${MYCORP_SHEETS_TOKEN}"},
                },
                "mycorp_wiki": {
                    "command": "npx",
                    "args": ["-y", "@mycorp-wiki/mcp-server"],
                    "env": {"MYCORP_WIKI_TOKEN": "${MYCORP_WIKI_TOKEN}"},
                },
            }
        }
    )

    original_hash = doctor_flows.roster_hash(original_text)
    changed_hash = doctor_flows.roster_hash(changed_text)
    assert original_hash != changed_hash

    path = tmp_path / ".bb-doctor-stamp.json"
    doctor_flows.write_stamp(path, PLUGIN_VERSION, original_hash, AT_A)

    status, reason = doctor_flows.evaluate_stamp(path, PLUGIN_VERSION, changed_hash)

    assert status == "stale"
    assert "roster_hash" in reason


# ---------------------------------------------------------------------------
# evaluate_stamp: timestamp difference alone never stale
# ---------------------------------------------------------------------------


def test_evaluate_stamp_timestamp_difference_alone_never_stale(tmp_path):
    roster_hash_value = doctor_flows.roster_hash(_ROSTER_TEXT)
    path_a = tmp_path / "stamp-a.json"
    path_b = tmp_path / "stamp-b.json"

    doctor_flows.write_stamp(path_a, PLUGIN_VERSION, roster_hash_value, AT_A)
    doctor_flows.write_stamp(path_b, PLUGIN_VERSION, roster_hash_value, AT_B)

    status_a, _ = doctor_flows.evaluate_stamp(path_a, PLUGIN_VERSION, roster_hash_value)
    status_b, _ = doctor_flows.evaluate_stamp(path_b, PLUGIN_VERSION, roster_hash_value)

    assert status_a == "fresh"
    assert status_b == "fresh"
    assert json.loads(path_a.read_text())["at"] != json.loads(path_b.read_text())["at"]


# ---------------------------------------------------------------------------
# evaluate_stamp: stale on missing file
# ---------------------------------------------------------------------------


def test_evaluate_stamp_stale_on_missing_file(tmp_path):
    missing_path = tmp_path / "does-not-exist.json"

    status, reason = doctor_flows.evaluate_stamp(missing_path, PLUGIN_VERSION, "0" * 16)

    assert status == "stale"
    assert "missing" in reason


# ---------------------------------------------------------------------------
# evaluate_stamp: stale on corrupt (non-JSON) file
# ---------------------------------------------------------------------------


def test_evaluate_stamp_stale_on_corrupt_file(tmp_path):
    path = tmp_path / ".bb-doctor-stamp.json"
    path.write_bytes(b"\xff\xfe\x00not-json-garbage-\x00\x01\x02")

    status, reason = doctor_flows.evaluate_stamp(path, PLUGIN_VERSION, "0" * 16)

    assert status == "stale"


# ---------------------------------------------------------------------------
# evaluate_stamp: stale on wrong schema value
# ---------------------------------------------------------------------------


def test_evaluate_stamp_stale_on_wrong_schema(tmp_path):
    path = tmp_path / ".bb-doctor-stamp.json"
    roster_hash_value = doctor_flows.roster_hash(_ROSTER_TEXT)
    path.write_text(
        json.dumps(
            {
                "schema": "bb.stamp.v2",
                "at": AT_A,
                "plugin_version": PLUGIN_VERSION,
                "roster_hash": roster_hash_value,
            }
        ),
        encoding="utf-8",
    )

    status, reason = doctor_flows.evaluate_stamp(path, PLUGIN_VERSION, roster_hash_value)

    assert status == "stale"
    assert "schema" in reason


# ---------------------------------------------------------------------------
# roster_hash: stability, key-order insensitivity, env-var-ref-as-literal
# ---------------------------------------------------------------------------


def test_roster_hash_same_text_same_hash():
    assert doctor_flows.roster_hash(_ROSTER_TEXT) == doctor_flows.roster_hash(_ROSTER_TEXT)


def test_roster_hash_is_key_order_insensitive():
    text_a = json.dumps(
        {
            "mcpServers": {
                "mycorp_sheets": {"command": "npx", "args": ["-y"], "env": {"A": "1"}},
                "mycorp_wiki": {"command": "npx", "args": ["-y"], "env": {"B": "2"}},
            }
        }
    )
    # Same content, top-level server order swapped AND each server's own
    # key order swapped — canonicalization (sort_keys) must apply at every
    # nesting level, not just the top one.
    text_b = json.dumps(
        {
            "mcpServers": {
                "mycorp_wiki": {"env": {"B": "2"}, "args": ["-y"], "command": "npx"},
                "mycorp_sheets": {"env": {"A": "1"}, "args": ["-y"], "command": "npx"},
            }
        }
    )

    assert text_a != text_b  # sanity: literally different serialized text
    assert doctor_flows.roster_hash(text_a) == doctor_flows.roster_hash(text_b)


def test_roster_hash_env_var_refs_are_literal_never_resolved(monkeypatch):
    monkeypatch.delenv("BB_TEST_TOKEN_VAR", raising=False)
    text = json.dumps(
        {"mcpServers": {"srv": {"command": "npx", "env": {"TOK": "${BB_TEST_TOKEN_VAR}"}}}}
    )

    # Must not raise even though the referenced env var is unset anywhere —
    # a resolving implementation would either raise or substitute here.
    hash_unset = doctor_flows.roster_hash(text)

    monkeypatch.setenv("BB_TEST_TOKEN_VAR", "super-secret-value")
    hash_set = doctor_flows.roster_hash(text)

    assert hash_unset == hash_set  # env state never consulted
    assert "super-secret-value" not in text  # sanity: literal ref only


def test_roster_hash_defaults_missing_mcp_servers_to_empty_map():
    assert doctor_flows.roster_hash("{}") == doctor_flows.roster_hash(
        json.dumps({"mcpServers": {}})
    )


# ---------------------------------------------------------------------------
# Stamp path: workspace-root, gitignored, never a scaffold file
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_stamp_gitignored_in_repo():
    gitignore_lines = (_REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".bb-doctor-stamp.json" in gitignore_lines


def test_stamp_path_is_workspace_root_and_never_a_scaffold_file(tmp_path):
    scaffold_paths, _mcp_text = setup_flows.scaffold_workspace(
        tmp_path, {"configVersion": "bb.config.v1"}, {}
    )

    # scaffold_workspace's own four documented outputs never include the stamp.
    assert ".bb-doctor-stamp.json" not in scaffold_paths
    assert all(
        p.name != ".bb-doctor-stamp.json" for p in scaffold_paths.values()
    )

    stamp_path = tmp_path / ".bb-doctor-stamp.json"
    doctor_flows.write_stamp(stamp_path, PLUGIN_VERSION, "0" * 16, AT_A)

    # Workspace root, not nested under any scaffold subdirectory.
    assert stamp_path.parent == tmp_path
    assert stamp_path not in set(scaffold_paths.values())
