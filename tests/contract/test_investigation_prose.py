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


# ---------------------------------------------------------------------------
# US2 / T012 — triage agent definition pinned-property gates (FR-006,
# US2-AS1/AS3/AS4). `agents/triage.md` now exists (T010), so the SC-005 scan
# above (sections 1) already covers it automatically via `SCAN_TARGETS`'
# `AGENTS_DIR.glob("*.md")` half — no change needed there. This section adds
# the triage-specific structural gates: the Budget section's turn-cap +
# enforcement-attribution + target-vs-enforced distinction, the four fixed
# questions, the truncation-satisfies-FR-5f(a) statement, and the
# re-invocation charter. Per tasks.md's serialization note this module's
# next extension is T014 (deep-investigator).
# ---------------------------------------------------------------------------

TRIAGE_DOC = AGENTS_DIR / "triage.md"
TRIAGE_TEXT = TRIAGE_DOC.read_text(encoding="utf-8")

TRIAGE_BUDGET_SECTION = _section(TRIAGE_TEXT, "Budget")
TRIAGE_QUESTIONS_SECTION = _section(TRIAGE_TEXT, "The four questions")
TRIAGE_OUTPUT_CONTRACT_SECTION = _section(TRIAGE_TEXT, "Output contract")
TRIAGE_REINVOCATION_SECTION = _section(TRIAGE_TEXT, "Re-invocation")


def test_all_triage_scoped_sections_were_found():
    for name, section in (
        ("Budget", TRIAGE_BUDGET_SECTION),
        ("The four questions", TRIAGE_QUESTIONS_SECTION),
        ("Output contract", TRIAGE_OUTPUT_CONTRACT_SECTION),
        ("Re-invocation", TRIAGE_REINVOCATION_SECTION),
    ):
        assert section is not None, "agents/triage.md has no `## %s` section" % name


# --- Budget gates (US2-AS1): default 15, the config key, enforcement
# attributed to the hook/deterministic layer, and the target-vs-enforced
# distinction — never a self-enforcement claim. ---------------------------


def test_triage_budget_names_the_default_turn_cap():
    # "default 15" (not a bare "15") binds the number to its meaning, so an
    # incidental 15 elsewhere in the section can never phantom-satisfy this.
    assert "default 15" in TRIAGE_BUDGET_SECTION, (
        "agents/triage.md's Budget section does not name the default turn "
        "cap (expected the phrase 'default 15')"
    )


def test_triage_budget_names_the_config_key():
    assert "budgets.triageTurnCap" in TRIAGE_BUDGET_SECTION, (
        "agents/triage.md's Budget section does not name the "
        "`budgets.triageTurnCap` configuration key"
    )


def test_triage_budget_attributes_enforcement_to_the_hook():
    lowered = TRIAGE_BUDGET_SECTION.lower()
    assert "hook" in lowered or "deterministic" in lowered, (
        "agents/triage.md's Budget section does not attribute turn-cap "
        "enforcement to the hook/deterministic layer"
    )


def test_triage_budget_states_target_never_enforced_distinction():
    lowered = TRIAGE_BUDGET_SECTION.lower()
    assert "target" in lowered, (
        "agents/triage.md's Budget section does not name the wall-clock "
        "'target'"
    )
    assert "never enforced" in lowered or "not enforced" in lowered, (
        "agents/triage.md's Budget section does not state that the "
        "wall-clock target is never/not enforced"
    )


# --- Four-questions gate: all four fixed question anchors present. -------


@pytest.mark.parametrize(
    "anchor", ["Known?", "Real?", "What changed?", "Who's affected?"]
)
def test_triage_names_the_four_fixed_questions(anchor):
    # Scoped to the section body: the frontmatter description also lists the
    # four questions, so a whole-doc scan would keep passing with the section
    # gutted (review mutation finding).
    assert anchor in TRIAGE_QUESTIONS_SECTION, (
        "agents/triage.md's 'The four questions' section does not contain "
        "the fixed-question anchor %r" % anchor
    )


# --- Truncation gate (US2-AS3): the truncation-satisfies-FR-5f(a) statement,
# via the verdict's own fields, with no separate signal invented. ---------


def test_triage_output_contract_names_no_strong_signal_field():
    assert "no_strong_signal" in TRIAGE_OUTPUT_CONTRACT_SECTION, (
        "agents/triage.md's Output contract section does not name the "
        "`no_strong_signal` field"
    )


def test_triage_output_contract_names_budget_spent_field():
    assert "budget_spent" in TRIAGE_OUTPUT_CONTRACT_SECTION, (
        "agents/triage.md's Output contract section does not name the "
        "`budget_spent` field"
    )


