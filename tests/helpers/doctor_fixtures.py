"""Fixture surfaces for slice-4 doctor/setup contract tests (research R5, R8, R12;
data-model.md "Fixture surfaces" table). Dev-only: nothing here ships (FR-012,
Constitution I) — these builders and stand-ins exist solely so the resolution
protocol, the store-header create-vs-validate decision, the shell round-trip check,
and a responder-credential probe failure — none of which operation contract v1
models directly — can be exercised by hermetic contract tests instead of asserted on
prose (Constitution VIII).

Two families live here:

- Roster builders (R8): functions producing a *roster surface*
  (``tool_name -> {"input": {...}, "output": {...}}``) with shapes pulled live from a
  ``MockMcp`` instance's ``describe()`` — never hardcoded — and assigned to fixture
  tool names deliberately distinct from their op names (doctor-protocol.md's own
  example, ``"storage.append_record": "mycorp_sheets.add_row"``), so a resolver that
  degenerately matched tool name == op name would fail every assertion built on
  these rosters.
- Everything else (R5/R12): ``FixtureHeaderStore``, ``FixtureShellAdapter``, the
  ``FailingProbeInjector``, and loaders for the T005 config-block JSON fixtures
  under ``tests/fixtures/doctor/``.
"""

import json
from pathlib import Path

from helpers import store_flows

# ---------------------------------------------------------------------------
# Fixture tool-name assignment (R8) — identifiers only, never shapes. Shapes
# always come live from mock.describe() (required half) or the manifest passed
# in by the caller (optional half, R7) — these dicts exist purely so every
# roster builder and tests/fixtures/doctor/config-valid.json's `bindings` block
# agree on the same fixture tool name for the same operation.
# ---------------------------------------------------------------------------

REQUIRED_FIXTURE_TOOL_NAMES = {
    ("storage", "append_record"): "mycorp_sheets.add_row",
    ("storage", "read_records"): "mycorp_sheets.query_rows",
    ("storage", "update_record"): "mycorp_sheets.update_row",
    ("artifacts", "put_file"): "mycorp_drive.upload_file",
    ("diary", "append_entry"): "mycorp_wiki.add_note",
    ("diary", "read_recent"): "mycorp_wiki.recent_notes",
    ("alerting", "get_alert"): "mycorp_pager.fetch_alert",
    ("alerting", "list_alert_history"): "mycorp_pager.alert_history",
}

# R7's optional half (design §7.1): code.read_file/list_commits/search,
# observability.query_metrics/search_logs. Shapes are authored by the manifest
# (test callers pass one in), not by this module — see build_roster_with_optional.
OPTIONAL_FIXTURE_TOOL_NAMES = {
    ("code", "read_file"): "mycorp_repo.get_file_contents",
    ("code", "list_commits"): "mycorp_repo.list_commits",
    ("code", "search"): "mycorp_repo.search_code",
    ("observability", "query_metrics"): "mycorp_metrics.query",
    ("observability", "search_logs"): "mycorp_logs.search",
}

# The required capabilities/ops set (contracts/doctor-protocol.md's manifest
# section): every op contract.json declares for storage/artifacts/diary/alerting,
# except artifacts.get_file — "read-back for tests" (operations.md), excluded from
# the manifest's required half as test-only harness surface.
_REQUIRED_CAPABILITIES = ("storage", "artifacts", "diary", "alerting")
_EXCLUDED_REQUIRED_OPS = {("artifacts", "get_file")}


def _required_ops(mock):
    """(capability, op) pairs for every required-capability operation in the live
    contract, excluding artifacts.get_file — read live from mock.describe() so this
    can never drift from contract.json."""
    surface = mock.describe()
    ops = []
    for capability in _REQUIRED_CAPABILITIES:
        for op in surface.get(capability, {}):
            if (capability, op) in _EXCLUDED_REQUIRED_OPS:
                continue
            ops.append((capability, op))
    return ops


def required_bindings():
    """``capability.operation -> fixture tool name`` for every required op, in the
    exact map ``tests/fixtures/doctor/config-valid.json``'s ``bindings`` block
    mirrors (T005) — so tests can cross-use both fixtures without hand-copying the
    map twice."""
    return {
        "{}.{}".format(capability, op): tool_name
        for (capability, op), tool_name in REQUIRED_FIXTURE_TOOL_NAMES.items()
    }


# ---------------------------------------------------------------------------
# Roster builders (R8)
# ---------------------------------------------------------------------------


