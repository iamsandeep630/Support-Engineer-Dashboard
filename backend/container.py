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

from adapters.repository_adapters import GitHubRepositoryAdapter, GitHubMCPAdapter
from adapters.cicd_adapters import GitHubActionsAdapter, AWSCodePipelineAdapter
from adapters.catalog_sync_adapters import EnterpriseAppSyncAdapter
from adapters.ticketing_adapters import JiraCloudDashboardAdapter


class Container:
    """Central container managing port instances for Support Engineer Dashboard."""

    _token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN") or os.getenv("GITHUB_PAT") or os.getenv("GITHUB_TOKEN") or ""
    _owner = "iamsandeep630"
    _repo = "Meridian-Enterprise-Application"
    # Default to True so GitHub MCP is the primary adapter for Code Analysis Agent
    _use_mcp = os.getenv("USE_GITHUB_MCP", "true").lower() in ["1", "true", "yes"]

    if _use_mcp:
        _repository_port: ICodeRepositoryPort = GitHubMCPAdapter(owner=_owner, repo=_repo, token=_token)
    else:
        _repository_port: ICodeRepositoryPort = GitHubRepositoryAdapter(owner=_owner, repo=_repo, token=_token)

    # CI/CD Deployment Port Provider: GitHub Actions (default) or AWS CodePipeline
    _cicd_provider = os.getenv("CICD_PROVIDER", "github_actions").lower()
    _use_aws_pipeline = _cicd_provider in ["aws", "codepipeline", "aws_codepipeline"] or os.getenv("USE_AWS_CODEPIPELINE", "false").lower() in ["1", "true", "yes"]

    if _use_aws_pipeline:
        _cicd_port: ICICDDeploymentPort = AWSCodePipelineAdapter(
            pipeline_name=os.getenv("AWS_CODEPIPELINE_NAME", "meridian-enterprise-pipeline"),
            region_name=os.getenv("AWS_DEPLOY_REGION") or os.getenv("AWS_REGION") or "us-east-1"
        )
    else:
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
    def set_cicd_port(cls, port: ICICDDeploymentPort) -> None:
        cls._cicd_port = port

    @classmethod
    def get_catalog_sync_port(cls) -> IEnterpriseAppSyncPort:
        return cls._catalog_sync_port

    @classmethod
    def get_ticketing_port(cls) -> ITicketingPort:
        return cls._ticketing_port
