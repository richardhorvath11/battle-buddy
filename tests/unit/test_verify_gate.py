"""Gate-behavior tests for the make targets (FR-001, Story 1 AS-1..3).

Each case copies the repo Makefile into a temp sandbox, arranges a layer
directory state (missing / empty / passing / failing), runs the make target via
subprocess, and asserts the exit code and the green-but-loud notice text.

Python 3.9-compatible (unit layer runs on the shipped-code floor).
"""

import subprocess
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LAYERS = ["unit", "contract"]

PASSING_TEST = "def test_present_and_green():\n    assert True\n"
FAILING_TEST = "def test_seeded_defect():\n    assert 1 == 2, 'deliberate defect'\n"


def run_make_target(sandbox, layer):
    shutil.copy(str(REPO_ROOT / "Makefile"), str(sandbox / "Makefile"))
    return subprocess.run(
        ["make", "test-" + layer],
        cwd=str(sandbox),
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("layer", LAYERS)
def test_missing_layer_dir_is_green_but_loud(tmp_path, layer):
    result = run_make_target(tmp_path, layer)
    assert result.returncode == 0
    assert "NO TESTS" in result.stdout
    assert "green-but-loud" in result.stdout


@pytest.mark.parametrize("layer", LAYERS)
def test_empty_layer_dir_is_green_but_loud(tmp_path, layer):
    (tmp_path / "tests" / layer).mkdir(parents=True)
    result = run_make_target(tmp_path, layer)
    assert result.returncode == 0
    assert "NO TESTS" in result.stdout
    assert "green-but-loud" in result.stdout


@pytest.mark.parametrize("layer", LAYERS)
def test_populated_layer_passes_without_notice(tmp_path, layer):
    layer_dir = tmp_path / "tests" / layer
    layer_dir.mkdir(parents=True)
    (layer_dir / "test_green.py").write_text(PASSING_TEST)
    result = run_make_target(tmp_path, layer)
    assert result.returncode == 0
    assert "NO TESTS" not in result.stdout


@pytest.mark.parametrize("layer", LAYERS)
def test_failing_layer_goes_red_naming_the_test(tmp_path, layer):
    layer_dir = tmp_path / "tests" / layer
    layer_dir.mkdir(parents=True)
    (layer_dir / "test_red.py").write_text(FAILING_TEST)
    result = run_make_target(tmp_path, layer)
    assert result.returncode != 0
    assert "test_seeded_defect" in result.stdout


def run_make_verify(sandbox):
    shutil.copy(str(REPO_ROOT / "Makefile"), str(sandbox / "Makefile"))
    return subprocess.run(
        ["make", "verify"], cwd=str(sandbox), capture_output=True, text=True
    )


def test_verify_aggregates_both_layers_green(tmp_path):
    for layer in LAYERS:
        layer_dir = tmp_path / "tests" / layer
        layer_dir.mkdir(parents=True)
        (layer_dir / "test_green.py").write_text(PASSING_TEST)
    result = run_make_verify(tmp_path)
    assert result.returncode == 0
    assert "verify: green" in result.stdout


@pytest.mark.parametrize("red_layer", LAYERS)
def test_verify_goes_red_when_either_layer_fails(tmp_path, red_layer):
    # FR-001: the single command exits zero only when all present tests pass —
    # a Makefile edit dropping a layer from `verify:` must not survive this.
    for layer in LAYERS:
        layer_dir = tmp_path / "tests" / layer
        layer_dir.mkdir(parents=True)
        content = FAILING_TEST if layer == red_layer else PASSING_TEST
        (layer_dir / "test_layer.py").write_text(content)
    result = run_make_verify(tmp_path)
    assert result.returncode != 0
    assert "verify: green" not in result.stdout
