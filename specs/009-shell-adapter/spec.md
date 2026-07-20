# Feature Specification: Shell Adapter

**Feature Branch**: `009-shell-adapter`

**Created**: 2026-07-20

**Status**: Draft

**Input**: Slice 9 of the battle-buddy MVP (design `bb-technical-design.md` §6.3, §3.1, §2 shell layer; decisions D-2, D-9; PRD FR-3, FR-9, FR-22–24, FR-26, R-1, R-2; Constitution Platform Constraints, III, VII): the single-screen surface — the `bb-shell` CLI shim (shipped code, Python 3 stdlib), the cmux backend, and first-class degraded mode — with unit tests per the slice-1/2 pattern (fake socket). This is the slice whose deliverable is real shipped code beyond slice 2; the shim's documented interface doubles as the adapter spec for any future shell (D-2).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One screen at 3am, or plain links — both first-class (Priority: P1)

With a shell adapter configured, session start creates a session-named workspace: the agent terminal pane plus browser panes for the service's dashboards; evidence deep-links drive panes into view; notifications fire on attention and approval needs. Without one — non-Mac responders, or teams that never configure it — every call becomes a printed link or message in the plain terminal, and *every feature works*. Degraded mode is a first-class path, never an error state.

**Why this priority**: The single-screen experience is the launch differentiator (D-9), and FR-26's degraded promise is what keeps it from becoming a platform lock. P1.

**Independent Test**: Invoke every interface verb under `shell: none` and assert the printed-link/message output for each; invoke under a fake-socket cmux backend and assert the protocol messages sent — both hermetically, no real shell.

**Acceptance Scenarios**:

1. **Given** `battleBuddy.shell: none` (or the key absent), **When** any verb runs, **Then** the output is a printed link or message conveying the same information, exit success — degraded mode is selected and fully functional. *(§6.3 degraded; FR-26; config absent = degraded, see Assumptions)*
2. **Given** `battleBuddy.shell: cmux`, **When** `open-pane` runs with a workspace argument, **Then** the fake socket receives the workspace-creation traffic for a session-named workspace. *(§6.3 cmux; FR-3, FR-22)*
3. **Given** a configured backend, **When** `navigate-pane` runs, **Then** the addressed pane is driven to the URL (fake-socket assertion) — the evidence deep-linking primitive. *(§6.3; FR-9)*
4. **Given** `notify` at each level (`info`, `warn`, `approval`), **When** invoked, **Then** the level reaches the backend (or prints, degraded) — the attention/approval channel. *(§6.3)*

---

### User Story 2 - A dead shell never takes the investigation with it (Priority: P1)

Mid-session, the cmux socket dies — the app crashed, the socket file vanished, a write timed out. Every `bb-shell` call fails soft: the command automatically falls back to degraded output (the link or message prints instead), exits successfully, and the investigation continues unaffected. A shell failure must never brick a session — the adapter covers *availability*, and its failure mode is the degraded path, not an error.

