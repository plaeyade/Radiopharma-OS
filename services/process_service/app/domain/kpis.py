"""Indicadores operativos (Informe 18.9; KPI Generator 38.12/27.10).

KPIs del Operational Twin calculados sobre los registros reales del
sistema (lotes de inventario, resultados QC, costeos). Las
definiciones son versionadas (gestión documental): cada KPI declara
su fórmula y su versión.
"""
from __future__ import annotations

from datetime import datetime, timezone

KPI_VERSION = "kpi-ops-1.0.0"


def kpis_operativos(lotes: list[dict], resultados_qc: list[dict],
                    costeos: list[dict]) -> dict:
    """Indicadores operativos de planta.

    - tasa_liberacion_qc: lotes con recomendación 'liberacion' /
      lotes evaluados (QC Release, cap. 25.12);
    - rendimiento_medio_gbq: actividad media registrada por lote;
    - lotes_activos: disponibles + reservados;
    - coste_medio_dosis (si hay costeos, 38.12).
    """
    n_qc = len(resultados_qc)
    liberados = sum(1 for r in resultados_qc
                    if r.get("recomendacion") == "liberacion")
    activos = sum(1 for l in lotes
                  if l.get("estado") in ("disponible", "reservado"))
    actividades = [l.get("actividad_gbq", 0.0) for l in lotes]
    kpis: dict = {
        "version_definiciones": KPI_VERSION,
        "fecha": datetime.now(timezone.utc).isoformat(),
        "lotes_registrados": len(lotes),
        "lotes_activos": activos,
        "tasa_liberacion_qc": round(liberados / n_qc, 4) if n_qc else None,
        "lotes_qc_evaluados": n_qc,
        "actividad_media_gbq": (round(sum(actividades) / len(actividades), 4)
                                if actividades else None),
    }
    if costeos:
        total = sum(c.get("coste_total", 0.0) for c in costeos)
        dosis = sum(c.get("dosis", 0) for c in costeos)
        kpis["coste_medio_dosis"] = (round(total / dosis, 2)
                                     if dosis else None)
        kpis["coste_total_periodo"] = round(total, 2)
    kpis["nota"] = ("KPIs calculados sobre registros reales del sistema; "
                    "definiciones versionadas (38.12)")
    return kpis
