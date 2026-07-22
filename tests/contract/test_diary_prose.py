"""Prose gate for skills/diary/ (FR-006/FR-008; SC-006).

This module is the prose-gate for the diary skill: every hermetic assertion
``skills/diary/**/*.md`` must satisfy lives here, discovered dynamically
(``rglob`` over the skill directory, never a hand-maintained file list).

T001 (Phase 1: Setup) creates this module together with ``skills/diary/`` and
``tests/contract/test_catalog_prose.py``'s ``SCANNED_SKILL_DIRS`` registration
— the three land in the same change on purpose (tasks.md's Dependencies
note): creating ``skills/diary/`` without a scan turns
``test_catalog_prose.py``'s ``test_every_skill_directory_is_covered_by_a_naming_scan``
red by design ("a skill added without one is silently exempt"). T001 lands:

- the doc-set discovery below (mirrors ``test_catalog_prose.py``'s
  ``MD_FILES``/``MD_IDS`` shape);
- a non-vanishing guard whose full **target** set is
  ``{"SKILL.md", "references/format.md"}`` but which ships asserting only
  ``SKILL.md`` — ``references/format.md`` does not exist until T008 (US1)
  writes it, and T008 is what widens this guard to the full target set;
- the SC-006 naming scan itself: the **merged** ``DENY_PATTERNS`` mechanism
  imported from ``test_command_capability_naming.py`` (never a slice-local
  copy of the patterns, and never the slice-3 base set) — the merged set is
  the right one specifically for this skill, since it is the one that
  carries the document-store vendors (``confluence``, ``notion``,
  ``sharepoint``, ``dropbox``), and a doc whose subject *is* a document is
  the doc most likely to name one — together with ``FENCE_RE`` imported from
  ``test_skill_capability_naming.py`` (the shared fence mechanism, restated
  below only as a one-line wrapper so it cannot drift). This is
  ``test_investigation_prose.py``'s own precedent (its line 27/28): import
  exactly those two, from exactly those two modules. The scan runs over
  every discovered doc with that same fence-stripping treatment (a worked
  example's raw data belongs in a fence; normative prose naming a concrete
  product does not), plus a ``mcp__`` literal hard fail that gets **no**
  fence exemption — a literal tool-call string has no legitimate fenced use
  here either, the same posture ``test_skill_capability_naming.py`` takes.

T013 (US2) lands ``SKILL.md``'s Write flow section together with a
**deferral-list mask**, in the same task, per its own note above: the merged
set bans ``confluence`` and ``notion``, and FR-004 *requires* ``SKILL.md`` to
name them — alongside git-markdown — as explicitly deferred adapters. A mask
with nothing yet to mask is the vacuous gate this repo's own precedent warns
about, so the two land together rather than the mask arriving first.

**Why the mask is legitimate** (Constitution VII): the deny-list exists to
stop a skill from naming a concrete product or server as something it
*integrates with* — the "make this HTTP call to that Google API" shape.
FR-004's deferral sentence does the opposite: it names Confluence, Notion,
and git-markdown as adapters this v1 explicitly does **not** wire up. A
deferral list is a boundary statement about non-integration, not an
integration by name, so masking it before the scan is not an exemption from
Constitution VII — it is recognizing that this one sentence was never the
violation the rule targets in the first place.

The mask is **sentence-scoped**, not vendor-word-scoped, unlike
``test_catalog_prose.py``'s ``_mask_canonical_annotation_keys`` (which masks
an open *set* of legitimate key substrings, because catalog annotation keys
are a vocabulary, not a single sentence). Here there is exactly one reviewed
claim to exempt, so the mask target is that sentence's own literal text,
verbatim (``DEFERRED_ADAPTERS_SENTENCE``) — removed wherever it occurs,
never a bare "confluence" or "notion" strip, and never a whole line or
paragraph around it. That keeps the exemption narrow on purpose: the same
vendor word written *anywhere else* in ``skills/diary/`` prose — including
immediately after the sentence on the same line — the regression this whole
scan exists to catch — still fails, because nothing outside the exact
sentence is touched by the mask.
``test_vendor_word_outside_the_deferral_sentence_still_fails`` pins that
half directly against a synthetic same-line decoy naming both merged-in
vendors (Confluence and Notion); the mask's own inputs cannot provide it
since no other sentence in the shipped prose is supposed to name a vendor
at all.

The mask is also **file-scoped**, applied to ``SKILL.md`` only. FR-004's
deferral sentence is required in ``SKILL.md`` alone —
``references/format.md`` deliberately names no vendor at all — so every
other doc under ``skills/diary/`` is scanned with no mask applied, and gets
no exemption it never earned.

Later tasks extend this same module in place, never replace it:

- T008 (US1): widens the non-vanishing guard to the full target set once
  ``references/format.md`` lands.
- T020 (Phase 6): extends the naming scan with a **local** pattern for the
  singular "Google Doc" — the shared deny-list's ``google\\s+docs`` pattern
  does not match it, and it is the exact string design §6.2's MVP heading
  uses.
- T021 (Phase 6): the operation-fidelity gate against
  ``tools/bb-mock-mcp/contract.json``, masked for the skill-level name
  ``write_entry``.
- T022 (Phase 6): the ordering-prose gates (SC-005) — the consumer-side
  no-re-sort statement, the adapter-side reversal statement, and a masked
  negative scan for re-sort directives.
- T023 (Phase 6): the prose<->encoding agreement gates — notice kinds,
  ``STRUCTURE_PARTS``, and the minimal-default skeleton, each asserted both
  ways against ``tests/helpers/diary_reference.py``.
- T024 (Phase 6): the packaging ratchet (FR-008) and the FR-004/FR-005/
  non-goals prose gates.
"""

