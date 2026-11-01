import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import tablero_produccion as T

PLAN = {
    "plan": [{"isotopo": "F18", "corriente_uA": 300, "horas": 2.0, "doble_haz": True,
              "eob_GBq_por_corrida_teorico": 1000.0, "eob_GBq_semana_teorico": 10000.0}],
    "cumple": True,
    "advertencias": [],
}


class QcFalso:
    def release(self, protocolo, resultados, lote=""):
        oos = sum(v is not None and v < 95 for k, v in resultados.items() if k.endswith("_pct"))
        rec = "rechazo" if oos else ("liberacion" if resultados else "revision")
        return SimpleNamespace(recomendacion=rec, n_oos=oos, n_pendientes=0 if resultados else 8, motivos=())


def lote(**c):
    base = {"lote": "L1", "isotopo": "F18", "fecha": "2026-11-02", "corriente_uA": 300, "horas": 2.0,
            "doble_haz": True, "eob_GBq": 600.0}
    return base | c


def test_rendimientos_y_qc():
    t = T.tablero([lote(eos_GBq=330.0, minutos_eob_a_eos=30, qc={"pureza_radioquimica_pct": 98})], PLAN, QcFalso())
    (f,) = t["lotes"]
    assert f["eob_teorico_GBq"] == 1000.0 and f["rendimiento_blanco"] == 0.6
    esperado = 330 / (600 * math.exp(-math.log(2) / 109.77 * 30))
    assert f["rendimiento_sintesis_corr"] == round(esperado, 3)
    assert f["qc"] == "liberacion" and t["resumen"]["F18"]["qc"]["liberacion"] == 1


def test_escala_por_corriente_y_saturacion():
    f = T.evaluar_lote(lote(corriente_uA=150, horas=1.0), {"F18": PLAN["plan"][0]}, QcFalso())
    sat = (1 - math.exp(-math.log(2) / 109.77 * 60)) / (1 - math.exp(-math.log(2) / 109.77 * 120))
    assert f["eob_teorico_GBq"] == round(1000 * 0.5 * sat, 1)


def test_alertas_oos_y_sin_protocolo():
    t = T.tablero([lote(eob_GBq=1200.0, qc={"pureza_radioquimica_pct": 90}),
                   lote(lote="G1", isotopo="Ga68", doble_haz=False, corriente_uA=40, horas=1.0, eob_GBq=40)],
                  PLAN, QcFalso())
    f18, ga = t["lotes"]
    assert f18["qc"] == "rechazo" and any("> teórico" in a for a in f18["alertas"])
    assert ga["qc"] == "SIN_PROTOCOLO" and ga["eob_teorico_GBq"] is None


def test_lote_incompleto_falla():
    with pytest.raises(ValueError, match="faltan eob_GBq"):
        T.tablero([{k: v for k, v in lote().items() if k != "eob_GBq"}], PLAN, QcFalso())


def test_html_y_ejemplo_con_servicios_reales(tmp_path):
    lotes = json.loads((Path(__file__).parent / "fixtures" / "lotes_ejemplo.json").read_text(encoding="utf-8"))
    t = T.tablero(lotes)
    assert [f["qc"] for f in t["lotes"]] == ["liberacion", "rechazo", "SIN_PROTOCOLO"]
    h = T.a_html(t)
    assert "<tr class='rechazo'>" in h and "FDG-2611-01" in h
