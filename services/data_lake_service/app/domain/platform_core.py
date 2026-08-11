"""EDS cap. 51 — Digital Platform Core.

Catálogo de microservicios 51.7/51.8 (cada servicio con responsabilidad
única e interfaces bien definidas; cada imagen registra versión,
dependencias, configuración y firma — las imágenes permanecen
completamente trazables y el catálogo NUNCA sobrescribe) y Gestión de
configuración 51.12 (la configuración permanece separada del código; cada
parámetro registra versión, entorno, vigencia y responsable; TODA
modificación permanece auditada — historial completo, nunca reescrito).
La orquestación concreta (Kubernetes 51.9, Service Mesh 51.10, API
Gateway 51.11) permanece desacoplada del diseño funcional: su estado se
registra declarativamente y nunca se declara desplegada sin evidencia.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

PLATFORM_CORE_VERSION = "1.0.0"
ENTORNOS = ("desarrollo", "validacion", "produccion")
ESTADOS_DESPLIEGUE = ("registrado", "desplegado", "retirado")


class PlataformaInvalida(ValueError):
    pass


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ImagenServicio:
    version: str
    dependencias: list[str]
    configuracion: dict[str, Any]
    firma: str | None
    registrada_en: str


@dataclass
class Servicio:
    servicio_id: str
    responsabilidad: str
    interfaces: list[str]
    estado: str
    imagenes: list[ImagenServicio] = field(default_factory=list)
    registrado_en: str = ""


@dataclass
class VersionParametro:
    version: int
    valor: Any
    entorno: str
    vigencia_desde: str
    responsable: str
    motivo: str
    registrada_en: str


class PlatformCoreEngine:
    """Núcleo de plataforma digital (cap. 51)."""

    def __init__(self) -> None:
        self._servicios: dict[str, Servicio] = {}
        self._parametros: dict[str, list[VersionParametro]] = {}
        self._auditoria: list[dict[str, Any]] = []

    # ---------------- auditoría ALCOA+ (51.19) ----------------
    def _auditar(self, accion: str, detalle: dict[str, Any], actor: str) -> None:
        self._auditoria.append({
            "evento_id": str(uuid.uuid4()),
            "accion": accion,
            "detalle": detalle,
            "actor": actor,
            "timestamp": _ahora(),
            "version_motor": PLATFORM_CORE_VERSION,
        })

    def auditoria(self) -> list[dict[str, Any]]:
        return list(self._auditoria)

    # ---------------- Catálogo de microservicios 51.7/51.8 ----------------
    def registrar_servicio(self, servicio_id: str, responsabilidad: str,
                           interfaces: list[str], actor: str) -> dict[str, Any]:
        if not servicio_id or not responsabilidad or not actor:
            raise PlataformaInvalida("servicio_id, responsabilidad y actor son obligatorios")
        if not interfaces:
            raise PlataformaInvalida("cada servicio publica interfaces bien definidas (51.7)")
        if servicio_id in self._servicios:
            raise PlataformaInvalida(f"servicio ya registrado: {servicio_id} — el catálogo "
                                     "nunca sobrescribe")
        self._servicios[servicio_id] = Servicio(
            servicio_id, responsabilidad, list(interfaces), "registrado", [], _ahora())
        self._auditar("servicio_registrado", {"servicio_id": servicio_id,
                                              "interfaces": interfaces}, actor)
        return self._dto_servicio(self._servicios[servicio_id])

    def registrar_imagen(self, servicio_id: str, version: str,
                         dependencias: list[str], configuracion: dict[str, Any],
                         actor: str, firma: str | None = None) -> dict[str, Any]:
        svc = self._servicio(servicio_id)
        if not version or not actor:
            raise PlataformaInvalida("version y actor son obligatorios")
        if any(i.version == version for i in svc.imagenes):
            raise PlataformaInvalida(f"imagen {servicio_id}:{version} ya registrada — "
                                     "las imágenes permanecen trazables, nunca reemplazadas (51.8)")
        svc.imagenes.append(ImagenServicio(version, list(dependencias),
                                           dict(configuracion), firma, _ahora()))
        self._auditar("imagen_registrada", {"servicio_id": servicio_id, "version": version,
                                            "firmada": firma is not None}, actor)
        return {"servicio_id": servicio_id, "version": version, "firmada": firma is not None}

    def cambiar_estado_servicio(self, servicio_id: str, estado: str,
                                actor: str, evidencia: str) -> dict[str, Any]:
        """51.9/51.17: el despliegue solo se declara con evidencia del orquestador."""
        svc = self._servicio(servicio_id)
        if estado not in ESTADOS_DESPLIEGUE:
            raise PlataformaInvalida(f"estado debe ser uno de {ESTADOS_DESPLIEGUE}")
        if estado == "desplegado" and not evidencia:
            raise PlataformaInvalida("evidencia obligatoria: nunca se declara desplegado "
                                     "sin evidencia del orquestador (51.9/51.17)")
        if estado == "desplegado" and not svc.imagenes:
            raise PlataformaInvalida("sin imagen registrada no puede declararse despliegue")
        svc.estado = estado
        self._auditar("servicio_estado", {"servicio_id": servicio_id, "estado": estado,
                                          "evidencia": evidencia or None}, actor)
        return self._dto_servicio(svc)

    def servicios(self) -> list[dict[str, Any]]:
        return [self._dto_servicio(s) for s in self._servicios.values()]

    def _servicio(self, servicio_id: str) -> Servicio:
        svc = self._servicios.get(servicio_id)
        if svc is None:
            raise PlataformaInvalida(f"servicio no registrado: {servicio_id}")
        return svc

    @staticmethod
    def _dto_servicio(s: Servicio) -> dict[str, Any]:
        return {"servicio_id": s.servicio_id, "responsabilidad": s.responsabilidad,
                "interfaces": list(s.interfaces), "estado": s.estado,
                "imagenes": [{"version": i.version, "dependencias": i.dependencias,
                              "configuracion": i.configuracion, "firma": i.firma,
                              "registrada_en": i.registrada_en} for i in s.imagenes],
                "registrado_en": s.registrado_en}

    # ---------------- Gestión de configuración 51.12 ----------------
    def definir_parametro(self, clave: str, valor: Any, entorno: str,
                          vigencia_desde: str, responsable: str, motivo: str) -> dict[str, Any]:
        if not clave or not vigencia_desde or not responsable or not motivo:
            raise PlataformaInvalida("clave, vigencia_desde, responsable y motivo son "
                                     "obligatorios (51.12)")
        if entorno not in ENTORNOS:
            raise PlataformaInvalida(f"entorno debe ser uno de {ENTORNOS}: {entorno}")
        versiones = self._parametros.setdefault(clave, [])
        version = len(versiones) + 1  # historial completo: nunca se reescribe
        versiones.append(VersionParametro(version, valor, entorno, vigencia_desde,
                                          responsable, motivo, _ahora()))
        self._auditar("parametro_definido", {"clave": clave, "version": version,
                                             "entorno": entorno, "motivo": motivo}, responsable)
        return {"clave": clave, "version": version, "entorno": entorno}

    def parametro(self, clave: str, entorno: str | None = None,
                  version: int | None = None) -> dict[str, Any]:
        versiones = self._parametros.get(clave)
        if not versiones:
            raise PlataformaInvalida(f"parámetro no definido: {clave}")
        candidatas = [v for v in versiones if entorno is None or v.entorno == entorno]
        if not candidatas:
            raise PlataformaInvalida(f"sin valor de {clave} para el entorno {entorno}")
        if version is not None:
            v = next((x for x in candidatas if x.version == version), None)
            if v is None:
                raise PlataformaInvalida(f"versión {version} no registrada para {clave}")
        else:
            v = candidatas[-1]
        return {"clave": clave, "version": v.version, "valor": v.valor, "entorno": v.entorno,
                "vigencia_desde": v.vigencia_desde, "responsable": v.responsable,
                "motivo": v.motivo, "registrada_en": v.registrada_en,
                "revisiones": len(versiones)}

    def historial_parametro(self, clave: str) -> list[dict[str, Any]]:
        versiones = self._parametros.get(clave)
        if not versiones:
            raise PlataformaInvalida(f"parámetro no definido: {clave}")
        return [{"version": v.version, "valor": v.valor, "entorno": v.entorno,
                 "vigencia_desde": v.vigencia_desde, "responsable": v.responsable,
                 "motivo": v.motivo, "registrada_en": v.registrada_en} for v in versiones]

    def listar_parametros(self) -> list[dict[str, Any]]:
        return [self.parametro(k) for k in sorted(self._parametros)]
