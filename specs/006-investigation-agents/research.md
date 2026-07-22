# Research — Investigation Agents & Skill (plan-time pins)

Every unknown the plan depends on, resolved before design. Format per house style:
Decision / Rationale / Alternatives considered.

## R1 — Deliverable locations

**Decision**: `agents/triage.md`, `agents/deep-investigator.md`, `agents/log-diver.md`,
`agents/deploy-analyst.md`, `agents/dependency-checker.md`;
`skills/investigation/SKILL.md` + `references/schemas.md`, `references/briefing.md`,
`references/retrieval.md`.

**Rationale**: design §3.1's plugin bundle layout names exactly these paths.
`retrieval.md` ships as a **pointer** to `skills/session-store/references/retrieval.md`
— slice 3's plan made session-store the normative home (its placement assumption, cited
by this spec's Assumptions); the pointer resolves §3.1's sketch without duplicating
rules (one source of truth per rule).

**Alternatives considered**: omitting `retrieval.md` entirely (rejected — §3.1 names it,
and the skill needs a stable in-bundle reference target for the retrieval flow it
instructs agents to consume); restating the retrieval rules (rejected — duplication is
exactly what slice 3's placement decision forbids).

## R2 — Agent definition format

**Decision**: each agent file is markdown with minimal YAML frontmatter (`name`,
`description` only) followed by structured sections with machine-parseable anchors:
`## Model class` (class + rationale + configurability statement), `## Budget` (triage
only: default, config key, enforcement attribution), `## Toolset` (a markdown table
with `Capability` / `Operations` / `Access` columns — SC-006's parse target),
`## Input contract`, `## Output contract`, plus role-specific sections (four questions,
re-invocation, ledger rules, findings contract).

**Rationale**: frontmatter carries only identity — a `tools:` frontmatter field would
require concrete tool names (Constitution VII forbids) and a `model:` field would pin a
model ID (the spec's model-class assumption forbids). Structured section anchors and
tables are the same discipline `fingerprint.md` uses for worked examples: prose the
tests can parse without asserting on wording.

**Alternatives considered**: full Claude Code agent frontmatter with `tools:`/`model:`
(rejected — violates Constitution VII / the configurable-class pin); free prose with no
parse anchors (rejected — FR-012 requires asserting on artifacts, and un-anchored prose
forces tests to grep wording, the brittleness slice 3 avoided).

## R3 — Model-class configurability without minting config keys

**Decision**: the triage definition states "fast/cheap class" and the deep-investigator
"frontier class" with the budget-vs-depth rationale, each noting the class default is
overridable via the workspace `battleBuddy` configuration (design D-10). **No new config
key is minted.** The one configuration key any definition names is the protocol's
existing `budgets.triageTurnCap` (default 15).

**Rationale**: the local-state protocol documents keys read by the deterministic layer;
model-class resolution happens at spawn time — slice 5's surface. Minting a key here
would pin a contract for a consumer that doesn't exist yet (the same reason slice-2
FR-010 deferred the ticket capability: the set grows with the contract, not ad hoc).

**Alternatives considered**: pinning `models.triage`/`models.deep` keys (rejected —
invents protocol surface for slice 5 without slice 5's participation); pinning model
aliases like "haiku" (rejected — spec assumption says class defaults, never model IDs).

## R4 — Schemas-reference ↔ validator consistency mechanism

**Decision**: `schemas.md` carries worked examples as fenced JSON blocks, each
immediately preceded by an HTML marker line:
`<!-- bb-example: <id> expect=valid -->` or
`<!-- bb-example: <id> expect=invalid rule=<rule.name>[,<rule.name>…] -->`.
`test_schemas_reference.py` parses every marker+fence pair, runs the real
`bb_validate.validate()` on the JSON, and asserts: `expect=valid` ⇒ zero violations;
`expect=invalid` ⇒ the named rule(s) each appear among the violation rules —
**membership assertions, never exact-set**: several invalid states legitimately trip
more than one rule (e.g. 2 live non-fresh hypotheses fire both anchoring rules), so an
exact-set assertion would false-fail (converge finding). A non-vanishing guard
requires a minimum example count and at least one valid + one invalid example per
schema. The same module asserts vocabulary agreement in **exact set-equality both
ways** against the validator's constants (`PHASES`, `INVARIANT_PHASES`,
`PROVENANCE_VALUES`, `VALIDATION_VALUES`, `MIN_LIVE_HYPOTHESES`,
`VERDICT_SCHEMA`/`LEDGER_SCHEMA`) — which requires a machine-readable source in the
doc: `schemas.md` carries one fenced vocabulary block in a pinned line format
(`phases: a | b | …`, `invariant-phases: …`, `provenance: …`, `validation: …`,
`min-live: 3`, `schemas: bb.verdict.v1 | bb.ledger.v1`) that the test parses for
equality; substring containment alone could not catch a doc listing an extra or
misspelled value (converge finding).

**Rationale**: this is slice-3's FR-003 fingerprint precedent (doc ↔ helper ↔ corpus,
worked examples recomputed through the real implementation) applied to the validator,
exactly as this slice's FR-011 requires. Markers make classification machine-readable
without constraining the surrounding prose; importing constants makes doc/validator
drift a test failure, not a review hope.

**Alternatives considered**: a separate JSON example corpus under `tests/fixtures/`
(rejected as the *primary* form — the doc's own examples must be the classified ones,
or the doc could drift while a private corpus stays green; the validator's existing
fixture corpus already covers tool-side cases); parsing headings/prose to infer
intent (rejected — wording-brittle).

## R5 — Anchoring-guard matrix construction

**Decision**: `tests/unit/test_anchoring_matrix.py` builds ledgers programmatically
(a small in-test builder) and parametrizes both invariant phases
(`evidence-gathering`, `deep-dive`) × the four spec states: 2 live ⇒
`ledger.min_live_hypotheses` present among the violations; 3 live none fresh ⇒
`ledger.fresh_required` present; 3 live with fresh ⇒ no anchoring-rule violations;
3 live non-fresh + 1 **dead** fresh ⇒ `ledger.fresh_required` present (dead fresh
does not satisfy). Assertions are rule-presence (membership), never exact-set — a
2-live-non-fresh cell legitimately fires both anchoring rules. It also asserts the
early phases (`triage-seeded`, `hypothesis-generation`) accept sparse and empty
ledgers — empty meaning `hypotheses: []`, since `hypotheses` is a required field
whose omission trips `schema.missing_field` — and `resolution` is non-invariant,
pinning the full phase scoping FR-002 states.

**Rationale**: SC-004 is a matrix over pure validator behavior — no mock, no store —
so it belongs in the **unit layer** beside `tests/unit/test_validate.py`, running on
the py3.9 shipped-code floor as well as 3.12 (contract placement would skip the
floor; converge finding). Programmatic construction keeps 8+ cells cheap and exact;
the doc-agreement half already rides R4's worked examples (the schemas reference
documents representative guard states with markers); the existing `test_validate.py`
corpus covers per-rule emission, while this module pins the phase × state matrix
SC-004 names.

