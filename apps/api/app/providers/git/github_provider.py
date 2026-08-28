"""
Real GitHub integration via a founder-supplied fine-grained Personal Access
Token (§3-4: "appropriately scoped token as fallback"). Every request in
this file targets api.github.com only — the host is hardcoded, never taken
from user input, so this cannot be used as an SSRF vector regardless of
what owner/repo strings a caller passes in.
"""
import base64

import httpx

from app.providers.git.base import (
    CheckRunSummary,
    FileContent,
    GitProvider,
    GitProviderError,
    PullRequestInfo,
    RepoInfo,
)

_API_BASE = "https://api.github.com"


class GitHubProvider(GitProvider):
    name = "github"

    def __init__(self, token: str):
        self._token = token

    def configured(self) -> bool:
        return bool(self._token)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        if not self.configured():
            raise GitProviderError("GitHub is not connected for this workspace")
        try:
            resp = httpx.request(method, f"{_API_BASE}{path}", headers=self._headers(), timeout=20, **kwargs)
        except httpx.HTTPError as exc:
            raise GitProviderError(f"GitHub request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise GitProviderError(f"GitHub API error {resp.status_code} on {method} {path}: {resp.text[:300]}")
        return resp

    def list_repositories(self) -> list[RepoInfo]:
        if not self.configured():
            return []
        resp = self._request("GET", "/user/repos", params={"per_page": 100, "sort": "updated"})
        return [
            RepoInfo(
                owner=r["owner"]["login"],
                name=r["name"],
                default_branch=r["default_branch"],
                private=r["private"],
                html_url=r["html_url"],
            )
            for r in resp.json()
        ]

    def get_repo_info(self, *, owner: str, repo: str) -> RepoInfo:
        r = self._request("GET", f"/repos/{owner}/{repo}").json()
        return RepoInfo(
            owner=r["owner"]["login"], name=r["name"], default_branch=r["default_branch"],
            private=r["private"], html_url=r["html_url"],
        )

    def get_file_content(self, *, owner: str, repo: str, path: str, ref: str) -> FileContent | None:
        resp = httpx.get(
            f"{_API_BASE}/repos/{owner}/{repo}/contents/{path}",
            headers=self._headers(), params={"ref": ref}, timeout=20,
        )
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise GitProviderError(f"GitHub API error {resp.status_code} reading {path}: {resp.text[:300]}")
        data = resp.json()
        if data.get("encoding") != "base64":
            raise GitProviderError(f"Unexpected content encoding for {path}: {data.get('encoding')}")
        content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        return FileContent(path=path, content=content, sha=data["sha"])

    def create_branch(self, *, owner: str, repo: str, base_branch: str, new_branch: str) -> str:
        base_ref = self._request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{base_branch}").json()
        base_sha = base_ref["object"]["sha"]
        self._request(
            "POST", f"/repos/{owner}/{repo}/git/refs",
            json={"ref": f"refs/heads/{new_branch}", "sha": base_sha},
        )
        return base_sha

    def commit_file_change(
        self, *, owner: str, repo: str, branch: str, path: str, new_content: str, message: str, previous_sha: str
    ) -> str:
        # GitHub's Contents API creates a new file when `sha` is omitted, and
        # updates an existing one when it's provided — so an empty
        # previous_sha (a file that didn't exist yet) is a legitimate,
        # supported "create" rather than an error.
        payload = {
            "message": message,
            "content": base64.b64encode(new_content.encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        if previous_sha:
            payload["sha"] = previous_sha
        resp = self._request("PUT", f"/repos/{owner}/{repo}/contents/{path}", json=payload)
        return resp.json()["commit"]["sha"]

    def create_pull_request(
        self, *, owner: str, repo: str, head_branch: str, base_branch: str, title: str, body: str
    ) -> PullRequestInfo:
        resp = self._request(
            "POST", f"/repos/{owner}/{repo}/pulls",
            json={"title": title, "body": body, "head": head_branch, "base": base_branch},
        )
        data = resp.json()
        return PullRequestInfo(
            number=data["number"], url=data["html_url"], state=data["state"],
            head_branch=head_branch, base_branch=base_branch,
        )

    def get_pull_request(self, *, owner: str, repo: str, number: int) -> PullRequestInfo:
        data = self._request("GET", f"/repos/{owner}/{repo}/pulls/{number}").json()
        state = "merged" if data.get("merged") else data["state"]
        return PullRequestInfo(
            number=data["number"], url=data["html_url"], state=state,
            head_branch=data["head"]["ref"], base_branch=data["base"]["ref"],
        )

    def get_check_runs(self, *, owner: str, repo: str, ref: str) -> list[CheckRunSummary]:
        try:
            data = self._request("GET", f"/repos/{owner}/{repo}/commits/{ref}/check-runs").json()
        except GitProviderError:
            return []
        return [
            CheckRunSummary(name=c["name"], status=c["status"], conclusion=c.get("conclusion") or "")
            for c in data.get("check_runs", [])
        ]
