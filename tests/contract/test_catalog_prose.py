"""Prose gate for skills/catalog/ (FR-002/FR-003/FR-004/FR-005/FR-007/FR-009;
SC-005/SC-006).

This module is the prose-gate for the catalog skill: every hermetic assertion
``skills/catalog/**/*.md`` must satisfy lives here, discovered dynamically
(``rglob`` over the skill directory, never a hand-maintained file list).

T001 (Phase 1: Setup) creates this module as an empty skeleton with a single
non-vanishing guard — setup, not any user story, owns this file's *existence*,
so a scope cut dropping US3 or US4 (see tasks.md's "If scope must be cut")
can never orphan a later task that would otherwise have nowhere to land.
Later tasks extend this same module in place, never replace it:

- T016 (US4): the SC-006 storage-op scan — zero occurrences of the write ops
  (``append_record``, ``update_record``, ``put_file``, ``append_entry``)
  anywhere under ``skills/catalog/**/*.md`` — plus the freshness/runbook-format
  prose gates.
- T018 (Phase 6): the SC-005 naming scan (the ``mcp__`` hard fail, the
  deny-list scan extended locally with a ``github`` pattern, canonical-key
  masking) and the FR-007 gates (the literal "your code tool's file reads"
  phrase, the enumerated code-operation-token deny list, the manifest-fidelity
  backstop scoped to that token set).
- T019 (Phase 6): the prose<->encoding agreement test — the annotation table
  in ``references/annotations.md`` against
  ``tests/helpers/catalog_reference.py``'s ``CANONICAL_ANNOTATIONS`` /
  ``LINKAGE_ANNOTATIONS`` vocabularies, asserted both ways.
- T020 (Phase 6): the doctor-fixture ratchet — slice 4's
  ``tests/fixtures/doctor/catalog-valid.json`` annotation keys are asserted a
  (non-vacuous) subset of the canonical vocabulary.
- T022 (Phase 6): the FR-009 assertion that ``skills/catalog/`` ships no
  ``*.py`` file and that ``tests/helpers/catalog_reference.py`` is named by no
  glob in ``tests/fixtures/packaging/intended-bundle.json``'s shipped bundle.

T016 scope notes, recorded here rather than only in code comments because both
are deliberate choices a future author could otherwise mistake for bugs:

(a) ``read_records`` is deliberately **not** scanned by the SC-006 write-op
    scan below. Reading the session store back is not a catalog *write* —
    spec SC-006 names only the four write operations
    (``append_record``, ``update_record``, ``put_file``, ``append_entry``) —
    and a doc that legitimately cites where a runbook pointer is read back
    from must not be failed by a gate scoped to writes.

(b) The SC-006 scan below is **unconditional** — every ``*.md`` file, no
    exemption — where the spec text says "applied to catalog content." That
    is a deliberate widening. Scoping the scan to "the catalog-flow sections"
    would need a section boundary the prose does not carry, and any such
    boundary is gameable by moving a sentence past it. The accepted cost: the
    prose must state the never-copied rule without ever naming a write
    operation, which is exactly what ``SKILL.md``'s freshness section does
    ("never cached across sessions and never copied into any store").
"""

import fnmatch
import json
import re

import pytest

from conftest import REPO_ROOT
from helpers.catalog_reference import (
    CANONICAL_ANNOTATIONS,
    CATALOG_PARTS,
    LINKAGE_ANNOTATIONS,
    MODEL_FIELDS,
    WARNING_KINDS,
)
from test_skill_capability_naming import DENY_PATTERNS as _SLICE3_DENY_PATTERNS

SKILLS_DIR = REPO_ROOT / "skills" / "catalog"

MD_FILES = sorted(SKILLS_DIR.rglob("*.md"))
MD_IDS = [p.relative_to(SKILLS_DIR).as_posix() for p in MD_FILES]


# ---------------------------------------------------------------------------
# Non-vanishing guard (TA5-style, per test_skill_capability_naming.py's
# precedent): a broken glob or an emptied doc set must not turn every
# parametrized check the later tasks add into a silently-skipped, still-green
# no-op.
# ---------------------------------------------------------------------------


def test_scan_finds_the_known_catalog_docs():
    # T009: guard is now at its full target set — no remaining widener
    assert {"SKILL.md", "references/annotations.md", "references/resolution.md"} <= set(MD_IDS)


def _paragraphs(text):
    r"""Whitespace-normalized paragraphs — wrap-robust, boundary-respecting.

    Per paragraph, deliberately, never a global ``re.sub(r"\s+", " ", text)``
    over the whole corpus. A global collapse also erases blank lines and the
    inter-file join, so a phrase could be satisfied by words reassembled
    across a paragraph break — or across two different files — while neither
    doc actually says it. A review demonstrated both. Splitting on blank lines
    first keeps the hard-wrap robustness (the reason normalization exists at
    all) and closes the boundary-crossing vector: a phrase must live inside
    one paragraph of one file.
    """
    return [
        re.sub(r"\s+", " ", block).strip()
        for block in re.split(r"\n\s*\n", text)
        if block.strip()
    ]


def _states(phrase, paragraphs):
    """True when some single paragraph contains the phrase verbatim."""
    return any(phrase in paragraph for paragraph in paragraphs)


ALL_CATALOG_TEXT = "\n".join(p.read_text(encoding="utf-8") for p in MD_FILES)
ALL_CATALOG_PARAGRAPHS = [
    paragraph
    for doc in MD_FILES
    for paragraph in _paragraphs(doc.read_text(encoding="utf-8"))
]

