"""Negative coverage for the FR-008 assertion entry points: they must FAIL on
divergent state, not vacuously pass — later slices build scenario checks on
these primitives."""

import pytest

from conftest import fixture_path, load_fixture
from helpers.assertions import assert_seeded_state, assert_write_sequence


def test_assert_seeded_state_fails_on_divergent_state(mock_mcp):
    seed = load_fixture("seeds", "synthetic-incident.json")
    mock_mcp.load_seed(fixture_path("seeds", "synthetic-incident.json"))
    mock_mcp.invoke("storage", "append_record", {"record": {"session_id": "extra"}})
    with pytest.raises(AssertionError):
        assert_seeded_state(mock_mcp, seed)


def test_assert_write_sequence_fails_on_wrong_sequence(mock_mcp):
    mock_mcp.invoke("diary", "append_entry", {"content": "x"})
    with pytest.raises(AssertionError):
        assert_write_sequence(mock_mcp, [("storage", "append_record")])


def test_assert_write_sequence_fails_on_missing_write(mock_mcp):
    mock_mcp.invoke("diary", "append_entry", {"content": "x"})
    mock_mcp.invoke("storage", "append_record", {"record": {"session_id": "s1"}})
    with pytest.raises(AssertionError):
        assert_write_sequence(mock_mcp, [("diary", "append_entry")])
