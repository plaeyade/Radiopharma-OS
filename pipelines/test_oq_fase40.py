"""Pruebas del informe OQ de fase 40 (evidencia real F38/F39/F42)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oq_fase40 as f40  # noqa: E402

EV = Path("/mnt/agents/work/evidencia_v072")


def test_informe_real_parcial_honesto():
    rep = f40.construir_informe(EV)
    assert rep["estado"] == "oq_parcial_honesto"
    nombres = {i["nombre"]: i["estado"] for i in rep["items"]}
    assert nombres["f38_plano_real"] == "parcial"
    assert nombres["f39_cotizaciones"] == "ejecutado"
    assert nombres["f42_mc_real"] == "parcial"


def test_f42_declara_segfaults_y_triple_real():
    it = f40.verificar_f42(EV)
    assert it["estado"] == "parcial"
    assert "3/6 semillas" in it["detalle"]
    assert "segfault" in it["detalle"]
    assert "comparación triple real" in it["detalle"]
    assert "30000" in it["detalle"] or "30 000" in it["detalle"] \
        or "historias" in it["detalle"]


def test_f38_hallazgo_negativo_alzados():
    it = f40.verificar_f38(EV)
    assert it["estado"] == "parcial"
    assert "sin alzados" in it["detalle"]
    assert "pendiente_verificacion" in it["detalle"]


def test_sin_evidencia_es_pendiente_no_fabricado(tmp_path):
    rep = f40.construir_informe(tmp_path)
    assert rep["estado"] == "oq_no_demostrable"
    assert all(i["estado"] == "pendiente" for i in rep["items"])


def test_pq_nunca_declarada_y_main(tmp_path):
    rep = f40.construir_informe(EV)
    assert "no_declarada_nunca" in rep["pq"]
    out = tmp_path / "f40.json"
    sys.argv = ["oq_fase40.py", "--evidencia", str(EV), "--out", str(out)]
    rc = f40.main()
    escrito = json.loads(out.read_text())
    assert rc == 0  # parcial honesto no es fracaso
    assert escrito["estado"] == "oq_parcial_honesto"
