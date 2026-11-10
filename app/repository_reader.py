"""Repository reads pinned to the current default-branch commit."""
import base64
import re
import time
from pathlib import PurePosixPath

from .config import (
    FULL_REPO, MAX_FILE_BYTES, MAX_LIST_ITEMS, MAX_SEARCH_FILES,
    MAX_SEARCH_RESULTS,
)
from .github_auth import AccessError
from .github_client import GitHubClient
from .redaction import sensitive_path

_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
_EXTENSION = re.compile(r"^\.[A-Za-z0-9]{1,16}$")


def validate_path(path, allow_empty=False):
    if not isinstance(path, str) or len(path) > 400:
        raise ValueError("Path must be a repository-relative string of at most 400 characters")
    if not path and allow_empty:
        return ""
    if not path or path.startswith("/") or "\\" in path or ":" in path or "%" in path:
        raise ValueError("Path must be repository-relative and use forward slashes")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in path):
        raise ValueError("Path contains control characters")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("Path contains an empty or traversal segment")
    return str(PurePosixPath(path))


def validate_ref(ref):
    if ref is not None and (not isinstance(ref, str) or not _SHA.fullmatch(ref)):
        raise ValueError("Reference must be a complete 40-character commit SHA")
    return ref


def validate_page(page, per_page, max_per_page=100):
    if type(page) is not int or page < 1 or page > 10000:
        raise ValueError("Page must be an integer from 1 to 10000")
    if type(per_page) is not int or per_page < 1 or per_page > max_per_page:
        raise ValueError("per_page is outside the allowed range")


