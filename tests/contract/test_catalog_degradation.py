"""T014 / US3 / SC-004: partial catalogs degrade, never error.

Ties ``tests/helpers/catalog_reference.py``'s ``disabled_features``/
``blast_radius`` (T012) and ``load_catalog``/``resolve`` back to
``specs/007-catalog-adapter/spec.md``'s "User Story 3 - Partial catalogs
degrade, never error":

- **SC-004** ("100% of degradation fixtures produce their documented
  per-field behavior; the malformed-file fixture never prevents any other
  fixture service from parsing"): every per-field-omission fixture yields
  exactly its documented feature, asserted against literal hardcoded sets —
  see the comment on the parametrize below for why literals and not
  ``golden-models.json``.
- **AS-2**'s degradation half: a service with no alert-match annotation
  routes an alert for it down the ask-once + fix-up path — the same
  ``miss`` outcome a resolution miss produces.
- **AS-3**: one malformed catalog file isolates to one ``Failure`` naming
  that file; every other fixture service still parses; the broken file
  contributes no service and no ``ignored_entity`` warning.
- **AS-4 + FR-006**: `dependsOn` widens blast radius one hop, dangling
  entries are kept, and the second hop is explicitly excluded — the
  depth bound.

Everything here asserts on ``disabled_features``/``blast_radius``/
``load_catalog``'s real return values, never on prose — same posture as
``test_catalog_model.py`` and ``test_catalog_resolution.py``.
"""

from pathlib import Path

import pytest

from conftest import fixture_path, load_fixture
from helpers.catalog_reference import (
    parse_entity,
    DEGRADED_FEATURES_BY_FIELD,
    blast_radius,
    disabled_features,
    load_catalog,
    resolve,
)

CATALOG = load_catalog(fixture_path("catalog", "repo"))

ALL_FOUR_FEATURES = frozenset(
    {"pane_driving", "alert_resolution", "runbook_fetch", "blast_radius_widening"}
)


# ---------------------------------------------------------------------------
# SC-004 — per-field degradation, asserted against LITERAL hardcoded sets.
#
# Deliberately NOT compared against golden-models.json's disabled_features:
# the goldens and DEGRADED_FEATURES_BY_FIELD were authored against the same
# documented expectations, so a golden-vs-golden comparison is
# self-consistently green even if both drifted from the spec together — it
# proves the encoding agrees with itself, not that it agrees with SC-004.
# These literals are the independent check.
# ---------------------------------------------------------------------------

PER_FIELD_CASES = [
    ("inventory", {"pane_driving"}),
    ("notifier", {"alert_resolution"}),
    ("ledger-svc", {"runbook_fetch"}),
    ("search-api", {"blast_radius_widening"}),
    ("payments-api", ALL_FOUR_FEATURES),
    ("checkout", set()),
]
PER_FIELD_IDS = [name for name, _ in PER_FIELD_CASES]


@pytest.mark.parametrize("name, expected", PER_FIELD_CASES, ids=PER_FIELD_IDS)
def test_disabled_features_matches_literal_expectation(name, expected):
    service = CATALOG["services"][name]
    assert disabled_features(service) == expected, (
        "%r must disable exactly %r and no other feature (SC-004) — got %r"
        % (name, expected, disabled_features(service))
    )


def test_single_omission_services_cover_all_four_features():
    # Coverage check over the literals above: the four single-omission
    # services collectively exercise every documented feature, so no feature
    # is asserted by zero cases. This is NOT a guard on the encoding's table —
    # the expectations here are literals, so a dropped table row fails the
    # individual case, not this union. The table itself is guarded below.
    single_omission_names = {"inventory", "notifier", "ledger-svc", "search-api"}
    union = set()
    for name, expected in PER_FIELD_CASES:
        if name in single_omission_names:
            union |= expected
    assert union == ALL_FOUR_FEATURES, (
        "the four single-omission services must collectively cover all four "
        "documented features exactly once each; got union=%r expected=%r"
        % (sorted(union), sorted(ALL_FOUR_FEATURES))
    )


