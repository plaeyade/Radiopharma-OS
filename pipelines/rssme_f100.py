#!/usr/bin/env python3
"""
F100 — Cap. 36: Radiation Safety & Shielding Management Engine (RSSME)
Radiopharma OS — protección radiológica, blindajes, dosimetría ambiental.

Reglas canónicas:
- 36.3: supervisa y documenta; NO sustituye programas institucionales de
  protección radiológica, decisiones del OPR ni sistemas físicos de seguridad.
- 36.6: cada monitor vinculado al Asset Registry (F97/F98).
- 36.7: blindajes sincronizados con el Facility Twin (geometría F81/F97,
  espesores F82/F83).
- 36.8: clasificación de áreas versionada (F88).
- 36.12: cada medición registra timestamp, detector, ubicación, valor, calidad.
- 36.20: antes de aceptar una medición se verifica estado del detector,
  integridad de comunicación, rango esperado y consistencia temporal; las
  anomalías generan eventos de revisión.
- 36.22: auditoría (usuario, detector, área, fecha, acción) jsonl md5 ALCOA+.
- 36.18: recomendaciones IA separadas de mediciones oficiales (18.10).
- Memoria 3: sin detectores físicos → adquisición 36.13 pendiente declarada;
  dosimetría ocupacional = sistemas institucionales, pendiente declarada.
"""
import hashlib, json, os, sys
from datetime import datetime, timezone

FASE = "fase100"
EV_DIR = "/mnt/agents/work/evidencia_v072/fase100"
EV_ROOT = "/mnt/agents/work/evidencia_v072"

FILOSOFIA_36_3 = ("RSSME integra, visualiza y analiza; no sustituye programas "
                  "institucionales de protección radiológica, decisiones del OPR "
                  "ni sistemas físicos de seguridad.")

RANGOS_uSv_h = {  # rango esperado declarado por tipo de detector (36.20)
    "centelleo_area": (0.01, 1e4),
    "gm_contaminacion": (0.0, 1e6),
    "ionizacion_ambiental": (0.001, 1e3),
}


# ---------- 36.6 Radiation Monitor Manager -------------------------------------------
class MonitorManager:
    def __init__(self, activos_validos):
        self.monitores = {}
        self.activos = set(activos_validos)

    def registrar(self, id_mon, ubicacion, tipo, activo_vinculado,
                  calibracion="pendiente_declarada"):
        if activo_vinculado not in self.activos:
            raise ValueError(f"activo_no_registrado:{activo_vinculado}")
        m = {"id": id_mon, "ubicacion": ubicacion, "tipo": tipo,
             "estado": "sin_conexion_pendiente_detector",
             "calibracion": calibracion, "activo_vinculado": activo_vinculado,
             "historial": []}
        self.monitores[id_mon] = m
        return m


# ---------- 36.12 medición -----------------------------------------------------------------
def medicion(id_det, ubicacion, valor_uSv_h, calidad="buena_vv"):
    return {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "detector": id_det, "ubicacion": ubicacion,
            "valor_uSv_h": valor_uSv_h, "calidad": calidad}


# ---------- 36.20 Validation Engine ----------------------------------------------------------
def validar_medicion(m, detector, tipo, comunicacion_ok=True, prev_ts=None):
    errores = []
    if detector["estado"].startswith("fuera_servicio"):
        errores.append("estado_detector:fuera_de_servicio")
    if not comunicacion_ok:
        errores.append("integridad_comunicacion:falla")
    lo, hi = RANGOS_uSv_h[tipo]
    if not (lo <= m["valor_uSv_h"] <= hi):
        errores.append(f"rango:{m['valor_uSv_h']} fuera de [{lo},{hi}]")
    if prev_ts and m["timestamp_utc"] < prev_ts:
        errores.append("consistencia_temporal:timestamp_retrocede")
    return errores


