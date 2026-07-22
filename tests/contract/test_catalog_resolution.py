"""T011 / US1 / SC-003: alert-to-service resolution classifies every matrix
case exactly as documented, with zero silent picks.

Ties ``tests/helpers/catalog_reference.py``'s ``resolve``/``fixup_offer``
(T010) to ``tests/fixtures/catalog/resolution-matrix.json`` (T010) and to
``skills/catalog/references/resolution.md``'s "The match order" / "The
fix-up offer":

- **SC-003** ("The resolution matrix classifies 100% correctly: exact beats
  substring, multi-match surfaces choices, misses reach the ask-once path —
  zero silent picks across all fixture cases"): the full expectation —
  outcome, service/candidates, stage-or-absence — for every case.
- The matrix's headline claim, "never a silent pick": counted across the
  whole matrix, no ``ambiguous`` resolution ever carries a ``service`` key.
- Sparse/degenerate alerts never raise — only ever resolve to ``miss``.
- US3 AS-2's resolution half: a matcher-less service (``notifier``) still
  routes to the miss path when the alert doesn't spell its name.
- The fix-up offer's four fields, its pinned annotation value order, and its
  two ``source_path`` conventions (existing service vs. brand-new entity).

Everything here asserts on ``resolve``/``fixup_offer``'s real return values,
never on prose — the matrix fixture's own description states it was derived
by hand against the documented rules, not by running the implementation
under test.
"""

import pytest

from conftest import fixture_path, load_fixture
from helpers.catalog_reference import fixup_offer, load_catalog, resolve

CATALOG = load_catalog(fixture_path("catalog", "repo"))
MATRIX = load_fixture("catalog", "resolution-matrix.json")
CASES = MATRIX["cases"]

EXPECTED_CASE_IDS = frozenset(
    {
        "exact-tag-hit",
        "exact-name-hit",
        "substring-hit",
        "exact-beats-substring",
        "multi-exact",
        "multi-substring",
        "miss",
        "sparse-alert",
        "reverse-direction-probe",
        "name-is-substring-stage-only",
    }
)


# ---------------------------------------------------------------------------
# Non-vanishing guard, first (TA5-style, per test_catalog_model.py's and
# test_fingerprint_reference.py's precedent) — a truncated or renamed matrix
# must fail here, not silently shrink the parametrize below to a smaller,
# still-green set.
# ---------------------------------------------------------------------------


def test_matrix_has_at_least_the_documented_ten_cases():
    assert len(CASES) >= 10, (
        "resolution-matrix.json must carry at least the 10 documented cases; "
        "got %d — a truncated matrix must fail here, not silently shrink "
        "every parametrize below" % len(CASES)
    )


def test_matrix_case_ids_are_exactly_the_documented_set():
    case_ids = set(case["id"] for case in CASES)
    assert case_ids == EXPECTED_CASE_IDS, (
        "resolution-matrix.json's case-id set must equal the documented ten "
        "exactly — a renamed or dropped id must fail here rather than "
        "silently disappearing from the parametrize below; "
        "missing=%r extra=%r"
        % (
            sorted(EXPECTED_CASE_IDS - case_ids),
            sorted(case_ids - EXPECTED_CASE_IDS),
        )
    )


CASE_IDS = [case["id"] for case in CASES]


# ---------------------------------------------------------------------------
# SC-003 — the matrix, parametrized over every case.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS or None)
def test_matrix_case_resolves_exactly_as_expected(case):
    why = case["why"]
    expected = case["expected"]
    resolution = resolve(case["alert"], CATALOG)

    assert resolution["outcome"] == expected["outcome"], (
        "%s: outcome must be %r — %s; got %r"
        % (case["id"], expected["outcome"], why, resolution["outcome"])
    )

    if "service" in expected:
        assert resolution.get("service") == expected["service"], (
            "%s: resolution['service'] must be %r — %s; got %r"
            % (case["id"], expected["service"], why, resolution.get("service"))
        )
        assert resolution["candidates"] == [], (
            "%s: a resolved single-hit case must carry an empty candidates "
            "list — %s; got %r" % (case["id"], why, resolution["candidates"])
        )

    # Unconditional, not `if expected.get("candidates")`: a falsy [] would
    # skip the assertion entirely on every miss case, leaving data-model.md
    # §5's `miss -> candidates == []` row asserted by nothing. Every case in
    # the matrix carries a candidates key, so there is nothing to guard.
    assert resolution["candidates"] == expected["candidates"], (
        "%s: candidates must equal %r IN ORDER (source-path order, never "
        "a set) — %s; got %r"
        % (case["id"], expected["candidates"], why, resolution["candidates"])
    )

    if "stage" in expected:
        assert resolution.get("stage") == expected["stage"], (
            "%s: resolution['stage'] must be %r — %s; got %r"
            % (case["id"], expected["stage"], why, resolution.get("stage"))
        )
    else:
        assert "stage" not in resolution, (
            "%s: a miss must carry no 'stage' key at all (not None — "
            "genuinely absent) — %s; got resolution=%r" % (case["id"], why, resolution)
        )

    if expected["outcome"] in ("miss", "ambiguous"):
        assert "service" not in resolution, (
            "%s: outcome %r must never carry a 'service' key — never a "
            "silent pick — %s; got resolution=%r"
            % (case["id"], expected["outcome"], why, resolution)
        )


