"""Facility Simulation & Capacity Planning Engine (EDS cap. 37).

Simulación prospectiva sobre un modelo VIRTUAL de la instalación:

- **Scenario Manager (37.6)**: escenarios versionados que NUNCA alteran
  el modelo operacional ni los datos reales (37.3).
- **Capacity Analyzer (37.7)**: utilización, capacidad disponible,
  saturación y reservas por recurso y por proceso.
- **Bottleneck Detector (37.8)**: recurso que limita el desempeño
  global, para priorizar inversiones.
- **Resource Optimizer (37.9)**: propuestas de redistribución
  DOCUMENTADAS y marcadas como soporte a la decisión (41.9).
- **Expansion Planner (37.10)** y **What-If Engine (37.11)**:
  comparación de escenarios entre sí, independiente de la operación.
- **Validation Engine (37.21)**: integridad del escenario, parámetros,
  consistencia temporal — las simulaciones incompletas se RECHAZAN.

Modelo analítico determinista (documentado, no discreto): cada recurso
ejecuta ciclos de duración fija; la capacidad diaria de una etapa es
`unidades · horas_disponibles · disponibilidad · 60 / duración_min ·
capacidad_por_ciclo`; el rendimiento del proceso es el mínimo entre
etapas (cada lote atraviesa todas). La disponibilidad del recurso debe
provenir del ALME 34.12 cuando se configure el escenario — el motor no
la inventa: si falta, la simulación se rechaza (37.21).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

FSCPE_VERSION = "fscpe-1.0.0"


class SimulacionInvalida(ValueError):
    """Escenario incompleto o inconsistente: rechazado (37.21)."""


@dataclass
class RecursoEscenario:
    """Recurso del escenario (capacidad 37.7, disponibilidad 37.17)."""
    recurso_id: str
    tipo: str                       # ciclotron/sintesis/laboratorio_qc/...
    unidades: int
    horas_disponibles_dia: float
    disponibilidad: float           # 0-1, del ALME 34.12


@dataclass
class EtapaEscenario:
    """Etapa del proceso ejecutada sobre un recurso (37.14/37.15/37.16)."""
    nombre: str                     # irradiacion/sintesis/purificacion/...
    recurso_id: str
    duracion_min: float
    capacidad_por_ciclo: int = 1    # lotes por ciclo


@dataclass
class Escenario:
    """Escenario de simulación (37.6): aislado de la operación real."""
    escenario_id: str
    descripcion: str
    hipotesis: str
    recursos: list[RecursoEscenario]
    etapas: list[EtapaEscenario]
    demanda_diaria_lotes: float
    version: str
    fecha: str = ""


class CapacitySimulationEngine:
    """FSCPE: escenarios aislados, análisis determinista, propuestas
    documentadas (nunca decisiones operativas)."""

    def __init__(self) -> None:
        self._escenarios: dict[str, Escenario] = {}
        self._resultados: dict[str, list[dict]] = {}   # 37.20 versionado
        self._auditoria: list[dict] = []

    def _auditar(self, usuario: str, accion: str, detalle: str) -> None:
        self._auditoria.append({"usuario": usuario, "accion": accion,
                                "detalle": detalle,
                                "fecha": datetime.now(
                                    timezone.utc).isoformat()})

    def auditoria(self) -> list[dict]:
        return list(self._auditoria)

    # -------------------------------------------------- escenarios 37.6
    def registrar_escenario(self, esc: Escenario, usuario: str) -> dict:
        if esc.escenario_id in self._escenarios:
            raise SimulacionInvalida(          # nunca sobrescribe
                f"escenario ya registrado: {esc.escenario_id}")
        esc.fecha = esc.fecha or datetime.now(timezone.utc).isoformat()
        self._validar_escenario(esc)           # 37.21
        self._escenarios[esc.escenario_id] = esc
        self._auditar(usuario, "registrar_escenario",
                      f"{esc.escenario_id} v{esc.version}")
        return {"escenario_id": esc.escenario_id, "version": esc.version,
                "nota": "escenario aislado: nunca altera el modelo "
                        "operacional ni los datos reales (37.3)"}

    def _validar_escenario(self, esc: Escenario) -> None:
        if not esc.recursos or not esc.etapas:
            raise SimulacionInvalida(
                "escenario incompleto: sin recursos o sin etapas (37.21)")
        if esc.demanda_diaria_lotes < 0:
            raise SimulacionInvalida("demanda negativa (37.21)")
        ids = {r.recurso_id for r in esc.recursos}
        for r in esc.recursos:
            if r.unidades < 1 or r.horas_disponibles_dia <= 0:
                raise SimulacionInvalida(
                    f"recurso {r.recurso_id}: unidades/horas inválidas")
            if not (0.0 < r.disponibilidad <= 1.0):
                raise SimulacionInvalida(
                    f"recurso {r.recurso_id}: disponibilidad fuera de "
                    "(0, 1] — debe provenir del ALME 34.12; el motor no "
                    "la inventa (37.21)")
        for e in esc.etapas:
            if e.recurso_id not in ids:
                raise SimulacionInvalida(
                    f"etapa {e.nombre}: recurso inexistente "
                    f"{e.recurso_id} (37.21)")
            if e.duracion_min <= 0 or e.capacidad_por_ciclo < 1:
                raise SimulacionInvalida(
                    f"etapa {e.nombre}: duración/capacidad inválida")

    def escenarios(self) -> list[dict]:
        return [{"escenario_id": e.escenario_id,
                 "descripcion": e.descripcion, "hipotesis": e.hipotesis,
                 "version": e.version, "fecha": e.fecha,
                 "n_recursos": len(e.recursos), "n_etapas": len(e.etapas),
                 "demanda_diaria_lotes": e.demanda_diaria_lotes}
                for e in self._escenarios.values()]

    # -------------------------------------------------- simulación 37.4
    def ejecutar(self, escenario_id: str, usuario: str) -> dict:
        if escenario_id not in self._escenarios:
            raise SimulacionInvalida(f"escenario inexistente: {escenario_id}")
        esc = self._escenarios[escenario_id]
        por_recurso: dict[str, dict] = {}
        for e in esc.etapas:
            r = next(r for r in esc.recursos
                     if r.recurso_id == e.recurso_id)
            ciclos_dia = (r.unidades * r.horas_disponibles_dia
                          * r.disponibilidad * 60.0 / e.duracion_min)
            capacidad = ciclos_dia * e.capacidad_por_ciclo
            prev = por_recurso.get(e.recurso_id)
            if prev is None or capacidad < prev["capacidad_lotes_dia"]:
                por_recurso[e.recurso_id] = {
                    "recurso_id": e.recurso_id, "tipo": r.tipo,
                    "etapa_limitante": e.nombre,
                    "capacidad_lotes_dia": round(capacidad, 4)}
        rendimiento = min(v["capacidad_lotes_dia"]
                          for v in por_recurso.values())
        cuello = min(por_recurso.values(),
                     key=lambda v: v["capacidad_lotes_dia"])
        recursos = []
        for v in por_recurso.values():
            cap = v["capacidad_lotes_dia"]
            utilizacion = (esc.demanda_diaria_lotes / cap if cap > 0
                           else float("inf"))
            recursos.append({**v,
                             "utilizacion": round(utilizacion, 4),
                             "saturado": utilizacion > 1.0,
                             "reserva_lotes_dia": round(
                                 cap - esc.demanda_diaria_lotes, 4)})
        resultado = {
            "escenario_id": escenario_id, "version": esc.version,
            "rendimiento_lotes_dia": round(rendimiento, 4),
            "demanda_diaria_lotes": esc.demanda_diaria_lotes,
            "cubre_demanda": rendimiento >= esc.demanda_diaria_lotes,
            "cuello_de_botella": cuello,          # 37.8
            "recursos": recursos,                  # 37.7
            "modelo": "analítico determinista (ciclos/día por recurso, "
                      "mínimo entre etapas)",
            "fecha_ejecucion": datetime.now(timezone.utc).isoformat(),
            "version_motor": FSCPE_VERSION}
        self._resultados.setdefault(escenario_id, []).append(resultado)
        self._auditar(usuario, "ejecutar_simulacion",
                      f"{escenario_id} v{esc.version}")
        return resultado

    def resultados(self, escenario_id: str) -> list[dict]:
        return list(self._resultados.get(escenario_id, []))

    # ------------------------------------- what-if / expansión 37.10-11
    def comparar(self, escenario_base: str, escenario_alternativo: str,
                 usuario: str) -> dict:
        """Comparación aislada entre escenarios (What-If 37.11,
        Expansion Planner 37.10)."""
        for sid in (escenario_base, escenario_alternativo):
            if not self._resultados.get(sid):
                self.ejecutar(sid, usuario)
        b = self._resultados[escenario_base][-1]
        a = self._resultados[escenario_alternativo][-1]
        delta = a["rendimiento_lotes_dia"] - b["rendimiento_lotes_dia"]
        comp = {"base": escenario_base, "alternativo": escenario_alternativo,
                "rendimiento_base": b["rendimiento_lotes_dia"],
                "rendimiento_alternativo": a["rendimiento_lotes_dia"],
                "delta_lotes_dia": round(delta, 4),
                "delta_pct": (round(100.0 * delta
                                    / b["rendimiento_lotes_dia"], 2)
                              if b["rendimiento_lotes_dia"] else None),
                "cuello_base": b["cuello_de_botella"]["recurso_id"],
                "cuello_alternativo": a["cuello_de_botella"]["recurso_id"],
                "nota": "resultados de simulación aislada (37.11); "
                        "independientes de la operación real"}
        self._auditar(usuario, "comparar_escenarios",
                      f"{escenario_base} vs {escenario_alternativo}")
        return comp

    # ---------------------------------------------- optimizador 37.9
    def proponer_redistribucion(self, escenario_id: str,
                                usuario: str) -> dict:
        """Propuesta documentada de redistribución de carga (37.9).

        PROPUESTA, nunca decisión: recomienda la acción sobre el cuello
        de botella del escenario (41.9)."""
        if not self._resultados.get(escenario_id):
            self.ejecutar(escenario_id, usuario)
        r = self._resultados[escenario_id][-1]
        cuello = r["cuello_de_botella"]
        saturados = [x["recurso_id"] for x in r["recursos"] if x["saturado"]]
        propuesta = {
            "escenario_id": escenario_id,
            "tipo": "propuesta_redistribucion",
            "cuello_de_botella": cuello["recurso_id"],
            "etapa_limitante": cuello["etapa_limitante"],
            "recursos_saturados": saturados,
            "propuesta": (f"incrementar capacidad de "
                          f"'{cuello['recurso_id']}' (etapa "
                          f"'{cuello['etapa_limitante']}') o redistribuir "
                          f"carga hacia recursos con reserva"),
            "naturaleza": "PROPUESTA de soporte a la decisión (37.9/41.9): "
                          "requiere evaluación y aprobación humana; el "
                          "motor nunca modifica la operación real",
            "fecha": datetime.now(timezone.utc).isoformat()}
        self._auditar(usuario, "proponer_redistribucion", escenario_id)
        return propuesta
