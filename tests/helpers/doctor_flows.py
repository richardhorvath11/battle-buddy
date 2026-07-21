"""The `/doctor` decision protocol's executable form (research R6, R8;
contracts/doctor-protocol.md "Resolution protocol" / "Benign-probe table" /
"Drift re-validation"; spec FR-002/FR-012).

Dev-only: nothing here ships (FR-012, Constitution I) — this module exists solely
so the resolution protocol, the benign-probe table, and drift re-validation can be
*exercised* by hermetic contract tests against ``bb-mock-mcp``, rather than
asserted on prose (Constitution VIII). Each function's steps carry a comment
citing the doctor-protocol.md section it executes, mirroring
``tests/helpers/store_flows.py``'s house style.

This task (T006) delivers the resolution core: ``resolve_bindings``,
``run_probes``, ``revalidate_bindings``. T008 adds the verification checks
(``check_config``, ``check_versions``, ``check_shell``) and report assembly
(``assemble_report`` -> ``bb.doctor.report.v1``). T016 (US3) adds the green
stamp (``bb.stamp.v1``): ``roster_hash``, ``write_stamp``/
``write_stamp_if_green``, ``evaluate_stamp`` (contracts/doctor-protocol.md
"Green stamp"; FR-005).
"""

import hashlib
import json
from pathlib import Path

from helpers import store_flows

# ---------------------------------------------------------------------------
# Shape matching (contracts/doctor-protocol.md "Resolution protocol" step 1)
# ---------------------------------------------------------------------------
#
# Research R8: fixture rosters assign a tool_name -> {"input", "output"} shape
# pulled live from mock.describe() (required half) or the manifest itself
# (optional half — R7 does not extend contract v1 with optional ops). Matching
# is therefore deterministic structural equality between a roster entry's shape
# and the operation's own {"input", "output"} shape — the protocol pins *this*
# comparison, not semantic match quality (that's D-7's live agent-side job).


def _op_shape(op_spec):
    """The {"input", "output"} shape an operation contract entry describes —
    the same two-key shape a roster entry carries (R8)."""
    return {"input": op_spec["input"], "output": op_spec["output"]}


def _candidate_tools(op_spec, roster):
    """Every roster tool whose shape structurally equals the operation's shape
    (contracts/doctor-protocol.md "Resolution protocol" step 1 — "Match"),
    sorted for a deterministic candidate list."""
    expected = _op_shape(op_spec)
    return sorted(tool_name for tool_name, shape in roster.items() if shape == expected)


def _lookup_op_spec(manifest, capability, op):
    """Find a (capability, op)'s manifest entry in either half — required or
    optional — or ``None`` if the manifest no longer declares it (drift
    re-validation needs this to re-derive the expected shape; see
    ``revalidate_bindings``)."""
    for section in ("required", "optional"):
        cap_block = manifest.get(section, {}).get(capability)
        if cap_block and op in cap_block.get("ops", {}):
            return cap_block["ops"][op]
    return None


# ---------------------------------------------------------------------------
# resolve_bindings (contracts/doctor-protocol.md "Resolution protocol")
# ---------------------------------------------------------------------------


def _resolve_one(capability, op, op_spec, roster, choices, required):
    """One operation through resolution protocol steps 2-5. Returns
    ``(binding_entry_or_None, check_or_None)`` — ``check`` is ``None`` only for
    an unresolved *optional* op (a missing optional op yields no fail check;
    reduced-features derivation from that gap is left to T008's report
    assembly, which has the manifest's ``enables`` lists to hand)."""
    key = "{}.{}".format(capability, op)
    check_id = "binding.{}".format(key)
    candidates = _candidate_tools(op_spec, roster)

    if not candidates:
        # Step 2: zero candidates.
        if not required:
            return None, None
        return None, {
            "id": check_id,
            "kind": "binding",
            "capability": capability,
            "op": op,
            "status": "fail",
            "detail": "no roster tool satisfies {} — required operation unresolved".format(
                key
            ),
        }

    if len(candidates) > 1:
        # Step 3: more than one candidate -> ambiguous, unless an explicit,
        # *valid* choice (one of the candidates) was supplied — an invalid
        # choice (not among candidates) must not silently bind, so it falls
        # through to the same ambiguous outcome as no choice at all.
        choice = choices.get(key)
        if choice is not None and choice in candidates:
            return choice, {
                "id": check_id,
                "kind": "binding",
                "capability": capability,
                "op": op,
                "status": "ok",
                "detail": "explicit choice {!r} recorded among candidates {!r}".format(
                    choice, candidates
                ),
            }
        return None, {
            "id": check_id,
            "kind": "binding",
            "capability": capability,
            "op": op,
            "status": "ambiguous",
            "detail": "multiple candidates satisfy {} — explicit choice required".format(
                key
            ),
            "candidates": candidates,
        }

    # Step 4/5: exactly one candidate -> resolved. (Probe/schema-match
    # confirmation of *this* candidate is run_probes'/setup's job, not this
    # step's — see contracts/doctor-protocol.md step 4's split between
    # read-shaped probes and mutating-op schema match.)
    tool_name = candidates[0]
    return tool_name, {
        "id": check_id,
        "kind": "binding",
        "capability": capability,
        "op": op,
        "status": "ok",
        "detail": "resolved to {}".format(tool_name),
    }


