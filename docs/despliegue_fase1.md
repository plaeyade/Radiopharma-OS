# Fase 1 — Despliegue de infraestructura y activación de conectores

Guía operativa para levantar la infraestructura base y **activar de verdad**
cada conector externo. Regla de plataforma honesta: un conector solo deja de
reportar su marcador honesto (`no_configurado`, `fallo_conexion`,
`sin_runtime`) cuando el endpoint real está registrado **y** el sondeo real
responde. Nada se simula en ningún paso.

## 1. Arranque base

```bash
cp .env.example .env        # ajustar secretos
docker compose up -d        # 8 servicios + postgres + minio + influxdb + redis + consola
```

Perfiles opcionales:

```bash
docker compose --profile conectores up -d   # broker MQTT (mosquitto)
docker compose --profile mapa up -d         # OSRM propio (requiere mapa, ver §3)
docker compose --profile demo up -d         # banco OPC-UA simulado
docker compose run --rm verapdf /data/ebr.pdf   # gate PDF/A (perfil calidad)
```

## 2. Verificación post-despliegue

```bash
python3 scripts/verificar_despliegue.py
```

El script consulta los endpoints `/status` reales de cada servicio y lista:

- servicios caídos (fallo de conexión real),
- marcadores honestos que **siguen activos** (lo que falta por cablear),
- conectores ya registrados y su resultado de sondeo.

Un despliegue recién instalado **debe** mostrar marcadores pendientes: es el
estado honesto. La fase termina cuando el script no reporta ningún
`no_configurado` en los conectores que el centro haya decidido activar.

## 3. Activación por conector (marcador → pasos reales)

### 3.1 OSRM — routing terrestre del logistics twin (process-service :8007)

Marcador cuando falta: rutas con proveedor local Haversine; servidores OSRM
vacíos o `fallo_conexion`.

1. Mapa propio (recomendado para producción — el servidor público de demo no
   tiene SLA):

   ```bash
   # descargar el extracto OSM de la región (p. ej. España, ~1 GB)
   docker run --rm -v rpos_osrmdata:/data -w /data osrm/osrm-backend \
     sh -c "wget https://download.geofabrik.de/europe/spain-latest.osm.pbf"
   docker run --rm -v rpos_osrmdata:/data osrm/osrm-backend \
     osrm-extract -p /opt/car.lua /data/spain-latest.osm.pbf
   docker run --rm -v rpos_osrmdata:/data osrm/osrm-backend \
     osrm-contract /data/spain-latest.osrm
   docker run --rm -v rpos_osrmdata:/data osrm/osrm-backend \
     mv /data/spain-latest.osrm /data/mapa.osrm   # nombre esperado por el compose
   docker compose --profile mapa up -d osrm
   ```

2. Registrar y sondear (conexión HTTP real):

   ```bash
   curl -X POST localhost:8007/api/v1/osrm/servers -H 'Content-Type: application/json' \
     -d '{"servidor_id":"osrm_local","endpoint":"http://host.docker.internal:5000","perfil":"driving"}'
   curl -X POST localhost:8007/api/v1/osrm/servers/osrm_local/probe
   ```

3. Activar como proveedor de routing del twin:

   ```bash
   curl -X POST localhost:8007/api/v1/osrm/servers/osrm_local/activate
   ```

   Desde ese instante las rutas logísticas se recalculan por red vial real
   (duración/distancia del servidor OSRM). `deactivate` revierte al proveedor
   local — ambas transiciones quedan auditadas (ALCOA+).

### 3.2 MQTT — RTMSIL/SCADA (EDS cap. 31, telemetry-service :8006)

Marcador cuando falta: conectores SCADA vacíos; `persistencia_31_23` honesta.

```bash
docker compose --profile conectores up -d mosquitto
curl -X POST localhost:8006/api/v1/scada/connectors -H 'Content-Type: application/json' \
  -d '{"conector_id":"mqtt_planta","tipo":"mqtt","endpoint":"mqtt://host.docker.internal:1883"}'
curl -X POST localhost:8006/api/v1/scada/connectors/mqtt_planta/probe
```

Nota honesta: MQTT es pub/sub — `read` sobre un conector MQTT responde 503
explicando que no hay lectura bajo demanda; la telemetría llega por
suscripción. Para OPC UA, el conector apunta al PLC real del ciclotrón en la
red OT (`opcua://...`); el perfil `demo` ofrece un banco de pruebas local.

### 3.3 BentoML — serving de modelos (EDS 20.10-20.11, surrogate-service :8008)

Marcador cuando falta: `POST /api/v1/serving/servers/{id}/infer` → 503; el
puente de runtime deja de declarar `sin_runtime` solo con servidor vivo.

1. Desplegar el servidor BentoML con los modelos aprobados del Model Registry
   (42.8 — solo modelos `desplegado`).
2. Registrar, sondear y enlazar como runtime de ei_core:

   ```bash
   curl -X POST localhost:8008/api/v1/serving/servers -H 'Content-Type: application/json' \
     -d '{"servidor_id":"bentoml_prod","endpoint":"http://host.docker.internal:3000","ruta_salud":"/healthz"}'
   curl -X POST localhost:8008/api/v1/serving/servers/bentoml_prod/probe
   curl -X POST localhost:8008/api/v1/serving/bridge/runtime -H 'Content-Type: application/json' \
     -d '{"servidor_id":"bentoml_prod","ruta":"/predict","modelo":"<id>","version_modelo":"<ver>"}'
   ```

   El puente exige que el modelo esté desplegado en el registry (41.20/42.8);
   toda inferencia queda documentada con ejecución, modelo y versión (20.11).

### 3.4 GenAI — embeddings y LLM (EDS cap. 45, surrogate-service :8008)

Marcador cuando falta: proveedores vacíos; búsqueda semántica/RAG → 503; el
índice léxico TF-IDF sigue operativo con el marcador honesto
`embedding_neuronal: false`.

```bash
curl -X POST localhost:8008/api/v1/genai/providers -H 'Content-Type: application/json' \
  -d '{"proveedor_id":"emb_local","tipo":"embeddings","endpoint":"http://host.docker.internal:8081"}'
curl -X POST localhost:8008/api/v1/genai/providers/emb_local/probe
curl -X POST localhost:8008/api/v1/genai/providers/emb_local/semantic-index
```

Los índices semánticos son append-only con el modelo usado, para
reproducibilidad (45.8); las respuestas RAG citan solo documentos reales del
Document Registry (45.10/45.11/45.23).

### 3.5 EXFOR / NNDC / SRIM (Informe 19.10-19.13, nuclear-data-service :8001)

```bash
curl -X POST localhost:8001/api/v1/connectors/sources -H 'Content-Type: application/json' \
  -d '{"fuente_id":"exfor_iaea","tipo":"exfor","endpoint":"https://www-nds.iaea.org/exfor"}'
curl -X POST localhost:8001/api/v1/connectors/sources/exfor_iaea/probe
```

- EXFOR: importación real con metadatos (19.12 — prioridad de los datos
  experimentales conservada).
- SRIM: `tipo: "srim"` con `endpoint` = directorio local de salidas reales
  (CSV `energia_mev,stopping_power`); el sondeo verifica que el directorio
  existe; duplicados por sha256 rechazados.
- NNDC: consulta por nucleido contra el endpoint real.

## 4. Criterio de cierre de fase

- `scripts/verificar_despliegue.py` sin servicios caídos.
- Cero marcadores `no_configurado` en los conectores decididos para el centro
  (los no aplicables se documentan como tales — no se fuerzan).
- Registro de auditoría de cada activación consultable en `/audit` del
  conector correspondiente.
