# syntax=docker/dockerfile:1
# Radiopharma OS — imagen de la plataforma: sirve el Yield Engine (FastAPI) con uvicorn.
#
#   docker build -t radiopharma-os:dev \
#     --build-arg BUILD_COMMIT=$(git rev-parse --short HEAD) \
#     --build-arg BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ) .
#   docker run --rm -p 8002:8002 radiopharma-os:dev      # http://localhost:8002/docs
#
# La etapa `pruebas` corre la suite del Yield Engine: si falla, la imagen no se construye.
# El resto de servicios (nuclear-data, process, qc…) se levantan con docker-compose.yml.

ARG PYTHON_IMAGE=python:3.12-slim

# ── Dependencias ──────────────────────────────────────────────────────────────────────────────
FROM ${PYTHON_IMAGE} AS deps
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /srv
COPY services/yield_engine/requirements.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -r requirements.txt

# ── Pruebas (OQ parcial en tiempo de build) ──────────────────────────────────────────────────
FROM deps AS pruebas
ENV PATH=/opt/venv/bin:$PATH PYTHONPATH=/srv PYTHONDONTWRITEBYTECODE=1
RUN pip install pytest==8.*
COPY services/yield_engine/ /srv/
RUN python -m pytest tests -q -p no:cacheprovider && touch /srv/.pruebas-ok

# ── Ejecución ────────────────────────────────────────────────────────────────────────────────
FROM ${PYTHON_IMAGE} AS runtime
ARG BUILD_VERSION=0.3.0
ARG BUILD_COMMIT=unknown
ARG BUILD_DATE=unknown
LABEL org.opencontainers.image.title="radiopharma-os" \
      org.opencontainers.image.description="Radiopharma OS — Yield Engine (rendimiento de radionúclidos, Physics Twin)" \
      org.opencontainers.image.version="${BUILD_VERSION}" \
      org.opencontainers.image.revision="${BUILD_COMMIT}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/plaeyade/radiopharma-os"

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/srv \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8002 \
    WORKERS=2

RUN useradd --system --uid 10001 --home /srv rpos
WORKDIR /srv
COPY --from=deps /opt/venv /opt/venv
COPY --chown=rpos services/yield_engine/app ./app
COPY --chown=rpos services/yield_engine/data ./data
# Obliga a que la etapa de pruebas se haya ejecutado con éxito.
COPY --from=pruebas /srv/.pruebas-ok /srv/.pruebas-ok

USER rpos
EXPOSE 8002
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8002\")}/health',timeout=4)"
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers ${WORKERS} --proxy-headers"]
