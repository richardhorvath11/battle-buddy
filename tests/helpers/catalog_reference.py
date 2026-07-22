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
                "entity at {} has kind {!r} (not service-shaped per "
                "SERVICE_KINDS={!r}) or missing/empty metadata.name — "
                "ignored, never parsed into the model".format(
                    source_path, kind, sorted(SERVICE_KINDS)
                )
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

    Warnings ``parse_entity`` raises for every file — including those of a
    duplicate group's dropped losers — are carried into the catalog's
    ``warnings`` list unconditionally.
    """
    repo_root = Path(repo_root)
    warnings = []
    failures = []
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
