"""Conformance: storage ops (contracts/operations.md; SC-003).

Every op gets a happy path, each documented error, the D-3 single-field limit
boundary (44999 / 45000 / 45001), and insertion-order reads.
"""

import pytest

D3_LIMIT = 45000  # the contract's documented threshold (design §5.4, D-3)


def assert_error(result, op_ref, code):
    assert set(result) == {"error"}, "expected an error envelope, got {}".format(result)
    assert result["error"]["op"] == op_ref
    assert result["error"]["code"] == code
    assert result["error"]["message"], "message must name the violated expectation"
    return result["error"]["message"]


def test_contract_pins_the_d3_limit(mock_mcp):
    # The red-path canary (quickstart scenario 2): editing contract.json's
    # limit diverges from the contract's documented 45,000 and fails here.
    assert mock_mcp.schema_registry.constants["single_field_limit_chars"] == D3_LIMIT


def test_append_and_read_roundtrip(mock_mcp):
    out = mock_mcp.invoke("storage", "append_record", {"record": {"session_id": "s1", "status": "open"}})
    assert out == {"session_id": "s1"}
    read = mock_mcp.invoke("storage", "read_records", {})
    assert read == {"records": [{"session_id": "s1", "status": "open"}]}


def test_read_records_preserves_insertion_order(mock_mcp):
    for i in range(5):
        mock_mcp.invoke("storage", "append_record", {"record": {"session_id": "s{}".format(i)}})
    read = mock_mcp.invoke("storage", "read_records", {})
    assert [r["session_id"] for r in read["records"]] == ["s0", "s1", "s2", "s3", "s4"]


def test_read_records_field_equality_filter(mock_mcp):
    mock_mcp.invoke("storage", "append_record", {"record": {"session_id": "s1", "fingerprint": "fp-a"}})
    mock_mcp.invoke("storage", "append_record", {"record": {"session_id": "s2", "fingerprint": "fp-b"}})
    mock_mcp.invoke("storage", "append_record", {"record": {"session_id": "s3", "fingerprint": "fp-a"}})
    read = mock_mcp.invoke("storage", "read_records", {"filter": {"fingerprint": "fp-a"}})
    assert [r["session_id"] for r in read["records"]] == ["s1", "s3"]


def test_read_records_absent_filter_means_all(mock_mcp):
    mock_mcp.invoke("storage", "append_record", {"record": {"session_id": "s1"}})
    assert len(mock_mcp.invoke("storage", "read_records")["records"]) == 1


def test_read_records_on_empty_store_is_empty_list_not_error(mock_mcp):
    assert mock_mcp.invoke("storage", "read_records", {}) == {"records": []}


def test_update_record_merges_fields(mock_mcp):
    mock_mcp.invoke("storage", "append_record", {"record": {"session_id": "s1", "status": "open", "owner": "a"}})
    out = mock_mcp.invoke("storage", "update_record", {"session_id": "s1", "fields": {"status": "closed"}})
    assert out == {"session_id": "s1"}
    record = mock_mcp.records.records[0]
    assert record == {"session_id": "s1", "status": "closed", "owner": "a"}


def test_append_record_missing_session_id(mock_mcp):
    result = mock_mcp.invoke("storage", "append_record", {"record": {"note": "no id"}})
    message = assert_error(result, "storage.append_record", "invalid_input")
    assert "session_id" in message


def test_append_record_empty_session_id(mock_mcp):
    result = mock_mcp.invoke("storage", "append_record", {"record": {"session_id": ""}})
    assert_error(result, "storage.append_record", "invalid_input")


def test_append_record_non_map_record(mock_mcp):
    result = mock_mcp.invoke("storage", "append_record", {"record": ["not", "a", "map"]})
    message = assert_error(result, "storage.append_record", "invalid_input")
    assert "map" in message


def test_read_records_non_map_filter(mock_mcp):
    result = mock_mcp.invoke("storage", "read_records", {"filter": "fingerprint=fp-a"})
    message = assert_error(result, "storage.read_records", "invalid_input")
    assert "filter" in message


def test_update_record_unknown_session_id(mock_mcp):
    result = mock_mcp.invoke("storage", "update_record", {"session_id": "ghost", "fields": {"a": "b"}})
    message = assert_error(result, "storage.update_record", "not_found")
    assert "ghost" in message


def test_update_record_empty_fields(mock_mcp):
    mock_mcp.invoke("storage", "append_record", {"record": {"session_id": "s1"}})
    result = mock_mcp.invoke("storage", "update_record", {"session_id": "s1", "fields": {}})
    assert_error(result, "storage.update_record", "invalid_input")


@pytest.mark.parametrize("size,accepted", [(D3_LIMIT - 1, True), (D3_LIMIT, True), (D3_LIMIT + 1, False)])
def test_append_record_d3_boundary(mock_mcp, size, accepted):
    record = {"session_id": "s1", "blob": "x" * size}
    result = mock_mcp.invoke("storage", "append_record", {"record": record})
    if accepted:
        assert result == {"session_id": "s1"}
    else:
        message = assert_error(result, "storage.append_record", "invalid_input")
        assert "blob" in message and str(D3_LIMIT) in message


@pytest.mark.parametrize("size,accepted", [(D3_LIMIT - 1, True), (D3_LIMIT, True), (D3_LIMIT + 1, False)])
def test_update_record_d3_boundary(mock_mcp, size, accepted):
    mock_mcp.invoke("storage", "append_record", {"record": {"session_id": "s1"}})
    result = mock_mcp.invoke("storage", "update_record", {"session_id": "s1", "fields": {"blob": "x" * size}})
    if accepted:
        assert result == {"session_id": "s1"}
    else:
        assert_error(result, "storage.update_record", "invalid_input")
