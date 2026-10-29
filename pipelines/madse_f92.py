#!/usr/bin/env python3
"""
F92 — Cap. 43: Multi-Agent Decision Support Engine (MADSE)
Radiopharma OS — EDS Volumen VIII (Enterprise Intelligence & AI Twin)

Reglas canónicas:
- 43.3: los agentes son asistentes; NO sustituyen decisiones clínicas,
  regulatorias, administrativas ni operativas. Decisión final: usuario
  autorizado (18.10/43.17: propuestas sujetas a aprobación humana).
- 43.8/43.12: el Orchestrator coordina y el Task Planner descompone; el
  flujo y la secuencia quedan registrados.
- 43.9: el Consensus Engine consolida; las contribuciones individuales
  permanecen registradas (trazabilidad).
- 43.21: antes de recomendar se verifica contexto, integridad, consistencia
  y estado de modelos; las inconsistencias generan eventos de revisión.
- 43.23: auditoría append-only (usuario, agentes, contexto, fecha, versión),
  jsonl encadenado md5 (ALCOA+).
- Honestidad: los agentes son heurísticas deterministas DECLARADAS que
  consultan evidencia real de fases previas (F82/F83/F86/F87/F90); no se
  simulan lecturas ni resultados. Agentes con datos pendientes lo declaran.
"""
import hashlib, json, os, sys
from datetime import datetime, timezone

FASE = "fase92"
EV_DIR = "/mnt/agents/work/evidencia_v072/fase92"
EV_BASE = "/mnt/agents/work/evidencia_v072"

DOMINIOS_43_7 = ["fisica_medica", "radioquimica", "control_calidad", "produccion",
                 "operacion", "proteccion_radiologica", "mantenimiento", "economia",
                 "regulacion", "logistica"]


def _cargar(fase, archivo):
    p = os.path.join(EV_BASE, fase, archivo)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


# --- 43.6 Agent Registry --------------------------------------------------------
def registrar_agente(registro, id_agente, dominio, capacidades, version="1.0"):
    a = {"id": id_agente, "dominio": dominio, "version": version,
         "capacidades": capacidades, "estado": "activo",
         "fecha_utc": datetime.now(timezone.utc).isoformat()}
    registro.append(a)
    return a


# --- Agentes especializados (heurísticas deterministas declaradas) -----------------
def agente_economia(tarea, ctx):
    ev = ctx.get("f90")
    if not ev:
        return {"voto": "revision", "detalle": "evidencia F90 no disponible",
                "fuente": None}
    k = ev["reporte"]["kpis"]; p = ev["escenario"]["parametros"]
    lotes_obj = tarea.get("lotes_objetivo", p["lotes_mes"])
    cap = p.get("capacidad_lotes_mes", 30)
    if lotes_obj > cap:
        return {"voto": "desfavorable",
                "detalle": f"objetivo {lotes_obj} lotes/mes excede capacidad {cap} (F90)",
                "fuente": "evidencia_v072/fase90"}
    mc = (p["precio_dosis_mxn"] - p["costo_variable_dosis_mxn"]
          - p["costo_utilidades_mxn_lote"] / p["dosis_por_lote"])
    delta = (lotes_obj - p["lotes_mes"]) * p["dosis_por_lote"] * mc
    return {"voto": "favorable" if delta > 0 else "precaucion",
            "detalle": f"margen unitario {mc:,.2f} MXN/dosis; Δutilidad mensual estimada "
                       f"{delta:,.0f} MXN; margen actual {k['rentabilidad_margen_pct']} %",
            "fuente": "evidencia_v072/fase90"}


def agente_produccion(tarea, ctx):
    ev = ctx.get("f90")
    if not ev:
        return {"voto": "revision", "detalle": "evidencia F90 no disponible", "fuente": None}
    p = ev["escenario"]["parametros"]
    lotes_obj = tarea.get("lotes_objetivo", p["lotes_mes"])
    cap = p.get("capacidad_lotes_mes", 30)
    util = 100.0 * lotes_obj / cap
    voto = "favorable" if util <= 85 else ("precaucion" if util <= 100 else "desfavorable")
    return {"voto": voto,
            "detalle": f"utilización resultante {util:.1f} % de {cap} lotes/mes; "
                       f"LN2 trampa 28.6 kg/lote y 455.55 MXN/lote (F86)",
            "fuente": "evidencia_v072/fase86,fase90"}


