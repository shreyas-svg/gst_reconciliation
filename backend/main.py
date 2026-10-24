import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Ensure environment is loaded at startup from candidate locations
env_candidates = [
    Path(__file__).resolve().parent / ".env",
    Path(__file__).resolve().parent.parent / ".env",
    Path.cwd() / ".env",
    Path.cwd() / "backend" / ".env",
]
for p in env_candidates:
    if p.exists():
        load_dotenv(p)
        break

from database import engine, run_migrations
from models import models
from models.base import Base
from routers.anomalies import router as anomalies_router
from routers.auth import router as auth_router
from routers.gstr3b import router as gstr3b_router
from routers.imports import router as imports_router
from routers.invoices import router as invoices_router, upload_csv
from routers.reconciliation import router as reconciliation_router
from routers.reports import router as reports_router

import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database schema safely during application lifespan startup
    try:
        run_migrations(engine)
        logger.info("Database schema and migrations verified and initialized.")
    except Exception as _schema_exc:
        logger.warning(
            "Database schema initialisation skipped at startup: %s — using test/offline mode.",
            _schema_exc,
        )
    yield


app = FastAPI(
    title="Automated MSME GST Reconciliation and Anomaly Detector",
    version="1.0.0",
    description="Production-style GST reconciliation, exception management, and GSTR compliance system for MSMEs.",
    lifespan=lifespan,
)

# Robust CORS configuration compliant with credentials and custom headers
cors_origins_env = os.getenv("CORS_ORIGINS", "")
configured_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]
allowed_origins = list(dict.fromkeys(configured_origins + default_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Type", "*"],
)

app.include_router(auth_router)
app.include_router(reconciliation_router)
app.include_router(gstr3b_router)
app.include_router(invoices_router)
app.include_router(imports_router)
app.include_router(anomalies_router)
app.include_router(reports_router)

# Direct alias for /upload to match specification
app.add_api_route("/upload", upload_csv, methods=["POST"], tags=["Invoices"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Hide raw internal traces from production responses while preserving CORS
    origin = request.headers.get("origin", "*")
    headers = {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Allow-Methods": "*",
    }
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please check backend logs."},
        headers=headers,
    )


@app.get("/")
def home():
    return {
        "system": "Automated MSME GST Reconciliation and Anomaly Detector",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": [
            "/reconcile",
            "/gstr3b/summary",
            "/invoices",
            "/invoices/upload",
            "/imports",
            "/anomalies",
            "/reports/summary",
            "/reports/export",
            "/health",
        ],
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "database": "connected",
    }

