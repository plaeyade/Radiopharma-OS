"""
Catálogo de blancos del MVP (biblioteca extensible, EDS cap. 5).

Cada blanco define: material para stopping power, núclido blanco,
fracción másica y enriquecimiento isotópico por defecto.
"""
from __future__ import annotations

from app.domain.entities import TargetMaterial

TARGET_CATALOG: dict[str, TargetMaterial] = {
    # Blanco líquido H2-18O enriquecido (ruta estándar de producción de 18F-)
    "h2_18o": TargetMaterial(
        material_id="h2_18o",
        label="Agua enriquecida H2[18O] (líquida)",
        stopping_material="h2o",
        target_nuclide="18O",
        molar_mass_g_mol=18.0,
        mass_fraction=18.0 / 20.015,   # 18O en H2^18O (M = 20.015 g/mol)
        enrichment=0.995,              # enriquecimiento típico comercial 99.5%
    ),
    # Blanco gaseoso N2 natural (ruta estándar [11C]CO2; en producción real
    # se mezcla con 0.5-1% O2, despreciable en el cálculo de rendimiento)
    "n2_gas": TargetMaterial(
        material_id="n2_gas",
        label="Gas nitrógeno natural N2",
        stopping_material="n2",
        target_nuclide="14N",
        molar_mass_g_mol=14.0,
        mass_fraction=1.0,             # todo el material es N
        enrichment=0.99634,            # abundancia natural de 14N
    ),
    # Blanco gaseoso 15N2 enriquecido (ruta estándar [15O]O2 / [15O]H2O)
    "n15_gas": TargetMaterial(
        material_id="n15_gas",
        label="Gas nitrógeno enriquecido [15N]N2",
        stopping_material="n15",         # S(E) por gramo difiere 7% vs 14N2 (masa molar)
        target_nuclide="15N",
        molar_mass_g_mol=15.0,
        mass_fraction=1.0,
        enrichment=0.99,
    ),
    # Blanco de 68Zn enriquecido (sólido electroplated o líquido [68Zn]ZnCl2/HCl)
    "zn68": TargetMaterial(
        material_id="zn68",
        label="Zinc enriquecido 68Zn",
        stopping_material="zn68",
        target_nuclide="68Zn",
        molar_mass_g_mol=68.0,
        mass_fraction=1.0,
        enrichment=0.982,                # enriquecimiento típico comercial
    ),
    # Blanco de 64Ni enriquecido (electroplated sobre backplate Au/Cu —
    # ruta ciclotrón estándar de 64Cu). Stopping: proxy Cu PSTAR
    # DECLARADO (PSTAR no publica Ni; pendiente tabla SRIM/ATIMA real
    # exportada por el usuario → calibración/promoción 19.10).
    "ni64": TargetMaterial(
        material_id="ni64",
        label=("Níquel enriquecido 64Ni (stopping: proxy Cu PSTAR "
               "declarado; enriquecimiento típico comercial declarado)"),
        stopping_material="ni64",
        target_nuclide="64Ni",
        molar_mass_g_mol=64.0,
        mass_fraction=1.0,
        enrichment=0.95,                 # enriquecimiento típico comercial declarado
    ),
    # Blanco gaseoso 18O2 (ruta [18F]F2)
    "o2_18": TargetMaterial(
        material_id="o2_18",
        label="Gas oxígeno enriquecido [18O]O2",
        stopping_material="o2",
        target_nuclide="18O",
        molar_mass_g_mol=18.0,
        mass_fraction=1.0,
        enrichment=0.995,
    ),
}
