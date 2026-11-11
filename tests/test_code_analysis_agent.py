"""
Tests for CodeAnalysisAgent (Strands Agents + Fake Bedrock + Fake MCP Session)
Verifies:
1. LLM tool list never contains raw write tools.
2. Agent executes read tools and produces structured diagnosis.
3. Missing GitHub token returns clean guidance.
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

from agents.code_analysis_agent import CodeAnalysisAgent, ALLOWED_READ_TOOLS


class TestCodeAnalysisAgent(unittest.TestCase):

    def setUp(self):
        self.agent = CodeAnalysisAgent()

    def test_system_prompt_loading(self):
        """Verify system prompt loads from system_prompt.py with target repo formatting."""
        prompt = self.agent.system_prompt
        self.assertIn("Code Analysis Agent (SmartFix)", prompt)
        self.assertIn(f"Target repository: '{self.agent.owner}/{self.agent.repo}'", prompt)
        self.assertIn("SCENARIO 6 ARCHITECTURAL CONTEXT", prompt)

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
        # Simulated list of tools returned by MCP session.list_tools()
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

        # Filter using the exact logic from CodeAnalysisAgent
        filtered = [t for t in mock_tools if t.name in ALLOWED_READ_TOOLS]

        exposed_tool_names = [t.name for t in filtered]

        # 1. Assert write tools are completely excluded
        self.assertNotIn("create_or_update_file", exposed_tool_names)
        self.assertNotIn("push_files", exposed_tool_names)
        self.assertNotIn("create_pull_request", exposed_tool_names)
        self.assertNotIn("merge_pull_request", exposed_tool_names)
        self.assertNotIn("create_branch", exposed_tool_names)

        # 2. Assert only read tools are included
        self.assertEqual(sorted(exposed_tool_names), ["get_file_contents", "list_commits", "search_code"])

    @patch("agents.code_analysis_agent._load_env_secret")
    def test_query_without_token_returns_warning(self, mock_secret):
        """Verify agent handles missing token gracefully without crashing."""
        mock_secret.return_value = ""

        agent = CodeAnalysisAgent()
        res = asyncio.run(agent.query_async("Check invoice dropdown"))
        self.assertIn("GitHub Authentication Warning", res)
        self.assertIn("GITHUB_PERSONAL_ACCESS_TOKEN", res)

    @patch("boto3.Session")
    @patch("mcp.client.stdio.stdio_client")
    @patch("agents.code_analysis_agent._load_env_secret")
    def test_bedrock_tool_use_loop_and_diagnosis(self, mock_secret, mock_stdio, mock_boto_session):
        """Simulate a Strands tool use loop with fake Bedrock Converse and fake MCP session."""
        mock_secret.side_effect = lambda keys, default="": "dummy-token" if "token" in keys[0].lower() else default

        # 1. Fake Bedrock Converse Responses:
        # Step 1: Tool use (get_file_contents)
        # Step 2: Final text response with diagnosis and diff
        step1_response = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "toolu_01",
                                "name": "get_file_contents",
                                "input": {
                                    "owner": "iamsandeep630",
                                    "repo": "Meridian-Enterprise-Application",
                                    "path": "frontend/templates/employee_portal.html"
                                }
                            }
                        }
                    ]
                }
            },
            "stopReason": "tool_use"
        }

        step2_response = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "text": (
                                "🔍 **Root Cause**: The dropdown filters by `show_in_invoice_dropdown === 1`.\n"
                                "📁 **Target File**: `backend/catalog_config.json`\n"
                                "📝 **Proposed Diff**:\n```diff\n- \"show_in_invoice_dropdown\": false\n+ \"show_in_invoice_dropdown\": true\n```\n"
                                "🛠️ **Manual Fix Instructions**: Update `backend/catalog_config.json` and reload catalog."
                            )
                        }
                    ]
                }
            },
            "stopReason": "end_turn"
        }

        mock_bedrock = MagicMock()
        mock_bedrock.converse.side_effect = [step1_response, step2_response]

        sess_instance = MagicMock()
        sess_instance.client.return_value = mock_bedrock
        mock_boto_session.return_value = sess_instance

        # 2. Fake MCP Session
        mock_mcp_tool = MagicMock()
        mock_mcp_tool.name = "get_file_contents"
        mock_mcp_tool.description = "Read file"
        mock_mcp_tool.input_schema = {}

        mock_content = MagicMock()
        mock_content.text = "sel.innerHTML = productCatalog.filter(p => p.show_in_invoice_dropdown === 1)"

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[mock_mcp_tool]))
        mock_session.call_tool = AsyncMock(return_value=MagicMock(content=[mock_content]))

        # Context manager for stdio_client
        mock_stdio_ctx = AsyncMock()
        mock_stdio_ctx.__aenter__.return_value = (MagicMock(), MagicMock())
        mock_stdio.return_value = mock_stdio_ctx

        with patch("mcp.ClientSession") as mock_session_cls:
            session_ctx = AsyncMock()
            session_ctx.__aenter__.return_value = mock_session
            mock_session_cls.return_value = session_ctx

            agent = CodeAnalysisAgent()
            result = asyncio.run(agent.query_async("Maya says 4K Webcam Pro is not showing in invoice dropdown"))

            # Verify Claude was called twice via Bedrock converse (tool use -> final response)
            self.assertEqual(mock_bedrock.converse.call_count, 2)

            # Verify MCP tool was called
            mock_session.call_tool.assert_called_once()
            call_tool_args = mock_session.call_tool.call_args[0]
            self.assertEqual(call_tool_args[0], "get_file_contents")

            # Verify final text has diagnosis and diff
            self.assertIn("Root Cause", result)
            self.assertIn("Proposed Diff", result)
            self.assertIn("Manual Fix Instructions", result)


if __name__ == "__main__":
    unittest.main()
