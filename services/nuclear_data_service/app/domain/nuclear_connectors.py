"""Conectores de datos nucleares externos — EXFOR (19.12), SRIM (19.10)
y NNDC (19.13).

Filosofía canónica:
- **EXFOR (19.12)**: los datos experimentales tienen PRIORIDAD sobre los
  modelos teóricos. La importación es una consulta HTTP REAL a la fuente
  (p. ej. IAEA NDS); cada conjunto conserva referencia, versión, fecha y
  fuente extraídos de la respuesta real — nunca se inventan.
- **SRIM (19.10)**: las tablas de stopping power / alcance se importan
  desde archivos de salida REALES de SRIM (directorio configurado); el
  archivo se parsea de verdad, se registra con hash sha256 y alimenta al
  Yield Engine mediante un cargador inyectado.
- **NNDC (19.13)**: consulta HTTP REAL de constantes nucleares.
- Sin fuente configurada o sin sonda exitosa → ``no_configurado`` /
  ``fallo_conexion`` honestos y 503 en las importaciones.
- Fuentes versionadas: la configuración nunca se sobrescribe.
- Auditoría ALCOA+ en todas las operaciones.

El cliente HTTP es inyectable (pruebas); en producción se usa httpx.
"""
from __future__ import annotations

import csv
import hashlib
import io
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

CONNECTORS_VERSION = "nuclear-connectors-1.0.0"

TIPOS_FUENTE = ("exfor", "srim", "nndc")


class FuenteInvalida(ValueError):
    """Fuente, consulta o archivo inválido."""


class SinFuente(RuntimeError):
    """Fuente sin configurar/conectar → 503 honesto."""


@dataclass
class Fuente:
    fuente_id: str
    tipo: str
    endpoint: str          # URL http(s) para exfor/nndc; directorio para srim
    version: int
    responsable: str
    registrada_en: str


