# Doctor & Setup Protocol v1 (cross-slice contract)

Versioned contract for the artifacts `/doctor` and `/setup` produce and the rules later
slices consume — slice 5's `/page` preflight trusts the stamp defined here; the slice-2
deterministic layer reads the binding map written in the format restated here. The
shipped command prose (`commands/doctor.md`, `commands/setup.md`) is the runtime-facing
statement of these same rules; this document is the dev-side authority, and contract
tests exercise every assertion. Changes require a version bump of the affected `bb.*`
schema and a same-change update of every consumer.

## Capability manifest (`bb.capabilities.v1`)

`manifest/capabilities.json`, shipped in the plugin bundle. Top level:

```json
{
  "schema": "bb.capabilities.v1",
  "required": {"<capability>": {"ops": {"<op>": {"input": {...}, "output": {...}}}}},
  "optional": {"<capability>": {"ops": {...}, "enables": ["<feature>", ...]}}
}
```

- **Required half** (`storage`, `artifacts`, `diary`, `alerting`): the shipped projection
  of operation contract v1 — capability names, op names, and input/output shapes MUST
  match `tools/bb-mock-mcp/contract.json` exactly (a contract test enforces fidelity).
  The test-only op `artifacts.get_file` ("read-back for tests", operations.md) is **not**
  projected into the manifest — it is harness surface, not an integration requirement.
- **Optional half** (`code`, `observability`): ops and shapes authored from design §7.1,
  normative *here* until a consuming slice promotes them into the operation contract
  (research R7 records the deferral). `enables` lists the features disabled when the
  capability is absent: `code` → `["deploy correlation", "catalog", "runbook fetch"]`;
  `observability` → `["metric reads", "evidence deep-links"]`.

## Binding map (restated from local-state protocol v1)

Written by doctor into the workspace config block at `battleBuddy.bindings`: a map of
**`<capability>.<operation>` → tool name** (e.g.
`"storage.append_record": "mycorp_sheets.add_row"`). The key format is owned by the
slice-2 local-state protocol's config table; this slice writes it, never redefines it.
One entry per required operation; optional-capability entries appear only when resolved.
Committed with the workspace repo (bindings are team scope, D-13).

## Resolution protocol (doctor, per required operation)

Input surfaces: the capability manifest and the **roster surface** — the connected tools'
schemas, `tool_name → {input, output}` (hermetically: fixture rosters built from the
mock's `describe()` registry, slice-1 FR-011; live: MCP tool-schema inspection with
semantic matching by the agent, D-7 — match *quality* is out of deterministic scope, the
protocol below is not).

Per required operation, in order:

1. **Match**: collect candidate tools whose schemas can express the operation's shape.
2. **Zero candidates** → `binding` check `fail`, naming the operation; run outcome `red`.
3. **More than one candidate** → `binding` check `ambiguous`, carrying the candidate tool
   names; the binding entry is written only after an explicit choice (never a silent
   pick). An unresolved ambiguity leaves the run non-green.
