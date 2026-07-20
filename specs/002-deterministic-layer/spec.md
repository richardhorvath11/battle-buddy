# Feature Specification: Deterministic Layer

**Feature Branch**: `002-deterministic-layer`

**Created**: 2026-07-20

**Status**: Draft

**Input**: Slice 2 of the battle-buddy MVP (design `bb-technical-design.md` §3.4, §3.5, §4, §5.2, §5.4; decisions D-1, D-11, D-12, D-14, D-17, D-20; Constitution II, III, VI): the shipped deterministic components — the guardrail deny hook, the tool-trace/budget/tripwire hook, the session-guard hook, and the `bb-fingerprint` and `bb-validate` helpers. These are the code backstops behind every convention the product trusts the model to follow.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Destructive actions are blocked before they run (Priority: P1)

A responder's investigation agent — possibly influenced by injected text in alert payloads — attempts a dangerous command (destroying infrastructure, scanning credentials after an auth error, retrying with verification disabled). The deny hook blocks the call outright before execution, independent of any approval prompt, and tells the agent why. A broken or crashing hook never bricks the session: on its own failure it allows the call (fail open) — safety must not make the tool unusable at 3am.

**Why this priority**: This is the outermost deterministic guarantee of Constitution III; every other guardrail layer assumes it exists. Documented real-world agentic misbehaviors are the concrete threat model.

**Independent Test**: Run the misbehavior fixture suite through the hook: every fixture representing a documented dangerous pattern is blocked with a reason; every benign fixture passes; a malformed input or internal hook error results in allow (fail open) — all without any agent or network involved.

**Acceptance Scenarios**:

1. **Given** a tool call matching a deny class (destructive filesystem/cluster/cloud operation, credential scanning after an auth error appears in recent trace context, verification-skipping retry), **When** the hook evaluates it, **Then** the call is blocked and the block message names the matched pattern class.
2. **Given** a benign tool call listed in the benign near-miss corpus, **When** the hook evaluates it, **Then** it is allowed with no side effects. (Corpus membership rule: a near-miss is benign when the *executed action* is safe and the dangerous pattern appears only as data — a quoted string argument, URL, or commit-message content. Over-match beyond the corpus is acceptable collateral per Constitution III; each false positive met in practice is *deliberately* added to the corpus, making the corpus the decided boundary.)
3. **Given** malformed input, missing fields, or an unexpected internal error in the hook itself, **When** the hook runs, **Then** it allows the call (fail open) — and the failure is visible in the hook's own diagnostics, never silent *and* blocking.
4. **Given** a new documented agentic misbehavior is added as a fixture, **When** the suite runs, **Then** the hook must block it or the suite fails — the fixture corpus is the regression gate.

---

### User Story 2 - Checkpoints are validated before they persist (Priority: P1)

A component about to persist a triage verdict or ledger checkpoint runs `bb-validate` on the candidate JSON. The validator checks both schema shape (per version tag `bb.verdict.v1` / `bb.ledger.v1`) and the semantic invariants the product's headline behaviors depend on: every non-`fresh` hypothesis carries VALIDATED/INVALIDATED status, ≥3 live hypotheses with ≥1 `fresh` whenever the ledger's `phase` indicates active deep-dive investigation (FR-006), and every evidence entry is a `{url, excerpt}` pair. On failure it emits a machine-readable error list the caller can feed back to the producing agent; it never mutates input and it renders a verdict, not a judgment call.

**Why this priority**: Constitution VI says these invariants are "enforced by `bb-validate`, not by convention" — without this tool, the validation discipline (SM-4) is prose. Co-P1 with Story 1.

**Independent Test**: Run the validator against a corpus of valid and invalid documents (one seeded violation per schema rule and per semantic invariant): exit code and error list exactly match expectations; valid documents pass byte-for-byte unmodified.

**Acceptance Scenarios**:

