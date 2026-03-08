"""
Knowledge Base — per-client FAQ/content entries injected into the chat system prompt.
Stored as data/knowledge/{client_id}.json
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

KB_DIR = Path("data/knowledge")


def _ensure_dir() -> None:
    KB_DIR.mkdir(parents=True, exist_ok=True)


def _path(client_id: str) -> Path:
    return KB_DIR / f"{client_id}.json"


def list_entries(client_id: str) -> list[dict]:
    _ensure_dir()
    p = _path(client_id)
    if not p.exists():
        return []
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save(client_id: str, entries: list[dict]) -> None:
    _ensure_dir()
    with open(_path(client_id), "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


def add_entry(client_id: str, topic: str, content: str) -> dict:
    entries = list_entries(client_id)
    now = datetime.utcnow().isoformat()
    entry = {
        "id": str(uuid.uuid4())[:8],
        "topic": topic,
        "content": content,
        "created_at": now,
        "updated_at": now,
    }
    entries.append(entry)
    _save(client_id, entries)
    return entry


def update_entry(client_id: str, entry_id: str, topic: str, content: str) -> dict | None:
    entries = list_entries(client_id)
    for e in entries:
        if e["id"] == entry_id:
            e["topic"] = topic
            e["content"] = content
            e["updated_at"] = datetime.utcnow().isoformat()
            _save(client_id, entries)
            return e
    return None


def delete_entry(client_id: str, entry_id: str) -> bool:
    entries = list_entries(client_id)
    new = [e for e in entries if e["id"] != entry_id]
    if len(new) == len(entries):
        return False
    _save(client_id, new)
    return True


def entries_to_prompt(entries: list[dict]) -> str:
    """Format KB entries into a string to inject into the system prompt."""
    if not entries:
        return ""
    lines = ["--- Base de conocimiento / Knowledge Base ---"]
    for e in entries:
        lines.append(f"\n## {e['topic']}\n{e['content']}")
    return "\n".join(lines)
