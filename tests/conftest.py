"""Shared test plumbing for both hermetic layers (design §10).

- ``mock_mcp``: fresh bb-mock-mcp instance per test. The import happens lazily
  inside the fixture so the unit layer never imports the mock (layer separation:
  unit tests prove future shipped code, which must not depend on dev tooling).
- ``load_fixture``: JSON-fixture loader for table-driven parametrize (FR-007).

Everything here is hermetic: no network, no credentials, no external services.
"""

import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
MOCK_PKG_DIR = REPO_ROOT / "tools" / "bb-mock-mcp"

# Make tests/helpers importable from any layer (`from helpers... import ...`).
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))


def load_fixture(*relpath):
    """Load a JSON fixture from tests/fixtures/, e.g. load_fixture("unit", "selftest.json")."""
    path = FIXTURES_DIR.joinpath(*relpath)
    with open(str(path), encoding="utf-8") as f:
        return json.load(f)


def fixture_path(*relpath):
    """Absolute path to a fixture file — for loaders that take a path (e.g. load_seed)."""
    return FIXTURES_DIR.joinpath(*relpath)


@pytest.fixture
def mock_mcp_factory():
    """Callable producing fresh MockMcp instances (determinism tests need >1)."""

    def make():
        if str(MOCK_PKG_DIR) not in sys.path:
            sys.path.insert(0, str(MOCK_PKG_DIR))
        from bb_mock_mcp import MockMcp

        return MockMcp()

    return make


@pytest.fixture
def mock_mcp(mock_mcp_factory):
    """A fresh MockMcp per test — isolation without cleanup code (research R3)."""
    return mock_mcp_factory()