def build_full_roster(mock):
    """R8 'full-required' scenario: one distinctly-named fixture tool per required
    operation, shapes pulled live from ``mock.describe()``. ``mock`` may be a
    ``MockMcp`` instance or anything exposing the same ``describe()`` surface."""
    surface = mock.describe()
    roster = {}
    for capability, op in _required_ops(mock):
        try:
            tool_name = REQUIRED_FIXTURE_TOOL_NAMES[(capability, op)]
        except KeyError:
            raise KeyError(
                "no fixture tool name assigned for required op {}.{} — add one to "
                "REQUIRED_FIXTURE_TOOL_NAMES".format(capability, op)
            )
        roster[tool_name] = surface[capability][op]
    return roster


def build_roster_missing(mock, capability, op):
    """R8 'missing-one-required' scenario: ``build_full_roster`` with the given
    operation's fixture tool removed — resolution protocol step 2 (zero
    candidates -> loud fail naming the operation)."""
    roster = build_full_roster(mock)
    tool_name = REQUIRED_FIXTURE_TOOL_NAMES[(capability, op)]
    del roster[tool_name]
    return roster


def build_roster_multi_match(mock, capability, op):
    """R8 'two-tools-one-op' (ambiguity) scenario: adds a second tool with an
    identical shape for the given operation — resolution protocol step 3 (more
    than one candidate -> ``ambiguous`` + candidate names, no silent pick)."""
    roster = build_full_roster(mock)
    original_name = REQUIRED_FIXTURE_TOOL_NAMES[(capability, op)]
    second_name = original_name + "__second"
    roster[second_name] = dict(roster[original_name])
    return roster


def build_roster_with_optional(mock, manifest):
    """R7/R8 'with-optional' scenario: ``build_full_roster`` plus one fixture tool
    per optional operation ``manifest`` (``bb.capabilities.v1`` shape) declares.
    Shapes come from ``manifest`` itself, never from ``mock.describe()`` — R7
    deliberately does not extend contract v1 with optional ops, so the manifest is
    the shape authority for them until a consuming slice promotes them."""
    roster = build_full_roster(mock)
    optional = manifest.get("optional", {})
    for capability, cap_block in optional.items():
        for op, shape in cap_block.get("ops", {}).items():
            try:
                tool_name = OPTIONAL_FIXTURE_TOOL_NAMES[(capability, op)]
            except KeyError:
                raise KeyError(
                    "no fixture tool name assigned for optional op {}.{} — add one "
                    "to OPTIONAL_FIXTURE_TOOL_NAMES".format(capability, op)
                )
            roster[tool_name] = {"input": shape["input"], "output": shape["output"]}
    return roster


def build_roster_drifted(roster, bindings, capability, op, rename_to=None):
    """R8 'drifted' scenario: the tool a committed binding entry
    (``bindings["capability.operation"] -> tool_name``) references is removed from
    the roster (``rename_to=None``) or renamed (``rename_to=<new name>``) — doctor's
    drift re-validation (contracts/doctor-protocol.md "Drift re-validation") must
    flag the entry stale by name, never silently rewrite it. Returns a new roster
    dict; neither ``roster`` nor ``bindings`` is mutated."""
    roster = dict(roster)
    key = "{}.{}".format(capability, op)
    tool_name = bindings[key]
    shape = roster.pop(tool_name)
    if rename_to is not None:
        roster[rename_to] = shape
    return roster


# ---------------------------------------------------------------------------
# FixtureHeaderStore (R5) — store header create-vs-validate
# ---------------------------------------------------------------------------

# Header representation (contracts/doctor-protocol.md "Store header
# create-vs-validate"): schema.md column order, then the version-sentinel cell.
# Authority chain: schema.md -> SC-006 cross-check -> store_flows.COLUMN_NAMES —
# this slice re-parses nothing (research R5).
EXPECTED_HEADER = list(store_flows.COLUMN_NAMES) + [store_flows.SCHEMA_VERSION]


class FixtureHeaderStore:
    """R5: fixture stand-in for a live store's header row + sentinel cell —
    operation contract v1 has no header concept. ``header`` is an ordered cell
    list, or ``None`` for an empty store. Every ``create_header`` call is recorded
    in ``write_log`` (ordered), mirroring bb-mock-mcp's write-log discipline so
    create-vs-validate tests can assert zero writes on the validate path."""

    def __init__(self, header=None):
        self.header = header
        self.write_log = []

    def read_header(self):
        """The current header cells, or ``None`` for an empty store. Never
        mutates state."""
        return self.header

    def create_header(self, cells):
        """Writes ``cells`` as the header row (the empty-store path) and appends
        the write to ``write_log``. Returns the stored header."""
        cells = list(cells)
        self.header = cells
        self.write_log.append(cells)
        return self.header


