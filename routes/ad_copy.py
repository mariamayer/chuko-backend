"""
Ad Copy Refresh Agent — HTTP endpoints.

POST /api/agents/ad-copy         → generate Meta + Google ad copy for one product
GET  /api/agents/ad-copy/refresh → refresh ad copy for all Shopify products
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from lib.agent_runs import save_run
from lib.ad_copy import generate_ad_copy_for_handle, generate_ad_copy_refresh_all

router = APIRouter(prefix="/api/agents/ad-copy", tags=["agents"])


class AdCopyRequest(BaseModel):
    handle: str = Field(..., min_length=1, max_length=200, description="Shopify product handle")
    performance_notes: str = Field(
        default="",
        max_length=500,
        description="Optional notes about current ad performance",
    )
    client_id: str = Field(default="default", description="Client identifier")


@router.post("")
def ad_copy(req: AdCopyRequest):
    """Generate 3 Meta + 2 Google ad copy variations for a product and save the run."""
    result = generate_ad_copy_for_handle(req.handle, req.performance_notes)
    if "error" in result:
        status_code = 404 if "not found" in result["error"].lower() else 500
        raise HTTPException(status_code=status_code, detail=result["error"])
    save_run(req.client_id, "ad_copy", result)
    return {"ok": True, "ad_copy": result}


@router.get("/refresh")
def ad_copy_refresh(client_id: str = Query(default="default")):
    """Refresh ad copy for all products and save a bulk run."""
    results = generate_ad_copy_refresh_all()
    save_run(client_id, "ad_copy", {"ad_copies": results, "count": len(results)})
    return {"ok": True, "count": len(results), "ad_copy": results}
