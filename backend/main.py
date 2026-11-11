"""
Support Engineer Dashboard Backend
Hosts Jira Ticket Synchronization & Code Analysis Agent (SmartFix) for Alex Turner
Port: 8002
"""
import sys
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import STATIC_DIR
from routers import dashboard, agents, pages

app = FastAPI(
    title="Support Engineer Dashboard API",
    version="2.0.0",
    description="Support Engineer Dashboard with Jira Ticket Synchronization & Code Analysis Agent"
)

# CORS Middleware - allows cross-origin requests from Enterprise App
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# No-Cache headers middleware
@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.endswith((".html", ".js", ".css")) or request.url.path in ["/", "/dashboard"]:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Mount Modular Routers
app.include_router(dashboard.router)
app.include_router(agents.router)
app.include_router(pages.router)

# Mount Static Files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Support Engineer Dashboard",
        "port": 8002,
        "agents": ["CodeAnalysisAgent"]
    }
