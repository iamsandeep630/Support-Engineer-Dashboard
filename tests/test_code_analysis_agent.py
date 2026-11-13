"""
Tests for CodeAnalysisAgent
Verifies:
1. LLM tool list never contains raw write tools.
2. Agent executes read tools and produces structured diagnosis.
3. Missing GitHub token returns clean guidance.
4. Hexagonal Architecture port dependency injection.
5. Autonomous Agent Two-Stage Human-in-the-Loop (HITL) Workflow.
"""
import unittest
import asyncio
import json
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
import sys

# Add backend to path
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from agents.code_analysis_agent import CodeAnalysisAgent, ALLOWED_READ_TOOLS, HITLStage
from ports.repository_port import ICodeRepositoryPort
from ports.cicd_port import ICICDDeploymentPort
from ports.catalog_sync_port import IEnterpriseAppSyncPort


class TestCodeAnalysisAgent(unittest.TestCase):

    def setUp(self):
        self.agent = CodeAnalysisAgent()

    def test_system_prompt_loading(self):
        """Verify system prompt loads from system_prompt.py with target repo formatting."""
        prompt = self.agent.system_prompt
        self.assertIn("Code Analysis Agent (SmartFix)", prompt)
        self.assertIn(f"Target repository: '{self.agent.owner}/{self.agent.repo}'", prompt)
        self.assertIn("REPOSITORY ARCHITECTURAL CONTEXT", prompt)

    def test_scan_snippet_regex(self):
        """Verify scan_snippet detects vulnerabilities and clean code."""
        bad_code = "eval('secret_key = 123'); NoneType"
        res_bad = self.agent.scan_snippet(bad_code)
        self.assertEqual(res_bad["status"], "warnings_detected")
        self.assertTrue(res_bad["findings_count"] >= 2)

        good_code = "def add(a, b): return a + b"
        res_good = self.agent.scan_snippet(good_code)
        self.assertEqual(res_good["status"], "clean")
        self.assertEqual(res_good["findings_count"], 0)

    def test_llm_tool_list_has_no_write_tools(self):
        """Verify that the tool list exposed to Claude never includes write tools."""
        raw_mcp_tool_names = [
            "create_or_update_file",
            "push_files",
            "create_pull_request",
            "merge_pull_request",
            "create_branch",
            "delete_file",
            "get_file_contents",
            "search_code",
            "list_commits"
        ]

        mock_tools = []
        for name in raw_mcp_tool_names:
            mock_tool = MagicMock()
            mock_tool.name = name
            mock_tool.description = f"Tool {name}"
            mock_tool.input_schema = {"type": "object"}
            mock_tools.append(mock_tool)

        filtered = [t for t in mock_tools if t.name in ALLOWED_READ_TOOLS]
        exposed_tool_names = [t.name for t in filtered]

        self.assertNotIn("create_or_update_file", exposed_tool_names)
        self.assertNotIn("push_files", exposed_tool_names)
        self.assertNotIn("create_pull_request", exposed_tool_names)
        self.assertNotIn("merge_pull_request", exposed_tool_names)
        self.assertNotIn("create_branch", exposed_tool_names)
        self.assertEqual(sorted(exposed_tool_names), ["get_file_contents", "list_commits", "search_code"])

    @patch("agents.code_analysis_agent._load_env_secret")
    def test_query_without_token_returns_warning(self, mock_secret):
        """Verify agent handles missing token gracefully without crashing."""
        mock_secret.return_value = ""

        agent = CodeAnalysisAgent()
        res = asyncio.run(agent.query_async("Check invoice dropdown"))
        self.assertIn("GitHub Authentication Warning", res)
        self.assertIn("GITHUB_PERSONAL_ACCESS_TOKEN", res)

    @patch("agents.code_analysis_agent.Agent")
    @patch("agents.code_analysis_agent._load_env_secret")
    def test_bedrock_tool_use_loop_and_diagnosis(self, mock_secret, mock_agent_cls):
        """Simulate a Strands Agent tool invocation loop and verify structured diagnosis."""
        mock_secret.side_effect = lambda keys, default="": "dummy-token" if "token" in keys[0].lower() else default

        expected_response = (
            "### 🔍 Root Cause Analysis: Invoice Dropdown Missing Products\n"
            "📁 **Target File**: `backend/catalog_config.json`\n"
            "📝 **Proposed Diff**:\n```diff\n- \"show_in_invoice_dropdown\": false\n+ \"show_in_invoice_dropdown\": true\n```\n"
            "🛠️ **Manual Fix Instructions**: Update `backend/catalog_config.json` and reload catalog."
        )

        mock_instance = AsyncMock()
        mock_instance.invoke_async = AsyncMock(return_value=expected_response)
        mock_agent_cls.return_value = mock_instance

        agent = CodeAnalysisAgent()
        result = asyncio.run(agent.query_async("Investigate why 4K Webcam Pro is not showing in invoice dropdown"))

        mock_agent_cls.assert_called_once()
        mock_instance.invoke_async.assert_called_once()
        self.assertIn("Root Cause", result)
        self.assertIn("Proposed Diff", result)
        self.assertIn("Manual Fix Instructions", result)

    def test_hexagonal_port_injection(self):
        """Verify CodeAnalysisAgent accepts injected Hexagonal ports."""
        mock_repo = MagicMock(spec=ICodeRepositoryPort)
        mock_cicd = MagicMock(spec=ICICDDeploymentPort)
        mock_sync = MagicMock(spec=IEnterpriseAppSyncPort)

        agent = CodeAnalysisAgent(
            repo_port=mock_repo,
            cicd_port=mock_cicd,
            sync_port=mock_sync
        )

        self.assertEqual(agent.repo_port, mock_repo)
        self.assertEqual(agent.cicd_port, mock_cicd)
        self.assertEqual(agent.sync_port, mock_sync)

    @patch("agents.code_analysis_agent.Agent", side_effect=Exception("Simulate fallback to HITL domain handler"))
    @patch("agents.code_analysis_agent._load_env_secret")
    def test_two_stage_hitl_workflow(self, mock_secret, mock_agent):
        """Verify Two-Stage Human-in-the-Loop: Stage 1 proposes diff, Stage 2 executes upon human approval."""
        mock_secret.side_effect = lambda keys, default="": "dummy-token" if "token" in keys[0].lower() else default

        mock_repo = MagicMock(spec=ICodeRepositoryPort)
        mock_repo.get_file_contents.return_value = '{"products": {"4K Webcam Pro": {"show_in_invoice_dropdown": false}}}'
        mock_repo.commit_file_change.return_value = {"success": True, "commit_sha": "abc1234"}

        mock_cicd = MagicMock(spec=ICICDDeploymentPort)
        mock_cicd.trigger_workflow.return_value = {"success": True, "run_id": "run-987"}

        mock_sync = MagicMock(spec=IEnterpriseAppSyncPort)
        mock_sync.reload_catalog.return_value = {"success": True}

        agent = CodeAnalysisAgent(
            repo_port=mock_repo,
            cicd_port=mock_cicd,
            sync_port=mock_sync
        )

        # ---------------------------------------------------------
        # STAGE 1: Investigation (Read-Only)
        # ---------------------------------------------------------
        stage1_res = asyncio.run(agent.query_async("Investigate why 4K Webcam Pro is not showing in dropdown"))

        self.assertIn("STAGE 1: INVESTIGATION", stage1_res)
        self.assertIn("HUMAN-IN-THE-LOOP (HITL) APPROVAL GATE", stage1_res)
        self.assertIn("[ACTION_REQUIRED", stage1_res)
        self.assertIsNotNone(agent.get_pending_action())
        self.assertEqual(agent.get_pending_action()["defect_type"], "CATALOG_DROPDOWN")

        # Verify no commit or CI/CD happened in Stage 1
        mock_repo.commit_file_change.assert_not_called()
        mock_cicd.trigger_workflow.assert_not_called()

        # ---------------------------------------------------------
        # STAGE 2: Human Approval & Execution
        # ---------------------------------------------------------
        stage2_res = asyncio.run(agent.query_async("Approve and proceed with deployment to AWS ECS Fargate"))

        self.assertIn("STAGE 2: EXECUTION COMPLETE", stage2_res)
        self.assertIn("Code Fix Applied & Production CI/CD Triggered", stage2_res)

        # Verify Stage 2 triggered commit, catalog reload, and CI/CD workflow
        mock_repo.commit_file_change.assert_called_once()
        mock_sync.reload_catalog.assert_called_once()
        mock_cicd.trigger_workflow.assert_called_once()

        # Verify pending action is cleared after deployment
        self.assertIsNone(agent.get_pending_action())

    def test_github_mcp_adapter_conformance(self):
        """Verify GitHubMCPAdapter satisfies ICodeRepositoryPort interface and local workspace lookup."""
        from adapters.repository_adapters import GitHubMCPAdapter
        adapter = GitHubMCPAdapter()
        self.assertIsInstance(adapter, ICodeRepositoryPort)

        # Test local read via MCP adapter
        content = adapter.get_file_contents("backend/catalog_config.json")
        self.assertIsNotNone(content)
        self.assertIn("4K Webcam Pro", content)

    @patch("agents.code_analysis_agent.Agent", side_effect=Exception("Fallback to domain handler"))
    @patch("agents.code_analysis_agent._load_env_secret")
    def test_navigation_device_connection_lookup(self, mock_secret, mock_agent):
        """Verify agent locates device connection function in meshcentral_service without hallucinating tax reports."""
        mock_secret.side_effect = lambda keys, default="": "dummy-token" if "token" in keys[0].lower() else default
        agent = CodeAnalysisAgent()

        query = "Can you display me the function responsible for checking device connection?"
        res = asyncio.run(agent.query_async(query))

        # Must find the real ground-truth function in meshcentral_service.py
        self.assertIn("backend/services/meshcentral_service.py", res)
        self.assertIn("list_managed_devices", res)
        # Must NOT hallucinate generate_tax_report or tax diffs
        self.assertNotIn("generate_tax_report", res)
        self.assertNotIn("tax_data", res)
        # Navigation should not require approval gate
        self.assertIsNone(agent.get_pending_action())

    @patch("agents.code_analysis_agent.Agent", side_effect=Exception("Fallback to domain handler"))
    @patch("agents.code_analysis_agent._load_env_secret")
    def test_multiturn_context_in_services_followup(self, mock_secret, mock_agent):
        """Verify multi-turn follow up preserves context and searches services correctly."""
        mock_secret.side_effect = lambda keys, default="": "dummy-token" if "token" in keys[0].lower() else default
        agent = CodeAnalysisAgent()

        history = [
            {"role": "user", "content": "Can you display me the function responsible for checking device connection?"},
            {"role": "assistant", "content": "Looking into backend services..."}
        ]

        # Follow-up message from Alex
        follow_up = "It will be within services. please check thoroughly"
        res = asyncio.run(agent.query_async(follow_up, session_id="alex-turner-1", history=history))

        self.assertIn("backend/services/meshcentral_service.py", res)
        self.assertIn("list_managed_devices", res)
        self.assertNotIn("generate_tax_report", res)
        self.assertNotIn("currency tax", res.lower())

    def test_repository_port_list_directory(self):
        """Verify ICodeRepositoryPort lists directories and files correctly."""
        services = self.agent.repo_port.list_directory("backend/services")
        names = [s["name"] for s in services]
        self.assertIn("meshcentral_service.py", names)
        self.assertIn("jira_service.py", names)
        self.assertIn("escalation_service.py", names)

    @patch("agents.code_analysis_agent.Agent", side_effect=Exception("Fallback to domain handler"))
    @patch("agents.code_analysis_agent._load_env_secret")
    def test_navigation_escalation_service_logic_lookup(self, mock_secret, mock_agent):
        """Verify agent returns authoritative breakdown when asked about escalation service logic."""
        mock_secret.side_effect = lambda keys, default="": "dummy-token" if "token" in keys[0].lower() else default
        agent = CodeAnalysisAgent()

        queries = [
            "what logic has been used in escalation service?",
            "I want to know the logic used for implementing the escalation servicve",
            "escalation_service.py"
        ]
        for q in queries:
            res = asyncio.run(agent.query_async(q))
            self.assertIn("backend/services/escalation_service.py", res)
            self.assertIn("escalate_session", res)
            self.assertIn("escalation_store", res)
            self.assertIn("broadcast_dashboard", res)
            self.assertIsNone(agent.get_pending_action())

    @patch("agents.code_analysis_agent.Agent", side_effect=Exception("Fallback to domain handler"))
    @patch("agents.code_analysis_agent._load_env_secret")
    def test_generalized_navigation_arbitrary_files(self, mock_secret, mock_agent):
        """Verify agent can navigate and inspect ANY arbitrary repository file, route, and model."""
        mock_secret.side_effect = lambda keys, default="": "dummy-token" if "token" in keys[0].lower() else default
        agent = CodeAnalysisAgent()

        # 1. Inspect enterprise.py router
        res_router = asyncio.run(agent.query_async("show me all endpoints in backend/routers/enterprise.py"))
        self.assertIn("backend/routers/enterprise.py", res_router)
        self.assertIn("/invoices", res_router)
        self.assertIn("/products", res_router)
        self.assertIn("/api/reports/quarterly-tax-reconciliation", res_router)
        self.assertIn("Registered FastAPI Endpoints", res_router)

        # 2. Inspect models.py database schemas
        res_models = asyncio.run(agent.query_async("what models are in backend/database/models.py?"))
        self.assertIn("backend/database/models.py", res_models)
        self.assertIn("Invoice", res_models)
        self.assertIn("Product", res_models)
        self.assertIn("Classes & Schemas", res_models)

    @patch("agents.code_analysis_agent.Agent", side_effect=Exception("Fallback to domain handler"))
    @patch("agents.code_analysis_agent._load_env_secret")
    def test_generalized_investigation_and_fix_arbitrary_file(self, mock_secret, mock_agent):
        """Verify agent can investigate ANY bug in ANY file, stage unified diff, and deploy upon approval."""
        mock_secret.side_effect = lambda keys, default="": "dummy-token" if "token" in keys[0].lower() else default

        mock_repo = MagicMock(spec=ICodeRepositoryPort)
        mock_repo.get_file_contents.return_value = (
            "def calculate_tax(amount: float, rate: float = -0.05) -> float:\n"
            "    return amount * rate\n"
        )
        mock_repo.commit_file_change.return_value = {"success": True, "commit_sha": "tax-fix-789"}

        mock_cicd = MagicMock(spec=ICICDDeploymentPort)
        mock_cicd.trigger_workflow.return_value = {"success": True, "run_id": "run-arbitrary-456"}

        mock_sync = MagicMock(spec=IEnterpriseAppSyncPort)

        agent = CodeAnalysisAgent(
            repo_port=mock_repo,
            cicd_port=mock_cicd,
            sync_port=mock_sync
        )

        # Stage 1: Investigation of arbitrary file
        stage1_res = asyncio.run(agent.query_async(
            "investigate bug in backend/routers/enterprise.py: replace 'rate: float = -0.05' with 'rate: float = 0.05'"
        ))

        self.assertIn("STAGE 1: INVESTIGATION", stage1_res)
        self.assertIn("backend/routers/enterprise.py", stage1_res)
        self.assertIn("diff", stage1_res.lower())
        self.assertIn("HUMAN-IN-THE-LOOP", stage1_res)

        action = agent.get_pending_action()
        self.assertIsNotNone(action)
        self.assertEqual(action["target_file"], "backend/routers/enterprise.py")
        self.assertIn("rate: float = 0.05", action["proposed_content"])

        # Stage 2: Approval & Fix Execution
        stage2_res = asyncio.run(agent.query_async("Approve and deploy fix to EC2"))

        self.assertIn("STAGE 2: EXECUTION COMPLETE", stage2_res)
        self.assertIn("backend/routers/enterprise.py", stage2_res)
        self.assertIn("deploy-ec2.yml", stage2_res)
        mock_repo.commit_file_change.assert_called_once()
        self.assertEqual(mock_repo.commit_file_change.call_args[0][0], "backend/routers/enterprise.py")
        mock_cicd.trigger_workflow.assert_called_once()
        self.assertIsNone(agent.get_pending_action())


if __name__ == "__main__":
    unittest.main()
