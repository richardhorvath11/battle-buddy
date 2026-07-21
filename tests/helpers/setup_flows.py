"""`/setup`'s executable form (contracts/doctor-protocol.md "Setup mode
derivation" / "Store header create-vs-validate" / "Smoke test" / "Workspace
scaffold" / "Config block"; spec FR-006/FR-007/FR-012).

Dev-only: nothing here ships (FR-012, Constitution I) — this module exists
solely so the mode-derivation table and team-mode's full sequence can be
*exercised* by hermetic contract tests against ``bb-mock-mcp``, rather than
asserted on prose (Constitution VIII). Each function's steps carry a comment
citing the doctor-protocol.md section it executes, mirroring
``tests/helpers/doctor_flows.py``'s house style. This module calls
``doctor_flows``/``store_flows`` for every piece of logic they already own
(binding resolution, probes, checks, report assembly, the schema column
table, retrieval) — nothing here re-derives those constants or re-implements
that logic.

This task (T012) delivers ``derive_mode`` (team/repair fully; a reasonable
responder/already-set-up split — see its docstring) and team mode
(``team_mode``, ``scaffold_workspace``, ``smoke_test``). Extension points left
for later tasks:

- T017 (US3) fills in ``responder_mode`` for real and refines how
  ``Workspace.probes_ok``/``stamp_state`` get populated (today they are
  caller-supplied fields with defaults; T017 will compute ``stamp_state`` via
  ``doctor_flows.evaluate_stamp`` once T016 lands that function, and
  ``probes_ok`` via a real per-responder probe run).
- T020 (US4) fills in ``validate_existing`` for real (already-set-up
  validation + partial-state resumption + malformed-config repair
  surfacing). Team mode's own store create-or-validate branch (below) is the
  only validation *this* task needs — a full standalone idempotence pass
  belongs to T020, not here.
"""

import json
from pathlib import Path

from helpers import doctor_fixtures, doctor_flows, store_flows

# ---------------------------------------------------------------------------
# Path plumbing (mirrors doctor_fixtures.py's own idiom — independent of
# conftest.py, which is pytest-only; helper modules stay importable without it)
# ---------------------------------------------------------------------------

_HELPERS_DIR = Path(__file__).resolve().parent
_TESTS_DIR = _HELPERS_DIR.parent
_REPO_ROOT = _TESTS_DIR.parent
_MANIFEST_PATH = _REPO_ROOT / "manifest" / "capabilities.json"


