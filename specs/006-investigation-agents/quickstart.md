# Quickstart — validating Investigation Agents & Skill

Everything runs hermetically under the standard gate:

```bash
make verify                # both layers, the pre-commit/pre-push gate
make test-contract         # this slice's new modules live here
pytest tests/contract/test_schemas_reference.py -q     # doc ↔ validator agreement
```

Prerequisites: repo checkout, `pip install pytest` (dev-only). No credentials, no
network, no live MCP servers.

## Scenario → test module map

| Scenario (spec) | Prove it with | Expected outcome |
|---|---|---|
| US1 — recalled memory is a hypothesis; skill and validator state one rule | `pytest tests/contract/test_schemas_reference.py -q` | Every `<!-- bb-example: … -->`-tagged example in `skills/investigation/references/schemas.md` classifies through the real `bb_validate.validate()` exactly as its marker documents (valid ⇒ no violations; invalid ⇒ named rule present); documented vocabularies equal the validator's constants |
| US1/US5 anchoring guard, phase-scoped (SC-004) | `pytest tests/unit/test_anchoring_matrix.py -q` | Both invariant phases × {2 live, 3 live none fresh, 3 live with fresh, dead fresh} classify with the documented rule present among the violations (membership — multi-rule cells are legitimate); early phases accept sparse/empty ledgers |
| US2 — triage pinned properties (FR-006) | `pytest tests/contract/test_agent_toolsets.py -q` (toolset half) and `pytest tests/contract/test_investigation_prose.py -q` (attribution half) | Triage toolset parses to exactly `{alerting, code, storage, observability}`, all read-only; turn-cap section names default 15 + `budgets.triageTurnCap` and attributes enforcement to the slice-2 hook |
| US3 — deep investigator pinned properties (FR-007) | same two modules | Checkpoint section cites the validator gate + slice-3 conventions; seeding, ≥1-fresh, ledger-updates-only anchors present; mutations marked approval-gated |
| US4 — specialists (FR-008) | same two modules | Each specialist single-purpose, read-only, findings-to-deep-investigator-only, `{url, excerpt}` finding contract; agent-teams note non-normative |
| US5 — launch conditions + role registration (FR-009/FR-010) | `pytest tests/contract/test_investigation_prose.py -q` and `pytest tests/contract/test_role_registration.py -q` | Exactly the three FR-5f conditions + confirm rule + `autoLaunchDeep`; simulated spawn write conforms to the protocol `agents.json` shape; seeded bad role rejected (SC-003) |
| SC-005 — zero concrete tool names | `pytest tests/contract/test_investigation_prose.py -q` | Naming scan (slice-3/4 mechanism) clean over all 5 agent docs + SKILL.md + 3 references |
| SC-006 — toolsets ⊆ manifest | `pytest tests/contract/test_agent_toolsets.py -q` | Every capability token in every toolset table exists in `manifest/capabilities.json` required ∪ optional |

## FR-001–FR-014 → test mapping (SC-001)

Every functional requirement maps to at least one passing hermetic test. The scenario
table above groups by user story; this table walks spec.md's FR list directly so the
SC-001 completeness claim is checkable FR by FR.

| FR | Requirement (short) | Test module(s) |
|---|---|---|
| FR-001 | Validation discipline leads the skill; loaded by orchestrator + both investigation agents | `test_investigation_prose.py` (discipline-first ordering gate; Overview loading-clause anchors) |
| FR-002 | Anchoring guard, phase-scoped, validator-enforced | `test_investigation_prose.py` (Anchoring guard section anchors) + `test_anchoring_matrix.py` (SC-004 matrix) + `test_schemas_reference.py` (phase-scoped worked examples) |
| FR-003 | Evidence rule — `{url, excerpt}`, prose-only invalid | `test_investigation_prose.py` (Evidence rules section + specialist Findings contract gates) + `test_schemas_reference.py` (evidence worked examples) |
| FR-004 | Capability-scoped untrusted-data rule (`alerting`/`observability`, delimiter, probabilistic framing) | `test_investigation_prose.py` (Untrusted telemetry section gates) |
| FR-005 | Briefing format + retrieval pointer; causal-field proposal discipline | `test_investigation_prose.py` (briefing causal anchor; retrieval pointer anchors) |
| FR-006 | Triage definition pins (model class, budget, toolset, four questions, verdict contract, re-invocation) | `test_agent_toolsets.py` (triage capability set exact + read-only) + `test_investigation_prose.py` (Budget/four-questions/Output contract/Re-invocation gates) |
| FR-007 | Deep-investigator pins (frontier class, open budget, approval-gated mutations, ledger ownership, checkpoint gate, seeding, ledger-updates-only) | `test_agent_toolsets.py` (capabilities ⊆ manifest, mutating rows approval-gated) + `test_investigation_prose.py` (Checkpointing/Seeding/Ledger ownership gates) |
| FR-008 | Specialist pins (single purpose, read-only, parallel, findings-to-deep-investigator-only, `{url, excerpt}`) | `test_agent_toolsets.py` (specialist capabilities ⊆ manifest, all read-only) + `test_investigation_prose.py` (Purpose/Findings contract gates; agent-teams non-normative note) |
| FR-009 | Deep-investigation launch conditions (a/b/c) + confirm rule + `autoLaunchDeep` | `test_investigation_prose.py` (Launch conditions section gates) |
| FR-010 | Spawn-time role registration; mechanism/policy split; fail-open | `test_investigation_prose.py` (Spawn flow and role registration section gates) + `test_role_registration.py` (SC-003 protocol-shape simulation) |
| FR-011 | Schemas reference is normative for `bb.verdict.v1`/`bb.ledger.v1`; validator is the implementation | `test_schemas_reference.py` (SC-002 doc↔validator consistency + vocabulary agreement) |
| FR-012 | Hermetic test coverage requirement itself (artifacts only, no credentials/network) | `test_schemas_reference.py` + `test_anchoring_matrix.py` + `test_role_registration.py` + `test_agent_toolsets.py` (the four modules jointly satisfy this — each asserts on parsed artifacts/validator output/protocol shapes, never prose opinion) |
| FR-013 | Zero concrete MCP server/tool names across all prose deliverables | `test_investigation_prose.py` (SC-005 naming scan — `mcp__` raw scan + deny-list scan, finalized over the nine-file floor at T022) |
| FR-014 | This slice ships prose + tests only, no runtime code | Structural, not behavior-testable directly: `tests/unit/test_packaging.py` proves the shipped bundle boundary excludes `tests/`/`tools/`/fixture paths, so the only Python this slice adds (all under `tests/`) can never ship; the absence of any non-prose, non-test file under `agents/`/`skills/investigation/` is the FR-014 claim itself, verified by inspection (T025's packaging walk) rather than a dedicated assertion |

## Manual spot-checks (optional, not CI)

- Open `skills/investigation/SKILL.md`: the first section after the overview is the
  validation discipline (US1-AS1's ordering property, also asserted mechanically).
- Run a documented-invalid example through the CLI by hand:
  `bin/bb-validate <(pbpaste)` after copying an example block — exit 1 with the
  documented rule on stdout.
- Agent *behavior* (does triage actually answer in ≤2 minutes; does the ledger validate
  recalled candidates in practice) is deliberately not covered here — design §10's
  on-demand scenario harness owns it, outside CI (spec FR-012 boundary).
