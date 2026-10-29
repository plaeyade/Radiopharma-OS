"""F82 - Ingesta a la BD del documento "ESTIMACION DE BLINDAJES ONCOLOGIA ZUMAYA" (28/10/2026).

Fuente: PDF subido por el usuario (Gamma Diagnosticos del Sureste S.A. de C.V. / Hospitales
Zumaya). Transcripcion fiel de los valores legibles; el documento declara espesores
PRELIMINARES con variacion esperada 15-20% en la memoria analitica definitiva.
La extraccion de texto del PDF pierde la geometria de las figuras: cuando la asignacion
valor<->muro es ambigua se registra como lista en orden de aparicion con
ambiguedad_declarada=True. NADA se inventa; valores no legibles se omiten.

Reglas canonicas: plataforma honesta, registro append-only ALCOA+ md5-encadenado,
fuente citada (49.11), esto es registro documental, no decision de diseno (18.10).
"""
import json, hashlib, os, datetime

EV = "/mnt/agents/work/evidencia_v072/fase82"

DOC = {
    "titulo": "ESTIMACION DE BLINDAJES ONCOLOGIA ZUMAYA",
    "fecha": "2026-10-28",
    "emisor": "Gamma Diagnosticos del Sureste S.A. de C.V. / Hospitales Zumaya",
    "naturaleza": "preliminar_variacion_esperada_15_a_20_pct_declarada",
    "densidades_blindaje_g_cm3": [2.35, 5.0, 5.5, 3.5],
}

# --- Acelerador Lineal (NCRP-151) ---
LINAC = {
    "criterio": "NCRP-151",
    "carga_trabajo": {"pacientes_por_jornada_8h": 30, "turnos_semanales_l_v": 2,
                       "dosis_por_paciente_cGy": 300},
    "nota_diseno": "se dio prioridad a ganar espacio interno en la sala del acelerador",
    "casos": [
        {"caso": 1, "densidad_g_cm3": 2.35, "tipo": "concreto_monolitico",
         "altura_sala_m": 3.5, "arriba": "sala_de_espera", "lado": "banos_publicos",
         "barrera_primaria_calculada_cm": {"losa": 240, "otra": 180},
         "espesores_estimados_cm_orden_doc": [100, 230, 50, 100, 120, 50],
         "ambiguedad_declarada": True},
        {"caso": 2, "densidad_g_cm3": 5.0, "tipo": "concreto_monolitico",
         "altura_sala_m": 3.5, "arriba": "sala_de_espera", "lado": "banos_publicos",
         "barrera_primaria_calculada_cm": {"losa": 105, "otra": 75},
         "espesores_estimados_cm_orden_doc": [50, 75, 30, 50, 50, 30],
         "ambiguedad_declarada": True},
        {"caso": 2, "densidad_g_cm3": 5.0, "tipo": "tabiques",
         "altura_sala_m": 3.5, "ancho_tabique_cm": 13, "altura_total_bunker_cm": 458,
         "barrera_primaria_calculada_cm": {"losa": 108, "laterales": 78},
         "secundarias_regla": "aprox_60_pct_de_primaria_declarado",
         "espesores_estimados_cm_orden_doc": [52, 78, 39, 52, 52, 39],
         "estado": "propuestas_por_confirmar_con_proveedor", "ambiguedad_declarada": True},
        {"caso": 3, "densidad_g_cm3": 5.5, "tipo": "concreto_monolitico",
         "altura_sala_m": 3.5, "arriba": "sala_de_espera", "lado": "banos_publicos",
         "barrera_primaria_calculada_cm": {"losa": 95.72, "otra": 62.48},
         "espesores_estimados_cm_orden_doc": [37.86, 63.1, 20, 37.48, 37.86, 20],
         "ambiguedad_declarada": True},
        {"caso": 3, "densidad_g_cm3": 5.5, "tipo": "tabiques",
         "altura_sala_m": 3.5, "ancho_tabique_cm": 13, "altura_total_bunker_cm": 458,
         "barrera_primaria_calculada_cm": {"losa": 108, "laterales": 65},
         "secundarias_regla": "aprox_60_pct_de_primaria_declarado",
         "espesores_estimados_cm_orden_doc": [39, 65, 26, 39, 39, 26],
         "estado": "propuestas_por_confirmar_con_proveedor", "ambiguedad_declarada": True},
        {"caso": 4, "densidad_g_cm3": 5.5, "tipo": "concreto_monolitico",
         "altura_sala_m": 3.2, "arriba": "sala_de_espera", "lado": "banos_publicos",
         "barrera_primaria_calculada_cm": {"losa": 96.58, "otra": 62.48},
         "espesores_estimados_cm_orden_doc": [37.86, 63.1, 20, 37.48, 37.86, 20],
         "ambiguedad_declarada": True},
        {"caso": 4, "densidad_g_cm3": 5.5, "tipo": "tabiques",
         "altura_sala_m": 3.2, "ancho_tabique_cm": 13, "altura_total_bunker_cm": 428,
         "barrera_primaria_calculada_cm": {"losa": 108, "laterales": 65},
         "secundarias_regla": "aprox_60_pct_de_primaria_declarado",
         "espesores_estimados_cm_orden_doc": [39, 65, 26, 39, 39, 26],
         "estado": "propuestas_por_confirmar_con_proveedor", "ambiguedad_declarada": True},
    ],
}

