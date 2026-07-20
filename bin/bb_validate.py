#!/usr/bin/env python3
"""bb-validate — checkpoint validator (design §5.4, D-14; Constitution VI).

Validates verdict/ledger documents against their embedded version tag:
schema shape *plus* the semantic invariants the product's headline behaviors
depend on — hand-rolled checks, no jsonschema dependency (D-1's no-install
rule). ``validate(doc)`` is the pure library entry (one violation record per
finding, all in one pass, input never modified); the CLI wraps it with
R7's exit codes: 0 pass / 1 violation(s) / 2 usage-or-parse error, violations
as JSON lines on stdout.

Semantic invariants enforced (Constitution VI — "enforced by bb-validate,
not by convention"):
- every non-`fresh` hypothesis/candidate carries VALIDATED/INVALIDATED;
- ≥3 live hypotheses and ≥1 live `fresh` whenever the ledger's phase is in
  the active deep-dive window (R9: evidence-gathering, deep-dive);
- every evidence entry is a `{url, excerpt}` pair — prose alone is invalid
  by schema (Constitution IV).

Scope of v1 (recorded so the subset is a decision, not an accident): v1
enforces the fields the headline invariants ride on. It intentionally does
NOT yet check `known_issue` sub-fields (`matched_session_id`,
`prior_resolution`) beyond their `validation` tag, and it accepts any string
for a hypothesis `status` (only `"live"` is counted toward the anchoring
invariant — an unknown status shrinks the live set and so fails *loud* via
`ledger.min_live_hypotheses`, never silently passes). Design §5.4 defers the
full field schemas to `skills/investigation/references/schemas.md` (slice 6);
this validator tightens as that lands.

Python 3.9-compatible, stdlib only.
"""

import json
import sys

VERDICT_SCHEMA = "bb.verdict.v1"
LEDGER_SCHEMA = "bb.ledger.v1"
KNOWN_SCHEMAS = (VERDICT_SCHEMA, LEDGER_SCHEMA)

# R9: closed phase enumeration; unknown values are a schema violation.
PHASES = (
    "triage-seeded",
    "hypothesis-generation",
    "evidence-gathering",
    "deep-dive",
    "resolution",
)
# The ≥3-live/≥1-fresh anchoring invariant applies in these phases (FR-006).
INVARIANT_PHASES = ("evidence-gathering", "deep-dive")

PROVENANCE_VALUES = ("triage", "recall", "fresh")
VALIDATION_VALUES = ("VALIDATED", "INVALIDATED")

MIN_LIVE_HYPOTHESES = 3


def _violation(violations, rule, path, message):
    violations.append({"rule": rule, "path": path, "message": message})


def _type_name(value):
    return type(value).__name__


def _check_field(doc, field, expected_types, path, violations, required=True):
    """Presence + type check; returns the value when usable, else None."""
    if field not in doc:
        if required:
            _violation(
                violations, "schema.missing_field", "%s.%s" % (path, field),
                "required field '%s' is missing" % field,
            )
        return None
    value = doc[field]
    if isinstance(value, bool) and bool not in expected_types:
        # bool is an int subclass; never accept it where int/number is meant.
        _violation(
            violations, "schema.wrong_type", "%s.%s" % (path, field),
            "'%s' must be %s, got bool" % (field, expected_types),
        )
        return None
    if not isinstance(value, tuple(expected_types)):
        _violation(
            violations, "schema.wrong_type", "%s.%s" % (path, field),
            "'%s' must be %s, got %s"
            % (field, "/".join(t.__name__ for t in expected_types), _type_name(value)),
        )
        return None
    return value


