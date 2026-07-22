"""T007 / US2 / SC-002: the parsed catalog model matches its goldens field-for-field.

Ties ``tests/helpers/catalog_reference.py``'s ``load_catalog`` (T004) to
``tests/fixtures/catalog/golden-models.json`` (T006) and to spec.md's "User Story 2 -
One service shape for the whole system":

- **SC-002** ("100% of fixture services parse to their golden models field-for-field,
  including empty-list defaults"): every golden's ``model``, ``source_path``, and
  ``linkage`` sub-objects must agree exactly with what ``load_catalog`` parsed.
- **AS-2** (minimal annotated subset is sufficient): ``kind`` + ``metadata.name`` +
  ``spec.owner`` alone still parses to a valid model with four empty lists.
- **AS-3** (no raw catalog structure escapes): a parsed ``Service``'s key set is
  exactly the six ``MODEL_FIELDS``, and linkage (``paging_id``, ``repo_slug``) lives
  beside the model in ``catalog["linkage"]``, never inside it.

Also exercises the catalog-quality warning vocabulary the fixture roster is built to
cover (``ignored_entity``, ``duplicate_name``, ``dangling_dependency``,
``missing_owner``) and the model-side half of file-scoped failure isolation — US3
(``specs/007-catalog-adapter/spec.md``) owns the full failure-isolation assertion;
this file only pins that the other 8 services still parse when one file is broken.

Everything here asserts on ``load_catalog``'s real return value, never on prose —
``tests/helpers/catalog_reference.py``'s own docstring states it is a CI instrument
for the documented rules, not proof a live agent follows them.
"""

import pytest

from conftest import fixture_path, load_fixture
from helpers.catalog_reference import MODEL_FIELDS, load_catalog, parse_entity

CATALOG = load_catalog(fixture_path("catalog", "repo"))
GOLDEN = load_fixture("catalog", "golden-models.json")

EXPECTED_SERVICE_NAMES = frozenset(
    {
        "billing",
        "checkout",
        "inventory",
        "ledger-svc",
        "notifier",
        "orders",
        "payments-api",
        "search-api",
    }
)

# Keys that must never appear on a parsed Service — raw catalog/linkage structure
# that AS-3 says stops at the adapter boundary.
_LEAKED_KEYS = frozenset(
    {"linkage", "paging_id", "repo_slug", "annotations", "metadata", "spec", "kind"}
)


# ---------------------------------------------------------------------------
# Non-vanishing guards (TA5-style, per test_fingerprint_reference.py's
# precedent) — written first, everything else is parametrized off these sets.
# A broken fixture glob or a dropped golden must fail loudly here, not
# silently shrink a later parametrize to an empty, still-green no-op.
# ---------------------------------------------------------------------------


def test_golden_set_is_non_empty():
    assert GOLDEN, (
        "golden-models.json loaded to an empty object — every field-for-field "
        "comparison below would vacuously pass over zero services"
    )


def test_golden_keys_equal_parsed_service_keys():
    golden_names = set(GOLDEN)
    parsed_names = set(CATALOG["services"])
    assert golden_names == parsed_names, (
        "golden-models.json's key set must equal load_catalog's parsed "
        "catalog[\"services\"] key set exactly — a broken fixture glob or a "
        "dropped golden must fail here, not silently shrink every parametrize "
        "below; golden-only=%r parsed-only=%r"
        % (sorted(golden_names - parsed_names), sorted(parsed_names - golden_names))
    )


def test_roster_is_the_documented_eight_services():
    golden_names = set(GOLDEN)
    parsed_names = set(CATALOG["services"])
    assert golden_names == EXPECTED_SERVICE_NAMES, (
        "the fixture roster (README.md's 'Fixture service roster') documents "
        "exactly these 8 parsed services; golden-models.json disagrees: "
        "missing=%r extra=%r"
        % (
            sorted(EXPECTED_SERVICE_NAMES - golden_names),
            sorted(golden_names - EXPECTED_SERVICE_NAMES),
        )
    )
    assert parsed_names == EXPECTED_SERVICE_NAMES, (
        "load_catalog must resolve the fixture repo to exactly these 8 services "
        "(11 entities minus docs-site/ignored, broken/failed, orders-us/duplicate "
        "loser); missing=%r extra=%r"
        % (
            sorted(EXPECTED_SERVICE_NAMES - parsed_names),
            sorted(parsed_names - EXPECTED_SERVICE_NAMES),
        )
    )


SERVICE_NAMES = sorted(GOLDEN)


