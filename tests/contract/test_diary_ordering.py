"""US3 — recent entries always arrive newest-first, consumed with no
re-sort (spec Phase 5 / SC-005; data-model.md §2).

Slice 1's ``tests/contract/test_diary.py`` already gates the mock's RAW
behavior: ``read_recent`` returns newest-first, a short read returns fewer
than ``n`` entries in that same order, and an empty diary returns ``[]``
rather than an error. This module does not re-litigate any of that — it
asserts the CONSUMPTION layer built on top: that the documented flow
(``resolve_format`` via ``extract_structure``, and
``tests/helpers/diary_reference.consume_recent``) takes what the contract
already ordered and passes it through without ever re-deriving that order
itself.
"""

import inspect

from conftest import load_fixture
from helpers import diary_reference


def _seed_from_fixture(mock, fixture_name):
    # tests/fixtures/diary/README.md "Mock-seeding rule": a fixture is
    # newest-first (the shape read_recent returns), so seeding the mock
    # oldest-first means iterating reversed(entries) and appending each
    # entry's content — the mock's own newest-first read then reproduces
    # the fixture's original order. This is test-setup CONSTRUCTING diary
    # state, not the encoding consuming a read — see the no-reorder scan's
    # note below for why that distinction matters.
    fixture = load_fixture("diary", fixture_name)
    for entry in reversed(fixture["entries"]):
        mock.invoke("diary", "append_entry", {"content": entry["content"]})
    return fixture


def test_read_recent_reproduces_the_full_fixture_content_order(mock_mcp):
    fixture = _seed_from_fixture(mock_mcp, "entries-consistent.json")

    out = mock_mcp.invoke("diary", "read_recent", {"n": 5})
    returned = out["entries"]

    # The FULL sequence, not just entries[0] — and compared on `content`
    # only: the mock mints its own `link`/`at` on every append, so a
    # returned entry never `==` the fixture's entry dict (README's stated
    # trap).
    assert [e["content"] for e in returned] == [e["content"] for e in fixture["entries"]]


def test_consume_recent_freshest_and_considered_pass_through_unchanged(mock_mcp):
    _seed_from_fixture(mock_mcp, "entries-consistent.json")
    returned = mock_mcp.invoke("diary", "read_recent", {"n": 5})["entries"]

    consumed = diary_reference.consume_recent(returned)

    assert consumed["freshest"] == returned[0]
    assert consumed["considered"] == returned  # whole-list ==, not just freshest


def test_short_read_newest_first_and_resolution_proceeds_matched(mock_mcp):
    fixture = _seed_from_fixture(mock_mcp, "entries-short.json")
    assert len(fixture["entries"]) == 2  # fixture precondition (fewer than n=5)

    returned = mock_mcp.invoke("diary", "read_recent", {"n": 5})["entries"]
    assert [e["content"] for e in returned] == [e["content"] for e in fixture["entries"]]

    # AS-2: a short read is still a real read — resolution proceeds to the
    # matched path, not the empty-diary default.
    resolution = diary_reference.resolve_format(None, returned)
    assert resolution["source"] == "matched"


def test_empty_read_returns_empty_list_and_resolution_takes_default_path(mock_mcp):
    out = mock_mcp.invoke("diary", "read_recent", {"n": 5})
    assert out["entries"] == []

    resolution = diary_reference.resolve_format(None, out["entries"])
    assert resolution["source"] == "default"


# ---------------------------------------------------------------------------
# No-reorder source scan
# ---------------------------------------------------------------------------

_BANNED_TOKENS = ("sorted(", ".sort(", "reversed(")

_SCANNED_FUNCTIONS = (
    diary_reference.extract_structure,
    diary_reference.resolve_format,
    diary_reference.consume_recent,
)


def _banned_tokens_in(source_text):
    return [token for token in _BANNED_TOKENS if token in source_text]


def test_no_reorder_tokens_in_the_consuming_functions_bodies():
    # SOURCE SLICING via inspect.getsource, scoped to each function's own
    # body — never the whole file — so a `reversed(` used elsewhere in this
    # module (e.g. this test file's own `_seed_from_fixture` above, which
    # legitimately reverses a fixture to CONSTRUCT diary state, not to
    # consume a read) can never trip this gate. The ban is on the ENCODING
    # reordering what the contract already ordered; test-setup code that
    # seeds the mock oldest-first is doing the opposite — restoring the
    # fixture's own order for the mock to hand back.
    for fn in _SCANNED_FUNCTIONS:
        found = _banned_tokens_in(inspect.getsource(fn))
        assert found == [], "{} contains banned reorder token(s): {}".format(fn.__qualname__, found)


def test_no_reorder_scan_positive_control_can_actually_fail():
    # Non-vacuity: a scan that can never fail proves nothing. Plant a
    # `reversed(` in a throwaway function's source and confirm the same
    # scan mechanism used above DOES detect it.
    def _planted_reorder(entries):
        return list(reversed(entries))  # deliberately banned — control only

    found = _banned_tokens_in(inspect.getsource(_planted_reorder))
    assert found == ["reversed("]
