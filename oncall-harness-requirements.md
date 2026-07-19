# battle-buddy — Requirements Document

*An on-call agent harness: your battle buddy for the pager.*

**Version:** 0.9 (draft for iteration)
**Status:** Pre-implementation
**Last updated:** 2026-07-18

**Changes in 0.9:** Deep investigator owns the ledger and synthesis; orchestrator reduced to thin router/lifecycle. Triage verdict persisted as checkpoint zero. Hypothesis provenance tags (triage | recall | fresh) with a mandatory fresh hypothesis to counter triage anchoring. Explicit deep-investigation launch conditions (FR-5f).

**Changes in 0.8:** Tier 0 rewritten as conventions-only — zero shipped storage code. All tier-0 I/O goes through stock Google MCPs; retrieval is fingerprint exact-match → keyword filter → agent-ranked in-context; embeddings are cut from tier 0. Vector search and the repository interfaces (`IncidentStore` etc.) are born with the tier-1 Go server. Graduation trigger defined: when agent-ranked retrieval starts missing.

**Changes in 0.7 (research cross-reference):** Memory anti-over-trust (VALIDATED/INVALIDATED re-check) elevated to a headline feature. Investigation checkpoints for pause/resume/handoff. PreToolUse guardrail deny layer tuned to documented agentic misbehaviors. Prompt-injection hardening for untrusted telemetry text. Causal fields (root cause, action items) kept human-curated in all auto-drafts. Success-metrics subsection. Fingerprint keying in the session schema. Prior-art section. Team-wide scoped-auth gateway explicitly out of scope for v1.

**Changes in 0.6:** Added §9 Future Agents & Skills — the post-MVP roster across during-incident (scribe/comms, escalation advisor, mitigation planner), after-incident (postmortem drafter, runbook-gap agent), and between-incident (pattern miner, handoff briefer, catalog auditor) phases.

**Changes in 0.5:** Two-speed agent model: fast triage subagent (auto-run at session start, budgeted, read-only, structured verdict) and deep investigator (hypothesis ledger, approval-gated tools, parallel specialist subagents). Capability-manifest model for MCPs: teams bring their own servers; the harness declares required/optional capabilities and `doctor` verifies them.

**Changes in 0.4:** Introduced tiered storage. Tier 0 (zero infrastructure): Google Sheet as the structured store behind the same `IncidentStore` interface, embeddings stored as a column with client-side similarity, large blobs in Drive with links in rows. Tier 1: the Postgres+pgvector Go server as the graduation path. MVP re-scoped to tier 0; the server moves to fast-follow.

**Changes in 0.3:** Sessions cover both declared incidents and routine (non-incident) pages. Teams configure their existing diary location; the harness dual-writes at session close — team diary + our DB — and the DB record stores the link to the diary entry.

**Changes in 0.2:** Adopted Claude Code as the runtime across all phases (resolves OQ-4). Replaced the custom Tauri shell with a shell-adapter model, cmux as the reference shell. Collapsed architecture from three custom layers to two. Reworked MVP cut. Added Risks section.

---

## 1. Vision

An open-source harness that an on-call engineer launches when a page fires — whether it becomes a declared incident or stays a routine alert. Agents do the heavy lifting — context assembly, investigation, deploy correlation, runbook retrieval, comms drafting — through connections to the tools a team already uses (GitHub, Grafana, Splunk, Opsgenie/PagerDuty, etc.). A hosted persistence server provides institutional memory: every incident enriches a shared knowledge store, so each on-call shift is better-informed than the last.

The engineer works from a single screen: the agent in one pane, embedded browser views of their observability and incident tools alongside, with the agent able to drive those views to the evidence it cites.

**Core flywheel:** agent reads memory → agent does work → agent writes memory.

## 2. Goals

- A team or company can clone the project and be running against their own database and tool stack with minimal integration work.
- Agents operate through standard MCP connections; nothing in the harness is bespoke per-tool integration code.
- Institutional knowledge (incident history, resolutions, tool traces) compounds automatically over time without manual diary upkeep.
- Human-curated knowledge (runbooks, service catalogs) is never duplicated into the system — always fetched fresh from its source of truth at session start.
- One screen for the whole incident: chat, dashboards, logs, alerts.
- Minimal custom surface area: build on Claude Code and existing shells rather than a bespoke agent runtime or desktop app.

