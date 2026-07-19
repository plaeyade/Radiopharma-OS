"""
Tests del pipeline CLI: tabla de decaimiento post-EOB (física pura).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipelines"))

from batch_cli import decay_table


def test_decay_table_a_una_vida_media():
    # 18F: T1/2 = 109.77 min
    pts = decay_table(100.0, 109.77, points_min=(109.77,))
    assert math.isclose(pts[0]["activity_gbq"], 50.0, rel_tol=1e-3)


def test_decay_table_monotona_decreciente():
    pts = decay_table(100.0, 109.77)
    actividades = [p["activity_gbq"] for p in pts]
    assert all(a > b for a, b in zip(actividades, actividades[1:]))
