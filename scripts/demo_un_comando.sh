#!/usr/bin/env bash
# Radiopharma OS — demo de un solo comando (despliegue endurecido, Fase 6).
#
# Uso:  ./scripts/demo_un_comando.sh
#
# Comportamiento:
#   1. Si hay Docker: levanta la plataforma completa con docker compose
#      (8 microservicios + postgres + redis + mosquitto + minio + console/nginx).
#   2. Si NO hay Docker (p. ej. sandbox/CI): modo local — arranca los 8
#      microservicios con uvicorn sobre el código fuente.
#   En ambos casos espera a los healthchecks reales y ejecuta
#   scripts/verificar_despliegue.py como puerta de salud honesta.
#   Nunca simula: si un servicio no levanta, el verificador lo reporta
#   con su marcador honesto y el script sale con código != 0.
set -u
cd "$(dirname "$0")/.."
RAIZ="$(pwd)"
PUERTOS=(8001 8002 8003 8004 8005 8006 8007 8008)
SERVICIOS=(nuclear_data_service yield_engine data_lake_service auth_service qc_engine telemetry_service process_service surrogate_service)

esperar_salud() {  # url, intentos
  local url="$1" n="${2:-60}"
  for _ in $(seq 1 "$n"); do
    if curl -sf "$url" -o /dev/null 2>&1; then return 0; fi
    sleep 2
  done
  return 1
}

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  echo "== MODO DOCKER =="
  docker compose up -d --build
  for p in "${PUERTOS[@]}"; do
    esperar_salud "http://localhost:${p}/health" 90 || echo "AVISO: :${p} sin health tras espera (se reportará honestamente)"
  done
else
  echo "== MODO LOCAL (sin Docker) =="
  mkdir -p out/demo_logs
  PIDS=()
  for i in "${!SERVICIOS[@]}"; do
    s="${SERVICIOS[$i]}"; p="${PUERTOS[$i]}"
    (cd "services/$s" && PYTHONPATH=. nohup python3 -m uvicorn app.main:app --port "$p" \
      > "$RAIZ/out/demo_logs/$s.log" 2>&1) &
    PIDS+=($!)
  done
  echo "${PIDS[@]}" > out/demo_logs/pids.txt
  echo "servicios lanzados (pids en out/demo_logs/pids.txt; parar con: kill \$(cat out/demo_logs/pids.txt))"
  for p in "${PUERTOS[@]}"; do
    esperar_salud "http://localhost:${p}/health" 45 || echo "AVISO: :${p} sin health tras espera"
  done
fi

echo "== PUERTA DE SALUD HONESTA =="
python3 scripts/verificar_despliegue.py localhost
rc=$?
echo "verificar_despliegue.py -> exit $rc"
exit $rc
