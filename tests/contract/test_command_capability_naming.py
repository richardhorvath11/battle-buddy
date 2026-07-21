"""FR-010: shipped command/manifest/template prose names capabilities and
operations only, never concrete MCP server/tool names (Constitution VII) —
the slice-4 extension of the slice-3 mechanism
(``tests/contract/test_skill_capability_naming.py``) over this slice's new
prose surfaces: ``commands/*.md``, ``manifest/capabilities.json`` (its prose
*strings*, not its structural keys), and ``templates/session-sheet.md``
(research R13). ``templates/mcp.recommended.json`` is FR-010's single
sanctioned server-naming location and is therefore EXEMPT from the deny scan
— a dedicated positive test below asserts it is valid, capability-covering,
and secret-free instead.

Three porting caveats from the slice-3 mechanism, per spec.md FR-010 / R13 /
tasks.md T022 (do **not** port verbatim):

1. **Deny-list**: reused by importing ``DENY_PATTERNS`` from
   ``test_skill_capability_naming`` (rather than re-typing it — one list, one
   place it can drift) and extended here with vendor names relevant to the
   two *optional* capabilities this slice's manifest introduces (``code``,
   ``observability``) plus a few additional storage/artifacts/diary/alerting
   vendors slice 3 had no reason to name. ``FENCE_RE`` is imported too;
   ``_strip_fenced_blocks`` itself is restated as a one-line wrapper rather
   than imported, since it is underscore-prefixed in its home module (a
   private helper, not a name meant for cross-module reuse) while the regex
   it wraps is a public constant we do import directly.
2. **Dotted operation tokens.** Slice-3's fidelity check only recognizes
   *undotted* backtick tokens (``BACKTICK_TOKEN_RE`` = `` `([a-z_]+)` `` —
   no dot allowed at all). This slice's command prose instead cites
   operations throughout in the protocol's actual `capability.operation`
   form (`` `storage.append_record` ``, `` `diary.append_entry` ``, ...), so
   a *new*, separate regex is needed — porting the undotted one verbatim
   would silently never match any of these tokens and the fidelity check
   would be vacuous. See ``_dotted_capability_op_candidates`` below for how
   the false-positive surface (file names, config keys, version sentinels
   that happen to contain a lowercase `word.word` substring) is kept out.
3. **Authority for undotted op-like tokens.** If the slice-3
   ``OP_LIKE_SUFFIXES`` approach is ported for undotted tokens, the ops it
   resolves against must be ``manifest/capabilities.json``'s required ∪
   optional op set, **not** ``tools/bb-mock-mcp/contract.json`` directly —
   contract v1 declares no optional operations at all (research R7), so an
   undotted mention of an optional op such as `` `read_file` `` would
   false-fail against contract.json alone even though it is a perfectly
   valid manifest operation. See ``test_undotted_op_like_tokens_...`` below.
"""

import json
import re

import pytest

from conftest import REPO_ROOT
from test_skill_capability_naming import (
    BACKTICK_TOKEN_RE,
    DENY_PATTERNS as _SLICE3_DENY_PATTERNS,
    FENCE_RE,
    OP_LIKE_SUFFIXES,
)

COMMANDS_DIR = REPO_ROOT / "commands"
MANIFEST_PATH = REPO_ROOT / "manifest" / "capabilities.json"
TEMPLATES_DIR = REPO_ROOT / "templates"
SESSION_SHEET_PATH = TEMPLATES_DIR / "session-sheet.md"
MCP_RECOMMENDED_PATH = TEMPLATES_DIR / "mcp.recommended.json"

COMMAND_MD_FILES = sorted(COMMANDS_DIR.glob("*.md"))

# Deny-scan targets: every shipped command doc + the store-template reference
# doc. `templates/mcp.recommended.json` is deliberately absent — FR-010's one
# sanctioned exemption, asserted separately below.
MD_SCAN_TARGETS = COMMAND_MD_FILES + [SESSION_SHEET_PATH]
MD_SCAN_IDS = [p.relative_to(REPO_ROOT).as_posix() for p in MD_SCAN_TARGETS]


# ---------------------------------------------------------------------------
# Deny-list: slice-3's list, imported, extended with vendor names relevant to
# this slice's optional capabilities (`code`, `observability`) and a few more
# storage/artifacts/diary/alerting vendors slice 3 had no reason to name.
# ---------------------------------------------------------------------------

