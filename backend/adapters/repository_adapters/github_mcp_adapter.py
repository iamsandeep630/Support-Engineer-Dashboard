"""
GitHub Model Context Protocol (MCP) Secondary Adapter
Implements ICodeRepositoryPort using Anthropic's Model Context Protocol (MCP)
connecting to @modelcontextprotocol/server-github via StdioClient.
"""
import os
import json
import base64
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

        # Resolve path to local sibling enterprise repository robustly
        self.enterprise_dir = None
        self.base_dir = None
        for p in Path(__file__).resolve().parents:
            if (p / "Meridian Enterprise Application").is_dir():
                self.enterprise_dir = p / "Meridian Enterprise Application"
                self.base_dir = p / "Support Engineer Dashboard"
                break
        if not self.enterprise_dir:
            self.base_dir = Path(__file__).resolve().parents[3]
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

    def list_directory(self, path: str = "") -> List[Dict[str, Any]]:
        """Lists files and directories under the given relative path via GitHub MCP primary."""
        clean_path = path.lstrip("/")

        # 1. Primary: Call GitHub MCP Server (@modelcontextprotocol/server-github)
        args = {
            "owner": self.owner,
            "repo": self.repo,
            "path": clean_path
        }
        try:
            mcp_res = self._run_async(self._call_mcp_tool_async("get_file_contents", args))
            if mcp_res and hasattr(mcp_res, "content"):
                for c in mcp_res.content:
                    if hasattr(c, "text"):
                        parsed = json.loads(c.text)
                        if isinstance(parsed, list):
                            return [
                                {
                                    "name": item.get("name", ""),
                                    "path": item.get("path", ""),
                                    "type": item.get("type", "file")
                                }
                                for item in parsed
                            ]
        except Exception as e:
            logger.warning(f"GitHub MCP directory listing error for '{clean_path}': {e}")

        # 2. Secondary fallback: Local workspace directory inspection
        target_dir = self.enterprise_dir / clean_path.replace("\\", "/")
        if target_dir.is_dir():
            try:
                results = []
                ignored = {".git", ".pytest_cache", "__pycache__", "node_modules", ".venv", "venv"}
                for entry in sorted(target_dir.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
                    if entry.name in ignored:
                        continue
                    rel = entry.relative_to(self.enterprise_dir).as_posix()
                    results.append({
                        "name": entry.name,
                        "path": rel,
                        "type": "dir" if entry.is_dir() else "file"
                    })
                return results
            except Exception as e:
                logger.warning(f"Local list_directory fallback error for '{clean_path}': {e}")

        return []

    def get_file_contents(self, path: str) -> Optional[str]:
        """Fetches file contents primarily via GitHub MCP Server with local fallback."""
        clean_path = path.lstrip("/")

        # 1. Primary: Call GitHub MCP Server (@modelcontextprotocol/server-github)
        args = {
            "owner": self.owner,
            "repo": self.repo,
            "path": clean_path
        }
        try:
            mcp_res = self._run_async(self._call_mcp_tool_async("get_file_contents", args))
            if mcp_res and hasattr(mcp_res, "content"):
                for c in mcp_res.content:
                    if hasattr(c, "text"):
                        try:
                            data = json.loads(c.text)
                            if isinstance(data, dict):
                                raw_cnt = data.get("content", "")
                                if isinstance(raw_cnt, str) and raw_cnt:
                                    if any(marker in raw_cnt for marker in ["\n", "import ", "def ", "class ", " ", "{", "<", ";"]):
                                        return raw_cnt
                                    try:
                                        clean = raw_cnt.replace("\n", "").replace("\r", "").strip()
                                        missing_padding = len(clean) % 4
                                        if missing_padding:
                                            clean += "=" * (4 - missing_padding)
                                        return base64.b64decode(clean).decode("utf-8")
                                    except Exception:
                                        return raw_cnt
                        except Exception:
                            return c.text
        except Exception as e:
            logger.warning(f"GitHub MCP get_file_contents error for '{clean_path}': {e}")

        # 2. Secondary fallback: Local workspace check
        local_path = self.enterprise_dir / clean_path
        if local_path.is_file():
            try:
                return local_path.read_text(encoding="utf-8")
            except Exception:
                pass

        return None

    def search_code(self, query: str, path_filter: Optional[str] = None) -> Dict[str, Any]:
        """Searches symbols and text primarily via GitHub MCP with workspace fallback."""
        query_clean = query.strip()
        if not query_clean:
            return {"total_count": 0, "items": [], "status": "empty"}

        # 1. Primary: Call GitHub MCP tool: search_code
        args = {
            "q": f"{query_clean} repo:{self.owner}/{self.repo}"
        }
        try:
            mcp_res = self._run_async(self._call_mcp_tool_async("search_code", args))
            if mcp_res and hasattr(mcp_res, "content"):
                for c in mcp_res.content:
                    if hasattr(c, "text"):
                        data = json.loads(c.text)
                        raw_items = data.get("items", [])
                        if raw_items:
                            items = []
                            for it in raw_items[:15]:
                                items.append({
                                    "name": it.get("name", "mcp-match"),
                                    "path": it.get("path", ""),
                                    "line_number": 1,
                                    "line_content": f"Matched in {it.get('path', '')}"
                                })
                            return {
                                "total_count": data.get("total_count", len(items)),
                                "items": items,
                                "status": "success",
                                "source": "github_mcp_primary"
                            }
        except Exception as e:
            logger.warning(f"GitHub MCP search_code error: {e}")

        # 2. Secondary fallback: Local Workspace Search
        if self.enterprise_dir.is_dir():
            local_items = []
            ignored_dirs = {".git", ".pytest_cache", "__pycache__", "node_modules", ".venv", "venv", ".aws"}
            binary_extensions = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".pyc", ".zip", ".tar", ".gz"}
            search_terms = [t.lower() for t in query_clean.split() if len(t) > 2] or [query_clean.lower()]

            search_root = self.enterprise_dir
            if path_filter:
                filtered_target = self.enterprise_dir / path_filter.lstrip("/").replace("\\", "/")
                if filtered_target.exists():
                    search_root = filtered_target

            files_to_check = []
            if search_root.is_file():
                files_to_check = [search_root]
            else:
                for root, dirs, files in os.walk(search_root):
                    dirs[:] = [d for d in dirs if d not in ignored_dirs]
                    for f in files:
                        p = Path(root) / f
                        if p.suffix.lower() not in binary_extensions:
                            files_to_check.append(p)

            for file_path in files_to_check:
                try:
                    rel_path = file_path.relative_to(self.enterprise_dir).as_posix()
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_idx, line in enumerate(f, 1):
                            line_low = line.lower()
                            if any(term in line_low for term in search_terms) or any(term in rel_path.lower() for term in search_terms):
                                local_items.append({
                                    "name": file_path.name,
                                    "path": rel_path,
                                    "line_number": line_idx,
                                    "line_content": line.strip()[:200]
                                })
                                if len(local_items) >= 20:
                                    break
                    if len(local_items) >= 20:
                        break
                except Exception:
                    continue

            if local_items:
                return {
                    "total_count": len(local_items),
                    "items": local_items,
                    "status": "success",
                    "source": "local_workspace_fallback"
                }

        return {"total_count": 0, "items": [], "status": "empty"}

    def list_commits(self, path: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Calls GitHub MCP tool: list_commits."""
        args = {
            "owner": self.owner,
            "repo": self.repo,
            "perPage": limit
        }
        if path:
            args["sha"] = "main"

        try:
            mcp_res = self._run_async(self._call_mcp_tool_async("list_commits", args))
            if mcp_res and hasattr(mcp_res, "content"):
                commits = []
                for c in mcp_res.content:
                    if hasattr(c, "text"):
                        try:
                            parsed = json.loads(c.text)
                            if isinstance(parsed, list):
                                for item in parsed[:limit]:
                                    sha = item.get("sha", "mcp-commit")[:7]
                                    commit_info = item.get("commit", {})
                                    msg = commit_info.get("message", "Commit via MCP")
                                    author = commit_info.get("author", {}).get("name", "MCP")
                                    commits.append({
                                        "sha": sha,
                                        "commit": {
                                            "message": msg.split("\n")[0][:80],
                                            "author": {"name": author}
                                        }
                                    })
                        except Exception:
                            commits.append({"sha": "mcp-commit", "commit": {"message": c.text[:60], "author": {"name": "MCP"}}})
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

        # 2. Look up existing file SHA for GitHub update
        clean_path = path.lstrip("/")
        sha = None
        try:
            file_res = self._run_async(self._call_mcp_tool_async(
                "get_file_contents",
                {"owner": self.owner, "repo": self.repo, "path": clean_path}
            ))
            if file_res and hasattr(file_res, "content"):
                for c in file_res.content:
                    if hasattr(c, "text"):
                        file_data = json.loads(c.text)
                        if isinstance(file_data, dict) and "sha" in file_data:
                            sha = file_data["sha"]
                            break
        except Exception as e:
            logger.warning(f"Could not retrieve existing SHA for {clean_path}: {e}")

        # 3. Call GitHub MCP tool: create_or_update_file
        args = {
            "owner": self.owner,
            "repo": self.repo,
            "path": clean_path,
            "content": content,
            "message": commit_message,
            "branch": "main"
        }
        if sha:
            args["sha"] = sha

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

