"""ConfigView: the R6 read protocol over `.claude/settings.json` → battleBuddy.

Table-driven over inline config documents written to a tmp workspace — the
"workspace config block is a fixture file in tests" arrangement of spec FR-002.
Every row of the protocol doc's config-key table has a case here.
"""

import json

import pytest

import _config


def write_settings(root, text):
    claude_dir = root / ".claude"
    claude_dir.mkdir(exist_ok=True)
    (claude_dir / "settings.json").write_text(text, encoding="utf-8")


def view(root):
    return _config.load_config(root)


FULL_CONFIG = {
    "battleBuddy": {
        "budgets": {"triageTurnCap": 7},
        "bindings": {
            "storage.append_record": "mcp__sheets__append_row",
            "storage.read_rows": "mcp__sheets__read_range",
            "alerting.get_alert": "mcp__opsgenie__get_alert",
            "observability.query_metrics": "mcp__grafana__query",
            "diary.append_entry": "mcp__docs__append",
        },
    }
}


def test_absent_settings_file_gives_defaults(tmp_path):
    cfg = view(tmp_path)
    assert cfg.turn_cap == 15
    assert cfg.bindings is None
    assert cfg.config_present is False


def test_default_turn_cap_is_protocol_documented_15(tmp_path):
    # The protocol doc pins 15 as the documented default (spec edge case:
    # "turn-cap configuration absent: a documented default applies").
    assert _config.DEFAULT_TRIAGE_TURN_CAP == 15
    assert view(tmp_path).turn_cap == 15


def test_settings_without_battlebuddy_block(tmp_path):
    write_settings(tmp_path, json.dumps({"permissions": {"allow": []}}))
    cfg = view(tmp_path)
    assert cfg.config_present is False
    assert cfg.turn_cap == 15
    assert cfg.bindings is None


def test_full_config_reads_cap_and_bindings(tmp_path):
    write_settings(tmp_path, json.dumps(FULL_CONFIG))
    cfg = view(tmp_path)
    assert cfg.config_present is True
    assert cfg.turn_cap == 7
    assert cfg.bindings == FULL_CONFIG["battleBuddy"]["bindings"]
    assert cfg.notices == []


def test_malformed_json_is_treated_as_absent_with_notice(tmp_path):
    write_settings(tmp_path, "{broken json,,,")
    cfg = view(tmp_path)
    assert cfg.config_present is False
    assert cfg.turn_cap == 15
    assert cfg.bindings is None
    assert cfg.notices  # fail open, never silent


def test_battlebuddy_block_of_wrong_type_is_absent_with_notice(tmp_path):
    write_settings(tmp_path, json.dumps({"battleBuddy": "yes please"}))
    cfg = view(tmp_path)
    assert cfg.config_present is False
    assert cfg.notices


@pytest.mark.parametrize(
    "cap", ["15", 14.5, True, -3, None],
    ids=["string", "float", "bool", "negative", "null"],
)
def test_invalid_turn_cap_falls_back_to_default(tmp_path, cap):
    write_settings(
        tmp_path,
        json.dumps({"battleBuddy": {"budgets": {"triageTurnCap": cap}}}),
    )
    cfg = view(tmp_path)
    assert cfg.turn_cap == 15
    if cap is not None:
        assert cfg.notices


def test_zero_turn_cap_is_a_valid_configuration(tmp_path):
    write_settings(
        tmp_path, json.dumps({"battleBuddy": {"budgets": {"triageTurnCap": 0}}})
    )
    assert view(tmp_path).turn_cap == 0


def test_bindings_of_wrong_type_disable_tripwire_with_notice(tmp_path):
    write_settings(
        tmp_path, json.dumps({"battleBuddy": {"bindings": ["not", "a", "map"]}})
    )
    cfg = view(tmp_path)
    assert cfg.bindings is None
    assert cfg.notices


def test_binding_entries_must_be_operation_level(tmp_path):
    # Keys are `capability.operation` (design §7.2/D-13); a flat capability key
    # or a non-string value is ignored with a notice, valid entries survive.
    write_settings(
        tmp_path,
        json.dumps(
            {
                "battleBuddy": {
                    "bindings": {
                        "storage.append_record": "mcp__sheets__append_row",
                        "alerting": "mcp__opsgenie__get_alert",
                        "observability.query_metrics": 42,
                    }
                }
            }
        ),
    )
    cfg = view(tmp_path)
    assert cfg.bindings == {"storage.append_record": "mcp__sheets__append_row"}
    assert len(cfg.notices) == 2


def test_reverse_lookup_single_capability(tmp_path):
    write_settings(tmp_path, json.dumps(FULL_CONFIG))
    cfg = view(tmp_path)
    assert cfg.capabilities_for("mcp__opsgenie__get_alert") == {"alerting"}
    assert cfg.capabilities_for("mcp__sheets__append_row") == {"storage"}


def test_reverse_lookup_multi_capability_tool(tmp_path):
    # One tool serving operations of several capabilities classifies as the
    # set of matching capabilities (protocol doc rule).
    config = {
        "battleBuddy": {
            "bindings": {
                "alerting.get_alert": "mcp__swiss_army__call",
                "observability.query_metrics": "mcp__swiss_army__call",
            }
        }
    }
    write_settings(tmp_path, json.dumps(config))
    assert view(tmp_path).capabilities_for("mcp__swiss_army__call") == {
        "alerting",
        "observability",
    }


def test_reverse_lookup_unbound_tool_is_empty(tmp_path):
    write_settings(tmp_path, json.dumps(FULL_CONFIG))
    assert view(tmp_path).capabilities_for("mcp__unknown__tool") == set()
    assert view(tmp_path).capabilities_for("") == set()


def test_reverse_lookup_with_no_bindings_is_empty(tmp_path):
    assert view(tmp_path).capabilities_for("mcp__opsgenie__get_alert") == set()


def test_loader_never_writes(tmp_path):
    write_settings(tmp_path, json.dumps(FULL_CONFIG))
    before = (tmp_path / ".claude" / "settings.json").read_bytes()
    view(tmp_path)
    assert (tmp_path / ".claude" / "settings.json").read_bytes() == before
