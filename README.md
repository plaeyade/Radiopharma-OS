# Radiopharma OS — MVP Physics Twin

## Informe cap. 19 — Biblioteca Universal de Radionúclidos (v0.56.0)

NDS: estructura completa 19.5 (nuclear, física 19.9, química 19.14, clínica 19.15, económica);
catálogo canónico PET 19.6 (11), SPECT 19.7 (5) y terapéuticos 19.8 (8); biblioteca versionada
que **nunca sobrescribe** (19.17); incorporación de nuevos núclidos **sin modificar software** (19.16,
bibliografía obligatoria); datos experimentales EXFOR 19.12 con prioridad explícita sobre modelos
teóricos y referencia/versión/fecha/fuente obligatorias; modelado radioquímico A_EOS con la fórmula
documentada 19.14 (decaimiento · eficiencia · pérdidas · purificación · formulación); ventana clínica
19.15; integraciones SRIM/TALYS/EXFOR/NNDC con estado honesto; auditoría ALCOA+.

## Informe 14.9 — Qualification Engine DQ/IQ/OQ/PQ (v0.57.0)

QC: calificación de componentes con orden estricto DQ → IQ → OQ → PQ; protocolos
versionados que **nunca se sobrescriben** (14.12); una etapa sólo se supera con
resultados reales por criterio — nada se declara sin evidencia; **PQ exige
`condiciones_reales`** (14.9): en entorno simulado la ejecución se registra pero
queda honestamente no superada; expediente de calificación estructurado como
evidencia para el RCAE (EDS 49.8/49.13, vinculada a su origen); auditoría ALCOA+.

## EDS cap. 31 — RTMSIL: SCADA Integration Layer (v0.58.0)

TEL: conectores industriales **reales** OPC UA (asyncua), MQTT (paho-mqtt) y
Modbus TCP/RTU (pymodbus) — sondeo con intento real de conexión y fallo honesto
(`fallo_conexion` + evento `perdida_comunicacion`, 31.11); lectura 503 sin
conexión viva (nunca se inventan mediciones); PLC Adapter Manager por fabricante
con traducción real al modelo interno (31.9); Time-Series Collector con
normalización UTC (31.13) y metadatos completos (31.21); Validation Engine con
formato/rango/consistencia temporal — la anomalía genera evento y la medición NO
se acepta (31.22); alarmas con historial completo que nunca se reinicia (31.12);
conectores versionados sin sobrescritura; persistencia InfluxDB/Redis/MinIO
honesta `no_configurado` (31.23); auditoría 31.24.

## EDS 20.10/20.11 — Conector BentoML real (v0.59.0)

SUR: conexión HTTP **real** (httpx) con servidores BentoML externos — servidores
versionados sin sobrescritura y endpoint http(s) obligatorio; sonda GET `/healthz`
real con `fallo_conexion` honesto; inferencia POST real con `ejecucion_id`,
modelo y versión (20.11); **503 sin conexión viva — el resultado nunca se
inventa**; puente `runtime_bentoml` registrable en el Inference Engine (41.8) con
verificación de modelo validado y desplegado (41.20/42.8); auditoría ALCOA+.

## Informe 19.10-19.13 — Conectores nucleares EXFOR/SRIM/NNDC (v0.60.0)

NDS: **EXFOR (19.12)** con consulta HTTP real e importación a la biblioteca —
referencia/versión/fecha extraídos de la respuesta real y prioridad explícita
sobre modelos teóricos; **SRIM (19.10)** con parseo real de tablas CSV de
stopping power, hash sha256, nunca sobrescribe y alimenta al Yield Engine vía
cargador inyectado; **NNDC (19.13)** con consulta real de constantes; fuentes
versionadas sin sobrescritura; sonda honesta con `fallo_conexion` real; 503 sin
conexión viva — nada se inventa; auditoría ALCOA+.

## Conector OSRM — routing terrestre real del Logistics Twin (v0.61.0)

PT: `OsrmRoutingProvider` real (API OSRM `route`/`table` vía HTTP); isócronas
reales con anillo de 12 puntos vía `/table/v1`; servidores versionados sin
sobrescritura y endpoint http(s) obligatorio; sonda real con `fallo_conexion`
honesto; **activación que inyecta el provider en el LogisticsService** — desde
ese momento `routing_source` declara `osrm-http` en cada ruta (nunca sustitución
silenciosa por el proveedor local); desactivación auditada; 503 sin conexión
viva; ruta directa real entre coordenadas; auditoría ALCOA+.

## EDS cap. 45 — Conectores GenAI: embeddings y LLM reales (v0.62.0)

SUR: embeddings neuronales **reales** vía HTTP (API OpenAI-compatible, 45.8) —
cada índice registra proveedor y versión del modelo (reproducibilidad); Vector
Index semántico con coseno real sobre vectores reales (45.9); retrieval
semántico vinculado a fuentes originales (45.10/45.11); **generación RAG con
LLM real (45.20)**: el contexto son documentos reales del registro (el contexto
nunca se inventa), la recuperación permanece separada del razonamiento (45.4) y
cada respuesta registra citas y documentos usados (45.11/45.23); proveedores
versionados sin sobrescritura; 503 sin conexión — ni el embedding ni la
respuesta se inventan; auditoría ALCOA+.

## EDS 45.7 — Extractor documental real PDF/OCR (v0.63.0)

SUR: extracción REAL de PDF — capa de texto vía pypdf y páginas escaneadas vía
render poppler + OCR Tesseract real; OCR de imágenes (png/jpg/tiff/bmp); las
páginas sin texto extraíble se reportan honestamente en `paginas_sin_texto` —
nunca se rellenan; documentos sin texto quedan en revisión (45.21); endpoint
`extractor-status` con estado real de pypdf/Tesseract/poppler; el texto
extraído alimenta el índice y la recuperación RAG.

## Fase 2 — Cableado industrial: MQTT pub/sub real y perfiles PLC (v0.66.0)

TEL: suscripción MQTT real (31.7) — cada mensaje del broker se ingiere como
medición validada (31.22): payload no numérico o fuera de rango genera
evento de validación y NO se acepta; sin conexión viva → 503 honesto; la
lectura bajo demanda sigue declarando honestamente que MQTT es pub/sub.
Perfiles de adaptador PLC por fabricante (31.9): Siemens S7 (DB → OPC UA),
Allen-Bradley ControlLogix (tags) y Modbus genérico (registros holding),
versionados y documentados; un perfil desconocido devuelve error honesto —
el mapeo nunca se inventa; `GET /adapter-profiles` y
`POST /adapters/from-profile`.

## Fase 1 — Despliegue de infraestructura y activación de conectores (v0.65.0)

Compose ampliado: Redis y, bajo perfiles, broker MQTT mosquitto (`conectores`)
y servidor OSRM propio (`mapa` — la imagen no incluye mapa: se prepara una
vez con osrm-extract/contract, hasta entonces el conector reporta honestamente
`fallo_conexion`); `.env.example` con los endpoints de cada conector
(OSRM/MQTT/BentoML/GenAI/EXFOR/NNDC/SRIM); guía `docs/despliegue_fase1.md`
que mapea cada marcador honesto (`no_configurado`/`fallo_conexion`/
`sin_runtime`) a sus pasos reales de activación; y
`scripts/verificar_despliegue.py`, que consulta los `/status` reales y lista
servicios caídos y marcadores pendientes — nunca declara completo lo que no
responde.

## EDS 45.7 — Parser Word .docx real (v0.64.0)

SUR: extracción REAL de .docx vía python-docx — párrafos y tablas (filas con
celdas separadas por ` | `); un .docx sin texto extraíble NO se inventa: el
documento permanece en revisión (45.21); `extractor-status` reporta también el
estado real de python-docx.

