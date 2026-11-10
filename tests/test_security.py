import time

import pytest

from app.github_auth import AccessError, GitHubAppAuth
from app.redaction import protect, sensitive_path
from app.repository_reader import validate_path, validate_ref


@pytest.mark.parametrize("path", [
    "../other", "docs/../secret", "/absolute", r"C:\source\file",
    "docs//file", "./README.md", "README%2emd", r"docs\evil",
])
def test_path_traversal_and_other_scope_rejected(path):
    with pytest.raises(ValueError):
        validate_path(path)


def test_commit_sha_validation():
    with pytest.raises(ValueError):
        validate_ref("main")
    assert validate_ref("a" * 40) == "a" * 40


def test_sensitive_paths_and_redaction():
    assert sensitive_path("credentials/secret.pem")
    assert sensitive_path(".env")
    result = protect({"content": "sk-" + "A" * 24, "complete": True, "limitations": []})
    assert result["content"] == "[REDACTED CREDENTIAL]"
    assert not result["complete"]


def test_installation_permission_discrepancy_stops():
    auth = GitHubAppAuth()
    auth._app_get = lambda path, token: (
        {"id": 5692993, "slug": "aps-tis-readonly"} if path == "/app" else {
            "app_id": 5692993, "account": {"login": "APS-TIS"},
            "target_type": "Organization", "repository_selection": "selected",
            "permissions": {"contents": "write", "issues": "read", "metadata": "read"},
            "id": 123,
        }
    )
    with pytest.raises(AccessError, match="permissions"):
        auth._discover("dummy")


def test_cached_token_refreshes_before_expiration():
    auth = GitHubAppAuth()
    auth._token = "old"
    auth._expires_at = time.time() + 100
    auth._jwt = lambda: "dummy"
    auth._discover = lambda token: None
    auth._mint_token = lambda token: ("new", time.time() + 3600)
    auth._verify_token_repository = lambda token: None
    assert auth.get_token() == "new"
    assert auth.get_token() == "new"

def test_other_repository_api_path_rejected():
    from app.github_client import GitHubClient
    with pytest.raises(AccessError, match="outside fixed repository"):
        GitHubClient()._get("/repos/OTHER/OTHER")
    with pytest.raises(AccessError, match="traversal"):
        GitHubClient()._get("/repos/APS-TIS/APS-TIS/../OTHER")
