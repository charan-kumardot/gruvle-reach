"""
Read-only Vercel adapter for a *founder-connected target website's own*
Vercel account — never Gruvle Reach's own deployment credentials (those
live only in this app's own .env/.env.deploy and are unrelated). Requires
the founder to supply a Vercel API token and the target project's id via
Settings -> Integrations once they choose to connect it; until then this
adapter simply isn't instantiated and DisabledDeploymentProvider is used.
"""
import httpx

from app.providers.deployment.base import DeploymentProvider, DeploymentStatus

_API_BASE = "https://api.vercel.com"


class VercelProvider(DeploymentProvider):
    name = "vercel"

    def __init__(self, token: str, project_id: str):
        self._token = token
        self._project_id = project_id

    def configured(self) -> bool:
        return bool(self._token and self._project_id)

    def create_preview(self, *, owner: str, repo: str, branch: str) -> DeploymentStatus:
        # Vercel creates previews automatically via its own GitHub integration
        # once a branch/PR exists — Reach doesn't trigger deployments itself,
        # it only reads status (see get_deployment_status).
        return self.get_deployment_status(owner=owner, repo=repo, branch=branch)

    def get_deployment_status(self, *, owner: str, repo: str, branch: str) -> DeploymentStatus:
        if not self.configured():
            return DeploymentStatus(state="unknown")
        try:
            resp = httpx.get(
                f"{_API_BASE}/v6/deployments",
                headers={"Authorization": f"Bearer {self._token}"},
                params={"projectId": self._project_id, "limit": 1, "meta-githubCommitRef": branch},
                timeout=15,
            )
            resp.raise_for_status()
        except httpx.HTTPError:
            return DeploymentStatus(state="unknown")

        deployments = resp.json().get("deployments", [])
        if not deployments:
            return DeploymentStatus(state="unknown")

        d = deployments[0]
        state_map = {"READY": "ready", "BUILDING": "building", "QUEUED": "queued", "ERROR": "error"}
        return DeploymentStatus(
            state=state_map.get(d.get("readyState", ""), "unknown"),
            preview_url=f"https://{d['url']}" if d.get("url") else "",
            build_logs_url=f"https://vercel.com/{owner}/{repo}/{d.get('uid', '')}" if d.get("uid") else "",
        )
