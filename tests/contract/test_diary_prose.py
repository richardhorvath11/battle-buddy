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

  **The deferral-list mask is NOT built here.** The merged set bans
  ``confluence`` and ``notion``, and FR-004 *requires* ``SKILL.md`` to name
  them — alongside git-markdown — as explicitly deferred adapters. T013
  (US2) lands that sentence and its mask together, in the same task: a mask
  with nothing yet to mask is the vacuous gate this repo's own precedent
  warns about.

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
    # Full target set is {"SKILL.md", "references/format.md"} — but
    # references/format.md does not exist until T008 (US1) writes it. T008
    # is the task that widens this assertion to the full target set; until
    # then only SKILL.md's presence is asserted.
    assert {"SKILL.md"} <= set(MD_IDS)


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


@pytest.mark.parametrize("doc_path", MD_FILES, ids=MD_IDS)
def test_no_concrete_server_product_name_outside_fences(doc_path):
    text = doc_path.read_text(encoding="utf-8")
    prose = _strip_fenced_blocks(text)
    hits = sorted(name for name, pattern in DENY_PATTERNS.items() if pattern.search(prose))
    assert not hits, (
        "%s names a concrete MCP server/product in normative prose: %r — "
        "SC-006 permits only capability/operation names, never a vendor or "
        "product name (Constitution VII)" % (doc_path, hits)
    )