_VENDOR_DENY_EXTENSIONS = {
    # code-hosting vendors (this slice's optional `code` capability)
    "github": re.compile(r"github", re.IGNORECASE),
    "gitlab": re.compile(r"gitlab", re.IGNORECASE),
    "bitbucket": re.compile(r"bitbucket", re.IGNORECASE),
    # observability vendors (this slice's optional `observability` capability)
    "honeycomb": re.compile(r"honeycomb", re.IGNORECASE),
    "new relic": re.compile(r"new\s*relic", re.IGNORECASE),
    "prometheus": re.compile(r"prometheus", re.IGNORECASE),
    "kibana": re.compile(r"kibana", re.IGNORECASE),
    "cloudwatch": re.compile(r"cloudwatch", re.IGNORECASE),
    # additional storage/artifacts/diary vendors
    "notion": re.compile(r"notion", re.IGNORECASE),
    "airtable": re.compile(r"airtable", re.IGNORECASE),
    "confluence": re.compile(r"confluence", re.IGNORECASE),
    "dropbox": re.compile(r"dropbox", re.IGNORECASE),
    "sharepoint": re.compile(r"sharepoint", re.IGNORECASE),
    # additional alerting vendors
    "victorops": re.compile(r"victorops", re.IGNORECASE),
    "xmatters": re.compile(r"xmatters", re.IGNORECASE),
    "squadcast": re.compile(r"squadcast", re.IGNORECASE),
    "bigpanda": re.compile(r"bigpanda", re.IGNORECASE),
    "servicenow": re.compile(r"servicenow", re.IGNORECASE),
    "zendesk": re.compile(r"zendesk", re.IGNORECASE),
}

DENY_PATTERNS = dict(_SLICE3_DENY_PATTERNS)
DENY_PATTERNS.update(_VENDOR_DENY_EXTENSIONS)


def _strip_fenced_blocks(text):
    """Restated (not imported) from ``test_skill_capability_naming``: that
    module's version is a private helper; the constant it wraps (``FENCE_RE``)
    is imported directly above, so this is the only duplicated line.
    """
    return FENCE_RE.sub("", text)


def _json_string_values(obj):
    """Recursively yield every string leaf value in a parsed JSON structure
    — the "prose strings" the deny scan targets, deliberately excluding
    object keys (capability/op names, which are structural, not prose).
    """
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            for s in _json_string_values(value):
                yield s
    elif isinstance(obj, list):
        for item in obj:
            for s in _json_string_values(item):
                yield s


# ---------------------------------------------------------------------------
# Manifest authority — loaded once, dynamically (never hardcoded), so a
# manifest change is reflected here automatically instead of silently
# diverging from a stale copy.
# ---------------------------------------------------------------------------


def _load_manifest():
    with open(str(MANIFEST_PATH), encoding="utf-8") as f:
        return json.load(f)


MANIFEST = _load_manifest()
REQUIRED_CAPABILITIES = set(MANIFEST["required"])

CAPABILITY_OPS = {}
for _half in ("required", "optional"):
    for _cap_name, _cap in MANIFEST[_half].items():
        CAPABILITY_OPS[_cap_name] = set(_cap["ops"])

ALL_MANIFEST_OPS = set()
for _ops in CAPABILITY_OPS.values():
    ALL_MANIFEST_OPS.update(_ops)


# ---------------------------------------------------------------------------
# Non-vanishing guards — a broken glob or an emptied file set must not turn
# every parametrized/derived check below into a silently-skipped no-op
# (TA5-style precedent, per test_skill_capability_naming.py).
# ---------------------------------------------------------------------------


def test_scan_finds_the_known_command_docs():
    names = {p.name for p in COMMAND_MD_FILES}
    assert {"doctor.md", "setup.md"} <= names


def test_scan_targets_all_exist():
    for path in MD_SCAN_TARGETS + [MANIFEST_PATH, MCP_RECOMMENDED_PATH]:
        assert path.is_file(), "%s missing" % path


def test_mcp_recommended_template_not_in_deny_scan_targets():
    # Guards the FR-010 exemption itself: this file must never accidentally
    # join the deny-scanned set (e.g. via a future `.md` rename).
    assert MCP_RECOMMENDED_PATH not in MD_SCAN_TARGETS


# ---------------------------------------------------------------------------
# 1a. mcp__ hard fail — commands/*.md and templates/session-sheet.md, raw
#     text, fenced or not.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("doc_path", MD_SCAN_TARGETS, ids=MD_SCAN_IDS)
def test_no_concrete_mcp_tool_name_marker(doc_path):
    text = doc_path.read_text(encoding="utf-8")
    assert "mcp__" not in text, (
        "%s references a concrete MCP tool name (mcp__ marker) — FR-010 requires "
        "capability/operation names only, never a hardcoded MCP tool name" % doc_path
    )


