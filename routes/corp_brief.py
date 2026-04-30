"""
Corporate brief modal — storefront posts here; we email via Resend (server-side only).
"""

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from lib.email_send import send_corp_brief_email

router = APIRouter(prefix="/api", tags=["corp-brief"])


class CorpBriefPayload(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=120)
    apellido: str = Field(..., min_length=1, max_length=120)
    empresa: str = Field(..., min_length=1, max_length=200)
    puesto: str = Field(..., min_length=1, max_length=120)
    email: str = Field(..., min_length=5, max_length=254, pattern=r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
    tel: str = Field("", max_length=80)
    preferencia_contacto: str = Field("", max_length=32)
    tipo: str = Field("", max_length=80)
    logo: str = Field("", max_length=80)
    contexto: str = Field("", max_length=12000)

    como: str = Field("", max_length=160)
    cantidad: str = Field("", max_length=160)
    fecha: str = Field("", max_length=160)

    form_token: str | None = Field(None, max_length=256)

    model_config = {"extra": "ignore"}


@router.post("/corp-brief")
async def post_corp_brief(body: CorpBriefPayload):
    secret = os.environ.get("BRIEF_FORM_SECRET", "").strip()
    if secret and (body.form_token or "").strip() != secret:
        raise HTTPException(status_code=403, detail="Invalid form token")

    payload = body.model_dump(exclude={"form_token"}, exclude_none=True)
    ok, msg = send_corp_brief_email(payload)
    if not ok:
        raise HTTPException(status_code=500, detail=msg)
    return {"ok": True}
