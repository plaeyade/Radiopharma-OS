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
    # Fase 32: TODOS los modelos del catálogo son seleccionables. Los que no
    # tienen consumo eléctrico con fuente citada llevan rango None → el motor
    # acepta la potencia declarada por el usuario (con fuente) y la marca
    # "declarada_usuario_pendiente_fuente" — nunca la inventa.
    "ge_pettrace_840": {
        "nombre": "GE PETtrace 840 (16.5 MeV, 60 µA)",
        "potencia_standby_kw": None, "potencia_haz_kw_min": None, "potencia_haz_kw_max": None,
        "fuente_potencia": "pendiente_fuente (consumo eléctrico no publicado en fuente consultada)",
    },
    "ge_pettrace_860": {
        "nombre": "GE PETtrace 860 (16.5 MeV, 130 µA)",
        "potencia_standby_kw": None, "potencia_haz_kw_min": None, "potencia_haz_kw_max": None,
        "fuente_potencia": "pendiente_fuente",
    },
    "ge_pettrace_880": {
        "nombre": "GE PETtrace 880 (16.5 MeV)",
        "potencia_standby_kw": None, "potencia_haz_kw_min": None, "potencia_haz_kw_max": None,
        "fuente_potencia": "pendiente_fuente",
    },
    "ge_pettrace_890": {
        "nombre": "GE PETtrace 890 (16.5 MeV, 160 µA — data sheet PT800 rev3)",
        "potencia_standby_kw": None, "potencia_haz_kw_min": None, "potencia_haz_kw_max": None,
        "fuente_potencia": "pendiente_fuente (corriente citada: 160 µA, data sheet PT800 rev3)",
    },
    "ge_minitrace_qilin": {
        "nombre": "GE MINItrace Qilin (autoblindado compacto)",
        "potencia_standby_kw": None, "potencia_haz_kw_min": None, "potencia_haz_kw_max": None,
        "fuente_potencia": "pendiente_fuente",
    },
    "best_b100": {
        "nombre": "Best B-100 (7.5 MeV integrado)",
        "potencia_standby_kw": None, "potencia_haz_kw_min": None, "potencia_haz_kw_max": None,
        "fuente_potencia": "pendiente_fuente",
    },
    "best_b6_15": {
        "nombre": "Best B6-15 (6-15 MeV variable, ≤1000 µA)",
        "potencia_standby_kw": None, "potencia_haz_kw_min": None, "potencia_haz_kw_max": None,
        "fuente_potencia": "pendiente_fuente",
    },
    "lbt_7": {
        "nombre": "LBT Longevous Beamtech 7 MeV (China)",
        "potencia_standby_kw": None, "potencia_haz_kw_min": None, "potencia_haz_kw_max": None,
        "fuente_potencia": "pendiente_fuente (Preqin 2025: modelo existe; consumo no publicado)",
    },
    "lbt_11": {
        "nombre": "LBT Longevous Beamtech 11 MeV (China)",
        "potencia_standby_kw": None, "potencia_haz_kw_min": None, "potencia_haz_kw_max": None,
        "fuente_potencia": "pendiente_fuente",
    },
    "lbt_20": {
        "nombre": "LBT Longevous Beamtech 20 MeV (China)",
        "potencia_standby_kw": None, "potencia_haz_kw_min": None, "potencia_haz_kw_max": None,
        "fuente_potencia": "pendiente_fuente",
    },
}

