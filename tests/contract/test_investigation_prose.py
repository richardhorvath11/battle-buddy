"""SC-005 / FR-001..FR-005 / research R12: doc-structure gates for the
``investigation`` skill's normative prose.

Ties `skills/investigation/**/*.md` (and, once it exists, `agents/*.md`) to
the same naming discipline slice-3/4 proved (``mcp__`` hard fail; a deny-list
of concrete MCP server/product names) and adds the structural gates FR-001,
FR-002, FR-003, FR-004, and FR-005 pin: discipline-first section ordering,
the anchoring guard's phase/enforcement anchors, the evidence-rule anchor,
the one-skill-loaded-by-all anchor, the untrusted-telemetry anchors, the
briefing causal-proposal anchor, and the retrieval pointer's honesty anchors.

This is the *initial* module (T009). Later tasks in this slice extend it in
place rather than restructure it (tasks.md's serialization note: T009 ->
T012 -> T014 -> T018 -> T021 -> T022): T012 adds the triage pinned-property
gates, T014 the deep-investigator checkpoint/seeding/ledger-only gates, T018
the specialist single-purpose/findings gates, T021 the launch-condition and
role-registration gates, and T022 finalizes the SC-005 non-vanishing guard
over the full nine-file set once `agents/*.md` exists. The `_section` helper
below is shared by every section-scoped gate those tasks add.
"""

import re

import pytest

from conftest import REPO_ROOT
from test_command_capability_naming import DENY_PATTERNS
from test_skill_capability_naming import FENCE_RE

INVESTIGATION_SKILL_DIR = REPO_ROOT / "skills" / "investigation"
AGENTS_DIR = REPO_ROOT / "agents"
SKILL_DOC = INVESTIGATION_SKILL_DIR / "SKILL.md"
BRIEFING_DOC = INVESTIGATION_SKILL_DIR / "references" / "briefing.md"
RETRIEVAL_DOC = INVESTIGATION_SKILL_DIR / "references" / "retrieval.md"

# SC-005 scan set: every `.md` under skills/investigation/ (rglob — a future
# reference file is covered automatically, no list to maintain) plus every
# `.md` directly under agents/. `agents/` does not exist yet (T010/T013/
# T015-17 create it); `Path.glob` on a missing directory yields no matches
# rather than raising, so this tolerates that today. T022 adds the
# non-vanishing guard over the finalized nine-file set once it does.
SCAN_TARGETS = sorted(INVESTIGATION_SKILL_DIR.rglob("*.md")) + sorted(
    AGENTS_DIR.glob("*.md")
)
SCAN_IDS = [p.relative_to(REPO_ROOT).as_posix() for p in SCAN_TARGETS]

_WS_RE = re.compile(r"\s+")
_HEADING_RE = re.compile(r"^## (.+)$", re.MULTILINE)


def _strip_fenced_blocks(text):
    """Restated one-line wrapper (slice-3/4 precedent): ``FENCE_RE`` is the
    public constant imported above; the stripper itself stays private per
    module rather than imported across (the home module's version is
    underscore-prefixed).
    """
    return FENCE_RE.sub("", text)


def _normalize_ws(text):
    """Collapse whitespace runs to a single space so a hand-wrapped markdown
    line break inside a normative token (e.g. SKILL.md's evidence rule wraps
    ``{url,`` / ``excerpt}`` across a line) never defeats a literal substring
    check.
    """
    return _WS_RE.sub(" ", text)


def _section(text, heading):
    """Body of the ``## <heading>`` section: every line between that heading
    and the next ``## `` heading (or end of document). Returns ``None`` when
    the heading is absent. Shared by every section-scoped gate in this
    module — later tasks (T012/T014/T018/T021) reuse it for their own
    sections.
    """
    lines = text.splitlines()
    target = "## %s" % heading
    start = None
    for i, line in enumerate(lines):
        if line.strip() == target:
            start = i + 1
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return "\n".join(lines[start:end])


SKILL_TEXT = SKILL_DOC.read_text(encoding="utf-8")
BRIEFING_TEXT = BRIEFING_DOC.read_text(encoding="utf-8")
RETRIEVAL_TEXT = RETRIEVAL_DOC.read_text(encoding="utf-8")

