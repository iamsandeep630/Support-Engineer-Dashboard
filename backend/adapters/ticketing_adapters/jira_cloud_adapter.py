"""
Jira Cloud Dashboard Secondary Adapter
Implements ITicketingPort wrapping backend Jira Cloud integration.
"""
from typing import List, Dict, Any
from ports.ticketing_port import ITicketingPort
from services import jira_service


class JiraCloudDashboardAdapter(ITicketingPort):
    """Adapter wrapping jira_service for Support Dashboard."""

    def __init__(self, service=jira_service):
        self._service = service

    def fetch_tickets(self, project_key: str = "SCRUM", max_results: int = 50) -> List[Dict[str, Any]]:
        return self._service.get_tickets_for_project(project_key=project_key, max_results=max_results)

    def update_ticket_status(self, ticket_key: str, status_name: str) -> bool:
        return self._service.update_ticket_status(ticket_key=ticket_key, status_name=status_name)

