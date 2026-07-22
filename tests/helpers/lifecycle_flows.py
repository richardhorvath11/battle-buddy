"""`/page`'s (and, forward, `/incident`/`/close`'s) executable specification
(spec FR-001/FR-002/FR-004/FR-005/FR-006; contracts/lifecycle-protocol.md
"Preflight decision table", "Open-flow order", "Marker lifecycle",
"Join-vs-separate", "Briefing artifact"; research R1, R2, R4, R6, R8, R11,
R14, R15, R16, R17).

Dev-only: nothing here ships (FR-013, Constitution I) — this module composes
the existing slice-3/4 helpers (``store_flows``, ``doctor_flows``,
``setup_flows``) plus this slice's own fixture stand-ins
(``lifecycle_fixtures``) into the two flow functions the `/page` command
document restates in prose: ``preflight`` and ``open_command``. Each
function's steps carry a comment citing the contracts-doc section they
execute, mirroring ``store_flows.py``/``setup_flows.py``'s own house style.

**Reuse boundary (R1)**: this module never calls ``store_flows.open_session``
— that helper writes the marker once, at the end, over a plain row; the
lifecycle open needs the marker written early (``open_write_confirmed:
false``, before any store activity) with the triage verdict riding the very
same append (R2). Instead, ``open_command`` composes the lower primitives
directly: ``store_flows.retrieve_candidates``, ``store_flows.parse_source_id``
(via ``store_flows.detect_open_session``), ``store_flows._serialize_checkpoint``,
``store_flows.build_row``, ``store_flows.COLUMN_NAMES``, and the real
``bb_validate`` (reached through ``store_flows.bb_validate`` — the module
already imports it, so this file doesn't need a second top-level import of
the same real validator).

**JUDGMENT CALL — responder-mode auto-run is caller-injectable (R11, T007)**:
``preflight``'s row 5 (stamp missing/stale) needs to auto-run
``setup_flows.responder_mode``, which itself needs a fully-wired
``setup_flows.Workspace`` (header_store, catalog_path, roster,
roster_file_text) — none of which `/page`'s preflight has any business
constructing itself (that wiring is team/responder-scope *setup* concern,
not a page-open decision). Rather than have ``preflight`` build a Workspace
inline (disproportionate — it would make a "cheap, zero-probe" decision
function depend on the entire setup-flow object graph), the auto-run is a
caller-injected zero-arg callable: ``responder_mode_fn``. Every current
caller/test builds it via ``default_responder_mode_fn`` below, a thin
wrapper binding ``setup_flows.responder_mode``'s four arguments into that
zero-arg shape; a real command implementation would do exactly the same,
constructing its own ``Workspace`` once and closing over it.

**JUDGMENT CALL — briefing claims come from ``candidates`` with evidence,
never from a bare ``known_issue`` (R16, Constitution IV)**: ``bb.verdict.v1``
(``bin/bb_validate.py``) never requires (or even shapes) an ``evidence`` list
on ``known_issue`` — only ``validation``. Since every briefing claim must
carry >=1 non-empty ``{url, excerpt}`` pair, a claim is built only from a
``candidates[]`` entry that itself carries a ``statement`` and a non-empty,
well-formed ``evidence`` list; a candidate lacking either contributes no
claim at all (skipped, never an unevidenced claim promoted to satisfy a
count). This keeps Constitution IV's invariant true *by construction* rather
than by hoping every fixture happens to comply. Briefing *content and
format* beyond these structural properties remain slice 6's
(``references/briefing.md``) — this module only pins what
contracts/lifecycle-protocol.md's ``bb.briefing.v1`` normatively requires.
"""

import json
import shutil
from pathlib import Path

from helpers import doctor_flows, lifecycle_fixtures, setup_flows, store_flows

# ---------------------------------------------------------------------------
# preflight (contracts/lifecycle-protocol.md "Preflight decision table";
# FR-001; research R8, R11)
# ---------------------------------------------------------------------------


def _preflight_outcome(proceed, stopped_reason, responder_mode_ran, marker_state, stamp_state):
    return {
        "proceed": proceed,
        "stopped_reason": stopped_reason,
        "responder_mode_ran": responder_mode_ran,
        "marker_state": marker_state,
        "stamp_state": stamp_state,
    }


def default_responder_mode_fn(mock, workspace, plugin_version, at):
    """R11/T007's caller-injectable default: binds
    ``setup_flows.responder_mode``'s four arguments into the zero-arg
    callable ``preflight``'s ``responder_mode_fn`` parameter expects. See the
    module docstring's judgment-call note for why ``preflight`` itself never
    constructs a ``Workspace`` — that wiring is left entirely to the caller
    building this closure."""

    def _run():
        return setup_flows.responder_mode(mock, workspace, plugin_version, at)

    return _run


