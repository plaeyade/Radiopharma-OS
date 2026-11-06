#!/usr/bin/env python3
"""
F99 — Cap. 35: Building Environmental Management Engine (BEME)
Radiopharma OS — HVAC, presiones diferenciales, utilidades críticas,
monitoreo ambiental integral.

Reglas canónicas:
- 35.3: BEME monitorea/registra/analiza/genera eventos; NO controla
  sistemas HVAC ni utilidades (el control físico es de los sistemas
  industriales).
- 35.6: cada sensor vinculado al Asset Registry (F97/F98).
- 35.13: toda variable registra timestamp, valor, calidad y origen.
- 35.21: antes de aceptar una medición se verifica rango, consistencia
  temporal, estado del sensor y calidad; las anomalías generan eventos
  de validación.
- 35.23: auditoría (usuario, sensor, área, acción, fecha) jsonl md5 ALCOA+.
- 35.20: recomendaciones IA ≠ mediciones reales (diferenciadas).
- Memoria 3: sin sensores físicos → adquisición 35.14 (OPC UA/MQTT/Modbus)
  pendiente declarada; mediciones de demostración sintéticas v&v.
Base: sincroniza zonas/parámetros declarados de F88 y activos de F97.
"""
import hashlib, json, os, sys
from datetime import datetime, timezone

FASE = "fase99"
EV_DIR = "/mnt/agents/work/evidencia_v072/fase99"
EV_ROOT = "/mnt/agents/work/evidencia_v072"

FILOSOFIA_35_3 = ("BEME monitorea, registra, analiza y genera eventos; "
                  "no controla directamente HVAC ni utilidades.")

RANGOS = {  # rangos permitidos declarados (validación 35.21)
    "temperatura_C": (-10.0, 50.0),
    "humedad_pct": (0.0, 100.0),
    "presion_diferencial_Pa": (-100.0, 100.0),
    "particulas_0_5um_m3": (0.0, 1e9),
    "voltaje_V": (0.0, 500.0),
}


# ---------- 35.6 Environmental Sensor Manager ------------------------------------
class SensorManager:
    def __init__(self, activos_validos):
        self.sensores = {}
        self.activos_validos = set(activos_validos)

    def registrar(self, id_sensor, ubicacion, variable, activo_vinculado,
                  calibracion="pendiente_declarada"):
        if activo_vinculado not in self.activos_validos:
            raise ValueError(f"activo_no_registrado:{activo_vinculado}")
        s = {"id": id_sensor, "ubicacion": ubicacion, "variable": variable,
             "estado": "sin_conexion_pendiente_sensor",
             "calibracion": calibracion, "activo_vinculado": activo_vinculado}
        self.sensores[id_sensor] = s
        return s


# ---------- 35.13 medición con calidad y origen ---------------------------------------
def medicion(id_sensor, variable, valor, origen, calidad="buena_vv"):
    return {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "sensor": id_sensor, "variable": variable, "valor": valor,
            "calidad": calidad, "origen": origen}  # 35.13


# ---------- 35.21 Validation Engine ------------------------------------------------------
def validar_medicion(m, sensor, prev_timestamp=None):
    errores = []
    lo, hi = RANGOS[m["variable"]]
    if not (lo <= m["valor"] <= hi):
        errores.append(f"rango:{m['valor']} fuera de [{lo},{hi}]")
    if sensor["estado"].startswith("fuera_servicio"):
        errores.append("estado_sensor:fuera_de_servicio")
    if m["calidad"] not in ("buena_vv", "buena"):
        errores.append(f"calidad_dato:{m['calidad']}")
    if prev_timestamp and m["timestamp_utc"] < prev_timestamp:
        errores.append("consistencia_temporal:timestamp_retrocede")
    return errores


# ---------- 35.12 Alarm Manager -------------------------------------------------------------
class AlarmManager:
    def __init__(self):
        self.alarmas = []

    def generar(self, area, tipo, detalle):
        a = {"area": area, "tipo": tipo, "detalle": detalle,
             "timestamp_utc": datetime.now(timezone.utc).isoformat(),
             "estado": "activa"}
        self.alarmas.append(a)
        return a


