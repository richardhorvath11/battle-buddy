"""US3 checkpoint conventions (spec AS-1..AS-4, Edge Cases, FR-005, FR-006, SC-005).

Drives ``store_flows.write_checkpoint`` / ``store_flows.read_latest_checkpoint`` — the
executable form of ``skills/session-store/SKILL.md``'s "Checkpoints" section — against
the mock store, asserting on the row cell contents, the local
``staging/checkpoints.jsonl`` history file, and the mock's artifact store (never
prose).

Fixtures live in ``tests/fixtures/store/checkpoints/``: a real ``bb.ledger.v1``
document that genuinely passes ``bb_validate`` (modeled on
``tests/fixtures/validate/valid-ledger-deep-dive.json``), an invalid+fixed candidate
pair, an invalid+still-invalid candidate pair, and an oversize *template* this module
pads at test time. The padding relies on SKILL.md's pinned serialization convention —
``json.dumps(doc, sort_keys=True, separators=(",", ":"))`` — under which appending a
plain ASCII character to a string field grows the serialized document by exactly one
character, so an exact target length is reachable by direct arithmetic (no
trial-and-error).
"""

import json


from conftest import fixture_path
from helpers import store_flows

CHECKPOINTS_DIR = ("store", "checkpoints")

OPEN_FIELDS = dict(
    fingerprint="b" * 16,
    catalog_resolved=True,
    alert_signature="checkout-api: high latency",
    services=["checkout-api"],
    severity="sev2",
    responder="alice @ 2026-07-20T09:00:00Z",
    started_at="2026-07-20T09:00:00Z",
)

RESPONDER = OPEN_FIELDS["responder"]


def _open(mock, tmp_path, source_id="ALERT-CKPT", **overrides):
    fields = dict(OPEN_FIELDS)
    fields.update(overrides)
    return store_flows.open_session(
        mock, tmp_path, "incident", source_id, "2026-07-20", **fields
    )


def _load(name):
    with open(str(fixture_path(*CHECKPOINTS_DIR, name)), encoding="utf-8") as f:
        return json.load(f)


def _serialize(doc):
    # Mirrors store_flows._serialize_checkpoint's pinned convention exactly —
    # tests must measure the same serialization the guard/cell use, never a
    # second, possibly-drifting one.
    return json.dumps(doc, sort_keys=True, separators=(",", ":"))


def _pad_to_length(template, target_len):
    """Pad ``oversize-template.json``'s designated field
    (``hypotheses[0].evidence_for[0].excerpt``) with ASCII filler until the
    document's pinned serialization is exactly ``target_len`` characters."""
    doc = json.loads(json.dumps(template))  # deep copy
    base_len = len(_serialize(doc))
    delta = target_len - base_len
    if delta < 0:
        raise ValueError(
            "template already exceeds target_len %d (base %d) — pick a smaller "
            "target or a smaller template" % (target_len, base_len)
        )
    doc["hypotheses"][0]["evidence_for"][0]["excerpt"] += "a" * delta
    assert len(_serialize(doc)) == target_len
    return doc


def _row(mock, session_id):
    return mock.invoke(
        "storage", "read_records", {"filter": {"session_id": session_id}}
    )["records"][0]


def _history_lines(tmp_path):
    path = tmp_path / "staging" / "checkpoints.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _guard_chars(mock):
    return mock.schema_registry.constants["single_field_limit_chars"]


# ---------------------------------------------------------------------------
# AS-1: within-guard checkpoint -> full document in the cell, one history line.
# ---------------------------------------------------------------------------


