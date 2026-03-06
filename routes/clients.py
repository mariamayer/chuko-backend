"""
Client management endpoints.

GET    /api/clients              → list all clients
POST   /api/clients              → create a new client
GET    /api/clients/{client_id}  → get one client (token masked)
PUT    /api/clients/{client_id}  → update a client
DELETE /api/clients/{client_id}  → delete a client (not 'default')
"""

import os
import re

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from lib.clients import (
    AVAILABLE_MODULES,
    delete_client,
    get_client,
    list_clients,
    sanitize,
    save_client,
)

router = APIRouter(prefix="/api/clients", tags=["clients"])

_TOKEN = os.environ.get("AGENT_TOKEN") or os.environ.get("REPORT_TOKEN")


def _check_token(token: str) -> None:
    if _TOKEN and token != _TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing token")


def _to_slug(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


class ClientPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    shopify_store_domain: str = Field(default="")
    shopify_storefront_token: str = Field(default="")
    shopify_store_url: str = Field(default="")
    digest_email: str = Field(default="")
    enabled_modules: list[str] = Field(default=AVAILABLE_MODULES)


@router.get("")
def get_clients(token: str = Query(default="")):
    """List all clients (tokens masked)."""
    _check_token(token)
    return {"ok": True, "clients": [sanitize(c) for c in list_clients()]}


@router.post("", status_code=201)
def create_client(payload: ClientPayload, token: str = Query(default="")):
    """Create a new client."""
    _check_token(token)
    client_id = _to_slug(payload.name)
    if not client_id:
        raise HTTPException(status_code=422, detail="Name produces an empty slug")
    if get_client(client_id):
        raise HTTPException(status_code=409, detail=f"Client '{client_id}' already exists")
    saved = save_client(client_id, payload.model_dump())
    return {"ok": True, "client": sanitize(saved)}


@router.get("/{client_id}")
def get_one_client(client_id: str, token: str = Query(default="")):
    """Get a single client by ID (token masked)."""
    _check_token(token)
    client = get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail=f"Client '{client_id}' not found")
    return {"ok": True, "client": sanitize(client)}


@router.put("/{client_id}")
def update_client(client_id: str, payload: ClientPayload, token: str = Query(default="")):
    """Update an existing client. Sending '••••••••' for the token keeps the existing value."""
    _check_token(token)
    existing = get_client(client_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Client '{client_id}' not found")

    updated = {**existing, **payload.model_dump()}

    # If the caller sent back the masked placeholder, restore the real token
    if updated.get("shopify_storefront_token", "").startswith("•"):
        updated["shopify_storefront_token"] = existing.get("shopify_storefront_token", "")

    saved = save_client(client_id, updated)
    return {"ok": True, "client": sanitize(saved)}


@router.delete("/{client_id}")
def remove_client(client_id: str, token: str = Query(default="")):
    """Delete a client. The 'default' client cannot be deleted."""
    _check_token(token)
    if client_id == "default":
        raise HTTPException(status_code=400, detail="The default client cannot be deleted")
    if not delete_client(client_id):
        raise HTTPException(status_code=404, detail=f"Client '{client_id}' not found")
    return {"ok": True, "message": f"Client '{client_id}' deleted"}