# ---------------------------------------------------------------------------
# 1b. Server/product-name deny-list — fenced blocks stripped first.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("doc_path", MD_SCAN_TARGETS, ids=MD_SCAN_IDS)
def test_no_concrete_server_product_name_outside_fences(doc_path):
    text = doc_path.read_text(encoding="utf-8")
    prose = _strip_fenced_blocks(text)
    hits = sorted(name for name, pattern in DENY_PATTERNS.items() if pattern.search(prose))
    assert not hits, (
        "%s names a concrete MCP server/product in normative prose: %r — FR-010 "
        "confines concrete server names to templates/mcp.recommended.json only"
        % (doc_path, hits)
    )


# ---------------------------------------------------------------------------
# 1c. manifest/capabilities.json — scan prose *string values* only (never
#     structural keys, which are legitimately-named capabilities/ops).
# ---------------------------------------------------------------------------


def test_manifest_prose_strings_have_no_mcp_marker():
    blob = "\n".join(_json_string_values(MANIFEST))
    assert "mcp__" not in blob, (
        "manifest/capabilities.json's prose strings reference a concrete MCP "
        "tool name (mcp__ marker) — FR-010 forbids this everywhere but the "
        "recommended-roster template"
    )


def test_manifest_prose_strings_have_no_vendor_deny_hits():
    blob = "\n".join(_json_string_values(MANIFEST))
    hits = sorted(name for name, pattern in DENY_PATTERNS.items() if pattern.search(blob))
    assert not hits, (
        "manifest/capabilities.json's prose strings name a concrete MCP "
        "server/product: %r — FR-010 confines concrete server names to "
        "templates/mcp.recommended.json only" % hits
    )


# ---------------------------------------------------------------------------
# 2. Positive roster-template test — templates/mcp.recommended.json is the
#    FR-010 sanctioned exemption: valid JSON, non-empty roster, names all
#    four required capabilities, and every credential is an env-var ref.
# ---------------------------------------------------------------------------

ENV_REF_RE = re.compile(r"^\$\{[A-Z0-9_]+\}$")


def _load_mcp_recommended():
    with open(str(MCP_RECOMMENDED_PATH), encoding="utf-8") as f:
        return json.load(f)


def test_mcp_recommended_template_parses_as_json_with_server_entries():
    roster = _load_mcp_recommended()
    assert isinstance(roster, dict)
    assert roster.get("mcpServers"), (
        "templates/mcp.recommended.json must declare at least one server "
        "under mcpServers"
    )


def test_mcp_recommended_template_covers_all_required_capabilities():
    text = MCP_RECOMMENDED_PATH.read_text(encoding="utf-8")
    # Required capability names loaded from the manifest (never hardcoded),
    # so this test tracks the manifest if the required set ever changes.
    missing = sorted(cap for cap in REQUIRED_CAPABILITIES if cap not in text)
    assert not missing, (
        "templates/mcp.recommended.json does not name all required "
        "capabilities somewhere in the file (server keys or description) — "
        "FR-25a's default roster must cover all of them out of the box; "
        "missing: %r" % missing
    )


def test_mcp_recommended_template_env_values_are_var_refs_never_literals():
    roster = _load_mcp_recommended()
    bad = []
    for server_name, server in roster["mcpServers"].items():
        for key, value in server.get("env", {}).items():
            if not ENV_REF_RE.match(value):
                bad.append("%s.env.%s=%r" % (server_name, key, value))
    assert not bad, (
        "templates/mcp.recommended.json has env value(s) that are not "
        "${ENV_VAR} references — secrets must never enter this file (FR-007): "
        "%r" % bad
    )


def test_mcp_recommended_template_is_the_documented_deny_scan_exemption():
    """Mirrors test_skill_capability_naming.py's fenced-datadog exemption
    pin: proves this file really does contain deny-listed vendor names (it
    is FR-010's one sanctioned location for them), so excluding it from the
    deny scan above is an intentional exemption — not survivorship because
    the file happens to be vendor-name-free.
    """
    text = MCP_RECOMMENDED_PATH.read_text(encoding="utf-8")
    hits = sorted(name for name, pattern in DENY_PATTERNS.items() if pattern.search(text))
    assert hits, (
        "expected templates/mcp.recommended.json to contain deny-listed "
        "vendor names; if this fails, the deny-scan exemption above has "
        "nothing to exempt"
    )


# ---------------------------------------------------------------------------
# 3. Dotted `capability.operation` fidelity — commands/*.md only (the
#    manifest and the store-template doc don't use this citation form).
# ---------------------------------------------------------------------------