# ---------------------------------------------------------------------------
# SC-002 — golden model agreement, parametrized over every golden service.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", SERVICE_NAMES, ids=SERVICE_NAMES or None)
def test_golden_model_agrees_with_parsed_catalog(name):
    golden = GOLDEN[name]
    parsed_model = CATALOG["services"][name]
    assert parsed_model == golden["model"], (
        "%r: parsed Service must equal the golden's `model` sub-object "
        "field-for-field, including empty-list defaults for absent annotations "
        "(SC-002) — parsed=%r golden=%r" % (name, parsed_model, golden["model"])
    )
    assert CATALOG["sources"][name] == golden["source_path"], (
        "%r: catalog[\"sources\"] must name the same winning file the golden "
        "was authored against — got %r, golden expects %r"
        % (name, CATALOG["sources"][name], golden["source_path"])
    )
    # Indexed, not .get(name, {}): seven of the eight goldens carry an empty
    # linkage, so a defaulting lookup would compare {} == {} and pass even if
    # load_catalog never populated an entry at all. Indexing additionally pins
    # data-model.md §3's `linkage: {name -> {...}}` — an entry per service.
    assert CATALOG["linkage"][name] == golden["linkage"], (
        "%r: catalog[\"linkage\"] must carry exactly the golden's `linkage` "
        "sub-object — linkage rides beside the model, not inside it, and must "
        "still be preserved intact" % name
    )
    # Structural guard on the golden itself: T014 (US3) owns the
    # disabled_features *assertion*, but without this a golden missing the key
    # — or carrying a wrong type — stays green through all of Phase 2 and only
    # surfaces as a KeyError two phases later.
    assert set(golden) == {"model", "linkage", "disabled_features", "source_path"}, (
        "%r: every golden carries exactly data-model.md §10's four sibling "
        "keys — got %r" % (name, sorted(golden))
    )
    assert isinstance(golden["disabled_features"], list), (
        "%r: disabled_features is a JSON list (JSON has no set type); "
        "assertions coerce it with set()" % name
    )


# ---------------------------------------------------------------------------
# US2 AS-2 — the minimal annotated subset is sufficient, asserted directly
# against the parse (not only transitively via the golden).
# ---------------------------------------------------------------------------


def test_payments_api_minimal_subset_parses_with_empty_lists():
    service = CATALOG["services"]["payments-api"]
    assert service["name"] == "payments-api"
    assert service["owner"] == "team-payments", (
        "payments-api's fixture carries only kind + metadata.name + spec.owner "
        "(PRD FR-13's minimal viable subset) — owner must still populate"
    )
    for field in ("runbooks", "dashboards", "alert_matchers", "depends_on"):
        assert service[field] == [], (
            "%r must be an empty list, never None or absent, when its source "
            "annotation is missing entirely — the minimal subset must still "
            "produce a valid model (AS-2); got %r" % (field, service[field])
        )


# ---------------------------------------------------------------------------
# US2 AS-3 — no raw catalog structure escapes the model, for every parsed
# service; linkage is carried beside the model, never inside it.
# ---------------------------------------------------------------------------


ALL_SERVICE_NAMES = sorted(CATALOG["services"])


@pytest.mark.parametrize("name", ALL_SERVICE_NAMES, ids=ALL_SERVICE_NAMES or None)
def test_parsed_service_exposes_exactly_the_six_model_fields(name):
    service = CATALOG["services"][name]
    assert set(service) == set(MODEL_FIELDS), (
        "%r: a parsed Service's key set must be exactly MODEL_FIELDS=%r — AS-3 "
        "forbids any raw catalog structure from escaping the model; got %r"
        % (name, sorted(MODEL_FIELDS), sorted(service))
    )
    leaked = _LEAKED_KEYS & set(service)
    assert not leaked, (
        "%r: a parsed Service must never carry raw catalog/linkage keys — "
        "found %r riding inside the model instead of beside it" % (name, sorted(leaked))
    )


def test_checkout_linkage_lives_beside_the_model_not_inside_it():
    """Proves linkage is carried, not silently dropped, while still absent from
    the six-field model (pinned per-service by the parametrized test above)."""
    linkage = CATALOG["linkage"]["checkout"]
    assert linkage.get("paging_id") == "PD-CHECKOUT", (
        "checkout's pagerduty.com/service-id annotation must resolve into "
        "catalog[\"linkage\"][\"checkout\"][\"paging_id\"]"
    )
    assert linkage.get("repo_slug") == "example-org/checkout", (
        "checkout's github.com/project-slug annotation must resolve into "
        "catalog[\"linkage\"][\"checkout\"][\"repo_slug\"]"
    )


