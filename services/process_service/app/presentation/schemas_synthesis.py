"""
Schemas REST del Process Twin químico (caps. 22-24).
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class ReactionIn(BaseModel):
    protocol_id: str
    eob_activity_gbq: float = Field(..., gt=0)
    incertidumbre_inicial_rel: float = Field(0.0, ge=0, lt=1)
    operador: str = Field(..., min_length=1)
    motivo: str = ""
    lote: str = ""
    fecha_lote: date | None = None


class ReactionStageOut(BaseModel):
    kind: str
    inicio_min: float
    fin_min: float
    duration_min: float
    activity_in_gbq: float
    activity_after_decay_gbq: float
    activity_out_gbq: float
    efficiency: float
    detalle: dict | None


class ReactionOut(BaseModel):
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
    stages: list[ReactionStageOut]
    auditoria: dict


class PurificationIn(BaseModel):
    protocol_id: str
    input_activity_gbq: float = Field(..., gt=0)
    impurezas_iniciales: dict[str, float] = Field(default_factory=dict)
    operador: str = Field(..., min_length=1)
    motivo: str = ""
    lote: str = ""


class PurificationStageOut(BaseModel):
    kind: str
    duration_min: float
    activity_in_gbq: float
    activity_after_decay_gbq: float
    activity_out_gbq: float
    recovery: float


class PurificationOut(BaseModel):
    protocol_id: str
    version: str
    radiopharmaceutical: str
    input_activity_gbq: float
    final_activity_gbq: float
    producto_recuperado_gbq: float
    perdidas_acumuladas_gbq: float
    eficiencia_recuperacion: float
    total_time_min: float
    impurezas_iniciales: dict
    impurezas_remanentes: dict
    validated: bool
    stages: list[PurificationStageOut]
    auditoria: dict


class FormulationIn(BaseModel):
    protocol_id: str
    input_activity_gbq: float = Field(..., gt=0)
    input_volumen_ml: float = Field(..., gt=0)
    operador: str = Field(..., min_length=1)
    motivo: str = ""
    lote: str = ""
    fecha_lote: date | None = None


class FormulationOut(BaseModel):
    protocol_id: str
    version: str
    radiopharmaceutical: str
    input_activity_gbq: float
    input_volumen_ml: float
    final_activity_gbq: float
    volumen_final_ml: float
    concentracion_final_gbq_ml: float
    factor_dilucion: float
    duration_min: float
    validated: bool
    excipientes_aplicados: list[str]
    auditoria: dict


class SynthesisE2EIn(BaseModel):
    reaction_id: str
    purification_id: str
    formulation_id: str
    eob_activity_gbq: float = Field(..., gt=0)
    incertidumbre_inicial_rel: float = Field(0.0, ge=0, lt=1)
    volumen_crudo_ml: float = Field(3.0, gt=0)
    impurezas_iniciales: dict[str, float] = Field(default_factory=dict)
    operador: str = Field(..., min_length=1)
    motivo: str = ""
    lote: str = ""
    fecha_lote: date | None = None


class SynthesisProtocolSummaryOut(BaseModel):
    kind: str
    protocol_id: str
    version: str
    radiopharmaceutical: str
    validated: bool
    source: str
