# battle-buddy

**An on-call agent harness for Claude Code** — a plugin that gives incident responders
agent-led investigation with compounding institutional memory. One command takes you from
alert to briefing; every closed session leaves behind searchable history that makes the
next page faster.

battle-buddy ships as a single Claude Code plugin. There is no server, no database, and
no bespoke per-tool integration: storage is conventions over your team's own connected
MCP tools (a spreadsheet, a drive, a doc), verified at setup time by a capability
manifest. Shipped code is Python 3 stdlib only (3.9+).

## What you get

| Surface | Contents |
|---|---|
| **Commands** | `/page` (alert → briefing), `/incident` (incident-weight open or promote), `/close` (diary + persistence + teardown), `/setup` (onboarding wizard), `/doctor` (capability health check) |
| **Agents** | `triage` (fast, read-only, turn-budgeted), `deep-investigator` (owns the hypothesis ledger), plus three specialists: `log-diver`, `deploy-analyst`, `dependency-checker` |
| **Skills** | `session-store`, `investigation`, `catalog`, `diary` — conventions the agents follow |
| **Hooks** | Deterministic guardrails: a PreToolUse deny layer, tool tracing, session-lifecycle guards (e.g. "session row not persisted — run /close") |
| **Helpers** | `bb-fingerprint` (alert fingerprinting), `bb-validate` (schema/invariant validator), `bb-shell` (shell-adapter shim for cmux) |

How it fits together, in one pass: `/page` opens a session, fetches alert and catalog
context, retrieves prior history for the same fingerprint, spawns triage, and presents a
deep-linked briefing. `/incident` runs the same flow with incident weight and proposes
deep investigation. `/close` drafts the diary entry (causal fields are always proposals
for *your* approval), persists everything in order, and only deletes local state once the
session row reads back confirmed.

The full architecture lives in [`bb-technical-design.md`](bb-technical-design.md); the
product rationale in [`oncall-harness-requirements.md`](oncall-harness-requirements.md).

## Setup guide

There are two setup paths. **Team setup** stands up battle-buddy for a team the first
time; **responder setup** gets each additional on-call engineer running against an
existing team workspace. Both end with a green `/doctor`.

### Prerequisites

- **Claude Code** installed and authenticated (`claude --version` works).
- **Python 3.9+** available as `python3` — the hook layer and helper scripts run on it.
  Stdlib only; nothing to `pip install` for normal use.
- **git** — the team workspace is a git repo.
- **MCP servers covering the four required capabilities** (team setup only; see step 3).

### Step 1 — Install the plugin

The repo doubles as a single-plugin marketplace, so installation is two commands:

```bash
claude plugin marketplace add richardhorvath11/battle-buddy
claude plugin install battle-buddy@battle-buddy
```

(Working from a local clone instead? `claude plugin marketplace add ./` from the repo
root, then the same install command. See
[`docs/local-plugin-testing.md`](docs/local-plugin-testing.md) for the full local-dev
flow, including how to pick up code changes.)

### Step 2 — Verify the install

```bash
claude plugin list                               # → battle-buddy@battle-buddy  ✔ enabled
claude plugin details battle-buddy@battle-buddy
```

The details output must show **Hooks (4)** — `PreToolUse`, `PostToolUse`,
`SessionStart`, `SessionEnd` — and **Agents (5)**. If the hooks are missing, stop and fix
that before anything else: the deny layer and the session-persistence backstop live
there, and a silently-dead hook is the most dangerous false green in the system.

### Step 3 — Connect your team's tools (team setup)

battle-buddy never hardcodes an MCP server or tool name. It declares the *operations* it
needs in [`manifest/capabilities.json`](manifest/capabilities.json), grouped by
capability, and `/doctor` resolves whatever you actually connected against them by
schema:

| Capability | Required? | What it's for | Example tool |
|---|---|---|---|
| `storage` | required | Session-store rows (append, read, update) | Google Sheets MCP |
| `artifacts` | required | Tool traces, transcripts, checkpoints | Google Drive MCP |
| `diary` | required | The team diary entries `/close` writes | Google Docs MCP |
| `alerting` | required | Alert context and history for `/page` | PagerDuty / Opsgenie MCP |
| `code` | optional | Deploy correlation for the deploy-analyst | GitHub MCP |
| `observability` | optional | Log/metric excavation for the log-diver | Grafana / Splunk MCPs |

Any roster whose connected tools satisfy the required operation shapes works.
[`templates/mcp.recommended.json`](templates/mcp.recommended.json) is a documented
starting roster for a Google-workspace team that passes `/doctor` out of the box — copy
it into your workspace's `.mcp.json` and swap entries freely.