SKILL_MD_TEXT = next(p.read_text(encoding="utf-8") for p in MD_FILES if p.name == "SKILL.md")
SKILL_MD_PARAGRAPHS = _paragraphs(SKILL_MD_TEXT)


def test_combined_catalog_prose_is_non_trivial():
    # T016 non-vanishing guard: an emptied doc set must not let the "X in
    # text" content gates below pass trivially by having nothing left to
    # contradict them.
    assert len(ALL_CATALOG_TEXT) > 2000, (
        "combined text of skills/catalog/**/*.md is only %d chars — too "
        "small to trust the content-presence gates below"
        % len(ALL_CATALOG_TEXT)
    )


# ---------------------------------------------------------------------------
# SC-006 — zero occurrences of the four storage/artifact/diary write
# operations anywhere under skills/catalog/**/*.md. Raw text, no
# fence-stripping exemption (unlike FR-010's deny-list scan in
# test_skill_capability_naming.py): a catalog doc has no legitimate reason to
# name a write op, worked example or not, so there is nothing to exempt.
# ---------------------------------------------------------------------------

WRITE_OPS = ("append_record", "update_record", "put_file", "append_entry")


@pytest.mark.parametrize("doc_path", MD_FILES, ids=MD_IDS)
def test_no_storage_write_operation_named(doc_path):
    text = doc_path.read_text(encoding="utf-8")
    # Case-insensitive: `Append_Record` is the same operation name, and a
    # scan that only catches the lowercase spelling is a scan with a
    # trivially-typed hole in it.
    lowered = text.lower()
    hits = sorted(op for op in WRITE_OPS if op in lowered)
    assert not hits, (
        "%s names storage/artifact/diary write operation(s) %r — SC-006 "
        "requires catalog content is never written to a store, and naming a "
        "write op in catalog prose is exactly the shape that rules out "
        "(read_records is deliberately exempt — see module docstring)"
        % (doc_path, hits)
    )


# ---------------------------------------------------------------------------
# US4 content gates (FR-005) — assert the prose actually *says* the things
# FR-005 requires, not just that it avoids naming a write op.
# ---------------------------------------------------------------------------


def test_freshness_statement_present():
    # Scanned against SKILL.md, not the whole corpus: US4's independent test
    # inspects *the skill's* documented flow, and T015 places the freshness
    # rule in SKILL.md specifically. A corpus-wide scan would stay green if
    # the statement were moved out of SKILL.md into a reference doc, which is
    # exactly the regression this gate exists to catch.
    assert _states("fresh at session start", SKILL_MD_PARAGRAPHS), (
        "FR-005: SKILL.md must state catalog data is read fresh at session "
        "start — literal phrase 'fresh at session start' not found in any "
        "single paragraph of SKILL.md"
    )
    assert _states("never cached across sessions", SKILL_MD_PARAGRAPHS), (
        "FR-005: SKILL.md must state catalog data is never cached across "
        "sessions — literal phrase not found in any single paragraph"
    )
    assert _states("never copied into any store", SKILL_MD_PARAGRAPHS), (
        "FR-005: SKILL.md must state catalog data is never copied into any "
        "store — literal phrase not found in any single paragraph"
    )


# Anchored to the literal clause in SKILL.md's "Runbook references are
# pointers, never content" section: "Runbook **content** - what the runbook
# actually says - is never persisted anywhere; only the pointer is."
#
# The clause, not a loose "never ... persist" regex. A review showed the loose
# form is satisfiable by an unrelated decoy sentence elsewhere in the doc while
# the real sentence is inverted to say content IS persisted — the gate would
# stay green on prose that states the opposite of FR-005.
NEVER_CONTENT_CLAUSE = "is never persisted anywhere; only the pointer is"


def test_runbook_pointer_format_stated_in_skill_md():
    assert _states("runbook_refs", SKILL_MD_PARAGRAPHS), (
        "FR-005: SKILL.md must name runbook_refs as the runbook-pointer "
        "destination — literal 'runbook_refs' not found in SKILL.md"
    )
    assert _states("commit SHA", SKILL_MD_PARAGRAPHS), (
        "FR-005: SKILL.md must mention the commit SHA a runbook pointer is "
        "read at — literal 'commit SHA' not found in SKILL.md"
    )
    assert _states(NEVER_CONTENT_CLAUSE, SKILL_MD_PARAGRAPHS), (
        "FR-005: SKILL.md must state that runbook content itself is never "
        "persisted, only the pointer — the clause %r was not found in any "
        "single paragraph of SKILL.md" % NEVER_CONTENT_CLAUSE
    )


def test_catalog_unreachable_path_named_in_skill_md():
    assert "catalog repo unreachable" in SKILL_MD_TEXT, (
        "FR-005: SKILL.md must name the catalog-repo-unreachable path "
        "literally — phrase 'catalog repo unreachable' not found in "
        "SKILL.md"
    )


UNREACHABLE_CLAIMS = [
    ("never blocks the session opening", "nothing blocks the session open"),
    ("lower rungs carry the session", "the fingerprint ladder carries the session"),
    ("surfaced in the briefing", "the gap is surfaced in the briefing"),
]
UNREACHABLE_IDS = [claim for claim, _ in UNREACHABLE_CLAIMS]


@pytest.mark.parametrize("phrase, rule", UNREACHABLE_CLAIMS, ids=UNREACHABLE_IDS)
def test_catalog_unreachable_path_states_its_three_claims(phrase, rule):
    # The name check above is satisfied by the heading alone: a review gutted
    # the subsection's entire body and the suite stayed green. spec.md's
    # catalog-unreachable edge case makes three claims, and each gets an
    # assertion here so the section cannot decay into a heading.
    assert _states(phrase, SKILL_MD_PARAGRAPHS), (
        "FR-005 / spec.md's catalog-unreachable edge case: SKILL.md must "
        "state that %s — expected phrase %r in some paragraph" % (rule, phrase)
    )