class RepositoryReader:
    def __init__(self, client=None):
        self.client = client or GitHubClient()

    def _resolve(self, ref=None):
        validate_ref(ref)
        info = self.client.repository()
        if info.get("full_name", "").lower() != FULL_REPO.lower():
            raise AccessError("GitHub returned a different repository")
        branch = info.get("default_branch")
        if not isinstance(branch, str) or not branch:
            raise AccessError("Repository default branch is missing")
        commit = self.client.commit(ref or branch)
        sha = commit.get("sha")
        if not isinstance(sha, str) or not _SHA.fullmatch(sha):
            raise AccessError("GitHub returned an invalid commit SHA")
        return info, branch, commit

    def get_repository_info(self):
        info, branch, commit = self._resolve()
        return {
            "repository": FULL_REPO,
            "visibility": info.get("visibility"),
            "private": info.get("private"),
            "default_branch": branch,
            "description": info.get("description"),
            "archived": info.get("archived"),
            "updated_at": info.get("updated_at"),
            "html_url": info.get("html_url"),
            "source_sha": commit["sha"],
        }

    def get_latest_commit(self):
        _, branch, commit = self._resolve()
        details = commit.get("commit") or {}
        author = details.get("author") or {}
        return {
            "repository": FULL_REPO,
            "default_branch": branch,
            "sha": commit["sha"],
            "message": details.get("message"),
            "author": author.get("name"),
            "author_login": (commit.get("author") or {}).get("login"),
            "timestamp": author.get("date"),
            "html_url": commit.get("html_url"),
        }

    def _tree(self, commit):
        tree_sha = ((commit.get("commit") or {}).get("tree") or {}).get("sha")
        if not isinstance(tree_sha, str) or not _SHA.fullmatch(tree_sha):
            raise AccessError("Commit tree SHA is missing")
        result = self.client.tree(tree_sha, recursive=True)
        return result

    def list_repository_files(self, directory="", recursive=False, page=1, per_page=100):
        directory = validate_path(directory, allow_empty=True)
        validate_page(page, per_page)
        if type(recursive) is not bool:
            raise ValueError("recursive must be a boolean")
        _, branch, commit = self._resolve()
        sha = commit["sha"]
        if recursive:
            tree = self._tree(commit)
            prefix = directory + "/" if directory else ""
            entries = [
                {"path": item["path"], "type": "directory" if item["type"] == "tree" else "file",
                 "sha": item.get("sha"), "size": item.get("size")}
                for item in tree.get("tree", [])
                if item.get("type") in ("tree", "blob")
                and (not directory or item.get("path", "").startswith(prefix))
            ]
            github_truncated = bool(tree.get("truncated"))
        else:
            listing = self.client.contents(directory, sha)
            if not isinstance(listing, list):
                raise ValueError("The requested path is not a directory")
            entries = [
                {"path": item.get("path"), "type": "directory" if item.get("type") == "dir" else "file",
                 "sha": item.get("sha"), "size": item.get("size")}
                for item in listing if item.get("type") in ("dir", "file")
            ]
            github_truncated = False
        start = (page - 1) * per_page
        result = entries[start:start + per_page]
        return {
            "repository": FULL_REPO, "source_sha": sha, "default_branch": branch,
            "directory": directory, "recursive": recursive, "page": page,
            "per_page": per_page, "total_entries": len(entries), "entries": result,
            "next_page": page + 1 if start + per_page < len(entries) else None,
            "limitations": ["GitHub tree response was truncated; some paths may be absent"] if github_truncated else [],
        }

    def _read_at_sha(self, path, sha):
        if sensitive_path(path):
            return {"repository": FULL_REPO, "path": path, "source_sha": sha, "size": None, "encoding": None, "content": None, "complete": False, "limitations": ["Sensitive credential path is blocked"]}
        item = self.client.contents(path, sha)
        if not isinstance(item, dict) or item.get("type") != "file":
            raise ValueError("Requested path is not a regular file")
        size = item.get("size")
        result = {
            "repository": FULL_REPO, "path": path, "source_sha": sha,
            "git_blob_sha": item.get("sha"), "size": size,
            "encoding": None, "content": None, "complete": False, "limitations": [],
        }
        if not isinstance(size, int) or size < 0:
            result["limitations"].append("GitHub did not provide a valid file size")
            return result
        if size > MAX_FILE_BYTES:
            result["limitations"].append("File exceeds the 512 KiB MCP read limit")
            return result
        if item.get("encoding") != "base64" or not isinstance(item.get("content"), str):
            result["limitations"].append("GitHub did not return inline base64 file content")
            return result
        try:
            raw = base64.b64decode(item["content"], validate=False)
        except (ValueError, base64.binascii.Error):
            result["limitations"].append("GitHub returned invalid base64 content")
            return result
        if len(raw) != size:
            result["limitations"].append("Returned byte count does not match GitHub file size")
            return result
        if b"\x00" in raw:
            result["limitations"].append("Binary file content is not returned")
            return result
        try:
            text = raw.decode("utf-8-sig")
            result["encoding"] = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
        except UnicodeDecodeError:
            result["limitations"].append("File is not valid UTF-8 text")
            return result
        result["content"] = text
        result["complete"] = True
        if text.startswith("version https://git-lfs.github.com/spec/v1\n"):
            result["limitations"].append("Git LFS pointer only; native LFS object was not retrieved")
        return result

    def read_file(self, path, ref=None):
        path = validate_path(path)
        _, branch, commit = self._resolve(ref)
        result = self._read_at_sha(path, commit["sha"])
        result["default_branch"] = branch
        return result

    def search_repository(self, text, directory_prefix="", file_extension=None, page=1):
        if not isinstance(text, str) or not text.strip() or len(text) > 120:
            raise ValueError("Search text must be 1 to 120 characters")
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
            raise ValueError("Search text contains control characters")
        directory_prefix = validate_path(directory_prefix, allow_empty=True)
        if file_extension is not None and not _EXTENSION.fullmatch(file_extension):
            raise ValueError("File extension must look like .md or .py")
        validate_page(page, MAX_SEARCH_FILES)
        _, branch, commit = self._resolve()
        tree = self._tree(commit)
        prefix = directory_prefix + "/" if directory_prefix else ""
        candidates = [
            item["path"] for item in tree.get("tree", [])
            if item.get("type") == "blob"
            and (not directory_prefix or item.get("path", "").startswith(prefix))
            and (file_extension is None or item.get("path", "").lower().endswith(file_extension.lower()))
        ]
        start = (page - 1) * MAX_SEARCH_FILES
        selected = candidates[start:start + MAX_SEARCH_FILES]
        matches = []
        skipped = 0
        scanned = 0
        timed_out = False
        deadline = time.monotonic() + 70
        result_limit_hit = False
        for path in selected:
            if time.monotonic() >= deadline:
                timed_out = True
                break
            scanned += 1
            file = self._read_at_sha(path, commit["sha"])
            if not file["complete"]:
                skipped += 1
                continue
            for line_no, line in enumerate(file["content"].splitlines(), 1):
                if text.casefold() in line.casefold():
                    if len(matches) >= MAX_SEARCH_RESULTS:
                        result_limit_hit = True
                        continue
                    snippet = line.strip()
                    if len(snippet) > 240:
                        snippet = snippet[:240] + "…"
                    matches.append({"path": path, "line": line_no, "snippet": snippet})
        limitations = []
        if tree.get("truncated"):
            limitations.append("GitHub tree response was truncated")
        if skipped:
            limitations.append(str(skipped) + " selected files were too large, binary, or unavailable as inline text")
        if result_limit_hit:
            limitations.append("Only the first 20 matches on this page are returned")
        if timed_out:
            limitations.append("70-second search budget reached; remaining files on this page were not searched")
        if start + MAX_SEARCH_FILES < len(candidates):
            limitations.append("More candidate files remain; request next_page to continue")
        return {
            "repository": FULL_REPO, "source_sha": commit["sha"], "default_branch": branch,
            "query": text, "directory_prefix": directory_prefix,
            "file_extension": file_extension, "page": page,
            "candidate_files": len(candidates), "selected_files": len(selected), "scanned_files": scanned,
            "matches": matches,
            "next_page": page + 1 if start + MAX_SEARCH_FILES < len(candidates) else None,
            "limitations": limitations,
        }
