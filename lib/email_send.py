"""
Email sending - admin and client notifications for estimates.
Uses Resend (https://resend.com) if RESEND_API_KEY is set, else no-op.
"""

import os
from typing import Any


def _format_currency(amount: float, currency: str = "USD") -> str:
    return f"{currency} {amount:,.2f}"


def _build_admin_body(estimate_id: str, data: dict) -> str:
    breakdown = data.get("breakdown", {})
    meta = data.get("meta", {})
    analysis = data.get("analysis", {})
    lines = [
        f"Estimate #{estimate_id}",
        "",
        "--- Summary ---",
        f"Total: {_format_currency(data.get('estimate', 0), data.get('currency', 'USD'))}",
        f"Quantity: {breakdown.get('quantity', '-')}",
        f"Size: {breakdown.get('size') or '-'}",
        f"Color: {breakdown.get('color') or '-'}",
        f"Product ID: {meta.get('product_id', '-')}",
        f"Variant ID: {meta.get('variant_id', '-')}",
        "",
        "--- Pricing breakdown ---",
        f"Logo size: {breakdown.get('logo_size', '-')}",
        f"Color count: {breakdown.get('color_count', '-')}",
        f"Unit price: {breakdown.get('unit_price_cents', 0) / 100:.2f}",
        "",
    ]
    if data.get("client_name") or data.get("client_email") or data.get("client_company"):
        lines.extend([
            "--- Client ---",
            f"Name: {data.get('client_name', '-')}",
            f"Email: {data.get('client_email', '-')}",
            f"Company: {data.get('client_company', '-')}",
            "",
        ])
    if analysis:
        lines.append("--- Design analysis ---")
        for k, v in analysis.items():
            if isinstance(v, dict):
                lines.append(f"  {k}: {v.get('logo_size', '-')} / {v.get('color_count', '-')} colors")
            else:
                lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def _build_client_body(estimate_id: str, data: dict) -> str:
    breakdown = data.get("breakdown", {})
    lines = [
        f"Your estimate #{estimate_id}",
        "",
        f"Total: {_format_currency(data.get('estimate', 0), data.get('currency', 'USD'))}",
        f"Quantity: {breakdown.get('quantity', '-')} units",
        f"Size: {breakdown.get('size') or 'N/A'}",
        f"Color: {breakdown.get('color') or 'N/A'}",
        "",
    ]
    if data.get("client_company"):
        lines.append(f"Company: {data.get('client_company')}")
        lines.append("")
    lines.append("Guarda este número de referencia. Podés contestar a este email para cualquier consulta.")
    return "\n".join(lines)


def send_estimate_emails(estimate_id: str, data: dict) -> tuple[bool, str]:
    """
    Send estimate emails to admin and client.
    Returns (success, message).
    """
    api_key = os.environ.get("RESEND_API_KEY")
    admin_email = os.environ.get("ADMIN_EMAIL")
    from_email = os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev")

    if not api_key or not admin_email:
        return False, "Email not configured (RESEND_API_KEY, ADMIN_EMAIL)"

    client_email = data.get("client_email")
    if not client_email:
        return False, "No client email"

    try:
        import httpx

        quantity = data.get("breakdown", {}).get("quantity", 0) or 0
        client_body = _build_client_body(estimate_id, data)

        # Send to admin only when quantity >= 100
        if quantity >= 100:
            admin_body = _build_admin_body(estimate_id, data)
            r_admin = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "from": from_email,
                    "to": [admin_email],
                    "subject": f"[merch7am] Estimate #{estimate_id} - {data.get('client_name', 'Unknown')}",
                    "text": admin_body,
                },
                timeout=10,
            )
            if r_admin.status_code >= 400:
                return False, f"Admin email failed: {r_admin.text}"

        # Send to client (always)
        r_client = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "from": from_email,
                "to": [client_email],
                "subject": f"Your estimate #{estimate_id} - merch7am",
                "text": client_body,
            },
            timeout=10,
        )
        if r_client.status_code >= 400:
            return False, f"Client email failed: {r_client.text}"

        return True, "Emails sent"
    except Exception as e:
        return False, str(e)
