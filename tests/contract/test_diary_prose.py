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
  requires the plural and does not match it, and "Google Doc" (singular) is
  the exact string design §6.2's MVP heading uses, making it the string
  most likely to be copied verbatim into this skill's own prose.
  Load-bearing, not belt-and-braces.
- T021 (Phase 6): the operation-fidelity gate against
  ``tools/bb-mock-mcp/contract.json``, masked for the skill-level name
  ``write_entry`` via ``SKILL_LEVEL_NAMES`` — see "Why write_entry needs a
  mask" below.
- T022 (Phase 6): the ordering-prose gates (SC-005) over
  ``references/format.md``'s "Ordering consumption" section — the
  consumer-side no-re-sort statement, the adapter-side reversal statement,
  and a negative scan for re-sort directives, sentence-masked for the one
  legitimate adapter-side mention.
- T023 (Phase 6): the prose<->encoding agreement gates — notice kinds,
  ``STRUCTURE_PARTS``, and the minimal-default skeleton, each asserted
  against ``tests/helpers/diary_reference.py`` via table-scoped parsing
  (``test_catalog_prose.py``'s own technique for its annotation tables,
  never a loose "name in text" substring check).
- T024 (Phase 6): the packaging ratchet (FR-008: no ``*.py`` under
  ``skills/diary/``, the reference encoding named by no shipped-bundle
  glob) and the FR-004/FR-005/non-goals prose gates.

