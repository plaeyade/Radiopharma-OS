"""Economic Digital Twin: costeo ABC e indicadores (caps. 38-39).

Cost Engine (38.6) con costeo basado en actividades (cap. 39):
  - Activity Manager (39.6): actividades versionadas de la producción
    (irradiación, síntesis, purificación, formulación, QC, logística);
  - Resource Consumption / Cost Drivers (39.7/39.8): cada actividad
    consume recursos con driver propio (horas de ciclotrón, minutos de
    módulo, ensayos QC, ml de reactivo);
  - Cost Allocation (39.9): el coste del lote es la suma de actividades
    consumidas — sin prorrateos arbitrarios;
  - costes por lote (38.8/39.11), por dosis (39.12) y por radiofármaco
    (39.13); Revenue Engine (38.7) y KPI Generator (38.12).

El catálogo de costes es un dato versionado (gestión documental
38.20): los precios nunca están embebidos en el código.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


class EconomiaInvalida(ValueError):
    """Catálogo o consumo que viola las reglas de costeo."""


@dataclass(frozen=True)
class ActividadCoste:
    """Actividad ABC con driver y tarifa (39.6-39.8)."""
    actividad: str          # irradiacion/sintesis/purificacion/formulacion/qc/logistica
    driver: str             # hora_ciclotron / min_modulo / ensayo / ml / envio
    tarifa: float           # coste por unidad de driver
    moneda: str = "EUR"


@dataclass
class CostCatalog:
    catalog_id: str
    version: str
    moneda: str
    actividades: dict[str, ActividadCoste]
    fuente: str
    validado: bool = False


@dataclass
class ConsumoActividad:
    actividad: str
    unidades_driver: float


@dataclass
class BatchCostResult:
    lote_id: str
    radiopharmaceutical: str
    catalog_id: str
    catalog_version: str
    desglose: dict[str, float]
    coste_total: float
    dosis: int
    coste_por_dosis: float          # 39.12
    actividad_eob_gbq: float
    coste_por_gbq: float
    moneda: str
    auditoria: dict


def cargar_catalogo(path: str | Path) -> CostCatalog:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    acts = {k: ActividadCoste(**v) for k, v in raw["actividades"].items()}
    return CostCatalog(catalog_id=raw["catalog_id"], version=raw["version"],
                       moneda=raw.get("moneda", "EUR"), actividades=acts,
                       fuente=raw["fuente"],
                       validado=bool(raw.get("validado", False)))


def costear_lote(catalog: CostCatalog, lote_id: str,
                 radiopharmaceutical: str,
                 consumos: list[ConsumoActividad],
                 dosis: int, actividad_eob_gbq: float,
                 operador: str, motivo: str) -> BatchCostResult:
    """Costeo ABC del lote (39.9-39.12)."""
    if dosis <= 0 or actividad_eob_gbq <= 0:
        raise EconomiaInvalida("dosis y actividad EOB deben ser > 0")
    desglose: dict[str, float] = {}
    for c in consumos:
        if c.actividad not in catalog.actividades:
            raise EconomiaInvalida(
                f"actividad no registrada en el catálogo "
                f"{catalog.catalog_id} v{catalog.version}: {c.actividad}")
        if c.unidades_driver < 0:
            raise EconomiaInvalida("unidades de driver negativas")
        tarifa = catalog.actividades[c.actividad].tarifa
        desglose[c.actividad] = round(
            desglose.get(c.actividad, 0.0) + tarifa * c.unidades_driver, 2)
    if not desglose:
        raise EconomiaInvalida("lote sin consumo de actividades (39.7)")
    total = round(sum(desglose.values()), 2)
    return BatchCostResult(
        lote_id=lote_id, radiopharmaceutical=radiopharmaceutical,
        catalog_id=catalog.catalog_id, catalog_version=catalog.version,
        desglose=desglose, coste_total=total, dosis=dosis,
        coste_por_dosis=round(total / dosis, 2),
        actividad_eob_gbq=actividad_eob_gbq,
        coste_por_gbq=round(total / actividad_eob_gbq, 2),
        moneda=catalog.moneda,
        auditoria={"fecha": datetime.now(timezone.utc).isoformat(),
                   "operador": operador, "motivo": motivo,
                   "fuente_tarifas": catalog.fuente,
                   "validado": catalog.validado,
                   "nota": "costeo ABC por actividades consumidas (39.9); "
                           "sin prorrateos arbitrarios"})


def coste_por_radiofarmaco(resultados: list[BatchCostResult],
                           radiopharmaceutical: str) -> dict:
    """Agregación por radiofármaco (38.9/39.13)."""
    sel = [r for r in resultados
           if r.radiopharmaceutical == radiopharmaceutical]
    if not sel:
        raise EconomiaInvalida(
            f"sin lotes costeados para {radiopharmaceutical}")
    total = sum(r.coste_total for r in sel)
    dosis = sum(r.dosis for r in sel)
    return {"radiopharmaceutical": radiopharmaceutical, "lotes": len(sel),
            "coste_total": round(total, 2), "dosis": dosis,
            "coste_medio_lote": round(total / len(sel), 2),
            "coste_medio_dosis": round(total / dosis, 2) if dosis else None,
            "moneda": sel[0].moneda}


def kpis_economicos(resultados: list[BatchCostResult],
                    precio_dosis: float | None = None) -> dict:
    """KPI Generator (38.12): margen y eficiencia de coste."""
    if not resultados:
        raise EconomiaInvalida("sin resultados de costeo")
    total = sum(r.coste_total for r in resultados)
    dosis = sum(r.dosis for r in resultados)
    gbq = sum(r.actividad_eob_gbq for r in resultados)
    kpis = {"lotes": len(resultados), "coste_total": round(total, 2),
            "coste_medio_dosis": round(total / dosis, 2) if dosis else None,
            "coste_medio_gbq": round(total / gbq, 2) if gbq else None,
            "moneda": resultados[0].moneda}
    if precio_dosis is not None and dosis:
        ingresos = precio_dosis * dosis  # Revenue Engine (38.7)
        kpis.update({"precio_dosis": precio_dosis, "ingresos": ingresos,
                     "margen": round(ingresos - total, 2),
                     "margen_pct": round(100.0 * (ingresos - total) / ingresos,
                                         2)})
    return kpis
