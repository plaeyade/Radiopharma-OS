"""API del catálogo de equipamiento y capacidades (Fase 30)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...domain import equipment_catalog as ec
from ...domain import production_capacity as pc

router = APIRouter(prefix="/api/v1/equipamiento", tags=["equipamiento"])


class CapacidadIn(BaseModel):
    ciclotron_id: str
    corriente: float
    tiempo: float  # min para F-18/N-13, h para Cu-64


@router.get("/ciclotrones")
def ciclotrones():
    return ec.CICLOTRONES_EXT


@router.get("/modulos-sintesis")
def modulos():
    return ec.MODULOS_SINTESIS


@router.get("/kits")
def kits():
    return ec.KITS_RADIOQUIMICA


@router.get("/blancos/materiales")
def materiales():
    return ec.MATERIALES_BLANCO


@router.get("/blancos/tipos")
def tipos():
    return ec.TIPOS_BLANCO


@router.get("/blancos/estatus/{estatus}")
def estatus(estatus: str):
    try:
        return {"estatus": estatus, "resultado": ec.validar_estatus_proveedor(estatus)}
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/fuentes-iones")
def fuentes():
    return ec.FUENTES_IONES


@router.get("/fuentes-iones/{fuente_id}/optimizacion")
def optimizacion(fuente_id: str):
    try:
        return ec.recomendacion_fuente_iones(fuente_id)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.post("/capacidad/f18")
def cap_f18(body: CapacidadIn):
    try:
        return pc.capacidad_f18(body.ciclotron_id, body.corriente, body.tiempo)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.post("/capacidad/n13")
def cap_n13(body: CapacidadIn):
    try:
        return pc.capacidad_n13(body.ciclotron_id, body.corriente, body.tiempo)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.post("/capacidad/cu64")
def cap_cu64(body: CapacidadIn):
    try:
        return pc.capacidad_cu64(body.ciclotron_id, body.corriente, body.tiempo)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/capacidad/tablero")
def tablero():
    return pc.tablero_capacidades()
