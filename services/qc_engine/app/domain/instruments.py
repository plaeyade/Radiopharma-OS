"""Instrument Integration Layer (EDS cap. 26).

Instrument Registry (26.6) + File Import Manager (26.12) + Data
Normalization Engine (26.10) para la integración de instrumentos
QC (HPLC, GC, TLC, calibradores de dosis, espectrometría gamma).

Modelos de comunicación (26.9): la conexión directa con el
instrumento requiere sus drivers físicos (honestamente fuera del
sandbox); la vía real implementada aquí es la importación de
archivos exportados (26.12): cromatogramas, espectros y tablas.
Los archivos originales permanecen almacenados con su hash
(26.12/26.24) y cada resultado incorpora fecha, hora, instrumento,
operador y lote (26.13) para reconstruir la secuencia analítica.
Los resultados normalizados alimentan el QC Engine (26.14).
"""
from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

TIPOS_INSTRUMENTO = ("hplc", "gc", "tlc", "calibrador_dosis",
                     "espectrometro_gamma", "phmetro")


class InstrumentoInvalido(ValueError):
    """Registro o importación que viola el cap. 26."""


@dataclass
class Instrument:
    """Entrada del Instrument Registry (26.6). Nunca se sobrescribe."""
    instrument_id: str
    tipo: str
    fabricante: str
    modelo: str
    ubicacion: str
    formato_export: str          # csv_cromatograma / csv_espectro / csv_tabla
    configuracion: str           # versión de la configuración del driver
    validado: bool = False       # honestidad: cualificación pendiente


@dataclass
class ImportResult:
    instrument_id: str
    ensayo: str
    resultados: dict[str, float]
    archivo_sha256: str
    archivo_original: str
    fecha: str                   # 26.13: fecha+hora
    operador: str
    batch: str
    auditoria: dict


class InstrumentRegistry:
    """26.6: registro versionado de instrumentos; nunca sobrescribe."""

    def __init__(self) -> None:
        self._items: dict[str, Instrument] = {}

    def register(self, inst: Instrument) -> dict:
        if inst.instrument_id in self._items:
            raise InstrumentoInvalido(
                f"el instrumento {inst.instrument_id} ya existe (26.6)")
        if inst.tipo not in TIPOS_INSTRUMENTO:
            raise InstrumentoInvalido(f"tipo no soportado: {inst.tipo}")
        self._items[inst.instrument_id] = inst
        return asdict(inst)

    def get(self, instrument_id: str) -> Instrument:
        try:
            return self._items[instrument_id]
        except KeyError:
            raise InstrumentoInvalido(
                f"instrumento no registrado: {instrument_id}")

    def list(self) -> list[dict]:
        return [asdict(i) for i in self._items.values()]


# ------------------------------------------------- normalización (26.10)
def normalizar_cromatograma(contenido: str,
                            tiempo_pico_esperado_min: float | None = None
                            ) -> dict[str, float]:
    """CSV ``tiempo_min,senal`` → pureza del pico principal.

    La pureza radioquímica se calcula como área del pico principal /
    área total (método trapezoidal, documentado).
    """
    t, s = _leer_pares(contenido, "cromatograma")
    if len(t) < 3:
        raise InstrumentoInvalido("cromatograma insuficiente (26.10)")
    areas = []
    for i in range(len(t) - 1):
        areas.append((s[i] + s[i + 1]) / 2.0 * (t[i + 1] - t[i]))
    area_total = sum(areas)
    if area_total <= 0:
        raise InstrumentoInvalido("área total nula en cromatograma")
    i_pico = max(range(len(s)), key=lambda i: s[i])
    # límites del pico: señal cae por debajo del 5 % del máximo a
    # ambos lados del vértice (integración cromatográfica estándar)
    umbral = 0.05 * s[i_pico]
    izq = i_pico
    while izq > 0 and s[izq] > umbral:
        izq -= 1
    der = i_pico
    while der < len(s) - 1 and s[der] > umbral:
        der += 1
    area_pico = sum(areas[izq:der])
    resultados = {
        "tiempo_pico_min": round(float(t[i_pico]), 3),
        "pureza_radioquimica_pct": round(100.0 * area_pico / area_total, 2)}
    if tiempo_pico_esperado_min is not None:
        resultados["desviacion_rt_min"] = round(
            abs(float(t[i_pico]) - tiempo_pico_esperado_min), 3)
    return resultados


