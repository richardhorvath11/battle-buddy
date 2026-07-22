"""FR-011 / research R4: schemas.md <-> bb_validate consistency (SC-002).

Ties the normative doc to the real implementation of record, mirroring
``test_fingerprint_reference.py``'s doc<->helper<->corpus precedent applied to
the checkpoint validator: every marker-tagged worked example in
``skills/investigation/references/schemas.md`` must classify through the real
``bb_validate.validate()`` exactly as its marker documents, and the doc's one
fenced machine-readable vocabulary block must agree with the validator's own
constants by exact set-equality both ways — a doc that silently drifts from
the validator (an extra phase, a renamed rule, a misspelled vocabulary value)
fails here rather than in review.
"""

import json
import re

import pytest

import bb_validate
from conftest import REPO_ROOT

SCHEMAS_DOC = (
    REPO_ROOT / "skills" / "investigation" / "references" / "schemas.md"
)

# Marker line, per schemas.md's documented format:
#   <!-- bb-example: <id> expect=valid -->
#   <!-- bb-example: <id> expect=invalid rule=<rule>[,<rule>...] -->
# The marker line is OUTSIDE the fence, immediately before it.
_MARKER_RE = re.compile(
    r"^<!-- bb-example: (?P<id>[a-z0-9][a-z0-9-]*) expect=(?P<expect>valid|invalid)"
    r"(?: rule=(?P<rules>[a-z0-9_.,]+))? -->$"
)

# Vocabulary block line, per schemas.md's pinned format: `key: v1 | v2 | ...`.
_VOCAB_LINE_RE = re.compile(r"^(?P<key>[a-z-]+):\s*(?P<value>.+)$")
_VOCAB_KEYS = (
    "phases",
    "invariant-phases",
    "provenance",
    "validation",
    "min-live",
    "schemas",
)


def _fenced_blocks(text):
    """Every ``` fenced code block's content, in document order.

    Same walk as test_fingerprint_reference.py's ``_fenced_blocks``: a line
    that is only backticks toggles in/out of a block: this also matches
    ```` ```json ```` opens since only the leading backtick run is checked
    via ``.startswith``.
    """
    blocks = []
    current = None
    for line in text.splitlines():
        if line.strip().startswith("```"):
            if current is None:
                current = []
            else:
                blocks.append("\n".join(current))
                current = None
            continue
        if current is not None:
            current.append(line)
    return blocks


def _parse_examples(text):
    """Every marker+fence pair: marker line immediately followed by a fence."""
    lines = text.splitlines()
    examples = []
    i = 0
    while i < len(lines):
        match = _MARKER_RE.match(lines[i].strip())
        if match is None:
            i += 1
            continue
        fence_open = i + 1
        if fence_open >= len(lines) or not lines[fence_open].strip().startswith("```"):
            i += 1
            continue
        body = []
        k = fence_open + 1
        while k < len(lines) and not lines[k].strip().startswith("```"):
            body.append(lines[k])
            k += 1
        rules = match.group("rules")
        examples.append(
            {
                "id": match.group("id"),
                "expect": match.group("expect"),
                "rules": rules.split(",") if rules else [],
                "json_text": "\n".join(body),
            }
        )
        i = k + 1
    return examples


