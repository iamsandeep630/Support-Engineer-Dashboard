"""
Unit tests for AWSCodePipelineAdapter.
Verifies:
1. Conformance to ICICDDeploymentPort interface.
2. start_pipeline_execution invocation and return schema.
3. Pipeline status mapping (InProgress, Succeeded, Failed).
4. Dependency Injection via Container.
"""
import unittest
from unittest.mock import MagicMock, patch
import os
import sys
from pathlib import Path

# Add backend to path
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from ports.cicd_port import ICICDDeploymentPort
from adapters.cicd_adapters.aws_codepipeline_adapter import AWSCodePipelineAdapter
from container import Container


class TestAWSCodePipelineAdapter(unittest.TestCase):

    def setUp(self):
        self.adapter = AWSCodePipelineAdapter(
            pipeline_name="test-meridian-pipeline",
            region_name="us-east-1",
            cluster_name="meridian-cluster",
            service_name="meridian-enterprise-service"
        )

    def test_implements_cicd_port_interface(self):
        """Verify AWSCodePipelineAdapter satisfies ICICDDeploymentPort interface."""
        self.assertIsInstance(self.adapter, ICICDDeploymentPort)

    @patch("adapters.cicd_adapters.aws_codepipeline_adapter.boto3.client")
    def test_trigger_workflow_success(self, mock_boto_client):
        """Verify trigger_workflow calls start_pipeline_execution with expected parameters."""
        mock_cp = MagicMock()
        mock_cp.start_pipeline_execution.return_value = {
            "pipelineExecutionId": "exec-abc-123"
        }
        mock_boto_client.return_value = mock_cp

        adapter = AWSCodePipelineAdapter(pipeline_name="test-meridian-pipeline")
        res = adapter.trigger_workflow("deploy-ecs.yml", ref="main", environment="production")

        mock_cp.start_pipeline_execution.assert_called_once_with(name="deploy-ecs")
        self.assertTrue(res["success"])
        self.assertEqual(res["provider"], "AWS CodePipeline")
        self.assertEqual(res["run_id"], "exec-abc-123")
        self.assertEqual(res["status"], "InProgress")
        self.assertIn("AWS ECS Fargate", res["target"])

    @patch("adapters.cicd_adapters.aws_codepipeline_adapter.boto3.client")
    def test_get_workflow_status_succeeded(self, mock_boto_client):
        """Verify get_workflow_status maps Succeeded status correctly."""
        mock_cp = MagicMock()
        mock_cp.get_pipeline_execution.return_value = {
            "pipelineExecution": {
                "pipelineExecutionId": "exec-999",
                "status": "Succeeded"
            }
        }
        mock_boto_client.return_value = mock_cp

        adapter = AWSCodePipelineAdapter(pipeline_name="test-meridian-pipeline")
        status_res = adapter.get_workflow_status(run_id="exec-999")

        self.assertEqual(status_res["status"], "completed")
        self.assertEqual(status_res["conclusion"], "success")
        self.assertEqual(status_res["provider"], "AWS CodePipeline")

    @patch("adapters.cicd_adapters.aws_codepipeline_adapter.boto3.client")
    def test_get_workflow_status_failed(self, mock_boto_client):
        """Verify get_workflow_status maps Failed status correctly."""
        mock_cp = MagicMock()
        mock_cp.get_pipeline_execution.return_value = {
            "pipelineExecution": {
                "pipelineExecutionId": "exec-fail-1",
                "status": "Failed"
            }
        }
        mock_boto_client.return_value = mock_cp

        adapter = AWSCodePipelineAdapter(pipeline_name="test-meridian-pipeline")
        status_res = adapter.get_workflow_status(run_id="exec-fail-1")

        self.assertEqual(status_res["status"], "completed")
        self.assertEqual(status_res["conclusion"], "failure")

    def test_container_dependency_injection(self):
        """Verify Container allows swapping CI/CD port to AWSCodePipelineAdapter."""
        initial_port = Container.get_cicd_port()
        
        custom_pipeline_adapter = AWSCodePipelineAdapter(pipeline_name="injected-pipeline")
        Container.set_cicd_port(custom_pipeline_adapter)

        self.assertEqual(Container.get_cicd_port(), custom_pipeline_adapter)
        self.assertIsInstance(Container.get_cicd_port(), ICICDDeploymentPort)

        # Restore
        Container.set_cicd_port(initial_port)

    def test_adapter_package_exports(self):
        """Verify adapters root package and cicd_adapters subpackage export AWSCodePipelineAdapter."""
        from adapters import AWSCodePipelineAdapter as RootAdapter
        from adapters.cicd_adapters import AWSCodePipelineAdapter as SubpkgAdapter
        self.assertIs(RootAdapter, AWSCodePipelineAdapter)
        self.assertIs(SubpkgAdapter, AWSCodePipelineAdapter)


if __name__ == "__main__":
    unittest.main()

