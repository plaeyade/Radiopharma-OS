#!/usr/bin/env python3
"""
F91 — Cap. 42: MLOps & AI Lifecycle Management Engine (MALME)
Radiopharma OS — EDS Volumen VIII (Enterprise Intelligence & AI Twin)

Reglas canónicas:
- 42.3: MALME administra modelos; NO desarrolla automáticamente nuevos
  algoritmos. Infraestructura de ciclo de vida: entrenamiento → validación →
  registro → despliegue → monitoreo → retiro (42.4), cada transición
  documentada.
- 42.8/42.20: sólo modelos aprobados pueden desplegarse; los no validados
  permanecen en estado de revisión.
- 42.15/18.10: las recomendaciones permanecen desacopladas de la ejecución
  operacional.
- 42.22: auditoría append-only (usuario, modelo, versión, acción, fecha),
  registro jsonl encadenado md5 (ALCOA+).
- Memoria 3 / honestidad: el dataset de demanda es SINTÉTICO DECLARADO para
  V&V del ciclo de vida; no son datos reales de producción. El entrenamiento
  es real (mínimos cuadrados) sobre ese dataset.
"""
import hashlib, json, os, random, sys
from datetime import datetime, timezone

FASE = "fase91"
EV_DIR = "/mnt/agents/work/evidencia_v072/fase91"

ESTADOS = ("entrenado", "en_validacion", "aprobado", "desplegado", "retirado")


# --- 42.6 Dataset Manager -------------------------------------------------------
def registrar_dataset(nombre, origen, datos, version="1.0"):
    blob = json.dumps(datos, sort_keys=True).encode()
    return {
        "nombre": nombre, "origen": origen, "version": version,
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "n_registros": len(datos), "md5": hashlib.md5(blob).hexdigest(),
        "estado": "versionado",
    }


# --- Entrenamiento real (mínimos cuadrados, algoritmo fijo — 42.3) ---------------
def entrenar_lineal(xs, ys):
    n = len(xs)
    sx, sy = sum(xs), sum(ys)
    sxx = sum(x * x for x in xs); sxy = sum(x * y for x, y in zip(xs, ys))
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-12:
        raise ValueError("dataset_degenerado")
    b = (n * sxy - sx * sy) / denom
    a = (sy - b * sx) / n
    return {"algoritmo": "regresion_lineal_ols", "intercepto": a, "pendiente": b}


def metricas(modelo, xs, ys):
    n = len(xs)
    pred = [modelo["intercepto"] + modelo["pendiente"] * x for x in xs]
    err = [p - y for p, y in zip(pred, ys)]
    rmse = (sum(e * e for e in err) / n) ** 0.5
    mae = sum(abs(e) for e in err) / n
    media = sum(ys) / n
    sst = sum((y - media) ** 2 for y in ys)
    sse = sum(e * e for e in err)
    r2 = 1 - sse / sst if sst > 0 else 0.0
    return {"rmse": round(rmse, 4), "mae": round(mae, 4), "r2": round(r2, 4)}


# --- 42.7 Experiment Tracker ------------------------------------------------------
def registrar_experimento(nombre_modelo, modelo, hiperparametros, mets, dataset):
    return {
        "modelo": nombre_modelo, "algoritmo": modelo["algoritmo"],
        "hiperparametros": hiperparametros, "resultados": mets,
        "dataset_ref": {"nombre": dataset["nombre"], "version": dataset["version"],
                        "md5": dataset["md5"]},
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "reproducible": True,  # algoritmo determinista + dataset versionado
    }


# --- 42.8 Model Registry ------------------------------------------------------------
def registrar_modelo(registro, nombre, version, modelo, mets, doc):
    entrada = {
        "nombre": nombre, "version": version, "estado": "entrenado",
        "parametros": modelo, "metricas": mets, "documentacion": doc,
        "md5": hashlib.md5(json.dumps(modelo, sort_keys=True).encode()).hexdigest(),
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
    }
    registro.append(entrada)
    return entrada


