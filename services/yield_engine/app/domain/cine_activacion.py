# -*- coding: utf-8 -*-
"""Cine de activación por componente del búnker — Fase 45 (didáctico).

A partir del mesh tally REAL de fluencia (F35/F37, Geant4) se calcula la
actividad Bateman pulso a pulso por voxel (forma cerrada de la recurrencia
de ActivationEngine.actividad_tras_pulsos — misma física, vectorizada) y
se agrega por COMPONENTE del búnker (muros, losas, corona del laberinto),
con el isótopo predominante de cada régimen:

- hormigón, largo plazo: ¹⁵²Eu (de trazas de ¹⁵¹Eu) — culpable #1 de
  muros (catálogo CULPABLES, σ y T½ con fuente citada);
- hormigón, primeras horas tras apagar: ²⁴Na;
- referencia foil/componentes base cobalto: ⁶⁰Co.

Concentraciones de trazas en concreto: DECLARADAS pendientes de fuente
(concentracion_declarada_pendiente_fuente) — 1 ppm Co y 1 ppm Eu son
valores típicos de literatura; el concreto real exige análisis (F38/F39).
Na y demás elementos mayoritarios salen de la composición NIST citada
(G4_CONCRETE) — esos sí tienen fuente.

Nada de esto simula lecturas: la fluencia es MC real; las concentraciones
declaradas se etiquetan como tales en cada salida (honestidad 18.x/49.11).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

ANIO_S = 365.25 * 86400.0
NA = 6.02214076e23

# Composición NIST G4_CONCRETE (fracción en peso) — fuente: Geant4 NIST
NIST_CONCRETE_WO = {
    "H": 0.010000, "C": 0.001000, "O": 0.529107, "Na": 0.016000,
    "Mg": 0.002000, "Al": 0.033872, "Si": 0.337021, "K": 0.013000,
    "Ca": 0.044000, "Fe": 0.014000,
}
RHO_CONCRETE = 2.3  # g/cm³ (NIST)

# Isótopos del cine (del catálogo CULPABLES de activation.py — σ/T½ citadas)
ISOTOPOS_CINE = {
    "Eu-152": {"padre": "Eu-151", "sigma_b": 9051.0, "t12_s": 13.517 * ANIO_S,
               "abund_padre": 0.4781,  # abundancia 151Eu (CIAAW)
               "elemento": "Eu", "regimen": "largo_plazo"},
    "Co-60": {"padre": "Co-59", "sigma_b": 37.18, "t12_s": 5.2713 * ANIO_S,
              "abund_padre": 1.0,
              "elemento": "Co", "regimen": "largo_plazo"},
    "Na-24": {"padre": "Na-23", "sigma_b": 0.53, "t12_s": 14.959 * 3600.0,
              "abund_padre": 1.0,
              "elemento": "Na", "regimen": "primeras_horas"},
}
# ppm en peso DECLARADAS pendientes de fuente (trazas en concreto)
TRAZAS_PPM_DECLARADAS = {"Eu": 1.0, "Co": 1.0}
MASA_MOLAR = {"Eu": 151.964, "Co": 58.933, "Na": 22.990}  # g/mol (CIAAW)


@dataclass(frozen=True)
class ComponenteBunker:
    nombre: str
    descripcion: str


COMPONENTES = {
    "muro_laberinto": ComponenteBunker("muro_laberinto",
        "muro X+ atravesado por el laberinto (grosor real 3,0 m en X)"),
    "muro_oeste": ComponenteBunker("muro_oeste", "muro X− (3,0 m)"),
    "muro_norte": ComponenteBunker("muro_norte", "muro Y+ (2,0 m)"),
    "muro_sur": ComponenteBunker("muro_sur", "muro Y− (2,0 m)"),
    "losa_techo": ComponenteBunker("losa_techo", "losa superior (1,0 m)"),
    "losa_piso": ComponenteBunker("losa_piso", "losa inferior (1,0 m)"),
}


def mascara_componentes(dims=(110, 110, 60)) -> dict[str, np.ndarray]:
    """Máscaras por componente sobre la malla F35 (world 22×22×12 m,
    spacing 20 cm; bloque concreto x∈[−6,6] y∈[−5,5] z∈[−3,3] m;
    bóveda x,y∈[−3,3] z∈[−2,2] m; laberinto_1 x∈[3,6] y∈[−3,−1,8]
    z∈[−2,0,4] m). Índice i = (x_m + 11)/0,2."""
    nx, ny, nz = dims
    xs = (np.arange(nx) + 0.5) * 0.2 - 11.0
    ys = (np.arange(ny) + 0.5) * 0.2 - 11.0
    zs = (np.arange(nz) + 0.5) * 0.2 - 6.0
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")
    bloque = ((np.abs(X) <= 6.0) & (np.abs(Y) <= 5.0) & (np.abs(Z) <= 3.0))
    boveda = ((np.abs(X) < 3.0) & (np.abs(Y) < 3.0) & (np.abs(Z) < 2.0))
    lab1 = ((X >= 3.0) & (X <= 6.0) & (Y >= -3.0) & (Y <= -1.8)
            & (Z >= -2.0) & (Z <= 0.4))
    concreto = bloque & ~boveda & ~lab1
    m = {
        "muro_laberinto": concreto & (X >= 3.0),
        "muro_oeste": concreto & (X <= -3.0),
        "muro_norte": concreto & (np.abs(X) < 3.0) & (Y >= 3.0),
        "muro_sur": concreto & (np.abs(X) < 3.0) & (Y <= -3.0),
        "losa_techo": concreto & (np.abs(X) < 3.0) & (np.abs(Y) < 3.0)
                      & (Z >= 2.0),
        "losa_piso": concreto & (np.abs(X) < 3.0) & (np.abs(Y) < 3.0)
                     & (Z <= -2.0),
    }
    return m


def nucleos_padre_cm3(isotopo: str) -> tuple[float, str]:
    """Núcleos padre por cm³ de concreto + etiqueta de fuente honesta."""
    p = ISOTOPOS_CINE[isotopo]
    el = p["elemento"]
    if el in NIST_CONCRETE_WO:  # elemento mayoritario NIST — fuente citada
        w = NIST_CONCRETE_WO[el]
        fuente = "composicion_NIST_G4_CONCRETE (Geant4 NIST manager)"
    else:  # traza declarada pendiente de fuente
        w = TRAZAS_PPM_DECLARADAS[el] * 1e-6
        fuente = ("concentracion_declarada_pendiente_fuente "
                  f"({TRAZAS_PPM_DECLARADAS[el]} ppm típico literatura; "
                  "exige análisis del concreto real — F38/F39)")
    n = w * RHO_CONCRETE / MASA_MOLAR[el] * NA * p["abund_padre"]
    return n, fuente


def actividad_pulso(phi_voxel: np.ndarray, isotopo: str, k: int,
                    t_pulso_s: float, t_entre_pulsos_s: float,
                    v_voxel_cm3: float = 8000.0) -> np.ndarray:
    """Actividad [Bq] por voxel al final del pulso k — forma cerrada de la
    recurrencia exacta de ActivationEngine.actividad_tras_pulsos:
        a_k = g·(1−r^k)/(1−r),  r = e^{−λ(tp+te)},  g = Nσφ(1−e^{−λtp}).
    """
    if k <= 0:
        return np.zeros_like(phi_voxel)
    p = ISOTOPOS_CINE[isotopo]
    n_cm3, _ = nucleos_padre_cm3(isotopo)
    n_padre = n_cm3 * v_voxel_cm3
    lam = math.log(2.0) / p["t12_s"]
    g = n_padre * (p["sigma_b"] * 1e-24) * phi_voxel * (-math.expm1(-lam * t_pulso_s))
    r = math.exp(-lam * (t_pulso_s + t_entre_pulsos_s))
    if abs(1.0 - r) < 1e-12:
        return g * k
    return g * (1.0 - r ** k) / (1.0 - r)


def actividad_por_componente(phi_voxel: np.ndarray, isotopo: str, k: int,
                             t_pulso_s: float, t_entre_pulsos_s: float
                             ) -> dict[str, float]:
    a = actividad_pulso(phi_voxel, isotopo, k, t_pulso_s, t_entre_pulsos_s)
    mascaras = mascara_componentes(phi_voxel.shape)
    return {nombre: float(a[m].sum()) for nombre, m in mascaras.items()}


def mascara_concreto(dims=(110, 110, 60)) -> np.ndarray:
    """Unión de las máscaras de componentes = todo el concreto del bloque."""
    m = mascara_componentes(dims)
    u = np.zeros(dims, dtype=bool)
    for x in m.values():
        u |= x
    return u


def isotopo_predominante(phi_voxel: np.ndarray, k: int, t_pulso_s: float,
                         t_entre_pulsos_s: float,
                         t_tras_apagado_s: float = 0.0) -> dict:
    """Isótopo que domina la actividad total del CONCRETO en el pulso k
    (suma enmascarada al concreto — el aire no se activa como hormigón)."""
    mc = mascara_concreto(phi_voxel.shape)
    tot = {}
    for iso in ISOTOPOS_CINE:
        p = ISOTOPOS_CINE[iso]
        a = actividad_pulso(phi_voxel, iso, k, t_pulso_s, t_entre_pulsos_s)[mc]
        s = float(a.sum())
        if t_tras_apagado_s > 0:
            s *= math.exp(-math.log(2.0) / p["t12_s"] * t_tras_apagado_s)
        tot[iso] = s
    dominante = max(tot, key=tot.get) if any(v > 0 for v in tot.values()) else None
    return {"actividad_total_bq": tot, "predominante": dominante}
