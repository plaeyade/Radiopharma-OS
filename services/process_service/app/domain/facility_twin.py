"""Facility Twin Core (EDS cap. 33) + Asset Lifecycle Management (cap. 34).

Facility Twin (33):

- **Asset Registry (33.6)**: registro central con identificador único;
  nunca sobrescribe.
- **Building Model Manager (33.7)**: estructura física — niveles, áreas,
  salas, zonas restringidas — con organización espacial VERSIONADA.
- **Gestión de áreas (33.8)** y **de zonas (33.12)**: función,
  clasificación, superficie, estado; vinculadas a los procesos que
  albergan.
- **Utility Manager (33.10)**: servicios críticos con estado operacional
  propio.
- **Environmental Manager (33.11)**: registra mediciones ambientales
  PROVENIENTES del monitoreo en tiempo real — nunca las simula.

Asset Lifecycle (34):

- **Ciclo de vida (34.7)**: adquisición → instalación → puesta en
  servicio → operación → mantenimiento → actualización → retiro; cada
  transición registrada.
- **Maintenance Manager (34.8)** con planes versionados (34.9).
- **Calibration Manager (34.10)**: el historial NUNCA se elimina.
- **Certification Manager (34.11)**.
- **Reliability Analyzer (34.12)**: disponibilidad, frecuencia de fallas,
  MTBF, tiempo fuera de servicio y utilización calculados sobre los
  registros reales del activo.
- **Spare Parts Manager (34.13)**: stock con inventario mínimo.

Auditoría 33.24/34.24 en todas las operaciones.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

FACILITY_MODEL_VERSION = "facility-model-1.0.0"

CICLO_VIDA = ("adquisicion", "instalacion", "puesta_en_servicio",
              "operacion", "mantenimiento", "actualizacion", "retiro")

TIPOS_MANTENIMIENTO = ("preventivo", "correctivo", "predictivo",
                       "inspeccion")

UTILIDADES_CRITICAS = ("energia_electrica", "agua_purificada",
                       "aire_comprimido", "vacio", "gases_especiales",
                       "agua_helada", "vapor")

ZONAS_FACILITY = ("area_limpia", "area_controlada", "zona_caliente",
                  "zona_tecnica", "area_administrativa")


class FacilityInvalido(ValueError):
    """Activo, transición, plan o medición inválida (33.22/34.22)."""


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Activo:
    """Asset Registry (33.6/34.6)."""
    activo_id: str
    tipo: str                       # equipo/edificio/laboratorio/
                                    # mobiliario/infraestructura
    nombre: str
    area_id: str = ""
    estado_ciclo: str = "adquisicion"


@dataclass
class Area:
    """Gestión de áreas (33.8)."""
    area_id: str
    funcion: str
    clasificacion: str              # ZONAS_FACILITY 33.12
    superficie_m2: float
    nivel: str = ""
    procesos: list[str] = field(default_factory=list)
    estado: str = "operativa"
    zona_restringida: bool = False


@dataclass
class Utilidad:
    """Utility Manager (33.10)."""
    utilidad_id: str
    tipo: str
    estado: str = "operativa"       # operativa/degradada/fuera_de_servicio


@dataclass
class MedicionAmbiental:
    """Environmental Manager (33.11): dato del monitoreo en tiempo real."""
    area_id: str
    variable: str                   # temperatura/humedad/
                                    # presion_diferencial/calidad_aire
    valor: float
    unidad: str
    fuente: str                     # sensor/serie del monitoring real
    fecha: str = ""


@dataclass
class Mantenimiento:
    """Maintenance Manager (34.8)."""
    intervencion_id: str
    activo_id: str
    tipo: str                       # TIPOS_MANTENIMIENTO
    descripcion: str
    inicio: str
    fin: str | None = None          # None = en curso
    es_falla: bool = False


@dataclass
class Calibracion:
    """Calibration Manager (34.10): historial nunca eliminado."""
    calibracion_id: str
    activo_id: str
    fecha: str
    laboratorio: str
    procedimiento: str
    resultado: str                  # conforme/no_conforme
    vigencia_hasta: str


@dataclass
class Certificacion:
    """Certification Manager (34.11)."""
    documento_id: str
    activo_id: str
    tipo: str                       # certificacion/calificacion/validacion/
                                    # inspeccion_regulatoria
    referencia: str
    fecha: str
    vigencia_hasta: str | None = None


@dataclass
class Repuesto:
    """Spare Parts Manager (34.13)."""
    repuesto_id: str
    descripcion: str
    stock: int
    stock_minimo: int
    compatibles: list[str] = field(default_factory=list)


class FacilityTwin:
    """Modelo digital vivo de la planta (33.4) con ciclo de vida (34.4)."""

    def __init__(self) -> None:
        self._activos: dict[str, Activo] = {}
        self._areas: dict[str, Area] = {}
        self._utilidades: dict[str, Utilidad] = {}
        self._mediciones: list[MedicionAmbiental] = []
        self._mantenimientos: list[Mantenimiento] = []
        self._calibraciones: list[Calibracion] = []
        self._certificaciones: list[Certificacion] = []
        self._repuestos: dict[str, Repuesto] = {}
        self._planes: dict[str, dict] = {}
        self._transiciones: list[dict] = []
        self._auditoria: list[dict] = []

    # ------------------------------------------------------------ núcleo
    def _auditar(self, usuario: str, accion: str, detalle: str) -> None:
        self._auditoria.append({"usuario": usuario, "accion": accion,
                                "detalle": detalle, "fecha": _ahora()})

    def auditoria(self) -> list[dict]:
        return list(self._auditoria)

    # ---------------------------------------------------- registry 33.6
    def registrar_activo(self, activo: Activo, usuario: str) -> dict:
        if activo.activo_id in self._activos:
            raise FacilityInvalido(           # nunca sobrescribe
                f"activo ya registrado: {activo.activo_id}")
        if not activo.tipo or not activo.nombre:
            raise FacilityInvalido("tipo y nombre obligatorios (33.6)")
        if activo.area_id and activo.area_id not in self._areas:
            raise FacilityInvalido(f"área inexistente: {activo.area_id}")
        self._activos[activo.activo_id] = activo
        self._auditar(usuario, "registrar_activo", activo.activo_id)
        return {"activo_id": activo.activo_id,
                "estado_ciclo": activo.estado_ciclo,
                "version_modelo": FACILITY_MODEL_VERSION}

    def activos(self) -> list[dict]:
        return [{"activo_id": a.activo_id, "tipo": a.tipo,
                 "nombre": a.nombre, "area_id": a.area_id,
                 "estado_ciclo": a.estado_ciclo}
                for a in self._activos.values()]

    # ------------------------------------------------------ áreas 33.8
    def registrar_area(self, area: Area, usuario: str) -> dict:
        if area.area_id in self._areas:
            raise FacilityInvalido(f"área ya registrada: {area.area_id}")
        if area.clasificacion not in ZONAS_FACILITY:
            raise FacilityInvalido(
                f"clasificación no reconocida (33.12): {area.clasificacion}")
        if area.superficie_m2 <= 0:
            raise FacilityInvalido("superficie debe ser > 0")
        self._areas[area.area_id] = area
        self._auditar(usuario, "registrar_area", area.area_id)
        return {"area_id": area.area_id,
                "version_modelo": FACILITY_MODEL_VERSION}

    def areas(self) -> list[dict]:
        return [{"area_id": a.area_id, "funcion": a.funcion,
                 "clasificacion": a.clasificacion,
                 "superficie_m2": a.superficie_m2, "nivel": a.nivel,
                 "procesos": list(a.procesos), "estado": a.estado,
                 "zona_restringida": a.zona_restringida}
                for a in self._areas.values()]

    # -------------------------------------------------- utilidades 33.10
    def registrar_utilidad(self, utilidad: Utilidad, usuario: str) -> dict:
        if utilidad.utilidad_id in self._utilidades:
            raise FacilityInvalido(
                f"utilidad ya registrada: {utilidad.utilidad_id}")
        if utilidad.tipo not in UTILIDADES_CRITICAS:
            raise FacilityInvalido(
                f"utilidad no reconocida (33.10): {utilidad.tipo}")
        self._utilidades[utilidad.utilidad_id] = utilidad
        self._auditar(usuario, "registrar_utilidad", utilidad.utilidad_id)
        return {"utilidad_id": utilidad.utilidad_id}

    def cambiar_estado_utilidad(self, utilidad_id: str, estado: str,
                                usuario: str) -> dict:
        if utilidad_id not in self._utilidades:
            raise FacilityInvalido(f"utilidad inexistente: {utilidad_id}")
        if estado not in ("operativa", "degradada", "fuera_de_servicio"):
            raise FacilityInvalido(f"estado inválido: {estado}")
        self._utilidades[utilidad_id].estado = estado
        self._auditar(usuario, "estado_utilidad",
                      f"{utilidad_id} -> {estado}")
        return {"utilidad_id": utilidad_id, "estado": estado}

    def utilidades(self) -> list[dict]:
        return [{"utilidad_id": u.utilidad_id, "tipo": u.tipo,
                 "estado": u.estado} for u in self._utilidades.values()]

    # -------------------------------------------------- ambiente 33.11
    def registrar_medicion_ambiental(self, m: MedicionAmbiental,
                                     usuario: str) -> dict:
        if m.area_id not in self._areas:
            raise FacilityInvalido(f"área inexistente: {m.area_id}")
        if m.variable not in ("temperatura", "humedad",
                              "presion_diferencial", "calidad_aire"):
            raise FacilityInvalido(f"variable no reconocida: {m.variable}")
        if not m.fuente:
            raise FacilityInvalido(
                "toda medición exige fuente del monitoreo en tiempo real "
                "(33.11); el Facility Twin nunca simula mediciones")
        m.fecha = m.fecha or _ahora()
        self._mediciones.append(m)
        self._auditar(usuario, "medicion_ambiental",
                      f"{m.area_id}/{m.variable}={m.valor}{m.unidad}")
        return {"area_id": m.area_id, "variable": m.variable,
                "valor": m.valor, "fecha": m.fecha}

    def mediciones(self, area_id: str | None = None) -> list[dict]:
        return [{"area_id": m.area_id, "variable": m.variable,
                 "valor": m.valor, "unidad": m.unidad, "fuente": m.fuente,
                 "fecha": m.fecha}
                for m in self._mediciones
                if area_id is None or m.area_id == area_id]

    # ------------------------------------------------- ciclo de vida 34.7
    def transicionar_ciclo(self, activo_id: str, nuevo_estado: str,
                           usuario: str) -> dict:
        if activo_id not in self._activos:
            raise FacilityInvalido(f"activo inexistente: {activo_id}")
        if nuevo_estado not in CICLO_VIDA:
            raise FacilityInvalido(f"estado de ciclo inválido: {nuevo_estado}")
        a = self._activos[activo_id]
        if nuevo_estado == a.estado_ciclo:
            raise FacilityInvalido("el activo ya está en ese estado")
        anterior = a.estado_ciclo
        a.estado_ciclo = nuevo_estado
        self._transiciones.append({"activo_id": activo_id,
                                   "de": anterior, "a": nuevo_estado,
                                   "fecha": _ahora(), "usuario": usuario})
        self._auditar(usuario, "transicion_ciclo",
                      f"{activo_id}: {anterior} -> {nuevo_estado}")
        return {"activo_id": activo_id, "de": anterior, "a": nuevo_estado}

    def historial_ciclo(self, activo_id: str) -> list[dict]:
        return [t for t in self._transiciones if t["activo_id"] == activo_id]

    # ----------------------------------------------- mantenimiento 34.8
    def registrar_plan(self, plan_id: str, plan: dict, usuario: str) -> dict:
        """Plan de mantenimiento versionado (34.9); nunca sobrescribe."""
        if plan_id in self._planes:
            raise FacilityInvalido(f"plan ya registrado: {plan_id}")
        for campo in ("activo_id", "periodicidad", "responsable",
                      "procedimiento", "criterios_aceptacion", "version"):
            if campo not in plan:
                raise FacilityInvalido(f"plan sin '{campo}' (34.9)")
        if plan["activo_id"] not in self._activos:
            raise FacilityInvalido(f"activo inexistente: {plan['activo_id']}")
        self._planes[plan_id] = dict(plan, plan_id=plan_id)
        self._auditar(usuario, "registrar_plan", plan_id)
        return {"plan_id": plan_id, "version": plan["version"]}

    def registrar_mantenimiento(self, m: Mantenimiento,
                                usuario: str) -> dict:
        if m.activo_id not in self._activos:
            raise FacilityInvalido(f"activo inexistente: {m.activo_id}")
        if m.tipo not in TIPOS_MANTENIMIENTO:
            raise FacilityInvalido(f"tipo inválido (34.8): {m.tipo}")
        if any(x.intervencion_id == m.intervencion_id
               for x in self._mantenimientos):
            raise FacilityInvalido(
                f"intervención ya registrada: {m.intervencion_id}")
        self._mantenimientos.append(m)
        self._auditar(usuario, "mantenimiento",
                      f"{m.intervencion_id} ({m.tipo}) en {m.activo_id}")
        return {"intervencion_id": m.intervencion_id, "tipo": m.tipo}

    def cerrar_mantenimiento(self, intervencion_id: str, fin: str,
                             usuario: str) -> dict:
        for m in self._mantenimientos:
            if m.intervencion_id == intervencion_id:
                if m.fin is not None:
                    raise FacilityInvalido("intervención ya cerrada")
                m.fin = fin
                self._auditar(usuario, "cierre_mantenimiento",
                              intervencion_id)
                return {"intervencion_id": intervencion_id, "fin": fin}
        raise FacilityInvalido(f"intervención inexistente: {intervencion_id}")

    # ------------------------------------------------ calibraciones 34.10
    def registrar_calibracion(self, c: Calibracion, usuario: str) -> dict:
        if c.activo_id not in self._activos:
            raise FacilityInvalido(f"activo inexistente: {c.activo_id}")
        if c.resultado not in ("conforme", "no_conforme"):
            raise FacilityInvalido("resultado debe ser conforme/no_conforme")
        if any(x.calibracion_id == c.calibracion_id
               for x in self._calibraciones):
            raise FacilityInvalido(
                f"calibración ya registrada: {c.calibracion_id}")
        self._calibraciones.append(c)   # el historial nunca se elimina
        self._auditar(usuario, "calibracion",
                      f"{c.calibracion_id} en {c.activo_id}: {c.resultado}")
        return {"calibracion_id": c.calibracion_id, "resultado": c.resultado}

    def calibraciones(self, activo_id: str) -> list[dict]:
        return [{"calibracion_id": c.calibracion_id, "fecha": c.fecha,
                 "laboratorio": c.laboratorio, "procedimiento": c.procedimiento,
                 "resultado": c.resultado, "vigencia_hasta": c.vigencia_hasta}
                for c in self._calibraciones if c.activo_id == activo_id]

    def calibracion_vigente(self, activo_id: str, fecha_iso: str) -> dict:
        vigentes = [c for c in self._calibraciones
                    if c.activo_id == activo_id
                    and c.resultado == "conforme"
                    and c.vigencia_hasta >= fecha_iso]
        return {"activo_id": activo_id, "fecha_consulta": fecha_iso,
                "vigente": bool(vigentes),
                "calibracion_id": vigentes[-1].calibracion_id
                if vigentes else None}

    # --------------------------------------------- certificaciones 34.11
    def registrar_certificacion(self, c: Certificacion,
                                usuario: str) -> dict:
        if c.activo_id not in self._activos:
            raise FacilityInvalido(f"activo inexistente: {c.activo_id}")
        if any(x.documento_id == c.documento_id
               for x in self._certificaciones):
            raise FacilityInvalido(f"documento ya registrado: {c.documento_id}")
        self._certificaciones.append(c)
        self._auditar(usuario, "certificacion",
                      f"{c.documento_id} ({c.tipo}) de {c.activo_id}")
        return {"documento_id": c.documento_id}

    def certificaciones(self, activo_id: str) -> list[dict]:
        return [{"documento_id": c.documento_id, "tipo": c.tipo,
                 "referencia": c.referencia, "fecha": c.fecha,
                 "vigencia_hasta": c.vigencia_hasta}
                for c in self._certificaciones if c.activo_id == activo_id]

    # ------------------------------------------------ confiabilidad 34.12
    def confiabilidad(self, activo_id: str, horas_periodo: float) -> dict:
        """Indicadores sobre los registros reales del activo (34.12)."""
        if activo_id not in self._activos:
            raise FacilityInvalido(f"activo inexistente: {activo_id}")
        if horas_periodo <= 0:
            raise FacilityInvalido("horas_periodo debe ser > 0")
        mants = [m for m in self._mantenimientos
                 if m.activo_id == activo_id and m.fin is not None]
        tfs = 0.0
        for m in mants:
            t0 = datetime.fromisoformat(m.inicio)
            t1 = datetime.fromisoformat(m.fin)
            tfs += max(0.0, (t1 - t0).total_seconds() / 3600.0)
        tfs = min(tfs, horas_periodo)
        fallas = [m for m in mants if m.es_falla]
        n_fallas = len(fallas)
        disponibilidad = (horas_periodo - tfs) / horas_periodo
        return {"activo_id": activo_id, "horas_periodo": horas_periodo,
                "tiempo_fuera_de_servicio_h": round(tfs, 4),
                "disponibilidad": round(disponibilidad, 6),
                "n_fallas": n_fallas,
                "frecuencia_fallas_por_h": round(
                    n_fallas / horas_periodo, 8),
                "mtbf_h": (round((horas_periodo - tfs) / n_fallas, 4)
                           if n_fallas else None),
                "nota": "indicadores calculados sobre intervenciones "
                        "cerradas reales (34.12); las intervenciones en "
                        "curso no computan"}

    # ---------------------------------------------------- repuestos 34.13
    def registrar_repuesto(self, r: Repuesto, usuario: str) -> dict:
        if r.repuesto_id in self._repuestos:
            raise FacilityInvalido(f"repuesto ya registrado: {r.repuesto_id}")
        if r.stock < 0 or r.stock_minimo < 0:
            raise FacilityInvalido("stock no puede ser negativo")
        self._repuestos[r.repuesto_id] = r
        self._auditar(usuario, "registrar_repuesto", r.repuesto_id)
        return {"repuesto_id": r.repuesto_id}

    def consumir_repuesto(self, repuesto_id: str, cantidad: int,
                          usuario: str) -> dict:
        if repuesto_id not in self._repuestos:
            raise FacilityInvalido(f"repuesto inexistente: {repuesto_id}")
        r = self._repuestos[repuesto_id]
        if cantidad <= 0 or cantidad > r.stock:
            raise FacilityInvalido("cantidad inválida o stock insuficiente")
        r.stock -= cantidad
        self._auditar(usuario, "consumir_repuesto",
                      f"{repuesto_id} -{cantidad} -> {r.stock}")
        return {"repuesto_id": repuesto_id, "stock": r.stock,
                "bajo_minimo": r.stock < r.stock_minimo}

    def repuestos(self) -> list[dict]:
        return [{"repuesto_id": r.repuesto_id, "descripcion": r.descripcion,
                 "stock": r.stock, "stock_minimo": r.stock_minimo,
                 "bajo_minimo": r.stock < r.stock_minimo,
                 "compatibles": list(r.compatibles)}
                for r in self._repuestos.values()]
