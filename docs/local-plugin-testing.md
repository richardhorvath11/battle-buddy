# Local plugin testing

How to load battle-buddy as a real Claude Code plugin on your own machine so the
commands, agents, skills, and — critically — the four hook events actually fire. This is
the wiring step every interactive (Tier 2) test scenario depends on.

Dev documentation, not shipped plugin surface (not in the `intended-bundle` globs).

## Why this exists

`hooks/hooks.json` invokes each hook as `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/<hook>.py"`.
`${CLAUDE_PLUGIN_ROOT}` is set **only** when Claude Code loads the plugin through its
plugin system — it is not set if you merely open the repo. So to exercise the hooks in a
live session you install the plugin locally. The repo doubles as a single-plugin
marketplace (`.claude-plugin/marketplace.json`) precisely so this is one command.

## Validate the manifests

Always run this after touching `.claude-plugin/*.json`, any command/agent/skill
frontmatter, or `hooks/hooks.json`:

```bash
claude plugin validate .            # errors on broken frontmatter, missing metadata
claude plugin validate . --strict   # CI-grade: warnings become failures
```

`validate` catches what the pytest layers cannot — e.g. a `description:` frontmatter value
containing an unquoted `: ` (colon-space) parses as a nested YAML key and the component
loads with **empty metadata**, silently. Quote such values.

Expected on a clean tree: `✔ Validation passed with warnings`. The one remaining warning —
`CLAUDE.md at the plugin root is not loaded as project context` — is benign: `CLAUDE.md`
is a dev instruction file and is not in the shipped bundle. (This is why `--strict` exits
1; that single warning is unavoidable without removing `CLAUDE.md` from the root.)

## Install the plugin locally

From the repo root:

```bash
claude plugin marketplace add ./                 # register this repo as a marketplace
claude plugin install battle-buddy@battle-buddy  # install the plugin from it
claude plugin list                               # → battle-buddy@battle-buddy  ✔ enabled
```

Confirm the component inventory and that all four hook events registered:

```bash
claude plugin details battle-buddy@battle-buddy
# Hooks (4)  PreToolUse, PostToolUse, SessionStart, SessionEnd
# Agents (5) triage, deep-investigator, log-diver, deploy-analyst, dependency-checker
```

The plugin is cached at
`~/.claude/plugins/cache/battle-buddy/battle-buddy/<version>/`; that path is the
`${CLAUDE_PLUGIN_ROOT}` the hooks resolve against at runtime.

**Re-installing after a code change.** The cache is keyed by the `version` in
`.claude-plugin/plugin.json`. To pick up edits, either bump that version, or:

```bash
claude plugin marketplace update battle-buddy
claude plugin update battle-buddy          # restart Claude Code to apply
```

## Verify the hooks actually fire

Registration (above) is necessary but not sufficient — confirm each event executes. The
definitive check is a live session, but you can prove the wiring resolves without one by
running the exact command `hooks.json` invokes, with `${CLAUDE_PLUGIN_ROOT}` set:

```bash
export CLAUDE_PLUGIN_ROOT=~/.claude/plugins/cache/battle-buddy/battle-buddy/0.9.0

# PreToolUse deny layer — expect exit 2
echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"dd if=/dev/zero of=/dev/sda"}}' \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/guardrail_deny.py"; echo "exit=$?"

# SessionStart config warning (FR-015) — expect a systemMessage on stdout
echo '{"hook_event_name":"SessionStart"}' | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/session_guard.py"
```

In a live session, the four events map to observable behavior:

| Event | Hook | How to observe it firing |
|---|---|---|
| PreToolUse | `guardrail_deny.py`, `tool_trace.py` | Ask the agent to run a deny-class command (e.g. `dd` to a device) → blocked. Turn-cap denial appears when a budgeted triage exceeds its cap |
| PostToolUse | `tool_trace.py` | After any tool call, `.bb-session/trace.jsonl` gains a line; an injection directive from an untrusted-capability result trips the tripwire |
| SessionStart | `session_guard.py` | Start a session outside a configured workspace → the "no workspace config block" notice |
| SessionEnd | `session_guard.py` | End a session with an unconfirmed/open session marker → "session row not persisted — run /close" (the D-11 backstop) |

A silently-dead hook is the most dangerous false green in the repo — if a deny-class
command executes, or ending an open session produces no D-11 warning, stop and fix the
wiring before trusting any other result.

## Clean up

The marketplace and install are written to **user scope** (`~/.claude`), so they persist
across sessions and projects until removed:

```bash
claude plugin uninstall battle-buddy@battle-buddy
claude plugin marketplace remove battle-buddy
```

## Distribution note

The same `.claude-plugin/marketplace.json` lets anyone install from the published repo:

```bash
claude plugin marketplace add richardhorvath11/battle-buddy
claude plugin install battle-buddy@battle-buddy
```

This matches the design's deployment model (§2.1): the plugin is delivered upstream via a
marketplace; a team's workspace repo (scaffolded by `/setup`) is separate and never a fork.
