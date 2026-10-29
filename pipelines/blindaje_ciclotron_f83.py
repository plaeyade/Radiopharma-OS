"""F83 - Ingesta "ESTIMACION DE BLINDAJE CICLOTRON ONCOLOGIA ZUMAYA" (16/07/2026) y
cotejo con los modelos internos F52/F70/F81.

Fuente: PDF subido por el usuario (Gamma Diagnosticos del Sureste / Hospitales Zumaya).
Documento PRELIMINAR (variacion 15-20% declarada). Verificacion de planos IBA con
material 3.5 g/cm3; declara "Pendiente simulacion Monte Carlo".

Cotejo interno (documental, sin decision operativa, 18.10):
- F70: vault BIND modelado con muro 2.11 m concreto 2.35 g/cm3 (geometria CSG).
- Documento: losa 2.3-2.5 m @3.5 g/cm3 segun guia IBA; muros adicionales 30 cm @3.5.
- Equivalencia de atenuacion aproximada via densidad*espesor (g/cm2) SOLO como
  comparacion gruesa declarada: no sustituye transporte de neutrones (NCRP-144).
"""
import json, hashlib, os, datetime

EV = "/mnt/agents/work/evidencia_v072/fase83"

DOC = {
    "titulo": "ESTIMACION DE BLINDAJE CICLOTRON ONCOLOGIA ZUMAYA",
    "fecha_documento": "2026-07-16",
    "emisor": "Gamma Diagnosticos del Sureste S.A. de C.V. / Hospitales Zumaya",
    "naturaleza": "preliminar_variacion_15_a_20_pct_declarada",
    "consideraciones": [
        "verificacion de planos entregados por IBA con guias y estandares internacionales",
        "material de blindaje densidad 3.5 g/cm3",
        "capacidad maxima de produccion del ciclotron y radiofarmacia",
        "validada la propuesta de diseno de la radiofarmacia previendo incremento de produccion",
    ],
}

CICLOTRON = {
    "criterio": "NCRP-144 + Monte Carlo (conservadores, declarados)",
    "carga_trabajo": {
        "horas_irradiacion_dia": 8,
        "regimen": "potencia_maxima",
        "energia_MeV": 18,
        "corriente_uA": 300,
    },
    "densidad_blindaje_g_cm3": 3.5,
    "losa_bunker": {"espesor_m": [2.3, 2.5],
                     "base": "guia IBA para la instalacion especifica (declarado)",
                     "nota": "espesor de losa de 2.3 m a 2.5 m de altura dentro del bunker"},
    "muros_adicionales_cm": {"espesor": 30, "densidad_g_cm3": 3.5,
                              "nota": "muros donde se indica blindaje; espesores estimados adecuados @3.5 g/cm3"},
    "pendiente_declarado": "simulacion Monte Carlo",
    "calculos": "sobreestimados considerando crecimiento de capacidades de produccion",
}

# Datos internos (de evidencias previas, con fuente)
INTERNO = {
    "F70_vault_BIND": {"muro_m": 2.11, "densidad_g_cm3": 2.35,
                        "fuente": "evidencia_v072/fase70 (geometria CSG BIND)"},
    "F52_corridas": {"T_H10": 0.0451, "fuente": "homologacion_h10_f76.json"},
    "F81_plantas": {"bunker_ciclotron": "planta baja, capa BUNKER + etiqueta CICLOTRON",
                     "techo": "sala control AA, bajo factor de ocupacion (usuario)"},
}


def g_cm2(espesor_m, densidad):
    return espesor_m * 100 * densidad


def cotejo():
    # comparacion gruesa en g/cm2 (declarada; NO es transporte NCRP-144)
    losa_min = g_cm2(2.3, 3.5)   # 805
    losa_max = g_cm2(2.5, 3.5)   # 875
    f70 = g_cm2(INTERNO["F70_vault_BIND"]["muro_m"], 2.35)  # 495.85
    return [
        {"check": "losa_IBA_g_cm2_vs_muro_F70",
         "losa_IBA_g_cm2": [losa_min, losa_max], "muro_F70_g_cm2": round(f70, 1),
         "razon": round(losa_min / f70, 2),
         "interpretacion": "la losa IBA @3.5 tiene ~1.6x mas masa superficial que el muro F70 @2.35; "
                           "comparacion en g/cm2 unicamente, atenuacion neutronica real depende de "
                           "composicion (agregados pesados vs portland) - declarado"},
        {"check": "corriente_documento_vs_fuente_F70",
         "doc_uA": 300, "F70_fuente": "Bonvin 2021 Fig.7, 4.616e12 n/s nominal (KIUBE supuesto)",
         "interpretacion": "300 uA a 18 MeV es consistente con el regimen maximo KIUBE; "
                           "la normalizacion exacta de la fuente F70 queda pendiente de hoja de datos IBA"},
    ]


def md5_file(p, chunk=1 << 20):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(chunk), b""):
            h.update(blk)
    return h.hexdigest()


def main():
    os.makedirs(EV, exist_ok=True)
    src = "/mnt/agents/upload/ESTIMACIÓN DE BLINDAJE CICLOTRON ONCOLOGÍA ZUMAYA.pdf"
    ev = {
        "fase": "F83",
        "fecha_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "fuente": {"archivo": "ESTIMACION DE BLINDAJE CICLOTRON ONCOLOGIA ZUMAYA.pdf",
                    "md5": md5_file(src), **DOC},
        "ciclotron": CICLOTRON,
        "cotejo_interno": cotejo(),
        "contexto_interno": INTERNO,
        "hallazgos": [
            "Documento de 16/07/2026 (anterior al de 28/10/2026 de F82): verificacion de planos IBA del bunker ciclotron + radiofarmacia.",
            "Losa del bunker 2.3-2.5 m @3.5 g/cm3 segun guia IBA; muros adicionales 30 cm @3.5 g/cm3.",
            "Regimen: 8 h/dia a potencia maxima, 18 MeV, 300 uA - primer dato externo de corriente del proyecto.",
            "El documento declara PENDIENTE la simulacion Monte Carlo: coherente con F70-F78 (nuestras corridas MC son la unica estimacion de transporte existente, de alcance teorico, memoria 3).",
            "Techo del bunker sin ocupacion significativa (F81, usuario) es consistente con una losa guiada por IBA.",
        ],
        "advertencias": [
            "Preliminar (15-20%); espesores del plano IBA tambien preliminares segun el propio documento.",
            "Comparacion en g/cm2 es gruesa y declarada; no sustituye NCRP-144 ni transporte Monte Carlo.",
            "Registro documental; no es diseno ni decision operativa (18.10).",
        ],
        "estado": "completada_documental",
    }
    outp = os.path.join(EV, "blindaje_ciclotron_f83.json")
    json.dump(ev, open(outp, "w"), ensure_ascii=False, indent=1)

    regp = os.path.join(EV, "registro_blindaje_ciclotron_f83.jsonl")
    prev = ""
    if os.path.exists(regp):
        lines = open(regp).read().strip().splitlines()
        if lines:
            prev = hashlib.md5(lines[-1].encode()).hexdigest()
    entry = {"ts": ev["fecha_utc"], "fase": "F83",
             "evento": "ingesta_blindaje_ciclotron_zumaya",
             "md5_fuente": ev["fuente"]["md5"], "md5_evidencia": md5_file(outp),
             "prev": prev}
    entry["md5"] = hashlib.md5(json.dumps(entry, sort_keys=True).encode()).hexdigest()
    with open(regp, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(json.dumps({"evidencia": outp, "md5": entry["md5"]}, indent=1))


if __name__ == "__main__":
    main()
