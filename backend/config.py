"""
Configuration for Support Engineer Dashboard
Port: 8002
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory: root of Support Engineer Dashboard/
BACKEND_DIR = Path(__file__).resolve().parent
BASE_DIR = BACKEND_DIR.parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

# Server Config (Port 8002 for Support Engineer Dashboard)
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("SUPPORT_PORT", "8002"))

# Enterprise Application URL (Port 8001)
ENTERPRISE_APP_URL = os.getenv("ENTERPRISE_APP_URL", "http://localhost:8001")

# Templates and Static Directories
TEMPLATES_DIR = BASE_DIR / "frontend" / "templates"
STATIC_DIR = BASE_DIR / "frontend" / "static"
STATIC_DIR.mkdir(exist_ok=True)

# Atlassian Jira Configuration (Direct cloud synchronization)
_raw_jira_url = (os.getenv("JIRA_INSTANCE_URL") or os.getenv("JIRA_HOST") or "https://iamsandeep630.atlassian.net").strip().strip('"').strip("'").rstrip("/")
if _raw_jira_url and not _raw_jira_url.startswith("http"):
    _raw_jira_url = f"https://{_raw_jira_url}"
JIRA_INSTANCE_URL = _raw_jira_url
JIRA_EMAIL = (os.getenv("JIRA_EMAIL") or os.getenv("JIRA_USERNAME") or "iamsandeep630@gmail.com").strip().strip('"').strip("'")
JIRA_API_TOKEN = (os.getenv("JIRA_API_TOKEN") or os.getenv("JIRA_API_KEY") or "").strip().strip('"').strip("'")
JIRA_PROJECT_KEY = (os.getenv("JIRA_PROJECT_KEY") or "SCRUM").strip().strip('"').strip("'")

# AWS Bedrock (for AI Code Analysis if needed)
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")

# GitHub Integration (Code Analysis Agent)
GITHUB_REPO = os.getenv("GITHUB_REPO", "iamsandeep630/Meridian-Enterprise-Application")
GITHUB_PERSONAL_ACCESS_TOKEN = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", "")