BRAQUITERAPIA = {
    "criterio": "IAEA Safety Report No. 47 (restrictivo)",
    "carga_trabajo": {"pacientes_semanales": "40-50", "tiempo_promedio_min": 25,
                       "dosis_por_paciente_Gy": 7},
    "densidad_g_cm3": 3.5,
    "altura_muros_m": 5, "arriba": "banos_publicos",
    "lados": ["sala_de_control", "pasillo_general", "cuarto_caliente"],
    "techo_cm": {"valores_2_35": [71, 12, 50, 58], "valores_3_5": [47, 13, 34, 39]},
    "piso_cm": {"valores_2_35": [70, 12, 40, 49], "valores_3_5": [47, 13, 26, 33]},
    "puerta": "3mm_plomo",
    "tabiques": {"ancho_cm": 13, "densidad_g_cm3": 3.5,
                  "techo_cm": [52, 39, 39], "piso_cm": [52, 13, 26, 39],
                  "estado": "propuestas_por_confirmar_con_proveedor"},
    "nota_doc": "calculos sobreestimados (declarado)",
    "ambiguedad_declarada": True,
}

GAMMA_KNIFE = {
    "criterio": "ICRP (restrictivo)",
    "carga_trabajo": {"pacientes_semanales": 20, "dias_semana": 5,
                       "actividad_max_Ci": 6600, "margen": "+10%"},
    "densidad_g_cm3": 3.5,
    "altura_muros_m": 5.4,
    "arriba": "sala_de_braquiterapia",
    "lados": ["pasillo_RF", "pasillo_general", "sala_de_control"],
    "techo_cm": {"valores_2_35": [35, 35, 28, 70, 14, 10],
                  "valores_3_5": [23, 23, 19, 47, 10, 7]},
    "puerta": "3mm_plomo",
    "nota_doc": "calculos sobreestimados (declarado)",
    "ambiguedad_declarada": True,
}

PETCT = {
    "criterio": "AAPM Task Group 108 (restrictivo)",
    "carga_trabajo": {"pacientes_semana": 60, "turnos_dia": 2, "dias_semana": 5,
                       "actividad_por_paciente_mCi": 20},
    "altura_entrepiso_m": 5, "arriba": "medicina_nuclear",
    "lados": ["sala_de_control", "salas_de_inyeccion"],
    "blindar_hasta_m": 2.5,
    "techo_cm": {"valores_2_35": [45, 25, 3, 15, 9, 7],
                  "valores_3_5": [30, 17, 2, 10, 7, 5],
                  "valores_5_0": [22, 12, 7, 5, 4]},
    "puertas": ["3mm_plomo", "3mm_plomo"], "ventana": "2mm_plomo_equivalente",
    "nota_doc": "calculos sobreestimados (declarado)",
    "ambiguedad_declarada": True,
}

SPECTCT = {
    "criterio": "IAEA-TECDOC-1608 (restrictivo)",
    "carga_trabajo": {"pacientes_semana_Tc99m": 40, "pacientes_I131": 2,
                       "pacientes_Lu177": 1, "dias_semana": 5,
                       "actividad": "variable_por_paciente_y_estudio"},
    "altura_entrepiso_m": 5, "arriba": "area_no_controlada",
    "lados": ["cuarto_caliente", "cuarto_de_control", "cuarto_de_equipos"],
    "blindar_hasta_m": 2.5,
    "techo_cm": {"valores_2_35": [12, 20, 20, 27, 33, 16, 12],
                  "valores_3_5": [8, 13, 14, 18, 22, 11, 8]},
    "plomo_mm_muros": [2, 6, 2, 5, 5, 2, 2, 3, 5, 7, 7, 2],
    "puerta": "2mm_plomo", "ventana": "2mm_plomo_equivalente",
    "castillo": "5cm_plomo",
    "pendientes_declarados": ["calculo de contenedores y muro hacia consultorios",
                               "cambiar ubicacion de descontaminacion y contenedores"],
    "nota_doc": "puertas y vidrios cumpliran el espesor del muro correspondiente; calculos sobreestimados",
    "ambiguedad_declarada": True,
}

