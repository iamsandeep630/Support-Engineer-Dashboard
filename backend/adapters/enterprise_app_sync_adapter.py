"""
Enterprise App Runtime Synchronization Secondary Adapter
Implements IEnterpriseAppSyncPort by issuing signed HTTP requests to Meridian Enterprise App.
"""
import json
import urllib.request
import urllib.error
from typing import Dict, Any
from ports.catalog_sync_port import IEnterpriseAppSyncPort


class EnterpriseAppSyncAdapter(IEnterpriseAppSyncPort):
    """Adapter for runtime hot-reloads of Meridian Enterprise Application."""

    def __init__(self, base_url: str = "http://localhost:8001", sync_key: str = "meridian-admin-sync-secret-2026"):
        self.base_url = base_url.rstrip("/")
        self.sync_key = sync_key

    def reload_catalog(self, catalog_content: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/api/admin/catalog/reload"
        headers = {
            "Content-Type": "application/json",
            "X-Sync-Key": self.sync_key
        }
        data = json.dumps({"content": catalog_content}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                resp_text = resp.read().decode("utf-8")
                return json.loads(resp_text) if resp_text else {"success": True}
        except Exception as e:
            # If server not running locally, return warning without failing
            return {"success": False, "status": "skipped", "reason": str(e)}

