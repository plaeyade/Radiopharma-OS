"""
Repositorio de secciones eficaces calculadas con TALYS.

Implementa el mismo puerto CrossSectionRepository que el repositorio
CSV IAEA: TALYS es la segunda fuente (teórica) para verificación
cruzada. Resultados cacheados con procedencia ALCOA+ (input, salida
cruda, CSV parseado, meta.json con versión, fecha y sha256).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.domain.entities import CrossSectionPoint, ReactionChannel
from app.infrastructure.repositories.csv_cross_section_repository import (
    REACTION_CATALOG)
from app.infrastructure.talys.talys_runner import (TalysRunner,
                                                   TalysUnavailable,
                                                   build_input,
                                                   parse_rp_tot,
                                                   product_rp_file)

# símbolo de elemento y masa del blanco por reacción (para el input TALYS)
_TARGET_MAP: dict[str, tuple[str, int]] = {
    "n15_p_n_o15": ("n", 15),
    "zn68_p_n_ga68": ("zn", 68),
    "n14_p_a_c11": ("n", 14),
    "o18_p_n_f18": ("o", 18),
}

TALYS_DATASET_SUFFIX = "talys2"


class TalysCrossSectionRepository:
    """σ(E) teóricas vía TALYS, con caché y procedencia."""

    def __init__(self, cache_dir: Path,
                 runner: TalysRunner | None = None) -> None:
        self._cache = Path(cache_dir)
        self._runner = runner or TalysRunner()

    @property
    def runner(self) -> TalysRunner:
        return self._runner

    # -------------------------------------------------------- caché
    def _dir(self, reaction_id: str) -> Path:
        return self._cache / reaction_id

    def _csv(self, reaction_id: str) -> Path:
        return self._dir(reaction_id) / "talys_parsed.csv"

    def _load_cached(self, reaction_id: str) -> tuple[CrossSectionPoint, ...] | None:
        csv_path = self._csv(reaction_id)
        if not csv_path.is_file():
            return None
        pts: list[CrossSectionPoint] = []
        for line in csv_path.read_text(encoding="utf-8").splitlines()[1:]:
            if not line.strip():
                continue
            e, xs = line.split(",")[:2]
            pts.append(CrossSectionPoint(energy_mev=float(e),
                                         sigma_mb=float(xs),
                                         dsigma_mb=None))
        return tuple(pts)

    # -------------------------------------------------------- cálculo
    def compute(self, reaction_id: str,
                emin_mev: float = 0.1, emax_mev: float = 30.0,
                force: bool = False) -> ReactionChannel:
        """Calcula (o carga de caché) la σ(E) TALYS de una reacción."""
        meta = REACTION_CATALOG.get(reaction_id)
        if meta is None:
            raise KeyError(reaction_id)
        if not force:
            cached = self._load_cached(reaction_id)
            if cached is not None:
                return self._channel(reaction_id, meta, cached, from_cache=True)

        element, mass = _TARGET_MAP[reaction_id]
        rp_file = product_rp_file(meta["product_nuclide"])
        inp = build_input(meta["projectile"], element, mass,
                          emin_mev, emax_mev)
        workdir = self._dir(reaction_id)
        rp = self._runner.run(workdir, inp, rp_file)
        raw = parse_rp_tot(rp)

        # persistir con procedencia ALCOA+
        csv_text = "energy_mev,sigma_mb\n" + "".join(
            f"{e:.6e},{xs:.6e}\n" for e, xs in raw)
        self._csv(reaction_id).write_text(csv_text, encoding="utf-8")
        sha = hashlib.sha256(csv_text.encode()).hexdigest()
        (workdir / "meta.json").write_text(json.dumps({
            "reaction_id": reaction_id,
            "source": "TALYS (cálculo teórico, segunda fuente σ(E))",
            "tool": self._runner.version() or "talys",
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "sha256": sha,
            "n_points": len(raw),
        }, indent=1), encoding="utf-8")

        pts = tuple(CrossSectionPoint(energy_mev=e, sigma_mb=xs,
                                      dsigma_mb=None) for e, xs in raw)
        return self._channel(reaction_id, meta, pts, from_cache=False)

    @staticmethod
    def _channel(reaction_id: str, meta: dict,
                 pts: tuple[CrossSectionPoint, ...],
                 from_cache: bool) -> ReactionChannel:
        return ReactionChannel(
            reaction_id=reaction_id,
            notation=meta["notation"],
            projectile=meta["projectile"],
            target_nuclide=meta["target_nuclide"],
            product_nuclide=meta["product_nuclide"],
            q_value_mev=meta["q_value_mev"],
            threshold_mev=meta["threshold_mev"],
            dataset_id=f"{meta['dataset_id']}_{TALYS_DATASET_SUFFIX}"
                       + ("_cache" if from_cache else ""),
            points=pts)

    # -------------------------------------------------------- puerto
    def list_reactions(self) -> list[ReactionChannel]:
        out: list[ReactionChannel] = []
        for rid in REACTION_CATALOG:
            try:
                out.append(self.compute(rid))
            except TalysUnavailable:
                raise
            except Exception:
                continue
        return out

    def get_reaction(self, reaction_id: str) -> Optional[ReactionChannel]:
        try:
            return self.compute(reaction_id)
        except Exception:
            return None
