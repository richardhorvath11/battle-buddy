"""bb-mock-mcp — in-memory executable specification of the operation contract.

Dev-only (Constitution I; spec FR-010): used in-process by the contract test
layer, never shipped. Behavior, schema surface, and conformance tests all
derive from ``contract.json`` (research R5) so they cannot drift independently.

Facade surface:

- ``invoke(capability, op, payload)`` — the contract entry point. Validates
  contract shape before dispatch; rejections return the uniform envelope
  ``{"error": {"op", "code", "message"}}`` (FR-004); every mutating op appends
  to the ordered write log (FR-005).
- ``describe()`` — per-capability op schemas without invocation (FR-011).
- Direct state access for tests (FR-006): ``records.records``,
  ``artifacts.files``, ``diary.entries``, ``alerting.alerts`` /
  ``alerting.history``, ``write_log.entries``.
"""

import json

from .errors import ERROR_CODES, ContractViolation, SeedError
from .schema import SchemaRegistry
from .stores import (
    MockAlerting,
    MockArtifactStore,
    MockDiary,
    MockRecordStore,
    WriteLog,
)

_TYPE_CHECKS = {
    "map": lambda v: isinstance(v, dict),
    "str": lambda v: isinstance(v, str),
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "list": lambda v: isinstance(v, list),
}


