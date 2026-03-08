"""
Auth endpoint — no token required (this IS the login step).
Validates admin credentials (env vars) or client credentials (client JSON password field).
"""

import os

from fastapi import APIRouter
from pydantic import BaseModel

from lib.clients import get_client

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/api/auth/login")
def login(req: LoginRequest):
    # ── Admin login ────────────────────────────────────────────────────────────
    admin_username = os.environ.get("ADMIN_USERNAME", "admin")
    admin_password = (
        os.environ.get("ADMIN_PASSWORD")
        or os.environ.get("DASHBOARD_PASSWORD", "")
    )

    if (
        req.username == admin_username
        and admin_password
        and req.password == admin_password
    ):
        return {"ok": True, "role": "admin", "name": "Admin"}

    # ── Client login ───────────────────────────────────────────────────────────
    client = get_client(req.username)
    if (
        client
        and client.get("password")
        and req.password == client["password"]
    ):
        return {
            "ok": True,
            "role": "client",
            "client_id": client["client_id"],
            "name": client["name"],
            "enabled_modules": client.get("enabled_modules", []),
        }

    return {"ok": False, "error": "Invalid credentials"}