# ---------------------------------------------------------------------------
# T018 — SC-005 naming scan over skills/catalog/**/*.md.
#
# Mirrors test_skill_capability_naming.py's mechanism (FR-010) for this
# skill's own docs. That module's DENY_PATTERNS has no `github` pattern —
# slice 3 had no reason to name it — so it is imported here and extended
# locally with one. Without the extension, masking the literal key
# `github.com/project-slug` below would be a no-op (nothing in
# DENY_PATTERNS would ever have matched "github" in the first place), and
# the third leg of test_masking_exemption_is_not_vacuous would be checking
# nothing.
# ---------------------------------------------------------------------------

CATALOG_DENY_PATTERNS = dict(_SLICE3_DENY_PATTERNS)
CATALOG_DENY_PATTERNS["github"] = re.compile(r"github", re.IGNORECASE)

# Every canonical/linkage annotation key, sourced dynamically from
# catalog_reference (never hardcoded here) — the mask target for the scan
# below.
CANONICAL_ANNOTATION_KEYS = tuple(CANONICAL_ANNOTATIONS) + tuple(LINKAGE_ANNOTATIONS)


def _mask_canonical_annotation_keys(text):
    """Remove every canonical annotation key as a WHOLE string — never a
    bare vendor-name prefix — before the deny-list scan below.

    `grafana/dashboard-selector`, `pagerduty.com/service-id`,
    `github.com/project-slug` are this skill's own documented annotation
    keys (annotations.md's mapping table); masking the full key string lets
    that legitimate, documented use pass while the same vendor word written
    as a *product* name elsewhere in the doc — "grafana", "pagerduty",
    "github" on their own, outside one of these three exact strings — still
    fails. Masking a bare prefix instead (stripping "grafana" wherever it
    occurs, say) would also silently exempt that exact failure mode, which
    is precisely why the mask target is the whole key string and not its
    vendor-name prefix.
    """
    masked = text
    for key in CANONICAL_ANNOTATION_KEYS:
        masked = masked.replace(key, "")
    return masked


@pytest.mark.parametrize("doc_path", MD_FILES, ids=MD_IDS)
def test_no_concrete_mcp_tool_name_marker_in_catalog(doc_path):
    text = doc_path.read_text(encoding="utf-8")
    assert "mcp__" not in text, (
        "%s references a concrete MCP tool name (mcp__ marker) — SC-005 "
        "requires capability/operation names only, never a hardcoded MCP "
        "tool name; fenced or not, there is no legitimate use here" % doc_path
    )


@pytest.mark.parametrize("doc_path", MD_FILES, ids=MD_IDS)
def test_no_concrete_vendor_name_after_masking_canonical_keys(doc_path):
    text = doc_path.read_text(encoding="utf-8")
    masked = _mask_canonical_annotation_keys(text)
    hits = sorted(
        name for name, pattern in CATALOG_DENY_PATTERNS.items() if pattern.search(masked)
    )
    assert not hits, (
        "%s names concrete MCP server/vendor product(s) %r in normative "
        "prose after masking the documented annotation keys — SC-005 "
        "permits only capability/operation names and the three canonical "
        "vendor-prefixed annotation keys, never a vendor product name "
        "written as such" % (doc_path, hits)
    )


def test_masking_exemption_is_not_vacuous():
    """Two-halved positive control mirroring test_skill_capability_naming's
    test_fenced_datadog_example_is_the_documented_exemption: the masking
    exemption above must have something real to exempt (all three
    vendor-prefixed keys actually appear in catalog prose), and masking
    must actually remove every deny-list hit those keys would otherwise
    cause. A failure of the first half means the mask has become vacuous —
    there is nothing left in the prose for it to exempt.
    """
    for key in (
        "grafana/dashboard-selector",
        "pagerduty.com/service-id",
        "github.com/project-slug",
    ):
        assert key in ALL_CATALOG_TEXT, (
            "expected the canonical vendor-prefixed annotation key %r "
            "somewhere in skills/catalog/**/*.md prose, but it is absent — "
            "the masking exemption has nothing to mask, which makes SC-005's "
            "masked deny-list scan vacuous rather than a real exemption"
            % key
        )

    masked_corpus = "\n".join(
        _mask_canonical_annotation_keys(p.read_text(encoding="utf-8")) for p in MD_FILES
    )
    survivors = sorted(
        name
        for name in ("grafana", "pagerduty", "github")
        if CATALOG_DENY_PATTERNS[name].search(masked_corpus)
    )
    assert not survivors, (
        "%r survive masking the canonical annotation keys — the mask should "
        "remove exactly the documented key strings, leaving no bare vendor "
        "word behind" % survivors
    )


# ---------------------------------------------------------------------------
# FR-007 — sourcing is described generically ("your code tool's file
# reads"), never as a named code operation, and never a concrete server/tool
# name.
#
# Docstring note on FR-007's own rationale: slice 4's manifest
# (manifest/capabilities.json) went on to pin the optional `code`
# capability's op shapes (`read_file`, `list_commits`, `search`) — so
# FR-007's stated rationale ("operation contract v1,
# tools/bb-mock-mcp/contract.json, defines no code operations") is now
# stale; contract.json's capabilities still have no `code` half at all.
# What FR-007 *normatively requires* — catalog prose never cites a
# code-operation name, a generic reference only — is unaffected by that
# staleness, and is exactly what the gates below enforce.
# ---------------------------------------------------------------------------