1. **Given** a well-formed verdict or ledger document, **When** validated, **Then** exit 0 and no output (or an explicit pass summary) — the document is untouched.
2. **Given** a document violating a schema rule (missing field, wrong type, unknown version tag) or a semantic invariant (unvalidated `recall` hypothesis, two live hypotheses or no `fresh` hypothesis while `phase` indicates deep-dive (FR-006), prose-only evidence), **When** validated, **Then** non-zero exit and a machine-readable error list naming each violated rule and its location in the document.
3. **Given** a document with multiple violations, **When** validated, **Then** all violations are reported in one pass (no fix-one-rerun loops).
4. **Given** any input at all (including non-JSON), **When** validated, **Then** the validator terminates with a decisive exit code — it never hangs, crashes uncleanly, or partially reports.

---

### User Story 3 - One fingerprint, everywhere, forever (Priority: P1)

Every component that computes a session fingerprint — triage retrieval, session close, future tier-1 ingestion — calls `bb-fingerprint` and gets an identical result for identical inputs: same normalization (case, whitespace, ID/UUID/timestamp/hostname placeholder substitution), same hash truncation, on every supported platform and Python version. The normalization rules are versioned; changing them requires a new version and is loud, never silent — because silent drift breaks exact-match recall, the retrieval path the whole tier-0 memory flywheel rides on.

**Why this priority**: The fingerprint carries the retrieval load embeddings would otherwise carry (design §5.2); recall correctness is a headline product property. P1.

**Independent Test**: Run the golden corpus (input pairs → expected fingerprints, including unicode, messy whitespace, embedded UUIDs/timestamps/IPs/hostnames, and near-collision cases) on the oldest and newest supported Python versions: 100% match, both directions — and a deliberately altered normalization rule fails the corpus.

**Acceptance Scenarios**:

1. **Given** a service name and alert type, **When** fingerprinted twice anywhere, **Then** results are identical 16-character outputs.
2. **Given** alert-type text containing volatile tokens (UUIDs, hex ids, large integers, ISO timestamps, hostnames/IPs), **When** normalized, **Then** volatile tokens collapse to placeholders so repeat alerts fingerprint identically, while distinct service/alert combinations stay distinct.
3. **Given** the documented rules and the implementation, **When** the golden corpus runs, **Then** every case matches — the corpus is the executable form of the rules document.

---

### User Story 4 - The investigation leaves a complete, bounded trace (Priority: P2)

While agents investigate, the trace hook records every tool call as one structured line in the session's local trace file — from every agent in the session, deterministically, with no reliance on model cooperation. The same hook enforces the triage agent's turn cap (past the configured cap, further tool calls are denied with "budget exhausted — emit your verdict now") and raises the injection tripwire: when a result from an untrusted-capability tool matches instruction-shaped heuristics, it appends an advisory reminder that the content is data, and logs the event for post-incident review.

**Why this priority**: The trace is the audit log's raw material and the timeline's source (D-5, D-12); the turn cap is NFR-1's deterministic bound (D-17); the tripwire is layer 4's honest, advisory mechanism (D-20). All valuable, none blocking slice 3's conventions work — P2.

**Independent Test**: Feed the hook a scripted sequence of tool-call events: the trace file reproduces the sequence exactly; the (N+1)th triage tool call is denied with the budget message; a fixture result containing instruction-shaped text triggers exactly one advisory injection and one trace log entry; benign results trigger none; with no binding map present, the same instruction-shaped fixture triggers **no advisory and exactly one disabled-tripwire logged notice** (FR-010 degraded mode).

**Acceptance Scenarios**:

1. **Given** any sequence of tool calls across agents, **When** the session proceeds, **Then** the trace file contains one ordered structured line per call — no gaps, no reordering.
2. **Given** the triage agent at its configured turn cap, **When** it attempts another tool call, **Then** the call is denied with the emit-your-verdict message and budget exhaustion is trace-logged; downstream no-strong-signal handling (PRD FR-5f(a), via design §3.4) rides the verdict's own `budget_spent`/`no_strong_signal` fields (design §5.4) — the hook introduces no separate marker.
3. **Given** a tool result from an untrusted capability containing instruction-shaped content ("ignore previous instructions", "run the following", base64 blobs, tool-call syntax), **When** the hook processes it, **Then** an advisory data-not-instructions reminder is appended and the event is trace-logged; results without such content pass untouched.
4. **Given** hook failure of any kind, **When** a tool call occurs, **Then** the call proceeds (fail open) — trace completeness degrades before availability does, and the failure is visible in diagnostics.