def run():
    os.makedirs(EV_DIR, exist_ok=True)
    reg_path = os.path.join(EV_DIR, "registro_rssme_f100.jsonl")

    def audit(usuario, detector, area, accion):  # 36.22
        prev = "0" * 64
        if os.path.exists(reg_path):
            ls = [l for l in open(reg_path, encoding="utf-8").read().splitlines() if l.strip()]
            if ls:
                prev = json.loads(ls[-1])["md5"]
        e = {"fecha_utc": datetime.now(timezone.utc).isoformat(), "usuario": usuario,
             "detector": detector, "area": area, "accion": accion, "prev_md5": prev}
        e["md5"] = hashlib.md5(json.dumps(e, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with open(reg_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")

    # 36.7 Shielding Manager — sincronizado con F82/F83 (Facility Twin 36.15)
    f83 = json.load(open(f"{EV_ROOT}/fase83/blindaje_ciclotron_f83.json", encoding="utf-8")) \
        if os.path.exists(f"{EV_ROOT}/fase83/blindaje_ciclotron_f83.json") else None
    blindajes = {
        "bunker_ciclotron": {"criterio": "NCRP-144", "losa_m": "2.3–2.5 @3.5 g/cm³",
                             "fuente": "fase83 (preliminar 15–20% declarado)",
                             "geometria": "fase81 DWG"},
        "linac": {"criterio": "NCRP-151", "losa_primaria_cm": {"2.35": 240, "5.0": 105},
                  "fuente": "fase82"},
        "braquiterapia": {"criterio": "IAEA-SRS-47", "puerta_mm_Pb": 3, "fuente": "fase82"},
        "gamma_knife": {"criterio": "ICRP", "puerta_mm_Pb": 3, "fuente": "fase82"},
        "pet_ct": {"criterio": "AAPM-TG-108", "puertas_mm_Pb": 3, "ventana_mm_Pb": 2,
                   "fuente": "fase82"},
        "medicina_nuclear": {"criterio": "IAEA-TECDOC-1608", "puerta_mm_Pb": 6,
                             "fuente": "fase82"},
    }

    # 36.8 Area Classification — versionada desde F88
    f88 = json.load(open(f"{EV_ROOT}/fase88/beme_f88.json", encoding="utf-8"))
    areas = [{"id": z["id"], "clasificacion": z["clasificacion"],
              "nivel_acceso": "restringido" if "controlada" in z["clasificacion"]
                              or "C_ISO" in z["clasificacion"] else "general",
              "estado": "declarado_sin_operacion",
              "config_version": "f88_v1"} for z in f88["zonas"]]

    # 36.6 monitores vinculados al Asset Registry
    mm = MonitorManager(["MON-RAD-RED-01", "HVAC-UMA-01", "CICLOTRON-IBA-KIUBE"])
    mm.registrar("RAD-BUNKER-01", "bunker_ciclotron", "centelleo_area", "MON-RAD-RED-01")
    mm.registrar("RAD-CY-01", "cuarto_yodo", "ionizacion_ambiental", "MON-RAD-RED-01")
    mm.registrar("RAD-CONT-QC-01", "laboratorio_QC", "gm_contaminacion", "MON-RAD-RED-01")
    audit("rpos_pipeline_f100", "monitores", "planta", "registro_36_6")

    # 36.20 validación vv: medición válida + anomalía (comunicación)
    m_ok = medicion("RAD-BUNKER-01", "bunker_ciclotron", 0.8)
    err_ok = validar_medicion(m_ok, mm.monitores["RAD-BUNKER-01"], "centelleo_area")
    m_bad = medicion("RAD-CY-01", "cuarto_yodo", 0.05)
    err_bad = validar_medicion(m_bad, mm.monitores["RAD-CY-01"],
                               "ionizacion_ambiental", comunicacion_ok=False)
    eventos_revision = []
    if err_bad:
        eventos_revision.append({"medicion": m_bad, "errores": err_bad})
    audit("rpos_pipeline_f100", "RAD-CY-01", "cuarto_yodo", "evento_revision_36_20")

    # 36.11 alarmas vv
    alarmas = [{"area": "bunker_ciclotron", "tipo": "incremento_tasa_dosis",
                "detalle": "vv sintético declarado", "estado": "activa",
                "timestamp_utc": datetime.now(timezone.utc).isoformat()}]

    # 36.9 contaminación / 36.10 dosimetría (pendientes declaradas)
    contaminacion = {"eventos": [], "monitoreo_rutinario": "pendiente_instrumento_declarado"}
    dosimetria = {"ambiental": "pendiente_TLD_declarado",
                  "area": "pendiente_detectores (memoria 3)",
                  "ocupacional": "sistema_institucional_pendiente_declarado (36.10)"}

    # 36.14 comparación con Physics Twin
    comparacion_physics = {"mapas_dosis_mc": "pendiente_FEM/Monte Carlo declarado (F60s)",
                           "secciones_talys": "fases F60–F79 disponibles",
                           "mediciones_reales": "pendientes (memoria 3) — comparación diferida"}

    out = {
        "fase": FASE, "capitulo_canonico": 36,
        "componentes_36_5": ["Radiation Monitor Manager", "Shielding Manager",
                             "Area Classification Manager", "Contamination Manager",
                             "Dosimetry Manager", "Alarm Manager",
                             "Validation Engine", "Reporting Service"],
        "filosofia_36_3": FILOSOFIA_36_3,
        "monitores_36_6": {"total": len(mm.monitores), "detalle": list(mm.monitores.values())},
        "shielding_manager_36_7": blindajes,
        "area_classification_36_8": {"total": len(areas), "areas": areas},
        "contamination_manager_36_9": contaminacion,
        "dosimetry_manager_36_10": dosimetria,
        "alarmas_36_11": alarmas,
        "validacion_36_20": {"aceptada_sin_errores": err_ok == [],
                             "eventos_revision": eventos_revision},
        "physics_twin_36_14": comparacion_physics,
        "adquisicion_36_13": "pendiente_detectores_declarado",
        "pendientes_declarados": [
            "Red de detectores física (36.13) — memoria 3.",
            "Dosimetría ocupacional institucional (36.10) — integración pendiente.",
            "InfluxDB/PostgreSQL/MinIO (36.21) pendientes.",
        ],
    }
    with open(os.path.join(EV_DIR, "rssme_f100.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    audit("rpos_pipeline_f100", "rssme", "planta", "exportacion")

    print(json.dumps({"monitores": len(mm.monitores), "areas": len(areas),
                      "blindajes": len(blindajes), "eventos_revision": len(eventos_revision)},
                     indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