FR_007_PHRASE = "your code tool's file reads"

# The three code-capability operation names, enumerated explicitly rather
# than derived from a suffix heuristic: test_skill_capability_naming.py's
# `_looks_like_op` suffix check (`_record`/`_records`/`_file`/`_entry`) would
# only ever catch `read_file` here — `list_commits` and `search` need to be
# named outright.
CODE_OP_TOKENS = ("read_file", "list_commits", "search")

# `search` needs a stricter boundary than `\b`. Two strings contain it
# without citing the operation: "research" (ordinary English) and
# "search-api" (a real fixture service name — exactly what a worked example
# in resolution.md would reach for). `\b` handles the first but NOT the
# second: a word boundary sits between "h" and "-", so `\bsearch\b` matches
# inside "search-api" and the gate would fail an innocent doc. A review
# demonstrated it. The lookarounds below exclude a hyphen on either side as
# well as word characters, so only a standalone `search` — the operation
# name — trips the gate.
# `read_file`/`list_commits` have no such collision risk and are checked
# with plain substring containment.
_SEARCH_WORD_RE = re.compile(r"(?<![\w-])search(?![\w-])")

MANIFEST_PATH = REPO_ROOT / "manifest" / "capabilities.json"


def _code_op_token_hits(text):
    hits = []
    if "read_file" in text:
        hits.append("read_file")
    if "list_commits" in text:
        hits.append("list_commits")
    if _SEARCH_WORD_RE.search(text):
        hits.append("search")
    return hits


def _load_manifest_code_ops():
    with open(str(MANIFEST_PATH), encoding="utf-8") as f:
        manifest = json.load(f)
    return set(manifest["optional"]["code"]["ops"].keys())


MANIFEST_CODE_OPS = _load_manifest_code_ops()


def test_fr007_sourcing_phrase_is_present():
    assert _states(FR_007_PHRASE, ALL_CATALOG_PARAGRAPHS), (
        "FR-007: catalog prose must describe its sourcing generically as "
        "%r — literal phrase not found in any single paragraph of "
        "skills/catalog/**/*.md" % FR_007_PHRASE
    )


def test_fr007_no_code_operation_name_cited():
    hits = _code_op_token_hits(ALL_CATALOG_TEXT)
    assert not hits, (
        "catalog prose cites code-operation name(s) %r — FR-007 requires a "
        "generic reference to code-tool file reads, never a named "
        "operation" % hits
    )


def test_manifest_declares_the_three_code_op_tokens():
    # Standalone manifest-fidelity pin: the three code-op tokens the
    # FR-007 gate forbids in prose are exactly the three the manifest declares: it needs real ops
    # to check against, or it would be vacuously true no matter what the
    # prose cited.
    assert set(CODE_OP_TOKENS) <= MANIFEST_CODE_OPS, (
        "expected manifest/capabilities.json's optional.code.ops to declare "
        "all three of %r; got %r" % (CODE_OP_TOKENS, sorted(MANIFEST_CODE_OPS))
    )


# ---------------------------------------------------------------------------
# T019 — prose<->encoding agreement: annotations.md's tables against
# catalog_reference's CANONICAL_ANNOTATIONS / LINKAGE_ANNOTATIONS, both
# ways. Mirrors slice 3's fingerprint.md<->bb-fingerprint relationship: a
# doc whose table silently diverges from the encoding must fail here.
# ---------------------------------------------------------------------------

ANNOTATIONS_DOC_PATH = SKILLS_DIR / "references" / "annotations.md"
ANNOTATIONS_DOC_TEXT = ANNOTATIONS_DOC_PATH.read_text(encoding="utf-8")

_TABLE_SEPARATOR_RE = re.compile(r"^:?-+:?$")
_CODE_CELL_RE = re.compile(r"`([^`]+)`")


def _markdown_section(heading, text):
    """The body text between a '## <heading>' line and the next '## '
    heading (or end of document) — scopes table parsing to one table at a
    time so annotations.md's canonical mapping table and its linkage table
    are never conflated.
    """
    pattern = re.compile(
        r"^##\s+" + re.escape(heading) + r"\s*\n(.*?)(?=\n##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    assert match is not None, "expected a '## %s' section in %s" % (
        heading,
        ANNOTATIONS_DOC_PATH,
    )
    return match.group(1)


def _table_rows(section_text):
    """Every markdown table row in section_text as a list of raw cell
    strings — header and '---' separator rows excluded mechanically (by
    content, never by skipping a fixed line count, which would break the
    moment a row is inserted above the table)."""
    rows = []
    for line in section_text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(_TABLE_SEPARATOR_RE.match(c) for c in cells):
            continue
        rows.append(cells)
    return rows


def _parse_canonical_mapping_table(section_text):
    """Only collects cells that LOOK LIKE annotation keys — i.e. contain a
    '/'. The canonical table also carries `metadata.name` / `spec.owner` /
    `spec.dependsOn` rows in its 'Source' column; those are catalog paths,
    not annotation keys, and have no '/' in them, so this filter skips them
    mechanically rather than by row position or a hardcoded skip-list.
    """
    keys = set()
    for cells in _table_rows(section_text):
        if len(cells) < 2:
            continue
        match = _CODE_CELL_RE.search(cells[1])
        if match and "/" in match.group(1):
            keys.add(match.group(1))
    return keys