def preflight(
    config,
    state_dir,
    stamp_path,
    plugin_version,
    current_roster_hash,
    marker_confirm=False,
    responder_mode_fn=None,
):
    """contracts/lifecycle-protocol.md "Preflight decision table" — the six
    rows, evaluated strictly in the documented order (FR-001).

    **Ordering note** (contracts doc, restated): marker rows 3-4 are checked
    *before* the stamp row 5, even though FR-001's prose lists the stamp
    first — the stale-stamp branch's auto-run performs store *reads*
    (``responder_mode``'s probes), and the crashed-open Assumption requires
    marker detection before any store read at all. Marker-first is the only
    order that satisfies both. Config presence/well-formedness (rows 1-2)
    are checked before either — a malformed config always wins, mirroring
    ``setup_flows.derive_mode``'s own "malformed always wins" precedent, and
    "no config" must stop before anything else is even inspected.

    ``config``: the parsed ``bb.config.v1`` dict, or ``None`` for "no config
    block at all" (row 1), or any non-dict value (e.g. a caught
    ``json.JSONDecodeError`` passed straight through — the same malformed-
    config convention ``doctor_flows``/``setup_flows`` already use) for row 2.

    ``state_dir``: the local session-state directory (``.bb-session/``
    stand-in) — ``state_dir/marker.json`` is read, never written, by this
    function (writing/rewriting the marker belongs to ``open_command``,
    which runs only once ``preflight`` says ``proceed: True``).

    ``stamp_path``/``plugin_version``/``current_roster_hash``: threaded
    straight into ``doctor_flows.evaluate_stamp`` (R11) — this function
    never redefines slice-4's staleness semantics, only consumes them.

    ``marker_confirm``: the crash-residue confirmation decision (row 4) as a
    plain boolean parameter — no interactivity in tests or in this function;
    a real command's prompt-and-confirm step supplies this value.

    ``responder_mode_fn``: a zero-arg callable invoked only when the stamp
    is missing/stale (row 5); see ``default_responder_mode_fn`` above. If
    the stamp needs a refresh and no callable was supplied, this is a
    caller-usage error (fails loud rather than silently skipping the
    auto-run FR-001 requires).

    Returns the data-model.md outcome dict: ``{"proceed", "stopped_reason",
    "responder_mode_ran", "marker_state", "stamp_state"}``. ``marker_state``
    is one of ``None`` (never reached — rows 1-2 stopped first), ``"absent"``,
    ``"confirmed_open"``, ``"crash_residue"`` (declined), or
    ``"crash_residue_confirmed"``. ``stamp_state`` is ``None`` when never
    reached, else the ``doctor_flows.evaluate_stamp`` vocabulary
    (``"fresh"``/``"stale"``) as it stood once preflight finished deciding.
    """
    state_dir = Path(state_dir)
    marker_path = state_dir / "marker.json"

    # Row 1: no config block at all — stop; never even looks at the marker
    # or the stamp (no session artifacts are created — never half-open).
    if config is None:
        return _preflight_outcome(
            proceed=False,
            stopped_reason="no battleBuddy config block present — run /setup",
            responder_mode_ran=False,
            marker_state=None,
            stamp_state=None,
        )

    # Row 2: config present but malformed — an explicit repair case, never
    # treated as absent (contracts/doctor-protocol.md "Malformed config
    # block", consumed here verbatim).
    if not isinstance(config, dict):
        return _preflight_outcome(
            proceed=False,
            stopped_reason=(
                "battleBuddy config block is malformed ({!r}) — repair case, "
                "surfaced explicitly, never treated as absent".format(config)
            ),
            responder_mode_ran=False,
            marker_state=None,
            stamp_state=None,
        )

    # Rows 3-4: marker check BEFORE stamp evaluation (ordering note above) —
    # before any store read of any kind.
    marker = None
    if marker_path.exists():
        marker = json.loads(marker_path.read_text(encoding="utf-8"))

    marker_state = "absent"
    if marker is not None:
        if marker.get("open_write_confirmed"):
            # Row 3: a session is already open in this workspace.
            return _preflight_outcome(
                proceed=False,
                stopped_reason=(
                    "a session is already open ({}) — offering /close first "
                    "(local-state protocol v1 one-session-at-a-time rule)"
                    .format(marker.get("session_id"))
                ),
                responder_mode_ran=False,
                marker_state="confirmed_open",
                stamp_state=None,
            )
        # Row 4: crash residue — the marker's own open write was never
        # confirmed. Surface it; proceed only on explicit confirmation,
        # which the caller's subsequent open_command call REWRITES as part
        # of the new open (never a standalone delete — deletion-is-cleared
        # stays exclusive to confirmed close).
        if not marker_confirm:
            return _preflight_outcome(
                proceed=False,
                stopped_reason=(
                    "crash residue: marker for {} was never confirmed — "
                    "responder confirmation is required before it is "
                    "overwritten by a new open".format(marker.get("session_id"))
                ),
                responder_mode_ran=False,
                marker_state="crash_residue",
                stamp_state=None,
            )
        marker_state = "crash_residue_confirmed"

    # Row 5: stamp evaluation (slice-4 semantics, consumed never redefined).
    stamp_status, stamp_reason = doctor_flows.evaluate_stamp(
        stamp_path, plugin_version, current_roster_hash
    )
    responder_mode_ran = False
    if stamp_status != "fresh":
        if responder_mode_fn is None:
            raise RuntimeError(
                "preflight: stamp is {} ({}) and no responder_mode_fn was "
                "supplied to auto-run responder-mode setup (FR-001/R11) — "
                "pass a zero-arg callable, e.g. "
                "lifecycle_flows.default_responder_mode_fn(mock, workspace, "
                "plugin_version, at)".format(stamp_status, stamp_reason)
            )
        responder_result = responder_mode_fn()
        responder_mode_ran = True
        if responder_result["report"]["outcome"] != "green":
            return _preflight_outcome(
                proceed=False,
                stopped_reason=(
                    "responder-mode auto-run did not go green: {!r}".format(
                        responder_result["report"]
                    )
                ),
                responder_mode_ran=True,
                marker_state=marker_state,
                stamp_state=stamp_status,
            )
        stamp_status = "fresh"

    # Row 6: proceed to the open flow. On the happy path (stamp already
    # fresh) this function has made zero mock calls of any kind — SC-002.
    return _preflight_outcome(
        proceed=True,
        stopped_reason=None,
        responder_mode_ran=responder_mode_ran,
        marker_state=marker_state,
        stamp_state=stamp_status,
    )


# ---------------------------------------------------------------------------
# open_command (contracts/lifecycle-protocol.md "Open-flow order",
# "Marker lifecycle", "Join-vs-separate", "Briefing artifact"; FR-001,
# FR-002, FR-004, FR-005, FR-006; research R2, R4, R6, R14, R15, R16, R17)
# ---------------------------------------------------------------------------


def _validate_verdict_candidates(candidates):
    """SKILL.md "Validation gate" logic, duplicated in miniature from
    ``store_flows.write_checkpoint``'s step 1 (never called directly here —
    R2 forbids a second, post-append store write, which is exactly what
    ``write_checkpoint`` would perform over an *existing* row). One
    re-prompt: validate ``candidates[0]`` with the real validator; on
    failure, try ``candidates[1]``; on a second failure, persist
    ``candidates[1]`` flagged ``schema_valid: false`` rather than dropping
    it. Returns ``(winning_doc, schema_valid, validator_errors)``."""
    validator_errors = []
    first_errors = store_flows.bb_validate.validate(candidates[0])
    validator_errors.append(first_errors)
    if not first_errors:
        return candidates[0], True, validator_errors

    second_errors = store_flows.bb_validate.validate(candidates[1])
    validator_errors.append(second_errors)
    if not second_errors:
        return candidates[1], True, validator_errors

    winning_doc = dict(candidates[1])
    winning_doc["schema_valid"] = False
    return winning_doc, False, validator_errors


def _build_claims(winning_doc):
    """contracts/lifecycle-protocol.md "Briefing artifact" -> claims: one
    ``{statement, evidence: [{url, excerpt}, ...]}`` per ``candidates[]``
    entry that carries both a non-empty ``statement`` and >=1 well-formed
    evidence pair (see module docstring's judgment call — a candidate
    lacking either contributes no claim, never an unevidenced one)."""
    claims = []
    for candidate in winning_doc.get("candidates") or []:
        statement = candidate.get("statement")
        evidence = candidate.get("evidence")
        if not statement or not evidence:
            continue
        clean_evidence = [
            {"url": entry["url"], "excerpt": entry["excerpt"]}
            for entry in evidence
            if isinstance(entry, dict) and entry.get("url") and entry.get("excerpt")
        ]
        if not clean_evidence:
            continue
        claims.append({"statement": statement, "evidence": clean_evidence})
    return claims


def _top_cited_dashboard(claims):
    """contracts/lifecycle-protocol.md "Briefing artifact" -> top-cited: the
    URL most cited across every claim's evidence, ties broken by first
    citation order (the order a URL is first seen, walking claims then
    evidence in order). Returns ``None`` when there is no evidence at all."""
    counts = {}
    first_seen_order = []
    for claim in claims:
        for entry in claim["evidence"]:
            url = entry["url"]
            if url not in counts:
                counts[url] = 0
                first_seen_order.append(url)
            counts[url] += 1
    if not counts:
        return None
    max_count = max(counts.values())
    for url in first_seen_order:
        if counts[url] == max_count:
            return url
    return None  # unreachable — first_seen_order always covers counts' keys


