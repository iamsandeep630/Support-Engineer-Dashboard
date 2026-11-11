"""
GitHub Model Context Protocol (MCP) Secondary Adapter
Implements ICodeRepositoryPort using Anthropic's Model Context Protocol (MCP)
connecting to @modelcontextprotocol/server-github via StdioClient.
"""
import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

from ports.repository_port import ICodeRepositoryPort

logger = logging.getLogger("github_mcp_adapter")


class GitHubMCPAdapter(ICodeRepositoryPort):
    """
    Adapter implementing ICodeRepositoryPort by dispatching tool calls to the
    official GitHub MCP Server (@modelcontextprotocol/server-github).
    """

    def __init__(self, owner: str = "iamsandeep630", repo: str = "Meridian-Enterprise-Application", token: str = ""):
        self.owner = owner
        self.repo = repo
        self.token = token
        self.base_dir = Path(__file__).resolve().parent.parent.parent
        self.enterprise_dir = self.base_dir.parent / "Meridian Enterprise Application"

    def _get_mcp_params(self):
        """Builds StdioServerParameters for launching GitHub MCP server."""
        try:
            from mcp import StdioServerParameters
            env = os.environ.copy()
            if self.token:
                env["GITHUB_PERSONAL_ACCESS_TOKEN"] = self.token
                env["GITHUB_TOKEN"] = self.token

            return StdioServerParameters(
                command="npx",
                args=["-y", "@modelcontextprotocol/server-github"],
                env=env
            )
        except Exception as e:
            logger.warning(f"Unable to build StdioServerParameters for MCP: {e}")
            return None

    async def _call_mcp_tool_async(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Executes a tool on the GitHub MCP server session."""
        try:
            from mcp import ClientSession
            from mcp.client.stdio import stdio_client

            params = self._get_mcp_params()
            if not params:
                return None

            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    return result
        except Exception as e:
            logger.warning(f"GitHub MCP call_tool failed for '{tool_name}': {e}")
            return None

    def _run_async(self, coro):
        """Runs an async coroutine synchronously or in an existing loop."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # In active loop, create new loop or run in task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(asyncio.run, coro).result(timeout=15)
            return loop.run_until_complete(coro)
        except Exception:
            return asyncio.run(coro)

    def get_file_contents(self, path: str) -> Optional[str]:
        # 1. Local workspace check for instant ground-truth
        local_path = self.enterprise_dir / path.lstrip("/")
        if local_path.is_file():
            try:
                return local_path.read_text(encoding="utf-8")
            except Exception:
                pass

        # 2. Call GitHub MCP tool: get_file_contents
        args = {
            "owner": self.owner,
            "repo": self.repo,
            "path": path.lstrip("/")
        }
        try:
            mcp_res = self._run_async(self._call_mcp_tool_async("get_file_contents", args))
            if mcp_res and hasattr(mcp_res, "content"):
                text_blocks = [c.text for c in mcp_res.content if hasattr(c, "text")]
                if text_blocks:
                    return "\n".join(text_blocks)
        except Exception as e:
            logger.warning(f"GitHub MCP get_file_contents error: {e}")

        return None

    def search_code(self, query: str) -> Dict[str, Any]:
        """Calls GitHub MCP tool: search_code."""
        args = {
            "q": f"{query} repo:{self.owner}/{self.repo}"
        }
        try:
            mcp_res = self._run_async(self._call_mcp_tool_async("search_code", args))
            if mcp_res and hasattr(mcp_res, "content"):
                text_blocks = [c.text for c in mcp_res.content if hasattr(c, "text")]
                return {"items": text_blocks, "status": "success"}
        except Exception as e:
            logger.warning(f"GitHub MCP search_code error: {e}")
        return {"items": [], "status": "empty"}

    def list_commits(self, path: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Calls GitHub MCP tool: list_commits."""
        args = {
            "owner": self.owner,
            "repo": self.repo,
            "per_page": limit
        }
        if path:
            args["path"] = path.lstrip("/")

        try:
            mcp_res = self._run_async(self._call_mcp_tool_async("list_commits", args))
            if mcp_res and hasattr(mcp_res, "content"):
                commits = []
                for c in mcp_res.content:
                    if hasattr(c, "text"):
                        commits.append({"sha": "mcp-commit", "commit": {"message": c.text, "author": {"name": "MCP"}}})
                return commits
        except Exception as e:
            logger.warning(f"GitHub MCP list_commits error: {e}")
        return []

    def commit_file_change(self, path: str, content: str, commit_message: str) -> Dict[str, Any]:
        """Calls GitHub MCP tool: create_or_update_file to push commit."""
        # 1. Update local workspace
        local_path = self.enterprise_dir / path.lstrip("/")
        local_ok = False
        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(content, encoding="utf-8")
            local_ok = True
        except Exception:
            local_ok = False

        # 2. Call GitHub MCP tool: create_or_update_file
        args = {
            "owner": self.owner,
            "repo": self.repo,
            "path": path.lstrip("/"),
            "content": content,
            "message": commit_message,
            "branch": "main"
        }
        remote_ok = False
        commit_sha = ""
        try:
            mcp_res = self._run_async(self._call_mcp_tool_async("create_or_update_file", args))
            if mcp_res:
                remote_ok = True
                commit_sha = "mcp-applied"
        except Exception as e:
            logger.warning(f"GitHub MCP commit_file_change error: {e}")

        return {
            "success": local_ok or remote_ok,
            "local_applied": local_ok,
            "remote_committed": remote_ok,
            "commit_sha": commit_sha or "mcp-patched",
            "protocol": "Model Context Protocol (MCP)",
            "path": path,
            "message": commit_message
        }
