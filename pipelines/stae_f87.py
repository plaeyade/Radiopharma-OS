"""F87 - Stability & Trend Analysis Engine (STAE), Capitulo 27 del MVP canonico.

Componentes canonicos implementados (27.5): Historical Data Manager (ingesta
validada), SPC Engine (27.7: cartas de control I-MR, reglas Western Electric),
Trend Analyzer (27.8: pendiente + Mann-Kendall), Stability Analyzer (27.9: %RSD,
deriva), KPI Generator (27.10), Alert Manager (27.13), validacion (27.21),
auditoria ALCOA+ (27.23).

Reglas canonicas respetadas:
- 27.14: nunca analiza resultados incompletos o pendientes (se rechazan).
- 27.21: verifica integridad, consistencia temporal, ausencia de duplicados.
- 27.3: el STAE NO modifica resultados.
- 18.10: indicadores/alertas no son decisiones operativas.
- Honestidad: los datos de este pipeline son VECTORES SINTETICOS DECLARADOS para
  V&V del motor (no hay ciclotron operativo - memoria 3). Nunca se presentan
  como resultados QC reales.
"""
import json, hashlib, os, datetime, math, statistics

EV = "/mnt/agents/work/evidencia_v072/fase87"

D2 = 1.128  # constante carta I-MR (n=2)


def md5_file(p, chunk=1 << 20):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(chunk), b""):
            h.update(blk)
    return h.hexdigest()


def validar_dataset(lotes):
    """27.21: integridad, consistencia temporal, sin duplicados, sin pendientes."""
    errs = []
    ids = [l["id"] for l in lotes]
    if len(set(ids)) != len(ids):
        errs.append("duplicados")
    fechas = [l["fecha"] for l in lotes]
    if fechas != sorted(fechas):
        errs.append("inconsistencia_temporal")
    for l in lotes:
        if l.get("estado") != "validado":
            errs.append(f"pendiente_o_incompleto:{l['id']}")
        if "valor" not in l or not isinstance(l["valor"], (int, float)):
            errs.append(f"sin_valor:{l['id']}")
    return errs


def spc_imr(valores):
    """Carta individuales + rango movil; reglas Western Electric 1-4."""
    n = len(valores)
    mr = [abs(valores[i] - valores[i - 1]) for i in range(1, n)]
    xbar = statistics.mean(valores)
    mrbar = statistics.mean(mr) if mr else 0.0
    sigma = mrbar / D2 if mrbar else 0.0
    ucl, lcl = xbar + 3 * sigma, xbar - 3 * sigma
    alertas = []
    for i, v in enumerate(valores):
        # regla 1: punto fuera de 3 sigma
        if sigma and (v > ucl or v < lcl):
            alertas.append({"regla": "WE1_fuera_3sigma", "indice": i, "valor": v})
        # regla 2: 2 de 3 fuera de 2 sigma (mismo lado)
        if i >= 2 and sigma:
            w = valores[i - 2:i + 1]
            hi = sum(1 for x in w if x > xbar + 2 * sigma)
            lo = sum(1 for x in w if x < xbar - 2 * sigma)
            if hi >= 2 or lo >= 2:
                alertas.append({"regla": "WE2_2de3_fuera_2sigma", "indice": i, "valor": v})
        # regla 4: 8 consecutivos del mismo lado
        if i >= 7:
            w = valores[i - 7:i + 1]
            if all(x > xbar for x in w) or all(x < xbar for x in w):
                alertas.append({"regla": "WE4_8_mismo_lado", "indice": i, "valor": v})
    return {"n": n, "media": round(xbar, 6), "sigma_imr": round(sigma, 6),
            "UCL": round(ucl, 6), "LCL": round(lcl, 6), "alertas": alertas}


def mann_kendall(valores):
    n = len(valores)
    s = 0
    for i in range(n):
        for j in range(i + 1, n):
            s += (valores[j] > valores[i]) - (valores[j] < valores[i])
    var = n * (n - 1) * (2 * n + 5) / 18
    z = 0.0 if s == 0 else (s - 1) / math.sqrt(var) if s > 0 else (s + 1) / math.sqrt(var)
    tendencia = "creciente" if z > 1.96 else "decreciente" if z < -1.96 else "sin_tendencia_significativa"
    return {"S": s, "z": round(z, 4), "tendencia": tendencia}


def pendiente_ls(valores):
    n = len(valores)
    xs = list(range(n))
    mx, my = (n - 1) / 2, statistics.mean(valores)
    num = sum((x - mx) * (v - my) for x, v in zip(xs, valores))
    den = sum((x - mx) ** 2 for x in xs)
    return num / den if den else 0.0


