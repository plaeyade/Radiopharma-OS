"""F88 - Building Environmental Management Engine (BEME), Capitulo 35 del MVP.

Componentes canonicos (35.5): Environmental Sensor Manager, HVAC Manager,
Differential Pressure Manager, Utility Manager, Air Quality Manager, Alarm
Manager, Validation Engine, Reporting Service.

Filosofia canonica (35.3): el BEME monitorea/registra/analiza/genera eventos;
NO controla fisicamente (el control queda en los sistemas industriales).

Zonas: derivadas de los espacios reales registrados en F81 (plantas BIND).
Objetivos de presion/temperatura/humedad/clasificacion: OBJETIVOS DE DISENO
declarados (buenas practicas radiofarmacia: cuartos calientes negativos, pasillos
intermedios), NO mediciones. Sensores: estado honesto pendiente_telemetria
(sin SCADA conectado; memoria 3). Utilidades: leidas de la evidencia F86
(fuente citada). Alarmas: V&V con vectores sinteticos DECLARADOS (no son
lecturas reales).
"""
import json, hashlib, os, datetime

EV = "/mnt/agents/work/evidencia_v072/fase88"
F86 = "/mnt/agents/work/evidencia_v072/fase86/utilidades_completas_f86.json"

# Zonas (espacios reales F81) con objetivos de diseno DECLARADOS.
# dP en Pa respecto a exterior (0). Radiofarmacia: cascada negativa hacia
# cuartos calientes; areas de yodo mas negativas (declarado).
ZONAS = [
    {"id": "PB-BUNKER-CICLOTRON", "nivel": "planta_baja", "clasificacion": "controlada_no_limpia",
     "dP_Pa": -5, "T_C": [18, 26], "HR_pct": [30, 65], "ACH": 6},
    {"id": "PB-RADIOFARMACIA-RESGUARDO", "nivel": "planta_baja", "clasificacion": "controlada",
     "dP_Pa": -15, "T_C": [18, 25], "HR_pct": [30, 60], "ACH": 10},
    {"id": "PB-GAMMA-KNIFE", "nivel": "planta_baja", "clasificacion": "controlada",
     "dP_Pa": -5, "T_C": [18, 26], "HR_pct": [30, 65], "ACH": 6},
    {"id": "PB-LINAC", "nivel": "planta_baja", "clasificacion": "controlada",
     "dP_Pa": -5, "T_C": [18, 26], "HR_pct": [30, 65], "ACH": 6},
    {"id": "N1-CUARTO-CALIENTE-PET", "nivel": "primer_nivel", "clasificacion": "C_ISO8_declarada",
     "dP_Pa": -30, "T_C": [18, 24], "HR_pct": [30, 60], "ACH": 20},
    {"id": "N1-INYECCIONES", "nivel": "primer_nivel", "clasificacion": "D_declarada",
     "dP_Pa": -10, "T_C": [18, 26], "HR_pct": [30, 65], "ACH": 8},
    {"id": "N1-PASILLO-RF", "nivel": "primer_nivel", "clasificacion": "controlada",
     "dP_Pa": -15, "T_C": [18, 26], "HR_pct": [30, 65], "ACH": 8},
    {"id": "N2-CUARTO-YODO", "nivel": "segundo_nivel", "clasificacion": "controlada_extractada",
     "dP_Pa": -40, "T_C": [18, 25], "HR_pct": [30, 60], "ACH": 20},
    {"id": "N2-CUARTO-CALIENTE", "nivel": "segundo_nivel", "clasificacion": "C_ISO8_declarada",
     "dP_Pa": -30, "T_C": [18, 24], "HR_pct": [30, 60], "ACH": 20},
    {"id": "N2-CONSULTORIOS", "nivel": "segundo_nivel", "clasificacion": "no_controlada",
     "dP_Pa": 0, "T_C": [18, 27], "HR_pct": [30, 70], "ACH": 4},
    {"id": "N3-BIOLOGIA-MOLECULAR", "nivel": "tercer_nivel", "clasificacion": "controlada",
     "dP_Pa": -10, "T_C": [18, 25], "HR_pct": [30, 60], "ACH": 10},
]

SENSORES_POR_ZONA = ["temperatura", "humedad", "presion_diferencial"]


def md5_file(p, chunk=1 << 20):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(chunk), b""):
            h.update(blk)
    return h.hexdigest()


def construir_beme():
    sensores = []
    for z in ZONAS:
        for v in SENSORES_POR_ZONA:
            sensores.append({"zona": z["id"], "variable": v,
                             "estado": "pendiente_telemetria",  # honesto: sin SCADA
                             "calibracion": "pendiente_declarada"})
    # cascada: monotonia negativa hacia zonas calientes por nivel
    checks = []
    cc = next(z for z in ZONAS if z["id"] == "N1-CUARTO-CALIENTE-PET")
    pa = next(z for z in ZONAS if z["id"] == "N1-PASILLO-RF")
    inj = next(z for z in ZONAS if z["id"] == "N1-INYECCIONES")
    checks.append({"check": "cascada_N1_cuarto_caliente_mas_negativo_que_pasillo",
                    "ok": cc["dP_Pa"] < pa["dP_Pa"]})
    checks.append({"check": "cascada_N1_pasillo_negativo_vs_exterior", "ok": pa["dP_Pa"] < 0})
    checks.append({"check": "cascada_N1_pasillo_mas_negativo_que_inyecciones",
                    "ok": pa["dP_Pa"] < inj["dP_Pa"]})
    yo = next(z for z in ZONAS if z["id"] == "N2-CUARTO-YODO")
    checks.append({"check": "cascada_N2_yodo_el_mas_negativo",
                    "ok": yo["dP_Pa"] <= min(z["dP_Pa"] for z in ZONAS)})
    return sensores, checks


