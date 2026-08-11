"""EDS cap. 41 — Enterprise Intelligence & AI Twin Core.

Feature Store 41.7 (trazabilidad completa, fuentes declaradas de los
Gemelos), Inference Engine 41.8/41.12/41.22 (toda inferencia documentada:
modelo, versión, datos, resultado, usuario; solo modelos validados y
desplegados 41.20/42.8; runtime honestamente `sin_runtime` cuando no hay
motor registrado — NUNCA se inventa un resultado) y Recommendation Engine
41.9/41.3 (recomendaciones claramente diferenciadas de las decisiones
operativas; la acción final permanece bajo responsabilidad de usuarios
autorizados — nunca automática).
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

EI_CORE_VERSION = "1.0.0"
AREAS_RECOMENDACION = ("produccion", "mantenimiento", "logistica", "calidad", "utilizacion_recursos")
TWINS_FUENTE = ("physics", "process", "qc", "operational", "facility", "economic")
NATURALEZA_RECOMENDACION = (
    "RECOMENDACIÓN de soporte a la decisión (41.3/41.9): no sustituye decisiones "
    "clínicas, no reemplaza procesos regulatorios, no modifica automáticamente la "
    "operación; la acción final permanece bajo responsabilidad de usuarios autorizados."
)


class EiInvalido(ValueError):
    pass


class SinRuntime(RuntimeError):
    """No hay motor de inferencia registrado: el resultado NO se inventa."""


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class VersionFeature:
    version: int
    twin_origen: str
    descripcion: str
    unidad: str
    registrada_en: str


@dataclass
class ValorFeature:
    valor_id: str
    feature_id: str
    version_feature: int
    valor: float
    timestamp_dato: str
    fuente: str
    registrado_en: str


@dataclass
class Inferencia:
    inferencia_id: str
    modelo_id: str
    version_modelo: str
    datos: dict[str, Any]
    resultado: Any
    usuario: str
    ejecutada_en: str
    hash_datos: str


@dataclass
class Recomendacion:
    recomendacion_id: str
    area: str
    titulo: str
    detalle: str
    soporte: dict[str, Any]
    generada_por: str
    naturaleza: str
    estado: str
    creada_en: str
    resuelta_por: str | None = None
    resuelta_en: str | None = None
    motivo_resolucion: str | None = None


class EiCoreEngine:
    """Núcleo transversal del Enterprise Intelligence & AI Twin (cap. 41)."""

    def __init__(self, verificador_modelo: Callable[[str, str], dict[str, Any] | None] | None = None):
        # verificador_modelo: consulta al Model Registry (cap. 42) — devuelve
        # {"estado": ...} o None si el modelo/versión no está registrado.
        self._verificador_modelo = verificador_modelo
        self._features: dict[str, list[VersionFeature]] = {}
        self._valores: dict[str, list[ValorFeature]] = {}
        self._runtimes: dict[tuple[str, str], Callable[[dict[str, Any]], Any]] = {}
        self._inferencias: list[Inferencia] = []
        self._recomendaciones: dict[str, Recomendacion] = {}
        self._auditoria: list[dict[str, Any]] = []

    # ---------------- auditoría ALCOA+ ----------------
    def _auditar(self, accion: str, detalle: dict[str, Any], actor: str) -> None:
        self._auditoria.append({
            "evento_id": str(uuid.uuid4()),
            "accion": accion,
            "detalle": detalle,
            "actor": actor,
            "timestamp": _ahora(),
            "version_motor": EI_CORE_VERSION,
        })

    def auditoria(self) -> list[dict[str, Any]]:
        return list(self._auditoria)

    # ---------------- Feature Store 41.7 ----------------
    def registrar_feature(self, feature_id: str, twin_origen: str, descripcion: str,
                          unidad: str, actor: str) -> dict[str, Any]:
        if not feature_id or not descripcion or not actor:
            raise EiInvalido("feature_id, descripcion y actor son obligatorios")
        if twin_origen not in TWINS_FUENTE:
            raise EiInvalido(f"twin_origen debe ser uno de {TWINS_FUENTE}: {twin_origen}")
        versiones = self._features.setdefault(feature_id, [])
        version = len(versiones) + 1  # versionado: nunca sobrescribe
        versiones.append(VersionFeature(version, twin_origen, descripcion, unidad, _ahora()))
        self._auditar("feature_registrada", {"feature_id": feature_id, "version": version,
                                             "twin_origen": twin_origen}, actor)
        return {"feature_id": feature_id, "version": version, "twin_origen": twin_origen}

    def feature(self, feature_id: str, version: int | None = None) -> dict[str, Any]:
        versiones = self._features.get(feature_id)
        if not versiones:
            raise EiInvalido(f"feature no registrada: {feature_id}")
        v = versiones[-1] if version is None else next(
            (x for x in versiones if x.version == version), None)
        if v is None:
            raise EiInvalido(f"versión {version} no registrada para {feature_id}")
        return {"feature_id": feature_id, "version": v.version, "twin_origen": v.twin_origen,
                "descripcion": v.descripcion, "unidad": v.unidad, "registrada_en": v.registrada_en,
                "revisiones": len(versiones)}

    def listar_features(self) -> list[dict[str, Any]]:
        return [self.feature(fid) for fid in sorted(self._features)]

    def registrar_valor(self, feature_id: str, valor: float, timestamp_dato: str,
                        fuente: str, actor: str, version_feature: int | None = None) -> dict[str, Any]:
        if not fuente:
            raise EiInvalido("fuente obligatoria: toda variable mantiene trazabilidad completa (41.7)")
        if not timestamp_dato:
            raise EiInvalido("timestamp_dato obligatorio (gestión temporal 41.12)")
        f = self.feature(feature_id, version_feature)  # valida existencia
        reg = ValorFeature(str(uuid.uuid4()), feature_id, f["version"], float(valor),
                           timestamp_dato, fuente, _ahora())
        self._valores.setdefault(feature_id, []).append(reg)
        self._auditar("valor_feature_registrado", {"feature_id": feature_id,
                      "version_feature": f["version"], "fuente": fuente}, actor)
        return {"valor_id": reg.valor_id, "feature_id": feature_id,
                "version_feature": reg.version_feature, "valor": reg.valor,
                "timestamp_dato": timestamp_dato, "fuente": fuente}

    def valores_feature(self, feature_id: str) -> list[dict[str, Any]]:
        self.feature(feature_id)  # valida existencia
        return [{"valor_id": v.valor_id, "version_feature": v.version_feature,
                 "valor": v.valor, "timestamp_dato": v.timestamp_dato, "fuente": v.fuente,
                 "registrado_en": v.registrado_en}
                for v in self._valores.get(feature_id, [])]

    # ---------------- Inference Engine 41.8 ----------------
    def registrar_runtime(self, modelo_id: str, version_modelo: str,
                          runtime: Callable[[dict[str, Any]], Any], actor: str) -> dict[str, Any]:
        if runtime is None or not callable(runtime):
            raise EiInvalido("runtime inválido: debe ser invocable")
        self._verificar_modelo_desplegado(modelo_id, version_modelo)
        self._runtimes[(modelo_id, version_modelo)] = runtime
        self._auditar("runtime_registrado", {"modelo_id": modelo_id,
                                             "version_modelo": version_modelo}, actor)
        return {"modelo_id": modelo_id, "version_modelo": version_modelo, "runtime": "registrado"}

    def _verificar_modelo_desplegado(self, modelo_id: str, version_modelo: str) -> dict[str, Any]:
        if self._verificador_modelo is None:
            raise EiInvalido("Model Registry no disponible: no puede verificarse la validación "
                             "del modelo (41.20 — los no validados no pueden utilizarse)")
        info = self._verificador_modelo(modelo_id, version_modelo)
        if info is None:
            raise EiInvalido(f"modelo no registrado en el Model Registry: {modelo_id} v{version_modelo}")
        if info.get("estado") != "desplegado":
            raise EiInvalido(f"modelo {modelo_id} v{version_modelo} en estado "
                             f"'{info.get('estado')}': solo modelos validados y desplegados "
                             "pueden ejecutar inferencias (41.20/42.8)")
        return info

    def ejecutar_inferencia(self, modelo_id: str, version_modelo: str, datos: dict[str, Any],
                            usuario: str) -> dict[str, Any]:
        if not usuario:
            raise EiInvalido("usuario obligatorio: toda inferencia registra quién la ejecutó (41.22)")
        if not isinstance(datos, dict) or not datos:
            raise EiInvalido("datos de inferencia obligatorios")
        self._verificar_modelo_desplegado(modelo_id, version_modelo)
        runtime = self._runtimes.get((modelo_id, version_modelo))
        if runtime is None:
            raise SinRuntime(f"sin runtime de inferencia para {modelo_id} v{version_modelo}: "
                             "el resultado NO se inventa (BentoML/serving honestamente pendiente)")
        resultado = runtime(datos)
        hash_datos = hashlib.sha256(repr(sorted(datos.items())).encode()).hexdigest()
        inf = Inferencia(str(uuid.uuid4()), modelo_id, version_modelo, dict(datos),
                         resultado, usuario, _ahora(), hash_datos)
        self._inferencias.append(inf)  # toda inferencia permanece documentada (41.8)
        self._auditar("inferencia_ejecutada", {"inferencia_id": inf.inferencia_id,
                      "modelo_id": modelo_id, "version_modelo": version_modelo,
                      "hash_datos": hash_datos}, usuario)
        return {"inferencia_id": inf.inferencia_id, "modelo_id": modelo_id,
                "version_modelo": version_modelo, "resultado": resultado,
                "usuario": usuario, "ejecutada_en": inf.ejecutada_en, "hash_datos": hash_datos}

    def historial_inferencias(self, modelo_id: str | None = None) -> list[dict[str, Any]]:
        return [{"inferencia_id": i.inferencia_id, "modelo_id": i.modelo_id,
                 "version_modelo": i.version_modelo, "datos": i.datos,
                 "resultado": i.resultado, "usuario": i.usuario,
                 "ejecutada_en": i.ejecutada_en, "hash_datos": i.hash_datos}
                for i in self._inferencias
                if modelo_id is None or i.modelo_id == modelo_id]

    # ---------------- Recommendation Engine 41.9 ----------------
    def generar_recomendacion(self, area: str, titulo: str, detalle: str,
                              soporte: dict[str, Any], generada_por: str) -> dict[str, Any]:
        if area not in AREAS_RECOMENDACION:
            raise EiInvalido(f"area debe ser una de {AREAS_RECOMENDACION}: {area}")
        if not titulo or not detalle or not generada_por:
            raise EiInvalido("titulo, detalle y generada_por son obligatorios")
        if not soporte or not any(soporte.get(k) for k in
                                  ("inferencia_ids", "feature_ids", "documento_ids", "hallazgos")):
            raise EiInvalido("soporte obligatorio: la recomendación debe referenciar su base "
                             "(inferencias, features, documentos o hallazgos) — nunca sin fundamento")
        rec = Recomendacion(str(uuid.uuid4()), area, titulo, detalle, dict(soporte),
                            generada_por, NATURALEZA_RECOMENDACION, "propuesta", _ahora())
        self._recomendaciones[rec.recomendacion_id] = rec
        self._auditar("recomendacion_generada", {"recomendacion_id": rec.recomendacion_id,
                                                 "area": area}, generada_por)
        return self._dto_rec(rec)

    def resolver_recomendacion(self, recomendacion_id: str, decision: str,
                               usuario: str, motivo: str) -> dict[str, Any]:
        """41.3: la acción final permanece bajo responsabilidad de usuarios autorizados."""
        rec = self._recomendaciones.get(recomendacion_id)
        if rec is None:
            raise EiInvalido(f"recomendación no registrada: {recomendacion_id}")
        if decision not in ("aceptada", "rechazada"):
            raise EiInvalido("decision debe ser 'aceptada' o 'rechazada'")
        if not usuario or not motivo:
            raise EiInvalido("usuario y motivo obligatorios (responsabilidad del usuario autorizado)")
        if rec.estado != "propuesta":
            raise EiInvalido(f"recomendación ya resuelta ({rec.estado}) — no se re-resuelve")
        rec.estado = decision
        rec.resuelta_por = usuario
        rec.resuelta_en = _ahora()
        rec.motivo_resolucion = motivo
        self._auditar("recomendacion_resuelta", {"recomendacion_id": recomendacion_id,
                                                 "decision": decision, "motivo": motivo}, usuario)
        return self._dto_rec(rec)

    def recomendaciones(self, area: str | None = None) -> list[dict[str, Any]]:
        return [self._dto_rec(r) for r in self._recomendaciones.values()
                if area is None or r.area == area]

    @staticmethod
    def _dto_rec(r: Recomendacion) -> dict[str, Any]:
        return {"recomendacion_id": r.recomendacion_id, "area": r.area, "titulo": r.titulo,
                "detalle": r.detalle, "soporte": r.soporte, "generada_por": r.generada_por,
                "naturaleza": r.naturaleza, "estado": r.estado, "creada_en": r.creada_en,
                "resuelta_por": r.resuelta_por, "resuelta_en": r.resuelta_en,
                "motivo_resolucion": r.motivo_resolucion}
