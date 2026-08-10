"""Business Continuity, Disaster Recovery & Resilience Engine (cap. 50).

El BCDRRE coordina estrategias de continuidad; NO sustituye la
infraestructura tecnológica (50.3).

- **Business Continuity Manager (50.6)**: planes versionados
  (alcance, responsables, procedimientos, prioridades, dependencias);
  la aprobación exige integridad (50.19): los incompletos permanecen
  en revisión.
- **Backup Manager (50.8)**: políticas por dominio de información +
  ejecución REAL de respaldos: copia del fichero con sha256 y
  verificación de integridad (nunca se declara un respaldo sin
  verificarlo).
- **Disaster Recovery Manager (50.7)**: eventos de recuperación
  documentados (restauración, verificación, retorno a operación).
- **Replication Manager (50.9)**: estado honesto de la estrategia de
  replicación; sin infraestructura configurada → `no_configurada`.
- **High Availability Manager (50.10)**: chequeos REALES de /health
  contra los servicios registrados; estado honesto cuando un servicio
  no responde.
- **Resilience Analyzer (50.11)**: disponibilidad y MTTR calculados
  sobre eventos reales registrados.

Auditoría 50.21 en todas las operaciones.
"""
from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone

BCDR_VERSION = "bcdr-1.0.0"

DOMINIOS_BACKUP = ("bases_de_datos", "documentos", "modelos",
                   "configuraciones", "registros_historicos")

ESTADOS_PLAN = ("borrador", "revision", "aprobado", "retirado")


class BcdrInvalido(ValueError):
    """Plan, respaldo o evento inválido (50.19)."""


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PlanContinuidad:
    """Business Continuity Manager (50.6)."""
    plan_id: str
    alcance: str
    responsables: list[str]
    procedimientos: list[str]
    prioridades: list[str]
    dependencias: list[str] = field(default_factory=list)
    rto_min: float | None = None    # tiempo objetivo de recuperación
    rpo_min: float | None = None    # punto objetivo de recuperación
    version: str = "1.0.0"
    estado: str = "borrador"


@dataclass
class PoliticaBackup:
    """Backup Manager (50.8): política por dominio de información."""
    politica_id: str
    dominio: str                    # DOMINIOS_BACKUP
    frecuencia: str                 # p. ej. "diario"
    retencion_dias: int
    destino: str                    # directorio de respaldo