def open_command(
    mock,
    state_dir,
    session_type,
    source_id,
    opened_date,
    started_at,
    responder,
    verdict_candidates,
    catalog,
    shell=None,
    rung_answers=None,
    auto_launch_deep=False,
    deep_confirmed=False,
    ignore_join_offer=False,
):
    """contracts/lifecycle-protocol.md "Open-flow order", executed in the
    documented sequence (FR-001).

    ``mock``: the ``bb-mock-mcp`` facade (or a fault-injecting wrapper
    sharing its ``invoke`` surface). ``state_dir``: the local session-state
    directory (``.bb-session/`` stand-in) — ``marker.json`` and
    ``staging/checkpoints.jsonl`` live under it. ``session_type``/
    ``source_id``/``opened_date``: compute ``session_id`` =
    ``{type}-{source-id}-{ISO date}`` (D-8; R17 — ``opened_date`` is the
    open-time UTC date, supplied by the caller, never read from the clock
    here). ``started_at``: the full ISO 8601 open timestamp, both the row's
    ``started_at`` and the marker's ``opened_at``. ``responder``: the
    row's/marker take-over's responder string. ``verdict_candidates``: the
    ordered produce-then-re-prompt list (research R9's convention,
    ``store_flows.write_checkpoint``'s own parameter shape) — a single-
    element list is fine when the caller already knows the document is
    valid. ``catalog``: the loaded fixture catalog
    (``lifecycle_fixtures.load_catalog()``'s shape). ``shell``: a shell
    adapter (``lifecycle_fixtures.RecordingShellAdapter``/
    ``FailingShellAdapter``) or ``None`` for degraded mode (R6). ``source_id``
    doubles as the alerting key (``alerting.get_alert``'s ``alert_id``) —
    exactly the real-world case for `/page`, where the alert ID *is* the
    source ID. ``rung_answers``: forwarded verbatim to
    ``lifecycle_fixtures.resolve_service`` for a catalog-miss ladder walk.
    ``auto_launch_deep``/``deep_confirmed``: the FR-5f/R14 orchestration
    inputs `/incident` (US2) will drive; `/page` sessions never propose deep
    investigation at all (see ``deep_proposed`` below). ``ignore_join_offer``
    (US3, additive, keyword-only, default ``False``): the cleanest additive
    mechanism found for ``open_separate`` (below) to force the explicit
    "separate" choice through step 5's join halt — every existing caller is
    unaffected (default preserves this function's halt-and-surface behavior
    exactly); ``open_separate`` is the only caller that ever passes ``True``.

    Steps, each citing the contracts-doc section it executes:

    1. **Marker write** (open write unconfirmed) — written early, before any
       store activity, mirroring FR-002's "created at open" state.
    2. **Shell open_pane** (session-named workspace) — degraded: a printed
       message (R6, §6.3).
    3. **Alert context + flap history** (``alerting.get_alert``,
       ``alerting.list_alert_history``) — fail-soft: a ``not_found`` on the
       alert degrades the row's alert signature to the alert ID alone and
       is surfaced in the briefing's notes, but the session still opens
       (R15).
    4. **Catalog resolve + fresh runbook/dashboard fetch**
       (``lifecycle_fixtures.resolve_service``, R4) — a catalog miss walks
       the ladder, downgrading ``catalog_resolved`` and noted in the
       briefing.
    5. **Tier-0 retrieval** (``store_flows.retrieve_candidates``) plus join
       detection on the same retrieval point (``store_flows.
       detect_open_session`` — a second ``read_records`` by contract
       limitation, not a second decision point). A non-empty match means an
       open/handoff row already exists for this source ID: this function
       **stops here, before any store write**, and returns the offer as
       ``join_offer`` — join/separate execution itself is US3 scope
       (``join_session``/``open_separate`` below), UNLESS the caller passed
       ``ignore_join_offer=True`` (``open_separate``'s own mechanism), in
       which case this step's match is still reported as ``join_offer`` on
       the completed-path outcome below (bypassed, never silently hidden)
       and the flow proceeds exactly as if no candidates existed (FR-004).
    6. **Verdict validation** (one re-prompt; second failure persists
       flagged ``schema_valid: false`` — FR-005) via
       ``_validate_verdict_candidates`` above (R2 — never
       ``store_flows.write_checkpoint``, which would be a second,
       forbidden post-append write).
    7. **Row append carrying the verdict** — checkpoint zero rides this
       append (never a separate write): the winning document is serialized
       via ``store_flows._serialize_checkpoint`` and, if it exceeds the
       contract's cell guard, is written to an artifact FIRST
       (``artifacts.put_file`` at
       ``battle-buddy/<session_id>/checkpoint-0.json``) with the row's cell
       then holding ``{"overflow": <link>, "seq": 0}`` (R2). The checkpoint
       history line (``staging/checkpoints.jsonl``, ``{"seq": 0,
       "document": <full document>}``) is appended alongside it.
    8. **Read-back** (``storage.read_records``) — only a confirmed
       single-row match flips the marker's ``open_write_confirmed`` to
       ``true`` (FR-002).
    9. **Briefing** (``bb.briefing.v1``, R16) — claims from the verdict's
       candidates (see ``_build_claims``), top-cited dashboard navigated
       into view when a shell is configured, printed instead when degraded
       or when the adapter call fails mid-flow (R6 fail-soft).

    Returns a data-model.md-shaped outcome dict — see the two return points
    below for the exact keys on the halted-for-join and completed paths.
    """
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "staging").mkdir(parents=True, exist_ok=True)
    marker_path = state_dir / "marker.json"

    session_id = "{}-{}-{}".format(session_type, source_id, opened_date)

    # Step 1 (contracts doc "Open-flow order"): marker write, open write
    # unconfirmed.
    marker = {
        "protocol": "bb.local.v1",
        "session_id": session_id,
        "source_id": source_id,
        "opened_at": started_at,
        "open_write_confirmed": False,
    }
    marker_path.write_text(json.dumps(marker, indent=2), encoding="utf-8")

    printed = lifecycle_fixtures.PrintedOutput()

    # Step 2: shell open_pane — session-named workspace; degraded/failed ->
    # printed message, never a flow failure (R6).
    if shell is not None:
        try:
            shell.open_pane(session_id, workspace=session_id)
        except Exception:
            printed.message("open workspace pane for {}".format(session_id))
    else:
        printed.message("open workspace pane for {}".format(session_id))

    # Step 3: alert context + flap history — fail-soft on a not_found alert.
    alert_result = mock.invoke("alerting", "get_alert", {"alert_id": source_id})
    if "error" in alert_result:
        alert = None
        alert_context_available = False
        alert_signature = source_id
    else:
        alert = alert_result["alert"]
        alert_context_available = True
        alert_signature = "{}: {}".format(
            alert.get("service_hint") or "unknown", alert.get("description") or source_id
        )

    history_result = mock.invoke(
        "alerting", "list_alert_history", {"filter": {"alert_id": source_id}}
    )
    flap_history = history_result.get("alerts", []) if "error" not in history_result else []

    # Step 4: catalog resolve + fresh runbook/dashboard fetch.
    resolution = lifecycle_fixtures.resolve_service(alert, catalog, rung_answers)

    # Step 5: tier-0 retrieval + join detection on the same retrieval point.
    retrieval = store_flows.retrieve_candidates(
        mock,
        resolution["fingerprint"],
        resolution["catalog_resolved"],
        [resolution["service"]],
        alert_signature,
        None,  # severity unknown until the verdict returns (step 6, below)
    )
    join_candidates = store_flows.detect_open_session(mock, source_id)
    if join_candidates and not ignore_join_offer:
        # FR-004: no store write of any kind before the explicit choice.
        # join/separate execution is US3 scope (join_session/open_separate
        # below) — halt here unless the caller explicitly bypassed via
        # ignore_join_offer (open_separate's mechanism).
        return {
            "proceed": False,
            "session_id": session_id,
            "marker": marker,
            "marker_path": marker_path,
            "join_offer": join_candidates,
            "resolution": resolution,
            "retrieval": retrieval,
            "alert": alert,
            "alert_context_available": alert_context_available,
            "flap_history": flap_history,
            "shell_calls": getattr(shell, "calls", None) if shell is not None else None,
            "printed": printed.entries,
            "readback_confirmed": False,
            "verdict_valid": None,
            "verdict_overflowed": None,
            "briefing": None,
            "deep_proposed": None,
            "deep_launched": None,
        }

    # Step 6: verdict validation (one re-prompt; second failure persists
    # flagged).
    winning_doc, schema_valid, validator_errors = _validate_verdict_candidates(
        verdict_candidates
    )
    severity = winning_doc.get("severity")

    # Step 7: row append carrying the verdict — checkpoint zero rides the
    # append; cell-guard overflow-first.
    serialized = store_flows._serialize_checkpoint(winning_doc)
    cell_guard_chars = mock.schema_registry.constants["single_field_limit_chars"]
    overflowed = False
    overflow_link = None
    if len(serialized) <= cell_guard_chars:
        cell_value = serialized
    else:
        overflowed = True
        artifact_name = "battle-buddy/{}/checkpoint-0.json".format(session_id)
        put_result = mock.invoke(
            "artifacts", "put_file", {"name": artifact_name, "content": serialized}
        )
        if "error" in put_result:
            # Never write a dangling overflow pointer — a rejected upload
            # fails loudly (mirrors store_flows.write_checkpoint's own rule).
            raise RuntimeError(
                "overflow put_file rejected for {}: {!r}".format(
                    artifact_name, put_result["error"]
                )
            )
        overflow_link = put_result["link"]
        cell_value = store_flows._serialize_checkpoint(
            {"overflow": overflow_link, "seq": 0}
        )

    row = store_flows.build_row(
        session_id=session_id,
        session_type=session_type,
        status="open",
        fingerprint=resolution["fingerprint"],
        catalog_resolved=resolution["catalog_resolved"],
        alert_signature=alert_signature,
        services=[resolution["service"]],
        severity=severity,
        responder=responder,
        started_at=started_at,
        triage_verdict=cell_value,
    )
    append_result = mock.invoke("storage", "append_record", {"record": row})

    # History line (staging/checkpoints.jsonl, {"seq": 0, "document": ...}) —
    # slice-3's history rule, applied to checkpoint zero.
    history_path = state_dir / "staging" / "checkpoints.jsonl"
    history_line = store_flows._serialize_checkpoint({"seq": 0, "document": winning_doc})
    with history_path.open("a", encoding="utf-8") as f:
        f.write(history_line + "\n")

    # Step 8: read-back — only a confirmed single-row match flips the marker.
    readback = mock.invoke(
        "storage", "read_records", {"filter": {"session_id": session_id}}
    )
    records = readback["records"]
    readback_confirmed = len(records) == 1 and records[0].get("session_id") == session_id
    if readback_confirmed:
        marker = dict(marker)
        marker["open_write_confirmed"] = True
        marker_path.write_text(json.dumps(marker, indent=2), encoding="utf-8")

    # Step 9: briefing (bb.briefing.v1) — claims, top-cited dashboard,
    # navigate-vs-printed branch.
    claims = _build_claims(winning_doc)
    top_cited_dashboard = _top_cited_dashboard(claims)

    notes = []
    if not alert_context_available:
        notes.append("alert context unavailable")
    if not resolution["catalog_resolved"]:
        notes.append("catalog resolution downgraded — resolved via the fallback ladder")

    nav_failed = False
    if top_cited_dashboard is not None and shell is not None:
        try:
            shell.navigate_pane(session_id, top_cited_dashboard)
        except Exception:
            nav_failed = True
    degraded = shell is None or nav_failed
    printed_links = []
    if top_cited_dashboard is not None and degraded:
        printed.link(top_cited_dashboard)
        printed_links = [top_cited_dashboard]

    briefing = {
        "schema": "bb.briefing.v1",
        "session_id": session_id,
        "alert_context_available": alert_context_available,
        "claims": claims,
        "top_cited_dashboard": top_cited_dashboard,
        "degraded": degraded,
        "printed_links": printed_links,
        "notes": notes,
    }

    # Deep-investigation orchestration flags (R14) — /page never proposes
    # deep investigation immediately; that is /incident's (US2) behavior.
    deep_proposed = session_type == "incident"
    deep_launched = deep_proposed and (auto_launch_deep or deep_confirmed)

    return {
        "proceed": True,
        "session_id": session_id,
        "row": row,
        "append_result": append_result,
        "readback_confirmed": readback_confirmed,
        "marker": marker,
        "marker_path": marker_path,
        "verdict_valid": schema_valid,
        "verdict_overflowed": overflowed,
        "overflow_link": overflow_link,
        "validator_errors": validator_errors,
        "winning_document": winning_doc,
        "resolution": resolution,
        "retrieval": retrieval,
        # Empty on every existing (non-bypassed) caller — join_candidates is
        # necessarily [] to have reached this point without ignore_join_offer.
        # A caller that bypassed via ignore_join_offer=True (open_separate)
        # sees whatever step 5 actually found, bypassed rather than hidden.
        "join_offer": join_candidates,
        "alert": alert,
        "alert_context_available": alert_context_available,
        "flap_history": flap_history,
        "briefing": briefing,
        "shell_calls": getattr(shell, "calls", None) if shell is not None else None,
        "printed": printed.entries,
        "deep_proposed": deep_proposed,
        "deep_launched": deep_launched,
    }