import pytest

from conftest import REPO_ROOT
from test_command_capability_naming import DENY_PATTERNS
from test_skill_capability_naming import FENCE_RE

SKILLS_DIR = REPO_ROOT / "skills" / "diary"

MD_FILES = sorted(SKILLS_DIR.rglob("*.md"))
MD_IDS = [p.relative_to(SKILLS_DIR).as_posix() for p in MD_FILES]


# ---------------------------------------------------------------------------
# Non-vanishing guard (test_catalog_prose.py's precedent): a broken glob or
# an emptied doc set must not turn every parametrized check the later tasks
# add into a silently-skipped, still-green no-op.
# ---------------------------------------------------------------------------


def test_scan_finds_the_known_diary_docs():
    assert {"SKILL.md", "references/format.md"} <= set(MD_IDS)


# ---------------------------------------------------------------------------
# SC-006 naming scan — the merged DENY_PATTERNS mechanism from
# test_command_capability_naming.py, never a slice-local copy of the
# patterns; FENCE_RE from test_skill_capability_naming.py.
# ---------------------------------------------------------------------------

def _strip_fenced_blocks(text):
    """Restated one-line wrapper (slice-3/4 precedent, test_investigation_prose.py
    line 28): ``FENCE_RE`` is the public constant imported above; the
    stripper itself stays private per module rather than imported across
    (the home module's version is underscore-prefixed).
    """
    return FENCE_RE.sub("", text)


@pytest.mark.parametrize("doc_path", MD_FILES, ids=MD_IDS)
def test_no_concrete_mcp_tool_name_marker(doc_path):
    # Raw text, fenced or not — no fence exemption for this one.
    text = doc_path.read_text(encoding="utf-8")
    assert "mcp__" not in text, (
        "%s references a concrete MCP tool name (mcp__ marker) — SC-006 "
        "requires capability/operation names only, never a hardcoded MCP "
        "tool name; fenced or not, there is no legitimate use here" % doc_path
    )


# ---------------------------------------------------------------------------
# T013 — the deferral-list mask. FR-004 requires SKILL.md's Write flow
# section to name Confluence, Notion, and git-markdown as explicitly
# deferred adapters; the merged DENY_PATTERNS above bans "confluence" and
# "notion" unconditionally. See the module docstring for why masking this
# one sentence before the deny scan is legitimate rather than a loophole.
#
# The mask applies to ``SKILL.md`` only. FR-004's deferral sentence is
# required in ``SKILL.md`` alone — ``references/format.md`` deliberately
# names no vendor at all — so the exemption is scoped to the one doc that
# earns it; the reference doc gets no free exemption it never asked for.
# ---------------------------------------------------------------------------

# Verbatim — must match skills/diary/SKILL.md's Write flow section exactly.
# A whole-sentence literal, not a vendor-word fragment: the mask below
# removes exactly this string, nothing shorter and nothing broader.
DEFERRED_ADAPTERS_SENTENCE = (
    "Confluence, Notion, and git-markdown adapters are explicitly deferred."
)


