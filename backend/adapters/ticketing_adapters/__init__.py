"""
Ticketing Adapters - Implementations of ITicketingPort.
Provides pluggable adapters for Jira Cloud and other issue trackers.
"""
from adapters.ticketing_adapters.jira_cloud_adapter import JiraCloudDashboardAdapter

__all__ = [
    "JiraCloudDashboardAdapter"
]

