"""EDS cap. 54 — Data Lakehouse & Analytics Platform.

Data Ingestion Manager 54.6 (incorporación por lotes o flujos con origen
obligatorio — NUNCA se inventan datos), Metadata Catalog 54.8 (cada
conjunto de datos registra identificador, propietario, dominio, versión,
calidad y clasificación — completamente versionado, nunca sobrescrito),
Data Governance Manager 54.9 (políticas de propiedad/acceso/clasificación/
retención/calidad versionadas), Data Quality Engine 54.10 (integridad,
consistencia, completitud, unicidad y actualidad calculadas sobre los
registros REALES ingeridos — nunca declaradas sin datos) y gestión
temporal 54.12 (creación, actualización, vigencia, versión de cada
conjunto). La plataforma analítica permanece desacoplada de las bases
operacionales (54.11).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

LAKEHOUSE_VERSION = "1.0.0"
DOMINIOS = ("physics", "process", "qc", "operational", "facility", "economic",
            "inteligencia", "clinico")
CLASIFICACIONES = ("publico", "interno", "confidencial", "regulado")
MODOS_INGESTA = ("lotes", "flujo")
TIPOS_POLITICA = ("propiedad", "acceso", "clasificacion", "retencion", "calidad")
CAMPOS_CALIDAD = ("integridad", "consistencia", "completitud", "unicidad", "actualidad")


class LakehouseInvalido(ValueError):
    pass


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class VersionDataset:
    version: int
    esquema: list[str]
    clasificacion: str
    vigencia_desde: str
    registrada_en: str


@dataclass
class Dataset:
    dataset_id: str
    propietario: str
    dominio: str
    versiones: list[VersionDataset] = field(default_factory=list)
    registros: list[dict[str, Any]] = field(default_factory=list)
    creado_en: str = ""


@dataclass
class VersionPolitica:
    version: int
    tipo: str
    contenido: str
    responsable: str
    registrada_en: str


class LakehouseEngine:
    """Data Lakehouse analítico gobernado por metadatos (cap. 54)."""

    def __init__(self) -> None:
        self._datasets: dict[str, Dataset] = {}
        self._politicas: dict[str, list[VersionPolitica]] = {}
        self._evaluaciones: list[dict[str, Any]] = []
        self._auditoria: list[dict[str, Any]] = []

    # ---------------- auditoría ALCOA+ (54.20) ----------------
    def _auditar(self, accion: str, detalle: dict[str, Any], actor: str) -> None:
        self._auditoria.append({
            "evento_id": str(uuid.uuid4()),
            "accion": accion,
            "detalle": detalle,
            "actor": actor,
            "timestamp": _ahora(),
            "version_motor": LAKEHOUSE_VERSION,
        })

    def auditoria(self) -> list[dict[str, Any]]:
        return list(self._auditoria)

    # ---------------- Metadata Catalog 54.8 ----------------
    def registrar_dataset(self, dataset_id: str, propietario: str, dominio: str,
                          esquema: list[str], clasificacion: str,
                          vigencia_desde: str, actor: str) -> dict[str, Any]:
        if not dataset_id or not propietario or not actor:
            raise LakehouseInvalido("dataset_id, propietario y actor son obligatorios")
        if dominio not in DOMINIOS:
            raise LakehouseInvalido(f"dominio debe ser uno de {DOMINIOS}: {dominio}")
        if clasificacion not in CLASIFICACIONES:
            raise LakehouseInvalido(f"clasificacion debe ser una de {CLASIFICACIONES}")
        if not esquema:
            raise LakehouseInvalido("esquema obligatorio: la organización permanece "
                                    "gobernada mediante metadatos (54.7)")
        if dataset_id in self._datasets:
            raise LakehouseInvalido(f"dataset ya registrado: {dataset_id} — el catálogo "
                                    "nunca sobrescribe; publique una nueva versión (54.8)")
        ds = Dataset(dataset_id, propietario, dominio,
                     [VersionDataset(1, list(esquema), clasificacion,
                                     vigencia_desde, _ahora())], [], _ahora())
        self._datasets[dataset_id] = ds
        self._auditar("dataset_registrado", {"dataset_id": dataset_id, "dominio": dominio,
                                             "clasificacion": clasificacion}, actor)
        return self._dto_dataset(ds)

    def publicar_version_dataset(self, dataset_id: str, esquema: list[str],
                                 clasificacion: str, vigencia_desde: str,
                                 actor: str) -> dict[str, Any]:
        ds = self._dataset(dataset_id)
        if clasificacion not in CLASIFICACIONES:
            raise LakehouseInvalido(f"clasificacion debe ser una de {CLASIFICACIONES}")
        anterior = set(ds.versiones[-1].esquema)
        if not anterior.issubset(set(esquema)):
            raise LakehouseInvalido(
                f"versión incompatible: debe conservar los campos {sorted(anterior)} — "
                "toda la evolución permanece disponible (54.12)")
        version = len(ds.versiones) + 1
        ds.versiones.append(VersionDataset(version, list(esquema), clasificacion,
                                           vigencia_desde, _ahora()))
        self._auditar("dataset_version_publicada", {"dataset_id": dataset_id,
                                                    "version": version}, actor)
        return self._dto_dataset(ds)

    def catalogo(self, dominio: str | None = None) -> list[dict[str, Any]]:
        return [self._dto_dataset(d) for d in self._datasets.values()
                if dominio is None or d.dominio == dominio]

    def _dataset(self, dataset_id: str) -> Dataset:
        ds = self._datasets.get(dataset_id)
        if ds is None:
            raise LakehouseInvalido(f"dataset no registrado: {dataset_id}")
        return ds

    @staticmethod
    def _dto_dataset(d: Dataset) -> dict[str, Any]:
        v = d.versiones[-1]
        return {"dataset_id": d.dataset_id, "propietario": d.propietario,
                "dominio": d.dominio, "version_vigente": v.version,
                "esquema": list(v.esquema), "clasificacion": v.clasificacion,
                "vigencia_desde": v.vigencia_desde, "n_registros": len(d.registros),
                "creado_en": d.creado_en, "revisiones": len(d.versiones)}

    # ---------------- Data Ingestion Manager 54.6 ----------------
    def ingerir(self, dataset_id: str, registros: list[dict[str, Any]],
                origen: str, modo: str, actor: str) -> dict[str, Any]:
        ds = self._dataset(dataset_id)
        if not origen:
            raise LakehouseInvalido("origen obligatorio: toda adquisición declara su "
                                    "procedencia (54.6) — nunca se inventan datos")
        if modo not in MODOS_INGESTA:
            raise LakehouseInvalido(f"modo debe ser uno de {MODOS_INGESTA}")
        if not registros:
            raise LakehouseInvalido("lote vacío: nada que ingerir")
        esquema = set(ds.versiones[-1].esquema)
        for i, reg in enumerate(registros):
            desconocidos = set(reg) - esquema
            if desconocidos:
                raise LakehouseInvalido(
                    f"registro {i} con campos fuera del esquema vigente: "
                    f"{sorted(desconocidos)}")
        for reg in registros:
            ds.registros.append({**reg, "_origen": origen, "_ingerido_en": _ahora()})
        self._auditar("ingesta", {"dataset_id": dataset_id, "n": len(registros),
                                  "origen": origen, "modo": modo}, actor)
        return {"dataset_id": dataset_id, "ingeridos": len(registros),
                "origen": origen, "modo": modo, "total": len(ds.registros)}

    def registros(self, dataset_id: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self._dataset(dataset_id).registros]

    # ---------------- Data Governance Manager 54.9 ----------------
    def definir_politica(self, politica_id: str, tipo: str, contenido: str,
                         responsable: str) -> dict[str, Any]:
        if not politica_id or not contenido or not responsable:
            raise LakehouseInvalido("politica_id, contenido y responsable son obligatorios")
        if tipo not in TIPOS_POLITICA:
            raise LakehouseInvalido(f"tipo debe ser uno de {TIPOS_POLITICA}: {tipo}")
        versiones = self._politicas.setdefault(politica_id, [])
        version = len(versiones) + 1  # versionadas, sincronizables con el EGC
        versiones.append(VersionPolitica(version, tipo, contenido, responsable, _ahora()))
        self._auditar("politica_datos", {"politica_id": politica_id, "tipo": tipo,
                                         "version": version}, responsable)
        return {"politica_id": politica_id, "tipo": tipo, "version": version}

    def politicas(self, tipo: str | None = None) -> list[dict[str, Any]]:
        return [{"politica_id": pid, "tipo": v.tipo, "version": v.version,
                 "contenido": v.contenido, "responsable": v.responsable,
                 "registrada_en": v.registrada_en, "revisiones": len(versiones)}
                for pid, versiones in sorted(self._politicas.items())
                for v in [versiones[-1]]
                if tipo is None or v.tipo == tipo]

    # ---------------- Data Quality Engine 54.10 ----------------
    def evaluar_calidad(self, dataset_id: str, campo_clave: str,
                        evaluador: str) -> dict[str, Any]:
        """Indicadores calculados sobre los registros REALES ingeridos."""
        ds = self._dataset(dataset_id)
        if not evaluador:
            raise LakehouseInvalido("evaluador obligatorio")
        if not ds.registros:
            raise LakehouseInvalido(f"dataset {dataset_id} sin registros: la calidad "
                                    "NUNCA se declara sin datos reales")
        if campo_clave not in ds.versiones[-1].esquema:
            raise LakehouseInvalido(f"campo_clave fuera del esquema: {campo_clave}")
        registros = ds.registros
        esquema = ds.versiones[-1].esquema
        n = len(registros)
        completos = sum(1 for r in registros
                        if all(r.get(c) is not None for c in esquema))
        claves = [r.get(campo_clave) for r in registros]
        unicas = len(set(claves))
        presentes_clave = sum(1 for k in claves if k is not None)
        evaluacion = {
            "evaluacion_id": str(uuid.uuid4()),
            "dataset_id": dataset_id,
            "version_dataset": ds.versiones[-1].version,
            "n_registros": n,
            "integridad": round(presentes_clave / n * 100, 2),
            "consistencia": round(completos / n * 100, 2),
            "completitud": round(completos / n * 100, 2),
            "unicidad": round(unicas / n * 100, 2),
            "actualidad": {"ultima_ingesta": max(r["_ingerido_en"] for r in registros)},
            "evaluador": evaluador,
            "evaluada_en": _ahora(),
        }
        self._evaluaciones.append(evaluacion)
        self._auditar("calidad_evaluada", {"dataset_id": dataset_id,
                      "completitud": evaluacion["completitud"],
                      "unicidad": evaluacion["unicidad"]}, evaluador)
        return dict(evaluacion)

    def evaluaciones(self, dataset_id: str | None = None) -> list[dict[str, Any]]:
        return [dict(e) for e in self._evaluaciones
                if dataset_id is None or e["dataset_id"] == dataset_id]
