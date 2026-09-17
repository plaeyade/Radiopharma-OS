"""Motor de Costos y Precio por Corrida (Fase 29).

Ingeniería canónica:
- 49.11: potencias de ciclotrón, tarifas eléctricas, precios de agua
  enriquecida y factores de reciclaje SOLO con fuente citada. Sin fuente
  externa → marcador honesto "declarado_interno_pendiente_fuente".
- 18.10: los escenarios de precio de venta son RECOMENDACIÓN / soporte a la
  decisión; la decisión de precio es operativa y humana.
- Registro versionado, nunca sobrescribe (ALCOA+): cada corrida de cálculo
  es un registro nuevo con motivo.
- Nada se simula: los kWh se calculan de potencia × tiempo (aritmética
  directa con entradas declaradas), no de lecturas simuladas.

Fuentes citadas (Fase 29):
- Potencia IBA Cyclone KIUBE: standby <3 kW, haz 45-65 kW (ficha comercial
  IBA vía medicalexpo, 2026).
- Tarifas CFE (Villahermosa, Tabasco = división Sureste):
  PDBT (pequeña demanda ≤25 kW) ~3-5 MXN/kWh; GDMTO (<100 kW) ~1.21 MXN/kWh
  +IVA; GDMTH (≥100 kW) base ~0.85 / intermedio ~1.53 / punta ~1.74 MXN/kWh.
  Fuente: páginas oficiales de tarifas CFE (app.cfe.mx), consulta 2026-09.
- Agua enriquecida H2-18O: chempep 98% 1 g USD 150 / 25 g USD 1500;
  isotopeshop 1 g EUR 193 / 5 g EUR 725; silantes desde EUR 170/g;
  NUCMEDCOR GMP 98 atom% (viales 10/20/50 g); Sigma-Aldrich ≥98 atom%
  grado PET. Consulta 2026-09.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Catálogos con fuente citada
# ---------------------------------------------------------------------------

CICLOTRONES = {
    "abt_bg75": {
        "nombre": "ABT BG-75 (7.5 MeV, autoblindado)",
        "potencia_standby_kw": 1.0,          # declarado interno, pendiente_fuente
        "potencia_haz_kw_min": 1.0,
        "potencia_haz_kw_max": 5.0,          # "<5 kW operación" → cota superior citada
        "fuente_potencia": ("ABT BG-75 Technical Overview: potencia de operación <5 kW "
                            "(cota superior citada); standby declarado interno pendiente_fuente"),
    },
    "iba_cyclone_kiube": {
        "nombre": "IBA Cyclone KIUBE (18 MeV)",
        "potencia_standby_kw": 3.0,          # "<3 kW" → cota superior declarada
        "potencia_haz_kw_min": 45.0,
        "potencia_haz_kw_max": 65.0,
        "fuente_potencia": "Ficha comercial IBA Cyclone KIUBE (medicalexpo, consulta 2026-09): standby <3 kW, haz 45-65 kW",
    },
}

TARIFAS_CFE = {
    "PDBT": {
        "nombre": "PDBT — Pequeña Demanda Baja Tensión (≤25 kW)",
        "rango_mxn_kwh": (3.0, 5.0),
        "demanda_max_kw": 25.0,
        "fuente": "CFE tarifas vigentes (app.cfe.mx), división Sureste (Tabasco), consulta 2026-09",
    },
    "GDMTO": {
        "nombre": "GDMTO — Gran Demanda Media Tensión Ordinaria (<100 kW)",
        "rango_mxn_kwh": (1.21, 1.21),
        "demanda_max_kw": 100.0,
        "fuente": "CFE tarifas vigentes (app.cfe.mx), división Sureste (Tabasco), consulta 2026-09",
    },
    "GDMTH": {
        "nombre": "GDMTH — Gran Demanda Media Tensión Horaria (≥100 kW)",
        "rango_mxn_kwh": (0.85, 1.74),  # base / punta
        "demanda_max_kw": None,
        "fuente": "CFE tarifas vigentes (app.cfe.mx), división Sureste (Tabasco), consulta 2026-09",
    },
}

PROVEEDORES_H2O18 = {
    "chempep_98": {
        "nombre": "ChemPep H2-18O 98 atom%",
        "enriquecimiento_pct": 98.0,
        "precio_usd_g": 150.0,   # 1 g USD 150 (25 g USD 1500 → 60 USD/g a granel)
        "precio_usd_g_granel": 60.0,
        "fuente": "ChemPep lista de precios H2-18O 98%, consulta 2026-09",
    },
    "isotopeshop_98": {
        "nombre": "IsotopesShop H2-18O 98 atom%",
        "enriquecimiento_pct": 98.0,
        "precio_usd_g": 193.0,   # EUR 193 ≈ declarado como USD equivalente por usuario del registro
        "precio_usd_g_granel": 145.0,  # 5 g EUR 725 → 145/g
        "fuente": "IsotopesShop lista de precios H2-18O 98% (EUR), consulta 2026-09",
    },
    "silantes_98": {
        "nombre": "Silantes H2-18O 98 atom%",
        "enriquecimiento_pct": 98.0,
        "precio_usd_g": 170.0,
        "precio_usd_g_granel": None,
        "fuente": "Silantes lista de precios (desde EUR 170/g), consulta 2026-09",
    },
}

# Costos de desgaste por componente (vinculados a Fase 27). Sin fuente de
# fabricante → se registran con fuente obligatoria del usuario; el motor no
# inventa precios de refacciones.

MODOS_PRECIO = ("granel_mxn_gb", "unidosis_mxn_dosis")


# ---------------------------------------------------------------------------
# Entidades
# ---------------------------------------------------------------------------

@dataclass
class CorridaCosto:
    corrida_id: str
    isotopo: str
    ciclotron_id: str
    tarifa_id: str
    # Operación
    t_irradiacion_min: float
    t_standby_min: float
    potencia_haz_kw: float
    # Agua enriquecida
    proveedor_agua_id: str
    agua_cargada_g: float
    fraccion_recuperada: float        # reciclaje: 0-1, con fuente
    fuente_reciclaje: str
    # Producción
    actividad_producida_gb: float
    n_dosis: int
    # Desgaste (Fase 27, entradas declaradas)
    costo_desgaste_mxn: float
    fuente_desgaste: str
    # Otros consumibles
    costo_consumibles_mxn: float
    fuente_consumibles: str
    motivo: str
    responsable: str


# ---------------------------------------------------------------------------
# Motor
# ---------------------------------------------------------------------------

class CostEngine:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._corridas: dict[str, dict] = {}
        self._cargar()

    def _cargar(self):
        if self.path.exists():
            try:
                d = json.loads(self.path.read_text(encoding="utf-8"))
                self._corridas = d.get("corridas", {})
            except Exception:
                self._corridas = {}

    def _guardar(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"corridas": self._corridas},
                                  indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    # -- catálogos ----------------------------------------------------------
    def ciclotrones(self):
        return CICLOTRONES

    def tarifas(self):
        return TARIFAS_CFE

    def proveedores_agua(self):
        return PROVEEDORES_H2O18

    # -- cálculo ------------------------------------------------------------
    def registrar_corrida(self, c: CorridaCosto) -> dict:
        if c.corrida_id in self._corridas:
            raise ValueError("corrida_id duplicado — los registros nunca se sobrescriben")
        if c.ciclotron_id not in CICLOTRONES:
            raise ValueError("ciclotron_id no está en el catálogo (registre con fuente 49.11)")
        if c.tarifa_id not in TARIFAS_CFE:
            raise ValueError("tarifa_id no está en el catálogo CFE")
        if c.proveedor_agua_id not in PROVEEDORES_H2O18:
            raise ValueError("proveedor_agua_id no está en el catálogo")
        if not c.motivo or not c.responsable:
            raise ValueError("motivo y responsable son obligatorios (18.10 / ALCOA+)")
        if not c.fuente_reciclaje:
            raise ValueError("fracción de reciclaje exige fuente citada (49.11)")
        if not 0.0 <= c.fraccion_recuperada <= 1.0:
            raise ValueError("fraccion_recuperada fuera de [0,1]")
        if not c.fuente_desgaste or not c.fuente_consumibles:
            raise ValueError("costos de desgaste y consumibles exigen fuente citada")
        if c.actividad_producida_gb <= 0 or c.n_dosis <= 0:
            raise ValueError("actividad y número de dosis deben ser positivos")

        cyc = CICLOTRONES[c.ciclotron_id]
        if not cyc["potencia_haz_kw_min"] <= c.potencia_haz_kw <= cyc["potencia_haz_kw_max"]:
            raise ValueError(
                f"potencia_haz_kw fuera del rango citado "
                f"[{cyc['potencia_haz_kw_min']}, {cyc['potencia_haz_kw_max']}] kW")

        tar = TARIFAS_CFE[c.tarifa_id]
        estado_tarifa = "fuente_externa_citada"
        if tar["demanda_max_kw"] is not None and c.potencia_haz_kw > tar["demanda_max_kw"]:
            estado_tarifa = (
                "ADVERTENCIA: la demanda de haz excede el límite de la tarifa "
                f"{c.tarifa_id} ({tar['demanda_max_kw']} kW) — verificar tarifa aplicable")

        # kWh: aritmética directa potencia × tiempo
        kwh_haz = c.potencia_haz_kw * c.t_irradiacion_min / 60.0
        kwh_standby = cyc["potencia_standby_kw"] * c.t_standby_min / 60.0
        kwh_total = kwh_haz + kwh_standby

        tarifa_mxn_kwh = sum(tar["rango_mxn_kwh"]) / 2.0
        costo_electrico_mxn = kwh_total * tarifa_mxn_kwh

        # Agua enriquecida: pérdida neta por reciclaje
        prov = PROVEEDORES_H2O18[c.proveedor_agua_id]
        agua_perdida_g = c.agua_cargada_g * (1.0 - c.fraccion_recuperada)
        precio_g = prov["precio_usd_g_granel"] or prov["precio_usd_g"]
        costo_agua_mxn = agua_perdida_g * precio_g  # moneda del proveedor, declarada
        nota_moneda = ("precio en moneda del proveedor (USD/EUR declarado); "
                       "tipo de cambio no incluido — declarar si aplica")

        costo_total = (costo_electrico_mxn + costo_agua_mxn
                       + c.costo_desgaste_mxn + c.costo_consumibles_mxn)

        rec = {
            **asdict(c),
            "kwh_haz": round(kwh_haz, 3),
            "kwh_standby": round(kwh_standby, 3),
            "kwh_total": round(kwh_total, 3),
            "tarifa_mxn_kwh": tarifa_mxn_kwh,
            "costo_electrico_mxn": round(costo_electrico_mxn, 2),
            "agua_perdida_g": round(agua_perdida_g, 4),
            "precio_agua_por_g": precio_g,
            "costo_agua": round(costo_agua_mxn, 2),
            "nota_moneda_agua": nota_moneda,
            "costo_total_mxn": round(costo_total, 2),
            "costo_por_gb_mxn": round(costo_total / c.actividad_producida_gb, 2),
            "costo_por_dosis_mxn": round(costo_total / c.n_dosis, 2),
            "estado_tarifa": estado_tarifa,
            "fuentes": {
                "potencia": cyc["fuente_potencia"],
                "tarifa": tar["fuente"],
                "agua": prov["fuente"],
                "reciclaje": c.fuente_reciclaje,
                "desgaste": c.fuente_desgaste,
                "consumibles": c.fuente_consumibles,
            },
            "naturaleza": ("CÁLCULO con entradas declaradas y fuentes citadas. "
                           "Escenarios de precio = RECOMENDACIÓN (soporte a la "
                           "decisión 18.10); la fijación de precio es decisión operativa humana."),
        }
        self._corridas[c.corrida_id] = rec
        self._guardar()
        return rec

    def escenario_precio(self, corrida_id: str, modo: str,
                         margen_pct: float, motivo: str) -> dict:
        """Propone precio de venta (granel MXN/GBq o unidosis MXN/dosis)."""
        if corrida_id not in self._corridas:
            raise ValueError("corrida desconocida")
        if modo not in MODOS_PRECIO:
            raise ValueError(f"modo debe ser uno de {MODOS_PRECIO}")
        if not motivo:
            raise ValueError("motivo obligatorio (18.10)")
        if margen_pct < 0:
            raise ValueError("margen no puede ser negativo")
        r = self._corridas[corrida_id]
        base = r["costo_por_gb_mxn"] if modo == "granel_mxn_gb" else r["costo_por_dosis_mxn"]
        precio = base * (1.0 + margen_pct / 100.0)
        esc = {
            "corrida_id": corrida_id,
            "modo": modo,
            "margen_pct": margen_pct,
            "precio_sugerido_mxn": round(precio, 2),
            "costo_base_mxn": base,
            "motivo": motivo,
            "naturaleza": ("RECOMENDACIÓN — soporte a la decisión (18.10). "
                           "No constituye decisión operativa de precio."),
        }
        r.setdefault("escenarios_precio", []).append(esc)
        self._guardar()
        return esc

    def corridas(self):
        return list(self._corridas.values())

    def corrida(self, corrida_id: str) -> Optional[dict]:
        return self._corridas.get(corrida_id)
