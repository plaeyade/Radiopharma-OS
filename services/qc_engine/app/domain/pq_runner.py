"""Ejecutor PQ real — Performance Qualification contra servicios vivos
(Informe 14.9: PQ es verificación de desempeño bajo condiciones reales).

Cada criterio del protocolo PQ es una comprobación REAL contra un
servicio desplegado (HTTP GET con medición de latencia real). Los
resultados se miden — nunca se inventan: un servicio caído produce un
criterio no cumplido con el error real registrado, y la etapa queda
honestamente ``no_superada``. Los protocolos son versionados y nunca se
sobrescriben (14.12). Cada ejecución alimenta el QualificationEngine con
``entorno == "condiciones_reales"`` y queda auditada (ALCOA+).
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from .qualification import (CalificacionInvalida, QualificationEngine)

PQ_RUNNER_VERSION = "pq-runner-1.0.0"


def _fabrica_http_defecto():
    import httpx
    return httpx.Client(timeout=5.0, follow_redirects=True)


class EjecutorPQ:
    """Ejecuta protocolos PQ midiendo criterios reales (14.9)."""

    def __init__(self, engine: QualificationEngine, fabrica_http=None,
                 timeout_s: float = 5.0) -> None:
        self._engine = engine
        self._fabrica_http = fabrica_http or _fabrica_http_defecto
        self._timeout = timeout_s
        self._protocolos: dict[str, list[dict]] = {}
        self._auditoria: list[dict] = []

    # ------------------------------------------------------------ núcleo
    def _ahora(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _auditar(self, accion: str, detalle: dict, actor: str,
                 resultado: str = "ok") -> None:
        self._auditoria.append({
            "evento_id": str(uuid.uuid4()), "accion": accion,
            "detalle": detalle, "actor": actor, "resultado": resultado,
            "timestamp": self._ahora(),
            "version_motor": PQ_RUNNER_VERSION,
        })

    def auditoria(self) -> list[dict]:
        return list(self._auditoria)

    # --------------------------------------------- protocolos versionados
    def definir_protocolo(self, protocolo_id: str, componente_id: str,
                          criterios: list[dict], responsable: str,
                          motivo: str) -> dict:
        """Alta o nueva versión de un protocolo PQ ejecutable.

        Cada criterio: ``{criterio, url, status_esperado (200),
        contiene (opcional), umbral_ms (opcional)}``. La definición se
        replica como protocolo de etapa PQ del QualificationEngine
        (misma versión de criterios, nunca sobrescrita)."""
        if not all([protocolo_id, componente_id, responsable, motivo]):
            raise CalificacionInvalida(
                "protocolo_id, componente_id, responsable y motivo "
                "obligatorios (14.12)")
        if not criterios:
            raise CalificacionInvalida(
                "el protocolo PQ exige al menos un criterio medible")
        for c in criterios:
            if not c.get("criterio") or not c.get("url"):
                raise CalificacionInvalida(
                    "cada criterio exige nombre y url real; un criterio "
                    "sin comprobación sería una declaración vacía")
            if not str(c["url"]).startswith(("http://", "https://")):
                raise CalificacionInvalida(
                    f"url inválida: {c['url']} (http/https obligatorio)")
        versiones = self._protocolos.setdefault(protocolo_id, [])
        proto = {
            "protocolo_id": protocolo_id, "componente_id": componente_id,
            "version": len(versiones) + 1,
            "criterios": [dict(c) for c in criterios],
            "responsable": responsable, "motivo": motivo,
            "definido_en": self._ahora(),
        }
        versiones.append(proto)
        # espejo en el motor de calificación (orden DQ→IQ→OQ→PQ intacto)
        self._engine.definir_protocolo(
            componente_id, "PQ", [c["criterio"] for c in criterios],
            responsable, motivo)
        self._auditar("protocolo_pq_definido",
                      {"protocolo_id": protocolo_id,
                       "componente_id": componente_id,
                       "version": proto["version"],
                       "criterios": len(criterios)}, responsable)
        return proto

    def protocolos(self) -> list[dict]:
        return [
            {"protocolo_id": p["protocolo_id"],
             "componente_id": p["componente_id"],
             "version": p["version"], "criterios": len(p["criterios"]),
             "responsable": p["responsable"],
             "definido_en": p["definido_en"]}
            for p in (v[-1] for v in self._protocolos.values())
        ]

    def _vigente(self, protocolo_id: str) -> dict:
        versiones = self._protocolos.get(protocolo_id)
        if not versiones:
            raise CalificacionInvalida(
                f"protocolo PQ desconocido: {protocolo_id}")
        return versiones[-1]

    # -------------------------------------------------- ejecución real
    def _medir_criterio(self, http, criterio: dict) -> dict:
        """Comprobación REAL de un criterio: GET + latencia medida.
        Cualquier fallo se devuelve honestamente como no cumplido."""
        t0 = time.perf_counter()
        try:
            r = http.get(criterio["url"])
            latencia_ms = round((time.perf_counter() - t0) * 1000, 2)
            status = getattr(r, "status_code", None)
            cuerpo = getattr(r, "text", "") or ""
            esperado = int(criterio.get("status_esperado", 200))
            fallos = []
            if status != esperado:
                fallos.append(f"status {status} != {esperado}")
            contiene = criterio.get("contiene")
            if contiene and contiene not in cuerpo:
                fallos.append(f"el cuerpo no contiene {contiene!r}")
            umbral = criterio.get("umbral_ms")
            if umbral is not None and latencia_ms > float(umbral):
                fallos.append(
                    f"latencia {latencia_ms} ms > umbral {umbral} ms")
            return {
                "criterio": criterio["criterio"],
                "cumple": not fallos,
                "detalle": (f"GET {criterio['url']} → {status} en "
                            f"{latencia_ms} ms" +
                            (f"; fallos: {'; '.join(fallos)}"
                             if fallos else "")),
                "evidencia_ref": criterio["url"],
            }
        except Exception as exc:
            latencia_ms = round((time.perf_counter() - t0) * 1000, 2)
            return {
                "criterio": criterio["criterio"],
                "cumple": False,
                "detalle": (f"GET {criterio['url']} falló en "
                            f"{latencia_ms} ms: {type(exc).__name__}: "
                            f"{exc} — el servicio NO responde; el "
                            "criterio no se declara cumplido"),
                "evidencia_ref": criterio["url"],
            }

    def ejecutar(self, protocolo_id: str, ejecutor: str) -> dict:
        """Ejecuta el protocolo PQ vigente midiendo TODOS los criterios
        contra los servicios reales y registra la etapa PQ en el motor
        con entorno ``condiciones_reales`` (14.9)."""
        if not ejecutor:
            raise CalificacionInvalida("ejecutor obligatorio (ALCOA+)")
        proto = self._vigente(protocolo_id)
        http = self._fabrica_http()
        resultados = [self._medir_criterio(http, c)
                      for c in proto["criterios"]]
        ejec = self._engine.ejecutar_etapa(
            proto["componente_id"], "PQ", "condiciones_reales",
            ejecutor, resultados)
        self._auditar(
            "pq_ejecutado",
            {"protocolo_id": protocolo_id,
             "protocolo_version": proto["version"],
             "componente_id": proto["componente_id"],
             "estado": ejec.estado,
             "ejecucion_id": ejec.ejecucion_id,
             "criterios_cumplidos":
                 sum(1 for r in ejec.resultados if r.cumple),
             "criterios_totales": len(ejec.resultados)},
            ejecutor,
            "ok" if ejec.estado == "superada" else "fallo")
        return {
            "ejecucion_id": ejec.ejecucion_id,
            "protocolo_id": protocolo_id,
            "protocolo_version": proto["version"],
            "componente_id": proto["componente_id"],
            "entorno": ejec.entorno,
            "estado": ejec.estado,
            "resultados": [
                {"criterio": r.criterio, "cumple": r.cumple,
                 "detalle": r.detalle, "evidencia_ref": r.evidencia_ref}
                for r in ejec.resultados
            ],
            "ejecutada_en": ejec.ejecutada_en,
        }

    def estado_runner(self) -> dict:
        return {
            "version_motor": PQ_RUNNER_VERSION,
            "protocolos": len(self._protocolos),
            "fabrica_http": ("inyectada" if self._fabrica_http
                             is not _fabrica_http_defecto
                             else "httpx_real"),
            "timeout_s": self._timeout,
        }
