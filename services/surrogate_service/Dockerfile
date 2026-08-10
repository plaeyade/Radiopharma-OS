FROM python:3.12-slim
# 10.17: cada imagen registra versión, commit, fecha e identificador.
# Se inyectan en build:  docker build --build-arg BUILD_COMMIT=$(git rev-parse --short HEAD)
ARG BUILD_VERSION=dev
ARG BUILD_COMMIT=unknown
ARG BUILD_DATE=unknown
LABEL org.opencontainers.image.title="radiopharma-os/surrogate_service" \
      org.opencontainers.image.version="${BUILD_VERSION}" \
      org.opencontainers.image.revision="${BUILD_COMMIT}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://radiopharma.local/repo" \
      org.opencontainers.image.description="Radiopharma OS MVP — surrogate_service (EDS 10.17)"

WORKDIR /srv
RUN pip install --no-cache-dir fastapi uvicorn pydantic numpy
COPY app ./app
EXPOSE 8008
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8008"]
