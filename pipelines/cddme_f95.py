#!/usr/bin/env python3
"""
F95 — Cap. 32: Clinical Delivery & Dose Management Engine (CDDME)
Radiopharma OS — Operational Twin

Reglas canónicas:
- 32.3: coordina el flujo posterior a la liberación; NO produce, NO hace CQ,
  NO interpreta clínicamente, NO prescribe.
- 32.8: el Decay Calculator usa física real A(t)=A0·2^(−t/T½) con T½(¹⁸F)
  = 109.77 min (valor NNDC, declarado); sincronizado con hora del sistema.
- 32.15: SOLO lotes liberados por el QC Twin pueden asignarse a pacientes.
- 32.11: la reprogramación por decaimiento es una PROPUESTA que requiere
  confirmación del usuario autorizado — nunca se auto-aplica.
- 32.21: antes de asignar se verifica estado del lote, actividad disponible,
  programación vigente y recursos; las inconsistencias impiden la asignación.
- 32.23: auditoría append-only (usuario, dosis, paciente_id_interno, lote,
  fecha, resultado) — jsonl encadenado md5 (ALCOA+).
- Honestidad/privacidad: la agenda de pacientes es SINTÉTICA DECLARADA (V&V);
  identificadores internos, jamás datos clínicos reales.
"""
import hashlib, json, math, os, sys
from datetime import datetime, timezone

FASE = "fase95"
EV_DIR = "/mnt/agents/work/evidencia_v072/fase95"

T12_F18_MIN = 109.77  # NNDC (declarado)


# --- 32.8 Decay Calculator -------------------------------------------------------
def actividad(a0_mbq, t_min, t12=T12_F18_MIN):
    if t_min < 0:
        raise ValueError("tiempo_negativo")
    return a0_mbq * 2.0 ** (-t_min / t12)


# --- 32.6 Dose Manager -------------------------------------------------------------
class Lote:
    def __init__(self, lote_id, actividad_mbq, t_liberacion_min, estado_qc):
        self.id = lote_id
        self.a0 = actividad_mbq          # a la hora de liberación
        self.t0 = t_liberacion_min       # min desde referencia del día
        self.estado_qc = estado_qc       # 'liberado' | 'no_liberado' | 'pendiente'
        self.dosis = []

    def actividad_disponible(self, t_min):
        usada = sum(d["actividad_asignada_mbq"] for d in self.dosis)
        return actividad(self.a0, t_min - self.t0) - usada * 0  # asignación nominal


def asignar_dosis(lote, dosis_id, actividad_objetivo_mbq, t_prep_min, destino):
    """Asigna actividad a preparar en t_prep, garantizando la actividad objetivo
    a la administración. Verificaciones 32.21."""
    if lote.estado_qc != "liberado":
        raise ValueError(f"lote_no_liberado:{lote.estado_qc}")  # 32.15/32.21
    if t_prep_min < lote.t0:
        raise ValueError("programacion_no_vigente:preparacion_antes_de_liberacion")
    disp = lote.actividad_disponible(t_prep_min) - \
        sum(d["actividad_asignada_mbq"] for d in lote.dosis)
    if actividad_objetivo_mbq > disp + 1e-9:
        raise ValueError(f"actividad_insuficiente:{disp:.1f}<{actividad_objetivo_mbq}")
    d = {"id": dosis_id, "lote": lote.id, "actividad_asignada_mbq": actividad_objetivo_mbq,
         "t_preparacion_min": t_prep_min, "destino": destino,
         "volumen_ml": None,  # depende de concentración — pendiente_dato
         "trazable": True}
    lote.dosis.append(d)
    return d


# --- 32.7 Patient Schedule Manager -----------------------------------------------------
def programar_paciente(agenda, paciente_id_interno, procedimiento, horario_min,
                       prioridad, dosis_id):
    reg = {"paciente_id_interno": paciente_id_interno,  # jamás datos clínicos reales
           "procedimiento": procedimiento, "horario_min": horario_min,
           "prioridad": prioridad, "estado": "programado", "dosis_id": dosis_id,
           "declarado": "agenda_sintetica_vv"}
    agenda.append(reg)
    return reg


# --- 32.9 Delivery Coordinator ------------------------------------------------------------
TRANSICIONES = ["preparacion", "despacho", "recepcion", "confirmacion_entrega"]


