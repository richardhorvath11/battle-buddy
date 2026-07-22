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
"""

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
    # T001: widened to the full set once T009 lands — see tasks.md
    assert {"SKILL.md", "references/annotations.md"} <= set(MD_IDS)
