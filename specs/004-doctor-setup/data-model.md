# Data Model — Doctor & Setup (slice 4)

Entities this slice defines or consumes. Normative shapes live in
[`contracts/doctor-protocol.md`](contracts/doctor-protocol.md); this file maps entities →
fields → validation rules → consumers, and pins the fixture surfaces.

## Shipped artifacts

### Capability manifest — `manifest/capabilities.json` (`bb.capabilities.v1`)

| Field | Rule |
|---|---|
| `schema` | `"bb.capabilities.v1"` |
| `required.{storage,artifacts,diary,alerting}.ops` | Names + `{input, output}` shapes identical to `contract.json` (fidelity test); `artifacts.get_file` excluded (test-only op) |
| `optional.{code,observability}.ops` | Shapes authored from design §7.1 (normative in the manifest until promoted — research R7) |
| `optional.*.enables` | Feature lists driving `reduced_features` reporting |

Consumers: doctor resolution (tests), FR-004 reduced-features reporting, future slices 7+.

### Command prose — `commands/doctor.md`, `commands/setup.md`

Capability/operation language only (FR-010); each documented step is executed by a flow
helper (research R9). First shipped content in `commands/`.

### Templates — `templates/mcp.recommended.json`, `templates/session-sheet.md`

`mcp.recommended.json`: the one shipped location where concrete MCP server names may
appear (FR-010); a default roster with `${ENV_VAR}` token refs. `session-sheet.md`:
reference documentation for manual store setup — explicitly *not* the setup path (§7.3).

## Written artifacts (produced at runtime by the commands' conventions)

### Doctor report (`bb.doctor.report.v1`)

`{schema, outcome: green|red, checks[], reduced_features[], migrations[]}`; check =
`{id, kind: binding|probe|config|version|shell, capability?, op?, status:
ok|fail|skip|ambiguous, detail, candidates?}`.

Validation rules: outcome `red` iff any required check `fail` or unresolved `ambiguous`;
one `binding` check per manifest op; one `probe` check per probe attempted; `candidates`
only on `ambiguous`; `migrations` mirrors `version`-check failures. Consumer: contract
tests (the oracle read-shaped probes need — write log can't see reads).

### Binding map (in config block, `battleBuddy.bindings`)

Entries `capability.operation → tool_name`. Key format owned by local-state protocol v1;
parse rule: capability = prefix before first `.`. Consumers: slice-2 tripwire/trace
(shipped), every runtime call site (slices 5–9).

### Green stamp (`bb.stamp.v1`) — `.bb-doctor-stamp.json`, workspace root, gitignored

`{schema, at, plugin_version, roster_hash}`. State machine:

| State | Condition | Preflight behavior (slice 5) |
|---|---|---|
| fresh | `plugin_version` == installed && `roster_hash` == hash(current roster) | trust; no probes |
| stale | either field differs; or file missing/unparseable | auto-run responder-mode setup |

`at` is diagnostic only — never expiry-checked. Roster hash: 16-hex SHA-256 prefix over
canonical JSON of `.mcp.json` `mcpServers` (env-var refs literal).

### Config block (`bb.config.v1`) — `battleBuddy` in workspace `.claude/settings.json`

`configVersion`, `pluginPin`, `store{url, schemaVersion}`, `diary{url}`, `catalog{repo}`,
`artifactRoot`, `bindings`, `budgets.triageTurnCap`, `shell{adapter}`. Protocol-v1 keys
keep their paths (additive extension). Malformed ⇒ repair case, never absent.

### Smoke-test session row

`session_id = test-bb-setup-<ISO date>`, `session_type: test`, `status: closed`
(terminal at append — inert; slice-3 excludes `test` rows from every retrieval stage).
Exercises append_record → put_file → append_entry → record read-back (`read_records`),
all through resolved bindings; artifact success = returned link recorded on the row
(`get_file` is harness-only, never part of the documented path).

### Workspace scaffold (team mode)

Four files (`.claude/settings.json`, `.mcp.json`, `README.md`, `.gitignore`), zero
upstream content. Secrets only as `${ENV_VAR}` references.

## Setup mode derivation (state → mode)

Derived from artifacts only (FR-006): team scope = {config block, store header, artifact
root, binding map}; responder scope = {tokens, probe results, stamp}. Modes: team /
responder / already-set-up / repair (malformed config). Partial team state ⇒ create only
what is missing, validate the rest.

## Fixture surfaces (dev-only; pinned per spec Assumptions)

| Surface | Home | Stands in for |
|---|---|---|
| Roster fixtures (`tool_name → {input, output}`), built from `describe()` | `tests/helpers/doctor_fixtures.py` + `tests/fixtures/doctor/` | Live MCP tool-schema inspection |
| `FixtureHeaderStore` (`header: [cells] \| None`, write log) | `tests/helpers/doctor_fixtures.py` | Live store header row + sentinel |
| Fixture shell adapter (answering / raising / absent) | `tests/helpers/doctor_fixtures.py` | slice-9 `bb-shell notify` round-trip |
| Failing-probe injector (wraps the mock; designated capability's probe returns an error) | `tests/helpers/doctor_fixtures.py` | Responder-credential probe failure (contract has no auth error code — the injector stands in for permission failures) |
| Fixture catalog repo path (parseable / not) | existing `tests/fixtures/` scenario surface | Catalog repo parseability check |
| Config-block fixtures (valid, malformed, future-versioned) | `tests/fixtures/doctor/` | Workspace settings states |

Header cell authority: `store_flows.COLUMN_NAMES` + `bb.schema.v1` sentinel (research R5 —
inherits the SC-006 no-drift chain; this slice re-parses nothing).