# ---------------------------------------------------------------------------
# join_session / open_separate (contracts/lifecycle-protocol.md
# "Join-vs-separate", "Marker lifecycle" state 3; FR-002, FR-004; research
# R1, R7) — T018 (US3)
# ---------------------------------------------------------------------------


def join_session(mock, state_dir, row, responder):
    """contracts/lifecycle-protocol.md "Join-vs-separate" / "Marker
    lifecycle" state 3 (R7): executes the explicit **join** choice on one of
    ``open_command``'s ``join_offer`` candidate rows (a full row dict from
    ``store_flows.detect_open_session``'s scan — already read, never a
    second lookup by this function).

    Steps, each citing the contracts-doc section it executes:

    1. **Rehydrate** — ``store_flows.read_latest_checkpoint`` on the joined
       row's own ``session_id`` (never a newly computed one): reads
       ``latest_checkpoint``/``triage_verdict`` and follows an overflow
       pointer via ``artifacts.get_file`` when present. A row that carries
       no checkpoint at all yet is a legitimate outcome — ``None`` is
       surfaced as-is, never treated as an error.
    2. **Take-over** — ``store_flows.take_over`` writes ``responder`` onto
       the joined row: exactly one ``update_record`` (the read inside
       ``take_over`` is non-mutating — it only reports who gets displaced,
       never gates the write; a take-over always wins, D-18).
    3. **Marker rewrite** (R7, documented protocol extension) — the local
       marker is rewritten **wholesale** to the joined session's identity:
       ``session_id`` (the joined row's own, from ``row``), ``source_id``
       (parsed from that same ``session_id`` per schema.md's rule —
       ``store_flows.parse_source_id``, never carried over from whatever
       this workspace's marker previously named), ``opened_at`` (the joined
       row's own ``started_at`` — never this join's own timestamp).
       Confirmation is the take-over write's **read-back**, not the marker
       write itself: the row is re-read by ``session_id`` and its
       ``responder`` cell is compared against ``responder`` (this join's
       token) — a match sets ``open_write_confirmed: true``; a missing row
       or a mismatch (a race — someone else took over between step 2 and
       this re-read) leaves it ``false``. The marker is rewritten to the
       joined identity **either way** — the rewrite IS the join; only its
       confirmation flag depends on the read-back (contracts doc: "marker
       still rewritten to the joined identity — the rewrite is the join;
       the confirmation is the read-back").

    ``state_dir``: the local session-state directory whose ``marker.json``
    this function overwrites — replacing whatever marker the halted
    ``open_command`` call left behind for the not-yet-opened new session
    (the halt path already wrote one, unconfirmed, for a session that never
    actually opens once "join" is chosen).

    Returns the data-model.md ``join_session`` outcome: ``{"session_id",
    "rehydrated_checkpoint", "takeover_result", "marker_rewritten",
    "marker_confirmed"}`` — ``marker_rewritten`` is unconditionally ``True``
    (the rewrite always happens); ``marker_confirmed`` is the read-back
    result described above. Also returns ``"marker"``/``"marker_path"`` for
    callers/tests that want the written shape or location without
    re-reading the file themselves.
    """
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    session_id = row["session_id"]

    # Step 1: rehydrate from the joined row's own latest checkpoint
    # (overflow followed); None is a legitimate, surfaced-as-is outcome.
    rehydrated_checkpoint = store_flows.read_latest_checkpoint(mock, session_id)

    # Step 2: take-over — exactly one update_record; no precondition here
    # (take_over's own read is non-mutating and never gates the write).
    takeover_result = store_flows.take_over(mock, session_id, responder)

    # Step 3: marker rewritten to the joined identity; confirmation is the
    # take-over write's own read-back, never the marker write itself.
    readback = mock.invoke(
        "storage", "read_records", {"filter": {"session_id": session_id}}
    )
    readback_rows = readback["records"]
    marker_confirmed = (
        len(readback_rows) == 1 and readback_rows[0].get("responder") == responder
    )

    marker = {
        "protocol": "bb.local.v1",
        "session_id": session_id,
        "source_id": store_flows.parse_source_id(session_id),
        "opened_at": row.get("started_at"),
        "open_write_confirmed": marker_confirmed,
    }
    marker_path = state_dir / "marker.json"
    marker_path.write_text(json.dumps(marker, indent=2), encoding="utf-8")

    return {
        "session_id": session_id,
        "rehydrated_checkpoint": rehydrated_checkpoint,
        "takeover_result": takeover_result,
        "marker_rewritten": True,
        "marker_confirmed": marker_confirmed,
        "marker": marker,
        "marker_path": marker_path,
    }


