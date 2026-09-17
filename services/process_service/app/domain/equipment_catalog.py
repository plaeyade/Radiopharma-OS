"""Catálogo de equipamiento radiofarmacéutico (Fase 30).

49.11: TODA especificación (energía, corriente, potencia, rendimiento,
conductividad, vida útil) lleva fuente citada. Lo que no tiene fuente
externa queda marcado "pendiente_fuente" — el tablero lo muestra.

Blancos de terceros: el estatus "no_autorizado" es una ADVERTENCIA
operativa (garantía/calificación), nunca una recomendación de uso (18.10).
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Ciclotrones (complementa CICLOTRONES de cost_engine)
# ---------------------------------------------------------------------------

CICLOTRONES_EXT = {
    "abt_bg75": {
        "nombre": "ABT BG-75 Biomarker Generator (Best/ABT)",
        "energia_mev": 7.5,
        "corriente_max_ua": 5.0,
        "corriente_rutina_ua": 4.5,
        "blancos": 3,
        "blanco_tipo": "internos, no simultáneos",
        "autoblindado": True,
        "potencia_operacion_kw": 5.0,   # "<5 kW" → cota superior declarada
        "fuente": ("Zaman 2019 (PMC6709360): 7.5 MeV H+, ≤5 µA interna, 3 blancos, "
                   "autoblindado; ABT Technical Overview: potencia operación <5 kW. "
                   "Ruptura de blanco reportada a 5.5 µA — límite del fabricante 5 µA"),
    },
    "best_b100": {
        "nombre": "Best B-100 (TeamBest)",
        "energia_mev": 7.5,
        "corriente_max_ua": None,  # pendiente_fuente
        "corriente_rutina_ua": None,
        "blancos": None,
        "blanco_tipo": "integrado con módulo de química y QC FDG",
        "autoblindado": True,
        "potencia_operacion_kw": None,  # pendiente_fuente
        "fuente": ("Best Cyclotron Systems (bestcyclotron.com/about): B-100 7.5 MeV "
                   "autoblindado integrado, produce 18FDG y Na18F, dosis única o lote, "
                   "laboratorio completo en 5×5 m. Corriente y potencia: pendiente_fuente"),
    },
    "best_b6_15": {
        "nombre": "Best B6-15 (TeamBest, energía variable)",
        "energia_mev": 15.0,
        "energia_min_mev": 6.0,
        "corriente_max_ua": 1000.0,
        "corriente_rutina_ua": None,  # depende del blanco
        "blancos": None,
        "blanco_tipo": "externos de alta corriente",
        "autoblindado": False,
        "potencia_operacion_kw": None,  # pendiente_fuente
        "fuente": ("BCS EINPresswire 2021-06-03 y folleto 2026: 6–15 MeV variable, "
                   "1–1000 µA extraída, fuente de iones externa; produce 18F, 68Ga, "
                   "89Zr, 99mTc, 11C, 13N, 15O, 64Cu, 67Ga, 111In, 124I, 225Ac, 103Pd"),
    },
    "ge_pettrace_840": {
        "nombre": "GE PETtrace 840",
        "energia_mev": 16.5,
        "corriente_max_ua": 60.0,      # configuración estándar citada
        "corriente_max_demostrada_ua": 200.0,
        "blancos": 6,
        "blanco_tipo": "externos, doble blanco simultáneo",
        "autoblindado": False,
        "potencia_operacion_kw": None,  # pendiente_fuente
        "fuente": ("PETtrace 800 data sheet rev3: 16.5 MeV, 60 µA estándar; "
                   "Bosko 2005 (Texas A&M): 60 µA, doble blanco; Eriksson 2012 "
                   "(AIPC 1509:66): rutina 180 µA demostrada, 200 µA en evaluación "
                   "con blanco W/Cu autoblindado"),
    },
    "ge_pettrace_860": {
        "nombre": "GE PETtrace 860",
        "energia_mev": 16.5,
        "corriente_max_ua": 60.0,
        "corriente_max_demostrada_ua": 200.0,
        "blancos": 6,
        "blanco_tipo": "externos, doble blanco simultáneo",
        "autoblindado": False,
        "potencia_operacion_kw": None,
        "fuente": ("PETtrace 800 data sheet rev3 (840/860/880): 16.5 MeV, 60 µA; "
                   "IFMP Plovdiv 2019 (CERN indico): PETtrace 860 operación real "
                   "35-38 µA blanco, eficiencia fuente de iones 0.22"),
    },
    "ge_pettrace_880": {
        "nombre": "GE PETtrace 880",
        "energia_mev": 16.5,
        "corriente_max_ua": 60.0,
        "corriente_max_demostrada_ua": 200.0,
        "blancos": 6,
        "blanco_tipo": "externos, doble blanco simultáneo",
        "autoblindado": False,
        "potencia_operacion_kw": None,
        "fuente": ("PETtrace 800 data sheet rev3 (840/860/880): 16.5 MeV, 60 µA; "
                   "Asp 2020 (PubMed 31778235): rango rutinario 10-100 µA"),
    },
    "lbt_7": {
        "nombre": "Longevous Beamtech serie 7 MeV (China)",
        "energia_mev": 7.0,
        "corriente_max_ua": None,
        "blancos": None,
        "blanco_tipo": "pendiente_fuente",
        "autoblindado": None,
        "potencia_operacion_kw": None,
        "fuente": ("Preqin asset profile 2025: Longevous Beamtech (Mianyang, 2017) "
                   "produce ciclotrones de 7, 11 y 20 MeV para isótopos PET; "
                   "corriente/blancos/potencia: pendiente_fuente (ficha del fabricante)"),
    },
    "lbt_11": {
        "nombre": "Longevous Beamtech serie 11 MeV (China)",
        "energia_mev": 11.0,
        "corriente_max_ua": None,
        "blancos": None,
        "blanco_tipo": "pendiente_fuente",
        "autoblindado": None,
        "potencia_operacion_kw": None,
        "fuente": ("Preqin asset profile 2025: series 7/11/20 MeV. "
                   "Corriente/blancos/potencia: pendiente_fuente"),
    },
    "lbt_20": {
        "nombre": "Longevous Beamtech serie 20 MeV (China)",
        "energia_mev": 20.0,
        "corriente_max_ua": None,
        "blancos": None,
        "blanco_tipo": "pendiente_fuente",
        "autoblindado": None,
        "potencia_operacion_kw": None,
        "fuente": ("Preqin 2025 + chinacyclotron.com: serie 20 MeV; LB-30TP "
                   "(13-35 MeV p) en desarrollo (CYC2025 Chengdu). "
                   "Corriente/blancos/potencia: pendiente_fuente"),
    },
}

# ---------------------------------------------------------------------------
# Módulos de síntesis
# ---------------------------------------------------------------------------

MODULOS_SINTESIS = {
    "neptis_rs": {
        "fabricante": "ORA (Bélgica)",
        "tipo": "casete, síntesis nucleofílica 18F sin HPLC",
        "aplicaciones": ["18F-FDG", "18F-NaF", "18F-FLT", "18F-FMISO",
                          "18F-colina", "18F-F-acetato", "18F-FDOPA", "68Ga", "177Lu"],
        "nota": ">70 % rendimiento no corregido FDG; 100+ instalados; GAMP5, 21 CFR 11",
        "fuente": "oraneptis.com/products/neptis-rs (consulta 2026-09)",
    },
    "neptis_db": {
        "fabricante": "ORA (Bélgica)",
        "tipo": "casete, doble corrida FDG consecutiva con limpieza automática",
        "aplicaciones": ["18F-FDG (doble lote)"],
        "nota": "Compatible con casetes y química TracerLab Mx",
        "fuente": "oraneptis.com/products/neptis-rs (consulta 2026-09)",
    },
    "neptis_lc": {
        "fabricante": "ORA (Bélgica)",
        "tipo": "casete compacto (3 por mini-celda)",
        "aplicaciones": ["18F-FDG", "18F-FLT", "18F-FMISO", "18F-colina",
                          "68Ga", "188Re", "177Lu", "89Zr", "90Y", "131I", "225Ac", "99mTc"],
        "nota": ">70 % no corregido FDG; 20 kg",
        "fuente": "oraneptis.com/products/neptis-lc (consulta 2026-09)",
    },
    "neptis_perform": {
        "fabricante": "ORA (Bélgica)",
        "tipo": "casete con HPLC integrado + reformulación SPE",
        "aplicaciones": ["18F-PSMA-1007", "18F-FET", "18F-FES", "18F-FDOPA",
                          "18F-fallypride", "68Ga", "177Lu"],
        "nota": "Selector de 2 columnas HPLC; doble corrida FDG opcional",
        "fuente": "oraneptis.com/products/neptis-perform (consulta 2026-09)",
    },
    "trasis_allinone": {
        "fabricante": "Trasis (Bélgica)",
        "tipo": "casete universal, 30 actuadores (18-36), HPLC semi-preparativo",
        "aplicaciones": [">40 trazadores: 18F, 11C, 68Ga, 64Cu"],
        "nota": "Hasta 4 columnas HPLC, 15 detectores; manifolds de volumen muerto cero",
        "fuente": "trasis.com/en/product/allinone + Li 2016 (PMC5843816)",
    },
    "trasis_miniallinone": {
        "fabricante": "Trasis (Bélgica)",
        "tipo": "casete compacto para radiometales y procesos sin HPLC",
        "aplicaciones": ["68Ga", "177Lu", "99mTc", "89Zr", "64Cu", "90Y", "188Re", "203Pb"],
        "nota": "Producción GMP rutinaria de radiometales; teranóstica",
        "fuente": "trasis.com/en/product/allinone-mini (consulta 2026-09)",
    },
    "iba_cassy": {
        "fabricante": "IBA (Bélgica)",
        "tipo": "CASSY — Compact Automated Scalable SYnthesis, radiometales",
        "aplicaciones": ["radiometales: purificación y radiomarcado", "radiotrazadores"],
        "nota": "Lanzado 2025-05-13; hasta 6 unidades apiladas en una celda caliente",
        "fuente": "IBA press release 2025-05-13 (iba-worldwide.com)",
    },
    "scintomics_grp4v": {
        "fabricante": "Scintomics (Alemania)",
        "tipo": "GRP 4V, casete, modo experto/GMP-App",
        "aplicaciones": ["18F-FDG", "18F-FMISO", "18F-FET", "18F-FLT", "18F-siPSMA-14",
                          "68Ga", "177Lu", "99mTc-PSMA", "89Zr", "90Y", "18F-NaF"],
        "nota": ">100 centros, decenas de miles de producciones; apilable",
        "fuente": "Scintomics GRP module series (radnostix/att PDF, consulta 2026-09)",
    },
}

# ---------------------------------------------------------------------------
# Kits de radioquímica
# ---------------------------------------------------------------------------

KITS_RADIOQUIMICA = {
    "abx_fdg_kit": {
        "fabricante": "ABX (Radeberg, Alemania)",
        "producto": "Reagent kit + cassette [18F]FDG (PE-SC-07)",
        "sintesis": "2 pasos ABX, 40 min, purificación por cartucho, 13 mL final, Ph. Eur.",
        "calidad": "grado investigación (gamma irradiado); cadena GMP completa disponible",
        "fuente": "abx.de/products/reagent-kits-cassettes (consulta 2026-09)",
    },
    "abx_multitracer": {
        "fabricante": "ABX",
        "producto": "Kits FDG, F-DOPA, FLT, F-colina, NaF, FMISO, FES, FET",
        "sintesis": "precursores y kits validados por módulo; DMF de manosa triflato",
        "calidad": "GMP API auditado; distribuidor de agua 18O grado FDG y GMP",
        "fuente": "petros-hgs10.de / abx.de (consulta 2026-09)",
    },
    "scintomics_kits": {
        "fabricante": "Scintomics",
        "producto": "Casetes y kits para módulos GRP (FDG, FET, FLT, FMISO, siPSMA)",
        "sintesis": "casetes estériles por aplicación; modo GMP-App",
        "calidad": "GMP",
        "fuente": "globalmedicalsolutions.com.au/pages/scintomics (consulta 2026-09)",
    },
    "trasis_kits": {
        "fabricante": "Trasis",
        "producto": "Casetes desechables AllInOne / miniAllInOne con reactivos",
        "sintesis": "casete único por trazador; QC integrado",
        "calidad": "GMP",
        "fuente": "trasis.com (consulta 2026-09)",
    },
}

# ---------------------------------------------------------------------------
# Blancos (targetry): materiales con propiedades citadas
# ---------------------------------------------------------------------------

MATERIALES_BLANCO = {
    "plata": {
        "conductividad_w_mk": 415.0, "inercia_quimica": "buena",
        "activacion": "105Ag/106mAg/109Cd/110mAg — dosis mayor",
        "nota": ("referencia histórica 25 años; forma coloides en agua enriquecida "
                 "que bajan el rendimiento"),
        "fuente": "OSTI 945375 + PMC10145432 (comparativa Ta vs Ag, 2023)",
    },
    "tantalio": {
        "conductividad_w_mk": 57.0, "inercia_quimica": "excelente",
        "activacion": "menor dosis que plata; fluoruro de mejor calidad",
        "nota": ("baja conductividad lo limitó a ≤1 kW salvo diseño mejorado "
                 "(radiador posterior); más inerte y más vida útil del blanco"),
        "fuente": "OSTI 945375 (DUKE-1/2 Ta) + PMC10145432",
    },
    "niobio": {
        "conductividad_w_mk": 53.7, "inercia_quimica": "excelente",
        "activacion": "92mNb/93mMo posibles (Köhler, tabla PMC10145432)",
        "nota": ("blanco Nb Lund: 93 GBq F-18 en 1 h @ 40 µA (~300 % vs blanco "
                 "de plata previo); químicamente inerte verificado"),
        "fuente": "Lund Univ. (lup.lub.lu.se) desarrollo blanco Nb, MC-16",
    },
    "titanio": {
        "conductividad_w_mk": 21.9, "inercia_quimica": "buena",
        "activacion": "46Sc/48V (Mochizuki, tabla PMC10145432)",
        "nota": "blancos Ti/Nb de baja presión alto rendimiento (Berridge 2002)",
        "fuente": "PMC10145432 + Berridge 2002 (Semantic Scholar)",
    },
    "niquel": {"conductividad_w_mk": 90.9, "inercia_quimica": "regular",
               "activacion": "—", "nota": "material de cuerpo citado en targetry PET",
               "fuente": "PET Cyclotron Targetry slideshare (tabla propiedades)"},
    "aluminio": {"conductividad_w_mk": 167.0, "inercia_quimica": "regular",
                 "activacion": "—", "nota": "cuerpos termosyphon con inserto de Ta",
                 "fuente": "OSTI 945375"},
    "tungsteno_cobre": {
        "conductividad_w_mk": None, "inercia_quimica": "—",
        "activacion": "187W (T½ 24 h) domina; 60Co ~250× menor a 24 h post-EOB",
        "nota": ("blanco autoblindado W/Cu de PETtrace: reduce dosis de foils "
                 "Havar ×8-10 y permite rutina a 180-200 µA"),
        "fuente": "Eriksson 2012 (AIPC 1509:66)",
    },
}

ESTATUS_PROVEEDOR = ("oem_original", "tercero_autorizado", "tercero_no_autorizado")

TIPOS_BLANCO = {
    "liquido_agua_enriquecida": {
        "descripcion": "H2[18O] → 18F (y H2O natural → 13N-NH3 in-target)",
        "presion": "sellado o sobrepresión He; ebullición durante irradiación",
        "fuente": "PET Cyclotron Targetry (slideshare, sección water targets)",
    },
    "gaseoso": {
        "descripcion": "14N2 → 11C (p,α); 15N2 → 15O (p,n); cuerpo cilíndrico presurizado",
        "presion": "alta presión, ventana delgada enfriada",
        "fuente": "PET Cyclotron Targetry (sección gas targets) + ORISE ML12047A027",
    },
    "solido": {
        "descripcion": "64Ni electrodepositado → 64Cu (p,n); lanzadera/PTS",
        "presion": "atmósfera/vacío; enfriamiento por backing",
        "fuente": "IAEA Pub1717 (64Cu) + Frontiers Phys 2022 (TR-19)",
    },
}


def validar_estatus_proveedor(estatus: str) -> str:
    if estatus not in ESTATUS_PROVEEDOR:
        raise ValueError(f"estatus debe ser uno de {ESTATUS_PROVEEDOR}")
    if estatus == "tercero_no_autorizado":
        return ("ADVERTENCIA: blanco de tercero NO autorizado — puede anular "
                "garantía del ciclotrón y exige calificación propia (decisión "
                "operativa humana, 18.10)")
    return estatus


# ---------------------------------------------------------------------------
# Fuentes de iones: parámetros y optimización (consultivo)
# ---------------------------------------------------------------------------

FUENTES_IONES = {
    "penning_interna_bg75": {
        "tipo": "Penning (PIG) interna, H+",
        "parametros": {"arco_ma": 72.0, "voltaje_arco_v": 832.0,
                        "gas_sccm": (4.0, 5.0), "arco_max_ma": 400.0,
                        "potencia_estable_w": 60.0},
        "vida_catodo": "no reportada",
        "fuente": "Dehnel (JLab indico 13663): BEST/ABT BG-75, 5 µA @ 7.5 MeV",
    },
    "penning_pettrace": {
        "tipo": "Penning (PIG) interna, H-",
        "parametros": {"arco_ma_tipico": (139.0, 160.0),
                        "eficiencia_fuente": 0.22},
        "vida_catodo": "16-26 semanas a 55-60 h/sem (880-1560 h)",
        "nota": ("reemplazo típico por erosión de la ranura de la cámara anódica "
                 "('chimney'); cátodos reutilizables 2-3 chimneys; contaminación "
                 "por fuga de aire degrada la superficie"),
        "fuente": ("Dehnel (JLab indico 13663, com. Andry Manuals SPIE 2014) + "
                   "IFMP Plovdiv 2019 (arco 139-160 mA, eficiencia 0.22)"),
    },
    "multicusp_externa_best": {
        "tipo": "multicúspide externa, H-",
        "parametros": {"corriente_fuente_ma": 5.0},
        "vida_catodo": "pendiente_fuente",
        "fuente": "Best 15p datasheet (bestcyclotron.com): fuente externa multicusp 5 mA",
    },
}


def recomendacion_fuente_iones(fuente_id: str) -> dict:
    """Puntos de optimización de la fuente de iones (consultivo, 18.10).

    Nunca ajusta parámetros: enumera palancas citadas y enlaza el gemelo de
    desgaste (Fase 27) para la vida del cátodo.
    """
    if fuente_id not in FUENTES_IONES:
        raise ValueError("fuente_id no catalogada")
    f = FUENTES_IONES[fuente_id]
    palancas = [
        "corriente de arco: subir dentro del rango citado eleva corriente de haz hasta saturación del espacio de carga (declarado)",
        "flujo de gas (sccm): optimizar presión de descarga — fuera de rango citado degrada el cátodo",
        "vida del cátodo/chimney: seguimiento con el gemelo de desgaste (Fase 27), reemplazo por erosión de ranura",
        "fugas de aire: contaminan la superficie del cátodo y reducen salida (citado PETtrace)",
        "eficiencia de extracción: PETtrace real 0.22 (IFMP 2019) — margen de mejora por ajuste de puller/slit",
    ]
    return {
        "fuente_id": fuente_id,
        "parametros_citados": f["parametros"],
        "vida_catodo": f["vida_catodo"],
        "palancas_optimizacion": palancas,
        "fuentes": f["fuente"],
        "naturaleza": ("RECOMENDACIÓN — soporte a la decisión (18.10). El ajuste "
                       "de la fuente de iones es decisión operativa con datos de "
                       "haz reales; no bloquear por ausencia de ellos."),
    }

# ---------------------------------------------------------------------------
# Fase 31: ampliaciones citadas
# ---------------------------------------------------------------------------

CICLOTRONES_EXT.update({
    "ge_minitrace_qilin": {
        "nombre": "GE MINItrace Qilin",
        "energia_mev": None,   # pendiente_fuente (ficha pública no la declara)
        "corriente_max_ua": None,
        "blancos": None,
        "blanco_tipo": "integrado, totalmente automatizado",
        "autoblindado": True,
        "potencia_operacion_kw": None,
        "fuente": ("GE Healthcare MINItrace Qilin (gehealthcare.com, consulta 2026-09): "
                   "compacto, autoblindado, vertical, cubre >99 % de procedimientos "
                   "clínicos PET, capacidad para 3-4 escáneres propios + distribución "
                   "local. Energía/corriente/potencia: pendiente_fuente"),
    },
    "ge_pettrace_890": {
        "nombre": "GE PETtrace 890",
        "energia_mev": 16.5,
        "corriente_max_ua": 160.0,
        "blancos": 6,
        "blanco_tipo": "externos, doble blanco simultáneo; blanco sólido disponible",
        "autoblindado": False,
        "potencia_operacion_kw": None,
        "fuente": ("PT800 Cyclotron System Data Sheet rev3: PETtrace 890, 160 µA; "
                   "instalación U. Oklahoma 2025-09 (g-medtech). Rendimientos EOB "
                   "citados en RENDIMIENTOS_SINTESIS"),
    },
})

# Targets F-18 de alto rendimiento (citados)
TARGETS_F18_ALTO_RENDIMIENTO = {
    "iba_nirta_conical_5": {"volumen_llenado_ml": 1.8, "corriente_ua": 45,
        "rendimiento_sat_mci_ua": 230.0, "salida_2h_ci": 5.5,
        "presion_bar": 40, "material": "niobio, ventana Havar 35 µm",
        "fuente": "Devillet 2013 (CYCLOTRONS2013 WEPSH043, IBA)"},
    "iba_nirta_conical_8": {"volumen_llenado_ml": 2.3, "corriente_ua": 65,
        "rendimiento_sat_mci_ua": 224.0, "salida_2h_ci": 7.7,
        "presion_bar": 30, "material": "niobio, ventana Havar 35 µm",
        "fuente": "Devillet 2013 (CYCLOTRONS2013 WEPSH043, IBA)"},
    "iba_nirta_conical_12": {"volumen_llenado_ml": 2.7, "corriente_ua": 100,
        "rendimiento_sat_mci_ua": 228.0, "salida_2h_ci": 12.1,
        "presion_bar": 30, "material": "niobio, ventana Havar 35 µm",
        "fuente": "Devillet 2013 (CYCLOTRONS2013 WEPSH043, IBA)"},
    "iba_nirta_conical_16": {"volumen_llenado_ml": 4.2, "corriente_ua": 130,
        "rendimiento_sat_mci_ua": 235.0, "salida_2h_ci": 16.2,
        "presion_bar": 30, "material": "niobio, ventana Havar 35 µm",
        "nota": "145 µA / 2 h → 18 Ci medido; ruptura >50 bar",
        "fuente": "Devillet 2013 (CYCLOTRONS2013 WEPSH043, IBA)"},
    "iba_nirta_cilindrico_3xl": {"volumen_llenado_ml": 4.0, "corriente_ua": None,
        "rendimiento_sat_mci_ua": None, "salida_2h_ci": 13.0,
        "presion_bar": None, "material": "niobio",
        "nota": "referencia cilíndrica: la cónica 16 supera ~25 % a igual volumen",
        "fuente": "Devillet 2013, tabla comparativa cilíndrico vs cónico"},
    "lund_niobio_alto_rendimiento": {"volumen_llenado_ml": None, "corriente_ua": 40,
        "rendimiento_sat_mci_ua": None, "salida_2h_ci": None,
        "presion_bar": None, "material": "niobio",
        "nota": "93 GBq F-18 en 1 h @ 40 µA (~300 % vs blanco de plata previo)",
        "fuente": "Lund Univ. (lup.lub.lu.se), blanco Nb MC-16"},
    "ge_w_cu_autoblindado": {"volumen_llenado_ml": None, "corriente_ua": 200,
        "rendimiento_sat_mci_ua": None, "salida_2h_ci": None,
        "presion_bar": None, "material": "tungsteno/cobre autoblindado",
        "nota": "rutina 180 µA demostrada; dosis de foils Havar ×8-10 menor",
        "fuente": "Eriksson 2012 (AIPC 1509:66)"},
}

# Rendimientos de síntesis / EOB citados por equipo
RENDIMIENTOS_SINTESIS = {
    "neptis_fdg_no_corregido": {"valor_pct": 70.0, "cota": ">70 % no corregido",
        "modulos": ["neptis_rs", "neptis_db", "neptis_lc"],
        "fuente": "oraneptis.com/products/neptis-rs y /neptis-lc (consulta 2026-09)"},
    "pettrace_eob_gb": {
        "18F_840": 240.0, "18F_860": 400.0, "18F_880": 518.0,
        "11C_CO2": 166.0, "13N_NH3_EOS": 16.6, "15O_O2_EOS": 44.4,
        "15O_H2O_EOS": 44.0, "18F_F2_D": 11.0, "18F_F2_H": 66.5,
        "fuente": "GE Healthcare PETtrace 800 series yield specifications (consulta 2026-09)"},
    "lbt_rendimientos": {"estado": "pendiente_fuente — ficha del fabricante no pública",
        "fuente": "Preqin 2025 / chinacyclotron.com (solo energías 7/11/20 MeV)"},
}

# Gases de alta pureza (costo y descripción citados)
GASES_ALTA_PUREZA = {
    "n2_6_0": {"descripcion": "Nitrógeno 6.0 (99.9999 %) — gas de blanco gaseoso C-11 (mezcla N2/O2 39:1)",
        "precio_declarado": "lista Praxair 2018: N2 5.0 UHP $35.63 USD/cil + renta; 6.0 pendiente_fuente",
        "fuente": "Lista Praxair (uiowa.edu 2018) + MDPI applsci 15:11946 (mezcla 39:1)"},
    "he_5_0": {"descripcion": "Helio 5.0 — sobrepresión de blancos líquidos, soplado de líneas, cryo",
        "precio_declarado": "lista Praxair 2018: He research $148.43-258.59 USD/cil + renta",
        "fuente": "Lista Praxair (uiowa.edu 2018)"},
    "ar_6_0": {"descripcion": "Argón 6.0 UHP — uso analítico QC (GC), gas de purga",
        "precio_declarado": "Humphries UHP: Ar $1678.97 USD/cil; gases simples desde $599.33/cil",
        "fuente": "humphriesinc.com ultra-high-purity (consulta 2026-09)"},
    "o2_5_0": {"descripcion": "Oxígeno 5.0 — mezcla de blanco C-11 (1/40), oxidante",
        "precio_declarado": "pendiente_fuente (cotización local)",
        "fuente": "declarado interno"},
    "h2_5_0": {"descripcion": "Hidrógeno 5.0 — reducción in-target 13N-NH3 (proceso etanol), GC-FID",
        "precio_declarado": "pendiente_fuente (cotización local)",
        "fuente": "declarado interno"},
}

# Proveedores mundiales de agua enriquecida H2-18O
PROVEEDORES_H2O18_MUNDIAL = {
    "nippon_sanso_japon": {"pais": "Japón", "nota": "único fabricante japonés; desde 2004, >30 países; 3ª planta → 600 kg/año (2015), destilación criogénica",
        "fuente": "C&EN 2013 + nsc.jp.nipponsanso.com (consulta 2026-09)"},
    "cambridge_isotope_usa": {"pais": "EE. UU.", "nota": "CIL — catálogo H2-18O varios grados",
        "fuente": "pendiente_fuente_precio (catálogo CIL, consulta 2026-09)"},
    "isotec_sigma_usa": {"pais": "EE. UU.", "nota": "Sigma-Aldrich ISOTEC ≥98 atom% grado PET",
        "fuente": "sigmaaldrich.com (consulta 2026-09, Fase 29)"},
    "nucmedcor_usa": {"pais": "EE. UU.", "nota": "NUCMEDCOR GMP 98 atom%, viales 10/20/50 g",
        "fuente": "nucmedcor.com (consulta 2026-09, Fase 29)"},
    "eurisotop_francia": {"pais": "Francia", "nota": "Eurisotop (filial CEA) — isótopos estables",
        "fuente": "pendiente_fuente_precio (eurisotop.com, consulta 2026-09)"},
    "silantes_alemania": {"pais": "Alemania", "nota": "desde EUR 170/g (98 %)",
        "fuente": "silantes.com (consulta 2026-09, Fase 29)"},
    "abx_alemania": {"pais": "Alemania", "nota": "distribuidor agua 18O grado FDG y GMP",
        "fuente": "abx.de (consulta 2026-09, Fase 29)"},
    "chempep_usa": {"pais": "EE. UU.", "nota": "98 %: 1 g $150 / 25 g $1500",
        "fuente": "chempep.com (consulta 2026-09, Fase 29)"},
    "isotopeshop": {"pais": "—", "nota": "98 %: 1 g EUR 193 / 5 g EUR 725",
        "fuente": "isotopeshop.com (consulta 2026-09, Fase 29)"},
    "ntp_sudafrica": {"pais": "Sudáfrica", "nota": "NTP Radioisotopes — línea de isótopos estables por confirmar para H2-18O",
        "fuente": "pendiente_fuente (ntpradioisotopes.com)"},
}