## 3. Non-Goals

- Autonomous remediation without human approval (v1 is read-only investigation plus gated, approve-to-run actions).
- A team-wide scoped-auth gateway (centralized per-user/per-environment credential brokering). v1 uses per-responder credentials with read-only token defaults; a gateway is a possible tier-1+ roadmap item.
- Replacing the team's incident management tool (Opsgenie/PagerDuty remain the system of record for paging and escalation).
- Storing or versioning runbooks and remediation documentation.
- Building a custom desktop shell or agent runtime (superseded by cmux + Claude Code; see §5).
- A self-contained/offline deployment model (server and DB are hosted by the adopter).

## 4. Personas

- **Responder** — the on-call engineer who launches the harness for an incident. Wants context fast at 3am and minimal typing.
- **Platform adopter** — the engineer or platform team deploying the server and configuring the catalog/MCP roster for their org.
- **Contributor/forker** — an OSS user extending storage backends, catalog adapters, shell adapters, or MCP integrations.

## 5. System Architecture

One custom component (the Claude Code plugin), a tiered storage model, and two adopted platforms:

1. **Harness (Claude Code plugin)** — the agent runtime is Claude Code itself. The harness ships as a plugin/config bundle: `.mcp.json` registering the storage backend and catalog adapter, `/incident` and `/page` slash commands driving the session lifecycle, a skill encoding investigation methodology, and hooks for guardrails. Permission gating rides on Claude Code's native approval system.
2. **Storage (tiered)** —
   - **Tier 0 — conventions, not code (MVP):** a Google Sheet is the structured store, accessed entirely through stock Google MCPs. battle-buddy ships a documented schema (columns) and skill instructions, not storage code. Rows are session records; large artifacts (tool traces, transcripts) live as Drive files with links in the row. Retrieval: fingerprint exact-match → keyword filter on service/alert columns → the agent pulls candidate rows and ranks relevance in-context, which is reliable at team scale (dozens to a few hundred rows). No embeddings in tier 0.
   - **Tier 1 — server (fast-follow):** the Go persistence server with Postgres+pgvector, itself an MCP server exposing `search_similar_incidents`, `log_diary_entry`, `get_service_history`, `record_resolution`. The repository interfaces (`IncidentStore`, `KnowledgeStore`) are born here, along with vector/hybrid retrieval and enforced schema. Migration is a documented sheet ingest.
   - **Graduation trigger:** not scale in the abstract — graduate when agent-ranked retrieval starts missing (SM-3 surfaces this naturally), typically as the store grows past what fits usefully in context.
3. **Shell (adopted, via adapters)** — the single-screen environment is provided by an existing programmable shell. Reference integration: **cmux** (macOS) — agent terminal pane + embedded browser panes in an incident-named workspace, driven through its socket API. The harness talks to shells through a thin **shell-adapter interface** (`open-pane`, `navigate-pane`, `notify`) so the core never depends on cmux specifically. Degraded mode: plain terminal, links printed instead of panes driven.
4. **Runtime phases on Claude Code:**
   - *Responder-launched (v1):* interactive Claude Code with the plugin.
   - *Programmatic embedding (later, if needed):* Agent SDK exposes the same engine as a typed async API; its streamed message objects double as the structured tool trace.
   - *Alert-triggered (later):* headless `claude -p --bare` runs with explicit config/credentials and schema-constrained JSON output for findings attached to pages.

### Division of knowledge

| Store | Contents | Write policy | Freshness model |
|---|---|---|---|
| Team's git / Backstage | Service catalog, runbooks, dashboard links | Human-curated, PR-reviewed | Fetched fresh at session start; never copied |
| Team's diary (their tool: Confluence, Notion, git, doc) | Human-readable session entries in the team's chosen format/location | Agent-drafted at close, human-approved; dual-written alongside our DB | The team's readable artifact; our DB stores the link to each entry |
| Persistence server | Session records (incidents and pages), resolutions, agent tool traces, diary entry links | Append-only, agent-generated (human-approved at close) | Written at session close; indexed for retrieval |

