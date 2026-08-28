from app.providers.git.base import CheckRunSummary, FileContent, GitProvider, PullRequestInfo, RepoInfo


class MockGitProvider(GitProvider):
    """DEMO-only provider for exercising the optimization-agent flow without
    a real GitHub token. Every value is clearly marked DEMO — never mistaken
    for a real repository, branch, or PR."""

    name = "mock"

    def configured(self) -> bool:
        return True

    def list_repositories(self) -> list[RepoInfo]:
        return [
            RepoInfo(owner="demo-org", name="demo-website [DEMO]", default_branch="main", private=False, html_url="https://example.com/demo-org/demo-website")
        ]

    def get_repo_info(self, *, owner: str, repo: str) -> RepoInfo:
        return RepoInfo(owner=owner, name=f"{repo} [DEMO]", default_branch="main", private=False, html_url=f"https://example.com/{owner}/{repo}")

    def get_file_content(self, *, owner: str, repo: str, path: str, ref: str) -> FileContent | None:
        return FileContent(path=path, content="[DEMO] placeholder file content", sha="demo-sha-0000")

    def create_branch(self, *, owner: str, repo: str, base_branch: str, new_branch: str) -> str:
        return "demo-sha-0000"

    def commit_file_change(
        self, *, owner: str, repo: str, branch: str, path: str, new_content: str, message: str, previous_sha: str
    ) -> str:
        return "demo-sha-0001"

    def create_pull_request(
        self, *, owner: str, repo: str, head_branch: str, base_branch: str, title: str, body: str
    ) -> PullRequestInfo:
        return PullRequestInfo(number=0, url="https://example.com/demo-pr [DEMO]", state="open", head_branch=head_branch, base_branch=base_branch)

    def get_pull_request(self, *, owner: str, repo: str, number: int) -> PullRequestInfo:
        return PullRequestInfo(number=number, url="https://example.com/demo-pr [DEMO]", state="open", head_branch="demo", base_branch="main")

    def get_check_runs(self, *, owner: str, repo: str, ref: str) -> list[CheckRunSummary]:
        return [CheckRunSummary(name="demo-build [DEMO]", status="completed", conclusion="success")]
