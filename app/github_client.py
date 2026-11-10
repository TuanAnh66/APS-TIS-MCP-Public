"""Fixed-repository GitHub GET client. No caller-selectable API URL or method."""
import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode
from urllib.request import HTTPSHandler, HTTPRedirectHandler, Request, build_opener

from .config import API_BASE, API_VERSION, FULL_REPO, MAX_RESPONSE_BYTES, ORG, REPO
from .github_auth import AccessError, GitHubAppAuth


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = build_opener(HTTPSHandler(), _NoRedirect())
_ROOT = "/repos/" + ORG + "/" + REPO


def encode_path(path):
    return "/".join(quote(segment, safe="") for segment in path.split("/"))


class GitHubClient:
    def __init__(self, auth=None):
        self.auth = auth or GitHubAppAuth()

    def _get(self, path, params=None, retry=True):
        decoded = unquote(path)
        if any(segment in (".", "..") for segment in decoded.split("/")) or "\\" in decoded or ":" in decoded:
            raise AccessError("GitHub API path traversal rejected")
        if path != _ROOT and not path.startswith(_ROOT + "/"):
            raise AccessError("GitHub API path outside fixed repository")
        query = "?" + urlencode(params) if params else ""
        token = self.auth.get_token()
        request = Request(
            API_BASE + path + query,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer " + token,
                "X-GitHub-Api-Version": API_VERSION,
                "User-Agent": "APS-TIS-ReadOnly-MCP",
            },
            method="GET",
        )
        try:
            with _OPENER.open(request, timeout=20) as response:
                data = response.read(MAX_RESPONSE_BYTES + 1)
                if len(data) > MAX_RESPONSE_BYTES:
                    raise AccessError("GitHub response exceeds configured size limit")
                return json.loads(data)
        except HTTPError as exc:
            if exc.code == 401 and retry:
                self.auth.invalidate()
                return self._get(path, params, retry=False)
            reset = exc.headers.get("X-RateLimit-Reset")
            suffix = " (rate limit reset: " + reset + ")" if exc.code in (403, 429) and reset and reset.isdigit() else ""
            raise AccessError("GitHub API HTTP " + str(exc.code) + suffix) from None
        except (URLError, TimeoutError, OSError) as exc:
            raise AccessError("GitHub API network error: " + type(exc).__name__) from None
        except (ValueError, UnicodeError):
            raise AccessError("GitHub returned invalid JSON") from None

    def repository(self):
        return self._get(_ROOT)

    def commit(self, ref):
        return self._get(_ROOT + "/commits/" + quote(ref, safe=""))

    def contents(self, path, sha):
        suffix = "/contents" + ("/" + encode_path(path) if path else "")
        return self._get(_ROOT + suffix, {"ref": sha})

    def tree(self, sha, recursive=False):
        return self._get(_ROOT + "/git/trees/" + quote(sha, safe=""), {"recursive": "1"} if recursive else None)

    def issues(self, state, page, per_page):
        return self._get(_ROOT + "/issues", {"state": state, "page": page, "per_page": per_page, "sort": "updated", "direction": "desc"})

    def issue(self, number):
        return self._get(_ROOT + "/issues/" + str(number))

    def issue_comments(self, number, page, per_page):
        return self._get(_ROOT + "/issues/" + str(number) + "/comments", {"page": page, "per_page": per_page})