def test_triage_output_contract_names_fr_5f_a():
    assert (
        "FR-5f(a)" in TRIAGE_OUTPUT_CONTRACT_SECTION
        or "5f(a)" in TRIAGE_OUTPUT_CONTRACT_SECTION
    ), (
        "agents/triage.md's Output contract section does not cite the "
        "FR-5f(a) launch condition it satisfies via its own fields"
    )


def test_triage_output_contract_states_no_separate_signal_invented():
    assert "no separate" in TRIAGE_OUTPUT_CONTRACT_SECTION.lower(), (
        "agents/triage.md's Output contract section does not state that no "
        "separate escalation signal is invented"
    )


# --- Re-invocation gate (US2-AS4): related-vs-separate classification, and
# the never-disturb-a-running-deep-investigation clause. ------------------


def test_triage_reinvocation_names_related_and_separate():
    lowered = TRIAGE_REINVOCATION_SECTION.lower()
    assert "related" in lowered, (
        "agents/triage.md's Re-invocation section does not name the "
        "'related' classification"
    )
    assert "separate" in lowered, (
        "agents/triage.md's Re-invocation section does not name the "
        "'separate' classification"
    )


def test_triage_reinvocation_never_disturbs_deep_investigation():
    assert "deep investigation" in TRIAGE_REINVOCATION_SECTION.lower(), (
        "agents/triage.md's Re-invocation section does not name the "
        "never-disturb-a-running-deep-investigation clause"
    )


# ---------------------------------------------------------------------------
# US3 / T014 — deep-investigator agent definition pinned-property gates
# (FR-007, US3-AS1/AS2/AS3). `agents/deep-investigator.md` now exists (T013),
# so the SC-005 scan above (section 1) already covers it automatically via
# `SCAN_TARGETS`'s `AGENTS_DIR.glob("*.md")` half — no change needed there.
# This section adds the deep-investigator-specific structural gates: the
# Checkpointing section's validator-gate + session-store-conventions
# anchors, the Seeding section's provenance/carried-forward-mark/
# fresh-before-deep-dive/re-validation anchors, the Ledger-ownership
# section's ledger-updates-only + raw-findings-forbidden anchors, and the
# Specialist-dispatch section's agent-teams non-normative anchor. Per
# tasks.md's serialization note this module's next extension is T018 (the
# three specialists).
# ---------------------------------------------------------------------------

DEEP_INVESTIGATOR_DOC = AGENTS_DIR / "deep-investigator.md"
DEEP_INVESTIGATOR_TEXT = DEEP_INVESTIGATOR_DOC.read_text(encoding="utf-8")

DEEP_CHECKPOINTING_SECTION = _section(DEEP_INVESTIGATOR_TEXT, "Checkpointing")
DEEP_SEEDING_SECTION = _section(DEEP_INVESTIGATOR_TEXT, "Seeding")
DEEP_LEDGER_OWNERSHIP_SECTION = _section(
    DEEP_INVESTIGATOR_TEXT, "Ledger ownership and synthesis"
)
DEEP_DISPATCH_SECTION = _section(DEEP_INVESTIGATOR_TEXT, "Specialist dispatch")


def test_all_deep_investigator_scoped_sections_were_found():
    for name, section in (
        ("Checkpointing", DEEP_CHECKPOINTING_SECTION),
        ("Seeding", DEEP_SEEDING_SECTION),
        ("Ledger ownership and synthesis", DEEP_LEDGER_OWNERSHIP_SECTION),
        ("Specialist dispatch", DEEP_DISPATCH_SECTION),
    ):
        assert section is not None, (
            "agents/deep-investigator.md has no `## %s` section" % name
        )


# --- Checkpointing gates (US3-AS1): validator gate cited (bb-validate/
# validator, re-prompt, schema_valid) + session-store conventions cited —
# never a direct unvalidated write. -----------------------------------------


def test_deep_investigator_checkpointing_cites_the_validator_gate():
    lowered = DEEP_CHECKPOINTING_SECTION.lower()
    assert "bb-validate" in DEEP_CHECKPOINTING_SECTION or "validator" in lowered, (
        "agents/deep-investigator.md's Checkpointing section does not cite "
        "bb-validate/the validator"
    )
    assert "re-prompt" in lowered, (
        "agents/deep-investigator.md's Checkpointing section does not cite "
        "the one-re-prompt-then-persist-flagged gate"
    )
    assert "schema_valid" in DEEP_CHECKPOINTING_SECTION, (
        "agents/deep-investigator.md's Checkpointing section does not name "
        "the `schema_valid` flag persisted on a second validation failure"
    )


