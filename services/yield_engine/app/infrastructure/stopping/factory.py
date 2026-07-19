"""
Fábrica de proveedores de stopping power con degradación elegante:
ATIMA nativo -> tablas CSV empaquetadas.
"""
from __future__ import annotations

from pathlib import Path

from app.domain.interfaces import StoppingPowerProvider


def build_stopping_provider(data_dir: Path) -> StoppingPowerProvider:
    try:
        from app.infrastructure.stopping.atima_stopping import AtimaStoppingPower
        return AtimaStoppingPower()
    except Exception:
        from app.infrastructure.stopping.table_stopping import TableStoppingPower
        return TableStoppingPower(data_dir)
