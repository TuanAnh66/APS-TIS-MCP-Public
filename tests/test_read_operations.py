import base64

from app.config import FULL_REPO
from app.issue_reader import IssueReader
from app.repository_reader import RepositoryReader


SHA = "a" * 40
TREE_SHA = "b" * 40


class FakeClient:
    def repository(self):
        return {"full_name": FULL_REPO, "default_branch": "main", "visibility": "private"}

    def commit(self, ref):
        return {"sha": SHA, "commit": {"tree": {"sha": TREE_SHA}, "author": {"name": "A", "date": "2026-11-10T00:00:00Z"}, "message": "Read"}, "html_url": "https://github.com/APS-TIS/APS-TIS/commit/" + SHA}

    def contents(self, path, sha):
        assert sha == SHA
        if path == "":
            return [{"path": "README.md", "type": "file", "sha": "c" * 40, "size": 4}]
        body = {
            "README.md": b"hello\n",
            "pointer.txt": b"version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 123\n",
            "binary.dat": b"\x00\x01",
            "docs/example.md": b"line one\nmatching text\n",
        }[path]
        return {"path": path, "type": "file", "size": len(body), "encoding": "base64", "content": base64.b64encode(body).decode(), "sha": "c" * 40}

    def tree(self, sha, recursive=False):
        assert sha == TREE_SHA and recursive
        return {"truncated": False, "tree": [
            {"path": "README.md", "type": "blob", "sha": "c" * 40},
            {"path": "docs", "type": "tree", "sha": "d" * 40},
            {"path": "docs/example.md", "type": "blob", "sha": "e" * 40},
        ]}

    def issues(self, state, page, per_page):
        return [
            {"number": 1, "title": "Issue", "state": "open", "created_at": "t", "updated_at": "t", "html_url": "https://github.com/APS-TIS/APS-TIS/issues/1"},
            {"number": 2, "title": "PR", "state": "open", "pull_request": {}, "created_at": "t", "updated_at": "t"},
        ]

    def issue(self, number):
        return {"number": number, "title": "Issue", "body": "body", "state": "open", "user": {"login": "owner"}, "labels": [], "assignees": []}

    def issue_comments(self, number, page, per_page):
        return [{"body": "comment", "user": {"login": "owner"}, "created_at": "t", "html_url": "https://github.com/APS-TIS/APS-TIS/issues/1#issuecomment-1"}]


def test_file_content_and_sha():
    reader = RepositoryReader(FakeClient())
    result = reader.read_file("README.md")
    assert result["content"] == "hello\n"
    assert result["source_sha"] == SHA and result["complete"]
    assert result["size"] == 6
    assert reader.read_file("pointer.txt")["limitations"] == ["Git LFS pointer only; native LFS object was not retrieved"]
    assert not reader.read_file("binary.dat")["complete"]


def test_list_and_bounded_search():
    reader = RepositoryReader(FakeClient())
    listing = reader.list_repository_files("docs", recursive=True)
    assert listing["entries"][0]["path"] == "docs/example.md"
    found = reader.search_repository("matching", directory_prefix="docs", file_extension=".md")
    assert found["source_sha"] == SHA
    assert found["matches"] == [{"path": "docs/example.md", "line": 2, "snippet": "matching text"}]


def test_issue_reads_exclude_pull_requests():
    reader = IssueReader(FakeClient())
    assert [item["number"] for item in reader.list_issues()["issues"]] == [1]
    assert reader.get_issue(1)["author"] == "owner"
    assert reader.list_issue_comments(1)["comments"][0]["body"] == "comment"