def _parse_canonical_field_map(section_text):
    """annotation key -> Model field, for every canonical-table row whose
    Source cell looks like an annotation key.

    The key-set agreement alone leaves the doc's own key->field CLAIM
    unchecked: a review showed the table could say `oncall-harness/runbooks`
    populates `dashboards`, or name a field (`alertMatchers`) that does not
    exist in the model at all, and stay green. The linkage table already
    compares full dicts for exactly this reason; this brings the canonical
    table to the same standard.
    """
    pairs = {}
    for cells in _table_rows(section_text):
        if len(cells) < 2:
            continue
        field_match = _CODE_CELL_RE.search(cells[0])
        key_match = _CODE_CELL_RE.search(cells[1])
        if field_match and key_match and "/" in key_match.group(1):
            pairs[key_match.group(1)] = field_match.group(1)
    return pairs


def _parse_linkage_table(section_text):
    """annotation key -> Internal name, for every linkage-table row whose
    first cell looks like an annotation key (contains '/')."""
    pairs = {}
    for cells in _table_rows(section_text):
        if len(cells) < 2:
            continue
        key_match = _CODE_CELL_RE.search(cells[0])
        name_match = _CODE_CELL_RE.search(cells[1])
        if key_match and "/" in key_match.group(1) and name_match:
            pairs[key_match.group(1)] = name_match.group(1)
    return pairs


def test_annotations_doc_canonical_table_matches_encoding_both_ways():
    section = _markdown_section(
        "The annotation mapping table (literal keys)", ANNOTATIONS_DOC_TEXT
    )
    doc_keys = _parse_canonical_mapping_table(section)

    # Non-vanishing guard: a parser matching nothing must fail loudly here,
    # not pass vacuously via the subset assertions below.
    assert doc_keys, (
        "parsed zero annotation keys out of annotations.md's canonical "
        "mapping table — a broken table parser would otherwise make the "
        "agreement assertions below vacuously true"
    )

    encoded_keys = set(CANONICAL_ANNOTATIONS)
    assert doc_keys <= encoded_keys, (
        "annotations.md's canonical mapping table documents annotation "
        "key(s) %r that catalog_reference.CANONICAL_ANNOTATIONS does not "
        "encode" % sorted(doc_keys - encoded_keys)
    )
    assert encoded_keys <= doc_keys, (
        "catalog_reference.CANONICAL_ANNOTATIONS encodes annotation key(s) "
        "%r that annotations.md's canonical mapping table does not "
        "document" % sorted(encoded_keys - doc_keys)
    )

    # Model-field column, asserted both ways too — the key-set agreement
    # above stays green through a swapped or invented field name, which is a
    # prose-vs-encoding divergence that ships wrong guidance to a reader.
    doc_field_map = _parse_canonical_field_map(section)
    assert doc_field_map == CANONICAL_ANNOTATIONS, (
        "annotations.md's canonical mapping table's Model-field column "
        "disagrees with catalog_reference.CANONICAL_ANNOTATIONS: doc maps "
        "%r, encoding maps %r" % (doc_field_map, CANONICAL_ANNOTATIONS)
    )
    assert set(doc_field_map.values()) <= set(MODEL_FIELDS), (
        "annotations.md names model field(s) %r that are not in the "
        "six-field Service model" % sorted(set(doc_field_map.values()) - set(MODEL_FIELDS))
    )


def test_annotations_doc_linkage_table_matches_encoding_both_ways():
    section = _markdown_section("Linkage annotations", ANNOTATIONS_DOC_TEXT)
    doc_pairs = _parse_linkage_table(section)

    assert doc_pairs, (
        "parsed zero rows out of annotations.md's Linkage annotations table "
        "— a broken table parser would otherwise make the agreement "
        "assertions below vacuously true"
    )

    doc_keys = set(doc_pairs)
    encoded_keys = set(LINKAGE_ANNOTATIONS)
    assert doc_keys <= encoded_keys, (
        "annotations.md's Linkage annotations table documents key(s) %r "
        "that catalog_reference.LINKAGE_ANNOTATIONS does not encode"
        % sorted(doc_keys - encoded_keys)
    )
    assert encoded_keys <= doc_keys, (
        "catalog_reference.LINKAGE_ANNOTATIONS encodes key(s) %r that "
        "annotations.md's Linkage annotations table does not document"
        % sorted(encoded_keys - doc_keys)
    )

    # Internal name column, asserted both ways too: the key-set agreement
    # above would stay green through a silent rename of paging_id/repo_slug
    # in either the doc or the encoding. Comparing the full key->name dicts
    # (both sides already proven to share the same key set, above) catches
    # that rename in either direction.
    assert doc_pairs == LINKAGE_ANNOTATIONS, (
        "annotations.md's Linkage annotations table's Internal name column "
        "disagrees with catalog_reference.LINKAGE_ANNOTATIONS even though "
        "the key sets agree: doc maps %r, encoding maps %r"
        % (doc_pairs, LINKAGE_ANNOTATIONS)
    )


# ---------------------------------------------------------------------------
# T020 — doctor-fixture ratchet: slice 4's
# tests/fixtures/doctor/catalog-valid.json annotation keys are a
# (non-vacuous) subset of the canonical vocabulary. `/doctor`'s own catalog
# check only asserts the file parses (test_doctor_checks.py,
# test_doctor_report.py) — no test there reads its annotation keys — so
# this is the only gate pinning that the fixture actually uses real catalog
# annotation keys, not the pre-slice-7 placeholders it originally shipped
# with.
# ---------------------------------------------------------------------------

DOCTOR_CATALOG_VALID_PATH = REPO_ROOT / "tests" / "fixtures" / "doctor" / "catalog-valid.json"


