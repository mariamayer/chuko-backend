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


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Cleanup if needed


app = FastAPI(
    title="merch7am Price Estimator",
    description="AI-powered price estimation for custom merchandise",
    lifespan=lifespan,
)

# CORS: permissive for dev, configurable for prod
_cors = os.environ.get("CORS_ORIGIN", "*").strip()
if _cors == "*":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    origins = [o.strip() for o in _cors.split(",") if o.strip()]
    # Regex: Shopify, localhost, merch7am.com
    _regex = (
        r"^https://[a-zA-Z0-9-]+\.myshopify\.com$"
        r"|^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
        r"|^https://(www\.)?merch7am\.com$"
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=_regex,
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


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "merch7am-price-estimator",
        "openai_configured": bool(os.environ.get("OPENAI_API_KEY")),
        "chat_enabled": bool(os.environ.get("OPENAI_API_KEY")),
        "agents_enabled": bool(os.environ.get("OPENAI_API_KEY")),
        "shopify_configured": bool(os.environ.get("SHOPIFY_STOREFRONT_TOKEN")),
    }
