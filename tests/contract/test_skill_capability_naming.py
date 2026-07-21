"""FR-010: skill prose names capabilities and operations, never concrete MCP
server/tool names (Constitution VII).

Scans every ``*.md`` file under ``skills/session-store/`` (``rglob`` — recursive,
so a future reference file is covered automatically, no list to maintain) for
three things:

1. **The literal substring ``mcp__``** — the concrete-tool-name marker any
   Claude Code MCP tool invocation carries. A hard fail wherever it appears,
   fenced or not: there is no legitimate reason a documented *convention*
   would ever spell out a literal tool-call string.
2. **A deny-list of concrete MCP server/product names** in normative prose —
   "sheets mcp", "drive mcp", "docs mcp", "google sheets", "google drive",
   "google docs", "opsgenie", "pagerduty", "grafana", "splunk", "datadog".
   Store-medium nouns (Sheet, Drive, cell) remain permitted per FR-010 — every
   multi-word pattern requires its qualifying word ("google", "mcp"), so a
   doc's standalone "Drive" (the tier-0 medium noun) never trips "google
   drive".
3. **Operation-contract fidelity** — every backtick-quoted single-token span
   that *looks like* a storage/artifact/diary operation name (ends with
   ``_record``/``_records``/``_file``/``_entry``, or sits in a small curated
   set of contract ops that don't follow that suffix shape) must be a real
   operation in ``tools/bb-mock-mcp/contract.json``'s capabilities — the set
   is built dynamically from the contract file (never hardcoded), so a doc
   citing an operation the contract doesn't have fails here rather than a doc
   citing a real one just not being in some maintained allow-list.

**Fence-stripping rule (deny-list scan only)**: before the deny-list scan,
every ```` ``` ````-fenced code block's *content* is removed from the text.
``references/fingerprint.md``'s rung-4 worked example fences the literal
alert-source value ``datadog`` ("the alerting tool's source identifier,"
per that doc's rung-4 rule) — a worked *data value* fed into the fingerprint
formula, not a tool integration named by the skill. Fences are exactly where
a worked example's raw data belongs, so stripping them before the scan (and
still carrying "datadog" in the deny-list) means that example passes today
because it is fenced — the same string typed into normative prose *outside*
a fence still fails (``test_fenced_datadog_example_is_the_documented_exemption``
below pins both halves of that claim). The ``mcp__`` check does **not** get
this exemption and scans raw text, fenced or not — a literal tool-call
string has no legitimate fenced use here either.
"""

import json
import re

import pytest

from conftest import REPO_ROOT

SKILLS_DIR = REPO_ROOT / "skills" / "session-store"
CONTRACT_PATH = REPO_ROOT / "tools" / "bb-mock-mcp" / "contract.json"

MD_FILES = sorted(SKILLS_DIR.rglob("*.md"))
MD_IDS = [p.relative_to(SKILLS_DIR).as_posix() for p in MD_FILES]

FENCE_RE = re.compile(r"```.*?```", re.DOTALL)

# FR-010 deny-list: concrete MCP server/product names that must never appear
# in normative prose (fenced worked-example data excepted — see module
# docstring). Case-insensitive; "google X" / "X mcp" patterns require the
# qualifying word so a bare medium noun (Sheet, Drive, cell) never trips them.
DENY_PATTERNS = {
    "sheets mcp": re.compile(r"sheets\s+mcp", re.IGNORECASE),
    "drive mcp": re.compile(r"drive\s+mcp", re.IGNORECASE),
    "docs mcp": re.compile(r"docs\s+mcp", re.IGNORECASE),
    "google sheets": re.compile(r"google\s+sheets", re.IGNORECASE),
    "google drive": re.compile(r"google\s+drive", re.IGNORECASE),
    "google docs": re.compile(r"google\s+docs", re.IGNORECASE),
    "opsgenie": re.compile(r"opsgenie", re.IGNORECASE),
    "pagerduty": re.compile(r"pagerduty", re.IGNORECASE),
    "grafana": re.compile(r"grafana", re.IGNORECASE),
    "splunk": re.compile(r"splunk", re.IGNORECASE),
    "datadog": re.compile(r"datadog", re.IGNORECASE),
}

BACKTICK_TOKEN_RE = re.compile(r"`([a-z_]+)`")
OP_LIKE_SUFFIXES = ("_record", "_records", "_file", "_entry")
# Contract ops that don't follow the _record(s)/_file/_entry suffix shape —
# curated so the fidelity check still has a hook if a doc ever cites one.
CURATED_OP_CANDIDATES = {"read_recent", "get_alert", "list_alert_history"}


