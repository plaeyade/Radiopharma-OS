"""EDS cap. 56 — DevSecOps & Platform Engineering.

Source Control Manager 56.6 (todo cambio asociado a un identificador
único; historial nunca reescrito), Continuous Integration Engine 56.7
(cada ejecución — compilación, pruebas, análisis estático, artefactos —
permanece registrada; el runner real se inyecta: sin runner la ejecución
NO se declara), Continuous Delivery Engine 56.8 (estrategias de despliegue
configurables; promoción solo desde una ejecución CI exitosa y con
escaneo de seguridad sin críticos 56.9), Security Scanner 56.9 (los
resultados — vulnerabilidades reales reportadas por el scanner inyectado
— forman parte del proceso de validación; nunca se declara "limpio" sin
escaneo) y Artifact Registry 56.10 (trazabilidad completa; nunca
sobrescribe).
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

DEVSECOPS_VERSION = "1.0.0"
ESTADOS_CI = ("exitosa", "fallida")
ESTADOS_CD = ("promovido", "rechazado")
ESTRATEGIAS_DESPLIEGUE = ("rolling", "blue_green", "canary")
SEVERIDADES = ("critica", "alta", "media", "baja")


class DevsecopsInvalido(ValueError):
    pass


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Cambio:
    cambio_id: str
    repositorio: str
    rama: str
    autor: str
    descripcion: str
    hash_commit: str
    registrado_en: str


@dataclass
class EjecucionCI:
    ejecucion_id: str
    cambio_id: str
    estado: str
    etapas: dict[str, Any]
    artefactos: list[str]
    responsable: str
    ejecutada_en: str


@dataclass
class Artefacto:
    artefacto_id: str
    tipo: str
    version: str
    hash_sha256: str
    ejecucion_origen: str
    registrado_en: str


class DevsecopsEngine:
    """Pipeline DevSecOps (cap. 56)."""

    def __init__(self) -> None:
        self._cambios: dict[str, Cambio] = {}
        self._ejecuciones: list[EjecucionCI] = []
        self._escaneos: dict[str, dict[str, Any]] = {}  # ejecucion_id -> resultado
        self._despliegues: list[dict[str, Any]] = []
        self._artefactos: dict[str, Artefacto] = {}
        self._auditoria: list[dict[str, Any]] = []

    # ---------------- auditoría ALCOA+ ----------------
    def _auditar(self, accion: str, detalle: dict[str, Any], actor: str) -> None:
        self._auditoria.append({
            "evento_id": str(uuid.uuid4()),
            "accion": accion,
            "detalle": detalle,
            "actor": actor,
            "timestamp": _ahora(),
            "version_motor": DEVSECOPS_VERSION,
        })

    def auditoria(self) -> list[dict[str, Any]]:
        return list(self._auditoria)

    # ---------------- Source Control Manager 56.6 ----------------
    def registrar_cambio(self, cambio_id: str, repositorio: str, rama: str,
                         autor: str, descripcion: str,
                         hash_commit: str) -> dict[str, Any]:
        if not all([cambio_id, repositorio, rama, autor, hash_commit]):
            raise DevsecopsInvalido("cambio_id, repositorio, rama, autor y hash_commit "
                                    "son obligatorios")
        if cambio_id in self._cambios:
            raise DevsecopsInvalido(f"cambio ya registrado: {cambio_id} — identificador "
                                    "único por cambio (56.6)")
        self._cambios[cambio_id] = Cambio(cambio_id, repositorio, rama, autor,
                                          descripcion, hash_commit, _ahora())
        self._auditar("cambio_registrado", {"cambio_id": cambio_id,
                      "repositorio": repositorio, "rama": rama}, autor)
        return {"cambio_id": cambio_id, "hash_commit": hash_commit}

    def historial_cambios(self, repositorio: str | None = None) -> list[dict[str, Any]]:
        return [{"cambio_id": c.cambio_id, "repositorio": c.repositorio,
                 "rama": c.rama, "autor": c.autor, "descripcion": c.descripcion,
                 "hash_commit": c.hash_commit, "registrado_en": c.registrado_en}
                for c in self._cambios.values()
                if repositorio is None or c.repositorio == repositorio]

    # ---------------- Continuous Integration Engine 56.7 ----------------
    def ejecutar_ci(self, cambio_id: str, responsable: str,
                    runner: Callable[[str], dict[str, Any]] | None = None) -> dict[str, Any]:
        if cambio_id not in self._cambios:
            raise DevsecopsInvalido(f"cambio no registrado: {cambio_id}")
        if not responsable:
            raise DevsecopsInvalido("responsable obligatorio (56.12)")
        if runner is None:
            raise DevsecopsInvalido("sin runner de CI: la ejecución NO se declara — "
                                    "resultado honesto pendiente del entorno de build")
        etapas = runner(cambio_id)  # ejecución REAL del pipeline inyectado
        if not isinstance(etapas, dict) or "compilacion" not in etapas \
                or "pruebas" not in etapas:
            raise DevsecopsInvalido("el runner debe devolver etapas con compilacion y "
                                    "pruebas")
        estado = "exitosa" if etapas.get("compilacion") == "ok" \
            and etapas.get("pruebas", {}).get("fallidas", 1) == 0 else "fallida"
        artefactos = list(etapas.get("artefactos", [])) if estado == "exitosa" else []
        ej = EjecucionCI(str(uuid.uuid4()), cambio_id, estado, dict(etapas),
                         artefactos, responsable, _ahora())
        self._ejecuciones.append(ej)  # cada ejecución permanece registrada
        self._auditar("ci_ejecutada", {"ejecucion_id": ej.ejecucion_id,
                      "cambio_id": cambio_id, "estado": estado}, responsable)
        return {"ejecucion_id": ej.ejecucion_id, "cambio_id": cambio_id,
                "estado": estado, "artefactos": artefactos,
                "ejecutada_en": ej.ejecutada_en}

    def ejecuciones_ci(self) -> list[dict[str, Any]]:
        return [{"ejecucion_id": e.ejecucion_id, "cambio_id": e.cambio_id,
                 "estado": e.estado, "etapas": e.etapas, "artefactos": e.artefactos,
                 "responsable": e.responsable, "ejecutada_en": e.ejecutada_en}
                for e in self._ejecuciones]

    # ---------------- Security Scanner 56.9 ----------------
    def registrar_escaneo(self, ejecucion_id: str, responsable: str,
                          scanner: Callable[[], list[dict[str, Any]]] | None = None
                          ) -> dict[str, Any]:
        ej = self._ejecucion(ejecucion_id)
        if scanner is None:
            raise DevsecopsInvalido("sin scanner de seguridad: el resultado NO se "
                                    "declara limpio — honestidad 56.9")
        hallazgos = scanner()  # hallazgos REALES del scanner inyectado
        for h in hallazgos:
            if h.get("severidad") not in SEVERIDADES:
                raise DevsecopsInvalido(f"severidad inválida: {h.get('severidad')}")
        criticos = sum(1 for h in hallazgos if h["severidad"] == "critica")
        resultado = {"ejecucion_id": ejecucion_id, "hallazgos": hallazgos,
                     "n_hallazgos": len(hallazgos), "criticos": criticos,
                     "apto_para_promocion": criticos == 0,
                     "responsable": responsable, "escaneado_en": _ahora()}
        self._escaneos[ejecucion_id] = resultado
        self._auditar("escaneo_seguridad", {"ejecucion_id": ejecucion_id,
                      "hallazgos": len(hallazgos), "criticos": criticos}, responsable)
        return dict(resultado)

    def _ejecucion(self, ejecucion_id: str) -> EjecucionCI:
        ej = next((e for e in self._ejecuciones if e.ejecucion_id == ejecucion_id), None)
        if ej is None:
            raise DevsecopsInvalido(f"ejecución CI no registrada: {ejecucion_id}")
        return ej

    # ---------------- Continuous Delivery Engine 56.8 ----------------
    def promover(self, ejecucion_id: str, entorno: str, estrategia: str,
                 responsable: str) -> dict[str, Any]:
        if estrategia not in ESTRATEGIAS_DESPLIEGUE:
            raise DevsecopsInvalido(f"estrategia debe ser una de {ESTRATEGIAS_DESPLIEGUE}")
        ej = self._ejecucion(ejecucion_id)
        if ej.estado != "exitosa":
            raise DevsecopsInvalido(f"ejecución CI {ej.estado}: solo se promueven "
                                    "ejecuciones exitosas (56.8)")
        escaneo = self._escaneos.get(ejecucion_id)
        if escaneo is None:
            raise DevsecopsInvalido("sin escaneo de seguridad registrado: la promoción "
                                    "NO procede — el escaneo forma parte de la "
                                    "validación (56.9)")
        if not escaneo["apto_para_promocion"]:
            raise DevsecopsInvalido(f"escaneo con {escaneo['criticos']} hallazgos "
                                    "críticos: promoción bloqueada (56.9)")
        despliegue = {"despliegue_id": str(uuid.uuid4()),
                      "ejecucion_id": ejecucion_id, "entorno": entorno,
                      "estrategia": estrategia, "estado": "promovido",
                      "artefactos": list(ej.artefactos), "responsable": responsable,
                      "promovido_en": _ahora()}
        self._despliegues.append(despliegue)
        self._auditar("cd_promocion", {"despliegue_id": despliegue["despliegue_id"],
                      "entorno": entorno, "estrategia": estrategia}, responsable)
        return dict(despliegue)

    def despliegues(self) -> list[dict[str, Any]]:
        return [dict(d) for d in self._despliegues]

    # ---------------- Artifact Registry 56.10 ----------------
    def registrar_artefacto(self, artefacto_id: str, tipo: str, version: str,
                            contenido: bytes, ejecucion_origen: str,
                            responsable: str) -> dict[str, Any]:
        if not all([artefacto_id, tipo, version, ejecucion_origen, responsable]):
            raise DevsecopsInvalido("todos los campos son obligatorios (56.10)")
        if artefacto_id in self._artefactos:
            raise DevsecopsInvalido(f"artefacto ya registrado: {artefacto_id} — "
                                    "trazabilidad completa, nunca sobrescrito")
        hash_sha256 = hashlib.sha256(contenido).hexdigest()
        self._artefactos[artefacto_id] = Artefacto(
            artefacto_id, tipo, version, hash_sha256, ejecucion_origen, _ahora())
        self._auditar("artefacto_registrado", {"artefacto_id": artefacto_id,
                      "tipo": tipo, "hash": hash_sha256}, responsable)
        return {"artefacto_id": artefacto_id, "hash_sha256": hash_sha256}

    def verificar_artefacto(self, artefacto_id: str, contenido: bytes) -> dict[str, Any]:
        art = self._artefactos.get(artefacto_id)
        if art is None:
            raise DevsecopsInvalido(f"artefacto no registrado: {artefacto_id}")
        hash_real = hashlib.sha256(contenido).hexdigest()
        integro = hash_real == art.hash_sha256
        return {"artefacto_id": artefacto_id, "integro": integro,
                "hash_registrado": art.hash_sha256, "hash_calculado": hash_real}

    def artefactos(self) -> list[dict[str, Any]]:
        return [{"artefacto_id": a.artefacto_id, "tipo": a.tipo, "version": a.version,
                 "hash_sha256": a.hash_sha256, "ejecucion_origen": a.ejecucion_origen,
                 "registrado_en": a.registrado_en}
                for a in self._artefactos.values()]