SKILL_HEADINGS = _HEADING_RE.findall(SKILL_TEXT)
OVERVIEW_SECTION = _section(SKILL_TEXT, "Overview")
ANCHORING_GUARD_SECTION = _section(SKILL_TEXT, "Anchoring guard")
EVIDENCE_RULES_SECTION = _section(SKILL_TEXT, "Evidence rules")
UNTRUSTED_TELEMETRY_SECTION = _section(SKILL_TEXT, "Untrusted telemetry")


# ---------------------------------------------------------------------------
# Non-vanishing guards (TA5-style precedent, per test_skill_capability_naming
# / test_command_capability_naming / test_schemas_reference): a broken glob,
# a renamed heading, or an emptied file set must not turn every check below
# into a silently-skipped no-op. This module's file-set guard is *initial* —
# T022 finalizes it over the full nine-file set once agents/ exists.
# ---------------------------------------------------------------------------


def test_scan_finds_the_known_investigation_docs():
    names = {
        p.relative_to(INVESTIGATION_SKILL_DIR).as_posix()
        for p in SCAN_TARGETS
        if INVESTIGATION_SKILL_DIR in p.parents
    }
    assert {
        "SKILL.md",
        "references/schemas.md",
        "references/briefing.md",
        "references/retrieval.md",
    } <= names


def test_skill_doc_sections_were_parsed():
    assert SKILL_HEADINGS, "no `## ` headings parsed out of SKILL.md"


def test_all_scoped_sections_were_found():
    for name, section in (
        ("Overview", OVERVIEW_SECTION),
        ("Anchoring guard", ANCHORING_GUARD_SECTION),
        ("Evidence rules", EVIDENCE_RULES_SECTION),
        ("Untrusted telemetry", UNTRUSTED_TELEMETRY_SECTION),
    ):
        assert section is not None, "SKILL.md has no `## %s` section" % name


# ---------------------------------------------------------------------------
# 1. SC-005 naming scan: mcp__ raw hard-fail on every scanned file (fenced or
#    not) + the merged deny-list on fence-stripped text.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("doc_path", SCAN_TARGETS, ids=SCAN_IDS)
def test_no_concrete_mcp_tool_name_marker(doc_path):
    text = doc_path.read_text(encoding="utf-8")
    assert "mcp__" not in text, (
        "%s references a concrete MCP tool name (mcp__ marker) — SC-005/"
        "Constitution VII requires capability/operation names only, never a "
        "hardcoded MCP tool name" % doc_path
    )


@pytest.mark.parametrize("doc_path", SCAN_TARGETS, ids=SCAN_IDS)
def test_no_concrete_server_product_name_outside_fences(doc_path):
    text = doc_path.read_text(encoding="utf-8")
    prose = _strip_fenced_blocks(text)
    hits = sorted(
        name for name, pattern in DENY_PATTERNS.items() if pattern.search(prose)
    )
    assert not hits, (
        "%s names a concrete MCP server/product in normative prose: %r — "
        "SC-005/FR-010 permits only capability/operation names" % (doc_path, hits)
    )


# ---------------------------------------------------------------------------
# 2. Discipline-first ordering gate (US1-AS1, FR-001, research R12(a)): the
#    first `## ` section after both structural sections (Overview,
#    References) is Validation discipline. References sits between the two
#    — the gate must skip both, not just Overview.
# ---------------------------------------------------------------------------


def test_validation_discipline_is_first_section_after_overview_and_references():
    structural = {"Overview", "References"}
    first_non_structural = next(
        (heading for heading in SKILL_HEADINGS if heading not in structural), None
    )
    assert first_non_structural == "Validation discipline", (
        "expected 'Validation discipline' as the first non-structural `## ` "
        "section (after Overview and References) — got %r from heading "
        "sequence %r" % (first_non_structural, SKILL_HEADINGS)
    )


# ---------------------------------------------------------------------------
# 3. Anchoring-guard section gates (FR-002, research R12(b)): both invariant
#    phases, both early phases, and the enforcement attribution, all within
#    the section's own text.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("phase", ["evidence-gathering", "deep-dive"])
def test_anchoring_guard_names_invariant_phase(phase):
    assert phase in ANCHORING_GUARD_SECTION, (
        "SKILL.md's Anchoring guard section does not name invariant phase "
        "%r" % phase
    )


@pytest.mark.parametrize("phase", ["triage-seeded", "hypothesis-generation"])
def test_anchoring_guard_names_early_phase(phase):
    assert phase in ANCHORING_GUARD_SECTION, (
        "SKILL.md's Anchoring guard section does not name early phase %r"
        % phase
    )