## 6. Functional Requirements

### 6.1 Session lifecycle (incidents and pages)

- FR-1: The responder starts a session from either a declared incident (`/incident INC-1234`) or a routine page/alert (`/page <alert-id>`); the harness opens a scoped workspace either way. Pages get a lighter-weight lifecycle; a page session can be promoted to an incident session without losing context.
- FR-2: On session start, the harness resolves the firing alert to a service via the catalog, fetches that service's runbooks and dashboards fresh from their sources, queries the persistence server for similar past sessions (incidents and pages), and presents the agent's briefing before the responder asks anything.
- FR-3: Workspace panes, chat history, and time ranges are scoped to the session. When a shell adapter is active, the workspace is named for the session and survives restarts (session restore).
- FR-3a: **Investigation checkpoints.** The hypothesis ledger and investigation state (phase, hypotheses with confidence and supporting/refuting evidence, services touched, tool-call count) checkpoint to the session store as the investigation progresses — so an investigation survives session death, can be paused and resumed, and can be handed to another responder mid-flight (e.g. at shift change) with full state.
- FR-4: At close, the agent drafts a diary entry from the session transcript; the responder approves or edits it. The harness then **dual-writes**: (a) the human-readable entry to the team's configured diary destination, and (b) the structured session record to the persistence server, including the URL/link of the diary entry just written.
- FR-4a: Diary destinations are configurable per team behind a **diary-adapter interface** (same pattern as storage/catalog/shell adapters), written via MCP — e.g. Confluence page, Notion database, Google Doc, or a markdown file in git.
- FR-4b: Write ordering and failure policy: diary first (to capture its URL), then the DB record. If the diary write fails, the DB record is still written with a `diary_pending` flag and the entry is queued for retry; the DB write is the one that must not be lost. In tier 0 this ordering is enforced by skill instructions within the human-approved close flow; in tier 1 it is enforced in server code.
- FR-4c: Diary entry format: teams may configure an entry template; absent one, the agent reads recent entries in the destination diary and matches their existing format. The structured DB record is unaffected by diary formatting either way.
- FR-4d: **Session report.** A full human-readable investigation report is generatable from persisted data alone: triage verdict, hypothesis ledger with per-hypothesis evidence (deep links to dashboards with time windows, log/search query URLs, code/PR refs, log excerpts), timeline, resolution, and causal fields flagged per FR-8. Generated at close by default (configurable) as a Drive document, linked from both the session row and the diary entry — and **regenerable on demand at any later time from the record**, since it is purely a rendering of what FR-21 already stores.
- FR-4e: **Evidence is links plus excerpts.** Ledger evidence entries and triage-verdict citations store the URL-addressable reference (dashboard + time range, search query URL, commit/PR, alert) plus a short excerpt — never prose summary alone. This is what makes FR-4d's report reconstructable and FR-9's deep-linking possible after the fact.

### 6.2 Agent model and capabilities

**Two-speed investigation.** The responder talks to an orchestrator session; investigation runs at two speeds beneath it, implemented as Claude Code subagents (per-subagent model and tool restrictions), sharing one investigation skill under different budget/toolset/model settings.

