"""SC-003 / FR-010 / research R6: the investigation skill's documented
spawn-flow write into the local-state protocol's ``agents.json`` — proven
protocol-conforming without any production writer existing yet (no spawn
step lands until slice 5's lifecycle commands invoke these agents).

Layer boundary (research R6's reuse note): ``tests/unit/test_local_state_protocol.py``
already covers ``agents.json`` from ``hooks/_state.py``'s *read* side —
``read_roles``/``role_for`` parsing a hand-written file, fail-open on an
unregistered actor, and malformed-file tolerance. That module owns those
behaviors; this one does not re-test them. What is untested elsewhere is the
*write* side ``skills/investigation/SKILL.md``'s "Spawn flow and role
registration" section documents (merge-into-``roles``, never rewrite other
entries) and whether that documented write's output is shape-conformant to
the protocol — no importable public write helper exists in ``hooks/_state.py``
for ``agents.json`` (only read helpers are shipped there; a
production writer is future work per research R6), so this module implements
``registration_write`` standalone, as a simulation of the documented flow,
and validates its output against ``check_registration_shape``.

Role vocabulary under test is derived from the shipped agent docs, never
hardcoded literals (converge finding, FR-012 assert-on-artifacts): ``triage``
and ``deep`` are justified by the existence of ``agents/triage.md`` and
``agents/deep-investigator.md``; each ``specialist:<stem>`` role is computed
from the remaining ``agents/*.md`` filenames.
"""

import json
import os
import re

import pytest

import _state
from conftest import REPO_ROOT

AGENTS_DIR = REPO_ROOT / "agents"
TRIAGE_DOC = AGENTS_DIR / "triage.md"
DEEP_INVESTIGATOR_DOC = AGENTS_DIR / "deep-investigator.md"

ROLE_RE = re.compile(r"^(triage|deep|specialist:[a-z0-9-]+)$")


# ---------------------------------------------------------------------------
# The documented write (SKILL.md "Spawn flow and role registration"):
# read agents.json if present (else start the empty-roles shape), merge the
# new entry, write back. No file locking here — the protocol's own writer
# (hooks/_state.py) owns durability concerns for its own files; this
# simulates only the *shape* of the documented merge, which is what SC-003
# and FR-010 require proving.
# ---------------------------------------------------------------------------


def registration_write(state_dir, actor_key, role):
    """Simulate the SKILL-documented spawn-flow write into ``agents.json``.

    ``state_dir`` is the ``.bb-session``-equivalent directory that directly
    contains (or will contain) ``agents.json`` — the caller supplies a temp
    dir, never a real session. Returns the merged document that was written.
    """
    path = os.path.join(str(state_dir), "agents.json")
    doc = None
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, ValueError):
            doc = None
    if not isinstance(doc, dict):
        doc = {"protocol": _state.PROTOCOL, "roles": {}}
    doc.setdefault("protocol", _state.PROTOCOL)
    roles = doc.get("roles")
    if not isinstance(roles, dict):
        roles = {}
    roles = dict(roles)  # merge, never mutate-in-place over a shared ref
    roles[actor_key] = role
    doc["roles"] = roles
    if not os.path.isdir(str(state_dir)):
        os.makedirs(str(state_dir))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    return doc


def check_registration_shape(doc):
    """Return a list of violation strings for a registration document
    (empty ⇒ conformant). No key-grammar assertion on actor keys — key
    derivation is the deterministic layer's unowned surface here (analyze
    U2); only non-empty-string-ness is checked.
    """
    violations = []
    if not isinstance(doc, dict):
        return ["doc.not_object"]
    if doc.get("protocol") != _state.PROTOCOL:
        violations.append("protocol.mismatch:%r" % (doc.get("protocol"),))
    roles = doc.get("roles")
    if not isinstance(roles, dict):
        violations.append("roles.not_object:%r" % (roles,))
        return violations
    for key, value in roles.items():
        if not isinstance(key, str) or not key.strip():
            violations.append("roles.key.not_nonempty_string:%r" % (key,))
        if not isinstance(value, str) or not ROLE_RE.match(value):
            violations.append("roles.value.invalid:%r" % (value,))
    return violations


# ---------------------------------------------------------------------------
# Role vocabulary derived from shipped artifacts (research R6) — never test
# literals. A renamed or added agent doc changes what this module checks.
# ---------------------------------------------------------------------------


def _derive_specialist_roles():
    known_non_specialists = {TRIAGE_DOC.name, DEEP_INVESTIGATOR_DOC.name}
    return sorted(
        "specialist:%s" % p.stem
        for p in AGENTS_DIR.glob("*.md")
        if p.name not in known_non_specialists
    )


def test_triage_and_deep_agent_docs_exist_and_justify_their_roles():
    assert TRIAGE_DOC.is_file(), (
        "%s must exist to justify the `triage` role" % TRIAGE_DOC
    )
    assert DEEP_INVESTIGATOR_DOC.is_file(), (
        "%s must exist to justify the `deep` role" % DEEP_INVESTIGATOR_DOC
    )


