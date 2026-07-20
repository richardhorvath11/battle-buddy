"""Artifact-assertion entry point (spec Story 3, FR-008).

Structural checks over mock state — never prose (Constitution VIII: assert on
artifacts). Later slices grow scenario-level checks here; slice 1 ships the
skeleton with the two foundational ones.
"""


def assert_seeded_state(mock, seed):
    """The mock contains exactly the state a seed fixture describes."""
    assert mock.records.records == [dict(r) for r in seed.get("records", [])]
    assert list(mock.artifacts.files.values()) == [
        {"name": a["name"], "content": a["content"]}
        for a in seed.get("artifacts", [])
    ]
    assert [e["content"] for e in mock.diary.entries] == list(seed.get("diary", []))
    alerts = seed.get("alerts", {})
    assert mock.alerting.alerts == {
        a["alert_id"]: dict(a) for a in alerts.get("alerts", [])
    }
    assert mock.alerting.history == [dict(h) for h in alerts.get("history", [])]


def assert_write_sequence(mock, expected):
    """The write log reproduces exactly the (capability, op) sequence given."""
    actual = [(e["capability"], e["op"]) for e in mock.write_log.entries]
    assert actual == list(expected)
    assert [e["seq"] for e in mock.write_log.entries] == list(
        range(1, len(actual) + 1)
    )
