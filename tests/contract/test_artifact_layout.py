"""US5 artifact layout (spec AS-1..AS-3, FR-004).

Drives ``store_flows.close_session`` / ``store_flows.write_checkpoint`` — the
executable form of ``skills/session-store/SKILL.md``'s "Artifact layout" section
(plus the close-flow and checkpoint sections it cross-references) — against the
mock artifact store, asserting on ``mock.artifacts.files`` / ``get_file`` results
and the row's ``artifacts_folder_url``/``links`` fields — never prose.

AS-1 proves presence, not exclusivity: the four canonical names land under the
session's folder-qualified prefix, and a mid-session checkpoint overflow's
``checkpoint-<seq>.json`` coexists there without upsetting that assertion. AS-2
proves the local-name -> uploaded-name mapping is deliberate (``trace.jsonl`` ->
``tool-trace.jsonl``, ``staging/transcript.md`` -> ``transcript.md``), not an
accidental pass-through. AS-3 proves regenerability (FR-4d/FR-4e, Constitution
IV): the row's ``links`` are well-formed ``{url, excerpt}`` pairs, every link
resolves to the exact uploaded content, and the four canonical artifacts are
reconstructable from the row alone — even after the local state directory
(marker + staging) is gone.
"""

import json
import shutil

from conftest import fixture_path
from helpers import store_flows

CHECKPOINTS_DIR = ("store", "checkpoints")

OPEN_FIELDS = dict(
    fingerprint="c" * 16,
    catalog_resolved=True,
    alert_signature="checkout-api: high latency",
    services=["checkout-api"],
    severity="sev2",
    responder="alice @ 2026-07-20T09:00:00Z",
    started_at="2026-07-20T09:00:00Z",
)

RESPONDER = OPEN_FIELDS["responder"]

CLOSE_FIELDS = dict(
    closed_at="2026-07-20T10:00:00Z",
    timeline=[{"at": "2026-07-20T09:05:00Z", "event": "triage started"}],
    root_cause="deploy rollback race",
    resolution="rolled back to previous revision",
    runbook_refs=[],
    report_url=None,
)

# SKILL.md "Artifact layout" -> "The four documented artifacts": the canonical
# set, keyed by the local staging name close_session's mapping expects (report
# has no local-staged counterpart — it uploads verbatim, per the mapping table).
STAGED_ARTIFACTS = {
    "staging/transcript.md": "# transcript\n...",
    "trace.jsonl": '{"seq": 1}\n',
    "staging/checkpoints.jsonl": '{"seq": 0}\n',
    "report.md": "# Report\n\nRegenerated content.\n",
}

CANONICAL_ARTIFACT_NAMES = ("transcript.md", "tool-trace.jsonl", "checkpoints.jsonl", "report.md")


def _open(mock, tmp_path, source_id="ALERT-ARTIFACTS", **overrides):
    fields = dict(OPEN_FIELDS)
    fields.update(overrides)
    return store_flows.open_session(
        mock, tmp_path, "incident", source_id, "2026-07-20", **fields
    )


def _row(mock, session_id):
    return mock.invoke(
        "storage", "read_records", {"filter": {"session_id": session_id}}
    )["records"][0]


def _load_checkpoint(name):
    with open(str(fixture_path(*CHECKPOINTS_DIR, name)), encoding="utf-8") as f:
        return json.load(f)


def _serialize(doc):
    # Mirrors store_flows._serialize_checkpoint's pinned convention exactly.
    return json.dumps(doc, sort_keys=True, separators=(",", ":"))


def _pad_to_length(template, target_len):
    doc = json.loads(json.dumps(template))  # deep copy
    base_len = len(_serialize(doc))
    delta = target_len - base_len
    if delta < 0:
        raise ValueError(
            "template already exceeds target_len %d (base %d)" % (target_len, base_len)
        )
    doc["hypotheses"][0]["evidence_for"][0]["excerpt"] += "a" * delta
    assert len(_serialize(doc)) == target_len
    return doc


def _artifact_names(mock):
    return [f["name"] for f in mock.artifacts.files.values()]


# ---------------------------------------------------------------------------
# AS-1: full close -> four canonical names land under the session's
# folder-qualified prefix (presence, not exclusivity); an overflowed
# mid-session checkpoint's checkpoint-<seq>.json coexists without upsetting
# the canonical-four assertion.
# ---------------------------------------------------------------------------


def test_as1_close_uploads_four_canonical_names_overflow_coexists(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path)
    session_id = open_out["session_id"]
    prefix = "battle-buddy/{}/".format(session_id)

    # Mid-session overflowed checkpoint (SKILL.md "Checkpoints" -> "Cell
    # guard") — its own checkpoint-<seq>.json lands under the same
    # folder-qualified prefix, at write time, before /close ever runs.
    guard = mock_mcp.schema_registry.constants["single_field_limit_chars"]
    oversize_doc = _pad_to_length(_load_checkpoint("oversize-template.json"), guard + 500)
    ckpt_outcome = store_flows.write_checkpoint(
        mock_mcp, tmp_path, session_id, [oversize_doc], responder=RESPONDER, seq=1
    )
    assert ckpt_outcome["overflowed"] is True

    close_out = store_flows.close_session(
        mock_mcp,
        tmp_path,
        session_id,
        close_fields=CLOSE_FIELDS,
        diary_content="closing out the incident",
        staged_artifacts=STAGED_ARTIFACTS,
    )
    assert close_out["marker_cleared"] is True

    all_names = _artifact_names(mock_mcp)

    # Folder-qualification: every artifact this session produced — close-flow
    # uploads AND the mid-session overflow — lives under the same prefix.
    assert all_names  # sanity: something actually uploaded
    assert all(name.startswith(prefix) for name in all_names)

    # Presence: the four documented names exist under the prefix...
    for artifact_name in CANONICAL_ARTIFACT_NAMES:
        assert prefix + artifact_name in all_names

    # ...not exclusivity: the overflow file is expected company, not a
    # conformance violation, and the canonical-four check above still holds
    # with it present.
    assert prefix + "checkpoint-1.json" in all_names
    assert len(all_names) == len(CANONICAL_ARTIFACT_NAMES) + 1