# ---------------------------------------------------------------------------
# FixtureShellAdapter (R12) — shell notify round-trip check
# ---------------------------------------------------------------------------


class FixtureShellAdapter:
    """R12: fixture stand-in for slice 9's ``bb-shell notify`` round-trip
    (contracts/doctor-protocol.md 'shell' check). ``answering=True`` (default)
    makes ``notify`` echo the message back — the check's ``ok`` path;
    ``answering=False`` makes it raise — the ``fail`` path. There is no third
    "absent" instance state: absence of a configured adapter is represented by
    passing ``None`` where an adapter is expected (the check's ``skip`` path is
    "no adapter configured", not an adapter attribute — FR-003)."""

    def __init__(self, answering=True):
        self.answering = answering
        self.calls = []

    def notify(self, message):
        self.calls.append(message)
        if not self.answering:
            raise RuntimeError(
                "fixture shell adapter: notify unreachable (answering=False)"
            )
        return message


# ---------------------------------------------------------------------------
# FailingProbeInjector — responder-credential/permission failure stand-in
# ---------------------------------------------------------------------------

# Operation contract v1's closed error-code set (errors.py ERROR_CODES) has no
# entry for an authentication/permission failure — data-model.md "Fixture
# surfaces" names this injector as the stand-in. It borrows an existing
# closed-set code rather than inventing a new one (a new code would itself be an
# undocumented contract extension).
_DEFAULT_INJECTED_CODE = "invalid_input"
_DEFAULT_INJECTED_MESSAGE = (
    "responder credentials rejected (fixture stand-in — operation contract v1 has "
    "no auth error code; see data-model.md 'Fixture surfaces')"
)


class FailingProbeInjector:
    """Wraps a ``MockMcp`` so every call against ``failing_capability`` returns the
    contract's uniform error envelope, unconditionally — a stand-in for a
    responder-credential/permission failure. Every other capability's calls pass
    straight through to the wrapped mock unchanged, so one capability's binding can
    fail under this responder's credentials while the rest of a doctor run
    proceeds normally. Exposes the same ``invoke``/``describe`` surface real flow
    helpers call, and forwards any other attribute access (``records``,
    ``write_log``, ``schema_registry``, ...) to the wrapped mock for test
    inspection."""

    def __init__(
        self,
        mock,
        failing_capability,
        code=_DEFAULT_INJECTED_CODE,
        message=_DEFAULT_INJECTED_MESSAGE,
    ):
        self._mock = mock
        self.failing_capability = failing_capability
        self._code = code
        self._message = message

    def describe(self):
        return self._mock.describe()

    def invoke(self, capability, op, payload=None):
        if capability == self.failing_capability:
            return {
                "error": {
                    "op": "{}.{}".format(capability, op),
                    "code": self._code,
                    "message": self._message,
                }
            }
        return self._mock.invoke(capability, op, payload)

    def __getattr__(self, name):
        # Anything not defined on the injector itself (test-inspection surfaces,
        # schema_registry, etc.) passes through to the wrapped mock.
        return getattr(self._mock, name)


# ---------------------------------------------------------------------------
# Config-block fixture loaders (T005) — tests/fixtures/doctor/*.json
# ---------------------------------------------------------------------------

# Mirrors conftest.py's TESTS_DIR/FIXTURES_DIR idiom (and failopen.py's
# FAULTS_DIR) without importing conftest — helper modules stay usable
# independent of the pytest-only conftest module.
_HELPERS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _HELPERS_DIR.parent
DOCTOR_FIXTURES_DIR = _TESTS_DIR / "fixtures" / "doctor"


def config_fixture_path(name):
    """Absolute path to a ``tests/fixtures/doctor/*.json`` fixture (T005) — for
    callers that want a path rather than parsed content (e.g. asserting that
    ``json.load`` raises on the malformed fixture)."""
    return DOCTOR_FIXTURES_DIR / name


def load_config_fixture(name):
    """Load and parse one of the T005 config-block fixtures by filename (e.g.
    ``"config-valid.json"``). Raises ``json.JSONDecodeError`` unchanged for the
    malformed fixture — callers that want to assert the parse failure do so
    themselves rather than have this loader swallow it."""
    path = config_fixture_path(name)
    with open(str(path), encoding="utf-8") as f:
        return json.load(f)
