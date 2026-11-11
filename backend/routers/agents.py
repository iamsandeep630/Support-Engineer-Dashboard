"""
Agents Router for Support Engineer Dashboard
Hosts Code Analysis Agent (SmartFix) for Alex Turner.
"""
from fastapi import APIRouter
from agents import CodeAnalysisAgent

router = APIRouter(prefix="/api/agents", tags=["Code Analysis Agent"])

code_agent = CodeAnalysisAgent()

@router.post("/analyze-code")
@router.post("/code-analysis/query")
async def analyze_code(req: dict):
    """Queries Code Analysis Agent for code review, error diagnostics, and system insights."""
    prompt = req.get("prompt", req.get("query", "")).strip()
    if not prompt:
        return {"error": "Prompt is required"}
    result = await code_agent.query_async(prompt)
    return {"success": True, "response": result}

@router.post("/scan-repo")
@router.post("/code-analysis/scan")
def scan_code(req: dict):
    """Scans code snippets for null checks, memory leaks, bugs, and security vulnerabilities."""
    snippet = req.get("snippet", req.get("code", "")).strip()
    if not snippet:
        return {"error": "Snippet is required"}
    scan_res = code_agent.scan_snippet(snippet)
    return scan_res
