"""Conformance: diary ops — append→link, read_recent most-recent-first
(design §6.2, v1.2.1), n validation (contracts/operations.md; SC-003)."""

import pytest


def test_append_entry_returns_link(mock_mcp):
    out = mock_mcp.invoke("diary", "append_entry", {"content": "began triage"})
    assert set(out) == {"link"}
    assert out["link"]


def test_read_recent_most_recent_first(mock_mcp):
    for content in ("first", "second", "third"):
        mock_mcp.invoke("diary", "append_entry", {"content": content})
    out = mock_mcp.invoke("diary", "read_recent", {"n": 2})
    assert [e["content"] for e in out["entries"]] == ["third", "second"]


def test_read_recent_entries_carry_link_content_at(mock_mcp):
    mock_mcp.invoke("diary", "append_entry", {"content": "note"})
    (entry,) = mock_mcp.invoke("diary", "read_recent", {"n": 1})["entries"]
    assert set(entry) == {"link", "content", "at"}
    assert entry["at"]  # ISO 8601, deterministic logical clock


def test_read_recent_n_larger_than_entries_returns_all(mock_mcp):
    mock_mcp.invoke("diary", "append_entry", {"content": "only"})
    out = mock_mcp.invoke("diary", "read_recent", {"n": 10})
    assert [e["content"] for e in out["entries"]] == ["only"]


@pytest.mark.parametrize("n", [0, -1, "3", 1.5, None])
def test_read_recent_rejects_invalid_n(mock_mcp, n):
    result = mock_mcp.invoke("diary", "read_recent", {"n": n})
    assert result["error"]["op"] == "diary.read_recent"
    assert result["error"]["code"] == "invalid_input"
    assert "n" in result["error"]["message"]


def test_append_entry_rejects_empty_content(mock_mcp):
    result = mock_mcp.invoke("diary", "append_entry", {"content": ""})
    assert result["error"]["code"] == "invalid_input"
    assert "content" in result["error"]["message"]
