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
(``team_mode``, ``scaffold_workspace``, ``smoke_test``). T016/T017 (US3) add
the green stamp's wiring: ``team_mode``'s doctor step now writes it via
``doctor_flows.write_stamp_if_green`` on a green report, and ``responder_mode``
is now implemented for real (probe checks against the existing team scope,
optional binding drift re-check, stamp write on green — see its own
docstring). ``Workspace.probes_ok``/``stamp_state`` remain caller-supplied,
test-injectable fields (see ``compute_stamp_state`` for the optional
real-caller convenience that populates ``stamp_state`` from
``doctor_flows.evaluate_stamp``; slice 5's `/page` preflight is its real,
live caller).

T020 (US4, idempotence) delivers the remaining three modes' real
implementations, plus one addition to ``derive_mode`` itself:

- ``derive_mode`` gains a **team-partial** row, inserted *before* the
  responder check: a config-present workspace whose ``roster`` is non-empty
  but whose store header is still missing routes here rather than to
  responder or already-set-up (contracts/doctor-protocol.md "Setup mode
  derivation"'s "Partial team state" note). See the function's own docstring
  for why this is gated on a non-empty roster — it's what keeps every
  T012/T017 responder/already-set-up test green unchanged.
- ``validate_existing`` — the **already-set-up** path: read-only,
  doctor-style validation (config, version, probe, optional binding-drift,
  shell checks) assembled into a ``bb.doctor.report.v1``-shaped summary;
  deliberately never refreshes the green stamp (see its own docstring for
  why that's responder scope, not this path's).
- ``resume_partial`` — the **team-partial** path: creates only whichever
  team-scope artifact is genuinely missing (currently: the store header,
  through the config's already-committed ``storage.append_record`` binding
  — never a fresh resolution — and any scaffold file absent from
  ``workspace.tmp_path``), validates whatever's already present, and closes
  with the same read-only validation ``validate_existing`` performs.
- ``repair_report`` — the **repair** path: names the malformed config's
  parse error via ``doctor_flows._check_config_wellformed`` and performs no
  operation whatsoever — team mode must never run over a malformed config,
  no matter how empty the rest of the workspace looks (the spec edge case's
  exact trap).
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
# Same determinism discipline for the green stamp's diagnostic-only "at"
# field (contracts/doctor-protocol.md "Green stamp"; T016) — a caller that
# doesn't care passes nothing and gets this fixed ISO 8601 fallback; tests
# that DO care pass their own via `inputs["at"]` (team_mode) or the explicit
# `at` argument (responder_mode).
_DEFAULT_STAMP_AT = "2026-01-01T00:00:00Z"


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

    Fully implemented here: **team** (no config block), **repair** (config
    present but malformed — never treated as absent, contracts/
    doctor-protocol.md "Malformed config block"), **team-partial** (T020,
    US4 scenario 2), and the **responder** / **already-set-up** split.

    **team-partial** (T020): contracts/doctor-protocol.md's "Partial team
    state (e.g. config present, store header missing) does only what is
    missing" note, refined into its own mode row so a caller dispatches to
    ``resume_partial`` rather than ``responder_mode``/``validate_existing``.
    The check: ``workspace.roster`` is non-empty AND
    ``workspace.header_store.read_header()`` is ``None``.

    JUDGMENT CALL — gated on a non-empty roster: a bare
    ``Workspace(config=...)`` built for a T012/T017-era responder/
    already-set-up test never populates ``roster`` (it defaults to ``{}``) —
    that's simply "no roster information supplied to this call," not "the
    team's store header is genuinely missing." Without a roster there is
    nothing ``resume_partial`` could create the header *through* anyway
    (creating it "through the config's already-committed storage binding"
    presumes a roster that binding was resolved against in the first place)
    — so an empty roster conservatively falls through to the existing
    responder/already-set-up split exactly as T012/T017 left it. This is
    precisely what keeps
    ``test_derive_mode_config_present_stamp_missing_is_responder`` (T012)
    and the "valid team scope" responder-mode tests (T017) green unchanged:
    both either supply no roster or supply one whose header is already
    present, so neither ever satisfies this new check.

    A malformed config is checked *before* team-partial and always wins —
    "config present but malformed" must never be read as "config present,
    team-scope artifact missing" (see ``repair_report``).

    Below team-partial, the **responder** / **already-set-up** split is
    unchanged from T012/T017: a config-present workspace is responder mode
    whenever ``workspace.probes_ok`` is false or ``workspace.stamp_state``
    isn't ``"fresh"`` (which — given ``stamp_state``'s ``"missing"``
    default — means "config present, no stamp yet" reads as responder,
    exactly the table's "stamp missing or stale" row); otherwise
    already-set-up.

    JUDGMENT CALL (T017, restated): ``stamp_state``/``probes_ok`` stay
    exactly the bare, caller-supplied ``Workspace`` fields T012 left them
    as — ``derive_mode`` never evaluates a real stamp itself. Actually
    evaluating one (filesystem read + roster re-hash) is a side-effecting
    step a real caller performs once and feeds in via ``stamp_state``, not
    something a pure mode-derivation predicate should do on every call;
    ``responder_mode`` (T017) and the module-level ``compute_stamp_state``
    convenience are where ``doctor_flows.evaluate_stamp`` actually gets
    used.
    """
    config = workspace.config

    if config is None:
        return "team"

    if not isinstance(config, dict):
        # Malformed (e.g. a caught json.JSONDecodeError passed straight
        # through — doctor_flows.check_config's own convention). A repair
        # case, never "no config" — team mode must never re-create resources
        # over a typo. Checked before team-partial: malformed always wins.
        return "repair"

    if workspace.roster and workspace.header_store.read_header() is None:
        # T020: config present, a roster to resolve/create against exists,
        # and the store header is genuinely missing — team-partial, never
        # responder/already-set-up (contracts/doctor-protocol.md "Partial
        # team state").
        return "team-partial"

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
    if "error" in readback:
        # Loud-and-specific discipline, same as every other smoke path: name
        # the failing op and the store's own error message.
        return _smoke_outcome(
            session_id, trace, False,
            "read_records failed: {}".format(readback["error"].get("message")),
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
    stamp_path=None,
    stamp_wrote=False,
    roster_hash=None,
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
        # T016/FR-005: the green-stamp write this doctor step attempted —
        # `stamp_wrote` is False whenever the doctor report wasn't green,
        # regardless of what happens afterwards (the smoke test is
        # team-mode's own additional gate on top of "doctor green").
        "stamp_path": stamp_path,
        "stamp_wrote": stamp_wrote,
        "roster_hash": roster_hash,
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
        unwound). Immediately after assembling the report, this step also
        calls ``doctor_flows.write_stamp_if_green`` (T016, FR-005) at
        ``<workspace.tmp_path>/.bb-doctor-stamp.json``, using
        ``doctor_flows.roster_hash(workspace.roster_file_text)`` (the
        ``.mcp.json`` text step (f) just wrote) and ``inputs.get("at", ...)``
        for the diagnostic timestamp — gated on *this* report's own outcome,
        never on the smoke test below (see the inline comment at the call
        site for why).
    (h) **Smoke test** (contracts/doctor-protocol.md "Smoke test"):
        ``smoke_test(mock, bindings, artifact_root, opened_date)`` —
        ``inputs.get("opened_date")`` (default a fixed hermetic date, no wall
        clock).

    Returns a result dict: ``{"steps", "bindings", "binding_checks",
    "config", "scaffold_paths", "report", "smoke", "green", "failure",
    "stamp_path", "stamp_wrote", "roster_hash"}``. On an early short-circuit
    (header mismatch, or a non-green doctor report), fields past the failure
    point are ``None``/absent and ``"green"`` is ``False`` with ``"failure"``
    naming why. ``stamp_path``/``stamp_wrote``/``roster_hash`` are ``None``/
    ``False`` on the header-mismatch short-circuit (the doctor step never
    ran) and reflect the doctor step's own outcome on every other path,
    independent of the smoke test's own result (T016, FR-005).
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

    # --- (g.1) green stamp (contracts/doctor-protocol.md "Green stamp";
    # FR-005 — this task, T016, is the rule's owner). Gated on *this* doctor
    # step's own report outcome alone, never on the smoke test below: FR-005
    # is "a green doctor run", and the doctor report's own outcome rule is
    # exactly what that means; the smoke test is team-mode's own additional
    # end-to-end gate layered on top, not part of the stamp's gate. Recorded
    # onto the existing "doctor" step entry (not a new step) so the
    # documented eight-step sequence (resolve_bindings .. smoke_test) is
    # unchanged.
    roster_hash_value = doctor_flows.roster_hash(workspace.roster_file_text)
    stamp_path = Path(workspace.tmp_path) / ".bb-doctor-stamp.json"
    stamp_at = inputs.get("at", _DEFAULT_STAMP_AT)
    stamp_wrote = doctor_flows.write_stamp_if_green(
        report, stamp_path, plugin_version, roster_hash_value, stamp_at
    )
    steps.append(
        {
            "step": "doctor",
            "report": report,
            "stamp_path": str(stamp_path),
            "stamp_wrote": stamp_wrote,
            "roster_hash": roster_hash_value,
        }
    )

    if report["outcome"] != "green":
        return _result(
            steps, bindings, binding_checks,
            config=config, scaffold_paths=scaffold_paths, report=report,
            failure="doctor report outcome red — see report['checks'] for detail",
            stamp_path=stamp_path, stamp_wrote=stamp_wrote, roster_hash=roster_hash_value,
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
        stamp_path=stamp_path, stamp_wrote=stamp_wrote, roster_hash=roster_hash_value,
    )


# ---------------------------------------------------------------------------
# Extension points — not implemented in this task (see module docstring)
# ---------------------------------------------------------------------------


def responder_mode(mock, workspace, plugin_version, at):
    """T017 (US3, FR-008): responder-mode `/setup` — verify this responder's
    own probes under their *current* credentials against the already-existing
    team scope, and write the local green stamp on success. Creates no team
    resources whatsoever: ``derive_mode`` already routes a config-present,
    stamp-missing-or-stale workspace here (team scope — config, store header,
    bindings — travels with the cloned repo; what's missing is this
    responder's own scope).

    ``mock``: the MCP surface reachable *under this responder's own
    credentials* — a plain mock, or a ``doctor_fixtures.FailingProbeInjector``
    standing in for a responder-credential/permission failure on one
    capability (spec edge case: "Probe fails under this responder's
    credentials while the committed binding map is valid"). ``workspace``:
    the already-committed team scope this mode only ever reads
    (``workspace.config``, ``workspace.header_store``,
    ``workspace.catalog_path``, and — see judgment call below —
    ``workspace.roster``/``workspace.roster_file_text``). ``at``: caller-
    supplied ISO 8601 timestamp for the stamp (hermetic — no wall clock;
    mirrors ``team_mode``'s own ``inputs["at"]``).

    Steps, every one of them read-only:

    (a) ``doctor_flows.run_probes(mock)`` — one ``probe``-kind check per
        required capability, run under *this* responder's credentials. A
        capability whose credentials are rejected fails here with kind
        ``"probe"`` — **never** ``"binding"``: this mode never re-resolves
        bindings at all (they're team scope, already committed; FR-008 only
        ever asks this mode to provision/verify *this responder's* tokens).
    (b) JUDGMENT CALL — optional binding drift re-check: bindings are team
        scope and this mode has no business re-*resolving* them. But the
        spec edge case above is only observable in a report if that report
        can show a *still-valid* committed binding map alongside a *failing*
        responder-scope probe in the same run — so when ``workspace.config``
        is a dict carrying a ``"bindings"`` map and ``workspace.roster`` is
        non-empty, this function additionally runs
        ``doctor_flows.revalidate_bindings`` (drift re-*validation*, never
        resolution) over the committed map, purely so the report can
        distinguish the two failure kinds side by side. When either is
        absent, no ``binding``-kind checks appear at all — never required
        for this mode to run.
    (c) ``doctor_flows.check_config(mock, workspace.config,
        workspace.header_store, workspace.catalog_path)`` — the same store/
        diary/catalog config checks doctor runs, against the *existing*
        workspace state (never a create path: ``check_config`` only ever
        calls ``header_store.read_header()``, never ``create_header``).
    (d) ``doctor_flows.assemble_report`` over exactly these check families
        (binding [from (b), maybe empty], probe [from (a)], config [from
        (c)]) plus empty version checks and no shell check — version-seam
        and shell-notify are team-scope/doctor concerns this mode doesn't
        touch (matches the task's own "probe checks + config checks"
        scope). ``manifest`` is the real shipped
        ``manifest/capabilities.json`` (mirrors ``team_mode``).
    (e) On a green report: write the stamp via
        ``doctor_flows.write_stamp_if_green`` at
        ``<workspace.tmp_path>/.bb-doctor-stamp.json`` (same location
        ``team_mode`` uses), hashing ``workspace.roster_file_text`` (the
        committed ``.mcp.json`` text this responder cloned) — or an
        empty-roster hash when the workspace carries no roster text at all
        (a workspace fixture that never set it; ``roster_hash`` treats a
        missing ``"mcpServers"`` key as an empty map rather than raising).

    Creates no team resources: ``workspace.header_store.create_header`` is
    never called, ``workspace.config`` is only ever read, ``scaffold_workspace``
    is never called, and every mock call this function makes
    (``run_probes``'s/``check_config``'s own calls) is read-shaped — so a
    caller's ``mock.write_log`` is provably unchanged across a
    ``responder_mode`` run (US3 "no mutating operation touches team
    resources").

    Returns ``{"report", "stamp_path", "stamp_wrote", "roster_hash"}``.
    """
    manifest = _load_manifest()
    config = workspace.config

    probe_checks = doctor_flows.run_probes(mock)

    binding_checks = []
    if isinstance(config, dict) and config.get("bindings") and workspace.roster:
        binding_checks = doctor_flows.revalidate_bindings(
            config["bindings"], workspace.roster, manifest
        )

    config_checks = doctor_flows.check_config(
        mock, config, workspace.header_store, workspace.catalog_path
    )

    bindings = config.get("bindings", {}) if isinstance(config, dict) else {}
    report = doctor_flows.assemble_report(
        binding_checks, probe_checks, config_checks, [], None, manifest, bindings,
    )

    roster_text = (
        workspace.roster_file_text if workspace.roster_file_text is not None else "{}"
    )
    roster_hash_value = doctor_flows.roster_hash(roster_text)
    stamp_path = Path(workspace.tmp_path) / ".bb-doctor-stamp.json"
    stamp_wrote = doctor_flows.write_stamp_if_green(
        report, stamp_path, plugin_version, roster_hash_value, at
    )

    return {
        "report": report,
        "stamp_path": stamp_path,
        "stamp_wrote": stamp_wrote,
        "roster_hash": roster_hash_value,
    }


def compute_stamp_state(stamp_path, plugin_version, current_roster_hash):
    """Optional convenience (T016 extension point) for a real caller
    populating ``Workspace.stamp_state`` — which stays ``derive_mode``'s
    plain, test-injectable field, exactly as T012 left it; this function is
    never called by ``derive_mode``/``team_mode``/``responder_mode``
    themselves. It wraps ``doctor_flows.evaluate_stamp`` and returns just the
    two-value vocabulary ``derive_mode`` reads (``"fresh"`` / ``"stale"``),
    discarding the human-readable reason (a caller that wants the reason too
    should call ``doctor_flows.evaluate_stamp`` directly).

    Slice 5's `/page` preflight is the real, live caller of this path: it
    reads the on-disk stamp, computes the current roster hash, and uses
    exactly this fresh/stale result to decide whether to auto-run
    ``responder_mode``. Nothing in this slice calls it automatically —
    keeping ``derive_mode`` a pure inspection over whatever
    ``Workspace.stamp_state`` already holds is what keeps it hermetic and
    test-injectable.
    """
    status, _reason = doctor_flows.evaluate_stamp(
        stamp_path, plugin_version, current_roster_hash
    )
    return status


def _read_only_validation_report(mock, workspace, plugin_version):
    """Shared read-only doctor-style validation, used by both
    ``validate_existing`` (already-set-up) and ``resume_partial``'s closing
    step (team-partial): config checks (well-formedness, store header,
    diary, catalog — ``doctor_flows.check_config``), the version-seam checks
    (``check_versions``), the read-shaped probes (``run_probes``), the
    optional binding-drift re-check (``revalidate_bindings`` — included only
    when ``workspace.config`` carries a ``"bindings"`` map and
    ``workspace.roster`` is non-empty, exactly ``responder_mode``'s (T017)
    own judgment call), and the shell round-trip/skip (``check_shell``),
    assembled into one ``bb.doctor.report.v1``-shaped report
    (``assemble_report``).

    Every function this calls is read-only per its own doctor_flows
    docstring — this helper never writes anything (no header create, no
    config write, no scaffold write, no stamp write). Factored out once both
    T020 entry points needed the identical assembly.
    """
    manifest = _load_manifest()
    config = workspace.config

    config_checks = doctor_flows.check_config(
        mock, config, workspace.header_store, workspace.catalog_path
    )
    version_checks = doctor_flows.check_versions(config, plugin_version)
    probe_checks = doctor_flows.run_probes(mock)

    binding_checks = []
    if isinstance(config, dict) and config.get("bindings") and workspace.roster:
        binding_checks = doctor_flows.revalidate_bindings(
            config["bindings"], workspace.roster, manifest
        )

    shell_check = doctor_flows.check_shell(config, workspace.shell_adapter)

    bindings = config.get("bindings", {}) if isinstance(config, dict) else {}
    return doctor_flows.assemble_report(
        binding_checks, probe_checks, config_checks, version_checks, shell_check,
        manifest, bindings,
    )


def validate_existing(mock, workspace, plugin_version):
    """T020 (US4 scenario 1, FR-009): the **already-set-up** path — every
    existing team-scope resource is validated with zero writes, and the
    result is a doctor-style summary report, in exactly the
    ``bb.doctor.report.v1`` shape a standalone `/doctor` run produces
    (contracts/doctor-protocol.md "Doctor report").

    Delegates the entire check assembly to ``_read_only_validation_report``
    (config/version/probe/optional-binding-drift/shell), so this function
    itself never calls ``workspace.header_store.create_header``, never
    writes ``workspace.config``, never calls ``scaffold_workspace``, and
    never runs ``smoke_test`` — the caller's ``mock.write_log`` and
    ``workspace.header_store.write_log`` are provably unchanged across a run
    (SC-005).

    JUDGMENT CALL — no stamp refresh: a green ``validate_existing`` run
    deliberately does **not** call ``doctor_flows.write_stamp_if_green``.
    Stamp freshness is responder scope (FR-005/FR-008), owned by
    ``responder_mode`` — and ``derive_mode`` already only ever reaches
    "already-set-up" once ``workspace.stamp_state == "fresh"``, so by
    construction there is nothing here that needs refreshing. Re-stamping on
    every already-set-up validation run would blur the boundary between
    team-scope validation (this function) and responder-scope stamp
    ownership (``responder_mode``), and would advance the stamp's ``at``
    field on a run that touched nothing — undermining its own "diagnostic,
    never expiry-checked" contract the moment anything ever mistook stamp
    recency for validation recency.

    Returns ``{"mode": "already-set-up", "report": report, "green": bool}``.
    """
    report = _read_only_validation_report(mock, workspace, plugin_version)
    return {
        "mode": "already-set-up",
        "report": report,
        "green": report["outcome"] == "green",
    }


def resume_partial(mock, workspace, roster, inputs, plugin_version):
    """T020 (US4 scenario 2, contracts/doctor-protocol.md "Partial team
    state"): the **team-partial** resumption path — the config block is
    already present and well-formed (a malformed config never reaches here;
    ``derive_mode`` checks that first, and always routes it to
    ``repair_report`` instead), but at least one other team-scope artifact
    is genuinely missing. Creates ONLY the missing piece(s); everything
    already present is validated, never re-created.

    Currently-recognized team-scope artifacts (contracts/doctor-protocol.md
    "Store header create-vs-validate" + "Workspace scaffold"):

    (a) **Store header** — create-or-validate, exactly team_mode's own
        branch (b), with one deliberate difference: the storage binding used
        to create it comes from ``workspace.config["bindings"]`` — the
        config's already-committed team-scope binding map — **never** a
        fresh ``doctor_flows.resolve_bindings`` call. The binding map is
        team scope and already exists in this state (that is exactly what
        "config present" means here); re-resolving it would be a second,
        possibly-diverging resolution of something already committed, not a
        resumption of what's actually missing.
    (b) **Scaffold files** — each of the four ``scaffold_workspace`` files
        under ``workspace.tmp_path`` is created only if absent (using the
        same per-file content ``scaffold_workspace`` itself would write,
        built from this same ``config``/``roster``) and left untouched if
        already present. ``scaffold_workspace`` itself has no partial-write
        mode — every call rewrites all four unconditionally — so this
        duplicates its per-file content generation rather than calling it
        outright; that is what lets an already-present file survive a
        resumption completely untouched.

    JUDGMENT CALL — "config block absent-fields" is out of scope for this
    task: a well-formed config dict missing one of contracts/
    doctor-protocol.md's documented keys is not checked or repaired here.
    Reaching this function at all already implies ``isinstance(config,
    dict)`` (a malformed config routes to ``repair_report`` before
    ``derive_mode`` ever considers team-partial), and no spec scenario,
    fixture, or existing test pins what a partially-populated-but-
    well-formed config dict looks like — inventing a repair shape for it
    here would be speculative, untested surface. The two artifacts above are
    the ones US4 scenario 2's own example ("config present, store header
    missing") and contracts/doctor-protocol.md's "Workspace scaffold"
    section actually pin.

    Closes with ``_read_only_validation_report`` — the identical read-only,
    doctor-style validation ``validate_existing`` performs — so the returned
    report is directly comparable to ``validate_existing``'s. Never runs
    ``smoke_test``: that is team_mode's own full-sequence finish, not a
    resumption's, and the spec-pinned scenario this task targets explicitly
    excludes it.

    ``roster``: the current roster surface (mirrors ``team_mode``'s own
    explicit ``roster`` argument); also recorded onto ``workspace.roster``.
    ``inputs``: accepted for signature symmetry with ``team_mode``; nothing
    here currently reads it — there is no create-vs-validate *choice* left
    to make once the binding is already committed.

    Returns ``{"mode": "team-partial", "steps", "report", "green"}``. Never
    calls ``doctor_flows.resolve_bindings``, never writes
    ``workspace.config``, never calls ``smoke_test``.
    """
    inputs = inputs or {}
    config = workspace.config
    if not isinstance(config, dict):
        raise RuntimeError(
            "resume_partial requires an already-well-formed config block — "
            "a malformed config always routes to repair_report, never here "
            "(contracts/doctor-protocol.md 'Malformed config block')"
        )

    workspace.roster = roster
    bindings = config.get("bindings", {})
    steps = []

    # --- store header: create ONLY if missing, through the COMMITTED
    # (never freshly re-resolved) binding ---------------------------------
    header = workspace.header_store.read_header()
    if header is None:
        storage_tool = bindings.get("storage.append_record")
        if storage_tool is None:
            raise RuntimeError(
                "cannot create the store header: the committed config "
                "carries no storage.append_record binding entry — "
                "resume_partial only ever creates through an "
                "already-committed team-scope binding, never a fresh "
                "resolution (contracts/doctor-protocol.md 'Setup mode "
                "derivation' partial-team-state note)"
            )
        created_header = workspace.header_store.create_header(
            doctor_fixtures.EXPECTED_HEADER
        )
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
        steps.append(
            {"step": "store_header", "action": "validate", "check": header_check}
        )

    # --- scaffold: create only the files genuinely missing from tmp_path --
    created_files = []
    validated_files = []
    if workspace.tmp_path is not None:
        tmp_path = Path(workspace.tmp_path)
        settings_path = tmp_path / ".claude" / "settings.json"
        mcp_path = tmp_path / ".mcp.json"
        readme_path = tmp_path / "README.md"
        gitignore_path = tmp_path / ".gitignore"

        if settings_path.exists():
            validated_files.append(".claude/settings.json")
        else:
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                json.dumps({"battleBuddy": config}, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            created_files.append(".claude/settings.json")

        if mcp_path.exists():
            workspace.roster_file_text = mcp_path.read_text(encoding="utf-8")
            validated_files.append(".mcp.json")
        else:
            mcp_text = (
                json.dumps(
                    {"mcpServers": _mcp_servers_from_roster(roster)},
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            mcp_path.write_text(mcp_text, encoding="utf-8")
            workspace.roster_file_text = mcp_text
            created_files.append(".mcp.json")

        if readme_path.exists():
            validated_files.append("README.md")
        else:
            readme_path.write_text(_README_TEMPLATE, encoding="utf-8")
            created_files.append("README.md")

        if gitignore_path.exists():
            validated_files.append(".gitignore")
        else:
            gitignore_path.write_text(
                "\n".join(_GITIGNORE_LINES) + "\n", encoding="utf-8"
            )
            created_files.append(".gitignore")

    steps.append(
        {"step": "scaffold", "created": created_files, "validated": validated_files}
    )

    # --- close with the same read-only validation validate_existing uses --
    report = _read_only_validation_report(mock, workspace, plugin_version)
    steps.append({"step": "doctor", "report": report})

    return {
        "mode": "team-partial",
        "steps": steps,
        "report": report,
        "green": report["outcome"] == "green",
    }


def repair_report(workspace):
    """T020 (US4, edge case "Malformed config block"): the **repair** path —
    a malformed config block is surfaced explicitly, naming the exact parse
    error, and never triggers any team-mode resource creation, no matter how
    empty the rest of the workspace looks. This is the spec edge case's
    precise trap: an empty/missing store header here must NOT be read as
    "team mode's empty store," because the config itself was never readable
    to begin with — ``derive_mode`` already guarantees a malformed config
    always routes here, never to ``"team"`` or ``"team-partial"``.

    Reuses ``doctor_flows._check_config_wellformed`` — the exact same
    malformed-config check ``check_config`` runs as its own first check —
    rather than re-deriving or re-parsing anything independently, so the
    parse error named here can never drift from what a standalone `/doctor`
    run (or ``check_config`` itself) would report for the same malformed
    config.

    Performs zero operations: reads only ``workspace.config`` (to name its
    parse error); never touches ``workspace.header_store``,
    ``workspace.tmp_path``, or any mock — and is clearly not team mode: no
    resource of any kind is created or validated here.

    Returns ``{"mode": "repair", "check": <the config.wellformed check
    dict>, "green": False}``.
    """
    check = doctor_flows._check_config_wellformed(workspace.config)
    return {"mode": "repair", "check": check, "green": False}
