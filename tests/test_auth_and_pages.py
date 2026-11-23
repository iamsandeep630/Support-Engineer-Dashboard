"""
Unit & Integration Tests for Support Engineer Dashboard Authentication & Page Routing:
1. Root '/' route redirects to '/login' (HTTP 302).
2. '/login' and '/login.html' return HTTP 200 with the branded login template.
3. '/login' POST validates credentials:
   - alex@meridian.com / pass123 -> HTTP 200 with access token.
   - alex / pass123 -> HTTP 200.
   - alex.turner@meridian.com / pass123 -> HTTP 200.
   - Invalid password or username -> HTTP 401 Unauthorized.
4. '/me' and '/api/auth/me' return Alex Turner profile.
5. Auth guard exists in 'support_dashboard.html' to redirect unauthenticated users to 'login.html'.
"""
import unittest
import sys
from pathlib import Path
from starlette.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from main import app
from config import TEMPLATES_DIR


class TestAuthAndPages(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_root_redirects_to_login(self):
        """Root route '/' should redirect directly to '/login'."""
        res = self.client.get("/", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers.get("location"), "/login")

    def test_login_page_renders_meridian_ui(self):
        """'/login' should serve login.html containing Meridian branding and clean login form without credentials banner."""
        res = self.client.get("/login")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Meridian", res.text)
        self.assertIn("Support Engineer Sign In", res.text)
        self.assertIn("alex@meridian.com", res.text)
        self.assertNotIn("pass123", res.text)
        self.assertNotIn("Credentials", res.text)
        self.assertIn("role-toggle-bar", res.text)
        self.assertIn("brand-header", res.text)

    def test_login_page_html_alias(self):
        """'/login.html' should serve the exact same login template."""
        res = self.client.get("/login.html")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Support Engineer Sign In", res.text)

    def test_login_success_with_primary_credentials(self):
        """POST /login with alex@meridian.com / pass123 succeeds with bearer token."""
        payload = {"email": "alex@meridian.com", "password": "pass123"}
        res = self.client.post("/login", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data.get("role"), "support_engineer")
        self.assertEqual(data.get("user", {}).get("email"), "alex@meridian.com")

    def test_login_success_with_alias_usernames(self):
        """POST /login accepts username aliases like 'alex' and 'alex.turner@meridian.com'."""
        for alias in ["alex", "alex.turner@meridian.com", "alex.turner"]:
            res = self.client.post("/login", json={"email": alias, "password": "pass123"})
            self.assertEqual(res.status_code, 200, f"Failed for alias: {alias}")

    def test_login_rejects_invalid_password(self):
        """POST /login with wrong password returns HTTP 401 Unauthorized."""
        payload = {"email": "alex@meridian.com", "password": "incorrect_password"}
        res = self.client.post("/login", json=payload)
        self.assertEqual(res.status_code, 401)
        self.assertIn("Incorrect", res.json().get("detail", ""))

    def test_login_rejects_invalid_user(self):
        """POST /login with unknown user returns HTTP 401 Unauthorized."""
        payload = {"email": "intruder@external.com", "password": "pass123"}
        res = self.client.post("/login", json=payload)
        self.assertEqual(res.status_code, 401)

    def test_auth_me_profile_endpoints(self):
        """'/me' and '/api/auth/me' return Alex Turner's profile."""
        for endpoint in ["/me", "/api/auth/me"]:
            res = self.client.get(endpoint)
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data.get("name"), "Alex Turner")
            self.assertEqual(data.get("email"), "alex@meridian.com")
            self.assertEqual(data.get("role"), "support_engineer")

    def test_support_dashboard_has_auth_guard(self):
        """'support_dashboard.html' must have a client-side auth guard redirecting to login.html if unauthenticated."""
        dashboard_tpl = TEMPLATES_DIR / "support_dashboard.html"
        self.assertTrue(dashboard_tpl.exists())
        content = dashboard_tpl.read_text(encoding="utf-8")
        self.assertIn("localStorage.getItem(\"support_token\")", content)
        self.assertIn("window.location.replace(\"login.html\")", content)


if __name__ == "__main__":
    unittest.main()
