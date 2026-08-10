"""Radiation Safety & Shielding Engine (EDS cap. 36).

Física de protección radiológica del MVP:

- **Shielding Manager (36.7)**: atenuación de fotones con factor de
  acumulación — I = I₀·B(μx)·e^(−μx), modelo de Taylor B = 1 + a·μx —
  y espesor requerido para una tasa de dosis objetivo. Coeficientes
  μ/ρ de referencia publicados (NIST XCOM) a 511 keV, documentados
  con su fuente; las nuevas versiones generan nuevas constantes,
  nunca se sobrescriben.
- **Tasa de dosis**: fuente puntual con constante gamma de ¹⁸F
  (Γ ≈ 0.143 µSv·m²/(GBq·h), referencia bibliográfica documentada).
- **Area Classification (36.8)**: zonificación por umbrales
  configurables y versionados (IAEA GSR Part 3 como referencia).
- **Contamination Manager (36.9)**: registro de mediciones de
  contaminación superficial vs límites (Bq/cm²).
- **Dosimetry Manager (36.10)**: dosis acumulada por trabajador vs
  límites ocupacionales (20 mSv/año, ICRP; referencia documentada).

Toda decisión queda auditada (36.22). Nada de esto sustituye a la
evaluación del Servicio de Protección Radiológica: son cálculos de
ingeniería con sus referencias explícitas.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

# Constantes documentadas (referencias públicas):
# - μ/ρ y ρ: NIST XCOM a 511 keV (0.511 MeV).
# - Γ 18F: 0.143 µSv·m²/(GBq·h) (referencia bibliográfica estándar).
GAMMA_F18_USV_M2_PER_GBQ_H = 0.143
LIMITE_OCUPACIONAL_MSV_ANO = 20.0   # ICRP / IAEA GSR Part 3
CONSTANTES_VERSION = "xcom-511kev-1.0.0"

# (mu_rho_cm2_g [NIST XCOM @511 keV], rho_g_cm3, coef Taylor a)
_MATERIALES: dict[str, dict] = {
    "plomo": {"mu_rho": 0.161, "rho": 11.34, "taylor_a": 0.30,
              "fuente": "NIST XCOM Pb @ 511 keV"},
    "hierro": {"mu_rho": 0.084, "rho": 7.874, "taylor_a": 0.45,
               "fuente": "NIST XCOM Fe @ 511 keV"},
    "hormigon": {"mu_rho": 0.087, "rho": 2.35, "taylor_a": 0.55,
                 "fuente": "NIST XCOM hormigón ordinario @ 511 keV"},
}

# Umbrales de zonificación (36.8): referencia IAEA GSR Part 3,
# configurables y versionados — nunca embebidos sin documentar.
UMBRALES_ZONA_VERSION = "zonificacion-gsr3-1.0.0"
ZONAS = (("zona_controlada", 7.5), ("zona_vigilada", 0.5),
         ("zona_publica", 0.0))  # µSv/h


class ProteccionInvalida(ValueError):
    """Material, parámetro o registro inválido (cap. 36)."""


def _material(nombre: str) -> dict:
    try:
        return _MATERIALES[nombre]
    except KeyError:
        raise ProteccionInvalida(
            f"material no registrado ({CONSTANTES_VERSION}): {nombre}")


def tasa_dosis_fuente_puntual(actividad_gbq: float, distancia_m: float
                              ) -> float:
    """µSv/h a distancia de una fuente puntual de ¹⁸F (Γ documentada)."""
    if actividad_gbq <= 0 or distancia_m <= 0:
        raise ProteccionInvalida("actividad y distancia deben ser > 0")
    return GAMMA_F18_USV_M2_PER_GBQ_H * actividad_gbq / distancia_m ** 2


def factor_buildup_taylor(mu_x: float, material: str) -> float:
    """B = 1 + a·μx (aproximación de Taylor, documentada)."""
    m = _material(material)
    return 1.0 + m["taylor_a"] * mu_x


def atenuacion(espesor_cm: float, material: str) -> float:
    """Fracción transmitida I/I₀ con buildup (36.7)."""
    if espesor_cm < 0:
        raise ProteccionInvalida("espesor negativo")
    m = _material(material)
    mu = m["mu_rho"] * m["rho"]  # cm⁻¹
    mu_x = mu * espesor_cm
    return factor_buildup_taylor(mu_x, material) * math.exp(-mu_x)


def espesor_requerido_cm(tasa_objetivo_usv_h: float, tasa_inicial_usv_h: float,
                         material: str) -> dict:
    """Espesor para reducir la tasa al objetivo (búsqueda exacta sobre
    el modelo con buildup, no aproximación TVL)."""
    if tasa_objetivo_usv_h <= 0 or tasa_inicial_usv_h <= 0:
        raise ProteccionInvalida("tasas deben ser > 0")
    if tasa_objetivo_usv_h >= tasa_inicial_usv_h:
        return {"espesor_cm": 0.0, "material": material,
                "nota": "el objetivo ya se cumple sin blindaje"}
    # bisección: atenuación monótona decreciente
    lo, hi = 0.0, 1.0
    while atenuacion(hi, material) * tasa_inicial_usv_h > tasa_objetivo_usv_h:
        hi *= 2.0
        if hi > 500.0:
            raise ProteccionInvalida("espesor no físico (>5 m)")
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if atenuacion(mid, material) * tasa_inicial_usv_h > tasa_objetivo_usv_h:
            lo = mid
        else:
            hi = mid
    m = _material(material)
    return {"espesor_cm": round(hi, 4), "material": material,
            "tasa_inicial_usv_h": tasa_inicial_usv_h,
            "tasa_objetivo_usv_h": tasa_objetivo_usv_h,
            "modelo": "I=I0·B(μx)·e^(−μx), Taylor",
            "fuente_constantes": m["fuente"],
            "version_constantes": CONSTANTES_VERSION}


def clasificar_area(tasa_usv_h: float) -> dict:
    """Zonificación 36.8 con umbrales versionados (GSR Part 3)."""
    if tasa_usv_h < 0:
        raise ProteccionInvalida("tasa negativa")
    for zona, umbral in ZONAS:
        if tasa_usv_h > umbral:
            return {"zona": zona, "tasa_usv_h": tasa_usv_h,
                    "umbrales_version": UMBRALES_ZONA_VERSION,
                    "referencia": "IAEA GSR Part 3 (umbrales configurables)"}
    return {"zona": "zona_publica", "tasa_usv_h": tasa_usv_h,
            "umbrales_version": UMBRALES_ZONA_VERSION,
            "referencia": "IAEA GSR Part 3 (umbrales configurables)"}


@dataclass
class MedicionContaminacion:
    punto: str
    bq_cm2: float
    limite_bq_cm2: float
    operador: str
    fecha: str = ""

    def evaluar(self) -> dict:
        if self.bq_cm2 < 0 or self.limite_bq_cm2 <= 0:
            raise ProteccionInvalida("medición o límite inválido (36.9)")
        supera = self.bq_cm2 > self.limite_bq_cm2
        return {"punto": self.punto, "bq_cm2": self.bq_cm2,
                "limite_bq_cm2": self.limite_bq_cm2,
                "estado": "supera_limite" if supera else "conforme",
                "fecha": self.fecha
                or datetime.now(timezone.utc).isoformat(),
                "nota": "Contamination Manager 36.9: registro auditado; "
                        "las acciones correctoras siguen el procedimiento "
                        "del SPR"}


@dataclass
class DosimetryRecord:
    """Dosimetry Manager (36.10): acumulación por trabajador."""
    trabajador_id: str
    dosis_msv: float
    periodo: str                  # p. ej. "2026-08"
    fecha: str = ""


class DosimetryManager:
    """Registro y control de dosis ocupacionales (36.10/36.22)."""

    def __init__(self, limite_ano_msv: float = LIMITE_OCUPACIONAL_MSV_ANO
                 ) -> None:
        self._limite = limite_ano_msv
        self._registros: list[DosimetryRecord] = []

    def registrar(self, rec: DosimetryRecord) -> dict:
        if rec.dosis_msv < 0:
            raise ProteccionInvalida("dosis negativa")
        rec.fecha = rec.fecha or datetime.now(timezone.utc).isoformat()
        self._registros.append(rec)
        return {"trabajador_id": rec.trabajador_id,
                "dosis_msv": rec.dosis_msv, "fecha": rec.fecha,
                "nota": "registro dosimétrico auditado (36.22)"}

    def dosis_acumulada(self, trabajador_id: str, ano: str) -> dict:
        total = sum(r.dosis_msv for r in self._registros
                    if r.trabajador_id == trabajador_id
                    and r.periodo.startswith(ano))
        fraccion = total / self._limite
        return {"trabajador_id": trabajador_id, "ano": ano,
                "dosis_acumulada_msv": round(total, 4),
                "limite_ano_msv": self._limite,
                "fraccion_limite": round(fraccion, 4),
                "estado": ("supera_limite" if total > self._limite else
                           "investigacion" if fraccion > 0.6 else "conforme"),
                "referencia": "ICRP / IAEA GSR Part 3 (20 mSv/año)"}

    def registros(self) -> list[dict]:
        return [{"trabajador_id": r.trabajador_id, "dosis_msv": r.dosis_msv,
                 "periodo": r.periodo, "fecha": r.fecha}
                for r in self._registros]