---

### User Story 5 - A session cannot silently lose its record (Priority: P2)

When a session that opened a session record ends, the session guard checks the local marker: if the record write was never confirmed (marker uncleared), it blocks/warns loudly — "session row not persisted — run /close" — instead of letting the session die silently. It also copies the runtime's native transcript into the session's local artifact staging area, so close-time upload is mechanical.

**Why this priority**: The must-not-lose write (FR-4b) gets its deterministic detector here (D-11); transcript capture makes the audit log real (D-12). Depends on conventions defined in slice 3 for full integration, so P2 — but the mechanism is testable now against fixture marker states.

**Independent Test**: Run the guard against fixture marker states (absent / open-unconfirmed / open-confirmed-never-closed / cleared) plus fixture transcript paths (present / missing / unreadable): warnings fire on exactly the two uncleared states, silence on the other two, and transcript staging behaves per scenario — no session or agent involved.

**Acceptance Scenarios**:

1. **Given** a session marker showing an opened-but-unconfirmed record, **When** the session ends, **Then** the guard emits the loud unpersisted-row warning/block with the exact remedial instruction.
2. **Given** a marker whose open-time record write was confirmed but which was **never cleared by a confirmed close** (the model skipped `/close` — the canonical D-11 case, design §9), **When** the session ends, **Then** the guard warns/blocks just as loudly: the trigger is "marker present and not cleared," regardless of open-write confirmation state.
3. **Given** a cleared marker (or no marker — no session was opened), **When** the session ends, **Then** the guard stays silent and the session ends normally.
4. **Given** a transcript path in the hook input, **When** the session ends, **Then** the transcript file is copied to the session's staging area; a missing/unreadable transcript degrades to a logged notice, never a session-ending failure.
5. **Given** a session directory lacking the workspace config block, **When** a session-scoped hook event fires, **Then** the guard emits the run-from-the-workspace-repo warning (design §2.1) without blocking.

---

### Edge Cases

