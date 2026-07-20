# battle-buddy dev harness. `make verify` is THE gate (AGENTS.md, Constitution VIII):
# both hermetic test layers from design §10 — no credentials, no network.
#
# Green-but-loud rule (spec Story 1 AS-3): an empty or absent layer passes with a
# visible notice — never a silent green, never a hard failure for emptiness alone.
# pytest exit 5 means "no tests collected".

.PHONY: verify test-unit test-contract

verify: test-unit test-contract
	@echo "verify: green"

# Layer 1 — hooks/helpers as pure (stdin, state) -> (exit code, output) functions.
test-unit:
	@if [ -d tests/unit ]; then \
		pytest tests/unit -q; rc=$$?; \
		if [ $$rc -eq 5 ]; then \
			echo "test-unit: NO TESTS in tests/unit — green-but-loud (gate strictness grows as tests land)"; \
		elif [ $$rc -ne 0 ]; then \
			exit $$rc; \
		fi; \
	else \
		echo "test-unit: NO TESTS — tests/unit not present — green-but-loud (gate strictness grows as tests land)"; \
	fi

# Layer 2 — contract tests against bb-mock-mcp (the operation contract's executable spec).
test-contract:
	@if [ -d tests/contract ]; then \
		pytest tests/contract -q; rc=$$?; \
		if [ $$rc -eq 5 ]; then \
			echo "test-contract: NO TESTS in tests/contract — green-but-loud (gate strictness grows as tests land)"; \
		elif [ $$rc -ne 0 ]; then \
			exit $$rc; \
		fi; \
	else \
		echo "test-contract: NO TESTS — tests/contract not present — green-but-loud (gate strictness grows as tests land)"; \
	fi
