# Radiopharma OS — imagen de la plataforma (F50, ítem diferido: Docker)
# NOTA HONESTA: Dockerfile declarado y revisado, pendiente de build real en
# un entorno con daemon Docker (el sandbox no lo tiene — no se fabrica la
# imagen aquí).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY services/ ./services/
COPY pipelines/ ./pipelines/
COPY Makefile pytest.ini ./
RUN pip install --no-cache-dir pytest numpy scipy fastapi uvicorn pydantic

# Suite canónica al construir (OQ parcial en build-time)
RUN cd services/yield_engine && PYTHONPATH=. python -m pytest tests -q

EXPOSE 8000
CMD ["python", "-m", "pytest", "--version"]
