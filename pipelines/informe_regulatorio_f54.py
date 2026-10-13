"""F54 — Informe regulatorio integrado (expediente as-built).

Reglas canónicas aplicadas:
- SOLO lectura de evidencia real ya registrada (append-only): nunca se recalcula
  ni se inventa un dato; lo que falta se declara pendiente_*.
- Recomendación ≠ decisión operacional (18.10).
- Toda magnitud lleva su fuente (49.11) heredada del JSON de fase.
- PQ nunca declarada (14.9): requiere entorno real.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

EVIDENCIA_DEF = Path("/mnt/agents/work/evidencia_v072")

# (clave_seccion, ruta_json_relativa, fase_origen)
SECCIONES = [
    ("geometria_plano_f38", "fase38/verificacion_plano_f38.json", "F38"),
    ("cotizaciones_blindaje_f39", "fase39/cotizaciones_blindaje_f39.json", "F39"),
    ("oq_f40", "fase40/informe_oq_f40.json", "F40"),
    ("mc_oiea_f42", "fase42/combinado_openmc_f42.json", "F42"),
    ("mc_bind_real_f42b", "fase42b/combinado_bind_f42b.json", "F42b"),
    ("blindaje_asbuilt_f51", "fase51/blindaje_asbuilt_f51.json", "F51"),
    ("dosis_asbuilt_f53", "fase53/dosis_asbuilt_f53.json", "F53"),
    ("sab_f52", "fase52/estado_sab_f52.json", "F52"),
]

ESTADOS_ABIERTOS = ("pendiente", "no_demostrable", "parcial")


def _cargar(evidencia: Path, rel: str) -> dict:
    p = evidencia / rel
    if not p.is_file():
        return {"estado": "pendiente_evidencia", "ruta": rel}
    return json.loads(p.read_text(encoding="utf-8"))


def _hallazgos_abiertos(sec: dict) -> list[str]:
    """Extrae honestamente los estados abiertos de cada sección."""
    hall: list[str] = []
    def rec(o, ruta=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "estado" and isinstance(v, str) and any(e in v for e in ESTADOS_ABIERTOS):
                    hall.append(f"{ruta}: {v}")
                else:
                    rec(v, f"{ruta}.{k}" if ruta else k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                rec(v, f"{ruta}[{i}]")
    rec(sec)
    return hall


def construir_informe(evidencia: Path = EVIDENCIA_DEF) -> dict:
    evidencia = Path(evidencia)
    secciones = {}
    hallazgos = []
    for clave, rel, fase in SECCIONES:
        datos = _cargar(evidencia, rel)
        secciones[clave] = {"fase": fase, "fuente": rel, "datos": datos}
        if datos.get("estado") == "pendiente_evidencia":
            hallazgos.append(f"{clave}: pendiente_evidencia ({rel})")
        else:
            hallazgos.extend(f"{clave} → {h}" for h in _hallazgos_abiertos(datos))

    # Síntesis cuantitativa SOLO con valores ya publicados en evidencia (49.11).
    sintesis = {}
    b = secciones["blindaje_asbuilt_f51"]["datos"]
    d = secciones["dosis_asbuilt_f53"]["datos"]
    if "transmision_muro_este" in b:
        sintesis["transmision_muro_este"] = b["transmision_muro_este"].get("valor")
    if "tvl_empirico" in b:
        sintesis["tvl_efectivo_m"] = b["tvl_empirico"].get("tvl_efectivo_m")
    esc = d.get("escenario_este", {})
    if esc:
        sintesis["dosis_tras_muro_usv_sem"] = esc.get("dosis_externa_usv_sem")
        sintesis["tvl_adicionales_requeridos"] = esc.get("tvl_adicionales_requeridos")

    estado = "expediente_integrado_honesto"
    return {
        "fase": "F54_informe_regulatorio_integrado",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "estado": estado,
        "secciones": secciones,
        "sintesis_citada": sintesis,
        "hallazgos_abiertos": sorted(set(hallazgos)),
        "pq": "no_declarada_nunca (requiere entorno real, 14.9)",
        "nota_1810": ("Este expediente integra evidencia; cualquier espesor o acción "
                      "derivada es RECOMENDACIÓN, no decisión operacional."),
    }


def main() -> int:
    inf = construir_informe()
    out = EVIDENCIA_DEF / "fase54"
    out.mkdir(parents=True, exist_ok=True)
    (out / "informe_regulatorio_f54.json").write_text(
        json.dumps(inf, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"secciones={len(inf['secciones'])} hallazgos_abiertos={len(inf['hallazgos_abiertos'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