**Radiopharma OS** · v0.66.0 · Caps. 55-60 (Observability & Monitoring — Metrics Manager 55.6 por dominio con origen y timestamp obligatorios 55.12, Log Platform 55.7 con consulta real indexada, Distributed Tracing 55.8 reconstruido exclusivamente desde spans reales, Alert Manager 55.9 con políticas versionadas y alertas que solo nacen de mediciones reales — nunca inventadas —, AIOps 55.10 honesto `sin_modelos` · DevSecOps & Platform Engineering — SCM 56.6 con identificador único por cambio, CI 56.7 con runner real inyectado — sin runner la ejecución NO se declara —, CD 56.8 con promoción solo desde CI exitosa y escaneo sin críticos 56.9 — nunca «limpio» sin escaneo real —, Artifact Registry 56.10 con verificación sha256 real · HPC & Scientific Computing — Resource Manager 57.7 con contabilidad real que nunca sobre-asigna, GPU Manager 57.8 independiente del fabricante con asignación/liberación efectiva, Job Scheduler 57.6 con 503 honesto sin runtime científico 57.10, Workflow Manager 57.11 con orden topológico real, validación de ciclos y resultados propagados entre etapas · Digital Thread & Traceability — hilos por entidad con continuidad 58.6 (eventos anexados, nunca reescritos), Data Lineage 58.7 versionado, genealogía de producto con secuencia estricta 58.8, correlación multi-dominio real 58.9, reconstrucción histórica solo desde eventos reales 58.10, Provenance Registry 58.11 nunca sobrescrito · Deployment Technology Reference — 8 capas tecnológicas 59.5 con decisiones versionadas y justificación obligatoria: recomendadas, nunca impuestas 59.6 · Master Reference Architecture — 10 capas 60.5 y 10 volúmenes 60.6 como registro canónico, flujo integral 60.7 no redefinible, coherencia calculada sobre el registro real — nunca declara completo lo pendiente) · v0.54.0 · Caps. 53+54 (API Gateway & Integration Layer — API Registry 53.7 versionado con documentación obligatoria — nunca sobrescrito —, Lifecycle Manager 53.9 con transiciones estrictas diseño→publicada→retirada y compatibilidad de rutas entre versiones, Integration Manager 53.8 con documentación obligatoria y APIs referenciadas que deben existir en el catálogo, Traffic Manager 53.11 con limitación REAL por consumidor y ventana deslizante, validación de TODA solicitud antes del servicio 53.6 — admitida, rechazada o limitada, jamás enrutada a una API inexistente o no publicada —, registro de toda interacción 53.12, proxy HTTP de borde honestamente `no_configurado` · Data Lakehouse & Analytics Platform — Metadata Catalog 54.8 completamente versionado con evolución compatible 54.12, Data Ingestion 54.6 por lotes o flujos con origen obligatorio — NUNCA se inventan datos — y esquema vigente exigido, Data Governance Manager 54.9 con políticas versionadas — propiedad/acceso/clasificación/retención/calidad —, Data Quality Engine 54.10 con integridad/consistencia/completitud/unicidad/actualidad calculadas sobre los registros REALES ingeridos — la calidad nunca se declara sin datos —, plataforma analítica desacoplada de las bases operacionales 54.11, auditoría ALCOA+) · v0.53.0 · Caps. 51+52 (Digital Platform Core — catálogo de microservicios 51.7 con responsabilidad única e interfaces definidas, imágenes completamente trazables 51.8 — versión/dependencias/configuración/firma, nunca sobrescritas —, estado de despliegue declarado SOLO con evidencia del orquestador e imagen registrada 51.9/51.17, gestión de configuración separada del código 51.12 — cada parámetro con versión, entorno, vigencia, responsable y motivo; historial completo auditado, nunca reescrito — · Event Bus & Message Broker — Topic Manager 52.7 por dominio, Schema Registry 52.10 con compatibilidad hacia atrás obligatoria y toda versión disponible, Event Registry 52.8, Event Router 52.9 desacoplado del productor con entrega REAL a suscriptores con canal — una suscripción sin canal jamás se declara entregada y el broker externo se reporta honestamente `no_configurado` 52.6 —, Dead Letter Manager 52.11 con causa real del fallo y reprocesamiento verificado — nunca declarado sin entrega efectiva —, gestión temporal 52.12, auditoría ALCOA+ 52.20) · v0.52.0 · Caps. 41+47 (Enterprise Intelligence & AI Twin Core — Feature Store 41.7 con fuente obligatoria y trazabilidad completa — nunca una variable sin origen —, features versionadas 41.6, Inference Engine 41.8/41.12/41.22 que solo ejecuta modelos validados y desplegados del Model Registry 41.20/42.8 — 503 honesto sin runtime, NUNCA inventa el resultado —, toda inferencia documentada con modelo/versión/datos/hash/resultado/usuario, Recommendation Engine 41.9/41.3 con soporte obligatorio, naturaleza claramente diferenciada de las decisiones operativas y resolución exclusivamente por usuario autorizado · Identity & Access Management — Identity Registry 47.6 con cinco tipos de identidad — usuarios, aplicaciones, servicios, dispositivos, agentes inteligentes — y unicidad estricta, Role Manager 47.9 con definiciones versionadas — nunca sobrescritas —, Session Manager 47.10 con ciclo completo trazable — inicio/renovación/cierre/expiración registrada, nunca silenciosa —, Policy Enforcement Point 47.11 centralizado default-deny donde TODA decisión — permitida o denegada — permanece registrada 47.8, auditoría ALCOA+ 47.19) · v0.51.0 · Caps. 44+45+42+48 (Knowledge Graph & Semantic Intelligence — ontología versionada 44.6, Entity Registry con identidad semántica única 44.7, relaciones trazables con evidencia 44.8, consulta semántica 44.9, camino BFS multi-dominio — honesto «sin camino» —, razonamiento transitivo 44.10 con cadena de justificación completa, sincronización controlada idempotente 44.11 · Enterprise RAG & Scientific Knowledge — Document Registry que nunca sobrescribe 45.6/45.12, parser 45.7 con sha256 del original — PDF/OCR honestamente pendientes, nunca texto inventado —, índice léxico TF-IDF real versionado 45.8/45.9 con marcador honesto `embedding_neuronal: false`, recuperación por coseno real con filtros y fuente original 45.10, Citation Manager 45.11 · MLOps & AI Lifecycle — Dataset Manager versionado 42.6, Experiment Tracker que exige dataset+versión exactos registrados 42.7 — reproducibilidad —, Model Registry 42.8 con despliegue solo de modelos aprobados, aprobación validada 42.20 — sin responsable/documentación permanece en revisión —, reversión/retiro 42.9, monitoreo ligado a versión 42.10, historial temporal 42.12 · Cybersecurity & Zero Trust — políticas versionadas 48.6, verificación de acceso default-deny 48.1/48.4 con registro de TODA solicitud — permitida o denegada —, postura de endpoints 48.10, eventos de seguridad 48.7/48.12, detección de amenazas solo sobre eventos reales con disparadores documentados 48.8 — nunca alertas inventadas —, segmentación de red default-deny 48.9, expedientes de incidente vinculados a alertas reales 48.11, auditoría ALCOA+) · v0.50.0 · Caps. 46+43+50 (Enterprise Governance Core — Policy Manager versionado 46.6 con publicación validada 46.17 — las incompletas permanecen en revisión —, Rule Manager 46.7 con evaluación desacoplada 46.20, Architecture Manager 46.9 con dependencias no registradas marcadas honestamente, registro oficial 46.10, auditoría 46.19 · Multi-Agent Decision Support — Agent Registry versionado 43.6 con honestidad `sin_runtime` — el motor NUNCA inventa la contribución de un agente sin runtime —, Task Planner 43.12, Orchestrator 43.8, Consensus Engine 43.9 con procedencia de cada contribución, Conversation Manager 43.11 con contexto referenciado 43.10, toda salida marcada como RECOMENDACIÓN de soporte a la decisión 43.3/41.9 — nunca decide — · Business Continuity, DR & Resilience — planes versionados 50.6 con aprobación validada 50.19, Backup Manager 50.8 con respaldo REAL verificado sha256 — nunca declarado sin verificar —, eventos DR documentados 50.7/50.12, replicación honesta `no_configurada` 50.9, HA Manager 50.10 con chequeo REAL de /health — un servicio sin respuesta se reporta no disponible —, Resilience Analyzer 50.11 con MTTR sobre eventos reales — null honesto sin eventos) · v0.49.0 · Caps. 49+40 (Regulatory Compliance & Audit Engine — Requirement Registry versionado 49.6/49.12, Evidence Manager con vínculo obligatorio al origen 49.8/49.13, evaluación que exige evidencia 49.18 con marcador honesto `no_demostrable`, tablero de cumplimiento sin inflar — excluye lo no demostrable —, expedientes de auditoría 49.9 con cierre bloqueado ante hallazgos críticos/mayores sin CAPA, CAPA vinculada al hallazgo 49.10, expediente de inspección que compila el estado real marcando evidencia pendiente 49.11, audit trail 49.20 · Financial Forecasting & Scenario Analysis — escenarios aislados 40.6/40.3, Forecast Engine 40.7 con demanda compuesta documentada, Sensitivity Analyzer 40.8, Investment Evaluator 40.9 — payback/VAN/ROI con fórmulas explícitas, propuesta 41.9 —, Risk Analyzer 40.10, KPI Generator 40.11, validación 40.20, auditoría 40.22) · v0.48.0 · Caps. 35+37 (Building Environmental Management Engine — Sensor Manager vinculado al Asset Registry 35.6, HVAC con fuente SCADA obligatoria 35.7, gradientes y estabilidad de presión diferencial 35.8, zonas ambientales con configuración versionada 35.11, Alarm Manager 35.12 por área, gestión temporal 35.13 — timestamp/valor/calidad/origen —, Validation Engine 35.21: rango físico, consistencia temporal, estado del sensor y calidad del dato con eventos de validación, NUNCA corrección silenciosa; el BEME monitorea y no controla 35.3 · Facility Simulation & Capacity Planning — Scenario Manager aislado 37.6/37.3, Capacity Analyzer 37.7 con modelo analítico determinista documentado, Bottleneck Detector 37.8, propuestas de redistribución como soporte a la decisión 37.9/41.9, What-If y Expansion Planner 37.10-11 con comparación aislada, disponibilidad exigida del ALME 34.12 — nunca inventada 37.21 —, resultados versionados 37.20, auditoría 37.23) · v0.47.0 · Caps. 32-34 (Clinical Delivery & Dose Management Engine — asignación de dosis trazable al lote 32.6, Decay Calculator que usa EXCLUSIVAMENTE el NNDC Service 32.8 con 503 honesto sin servicio, sólo lotes liberados por QC asignables 32.15/32.21, secuencia de entrega completa 32.9/32.19, reprogramación por decaimiento NUNCA automática — propuesta + confirmación de usuario autorizado 32.11 —, auditoría 32.23 · Facility Twin Core — Asset Registry 33.6, Building Model versionado 33.7, áreas 33.8 y zonas 33.12, Utility Manager 33.10, Environmental Manager 33.11 con fuente de monitoreo real obligatoria — nunca simula mediciones — · Asset Lifecycle Management — ciclo de vida 34.7 con transiciones registradas, planes de mantenimiento versionados 34.9, Calibration Manager 34.10 con historial nunca eliminado y consulta de vigencia, Certification Manager 34.11, Reliability Analyzer 34.12 — disponibilidad/MTBF/frecuencia de fallas calculados sobre intervenciones reales cerradas —, Spare Parts 34.13 con stock mínimo) · v0.46.0 · Radiation Safety & Shielding Engine (EDS cap. 36: atenuación con buildup de Taylor y constantes NIST XCOM @511 keV versionadas, espesor de blindaje por bisección exacta sobre el modelo, tasa de dosis puntual con Γ(¹⁸F) documentada, zonificación GSR Part 3, contaminación superficial 36.9 y dosimetría ocupacional ICRP 20 mSv/año con registro ALCOA+ — nunca sustituye al SPR) · v0.45.0 · Restos canónicos cerrados (cap. 31 SCADA completo: conectores Modbus 31.8 — roundtrip real de protocolo en test — y MQTT 31.7 — honesto sin broker —, normalización de tags 31.13 con validación de rango 6.23 · cap. 26 Instrument Integration Layer: registry 26.6 que nunca sobrescribe, File Import Manager 26.12 con originales sha256, normalización 26.10 — pureza cromatográfica por integración de pico, identidad 511 keV en espectro γ, tablas —, auditoría 26.13/26.20/26.24 · proveedor OSRM real honesto · etiquetas OCI 10.17 en las 8 imágenes · registro inmutable de artefactos 10.18 con verificación sha256) · v0.44.0 · Fase 7 Dashboards (Informe 18.11: app Streamlit 6.18 — paneles de producción, optimización, QC, inventario, KPIs y telemetría vía APIs, nunca el PLC directamente —, vistas 3D PyVista del blanco con campo térmico — malla y campo testables sin runtime, render honesto —, exportación ParaView .vti con roundtrip de integridad para post-proceso de campos MC/FEM, y Grafana 6.17 aprovisionada — datasource InfluxDB + dashboard con los 6 paneles canónicos: ciclotrón, blanco, presión, vacío, energía, producción —, overlay `docker-compose.dashboards.yml`) · v0.43.0 · Fases 5/6/8 + infraestructura completadas (Fase 6 IA: adaptador BentoML honesto 20.10 con empaquetado versionado que nunca sobrescribe, optimizador físico de producción en YE — grilla sobre el modelo determinista con restricción térmica, recomendación 41.9 nunca decisión — y detección de anomalías MAD en TEL 6.22/6.23 con política externa versionada y auditoría · Fase 5 Operational Twin: inventario con decaimiento — lotes radiactivos con referencia temporal, consumibles con caducidad 22.7, movimientos auditados 28.24 — Economic Twin ABC caps. 38-39 — costeo por actividades con drivers, coste lote/dosis/radiofármaco 39.11-13, Revenue 38.7, KPIs 38.12, catálogo de tarifas versionado validado=false — e indicadores operativos 18.9 · Fase 8 Automatización: conector PLC OPC-UA real cap. 30 — lectura real de nodos, 503 honesto, roundtrip de protocolo contra servidor OPC-UA real en test — y DAGs Airflow cap. 8 — producción 8.17 y económico 8.19, orquestación HTTP sin cálculo científico 8.7, importables sin runtime — · Infraestructura: validador OIDC/Keycloak 47.7 — verificación real RS256 contra JWKS, 503 honesto sin proveedor, realm de referencia + overlay compose — y calificación DQ/IQ/OQ Informe 14.9 — DQ documentos canónicos + trazabilidad, IQ instalación, OQ 6 casos funcionales sobre motores reales, PQ honestamente no iniciada —) · v0.41.0 · Framework de Validación (Fase 9, Informe 18.13 + EDS cap. 10: pipeline `pipelines/validation_report.py` que consolida pruebas unitarias/integración de los 8 servicios — 596 tests, validación científica en vivo 10.15 con reproducibilidad bit a bit del Yield Engine, magnitud física vs referencias FDG, decaimiento exacto, evidencia MC vs determinista −2.10 % y puerta canónica 8.11, pruebas de rendimiento 10.16 con tiempos por servicio, validación previa al despliegue 10.21 — dependencias, integridad sha256 del artefacto, disponibilidad real de solvers — y estado honesto de los niveles clínico y regulatorio, que nunca se declaran completos; veredicto obligatorio `apto`/`no_apto` con código de salida) · v0.40.0 · Surrogate Modeling Server cap. 20 (Fase 6: dataset real versionado del Yield Engine — 41 puntos σ/S IAEA+ATIMA, ridge log-log grado 5, puerta de validación holdout 20.21 con rmse 1.7 %, Model Registry que nunca sobrescribe 20.9, Inference API auditada 20.24, Drift Monitor 20.20, BentoML reportado honestamente como runtime pendiente 20.10) · v0.39.0 · Process Twin químico (Fase 4, caps. 22-25: Reaction Engine con Kinetic Solver Arrhenius + perfil térmico + decaimiento por etapa + incertidumbre propagada, Purification Engine con Impurity/Cartridge/Recovery Managers, Formulation Engine con límites operativos, QC Release con especificaciones versionadas + Validation Engine + Release Engine — recomendación técnica, nunca liberación final) · v0.38.1 · Monte Carlo con solver real verificado e2e (OpenGATE 10.1.1 + Geant4 11.4.2 vía PyPI: 16.154 MeV/hist @ 16.5 MeV en H2-18O, potencia MC 597.68 W vs 610.5 W determinista −2.10 %, incertidumbre 0.08 %, registro DL SIM-2FC7F50694E0 con integridad ALCOA+) · v0.38.0 · Monte Carlo Interface cap. 19 (OpenGATE/Geant4 reales: transporte de protones en H2-18O, deposición/dosis, incertidumbre estadística por lotes 19.20, validación previa 19.21, comparación independiente vs determinista 19.14, auditoría 19.24, estado honesto de datasets) · v0.37.0 · Elmer FEM Interface cap. 18 (termo-mecánico acoplado Heat→Stress real: von Mises + desplazamiento, Material Library 18.8/18.14, validación numérica 18.22, artefactos con StressSolve persistidos) · v0.36.0 · Calibration Layer F3 (K-factor por lote 17.6/17.21: puerta de calidad predefinida, ajuste incremental, auditoría 17.25, descomposición de incertidumbre 17.20) · v0.35.1 · Runtime científico mínimo validado (structure TALYS esencial: 12 subdirectorios + `ctm.light`; revalidación e2e: 61 puntos, pico 331.28 mb @ 8.6 MeV, rms 0.6886) · v0.35.0 · DL Simulations (caps. 4.9/7.11: `simulation/elmer/`, hash ALCOA+) + validación con binarios reales TALYS 2.2 / ElmerFEM 26.2 · v0.34.0 · Calibration Layer F2 (indicadores 17.26, Drift Analyzer 17.10, gestión temporal 17.11, validación anti-deterioro 17.23) · v0.33.0 · QC SPC (Shewhart + WE/Nelson + Cpk, trending GMP) · Puerta canónica Yield→Burnup→Elmer · v0.32.0 · Process Twin F4 (plan de campaña: demanda → mínimo nº de lotes con decaimiento y turnaround) · v0.31.0 · Consola Física (Burnup 2D + Thermal + Elmer en navegador) · v0.30.0 · Burnup 2D radial (haz gaussiano, EOB_2D ≤ EOB_1D) + Thermal Engine reducido + acoplamiento Elmer FEM honesto · Pierna con dron VTOL (catálogo real, alcance/payload, marco EASA+IAEA Clase 7) · TALYS 2ª fuente σ(E) · v0.27.0 · Logistics Twin F1 (rutas terrestre/aérea con decaimiento en tránsito, OpenFlights, buffer TDG) · Process Twin F3 (calendario multi-paciente) · Process Twin F2 (planificación inversa desde hora de dosis + cuellos de botella + tiempos muertos medidos) · Process Twin F1 (cascada EOB→EOS con decaimiento y eficiencias, dosis por paciente) · Alertado activo (reglas validadas → persistencia ALCOA+ + webhook) · Gate formal veraPDF (eBR PDF/A-2b, 144/144 reglas) · Calibration Layer multivendor · MFA TOTP · Burnup 1D · OPC-UA · Trending EOB · `docker compose up` · datos 100 % abiertos

