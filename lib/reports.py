"""
Company report - aggregates companies from estimates and sends email.
"""

import json
import os
from datetime import datetime
from pathlib import Path

ESTIMATES_DIR = Path(os.environ.get("ESTIMATES_DIR", "data/estimates"))


def load_all_estimates() -> list[dict]:
    """Load all estimate JSON files."""
    if not ESTIMATES_DIR.exists():
        return []
    estimates = []
    for path in ESTIMATES_DIR.glob("EST-*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
                data["_file"] = path.name
                estimates.append(data)
        except Exception:
            continue
    return estimates


def build_company_report() -> tuple[list[dict], str]:
    """
    Aggregate estimates by company (only those with client_company).
    Returns (list of company entries, report body text).
    """
    estimates = load_all_estimates()
    # Group by company: company_name -> list of estimates
    by_company: dict[str, list[dict]] = {}
    for est in estimates:
        company = (est.get("client_company") or "").strip()
        if not company:
            continue
        if company not in by_company:
            by_company[company] = []
        by_company[company].append(est)

    # Build report entries
    entries = []
    for company, ests in sorted(by_company.items(), key=lambda x: x[0].lower()):
        # Get unique contacts (name + email)
        contacts = set()
        last_date = None
        for e in ests:
            name = e.get("client_name") or "-"
            email = e.get("client_email") or "-"
            contacts.add((name, email))
            eid = e.get("estimate_id", "")
            if eid.startswith("EST-"):
                try:
                    # EST-20260225-0001 -> 2026-02-25
                    date_str = eid[4:12]
                    dt = datetime.strptime(date_str, "%Y%m%d")
                    if last_date is None or dt > last_date:
                        last_date = dt
                except Exception:
                    pass
        entries.append(
            {
                "company": company,
                "estimate_count": len(ests),
                "contacts": sorted(contacts),
                "last_estimate": last_date.strftime("%Y-%m-%d") if last_date else "-",
            }
        )

    # Build email body
    lines = [
        "Reporte de empresas - Presupuestos merch7am",
        f"Generado: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"Total empresas: {len(entries)}",
        "",
        "--- Empresas ---",
        "",
    ]
    for e in entries:
        lines.append(f"• {e['company']}")
        lines.append(f"  Presupuestos: {e['estimate_count']} | Último: {e['last_estimate']}")
        for name, email in e["contacts"]:
            lines.append(f"  - {name} <{email}>")
        lines.append("")

    return entries, "\n".join(lines)


def send_company_report() -> tuple[bool, str]:
    """
    Send company report email. Returns (success, message).
    """
    api_key = os.environ.get("RESEND_API_KEY")
    to_email = os.environ.get("REPORT_EMAIL") or os.environ.get("ADMIN_EMAIL")
    from_email = os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev")

    if not api_key or not to_email:
        return False, "REPORT_EMAIL (or ADMIN_EMAIL) and RESEND_API_KEY required"

    entries, body = build_company_report()
    if not entries:
        body = "No hay empresas con presupuestos registrados."
    try:
        import httpx

        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "from": from_email,
                "to": [to_email],
                "subject": f"[merch7am] Reporte empresas - {len(entries)} empresas con presupuestos",
                "text": body,
            },
            timeout=10,
        )
        if r.status_code >= 400:
            return False, f"Email failed: {r.text}"
        return True, f"Report sent to {to_email} ({len(entries)} companies)"
    except Exception as e:
        return False, str(e)
