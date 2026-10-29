#!/usr/bin/env python3
"""
F97 — Cap. 33: Facility Twin Core (infraestructura, activos, utilidades)
Radiopharma OS — modelo digital de la planta.

Reglas canónicas:
- 33.3: representa EXCLUSIVAMENTE infraestructura; no ejecuta producción,
  simulación física, CQ ni programación clínica.
- 33.22: antes de incorporar un activo se verifica identificación,
  clasificación, ubicación y consistencia documental; los registros
  incompletos NO se incorporan.
- 33.24: auditoría append-only (usuario, activo, fecha, acción, motivo) —
  jsonl encadenado md5 (ALCOA+).
- 33.7/33.21: organización espacial y cambios versionados.
- Sincronización con evidencia real: F81 (niveles/salas DWG), F88 (zonas,
  ambiental), F89 (equipos), F86 (utilidades). Estados sin telemetría =
  pendiente declarado (memoria 3), jamás simulados.
"""
import hashlib, json, os, sys
from datetime import datetime, timezone

FASE = "fase97"
EV_DIR = "/mnt/agents/work/evidencia_v072/fase97"
EV_ROOT = "/mnt/agents/work/evidencia_v072"

REGLA_33_3 = ("Facility Twin representa exclusivamente infraestructura: "
              "no ejecuta producción, simulaciones físicas, CQ ni programación clínica.")

# ---------- 33.6 Asset Registry -------------------------------------------------
class AssetRegistry:
    """Registro central de activos con identificador único (33.6)."""

    def __init__(self):
        self.activos = {}

    def registrar(self, id_activo, tipo, ubicacion, clasificacion, estado, metadatos=None):
        if id_activo in self.activos:
            raise ValueError(f"duplicado:{id_activo}")
        a = {"id": id_activo, "tipo": tipo, "ubicacion": ubicacion,
             "clasificacion": clasificacion, "estado": estado,
             "metadatos": metadatos or {},
             "fecha_utc": datetime.now(timezone.utc).isoformat(),
             "historial": []}  # 33.21: evolución completa
        self.activos[id_activo] = a
        return a

    def actualizar_estado(self, id_activo, estado, motivo):
        a = self.activos[id_activo]
        a["historial"].append({"estado_anterior": a["estado"], "estado_nuevo": estado,
                               "motivo": motivo,
                               "fecha_utc": datetime.now(timezone.utc).isoformat()})
        a["estado"] = estado

    def md5(self):
        return hashlib.md5(json.dumps(self.activos, sort_keys=True,
                                      ensure_ascii=False).encode()).hexdigest()


# ---------- 33.22 Validation Engine -------------------------------------------------
def validar_activo(activo):
    """Registros incompletos no se incorporan (33.22)."""
    errores = []
    if not activo.get("id"):
        errores.append("identificacion:faltante")
    if not activo.get("clasificacion"):
        errores.append("clasificacion:faltante")
    if not activo.get("ubicacion") or activo["ubicacion"] in ("", "na"):
        errores.append("ubicacion:faltante")
    if not activo.get("tipo"):
        errores.append("tipo:faltante")
    return errores


# ---------- 33.7 Building Model Manager (versionado) ----------------------------------
def construir_modelo_edificio():
    """Estructura física según F81 (DWG BIND 20-10-26, distribución declarada)."""
    return {
        "version": "f81_dwg_bind_201026",
        "fuente": "evidencia_v072/fase81 (PLANTAS ARQ BIND 20-10-26.dwg)",
        "niveles": [
            {"nivel": "planta_baja", "areas": ["bunker_ciclotron", "radiofarmacia",
                "gamma_knife", "acelerador_lineal"],
             "zonas_restringidas": ["bunker_ciclotron", "gamma_knife", "acelerador_lineal"]},
            {"nivel": "nivel_1", "areas": ["pet_ct", "tomografo_simulador",
                "cuarto_caliente_pet", "inyeccion_1_4", "braquiterapia"],
             "zonas_restringidas": ["cuarto_caliente_pet"]},
            {"nivel": "nivel_2", "areas": ["medicina_nuclear", "cuarto_yodo",
                "cuarto_caliente_mn", "consultorios_1_3"],
             "zonas_restringidas": ["cuarto_yodo", "cuarto_caliente_mn"]},
            {"nivel": "nivel_3", "areas": ["biologia_molecular"], "zonas_restringidas": []},
            {"nivel": "nivel_4", "areas": ["proyectado_no_construido"],
             "zonas_restringidas": [], "declarado": "proyectado, no construido (F81)"},
        ]}


# ---------- 33.10 Utility Manager --------------------------------------------------------
def cargar_utilidades():
    """Servicios críticos con estado operacional propio (33.10), desde F86."""
    d = json.load(open(f"{EV_ROOT}/fase86/utilidades_completas_f86.json", encoding="utf-8"))
    servicios = []
    for it in d["items"]:
        servicios.append({"servicio": it["concepto"], "unidad": it["unidad"],
                          "consumo_lote": it["cantidad"], "costo_mxn_lote": it["costo_mxn_lote"],
                          "fuente": it["fuente"],
                          "estado_operacional": "pendiente_telemetria_declarado"})
    return {"servicios": servicios,
            "total_costo_mxn_lote": d["totales"]["costo_utilidades_mxn_lote"],
            "total_kwh_lote": d["totales"]["electricidad_kWh_lote"]}