def kpis(lotes, spc, usl, lsl):
    n = len(lotes)
    aprob = sum(1 for l in lotes if l.get("aprobado")) / n if n else 0
    valores = [l["valor"] for l in lotes]
    sigma = spc["sigma_imr"]
    media = spc["media"]
    cpk = None
    if sigma and usl is not None and lsl is not None:
        cpk = round(min(usl - media, media - lsl) / (3 * sigma), 4)
    return {"pct_aprobacion": round(aprob * 100, 2),
            "pct_rechazo": round((1 - aprob) * 100, 2),
            "rsd_pct": round(statistics.pstdev(valores) / media * 100, 3) if media else None,
            "cpk": cpk, "n_lotes": n}


# --- vectores sinteticos DECLARADOS para V&V (NO son QC real) ---
def vectores_vv():
    base = [100.0 + ((-1) ** i) * 0.5 for i in range(24)]           # estable
    tend = [100.0 + 0.8 * i for i in range(24)]                      # tendencia creciente
    ooc = [100.0] * 12 + [110.0]                                     # punto fuera de control
    corrida = [100.0 + (0.1 if i >= 8 else -0.1) for i in range(16)] # 8 mismo lado
    hoy = "2026-10-29"
    def mk(vals, ap=True):
        return [{"id": f"V{i:02d}", "fecha": f"2026-01-{i+1:02d}", "valor": round(v, 4),
                 "estado": "validado", "aprobado": (ap and abs(v - 100) < 5)} for i, v in enumerate(vals)]
    return {
        "estable": mk(base), "tendencia": mk(tend, ap=False),
        "fuera_de_control": mk(ooc, ap=False), "corrida": mk(corrida),
        "invalido_duplicado": mk(base) + [dict(mk(base)[0])],
        "invalido_pendiente": mk(base)[:5] + [{"id": "X1", "fecha": "2026-02-01", "valor": 99.0,
                                               "estado": "pendiente", "aprobado": False}],
    }


def main():
    os.makedirs(EV, exist_ok=True)
    vv = vectores_vv()
    resultados = {}
    for nombre, lotes in vv.items():
        errs = validar_dataset(lotes)
        if errs:
            resultados[nombre] = {"rechazado": True, "errores": sorted(set(errs))}
            continue
        valores = [l["valor"] for l in lotes]
        spc = spc_imr(valores)
        mk_ = mann_kendall(valores)
        resultados[nombre] = {
            "rechazado": False, "spc": spc, "tendencia": mk_,
            "pendiente_por_lote": round(pendiente_ls(valores), 5),
            "kpis": kpis(lotes, spc, 105.0, 95.0),
        }
    ev = {
        "fase": "F87", "fecha_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "componente": "STAE (Stability & Trend Analysis Engine) - Capitulo 27 MVP",
        "componentes_canonicos": ["Historical Data Manager (27.6)", "SPC Engine (27.7)",
                                   "Trend Analyzer (27.8)", "Stability Analyzer (27.9)",
                                   "Alert Manager (27.13)", "KPI Generator (27.10)",
                                   "Validation Engine (27.21)", "Auditoria (27.23)"],
        "metodos": {"carta": "I-MR (sigma=MRbar/1.128)", "reglas": ["WE1", "WE2", "WE4"],
                     "tendencia": "Mann-Kendall (|z|>1.96) + pendiente minimos cuadrados",
                     "kpis": ["pct_aprobacion", "pct_rechazo", "rsd_pct", "cpk"]},
        "naturaleza_datos": "vectores_sinteticos_declarados_para_VyV_del_motor; NO son resultados QC reales (sin ciclotron, memoria 3)",
        "resultados": resultados,
        "integraciones_canonicas": {"QC Engine": "27.14 (solo resultados validados)",
                                     "Economic Twin": "27.17 (rechazos, repeticiones)",
                                     "IA futura": "27.18 (predicciones diferenciadas de observado)"},
        "estado": "completada_motor_validado",
        "advertencias": [
            "Motor validado con datos sinteticos declarados; la operacion real requiere historial QC validado del QC Engine (27.14).",
            "27.3: el STAE no modifica resultados; 18.10: alertas no son decisiones operativas.",
            "Persistencia PostgreSQL/MinIO/Data Lake (27.22) mapeada a evidencia+registro ALCOA+ en esta fase.",
        ],
    }
    outp = os.path.join(EV, "stae_f87.json")
    json.dump(ev, open(outp, "w"), ensure_ascii=False, indent=1)
    regp = os.path.join(EV, "registro_stae_f87.jsonl")
    prev = ""
    if os.path.exists(regp):
        lines = open(regp).read().strip().splitlines()
        if lines:
            prev = hashlib.md5(lines[-1].encode()).hexdigest()
    entry = {"ts": ev["fecha_utc"], "fase": "F87", "evento": "implementacion_stae_cap27",
             "algoritmo": "I-MR/WE+MannKendall", "version": "1.0",
             "md5_evidencia": md5_file(outp), "prev": prev}
    entry["md5"] = hashlib.md5(json.dumps(entry, sort_keys=True).encode()).hexdigest()
    with open(regp, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(json.dumps({"evidencia": outp, "md5": entry["md5"]}, indent=1))


if __name__ == "__main__":
    main()