def open_separate(
    mock,
    state_dir,
    session_type,
    source_id,
    opened_date,
    started_at,
    responder,
    verdict_candidates,
    catalog,
    shell=None,
    rung_answers=None,
    auto_launch_deep=False,
    deep_confirmed=False,
):
    """contracts/lifecycle-protocol.md "Join-vs-separate": the explicit
    **separate** choice — proceed with the normal open flow for a NEW
    session despite an existing ``join_offer`` candidate, appending a
    distinct row and tracking only the new session in the local marker.

    A thin re-entry into ``open_command`` with its additive, keyword-only
    ``ignore_join_offer=True`` — the cleanest additive mechanism available
    (R1's reuse discipline): no duplicated open-flow logic, and
    ``open_command``'s own default behavior (halt and surface the choice)
    is completely unchanged for every other caller, since that parameter
    defaults to ``False``. Every argument here is forwarded verbatim; this
    function makes no decision of its own beyond forcing the bypass, so its
    parameter list and return shape are identical to ``open_command``'s own
    (see that function's docstring for each parameter's meaning).
    """
    return open_command(
        mock,
        state_dir,
        session_type,
        source_id,
        opened_date,
        started_at,
        responder,
        verdict_candidates,
        catalog,
        shell=shell,
        rung_answers=rung_answers,
        auto_launch_deep=auto_launch_deep,
        deep_confirmed=deep_confirmed,
        ignore_join_offer=True,
    )


# ---------------------------------------------------------------------------
# promote_session (contracts/lifecycle-protocol.md "Promotion"; FR-003;
# data-model.md promote_session outcome shape)
# ---------------------------------------------------------------------------


def promote_session(mock, state_dir):
    """contracts/lifecycle-protocol.md "Promotion" (FR-003): `/incident`
    invoked *inside* an already-open page session promotes it in place —
    exactly one ``storage.update_record`` re-tagging the marker-named
    session's ``session_type`` to ``"incident"``. Never an append (this is
    the same session, not a new one) and never a marker rewrite (the marker
    already names the right session — promotion isn't a join, R7's marker
    rewrite is a join-only extension this function has no reason to touch).
    Deep investigation launches unconditionally on promotion — "Deep
    investigation launches on promotion (FR-5f(b))" (contracts doc), unlike
    a fresh `/incident`'s confirmation-vs-``autoLaunchDeep`` gate
    (``open_command``'s ``deep_launched`` above, R14) — so this function
    takes no confirmation parameter at all.

    ``state_dir``: the local session-state directory — ``marker.json``
    under it names the session to promote. Read-only: this function never
    writes it, since the session it names is exactly the one being promoted
    (contrast ``join_session``'s (US3) marker rewrite onto a *different*
    session's identity).

    **No marker** — nothing open in this workspace to promote at all. This
    is a caller-usage/edge condition, not a promotion failure (the spec's
    Independent Test for this story assumes an already-open page session);
    no store call of any kind is made. Returns ``{"session_id": None,
    "retagged": False, "deep_launched": False, "reason": <str>}``.

    **Marker present but the row it names no longer resolves** (the
    ``update_record`` call itself comes back ``not_found`` — a stale or
    corrupted local marker): this function does **not** attempt
    ``store_flows.close_session``'s not-found relocate-by-source-ID scan.
    That reconciliation exists for close's merge-aware posture, where
    multiple rows can legitimately share a source ID mid-session; a
    promotion marker names exactly one session by ID, so a `not_found` here
    reflects a local-state inconsistency, not a duplicate-row scenario the
    reconciliation is built to resolve — surfacing the raw error is more
    honest than guessing at a relocation target. Returns ``{"session_id":
    <marker's>, "retagged": False, "deep_launched": False, "update_error":
    <the mock's error envelope>}``.

    On success: ``{"session_id": <marker's>, "retagged": True,
    "deep_launched": True, "update_result": <mock result>}`` — the
    data-model.md outcome shape (``session_id``, ``retagged``,
    ``deep_launched``) plus the raw mock result for callers/tests that want
    it.
    """
    state_dir = Path(state_dir)
    marker_path = state_dir / "marker.json"

    if not marker_path.exists():
        return {
            "session_id": None,
            "retagged": False,
            "deep_launched": False,
            "reason": "no local session marker — nothing open to promote",
        }

    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    session_id = marker.get("session_id")

    # The one and only write this function performs: the re-tag.
    update_result = mock.invoke(
        "storage",
        "update_record",
        {"session_id": session_id, "fields": {"session_type": "incident"}},
    )

    if "error" in update_result:
        return {
            "session_id": session_id,
            "retagged": False,
            "deep_launched": False,
            "update_error": update_result["error"],
        }

    return {
        "session_id": session_id,
        "retagged": True,
        "deep_launched": True,
        "update_result": update_result,
    }


# ---------------------------------------------------------------------------
# derive_timeline (contracts/lifecycle-protocol.md "Timeline derivation";
# FR-009, D-5; research R10) — T015 (US4)
# ---------------------------------------------------------------------------