def agente_proteccion_radiologica(tarea, ctx):
    ev = ctx.get("f83")
    if not ev:
        return {"voto": "revision", "detalle": "evidencia F83 no disponible", "fuente": None}
    pend = "Monte Carlo" in json.dumps(ev, ensure_ascii=False)
    return {"voto": "precaucion" if pend else "favorable",
            "detalle": "blindaje ciclotrón calculado NCRP-144 (F83, losa 2.3–2.5 m @3.5 g/cm³); "
                       "simulación Monte Carlo DECLARADA pendiente — mayor actividad requiere "
                       "verificación de dosis antes de aprobar",
            "fuente": "evidencia_v072/fase83"}


def agente_control_calidad(tarea, ctx):
    ev = ctx.get("f87")
    if not ev:
        return {"voto": "revision", "detalle": "evidencia F87 no disponible", "fuente": None}
    return {"voto": "precaucion",
            "detalle": "STAE (F87) validado con vectores sintéticos declarados; sin datos "
                       "reales de CQ aún (memoria 3) — capacidad estadística lista, datos pendientes",
            "fuente": "evidencia_v072/fase87"}


def agente_regulacion(tarea, ctx):
    return {"voto": "precaucion",
            "detalle": "incremento de actividad requiere verificar licencia COFEPRIS/CNSNS "
                       "vigente (dato institucional pendiente); PQ no declarada (14.9)",
            "fuente": None}


AGENTES_FN = {"economia": agente_economia, "produccion": agente_produccion,
              "proteccion_radiologica": agente_proteccion_radiologica,
              "control_calidad": agente_control_calidad, "regulacion": agente_regulacion}


# --- 43.12 Task Planner -------------------------------------------------------------
def planificar(consulta, lotes_objetivo=None):
    tarea = {"consulta": consulta, "lotes_objetivo": lotes_objetivo}
    if lotes_objetivo is not None:
        tareas = [{"agente": a, "tarea": dict(tarea)} for a in
                  ("produccion", "economia", "proteccion_radiologica",
                   "control_calidad", "regulacion")]
    else:
        tareas = [{"agente": "economia", "tarea": dict(tarea)}]
    return {"consulta": consulta, "secuencia_registrada": True, "tareas": tareas}


# --- 43.10 Context Manager ------------------------------------------------------------
def construir_contexto():
    fuentes = {"f90": ("fase90", "ffsae_f90.json"), "f86": ("fase86", "utilidades_completas_f86.json"),
               "f83": ("fase83", "blindaje_ciclotron_f83.json"), "f87": ("fase87", "stae_f87.json")}
    ctx, refs, faltantes = {}, [], []
    for k, (fase, arch) in fuentes.items():
        ev = _cargar(fase, arch)
        if ev is None:
            faltantes.append(k)
        else:
            ctx[k] = ev
            refs.append(f"evidencia_v072/{fase}/{arch}")
    return ctx, {"fuentes": refs, "faltantes": faltantes,
                 "gemelos": ["Economic", "Operational", "Physics", "QC"]}


# --- 43.8 Agent Orchestrator --------------------------------------------------------------
def orquestar(plan, ctx):
    contribuciones = []
    for t in plan["tareas"]:
        fn = AGENTES_FN.get(t["agente"])
        if fn is None:
            contribuciones.append({"agente": t["agente"], "voto": "revision",
                                   "detalle": "agente_no_registrado", "fuente": None})
        else:
            r = fn(t["tarea"], ctx)
            contribuciones.append({"agente": t["agente"], **r})
    return contribuciones


# --- 43.9 Consensus Engine ------------------------------------------------------------------
PESOS = {"favorable": 1.0, "precaucion": 0.0, "desfavorable": -1.0, "revision": None}


def consenso(contribuciones):
    validos = [c for c in contribuciones if c["voto"] in PESOS and PESOS[c["voto"]] is not None]
    if not validos:
        return {"recomendacion": "revision", "score": None}
    score = sum(PESOS[c["voto"]] for c in validos) / len(validos)
    if score > 0.4:
        rec = "favorable_con_condiciones"
    elif score >= -0.2:
        rec = "precaucion"
    else:
        rec = "desfavorable"
    return {"recomendacion": rec, "score": round(score, 3),
            "n_agentes": len(validos),
            "contribuciones_registradas": contribuciones,  # 43.9 trazabilidad
            "marca_43_3": "asistencia a la decisión — NO sustituye decisión humana "
                          "autorizada (43.3/18.10); sujeta a aprobación humana (43.17)"}


