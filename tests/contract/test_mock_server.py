"""Contract tests for the bb-mock-mcp stdio server (test-plan B-3).

The server is the transport the interactive (Tier 2) scenario harness trusts, so
it cannot be the one untested component (Constitution VIII). These are hermetic:
they drive ``handle()`` and the state/schema helpers directly — no real stdio,
no subprocess — so the JSON-RPC surface, the alien-name resolution, the schema
translation, cross-process state, and fault injection are all pinned as pure
functions.

Lives in the contract layer: the server is dev tooling that imports
``bb_mock_mcp``, and the contract layer is the one that legitimately depends on
the mock (``tests/conftest.py`` layer rule).
"""

import json
import os
import sys

import pytest

from conftest import MOCK_PKG_DIR, fixture_path

if str(MOCK_PKG_DIR) not in sys.path:
    sys.path.insert(0, str(MOCK_PKG_DIR))

import server  # noqa: E402  (bb-mock-mcp/server.py, via MOCK_PKG_DIR on sys.path)
from bb_mock_mcp import MockMcp  # noqa: E402


@pytest.fixture
def mock():
    return MockMcp()


@pytest.fixture
def names():
    return dict(server.DEFAULT_NAMES)


# --------------------------------------------------------------------------- #
# initialize / handshake
# --------------------------------------------------------------------------- #
def test_initialize_echoes_requested_protocol_version(mock, names):
    msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
           "params": {"protocolVersion": "2025-06-18"}}
    resp = server.handle(mock, names, set(), msg)
    assert resp["result"]["protocolVersion"] == "2025-06-18"
    assert resp["result"]["capabilities"] == {"tools": {}}
    assert resp["result"]["serverInfo"]["name"] == "bb-mock-mcp"


def test_initialize_falls_back_to_default_version(mock, names):
    msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    resp = server.handle(mock, names, set(), msg)
    assert resp["result"]["protocolVersion"] == server.DEFAULT_PROTOCOL_VERSION


def test_initialized_notification_yields_no_response(mock, names):
    msg = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    assert server.handle(mock, names, set(), msg) is None


def test_unknown_method_is_method_not_found(mock, names):
    msg = {"jsonrpc": "2.0", "id": 9, "method": "bogus/method"}
    resp = server.handle(mock, names, set(), msg)
    assert resp["error"]["code"] == -32601


def test_unknown_notification_yields_no_response(mock, names):
    msg = {"jsonrpc": "2.0", "method": "bogus/notification"}
    assert server.handle(mock, names, set(), msg) is None