**Credentials rule:** every credential in `.mcp.json` is written as an `${ENV_VAR}`
reference, resolved from each responder's own shell environment at launch. No literal
token, key, or secret ever goes into the file or the repo that holds it. Export the
variables your roster needs (for the recommended roster: `GOOGLE_PROJECT_ID`,
`GOOGLE_APPLICATION_CREDENTIALS`, `GDRIVE_OAUTH_PATH`, `GDRIVE_CREDENTIALS_PATH`,
`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `PAGERDUTY_USER_API_KEY`) in your shell
profile or secrets manager.

### Step 4 — Run `/setup`

Start Claude Code in the directory that will become (or already is) your team workspace
and run `/setup`. It is **idempotent and mode-aware**: it inspects what exists and does
only what's missing, so it is always safe to run.

**Team mode** (empty directory, first-ever run) walks the full sequence:

1. Resolves every required operation to a connected tool (failing loudly on gaps,
   asking you to choose on ambiguity — it never silently picks).
2. Creates the session store, writing the header row through the just-resolved binding
   so columns are guaranteed to match what actually gets written.
3. Records the artifact root (default `battle-buddy/`).
4. Prompts for the diary location and catalog repo.
5. Writes the `battleBuddy` config block into `.claude/settings.json`.
6. Scaffolds the workspace repo: `.claude/settings.json`, `.mcp.json` (env-var
   references only), a workspace `README.md`, and a `.gitignore` for local runtime
   state. Runs `git init`.
7. Finishes with a full `/doctor` pass and an end-to-end **smoke test** — a synthetic,
   already-closed session that proves every write and read path works through the real
   bindings, then cleans up after itself.

Then push the scaffolded workspace to a **private** repo in your org. The workspace is
your team's state, not battle-buddy's — it is never a fork of this repo.

**Responder mode** (you just cloned the team's workspace): clone, export your own
credential env vars (step 3), start Claude Code in the workspace, run `/setup`. It
provisions and verifies only you — team state is inherited from the clone. `/page` also
triggers this automatically whenever your local green stamp is missing or stale.

### Step 5 — Confirm with `/doctor`

```
/doctor
```

Run it between pages, never mid-incident. Every run produces one structured report: it is
either green, or it names specifically what's wrong (an unresolved
`capability.operation`, a stale binding, a store-schema mismatch, a plugin/config version
skew). Re-run it after any MCP roster change and after every plugin update.

### Daily use

- **Alert fires** → `/page` — briefing with triage verdict, prior history, deep links.
- **It's a real incident** → `/incident` — promotes the open page session in place.
- **Wrapping up** → `/close` — approve the drafted diary entry (causal fields are
  proposals, never auto-asserted), persistence happens in order, local state clears only
  after read-back confirms.

## Development setup

Contributor setup is separate from the responder path above — the test harness is
dev-only and never ships.

```bash
git clone https://github.com/richardhorvath11/battle-buddy.git
cd battle-buddy
python3 -m venv .venv && source .venv/bin/activate
pip install pytest
make verify
```

`make verify` is **the** gate (Constitution VIII): it runs both hermetic test layers —
unit tests on hooks/helpers as pure functions, and contract tests against
`tools/bb-mock-mcp`, a stdio mock server that is the operation contract's executable
spec. No credentials, no network. Run it before claiming any task done, before every
commit and push. CI ([`.github/workflows/verify.yml`](.github/workflows/verify.yml))
invokes the exact same targets: unit on Python 3.9 (the shipped-code floor) and 3.12,
contract on 3.12.

Useful narrower invocations:

```bash
make test-unit                                   # layer 1 only
make test-contract                               # layer 2 only
pytest tests/contract/test_doctor_checks.py -q   # single file
claude plugin validate .                         # manifest/frontmatter lint
```

To exercise the hooks in a live session, install the plugin from your working copy —
[`docs/local-plugin-testing.md`](docs/local-plugin-testing.md) covers the wiring,
verification table, and cache-refresh steps.

Feature work flows through spec-kit: each vertical slice gets spec → plan → tasks →
implement under `specs/NNN-*/`. Read [`AGENTS.md`](AGENTS.md) end-to-end before touching
anything; the hard invariants live in
[`.specify/memory/constitution.md`](.specify/memory/constitution.md).

## Repository layout

```
commands/     /page /incident /close /doctor /setup
agents/       triage, deep-investigator, log-diver, deploy-analyst, dependency-checker
skills/       session-store, investigation, catalog, diary conventions
hooks/        deterministic layer: deny guardrails, tool trace, session guards
bin/          bb-fingerprint, bb-validate, bb-shell (+ interface docs)
manifest/     capabilities.json — the operation contract /doctor resolves against
templates/    mcp.recommended.json, session-sheet.md
tools/        bb-mock-mcp — dev-only mock MCP server (never shipped)
tests/        unit / contract / scenario layers + fixtures and helpers
specs/        per-slice specs (spec-kit), slices 001–009 landed
docs/         local-plugin-testing.md, test-plan.md
```

## Documentation map

| Document | Read it when |
|---|---|
| [`oncall-harness-requirements.md`](oncall-harness-requirements.md) | You want the *what and why* (PRD v0.9) |
| [`bb-technical-design.md`](bb-technical-design.md) | You want the *how*: architecture, schemas, decision log, testing strategy |
| [`AGENTS.md`](AGENTS.md) | You (human or agent) are about to change code |
| [`.specify/memory/constitution.md`](.specify/memory/constitution.md) | You need the rules no change may break |
| [`docs/local-plugin-testing.md`](docs/local-plugin-testing.md) | You want the plugin's hooks firing on your machine |
