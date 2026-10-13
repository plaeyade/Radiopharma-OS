"""Tests F54 — informe regulatorio integrado."""
import json
from pathlib import Path

from pipelines.informe_regulatorio_f54 import construir_informe, SECCIONES


def test_integra_evidencia_real():
    inf = construir_informe()
    assert inf["estado"] == "expediente_integrado_honesto"
    assert len(inf["secciones"]) == len(SECCIONES)
    # F42b real: 30k historias deben aparecer tal cual (sin recalcular)
    assert inf["secciones"]["mc_bind_real_f42b"]["datos"]["historias_totales"] == 30000


def test_sintesis_solo_valores_publicados():
    inf = construir_informe()
    s = inf["sintesis_citada"]
    assert abs(s["transmision_muro_este"] - 0.0282) < 1e-9
    assert 1.0 < s["tvl_efectivo_m"] < 1.2
    assert s["tvl_adicionales_requeridos"] > 4.0


def test_hallazgos_abiertos_declarados():
    inf = construir_informe()
    txt = " ".join(inf["hallazgos_abiertos"])
    assert "pendiente" in txt or "no_demostrable" in txt or "parcial" in txt
    assert inf["pq"].startswith("no_declarada_nunca")


def test_sin_evidencia_marca_pendiente(tmp_path):
    inf = construir_informe(evidencia=tmp_path)
    assert all(sec["datos"]["estado"] == "pendiente_evidencia"
               for sec in inf["secciones"].values())
    assert len(inf["hallazgos_abiertos"]) == len(SECCIONES)