4. **One candidate (or explicit choice)**: read-shaped ops are confirmed by the benign
   probe (table below); mutating ops by schema match (probe kind `skip` with
   `detail` recording schema-match-only; exercised end-to-end by setup's smoke test).
5. **Write** the binding entry in the exact key format above.

**Drift re-validation**: with a committed binding map, doctor re-checks each entry against
the current roster surface; an entry whose tool name is absent (or no longer
shape-compatible) is flagged as stale by name (`binding` check `fail`, `detail` naming the
stale entry) — never silently rewritten.

## Benign-probe table (research R6)

Payloads are the exact operation-contract invocation payloads (`read_records` and
`list_alert_history` take their map under the contract's `filter` key):

| Capability | Probe (read-shaped, literal payload) | Passes when |
|---|---|---|
| `storage` | `read_records` ← `{"filter": {"session_id": "bb-doctor-probe"}}` | call succeeds; empty result is a pass |
| `diary` | `read_recent` ← `{"n": 1}` | call succeeds; shape matches |
| `alerting` | `list_alert_history` ← `{"filter": {"alert_id": "bb-doctor-probe"}}` | call succeeds; empty result is a pass |
| `artifacts` | *(none — no read-shaped entry op)* | schema match only at doctor time |

Mutating ops (`append_record`, `update_record`, `put_file`, `append_entry`): schema match
at doctor time; end-to-end exercise belongs to team-mode setup's smoke test. Probes
assert reachability and shape, never data presence.

## Doctor report (`bb.doctor.report.v1`)

The structured per-run artifact (spec FR-004); the test oracle for read-shaped probe
outcomes. Produced by every doctor run (standalone or setup-invoked).

```json
{
  "schema": "bb.doctor.report.v1",
  "outcome": "green | red",
  "checks": [
    {"id": "binding.storage.append_record", "kind": "binding",
     "capability": "storage", "op": "append_record",
     "status": "ok | fail | skip | ambiguous",
     "detail": "<human-readable specifics; exact gap/mismatch/migration when not ok>",
     "candidates": ["<tool>", "..."]}
  ],
  "reduced_features": [{"capability": "code", "disabled": ["deploy correlation", "catalog", "runbook fetch"]}],
  "migrations": ["<exact migration string>", "..."]
}
```

- `kind` ∈ `binding | probe | config | version | shell`. One `binding` check per manifest
  operation considered; one `probe` check per probe attempted; `config` checks cover
  store-header validation (exact mismatch in `detail`), diary readability, catalog
  parseability, and config-block well-formedness; `version` checks cover the two seam
  comparisons (config block, store schema); `shell` is the notify round-trip
  (`skip` when no adapter configured).
- `candidates` appears only on `ambiguous`.
- **Outcome rule**: `red` iff any required-capability check is `fail` or any `ambiguous`
  is unresolved; missing optional capabilities never affect `outcome` — they populate
  `reduced_features` (exact `enables` lists of the missing capabilities). `migrations`
  mirrors every `version`-check failure's exact migration string.
- Tests assert on this artifact, never on prose.

## Green stamp (`bb.stamp.v1`)

Written on a green doctor run (outcome `green`); local only, never committed.

- **Location**: `.bb-doctor-stamp.json` at the workspace root (gitignored; a runtime
  dropping per design §2.1 — deliberately *outside* `.bb-session/`, which is deleted on
  close).
- **Shape**: `{"schema": "bb.stamp.v1", "at": "<ISO 8601>", "plugin_version": "<str>",
  "roster_hash": "<16 hex>"}`.
- **Roster hash**: first 16 hex chars of SHA-256 over the canonical JSON serialization
  (sorted keys, compact `,`/`:` separators, UTF-8) of the workspace `.mcp.json`
  `mcpServers` map as committed — `${ENV_VAR}` references as literal strings, never
  resolved values. Computed from the local file only; no network.
- **Staleness (the sole v1 rules)**: stale iff `plugin_version` differs from the installed
  plugin version **or** `roster_hash` differs from the hash of the current roster file.
  `at` is diagnostic — reported, never expiry-checked (a time window would reintroduce
  3am probes). A missing or unparseable stamp is stale.
- **Runtime version source**: the installed plugin's manifest version
  (`.claude-plugin/plugin.json` once the bundle ships — research R14); hermetic tests pass
  `plugin_version` explicitly.
- Slice 5's `/page` preflight consumes exactly these rules: fresh-and-matching → no
  probes; missing/stale → auto-run responder-mode setup.

## Config block (`bb.config.v1`)

The `battleBuddy` key in the workspace `.claude/settings.json`. Additive over the
local-state protocol v1 config table — the keys slice 2 reads keep their exact paths.

| Key | Type | Owner/consumer |
|---|---|---|
| `configVersion` | `"bb.config.v1"` | §2.1 seam; doctor `version` check |
| `pluginPin` | string | §2.1 plugin pin; workspace-declared expected plugin version |
| `store` | `{url, schemaVersion}` | setup writes; doctor validates header + sentinel against `schemaVersion` |
| `diary` | `{url}` | setup prompt; doctor readability check |
| `catalog` | `{repo}` | setup prompt; doctor parseability check |
| `artifactRoot` | string (default `battle-buddy/`) | slice-3 artifact-layout prefix |
| `bindings` | map `capability.operation` → tool name | **protocol v1 table — unchanged path** |
| `budgets.triageTurnCap` | int | **protocol v1 table — unchanged path** |
| `shell` | `{adapter}` — presence ⇒ configured | doctor `shell` check; slice 9 adapter |

**Malformed config block**: setup/doctor surface it as an explicit repair case
(`config` check `fail` naming the parse error), never treat it as absent — a deliberate,
recorded divergence from the slice-2 hooks' fail-open reading (a guardrail must not brick
a session; an onboarding wizard must not destroy state over a typo).

## Setup mode derivation (inspection, never a done-flag)

| Observed state | Mode |
|---|---|
| No config block | **team** — full sequence (resolve → store create/validate → artifact root → diary/catalog prompts → config write → scaffold → doctor + smoke test) |
| Config block present; this responder's probes fail or stamp missing/stale | **responder** — provision tokens, verify probes under this responder's credentials, write stamp; creates no team resources |
| Everything green | **already-set-up** — validate + report only; zero mutating operations |
| Config block present but malformed | **repair** — surfaced explicitly (above); never team mode |

Partial team state (e.g. config present, store header missing) does only what is missing;
existing resources are validated, never re-created.

## Store header create-vs-validate (team mode / doctor config check)

Header representation: the slice-3 schema columns in `schema.md` column-table order,
followed by the version-sentinel cell holding the schema version (`bb.schema.v1`) — one
column right of the last schema column, not a data column. Authority chain: `schema.md` →
SC-006 cross-check → `store_flows.COLUMN_NAMES` (research R5).

- **Empty store** → create: write the header row **through the resolved storage binding**.
- **Existing store, matching header + sentinel** → validate: zero writes.
- **Existing store, mismatch** → report the exact mismatch (missing/extra/misordered
  columns, wrong sentinel) with zero writes; never silently re-create.

## Smoke test (team mode, end of sequence)

A synthetic session, `session_type: test`, **`status: closed`** (terminal at append —
the row is inert, never a live session join-at-open could surface), session ID
`test-bb-setup-<ISO date>` (D-8 format), exercising exactly four paths through the
resolved bindings: record append → artifact write (under `<artifactRoot><session_id>/`)
→ diary append → **record read-back** (`read_records` through the storage binding,
confirming the appended row). Artifact write success is verified by the returned link
being recorded on the row — `get_file` is harness surface, not a resolved binding, so
tests may read the artifact back through the mock as an extra oracle but the documented
smoke path never invokes it. Slice-3 retrieval conventions permanently exclude
`session_type: test` rows; accumulation across repeated setups is cosmetic. Smoke-test
failure is a loud, specific failure of the run (it is the end-to-end exercise of every
mutating op the probes could only schema-match).

## Version-seam compatibility (v1)

Exact match (research R11): installed plugin expects `configVersion == bb.config.v1` and
`store.schemaVersion == bb.schema.v1` (and the live sentinel cell equal to it). Any
mismatch → `version` check `fail` with `detail` = the exact migration string:
`"<artifact> <found-version> → <expected-version>: <remedy>"`. Migration execution is out
of scope until a second version exists.

## Workspace scaffold (team mode; §2.1's file set)

Exactly four files, zero upstream content: `.claude/settings.json` (config block above),
`.mcp.json` (roster; tokens as `${ENV_VAR}` refs — secrets never enter the repo),
`README.md` (push-to-private-org instructions, auth floor), `.gitignore` (`.bb-session/`,
`.bb-doctor-stamp.json`, `*.local.jsonl`). `git init` locally; pushing is the team's
explicit act.
