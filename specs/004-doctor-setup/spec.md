# Feature Specification: Doctor & Setup

**Feature Branch**: `004-doctor-setup`

**Created**: 2026-07-20

**Status**: Draft

**Input**: Slice 4 of the battle-buddy MVP (design `bb-technical-design.md` §7.1–§7.3, §2.1, §3.1, §3.2 step 1; decisions D-7, D-13, D-15, D-16; PRD FR-25/FR-25a, SM-2; Constitution I, II, VII, VIII): the capability-verification and onboarding surface — `/doctor` as conformance test and binding linker, `/setup` as the idempotent, mode-aware onboarding wizard, and the shipped capability manifest — expressed as command prose, JSON manifest and templates, and hermetic contract tests against `bb-mock-mcp`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A new team goes from empty directory to green in one command (Priority: P1)

A team installs the plugin and runs `/setup` in an empty directory. Setup detects team mode (no config block), resolves the team's MCP roster into a binding map, creates the session store from the documented schema — writing the header row *through the just-resolved storage binding*, guaranteeing column fidelity — creates the artifact folder root, prompts for the diary location and catalog repo, writes the full config block, and scaffolds the workspace repo (initialized locally with push-to-your-private-org instructions; zero upstream content). It finishes by running `/doctor` plus one end-to-end smoke test: a synthetic `session_type: test` session exercising record append, artifact write, diary append, and read-back. The run ends with either "green: run /page on your next alert" or one specific failure.

**Why this priority**: First-run experience is the SM-2 adoption test (D-15); every other slice assumes a configured workspace exists. P1.

**Independent Test**: Drive the documented team-mode steps as a deterministic script against `bb-mock-mcp` from a fixture empty state: assert the header row lands through the storage binding and matches the documented column list, the config block is written with its version field, the smoke-test session exercises all four operations, and the run is reported green.

**Acceptance Scenarios**:

1. **Given** no config block, **When** `/setup` runs with valid inputs, **Then** it selects team mode by inspection (never a stored done-flag) and performs the full sequence: binding resolution → store creation/validation → artifact root → diary + catalog configuration → config write → workspace scaffold → doctor + smoke test. *(§7.3, D-15)*
2. **Given** store creation, **When** the header row is written, **Then** it is written through the resolved storage binding and matches the slice-3 documented column set exactly. *(§7.3)*
3. **Given** the smoke test, **When** it completes, **Then** a `session_type: test` row exists having exercised append, artifact write, diary append, and read-back — and that row appears in no retrieval candidate set (slice-3 exclusion). *(§7.3; slice-3 spec FR-007)*
4. **Given** an existing Sheet whose header does not match the documented schema, **When** team-mode setup inspects it, **Then** the exact mismatch is reported and nothing is silently re-created. *(§7.3 "validate an existing Sheet's header")*

---

### User Story 2 - `/doctor` links capabilities to whatever tools the team brought (Priority: P1)

A team runs `/doctor` outside any incident, or after changing its MCP roster. For each required operation in the capability manifest, doctor inspects the connected MCP tools' schemas, matches the operation to a concrete tool semantically, confirms the match with a benign probe, and writes the resolved binding map — entries in the exact `capability.operation` → tool-name format the deterministic layer reads — into the workspace configuration, committed with the workspace repo. Required capability unsatisfied → fail loudly naming the gap; optional capability missing → a "reduced features" report listing exactly which features are disabled. Doctor also verifies config validity (store reachable with the expected header row, diary writable, catalog repo parseable), shell-notification round-trip when a shell adapter is configured, and version-seam integrity — config-block and store-schema versions compatible with the installed plugin, reporting the exact migration otherwise.

**Why this priority**: The binding map is the integration artifact of Constitution VII (D-13); without it, every skill's capability reference has nothing concrete to resolve to. Co-P1.

**Independent Test**: Run the documented resolution steps against `bb-mock-mcp`'s schema-registry surface (`describe()`): assert every required operation resolves, the written binding entries use the protocol's exact key format, a roster missing one required operation fails loudly naming it, and a missing optional capability produces the reduced-features list.

**Acceptance Scenarios**:

1. **Given** a roster whose tools cover all required operations, **When** doctor resolves bindings, **Then** the binding map contains one entry per required operation in the `capability.operation` → tool-name format the slice-2 local-state protocol's config table specifies. *(§7.2, D-13; local-state protocol v1 config keys)*
2. **Given** a roster with no tool matching one required operation, **When** doctor runs, **Then** it fails loudly naming the specific unsatisfied operation. *(§7.2)*
3. **Given** a roster missing an optional capability, **When** doctor reports, **Then** the report lists exactly the disabled features (no `code` → no deploy correlation; no `observability` → briefings cite links the agent cannot read itself) and the run is otherwise green. *(§7.2)*
4. **Given** config-block or store-schema versions incompatible with the installed plugin, **When** doctor runs, **Then** it reports the exact migration needed, never a generic failure. *(§2.1, §7.2)*
5. **Given** a committed binding map and a roster whose tools have since changed, **When** doctor re-validates, **Then** the drift is flagged naming the stale entries. *(§7.2 "re-validates per responder and flags drift")*

---

### User Story 3 - A new responder self-heals on their first page (Priority: P2)

A responder clones the team's workspace repo on a new machine. Config, bindings, and store all exist (team scope travels with the repo); what's missing is responder scope — their own tokens, probe results, and the local green stamp. Responder-mode `/setup` provisions tokens, verifies the probes under *this responder's* credentials, and writes the local last-green-doctor stamp (timestamp + plugin version + roster hash) — creating no resources. The stamp is what `/page`'s preflight trusts at 3am: fresh and matching stamp → no probes, straight to the briefing; missing or stale stamp → responder-mode setup auto-runs (seconds, only ever on a first page from a new machine).

**Why this priority**: The stamp is the deterministic artifact that keeps NFR-1's no-probes-at-3am promise honest (D-15); the preflight that consumes it ships in slice 5. P2.

**Independent Test**: From a fixture state with valid team scope and absent responder scope, run responder-mode steps against the mock: assert probes run, the stamp lands with its three fields, no mutating operation touches team resources; then assert a plugin-version or roster-hash change invalidates the stamp.

**Acceptance Scenarios**:

1. **Given** valid team scope and missing responder scope, **When** `/setup` runs, **Then** it selects responder mode by inspection, verifies probes under the responder's own credentials, writes the stamp, and creates no team resources. *(§7.3, D-15)*
2. **Given** a green doctor run, **When** it completes, **Then** the local stamp records timestamp, plugin version, and roster hash — locally only, never committed. *(§7.2, §2.1 "runtime droppings … gitignored")*
3. **Given** a stamp whose plugin version or roster hash no longer matches, **When** the stamp is evaluated, **Then** it is treated as stale. *(§3.2 step 1, D-15)*

---

### User Story 4 - Running setup again is always safe (Priority: P2)

Setup state is derived from artifacts across its two scopes, never from a stored flag. Running `/setup` on a fully configured workspace validates the existing resources — store header, config, bindings, stamp — performs no writes, and reports "already set up" with a doctor summary. Partial states do only what is missing.

**Why this priority**: Idempotence-by-inspection removes "am I set up?" as a question anyone must answer (D-15); it is also what makes the preflight auto-trigger safe. P2.

**Independent Test**: Run the documented setup flow twice against the mock from the same fixture: assert the second run performs zero mutating operations (mock write log unchanged) and reports already-green.

**Acceptance Scenarios**:

1. **Given** an everything-green workspace, **When** `/setup` runs, **Then** it reports already-set-up plus a doctor summary and the mock write log records zero mutating operations for the run. *(§7.3)*
2. **Given** a partial state (e.g. config present, store header missing), **When** `/setup` runs, **Then** only the missing pieces are created and existing resources are validated, never re-created. *(§7.3)*

---

### Edge Cases

