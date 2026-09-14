"""API REST del dominio del ciclotrón (Informe §1558; EDS 5.9).

Registro versionado de aceleradores con fuente citada obligatoria e
irradiaciones append-only validadas contra los límites reales de la
máquina, con cálculo EOB del Yield Engine.

Nota de honestidad física: la energía del haz es la declarada en la
corrida; la degradación en la ventana del blanco (19.10 — cadena
SRIM/PSTAR) NO se aplica todavía, por lo que la actividad EOB calculada
es una COTA SUPERIOR declarada, nunca un valor medido.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.application.production_service import ProductionService
from app.domain.cyclotron import (CiclotronInvalido, CiclotronRegistry)
from app.infrastructure.stopping.pstar_stopping import (PstarTables,
                                                        VentanaInvalida)

router = APIRouter(prefix="/api/v1", tags=["cyclotron"])

_registry: CiclotronRegistry | None = None
_service: ProductionService | None = None
_pstar: PstarTables | None = None

NOTA_COTA_SUPERIOR = (
    "energía de haz declarada en la corrida; sin ventana registrada no se "
    "aplica degradación (19.10) — EOB = cota superior declarada, nunca "
    "valor medido")

NOTA_DEGRADACION = (
    "degradación en ventana calculada con rangos CSDA NIST PSTAR "
    "(fuente versionada) — EOB nominal con la energía efectiva en el "
    "blanco; la aproximación de la ventana (material proxy, espesor) es "
    "supuesto declarado por el usuario, nunca verificado contra el "
    "fabricante")


def init(service: ProductionService,
         registry: CiclotronRegistry | None = None,
         pstar: PstarTables | None = None) -> None:
    global _registry, _service, _pstar
    _service = service
    _registry = registry or CiclotronRegistry()
    _pstar = pstar


def _reg() -> CiclotronRegistry:
    if _registry is None:
        raise HTTPException(503, "registro de ciclotrones no inicializado")
    return _registry


class CiclotronIn(BaseModel):
    fabricante: str
    modelo: str
    energia_max_mev: float = Field(gt=0)
    corriente_max_ua: float = Field(gt=0)
    estado_operativo: str = "operativo"
    fuente: str                      # referencia citada — obligatoria
    registrado_por: str
    motivo_version: str = "registro inicial"


class VentanaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    """Ventana del blanco: material con tabla PSTAR versionada.

    ``material``: clave de tabla PSTAR (water, iron); usar ``iron`` como
    proxy declarado de Havar es responsabilidad del usuario y queda
    registrado como supuesto — nunca como dato del fabricante.
    ``espesor_g_cm2``: espesor areal (espesor_cm × densidad declarada).
    """
    material: str
    espesor_g_cm2: float = Field(gt=0)
    descripcion: str = ""           # p. ej. "Havar 25 µm aprox. como Fe"


class IrradiacionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    energia_mev: float = Field(gt=0)
    corriente_ua: float = Field(gt=0)
    tiempo_min: float = Field(gt=0)
    reaccion_id: str = "o18_p_n_f18"
    blanco_id: str = "h2_18o"
    ventana: VentanaIn | None = None
    registrado_por: str = ""      # trazabilidad ALCOA+ del registro


def _ciclotron_dict(c) -> dict:
    return dict(ciclotron_id=c.ciclotron_id, fabricante=c.fabricante,
                modelo=c.modelo, energia_max_mev=c.energia_max_mev,
                corriente_max_ua=c.corriente_max_ua,
                estado_operativo=c.estado_operativo, fuente=c.fuente,
                version=c.version, motivo_version=c.motivo_version,
                registrado_por=c.registrado_por,
                registrado_en=c.registrado_en)


@router.post("/cyclotrons", status_code=201)
def registrar_ciclotron(body: CiclotronIn):
    try:
        c = _reg().registrar(**body.model_dump())
    except CiclotronInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _ciclotron_dict(c)


@router.get("/cyclotrons")
def listar_ciclotrones():
    return [_ciclotron_dict(c) for c in _reg().listar()]


@router.get("/cyclotrons/{ciclotron_id}/versions")
def versiones_ciclotron(ciclotron_id: str):
    try:
        return [_ciclotron_dict(c) for c in _reg().versiones(ciclotron_id)]
    except CiclotronInvalido as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/cyclotrons/{ciclotron_id}/irradiations", status_code=201)
def registrar_irradiacion(ciclotron_id: str, body: IrradiacionIn):
    try:
        irr = _reg().registrar_irradiacion(
            ciclotron_id, body.energia_mev, body.corriente_ua,
            body.tiempo_min, body.reaccion_id, body.blanco_id,
            body.registrado_por)
    except CiclotronInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    resp = dict(irradiacion_id=irr.irradiacion_id,
                ciclotron_id=irr.ciclotron_id,
                ciclotron_version=irr.ciclotron_version,
                energia_mev=irr.energia_mev, corriente_ua=irr.corriente_ua,
                tiempo_min=irr.tiempo_min, reaccion_id=irr.reaccion_id,
                blanco_id=irr.blanco_id, registrado_por=irr.registrado_por,
                registrada_en=irr.registrada_en,
                potencia_haz_w=round(body.energia_mev * body.corriente_ua, 1))

    # degradación en ventana (19.10) con rangos CSDA PSTAR reales
    energia_blanco = irr.energia_mev
    if body.ventana is not None:
        if _pstar is None:
            raise HTTPException(
                503, "tablas PSTAR no configuradas — degradación no "
                     "demostrable, nunca estimada")
        v = body.ventana
        try:
            energia_blanco = _pstar.degradar(
                v.material, v.espesor_g_cm2, irr.energia_mev)
        except (VentanaInvalida, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        resp["ventana"] = dict(
            material=v.material, espesor_g_cm2=v.espesor_g_cm2,
            descripcion=v.descripcion,
            energia_entrada_mev=irr.energia_mev,
            energia_en_blanco_mev=round(energia_blanco, 3),
            perdida_mev=round(irr.energia_mev - energia_blanco, 3),
            fuente=_pstar.source_label(),
            supuesto_declarado=True)
        resp["nota_honestidad"] = NOTA_DEGRADACION
    else:
        resp["nota_honestidad"] = NOTA_COTA_SUPERIOR

    # actividad EOB del motor de rendimiento real (σ(E) IAEA · S(E) ATIMA)
    try:
        r = _service.compute(
            reaction_id=irr.reaccion_id, target_id=irr.blanco_id,
            beam_energy_mev=energia_blanco, current_ua=irr.corriente_ua,
            irradiation_time_min=irr.tiempo_min)
        resp["eob"] = dict(
            eob_activity_gbq=round(r.eob_activity_gbq, 3),
            eob_uncertainty_gbq=round(
                r.eob_activity_gbq * r.relative_uncertainty, 3),
            saturation_yield_mbq_ua=round(r.saturation_yield_mbq_ua, 1),
            saturation_factor=round(r.saturation_factor, 5),
            dataset_id=r.dataset_id, stopping_source=r.stopping_source)
        # impurezas radionuclídicas de canales competidores (dataset citado)
        impurezas = _service.compute_impurities(
            reaction_id=irr.reaccion_id, target_id=irr.blanco_id,
            beam_energy_mev=energia_blanco, current_ua=irr.corriente_ua,
            irradiation_time_min=irr.tiempo_min,
            eob_principal_gbq=r.eob_activity_gbq)
        if impurezas:
            resp["impurezas"] = impurezas
        else:
            resp["impurezas"] = {
                "no_demostrable": True,
                "motivo": ("sin canal competidor registrado con dataset "
                           "citado para esta reacción — la impureza "
                           "nunca se estima")            }
    except ValueError as exc:
        resp["eob"] = {"no_demostrable": True, "motivo": str(exc)}
    return resp


@router.get("/cyclotrons/{ciclotron_id}/irradiations")
def historial_irradiaciones(ciclotron_id: str):
    try:
        _reg().obtener(ciclotron_id)
    except CiclotronInvalido as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return [dict(irradiacion_id=i.irradiacion_id,
                 energia_mev=i.energia_mev, corriente_ua=i.corriente_ua,
                 tiempo_min=i.tiempo_min, reaccion_id=i.reaccion_id,
                 registrada_en=i.registrada_en)
            for i in _reg().irradiaciones(ciclotron_id)]


class RecomendacionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reaccion_id: str
    blanco_id: str
    corriente_ua: float = Field(gt=0)
    tiempo_min: float = Field(gt=0)
    criterio_max_impureza_pct: float = Field(gt=0)
    fuente_criterio: str            # norma/ficha que fija el límite — obligatoria
    ventana: VentanaIn | None = None
    paso_mev: float = Field(default=0.5, gt=0, le=2.0)


@router.post("/cyclotrons/{ciclotron_id}/recommend-energy")
def recomendar_energia(ciclotron_id: str, body: RecomendacionIn):
    """Recomendación de energía con límite de impureza (Informe 18.10).

    Barre energías reales de la máquina registrada, computa EOB del
    producto y de las impurezas (canales con dataset citado) y devuelve
    la energía que maximiza el EOB cumpliendo el criterio. Es una
    RECOMENDACIÓN diferenciada de la decisión operativa — el criterio
    exige fuente citada (norma, monografía o ficha), nunca inventado.
    """
    try:
        c = _reg().obtener(ciclotron_id)
    except CiclotronInvalido as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if not body.fuente_criterio.strip():
        raise HTTPException(422, "el criterio de impureza exige fuente "
                            "citada — nunca se inventa (49.11)")
    e_max = c.energia_max_mev
    paso = body.paso_mev
    puntos = []
    n = int(e_max / paso)
    for i in range(1, n + 1):
        e_in = round(i * paso, 3)
        e_blanco = e_in
        if body.ventana is not None:
            if _pstar is None:
                raise HTTPException(503, "tablas PSTAR no configuradas")
            try:
                e_blanco = _pstar.degradar(body.ventana.material,
                                           body.ventana.espesor_g_cm2, e_in)
            except VentanaInvalida:
                continue                    # haz detenido en la ventana
        try:
            r = _service.compute(
                reaction_id=body.reaccion_id, target_id=body.blanco_id,
                beam_energy_mev=e_blanco, current_ua=body.corriente_ua,
                irradiation_time_min=body.tiempo_min)
        except ValueError:
            continue
        imp = _service.compute_impurities(
            reaction_id=body.reaccion_id, target_id=body.blanco_id,
            beam_energy_mev=e_blanco, current_ua=body.corriente_ua,
            irradiation_time_min=body.tiempo_min,
            eob_principal_gbq=r.eob_activity_gbq)
        razon = max((i_["razon_eob_pct"] or 0.0) for i_ in imp) if imp else 0.0
        puntos.append({"energia_entrada_mev": e_in,
                       "energia_en_blanco_mev": round(e_blanco, 3),
                       "eob_gbq": round(r.eob_activity_gbq, 3),
                       "impureza_max_pct": round(razon, 4)})
    viables = [p for p in puntos
               if p["impureza_max_pct"] <= body.criterio_max_impureza_pct]
    recomendacion = (max(viables, key=lambda p: p["eob_gbq"])
                     if viables else None)
    return {
        "ciclotron_id": ciclotron_id,
        "criterio_max_impureza_pct": body.criterio_max_impureza_pct,
        "fuente_criterio": body.fuente_criterio,
        "recomendacion": recomendacion,
        "curva": puntos,
        "tipo": "recomendacion",
        "nota_honestidad": (
            "recomendación del modelo físico determinista sobre datos "
            "reales versionados — NO es una decisión operativa: la "
            "decisión de producción corresponde al responsable "
            "cualificado (18.10)"),
        **({"motivo_no_viable": "ninguna energía cumple el criterio"}
           if recomendacion is None else {}),
    }


@router.get("/stopping-power/status")
def estado_stopping_power():
    """19.10: proveedores de poder de frenado REALES configurados + SRIM."""
    prov = _service.stopping_status() if _service else None
    return {
        "proveedor_configurado": prov or {"estado": "no_inicializado"},
        "pstar_ventanas": (
            {"estado": "configurado",
             "materiales": _pstar.materiales(),
             "fuente": _pstar.source_label()}
            if _pstar is not None else
            {"estado": "no_configurado",
             "motivo": "tablas PSTAR no cargadas"}),
        "srim": {
            "estado": "no_configurado",
            "motivo": ("SRIM es software propietario (solo Windows, sin "
                       "licencia en esta plataforma): nunca se simula su "
                       "salida; su rol lo cubre el proveedor ATIMA/CATIMA "
                       "con fuente versionada, y la integración PSTAR/NIST "
                       "queda registrada como pendiente (19.10)"),
        },
    }
