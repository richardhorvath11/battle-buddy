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
    investigation at all (see ``deep_proposed`` below).

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
       ``join_offer`` — join/separate execution itself is US3 scope (T018);
       this outcome is shaped so that later work can extend it (FR-004).
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
    if join_candidates:
        # FR-004: no store write of any kind before the explicit choice.
        # join/separate execution is US3 scope (T018) — halt here.
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
        "join_offer": [],
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
