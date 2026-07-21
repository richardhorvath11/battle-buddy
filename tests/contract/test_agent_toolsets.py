"""SC-006 / FR-006 / research R7: every agent definition's ``## Toolset``
table is mechanically cross-checked against the capability manifest
(``manifest/capabilities.json``) — the declared-capability authority, loaded
dynamically and never hardcoded, so a doc citing a capability or operation
the manifest doesn't declare fails here rather than against a maintained
allow-list that can drift.

Parser: for each ``agents/*.md`` file (sorted glob), find the ``## Toolset``
section and parse its markdown table rows into ``(capability, operations,
access)`` tuples. The Capability cell may carry a single backticked token
(e.g. `` `alerting` ``) — the bare token is extracted. The Operations cell is
a comma-separated list of (optionally backticked) operation tokens.

This is the *initial* module (T011, triage only). Later tasks in this slice
extend it in place (tasks.md's serialization note: T011 -> T014 -> T018):
T014 adds the deep-investigator's mutating/approval-gated assertions, T018
the three specialists' read-only/single-purpose-adjacent assertions. Both
reuse the module-level ``parse_toolset``/``_load_manifest`` helpers below and
the ``AGENT_DOCS``/``TOOLSET_BY_DOC`` module-level fixtures rather than
re-parsing — the glob already covers new agent docs as they land, no list to
maintain.

``_section`` below is restated (not imported) from
``test_investigation_prose``: that module's helper is underscore-prefixed in
its home module — a private helper, not a name meant for cross-module reuse
(the same convention ``test_command_capability_naming`` follows for
``_strip_fenced_blocks``) — so this module carries its own copy rather than
reaching across a test-module boundary for it.
"""

import json
import re

import pytest

from conftest import REPO_ROOT

AGENTS_DIR = REPO_ROOT / "agents"
MANIFEST_PATH = REPO_ROOT / "manifest" / "capabilities.json"

AGENT_DOCS = sorted(AGENTS_DIR.glob("*.md"))
AGENT_DOC_IDS = [p.relative_to(REPO_ROOT).as_posix() for p in AGENT_DOCS]

TRIAGE_DOC = AGENTS_DIR / "triage.md"

_BACKTICK_WRAPPED_RE = re.compile(r"^`([^`]+)`$")


# ---------------------------------------------------------------------------
# Parsing helpers (module level — reused by later tasks' extensions)
# ---------------------------------------------------------------------------


def _section(text, heading):
    """Body of the ``## <heading>`` section: every line between that heading
    and the next ``## `` heading (or end of document). Returns ``None`` when
    the heading is absent.
    """
    lines = text.splitlines()
    target = "## %s" % heading
    start = None
    for i, line in enumerate(lines):
        if line.strip() == target:
            start = i + 1
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return "\n".join(lines[start:end])


def _bare_token(cell):
    """Strip one pair of surrounding backticks from a table-cell token, if
    present. A capability cell like `` `alerting` `` yields ``alerting``; an
    already-bare cell is returned unchanged.
    """
    cell = cell.strip()
    match = _BACKTICK_WRAPPED_RE.match(cell)
    return match.group(1) if match else cell


def _parse_operations_cell(cell):
    """Comma-separated (optionally backticked) operation tokens, e.g.
    "``get_alert``, ``list_alert_history``" -> ``("get_alert",
    "list_alert_history")``. Blank/empty parts are dropped.
    """
    parts = [p.strip() for p in cell.split(",")]
    return tuple(_bare_token(p) for p in parts if p)


def _table_rows(section_text):
    """Yield each data row of a markdown table (skipping the header row and
    the ``|---|---|---|`` separator row) as a tuple of stripped cell strings.
    """
    for line in section_text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells:
            continue
        if all(re.fullmatch(r"-+", c) for c in cells):
            continue  # separator row
        if cells == ["Capability", "Operations", "Access"]:
            continue  # header row
        yield tuple(cells)