def resolve_bindings(manifest, roster, choices=None):
    """contracts/doctor-protocol.md "Resolution protocol", executed per
    required operation in ``manifest["required"]`` (iterated in stable sorted
    order over capabilities then ops) and, additionally, per optional
    operation in ``manifest["optional"]`` when the roster happens to satisfy
    it (same per-op protocol; a missing optional op is silent — no fail
    check, per FR-004's "optional capability missing -> green run").

    ``choices``: optional ``{"<cap>.<op>": tool_name}`` map supplying an
    explicit pick for an ambiguous op (step 3) — never consulted, and never
    required, when there is exactly one candidate.

    Returns ``(bindings, checks)``: ``bindings`` is a
    ``"<capability>.<operation>" -> tool_name`` map in the protocol-v1 entry
    format (contracts/doctor-protocol.md "Binding map"); ``checks`` is the
    list of ``binding``-kind check dicts (one per operation considered, minus
    the silent optional-missing case) this step produces.
    """
    choices = choices or {}
    bindings = {}
    checks = []

    for section, required in (("required", True), ("optional", False)):
        cap_block = manifest.get(section, {})
        for capability in sorted(cap_block):
            ops = cap_block[capability].get("ops", {})
            for op in sorted(ops):
                entry, check = _resolve_one(
                    capability, op, ops[op], roster, choices, required
                )
                if entry is not None:
                    bindings["{}.{}".format(capability, op)] = entry
                if check is not None:
                    checks.append(check)

    return bindings, checks


# ---------------------------------------------------------------------------
# run_probes (contracts/doctor-protocol.md "Benign-probe table", research R6)
# ---------------------------------------------------------------------------

# Literal invocation payloads from the probe table — read-shaped ops only.
# artifacts has no read-shaped entry op (schema-match-only at doctor time; see
# below).
_PROBE_TABLE = (
    ("storage", "read_records", {"filter": {"session_id": "bb-doctor-probe"}}),
    ("diary", "read_recent", {"n": 1}),
    ("alerting", "list_alert_history", {"filter": {"alert_id": "bb-doctor-probe"}}),
)


def run_probes(mock):
    """contracts/doctor-protocol.md "Benign-probe table", run against ``mock``
    (a ``MockMcp`` instance, or any wrapper exposing the same ``invoke``
    surface — e.g. ``doctor_fixtures.FailingProbeInjector``, standing in for a
    responder-credential failure on one capability).

    Empty results pass (call succeeded; the table never asserts on data
    presence). An error envelope from ``mock.invoke`` fails the probe, with
    the envelope's ``message`` recorded in ``detail``. ``artifacts`` has no
    read-shaped entry op, so it gets a ``skip`` check recording
    schema-match-only instead of a probe call.

    Returns the list of ``probe``-kind check dicts, one per capability in the
    table (four total: storage, diary, alerting, artifacts).
    """
    checks = []
    for capability, op, payload in _PROBE_TABLE:
        result = mock.invoke(capability, op, payload)
        check_id = "probe.{}".format(capability)
        if isinstance(result, dict) and "error" in result:
            checks.append(
                {
                    "id": check_id,
                    "kind": "probe",
                    "capability": capability,
                    "status": "fail",
                    "detail": result["error"].get("message"),
                }
            )
        else:
            checks.append(
                {
                    "id": check_id,
                    "kind": "probe",
                    "capability": capability,
                    "status": "ok",
                    "detail": "{}.{} call succeeded".format(capability, op),
                }
            )

    checks.append(
        {
            "id": "probe.artifacts",
            "kind": "probe",
            "capability": "artifacts",
            "status": "skip",
            "detail": (
                "artifacts has no read-shaped entry op — schema-match-only at "
                "doctor time (exercised end-to-end by setup's smoke test)"
            ),
        }
    )
    return checks


