"""
Email sending - admin and client notifications for estimates.
Uses AWS SES via boto3 (no API key needed — uses the AppRunner IAM role).
Falls back gracefully if SES is not configured.
"""

import os
from typing import Any


ADMIN_EMAIL  = os.environ.get("ADMIN_EMAIL", "")
FROM_EMAIL   = os.environ.get("RESEND_FROM_EMAIL", "")   # reuse same env var
AWS_REGION   = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")


def _ses():
    import boto3
    return boto3.client("ses", region_name=AWS_REGION)


def _format_currency(amount: float, currency: str = "USD") -> str:
    return f"{currency} {amount:,.2f}"


def _build_admin_body(estimate_id: str, data: dict) -> str:
    breakdown = data.get("breakdown", {})
    meta      = data.get("meta", {})
    analysis  = data.get("analysis", {})
    lines = [
        f"Estimate #{estimate_id}",
        "",
        "--- Summary ---",
        f"Total: {_format_currency(data.get('estimate', 0), data.get('currency', 'USD'))}",
        f"Quantity: {breakdown.get('quantity', '-')}",
        f"Product: {breakdown.get('product_type') or breakdown.get('matched_row', {}).get('product') or '-'}",
        f"Technique: {breakdown.get('technique') or '-'}",
        f"Product ID: {meta.get('product_id', '-')}",
        f"Variant ID: {meta.get('variant_id', '-')}",
        "",
        "--- Client ---",
        f"Name: {data.get('client_name', '-')}",
        f"Email: {data.get('client_email', '-')}",
        f"Company: {data.get('client_company', '-')}",
        "",
    ]
    if analysis:
        lines.append("--- Design analysis ---")
        for k, v in analysis.items():
            if isinstance(v, dict):
                lines.append(f"  {k}: {v.get('logo_size', '-')} / {v.get('color_count', '-')} colors")
    return "\n".join(lines)


def _build_client_body(estimate_id: str, data: dict) -> str:
    breakdown = data.get("breakdown", {})
    lines = [
        f"Tu presupuesto #{estimate_id}",
        "",
        f"Total: {_format_currency(data.get('estimate', 0), data.get('currency', 'USD'))}",
        f"Cantidad: {breakdown.get('quantity', '-')} unidades",
        "",
        "Guardá este número de referencia. Podés contestar a este email para cualquier consulta.",
    ]
    return "\n".join(lines)


def _send_ses(*, to: str, subject: str, body: str) -> tuple[bool, str]:
    if not FROM_EMAIL:
        return False, "FROM_EMAIL not configured (set RESEND_FROM_EMAIL env var)"
    try:
        _ses().send_email(
            Source=FROM_EMAIL,
            Destination={"ToAddresses": [to]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body":    {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
        return True, "sent"
    except Exception as e:
        return False, str(e)


def send_estimate_emails(estimate_id: str, data: dict) -> tuple[bool, str]:
    if not ADMIN_EMAIL:
        return False, "ADMIN_EMAIL not configured"

    client_email = data.get("client_email")
    if not client_email:
        return False, "No client email"

    quantity = (data.get("breakdown") or {}).get("quantity", 0) or 0

    # Notify admin only for larger orders
    if quantity >= 100:
        ok, msg = _send_ses(
            to=ADMIN_EMAIL,
            subject=f"[merch7am] Estimate #{estimate_id} — {data.get('client_name', 'Unknown')}",
            body=_build_admin_body(estimate_id, data),
        )
        if not ok:
            return False, f"Admin email failed: {msg}"

    # Always notify client
    ok, msg = _send_ses(
        to=client_email,
        subject=f"Tu presupuesto #{estimate_id} — merch7am",
        body=_build_client_body(estimate_id, data),
    )
    if not ok:
        return False, f"Client email failed: {msg}"

    return True, "Emails sent"


def _corp_brief_text_body(data: dict) -> str:
    lines = [
        "Brief corporativo — formulario web",
        "",
        "--- Contacto ---",
        f"Nombre: {data.get('nombre', '-')}",
        f"Apellido: {data.get('apellido', '-')}",
        f"Empresa: {data.get('empresa', '-')}",
        f"Puesto: {data.get('puesto', '-')}",
        f"Mail: {data.get('email', '-')}",
        f"WhatsApp / tel: {data.get('tel') or '—'}",
        f"Preferencia de contacto: {data.get('preferencia_contacto') or '—'}",
        "",
        "--- Proyecto ---",
        f"Tipo: {data.get('tipo') or '—'}",
        f"Logo / diseño: {data.get('logo') or '—'}",
    ]
    if data.get("como"):
        lines.extend(["", f"Cómo nos conocieron: {data['como']}"])
    if data.get("cantidad"):
        lines.append(f"Cantidad tentativa: {data['cantidad']}")
    if data.get("fecha"):
        lines.append(f"Fecha esperada entrega / evento: {data['fecha']}")
    ctx = (data.get("contexto") or "").strip()
    lines.extend(["", "--- Detalle ---", ctx or "(sin texto adicional)", ""])
    return "\n".join(lines)


def send_corp_brief_email(data: dict) -> tuple[bool, str]:
    to_email = os.environ.get("BRIEF_TO_EMAIL") or ADMIN_EMAIL
    if not to_email:
        return False, "ADMIN_EMAIL not configured"

    empresa = data.get("empresa") or "—"
    nombre  = data.get("nombre") or ""

    return _send_ses(
        to=to_email,
        subject=f"[merch7am] Brief — {nombre} — {empresa}",
        body=_corp_brief_text_body(data),
    )