- Malformed or truncated JSON on stdin (any hook): fail open, diagnostics visible (US1 AS-3 generalizes to all three hooks).
- Deny patterns appearing inside legitimate content (a quoted command in a commit message, a URL containing "rm -rf"): over-match is acceptable *outside the benign corpus* (Constitution III); the corpus pins the calls that MUST pass per US1 AS-2's membership rule, so over-matching stays deliberate — the corpus is the boundary, and narrowing over-match is done by growing the corpus, never by loosening patterns ad hoc.
- Fingerprint inputs that are empty, whitespace-only, or entirely volatile tokens after normalization: deterministic documented outputs (never an exception), flagged so callers can apply the resolution ladder (design §5.2).
- Validator given a checkpoint with `"schema_valid": false` already set (a previously flag-persisted document): validates like any other; the flag is caller metadata, not a validator bypass.
- Trace file grows large during a long incident: appends stay O(1) — the hook never reads or rewrites the file it appends to.
- Concurrent tool calls hitting the trace hook (parallel subagents): every call lands exactly once; ordering is by completion observed by the hook, and `seq` never duplicates.
- Turn-cap configuration absent: a documented default applies (no crash, no unlimited budget).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: All five components MUST be implemented in Python 3 standard library only, compatible with Python 3.9+, with zero installation steps beyond the plugin itself. *(D-1; Constitution Platform Constraints)*
- **FR-002**: All five components MUST behave as pure functions of (input payload, local state directory) → (exit code, output) with no network access and no reads beyond three permitted sources: the session's local state, paths explicitly named in the input payload (e.g. the runtime's transcript path, FR-012), and the workspace config block (turn-cap config FR-009, binding map FR-010, config-presence check FR-015 — a fixture file in tests) — hermetically testable by the slice-1 unit layer. *(Design §10, D-10; slice-1 FR-007)*
- **FR-003**: The deny hook MUST block tool calls matching the documented deny classes — destructive filesystem, destructive cluster/cloud, credential scanning following auth errors, verification-skipping retries — reporting the matched class, and MUST allow everything else. *(Design §3.5 layer 1; FR-7a)*
- **FR-004**: Every hook MUST fail open: any internal error, malformed input, or unexpected condition results in allowing the call/session to proceed, with the failure visible in diagnostics. A hook MUST never be the reason a session cannot continue. *(Constitution III)*
- **FR-005**: The misbehavior fixture corpus MUST be the deny hook's regression gate: each documented real-world agentic misbehavior is a fixture the hook must block; benign near-miss fixtures must pass; the suite fails on any divergence. *(Design §3.5; FR-7a)*
- **FR-006**: `bb-validate` MUST validate documents against their embedded version tag (`bb.verdict.v1`, `bb.ledger.v1`): schema shape plus the semantic invariants — non-`fresh` hypotheses carry validation status; ≥3 live hypotheses and ≥1 `fresh` whenever the ledger's `phase` field indicates active deep-dive investigation (the concrete `phase` enumeration is pinned at plan time against the design §5.4 example) — and evidence entries are `{url, excerpt}` pairs — reporting all violations in one pass as a machine-readable list, exiting non-zero on any violation, and never modifying input. *(Design §5.4, D-14; Constitution VI)*
- **FR-007**: `bb-fingerprint` MUST implement the versioned normalization rules and 16-hex-character truncated hash of design §5.2 exactly, deterministically across supported platforms and Python versions; the golden corpus is the executable form of the rules and MUST fail on any behavioral change without a version bump. *(Design §5.2, D-4)*
- **FR-008**: The trace hook MUST append one structured line per tool call (all agents) to the session's local trace file: sequence number, agent, tool, capability where known, timestamp, payload summary, and **outcome** (success, or an error class — including `auth_error` for 401/403-shaped results) — append-only, no gaps or duplicates. The outcome field is what makes the deny hook's credential-scanning class detectable from recent trace context (FR-003; design §3.5). *(D-12; design §5.3)*
- **FR-009**: The trace hook MUST enforce the configured triage turn cap by denying further tool calls past the cap with the budget-exhausted/emit-your-verdict message and trace-logging the budget exhaustion; it introduces **no separate marker** — downstream no-strong-signal handling (PRD FR-5f(a), via design §3.4) rides the verdict's own `budget_spent`/`no_strong_signal` fields (design §5.4). Absent configuration, a documented default cap applies. *(D-17; design §3.4)*
- **FR-010**: The trace hook MUST implement the injection tripwire: results from untrusted-capability tools matching the documented instruction-shaped heuristics trigger one advisory data-not-instructions reminder and one trace log entry; the mechanism is advisory only and documented as probabilistic. Tool→capability classification comes from the binding map (design §3.3, §7.2 — written by slice 4's `/doctor`); the untrusted set v1 is `alerting` and `observability` (design §3.3 also names "ticket-shaped tools," but the v1 operation contract defines no ticket capability the binding map could classify — the plan MUST either note this deferral or define the classification; the untrusted set grows with the contract, not ad hoc). This slice defines the binding-map read protocol; when no binding map is present the tripwire degrades to disabled with a logged notice (fail-open spirit). *(D-20; design §3.3, §3.5 layer 4)*
- **FR-011**: The session guard MUST warn/block loudly with the remedial instruction at session end whenever a session marker is **present and not cleared by a confirmed close** — covering both the open-unconfirmed state and the open-confirmed-but-never-closed state (the skipped-`/close` case, design §9) — and MUST stay silent only when no marker exists or the marker was cleared. *(D-11; design §4; Constitution II)*
- **FR-012**: The session guard MUST copy the runtime-provided transcript into the session's local staging area at session end, degrading to a logged notice on failure. *(D-12; design §5.3)*
- **FR-013**: The marker and trace file formats, locations, and lifecycle MUST be documented as a versioned local-state protocol — slice 3's conventions and slice 5's commands build on them without reverse-engineering the code. Acceptance: the protocol document exists, carries a version, and every format/location assertion in it is exercised by at least one unit test. *(Design D-6 rationale: structured contracts, not prose conventions)*
- **FR-014**: Every component MUST ship with its unit tests in the same change, using the slice-1 table-driven fixture pattern. *(Constitution VIII)*
- **FR-015**: The session guard MUST emit a non-blocking run-from-the-workspace-repo warning when session-scoped hook events fire in a directory lacking the workspace config block. *(Design §2.1: "the session-marker hook warns if the config block is absent")*

### Key Entities

- **Hook input payload**: The runtime's hook-event JSON (tool name, input, session/agent identity, transcript path where provided) — read-only input to every hook.
- **Deny class**: A named category of dangerous patterns with its match rules and fixture set; the four classes above are v1.
- **Misbehavior fixture**: A recorded hook payload representing one documented agentic misbehavior (or a benign near-miss), with the expected verdict.
- **Session marker**: Local file recording session identity and record-write confirmation state; created at open, updated on confirmed open-time write, cleared **only** by a confirmed close — the guard's warning trigger is "present and not cleared" (FR-011).
- **Trace line**: One structured record per tool call: `{seq, agent, tool, capability?, at, summary, outcome}` — `outcome` ∈ success or an error class incl. `auth_error` (FR-008).
- **Verdict/ledger documents**: JSON documents tagged `bb.verdict.v1` / `bb.ledger.v1` per design §5.4.
- **Golden fingerprint corpus**: Input → expected-fingerprint pairs, the executable form of the §5.2 normalization rules.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of misbehavior fixtures are blocked and 100% of benign near-miss fixtures pass, on every CI run — a regression in either direction fails the build.
- **SC-002**: Hook overhead is imperceptible in use: each hook completes well under 100ms per invocation on a typical laptop (they run on every tool call; latency here is responder-facing).
- **SC-003**: The fingerprint golden corpus passes 100% on both ends of the CI version matrix — the 3.9 floor (design D-1) and the matrix's newest version (3.12 at time of writing) — and a seeded normalization change without a version bump fails it.
- **SC-004**: The validator corpus (≥1 violation case per schema rule and per semantic invariant, plus valid documents) is classified 100% correctly, with all violations of a multi-violation document reported in a single pass.
- **SC-005**: A scripted 100-call multi-agent session yields a trace file with exactly 100 lines, correctly ordered, with zero duplicates — and the run with the turn cap set to N denies call N+1.
- **SC-006**: Zero third-party imports across all five shipped components, verified mechanically in CI (the packaging/import check extends slice 1's boundary test).
- **SC-007**: Fail-open holds under fault injection: every seeded hook-internal failure (malformed stdin, unreadable state, thrown exception) results in the call/session proceeding, 100% of the fault corpus.

## Assumptions

- The runtime's hook events (pre-tool, post-tool, session-end) provide tool name, input, agent identity, and transcript path per current Claude Code hook documentation; exact field names are a plan-level concern, and hooks tolerate absent optional fields (FR-004 covers surprises).
- The turn cap's configuration source is the workspace config block (design D-10); this slice defines the read protocol, slice 4's `/setup` writes it.
- The deny hook does not implement an inline named-reason bypass in v1 — the design specifies outright blocking for deny classes (FR-7a); a push-gate-style bypass pattern (family-meals lineage) is a *dev-workflow* gate, distinct from these runtime guardrails, and is deferred to a later dev-workflow change. AGENTS.md's pre-flight-gate wording is amended in this same PR to match (it previously scheduled the push-gate into this slice).
- Auth-error context for the credential-scanning deny class comes from the session's own trace file — specifically recent lines' `outcome` field (`auth_error`, FR-008) — not from external state, keeping the hook hermetic. This creates an explicit ordering dependency: the deny class degrades gracefully (pattern-matching only, no auth-context trigger) when the trace file is absent.
- The session marker/trace protocol documented here (FR-013) is v1 and may be extended (never silently changed) by later slices.
- Instruction-shaped heuristics (FR-010) start with the documented v1 list; extending the list is a fixture-plus-rule change, not a redesign.