**Why write_entry needs a mask, and read_recent does not** (T021): the
imported op-like predicate here (``OP_LIKE_SUFFIXES`` plus
``CURATED_OP_CANDIDATES``, both from ``test_skill_capability_naming.py``,
unchanged) flags any backtick-quoted token ending ``_entry`` as
op-shaped — exactly right for a doc citing a *contract* operation, and
exactly wrong for ``write_entry``, the *skill-level* name FR-001 requires
``SKILL.md``'s Interface section to state (the contract op it realizes onto
is ``append_entry``, a different string entirely). Without
``SKILL_LEVEL_NAMES = {"write_entry"}`` exempting it, the fidelity gate
would reject the one name FR-001 mandates the doc state — the same shape of
false positive T013's deferral-list mask exists to fix for FR-004.
``read_recent`` needs no such mask: ``SKILL.md``'s own realization table
maps ``read_recent(n)`` to the contract's ``read_recent(n)`` unchanged (the
one skill-level name that is *also* its own contract name), and it is
already carried in the imported ``CURATED_OP_CANDIDATES``. The mask is
name-scoped, not suffix-scoped, and deliberately narrow: it exempts the
literal string ``write_entry`` and nothing shaped like it, so a genuinely
fabricated operation — this module's own planted ``read_entries`` control —
still fails.
"""

import fnmatch
import json
import re

import pytest

from conftest import REPO_ROOT
from helpers.diary_reference import (
    DEFAULT_READ_DEPTH,
    MINIMAL_DEFAULT,
    MINIMAL_DEFAULT_TEXT,
    NOTICE_KINDS,
    STRUCTURE_PARTS,
    _date_format_for_line,
    extract_structure,
    resolve_date_ambiguity,
    resolve_format,
)
from test_command_capability_naming import DENY_PATTERNS
from test_skill_capability_naming import (
    BACKTICK_TOKEN_RE,
    CURATED_OP_CANDIDATES,
    FENCE_RE,
    OP_LIKE_SUFFIXES,
)

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


# ---------------------------------------------------------------------------
# T020 — local hardening of the naming scan: the singular "Google Doc". The
# shared merged DENY_PATTERNS' "google docs" entry requires the plural
# (``google\s+docs``) and does not match the singular "Google Doc" — the
# exact string design §6.2's MVP heading uses (bb-technical-design.md), and
# therefore the string most likely to be copied verbatim into this skill's
# own prose. Load-bearing, not belt-and-braces: without this local
# addition, a copy-pasted "Google Doc" heading would sail through the
# shared scan untouched. Follows test_catalog_prose.py's own local-
# extension precedent (its ``CATALOG_DENY_PATTERNS["github"]``).
# ---------------------------------------------------------------------------

DIARY_DENY_PATTERNS = dict(DENY_PATTERNS)
DIARY_DENY_PATTERNS["google doc"] = re.compile(r"google\s+docs?", re.IGNORECASE)


def test_google_doc_singular_is_rejected_by_the_local_pattern():
    """Positive control (i): the shared 'google docs' pattern genuinely
    misses the singular — proving the local addition above is load-bearing,
    not belt-and-braces — and the local pattern genuinely catches it."""
    assert not DENY_PATTERNS["google docs"].search("Google Doc"), (
        "expected the shared 'google docs' pattern to MISS the singular "
        "'Google Doc' — if it now matches, T020's local pattern has become "
        "belt-and-braces rather than load-bearing and this control should "
        "be revisited"
    )
    assert DIARY_DENY_PATTERNS["google doc"].search("Google Doc"), (
        "the local google\\s+docs? pattern must reject the singular "
        "'Google Doc'"
    )


def test_shared_deny_patterns_reject_a_string_they_should():
    """Positive control (ii): the imported shared DENY_PATTERNS mechanism
    itself has teeth on a string it is documented to catch — without this,
    a broken import or an emptied pattern dict could make every scan below
    pass vacuously."""
    assert DENY_PATTERNS["google docs"].search("Google Docs"), (
        "expected the shared 'google docs' pattern to match its own "
        "documented plural string 'Google Docs'"
    )


@pytest.mark.parametrize("doc_path", MD_FILES, ids=MD_IDS)
def test_no_concrete_server_product_name_outside_fences(doc_path):
    text = doc_path.read_text(encoding="utf-8")
    stripped = _strip_fenced_blocks(text)
    # Scoped to SKILL.md: that is the only doc FR-004 requires the deferral
    # sentence in, so every other doc — references/format.md included —
    # gets the deny scan with no mask applied at all.
    prose = _mask_deferred_adapters_sentence(stripped) if doc_path.name == "SKILL.md" else stripped
    hits = sorted(name for name, pattern in DIARY_DENY_PATTERNS.items() if pattern.search(prose))
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
    # G8 (round 2): both masks are `text.replace(sentence, "")` with no
    # count limit — `str.replace` with no count exempts EVERY occurrence,
    # so a duplicated masked sentence would be silently exempted twice
    # rather than caught. This asserts the source has exactly one
    # occurrence to mask, so a future accidental duplicate (e.g. the
    # sentence pasted twice) fails loudly here instead of sailing through
    # the deny-list scan unnoticed.
    assert text.count(DEFERRED_ADAPTERS_SENTENCE) == 1, (
        "expected DEFERRED_ADAPTERS_SENTENCE exactly once in SKILL.md — "
        "found %d; a duplicate would be silently exempted twice by the "
        "unbounded replace() mask" % text.count(DEFERRED_ADAPTERS_SENTENCE)
    )

    masked = _mask_deferred_adapters_sentence(_strip_fenced_blocks(text))
    hits = sorted(name for name, pattern in DIARY_DENY_PATTERNS.items() if pattern.search(masked))
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
    hits = sorted(name for name, pattern in DIARY_DENY_PATTERNS.items() if pattern.search(masked))
    assert hits == ["confluence", "notion"], (
        "expected masking to remove only the deferral sentence, leaving a "
        "same-line, same-vendor-word mention right after it still caught by "
        "the deny-list scan for both merged-in vendors; got hits=%r" % hits
    )


# ---------------------------------------------------------------------------
# T021 — operation-fidelity gate: every backtick-quoted single-token span in
# skills/diary/**/*.md that LOOKS LIKE a contract operation (the imported
# OP_LIKE_SUFFIXES / CURATED_OP_CANDIDATES predicate
# test_skill_capability_naming.py uses for skills/session-store/) must be a
# real operation in tools/bb-mock-mcp/contract.json — or the one
# skill-level exception in SKILL_LEVEL_NAMES below. The valid op set is
# built dynamically from contract.json, never hardcoded.
#
# See the module docstring's "Why write_entry needs a mask, and read_recent
# does not" for the full reasoning.
# ---------------------------------------------------------------------------

CONTRACT_PATH = REPO_ROOT / "tools" / "bb-mock-mcp" / "contract.json"


def _load_contract_ops():
    with open(str(CONTRACT_PATH), encoding="utf-8") as f:
        contract = json.load(f)
    ops = set()
    for capability in contract["capabilities"].values():
        ops.update(capability["ops"].keys())
    return ops


CONTRACT_OPS = _load_contract_ops()

# FR-001 requires SKILL.md's Interface section to state the skill-level
# name write_entry (realizing onto the contract's append_entry). It ends
# in "_entry", so the imported op-like-suffix predicate flags it as
# op-shaped; without this mask the fidelity gate below would reject the
# exact name FR-001 mandates. read_recent needs no equivalent entry here:
# it is a real contract op under both its skill-level name and its
# realized name (SKILL.md's own realization table maps read_recent(n) to
# the contract's read_recent(n) unchanged), and it is already carried in
# the imported CURATED_OP_CANDIDATES.
SKILL_LEVEL_NAMES = {"write_entry"}

# The imported OP_LIKE_SUFFIXES pairs "_record"/"_records" but only
# "_entry" (no "_entries") — a gap this module closes locally so a
# plausible fabrication like "read_entries" (this module's own planted
# violation below) is recognized as op-shaped by the SAME predicate the
# real per-doc gate uses, rather than a separate predicate invented just
# for the control. It costs nothing against real content: the only
# op-like tokens either shipped doc actually cites are append_entry,
# read_recent and write_entry (test_diary_docs_cite_the_expected_core_operations
# pins exactly that set, non-vacuously).
DIARY_OP_LIKE_SUFFIXES = OP_LIKE_SUFFIXES + ("_entries",)


def _looks_like_op(token):
    return token.endswith(DIARY_OP_LIKE_SUFFIXES) or token in CURATED_OP_CANDIDATES


def _op_like_tokens(text):
    return {tok for tok in BACKTICK_TOKEN_RE.findall(text) if _looks_like_op(tok)}


@pytest.mark.parametrize("doc_path", MD_FILES, ids=MD_IDS)
def test_doc_cited_operations_exist_in_contract_or_are_skill_level(doc_path):
    text = doc_path.read_text(encoding="utf-8")
    cited = _op_like_tokens(text)
    unknown = sorted(cited - CONTRACT_OPS - SKILL_LEVEL_NAMES)
    assert not unknown, (
        "%s cites operation-like token(s) absent from contract.json's "
        "capabilities and not in SKILL_LEVEL_NAMES: %r" % (doc_path, unknown)
    )


def test_diary_docs_cite_the_expected_core_operations():
    # Non-vacuity: the fidelity check above has something real to bite on.
    all_text = "\n".join(p.read_text(encoding="utf-8") for p in MD_FILES)
    cited = _op_like_tokens(all_text)
    assert {"append_entry", "read_recent", "write_entry"} <= cited


def test_write_entry_is_a_masked_skill_level_name_actually_cited():
    """Control half (i): write_entry passes — the mask has something real
    to exempt (SKILL.md genuinely cites it), and write_entry is genuinely
    NOT a contract op (the wire op is append_entry), so the mask is doing
    real work rather than exempting an already-valid name."""
    assert "write_entry" not in CONTRACT_OPS
    skill_md = next(p for p in MD_FILES if p.name == "SKILL.md")
    cited = _op_like_tokens(skill_md.read_text(encoding="utf-8"))
    assert "write_entry" in cited
    assert "write_entry" not in (cited - CONTRACT_OPS - SKILL_LEVEL_NAMES)


def test_fabricated_read_entries_still_fails_the_fidelity_gate():
    """Control half (ii): the mask is scoped to write_entry alone. A
    fabricated operation that was never documented and is not a real
    contract op must still fail — proving SKILL_LEVEL_NAMES has not grown
    into a general escape hatch."""
    synthetic = "the skill never exposes a bulk `read_entries` operation"
    cited = _op_like_tokens(synthetic)
    assert "read_entries" in cited
    unknown = cited - CONTRACT_OPS - SKILL_LEVEL_NAMES
    assert "read_entries" in unknown


def test_read_recent_needs_no_mask():
    # Recorded per T021: read_recent is a real contract op under both its
    # skill-level name and its realized name, and it is already curated —
    # nothing for SKILL_LEVEL_NAMES to add.
    assert "read_recent" in CONTRACT_OPS
    assert "read_recent" not in SKILL_LEVEL_NAMES
    assert "read_recent" in CURATED_OP_CANDIDATES


# ---------------------------------------------------------------------------
# Shared doc-text constants and helpers for T022-T024 below.
# ---------------------------------------------------------------------------

SKILL_MD_PATH = next(p for p in MD_FILES if p.name == "SKILL.md")
FORMAT_MD_PATH = next(
    p for p in MD_FILES if p.relative_to(SKILLS_DIR).as_posix() == "references/format.md"
)
SKILL_MD_TEXT = SKILL_MD_PATH.read_text(encoding="utf-8")
FORMAT_MD_TEXT = FORMAT_MD_PATH.read_text(encoding="utf-8")


def _normalize_whitespace(text):
    """Collapses every run of whitespace — including the hard-wrap line
    breaks markdown prose is full of — to a single space, so a phrase or
    pattern split across a wrapped line is not missed, and (T022) a
    lookbehind exclusion sees "never re-sort" as adjacent words rather than
    words separated by a literal line break."""
    return re.sub(r"\s+", " ", text)


SKILL_MD_NORMALIZED = _normalize_whitespace(SKILL_MD_TEXT)
FORMAT_MD_NORMALIZED = _normalize_whitespace(FORMAT_MD_TEXT)


def _markdown_section(heading, text, doc_path):
    """The body text between a '## <heading>' line and the next '## '
    heading (or end of document) — test_catalog_prose.py's own
    ``_markdown_section`` precedent, restated here (private helper, not a
    shared mechanism)."""
    pattern = re.compile(
        r"^##\s+" + re.escape(heading) + r"\s*\n(.*?)(?=\n##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    assert match is not None, "expected a '## %s' section in %s" % (heading, doc_path)
    return match.group(1)


# ---------------------------------------------------------------------------
# T022 — ordering-prose gates (SC-005) over references/format.md's
# "Ordering consumption" section: the consumer-side no-re-sort commitment,
# the adapter-side reversal commitment, and a negative scan for
# consumer-side re-sort DIRECTIVES that masks only the one legitimate
# adapter-side mention.
#
# Scoped to the "Ordering consumption" section specifically, not the whole
# document: format.md's own intro sentence ("Follow the decision in the
# stated order; nothing here is a menu of options to reorder.") legitimately
# uses the word "reorder" about the RESOLUTION DECISION's step order, a
# concern unrelated to entry-ordering consumption — scanning the whole
# document trips on it. Scoping to the section that actually states the
# ordering-consumption commitment is also the more precise gate: it is what
# would catch the statement being moved out of this section entirely, the
# same reasoning test_catalog_prose.py's own freshness gate uses for
# scoping to SKILL.md specifically.
# ---------------------------------------------------------------------------

ORDERING_CONSUMPTION_SECTION = _markdown_section(
    "Ordering consumption", FORMAT_MD_TEXT, FORMAT_MD_PATH
)
ORDERING_CONSUMPTION_NORMALIZED = _normalize_whitespace(ORDERING_CONSUMPTION_SECTION)

CONSUMER_SIDE_NO_RESORT_PHRASE = "consumers never re-sort them"

# Verbatim (post whitespace-normalization) — the one sentence T008 placed in
# references/format.md that legitimately mentions "oldest-first" and
# "reverses on read" at all.
ADAPTER_SIDE_REVERSAL_SENTENCE = (
    "an adapter sitting over a store that is natively oldest-first "
    "**reverses on read**, so that its consumers never have to."
)


def test_format_md_states_the_consumer_side_no_resort_commitment():
    assert CONSUMER_SIDE_NO_RESORT_PHRASE in ORDERING_CONSUMPTION_NORMALIZED, (
        "SC-005: references/format.md's 'Ordering consumption' section "
        "must state the consumer-side ordering commitment — %r not found"
        % CONSUMER_SIDE_NO_RESORT_PHRASE
    )


def test_format_md_states_the_adapter_side_reversal_commitment():
    # Gate (ii): what stops the negative scan's mask below being vacuous —
    # asserted here for real, not just implied by the mask happening to work.
    assert ADAPTER_SIDE_REVERSAL_SENTENCE in ORDERING_CONSUMPTION_NORMALIZED, (
        "SC-005: references/format.md's 'Ordering consumption' section "
        "must also state the adapter-side half of the ordering commitment "
        "— an adapter over a natively oldest-first store reverses on read "
        "— sentence %r not found" % ADAPTER_SIDE_REVERSAL_SENTENCE
    )


# Enumerated, at minimum, per T022. "re-sort" excludes the one legitimate
# negated use ("consumers never re-sort them") via a lookbehind rather than
# via the sentence mask below — the mask below is scoped to the
# adapter-side sentence only, so the consumer-side sentence's own
# legitimate "re-sort" mention has to survive on the pattern's own terms.
REORDER_DIRECTIVE_PATTERNS = {
    "re-sort": re.compile(r"(?<!never )re-sort", re.IGNORECASE),
    "resort": re.compile(r"resort", re.IGNORECASE),
    "sort the entries": re.compile(r"sort the entries", re.IGNORECASE),
    "reorder": re.compile(r"reorder", re.IGNORECASE),
    "oldest first": re.compile(r"oldest[\s-]+first", re.IGNORECASE),
}


def _mask_adapter_side_sentence(text):
    return text.replace(ADAPTER_SIDE_REVERSAL_SENTENCE, "")


def test_reorder_directive_patterns_have_teeth_on_each_enumerated_form():
    # Non-vacuity: each pattern actually catches the directive shape it is
    # meant to, on realistic bad phrasing that is not in the shipped doc.
    for name, sample in (
        ("re-sort", "the flow should re-sort them again"),
        ("resort", "no consumer may resort the list"),
        ("sort the entries", "always sort the entries before use"),
        ("reorder", "never reorder what read_recent returns"),
        ("oldest first", "entries then arrive oldest first"),
    ):
        assert REORDER_DIRECTIVE_PATTERNS[name].search(sample), (
            "pattern %r should catch %r" % (name, sample)
        )


@pytest.mark.parametrize("doc_path", MD_FILES, ids=MD_IDS)
def test_no_consumer_side_resort_directive_outside_the_adapter_sentence(doc_path):
    # WHOLE-DOCUMENT scan, deliberately, not the "Ordering consumption"
    # section alone. Slice 7 recorded the reasoning this follows
    # (test_catalog_prose.py's SC-006 scope note): a gate bounded by a
    # section heading "would need a section boundary the prose does not
    # carry, and any such boundary is gameable by moving a sentence past
    # it." A re-sort directive written into some other section of this
    # document is exactly as wrong as one written into this one, and a
    # section-scoped negative scan would wave it through. The positive
    # gates above stay section-scoped — those assert the commitment is in
    # its documented home, which is a different question.
    #
    # F9 (review round): PARAMETRIZED over every doc under skills/diary/,
    # not references/format.md alone. SKILL.md carries the same
    # interface-level ordering commitment ("consumers use that order as-is
    # — they never re-sort it"), and SC-005 covers the documented flow
    # ACROSS both docs — a file-scoped negative scan has exactly the same
    # "gameable by moving a sentence past it" hole a section-scoped one
    # does, just at a coarser grain. The adapter-side reversal sentence is
    # masked only for references/format.md — it is the only doc that
    # legitimately states it (SKILL.md never mentions the adapter-side
    # reversal at all), so every other doc gets the scan with no mask.
    text = doc_path.read_text(encoding="utf-8")
    normalized = _normalize_whitespace(text)
    if doc_path == FORMAT_MD_PATH:
        normalized = _mask_adapter_side_sentence(normalized)
    hits = sorted(
        name for name, pattern in REORDER_DIRECTIVE_PATTERNS.items() if pattern.search(normalized)
    )
    assert not hits, (
        "%s names consumer-side re-sort directive(s) %r — SC-005 requires "
        "read_recent's order consumed as-is across every doc under "
        "skills/diary/, with the single adapter-side reversal sentence "
        "(references/format.md only) masked out first" % (doc_path, hits)
    )


def test_adapter_side_sentence_present_and_masking_removes_every_hit_it_causes():
    """Two-halved control (T022): the mask has something real to exempt —
    the adapter-side sentence alone trips at least one reorder-directive
    pattern (oldest first) — and masking it out of the section's full,
    normalized text removes every hit that sentence alone causes.
    """
    assert ADAPTER_SIDE_REVERSAL_SENTENCE in ORDERING_CONSUMPTION_NORMALIZED, (
        "expected the adapter-side reversal sentence verbatim (after "
        "whitespace normalization) in references/format.md — the mask has "
        "nothing to exempt without it, which would make it vacuous"
    )
    # G8 (round 2) — this mask's own twin of the assertion added to
    # test_deferred_adapters_sentence_is_present_and_masked_scan_passes:
    # _mask_adapter_side_sentence is also an unbounded replace(), so a
    # duplicated sentence would be silently exempted twice rather than
    # caught by the reorder-directive scan.
    assert ORDERING_CONSUMPTION_NORMALIZED.count(ADAPTER_SIDE_REVERSAL_SENTENCE) == 1, (
        "expected ADAPTER_SIDE_REVERSAL_SENTENCE exactly once in the "
        "'Ordering consumption' section — found %d; a duplicate would be "
        "silently exempted twice by the unbounded replace() mask"
        % ORDERING_CONSUMPTION_NORMALIZED.count(ADAPTER_SIDE_REVERSAL_SENTENCE)
    )
    unmasked_hits = sorted(
        name
        for name, pattern in REORDER_DIRECTIVE_PATTERNS.items()
        if pattern.search(ADAPTER_SIDE_REVERSAL_SENTENCE)
    )
    assert unmasked_hits, (
        "expected the adapter-side sentence alone to trip at least one "
        "reorder-directive pattern — otherwise masking it removes nothing "
        "and this control is vacuous"
    )
    masked = _mask_adapter_side_sentence(ORDERING_CONSUMPTION_NORMALIZED)
    survivors = sorted(
        name for name in unmasked_hits if REORDER_DIRECTIVE_PATTERNS[name].search(masked)
    )
    assert not survivors, (
        "masking ADAPTER_SIDE_REVERSAL_SENTENCE out of format.md's "
        "'Ordering consumption' section should remove every "
        "reorder-directive hit that sentence alone causes; survivor(s): %r"
        % survivors
    )


# ---------------------------------------------------------------------------
# T023 — prose<->encoding agreement gates: references/format.md's own
# tables and quoted skeleton against tests/helpers/diary_reference.py's
# NOTICE_KINDS, STRUCTURE_PARTS, MINIMAL_DEFAULT_TEXT and MINIMAL_DEFAULT.
# Table-scoped parsing (test_catalog_prose.py's own technique for its
# annotation tables), never a loose "name in text" substring check — a
# substring check would stay green through an invented fifth notice kind
# sitting in the same table as the real four.
# ---------------------------------------------------------------------------

_TABLE_SEPARATOR_RE = re.compile(r"^:?-+:?$")


def _first_table_rows(text):
    """The FIRST contiguous run of '|'-prefixed lines in ``text``, as a
    list of cell-lists (header/separator rows excluded by content). Both
    T023 callers scope a whole '##' section that contains exactly one
    leading table followed by ordinary prose ("Structure extraction"'s
    section also contains '###' subsections with tables of their own,
    further down) — taking only the first contiguous run isolates that one
    leading table without needing to parse subsection boundaries at all.
    """
    rows = []
    started = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            started = True
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(_TABLE_SEPARATOR_RE.match(c) for c in cells):
                continue
            rows.append(cells)
        elif started:
            break
    return rows


def _backtick_token(cell):
    match = BACKTICK_TOKEN_RE.search(cell)
    assert match is not None, "expected a backtick-quoted token in table cell %r" % cell
    return match.group(1)


NOTICE_KINDS_SECTION = _markdown_section("Notice kinds", FORMAT_MD_TEXT, FORMAT_MD_PATH)
# [1:] drops the header row ("kind" / "Surfaced when") — _first_table_rows
# already excludes the '---' separator row by content, but the header row
# itself has no backtick-quoted first cell to extract.
NOTICE_KINDS_TABLE_ROWS = _first_table_rows(NOTICE_KINDS_SECTION)[1:]
DOC_NOTICE_KINDS = frozenset(_backtick_token(row[0]) for row in NOTICE_KINDS_TABLE_ROWS)

STRUCTURE_EXTRACTION_SECTION = _markdown_section(
    "Structure extraction", FORMAT_MD_TEXT, FORMAT_MD_PATH
)
STRUCTURE_PARTS_TABLE_ROWS = _first_table_rows(STRUCTURE_EXTRACTION_SECTION)[1:]
DOC_STRUCTURE_PARTS = tuple(_backtick_token(row[0]) for row in STRUCTURE_PARTS_TABLE_ROWS)


def test_notice_kinds_table_parses_nonvacuously():
    assert NOTICE_KINDS_TABLE_ROWS, (
        "parsed zero rows from references/format.md's Notice kinds table — "
        "a broken table parser would make the agreement assertion below "
        "vacuously true"
    )


def test_format_md_notice_kinds_match_the_encoding_both_ways():
    assert DOC_NOTICE_KINDS == NOTICE_KINDS, (
        "references/format.md's Notice kinds table and "
        "diary_reference.NOTICE_KINDS disagree: doc names %r, encoding "
        "declares %r" % (sorted(DOC_NOTICE_KINDS), sorted(NOTICE_KINDS))
    )


def test_structure_parts_table_parses_nonvacuously():
    assert STRUCTURE_PARTS_TABLE_ROWS, (
        "parsed zero rows from references/format.md's Structure extraction "
        "table — a broken table parser would make the agreement assertion "
        "below vacuously true"
    )


def test_format_md_structure_parts_match_the_encoding_both_ways():
    assert DOC_STRUCTURE_PARTS == STRUCTURE_PARTS, (
        "references/format.md's Structure extraction table and "
        "diary_reference.STRUCTURE_PARTS disagree: doc names %r in order, "
        "encoding declares %r" % (DOC_STRUCTURE_PARTS, STRUCTURE_PARTS)
    )


_FENCE_CONTENT_RE = re.compile(r"```\n(.*?)```", re.DOTALL)


def test_minimal_default_skeleton_is_quoted_byte_identical_in_format_md():
    # Deliberately NOT _markdown_section: the fenced skeleton's own body
    # contains "## " lines ("## What happened", "## Timeline", ...), and
    # _markdown_section's heading-boundary regex has no notion of fences —
    # it would stop at the first of those look-alike headings, truncating
    # the section before the fence ever closes. Instead: locate the "The
    # minimal default" heading's own position and search for the first
    # fenced block anywhere after it in the FULL (untruncated) text.
    heading_match = re.search(r"^##\s+The minimal default\s*$", FORMAT_MD_TEXT, re.MULTILINE)
    assert heading_match is not None, (
        "expected a '## The minimal default' heading in references/format.md"
    )
    match = _FENCE_CONTENT_RE.search(FORMAT_MD_TEXT, heading_match.end())
    assert match is not None, (
        "expected a fenced code block carrying the minimal-default "
        "skeleton after references/format.md's 'The minimal default' "
        "heading"
    )
    assert match.group(1) == MINIMAL_DEFAULT_TEXT, (
        "the minimal-default skeleton quoted in references/format.md is "
        "not byte-identical to diary_reference.MINIMAL_DEFAULT_TEXT"
    )


def test_extract_structure_of_minimal_default_text_matches_minimal_default_in_full():
    # data-model §3's pattern-language rule is what makes the skeleton's
    # own title line ("# YYYY-MM-DD - ...") date-bearing, so every part —
    # title and date_format included — reproduces with no carve-out.
    assert extract_structure(MINIMAL_DEFAULT_TEXT) == MINIMAL_DEFAULT, (
        "extract_structure(MINIMAL_DEFAULT_TEXT) must equal MINIMAL_DEFAULT "
        "in full — a divergence here means the two hand-written constants "
        "in diary_reference.py (deliberately not derived from each other, "
        "per that module's own comment) have drifted apart"
    )


# ---------------------------------------------------------------------------
# G5 (round 2) — DEFAULT_READ_DEPTH had no mechanical anchor: nothing
# checked that references/format.md's stated read depth agreed with the
# encoding's constant. Unlike DEFAULT_READ_DEPTH's own documented deferral
# (no landed consumer reads the override key yet — that half genuinely IS
# prose-only), a doc/encoding drift on the DEFAULT value itself is CI
# observable right now, so it is gated here rather than left as prose-only
# — the same both-ways agreement style T023's NOTICE_KINDS / STRUCTURE_PARTS
# gates above use: the depth is PARSED out of format.md's own text, never
# hardcoded in this test, so a doc edit that silently drifts from the
# encoding's constant (or vice versa) fails here instead of surviving
# unnoticed.
# ---------------------------------------------------------------------------

_READ_DEPTH_RE = re.compile(r"go \*\*(\d+) entries deep by default\*\*")


def test_read_depth_sentence_parses_nonvacuously():
    match = _READ_DEPTH_RE.search(FORMAT_MD_TEXT)
    assert match is not None, (
        "expected references/format.md's 'Read depth' section to state "
        "'go **N entries deep by default**' — parsed zero matches, which "
        "would make the agreement assertion below vacuously true"
    )


def test_format_md_read_depth_matches_the_encoding_constant():
    match = _READ_DEPTH_RE.search(FORMAT_MD_TEXT)
    assert match is not None
    doc_depth = int(match.group(1))
    assert doc_depth == DEFAULT_READ_DEPTH, (
        "references/format.md states a default read depth of %d, but "
        "diary_reference.DEFAULT_READ_DEPTH is %d — the two must agree"
        % (doc_depth, DEFAULT_READ_DEPTH)
    )


# H4 (round 3) — the gate above only ever parsed references/format.md;
# SKILL.md's own Interface section states the same default independently
# ("n defaults to 5" in its `read_recent(n)` signature comment), and
# nothing checked that one at all — a doc edit that drifted SKILL.md's
# stated default from the encoding's constant (or from format.md's own
# statement) would have sailed through silently. Same both-ways,
# parsed-not-hardcoded style as the format.md gate above, with its own
# non-vacuity guard so a broken regex can't make the agreement assertion
# vacuously true either.

_SKILL_MD_READ_DEPTH_RE = re.compile(r"n defaults to (\d+)")


def test_skill_md_read_depth_sentence_parses_nonvacuously():
    match = _SKILL_MD_READ_DEPTH_RE.search(SKILL_MD_TEXT)
    assert match is not None, (
        "expected SKILL.md's Interface section to state 'n defaults to N' "
        "— parsed zero matches, which would make the agreement assertion "
        "below vacuously true"
    )


def test_skill_md_read_depth_matches_the_encoding_constant():
    match = _SKILL_MD_READ_DEPTH_RE.search(SKILL_MD_TEXT)
    assert match is not None
    doc_depth = int(match.group(1))
    assert doc_depth == DEFAULT_READ_DEPTH, (
        "SKILL.md states a default read depth of %d, but "
        "diary_reference.DEFAULT_READ_DEPTH is %d — the two must agree"
        % (doc_depth, DEFAULT_READ_DEPTH)
    )


# ---------------------------------------------------------------------------
# J4 (round 4) — doc<->encoding agreement gates for the tokenizer/ambiguity
# rules references/format.md documents in prose, in the same both-ways style
# as T023's NOTICE_KINDS/STRUCTURE_PARTS gates above: each gate below (a)
# asserts the doc states the rule (a verbatim, paragraph-scoped substring —
# so deleting the paragraph makes this half fail) and (b) executes a worked
# example FROM that same substring through the encoding, asserting the
# documented outcome. Mutation-tested (reported in the round-4 PR): deleting
# either half's substring, or flipping the encoding's behavior, fails the
# corresponding test — neither half is decorative.
# ---------------------------------------------------------------------------

# (i) Digit-glue boundaries — "Date-format tokens" section.
DIGIT_GLUE_DOC_SENTENCE = (
    "`1.2.3-4/5/2026` and `build 2026-07-21-3` therefore carry no recognized date at all."
)


def test_format_md_states_the_digit_glue_worked_examples():
    assert DIGIT_GLUE_DOC_SENTENCE in FORMAT_MD_TEXT, (
        "expected references/format.md's Digit-glue boundaries paragraph to name "
        "its two worked examples verbatim — %r not found" % DIGIT_GLUE_DOC_SENTENCE
    )


def test_digit_glue_worked_examples_carry_no_recognized_date_in_the_encoding():
    for example in ("1.2.3-4/5/2026", "build 2026-07-21-3"):
        assert _date_format_for_line(example) is None, (
            "%r is the doc's own digit-glue worked example — the encoding must "
            "carry no recognized date for it, per references/format.md's "
            "Digit-glue boundaries paragraph" % example
        )


# (ii) Both-components-over-12 ambiguity — "Numeric date ambiguity" section.
BOTH_OVER_12_DOC_SENTENCE = (
    "`99/99/9999` is provisionally labelled `MM/DD/YYYY` and flagged `ambiguous`, "
    "the same as the ≤ 12 case."
)


def test_format_md_states_the_both_over_12_worked_example():
    assert BOTH_OVER_12_DOC_SENTENCE in FORMAT_MD_NORMALIZED, (
        "expected references/format.md's Numeric date ambiguity section to state "
        "the both-components-over-12 worked example verbatim — %r not found"
        % BOTH_OVER_12_DOC_SENTENCE
    )


def test_both_over_12_worked_example_matches_the_encoding():
    assert _date_format_for_line("99/99/9999") == {"pattern": "MM/DD/YYYY", "ambiguous": True}, (
        "the doc's own '99/99/9999' worked example must provisionally label as "
        "MM/DD/YYYY and flag ambiguous, per references/format.md's Numeric date "
        "ambiguity section"
    )


# (iii) Start-of-line 2-digit-year rule (J1/J2) — "Date-format tokens"
# section's bare-line and marked-line halves.
START_OF_LINE_BARE_DOC_SENTENCE = (
    "so the date must be the line's **entire content** (aside from trailing "
    "whitespace): `21 Jul 26` and `July 4, 26` are recognized; "
    "`Dec 25, 10 alerts fired.` is not"
)
START_OF_LINE_MARKED_DOC_SENTENCE = (
    "anything may follow it: `# 21 Jul 26 - checkout: latency`, "
    "`# 21 Jul 26 (checkout)`, `# 21 Jul 26 [P1]`, and `**21 Jul 26**` are all "
    "recognized."
)


def test_format_md_states_the_start_of_line_rule_both_halves():
    assert START_OF_LINE_BARE_DOC_SENTENCE in FORMAT_MD_NORMALIZED, (
        "expected references/format.md to state the bare-line half of the "
        "start-of-line rule verbatim — %r not found" % START_OF_LINE_BARE_DOC_SENTENCE
    )
    assert START_OF_LINE_MARKED_DOC_SENTENCE in FORMAT_MD_NORMALIZED, (
        "expected references/format.md to state the marked-line half of the "
        "start-of-line rule verbatim — %r not found" % START_OF_LINE_MARKED_DOC_SENTENCE
    )


def test_start_of_line_rule_worked_examples_match_the_encoding():
    # Bare-line half: the date must be the line's entire content.
    assert _date_format_for_line("21 Jul 26") == {"pattern": "DD Mon YY", "ambiguous": False}
    assert _date_format_for_line("July 4, 26") == {"pattern": "Month D, YY", "ambiguous": False}
    assert _date_format_for_line("Dec 25, 10 alerts fired.") is None, (
        "the doc's own bare-line counter-example must still carry no recognized "
        "date — its date leads the line but text follows it"
    )
    # Marked-line half: anything may follow the date once a heading marker leads.
    for line in (
        "# 21 Jul 26 - checkout: latency",
        "# 21 Jul 26 (checkout)",
        "# 21 Jul 26 [P1]",
        "**21 Jul 26**",
    ):
        assert _date_format_for_line(line) == {"pattern": "DD Mon YY", "ambiguous": False}, (
            "%r is one of the doc's own marked-line worked examples and must "
            "parse regardless of what trails the date" % line
        )


# (iv) The conflict clause — "Numeric date ambiguity" section's pass-level
# resolution: two-plus unambiguous entries voting different orders resolve
# nothing, and date_ambiguous still surfaces.
CONFLICT_CLAUSE_DOC_SENTENCE = (
    "the conflict resolves nothing: the flags stand exactly as if no entry had "
    "resolved it, and `date_ambiguous` still surfaces."
)


def test_format_md_states_the_conflict_clause():
    assert CONFLICT_CLAUSE_DOC_SENTENCE in FORMAT_MD_NORMALIZED, (
        "expected references/format.md's Numeric date ambiguity section to "
        "state the conflicting-votes clause verbatim — %r not found"
        % CONFLICT_CLAUSE_DOC_SENTENCE
    )


def test_conflict_clause_worked_example_matches_the_encoding():
    # "one clearly day-first, another clearly month-first" (the doc's own
    # framing) — resolve_date_ambiguity must leave every structure UNCHANGED
    # rather than adopt either voted order.
    day_first = {
        "title": None, "sections": [], "field_order": [],
        "date_format": {"pattern": "DD/MM/YYYY", "ambiguous": False},
    }
    month_first = {
        "title": None, "sections": [], "field_order": [],
        "date_format": {"pattern": "MM/DD/YYYY", "ambiguous": False},
    }
    genuinely_ambiguous = {
        "title": None, "sections": [], "field_order": [],
        "date_format": {"pattern": "MM/DD/YYYY", "ambiguous": True},
    }
    structures = [day_first, month_first, genuinely_ambiguous]
    assert resolve_date_ambiguity(structures) == structures, (
        "conflicting unambiguous votes must leave every structure's flags "
        "exactly as if no entry had resolved the ambiguity, per the doc's "
        "conflict clause"
    )

    # And the notice half: date_ambiguous still surfaces end to end.
    entries = [
        {
            "link": "diary-j4-conflict-newest",
            "content": "# 17/06/2026 — checkout: incident\n\n## What happened\nBody.\n",
            "at": "2026-06-17T00:00:00Z",
        },
        {
            "link": "diary-j4-conflict-middle",
            "content": "# 06/17/2026 — checkout: incident\n\n## What happened\nBody.\n",
            "at": "2026-06-16T00:00:00Z",
        },
        {
            "link": "diary-j4-conflict-oldest",
            "content": "# 03/04/2026 — checkout: incident\n\n## What happened\nBody.\n",
            "at": "2026-06-15T00:00:00Z",
        },
    ]
    resolution = resolve_format(None, entries)
    assert "date_ambiguous" in set(notice["kind"] for notice in resolution["notices"]), (
        "date_ambiguous must still surface when the pass's unambiguous entries "
        "disagree on order, per the doc's conflict clause"
    )


# ---------------------------------------------------------------------------
# T024 — packaging ratchet (FR-008) and boundary prose gates.
# ---------------------------------------------------------------------------

INTENDED_BUNDLE_PATH = REPO_ROOT / "tests" / "fixtures" / "packaging" / "intended-bundle.json"
DIARY_REFERENCE_RELPATH = "tests/helpers/diary_reference.py"


def test_diary_skill_ships_no_python():
    stray = sorted(p.relative_to(REPO_ROOT).as_posix() for p in SKILLS_DIR.rglob("*.py"))
    assert not stray, (
        "FR-008: skills/diary/ ships prose only — no diary-adapter code. "
        "Found Python source(s): %r" % stray
    )


def test_diary_reference_encoding_is_named_by_no_bundle_glob():
    with open(str(INTENDED_BUNDLE_PATH), encoding="utf-8") as handle:
        bundle = json.load(handle)["bundle"]

    assert bundle, "intended-bundle.json declares an empty bundle"

    matching = sorted(glob for glob in bundle if fnmatch.fnmatch(DIARY_REFERENCE_RELPATH, glob))
    assert not matching, (
        "FR-008: the reference encoding is dev-only tooling and must never "
        "be named for shipping; bundle glob(s) %r match %s"
        % (matching, DIARY_REFERENCE_RELPATH)
    )


# FR-004 prose gate.
FR004_PHRASES = ("append-only", "no diary creation", "no alternate destination")


def test_fr004_write_flow_states_append_only_no_creation_no_alternate_destination():
    for phrase in FR004_PHRASES:
        assert phrase in SKILL_MD_NORMALIZED, "FR-004: SKILL.md's Write flow must state %r" % phrase
    assert DEFERRED_ADAPTERS_SENTENCE in SKILL_MD_TEXT, (
        "FR-004: SKILL.md must name Confluence, Notion, and git-markdown as "
        "explicitly deferred adapters"
    )


# FR-005 prose gate.
#
# G9 (round 2): "Resolution" was missing from this tuple — the fifth of
# five documented drafting inputs (SKILL.md's Drafting handoff), and
# precisely the input close.md's current draft anatomy does not
# corroborate (see G4's fix to that same section). Its absence here meant
# a regression that dropped the Resolution bullet from SKILL.md would have
# gone undetected by this gate.
#
# H2 (round 3): G9's own fix was vacuous. The bare word "Resolution" also
# occurs in this same section's intro paragraph — "it does not yet name
# Resolution or the locally staged artifact content as fields it fills" —
# so deleting the "**Resolution** — factual" bullet entirely still left a
# "Resolution" substring in SKILL_MD_NORMALIZED and the gate kept passing.
# The phrase below is anchored to the bullet's own bold-lead-in text
# ("**Resolution** — factual"), which appears nowhere else in the
# document, so it goes missing if and only if the bullet itself does.
FR005_INPUT_PHRASES = (
    "In-session evidence links",
    "Services and severity",
    "**Resolution** — factual",
    "Labeled causal proposals",
    "Locally staged artifact content",
)


def test_fr005_drafting_handoff_states_the_input_contract():
    for phrase in FR005_INPUT_PHRASES:
        assert phrase in SKILL_MD_NORMALIZED, (
            "FR-005: SKILL.md's drafting handoff must state the input %r" % phrase
        )


def test_fr005_drafting_handoff_excludes_the_close_time_row_update():
    assert "Not an input: the close-time row update" in SKILL_MD_NORMALIZED, (
        "FR-005: SKILL.md must state that the close-time row update is not "
        "among the drafting handoff's inputs"
    )


# Non-goals gate: names ownership rather than restating it.
NON_GOALS_SECTION = _markdown_section("Non-goals", SKILL_MD_TEXT, SKILL_MD_PATH)
NON_GOALS_NORMALIZED = _normalize_whitespace(NON_GOALS_SECTION)


def test_non_goals_names_close_flow_ownership_of_retry_and_approval():
    assert "retry" in NON_GOALS_NORMALIZED.lower(), (
        "SKILL.md's Non-goals must name retry as the close flow's, not "
        "this skill's"
    )
    assert "approv" in NON_GOALS_NORMALIZED.lower(), (
        "SKILL.md's Non-goals must name draft approval as the close flow's"
    )
    assert "close flow" in NON_GOALS_NORMALIZED, (
        "SKILL.md's Non-goals must attribute retry and approval to the "
        "close flow by name"
    )


def test_non_goals_names_session_store_ownership_of_diary_fields():
    for token in ("diary_url", "diary_pending"):
        assert token in NON_GOALS_SECTION, (
            "SKILL.md's Non-goals must name %r as skills/session-store/'s" % token
        )
    assert "session-store" in NON_GOALS_SECTION, (
        "SKILL.md's Non-goals must attribute diary_url/diary_pending "
        "ownership to skills/session-store/ by name"
    )


def test_non_goals_states_the_approval_boundary_this_slice_must_not_weaken():
    assert "no write of any kind" in NON_GOALS_NORMALIZED, (
        "SKILL.md's Non-goals must state the approval boundary: no write "
        "of any kind happens before the responder approves the draft"
    )
    assert "before the responder approves the draft" in NON_GOALS_NORMALIZED, (
        "SKILL.md's Non-goals must state that no write happens before the "
        "responder approves the draft"
    )


# FR-008 — no surviving Phase-1 placeholder task markers anywhere under
# skills/diary/. The Phase-1 skeleton (T001) shipped "<!-- T0NN ... -->"
# comments naming the tasks that would fill each section; a shipped plugin
# surface must not carry them once those tasks are done.


def test_no_task_marker_placeholder_comments_remain_under_skills_diary():
    hits = []
    for path in sorted(SKILLS_DIR.rglob("*")):
        if path.is_file() and "<!-- T0" in path.read_text(encoding="utf-8"):
            hits.append(path.relative_to(SKILLS_DIR).as_posix())
    assert not hits, (
        "FR-008: skills/diary/ must ship with no Phase-1 placeholder task "
        "markers remaining — found '<!-- T0' in: %r" % hits
    )
