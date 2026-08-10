"""Multi-Agent Decision Support Engine (EDS cap. 43).

El MADSE coordina agentes especializados que ASISTEN la decisión; no
sustituyen decisiones clínicas, regulatorias, administrativas ni
operativas (43.3): toda salida del motor es una RECOMENDACIÓN marcada
como soporte a la decisión (41.9), y las decisiones finales permanecen
en usuarios autorizados.

- **Agent Registry (43.6)**: catálogo versionado de agentes
  (dominio, capacidades, estado). Los agentes con respaldo de modelo
  IA se declaran con su contribución determinista registrada; un
  agente sin contribución disponible se marca honestamente
  `sin_runtime` — el motor NUNCA inventa su respuesta.
- **Agent Orchestrator (43.8)**: selecciona agentes por dominio y
  coordina la consulta; el flujo queda documentado.
- **Consensus Engine (43.9)**: consolida contribuciones en una
  recomendación integrada; cada contribución individual permanece
  registrada.
- **Context Manager (43.10)**: contexto referenciado en cada consulta.
- **Conversation Manager (43.11)**: conversaciones con fecha, usuario,
  agentes, contexto y resultados.
- **Task Planner (43.12)**: descomposición del problema en tareas por
  dominio, con secuencia registrada.

Auditoría completa de inferencias (43.2).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

MADSE_VERSION = "madse-1.0.0"

DOMINIOS_AGENTE = ("fisica_medica", "radioquimica", "control_calidad",
                   "produccion", "operacion", "proteccion_radiologica",
                   "mantenimiento", "economia", "regulacion", "logistica")

# contribución determinista: (contexto) -> dict
Contribucion = Callable[[dict], dict]


class AgentesInvalido(ValueError):
    """Agente, consulta o consenso inválido (cap. 43)."""


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Agente:
    """Agent Registry (43.6)."""
    agente_id: str
    dominio: str
    version: str
    capacidades: list[str]
    estado: str = "activo"          # activo/sin_runtime/retirado
    descripcion: str = ""


class MultiAgentEngine:
    """MADSE: orquestación, consenso y trazabilidad de recomendaciones."""

    def __init__(self) -> None:
        self._agentes: dict[str, Agente] = {}
        self._contribuciones: dict[str, Contribucion] = {}
        self._conversaciones: list[dict] = []
        self._auditoria: list[dict] = []

    def _auditar(self, usuario: str, accion: str, detalle: str) -> None:
        self._auditoria.append({"usuario": usuario, "accion": accion,
                                "detalle": detalle, "fecha": _ahora()})

    def auditoria(self) -> list[dict]:
        return list(self._auditoria)

    # --------------------------------------------------- registry 43.6
    def registrar_agente(self, agente: Agente,
                         contribucion: Contribucion | None,
                         usuario: str) -> dict:
        """Alta de agente. Sin contribución registrada, el agente queda
        honestamente `sin_runtime`: el motor nunca inventa su salida."""
        if agente.agente_id in self._agentes:
            raise AgentesInvalido(
                f"agente ya registrado: {agente.agente_id} (43.6: "
                "versionado, nunca sobrescribe)")
        if agente.dominio not in DOMINIOS_AGENTE:
            raise AgentesInvalido(f"dominio no reconocido (43.7): "
                                  f"{agente.dominio}")
        if not agente.capacidades:
            raise AgentesInvalido("capacidades obligatorias (43.6)")
        if contribucion is None:
            agente.estado = "sin_runtime"
        else:
            self._contribuciones[agente.agente_id] = contribucion
        self._agentes[agente.agente_id] = agente
        self._auditar(usuario, "registrar_agente",
                      f"{agente.agente_id} ({agente.dominio}, "
                      f"{agente.estado})")
        return {"agente_id": agente.agente_id, "estado": agente.estado}

    def agentes(self) -> list[dict]:
        return [{"agente_id": a.agente_id, "dominio": a.dominio,
                 "version": a.version, "capacidades": list(a.capacidades),
                 "estado": a.estado} for a in self._agentes.values()]

    # -------------------------------------------- orquestación 43.8/43.12
    def planificar(self, problema: str, dominios: list[str]) -> list[dict]:
        """Task Planner (43.12): descomposición en tareas por dominio,
        secuencia registrada."""
        if not dominios:
            raise AgentesInvalido("la consulta exige dominios (43.12)")
        tareas = []
        for i, d in enumerate(dominios, 1):
            if d not in DOMINIOS_AGENTE:
                raise AgentesInvalido(f"dominio desconocido: {d}")
            tareas.append({"secuencia": i, "dominio": d,
                           "tarea": f"analizar '{problema}' desde {d}"})
        return tareas

    def consultar(self, problema: str, dominios: list[str], contexto: dict,
                  usuario: str) -> dict:
        """Orchestrator (43.8) + Consensus Engine (43.9).

        Devuelve recomendación integrada con contribuciones individuales
        registradas; marcada como soporte a la decisión (43.3/41.9).
        """
        if not problema:
            raise AgentesInvalido("problema obligatorio")
        tareas = self.planificar(problema, dominios)
        contribuciones = []
        omitidos = []
        for tarea in tareas:
            candidatos = [a for a in self._agentes.values()
                          if a.dominio == tarea["dominio"]]
            activos = [a for a in candidatos if a.estado == "activo"]
            if not activos:
                omitidos.append({
                    "dominio": tarea["dominio"],
                    "motivo": ("sin agentes registrados"
                               if not candidatos else
                               "agentes sin runtime: el motor nunca "
                               "inventa su contribución")})
                continue
            for a in activos:
                salida = self._contribuciones[a.agente_id](contexto)
                contribuciones.append({
                    "agente_id": a.agente_id, "dominio": a.dominio,
                    "version_agente": a.version,
                    "secuencia": tarea["secuencia"],
                    "contribucion": salida})
        if not contribuciones:
            raise AgentesInvalido(
                "ningún dominio pudo contribuir: no hay recomendación "
                "que consolidar (honesto, 43.9)")
        consenso = self._consolidar(contribuciones)
        conversacion = {
            "conversacion_id": f"conv-{len(self._conversaciones) + 1:04d}",
            "fecha": _ahora(), "usuario": usuario, "problema": problema,
            "tareas": tareas, "contexto": dict(contexto),   # 43.10
            "agentes_participantes": [c["agente_id"]
                                      for c in contribuciones],
            "contribuciones": contribuciones,               # 43.9
            "dominios_omitidos": omitidos,
            "recomendacion": consenso,
            "naturaleza": "RECOMENDACIÓN de soporte a la decisión "
                          "(43.3/41.9): la decisión final permanece en "
                          "usuarios autorizados; el MADSE nunca decide"}
        self._conversaciones.append(conversacion)
        self._auditar(usuario, "consultar",
                      f"{conversacion['conversacion_id']}: "
                      f"{len(contribuciones)} contribuciones")
        return conversacion

    def _consolidar(self, contribuciones: list[dict]) -> dict:
        """Consenso determinista documentado (43.9): une hallazgos,
        alertas y sugerencias preservando su procedencia."""
        hallazgos, alertas, sugerencias = [], [], []
        for c in contribuciones:
            origen = f"{c['agente_id']} ({c['dominio']})"
            datos = c["contribucion"]
            for h in datos.get("hallazgos", []):
                hallazgos.append({"origen": origen, "hallazgo": h})
            for a in datos.get("alertas", []):
                alertas.append({"origen": origen, "alerta": a})
            for s in datos.get("sugerencias", []):
                sugerencias.append({"origen": origen, "sugerencia": s})
        return {"metodo": "consenso determinista: unión de hallazgos, "
                          "alertas y sugerencias con procedencia",
                "n_contribuciones": len(contribuciones),
                "hallazgos": hallazgos, "alertas": alertas,
                "sugerencias": sugerencias}

    # ------------------------------------------- conversaciones 43.11
    def conversaciones(self) -> list[dict]:
        return [{"conversacion_id": c["conversacion_id"],
                 "fecha": c["fecha"], "usuario": c["usuario"],
                 "problema": c["problema"],
                 "agentes_participantes": c["agentes_participantes"],
                 "n_contribuciones": len(c["contribuciones"])}
                for c in self._conversaciones]

    def conversacion(self, conversacion_id: str) -> dict:
        for c in self._conversaciones:
            if c["conversacion_id"] == conversacion_id:
                return c
        raise AgentesInvalido(f"conversación inexistente: "
                              f"{conversacion_id}")
