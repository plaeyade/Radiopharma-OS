"""F86 - Utilidades completas de planta auxiliar (Informe canonico 5.12) y costo
unitario por lote. Extiende F85 (evaporacion, LN2, aire comprimido, blanketing) con:
gases de proceso (Ar sintesis), vapor de planta (reheat HVAC), HVAC del cuarto
caliente (carga termica por renovaciones de aire), y costo por lote en MXN.

Base termodinamica: salidas reales de DWSIM registradas en evidencias F84/F85
(nunca recalculadas aqui; se leen de los JSON de evidencia - fuente citada).
Las cargas HVAC/vapor/gases son ANALITICAS con supuestos declarados.
Tarifas: SUPUESTOS declarados en MXN - tarifas CFE reales y tipo de cambio siguen
pendientes (declarado en pendientes del proyecto); nunca se presentan como reales.
"""
import json, hashlib, os, datetime

EV = "/mnt/agents/work/evidencia_v072/fase86"
F85 = "/mnt/agents/work/evidencia_v072/fase85/nrtl_utilidades_f85.json"

TARIFAS_DECLARADAS_MXN = {
    "electricidad_kWh": 2.50,     # supuesto declarado; tarifa CFE real pendiente
    "LN2_kg": 8.0,
    "N2_gas_Nm3": 15.0,
    "Ar_gas_Nm3": 60.0,
    "agua_m3": 30.0,
    "vapor_kWh_termico": 0.90,
    "nota": "supuestos declarados - NO son tarifas oficiales CFE ni cotizaciones",
}

SUPUESTOS = {
    "horas_lote": 8,
    "cuarto_caliente": {"volumen_m3": 25, "renovaciones_h": 20, "deltaT_C": 8,
                          "rho_aire_kg_m3": 1.2, "cp_aire_kJ_kgK": 1.005},
    "vapor_planta": {"reheat_kW": 3.0, "horas": 8},
    "gases_proceso": {"N2_blanketing_Nm3": 5.0, "Ar_sintesis_Nm3": 1.0},
    "agua_proceso_m3": 0.5,
}


def md5_file(p, chunk=1 << 20):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(chunk), b""):
            h.update(blk)
    return h.hexdigest()


def main():
    os.makedirs(EV, exist_ok=True)
    base = json.load(open(F85))
    u85 = base["utilidades"]
    s = SUPUESTOS
    cc = s["cuarto_caliente"]
    # HVAC cuarto caliente: Q = rho*cp*(V*ACH/3600)*dT
    q_hvac_kw = cc["rho_aire_kg_m3"] * cc["cp_aire_kJ_kgK"] * (cc["volumen_m3"] * cc["renovaciones_h"] / 3600) * cc["deltaT_C"]
    kwh_hvac = q_hvac_kw * s["horas_lote"]
    kwh_vapor_planta = s["vapor_planta"]["reheat_kW"] * s["vapor_planta"]["horas"]

    items = [
        {"concepto": "evaporacion_agua_enriquecida", "cantidad": u85["vapor_o_electricidad_evaporacion"]["kWh_lote"],
         "unidad": "kWh", "tarifa": TARIFAS_DECLARADAS_MXN["electricidad_kWh"], "fuente": "DWSIM IAPWS (F84/F85)"},
        {"concepto": "trampa_fria_LN2", "cantidad": u85["LN2_trampa_fria"]["kg_LN2_lote"],
         "unidad": "kg LN2", "tarifa": TARIFAS_DECLARADAS_MXN["LN2_kg"], "fuente": "DWSIM PR78 hfg (F85)"},
        {"concepto": "aire_comprimido", "cantidad": u85["aire_comprimido"]["kWh_lote"],
         "unidad": "kWh", "tarifa": TARIFAS_DECLARADAS_MXN["electricidad_kWh"], "fuente": "analitico isotermo (F85)"},
        {"concepto": "HVAC_cuarto_caliente", "cantidad": round(kwh_hvac, 2),
         "unidad": "kWh", "tarifa": TARIFAS_DECLARADAS_MXN["electricidad_kWh"], "fuente": "analitico declarado (F86)"},
        {"concepto": "vapor_planta_reheat", "cantidad": round(kwh_vapor_planta, 2),
         "unidad": "kWh_t", "tarifa": TARIFAS_DECLARADAS_MXN["vapor_kWh_termico"], "fuente": "supuesto declarado (F86)"},
        {"concepto": "N2_blanketing", "cantidad": s["gases_proceso"]["N2_blanketing_Nm3"],
         "unidad": "Nm3", "tarifa": TARIFAS_DECLARADAS_MXN["N2_gas_Nm3"], "fuente": "supuesto declarado (F85)"},
        {"concepto": "Ar_sintesis", "cantidad": s["gases_proceso"]["Ar_sintesis_Nm3"],
         "unidad": "Nm3", "tarifa": TARIFAS_DECLARADAS_MXN["Ar_gas_Nm3"], "fuente": "supuesto declarado (F86)"},
        {"concepto": "agua_proceso", "cantidad": s["agua_proceso_m3"],
         "unidad": "m3", "tarifa": TARIFAS_DECLARADAS_MXN["agua_m3"], "fuente": "supuesto declarado (F86)"},
    ]
    for it in items:
        it["costo_mxn_lote"] = round(it["cantidad"] * it["tarifa"], 2)
    total = round(sum(it["costo_mxn_lote"] for it in items), 2)
    kwh_elec = round(sum(it["cantidad"] for it in items if it["unidad"] == "kWh"), 2)

    ev = {
        "fase": "F86",
        "fecha_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "alcance": "utilidades completas 5.12 + costo unitario por lote (MXN)",
        "fuentes": {"F85": "evidencia_v072/fase85/nrtl_utilidades_f85.json",
                     "F84": "evidencia_v072/fase84/dwsim_service_f84.json"},
        "tarifas_declaradas_mxn": TARIFAS_DECLARADAS_MXN,
        "supuestos": SUPUESTOS,
        "hvac_cuarto_caliente_kW": round(q_hvac_kw, 3),
        "items": items,
        "totales": {"costo_utilidades_mxn_lote": total,
                     "electricidad_kWh_lote": kwh_elec,
                     "nota": "solo utilidades; excluye insumos (agua enriquecida, reactivos) y mano de obra"},
        "estado": "completada",
        "advertencias": [
            "Tarifas son SUPUESTOS declarados: tarifa CFE real y tipo de cambio MXN siguen pendientes (lista de pendientes del proyecto).",
            "HVAC y vapor de planta son analiticos con supuestos declarados, no mediciones.",
            "El total cubre SOLO utilidades; no es el costo del lote completo.",
            "Registro documental; no es decision operativa (18.10).",
        ],
    }
    outp = os.path.join(EV, "utilidades_completas_f86.json")
    json.dump(ev, open(outp, "w"), ensure_ascii=False, indent=1)
    regp = os.path.join(EV, "registro_f86.jsonl")
    prev = ""
    if os.path.exists(regp):
        lines = open(regp).read().strip().splitlines()
        if lines:
            prev = hashlib.md5(lines[-1].encode()).hexdigest()
    entry = {"ts": ev["fecha_utc"], "fase": "F86",
             "evento": "utilidades_completas_5_12_costo_lote",
             "md5_evidencia": md5_file(outp), "prev": prev}
    entry["md5"] = hashlib.md5(json.dumps(entry, sort_keys=True).encode()).hexdigest()
    with open(regp, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(json.dumps({"evidencia": outp, "total_mxn_lote": total, "md5": entry["md5"]}, indent=1))


if __name__ == "__main__":
    main()