def _parse_vocabulary_block(text):
    """The one fenced block whose every non-blank line is ``key: value``
    across exactly the documented vocabulary key set — distinguishes it from
    the ```json worked-example blocks (whose lines never match this shape)
    without relying on a language tag.
    """
    for block in _fenced_blocks(text):
        lines = [line for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        parsed = {}
        ok = True
        for line in lines:
            match = _VOCAB_LINE_RE.match(line.strip())
            if match is None:
                ok = False
                break
            parsed[match.group("key")] = match.group("value")
        if ok and set(parsed) == set(_VOCAB_KEYS):
            return parsed
    return None


def _split_pipe_list(value):
    return [v.strip() for v in value.split("|")]


DOC_TEXT = SCHEMAS_DOC.read_text(encoding="utf-8")
EXAMPLES = _parse_examples(DOC_TEXT)
VOCAB = _parse_vocabulary_block(DOC_TEXT)

VALID_EXAMPLES = [e for e in EXAMPLES if e["expect"] == "valid"]
INVALID_EXAMPLES = [e for e in EXAMPLES if e["expect"] == "invalid"]


# ---------------------------------------------------------------------------
# Non-vanishing guards (TA5-style precedent, per test_fingerprint_reference.py
# and test_skill_capability_naming.py): a broken marker regex or an emptied
# doc must not turn every check below into a silently-skipped no-op.
# ---------------------------------------------------------------------------


def test_doc_exists():
    assert SCHEMAS_DOC.is_file()


def test_at_least_eight_examples_total():
    assert len(EXAMPLES) >= 8


def _schema_of(example):
    return json.loads(example["json_text"]).get("schema")


def test_at_least_one_valid_and_one_invalid_example_per_schema():
    for schema in (bb_validate.VERDICT_SCHEMA, bb_validate.LEDGER_SCHEMA):
        valid_for_schema = [e for e in VALID_EXAMPLES if _schema_of(e) == schema]
        invalid_for_schema = [e for e in INVALID_EXAMPLES if _schema_of(e) == schema]
        assert valid_for_schema, "no valid worked example for schema %r" % schema
        assert invalid_for_schema, "no invalid worked example for schema %r" % schema


def test_vocabulary_block_was_found():
    assert VOCAB is not None, (
        "schemas.md must carry one fenced vocabulary block with exactly the "
        "keys %r" % (_VOCAB_KEYS,)
    )


# ---------------------------------------------------------------------------
# Worked examples: every marker+fence pair classifies through the real
# validator exactly as documented.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "example", VALID_EXAMPLES, ids=[e["id"] for e in VALID_EXAMPLES] or None
)
def test_valid_example_produces_zero_violations(example):
    doc = json.loads(example["json_text"])
    violations = bb_validate.validate(doc)
    assert violations == [], "%s: expected zero violations, got %r" % (
        example["id"],
        violations,
    )


@pytest.mark.parametrize(
    "example", INVALID_EXAMPLES, ids=[e["id"] for e in INVALID_EXAMPLES] or None
)
def test_invalid_example_trips_every_named_rule(example):
    doc = json.loads(example["json_text"])
    violations = bb_validate.validate(doc)
    rule_names = {v["rule"] for v in violations}
    missing = [rule for rule in example["rules"] if rule not in rule_names]
    # Membership, never exact-set: a document may legitimately trip more
    # rules than the ones its marker names (research R4 converge finding).
    assert not missing, "%s: named rule(s) %r not among violations %r" % (
        example["id"],
        missing,
        sorted(rule_names),
    )
    assert example["rules"], "%s: expect=invalid marker names no rule at all" % (
        example["id"],
    )


# ---------------------------------------------------------------------------
# Vocabulary agreement: exact set-equality both ways against the validator's
# own constants. Phase order is additionally pinned (tuple equality).
# ---------------------------------------------------------------------------


def test_vocabulary_phases_match_validator_order_and_set():
    documented = tuple(_split_pipe_list(VOCAB["phases"]))
    assert documented == bb_validate.PHASES


def test_vocabulary_invariant_phases_match_validator():
    documented = set(_split_pipe_list(VOCAB["invariant-phases"]))
    assert documented == set(bb_validate.INVARIANT_PHASES)


def test_vocabulary_provenance_matches_validator():
    documented = set(_split_pipe_list(VOCAB["provenance"]))
    assert documented == set(bb_validate.PROVENANCE_VALUES)


def test_vocabulary_validation_values_match_validator():
    documented = set(_split_pipe_list(VOCAB["validation"]))
    assert documented == set(bb_validate.VALIDATION_VALUES)


def test_vocabulary_min_live_matches_validator():
    assert int(VOCAB["min-live"]) == bb_validate.MIN_LIVE_HYPOTHESES


def test_vocabulary_schemas_match_validator():
    documented = set(_split_pipe_list(VOCAB["schemas"]))
    assert documented == {bb_validate.VERDICT_SCHEMA, bb_validate.LEDGER_SCHEMA}
