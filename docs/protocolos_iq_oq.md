# Protocolos IQ / OQ — Radiopharma OS v2.0.0 (ejecutables en planta)

Estos protocolos son la "fase de pruebas" canónica (14.9). Se ejecutan sobre la
instalación física siguiendo `docs/despliegue_planta.md`. Cada protocolo deja
evidencia append-only; **PQ no forma parte de este documento**: se declara solo
bajo condiciones reales de operación, nunca en software (14.9).

## Protocolo IQ — Calificación de instalación

Objetivo: demostrar que la plataforma está instalada según especificación.

| # | Prueba | Comando / método | Criterio de aceptación |
|---|---|---|---|
| IQ-1 | Imágenes y versiones | `docker compose images` + `git describe --tags` | tag = v2.0.0, digests archivados (sha256) |
| IQ-2 | Servicios arriba | `python3 scripts/verificar_despliegue.py` | 0 servicios caídos |
| IQ-3 | Persistencia | escribir/leer objeto en MinIO, fila en PostgreSQL, punto en InfluxDB | roundtrip verificado, marcadores `no_configurado` ausentes |
| IQ-4 | Red y TLS | `curl -k` a cada endpoint `/status` con certificado de planta | 200 + cert válido |
| IQ-5 | Biblioteca nuclear | checksum sha256 de datasets versionados (reactions.json, decay/*.json) | coincide con los del repo |
| IQ-6 | Auditoría ALCOA+ | insertar evento de prueba y verificar inmutabilidad (re-escritura rechazada) | append-only confirmado |

## Protocolo OQ — Calificación operacional (funciones de software)

Objetivo: demostrar que cada función opera según especificación, **sin
producción real** (todos los cálculos son teóricos hasta PQ).

| # | Función | Método | Criterio |
|---|---|---|---|
| OQ-1 | Suite de regresión | `pytest` completo (8 servicios + pipelines) | 100 % en verde |
| OQ-2 | Yield Engine vs IAEA | tests de validación física (Hess 2001 / IAEA-NDS) | desviación < 8 % |
| OQ-3 | Blindaje (OpenMC) | reproducir caso F52 con semilla fija | T dentro de 3 σ del valor archivado |
| OQ-4 | Batch Manager | `POST /lotes/teorico` + `GET /lotes` | lote creado con trazabilidad; registro append-only |
| OQ-5 | Conectores cap. 31 | sondeo real tras cablear cada equipo | marcador honesto desaparece; lectura real archivada |
| OQ-6 | Expediente RCAE | regenerar informe integrado (F54) | JSON generado, hallazgos listados |
| OQ-7 | Recomendación ≠ decisión | intentar liberar lote por API | rechazado; liberación permanece `no_liberada` |
| OQ-8 | Copias y restauración BCDR (cap. 50) | backup + restore en entorno aislado | integridad verificada |

## Registro de ejecución

Cada protocolo ejecutado anexa una línea al registro ALCOA+ del centro:
`protocolo, id_prueba, resultado, ejecutor, fecha, evidencia (ruta/sha256)`.
Las desviaciones se gestionan como no-conformidades (cap. 49), nunca editando
el registro.

## Condición de cierre

IQ + OQ completos y firmados → la plataforma queda **lista para PQ**.
PQ requiere: ciclotrón operativo, módulos cableados, personal y lotes reales
bajo procedimientos aprobados. Solo tras PQ y el expediente regulatorio se
declara Producción Clínica (18.19).
