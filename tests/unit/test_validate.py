"""US2: bb-validate corpus classification (SC-004) and CLI behavior (R7).

Table-driven over tests/fixtures/validate/*.json: each fixture carries a
document and the exact multiset of rule names it must trigger (empty for
valid documents). One seeded violation per schema rule and per semantic
invariant; the multi-violation fixture proves one-pass completeness.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import bb_validate
from conftest import BIN_DIR, FIXTURES_DIR

VALIDATE_FILES = sorted((FIXTURES_DIR / "validate").glob("*.json"))


def load(fixture_path):
    with open(str(fixture_path), encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize(
    "fixture_path", VALIDATE_FILES, ids=[p.stem for p in VALIDATE_FILES]
)
def test_corpus_is_classified_exactly(fixture_path):
    fixture = load(fixture_path)
    violations = bb_validate.validate(fixture["document"])
    assert sorted(v["rule"] for v in violations) == sorted(
        fixture["expected_rules"]
    ), "%s: got %r" % (fixture["name"], violations)


@pytest.mark.parametrize(
    "fixture_path", VALIDATE_FILES, ids=[p.stem for p in VALIDATE_FILES]
)
def test_every_violation_record_is_machine_readable(fixture_path):
    fixture = load(fixture_path)
    for violation in bb_validate.validate(fixture["document"]):
        assert set(violation) == {"rule", "path", "message"}
        assert violation["path"].startswith("$")
        assert violation["rule"] and violation["message"]


def emittable_rules_from_source():
    """Every rule name the validator can emit, derived from the source rather
    than a hand-maintained list (TA4) — a new `_violation(..., "rule.x", ...)`
    with no fixture then actually fails this gate instead of slipping through
    a frozen roster that lacks it on both sides."""
    source = (BIN_DIR / "bb_validate.py").read_text(encoding="utf-8")
    return set(re.findall(r'_violation\(\s*violations,\s*"([^"]+)"', source))


def test_corpus_covers_every_rule_the_validator_can_emit():
    # The fixture corpus is the gate: if a rule exists in the validator but
    # no fixture triggers it, the corpus has a hole (SC-004's ">=1 violation
    # case per rule").
    emitted = set()
    for fixture_path in VALIDATE_FILES:
        emitted.update(load(fixture_path)["expected_rules"])
    can_emit = emittable_rules_from_source()
    assert can_emit, "roster derivation found no rules — regex drifted"
    missing = can_emit - emitted
    assert missing == set(), "rules with no violation fixture: %s" % sorted(missing)
    assert emitted <= can_emit, (
        "fixtures expect rules the validator cannot emit: %s"
        % sorted(emitted - can_emit)
    )


def test_one_pass_reports_all_violations_of_a_multi_violation_document():
    fixture = load(FIXTURES_DIR / "validate" / "multi-violation-verdict.json")
    violations = bb_validate.validate(fixture["document"])
    assert len(violations) >= 5
    assert len({v["rule"] for v in violations}) >= 5


def test_validate_never_mutates_its_input():
    fixture = load(FIXTURES_DIR / "validate" / "valid-verdict.json")
    document = fixture["document"]
    snapshot = json.dumps(document, sort_keys=True)
    bb_validate.validate(document)
    assert json.dumps(document, sort_keys=True) == snapshot


# --- CLI shim (R7): exit codes, JSON-lines output, byte identity ------------


def run_cli(args=(), stdin_text=None):
    return subprocess.run(
        [sys.executable, str(BIN_DIR / "bb-validate")] + list(args),
        input=stdin_text, capture_output=True, text=True, timeout=30,
    )


def test_cli_valid_document_exits_0_silently(tmp_path):
    fixture = load(FIXTURES_DIR / "validate" / "valid-ledger-deep-dive.json")
    result = run_cli(stdin_text=json.dumps(fixture["document"]))
    assert result.returncode == 0
    assert result.stdout == ""


def test_cli_file_input_leaves_the_file_byte_identical(tmp_path):
    fixture = load(FIXTURES_DIR / "validate" / "valid-verdict.json")
    doc_path = tmp_path / "verdict.json"
    doc_path.write_text(json.dumps(fixture["document"], indent=3), encoding="utf-8")
    before = doc_path.read_bytes()
    result = run_cli(args=[str(doc_path)])
    assert result.returncode == 0
    assert doc_path.read_bytes() == before


def test_cli_violations_exit_1_with_json_lines():
    fixture = load(
        FIXTURES_DIR / "validate" / "ledger-two-live-in-deep-dive.json"
    )
    result = run_cli(stdin_text=json.dumps(fixture["document"]))
    assert result.returncode == 1
    lines = [json.loads(line) for line in result.stdout.splitlines()]
    assert lines and all(
        set(line) == {"rule", "path", "message"} for line in lines
    )
    assert any(line["rule"] == "ledger.min_live_hypotheses" for line in lines)


@pytest.mark.parametrize(
    "garbage", ["", "{truncated", "not json at all", "\x00\x01\x02"],
    ids=["empty", "truncated", "prose", "binary"],
)
def test_cli_garbage_input_terminates_decisively_with_exit_2(garbage):
    result = run_cli(stdin_text=garbage)
    assert result.returncode == 2
    assert result.stderr.strip()


def test_cli_missing_file_is_a_usage_error():
    result = run_cli(args=["/nonexistent/never.json"])
    assert result.returncode == 2
    assert result.stderr.strip()


def test_cli_non_utf8_file_is_a_read_error_not_a_violation(tmp_path):
    # SF7: a UTF-16 file raises UnicodeDecodeError (a ValueError) on read; that
    # must exit 2 (read error), never 1 (the "violations found" code a scripted
    # caller would try to parse as JSON lines).
    doc_path = tmp_path / "verdict-utf16.json"
    doc_path.write_bytes('{"schema": "bb.verdict.v1"}'.encode("utf-16"))
    result = run_cli(args=[str(doc_path)])
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.strip()


def test_cli_too_many_arguments_is_a_usage_error():
    result = run_cli(args=["a.json", "b.json"])
    assert result.returncode == 2