def test_as1_within_guard_checkpoint_lands_full_document_in_cell(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path)
    session_id = open_out["session_id"]
    doc = _load("valid-ledger.json")

    outcome = store_flows.write_checkpoint(
        mock_mcp, tmp_path, session_id, [doc], responder=RESPONDER, seq=1
    )

    assert outcome["written"] is True
    assert outcome["cell"] == "latest_checkpoint"
    assert outcome["overflowed"] is False
    assert outcome["link"] is None
    assert outcome["schema_valid"] is True
    assert "error" not in outcome["update_result"]

    row = _row(mock_mcp, session_id)
    assert json.loads(row["latest_checkpoint"]) == doc

    lines = _history_lines(tmp_path)
    assert len(lines) == 1
    assert lines[0] == {"seq": 1, "document": doc}
    assert outcome["history_line_count"] == 1


# ---------------------------------------------------------------------------
# AS-2 + SC-005: over-guard checkpoint -> overflow artifact, cell holds the
# pointer, read_latest_checkpoint recovers the full document, zero rejections.
# ---------------------------------------------------------------------------


def test_as2_over_guard_checkpoint_overflows_and_round_trips(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path)
    session_id = open_out["session_id"]
    guard = _guard_chars(mock_mcp)
    template = _load("oversize-template.json")
    doc = _pad_to_length(template, guard + 500)
    assert len(_serialize(doc)) > guard

    outcome = store_flows.write_checkpoint(
        mock_mcp, tmp_path, session_id, [doc], responder=RESPONDER, seq=1
    )

    assert outcome["written"] is True
    assert outcome["overflowed"] is True
    assert outcome["link"] is not None
    # zero rejections (SC-005): neither the artifact write nor the row update
    # came back as an error envelope.
    assert outcome["put_result"] is not None and "error" not in outcome["put_result"]
    assert "error" not in outcome["update_result"]

    row = _row(mock_mcp, session_id)
    cell = json.loads(row["latest_checkpoint"])
    assert cell == {"overflow": outcome["link"], "seq": 1}

    recovered = store_flows.read_latest_checkpoint(mock_mcp, session_id)
    assert recovered == doc  # the COMPLETE document, not the pointer


# ---------------------------------------------------------------------------
# Exactly-at-guard edge: 45,000 chars lands in the cell, not overflow.
# ---------------------------------------------------------------------------


def test_exactly_at_guard_lands_in_cell_not_overflow(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path)
    session_id = open_out["session_id"]
    guard = _guard_chars(mock_mcp)
    assert guard == 45000
    template = _load("oversize-template.json")
    doc = _pad_to_length(template, guard)
    serialized = _serialize(doc)
    assert len(serialized) == 45000

    outcome = store_flows.write_checkpoint(
        mock_mcp, tmp_path, session_id, [doc], responder=RESPONDER, seq=1
    )

    assert outcome["serialized_len"] == 45000
    assert outcome["overflowed"] is False
    assert outcome["cell"] == "latest_checkpoint"
    assert outcome["link"] is None
    assert "error" not in outcome["update_result"]

    row = _row(mock_mcp, session_id)
    assert json.loads(row["latest_checkpoint"]) == doc


# ---------------------------------------------------------------------------
# AS-3: validation gate — invalid+fixed persists unflagged; twice-invalid
# persists flagged, data intact, both validator error lists surfaced.
# ---------------------------------------------------------------------------


def test_as3_invalid_then_fixed_persists_second_candidate_unflagged(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path)
    session_id = open_out["session_id"]
    invalid_doc, fixed_doc = _load("invalid-then-fixed.json")

    outcome = store_flows.write_checkpoint(
        mock_mcp,
        tmp_path,
        session_id,
        [invalid_doc, fixed_doc],
        responder=RESPONDER,
        seq=1,
    )

    assert outcome["schema_valid"] is True
    assert outcome["validator_errors"][0]  # first attempt had real errors
    assert outcome["validator_errors"][0][0]["rule"] == "schema.missing_field"
    assert outcome["validator_errors"][1] == []  # re-prompted attempt is clean

    row = _row(mock_mcp, session_id)
    stored = json.loads(row["latest_checkpoint"])
    assert stored == fixed_doc
    assert "schema_valid" not in stored