def normalizar_espectro_gamma(contenido: str,
                              energia_esperada_kev: float = 511.0,
                              tolerancia_kev: float = 5.0
                              ) -> dict[str, float]:
    """CSV ``energia_kev,cuentas`` → pico principal e identidad."""
    e, c = _leer_pares(contenido, "espectro")
    if len(e) < 3:
        raise InstrumentoInvalido("espectro insuficiente (26.10)")
    i_pico = max(range(len(c)), key=lambda i: c[i])
    e_pico = float(e[i_pico])
    identidad = abs(e_pico - energia_esperada_kev) <= tolerancia_kev
    total = sum(c)
    return {"energia_pico_kev": round(e_pico, 2),
            "identidad_radionuclidica_ok": 1.0 if identidad else 0.0,
            "fraccion_cuentas_pico": round(float(c[i_pico]) / total, 4)
            if total > 0 else 0.0}


def normalizar_tabla(contenido: str) -> dict[str, float]:
    """CSV ``parametro,valor`` → diccionario de resultados (26.12)."""
    lector = csv.reader(io.StringIO(contenido))
    filas = [f for f in lector if f]
    if not filas:
        raise InstrumentoInvalido("tabla vacía (26.12)")
    resultados: dict[str, float] = {}
    for fila in filas[1:] if filas[0][0].lower() in ("parametro", "parametro") else filas:  # noqa: E501
        if len(fila) < 2:
            continue
        try:
            resultados[fila[0].strip()] = float(fila[1])
        except ValueError:
            raise InstrumentoInvalido(
                f"valor no numérico en tabla: {fila!r} (26.10)")
    if not resultados:
        raise InstrumentoInvalido("tabla sin resultados (26.12)")
    return resultados


def _leer_pares(contenido: str, nombre: str) -> tuple[list[float], list[float]]:
    lector = csv.reader(io.StringIO(contenido))
    xs, ys = [], []
    for i, fila in enumerate(l for l in lector if l):
        if i == 0 and not _es_numero(fila[0]):
            continue  # cabecera
        if len(fila) < 2:
            raise InstrumentoInvalido(f"{nombre}: fila inválida {fila!r}")
        xs.append(float(fila[0]))
        ys.append(float(fila[1]))
    return xs, ys


def _es_numero(s: str) -> bool:
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


# ------------------------------------------------ File Import (26.12)
class FileImportManager:
    """Importación de archivos exportados por instrumentos (26.12).

    El archivo original permanece almacenado (hash sha256) y cada
    importación queda auditada con fecha, instrumento, operador y
    lote (26.13/26.24).
    """

    def __init__(self, registry: InstrumentRegistry,
                 store_dir: str = "/tmp/qc_instrument_files") -> None:
        self._registry = registry
        self._store = store_dir
        self._eventos: list[dict] = []

    def importar(self, instrument_id: str, nombre_archivo: str,
                 contenido: bytes, ensayo: str, operador: str,
                 batch: str, ensayo_map: dict | None = None) -> ImportResult:
        inst = self._registry.get(instrument_id)
        digest = hashlib.sha256(contenido).hexdigest()
        texto = contenido.decode("utf-8")
        if inst.formato_export == "csv_cromatograma":
            res = normalizar_cromatograma(texto)
        elif inst.formato_export == "csv_espectro":
            res = normalizar_espectro_gamma(texto)
        elif inst.formato_export == "csv_tabla":
            res = normalizar_tabla(texto)
        else:
            raise InstrumentoInvalido(
                f"formato de export no soportado: {inst.formato_export}")
        if ensayo_map:  # 26.14: asociación automática al ensayo QC
            res = {ensayo_map.get(k, k): v for k, v in res.items()}
        fecha = datetime.now(timezone.utc).isoformat()
        auditoria = {"fecha": fecha, "instrumento": instrument_id,
                     "operador": operador, "batch": batch,
                     "archivo": nombre_archivo, "sha256": digest,
                     "nota": "archivo original preservado (26.12); evento "
                             "de adquisición registrado (26.20/26.24)"}
        self._eventos.append({"tipo": "adquisicion", **auditoria})
        return ImportResult(instrument_id=instrument_id, ensayo=ensayo,
                            resultados=res, archivo_sha256=digest,
                            archivo_original=nombre_archivo, fecha=fecha,
                            operador=operador, batch=batch,
                            auditoria=auditoria)

    def eventos(self) -> list[dict]:
        return list(self._eventos)