- FR-5: **Triage agent (fast).** Auto-runs at session start and produces the FR-2 briefing. Hard-budgeted (target ≤2 min, capped turns), fast model, narrow read-only toolset. Fixed questions: is this known (similar-session retrieval)? is it real (alert flap history)? what changed (deploy window)? who's affected (metric read + dependency glance)? Output is a structured verdict: known-issue match with prior resolution, top cause candidates with confidence, severity read, recommended next step — including an honest "no strong signal, recommend deep investigation." **The verdict is persisted to the session store as checkpoint zero** — evidence with provenance, surviving handoff, and enabling later measurement of triage accuracy.
- FR-5a: The triage agent is re-invocable mid-session on newly firing alerts, classifying them as related-to-current vs separate, without disrupting deep investigation.
- FR-5b: **Deep investigator.** Owns the **hypothesis ledger** — hypotheses with evidence for/against — and owns synthesis: specialist subagent findings (e.g. log-diver, deploy-analyst, dependency-checker, run in parallel) return to the deep investigator and are merged into the ledger there. **The orchestrator does not ingest findings**; it is a thin router that relays ledger updates to the responder and steering back, keeping the conversational session's context lean across long incidents. The deep investigator reports at each ledger update rather than running silently; mutating tools sit behind approval gates. (Claude Code's experimental agent-teams mode — cross-communicating parallel agents — is the intended future fan-out upgrade: opt-in for incident-severity sessions once the feature stabilizes, configured per-mode per FR-5c. Stability is the blocker, not its ~4x token cost, which is noise against incident impact.)
- FR-5c: Speeds are configuration, not separate agents: budgets, toolsets, and model choice per mode are exposed as plugin settings.
- FR-5d: **Recalled memory and triage output are hypotheses, never conclusions.** Every ledger hypothesis carries a **provenance tag**: `triage` (from the triage verdict), `recall` (from the session store), or `fresh` (generated by the deep investigator from raw evidence). Recalled sessions and triage candidates alike must be classified **VALIDATED or INVALIDATED against fresh evidence from the current incident** before being acted on — semantic similarity and fast shallow triage both produce systematic, confident errors. The triage verdict and ledger explicitly mark each finding's validation status. This discipline is a headline feature of the product, not an internal detail.
- FR-5e: **Tunnel-vision and anchoring guard.** The ledger requires a minimum of 3 live hypotheses before deep-diving any single one, and at least one must be `fresh` — generated independently of the triage verdict — so triage's shallow ranking cannot fully anchor the investigation. (Full blind re-derivation is rejected as too slow mid-incident; the mandatory fresh hypothesis buys most of the protection at no latency.)
- FR-5f: **Deep-investigation launch conditions.** Deep mode launches when: (a) the triage verdict returns no strong signal or explicitly recommends it; (b) the responder requests it — promotion to `/incident` always launches it; or (c) a triage-recommended fix fails verification after application. Decision authority: the orchestrator proposes, the responder confirms (copilot principle); a config flag enables auto-launch for incident-severity sessions.
- FR-6: Deploy correlation — identify changes shipped within a configurable window that touch the affected service or its declared dependencies.
- FR-7: Runbook retrieval and read-only execution — locate the relevant runbook, execute its read-only diagnostic steps via MCP tools, report results. Mutating steps are surfaced as approve-to-run actions through Claude Code's permission prompts.
- FR-7a: **Guardrail deny layer.** PreToolUse hooks block known-dangerous command patterns outright (destructive filesystem/cluster/cloud operations, credential-scanning after auth errors, verification-skipping retries), beneath and independent of the approval gates. Documented real-world agentic misbehaviors serve as the guardrail test suite.
- FR-7b: **Injection hardening.** Alert descriptions, error payloads, and ticket text are untrusted input; the harness marks such telemetry-derived text as data-not-instructions in prompts. The recommended configuration defaults every MCP to read-only credentials (e.g. viewer-role tokens, read-only IAM conditions) and context-pins cluster tooling to a single environment per server instance.
- FR-8: Comms drafting — status updates, exec summaries, and incident timeline reconstructed from the channel and tool calls. **Auto-drafts fill factual fields only** (timeline, links, metrics, who/what/when); causal fields — root cause, contributing factors, action items — are drafted as explicitly-labeled proposals requiring human curation, since hallucination concentrates in causal analysis.
- FR-9: Evidence deep-linking — factual claims in agent output are backed by URL-addressable views (Grafana dashboard + time window, Splunk search, PR, alert). With a shell adapter active, the agent navigates the adjacent browser pane to the evidence; without one, it prints the links.

### 6.3 Service catalog

- FR-10: The native catalog format is the Backstage entity format (`catalog-info.yaml`). Two source modes: (a) files in git parsed directly; (b) a live Backstage catalog API.
- FR-11: Established Backstage annotations are read where present (e.g. `grafana/dashboard-selector`, `pagerduty.com/service-id`, `github.com/project-slug`).
- FR-12: A documented `oncall-harness/*` annotation namespace covers gaps, minimally: runbook locations and alert→service matching. The harness degrades gracefully with partial annotations.
- FR-13: A minimal entity subset is accepted (`kind`, `metadata.name`, `spec.owner`, annotations) so teams without Backstage face a low floor.
- FR-14: Catalog sources are adapters into a small internal service model (service, owners, runbooks, dashboards, alerts, dependencies), keeping the door open for CMDB or plain-JSON adapters.
- FR-15: `spec.dependsOn` drives blast-radius widening during investigation.

