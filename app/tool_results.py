"""Explicit MCP output schemas for ChatGPT's structured tool results."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolOutput(BaseModel):
    model_config = ConfigDict(extra="allow")
    limitations: list[str] = Field(default_factory=list)


class RepositoryInfoOutput(ToolOutput):
    repository: str
    visibility: str | None = None
    private: bool | None = None
    default_branch: str
    description: str | None = None
    archived: bool | None = None
    updated_at: str | None = None
    html_url: str | None = None
    source_sha: str


class LatestCommitOutput(ToolOutput):
    repository: str
    default_branch: str
    sha: str
    message: str | None = None
    author: str | None = None
    author_login: str | None = None
    timestamp: str | None = None
    html_url: str | None = None


class RepositoryFilesOutput(ToolOutput):
    repository: str
    source_sha: str
    default_branch: str
    directory: str
    recursive: bool
    page: int
    per_page: int
    total_entries: int
    entries: list[dict[str, Any]]
    next_page: int | None = None


class ReadFileOutput(ToolOutput):
    repository: str
    path: str
    source_sha: str
    git_blob_sha: str | None = None
    size: int | None = None
    encoding: str | None = None
    content: str | None = None
    complete: bool
    default_branch: str


class SearchRepositoryOutput(ToolOutput):
    repository: str
    source_sha: str
    default_branch: str
    query: str
    directory_prefix: str
    file_extension: str | None = None
    page: int
    candidate_files: int
    selected_files: int
    scanned_files: int
    matches: list[dict[str, Any]]
    next_page: int | None = None


class ListIssuesOutput(ToolOutput):
    repository: str
    state: str
    page: int
    per_page: int
    issues: list[dict[str, Any]]
    next_page: int | None = None


class IssueOutput(ToolOutput):
    repository: str
    number: int
    title: str | None = None
    description: str
    state: str | None = None
    author: str | None = None
    labels: list[str | None]
    assignees: list[str | None]
    created_at: str | None = None
    updated_at: str | None = None
    closed_at: str | None = None
    html_url: str | None = None


class IssueCommentsOutput(ToolOutput):
    repository: str
    issue_number: int
    page: int
    per_page: int
    comments: list[dict[str, Any]]
    next_page: int | None = None