def _check_evidence_list(entries, path, violations):
    if not isinstance(entries, list):
        _violation(
            violations, "schema.wrong_type", path,
            "evidence must be a list, got %s" % _type_name(entries),
        )
        return
    for i, entry in enumerate(entries):
        entry_path = "%s[%d]" % (path, i)
        if not isinstance(entry, dict):
            _violation(
                violations, "evidence.not_url_excerpt_pair", entry_path,
                "evidence entries are {url, excerpt} pairs, never prose alone",
            )
            continue
        for key in ("url", "excerpt"):
            value = entry.get(key)
            if not isinstance(value, str) or not value.strip():
                _violation(
                    violations, "evidence.not_url_excerpt_pair",
                    "%s.%s" % (entry_path, key),
                    "evidence entry needs a non-empty '%s'" % key,
                )


def _check_provenance_and_validation(item, path, violations):
    """The Constitution VI pair: provenance tag + validation on non-fresh."""
    provenance = item.get("provenance")
    if provenance not in PROVENANCE_VALUES:
        _violation(
            violations, "provenance.unknown", "%s.provenance" % path,
            "provenance must be one of %s, got %r"
            % ("/".join(PROVENANCE_VALUES), provenance),
        )
        return
    if provenance == "fresh":
        return
    validation = item.get("validation")
    if validation is None:
        _violation(
            violations, "memory.unvalidated_non_fresh", "%s.validation" % path,
            "non-fresh (provenance %r) items must be marked VALIDATED or "
            "INVALIDATED against fresh evidence before being acted on"
            % provenance,
        )
    elif validation not in VALIDATION_VALUES:
        _violation(
            violations, "validation.unknown_value", "%s.validation" % path,
            "validation must be VALIDATED or INVALIDATED, got %r" % validation,
        )


def _check_confidence(item, path, violations):
    if "confidence" not in item:
        return
    confidence = item["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        _violation(
            violations, "schema.wrong_type", "%s.confidence" % path,
            "confidence must be a number, got %s" % _type_name(confidence),
        )
    elif not 0 <= confidence <= 1:
        _violation(
            violations, "confidence.out_of_range", "%s.confidence" % path,
            "confidence must be within [0, 1], got %r" % confidence,
        )


def _validate_verdict(doc, violations):
    _check_field(doc, "session_id", (str,), "$", violations)
    _check_field(doc, "severity", (str,), "$", violations)
    _check_field(doc, "no_strong_signal", (bool,), "$", violations)
    _check_field(doc, "budget_spent", (dict,), "$", violations)
    _check_field(doc, "flap_assessment", (str,), "$", violations, required=False)
    _check_field(doc, "next_step", (str,), "$", violations, required=False)
    _check_field(doc, "deploy_window", (list,), "$", violations, required=False)

    known_issue = _check_field(
        doc, "known_issue", (dict,), "$", violations, required=False
    )
    if known_issue is not None:
        validation = known_issue.get("validation")
        if validation not in VALIDATION_VALUES:
            _violation(
                violations, "memory.unvalidated_non_fresh", "$.known_issue.validation",
                "a known-issue match is recalled memory; it must be marked "
                "VALIDATED or INVALIDATED, got %r" % validation,
            )

    candidates = _check_field(doc, "candidates", (list,), "$", violations)
    if candidates is None:
        return
    for i, candidate in enumerate(candidates):
        path = "$.candidates[%d]" % i
        if not isinstance(candidate, dict):
            _violation(
                violations, "schema.wrong_type", path,
                "candidate must be an object, got %s" % _type_name(candidate),
            )
            continue
        _check_field(candidate, "statement", (str,), path, violations)
        _check_provenance_and_validation(candidate, path, violations)
        _check_confidence(candidate, path, violations)
        if "evidence" in candidate:
            _check_evidence_list(
                candidate["evidence"], "%s.evidence" % path, violations
            )


