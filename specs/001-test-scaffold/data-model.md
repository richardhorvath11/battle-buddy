# Data Model: Test Scaffold & Mock MCP

Entities from the spec, concretized per research R1/R5/R6. All state is in-memory,
per-mock-instance (fresh instance per test via the conftest factory).

## MockRecordStore

- `records`: ordered list of field maps; ▸`session_id` required per contract
- Semantics: append preserves insertion order; `update_record` merges fields into the
  matching record (last-write-wins per field — deterministic final state; conflict
  *policy* is caller business logic, out of mock scope)
- Validation: contract shape only (research R6) + D-3 single-field size limit (45,000)

## MockArtifactStore

- `files`: map `link → {name, content}`; `link` = `"art://"` + monotonic counter
  (stable, opaque, deterministic across identical runs)

## MockDiary

- `entries`: ordered list `{link, content, at}`; `at` = injected logical clock (no wall
  clock — determinism); `read_recent(n)` returns last n, reversed (most recent first)

## MockAlerting

- `alerts`: map `alert_id → alert field map`; `history`: ordered list of alert field maps
- Seed-only (no mutating contract ops); `list_alert_history` filters newest first

## WriteLog

- `entries`: ordered `{seq, capability, op, summary}`; `seq` monotonic from 1 per instance
- Appended by every mutating contract op; seed loading bypasses it (seeds are precondition
  state, not scenario writes)

## SchemaRegistry (FR-011)

- Loaded from `contract.json` at instance creation; `describe()` returns the full
  per-capability operation schema map; never mutated at runtime

## SeedFixture

- JSON file: `{records: [...], artifacts: [{name, content}], diary: [...],
  alerts: {alerts: [...], history: [...]}}` — all keys optional
- Loading is all-or-nothing: any invalid entry aborts the load naming the offending entry
  (spec Story 3 AS-2); on success the mock contains exactly the seeded state
- Slice 1 ships ≥1 synthetic incident seed (an alert + its flap history + two prior
  session records, one sharing the alert's fingerprint field)

## State transitions

None persisted across tests by design — every test gets a fresh instance; the only ordered
state is insertion order and the write log's `seq`.
