import asyncio
from pathlib import Path

from app.server import mcp

EXPECTED = {
    "get_repository_info", "get_latest_commit", "list_repository_files",
    "read_file", "search_repository", "list_issues", "get_issue",
    "list_issue_comments",
}


def test_inventory_is_exact_and_read_only():
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == EXPECTED
    assert all(tool.annotations.read_only_hint is True for tool in tools)
    assert all(tool.annotations.open_world_hint is False for tool in tools)


def test_repo_client_has_no_write_method():
    root = Path(__file__).resolve().parents[1] / "app"
    client = (root / "github_client.py").read_text(encoding="utf-8")
    assert 'method="GET"' in client
    assert 'method="POST"' not in client
    for method in ("PATCH", "PUT", "DELETE"):
        assert 'method="' + method + '"' not in client
    auth = (root / "github_auth.py").read_text(encoding="utf-8")
    assert auth.count('method="POST"') == 1
    assert '/access_tokens' in auth
    assert '"repositories": [REPO]' in auth