def test_deep_investigator_checkpointing_cites_session_store_conventions():
    assert "session-store" in DEEP_CHECKPOINTING_SECTION.lower(), (
        "agents/deep-investigator.md's Checkpointing section does not cite "
        "the session-store skill's checkpoint conventions"
    )


# --- Seeding gates (US3-AS2): provenance `triage`, marks carried forward,
# ≥1-fresh-before-deep-dive, and re-validation required. --------------------


def test_deep_investigator_seeding_names_triage_provenance():
    assert "`triage`" in DEEP_SEEDING_SECTION, (
        "agents/deep-investigator.md's Seeding section does not name "
        "provenance `triage`"
    )


def test_deep_investigator_seeding_states_marks_carry_forward():
    assert "VALIDATED" in DEEP_SEEDING_SECTION, (
        "agents/deep-investigator.md's Seeding section does not name the "
        "VALIDATED/INVALIDATED mark"
    )
    lowered = DEEP_SEEDING_SECTION.lower()
    assert "carries" in lowered or "carry" in lowered, (
        "agents/deep-investigator.md's Seeding section does not state that "
        "seeding carries the mark forward"
    )


def test_deep_investigator_seeding_states_fresh_before_deep_dive():
    lowered = DEEP_SEEDING_SECTION.lower()
    assert "fresh" in lowered and "before" in lowered, (
        "agents/deep-investigator.md's Seeding section does not state the "
        "at-least-one-fresh-before-deep-dive rule"
    )


def test_deep_investigator_seeding_states_revalidation_requirement():
    assert "re-valid" in DEEP_SEEDING_SECTION.lower(), (
        "agents/deep-investigator.md's Seeding section does not state the "
        "re-validation-against-current-incident-evidence requirement"
    )


# --- Ledger-ownership gates (US3-AS3): ledger-updates-only reporting to the
# orchestrator, raw findings forbidden. --------------------------------------


def test_deep_investigator_ledger_ownership_states_updates_only_to_orchestrator():
    lowered = DEEP_LEDGER_OWNERSHIP_SECTION.lower()
    assert "ledger update" in lowered, (
        "agents/deep-investigator.md's Ledger ownership and synthesis "
        "section does not name 'ledger update(s)'"
    )
    assert "orchestrator" in lowered, (
        "agents/deep-investigator.md's Ledger ownership and synthesis "
        "section does not name the orchestrator"
    )


def test_deep_investigator_ledger_ownership_forbids_raw_findings_upward():
    lowered = DEEP_LEDGER_OWNERSHIP_SECTION.lower()
    assert "raw" in lowered, (
        "agents/deep-investigator.md's Ledger ownership and synthesis "
        "section does not name 'raw' findings"
    )
    assert "forbidden" in lowered or "never" in lowered, (
        "agents/deep-investigator.md's Ledger ownership and synthesis "
        "section does not forbid relaying raw findings upward"
    )


# --- Specialist-dispatch gate: agent-teams future mode is explicitly
# non-normative (FR-008's note lands here per tasks.md T013). --------------


def test_deep_investigator_dispatch_marks_agent_teams_non_normative():
    lowered = DEEP_DISPATCH_SECTION.lower()
    assert "agent-teams" in lowered or "agent teams" in lowered, (
        "agents/deep-investigator.md's Specialist dispatch section does not "
        "name agent-teams mode"
    )
    assert "future" in lowered, (
        "agents/deep-investigator.md's Specialist dispatch section does not "
        "mark agent-teams mode as future work"
    )
    assert "non-normative" in lowered or "no design content" in lowered, (
        "agents/deep-investigator.md's Specialist dispatch section does not "
        "mark agent-teams mode as non-normative"
    )


# ---------------------------------------------------------------------------
# US4 / T018 — specialist agent definition pinned-property gates (FR-008,
# US4-AS1/AS2). `agents/log-diver.md`, `agents/deploy-analyst.md`, and
# `agents/dependency-checker.md` now exist (T015/T016/T017), so the SC-005
# scan above (section 1) already covers all three automatically via
# `SCAN_TARGETS`'s `AGENTS_DIR.glob("*.md")` half — no change needed there.
# This section adds the three specialists' structural gates, parametrized
# over the three docs where natural: the Purpose section's single-purpose
# anchor, and the Findings contract section's deep-investigator-only anchor,
# `{url, excerpt}` evidence anchor, and empty-findings-legitimate anchor.
#
# US4-AS3 (the agent-teams note in deep-investigator.md is marked future +
# non-normative) is already covered by
# `test_deep_investigator_dispatch_marks_agent_teams_non_normative` above
# (added at T014, before any specialist doc existed) — that gate asserts
# exactly AS3's three anchors (agent-teams named, "future", "non-normative"/
# "no design content"), so there is no gap to extend here.
#
# Per tasks.md's serialization note this module's next extension is T021
# (launch conditions + role registration).
# ---------------------------------------------------------------------------