class MockMcp:
    def __init__(self, contract_path=None):
        self.schema_registry = SchemaRegistry(contract_path)
        limit = self.schema_registry.constants["single_field_limit_chars"]
        self.records = MockRecordStore(limit)
        self.artifacts = MockArtifactStore()
        self.diary = MockDiary()
        self.alerting = MockAlerting()
        self.write_log = WriteLog()
        self._dispatch = {
            ("storage", "append_record"): lambda p: self.records.append_record(p["record"]),
            ("storage", "read_records"): lambda p: self.records.read_records(p.get("filter")),
            ("storage", "update_record"): lambda p: self.records.update_record(p["session_id"], p["fields"]),
            ("artifacts", "put_file"): lambda p: self.artifacts.put_file(p["name"], p["content"]),
            ("artifacts", "get_file"): lambda p: self.artifacts.get_file(p["link"]),
            ("diary", "append_entry"): lambda p: self.diary.append_entry(p["content"]),
            ("diary", "read_recent"): lambda p: self.diary.read_recent(p["n"]),
            ("alerting", "get_alert"): lambda p: self.alerting.get_alert(p["alert_id"]),
            ("alerting", "list_alert_history"): lambda p: self.alerting.list_alert_history(p["filter"]),
        }

    def describe(self):
        return self.schema_registry.describe()

    def invoke(self, capability, op, payload=None):
        op_ref = "{}.{}".format(capability, op)
        op_spec = self.schema_registry.operation(capability, op)
        if op_spec is None:
            return ContractViolation(
                "unknown_op",
                "'{}' is not an operation in the contract "
                "(see describe() for the full surface)".format(op_ref),
            ).envelope(op_ref)
        payload = {} if payload is None else payload
        try:
            if not isinstance(payload, dict):
                raise ContractViolation("invalid_input", "payload must be a map")
            self._validate_shape(op_spec["input"], payload)
            result = self._dispatch[(capability, op)](payload)
        except ContractViolation as exc:
            return exc.envelope(op_ref)
        if op_spec.get("mutating"):
            self.write_log.append(capability, op, _summarize(op, payload, result))
        return result

    def load_seed(self, path):
        """Load a declarative seed fixture (data-model.md SeedFixture).

        All-or-nothing: the whole file is validated before any state is
        applied, and failures raise SeedError naming the offending entry.
        Seeds bypass the write log — they are precondition state, not
        scenario writes.
        """
        with open(str(path), encoding="utf-8") as f:
            try:
                seed = json.load(f)
            except ValueError as exc:
                raise SeedError("seed file is not valid JSON: {}".format(exc))
        self._validate_seed(seed)
        for record in seed.get("records", []):
            self.records.append_record(dict(record))
        for artifact in seed.get("artifacts", []):
            self.artifacts.put_file(artifact["name"], artifact["content"])
        for content in seed.get("diary", []):
            self.diary.append_entry(content)
        alerts = seed.get("alerts", {})
        for alert in alerts.get("alerts", []):
            self.alerting.alerts[alert["alert_id"]] = dict(alert)
        for entry in alerts.get("history", []):
            self.alerting.history.append(dict(entry))

    def _validate_seed(self, seed):
        limit = self.schema_registry.constants["single_field_limit_chars"]
        if not isinstance(seed, dict):
            raise SeedError("seed: top level must be a map")
        known = ("records", "artifacts", "diary", "alerts")
        for key in seed:
            if key not in known:
                raise SeedError("seed: unknown top-level key '{}'".format(key))
        for key in known[:3]:
            if key in seed and not isinstance(seed[key], list):
                raise SeedError("seed {}: must be a list".format(key))

        for i, record in enumerate(seed.get("records", [])):
            where = "records[{}]".format(i)
            if not isinstance(record, dict):
                raise SeedError("seed {}: must be a field map".format(where))
            session_id = record.get("session_id")
            if not isinstance(session_id, str) or not session_id:
                raise SeedError(
                    "seed {}: session_id must be a non-empty string".format(where)
                )
            for field, value in record.items():
                if isinstance(value, str) and len(value) > limit:
                    raise SeedError(
                        "seed {}: field '{}' exceeds the {}-char D-3 limit".format(
                            where, field, limit
                        )
                    )

        for i, artifact in enumerate(seed.get("artifacts", [])):
            where = "artifacts[{}]".format(i)
            if not isinstance(artifact, dict):
                raise SeedError("seed {}: must be a map".format(where))
            if not isinstance(artifact.get("name"), str) or not artifact["name"]:
                raise SeedError("seed {}: name must be a non-empty string".format(where))
            if not isinstance(artifact.get("content"), str):
                raise SeedError("seed {}: content must be a string".format(where))

        for i, content in enumerate(seed.get("diary", [])):
            if not isinstance(content, str) or not content:
                raise SeedError(
                    "seed diary[{}]: entry must be a non-empty content string".format(i)
                )

        alerts = seed.get("alerts", {})
        if not isinstance(alerts, dict):
            raise SeedError("seed alerts: must be a map with 'alerts'/'history' lists")
        for key in alerts:
            if key not in ("alerts", "history"):
                raise SeedError("seed alerts: unknown key '{}'".format(key))
        for group in ("alerts", "history"):
            entries = alerts.get(group, [])
            if not isinstance(entries, list):
                raise SeedError("seed alerts.{}: must be a list".format(group))
            for i, alert in enumerate(entries):
                where = "alerts.{}[{}]".format(group, i)
                if not isinstance(alert, dict):
                    raise SeedError("seed {}: must be a field map".format(where))
                for field in MockAlerting.REQUIRED_ALERT_FIELDS:
                    if field not in alert:
                        raise SeedError(
                            "seed {}: missing required field '{}'".format(where, field)
                        )
                if not isinstance(alert["alert_id"], str) or not alert["alert_id"]:
                    raise SeedError(
                        "seed {}: alert_id must be a non-empty string".format(where)
                    )

    @staticmethod
    def _validate_shape(input_spec, payload):
        """Generic contract-shape validation: required fields, types, and the
        contract's declared constraints — semantic rules stay in the stores."""
        for field, spec in input_spec.items():
            if field not in payload:
                if spec.get("required"):
                    raise ContractViolation(
                        "invalid_input", "missing required field '{}'".format(field)
                    )
                continue
            value = payload[field]
            if not _TYPE_CHECKS[spec["type"]](value):
                raise ContractViolation(
                    "invalid_input",
                    "field '{}' must be of type {}".format(field, spec["type"]),
                )
            if spec.get("non_empty") and len(value) == 0:
                raise ContractViolation(
                    "invalid_input", "field '{}' must be non-empty".format(field)
                )
            if "min" in spec and value < spec["min"]:
                raise ContractViolation(
                    "invalid_input",
                    "field '{}' must be >= {}".format(field, spec["min"]),
                )


def _summarize(op, payload, result):
    """One-line deterministic payload summary for the write log."""
    if op == "append_record":
        return "session_id={}".format(payload["record"].get("session_id"))
    if op == "update_record":
        return "session_id={} fields={}".format(
            payload["session_id"], sorted(payload["fields"])
        )
    if op == "put_file":
        return "name={} -> {}".format(payload["name"], result["link"])
    if op == "append_entry":
        return "-> {}".format(result["link"])
    return op
