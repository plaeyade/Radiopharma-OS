"""Activación neutrónica — Bateman por isótopo (Fase 28).

Inventario de activación de materiales de instalación (muros del
búnker, foil Havar, componentes) a partir de captura neutrónica:

    A(t) = N · σ̄ · φ · (1 − e^(−λ·t_irr)) · e^(−λ·t_dec)

con calendario de PULSOS de irradiación (lotes FDG) y decaimiento entre
pulsos — suma exacta pulso a pulso, nunca un factor continuo inventado.

Reglas canónicas:

- 49.11: σ̄ y T½ con fuente citada DECLARADA en cada registro (ENDF /
  literatura medida / ENSDF). El catálogo de culpables típicos trae las
  fuentes; un isótopo sin fuente no entra al cálculo.
- El flujo φ exige `origen_flujo`: si no proviene de un mesh tally MC
  real, el cálculo queda marcado `flujo_declarado_pendiente_mesh_tally`
  — el tablero lo muestra, nunca lo oculta (honestidad 18.x).
- Cálculos append-only con auditoría ALCOA+; nunca se sobrescriben.

Culpables típicos precargados (valores térmicos, fuente citada):
- ⁵⁹Co(n,γ)⁶⁰Co — σ = 37.18 b (ENDF/B-VI R8, evaluación estándar
  2200 m/s; OSTI 20332542).
- ¹⁵¹Eu(n,γ)¹⁵²Eu — σ = 9051 ± 683 b medida (Lee et al. 2017,
  Nucl. Sci. Eng., 0.0253 eV).
- ¹⁵³Eu(n,γ)¹⁵⁴Eu — σ = 364 b medida (misma referencia).
- ²³Na(n,γ)²⁴Na — σ = 0.53 ± 0.03 b (método de activación,
  Nucl. Phys. A; ver también tablas ENDF).
- ⁵⁵Mn(n,γ)⁵⁶Mn — σ = 12.7 ± 0.3 b (misma referencia).
T½ declaradas con fuente ENSDF/IAEA LiveChart (valores estándar).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

ACTIVATION_VERSION = "activation-1.0.0"

ANIO_S = 365.25 * 86400.0
HORA_S = 3600.0
DIA_S = 86400.0


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


class ActivacionInvalida(ValueError):
    """Entrada de cálculo de activación inválida."""


# Catálogo de culpables típicos — σ térmica (2200 m/s) con fuente citada.
CULPABLES: dict[str, dict] = {
    "Co-60": {
        "padre": "Co-59", "reaccion": "(n,gamma)",
        "sigma_b": 37.18, "sigma_inc_b": 0.2,
        "fuente_sigma": "ENDF/B-VI R8, sección térmica 2200 m/s "
                        "(OSTI 20332542)",
        "t12_s": 5.2713 * ANIO_S,
        "fuente_t12": "ENSDF / IAEA LiveChart (5.2713 a) — declarada",
        "contexto": "foil Havar (aleación base Co) y aceros — domina el "
                    "residuo a largo plazo",
    },
    "Eu-152": {
        "padre": "Eu-151", "reaccion": "(n,gamma)",
        "sigma_b": 9051.0, "sigma_inc_b": 683.0,
        "fuente_sigma": "Lee et al. 2017, Nucl. Sci. Eng. — medida a "
                        "0.0253 eV (9051 ± 683 b)",
        "t12_s": 13.517 * ANIO_S,
        "fuente_t12": "ENSDF / IAEA LiveChart (13.517 a) — declarada",
        "contexto": "trazas de Eu en concreto — culpable #1 de muros a "
                    "largo plazo",
    },
    "Eu-154": {
        "padre": "Eu-153", "reaccion": "(n,gamma)",
        "sigma_b": 364.0, "sigma_inc_b": None,
        "fuente_sigma": "Lee et al. 2017, Nucl. Sci. Eng. — medida a "
                        "0.0253 eV (364 b)",
        "t12_s": 8.593 * ANIO_S,
        "fuente_t12": "ENSDF / IAEA LiveChart (8.593 a) — declarada",
        "contexto": "trazas de Eu en concreto — largo plazo",
    },
    "Na-24": {
        "padre": "Na-23", "reaccion": "(n,gamma)",
        "sigma_b": 0.53, "sigma_inc_b": 0.03,
        "fuente_sigma": "método de activación (Nucl. Phys. A; 0.53 ± "
                        "0.03 b) — ver tablas ENDF",
        "t12_s": 14.959 * HORA_S,
        "fuente_t12": "ENSDF / IAEA LiveChart (14.959 h) — declarada",
        "contexto": "concreto — domina la dosis de entrada en las "
                    "primeras horas tras apagar",
    },
    "Mn-56": {
        "padre": "Mn-55", "reaccion": "(n,gamma)",
        "sigma_b": 12.7, "sigma_inc_b": 0.3,
        "fuente_sigma": "método de activación (Nucl. Phys. A; 12.7 ± "
                        "0.3 b) — ver tablas ENDF",
        "t12_s": 2.5789 * HORA_S,
        "fuente_t12": "ENSDF / IAEA LiveChart (2.5789 h) — declarada",
        "contexto": "aceros y concreto — primeras horas tras apagar",
    },
}


@dataclass
class CalculoActivacion:
    """Entrada de un cálculo de activación (append-only)."""
    calculo_id: str
    isotopo: str               # clave de CULPABLES o isótopo declarado
    n_nucleos_padre: float     # núcleos blanco en el volumen considerado
    flujo_n_cm2_s: float       # φ en la superficie/volumen
    origen_flujo: str          # "mesh_tally:..." | declaración honesta
    t_pulso_s: float           # duración de un pulso de irradiación
    n_pulsos: int              # lotes acumulados (vida de la instalación)
    t_entre_pulsos_s: float    # decaimiento entre pulsos
    t_enfriamiento_s: float = 0.0
    motivo: str = ""
    # para isótopos fuera del catálogo (σ y T½ declaradas con fuente):
    sigma_b: float | None = None
    fuente_sigma: str = ""
    t12_s: float | None = None
    fuente_t12: str = ""


class ActivationEngine:
    """Bateman por isótopo con calendario de pulsos (append-only)."""

    def __init__(self) -> None:
        self._calculos: list[dict] = []
        self._audit: list[dict] = []

    def _auditar(self, usuario: str, accion: str, detalle: str) -> None:
        self._audit.append({"ts": _ahora(), "usuario": usuario,
                            "accion": accion, "detalle": detalle})

    def auditoria(self) -> list[dict]:
        return list(self._audit)

    def culpables(self) -> dict[str, dict]:
        return {k: dict(v) for k, v in CULPABLES.items()}

    # ------------------------------------------------------ núcleo
    @staticmethod
    def actividad_tras_pulsos(n_padre: float, sigma_b: float,
                              phi: float, t12_s: float,
                              t_pulso_s: float, n_pulsos: int,
                              t_entre_pulsos_s: float,
                              t_enfriamiento_s: float = 0.0) -> float:
        """Actividad [Bq] exacta: suma de pulsos con decaimiento real.

        Pulso i produce P·(1−e^(−λ·t_p)) y decae durante los pulsos y
        pausas posteriores hasta el final + enfriamiento.
        """
        lam = math.log(2.0) / t12_s
        sigma_cm2 = sigma_b * 1e-24
        produccion_sat = n_padre * sigma_cm2 * phi          # Bq en saturación
        ganancia = produccion_sat * (-math.expm1(-lam * t_pulso_s))
        a = 0.0
        for _ in range(n_pulsos):
            # fin de pulso → pausa (t_e) → pulso siguiente (decae también
            # durante el pulso mientras se produce) — recurrencia exacta
            a = a * math.exp(-lam * (t_entre_pulsos_s + t_pulso_s)) + ganancia
        return a * math.exp(-lam * t_enfriamiento_s)

    @staticmethod
    def curva_enfriamiento(a_apagado_bq: float, t12_s: float,
                           puntos_s: list[float]) -> list[dict]:
        lam = math.log(2.0) / t12_s
        return [{"t_s": t, "actividad_bq": a_apagado_bq * math.exp(-lam * t)}
                for t in puntos_s]

    # ----------------------------------------------------- registro
    def calcular(self, c: CalculoActivacion, usuario: str) -> dict:
        if c.calculo_id in {x["calculo_id"] for x in self._calculos}:
            raise ActivacionInvalida(
                f"calculo {c.calculo_id} ya registrado — nunca se "
                "sobrescribe")
        if c.n_nucleos_padre <= 0 or c.flujo_n_cm2_s <= 0:
            raise ActivacionInvalida(
                "n_nucleos_padre y flujo_n_cm2_s deben ser > 0")
        if c.t_pulso_s <= 0 or c.n_pulsos <= 0 or c.t_entre_pulsos_s < 0:
            raise ActivacionInvalida("calendario de pulsos inválido")
        if not c.origen_flujo.strip():
            raise ActivacionInvalida(
                "origen_flujo obligatorio — si no es mesh tally MC real "
                "se declara y el cálculo queda marcado")
        if c.isotopo in CULPABLES:
            cat = CULPABLES[c.isotopo]
            sigma_b, fuente_sigma = cat["sigma_b"], cat["fuente_sigma"]
            t12_s, fuente_t12 = cat["t12_s"], cat["fuente_t12"]
        else:
            if not (c.sigma_b and c.sigma_b > 0 and c.fuente_sigma.strip()
                    and c.t12_s and c.t12_s > 0 and c.fuente_t12.strip()):
                raise ActivacionInvalida(
                    "isótopo fuera de catálogo: sigma_b y t12_s con sus "
                    "fuentes son obligatorios (49.11)")
            sigma_b, fuente_sigma = c.sigma_b, c.fuente_sigma
            t12_s, fuente_t12 = c.t12_s, c.fuente_t12
        es_mc = c.origen_flujo.startswith("mesh_tally:")
        a_apagado = self.actividad_tras_pulsos(
            c.n_nucleos_padre, sigma_b, c.flujo_n_cm2_s, t12_s,
            c.t_pulso_s, c.n_pulsos, c.t_entre_pulsos_s, 0.0)
        a_final = self.actividad_tras_pulsos(
            c.n_nucleos_padre, sigma_b, c.flujo_n_cm2_s, t12_s,
            c.t_pulso_s, c.n_pulsos, c.t_entre_pulsos_s,
            c.t_enfriamiento_s)
        lam = math.log(2.0) / t12_s
        a_sat = (c.n_nucleos_padre * sigma_b * 1e-24 * c.flujo_n_cm2_s
                 * (-math.expm1(-lam * c.t_pulso_s))
                 / (1.0 - math.exp(-lam * (c.t_pulso_s
                                           + c.t_entre_pulsos_s))))
        reg = {
            "calculo_id": c.calculo_id,
            "isotopo": c.isotopo,
            "sigma_b": sigma_b, "fuente_sigma": fuente_sigma,
            "t12_s": t12_s, "fuente_t12": fuente_t12,
            "n_nucleos_padre": c.n_nucleos_padre,
            "flujo_n_cm2_s": c.flujo_n_cm2_s,
            "origen_flujo": c.origen_flujo,
            "estado_flujo": ("flujo_mc_real" if es_mc else
                             "flujo_declarado_pendiente_mesh_tally"),
            "calendario": {"t_pulso_s": c.t_pulso_s,
                           "n_pulsos": c.n_pulsos,
                           "t_entre_pulsos_s": c.t_entre_pulsos_s},
            "actividad_apagado_bq": a_apagado,
            "actividad_tras_enfriamiento_bq": a_final,
            "t_enfriamiento_s": c.t_enfriamiento_s,
            "actividad_equilibrio_bq": a_sat,
            "fraccion_saturacion": (a_apagado / a_sat) if a_sat > 0 else 0.0,
            "motivo": c.motivo,
            "ts": _ahora(),
            "version_modelo": ACTIVATION_VERSION,
        }
        self._calculos.append(reg)
        self._auditar(usuario, "calcular_activacion",
                      f"{c.calculo_id} {c.isotopo} A={a_apagado:.3e} Bq")
        return dict(reg)

    def calculos(self) -> list[dict]:
        return [dict(x) for x in self._calculos]