def _doctor_catalog_fixture_annotation_keys():
    with open(str(DOCTOR_CATALOG_VALID_PATH), encoding="utf-8") as f:
        document = json.load(f)
    annotations = document.get("metadata", {}).get("annotations", {})
    return set(annotations)


def test_doctor_catalog_fixture_keys_are_a_nonvacuous_canonical_subset():
    keys = _doctor_catalog_fixture_annotation_keys()

    # Non-vanishing guard: a bare subset assertion passes on the empty set,
    # which is exactly how a wrong key-path extractor (or a since-emptied
    # fixture) would silently neuter this ratchet.
    assert keys, (
        "extracted zero annotation keys from %s — a broken key-path "
        "extractor would make the subset assertion below vacuously true"
        % DOCTOR_CATALOG_VALID_PATH
    )
    assert {"oncall-harness/alert-match", "grafana/dashboard-selector"} <= keys, (
        "expected tests/fixtures/doctor/catalog-valid.json to carry both "
        "retagged keys 'oncall-harness/alert-match' and "
        "'grafana/dashboard-selector'; got %r" % sorted(keys)
    )

    canonical_vocabulary = set(CANONICAL_ANNOTATIONS) | set(LINKAGE_ANNOTATIONS)
    assert keys <= canonical_vocabulary, (
        "tests/fixtures/doctor/catalog-valid.json annotation key(s) %r are "
        "outside the canonical vocabulary (CANONICAL_ANNOTATIONS union "
        "LINKAGE_ANNOTATIONS)" % sorted(keys - canonical_vocabulary)
    )


# ---------------------------------------------------------------------------
# T022 / FR-009 — "This slice ships skill prose and tests only — no parsing
# library, no shipped integration code."
#
# Asserted directly rather than inferred. `tests/unit/test_stdlib_boundary.py`
# walks `hooks/` and `bin/` only, so it passes vacuously for a slice that adds
# no shipped Python; and `tests/unit/test_packaging.py` lints the declared
# bundle's glob *strings* without ever expanding one against the filesystem.
# Neither would notice a `.py` file appearing under `skills/catalog/`, and an
# end-of-slice eyeball is not a test — so SC-001's "every FR maps to at least
# one test" needs this to hold without an exception.
# ---------------------------------------------------------------------------

INTENDED_BUNDLE_PATH = REPO_ROOT / "tests" / "fixtures" / "packaging" / "intended-bundle.json"
REFERENCE_ENCODING_RELPATH = "tests/helpers/catalog_reference.py"


def test_catalog_skill_ships_no_python():
    stray = sorted(p.relative_to(REPO_ROOT).as_posix() for p in SKILLS_DIR.rglob("*.py"))
    assert not stray, (
        "FR-009: skills/catalog/ ships prose only — no parsing library, no "
        "catalog-adapter code. Found Python source(s): %r" % stray
    )


def test_reference_encoding_is_named_by_no_bundle_glob():
    with open(str(INTENDED_BUNDLE_PATH), encoding="utf-8") as handle:
        bundle = json.load(handle)["bundle"]

    # Non-vanishing guard: an emptied bundle would make the check below
    # vacuously true, and the bundle is a fixture someone could edit.
    assert bundle, "intended-bundle.json declares an empty bundle"

    # fnmatch rather than a prefix test: the point is that no DECLARED glob
    # would pull the dev-only reference encoding into the shipped plugin.
    matching = sorted(
        glob for glob in bundle if fnmatch.fnmatch(REFERENCE_ENCODING_RELPATH, glob)
    )
    assert not matching, (
        "FR-009: the reference encoding is dev-only tooling (D-1 exemption, "
        "same standing as bb-mock-mcp) and must never be named for shipping; "
        "bundle glob(s) %r match %s" % (matching, REFERENCE_ENCODING_RELPATH)
    )


# ---------------------------------------------------------------------------
# T017's own deliverables — Overview, References routing table, Non-goals.
#
# A review gutted each of those three sections in turn, keeping only their
# headings, and the suite stayed green; it also added a seventh field to the
# Service line, contradicting both annotations.md and MODEL_FIELDS, with
# nothing firing. The catalog-unreachable section was hardened after exactly
# this failure — these are the same shape.
# ---------------------------------------------------------------------------


MODEL_LINE_DOCS = [p for p in MD_FILES if "Service {" in p.read_text(encoding="utf-8")]
MODEL_LINE_IDS = [p.relative_to(SKILLS_DIR).as_posix() for p in MODEL_LINE_DOCS]


@pytest.mark.parametrize("doc_path", MODEL_LINE_DOCS, ids=MODEL_LINE_IDS)
def test_every_doc_stating_the_model_states_it_identically(doc_path):
    # The six-field block appears in SKILL.md's Overview AND annotations.md's
    # "The consumer model" — near-verbatim, with no gate keeping them in sync.
    # Only SKILL.md's copy was pinned; the ungated copy lived in the doc that
    # calls itself the mapping's source of truth.
    listed = ", ".join(
        field + "[]" if field not in ("name", "owner") else field
        for field in MODEL_FIELDS
    )
    expected = "Service {%s}" % listed
    assert _states(expected, _paragraphs(doc_path.read_text(encoding="utf-8"))), (
        "%s states the Service model, so it must state it exactly as %r — two "
        "copies of a normative shape with only one gated is how they drift"
        % (doc_path, expected)
    )


def test_at_least_two_docs_state_the_model():
    # Non-vanishing guard: if the discovery above ever matches nothing, the
    # parametrized gate silently disappears.
    assert len(MODEL_LINE_DOCS) >= 2, (
        "expected the Service model block in at least SKILL.md and "
        "annotations.md; found %r" % MODEL_LINE_IDS
    )