class NuclearDataConnectors:
    """Conectores EXFOR/SRIM/NNDC (Informe 19.10-19.13)."""

    def __init__(self, biblioteca=None, fabrica_http=None,
                 cargador_yield=None, timeout_s: float = 10.0) -> None:
        # biblioteca: RadionuclideLibrary inyectada (importación EXFOR 19.12)
        # cargador_yield: callable(material, tabla, metadatos) que alimenta
        # al Yield Engine con tablas SRIM reales (19.10)
        self._biblioteca = biblioteca
        self._fabrica_http = fabrica_http
        self._cargador_yield = cargador_yield
        self._timeout_s = timeout_s
        self._fuentes: dict[str, list[Fuente]] = {}
        self._vivas: dict[str, Fuente] = {}
        self._ultimo_estado: dict[str, dict] = {}
        self._tablas_srim: dict[str, list[dict]] = {}
        self._auditoria: list[dict] = []

    # ------------------------------------------------------------ núcleo
    def _ahora(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _auditar(self, accion: str, detalle: dict, actor: str,
                 resultado: str = "ok") -> None:
        self._auditoria.append({
            "evento_id": str(uuid.uuid4()),
            "accion": accion,
            "detalle": detalle,
            "actor": actor,
            "resultado": resultado,
            "timestamp": self._ahora(),
            "version_motor": CONNECTORS_VERSION,
        })

    def auditoria(self) -> list[dict]:
        return list(self._auditoria)

    def _http(self):
        if self._fabrica_http is not None:
            return self._fabrica_http()
        import httpx
        return httpx.Client(timeout=self._timeout_s)

    # ------------------------------------------------ fuentes (versionadas)
    def registrar_fuente(self, fuente_id: str, tipo: str, endpoint: str,
                         responsable: str) -> Fuente:
        """Alta o nueva versión de la configuración; nunca se sobrescribe."""
        if tipo not in TIPOS_FUENTE:
            raise FuenteInvalida(
                f"tipo inválido {tipo}; tipos: {list(TIPOS_FUENTE)}")
        if not endpoint or not responsable:
            raise FuenteInvalida(
                "endpoint y responsable obligatorios; sin endpoint la "
                "fuente sería una simulación")
        if tipo in ("exfor", "nndc") and not endpoint.startswith(
                ("http://", "https://")):
            raise FuenteInvalida(
                f"fuente {tipo}: endpoint debe ser URL http(s)")
        versiones = self._fuentes.setdefault(fuente_id, [])
        f = Fuente(fuente_id, tipo, endpoint.rstrip("/"),
                   len(versiones) + 1, responsable, self._ahora())
        versiones.append(f)
        self._vivas.pop(fuente_id, None)
        self._auditar("fuente_registrada",
                      {"fuente_id": fuente_id, "tipo": tipo,
                       "endpoint": endpoint, "version": f.version},
                      responsable)
        return f

    def fuentes(self) -> list[dict]:
        return [{"fuente_id": v[-1].fuente_id, "tipo": v[-1].tipo,
                 "endpoint": v[-1].endpoint, "version": v[-1].version,
                 "estado": self._ultimo_estado.get(
                     v[-1].fuente_id, {}).get("estado", "no_sondeada")}
                for v in self._fuentes.values()]

    def historial_fuente(self, fuente_id: str) -> list[dict]:
        return [{"version": f.version, "endpoint": f.endpoint,
                 "responsable": f.responsable,
                 "registrada_en": f.registrada_en}
                for f in self._fuentes.get(fuente_id, [])]

    def _vigente(self, fuente_id: str) -> Fuente:
        versiones = self._fuentes.get(fuente_id)
        if not versiones:
            raise FuenteInvalida(f"fuente desconocida: {fuente_id}")
        return versiones[-1]

    def sondear(self, fuente_id: str, actor: str = "sistema") -> dict:
        """Sonda REAL: HTTP GET para exfor/nndc; verificación real del
        directorio para srim (archivos de salida 19.10)."""
        f = self._vigente(fuente_id)
        try:
            if f.tipo == "srim":
                if not os.path.isdir(f.endpoint):
                    raise FileNotFoundError(
                        f"directorio SRIM inexistente: {f.endpoint}")
                detalle_ok = f"directorio con {len(os.listdir(f.endpoint))} archivos"
            else:
                with self._http() as http:
                    resp = http.get(f.endpoint)
                if resp.status_code >= 400:
                    raise ConnectionError(f"HTTP {resp.status_code}")
                detalle_ok = f"HTTP {resp.status_code}"
            self._vivas[fuente_id] = f
            estado = {"estado": "conectada", "detalle": detalle_ok,
                      "sondeada_en": self._ahora()}
            resultado = "ok"
        except Exception as exc:
            self._vivas.pop(fuente_id, None)
            estado = {"estado": "fallo_conexion",
                      "detalle": f"{type(exc).__name__}: {exc}",
                      "sondeada_en": self._ahora()}
            resultado = "fallo"
        self._ultimo_estado[fuente_id] = estado
        self._auditar("fuente_sondeada",
                      {"fuente_id": fuente_id, "tipo": f.tipo,
                       "estado": estado["estado"],
                       "detalle": estado["detalle"]}, actor, resultado)
        return {"fuente_id": fuente_id, **estado}

    def _viva(self, fuente_id: str, actor: str) -> Fuente:
        f = self._vigente(fuente_id)
        if fuente_id not in self._vivas:
            self._auditar("importacion_rechazada",
                          {"fuente_id": fuente_id,
                           "motivo": "sin conexión viva"}, actor, "fallo")
            raise SinFuente(
                f"fuente {fuente_id} sin conexión viva; sondee primero")
        return f

    # ------------------------------------------- EXFOR (19.12)
    def importar_exfor(self, fuente_id: str, nuclide: str,
                       ruta_consulta: str, autor: str) -> dict:
        """Consulta HTTP REAL a la fuente EXFOR e importa el conjunto a
        la biblioteca (19.12): referencia, versión, fecha y fuente se
        extraen de la respuesta real; los datos experimentales prevalecen
        sobre los modelos teóricos."""
        f = self._viva(fuente_id, autor)
        if f.tipo != "exfor":
            raise FuenteInvalida(
                f"la fuente {fuente_id} es {f.tipo}, no exfor")
        if self._biblioteca is None:
            raise SinFuente(
                "biblioteca no inyectada: no hay dónde registrar los "
                "datos experimentales (19.12)")
        if not autor:
            raise FuenteInvalida("autor obligatorio (19.12)")
        try:
            with self._http() as http:
                resp = http.get(f.endpoint + ruta_consulta)
            if resp.status_code >= 400:
                raise ConnectionError(f"HTTP {resp.status_code}")
            cuerpo = resp.json()
        except Exception as exc:
            self._auditar("importacion_exfor_fallida",
                          {"fuente_id": fuente_id, "nuclide": nuclide,
                           "detalle": f"{type(exc).__name__}: {exc}"},
                          autor, "fallo")
            raise SinFuente(
                f"fallo consultando EXFOR: {type(exc).__name__}: {exc}"
                ) from exc
        # metadatos obligatorios 19.12 extraídos de la respuesta REAL
        meta = cuerpo.get("metadatos", {})
        datos = cuerpo.get("datos", [])
        faltan = [k for k in ("referencia", "version", "fecha")
                  if not meta.get(k)]
        if faltan or not datos:
            raise FuenteInvalida(
                f"respuesta EXFOR incompleta: faltan {faltan or ['datos']}"
                "; no se importa un conjunto sin referencia/versión/fecha"
                " (19.12)")
        registro = self._biblioteca.registrar_datos_experimentales(
            nuclide, tipo=cuerpo.get("tipo", "seccion_eficaz"),
            datos=datos, referencia=meta["referencia"],
            version_datos=str(meta["version"]), fecha=meta["fecha"],
            fuente=f"EXFOR — {f.endpoint}", autor=autor)
        self._auditar("importacion_exfor",
                      {"fuente_id": fuente_id, "nuclide": nuclide,
                       "referencia": meta["referencia"],
                       "puntos": len(datos),
                       "registro_id": registro["registro_id"]}, autor)
        return {"registro": registro,
                "prioridad": registro["prioridad"],
                "importado_en": self._ahora()}

    # ------------------------------------------- SRIM (19.10)
    def importar_srim(self, fuente_id: str, material: str, archivo: str,
                      autor: str) -> dict:
        """Importa una tabla REAL de salida SRIM (CSV con columnas
        energia_mev, stopping_power) desde el directorio configurado;
        registra hash sha256 y alimenta al Yield Engine si hay cargador
        inyectado. Las tablas nunca se sobrescriben: mismo material +
        mismo hash = duplicado rechazado."""
        f = self._viva(fuente_id, autor)
        if f.tipo != "srim":
            raise FuenteInvalida(
                f"la fuente {fuente_id} es {f.tipo}, no srim")
        if not material or not archivo or not autor:
            raise FuenteInvalida(
                "material, archivo y autor obligatorios (19.10)")
        ruta = os.path.join(f.endpoint, archivo)
        if not os.path.isfile(ruta):
            raise FuenteInvalida(
                f"archivo SRIM inexistente: {ruta}; no se inventan "
                "tablas de stopping power")
        contenido = open(ruta, "rb").read()
        sha = hashlib.sha256(contenido).hexdigest()
        tabla = self._parsear_tabla_srim(contenido.decode("utf-8"))
        versiones = self._tablas_srim.setdefault(material, [])
        if any(t["sha256"] == sha for t in versiones):
            raise FuenteInvalida(
                f"tabla idéntica ya importada para {material} "
                f"(sha256 {sha[:12]}…); nunca se sobrescribe")
        entrada = {"material": material, "archivo": archivo,
                   "sha256": sha, "puntos": len(tabla),
                   "version": len(versiones) + 1,
                   "importada_en": self._ahora(), "autor": autor}
        versiones.append(entrada)
        alimentado = False
        if self._cargador_yield is not None:
            self._cargador_yield(material, tabla, {
                "sha256": sha, "fuente": f"SRIM — {archivo}"})
            alimentado = True
        self._auditar("importacion_srim",
                      {"fuente_id": fuente_id, "material": material,
                       "archivo": archivo, "sha256": sha,
                       "puntos": len(tabla),
                       "alimenta_yield_engine": alimentado}, autor)
        return {**entrada, "alimenta_yield_engine": alimentado}

    @staticmethod
    def _parsear_tabla_srim(texto: str) -> list[dict]:
        """Parseo real de CSV (energia_mev,stopping_power); cualquier
        fila malformada invalida la tabla — no se corrige a mano."""
        lector = csv.DictReader(io.StringIO(texto))
        campos = set(lector.fieldnames or [])
        if not {"energia_mev", "stopping_power"} <= campos:
            raise FuenteInvalida(
                "CSV SRIM sin columnas energia_mev/stopping_power")
        tabla = []
        for i, fila in enumerate(lector, start=2):
            try:
                tabla.append({"energia_mev": float(fila["energia_mev"]),
                              "stopping_power":
                                  float(fila["stopping_power"])})
            except (TypeError, ValueError) as exc:
                raise FuenteInvalida(
                    f"fila {i} malformada en la tabla SRIM: {fila}"
                    ) from exc
        if not tabla:
            raise FuenteInvalida("tabla SRIM vacía")
        return tabla

    def tablas_srim(self, material: str) -> list[dict]:
        return [dict(t) for t in self._tablas_srim.get(material, [])]

    # ------------------------------------------- NNDC (19.13)
    def consultar_nndc(self, fuente_id: str, nuclide: str,
                       actor: str = "sistema") -> dict:
        """Consulta HTTP REAL de constantes nucleares (19.13)."""
        f = self._viva(fuente_id, actor)
        if f.tipo != "nndc":
            raise FuenteInvalida(
                f"la fuente {fuente_id} es {f.tipo}, no nndc")
        try:
            with self._http() as http:
                resp = http.get(f"{f.endpoint}/nuclide/{nuclide}")
            if resp.status_code >= 400:
                raise ConnectionError(f"HTTP {resp.status_code}")
            cuerpo = resp.json()
        except Exception as exc:
            raise SinFuente(
                f"fallo consultando NNDC: {type(exc).__name__}: {exc}"
                ) from exc
        self._auditar("consulta_nndc",
                      {"fuente_id": fuente_id, "nuclide": nuclide}, actor)
        return {"nuclide": nuclide, "constantes": cuerpo,
                "fuente": f.endpoint, "consultada_en": self._ahora()}

    # -------------------------------------------------- estado honesto
    def estado_integraciones(self) -> dict:
        return {
            "version_motor": CONNECTORS_VERSION,
            "fuentes": self.fuentes(),
            "biblioteca": ("inyectada" if self._biblioteca is not None
                           else "no_inyectada"),
            "yield_engine": ("cargador_inyectado"
                             if self._cargador_yield is not None
                             else "no_inyectado"),
            "nota": ("EXFOR otorga prioridad experimental (19.12); "
                     "SRIM alimenta al Yield Engine (19.10); NNDC "
                     "alimenta motores clínicos y logísticos (19.13); "
                     "sin fuente configurada/conectada las importaciones"
                     " devuelven 503 y nada se inventa")}
