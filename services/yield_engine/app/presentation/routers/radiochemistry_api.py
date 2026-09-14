"""API REST de modelado radioquímico (Informe 19.14).

Procesos post-EOB versionados (síntesis → transferencia → purificación →
formulación), cada etapa con eficiencia registrada SOLO con fuente
citada (ficha técnica real del proveedor o literatura especializada).
Los procesos pueden vincularse a un módulo de síntesis del catálogo
(IBA Synthera, Trasis AllinOne, GE FASTlab 2, …). La actividad al EOS
usa la λ REAL del núclido desde la biblioteca nuclear configurada —
nunca un valor tecleado ni inventado. Endpoint por lote para estimación
multiisótopo (F-18, Ga-68, C-11, O-15 según biblioteca).
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.application.production_service import ProductionService
from app.domain.radiochemistry import (EtapaRadioquimica, ProcesoInvalido,
                                       ProcesoRadioquimicoRegistry,
                                       actividad_eos)
from app.domain.synthesis_module import (ModuloInvalido,
                                         ModuloSintesisRegistry)

router = APIRouter(prefix="/api/v1/radiochemistry", tags=["radiochemistry"])

_service: ProductionService | None = None
_procesos: ProcesoRadioquimicoRegistry | None = None
_modulos: ModuloSintesisRegistry | None = None


def init(service: ProductionService,
         procesos: ProcesoRadioquimicoRegistry,
         modulos: ModuloSintesisRegistry | None = None) -> None:
    global _service, _procesos, _modulos
    _service, _procesos, _modulos = service, procesos, modulos


class EtapaIn(BaseModel):
    tipo: str
    nombre: str
    eficiencia: float
    duracion_min: float
    fuente: str


class ProcesoIn(BaseModel):
    producto: str
    nucleido: str
    etapas: list[EtapaIn]
    registrado_por: str
    motivo_version: str = "registro inicial"
    modulo_id: str | None = None


class EosIn(BaseModel):
    proceso_id: str
    eob_gbq: float
    version: int | None = None


class EosLoteIn(BaseModel):
    items: list[EosIn]


def _proceso_dict(p) -> dict:
    d = asdict(p)
    d["etapas"] = [asdict(e) for e in p.etapas]
    return d


def _calcular_eos(body: EosIn) -> dict:
    """A_EOS = A_EOB · Π(eficiencias) · exp(−λ·t_total) — 19.14."""
    p = _procesos.obtener(body.proceso_id, version=body.version)
    lam = _service.decay_constant_s(p.nucleido)   # λ real de la biblioteca
    resultado = actividad_eos(p, body.eob_gbq, lam)
    resultado["lambda_s"] = lam
    resultado["fuente_lambda"] = "biblioteca nuclear configurada (real)"
    return resultado


@router.post("/processes", status_code=201)
def registrar_proceso(body: ProcesoIn):
    assert _procesos is not None
    if body.modulo_id is not None:
        assert _modulos is not None
        try:
            mod = _modulos.obtener(body.modulo_id)
        except ModuloInvalido as exc:
            raise HTTPException(422, str(exc)) from exc
        if body.nucleido.strip() not in mod.nucleidos_soportados:
            raise HTTPException(
                422, f"el módulo {body.modulo_id} "
                f"({mod.fabricante} {mod.modelo}) no declara soporte para "
                f"{body.nucleido} — soportados: {list(mod.nucleidos_soportados)}")
    etapas = [EtapaRadioquimica(**e.model_dump()) for e in body.etapas]
    try:
        p = _procesos.registrar(
            producto=body.producto, nucleido=body.nucleido, etapas=etapas,
            registrado_por=body.registrado_por,
            motivo_version=body.motivo_version, modulo_id=body.modulo_id)
        return _proceso_dict(p)
    except ProcesoInvalido as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/processes")
def listar_procesos():
    assert _procesos is not None
    return {"procesos": [_proceso_dict(p) for p in _procesos.listar()]}


@router.get("/processes/{proceso_id}")
def obtener_proceso(proceso_id: str, version: int | None = None):
    assert _procesos is not None
    try:
        return _proceso_dict(_procesos.obtener(proceso_id, version=version))
    except ProcesoInvalido as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/processes/{proceso_id}/versions")
def versiones_proceso(proceso_id: str):
    assert _procesos is not None
    try:
        return {"versiones": [_proceso_dict(p)
                              for p in _procesos.versiones(proceso_id)]}
    except ProcesoInvalido as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/eos")
def calcular_eos(body: EosIn):
    assert _procesos is not None and _service is not None
    try:
        return _calcular_eos(body)
    except ProcesoInvalido as exc:
        msg = str(exc)
        raise HTTPException(404 if "desconocido" in msg or "inexistente" in msg
                            else 422, msg) from exc


@router.post("/eos/batch")
def calcular_eos_lote(body: EosLoteIn):
    """EOS multiisótopo: cada ítem usa la λ REAL de su núclido.

    Los errores por ítem se reportan aislados — un proceso inválido no
    contamina el resto del lote (honestidad por ítem).
    """
    assert _procesos is not None and _service is not None
    resultados, errores = [], []
    for item in body.items:
        try:
            resultados.append(_calcular_eos(item))
        except ProcesoInvalido as exc:
            errores.append({"proceso_id": item.proceso_id,
                            "error": str(exc)})
    return {"resultados": resultados, "errores": errores,
            "nota_honestidad": (
                "estimaciones teóricas 19.14 con λ de la biblioteca "
                "nuclear por núclido — nunca valores medidos de producción")}


# -------------------------------------- catálogo de módulos de síntesis
class ModuloIn(BaseModel):
    fabricante: str
    modelo: str
    nucleidos_soportados: list[str]
    fuente: str                     # ficha técnica o literatura citada
    registrado_por: str
    motivo_version: str = "registro inicial"


@router.post("/modules", status_code=201)
def registrar_modulo(body: ModuloIn):
    assert _modulos is not None
    try:
        return asdict(_modulos.registrar(**body.model_dump()))
    except ModuloInvalido as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/modules")
def listar_modulos():
    assert _modulos is not None
    return {"modulos": [asdict(m) for m in _modulos.listar()]}


@router.get("/modules/{modulo_id}")
def obtener_modulo(modulo_id: str):
    assert _modulos is not None
    try:
        return asdict(_modulos.obtener(modulo_id))
    except ModuloInvalido as exc:
        raise HTTPException(404, str(exc)) from exc