def test_degradation_map_is_exactly_the_documented_four():
    # Reads the encoding's own table, which the literal cases above cannot:
    # they catch a row being DROPPED (an individual case then fails), but a row
    # being ADDED — a fifth feature keyed on some other field — is invisible to
    # them, because no fixture service would trip it. data-model.md §6 pins
    # exactly four rows.
    assert set(DEGRADED_FEATURES_BY_FIELD) == {
        "dashboards",
        "alert_matchers",
        "runbooks",
        "depends_on",
    }, (
        "the degradation map is keyed on exactly the four documented Service "
        "fields (data-model.md §6); got %r" % sorted(DEGRADED_FEATURES_BY_FIELD)
    )
    assert set(DEGRADED_FEATURES_BY_FIELD.values()) == ALL_FOUR_FEATURES, (
        "each documented field disables exactly one documented feature, and "
        "there are no others; got %r" % sorted(DEGRADED_FEATURES_BY_FIELD.values())
    )


def test_missing_owner_is_a_warning_not_a_disabled_feature():
    # Unreachable from the fixture roster — every fixture entity declares an
    # owner — so a mutation adding an owner-derived feature survived the whole
    # suite. Asserted directly instead: ownership is a catalog-quality signal
    # (it gets a missing_owner warning at parse time), and it disables no
    # feature, so a fully-annotated but unowned service degrades nothing.
    fully_annotated_but_ownerless = {
        "name": "ownerless",
        "owner": "",
        "runbooks": ["https://runbooks.example/x.md"],
        "dashboards": ["https://dashboards.example/x"],
        "alert_matchers": ["x-5xx"],
        "depends_on": ["y"],
    }
    assert disabled_features(fully_annotated_but_ownerless) == set(), (
        "a missing owner is a catalog-quality warning, never a disabled "
        "feature — ownership gates no feature (data-model.md §1, §6)"
    )


def test_golden_disabled_features_agree_with_the_encoding():
    # A drift check ALONGSIDE the literals above, never in place of them: the
    # goldens are hand-authored, so this catches the two artifacts diverging
    # without being the primary SC-004 assertion (which stays literal).
    goldens = load_fixture("catalog", "golden-models.json")
    assert goldens, "golden set must be non-empty for this drift check to bite"
    for name, golden in sorted(goldens.items()):
        assert set(golden["disabled_features"]) == disabled_features(
            CATALOG["services"][name]
        ), (
            "%r: golden-models.json's disabled_features has drifted from the "
            "encoding — golden=%r encoding=%r"
            % (name, sorted(golden["disabled_features"]),
               sorted(disabled_features(CATALOG["services"][name])))
        )


def test_blast_radius_is_sorted():
    # Unobservable on the fixture roster — every fixture service has at most
    # one dependsOn entry — so a mutation returning them reversed survived.
    # data-model.md §9 pins sorted output; asserted on a synthetic catalog.
    catalog = {
        "services": {"a": {"depends_on": ["zeta", "alpha", "mid"]}},
        "sources": {},
    }
    assert blast_radius("a", catalog) == ["alpha", "mid", "zeta"], (
        "blast_radius returns its one-hop entries sorted (data-model.md §9), "
        "so the widened set is presented deterministically"
    )


# ---------------------------------------------------------------------------
# AS-2's degradation half — a matcher-less service's alert resolves miss,
# the same path a resolution miss takes.
# ---------------------------------------------------------------------------


def test_notifier_alert_match_disabled_and_its_alert_misses():
    assert "alert_resolution" in disabled_features(CATALOG["services"]["notifier"]), (
        "notifier carries no oncall-harness/alert-match annotation — "
        "alert_resolution must be disabled for it"
    )
    # notifier has no alert_matchers, so it cannot hit the exact stage at
    # all. This alert deliberately does NOT contain the string "notifier":
    # notifier has no matchers so it cannot match at the exact stage, but the
    # substring stage WOULD legitimately resolve it if the alert spelled its
    # name — an alert that did would assert the opposite of what this test
    # reads.
    alert = {
        "alert_id": "n1",
        "tags": ["email-queue-backlog"],
        "fields": {"name": "outbound email backlog"},
    }
    resolution = resolve(alert, CATALOG)
    assert resolution["outcome"] == "miss", (
        "notifier's alert-match omission must route this alert down the "
        "ask-once + fix-up path — the same 'miss' outcome a resolution miss "
        "takes (AS-2); got %r" % resolution
    )


