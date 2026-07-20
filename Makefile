# battle-buddy dev harness. `make verify` is THE gate (AGENTS.md, Constitution VIII):
# both hermetic test layers from design §10 — no credentials, no network.

.PHONY: verify test-unit test-contract

verify: test-unit test-contract
	@echo "verify: green"

# Green-but-loud rule (spec 001 Story 1 AS-3): an empty layer (pytest exit 5,
# "no tests collected") passes with a visible notice — never silent green, never
# red for emptiness alone.

# Layer 1 — hooks/helpers as pure (stdin, state) -> (exit code, output) functions.
test-unit:
	@if [ -d tests/unit ]; then \
		pytest tests/unit -q; rc=$$?; \
		if [ $$rc -eq 5 ]; then \
			echo "test-unit: NOTICE — tests/unit contains no tests yet (green-but-loud)"; \
		elif [ $$rc -ne 0 ]; then \
			exit $$rc; \
		fi; \
	else \
		echo "test-unit: tests/unit not present yet (slice 1 pending) — skipping"; \
	fi

# Layer 2 — contract tests against bb-mock-mcp (the operation contract's executable spec).
test-contract:
	@if [ -d tests/contract ]; then \
		pytest tests/contract -q; rc=$$?; \
		if [ $$rc -eq 5 ]; then \
			echo "test-contract: NOTICE — tests/contract contains no tests yet (green-but-loud)"; \
		elif [ $$rc -ne 0 ]; then \
			exit $$rc; \
		fi; \
	else \
		echo "test-contract: tests/contract not present yet (slice 1 pending) — skipping"; \
	fi
