"""API REST de los conectores nucleares EXFOR/SRIM/NNDC (19.10-19.13)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...domain.nuclear_connectors import (
    CONNECTORS_VERSION,
    FuenteInvalida,
    NuclearDataConnectors,
    SinFuente,
)

router = APIRouter(prefix="/api/v1/connectors", tags=["nuclear-connectors"])

_connector: NuclearDataConnectors | None = None


def init(connector: NuclearDataConnectors | None = None, **kwargs) -> None:
    global _connector
    _connector = connector or NuclearDataConnectors(**kwargs)


def _con() -> NuclearDataConnectors:
    if _connector is None:
        init()
    return _connector  # type: ignore[return-value]


def _guard(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except SinFuente as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except FuenteInvalida as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError as exc:  # BibliotecaInvalida y dominio
        raise HTTPException(status_code=422, detail=str(exc))


class FuenteIn(BaseModel):
    fuente_id: str
    tipo: str
    endpoint: str
    responsable: str


class ExforIn(BaseModel):
    nuclide: str
    ruta_consulta: str
    autor: str


class SrimIn(BaseModel):
    material: str
    archivo: str
    autor: str


@router.post("/sources", status_code=201)
def registrar_fuente(body: FuenteIn):
    f = _guard(_con().registrar_fuente, body.fuente_id, body.tipo,
               body.endpoint, body.responsable)
    return {"fuente_id": f.fuente_id, "version": f.version}


@router.get("/sources")
def fuentes():
    return _con().fuentes()


@router.get("/sources/{fuente_id}/history")
def historial(fuente_id: str):
    return _con().historial_fuente(fuente_id)


@router.post("/sources/{fuente_id}/probe")
def sondear(fuente_id: str, actor: str = "sistema"):
    return _guard(_con().sondear, fuente_id, actor)


@router.post("/sources/{fuente_id}/exfor/import", status_code=201)
def importar_exfor(fuente_id: str, body: ExforIn):
    return _guard(_con().importar_exfor, fuente_id, body.nuclide,
                  body.ruta_consulta, body.autor)


@router.post("/sources/{fuente_id}/srim/import", status_code=201)
def importar_srim(fuente_id: str, body: SrimIn):
    return _guard(_con().importar_srim, fuente_id, body.material,
                  body.archivo, body.autor)


@router.get("/srim/{material}")
def tablas_srim(material: str):
    return _con().tablas_srim(material)


@router.get("/sources/{fuente_id}/nndc/{nuclide}")
def consultar_nndc(fuente_id: str, nuclide: str, actor: str = "sistema"):
    return _guard(_con().consultar_nndc, fuente_id, nuclide, actor)


@router.get("/status")
def estado():
    return _con().estado_integraciones()


@router.get("/audit")
def auditoria():
    return _con().auditoria()


@router.get("/meta")
def meta():
    return {"version_motor": CONNECTORS_VERSION,
            "tipos_fuente": ["exfor", "srim", "nndc"],
            "nota": ("EXFOR 19.12 (prioridad experimental), SRIM 19.10 "
                     "(tablas reales con hash), NNDC 19.13 (constantes); "
                     "sin conexión viva → 503 honesto.")}
