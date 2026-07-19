"""
Repositorio CSV de secciones eficaces.

Los archivos CSV viven versionados en el propio repositorio (data-centric):
cada dataset lleva procedencia, hash y fecha de descarga (ALCOA+).
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from app.domain.entities import CrossSectionPoint, ReactionChannel


# Catálogo de reacciones soportadas por el MVP.
# Cada entrada mapea reaction_id -> metadatos físicos + archivo de datos.
REACTION_CATALOG: dict[str, dict] = {
    "n15_p_n_o15": {
        "notation": "15N(p,n)15O", "projectile": "p", "target_nuclide": "15N",
        "product_nuclide": "15O", "q_value_mev": -3.54, "threshold_mev": 3.77,
        "dataset_id": "n15_p_n_o15_iaea2021",
        "file": "n15_p_n_o15/n15_p_n_o15_iaea2021.csv",
    },
    "zn68_p_n_ga68": {
        "notation": "68Zn(p,n)68Ga", "projectile": "p", "target_nuclide": "68Zn",
        "product_nuclide": "68Ga", "q_value_mev": -3.70, "threshold_mev": 3.76,
        "dataset_id": "zn68_p_n_ga68_iaea2021",
        "file": "zn68_p_n_ga68/zn68_p_n_ga68_iaea2021.csv",
    },
    "n14_p_a_c11": {
        "notation": "14N(p,alpha)11C",
        "projectile": "p",
        "target_nuclide": "14N",
        "product_nuclide": "11C",
        "q_value_mev": -2.922,
        "threshold_mev": 3.132,
        "dataset_id": "n14_p_a_c11_iaea2021",
        "file": "n14_p_a_c11/n14_p_a_c11_iaea2021.csv",
    },
    "o18_p_n_f18": {
        "notation": "18O(p,n)18F",
        "projectile": "p",
        "target_nuclide": "18O",
        "product_nuclide": "18F",
        "q_value_mev": -2.438,
        "threshold_mev": 2.574,
        "dataset_id": "o18_p_n_f18_iaea2021",
        "file": "o18_p_n_f18/o18_p_n_f18_iaea2021.csv",
    },
}


class CsvCrossSectionRepository:
    """Implementación CSV del puerto CrossSectionRepository."""

    def __init__(self, data_dir: Path) -> None:
        self._base = Path(data_dir) / "cross_sections"

    def _load_points(self, rel_file: str) -> tuple[CrossSectionPoint, ...]:
        path = self._base / rel_file
        points: list[CrossSectionPoint] = []
        with open(path, newline="") as fh:
            reader = csv.reader(fh)
            for row in reader:
                if not row or row[0].startswith("#"):
                    continue
                if row[0] == "energy_MeV":  # encabezado
                    continue
                ds = float(row[2]) if len(row) > 2 and row[2] != "" else None
                points.append(CrossSectionPoint(
                    energy_mev=float(row[0]), sigma_mb=float(row[1]), dsigma_mb=ds))
        return tuple(points)

    def list_reactions(self) -> list[ReactionChannel]:
        return [self._build(rid, meta) for rid, meta in REACTION_CATALOG.items()]

    def get_reaction(self, reaction_id: str) -> Optional[ReactionChannel]:
        meta = REACTION_CATALOG.get(reaction_id)
        if meta is None:
            return None
        return self._build(reaction_id, meta)

    def _build(self, rid: str, meta: dict) -> ReactionChannel:
        return ReactionChannel(
            reaction_id=rid,
            notation=meta["notation"],
            projectile=meta["projectile"],
            target_nuclide=meta["target_nuclide"],
            product_nuclide=meta["product_nuclide"],
            q_value_mev=meta["q_value_mev"],
            threshold_mev=meta["threshold_mev"],
            dataset_id=meta["dataset_id"],
            points=self._load_points(meta["file"]),
        )
