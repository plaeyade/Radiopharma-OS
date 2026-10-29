#!/usr/bin/env python3
"""F95 — V&V del CDDME (cap. 32). 4 pruebas."""
import json, math, os, sys

sys.path.insert(0, "/mnt/agents/work/rpos25/pipelines")
import cddme_f95 as f

EV = "/mnt/agents/work/evidencia_v072/fase95/cddme_f95.json"


def test_decay_calculator_exacto():
    # A(109.77 min) = A0/2 exactamente; A(0)=A0; monótono decreciente
    assert abs(f.actividad(7400.0, 109.77) - 3700.0) < 1e-6
    assert f.actividad(7400.0, 0.0) == 7400.0
    assert f.actividad(1000.0, 60.0) < f.actividad(1000.0, 30.0)
    try:
        f.actividad(100.0, -5.0)
        assert False
    except ValueError:
        pass


def test_asignacion_validaciones_32_21():
    lote = f.Lote("L1", 7400.0, 480.0, "liberado")
    d = f.asignar_dosis(lote, "D1", 370.0, 510, "PET-CT")
    assert d["trazable"] and d["lote"] == "L1"
    # no liberado → bloqueado (32.15)
    lote_p = f.Lote("L2", 7400.0, 480.0, "pendiente")
    try:
        f.asignar_dosis(lote_p, "D2", 100.0, 500, "PET-CT")
        assert False
    except ValueError as e:
        assert "lote_no_liberado" in str(e)
    # actividad insuficiente
    try:
        f.asignar_dosis(lote, "D3", 99999.0, 510, "PET-CT")
        assert False
    except ValueError as e:
        assert "actividad_insuficiente" in str(e)
    # programación no vigente
    try:
        f.asignar_dosis(lote, "D4", 100.0, 100.0, "PET-CT")
        assert False
    except ValueError:
        pass


def test_secuencia_entrega_admin_y_reprogramacion():
    lote = f.Lote("L1", 7400.0, 480.0, "liberado")
    d = f.asignar_dosis(lote, "D1", 370.0, 510, "PET-CT")
    agenda = []
    p = f.programar_paciente(agenda, "PAC-1", "PET-CT", 540, "alta", "D1")
    # administrar sin entrega → error
    try:
        f.registrar_administracion(d, lote, p, 540, "op")
        assert False
    except ValueError:
        pass
    try:
        f.registrar_entrega(d, 530, 520)  # llegada antes de salida
        assert False
    except ValueError:
        pass
    f.registrar_entrega(d, 525, 535)
    adm = f.registrar_administracion(d, lote, p, 540, "op")
    # 30 min de decaimiento desde preparación: 370·2^(−30/109.77) ≈ 305.8
    esperado = 370.0 * 2 ** (-30.0 / f.T12_F18_MIN)
    assert abs(adm["actividad_administrada_mbq"] - esperado) < 0.01
    assert p["estado"] == "completado"
    # propuesta de reprogramación: nunca auto-aplicada (32.11)
    prop = f.proponer_reprogramacion(
        lote, [{"paciente_id_interno": "P", "horario_min": 700, "estado": "programado"}], 60)
    assert prop["tipo"] == "propuesta_reprogramacion"
    assert prop["requiere_confirmacion_usuario_autorizado"] is True
    assert prop["auto_aplicada"] is False
    prop2 = f.proponer_reprogramacion(
        lote, [{"paciente_id_interno": "P", "horario_min": 700, "estado": "programado"}], 5)
    assert prop2["tipo"] == "sin_accion"


def test_evidencia_y_auditoria():
    assert os.path.exists(EV)
    ev = json.load(open(EV, encoding="utf-8"))
    assert ev["lote_no_liberado_bloqueado"] is True
    assert ev["reporte"]["dosis_administradas"] == 5
    assert 0 < ev["reporte"]["aprovechamiento_pct"] < 100
    assert ev["propuesta_reprogramacion_32_11"]["auto_aplicada"] is False
    assert ev["decay_calculator"]["t12_f18_min"] == 109.77
    reg = [json.loads(l) for l in
           open("/mnt/agents/work/evidencia_v072/fase95/registro_cddme_f95.jsonl",
                encoding="utf-8").read().splitlines() if l.strip()]
    for prev, cur in zip(reg, reg[1:]):
        assert cur["prev_md5"] == prev["md5"]
    assert sum(1 for r in reg if r["accion"] == "administrar") == 5
    # pacientes solo con identificador interno (privacidad)
    assert all(r["paciente_id_interno"] is None or
               r["paciente_id_interno"].startswith("PAC-VV") for r in reg)