# ---------------------------------------------------------------------------
# Non-service entities ignored.
# ---------------------------------------------------------------------------


def test_docs_site_is_ignored_not_parsed():
    assert "docs-site" not in CATALOG["services"], (
        "docs-site's kind is \"Documentation\", outside SERVICE_KINDS — it must "
        "never reach catalog[\"services\"]"
    )
    ignored = [w for w in CATALOG["warnings"] if w["kind"] == "ignored_entity"]
    assert len(ignored) == 1, (
        "docs-site is the fixture repo's only non-service-shaped entity, so "
        "exactly one ignored_entity warning is expected; got %d: %r"
        % (len(ignored), ignored)
    )
    assert ignored[0]["sources"] == ["services/docs-site/catalog-info.yaml"], (
        "the ignored_entity warning must name docs-site's own source file, not "
        "some other entity"
    )


# ---------------------------------------------------------------------------
# Duplicate metadata.name — orders-eu wins, orders-us loses, both are named.
# ---------------------------------------------------------------------------


def test_duplicate_orders_resolves_to_the_lexicographically_first_source():
    assert CATALOG["sources"]["orders"] == "services/orders-eu/catalog-info.yaml", (
        "orders-eu/catalog-info.yaml sorts before orders-us/catalog-info.yaml — "
        "the lexicographically-first source path must be canonical"
    )
    dup_warnings = [w for w in CATALOG["warnings"] if w["kind"] == "duplicate_name"]
    assert len(dup_warnings) == 1, (
        "exactly one duplicate_name warning is expected for the orders pair; "
        "got %d: %r" % (len(dup_warnings), dup_warnings)
    )
    assert set(dup_warnings[0]["sources"]) == {
        "services/orders-eu/catalog-info.yaml",
        "services/orders-us/catalog-info.yaml",
    }, (
        "the duplicate_name warning must name BOTH source paths of the "
        "colliding metadata.name group, winner and loser alike — got %r"
        % dup_warnings[0]["sources"]
    )
    assert CATALOG["services"]["orders"]["owner"] == "team-orders-eu", (
        "the canonical orders model must carry orders-eu's values (the "
        "lexicographic winner), not orders-us's"
    )


# ---------------------------------------------------------------------------
# Catalog-quality warnings: dangling dependency kept-not-filtered; the
# missing_owner vocabulary exercised without a false positive.
# ---------------------------------------------------------------------------


def test_billing_dangling_dependency_kept_and_warned():
    assert "nonexistent-svc" in CATALOG["services"]["billing"]["depends_on"], (
        "FR-006 requires a dangling dependsOn entry to be KEPT in the model, "
        "never filtered — billing's depends_on must still name nonexistent-svc"
    )
    dangling = [
        w
        for w in CATALOG["warnings"]
        if w["kind"] == "dangling_dependency" and w["service"] == "billing"
    ]
    assert len(dangling) == 1, (
        "exactly one dangling_dependency warning is expected for billing; "
        "got %d: %r" % (len(dangling), dangling)
    )
    assert "nonexistent-svc" in dangling[0]["detail"], (
        "the dangling_dependency warning must name the absent service "
        "(nonexistent-svc) it is about, not just billing itself"
    )


def test_missing_owner_vocabulary_has_no_false_positive_on_this_roster():
    # Positive case deliberately absent from the fixture roster: every fixture
    # service (README.md's roster table) carries a non-empty spec.owner, so
    # missing_owner has nothing to fire on here. This asserts the negative
    # half only — that the vocabulary is exercised without spuriously firing
    # on a fully-owned roster; a fixture exercising the positive case would
    # need its own dedicated entity, out of scope for T007.
    missing_owner = [w for w in CATALOG["warnings"] if w["kind"] == "missing_owner"]
    assert not missing_owner, (
        "every fixture service declares spec.owner — a missing_owner warning "
        "here would mean an owned service is being flagged as unowned: %r"
        % missing_owner
    )


# ---------------------------------------------------------------------------
# File-scoped failure isolation (model-side half; US3 owns the full
# assertion) — one Failure for the broken file, everything else still parses.
# ---------------------------------------------------------------------------


