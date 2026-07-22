"""Prose gate for skills/catalog/ (FR-002/FR-003/FR-004/FR-005/FR-007/FR-009;
SC-005/SC-006).

This module is the prose-gate for the catalog skill: every hermetic assertion
``skills/catalog/**/*.md`` must satisfy lives here, discovered dynamically
(``rglob`` over the skill directory, never a hand-maintained file list).

T001 (Phase 1: Setup) creates this module as an empty skeleton with a single
non-vanishing guard — setup, not any user story, owns this file's *existence*,
so a scope cut dropping US3 or US4 (see tasks.md's "If scope must be cut")
can never orphan a later task that would otherwise have nowhere to land.
Later tasks extend this same module in place, never replace it:

- T016 (US4): the SC-006 storage-op scan — zero occurrences of the write ops
  (``append_record``, ``update_record``, ``put_file``, ``append_entry``)
  anywhere under ``skills/catalog/**/*.md`` — plus the freshness/runbook-format
  prose gates.
- T018 (Phase 6): the SC-005 naming scan (the ``mcp__`` hard fail, the
  deny-list scan extended locally with a ``github`` pattern, canonical-key
  masking) and the FR-007 gates (the literal "your code tool's file reads"
  phrase, the enumerated code-operation-token deny list, the manifest-fidelity
  backstop scoped to that token set).
- T019 (Phase 6): the prose<->encoding agreement test — the annotation table
  in ``references/annotations.md`` against
  ``tests/helpers/catalog_reference.py``'s ``CANONICAL_ANNOTATIONS`` /
  ``LINKAGE_ANNOTATIONS`` vocabularies, asserted both ways.
- T020 (Phase 6): the doctor-fixture ratchet — slice 4's
  ``tests/fixtures/doctor/catalog-valid.json`` annotation keys are asserted a
  (non-vacuous) subset of the canonical vocabulary.
- T022 (Phase 6): the FR-009 assertion that ``skills/catalog/`` ships no
  ``*.py`` file and that ``tests/helpers/catalog_reference.py`` is named by no
  glob in ``tests/fixtures/packaging/intended-bundle.json``'s shipped bundle.

T016 scope notes, recorded here rather than only in code comments because both
are deliberate choices a future author could otherwise mistake for bugs:

(a) ``read_records`` is deliberately **not** scanned by the SC-006 write-op
    scan below. Reading the session store back is not a catalog *write* —
    spec SC-006 names only the four write operations
    (``append_record``, ``update_record``, ``put_file``, ``append_entry``) —
    and a doc that legitimately cites where a runbook pointer is read back
    from must not be failed by a gate scoped to writes.

(b) The SC-006 scan below is **unconditional** — every ``*.md`` file, no
    exemption — where the spec text says "applied to catalog content." That
    is a deliberate widening. Scoping the scan to "the catalog-flow sections"
    would need a section boundary the prose does not carry, and any such
    boundary is gameable by moving a sentence past it. The accepted cost: the
    prose must state the never-copied rule without ever naming a write
    operation, which is exactly what ``SKILL.md``'s freshness section does
    ("never cached across sessions and never copied into any store").
"""

import re

import pytest

from conftest import REPO_ROOT

SKILLS_DIR = REPO_ROOT / "skills" / "catalog"

MD_FILES = sorted(SKILLS_DIR.rglob("*.md"))
MD_IDS = [p.relative_to(SKILLS_DIR).as_posix() for p in MD_FILES]


# ---------------------------------------------------------------------------
# Non-vanishing guard (TA5-style, per test_skill_capability_naming.py's
# precedent): a broken glob or an emptied doc set must not turn every
# parametrized check the later tasks add into a silently-skipped, still-green
# no-op.
# ---------------------------------------------------------------------------


def test_scan_finds_the_known_catalog_docs():
    # T009: guard is now at its full target set — no remaining widener
    assert {"SKILL.md", "references/annotations.md", "references/resolution.md"} <= set(MD_IDS)