def test_skill_md_states_the_six_field_model_exactly():
    listed = ", ".join(
        field + "[]" if field != "name" and field != "owner" else field
        for field in MODEL_FIELDS
    )
    expected = "Service {%s}" % listed
    assert _states(expected, SKILL_MD_PARAGRAPHS), (
        "FR-001: SKILL.md's Overview must state the six-field model exactly "
        "as %r — the model line is the Overview's core claim, and a seventh "
        "field appearing here would contradict annotations.md and "
        "MODEL_FIELDS with nothing else to catch it" % expected
    )


def test_skill_md_routes_to_both_references():
    for reference in ("references/annotations.md", "references/resolution.md"):
        assert reference in SKILL_MD_TEXT, (
            "SKILL.md's References table must route to %r — the routing "
            "table is how a reader reaches the normative statements this "
            "document deliberately does not restate" % reference
        )


def test_skill_md_states_its_non_goals():
    for phrase, rule in (
        ("API-mode", "API-mode Backstage is deferred"),
        ("never writes to the catalog", "the harness never writes to the catalog"),
    ):
        assert _states(phrase, SKILL_MD_PARAGRAPHS), (
            "SKILL.md's Non-goals must state that %s — expected %r" % (rule, phrase)
        )


# ---------------------------------------------------------------------------
# L3 — resolution.md's normative body had NO positive gate: every rule in it
# (match order, exactness-beats-substring, never-a-silent-pick, candidate
# ordering, the miss path, the fix-up offer, the one-hop bound) could be
# deleted and the suite stayed green. SKILL.md and annotations.md were each
# hardened after exactly this finding; resolution.md — the doc carrying US1's
# entire normative content — was not.
# ---------------------------------------------------------------------------

RESOLUTION_MD_TEXT = next(
    p.read_text(encoding="utf-8") for p in MD_FILES if p.name == "resolution.md"
)
RESOLUTION_MD_PARAGRAPHS = _paragraphs(RESOLUTION_MD_TEXT)

RESOLUTION_CLAIMS = [
    ("is not an exact-stage input", "the service name is a substring-stage input only"),
    ("An empty matcher never matches", "an empty matcher never matches"),
    ("is not commit-ready", "an offer with an empty value is not commit-ready"),
    ("read-only by default", "the never-writes boundary rests on read-only credentials"),
    ("never the reverse", "the substring direction is pinned"),
    ("never a silent pick", "ambiguity surfaces candidates rather than picking"),
    ("ordered by source path", "candidate order is deterministic"),
    ("one hop", "blast-radius widening is one hop in v1"),
    ("catalog_resolved", "a miss carries the resolution flag onto the session record"),
    ("No agent ever writes to the catalog", "the responder commits the fix-up, not an agent"),
]
RESOLUTION_IDS = [claim for claim, _ in RESOLUTION_CLAIMS]


@pytest.mark.parametrize("phrase, rule", RESOLUTION_CLAIMS, ids=RESOLUTION_IDS)
def test_resolution_md_states_its_normative_rules(phrase, rule):
    assert _states(phrase, RESOLUTION_MD_PARAGRAPHS), (
        "references/resolution.md must state that %s — expected %r in some "
        "paragraph. This doc carries US1's normative content; without these "
        "gates its whole body is deletable with a green suite." % (rule, phrase)
    )


DEGRADATION_ROWS = ["pane driving", "runbook fetch", "blast-radius widening"]


@pytest.mark.parametrize("feature", DEGRADATION_ROWS, ids=DEGRADATION_ROWS)
def test_skill_md_degradation_table_names_each_disabled_feature(feature):
    # FR-004's core prose. The encoding's disabled_features map is gated in
    # test_catalog_degradation.py; this pins that the shipped table a reader
    # actually follows names the same features.
    assert _states(feature, SKILL_MD_PARAGRAPHS), (
        "SKILL.md's degradation table must name %r as a disabled feature "
        "(FR-004)" % feature
    )


# ---------------------------------------------------------------------------
# L5 — FR-002 names `metadata.name`, `spec.owner` and `spec.dependsOn`
# literally as MUST-document mappings, but both table parsers filter to cells
# containing "/", which discards exactly those three rows. The doc could say
# `name` comes from `metadata.title`, or drop the depends_on row, and stay
# green while parse_entity reads the real paths.
# ---------------------------------------------------------------------------

SPEC_PATH_ROWS = {
    "name": "metadata.name",
    "owner": "spec.owner",
    "depends_on": "spec.dependsOn",
}


def _parse_spec_path_rows(section_text):
    """The canonical table's NON-annotation rows: model field -> catalog path."""
    pairs = {}
    for cells in _table_rows(section_text):
        if len(cells) < 2:
            continue
        field_match = _CODE_CELL_RE.search(cells[0])
        source_match = _CODE_CELL_RE.search(cells[1])
        if field_match and source_match and "/" not in source_match.group(1):
            pairs[field_match.group(1)] = source_match.group(1)
    return pairs


def test_annotations_doc_documents_the_three_spec_path_mappings():
    section = _markdown_section(
        "The annotation mapping table (literal keys)", ANNOTATIONS_DOC_TEXT
    )
    assert _parse_spec_path_rows(section) == SPEC_PATH_ROWS, (
        "FR-002 names metadata.name, spec.owner and spec.dependsOn literally "
        "as documented mappings; annotations.md's table must carry exactly "
        "those three non-annotation rows — got %r"
        % _parse_spec_path_rows(section)
    )


