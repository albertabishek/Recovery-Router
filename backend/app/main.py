import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
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
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(webhooks.router)
app.include_router(analytics.router)
app.include_router(events.router)
app.include_router(health.router)
app.include_router(checkout.router)


@app.get("/")
async def root():
    return {
        "name": "Recovery Router API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }
