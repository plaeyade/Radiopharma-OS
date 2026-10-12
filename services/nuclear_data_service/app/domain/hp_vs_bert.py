# -*- coding: utf-8 -*-
"""Comparación HP vs BERT del tally del búnker — Fase 37.

Compara el mapa de fluencia del MISMO caso de búnker (misma geometría,
mismo espectro TALYS real, mismo mesh 110×110×60) corrido con dos
listas de física distintas:

- FTFP_BERT      (Fase 32/35): cascada Bertini + tratamiento térmico
                 genérico (gas libre).
- FTFP_BERT_HP   (Fase 37): secciones eficaces medidas isótopo a
                 isótopo de G4NDL 4.7.1 para n < 20 MeV, incluido el
                 régimen térmico (Capture/Elastic/Inelastic +
                 ThermalScattering del propio G4NDL).

Por qué importa (declarado): la activación de muros (Co-60, Eu-152,
Na-24) está dominada por capturas térmicas (n,γ) cuya sección eficaz
crece ∝ 1/v; el modelo de gas libre de BERT no reproduce las
secciones térmicas medidas. HP es por tanto la referencia física más
fiel disponible sin licencias externas.

REGLA CANÓNICA: la comparación usa SOLO tallies reales corridos en
esta plataforma. Si falta alguno, estado=no_demostrable y se dice así.
Nunca se fabrica una "diferencia esperada" de literatura.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.domain.fluence_connector import leer_tally_mhd


@dataclass(frozen=True)
class ComparacionHpBert:
    phi_media_bert: float
    phi_media_hp: float
    phi_max_bert: float
    phi_max_hp: float
    delta_rel_media: float          # (HP − BERT)/BERT sobre la media de muros
    delta_rel_max: float
    voxels_comunes: int             # activos en AMBOS mapas
    dif_rel_mediana_voxel: float | None   # mediana de |HP−BERT|/media por voxel común
    estado: str                     # comparacion_real | no_demostrable
    nota: str


def comparar_tallies(ruta_bert: str, ruta_hp: str) -> ComparacionHpBert:
    """Compara dos tallies .mhd (misma geometría de malla obligatoria).

    Métricas declaradas:
    - φ media/máx sobre voxels activos de cada mapa (criterio idéntico
      al de Fase 35 para no cambiar el estimador entre fases).
    - Δ_rel media y máx: (HP − BERT)/BERT.
    - Sobre voxels activos en AMBOS: mediana de la diferencia relativa
      simétrica |HP − BERT| / ((HP + BERT)/2) — robusta a outliers de
      1 cuenta.
    """
    cb = leer_tally_mhd(ruta_bert)["counts"]
    ch = leer_tally_mhd(ruta_hp)["counts"]
    if cb.shape != ch.shape:
        return ComparacionHpBert(
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, None,
            "no_demostrable",
            f"mallas distintas {cb.shape} vs {ch.shape} — comparación imposible",
        )
    ab = cb[cb > 0]
    ah = ch[ch > 0]
    if ab.size == 0 or ah.size == 0:
        return ComparacionHpBert(
            float(ab.mean()) if ab.size else 0.0,
            float(ah.mean()) if ah.size else 0.0,
            0.0, 0.0, 0.0, 0.0, 0, None,
            "no_demostrable",
            "uno de los mapas no tiene voxels activos",
        )
    mb, mh = float(ab.mean()), float(ah.mean())
    xb, xh = float(ab.max()), float(ah.max())
    comun = (cb > 0) & (ch > 0)
    n_comun = int(comun.sum())
    mediana = None
    if n_comun > 0:
        vb = cb[comun].astype(float)
        vh = ch[comun].astype(float)
        dif = np.abs(vh - vb) / ((vh + vb) / 2.0)
        mediana = float(np.median(dif))
    return ComparacionHpBert(
        mb, mh, xb, xh,
        (mh - mb) / mb if mb else 0.0,
        (xh - xb) / xb if xb else 0.0,
        n_comun, mediana,
        "comparacion_real",
        "misma malla; Δ_rel sobre medias de voxels activos; mediana "
        "voxel a voxel con denominador simétrico",
    )
