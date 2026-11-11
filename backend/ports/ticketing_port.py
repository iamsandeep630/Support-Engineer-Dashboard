"""
Ticketing Dashboard Port (Outbound Driven Port)
Defines abstract interface for querying and updating support tickets for the dashboard cockpit.
"""
from typing import Protocol, runtime_checkable, Dict, Any, List, Optional


@runtime_checkable
class ITicketingPort(Protocol):
    """Outbound port for dashboard ticket synchronization."""

    def fetch_tickets(self, project_key: str = "SCRUM", max_results: int = 50) -> List[Dict[str, Any]]:
        """Retrieves and standardizes tickets from the ticketing backend."""
        ...

    def update_ticket_status(self, ticket_key: str, status_name: str) -> bool:
        """Transitions ticket lifecycle status."""
        ...