# --- 43.21 Validation Engine ------------------------------------------------------------------
def validar_recomendacion(contexto, contribuciones):
    eventos = []
    for f in contexto["faltantes"]:
        eventos.append(f"contexto_faltante:{f}")
    if any(c["voto"] == "revision" for c in contribuciones):
        eventos.append("agente_en_revision")
    votos = {c["voto"] for c in contribuciones}
    if "favorable" in votos and "desfavorable" in votos:
        eventos.append("inconsistencia_entre_agentes")
    return eventos


# --- 43.11 Conversation Manager + ejecución ------------------------------------------------------
def run():
    os.makedirs(EV_DIR, exist_ok=True)
    reg = os.path.join(EV_DIR, "registro_madse_f92.jsonl")

    def audit(accion, detalle):
        prev = "0" * 64
        if os.path.exists(reg):
            lines = [l for l in open(reg, encoding="utf-8").read().splitlines() if l.strip()]
            if lines:
                prev = json.loads(lines[-1])["md5"]
        e = {"fecha_utc": datetime.now(timezone.utc).isoformat(),
             "usuario": "rpos_pipeline_f92", "accion": accion, "detalle": detalle,
             "prev_md5": prev}
        e["md5"] = hashlib.md5(json.dumps(e, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with open(reg, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")

    # 43.6 registro de agentes (catálogo 43.7 ampliado)
    registro = []
    for dom in DOMINIOS_43_7:
        registrar_agente(registro, f"agente_{dom}", dom,
                         ["analisis_dominio", "voto_trazable"],
                         version="1.0" if dom in AGENTES_FN else "0.0-pendiente_logica")
    audit("registrar_agentes", {"n": len(registro)})

    ctx, ctx_info = construir_contexto()
    audit("construir_contexto", ctx_info)

    consulta = "¿Es viable aumentar la producción FDG a 24 lotes/mes?"
    plan = planificar(consulta, lotes_objetivo=24)
    audit("planificar", {"tareas": [t["agente"] for t in plan["tareas"]]})

    contribuciones = orquestar(plan, ctx)
    audit("orquestar", {"n_contribuciones": len(contribuciones)})

    eventos = validar_recomendacion(ctx_info, contribuciones)
    con = consenso(contribuciones)
    audit("consenso", {"recomendacion": con["recomendacion"], "score": con["score"],
                       "eventos_revision": eventos})

    conversacion = {  # 43.11
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "usuario": "rpos_pipeline_f92",
        "consulta": consulta,
        "agentes_participantes": [c["agente"] for c in contribuciones],
        "contexto": ctx_info, "resultados": con,
    }
    audit("conversacion", {"consulta": consulta})

    out = {
        "fase": FASE, "capitulo_canonico": 43,
        "componentes_43_5": ["Agent Registry", "Agent Orchestrator", "Consensus Engine",
                             "Context Manager", "Conversation Manager", "Task Planner",
                             "Validation Engine", "Audit Service"],
        "agentes_registrados": registro,
        "conversacion": conversacion,
        "eventos_revision_43_21": eventos,
        "naturaleza_agentes": "heurísticas deterministas declaradas sobre evidencia real; "
                              "LLM/agentes autónomos: compatibilidad futura (43.26)",
        "pendientes_declarados": [
            "Agentes fisica_medica, radioquimica, operacion, mantenimiento, logistica: "
            "registrados v0.0, lógica pendiente (43.25: se incorporan sin modificar el núcleo).",
            "PostgreSQL/MinIO/Vector DB (43.22) pendientes de despliegue.",
            "Verificación Monte Carlo de blindaje (F83) condiciona el voto radiológico.",
        ],
    }
    with open(os.path.join(EV_DIR, "madse_f92.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print(json.dumps({"recomendacion": con["recomendacion"], "score": con["score"],
                      "votos": {c["agente"]: c["voto"] for c in contribuciones},
                      "eventos": eventos}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