def evaluar_alarmas(lecturas_sinteticas):
    """V&V del Alarm Manager con vectores sinteticos DECLARADOS (no reales)."""
    eventos = []
    for l in lecturas_sinteticas:
        z = next(x for x in ZONAS if x["id"] == l["zona"])
        if l["variable"] == "temperatura" and not (z["T_C"][0] <= l["valor"] <= z["T_C"][1]):
            eventos.append({"tipo": "desviacion_temperatura", "zona": l["zona"], "valor": l["valor"]})
        if l["variable"] == "humedad" and not (z["HR_pct"][0] <= l["valor"] <= z["HR_pct"][1]):
            eventos.append({"tipo": "desviacion_humedad", "zona": l["zona"], "valor": l["valor"]})
        if l["variable"] == "presion_diferencial" and l["valor"] > z["dP_Pa"] + 10:
            eventos.append({"tipo": "perdida_de_presion", "zona": l["zona"], "valor": l["valor"]})
    return eventos


def main():
    os.makedirs(EV, exist_ok=True)
    sensores, checks = construir_beme()
    util = json.load(open(F86))
    # V&V alarmas: vectores sinteticos declarados
    vectores = [
        {"zona": "N1-CUARTO-CALIENTE-PET", "variable": "temperatura", "valor": 21.0},   # ok
        {"zona": "N1-CUARTO-CALIENTE-PET", "variable": "temperatura", "valor": 27.5},   # alta
        {"zona": "N2-CUARTO-YODO", "variable": "presion_diferencial", "valor": -5.0},   # perdida
        {"zona": "PB-LINAC", "variable": "humedad", "valor": 72.0},                     # alta
        {"zona": "N2-CONSULTORIOS", "variable": "temperatura", "valor": 22.0},          # ok
    ]
    eventos = evaluar_alarmas(vectores)
    ev = {
        "fase": "F88", "fecha_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "componente": "BEME (Building Environmental Management Engine) - Capitulo 35",
        "filosofia_35_3": "monitorea/registra/analiza/genera eventos; NO controla fisicamente",
        "zonas": ZONAS,
        "sensores": {"total": len(sensores), "detalle": sensores,
                      "estado_honesto": "pendiente_telemetria (sin SCADA/OPC UA conectado; memoria 3)"},
        "hvac_manager": {"fuente_cargas": "F86 (DWSIM/analitico)",
                          "carga_cuarto_caliente_kW": util["hvac_cuarto_caliente_kW"],
                          "renovaciones_objetivo": {z["id"]: z["ACH"] for z in ZONAS}},
        "utility_manager": {"fuente": "evidencia F86 (citada)",
                             "costo_utilidades_mxn_lote": util["totales"]["costo_utilidades_mxn_lote"]},
        "differential_pressure": {"objetivos_declarados_Pa": {z["id"]: z["dP_Pa"] for z in ZONAS},
                                    "coherencia_cascada": checks},
        "air_quality": {"clasificaciones_declaradas": {z["id"]: z["clasificacion"] for z in ZONAS},
                         "nota": "conteo de particulas pendiente_instrumentacion (honesto)"},
        "alarm_manager": {"vv_vectores_sinteticos_declarados": vectores,
                           "eventos_generados": eventos},
        "integraciones": {"adquisicion": "OPC UA/MQTT/Modbus (35.14) - pendiente_telemetria",
                           "facility_twin": "35.15", "operational_twin": "35.16",
                           "asset_registry": "35.6 vinculacion declarada"},
        "estado": "completada_motor_validado",
        "advertencias": [
            "Objetivos ambientales son DE DISENO declarados, no mediciones; sensores pendiente_telemetria.",
            "Vectores de alarma sinteticos declarados para V&V; no son lecturas reales.",
            "El BEME no controla HVAC (35.3); 18.10: alarmas no son decisiones operativas.",
        ],
    }
    outp = os.path.join(EV, "beme_f88.json")
    json.dump(ev, open(outp, "w"), ensure_ascii=False, indent=1)
    regp = os.path.join(EV, "registro_beme_f88.jsonl")
    prev = ""
    if os.path.exists(regp):
        lines = open(regp).read().strip().splitlines()
        if lines:
            prev = hashlib.md5(lines[-1].encode()).hexdigest()
    entry = {"ts": ev["fecha_utc"], "fase": "F88", "evento": "implementacion_beme_cap35",
             "version": "1.0", "md5_evidencia": md5_file(outp), "prev": prev}
    entry["md5"] = hashlib.md5(json.dumps(entry, sort_keys=True).encode()).hexdigest()
    with open(regp, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(json.dumps({"evidencia": outp, "n_eventos_vv": len(eventos), "md5": entry["md5"]}, indent=1))


if __name__ == "__main__":
    main()