# ---------------------------------------------------------------------------
# revalidate_bindings (contracts/doctor-protocol.md "Drift re-validation")
# ---------------------------------------------------------------------------


def revalidate_bindings(bindings, roster, manifest):
    """contracts/doctor-protocol.md "Drift re-validation": re-check each
    already-committed ``bindings`` entry against the current ``roster``
    surface. ``manifest`` supplies the operation's expected shape (looked up
    in either half) so a tool that is still *present* but no longer
    shape-compatible with the bound operation is caught too, not just an
    outright-removed tool name.

    An entry whose tool name is absent from ``roster``, or whose current
    shape no longer matches the bound operation, is flagged stale by name
    (``fail``, ``detail`` naming the stale entry and tool) — never silently
    rewritten (this function returns checks only; it never mutates
    ``bindings``). A still-valid entry checks ``ok``.

    Returns the list of ``binding``-kind check dicts, one per entry in
    ``bindings`` (iterated in sorted key order for determinism).
    """
    checks = []
    for key in sorted(bindings):
        capability, op = key.split(".", 1)
        tool_name = bindings[key]
        check_id = "binding.{}".format(key)

        if tool_name not in roster:
            checks.append(
                {
                    "id": check_id,
                    "kind": "binding",
                    "capability": capability,
                    "op": op,
                    "status": "fail",
                    "detail": (
                        "stale binding: {} -> {!r} no longer present in the "
                        "roster".format(key, tool_name)
                    ),
                }
            )
            continue

        op_spec = _lookup_op_spec(manifest, capability, op)
        if op_spec is not None and roster[tool_name] != _op_shape(op_spec):
            checks.append(
                {
                    "id": check_id,
                    "kind": "binding",
                    "capability": capability,
                    "op": op,
                    "status": "fail",
                    "detail": (
                        "stale binding: {} -> {!r} is no longer shape-compatible "
                        "with the bound operation".format(key, tool_name)
                    ),
                }
            )
            continue

        checks.append(
            {
                "id": check_id,
                "kind": "binding",
                "capability": capability,
                "op": op,
                "status": "ok",
                "detail": "{} still resolves to {}".format(key, tool_name),
            }
        )
    return checks


# ---------------------------------------------------------------------------
# check_config (contracts/doctor-protocol.md "Config block", "Store header
# create-vs-validate", "Benign-probe table" diary row) — T008
# ---------------------------------------------------------------------------
#
# JUDGMENT CALL — malformed-config representation: no function in this module
# ever parses JSON itself (``resolve_bindings``/``revalidate_bindings`` take
# already-loaded ``manifest``/``roster``/``bindings`` dicts, never paths).
# ``check_config`` keeps that shape: ``config`` is either the parsed
# ``bb.config.v1`` dict, or the parse-error object a caller caught while
# loading it (``doctor_fixtures.load_config_fixture`` raises
# ``json.JSONDecodeError`` unchanged for the T005 malformed fixture — a
# caller catches that and passes the exception straight through as
# ``config``, e.g. ``try: config = load_config_fixture(...); except
# json.JSONDecodeError as exc: config = exc``). Anything that isn't a
# ``dict`` is the malformed sentinel; ``str(config)`` names the parse error
# in the fail detail. This avoids a second, possibly-drifting JSON-parsing
# codepath inside doctor_flows itself — the malformed case is a repair case,
# never treated as absent (contracts/doctor-protocol.md "Malformed config
# block").

# Header representation authority (research R5): schema.md column order,
# then the bb.schema.v1 sentinel one column past the last schema column.
# Constructed independently from store_flows directly (this module never
# imports doctor_fixtures — a dev fixtures module has no business being a
# dependency of the flow-protocol module) but by the exact same authority
# chain doctor_fixtures.EXPECTED_HEADER uses, so the two can never disagree;
# test_doctor_fixtures.py already pins doctor_fixtures.EXPECTED_HEADER's
# shape against store_flows, and the contract tests here cross-check both
# constants agree.
_EXPECTED_HEADER = list(store_flows.COLUMN_NAMES) + [store_flows.SCHEMA_VERSION]


