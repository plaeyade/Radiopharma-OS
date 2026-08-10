"""
Tests del Process Twin químico (caps. 22-24): Reaction Engine,
Purification Engine, Formulation Engine y cadena e2e.
"""
from __future__ import annotations

import math
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.application.synthesis_service import (SynthesisCatalog,
                                               SynthesisService)
from app.domain.formulation_engine import (FormulacionInvalida,
                                           simular_formulacion)
from app.domain.purification_engine import (PurificacionInvalida,
                                            simular_purificacion)
from app.domain.reaction_engine import (ProtocoloInvalido, arrhenius_k,
                                        conversion_primer_orden,
                                        simular_reaccion, validar_protocolo)
from app.main import app

HL = 109.77  # 18F


@pytest.fixture()
def svc() -> SynthesisService:
    return SynthesisService()


@pytest.fixture()
def proto(svc):
    return svc.catalog.reaction("fdg_18f_synthesis")


# ------------------------------------------------------------- catálogo
class TestCatalogo:
    def test_carga_protocolos(self, svc):
        assert svc.catalog.reaction("fdg_18f_synthesis").version == "1.0.0"
        assert svc.catalog.purification("fdg_18f_purification").version == "1.0.0"
        assert svc.catalog.formulation("fdg_18f_formulation").version == "1.0.0"

    def test_protocolos_versionados_y_honestos(self, svc):
        # 22.6/23.6/24.6 + honestidad de datos: bibliográficos no validados
        for p in (svc.catalog.reaction("fdg_18f_synthesis"),):
            assert p.validated is False
            assert "bibliográficos" in p.source


# ------------------------------------------------------------- cinética
class TestCinetica:
    def test_arrhenius_sin_ea_es_constante(self, proto):
        from app.domain.synthesis_entities import KineticParams
        k = KineticParams("primer_orden", 0.9, 0.05, 25.0, 0.0)
        assert arrhenius_k(k, 85.0) == pytest.approx(0.05)

    def test_arrhenius_aumenta_con_temperatura(self, proto):
        k25 = arrhenius_k(proto.kinetic, 25.0)
        k85 = arrhenius_k(proto.kinetic, 85.0)
        assert k85 > k25
        # Ea=60 kJ/mol: factor esperado ~58 entre 25 °C y 85 °C
        # (exp(Ea/R * (1/298.15 - 1/358.15)) = exp(4.06))
        assert 40.0 < k85 / k25 < 80.0

    def test_conversion_primer_orden(self, proto):
        c0 = conversion_primer_orden(proto.kinetic, 0.0, 85.0)
        c_inf = conversion_primer_orden(proto.kinetic, 1e6, 85.0)
        assert c0 == pytest.approx(0.0)
        assert c_inf == pytest.approx(proto.kinetic.conversion_max, rel=1e-3)


# ------------------------------------------------------------- validación
class TestValidacionProtocolo:
    def test_protocolo_catalogo_valido(self, proto):
        assert validar_protocolo(proto, fecha_lote=date(2026, 8, 10)) == []

    def test_reactivo_vencido_detiene(self, proto):
        from dataclasses import replace
        malo = replace(proto.reagents[0], caducidad="2020-01-01")
        p = replace(proto, reagents=(malo,) + proto.reagents[1:])
        errores = validar_protocolo(p, fecha_lote=date(2026, 8, 10))
        assert any("vencido" in e for e in errores)

    def test_secuencia_vacia_detiene(self, proto):
        from dataclasses import replace
        p = replace(proto, steps=())
        assert any("secuencia vacía" in e for e in validar_protocolo(p))

    def test_modelo_no_registrado_detiene(self, proto):
        from dataclasses import replace
        k = replace(proto.kinetic, modelo="segundo_orden")
        p = replace(proto, kinetic=k)
        assert any("no registrado" in e for e in validar_protocolo(p))


