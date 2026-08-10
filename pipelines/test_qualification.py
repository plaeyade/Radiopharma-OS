"""Pruebas del pipeline de calificación DQ/IQ/OQ/PQ (Informe 14.9)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qualification as q  # noqa: E402


def test_dq_documentos_y_trazabilidad():
    rep = q.dq()
    assert rep["ok"], [c for c in rep["checks"] if not c["ok"]]
    assert "14.9" in rep["nota"]


def test_iq_instalacion():
    rep = q.iq()
    assert rep["ok"], [c["detalle"] for c in rep["checks"] if not c["ok"]]


def test_oq_casos_funcionales():
    rep = q.oq()
    nombres = {c["nombre"] for c in rep["checks"]}
    assert "oq_yield_eob_conocido" in nombres
    assert "oq_qc_release_conforme" in nombres
    assert rep["ok"], [c["detalle"] for c in rep["checks"] if not c["ok"]]


def test_reporte_pq_honesto_y_exit(tmp_path):
    rep = q.construir_reporte()
    pq = [e for e in rep["etapas"] if e["etapa"] == "PQ"][0]
    assert pq["ok"] is None  # nunca se declara superada
    assert "nunca la declara" in pq["nota"]
    assert rep["veredicto"] in ("calificado_dq_iq_oq", "no_calificado")
    sys.argv = ["qualification.py", "--out", str(tmp_path / "q.json")]
    rc = q.main()
    escrito = json.loads((tmp_path / "q.json").read_text())
    assert rc == (0 if escrito["veredicto"] == "calificado_dq_iq_oq" else 1)
