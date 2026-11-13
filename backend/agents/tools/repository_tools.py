"""
Repository Tools for Code Analysis Agent.
Provides read-only inspection, search, and directory navigation of the codebase
via ICodeRepositoryPort.
"""
from typing import Optional, List, Dict, Any
from strands import tool

from container import Container
from ports.repository_port import ICodeRepositoryPort


def build_repository_tools(repo_port: Optional[ICodeRepositoryPort] = None):
    """Factory that returns decorated Strands tools bound to the given repository port."""
    port = repo_port or Container.get_repository_port()

    @tool
    async def list_directory(path: str = "") -> str:
        """Lists files and subdirectories under the given relative path in the repository."""
        items = port.list_directory(path)
        if items:
            formatted = [f"- [{i.get('type', 'file').upper()}] {i.get('name')} ({i.get('path')})" for i in items]
            return f"Contents of '{path or '.'}':\n" + "\n".join(formatted)
        return f"No items found in directory: {path}"

    @tool
    async def get_file_contents(path: str, owner: str = "", repo: str = "") -> str:
        """Get contents of a file via ICodeRepositoryPort."""
        content = port.get_file_contents(path)
        if content is not None:
            return content[:12000]
        return f"File not found: {path}"

    @tool
    async def search_code(q: str, path_filter: str = "") -> str:
        """Search code symbols and text via ICodeRepositoryPort with matching line details."""
        res = port.search_code(q, path_filter=path_filter or None)
        if isinstance(res, dict) and "items" in res:
            items = res.get("items", [])
            if items:
                lines_summary = []
                for item in items[:10]:
                    if isinstance(item, dict):
                        p = item.get("path", "")
                        ln = item.get("line_number", "")
                        cnt = item.get("line_content", "")
                        lines_summary.append(f"- `{p}` (L{ln}): {cnt}")
                    elif isinstance(item, str):
                        lines_summary.append(f"- {item[:150]}")
                return f"Search found {res.get('total_count', len(items))} matching occurrences:\n" + "\n".join(lines_summary)
        return f"Search completed: no matching symbols found for '{q}'."

    @tool
    async def list_commits(path: str = "", owner: str = "", repo: str = "") -> str:
        """List recent git commits via ICodeRepositoryPort."""
        commits = port.list_commits(path=path, limit=5)
        if commits:
            summaries = [f"- {c['sha'][:7]}: {c['commit']['message']} ({c['commit']['author']['name']})" for c in commits[:4]]
            return "Recent commits:\n" + "\n".join(summaries)
        return "Unable to retrieve commit log."

    return list_directory, get_file_contents, search_code, list_commits

