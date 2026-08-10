"""Financial Forecasting & Scenario Analysis Engine (EDS cap. 40).

Proyección financiera sobre ESCENARIOS (40.3): el motor nunca modifica
registros contables, costes históricos ni la producción real.

- **Scenario Manager (40.6)**: escenarios versionados, nunca alteran
  datos históricos.
- **Forecast Engine (40.7)**: proyección mensual determinista de
  ingresos, costes y margen sobre el horizonte; modelo documentado:
  demanda_t = demanda_0·(1+g)^t; ingresos_t = demanda_t·precio;
  costes_t = demanda_t·coste_dosis + coste_fijo.
- **Sensitivity Analyzer (40.8)**: elasticidad de resultados ante
  variaciones de un parámetro, asociada al escenario.
- **Investment Evaluator (40.9)**: payback, VAN y ROI con fórmulas
  explícitas; PROPUESTA de soporte a la decisión (41.9).
- **Risk Analyzer (40.10)**: impacto de eventos adversos respecto al
  escenario base.
- **KPI Generator (40.11)**: rentabilidad y crecimiento.

Validación 40.20: escenarios incompletos o incoherentes, rechazados.
Auditoría 40.22 en todas las ejecuciones.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

FFSAE_VERSION = "ffsae-1.0.0"

PARAMETROS_SENSIBLES = ("demanda_mensual_dosis", "precio_dosis",
                        "coste_por_dosis", "coste_fijo_mensual",
                        "crecimiento_mensual_pct")


class FinanzasInvalidas(ValueError):
    """Escenario financiero incompleto o incoherente (40.20)."""


@dataclass
class EscenarioFinanciero:
    """Escenario financiero (40.6): aislado de la operación real."""
    escenario_id: str
    hipotesis: str
    demanda_mensual_dosis: float
    precio_dosis: float
    coste_por_dosis: float          # del ABC Engine 39.12 (40.13)
    coste_fijo_mensual: float
    crecimiento_mensual_pct: float = 0.0
    horizonte_meses: int = 12
    version: str = "esc-fin-1.0.0"
    fecha: str = ""


class FinancialForecastEngine:
    """FFSAE: proyecciones deterministas, escenarios aislados,
    propuestas documentadas (nunca decisiones)."""

    def __init__(self) -> None:
        self._escenarios: dict[str, EscenarioFinanciero] = {}
        self._resultados: dict[str, list[dict]] = {}
        self._auditoria: list[dict] = []

    def _auditar(self, usuario: str, accion: str, detalle: str) -> None:
        self._auditoria.append({"usuario": usuario, "accion": accion,
                                "detalle": detalle,
                                "fecha": datetime.now(
                                    timezone.utc).isoformat()})

    def auditoria(self) -> list[dict]:
        return list(self._auditoria)

    # -------------------------------------------------- escenarios 40.6
    def registrar_escenario(self, esc: EscenarioFinanciero,
                            usuario: str) -> dict:
        if esc.escenario_id in self._escenarios:
            raise FinanzasInvalidas(           # nunca sobrescribe
                f"escenario ya registrado: {esc.escenario_id}")
        self._validar(esc)
        esc.fecha = esc.fecha or datetime.now(timezone.utc).isoformat()
        self._escenarios[esc.escenario_id] = esc
        self._auditar(usuario, "registrar_escenario",
                      f"{esc.escenario_id} v{esc.version}")
        return {"escenario_id": esc.escenario_id, "version": esc.version,
                "nota": "escenario aislado: nunca altera registros "
                        "contables ni datos históricos (40.3)"}

    def _validar(self, esc: EscenarioFinanciero) -> None:
        if not esc.hipotesis:
            raise FinanzasInvalidas("hipótesis obligatoria (40.6)")
        if esc.demanda_mensual_dosis < 0 or esc.precio_dosis <= 0:
            raise FinanzasInvalidas("demanda/precio inválidos (40.20)")
        if esc.coste_por_dosis < 0 or esc.coste_fijo_mensual < 0:
            raise FinanzasInvalidas("costes negativos (40.20)")
        if not (1 <= esc.horizonte_meses <= 360):
            raise FinanzasInvalidas("horizonte fuera de [1, 360] meses")
        if esc.crecimiento_mensual_pct <= -100.0:
            raise FinanzasInvalidas("crecimiento mensual ≤ −100 %")

    def escenarios(self) -> list[dict]:
        return [{"escenario_id": e.escenario_id, "hipotesis": e.hipotesis,
                 "version": e.version, "fecha": e.fecha,
                 "horizonte_meses": e.horizonte_meses}
                for e in self._escenarios.values()]

    # ------------------------------------------------- proyección 40.7
    def _proyectar(self, esc: EscenarioFinanciero) -> list[dict]:
        g = esc.crecimiento_mensual_pct / 100.0
        meses = []
        for t in range(1, esc.horizonte_meses + 1):
            demanda = esc.demanda_mensual_dosis * (1.0 + g) ** (t - 1)
            ingresos = demanda * esc.precio_dosis
            costes = demanda * esc.coste_por_dosis + esc.coste_fijo_mensual
            meses.append({"mes": t, "demanda_dosis": round(demanda, 4),
                          "ingresos": round(ingresos, 2),
                          "costes": round(costes, 2),
                          "margen": round(ingresos - costes, 2)})
        return meses

    def proyectar(self, escenario_id: str, usuario: str) -> dict:
        if escenario_id not in self._escenarios:
            raise FinanzasInvalidas(f"escenario inexistente: {escenario_id}")
        esc = self._escenarios[escenario_id]
        meses = self._proyectar(esc)
        ingresos = sum(m["ingresos"] for m in meses)
        costes = sum(m["costes"] for m in meses)
        equilibrio = next((m["mes"] for m in meses if m["margen"] >= 0),
                          None)
        resultado = {
            "escenario_id": escenario_id, "version": esc.version,
            "horizonte_meses": esc.horizonte_meses, "meses": meses,
            "ingresos_totales": round(ingresos, 2),
            "costes_totales": round(costes, 2),
            "margen_total": round(ingresos - costes, 2),
            "mes_equilibrio": equilibrio,
            "modelo": "demanda_t=demanda_0·(1+g)^t; ingresos=demanda·"
                      "precio; costes=demanda·coste_dosis+coste_fijo",
            "fecha_ejecucion": datetime.now(timezone.utc).isoformat(),
            "version_motor": FFSAE_VERSION}
        self._resultados.setdefault(escenario_id, []).append(resultado)
        self._auditar(usuario, "proyectar",
                      f"{escenario_id} v{esc.version}")
        return resultado

    def resultados(self, escenario_id: str) -> list[dict]:
        return list(self._resultados.get(escenario_id, []))

    # ------------------------------------------------ sensibilidad 40.8
    def sensibilidad(self, escenario_id: str, parametro: str,
                     variaciones_pct: list[float], usuario: str) -> dict:
        if escenario_id not in self._escenarios:
            raise FinanzasInvalidas(f"escenario inexistente: {escenario_id}")
        if parametro not in PARAMETROS_SENSIBLES:
            raise FinanzasInvalidas(
                f"parámetro no sensible (40.8): {parametro}")
        esc = self._escenarios[escenario_id]
        base_val = getattr(esc, parametro)
        puntos = []
        for v in variaciones_pct:
            mod = EscenarioFinanciero(
                escenario_id=esc.escenario_id, hipotesis=esc.hipotesis,
                demanda_mensual_dosis=esc.demanda_mensual_dosis,
                precio_dosis=esc.precio_dosis,
                coste_por_dosis=esc.coste_por_dosis,
                coste_fijo_mensual=esc.coste_fijo_mensual,
                crecimiento_mensual_pct=esc.crecimiento_mensual_pct,
                horizonte_meses=esc.horizonte_meses, version=esc.version)
            setattr(mod, parametro, base_val * (1.0 + v / 100.0))
            meses = self._proyectar(mod)
            ingresos = sum(m["ingresos"] for m in meses)
            costes = sum(m["costes"] for m in meses)
            puntos.append({"variacion_pct": v,
                           "valor_parametro": round(
                               base_val * (1.0 + v / 100.0), 6),
                           "ingresos_totales": round(ingresos, 2),
                           "margen_total": round(ingresos - costes, 2)})
        self._auditar(usuario, "sensibilidad",
                      f"{escenario_id}/{parametro}")
        return {"escenario_id": escenario_id, "parametro": parametro,
                "valor_base": base_val, "puntos": puntos,
                "nota": "análisis asociado al escenario (40.8); nunca "
                        "altera sus parámetros"}

    # -------------------------------------------------- inversión 40.9
    def evaluar_inversion(self, escenario_id: str, capex: float,
                          delta_ingresos_mensual: float,
                          delta_coste_mensual: float,
                          tasa_descuento_anual_pct: float,
                          horizonte_meses: int, usuario: str) -> dict:
        """Payback, VAN y ROI con fórmulas explícitas (40.9).

        PROPUESTA de soporte a la decisión (41.9), nunca decisión."""
        if escenario_id not in self._escenarios:
            raise FinanzasInvalidas(f"escenario inexistente: {escenario_id}")
        if capex <= 0 or horizonte_meses < 1:
            raise FinanzasInvalidas("capex/horizonte inválidos")
        flujo = delta_ingresos_mensual - delta_coste_mensual
        r_mes = tasa_descuento_anual_pct / 100.0 / 12.0
        van = -capex + sum(flujo / (1.0 + r_mes) ** t
                           for t in range(1, horizonte_meses + 1))
        payback = (capex / flujo if flujo > 0 else None)
        roi = ((flujo * horizonte_meses - capex) / capex * 100.0)
        self._auditar(usuario, "evaluar_inversion", escenario_id)
        return {"escenario_id": escenario_id, "capex": capex,
                "flujo_mensual_neto": round(flujo, 2),
                "payback_meses": (round(payback, 2)
                                  if payback is not None else None),
                "van": round(van, 2),
                "roi_pct": round(roi, 2),
                "formulas": "VAN=−CAPEX+Σ F_t/(1+r)^t; payback=CAPEX/F; "
                            "ROI=(F·n−CAPEX)/CAPEX",
                "naturaleza": "PROPUESTA de soporte a la decisión "
                              "(40.9/41.9): requiere aprobación humana"}

    # ------------------------------------------------------- riesgo 40.10
    def analizar_riesgo(self, escenario_id: str, evento: dict,
                        usuario: str) -> dict:
        """Impacto de un evento adverso respecto a la proyección base."""
        if escenario_id not in self._escenarios:
            raise FinanzasInvalidas(f"escenario inexistente: {escenario_id}")
        esc = self._escenarios[escenario_id]
        base = self._proyectar(esc)
        mod = EscenarioFinanciero(
            escenario_id=esc.escenario_id, hipotesis=esc.hipotesis,
            demanda_mensual_dosis=esc.demanda_mensual_dosis
            * (1.0 + evento.get("demanda_pct", 0.0) / 100.0),
            precio_dosis=esc.precio_dosis,
            coste_por_dosis=esc.coste_por_dosis
            * (1.0 + evento.get("coste_pct", 0.0) / 100.0),
            coste_fijo_mensual=esc.coste_fijo_mensual,
            crecimiento_mensual_pct=esc.crecimiento_mensual_pct,
            horizonte_meses=esc.horizonte_meses, version=esc.version)
        self._validar(mod)
        estres = self._proyectar(mod)
        margen_base = sum(m["margen"] for m in base)
        margen_estres = sum(m["margen"] for m in estres)
        self._auditar(usuario, "analizar_riesgo",
                      f"{escenario_id}: {evento.get('nombre', 'evento')}")
        return {"escenario_id": escenario_id,
                "evento": evento.get("nombre", "evento"),
                "margen_base": round(margen_base, 2),
                "margen_bajo_evento": round(margen_estres, 2),
                "impacto": round(margen_estres - margen_base, 2),
                "nota": "análisis orientado al soporte de decisiones "
                        "(40.10); el escenario base no se modifica"}

    # --------------------------------------------------------- KPIs 40.11
    def kpis(self, escenario_id: str, usuario: str) -> dict:
        if escenario_id not in self._escenarios:
            raise FinanzasInvalidas(f"escenario inexistente: {escenario_id}")
        if not self._resultados.get(escenario_id):
            self.proyectar(escenario_id, usuario)
        r = self._resultados[escenario_id][-1]
        esc = self._escenarios[escenario_id]
        rentabilidad = (r["margen_total"] / r["ingresos_totales"]
                        if r["ingresos_totales"] else None)
        meses = r["meses"]
        crecimiento = ((meses[-1]["ingresos"] / meses[0]["ingresos"] - 1.0)
                       * 100.0 if meses[0]["ingresos"] else None)
        self._auditar(usuario, "kpis", escenario_id)
        return {"escenario_id": escenario_id,
                "rentabilidad_pct": (round(rentabilidad * 100.0, 2)
                                     if rentabilidad is not None else None),
                "crecimiento_ingresos_pct": (round(crecimiento, 2)
                                             if crecimiento is not None
                                             else None),
                "coste_medio_mensual": round(
                    r["costes_totales"] / esc.horizonte_meses, 2),
                "version_motor": FFSAE_VERSION}
