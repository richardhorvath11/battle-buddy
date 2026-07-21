# Research — Lifecycle Commands (plan-time pins)

Each entry: **Decision / Rationale / Alternatives considered**. These resolve every
plan-time unknown the spec's Assumptions defer ("pinned at plan time") plus the
executable-form questions the prior slices' pattern raises. Normative cross-slice
shapes live in `contracts/lifecycle-protocol.md`; this file records *why*.

## R1 — Executable form: `lifecycle_flows.py` + `lifecycle_fixtures.py` in `tests/helpers/`

**Decision**: The three commands' executable specification is one dev-only flow module
(`tests/helpers/lifecycle_flows.py`) composing the existing slice-3/4 helpers —
`store_flows` (open/close primitives, checkpoints, ownership, retrieval),
`doctor_flows.evaluate_stamp`, `setup_flows.responder_mode` — plus one fixture module
(`tests/helpers/lifecycle_fixtures.py`) for the consumed slice-6–9 surfaces. Flow
functions mirror the command docs step-for-step, each step commented with the command
section it executes.

**Rationale**: Exactly the established pattern (slice 3's `store_flows`, slice 4's
`doctor_flows`/`setup_flows`); reuse keeps one implementation per convention (D-4's
drift argument generalized). Constitution I: nothing ships.

**Reuse boundary, stated precisely**: the **close** path reuses
`store_flows.close_session` itself, extended with two *additive, default-off*
keyword-only parameters (see R13) so slice-3 behavior and tests are untouched. The
**open** path does *not* call `store_flows.open_session` (which writes the marker once,
at the end, and appends a plain row — the lifecycle open needs the marker early at
`open_write_confirmed: false` and the verdict riding the append, R2); it reuses the
lower primitives instead — `retrieve_candidates`, `parse_source_id`,
`detect_open_session`, `read_latest_checkpoint`, `take_over`, `merge_duplicates`,
`_serialize_checkpoint`, `COLUMNS`/`WRITE_ONCE`, and the real `bb_validate` — and owns
its own marker/append sequencing.

**Alternatives**: a `tests/scenarios/` driver (rejected: scenario harness is on-demand,
not the required hermetic layer); duplicating the pinned close-order logic in lifecycle
flows (rejected: two implementations of the close order would drift — hence the
additive extension of `close_session` rather than a bespoke close path).

## R2 — Checkpoint zero rides the open-time append

**Decision**: `/page`'s open flow validates the verdict (real `bb_validate`, one
re-prompt, flagged persist on second failure — the slice-3 gate) and then embeds the
winning serialized document in the **appended row's `triage_verdict` field** — not a
separate `update_record`. The cell guard applies at append: an over-guard verdict is
`put_file`d first (`battle-buddy/<session_id>/checkpoint-0.json`) and the row carries
the overflow pointer. The history line (`staging/checkpoints.jsonl`, `{"seq": 0,
"document": ...}`) is appended per slice-3's history rule. Serialization reuses
`store_flows._serialize_checkpoint`'s pinned form via a shared code path.

**Rationale**: Spec FR-001 pins "riding the open-time append … not a separate store
write; an overflowed verdict stores its artifact first". One write means the open-time
read-back also confirms checkpoint zero landed. Mirrors slice-3 semantics without
calling `write_checkpoint` (which is an `update_record` on an existing row and
pre-reads ownership the just-appending session trivially holds).

**Alternatives**: append then `write_checkpoint` seq 0 (rejected: two writes, and the
spec explicitly forbids it).

## R3 — Fixture triage (slice-6 stand-in)

**Decision**: Fixture verdict documents under `tests/fixtures/lifecycle/verdicts/`,
conforming to (or deliberately violating) `bb.verdict.v1` and validated by the **real**
`bb_validate`. The re-prompt path is modeled as an ordered candidate list — the same
convention `store_flows.write_checkpoint` already uses — so "one re-prompt, then persist
flagged" is exercised without any agent. Slice-3's `tests/fixtures/validate/` corpus is
reused where a generic valid/invalid verdict suffices.

**Rationale**: Spec Assumption "triage is simulated by a fixture verdict"; the pinned
contract is `bb.verdict.v1`, already enforced by slice 2. No mock of the validator
(slice-3 research R9 precedent).