def parse_toolset(doc_text):
    """Parse the ``## Toolset`` section of an agent doc's full text into a
    list of ``(capability, operations, access)`` tuples — ``capability`` a
    bare token, ``operations`` a tuple of bare tokens, ``access`` the raw
    cell string (e.g. ``"read-only"``, ``"approval-gated"``). Returns ``[]``
    when the section is absent or has no data rows.
    """
    section = _section(doc_text, "Toolset")
    if section is None:
        return []
    rows = []
    for cells in _table_rows(section):
        if len(cells) != 3:
            continue
        capability_cell, operations_cell, access_cell = cells
        rows.append(
            (
                _bare_token(capability_cell),
                _parse_operations_cell(operations_cell),
                access_cell.strip(),
            )
        )
    return rows


def _load_manifest():
    with open(str(MANIFEST_PATH), encoding="utf-8") as f:
        return json.load(f)


def _declared_capabilities(manifest):
    return set(manifest["required"]) | set(manifest["optional"])


def _declared_ops(manifest, capability):
    if capability in manifest["required"]:
        return set(manifest["required"][capability]["ops"])
    if capability in manifest["optional"]:
        return set(manifest["optional"][capability]["ops"])
    return set()


TOOLSET_BY_DOC = {p: parse_toolset(p.read_text(encoding="utf-8")) for p in AGENT_DOCS}


# ---------------------------------------------------------------------------
# Non-vanishing guards
# ---------------------------------------------------------------------------


def test_agents_glob_finds_at_least_one_file():
    assert AGENT_DOCS, "agents/*.md glob found no files — parser has nothing to check"


def test_triage_doc_is_among_the_parsed_files():
    assert TRIAGE_DOC in AGENT_DOCS, (
        "agents/triage.md is not among the agents/*.md glob results %r" % AGENT_DOCS
    )


@pytest.mark.parametrize("doc_path", AGENT_DOCS, ids=AGENT_DOC_IDS)
def test_every_parsed_doc_yields_at_least_one_toolset_row(doc_path):
    rows = TOOLSET_BY_DOC[doc_path]
    assert rows, "%s's ## Toolset section yielded zero parsed rows" % doc_path


# ---------------------------------------------------------------------------
# Manifest authority: every parsed capability token must be declared,
# required or optional (SC-006).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("doc_path", AGENT_DOCS, ids=AGENT_DOC_IDS)
def test_every_capability_token_is_declared_in_the_manifest(doc_path):
    manifest = _load_manifest()
    declared = _declared_capabilities(manifest)
    for capability, _operations, _access in TOOLSET_BY_DOC[doc_path]:
        assert capability in declared, (
            "%s's Toolset table names capability %r, which is not in "
            "manifest/capabilities.json's required ∪ optional set %r"
            % (doc_path, capability, sorted(declared))
        )


# ---------------------------------------------------------------------------
# Operation fidelity: every parsed operation token must exist under its
# row's capability in the manifest (required or optional half).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("doc_path", AGENT_DOCS, ids=AGENT_DOC_IDS)
def test_every_operation_token_exists_under_its_capability(doc_path):
    manifest = _load_manifest()
    for capability, operations, _access in TOOLSET_BY_DOC[doc_path]:
        allowed_ops = _declared_ops(manifest, capability)
        for op in operations:
            assert op in allowed_ops, (
                "%s's Toolset table cites operation %r under capability %r, "
                "not present in the manifest's op set %r for that "
                "capability" % (doc_path, op, capability, sorted(allowed_ops))
            )


# ---------------------------------------------------------------------------
# Triage-specific pins (FR-006): exact capability set, every row read-only.
# ---------------------------------------------------------------------------


def test_triage_capability_set_is_exactly_the_pinned_four():
    rows = parse_toolset(TRIAGE_DOC.read_text(encoding="utf-8"))
    capabilities = {capability for capability, _operations, _access in rows}
    assert capabilities == {"alerting", "code", "storage", "observability"}, (
        "agents/triage.md's Toolset capability set is %r, expected exactly "
        "{alerting, code, storage, observability}" % sorted(capabilities)
    )