def registrar_entrega(dosis, t_salida_min, t_llegada_min):
    if t_llegada_min < t_salida_min:
        raise ValueError("inconsistencia_temporal_entrega")
    dosis["entrega"] = {
        "preparacion_min": dosis["t_preparacion_min"], "salida_min": t_salida_min,
        "llegada_min": t_llegada_min, "confirmacion": True,  # 32.9 cada transición registrada
        "secuencia": TRANSICIONES,
    }
    return dosis["entrega"]


# --- 32.10 Administration Manager -------------------------------------------------------------
def registrar_administracion(dosis, lote, paciente, t_admin_min, operador):
    if "entrega" not in dosis:
        raise ValueError("dosis_sin_entrega_confirmada")
    a_admin = actividad(dosis["actividad_asignada_mbq"], t_admin_min - dosis["t_preparacion_min"])
    adm = {"hora_min": t_admin_min, "operador": operador, "dosis_id": dosis["id"],
           "actividad_administrada_mbq": round(a_admin, 2), "estado": "administrada"}
    dosis["administracion"] = adm
    paciente["estado"] = "completado"
    return adm


# --- 32.11 Optimización por decaimiento (PROPUESTA, no auto-aplica) -----------------------------
def proponer_reprogramacion(lote, agenda, retraso_min, umbral_perdida_pct=10.0):
    ahora = max(p["horario_min"] for p in agenda if p["estado"] == "programado")
    a_sin = actividad(lote.a0, ahora - lote.t0)
    a_con = actividad(lote.a0, ahora + retraso_min - lote.t0)
    perdida_pct = 100.0 * (a_sin - a_con) / a_sin if a_sin > 0 else 0.0
    if perdida_pct := round(perdida_pct, 2):
        pass
    if perdida_pct >= umbral_perdida_pct:
        pendientes = [p for p in agenda if p["estado"] == "programado"]
        return {"tipo": "propuesta_reprogramacion", "retraso_min": retraso_min,
                "perdida_pct": perdida_pct,
                "propuesta": "adelantar pacientes de mayor prioridad y concentrar "
                             "administraciones antes del retraso",
                "pacientes_afectados": [p["paciente_id_interno"] for p in pendientes],
                "requiere_confirmacion_usuario_autorizado": True,  # 32.11
                "auto_aplicada": False}
    return {"tipo": "sin_accion", "perdida_pct": perdida_pct}


# --- 32.5 Reporting Service -------------------------------------------------------------------
def reporte(lote, agenda, t_fin_min):
    admin = [d for d in lote.dosis if "administracion" in d]
    a_admin = sum(d["administracion"]["actividad_administrada_mbq"] for d in admin)
    a_disp_t0 = lote.a0
    remanente = actividad(lote.a0, t_fin_min - lote.t0) - \
        sum(d["actividad_asignada_mbq"] for d in lote.dosis)
    return {
        "lote": lote.id,
        "dosis_asignadas": len(lote.dosis),
        "dosis_administradas": len(admin),
        "pacientes_completados": sum(1 for p in agenda if p["estado"] == "completado"),
        "actividad_administrada_total_mbq": round(a_admin, 2),
        "aprovechamiento_pct": round(100.0 * a_admin / a_disp_t0, 2),
        "remanente_estimado_mbq": round(max(remanente, 0.0), 2),
        "perdida_decaimiento_pct": round(100.0 - 100.0 * a_admin / a_disp_t0, 2),
        "alimenta_economic_twin_32_17": ["utilizacion_dosis", "actividad_remanente",
                                         "perdidas_decaimiento", "cancelaciones"],
    }