def _header_mismatch_detail(actual, expected):
    """contracts/doctor-protocol.md "Store header create-vs-validate": names
    the exact mismatch between an existing store's header cells and the
    expected ones — missing columns, extra columns, order deviations among
    the columns present in both, and a wrong/missing sentinel cell — in one
    human-readable detail string. Returns ``None`` when there is no
    mismatch (``actual == expected``, cell for cell)."""
    actual = list(actual)
    if actual == expected:
        return None

    expected_columns = expected[:-1]
    expected_sentinel = expected[-1]
    actual_columns = actual[:-1] if actual else []
    actual_sentinel = actual[-1] if actual else None

    missing = [c for c in expected_columns if c not in actual_columns]
    extra = [c for c in actual_columns if c not in expected_columns]

    shared_expected_order = [c for c in expected_columns if c in actual_columns]
    shared_actual_order = [c for c in actual_columns if c in expected_columns]

    parts = []
    if missing:
        parts.append("missing column(s) {!r}".format(missing))
    if extra:
        parts.append("extra column(s) {!r}".format(extra))
    if shared_expected_order != shared_actual_order:
        parts.append(
            "column order deviates from schema.md (expected order among "
            "shared columns {!r}, found {!r})".format(
                shared_expected_order, shared_actual_order
            )
        )
    if actual_sentinel != expected_sentinel:
        parts.append(
            "wrong/missing sentinel cell (expected {!r}, found {!r})".format(
                expected_sentinel, actual_sentinel
            )
        )
    if not parts:
        # Defensive: actual != expected overall but none of the specific
        # checks above fired (e.g. a duplicate column) — still name it
        # specifically, never silently.
        parts.append(
            "header {!r} does not match expected {!r}".format(actual, expected)
        )

    return "store header mismatch: " + "; ".join(parts)


def _check_config_wellformed(config):
    """contracts/doctor-protocol.md "Config block" -> "Malformed config
    block": a config block that failed to parse is an explicit repair case,
    named by its parse error — never treated as absent."""
    if isinstance(config, dict):
        return {
            "id": "config.wellformed",
            "kind": "config",
            "status": "ok",
            "detail": "config block parses as a JSON object",
        }
    return {
        "id": "config.wellformed",
        "kind": "config",
        "status": "fail",
        "detail": (
            "config block failed to parse: {} — repair case, never treated "
            "as absent".format(config)
        ),
    }


def _check_store_header(header_store):
    """contracts/doctor-protocol.md "Store header create-vs-validate", the
    doctor-side half — setup's create path owns the empty-store write
    (T012); doctor only ever reads. Zero writes ever: only
    ``header_store.read_header()`` is called."""
    header = header_store.read_header()
    if header is None:
        return {
            "id": "config.store_header",
            "kind": "config",
            "status": "fail",
            "detail": (
                "store empty/header missing — setup's create path owns "
                "creation; doctor only validates"
            ),
        }
    mismatch = _header_mismatch_detail(header, _EXPECTED_HEADER)
    if mismatch is not None:
        return {
            "id": "config.store_header",
            "kind": "config",
            "status": "fail",
            "detail": mismatch,
        }
    return {
        "id": "config.store_header",
        "kind": "config",
        "status": "ok",
        "detail": "store header matches schema.md column order + bb.schema.v1 sentinel",
    }


def _check_diary(mock):
    """contracts/doctor-protocol.md "Benign-probe table" (diary row):
    readability via the same ``read_recent`` probe payload ``run_probes``
    uses. ``append_entry`` is schema-matched, not probed (a mutating op —
    the benign-probe table only exercises read-shaped ops); that
    schema-matched status is recorded in this check's ok-case detail rather
    than as a separate check, per FR-003's "diary readable ... with its
    append operation schema-matched" phrasing."""
    result = mock.invoke("diary", "read_recent", {"n": 1})
    if isinstance(result, dict) and "error" in result:
        return {
            "id": "config.diary",
            "kind": "config",
            "status": "fail",
            "detail": "diary read_recent failed: {}".format(
                result["error"].get("message")
            ),
        }
    return {
        "id": "config.diary",
        "kind": "config",
        "status": "ok",
        "detail": (
            "diary readable (read_recent succeeded); append_entry is "
            "schema-matched, not probed (mutating op)"
        ),
    }