def derive_timeline(state_dir):
    """contracts/lifecycle-protocol.md "Timeline derivation" (FR-009, D-5;
    research R10): a pure function over the local ``trace.jsonl`` call lines
    and the ``staging/checkpoints.jsonl`` history entries — never the
    transcript. The mapping is 1:1 and complete: every input line yields
    exactly one event; no event exists without one.

    - Each ``trace.jsonl`` line **without** an ``event`` field (a call line —
      local-state-protocol.md "trace.jsonl"; tripwire/other event lines
      carry ``event`` and are skipped entirely, never becoming timeline
      events) maps to ``{"at", "source": "trace", "seq", "summary",
      "outcome"}``, read straight off the line.
    - Each ``staging/checkpoints.jsonl`` entry (``{"seq", "document"}`` —
      ``store_flows``'s own checkpoint-history-line shape, also what
      ``open_command``'s checkpoint-zero history line writes) maps to
      ``{"at", "source": "checkpoint", "seq", "phase"}``, with ``at``/
      ``phase`` read from the wrapped ``document`` where present (absent ->
      ``None`` — this function never fabricates either).

    Ordered by ``at``; ties broken by ``(source, seq)``. An event whose
    ``at`` is ``None`` sorts after every timestamped event (a defensive
    tie-break for a malformed/incomplete input line — well-formed fixtures
    always carry ``at`` on every line) — ties among ``None``-``at`` events
    still resolve by ``(source, seq)``.

    ``state_dir``: the local session-state directory — a missing
    ``trace.jsonl`` or ``staging/checkpoints.jsonl`` simply contributes no
    events from that source (never an error; a session with no checkpoints
    yet, or whose trace hasn't been written in this test, still derives
    whatever the other source has).
    """
    state_dir = Path(state_dir)
    events = []

    trace_path = state_dir / "trace.jsonl"
    if trace_path.exists():
        for line in trace_path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            entry = json.loads(line)
            if "event" in entry:
                continue  # tripwire/other event lines never become timeline events
            events.append(
                {
                    "at": entry.get("at"),
                    "source": "trace",
                    "seq": entry.get("seq"),
                    "summary": entry.get("summary"),
                    "outcome": entry.get("outcome"),
                }
            )

    history_path = state_dir / "staging" / "checkpoints.jsonl"
    if history_path.exists():
        for line in history_path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            entry = json.loads(line)
            document = entry.get("document") or {}
            events.append(
                {
                    "at": document.get("at"),
                    "source": "checkpoint",
                    "seq": entry.get("seq"),
                    "phase": document.get("phase"),
                }
            )

    events.sort(key=lambda e: (e["at"] is None, e["at"], e["source"], e["seq"]))
    return events


# ---------------------------------------------------------------------------
# draft_close (contracts/lifecycle-protocol.md "Diary draft artifact —
# bb.draft.v1"; FR-007, Constitution V; research R5) — T015 (US4)
# ---------------------------------------------------------------------------

_CAUSAL_FIELDS = ("root_cause", "contributing_factors", "action_items")
_PROPOSAL_LABEL = "[PROPOSAL]"


def _render_draft_entry(closed_at, causal_values, template=None, recent_entries=None):
    """Renders the diary-entry text from the draft's causal proposals —
    configured-template-else-format-matched-to-``read_recent(5)`` (R5).
    Rendering *style* beyond the explicit proposal labels is slice 8's
    surface (SKILL.md/contracts doc); this only pins the one structural
    property R5/SC-006 need asserted on *rendered text*: every causal
    section is explicitly labeled a proposal, never presented as fact.
    """
    lines = []
    if template:
        lines.append(template)
    elif recent_entries:
        # Format-matched judgment call: slice 8 owns the real format-
        # matching logic, and it has since landed — the rules now live in
        # skills/diary/references/format.md, encoded for tests by
        # tests/helpers/diary_reference.py. This line remains a stand-in
        # rather than a real match: replacing it would change the behavior
        # of a landed, gated helper, which slice 8 recorded as out of its
        # scope (specs/008-diary-adapter/research.md R14). It still proves
        # only what it always proved — that the read_recent path was
        # consulted (its count). Note the depth here is hardcoded at 5
        # while slice 8 pins `battleBuddy.diary.recentEntries` as the
        # override; wiring that key through is the other half of R14's
        # recorded deferral and belongs to this close flow, not to the
        # diary skill.
        lines.append(
            "(format-matched to {} recent diary entries)".format(len(recent_entries))
        )
    lines.append("Closed at: {}".format(closed_at))
    for label, value in causal_values:
        lines.append("{} {}: {!r}".format(_PROPOSAL_LABEL, label, value))
    return "\n".join(lines)


def draft_close(mock, config, row, timeline, proposals):
    """contracts/lifecycle-protocol.md "Diary draft artifact — bb.draft.v1"
    (FR-007, Constitution V; research R5): produces the structured draft
    artifact **before any write** — the approval step (``close_command``'s
    gate) operates on exactly this dict.

    ``factual`` is auto-filled from ``row`` — ``links``/``services``/
    ``severity``/``responder``/``started_at`` — plus ``closed_at``, which is
    caller-supplied (**judgment call**: the caller merges it into ``row``
    before calling this, or passes a row-shaped dict already carrying it —
    this function only ever reads ``row.get("closed_at")``, never the
    clock; R17's parameterized-time discipline applies here too — a real
    close-time field isn't known until the responder confirms the close, so
    threading it through ``row`` rather than adding a fourth caller-supplied
    scalar keeps this function's signature exactly the one the task pins).
    ``timeline`` is the caller's already-derived (``derive_timeline``) event
    list — this function never derives it itself, keeping one derivation
    path.

    ``proposals``: a plain ``{root_cause, contributing_factors,
    action_items}`` map of raw candidate values (the responder's not-yet-
    approved drafting input) — each is wrapped here as ``{"proposal": true,
    "value": ...}``. **Structural invariant (SC-006)**: causal values appear
    only under ``proposals.*``; ``factual`` carries no causal key at all.

    Rendering input: ``battleBuddy.diary.template`` (contracts doc's
    additive config key) when present in ``config``, else
    ``diary.read_recent(5)`` (slice-8 surface, consumed via the mock) —
    which path was taken is recorded (``render_source``), along with the
    ``read_recent`` result when that path runs (``diary_recent_entries``,
    ``None`` on the template path) and the rendered text itself
    (``rendered_entry``), with every causal section explicitly proposal-
    labeled (``_render_draft_entry`` above).

    Returns the ``bb.draft.v1`` dict, ``approved: False`` — approval is a
    separate, later responder decision (``close_command``'s gate), never
    set by this function.
    """
    factual = {
        "timeline": timeline,
        "links": list(row.get("links") or []),
        "services": list(row.get("services") or []),
        "severity": row.get("severity"),
        "responder": row.get("responder"),
        "started_at": row.get("started_at"),
        "closed_at": row.get("closed_at"),
    }

    wrapped_proposals = {
        key: {"proposal": True, "value": proposals.get(key)} for key in _CAUSAL_FIELDS
    }

    diary_cfg = ((config or {}).get("battleBuddy") or {}).get("diary") or {}
    template = diary_cfg.get("template")

    recent_entries = None
    if template:
        render_source = "template"
    else:
        render_source = "read_recent"
        recent_result = mock.invoke("diary", "read_recent", {"n": 5})
        recent_entries = (
            recent_result.get("entries", []) if "error" not in recent_result else []
        )

    rendered_entry = _render_draft_entry(
        factual["closed_at"],
        [
            ("Root cause", wrapped_proposals["root_cause"]["value"]),
            ("Contributing factors", wrapped_proposals["contributing_factors"]["value"]),
            ("Action items", wrapped_proposals["action_items"]["value"]),
        ],
        template=template,
        recent_entries=recent_entries,
    )

    return {
        "schema": "bb.draft.v1",
        "session_id": row.get("session_id"),
        "factual": factual,
        "proposals": wrapped_proposals,
        "approved": False,
        "render_source": render_source,
        "diary_recent_entries": recent_entries,
        "rendered_entry": rendered_entry,
    }


# ---------------------------------------------------------------------------
# close_command (contracts/lifecycle-protocol.md "Close order (FR-008) and
# ordering-claim scope", "Transcript capture at close", "Timeline
# derivation", "Marker lifecycle" close-time ownership scope; FR-007,
# FR-008, FR-009, FR-010; research R9, R10, R12, R13) — T015 (US4)
# ---------------------------------------------------------------------------


