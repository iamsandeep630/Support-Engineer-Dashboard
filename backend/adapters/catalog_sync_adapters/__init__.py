"""
Catalog Synchronization Adapters - Implementations of IEnterpriseAppSyncPort.
Provides pluggable adapters for runtime hot-reloads of Meridian Enterprise Application.
"""
from adapters.catalog_sync_adapters.enterprise_app_sync_adapter import EnterpriseAppSyncAdapter

__all__ = [
    "EnterpriseAppSyncAdapter"
]

