"""Fixture surfaces for slice-5 lifecycle-command contract tests (research
R1, R3-R6, R9, R10; data-model.md "Fixture surfaces" table). Dev-only:
nothing here ships (FR-013, Constitution I) — these fixtures and stand-ins
exist solely so `/page`/`/incident`/`/close`'s consumed slice-6-9 surfaces
(triage, catalog resolution, shell adapter) and the local-state protocol's
trace/checkpoint inputs can be exercised by hermetic contract tests instead
of asserted on prose (Constitution VIII). Nothing in this module is a
concrete MCP server or tool name (Constitution VII) — the few fixture tool
names below are deliberately fake, reusing doctor_fixtures.py's own
obviously-fictitious ``mycorp_*`` roster for consistency across fixture
modules.

Families, one per research decision:

- **R3** — fixture-verdict loaders: single ``bb.verdict.v1`` documents plus
  ordered re-prompt candidate lists from the `verdicts/*/` pair directories,
  validated by the real ``bb_validate`` (never a mock of the validator).
- **R4** — ``resolve_service``: a deterministic resolver walking design
  §5.2's fingerprint service-resolution ladder over
  ``tests/fixtures/lifecycle/catalog.json``, fingerprinting always through
  the real ``bb_fingerprint`` helper (D-4 — one implementation, no drift).
- **R6** — ``RecordingShellAdapter``/``FailingShellAdapter`` (the slice-9
  ``bb-shell`` stand-in) and ``PrintedOutput`` (the degraded-mode printed-
  message convention when a flow's ``shell`` argument is ``None``).
- **T004/T005** — seed loaders: ``tests/fixtures/lifecycle/seeds/*.json`` ->
  ``storage.append_record`` rows, columns checked against
  ``store_flows.COLUMN_NAMES``.
- **R10** — local-state builders: fixture ``trace.jsonl`` (call lines +
  a tripwire event line) and ``staging/checkpoints.jsonl`` entries under a
  caller-supplied state dir, for a later timeline-derivation function
  (``lifecycle_flows.derive_timeline``, T015) to consume.
- **R1/FR-008** — ``TransientFaultInjector``: wraps a ``MockMcp`` so one
  designated ``(capability, op)`` fails N times then passes through — the
  FR-008 transient row-write retry stand-in operation contract v1's closed
  error set cannot express directly (follows
  ``doctor_fixtures.FailingProbeInjector``'s wrap-and-pass-through shape).
"""

import json
from pathlib import Path

# Slice-2's real helpers (bin/bb_validate.py, bin/bb_fingerprint.py) —
# importable because tests/conftest.py puts REPO_ROOT/bin on sys.path before
# any test module (and therefore this helper) is collected. Research R3/R4:
# triage validation and fingerprinting always bind to the real helpers,
# never a mock of either.
import bb_fingerprint

from helpers import store_flows

# ---------------------------------------------------------------------------
# Fixture directories (mirrors doctor_fixtures.py's TESTS_DIR/FIXTURES_DIR
# idiom without importing conftest — helper modules stay usable independent
# of the pytest-only conftest module).
# ---------------------------------------------------------------------------

_HELPERS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _HELPERS_DIR.parent
LIFECYCLE_FIXTURES_DIR = _TESTS_DIR / "fixtures" / "lifecycle"
VERDICTS_DIR = LIFECYCLE_FIXTURES_DIR / "verdicts"
SEEDS_DIR = LIFECYCLE_FIXTURES_DIR / "seeds"
CATALOG_PATH = LIFECYCLE_FIXTURES_DIR / "catalog.json"

# R9: the copy source `/close`'s transcript-capture step reads from in tests
# (a stand-in for the runtime's transcript_path hook payload field).
TRANSCRIPT_PATH = LIFECYCLE_FIXTURES_DIR / "transcript.md"


# ---------------------------------------------------------------------------
# R3 — fixture-verdict loaders (tests/fixtures/lifecycle/verdicts/)
# ---------------------------------------------------------------------------


def load_verdict(name):
    """Load a single fixture ``bb.verdict.v1`` document by stem name (e.g.
    ``"valid-known-issue"``, ``"valid-no-signal"``) from
    ``tests/fixtures/lifecycle/verdicts/<name>.json``. Returns the parsed
    document, unvalidated — callers run it through the real
    ``bb_validate.validate()`` themselves; this loader draws no conclusion
    about validity (T002's acceptance is exercised by callers, not baked in
    here)."""
    path = VERDICTS_DIR / "{}.json".format(name)
    with open(str(path), encoding="utf-8") as f:
        return json.load(f)