def _validate_ledger(doc, violations):
    _check_field(doc, "seq", (int,), "$", violations)
    _check_field(doc, "at", (str,), "$", violations)
    _check_field(doc, "services_touched", (list,), "$", violations, required=False)
    _check_field(doc, "tool_call_count", (int,), "$", violations, required=False)

    phase = _check_field(doc, "phase", (str,), "$", violations)
    if phase is not None and phase not in PHASES:
        _violation(
            violations, "ledger.unknown_phase", "$.phase",
            "phase must be one of %s, got %r (unknown => error, never guess)"
            % ("/".join(PHASES), phase),
        )
        phase = None

    hypotheses = _check_field(doc, "hypotheses", (list,), "$", violations)
    if hypotheses is None:
        return

    live = []
    for i, hypothesis in enumerate(hypotheses):
        path = "$.hypotheses[%d]" % i
        if not isinstance(hypothesis, dict):
            _violation(
                violations, "schema.wrong_type", path,
                "hypothesis must be an object, got %s" % _type_name(hypothesis),
            )
            continue
        _check_field(hypothesis, "id", (str,), path, violations)
        _check_field(hypothesis, "statement", (str,), path, violations)
        status = _check_field(hypothesis, "status", (str,), path, violations)
        _check_provenance_and_validation(hypothesis, path, violations)
        _check_confidence(hypothesis, path, violations)
        for key in ("evidence_for", "evidence_against"):
            if key in hypothesis:
                _check_evidence_list(
                    hypothesis[key], "%s.%s" % (path, key), violations
                )
        if status == "live":
            live.append(hypothesis)

    if phase in INVARIANT_PHASES:
        if len(live) < MIN_LIVE_HYPOTHESES:
            _violation(
                violations, "ledger.min_live_hypotheses", "$.hypotheses",
                "phase %r requires >=%d live hypotheses (anchoring guard, "
                "FR-5e), found %d" % (phase, MIN_LIVE_HYPOTHESES, len(live)),
            )
        if not any(h.get("provenance") == "fresh" for h in live):
            _violation(
                violations, "ledger.fresh_required", "$.hypotheses",
                "phase %r requires >=1 live fresh hypothesis "
                "(tunnel-vision guard, FR-5e)" % phase,
            )


def validate(doc):
    """All violations of a parsed document, in one pass. Never mutates input."""
    violations = []
    if not isinstance(doc, dict):
        _violation(
            violations, "schema.not_object", "$",
            "document must be a JSON object, got %s" % _type_name(doc),
        )
        return violations
    schema = doc.get("schema")
    if schema not in KNOWN_SCHEMAS:
        _violation(
            violations, "schema.unknown_version", "$.schema",
            "unknown or missing version tag %r (known: %s)"
            % (schema, ", ".join(KNOWN_SCHEMAS)),
        )
        return violations
    if schema == VERDICT_SCHEMA:
        _validate_verdict(doc, violations)
    else:
        _validate_ledger(doc, violations)
    return violations


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) > 1:
        sys.stderr.write("usage: bb-validate [FILE]  (or document on stdin)\n")
        return 2
    try:
        # ValueError catches UnicodeDecodeError (a non-UTF-8 file) alongside
        # OSError — both are read failures, exit 2, never the exit-1 that means
        # "violations found" to a scripted caller branching on the code.
        if argv:
            with open(argv[0], encoding="utf-8") as f:
                raw = f.read()
        else:
            raw = sys.stdin.read()
    except (OSError, ValueError) as exc:
        sys.stderr.write("bb-validate: cannot read input (%s)\n" % exc)
        return 2
    try:
        doc = json.loads(raw)
    except ValueError as exc:
        sys.stderr.write("bb-validate: input is not JSON (%s)\n" % exc)
        return 2
    try:
        violations = validate(doc)
    except Exception as exc:
        # An internal validator bug must never masquerade as exit 1 (violations)
        # or exit 0 (valid). Correctness helper: fail loud, fail as usage-error.
        sys.stderr.write("bb-validate: internal error (%s)\n" % exc)
        return 2
    for violation in violations:
        sys.stdout.write(json.dumps(violation, sort_keys=True) + "\n")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