def check_catalog(catalog_path):
    """contracts/doctor-protocol.md "Config block" (catalog row) +
    data-model.md "Fixture surfaces" ("Fixture catalog repo path (parseable
    / not)").

    JUDGMENT CALL — catalog fixture shape: no existing ``tests/fixtures/``
    scenario surface models a catalog repo (design §6.1's file-mode Backstage
    ``catalog-info.yaml`` parsing is slice 7's scope, not this slice's); this
    slice only proves the parseable/not axis data-model.md pins. Rather than
    introduce a YAML dependency this slice doesn't otherwise need,
    ``catalog_path`` points at a plain JSON fixture file
    (``tests/fixtures/doctor/catalog-valid.json`` / ``catalog-broken.json`` —
    a minimal Backstage-shaped entry vs. deliberately truncated garbage,
    mirroring the T005 config-fixture convention). ``config["catalog"]
    ["repo"]`` (a repo slug in the real config block, e.g.
    ``"mycorp/service-catalog"``) is not read here — ``catalog_path`` is the
    fixture stand-in a caller resolves separately, mirroring how
    ``header_store`` stands in for a live store surface contract v1 has no
    header concept for.
    """
    path = Path(catalog_path)
    try:
        text = path.read_text(encoding="utf-8")
        json.loads(text)
    except (OSError, ValueError) as exc:
        return {
            "id": "config.catalog",
            "kind": "config",
            "status": "fail",
            "detail": "catalog repo not parseable at {}: {}".format(path, exc),
        }
    return {
        "id": "config.catalog",
        "kind": "config",
        "status": "ok",
        "detail": "catalog repo parseable at {}".format(path),
    }


def check_config(mock, config, header_store, catalog_path):
    """contracts/doctor-protocol.md "Config block" + "Store header
    create-vs-validate" + "Benign-probe table" (diary row) — FR-003's
    config-validity bullet, executed as one step.

    Returns the four ``config``-kind checks in a stable order: config-block
    well-formedness, store-header validate, diary readability, catalog
    parseability. All four always run — ``header_store``/``catalog_path`` are
    supplied directly by the caller (fixture plumbing standing in for live
    surfaces contract v1 has no concept of), never derived from ``config``
    itself, so a malformed config block (never treated as absent) doesn't
    block the other three from being exercised too.
    """
    return [
        _check_config_wellformed(config),
        _check_store_header(header_store),
        _check_diary(mock),
        check_catalog(catalog_path),
    ]


# ---------------------------------------------------------------------------
# check_versions (contracts/doctor-protocol.md "Version-seam compatibility
# (v1)", research R11/R14) — T008
# ---------------------------------------------------------------------------

_EXPECTED_CONFIG_VERSION = "bb.config.v1"
_EXPECTED_SCHEMA_VERSION = "bb.schema.v1"

_MIGRATION_REMEDY = "run /setup --migrate"


def _migration_string(artifact, found, expected):
    """contracts/doctor-protocol.md "Version-seam compatibility (v1)": the
    exact migration-string format, ``"<artifact> <found-version> →
    <expected-version>: <remedy>"`` — direction is found-version first (what
    is currently on disk) then expected-version (what this installed plugin
    needs), matching the contract doc's own worked example verbatim
    (``"config block bb.config.v2 → bb.config.v1: run /setup --migrate"``)."""
    return "{} {} → {}: {}".format(artifact, found, expected, _MIGRATION_REMEDY)