**Why this priority**: R-2 is the risk the design retires with exactly this behavior (§9's fail-soft row); the Platform Constraints make degraded mode the first-class fallback, and Constitution III's guardrail fail-open rule extends here by analogy — the binding authorities are the former two. Co-P1.

**Independent Test**: Run each verb against fault-injected fake sockets — connection refused, timeout, mid-write death — and assert: degraded output produced, exit code success, the failure visible in diagnostics; no fault case exits nonzero or produces silence.

**Acceptance Scenarios**:

1. **Given** a socket connection refused or absent, **When** any verb runs under `shell: cmux`, **Then** the call falls back to degraded output, exits success, and the fallback is noted in diagnostics. *(§6.3, §9 R-2 row; Constitution III fail-soft)*
2. **Given** a mid-write socket death, **When** the verb runs, **Then** same fallback — no hang, no partial-failure error surfaced to the caller. *(§9 R-2)*
3. **Given** repeated failures in one session, **When** calls continue, **Then** each falls back identically — the shim is stateless about backend health; no lockout, no retry storm. *(spec-pinned default — see Assumptions)*

---

### User Story 3 - The responder's SSO is theirs alone (Priority: P2)

Browser panes render third-party tools with the responder's own SSO sessions. The harness's role ends at pane creation and navigation — it never reads, injects, or manages those sessions or their credentials. The two credential paths (responder SSO in panes; agent MCP tokens) never cross, and `bb-shell` touches only URLs and pane identities, never page content or auth state.

**Why this priority**: FR-24 is a security boundary, not a feature; the shim's interface makes it structural (nothing in the interface can express credential access). P2 because it's a property to preserve, not machinery to build.

**Independent Test**: Interface-surface inspection: the verb set and argument shapes admit no credential, cookie, or content operation; the cmux protocol traffic the shim emits contains URLs and pane/workspace identifiers only (fake-socket capture assertion).

**Acceptance Scenarios**:

1. **Given** the complete interface, **When** inspected, **Then** no verb or argument expresses credential, cookie, session-state, or page-content access — the boundary is structural. *(§6.3, FR-24; §2 two-paths rule)*
2. **Given** any captured protocol traffic from the test suite, **When** scanned, **Then** it contains only workspace/pane identifiers, URLs, messages, and levels. *(FR-24)*

---

### User Story 4 - Any future shell slots in behind the same small verb set (Priority: P3)

The shim's documented interface — `open-pane`, `navigate-pane`, `notify`, with backend selection by configuration — is the adapter contract: a future shell (a different multiplexer, an IDE, a web dashboard) integrates by implementing the same verbs' semantics behind the shim, with zero changes to any command or skill. Commands and skills invoke only `bb-shell`; nothing in the core knows which shell answers.

**Why this priority**: D-2's rationale — the interface doubles as the spec for any future shell. Documentation property; P3.

**Independent Test**: The interface document exists, defines each verb's arguments and semantics backend-independently, and the mechanical scan finds no shell-product name in any command/skill deliverable of other slices (they say `bb-shell`, never the backend).

**Acceptance Scenarios**:

1. **Given** the interface documentation, **When** read, **Then** each verb's arguments, semantics, degraded behavior, and failure behavior are defined without reference to any concrete backend. *(D-2; FR-22)*
2. **Given** the plugin's commands and skills (other slices' deliverables), **When** scanned, **Then** shell interaction appears only as `bb-shell` invocations — no backend names outside this slice's backend documentation. *(FR-22; Constitution VII's spirit applied to shells)*

---

### Edge Cases

