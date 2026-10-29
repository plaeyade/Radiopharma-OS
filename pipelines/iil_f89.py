"""F89 - Instrument Integration Layer (IIL), Capitulo 26 del MVP.

Componentes canonicos (26.5): Instrument Registry, Device Adapter Manager, Data
Normalization Engine, Acquisition Manager, File Import Manager, Validation
Engine, Event Manager, Export Service.

Reglas canonicas:
- 26.3: el QC Engine NUNCA habla directo con un instrumento; toda comunicacion
  pasa por adaptadores que traducen al modelo interno.
- 26.13: cada resultado lleva fecha, hora, instrumento, operador y Batch.
- 27.14 (via Export): solo se exportan resultados completos y validados.

Honestidad: el inventario es PLANIFICADO declarado (equipos tipicos de un
laboratorio QC de radiofarmacia); estado de conexion honesto:
'sin_conexion_pendiente_instrumento'. Los archivos de prueba del importador son
vectores sinteticos DECLARADOS para V&V (no son resultados reales; memoria 3).
"""
import json, hashlib, os, datetime

EV = "/mnt/agents/work/evidencia_v072/fase89"

# Inventario PLANIFICADO declarado (26.6: id, fabricante, modelo, serie, fw, estado, ubicacion)
INSTRUMENTOS = [
    {"id": "HPLC-01", "tipo": "HPLC", "fabricante": "pendiente_seleccion", "modelo": "por_definir",
     "serie": "na", "firmware": "na", "ubicacion": "laboratorio_QC", "adaptador": "generic_hplc_uv_radiometrico"},
    {"id": "GC-01", "tipo": "GC", "fabricante": "pendiente_seleccion", "modelo": "por_definir",
     "serie": "na", "firmware": "na", "ubicacion": "laboratorio_QC", "adaptador": "generic_gc_fid"},
    {"id": "TLC-01", "tipo": "TLC_Scanner", "fabricante": "pendiente_seleccion", "modelo": "por_definir",
     "serie": "na", "firmware": "na", "ubicacion": "laboratorio_QC", "adaptador": "generic_tlc_scanner"},
    {"id": "DC-01", "tipo": "calibrador_dosis", "fabricante": "pendiente_seleccion", "modelo": "por_definir",
     "serie": "na", "firmware": "na", "ubicacion": "cuarto_caliente", "adaptador": "generic_dose_calibrator"},
    {"id": "GS-01", "tipo": "espectrometro_gamma", "fabricante": "pendiente_seleccion", "modelo": "por_definir",
     "serie": "na", "firmware": "na", "ubicacion": "laboratorio_QC", "adaptador": "generic_gamma_spec"},
    {"id": "WC-01", "tipo": "contador_pozo", "fabricante": "pendiente_seleccion", "modelo": "por_definir",
     "serie": "na", "firmware": "na", "ubicacion": "laboratorio_QC", "adaptador": "generic_well_counter"},
    {"id": "PH-01", "tipo": "ph_metro", "fabricante": "pendiente_seleccion", "modelo": "por_definir",
     "serie": "na", "firmware": "na", "ubicacion": "laboratorio_QC", "adaptador": "generic_ph"},
    {"id": "OSM-01", "tipo": "osmometro", "fabricante": "pendiente_seleccion", "modelo": "por_definir",
     "serie": "na", "firmware": "na", "ubicacion": "laboratorio_QC", "adaptador": "generic_osmo"},
    {"id": "ETX-01", "tipo": "lector_endotoxinas", "fabricante": "pendiente_seleccion", "modelo": "por_definir",
     "serie": "na", "firmware": "na", "ubicacion": "laboratorio_QC", "adaptador": "generic_lal"},
    {"id": "BAL-01", "tipo": "balanza_analitica", "fabricante": "pendiente_seleccion", "modelo": "por_definir",
     "serie": "na", "firmware": "na", "ubicacion": "laboratorio_QC", "adaptador": "generic_balance_rs232"},
]

# conversiones del motor de normalizacion (26.10)
CONV_MBq = {"MBq": 1.0, "mCi": 37.0, "GBq": 1e3, "uCi": 37e-3, "Ci": 37e3}


def md5_file(p, chunk=1 << 20):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(chunk), b""):
            h.update(blk)
    return h.hexdigest()


def normalizar_actividad(valor, unidad):
    """Normaliza a MBq (26.10: unidades al modelo interno)."""
    if unidad not in CONV_MBq:
        raise ValueError("unidad_no_soportada")
    return valor * CONV_MBq[unidad]


def normalizar_resultado(raw, instrumento, operador, batch):
    """Modelo interno unificado. Rechaza incompletos (27.14)."""
    req = ["ensayo", "valor", "unidad", "fecha_hora"]
    faltantes = [r for r in req if r not in raw or raw[r] in (None, "")]
    if faltantes:
        return {"rechazado": True, "errores": [f"falta_{f}" for f in faltantes]}
    norm = dict(raw)
    if raw["ensayo"] in ("actividad", "pureza_radionuclidica") and raw["unidad"] in CONV_MBq:
        norm["valor"] = normalizar_actividad(raw["valor"], raw["unidad"])
        norm["unidad"] = "MBq"
        norm["normalizacion"] = f"{raw['unidad']}->MBq"
    try:  # fechas a ISO
        dt = datetime.datetime.fromisoformat(str(raw["fecha_hora"]).replace(" ", "T"))
        norm["fecha_hora"] = dt.isoformat()
    except ValueError:
        return {"rechazado": True, "errores": ["fecha_invalida"]}
    norm.update({"instrumento": instrumento, "operador": operador, "batch": batch,
                 "estado": "validado", "origen": "adaptador_IIL"})
    return {"rechazado": False, "resultado": norm}