def check_versions(config, plugin_version):
    """contracts/doctor-protocol.md "Version-seam compatibility (v1)"
    (research R11): exact-match comparisons — ``config["configVersion"]`` vs
    ``bb.config.v1``, and ``config["store"]["schemaVersion"]`` vs
    ``bb.schema.v1``. A mismatch is a ``fail`` whose ``detail`` is the exact
    migration string (see ``_migration_string``); a match is ``ok``.

    ``plugin_version`` is threaded through per research R14 ("every flow
    takes ``plugin_version`` as an explicit input" rather than reading the
    in-tree plugin manifest that doesn't exist until slice 5+ ships the
    bundle) and recorded in the ok-case detail. JUDGMENT CALL: until a second
    ``bb.config``/``bb.schema`` version exists, ``plugin_version`` never
    changes *which* version is expected — R11 explicitly defers migration
    execution "until a second version exists", so there is nothing yet for
    it to select between. It is accepted and recorded now so call sites
    never need a signature change when that second version lands.

    Gracefully handles a still-malformed ``config`` (not a ``dict`` — the
    well-formedness check is ``check_config``'s job, not this one's) by
    failing both seam checks rather than raising, naming the block as
    unparsed instead of crashing on a missing key.
    """
    if not isinstance(config, dict):
        detail = (
            "config block failed to parse — version seam cannot be checked "
            "until repaired"
        )
        return [
            {
                "id": "version.config",
                "kind": "version",
                "status": "fail",
                "detail": detail,
            },
            {
                "id": "version.store_schema",
                "kind": "version",
                "status": "fail",
                "detail": detail,
            },
        ]

    checks = []

    found_config_version = config.get("configVersion")
    if found_config_version == _EXPECTED_CONFIG_VERSION:
        checks.append(
            {
                "id": "version.config",
                "kind": "version",
                "status": "ok",
                "detail": "config block {} matches plugin {}'s expected {}".format(
                    found_config_version, plugin_version, _EXPECTED_CONFIG_VERSION
                ),
            }
        )
    else:
        checks.append(
            {
                "id": "version.config",
                "kind": "version",
                "status": "fail",
                "detail": _migration_string(
                    "config block", found_config_version, _EXPECTED_CONFIG_VERSION
                ),
            }
        )

    found_schema_version = (config.get("store") or {}).get("schemaVersion")
    if found_schema_version == _EXPECTED_SCHEMA_VERSION:
        checks.append(
            {
                "id": "version.store_schema",
                "kind": "version",
                "status": "ok",
                "detail": "store schema {} matches plugin {}'s expected {}".format(
                    found_schema_version, plugin_version, _EXPECTED_SCHEMA_VERSION
                ),
            }
        )
    else:
        checks.append(
            {
                "id": "version.store_schema",
                "kind": "version",
                "status": "fail",
                "detail": _migration_string(
                    "store schema", found_schema_version, _EXPECTED_SCHEMA_VERSION
                ),
            }
        )

    return checks


# ---------------------------------------------------------------------------
# check_shell (contracts/doctor-protocol.md "Config block" shell row,
# research R12) — T008
# ---------------------------------------------------------------------------


def check_shell(config, adapter):
    """contracts/doctor-protocol.md "shell" check: the ``bb-shell notify``
    round-trip when a shell adapter is configured, skipped-not-failed
    otherwise (FR-003).

    Skip condition (either half absent): ``config`` has no ``"shell"`` key,
    or ``adapter`` is ``None`` — ``doctor_fixtures.FixtureShellAdapter``'s own
    docstring pins this: absence of a configured adapter is represented by
    passing ``None`` where an adapter is expected, never a third instance
    state. Otherwise: ``adapter.notify`` round-trips the probe message ->
    ``ok``; raises (or fails to echo it back) -> ``fail``.
    """
    if not isinstance(config, dict) or "shell" not in config or adapter is None:
        return {
            "id": "shell.notify",
            "kind": "shell",
            "status": "skip",
            "detail": "no shell adapter configured — skipped, not failed",
        }

    probe_message = "bb-doctor-probe"
    try:
        echoed = adapter.notify(probe_message)
    except Exception as exc:  # any adapter failure is a doctor "fail"
        return {
            "id": "shell.notify",
            "kind": "shell",
            "status": "fail",
            "detail": "shell notify round-trip failed: {}".format(exc),
        }

    if echoed != probe_message:
        return {
            "id": "shell.notify",
            "kind": "shell",
            "status": "fail",
            "detail": "shell notify did not round-trip: sent {!r}, got {!r}".format(
                probe_message, echoed
            ),
        }

    return {
        "id": "shell.notify",
        "kind": "shell",
        "status": "ok",
        "detail": "shell notify round-trip confirmed",
    }


# ---------------------------------------------------------------------------
# assemble_report (contracts/doctor-protocol.md "Doctor report") — T008
# ---------------------------------------------------------------------------


