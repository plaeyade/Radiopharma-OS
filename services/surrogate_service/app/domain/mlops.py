"""MLOps & AI Lifecycle Management Engine (EDS cap. 42).

El MALME administra el ciclo de vida de los modelos IA con proceso
reproducible, auditable y trazable; no desarrolla nuevos algoritmos
(42.3). Complementa al Model Registry del cap. 20 (que nunca
sobrescribe) con el ciclo de vida formal.

- **Dataset Manager (42.6)**: datasets versionados (origen, fecha,
  estado); nunca se sobrescribe una versión.
- **Experiment Tracker (42.7)**: cada entrenamiento registra modelo,
  algoritmo, hiperparámetros, resultados y dataset exacto — base de la
  reproducibilidad (42.2).
- **Model Registry (42.8)**: estados del modelo; SÓLO modelos
  aprobados pueden desplegarse.
- **Deployment Manager (42.9)**: despliegues, reversiones y retiros
  documentados.
- **Monitoring Engine (42.10)**: métricas de desempeño asociadas a
  cada versión desplegada.
- **Governance Manager (42.11)**: aprobaciones con responsable;
  validación previa al despliegue 42.20 — los modelos no validados
  permanecen en revisión.

Auditoría completa (42.12/42.24).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

MALME_VERSION = "malme-1.0.0"

ESTADOS_MODELO = ("entrenado", "en_revision", "aprobado", "desplegado",
                  "revertido", "retirado")


class MlopsInvalido(ValueError):
    """Dataset, experimento, modelo o despliegue inválido (42.20)."""


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Dataset:
    """Dataset Manager (42.6)."""
    dataset_id: str
    origen: str
    version: str
    fecha: str
    estado: str = "activo"          # activo/retirado
    hash_sha256: str = ""
    n_registros: int | None = None


@dataclass
class Experimento:
    """Experiment Tracker (42.7)."""
    experimento_id: str
    modelo_id: str
    algoritmo: str
    hiperparametros: dict
    dataset_id: str
    dataset_version: str            # conjunto EXACTO de datos (42.7)
    metricas: dict
    fecha: str = ""


class MlopsEngine:
    """MALME: ciclo de vida completo, reproducible y auditado."""

    def __init__(self) -> None:
        self._datasets: dict[str, list[Dataset]] = {}
        self._experimentos: dict[str, Experimento] = {}
        self._modelos: dict[str, dict] = {}
        self._despliegues: list[dict] = []
        self._metricas_monitor: list[dict] = []
        self._auditoria: list[dict] = []

    def _auditar(self, usuario: str, accion: str, detalle: str) -> None:
        self._auditoria.append({"usuario": usuario, "accion": accion,
                                "detalle": detalle, "fecha": _ahora()})

    def auditoria(self) -> list[dict]:
        return list(self._auditoria)

    # ---------------------------------------------------- datasets 42.6
    def registrar_dataset(self, ds: Dataset, usuario: str) -> dict:
        versiones = self._datasets.setdefault(ds.dataset_id, [])
        if any(d.version == ds.version for d in versiones):
            raise MlopsInvalido(
                f"versión de dataset duplicada: {ds.dataset_id} "
                f"v{ds.version} (42.6: nunca se sobrescribe)")
        if not ds.origen or not ds.fecha:
            raise MlopsInvalido("origen y fecha obligatorios (42.6)")
        versiones.append(ds)
        self._auditar(usuario, "registrar_dataset",
                      f"{ds.dataset_id} v{ds.version}")
        return {"dataset_id": ds.dataset_id, "version": ds.version}

    def datasets(self) -> list[dict]:
        return [{"dataset_id": did,
                 "version_vigente": v[-1].version,
                 "origen": v[-1].origen, "estado": v[-1].estado,
                 "n_registros": v[-1].n_registros,
                 "versiones": [d.version for d in v]}
                for did, v in self._datasets.items()]

    # ------------------------------------------------ experimentos 42.7
    def registrar_experimento(self, exp: Experimento, usuario: str) -> dict:
        if exp.experimento_id in self._experimentos:
            raise MlopsInvalido(
                f"experimento duplicado: {exp.experimento_id}")
        versiones = self._datasets.get(exp.dataset_id, [])
        if not any(d.version == exp.dataset_version for d in versiones):
            raise MlopsInvalido(
                f"dataset {exp.dataset_id} v{exp.dataset_version} no "
                "registrado: la reproducibilidad exige el conjunto "
                "exacto de datos (42.7)")
        exp.fecha = exp.fecha or _ahora()
        self._experimentos[exp.experimento_id] = exp
        self._auditar(usuario, "registrar_experimento",
                      f"{exp.experimento_id} ({exp.modelo_id})")
        return {"experimento_id": exp.experimento_id}

    def experimentos(self, modelo_id: str | None = None) -> list[dict]:
        return [{"experimento_id": e.experimento_id,
                 "modelo_id": e.modelo_id, "algoritmo": e.algoritmo,
                 "hiperparametros": dict(e.hiperparametros),
                 "dataset_id": e.dataset_id,
                 "dataset_version": e.dataset_version,
                 "metricas": dict(e.metricas), "fecha": e.fecha}
                for e in self._experimentos.values()
                if modelo_id is None or e.modelo_id == modelo_id]

    # ------------------------------------------------- modelos 42.8/42.20
    def registrar_modelo(self, modelo_id: str, version: str,
                         experimento_id: str, usuario: str) -> dict:
        if modelo_id in self._modelos:
            raise MlopsInvalido(f"modelo ya registrado: {modelo_id}")
        if experimento_id not in self._experimentos:
            raise MlopsInvalido(
                f"experimento inexistente: {experimento_id} — todo "
                "modelo nace de un entrenamiento registrado (42.7)")
        self._modelos[modelo_id] = {
            "modelo_id": modelo_id, "version": version,
            "experimento_id": experimento_id, "estado": "entrenado",
            "documentacion": "", "aprobaciones": [],
            "historial": [{"estado": "entrenado", "fecha": _ahora(),
                           "usuario": usuario}]}
        self._auditar(usuario, "registrar_modelo", modelo_id)
        return {"modelo_id": modelo_id, "estado": "entrenado"}

    def _modelo(self, modelo_id: str) -> dict:
        if modelo_id not in self._modelos:
            raise MlopsInvalido(f"modelo inexistente: {modelo_id}")
        return self._modelos[modelo_id]

    def _transicion(self, modelo_id: str, estado: str,
                    usuario: str) -> dict:
        m = self._modelo(modelo_id)
        m["estado"] = estado
        m["historial"].append({"estado": estado, "fecha": _ahora(),
                               "usuario": usuario})
        self._auditar(usuario, f"modelo:{estado}", modelo_id)
        return {"modelo_id": modelo_id, "estado": estado}

    def aprobar_modelo(self, modelo_id: str, responsable: str,
                       documentacion: str, usuario: str) -> dict:
        """Governance 42.11 + validación 42.20: documentación y
        responsable obligatorios; si falta, permanece en revisión."""
        m = self._modelo(modelo_id)
        if not responsable or not documentacion:
            m["estado"] = "en_revision"
            self._auditar(usuario, "aprobar_modelo",
                          f"{modelo_id} RECHAZADO: sin "
                          f"{'responsable' if not responsable else ''}"
                          f"{' documentación' if not documentacion else ''}")
            raise MlopsInvalido(
                "aprobación exige responsable y documentación (42.20): "
                "el modelo permanece en revisión")
        m["documentacion"] = documentacion
        m["aprobaciones"].append({"responsable": responsable,
                                  "fecha": _ahora()})
        return self._transicion(modelo_id, "aprobado", usuario)

    # ------------------------------------------------- despliegues 42.9
    def desplegar(self, modelo_id: str, entorno: str,
                  usuario: str) -> dict:
        """SÓLO modelos aprobados pueden desplegarse (42.8)."""
        m = self._modelo(modelo_id)
        if m["estado"] != "aprobado":
            raise MlopsInvalido(
                f"modelo en estado '{m['estado']}': sólo modelos "
                "aprobados pueden desplegarse (42.8)")
        self._transicion(modelo_id, "desplegado", usuario)
        reg = {"modelo_id": modelo_id, "entorno": entorno,
               "accion": "despliegue", "fecha": _ahora(),
               "usuario": usuario}
        self._despliegues.append(reg)
        return reg

    def revertir(self, modelo_id: str, motivo: str, usuario: str) -> dict:
        m = self._modelo(modelo_id)
        if m["estado"] != "desplegado":
            raise MlopsInvalido("sólo se revierte un modelo desplegado")
        self._despliegues.append({"modelo_id": modelo_id,
                                  "accion": "reversion", "motivo": motivo,
                                  "fecha": _ahora(), "usuario": usuario})
        return self._transicion(modelo_id, "revertido", usuario)

    def retirar(self, modelo_id: str, usuario: str) -> dict:
        return self._transicion(modelo_id, "retirado", usuario)

    def despliegues(self) -> list[dict]:
        return list(self._despliegues)

    def modelos(self) -> list[dict]:
        return [{"modelo_id": m["modelo_id"], "version": m["version"],
                 "estado": m["estado"],
                 "experimento_id": m["experimento_id"],
                 "n_historial": len(m["historial"])}
                for m in self._modelos.values()]

    def historial_modelo(self, modelo_id: str) -> list[dict]:
        return list(self._modelo(modelo_id)["historial"])

    # -------------------------------------------------- monitoreo 42.10
    def registrar_metrica(self, modelo_id: str, metrica: str,
                          valor: float, usuario: str) -> dict:
        """Monitoring Engine 42.10: métricas asociadas a la versión."""
        m = self._modelo(modelo_id)
        if not metrica:
            raise MlopsInvalido("métrica obligatoria")
        reg = {"modelo_id": modelo_id, "version": m["version"],
               "metrica": metrica, "valor": valor, "fecha": _ahora()}
        self._metricas_monitor.append(reg)
        self._auditar(usuario, "metrica_monitor",
                      f"{modelo_id}/{metrica}={valor}")
        return reg

    def metricas(self, modelo_id: str) -> list[dict]:
        self._modelo(modelo_id)
        return [m for m in self._metricas_monitor
                if m["modelo_id"] == modelo_id]
