# Research & Plan-Time Pins — Doctor & Setup (slice 4)

Every "pinned at plan time" clause in the spec's Assumptions resolves here. Sources are
in-repo authorities (design doc, constitution, slice-1/2/3 contracts and shipped docs);
no external unknowns. Each entry: Decision / Rationale / Alternatives considered.

## R1 — Doctor report artifact shape (`bb.doctor.report.v1`)

**Decision**: The structured report FR-004 pins is a JSON document, schema
`bb.doctor.report.v1`, normatively defined in `contracts/doctor-protocol.md`. Top level:
`{schema, outcome, checks, reduced_features, migrations}` (the binding map is a
config-block artifact, not a report field) where `outcome` ∈
`green | red`; `checks` is a list with **one entry per resolved operation and one per
verification check**, each `{id, kind, capability?, op?, status, detail, candidates?}`
with `kind` ∈ `binding | probe | config | version | shell` and `status` ∈
`ok | fail | skip | ambiguous`; `reduced_features` lists `{capability, disabled}` for
missing optional capabilities; `migrations` lists exact migration strings for version-seam
failures. Green-with-reduced-features is `outcome: green` + non-empty `reduced_features`
(the spec's "otherwise green" reading); any required gap or failed check forces `red`.

**Rationale**: FR-004 demands tests assert on the report, never prose — the per-check
granularity is exactly what the write log cannot see (read-shaped probes leave no write
log entries; spec FR-011 names the report as their oracle). The `ambiguous` status carries
the multi-match candidate list (FR-002's explicit-choice surface).

**Alternatives**: prose report with a green/red exit signal — rejected: untestable
(Constitution VIII, artifacts-never-prose); folding reduced-features into `checks` only —
rejected: US2's acceptance asserts on the exact disabled-features list, a first-class
field keeps that assertion direct.

## R2 — Green-stamp location and shape (`bb.stamp.v1`)

**Decision**: The last-green-doctor stamp is `.bb-doctor-stamp.json` at the workspace
root, schema `bb.stamp.v1`: `{schema, at, plugin_version, roster_hash}`. It is a runtime
dropping per design §2.1 — gitignored (the scaffolded workspace `.gitignore` lists it;
this repo's `.gitignore` gains the same line). It deliberately does **not** live in
`.bb-session/`: that directory is session-scoped and deleted on confirmed close
(local-state protocol v1), while the stamp must survive across sessions per responder per
machine.

**Rationale**: §2.1 groups the stamp with gitignored runtime droppings; protocol v1's
deletion-is-cleared rule makes `.bb-session/` a wrong home. A single root-level file keeps
the slice-5 preflight read trivial (one stat + parse, no probes — NFR-1).

**Alternatives**: `.bb-session/stamp.json` — rejected (deleted at close);
a `~/.battle-buddy/` home-dir stamp — rejected: "per machine *per workspace*" scoping is
what the preflight needs, and a home-dir file would leak state across teams' workspaces.

## R3 — Roster-hash input

**Decision**: `roster_hash` = first 16 hex chars of SHA-256 over the canonical JSON
serialization (sorted keys, `,`/`:` separators, UTF-8) of the workspace roster file's
server entries — the `.mcp.json` `mcpServers` map exactly as committed, with `${ENV_VAR}`
references as literal strings (never resolved values). Computed from the local file only.

**Rationale**: The stamp is evaluated by a 3am preflight that must not probe or touch the
network (FR-005, D-15) — so the hash can only be over local roster facts. This also makes
the spec's edge case fall out naturally: a server-side schema change leaves the local
roster file — and therefore the hash — unchanged; drift surfaces at the next doctor run.
16-hex SHA-256 prefix matches the house fingerprint idiom (D-4). Hashing literal env-var
references keeps secrets out of the hash input by construction.

**Alternatives**: hashing the live `describe()` registry surface — rejected: requires
connected servers at preflight time, reintroducing 3am probes; hashing resolved env
values — rejected: secret material in a hash input, and token rotation would spuriously
invalidate the stamp (token problems are what responder-mode probes are for).

## R4 — Config block shape (`bb.config.v1`)

**Decision**: The `battleBuddy` block in the workspace `.claude/settings.json` keeps the
two keys slice 2 already reads **unchanged at their protocol-v1 paths** (`bindings`,
`budgets.triageTurnCap`) and adds: `configVersion` ("bb.config.v1" — the §2.1 config-block
version field), `pluginPin` (plugin version string the workspace expects), `store`
(`{url, schemaVersion}`), `diary` (`{url}`), `catalog` (`{repo}`), `artifactRoot`
(the artifact-store path prefix, default `battle-buddy/` per slice-3 layout), and `shell`
(`{adapter}` — presence means configured; slice 9 owns adapter semantics). Normative table
in `contracts/doctor-protocol.md`.

**Rationale**: The local-state protocol's config table is a published contract with
consumers (tripwire, trace capability classification); extending it additively at the same
paths means slice 2 needs zero changes. `configVersion` and `store.schemaVersion` are the
two ends of the §2.1 versioned seam doctor polices.

**Alternatives**: a separate config file owned by battle-buddy — rejected: D-10 pins
`.claude/settings.json` as the native surface; nesting bindings under `store` — rejected:
would break the shipped slice-2 readers.

## R5 — Header create-vs-validate fixture surface

**Decision**: Contract v1 has no header concept, so the create-vs-validate decision
protocol is exercised against a fixture surface: `FixtureHeaderStore` in
`tests/helpers/doctor_fixtures.py`, holding `header` (an ordered cell list or `None` for
an empty store) and a write log. Header representation: the slice-3 column names **in
schema.md order** followed by the version-sentinel cell holding `bb.schema.v1` (schema.md
"Live-Sheet representation": row 1, one column right of the last schema column). The
column authority is `store_flows.COLUMN_NAMES` — already mechanically cross-checked
against `schema.md` by the slice-3 SC-006 test, so this slice inherits the no-drift
guarantee instead of re-parsing the doc.

**Rationale**: The spec pins exactly this move ("fixture surfaces pinned at plan time");
reusing `COLUMN_NAMES` gives one authority chain: schema.md → SC-006 cross-check →
`COLUMN_NAMES` → header fixture.

**Alternatives**: extending the mock with a header op — rejected: contract v1 is slice-1's
artifact and the real stores' header is a convention over a plain row, not an operation;
re-parsing schema.md in this slice's tests — rejected: duplicates the SC-006 parser.

## R6 — Benign-probe table

**Decision**: One read-shaped probe per capability, pinned in
`contracts/doctor-protocol.md` with literal operation-contract payloads: storage →
`read_records` with `{"filter": {"session_id": "bb-doctor-probe"}}` (empty result
passes); diary → `read_recent` with `{"n": 1}`; alerting → `list_alert_history` with
`{"filter": {"alert_id": "bb-doctor-probe"}}` (empty passes). `artifacts` has no
read-shaped entry op (`get_file` needs a pre-existing link), so **all artifacts ops are
schema-match-only at doctor time**; mutating ops everywhere (`append_record`,
`update_record`, `put_file`, `append_entry`) are schema-matched at doctor time and
exercised end-to-end only by team-mode setup's smoke test. Probes assert reachability and
shape, never data presence.

**Rationale**: Spec Assumption "benign probes are read-shaped" verbatim; the sentinel-ID
filters guarantee benignity (worst case: empty result) while still round-tripping the
operation.

**Alternatives**: probing `get_alert` with a real alert ID — rejected: needs live data to
pass, breaking "empty result passes"; a write-then-delete artifact probe — rejected:
contract has no delete, and mutating probes contradict the pinned benignity rule.

## R7 — Manifest optional half: contract v1 extension **deferred**

**Decision**: `manifest/capabilities.json` (`bb.capabilities.v1`) declares the required
half **derived from** `tools/bb-mock-mcp/contract.json` (a contract test asserts
capability/op/shape fidelity between the two) and the optional half (`code`:
`read_file`, `list_commits(window)`, `search`; `observability`: `query_metrics`,
`search_logs`, each with `enables` lists) authored from design §7.1 with shapes pinned
directly in the manifest. **Operation contract v1 is not extended** and the mock gains no
optional capabilities — the explicit deferral the spec Assumption allows, recorded here:
optional-op shapes become contract ops when the first consuming slice (7 — catalog/code,
or a future observability slice) lands. Resolution tests for optional-present rosters use
fixture registry surfaces (R8) instead of the mock.

**Rationale**: Extending slice-1's contract for operations nothing yet consumes would pin
shapes ahead of their first real consumer — the same premature-contract mistake the design
avoids elsewhere; the manifest itself is a fine authority for optional shapes until then.

**Alternatives**: extending contract.json now — rejected as above; omitting optional
shapes from the manifest — rejected: FR-001 requires shapes for every declared operation.

## R8 — Binding-resolution protocol inputs (roster fixtures over `describe()`)

**Decision**: The resolution protocol's input is a **roster surface**: a mapping
`tool_name → {input, output}` schema (per-tool, arbitrary names — e.g.
`mycorp_sheets.add_row`). Test rosters are built by a fixture builder in
`tests/helpers/doctor_fixtures.py` that pulls op shapes from the mock's `describe()`
(slice-1 FR-011 — the shape authority) and assigns them to fixture tool names, so roster
fixtures can never drift from contract v1. Scenario rosters: full-required,
missing-one-required, two-tools-one-op (ambiguity), with-optional (shapes from the
manifest per R7), drifted (a bound tool name absent). Matching in tests is deterministic
shape-equality — the tests pin the **protocol** (surface consumed, entry format written,
probe step, failure modes), never semantic match quality (D-7; spec Assumption
"semantic matching is agent-performed").

**Rationale**: Binding entries map operations to *tool names* the deterministic layer
reads (protocol v1 `bindings` table); a roster keyed by tool name is the minimal surface
that makes the written entry format non-degenerate while staying hermetic.

**Alternatives**: matching directly against `describe()`'s capability→op map — rejected:
tool name would collapse to the op name, making the binding-entry format assertion
(SC-002) vacuous.

## R9 — Executable form: `doctor_flows.py` + `setup_flows.py`

**Decision**: The commands' decision protocols get the same treatment slice 3 gave the
store conventions: dev-only flow modules `tests/helpers/doctor_flows.py` (resolution,
probes, config/version/shell checks, report assembly, stamp write/evaluate) and
`tests/helpers/setup_flows.py` (mode derivation by inspection, team-mode sequence,
responder-mode sequence, idempotent re-run, smoke test), each step citing the command-doc
section it executes. Contract tests drive these against the mock + fixture surfaces.

**Rationale**: Proven slice-3 pattern (`store_flows.py`); keeps command prose and its
executable specification mechanically converged without shipping any code (FR-012,
Constitution I).

**Alternatives**: asserting on command prose — rejected outright (Constitution VIII).

## R10 — Workspace-scaffold file set

**Decision**: Team-mode setup scaffolds exactly: `.claude/settings.json` (config block per
R4, including bindings and `pluginPin`), `.mcp.json` (team roster, tokens as `${ENV_VAR}`
references), `README.md` (push-to-private-org instructions + auth floor note), and
`.gitignore` (`.bb-session/`, `.bb-doctor-stamp.json`, `*.local.jsonl`). Zero upstream
content — no plugin files are ever copied in. Tests scaffold into a tmp dir and assert the
file set, the env-var-reference discipline (no secret-shaped values), and
zero-upstream-content.

**Rationale**: §2.1's "~4 files of pure team state" table verbatim, made testable. The
binding map's committed home is inside the config block (protocol v1 already reads it
there), so it is not a fifth file.

**Alternatives**: separate `bindings.json` — rejected: protocol v1 consumers read
`battleBuddy.bindings`, and two homes for one artifact invites drift.

## R11 — Version-seam compatibility rule (v1)

**Decision**: Compatibility in v1 is exact match: the installed plugin expects
`configVersion == "bb.config.v1"` and `store.schemaVersion == "bb.schema.v1"` (and the
store's live sentinel cell to equal it). Any mismatch is a `version`-kind check failure
whose `detail` is the exact migration string naming from-version, to-version, and remedy
(§2.1's example form: "store schema bb.schema.v1 → bb.schema.v2: run /setup --migrate").
Tests trigger it with fixture future versions; migration *execution* stays out of scope
(spec Assumption).

**Rationale**: Only one version of each contract exists; inventing a compatibility range
now would be speculation. The check's job this slice is precise *reporting* (FR-003).

## R12 — Shell round-trip check surface

**Decision**: Configured means `battleBuddy.shell.adapter` is present (R4). The check
calls a notify round-trip through a fixture adapter callable
(`tests/helpers/doctor_fixtures.py`): answering → `ok`; raising/unreachable → `fail`; key
absent → `skip` (skipped-not-failed, FR-003). The real `bb-shell` lands in slice 9; the
check's contract (key, statuses, skip semantics) is pinned now so slice 9 slots in
without touching doctor.

## R13 — FR-010 naming gate extension

**Decision**: Extend the slice-3 capability-naming scan (`test_skill_capability_naming.py`
mechanism) to the new shipped prose surfaces: `commands/*.md`, `manifest/`,
`templates/session-sheet.md` — with `templates/mcp.recommended.json` as the **single
allowed location** for concrete server names (FR-010) and therefore excluded from the
scan (plus a positive test that it is valid JSON naming at least the required
capabilities' worth of servers). Operation-name fidelity: command prose may name
operations only in forms that parse under the protocol's `capability.operation` key
format.

**Rationale**: FR-010 is this slice's Constitution VII gate; the slice-3 test already
knows how to scan shipped markdown for forbidden names — extending beats duplicating.

## R14 — Plugin-version source

**Decision**: At runtime the stamp's `plugin_version` and the seam check's "installed
plugin version" come from the plugin manifest (`.claude-plugin/plugin.json`, design §3.1)
— which does not exist in-tree yet (it ships with the bundle-assembly work, slice 5+). In
this slice every flow takes `plugin_version` as an explicit input and the contract doc
records the runtime source, so tests stay hermetic and no placeholder manifest ships.

**Rationale**: Inventing `.claude-plugin/plugin.json` now would ship bundle surface this
slice's spec doesn't own; an explicit parameter is honest and testable.
