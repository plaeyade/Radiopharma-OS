"""Pruebas de 10.17 (etiquetas OCI en imágenes) y 10.18 (registro)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import artifact_registry as ar  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_dockerfiles_con_etiquetas_oci_10_17():
    dockerfiles = sorted(ROOT.glob("services/*/Dockerfile"))
    assert len(dockerfiles) == 8
    for df in dockerfiles:
        texto = df.read_text()
        for clave in ["org.opencontainers.image.version",
                      "org.opencontainers.image.revision",
                      "org.opencontainers.image.created",
                      "BUILD_COMMIT", "BUILD_DATE", "BUILD_VERSION"]:
            assert clave in texto, f"{df}: falta {clave} (10.17)"


def test_registro_y_verificacion(tmp_path):
    artefacto = tmp_path / "paquete.zip"
    artefacto.write_bytes(b"contenido-artefacto")
    reg_path = tmp_path / "registry.json"
    entrada = ar.registrar(artefacto, "zip", "v1.0.0", reg_path)
    assert entrada["sha256"]
    assert entrada["version"] == "v1.0.0"
    res = ar.verificar(artefacto, reg_path)
    assert res["integridad_verificada"] is True
    assert res["entradas_coincidentes"] == ["paquete.zip:v1.0.0"]


def test_registro_inmutable_10_18(tmp_path):
    artefacto = tmp_path / "a.zip"
    artefacto.write_bytes(b"x")
    reg_path = tmp_path / "registry.json"
    ar.registrar(artefacto, "zip", "v1", reg_path)
    with pytest.raises(ValueError, match="10.18"):
        ar.registrar(artefacto, "zip", "v1", reg_path)
    # otra versión genera nueva entrada (nunca sobrescribe)
    ar.registrar(artefacto, "zip", "v2", reg_path)
    reg = json.loads(reg_path.read_text())
    assert len(reg["artefactos"]) == 2


def test_verificacion_falla_con_artefacto_modificado(tmp_path):
    artefacto = tmp_path / "b.zip"
    artefacto.write_bytes(b"original")
    reg_path = tmp_path / "registry.json"
    ar.registrar(artefacto, "zip", "v1", reg_path)
    artefacto.write_bytes(b"alterado")
    assert ar.verificar(artefacto, reg_path)["integridad_verificada"] is False


def test_proveedor_osrm_honesto():
    sys.path.insert(0, str(ROOT / "services" / "process_service"))
    from app.domain.logistics import GeoPoint
    from app.infrastructure.routing import (OsrmRoutingProvider,
                                            OsrmUnavailable)
    # una URL no http(s) se rechaza en construcción — el routing nunca
    # se inventa; y un servidor caído propaga la excepción real
    with pytest.raises((ValueError, AttributeError)):
        OsrmRoutingProvider(base_url=None)
    with pytest.raises(ValueError, match="http"):
        OsrmRoutingProvider(base_url="ftp://no-valido")

    def _http_caido():
        raise ConnectionError("connection refused: servidor OSRM caído")

    prov = OsrmRoutingProvider(base_url="http://osrm-caido:5000",
                               http_factory=_http_caido)
    with pytest.raises(ConnectionError, match="refused"):
        prov.road_time(GeoPoint(lat=40.4, lon=-3.7),
                       GeoPoint(lat=41.4, lon=2.1))