# ---------------------------------------------------------------------------
# AS-3 — malformed-file isolation.
# ---------------------------------------------------------------------------


def test_broken_file_isolates_to_one_failure_all_eight_services_still_parse():
    failures = CATALOG["failures"]
    assert len(failures) == 1, (
        "exactly one Failure is expected — the fixture repo's single "
        "unparseable file; got %d: %r" % (len(failures), failures)
    )
    failure = failures[0]
    assert failure["source_path"] == "services/broken/catalog-info.yaml", (
        "the Failure must name the broken file itself, not some other "
        "entity; got %r" % failure["source_path"]
    )
    assert failure.get("reason"), (
        "the Failure must carry a non-empty reason — surfaced, not fatal, "
        "means the responder learns why; got %r" % failure
    )
    assert len(CATALOG["services"]) == 8, (
        "a malformed file must degrade to a Failure for that file only — "
        "all 8 other fixture services must still parse; got %d: %r"
        % (len(CATALOG["services"]), sorted(CATALOG["services"]))
    )
    broken_ignored = [
        w
        for w in CATALOG["warnings"]
        if w["kind"] == "ignored_entity"
        and "services/broken/catalog-info.yaml" in w.get("sources", [])
    ]
    assert not broken_ignored, (
        "the broken file must never reach entity classification at all — a "
        "parse failure happens before ignored_entity would even be "
        "considered, so it must contribute no service AND no ignored_entity "
        "warning; got %r" % broken_ignored
    )


# ---------------------------------------------------------------------------
# AS-4 + FR-006 — blast radius one-hop widening and the depth bound.
# ---------------------------------------------------------------------------


def test_checkout_blast_radius_widens_one_hop_to_inventory():
    assert blast_radius("checkout", CATALOG) == ["inventory"], (
        "checkout's own dependsOn (['inventory']) must widen the assessment "
        "by exactly that one hop (AS-4, FR-006)"
    )


def test_checkout_blast_radius_excludes_the_second_hop_ledger_svc():
    # checkout -> inventory -> ledger-svc: the second hop of this chain must
    # NOT appear in checkout's blast radius. This is the actual FR-006 pin —
    # "one hop, v1" — asserted as its own statement rather than folded into
    # the equality above, since a bug that added ledger-svc alongside
    # inventory could otherwise slip past a loosely-worded message.
    assert "ledger-svc" not in blast_radius("checkout", CATALOG), (
        "blast_radius must widen by checkout's OWN dependsOn only, one hop "
        "(FR-006) — ledger-svc is inventory's dependency, two hops from "
        "checkout, and must not appear here"
    )


def test_inventory_blast_radius_reaches_ledger_svc_directly():
    # Proves the second hop above is a real exclusion, not an artifact of an
    # absent edge: inventory -> ledger-svc genuinely exists in the fixture,
    # one hop from inventory itself.
    assert blast_radius("inventory", CATALOG) == ["ledger-svc"], (
        "inventory's own dependsOn (['ledger-svc']) must widen by exactly "
        "that one hop — this proves the checkout->inventory->ledger-svc "
        "chain's second hop is a real edge the depth bound excludes, not an "
        "absent one"
    )


def test_search_api_absent_dependson_proceeds_unwidened():
    assert blast_radius("search-api", CATALOG) == [], (
        "search-api carries no spec.dependsOn — the assessment must proceed "
        "unwidened, yielding an empty blast radius (AS-4)"
    )


