# Guía de despliegue en planta — Radiopharma OS v2.0.0-rc1

**Alcance:** pasar del sandbox (validación teórica) a la instalación física del
centro (radiofarmacia + ciclotrón). Sigue `docs/despliegue_fase1.md` y la
extiende hasta la Puerta de Producción Clínica (Informe 18.19).

**Regla de plataforma honesta:** ningún marcador (`no_configurado`,
`fallo_conexion`, `sin_runtime`, `pendiente_entorno`) se borra a mano. Cada
uno desaparece solo cuando el equipo/servicio real responde. PQ nunca se
declara en software (14.9).

## 0. Prerrequisitos

- Servidor Linux con Docker + docker compose plugin, 8 vCPU / 32 GB RAM
  recomendados, red de planta con acceso a: ciclotrón (PLC/SCADA), módulos de
  síntesis, calibradores de dosis (si integran), red del hospital (PACS/HIS
  fuera del alcance del MVP).
- Certificados TLS internos, política de contraseñas (IAM cap. 47).
- Este repositorio clonado: `git clone <repo> && cd radiopharma-os`.
- Paquete de evidencia: `git bundle` o tag `v2.0.0-rc1`.

## 1. Infraestructura base (idéntico a despliegue_fase1.md)

```bash
cp .env.example .env        # RELLENAR secretos reales; nunca los de ejemplo
docker compose up -d
python3 scripts/verificar_despliegue.py
```

Resultado esperado: servicios arriba; marcadores honestos activos en conectores
aún no cableados. Esto es correcto — es el estado honesto.

## 2. Cableado de conectores industriales (cap. 31)

Para cada equipo, registrar endpoint real y sondear:

1. **OPC UA (31.6)** — PLC del ciclotrón: registrar endpoint
   `opc.tcp://<plc>:4840`, certificados, `POST /probe`. El marcador
   `fallo_conexion` debe desaparecer; si no, revisar red/certificados —
   no tocar el código.
2. **MQTT (31.7)** — broker: `docker compose --profile conectores up -d`
   (Mosquitto) o broker de planta; registrar y sondear.
3. **Modbus (31.8)** — registradores de módulos de síntesis.

## 3. Datos nucleares y física

- Biblioteca de radionúclidos (cap. 19): operativa sin red externa
  (datasets versionados IAEA/DDEP en el repo).
- Tablas SRIM (19.10): colocar tablas reales en el directorio configurado y
  promover con sha256 (el sistema las valida antes de usarlas).
- OpenMC+DAGMC (opcional, blindaje): binario compilado v1.25.1 en
  `sci_runtime/openmc_dagmc_bin/` + `bunker_dagmc.h5m` sellado (F61);
  requiere `LD_LIBRARY_PATH` del entorno dagmc y `materials.xml` UWUW.

## 4. Calificación (14.9)

1. **DQ/IQ/OQ**: ejecutar el Qualification Engine sobre la instalación real;
   adjuntar evidencia (scripts en `qc_engine`).
2. **PQ**: SOLO bajo condiciones reales de operación con el ciclotrón.
   El engine la marca `no_declarada_nunca` hasta entonces. No forzar.
3. Calibración 19.16: con los primeros datos de haz reales (hoy diferida).

## 5. Operación asistida

- Yield Engine / Batch Manager (`/lotes`): cálculos teóricos de apoyo.
  Toda salida es **recomendación**, nunca decisión operacional (18.10/41.9).
- QC y liberación de lotes: siempre humanos; el sistema nunca libera.
- Registro append-only ALCOA+: no editar `registro_lotes.jsonl` ni bases.

## 6. Puerta a Producción Clínica (18.19)

Checklist antes de declarar la fase:

- [ ] `verificar_despliegue.py` sin `no_configurado` en conectores activados
- [ ] IQ/OQ aprobados con evidencia archivada
- [ ] PQ ejecutada en condiciones reales (acto humano + evidencia)
- [ ] Expediente RCAE generado (F54) y presentado ante la autoridad sanitaria
- [ ] Personal formado; procedimientos firmados

Hasta completar esta lista, la plataforma opera como **sistema de apoyo
teórico validado**, no como sistema de producción clínica.