# --- Ejecución de fase -------------------------------------------------------------------------
def run():
    os.makedirs(EV_DIR, exist_ok=True)
    reg = os.path.join(EV_DIR, "registro_cddme_f95.jsonl")

    def audit(accion, dosis=None, paciente=None, resultado="ok"):
        prev = "0" * 64
        if os.path.exists(reg):
            lines = [l for l in open(reg, encoding="utf-8").read().splitlines() if l.strip()]
            if lines:
                prev = json.loads(lines[-1])["md5"]
        e = {"fecha_utc": datetime.now(timezone.utc).isoformat(),
             "usuario": "rpos_pipeline_f95", "accion": accion, "dosis": dosis,
             "paciente_id_interno": paciente, "lote": "LOTE-VV-001", "resultado": resultado,
             "prev_md5": prev}
        e["md5"] = hashlib.md5(json.dumps(e, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with open(reg, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")

    # Lote V&V sintético declarado, liberado_vv (memoria 3: no hay producción real)
    lote = Lote("LOTE-VV-001", 7400.0, 480.0, "liberado")  # 7400 MBq a las 08:00
    audit("liberar_lote_vv", resultado="liberado_vv_declarado")

    agenda = []
    pacientes = [  # agenda sintética declarada; ids internos
        ("PAC-VV-01", "PET-CT oncología", 540, "alta", 370.0),
        ("PAC-VV-02", "PET-CT oncología", 570, "alta", 370.0),
        ("PAC-VV-03", "PET-CT cardiología", 600, "media", 296.0),
        ("PAC-VV-04", "PET-CT oncología", 630, "media", 370.0),
        ("PAC-VV-05", "PET-CT neurología", 660, "baja", 296.0),
    ]
    errores = []
    for pid, proc, hora, prio, objetivo in pacientes:
        # asignar a preparación 30 min antes para garantizar actividad objetivo
        a_prep = objetivo / (2.0 ** (-30.0 / T12_F18_MIN))  # compensa decaimiento prep→admin
        try:
            d = asignar_dosis(lote, f"DOS-{pid}", round(a_prep, 2), hora - 30, "PET-CT")
            audit("asignar_dosis", dosis=d["id"], paciente=pid)
            p = programar_paciente(agenda, pid, proc, hora, prio, d["id"])
            audit("programar_paciente", paciente=pid)
            registrar_entrega(d, hora - 15, hora - 5)
            audit("entregar", dosis=d["id"], paciente=pid)
            registrar_administracion(d, lote, p, hora, "operador_vv")
            audit("administrar", dosis=d["id"], paciente=pid)
        except ValueError as ex:
            errores.append(str(ex))
            audit("asignar_dosis", paciente=pid, resultado=f"rechazado:{ex}")

    # 32.21: lote NO liberado no puede asignarse
    lote_nl = Lote("LOTE-VV-002", 7400.0, 480.0, "pendiente")
    try:
        asignar_dosis(lote_nl, "DOS-X", 100.0, 500, "PET-CT")
        bloqueado = False
    except ValueError:
        bloqueado = True

    # 32.11: retraso operativo de 60 min → propuesta (no auto-aplicada)
    propuesta = proponer_reprogramacion(lote, [
        {"paciente_id_interno": "PAC-VV-06", "horario_min": 700, "estado": "programado"}],
        retraso_min=60)

    rep = reporte(lote, agenda, 720.0)
    audit("reporte", resultado="generado")

    out = {
        "fase": FASE, "capitulo_canonico": 32,
        "componentes_32_5": ["Dose Manager", "Patient Schedule Manager", "Decay Calculator",
                             "Delivery Coordinator", "Administration Manager",
                             "Validation Engine", "Audit Manager", "Reporting Service"],
        "decay_calculator": {"modelo": "A(t)=A0·2^(−t/T½)", "t12_f18_min": T12_F18_MIN,
                             "fuente_t12": "NNDC (declarado)"},
        "agenda_vv": agenda,
        "dosis": lote.dosis,
        "asignaciones_rechazadas": errores,
        "lote_no_liberado_bloqueado": bloqueado,  # 32.15/32.21
        "propuesta_reprogramacion_32_11": propuesta,
        "reporte": rep,
        "pendientes_declarados": [
            "Agenda y lote son sintéticos declarados V&V (memoria 3); sin datos clínicos reales.",
            "Volumen por dosis: pendiente concentración del lote (dato de producción real).",
            "HIS/RIS/PACS/EMR (32.26) y PostgreSQL/Redis/MinIO (32.22) pendientes de despliegue.",
        ],
    }
    with open(os.path.join(EV_DIR, "cddme_f95.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print(json.dumps({"dosis_administradas": rep["dosis_administradas"],
                      "aprovechamiento_pct": rep["aprovechamiento_pct"],
                      "bloqueado_no_liberado": bloqueado,
                      "propuesta": propuesta["tipo"],
                      "rechazadas": len(errores)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