# --- 42.20 Validation Engine ----------------------------------------------------------
def validar_modelo(entrada, umbrales):
    """Antes del despliegue: desempeño, consistencia, documentación e
    integridad (42.20). Los no validados permanecen en revisión."""
    errores = []
    m = entrada["metricas"]
    if m.get("r2", 0) < umbrales["r2_min"]:
        errores.append(f"desempeno:r2 {m.get('r2')} < {umbrales['r2_min']}")
    if m.get("rmse", 1e9) > umbrales["rmse_max"]:
        errores.append(f"desempeno:rmse {m.get('rmse')} > {umbrales['rmse_max']}")
    md5 = hashlib.md5(json.dumps(entrada["parametros"], sort_keys=True).encode()).hexdigest()
    if md5 != entrada["md5"]:
        errores.append("integridad:md5_no_coincide")
    if not entrada.get("documentacion"):
        errores.append("documentacion:faltante")
    if abs(entrada["parametros"].get("pendiente", 0)) < 1e-9:
        errores.append("consistencia:pendiente_nula")
    entrada["estado"] = "en_validacion" if errores else "aprobado"
    entrada["errores_validacion"] = errores
    return errores


# --- 42.11 Governance Manager ------------------------------------------------------------
def aprobar_despliegue(entrada, responsable, politica):
    if not responsable:
        raise ValueError("gobernanza:responsable_requerido")
    aprob = {"responsable": responsable, "politica": politica,
             "fecha_utc": datetime.now(timezone.utc).isoformat()}
    entrada.setdefault("aprobaciones", []).append(aprob)
    return aprob


# --- 42.9 Deployment Manager ----------------------------------------------------------------
def desplegar(entrada):
    if entrada["estado"] != "aprobado":
        raise ValueError(f"solo_modelos_aprobados (estado={entrada['estado']})")
    entrada["estado"] = "desplegado"
    entrada["despliegue"] = {"fecha_utc": datetime.now(timezone.utc).isoformat(),
                             "documentado": True}
    return entrada["despliegue"]


def revertir(entrada, motivo):
    entrada["estado"] = "aprobado"
    entrada.setdefault("reversiones", []).append(
        {"motivo": motivo, "fecha_utc": datetime.now(timezone.utc).isoformat()})


def retirar(entrada, motivo):
    entrada["estado"] = "retirado"
    entrada["retiro"] = {"motivo": motivo,
                         "fecha_utc": datetime.now(timezone.utc).isoformat()}


# --- 42.10 Monitoring Engine -------------------------------------------------------------------
def monitorear(entrada, xs_holdout, ys_holdout):
    """Métricas asociadas a cada versión. En producción real:
    pendiente_telemetria (no se simulan lecturas operativas)."""
    m = metricas(entrada["parametros"], xs_holdout, ys_holdout)
    mon = {"version": entrada["version"], "desempeno_holdout": m,
           "estabilidad": "ok" if m["r2"] >= 0.85 else "deriva",
           "disponibilidad_produccion": "pendiente_telemetria",
           "fecha_utc": datetime.now(timezone.utc).isoformat()}
    entrada.setdefault("monitoreo", []).append(mon)
    return mon


