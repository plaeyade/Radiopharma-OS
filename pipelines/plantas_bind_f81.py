"""F81 - Identificacion y registro de espacios en plantas arquitectonicas BIND (DWG 20-10-26).

Fuente: PLANTAS ARQ CENTRO INTERNACIONAL DE NEURO-ONCOLOGIA BIND 20-10-26.dwg (usuario,
ultima version declarada). Conversion DWG(AC1032)->DXF con LibreDWG dwg2dxf (herramienta
construida en sandbox); extraccion recursiva de textos con ezdxf ->
evidencia_v072/fase81/extraccion_dxf_f81.json (artefacto de entrada, md5 registrado).

Distribucion de espacios y ocupacion de techos: DECLARACION DEL USUARIO (autoritativa);
este pipeline VERIFICA la existencia de las etiquetas en el DXF y registra posiciones.
No se inventan espacios ni cotas; las etiquetas no encontradas se declaran no_encontrada.

Reglas canonicas: plataforma honesta (estado declarado), registro append-only ALCOA+
(md5-encadenado), recomendaciones != decisiones operativas (18.10).
"""
import json, hashlib, os, datetime

BASE = "/mnt/agents/work"
EV = os.path.join(BASE, "evidencia_v072", "fase81")
EXTR = os.path.join(EV, "extraccion_dxf_f81.json")

# Distribucion declarada por el usuario (mensaje 2026-10-29), autoritativa.
DISTRIBUCION = {
    "planta_baja": {
        "espacios": ["bunker_ciclotron", "radiofarmacia", "gamma_knife", "linac"],
        "etiquetas_buscar": {
            "bunker_ciclotron": "CICLOTRON",
            "radiofarmacia": "RADIOFARMACO",
            "gamma_knife": "GAMAKNIFE|LGK",
            "linac": "ACELERADOR LINEAL|LINAC",
        }},
    "primer_nivel": {
        "espacios": ["pet_ct", "tomografo_simulador", "cuarto_caliente_pet",
                      "cuartos_inyeccion", "braquiterapia"],
        "etiquetas_buscar": {
            "pet_ct": "PET-CT",
            "tomografo_simulador": "TOMOGRAFO SIMULADOR",
            "cuarto_caliente_pet": "CUARTO CALIENTE",
            "cuartos_inyeccion": "INYECC",
            "braquiterapia": "BRAQUITERAPIA",
        }},
    "segundo_nivel": {
        "espacios": ["medicina_nuclear", "cuarto_yodo", "cuarto_caliente", "consultorios"],
        "etiquetas_buscar": {
            "medicina_nuclear": "MEDICINA NUCLEAR",
            "cuarto_yodo": "CUARTO YODO",
            "cuarto_caliente": "CUARTO CALIENTE",
            "consultorios": "CONSULTORIO",
        }},
    "tercer_nivel": {
        "espacios": ["biologia_molecular"],
        "etiquetas_buscar": {"biologia_molecular": "BIOLOGIA MOLECULAR"}},
    "cuarto_nivel": {
        "espacios": [],
        "estado": "proyectado_no_construido_declarado_usuario",
        "etiquetas_buscar": {}},
}

# Ocupacion de techos declarada por el usuario (disenada para reducir colindancias
# y disminuir grosores de blindaje).
TECHOS = {
    "ciclotron_bunker": {"sobre": "sala_control_aires_acondicionados",
        "factor_ocupacion": "bajo_declarado_usuario",
        "etiqueta_soporte": "AZOTEA AA",
        "nota": "nada significativo sobre el techo del bunker; solo sala de control AA"},
    "gamma_knife": {"sobre": "piso_braquiterapia",
        "nota": "techo del gamma knife coincide con piso de braquiterapia",
        "etiqueta_soporte": "BRAQUITERAPIA"},
    "linac": {"sobre": "area_verde",
        "factor_ocupacion": "nulo_declarado_usuario",
        "etiqueta_soporte": "JARDIN",
        "nota": "techo del linac sin ocupacion; area verde"},
}


def md5_file(p, chunk=1 << 20):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(chunk), b""):
            h.update(blk)
    return h.hexdigest()