def test_md_files_has_at_least_the_skill_and_two_references():
    # T016 non-vanishing guard: a broken glob must fail loudly here rather
    # than turning every parametrized scan below into a vacuous pass over
    # zero files.
    assert len(MD_FILES) >= 3, (
        "expected skills/catalog/**/*.md to discover SKILL.md plus at least "
        "two references/*.md docs; got %r" % MD_IDS
    )


# ---------------------------------------------------------------------------
# Combined prose text, built from the guarded MD_FILES above (never a fresh,
# independent rglob) — every content gate below scans this, or the SKILL.md
# slice of it named below, so a doc added to the skill is automatically in
# scope and a doc dropped from the glob is automatically out.
#
# Normalization exists because this repo's prose hard-wraps at a fixed column:
# a phrase like "never copied into any store" can straddle a line break in the
# raw file (a newline where an editor wrapped, not a boundary the phrase's
# meaning cares about).
#
# It is done PER PARAGRAPH, not by collapsing the whole corpus. A global
# `re.sub(r"\s+", " ", ...)` also erases blank lines and the inter-file join,
# so a phrase could be satisfied by words reassembled across a paragraph break
# — or across two different files — while neither doc actually says it. A
# review demonstrated both. Splitting on blank lines first keeps the
# wrap-robustness and closes the boundary-crossing vector: a phrase must live
# inside one paragraph of one file.
# ---------------------------------------------------------------------------


def _paragraphs(text):
    """Whitespace-normalized paragraphs — wrap-robust, boundary-respecting."""
    return [
        re.sub(r"\s+", " ", block).strip()
        for block in re.split(r"\n\s*\n", text)
        if block.strip()
    ]


def _states(phrase, paragraphs):
    """True when some single paragraph contains the phrase verbatim."""
    return any(phrase in paragraph for paragraph in paragraphs)


ALL_CATALOG_TEXT = "\n".join(p.read_text(encoding="utf-8") for p in MD_FILES)
ALL_CATALOG_PARAGRAPHS = [
    paragraph
    for doc in MD_FILES
    for paragraph in _paragraphs(doc.read_text(encoding="utf-8"))
]

SKILL_MD_TEXT = next(p.read_text(encoding="utf-8") for p in MD_FILES if p.name == "SKILL.md")
SKILL_MD_PARAGRAPHS = _paragraphs(SKILL_MD_TEXT)


def test_combined_catalog_prose_is_non_trivial():
    # T016 non-vanishing guard: an emptied doc set must not let the "X in
    # text" content gates below pass trivially by having nothing left to
    # contradict them.
    assert len(ALL_CATALOG_TEXT) > 2000, (
        "combined text of skills/catalog/**/*.md is only %d chars — too "
        "small to trust the content-presence gates below"
        % len(ALL_CATALOG_TEXT)
    )


# ---------------------------------------------------------------------------
# SC-006 — zero occurrences of the four storage/artifact/diary write
# operations anywhere under skills/catalog/**/*.md. Raw text, no
# fence-stripping exemption (unlike FR-010's deny-list scan in
# test_skill_capability_naming.py): a catalog doc has no legitimate reason to
# name a write op, worked example or not, so there is nothing to exempt.
# ---------------------------------------------------------------------------

WRITE_OPS = ("append_record", "update_record", "put_file", "append_entry")


@pytest.mark.parametrize("doc_path", MD_FILES, ids=MD_IDS)
def test_no_storage_write_operation_named(doc_path):
    text = doc_path.read_text(encoding="utf-8")
    # Case-insensitive: `Append_Record` is the same operation name, and a
    # scan that only catches the lowercase spelling is a scan with a
    # trivially-typed hole in it.
    lowered = text.lower()
    hits = sorted(op for op in WRITE_OPS if op in lowered)
    assert not hits, (
        "%s names storage/artifact/diary write operation(s) %r — SC-006 "
        "requires catalog content is never written to a store, and naming a "
        "write op in catalog prose is exactly the shape that rules out "
        "(read_records is deliberately exempt — see module docstring)"
        % (doc_path, hits)
    )