# ---------------------------------------------------------------------------
# AS-2: the local -> uploaded name mapping is deliberate, not accidental —
# trace.jsonl -> tool-trace.jsonl, staging/transcript.md -> transcript.md.
# ---------------------------------------------------------------------------


def test_as2_local_to_uploaded_name_mapping_is_deliberate(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path)
    session_id = open_out["session_id"]
    prefix = "battle-buddy/{}/".format(session_id)

    close_out = store_flows.close_session(
        mock_mcp,
        tmp_path,
        session_id,
        close_fields=CLOSE_FIELDS,
        diary_content="closing out the incident",
        staged_artifacts=STAGED_ARTIFACTS,
    )

    all_names = _artifact_names(mock_mcp)

    # trace.jsonl -> tool-trace.jsonl: the mapped name is present...
    assert prefix + "tool-trace.jsonl" in all_names
    # ...and the local staging name never appears as an uploaded artifact,
    # qualified or not — a documented mapping, not an accidental pass-through.
    assert prefix + "trace.jsonl" not in all_names
    assert "trace.jsonl" not in all_names

    # staging/transcript.md -> transcript.md: same shape.
    assert prefix + "transcript.md" in all_names
    assert prefix + "staging/transcript.md" not in all_names
    assert "staging/transcript.md" not in all_names

    # Cross-checked against close_session's own outcome mapping.
    assert close_out["uploaded"]["trace.jsonl"]["uploaded_name"] == "tool-trace.jsonl"
    assert close_out["uploaded"]["staging/transcript.md"]["uploaded_name"] == "transcript.md"
    assert (
        close_out["uploaded"]["staging/checkpoints.jsonl"]["uploaded_name"]
        == "checkpoints.jsonl"
    )


# ---------------------------------------------------------------------------
# AS-3: regenerability (FR-4d/FR-4e, Constitution IV) — every link is a
# well-formed {url, excerpt} pair, every link resolves to the exact uploaded
# content, and the four canonical artifacts are reconstructable from the row
# alone, even with the local state directory gone.
# ---------------------------------------------------------------------------


def test_as3_row_and_artifacts_regenerate_without_local_state(mock_mcp, tmp_path):
    open_out = _open(mock_mcp, tmp_path)
    session_id = open_out["session_id"]

    close_out = store_flows.close_session(
        mock_mcp,
        tmp_path,
        session_id,
        close_fields=CLOSE_FIELDS,
        diary_content="closing out the incident",
        staged_artifacts=STAGED_ARTIFACTS,
    )
    assert close_out["marker_cleared"] is True

    row = _row(mock_mcp, session_id)

    # (b) every links entry is a well-formed {url, excerpt} pair — exactly
    # those two keys, non-empty url (Constitution IV: evidence is never prose
    # alone).
    assert len(row["links"]) == len(STAGED_ARTIFACTS)
    for entry in row["links"]:
        assert set(entry) == {"url", "excerpt"}
        assert entry["url"]

    # (a) every link resolves via get_file to the exact content that was
    # uploaded for it.
    uploaded_name_to_content = {
        info["uploaded_name"]: STAGED_ARTIFACTS[local_name]
        for local_name, info in close_out["uploaded"].items()
    }
    for entry in row["links"]:
        fetched = mock_mcp.invoke("artifacts", "get_file", {"link": entry["url"]})
        assert fetched["content"] == uploaded_name_to_content[entry["excerpt"]]

    # Now prove none of this needed local state: the marker is already gone
    # (close cleared it) — delete the staging directory outright too, so
    # nothing on disk under tmp_path survives, then reconstruct purely from
    # the row + the artifact store.
    assert not (tmp_path / "marker.json").exists()
    staging_dir = tmp_path / "staging"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    assert not staging_dir.exists()

    folder_prefix = row["artifacts_folder_url"]
    assert folder_prefix == "battle-buddy/{}/".format(session_id)

    reconstructed = {}
    for entry in row["links"]:
        fetched = mock_mcp.invoke("artifacts", "get_file", {"link": entry["url"]})
        # (c) the full folder-qualified name is reconstructable from the row
        # alone (artifacts_folder_url + the link's excerpt), matching the
        # name the artifact actually stored under.
        assert fetched["name"] == folder_prefix + entry["excerpt"]
        reconstructed[entry["excerpt"]] = fetched["content"]

    for artifact_name in CANONICAL_ARTIFACT_NAMES:
        assert artifact_name in reconstructed

    assert reconstructed["transcript.md"] == STAGED_ARTIFACTS["staging/transcript.md"]
    assert reconstructed["tool-trace.jsonl"] == STAGED_ARTIFACTS["trace.jsonl"]
    assert reconstructed["checkpoints.jsonl"] == STAGED_ARTIFACTS["staging/checkpoints.jsonl"]
    assert reconstructed["report.md"] == STAGED_ARTIFACTS["report.md"]