def test_triage_every_toolset_row_is_read_only():
    rows = parse_toolset(TRIAGE_DOC.read_text(encoding="utf-8"))
    for capability, _operations, access in rows:
        assert access == "read-only", (
            "agents/triage.md's %r Toolset row has Access %r, expected "
            "'read-only'" % (capability, access)
        )


# ---------------------------------------------------------------------------
# US3 / T014 — deep-investigator toolset gates (FR-007, US3-AS4). Reuses the
# module-level ``parse_toolset``/``_load_manifest`` helpers and the
# ``AGENT_DOCS``/``TOOLSET_BY_DOC`` fixtures above rather than re-parsing
# (module docstring). Capability-token and operation-token membership against
# the manifest (SC-006) is already covered for this doc by the parametrized
# checks above — ``AGENT_DOCS`` picks up ``agents/deep-investigator.md``
# automatically via the sorted glob, no new test needed for that half. This
# section adds what's specific to a *mixed* toolset: both read-only and
# approval-gated rows present, every mutating row's Access exactly
# ``approval-gated`` (never a bare "write"), and every read row exactly
# ``read-only``. Per tasks.md's serialization note this module's next
# extension is T018 (the three specialists).
# ---------------------------------------------------------------------------

DEEP_INVESTIGATOR_DOC = AGENTS_DIR / "deep-investigator.md"

# Capability manifest operations that mutate store state (append_record and
# update_record for storage, put_file for artifacts, append_entry for the
# diary) — the only operations a Toolset row may legitimately pair with
# ``approval-gated`` access. Every other declared operation (read_records,
# get_alert, list_alert_history, read_file, search, list_commits,
# query_metrics, search_logs, read_recent) is a read, and must pair with
# ``read-only``.
MUTATING_OPERATIONS = {"append_record", "update_record", "put_file", "append_entry"}

# Every agent doc's Toolset Access column must be one of these two values —
# no bare "write" access anywhere, across every agent doc, not only the deep
# investigator's (FR-007: "every mutation is approval-gated").
ALLOWED_ACCESS_VALUES = {"read-only", "approval-gated"}


def test_deep_investigator_doc_is_among_the_parsed_files():
    assert DEEP_INVESTIGATOR_DOC in AGENT_DOCS, (
        "agents/deep-investigator.md is not among the agents/*.md glob "
        "results %r" % AGENT_DOCS
    )


@pytest.mark.parametrize("doc_path", AGENT_DOCS, ids=AGENT_DOC_IDS)
def test_every_toolset_row_access_is_an_allowed_value(doc_path):
    for capability, _operations, access in TOOLSET_BY_DOC[doc_path]:
        assert access in ALLOWED_ACCESS_VALUES, (
            "%s's %r Toolset row has Access %r, expected one of %r — no "
            "bare 'write' access is permitted anywhere"
            % (doc_path, capability, access, sorted(ALLOWED_ACCESS_VALUES))
        )


def test_deep_investigator_has_both_read_only_and_approval_gated_rows():
    rows = parse_toolset(DEEP_INVESTIGATOR_DOC.read_text(encoding="utf-8"))
    access_values = {access for _capability, _operations, access in rows}
    assert "read-only" in access_values, (
        "agents/deep-investigator.md's Toolset table has no read-only row"
    )
    assert "approval-gated" in access_values, (
        "agents/deep-investigator.md's Toolset table has no approval-gated "
        "row"
    )


def test_deep_investigator_mutating_rows_are_approval_gated():
    rows = parse_toolset(DEEP_INVESTIGATOR_DOC.read_text(encoding="utf-8"))
    for capability, operations, access in rows:
        if set(operations) & MUTATING_OPERATIONS:
            assert access == "approval-gated", (
                "agents/deep-investigator.md's %r row grants a mutating "
                "operation among %r but Access is %r, expected "
                "'approval-gated'" % (capability, operations, access)
            )


