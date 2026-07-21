# Data Model: Deterministic Layer

Entities per the spec, concretized by research R1–R12 and the local-state protocol
(contracts/local-state-protocol.md — authoritative for file formats; not restated here).

## DenyClass (in-code table, `guardrail_deny.py`)

- `name` ∈ `destructive_filesystem | destructive_infra | credential_scan | verify_skip`
- `patterns`: compiled regex list over the tool-call command/input
- `context_rule`: optional (only `credential_scan`: requires `error:auth` within the
  protocol's 10-line trace window)
- `message`: block text naming the class (spec US1 AS-1)

## MisbehaviorFixture / BenignFixture

- JSON: `{name, source (documented incident/lineage), hook_payload, expected: "block"|"allow",
  expected_class?}` — directories are the corpora (research R3); benign membership per the
  spec's corpus rule (executed action safe, dangerous pattern only as data)

## TraceLine / TripwireEvent / SessionMarker / Counters / AgentRoles

- Per `contracts/local-state-protocol.md` (protocol `bb.local.v1`) — authoritative for
  seq semantics (line sequence, append-time atomic, denying hook appends `denied:*`),
  `counters.json` (seq + per-actor turn counts under flock), and `agents.json` (derived
  actor keys, convention-registered roles, unregistered ⇒ uncapped per R10)

## OutcomeClassifier (in `tool_trace.py`)

- Ordered heuristic table → `ok | error:auth | error:timeout | error:other` (R4); first
  match wins; classification fixtures pair each rule with a positive and negative case

## TripwireFamily (in `tool_trace.py`)

- `family` ∈ `instruction_override | execution_directive | base64_blob | toolcall_syntax`
- each: regex(es) + trip/no-trip fixture pair (R5); applies only to results of tools whose
  binding-map capability ∈ untrusted set v1 (`alerting`, `observability`)

## Verdict / Ledger documents (validated by `bb-validate`)

- `bb.verdict.v1`, `bb.ledger.v1` — field shapes per design §5.4 examples
- `ledger.phase` enumeration (R9): `triage-seeded | hypothesis-generation |
  evidence-gathering | deep-dive | resolution`; invariant window: `evidence-gathering`,
  `deep-dive`
- Violation record (validator output, one JSON line each):
  `{rule, path, message}` — `rule` names the schema rule or semantic invariant

## FingerprintCase (golden corpus)

- `{service, alert_type, expected}` (16 hex chars) — includes unicode, whitespace,
  UUID/hex/int/timestamp/hostname/IP substitution cases, near-collisions, empty and
  all-volatile inputs (flagged per spec edge case); rules version `bb.fp.v1` embedded in
  `bb-fingerprint` output metadata

## ConfigView (shared read helper)

- `turn_cap: int (default 15)`, `bindings: dict[str, str]|None` (keys
  `capability.operation`, values tool names — design §7.2 shape, R6),
  `config_present: bool`, `settings_error: bool` (settings file exists but is
  unreadable — distinct from a missing block, so user-facing warnings name the real
  cause), `notices: list[str]` (read-time diagnostics, surfaced on hook stderr) —
  computed once per invocation from `.claude/settings.json`; malformed ⇒ absent
  semantics; exposes `capabilities_for(tool) -> set[str]` (reverse lookup with prefix
  parse per the protocol doc)