LOG_DIVER_DOC = AGENTS_DIR / "log-diver.md"
DEPLOY_ANALYST_DOC = AGENTS_DIR / "deploy-analyst.md"
DEPENDENCY_CHECKER_DOC = AGENTS_DIR / "dependency-checker.md"

SPECIALIST_DOCS = [LOG_DIVER_DOC, DEPLOY_ANALYST_DOC, DEPENDENCY_CHECKER_DOC]
SPECIALIST_DOC_IDS = [p.relative_to(REPO_ROOT).as_posix() for p in SPECIALIST_DOCS]

SPECIALIST_TEXT_BY_DOC = {
    p: p.read_text(encoding="utf-8") for p in SPECIALIST_DOCS
}
SPECIALIST_PURPOSE_SECTION_BY_DOC = {
    p: _section(text, "Purpose") for p, text in SPECIALIST_TEXT_BY_DOC.items()
}
SPECIALIST_FINDINGS_SECTION_BY_DOC = {
    p: _section(text, "Findings contract")
    for p, text in SPECIALIST_TEXT_BY_DOC.items()
}


@pytest.mark.parametrize("doc_path", SPECIALIST_DOCS, ids=SPECIALIST_DOC_IDS)
def test_all_specialist_scoped_sections_were_found(doc_path):
    for name, section in (
        ("Purpose", SPECIALIST_PURPOSE_SECTION_BY_DOC[doc_path]),
        ("Findings contract", SPECIALIST_FINDINGS_SECTION_BY_DOC[doc_path]),
    ):
        assert section is not None, "%s has no `## %s` section" % (doc_path, name)


# --- Purpose gate (US4-AS1): the single-purpose anchor. --------------------


@pytest.mark.parametrize("doc_path", SPECIALIST_DOCS, ids=SPECIALIST_DOC_IDS)
def test_specialist_purpose_names_single_purpose_anchor(doc_path):
    lowered = SPECIALIST_PURPOSE_SECTION_BY_DOC[doc_path].lower()
    assert "single" in lowered or "one hypothesis" in lowered, (
        "%s's Purpose section does not name the single-purpose anchor "
        "('single' or 'one hypothesis')" % doc_path
    )


# --- Findings contract gates (US4-AS2): deep-investigator-only return,
# {url, excerpt} evidence shape, empty-findings-is-legitimate. --------------


@pytest.mark.parametrize("doc_path", SPECIALIST_DOCS, ids=SPECIALIST_DOC_IDS)
def test_specialist_findings_contract_names_deep_investigator_only(doc_path):
    lowered = SPECIALIST_FINDINGS_SECTION_BY_DOC[doc_path].lower()
    assert "deep investigator" in lowered, (
        "%s's Findings contract section does not name 'deep investigator'"
        % doc_path
    )
    assert "never" in lowered, (
        "%s's Findings contract section does not state the never-to-"
        "orchestrator clause ('never')" % doc_path
    )


@pytest.mark.parametrize("doc_path", SPECIALIST_DOCS, ids=SPECIALIST_DOC_IDS)
def test_specialist_findings_contract_names_url_excerpt_pair(doc_path):
    section = SPECIALIST_FINDINGS_SECTION_BY_DOC[doc_path]
    assert "{url, excerpt}" in _normalize_ws(section), (
        "%s's Findings contract section does not name the {url, excerpt} "
        "evidence shape" % doc_path
    )


@pytest.mark.parametrize("doc_path", SPECIALIST_DOCS, ids=SPECIALIST_DOC_IDS)
def test_specialist_findings_contract_states_empty_is_legitimate(doc_path):
    lowered = SPECIALIST_FINDINGS_SECTION_BY_DOC[doc_path].lower()
    assert "empty" in lowered, (
        "%s's Findings contract section does not name the empty-findings "
        "case" % doc_path
    )
    assert "legitimate" in lowered, (
        "%s's Findings contract section does not state that an empty "
        "findings summary is legitimate" % doc_path
    )
