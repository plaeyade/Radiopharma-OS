"""Pruebas de la Fase 7 — Dashboards (Informe 18.11; EDS 6.17/6.18)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _cargar(nombre: str, ruta: Path):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = mod
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------- Streamlit
def test_streamlit_importable_sin_runtime_y_paneles():
    app = _cargar("streamlit_app", ROOT / "dashboard" / "streamlit_app.py")
    ids = [p["id"] for p in app.PANELES]
    assert ids == ["produccion", "optimizacion", "qc", "inventario",
                   "kpis", "telemetria", "plataforma"]
    tel = [p for p in app.PANELES if p["id"] == "telemetria"][0]
    assert "no consulta directamente el PLC" in tel["nota"]  # 6.18
    if not app.STREAMLIT_DISPONIBLE:
        with pytest.raises(RuntimeError, match="Streamlit"):
            app.main()


def test_data_client_apunta_a_apis_nunca_plc():
    fuente = (ROOT / "dashboard" / "data_client.py").read_text()
    assert "8002" in fuente and "8007" in fuente  # YE + Process
    assert "opc.tcp" not in fuente  # nunca OPC-UA directo (6.18)
    assert "PLC" in fuente  # documentado


# --------------------------------------------------------------- PyVista
def test_malla_blanco_y_campo_termico():
    pv_views = _cargar("pyvista_views", ROOT / "dashboard" / "pyvista_views.py")
    malla = pv_views.malla_blanco(radio_cm=1.0, espesor_cm=0.5)
    verts = malla["vertices"]
    assert verts.shape == (12, 48, 3)
    radios = np.hypot(verts[..., 0], verts[..., 1])
    assert radios == pytest.approx(1.0, abs=1e-12)
    campo = pv_views.campo_termico_analitico(malla, potencia_w=610.5)
    assert campo.min() > 293.15  # calentamiento real del blanco
    assert campo.shape == malla["z"].shape


def test_render_pyvista_honesto_sin_runtime():
    pv_views = _cargar("pyvista_views2", ROOT / "dashboard" / "pyvista_views.py")
    if not pv_views.PYVISTA_DISPONIBLE:
        malla = pv_views.malla_blanco()
        campo = pv_views.campo_termico_analitico(malla, 100.0)
        with pytest.raises(RuntimeError, match="PyVista"):
            pv_views.render_vista(malla, campo, "/tmp/x.html")


# -------------------------------------------------------------- ParaView
def test_export_vti_roundtrip(tmp_path):
    pve = _cargar("paraview_export", ROOT / "dashboard" / "paraview_export.py")
    campo = np.arange(60, dtype=float).reshape(3, 4, 5)
    r = pve.exportar_vti(campo, "edep_mev", tmp_path / "mc.vti")
    assert r["dimensiones"] == [3, 4, 5]
    leido = pve.leer_vti(tmp_path / "mc.vti")
    np.testing.assert_array_equal(leido, campo)


def test_export_vti_rechaza_no_3d(tmp_path):
    pve = _cargar("paraview_export2", ROOT / "dashboard" / "paraview_export.py")
    with pytest.raises(ValueError, match="3D"):
        pve.exportar_vti(np.zeros((3, 3)), "x", tmp_path / "x.vti")


# --------------------------------------------------------------- Grafana
def test_grafana_dashboard_paneles_canonicos_6_17():
    dash = json.loads((ROOT / "config" / "grafana" / "dashboards"
                       / "produccion_ciclotron.json").read_text())
    titulos = " ".join(p["title"].lower() for p in dash["panels"])
    for tema in ["ciclotrón", "temperatura del blanco", "presión",
                 "vacío", "energético", "producción"]:
        assert tema in titulos  # paneles canónicos 6.17
    assert len(dash["panels"]) == 6
    for p in dash["panels"]:
        for t in p["targets"]:
            assert "telemetry" in t["query"]  # bucket InfluxDB


def test_grafana_provisioning_valido():
    ds = yaml.safe_load((ROOT / "config" / "grafana" / "provisioning"
                         / "datasources" / "influxdb.yaml").read_text())
    assert ds["datasources"][0]["type"] == "influxdb"
    prov = yaml.safe_load((ROOT / "config" / "grafana" / "provisioning"
                           / "dashboards" / "radiopharma.yaml").read_text())
    assert prov["providers"][0]["type"] == "file"


def test_overlay_compose_dashboards():
    overlay = yaml.safe_load((ROOT / "docker-compose.dashboards.yml")
                             .read_text())
    assert set(overlay["services"]) == {"grafana", "streamlit"}
    env = overlay["services"]["streamlit"]["environment"]
    assert "YE_URL" in env and "TEL_URL" in env
    assert "PLC" not in json.dumps(env)  # 6.18
