#!/usr/bin/env python3
"""bb-mock-mcp stdio server (test-plan B-3) — the in-memory operation-contract
mock, exposed over MCP's stdio JSON-RPC transport so a live Claude Code session
can drive it. Dev-only (Constitution I): lives under ``tools/``, never shipped —
``tests/unit/test_packaging.py`` enforces that boundary.

It is a thin transport wrapper around ``bb_mock_mcp.MockMcp``; every semantic
(shape validation, the ``{"error": {...}}`` envelope, the write log) is the
facade's, unchanged. The wrapper adds four things:

1. **Alien tool names.** Tools are exposed under deliberately un-battle-buddy
   names (``acme_sheet_add_row`` → ``storage.append_record``) so ``/doctor``
   must resolve capabilities by *schema shape*, not keyword — the executable
   test of Constitution VII. Swap the map with ``--names <file>``.
2. **Schema translation.** The facade's ``describe()`` vocabulary
   (``map|str|int|list``) is translated to JSON Schema so a resolver has real
   ``inputSchema`` to match against.
3. **Write-through state.** ``--state <path>`` persists the mock's stores and
   write log to JSON on every mutating call, and rehydrates from it on startup —
   so a separate assertion process (B-4) can inspect a finished run, and so
   resume/handoff scenarios survive across two sessions.
4. **Fault injection.** ``BB_MOCK_FAIL=diary.append_entry,storage.update_record``
   makes exactly those ops return the error envelope, exercising the §9
   degraded-operation paths end to end.

Pure stdlib (no ``mcp`` SDK dependency): the handshake surface we need is small
and stable, and staying dependency-free keeps the whole harness hermetic and
off the 3.10+ floor the SDK would impose.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from bb_mock_mcp import MockMcp  # noqa: E402

# MCP stdio wire version we implement. We echo the client's requested version
# when it sends one (forward-compatible), falling back to this.
DEFAULT_PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "bb-mock-mcp", "version": "0.1.0"}

# Default alien-name map: tool name -> "capability.operation". Deliberately
# nothing like the operation names, so resolution can only succeed by shape.
DEFAULT_NAMES = {
    "acme_sheet_add_row": "storage.append_record",
    "acme_sheet_query": "storage.read_records",
    "acme_sheet_patch": "storage.update_record",
    "acme_blob_put": "artifacts.put_file",
    "acme_blob_fetch": "artifacts.get_file",
    "acme_journal_write": "diary.append_entry",
    "acme_journal_tail": "diary.read_recent",
    "acme_pager_get": "alerting.get_alert",
    "acme_pager_history": "alerting.list_alert_history",
}

# describe() type vocabulary -> JSON Schema type.
_JSON_SCHEMA_TYPE = {
    "map": "object",
    "str": "string",
    "int": "integer",
    "list": "array",
}


# --------------------------------------------------------------------------- #
# Schema translation
# --------------------------------------------------------------------------- #
def translate_schema(op_input):
    """Translate one op's ``describe()`` input block to a JSON Schema object.

    ``op_input`` is ``{param: {type, required, non_empty?, notes?}}``. Non-empty
    string constraints become ``minLength: 1``; ``notes`` become ``description``
    — both are legitimate matching signals a real tool schema would carry.
    """
    properties = {}
    required = []
    for param, spec in op_input.items():
        prop = {"type": _JSON_SCHEMA_TYPE.get(spec.get("type"), "string")}
        if spec.get("notes"):
            prop["description"] = spec["notes"]
        if spec.get("non_empty") and prop["type"] == "string":
            prop["minLength"] = 1
        properties[param] = prop
        if spec.get("required"):
            required.append(param)
    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def build_tools(mock, name_map):
    """The ``tools/list`` payload: one entry per mapped (capability, op)."""
    surface = mock.describe()
    tools = []
    for tool_name in sorted(name_map):
        capability, op = name_map[tool_name].split(".", 1)
        op_spec = surface.get(capability, {}).get(op)
        if op_spec is None:
            continue  # a names file naming an unknown op — skip, don't crash
        tools.append(
            {
                "name": tool_name,
                "description": "Mapped to {}.{} (bb-mock-mcp).".format(capability, op),
                "inputSchema": translate_schema(op_spec["input"]),
            }
        )
    return tools


# --------------------------------------------------------------------------- #
# State persistence (write-through)
# --------------------------------------------------------------------------- #
def dump_state(mock, path):
    """Serialize the mock's stores + write log + internal counters to JSON."""
    state = {
        "records": [dict(r) for r in mock.records.records],
        "artifacts": {
            "files": {k: dict(v) for k, v in mock.artifacts.files.items()},
            "counter": mock.artifacts._counter,
        },
        "diary": {
            "entries": [dict(e) for e in mock.diary.entries],
            "clock": mock.diary._clock,
        },
        "alerting": {
            "alerts": {k: dict(v) for k, v in mock.alerting.alerts.items()},
            "history": [dict(h) for h in mock.alerting.history],
        },
        "write_log": [dict(e) for e in mock.write_log.entries],
    }
    tmp = "{}.tmp".format(path)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)  # atomic swap — a reader never sees a half-written file


