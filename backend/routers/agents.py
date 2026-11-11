"""
Agents Router for Support Engineer Dashboard
Hosts Code Analysis Agent (SmartFix) with Hexagonal Architecture & Two-Stage HITL Pattern.
"""
from fastapi import APIRouter
from agents import CodeAnalysisAgent

router = APIRouter(prefix="/api/agents", tags=["Code Analysis Agent"])

code_agent = CodeAnalysisAgent()


@router.post("/analyze-code")
@router.post("/code-analysis/query")
async def analyze_code(req: dict):
    """
    Queries Code Analysis Agent.
    Implements Two-Stage Human-in-the-Loop Pattern:
    - Stage 1: Returns investigation findings, proposed diff, and requires_approval=True
    - Stage 2: Executes commit, catalog sync, and ECS Fargate deployment when approved
    """
    prompt = req.get("prompt", req.get("query", "")).strip()
    action = req.get("action", "").strip().lower()

    if action in ["approve", "confirm", "proceed", "deploy"]:
        prompt = "approve and deploy to ecs"

    if not prompt:
        return {"error": "Prompt or approval action is required"}

    result = await code_agent.query_async(prompt)
    pending = code_agent.get_pending_action()
    requires_approval = "[ACTION_REQUIRED" in result or (pending is not None and pending.get("status") == "PENDING_APPROVAL")
    stage = "STAGE_1_INVESTIGATION" if requires_approval else "STAGE_2_EXECUTION"

    return {
        "success": True,
        "response": result,
        "stage": stage,
        "requires_approval": requires_approval,
        "pending_action": pending
    }


@router.post("/approve-deployment")
async def approve_deployment(req: dict = None):
    """Direct API endpoint for the Human-in-the-Loop approval gate."""
    result = await code_agent.query_async("approve and proceed with deployment to AWS ECS Fargate")
    return {
        "success": True,
        "stage": "STAGE_2_EXECUTION",
        "requires_approval": False,
        "response": result
    }


@router.post("/scan-repo")
@router.post("/code-analysis/scan")
def scan_code(req: dict):
    """Scans code snippets for null checks, memory leaks, bugs, and security vulnerabilities."""
    snippet = req.get("snippet", req.get("code", "")).strip()
    if not snippet:
        return {"error": "Snippet is required"}
    scan_res = code_agent.scan_snippet(snippet)
    return scan_res
