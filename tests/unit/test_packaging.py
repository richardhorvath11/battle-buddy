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

# Roots that must never appear in a shipped bundle: dev-only artifacts
# (Constitution I, Platform Constraints: the mock and all test tooling) and
# the session-local state directory (runtime-created, never shipped — slice-2
# T025's shipped-side exclusion).
FORBIDDEN_ROOTS = ("tests/", "tools/", ".bb-session/")
FORBIDDEN_SEGMENTS = ("fixtures/",)

# The slice-2 shipped components: the bundle must enumerate these roots or
# the plugin ships without its deterministic layer.
REQUIRED_ROOTS = ("hooks/**", "bin/**")


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
    ["tests/unit/**", "tools/**", "skills/fixtures/x.json", ".bb-session/**"],
    ids=["tests-root", "tools-root", "fixtures-segment", "bb-session-root"],
)
def test_forbidden_paths_are_flagged(glob):
    assert check_bundle({"bundle": [glob]}) == [glob]


# --- slice-2 shipped side (T025, SC-006): hooks/ and bin/ ship; the state
# --- dir and every dev-only root provably never do.


def test_intended_bundle_ships_the_deterministic_layer():
    manifest = load_fixture("packaging", "intended-bundle.json")
    for required in REQUIRED_ROOTS:
        assert required in manifest["bundle"], required


def test_intended_bundle_excludes_state_and_dev_roots():
    manifest = load_fixture("packaging", "intended-bundle.json")
    for glob in manifest["bundle"]:
        assert not glob.startswith(FORBIDDEN_ROOTS), glob
