"""Exporta el JSON de datos REALES para render_target_blender.py (Fase 34).

Combina tres fuentes canónicas, todas reales o declaradas con marcador:
  1. GDML del blanco seleccionable (gdml_target.info_gdml) — geometría y
     materiales del catálogo de blancos (target_selector, Fase 32).
  2. Haz primario parametrizado (beam_model.haz_desde_ciclotron) — energía
     citada por modelo de ciclotrón; perfil/divergencia declarados
     pendientes de medición con haz real (nunca bloquear).
  3. Espectro de neutrones TALYS real (nspec_*.tot, Fase 32) — energía
     media del espectro, calculada del archivo YANDF-0.4, nunca inventada.

REGLA CANÓNICA: el JSON solo contiene datos trazables. Si falta el
espectro o el blanco, el script aborta (no_demostrable), no rellena.

Uso:
    python3 scripts/export_target_render_data.py \
        --blanco agua18_ag_estandar --ciclotron ge_pettrace_890 \
        --corriente-ua 60 --nspec evidencia/nspec_o18.tot \
        --salida render_data_f18.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services" / "yield_engine"))

from app.domain.beam_model import haz_desde_ciclotron  # noqa: E402
from app.infrastructure.gate.gdml_target import info_gdml  # noqa: E402


def energia_media_nspec(path: Path) -> dict:
    """E media de un nspec TALYS (columnas E-out y xs; salta comentarios #)."""
    e, xs = [], []
    for linea in path.read_text().splitlines():
        s = linea.strip()
        if not s or s.startswith("#"):
            continue
        partes = s.split()
        if len(partes) >= 2:
            try:
                e.append(float(partes[0]))
                xs.append(float(partes[1]))
            except ValueError:
                continue
    if not e or sum(xs) <= 0:
        raise SystemExit(f"no_demostrable: espectro vacío o inválido en {path}")
    e_media = sum(a * b for a, b in zip(e, xs)) / sum(xs)
    return {
        "archivo": str(path),
        "bins": len(e),
        "e_media_mev": round(e_media, 3),
        "e_max_mev": round(max(e), 3),
        "origen": "talys_corrida_real",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--blanco", required=True)
    p.add_argument("--ciclotron", required=True)
    p.add_argument("--corriente-ua", type=float, required=True)
    p.add_argument("--nspec", required=True, type=Path)
    p.add_argument("--salida", required=True, type=Path)
    p.add_argument("--isotopo", required=True, help="Etiqueta, p.ej. F-18")
    a = p.parse_args()

    if not a.nspec.exists():
        raise SystemExit(f"no_demostrable: falta espectro {a.nspec}")

    info = info_gdml(a.blanco)
    haz = haz_desde_ciclotron(a.ciclotron, a.corriente_ua)
    espec = energia_media_nspec(a.nspec)

    datos = {
        "isotopo": a.isotopo,
        "blanco_id": a.blanco,
        "geometria_gdml": {
            "radio_mm": info.radio_mm,
            "espesor_mm": info.espesor_mm,
            "material_cuerpo": info.material_cuerpo,
            "densidad_contenido_g_cm3": info.densidad_contenido,
            "foil_havar_um": 25.0,
            "marcadores": list(info.marcadores),
        },
        "haz": {
            "ciclotron_id": haz.ciclotron_id,
            "energia_mev": haz.energia_mev,
            "corriente_ua": haz.corriente_ua,
            "potencia_haz_w": haz.potencia_haz_w(),
            "sigma_mm": haz.sigma_mm,
            "divergencia_mrad": haz.divergencia_mrad,
            "densidad_pico_w_mm2": haz.densidad_pico_w_mm2(),
            "fuente_energia": haz.fuente_energia,
            "marcador_perfil": haz.marcador_perfil,
        },
        "espectro_neutrones": espec,
        "regla": "render de comunicación: la física proviene de TALYS/GDML reales; el render nunca genera física",
    }
    a.salida.write_text(json.dumps(datos, indent=2, ensure_ascii=False))
    print(f"OK {a.salida}  E_media={espec['e_media_mev']} MeV  P={datos['haz']['potencia_haz_w']:.0f} W")


if __name__ == "__main__":
    main()
