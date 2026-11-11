"""
Pages Router for Support Engineer Dashboard
Serves the HTML templates for Support Engineer Alex Turner.
"""
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse
from config import TEMPLATES_DIR, BASE_DIR

router = APIRouter(tags=["Pages"])

def get_template_path(filename: str) -> str:
    tpl = TEMPLATES_DIR / filename
    if tpl.exists():
        return str(tpl)
    return str(BASE_DIR / filename)

@router.get("/")
@router.get("/dashboard")
@router.get("/support-dashboard")
@router.get("/support_dashboard.html")
def support_dashboard_page():
    return FileResponse(get_template_path("support_dashboard.html"), media_type="text/html")

@router.get("/login")
@router.get("/login.html")
def login_page():
    login_path = TEMPLATES_DIR / "login.html"
    if login_path.exists():
        return FileResponse(str(login_path), media_type="text/html")
    return FileResponse(get_template_path("support_dashboard.html"), media_type="text/html")