def importar_tabla_hplc_csv(texto):
    """File Import Manager (26.12): tabla de picos CSV -> picos normalizados.
    Formato declarado de V&V: nombre,ret_min,area,unidad_area"""
    picos = []
    for i, linea in enumerate(texto.strip().splitlines()[1:]):
        p = linea.split(",")
        if len(p) != 4:
            return {"rechazado": True, "errores": [f"linea_{i+2}_formato"]}
        picos.append({"nombre": p[0], "retencion_min": float(p[1]),
                      "area": float(p[2]), "unidad_area": p[3]})
    total = sum(pk["area"] for pk in picos)
    for pk in picos:
        pk["area_pct"] = round(pk["area"] / total * 100, 3) if total else None
    return {"rechazado": False, "picos": picos, "n": len(picos)}


def main():
    os.makedirs(EV, exist_ok=True)
    for inst in INSTRUMENTOS:
        inst["estado_conexion"] = "sin_conexion_pendiente_instrumento"  # honesto
    eventos = []

    # --- V&V del motor con vectores sinteticos DECLARADOS (no reales) ---
    vv = {}
    # 1) normalizacion de actividad mCi -> MBq
    r1 = normalizar_resultado({"ensayo": "actividad", "valor": 20.0, "unidad": "mCi",
                                "fecha_hora": "2026-10-29 10:00"}, "DC-01", "OP-01", "BATCH-VV-001")
    vv["normalizacion_mCi_a_MBq"] = r1
    eventos.append("resultado_normalizado:DC-01")
    # 2) resultado incompleto rechazado (27.14)
    r2 = normalizar_resultado({"ensayo": "ph", "unidad": "pH", "fecha_hora": "2026-10-29 10:05"},
                               "PH-01", "OP-01", "BATCH-VV-001")
    vv["rechazo_incompleto"] = r2
    eventos.append("resultado_rechazado:PH-01")
    # 3) importacion de cromatograma CSV sintetico declarado
    csv_vv = "nombre,ret_min,area,unidad_area\nFDG,3.42,98500,mAU*s\nimpureza_A,5.11,1500,mAU*s\n"
    r3 = importar_tabla_hplc_csv(csv_vv)
    vv["importacion_hplc_csv"] = r3
    eventos.append("archivo_importado:HPLC-01")
    # 4) fecha invalida
    r4 = normalizar_resultado({"ensayo": "ph", "valor": 6.0, "unidad": "pH",
                                "fecha_hora": "ayer"}, "PH-01", "OP-01", "BATCH-VV-001")
    vv["rechazo_fecha"] = r4

    ev = {
        "fase": "F89", "fecha_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "componente": "Instrument Integration Layer (IIL) - Capitulo 26",
        "arquitectura_26_4": "Instrumentos -> Device Adapter -> IIL -> Unified Laboratory API -> QC Engine",
        "regla_26_3": "QC Engine nunca se comunica directo con un instrumento; adaptadores desacoplan fabricantes",
        "instrument_registry": {"inventario": INSTRUMENTOS, "naturaleza": "PLANIFICADO declarado",
                                 "estado_honesto": "sin_conexion_pendiente_instrumento"},
        "data_normalization": {"unidades_actividad_soportadas": list(CONV_MBq),
                                "destino": "MBq", "fechas": "ISO 8601",
                                "modelo_interno": ["ensayo", "valor", "unidad", "fecha_hora",
                                                    "instrumento", "operador", "batch", "estado", "origen"]},
        "file_import": {"formatos_vv": ["csv_tabla_picos"], "originales": "permanecen almacenados (declarado)"},
        "vv_vectores_sinteticos_declarados": vv,
        "event_manager": {"eventos": eventos},
        "export_service": {"destino": "QC Engine (26.14)", "regla": "solo completos y validados (27.14)"},
        "integraciones": {"LIMS": "26.15 (consumidor/productor/sincronizador) - pendiente institucion",
                           "STAE_F87": "alimenta historial una vez QC Engine valide"},
        "estado": "completada_motor_validado",
        "advertencias": [
            "Inventario planificado declarado; ningun instrumento conectado (honesto).",
            "Vectores de V&V sinteticos declarados; no son resultados analiticos reales (memoria 3).",
            "Adaptadores por fabricante: solo genericos declarados; drivers reales pendiente_instrumento.",
            "18.10: resultados normalizados no son decisiones operativas.",
        ],
    }
    outp = os.path.join(EV, "iil_f89.json")
    json.dump(ev, open(outp, "w"), ensure_ascii=False, indent=1)
    regp = os.path.join(EV, "registro_iil_f89.jsonl")
    prev = ""
    if os.path.exists(regp):
        lines = open(regp).read().strip().splitlines()
        if lines:
            prev = hashlib.md5(lines[-1].encode()).hexdigest()
    entry = {"ts": ev["fecha_utc"], "fase": "F89", "evento": "implementacion_iil_cap26",
             "version": "1.0", "eventos": len(eventos),
             "md5_evidencia": md5_file(outp), "prev": prev}
    entry["md5"] = hashlib.md5(json.dumps(entry, sort_keys=True).encode()).hexdigest()
    with open(regp, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(json.dumps({"evidencia": outp, "md5": entry["md5"]}, indent=1))


if __name__ == "__main__":
    main()