def assemble_report(
    binding_checks,
    probe_checks,
    config_checks,
    version_checks,
    shell_check,
    manifest,
    bindings,
):
    """contracts/doctor-protocol.md "Doctor report" (``bb.doctor.report.v1``).

    Assembles every check family this module's other functions produce
    (``resolve_bindings``/``revalidate_bindings``, ``run_probes``,
    ``check_config``, ``check_versions``, ``check_shell``) into the single
    structured artifact FR-004 pins, in stable kind order: binding, probe,
    config, version, shell.

    Outcome rule (contracts/doctor-protocol.md "Doctor report" -> "Outcome
    rule"): ``red`` iff any check has status ``fail`` or ``ambiguous``
    **except** ``binding``/``probe`` checks belonging to an *optional*
    capability — optional capabilities never affect outcome. A zero-candidate
    optional op produces no check at all, but an optional **multi-match**
    does emit an ``ambiguous`` check (surfaced for a later explicit choice);
    that check must not red the run — the capability appears in
    ``reduced_features`` iff none of its ops resolved (rule below).
    ``config``/``version``/``shell``
    failures always red (a *configured* shell adapter failing its round-trip
    is a real fault; an unconfigured one is ``skip``).

    ``bindings`` (the resolved ``capability.operation -> tool_name`` map) is
    an *input*, used only to compute ``reduced_features`` below.
    JUDGMENT CALL: it is not written back out under its own top-level key in
    the returned report — contracts/doctor-protocol.md's own
    ``bb.doctor.report.v1`` JSON example and data-model.md's "Doctor report"
    entry both name exactly ``{schema, outcome, checks, reduced_features,
    migrations}`` as the report's fields; the resolved binding map is a
    *config-block* artifact (the contract doc's separate "Binding map"
    section — ``battleBuddy.bindings``), not a report field.

    ``reduced_features`` / partial-optional-resolution rule (judgment call):
    an optional capability counts as "missing" — and gets one
    ``reduced_features`` entry naming its manifest ``enables`` list verbatim
    — iff **none** of its ops appear in ``bindings``. A capability with at
    least one resolved op is not reported as reduced, even if other ops of
    that same capability remain unresolved; a finer per-op reduction model is
    out of this slice's (and the manifest schema's — ``enables`` is a
    whole-capability list) scope.

    ``migrations`` mirrors every ``version``-kind check's failure detail
    verbatim, in ``version_checks`` order.
    """
    checks = (
        list(binding_checks)
        + list(probe_checks)
        + list(config_checks)
        + list(version_checks)
    )
    if shell_check is not None:
        checks.append(shell_check)

    optional_caps = set(manifest.get("optional", {}))

    def _affects_outcome(check):
        if check["status"] not in ("fail", "ambiguous"):
            return False
        # Optional-capability binding/probe checks never red the run
        # (contracts/doctor-protocol.md "Outcome rule").
        if check.get("kind") in ("binding", "probe"):
            return check.get("capability") not in optional_caps
        return True

    red = any(_affects_outcome(c) for c in checks)
    outcome = "red" if red else "green"

    reduced_features = []
    for capability in sorted(manifest.get("optional", {})):
        cap_block = manifest["optional"][capability]
        ops = cap_block.get("ops", {})
        resolved_any = any("{}.{}".format(capability, op) in bindings for op in ops)
        if not resolved_any:
            reduced_features.append(
                {
                    "capability": capability,
                    "disabled": list(cap_block.get("enables", [])),
                }
            )

    migrations = [c["detail"] for c in version_checks if c["status"] == "fail"]

    return {
        "schema": "bb.doctor.report.v1",
        "outcome": outcome,
        "checks": checks,
        "reduced_features": reduced_features,
        "migrations": migrations,
    }


# ---------------------------------------------------------------------------
# Green stamp (bb.stamp.v1) (contracts/doctor-protocol.md "Green stamp";
# spec FR-005, SC-006, US3 scenarios 2-3) — T016
# ---------------------------------------------------------------------------
#
# FR-005 is owned entirely by this section: a green doctor run writes the
# local, never-committed stamp; both standalone `/doctor` and team-mode's
# `setup_flows.team_mode` (its doctor step, US1's finish) call
# ``write_stamp_if_green`` here rather than each re-implementing the gate.

_STAMP_SCHEMA = "bb.stamp.v1"