- **Two connected tools both match one required operation**: doctor surfaces the candidates and requires an explicit choice — never a silent pick. *(spec-pinned default; design is silent — see Assumptions)*
- **Probe fails under this responder's credentials while the committed binding map is valid**: reported as a responder-scope failure (token/permission), distinct from a team-scope binding failure. *(§7.2, §7.3)*
- **Malformed config block**: surfaced as an explicit repair case, never silently treated as "no config" — team mode re-creating resources over a typo would destroy working state. *(spec-pinned default — see Assumptions)*
- **Shell adapter not configured**: the notify round-trip check is skipped and reported as skipped, not failed. *(§7.2 "if a shell adapter is configured")*
- **Doctor run mid-incident**: the design says run outside incidents; doctor performs no session writes, so an accidental mid-incident run degrades to noise, not damage. *(§3.2, §7.2)*
- **Smoke-test row accumulation**: repeated team-mode smoke tests append additional `session_type: test` rows; all are permanently excluded from retrieval (slice-3), so accumulation is cosmetic. *(§7.3; slice-3 spec FR-007)*
- **Roster hash unchanged but a tool's schema changed server-side**: the stamp stays green until the next doctor run; drift detection is a doctor-run property, not a background watch. *(§7.2; informed default)*

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The plugin MUST ship a capability manifest declaring required capabilities (`storage`, `artifacts`, `diary`, `alerting`) and optional capabilities (`code`, `observability`) with their operations and, for optional ones, the features they enable — derived from operation contract v1 (`tools/bb-mock-mcp/contract.json` is the source; the manifest is its shipped projection). *(§7.1; slice-1 operations.md "Slice 4's shipped manifest/capabilities.json derives from this artifact")*
- **FR-002**: `/doctor` MUST resolve each required operation to a concrete tool by inspecting connected MCP tools' schemas, MUST confirm each match with a benign probe, and MUST write the resolved binding map into the workspace configuration in the exact `capability.operation` → tool-name entry format the slice-2 local-state protocol's config table defines — the map is committed with the workspace repo. *(§7.2, D-13; local-state protocol v1)*
- **FR-003**: `/doctor` MUST verify, per run: probes pass under the current responder's credentials; the shell-notification round-trip when a shell adapter is configured (skipped-not-failed otherwise); config validity — store reachable with the expected header row (the slice-3 schema documentation is the authority), diary writable, catalog repo parseable; and version-seam integrity — config-block and store-schema versions compatible with the installed plugin, reporting the exact migration needed otherwise. *(§7.2, §2.1, D-16)*
- **FR-004**: Doctor report semantics MUST be: any required capability unsatisfied → loud failure naming the specific gap; optional capability missing → green run with a reduced-features list naming exactly what is disabled; dependent features degrade at runtime, never error. *(§7.2)*
- **FR-005**: A green doctor run MUST write the local last-green-doctor stamp — timestamp, plugin version, roster hash — never committed to the repo; the stamp is stale whenever the plugin version or roster hash differs from current state. The `/page` preflight that trusts it ships in slice 5; this slice defines the stamp's content and staleness rules. *(§7.2, §3.2 step 1, D-15, §2.1)*
- **FR-006**: `/setup` MUST derive its mode from artifact state — team scope (config block, store header, artifact root, binding map; travels with the workspace repo) and responder scope (tokens, probe results, local stamp; per person per machine, never committed) — and MUST NOT use a stored done-flag. *(§7.3, D-15)*
- **FR-007**: Team mode MUST: resolve bindings; create the session store from the slice-3 documented schema, writing the header row through the just-resolved storage binding, or validate an existing store's header reporting exact mismatches; create the artifact folder root; prompt for diary location and catalog repo; write the full config block including its version field; scaffold the workspace repo with zero upstream content and push-to-private-org instructions; and finish with `/doctor` plus an end-to-end smoke test — a `session_type: test` session exercising record append, artifact write, diary append, and read-back. *(§7.3, §2.1, D-16)*
- **FR-008**: Responder mode MUST provision and verify this responder's tokens via probes and write the stamp, creating no team resources; the mode is also what `/page`'s preflight auto-runs on a first page from a new machine (the trigger ships in slice 5). *(§7.3, §3.2 step 1)*
- **FR-009**: Running `/setup` on an already-green workspace MUST validate and report — zero mutating operations — and on partial state MUST do only what is missing; running twice is always safe. *(§7.3)*
- **FR-010**: Command prose MUST reference capabilities and operations only; concrete MCP server names may appear in exactly one shipped location — the recommended-roster template — and the store-template document is reference documentation, not the setup path. *(§3.1 design rule, §7.3; Constitution VII)*
- **FR-011**: Every requirement above MUST be exercised by hermetic contract tests against `bb-mock-mcp`: binding resolution against the mock's schema-registry surface (`describe()`, built by slice 1 for exactly this), setup create-vs-validate paths, smoke-test exclusion from retrieval, doctor failure modes (required-missing loud, optional-missing reduced), and stamp lifecycle — asserting on artifacts (rows, write log, stamp fields), never prose, with no credentials and no network. *(design §10 layer 2; slice-1 FR-011; Constitution VIII)*
- **FR-012**: This slice ships no storage code: setup and doctor write through resolved bindings only; deliverables are command prose, the JSON manifest, the two templates, and tests. *(Constitution I)*

