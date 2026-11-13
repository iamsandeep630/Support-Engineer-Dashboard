"""
Agents Tools Package for Support Engineer Dashboard.
Exposes categorized Hexagonal tools for:
- Repository inspection & search
- Remediation & catalog synchronization
- CI/CD deployment pipeline triggering & status tracking
"""
from typing import Optional, Tuple, Callable, List, Dict
from ports.repository_port import ICodeRepositoryPort
from ports.cicd_port import ICICDDeploymentPort
from ports.catalog_sync_port import IEnterpriseAppSyncPort

from .repository_tools import build_repository_tools
from .remediation_tools import build_remediation_tools
from .cicd_tools import build_cicd_tools


def create_code_analysis_tools(
    repo_port: Optional[ICodeRepositoryPort] = None,
    cicd_port: Optional[ICICDDeploymentPort] = None,
    sync_port: Optional[IEnterpriseAppSyncPort] = None
) -> Tuple[List[Callable], Dict[str, Callable]]:
    """
    Creates and returns all Strands tools bound to the injected ports.
    Returns:
        (tools_list, tools_dict)
    """
    list_dir, get_file, search, list_c = build_repository_tools(repo_port)
    (apply_fix,) = build_remediation_tools(repo_port, sync_port)
    trig_cicd, wf_status = build_cicd_tools(cicd_port)

    tools_list = [
        list_dir,
        get_file,
        search,
        list_c,
        apply_fix,
        trig_cicd,
        wf_status
    ]

    tools_dict = {
        "list_directory": list_dir,
        "get_file_contents": get_file,
        "search_code": search,
        "list_commits": list_c,
        "apply_code_fix": apply_fix,
        "trigger_cicd_pipeline": trig_cicd,
        "get_workflow_status": wf_status,
    }

    return tools_list, tools_dict


__all__ = [
    "build_repository_tools",
    "build_remediation_tools",
    "build_cicd_tools",
    "create_code_analysis_tools",
]
