"""Tests Fase 8 — registrador de batería científica en DL + RCAE.

Sin servicios: Http se sustituye por un doble; los artefactos se fabrican
en tmp_path con contenido real conocido. La regla canónica bajo prueba:
SIN artefactos reales NO hay registro (nunca evidencia inventada).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "registrar_bateria_rcae", RAIZ / "scripts" / "registrar_bateria_rcae.py")
mod = importlib.util.module_from_spec(_spec)
sys.modules["registrar_bateria_rcae"] = mod
_spec.loader.exec_module(mod)


def _fabricar_out(tmp_path: Path) -> Path:
    """Artefactos reales mínimos con la forma del informe de batería."""
    out = tmp_path / "out"
    (out / "talys_f18").mkdir(parents=True)
    (out / "gate_mc").mkdir()
    (out / "elmer_termico").mkdir()
    (out / "talys_f18" / "rp009018.tot").write_text(
        "# TALYS\n  8.0  330.27\n 18.0  46.42\n")
    (out / "gate_mc" / "resultado_mc.json").write_text(json.dumps(
        {"edep_total_mev": 31980.9}))
    (out / "elmer_termico" / "scalars.dat").write_text("8.01e5 3.41e5\n")
    (out / "elmer_termico" / "elmer.log").write_text("ALL DONE\n")
    informe = {"secciones": {"runtimes_cientificos": {
        "TALYS": {"ejecucion": "real", "puntos_sigma": 21,
                  "rango_mev": [8.0, 18.0],
                  "desviacion_media_abs_vs_iaea2021_pct": 23.6},
        "OpenGATE_Geant4": {"ejecucion": "real",
                            "motor": "OpenGATE 10.1.1 / Geant4",
                            "particula": "proton", "energia_mev": 16.0,
                            "historias": 2000, "semilla": 12345,
                            "blanco": "agua", "edep_total_mev": 31980.9,
                            "edep_esperada_mev": 32000.0,
                            "desviacion_pct": -0.06},
        "ElmerFEM": {"ejecucion": "real", "t_max_k": 801785.5,
                     "t_mean_k": 341015.7, "caso": "blanco 610,5 W"}}}}
    (out / "prueba_teorica_fisica.json").write_text(json.dumps(informe))
    return out


def test_sha256_file_real(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"contenido-real")
    assert mod.sha256_file(f) == hashlib.sha256(b"contenido-real").hexdigest()


def test_sha256_file_inexistente_falla(tmp_path):
    with pytest.raises(FileNotFoundError):
        mod.sha256_file(tmp_path / "no_existe.bin")


def test_build_registros_desde_artefactos(tmp_path):
    out = _fabricar_out(tmp_path)
    regs = mod.build_registros(out)
    assert [r["kind"] for r in regs] == [
        "talys_excitation", "monte_carlo", "elmer_thermal"]
    # hashes reales de los artefactos fabricados
    esperado = hashlib.sha256(
        (out / "talys_f18" / "rp009018.tot").read_bytes()).hexdigest()
    assert regs[0]["artefactos"]["rp009018.tot"] == esperado
    # MC marcado review_required: nunca cumplimiento pleno automático
    assert regs[1]["review_required"] is True
    assert "review_required" not in regs[0]


def test_build_registros_sin_artefactos_falla(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "prueba_teorica_fisica.json").write_text(json.dumps(
        {"secciones": {"runtimes_cientificos": {
            "TALYS": {"ejecucion": "real", "puntos_sigma": 21,
                      "rango_mev": [8.0, 18.0],
                      "desviacion_media_abs_vs_iaea2021_pct": 23.6},
            "OpenGATE_Geant4": {"ejecucion": "no_disponible"},
            "ElmerFEM": {"ejecucion": "no_disponible"}}}}))
    with pytest.raises(FileNotFoundError):
        mod.build_registros(out)


def test_build_registros_runtime_no_ejecutado_falla(tmp_path):
    out = _fabricar_out(tmp_path)
    informe = json.loads((out / "prueba_teorica_fisica.json").read_text())
    informe["secciones"]["runtimes_cientificos"]["TALYS"]["ejecucion"] = \
        "fallo_real"
    (out / "prueba_teorica_fisica.json").write_text(json.dumps(informe))
    with pytest.raises(RuntimeError, match="TALYS"):
        mod.build_registros(out)


class FakeHttp:
    """Doble de Http: emula DL + compliance en memoria, exige token."""

    def __init__(self) -> None:
        self.token = None
        self.simulaciones: dict[str, dict] = {}
        self.requisitos: set[str] = set()
        self.evidencias: dict[str, dict] = {}
        self.vinculos: dict[str, list[str]] = {}
        self.evaluaciones: list[dict] = []
        self.n = 0

    def post(self, puerto, path, payload, timeout=120):
        assert self.token == "jwt-real" or path.endswith("/login")
        if puerto == 8003 and path == "/api/v1/simulations":
            self.n += 1
            sid = f"SIM-{self.n:012d}"
            rec = {**payload, "simulation_id": sid,
                   "created_at": "2026-08-14T00:00:00+00:00",
                   "record_hash": hashlib.sha256(
                       json.dumps(payload, sort_keys=True).encode()
                   ).hexdigest()}
            self.simulaciones[sid] = rec
            return rec
        if puerto == 8005 and path == "/api/v1/compliance/requirements":
            assert payload["requisito_id"] not in self.requisitos
            self.requisitos.add(payload["requisito_id"])
            return payload
        if puerto == 8005 and path == "/api/v1/compliance/evidences":
            self.evidencias[payload["evidencia_id"]] = payload
            return payload
        if puerto == 8005 and path.endswith("/link"):
            rid = path.split("/")[-2]
            self.vinculos.setdefault(rid, []).append(payload["evidencia_id"])
            return payload
        if puerto == 8005 and path.endswith("/assess"):
            rid = path.split("/")[-2]
            # 49.18: sin evidencia vinculada no se puede evaluar
            assert self.vinculos.get(rid), "evaluación sin evidencia"
            self.evaluaciones.append({"requisito_id": rid, **payload})
            return payload
        raise AssertionError(f"ruta inesperada: {puerto}{path}")

    def get(self, puerto, path, timeout=60):
        if puerto == 8005 and path == "/api/v1/compliance/requirements":
            return [{"requisito_id": r} for r in sorted(self.requisitos)]
        if puerto == 8003 and path.endswith("/verify"):
            sid = path.split("/")[-2]
            return {"simulation_id": sid, "integrity_ok": True,
                    "record_hash": self.simulaciones[sid]["record_hash"]}
        raise AssertionError(f"ruta inesperada: {puerto}{path}")


def test_registrar_flujo_completo(tmp_path):
    out = _fabricar_out(tmp_path)
    regs = mod.build_registros(out)
    http = FakeHttp()
    http.token = "jwt-real"
    mod.asegurar_requisitos(http, "admin")
    resumen = mod.registrar(http, regs, "admin", "qp.fisica")

    assert len(resumen["simulaciones"]) == 3
    assert all(s["integridad_verificada"] for s in resumen["simulaciones"])
    # evidencia vinculada a su origen real con el hash del registro
    for ev in http.evidencias.values():
        sid = ev["referencia"]
        assert ev["origen"] == f"data_lake_service:/api/v1/simulations/{sid}"
        assert ev["hash_sha256"] == http.simulaciones[sid]["record_hash"]
    # MC queda cumple_parcial (review_required), los demás cumple
    estados = {e["requisito_id"]: e["estado"] for e in http.evaluaciones}
    assert estados["REQ-PT-19.14-MC"] == "cumple_parcial"
    assert estados["REQ-PT-19.12-TALYS"] == "cumple"
    assert estados["REQ-PT-8.11-TERM"] == "cumple"


def test_asegurar_requisitos_nunca_recrea(tmp_path):
    http = FakeHttp()
    http.token = "jwt-real"
    http.requisitos.add("REQ-PT-19.12-TALYS")  # ya existe (versionado)
    mod.asegurar_requisitos(http, "admin")
    # solo se crean los otros dos; el existente no se toca
    assert http.requisitos == {"REQ-PT-19.12-TALYS", "REQ-PT-19.14-MC",
                               "REQ-PT-8.11-TERM"}