# ---------------------------------------------------------------------------
# US4 content gates (FR-005) — assert the prose actually *says* the things
# FR-005 requires, not just that it avoids naming a write op.
# ---------------------------------------------------------------------------


def test_freshness_statement_present():
    # Scanned against SKILL.md, not the whole corpus: US4's independent test
    # inspects *the skill's* documented flow, and T015 places the freshness
    # rule in SKILL.md specifically. A corpus-wide scan would stay green if
    # the statement were moved out of SKILL.md into a reference doc, which is
    # exactly the regression this gate exists to catch.
    assert _states("fresh at session start", SKILL_MD_PARAGRAPHS), (
        "FR-005: SKILL.md must state catalog data is read fresh at session "
        "start — literal phrase 'fresh at session start' not found in any "
        "single paragraph of SKILL.md"
    )
    assert _states("never cached across sessions", SKILL_MD_PARAGRAPHS), (
        "FR-005: SKILL.md must state catalog data is never cached across "
        "sessions — literal phrase not found in any single paragraph"
    )
    assert _states("never copied into any store", SKILL_MD_PARAGRAPHS), (
        "FR-005: SKILL.md must state catalog data is never copied into any "
        "store — literal phrase not found in any single paragraph"
    )


# Anchored to the literal clause in SKILL.md's "Runbook references are
# pointers, never content" section: "Runbook **content** - what the runbook
# actually says - is never persisted anywhere; only the pointer is."
#
# The clause, not a loose "never ... persist" regex. A review showed the loose
# form is satisfiable by an unrelated decoy sentence elsewhere in the doc while
# the real sentence is inverted to say content IS persisted — the gate would
# stay green on prose that states the opposite of FR-005.
NEVER_CONTENT_CLAUSE = "is never persisted anywhere; only the pointer is"


def test_runbook_pointer_format_stated_in_skill_md():
    assert "runbook_refs" in SKILL_MD_TEXT, (
        "FR-005: SKILL.md must name runbook_refs as the runbook-pointer "
        "destination — literal 'runbook_refs' not found in SKILL.md"
    )
    assert "commit SHA" in SKILL_MD_TEXT, (
        "FR-005: SKILL.md must mention the commit SHA a runbook pointer is "
        "read at — literal 'commit SHA' not found in SKILL.md"
    )
    assert _states(NEVER_CONTENT_CLAUSE, SKILL_MD_PARAGRAPHS), (
        "FR-005: SKILL.md must state that runbook content itself is never "
        "persisted, only the pointer — the clause %r was not found in any "
        "single paragraph of SKILL.md" % NEVER_CONTENT_CLAUSE
    )


def test_catalog_unreachable_path_named_in_skill_md():
    assert "catalog repo unreachable" in SKILL_MD_TEXT, (
        "FR-005: SKILL.md must name the catalog-repo-unreachable path "
        "literally — phrase 'catalog repo unreachable' not found in "
        "SKILL.md"
    )


UNREACHABLE_CLAIMS = [
    ("never blocks the session opening", "nothing blocks the session open"),
    ("lower rungs carry the session", "the fingerprint ladder carries the session"),
    ("surfaced in the briefing", "the gap is surfaced in the briefing"),
]
UNREACHABLE_IDS = [claim for claim, _ in UNREACHABLE_CLAIMS]


@pytest.mark.parametrize("phrase, rule", UNREACHABLE_CLAIMS, ids=UNREACHABLE_IDS)
def test_catalog_unreachable_path_states_its_three_claims(phrase, rule):
    # The name check above is satisfied by the heading alone: a review gutted
    # the subsection's entire body and the suite stayed green. spec.md's
    # catalog-unreachable edge case makes three claims, and each gets an
    # assertion here so the section cannot decay into a heading.
    assert _states(phrase, SKILL_MD_PARAGRAPHS), (
        "FR-005 / spec.md's catalog-unreachable edge case: SKILL.md must "
        "state that %s — expected phrase %r in some paragraph" % (rule, phrase)
    )
