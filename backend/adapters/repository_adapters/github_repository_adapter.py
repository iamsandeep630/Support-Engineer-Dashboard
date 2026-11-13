"""
GitHub Repository Secondary Adapter
Implements ICodeRepositoryPort using GitHub REST API v3 with local filesystem fallback.
"""
import os
import json
import base64
import urllib.request
import urllib.error
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from ports.repository_port import ICodeRepositoryPort

logger = logging.getLogger("github_repository_adapter")


class GitHubRepositoryAdapter(ICodeRepositoryPort):
    """Adapter interacting with GitHub repository and local workspace."""

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

    def _http_request(self, endpoint: str, method: str = "GET", data: Optional[dict] = None) -> Any:
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/{endpoint.lstrip('/')}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Support-Dashboard-CodeAnalysisAgent/2.0",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        body = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_text = resp.read().decode("utf-8")
                return json.loads(resp_text) if resp_text else {}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8") if e.fp else ""
            return {"error": f"HTTP {e.code}", "detail": err_body}
        except Exception as e:
            return {"error": str(e)}

    def list_directory(self, path: str = "") -> List[Dict[str, Any]]:
        """Lists files and directories under the given relative path."""
        # 1. Local workspace directory inspection
        target_dir = self.enterprise_dir / path.lstrip("/").replace("\\", "/")
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
                logger.warning(f"Local list_directory error for '{path}': {e}")

        # 2. GitHub REST API fallback
        endpoint = f"contents/{path.lstrip('/')}"
        res = self._http_request(endpoint)
        if isinstance(res, list):
            return [
                {
                    "name": item.get("name", ""),
                    "path": item.get("path", ""),
                    "type": item.get("type", "file")
                }
                for item in res
            ]
        return []

    def get_file_contents(self, path: str) -> Optional[str]:
        # Check local workspace first for instant ground-truth
        local_path = self.enterprise_dir / path.lstrip("/")
        if local_path.is_file():
            try:
                return local_path.read_text(encoding="utf-8")
            except Exception:
                pass

        # Check GitHub API
        res = self._http_request(f"contents/{path.lstrip('/')}")
        if isinstance(res, dict) and "content" in res:
            try:
                return base64.b64decode(res["content"]).decode("utf-8")
            except Exception:
                pass
        return None

    def search_code(self, query: str, path_filter: Optional[str] = None) -> Dict[str, Any]:
        """Searches symbols and text across local workspace with remote GitHub API fallback."""
        query_clean = query.strip()
        if not query_clean:
            return {"total_count": 0, "items": [], "status": "empty"}

        # 1. Local Workspace Search (Fast, offline, ground truth)
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
                            # Check if query or search terms appear on line or filename
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
                    "source": "local_workspace"
                }

        # 2. Fallback to GitHub Search API
        url = f"https://api.github.com/search/code?q={urllib.request.quote(query_clean)}+repo:{self.owner}/{self.repo}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Support-Dashboard-CodeAnalysisAgent/2.0"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                items = []
                for item in res.get("items", [])[:15]:
                    items.append({
                        "name": item.get("name", ""),
                        "path": item.get("path", ""),
                        "line_number": 1,
                        "line_content": f"Matched in {item.get('path', '')}"
                    })
                return {
                    "total_count": res.get("total_count", len(items)),
                    "items": items,
                    "status": "success",
                    "source": "github_api"
                }
        except Exception as e:
            return {"total_count": 0, "items": [], "error": str(e), "status": "failed"}

    def list_commits(self, path: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        endpoint = f"commits?per_page={limit}"
        if path:
            endpoint += f"&path={path.lstrip('/')}"
        res = self._http_request(endpoint)
        return res if isinstance(res, list) else []

    def commit_file_change(self, path: str, content: str, commit_message: str) -> Dict[str, Any]:
        # 1. Update local workspace file
        local_path = self.enterprise_dir / path.lstrip("/")
        local_ok = False
        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(content, encoding="utf-8")
            local_ok = True
        except Exception:
            local_ok = False

        # 2. Commit via GitHub API if token available
        sha = None
        current_res = self._http_request(f"contents/{path.lstrip('/')}")
        if isinstance(current_res, dict) and "sha" in current_res:
            sha = current_res["sha"]

        payload = {
            "message": commit_message,
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8")
        }
        if sha:
            payload["sha"] = sha

        put_res = self._http_request(f"contents/{path.lstrip('/')}", method="PUT", data=payload)
        remote_ok = isinstance(put_res, dict) and "content" in put_res

        commit_sha = ""
        if remote_ok:
            commit_sha = put_res.get("commit", {}).get("sha", "")[:7]

        return {
            "success": local_ok or remote_ok,
            "local_applied": local_ok,
            "remote_committed": remote_ok,
            "commit_sha": commit_sha or "local-patched",
            "path": path,
            "message": commit_message
        }

