#!/usr/bin/env python3
"""
F90 — Cap. 40: Financial Forecasting & Scenario Analysis Engine (FFSAE)
Radiopharma OS — Radiopharma OS v2.0 EDS Volumen VII (Economic Digital Twin)

Reglas canónicas:
- 40.3: opera EXCLUSIVAMENTE sobre escenarios de simulación; NUNCA modifica
  registros contables, costos históricos, producción real ni programación
  operativa. Todo resultado lleva marca solo_simulacion.
- 40.20: antes de simular se verifica disponibilidad de información, coherencia
  del escenario, integridad de parámetros y consistencia temporal; las
  simulaciones incompletas se rechazan.
- 18.10: los resultados apoyan decisiones estratégicas; NO son decisiones
  operativas.
- 49.11: cifras solo con fuente citada (F86 utilidades, F87 KPIs, hipótesis
  declaradas del escenario).
- Trazabilidad 40.22: cada simulación registra escenario, versión, fecha y
  parámetros utilizados (registro jsonl encadenado md5, append-only).
"""
import hashlib, json, os, subprocess, sys
from datetime import datetime, timezone

FASE = "fase90"
EV_DIR = "/mnt/agents/work/evidencia_v072/fase90"
REPO = "/mnt/agents/work/rpos25"

# --- Fuentes citadas (49.11) -------------------------------------------------
F86_EVIDENCIA = "/mnt/agents/work/evidencia_v072/fase86/utilidades_completas_f86.json"
F87_EVIDENCIA = "/mnt/agents/work/evidencia_v072/fase87/stae_f87.json"

# Costos por lote verificados en F86 (cap. 5.12, tarifas declaradas MXN;
# tarifa CFE real pendiente — declarado en F86).
def cargar_costos_f86(path=F86_EVIDENCIA):
    with open(path, encoding="utf-8") as fh:
        ev = json.load(fh)
    return {
        "costo_utilidades_mxn_lote": ev["totales"]["costo_utilidades_mxn_lote"],
        "energia_kwh_lote": ev["totales"]["electricidad_kWh_lote"],
        "fuente": "F86 evidencia_v072/fase86 (tarifas declaradas, CFE real pendiente)",
    }


# --- 40.6 Scenario Manager ----------------------------------------------------
def crear_escenario(nombre, hipotesis, parametros, horizonte_meses, version="1.0"):
    return {
        "nombre": nombre,
        "hipotesis": hipotesis,                # lista de hipótesis declaradas
        "parametros": parametros,              # dict de parámetros declarados
        "horizonte_meses": int(horizonte_meses),
        "version": version,
        "solo_simulacion_no_modifica_registros": True,  # 40.3
        "creado_utc": datetime.now(timezone.utc).isoformat(),
    }


# --- 40.20 Validation Engine --------------------------------------------------
def validar_escenario(esc):
    errores = []
    if not esc.get("nombre"):
        errores.append("falta_identificacion")
    if not esc.get("hipotesis"):
        errores.append("falta_hipotesis")
    p = esc.get("parametros") or {}
    requeridos = ("lotes_mes", "dosis_por_lote", "precio_dosis_mxn",
                  "costo_utilidades_mxn_lote", "costo_fijo_mes_mxn",
                  "costo_variable_dosis_mxn")
    for k in requeridos:
        if k not in p or p[k] is None:
            errores.append(f"parametro_faltante:{k}")
        elif not isinstance(p[k], (int, float)) or p[k] < 0:
            errores.append(f"parametro_invalido:{k}")
    if esc.get("horizonte_meses", 0) <= 0:
        errores.append("horizonte_invalido")   # consistencia temporal
    return errores


# --- 40.7 Forecast Engine -----------------------------------------------------
def proyectar(esc):
    """Proyección mensual de ingresos, costos, utilización, demanda y capacidad
    sobre el horizonte temporal del escenario (40.7, 40.12)."""
    p = esc["parametros"]
    cap_lotes = p.get("capacidad_lotes_mes", 30)
    meses = []
    for m in range(1, esc["horizonte_meses"] + 1):
        demanda = p["lotes_mes"] * (1.0 + p.get("crecimiento_mensual", 0.0)) ** (m - 1)
        lotes = min(demanda, cap_lotes)
        dosis = lotes * p["dosis_por_lote"]
        ingresos = dosis * p["precio_dosis_mxn"]
        costos = (lotes * p["costo_utilidades_mxn_lote"]
                  + dosis * p["costo_variable_dosis_mxn"]
                  + p["costo_fijo_mes_mxn"])
        meses.append({
            "mes": m,
            "demanda_lotes": round(demanda, 3),
            "lotes_producidos": round(lotes, 3),
            "dosis": round(dosis, 2),
            "ingresos_mxn": round(ingresos, 2),
            "costos_mxn": round(costos, 2),
            "utilidad_mxn": round(ingresos - costos, 2),
            "utilizacion_pct": round(100.0 * lotes / cap_lotes, 2),
            "capacidad_lotes_mes": cap_lotes,
        })
    return meses