### Key Entities

- **Capability manifest**: The shipped declaration of required/optional capabilities and their operations (`bb.capabilities.v1`), projected from operation contract v1.
- **Binding map**: The doctor-resolved `capability.operation` → tool-name entries in the workspace configuration; the integration artifact (D-13); read by the slice-2 deterministic layer.
- **Green stamp**: Local, uncommitted record of the last green doctor run — timestamp, plugin version, roster hash; the artifact `/page` preflight trusts.
- **Config block**: The team's workspace configuration (store/diary/catalog locations, versions, bindings); team scope, committed.
- **Smoke-test session**: A `session_type: test` session created by team-mode setup; exercises the four write/read paths; permanently excluded from retrieval by slice-3 conventions.
- **Schema-registry surface**: The mock's `describe()` output (slice-1 FR-011) — the hermetic stand-in for live MCP tool-schema inspection.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every functional requirement maps to at least one passing hermetic contract test; the suite is green on every commit via the standard verify gate.
- **SC-002**: Against a fixture roster covering all required operations, binding resolution resolves 100% of them and every written entry parses under the protocol's `capability.operation` key format; against a fixture roster missing one required operation, the run fails loudly naming that operation in 100% of runs.
- **SC-003**: Create-vs-validate: from an empty store the created header matches the documented column list exactly; from a correct existing store, validation passes with zero writes; from a mismatched store, the exact mismatch is reported with zero writes — each in 100% of simulated runs.
- **SC-004**: The smoke-test session lands with `session_type: test` having exercised all four paths, and appears in 0% of retrieval candidate sets.
- **SC-005**: A second `/setup` run over an already-green fixture performs zero mutating operations (mock write log unchanged) in 100% of runs.
- **SC-006**: Stamp lifecycle: a green run writes all three stamp fields; a changed plugin version or roster hash is detected as stale in 100% of cases.
- **SC-007**: In simulation, a new team reaches a green report in a single `/setup` invocation given valid inputs — no manual intermediate steps.

## Assumptions

- **Semantic matching is agent-performed** (D-7): the quality of schema-to-operation matching is probabilistic and not unit-testable; what the tests pin deterministically is the resolution *protocol* — the registry surface consumed, the binding-entry format written, the probe-confirmation step, and the failure modes. *(Constitution II split: convention carries behavior, tests verify the artifact)*
- **Ambiguous multi-match** (two tools matching one operation) is surfaced for an explicit choice — spec-pinned default; the design is silent.
- **Benign probes are read-shaped**: doctor probes use read operations (e.g. reading records with a filter, reading recent diary entries); mutating operations are verified by schema match at doctor time and exercised end-to-end only by setup's smoke test — spec-pinned default; the design says "benign probe call" without defining benignity for mutating operations.
- **Malformed config block** is a repair case surfaced explicitly, not treated as absent — diverging deliberately from the slice-2 hooks' fail-open reading of malformed config (a guardrail must not brick a session; an onboarding wizard must not destroy state).
- **Roster hash input** (which roster facts are hashed) and the **stamp's on-disk location** are pinned at plan time; the stamp lives with the gitignored runtime droppings per §2.1.
- **Migration execution is out of scope**: doctor *reports* the exact migration (§2.1's example: "schema v1→v2 adds a column; run `/setup --migrate`"); executing migrations is deferred until a second schema version exists.
- **`/page` preflight is slice 5**: this slice defines the stamp artifact and staleness rules the preflight trusts; the trigger logic is slice-5 scope.
- **Shell round-trip depends on slice 9's adapter**: tests cover the configured-and-answering and not-configured (skip) paths through a fixture adapter surface; the real adapter ships in slice 9.
- **Diary and catalog prompts** accept URLs/locations without validation beyond doctor's reachability checks; deeper catalog parsing is slice 7's scope.
