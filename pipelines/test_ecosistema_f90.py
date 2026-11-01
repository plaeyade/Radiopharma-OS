import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ecosistema_f90 as E


def test_contrato_kiube():
    tf = E.cargar_termino_fuente()
    assert tf["doble_haz"]["corriente_total_igual_a_max"]
    assert tf["rendimiento_neutrones_n_p"]["18O(p,n)"]["v"] == 6.9e-3


def test_plan_dentro_y_fuera_de_presupuesto():
    tf = E.cargar_termino_fuente(); pres = {"corriente_max_uA": 300, "uAh_semana": 12000}
    ok = E.evaluar_plan([{"isotopo": "F18", "corridas_semana": 10, "horas": 2, "corriente_uA": 300, "doble_haz": True}], tf, pres)
    assert ok["cumple"] and abs(ok["uso_presupuesto"] - 0.5) < 1e-9
    mal = E.evaluar_plan([{"isotopo": "F18", "corridas_semana": 25, "horas": 2, "corriente_uA": 300, "doble_haz": True}], tf, pres)
    assert not mal["cumple"]
    alta = E.evaluar_plan([{"isotopo": "F18", "corridas_semana": 1, "horas": 1, "corriente_uA": 400, "doble_haz": True}], tf, pres)
    assert not alta["cumple"]


def test_neutrones_por_uAh():
    tf = E.cargar_termino_fuente()
    r = E.evaluar_plan([{"isotopo": "F18", "corridas_semana": 1, "horas": 1, "corriente_uA": 1, "doble_haz": False}], tf,
                       {"corriente_max_uA": 300, "uAh_semana": 12000})
    assert abs(r["neutrones_semana"] / (3600e-6 / 1.602176634e-19 * 6.9e-3) - 1) < 1e-9
