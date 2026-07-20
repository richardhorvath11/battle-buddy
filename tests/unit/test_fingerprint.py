"""US3: bb-fingerprint golden corpus (SC-003) — the executable §5.2 rules.

Runs on both ends of the CI version matrix by virtue of the slice-1 workflow;
the seeded rule-change test proves the corpus actually trips on silent
normalization drift (the failure mode that breaks exact-match recall).
"""

import json
import re
import subprocess
import sys

import pytest

import bb_fingerprint
from conftest import BIN_DIR, load_fixture

CORPUS = load_fixture("fingerprint", "golden.json")
CASES = CORPUS["cases"]
BY_NAME = {case["name"]: case for case in CASES}


def test_corpus_is_non_empty():
    # TA5: an emptied/renamed corpus must not make the golden gate vanish as an
    # empty parametrize (skipped, suite green).
    assert len(CASES) >= 20
    assert CORPUS["identical_pairs"] and CORPUS["distinct_pairs"]


def test_corpus_version_matches_implementation():
    assert CORPUS["version"] == bb_fingerprint.VERSION == "bb.fp.v1"


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_golden_corpus_matches_exactly(case):
    result = bb_fingerprint.fingerprint(case["service"], case["alert_type"])
    assert result["service_normalized"] == case["normalized_service"]
    assert result["alert_type_normalized"] == case["normalized_alert_type"]
    assert result["fingerprint"] == case["fingerprint"]
    assert result["flags"] == case["flags"]
    assert result["version"] == CORPUS["version"]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_output_is_16_hex_chars_and_deterministic(case):
    first = bb_fingerprint.fingerprint(case["service"], case["alert_type"])
    second = bb_fingerprint.fingerprint(case["service"], case["alert_type"])
    assert first == second
    assert re.fullmatch(r"[0-9a-f]{16}", first["fingerprint"])


@pytest.mark.parametrize(
    "pair", CORPUS["identical_pairs"], ids=["-vs-".join(p) for p in CORPUS["identical_pairs"]]
)
def test_volatile_variants_fingerprint_identically(pair):
    a, b = (BY_NAME[name] for name in pair)
    fp_a = bb_fingerprint.fingerprint(a["service"], a["alert_type"])
    fp_b = bb_fingerprint.fingerprint(b["service"], b["alert_type"])
    assert fp_a["fingerprint"] == fp_b["fingerprint"]


@pytest.mark.parametrize(
    "pair", CORPUS["distinct_pairs"], ids=["-vs-".join(p) for p in CORPUS["distinct_pairs"]]
)
def test_distinct_combinations_stay_distinct(pair):
    a, b = (BY_NAME[name] for name in pair)
    fp_a = bb_fingerprint.fingerprint(a["service"], a["alert_type"])
    fp_b = bb_fingerprint.fingerprint(b["service"], b["alert_type"])
    assert fp_a["fingerprint"] != fp_b["fingerprint"]


def test_service_rule_never_substitutes_placeholders():
    # Rule 3: service is canonical; digits/UUID-looking content stays literal.
    result = bb_fingerprint.fingerprint(
        "svc-3f9d2c1e-8a4b-4c6d-9e0f-112233445566", "x"
    )
    assert "<id>" not in result["service_normalized"]


def test_seeded_rule_change_without_version_bump_fails_the_corpus(monkeypatch):
    # SC-003: alter one normalization rule (int threshold 3 -> 2 digits) and
    # the corpus must catch it — this is the loud-drift tripwire.
    altered = tuple(
        (name, re.compile(r"\b\d{2,}\b") if name == "integer" else pattern, repl)
        for name, pattern, repl in bb_fingerprint.VOLATILE_RULES
    )
    monkeypatch.setattr(bb_fingerprint, "VOLATILE_RULES", altered)
    mismatches = [
        case["name"]
        for case in CASES
        if bb_fingerprint.fingerprint(case["service"], case["alert_type"])[
            "fingerprint"
        ]
        != case["fingerprint"]
    ]
    assert mismatches  # at least one golden case must trip


def test_never_raises_on_degenerate_inputs():
    for service, alert_type in [("", ""), ("   ", "\t"), ("x", "999")]:
        result = bb_fingerprint.fingerprint(service, alert_type)
        assert re.fullmatch(r"[0-9a-f]{16}", result["fingerprint"])


@pytest.mark.parametrize(
    "service, alert_type",
    [(None, "x"), ("x", None), (42, "x"), ("x", {"k": "v"}), (["x"], "y")],
    ids=["none-svc", "none-alert", "int-svc", "dict-alert", "list-svc"],
)
def test_non_str_inputs_raise_never_coerce(service, alert_type):
    # SF3: str()-coercion would turn None into a stable "none" fingerprint with
    # no flag, silently colliding every missing-service alert. Fail loud.
    with pytest.raises(TypeError):
        bb_fingerprint.fingerprint(service, alert_type)


def test_two_label_domain_stays_literal_boundary():
    # TA6: the hostname rule is ">=3 dotted labels"; a 2-label domain must NOT
    # collapse to <host>. Quantifier drift ({2,}->{1,}) would silently break
    # recall — pin the boundary.
    result = bb_fingerprint.fingerprint("svc-a", "example.com is down")
    assert "<host>" not in result["alert_type_normalized"]
    assert "example.com" in result["alert_type_normalized"]


def test_volatile_rule_precedence_is_pinned():
    # TA6: timestamp must win over integer (a date is not three <n>s), and UUID
    # must win over hex_id. Order changes fingerprints, so pin it.
    ts = bb_fingerprint.fingerprint("svc-a", "at 2026-07-20")["alert_type_normalized"]
    assert ts == "at <ts>"
    uuid = bb_fingerprint.fingerprint(
        "svc-a", "3f9d2c1e-8a4b-4c6d-9e0f-112233445566"
    )["alert_type_normalized"]
    assert uuid == "<id>"


# --- CLI shim (R7) ----------------------------------------------------------


def run_cli(args):
    return subprocess.run(
        [sys.executable, str(BIN_DIR / "bb-fingerprint")] + list(args),
        capture_output=True, text=True, timeout=30,
    )


def test_cli_matches_library():
    case = BY_NAME["mixed-volatile-tokens"]
    result = run_cli([case["service"], case["alert_type"]])
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload == bb_fingerprint.fingerprint(
        case["service"], case["alert_type"]
    )
    assert payload["version"] == "bb.fp.v1"  # version rides in output metadata


def test_cli_wrong_argc_is_usage_error():
    assert run_cli([]).returncode == 2
    assert run_cli(["a"]).returncode == 2
    assert run_cli(["a", "b", "c"]).returncode == 2