def test_as3_twice_invalid_persists_flagged_with_data_intact(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path)
    session_id = open_out["session_id"]
    invalid_doc, still_invalid_doc = _load("invalid-then-still-invalid.json")

    outcome = store_flows.write_checkpoint(
        mock_mcp,
        tmp_path,
        session_id,
        [invalid_doc, still_invalid_doc],
        responder=RESPONDER,
        seq=1,
    )

    assert outcome["schema_valid"] is False
    # both attempts' real validator error lists are surfaced, and they differ
    # (the second attempt fixed the memory.unvalidated_non_fresh violation).
    assert outcome["validator_errors"][0]
    assert outcome["validator_errors"][1]
    rules_0 = {v["rule"] for v in outcome["validator_errors"][0]}
    rules_1 = {v["rule"] for v in outcome["validator_errors"][1]}
    assert "memory.unvalidated_non_fresh" in rules_0
    assert "memory.unvalidated_non_fresh" not in rules_1
    assert "schema.missing_field" in rules_0 and "schema.missing_field" in rules_1

    row = _row(mock_mcp, session_id)
    stored = json.loads(row["latest_checkpoint"])
    assert stored["schema_valid"] is False
    without_flag = dict(stored)
    del without_flag["schema_valid"]
    assert without_flag == still_invalid_doc  # data never dropped

    # the history line retains the flagged document too — no data loss there
    # either.
    lines = _history_lines(tmp_path)
    assert lines[-1]["document"]["schema_valid"] is False


# ---------------------------------------------------------------------------
# AS-4: one-row-read resume — no full-history scan.
# ---------------------------------------------------------------------------


def test_as4_read_latest_checkpoint_resumes_without_scanning_history(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path)
    session_id = open_out["session_id"]

    doc0 = _load("valid-ledger.json")
    store_flows.write_checkpoint(
        mock_mcp, tmp_path, session_id, [doc0], responder=RESPONDER, seq=0
    )

    guard = _guard_chars(mock_mcp)
    template = _load("oversize-template.json")
    overflow_doc = _pad_to_length(template, guard + 200)
    store_flows.write_checkpoint(
        mock_mcp, tmp_path, session_id, [overflow_doc], responder=RESPONDER, seq=1
    )

    # Prove no full-history scan: poison the staging file so any attempt to
    # open/parse it would either raise or return garbage; the resume must
    # still recover the correct document using only the row + one artifact
    # read.
    history_path = tmp_path / "staging" / "checkpoints.jsonl"
    history_path.write_bytes(b"NOT JSON AT ALL - proves no history scan\n")

    recovered = store_flows.read_latest_checkpoint(mock_mcp, session_id)
    assert recovered == overflow_doc


# ---------------------------------------------------------------------------
# History retention: N writes -> N history lines matching the N winning
# documents in order.
# ---------------------------------------------------------------------------


def test_history_retention_matches_every_write_in_order(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path)
    session_id = open_out["session_id"]

    doc0 = _load("valid-ledger.json")
    invalid_doc, fixed_doc = _load("invalid-then-fixed.json")
    guard = _guard_chars(mock_mcp)
    template = _load("oversize-template.json")
    overflow_doc = _pad_to_length(template, guard + 100)

    store_flows.write_checkpoint(
        mock_mcp, tmp_path, session_id, [doc0], responder=RESPONDER, seq=0
    )
    store_flows.write_checkpoint(
        mock_mcp,
        tmp_path,
        session_id,
        [invalid_doc, fixed_doc],
        responder=RESPONDER,
        seq=1,
    )
    store_flows.write_checkpoint(
        mock_mcp, tmp_path, session_id, [overflow_doc], responder=RESPONDER, seq=2
    )

    lines = _history_lines(tmp_path)
    assert [line["seq"] for line in lines] == [0, 1, 2]
    assert [line["document"] for line in lines] == [doc0, fixed_doc, overflow_doc]


