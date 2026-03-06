"""
SEO Content Brief Agent — HTTP endpoints.

POST /api/agents/seo-brief     → brief for a single product (by Shopify handle)
GET  /api/agents/seo-brief/all → briefs for all Shopify products
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from lib.agent_runs import save_run
from lib.seo_brief import generate_seo_brief_for_handle, generate_seo_briefs_for_all

router = APIRouter(prefix="/api/agents/seo-brief", tags=["agents"])


class SeoBriefRequest(BaseModel):
    handle: str = Field(..., min_length=1, max_length=200, description="Shopify product handle")
    client_id: str = Field(default="default", description="Client identifier")


@router.post("")
def seo_brief(req: SeoBriefRequest):
    """Generate an SEO content brief for a single product and save the run."""
    result = generate_seo_brief_for_handle(req.handle)
    if "error" in result:
        status_code = 404 if "not found" in result["error"].lower() else 500
        raise HTTPException(status_code=status_code, detail=result["error"])
    save_run(req.client_id, "seo_brief", result)
    return {"ok": True, "brief": result}


@router.get("/all")
def seo_briefs_all(client_id: str = Query(default="default")):
    """Generate SEO briefs for all Shopify products and save a bulk run."""
    results = generate_seo_briefs_for_all()
    save_run(client_id, "seo_brief", {"briefs": results, "count": len(results)})
    return {"ok": True, "count": len(results), "briefs": results}
