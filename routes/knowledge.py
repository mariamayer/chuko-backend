"""
Knowledge Base CRUD — per-client FAQ/content entries.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import lib.knowledge as kb

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class EntryIn(BaseModel):
    topic: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=4000)


@router.get("")
def list_kb(client_id: str = "default"):
    entries = kb.list_entries(client_id)
    return {"ok": True, "client_id": client_id, "entries": entries}


@router.post("")
def create_entry(body: EntryIn, client_id: str = "default"):
    entry = kb.add_entry(client_id, body.topic, body.content)
    return {"ok": True, "entry": entry}


@router.put("/{entry_id}")
def update_entry(entry_id: str, body: EntryIn, client_id: str = "default"):
    entry = kb.update_entry(client_id, entry_id, body.topic, body.content)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"ok": True, "entry": entry}


@router.delete("/{entry_id}")
def delete_entry(entry_id: str, client_id: str = "default"):
    deleted = kb.delete_entry(client_id, entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"ok": True}
