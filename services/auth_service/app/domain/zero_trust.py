"""Cybersecurity & Zero Trust Engine (EDS cap. 48).

Zero Trust: ninguna identidad, dispositivo, aplicación o servicio
recibe confianza implícita (48.1). Toda solicitud debe ser autenticada,
autorizada, validada y registrada antes de acceder a un recurso.

- **Zero Trust Policy Manager (48.6)**: políticas versionadas —
  recursos protegidos, condiciones, restricciones; nunca se
  sobrescribe una versión.
- **Security Event Manager (48.7)**: centraliza eventos de seguridad
  con gestión temporal completa 48.12 (fecha, origen, destino,
  resultado).
- **Threat Detection Engine (48.8)**: reglas deterministas
  documentadas sobre los eventos reales (intentos fallidos repetidos,
  accesos denegados); TODA alerta muestra los eventos que la
  dispararon — nunca una alerta sin evidencia.
- **Network Security Manager (48.9)**: segmentación lógica
  configurable; la verificación de acceso entre zonas es
  determinista: denegado salvo regla explícita (default-deny).
- **Endpoint Security Manager (48.10)**: dispositivos con identidad,
  estado y cumplimiento; sólo endpoints conformes pasan la evaluación
  de políticas.
- **Incident Response Manager (48.11)**: expedientes independientes de
  incidente, vinculados a las alertas que los originaron.

Auditoría completa (48.21).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

CZTE_VERSION = "czte-1.0.0"

TIPOS_EVENTO = ("autenticacion", "acceso", "intento_fallido",
                "cambio_configuracion", "evento_critico")

SEVERIDADES_INCIDENTE = ("critica", "alta", "media", "baja")
ESTADOS_INCIDENTE = ("abierto", "contenido", "erradicado", "cerrado")


class SeguridadInvalida(ValueError):
    """Política, evento, dispositivo o incidente inválido (cap. 48)."""


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PoliticaZeroTrust:
    """Zero Trust Policy Manager (48.6)."""
    politica_id: str
    version: str
    recursos: list[str]             # patrones de recurso protegido
    roles_permitidos: list[str]
    requiere_endpoint_conforme: bool = True
    descripcion: str = ""


@dataclass
class Endpoint:
    """Endpoint Security Manager (48.10)."""
    endpoint_id: str
    identidad: str                  # usuario/servicio asociado
    estado: str = "registrado"      # registrado/conforme/no_conforme/
                                    # bloqueado
    cumplimiento: dict = field(default_factory=dict)


class ZeroTrustEngine:
    """CZTE: políticas, eventos, detección documentada, incidentes."""

    def __init__(self, umbral_fallidos: int = 3,
                 ventana_min: float = 10.0) -> None:
        self._politicas: dict[str, list[PoliticaZeroTrust]] = {}
        self._eventos: list[dict] = []
        self._alertas: list[dict] = []
        self._segmentos: dict[str, list[str]] = {}   # zona -> zonas ok
        self._endpoints: dict[str, Endpoint] = {}
        self._incidentes: dict[str, dict] = {}
        self._umbral_fallidos = umbral_fallidos
        self._ventana = timedelta(minutes=ventana_min)
        self._auditoria: list[dict] = []

    def _auditar(self, usuario: str, accion: str, detalle: str) -> None:
        self._auditoria.append({"usuario": usuario, "accion": accion,
                                "detalle": detalle, "fecha": _ahora()})

    def auditoria(self) -> list[dict]:
        return list(self._auditoria)

    # -------------------------------------------------- políticas 48.6
    def registrar_politica(self, p: PoliticaZeroTrust,
                           usuario: str) -> dict:
        versiones = self._politicas.setdefault(p.politica_id, [])
        if any(x.version == p.version for x in versiones):
            raise SeguridadInvalida(
                f"versión duplicada: {p.politica_id} v{p.version} "
                "(48.6: nunca se sobrescribe)")
        if not p.recursos or not p.roles_permitidos:
            raise SeguridadInvalida(
                "recursos y roles_permitidos obligatorios (48.6)")
        versiones.append(p)
        self._auditar(usuario, "registrar_politica",
                      f"{p.politica_id} v{p.version}")
        return {"politica_id": p.politica_id, "version": p.version}

    def politicas(self) -> list[dict]:
        return [{"politica_id": pid, "version_vigente": v[-1].version,
                 "recursos": list(v[-1].recursos),
                 "roles_permitidos": list(v[-1].roles_permitidos),
                 "requiere_endpoint_conforme":
                     v[-1].requiere_endpoint_conforme,
                 "revisiones": [x.version for x in v]}
                for pid, v in self._politicas.items()]

    # --------------------------------------------------- endpoints 48.10
    def registrar_endpoint(self, ep: Endpoint, usuario: str) -> dict:
        if ep.endpoint_id in self._endpoints:
            raise SeguridadInvalida(
                f"endpoint ya registrado: {ep.endpoint_id}")
        self._endpoints[ep.endpoint_id] = ep
        self._auditar(usuario, "registrar_endpoint", ep.endpoint_id)
        return {"endpoint_id": ep.endpoint_id}

    def marcar_endpoint(self, endpoint_id: str, estado: str,
                        usuario: str) -> dict:
        if endpoint_id not in self._endpoints:
            raise SeguridadInvalida(f"endpoint inexistente: {endpoint_id}")
        if estado not in ("registrado", "conforme", "no_conforme",
                          "bloqueado"):
            raise SeguridadInvalida(f"estado inválido: {estado}")
        self._endpoints[endpoint_id].estado = estado
        self._auditar(usuario, "marcar_endpoint",
                      f"{endpoint_id} -> {estado}")
        return {"endpoint_id": endpoint_id, "estado": estado}

    # --------------------------------------- verificación Zero Trust 48.4
    def verificar_acceso(self, identidad: str, rol: str, recurso: str,
                         endpoint_id: str, usuario: str = "sistema"
                         ) -> dict:
        """Toda solicitud: autenticada (identidad presente), autorizada
        (política vigente), validada (endpoint), REGISTRADA (48.1/48.7).

        Default-deny: sin política que cubra el recurso, acceso
        DENEGADO."""
        decision = {"identidad": identidad, "recurso": recurso,
                    "permitido": False, "motivos": []}
        if not identidad:
            decision["motivos"].append("sin identidad autenticada")
        politica = None
        for versiones in self._politicas.values():
            p = versiones[-1]
            if any(recurso.startswith(r.rstrip("*"))
                   for r in p.recursos):
                politica = p
                break
        if politica is None:
            decision["motivos"].append(
                "sin política vigente para el recurso: denegado por "
                "defecto (Zero Trust)")
        else:
            if rol not in politica.roles_permitidos:
                decision["motivos"].append(
                    f"rol '{rol}' no permitido por "
                    f"{politica.politica_id}")
            if politica.requiere_endpoint_conforme:
                ep = self._endpoints.get(endpoint_id)
                if ep is None or ep.estado != "conforme":
                    decision["motivos"].append(
                        "endpoint no conforme o no registrado (48.10)")
        if identidad and not decision["motivos"]:
            decision["permitido"] = True
        # registro de TODA solicitud (48.1)
        self.registrar_evento("acceso", identidad or "anonimo", recurso,
                              "permitido" if decision["permitido"]
                              else "denegado", usuario)
        decision["politica_aplicada"] = (politica.politica_id
                                         if politica else None)
        return decision

    # ------------------------------------------------------ eventos 48.7
    def registrar_evento(self, tipo: str, origen: str, destino: str,
                         resultado: str, usuario: str) -> dict:
        if tipo not in TIPOS_EVENTO:
            raise SeguridadInvalida(f"tipo de evento inválido: {tipo}")
        ev = {"tipo": tipo, "origen": origen, "destino": destino,
              "resultado": resultado, "fecha": _ahora()}   # 48.12
        self._eventos.append(ev)
        self._auditar(usuario, "evento_seguridad",
                      f"{tipo}:{origen}->{destino}:{resultado}")
        self._detectar(ev)
        return ev

    def eventos(self, tipo: str | None = None) -> list[dict]:
        return [e for e in self._eventos
                if tipo is None or e["tipo"] == tipo]

    # --------------------------------------------------- detección 48.8
    def _detectar(self, ev: dict) -> None:
        """Reglas deterministas documentadas sobre eventos reales."""
        if ev["tipo"] != "intento_fallido":
            return
        ahora = datetime.fromisoformat(ev["fecha"])
        recientes = [e for e in self._eventos
                     if e["tipo"] == "intento_fallido"
                     and e["origen"] == ev["origen"]
                     and ahora - datetime.fromisoformat(e["fecha"])
                     <= self._ventana]
        if len(recientes) >= self._umbral_fallidos:
            ya = any(a["tipo_alerta"] == "intentos_fallidos_repetidos"
                     and a["origen"] == ev["origen"]
                     for a in self._alertas)
            if not ya:
                self._alertas.append({
                    "alerta_id": f"alert-{len(self._alertas) + 1:04d}",
                    "tipo_alerta": "intentos_fallidos_repetidos",
                    "origen": ev["origen"],
                    "regla": f">= {self._umbral_fallidos} intentos "
                             f"fallidos en {self._ventana}",
                    "eventos_disparadores": [e["fecha"]
                                             for e in recientes],
                    "fecha": _ahora(),
                    "nota": "alerta generada SOLO sobre eventos reales "
                            "registrados (48.8)"})

    def alertas(self) -> list[dict]:
        return list(self._alertas)

    # ------------------------------------------------------ red 48.9
    def definir_segmento(self, zona: str, permitidas: list[str],
                         usuario: str) -> dict:
        """Segmentación lógica (48.9): zonas alcanzables desde `zona`."""
        self._segmentos[zona] = list(permitidas)
        self._auditar(usuario, "definir_segmento", zona)
        return {"zona": zona, "permitidas": list(permitidas)}

    def acceso_red(self, zona_origen: str, zona_destino: str) -> dict:
        """Default-deny: sin regla explícita, tráfico denegado."""
        permitidas = self._segmentos.get(zona_origen, [])
        permitido = zona_destino in permitidas
        return {"origen": zona_origen, "destino": zona_destino,
                "permitido": permitido,
                "motivo": ("regla explícita de segmentación"
                           if permitido else
                           "sin regla explícita: denegado por defecto")}

    # --------------------------------------------------- incidentes 48.11
    def abrir_incidente(self, incidente_id: str, severidad: str,
                        descripcion: str, alerta_id: str | None,
                        usuario: str) -> dict:
        if incidente_id in self._incidentes:
            raise SeguridadInvalida(
                f"incidente ya registrado: {incidente_id}")
        if severidad not in SEVERIDADES_INCIDENTE:
            raise SeguridadInvalida(f"severidad inválida: {severidad}")
        if alerta_id and not any(a["alerta_id"] == alerta_id
                                 for a in self._alertas):
            raise SeguridadInvalida(
                f"alerta inexistente: {alerta_id} — el expediente se "
                "vincula a evidencia real (48.11)")
        self._incidentes[incidente_id] = {
            "incidente_id": incidente_id, "severidad": severidad,
            "descripcion": descripcion, "alerta_id": alerta_id,
            "estado": "abierto", "apertura": _ahora(),
            "acciones": [], "cierre": None}
        self._auditar(usuario, "abrir_incidente", incidente_id)
        return {"incidente_id": incidente_id, "estado": "abierto"}

    def accion_incidente(self, incidente_id: str, accion: str,
                         usuario: str,
                         nuevo_estado: str | None = None) -> dict:
        inc = self._incidentes.get(incidente_id)
        if inc is None:
            raise SeguridadInvalida(f"incidente inexistente: "
                                    f"{incidente_id}")
        if nuevo_estado is not None:
            if nuevo_estado not in ESTADOS_INCIDENTE:
                raise SeguridadInvalida(f"estado inválido: {nuevo_estado}")
            inc["estado"] = nuevo_estado
            if nuevo_estado == "cerrado":
                inc["cierre"] = _ahora()
        inc["acciones"].append({"accion": accion, "usuario": usuario,
                                "fecha": _ahora()})
        self._auditar(usuario, "accion_incidente",
                      f"{incidente_id}: {accion}")
        return {"incidente_id": incidente_id, "estado": inc["estado"]}

    def incidentes(self) -> list[dict]:
        return list(self._incidentes.values())