def load_verdict_candidates(name):
    """Load an ordered re-prompt candidate list from a fixture pair
    directory (``"invalid-then-valid"``, ``"invalid-twice"``) under
    ``tests/fixtures/lifecycle/verdicts/<name>/`` — filename sort order is
    candidate order (``candidates[0]`` the first attempt, ``candidates[1]``
    the one re-prompt), the exact convention
    ``store_flows.write_checkpoint`` already uses for its own ``candidates``
    parameter, so this fixture plugs into that flow unchanged."""
    directory = VERDICTS_DIR / name
    documents = []
    for path in sorted(directory.glob("*.json")):
        with open(str(path), encoding="utf-8") as f:
            documents.append(json.load(f))
    return documents


# ---------------------------------------------------------------------------
# R4 — fixture catalog resolution (tests/fixtures/lifecycle/catalog.json)
# ---------------------------------------------------------------------------


def load_catalog():
    """Load ``tests/fixtures/lifecycle/catalog.json`` — the fixture stand-in
    for slice-7's catalog adapter: ``{"services": [{"name", "owner",
    "runbooks", "dashboards", "alert_matchers", "depends_on"}, ...]}``."""
    with open(str(CATALOG_PATH), encoding="utf-8") as f:
        return json.load(f)


def _fingerprint_for(service_name, alert_type):
    record = bb_fingerprint.fingerprint(service_name, alert_type)
    return record


def _resolution(service_name, catalog_resolved, alert_type, runbooks=None, dashboards=None):
    record = _fingerprint_for(service_name, alert_type)
    return {
        "service": service_name,
        "catalog_resolved": catalog_resolved,
        "fingerprint": record["fingerprint"],
        "fingerprint_record": record,
        "runbooks": list(runbooks or []),
        "dashboards": list(dashboards or []),
    }


def resolve_service(alert, catalog, rung_answers=None):
    """R4: fixture stand-in for slice-7's catalog adapter — walks design
    §5.2's fingerprint service-resolution ladder (D-19) deterministically
    over ``catalog`` (the ``load_catalog()`` shape) against ``alert`` (an
    ``alerting.get_alert`` result's ``"alert"`` field map; ``{}``/``None``
    when the alert fetch itself failed, R15 — the ladder still terminates in
    a fingerprint, never an exception).

    Ladder, rungs 2-4 always set ``catalog_resolved: False`` (never a shared
    sentinel service name, D-19):

    1. **Catalog match** — ``alert["service_hint"]`` against a catalog
       entry's own ``name`` or its ``alert_matchers`` list; first match
       wins. ``catalog_resolved: True``; ``runbooks``/``dashboards`` come
       from that entry.
    2. **Responder-provided name** — ``rung_answers["responder_name"]``, the
       §6.1 confirm-once answer this slice's orchestration (not this
       function) is responsible for collecting on a rung-1 miss.
    3. **The alert's own service/team tag from the alerting tool** —
       ``rung_answers["alert_tag"]`` when a caller wants to simulate a tag
       distinct from ``service_hint`` (test override), else
       ``alert["service_hint"]`` itself used unresolved — no catalog
       membership required at this rung, unlike rung 1.
    4. **Nothing names a service at all** — fingerprint on
       ``normalize(alert_source + rule_name)`` instead of a service name:
       ``rung_answers["alert_source"]``/``rung_answers["rule_name"]``,
       falling back to the alert's own ``alert_id`` and finally a fixed
       placeholder so the ladder always bottoms out.

    Fingerprinting always goes through the real ``bb_fingerprint`` helper
    (D-4), using ``alert["description"]`` as the ``alert_type`` side.
    ``rung_answers`` is caller-injected per T005 (e.g.
    ``{"responder_name": ..., "alert_tag": ...}``) — this function makes no
    orchestration decision about *when* to ask a rung's question, only *how*
    a given answer resolves.

    Returns ``{"service", "catalog_resolved", "fingerprint",
    "fingerprint_record", "runbooks", "dashboards"}``; ``runbooks``/
    ``dashboards`` are empty lists on every non-catalog rung.
    """
    alert = alert or {}
    rung_answers = rung_answers or {}
    service_hint = alert.get("service_hint")
    alert_type = alert.get("description", "")

    # Rung 1 (§5.2 rung 1): catalog match — first hit wins.
    for entry in catalog.get("services", []):
        matchers = entry.get("alert_matchers") or []
        if service_hint is not None and (
            service_hint == entry.get("name") or service_hint in matchers
        ):
            return _resolution(
                entry["name"], True, alert_type,
                entry.get("runbooks"), entry.get("dashboards"),
            )

    # Rung 2 (§5.2 rung 2): responder-provided name.
    responder_name = rung_answers.get("responder_name")
    if responder_name:
        return _resolution(responder_name, False, alert_type)

    # Rung 3 (§5.2 rung 3): the alert's own service/team tag.
    alert_tag = rung_answers.get("alert_tag") or service_hint
    if alert_tag:
        return _resolution(alert_tag, False, alert_type)

    # Rung 4 (§5.2 rung 4): nothing names a service — fingerprint on the
    # alert-rule composite instead.
    composite = "{}{}".format(
        rung_answers.get("alert_source", ""), rung_answers.get("rule_name", "")
    )
    composite = composite or alert.get("alert_id") or "unknown-alert-source"
    return _resolution(composite, False, alert_type)