def test_anchoring_guard_attributes_enforcement():
    lowered = ANCHORING_GUARD_SECTION.lower()
    assert "bb-validate" in ANCHORING_GUARD_SECTION or "validator" in lowered, (
        "SKILL.md's Anchoring guard section does not attribute enforcement "
        "to bb-validate/the validator"
    )
    assert "checkpoint write" in lowered, (
        "SKILL.md's Anchoring guard section does not attribute enforcement "
        "to checkpoint-write time"
    )


# ---------------------------------------------------------------------------
# 4. Evidence-rule anchor (FR-003): the {url, excerpt} shape and a
#    prose-only-is-invalid statement, within the Evidence rules section.
# ---------------------------------------------------------------------------


def test_evidence_rules_names_url_excerpt_pair():
    assert "{url, excerpt}" in _normalize_ws(EVIDENCE_RULES_SECTION), (
        "SKILL.md's Evidence rules section does not name the {url, excerpt} "
        "evidence shape"
    )


def test_evidence_rules_states_prose_only_is_invalid():
    lowered = EVIDENCE_RULES_SECTION.lower()
    assert "prose" in lowered and "invalid" in lowered, (
        "SKILL.md's Evidence rules section does not state that prose-only "
        "evidence is invalid"
    )


# ---------------------------------------------------------------------------
# 5. One-skill-loaded-by-all anchor (FR-001's loading clause, research R12):
#    the Overview names the orchestrator and both investigation agents.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("token", ["orchestrator", "triage", "deep"])
def test_overview_names_orchestrator_and_both_investigation_agents(token):
    assert token in OVERVIEW_SECTION.lower(), (
        "SKILL.md's Overview section does not mention %r — FR-001 pins one "
        "skill loaded by the orchestrator and both investigation agents"
        % token
    )


# ---------------------------------------------------------------------------
# 6. Untrusted-telemetry gates (FR-004, research R10): both v1 untrusted
#    capabilities, the delimiter token, and the probabilistic-mitigation
#    framing whose guarantee lives in the deterministic layers.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("capability", ["alerting", "observability"])
def test_untrusted_telemetry_names_v1_capability(capability):
    assert capability in UNTRUSTED_TELEMETRY_SECTION, (
        "SKILL.md's Untrusted telemetry section does not name v1 untrusted "
        "capability %r" % capability
    )


def test_untrusted_telemetry_names_the_delimiter():
    assert "<untrusted-telemetry>" in UNTRUSTED_TELEMETRY_SECTION, (
        "SKILL.md's Untrusted telemetry section does not name the "
        "<untrusted-telemetry> delimiter"
    )


def test_untrusted_telemetry_states_probabilistic_framing():
    lowered = UNTRUSTED_TELEMETRY_SECTION.lower()
    assert "probabilistic" in lowered, (
        "SKILL.md's Untrusted telemetry section does not frame the rule as "
        "probabilistic mitigation"
    )
    assert "guarantee" in lowered, (
        "SKILL.md's Untrusted telemetry section does not state that the "
        "guarantee lives in the deterministic layers"
    )


# ---------------------------------------------------------------------------
# 7. Briefing causal anchor (FR-005): the proposal-labeling discipline and
#    the {url, excerpt} per-claim property.
# ---------------------------------------------------------------------------


def test_briefing_states_proposal_labeling_discipline():
    lowered = BRIEFING_TEXT.lower()
    assert "proposal" in lowered, (
        "briefing.md does not name the proposal-labeling discipline"
    )
    assert "root cause" in lowered, (
        "briefing.md does not name 'root cause' as part of the "
        "proposal-labeling discipline"
    )


def test_briefing_names_url_excerpt_pair():
    assert "{url, excerpt}" in _normalize_ws(BRIEFING_TEXT), (
        "briefing.md does not name the {url, excerpt} per-claim evidence "
        "property"
    )


# ---------------------------------------------------------------------------
# 8. Retrieval pointer honesty (FR-005): names the session-store home and
#    states the recall provenance.
# ---------------------------------------------------------------------------


def test_retrieval_pointer_names_session_store_home():
    assert "session-store/references/retrieval.md" in RETRIEVAL_TEXT, (
        "retrieval.md does not point at "
        "skills/session-store/references/retrieval.md as its normative home"
    )


def test_retrieval_pointer_states_recall_provenance():
    assert "recall" in RETRIEVAL_TEXT.lower(), (
        "retrieval.md does not state the recall-provenance statement for "
        "candidate rows"
    )