def _load_manifest():
    """The real shipped manifest (`manifest/capabilities.json`) — team mode
    resolves against the actual capability manifest, not a fixture stand-in
    (fixture manifests are for doctor_flows' own unit-style tests)."""
    with open(str(_MANIFEST_PATH), encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Config-block defaults (contracts/doctor-protocol.md "Config block") — used
# only when `inputs` doesn't supply its own; never asserted on by name, so
# tests are free to override every one of these via `inputs`.
# ---------------------------------------------------------------------------

_DEFAULT_STORE_URL = "https://store.example/team-sessions"
_DEFAULT_DIARY_URL = "https://diary.example/team-diary"
_DEFAULT_CATALOG_REPO = "mycorp/service-catalog"
_DEFAULT_ARTIFACT_ROOT = "battle-buddy/"
_DEFAULT_TRIAGE_TURN_CAP = 15
# No wall clock (design determinism principle, research R3) — a fixed
# fallback so a caller that doesn't care about the exact smoke-test date
# still gets a deterministic one; tests that DO care pass their own via
# `inputs["opened_date"]`.
_DEFAULT_OPENED_DATE = "2026-01-01"


# ---------------------------------------------------------------------------
# Workspace — the lightweight test-side representation of setup's two scopes
# (FR-006: team scope + responder scope, inspected, never a stored done-flag)
# ---------------------------------------------------------------------------


class Workspace:
    """The artifact state `/setup` inspects to derive its mode (FR-006).
    Fields, in the order the mode-derivation table + team mode read them:

    - ``config``: the parsed ``bb.config.v1`` dict, or ``None`` for an empty
      workspace (team mode), or any non-dict value — conventionally a caught
      ``json.JSONDecodeError`` passed straight through, mirroring
      ``doctor_flows.check_config``'s own "malformed-config representation"
      convention — standing in for a malformed config block (repair mode).
      ``team_mode`` sets this to the config it writes on a successful run.
    - ``header_store``: a store-header surface exposing ``read_header()`` /
      ``create_header(cells)`` — ``doctor_fixtures.FixtureHeaderStore`` is the
      concrete fixture (contract v1 has no header concept of its own, R5).
      Defaults to a fresh empty ``FixtureHeaderStore`` when not supplied.
    - ``roster``: the current ``tool_name -> {"input", "output"}`` roster
      surface (mirrors what ``team_mode``'s own ``roster`` argument drives a
      given run with — kept here too so later flows, e.g. drift
      re-validation, have a workspace-scoped view to read).
    - ``roster_file_text``: the exact text last written to the scaffolded
      ``.mcp.json`` (set by ``scaffold_workspace`` via ``team_mode``) —
      optional; ``None`` until a scaffold has run. T016's ``roster_hash``
      will consume this (or a live equivalent) once it lands.
    - ``tmp_path``: a ``pathlib.Path`` (or path-like) the workspace scaffold
      is written under — the hermetic stand-in for the real workspace repo
      root (tests pass pytest's own ``tmp_path`` fixture here).
    - ``catalog_path``: path to a fixture catalog-repo file doctor's
      parseability check reads (data-model.md "Fixture surfaces" — contract
      v1 has no catalog concept). Defaults to the T005
      ``catalog-valid.json`` fixture.
    - ``shell_adapter``: a ``doctor_fixtures.FixtureShellAdapter`` instance,
      or ``None`` for "no adapter configured" (R12). Defaults to ``None``.
    - ``probes_ok``: bool, whether this responder's probes currently pass
      under their own credentials — a T017 concern; defaults to ``True`` so
      a plain team-mode run (which doesn't touch responder scope at all)
      never accidentally reads as a probe failure.
    - ``stamp_state``: one of ``"missing" | "stale" | "fresh"`` — the current
      green-stamp freshness (US3/T016/T017 concern). Defaults to
      ``"missing"``, which is exactly the "config present, no stamp yet"
      shape ``derive_mode``'s table needs to route a config-present workspace
      to responder mode by default.
    """

    def __init__(
        self,
        config=None,
        header_store=None,
        roster=None,
        roster_file_text=None,
        tmp_path=None,
        catalog_path=None,
        shell_adapter=None,
        probes_ok=True,
        stamp_state="missing",
    ):
        self.config = config
        self.header_store = (
            header_store if header_store is not None else doctor_fixtures.FixtureHeaderStore()
        )
        self.roster = roster or {}
        self.roster_file_text = roster_file_text
        self.tmp_path = tmp_path
        self.catalog_path = catalog_path or doctor_fixtures.config_fixture_path(
            "catalog-valid.json"
        )
        self.shell_adapter = shell_adapter
        self.probes_ok = probes_ok
        self.stamp_state = stamp_state


# ---------------------------------------------------------------------------
# derive_mode (contracts/doctor-protocol.md "Setup mode derivation")
# ---------------------------------------------------------------------------


def derive_mode(workspace):
    """contracts/doctor-protocol.md "Setup mode derivation": inspection only,
    never a stored done-flag (FR-006).

    Fully implemented here: **team** (no config block) and **repair**
    (config present but malformed — never treated as absent, contracts/
    doctor-protocol.md "Malformed config block"). The **responder** /
    **already-set-up** split is implemented to a reasonable T012 depth: a
    config-present workspace is responder mode whenever
    ``workspace.probes_ok`` is false or ``workspace.stamp_state`` isn't
    ``"fresh"`` (which — given ``stamp_state``'s ``"missing"`` default — means
    "config present, no stamp yet" reads as responder, exactly the table's
    "stamp missing or stale" row); otherwise already-set-up.

    T017 extends this by computing ``stamp_state``/``probes_ok`` from real
    probe/stamp-evaluation calls (``doctor_flows.evaluate_stamp``, once T016
    lands it) rather than accepting them as bare workspace fields, and by
    distinguishing partial team state (module docstring; T020's concern too).
    """
    config = workspace.config

    if config is None:
        return "team"

    if not isinstance(config, dict):
        # Malformed (e.g. a caught json.JSONDecodeError passed straight
        # through — doctor_flows.check_config's own convention). A repair
        # case, never "no config" — team mode must never re-create resources
        # over a typo.
        return "repair"

    if (not workspace.probes_ok) or workspace.stamp_state != "fresh":
        return "responder"

    return "already-set-up"


# ---------------------------------------------------------------------------
# scaffold_workspace (contracts/doctor-protocol.md "Workspace scaffold")
# ---------------------------------------------------------------------------

_GITIGNORE_LINES = (".bb-session/", ".bb-doctor-stamp.json", "*.local.jsonl")

_README_TEMPLATE = """\
# battle-buddy team workspace

This repository was scaffolded by `/setup` in team mode. It holds only your
team's battle-buddy configuration — no plugin/upstream code was copied in.

## Contents

- `.claude/settings.json` — the `battleBuddy` config block (store/diary/
  catalog locations, resolved capability bindings, budgets).
- `.mcp.json` — your team's connected MCP servers. Secrets are referenced as
  `${ENV_VAR}` tokens only — never as literal values.
- `.gitignore` — excludes local-only runtime droppings (`.bb-session/`,
  the local doctor stamp, `*.local.jsonl`).

## Push to your private org

A local git repository has already been initialized (`git init`). Push it to
a **private** repository in your own org — this repo is your team's working
state, not battle-buddy's:

    git add .
    git commit -m "battle-buddy: initial team setup"
    git remote add origin git@github.com:<your-org>/<private-repo>.git
    git push -u origin main

Keep the remote private: `.mcp.json` names your organization's connected
tools, and while no secret values are committed, the server inventory itself
is internal.
"""


def _server_name_from_tool(tool_name):
    """The server-identifying prefix of a fixture/roster tool name (e.g.
    ``"mycorp_sheets.add_row"`` -> ``"mycorp_sheets"``) — doctor-protocol.md's
    own worked example names tools ``<server>.<method>``-shaped."""
    return tool_name.split(".", 1)[0]


def _mcp_servers_from_roster(roster):
    """contracts/doctor-protocol.md "Workspace scaffold": one `.mcp.json`
    server entry per connected server the roster names, tokens as
    ``${ENV_VAR}`` literal refs — CRITICAL: never a secret-looking literal
    value. Built from ``roster``'s full tool-name inventory (every connected
    server the team brought), not narrowed to only the ops doctor happened
    to bind — an unresolved or ambiguous tool is still a server the team
    connected and `.mcp.json` should still name it.

    JUDGMENT CALL: contract v1 has no live MCP server-manifest surface to
    read real command/args/env shapes from (roster entries are op shapes,
    not server launch config) — entries here are plausible placeholders
    (``npx`` + a scoped package name + one env-var token per server), which
    is exactly what FR-010's "recommended-roster template" is for in the
    shipped case; this hermetic stand-in only has to satisfy the scaffold's
    own no-secrets/env-var-ref discipline.
    """
    server_names = sorted({_server_name_from_tool(name) for name in roster})
    servers = {}
    for server_name in server_names:
        env_var = "{}_TOKEN".format(server_name.upper())
        servers[server_name] = {
            "command": "npx",
            "args": ["-y", "@{}/mcp-server".format(server_name.replace("_", "-"))],
            "env": {env_var: "${" + env_var + "}"},
        }
    return servers


def scaffold_workspace(tmpdir, config, roster):
    """contracts/doctor-protocol.md "Workspace scaffold": exactly four files,
    zero upstream content — never copies any battle-buddy plugin file into
    the workspace.

    - ``.claude/settings.json``: ``{"battleBuddy": config}``.
    - ``.mcp.json``: ``{"mcpServers": ...}`` built from ``roster`` (see
      ``_mcp_servers_from_roster``).
    - ``README.md``: push-to-private-org instructions.
    - ``.gitignore``: the runtime-droppings lines (contract doc's exact
      three).

    ``git init``/pushing themselves are the team's explicit act, outside
    this function's scope (contract doc: "`git init` locally; pushing is the
    team's explicit act").

    Returns ``{relative_path: pathlib.Path}`` for the four files written.
    """
    tmpdir = Path(tmpdir)

    claude_dir = tmpdir / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    settings_path = claude_dir / "settings.json"
    settings_path.write_text(
        json.dumps({"battleBuddy": config}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    mcp_path = tmpdir / ".mcp.json"
    mcp_text = json.dumps(
        {"mcpServers": _mcp_servers_from_roster(roster)}, indent=2, sort_keys=True
    ) + "\n"
    mcp_path.write_text(mcp_text, encoding="utf-8")

    readme_path = tmpdir / "README.md"
    readme_path.write_text(_README_TEMPLATE, encoding="utf-8")

    gitignore_path = tmpdir / ".gitignore"
    gitignore_path.write_text("\n".join(_GITIGNORE_LINES) + "\n", encoding="utf-8")

    return {
        ".claude/settings.json": settings_path,
        ".mcp.json": mcp_path,
        "README.md": readme_path,
        ".gitignore": gitignore_path,
    }, mcp_text


# ---------------------------------------------------------------------------
# smoke_test (contracts/doctor-protocol.md "Smoke test")
# ---------------------------------------------------------------------------

_SMOKE_ARTIFACT_LOCAL_NAME = "smoke.txt"
_SMOKE_FINGERPRINT = "bb-setup-smoke-test"
_SMOKE_SERVICE = "bb-setup-smoke"


def _smoke_outcome(session_id, trace, green, failure, row=None, artifact_link=None):
    return {
        "session_id": session_id,
        "trace": trace,
        "row": row,
        "artifact_link": artifact_link,
        "green": green,
        "failure": failure,
    }


def smoke_test(mock, bindings, artifact_root, opened_date):
    """contracts/doctor-protocol.md "Smoke test": a synthetic
    ``session_type: test`` / ``status: closed`` session (terminal at append —
    inert, never a live session join-at-open could surface), session ID
    ``test-bb-setup-<opened_date>`` (D-8 format), exercising exactly the four
    documented paths **through the resolved bindings** — ``append_record``,
    ``put_file``, ``append_entry``, ``read_records`` — in the contract doc's
    pinned order: record append -> artifact write -> diary append ->
    record read-back.

    JUDGMENT CALL — "artifact write success is verified by the returned link
    being recorded on the row": the link isn't known until *after*
    ``put_file`` returns, which the pinned order places *after* the initial
    ``append_record`` — so recording it requires a follow-up
    ``storage.update_record`` call, placed immediately after ``put_file`` (
    conceptually still part of the "artifact write" step: writing the file
    AND linking it back to the row) and before the diary append. This is a
    fifth *call* but not a fifth *path* — it's the same ``storage`` capability
    ``append_record``/``read_records`` already exercise, not a new
    capability; the four *documented paths* (one per capability surface:
    storage-write, artifact-write, diary-write, storage-read) are unchanged.
    ``get_file`` is never invoked here — it is harness surface, not a
    resolved binding (contract doc: "tests may read the artifact back...as
    an extra oracle only", left to test code, not this flow).

    Every call is gated on its op having a resolved entry in ``bindings`` —
    an unresolved required op fails loudly (``RuntimeError``) rather than
    silently calling the mock by capability/op alone; the resolved tool name
    is recorded per trace entry as ``via_binding``.

    Returns an outcome dict: ``{"session_id", "trace", "row", "artifact_link",
    "green", "failure"}``. ``row`` is the post-read-back record (or the
    partial state read at the point of failure); ``failure`` is ``None`` on
    success.
    """

    def _require(key):
        tool_name = bindings.get(key)
        if tool_name is None:
            raise RuntimeError(
                "smoke test cannot exercise {} — no resolved binding; the "
                "smoke test only ever runs through resolved bindings "
                "(contracts/doctor-protocol.md 'Smoke test')".format(key)
            )
        return tool_name

    session_id = "test-bb-setup-{}".format(opened_date)
    trace = []

    row = store_flows.build_row(
        session_id=session_id,
        session_type="test",
        status="closed",
        fingerprint=_SMOKE_FINGERPRINT,
        catalog_resolved=True,
        alert_signature=_SMOKE_FINGERPRINT,
        services=[_SMOKE_SERVICE],
        severity="sev4",
        responder="bb-setup",
        started_at="{}T00:00:00Z".format(opened_date),
    )

    # Path 1/4 — record append.
    append_tool = _require("storage.append_record")
    append_result = mock.invoke("storage", "append_record", {"record": row})
    trace.append(
        {"op": "storage.append_record", "via_binding": append_tool, "result": append_result}
    )
    if "error" in append_result:
        return _smoke_outcome(
            session_id, trace, False,
            "append_record failed: {}".format(append_result["error"]),
        )

    # Path 2/4 — artifact write, under <artifactRoot><session_id>/.
    artifact_tool = _require("artifacts.put_file")
    artifact_name = "{}{}/{}".format(artifact_root, session_id, _SMOKE_ARTIFACT_LOCAL_NAME)
    put_result = mock.invoke(
        "artifacts", "put_file",
        {"name": artifact_name, "content": "bb-setup smoke test artifact\n"},
    )
    trace.append(
        {"op": "artifacts.put_file", "via_binding": artifact_tool, "result": put_result}
    )
    if "error" in put_result:
        return _smoke_outcome(
            session_id, trace, False, "put_file failed: {}".format(put_result["error"])
        )
    link = put_result["link"]

    # Record the returned link on the row (see docstring JUDGMENT CALL) —
    # same storage capability, not a new documented path.
    update_tool = _require("storage.update_record")
    update_result = mock.invoke(
        "storage",
        "update_record",
        {
            "session_id": session_id,
            "fields": {
                "links": [{"url": link, "excerpt": _SMOKE_ARTIFACT_LOCAL_NAME}],
                "artifacts_folder_url": "{}{}/".format(artifact_root, session_id),
            },
        },
    )
    trace.append(
        {"op": "storage.update_record", "via_binding": update_tool, "result": update_result}
    )
    if "error" in update_result:
        return _smoke_outcome(
            session_id, trace, False,
            "update_record (artifact link) failed: {}".format(update_result["error"]),
        )

    # Path 3/4 — diary append.
    diary_tool = _require("diary.append_entry")
    diary_result = mock.invoke(
        "diary", "append_entry", {"content": "bb-setup smoke test for {}".format(session_id)}
    )
    trace.append(
        {"op": "diary.append_entry", "via_binding": diary_tool, "result": diary_result}
    )
    if "error" in diary_result:
        return _smoke_outcome(
            session_id, trace, False, "append_entry failed: {}".format(diary_result["error"])
        )

    # Path 4/4 — record read-back, confirming the appended (and now linked)
    # row through the storage binding.
    readback_tool = _require("storage.read_records")
    readback = mock.invoke(
        "storage", "read_records", {"filter": {"session_id": session_id}}
    )
    trace.append(
        {"op": "storage.read_records", "via_binding": readback_tool, "result": readback}
    )
    rows = readback.get("records", [])
    row_after = rows[0] if rows else None
    confirmed = len(rows) == 1 and row_after.get("session_id") == session_id

    if not confirmed:
        return _smoke_outcome(
            session_id, trace, False,
            "read-back did not confirm the appended row", row=row_after,
        )

    return _smoke_outcome(
        session_id, trace, True, None, row=row_after, artifact_link=link
    )


# ---------------------------------------------------------------------------
# team_mode (contracts/doctor-protocol.md full sequence — spec FR-007)
# ---------------------------------------------------------------------------


def _result(
    steps,
    bindings,
    binding_checks,
    config=None,
    scaffold_paths=None,
    report=None,
    smoke=None,
    green=False,
    failure=None,
):
    return {
        "steps": steps,
        "bindings": bindings,
        "binding_checks": binding_checks,
        "config": config,
        "scaffold_paths": scaffold_paths,
        "report": report,
        "smoke": smoke,
        "green": green,
        "failure": failure,
    }


def team_mode(mock, workspace, roster, inputs, plugin_version, manifest=None):
    """contracts/doctor-protocol.md's team-mode sequence (spec FR-007, US1
    acceptance scenarios 1-4), executed **in order**, each step appended to
    the returned ``steps`` trace so tests can assert sequence:

    (a) **Resolve bindings** (contracts/doctor-protocol.md "Resolution
        protocol") against ``roster``, via ``doctor_flows.resolve_bindings``.
        ``inputs.get("choices")`` threads through as the explicit-choice map
        for any ambiguous op.
    (b) **Store create-or-validate** (contracts/doctor-protocol.md "Store
        header create-vs-validate"): empty store (``header_store.read_header()
        is None``) -> create the header **through the resolved storage
        binding** — this step fails loudly (``RuntimeError``) if
        ``storage.append_record`` has no resolved binding entry; header
        creation without a resolved binding is forbidden. Existing header ->
        validate via ``doctor_flows._check_store_header`` (reused, never
        re-implemented) with zero writes; a mismatch **short-circuits the
        whole run** here — nothing is re-created, no further step runs
        (config write, scaffold, doctor, smoke test all skipped).
    (c) **Artifact root**: ``inputs.get("artifact_root", "battle-buddy/")`` is
        recorded for the config write below (contract v1 has no folder
        concept — establishing the root reduces to recording the location
        and later exercising writability via the smoke test, per spec
        Assumptions).
    (d) **Diary/catalog prompts**: taken verbatim from ``inputs`` (with
        fixture-plausible defaults when absent, never asserted on by name).
    (e) **Config-block write** (contracts/doctor-protocol.md "Config block"):
        the full ``bb.config.v1`` dict — ``configVersion``,
        ``pluginPin=plugin_version``, ``store``, ``diary``, ``catalog``,
        ``artifactRoot``, ``bindings`` (the just-resolved map),
        ``budgets.triageTurnCap`` (default 15), and ``shell`` only when
        ``inputs`` supplies a shell adapter name. Written onto
        ``workspace.config`` as a side effect too (so a later
        ``derive_mode(workspace)`` call reads the just-written state).
    (f) **Scaffold** (contracts/doctor-protocol.md "Workspace scaffold"):
        ``scaffold_workspace(workspace.tmp_path, config, roster)`` — exactly
        four files, zero upstream content. The written ``.mcp.json`` text is
        also recorded onto ``workspace.roster_file_text`` (T016's future
        ``roster_hash`` input).
    (g) **Doctor**: ``run_probes`` + ``check_config`` + ``check_versions`` +
        ``check_shell`` + ``assemble_report`` — the same functions a
        standalone `/doctor` run uses, over this workspace's mock/config/
        header_store/catalog_path/shell_adapter. A non-green report
        short-circuits here (config write and scaffold have already
        happened — a doctor failure at this point is reported, not
        unwound).
    (h) **Smoke test** (contracts/doctor-protocol.md "Smoke test"):
        ``smoke_test(mock, bindings, artifact_root, opened_date)`` —
        ``inputs.get("opened_date")`` (default a fixed hermetic date, no wall
        clock).

    Returns a result dict: ``{"steps", "bindings", "binding_checks",
    "config", "scaffold_paths", "report", "smoke", "green", "failure"}``.
    On an early short-circuit (header mismatch, or a non-green doctor
    report), fields past the failure point are ``None``/absent and
    ``"green"`` is ``False`` with ``"failure"`` naming why.
    """
    inputs = inputs or {}
    if manifest is None:
        manifest = _load_manifest()

    workspace.roster = roster
    steps = []

    # --- (a) resolve bindings ------------------------------------------------
    bindings, binding_checks = doctor_flows.resolve_bindings(
        manifest, roster, choices=inputs.get("choices")
    )
    steps.append(
        {"step": "resolve_bindings", "bindings": dict(bindings), "checks": binding_checks}
    )

    # --- (b) store create-or-validate ---------------------------------------
    header = workspace.header_store.read_header()
    if header is None:
        storage_tool = bindings.get("storage.append_record")
        if storage_tool is None:
            raise RuntimeError(
                "cannot create the store header: storage.append_record has "
                "no resolved binding — header creation without a resolved "
                "binding is forbidden (contracts/doctor-protocol.md 'Store "
                "header create-vs-validate')"
            )
        created_header = workspace.header_store.create_header(doctor_fixtures.EXPECTED_HEADER)
        steps.append(
            {
                "step": "store_header",
                "action": "create",
                "via_binding": storage_tool,
                "header": created_header,
            }
        )
    else:
        header_check = doctor_flows._check_store_header(workspace.header_store)
        steps.append({"step": "store_header", "action": "validate", "check": header_check})
        if header_check["status"] != "ok":
            return _result(
                steps, bindings, binding_checks,
                failure=header_check["detail"],
            )

    # --- (c) artifact root ---------------------------------------------------
    artifact_root = inputs.get("artifact_root", _DEFAULT_ARTIFACT_ROOT)
    if not artifact_root.endswith("/"):
        artifact_root += "/"
    steps.append({"step": "artifact_root", "artifact_root": artifact_root})

    # --- (d) diary/catalog prompts -------------------------------------------
    diary_url = inputs.get("diary_url", _DEFAULT_DIARY_URL)
    catalog_repo = inputs.get("catalog_repo", _DEFAULT_CATALOG_REPO)
    steps.append(
        {"step": "diary_catalog_prompts", "diary_url": diary_url, "catalog_repo": catalog_repo}
    )

    # --- (e) config-block write -----------------------------------------------
    config = {
        "configVersion": "bb.config.v1",
        "pluginPin": plugin_version,
        "store": {
            "url": inputs.get("store_url", _DEFAULT_STORE_URL),
            "schemaVersion": store_flows.SCHEMA_VERSION,
        },
        "diary": {"url": diary_url},
        "catalog": {"repo": catalog_repo},
        "artifactRoot": artifact_root,
        "bindings": dict(bindings),
        "budgets": {"triageTurnCap": inputs.get("triage_turn_cap", _DEFAULT_TRIAGE_TURN_CAP)},
    }
    if inputs.get("shell_adapter_name"):
        config["shell"] = {"adapter": inputs["shell_adapter_name"]}
    workspace.config = config
    steps.append({"step": "config_write", "config": config})

    # --- (f) scaffold ----------------------------------------------------------
    scaffold_paths, mcp_text = scaffold_workspace(workspace.tmp_path, config, roster)
    workspace.roster_file_text = mcp_text
    steps.append(
        {"step": "scaffold", "paths": {name: str(p) for name, p in scaffold_paths.items()}}
    )

    # --- (g) doctor --------------------------------------------------------------
    probe_checks = doctor_flows.run_probes(mock)
    config_checks = doctor_flows.check_config(
        mock, config, workspace.header_store, workspace.catalog_path
    )
    version_checks = doctor_flows.check_versions(config, plugin_version)
    shell_check = doctor_flows.check_shell(config, workspace.shell_adapter)
    report = doctor_flows.assemble_report(
        binding_checks, probe_checks, config_checks, version_checks, shell_check,
        manifest, bindings,
    )
    steps.append({"step": "doctor", "report": report})

    if report["outcome"] != "green":
        return _result(
            steps, bindings, binding_checks,
            config=config, scaffold_paths=scaffold_paths, report=report,
            failure="doctor report outcome red — see report['checks'] for detail",
        )

    # --- (h) smoke test ------------------------------------------------------------
    opened_date = inputs.get("opened_date", _DEFAULT_OPENED_DATE)
    smoke = smoke_test(mock, bindings, artifact_root, opened_date)
    steps.append({"step": "smoke_test", "result": smoke})

    return _result(
        steps, bindings, binding_checks,
        config=config, scaffold_paths=scaffold_paths, report=report, smoke=smoke,
        green=smoke["green"],
        failure=None if smoke["green"] else smoke["failure"],
    )


# ---------------------------------------------------------------------------
# Extension points — not implemented in this task (see module docstring)
# ---------------------------------------------------------------------------


def responder_mode(mock, workspace, plugin_version):
    """T017's scope (US3): provision/verify this responder's tokens via
    probes under their own credentials and write the green stamp, creating no
    team resources. Not implemented here — ``derive_mode`` already routes a
    config-present, stamp-missing-or-stale workspace to ``"responder"`` mode;
    this function is the mode's executable body."""
    raise NotImplementedError("responder_mode is T017's scope (US3)")


def validate_existing(mock, workspace):
    """T020's scope (US4 idempotence): validate every existing team-scope
    resource (store header, config, bindings, stamp) with zero writes, and
    surface a malformed config block as an explicit repair case rather than
    re-creating over it. Not implemented here — team_mode's own store
    create-or-validate branch (b) is the only validation this task needs."""
    raise NotImplementedError("validate_existing is T020's scope (US4)")