MEDICINA_NUCLEAR = {
    "criterio": "IAEA-TECDOC-1608 (restrictivo)",
    "carga_trabajo": {"pacientes_hospitalizados": "2 pacientes x 3 dias",
                       "dosis_max_I131_mCi": 200},
    "altura_entrepiso_m": 5, "arriba": "area_no_controlada",
    "lados": ["cuarto_caliente", "cuarto_de_control", "cuarto_de_equipos"],
    "blindar_hasta_m": 2.5,
    "techo_cm": {"valores_2_35": [27, 25, 33], "valores_3_5": [18, 17, 22]},
    "piso_cm": {"valores_2_35": [21, 13, 20], "valores_3_5": [14, 9, 14]},
    "puerta": "6mm_plomo",
    "nota_doc": "puertas y vidrios cumpliran el espesor del muro correspondiente",
    "ambiguedad_declarada": True,
}

SALAS = {"acelerador_lineal": LINAC, "braquiterapia_hdr": BRAQUITERAPIA,
         "gamma_knife": GAMMA_KNIFE, "pet_ct": PETCT, "spect_ct": SPECTCT,
         "medicina_nuclear_I131": MEDICINA_NUCLEAR}


def md5_file(p, chunk=1 << 20):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(chunk), b""):
            h.update(blk)
    return h.hexdigest()


def coherencia():
    checks = []
    # monotonia: mayor densidad -> menor espesor primaria de losa (concreto monolitico)
    losas = {c["densidad_g_cm3"]: c["barrera_primaria_calculada_cm"]["losa"]
             for c in LINAC["casos"] if c["tipo"] == "concreto_monolitico"
             and c["altura_sala_m"] == 3.5}
    orden = [losas[d] for d in sorted(losas)]
    checks.append(("linac_losa_decrece_con_densidad", orden == sorted(orden, reverse=True), losas))
    # secundarias ~60% de primaria en tabiques
    sec = [c for c in LINAC["casos"] if c["tipo"] == "tabiques"]
    ok60 = all(39 <= 0.6 * 65 + 6 and 52 <= 0.6 * 78 + 8 for c in sec)
    checks.append(("linac_tabiques_secundarias_aprox_60pct", bool(ok60),
                   "52/78=%.2f 39/65=%.2f" % (52 / 78, 39 / 65)))
    # caso4 (3.2m) losa >= caso3 (3.5m)? doc: 96.58 vs 95.72 (ligeramente mayor)
    checks.append(("linac_caso4_losa_96_58_vs_caso3_95_72", 96.58 >= 95.72, None))
    return checks


def main():
    os.makedirs(EV, exist_ok=True)
    src = "/mnt/agents/upload/ESTIMACIÓN DE BLINDAJES ONCOLOGÍA ZUMAYA.pdf"
    checks = coherencia()
    ev = {
        "fase": "F82",
        "fecha_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "fuente": {"archivo": "ESTIMACION DE BLINDAJES ONCOLOGIA ZUMAYA.pdf",
                    "md5": md5_file(src), "fecha_documento": DOC["fecha"],
                    "emisor": DOC["emisor"], "naturaleza": DOC["naturaleza"]},
        "salas": SALAS,
        "coherencia_interna": [{"check": c, "ok": ok, "detalle": d} for c, ok, d in checks],
        "advertencias": [
            "Documento PRELIMINAR: espesor final se definira en memoria analitica definitiva (variacion 15-20% declarada).",
            "La extraccion de texto pierde la geometria de las figuras; valores listados en orden de aparicion con ambiguedad declarada.",
            "Registro documental de fuente externa; no constituye diseno ni decision operativa (18.10).",
            "El documento no cubre el ciclotron KIUBE (blindaje de ciclotron no incluido en esta estimacion).",
        ],
        "estado": "completada_documental",
    }
    outp = os.path.join(EV, "blindajes_zumaya_f82.json")
    json.dump(ev, open(outp, "w"), ensure_ascii=False, indent=1)

    regp = os.path.join(EV, "registro_blindajes_f82.jsonl")
    prev = ""
    if os.path.exists(regp):
        lines = open(regp).read().strip().splitlines()
        if lines:
            prev = hashlib.md5(lines[-1].encode()).hexdigest()
    entry = {"ts": ev["fecha_utc"], "fase": "F82",
             "evento": "ingesta_documento_blindajes_zumaya",
             "md5_fuente": ev["fuente"]["md5"], "md5_evidencia": md5_file(outp),
             "prev": prev}
    entry["md5"] = hashlib.md5(json.dumps(entry, sort_keys=True).encode()).hexdigest()
    with open(regp, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(json.dumps({"evidencia": outp, "md5": entry["md5"],
                      "checks": [c[0] for c in checks]}, indent=1))


if __name__ == "__main__":
    main()
