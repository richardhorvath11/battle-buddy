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

## Manual spot-checks (optional, not CI)

- Open `skills/investigation/SKILL.md`: the first section after the overview is the
  validation discipline (US1-AS1's ordering property, also asserted mechanically).
- Run a documented-invalid example through the CLI by hand:
  `bin/bb-validate <(pbpaste)` after copying an example block — exit 1 with the
  documented rule on stdout.
- Agent *behavior* (does triage actually answer in ≤2 minutes; does the ledger validate
  recalled candidates in practice) is deliberately not covered here — design §10's
  on-demand scenario harness owns it, outside CI (spec FR-012 boundary).