# ---------------------------------------------------------------------------
# W4 — Constitution VII's mechanical arm is per-skill-directory: slice 3 scans
# skills/session-store, this module scans skills/catalog. Nothing asserts the
# union covers every skill, so slice 8's diary skill could land unscanned and
# be silently exempt from the mcp__/vendor-name gate. Slice 7 is where the
# fork became a pattern, so the coverage guard lands here.
# ---------------------------------------------------------------------------

# Extended for skills/investigation/ ahead of slice 6's impl reaching main:
# that skill IS covered by a naming scan (test_investigation_prose.py scans
# skills/investigation/**/*.md plus agents/*.md), so listing it here is
# truthful, not a rubber stamp. This guard fired on a trial merge of slices
# 5-7 together, which is exactly what it exists for — a skill arriving
# without a scan must not land quietly.
SCANNED_SKILL_DIRS = {"session-store", "catalog", "investigation"}


def test_every_skill_directory_is_covered_by_a_naming_scan():
    present = {
        child.name
        for child in (REPO_ROOT / "skills").iterdir()
        if child.is_dir() and not child.name.startswith(".")
    }
    assert present, "no skill directories found — the guard below would be vacuous"
    # SUBSET, not equality: the safety property is "no skill exists without a
    # scan", and that is one-directional. A name listed here whose directory
    # has not landed yet is fine — this branch lists `investigation` ahead of
    # slice 6's skill reaching main, so the guard stays green both before and
    # after that merge rather than going red in between.
    unscanned = sorted(present - SCANNED_SKILL_DIRS)
    assert not unscanned, (
        "every skills/<name>/ directory must be covered by a capability-naming "
        "scan (Constitution VII's only mechanical enforcement). Unscanned: %r. "
        "Add a scan for it and list it in SCANNED_SKILL_DIRS — a skill added "
        "without one is silently exempt from the mcp__ and vendor-name gates."
        % unscanned
    )


# ---------------------------------------------------------------------------
# Converge round 1 hardened resolution.md's pre-existing body, then added new
# normative prose to annotations.md with no gate — the same defect, freshly
# committed. These gate that prose against the encoding's own identifiers.
# ---------------------------------------------------------------------------

WARNING_KIND_IDS = sorted(WARNING_KINDS)


@pytest.mark.parametrize("kind", WARNING_KIND_IDS, ids=WARNING_KIND_IDS)
def test_annotations_doc_names_every_warning_kind_identifier(kind):
    assert kind in ANNOTATIONS_DOC_TEXT, (
        "annotations.md must name the warning-kind identifier %r — a "
        "consuming slice branches on these strings, and the doc is where "
        "they are published" % kind
    )


def test_annotations_doc_declares_the_warning_vocabulary_closed():
    # The identifiers are only useful to a consumer if the set is closed;
    # an open set means coding for kinds that may never arrive.
    assert _states("The four warning kinds", _paragraphs(ANNOTATIONS_DOC_TEXT)), (
        "annotations.md must state the warning vocabulary is exactly four "
        "kinds, not an open set"
    )


def test_annotations_doc_documents_exactly_the_catalog_parts():
    # Parses the table rather than testing `part in section`: "services",
    # "warnings" and "failures" all appear in that section's surrounding
    # prose, so a substring check passed with three of the five rows deleted
    # — and passed with the table header destroyed entirely.
    section = _markdown_section("What a parse yields", ANNOTATIONS_DOC_TEXT)
    rows = [cells[0] for cells in _table_rows(section) if cells and cells[0]]
    # The header is asserted, not skipped: a review destroyed the table
    # structurally and the old substring check stayed green.
    assert rows[:1] == ["Part"], (
        "expected a `| Part | Contents |` table in 'What a parse yields'; "
        "got first row %r — the table's structure is part of the contract"
        % rows[:1]
    )
    documented = rows[1:]
    assert documented == list(CATALOG_PARTS), (
        "annotations.md's 'What a parse yields' table must document exactly "
        "the catalog's parts, in order, one row each — got %r, encoding "
        "declares %r" % (documented, list(CATALOG_PARTS))
    )


def test_annotations_doc_names_no_snake_case_identifier_the_encoding_lacks():
    # The reverse direction, done TOTALLY rather than by suffix family. An
    # earlier version only noticed invented kinds that reused one of the four
    # real kinds' suffixes, so `orphan_service` — the likelier shape for an
    # invented kind, a new noun — sailed through while its comment claimed the
    # direction was closed.
    #
    # Every snake_case identifier the doc quotes must be one the encoding
    # actually has: a warning kind, a model field, a catalog part, or a
    # linkage internal name. Anything else is the doc publishing a contract
    # the encoding will never honor.
    known = (
        set(WARNING_KINDS)
        | set(MODEL_FIELDS)
        | set(CATALOG_PARTS)
        | set(LINKAGE_ANNOTATIONS.values())
        | {"catalog_resolved", "runbook_refs"}  # slice-3 fields this doc cites
    )
    quoted = set(re.findall(r"`([a-z][a-z0-9]*(?:_[a-z0-9]+)+)`", ANNOTATIONS_DOC_TEXT))
    unknown = sorted(quoted - known)
    assert not unknown, (
        "annotations.md quotes snake_case identifier(s) %r that the encoding "
        "does not define — a consumer would branch on a name that never "
        "arrives. Known: warning kinds, model fields, catalog parts, linkage "
        "internal names, and the two slice-3 fields this doc cites." % unknown
    )

def test_annotations_doc_states_there_is_no_error_path():
    section = _markdown_section("What a parse yields", ANNOTATIONS_DOC_TEXT)
    assert "no error path" in section, (
        "the never-errors property is the whole point of the five-part shape; "
        "annotations.md must say it outright"
    )
