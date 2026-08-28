"""
DeploymentProvider abstraction (§5, §18). Optional — the branch/PR workflow
works fully without one. When connected (for the *target website's own*
deployment account, never Gruvle Reach's own), it can surface a preview URL
and build status for a WebsiteChange's PR.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DeploymentStatus:
    state: str  # queued, building, ready, error, unknown
    preview_url: str = ""
    build_logs_url: str = ""


class DeploymentProvider(ABC):
    name: str = "base"

    @abstractmethod
    def configured(self) -> bool:
        ...

    @abstractmethod
    def create_preview(self, *, owner: str, repo: str, branch: str) -> DeploymentStatus:
        ...

    @abstractmethod
    def get_deployment_status(self, *, owner: str, repo: str, branch: str) -> DeploymentStatus:
        ...
