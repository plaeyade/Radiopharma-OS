"""Enterprise Governance Core (EDS cap. 46).

El EGC establece las reglas bajo las cuales opera la plataforma; NO
ejecuta procesos operativos (46.3): la gobernanza permanece
centralizada y desacoplada de los Gemelos Digitales.

- **Policy Manager (46.6)**: políticas corporativas versionadas; la
  publicación exige consistencia (46.17): las incompletas permanecen
  en revisión.
- **Rule Manager (46.7)**: reglas declarativas (ámbito, campo,
  operador, valor) con evaluación desacoplada (46.20); toda
  modificación documentada.
- **Compliance Manager (46.8)**: requisitos institucionales con
  trazabilidad (delega la evidencia regulatoria al RCAE cap. 49).
- **Architecture Manager (46.9)**: representación declarativa de
  dominios, componentes, dependencias e interfaces versionadas.
- **Governance Registry (46.10)**: registro oficial consolidado.

Auditoría 46.19 en todas las operaciones.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

EGC_VERSION = "egc-1.0.0"

ESTADOS_POLITICA = ("borrador", "revision", "publicada", "retirada")
AMBITOS_REGLA = ("procesos", "datos", "usuarios", "modelos", "documentos")
OPERADORES = ("==", "!=", "<", "<=", ">", ">=", "in", "not_in")


class GobernanzaInvalida(ValueError):
    """Política, regla o elemento de arquitectura inválido (46.17)."""


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Politica:
    """Policy Manager (46.6)."""
    politica_id: str
    version: str
    alcance: str
    vigencia_desde: str
    responsable: str
    contenido: str = ""
    estado: str = "borrador"


@dataclass
class Regla:
    """Rule Manager (46.7): regla declarativa evaluable."""
    regla_id: str
    ambito: str                     # AMBITOS_REGLA
    campo: str
    operador: str                   # OPERADORES
    valor: object
    descripcion: str = ""
    version: str = "1.0.0"
    activa: bool = True


@dataclass
class ComponenteArquitectura:
    """Architecture Manager (46.9)."""
    componente_id: str
    dominio: str
    version: str
    interfaces: list[str] = field(default_factory=list)
    dependencias: list[str] = field(default_factory=list)


class GovernanceEngine:
    """EGC: políticas, reglas, arquitectura y registro oficial."""

    def __init__(self) -> None:
        self._politicas: dict[str, list[Politica]] = {}   # versionado
        self._reglas: dict[str, Regla] = {}
        self._arquitectura: dict[str, ComponenteArquitectura] = {}
        self._auditoria: list[dict] = []

    def _auditar(self, usuario: str, accion: str, detalle: str) -> None:
        self._auditoria.append({"usuario": usuario, "accion": accion,
                                "detalle": detalle, "fecha": _ahora()})

    def auditoria(self) -> list[dict]:
        return list(self._auditoria)

    # --------------------------------------------------- políticas 46.6
    def registrar_politica(self, p: Politica, usuario: str) -> dict:
        versiones = self._politicas.setdefault(p.politica_id, [])
        if any(x.version == p.version for x in versiones):
            raise GobernanzaInvalida(
                f"versión ya registrada para {p.politica_id}: {p.version} "
                "(46.6: nunca se sobrescribe)")
        versiones.append(p)
        self._auditar(usuario, "registrar_politica",
                      f"{p.politica_id} v{p.version}")
        return {"politica_id": p.politica_id, "version": p.version,
                "estado": p.estado}

    def _vigente(self, politica_id: str) -> Politica:
        if politica_id not in self._politicas:
            raise GobernanzaInvalida(f"política inexistente: {politica_id}")
        return self._politicas[politica_id][-1]

    def publicar_politica(self, politica_id: str, usuario: str) -> dict:
        """Validación 46.17: las incompletas permanecen en revisión."""
        p = self._vigente(politica_id)
        incompletos = [c for c in ("alcance", "vigencia_desde",
                                   "responsable", "contenido")
                       if not getattr(p, c)]
        if incompletos:
            p.estado = "revision"
            self._auditar(usuario, "publicar_politica",
                          f"{politica_id} RECHAZADA: {incompletos}")
            raise GobernanzaInvalida(
                f"política incompleta {incompletos}: permanece en "
                "revisión (46.17)")
        p.estado = "publicada"
        self._auditar(usuario, "publicar_politica", politica_id)
        return {"politica_id": politica_id, "estado": "publicada"}

    def retirar_politica(self, politica_id: str, usuario: str) -> dict:
        p = self._vigente(politica_id)
        p.estado = "retirada"
        self._auditar(usuario, "retirar_politica", politica_id)
        return {"politica_id": politica_id, "estado": "retirada"}

    def politicas(self) -> list[dict]:
        return [{"politica_id": pid,
                 "version_vigente": v[-1].version,
                 "estado": v[-1].estado, "alcance": v[-1].alcance,
                 "responsable": v[-1].responsable,
                 "revisiones": [x.version for x in v]}
                for pid, v in self._politicas.items()]

    # ------------------------------------------------------- reglas 46.7
    def registrar_regla(self, r: Regla, usuario: str) -> dict:
        if r.regla_id in self._reglas:
            raise GobernanzaInvalida(
                f"regla ya registrada: {r.regla_id} — las modificaciones "
                "se versionan como regla nueva (46.7)")
        if r.ambito not in AMBITOS_REGLA:
            raise GobernanzaInvalida(f"ámbito inválido: {r.ambito}")
        if r.operador not in OPERADORES:
            raise GobernanzaInvalida(f"operador inválido: {r.operador}")
        self._reglas[r.regla_id] = r
        self._auditar(usuario, "registrar_regla", r.regla_id)
        return {"regla_id": r.regla_id}

    def desactivar_regla(self, regla_id: str, usuario: str) -> dict:
        if regla_id not in self._reglas:
            raise GobernanzaInvalida(f"regla inexistente: {regla_id}")
        self._reglas[regla_id].activa = False
        self._auditar(usuario, "desactivar_regla", regla_id)
        return {"regla_id": regla_id, "activa": False}

    def evaluar_regla(self, regla_id: str, contexto: dict) -> dict:
        """Evaluación desacoplada (46.20): la regla se aplica al
        contexto que le entrega el módulo llamante."""
        if regla_id not in self._reglas:
            raise GobernanzaInvalida(f"regla inexistente: {regla_id}")
        r = self._reglas[regla_id]
        if not r.activa:
            raise GobernanzaInvalida(f"regla desactivada: {regla_id}")
        if r.campo not in contexto:
            return {"regla_id": regla_id, "resultado": None,
                    "nota": f"campo '{r.campo}' ausente en el contexto"}
        x = contexto[r.campo]
        v = r.valor
        try:
            if r.operador == "==":
                cumple = x == v
            elif r.operador == "!=":
                cumple = x != v
            elif r.operador == "<":
                cumple = x < v
            elif r.operador == "<=":
                cumple = x <= v
            elif r.operador == ">":
                cumple = x > v
            elif r.operador == ">=":
                cumple = x >= v
            elif r.operador == "in":
                cumple = x in v
            else:  # not_in
                cumple = x not in v
        except TypeError:
            raise GobernanzaInvalida(
                f"contexto no comparable con el valor de la regla: {x!r}")
        return {"regla_id": regla_id, "ambito": r.ambito,
                "campo": r.campo, "valor_contexto": x,
                "resultado": bool(cumple),
                "version_regla": r.version}

    def reglas(self) -> list[dict]:
        return [{"regla_id": r.regla_id, "ambito": r.ambito,
                 "campo": r.campo, "operador": r.operador,
                 "valor": r.valor, "version": r.version,
                 "activa": r.activa} for r in self._reglas.values()]

    # ------------------------------------------------ arquitectura 46.9
    def registrar_componente(self, c: ComponenteArquitectura,
                             usuario: str) -> dict:
        if c.componente_id in self._arquitectura:
            raise GobernanzaInvalida(
                f"componente ya registrado: {c.componente_id}")
        if not c.dominio or not c.version:
            raise GobernanzaInvalida(
                "dominio y versión obligatorios (46.9)")
        self._arquitectura[c.componente_id] = c
        self._auditar(usuario, "registrar_componente", c.componente_id)
        return {"componente_id": c.componente_id}

    def arquitectura(self) -> list[dict]:
        return [{"componente_id": c.componente_id, "dominio": c.dominio,
                 "version": c.version, "interfaces": list(c.interfaces),
                 "dependencias": list(c.dependencias)}
                for c in self._arquitectura.values()]

    def dependencias_de(self, componente_id: str) -> dict:
        if componente_id not in self._arquitectura:
            raise GobernanzaInvalida(
                f"componente inexistente: {componente_id}")
        c = self._arquitectura[componente_id]
        desconocidas = [d for d in c.dependencias
                        if d not in self._arquitectura]
        return {"componente_id": componente_id,
                "dependencias": list(c.dependencias),
                "dependencias_no_registradas": desconocidas}

    # ------------------------------------------- registro oficial 46.10
    def registro_oficial(self) -> dict:
        return {"fecha": _ahora(),
                "n_politicas": len(self._politicas),
                "politicas_publicadas": sum(
                    1 for v in self._politicas.values()
                    if v[-1].estado == "publicada"),
                "n_reglas": len(self._reglas),
                "reglas_activas": sum(1 for r in self._reglas.values()
                                      if r.activa),
                "n_componentes": len(self._arquitectura),
                "version_motor": EGC_VERSION}
