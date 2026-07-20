# Operation Contract v1 (concrete shapes)

Pins the input/output shapes design §7.1 leaves as placeholders. This document is the
authority for slice 1; the implementation encodes it as `tools/bb-mock-mcp/contract.json`,
from which the mock's behavior, its FR-011 schema registry, and the conformance tests all
derive (research R5). Slice 4's shipped `manifest/capabilities.json` derives from this
artifact. Errors are uniform: `{error: {op, code, message}}` with `code` ∈
`invalid_input | not_found | limit_exceeded | unknown_op`; `message` names the violated
expectation (spec FR-004).

Conventions: `record` = field map; required keys marked ▸; other fields are opaque
(research R6). All string sizes are UTF-8 character counts. `link` = opaque stable string
unique per stored object. Timestamps ISO 8601.

## storage (required)

| Op | Input | Output | Errors |
|---|---|---|---|
| `append_record` | `record` — ▸`session_id` (str, non-empty, unique among non-superseded rows is NOT enforced here; duplicate handling is caller policy) | `{session_id}` | `invalid_input` (missing/empty session_id, non-map record, any single field > 45,000 chars — D-3 threshold, extra-contractual store emulation) |
| `read_records` | `filter` — optional field-equality map (e.g. `{fingerprint: "…"}`); empty/absent = all records | `{records: [...]}` in insertion order | `invalid_input` (non-map filter) |
| `update_record` | ▸`session_id`, ▸`fields` (partial field map to merge) | `{session_id}` | `not_found` (unknown session_id), `invalid_input` (empty fields; oversized field per D-3) |

## artifacts (required)

| Op | Input | Output | Errors |
|---|---|---|---|
| `put_file` | ▸`name` (str), ▸`content` (str) | `{link}` | `invalid_input` (empty name) |
| *(read-back for tests)* `get_file` | ▸`link` | `{name, content}` | `not_found` |

## diary (required)

| Op | Input | Output | Errors |
|---|---|---|---|
| `append_entry` | ▸`content` (str, non-empty) | `{link}` | `invalid_input` |
| `read_recent` | ▸`n` (int ≥ 1) | `{entries: [{link, content, at}]}` **most recent first** (design §6.2, v1.2.1) | `invalid_input` |

## alerting (required)

| Op | Input | Output | Errors |
|---|---|---|---|
| `get_alert` | ▸`alert_id` (str) | `{alert}` — field map incl. ▸`alert_id`, ▸`service_hint` (may be empty), ▸`description`, ▸`fired_at` | `not_found` |
| `list_alert_history` | ▸`filter` — field-equality map; supports at least `{alert_id}` and `{service_hint}` | `{alerts: [...]}` newest first | `invalid_input` (non-map filter) |

## Schema registry surface (FR-011)

`describe()` → `{capability: {op_name: {input: {field: type/required}, output: {...}}}}` for
every operation above, loaded from `contract.json`, invocable without any operation having
been called. This is the surface binding-resolution tests (slice 4) match against.

## Write log (test-inspection surface, not a contract op)

Every mutating op (`append_record`, `update_record`, `put_file`, `append_entry`, seed
loading excluded) appends `{seq, capability, op, summary}` to an ordered per-instance log,
readable by tests via direct state access (spec FR-005/FR-006). Read ops are not logged.