### 6.4 Storage / persistence

- FR-16: **Tier 0 (conventions).** One row per session record; columns follow the FR-21 schema, documented as a template sheet. All reads/writes go through stock Google MCPs, orchestrated by skill instructions — battle-buddy ships no tier-0 storage code. Artifacts exceeding cell limits (~50k chars — tool traces, transcripts) are written as Drive files with their links stored in the row. Append-mostly write pattern within Sheets API rate limits.
- FR-16a: **Tier 0 retrieval:** fingerprint exact-match first, then keyword filtering on service/alert/severity columns, then the agent pulls candidate rows and ranks relevance in-context. The fingerprint definition (FR-21) carries the retrieval load embeddings would otherwise carry, and its normalization rules are therefore specified exactly in the schema doc.
- FR-16b: **Tier 1 (server).** The Go persistence server is an MCP server; Postgres + pgvector is the shipped backend. The repository interfaces (`IncidentStore`, `KnowledgeStore`) exist from tier 1 onward. Migration from tier 0 is a documented sheet ingest.
- FR-18: **Tier 1 retrieval** combines BM25/keyword and vector similarity with metadata filters (service, severity, alert type, session type), because on-call queries are dense with exact strings (error codes, service names).
- FR-19: **Tier 1 embedding generation** sits behind a provider interface (bring-your-own-embeddings; no vendor baked in) and occurs at write time.
- FR-20: Session records store pointers plus versions for external knowledge used (runbook URL + commit SHA where git-hosted), never the content itself.
- FR-21: The session record schema includes at minimum: session type (incident | page), **fingerprint (hash of service + error/alert type, checked for exact match before semantic search)**, alert signature, affected service(s), **triage verdict (checkpoint zero)**, **ledger checkpoints with hypothesis provenance tags**, timeline, root cause, resolution, links to PRs/dashboards, the diary entry link, and the agent's tool trace (inline in tier 1; Drive link in tier 0).

### 6.5 Shell integration

- FR-22: Shell integrations implement a thin adapter interface — `open-pane(url|command)`, `navigate-pane(pane, url)`, `notify(message, level)` — behind which the harness core is shell-agnostic.
- FR-23: Reference adapter: cmux via its socket API — incident-named workspace, agent terminal pane, embedded browser panes for third-party tools, notifications when the agent needs attention or approval.
- FR-24: Third-party tools render in the shell's embedded browser using the responder's own SSO sessions; the harness never handles user credentials for those tools. Agent tool access is a parallel path via MCP with API tokens.
- FR-25: **Capability manifest + `doctor`.** Teams bring their own MCP servers; the plugin declares required capabilities (`storage`, `diary`, `alerting`) and optional ones (`code`, `observability`), not specific server implementations. `doctor`, run outside of incidents, verifies each capability is satisfied by some connected, authenticating MCP (and that the shell adapter responds, if configured). Missing optional capabilities yield a "reduced features" report and gracefully disable dependent features (e.g. no `code` → no deploy correlation); missing required capabilities fail loudly.
- FR-25a: A **recommended `.mcp.json`** ships as a documented starting point for teams starting from zero; the investigation skill is written against capabilities ("your deploy-history tool"), never hardcoded tool names, so any conforming MCP slots in.
- FR-26: Degraded mode: with no shell adapter, everything works in a plain terminal; deep links are printed, not driven.

## 7. Non-Functional Requirements