**Alternatives**: monkeypatching validation outcomes (rejected: slice-3 precedent
forbids mocking the validator; fixtures exercise the real gate).

## R4 — Fixture catalog resolution (slice-7 stand-in)

**Decision**: `tests/fixtures/lifecycle/catalog.json` holds fixture catalog data
(service name, runbooks, dashboards, alert matchers, dependsOn); a small deterministic
resolver in `lifecycle_fixtures.py` maps the mock alert's fields against it —
rung 1 on a match (`catalog_resolved: true`), and on a miss walks the §5.2 ladder with
caller-injected rung answers (responder-provided name / alert tag / rule-based).
Fingerprints always compute through the real `bin/bb_fingerprint`.

**Rationale**: Spec Assumption "catalog resolution by fixture catalog data"; the
ladder's *selection* logic is this slice's orchestration concern (spec edge case
"Catalog resolution fails"), while YAML parsing stays slice 7's. Real fingerprint
helper per D-4 (one implementation, no drift).

**Alternatives**: reusing the scenario fixture catalog repo (deferred: that surface is
git-shaped for doctor's parseability check; retrieval here needs resolved fields, not
parsing).

## R5 — Diary draft: structured artifact `bb.draft.v1`, then rendering

**Decision**: `/close`'s drafting step produces a **structured draft artifact**
(`bb.draft.v1`, shape pinned in `contracts/lifecycle-protocol.md`): `factual` (autofilled
timeline/links/metrics/who-what-when fields) strictly separated from `proposals`
(`root_cause`, `contributing_factors`, `action_items` — each carrying
`"proposal": true`). The rendered diary entry is produced *from* the artifact — from the
configured template when `battleBuddy.diary.template` is present (additive optional
config key, pinned in the contracts doc), else format-matched against the mock's
`read_recent(5)` entries — with causal sections explicitly labeled as proposals in the
rendered text. Tests assert SC-006 on the artifact structure; rendering style is
asserted only for the presence of the proposal labels.