def run():
    os.makedirs(EV_DIR, exist_ok=True)
    reg_path = os.path.join(EV_DIR, "registro_beme_f99.jsonl")

    def audit(usuario, sensor, area, accion):  # 35.23
        prev = "0" * 64
        if os.path.exists(reg_path):
            ls = [l for l in open(reg_path, encoding="utf-8").read().splitlines() if l.strip()]
            if ls:
                prev = json.loads(ls[-1])["md5"]
        e = {"fecha_utc": datetime.now(timezone.utc).isoformat(), "usuario": usuario,
             "sensor": sensor, "area": area, "accion": accion, "prev_md5": prev}
        e["md5"] = hashlib.md5(json.dumps(e, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with open(reg_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")

    # Sincronización: zonas F88 (35.11) y activos F97 (35.6)
    f88 = json.load(open(f"{EV_ROOT}/fase88/beme_f88.json", encoding="utf-8"))
    f97 = json.load(open(f"{EV_ROOT}/fase97/facility_f97.json", encoding="utf-8"))
    zonas = [{"id": z["id"], "clasificacion": z["clasificacion"],
              "objetivos": {"dP_Pa": z["dP_Pa"], "T_C": z["T_C"], "HR_pct": z["HR_pct"],
                            "ACH": z["ACH"]},
              "estado_actual": "pendiente_telemetria_declarado",
              "config_version": "f88_v1"} for z in f88["zonas"]]

    # Activos válidos: equipos del ALME (F98) / Facility (F97)
    activos = ["HVAC-UMA-01", "CICLOTRON-IBA-KIUBE", "HPLC-01"]
    sm = SensorManager(activos)
    sm.registrar("S-T-QC-01", "laboratorio_QC", "temperatura_C", "HVAC-UMA-01")
    sm.registrar("S-DP-CY-01", "cuarto_yodo", "presion_diferencial_Pa", "HVAC-UMA-01")
    sm.registrar("S-V-EL-01", "cuarto_electrico", "voltaje_V", "CICLOTRON-IBA-KIUBE")
    audit("rpos_pipeline_f99", "sensores", "planta", "registro_sensores_35_6")

    # Mediciones v&v (35.13) y validación (35.21)
    alarm = AlarmManager()
    aceptadas, eventos = [], []
    m_ok = medicion("S-T-QC-01", "temperatura_C", 22.4, "vector_vv_sintetico_declarado")
    err = validar_medicion(m_ok, sm.sensores["S-T-QC-01"])
    aceptadas.append((m_ok, err))
    m_mala = medicion("S-DP-CY-01", "presion_diferencial_Pa", -250.0,
                      "vector_vv_sintetico_declarado")
    err2 = validar_medicion(m_mala, sm.sensores["S-DP-CY-01"])
    if err2:
        eventos.append({"medicion": m_mala, "errores": err2})
        alarm.generar("cuarto_yodo", "perdida_presion",
                      f"dP=-250 Pa fuera de rango (vv 35.21)")
    audit("rpos_pipeline_f99", "S-DP-CY-01", "cuarto_yodo", "evento_validacion_35_21")

    # 35.7 HVAC / 35.10 utilidades (estado independiente, sin control)
    hvac = {"umas": [{"id": "HVAC-UMA-01", "zonas_atendidas": len(zonas),
                      "estado": "pendiente_scada_declarado"}],
            "fuente_parametros": "SCADA cuando esté disponible (35.7)"}
    utilidades = {s["servicio"]: {"estado": "pendiente_telemetria_declarado"}
                  for s in f97["utility_manager"]["servicios"]}

    out = {
        "fase": FASE, "capitulo_canonico": 35,
        "componentes_35_5": ["Environmental Sensor Manager", "HVAC Manager",
                             "Differential Pressure Manager", "Utility Manager",
                             "Air Quality Manager", "Alarm Manager",
                             "Validation Engine", "Reporting Service"],
        "filosofia_35_3": FILOSOFIA_35_3,
        "zonas_ambientales_35_11": {"total": len(zonas), "zonas": zonas},
        "sensores_35_6": {"total": len(sm.sensores),
                          "detalle": list(sm.sensores.values())},
        "hvac_manager_35_7": hvac,
        "utility_manager_35_10": {"total": len(utilidades), "servicios": utilidades},
        "validacion_35_21": {"aceptadas": len([1 for _, e in aceptadas if not e]),
                             "eventos": eventos},
        "alarmas_35_12": alarm.alarmas,
        "adquisicion_35_14": {"protocolos": ["OPC UA", "MQTT", "Modbus"],
                              "estado": "pendiente_sensores_declarado"},
        "integraciones": {"facility_twin_35_15": "fase97",
                          "qc_twin_35_18": "consulta ambiental disponible",
                          "economic_twin_35_19": "consumo energético F86"},
        "pendientes_declarados": [
            "Adquisición industrial 35.14 — sin sensores físicos (memoria 3).",
            "InfluxDB/PostgreSQL/MinIO (35.22) pendientes.",
            "Contadores de partículas (35.9) — instrumentación no instalada, declarada.",
        ],
    }
    with open(os.path.join(EV_DIR, "beme_engine_f99.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    audit("rpos_pipeline_f99", "beme", "planta", "exportacion")

    print(json.dumps({"zonas": len(zonas), "sensores": len(sm.sensores),
                      "eventos_validacion": len(eventos), "alarmas": len(alarm.alarmas)},
                     indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