Primer incremento codificable del ecosistema Radiopharma OS (Informe Maestro v2.0,
EDS Vol. II): los dos microservicios que forman el núcleo del **Physics Twin** para
producción de radionúclidos PET en ciclotrón.

```
┌────────────────────┐   ┌────────────────────┐   ┌────────────────────┐
│ Nuclear Data Svc   │   │    Yield Engine    │   │  Data Lake Svc     │
│  FastAPI · :8001   │──▶│  FastAPI · :8002   │──▶│  FastAPI · :8003   │
│ σ(E) IAEA/EXFOR    │HTTP│ A_sat, EOB, burnup │HTTP│ ALCOA+ batches     │
│ decaimiento DDEP   │   │  CATIMA/ATIMA      │   │ PostgreSQL + MinIO │
└────────────────────┘   └────────────────────┘   └────────────────────┘
         ▲                                               ▲
         └──────────── pipelines/batch_cli.py ───────────┘
┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
│   Auth Service     │  │     QC Engine      │  │ Telemetry Service  │
│  FastAPI · :8004   │  │  FastAPI · :8005   │  │  FastAPI · :8006   │
└────────────────────┘  └────────────────────┘  └────────────────────┘
┌────────────────────┐
│  Process Service   │
│  FastAPI · :8007   │
│  Process Twin      │
│  EOB → EOS         │
└────────────────────┘
```

## Qué calcula

- Actividad a **saturación** y a **EOB** (fin de bombardeo) para blancos gruesos,
  integrando σ(E)/S(E) con las ecuaciones estándar de producción.
- Reacciones del MVP: **¹⁸O(p,n)¹⁸F** (H₂¹⁸O / ¹⁸O₂), **¹⁴N(p,α)¹¹C** (N₂),
  **¹⁵N(p,n)¹⁵O** (¹⁵N₂ enriquecido) y **⁶⁸Zn(p,n)⁶⁸Ga** (⁶⁸Zn enriquecido).
- **Burnup Engine** (cap. 16 EDS): corrección de rendimiento por depleción del
  blanco enriquecido. Modelo analítico de grupo único
  (`POST /api/v1/production/burnup`) y modelo **multizona 1D**
  (`POST /api/v1/production/burnup-multizone`): N capas axiales con pesos de
  producción σ(E)/S(E) por capa (misma malla de 4000 puntos del modelo base),
  σ_b(E) paramétrica con umbral, atenuación exponencial del flujo y Bateman
  con término de quemado por capa. Con `n_zones=1` reproduce exactamente el
  grupo único; el EOB sin quemado es idéntico al del modelo base.
- **Burnup Engine radial 2D** (v0.30.0, `POST /api/v1/production/burnup-2d`):
  depleción no uniforme bajo **haz gaussiano** — el spot se divide en N
  anillos con pesos de producción de forma cerrada (gaussiana truncada,
  Σw = 1 exacto), flujo medio por anillo, Bateman con quemado por anillo y
  σ_b,eff ponderada por producción del perfil axial 1D (misma física: la
  única diferencia es la distribución radial del flujo). Propiedades
  verificadas: `EOB_2D ≤ EOB_1D ≤ EOB_ideal` (la depleción se concentra en
  el eje; corrección radial positiva), σ ≫ R converge al 1D, convergencia
  en nº de anillos. Ejemplo vivo (18 MeV/300 µA/10 h, spot 0.5 cm²,
  σ = 0.1 cm): EOB_1D 2903.378 GBq → EOB_2D 2903.333 GBq (corrección
  0.045 GBq; depleción en el eje 2× la media ponderada).
- **Thermal Engine reducido** (v0.30.0, `POST /api/v1/thermal/target`):
  solución analítica estacionaria de la cadena térmica del blanco
  (potencia del haz 1 MeV·µA = 1 W → conducción axial q''·t/k → película
  q''/h), con **pico gaussiano** de forma cerrada (misma normalización que
  el Burnup radial), margen térmico frente al límite y **corriente máxima
  admisible** exacta. Es deliberadamente conservador (cota superior: toda
  la potencia conduce axialmente).