# Regiones / divisiones tarifarias de CFE (Fase 32). Base citada: división
# Sureste (Villahermosa, Tabasco) — ver TARIFAS_CFE. Las demás divisiones se
# registran como pendiente_fuente: el motor acepta la tarifa declarada por el
# usuario CON fuente (app.cfe.mx publica tarifas por división cada mes) y la
# marca; nunca inventa el precio del kWh de otra sede.
REGIONES_CFE = {
    "sureste_tab": {"nombre": "Sureste — Villahermosa, Tabasco (base)",
                    "tarifa_mxn_kwh_gdmto": 1.21,
                    "fuente": "CFE tarifas vigentes (app.cfe.mx), división Sureste, consulta 2026-09"},
    "noroeste": {"nombre": "Noroeste (Sonora/Sinaloa)", "tarifa_mxn_kwh_gdmto": None, "fuente": "pendiente_fuente"},
    "norte": {"nombre": "Norte (Chihuahua/Coahuila/Durango)", "tarifa_mxn_kwh_gdmto": None, "fuente": "pendiente_fuente"},
    "noreste": {"nombre": "Noreste (Nuevo León/Tamaulipas)", "tarifa_mxn_kwh_gdmto": None, "fuente": "pendiente_fuente"},
    "occidente": {"nombre": "Occidente (Jalisco/Michoacán)", "tarifa_mxn_kwh_gdmto": None, "fuente": "pendiente_fuente"},
    "centro": {"nombre": "Centro (CDMX/Edo. México/Querétaro)", "tarifa_mxn_kwh_gdmto": None, "fuente": "pendiente_fuente"},
    "oriente": {"nombre": "Oriente (Puebla/Veracruz/Hidalgo)", "tarifa_mxn_kwh_gdmto": None, "fuente": "pendiente_fuente"},
    "sur": {"nombre": "Sur (Guerrero/Oaxaca)", "tarifa_mxn_kwh_gdmto": None, "fuente": "pendiente_fuente"},
    "peninsular": {"nombre": "Peninsular (Yucatán/Q. Roo/Campeche)", "tarifa_mxn_kwh_gdmto": None, "fuente": "pendiente_fuente"},
    "baja_california": {"nombre": "Baja California", "tarifa_mxn_kwh_gdmto": None, "fuente": "pendiente_fuente"},
    "bcs": {"nombre": "Baja California Sur", "tarifa_mxn_kwh_gdmto": None, "fuente": "pendiente_fuente"},
}