# --- Ejecución de fase ----------------------------------------------------------------------------
def run():
    os.makedirs(EV_DIR, exist_ok=True)
    reg = os.path.join(EV_DIR, "registro_malme_f91.jsonl")

    def audit(accion, modelo, version):
        prev = "0" * 64
        if os.path.exists(reg):
            lines = [l for l in open(reg, encoding="utf-8").read().splitlines() if l.strip()]
            if lines:
                prev = json.loads(lines[-1])["md5"]
        e = {"fecha_utc": datetime.now(timezone.utc).isoformat(),
             "usuario": "rpos_pipeline_f91", "modelo": modelo, "version": version,
             "accion": accion, "prev_md5": prev}
        e["md5"] = hashlib.md5(json.dumps(e, sort_keys=True).encode()).hexdigest()
        with open(reg, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")

    # Dataset sintético DECLARADO (V&V del ciclo de vida; no datos reales)
    random.seed(42)  # reproducibilidad 42.7
    xs = [float(m) for m in range(1, 25)]
    ys = [18.0 * (1.02 ** (m - 1)) + random.uniform(-0.8, 0.8) for m in xs]
    ds = registrar_dataset("demanda_lotes_sintetica_vv", "sintetico_declarado_vv (memoria 3)",
                           [{"mes": x, "lotes": round(y, 4)} for x, y in zip(xs, ys)])
    audit("registrar_dataset", ds["nombre"], ds["version"])

    xs_tr, ys_tr = xs[:18], ys[:18]
    xs_ho, ys_ho = xs[18:], ys[18:]

    modelo = entrenar_lineal(xs_tr, ys_tr)
    mets = metricas(modelo, xs_tr, ys_tr)
    exp = registrar_experimento("demanda_lotes_forecast", modelo,
                                {"semilla": 42, "split": "18/6"}, mets, ds)
    audit("entrenar", exp["modelo"], "1.0")

    registro = []
    doc = {"proposito": "pronóstico de demanda de lotes (42.17 Economic Twin)",
           "limitaciones": "dataset sintético V&V; recomendación desacoplada (18.10)",
           "feature_store_ref": "pendiente_despliegue (42.14)"}
    m_ok = registrar_modelo(registro, "demanda_lotes_forecast", "1.0", modelo, mets, doc)
    audit("registrar_modelo", m_ok["nombre"], m_ok["version"])

    umbrales = {"r2_min": 0.90, "rmse_max": 1.5}
    errores_ok = validar_modelo(m_ok, umbrales)
    audit("validar", m_ok["nombre"], m_ok["version"])

    # Modelo deficiente: queda en revisión y NO puede desplegarse (42.8/42.20)
    modelo_malo = {"algoritmo": "regresion_lineal_ols", "intercepto": 5.0, "pendiente": 0.0}
    m_malo = registrar_modelo(registro, "demanda_lotes_forecast", "0.9-malo", modelo_malo,
                              metricas(modelo_malo, xs_tr, ys_tr), doc)
    errores_malo = validar_modelo(m_malo, umbrales)
    audit("validar", m_malo["nombre"], m_malo["version"])
    try:
        desplegar(m_malo)
        despliegue_malo_bloqueado = False
    except ValueError:
        despliegue_malo_bloqueado = True

    aprobar_despliegue(m_ok, responsable="responsable_calidad_declarado",
                       politica="aprobacion_previa_despliegue_v1")
    dep = desplegar(m_ok)
    audit("desplegar", m_ok["nombre"], m_ok["version"])

    mon = monitorear(m_ok, xs_ho, ys_ho)
    audit("monitorear", m_ok["nombre"], m_ok["version"])

    revertir(m_ok, "demostracion_reversion_vv")
    audit("revertir", m_ok["nombre"], m_ok["version"])
    retirar(m_ok, "cierre_ciclo_vida_vv")
    audit("retirar", m_ok["nombre"], m_ok["version"])

    out = {
        "fase": FASE, "capitulo_canonico": 42,
        "componentes_42_5": ["Dataset Manager", "Experiment Tracker", "Model Registry",
                             "Deployment Manager", "Monitoring Engine",
                             "Governance Manager", "Validation Engine", "Reporting Service"],
        "dataset": ds, "experimento": exp,
        "umbrales_validacion_declarados": umbrales,
        "modelo_aprobado": {"version": m_ok["version"], "metricas": mets,
                            "errores_validacion": errores_ok,
                            "despliegue": dep, "monitoreo": mon},
        "modelo_deficiente": {"version": m_malo["version"], "estado": m_malo["estado"],
                              "errores_validacion": errores_malo,
                              "despliegue_bloqueado": despliegue_malo_bloqueado},
        "ciclo_completo_vv": ["entrenado", "aprobado", "desplegado", "monitoreado",
                              "revertido", "retirado"],
        "pendientes_declarados": [
            "Dataset real de demanda (producción) — el actual es sintético declarado V&V.",
            "Feature Store (42.14) y PostgreSQL/MinIO/MLflow (42.21) pendientes de despliegue.",
            "Telemetría de disponibilidad en producción: pendiente_telemetria.",
        ],
    }
    with open(os.path.join(EV_DIR, "malme_f91.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print(json.dumps({"r2_aprobado": mets["r2"], "rmse_aprobado": mets["rmse"],
                      "errores_aprobado": errores_ok,
                      "malo_estado": m_malo["estado"],
                      "malo_bloqueado": despliegue_malo_bloqueado,
                      "monitoreo_holdout_r2": mon["desempeno_holdout"]["r2"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
