"""Conformance: artifacts ops — put/get roundtrip, stable deterministic links,
not_found (contracts/operations.md; SC-003)."""


def test_put_get_roundtrip(mock_mcp):
    out = mock_mcp.invoke("artifacts", "put_file", {"name": "report.md", "content": "# findings"})
    link = out["link"]
    assert link.startswith("art://")
    assert mock_mcp.invoke("artifacts", "get_file", {"link": link}) == {
        "name": "report.md",
        "content": "# findings",
    }


def test_links_are_unique_per_stored_object(mock_mcp):
    links = [
        mock_mcp.invoke("artifacts", "put_file", {"name": "f{}".format(i), "content": "c"})["link"]
        for i in range(3)
    ]
    assert len(set(links)) == 3


def test_links_deterministic_across_identical_runs(mock_mcp_factory):
    def run(mock):
        return [
            mock.invoke("artifacts", "put_file", {"name": n, "content": "c"})["link"]
            for n in ("a", "b", "c")
        ]

    assert run(mock_mcp_factory()) == run(mock_mcp_factory())


def test_get_file_unknown_link_is_not_found(mock_mcp):
    result = mock_mcp.invoke("artifacts", "get_file", {"link": "art://999"})
    assert result["error"]["op"] == "artifacts.get_file"
    assert result["error"]["code"] == "not_found"
    assert "art://999" in result["error"]["message"]


def test_put_file_empty_name_rejected(mock_mcp):
    result = mock_mcp.invoke("artifacts", "put_file", {"name": "", "content": "c"})
    assert result["error"]["code"] == "invalid_input"
    assert "name" in result["error"]["message"]