# Componentes de costo frecuentemente pasados por alto (Fase 32) — catálogo
# estructural: el motor NO inventa montos; el usuario los declara con fuente
# (cotización, nómina, contrato) y se suman al total de la corrida.
COMPONENTES_ADICIONALES = {
    "personal_operacion": "Sueldos/cargas sociales del operador y RPO prorrateados por corrida",
    "control_calidad_liberacion": "QC y liberación del lote (GC/HPLC, endotoxinas, esterilidad, pH, radioquímica)",
    "mantenimiento_preventivo": "Contrato de mantenimiento anual prorrateado por corrida",
    "gestion_residuos_radiactivos": "Almacenamiento/decaimiento y disposición de residuos radiactivos",
    "transporte_logistica": "Distribución en ventana de vida media (vehículo, contenedores tipo A)",
    "licencias_permisos": "COFEPRIS / CNSNS prorrateados",
    "seguros": "Seguro de responsabilidad civil e instalación prorrateado",
    "depreciacion_capex": "Depreciación del ciclotrón, celdas calientes y módulos",
    "gases_alta_pureza": "Gases UHP de proceso (catálogo citado Fase 31)",
    "agua_ultrapura_hvac": "Agua ultrapura, chiller y HVAC de celdas",
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
    # Fase 32 (opcionales)
    region_id: str | None = None                # división CFE de la sede
    tarifa_declarada_mxn_kwh: float | None = None  # requerida si la región está pendiente_fuente
    fuente_tarifa_declarada: str | None = None
    componentes_extra_mxn: dict | None = None   # claves de COMPONENTES_ADICIONALES
    fuente_componentes_extra: str | None = None


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

    def regiones(self):
        return REGIONES_CFE

    def componentes_adicionales(self):
        return COMPONENTES_ADICIONALES

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
        if cyc["potencia_haz_kw_min"] is None:
            if c.potencia_haz_kw <= 0:
                raise ValueError("potencia_haz_kw debe ser positiva")
            estado_potencia = ("declarada_usuario_pendiente_fuente: consumo "
                               "eléctrico del modelo sin fuente citada; la "
                               "potencia la declara el usuario")
        elif not cyc["potencia_haz_kw_min"] <= c.potencia_haz_kw <= cyc["potencia_haz_kw_max"]:
            raise ValueError(
                f"potencia_haz_kw fuera del rango citado "
                f"[{cyc['potencia_haz_kw_min']}, {cyc['potencia_haz_kw_max']}] kW")
        else:
            estado_potencia = "fuente_externa_citada"

        tar = TARIFAS_CFE[c.tarifa_id]
        estado_tarifa = "fuente_externa_citada"
        if tar["demanda_max_kw"] is not None and c.potencia_haz_kw > tar["demanda_max_kw"]:
            estado_tarifa = (
                "ADVERTENCIA: la demanda de haz excede el límite de la tarifa "
                f"{c.tarifa_id} ({tar['demanda_max_kw']} kW) — verificar tarifa aplicable")

        # Región / división CFE de la sede (Fase 32)
        estado_region = None
        tarifa_region_mxn_kwh = None
        if c.region_id is not None:
            if c.region_id not in REGIONES_CFE:
                raise ValueError("region_id no está en el catálogo de divisiones CFE")
            reg = REGIONES_CFE[c.region_id]
            tarifa_region_mxn_kwh = reg["tarifa_mxn_kwh_gdmto"]
            if tarifa_region_mxn_kwh is None:
                if c.tarifa_declarada_mxn_kwh is None or not c.fuente_tarifa_declarada:
                    raise ValueError(
                        f"la división {reg['nombre']} está pendiente_fuente: declare "
                        "tarifa_declarada_mxn_kwh CON fuente_tarifa_declarada (49.11)")
                tarifa_region_mxn_kwh = c.tarifa_declarada_mxn_kwh
                estado_region = "tarifa_regional_declarada_usuario_con_fuente"
            else:
                estado_region = "fuente_externa_citada"

        # kWh: aritmética directa potencia × tiempo
        kwh_haz = c.potencia_haz_kw * c.t_irradiacion_min / 60.0
        standby_kw = cyc["potencia_standby_kw"] or 0.0
        kwh_standby = standby_kw * c.t_standby_min / 60.0
        kwh_total = kwh_haz + kwh_standby

        tarifa_mxn_kwh = (tarifa_region_mxn_kwh if tarifa_region_mxn_kwh is not None
                          else sum(tar["rango_mxn_kwh"]) / 2.0)
        costo_electrico_mxn = kwh_total * tarifa_mxn_kwh

        # Agua enriquecida: pérdida neta por reciclaje
        prov = PROVEEDORES_H2O18[c.proveedor_agua_id]
        agua_perdida_g = c.agua_cargada_g * (1.0 - c.fraccion_recuperada)
        precio_g = prov["precio_usd_g_granel"] or prov["precio_usd_g"]
        costo_agua_mxn = agua_perdida_g * precio_g  # moneda del proveedor, declarada
        nota_moneda = ("precio en moneda del proveedor (USD/EUR declarado); "
                       "tipo de cambio no incluido — declarar si aplica")

        # Componentes adicionales declarados (Fase 32): nunca inventados,
        # solo claves del catálogo CON fuente.
        costo_extra = 0.0
        if c.componentes_extra_mxn:
            if not c.fuente_componentes_extra:
                raise ValueError("componentes extra exigen fuente citada (49.11)")
            for k, v in c.componentes_extra_mxn.items():
                if k not in COMPONENTES_ADICIONALES:
                    raise ValueError(f"componente extra desconocido: {k} "
                                     f"(válidos: {sorted(COMPONENTES_ADICIONALES)})")
                if v < 0:
                    raise ValueError(f"componente extra negativo: {k}")
                costo_extra += float(v)

        costo_total = (costo_electrico_mxn + costo_agua_mxn
                       + c.costo_desgaste_mxn + c.costo_consumibles_mxn
                       + costo_extra)

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
            "estado_potencia": estado_potencia,
            "estado_region": estado_region,
            "costo_componentes_extra_mxn": round(costo_extra, 2),
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