- NFR-1: **3am test** — starting a session requires one command plus an incident ID; the briefing arrives before the responder has finished pouring coffee.
- NFR-2: **Safety** — all mutating actions gated behind explicit human approval via Claude Code's permission system; the session transcript doubles as an audit log.
- NFR-3: **Extensibility** — storage backends, catalog sources, embedding providers, and shell adapters are all interface-swappable without touching the agent layer.
- NFR-4: **Adoption floor** — tier 0 requires only Claude Code auth, Google access, and the plugin: paste a Sheet URL and a diary URL, run `/page`, and the flywheel starts. No server, no database, no deploy. The Go server and cmux are upgrades, not gates.
- NFR-5: **Data ownership** — all incident data lives in the adopter's own database; the project ships no hosted service dependency.
- NFR-6: **Auth assumption** — each responder needs Claude Code auth (subscription or API key); alert-triggered mode needs a service API key. Stated plainly in the README.
- NFR-7: **License** — permissive open source (Apache-2.0 or MIT, TBD).

### Success metrics

- SM-1: **Time-to-first-hypothesis** — from page to a ranked, evidence-backed hypothesis list: target ~2–3 minutes against a typical unaided baseline of ~8–10.
- SM-2: **Adoption test** — responders *voluntarily* open the harness first during real incidents. This is the threshold for advancing past MVP.
- SM-3: **Memory payoff** — demonstrated cases where recall of a prior session's validated fix materially shortened a new investigation (the flywheel working, measured).
- SM-4: **Validation discipline** — recalled-memory findings carry VALIDATED/INVALIDATED status in ≥95% of briefings (the headline feature actually firing).

## 8. MVP Cut (tier 0 — zero infrastructure)

