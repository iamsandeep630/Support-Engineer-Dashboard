"""
Enterprise App Runtime Synchronization Secondary Adapter
Implements IEnterpriseAppSyncPort by issuing signed HTTP requests to Meridian Enterprise App.
Supports SSL verification bypass for self-signed development/staging load balancers.
"""
import os
import ssl
import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, List
from ports.catalog_sync_port import IEnterpriseAppSyncPort

logger = logging.getLogger("enterprise_app_sync_adapter")


class EnterpriseAppSyncAdapter(IEnterpriseAppSyncPort):
    """Adapter for runtime hot-reloads of Meridian Enterprise Application."""

    def __init__(self, base_url: str = None, sync_key: str = ""):
        # Load from environment if not explicitly provided
        configured_url = base_url or os.getenv("ENTERPRISE_APP_URL") or os.getenv("PUBLIC_APP_URL") or "https://meridian-nlb-7ae659c9d57f1a53.elb.us-east-1.amazonaws.com"
        self.base_url = configured_url.rstrip("/")
        self.sync_key = sync_key or os.getenv("ADMIN_SYNC_KEY", "meridian-admin-sync-secret-2026")
        
        # Candidate target URLs to keep local and cloud synchronized
        self.target_urls = [self.base_url]
        local_url = "http://localhost:8001"
        if local_url not in self.target_urls and self.base_url != local_url:
            self.target_urls.append(local_url)

    def reload_catalog(self, catalog_content: Dict[str, Any]) -> Dict[str, Any]:
        """Posts reload payload to all target application instances."""
        headers = {
            "Content-Type": "application/json",
            "X-Sync-Key": self.sync_key
        }
        
        # Ensure content is passed as JSON string or dict as required by API
        payload = {
            "content": json.dumps(catalog_content) if isinstance(catalog_content, dict) else str(catalog_content)
        }
        data = json.dumps(payload).encode("utf-8")

        # SSL context ignoring self-signed cert validation on NLB
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        last_result = {"success": False, "status": "skipped"}
        for target in self.target_urls:
            url = f"{target}/api/admin/catalog/reload"
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
                    resp_text = resp.read().decode("utf-8")
                    last_result = json.loads(resp_text) if resp_text else {"success": True}
                    logger.info(f"Catalog sync succeeded for {url}: {last_result}")
            except Exception as e:
                logger.warning(f"Catalog sync failed for {url}: {e}")

        return last_result
