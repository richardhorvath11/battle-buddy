"""The seeded-defect rejection corpus (FR-004, SC-006).

At least one deliberately contract-violating call per required operation,
parametrized as a table. Each must come back as the uniform error envelope
with the violated expectation named in the message — never silently accepted
or coerced.
"""

import pytest

# (case id, capability, op, payload, expected code, message must contain)
CORPUS = [
    ("append_record-missing-session-id", "storage", "append_record",
     {"record": {"note": "no id"}}, "invalid_input", "session_id"),
    ("append_record-non-map-record", "storage", "append_record",
     {"record": "not-a-map"}, "invalid_input", "record"),
    ("append_record-oversized-field", "storage", "append_record",
     {"record": {"session_id": "s1", "blob": "x" * 45001}}, "invalid_input", "blob"),
    ("read_records-non-map-filter", "storage", "read_records",
     {"filter": ["fingerprint"]}, "invalid_input", "filter"),
    ("update_record-unknown-session", "storage", "update_record",
     {"session_id": "ghost", "fields": {"a": "b"}}, "not_found", "ghost"),
    ("update_record-empty-fields", "storage", "update_record",
     {"session_id": "s1", "fields": {}}, "invalid_input", "fields"),
    ("put_file-empty-name", "artifacts", "put_file",
     {"name": "", "content": "c"}, "invalid_input", "name"),
    ("put_file-missing-content", "artifacts", "put_file",
     {"name": "f"}, "invalid_input", "content"),
    ("get_file-unknown-link", "artifacts", "get_file",
     {"link": "art://999"}, "not_found", "art://999"),
    ("append_entry-empty-content", "diary", "append_entry",
     {"content": ""}, "invalid_input", "content"),
    ("append_entry-missing-content", "diary", "append_entry",
     {}, "invalid_input", "content"),
    ("read_recent-zero-n", "diary", "read_recent",
     {"n": 0}, "invalid_input", "n"),
    ("read_recent-non-int-n", "diary", "read_recent",
     {"n": "five"}, "invalid_input", "n"),
    ("get_alert-unknown-id", "alerting", "get_alert",
     {"alert_id": "nope"}, "not_found", "nope"),
    ("get_alert-missing-id", "alerting", "get_alert",
     {}, "invalid_input", "alert_id"),
    ("list_alert_history-non-map-filter", "alerting", "list_alert_history",
     {"filter": 7}, "invalid_input", "filter"),
    ("unknown-op", "storage", "drop_table",
     {}, "unknown_op", "drop_table"),
    ("unknown-capability", "billing", "charge",
     {}, "unknown_op", "billing.charge"),
]


@pytest.mark.parametrize(
    "capability,op,payload,code,names",
    [c[1:] for c in CORPUS],
    ids=[c[0] for c in CORPUS],
)
def test_violation_is_rejected_naming_the_expectation(mock_mcp, capability, op, payload, code, names):
    result = mock_mcp.invoke(capability, op, payload)
    assert set(result) == {"error"}, "violating call was not rejected: {}".format(result)
    error = result["error"]
    assert set(error) == {"op", "code", "message"}  # uniform envelope
    assert error["op"] == "{}.{}".format(capability, op)
    assert error["code"] == code
    assert names in error["message"], (
        "message does not name the violated expectation: {!r}".format(error["message"])
    )


def test_corpus_covers_every_required_operation(mock_mcp):
    """SC-006: ≥1 deliberate violation per required operation."""
    covered = {(c[1], c[2]) for c in CORPUS}
    for cap, ops in mock_mcp.describe().items():
        for op in ops:
            assert (cap, op) in covered, "no rejection case for {}.{}".format(cap, op)