def test_deep_investigator_read_rows_are_read_only():
    rows = parse_toolset(DEEP_INVESTIGATOR_DOC.read_text(encoding="utf-8"))
    for capability, operations, access in rows:
        if not (set(operations) & MUTATING_OPERATIONS):
            assert access == "read-only", (
                "agents/deep-investigator.md's %r row grants only read "
                "operations %r but Access is %r, expected 'read-only'"
                % (capability, operations, access)
            )


# ---------------------------------------------------------------------------
# US4 / T018 — specialist toolset gates (FR-008, US4-AS1). Reuses the
# module-level ``parse_toolset``/``_load_manifest`` helpers and the
# ``AGENT_DOCS``/``TOOLSET_BY_DOC`` fixtures above rather than re-parsing
# (module docstring). Capability/operation membership against the manifest
# (SC-006) and the allowed-Access-value gate are already covered for these
# three docs by the parametrized checks above — ``AGENT_DOCS`` picks up
# ``agents/log-diver.md``, ``agents/deploy-analyst.md``, and
# ``agents/dependency-checker.md`` automatically via the sorted glob, no new
# test needed for either half. This section adds what's specific to the three
# specialists: every row is read-only-ONLY (no approval-gated rows anywhere
# in a specialist toolset — specialists never mutate, unlike the deep
# investigator's mixed toolset above), and each specialist's exact capability
# set (FR-008; single-purpose toolsets narrower than triage's or the deep
# investigator's four-capability read set). No non-vanishing guard in this
# module pins an exact *count* of agent docs (the finalized nine-file count
# lives in test_investigation_prose.py's T022, not here), so there is no
# count guard to update.
# ---------------------------------------------------------------------------

LOG_DIVER_DOC = AGENTS_DIR / "log-diver.md"
DEPLOY_ANALYST_DOC = AGENTS_DIR / "deploy-analyst.md"
DEPENDENCY_CHECKER_DOC = AGENTS_DIR / "dependency-checker.md"

SPECIALIST_DOCS = [LOG_DIVER_DOC, DEPLOY_ANALYST_DOC, DEPENDENCY_CHECKER_DOC]
SPECIALIST_DOC_IDS = [p.relative_to(REPO_ROOT).as_posix() for p in SPECIALIST_DOCS]


def test_all_three_specialist_docs_are_among_the_parsed_files():
    for doc in SPECIALIST_DOCS:
        assert doc in AGENT_DOCS, (
            "%s is not among the agents/*.md glob results %r" % (doc, AGENT_DOCS)
        )


@pytest.mark.parametrize("doc_path", SPECIALIST_DOCS, ids=SPECIALIST_DOC_IDS)
def test_specialist_every_toolset_row_is_read_only(doc_path):
    rows = parse_toolset(doc_path.read_text(encoding="utf-8"))
    for capability, _operations, access in rows:
        assert access == "read-only", (
            "%s's %r Toolset row has Access %r, expected 'read-only' — "
            "specialists never mutate (FR-008)" % (doc_path, capability, access)
        )


def test_log_diver_capability_set_is_exactly_observability():
    rows = parse_toolset(LOG_DIVER_DOC.read_text(encoding="utf-8"))
    capabilities = {capability for capability, _operations, _access in rows}
    assert capabilities == {"observability"}, (
        "agents/log-diver.md's Toolset capability set is %r, expected "
        "exactly {observability}" % sorted(capabilities)
    )


def test_deploy_analyst_capability_set_is_exactly_code():
    rows = parse_toolset(DEPLOY_ANALYST_DOC.read_text(encoding="utf-8"))
    capabilities = {capability for capability, _operations, _access in rows}
    assert capabilities == {"code"}, (
        "agents/deploy-analyst.md's Toolset capability set is %r, expected "
        "exactly {code}" % sorted(capabilities)
    )


def test_dependency_checker_capability_set_is_exactly_code_and_observability():
    rows = parse_toolset(DEPENDENCY_CHECKER_DOC.read_text(encoding="utf-8"))
    capabilities = {capability for capability, _operations, _access in rows}
    assert capabilities == {"code", "observability"}, (
        "agents/dependency-checker.md's Toolset capability set is %r, "
        "expected exactly {code, observability}" % sorted(capabilities)
    )