# ---------------------------------------------------------------------------
# Checkpoint zero: seq 0 -> triage_verdict; seq 1 -> latest_checkpoint; both
# recorded in history.
# ---------------------------------------------------------------------------


def test_checkpoint_zero_lands_in_triage_verdict_seq_one_in_latest_checkpoint(
    mock_mcp, tmp_path
):
    open_out = _open(mock_mcp, tmp_path)
    session_id = open_out["session_id"]
    doc0 = _load("valid-ledger.json")
    doc1 = _load("oversize-template.json")

    outcome0 = store_flows.write_checkpoint(
        mock_mcp, tmp_path, session_id, [doc0], responder=RESPONDER, seq=0
    )
    outcome1 = store_flows.write_checkpoint(
        mock_mcp, tmp_path, session_id, [doc1], responder=RESPONDER, seq=1
    )

    assert outcome0["cell"] == "triage_verdict"
    assert outcome1["cell"] == "latest_checkpoint"

    row = _row(mock_mcp, session_id)
    assert json.loads(row["triage_verdict"]) == doc0
    assert json.loads(row["latest_checkpoint"]) == doc1

    lines = _history_lines(tmp_path)
    assert [line["seq"] for line in lines] == [0, 1]


# ---------------------------------------------------------------------------
# Ownership pre-read denial: a mismatched responder gets no write at all.
# ---------------------------------------------------------------------------


def test_ownership_mismatch_denies_write_no_mutation_performed(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path)
    session_id = open_out["session_id"]
    doc = _load("valid-ledger.json")

    segment_start = len(mock_mcp.write_log.entries)
    outcome = store_flows.write_checkpoint(
        mock_mcp,
        tmp_path,
        session_id,
        [doc],
        responder="mallory @ 2026-07-20T09:30:00Z",
        seq=1,
    )

    assert outcome == {
        "written": False,
        "read_only": True,
        "taken_over_by": RESPONDER,
    }
    # no mutating op was performed by the denial path.
    assert mock_mcp.write_log.entries[segment_start:] == []
    row = _row(mock_mcp, session_id)
    assert "latest_checkpoint" not in row
    assert _history_lines(tmp_path) == []


# ---------------------------------------------------------------------------
# Accumulate -> upload seam, end to end: the history file write_checkpoint
# actually produced is what close_session uploads as checkpoints.jsonl
# (research R1; SKILL.md "History" + "Close" step 2).
# ---------------------------------------------------------------------------


def test_accumulated_history_uploads_at_close_end_to_end(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path)
    session_id = open_out["session_id"]

    doc0 = _load("valid-ledger.json")
    doc1 = dict(doc0, phase="deep-dive")
    store_flows.write_checkpoint(
        mock_mcp, tmp_path, session_id, [doc0], responder=RESPONDER, seq=0
    )
    store_flows.write_checkpoint(
        mock_mcp, tmp_path, session_id, [doc1], responder=RESPONDER, seq=1
    )

    # close reads the REAL accumulated staging file, not a literal.
    staging_file = tmp_path / "staging" / "checkpoints.jsonl"
    accumulated = staging_file.read_text(encoding="utf-8")
    close_out = store_flows.close_session(
        mock_mcp,
        tmp_path,
        session_id,
        close_fields={"closed_at": "2026-07-20T10:00:00Z"},
        diary_content="closing",
        staged_artifacts={"staging/checkpoints.jsonl": accumulated},
    )

    upload = close_out["uploaded"]["staging/checkpoints.jsonl"]
    assert upload["uploaded_name"] == "checkpoints.jsonl"
    fetched = mock_mcp.invoke("artifacts", "get_file", {"link": upload["link"]})
    assert fetched["name"] == "battle-buddy/{}/checkpoints.jsonl".format(session_id)
    assert fetched["content"] == accumulated
    lines = [json.loads(l) for l in accumulated.splitlines()]
    assert [entry["seq"] for entry in lines] == [0, 1]
    assert [entry["document"] for entry in lines] == [doc0, doc1]
