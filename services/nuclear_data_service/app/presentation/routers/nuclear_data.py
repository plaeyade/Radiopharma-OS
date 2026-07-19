"""
Router REST del Nuclear Data Service.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from app.application.queries import NuclearDataQueries
from app.presentation.schemas import (
    CrossSectionPointOut, DatasetOut, DecayModeOut, DecayOut, EmissionOut, ReactionOut)

router = APIRouter(prefix="/api/v1", tags=["nuclear-data"])

_queries: NuclearDataQueries | None = None
_data_dir: Path | None = None


def init(queries: NuclearDataQueries, data_dir: Path) -> None:
    """Inyección de dependencias desde main.py."""
    global _queries, _data_dir
    _queries, _data_dir = queries, data_dir


def _reaction_out(r) -> ReactionOut:
    return ReactionOut(
        reaction_id=r.reaction_id, notation=r.notation, projectile=r.projectile,
        target_nuclide=r.target_nuclide, product_nuclide=r.product_nuclide,
        q_value_mev=r.q_value_mev, threshold_mev=r.threshold_mev,
        dataset_id=r.dataset_id, n_points=len(r.points),
        points=[CrossSectionPointOut(energy_mev=p.energy_mev, sigma_mb=p.sigma_mb,
                                     dsigma_mb=p.dsigma_mb) for p in r.points])


@router.get("/reactions", response_model=list[ReactionOut])
def list_reactions() -> list[ReactionOut]:
    return [_reaction_out(r) for r in _queries.list_reactions()]


@router.get("/reactions/{reaction_id}", response_model=ReactionOut)
def get_reaction(reaction_id: str) -> ReactionOut:
    r = _queries.get_reaction(reaction_id)
    if r is None:
        raise HTTPException(status_code=404, detail=f"Reacción no encontrada: {reaction_id}")
    return _reaction_out(r)


@router.get("/reactions/{reaction_id}/cross-section", response_model=ReactionOut)
def get_cross_section(
    reaction_id: str,
    e_min: float = Query(0.0, ge=0.0),
    e_max: float = Query(1000.0, gt=0.0),
) -> ReactionOut:
    r = _queries.get_cross_section_window(reaction_id, e_min, e_max)
    if r is None:
        raise HTTPException(status_code=404, detail=f"Reacción no encontrada: {reaction_id}")
    return _reaction_out(r)


@router.get("/nuclides/{nuclide}/decay", response_model=DecayOut)
def get_decay(nuclide: str) -> DecayOut:
    d = _queries.get_decay(nuclide)
    if d is None:
        raise HTTPException(status_code=404, detail=f"Núclido no encontrado: {nuclide}")
    return DecayOut(
        nuclide=d.nuclide, z=d.z, a=d.a, half_life_s=d.half_life_s,
        decay_constant_s=d.decay_constant_s,
        decay_modes=[DecayModeOut(mode=m.mode, branching_ratio=m.branching_ratio,
                                  endpoint_energy_kev=m.endpoint_energy_kev) for m in d.decay_modes],
        emissions=[EmissionOut(type=e.type, energy_kev=e.energy_kev,
                               intensity_percent=e.intensity_percent) for e in d.emissions],
        dataset_id=d.dataset_id)


@router.get("/datasets", response_model=list[DatasetOut])
def list_datasets() -> list[DatasetOut]:
    registry = json.loads((_data_dir / "datasets.json").read_text())
    return [DatasetOut(**d) for d in registry["datasets"]]
