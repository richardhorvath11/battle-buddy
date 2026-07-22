"""US2 write flow — the consumption layer over the diary capability's write op
(spec Phase 4 / SC-004; data-model.md §1).

This module **consumes and does not duplicate** slice 1's
``tests/contract/test_diary.py``, which already gates the raw contract
behavior: ``append_entry`` returning a ``link``, ``read_recent``'s ``n``
validation, and the shape of the uniform error envelope. Nothing here
re-asserts any of that. What this module adds is the layer built on top of
it — ``tests/helpers/diary_reference.write_entry`` (T015), the documented
write flow's executable form — and the two structural pins the write flow
depends on (the write-log count per close, and the closed op-set).
"""

import json

from conftest import REPO_ROOT
from helpers import diary_reference

CONTRACT_PATH = REPO_ROOT / "tools" / "bb-mock-mcp" / "contract.json"


def _diary_ops():
    with open(str(CONTRACT_PATH), encoding="utf-8") as f:
        contract = json.load(f)
    return set(contract["capabilities"]["diary"]["ops"])


def _diary_writes(mock):
    return [e for e in mock.write_log.entries if e["capability"] == "diary"]


def test_write_entry_url_matches_what_the_mock_actually_stored(mock_mcp):
    # Not "compares a value to itself": `out["url"]` comes from write_entry's
    # return, while `stored_link` is read back independently through a
    # SEPARATE op (`read_recent`) rather than reused from the same call. A
    # transform inside write_entry that mangled the link before returning it
    # would make these two diverge even though the mock's own append
    # succeeded — this is the assertion that has write_entry's function body
    # as its subject, per T016.
    out = diary_reference.write_entry(mock_mcp.invoke, "began triage")
    assert out["error"] is None

    entries = mock_mcp.invoke("diary", "read_recent", {"n": 1})["entries"]
    stored_link = entries[0]["link"]

    assert out["url"] == stored_link
    # SKILL.md "Write flow": this is the value the close flow carries onward
    # into the session row's diary field — the linkage assertion's subject.
    assert out["url"] is not None


def test_write_entry_treats_an_explicit_null_error_as_success():
    # F7 (review round): "error" in result is a key-PRESENCE check, so a
    # result shaped {"link": ..., "error": None} — error explicitly nulled
    # to signal success, rather than the key being omitted entirely — used
    # to satisfy the old check and fall into the failure branch, producing
    # a both-null {"url": None, "error": None}: failure-shaped, with no
    # error to show for it. A hand-built invoke (not the mock) is enough
    # here since the defect is in write_entry's own branching, not in
    # anything the mock does.
    def fake_invoke(capability, op, payload):
        assert (capability, op) == ("diary", "append_entry")
        return {"link": "https://diary.example/entry/1", "error": None}

    out = diary_reference.write_entry(fake_invoke, "began triage")
    assert out == {"url": "https://diary.example/entry/1", "error": None}


def test_one_drafted_close_writes_the_diary_exactly_once(mock_mcp):
    # SC-004's count, asserted exactly — "at least one" would pass on a
    # duplicate append that silently doubled the write. The CLOSE-LEVEL
    # ordering claim (diary write precedes every artifact/record write in a
    # real close) is gated by slice 5's `tests/contract/test_close_flow.py`
    # and `tests/contract/test_lifecycle_full_sim.py`; this module only
    # asserts the diary adapter's own write count in isolation.
    diary_reference.write_entry(mock_mcp.invoke, "closing out the incident")

    assert len(_diary_writes(mock_mcp)) == 1


def test_diary_op_set_is_closed_exactly_append_and_read(mock_mcp):
    # EQUALITY, not a subset check: a subset assertion would go quiet the
    # moment a future `create_diary` op landed in the contract, which is
    # exactly the case FR-004's "no diary creation" pin depends on catching.
    assert _diary_ops() == {"append_entry", "read_recent"}


def test_write_entry_failure_surfaces_uniform_envelope_unswallowed(mock_mcp):
    # Empty content is contract-invalid (non_empty per contract.json) —
    # slice 1's test_diary.py already gates the raw envelope's shape and
    # code; this asserts write_entry passes it through faithfully rather
    # than swallowing it or reshaping it into something else.
    out = diary_reference.write_entry(mock_mcp.invoke, "")

    assert out["url"] is None
    error = out["error"]
    assert error is not None
    assert set(error) == {"op", "code", "message"}
    assert error["op"] == "diary.append_entry"

    # A failed (contract-rejected) call is never logged as a write (mock
    # convention, shared with slice 1) — the failure must not phantom-count
    # toward SC-004's per-close write.
    assert _diary_writes(mock_mcp) == []
