# -*- coding: utf-8 -*-
"""Conector mesh tally MC real → flujo φ para el motor Bateman (Fase 33).

Lee la imagen del tally Geant4 del búnker (Fase 32, formato .mhd/.raw) y
la convierte en un mapa de flujo φ (n/cm²/s) utilizable como
`origen_flujo="mesh_tally:..."` en activation.py, retirando el marcador
`flujo_declarado_pendiente_mesh_tally` de las regiones cubiertas.

ESTIMADOR DECLARADO (primera iteración, documentado):
- La imagen de counts del FluenceActor cuenta trayectos por voxel.
- φ_voxel = (counts_voxel × L̄ / N_historias) × Q / V_voxel, con
  L̄ = 2a/3 (cuerda media isotrópica de un cubo de arista a) y Q = tasa
  total de neutrones de la fuente (n/s).
- Q para F-18 se calcula por ARITMÉTICA citada: en saturación, la
  actividad 18F por µA (9,902 GBq/µA, IAEA-2021 plataforma) equivale a
  una desintegración por núcleo producido; cada 18O(p,n)18F emite un
  neutrón → Q ≥ 9,902e9 × I (COTA INFERIOR: ignora canales (p,2n), (p,np)
  y neutrones de otras reacciones; se declara así).
- Pendiente: reducción de varianza / HP para térmicos; validación
  cruzada con PHITS cuando la licencia llegue.
"""
from __future__ import annotations

from pathlib import Path

# Rendimiento de saturación 18F citado (IAEA-2021 plataforma, Fase 30).
Y_SAT_F18_GBQ_UA = 9.902


def tasa_neutrones_f18(corriente_ua: float) -> dict:
    """Q (n/s) de la fuente 18O(p,n)18F — aritmética citada, cota inferior."""
    if corriente_ua <= 0:
        raise ValueError("corriente_ua debe ser > 0")
    q = Y_SAT_F18_GBQ_UA * 1e9 * corriente_ua
    return {
        "q_n_s": q,
        "naturaleza": ("cota_inferior_declarada: solo canal 18O(p,n)18F en "
                       "saturación (Y_sat 9,902 GBq/µA citado IAEA-2021); "
                       "excluye (p,2n)/(p,np) y otras rutas"),
        "fuente": "Y_sat F-18 9,902 GBq/µA @ 18 MeV — dataset IAEA-2021 plataforma",
    }


def leer_tally_mhd(path_mhd: str | Path) -> dict:
    """Lee cabecera .mhd + .raw (MET_FLOAT/MET_DOUBLE) → array + geometría."""
    import numpy as np
    path_mhd = Path(path_mhd)
    hdr = {}
    for line in path_mhd.read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            hdr[k.strip()] = v.strip()
    dims = [int(x) for x in hdr["DimSize"].split()]          # nx ny nz
    spacing = [float(x) for x in hdr["ElementSpacing"].split()]  # mm
    etype = hdr["ElementType"]
    raw = (path_mhd.parent / hdr["ElementDataFile"]).read_bytes()
    dt = np.float32 if etype == "MET_FLOAT" else np.float64
    arr = np.frombuffer(raw, dtype=dt).reshape(dims[2], dims[1], dims[0])
    return {"counts": arr, "dims": dims, "spacing_mm": spacing}


def mapa_flujo(path_mhd: str | Path, q_n_s: float, n_historias: int) -> dict:
    """Convierte counts → mapa φ (n/cm²/s) por voxel (estimador declarado)."""
    if q_n_s <= 0 or n_historias <= 0:
        raise ValueError("q_n_s y n_historias deben ser > 0")
    t = leer_tally_mhd(path_mhd)
    counts = t["counts"]
    a_cm = t["spacing_mm"][0] / 10.0                        # voxel cúbico
    v_voxel = a_cm ** 3
    cuerda = 2.0 * a_cm / 3.0                               # L̄ isotrópica
    phi = counts * cuerda / n_historias * q_n_s / v_voxel
    return {
        "phi_n_cm2_s": phi,
        "voxel_cm": a_cm,
        "n_historias": n_historias,
        "q_n_s": q_n_s,
        "estimador": ("declarado: φ = counts·(2a/3)/(N·V)·Q — primera "
                      "iteración, pendiente reducción de varianza/HP y "
                      "validación cruzada PHITS"),
        "origen_flujo": f"mesh_tally:{Path(path_mhd).name}:N={n_historias}:Q={q_n_s:.3e}",
    }


