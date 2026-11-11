"""
Support Engineer Dashboard - Entrypoint CLI
Usage: python run.py [--port=8002] [--reload]
"""
import sys
from pathlib import Path

# Add backend directory to sys.path so backend modules can be imported directly
BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BASE_DIR))

import uvicorn
from config import HOST, PORT

if __name__ == "__main__":
    port = PORT
    reload = "--reload" in sys.argv
    for arg in sys.argv:
        if arg.startswith("--port="):
            port = int(arg.split("=")[1])
    print(f"Starting Support Engineer Dashboard on http://{HOST}:{port} (Reload: {reload})...")
    uvicorn.run("main:app", host=HOST, port=port, reload=reload, app_dir=str(BACKEND_DIR))