# ---------------------------------------------------------------------------
# R6 — RecordingShellAdapter / FailingShellAdapter / PrintedOutput
# (slice-9 bb-shell stand-in; §6.3 interface)
# ---------------------------------------------------------------------------


class RecordingShellAdapter:
    """R6: fixture stand-in for slice-9's ``bb-shell`` shim (§6.3) —
    records every call instead of touching a real terminal multiplexer.
    Methods mirror the contracts doc's shell surface exactly:
    ``open_pane``/``navigate_pane``/``notify``/``close_workspace``. Every
    call appends an ordered ``{"method", ...}`` record to ``self.calls``;
    every method also returns a small benign result so flow code can treat
    the return value uniformly whether a live adapter or this fixture is
    behind it."""

    def __init__(self):
        self.calls = []

    def open_pane(self, target, workspace=None):
        self.calls.append(
            {"method": "open_pane", "target": target, "workspace": workspace}
        )
        return {"pane": target, "workspace": workspace}

    def navigate_pane(self, pane, url):
        self.calls.append({"method": "navigate_pane", "pane": pane, "url": url})
        return {"pane": pane, "url": url}

    def notify(self, message, level):
        self.calls.append({"method": "notify", "message": message, "level": level})
        return {"message": message, "level": level}

    def close_workspace(self, session_id):
        self.calls.append({"method": "close_workspace", "session_id": session_id})
        return {"session_id": session_id}


class FailingShellAdapter:
    """R6: mid-flow shell-adapter death — every call raises ``RuntimeError``
    unconditionally, so flow code's fail-soft posture (every shell step
    degrades to a printed record and never fails the whole flow, R6) can be
    driven the same way ``RecordingShellAdapter`` drives the happy path.
    Same method surface as ``RecordingShellAdapter``; no call is ever
    recorded, since none of them succeed."""

    def open_pane(self, target, workspace=None):
        raise RuntimeError("fixture shell adapter: open_pane unreachable (mid-flow death)")

    def navigate_pane(self, pane, url):
        raise RuntimeError("fixture shell adapter: navigate_pane unreachable (mid-flow death)")

    def notify(self, message, level):
        raise RuntimeError("fixture shell adapter: notify unreachable (mid-flow death)")

    def close_workspace(self, session_id):
        raise RuntimeError("fixture shell adapter: close_workspace unreachable (mid-flow death)")


class PrintedOutput:
    """R6 degraded-mode convention: when a flow's ``shell`` argument is
    ``None`` (no adapter configured) there is nothing to call through — the
    documented degraded path is a printed message or link instead (§6.3:
    "every degraded call is a printed link or message"). Flow code appends
    entries here rather than each call site inventing its own ad hoc
    printed-output shape; ``self.entries`` (in append order) is what a flow
    outcome's ``printed``/``printed_links`` field reports."""

    def __init__(self):
        self.entries = []

    def message(self, text):
        entry = {"kind": "message", "text": text}
        self.entries.append(entry)
        return entry

    def link(self, url, label=None):
        entry = {"kind": "link", "url": url}
        if label is not None:
            entry["label"] = label
        self.entries.append(entry)
        return entry


# ---------------------------------------------------------------------------
# T004/T005 — seed loaders (tests/fixtures/lifecycle/seeds/*.json)
# ---------------------------------------------------------------------------


def load_seed_fixture(name):
    """Load a ``tests/fixtures/lifecycle/seeds/<name>.json`` fixture
    verbatim (parsed JSON) — a list of row dicts for the plain multi/single-
    row fixtures (``merge-duplicates``, ``promotion-open-page``,
    ``ownership-displaced``), or the named-variant dict for
    ``join-open-yesterday`` (see ``load_join_seed_variant`` below)."""
    path = SEEDS_DIR / "{}.json".format(name)
    with open(str(path), encoding="utf-8") as f:
        return json.load(f)