# ---------- 33.9 Equipment Manager --------------------------------------------------------
def cargar_equipos(reg):
    """Equipos físicos desde F89 (inventario IIL) + declarados documentales."""
    iil = json.load(open(f"{EV_ROOT}/fase89/iil_f89.json", encoding="utf-8"))
    n = 0
    for ins in iil["instrument_registry"]["inventario"]:
        a = {"id": ins["id"], "tipo": ins["tipo"], "ubicacion": ins["ubicacion"],
             "clasificacion": "equipo_laboratorio", "estado": ins["estado_conexion"]}
        errs = validar_activo(a)
        if not errs:
            reg.registrar(a["id"], a["tipo"], a["ubicacion"], a["clasificacion"],
                          a["estado"], {"adaptador": ins["adaptador"], "fuente": "fase89"})
            n += 1
    # Equipos mayores declarados documentalmente (F82/F83)
    for eq, ub, fuente in [("CICLOTRON-IBA-KIUBE", "bunker_ciclotron", "fase83 (declarado, digital twin pendiente)"),
                           ("LINAC-01", "acelerador_lineal", "fase82"),
                           ("GAMMA-KNIFE-01", "gamma_knife", "fase82"),
                           ("PETCT-01", "pet_ct", "fase82")]:
        reg.registrar(eq, "equipo_mayor", ub, "equipo_radiologico",
                      "pendiente_instalacion_declarado", {"fuente": fuente})
        n += 1
    return n


# ---------- 33.11 Environmental Manager ------------------------------------------------------
def cargar_ambiental():
    """Variables ambientales desde F88 (zonas con dP/T/HR); sin sensores reales."""
    d = json.load(open(f"{EV_ROOT}/fase88/beme_f88.json", encoding="utf-8"))
    zonas = []
    for z in d["zonas"]:
        zonas.append({"zona": z["id"], "clasificacion": z["clasificacion"],
                      "dP_Pa": z["dP_Pa"], "T_C": z["T_C"], "HR_pct": z["HR_pct"],
                      "ACH": z["ACH"],
                      "medicion_tiempo_real": "pendiente_sensores_declarado"})
    return {"zonas": zonas, "total": len(zonas),
            "fuente": "fase88 (objetivos declarados; 33.11 mediciones = monitoreo en tiempo real, pendiente)"}


def run():
    os.makedirs(EV_DIR, exist_ok=True)
    reg_path = os.path.join(EV_DIR, "registro_facility_f97.jsonl")

    def audit(usuario, id_activo, accion, motivo):  # 33.24
        prev = "0" * 64
        if os.path.exists(reg_path):
            ls = [l for l in open(reg_path, encoding="utf-8").read().splitlines() if l.strip()]
            if ls:
                prev = json.loads(ls[-1])["md5"]
        e = {"fecha_utc": datetime.now(timezone.utc).isoformat(), "usuario": usuario,
             "activo": id_activo, "accion": accion, "motivo": motivo, "prev_md5": prev}
        e["md5"] = hashlib.md5(json.dumps(e, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with open(reg_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")

    registry = AssetRegistry()
    edificio = construir_modelo_edificio()
    n_eq = cargar_equipos(registry)
    audit("rpos_pipeline_f97", "facility_model", "construccion_inicial", "F97 cap.33")

    # 33.22: activo incompleto → rechazado
    incompleto = {"id": "EQ-SIN-UBIC", "tipo": "generico", "ubicacion": "", "clasificacion": "x"}
    errs_inc = validar_activo(incompleto)
    audit("rpos_pipeline_f97", "EQ-SIN-UBIC", "rechazo_validacion_33_22", ",".join(errs_inc))

    utilidades = cargar_utilidades()
    ambiental = cargar_ambiental()

    # 33.15/33.16/33.19: vistas de consulta para los otros gemelos
    vistas = {
        "operational_twin_33_15": {"disponibilidad_areas": "declarada_f81",
                                   "estado_activos": {a["id"]: a["estado"] for a in registry.activos.values()}},
        "physics_twin_33_16": {"geometria": "fase81 (DWG)", "blindajes": "fase82/fase83"},
        "economic_twin_33_19": {"costo_utilidades_mxn_lote": utilidades["total_costo_mxn_lote"],
                                "depreciacion": "pendiente_dato_institucional"}}

    out = {
        "fase": FASE, "capitulo_canonico": 33,
        "componentes_33_5": ["Asset Registry", "Building Model Manager", "Utility Manager",
                             "Equipment Manager", "Environmental Manager", "Maintenance Interface",
                             "Validation Engine", "Export Service"],
        "filosofia_33_3": REGLA_33_3,
        "building_model": edificio,
        "activos": {"total": len(registry.activos), "equipos_registrados": n_eq,
                    "rechazados_33_22": [{"id": "EQ-SIN-UBIC", "errores": errs_inc}],
                    "md5_registro": registry.md5()},
        "utility_manager": utilidades,
        "environmental_manager": ambiental,
        "maintenance_interface": {"estado": "estructura_lista_sin_ordenes",
                                   "mantenimientos": [],
                                   "declarado": "sin activos físicos instalados (memoria 3)"},
        "integraciones": vistas,
        "pendientes_declarados": [
            "PostgreSQL/MinIO/Data Lake (33.23) — capa de persistencia pendiente.",
            "Integración BIM/IFC (33.13) — geometría DXF F81 versionada como base.",
            "Telemetría ambiental en tiempo real (33.11) — sin sensores (memoria 3).",
        ],
    }
    with open(os.path.join(EV_DIR, "facility_f97.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    audit("rpos_pipeline_f97", "facility_model", "exportacion", "facility_f97.json")

    print(json.dumps({"activos": len(registry.activos),
                      "rechazado": errs_inc, "utilidades_mxn_lote": utilidades["total_costo_mxn_lote"],
                      "zonas_ambientales": ambiental["total"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
