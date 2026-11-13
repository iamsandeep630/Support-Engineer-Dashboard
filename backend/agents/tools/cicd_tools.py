"""
CI/CD Deployment Tools for Code Analysis Agent.
Provides pipeline triggering and workflow run status inspection
via ICICDDeploymentPort targeting Meridian Enterprise Application on EC2 Instance.
"""
from typing import Optional
from strands import tool

from container import Container
from ports.cicd_port import ICICDDeploymentPort


def build_cicd_tools(cicd_port: Optional[ICICDDeploymentPort] = None):
    """Factory that returns decorated Strands CI/CD tools bound to port."""
    port = cicd_port or Container.get_cicd_port()

    @tool
    async def trigger_cicd_pipeline(
        workflow_file: str = "deploy-ec2.yml",
        ref: str = "main",
        environment: str = "production"
    ) -> str:
        """Dispatches CI/CD workflow via ICICDDeploymentPort targeting Meridian Enterprise Application deployed on EC2."""
        res = port.trigger_workflow(workflow_file=workflow_file, ref=ref, environment=environment)
        return f"CI/CD Pipeline '{workflow_file}' triggered for Meridian Enterprise Application on EC2 Instance. Run ID: {res.get('run_id')}."

    @tool
    async def get_workflow_status(run_id: str = "") -> str:
        """Checks status of deployment workflow via ICICDDeploymentPort."""
        status_res = port.get_workflow_status(run_id=run_id)
        return f"Workflow #{status_res.get('run_id')}: {status_res.get('status')} - Conclusion: {status_res.get('conclusion')}."

    return trigger_cicd_pipeline, get_workflow_status

