"""
Enterprise Application Synchronization Port (Outbound Driven Port)
Defines abstract interface for propagating live configuration reloads to running services.
"""
from typing import Protocol, runtime_checkable, Dict, Any


@runtime_checkable
class IEnterpriseAppSyncPort(Protocol):
    """Outbound port for syncing runtime configuration with Meridian Enterprise Application."""

    def reload_catalog(self, catalog_content: Dict[str, Any]) -> Dict[str, Any]:
        """Sends signed reload signal to running backend to refresh in-memory catalog."""
        ...