# ---------------------------------------------------------------------------
# Zero silent picks, counted across the whole matrix (SC-003's headline).
# ---------------------------------------------------------------------------


def test_no_ambiguous_resolution_ever_carries_a_service_across_the_matrix():
    ambiguous_count = 0
    for case in CASES:
        resolution = resolve(case["alert"], CATALOG)
        if resolution["outcome"] == "ambiguous":
            ambiguous_count += 1
            assert "service" not in resolution, (
                "%s: an ambiguous resolution must never carry a 'service' "
                "key — resolution.md's 'never a silent pick'; got %r"
                % (case["id"], resolution)
            )
    assert ambiguous_count > 0, (
        "the matrix must contain at least one case that actually resolves "
        "to 'ambiguous' — otherwise the zero-silent-picks check above is "
        "vacuous"
    )


# ---------------------------------------------------------------------------
# Sparse alerts do not raise.
# ---------------------------------------------------------------------------


DEGENERATE_ALERTS = [
    {},
    {"alert_id": "x"},
    {"alert_id": "x", "tags": None, "fields": None},
    {"alert_id": "x", "tags": ["", None], "fields": {"name": None, "other": 5}},
]
DEGENERATE_IDS = [
    "empty-alert",
    "alert-id-only",
    "none-tags-none-fields",
    "junk-tags-and-fields",
]


def test_sparse_alert_case_misses_without_raising():
    sparse_case = next(case for case in CASES if case["id"] == "sparse-alert")
    resolution = resolve(sparse_case["alert"], CATALOG)
    assert resolution["outcome"] == "miss", (
        "sparse-alert: %s; got %r" % (sparse_case["why"], resolution["outcome"])
    )


@pytest.mark.parametrize("alert", DEGENERATE_ALERTS, ids=DEGENERATE_IDS)
def test_hand_built_degenerate_alerts_miss_without_raising(alert):
    resolution = resolve(alert, CATALOG)
    assert resolution["outcome"] == "miss", (
        "a degenerate/malformed alert (%r) must resolve to 'miss', never "
        "raise — got %r" % (alert, resolution["outcome"])
    )


# ---------------------------------------------------------------------------
# US3 AS-2's resolution half — a matcher-less service routes to the miss
# path.
# ---------------------------------------------------------------------------


def test_matcherless_service_misses_when_alert_does_not_spell_its_name():
    # notifier carries no oncall-harness/alert-match annotation, so it has no
    # alert_matchers and cannot hit the exact stage at all. This alert
    # deliberately does NOT contain the string "notifier": "notifier" has no
    # alert_matchers so it cannot match at the exact stage, but the
    # substring stage would legitimately resolve it if the alert spelled its
    # name — an alert that did would assert the opposite of what this test
    # reads.
    alert = {
        "alert_id": "n1",
        "tags": ["email-queue-backlog"],
        "fields": {"name": "outbound email backlog"},
    }
    resolution = resolve(alert, CATALOG)
    assert resolution["outcome"] == "miss", (
        "a matcher-less service (notifier) must miss when nothing in the "
        "alert spells its name — got %r" % resolution
    )


# ---------------------------------------------------------------------------
# The fix-up offer on the miss path.
# ---------------------------------------------------------------------------


MISS_CASE = next(case for case in CASES if case["id"] == "miss")
MISS_ALERT = MISS_CASE["alert"]


