# Research: Catalog Adapter (slice 7)

Plan-time pins. Each entry resolves a question the spec deliberately left open (its
Assumptions section) or a convention this slice must inherit from the merged scaffold.
Format: **Decision / Rationale / Alternatives rejected.**

---

## R1 — Fixture catalog repo: location

**Decision**: `tests/fixtures/catalog/` — a fixture *repo tree* (`repo/services/<svc>/catalog-info.yaml`)
plus sibling expectation files (`golden-models.json`, `resolution-matrix.json`) and a
`README.md` recording the format decision (R2).

**Rationale**: the spec's Assumptions state plainly that no catalog fixture exists today and
that design §10's `tests/scenarios/` sketch was superseded by slice 1's actual scaffold,
which uses `tests/fixtures/<domain>/` (`doctor/`, `fingerprint/`, `seeds/`, `store/`, …).
Following the scaffold's real convention keeps `conftest.load_fixture` / `fixture_path`
usable unchanged. Nesting the catalog files under `repo/` inside that domain directory is
what makes file-*path* ordering meaningful (R7's duplicate tie-break) and lets the
malformed-file case be a real sibling file rather than a special-cased string.

**Alternatives rejected**: `tests/scenarios/catalog/` (design §10's sketch — that layout was
never built; inventing it now forks the fixture conventions for one slice).
`tests/fixtures/catalog-repo/` at top level (breaks the one-directory-per-domain grouping).

---

## R2 — Fixture catalog file format: strict JSON syntax inside `catalog-info.yaml`

**Decision**: fixture files are named `catalog-info.yaml` — the real Backstage filename —
and their content is written in **strict JSON syntax**: double-quoted keys and string
scalars, a space after every `:`, no comments, no trailing commas. Because YAML 1.2 is a
superset of JSON, every fixture file is genuinely valid YAML *and* parseable by the reference
encoding with stdlib `json`. **No YAML dependency is added.** The malformed fixture is a
truncated flow mapping — invalid as both YAML and JSON.

**Wording matters here** (converge round 1, lens B finding 7): the *instruction* must be
"strict JSON syntax", with "valid YAML 1.2 flow style" as the consequence — not the reverse.
"YAML flow style" is strictly broader than JSON and admits `{kind: Component}`, which
`json.load` rejects outright; an implementer handed the loose phrasing would plausibly write
exactly that and turn every fixture into a `Failure`. The space-after-colon rule is likewise
deliberate: YAML **1.1** parsers (PyYAML — what a future scenario-harness slice would reach
for) reject `{"a":1}`.

**Rationale**: three constraints meet here. (a) The fixture is the integration contract's
stand-in, so it should be an actual `catalog-info.yaml`, not a differently-named mirror.
(b) The reference encoding is dev tooling (D-1 exempt) but CI installs **pytest only**
(`.github/workflows/verify.yml`); adding PyYAML means editing the gate surface and taking a
third-party dev dependency for one slice. (c) The rules under test are *structural* — key
paths (`metadata.annotations["oncall-harness/alert-match"]`), match order, per-field
degradation, file-scoped failure isolation — and YAML and JSON share one data model, so
flow style loses no structural fidelity.

**Residual gap, stated honestly**: YAML-*syntax*-specific failure modes (tab indentation,
anchors/aliases, block-scalar folding, duplicate keys) are not exercised by these fixtures.
That gap is scenario-harness territory — where a live agent reads a real block-style
catalog through its own tooling — and is recorded as such rather than papered over.

**Alternatives rejected**: **PyYAML + block-style fixtures** — highest fidelity, but costs a
CI edit plus a dependency the repo's stdlib-only grain has so far avoided; revisit if a
later slice needs YAML syntax coverage in CI. **A hand-rolled stdlib YAML-subset parser** —
makes the parser, not the documented rules, the thing under test, and turns "malformed"
into "whatever my parser rejects" (circular). **`.json` fixture files** (slice 4's local
precedent) — no YAML validity claim at all and a filename the skill prose never mentions.

---

## R3 — Reference encoding: `tests/helpers/catalog_reference.py`

**Decision**: the dev-only, test-side executable form of the documented rules lives at
`tests/helpers/catalog_reference.py`, importable as `from helpers.catalog_reference import …`
(slice-1 conftest already puts `tests/` on `sys.path`). Plain functions over plain dicts —
no classes, matching `doctor_flows.py` / `store_flows.py` / `setup_flows.py`.

**Rationale**: `tests/helpers/` is exactly where slices 3–4 put dev-only executable
encodings of documented conventions, and its contents are already covered by the packaging
boundary as never-shipped. `tools/` is the mock MCP's home — a *simulated external service*,
a different thing from a rules encoding, and putting the catalog encoding there would imply
the catalog is an MCP-side concern. Naming it `catalog_reference.py` rather than
`catalog_flows.py` signals what it is: a reference encoding (the `bb-fingerprint` ↔
`fingerprint.md` relationship of slice 3), not a flow simulation.

**Alternatives rejected**: `tools/bb-catalog-reference/` (implies shippable tooling and
splits the dev-encoding convention across two homes); inlining the rules in each test module
(the four test modules would each re-encode the rules — three chances to disagree).

---

## R4 — Annotation vocabulary: `oncall-harness/*` is canonical; slice 4's fixture is retagged

**Decision**: the canonical annotation vocabulary is exactly FR-002's, matching design §6.1:

| Model field | Annotation / path |
|---|---|
| `name` | `metadata.name` |
| `owner` | `spec.owner` |
| `depends_on` | `spec.dependsOn` |
| `dashboards` | `grafana/dashboard-selector` |
| `runbooks` | `oncall-harness/runbooks` |
| `alert_matchers` | `oncall-harness/alert-match` |
| *(adapter-internal linkage)* | `pagerduty.com/service-id`, `github.com/project-slug` |

Slice 4's `tests/fixtures/doctor/catalog-valid.json` currently uses `battle-buddy/alert-match`
and `battle-buddy/dashboard` — a second, undocumented vocabulary. It is **retagged** to the
canonical keys, and a ratchet test asserts the doctor fixture's annotation keys are a subset
of the canonical set so the two surfaces cannot silently diverge again.

**Rationale**: retagging is safe and cheap — `/doctor`'s catalog check (`doctor_flows.check_catalog`)
only asserts the file *parses*; no test reads its annotation keys (verified by grep). Leaving
two vocabularies in the tree would mean the first real implementer of the catalog check has to
guess which is authoritative. FR-002 and the design agree, so the design's keys win and the
one-off fixture follows.

**Alternatives rejected**: leaving slice 4's fixture untouched with a note (preserves the
ambiguity this slice exists to remove); changing FR-002 to `battle-buddy/*` (contradicts
design §6.1 and the spec's converged requirement — a spec change, not a plan decision).

---

## R5 — SC-005 capability-naming scan with an annotation-key allowlist

**Decision**: `tests/contract/test_catalog_prose.py` extends slice 3's scan mechanism over
`skills/catalog/**/*.md` by importing `DENY_PATTERNS` from
`tests/contract/test_skill_capability_naming.py` (already a public module-level dict), and
runs the deny scan on prose from which **canonical annotation keys have first been masked**.

The mask is the exact key set from R4 — full keys only (`grafana/dashboard-selector`, not a
bare `grafana/`), so `grafana`, `pagerduty`, or `github` written as a *product* name outside
an annotation key still fails. A positive-control test pins both halves, mirroring
slice 3's `test_fenced_datadog_example_is_the_documented_exemption`: the canonical keys must
be present in the prose (else the exemption exempts nothing), and the same vendor words must
not survive masking.

**One extension over slice 3's set** (converge round 1, lens A finding 13): `DENY_PATTERNS`
contains `grafana`, `pagerduty`, `splunk`, `datadog`, `opsgenie` — but **no `github`**. Masking
`github.com/project-slug` against that set is a no-op, so the positive control's third leg
would be vacuously true. The catalog scan therefore adds a local `github` pattern, which makes
the mask load-bearing for all three vendor prefixes rather than two.

**Rationale**: the spec's SC-005 requires exactly this ("the scan must not trip on `grafana/`,
`pagerduty.com/`, `github.com/` inside FR-002's table"). Annotation keys are catalog-*file*
vocabulary — the team-facing integration contract — not MCP server or tool names, which is
what Constitution VII governs. Masking whole keys rather than widening the deny-list keeps
the ratchet tight.

**Alternatives rejected**: fence-stripping (slice 3's mechanism for worked-example *data*) —
the annotation table is normative prose in a markdown table, not a fenced example, and
fencing it to dodge the scan would degrade the doc to satisfy a test. Removing the vendor
patterns from the deny-list for this scan (loses the real protection wholesale).

---

## R6 — SC-006 storage/artifact/diary-op scan, and the no-invented-code-ops rule

**Decision**: two mechanical prose gates in the same module.

1. **SC-006**: `skills/catalog/**/*.md` contains zero occurrences of `append_record`,
   `update_record`, `put_file`, `append_entry` — the division-of-knowledge rule instrumented.
   (`read_records` is not scanned: reading the session store is not a catalog *write*, and
   the spec names only the four write ops.)
2. **FR-007's second half**: the prose cites **no code-capability operation name at all** —
   it refers to the capability generically ("your code tool's file reads"), and the gate
   asserts both the absence and the presence of that generic phrasing.

**Finding that qualifies the requirement's rationale** — FR-007 justifies its rule with
"contract v1 defines no code operations, and their shapes are slice 4's to pin or defer."
Slice 4 in fact **pinned** them: `manifest/capabilities.json` declares
`optional.code.ops` = `read_file(path) -> {content}`, `list_commits(window)`,
`search(query)` with full input/output shapes (authored in the manifest per slice 4's
research R7, "until a consuming slice promotes it into the operation contract").
Operation contract v1 (`tools/bb-mock-mcp/contract.json`) still has no `code` half, so the
spec's Assumption is accurate about the *contract* and outdated about the *manifest*.

**Decision on that gap**: this slice satisfies FR-007 **as written** — generic reference,
zero code-op citations. Citing `read_file` would no longer be *inventing* an operation, but
the requirement's normative MUST is the generic reference, and staying generic is also the
only form that survives whether or not a future slice promotes those ops into contract v1.
A secondary fidelity assertion backs the primary gate: should any code-operation-shaped
token ever appear in this prose, it must exist in `manifest/capabilities.json`'s
`optional.code.ops` — so a future deliberate relaxation degrades into a real check instead
of an unguarded hole. Promotion of the `code` ops into contract v1 is left to the slice that
consumes them (candidates: 8, 9) and is recorded here, not decided here.

**Rationale**: SC-006 is spec-mandated verbatim. The FR-007 gate keeps this slice from
binding its prose to an interface whose contract half is still unpinned — the failure mode
is a skill telling an agent to call an operation `/doctor` has no binding for.

**Alternatives rejected**: reusing slice 3's op-fidelity check *alone* (it asserts cited ops
*exist in* `contract.json` — here the primary requirement is to cite none); citing
`read_file` because the manifest now pins it (defensible on the manifest, but contradicts
FR-007's normative sentence — a spec change, not a plan decision).

---

## R7 — Determinism pins encoded as data, not prose-only

**Decision**: the spec-pinned tie-breaks become fixture-backed, mechanically asserted
behavior in the reference encoding — and, per converge round 1, each fixture must be
*discriminating*: the case has to fail against the plausible wrong implementation, not merely
pass against the right one.

| Pin | Encoding | What makes the fixture discriminating |
|---|---|---|
| Exact before substring | stage 2 runs only on an empty stage-1 result | the case's exact and substring candidates are **different services**, so a stage-merging implementation returns `ambiguous` |
| Multi-match at either stage | outcome `ambiguous` carrying **all** candidates, sorted by source path — never a pick | the `zz-billing`/`checkout` pair sorts oppositely by path vs name, so a name-sorting implementation fails; asserted **in order**, not as a set |
| Duplicate `metadata.name` | first in **lexicographic source-path order** wins; loser dropped with a `duplicate_name` warning | the pair shares a name, so path is the only available discriminator |
| Substring direction | the *service's name* is searched for *within* each alert field — never the reverse | the probe value is a **strict substring of a real service name** (`ledger` ⊂ `ledger-svc`), so a reversed implementation resolves it instead of missing |
| `dependsOn` depth | exactly one hop; the encoding never recurses | a two-hop chain (`checkout` → `inventory` → `ledger-svc`) whose second hop must be absent |
| Exact stage reads matchers only | the service's own `name` is a substring-stage input exclusively | recorded as D-22's sixth pin — FR-003's "exact tag/name" is the *alert's* tag/name field, not the service's name |

**Rationale**: these are precisely the places where prose and an implementation can drift
silently, and the spec pinned each one as a default over design silence. Encoding them as
data (a `resolution-matrix.json` case per rule) makes SC-003's "zero silent picks" a counted
property rather than a claim — but only if each case can actually fail, which is what the
third column exists to guarantee. Converge round 1 found three cases that could not
(exact-beats-substring with one service, an arbitrary reverse probe, and candidate ordering
with no inverting pair) and the roster gained `zz-billing` to fix the last of them.

**Alternatives rejected**: asserting them inline in test code only (the fixture then can't be
reused by the scenario harness, which is the stated consumer of these same rules).

---

## R8 — Test layer: contract only; no unit-layer module

**Decision**: all four new test modules live in `tests/contract/`. Nothing is added to
`tests/unit/`.

**Rationale**: `tests/conftest.py` states the layer rule explicitly — the unit layer "proves
future shipped code, which must not depend on dev tooling," and runs on the py3.9 shipped-code
floor. The reference encoding *is* dev tooling, so every test that imports it belongs to the
contract layer, which slice 1 already runs on 3.12 alone. Slice 3's
`test_fingerprint_reference.py` and `test_skill_capability_naming.py` set the precedent that
"contract" means *the executable spec of an agreement*, not merely "uses the mock."

**Alternatives rejected**: a unit-layer module for the pure matcher (would drag the dev-only
encoding across the layer boundary conftest draws, for no coverage gain).

---

## R9 — Design-doc reconciliation: §6.1 clarification + decision-log row D-22

**Decision**: this slice amends `bb-technical-design.md` in the same PR — a short §6.1
clarification plus one new decision-log row **D-22** recording the five catalog pins
(linkage annotations as adapter-internal metadata; explicit-choice on multi-match; one-hop
`dependsOn`; substring direction; lexicographic duplicate tie-break).

**Rationale**: the spec flags exactly these as "flagged for design reconciliation," and the
constitution's Development Workflow requires hard-to-reverse choices to amend the design
doc's §11 decision log in the same change. Slice 6 set the precedent by reconciling §5.4's
example ledger inside its own slice. The design's mapping table lists `paging linkage` and
`repo` rows with no matching field in the six-field model — D-22 resolves that dangling
without widening the consumer-facing model.

**Alternatives rejected**: a standalone ADR file (the repo has no `adr/` convention and §11
is the recorded home); deferring the amendment to a follow-up PR (leaves the design and the
shipped prose disagreeing at merge time).

---

## R10 — Packaging and boundary coverage: no changes needed

**Decision**: no edits to `tests/fixtures/packaging/intended-bundle.json`,
`tests/unit/test_packaging.py`, or `tests/unit/test_stdlib_boundary.py`.

**Rationale**: the intended bundle already globs `skills/**`, so `skills/catalog/` ships
automatically; `tests/**` and `tools/**` appear nowhere in the declared bundle, so the
fixtures and the reference encoding are outside it. The stdlib-boundary walk covers `hooks/`
and `bin/` only — this slice adds no shipped Python, so it has nothing to say here.

**Two honesty corrections from converge round 1** (lens A findings 4 and 11). First,
`test_packaging.py::check_bundle` is a **string lint over the declared glob list** — it never
expands a glob against the filesystem, and the manifest it lints is itself a stand-in for a
plugin manifest that does not exist yet. It is a real ratchet on what the bundle *declares*,
not proof of what would ship; "proven never-shipped" overstates it. Second, "no shipped
Python was added" is therefore **not** self-evidencing: `test_stdlib_boundary.py` passes
vacuously for this slice, and an end-of-slice eyeball is not a test. FR-009 gets a direct
assertion instead — `skills/catalog/` contains no `*.py`, and `tests/helpers/catalog_reference.py`
is named by no bundle glob — so SC-001's "every FR maps to ≥1 test" holds without an exception.

**Alternatives rejected**: adding `skills/catalog/**` explicitly to the bundle (redundant
with the existing glob and would imply the glob doesn't work).

---

## R11 — Runbook reference format: URL + commit SHA, pointer-only

**Decision**: the documented `runbook_refs` entry shape is `{url, commit}` — the git-hosted
URL plus the commit SHA it was read at — carried to the session row per slice 3's schema.
`commit` is documented as present **where git-hosted** and absent otherwise (a wiki-hosted
runbook has a URL and no SHA); content is never carried. The prose gate asserts the format
statement and the never-content rule; the reference encoding surfaces runbook entries from
`oncall-harness/runbooks` as pointers only.

**Rationale**: FR-005 and slice 3's `runbook_refs` column pin this jointly, and US4's
Independent Test is a documented-flow inspection. Making `commit` conditional matches the
spec's own "(where git-hosted)" qualifier rather than over-promising a SHA the catalog can't
supply.

**Alternatives rejected**: requiring `commit` unconditionally (would make every non-git
runbook link unrepresentable); an `{url, excerpt}` shape (that is Constitution IV's
*evidence* shape — a runbook reference is a pointer, not an evidence claim).

---

## R12 — Fix-up offer content: a ready-to-commit annotation snippet

**Decision**: the miss path's catalog fix-up is documented as a **ready-to-commit
`catalog-info.yaml` annotation snippet** keyed to the responder's answer — the
`oncall-harness/alert-match` key with the alert's discriminating field value, plus the
service file path it belongs in. The skill defines the snippet's content and states that
committing it is the responder's PR, never an agent write (human-curated store,
Constitution I/§2).

**Rationale**: FR-003 makes the fix-up's *content* this slice's deliverable while the
*interaction* is slice 5's. A snippet is the smallest thing that is both content and
actionable; anything less (a prose suggestion) isn't a deliverable a test can inspect.

**Alternatives rejected**: an auto-opened PR (shipped integration code, Constitution I);
writing the fix-up into the session store (violates the never-copied rule of FR-005).

---

## R13 — Converge round 1: defended findings and the two rules it changed

Two adversarial review lenses (spec/design fidelity; executability/test rigor) returned 31
findings against the plan artifacts. 27 were fixed in place and are visible in the artifacts
above. Two were **defended**, and are recorded here rather than silently declined:

**Defended 1 — the SC-006 scan is unconditional, where the spec says "applied to catalog
content."** Both lenses flagged the widening. It stands: scoping a scan to "the catalog-flow
sections" requires a section boundary the prose does not carry, and any such boundary is
gameable by moving a sentence. The cost is real and accepted — the prose cannot write
"catalog content is never passed to `append_record`" and must instead say "never written to
any store" — so T015 carries that instruction explicitly and T016's docstring records the
widening as deliberate, not as a bug for a future author to "fix".

**Defended 2 — `spec.md`'s FR-007 rationale clause is left uncorrected.** The clause
("contract v1 defines no code operations, and their shapes are slice 4's to pin or defer") is
factually stale, since slice 4 pinned them in the manifest (R6). The spec is converged and the
normative MUST is unaffected by the staleness, so reopening it would be churn against a
reviewed artifact. The correction lives in R6 and is called out in the PR body instead. A
later slice that promotes the `code` ops into contract v1 is the natural place to amend the
sentence.

**Two rules the round changed outright**, both of which had narrowed the spec without saying
so:

1. **Dangling `dependsOn` entries are kept, not filtered.** An earlier draft filtered
   `blast_radius` to names present in the catalog. FR-006 authorizes no such filter, and on
   the messy-catalog team this slice targets (D-19) a dependency on an uncatalogued service is
   the normal case — silently shrinking the blast radius is the opposite of the slice's
   surfaced-not-fatal posture. Entries are now returned unfiltered and surfaced as
   `dangling_dependency` warnings (data-model.md §3, §9).
2. **`spec.owner`'s absence is surfaced.** An earlier draft defaulted it to `""` silently,
   even though PRD FR-13 puts it in the minimal viable subset. A service nobody owns now
   carries a `missing_owner` warning — deliberately a warning and not a `disabled_features`
   entry, since ownership disables no feature (data-model.md §1).