def write_seed_rows(mock, rows):
    """Write each row dict in ``rows`` through ``storage.append_record``,
    validating every row's keys are a subset of ``store_flows.COLUMN_NAMES``
    first — schema.md is the one source of truth for column names, so a
    typoed fixture column fails loudly here rather than landing silently in
    the mock's laissez-faire dict store. Returns the list of
    ``append_record`` results, in row order."""
    results = []
    for row in rows:
        unknown = sorted(set(row) - set(store_flows.COLUMN_NAMES))
        if unknown:
            raise ValueError(
                "write_seed_rows: unknown column(s) not in schema.md: %r" % (unknown,)
            )
        results.append(mock.invoke("storage", "append_record", {"record": dict(row)}))
    return results


def write_seed(mock, name):
    """Convenience: ``load_seed_fixture(name)`` + ``write_seed_rows`` in one
    call, for the plain list-shaped fixtures (``merge-duplicates``,
    ``promotion-open-page``, ``ownership-displaced``).
    ``join-open-yesterday`` is named-variant-shaped, not a list — use
    ``load_join_seed_variant`` + ``write_seed_rows([...])`` for it instead."""
    rows = load_seed_fixture(name)
    if not isinstance(rows, list):
        raise ValueError(
            "write_seed: fixture %r is not list-shaped — use "
            "load_join_seed_variant for named-variant fixtures" % (name,)
        )
    return write_seed_rows(mock, rows)


def load_join_seed_variant(variant="base"):
    """``join-open-yesterday.json`` holds two named row variants rather than
    a list (the fixture file's own ``_doc`` entry explains why: writing both
    together would look like a true-race duplicate, not the single open row
    a join test expects). Returns the single row dict for the requested
    variant (``"base"`` or ``"overflow_variant"``) — wrap it in a list for
    ``write_seed_rows``."""
    fixture = load_seed_fixture("join-open-yesterday")
    return fixture[variant]


def seed_join_overflow_artifact(mock):
    """Seeds ``join-open-yesterday.json``'s ``"overflow_artifact"`` entry
    directly into the mock's artifact store (bypassing ``put_file`` and the
    write log) — the same "precondition state, not a scenario write"
    convention ``MockMcp.load_seed`` itself uses for seeded artifacts. Call
    this *before* writing the ``"overflow_variant"`` row so
    ``store_flows.read_latest_checkpoint``'s overflow-follow path actually
    resolves the link instead of raising ``not_found``. Returns the link."""
    fixture = load_seed_fixture("join-open-yesterday")
    artifact = fixture["overflow_artifact"]
    mock.artifacts.files[artifact["link"]] = {
        "name": artifact["name"],
        "content": artifact["content"],
    }
    return artifact["link"]


# ---------------------------------------------------------------------------
# R10 — local-state builders (fixture trace.jsonl + staging/checkpoints.jsonl)
# ---------------------------------------------------------------------------


