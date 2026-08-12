"""
Radiopharma OS - Surrogate Modeling Server (EDS Vol. II, cap. 20)
Punto de entrada FastAPI.

Modelos sustitutos entrenados con resultados de alta fidelidad
(20.6): nunca reemplazan al modelo físico de referencia (20.3) —
siempre coexisten la simulación completa y la inferencia rápida.

Nota de plataforma (20.10): BentoML es la plataforma oficial de
despliegue declarada por la especificación. Este servidor
implementa la interfaz uniforme de inferencia, registro y
validación de forma nativa; el adaptador BentoML se incorporará
cuando el runtime esté disponible en el entorno (honestidad de
plataforma: /health reporta su disponibilidad real).
"""
from __future__ import annotations

import importlib.util
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.application.surrogate_service import SurrogateService
from app.presentation.routers import (agents_api, graph_api, mlops_api, ei_api,
                                  rag_api, serving_api,
                                  surrogate_api)

app = FastAPI(
    title="Radiopharma OS - Surrogate Modeling Server",
    version="0.1.0",
    description=(
        "Surrogate Modeling Server (cap. 20): datasets versionados, "
        "puerta de validación previa al despliegue, Model Registry "
        "permanente, Inference API auditada y Drift Monitor."),
)

surrogate_api.init(SurrogateService())
agents_api.init()
graph_api.init()
rag_api.init()
mlops_api.init()
ei_api.init()
serving_api.init()
_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(surrogate_api.router)
app.include_router(agents_api.router)
app.include_router(graph_api.router)
app.include_router(rag_api.router)
app.include_router(mlops_api.router)
app.include_router(ei_api.router)
app.include_router(serving_api.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {
        "service": "surrogate-server",
        "status": "ok",
        "version": "0.1.0",
        "bentoml_disponible": importlib.util.find_spec("bentoml") is not None,
        "nota_bentoml": "BentoML es la plataforma oficial (20.10); el "
                        "servidor opera con runtime nativo hasta que el "
                        "adaptador esté disponible (honestidad de plataforma).",
    }
