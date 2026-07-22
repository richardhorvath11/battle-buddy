# Catalog Annotation Mapping Reference

Normative for the `catalog` skill (FR-002; design §6.1). Every value that reaches the
six-field consumer model arrives through exactly one of the rows in the table below — this
document is the mapping's source of truth, and the parsing rules a raw catalog entity must
pass through before it becomes that model.

## The consumer model

```
Service {name, owner, runbooks[], dashboards[], alert_matchers[], depends_on[]}
```

Six fields, no more. This is the **only** shape any consumer sees — raw catalog file
structure (entity `kind`, `metadata`, `spec`, annotation blocks) never crosses this boundary.
A consumer holding a `Service` never inspects where a field came from; it only ever sees the
six names above.

## The annotation mapping table (literal keys)

| Model field | Source | Notes |
|---|---|---|
| `name` | `metadata.name` | required — an entity without it is not a service |
| `owner` | `spec.owner` | minimal viable subset; absence is a catalog-quality warning, not a parse failure |
| `runbooks` | `oncall-harness/runbooks` | |
| `dashboards` | `grafana/dashboard-selector` | |
| `alert_matchers` | `oncall-harness/alert-match` | |
| `depends_on` | `spec.dependsOn` | |

## Empty-list defaults

Every list field (`runbooks`, `dashboards`, `alert_matchers`, `depends_on`) defaults to
`[]` when its source annotation is absent — never `null`, never omitted from the model.
Consumers branch on **emptiness**, never on presence: that uniformity is what makes
per-field degradation work the same way for every field, rather than requiring a
presence check before an emptiness check at every call site.

## Multi-valued parsing

A source annotation that is already a list parses to a list. A source annotation that is
a scalar string parses to a one-element list. **Commas inside a scalar are never split
on** — a comma is a legal character inside a matcher or a runbook identifier, and
splitting one on sight would make the annotation vocabulary ambiguous between "one value
containing a comma" and "several comma-separated values." `spec.dependsOn` follows the
same rule: a scalar there also parses to a one-element list.

## Entity classification

An entity is service-shaped iff `kind` ∈ {`Component`, `Service`} **and**
`metadata.name` is a non-empty string. Anything else — a `Documentation` entity, a
`Component` with no name, or any other `kind` — is skipped with a catalog-quality note.
It is never parsed into the model, and skipping it is never a failure: an entity that
isn't service-shaped simply isn't a service.

## Duplicate `metadata.name`

When more than one service-shaped entity shares the same `name`, the entity whose
repo-relative source path sorts **first lexicographically** is canonical; every other
entity sharing that name is dropped, and a catalog-quality warning names every source
path involved. Lexicographic path order is what makes "first" deterministic — it never
depends on directory-walk order, which is not itself stable across filesystems or catalog
sources. The fix-up path (defined in the resolution reference, not here) is
the correction vehicle when the wrong entity wins: a team retires or renames the losing
path, not this rule.

## Catalog-quality warnings

These are surfaced, never fatal, and never silently dropped — a catalog-quality problem
degrades a feature or a field, and the responder is told about it, but it never aborts a
session.

- **missing owner** — a service-shaped entity with no `spec.owner`. It parses fine, with
  an empty `owner`, *and* it is surfaced, because ownership is in the minimal viable
  subset: a service nobody owns must not parse clean and silent.
- **dangling dependency** — a `depends_on` entry naming a service the catalog does not
  contain. The entry is **kept**, not filtered out: on a messy catalog, a dependency on an
  uncatalogued service is the normal case, not an anomaly, and silently shrinking a blast
  radius on the assumption that an unknown name is invalid is worse than surfacing a wide
  one with a note attached.
- **ignored entity** — a non-service `kind`, per the entity-classification rule above.
- **duplicate name** — two entities declaring the same `metadata.name`, per the tie-break
  rule above.

The four warning kinds a consumer branches on are exactly `missing_owner`,
`dangling_dependency`, `ignored_entity`, and `duplicate_name`. A warning names the service
the *offending entity declared* — for a duplicate-group loser that is a name whose winning
entity came from a different file, so a warning's service name is not a key into the
resolved service set.

## What a parse yields

Reading a catalog repo produces the resolved services plus the quality signals gathered
along the way — five things, and a consumer can rely on all five being present even when
the catalog is a mess:

| Part | Contents |
|---|---|
| services | canonical name → the six-field `Service`, duplicates already resolved |
| linkage | canonical name → its linkage values (`paging_id`, `repo_slug`), an entry per service |
| sources | canonical name → the repo-relative path of the file the winning entity came from |
| warnings | the catalog-quality signals above, in the four kinds listed |
| failures | one entry per file that could not be parsed, naming the file and why |

**There is no error path.** A parse always yields all five; a malformed file, an
unreadable repo root, a non-service entity, a duplicate, and a missing owner each land in
`warnings` or `failures` rather than aborting anything.

## Linkage annotations

| Annotation key | Internal name | Purpose |
|---|---|---|
| `pagerduty.com/service-id` | `paging_id` | paging linkage |
| `github.com/project-slug` | `repo_slug` | repo linkage — scopes deploy-window reads |

The internal name is what a consumer indexes the per-service linkage map with; it is part
of this contract, not an implementation detail, so a rename is a documented change.

These are **metadata exposed beside the model, never fields of the six-field consumer
model**. That is the precise claim: the six fields in "The consumer model" above are
exhaustive of what `Service` carries, and neither linkage key is among them. It is not a
claim that consumers never receive these values — they are present on the catalog, and
the slices that need paging or repo scoping read them there, beside the model rather than
inside it.

## Runbook references

A runbook reference, once persisted to a session row, is `{url, commit}` — the runbook's
URL plus the commit SHA it was read at, present where the runbook is git-hosted and
absent otherwise. It is **a pointer with a version, never content**: the row records
where the runbook was and at what point in its history, not what the runbook said. The
session row's `runbook_refs` column is the destination for this pointer, and
`skills/session-store/` is its normative home — this document consumes that shape; it
does not restate it.

## Sourcing

File-mode Backstage is v1's only catalog source. API-mode is deferred. Every read this
document describes is one of **your code tool's file reads** against that file-mode
source — never a hardcoded server or tool name, and never a cached or session-persisted
copy of catalog content (FR-005, FR-007).
