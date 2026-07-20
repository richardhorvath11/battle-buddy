"""Packaging boundary check (FR-010, SC-007, research R7).

The shipped plugin bundle must enumerate no test, mock, or tooling path.
``check_bundle`` is the mechanical check: pure function over a bundle
manifest's glob list. Until slice 4+ creates the real plugin manifest, the
intended-bundle fixture stands in for it — the test's input then switches to
the real manifest with no logic change.

Python 3.9-compatible (unit layer runs on the shipped-code floor).
"""

import pytest

from conftest import load_fixture

# Dev-only roots that must never appear in a shipped bundle (Constitution I,
# Platform Constraints: the mock and all test tooling are dev-only artifacts).
FORBIDDEN_ROOTS = ("tests/", "tools/")
FORBIDDEN_SEGMENTS = ("fixtures/",)


def check_bundle(manifest):
    """Return the list of bundle globs that violate the dev-only boundary."""
    violations = []
    for glob in manifest["bundle"]:
        if glob.startswith(FORBIDDEN_ROOTS) or any(
            segment in glob for segment in FORBIDDEN_SEGMENTS
        ):
            violations.append(glob)
    return violations


def test_intended_bundle_is_clean():
    manifest = load_fixture("packaging", "intended-bundle.json")
    assert check_bundle(manifest) == []


def test_mis_packaged_bundle_fails_naming_every_offender():
    manifest = load_fixture("packaging", "mis-packaged.json")
    assert check_bundle(manifest) == [
        "tools/bb-mock-mcp/**",
        "tests/fixtures/seeds/**",
        "tests/conftest.py",
    ]


@pytest.mark.parametrize(
    "glob",
    ["tests/unit/**", "tools/**", "skills/fixtures/x.json"],
    ids=["tests-root", "tools-root", "fixtures-segment"],
)
def test_forbidden_paths_are_flagged(glob):
    assert check_bundle({"bundle": [glob]}) == [glob]