def roster_hash(roster_file_text):
    """contracts/doctor-protocol.md "Green stamp" -> "Roster hash": the first
    16 hex characters of a SHA-256 over the canonical JSON serialization
    (sorted keys, compact ``,``/``:`` separators, UTF-8) of the *parsed*
    roster file text's ``"mcpServers"`` map.

    ``roster_file_text``: the exact text of a workspace's ``.mcp.json`` (or
    any roster file sharing that shape) — a ``str``, never a path or an
    already-parsed dict; this function owns the parse so canonicalization is
    always computed over the same freshly-loaded structure, never a caller's
    possibly-differently-ordered in-memory dict.

    ``${ENV_VAR}`` references inside the text are hashed as the literal
    strings they are — this function never resolves them (no environment
    access at all), matching the contract's "never a resolved secret".
    Canonicalization (``sort_keys=True``) makes the hash key-order-insensitive
    at every nesting level, so two texts differing only in (nested) key order
    hash identically — the roster's *content*, not its serialization, is what
    staleness tracks.

    A roster file with no ``"mcpServers"`` key hashes an empty map (``{}``)
    rather than raising — callers that care to distinguish "no roster at all"
    do so before calling this function.
    """
    parsed = json.loads(roster_file_text)
    mcp_servers = parsed.get("mcpServers", {}) if isinstance(parsed, dict) else {}
    canonical = json.dumps(mcp_servers, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest[:16]


def write_stamp(path, plugin_version, roster_hash_value, at):
    """contracts/doctor-protocol.md "Green stamp" -> "Shape": writes
    ``{"schema": "bb.stamp.v1", "at": at, "plugin_version": plugin_version,
    "roster_hash": roster_hash_value}`` as JSON to ``path``, unconditionally
    (the green-outcome gate is ``write_stamp_if_green``'s job, not this
    function's — every caller that only ever wants to write on green should
    call that one instead).

    ``at``: an ISO 8601 string supplied by the caller (hermetic — this
    function never reads the wall clock; mirrors how ``store_flows``'s own
    flows take their dates as explicit inputs). Returns the stamp dict
    written.
    """
    stamp = {
        "schema": _STAMP_SCHEMA,
        "at": at,
        "plugin_version": plugin_version,
        "roster_hash": roster_hash_value,
    }
    Path(path).write_text(
        json.dumps(stamp, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return stamp


def write_stamp_if_green(report, path, plugin_version, roster_hash_value, at):
    """FR-005's gate: writes the stamp (via ``write_stamp``) iff
    ``report["outcome"] == "green"``; a non-green report writes nothing.
    Returns whether it wrote.

    This is the single owner of "only write on green" — both a standalone
    `/doctor` run and ``setup_flows.team_mode``'s doctor step call exactly
    this function (never ``write_stamp`` directly) so the gate can never
    drift between the two call sites.
    """
    if report.get("outcome") != "green":
        return False
    write_stamp(path, plugin_version, roster_hash_value, at)
    return True


def evaluate_stamp(path, plugin_version, current_roster_hash):
    """contracts/doctor-protocol.md "Green stamp" -> "Staleness": the sole
    v1 rules — stale iff the stamp file is missing/unparseable/not
    ``bb.stamp.v1``-shaped, or ``plugin_version`` differs, or
    ``roster_hash`` differs from ``current_roster_hash``. ``at`` is
    diagnostic only and is **never** consulted here — no time-based
    expiry (a time window would reintroduce 3am probes).

    Returns ``(status, reason)`` where ``status`` is ``"fresh"`` or
    ``"stale"`` and ``reason`` is a human-readable detail (mirroring this
    module's ``check``-dict ``detail`` convention, without inventing a third
    return shape just for this one function).
    """
    path = Path(path)

    if not path.exists():
        return "stale", "stamp file missing at {}".format(path)

    try:
        text = path.read_text(encoding="utf-8")
        stamp = json.loads(text)
    except (OSError, ValueError) as exc:
        return "stale", "stamp file unparseable at {}: {}".format(path, exc)

    if not isinstance(stamp, dict) or stamp.get("schema") != _STAMP_SCHEMA:
        found = stamp.get("schema") if isinstance(stamp, dict) else stamp
        return "stale", "stamp schema mismatch: expected {!r}, found {!r}".format(
            _STAMP_SCHEMA, found
        )

    if stamp.get("plugin_version") != plugin_version:
        return "stale", (
            "stamp plugin_version {!r} does not match installed plugin "
            "{!r}".format(stamp.get("plugin_version"), plugin_version)
        )

    if stamp.get("roster_hash") != current_roster_hash:
        return "stale", (
            "stamp roster_hash {!r} does not match current roster_hash "
            "{!r}".format(stamp.get("roster_hash"), current_roster_hash)
        )

    return "fresh", (
        "stamp matches installed plugin_version and current roster_hash "
        "(at={!r} is diagnostic only, never expiry-checked)".format(stamp.get("at"))
    )