def test_billing_dangling_dependency_kept_in_blast_radius_and_warned_once():
    assert blast_radius("billing", CATALOG) == ["nonexistent-svc"], (
        "billing's dangling dependsOn entry (nonexistent-svc) must be KEPT "
        "in the blast radius, never filtered (FR-006)"
    )
    dangling = [w for w in CATALOG["warnings"] if w["kind"] == "dangling_dependency"]
    assert len(dangling) == 1, (
        "exactly one dangling_dependency warning is expected across the "
        "whole catalog; got %d: %r" % (len(dangling), dangling)
    )
    assert dangling[0]["service"] == "billing", (
        "the warning names the DEPENDER, not the missing dependency — "
        "annotations.md makes a normative claim about this field, and "
        "nothing else in the suite pins it; got %r" % dangling[0]["service"]
    )
    assert "nonexistent-svc" in dangling[0]["detail"], (
        "the catalog's one dangling_dependency warning must name "
        "nonexistent-svc; got %r" % dangling[0]
    )


def test_unknown_service_name_yields_no_widening_without_raising():
    assert blast_radius("no-such-service", CATALOG) == [], (
        "a name absent from the catalog must yield [] rather than raise — "
        "the assessment simply proceeds unwidened"
    )


# ---------------------------------------------------------------------------
# Degradation never errors — the mechanical form of "no partial annotation
# ever errors a session".
# ---------------------------------------------------------------------------


def test_load_catalog_never_errors_over_a_messy_fixture_repo():
    catalog = load_catalog(fixture_path("catalog", "repo"))
    assert catalog is not None, (
        "load_catalog must return a catalog, never None, over a repo "
        "containing a broken file, a non-service entity, a duplicate pair, "
        "a dangling dependency, and four partially-annotated services"
    )
    assert catalog["services"], (
        "load_catalog's services must be non-empty despite every messy "
        "condition the fixture repo packs in at once — degradation never "
        "errors the whole session"
    )


# ---------------------------------------------------------------------------
# Pins that the fixture roster structurally cannot reach — asserted on
# synthetic catalogs. A whole-diff review found both stated in data-model.md
# and spec.md with no test anywhere.
# ---------------------------------------------------------------------------


def test_a_dependson_cycle_is_harmless_under_the_one_hop_bound():
    # spec.md's "dependsOn cycles or depth" edge case. One-hop traversal makes
    # a cycle harmless BY CONSTRUCTION, which is exactly why it is worth
    # pinning: a later multi-hop change would recurse forever here, and this
    # is the test that would say so instead of the suite hanging.
    catalog = {
        "services": {
            "a": {"depends_on": ["b"]},
            "b": {"depends_on": ["a"]},
        },
        "sources": {},
    }
    assert blast_radius("a", catalog) == ["b"]
    assert blast_radius("b", catalog) == ["a"]


def test_a_self_dependency_does_not_recurse_either():
    catalog = {"services": {"a": {"depends_on": ["a"]}}, "sources": {}}
    assert blast_radius("a", catalog) == ["a"], (
        "a service depending on itself is a catalog-authoring oddity, not a "
        "traversal problem — one hop returns it and stops"
    )


def test_an_unreadable_repo_root_is_surfaced_as_a_failure():
    # spec.md's "catalog repo unreachable" edge case, encoding side. A walk
    # over a missing path yields nothing and raises nothing, so without this
    # a caller cannot tell an unreachable repo from an empty one — and every
    # other absence in the module produces a Failure or a Warning.
    catalog = load_catalog(str(fixture_path("catalog", "no-such-repo-root")))
    assert catalog["services"] == {}
    assert len(catalog["failures"]) == 1, (
        "an unreadable repo root yields exactly one Failure naming it — not a "
        "silent empty catalog indistinguishable from a repo with no services"
    )
    assert "not a readable directory" in catalog["failures"][0]["reason"]