def _mask_deferred_adapters_sentence(text):
    """Remove the one FR-004 deferral sentence, verbatim, before the
    deny-list scan runs. Whole-sentence removal rather than a vendor-word
    strip: the mask exempts this exact, reviewed claim and nothing else, so
    the same vendor word written anywhere else in the prose — a slip back
    toward naming a real integration — still fails the scan below.
    """
    return text.replace(DEFERRED_ADAPTERS_SENTENCE, "")


@pytest.mark.parametrize("doc_path", MD_FILES, ids=MD_IDS)
def test_no_concrete_server_product_name_outside_fences(doc_path):
    text = doc_path.read_text(encoding="utf-8")
    stripped = _strip_fenced_blocks(text)
    # Scoped to SKILL.md: that is the only doc FR-004 requires the deferral
    # sentence in, so every other doc — references/format.md included —
    # gets the deny scan with no mask applied at all.
    prose = _mask_deferred_adapters_sentence(stripped) if doc_path.name == "SKILL.md" else stripped
    hits = sorted(name for name, pattern in DENY_PATTERNS.items() if pattern.search(prose))
    assert not hits, (
        "%s names a concrete MCP server/product in normative prose: %r — "
        "SC-006 permits only capability/operation names, never a vendor or "
        "product name (Constitution VII), with the single FR-004 "
        "deferred-adapters sentence masked out first when doc_path is "
        "SKILL.md" % (doc_path, hits)
    )


def test_deferred_adapters_sentence_is_present_and_masked_scan_passes():
    """Control half (i): the mask has something real to exempt (the FR-004
    sentence actually landed in SKILL.md, verbatim — not survivorship
    because it was never written), and masking it removes every deny-list
    hit that sentence alone causes.
    """
    skill_md = next(p for p in MD_FILES if p.name == "SKILL.md")
    text = skill_md.read_text(encoding="utf-8")
    assert DEFERRED_ADAPTERS_SENTENCE in text, (
        "expected the FR-004 deferred-adapters sentence verbatim in "
        "SKILL.md — DEFERRED_ADAPTERS_SENTENCE has nothing to exempt "
        "without it, which would make the mask vacuous"
    )

    masked = _mask_deferred_adapters_sentence(_strip_fenced_blocks(text))
    hits = sorted(name for name, pattern in DENY_PATTERNS.items() if pattern.search(masked))
    assert not hits, (
        "masking DEFERRED_ADAPTERS_SENTENCE out of SKILL.md should remove "
        "every deny-list hit that sentence alone causes; survivor(s): %r"
        % hits
    )


def test_vendor_word_outside_the_deferral_sentence_still_fails():
    """Control half (ii): the mask exempts the one reviewed sentence, never
    the bare vendor word wherever it appears — and the mask is scoped to
    that exact sentence, not to the line or paragraph it sits in. A vendor
    mention placed on the SAME LINE, immediately after the deferral
    sentence, is the discriminating case: a line- or paragraph-scoped mask
    would swallow it right along with the sentence it is anchored to, while
    the shipped literal-sentence mask removes only the exact reviewed text
    and leaves the trailing mention intact. This is the load-bearing half: a
    mask built as a vendor-word strip, or widened to line/paragraph scope,
    would pass this file's real content today AND silently swallow a real
    violation tomorrow; only a synthetic decoy proves the difference.

    Both merged-in vendors get named here (Confluence and Notion), not just
    one — the exemption covers both, and a decoy naming only one would never
    notice if the other's pattern dropped out of the merged DENY_PATTERNS.
    """
    decoy = (
        DEFERRED_ADAPTERS_SENTENCE
        + " Some teams pipe entries into Confluence or Notion directly instead."
    )
    masked = _mask_deferred_adapters_sentence(_strip_fenced_blocks(decoy))
    hits = sorted(name for name, pattern in DENY_PATTERNS.items() if pattern.search(masked))
    assert hits == ["confluence", "notion"], (
        "expected masking to remove only the deferral sentence, leaving a "
        "same-line, same-vendor-word mention right after it still caught by "
        "the deny-list scan for both merged-in vendors; got hits=%r" % hits
    )
