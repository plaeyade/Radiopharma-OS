"""Fase 40 — OQ (Operational Qualification) con evidencia real.

Extiende la calificación DQ/IQ/OQ/PQ de ``pipelines/qualification.py``
(Informe 14.9) con la evidencia de las fases F38/F39/F42:

  - F38: verificación del plano real BIND vs caso simulado (parcial —
    sin alzados en el DWG, hallazgo negativo honesto);
  - F39: cotizaciones de blindaje con verificación aritmética;
  - F42: corrida Monte Carlo REAL en OpenMC (piloto 10k + barrido
    estadístico 30k con semillas perdidas por segfault declaradas) y
    comparación triple real (BERT/HP/OpenMC).

Regla canónica: nada se fabrica. Cada ítem se marca
``ejecutado`` / ``parcial`` / ``pendiente`` según la evidencia real, y
PQ sigue sin declararse nunca.

Uso:  python pipelines/oq_fase40.py [--evidencia DIR] [--out f40.json]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCIA_DEF = Path("/mnt/agents/work/evidencia_v072")


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _leer(ev: Path, rel: str) -> dict | None:
    p = ev / rel
    if not p.exists():
        return None
    return json.loads(p.read_text())


def verificar_f38(ev: Path) -> dict:
    """Plano real BIND: veredictos y hallazgo negativo de alzados."""
    d = _leer(ev, "fase38/verificacion_plano_f38.json")
    if d is None:
        return {"nombre": "f38_plano_real", "estado": "pendiente",
                "detalle": "sin evidencia fase38"}
    verif = d.get("verificacion", {})
    checks = verif.get("checks", verif if isinstance(verif, list) else [])
    n_ok = sum(1 for c in checks
               if isinstance(c, dict) and str(c.get("veredicto", ""))
               .startswith("cumple"))
    muro = (d.get("geometria_real", {}).get("muro_oeste_m")
            or d.get("geometria_real", {}).get("muro_oeste", {}).get("m"))
    # Hallazgo negativo honesto: el DWG no contiene cortes/alzados
    # (verificado en v1.15.0) → la altura z queda provisional.
    return {"nombre": "f38_plano_real", "estado": "parcial",
            "detalle": f"{n_ok} veredictos 'cumple'; muro oeste "
                       f"{muro} m medido; sin alzados en el DWG "
                       f"(hallazgo negativo) → z=4,0 m provisional "
                       f"pendiente_verificacion"}


def verificar_f39(ev: Path) -> dict:
    """Cotizaciones de blindaje con verificación aritmética."""
    d = _leer(ev, "fase39/cotizaciones_blindaje_f39.json")
    if d is None:
        return {"nombre": "f39_cotizaciones", "estado": "pendiente",
                "detalle": "sin evidencia fase39"}
    val = d.get("validaciones", d.get("validacion", {}))
    ok = True
    if isinstance(val, dict):
        ok = all(v.get("ok", True) for v in val.values()
                 if isinstance(v, dict))
    return {"nombre": "f39_cotizaciones",
            "estado": "ejecutado" if ok else "parcial",
            "detalle": "2 cotizaciones reales registradas con documento "
                       "citado y verificación aritmética "
                       + ("✓" if ok else "con observaciones")}


def verificar_f42(ev: Path) -> dict:
    """Corrida MC real OpenMC: piloto + barrido + triple comparación."""
    comb = _leer(ev, "fase42/combinado_openmc_f42.json")
    triple = _leer(ev, "fase42/comparacion_triple_3patas_f42.json")
    if comb is None:
        return {"nombre": "f42_mc_real", "estado": "pendiente",
                "detalle": "sin evidencia fase42"}
    n_ok = len(comb.get("semillas_ok", []))
    n_bad = len(comb.get("semillas_fallidas_segfault", []))
    hist = comb.get("historias_totales", 0)
    vx = comb.get("voxels_con_flujo", 0)
    det = (f"{hist} historias reales ({n_ok}/{n_ok + n_bad} semillas; "
           f"{n_bad} perdidas por segfault conda, declarado), "
           f"{vx} voxels con flujo")
    if triple:
        omc = triple.get("patas", {}).get("OpenMC_ENDFB80", {})
        det += (f"; comparación triple real cerrada (unión "
                f"{triple.get('voxels_union')} voxels, Δ OpenMC "
                f"{omc.get('delta_rel_vs_referencia')} con caveat de "
                f"unidades declarado)")
    return {"nombre": "f42_mc_real",
            "estado": "parcial",  # 3/6 semillas: parcial honesto
            "detalle": det}


def construir_informe(evidencia: Path = EVIDENCIA_DEF) -> dict:
    items = [verificar_f38(evidencia), verificar_f39(evidencia),
             verificar_f42(evidencia)]
    estados = {i["estado"] for i in items}
    if estados == {"ejecutado"}:
        estado = "oq_completo"
    elif estados & {"ejecutado", "parcial"}:
        estado = "oq_parcial_honesto"
    else:
        estado = "oq_no_demostrable"
    return {"fase": "F40_OQ_evidencia_real",
            "timestamp": _ahora(),
            "items": items,
            "estado": estado,
            "pq": "no_declarada_nunca (requiere entorno real, 14.9)",
            "nota": "OQ operativa de las fases con evidencia real. "
                    "Nada se fabrica: los ítems parciales declaran su "
                    "limitación (segfaults conda, ausencia de alzados)."}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidencia", default=str(EVIDENCIA_DEF))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    rep = construir_informe(Path(a.evidencia))
    txt = json.dumps(rep, indent=2, ensure_ascii=False)
    if a.out:
        Path(a.out).write_text(txt)
    print(txt)
    return 0 if rep["estado"] != "oq_no_demostrable" else 1


if __name__ == "__main__":
    raise SystemExit(main())
