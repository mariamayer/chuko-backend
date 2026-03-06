"""
Weekly Performance Digest Agent

Aggregates estimate request data, computes weekly metrics, and uses OpenAI to write
a plain-English digest with actionable recommendations. Sends via Resend.
"""

import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from openai import OpenAI

ESTIMATES_DIR = Path(os.environ.get("ESTIMATES_DIR", "data/estimates"))


def _load_estimates() -> list[dict]:
    """Load all estimate JSON files."""
    if not ESTIMATES_DIR.exists():
        return []
    estimates = []
    for path in sorted(ESTIMATES_DIR.glob("EST-*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                estimates.append(json.load(f))
        except Exception:
            continue
    return estimates


def _parse_date(estimate_id: str) -> datetime | None:
    """Parse date from estimate ID like EST-20260225-0001."""
    try:
        return datetime.strptime(estimate_id[4:12], "%Y%m%d")
    except Exception:
        return None


def _build_metrics(estimates: list[dict], weeks: int = 4) -> dict:
    """Group estimates by ISO week and compute metrics for the last N weeks."""
    cutoff = datetime.now() - timedelta(weeks=weeks)
    weekly: dict = defaultdict(lambda: {
        "count": 0,
        "total_value": 0.0,
        "quantities": [],
        "clients": set(),
        "companies": set(),
        "products": set(),
    })

    for est in estimates:
        date = _parse_date(est.get("estimate_id", ""))
        if not date or date < cutoff:
            continue
        week_key = date.strftime("%Y-W%V")
        w = weekly[week_key]
        w["count"] += 1
        w["total_value"] += est.get("estimate", 0)
        qty = est.get("breakdown", {}).get("quantity", 0)
        if qty:
            w["quantities"].append(qty)
        if est.get("client_name"):
            w["clients"].add(est["client_name"])
        if est.get("client_company"):
            w["companies"].add(est["client_company"])
        pid = est.get("meta", {}).get("product_id", "")
        if pid:
            w["products"].add(pid)

    result = {}
    for week_key, data in sorted(weekly.items()):
        avg_qty = round(sum(data["quantities"]) / len(data["quantities"])) if data["quantities"] else 0
        result[week_key] = {
            "count": data["count"],
            "total_value": round(data["total_value"], 2),
            "avg_value": round(data["total_value"] / data["count"], 2) if data["count"] else 0,
            "avg_quantity": avg_qty,
            "unique_clients": len(data["clients"]),
            "unique_companies": len(data["companies"]),
            "unique_products": len(data["products"]),
        }
    return result


def _ai_summary(metrics: dict, total: int, value: float, avg: float, trend: str) -> str:
    """Use OpenAI to write a plain-English digest summary."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return (
            f"Last {len(metrics)} weeks: {total} estimate requests, "
            f"€{value:.2f} pipeline value, avg €{avg:.2f} per request. Trend: {trend}."
        )
    client = OpenAI(api_key=api_key)
    prompt = f"""You are a business analyst for merch7am, a custom merchandise e-commerce company.

Here are the weekly estimate request metrics for the last {len(metrics)} weeks:
{json.dumps(metrics, indent=2)}

Overall stats:
- Total estimate requests: {total}
- Total pipeline value: €{value:.2f}
- Average estimate value: €{avg:.2f}
- Trend vs previous week: {trend}

Write a concise (3-5 sentence) plain-English weekly performance digest. Include:
1. Key highlight (what went well or stood out)
2. Any concern or risk worth watching
3. One concrete, actionable recommendation for next week

Write in a direct, professional tone. Paragraphs only — no bullet points or headers."""

    try:
        resp = client.chat.completions.create(
            model=os.environ.get("CHAT_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[performance_digest] AI summary error: {e}")
        return f"Last {len(metrics)} weeks: {total} estimates, €{value:.2f} total, avg €{avg:.2f}. Trend: {trend}."


def build_digest(weeks: int = 4, no_ai: bool = False) -> dict:
    """
    Build the full performance digest dict.
    Returns metrics, trend, and optionally an AI summary.
    Pass no_ai=True to skip the OpenAI call (useful for dashboard previews).
    """
    estimates = _load_estimates()
    metrics = _build_metrics(estimates, weeks=weeks)

    total = sum(w["count"] for w in metrics.values())
    value = sum(w["total_value"] for w in metrics.values())
    avg = round(value / total, 2) if total else 0.0

    weeks_list = sorted(metrics.keys())
    current = metrics.get(weeks_list[-1], {}) if weeks_list else {}
    previous = metrics.get(weeks_list[-2], {}) if len(weeks_list) >= 2 else {}

    trend = "stable"
    if current and previous:
        if current["total_value"] > previous["total_value"] * 1.1:
            trend = "up"
        elif current["total_value"] < previous["total_value"] * 0.9:
            trend = "down"

    summary = None if no_ai else _ai_summary(metrics, total, value, avg, trend)

    return {
        "period_weeks": weeks,
        "total_estimates": total,
        "total_value_eur": value,
        "avg_estimate_eur": avg,
        "trend": trend,
        "weekly_breakdown": metrics,
        "ai_summary": summary,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }


def send_digest() -> tuple[bool, str]:
    """Build digest and send it via Resend. Returns (success, message)."""
    api_key = os.environ.get("RESEND_API_KEY")
    to_email = (
        os.environ.get("DIGEST_EMAIL")
        or os.environ.get("REPORT_EMAIL")
        or os.environ.get("ADMIN_EMAIL")
    )
    from_email = os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev")

    if not api_key or not to_email:
        return False, "RESEND_API_KEY and DIGEST_EMAIL (or REPORT_EMAIL / ADMIN_EMAIL) required"

    try:
        digest = build_digest()
    except Exception as e:
        return False, f"Failed to build digest: {e}"

    trend_icon = {"up": "📈", "down": "📉", "stable": "➡️"}.get(digest["trend"], "➡️")

    rows = ""
    for week, w in sorted(digest["weekly_breakdown"].items()):
        rows += f"""
          <tr>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;">{week}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:center;">{w['count']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:right;">€{w['total_value']:.2f}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:right;">€{w['avg_value']:.2f}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #eee;text-align:center;">{w['unique_clients']}</td>
          </tr>"""

    html = f"""<html><body style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;color:#333;padding:20px;">
  <h2 style="color:#1a1a1a;margin-bottom:4px;">📊 Weekly Performance Digest</h2>
  <p style="color:#888;font-size:13px;margin-top:0;">Generated: {digest['generated_at']}</p>

  <div style="background:#f8f9fa;border-radius:8px;padding:16px;margin:20px 0;">
    <h3 style="margin:0 0 12px;color:#1a1a1a;font-size:15px;">Summary — Last {digest['period_weeks']} Weeks</h3>
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr><td style="padding:3px 0;"><strong>Estimate Requests:</strong></td><td style="text-align:right;">{digest['total_estimates']}</td></tr>
      <tr><td style="padding:3px 0;"><strong>Pipeline Value:</strong></td><td style="text-align:right;">€{digest['total_value_eur']:.2f}</td></tr>
      <tr><td style="padding:3px 0;"><strong>Avg per Estimate:</strong></td><td style="text-align:right;">€{digest['avg_estimate_eur']:.2f}</td></tr>
      <tr><td style="padding:3px 0;"><strong>Trend:</strong></td><td style="text-align:right;">{trend_icon} {digest['trend'].capitalize()}</td></tr>
    </table>
  </div>

  <div style="border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin:20px 0;">
    <h3 style="margin:0 0 10px;color:#1a1a1a;font-size:15px;">🤖 AI Analysis & Recommendation</h3>
    <p style="line-height:1.7;color:#444;margin:0;">{digest['ai_summary']}</p>
  </div>

  <h3 style="color:#1a1a1a;font-size:15px;">Weekly Breakdown</h3>
  <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;font-size:14px;">
    <thead>
      <tr style="background:#f3f4f6;">
        <th style="padding:10px 12px;text-align:left;">Week</th>
        <th style="padding:10px 12px;text-align:center;">Estimates</th>
        <th style="padding:10px 12px;text-align:right;">Total Value</th>
        <th style="padding:10px 12px;text-align:right;">Avg Value</th>
        <th style="padding:10px 12px;text-align:center;">Clients</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>

  <p style="color:#bbb;font-size:12px;margin-top:30px;">merch7am · Automated Weekly Performance Report</p>
</body></html>"""

    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "from": from_email,
                "to": [to_email],
                "subject": (
                    f"📊 Weekly Digest — {digest['total_estimates']} estimates"
                    f" · €{digest['total_value_eur']:.0f} pipeline {trend_icon}"
                ),
                "html": html,
            },
            timeout=15,
        )
        if r.status_code >= 400:
            return False, f"Email failed: {r.text}"
        return True, f"Digest sent to {to_email}"
    except Exception as e:
        return False, str(e)