# Whole backtick-span must be EXACTLY `word.word` (single dot, lowercase +
# underscore only, no newline) — this shape alone already excludes every
# non-operation dotted token seen in the shipped docs today:
#   `.claude/settings.json`, `manifest/capabilities.json`,
#   `templates/mcp.recommended.json` — contain "/", fail the all-lowercase
#     single-token anchor
#   `.bb-doctor-stamp.json`, `bb.stamp.v1` — leading dot / >1 dot / a digit
#     ("v1"), fail the exact single-dot anchor
#   `battleBuddy.bindings`, `budgets.triageTurnCap` — mixed case, fail
#     `[a-z_]+` entirely
#   `<capability>.<operation>` — angle brackets, fails entirely
INLINE_BACKTICK_RE = re.compile(r"`([^`\n]+)`")
DOTTED_TOKEN_FULL_RE = re.compile(r"^[a-z_]+\.[a-z_]+$")


def _dotted_capability_op_candidates(text):
    return {
        m.group(1)
        for m in INLINE_BACKTICK_RE.finditer(text)
        if DOTTED_TOKEN_FULL_RE.match(m.group(1))
    }


def _resolved_dotted_refs(text):
    """Dotted candidates whose prefix is an actual manifest capability name —
    the practical filter research R13 / T022 calls for. This is largely
    belt-and-suspenders given the exact-shape filter above already excludes
    every known non-operation token, but it also correctly drops the format
    placeholder `capability.operation` itself (prefix "capability" is not a
    real capability name) without special-casing it.
    """
    resolved = {}
    unresolved_capability = []
    for token in _dotted_capability_op_candidates(text):
        prefix, _, op = token.partition(".")
        if prefix not in CAPABILITY_OPS:
            continue
        resolved[token] = (prefix, op)
    return resolved


def test_dotted_capability_operation_tokens_resolve_against_manifest():
    unresolved = []
    for doc_path in COMMAND_MD_FILES:
        text = doc_path.read_text(encoding="utf-8")
        for token, (prefix, op) in _resolved_dotted_refs(text).items():
            if op not in CAPABILITY_OPS[prefix]:
                unresolved.append(
                    "%s: `%s` — capability %r has no operation %r in "
                    "manifest/capabilities.json"
                    % (doc_path.relative_to(REPO_ROOT), token, prefix, op)
                )
    assert not unresolved, "\n".join(sorted(unresolved))


def test_dotted_capability_operation_tokens_non_vacuity_guard():
    # Positive control: commands/doctor.md and commands/setup.md definitely
    # cite these dotted operation names — if this set ever comes back empty,
    # the fidelity check above would be passing vacuously.
    all_text = "\n".join(p.read_text(encoding="utf-8") for p in COMMAND_MD_FILES)
    resolved = _resolved_dotted_refs(all_text)
    assert {
        "storage.append_record",
        "storage.read_records",
        "artifacts.put_file",
        "diary.append_entry",
    } <= set(resolved)


# ---------------------------------------------------------------------------
# 4. Undotted op-like tokens (slice-3's OP_LIKE_SUFFIXES approach), ported
#    thoughtfully: resolved against the MANIFEST's required ∪ optional ops,
#    never contract.json — contract v1 has no optional ops at all (R7), so
#    an undotted `read_file` would false-fail against contract.json alone.
#
#    Today commands/*.md cite every operation in the dotted
#    `capability.operation` form (see section 3 above), so no undotted
#    op-like token currently exists in either file and this check currently
#    passes vacuously by construction — it is kept so a future undotted
#    mention (bare `read_file`, `append_record`, ...) is still caught
#    against the correct authority rather than silently drifting, or being
#    ported over from slice-3's contract-only check and false-failing on an
#    optional op.
# ---------------------------------------------------------------------------

# Ops that don't follow the _record(s)/_file/_entry suffix shape: slice-3's
# curated required-side set, extended with this slice's optional-side
# non-suffix ops (list_commits, search, query_metrics, search_logs) — the
# same "still has a hook if a doc ever cites one" rationale as slice-3.
CURATED_OP_CANDIDATES = {
    "read_recent",
    "get_alert",
    "list_alert_history",
    "list_commits",
    "search",
    "query_metrics",
    "search_logs",
}


def _looks_like_undotted_op(token):
    return token.endswith(OP_LIKE_SUFFIXES) or token in CURATED_OP_CANDIDATES


def _undotted_op_like_tokens(text):
    return {tok for tok in BACKTICK_TOKEN_RE.findall(text) if _looks_like_undotted_op(tok)}


def test_undotted_op_like_tokens_resolve_against_manifest_not_contract():
    unresolved = []
    for doc_path in COMMAND_MD_FILES:
        text = doc_path.read_text(encoding="utf-8")
        cited = _undotted_op_like_tokens(text)
        unknown = sorted(cited - ALL_MANIFEST_OPS)
        if unknown:
            unresolved.append("%s: %r" % (doc_path.relative_to(REPO_ROOT), unknown))
    assert not unresolved, "\n".join(unresolved)
