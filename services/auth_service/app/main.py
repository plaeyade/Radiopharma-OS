"""
Radiopharma OS - Auth Service (Fase 1: seguridad)
Punto de entrada FastAPI.

Emisión y verificación de tokens JWT de plataforma, gestión de usuarios
y roles (admin > calidad > supervisor > operador).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.application.auth_service import AuthService
from app.presentation.routers import zerotrust_api, iam_api, gateway_api
from app.config import load_settings
from app.infrastructure.db.sql_refresh_token_store import SqlRefreshTokenStore
from app.infrastructure.db.sql_user_repository import SqlUserRepository
from app.infrastructure.security.jwt_issuer import JwtIssuer
from app.infrastructure.security.pbkdf2_hasher import Pbkdf2Hasher
from app.presentation.routers import auth

settings = load_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    repo = SqlUserRepository(settings.database_url)
    await repo.create_schema()
    refresh_store = SqlRefreshTokenStore(settings.database_url)
    await refresh_store.create_schema()
    service = AuthService(repo, Pbkdf2Hasher(), JwtIssuer(settings.jwt_secret),
                          token_ttl_min=settings.token_ttl_min,
                          refresh_store=refresh_store,
                          refresh_ttl_min=settings.refresh_ttl_min)
    await service.ensure_seed_admin(settings.seed_admin_user,
                                    settings.seed_admin_password)
    auth.init(service)
    yield
    await repo.dispose()
    await refresh_store.dispose()


app = FastAPI(
    title="Radiopharma OS - Auth Service",
    version="0.1.0",
    description="Autenticación JWT y roles de plataforma (ALCOA+ atribuible).",
    lifespan=lifespan,
)
# CORS: la consola web (origen distinto) consume estas APIs desde el navegador
_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
zerotrust_api.init()
iam_api.init()
gateway_api.init()
app.include_router(zerotrust_api.router)
app.include_router(iam_api.router)
app.include_router(gateway_api.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"service": "auth-service", "status": "ok", "version": "0.1.0"}
