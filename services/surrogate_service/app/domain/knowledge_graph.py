"""Knowledge Graph & Semantic Intelligence Engine (EDS cap. 44).

El KGSIE representa conocimiento y sus relaciones; NO sustituye las
bases transaccionales, el Data Lake ni los sistemas documentales
(44.3): conecta conceptualmente la información.

- **Ontology Manager (44.6)**: tipos de entidad y de relación
  versionados; nunca se sobrescribe una versión.
- **Entity Registry (44.7)**: identificador semántico único por
  entidad, con gestión temporal 44.12.
- **Relationship Manager (44.8)**: relaciones trazables entre
  entidades registradas.
- **Semantic Query Engine (44.9)**: consultas por relación y caminos
  multi-dominio (BFS documentado).
- **Reasoning Engine (44.10)**: inferencias por transitividad de
  jerarquías (`es_un`) y reglas declaradas; TODA inferencia queda
  documentada con su cadena de justificación — nunca se afirma una
  inferencia sin mostrar de dónde sale.
- **Knowledge Synchronizer (44.11)**: incorporación controlada y
  versionada de entidades/relaciones desde los Gemelos.

Auditoría completa (44.21).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

KGSIE_VERSION = "kgsie-1.0.0"

RELACIONES_BASE = ("produce", "contiene", "utiliza", "depende_de",
                   "pertenece_a", "deriva_de", "valida", "calibra",
                   "es_un", "documenta")


class GrafoInvalido(ValueError):
    """Entidad, relación, ontología o consulta inválida (cap. 44)."""


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Entidad:
    """Entity Registry (44.7)."""
    entidad_id: str                 # identificador semántico único
    tipo: str
    atributos: dict = field(default_factory=dict)
    origen: str = ""                # gemelo/servicio del que proviene
    creada: str = ""


@dataclass
class Relacion:
    """Relationship Manager (44.8)."""
    origen_id: str
    tipo: str
    destino_id: str
    evidencia: str = ""             # referencia al registro que la justifica
    creada: str = ""


class KnowledgeGraph:
    """Grafo semántico corporativo con razonamiento documentado."""

    def __init__(self) -> None:
        self._ontologia: dict[str, dict] = {}     # nombre -> versiones
        self._entidades: dict[str, Entidad] = {}
        self._relaciones: list[Relacion] = []
        self._inferencias: list[dict] = []
        self._auditoria: list[dict] = []

    def _auditar(self, usuario: str, accion: str, detalle: str) -> None:
        self._auditoria.append({"usuario": usuario, "accion": accion,
                                "detalle": detalle, "fecha": _ahora()})

    def auditoria(self) -> list[dict]:
        return list(self._auditoria)

    # --------------------------------------------------- ontología 44.6
    def registrar_tipo(self, nombre: str, version: str, definicion: dict,
                       usuario: str) -> dict:
        entrada = self._ontologia.setdefault(nombre, {"versiones": []})
        if any(v["version"] == version for v in entrada["versiones"]):
            raise GrafoInvalido(
                f"versión ontológica duplicada: {nombre} v{version} "
                "(44.6: nunca se sobrescribe)")
        entrada["versiones"].append({"version": version,
                                     "definicion": dict(definicion),
                                     "fecha": _ahora()})
        self._auditar(usuario, "registrar_tipo", f"{nombre} v{version}")
        return {"tipo": nombre, "version": version}

    def ontologia(self) -> dict:
        return {n: {"version_vigente": e["versiones"][-1]["version"],
                    "n_versiones": len(e["versiones"])}
                for n, e in self._ontologia.items()}

    # --------------------------------------------------- entidades 44.7
    def registrar_entidad(self, e: Entidad, usuario: str) -> dict:
        if e.entidad_id in self._entidades:
            raise GrafoInvalido(
                f"entidad ya registrada: {e.entidad_id} — la evolución "
                "se registra como versión nueva (44.12)")
        if e.tipo in self._ontologia or not self._ontologia:
            pass
        if e.tipo not in self._ontologia and self._ontologia:
            raise GrafoInvalido(
                f"tipo no definido en la ontología vigente: {e.tipo}")
        e.creada = e.creada or _ahora()
        self._entidades[e.entidad_id] = e
        self._auditar(usuario, "registrar_entidad", e.entidad_id)
        return {"entidad_id": e.entidad_id}

    def entidades(self, tipo: str | None = None) -> list[dict]:
        return [{"entidad_id": e.entidad_id, "tipo": e.tipo,
                 "atributos": dict(e.atributos), "origen": e.origen,
                 "creada": e.creada}
                for e in self._entidades.values()
                if tipo is None or e.tipo == tipo]

    # -------------------------------------------------- relaciones 44.8
    def registrar_relacion(self, r: Relacion, usuario: str) -> dict:
        for eid in (r.origen_id, r.destino_id):
            if eid not in self._entidades:
                raise GrafoInvalido(f"entidad inexistente: {eid}")
        if any(x.origen_id == r.origen_id and x.tipo == r.tipo
               and x.destino_id == r.destino_id for x in self._relaciones):
            raise GrafoInvalido(
                f"relación duplicada: {r.origen_id}-[{r.tipo}]->"
                f"{r.destino_id}")
        r.creada = r.creada or _ahora()
        self._relaciones.append(r)
        self._auditar(usuario, "registrar_relacion",
                      f"{r.origen_id}-[{r.tipo}]->{r.destino_id}")
        return {"origen": r.origen_id, "tipo": r.tipo,
                "destino": r.destino_id}

    def relaciones(self, entidad_id: str | None = None) -> list[dict]:
        return [{"origen": r.origen_id, "tipo": r.tipo,
                 "destino": r.destino_id, "evidencia": r.evidencia,
                 "creada": r.creada}
                for r in self._relaciones
                if entidad_id is None or entidad_id in
                (r.origen_id, r.destino_id)]

    # -------------------------------------------- consulta semántica 44.9
    def consultar(self, origen_id: str, tipo_relacion: str | None = None,
                  direccion: str = "saliente") -> list[dict]:
        """Consulta por relación (44.9)."""
        if origen_id not in self._entidades:
            raise GrafoInvalido(f"entidad inexistente: {origen_id}")
        out = []
        for r in self._relaciones:
            if tipo_relacion and r.tipo != tipo_relacion:
                continue
            if direccion == "saliente" and r.origen_id == origen_id:
                out.append({"tipo": r.tipo, "entidad": r.destino_id,
                            "evidencia": r.evidencia})
            elif direccion == "entrante" and r.destino_id == origen_id:
                out.append({"tipo": r.tipo, "entidad": r.origen_id,
                            "evidencia": r.evidencia})
        return out

    def camino(self, origen_id: str, destino_id: str,
               max_saltos: int = 6) -> dict:
        """Camino multi-dominio (44.9): BFS documentado."""
        for eid in (origen_id, destino_id):
            if eid not in self._entidades:
                raise GrafoInvalido(f"entidad inexistente: {eid}")
        ady: dict[str, list[tuple[str, str]]] = {}
        for r in self._relaciones:
            ady.setdefault(r.origen_id, []).append((r.tipo, r.destino_id))
        cola = deque([(origen_id, [])])
        visitados = {origen_id}
        while cola:
            nodo, ruta = cola.popleft()
            if nodo == destino_id:
                return {"existe": True, "saltos": len(ruta),
                        "camino": ruta}
            if len(ruta) >= max_saltos:
                continue
            for tipo, sig in ady.get(nodo, []):
                if sig not in visitados:
                    visitados.add(sig)
                    cola.append((sig, ruta + [
                        {"desde": nodo, "relacion": tipo, "hasta": sig}]))
        return {"existe": False,
                "nota": f"sin camino ≤ {max_saltos} saltos (honesto)"}

    # ------------------------------------------------- razonamiento 44.10
    def inferir_jerarquia(self, entidad_id: str) -> dict:
        """Transitividad de `es_un` con cadena de justificación (44.10).

        Toda inferencia documenta EXACTAMENTE de qué relaciones sale."""
        if entidad_id not in self._entidades:
            raise GrafoInvalido(f"entidad inexistente: {entidad_id}")
        ancestros = []
        cadena = []
        actual = entidad_id
        visitados = {actual}
        while True:
            paso = next((r for r in self._relaciones
                         if r.origen_id == actual and r.tipo == "es_un"),
                        None)
            if paso is None or paso.destino_id in visitados:
                break
            visitados.add(paso.destino_id)
            cadena.append({"desde": actual, "hasta": paso.destino_id,
                           "evidencia": paso.evidencia})
            ancestros.append(paso.destino_id)
            actual = paso.destino_id
        inferencia = {"entidad": entidad_id, "es_un": ancestros,
                      "justificacion": cadena,
                      "metodo": "transitividad de es_un (44.10): cada "
                                "paso muestra su relación y evidencia",
                      "fecha": _ahora()}
        self._inferencias.append(inferencia)
        self._auditar("motor", "inferir_jerarquia", entidad_id)
        return inferencia

    def inferencias(self) -> list[dict]:
        return list(self._inferencias)

    # ----------------------------------------------- sincronización 44.11
    def sincronizar(self, paquete: dict, usuario: str) -> dict:
        """Incorporación controlada y versionada desde un Gemelo (44.11).

        `paquete`: {"origen": str, "version": str,
                    "entidades": [...], "relaciones": [...]}"""
        for campo in ("origen", "version"):
            if campo not in paquete:
                raise GrafoInvalido(
                    f"paquete de sincronización sin '{campo}' (44.11)")
        n_ent, n_rel = 0, 0
        for e in paquete.get("entidades", []):
            if e["entidad_id"] not in self._entidades:
                self.registrar_entidad(Entidad(
                    entidad_id=e["entidad_id"], tipo=e["tipo"],
                    atributos=e.get("atributos", {}),
                    origen=paquete["origen"]), usuario)
                n_ent += 1
        for r in paquete.get("relaciones", []):
            try:
                self.registrar_relacion(Relacion(
                    origen_id=r["origen"], tipo=r["tipo"],
                    destino_id=r["destino"],
                    evidencia=f"sync:{paquete['origen']} v"
                              f"{paquete['version']}"), usuario)
                n_rel += 1
            except GrafoInvalido:
                pass   # duplicadas: no se reincorporan
        self._auditar(usuario, "sincronizar",
                      f"{paquete['origen']} v{paquete['version']}: "
                      f"+{n_ent} entidades, +{n_rel} relaciones")
        return {"origen": paquete["origen"], "version": paquete["version"],
                "entidades_incorporadas": n_ent,
                "relaciones_incorporadas": n_rel}