def _close_outcome(
    merged=False,
    canonical_id=None,
    superseded_ids=None,
    session_id=None,
    reason=None,
    draft=None,
    approved=False,
    transcript_notice=None,
    diary_link=None,
    diary_pending=None,
    uploaded=None,
    omitted_artifacts=None,
    timeline=None,
    update_result=None,
    readback_confirmed=False,
    marker_cleared=False,
    read_only=False,
    taken_over_by=None,
    shell_calls=None,
    printed=None,
):
    return {
        "merged": merged,
        "canonical_id": canonical_id,
        "superseded_ids": superseded_ids or [],
        "session_id": session_id,
        "reason": reason,
        "draft": draft,
        "approved": approved,
        "transcript_notice": transcript_notice,
        "diary_link": diary_link,
        "diary_pending": diary_pending,
        "uploaded": uploaded or {},
        "omitted_artifacts": omitted_artifacts or [],
        "timeline": timeline,
        "update_result": update_result,
        "readback_confirmed": readback_confirmed,
        "marker_cleared": marker_cleared,
        "read_only": read_only,
        "taken_over_by": taken_over_by,
        "shell_calls": shell_calls,
        "printed": printed,
    }


def _generate_report(row, session_id, timeline):
    """SKILL.md "The report" -> "a rendering, not a source": every fact here
    already lives on ``row`` (the canonical row merged with this close's own
    ``close_fields`` — the effective closed-state row; the report uploads
    before the row's own store update lands, close-order step 2 before step
    3) or in the ``timeline``/``links`` it already carries. Introduces no
    new fact — purely a rendering.
    """
    lines = [
        "# Session report: {}".format(session_id),
        "",
        "- Services: {}".format(", ".join(row.get("services") or [])),
        "- Severity: {}".format(row.get("severity")),
        "- Responder: {}".format(row.get("responder")),
        "- Started at: {}".format(row.get("started_at")),
        "- Closed at: {}".format(row.get("closed_at")),
        "",
        "## Root cause",
        str(row.get("root_cause") or ""),
        "",
        "## Resolution",
        str(row.get("resolution") or ""),
        "",
        "## Timeline",
    ]
    for event in timeline:
        lines.append("- " + json.dumps(event, sort_keys=True))
    lines.append("")
    lines.append("## Links")
    for link in row.get("links") or []:
        lines.append("- {} — {}".format(link.get("url"), link.get("excerpt")))
    return "\n".join(lines)


