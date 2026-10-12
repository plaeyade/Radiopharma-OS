# -*- coding: utf-8 -*-
"""Caso Monte Carlo del búnker OIEA en OpenMC — Fase 42.

Port 1:1 del caso Geant4/Gate de la Fase 32 (``bunker_case.py``) a CSG de
OpenMC: MISMA geometría, MISMO espectro TALYS real (nspec_o18.tot,
¹⁸O(p,xn) a 16,5 MeV — nunca un espectro fabricado), MISMA malla
110×110×60 sobre el world de 22×22×12 m y MISMO estimador de fluencia
(track-length), para que la comparación triple de la Fase 43
(FTFP_BERT vs FTFP_BERT_HP vs OpenMC) sea limpia.

Geometría declarada tipo OIEA (pendiente de plano real — Fase 38):
  - world aire 22 × 22 × 12 m
  - bloque de concreto 12 × 10 × 6 m centrado (muros 2,0 m sobre la bóveda)
  - bóveda interior (aire) 6 × 6 × 4 m
  - laberinto: tramo 1 (aire) 3,0 × 1,2 × 2,4 m en (4,5, −2,4, −0,8) m;
    tramo 2 (aire) 1,2 × 4,0 × 2,4 m en (6,6, 1,4, −0,8) m (fuera del bloque)

Materiales NIST (fuentes citadas — regla 49.11):
  - concreto NIST = G4_CONCRETE (NIST PD, ρ = 2,3 g/cm³), composición en
    peso según Geant4 NIST manager (Sin S(α,β): paridad declarada con el
    tratamiento de gas libre de los casos Geant4 F32/F35/F37).
  - aire NIST = G4_AIR (ρ = 1,20479e-3 g/cm³, N/O/Ar en peso).

Sin resultados simulados: este módulo SOLO construye el caso; la ejecución
real queda en evidencia_v072/fase42/ y los lotes estadísticos en la F43.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# --- Composiciones NIST (fracciones en PESO) — fuente: Geant4 NIST manager ---
# G4_CONCRETE (NIST concrete): H,C,O,Na,Mg,Al,Si,K,Ca,Fe
CONCRETE_WO = [
    ("H", 0.010000), ("C", 0.001000), ("O", 0.529107), ("Na", 0.016000),
    ("Mg", 0.002000), ("Al", 0.033872), ("Si", 0.337021), ("K", 0.013000),
    ("Ca", 0.044000), ("Fe", 0.014000),
]
# G4_AIR: N, O, Ar
AIR_WO = [("N", 0.755268), ("O", 0.231781), ("Ar", 0.012827)]

GEOM_CM = {
    "world": (-1100.0, 1100.0, -1100.0, 1100.0, -600.0, 600.0),
    "concreto": (-600.0, 600.0, -500.0, 500.0, -300.0, 300.0),
    "boveda": (-300.0, 300.0, -300.0, 300.0, -200.0, 200.0),
    "laberinto_1": (300.0, 600.0, -300.0, -180.0, -200.0, 40.0),
    "laberinto_2": (600.0, 720.0, -60.0, 340.0, -200.0, 40.0),
}
MESH_BINS = (110, 110, 60)

# --- F42b: geometría REAL del plano BIND (Fase 38), recentrada en la ---
# máquina (-10,6; 38,2 m del plano → origen). Cada bloque declara su
# estado: medido_sobre_plano o estimado_sobre_plano_pendiente_verificacion.
# Alturas en z: NO medibles en planta → provisional 4,0 m declarado
# (pendiente_verificacion con alzados/cortes del set arquitectónico).
GEOM_REAL_BIND_CM = {
    # envolvente del búnker: x -15,39..-5,68 ; y 33,53..49,02 (cota 15,499)
    "concreto": (-479.0, 492.0, -467.0, 1082.0, -200.0, 200.0),
    # sala interior ~5,9 x 4,7 m (estimada F38); la cara oeste respeta el
    # muro MEDIDO de 2,11 m (-479 + 211 = -268) — la sala NO está centrada
    # en la máquina (hallazgo del test de coherencia)
    "boveda": (-268.0, 322.0, -235.0, 235.0, -185.0, 185.0),
    # laberinto SUR real (2 cambios de dirección, F38): tramo de salida
    # estimado desde la pared sur de la sala hasta el borde de la envolvente
    "laberinto_1": (-90.0, 110.0, -467.0, -235.0, -120.0, 120.0),
    # muro oeste REAL: 2,11 m medidos (cara ext. x=-479 ↔ cara int. x=-268)
    "muro_oeste_medido_m": 2.11,
    "fuente_xy_plano_m": (-10.6, 38.2),
    "estado": ("geometria_parcial_medida_sobre_plano — envolvente y muro "
               "oeste medidos; sala interior y laberinto estimados; altura "
               "z provisional 4,0 m pendiente_verificacion (alzados)"),
}


@dataclass(frozen=True)
class BunkerOpenMCCase:
    """Configuración registrable del caso búnker OpenMC (19.24)."""
    spectrum_file: str            # nspec*.tot REAL de TALYS
    n_histories: int = 40_000
    batches: int = 10
    seed: int = 20261012
    mesh_bins: tuple = MESH_BINS
    cross_sections: str = ""      # OPENMC_CROSS_SECTIONS (ENDF/B-VIII.0)
    geometria: str = "oiea"       # "oiea" (F32) | "bind_real" (F38/F42b)
    nota_termico: str = ("sin S(α,β) — paridad declarada con gas libre "
                         "de los casos Geant4 (F32/F35/F37)")

    def geom(self) -> dict:
        if self.geometria == "bind_real":
            g = dict(GEOM_REAL_BIND_CM)
            g["world"] = (-1100.0, 1100.0, -1100.0, 1100.0, -600.0, 600.0)
            g["laberinto_2"] = (1.0, 2.0, 1.0, 2.0, 1.0, 2.0)  # no usado en bind_real
            return g
        return GEOM_CM


def _box_region(b):
    import openmc
    x0, x1, y0, y1, z0, z1 = b
    return (+openmc.XPlane(x0) & -openmc.XPlane(x1) &
            +openmc.YPlane(y0) & -openmc.YPlane(y1) &
            +openmc.ZPlane(z0) & -openmc.ZPlane(z1))


def vol_concreto_cm3(case: BunkerOpenMCCase | None = None) -> float:
    """Volumen analítico del concreto (para prueba de equivalencia)."""
    g = (case or BunkerOpenMCCase(spectrum_file="")).geom()
    def v(b):
        return (b[1]-b[0]) * (b[3]-b[2]) * (b[5]-b[4])
    return (v(g["concreto"]) - v(g["boveda"])
            - v(g["laberinto_1"]))


def vol_aire_cm3(case: BunkerOpenMCCase | None = None) -> float:
    g = (case or BunkerOpenMCCase(spectrum_file="")).geom()
    def v(b):
        return (b[1]-b[0]) * (b[3]-b[2]) * (b[5]-b[4])
    return (v(g["world"]) - v(g["concreto"])
            + v(g["boveda"]) + v(g["laberinto_1"])
            + v(g["laberinto_2"]))


def build_openmc_model(case: BunkerOpenMCCase):
    """Construye el modelo OpenMC en memoria (materiales, CSG, fuente, tally)."""
    import numpy as np
    import openmc

    # --- materiales NIST ---
    concreto = openmc.Material(name="G4_CONCRETE_NIST")
    for el, w in CONCRETE_WO:
        concreto.add_element(el, w, "wo")
    concreto.set_density("g/cm3", 2.3)

    aire = openmc.Material(name="G4_AIR_NIST")
    for el, w in AIR_WO:
        aire.add_element(el, w, "wo")
    aire.set_density("g/cm3", 1.20479e-3)

    mats = openmc.Materials([concreto, aire])

    # --- geometría CSG (OIEA F32 o real BIND F38/F42b) ---
    g = case.geom()
    # Frontera de vacío: los 6 planos del world se crean UNA VEZ con
    # boundary_type="vacuum" y se reusan en la región del world — si son
    # superficies distintas a las de las celdas, las partículas que cruzan
    # la frontera quedan "lost" (bug detectado en la corrida F42).
    x0, x1, y0, y1, z0, z1 = g["world"]
    world_planes = [openmc.XPlane(x0, boundary_type="vacuum"),
                    openmc.XPlane(x1, boundary_type="vacuum"),
                    openmc.YPlane(y0, boundary_type="vacuum"),
                    openmc.YPlane(y1, boundary_type="vacuum"),
                    openmc.ZPlane(z0, boundary_type="vacuum"),
                    openmc.ZPlane(z1, boundary_type="vacuum")]
    r_world = (+world_planes[0] & -world_planes[1] & +world_planes[2]
               & -world_planes[3] & +world_planes[4] & -world_planes[5])
    r_conc = _box_region(g["concreto"])
    r_bov = _box_region(g["boveda"])
    r_lab1 = _box_region(g["laberinto_1"])
    r_lab2 = _box_region(g["laberinto_2"])

    c_conc = openmc.Cell(name="concreto", fill=concreto,
                         region=r_conc & ~r_bov & ~r_lab1)
    c_bov = openmc.Cell(name="boveda", fill=aire, region=r_bov)
    c_lab1 = openmc.Cell(name="laberinto_1", fill=aire, region=r_lab1)
    celdas = [c_conc, c_bov, c_lab1]
    if case.geometria != "bind_real":
        # OIEA: segundo tramo del laberinto fuera del bloque
        c_lab2 = openmc.Cell(name="laberinto_2", fill=aire, region=r_lab2)
        celdas.append(c_lab2)
    c_out = openmc.Cell(name="aire_exterior", fill=aire,
                        region=(r_world & ~r_conc if case.geometria == "bind_real"
                                else r_world & ~r_conc & ~r_lab2))
    celdas.append(c_out)

    # frontera de vacío en el world
    x0, x1, y0, y1, z0, z1 = g["world"]
    world_planes = [openmc.XPlane(x0, boundary_type="vacuum"),
                    openmc.XPlane(x1, boundary_type="vacuum"),
                    openmc.YPlane(y0, boundary_type="vacuum"),
                    openmc.YPlane(y1, boundary_type="vacuum"),
                    openmc.ZPlane(z0, boundary_type="vacuum"),
                    openmc.ZPlane(z1, boundary_type="vacuum")]
    r_vac = (+world_planes[0] & -world_planes[1] & +world_planes[2]
             & -world_planes[3] & +world_planes[4] & -world_planes[5])
    for c in celdas:
        c.region &= r_vac
    geom = openmc.Geometry(celdas)

    # --- fuente: espectro TALYS REAL (histograma E, peso) ---
    e, w = [], []
    with open(case.spectrum_file) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            c = line.split()
            e.append(float(c[0]) * 1e6)   # MeV → eV
            w.append(float(c[1]))
    src = openmc.IndependentSource()
    src.space = openmc.stats.Point((0.0, 0.0, 0.0))
    src.angle = openmc.stats.Isotropic()
    src.energy = openmc.stats.Tabular(np.array(e), np.array(w), "histogram")

    settings = openmc.Settings()
    settings.run_mode = "fixed source"
    settings.particles = case.n_histories
    settings.batches = case.batches
    settings.seed = case.seed
    settings.source = src

    # --- tally: MISMA malla que F32/F35 (110×110×60 sobre 22×22×12 m) ---
    nx, ny, nz = case.mesh_bins
    mesh = openmc.RegularMesh()
    mesh.dimension = (nx, ny, nz)
    mesh.lower_left = (-1100.0, -1100.0, -600.0)
    mesh.upper_right = (1100.0, 1100.0, 600.0)
    tally = openmc.Tally(name="flujo_malla")
    tally.filters = [openmc.MeshFilter(mesh)]
    tally.scores = ["flux"]
    tallies = openmc.Tallies([tally])

    return openmc.Model(geometry=geom, materials=mats,
                        settings=settings, tallies=tallies)


def write_case(case_dir: str | Path, case: BunkerOpenMCCase) -> Path:
    """Escribe case.json versionado + materials/geometry/settings/tallies XML."""
    case_dir = Path(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case_openmc.json").write_text(json.dumps(
        {**case.__dict__, "mesh_bins": list(case.mesh_bins)}, indent=2))
    model = build_openmc_model(case)
    model.export_to_model_xml(path=str(case_dir / "model.xml"))
    return case_dir / "model.xml"