def phi_medio_muros(mapa: dict) -> dict:
    """φ medio y máximo en los voxels con counts > 0 de los muros
    (excluye el aire interior: regiones centrales sin counts de concreto
    ya vienen a ~0). Devuelve valores escalares para CalculoActivacion."""
    import numpy as np
    phi = mapa["phi_n_cm2_s"]
    activos = phi[phi > 0]
    if activos.size == 0:
        raise ValueError("mapa sin voxels activos — tally vacío")
    return {
        "phi_medio_n_cm2_s": float(activos.mean()),
        "phi_max_n_cm2_s": float(activos.max()),
        "voxels_activos": int(activos.size),
        "origen_flujo": mapa["origen_flujo"],
        "estimador": mapa["estimador"],
    }


def actividad_pared(engine, path_mhd: str | Path, corriente_ua: float,
                    n_historias: int, isotopo: str,
                    n_nucleos_padre: float, t_pulso_s: float,
                    n_pulsos: int, t_entre_pulsos_s: float,
                    motivo: str, usuario: str) -> dict:
    """Atajo canónico: tally real → φ medio de muros → CalculoActivacion
    del Bateman con estado_flujo=flujo_mc_real."""
    from app.domain.activation import CalculoActivacion
    q = tasa_neutrones_f18(corriente_ua)
    mapa = mapa_flujo(path_mhd, q["q_n_s"], n_historias)
    p = phi_medio_muros(mapa)
    c = CalculoActivacion(
        calculo_id="ACT-BUNKER-" + str(abs(hash(str(path_mhd))) % 10**6),
        isotopo=isotopo,
        n_nucleos_padre=n_nucleos_padre,
        flujo_n_cm2_s=p["phi_medio_n_cm2_s"],
        origen_flujo=p["origen_flujo"],
        t_pulso_s=t_pulso_s,
        n_pulsos=n_pulsos,
        t_entre_pulsos_s=t_entre_pulsos_s,
        motivo=motivo,
    )
    res = engine.calcular(c, usuario)
    res["tasa_neutrones"] = q
    res["phi_muros"] = {k: v for k, v in p.items() if k != "estimador"}
    return res


def estadistica_lotes(mapas: list) -> dict:
    """Estadística por lotes de K mapas φ independientes (semillas distintas).

    Estimador declarado: media por lotes y error estándar de la media
    (SEM = s/√K con s = desviación estándar muestral entre lotes, ddof=1).
    Honestidad: con K pequeño la incertidumbre es solo indicativa — se
    declara K y nunca se presenta como barra de error validada.
    """
    import numpy as np
    if len(mapas) < 2:
        raise ValueError("se requieren >= 2 lotes para estadística")
    formas = {m["phi_n_cm2_s"].shape for m in mapas}
    if len(formas) != 1:
        raise ValueError("lotes con geometrías distintas — no combinables")
    pila = np.stack([m["phi_n_cm2_s"] for m in mapas])
    k = len(mapas)
    media = pila.mean(axis=0)
    s = pila.std(axis=0, ddof=1)
    sem = s / np.sqrt(k)
    activos = media > 0
    if not activos.any():
        raise ValueError("mapas sin voxels activos — tally vacío")
    rel_sem = float((sem[activos] / media[activos]).mean())
    return {
        "phi_media_n_cm2_s": media,
        "phi_sem_n_cm2_s": sem,
        "k_lotes": k,
        "muros": {
            "phi_medio_n_cm2_s": float(media[activos].mean()),
            "phi_max_n_cm2_s": float(media[activos].max()),
            "sem_medio_n_cm2_s": float(sem[activos].mean()),
            "sem_relativo_medio": rel_sem,
            "voxels_activos": int(activos.sum()),
        },
        "estimador": ("declarado: media y SEM por lotes independientes "
                      f"(K={k}, ddof=1); incertidumbre indicativa, "
                      "pendiente reducción de varianza y validación PHITS"),
        "origen_flujo": "mesh_tally_lotes:" + ";".join(
            m["origen_flujo"] for m in mapas),
    }