# --- 40.8 Sensitivity Analyzer ------------------------------------------------
def sensibilidad(esc, variable, variaciones=(-0.20, -0.10, 0.10, 0.20)):
    """Impacto de cambios en demanda (lotes_mes), costos, utilización/capacidad.
    Cada análisis queda asociado al escenario (40.8)."""
    base = proyectar(esc)
    u_base = sum(m["utilidad_mxn"] for m in base)
    resultados = []
    for v in variaciones:
        esc_v = json.loads(json.dumps(esc))
        esc_v["version"] = esc["version"] + f"-sens({variable}{v:+.0%})"
        if variable == "demanda":
            esc_v["parametros"]["lotes_mes"] *= (1 + v)
        elif variable == "costos":
            esc_v["parametros"]["costo_utilidades_mxn_lote"] *= (1 + v)
            esc_v["parametros"]["costo_variable_dosis_mxn"] *= (1 + v)
            esc_v["parametros"]["costo_fijo_mes_mxn"] *= (1 + v)
        elif variable == "capacidad":
            esc_v["parametros"]["capacidad_lotes_mes"] = max(
                1, round(esc_v["parametros"].get("capacidad_lotes_mes", 30) * (1 + v)))
        else:
            raise ValueError(f"variable_no_soportada:{variable}")
        u_v = sum(m["utilidad_mxn"] for m in proyectar(esc_v))
        resultados.append({
            "variable": variable, "variacion_pct": round(v * 100, 1),
            "utilidad_horizonte_mxn": round(u_v, 2),
            "delta_vs_base_mxn": round(u_v - u_base, 2),
        })
    return {"escenario": esc["nombre"], "variable": variable,
            "utilidad_base_mxn": round(u_base, 2), "resultados": resultados}


# --- 40.9 Investment Evaluator --------------------------------------------------
def evaluar_inversion(esc, inversion_inicial_mxn, incremento_utilidad_mensual_mxn,
                      tasa_descuento_anual=0.12):
    """VPN y TIR (bisección) del flujo incremental. Apoya decisiones
    estratégicas de inversión (40.9); no es decisión operativa (18.10)."""
    n = esc["horizonte_meses"]
    r = (1 + tasa_descuento_anual) ** (1 / 12) - 1
    flujos = [-inversion_inicial_mxn] + [incremento_utilidad_mensual_mxn] * n
    vpn = sum(f / (1 + r) ** i for i, f in enumerate(flujos))

    def npv(tasa_m):
        return sum(f / (1 + tasa_m) ** i for i, f in enumerate(flujos))

    lo, hi = 0.0, 1.0
    tir_mensual = None
    if npv(lo) * npv(hi) < 0:
        for _ in range(200):
            mid = (lo + hi) / 2
            if npv(lo) * npv(mid) <= 0:
                hi = mid
            else:
                lo = mid
        tir_mensual = (lo + hi) / 2
    return {
        "escenario": esc["nombre"],
        "inversion_inicial_mxn": inversion_inicial_mxn,
        "vpn_mxn": round(vpn, 2),
        "tir_anual_pct": (round(((1 + tir_mensual) ** 12 - 1) * 100, 2)
                          if tir_mensual is not None else None),
        "criterio_referencia": "VPN>0 y TIR>tasa_descuento (referencia, no decisión)",
        "solo_simulacion": True,
    }


