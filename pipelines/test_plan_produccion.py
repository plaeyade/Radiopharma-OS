"""Plan semanal contra el término fuente de Cyclotron-SIM y el presupuesto de blindaje de Zumaya."""
import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan_produccion as P  # noqa: E402


class RendimientoFijo:
    def compute(self, rx, blanco, e, i, minutos):
        return SimpleNamespace(eob_activity_gbq=i * minutos / 100, dataset_id=f"{rx}-prueba", relative_uncertainty=0.1)


def plan(**cambios):
    p = copy.deepcopy(P.PLAN_BASE)
    for i, c in cambios.items():
        p[int(i[1:])].update(c)
    return p


def test_plan_base_cumple_con_contratos_versionados():
    r = P.planificar(rendimiento=RendimientoFijo())
    assert r["cumple"], r["incumplimientos"]
    assert r["blindaje"]["uAh_semana"] == 10 * 2 * 300 + 3 * 1 * 40 + 1 * 4 * 40
    f18 = r["plan"][0]
    assert f18["eob_GBq_por_corrida_teorico"] == pytest.approx(2 * 150 * 120 / 100)   # dos blancos de 150 µA


@pytest.mark.parametrize(("cambio", "texto"), [
    ({"i1": {"doble_haz": True}}, "doble haz sólo con blancos F-18"),
    ({"i0": {"energia_MeV": 20.0}}, "no es 18.0 MeV"),
    ({"i0": {"energia_MeV": 15.0}}, "doble haz a energía fija"),
    ({"i2": {"corriente_uA": 350}}, "excede KIUBE 300"),
    ({"i0": {"corridas_semana": 20, "horas": 4.0}}, "presupuesto de blindaje"),
])
def test_incumplimientos(cambio, texto):
    r = P.planificar(plan(**cambio), rendimiento=RendimientoFijo())
    assert not r["cumple"]
    assert any(texto in x for x in r["incumplimientos"]), r["incumplimientos"]


def test_energia_variable_en_puertos_3_7_es_valida():
    r = P.planificar(plan(i1={"energia_MeV": 16.5}), rendimiento=RendimientoFijo())
    assert r["cumple"], r["incumplimientos"]


def test_contrato_de_presupuesto_ajeno_se_rechaza(tmp_path):
    f = tmp_path / "p.json"
    f.write_text(json.dumps({"contrato": "otro@1"}))
    with pytest.raises(ValueError):
        P.cargar_presupuesto(f)


def test_rendimiento_real_de_yield_engine():
    r = P.planificar()
    f18, ga68, cu64 = r["plan"]
    assert f18["dataset"].startswith("o18_p_n_f18") and f18["eob_GBq_por_corrida_teorico"] > 0
    assert ga68["dataset"].startswith("zn68_p_n_ga68") and cu64["dataset"].startswith("ni64_p_n_cu64")
