FROM python:3.12-slim
# 10.17: cada imagen registra versión, commit, fecha e identificador.
# Se inyectan en build:  docker build --build-arg BUILD_COMMIT=$(git rev-parse --short HEAD)
ARG BUILD_VERSION=dev
ARG BUILD_COMMIT=unknown
ARG BUILD_DATE=unknown
LABEL org.opencontainers.image.title="radiopharma-os/process_service" \
      org.opencontainers.image.version="${BUILD_VERSION}" \
      org.opencontainers.image.revision="${BUILD_COMMIT}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://radiopharma.local/repo" \
      org.opencontainers.image.description="Radiopharma OS MVP — process_service (EDS 10.17)"


WORKDIR /srv
ENV PYTHONPATH=/srv \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data

EXPOSE 8007
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8007"]