DERIVED_SPECIALIST_ROLES = _derive_specialist_roles()
DERIVED_ROLES = ["triage", "deep"] + DERIVED_SPECIALIST_ROLES


def test_derived_specialist_role_set_is_exactly_the_shipped_three():
    # Non-vanishing guard (pinned once, per research R6 / task instructions):
    # a renamed or added specialist doc must surface here consciously rather
    # than silently shrinking or growing what this module exercises.
    assert set(DERIVED_SPECIALIST_ROLES) == {
        "specialist:log-diver",
        "specialist:deploy-analyst",
        "specialist:dependency-checker",
    }, (
        "derived specialist role set drifted from the three shipped "
        "specialist docs: got %r" % (DERIVED_SPECIALIST_ROLES,)
    )


# ---------------------------------------------------------------------------
# Positive: every derived role conforms to the protocol's role grammar, and
# a registration write of it produces a shape-check-clean agents.json.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", DERIVED_ROLES, ids=DERIVED_ROLES)
def test_derived_role_conforms_to_the_protocol_grammar(role):
    assert ROLE_RE.match(role), (
        "derived role %r does not match the protocol's role grammar "
        "^(triage|deep|specialist:[a-z0-9-]+)$" % role
    )


@pytest.mark.parametrize("role", DERIVED_ROLES, ids=DERIVED_ROLES)
def test_registration_write_of_derived_role_is_shape_clean(tmp_path, role):
    doc = registration_write(tmp_path, "agent-under-test", role)
    violations = check_registration_shape(doc)
    assert violations == [], (
        "registration_write(%r) produced a non-conforming agents.json: %r"
        % (role, violations)
    )
    # Round-trips off disk too — the write actually landed, not just the
    # in-memory return value.
    on_disk = json.loads((tmp_path / "agents.json").read_text(encoding="utf-8"))
    assert check_registration_shape(on_disk) == []
    assert on_disk["roles"]["agent-under-test"] == role


# ---------------------------------------------------------------------------
# Merge behavior: sequential writes accumulate, never clobber prior entries.
# ---------------------------------------------------------------------------


def test_sequential_writes_merge_without_touching_prior_entries(tmp_path):
    first = registration_write(tmp_path, "agent-aaa1", "triage")
    assert first["roles"] == {"agent-aaa1": "triage"}

    second = registration_write(tmp_path, "agent-bbb2", "specialist:log-diver")
    assert second["roles"] == {
        "agent-aaa1": "triage",
        "agent-bbb2": "specialist:log-diver",
    }
    # The first entry is untouched, not just still-present coincidentally.
    assert second["roles"]["agent-aaa1"] == "triage"
    assert check_registration_shape(second) == []


def test_sequential_writes_never_rewrite_the_protocol_tag(tmp_path):
    registration_write(tmp_path, "agent-1", "deep")
    doc = registration_write(tmp_path, "agent-2", "triage")
    assert doc["protocol"] == "bb.local.v1"


# ---------------------------------------------------------------------------
# Negative: seeded non-conforming role values are rejected (SC-003).
# ---------------------------------------------------------------------------


BAD_ROLES = ["admin", "specialist:", "specialist:Bad_Name", "", "TRIAGE", "deep "]
BAD_ROLE_IDS = [repr(r) for r in BAD_ROLES]


@pytest.mark.parametrize("bad_role", BAD_ROLES, ids=BAD_ROLE_IDS)
def test_seeded_non_conforming_role_is_rejected(bad_role):
    doc = {"protocol": "bb.local.v1", "roles": {"agent-x": bad_role}}
    violations = check_registration_shape(doc)
    assert violations, (
        "check_registration_shape did not reject non-conforming role %r"
        % bad_role
    )
    assert any(v.startswith("roles.value.invalid:") for v in violations)


def test_seeded_bad_protocol_tag_is_rejected():
    doc = {"protocol": "bb.local.v0", "roles": {"agent-x": "triage"}}
    violations = check_registration_shape(doc)
    assert any(v.startswith("protocol.mismatch:") for v in violations)


def test_seeded_non_dict_roles_is_rejected():
    doc = {"protocol": "bb.local.v1", "roles": ["triage"]}
    violations = check_registration_shape(doc)
    assert any(v.startswith("roles.not_object:") for v in violations)


def test_seeded_empty_actor_key_is_rejected():
    doc = {"protocol": "bb.local.v1", "roles": {"": "triage"}}
    violations = check_registration_shape(doc)
    assert any(v.startswith("roles.key.not_nonempty_string:") for v in violations)


def test_seeded_non_string_actor_key_is_rejected():
    # JSON object keys are always strings once round-tripped through the
    # file, but the shape check must still reject a non-string key handed
    # in-memory (e.g. a caller that built the dict programmatically) — this
    # exercises the isinstance half of the check, the empty-key test above
    # the non-empty half (converge round-1 finding).
    doc = {"protocol": "bb.local.v1", "roles": {123: "triage"}}
    violations = check_registration_shape(doc)
    assert any(v.startswith("roles.key.not_nonempty_string:") for v in violations)