1. **Claude Code plugin**: `.mcp.json` bundle (Google MCPs, Opsgenie, GitHub), `/incident` and `/page` slash commands, investigation skill, session-close dual-write flow, `doctor`.
2. **Session store conventions**: template Sheet with the FR-21 schema, exact fingerprint normalization rules, Drive-link pattern for large artifacts, and the FR-16a retrieval flow encoded in the investigation skill.
3. **One diary adapter**: Google Doc (matches tier 0's Google footprint) with FR-4c template/format-matching.
4. **File-mode Backstage catalog adapter** with the `oncall-harness/*` annotations.
5. **Opsgenie integration**: alert→session context on `/page` / `/incident`.
6. Session flow end-to-end: briefing on start, similar-session retrieval, dual-write on close.

**Fast-follow:** Go persistence server (tier 1, Postgres+pgvector) + sheet-export migration; cmux shell adapter.

Deferred further: Agent SDK embedding, alert-triggered headless mode, Backstage API mode, comms drafting, additional diary adapters (Confluence, Notion), wmux/other shell adapters.

## 9. Future Agents & Skills (post-MVP roadmap)

All entries below are pure consumers of assets the MVP already produces (session store, hypothesis ledger, transcript, catalog); none require new storage or architecture. All drafting agents follow the FR-8 rule: factual fields auto-fill, causal fields (root cause, contributing factors, action items) remain human-curated proposals. Ordered by lifecycle phase.

### During incident

- FA-1: **Scribe/comms agent** — FR-8 promoted to a live subagent: maintains the incident timeline as events occur, drafts status updates on a cadence, and answers stakeholder "what's the latest?" queries so the responder never context-switches to write prose.
- FA-2: **Escalation advisor** — joins catalog ownership data with incident context and drafts the escalation page to the correct team *with the current briefing attached*, so the escalated engineer never starts cold.
- FA-3: **Mitigation planner** — before any approve-to-run gate, lays out remediation options with blast radius and rollback path for each, making human approval an informed choice rather than a rubber stamp.

### After incident

- FA-4: **Postmortem drafter (skill)** — formats transcript + hypothesis ledger + timeline into the team's postmortem template; near-free given what the session already stores.
- FA-5: **Runbook-gap agent** — when a session closes with no matching runbook, or the runbook proved wrong, drafts a runbook PR to the team's own repo. Closes the curated-knowledge loop without violating the "we don't store runbooks" boundary: the agent feeds the team's source of truth, humans review.

### Between incidents (scheduled, not page-triggered)

- FA-6: **Pattern miner** — periodically sweeps the session store for recurring signatures ("this alert fired 14 times, 11 self-resolved," "these 6 pages shared a root cause") and produces a toil report with suggested alert tuning and runbook updates. Makes the flywheel visible to management.
- FA-7: **Handoff briefer** — at shift change, generates the rotation summary from data: open threads, degraded-but-not-paging systems, recent risky deploys, watch items. The handoff doc nobody actually writes.
- FA-8: **Catalog auditor** — checks Backstage entities for rot (dead runbook links, missing owners, absent annotations) and files fix-up PRs, keeping the map everything else depends on trustworthy.

**Priority order for implementation:** FA-5 and FA-6 first (pure session-store derivatives, hardest to replicate without the persistence layer, and they shift the pitch from "faster incidents" to "on-call gets structurally better every month"), FA-7 next (strong demo), then the rest.

## 10. Risks

- R-1: **cmux is macOS-only.** Windows has a young third-party port (wmux); Linux has no equivalent yet. Mitigated by FR-26 degraded mode and the adapter interface — but v1's flagship experience is Mac-first.
- R-2: **Shell dependency risk.** The flagship UX rides on a third-party app's socket API. Mitigated by the thin adapter interface, which doubles as the spec for a future first-party shell if ever needed.
- R-3: **SSO in embedded browser panes** is assumed, not yet verified. Action: hands-on test of Okta-style flows and session persistence in cmux's browser panel before committing the adapter design.
- R-4: **Claude Code surface churn.** Plugin/config/headless interfaces are evolving quickly; pin versions and keep the plugin thin.
- R-5: **Agentjacking.** Prompt injection via untrusted incident text (alert payloads, error messages, tickets) flowing into an agent with tool access is a live, industry-wide attack class. Mitigated by FR-7a/7b (deny layer, data-not-instructions marking, read-only defaults) but the security model for agents against live telemetry is immature everywhere; treat as an ongoing posture, not a solved item.

## 11. Open Questions

- OQ-1: ~~Responder-launched vs alert-triggered?~~ **Resolved 0.3:** responder-launched for v1; alert-triggered deferred.
- OQ-2: ~~Diary/knowledge scope?~~ **Resolved 0.3:** per-team.
- OQ-3: ~~Reference incident tool?~~ **Resolved 0.3:** Opsgenie first.
- OQ-4: ~~Agent runtime packaging~~ **Resolved 0.2:** Claude Code across all phases — plugin (v1) → Agent SDK (if programmatic embedding is needed) → headless `--bare` (alert-triggered).
- OQ-5: ~~Deployment model?~~ **Resolved 0.3:** no multi-tenancy — one server instance per team; isolation by deployment.
- OQ-6: Transcript→timeline storage — raw transcript, structured events, or both? (Note: Agent SDK / stream-json message objects provide structured events for free; leaning "both, structured derived from raw.")
- OQ-7: ~~Non-Mac responders in v1?~~ **Resolved 0.3:** Mac-first; degraded terminal mode covers everyone else until demand justifies a wmux/Linux adapter.

## 12. Prior Art & Differentiation

Adjacent projects, and what this project does that they don't:

- **wshobson/agents `incident-response` plugin** — widely-used open-source Claude Code plugin: guided triage→postmortem workflow, runbook/comms templates. No persistence, no memory, no storage tier.
- **Rootly Claude Code plugin** — official vendor plugin for incident ops (on-call lookup, status updates, handoffs, retros) tied to Rootly's platform.
- **RunbookAI** — the closest prior art: self-hosted knowledge server with an MCP endpoint, markdown runbook store, hypothesis-driven investigation with checkpoints, PreToolUse guardrails. Differs from us in storing runbooks itself (we point at the team's source of truth), no dual-write diary, no zero-infra tier, no memory-validation discipline as a product feature.
- **HolmesGPT** — read-only diagnostic agent; stops at diagnosis by design.
- **Grafana Assistant Investigations / Datadog AI agents** — vendor-native multi-agent investigation inside one vendor's data; not cross-tool, not team-owned storage.

**Our differentiators:** (1) validated memory — recalled sessions re-checked against fresh evidence as a first-class product behavior; (2) dual-write diary into the team's own tool with the structured store keeping the link; (3) zero-infrastructure tier 0 (Sheet + Doc) with a clean graduation path; (4) bring-your-own MCPs verified by capability manifest; (5) single-pane shell integration via cmux.
