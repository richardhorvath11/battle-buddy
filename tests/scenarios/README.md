# Scenario harness (Tier 2)

The on-demand, not-CI test layer from design §10: **fixture incidents** driven through a
live Claude Code session against the mock MCP server, judged afterwards by a
**deterministic assertion script** that inspects artifacts — never prose. This is the
layer that exercises what the hermetic suites cannot: the commands, agents, and skills as
an agent actually interprets them.

Dev tooling, never shipped (Constitution I; `tests/` is fenced by the packaging test).
Ownership: this README is the harness's design note — design §10 is its spec; no product
slice owns it (the `tools/bb-mock-mcp` precedent).

## Parts

| Part | Path | Role |
|---|---|---|
| Mock stdio server | `tools/bb-mock-mcp/server.py` | The Google layer's test double over real MCP transport; alien tool names; persists state for the judge |
| Assertion script | `assert_run.py` | Reads the persisted state + `.bb-session/`; runs the structural checks; exit 0/1 |
| Fixture bundles | `fixtures/<scenario>/` | `scenario.json` (declared inputs + expectations), `seed.json` (pre-seeded store/diary/alerts), `bindings.json` (reference binding map) |
| Run droppings | `state/` | gitignored; state files land here by convention |

## Running the `known-issue` scenario

One synthetic checkout-latency alert (`ALERT-123`) whose fingerprint exactly matches a
seeded prior resolved session — so retrieval hits, and triage must VALIDATE/INVALIDATE
the recall rather than parrot it.

```bash
# 0. once: install the plugin locally (docs/local-plugin-testing.md)

# 1. a clean test workspace, outside this repo
mkdir ~/bb-testbed && cd ~/bb-testbed
cat > .mcp.json <<'EOF'
{ "mcpServers": { "acme": {
    "command": "python3",
    "args": ["<REPO>/tools/bb-mock-mcp/server.py",
             "--state", "<REPO>/tests/scenarios/state/run.json",
             "--seed",  "<REPO>/tests/scenarios/fixtures/known-issue/seed.json"] } } }
EOF
# (replace <REPO> with this repo's absolute path)

# 2. drive it in a fresh session:  /setup  →  /doctor  →  /page ALERT-123  →  /close

# 3. judge the run
python3 <REPO>/tests/scenarios/assert_run.py \
    --state <REPO>/tests/scenarios/state/run.json \
    --workspace ~/bb-testbed \
    --scenario known-issue
```

Fault-injection variants (design §9 failure modes): prepend `BB_MOCK_FAIL=<cap.op>` to the
server's env in `.mcp.json` — e.g. `diary.append_entry` for the diary-down-at-close path
(the row must still land, `diary_pending: true`).

## The checks

| Check | Invariant | Source |
|---|---|---|
| `session-row-present` | the run persisted its session at all | §4 |
| `checkpoint-zero-valid` | `triage_verdict` passes `bin/bb-validate` | D-14, SM-4 |
| `fingerprint-correct` | row fingerprint == `bin/bb-fingerprint(service, alert_type)` | D-4 |
| `recall-validated` | every non-`fresh` candidate/hypothesis marked VALIDATED/INVALIDATED | Constitution VI |
| `diary-before-row` | diary write precedes the close-time row update in the write log | FR-4b |
| `ledger-anchored` | ≥3 live hypotheses, ≥1 `fresh` (skippable for triage-only scenarios via `optional_checks`) | Constitution VI |
| `trace-captured` | `.bb-session/trace.jsonl` present, seqs strictly increasing | D-12 |
| `marker-cleared` | session marker deleted by a confirmed close | D-11 |

The judge reuses the **shipped** helpers (`bb-validate`, `bb-fingerprint`) as
subprocesses, so it judges with exactly the implementations responders get.

## Honest caveat (design §10, verbatim intent)

A dev session isn't a clean room — ambient conversation context can influence agent
behavior, so local runs are *indicative, not reproducible*. The artifact assertions are
unaffected; trust the report, not your impression of the transcript. The headless driver
(`claude -p` wrapping the same fixtures + this same judge) is a planned follow-up wrapper,
not a rework.

## Adding a scenario

1. `fixtures/<name>/scenario.json` — declare `source_id`, `service`, `alert_type`
   (the fingerprint inputs), `seeded_session_ids`, and any `optional_checks`.
2. `fixtures/<name>/seed.json` — `load_seed` format (`records` / `artifacts` / `diary` /
   `alerts`); keep any seeded fingerprint in lockstep with the declared inputs
   (compute it: `python3 bin/bb-fingerprint <service> "<alert_type>"`).
3. Drive it, then `assert_run.py --scenario <name>`.
4. `tests/contract/test_assert_run.py` guards the judge itself; extend it if a new
   scenario needs a new check.
