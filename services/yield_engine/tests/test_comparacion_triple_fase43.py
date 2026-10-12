"""Tests F43 — comparación triple BERT / HP / OpenMC.

Estilo canónico de servicio: imports locales `from app...` (PYTHONPATH=.
según Makefile), sin acoplamiento a otros servicios.
"""
import json

import numpy as np
import pytest

from app.domain.comparacion_triple import (
    PataTally,
    comparar,
    phi_por_voxel,
    A_CM,
    V_CM3,
    Q_NS,
)

DIMS = (110, 110, 60)


def _mapa(semilla, escala=1.0, solo_concreto=False):
    rng = np.random.default_rng(semilla)
    m = rng.random(DIMS, dtype=np.float64) * escala
    if solo_concreto:
        mask = np.zeros(DIMS, dtype=bool)
        mask[25:85, 30:80, 15:45] = True
        m = m * mask
    return m


def test_phi_por_voxel_estimador_f35():
    counts = np.full(DIMS, 1.0e-6)
    pata = PataTally("X", counts, 1000)
    phi = phi_por_voxel(pata)
    esperado = 1.0e-9 * (2 * A_CM / 3.0) / V_CM3 * Q_NS
    assert phi.shape == DIMS
    assert np.isclose(phi[55, 55, 30], esperado, rtol=1e-12)


def test_comparar_dos_patas_identicas_delta_cero():
    counts = _mapa(1, solo_concreto=True)
    p1 = PataTally("FTFP_BERT", counts, 360_000)
    p2 = PataTally("FTFP_BERT_HP", counts.copy(), 360_000)
    r = comparar([p1, p2], referencia="FTFP_BERT")
    assert r["estado"] == "completado"
    assert r["patas_pendientes"] == []
    hp = r["patas"]["FTFP_BERT_HP"]
    assert hp["delta_rel_vs_referencia"] == pytest.approx(0.0, abs=1e-15)
    assert hp["dif_simetrica_mediana_voxel"] == pytest.approx(0.0, abs=1e-15)
    assert r["referencia"] == "FTFP_BERT"
    assert r["voxels_union"] == int((counts > 0).sum())


def test_comparar_delta_relativa_correcta():
    counts = _mapa(2, solo_concreto=True)
    p1 = PataTally("FTFP_BERT", counts, 360_000)
    p2 = PataTally("FTFP_BERT_HP", counts * 2.0, 160_000)
    r = comparar([p1, p2], referencia="FTFP_BERT")
    hp = r["patas"]["FTFP_BERT_HP"]
    # counts al doble y 160k vs 360k historias → suma/historia = 2·360/160 = 4,5×
    assert hp["delta_rel_vs_referencia"] == pytest.approx(3.5, rel=1e-9)
    assert r["patas"]["FTFP_BERT"]["delta_rel_vs_referencia"] == 0.0


def test_pata_pendiente_entorno_no_rompe():
    counts = _mapa(3, solo_concreto=True)
    p1 = PataTally("FTFP_BERT", counts, 360_000)
    p3 = PataTally("OpenMC", None, 0, estado="pendiente_entorno")
    r = comparar([p1, p3], referencia="FTFP_BERT")
    assert r["estado"] == "parcial_pendiente_entorno"
    assert r["patas_pendientes"] == ["OpenMC"]
    assert "OpenMC" not in r["patas"]  # nunca se fabrica la pata ausente


def test_desglose_por_componente_cubre_mascaras():
    counts = _mapa(4, solo_concreto=True)
    p1 = PataTally("FTFP_BERT", counts, 360_000)
    p2 = PataTally("FTFP_BERT_HP", counts * 1.05, 160_000)
    r = comparar([p1, p2], referencia="FTFP_BERT")
    comp = r["por_componente"]
    assert set(comp) >= {"muro_laberinto", "muro_oeste", "losa_techo", "losa_piso"}
    for nombre, patas in comp.items():
        assert set(patas) == {"FTFP_BERT", "FTFP_BERT_HP"}
        assert patas["FTFP_BERT_HP"]["delta_rel_vs_referencia"] == pytest.approx(
            1.05 * 360_000 / 160_000 - 1.0, rel=1e-9)


def test_formas_incompatibles_no_demostrable():
    p1 = PataTally("FTFP_BERT", np.zeros((10, 10, 10)), 1000)
    p2 = PataTally("FTFP_BERT_HP", np.zeros(DIMS), 1000)
    r = comparar([p1, p2], referencia="FTFP_BERT")
    assert r["estado"] == "no_demostrable"


def test_serializable_alcoa():
    counts = _mapa(5, solo_concreto=True)
    p1 = PataTally("FTFP_BERT", counts, 360_000)
    p2 = PataTally("FTFP_BERT_HP", counts * 0.9, 160_000)
    p3 = PataTally("OpenMC", None, 0, estado="pendiente_entorno")
    r = comparar([p1, p2, p3], referencia="FTFP_BERT")
    s = json.dumps(r, ensure_ascii=False)
    assert "FTFP_BERT" in s and "phi_media_union" in s
    assert r["estado"] == "parcial_pendiente_entorno"
