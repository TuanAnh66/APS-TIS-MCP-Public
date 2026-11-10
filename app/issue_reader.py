"""Bounded, fixed-repository issue reads."""
from .config import FULL_REPO
from .github_client import GitHubClient
from .repository_reader import validate_page


def validate_issue_number(number):
    if type(number) is not int or number < 1 or number > 2_147_483_647:
        raise ValueError("Issue number must be a positive integer")
    return number


class IssueReader:
    def __init__(self, client=None):
        self.client = client or GitHubClient()

    def list_issues(self, state="open", page=1, per_page=50):
        if state not in ("open", "closed", "all"):
            raise ValueError("State must be open, closed, or all")
        validate_page(page, per_page)
        raw = self.client.issues(state, page, per_page)
        issues = [
            {
                "number": item.get("number"), "title": item.get("title"),
                "state": item.get("state"), "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"), "html_url": item.get("html_url"),
            }
            for item in raw if "pull_request" not in item
        ]
        return {
            "repository": FULL_REPO, "state": state, "page": page,
            "per_page": per_page, "issues": issues,
            "next_page": page + 1 if len(raw) == per_page else None,
            "limitations": ["GitHub Issues list includes pull requests in pagination; those entries were excluded"] if len(raw) != len(issues) else [],
        }

    def get_issue(self, number):
        number = validate_issue_number(number)
        item = self.client.issue(number)
        if "pull_request" in item:
            raise ValueError("Number identifies a pull request, not an issue")
        return {
            "repository": FULL_REPO, "number": number, "title": item.get("title"),
            "description": (item.get("body") or "")[:65536], "state": item.get("state"),
            "author": (item.get("user") or {}).get("login"),
            "labels": [x.get("name") for x in item.get("labels", [])],
            "assignees": [x.get("login") for x in item.get("assignees", [])],
            "created_at": item.get("created_at"), "updated_at": item.get("updated_at"),
            "closed_at": item.get("closed_at"), "html_url": item.get("html_url"),
            "limitations": ["Issue description is longer than 64 KiB; truncated"] if len(item.get("body") or "") > 65536 else [],
        }

    def list_issue_comments(self, number, page=1, per_page=50):
        number = validate_issue_number(number)
        validate_page(page, per_page)
        issue = self.client.issue(number)
        if "pull_request" in issue:
            raise ValueError("Number identifies a pull request, not an issue")
        raw = self.client.issue_comments(number, page, per_page)
        comments = []
        for item in raw:
            body = item.get("body") or ""
            comments.append({
                "author": (item.get("user") or {}).get("login"),
                "body": body[:16384], "created_at": item.get("created_at"),
                "html_url": item.get("html_url"),
                "truncated": len(body) > 16384,
            })
        return {
            "repository": FULL_REPO, "issue_number": number, "page": page,
            "per_page": per_page, "comments": comments,
            "next_page": page + 1 if len(raw) == per_page else None,
            "limitations": ["Some comment bodies exceeded 16 KiB"] if any(x["truncated"] for x in comments) else [],
        }