# ------------------------------------------------------------- simulación
class TestReaccion:
    def test_decaimiento_por_etapa(self, svc, proto):
        # 22.13: actividad recalculada en cada etapa (exp(-lambda*dt))
        r = svc.reaction("fdg_18f_synthesis", 10.0,
                         fecha_lote=date(2026, 8, 10))
        lam = math.log(2) / HL
        s0 = r.stages[0]
        assert s0.activity_after_decay_gbq == pytest.approx(
            10.0 * math.exp(-lam * s0.duration_min), rel=1e-9)

    def test_conversion_aplica_en_etapa_reaccion(self, svc):
        r = svc.reaction("fdg_18f_synthesis", 10.0,
                         fecha_lote=date(2026, 8, 10))
        assert r.conversion is not None and 0 < r.conversion <= 0.9
        sr = [s for s in r.stages if s.kind == "reaccion"][0]
        assert sr.detalle["modelo"] == "primer_orden"
        assert sr.activity_out_gbq == pytest.approx(
            sr.activity_after_decay_gbq * sr.efficiency, rel=1e-9)

    def test_monotonia_temporal(self, svc):
        r = svc.reaction("fdg_18f_synthesis", 10.0,
                         fecha_lote=date(2026, 8, 10))
        assert r.final_activity_gbq < r.eob_activity_gbq
        reloj = 0.0
        for s in r.stages:
            assert s.inicio_min == pytest.approx(reloj, abs=1e-3)
            reloj = s.fin_min

    def test_eficiencia_global_menor_que_decay(self, svc):
        r = svc.reaction("fdg_18f_synthesis", 10.0,
                         fecha_lote=date(2026, 8, 10))
        lam = math.log(2) / HL
        solo_decay = math.exp(-lam * r.total_time_min)
        assert r.eficiencia_global < solo_decay
        assert r.rendimiento_quimico == pytest.approx(
            r.eficiencia_global / solo_decay, rel=1e-9)

    def test_incertidumbre_propagada(self, svc):
        # 22.21: la incertidumbre de la actividad inicial se propaga
        r = svc.reaction("fdg_18f_synthesis", 10.0, 0.05,
                         fecha_lote=date(2026, 8, 10))
        assert r.incertidumbre_final_gbq == pytest.approx(
            0.05 * r.final_activity_gbq, rel=1e-9)

    def test_eob_no_positiva_detiene(self, svc):
        with pytest.raises(ProtocoloInvalido):
            svc.reaction("fdg_18f_synthesis", 0.0)

    def test_auditoria_22_24(self, svc):
        r = svc.reaction("fdg_18f_synthesis", 10.0, operador="op1",
                         motivo="prueba", lote="L-1",
                         fecha_lote=date(2026, 8, 10))
        a = r.auditoria
        assert a["operador"] == "op1" and a["lote"] == "L-1"
        assert a["version"] == "1.0.0" and a["motivo"] == "prueba"


# ------------------------------------------------------------- purificación
class TestPurificacion:
    def test_cadena_recuperaciones(self, svc):
        r = svc.purification("fdg_18f_purification", 5.0)
        esperado_decay = math.exp(-math.log(2) / HL * r.total_time_min)
        prod_rec = 1.0
        for s in r.stages:
            prod_rec *= s.recovery
        assert r.final_activity_gbq == pytest.approx(
            5.0 * esperado_decay * prod_rec, rel=1e-9)
        assert r.eficiencia_recuperacion < esperado_decay

    def test_impurezas_reducidas_por_etapa(self, svc):
        imp = {"K2.2.2_residual": 100.0, "fluoruro_libre": 50.0}
        r = svc.purification("fdg_18f_purification", 5.0, imp)
        assert r.impurezas_remanentes["K2.2.2_residual"] == pytest.approx(
            100.0 * (1 - 0.9) * (1 - 0.6), rel=1e-9)
        assert r.impurezas_remanentes["fluoruro_libre"] == pytest.approx(
            50.0 * (1 - 0.85), rel=1e-9)

    def test_operacion_desconocida_detiene(self):
        from app.domain.purification_engine import (PurificationProtocol,
                                                    PurificationStep)
        p = PurificationProtocol("x", "1", "FDG", HL,
                                 (PurificationStep("filtrado", 1.0, 0.9),),
                                 (), False, "test")
        with pytest.raises(PurificacionInvalida):
            simular_purificacion(p, 1.0)


