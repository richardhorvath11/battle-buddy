# battle-buddy dev harness. `make verify` is THE gate (AGENTS.md, Constitution VIII):
# both hermetic test layers from design §10 — no credentials, no network.

.PHONY: verify test-unit test-contract

verify: test-unit test-contract
	@echo "verify: green"

# Layer 1 — hooks/helpers as pure (stdin, state) -> (exit code, output) functions.
test-unit:
	@if [ -d tests/unit ]; then \
		pytest tests/unit -q; \
	else \
		echo "test-unit: tests/unit not present yet (slice 1 pending) — skipping"; \
	fi

# Layer 2 — contract tests against bb-mock-mcp (the operation contract's executable spec).
test-contract:
	@if [ -d tests/contract ]; then \
		pytest tests/contract -q; \
	else \
		echo "test-contract: tests/contract not present yet (slice 1 pending) — skipping"; \
	fi