def load_state(mock, path):
    """Rehydrate a mock from a state file written by ``dump_state``."""
    with open(path, encoding="utf-8") as f:
        state = json.load(f)
    mock.records.records = [dict(r) for r in state.get("records", [])]
    artifacts = state.get("artifacts", {})
    mock.artifacts.files = {k: dict(v) for k, v in artifacts.get("files", {}).items()}
    mock.artifacts._counter = artifacts.get("counter", 0)
    diary = state.get("diary", {})
    mock.diary.entries = [dict(e) for e in diary.get("entries", [])]
    mock.diary._clock = diary.get("clock", 0)
    alerting = state.get("alerting", {})
    mock.alerting.alerts = {k: dict(v) for k, v in alerting.get("alerts", {}).items()}
    mock.alerting.history = [dict(h) for h in alerting.get("history", [])]
    mock.write_log.entries = [dict(e) for e in state.get("write_log", [])]


# --------------------------------------------------------------------------- #
# JSON-RPC handling
# --------------------------------------------------------------------------- #
def _result(msg_id, result):
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id, code, message):
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _tool_result(payload, is_error):
    """MCP tools/call result: the op's JSON as a single text content block."""
    return {
        "content": [{"type": "text", "text": json.dumps(payload)}],
        "isError": is_error,
    }


def handle(mock, name_map, fail_set, msg, protocol_version=DEFAULT_PROTOCOL_VERSION):
    """Handle one parsed JSON-RPC message.

    Returns a response dict, or ``None`` for notifications (no ``id``) and other
    no-reply messages. Never raises on a malformed request — a bad message
    becomes a JSON-RPC error, mirroring the facade's fail-loud-but-never-crash
    posture.
    """
    method = msg.get("method")
    msg_id = msg.get("id")
    is_notification = "id" not in msg

    if method == "initialize":
        requested = (msg.get("params") or {}).get("protocolVersion")
        return _result(
            msg_id,
            {
                "protocolVersion": requested or protocol_version,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            },
        )

    if method == "notifications/initialized":
        return None

    if method == "ping":
        return None if is_notification else _result(msg_id, {})

    if method == "tools/list":
        return _result(msg_id, {"tools": build_tools(mock, name_map)})

    if method == "tools/call":
        params = msg.get("params") or {}
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}
        op_ref = name_map.get(tool_name)
        if op_ref is None:
            return _result(msg_id, _tool_result(
                {"error": {"op": tool_name, "code": "unknown_op",
                           "message": "no tool named '{}'".format(tool_name)}},
                is_error=True,
            ))
        capability, op = op_ref.split(".", 1)
        if op_ref in fail_set:
            return _result(msg_id, _tool_result(
                {"error": {"op": op_ref, "code": "invalid_input",
                           "message": "injected fault (BB_MOCK_FAIL)"}},
                is_error=True,
            ))
        outcome = mock.invoke(capability, op, arguments)
        return _result(msg_id, _tool_result(outcome, is_error="error" in outcome))

    if is_notification:
        return None
    return _error(msg_id, -32601, "method not found: {}".format(method))


def _is_mutating(mock, op_ref):
    capability, op = op_ref.split(".", 1)
    spec = mock.schema_registry.operation(capability, op)
    return bool(spec and spec.get("mutating"))


# --------------------------------------------------------------------------- #
# stdio loop
# --------------------------------------------------------------------------- #
def serve(mock, name_map, fail_set, state_path, stdin, stdout):
    """Read newline-delimited JSON-RPC from ``stdin``, reply on ``stdout``.

    State is dumped after any successful mutating ``tools/call`` (write-through),
    so a crash or an un-clean session exit still leaves the assertion process a
    current file to read.
    """
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            _write(stdout, _error(None, -32700, "parse error"))
            continue
        response = handle(mock, name_map, fail_set, msg)
        if response is not None:
            _write(stdout, response)
        if state_path and _is_write_call(mock, name_map, msg):
            dump_state(mock, state_path)


def _is_write_call(mock, name_map, msg):
    if msg.get("method") != "tools/call":
        return False
    tool_name = (msg.get("params") or {}).get("name")
    op_ref = name_map.get(tool_name)
    return bool(op_ref) and _is_mutating(mock, op_ref)


def _write(stdout, obj):
    stdout.write(json.dumps(obj) + "\n")
    stdout.flush()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _parse_fail_set(env_value):
    if not env_value:
        return set()
    return {item.strip() for item in env_value.split(",") if item.strip()}


def _load_names(path):
    if path is None:
        return dict(DEFAULT_NAMES)
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    # Underscore-prefixed keys (e.g. "_comment") are documentation, not tools.
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def main(argv=None, stdin=None, stdout=None):
    parser = argparse.ArgumentParser(
        prog="bb-mock-mcp-server",
        description="MCP stdio server over the bb-mock-mcp operation contract (dev-only).",
    )
    parser.add_argument("--state", help="path to persist/rehydrate mock state (JSON)")
    parser.add_argument("--seed", help="path to a seed fixture to load at startup")
    parser.add_argument("--names", help="path to a tool-name map (JSON); defaults to acme_*")
    args = parser.parse_args(argv)

    mock = MockMcp()
    try:
        if args.state and os.path.exists(args.state):
            load_state(mock, args.state)
        if args.seed:
            mock.load_seed(args.seed)
        name_map = _load_names(args.names)
    except (OSError, ValueError) as exc:
        # ValueError covers SeedError (a ValueError subclass) and bad JSON in a
        # state or names file. Fail loud and specific, never a raw traceback.
        sys.stderr.write("bb-mock-mcp-server: {}\n".format(exc))
        return 2
    fail_set = _parse_fail_set(os.environ.get("BB_MOCK_FAIL"))

    if args.state:
        dump_state(mock, args.state)  # publish initial (seeded/rehydrated) state

    serve(mock, name_map, fail_set, args.state,
          stdin if stdin is not None else sys.stdin,
          stdout if stdout is not None else sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
