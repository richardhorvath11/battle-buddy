"""Conformance: the ordered write log (FR-005, Story 2 AS-3/AS-4, SC-004).

A scripted cross-capability write sequence must be reproducible exactly from
the log; read ops are never logged; interleaved two-actor writes land
deterministically in both log and final state.
"""


def ops_in_log(mock):
    return [(e["capability"], e["op"]) for e in mock.write_log.entries]


def test_scripted_sequence_reproduced_exactly(mock_mcp):
    # the canonical ordering rule this exists for: diary before record
    mock_mcp.invoke("diary", "append_entry", {"content": "investigating al-1"})
    mock_mcp.invoke("artifacts", "put_file", {"name": "evidence.md", "content": "…"})
    mock_mcp.invoke("storage", "append_record", {"record": {"session_id": "s1"}})

    assert ops_in_log(mock_mcp) == [
        ("diary", "append_entry"),
        ("artifacts", "put_file"),
        ("storage", "append_record"),
    ]
    assert [e["seq"] for e in mock_mcp.write_log.entries] == [1, 2, 3]


def test_read_ops_are_not_logged(mock_mcp):
    mock_mcp.invoke("diary", "append_entry", {"content": "x"})
    mock_mcp.invoke("diary", "read_recent", {"n": 1})
    mock_mcp.invoke("storage", "read_records", {})
    assert ops_in_log(mock_mcp) == [("diary", "append_entry")]


def test_log_reflects_operations_completed_so_far(mock_mcp):
    mock_mcp.invoke("diary", "append_entry", {"content": "x"})
    assert len(mock_mcp.write_log.entries) == 1  # mid-scenario query
    mock_mcp.invoke("storage", "append_record", {"record": {"session_id": "s1"}})
    assert len(mock_mcp.write_log.entries) == 2


def test_rejected_calls_are_not_logged(mock_mcp):
    mock_mcp.invoke("storage", "append_record", {"record": {"no": "session_id"}})
    assert mock_mcp.write_log.entries == []


def test_interleaved_two_actor_writes_deterministic(mock_mcp):
    # actor A creates; B and A interleave updates on the same record
    mock_mcp.invoke("storage", "append_record", {"record": {"session_id": "s1", "owner": "A"}})
    mock_mcp.invoke("storage", "update_record", {"session_id": "s1", "fields": {"owner": "B"}})
    mock_mcp.invoke("storage", "update_record", {"session_id": "s1", "fields": {"status": "closed"}})
    mock_mcp.invoke("storage", "update_record", {"session_id": "s1", "fields": {"owner": "A"}})

    # both actors' operations preserved, in order
    assert ops_in_log(mock_mcp) == [
        ("storage", "append_record"),
        ("storage", "update_record"),
        ("storage", "update_record"),
        ("storage", "update_record"),
    ]
    # deterministic final state: last write per field wins
    assert mock_mcp.records.records[0] == {
        "session_id": "s1",
        "owner": "A",
        "status": "closed",
    }
