"""API REST del RTMSIL — SCADA Integration Layer (EDS cap. 31)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...domain import scada
from ...domain.scada import ScadaEngine, ScadaInvalido, SinCanal

router = APIRouter(prefix="/api/v1/scada", tags=["scada-rtmsil"])

_engine: ScadaEngine | None = None


def init(engine: ScadaEngine | None = None, **kwargs) -> None:
    global _engine
    _engine = engine or ScadaEngine(**kwargs)


def _eng() -> ScadaEngine:
    if _engine is None:
        init()
    return _engine  # type: ignore[return-value]


def _guard(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except SinCanal as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ScadaInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


class ConectorIn(BaseModel):
    conector_id: str
    tipo: str
    endpoint: str
    configuracion: dict = {}
    responsable: str


class AdaptadorIn(BaseModel):
    fabricante: str
    mapeo: dict
    responsable: str


class TraduccionIn(BaseModel):
    datos_externos: dict


class ValidacionIn(BaseModel):
    variable: str
    minimo: float
    maximo: float
    responsable: str


class MedicionIn(BaseModel):
    dispositivo: str
    variable: str
    valor: float
    unidad: str
    timestamp: str
    origen: str
    calidad: str = "buena"


class EventoIn(BaseModel):
    tipo: str
    dispositivo: str
    detalle: dict = {}
    actor: str


class AlarmaIn(BaseModel):
    alarma_id: str
    criticidad: str
    origen: str
    responsable: str
    detalle: str = ""


class AlarmaEstadoIn(BaseModel):
    estado: str
    actor: str
    detalle: str = ""


@router.post("/connectors", status_code=201)
def registrar_conector(body: ConectorIn):
    con = _guard(_eng().registrar_conector, body.conector_id, body.tipo,
                 body.endpoint, body.configuracion, body.responsable)
    return {"conector_id": con.conector_id, "version": con.version}


@router.get("/connectors")
def conectores():
    return _eng().conectores()


@router.get("/connectors/{conector_id}/history")
def historial_conector(conector_id: str):
    return [{"version": c.version, "endpoint": c.endpoint,
             "configuracion": c.configuracion,
             "responsable": c.responsable,
             "registrado_en": c.registrado_en}
            for c in _eng().historial_conector(conector_id)]


@router.post("/connectors/{conector_id}/probe")
def sondear(conector_id: str, actor: str = "sistema"):
    return _guard(_eng().sondear, conector_id, actor)


@router.post("/connectors/{conector_id}/read")
def leer(conector_id: str, variable: str, actor: str = "sistema"):
    return _guard(_eng().leer_variable, conector_id, variable, actor)


class SuscripcionIn(BaseModel):
    topico: str
    dispositivo: str
    variable: str
    unidad: str
    responsable: str


@router.post("/connectors/{conector_id}/subscribe", status_code=201)
def suscribir(conector_id: str, body: SuscripcionIn):
    return _guard(_eng().suscribir_mqtt, conector_id, body.topico,
                  body.dispositivo, body.variable, body.unidad,
                  body.responsable)


@router.get("/subscriptions")
def suscripciones():
    return _eng().suscripciones()


class PersistenciaIn(BaseModel):
    backend: str               # influxdb | redis | minio
    config: dict
    responsable: str


def _almacen_real(backend: str, config: dict):
    if backend == "influxdb":
        from app.infrastructure.scada_persistencia import AlmacenInflux
        return AlmacenInflux(config["url"], config["token"],
                             config["org"], config["bucket"])
    if backend == "redis":
        from app.infrastructure.scada_persistencia import AlmacenRedis
        return AlmacenRedis(config["host"], int(config.get("puerto", 6379)))
    raise HTTPException(
        status_code=422, detail=(
            f"backend {backend} sin implementación en esta capa — se "
            "reporta honestamente no_configurado; influxdb y redis están "
            "disponibles (31.23)"))


@router.post("/persistence", status_code=201)
def configurar_persistencia(body: PersistenciaIn):
    """Activa un backend de persistencia real (31.23) con sondeo previo;
    si no responde → 503 honesto y no queda configurado."""
    almacen = _almacen_real(body.backend, body.config)
    return _guard(_eng().configurar_persistencia, body.backend, almacen,
                  body.responsable)


@router.get("/persistence")
def estado_persistencia():
    return _eng().estado_capa()["persistencia_31_23"]


@router.get("/adapter-profiles")
def perfiles_plc():
    from app.domain.plc_profiles import perfiles_disponibles
    return perfiles_disponibles()


class PerfilIn(BaseModel):
    perfil_id: str
    responsable: str


@router.post("/adapters/from-profile", status_code=201)
def adaptador_desde_perfil(body: PerfilIn):
    adp = _guard(_eng().registrar_adaptador_desde_perfil, body.perfil_id,
                 body.responsable)
    return {"fabricante": adp.fabricante, "version": adp.version}


@router.post("/adapters", status_code=201)
def registrar_adaptador(body: AdaptadorIn):
    adp = _guard(_eng().registrar_adaptador, body.fabricante, body.mapeo,
                 body.responsable)
    return {"fabricante": adp.fabricante, "version": adp.version}


@router.post("/adapters/{fabricante}/translate")
def traducir(fabricante: str, body: TraduccionIn):
    return _guard(_eng().traducir, fabricante, body.datos_externos)


@router.post("/validations", status_code=201)
def definir_validacion(body: ValidacionIn):
    return _guard(_eng().definir_validacion, body.variable, body.minimo,
                  body.maximo, body.responsable)


@router.post("/measurements", status_code=201)
def registrar_medicion(body: MedicionIn):
    med = _guard(_eng().registrar_medicion, body.dispositivo,
                 body.variable, body.valor, body.unidad, body.timestamp,
                 body.origen, body.calidad)
    return {"medicion_id": med.medicion_id, "timestamp": med.timestamp,
            "calidad": med.calidad}


@router.get("/series/{variable}")
def serie(variable: str):
    return _eng().serie(variable)


@router.post("/events", status_code=201)
def registrar_evento(body: EventoIn):
    return _guard(_eng().registrar_evento_operativo, body.tipo,
                  body.dispositivo, body.detalle, body.actor)


@router.get("/events")
def eventos(dispositivo: str | None = None):
    return _eng().eventos(dispositivo)


@router.post("/alarms", status_code=201)
def registrar_alarma(body: AlarmaIn):
    al = _guard(_eng().registrar_alarma, body.alarma_id, body.criticidad,
                body.origen, body.responsable, body.detalle)
    return {"alarma_id": al.alarma_id, "estado": al.estado}


@router.post("/alarms/{alarma_id}/transition")
def transicion_alarma(alarma_id: str, body: AlarmaEstadoIn):
    al = _guard(_eng().cambiar_estado_alarma, alarma_id, body.estado,
                body.actor, body.detalle)
    return {"alarma_id": al.alarma_id, "estado": al.estado,
            "historial": al.historial}


@router.get("/alarms")
def alarmas():
    return _eng().alarmas()


@router.get("/status")
def estado():
    return _eng().estado_capa()


@router.get("/audit")
def auditoria():
    return _eng().auditoria()


@router.get("/meta")
def meta():
    return {"version_motor": scada.SCADA_VERSION,
            "tipos_conector": list(scada.TIPOS_CONECTOR),
            "tipos_evento": list(scada.TIPOS_EVENTO),
            "nota": ("conexiones reales via asyncua/paho-mqtt/pymodbus; "
                     "sin endpoint o sin conexión viva el estado se "
                     "reporta honestamente y las lecturas devuelven "
                     "503 — nunca se inventan mediciones.")}