def test_a_duplicate_losers_own_warning_survives_resolution(tmp_path):
    # data-model.md's "Warning provenance across duplicate resolution" pin.
    # This MUST go through load_catalog: duplicate resolution is its job, and
    # an earlier version of this test called parse_entity twice, which cannot
    # observe survival through resolution at all — a mutant that dropped
    # loser-derived warnings passed it. Unreachable from the fixture roster
    # because every fixture entity declares an owner, hence the temp repo.
    import json

    def write(directory, name, spec):
        service_dir = tmp_path / "services" / directory
        service_dir.mkdir(parents=True)
        document = {"kind": "Component", "metadata": {"name": name}, "spec": spec}
        (service_dir / "catalog-info.yaml").write_text(
            json.dumps(document, indent=2), encoding="utf-8"
        )

    write("aaa", "dup", {"owner": "team-a"})   # sorts first -> canonical
    write("zzz", "dup", {})                    # loses, and has no owner

    catalog = load_catalog(tmp_path)

    assert catalog["sources"]["dup"] == "services/aaa/catalog-info.yaml", (
        "the lexicographically-first source path wins the tie-break"
    )
    assert catalog["services"]["dup"]["owner"] == "team-a", (
        "the canonical entity's values survive, not the loser's"
    )
    kinds = sorted(w["kind"] for w in catalog["warnings"])
    assert kinds == ["duplicate_name", "missing_owner"], (
        "the loser's own missing_owner survives into the catalog's warning "
        "stream even though its entity was dropped — the warning stream is a "
        "record of catalog quality, and a problem in a file that lost a "
        "tie-break is still a problem in the team's repo; got %r" % kinds
    )
    missing_owner = [w for w in catalog["warnings"] if w["kind"] == "missing_owner"][0]
    assert missing_owner["service"] == "dup", (
        "the warning names what the offending entity DECLARED; the resolved "
        "'dup' service came from the other file entirely, so this is not a "
        "key into catalog['services']"
    )


UNSET_ROOTS = ["", None, 0, [], Path("")]
UNSET_ROOT_IDS = ["empty-string", "none", "zero", "empty-list", "path-of-empty-string"]


@pytest.mark.parametrize("root", UNSET_ROOTS, ids=UNSET_ROOT_IDS)
def test_an_unset_or_non_path_repo_root_is_surfaced_not_walked(root):
    # Path("") is Path("."), so an unset config value that a caller has
    # already wrapped would otherwise walk the CURRENT WORKING DIRECTORY and
    # return whatever services happened to be under it — the worst possible
    # answer to "is the catalog repo reachable?". Every spelling is rejected.
    catalog = load_catalog(root)
    assert catalog["services"] == {}, (
        "an unset root must never resolve services — %r walked something" % (root,)
    )
    assert len(catalog["failures"]) == 1, (
        "an unset root is surfaced as exactly one Failure, never a silent "
        "empty catalog; got %r" % catalog["failures"]
    )
    assert "unset or not a path" in catalog["failures"][0]["reason"]


@pytest.mark.parametrize("root", UNSET_ROOTS + ["/nonexistent/xyz"], ids=UNSET_ROOT_IDS + ["missing-dir"])
def test_every_early_return_yields_the_same_catalog_shape(root):
    # The catalog shape was hand-written in three places; deleting a key from
    # either early-return copy was invisible while deleting it from the main
    # return failed instantly. Pinned against the real parse's shape.
    good = load_catalog(fixture_path("catalog", "repo"))
    assert set(load_catalog(root)) == set(good), (
        "every return path yields the same five-part catalog shape — a part "
        "added to one and not the others is exactly the drift this catches"
    )


def test_blast_radius_survives_a_malformed_services_collection():
    assert blast_radius("a", {"services": ["not", "a", "dict"]}) == [], (
        "blast_radius promises it never raises for a malformed catalog; a "
        "non-dict services collection is the shape that used to break it"
    )


def test_resolution_survives_a_malformed_sources_collection():
    # _candidates_by_source reads catalog["sources"] to order candidates; a
    # malformed sources collection used to raise there while its sibling
    # fixup_offer was guarded in the same commit.
    catalog = {
        "services": {
            "a": {"alert_matchers": ["shared"]},
            "b": {"alert_matchers": ["shared"]},
        },
        "sources": "junk",
    }
    resolution = resolve({"alert_id": "x", "tags": ["shared"], "fields": {}}, catalog)
    assert resolution["outcome"] == "ambiguous"
    assert sorted(resolution["candidates"]) == ["a", "b"]
