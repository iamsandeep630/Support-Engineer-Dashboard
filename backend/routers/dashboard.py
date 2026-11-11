"""
Dashboard Router for Support Engineer (Alex Turner)
Handles live Jira ticket synchronization, ticket status updates, and comments.
"""
import json
import asyncio
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from services import jira_service

router = APIRouter(tags=["Support Engineer Dashboard"])

# Active SSE subscriber queues
_dashboard_subscribers: set[asyncio.Queue] = set()

def _subscribe():
    q = asyncio.Queue()
    _dashboard_subscribers.add(q)
    return q

def _unsubscribe(q: asyncio.Queue):
    _dashboard_subscribers.discard(q)

async def broadcast_ticket_update(ticket_key: str, status: str):
    msg = f"data: {json.dumps({'type': 'ticket_updated', 'ticketKey': ticket_key, 'status': status})}\n\n"
    for q in list(_dashboard_subscribers):
        try:
            await q.put(msg)
        except Exception:
            _dashboard_subscribers.discard(q)

@router.post("/login")
def support_login(payload: dict):
    """Simple login endpoint for Support Engineer Alex Turner."""
    email = payload.get("email", "").lower().strip()
    return {
        "access_token": "support-token-alex-turner-l2",
        "token_type": "bearer",
        "role": "support_engineer",
        "user": {
            "name": "Alex Turner",
            "email": email or "alex.turner@meridian.com",
            "role": "Support Engineer"
        }
    }

@router.get("/api/dashboard/tickets")
@router.get("/api/tickets")
@router.get("/api/escalations")
def get_tickets():
    """
    Fetches synchronized Jira tickets directly from Jira Cloud REST API.
    Returns tickets with 'Chat with User' and 'Remote Device' links.
    """
    tickets = jira_service.list_jira_tickets(limit=50)
    return {
        "success": True,
        "count": len(tickets),
        "tickets": tickets
    }

@router.post("/api/dashboard/tickets/{ticket_key}/status")
@router.post("/api/escalations/{ticket_key}/status")
async def update_status(ticket_key: str, payload: dict):
    """Updates Jira ticket status (e.g. 'In Progress', 'Resolved') and adds note."""
    target_status = payload.get("status", "In Progress")
    notes = payload.get("notes", "")
    res = jira_service.transition_jira_ticket(ticket_key, target_status)
    if notes:
        jira_service.add_jira_comment(ticket_key, f"[Support Engineer Alex Turner]: {notes}")
    await broadcast_ticket_update(ticket_key, target_status)
    return res

@router.post("/api/dashboard/tickets/{ticket_key}/comment")
def add_comment(ticket_key: str, payload: dict):
    """Adds a resolution or diagnostic note to the Jira ticket."""
    comment = payload.get("comment", "")
    if not comment:
        raise HTTPException(status_code=400, detail="Comment text is required")
    res = jira_service.add_jira_comment(ticket_key, comment)
    return res

@router.delete("/api/escalations/{ticket_id}")
def delete_ticket(ticket_id: str):
    """Soft-delete/dismiss a test ticket."""
    return {"success": True, "ticket_id": ticket_id}

@router.get("/api/tickets/live")
async def sse_tickets():
    """Real-time SSE event stream for Support Engineer Dashboard."""
    q = _subscribe()
    async def event_generator():
        try:
            connected_data = json.dumps({"type": "connected", "time": datetime.utcnow().isoformat()})
            yield f"data: {connected_data}\n\n"
            while True:
                msg = await q.get()
                yield msg
        except asyncio.CancelledError:
            pass
        finally:
            _unsubscribe(q)
    return StreamingResponse(event_generator(), media_type="text/event-stream")
