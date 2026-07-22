# Quickstart: Diary Adapter (slice 8)

How to validate this slice, and the map from every requirement to the test that gates it.
Everything here is hermetic — no credentials, no network, no live diary.

## Prerequisites

```bash
pip install pytest          # the only dev dependency (slice 1 harness)
```

## Run it

```bash
make verify                                   # THE gate — both layers (Constitution VIII)
make test-contract                            # this slice's layer
pytest tests/contract/test_diary_format.py -q  # one module
pytest tests/contract/test_diary_format.py -q -k minimal_default   # one property
```

Expected: green. This slice adds nothing to `tests/unit/` — the unit layer runs at the
py3.9 shipped-code floor and proves future *shipped* code, and the reference encoding is dev
tooling (`tests/conftest.py`'s layer rule; slice-7 precedent).

## Validation scenarios

Each maps to a spec acceptance scenario and the module that gates it.

### US1 — the entry reads like the team wrote it (P1)

| Scenario | Gate |
|---|---|
| Configured template wins; **no recent-entry read is needed for formatting** (AS-1) | `test_diary_format.py` — resolution matrix row `template/*` asserts `source == "template"` and that no read is consumed |
| No template + consistent entries → structure mirrors observed headings, date format, field order (AS-2) | `test_diary_format.py` — `golden-structures.json`, field-for-field |
| Bold-only section labels are recognized as headings | `test_diary_format.py` — `entries-bold.json` golden |
| Inconsistent entries → freshest wins, drift surfaced | `test_diary_format.py` — `entries-inconsistent.json` + `entries_inconsistent` notice |
| Ambiguous numeric date → surfaced, never silently picked | `test_diary_format.py` — `entries-ambiguous-date.json` → `date_ambiguous`; `entries-disambiguating.json` resolves it |
| Malformed template (non-string / empty / whitespace) → falls back to match-recent, problem surfaced | `test_diary_format.py` — matrix rows `template-malformed/*` |
| Empty diary, no template → minimal default, offered as a template candidate | `test_diary_format.py` — `MINIMAL_DEFAULT` golden + `template_candidate` notice |
| Row fields never enter format resolution (AS-3, FR-003) | `test_diary_format.py` — `FORMAT_INPUT_KEYS` ∪ signature params disjoint from the row fields parsed out of `skills/session-store/references/schema.md`. Recorded honestly as an **accepted-weak** gate (data-model §9): the vocabularies are disjoint by ordinary English, not by construction; the non-vacuity half is what carries it |
| Ambiguous dates resolve pass-level, or surface | `test_diary_format.py` — `entries-ambiguous-date.json` vs `entries-disambiguating.json` |
| Extraction is bounded — a very long entry body never reaches the output | `test_diary_format.py` — in-test filler block, structure unchanged |
| Causal proposal labels survive format matching byte-preserved (FR-005) | `test_diary_format.py` — `entries-labeled-causal.json` through `apply_format`, byte-identical blocks |

### US2 — the first write lands and hands back its link (P1)

| Scenario | Gate |
|---|---|
| The append returns a stable link, and that link is what the flow hands onward for the row (AS-1) | `test_diary_write.py` — against `bb-mock-mcp`, across the encoding's `write_entry`, so the assertion has a subject rather than comparing a value to itself |
| Exactly one diary append per drafted close (SC-004) | `test_diary_write.py` — the mock's write log, filtered to `diary`, has length exactly 1. The close-*level* ordering claim is slice 5's (`test_close_flow.py`, `test_lifecycle_full_sim.py`), cited not re-asserted |
| Appends to the configured diary through the diary capability only — no creation, no alternate destinations (AS-2) | `test_diary_write.py` — the contract's diary op-set asserted **equal** to `{append_entry, read_recent}` (a subset assertion would go quiet on a future `create_diary`); `test_diary_prose.py` gates the prose half |
| A failed write surfaces the contract's uniform error envelope, unchanged | `test_diary_write.py` — the envelope passes through the encoding's `write_entry` untouched. The raw contract behavior is already gated by slice 1's `tests/contract/test_diary.py` |

### US3 — recent entries always arrive newest-first (P2)

| Scenario | Gate |
|---|---|
| `read_recent(5)` arrives newest-first and is consumed as-is (AS-1) | `test_diary_ordering.py` — seeded mock, full content sequence asserted, and the encoding's `entries[0]` is the freshest |
| No consumer-side re-sort anywhere (SC-005) | `test_diary_ordering.py` — source scan: the consumption functions contain no `sorted(` / `.sort(` / `reversed(`; `test_diary_prose.py` gates the prose half |
| Fewer than `n` entries → all available return, newest-first, matching proceeds (AS-2) | `test_diary_ordering.py` — `entries-short.json`; the mock's own short/empty-read behavior is already gated by slice 1's `tests/contract/test_diary.py` |
| Empty diary read → `[]`, and resolution takes the minimal-default path | `test_diary_ordering.py` + `test_diary_format.py` |

### Cross-cutting discipline

| Scenario | Gate |
|---|---|
| Zero concrete MCP server/tool names in the skill prose (SC-006) | `test_diary_prose.py` — the shared `DENY_PATTERNS` + `mcp__` hard fail + a positive control |
| Every backticked operation token is a real contract operation | `test_diary_prose.py` — against `tools/bb-mock-mcp/contract.json` |
| The ordering commitment is stated, and no consumer-side re-sort directive appears | `test_diary_prose.py` — positive + masked negative gate |
| Every skill directory is covered by a naming scan | `tests/contract/test_catalog_prose.py`'s existing guard — `"diary"` is registered in the same task that lands the scan |
| Nothing executable ships (FR-008) | `test_diary_prose.py` — `skills/diary/` holds no `*.py`; `tests/helpers/diary_reference.py` is named by no glob in `tests/fixtures/packaging/intended-bundle.json` |
| Consumed boundaries are declared, not re-implemented (FR-008) | `test_diary_prose.py` — the skill's non-goals name close-flow ownership of retry/approval and slice 3's ownership of `diary_url`/`diary_pending` |

## Requirement → test map (SC-001)

| FR | Gated by |
|---|---|
| FR-001 interface, contract bridge, error envelope | `test_diary_write.py` (link + envelope), `test_diary_prose.py` (op fidelity) |
| FR-002 format resolution + extraction + defaults | `test_diary_format.py` (full matrix + goldens) |
| FR-003 row unaffected by diary formatting | `test_diary_format.py` (input-signature property) |
| FR-004 configured diary via the diary capability, append-only | `test_diary_write.py` (op-set), `test_diary_prose.py` (no creation, no alternate destination, deferrals stated) |
| FR-005 drafting handoff + label pass-through | `test_diary_format.py` (byte-preservation), `test_diary_prose.py` (the input contract, and that the close-time row update is not among its inputs) |
| FR-006 capability-only naming | `test_diary_prose.py` |
| FR-007 hermetic coverage | this table + `make verify` |
| FR-008 prose and tests only; consumed boundaries | `test_diary_prose.py` (packaging ratchet + non-goals) |

| SC | Gated by |
|---|---|
| SC-001 every FR → ≥1 passing test | the table above |
| SC-002 100% of format-resolution fixtures classify correctly | `resolution-matrix.json`, fully parametrized |
| SC-003 100% of structure-extraction goldens match | `golden-structures.json`, field-for-field |
| SC-004 returned link == value handed onward; exactly one append | `test_diary_write.py` |
| SC-005 zero re-sort steps; newest-first end-to-end | `test_diary_ordering.py` + `test_diary_prose.py` |
| SC-006 zero concrete server/tool names | `test_diary_prose.py` |

## What is deliberately **not** validated here

Whether a live agent *drafts well* — whether the entry reads naturally, whether the prose is
good — is scenario-harness territory (design §10), not CI. This slice's CI instrument is a
**rules-coherence gate**: it proves the documented decision and extraction rules are
coherent and correctly encoded over fixtures. It proves nothing about agent behavior. That
boundary is the spec's own testing model, inherited from slice 7.

Three further things are pinned here but have **no landed consumer**, and the map above does
not pretend otherwise (research R14): `battleBuddy.diary.recentEntries` has no reader — slice
5's close-flow encoding hardcodes the depth; the four notice kinds are emitted but nothing in
`commands/close.md` receives them; and slice 5's `_render_draft_entry` stand-in still stands.
None blocks an FR or SC of this slice; all three would otherwise be assumed handled.