**Alternatives considered**: all matrix cells as documented examples in `schemas.md`
(rejected — a dozen near-identical JSON blocks would bloat a normative doc that readers
need to stay sharp; the doc shows representative states, the test sweeps the matrix).

## R6 — Role-registration shape check

**Decision**: the skill's spawn-flow section documents the exact write: merge
`{<actor-key>: <role>}` into `agents.json`'s `roles` map, file shape
`{"protocol": "bb.local.v1", "roles": {...}}`, role vocabulary
`triage` | `deep` | `specialist:<name>`. `test_role_registration.py` simulates the
documented write against a temp state dir and validates shape: protocol tag, `roles`
map of string→string with non-empty string actor keys, every role matching
`^(triage|deep|specialist:[a-z0-9-]+)$`; a seeded non-conforming role (e.g. `admin`)
is rejected by the check (SC-003). **The role values under test are derived from the
shipped artifacts, not test literals** (converge finding — FR-012 asserts on
artifacts): `triage` and `deep` from the existence of `agents/triage.md` /
`agents/deep-investigator.md`, and each `specialist:<stem>` from the shipped
specialist doc filenames, so a renamed or added agent doc changes what the test
checks. The test reuses/extends `tests/unit/test_local_state_protocol.py`'s existing
agents.json coverage where overlap exists rather than duplicating it.

**Rationale**: the protocol doc names slice 6's spawn flow as the registered writer;
the test proves the *documented* write conforms to the protocol shape — artifact
assertion, no live hooks involved (no production writer exists yet; deriving the
role vocabulary from the shipped agent docs keeps the check biting on a real
deliverable rather than its own literals). The specialist-name charset pin
(lowercase kebab, matching the three shipped specialist names) makes "conforming"
decidable.

**Alternatives considered**: asserting against the hook source's parsing (rejected —
slices build on the protocol document, never on hook source, per that contract's own
header); skipping the negative case (rejected — SC-003 names it).

## R7 — Toolset ↔ manifest cross-check (SC-006)

