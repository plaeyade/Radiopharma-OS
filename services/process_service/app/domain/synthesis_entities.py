"""
Entidades del Process Twin químico (EDS Vol. II, caps. 21-24).

Reaction Engine (cap. 22), Purification Engine (cap. 23) y
Formulation Engine (caps. 21.13/24): protocolos completamente
versionados (22.6, 23.6, 24.6), reactivos con trazabilidad
(22.7/21.10), etapas con parámetros independientes (22.8).
"""
from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------- reactivos
@dataclass(frozen=True)
class Reagent:
    """Reactivo registrado (22.7): trazabilidad durante el Batch."""
    nombre: str
    concentracion: str
    volumen_ml: float
    pureza: str
    lote: str
    caducidad: str  # ISO date; 22.22 exige verificar disponibilidad


# ---------------------------------------------------------------- térmico
@dataclass(frozen=True)
class ThermalProfile:
    """Perfil térmico asociado a la versión del protocolo (22.10)."""
    t_objetivo_c: float
    rampa_calentamiento_c_min: float
    t_mantenimiento_min: float
    rampa_enfriamiento_c_min: float


# ---------------------------------------------------------------- cinética
@dataclass(frozen=True)
class KineticParams:
    """Parámetros del Kinetic Solver (22.9).

    modelo 'primer_orden': conversion(t) = conversion_max * (1 - exp(-k*T))
    con k(T) = k_ref * exp(-Ea/R * (1/T - 1/Tref)) si ea_j_mol > 0
    (dependencia térmica de Arrhenius, modelo fenomenológico 22.9).
    """
    modelo: str  # 'primer_orden' (único registrado en el MVP)
    conversion_max: float          # límite asintótico (0-1]
    k_ref_min_inv: float           # constante aparente a t_ref
    t_ref_c: float = 25.0
    ea_j_mol: float = 0.0          # 0 => k independiente de T


# ---------------------------------------------------------------- etapas
ETAPAS_REACCION = ("carga", "mezcla", "calentamiento", "reaccion",
                   "enfriamiento", "transferencia")  # 22.8


@dataclass(frozen=True)
class ReactionStep:
    """Etapa de la secuencia de reacción (22.8).

    efficiency: fracción de actividad que sobrevive a la etapa por
    pérdidas físicas/químicas (transferencias, retención en líneas).
    La etapa 'reaccion' aplica además la conversión cinética (22.12).
    """
    kind: str
    duration_min: float
    efficiency: float = 1.0
    params: dict | None = None


@dataclass(frozen=True)
class ReactionProtocol:
    """Protocolo de síntesis versionado (22.6)."""
    protocol_id: str
    version: str
    radiopharmaceutical: str
    nuclide: str
    half_life_min: float
    reagents: tuple[Reagent, ...]
    steps: tuple[ReactionStep, ...]
    thermal: ThermalProfile | None
    kinetic: KineticParams | None
    validated: bool
    source: str


# ---------------------------------------------------------------- resultados
@dataclass(frozen=True)
class ReactionStageResult:
    """Control temporal + actividad por etapa (22.11)."""
    kind: str
    inicio_min: float
    fin_min: float
    duration_min: float
    activity_in_gbq: float
    activity_after_decay_gbq: float
    activity_out_gbq: float
    efficiency: float
    detalle: dict | None = None


@dataclass(frozen=True)
class ReactionResult:
    """Salida del Reaction Engine (22.12/22.17)."""
    protocol_id: str
    version: str
    radiopharmaceutical: str
    nuclide: str
    half_life_min: float
    eob_activity_gbq: float
    final_activity_gbq: float
    conversion: float | None
    rendimiento_quimico: float
    perdidas_reaccion_gbq: float
    eficiencia_global: float
    total_time_min: float
    incertidumbre_inicial_rel: float
    incertidumbre_final_gbq: float
    validated: bool
    stages: tuple[ReactionStageResult, ...]
    auditoria: dict
