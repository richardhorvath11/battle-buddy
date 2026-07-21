"""US1: anchoring-guard phase x state matrix (SC-004, FR-002, research R5).

Pure ``bb_validate.validate()`` behavior — no mock, no store — parametrized
over both invariant phases (``evidence-gathering``, ``deep-dive``) and the
four anchoring states the guard names, plus early-phase
(``triage-seeded``, ``hypothesis-generation``) and ``resolution``-phase
legality. Assertions are rule-presence (membership), never exact-set:
several cells legitimately fire more than one rule (e.g. a 2-live-non-fresh
cell fires both anchoring rules), so this module isolates the two anchoring
rules (``ledger.min_live_hypotheses``, ``ledger.fresh_required``) from
``memory.unvalidated_non_fresh`` by building every non-fresh hypothesis in
every cell already VALIDATED or INVALIDATED — per-rule emission is
``test_validate.py``'s corpus; this module sweeps the phase x state matrix
SC-004 names.
"""

import pytest

import bb_validate


def _ledger(phase, hypotheses):
    """Minimal valid bb.ledger.v1 document for the given phase/hypotheses."""
    return {
        "schema": "bb.ledger.v1",
        "seq": 1,
        "at": "2026-07-21T00:00:00Z",
        "phase": phase,
        "hypotheses": hypotheses,
    }


def _hyp(hid, status, provenance, validation=None):
    """Minimal hypothesis: {id, statement, status, provenance}, plus
    ``validation`` only when given. A cell whose non-fresh hypotheses should
    NOT trip ``memory.unvalidated_non_fresh`` must pass ``validation``
    explicitly for every one of them — that isolation is what lets this
    module's assertions land on the anchoring rules alone."""
    hypothesis = {
        "id": hid,
        "statement": "statement for %s" % hid,
        "status": status,
        "provenance": provenance,
    }
    if validation is not None:
        hypothesis["validation"] = validation
    return hypothesis


INVARIANT_PHASES = list(bb_validate.INVARIANT_PHASES)
EARLY_PHASES = ("triage-seeded", "hypothesis-generation")


def test_invariant_phases_are_exactly_evidence_gathering_and_deep_dive():
    """Pin research R5 / FR-002's exact invariant-phase set once. The
    parametrization below derives from ``bb_validate.INVARIANT_PHASES`` so a
    validator phase change propagates automatically; this test catches a
    change of substance rather than silently following it."""
    assert set(bb_validate.INVARIANT_PHASES) == {
        "evidence-gathering", "deep-dive",
    }


# --- Anchoring matrix: both invariant phases x four spec states -------------

ANCHORING_PRESENCE_CASES = [
    (
        "two-live-one-fresh",
        [
            _hyp("h1", "live", "fresh"),
            _hyp("h2", "live", "triage", validation="VALIDATED"),
        ],
        "ledger.min_live_hypotheses",
    ),
    (
        "three-live-none-fresh",
        [
            _hyp("h1", "live", "triage", validation="VALIDATED"),
            _hyp("h2", "live", "recall", validation="INVALIDATED"),
            _hyp("h3", "live", "triage", validation="VALIDATED"),
        ],
        "ledger.fresh_required",
    ),
    (
        "three-live-nonfresh-plus-dead-fresh",
        [
            _hyp("h1", "live", "triage", validation="VALIDATED"),
            _hyp("h2", "live", "recall", validation="INVALIDATED"),
            _hyp("h3", "live", "triage", validation="VALIDATED"),
            _hyp("h4", "dead", "fresh"),
        ],
        "ledger.fresh_required",
    ),
]


@pytest.mark.parametrize("phase", INVARIANT_PHASES, ids=INVARIANT_PHASES)
@pytest.mark.parametrize(
    "case_id, hypotheses, expected_rule",
    ANCHORING_PRESENCE_CASES,
    ids=[c[0] for c in ANCHORING_PRESENCE_CASES],
)
def test_anchoring_matrix_rule_presence(phase, case_id, hypotheses, expected_rule):
    doc = _ledger(phase, hypotheses)
    violations = bb_validate.validate(doc)
    rule_names = {v["rule"] for v in violations}
    assert expected_rule in rule_names, (
        "%s (phase=%s): expected %r among violation rules, got %r"
        % (case_id, phase, expected_rule, sorted(rule_names))
    )


@pytest.mark.parametrize("phase", INVARIANT_PHASES, ids=INVARIANT_PHASES)
def test_anchoring_matrix_three_live_with_fresh_has_zero_violations(phase):
    # The clean cell: >=3 live and >=1 live fresh among them satisfies both
    # anchoring rules at once, so the document validates to zero violations.
    hypotheses = [
        _hyp("h1", "live", "fresh"),
        _hyp("h2", "live", "triage", validation="VALIDATED"),
        _hyp("h3", "live", "recall", validation="INVALIDATED"),
    ]
    doc = _ledger(phase, hypotheses)
    violations = bb_validate.validate(doc)
    rule_names = {v["rule"] for v in violations}
    assert "ledger.min_live_hypotheses" not in rule_names
    assert "ledger.fresh_required" not in rule_names
    assert violations == []


# --- Early-phase legality: sparse and empty ledgers are fine ---------------


@pytest.mark.parametrize("phase", EARLY_PHASES, ids=EARLY_PHASES)
def test_early_phase_accepts_empty_hypotheses_list(phase):
    doc = _ledger(phase, [])
    assert bb_validate.validate(doc) == []


@pytest.mark.parametrize("phase", EARLY_PHASES, ids=EARLY_PHASES)
def test_early_phase_accepts_single_validated_triage_hypothesis(phase):
    doc = _ledger(phase, [_hyp("h1", "live", "triage", validation="VALIDATED")])
    assert bb_validate.validate(doc) == []


@pytest.mark.parametrize("phase", EARLY_PHASES, ids=EARLY_PHASES)
def test_early_phase_missing_hypotheses_key_trips_schema_missing_field(phase):
    # "Empty" means hypotheses: [] — a present, empty list. Omitting the
    # required field entirely is a different, invalid state (research R5's
    # "empty means [] not absent" pin).
    doc = _ledger(phase, [])
    del doc["hypotheses"]
    violations = bb_validate.validate(doc)
    assert "schema.missing_field" in {v["rule"] for v in violations}


# --- resolution is non-invariant --------------------------------------------


def test_resolution_phase_is_non_invariant():
    doc = _ledger(
        "resolution", [_hyp("h1", "live", "triage", validation="VALIDATED")]
    )
    assert bb_validate.validate(doc) == []
