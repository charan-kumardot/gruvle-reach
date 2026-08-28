"""
GitProvider abstraction (§30, §3-4 of the visibility spec). This interface
is deliberately narrow: read a repo, read a file, create a branch, commit a
file change, open a pull request, read PR/check status. There is no
merge(), no delete(), no force_push() method — those actions are simply
not representable through this interface, which is the structural
enforcement of §27 (git safety) and §33 (agent cannot merge or deploy).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RepoInfo:
    owner: str
    name: str
    default_branch: str
    private: bool
    html_url: str


@dataclass
class FileContent:
    path: str
    content: str
    sha: str  # required by GitHub's Contents API to update this file safely


@dataclass
class PullRequestInfo:
    number: int
    url: str
    state: str  # open, closed, merged
    head_branch: str
    base_branch: str


@dataclass
class CheckRunSummary:
    name: str
    status: str  # queued, in_progress, completed
    conclusion: str  # success, failure, neutral, cancelled, timed_out, ... or "" if not completed


class GitProviderError(RuntimeError):
    pass


class GitProvider(ABC):
    name: str = "base"

    @abstractmethod
    def configured(self) -> bool:
        ...

    @abstractmethod
    def list_repositories(self) -> list[RepoInfo]:
        ...

    @abstractmethod
    def get_repo_info(self, *, owner: str, repo: str) -> RepoInfo:
        ...

    @abstractmethod
    def get_file_content(self, *, owner: str, repo: str, path: str, ref: str) -> FileContent | None:
        """Returns None if the file doesn't exist at that ref."""

    @abstractmethod
    def create_branch(self, *, owner: str, repo: str, base_branch: str, new_branch: str) -> str:
        """Returns the new branch's HEAD commit SHA."""

    @abstractmethod
    def commit_file_change(
        self, *, owner: str, repo: str, branch: str, path: str, new_content: str, message: str, previous_sha: str
    ) -> str:
        """Returns the new commit SHA."""

    @abstractmethod
    def create_pull_request(
        self, *, owner: str, repo: str, head_branch: str, base_branch: str, title: str, body: str
    ) -> PullRequestInfo:
        ...

    @abstractmethod
    def get_pull_request(self, *, owner: str, repo: str, number: int) -> PullRequestInfo:
        ...

    @abstractmethod
    def get_check_runs(self, *, owner: str, repo: str, ref: str) -> list[CheckRunSummary]:
        """Reads the repo's own CI results for a ref — Reach never runs
        builds/tests itself (see docs/EXTENDING.md)."""