def write_trace_fixture(state_dir, call_lines=None, tripwire_lines=None):
    """Writes a fixture ``trace.jsonl`` under ``state_dir`` —
    local-state-protocol.md "trace.jsonl" call lines (no ``event`` field)
    plus at least one tripwire event line (``event: "tripwire"``) by
    default, so a later timeline-derivation function
    (``lifecycle_flows.derive_timeline``, T015) has both line types on hand
    to prove it filters/handles them differently (R10: only call lines
    become timeline events). Caller-supplied ``call_lines``/
    ``tripwire_lines`` replace the defaults outright (not merged) — a
    derivation test that cares about exact seq/at ordering supplies its own.
    Returns the full ordered list of line dicts written, in file order."""
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)

    if call_lines is None:
        call_lines = [
            {
                "protocol": "bb.local.v1", "seq": 1, "agent": "agent-fixture",
                "tool": "mycorp_sheets.add_row", "capability": "storage",
                "at": "2026-07-21T09:14:05+00:00",
                "summary": "append_record session_id=page-ALERT-123-2026-07-21",
                "outcome": "ok",
            },
            {
                "protocol": "bb.local.v1", "seq": 2, "agent": "agent-fixture",
                "tool": "mycorp_pager.fetch_alert", "capability": "alerting",
                "at": "2026-07-21T09:14:10+00:00",
                "summary": "get_alert alert_id=al-checkout-latency-p99",
                "outcome": "ok",
            },
        ]
    if tripwire_lines is None:
        tripwire_lines = [
            {
                "protocol": "bb.local.v1", "seq": 3, "event": "tripwire",
                "agent": "agent-fixture", "tool": "mycorp_pager.fetch_alert",
                "at": "2026-07-21T09:14:12+00:00", "matched": "instruction_override",
            },
        ]

    lines = list(call_lines) + list(tripwire_lines)
    trace_path = state_dir / "trace.jsonl"
    with trace_path.open("w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line, sort_keys=True) + "\n")
    return lines


def write_checkpoint_history_fixture(state_dir, entries=None):
    """Writes fixture ``staging/checkpoints.jsonl`` lines (``{"seq": n,
    "document": {...}}``) under ``state_dir/staging/`` — the exact shape
    ``store_flows.write_checkpoint``'s own history step produces (SKILL.md
    "Checkpoints" -> "History"), so a later timeline-derivation function has
    real-shaped checkpoint history on hand without needing a live
    ``write_checkpoint`` call. Returns the list of entries written, in file
    order."""
    state_dir = Path(state_dir)
    staging_dir = state_dir / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    if entries is None:
        entries = [
            {
                "seq": 0,
                "document": {
                    "schema": "bb.verdict.v1",
                    "session_id": "page-ALERT-123-2026-07-21",
                    "at": "2026-07-21T09:14:06+00:00",
                    "phase": "triage-seeded",
                },
            },
            {
                "seq": 1,
                "document": {
                    "schema": "bb.ledger.v1",
                    "seq": 1,
                    "at": "2026-07-21T09:20:00+00:00",
                    "phase": "hypothesis-generation",
                    "hypotheses": [],
                },
            },
        ]

    history_path = staging_dir / "checkpoints.jsonl"
    with history_path.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
    return entries


# ---------------------------------------------------------------------------
# R1/FR-008 — TransientFaultInjector (transient row-write retry stand-in)
# ---------------------------------------------------------------------------

# Operation contract v1's closed error-code set (errors.py ERROR_CODES) has
# no dedicated rate-limit/timeout code — borrows the closed set's
# limit_exceeded rather than inventing a new one (a new code would itself be
# an undocumented contract extension; same discipline
# doctor_fixtures.FailingProbeInjector applies to its own borrowed code).
_DEFAULT_TRANSIENT_CODE = "limit_exceeded"
_DEFAULT_TRANSIENT_MESSAGE = (
    "transient failure (fixture stand-in for FR-008's row-write retry path "
    "— operation contract v1 has no rate-limit/timeout error code; borrows "
    "the closed set's limit_exceeded, see data-model.md 'Fixture surfaces')"
)


class TransientFaultInjector:
    """R1/FR-008: wraps a ``MockMcp`` so one designated ``(capability, op)``
    pair fails with a contract-shaped error envelope for its first
    ``times`` invocations, then passes every subsequent call — including
    further calls to that same op — straight through to the wrapped mock.
    The FR-008 transient row-write retry stand-in operation contract v1's
    closed error set cannot express directly (follows
    ``doctor_fixtures.FailingProbeInjector``'s wrap-and-pass-through
    pattern). Only calls matching the designated pair ever consume the
    failure budget — an unrelated op's calls, or the designated op's own
    calls after the budget is spent, are never affected. Exposes the same
    ``invoke``/``describe`` surface real flow helpers call, and forwards any
    other attribute access (``records``, ``write_log``, ``schema_registry``,
    ...) to the wrapped mock for test inspection."""

    def __init__(
        self,
        mock,
        capability,
        op,
        times=1,
        code=_DEFAULT_TRANSIENT_CODE,
        message=_DEFAULT_TRANSIENT_MESSAGE,
    ):
        self._mock = mock
        self._capability = capability
        self._op = op
        self._remaining = times
        self._code = code
        self._message = message
        self.failures_injected = 0

    def describe(self):
        return self._mock.describe()

    def invoke(self, capability, op, payload=None):
        if capability == self._capability and op == self._op and self._remaining > 0:
            self._remaining -= 1
            self.failures_injected += 1
            return {
                "error": {
                    "op": "{}.{}".format(capability, op),
                    "code": self._code,
                    "message": self._message,
                }
            }
        return self._mock.invoke(capability, op, payload)

    def __getattr__(self, name):
        # Anything not defined on the injector itself (test-inspection
        # surfaces, schema_registry, etc.) passes through to the wrapped
        # mock, exactly as FailingProbeInjector does.
        return getattr(self._mock, name)
