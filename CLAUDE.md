# CLAUDE.md

Claude Code overlay for battle-buddy. Everything tool-neutral lives in `AGENTS.md` —
start there. Only Claude-specific notes go below.

@AGENTS.md

## Claude-only directives

- Spec-kit is the flow driver for slice work: `/speckit-specify` → `/speckit-plan` →
  `/speckit-tasks` → `/speckit-implement`. Superpowers process skills (brainstorming,
  writing-plans) stand down where spec-kit owns the flow.
- Run `make verify` before claiming any implementation task done (Constitution VIII).

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
`specs/008-diary-adapter/plan.md`
<!-- SPECKIT END -->
