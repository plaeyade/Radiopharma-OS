"""EDS cap. 57 — HPC & Scientific Computing Platform.

Resource Manager 57.7 (asignación REAL con contabilidad de capacidad:
nunca se sobre-asigna CPU/GPU/memoria — los recursos libres se calculan
sobre asignaciones activas), GPU Manager 57.8 (aceleradores registrados
de forma independiente del fabricante), Job Scheduler 57.6 (cada trabajo
registra identificador, usuario, prioridad, recursos solicitados y
estado; la planificación permanece documentada; la ejecución usa un
runtime científico REAL inyectado — sin runtime el resultado NO se
inventa, 57.10) y Workflow Manager 57.11 (flujos de trabajos dependientes
ejecutados en orden topológico real, con etapas, dependencias, resultados
e historial). Gestión temporal 57.12: inicio, finalización, duración y
utilización de cada trabajo.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

HPC_VERSION = "1.0.0"
ESTADOS_TRABAJO = ("planificado", "en_ejecucion", "completado", "fallido")
TIPOS_TAREA_GPU = ("ia", "simulacion", "procesamiento_cientifico", "imagenes")


class HpcInvalido(ValueError):
    pass


class SinRuntimeCientifico(RuntimeError):
    """Sin runtime científico registrado: el resultado NO se inventa (57.10)."""


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


@dataclass
class Recursos:
    cpu: int = 0
    gpu: int = 0
    memoria_gb: float = 0.0

    def cabe_en(self, disponible: "Recursos") -> bool:
        return (self.cpu <= disponible.cpu and self.gpu <= disponible.gpu
                and self.memoria_gb <= disponible.memoria_gb)


@dataclass
class Gpu:
    gpu_id: str
    modelo: str
    fabricante: str
    memoria_gb: float
    estado: str  # disponible/asignada/fuera_de_servicio
    asignada_a: str | None = None


@dataclass
class Trabajo:
    trabajo_id: str
    usuario: str
    prioridad: int
    recursos: Recursos
    estado: str
    descripcion: str
    planificado_en: str
    iniciado_en: str | None = None
    finalizado_en: str | None = None
    duracion_s: float | None = None
    resultado: Any = None
    error: str | None = None


class HpcEngine:
    """Plataforma HPC científica (cap. 57)."""

    def __init__(self, cpu_total: int, memoria_total_gb: float):
        if cpu_total <= 0 or memoria_total_gb <= 0:
            raise HpcInvalido("capacidad del clúster inválida")
        self._capacidad = Recursos(cpu_total, 0, memoria_total_gb)
        self._gpus: dict[str, Gpu] = {}
        self._trabajos: dict[str, Trabajo] = {}
        self._flujos: dict[str, dict[str, Any]] = {}
        self._auditoria: list[dict[str, Any]] = []

    # ---------------- auditoría ALCOA+ ----------------
    def _auditar(self, accion: str, detalle: dict[str, Any], actor: str) -> None:
        self._auditoria.append({
            "evento_id": str(uuid.uuid4()),
            "accion": accion,
            "detalle": detalle,
            "actor": actor,
            "timestamp": _iso(_ahora()),
            "version_motor": HPC_VERSION,
        })

    def auditoria(self) -> list[dict[str, Any]]:
        return list(self._auditoria)

    # ---------------- Resource Manager 57.7 ----------------
    def recursos_disponibles(self) -> dict[str, Any]:
        en_uso = Recursos()
        for t in self._trabajos.values():
            if t.estado == "en_ejecucion":
                en_uso.cpu += t.recursos.cpu
                en_uso.gpu += t.recursos.gpu
                en_uso.memoria_gb += t.recursos.memoria_gb
        gpu_total = sum(1 for g in self._gpus.values()
                        if g.estado != "fuera_de_servicio")
        return {"cpu_total": self._capacidad.cpu, "cpu_libres": self._capacidad.cpu - en_uso.cpu,
                "memoria_total_gb": self._capacidad.memoria_gb,
                "memoria_libre_gb": round(self._capacidad.memoria_gb - en_uso.memoria_gb, 4),
                "gpu_total": gpu_total, "gpu_en_uso": en_uso.gpu}

    # ---------------- GPU Manager 57.8 ----------------
    def registrar_gpu(self, gpu_id: str, modelo: str, fabricante: str,
                      memoria_gb: float, actor: str) -> dict[str, Any]:
        if not all([gpu_id, modelo, fabricante]) or memoria_gb <= 0 or not actor:
            raise HpcInvalido("gpu_id, modelo, fabricante, memoria_gb y actor son "
                              "obligatorios — independiente del fabricante (57.8)")
        if gpu_id in self._gpus:
            raise HpcInvalido(f"GPU ya registrada: {gpu_id}")
        self._gpus[gpu_id] = Gpu(gpu_id, modelo, fabricante, float(memoria_gb),
                                 "disponible")
        self._auditar("gpu_registrada", {"gpu_id": gpu_id, "modelo": modelo,
                                         "fabricante": fabricante}, actor)
        return {"gpu_id": gpu_id, "estado": "disponible"}

    def gpus(self) -> list[dict[str, Any]]:
        return [{"gpu_id": g.gpu_id, "modelo": g.modelo, "fabricante": g.fabricante,
                 "memoria_gb": g.memoria_gb, "estado": g.estado,
                 "asignada_a": g.asignada_a} for g in self._gpus.values()]

    # ---------------- Job Scheduler 57.6 ----------------
    def planificar_trabajo(self, usuario: str, prioridad: int, cpu: int,
                           gpu: int, memoria_gb: float, descripcion: str) -> dict[str, Any]:
        if not usuario or not descripcion:
            raise HpcInvalido("usuario y descripcion son obligatorios (57.6)")
        if not 1 <= prioridad <= 5:
            raise HpcInvalido("prioridad entre 1 (máxima) y 5")
        recursos = Recursos(cpu, gpu, memoria_gb)
        if cpu <= 0 and gpu <= 0:
            raise HpcInvalido("el trabajo debe solicitar cpu o gpu")
        t = Trabajo(str(uuid.uuid4()), usuario, prioridad, recursos,
                    "planificado", descripcion, _iso(_ahora()))
        self._trabajos[t.trabajo_id] = t  # planificación documentada
        self._auditar("trabajo_planificado", {"trabajo_id": t.trabajo_id,
                      "prioridad": prioridad, "cpu": cpu, "gpu": gpu,
                      "memoria_gb": memoria_gb}, usuario)
        return {"trabajo_id": t.trabajo_id, "estado": "planificado",
                "prioridad": prioridad}

    def ejecutar_trabajo(self, trabajo_id: str,
                         runtime: Callable[[], Any] | None = None) -> dict[str, Any]:
        t = self._trabajo(trabajo_id)
        if t.estado != "planificado":
            raise HpcInvalido(f"trabajo en estado '{t.estado}': no ejecutable")
        disp = self.recursos_disponibles()
        disponible = Recursos(disp["cpu_libres"], disp["gpu_total"] - disp["gpu_en_uso"],
                              disp["memoria_libre_gb"])
        if not t.recursos.cabe_en(disponible):
            raise HpcInvalido("recursos insuficientes: nunca se sobre-asigna el "
                              "clúster (57.7) — el trabajo permanece planificado")
        if t.recursos.gpu > 0:
            libres = [g for g in self._gpus.values() if g.estado == "disponible"]
            if len(libres) < t.recursos.gpu:
                raise HpcInvalido("GPUs insuficientes disponibles")
            for g in libres[:t.recursos.gpu]:
                g.estado, g.asignada_a = "asignada", trabajo_id
        if runtime is None:
            raise SinRuntimeCientifico("sin runtime científico (57.10): el resultado "
                                       "del trabajo NO se inventa")
        t.estado = "en_ejecucion"
        t.iniciado_en = _iso(_ahora())
        inicio = _ahora()
        try:
            t.resultado = runtime()  # ejecución REAL
        except Exception as exc:
            t.estado = "fallido"
            t.error = f"{type(exc).__name__}: {exc}"
        else:
            t.estado = "completado"
        fin = _ahora()
        t.finalizado_en = _iso(fin)
        t.duracion_s = round((fin - inicio).total_seconds(), 4)
        for g in self._gpus.values():
            if g.asignada_a == trabajo_id:
                g.estado, g.asignada_a = "disponible", None
        self._auditar("trabajo_finalizado", {"trabajo_id": trabajo_id,
                      "estado": t.estado, "duracion_s": t.duracion_s}, t.usuario)
        return self._dto_trabajo(t)

    def trabajos(self, estado: str | None = None) -> list[dict[str, Any]]:
        return [self._dto_trabajo(t) for t in self._trabajos.values()
                if estado is None or t.estado == estado]

    def cola_pendiente(self) -> list[dict[str, Any]]:
        pendientes = [t for t in self._trabajos.values() if t.estado == "planificado"]
        return [self._dto_trabajo(t)
                for t in sorted(pendientes, key=lambda x: (x.prioridad, x.planificado_en))]

    def _trabajo(self, trabajo_id: str) -> Trabajo:
        t = self._trabajos.get(trabajo_id)
        if t is None:
            raise HpcInvalido(f"trabajo no registrado: {trabajo_id}")
        return t

    @staticmethod
    def _dto_trabajo(t: Trabajo) -> dict[str, Any]:
        return {"trabajo_id": t.trabajo_id, "usuario": t.usuario,
                "prioridad": t.prioridad, "estado": t.estado,
                "descripcion": t.descripcion,
                "recursos": {"cpu": t.recursos.cpu, "gpu": t.recursos.gpu,
                             "memoria_gb": t.recursos.memoria_gb},
                "planificado_en": t.planificado_en, "iniciado_en": t.iniciado_en,
                "finalizado_en": t.finalizado_en, "duracion_s": t.duracion_s,
                "resultado": t.resultado, "error": t.error}

    # ---------------- Workflow Manager 57.11 ----------------
    def definir_flujo(self, flujo_id: str, etapas: list[dict[str, Any]],
                      actor: str) -> dict[str, Any]:
        """etapas: [{"etapa", "depende_de": [...], "runtime": nombre}] — las
        dependencias deben referenciar etapas del propio flujo y no tener ciclos."""
        if not flujo_id or not etapas or not actor:
            raise HpcInvalido("flujo_id, etapas y actor son obligatorios")
        if flujo_id in self._flujos:
            raise HpcInvalido(f"flujo ya registrado: {flujo_id}")
        nombres = [e.get("etapa") for e in etapas]
        if len(set(nombres)) != len(nombres) or any(not n for n in nombres):
            raise HpcInvalido("etapas con nombres únicos y no vacíos")
        for e in etapas:
            for dep in e.get("depende_de", []):
                if dep not in nombres:
                    raise HpcInvalido(f"dependencia desconocida: {dep} en {e['etapa']}")
        orden = self._topologico(etapas)  # valida ausencia de ciclos
        self._flujos[flujo_id] = {"flujo_id": flujo_id, "etapas": etapas,
                                  "orden": orden, "ejecuciones": [],
                                  "registrado_en": _iso(_ahora())}
        self._auditar("flujo_definido", {"flujo_id": flujo_id,
                                         "etapas": nombres, "orden": orden}, actor)
        return {"flujo_id": flujo_id, "orden_ejecucion": orden}

    @staticmethod
    def _topologico(etapas: list[dict[str, Any]]) -> list[str]:
        pendientes = {e["etapa"]: set(e.get("depende_de", [])) for e in etapas}
        orden: list[str] = []
        while pendientes:
            listos = [n for n, deps in pendientes.items() if not deps]
            if not listos:
                raise HpcInvalido("dependencias cíclicas en el flujo (57.11)")
            for n in sorted(listos):
                orden.append(n)
                del pendientes[n]
                for deps in pendientes.values():
                    deps.discard(n)
        return orden

    def ejecutar_flujo(self, flujo_id: str,
                       runtimes: dict[str, Callable[[dict[str, Any]], Any]],
                       actor: str) -> dict[str, Any]:
        flujo = self._flujos.get(flujo_id)
        if flujo is None:
            raise HpcInvalido(f"flujo no registrado: {flujo_id}")
        faltantes = [n for n in flujo["orden"] if n not in runtimes]
        if faltantes:
            raise SinRuntimeCientifico(f"sin runtime para etapas {faltantes}: el "
                                       "flujo NO se simula (57.10)")
        inicio = _ahora()
        resultados: dict[str, Any] = {}
        historial = []
        for etapa in flujo["orden"]:  # orden topológico REAL
            resultado = runtimes[etapa](dict(resultados))
            resultados[etapa] = resultado
            historial.append({"etapa": etapa, "resultado": resultado,
                              "finalizada_en": _iso(_ahora())})
        ejecucion = {"ejecucion_id": str(uuid.uuid4()), "flujo_id": flujo_id,
                     "orden": flujo["orden"], "historial": historial,
                     "iniciada_en": _iso(inicio), "finalizada_en": _iso(_ahora()),
                     "estado": "completado"}
        flujo["ejecuciones"].append(ejecucion)
        self._auditar("flujo_ejecutado", {"flujo_id": flujo_id,
                                          "etapas": len(historial)}, actor)
        return dict(ejecucion)
