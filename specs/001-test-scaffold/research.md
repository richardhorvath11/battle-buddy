# Phase 0 Research: Test Scaffold & Mock MCP

No NEEDS CLARIFICATION markers existed in the Technical Context — the design doc
(`bb-technical-design.md`) and its decision log answer every question. This file records
the plan-level decisions with rationale and rejected alternatives.

## R1 — Mock architecture: in-process library with a schema registry, not a protocol server

**Decision**: `bb-mock-mcp` is a plain Python package (`tools/bb-mock-mcp/`) used in-process
by tests. FR-011's tool-schema surface is a machine-readable **schema registry**: the mock
loads the operation contract (R5) and exposes per-capability operation names + input/output
shapes via an introspection API, without any operation being invoked.

**Rationale**: Hermetic speed (SC-002's 30s budget), zero protocol plumbing in slice 1, and
binding-resolution tests (slice 4) need schema *inspection and matching*, not wire-level MCP.
**Alternatives rejected**: a real stdio MCP server (protocol churn, slower tests, adds a
dependency for zero slice-1 benefit — can be added later as a thin wrapper over the same
package if a slice ever needs wire-level behavior); no schema surface (blocks slice 4's
hermetic binding-resolution tests — the round-1 review finding that produced FR-011).

## R2 — Python versions: dev floor 3.11, shipped-code floor 3.9, CI tests both

**Decision**: Dev tooling (mock, tests) targets Python 3.11+. CI runs the unit layer on a
{3.9, 3.12} matrix; the contract layer runs on 3.12 only.

**Rationale**: Shipped hooks/helpers (slice 2+) must run on macOS's command-line-tools
`python3` (3.9.x floor, design D-1) — so the unit layer, which tests future shipped code,
proves 3.9 compatibility from the start. The mock and contract tests are dev-only
(Constitution Platform Constraints exempt them), so they use modern Python freely.
**Alternative rejected**: single-version CI (would let 3.11+ syntax leak into shipped code
and surface only on a responder's machine).

## R3 — Test framework: pytest, table-driven via parametrize

**Decision**: pytest as the only test dependency; hook/helper unit tests are
`@pytest.mark.parametrize` tables over JSON fixture files (payload in → exit code/output
out); a shared `conftest.py` provides a fresh-mock factory fixture per test.

**Rationale**: Design §10 names the pattern (table-driven fixtures); pytest parametrize is
its native expression; per-test mock instances guarantee isolation without cleanup code.
**Alternative rejected**: unittest (more boilerplate for table-driven style, no fixture
ecosystem); any assertion-helper dependency (unneeded).

## R4 — CI: single GitHub Actions workflow, required check

**Decision**: `.github/workflows/verify.yml` — triggers on `pull_request` and push to
`main`; jobs: unit (matrix per R2) and contract; both invoke the same `make` targets
contributors run locally; marked as required checks for merge (FR-009/SC-005).

**Rationale**: CI must be a mirror of `make verify`, not a second implementation
(family-meals lesson: one verify loop, one exit code). GitHub is the confirmed platform
(spec Assumptions; remote configured).
**Alternative rejected**: separate CI-only scripts (drift between local and CI verdicts).

## R5 — The operation contract becomes a committed, machine-readable artifact

**Decision**: Phase 1 produces `contracts/operations.md` (this feature's contract document,
pinning concrete input/output shapes for every required operation — design §7.1's shapes
are `"..."` placeholders until now) and the implementation ships it as machine-readable
JSON (`tools/bb-mock-mcp/contract.json`) that both the mock's behavior and its FR-011
schema registry are loaded from.

**Rationale**: One source of truth: mock behavior, schema surface, and conformance tests
all derive from the same file, so they cannot drift independently. Slice 4's shipped
`manifest/capabilities.json` derives from this artifact (documented forward pointer).
**Alternative rejected**: shapes hardcoded in mock code (contract and executable spec drift
silently — exactly what the mock exists to prevent).

## R6 — Contract-level validation vs business-schema validation

**Decision**: The mock validates *contract shape* (required fields present, types correct,
size limit per the D-3 threshold) — it does NOT enforce the FR-21 session-record business
schema (fingerprint format, checkpoint schemas). Records are opaque field maps beyond the
contract-required keys.

**Rationale**: Business-schema enforcement is `bb-validate`'s job (slice 2) and the
session-store skill's concern (slice 3); baking it into the store mock would misplace the
design's layering (§5.4: validation is a caller-side pipeline step, not store behavior).

## R7 — Packaging check implementation (FR-010 / SC-007)

**Decision**: A unit test (`tests/unit/test_packaging.py`) that computes the shipped-bundle
file set from the plugin's manifest globs (once slice 4+ creates one; until then, from a
committed `packaging-manifest` fixture representing the intended bundle) and asserts no
`tests/`, `tools/`, or fixture path matches. The mis-packaged fixture case (SC-007) is a
second manifest fixture that deliberately includes a mock path and must fail.

**Rationale**: Mechanical, hermetic, and evolves naturally: when the real plugin manifest
appears, the test's input switches from fixture to real manifest with no logic change.