def test_fixup_offer_for_a_service_already_in_the_catalog():
    offer = fixup_offer(MISS_ALERT, "checkout", CATALOG)
    assert set(offer) == {
        "source_path",
        "annotation_key",
        "annotation_value",
        "commit_ready",
        "snippet",
    }, "fixup_offer must return exactly the five documented keys; got %r" % sorted(offer)
    assert offer["commit_ready"] is True, (
        "an offer with a real discriminating value is commit-ready"
    )
    assert offer["annotation_key"] == "oncall-harness/alert-match", (
        "annotation_key is always the literal oncall-harness/alert-match"
    )
    assert offer["source_path"] == "services/checkout/catalog-info.yaml", (
        "checkout is already in the catalog — source_path must be its "
        "existing source, not the brand-new-entity convention"
    )
    assert offer["annotation_value"] == "node-9 disk pressure", (
        "the pinned order takes fields['name'] first — got %r"
        % offer["annotation_value"]
    )
    assert offer["annotation_key"] in offer["snippet"], (
        "the snippet must contain the annotation_key so a responder can "
        "paste it as-is"
    )
    assert offer["annotation_value"] in offer["snippet"], (
        "the snippet must contain the annotation_value so a responder can "
        "paste it as-is"
    )


def test_fixup_offer_for_a_service_absent_from_the_catalog():
    offer = fixup_offer(MISS_ALERT, "brand-new-svc", CATALOG)
    assert offer["source_path"] == "services/brand-new-svc/catalog-info.yaml", (
        "a service absent from the catalog entirely gets the pinned "
        "conventional path services/<name>/catalog-info.yaml — got %r"
        % offer["source_path"]
    )


def test_fixup_offer_annotation_value_falls_back_to_service_hint():
    alert = {"alert_id": "x", "tags": [], "fields": {"service_hint": "some-hint"}}
    offer = fixup_offer(alert, "checkout", CATALOG)
    assert offer["annotation_value"] == "some-hint", (
        "no fields.name present — the pinned order falls back to "
        "fields.service_hint; got %r" % offer["annotation_value"]
    )


def test_fixup_offer_annotation_value_falls_back_to_first_tag():
    alert = {"alert_id": "x", "tags": ["first-tag", "second-tag"], "fields": {}}
    offer = fixup_offer(alert, "checkout", CATALOG)
    assert offer["annotation_value"] == "first-tag", (
        "no fields.name or fields.service_hint present — the pinned order "
        "falls back to the first tag; got %r" % offer["annotation_value"]
    )


def test_fixup_offer_annotation_value_defaults_to_empty_string():
    alert = {"alert_id": "x", "tags": [], "fields": {}}
    offer = fixup_offer(alert, "checkout", CATALOG)
    assert offer["annotation_value"] == "", (
        "none of fields.name, fields.service_hint, or a tag is present — "
        "the pinned order's final fallback is the empty string; got %r"
        % offer["annotation_value"]
    )


# ---------------------------------------------------------------------------
# Properties the matrix payloads cannot reach — asserted directly.
#
# A mutation review found seven surviving mutants here: every fixture matcher
# and every matrix alert value is already lowercase, already trimmed, and no
# alert field *key* collides with a matcher, so normalization and the
# value-not-key rule were free. These close that gap at the function boundary
# rather than by bending the roster, which data-model.md §10 pins for other
# reasons.
# ---------------------------------------------------------------------------


def _alert(tags=None, fields=None):
    return {
        "alert_id": "probe",
        "tags": [] if tags is None else tags,
        "fields": {} if fields is None else fields,
    }


def test_exact_stage_is_case_insensitive():
    resolution = resolve(_alert(tags=["CHECKOUT-5XX"]), CATALOG)
    assert (resolution["outcome"], resolution.get("service")) == ("exact", "checkout"), (
        "the exact stage compares case-insensitively (data-model.md §5.1) — an "
        "alert shouting its tag must still resolve; got %r" % resolution
    )


def test_exact_stage_trims_surrounding_whitespace():
    resolution = resolve(_alert(tags=["  checkout-5xx  "]), CATALOG)
    assert (resolution["outcome"], resolution.get("service")) == ("exact", "checkout"), (
        "the exact stage compares whitespace-trimmed (data-model.md §5.1); got %r"
        % resolution
    )