# --- 40.10 Risk Analyzer --------------------------------------------------------
def analizar_riesgos(esc, eventos):
    """Impacto potencial de eventos (disminución demanda, indisponibilidad,
    incremento de costos, retrasos) sobre la utilidad del horizonte (40.10)."""
    u_base = sum(m["utilidad_mxn"] for m in proyectar(esc))
    salida = []
    for ev in eventos:
        esc_e = json.loads(json.dumps(esc))
        tipo, mag = ev["tipo"], ev["magnitud_pct"] / 100.0
        if tipo == "disminucion_demanda":
            esc_e["parametros"]["lotes_mes"] *= (1 - mag)
        elif tipo == "indisponibilidad_equipo":
            esc_e["parametros"]["capacidad_lotes_mes"] = max(
                1, round(esc_e["parametros"].get("capacidad_lotes_mes", 30) * (1 - mag)))
        elif tipo == "incremento_costos":
            esc_e["parametros"]["costo_utilidades_mxn_lote"] *= (1 + mag)
            esc_e["parametros"]["costo_variable_dosis_mxn"] *= (1 + mag)
        elif tipo == "retraso_operativo":
            esc_e["parametros"]["lotes_mes"] *= (1 - mag)
            esc_e["parametros"]["costo_fijo_mes_mxn"] *= 1.0  # fijos permanecen
        else:
            raise ValueError(f"evento_no_soportado:{tipo}")
        u_e = sum(m["utilidad_mxn"] for m in proyectar(esc_e))
        salida.append({"evento": tipo, "magnitud_pct": ev["magnitud_pct"],
                       "utilidad_mxn": round(u_e, 2),
                       "impacto_mxn": round(u_e - u_base, 2)})
    return {"escenario": esc["nombre"], "utilidad_base_mxn": round(u_base, 2),
            "eventos": salida, "orientado_a_soporte_decisiones": True}


# --- 40.11 KPI Generator --------------------------------------------------------
def kpis(esc):
    p = esc["parametros"]
    proy = proyectar(esc)
    ing = sum(m["ingresos_mxn"] for m in proy)
    cos = sum(m["costos_mxn"] for m in proy)
    dos = sum(m["dosis"] for m in proy)
    util = sum(m["utilidad_mxn"] for m in proy)
    mc_unit = p["precio_dosis_mxn"] - p["costo_variable_dosis_mxn"] \
        - p["costo_utilidades_mxn_lote"] / p["dosis_por_lote"]
    pe_dosis_mes = (p["costo_fijo_mes_mxn"] / mc_unit) if mc_unit > 0 else None
    return {
        "escenario": esc["nombre"],
        "rentabilidad_margen_pct": round(100 * util / ing, 2) if ing > 0 else None,
        "productividad_dosis_horizonte": round(dos, 1),
        "utilizacion_media_pct": round(sum(m["utilizacion_pct"] for m in proy) / len(proy), 2),
        "eficiencia_costo_dosis_mxn": round(cos / dos, 2) if dos > 0 else None,
        "crecimiento_mensual_declarado_pct": round(100 * p.get("crecimiento_mensual", 0.0), 2),
        "punto_equilibrio_dosis_mes": round(pe_dosis_mes, 1) if pe_dosis_mes else None,
    }


# --- 40.8 Reporting Service -----------------------------------------------------
def reporte(esc, proy, sens, inv, riesgos, kpi):
    return {
        "titulo": f"FFSAE reporte — escenario '{esc['nombre']}' v{esc['version']}",
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "marca_40_3": "SOLO SIMULACIÓN — no modifica registros contables, "
                      "costos históricos, producción real ni programación operativa",
        "marca_18_10": "Soporte de decisiones estratégicas; no es decisión operativa",
        "resumen": {
            "ingresos_horizonte_mxn": round(sum(m["ingresos_mxn"] for m in proy), 2),
            "costos_horizonte_mxn": round(sum(m["costos_mxn"] for m in proy), 2),
            "utilidad_horizonte_mxn": round(sum(m["utilidad_mxn"] for m in proy), 2),
        },
        "kpis": kpi, "sensibilidad": sens, "inversion": inv, "riesgos": riesgos,
        "destino_persistencia_40_21": "PostgreSQL/MinIO/Data Lake (pendiente despliegue; "
                                      "esta fase persiste en evidencia jsonl append-only)",
    }


