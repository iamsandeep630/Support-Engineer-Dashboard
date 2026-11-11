"""
GitHub Repository Secondary Adapter
Implements ICodeRepositoryPort using GitHub REST API v3 with local filesystem fallback.
"""
import os
import json
import base64
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Any, List
from ports.repository_port import ICodeRepositoryPort


class GitHubRepositoryAdapter(ICodeRepositoryPort):
    """Adapter interacting with GitHub repository and local workspace."""

    def __init__(self, owner: str = "iamsandeep630", repo: str = "Meridian-Enterprise-Application", token: str = ""):
        self.owner = owner
        self.repo = repo
        self.token = token
        # Resolve path to local sibling enterprise repository
        self.base_dir = Path(__file__).resolve().parent.parent.parent
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

    def search_code(self, query: str) -> Dict[str, Any]:
        url = f"https://api.github.com/search/code?q={urllib.request.quote(query)}+repo:{self.owner}/{self.repo}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Support-Dashboard-CodeAnalysisAgent/2.0"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"items": [], "error": str(e)}

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

