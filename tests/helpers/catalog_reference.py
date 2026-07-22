"""The dev-only reference encoding of the catalog conventions documented in
``skills/catalog/`` (the annotation mapping, entity classification, the
degradation posture) and of ``tests/fixtures/catalog/README.md``'s format
decision (research R2 — ``catalog-info.yaml`` written in strict JSON syntax,
parsed with stdlib ``json``, never a YAML library).

This module IS: the CI instrument that lets those documented rules be
*exercised* by hermetic tests (Constitution VIII) instead of merely asserted
on prose. Nothing here ships (Constitution I; FR-009) — the catalog skill
explicitly does not ship a parsing library or catalog-adapter code; at
runtime the "parser" is an agent reading ``catalog-info.yaml`` files through
the code capability, guided by the skill's prose, not this module.

This module is NOT: proof that a live agent actually follows that prose when
it reads a real catalog repo. That is design §10's scenario-harness
territory — a live-agent exercise, never a hermetic unit/contract test. This
module only pins what "correct" looks like for the fixtures a hermetic test
can run against; it says nothing about agent behavior.

House style mirrors ``tests/helpers/doctor_flows.py``: plain functions over
plain dicts (no classes, no dataclasses), each step's comment citing the
prose section it encodes.
"""

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Module-level vocabularies (skills/catalog/ annotation mapping;
# tests/fixtures/catalog/README.md "Annotation keys")
# ---------------------------------------------------------------------------

CANONICAL_ANNOTATIONS = {  # annotation key -> Service field
    "oncall-harness/runbooks": "runbooks",
    "grafana/dashboard-selector": "dashboards",
    "oncall-harness/alert-match": "alert_matchers",
}
LINKAGE_ANNOTATIONS = {  # annotation key -> internal linkage name
    "pagerduty.com/service-id": "paging_id",
    "github.com/project-slug": "repo_slug",
}
SERVICE_KINDS = frozenset({"Component", "Service"})
MODEL_FIELDS = ("name", "owner", "runbooks", "dashboards", "alert_matchers", "depends_on")


# ---------------------------------------------------------------------------
# parse_entity (skills/catalog/ annotation mapping + entity classification;
# PRD FR-006 dependsOn kept-not-filtered; FR-013 owner in the minimal viable
# subset)
# ---------------------------------------------------------------------------


def _as_list(value):
    """Multi-valued parsing rule: a value that is already a list stays a
    list; a scalar non-empty string becomes a one-element list; anything
    else (missing key, ``None``, an empty string, a non-string/non-list
    scalar) yields an empty list — never ``None``, never absent, so
    consumers can branch on emptiness alone.

    Deliberately never splits on commas: a comma is a legal character inside
    a single alert matcher, and splitting would make the annotation
    vocabulary ambiguous (skills/catalog/ annotation mapping). This same
    rule serves both the three annotation-derived list fields and
    ``spec.dependsOn``.
    """
    if isinstance(value, list):
        # Copy rather than alias: the returned Service is a value, not a view
        # onto the source document. Aliasing is inert while load_catalog
        # re-parses every file per call, but a caller mutating
        # ``service["runbooks"]`` must never reach back into the parsed
        # annotation it came from.
        return list(value)
    if isinstance(value, str) and value:
        return [value]
    return []


def _as_dict(value):
    """Defensive shape guard: treat anything that isn't already a ``dict``
    (missing key, ``None``, or a malformed non-object value some garbage
    JSON document might carry) as an empty mapping, so a missing/malformed
    ``metadata``, ``spec``, or ``annotations`` block can never raise."""
    return value if isinstance(value, dict) else {}


def _parse_linkage(metadata):
    """The internal linkage map (``paging_id``, ``repo_slug``) parsed from
    ``LINKAGE_ANNOTATIONS``. Lives BESIDE the Service model, never inside
    it — linkage is plumbing for alert-to-service resolution, not a model
    field. A key is present in the returned dict only when its annotation is
    present as a non-empty string; an entity with neither linkage
    annotation gets an empty dict, never ``None``.
    """
    annotations = _as_dict(metadata.get("annotations"))
    linkage = {}
    for annotation_key, linkage_name in LINKAGE_ANNOTATIONS.items():
        value = annotations.get(annotation_key)
        if isinstance(value, str) and value:
            linkage[linkage_name] = value
    return linkage


def _ignored_entity_reason(source_path, kind, kind_is_service, name_is_valid):
    """Name the condition that actually failed, not both.

    A 3am reader of "kind X or missing name" has to go re-derive which half
    fired. Both booleans are already computed at the call site, so the
    message can simply say.
    """
    if not kind_is_service and not name_is_valid:
        return (
            "entity at {} has kind {!r}, which is not service-shaped, and no "
            "usable metadata.name — ignored, never parsed into the model"
        ).format(source_path, kind)
    if not kind_is_service:
        return (
            "entity at {} has kind {!r}, which is not service-shaped — "
            "ignored, never parsed into the model"
        ).format(source_path, kind)
    return (
        "entity at {} has a service-shaped kind {!r} but a missing or empty "
        "metadata.name — ignored, never parsed into the model"
    ).format(source_path, kind)


def parse_entity(document, source_path):
    """One ``catalog-info.yaml`` document (already ``json.loads``-parsed) ->
    ``{"service": <Service or None>, "linkage": <dict>, "warnings":
    [<Warning>...]}``.

    Entity classification (skills/catalog/): service-shaped iff
    ``document["kind"]`` is in ``SERVICE_KINDS`` AND ``metadata.name`` is a
    non-empty string. A non-service-shaped entity (wrong kind, or missing/
    empty/non-string name) yields ``service: None`` plus one
    ``ignored_entity`` warning — this is how the ``docs-site`` fixture
    (``kind: "Documentation"``) is handled: ignored, never raised on.

    ``owner`` always defaults to ``""`` and never fails parsing on its own
    absence — but a service-shaped entity with a missing/empty
    ``spec.owner`` emits one ``missing_owner`` warning. This is a
    catalog-quality signal, deliberately NOT modeled as a disabled feature
    (ownership disables no feature); PRD FR-13 puts ``owner`` in the minimal
    viable subset, so its absence must be surfaced, not silent.

    Every list-valued Service field (``runbooks``, ``dashboards``,
    ``alert_matchers``, ``depends_on``) goes through ``_as_list`` — empty
    list, never ``None``, never absent, never comma-split.

    Defensive about shape throughout: a ``document``, ``metadata``, or
    ``spec`` that is missing or not a ``dict`` never raises — it is treated
    as empty, same as ``_as_dict``'s contract.
    """
    document = _as_dict(document)
    metadata = _as_dict(document.get("metadata"))
    spec = _as_dict(document.get("spec"))

    kind = document.get("kind")
    name = metadata.get("name")
    name_is_valid = isinstance(name, str) and name != ""
    kind_is_service = isinstance(kind, str) and kind in SERVICE_KINDS

    linkage = _parse_linkage(metadata)

    if not kind_is_service or not name_is_valid:
        warning = {
            "kind": "ignored_entity",
            "service": name if name_is_valid else None,
            "detail": (
                _ignored_entity_reason(source_path, kind, kind_is_service, name_is_valid)
            ),
            "sources": [source_path],
        }
        return {"service": None, "linkage": linkage, "warnings": [warning]}

    warnings = []
    owner_raw = spec.get("owner")
    if isinstance(owner_raw, str) and owner_raw:
        owner = owner_raw
    else:
        owner = ""
        warnings.append(
            {
                "kind": "missing_owner",
                "service": name,
                "detail": (
                    "service {!r} at {} has no spec.owner — catalog-quality "
                    "warning; parsing does not fail over it (FR-13)".format(
                        name, source_path
                    )
                ),
                "sources": [source_path],
            }
        )

    annotations = _as_dict(metadata.get("annotations"))
    service = {
        "name": name,
        "owner": owner,
        "depends_on": _as_list(spec.get("dependsOn")),
    }
    for annotation_key, field_name in CANONICAL_ANNOTATIONS.items():
        service[field_name] = _as_list(annotations.get(annotation_key))

    return {"service": service, "linkage": linkage, "warnings": warnings}


# ---------------------------------------------------------------------------
# load_catalog (tests/fixtures/catalog/README.md "Layout" + "Fixture service
# roster"; PRD FR-006 dangling dependency kept-not-filtered)
# ---------------------------------------------------------------------------


def _read_document(file_path):
    """Parse one ``catalog-info.yaml`` file with stdlib ``json`` (research
    R2 — the fixtures are strict-JSON, a valid subset of YAML 1.2 flow
    style). Returns ``(document_or_None, failure_reason_or_None)`` — never
    raises; a file that fails to parse, or whose top-level JSON value isn't
    an object, produces a reason string and a ``None`` document instead
    (per-file failure isolation: this is the only place a parse error is
    allowed to surface, and it surfaces as data, never an exception).
    """
    try:
        text = file_path.read_text(encoding="utf-8")
        document = json.loads(text)
    except (OSError, ValueError) as exc:
        return None, str(exc)
    if not isinstance(document, dict):
        return None, "parsed JSON value is not an object (got {})".format(
            type(document).__name__
        )
    return document, None


def load_catalog(repo_root):
    """Walk every ``catalog-info.yaml`` under ``repo_root`` (recursively)
    and resolve it into a catalog:

    ``{"services": {name: Service}, "linkage": {name: {...}}, "sources":
    {name: source_path}, "warnings": [Warning], "failures": [Failure]}``.

    Always returns a catalog — there is no error path. Three isolation/
    resolution rules, each surfaced rather than fatal:

    - **Per-file failure isolation**: a file that fails to parse (or is not
      a JSON object) contributes one ``Failure`` (``{"source_path",
      "reason"}``) and never raises; every other file still parses.
    - **Duplicate metadata.name**: all service-shaped entities are grouped
      by name first (independent of directory-walk order, which is why this
      is deterministic by construction); the group member whose
      ``source_path`` sorts first lexicographically is canonical and the
      rest are dropped, with one ``duplicate_name`` warning naming every
      member's source path (sorted).
    - **Dangling dependsOn**: computed only after every service is
      resolved, so it sees the final name set. A ``depends_on`` entry
      naming an absent service gets one ``dangling_dependency`` warning per
      entry — the entry itself is KEPT in the model, never filtered (FR-006
      authorizes no filter; shrinking a blast radius silently would be the
      opposite of this slice's surfaced-not-fatal posture).

    Warnings ``parse_entity`` returns for every file — including those of a
    duplicate group's dropped losers — are carried into the catalog's
    ``warnings`` list unconditionally.
    """
    # Checked BEFORE Path() conversion: Path(None) raises, and Path("") is
    # Path("."), which would silently walk the current working directory —
    # the worst possible answer to "is the catalog repo reachable?". An unset
    # config value is the most plausible way a caller gets here.
    if not isinstance(repo_root, (str, Path)) or not str(repo_root):
        return {
            "services": {},
            "linkage": {},
            "sources": {},
            "warnings": [],
            "failures": [
                {
                    "source_path": "",
                    "reason": "catalog repo root is unset or not a path",
                }
            ],
        }

    repo_root = Path(repo_root)
    warnings = []
    failures = []

    # An unreadable root is the one absence that would otherwise be silent.
    # ``rglob`` on a nonexistent path — or on a path that is a regular file —
    # yields nothing and raises nothing, so a caller could not tell "the
    # team's catalog repo is unreachable" from "the repo contains no
    # catalog-info.yaml". That distinction is exactly the catalog-unreachable
    # case SKILL.md promises is surfaced, and every other absence in this
    # module produces a Failure or a Warning. This one does too.
    if not repo_root.is_dir():
        return {
            "services": {},
            "linkage": {},
            "sources": {},
            "warnings": [],
            "failures": [
                {
                    # The one source_path that is NOT repo-relative: there is
                    # no root to be relative to. Documented as the explicit
                    # exception in data-model.md's relativity rule.
                    "source_path": repo_root.as_posix(),
                    "reason": "catalog repo root is not a readable directory",
                }
            ],
        }
    # name -> [(source_path, Service, linkage_dict), ...], collected across
    # every service-shaped entity before any duplicate is resolved, so
    # resolution never depends on which file the walk visited first.
    candidates_by_name = {}

    for file_path in sorted(repo_root.rglob("catalog-info.yaml")):
        source_path = file_path.relative_to(repo_root).as_posix()
        document, reason = _read_document(file_path)
        if reason is not None:
            failures.append({"source_path": source_path, "reason": reason})
            continue

        parsed = parse_entity(document, source_path)
        warnings.extend(parsed["warnings"])

        service = parsed["service"]
        if service is None:
            continue

        candidates_by_name.setdefault(service["name"], []).append(
            (source_path, service, parsed["linkage"])
        )

    services = {}
    linkage = {}
    sources = {}
    for name in sorted(candidates_by_name):
        group = sorted(candidates_by_name[name], key=lambda entry: entry[0])
        winner_source, winner_service, winner_linkage = group[0]
        services[name] = winner_service
        sources[name] = winner_source
        linkage[name] = winner_linkage

        if len(group) > 1:
            warnings.append(
                {
                    "kind": "duplicate_name",
                    "service": name,
                    "detail": (
                        "multiple entities declare metadata.name {!r}; {!r} "
                        "is canonical (source_path sorts first "
                        "lexicographically)".format(name, winner_source)
                    ),
                    "sources": sorted(entry[0] for entry in group),
                }
            )

    for name in sorted(services):
        for dependency in services[name]["depends_on"]:
            if dependency not in services:
                warnings.append(
                    {
                        "kind": "dangling_dependency",
                        "service": name,
                        "detail": (
                            "{!r} depends on {!r}, which is not present in "
                            "the catalog — kept, never filtered (FR-006)".format(
                                name, dependency
                            )
                        ),
                        "sources": [sources[name]],
                    }
                )

    return {
        "services": services,
        "linkage": linkage,
        "sources": sources,
        "warnings": warnings,
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# resolve (skills/catalog/references/resolution.md "The match order"; PRD
# FR-003 alert-to-service resolution)
# ---------------------------------------------------------------------------


def _match_strings(alert):
    """Every string an alert offers a matcher to compare against: every tag
    plus every field VALUE (never a field name) — flattened into one list.
    Defensive per this slice's contract: a missing/non-list ``tags`` or a
    missing/non-dict ``fields`` contributes nothing rather than raising, and
    a non-string tag or field value is dropped rather than coerced (a
    coerced ``str(123)`` accidentally equaling a matcher would be
    surprising, undocumented behavior no prose describes).
    """
    alert = _as_dict(alert)
    # ``tags`` deliberately does NOT go through ``_as_list``: that helper
    # wraps a bare scalar string into a one-element list, which is right for
    # an annotation value but wrong here — a scalar ``tags`` is malformed
    # input, not a single tag, and silently accepting it would invent a
    # matching surface no prose describes. ``fields`` has no such nuance.
    tags = alert.get("tags")
    if not isinstance(tags, list):
        tags = []
    fields = _as_dict(alert.get("fields"))

    strings = [tag for tag in tags if isinstance(tag, str)]
    strings.extend(value for value in fields.values() if isinstance(value, str))
    return strings


def _normalize(text):
    """The exact/substring comparison's shared normalization: case-fold and
    whitespace-trim (resolution.md's "case-insensitively, whitespace-
    trimmed"). Centralized so both stages apply the identical rule."""
    return text.strip().lower()


def _candidates_by_source(names, catalog):
    """Sort matched service names by their **source path**
    (``catalog["sources"][name]``), never by name — resolution.md's
    "Candidates are ordered by source path". The `zz-billing` fixture
    (directory `zz-billing`, `metadata.name` `billing`) exists specifically
    to invert those two orderings and catch a name-sorting implementation.
    """
    sources = _as_dict(_as_dict(catalog).get("sources"))
    return sorted(names, key=lambda name: sources.get(name, ""))


def _exact_stage_hits(match_strings, catalog):
    """Stage 1: for every service, for every entry in its ``alert_matchers``
    only — never the service's own ``name`` — a hit when the matcher
    equals, after ``_normalize``, any alert string. A service is added at
    most once even if several of its matchers hit (``break`` on first).

    An empty matcher never hits, mirroring the substring stage's own
    emptiness guard. This is not hypothetical tidiness: a service whose
    ``alert_matchers`` contains the empty string — committed by hand, or by
    a harness predating ``fixup_offer``'s ``commit_ready`` flag — would
    otherwise match *every* sparse alert exactly, swallowing unrelated
    incidents. ``fixup_offer`` refuses to *produce* such a matcher; this is
    the read side of the same guard, and defense in depth means neither side
    is trusted to be the only one.
    """
    normalized_alert_strings = set(_normalize(s) for s in match_strings)
    hits = []
    for name, service in _as_dict(_as_dict(catalog).get("services")).items():
        if not isinstance(name, str):
            continue
        for matcher in _as_list(_as_dict(service).get("alert_matchers")):
            if not isinstance(matcher, str):
                continue
            normalized_matcher = _normalize(matcher)
            if normalized_matcher and normalized_matcher in normalized_alert_strings:
                hits.append(name)
                break
    return hits


def _substring_stage_hits(match_strings, catalog):
    """Stage 2 (only ever invoked when stage 1 hit nothing at all): for
    every service, a hit when the service's own name occurs as a substring
    of any alert string, after ``_normalize``. Direction is pinned per
    resolution.md — name-inside-alert-field, never the reverse; the
    ``reverse-direction-probe`` case (alert field ``"ledger"`` inside the
    service name ``ledger-svc``) exists to catch a flipped ``in`` check."""
    normalized_values = [_normalize(s) for s in match_strings]
    hits = []
    for name in _as_dict(_as_dict(catalog).get("services")):
        if not isinstance(name, str):
            continue
        normalized_name = _normalize(name)
        for value in normalized_values:
            if normalized_name and normalized_name in value:
                hits.append(name)
                break
    return hits


def _stage_resolution(hits, stage, catalog):
    """Turn a non-empty list of same-stage hits into the ``outcome``/
    ``service``/``candidates``/``stage`` shape: a single hit resolves
    (``outcome`` == ``stage``, ``service`` present, ``candidates`` empty); 2+
    hits is always ``ambiguous`` carrying every candidate — resolution.md's
    "never a silent pick" — with ``service`` absent rather than an arbitrary
    pick from the tie."""
    ordered = _candidates_by_source(hits, catalog)
    if len(ordered) == 1:
        return {
            "outcome": stage,
            "service": ordered[0],
            "candidates": [],
            "stage": stage,
        }
    return {
        "outcome": "ambiguous",
        "candidates": ordered,
        "stage": stage,
    }


def resolve(alert, catalog):
    """One firing ``alert`` against a ``load_catalog``-shaped ``catalog`` ->
    ``{"outcome": <exact|substring|ambiguous|miss>, "service": <str, exact/
    substring only>, "candidates": [<str>...], "stage": <exact|substring,
    absent on miss>}`` — resolution.md's "The match order".

    The exact stage runs first and covers every service's ``alert_matchers``
    only (never a service's own ``name`` — that is the substring stage's
    input, and only that). The substring stage runs ONLY when the exact
    stage produced zero hits across the whole service set — exactness beats
    substring globally, not per-service, so a single exact hit anywhere
    stops the substring stage from running at all, even for services whose
    own matchers didn't produce that hit (the ``exact-beats-substring`` case
    pins exactly this: a different service would substring-match, but the
    exact hit elsewhere pre-empts it). Whichever stage matched, 2+ hits is
    ``ambiguous`` with every candidate surfaced, source-path ordered; 0 hits
    at both stages is ``miss``, with no ``service`` and no ``stage`` key at
    all (not ``None`` — the key is genuinely absent, so a caller can branch
    on ``"stage" in resolution``).
    """
    match_strings = _match_strings(alert)

    exact_hits = _exact_stage_hits(match_strings, catalog)
    if exact_hits:
        return _stage_resolution(exact_hits, "exact", catalog)

    substring_hits = _substring_stage_hits(match_strings, catalog)
    if substring_hits:
        return _stage_resolution(substring_hits, "substring", catalog)

    return {"outcome": "miss", "candidates": []}


# ---------------------------------------------------------------------------
# fixup_offer (skills/catalog/references/resolution.md "The fix-up offer")
# ---------------------------------------------------------------------------


def _discriminating_field(alert):
    """The alert's discriminating field, resolved by resolution.md's pinned
    order: ``fields.name`` if non-empty, else ``fields.service_hint`` if
    non-empty, else the first entry of ``tags``, else ``""``. Deterministic
    by construction — this is a fixed lookup order, never a judgment call
    about which field "looks more meaningful"."""
    alert = _as_dict(alert)
    fields = _as_dict(alert.get("fields"))

    name = fields.get("name")
    if isinstance(name, str) and name:
        return name

    service_hint = fields.get("service_hint")
    if isinstance(service_hint, str) and service_hint:
        return service_hint

    tags = alert.get("tags")
    if isinstance(tags, list) and tags and isinstance(tags[0], str):
        return tags[0]

    return ""


def fixup_offer(alert, service_name, catalog):
    """The ready-to-commit annotation offer for a miss, once the responder
    has named ``service_name`` in the ask-once exchange (that interaction
    itself, and the agent surfacing this offer, are another slice's
    concern — this function only computes the offer's content) ->
    ``{"source_path", "annotation_key", "annotation_value", "snippet"}``.

    **The responder commits this. No agent ever writes to the catalog** —
    it is human-curated, PR-reviewed data, and that boundary is the whole
    point of reading it fresh each session rather than owning a copy of it
    (resolution.md "The fix-up offer").

    ``annotation_key`` is always the literal ``"oncall-harness/alert-match"``
    (the same key ``CANONICAL_ANNOTATIONS`` maps to ``alert_matchers``).
    ``annotation_value`` comes from ``_discriminating_field``. ``source_path``
    is the named service's existing source when it is already in the
    catalog, or — the pinned convention for a brand-new entity, absent from
    the catalog entirely — ``"services/<service_name>/catalog-info.yaml"``,
    relative to the repo root exactly as ``load_catalog``'s ``source_path``
    values are. ``snippet`` renders the key/value pair through stdlib
    ``json`` in the same strict-JSON, 2-space-indent style
    ``tests/fixtures/catalog/README.md``'s fixtures use, so a responder can
    paste it into a target file's ``annotations`` block mechanically.
    """
    annotation_value = _discriminating_field(alert)

    sources = _as_dict(catalog).get("sources", {})
    if not isinstance(sources, dict):
        sources = {}
    if service_name in sources:
        source_path = sources[service_name]
    else:
        source_path = "services/{}/catalog-info.yaml".format(service_name)

    annotation_key = "oncall-harness/alert-match"

    # An empty discriminating value makes the offer NOT commit-ready, and the
    # caller is told so rather than being handed a paste-ready snippet that
    # would harm the team. ``_exact_stage_hits`` guards against a committed
    # empty matcher on the read side; this is the same rule enforced on the
    # write side, so the harness never *produces* the thing it defends
    # against. Committing `alert_matchers: [""]` would give that service a
    # matcher that swallows every sparse alert.
    commit_ready = bool(annotation_value)
    if commit_ready:
        value_json = json.dumps([annotation_value], indent=2)
        snippet = '"{}": {}'.format(annotation_key, value_json)
    else:
        snippet = ""

    return {
        "source_path": source_path,
        "annotation_key": annotation_key,
        "annotation_value": annotation_value,
        "commit_ready": commit_ready,
        "snippet": snippet,
    }


# ---------------------------------------------------------------------------
# disabled_features / blast_radius (skills/catalog/ degradation posture;
# skills/catalog/references/resolution.md "Duplicate names and blast radius",
# FR-006 one-hop widening, kept-not-filtered dangling entries)
# ---------------------------------------------------------------------------


DEGRADED_FEATURES_BY_FIELD = {  # Service field -> the one feature its emptiness gates
    "dashboards": "pane_driving",
    "alert_matchers": "alert_resolution",
    "runbooks": "runbook_fetch",
    "depends_on": "blast_radius_widening",
}


def disabled_features(service):
    """The mechanical form of "each missing annotation degrades exactly its
    own feature" (skills/catalog/ degradation posture): derived PURELY from
    which of ``DEGRADED_FEATURES_BY_FIELD``'s four Service fields is empty on
    this one ``service``, nothing else. There are no cross-effects — a
    service missing only ``dashboards`` still briefs normally in every other
    respect, gaining exactly one disabled feature (``pane_driving``) and no
    more. A fully-annotated service — every field non-empty — returns an
    empty set.

    ``missing_owner`` is deliberately NOT a key in ``DEGRADED_FEATURES_BY_FIELD``,
    and never will be: it is a catalog-quality *warning* (see
    ``parse_entity``'s own ``missing_owner`` warning), not a disabled
    feature, because ownership disables no feature. Do not "fix" this
    function by adding it.

    A malformed ``catalog-info.yaml`` disables nothing globally: it
    contributes a ``Failure`` at ``load_catalog`` time and the service it
    would have defined is simply absent from ``catalog["services"]`` —
    every other file still parses, and every other service still briefs
    normally. This function only ever looks at one already-parsed
    ``service`` at a time; it has no notion of "globally" to begin with.

    Defensive about shape: a ``service`` that is not a ``dict`` (or is
    missing a field entirely) is treated as if every field on it were
    empty — never raises. Mirrors ``_as_dict``'s contract elsewhere in this
    module, which is why a fully-missing/``None`` service disables all four
    features rather than raising.
    """
    service = _as_dict(service)
    disabled = set()
    for field_name, feature_name in DEGRADED_FEATURES_BY_FIELD.items():
        if not service.get(field_name):
            disabled.add(feature_name)
    return disabled


def blast_radius(name, catalog):
    """The named service's own ``depends_on`` entries, sorted -> a widened
    affected-service list (resolution.md "Duplicate names and blast
    radius", FR-006).

    **One hop, v1 — stated outright.** This widens by the named service's
    OWN ``depends_on`` entries only; it never follows a dependency's own
    dependencies in turn. Deeper, multi-hop traversal is a recorded future
    option, not a promise this surface makes today — unbounded traversal
    would invite cycle-handling machinery a tier-0-scale catalog doesn't
    need.

    **Dangling entries are kept, never filtered.** An entry naming a
    service the catalog does not contain stays in the result exactly as
    written; it was already surfaced as a ``dangling_dependency`` warning at
    ``load_catalog`` time. On a messy catalog, a dependency on an
    uncatalogued service is the normal case, not an error to hide — silently
    shrinking a blast radius is worse than a wide one with a note attached.

    A ``name`` absent from the catalog, or present with an empty/missing
    ``depends_on``, yields ``[]`` — the assessment simply proceeds
    unwidened. Never raises for any catalog ``load_catalog`` returns — the
    ``_as_dict`` guard extends that to a malformed catalog too.
    """
    services = _as_dict(_as_dict(catalog).get("services"))
    service = services.get(name)
    if not isinstance(service, dict):
        return []
    return sorted(_as_list(service.get("depends_on")))