- **Unknown verb or malformed arguments**: usage error with nonzero exit — the one intentional failure mode; argument errors are caller bugs (slice-5 commands), not availability events, and must be loud. *(spec-pinned default — see Assumptions)*
- **Unknown `battleBuddy.shell` value** (e.g. a typo, or a future backend not in this build): treated as `none` with a diagnostic notice — fail-soft toward degraded, matching the slice-2 config posture (malformed config = absent, noticed). *(informed default; local-state protocol config precedent)*
- **`open-pane` with a command instead of a URL**: supported per the interface (`<url|command>`) — the agent terminal pane itself is opened this way; degraded mode prints the command it would have run. *(§6.3 interface)*
- **`navigate-pane` for a pane that doesn't exist**: backend reports it; the shim falls back to printing the URL (the responder can still click) — soft, never a session error. *(informed default from the fail-soft posture)*
- **Workspace already exists at `open-pane --workspace`** (restart/rejoin): the backend reattaches rather than duplicating — workspaces survive restarts by design; the shim passes the session ID through and the backend owns reattach semantics. *(§6.3 "workspaces survive restarts", FR-3)*
- **Notification when no one is watching** (degraded, redirected output): notify prints to the terminal; delivery beyond that is out of scope — the transcript remains the record. *(§9 R-1 row: "notifications inline")*
- **Concurrent bb-shell invocations** (parallel agents citing evidence): each invocation is an independent process with its own socket connection; ordering is the backend's; no shared state in the shim. *(spec-pinned default — the shim is stateless)*

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The shipped `bb-shell` shim MUST implement the documented adapter interface: the three §6.3 verbs — `open-pane <url|command> [--workspace <session-id>]`, `navigate-pane <pane> <url>`, `notify <message> --level <info|warn|approval>` — plus a workspace-close operation, whose existence this spec pins as a recorded D-2 interface addition (slice-5's close flow requires it and §6.3's three-verb block cannot express it — the design's own gap; name and exact semantics at plan time, state restorable per FR-3; see Assumptions). All in Python 3 stdlib only, per the shipped-code platform constraint. *(§6.3 interface, §4 close diagram, §3.1, D-2; Constitution Platform Constraints)*
- **FR-002**: Backend selection MUST come from workspace configuration (`battleBuddy.shell`: `cmux` | `none`): an absent key selects degraded mode *silently* — absence is the documented normal state for shell-less teams, not an anomaly — while an unrecognized value selects degraded mode *with* a diagnostic notice (a probable typo must be visible); commands and skills invoke only `bb-shell` and never know the backend. *(§6.3, D-2, FR-22; notice scoping — see Assumptions)*
- **FR-003**: The degraded backend MUST render every verb as a printed link or message conveying the same information, exit success — full function in a plain terminal, the non-Mac path, never an error state. *(§6.3 degraded, FR-26, R-1)*
- **FR-004**: The cmux backend MUST speak the backend's socket API to: create session-named workspaces with the agent terminal pane and dashboard browser panes at open, drive panes to URLs for evidence deep-linking, and deliver leveled notifications; workspaces survive restarts, with reattach on re-open of an existing session workspace. Workspace composition is caller-driven: the first `open-pane --workspace` call creates the session-named workspace and subsequent calls add panes to it — §6.3's multi-pane session-start outcome is achieved by the open flow issuing one call per pane. *(§6.3 cmux; FR-3, FR-9; socket protocol specifics pinned at plan time — see Assumptions)*
- **FR-005**: Every backend call MUST fail soft: on any socket failure (absent, refused, timeout, mid-write death) the shim automatically produces the degraded output for that verb, exits success, and notes the fallback in diagnostics — a shell failure never surfaces as a session error. The only nonzero exits are usage errors (unknown verb, malformed arguments), which must be loud. *(§9 R-2 row; Constitution Platform Constraints; III's fail-open rule by analogy; usage-error pin — see Assumptions)*
- **FR-006**: The shim MUST be structurally incapable of credential access: the interface admits no credential, cookie, session-state, or page-content operation; emitted protocol traffic carries only workspace/pane identifiers, URLs, messages, and levels — the responder's SSO sessions are never touched. *(§6.3, FR-24; §2 two-paths rule)*
- **FR-007**: The interface MUST be documented as the backend-independent adapter contract — per-verb arguments, semantics, degraded behavior, failure behavior — such that a future shell integrates behind the shim with zero core changes. *(D-2; FR-22–23)*
- **FR-008**: Unit tests MUST cover, hermetically per the slice-1/2 pattern: argument parsing and dispatch as pure functions; cmux protocol framing against a fake socket; degraded output for every verb; fail-soft fallback for every fault class (refused, absent, timeout, mid-write death — the fault-fixture pattern); config selection (`cmux` | `none` | absent | unrecognized); and the credential-surface scan of captured traffic — no real shell, no network, tests in the same change. *(design §10 layer 1 "bb-shell (fake socket)"; Constitution VIII)*
- **FR-009**: The shim MUST behave as a pure function of (arguments, config, socket behavior) → (exit code, output, protocol traffic) — no persistent state, no reads beyond config and its socket — keeping it unit-testable and keeping repeated failures independent. (The slice-2 precedent's no-network clause maps here to no-I/O-beyond-the-backend-socket, which the tests replace with the fake; §10 states the purity property of hooks and lists `bb-shell (fake socket)` in the same coverage table — the framing is adapted, not quoted.) *(design §10 layer 1, adapted; slice-2 FR-002 precedent)*

### Key Entities

- **`bb-shell` shim**: The shipped CLI — three verbs, config-selected backend, fail-soft; the only shell surface any other slice touches.
- **Adapter interface document**: The backend-independent contract (D-2) — the spec any future shell implements.
- **cmux backend**: The v1 socket-API implementation; protocol specifics pinned at plan time against the real API.
- **Degraded backend**: The print-everything implementation; first-class, default, and the universal fallback.
- **Fake socket**: The test double for the backend socket — protocol capture plus fault injection.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every functional requirement maps to at least one passing hermetic unit test; the suite is green on every commit via the standard verify gate.
- **SC-002**: 100% of verbs produce correct degraded output under `shell: none`, absent config, and unrecognized config — three selection paths, one behavior (plus the notice on unrecognized).
- **SC-003**: 100% of fault-fixture cases (refused, absent, timeout, mid-write death × every verb) produce degraded output with exit success and a diagnostic note; zero fault cases exit nonzero or hang.
- **SC-004**: 100% of captured fake-socket traffic across the suite contains only workspace/pane identifiers, URLs, messages, and levels — the credential-surface scan finds nothing else.
- **SC-005**: Zero third-party imports in the shipped shim, verified by the existing stdlib-boundary gate (`test_stdlib_boundary.py`, which already walks the shipped `bin/` — no extension needed; the socket modules join its allowlist as a deliberate, reviewed addition).
- **SC-006**: Usage errors (unknown verb, malformed arguments) exit nonzero with usage output in 100% of cases — the loud path stays loud.

## Assumptions

- **cmux protocol specifics are plan-time**: §6.3 commits to "speaks cmux's socket API" without message shapes; the plan pins framing against the real API. (D-9's verification claim is scoped honestly: what daily production use verified is SSO pane persistence — R-3's retirement — not the wire protocol; no spike covers the socket API.) The spec pins behavior (what each verb accomplishes), not wire format.
- **Notice scoping for config selection**: an unrecognized or malformed value gets a diagnostic notice (the slice-2 posture: malformed = treated as absent, noticed); a wholly absent `battleBuddy.shell` key is *silent* degraded — absence is the documented normal state for shell-less teams, and per-call notices for a normal state would be noise. This deliberately refines the slice-2 precedent (which notices whole-block absence once per session, not per call). Slice 4 pinned the opposite (repair-case, never treat-as-absent) for `/setup`, where re-creation is destructive — a read-only selection decision safely follows slice 2. Degraded-by-default is the only safe reading of FR-26's "first-class path".
- **Degraded `open-pane` prints**: §6.3's every-call rule; design §3.2 step 3 says "no-op in degraded mode" — the same design-internal inconsistency slice 5 flagged; the owning pin is here, in the shim's slice: print.
- **Usage errors are loud (nonzero)**: the fail-soft mandate covers *backend availability*, not caller bugs; a slice-5 command passing garbage must hear about it. Spec-pinned — the design addresses only backend failure.
- **Stateless shim / per-invocation independence**: no backend-health memory, no lockout, no retry storm — each call attempts and falls back independently. Spec-pinned; keeps the §10 pure-function property and makes R-2 recovery automatic (socket returns → next call uses it).
- **Reattach semantics live in the backend**: the shim passes the session ID; the backend decides create-vs-reattach. Consistent with "workspaces survive restarts" (§6.3) without the shim tracking workspace existence.
- **Notify delivery in degraded mode** is the printed message; richer delivery (system notifications) is a future backend concern, not v1.
- **Consumer invocation points** (open at `/page`, navigate at briefing, close at `/close` — slice 5, PR #10; the doctor round-trip — slice 4, PR #9) are consumed boundaries on open PRs, declared per house convention.
- **Interface completeness vs slice 5 — resolved by pin**: slice-5's close flow closes the shell workspace (its FR-008), but §6.3's interface block defines only three verbs — the design's own gap. Following the slice-5 precedent (resolve upstream conflicts in-spec, flag for reconciliation), this spec pins the workspace-close operation's *existence* into the interface (FR-001) as a recorded D-2 addition amending §6.3's block; its name and exact semantics are pinned at plan time against the backend API. Flagged for design-doc reconciliation.
