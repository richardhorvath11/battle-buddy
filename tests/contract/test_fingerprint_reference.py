"""FR-003 / research R6: fingerprint.md <-> bb_fingerprint <-> golden corpus.

Ties the three FR-003 artifacts together mechanically: the doc's stated version
tag must equal the real helper's ``VERSION`` and the golden corpus's ``version``
field, and every worked example the doc ships must recompute exactly through the
real helper — a doc whose prose rules silently diverge from the implementation
fails here even though its version tag still matches.
"""

import re

import pytest

import bb_fingerprint
from conftest import REPO_ROOT, load_fixture

FINGERPRINT_DOC = (
    REPO_ROOT / "skills" / "session-store" / "references" / "fingerprint.md"
)

# Machine-readable worked-example line, per fingerprint.md's stated format:
#   service=<service side> | alert_type=<alert_type side> -> <16 lowercase hex>
_EXAMPLE_LINE_RE = re.compile(
    r"^service=(?P<service>.*) \| alert_type=(?P<alert_type>.*) -> "
    r"(?P<fingerprint>[0-9a-f]{16})$"
)


def _fenced_blocks(text):
    """Every ``` fenced code block's content, in document order."""
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


def _parse_worked_examples(text):
    """Every ``service=... | alert_type=... -> ...`` line inside any fenced block.

    Comment lines (``#...``) and blank lines inside the block are skipped —
    they're mechanical-parsing scaffolding, not examples.
    """
    examples = []
    for block in _fenced_blocks(text):
        for line in block.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            match = _EXAMPLE_LINE_RE.match(stripped)
            if match:
                examples.append(match.groupdict())
    return examples


DOC_TEXT = FINGERPRINT_DOC.read_text(encoding="utf-8")
GOLDEN_CORPUS = load_fixture("fingerprint", "golden.json")
WORKED_EXAMPLES = _parse_worked_examples(DOC_TEXT)


def test_doc_version_tag_matches_helper_version():
    assert "bb.fp.v1" in DOC_TEXT
    assert bb_fingerprint.VERSION == "bb.fp.v1"


def test_doc_version_tag_matches_golden_corpus_version():
    assert GOLDEN_CORPUS["version"] == bb_fingerprint.VERSION


def test_doc_has_at_least_two_worked_examples():
    # TA5-style non-vanishing guard: a reformatted/emptied block must not make
    # this gate disappear as an empty parametrize (skipped, suite still green).
    assert len(WORKED_EXAMPLES) >= 2


@pytest.mark.parametrize(
    "example",
    WORKED_EXAMPLES,
    ids=[e["service"] for e in WORKED_EXAMPLES] or None,
)
def test_worked_example_recomputes_exactly_through_real_helper(example):
    result = bb_fingerprint.fingerprint(example["service"], example["alert_type"])
    assert result["fingerprint"] == example["fingerprint"]
    assert result["version"] == bb_fingerprint.VERSION