def test_substring_stage_is_case_insensitive():
    resolution = resolve(_alert(fields={"name": "latency on SEARCH-API"}), CATALOG)
    assert (resolution["outcome"], resolution.get("service")) == (
        "substring",
        "search-api",
    ), "the substring stage matches case-insensitively; got %r" % resolution


def test_alert_field_keys_are_not_match_strings():
    # data-model.md §5.1 pins the exact stage against alert tags and field
    # VALUES. A field whose *key* happens to equal a matcher must not match.
    resolution = resolve(_alert(fields={"checkout-5xx": "nothing here"}), CATALOG)
    assert resolution["outcome"] == "miss", (
        "alert field names are not match strings — only tags and field values "
        "are; got %r" % resolution
    )


def test_an_empty_matcher_never_matches_a_sparse_alert():
    # fixup_offer's pinned final fallback emits annotation_value == "" when a
    # sparse alert offers nothing discriminating. A responder who commits that
    # snippet verbatim gives their service alert_matchers: [""] — which, without
    # an emptiness guard on the exact stage, would then match every sparse alert
    # exactly. The tool must not talk a team into a catalog entry that swallows
    # unrelated incidents.
    poisoned = {
        "services": {"swallower": {"name": "swallower", "owner": "t", "runbooks": [],
                                   "dashboards": [], "alert_matchers": [""],
                                   "depends_on": []}},
        "linkage": {}, "sources": {"swallower": "services/swallower/catalog-info.yaml"},
        "warnings": [], "failures": [],
    }
    resolution = resolve(_alert(fields={"name": ""}), poisoned)
    assert resolution["outcome"] == "miss", (
        "an empty alert_matchers entry must never hit — got %r" % resolution
    )


def test_fixup_offer_uses_the_existing_source_path_not_the_convention():
    # billing is the only roster service whose directory name (zz-billing)
    # differs from its metadata.name, so it is the only subject that can tell
    # catalog["sources"] apart from the services/<name>/ convention. Asserting
    # this on checkout would be vacuous — the two strings coincide there.
    offer = fixup_offer(MISS_CASE["alert"], "billing", CATALOG)
    assert offer["source_path"] == "services/zz-billing/catalog-info.yaml", (
        "a service already in the catalog gets its EXISTING source path, not "
        "the brand-new-entity convention; got %r" % offer["source_path"]
    )


def test_fixup_offer_annotation_value_prefers_name_over_service_hint_and_tags():
    # The individual fallback rungs are asserted elsewhere with disjoint
    # alerts, which never observes the ORDER. This alert carries all three
    # candidates at once, so only the pinned precedence passes.
    offer = fixup_offer(
        _alert(tags=["a-tag"], fields={"name": "the-name", "service_hint": "the-hint"}),
        "checkout",
        CATALOG,
    )
    assert offer["annotation_value"] == "the-name", (
        "the discriminating field is pinned name -> service_hint -> first tag "
        "-> '' (data-model.md §7); got %r" % offer["annotation_value"]
    )


def test_fixup_offer_annotation_value_prefers_service_hint_over_tags():
    offer = fixup_offer(
        _alert(tags=["a-tag"], fields={"service_hint": "the-hint"}), "checkout", CATALOG
    )
    assert offer["annotation_value"] == "the-hint", (
        "service_hint outranks the first tag in the pinned order; got %r"
        % offer["annotation_value"]
    )


def test_empty_offer_is_not_commit_ready_and_carries_no_snippet():
    # The harness must never *produce* the thing _exact_stage_hits defends
    # against on the read side: a service whose alert_matchers contains the
    # empty string swallows every sparse alert. Both sides are guarded on
    # purpose — an empty matcher can still arrive by hand-editing, so neither
    # side is trusted to be the only one. When the alert
    # offers nothing discriminating, the offer is marked not-commit-ready and
    # carries no paste-ready snippet at all — there is nothing to paste.
    offer = fixup_offer({"alert_id": "sparse", "tags": [], "fields": {}}, "x", CATALOG)
    assert offer["annotation_value"] == "", "the pinned final fallback is the empty string"
    assert offer["commit_ready"] is False, (
        "an offer with an empty discriminating value is not commit-ready — a "
        "responder committing it would give the service a matcher that "
        "matches every sparse alert"
    )
    assert offer["snippet"] == "", (
        "a non-commit-ready offer carries no snippet: handing over a "
        "paste-ready block the module elsewhere calls harmful is the failure "
        "this pins against"
    )