# ------------------------------------------------------------- formulación
class TestFormulacion:
    def test_dilucion_y_concentracion(self, svc):
        r = svc.formulation("fdg_18f_formulation", 3.0, 3.0)
        assert r.factor_dilucion == pytest.approx(10.0 / 3.0, rel=1e-9)
        esperado = 3.0 * math.exp(-math.log(2) / HL * 10.0)
        assert r.final_activity_gbq == pytest.approx(esperado, rel=1e-9)
        assert r.concentracion_final_gbq_ml == pytest.approx(
            esperado / 10.0, rel=1e-9)

    def test_limite_concentracion_detiene(self, svc):
        with pytest.raises(FormulacionInvalida):
            svc.formulation("fdg_18f_formulation", 60.0, 3.0)  # > 5 GBq/ml

    def test_volumen_excedido_detiene(self, svc):
        with pytest.raises(FormulacionInvalida):
            svc.formulation("fdg_18f_formulation", 1.0, 5.0)  # 5+7 > 10 ml

    def test_excipiente_vencido_detiene(self, svc):
        with pytest.raises(FormulacionInvalida):
            svc.formulation("fdg_18f_formulation", 1.0, 2.0,
                            fecha_lote=date(2031, 1, 1))


# ------------------------------------------------------------- cadena e2e
class TestE2E:
    def test_cadena_completa(self, svc):
        r = svc.synthesis_e2e("fdg_18f_synthesis", "fdg_18f_purification",
                              "fdg_18f_formulation", 10.0,
                              impurezas_iniciales={"K2.2.2_residual": 80.0},
                              fecha_lote=date(2026, 8, 10))
        assert r["final_activity_gbq"] < 10.0
        assert r["concentracion_final_gbq_ml"] > 0
        # consistencia entre motores (22.17/23.17)
        assert r["purification"]["input_activity_gbq"] == pytest.approx(
            r["reaction"]["final_activity_gbq"], rel=1e-12)
        assert r["formulation"]["input_activity_gbq"] == pytest.approx(
            r["purification"]["final_activity_gbq"], rel=1e-12)

    def test_radiofarmaco_incompatible_detiene(self, svc):
        from app.domain.synthesis_entities import ReactionProtocol
        from app.application.synthesis_service import SynthesisCatalog
        import json, tempfile, pathlib
        raw = json.loads((pathlib.Path(
            __file__).parents[1] / "data" / "synthesis_protocols.json").read_text())
        raw["formulation_protocols"][0]["radiopharmaceutical"] = "OTRO"
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(raw, f)
            path = pathlib.Path(f.name)
        svc2 = SynthesisService(SynthesisCatalog(path))
        with pytest.raises(ProtocoloInvalido):
            svc2.synthesis_e2e("fdg_18f_synthesis", "fdg_18f_purification",
                               "fdg_18f_formulation", 10.0)


# ------------------------------------------------------------- API
class TestApi:
    def test_protocols_endpoint(self):
        c = TestClient(app)
        r = c.get("/api/v1/synthesis/protocols")
        assert r.status_code == 200
        kinds = {p["kind"] for p in r.json()}
        assert kinds == {"reaction", "purification", "formulation"}

    def test_reaction_endpoint(self):
        c = TestClient(app)
        r = c.post("/api/v1/synthesis/reaction", json={
            "protocol_id": "fdg_18f_synthesis", "eob_activity_gbq": 10.0,
            "operador": "test", "fecha_lote": "2026-08-10"})
        assert r.status_code == 200
        body = r.json()
        assert body["conversion"] is not None
        assert body["auditoria"]["operador"] == "test"

    def test_e2e_endpoint(self):
        c = TestClient(app)
        r = c.post("/api/v1/synthesis/e2e", json={
            "reaction_id": "fdg_18f_synthesis",
            "purification_id": "fdg_18f_purification",
            "formulation_id": "fdg_18f_formulation",
            "eob_activity_gbq": 10.0, "operador": "test",
            "impurezas_iniciales": {"K2.2.2_residual": 80.0},
            "fecha_lote": "2026-08-10"})
        assert r.status_code == 200
        body = r.json()
        assert body["final_activity_gbq"] < 10.0
        assert body["validated"] is False  # honestidad: sin validar in-situ

    def test_protocolo_inexistente_404(self):
        c = TestClient(app)
        r = c.post("/api/v1/synthesis/reaction", json={
            "protocol_id": "no_existe", "eob_activity_gbq": 1.0,
            "operador": "test"})
        assert r.status_code == 404