**Decision**: `test_agent_toolsets.py` parses each agent doc's `## Toolset` table
(R2's format), extracts the `Capability` column tokens, and asserts: every token ∈
manifest `required` ∪ `optional` keys (loaded dynamically from
`manifest/capabilities.json`, never hardcoded); triage's set is exactly
`{alerting, code, storage, observability}` (FR-006); every specialist row and every
triage row is marked read-only; the deep investigator's mutating rows are marked
approval-gated (FR-007). Non-vanishing guard: all five docs parse to ≥1 capability row.

**Rationale**: SC-006's instrument, per the spec; dynamic manifest loading follows the
slice-3 contract-ops precedent (a doc citing a capability the system doesn't declare
fails, without a maintained allow-list). The manifest merged with slice 4, so the
spec's cross-slice sequencing concern is moot — the test lands here.

**Alternatives considered**: checking against `bb-mock-mcp/contract.json` (rejected —
the contract has no optional capabilities, so `code`/`observability` would false-fail;
the manifest is the declared-capability authority, the same resolution slice 4 pinned
for undotted op tokens).

## R8 — Design §5.4 example-ledger reconciliation

**Decision**: amend `bb-technical-design.md` §5.4's ledger example in this slice's PR
to a validator-passing state (3 live hypotheses, ≥1 fresh, non-fresh validated), and
call the edit out in the PR body.

**Rationale**: the spec's Assumptions flag the example for reconciliation ("the schemas
reference must follow the validator"); leaving a failing example in the upstream design
doc while shipping a normative reference that contradicts it would be a standing
doc-vs-doc conflict. A worked-example fix is a clarification, not a decision-log
amendment (no D-entry change).

**Alternatives considered**: leaving the design doc untouched with a note in
`schemas.md` (rejected — perpetuates the conflict the spec explicitly flagged);
treating it as a design-decision amendment (rejected — no decision changes, only an
example that predates the validator's phase model).

## R9 — Schema field authority and v1 scope

**Decision**: `schemas.md` documents exactly the field sets the merged validator
enforces (see data-model.md for the tables), and reproduces the validator's recorded
v1 scope: `known_issue` sub-fields beyond `validation` unchecked; hypothesis `status`
accepts any string with only `"live"` counting toward the anchoring invariant (unknown
status shrinks the live set — fails loud, never silently passes); design-doc example
fields not enforced by v1 (`known_issue.matched_session_id` etc.) documented as
carried-but-unvalidated.

**Rationale**: FR-011 makes the validator the implementation of the normative doc —
so the doc must document the implementation's actual v1 scope, which the validator's
own docstring records as a decision. Anything stricter documented-as-normative would
instantly violate SC-002 (documented-valid must pass unmodified).

**Alternatives considered**: documenting an aspirational fuller schema with a
"validator catches up later" note (rejected — creates exactly the doc/tool disagreement
SC-002 exists to forbid; the validator's header says it tightens as *this doc* lands,
so the doc pins today's truth and future tightening is a versioned change).

## R10 — Untrusted-capability set and delimiter

**Decision**: the skill's untrusted-data rule names v1 set `{alerting, observability}`
and the delimiter `<untrusted-telemetry>` for agent-controlled quoting (checkpoints,
briefings, diary drafts, subagent prompts), stated as probabilistic mitigation with
guarantees living in deterministic layers 1–3; the tripwire is advisory (D-20). The
ticket-shaped-tools deferral is restated with slice-2 FR-010's rationale.

**Rationale**: spec FR-004 pins all of this; the delimiter token matches design §3.5's
literal; set parity with the slice-2 tripwire keeps skill prose and hook behavior
telling one story.

**Alternatives considered**: none open — the spec resolved this; recorded here so the
implementing tasks quote one source.

## R11 — Packaging registration for new shipped dirs

**Decision**: **no fixture edit** — `tests/fixtures/packaging/intended-bundle.json`
already lists `agents/**` and `skills/**` (which subsumes `skills/investigation/**`);
the task is verification-only: confirm both new dirs are covered by the existing
globs and `tests/unit/test_packaging.py` stays green (converge finding — the
originally planned addition was a no-op duplicate).

**Rationale**: the intended-bundle fixture stands in for the real plugin manifest
(its own docstring); the slice-1 authors pre-registered the design §3.1 layout, so
the new surfaces are already inside the boundary. No forbidden segments are
introduced (references/ is not fixtures/).

**Alternatives considered**: adding narrower duplicate globs (rejected — redundant
lines invite drift and add nothing the packaging check reads).

## R12 — Doc-structure gates for skill-level requirements

**Decision**: `test_investigation_prose.py` asserts the structural properties
FR-001/002/004/009/010 pin, on anchors rather than wording: (a) discipline-first —
SKILL.md's first `##` section after the overview is the validation discipline, and it
precedes any methodology section (US1-AS1); (b) the anchoring-guard section names both
invariant phases and both early phases with the enforcement attribution "slice-2
validator at checkpoint-write time"; (c) launch conditions — exactly three condition
anchors (a/b/c) plus the confirm rule and `autoLaunchDeep`; (d) enforcement
attribution — the turn-cap and registration sections attribute enforcement to the
deterministic layer (the skill/definitions never self-claim); (e) the naming scan
(SC-005) over all **nine** new prose files (5 agent docs + SKILL.md + 3 references),
importing the **public merged** `DENY_PATTERNS` from
`test_command_capability_naming.py` (slice-4's list already folds in slice-3's plus
the vendor extensions; the extensions dict itself is private and not imported —
converge finding) and `FENCE_RE` from `test_skill_capability_naming.py`, `mcp__`
raw-scan included, fences stripped for the deny-list half only.

**Rationale**: these are the spec's document-property Independent Tests; anchored
structure (section ordering, labeled condition list, attribution lines placed in
pinned sections) keeps them artifact-assertions per Constitution VIII. Reusing the
imported deny-list keeps one list in one place (slice-4 precedent).

**Alternatives considered**: one mega-module for all prose checks including toolsets
(rejected — SC-006's manifest cross-check and the doc-structure gates fail for
different reasons and belong in separately-named modules, matching the slice-3/4
one-concern-per-module layout).