def test_broken_file_isolated_as_a_failure_all_others_still_parse():
    failures = CATALOG["failures"]
    assert len(failures) == 1, (
        "exactly one Failure is expected — the fixture repo's single "
        "unparseable file; got %d: %r" % (len(failures), failures)
    )
    assert failures[0]["source_path"] == "services/broken/catalog-info.yaml", (
        "the Failure must name the broken file itself, not some other entity"
    )
    assert len(CATALOG["services"]) == 8, (
        "a malformed file must degrade to a Failure for that file only — the "
        "other 8 fixture services must still parse; got %d: %r"
        % (len(CATALOG["services"]), sorted(CATALOG["services"]))
    )


# ---------------------------------------------------------------------------
# Rules the fixture corpus cannot reach — asserted by calling parse_entity
# directly.
#
# Every annotation value in the fixture repo is a JSON list, and every
# service-shaped fixture declares spec.owner. That leaves two documented
# parsing rules with no fixture that exercises them, which a mutation review
# confirmed empirically: comma-splitting a scalar annotation, and defaulting
# owner to None instead of "", both left the suite green. These tests close
# that gap at the function boundary rather than by contorting the fixture
# roster, which is pinned by data-model.md §10 for other reasons.
# ---------------------------------------------------------------------------


def _entity(annotations=None, spec=None):
    metadata = {"name": "probe-svc"}
    if annotations is not None:
        metadata["annotations"] = annotations
    return {
        "apiVersion": "backstage.io/v1alpha1",
        "kind": "Component",
        "metadata": metadata,
        "spec": {"type": "service", "owner": "team-probe"} if spec is None else spec,
    }


def test_scalar_annotation_parses_to_a_one_element_list():
    result = parse_entity(
        _entity(annotations={"oncall-harness/alert-match": "solo-matcher"}),
        "services/probe-svc/catalog-info.yaml",
    )
    assert result["service"]["alert_matchers"] == ["solo-matcher"], (
        "a scalar annotation value parses to a one-element list — the "
        "documented multi-valued parsing rule (data-model.md §1)"
    )


def test_commas_inside_a_scalar_matcher_are_never_split():
    result = parse_entity(
        _entity(annotations={"oncall-harness/alert-match": "svc,with,commas"}),
        "services/probe-svc/catalog-info.yaml",
    )
    assert result["service"]["alert_matchers"] == ["svc,with,commas"], (
        "a comma is a legal character inside a single matcher — splitting on "
        "it would make the annotation vocabulary ambiguous, so the rule is "
        "one scalar in, one element out (data-model.md §1)"
    )


def test_dependson_scalar_follows_the_same_no_split_rule():
    result = parse_entity(
        _entity(spec={"type": "service", "owner": "t", "dependsOn": "a,b"}),
        "services/probe-svc/catalog-info.yaml",
    )
    assert result["service"]["depends_on"] == ["a,b"], (
        "spec.dependsOn shares the multi-valued parsing rule — scalar to a "
        "one-element list, never comma-split"
    )


def test_absent_owner_defaults_to_empty_string_and_warns():
    result = parse_entity(
        _entity(spec={"type": "service"}),
        "services/probe-svc/catalog-info.yaml",
    )
    assert result["service"]["owner"] == "", (
        "owner defaults to the empty string, never None — the non-list half "
        "of the never-null invariant (data-model.md §1)"
    )
    kinds = [w["kind"] for w in result["warnings"]]
    assert kinds == ["missing_owner"], (
        "a service-shaped entity with no spec.owner parses fine AND is "
        "surfaced: owner is in PRD FR-13's minimal viable subset, so a "
        "service nobody owns must not parse clean and silent; got %r" % kinds
    )


def test_missing_owner_is_not_emitted_for_a_non_service_entity():
    result = parse_entity(
        {"kind": "Documentation", "metadata": {"name": "d"}, "spec": {}},
        "services/d/catalog-info.yaml",
    )
    kinds = [w["kind"] for w in result["warnings"]]
    assert kinds == ["ignored_entity"], (
        "missing_owner is a service-shaped-entity warning; a non-service "
        "entity yields only ignored_entity, not both; got %r" % kinds
    )


def test_parsed_list_fields_do_not_alias_the_source_document():
    document = _entity(annotations={"oncall-harness/runbooks": ["https://rb.example/a"]})
    result = parse_entity(document, "services/probe-svc/catalog-info.yaml")
    result["service"]["runbooks"].append("https://rb.example/injected")
    assert document["metadata"]["annotations"]["oncall-harness/runbooks"] == [
        "https://rb.example/a"
    ], "the returned Service is a value, not a view onto the source document"
