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

from routes.estimate import router as estimate_router
from routes.reports import router as reports_router
from routes.chat import router as chat_router

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

app.include_router(estimate_router)
app.include_router(reports_router)
app.include_router(chat_router)


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "merch7am-price-estimator",
        "openai_configured": bool(os.environ.get("OPENAI_API_KEY")),
        "chat_enabled": bool(os.environ.get("OPENAI_API_KEY")),
    }