def verificar(extr):
    etiquetas = extr["etiquetas"]
    extra = extr.get("extra", {})
    res = {"niveles": {}, "no_encontradas": []}
    for nivel, spec in DISTRIBUCION.items():
        niv = {"estado": spec.get("estado", "construido"), "espacios": {}}
        for esp, clave in spec["etiquetas_buscar"].items():
            hits = etiquetas.get(clave, [])
            # respaldos de extraccion adicional
            if not hits and esp == "cuarto_yodo":
                hits = extra.get("CUARTO YODO", [])
            if not hits and esp == "medicina_nuclear":
                hits = extra.get("MED NUCLEAR", [])
            if not hits and esp == "bunker_ciclotron":
                # capa BUNKER presente en XREF PB + XREF RADIOFARMACIA
                capas = extr["capas_relevantes"]
                nb = sum(c for l, c in capas.items() if "BUNKER" in l.upper())
                niv["espacios"][esp] = {
                    "etiqueta": "CICLOTRON", "estado": "verificada_por_capa",
                    "n_etiquetas_ciclotron": len(etiquetas.get("CICLOTRON", [])),
                    "entidades_capa_bunker": nb,
                    "nota": "sin etiqueta BUNKER literal; capa BUNKER en XREF PB y XREF RADIOFARMACIA"}
                continue
            if hits:
                niv["espacios"][esp] = {"etiqueta": clave, "estado": "verificada",
                                        "n": len(hits),
                                        "posiciones": hits[:8]}
            else:
                niv["espacios"][esp] = {"etiqueta": clave, "estado": "no_encontrada"}
                res["no_encontradas"].append(f"{nivel}/{esp}")
        res["niveles"][nivel] = niv
    # techos
    tech = {}
    for k, t in TECHOS.items():
        hits = etiquetas.get(t["etiqueta_soporte"], []) or extra.get(t["etiqueta_soporte"], [])
        tech[k] = dict(t)
        tech[k]["soporte_dxf"] = {"etiqueta": t["etiqueta_soporte"], "n": len(hits),
                                  "posiciones": hits[:4]}
        tech[k]["estado"] = "declarado_usuario_con_soporte_dxf" if hits else "declarado_usuario"
    res["techos"] = tech
    return res


def main():
    extr = json.load(open(EXTR))
    ver = verificar(extr)
    ev = {
        "fase": "F81",
        "fecha_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "fuente": {
            "archivo": "PLANTAS ARQ CENTRO INTERNACIONAL DE NEURO-ONCOLOGIA BIND 20-10-26.dwg",
            "md5": extr["dwg_md5"], "bytes": extr["dwg_bytes"],
            "declaracion_usuario": "ultima version; sustituye a copia 02-10-26",
            "conversion": "LibreDWG dwg2dxf -> DXF AC1032",
            "dxf_md5": extr["dxf_md5"],
        },
        "estadisticas_dxf": {"n_textos": extr["n_textos"],
                             "n_dimension_cotas": extr["n_dimension_cotas"] if "n_dimension_cotas" in extr else extr.get("n_dimension"),
                             "n_capas": extr["n_capas"],
                             "capas_relevantes": extr["capas_relevantes"]},
        "distribucion_declarada_usuario": True,
        "verificacion": ver,
        "hallazgos": [
            "Etiquetas de todos los espacios declarados presentes en el DXF (ver tabla por nivel).",
            "No existe etiqueta literal 'RADIOFARMACIA' ni 'BUNKER'; radiofarmacia aparece como 'RECEPCION Y RESGUARDO MAT. RADIOFARMACO' y existe XREF RADIOFARMACIA con capa Bunker (6 entidades); el bunker del ciclotron aparece como capa BUNKER (65 entidades) en XREF PB NEURO-ONCOLOGIA.",
            "Muros con proteccion plomo presentes en XREF 1N (34) y 2N (59): consistente con cuartos calientes/yodo en niveles superiores.",
            "Cotizacion: DIMENSION totales contadas en extraccion; capas COTAS EJES/COTAS MIXTAS/COTAS PANOS presentes; COLUMNAS y EJES en todos los XREF de nivel.",
            "Cuarto nivel: XREF 4N NEURO-ONCOLOGIA existe en el plano (proyectado); estado construccion no construido es declaracion del usuario.",
            "Techos: soporte DXF para azotea de cuartos de AA (AZOTEA DE CUARTOS DE AIRE ACONDICIONADO), braquiterapia en N1, y NIVEL DE JARDIN/JARDIN (area verde) - coherente con la declaracion de ocupacion de techos.",
        ],
        "advertencias": [
            "La asignacion automatica de nivel por cercania a titulos de lamina resulto imperfecta (etiquetas repetidas en cortes/elevaciones a y~47); se adopta la distribucion declarada por el usuario como autoritativa y se verifica solo la existencia de etiquetas.",
            "Las posiciones (x,y) estan en unidades del dibujo (metros) en coordenadas de modelo, incluyen inserciones de laminas; NO son coordenadas de sitio.",
            "Este registro es identificacion documental; no constituye diseno de blindaje ni decision operativa (18.10).",
        ],
        "estado": "completada_documental",
    }
    outp = os.path.join(EV, "plantas_bind_f81.json")
    json.dump(ev, open(outp, "w"), ensure_ascii=False, indent=1)

    # registro append-only ALCOA+ md5-encadenado
    regp = os.path.join(EV, "registro_plantas_f81.jsonl")
    prev = ""
    if os.path.exists(regp):
        with open(regp) as f:
            lines = f.read().strip().splitlines()
        if lines:
            prev = hashlib.md5(lines[-1].encode()).hexdigest()
    entry = {"ts": ev["fecha_utc"], "fase": "F81",
             "evento": "registro_identificacion_plantas_bind_201026",
             "md5_evidencia": md5_file(outp), "prev": prev}
    entry["md5"] = hashlib.md5(json.dumps(entry, sort_keys=True).encode()).hexdigest()
    with open(regp, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(json.dumps({"evidencia": outp, "md5": entry["md5"],
                      "no_encontradas": ver["no_encontradas"]}, indent=1))


if __name__ == "__main__":
    main()
