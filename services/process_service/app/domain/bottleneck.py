"""
Análisis de cuello de botella del Process Twin (F2).

Para cada paso cuantifica:
  - pérdida por decaimiento (GBq) y pérdida por eficiencia (GBq),
  - ganancia de EOS si el paso fuese 1 min más rápido,
  - ganancia de EOS si su eficiencia mejorase 1 punto porcentual.

Propiedad útil: la ganancia por minuto es idéntica en todos los pasos
(solo depende de T½): EOS·(2^(1/T½) - 1). La ganancia por punto de
eficiencia es mayor donde η es menor — ahí está el cuello de botella.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.entities import Protocol, ProtocolStep
from app.domain.process_chain import simulate_chain


@dataclass(frozen=True)
class StepBottleneck:
    name: str
    loss_gbq: float            # entrada - salida
    decay_loss_gbq: float      # pérdida por decaimiento
    efficiency_loss_gbq: float # pérdida por rendimiento del paso
    eos_gain_1min_faster_gbq: float
    eos_gain_1pp_efficiency_gbq: float


@dataclass(frozen=True)
class BottleneckResult:
    protocol_id: str
    nuclide: str
    eob_activity_gbq: float
    eos_activity_gbq: float
    total_loss_gbq: float
    dominant_loss_step: str
    steps: tuple[StepBottleneck, ...]


def bottleneck_analysis(protocol: Protocol,
                        eob_activity_gbq: float) -> BottleneckResult:
    base = simulate_chain(protocol, eob_activity_gbq)

    analyses: list[StepBottleneck] = []
    for i, step in enumerate(protocol.steps):
        s = base.steps[i]
        decay_loss = s.activity_in_gbq - s.activity_after_decay_gbq
        eff_loss = s.activity_after_decay_gbq - s.activity_out_gbq

        # sensibilidad temporal: 1 min menos en este paso
        if step.duration_min >= 1.0:
            faster = list(protocol.steps)
            faster[i] = ProtocolStep(step.name, step.duration_min - 1.0,
                                     step.efficiency)
            gain_time = (simulate_chain(
                protocol.__class__(**{**protocol.__dict__,
                                      "steps": tuple(faster)}),
                eob_activity_gbq).eos_activity_gbq
                - base.eos_activity_gbq)
        else:
            gain_time = 0.0

        # sensibilidad de eficiencia: +1 pp en este paso (tope 1.0)
        if step.efficiency < 1.0:
            better = list(protocol.steps)
            better[i] = ProtocolStep(step.name, step.duration_min,
                                     min(1.0, step.efficiency + 0.01))
            gain_eff = (simulate_chain(
                protocol.__class__(**{**protocol.__dict__,
                                      "steps": tuple(better)}),
                eob_activity_gbq).eos_activity_gbq
                - base.eos_activity_gbq)
        else:
            gain_eff = 0.0

        analyses.append(StepBottleneck(
            name=step.name,
            loss_gbq=s.activity_in_gbq - s.activity_out_gbq,
            decay_loss_gbq=decay_loss,
            efficiency_loss_gbq=eff_loss,
            eos_gain_1min_faster_gbq=gain_time,
            eos_gain_1pp_efficiency_gbq=gain_eff))

    dominant = max(analyses, key=lambda a: a.loss_gbq)
    return BottleneckResult(
        protocol_id=protocol.protocol_id,
        nuclide=protocol.nuclide,
        eob_activity_gbq=eob_activity_gbq,
        eos_activity_gbq=base.eos_activity_gbq,
        total_loss_gbq=eob_activity_gbq - base.eos_activity_gbq,
        dominant_loss_step=dominant.name,
        steps=tuple(analyses))
