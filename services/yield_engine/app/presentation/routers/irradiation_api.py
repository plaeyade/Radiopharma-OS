"""API REST de enfriamiento del blanco y perfiles de irradiación.

- EDS 5.10 cooling_configuration: h y geometría SOLO con fuente citada
  (literatura especializada o ficha técnica del proveedor) — versionado,
  nunca sobrescribe. El FEM térmico usa la h registrada vigente; sin
  runtime Elmer → 503 honesto.
- EDS 5.9: perfil de irradiación COMPLETO como entidad versionada
  (energía, corriente, tiempo, blanco, reacción, ventana PSTAR, perfil
  de haz) — las irradiaciones pueden ejecutarse por perfil+versión,
  reproducibles en el tiempo (ALCOA+).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.application.production_service import ProductionService
from app.domain.cyclotron import CiclotronInvalido, CiclotronRegistry
from app.domain.irradiation_profile import (PerfilHaz, PerfilInvalido,
                                            PerfilIrradiacionRegistry,
                                            VentanaPerfil)
from app.domain.target_cooling import CoolingInvalido, CoolingRegistry
from app.infrastructure.elmer.elmer_runner import ElmerError, ElmerUnavailable
from app.infrastructure.stopping.pstar_stopping import (PstarTables,
                                                        VentanaInvalida)

router = APIRouter(prefix="/api/v1", tags=["irradiation"])

_service: ProductionService | None = None
_ciclotrones: CiclotronRegistry | None = None
_cooling: CoolingRegistry | None = None
_perfiles: PerfilIrradiacionRegistry | None = None
_pstar: PstarTables | None = None

NOTA_COTA_SUPERIOR = (
    "sin ventana en el perfil no se aplica degradación (19.10) — EOB = "
    "cota superior declarada, nunca valor medido")
NOTA_DEGRADACION = (
    "degradación en ventana con rangos CSDA NIST PSTAR (fuente "
    "versionada); la aproximación de la ventana es supuesto declarado "
    "por el usuario")


def init(service: ProductionService, ciclotrones: CiclotronRegistry,
         cooling: CoolingRegistry, perfiles: PerfilIrradiacionRegistry,
         pstar: PstarTables | None = None) -> None:
    global _service, _ciclotrones, _cooling, _perfiles, _pstar
    _service, _ciclotrones = service, ciclotrones
    _cooling, _perfiles, _pstar = cooling, perfiles, pstar


# ------------------------------------------------- enfriamiento (EDS 5.10)
class CoolingIn(BaseModel):
    h_w_cm2_k: float
    geometria: str
    fuente: str                      # literatura / ficha técnica citada
    registrado_por: str
    motivo_version: str = "registro inicial"


def _cooling_dict(c) -> dict:
    return dict(config_id=c.config_id, blanco_id=c.blanco_id,
                h_w_cm2_k=c.h_w_cm2_k, geometria=c.geometria,
                fuente=c.fuente, version=c.version,
                motivo_version=c.motivo_version,
                registrado_por=c.registrado_por,
                registrado_en=c.registrado_en)


@router.post("/targets/{blanco_id}/cooling-configs", status_code=201)
def registrar_cooling(blanco_id: str, body: CoolingIn):
    try:
        return _cooling_dict(_cooling.registrar(
            blanco_id, **body.model_dump()))
    except CoolingInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/targets/{blanco_id}/cooling-configs")
def versiones_cooling(blanco_id: str):
    return [_cooling_dict(c) for c in _cooling.versiones(blanco_id)]


@router.get("/targets/{blanco_id}/cooling-configs/current")
def cooling_vigente(blanco_id: str):
    try:
        return _cooling_dict(_cooling.vigente(blanco_id))
    except CoolingInvalido as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# -------------------------------------------------- perfiles (EDS 5.9)
class VentanaIn(BaseModel):
    material: str
    espesor_g_cm2: float = Field(gt=0)
    descripcion: str = ""


class HazIn(BaseModel):
    forma: str = "gaussiano"
    sigma_cm: float | None = 0.5
    notas: str = ""


class PerfilIn(BaseModel):
    nombre: str
    reaccion_id: str = "o18_p_n_f18"
    blanco_id: str = "h2_18o"
    energia_mev: float = Field(gt=0)
    corriente_ua: float = Field(gt=0)
    tiempo_min: float = Field(gt=0)
    ventana: VentanaIn | None = None
    haz: HazIn | None = None
    registrado_por: str
    motivo_version: str = "registro inicial"


def _perfil_dict(p) -> dict:
    return dict(
        perfil_id=p.perfil_id, nombre=p.nombre, reaccion_id=p.reaccion_id,
        blanco_id=p.blanco_id, energia_mev=p.energia_mev,
        corriente_ua=p.corriente_ua, tiempo_min=p.tiempo_min,
        ventana=(None if p.ventana is None else dict(
            material=p.ventana.material,
            espesor_g_cm2=p.ventana.espesor_g_cm2,
            descripcion=p.ventana.descripcion)),
        haz=dict(forma=p.haz.forma, sigma_cm=p.haz.sigma_cm,
                 notas=p.haz.notas),
        version=p.version, motivo_version=p.motivo_version,
        registrado_por=p.registrado_por, registrado_en=p.registrado_en)


@router.post("/irradiation-profiles", status_code=201)
def registrar_perfil(body: PerfilIn):
    try:
        p = _perfiles.registrar(
            nombre=body.nombre, reaccion_id=body.reaccion_id,
            blanco_id=body.blanco_id, energia_mev=body.energia_mev,
            corriente_ua=body.corriente_ua, tiempo_min=body.tiempo_min,
            ventana=(None if body.ventana is None else VentanaPerfil(
                **body.ventana.model_dump())),
            haz=(None if body.haz is None else PerfilHaz(
                **body.haz.model_dump())),
            registrado_por=body.registrado_por,
            motivo_version=body.motivo_version)
    except PerfilInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _perfil_dict(p)


@router.get("/irradiation-profiles")
def listar_perfiles():
    return [_perfil_dict(p) for p in _perfiles.listar()]


@router.get("/irradiation-profiles/{perfil_id}/versions")
def versiones_perfil(perfil_id: str):
    try:
        return [_perfil_dict(p) for p in _perfiles.versiones(perfil_id)]
    except PerfilInvalido as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# -------------------------------------- irradiación por perfil versionado
class IrradiacionPorPerfilIn(BaseModel):
    perfil_id: str
    version: int | None = None       # None = vigente


@router.post("/cyclotrons/{ciclotron_id}/irradiations/by-profile",
             status_code=201)
def irradiar_por_perfil(ciclotron_id: str, body: IrradiacionPorPerfilIn):
    try:
        perfil = _perfiles.obtener(body.perfil_id, body.version)
    except PerfilInvalido as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    try:
        irr = _ciclotrones.registrar_irradiacion(
            ciclotron_id, perfil.energia_mev, perfil.corriente_ua,
            perfil.tiempo_min, perfil.reaccion_id, perfil.blanco_id)
    except CiclotronInvalido as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    energia_blanco = perfil.energia_mev
    resp = dict(irradiacion_id=irr.irradiacion_id,
                ciclotron_id=ciclotron_id,
                perfil_id=perfil.perfil_id, perfil_version=perfil.version,
                energia_mev=perfil.energia_mev,
                corriente_ua=perfil.corriente_ua,
                tiempo_min=perfil.tiempo_min,
                potencia_haz_w=round(
                    perfil.energia_mev * perfil.corriente_ua, 1),
                haz=dict(forma=perfil.haz.forma, sigma_cm=perfil.haz.sigma_cm,
                         notas=perfil.haz.notas))
    if perfil.ventana is not None:
        if _pstar is None:
            raise HTTPException(503, "tablas PSTAR no configuradas — "
                                     "degradación no demostrable")
        try:
            energia_blanco = _pstar.degradar(
                perfil.ventana.material, perfil.ventana.espesor_g_cm2,
                perfil.energia_mev)
        except (VentanaInvalida, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        resp["ventana"] = dict(
            material=perfil.ventana.material,
            espesor_g_cm2=perfil.ventana.espesor_g_cm2,
            descripcion=perfil.ventana.descripcion,
            energia_en_blanco_mev=round(energia_blanco, 3),
            perdida_mev=round(perfil.energia_mev - energia_blanco, 3),
            fuente=_pstar.source_label(), supuesto_declarado=True)
        resp["nota_honestidad"] = NOTA_DEGRADACION
    else:
        resp["nota_honestidad"] = NOTA_COTA_SUPERIOR

    try:
        r = _service.compute(
            reaction_id=perfil.reaccion_id, target_id=perfil.blanco_id,
            beam_energy_mev=energia_blanco, current_ua=perfil.corriente_ua,
            irradiation_time_min=perfil.tiempo_min)
        resp["eob"] = dict(
            eob_activity_gbq=round(r.eob_activity_gbq, 3),
            eob_uncertainty_gbq=round(
                r.eob_activity_gbq * r.relative_uncertainty, 3),
            saturation_factor=round(r.saturation_factor, 5),
            dataset_id=r.dataset_id, stopping_source=r.stopping_source)
    except ValueError as exc:
        resp["eob"] = {"no_demostrable": True, "motivo": str(exc)}
    return resp


# ------------------------------------- FEM térmico con h registrada (8.11)
class ThermalIn(BaseModel):
    energia_mev: float = Field(gt=0)
    corriente_ua: float = Field(gt=0)
    spot_radius_cm: float = 1.5
    target_thickness_cm: float = 0.9
    conductivity_w_cm_k: float = 0.006
    coolant_temp_k: float = 293.15
    beam_sigma_cm: float = 0.5


@router.post("/targets/{blanco_id}/thermal")
def termico_con_h_registrada(blanco_id: str, body: ThermalIn):
    """FEM térmico con la h de la configuración de enfriamiento VIGENTE.

    Sin configuración registrada → 404 no_demostrable (nunca se asume h);
    sin runtime Elmer → 503 honesto (nunca se estima la temperatura).
    """
    try:
        cool = _cooling.vigente(blanco_id)
    except CoolingInvalido as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    try:
        r = _service.thermal_fem(
            beam_power_w=body.energia_mev * body.corriente_ua,
            spot_radius_cm=body.spot_radius_cm,
            target_thickness_cm=body.target_thickness_cm,
            conductivity_w_cm_k=body.conductivity_w_cm_k,
            film_coeff_w_cm2_k=cool.h_w_cm2_k,
            coolant_temp_k=body.coolant_temp_k,
            beam_sigma_cm=body.beam_sigma_cm)
    except ElmerUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ElmerError as exc:
        raise HTTPException(status_code=500,
                            detail=f"fallo real del solver: {exc}")
    return {**r, "blanco_id": blanco_id, "cooling_config_id": cool.config_id,
            "cooling_version": cool.version, "cooling_fuente": cool.fuente,
            "potencia_haz_w": round(body.energia_mev * body.corriente_ua, 1)}
