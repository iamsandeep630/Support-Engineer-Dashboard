"""
Adapters Package - Hexagonal Architecture Secondary Adapters for Support Engineer Dashboard.
Organized into port-specific adapter sub-packages for modularity, clean boundaries, and easy extension.

Sub-packages:
- cicd_adapters: GitHubActionsAdapter, AWSCodePipelineAdapter (implements ICICDDeploymentPort)
- repository_adapters: GitHubRepositoryAdapter, GitHubMCPAdapter (implements ICodeRepositoryPort)
- ticketing_adapters: JiraCloudDashboardAdapter (implements ITicketingPort)
- catalog_sync_adapters: EnterpriseAppSyncAdapter (implements IEnterpriseAppSyncPort)
"""
from adapters.repository_adapters import GitHubRepositoryAdapter, GitHubMCPAdapter
from adapters.cicd_adapters import GitHubActionsAdapter, AWSCodePipelineAdapter
from adapters.ticketing_adapters import JiraCloudDashboardAdapter
from adapters.catalog_sync_adapters import EnterpriseAppSyncAdapter

__all__ = [
    "GitHubRepositoryAdapter",
    "GitHubMCPAdapter",
    "GitHubActionsAdapter",
    "AWSCodePipelineAdapter",
    "JiraCloudDashboardAdapter",
    "EnterpriseAppSyncAdapter"
]
