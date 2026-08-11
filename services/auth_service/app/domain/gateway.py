"""EDS cap. 53 — API Gateway & Integration Layer.

API Registry 53.7 (catálogo corporativo versionado: identificador,
versión, propietario, documentación, estado), API Lifecycle Manager 53.9
(diseño → publicación → actualización → retiro; cada versión mantiene
compatibilidad conforme a la política), Integration Manager 53.8 (cada
integración completamente documentada), Traffic Manager 53.11 (políticas
configurables de limitación; TODA solicitud es validada antes de llegar
al servicio 53.6) y gestión temporal 53.12 (cada interacción registrada).

Honestidad de plataforma: el Gateway en proceso valida, limita y registra
de forma real; el proxy HTTP externo se reporta `no_configurado` — nunca
se declara enrutada una solicitud a un servicio que no existe o no está
publicado.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

GATEWAY_VERSION = "1.0.0"
ESTADOS_API = ("diseno", "publicada", "retirada")
TRANSICIONES_API = {"diseno": {"publicada", "retirada"},
                    "publicada": {"retirada"},
                    "retirada": set()}
TIPOS_INTEGRACION = ("clinica", "industrial", "cientifica", "corporativa", "externa")


class GatewayInvalido(ValueError):
    pass


class SolicitudRechazada(PermissionError):
    pass


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


@dataclass
class VersionApi:
    version: str
    documentacion: str
    rutas: list[str]
    registrada_en: str


@dataclass
class Api:
    api_id: str
    propietario: str
    estado: str
    versiones: list[VersionApi] = field(default_factory=list)
    registrada_en: str = ""
    retirada_en: str | None = None
    politica_trafico: dict[str, int] | None = None  # {"max_solicitudes", "ventana_s"}


@dataclass
class Integracion:
    integracion_id: str
    tipo: str
    sistema: str
    documentacion: str
    apis: list[str]
    estado: str
    registrada_en: str


class ApiGatewayEngine:
    """API Gateway corporativo (cap. 53)."""

    def __init__(self) -> None:
        self._apis: dict[str, Api] = {}
        self._integraciones: dict[str, Integracion] = {}
        self._interacciones: list[dict[str, Any]] = []
        self._auditoria: list[dict[str, Any]] = []

    # ---------------- auditoría ALCOA+ ----------------
    def _auditar(self, accion: str, detalle: dict[str, Any], actor: str) -> None:
        self._auditoria.append({
            "evento_id": str(uuid.uuid4()),
            "accion": accion,
            "detalle": detalle,
            "actor": actor,
            "timestamp": _iso(_ahora()),
            "version_motor": GATEWAY_VERSION,
        })

    def auditoria(self) -> list[dict[str, Any]]:
        return list(self._auditoria)

    def estado_proxy(self) -> dict[str, Any]:
        return {"proxy_externo": "no_configurado",
                "gateway_en_proceso": "operativo",
                "nota": "la validación, limitación y registro son reales; el "
                        "proxy HTTP de borde se declara honestamente pendiente"}

    # ---------------- API Registry 53.7 + Lifecycle 53.9 ----------------
    def registrar_api(self, api_id: str, version: str, propietario: str,
                      documentacion: str, rutas: list[str], actor: str) -> dict[str, Any]:
        if not api_id or not version or not propietario or not actor:
            raise GatewayInvalido("api_id, version, propietario y actor son obligatorios")
        if not documentacion:
            raise GatewayInvalido("documentación obligatoria (53.7)")
        if not rutas:
            raise GatewayInvalido("cada API registra sus rutas")
        if api_id in self._apis:
            raise GatewayInvalido(f"API ya registrada: {api_id} — el catálogo nunca "
                                  "sobrescribe (53.7); publique una nueva versión")
        api = Api(api_id, propietario, "diseno",
                  [VersionApi(version, documentacion, list(rutas), _iso(_ahora()))],
                  _iso(_ahora()))
        self._apis[api_id] = api
        self._auditar("api_registrada", {"api_id": api_id, "version": version}, actor)
        return self._dto_api(api)

    def publicar_version(self, api_id: str, version: str, documentacion: str,
                         rutas: list[str], actor: str) -> dict[str, Any]:
        """Nueva versión de una API existente: exige compatibilidad (rutas
        anteriores conservadas) conforme a la política 53.9."""
        api = self._api(api_id)
        if api.estado == "retirada":
            raise GatewayInvalido(f"API retirada: {api_id} — no admite nuevas versiones")
        if any(v.version == version for v in api.versiones):
            raise GatewayInvalido(f"versión ya registrada: {api_id} v{version}")
        rutas_vigentes = set(api.versiones[-1].rutas)
        if not rutas_vigentes.issubset(set(rutas)):
            raise GatewayInvalido(
                f"versión incompatible: debe conservar las rutas vigentes "
                f"{sorted(rutas_vigentes)} (53.9 — compatibilidad)")
        api.versiones.append(VersionApi(version, documentacion, list(rutas),
                                        _iso(_ahora())))
        self._auditar("api_version_publicada", {"api_id": api_id, "version": version}, actor)
        return self._dto_api(api)

    def transicion_api(self, api_id: str, estado: str, actor: str,
                       motivo: str) -> dict[str, Any]:
        api = self._api(api_id)
        if estado not in ESTADOS_API:
            raise GatewayInvalido(f"estado debe ser uno de {ESTADOS_API}")
        if estado not in TRANSICIONES_API[api.estado]:
            raise GatewayInvalido(f"transición inválida: {api.estado} → {estado} (53.9)")
        if estado == "publicada" and not api.versiones:
            raise GatewayInvalido("sin versión registrada no puede publicarse")
        if not motivo:
            raise GatewayInvalido("motivo obligatorio en cada transición del ciclo de vida")
        api.estado = estado
        if estado == "retirada":
            api.retirada_en = _iso(_ahora())
        self._auditar("api_transicion", {"api_id": api_id, "estado": estado,
                                         "motivo": motivo}, actor)
        return self._dto_api(api)

    def apis(self, estado: str | None = None) -> list[dict[str, Any]]:
        return [self._dto_api(a) for a in self._apis.values()
                if estado is None or a.estado == estado]

    def _api(self, api_id: str) -> Api:
        api = self._apis.get(api_id)
        if api is None:
            raise GatewayInvalido(f"API no registrada: {api_id}")
        return api

    @staticmethod
    def _dto_api(a: Api) -> dict[str, Any]:
        return {"api_id": a.api_id, "propietario": a.propietario, "estado": a.estado,
                "versiones": [{"version": v.version, "documentacion": v.documentacion,
                               "rutas": v.rutas, "registrada_en": v.registrada_en}
                              for v in a.versiones],
                "version_vigente": a.versiones[-1].version if a.versiones else None,
                "registrada_en": a.registrada_en, "retirada_en": a.retirada_en,
                "politica_trafico": a.politica_trafico}

    # ---------------- Integration Manager 53.8 ----------------
    def registrar_integracion(self, integracion_id: str, tipo: str, sistema: str,
                              documentacion: str, apis: list[str],
                              actor: str) -> dict[str, Any]:
        if not integracion_id or not sistema or not actor:
            raise GatewayInvalido("integracion_id, sistema y actor son obligatorios")
        if tipo not in TIPOS_INTEGRACION:
            raise GatewayInvalido(f"tipo debe ser uno de {TIPOS_INTEGRACION}: {tipo}")
        if not documentacion:
            raise GatewayInvalido("cada integración permanece completamente "
                                  "documentada (53.8)")
        for api_id in apis:
            self._api(api_id)  # las APIs referenciadas deben existir en el catálogo
        if integracion_id in self._integraciones:
            raise GatewayInvalido(f"integración ya registrada: {integracion_id}")
        self._integraciones[integracion_id] = Integracion(
            integracion_id, tipo, sistema, documentacion, list(apis),
            "activa", _iso(_ahora()))
        self._auditar("integracion_registrada", {"integracion_id": integracion_id,
                      "tipo": tipo, "sistema": sistema}, actor)
        return self._dto_integracion(self._integraciones[integracion_id])

    def integraciones(self, tipo: str | None = None) -> list[dict[str, Any]]:
        return [self._dto_integracion(i) for i in self._integraciones.values()
                if tipo is None or i.tipo == tipo]

    @staticmethod
    def _dto_integracion(i: Integracion) -> dict[str, Any]:
        return {"integracion_id": i.integracion_id, "tipo": i.tipo, "sistema": i.sistema,
                "documentacion": i.documentacion, "apis": i.apis, "estado": i.estado,
                "registrada_en": i.registrada_en}

    # ---------------- Traffic Manager 53.11 + validación 53.6 ----------------
    def definir_politica_trafico(self, api_id: str, max_solicitudes: int,
                                 ventana_s: int, actor: str) -> dict[str, Any]:
        api = self._api(api_id)
        if max_solicitudes <= 0 or ventana_s <= 0:
            raise GatewayInvalido("max_solicitudes y ventana_s deben ser positivos")
        api.politica_trafico = {"max_solicitudes": max_solicitudes,
                                "ventana_s": ventana_s}
        self._auditar("politica_trafico", {"api_id": api_id,
                      "max_solicitudes": max_solicitudes, "ventana_s": ventana_s}, actor)
        return dict(api.politica_trafico)

    def validar_solicitud(self, api_id: str, version: str, ruta: str,
                          consumidor: str) -> dict[str, Any]:
        """53.6: TODA solicitud es validada antes de llegar al servicio.
        53.12: toda interacción permanece registrada, admitida o rechazada."""
        if not consumidor:
            raise GatewayInvalido("consumidor obligatorio")
        resultado = "admitida"
        motivo = ""
        api = self._apis.get(api_id)
        if api is None:
            resultado, motivo = "rechazada", f"API no registrada: {api_id}"
        elif api.estado != "publicada":
            resultado, motivo = "rechazada", f"API en estado '{api.estado}'"
        elif not any(v.version == version for v in api.versiones):
            resultado, motivo = "rechazada", f"versión no registrada: v{version}"
        else:
            ver = next(v for v in api.versiones if v.version == version)
            if ruta not in ver.rutas:
                resultado, motivo = "rechazada", f"ruta no publicada: {ruta}"
            elif api.politica_trafico is not None:
                limite = api.politica_trafico["max_solicitudes"]
                ventana = api.politica_trafico["ventana_s"]
                corte = _ahora() - timedelta(seconds=ventana)
                recientes = [i for i in self._interacciones
                             if i["api_id"] == api_id
                             and i["consumidor"] == consumidor
                             and i["resultado"] == "admitida"
                             and datetime.fromisoformat(i["timestamp"]) >= corte]
                if len(recientes) >= limite:
                    resultado, motivo = "limitada", \
                        f"límite {limite} solicitudes/{ventana}s excedido (53.11)"
        interaccion = {"interaccion_id": str(uuid.uuid4()), "api_id": api_id,
                       "version": version, "ruta": ruta, "consumidor": consumidor,
                       "resultado": resultado, "motivo": motivo,
                       "timestamp": _iso(_ahora())}
        self._interacciones.append(interaccion)
        self._auditar("solicitud_validada", {"api_id": api_id, "ruta": ruta,
                      "resultado": resultado, "motivo": motivo or None}, consumidor)
        return interaccion

    def interacciones(self, api_id: str | None = None,
                      consumidor: str | None = None) -> list[dict[str, Any]]:
        return [i for i in self._interacciones
                if (api_id is None or i["api_id"] == api_id)
                and (consumidor is None or i["consumidor"] == consumidor)]
