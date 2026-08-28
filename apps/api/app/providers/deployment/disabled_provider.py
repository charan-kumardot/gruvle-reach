from app.providers.deployment.base import DeploymentProvider, DeploymentStatus


class DisabledDeploymentProvider(DeploymentProvider):
    """Default when no deployment platform is connected for a website. The
    branch/PR workflow (§19) is fully unaffected — the UI shows 'Preview
    unavailable. Review the GitHub diff before merging.' (§18)."""

    name = "disabled"

    def configured(self) -> bool:
        return False

    def create_preview(self, *, owner: str, repo: str, branch: str) -> DeploymentStatus:
        return DeploymentStatus(state="unknown")

    def get_deployment_status(self, *, owner: str, repo: str, branch: str) -> DeploymentStatus:
        return DeploymentStatus(state="unknown")