**Rationale**: SC-006 demands a *structural* property ("causal values appear only under
proposal-labeled fields — asserted on the draft artifact"); prose-only drafts can't be
asserted hermetically (Constitution VIII). Format matching itself is slice 8's surface —
this slice consumes `read_recent` and pins only the command-level properties.

**Alternatives**: asserting on rendered prose with regexes (rejected: prose assertions
are what §10 forbids); pinning a full diary rendering spec (rejected: slice 8's scope).

## R6 — Fixture shell adapter (slice-9 stand-in) and degraded mode

**Decision**: `lifecycle_fixtures.RecordingShellAdapter` exposes the §6.3 interface
this slice's commands call — `open_pane(target, workspace)`, `navigate_pane(pane, url)`,
`notify(message, level)`, `close_workspace(session_id)` (close-workspace is the §4
step-33 call; the `bb-shell` shim itself is slice 9) — recording every call; a failing
variant simulates mid-flow adapter death. Degraded mode (`shell.adapter` absent) routes
every call to a printed-message record in the flow outcome (per §6.3: a printed link or
message — the spec resolves §3.2's "no-op" wording to §6.3's behavior). Every shell
step is fail-soft: adapter errors degrade to printed output and never fail the flow.

**Rationale**: Spec FR-011 ("every shell interaction … through the shell-adapter
interface with a degraded path"), edge case "Shell adapter absent or its calls fail
mid-flow", and the degraded-mode Assumption. Slice-4's `FixtureShellAdapter` covers
only `notify`; lifecycle needs the pane/workspace surface.

**Alternatives**: extending slice-4's fixture in place (rejected: doctor's adapter is
round-trip-shaped; conflating the two surfaces couples unrelated tests).

## R7 — Join-path marker semantics (documented protocol extension)

**Decision**: On join, the marker is **rewritten** to the joined session's identity
(`session_id`, `source_id` parsed per schema.md, `opened_at` = the joined row's
`started_at`), with `open_write_confirmed` set only after the take-over write's
read-back confirms `responder` now names the joining responder. Pinned normatively in
`contracts/lifecycle-protocol.md` and flagged for local-state-protocol reconciliation
(a future protocol version bump), per the spec's Assumption.

**Rationale**: Spec FR-002 pins this extension; the protocol defines
`open_write_confirmed` for the open-time append only, and join performs an update. The
take-over read-back is the join path's "the store knows about me" proof — same
append-read-back discipline, different write.

**Alternatives**: leaving `open_write_confirmed: false` on join (rejected: the session
guard would warn on every legitimately joined session's end).

## R8 — Existing-marker handling: confirmed stops, unconfirmed is crash residue

**Decision**: The open commands check for a marker **before any store read**. A marker
with `open_write_confirmed: true` means a session is open in this workspace: surface it
and stop, offering `/close` first (one-session-at-a-time, protocol v1). A marker with
`open_write_confirmed: false` is crash residue: surface it, and only on explicit
responder confirmation **rewrite** it as part of proceeding with the new open — never
delete it as a separate step (deletion-is-cleared stays exclusive to confirmed close).
Declining leaves everything untouched.

**Rationale**: Spec FR-001's existing-marker step and the crashed-open edge case pin
both branches; rewrite-not-delete preserves D-11's invariant that only confirmed close
clears local state.

**Alternatives**: auto-clearing unconfirmed markers (rejected: silently destroys the
guard's evidence of an unpersisted session).

## R9 — Transcript at close: copy from the runtime transcript path, then upload

**Decision**: `/close` captures the transcript by copying the runtime's transcript file
(the same `transcript_path` the hooks receive; in tests, a caller-supplied fixture
path) into `staging/transcript.md`, then uploads it via the normal staged-artifact
mapping. A missing/unreadable transcript source is a logged notice: the artifact is
omitted (exactly the slice-3 per-file artifact-failure posture) and close continues.
Turns after close are absent from the upload — accepted v1 limitation, restated in
`commands/close.md`.

**Rationale**: Spec Assumption "Transcript availability at close" resolves the
protocol's SessionEnd-staging timing conflict this way; the mechanical-upload rule
(D-12) is preserved — close copies and uploads, never regenerates or summarizes.

**Alternatives**: waiting for SessionEnd staging (rejected: close runs mid-session;
the upload would race the session's own end); prose reconstruction (forbidden, D-12).

## R10 — Timeline derivation: mechanical map over trace lines + checkpoint history

**Decision**: The close-time `timeline` is derived by a pure function over (a) the
local `trace.jsonl` **call lines** (lines without an `event` field, per protocol v1)
and (b) the `staging/checkpoints.jsonl` history entries. Each trace call line maps to
one event `{"at", "source": "trace", "seq", "summary", "outcome"}`; each history entry
maps to `{"at", "source": "checkpoint", "seq", "phase"}` (`at`/`phase` read from the
checkpoint document where present). Events are ordered by timestamp (ties by source
seq). No transcript text is ever read. Tests assert the 1:1 mapping and the ordering.

**Rationale**: FR-009/D-5 pin the inputs and forbid prose recall; pinning the exact
event shape makes "timestamped, complete, never reconstructed" mechanically assertable
(SC-005/AS-6).

**Alternatives**: free-form timeline prose (unassertable); deriving from the uploaded
artifacts post-upload (equivalent inputs, worse ordering — derivation must precede the
row update that carries it).

## R11 — Preflight reuses slice-4 evaluation; SC-002's no-probe proof

**Decision**: The preflight's stamp evaluation **is** `doctor_flows.evaluate_stamp`
(missing/stale/fresh), fed by the config block's presence/validity first: no config →
stop with "run /setup"; malformed config → the slice-4 repair posture (stop, surface —
never treated as absent); stamp missing/stale → auto-run `setup_flows.responder_mode`
(the spec's "seconds, only on a first page from a new machine"); fresh → proceed with
**zero probe calls**. SC-002 is asserted on artifacts: mock write log unchanged by
preflight, no doctor-report artifact produced, stamp file byte-identical.

**Rationale**: Slice-4's helpers were built naming slice 5's preflight as their real
caller; reuse keeps staleness semantics single-sourced (the spec's "consumes that pin,
never redefines it").

**Alternatives**: reimplementing staleness in lifecycle flows (rejected: pin drift).

## R12 — Merge-at-close runs first (detection), but its writes run after approval

**Decision**: `/close` detects same-source-ID non-terminal duplicates (slice-3
`detect_open_session`) **before drafting** — a read, never a write — and determines the
prospective canonical row (earliest `started_at`) from that same scan; the draft is
built against this row. The merge's actual writes (`merge_duplicates`: links +
artifacts-folder folded, duplicates `superseded`) do **not** run at detection time —
they run later, after the draft is approved and after the closing session's own
ownership check (R13), immediately before the dual-write's diary write. The remainder of
close — dual-write, read-back — targets the **canonical** row, whichever session
invokes it; if the closing session's own row was superseded by the merge, its marker
deletion is gated on the canonical row's read-back (the incident's record is what must
land). The FR-008 ordering claim is scoped to the dual-write steps (diary → artifacts →
close-time row update → read-back); merge writes precede the scope, exactly as slice-3
scopes mid-session writes out.

**Rationale**: Drafting and the row update must describe one canonical record — merging
after the dual-write would close a row the merge then supersedes, so canonical must be
*determined* before drafting. But determining canonical is a read; actually *writing*
the merge (superseding a row) is not, and `bb.draft.v1`'s own invariant is "no write of
any kind occurs while `approved` is false" — a responder who declines a draft must find
nothing changed, not even a duplicate silently superseded. An earlier version of this
slice ran the merge's writes at detection time, before the approval gate; that violated
the draft's own zero-write invariant and `commands/close.md`'s own prose, and was
corrected here: detection (read) stays first, but merge *writes* move to after approval,
scoped alongside — not ahead of — the ownership check that must also gate them (R13).

**Alternatives**: merge writes at detection time, before approval (rejected above — the
corrected design); merge after the dual-write (rejected: closes a row the merge would
then supersede); merge only when the closing session is canonical (rejected: leaves a
duplicate open forever when the straggler closes first).

## R13 — Close-time ownership check: two checkpoints, each protecting a different row

**Decision**: The slice-3 pre-write ownership re-read extends to `/close`'s row writes
in **two** checkpoints, deliberately checking two *different* rows:

1. **This closing session's own row** (the one its local marker names) — re-read
   immediately after draft approval, before any close-flow write of any kind (merge,
   diary, or artifacts). Compared against **this session's own token**. On displacement:
   zero writes happen at all — not a merge write, not the diary, not an artifact, not
   the row update; close goes read-only and reports the take-over.
2. **The canonical row** — re-read again immediately before the close-time
   `update_record` (unchanged from slice-3's own placement of this check). Compared
   against canonical's own responder **as observed** during checkpoint 1's read-only
   detection scan (R12) — an optimistic-concurrency comparison spanning detection
   through to this update. On displacement: no row write, no read-back, no marker
   clearance; diary/artifact writes that already landed stand (additive, harmless); close
   goes read-only and reports the take-over.

When no merge is in play, canonical *is* the closing session's own row, so both
checkpoints protect the same row — checkpoint 2 simply reconfirms checkpoint 1's
guarantee immediately before the write it actually protects, not a second chance to
deny the same session for the same reason.

**Rationale**: Spec FR-010 pins the extension (following D-18's intent — no write to a
row you no longer own) while FR-008 pins that displacement, unlike transient write
failure, does not block-and-retry. A single checkpoint comparing canonical's row against
the closing session's own token — this slice's first cut at the mechanism — is **wrong**:
in the ordinary "straggler closes first" merge case (R12), the closing session is never
necessarily canonical's own opener, so that comparison false-denies the exact scenario
merge-at-close exists to handle (confirmed by executing it: two seeded rows, bob
canonical/carol duplicate, carol closing with her own marker and her own token was
denied because her token didn't match bob's row). Splitting into two checkpoints against
two different rows — this session's own identity, and canonical's own observed state —
resolves this: checkpoint 1 only ever compares a row against the token of whoever
actually opened it (always a legitimate comparison), and checkpoint 2 never involves the
closer's identity at all, only canonical's own last-known state versus its live state (a
pure optimistic-concurrency check, D-18's "no lock" model in its simplest form).
Checking checkpoint 1 before the diary write (rather than only at the row update) was
considered and rejected as *insufficient on its own*: the check's scope is row writes,
but scoping it to only the close-time update would let a displaced session's merge write
supersede a duplicate before the displacement is ever caught — checkpoint 1 has to run
before the merge write too, hence "immediately after approval, before any close-flow
write of any kind" rather than "immediately before the row update" for that first
checkpoint specifically.

**Mechanism** (unchanged by the two-checkpoint correction above — this is orchestration,
not a `store_flows` change): `store_flows.close_session` cannot host checkpoint 2 or the
retry today (no ownership pre-read, no retry — its only update-failure handling is
`not_found` reconciliation). Rather than duplicating the close order in lifecycle flows
(R1's rejected alternative), `close_session` gains two **additive, keyword-only,
default-off parameters**: `owned_by=None` — when set, re-read the row's `responder`
immediately before the step-3 `update_record`; on mismatch return a read-only outcome
(`read_only: True`, `taken_over_by`) without performing the row update, read-back, or
marker clearance (diary/artifact writes already made stand, per this pin) — and
`row_write_retries=0` — a bounded re-issue of the step-3 `update_record` on a
non-`not_found` error result (the injector-driven transient stand-in), never touching
steps 1–2 (no double diary write). Defaults preserve slice-3 behavior exactly; the
existing slice-3 close tests keep passing unmodified, and the new parameters are
exercised by this slice's close tests (Constitution VIII — code and its tests in the
same change). Checkpoint 1 (this session's own row) is orchestrated entirely in
`lifecycle_flows.close_command`, outside `close_session`, since it must run before the
merge write `close_session` never sees at all.

## R14 — Deep-investigation launch: orchestration flags only

**Decision**: The flows record orchestration outcomes — `deep_proposed` (always true
after triage for incident-type sessions), `deep_launched` (true on promotion, or when
`battleBuddy.autoLaunchDeep` is true for incident sessions, else only after recorded
responder confirmation) — and nothing else. No agent is spawned; slice 6 owns spawn
mechanics and the ledger. `autoLaunchDeep` is recorded as an additive config key in the
contracts doc.

**Rationale**: Spec Assumption "Deep-investigation launch mechanics are slice 6's";
§3.4's launch conditions (FR-5f) still need their command-side commitments pinned and
tested.

## R15 — Alert-fetch failure stand-in stays `not_found`

**Decision**: The hermetic stand-in for a failed alert fetch remains `get_alert` on an
unseeded alert (`not_found`) — no mock fault injection added. The open flow proceeds:
marker written, row appended with `alert_signature` from the alert ID alone, briefing
carries "alert context unavailable", failure surfaced in the outcome.

**Rationale**: The spec flags richer fault injection as plan-time work *if* the
broken-tool vs unknown-alert distinction proves test-relevant; it does not — every
FR-level behavior (session still opens, degradation surfaced) is identical for both
causes, so the closed error set suffices. Recorded so the deferral is explicit.

## R16 — Briefing: structural properties on a `bb.briefing.v1` artifact

**Decision**: The flows assemble a structured briefing artifact (shape pinned in the
contracts doc): `claims` — each `{statement, evidence: [{url, excerpt}, ...]}` drawn
from the verdict's candidates/known-issue fields — plus `top_cited_dashboard` (the
dashboard URL most cited across claim evidence; ties broken by first citation order),
`degraded` (bool), and `alert_context_available`. With a shell adapter, the flow issues
`navigate_pane` to `top_cited_dashboard`; degraded mode records printed links. Tests
assert every claim carries non-empty `{url, excerpt}` evidence and the navigate/print
branch. Briefing *content and format* remain slice 6's (`references/briefing.md`).

**Rationale**: FR-006/SC assertions need structure, not prose (Constitution VIII); the
command-level properties the spec pins (deep-linked evidence, top-cited navigation,
degraded links) are exactly what the artifact captures.

## R17 — Session-ID date is the open-time UTC ISO date; flows take it as input

**Decision**: `{ISO date}` in session IDs is the open-time date in UTC
(`YYYY-MM-DD`), restated in `commands/page.md`. Flow functions accept `opened_date` (and
timestamps generally) as parameters — tests pass fixed values; no flow reads the clock.

**Rationale**: Spec Assumption pins UTC; parameterized time keeps tests deterministic
(same discipline slice 4 used for the stamp's diagnostic timestamp).
