"""
CI/CD Deployment Port (Outbound Driven Port)
Defines abstract interface for triggering and inspecting cloud deployment pipelines.
"""
from typing import Protocol, runtime_checkable, Dict, Any, Optional


@runtime_checkable
class ICICDDeploymentPort(Protocol):
    """Outbound port for CI/CD workflow triggers and health tracking."""

    def trigger_workflow(self, workflow_file: str, ref: str = "main", environment: str = "production") -> Dict[str, Any]:
        """Dispatches an automated deployment pipeline workflow."""
        ...

    def get_workflow_status(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        """Queries the status and health conclusion of the latest pipeline run."""
        ...

    def rollback_deployment(self, workflow_file: str = "deploy-ec2.yml", target_commit: Optional[str] = None) -> Dict[str, Any]:
        """Rolls back the deployment to the previous stable release or restores backup."""
        ...