# --------------------------------------------------------------------------- #
# tools/list — alien names + schema translation
# --------------------------------------------------------------------------- #
def test_tools_list_exposes_every_mapped_op_under_an_alien_name(mock, names):
    resp = server.handle(mock, names, set(), {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    tools = resp["result"]["tools"]
    assert len(tools) == len(names) == 9
    listed = {t["name"] for t in tools}
    assert listed == set(names)
    # Not one exposed name may equal the operation it maps to — the whole point.
    for t in tools:
        cap, op = names[t["name"]].split(".", 1)
        assert op not in t["name"]
        assert cap not in t["name"]


def test_every_tool_carries_a_valid_object_input_schema(mock, names):
    resp = server.handle(mock, names, set(), {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    for t in resp["result"]["tools"]:
        schema = t["inputSchema"]
        assert schema["type"] == "object"
        assert "properties" in schema


def test_schema_translation_maps_types_required_and_nonempty():
    op_input = {
        "record": {"type": "map", "required": True, "notes": "the row"},
        "n": {"type": "int", "required": True},
        "name": {"type": "str", "required": True, "non_empty": True},
        "opt": {"type": "list", "required": False},
    }
    schema = server.translate_schema(op_input)
    props = schema["properties"]
    assert props["record"]["type"] == "object"
    assert props["record"]["description"] == "the row"
    assert props["n"]["type"] == "integer"
    assert props["name"]["type"] == "string"
    assert props["name"]["minLength"] == 1  # non_empty on a string
    assert props["opt"]["type"] == "array"
    assert set(schema["required"]) == {"record", "n", "name"}  # opt omitted
    assert "opt" not in schema["required"]


def test_a_names_file_referencing_an_unknown_op_is_skipped_not_crashed(mock):
    bad = dict(server.DEFAULT_NAMES)
    bad["acme_mystery"] = "storage.nonexistent_op"
    resp = server.handle(mock, bad, set(), {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    listed = {t["name"] for t in resp["result"]["tools"]}
    assert "acme_mystery" not in listed


# --------------------------------------------------------------------------- #
# tools/call — routing, envelopes, faults
# --------------------------------------------------------------------------- #
def _call(mock, names, fail, tool, arguments):
    msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
           "params": {"name": tool, "arguments": arguments}}
    resp = server.handle(mock, names, fail, msg)
    payload = json.loads(resp["result"]["content"][0]["text"])
    return resp["result"], payload


def test_tool_call_routes_to_the_mapped_operation(mock, names):
    result, payload = _call(
        mock, names, set(), "acme_sheet_add_row",
        {"record": {"session_id": "page-A-2026-07-23", "status": "open"}},
    )
    assert result["isError"] is False
    assert payload == {"session_id": "page-A-2026-07-23"}
    assert mock.records.records[0]["session_id"] == "page-A-2026-07-23"


def test_tool_call_surfaces_the_error_envelope_as_iserror(mock, names):
    # update_record on a session that does not exist → not_found envelope.
    result, payload = _call(
        mock, names, set(), "acme_sheet_patch",
        {"session_id": "missing", "fields": {"status": "closed"}},
    )
    assert result["isError"] is True
    assert payload["error"]["code"] == "not_found"
    assert payload["error"]["op"] == "storage.update_record"


def test_unknown_tool_name_is_an_iserror_unknown_op(mock, names):
    result, payload = _call(mock, names, set(), "not_a_tool", {})
    assert result["isError"] is True
    assert payload["error"]["code"] == "unknown_op"


def test_fault_injection_fails_exactly_the_named_op(mock, names):
    fail = {"diary.append_entry"}
    # the faulted op returns the envelope without dispatching...
    result, payload = _call(mock, names, fail, "acme_journal_write", {"content": "x"})
    assert result["isError"] is True
    assert payload["error"]["op"] == "diary.append_entry"
    assert mock.diary.entries == []  # never dispatched
    # ...while an unfaulted op still works.
    result2, payload2 = _call(
        mock, names, fail, "acme_sheet_add_row", {"record": {"session_id": "s1"}}
    )
    assert result2["isError"] is False


def test_parse_fail_set_splits_and_trims():
    assert server._parse_fail_set("") == set()
    assert server._parse_fail_set(None) == set()
    assert server._parse_fail_set("a.b, c.d ") == {"a.b", "c.d"}


# --------------------------------------------------------------------------- #
# state persistence — the B-4 contract
# --------------------------------------------------------------------------- #
def test_dump_then_load_round_trips_every_store(mock, names, tmp_path):
    _call(mock, names, set(), "acme_sheet_add_row", {"record": {"session_id": "s1"}})
    _call(mock, names, set(), "acme_blob_put", {"name": "t.md", "content": "hi"})
    _call(mock, names, set(), "acme_journal_write", {"content": "entry one"})
    path = str(tmp_path / "state.json")
    server.dump_state(mock, path)

    fresh = MockMcp()
    server.load_state(fresh, path)
    assert fresh.records.records == mock.records.records
    assert fresh.artifacts.files == mock.artifacts.files
    assert fresh.artifacts._counter == mock.artifacts._counter
    assert [e["content"] for e in fresh.diary.entries] == ["entry one"]
    assert fresh.diary._clock == mock.diary._clock
    # write log is what B-4 reads for ordering — it must survive verbatim.
    assert fresh.write_log.entries == mock.write_log.entries


def test_state_write_log_preserves_mutation_order(mock, names, tmp_path):
    _call(mock, names, set(), "acme_journal_write", {"content": "diary first"})
    _call(mock, names, set(), "acme_sheet_add_row", {"record": {"session_id": "s1"}})
    _call(mock, names, set(), "acme_sheet_patch",
          {"session_id": "s1", "fields": {"diary_url": "diary://1"}})
    path = str(tmp_path / "state.json")
    server.dump_state(mock, path)
    with open(path, encoding="utf-8") as f:
        entries = json.load(f)["write_log"]
    seq = [(e["capability"], e["op"]) for e in entries]
    assert seq == [
        ("diary", "append_entry"),
        ("storage", "append_record"),
        ("storage", "update_record"),
    ]
    assert [e["seq"] for e in entries] == [1, 2, 3]


def test_reads_do_not_appear_in_the_write_log(mock, names, tmp_path):
    _call(mock, names, set(), "acme_sheet_add_row", {"record": {"session_id": "s1"}})
    _call(mock, names, set(), "acme_sheet_query", {"filter": {}})  # a read
    assert [e["op"] for e in mock.write_log.entries] == ["append_record"]


def test_is_write_call_flags_only_mutating_tool_calls(mock, names):
    def msg(method, tool=None):
        m = {"method": method}
        if tool is not None:
            m["params"] = {"name": tool}
        return m

    assert server._is_write_call(mock, names, msg("tools/call", "acme_sheet_add_row"))
    assert not server._is_write_call(mock, names, msg("tools/call", "acme_sheet_query"))
    assert not server._is_write_call(mock, names, msg("tools/list"))


# --------------------------------------------------------------------------- #
# serve() — the stdio loop over real streams
# --------------------------------------------------------------------------- #
def test_serve_writes_wellformed_jsonrpc_and_persists_state(mock, names, tmp_path):
    import io
    state = str(tmp_path / "state.json")
    stdin = io.StringIO("\n".join([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": "acme_sheet_add_row",
                               "arguments": {"record": {"session_id": "s1"}}}}),
        "",  # blank line is skipped, not an error
    ]) + "\n")
    stdout = io.StringIO()
    server.serve(mock, names, set(), state, stdin, stdout)

    lines = [json.loads(l) for l in stdout.getvalue().splitlines() if l]
    # one reply for initialize, none for the notification, one for the call.
    assert len(lines) == 2
    for reply in lines:
        assert reply["jsonrpc"] == "2.0"
        assert "id" in reply
    assert lines[0]["id"] == 1               # initialize
    assert lines[1]["id"] == 2               # tools/call
    assert lines[1]["result"]["isError"] is False
    # the mutating call was persisted write-through.
    with open(state, encoding="utf-8") as f:
        assert len(json.load(f)["write_log"]) == 1


def test_serve_emits_parse_error_on_a_bad_line(mock, names):
    import io
    stdout = io.StringIO()
    server.serve(mock, names, set(), None, io.StringIO("not json\n"), stdout)
    reply = json.loads(stdout.getvalue())
    assert reply["error"]["code"] == -32700


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_main_seeds_and_publishes_initial_state(tmp_path):
    import io
    state = str(tmp_path / "state.json")
    # empty stdin so serve() returns immediately after the initial state publish.
    rc = server.main(["--state", state,
                      "--seed", str(fixture_path("seeds", "synthetic-incident.json"))],
                     stdin=io.StringIO(""), stdout=io.StringIO())
    assert rc == 0
    with open(state, encoding="utf-8") as f:
        published = json.load(f)
    # the seed's rows are visible to a later assertion process before any call.
    assert len(published["records"]) == 2
    assert published["write_log"] == []  # seeds bypass the write log


def test_main_fails_cleanly_on_a_bad_seed(tmp_path, capsys):
    bad = tmp_path / "bad-seed.json"
    bad.write_text(json.dumps({"_doc": "not a valid seed shape"}))
    rc = server.main(["--seed", str(bad)])
    assert rc == 2
    assert "bb-mock-mcp-server:" in capsys.readouterr().err


def test_main_loads_a_custom_names_file(tmp_path):
    names_file = tmp_path / "names.json"
    names_file.write_text(json.dumps({
        "_comment": "documentation, must be ignored",
        "zzz_add": "storage.append_record",
    }))
    loaded = server._load_names(str(names_file))
    assert loaded == {"zzz_add": "storage.append_record"}
    assert "_comment" not in loaded