def _strip_fenced_blocks(text):
    """Remove every ```-fenced block's content (deny-list scan target only).

    A worked example's raw data (e.g. fingerprint.md's "datadog" alert-source
    literal) lives inside a fence deliberately — see module docstring.
    """
    return FENCE_RE.sub("", text)


def _load_contract_ops():
    with open(str(CONTRACT_PATH), encoding="utf-8") as f:
        contract = json.load(f)
    ops = set()
    for capability in contract["capabilities"].values():
        ops.update(capability["ops"].keys())
    return ops


CONTRACT_OPS = _load_contract_ops()


def _looks_like_op(token):
    return token.endswith(OP_LIKE_SUFFIXES) or token in CURATED_OP_CANDIDATES


def _op_like_tokens(text):
    return {tok for tok in BACKTICK_TOKEN_RE.findall(text) if _looks_like_op(tok)}


# ---------------------------------------------------------------------------
# Non-vanishing guard (TA5-style, per test_fingerprint_reference.py's
# precedent): a broken glob or an emptied doc set must not turn every
# parametrized check below into a silently-skipped, still-green no-op.
# ---------------------------------------------------------------------------


def test_scan_finds_the_known_skill_docs():
    names = set(MD_IDS)
    assert {
        "SKILL.md",
        "references/schema.md",
        "references/fingerprint.md",
        "references/retrieval.md",
    } <= names


# ---------------------------------------------------------------------------
# 1. mcp__ hard fail — raw text, fenced or not.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("doc_path", MD_FILES, ids=MD_IDS)
def test_no_concrete_mcp_tool_name_marker(doc_path):
    text = doc_path.read_text(encoding="utf-8")
    assert "mcp__" not in text, (
        "%s references a concrete MCP tool name (mcp__ marker) — FR-010 requires "
        "capability/operation names only, never a hardcoded MCP tool name"
        % doc_path
    )


# ---------------------------------------------------------------------------
# 2. Server/product-name deny-list — fenced blocks stripped first.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("doc_path", MD_FILES, ids=MD_IDS)
def test_no_concrete_server_product_name_outside_fences(doc_path):
    text = doc_path.read_text(encoding="utf-8")
    prose = _strip_fenced_blocks(text)
    hits = sorted(name for name, pattern in DENY_PATTERNS.items() if pattern.search(prose))
    assert not hits, (
        "%s names a concrete MCP server/product in normative prose: %r — FR-010 "
        "permits only operation names and store-medium nouns (Sheet, Drive, cell)"
        % (doc_path, hits)
    )


def test_fenced_datadog_example_is_the_documented_exemption():
    """Pins both halves of the fence-stripping claim against drift.

    If fingerprint.md's worked example ever loses its fence (or the string),
    this — not a silently-passing deny-list scan — is what should fail.
    """
    fp_doc = SKILLS_DIR / "references" / "fingerprint.md"
    text = fp_doc.read_text(encoding="utf-8")
    assert DENY_PATTERNS["datadog"].search(text), (
        "expected the known fenced worked-example use of 'datadog' in "
        "fingerprint.md; the fence-stripping exemption this test documents "
        "has nothing to exempt"
    )
    assert not DENY_PATTERNS["datadog"].search(_strip_fenced_blocks(text)), (
        "'datadog' survives fence-stripping — it is no longer confined to a "
        "fenced worked example and the deny-list should be catching it"
    )


# ---------------------------------------------------------------------------
# 3. Operation-contract fidelity — every doc-cited op-like backtick token
#    must be a real contract op, loaded dynamically from contract.json.
# ---------------------------------------------------------------------------


def test_contract_ops_loaded_dynamically_is_non_empty():
    assert CONTRACT_OPS
    assert {
        "append_record",
        "read_records",
        "update_record",
        "put_file",
        "get_file",
        "append_entry",
    } <= CONTRACT_OPS


@pytest.mark.parametrize("doc_path", MD_FILES, ids=MD_IDS)
def test_doc_cited_operations_exist_in_contract(doc_path):
    text = doc_path.read_text(encoding="utf-8")
    cited = _op_like_tokens(text)
    unknown = sorted(cited - CONTRACT_OPS)
    assert not unknown, (
        "%s cites operation-like token(s) absent from contract.json's "
        "capabilities: %r" % (doc_path, unknown)
    )


def test_skill_docs_cite_the_expected_core_operations():
    # Positive control: the fidelity check above has something real to bite
    # on — an always-empty cited set would make it vacuously true.
    all_text = "\n".join(p.read_text(encoding="utf-8") for p in MD_FILES)
    cited = _op_like_tokens(all_text)
    assert {
        "append_record",
        "read_records",
        "update_record",
        "put_file",
        "get_file",
        "append_entry",
    } <= cited