- **Acoplamiento Elmer FEM** (v0.30.0, cap. 18 EDS): generador de caso
  completo para ElmerFEM — malla nativa estructurada (cuadriláteros 404,
  formato mesh.header/nodes/elements/boundary) y SIF axisimétrico
  (Heat Equation estacionaria, fuente volumétrica gaussiana en MATC con
  ∫q'''dV = P exacto, BC convectiva en SI), runner `ELMER_CMD` (patrón
  TALYS_CMD/VERAPDF_CMD) y parser tolerante de SaveScalars. Endpoints
  `GET /api/v1/elmer/status` (honesto) y
  `POST /api/v1/elmer/thermal/compare` (FEM 2D vs reducido; **503 si el
  binario no está instalado — nunca se simula un resultado FEM**).
  **Puerta canónica (v0.33.0, cap. 8.11: «No se permite ejecutar Elmer
  sin disponer previamente del cálculo de Yield y Burnup»)**: el compare
  exige reacción/blanco y calcula Yield + Burnup con los mismos
  parámetros antes de generar el caso FEM; la respuesta lleva el linaje
  (`pipeline: yield→burnup→elmer`, EOB y pérdida por quemado) — sin
  Yield/Burnup válidos responde 422 antes de tocar el solver.
- **Data Lake (Fase 1)**: registros de lote inmutables ALCOA+ con hash SHA-256
  de integridad, anulación controlada (sin borrado), artefactos JSON en object
  store (MinIO/S3 en despliegue, filesystem en dev) y metadatos en PostgreSQL.
- **Pipeline CLI** (`pipelines/batch_cli.py`): encadena producción → linaje de
  datasets → login JWT → registro del lote → tabla de decaimiento post-EOB.
- **Auth Service**: emisión/verificación JWT (HS256), usuarios con PBKDF2-100k,
  roles de plataforma. El Data Lake exige token en todo; `created_by` se deriva
  del token (ALCOA+ *atribuible*), anular lote requiere rol `calidad`+.
- **Sesiones con refresh tokens** (Auth v2, control de acceso §11.10(d)):
  - `/login` emite par **access (corta vida) + refresh** (JWT_REFRESH_TTL_MIN,
    720 min por defecto); los access tokens llevan `jti` único por emisión,
  - `/refresh` **rota** el refresh token: el usado queda revocado en servidor
    (detección básica de reuso) y se entrega un par nuevo,
  - `/logout` revoca el refresh presentado (idempotente, tolera expirados),
  - `POST /users/{u}/revoke` (admin): revoca todas las sesiones de un usuario
    (offboarding inmediato),
  - store SQL `refresh_tokens` (jti, usuario, expira, revocado); los access
    tokens siguen verificándose localmente sin red en cada servicio.
- **MFA TOTP (RFC 6238)** — segundo factor opcional por usuario
  (§11.10(d) 21 CFR Part 11):
  - `/login` con MFA activo devuelve `{mfa_required, mfa_token}` (reto parcial
    de 5 min, sin privilegios); `POST /mfa/verify` canjea reto + código TOTP
    (o código de respaldo) por el par completo de tokens,
  - enrolamiento autoservicio: `/mfa/enroll` (secreto base32 + URI otpauth://,
    compatible con Google/Microsoft Authenticator, Aegis…), `/mfa/confirm`
    (activa y entrega 8 códigos de respaldo de un solo uso, almacenados como
    hash SHA-256), `/mfa/disable` (con código válido),
  - **anti-replay**: cada paso TOTP de 30 s se consume (no reutilizable dentro
    de su ventana); el reto MFA y los refresh tokens (claim `type`) son
    rechazados como credenciales de API en todos los servicios,
  - `POST /users/{u}/mfa/reset` (admin): reset por pérdida de dispositivo,
  - consola: login en dos pasos + diálogo de gestión MFA (icono escudo en el
    chip de sesión).
- **Perfil IBA KIUBE**: validación de corriente hasta 300 µA y energía del
  simulador OPC-UA a 18 MeV (extracción fija del KIUBE).
- **Catálogo multivendor de ciclotrones** (`GET /api/v1/equipment`): perfiles
  configurables para IBA KIUBE, Cyclone 30 y 70, GE PETtrace y MINItrace
  Qilin, Best Cyclotron Systems (B15/B70), LBT e ikure; las especificaciones
  se ajustan a la hoja del fabricante de cada sitio (`data/equipment.json`).
- **Calibration Layer** (Physics Twin calibrado con producción real, EDS
  Vol. II): factor multiplicativo C = EOB_real / EOB_predicho por
  (reacción, equipo), ajustado por **WLS con χ²** y estado GMP
  (vigente/observado/investigar); modelos **versionados** con trazabilidad
  (`POST /calibration/fit`, `GET /calibration/models`,
  `GET /calibration/{reacción}/{equipo}`); `POST /production/calibrated`
  devuelve la predicción física con el factor vigente aplicado y su
  metadato de calibración (o `calibrated=false` si no hay modelo).
  **F2 (v0.34.0, cap. 17)**:
  - **Indicadores de desempeño (17.26)** — error absoluto/relativo,
    tendencia temporal (pendiente + R²) y estabilidad (σ del error) sobre
    pares teórico ↔ medido: `POST /calibration/indicators`.
  - **Drift Analyzer (17.10)** — deriva significativa: cambio acumulado
    de la pendiente sobre el intervalo observado > 2σ de los residuos
    del ajuste lineal (avisa de degradación antes de que afecte a la
    producción; el ruido grande no se reporta como deriva).
  - **Gestión temporal (17.11)** — qué versión era válida en una fecha
    dada, para auditorías: `GET /calibration/{reacción}/{equipo}/at?when=…`
    (404 honesto si no existía ninguna).
  - **Validación anti-deterioro (17.23)** — una calibración nueva solo
    se acepta si su RMS de cocientes residuales sobre las mismas medidas
    no supera al de la versión vigente; si empeora, `fit` responde **422
    sin almacenar nada** (la validación queda registrada en el modelo).
  **F3 (v0.36.0, cap. 17)** — K-factor por lote con datos de producción reales:
  - **Medidas asociadas al lote (17.6)** — `POST /calibration/batch-measurement`
    registra la EOB medida de un lote junto a su predicción física.
  - **Puerta de calidad predefinida (17.21)** — solo se incorporan medidas
    coherentes (k ∈ [0.1, 10], u_rel ≤ 25 %, lote y operador trazables);
    «no todas las producciones se incorporan automáticamente».
  - **Ajuste incremental (17.21 + 17.23)** — `POST /calibration/fit-from-batches`
    recalcula C con las medidas aceptadas pasando la puerta anti-deterioro.
  - **Versionado y auditoría (17.22/17.25)** — operador, motivo, algoritmo y
    evidencia por registro y por ajuste; `GET /calibration/audit` expone
    también los rechazos (nada se oculta).
  - **Descomposición de incertidumbre (17.20)** — `/production/calibrated`
    reporta física, experimental y de calibración por separado; el resultado
    físico puro permanece intacto y accesible (17.3).
- **Elmer FEM Interface — termo-mecánico** (v0.37.0, EDS cap. 18):
  - **Acoplamiento Heat→Stress (18.13)** — la temperatura del HeatSolver
    alimenta el StressSolve (elasticidad lineal axisimétrica) en la misma
    malla; `POST /elmer/thermomechanical` devuelve temperatura máxima/media,
    **tensión de von Mises máxima** y **desplazamiento máximo** (18.12).
  - **Material Library (18.8/18.14)** — propiedades termo-mecánicas
    versionadas con referencia (Havar, 316L); material desconocido o
    incompleto → simulación rechazada (422 honesto).
  - **Puerta canónica 8.11** — la respuesta lleva linaje
    `yield→burnup→elmer(thermomechanical)`.
  - **Validación numérica (18.22)** — el log del solver se verifica
    (`ALL DONE`); los resultados dudosos se marcan `review_required`,
    nunca se ocultan.
  - **Registro DL** — kind `elmer_thermomechanical` (cap. 4.9) con hash
    ALCOA+, igual que el resto de simulaciones.
- **Alembic**: scaffolding de migraciones en `services/data_lake_service/alembic/`
  (revisión inicial `0001_batch_records`).
- **QC Engine** (Quality Control Twin, EDS Vol. IV):
  - corrección por decaimiento (futuro/pasado) con incertidumbres propagadas,
  - verificación de vida media por WLS sobre ln A (identidad radionuclídica,
    tolerancia configurable) y **detección de impurezas** por χ² reducido,
  - motor de reglas de aceptación: packs `fdg` y `generic_pet` precargados
    (referencias generales USP <823>/Ph. Eur. — verificar monografía vigente),
  - **SPC / trending GMP** (v0.33.0, caps. 25.17/26.19 — `POST /qc/spc`):
    carta de individuales de Shewhart (μ ± 3σ) con reglas **Western
    Electric/Nelson** (WE1 ±3σ, WE2 2/3 ±2σ, WE3 4/5 ±1σ, WE4 8 mismo lado,
    TREND 6 consecutivos) y **capacidad de proceso Cp/Cpk** al aportar
    límites de especificación. Detecta deriva del proceso antes del OOS;
    el resultado es apoyo a la decisión y nunca sustituye la evaluación
    técnica (nota explícita en la respuesta). En la consola: tarjeta
    «Carta de control SPC» en QC — historia del parámetro entre lotes,
    líneas CL/UCL/LCL y de especificación, puntos violadores marcados —
    verificado e2e (serie pH en control, Cpk 7.67; pureza decreciente →
    TREND detectado antes del OOS),
  - vidas medias resueltas desde el NDS (fallback DDEP local).
- **Ciclo GMP completo** (Data Lake v2 + `pipelines/qc_cli.py`):
  - informes QC inmutables ligados al lote (`qc_reports`, hash SHA-256),
  - decisión de liberación con reglas GMP: solo rol `calidad`+, **exige al menos
    un informe QC 'pass'**, rechazo con motivo obligatorio, lote liberado queda
    inmutable (no admite anulación ni doble decisión),
  - migración Alembic `0002_qc_reports_release`.
- **eBR — Electronic Batch Record** (Data Lake v3 + `pipelines/ebr_cli.py`):
  - documento consolidado del lote: registro de producción + informes QC +
    firmas + **pista de auditoría cronológica**, con hash de integridad del
    documento completo (`GET /api/v1/batches/{id}/ebr`),
  - **firmas electrónicas estilo 21 CFR Part 11**: re-autenticación con
    usuario+contraseña contra el Auth Service en el momento de firmar
    (§11.200), tres significados (`performed_by` operador+, `reviewed_by`
    supervisor+, `approved_by` calidad+), el firmante debe coincidir con la
    sesión JWT, y cada firma liga registro (hash) + firmante + significado +
    sello de tiempo (§11.50/11.70),
  - reglas de estado: no se firma un lote anulado; `approved_by` exige decisión
    de liberación previa; una firma queda **obsoleta de forma detectable** si el
    registro cambiara después,
  - verificación de integridad lote + QC + firmas
    (`GET /api/v1/batches/{id}/ebr/verify`),
  - migración Alembic `0003_ebr_signatures` (+ `released_at` en lotes).
- **eBR archivable en PDF/A-2b** (`GET /api/v1/batches/{id}/ebr/pdf`):
  copia legible por humanos para inspección y archivo documental — portada,
  registro de lote, informes QC con reglas de aceptación, tabla de firmas con
  hash SHA-256, pista de auditoría y bloque de integridad del documento.
  Emitido directamente como **PDF/A-2b (ISO 19005-2)** — preservación a largo
  plazo exigible en archivo GMP:
  - fuentes **DejaVu TrueType incrustadas** (subseteadas; alias de las
    base-14 para el reset de estado de reportlab — `rendering/fonts.py`),
    con cobertura unicode completa (µA, ±, ¹⁸F, →, ✓),
  - **OutputIntent ICC sRGB** incrustado (`assets/color/sRGB.icc`) y
    metadatos **XMP con `pdfaid:part=2` / `conformance=B`** + Dublin Core
    (`rendering/pdfa.py`, pikepdf), PDF 1.7,
  - **validador estructural interno** `validate_pdfa2b()` (XMP de
    conformidad, OutputIntent, incrustación de fuentes página a página,
    ausencia de cifrado) ejercido en tests; la validación formal con
    veraPDF se ejecuta en la ingesta del archivo documental,
  - cabecera `X-PDF-Conformance: PDF/A-2b` en la respuesta; descarga
    directa con `pipelines/ebr_cli.py --pdf archivo.pdf`.
- **Telemetry Service** (Operational Twin, Fase 1 · :8006):
  - series temporales de la corrida (corriente de haz, presión de blanco,
    caudal de enfriamiento…) **append-only**, etiquetadas por `batch_id` para
    vincular la evidencia operacional al expediente del lote,
  - backend conmutable por entorno: **InfluxDB 2.x** en despliegue
    (`TELEMETRY_BACKEND=influx`, protocolo de línea + Flux vía HTTP, sin
    cliente oficial) o **SQLite** en dev/test,
  - endpoints: ingesta por lotes (`POST /telemetry/points`), consulta por
    serie/etiqueta/rango (`GET /telemetry/query`), catálogo
    (`GET /telemetry/series`) y **resumen estadístico por lote**
    (`GET /telemetry/batches/{id}/summary`: n, media, min, max, σ por serie),
  - JWT de plataforma obligatorio (mismo secreto que DL/Auth); ingesta
    requiere rol operador+,
  - `pipelines/telemetry_cli.py`: simulador de corrida (rampa de corriente,
    ruido, deriva térmica) para pruebas sin hardware, con inyección de
    excursión de enfriamiento (`--excursion`).
- **Conector OPC-UA** (`pipelines/opcua_connector.py`) — ingreso de
  telemetría con el protocolo industrial del PLC del ciclotrón:
  - cliente OPC-UA (asyncua) que lee periódicamente los nodos del PLC
    (corriente/energía de haz, presión del blanco, caudal de enfriamiento)
    por *browse path* y los empuja al Telemetry Service con JWT de
    plataforma, etiquetados `source=opcua`,
  - **mapa de tags configurable** (`--mapa tags.json`): contra el PLC real
    solo cambian el endpoint y el mapa — el conector no se toca,
  - **servidor OPC-UA simulado** (`pipelines/opcua_server_sim.py`): banco
    de pruebas con el mismo árbol de nodos y modelo de proceso (rampa,
    deriva, ruido, excursión opcional); en compose con
    `docker compose --profile demo up` (servicio `opcua-sim`, puerto 4840),
  - requisito de despliegue: `pip install -r pipelines/requirements-opcua.txt`
    en la red del acelerador.
- **Operational Twin F2** — downsampling y desviaciones de proceso:
  - **diezmado de series** en `GET /telemetry/query` (`max_points` +
    `method`): **LTTB** (Largest-Triangle-Three-Buckets — selecciona puntos
    reales preservando picos y forma visual) o `bucket-mean` (promedio por
    ventana), aplicado en la capa de aplicación para paridad
    SQLite/InfluxDB,
  - **detección de desviaciones** (`POST
    /telemetry/batches/{id}/deviation-check`): reglas de rango por serie en
    packs precargados (`cyclotron_generic`: haz, presión de blanco,
    enfriamiento) o reglas propias; excluye la rampa inicial del haz
    (`grace_fraction`) y agrupa rachas fuera de límite en **eventos**
    (inicio, fin, nº de puntos, extremo, lado),
  - **registro GMP de desviaciones**: `POST /api/v1/batches/{id}/events`
    (Data Lake, operador+) declara eventos de proceso append-only con actor
    del token y sello de servidor — entran en la **pista de auditoría del
    eBR** (y de su PDF/A) vía tabla `audit_events` (Alembic `0004`),
  - en la consola: gráficas diezmadas LTTB (≤400 puntos/serie), simulación
    con excursión opcional y «Verificar desviaciones» → «Registrar en Data
    Lake (eBR)» — verificado e2e (fallo de enfriamiento → 2 eventos
    coherentes → visibles en el eBR).
- **Trending EOB histórico** (`GET /api/v1/analytics/eob-trend`) — análisis
  de deriva del rendimiento lote a lote, insumo del *trending* GMP de la
  revisión periódica de producto (APR/PQR):
  - **gráfico de control de Shewhart** sobre el EOB normalizado
    (`eob_per_uah` = GBq por µA·h de haz — comparable entre corridas con
    distinta corriente y duración): límites de aviso ±2σ y de control ±3σ;
  - detección de valores atípicos **leave-one-out** (un solo outlier no
    enmascara su propia desviación inflando σ) y límites recalculados sin
    ellos (fase I SPC); lotes anulados (`voided`) excluidos por defecto;
  - **deriva temporal**: regresión lineal sobre puntos limpios (pendiente
    %/día + R²) y **run rules** (racha monótona de 6+, racha de un mismo
    lado de la media) con clasificación estable / creciente / decreciente y
    alertas textuales por lote;
  - en la consola: pestaña **Tendencias** con control chart por reacción
    (puntos coloreados por estado, líneas de media/±2σ/±3σ), tarjetas de
    rendimiento/límites y panel de alertas — verificado e2e (deriva
    −0.42 %/día + punto 3σ detectados en vivo).
- **Alertado activo** (Data Lake v4 · `GET /api/v1/alerts`) — reglas
  **validadas como código** (no configuración opaca) que vigilan los sucesos
  del dominio y levantan alertas persistidas:
  - catálogo de reglas (`GET /api/v1/alerts/rules`): `desviacion_proceso`
    (crítica — evento declarado como desviación en la pista del lote),
    `qc_fail` (crítica — informe QC con veredicto FAIL), `qc_warning`
    (aviso) y `lote_anulado` (aviso — void con motivo);
  - cada alerta queda **persistida** (tabla `alerts`, migración
    `0005_alerts`), **registrada en la pista de auditoría del eBR**
    (evento `alerta_disparada` con actor `sistema` — ALCOA+) y
    **despachada a un webhook** (`ALERT_WEBHOOK_URL`; best-effort, 2
    intentos, nunca bloquea el flujo del lote);
  - **reconocimiento atribuible e idempotente** (`POST /alerts/{id}/ack`,
    rol operador+): conserva el primer `acked_by`/`acked_at`;
  - en la consola: tarjeta **Alertas activas** en Resumen con contador de
    pendientes, severidad y botón *Reconocer* — verificado e2e (desviación
    + QC FAIL + anulación → 3 alertas persistidas, 3 eventos en el eBR y
    3 POST al webhook; ack desde la UI).
- **Process Twin F1** (Process Service · :8007 · `POST /api/v1/process/simulate`)
  — el gemelo de proceso radioquímico: comienza exactamente donde el
  Physics Twin concluye (actividad al EOB) y continúa hasta el radiofármaco
  listo para liberación clínica (EOS):
  - **cascada por pasos** (transferencia → síntesis → purificación →
    formulación → transporte): cada paso aplica decaimiento físico durante
    su duración (`0.5^(t/T½)`) y su eficiencia de proceso η;
    cierre analítico `EOS = EOB · Π(0.5^(t_i/T½)) · Πη_i`;
  - **dosis por paciente**: `floor(EOS / dosis_paciente)` con dosis de
    referencia por protocolo (0.37 GBq ¹⁸F, 0.74 GBq ¹¹C, 0.185 GBq ⁶⁸Ga);
  - **catálogo de protocolos** (`data/protocols.json`): FDG-¹⁸F, MET-¹¹C y
    PSMA-⁶⁸Ga, todos `validated: false` — parámetros de referencia
    bibliográficos **pendientes de validación in-situ** (honestidad de
    datos, misma política que el catálogo de equipos);
  - endpoints: `GET /process/protocols`, `GET /process/protocols/{id}`,
    `POST /process/simulate` (sin JWT — motor de cálculo como YE/NDS/QC);
  - en la consola: pestaña **Proceso** (selector de protocolo + lote con
    EOB autorrellenada, tarjetas EOS/decaimiento/eficiencia/dosis, tabla de
    cascada paso a paso y **registro de la simulación en el eBR** del lote
    como evento `proceso_simulado`) — verificado e2e (lote real
    B-20260719-DA21A43E: EOB 108.95 GBq → EOS 31.03 GBq → 83 dosis).
- **Process Twin F2** (Process Service v0.2 · `POST /process/schedule` +
  `POST /process/bottleneck`) — la cascada se vuelve operativa:
  - **planificación inversa** (`/schedule`): dado el objetivo clínico
    (actividad EOS o nº de dosis a una hora de administración), resuelve la
    inversa de la cascada (`EOB = EOS / (Πdecay·Πη)`) y construye la línea
    temporal hacia atrás: inicio de haz, EOB, ventana de cada paso con su
    actividad de salida — con tiempo de preparación del haz configurable;
  - **análisis de cuello de botella** (`/bottleneck`): por paso, pérdida
    descompuesta en decaimiento + eficiencia, ganancia de EOS por minuto
    ahorrado (idéntica en todos los pasos — solo depende de T½) y por punto
    porcentual de eficiencia (máxima donde η es menor → paso dominante);
  - **tiempos muertos medidos** (consola): la telemetría real de la corrida
    (span de las series) se compara con el tiempo nominal de irradiación
    del lote → tiempo muerto estimado (rampa + manipulación), dato medido
    y no nominal;
  - verificado e2e en vivo (lote B-20260720-1428496C, KIUBE 18 MeV/75 µA):
    180 dosis a las 14:00 → haz a las 11:20, EOB requerida 233.85 GBq
    (lote real: 234.22 GBq ✓), paso dominante síntesis (73.6 GBq de
    pérdida por eficiencia), tiempo muerto medido 6 min.
- **Process Twin F3** (Process Service v0.3 · `POST /process/dose-calendar`)
  — calendario multi-paciente: fracciona la actividad EOS en dosis
  individuales con decaimiento continuo entre administraciones:
  - por cita: inventario disponible en su instante, viabilidad (la dosis
    no viable no descuenta actividad) y remanente tras la administración;
    citas desordenadas se ordenan; dosis por defecto = la del protocolo;
  - **inversa exacta**: EOS mínima que serviría TODAS las citas
    (propagación hacia atrás desde la última dosis);
  - en la consola: tarjeta **Calendario de pacientes** (filas dinámicas
    paciente/hora/dosis, tabla de viabilidad, servidos/total, extraído,
    remanente y EOS mínima) — verificado e2e en vivo (EOS real 66.7 GBq:
    3/3 pacientes servidos entre 14:00 y 18:00; EOS mínima 2.71 GBq —
    el lote está sobredimensionado para esa agenda).
- **Process Twin F4** (Process Service v0.5 · `POST /process/campaign`)
  — plan de campaña: de la demanda de pacientes a los lotes necesarios:
  - agrupa las citas en el **mínimo número de lotes viables** (voraz
    cronológico): cada lote nace `prep_min` antes de su primera cita,
    crece mientras la EOS requerida exacta (inversa del calendario, con
    decaimiento entre administraciones) quepa en la capacidad, y respeta
    la separación mínima `turnaround_min` entre lotes (haz + síntesis +
    QC del anterior);
  - honestidad operativa: las citas no servibles (dosis > capacidad, o
    el turnaround empuja la EOS más allá de la cita) se reportan como
    **no servidas** — nunca se maquilla;
  - propiedades verificadas: inversa exacta (remanente ≈ 0 al servir
    con la EOS requerida), monotonía en capacidad, turnaround entre
    lotes consecutivos;
  - en la consola: tarjeta **Plan de campaña** en Proceso (reutiliza las
    citas del calendario: capacidad/prep/turnaround, tabla de lotes con
    EOS requerida, utilización y ventana) — verificado e2e en vivo
    (7 citas: 1 lote 14.44 GBq al 36 %; con capacidad 3 GBq → 2 lotes,
    mañana 2.72 GBq al 90.6 % + tarde 1.76 GBq, turnaround respetado).
- **Logistics Twin F1** (Process Service v0.4 · `POST /process/logistics/route`
  + `/reachability`) — la distribución del radiofármaco con decaimiento
  en tránsito:
  - **terrestre**: proveedor de routing intercambiable tras interfaz
    (`RoutingProvider`): local determinista (haversine × factor vial,
    por defecto y en tests) u **OSMnx/OpenStreetMap** real en producción
    (import perezoso; cuando haya red Overpass). La capa GNN
    (city2graph) para tiempos aprendidos con GPS real de transportistas
    queda como Logistics F2 documentado en el código;
  - **aéreo**: cadena completa carretera → **buffer TDG Clase 7**
    (90 min, configurable) → **vuelo** (haversine/800 km/h + overhead)
    → mensajería destino, sobre el catálogo **OpenFlights real**
    (1.484 aeropuertos con ≥10 rutas comerciales, dominio público);
    mismo aeropuerto origen/destino → 422 con consejo de modo terrestre;
  - **alcanzabilidad**: presupuesto de tiempo para llegar con 1 dosis
    (`T½·log2(EOS/dosis)`), bandas-isócronas (radio + actividad a esa
    hora) y viabilidad por hospital;
  - instalaciones `validated: false` (coordenadas demo honestas);
  - **pierna con dron** (v0.29.0): operación punto a punto sin aeropuerto
    (ops UAS/bulto Tipo A + vuelo directo), catálogo real de 3 clases
    (VTOL ligero 3 kg/100 km, VTOL ala fija pesado 60 kg/300 km,
    helicóptero UAV 15 kg/350 km — parámetros de fabricante/publicaciones,
    `validated: false`), restricciones duras de **alcance y payload**
    (blindaje FDG 15-30 kg + contenedor: el ligero solo vale para dosis
    unitarias; el pesado no llega a 302.6 km → 422 honesto), y **notas
    regulatorias** en la respuesta (EASA specific/SORA + ICAO TI/IATA DGR,
    bulto Tipo A IAEA SSR-6);
  - en la consola: pestaña **Física** (v0.31.0): Burnup radial 2D
    interactivo (EOB ideal/1D/2D, gráfica de depleción y flujo por anillo,
    corrección radial), Thermal Engine (margen térmico, corriente máxima
    admisible, veredicto) y tarjeta Elmer FEM con estado honesto — verificado
    e2e en navegador (75 µA/2 h: EOB_2D 394.572 vs 1D 394.574 GBq;
    ventana Havar 40 µA: T_pico 502.6 K, fuera de límite por 29.5 K,
    corriente máx. 34.4 µA);
  - en la consola: pestaña **Logística** (calculadora de ruta con las
    piernas, selector de modo terrestre/aéreo/dron con catálogo de drones
    y blindaje, tarjetas de llegada/dosis, notas regulatorias,
    alcanzabilidad por hospital y bandas) — verificado e2e en vivo
    (lote 234.2 GBq: aéreo MAD→VLC 192 min → 69.6 GBq/187 dosis vs
    terrestre 472 min → 24.9 GBq; dron pesado urbano 24 min →
    201.8 GBq/545 dosis).
- **Consola web operativa** (`console/`, React + TypeScript + Vite +
  Tailwind/shadcn): el ciclo GMP completo desde el navegador —
  - **login contra el Auth Service** (JWT en sesión, chip de usuario con rol,
    logout), con gating por rol en la UI y en servidor,
  - **acciones operativas**: registrar lote (Yield Engine → Nuclear Data →
    Data Lake, como `batch_cli`), simular la corrida de telemetría,
    evaluar QC (QC Engine → informe persistido), liberar/rechazar (rol
    calidad+) y **firmar el eBR con re-autenticación** (21 CFR §11.200),
  - **CORS habilitado** en los 6 microservicios (`CORS_ORIGINS`, `*` por
    defecto en dev) para consumo desde el navegador,
  - *Resumen*: KPIs (lotes, EOB liberada, QC conforme, salud 6/6), tarjeta
    de **alertas activas** con reconocimiento y panel de salud de los 6
    microservicios con latencia,
  - *Lotes*: tabla ALCOA+ con integridad de hash y detalle del registro,
  - *Control de calidad*: informes con reglas de aceptación evaluadas,
  - *eBR*: firmas electrónicas, pista de auditoría cronológica e integridad del
    documento, con descarga del PDF archivable (modo en vivo),
  - *Telemetría*: gráficas de las series de la corrida + resumen estadístico,
  - opera en **modo en vivo** contra los microservicios (URL + token JWT en
    Configuración) o en **modo demostración** con dataset determinista cuando
    los servicios no son alcanzables;
  - **servida en docker-compose** (`console/Dockerfile` multi-etapa
    node→nginx, puerto **8080**): la consola usa **prefijos relativos de mismo
    origen** (`/dl`, `/auth`, `/ye`, `/nds`, `/qc`, `/tel`) que nginx proxifica
    a cada microservicio — sin CORS ni configuración de URLs en despliegue;
    migración automática de configuraciones guardadas con URLs absolutas
    (`rpos.cfgver`); en desarrollo las URLs absolutas siguen disponibles en
    Ajustes;
  - `cd console && npm install && npm run build` → `dist/` estático (servible
    por cualquier web server o el compose).
- El Yield Engine puede consumir los datos del Nuclear Data Service **vía HTTP**
  (variable `NUCLEAR_DATA_URL`) o en modo standalone con datasets empaquetados.
- Incertidumbre combinada (σ evaluada IAEA + stopping + corriente) y trazabilidad
  de procedencia por dataset (ALCOA+).

## Validación física

Motor vs. literatura publicada (Hess et al. 2001, EXFOR D4095, blanco gaseoso ¹⁸O):

| E (MeV) | Motor (MBq/µA sat) | Hess 2001 | Desviación |
|---|---|---|---|
| 6.0 | 2343 | 2209 | +6.1 % |
| 10.0 | 6713 | 6871 | −2.3 % |
| 14.0 | 10601 | 11004 | −3.7 % |
| 18.0 | 13091 | 13454 | −2.7 % |
| 20.0 | 13847 | 14228 | −2.7 % |

Caso típico ¹⁸F (16.5 MeV, 37 µA, 60 min, H₂¹⁸O 99.5 %): **EOB = 108.9 ± 8.1 GBq**,
saturación 9.34 GBq/µA — dentro del rango industrial habitual (2–4 Ci EOB).

Validación ¹¹C vs. rendimientos a saturación calculados por la IAEA (misma σ(E)):

| E (MeV) | Motor (GBq/µA sat) | IAEA (GBq/µA sat) | Desviación |
|---|---|---|---|
| 8.0 | 1.68 | 1.76 | −4.4 % |
| 10.0 | 2.66 | 2.71 | −1.8 % |
| 12.0 | 4.00 | 4.08 | −2.0 % |
| 16.0 | 7.37 | 7.47 | −1.3 % |
| 20.0 | 9.74 | 9.84 | −1.0 % |

Validación ¹⁵O y ⁶⁸Ga (saturación, misma referencia IAEA):

| Reacción | E (MeV) | Motor (GBq/µA) | IAEA | Desviación |
|---|---|---|---|---|
| ¹⁵N(p,n)¹⁵O | 16.0 | 5.87 | 6.00 | −2.1 % |
| ⁶⁸Zn(p,n)⁶⁸Ga | 16.0 | 14.56 | 15.00 | −2.9 % |

Casos típicos verificados en vivo: ⁶⁸Ga 14.5 MeV/25 µA/60 min → **146.1 ± 10.0 GBq EOB**;
¹⁵O 16 MeV/20 µA/5 min → **96.0 GBq EOB** (factor saturación 0.82).

Detalle completo en [`docs/VALIDATION.md`](docs/VALIDATION.md).

## Decisiones de arquitectura (vs. EDS v2.0)

1. **CATIMA/ATIMA sustituye a SRIM.** SRIM es escritorio Windows sin API; ATIMA
   (GSI) ofrece tablas de stopping power equivalentes como librería automatizable
   (`pycatima`). Fallback a tablas CSV empaquetadas si el wheel no está disponible.
2. **Datos empaquetados con el servicio.** Los datasets IAEA/EXFOR y DDEP viven
   versionados en el repo con hash SHA-256, URL fuente y fecha (ALCOA+), no se
   descargan en runtime.
3. **Datos 100 % abiertos**: IAEA-NDS Medical Portal (Padé fit, May-2021),
   LiveChart/DDEP, CATIMA. Sin licencias comerciales.
4. **Segunda fuente σ(E): TALYS** (NDS v0.2 · `GET /nds/talys/status` +
   `GET /nds/cross-sections/compare/{id}`) — verificación cruzada de las
   funciones de excitación IAEA (experimentales) contra el código teórico
   TALYS, sin necesidad de datos de planta:
   - mismo puerto `CrossSectionRepository`: `TalysCrossSectionRepository`
     ejecuta TALYS (input generado por reacción), parsea la salida real
     `rp*.tot` y cachea con procedencia ALCOA+ (input, salida cruda, CSV
     parseado, `meta.json` con versión/fecha/SHA-256);
   - comparación: resúmenes de pico de cada fuente + desviación relativa
     máxima y RMS sobre el rango solapado (solo donde la referencia IAEA
     supera el 5 % de su pico, para no amplificar ruido de umbral);
   - binario localizado con `TALYS_CMD` (patrón VERAPDF_CMD); sin binario,
     `/talys/status` responde `available: false` y la comparación 503 —
     honesto, nunca simulado.

### Instalación de los binarios científicos (TALYS y Elmer)

Ambos acoplamientos son **externos por diseño canónico** (EDS caps. 11.10 y
7.11/8.11: códigos de terceros detrás de interfaces, resultados siempre
identificados como modelados o FEM). Alternativas reales de instalación:

**TALYS** (actual: **TALYS-2.2**, licencia MIT, nds.iaea.org/talys):

| # | Vía | Comandos clave | Notas |
|---|-----|----------------|-------|
| 1 | **Tarball oficial IAEA** (recomendada) | `curl -O https://nds.iaea.org/talys/talys2.0.tar` (o 2.2), `tar xf`, `make` con gfortran ≥ 9 | ~1.6 GB (incluye librerías); compilación validada con gfortran 15 (conda) en este repo |
| 2 | **GitHub IAEA-NDS/talys** | `git clone --depth 1 https://github.com/IAEA-NDS/talys` + `make` | fuente viva; en el sandbox la red a github está bloqueada, en planta funciona |
| 3 | **Contenedor propio** | `Dockerfile`: `FROM debian + gfortran`, copia del tarball, `make`; montar el binario y `TALYS_CMD=/opt/talys/bin/talys` | reproducible y aislado; encaja con el `docker compose` del MVP |

**Elmer FEM** (actual: Elmer 9.x, GPL/LGPL, ElmerCSC):

| # | Vía | Comandos clave | Notas |
|---|-----|----------------|-------|
| 1 | **PPA oficial Ubuntu/Debian** (recomendada) | `apt-add-repository ppa:elmer-csc-ubuntu/elmer-csc-ppa && apt install elmerfem-csc` | binarios firmados, `ElmerSolver` en PATH → `ELMER_CMD` innecesaria |
| 2 | **Binarios precompilados / VM** | elmerfem.org: WSL, instalador Windows, VirtualBox VM | útil para puestos de ingeniería, no para el servicio |
| 3 | **Docker oficial** (ElmerCSC/elmerfem-docker) | imagen MPI-enabled: `docker run -v $PWD:/home elmer-runenv /usr/local/elmer/bin/ElmerSolver case.sif` | camino natural en el compose del MVP; `ELMER_CMD` apuntando a un wrapper |
| 4 | **Compilar desde fuente** | `git clone ElmerCSC/elmerfem` + CMake (+MPI/LAPACK) | control total; pesado (Fortran+C, ~30 min) |
| ❌ | conda-forge | — | **no existe paquete elmerfem** (verificado 2026-07) |

En todos los casos: `export TALYS_CMD=/ruta/talys` /
`export ELMER_CMD=/ruta/ElmerSolver` y los endpoints pasan de 503 honesto
a funcionales **sin tocar código**.

#### Validación con binarios reales (evidencia)

Compilados desde fuente en el sandbox (gfortran 16.1.0 conda; TALYS 2.2 de
`arjankoning1/talys`, ElmerFEM 26.2 build mínimo sin MPI) y ejecutados de
extremo a extremo a través de la API:

| Validación | Resultado real |
|------------|----------------|
| TALYS ¹⁸O(p,n)¹⁸F vs IAEA (estructura completa) | 61 puntos; pico 334 mb @ 8.6 MeV vs 533.4 mb @ 5.04 MeV IAEA; `rms_rel_deviation` 0.6883 |
| TALYS revalidación con **structure mínima** (v0.35.1) | 61 puntos; pico **331.28 mb @ 8.6 MeV**; `rms_rel_deviation` **0.6886**; `n_compared` 76 — vía `GET /api/v1/cross-sections/compare/o18_p_n_f18` |
| Elmer FEM vs modelo térmico reducido | `pipeline: yield→burnup→elmer`; t_peak_fem 962.73 K < t_peak_reduced 1085.45 K → `fem_conservative_bound_ok: true` (puerta cap. 8.11 respetada) |
| Registro DL de la simulación FEM | `SIM-3AF3172F5F27`, artefacto `simulation/elmer_thermal/SIM-3AF3172F5F27/results.json`, `integrity_ok: true` |
| Elmer 26.2 (devel b1187b5) e2e con artefactos persistidos (v0.35.1) | caso 610 W en 0.5 cm³: t_peak_fem 26951.65 K < t_peak_reduced 52389.15 K → cota conservadora OK (analítico axial: q·L²/2k + película + refrigerante ≈ 26 951 K, coincidencia exacta); registro `SIM-29A044FC7B60`, `integrity_ok: true` |
| Elmer termo-mecánico real (v0.37.0, cap. 18) | Heat→Stress acoplado (StressSolve): mismo caso térmico (t_peak 26951.65 K, idéntico al solver térmico) + **von Mises máx 116 033 MPa** y **desplazamiento máx 2.05 mm** (consistentes con σ≈E·α·ΔT y empotramiento de la cara refrigerada — el caso por defecto es extremo y el modelo lo reporta honestamente); validación numérica 18.22 OK; registro `SIM-41FF20C852FF`, `integrity_ok: true` |

Los artefactos de Elmer (binario + módulos HeatSolve/SaveData/ResultOutputSolve
+ librerías, 30 MB, md5 `5708285f…`) quedan persistidos en
`sci_runtime/elmer_artifacts.tar.gz`: la restauración ya no requiere toolchain
ni compilación.

**Hallazgo de ingeniería (v0.35.1):** la structure de TALYS (8.7 GB, 16
subdirectorios) tiene un **subconjunto esencial** para nucleidos ligeros:
11 subdirectorios simples (`abundance, masses, levels, best, decay,
deformation, resonances, resfiles, thermal, profile, integral`) + `optical`
+ de `density` únicamente `ground/ctm/ctm.light` (436 B, lectura
incondicional en `densitymatch_` durante la inicialización). `gamma`,
`fission` y `breakup` no se leen para p+¹⁸O y la desviación frente a la
estructura completa es < 1 % (331.28 vs 334 mb). La restauración del
runtime pasa así de ~15 min a ~2 min. Para otros proyectiles/targets
(d, α, actínidos) sí hacen falta `breakup`/`fission`/`gamma`.

 Los resultados FEM se organizan según
la estructura canónica del Data Lake (`simulation/elmer/`, cap. 4.9) y
las curvas TALYS como «datos modelados» (cap. 11.10).

## Arranque rápido

```bash
# opción A: docker — plataforma completa en un comando
docker compose up --build
#   consola operativa  -> http://localhost:8080  (nginx: SPA + proxy same-origin)
#   APIs               -> http://localhost:8001..8007/docs
#   (usuario inicial: admin / admin-change-me — cámbiese en el primer arranque)

# opción B: local
pip install -r services/yield_engine/requirements.txt
make nds   # Nuclear Data Service  -> http://localhost:8001/docs
make ye    # Yield Engine          -> http://localhost:8002/docs
```

## Uso

```bash
curl -X POST http://localhost:8002/api/v1/production \
  -H "Content-Type: application/json" \
  -d '{"reaction_id":"o18_p_n_f18","target_id":"h2_18o",
       "beam_energy_mev":16.5,"current_ua":37.0,"irradiation_time_min":60.0}'
```

Respuesta: saturación, actividad EOB, factor de saturación, incertidumbre y
procedencia del dataset usado.

## Tests

```bash
make test     # 886 tests (41 NDS + 190 YE + 143 DL + 60 Auth + 87 QC + 76 TEL + 210 PT + 79 Surrogate)
make validation  # reporte consolidado de validación Fase 9 (18.13): unitarias/integración,
                 # científica en vivo, rendimiento, pre-despliegue; veredicto apto/no_apto
make qualification  # calificación DQ/IQ/OQ (Informe 14.9); PQ honestamente no iniciada
# Dashboards (Fase 7): docker compose -f docker-compose.yml -f docker-compose.dashboards.yml up grafana streamlit
```

## Estructura

```
services/
├── nuclear_data_service/      # σ(E), decaimiento, registry de datasets
├── yield_engine/              # física de producción + burnup 1D/2D + térmico + Elmer
├── data_lake_service/         # batches + QC + liberación + eBR (ALCOA+)
├── auth_service/              # JWT + usuarios + roles + refresh tokens
├── qc_engine/                 # QC físico: decay, half-life fit, aceptación
├── telemetry_service/         # series temporales (SQLite/InfluxDB)
└── process_service/           # Process Twin: cascada EOB→EOS
pipelines/
├── batch_cli.py               # pipeline de lote end-to-end
├── qc_cli.py                  # pipeline QC + liberación GMP
├── ebr_cli.py                 # emisión, firma y verificación del eBR
└── telemetry_cli.py           # simulador de corrida + resumen de telemetría
console/                       # consola web (React + Vite + Tailwind)
```

Clean Architecture por servicio: `domain` (entidades + física pura) ←
`application` (casos de uso) ← `infrastructure` (ATIMA, CSV) ←
`presentation` (FastAPI). Convenciones: snake_case, type hints, docstrings ES.

## Roadmap inmediato

- [x] Monte Carlo Interface cap. 19 (v0.38.0): transporte de partículas
      con OpenGATE/Geant4 reales — Geometry Builder 19.6, Material
      Manager 19.7 (H2-18O consistente con el Physics Twin), Source
      Generator 19.8, Physics List Manager 19.9 (FTFP_BERT/QGSP_*_HP
      registradas), Scoring de deposición/dosis 19.11, incertidumbre
      estadística por lotes independientes con convergencia 19.20,
      validación previa 19.21 (simulaciones incompletas no entran al
      DL), comparación independiente vs potencia determinista 19.14 y
      auditoría completa 19.24. Endpoints: `GET /mc/status` (inventario
      honesto de datasets Geant4) y `POST /mc/target`. DL: kind
      `monte_carlo` en `simulation/monte_carlo/`.
- [x] Process Twin químico (v0.39.0, Fase 4): Reaction Engine cap. 22
      (Protocol/Reagent/Sequence Managers, Kinetic Solver de primer
      orden con Arrhenius, perfil térmico 22.10, control temporal
      22.11, rendimiento 22.12, decaimiento por etapa 22.13,
      incertidumbre propagada 22.21, validación previa 22.22,
      auditoría 22.24); Purification Engine cap. 23 (etapas
      retención/lavado/elución/recuperación 23.7, Cartridge Manager
      23.8, Impurity Manager 23.10, Recovery Calculator 23.11);
      Formulation Engine caps. 21.13/24 (dilución, ajuste de volumen,
      excipientes 24.7, límite de concentración 24.6); QC Release
      cap. 25 (protocolos QC 25.6, especificaciones versionadas
      25.10, Validation Engine 25.11, Release Engine 25.12 con
      recomendación técnica documentada). Endpoints:
      `POST /synthesis/reaction|purification|formulation|e2e`,
      `GET /synthesis/protocols`, `POST /qc/release`,
      `GET /qc/release/protocols`.
- [x] Surrogate Modeling Server (v0.40.0, cap. 20): Dataset Manager
      20.6 (dataset real versionado con hash, 41 puntos del Yield
      Engine determinista), Feature Engineering documentado 20.7,
      entrenamiento fuera del servidor 20.8, Model Registry
      permanente 20.9, Inference API 20.11 con auditoría 20.24,
      Drift Monitor 20.20 (sesgo/rmse → reentrenamiento), gestión
      de incertidumbre holdout 20.22, puerta de validación 20.21
      (los modelos que no cumplen no se publican). Endpoints:
      `POST /surrogates/train|infer|drift/observe`,
      `GET /surrogates/models|datasets|audit|drift/status`.
      Servicio en :8008.
- [x] Framework de Validación (v0.41.0, Fase 9 — Informe 18.13 + EDS
      cap. 10): pipeline `pipelines/validation_report.py` que consolida
      pruebas unitarias/integración 10.13/10.14 (los 8 servicios),
      validación científica 10.15 en vivo (reproducibilidad bit a bit
      del Yield Engine, magnitud física vs referencias FDG, decaimiento
      exacto, evidencia MC vs determinista −2.10 %, puerta 8.11),
      rendimiento 10.16 (tiempos por servicio) y validación previa al
      despliegue 10.21 (dependencias, integridad sha256 del artefacto,
      disponibilidad real de solvers). Los niveles clínico y
      regulatorio se reportan honestamente como no iniciados — el
      sistema nunca los declara completos. Veredicto obligatorio
      `apto`/`no_apto` con código de salida. `make validation`.
- [x] Fase 6 IA completada (v0.42.0): adaptador BentoML honesto 20.10
      (empaquetado versionado, nunca sobrescribe 20.9, 503 sin runtime),
      optimizador físico de producción (`POST /production/optimize`:
      grilla sobre el modelo determinista con restricción térmica;
      recomendación 41.9, nunca decisión) y detección de anomalías MAD
      en Telemetry 6.22/6.23 (`POST /telemetry/anomalies/detect`,
      política externa versionada, auditoría).
- [x] Fase 5 Operational Twin completada (v0.43.0): inventario con
      decaimiento (`/inventory/*`: lotes radiactivos con referencia
      temporal, consumibles con caducidad 22.7, movimientos auditados
      28.24), Economic Twin ABC caps. 38-39 (`/economics/*`: costeo por
      actividades con drivers, coste lote/dosis/radiofármaco, Revenue
      38.7, KPIs 38.12, catálogo de tarifas versionado) e indicadores
      operativos (`/operations/kpis`, 18.9).
- [x] Fase 8 Automatización (v0.43.0): conector PLC OPC-UA real
      (`/telemetry/plc/status|read`, cap. 30: lectura real de nodos,
      503 honesto, nunca simulado) y DAGs Airflow cap. 8
      (`airflow/dags/`: producción 8.17 + económico 8.19; Airflow
      orquesta vía HTTP, nunca calcula ciencia 8.7).
- [x] Infraestructura (v0.43.0): validador OIDC/Keycloak 47.7
      (`/auth/oidc/status|verify`: verificación real RS256 contra JWKS,
      realm de referencia `config/keycloak/` + overlay
      `docker-compose.keycloak.yml`) y calificación DQ/IQ/OQ
      (`make qualification`, Informe 14.9: OQ ejecuta 6 casos
      funcionales sobre los motores reales; PQ honestamente no
      iniciada).
- [x] Fase 7 Dashboards (v0.44.0, Informe 18.11): Streamlit
      (`dashboard/streamlit_app.py`, 6.18: paneles sobre las APIs —
      nunca el PLC directo —, lógica de datos testable sin runtime),
      PyVista 3D (`dashboard/pyvista_views.py`: malla del blanco +
      campo térmico conservador cap. 18; render honesto), ParaView
      (`dashboard/paraview_export.py`: campos MC/FEM a .vti con
      roundtrip de integridad) y Grafana aprovisionada (6.17:
      datasource InfluxDB + 6 paneles canónicos en
      `config/grafana/`). Overlay `docker-compose.dashboards.yml`.
- [x] Restos canónicos (v0.45.0): cap. 31 SCADA completo —
      conectores Modbus 31.8 (roundtrip real pymodbus en test) y MQTT
      31.7 (honesto), normalización de tags 31.13 con rango 6.23,
      endpoints `/telemetry/scada/*` —; cap. 26 Instrument Integration
      Layer — registry 26.6, File Import 26.12 con originales sha256,
      normalización 26.10 (pureza cromatográfica, identidad γ 511 keV,
      tablas), endpoints `/qc/instruments/*` —; proveedor OSRM real
      (honesto 503); etiquetas OCI 10.17 en las 8 imágenes; registro
      inmutable de artefactos 10.18 (`pipelines/artifact_registry.py`).
- [x] Radiation Safety & Shielding Engine (v0.46.0, EDS cap. 36): Shielding
      Manager 36.7 — atenuación I=I₀·B(μx)·e^(−μx) con buildup de Taylor,
      constantes XCOM @511 keV versionadas (`xcom-511kev-1.0.0`) para
      plomo/hierro/hormigón, espesor requerido por bisección exacta sobre
      el modelo (no aproximación TVL) —; Radiation Monitor 36.6 — tasa de
      dosis de fuente puntual con Γ(¹⁸F)=0.143 µSv·m²/(GBq·h)
      documentada —; Area Classification 36.8 con umbrales GSR Part 3
      versionados (pública/vigilada/controlada); Contamination Manager
      36.9 con registro auditado; Dosimetry Manager 36.10/36.22 — dosis
      acumulada vs límite ocupacional 20 mSv/año ICRP, estados
      conforme/investigación/supera_límite, registros ALCOA+ —.
      Endpoints `/api/v1/qc/radiation/*`. Nota explícita: cálculos de
      ingeniería con referencias; no sustituyen al SPR.
- [x] Clinical Delivery & Dose Management (v0.47.0, EDS cap. 32): Dose
      Manager 32.6, Patient Schedule 32.7, Decay Calculator EXCLUSIVO vía
      NNDC Service 32.8 (503 honesto, nunca λ local), validación 32.21 —
      sólo lotes liberados por QC 32.15 —, Delivery Coordinator 32.9 con
      secuencia temporal 32.19, Administration Manager 32.10,
      reprogramación por decaimiento como propuesta confirmable — nunca
      automática 32.11 —, auditoría 32.23. Endpoints
      `/api/v1/clinical/*`. Límite 32.3 explícito: sin producción, QC,
      interpretación clínica ni prescripción.
- [x] Facility Twin Core (cap. 33) + Asset Lifecycle (cap. 34): Asset
      Registry único 33.6, Building Model versionado 33.7, áreas 33.8 /
      zonas 33.12, Utility Manager 33.10, Environmental Manager 33.11
      — mediciones con fuente del monitoreo en tiempo real obligatoria,
      nunca simuladas —; ciclo de vida 34.7 auditado, planes de
      mantenimiento versionados 34.9, Calibration Manager 34.10 —
      historial nunca eliminado, consulta de vigencia —, Certification
      Manager 34.11, Reliability Analyzer 34.12 — disponibilidad, MTBF,
      frecuencia de fallas sobre registros reales cerrados —, Spare
      Parts 34.13. Endpoints `/api/v1/facility/*`.
- [x] Building Environmental Management Engine (v0.48.0, EDS cap. 35):
      Sensor Manager 35.6 (vínculo al Asset Registry), HVAC Manager 35.7
      (parámetros sólo con fuente SCADA — nunca inventados), Differential
      Pressure Manager 35.8 (gradiente entre zonas + estabilidad temporal,
      honesto sin datos), zonas ambientales versionadas 35.11, Alarm
      Manager 35.12 por área, gestión temporal 35.13 y Validation Engine
      35.21 (rango, temporalidad, estado del sensor, calidad) con eventos
      de validación — nunca corrección silenciosa. Endpoints
      `/api/v1/beme/*`. Filosofía 35.3: monitorea, no controla.
- [x] Facility Simulation & Capacity Planning (cap. 37): escenarios
      aislados versionados 37.6 — nunca alteran la operación 37.3 —,
      Capacity Analyzer 37.7 (utilización/saturación/reservas),
      Bottleneck Detector 37.8, Resource Optimizer 37.9 (propuestas
      documentadas, soporte a la decisión 41.9), Expansion Planner 37.10
      y What-If 37.11 (comparación aislada), Validation 37.21 (rechaza
      escenarios incompletos; la disponibilidad proviene del ALME 34.12),
      resultados versionados 37.20, auditoría 37.23. Endpoints
      `/api/v1/simulation/*`.
- [x] Regulatory Compliance & Audit Engine (v0.49.0, EDS cap. 49):
      Requirement Registry versionado 49.6 — revisiones, nunca
      sobrescribe 49.12 —, Evidence Manager 49.8 con vínculo al origen
      49.13, Compliance Manager 49.7/49.18 — cumplimiento exige
      evidencia; marcador honesto `no_demostrable` —, tablero real sin
      inflar, Audit Manager 49.9 — cierre bloqueado sin CAPA —, CAPA
      Manager 49.10, Inspection Manager 49.11 — expediente con evidencia
      pendiente explícita —, audit trail 49.20. Endpoints
      `/api/v1/compliance/*`.
- [x] Financial Forecasting & Scenario Analysis (cap. 40): escenarios
      aislados versionados 40.6/40.3, Forecast Engine 40.7 — proyección
      mensual con demanda compuesta, modelo documentado —, Sensitivity
      40.8, Investment Evaluator 40.9 — payback/VAN/ROI con fórmulas
      explícitas, PROPUESTA 41.9 —, Risk Analyzer 40.10, KPIs 40.11,
      validación 40.20, auditoría 40.22. Endpoints `/api/v1/financial/*`.
- [x] Enterprise Governance Core (v0.50.0, EDS cap. 46): Policy
      Manager 46.6 versionado — publicación validada 46.17 —, Rule
      Manager 46.7 declarativo con evaluación desacoplada 46.20,
      Architecture Manager 46.9, Governance Registry 46.10, auditoría
      46.19. Endpoints `/api/v1/governance/*`.
- [x] Multi-Agent Decision Support (cap. 43): Agent Registry 43.6
      versionado con honestidad `sin_runtime` (nunca se inventa una
      contribución), Task Planner 43.12, Orchestrator 43.8, Consensus
      Engine 43.9 con procedencia, Conversation Manager 43.11,
      recomendaciones marcadas 43.3/41.9 — el motor nunca decide —.
      Endpoints `/api/v1/agents/*`.
- [x] Business Continuity, DR & Resilience (cap. 50): planes
      versionados 50.6/50.19, Backup Manager 50.8 — respaldo real
      verificado sha256 —, Disaster Recovery 50.7/50.12, Replication
      50.9 honesta, High Availability 50.10 — chequeo real /health —,
      Resilience Analyzer 50.11 — indicadores sobre eventos reales,
      null honesto —. Endpoints `/api/v1/bcdr/*`.
- [x] Cap. 44 Knowledge Graph & Semantic Intelligence (surrogate_service): ontología versionada 44.6, entidades 44.7, relaciones con evidencia 44.8, consulta 44.9, camino BFS, inferencia transitiva justificada 44.10, sincronización 44.11, auditoría.
- [x] Cap. 45 Enterprise RAG & Scientific Knowledge (surrogate_service): Document Registry 45.6/45.12, parser sha256 45.7 (PDF/OCR honestamente pendientes), índice TF-IDF léxico versionado 45.8/45.9 (`embedding_neuronal: false` honesto), retrieval coseno 45.10, citas 45.11, auditoría.
- [x] Cap. 42 MLOps & AI Lifecycle (surrogate_service): datasets versionados 42.6, experimentos reproducibles 42.7, Model Registry 42.8, aprobación validada 42.20, reversión/retiro 42.9, monitoreo 42.10, historial 42.12, auditoría.
- [x] Cap. 48 Cybersecurity & Zero Trust (auth_service): políticas versionadas 48.6, default-deny con registro total 48.1/48.4, postura de endpoints 48.10, eventos 48.7/48.12, detección sobre eventos reales 48.8, segmentación 48.9, incidentes vinculados 48.11, auditoría.
- [x] Cap. 41 Enterprise Intelligence & AI Twin Core (surrogate_service): Feature Store 41.7 trazable y versionado, Inference Engine 41.8/41.20 — solo modelos desplegados, 503 honesto sin runtime —, toda inferencia documentada 41.12/41.22, Recommendation Engine 41.9/41.3 — soporte obligatorio, resolución solo por usuario autorizado —, auditoría.
- [x] Cap. 47 Identity & Access Management (auth_service): Identity Registry 47.6 (5 tipos, unicidad), Role Manager 47.9 versionado, Session Manager 47.10 trazable, PEP 47.11 centralizado default-deny con toda decisión registrada 47.8, auditoría 47.19.
- [x] Cap. 51 Digital Platform Core (data_lake_service): catálogo de servicios 51.7, imágenes trazables 51.8, despliegue con evidencia 51.9/51.17, configuración versionada con historial auditado 51.12, auditoría 51.19.
- [x] Cap. 52 Event Bus & Message Broker (telemetry_service): tópicos 52.7, esquemas versionados compatibles 52.10, catálogo 52.8, router desacoplado 52.9 con entrega real y `sin_canal` honesto (broker externo `no_configurado` 52.6), dead letters con causa real y reprocesamiento 52.11, temporal 52.12, auditoría 52.20.
- [x] Cap. 53 API Gateway & Integration Layer (auth_service): API Registry 53.7 versionado, Lifecycle 53.9 con compatibilidad, Integration Manager 53.8 documentado, Traffic Manager 53.11 con limitación real, validación de toda solicitud 53.6, interacciones registradas 53.12, proxy externo honesto `no_configurado`, auditoría.
- [x] Cap. 54 Data Lakehouse & Analytics Platform (data_lake_service): Metadata Catalog 54.8 versionado, Ingestion 54.6 con origen obligatorio y esquema vigente, Governance 54.9 con políticas versionadas, Data Quality 54.10 sobre registros reales — nunca declarada sin datos —, temporal 54.12, auditoría.
- [x] Cap. 55 Observability & Monitoring Platform (telemetry_service): métricas por dominio 55.6/55.12, logs indexados 55.7, trazas desde spans reales 55.8, alertas solo de mediciones reales 55.9 con políticas versionadas, AIOps honesto `sin_modelos` 55.10, auditoría.
- [x] Cap. 56 DevSecOps & Platform Engineering (data_lake_service): SCM 56.6, CI 56.7 con runner real — sin runner no se declara —, CD 56.8 con promoción validada por escaneo 56.9, Artifact Registry 56.10 con verificación sha256, auditoría.
- [x] Cap. 57 HPC & Scientific Computing (yield_engine): recursos con contabilidad real 57.7, GPUs 57.8, scheduler 57.6 con 503 honesto sin runtime 57.10, workflows topológicos con propagación real 57.11, temporal 57.12, auditoría.
- [x] Cap. 58 Digital Thread & Traceability (data_lake_service): hilos 58.6, linaje 58.7, genealogía estricta 58.8, correlación real 58.9, reconstrucción desde eventos reales 58.10, procedencia 58.11, auditoría.
- [x] Caps. 59+60 Deployment Technology Reference & Master Reference Architecture (data_lake_service): capas tecnológicas 59.5 con decisiones versionadas justificadas (referencia, nunca imposición 59.6), 10 capas 60.5, 10 volúmenes 60.6, flujo integral 60.7 canónico, coherencia calculada sobre el registro real, auditoría.
- [x] Cliente HTTP del YE hacia el NDS (variable `NUCLEAR_DATA_URL`).
- [x] **Extractor documental PDF/OCR real (EDS 45.7)**: pypdf + Tesseract/poppler, páginas sin texto reportadas honestamente.
- [x] **Conectores GenAI (EDS cap. 45)**: embeddings neuronales reales, índice semántico versionado, generación RAG con LLM real y citas trazables.
- [x] **Conector OSRM (routing terrestre real)**: provider OSRM inyectable en el Logistics Twin, isócronas vía table, sonda honesta, 503 sin conexión.
- [x] **Conectores EXFOR/SRIM/NNDC (Informe 19.10-19.13)**: importación real a la biblioteca, tablas SRIM con hash, fuentes versionadas, 503 honesto.
- [x] **Conector BentoML real (EDS 20.10/20.11)**: sonda e inferencia HTTP reales, puente al Inference Engine 41.8, 503 honesto sin servidor.
- [x] **RTMSIL / SCADA Integration Layer (EDS cap. 31)**: conectores reales OPC UA/MQTT/Modbus, adaptadores PLC por fabricante, colector de series con validación 31.22, eventos 31.11, alarmas 31.12, estados honestos.
- [x] **Qualification Engine DQ/IQ/OQ/PQ (Informe 14.9)**: orden estricto, protocolos versionados (14.12), evidencia real por criterio, PQ sólo bajo condiciones reales, expediente integrable al RCAE.
- [x] **Biblioteca Universal de Radionúclidos (Informe cap. 19)**: estructura 19.5 completa, catálogos PET/SPECT/terapéuticos (19.6-19.8), versionado sin sobrescritura 19.17, incorporación sin tocar código 19.16, EXFOR 19.12, A_EOS 19.14 y ventana clínica 19.15.
- [x] Segunda reacción: ¹⁴N(p,α)¹¹C con blanco N₂.
- [x] Reacciones ¹⁵N(p,n)¹⁵O y ⁶⁸Zn(p,n)⁶⁸Ga (mismo patrón, ~30 min c/u).
- [x] Burnup Engine: depleción de blanco enriquecido (EDS cap. 16, grupo único).
- [x] Validación con binarios reales compilados desde fuente: TALYS 2.2
  (pico 334 mb @ 8.6 MeV, rms 0.6883 vs IAEA) y ElmerFEM 26.2
  (puerta cap. 8.11: yield→burnup→elmer, cota conservadora verificada).
- [x] DL Simulations (caps. 4.9/7.11): registro ALCOA+ de resultados FEM
  en `simulation/elmer/` con hash de integridad y verificación.
- [x] Runtime científico mínimo revalidado (v0.35.1): structure TALYS
  esencial (12 subdirectorios + `ctm.light`), restauración ~2 min.
- [x] Burnup 2D radial (distribución espacial del quemado) + Elmer FEM
      acoplado tras ELMER_CMD (binario honesto: 503 si no está instalado).
- [x] Elmer FEM Interface cap. 18 (v0.37.0): análisis termo-mecánico
      acoplado Heat→Stress (18.13) con solver real — temperatura, von Mises
      y desplazamiento (18.12), Material Library versionada con rechazo de
      materiales incompletos (18.8/18.14), validación numérica con marca de
      revisión (18.22), registro DL `elmer_thermomechanical`. Endpoint:
      `POST /elmer/thermomechanical`. Artefactos Elmer v2 (con StressSolve)
      persistidos — restauración sin compilar.
- [x] Calibration Layer F3 (v0.36.0): K-factor por lote con datos de
      producción reales (cap. 17) — medidas EOB asociadas al lote (17.6),
      puerta de calidad predefinida e incremental (17.21), versionado con
      operador/motivo/algoritmo (17.22), auditoría completa con evidencia
      (17.25) y descomposición de incertidumbre física/experimental/
      calibración (17.20). Endpoints: `POST /calibration/batch-measurement`,
      `GET .../measurements`, `POST /calibration/fit-from-batches`,
      `GET /calibration/audit`.
- [x] Fase 1: Data Lake (PostgreSQL + MinIO), registros ALCOA+, pipeline CLI.
- [x] Auth Service (JWT + roles) y Data Lake endurecido; Alembic scaffolding.
- [x] Informes QC persistidos + liberación GMP (lote→QC→liberación).
- [x] eBR (Electronic Batch Record) con firmas electrónicas 21 CFR Part 11
      y pista de auditoría (`ebr_cli.py`).
- [x] eBR archivable en PDF (`/ebr/pdf`, `--pdf` en `ebr_cli.py`).
- [x] eBR en **PDF/A-2b** (ISO 19005-2): fuentes DejaVu incrustadas,
      OutputIntent ICC sRGB, XMP `pdfaid` y validador estructural propio.
- [x] Refresh tokens con rotación y revocación (logout, offboarding admin).
- [x] Telemetry Service (Operational Twin F1): series por lote, backend
      SQLite/InfluxDB, resumen estadístico, simulador CLI.
- [x] Operational Twin F2: downsampling LTTB, detección de desviaciones de
      proceso (packs de límites) y su registro GMP en el Data Lake
      (`audit_events`, visibles en el eBR).
- [x] Trending EOB: control chart de Shewhart con deriva temporal y run
      rules (`/api/v1/analytics/eob-trend` + pestaña Tendencias).
- [x] Consola web V1 (dashboard de solo lectura, modo vivo/demostración).
- [x] Consola V2 (operativa: login y ciclo GMP completo desde la UI —
      verificado e2e en navegador contra los 6 servicios).
- [x] Consola servida en docker-compose (nginx :8080, proxy same-origin a los
      6 servicios — verificado e2e: login + registro de lote YE→NDS→DL a
      través del proxy).
- [x] Conector OPC-UA (cliente industrial → Telemetry Service) con servidor
      simulado del PLC y mapa de tags configurable — verificado e2e
      (244 puntos adquiridos vía OPC-UA, visibles en consola y en
      deviation-check).
- [x] Burnup multizona 1D: perfil axial de depleción del blanco (10-50 capas),
      endpoint `/production/burnup-multizone` + gráfica de perfil en la
      consola (pestaña Lotes) — verificado e2e (EOB sin quemado idéntico al
      modelo base; pérdida global < 0.5 % en ciclotrón médico típico).
- [x] MFA TOTP (RFC 6238) con anti-replay, códigos de respaldo y login en dos
      pasos en consola — verificado e2e (vectores RFC, rechazo de retos como
      credencial de API, activación y login completos desde la UI).
- [x] Perfil IBA KIUBE: límites de operación 18 MeV / 300 µA en validadores.
- [x] Calibration Layer: WLS + χ² con criterios GMP, modelos versionados y
      producción calibrada — verificado e2e (C=0.92 recuperado con datos
      sintéticos KIUBE; predicción calibrada = física × C).
- [x] Calibration Layer F2 (v0.34.0, cap. 17): indicadores 17.26, Drift
      Analyzer 17.10, gestión temporal 17.11 y validación anti-deterioro
      17.23 — verificado e2e (deriva −1 %/día detectada con R²=1;
      calibración que deteriora rechazada con 422).
- [x] Gate formal veraPDF: `POST /batches/{id}/ebr/validate-pdfa` ejecuta el
      validador de referencia ISO 19005 (VERAPDF_CMD o imagen Docker perfil
      `calidad`), registra el veredicto en la pista de auditoría del eBR
      (ALCOA+) y `pipelines/verapdf_check.py` sirve como gate de CI.
      Incluye reparación automática de anchos de glifo (§6.2.11.5) que
      reportlab escribe mal al subsetear ciertas TTF — verificado e2e:
      eBR CONFORME 144/144 reglas con veraPDF 1.30 real.
- [x] Alertado activo: reglas validadas (desviación crítica, QC FAIL
      crítica, QC WARNING aviso, lote anulado aviso) → persistencia ALCOA+
      + evento `alerta_disparada` en el eBR + webhook best-effort; ack
      idempotente y feed en consola — verificado e2e.
- [x] Process Twin F1 (EDS cap. 5 / MVP caps. 22-24): cascada EOB→EOS con
      decaimiento por paso y eficiencias, catálogo FDG/MET/PSMA
      (`validated: false` hasta validación in-situ), dosis por paciente,
      pestaña Proceso en consola y registro `proceso_simulado` en el eBR —
      verificado e2e (EOB real 108.95 GBq → EOS 31.03 GBq → 83 dosis).
- [x] Process Twin F2: planificación inversa desde hora de dosis (inversa
      exacta de la cascada + línea temporal completa), análisis de cuello de
      botella (pérdidas decaimiento/eficiencia y sensibilidades por paso) y
      tiempo muerto medido desde telemetría real — verificado e2e.
- [x] Process Twin F3: calendario multi-paciente (fraccionamiento del EOS
      con decaimiento entre administraciones, viabilidad por cita e inversa
      exacta de EOS requerida) — verificado e2e.
- [x] Process Twin F4: plan de campaña (demanda → mínimo nº de lotes con
      inversa exacta por lote, turnaround y citas no servidas honestas) —
      verificado e2e.
- [x] QC SPC: trending GMP (Shewhart I + WE/Nelson + Cp/Cpk) como apoyo a
      la decisión (caps. 25.17/26.19) con carta de control en consola —
      verificado e2e.
- [x] Puerta canónica Yield→Burnup→Elmer (cap. 8.11) con linaje en la
      respuesta FEM — verificado e2e (503 sin binario, 422 sin puerta).
- [x] Logistics Twin F1: rutas terrestre (interfaz OSMnx-ready) y aérea
      (OpenFlights + buffer TDG) con decaimiento en tránsito,
      alcanzabilidad por presupuesto de dosis — verificado e2e.
- [ ] Logistics Twin F2: OSRM/Valhalla self-hosted como proveedor de
      routing en producción, y capa GNN (city2graph) para predicción de
      tiempos con GPS real de transportistas (cuando exista telemetría).
- [x] Pierna con dron (v0.29.0): catálogo de 3 clases VTOL, restricciones
      de alcance/payload, bulto Tipo A y marco EASA/IAEA Clase 7 en notas —
      verificado e2e.
- [ ] Protocolos del Process Twin validados con datos in-situ (bloqueado:
      requiere rendimientos y tiempos medidos en planta).
- [x] TALYS como segunda fuente de σ(E) (cap. 13): proveedor tras el mismo
      puerto del NDS, caché ALCOA+, verificación cruzada con métricas y
      endpoints /talys/status + /cross-sections/compare — binario vía
      TALYS_CMD (patrón VERAPDF_CMD).
- [x] Burnup 2D radial + Thermal Engine + acoplamiento Elmer FEM
      (v0.30.0): depleción gaussiana por anillos (EOB_2D ≤ EOB_1D),
      térmico reducido exacto con corriente máxima, generador de malla
      nativa + SIF axisimétrico y runner ELMER_CMD con status/503 honestos
      (binario no instalable en el sandbox: no está en conda-forge) —
      verificado e2e. Pendiente: ejecutar el FEM real en planta.
- [ ] Conector OPC-UA contra el PLC real (red del acelerador), Keycloak/OIDC
      externo, validación veraPDF en CI del archivo documental.
