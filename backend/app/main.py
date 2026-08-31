import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.config import settings
from app.auth import verify_login
from app.routers import webhooks, analytics, events, health, checkout

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="Recovery Router API",
    description="Intelligent revenue recovery engine — Razorpay AI Buildathon Track 3",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:5173",
        "http://localhost:3000",
        "https://albertabishek.com",
        "https://app.albertabishek.com",
        "https://api.albertabishek.com",
        "https://razorpay.albertabishek.com",
    ],
    allow_origin_regex=r"https://recovery-router[a-z0-9-]*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(webhooks.router)
app.include_router(analytics.router)
app.include_router(events.router)
app.include_router(health.router)
app.include_router(checkout.router)

logger = logging.getLogger(__name__)


@app.on_event("startup")
async def _startup_checks():
    try:
        from app.redis_client import get_redis
        get_redis().ping()
        logger.info("Redis connection verified")
    except Exception as exc:
        logger.error("Redis connection failed on startup: %s", exc)


@app.get("/")
async def root():
    return {
        "name": "Recovery Router API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }


class LoginRequest(BaseModel):
    password: str


@app.post("/api/login")
async def login(req: LoginRequest):
    if verify_login(req.password):
        return {"status": "ok", "token": settings.APP_PASSWORD}
    return JSONResponse(status_code=401, content={"status": "error", "detail": "Invalid password"})
