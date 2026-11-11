# Support Engineer Dashboard

Dedicated workspace for Support Engineer **Alex Turner** featuring **Jira Ticket Synchronization**, **Direct Chat with User**, **MeshCentral Remote Device Control**, and the **Code Analysis Agent (SmartFix)**.

---

## Overview

- **Port**: `8002`
- **Default User**: Alex Turner (`alex.turner@meridian.com` / `password123`)
- **Agent**: Code Analysis Agent (`CodeAnalysisAgent` for syntax audits, bug detection & performance analysis)
- **Ticket Synchronization**: Synchronizes live Jira Cloud tickets directly via REST API
- **Direct Links**:
  - **'Chat with User'**: Opens live SSE chat with the employee on `http://localhost:8001/support/chat/{sessionId}`
  - **'Remote Device'**: Opens the 30-minute ephemeral MeshCentral remote desktop session
- **Independent Architecture**: Fully decoupled from the Enterprise Application; Jira Cloud serves as the single source of truth

---

## Directory Layout

```
Support Engineer Dashboard/
├── run.py                     # Entry point (port 8002)
├── .env                       # Environment variables
├── requirements.txt           # Dependencies
├── backend/                   # Backend Python subsystem
│   ├── main.py                # FastAPI entry point
│   ├── config.py              # Configuration & settings
│   ├── agents/                # Code Analysis Agent
│   ├── services/              # Jira Cloud synchronization service
│   └── routers/               # Dashboard, tickets & code agent endpoints
└── frontend/                  # Frontend UI subsystem
    ├── templates/             # HTML templates
    │   ├── support_dashboard.html  # Alex's live dashboard
    │   └── login.html
    └── static/                # Static assets (CSS, JS, icons)
```

---

## Running the Application

```bash
cd "Support Engineer Dashboard"
python run.py
```

Access the dashboard at: **http://localhost:8002**
- Support Dashboard: `http://localhost:8002/` or `http://localhost:8002/dashboard`
- Login: `http://localhost:8002/login`
