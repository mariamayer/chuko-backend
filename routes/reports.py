"""
Reports API - company report (triggered manually or by cron service).
"""

from fastapi import APIRouter, HTTPException, Query

from lib.reports import send_company_report

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/companies")
async def trigger_company_report(
    token: str = Query(..., description="REPORT_TOKEN from env"),
):
    """Trigger company report email. Requires ?token=REPORT_TOKEN."""
    import os

    expected = os.environ.get("REPORT_TOKEN")
    if not expected or token != expected:
        raise HTTPException(status_code=403, detail="Invalid token")
    ok, msg = send_company_report()
    if not ok:
        raise HTTPException(status_code=500, detail=msg)
    return {"ok": True, "message": msg}
