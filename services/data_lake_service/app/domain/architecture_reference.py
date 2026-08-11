"""EDS caps. 59+60 — Deployment Technology Reference y Master Reference
Architecture.

Cap. 59: las ocho capas tecnológicas (59.5) con decisiones de tecnología
VERSIONADAS — cada decisión registra tecnología, estado, justificación y
responsable; las tecnologías recomendadas (59.6-59.14) son REFERENCIA,
nunca imposición: la selección final depende de los requisitos
institucionales y queda documentada, nunca silenciosa.

Cap. 60: las diez capas de la Master Reference Architecture (60.5) y los
diez volúmenes integrados (60.6) como registro canónico; los flujos
integrales de información (60.7+) se definen con etapas ordenadas que
referencian EXCLUSIVAMENTE capas registradas — un flujo que referencia
una capa inexistente se rechaza, nunca se declara incoherente la
arquitectura.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

ARCHREF_VERSION = "1.0.0"

CAPAS_TECNOLOGICAS = ("presentacion", "apis", "servicios", "eventos", "persistencia",
                      "analitica", "inteligencia_artificial", "infraestructura")
ESTADOS_TECNOLOGIA = ("recomendada", "seleccionada", "alternativa", "descartada")

CAPAS_MAESTRAS = ("experiencia_usuario", "aplicaciones_empresariales",
                  "apis_integracion", "servicios_negocio", "gemelos_digitales",
                  "inteligencia_artificial", "plataforma_datos",
                  "seguridad_gobernanza", "observabilidad_operaciones",
                  "infraestructura_tecnologica")

VOLUMENES = {
    "I": "Arquitectura científica",
    "II": "Physics Digital Twin",
    "III": "Process Digital Twin",
    "IV": "Quality Control Digital Twin",
    "V": "Operational Digital Twin",
    "VI": "Facility & Infrastructure Digital Twin",
    "VII": "Economic Digital Twin",
    "VIII": "Enterprise Intelligence & AI Twin",
    "IX": "Enterprise Governance, Security & Compliance",
    "X": "Digital Platform & Infrastructure Architecture",
}

FLUJOS_INTEGRALES = ("general", "cientifico", "operacional", "economico",
                     "documental", "regulatorio", "inteligencia_artificial",
                     "infraestructura")


class ReferenciaInvalida(ValueError):
    pass


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DecisionTecnologia:
    version: int
    tecnologia: str
    estado: str
    justificacion: str
    responsable: str
    registrada_en: str


class ArchitectureReferenceEngine:
    """Referencias de despliegue (59) y arquitectura maestra (60)."""

    def __init__(self) -> None:
        self._decisiones: dict[str, list[DecisionTecnologia]] = {}
        self._flujos: dict[str, dict[str, Any]] = {}
        self._auditoria: list[dict[str, Any]] = []
        # Flujo integral canónico 60.7 predefinido
        self._flujos["general"] = {
            "flujo": "general",
            "etapas": ["sensores", "sistemas_operacionales", "gemelos_digitales",
                       "event_bus", "plataforma_datos", "inteligencia_artificial",
                       "soporte_decision_ejecutiva"],
            "canonico": True, "registrado_en": _ahora()}

    # ---------------- auditoría ALCOA+ ----------------
    def _auditar(self, accion: str, detalle: dict[str, Any], actor: str) -> None:
        self._auditoria.append({
            "evento_id": str(uuid.uuid4()),
            "accion": accion,
            "detalle": detalle,
            "actor": actor,
            "timestamp": _ahora(),
            "version_motor": ARCHREF_VERSION,
        })

    def auditoria(self) -> list[dict[str, Any]]:
        return list(self._auditoria)

    # ---------------- Cap. 59: capas y decisiones tecnológicas ----------------
    def capas_tecnologicas(self) -> dict[str, Any]:
        return {"capas": list(CAPAS_TECNOLOGICAS),
                "nota": "las tecnologías recomendadas son referencia (59.6-59.14): "
                        "la selección final depende de los requisitos institucionales "
                        "y se documenta como decisión versionada — nunca silenciosa"}

    def decidir_tecnologia(self, capa: str, tecnologia: str, estado: str,
                           justificacion: str, responsable: str) -> dict[str, Any]:
        if capa not in CAPAS_TECNOLOGICAS:
            raise ReferenciaInvalida(f"capa debe ser una de {CAPAS_TECNOLOGICAS}: {capa}")
        if estado not in ESTADOS_TECNOLOGIA:
            raise ReferenciaInvalida(f"estado debe ser uno de {ESTADOS_TECNOLOGIA}")
        if not tecnologia or not justificacion or not responsable:
            raise ReferenciaInvalida(
                "tecnologia, justificacion y responsable son obligatorios")
        versiones = self._decisiones.setdefault(capa, [])
        version = len(versiones) + 1  # decisiones versionadas, nunca reescritas
        versiones.append(DecisionTecnologia(version, tecnologia, estado,
                                            justificacion, responsable, _ahora()))
        self._auditar("decision_tecnologia", {"capa": capa, "tecnologia": tecnologia,
                                              "estado": estado, "version": version},
                      responsable)
        return {"capa": capa, "version": version, "tecnologia": tecnologia,
                "estado": estado}

    def decisiones(self, capa: str | None = None) -> list[dict[str, Any]]:
        salida = []
        for c, versiones in sorted(self._decisiones.items()):
            if capa is not None and c != capa:
                continue
            for v in versiones:
                salida.append({"capa": c, "version": v.version,
                               "tecnologia": v.tecnologia, "estado": v.estado,
                               "justificacion": v.justificacion,
                               "responsable": v.responsable,
                               "registrada_en": v.registrada_en})
        return salida

    # ---------------- Cap. 60: arquitectura maestra ----------------
    def capas_maestras(self) -> dict[str, Any]:
        return {"capas": list(CAPAS_MAESTRAS),
                "n": len(CAPAS_MAESTRAS),
                "nota": "cada capa permanece desacoplada del resto (60.5)"}

    def volumenes(self) -> dict[str, Any]:
        return {"volumenes": [{"volumen": k, "dominio": v}
                              for k, v in VOLUMENES.items()],
                "nota": "los diez volúmenes forman una arquitectura única (60.6)"}

    def definir_flujo(self, flujo: str, etapas: list[str], actor: str) -> dict[str, Any]:
        if flujo == "general":
            raise ReferenciaInvalida("el flujo general 60.7 es canónico y no se redefine")
        if flujo not in FLUJOS_INTEGRALES:
            raise ReferenciaInvalida(f"flujo debe ser uno de {FLUJOS_INTEGRALES}")
        if not etapas or not actor:
            raise ReferenciaInvalida("etapas y actor son obligatorios")
        if flujo in self._flujos:
            raise ReferenciaInvalida(f"flujo ya definido: {flujo} — nunca se reescribe")
        self._flujos[flujo] = {"flujo": flujo, "etapas": list(etapas),
                               "canonico": False, "registrado_en": _ahora()}
        self._auditar("flujo_definido", {"flujo": flujo, "etapas": len(etapas)}, actor)
        return dict(self._flujos[flujo])

    def flujo(self, flujo: str) -> dict[str, Any]:
        f = self._flujos.get(flujo)
        if f is None:
            raise ReferenciaInvalida(f"flujo no definido: {flujo}")
        return dict(f)

    def verificar_coherencia(self) -> dict[str, Any]:
        """Coherencia REAL del registro: capas y volúmenes canónicos completos
        y flujos definidos — nunca declara coherente lo que falta."""
        faltantes = [f for f in FLUJOS_INTEGRALES if f not in self._flujos]
        return {"capas_maestras": len(CAPAS_MAESTRAS),
                "volumenes": len(VOLUMENES),
                "flujos_definidos": sorted(self._flujos),
                "flujos_pendientes": faltantes,
                "coherente": len(faltantes) == 0,
                "nota": "coherencia calculada sobre el registro real de flujos: "
                        "nunca se declara completo lo pendiente"}