class BcdrEngine:
    """BCDRRE: continuidad, respaldo verificado, recuperación real."""

    def __init__(self, backup_root: str = "/tmp/rpos_backups") -> None:
        self._planes: dict[str, list[PlanContinuidad]] = {}
        self._politicas: dict[str, PoliticaBackup] = {}
        self._respaldos: list[dict] = []
        self._eventos_dr: list[dict] = []
        self._replicacion: dict = {"estrategia": None}
        self._servicios_ha: dict[str, str] = {}   # nombre -> url
        self._backup_root = backup_root
        self._auditoria: list[dict] = []

    def _auditar(self, usuario: str, accion: str, detalle: str) -> None:
        self._auditoria.append({"usuario": usuario, "accion": accion,
                                "detalle": detalle, "fecha": _ahora()})

    def auditoria(self) -> list[dict]:
        return list(self._auditoria)

    # ------------------------------------------------------ planes 50.6
    def registrar_plan(self, plan: PlanContinuidad, usuario: str) -> dict:
        versiones = self._planes.setdefault(plan.plan_id, [])
        if any(p.version == plan.version for p in versiones):
            raise BcdrInvalido(
                f"versión ya registrada para {plan.plan_id}: "
                f"{plan.version} (50.6: nunca se sobrescribe)")
        versiones.append(plan)
        self._auditar(usuario, "registrar_plan",
                      f"{plan.plan_id} v{plan.version}")
        return {"plan_id": plan.plan_id, "version": plan.version}

    def aprobar_plan(self, plan_id: str, usuario: str) -> dict:
        """Validación 50.19: los planes incompletos permanecen en
        revisión."""
        if plan_id not in self._planes:
            raise BcdrInvalido(f"plan inexistente: {plan_id}")
        p = self._planes[plan_id][-1]
        faltantes = []
        if not p.alcance:
            faltantes.append("alcance")
        if not p.responsables:
            faltantes.append("responsables")
        if not p.procedimientos:
            faltantes.append("procedimientos")
        if p.rto_min is None:
            faltantes.append("rto_min")
        if p.rpo_min is None:
            faltantes.append("rpo_min")
        if faltantes:
            p.estado = "revision"
            self._auditar(usuario, "aprobar_plan",
                          f"{plan_id} RECHAZADO: {faltantes}")
            raise BcdrInvalido(
                f"plan incompleto {faltantes}: permanece en revisión "
                "(50.19)")
        p.estado = "aprobado"
        self._auditar(usuario, "aprobar_plan", plan_id)
        return {"plan_id": plan_id, "estado": "aprobado"}

    def planes(self) -> list[dict]:
        return [{"plan_id": pid, "version_vigente": v[-1].version,
                 "estado": v[-1].estado, "alcance": v[-1].alcance,
                 "rto_min": v[-1].rto_min, "rpo_min": v[-1].rpo_min,
                 "revisiones": [p.version for p in v]}
                for pid, v in self._planes.items()]

    # ------------------------------------------------------ backup 50.8
    def registrar_politica_backup(self, pol: PoliticaBackup,
                                  usuario: str) -> dict:
        if pol.politica_id in self._politicas:
            raise BcdrInvalido(f"política ya registrada: {pol.politica_id}")
        if pol.dominio not in DOMINIOS_BACKUP:
            raise BcdrInvalido(f"dominio inválido (50.8): {pol.dominio}")
        if pol.retencion_dias < 1 or not pol.destino:
            raise BcdrInvalido("retención/destino inválidos")
        self._politicas[pol.politica_id] = pol
        self._auditar(usuario, "registrar_politica_backup",
                      pol.politica_id)
        return {"politica_id": pol.politica_id}

    def ejecutar_backup(self, politica_id: str, ruta_origen: str,
                        usuario: str) -> dict:
        """Respaldo REAL con verificación de integridad (50.8).

        Nunca se declara un respaldo correcto sin verificar el sha256
        del destino contra el origen."""
        if politica_id not in self._politicas:
            raise BcdrInvalido(f"política inexistente: {politica_id}")
        if not os.path.isfile(ruta_origen):
            raise BcdrInvalido(f"origen inexistente: {ruta_origen}")
        pol = self._politicas[politica_id]
        destino_dir = os.path.join(self._backup_root, pol.dominio)
        os.makedirs(destino_dir, exist_ok=True)
        nombre = f"{os.path.basename(ruta_origen)}." \
                 f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}"
        destino = os.path.join(destino_dir, nombre)
        shutil.copyfile(ruta_origen, destino)

        def _sha(ruta: str) -> str:
            h = hashlib.sha256()
            with open(ruta, "rb") as f:
                for bloque in iter(lambda: f.read(65536), b""):
                    h.update(bloque)
            return h.hexdigest()

        sha_origen, sha_destino = _sha(ruta_origen), _sha(destino)
        verificado = sha_origen == sha_destino
        registro = {"politica_id": politica_id, "dominio": pol.dominio,
                    "origen": ruta_origen, "destino": destino,
                    "sha256": sha_origen, "verificado": verificado,
                    "fecha": _ahora()}
        self._respaldos.append(registro)
        self._auditar(usuario, "ejecutar_backup",
                      f"{ruta_origen} -> {destino} "
                      f"({'verificado' if verificado else 'FALLO'})")
        if not verificado:
            raise BcdrInvalido(
                "el respaldo no superó la verificación de integridad: "
                "no se declara correcto")
        return registro

    def respaldos(self) -> list[dict]:
        return list(self._respaldos)

    # ------------------------------------------- recuperación 50.7/50.12
    def registrar_evento_dr(self, evento_id: str, tipo: str,
                            descripcion: str, inicio: str,
                            usuario: str) -> dict:
        """Disaster Recovery Manager (50.7): cada evento documentado."""
        if tipo not in ("restauracion", "recuperacion_servicio",
                        "verificacion", "retorno_operacion"):
            raise BcdrInvalido(f"tipo de evento inválido: {tipo}")
        if any(e["evento_id"] == evento_id for e in self._eventos_dr):
            raise BcdrInvalido(f"evento duplicado: {evento_id}")
        self._eventos_dr.append({
            "evento_id": evento_id, "tipo": tipo,
            "descripcion": descripcion, "inicio": inicio, "fin": None,
            "duracion_min": None})
        self._auditar(usuario, "evento_dr", f"{evento_id} ({tipo})")
        return {"evento_id": evento_id}

    def cerrar_evento_dr(self, evento_id: str, fin: str,
                         usuario: str) -> dict:
        for e in self._eventos_dr:
            if e["evento_id"] == evento_id:
                if e["fin"] is not None:
                    raise BcdrInvalido("evento ya cerrado")
                t0 = datetime.fromisoformat(e["inicio"])
                t1 = datetime.fromisoformat(fin)
                e["fin"] = fin
                e["duracion_min"] = round(
                    (t1 - t0).total_seconds() / 60.0, 2)
                self._auditar(usuario, "cerrar_evento_dr", evento_id)
                return {"evento_id": evento_id,
                        "duracion_min": e["duracion_min"]}
        raise BcdrInvalido(f"evento inexistente: {evento_id}")

    def eventos_dr(self) -> list[dict]:
        return list(self._eventos_dr)

    # ------------------------------------------------- replicación 50.9
    def configurar_replicacion(self, estrategia: str, destinos: list[str],
                               usuario: str) -> dict:
        if not estrategia or not destinos:
            raise BcdrInvalido("estrategia y destinos obligatorios")
        self._replicacion = {"estrategia": estrategia,
                             "destinos": list(destinos),
                             "configurada_en": _ahora()}
        self._auditar(usuario, "configurar_replicacion", estrategia)
        return {"estrategia": estrategia, "destinos": destinos}

    def estado_replicacion(self) -> dict:
        """Estado honesto (50.9): sin configuración → no_configurada."""
        if self._replicacion["estrategia"] is None:
            return {"estado": "no_configurada",
                    "nota": "la estrategia de replicación depende de la "
                            "infraestructura desplegada (50.9); el motor "
                            "no declara replicación sin configurarla"}
        return {"estado": "configurada", **self._replicacion,
                "nota": "estrategia declarada; la verificación real "
                        "exige la infraestructura de destino"}

    # --------------------------------------------- alta disponibilidad 50.10
    def registrar_servicio_ha(self, nombre: str, health_url: str,
                              usuario: str) -> dict:
        if nombre in self._servicios_ha:
            raise BcdrInvalido(f"servicio ya registrado: {nombre}")
        self._servicios_ha[nombre] = health_url
        self._auditar(usuario, "registrar_servicio_ha", nombre)
        return {"nombre": nombre}

    def chequear_disponibilidad(self, timeout_s: float = 3.0) -> dict:
        """Chequeo REAL de /health de cada servicio registrado (50.10).

        Nunca se declara disponible un servicio sin respuesta real."""
        import httpx
        resultados = {}
        for nombre, url in self._servicios_ha.items():
            try:
                r = httpx.get(url, timeout=timeout_s)
                resultados[nombre] = {
                    "disponible": r.status_code == 200,
                    "status_code": r.status_code}
            except Exception as exc:
                resultados[nombre] = {"disponible": False,
                                      "error": str(exc)}
        disponibles = sum(1 for v in resultados.values()
                          if v["disponible"])
        return {"fecha": _ahora(), "servicios": resultados,
                "disponibles": disponibles, "total": len(resultados),
                "nota": "chequeo real de /health; un servicio sin "
                        "respuesta se reporta como no disponible"}

    # ---------------------------------------------- resiliencia 50.11
    def resiliencia(self) -> dict:
        """Indicadores calculados sobre eventos REALES (50.11)."""
        cerrados = [e for e in self._eventos_dr if e["fin"] is not None]
        mttr = (sum(e["duracion_min"] for e in cerrados) / len(cerrados)
                if cerrados else None)
        verificados = sum(1 for b in self._respaldos if b["verificado"])
        planes_aprobados = sum(1 for v in self._planes.values()
                               if v[-1].estado == "aprobado")
        return {"fecha": _ahora(),
                "n_eventos_dr": len(self._eventos_dr),
                "eventos_cerrados": len(cerrados),
                "mttr_min": (round(mttr, 2) if mttr is not None else None),
                "respaldos_verificados": verificados,
                "respaldos_totales": len(self._respaldos),
                "planes_aprobados": planes_aprobados,
                "replicacion": self.estado_replicacion()["estado"],
                "nota": "indicadores sobre eventos reales registrados; "
                        "sin eventos, los indicadores son honestamente "
                        "null — nunca estimados"}