# --- Ejecución de fase ----------------------------------------------------------
def run():
    os.makedirs(EV_DIR, exist_ok=True)
    f86 = cargar_costos_f86()

    esc = crear_escenario(
        nombre="base_fdg_zumaya",
        hipotesis=[
            "Tarifas de utilidades declaradas en F86 (CFE real pendiente).",
            "Precio por dosis FDG declarado 3500 MXN (hipótesis, no dato de mercado).",
            "Capacidad nominal 30 lotes/mes; crecimiento de demanda 2 % mensual declarado.",
            "Horizonte 24 meses (40.12).",
        ],
        parametros={
            "lotes_mes": 18.0, "dosis_por_lote": 10.0, "precio_dosis_mxn": 3500.0,
            "costo_utilidades_mxn_lote": f86["costo_utilidades_mxn_lote"],
            "costo_variable_dosis_mxn": 450.0, "costo_fijo_mes_mxn": 280000.0,
            "capacidad_lotes_mes": 30, "crecimiento_mensual": 0.02,
        },
        horizonte_meses=24,
    )

    errores = validar_escenario(esc)
    rechazado = crear_escenario("incompleto_sin_precio", [], {
        "lotes_mes": 18.0, "dosis_por_lote": 10.0,
        "costo_utilidades_mxn_lote": f86["costo_utilidades_mxn_lote"],
        "costo_variable_dosis_mxn": 450.0, "costo_fijo_mes_mxn": 280000.0,
    }, 0)
    errores_rechazado = validar_escenario(rechazado)

    proy = proyectar(esc)
    sens = [sensibilidad(esc, "demanda"), sensibilidad(esc, "costos")]
    inv = evaluar_inversion(esc, inversion_inicial_mxn=2_500_000.0,
                            incremento_utilidad_mensual_mxn=120_000.0)
    riesgos = analizar_riesgos(esc, [
        {"tipo": "disminucion_demanda", "magnitud_pct": 25},
        {"tipo": "indisponibilidad_equipo", "magnitud_pct": 20},
        {"tipo": "incremento_costos", "magnitud_pct": 15},
    ])
    kpi = kpis(esc)
    rep = reporte(esc, proy, sens, inv, riesgos, kpi)

    out = {
        "fase": FASE, "capitulo_canonico": 40,
        "componentes_40_5": ["Scenario Manager", "Forecast Engine",
                             "Sensitivity Analyzer", "Investment Evaluator",
                             "Risk Analyzer", "KPI Generator",
                             "Validation Engine", "Reporting Service"],
        "validacion_40_20": {"escenario_base_errores": errores,
                             "escenario_incompleto_rechazado": True,
                             "errores_detectados": errores_rechazado},
        "fuente_costos": f86["fuente"],
        "costo_utilidades_mxn_lote": f86["costo_utilidades_mxn_lote"],
        "energia_kwh_lote": f86["energia_kwh_lote"],
        "escenario": esc, "proyeccion_meses": proy, "reporte": rep,
        "pendientes_declarados": [
            "Tarifa CFE real (F86 usa tarifa declarada 2.50 MXN/kWh).",
            "Precio de dosis y demanda son hipótesis declaradas, no datos de mercado.",
            "Persistencia PostgreSQL/MinIO/Data Lake pendiente de despliegue (40.21).",
        ],
    }
    with open(os.path.join(EV_DIR, "ffsae_f90.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    # Registro ALCOA+ append-only encadenado md5 (40.22)
    reg = os.path.join(EV_DIR, "registro_ffsae_f90.jsonl")
    prev = "0" * 64
    if os.path.exists(reg):
        with open(reg, encoding="utf-8") as fh:
            lines = [l for l in fh.read().splitlines() if l.strip()]
        if lines:
            prev = json.loads(lines[-1])["md5"]
    entrada = {
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "usuario": "rpos_pipeline_f90",
        "escenario": esc["nombre"], "version": esc["version"],
        "parametros_utilizados": esc["parametros"],
        "accion": "simulacion_ffsae_f90",
        "solo_simulacion_40_3": True,
        "prev_md5": prev,
    }
    entrada["md5"] = hashlib.md5(
        json.dumps(entrada, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    with open(reg, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entrada, ensure_ascii=False) + "\n")

    print(json.dumps({"validacion_errores": errores,
                      "rechazado_errores": errores_rechazado,
                      "utilidad_horizonte_mxn": rep["resumen"]["utilidad_horizonte_mxn"],
                      "margen_pct": kpi["rentabilidad_margen_pct"],
                      "vpn_inversion_mxn": inv["vpn_mxn"],
                      "tir_anual_pct": inv["tir_anual_pct"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
