"""GitHub App authentication. Only the fixed token endpoint uses POST."""
import json
import threading
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, HTTPRedirectHandler, Request, build_opener

import jwt

from .config import (
    API_BASE, API_VERSION, APP_ID, APP_SLUG, EXPECTED_PERMISSIONS,
    FULL_REPO, KEY_PATH, MAX_RESPONSE_BYTES, ORG, REPO,
)


class AccessError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = build_opener(HTTPSHandler(), _NoRedirect())


def _headers(token):
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token,
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "APS-TIS-ReadOnly-MCP",
    }


def _receive(request):
    try:
        with _OPENER.open(request, timeout=20) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
            if len(data) > MAX_RESPONSE_BYTES:
                raise AccessError("GitHub response exceeds configured size limit")
            return json.loads(data)
    except HTTPError as exc:
        reset = exc.headers.get("X-RateLimit-Reset")
        suffix = " (rate limit reset: " + reset + ")" if exc.code in (403, 429) and reset and reset.isdigit() else ""
        raise AccessError("GitHub API HTTP " + str(exc.code) + suffix) from None
    except (URLError, TimeoutError, OSError) as exc:
        raise AccessError("GitHub API network error: " + type(exc).__name__) from None
    except (ValueError, UnicodeError):
        raise AccessError("GitHub returned invalid JSON") from None


class GitHubAppAuth:
    def __init__(self):
        self._lock = threading.RLock()
        self._token = None
        self._expires_at = 0
        self.installation_id = None
        self.verified_permissions = None

    def _jwt(self):
        if not KEY_PATH.is_file():
            raise AccessError("GitHub App private key is missing from the credentials directory")
        # The PEM and signed JWT never enter logs or MCP results.
        key = KEY_PATH.read_bytes()
        now = int(time.time())
        return jwt.encode(
            {"iat": now - 60, "exp": now + 540, "iss": str(APP_ID)},
            key,
            algorithm="RS256",
        )

    def _app_get(self, path, app_jwt):
        if path not in ("/app", "/orgs/" + ORG + "/installation"):
            raise AccessError("App API path rejected")
        return _receive(Request(API_BASE + path, headers=_headers(app_jwt), method="GET"))

    def _discover(self, app_jwt):
        app = self._app_get("/app", app_jwt)
        if app.get("id") != APP_ID or app.get("slug", "").lower() != APP_SLUG:
            raise AccessError("GitHub App identity does not match configured App ID and slug")
        installation = self._app_get("/orgs/" + ORG + "/installation", app_jwt)
        if installation.get("app_id") != APP_ID:
            raise AccessError("Installation App ID mismatch")
        if installation.get("account", {}).get("login", "").lower() != ORG.lower():
            raise AccessError("Installation organization mismatch")
        if installation.get("target_type") != "Organization":
            raise AccessError("Installation target type mismatch")
        if installation.get("repository_selection") != "selected":
            raise AccessError("Installation is not restricted to selected repositories")
        if installation.get("suspended_at"):
            raise AccessError("GitHub App installation is suspended")
        permissions = installation.get("permissions") or {}
        if permissions != EXPECTED_PERMISSIONS:
            raise AccessError("Installation permissions differ from contents/read, issues/read, metadata/read")
        self.installation_id = installation.get("id")
        self.verified_permissions = permissions
        if not isinstance(self.installation_id, int) or self.installation_id <= 0:
            raise AccessError("Installation ID is invalid")

    def _mint_token(self, app_jwt):
        if self.installation_id is None:
            raise AccessError("Installation has not been verified")
        # GitHub requires POST only to mint an installation token. The body narrows
        # it to one repository and the three read permissions; it cannot write.
        path = "/app/installations/" + str(self.installation_id) + "/access_tokens"
        body = json.dumps({
            "repositories": [REPO],
            "permissions": EXPECTED_PERMISSIONS,
        }).encode("utf-8")
        headers = _headers(app_jwt)
        headers["Content-Type"] = "application/json"
        result = _receive(Request(API_BASE + path, data=body, headers=headers, method="POST"))
        token = result.get("token")
        if not isinstance(token, str) or not token:
            raise AccessError("GitHub did not return an installation token")
        if result.get("permissions") != EXPECTED_PERMISSIONS:
            raise AccessError("Installation token permissions differ from expected read permissions")
        repositories = result.get("repositories")
        if repositories is not None and (
            not isinstance(repositories, list)
            or len(repositories) != 1
            or repositories[0].get("full_name", "").lower() != FULL_REPO.lower()
        ):
            raise AccessError("Installation token repository scope mismatch")
        try:
            expiry = datetime.fromisoformat(result["expires_at"].replace("Z", "+00:00")).timestamp()
        except (KeyError, TypeError, ValueError):
            raise AccessError("Installation token expiration is missing or invalid") from None
        if expiry - time.time() < 300:
            raise AccessError("Installation token expires too soon")
        return token, expiry

    def _verify_token_repository(self, token):
        path = "/installation/repositories?per_page=2"
        result = _receive(Request(API_BASE + path, headers=_headers(token), method="GET"))
        repos = result.get("repositories")
        if result.get("total_count") != 1 or not isinstance(repos, list) or len(repos) != 1:
            raise AccessError("Installation token can access an unexpected number of repositories")
        if repos[0].get("full_name", "").lower() != FULL_REPO.lower():
            raise AccessError("Installation token repository is not APS-TIS/APS-TIS")

    def get_token(self):
        with self._lock:
            if self._token and time.time() < self._expires_at - 300:
                return self._token
            app_jwt = self._jwt()
            self._discover(app_jwt)
            token, expiry = self._mint_token(app_jwt)
            self._verify_token_repository(token)
            self._token, self._expires_at = token, expiry
            return token

    def invalidate(self):
        with self._lock:
            self._token, self._expires_at = None, 0

    def status(self):
        self.get_token()
        return {
            "app_id": APP_ID,
            "app_slug": APP_SLUG,
            "organization": ORG,
            "installation_id": self.installation_id,
            "repository": FULL_REPO,
            "permissions": self.verified_permissions,
            "repository_selection": "selected",
            "token_scope_verified": True,
            "token_expiration_utc": datetime.fromtimestamp(self._expires_at, timezone.utc).isoformat(),
        }
