"""
merch7am Price Estimator API

Run: uvicorn main:app --reload (development)
     uvicorn main:app (production)
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from routes.auth import router as auth_router
from routes.estimate import router as estimate_router
from routes.reports import router as reports_router
from routes.chat import router as chat_router
from routes.performance_digest import router as digest_router
from routes.seo_brief import router as seo_brief_router
from routes.ad_copy import router as ad_copy_router
from routes.clients import router as clients_router
from routes.agent_runs import router as agent_runs_router
from routes.knowledge import router as knowledge_router
from routes.pricing import router as pricing_router
from routes.estimates import router as estimates_router

load_dotenv()

# ── Default pricing rules seed ────────────────────────────────────────────────
# Written to disk on first startup if no rules file exists yet.
# Edit via the dashboard Pricing page — changes are persisted in the JSON file.
_DEFAULT_PRICING_RULES = {
  "mode": "additive",
  "currency": "ARS",
  "quantity_tiers": [50, 100, 200, 500],
  "personalization_prices": [
    {"id":"row_4","product":"remera","technique":"serigrafia","variant":"standard","placement":"1 logo","colors":"1","qty_50":960,"qty_100":850,"qty_200":750,"qty_500":700},
    {"id":"row_5","product":"remera","technique":"serigrafia","variant":"standard","placement":"1 logo","colors":"2","qty_50":1400,"qty_100":1360,"qty_200":1200,"qty_500":1100},
    {"id":"row_6","product":"remera","technique":"serigrafia","variant":"standard","placement":"1 logo","colors":"3+","qty_50":2200,"qty_100":1890,"qty_200":1600,"qty_500":1450},
    {"id":"row_7","product":"remera","technique":"serigrafia","variant":"standard","placement":"2 logos frente+espalda","colors":"3+","qty_50":3200,"qty_100":2800,"qty_200":2600,"qty_500":2400},
    {"id":"row_8","product":"remera","technique":"serigrafia","variant":"standard","placement":"diseño 30x40","colors":"3+","qty_50":3500,"qty_100":3000,"qty_200":2700,"qty_500":2500},
    {"id":"row_9","product":"remera","technique":"dtf","variant":"standard","placement":"1 logo","colors":"1","qty_50":1200,"qty_100":1100,"qty_200":900,"qty_500":800},
    {"id":"row_10","product":"remera","technique":"dtf","variant":"standard","placement":"1 logo","colors":"2","qty_50":1200,"qty_100":1100,"qty_200":900,"qty_500":800},
    {"id":"row_11","product":"remera","technique":"dtf","variant":"standard","placement":"1 logo","colors":"full","qty_50":1200,"qty_100":1100,"qty_200":900,"qty_500":800},
    {"id":"row_12","product":"remera","technique":"dtf","variant":"standard","placement":"2 logos frente+espalda","colors":"full","qty_50":2200,"qty_100":1900,"qty_200":1700,"qty_500":1500},
    {"id":"row_13","product":"remera","technique":"dtf","variant":"standard","placement":"diseño 30x40","colors":"full","qty_50":2000,"qty_100":1600,"qty_200":1400,"qty_500":1300},
    {"id":"row_14","product":"remera","technique":"serigrafia","variant":"negra","placement":"1 logo","colors":"1","qty_50":1300,"qty_100":980,"qty_200":900,"qty_500":840},
    {"id":"row_15","product":"remera","technique":"serigrafia","variant":"negra","placement":"1 logo","colors":"2","qty_50":2200,"qty_100":1600,"qty_200":1440,"qty_500":1300},
    {"id":"row_16","product":"remera","technique":"serigrafia","variant":"negra","placement":"1 logo","colors":"3+","qty_50":2900,"qty_100":None,"qty_200":1900,"qty_500":1750},
    {"id":"row_17","product":"remera","technique":"serigrafia","variant":"negra","placement":"2 logos frente+espalda","colors":"3+","qty_50":3900,"qty_100":3150,"qty_200":2900,"qty_500":2650},
    {"id":"row_18","product":"remera","technique":"serigrafia","variant":"negra","placement":"diseño 30x40","colors":"3+","qty_50":3900,"qty_100":3100,"qty_200":2900,"qty_500":2600},
    {"id":"row_19","product":"remera","technique":"dtf","variant":"negra","placement":"1 logo","colors":"1","qty_50":1200,"qty_100":1100,"qty_200":900,"qty_500":800},
    {"id":"row_20","product":"remera","technique":"dtf","variant":"negra","placement":"1 logo","colors":"2","qty_50":1200,"qty_100":1100,"qty_200":900,"qty_500":800},
    {"id":"row_21","product":"remera","technique":"dtf","variant":"negra","placement":"1 logo","colors":"full","qty_50":1200,"qty_100":1100,"qty_200":900,"qty_500":800},
    {"id":"row_22","product":"remera","technique":"dtf","variant":"negra","placement":"2 logos frente+espalda","colors":"full","qty_50":2400,"qty_100":1900,"qty_200":1700,"qty_500":1500},
    {"id":"row_23","product":"remera","technique":"dtf","variant":"negra","placement":"diseño 25x35","colors":"full","qty_50":2000,"qty_100":1800,"qty_200":1600,"qty_500":1400},
    {"id":"row_24","product":"gorra","technique":"bordado","variant":"standard","placement":"1 logo","colors":"full","qty_50":1573,"qty_100":1452,"qty_200":None,"qty_500":None},
    {"id":"row_25","product":"gorra","technique":"bordado","variant":"standard","placement":"2 logos","colors":"full","qty_50":2299,"qty_100":2178,"qty_200":None,"qty_500":None},
    {"id":"row_26","product":"gorra","technique":"serigrafia","variant":"standard","placement":"1 logo","colors":"1","qty_50":1100,"qty_100":980,"qty_200":900,"qty_500":800},
    {"id":"row_27","product":"gorra","technique":"dtf","variant":"standard","placement":"1 logo","colors":"1","qty_50":1100,"qty_100":980,"qty_200":800,"qty_500":750},
    {"id":"row_28","product":"piluso","technique":"serigrafia","variant":"standard","placement":"1 logo","colors":"1","qty_50":1360,"qty_100":980,"qty_200":900,"qty_500":800},
    {"id":"row_29","product":"piluso","technique":"dtf","variant":"standard","placement":"1 logo","colors":"1","qty_50":1000,"qty_100":900,"qty_200":800,"qty_500":750},
    {"id":"row_30","product":"piluso","technique":"bordado","variant":"standard","placement":"1 logo","colors":"full","qty_50":1000,"qty_100":900,"qty_200":None,"qty_500":None},
    {"id":"row_31","product":"totebag","technique":"serigrafia","variant":"standard","placement":"1 logo","colors":"1","qty_50":960,"qty_100":850,"qty_200":750,"qty_500":700},
    {"id":"row_32","product":"totebag","technique":"serigrafia","variant":"standard","placement":"1 logo","colors":"2","qty_50":1400,"qty_100":1360,"qty_200":1200,"qty_500":1100},
    {"id":"row_33","product":"totebag","technique":"serigrafia","variant":"standard","placement":"1 logo","colors":"3+","qty_50":3600,"qty_100":3200,"qty_200":2900,"qty_500":2800},
    {"id":"row_34","product":"totebag","technique":"serigrafia","variant":"standard","placement":"diseño 25x35","colors":"3+","qty_50":2800,"qty_100":2800,"qty_200":2500,"qty_500":2300},
    {"id":"row_35","product":"totebag","technique":"serigrafia","variant":"standard","placement":"diseño 30x40","colors":"3+","qty_50":3100,"qty_100":3500,"qty_200":3500,"qty_500":3200},
    {"id":"row_36","product":"totebag","technique":"dtf","variant":"standard","placement":"1 logo","colors":"1","qty_50":1200,"qty_100":1100,"qty_200":900,"qty_500":800},
    {"id":"row_37","product":"totebag","technique":"dtf","variant":"standard","placement":"1 logo","colors":"2","qty_50":1200,"qty_100":1100,"qty_200":900,"qty_500":800},
    {"id":"row_38","product":"totebag","technique":"dtf","variant":"standard","placement":"1 logo","colors":"full","qty_50":1200,"qty_100":1100,"qty_200":900,"qty_500":800},
    {"id":"row_39","product":"totebag","technique":"dtf","variant":"standard","placement":"2 logos frente+espalda","colors":"full","qty_50":1500,"qty_100":1900,"qty_200":1700,"qty_500":1500},
    {"id":"row_40","product":"botella","technique":"serigrafia","variant":"standard","placement":"1 logo","colors":"1","qty_50":1000,"qty_100":850,"qty_200":750,"qty_500":700},
    {"id":"row_41","product":"botella","technique":"serigrafia","variant":"standard","placement":"1 logo","colors":"2","qty_50":1400,"qty_100":1200,"qty_200":None,"qty_500":None},
    {"id":"row_42","product":"botella","technique":"serigrafia","variant":"standard","placement":"2 logos","colors":"1","qty_50":1600,"qty_100":1400,"qty_200":1300,"qty_500":1200},
    {"id":"row_43","product":"botella","technique":"serigrafia","variant":"standard","placement":"2 logos","colors":"2","qty_50":2000,"qty_100":1800,"qty_200":1200,"qty_500":1050},
    {"id":"row_44","product":"botella","technique":"serigrafia","variant":"standard","placement":"360°","colors":"full","qty_50":3600,"qty_100":3000,"qty_200":2800,"qty_500":2600},
    {"id":"row_45","product":"botella","technique":"serigrafia","variant":"plástico","placement":"1 logo","colors":"1","qty_50":1000,"qty_100":850,"qty_200":750,"qty_500":700},
    {"id":"row_46","product":"botella","technique":"serigrafia","variant":"plástico","placement":"2 logos","colors":"1","qty_50":1500,"qty_100":1400,"qty_200":1300,"qty_500":1200},
    {"id":"row_47","product":"botella","technique":"serigrafia","variant":"metal/vidrio","placement":"1 logo","colors":"1","qty_50":1500,"qty_100":1100,"qty_200":1050,"qty_500":1000},
    {"id":"row_48","product":"botella","technique":"serigrafia","variant":"metal/vidrio","placement":"2 logos","colors":"1","qty_50":1800,"qty_100":1700,"qty_200":1500,"qty_500":1400},
    {"id":"row_49","product":"botella","technique":"grabado","variant":"standard","placement":"1 logo","colors":"full","qty_50":1200,"qty_100":1100,"qty_200":1000,"qty_500":900},
    {"id":"row_50","product":"bolígrafo","technique":"tampo","variant":"standard","placement":"1 logo","colors":"1","qty_50":1000,"qty_100":750,"qty_200":110,"qty_500":100},
    {"id":"row_51","product":"llavero","technique":"grabado laser","variant":"standard","placement":"1 logo","colors":"full","qty_50":1000,"qty_100":950,"qty_200":None,"qty_500":None},
  ]
}


def _seed_pricing_rules() -> None:
    """Write default pricing rules for every known client if the file is missing."""
    from lib.pricing_rules import save_rules, load_rules
    for client_id in ("default", "merch7am"):
        rules = load_rules(client_id)
        if not rules.get("personalization_prices"):
            print(f"[startup] Seeding pricing rules for client_id={client_id!r}")
            save_rules(_DEFAULT_PRICING_RULES, client_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _seed_pricing_rules()
    yield
    # Cleanup if needed


app = FastAPI(
    title="merch7am Price Estimator",
    description="AI-powered price estimation for custom merchandise",
    lifespan=lifespan,
)

# CORS: storefront JS calls this API from https://merch7am.com.
# Shopify's shop_events_listener may wrap fetch with credentials; browsers then REJECT
# Access-Control-Allow-Origin: * (requires a concrete origin + Allow-Credentials).
# So we never use allow_origins=["*"] here — always explicit domains + myshopify regex.
_STORE_ORIGINS = (
    "https://merch7am.com",
    "https://www.merch7am.com",
    "https://merch7am.myshopify.com",
)
_DEV_ORIGINS = (
    "http://127.0.0.1:9292",
    "http://localhost:9292",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
)
_ORIGIN_REGEX = (
    r"^https://[a-zA-Z0-9-]+\.myshopify\.com$"
    r"|^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
    r"|^https://(www\.)?merch7am\.com$"
)


def _cors_allowed_origins() -> list[str]:
    seen = set()
    out = []
    for o in (*_STORE_ORIGINS, *_DEV_ORIGINS):
        if o not in seen:
            seen.add(o)
            out.append(o)
    raw = (os.environ.get("CORS_ORIGIN") or "").strip()
    if raw and raw != "*":
        for part in raw.split(","):
            p = part.strip().rstrip("/")
            if p and p not in seen:
                seen.add(p)
                out.append(p)
    return out


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allowed_origins(),
    allow_origin_regex=_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(estimate_router)
app.include_router(reports_router)
app.include_router(chat_router)

# Agents
app.include_router(digest_router)
app.include_router(seo_brief_router)
app.include_router(ad_copy_router)

# Multi-client & run history
app.include_router(clients_router)
app.include_router(agent_runs_router)
app.include_router(knowledge_router)
app.include_router(pricing_router)
app.include_router(estimates_router)


@app.get("/")
def root():
    """Avoid 404 noise when opening http://localhost:3001/ in a browser."""
    return {
        "service": "merch7am-price-estimator",
        "openapi": "/docs",
        "health": "/api/health",
        "estimate": "POST /api/estimate-price",
    }


@app.get("/favicon.ico")
def favicon_noop():
    return Response(status_code=204)


@app.get("/api/health")
def health():
    from lib.pricing_rules import load_rules
    from pathlib import Path
    rules_default = load_rules("default")
    rules_merch   = load_rules("merch7am")
    return {
        "ok": True,
        "service": "merch7am-price-estimator",
        "version": "2026-04-11-additive",
        "openai_configured": bool(os.environ.get("OPENAI_API_KEY")),
        "shopify_configured": bool(os.environ.get("SHOPIFY_STOREFRONT_TOKEN")),
        "pricing_debug": {
            "default_rows":   len(rules_default.get("personalization_prices", [])),
            "merch7am_rows":  len(rules_merch.get("personalization_prices", [])),
            "default_mode":   rules_default.get("mode"),
            "default_file_exists": Path("data/pricing_rules/default.json").exists(),
            "merch7am_file_exists": Path("data/pricing_rules/merch7am.json").exists(),
        },
    }
