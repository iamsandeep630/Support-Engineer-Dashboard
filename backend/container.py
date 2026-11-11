"""
Dependency Injection Container / Service Registry
Wires Hexagonal Architecture Ports to their concrete Adapters for Support Engineer Dashboard.
Supports both native GitHub REST Adapter and official GitHub MCP Server Adapter.
"""
import os
from dotenv import load_dotenv

load_dotenv()

from ports.repository_port import ICodeRepositoryPort
from ports.cicd_port import ICICDDeploymentPort
from ports.catalog_sync_port import IEnterpriseAppSyncPort
from ports.ticketing_port import ITicketingPort

from adapters.github_repository_adapter import GitHubRepositoryAdapter
from adapters.github_mcp_adapter import GitHubMCPAdapter
from adapters.github_actions_adapter import GitHubActionsAdapter
from adapters.enterprise_app_sync_adapter import EnterpriseAppSyncAdapter
from adapters.jira_cloud_adapter import JiraCloudDashboardAdapter


class Container:
    """Central container managing port instances for Support Engineer Dashboard."""

    _token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN") or os.getenv("GITHUB_PAT") or os.getenv("GITHUB_TOKEN") or ""
    _owner = "iamsandeep630"
    _repo = "Meridian-Enterprise-Application"
    _use_mcp = os.getenv("USE_GITHUB_MCP", "false").lower() in ["1", "true", "yes"]

    if _use_mcp:
        _repository_port: ICodeRepositoryPort = GitHubMCPAdapter(owner=_owner, repo=_repo, token=_token)
    else:
        _repository_port: ICodeRepositoryPort = GitHubRepositoryAdapter(owner=_owner, repo=_repo, token=_token)

    _cicd_port: ICICDDeploymentPort = GitHubActionsAdapter(owner=_owner, repo=_repo, token=_token)
    _catalog_sync_port: IEnterpriseAppSyncPort = EnterpriseAppSyncAdapter(base_url=os.getenv("ENTERPRISE_APP_URL", "http://localhost:8001"))
    _ticketing_port: ITicketingPort = JiraCloudDashboardAdapter()

    @classmethod
    def get_repository_port(cls) -> ICodeRepositoryPort:
        return cls._repository_port

    @classmethod
    def set_repository_port(cls, port: ICodeRepositoryPort) -> None:
        cls._repository_port = port

    @classmethod
    def get_cicd_port(cls) -> ICICDDeploymentPort:
        return cls._cicd_port

    @classmethod
    def get_catalog_sync_port(cls) -> IEnterpriseAppSyncPort:
        return cls._catalog_sync_port

    @classmethod
    def get_ticketing_port(cls) -> ITicketingPort:
        return cls._ticketing_port