def close_command(
    mock,
    state_dir,
    transcript_path,
    draft,
    close_fields,
    responder,
    shell=None,
    row_write_retries=2,
):
    """contracts/lifecycle-protocol.md "Close order (FR-008) and ordering-
    claim scope", executed in the documented sequence.

    ``mock``: the ``bb-mock-mcp`` facade (or a fault-injecting wrapper).
    ``state_dir``: the local session-state directory — ``marker.json``
    names the session this `/close` invocation is closing.
    ``transcript_path``: the runtime's transcript file path (R9) — a
    caller-supplied fixture path in tests, or ``None``/an unreadable path to
    exercise the missing-source notice. ``draft``: the ``bb.draft.v1``
    artifact (``draft_close`` above, built against whatever this function's
    own read-only detection step determines to be the prospective canonical
    row) — its ``approved`` flag gates every write below; only ``approved``
    and ``rendered_entry`` are read here, so a test may hand-build a minimal
    draft dict to drive a specific failure path without going through
    ``draft_close``. ``close_fields``: the close-time field-group values the
    responder has already curated from the draft (``root_cause``,
    ``resolution``, ``runbook_refs``, ``report_url``, ...) — passed through
    to ``store_flows.close_session`` mostly verbatim; this function only
    ever adds/overrides ``timeline`` (always its own derivation, R10) and
    folds in whatever ``links`` the canonical row already carries (below —
    ``store_flows.close_session`` would otherwise overwrite ``links``
    wholesale with only what it's given). ``responder``: this closing
    session's own currently-believed ownership token (the exact
    ``responder``-cell format) — checked against THIS SESSION's own
    (marker-named) row at step 4 below, never canonical's directly (see that
    step's note: comparing canonical's responder to this token would be
    wrong whenever this session isn't itself canonical — exactly the
    ordinary "straggler closes first" merge case R12 exists for; an earlier
    version of this function made that mistake and false-denied the normal
    merge-close). ``shell``: a shell adapter or ``None`` for degraded mode.
    ``row_write_retries``: forwarded to ``store_flows.close_session``
    (FR-008's bounded transient-failure retry) — a small default > 0 so a
    caller doesn't have to know to ask for the retry FR-008 requires; ``0``
    still opts a test all the way out.

    Steps, each citing the contracts-doc section it executes:

    1. **No marker** — nothing open in this workspace to close. Zero writes
       of any kind; returns immediately with a reason.
    2. **Read-only duplicate detection + canonical determination** (R12):
       ``store_flows.detect_open_session`` on the marker's ``source_id`` —
       a read, never a write, so it runs even when the draft turns out
       unapproved below. Two or more non-terminal rows sharing the source ID
       means the earliest-``started_at`` one is the *prospective* canonical
       row (the same selection ``merge_duplicates`` will itself make) — its
       ``responder``, **as observed right here**, is captured for step 8's
       close-time ownership check. Fewer than two: canonical is simply this
       session's own (marker-named) row. This step only *describes* what
       canonical will be — the draft (already built by the caller before
       calling this function) targets this same row; nothing is written
       yet.
    3. **Approval gate** (Constitution V, SC-006): ``draft["approved"]``
       must be ``True`` — otherwise returns immediately with **zero writes
       of any kind**, duplicates or not (the contracts doc's "no write of
       any kind occurs while approved is false" covers the merge too, not
       only the dual-write).
    4. **Ownership pre-read of this session's own row** (R13's first
       checkpoint) — immediately after approval, before any close-flow
       write of any kind. A fresh read of the row THIS SESSION's marker
       names, compared against ``responder`` (this closing session's own
       token) — never canonical's, which may be a different row entirely
       (step 2's merge case). This single check subsumes R13's "immediately
       before the merge's row updates" *and* covers the plain no-merge case
       in one rule (there, canonical IS this row, so the same check already
       protects it). A mismatch returns read-only with **zero writes at
       all** — not even a diary or artifact write lands first; FR-010 only
       requires "going read-only with a take-over report," never that any
       write happen before it's caught.
    5. **Merge writes** (R12) — only when step 2 found two or more
       duplicates: ``store_flows.merge_duplicates`` — earliest
       ``started_at`` canonical, duplicates ``superseded``, links + the
       duplicate's artifacts folder folded in. Runs after approval and this
       session's own ownership check, immediately before the diary write
       below — still outside the FR-008 ordering scope (merge writes
       precede it, exactly as slice-3 scopes mid-session writes out). Every
       step from here on targets the **canonical** session_id, whichever
       session invoked `/close` (R12).
    6. **Transcript capture** (R9): copies ``transcript_path`` into
       ``state_dir/staging/transcript.md``. A missing/unreadable source is a
       logged notice — the artifact is simply omitted from the staged set
       below, close continues.
    7. **Assemble staged artifacts + derive the timeline** (R10, D-5): the
       slice-3 local-name -> uploaded-name mapping's order (transcript,
       trace, checkpoint history), plus a freshly generated ``report.md``
       (a rendering of the canonical row + this close's own ``close_fields``,
       never a new fact — SKILL.md "The report"). ``derive_timeline`` runs
       over this same ``state_dir`` — the closing responder's own local
       trace/checkpoint files, regardless of which session is canonical.
    8. **Dual-write** (the FR-008 ordering scope): delegates to the extended
       ``store_flows.close_session`` — diary -> artifacts -> the ownership-
       gated (immediately before the close-time ``update_record`` — R13's
       second checkpoint, **unchanged**, exactly where slice-3 put it),
       retry-bounded row update -> read-back -> marker clearance —
       targeting the canonical session_id. The ``owned_by`` passed to this
       check is canonical's responder **as observed in step 2** when a
       merge occurred (an optimistic-concurrency check spanning detection
       through to this update — D-18's "no lock, compare live-vs-last-known"
       model, catching a take-over of the *canonical* row in that window);
       when no merge occurred, canonical IS this session's own row, so it's
       simply ``responder`` unchanged.
    9. **Whole local session directory removed** on confirmed marker
       clearance (protocol's "deletion is the cleared state", extended past
       ``close_session``'s own marker.json-only deletion to the entire
       ``state_dir`` — ``shutil.rmtree``). Left untouched on a read-only or
       failed-read-back outcome.
    10. **Shell close** — ``close_workspace(canonical_id)`` last, fail-soft
        (degraded: a printed message), state restorable.

    Returns a data-model.md-shaped outcome dict (``_close_outcome`` above).
    """
    state_dir = Path(state_dir)
    marker_path = state_dir / "marker.json"

    # Step 1: no marker at all -> zero writes, reason surfaced.
    if not marker_path.exists():
        return _close_outcome(reason="no local session marker — nothing open to close")

    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    session_id = marker["session_id"]
    source_id = marker.get("source_id") or store_flows.parse_source_id(session_id)

    # Step 2: read-only duplicate detection + canonical determination
    # (R12) — a read, never a write; runs even if the draft turns out
    # unapproved below.
    duplicates = store_flows.detect_open_session(mock, source_id)
    will_merge = len(duplicates) >= 2
    if will_merge:
        prospective_canonical = min(duplicates, key=lambda r: r["started_at"])
        canonical_id = prospective_canonical["session_id"]
        # "As observed" here — step 8's close-time check compares against
        # this snapshot, never a fresh re-read, by design (R13's adjudicated
        # optimistic-concurrency semantics for the canonical row).
        canonical_observed_responder = prospective_canonical.get("responder")
    else:
        canonical_id = session_id
        canonical_observed_responder = responder

    # Step 3: approval gate — zero writes of any kind while unapproved,
    # duplicates or not.
    if not draft.get("approved"):
        return _close_outcome(
            merged=False,
            canonical_id=canonical_id,
            session_id=session_id,
            draft=draft,
            approved=False,
            reason="draft not approved — no writes performed",
        )

    # Step 4: ownership pre-read of THIS session's own (marker-named) row —
    # R13's first checkpoint, immediately after approval, before any
    # close-flow write of any kind. Checked against the closer's own token,
    # never canonical's (see docstring step 4).
    own_row_result = mock.invoke(
        "storage", "read_records", {"filter": {"session_id": session_id}}
    )
    own_rows = own_row_result["records"]
    current_own_responder = own_rows[0].get("responder") if own_rows else None
    if current_own_responder != responder:
        return _close_outcome(
            session_id=session_id,
            canonical_id=canonical_id,
            read_only=True,
            taken_over_by=current_own_responder,
            reason=(
                "ownership displaced from this session's own row before any "
                "close-flow write — no writes performed"
            ),
        )

    # Step 5: merge writes (R12) — after approval + this session's own
    # ownership check, immediately before the diary write; still outside
    # the FR-008 ordering scope.
    merged = False
    superseded_ids = []
    if will_merge:
        merge_result = store_flows.merge_duplicates(mock, source_id)
        if merge_result is not None:
            merged = True
            canonical_id = merge_result["canonical_id"]
            superseded_ids = merge_result["superseded_ids"]

    # Step 6: transcript capture (R9).
    transcript_notice = None
    staged_transcript = None
    if transcript_path is not None:
        try:
            staged_transcript = Path(transcript_path).read_text(encoding="utf-8")
        except OSError as exc:
            transcript_notice = (
                "transcript source unavailable ({}) — omitted, close continues".format(exc)
            )
    else:
        transcript_notice = "no transcript source path supplied — omitted, close continues"

    if staged_transcript is not None:
        staging_dir = state_dir / "staging"
        staging_dir.mkdir(parents=True, exist_ok=True)
        (staging_dir / "transcript.md").write_text(staged_transcript, encoding="utf-8")

    # Step 7: assemble staged artifacts (mapping order) + derive the timeline.
    canonical_row_result = mock.invoke(
        "storage", "read_records", {"filter": {"session_id": canonical_id}}
    )
    canonical_rows = canonical_row_result["records"]
    canonical_row = canonical_rows[0] if canonical_rows else {}

    timeline = derive_timeline(state_dir)

    staged_artifacts = {}
    if staged_transcript is not None:
        staged_artifacts["staging/transcript.md"] = staged_transcript

    trace_path = state_dir / "trace.jsonl"
    if trace_path.exists():
        staged_artifacts["trace.jsonl"] = trace_path.read_text(encoding="utf-8")

    checkpoints_path = state_dir / "staging" / "checkpoints.jsonl"
    if checkpoints_path.exists():
        staged_artifacts["staging/checkpoints.jsonl"] = checkpoints_path.read_text(
            encoding="utf-8"
        )

    effective_row = dict(canonical_row)
    effective_row.update(close_fields)
    effective_row["timeline"] = timeline
    staged_artifacts["report.md"] = _generate_report(effective_row, canonical_id, timeline)

    final_close_fields = dict(close_fields)
    final_close_fields["timeline"] = timeline
    preserved_links = list(canonical_row.get("links") or [])
    caller_links = list(close_fields.get("links") or [])
    final_close_fields["links"] = preserved_links + caller_links

    # Step 8: dual-write, delegated to the extended close_session. owned_by
    # is canonical's responder as observed in step 2 (merge case) or this
    # session's own token unchanged (no-merge case, canonical IS this row)
    # — see docstring step 8; this is the fix for the false-denial bug an
    # earlier version of this function had (comparing canonical's live
    # responder against the closer's own token unconditionally).
    close_result = store_flows.close_session(
        mock,
        state_dir,
        canonical_id,
        close_fields=final_close_fields,
        diary_content=draft.get("rendered_entry", ""),
        staged_artifacts=staged_artifacts,
        owned_by=canonical_observed_responder,
        row_write_retries=row_write_retries,
    )

    # Step 9: whole local session directory removed on confirmed clearance.
    if close_result["marker_cleared"] and state_dir.exists():
        shutil.rmtree(str(state_dir))

    # Step 10: shell close, last, fail-soft.
    printed = lifecycle_fixtures.PrintedOutput()
    if shell is not None:
        try:
            shell.close_workspace(canonical_id)
        except Exception:
            printed.message("close workspace for {}".format(canonical_id))
    else:
        printed.message("close workspace for {}".format(canonical_id))

    return _close_outcome(
        merged=merged,
        canonical_id=canonical_id,
        superseded_ids=superseded_ids,
        session_id=session_id,
        draft=draft,
        approved=True,
        transcript_notice=transcript_notice,
        diary_link=close_result["diary_link"],
        diary_pending=close_result["diary_pending"],
        uploaded=close_result["uploaded"],
        omitted_artifacts=close_result["omitted_artifacts"],
        timeline=timeline,
        update_result=close_result["update_result"],
        readback_confirmed=close_result["readback_confirmed"],
        marker_cleared=close_result["marker_cleared"],
        read_only=close_result["read_only"],
        taken_over_by=close_result["taken_over_by"],
        shell_calls=getattr(shell, "calls", None) if shell is not None else None,
        printed=printed.entries,
    )
