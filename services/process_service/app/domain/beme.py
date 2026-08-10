"""Building Environmental Management Engine (EDS cap. 35).

El BEME representa las condiciones ambientales de la instalación:

- **Environmental Sensor Manager (35.6)**: sensores vinculados al
  Asset Registry, con calibración.
- **HVAC Manager (35.7)**: unidades manejadoras de aire; los parámetros
  provienen del SCADA cuando está disponible — el BEME NUNCA los
  inventa.
- **Differential Pressure Manager (35.8)**: gradientes entre zonas y
  estabilidad temporal.
- **Gestión de zonas ambientales (35.11)**: condiciones objetivo con
  configuración VERSIONADA (cada cambio es una versión nueva; el
  historial nunca se pierde).
- **Alarm Manager (35.12)**: eventos de desviación asociados al área.
- **Validation Engine (35.21)**: antes de aceptar una medición se
  verifica rango, consistencia temporal, estado del sensor y calidad
  del dato; las anomalías generan eventos de validación.
- **Gestión temporal (35.13)**: timestamp, valor, calidad, origen.

Filosofía 35.3: el BEME monitorea, registra, analiza y genera eventos.
NO controla el HVAC ni las utilidades — el control físico permanece en
los sistemas industriales. Las recomendaciones permanecen diferenciadas
de las mediciones reales (35.20).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

BEME_VERSION = "beme-1.0.0"

# Rangos de plausibilidad física por variable (35.21)
RANGOS_PLAUSIBLES = {
    "temperatura": (-40.0, 80.0),            # °C
    "humedad": (0.0, 100.0),                 # %HR
    "presion_diferencial": (-100.0, 100.0),  # Pa
    "particulas_0_5um_m3": (0.0, 1e9),
}

CALIDADES = ("good", "uncertain", "bad")     # calidad del dato 35.13


class BemeInvalido(ValueError):
    """Medición, sensor o configuración inválida (35.21)."""


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Sensor:
    """Environmental Sensor Manager (35.6)."""
    sensor_id: str
    activo_id: str                  # vínculo al Asset Registry (33.6)
    area_id: str
    variable: str
    unidad: str
    estado: str = "operativo"       # operativo/fuera_de_servicio
    calibracion_id: str = ""        # vínculo a Calibration Manager 34.10


@dataclass
class CondicionesObjetivo:
    """Condiciones objetivo de una zona ambiental (35.11)."""
    temp_min_c: float | None = None
    temp_max_c: float | None = None
    humedad_min_pct: float | None = None
    humedad_max_pct: float | None = None
    presion_min_pa: float | None = None    # cascada: zonas calientes < 0
    presion_max_pa: float | None = None
    particulas_max_m3: float | None = None


@dataclass
class UnidadHvac:
    """HVAC Manager (35.7)."""
    hvac_id: str
    area_id: str
    descripcion: str = ""
    parametros: dict = field(default_factory=dict)  # caudal, renovaciones…
    fuente_scada: str = ""          # serie SCADA de la que provienen
    estado: str = "operativa"


class BemeEngine:
    """Motor ambiental: monitorea, registra, analiza, genera eventos."""

    def __init__(self, max_antiguedad_s: float = 900.0) -> None:
        self._sensores: dict[str, Sensor] = {}
        self._zonas: dict[str, dict] = {}          # area_id -> config vigente
        self._versiones_zona: dict[str, list[dict]] = {}
        self._hvac: dict[str, UnidadHvac] = {}
        self._mediciones: list[dict] = []
        self._eventos: list[dict] = []
        self._auditoria: list[dict] = []
        self._max_antiguedad = timedelta(seconds=max_antiguedad_s)

    # ------------------------------------------------------------ núcleo
    def _auditar(self, usuario: str, accion: str, detalle: str) -> None:
        self._auditoria.append({"usuario": usuario, "accion": accion,
                                "detalle": detalle,
                                "fecha": _ahora().isoformat()})

    def _evento(self, tipo: str, area_id: str, detalle: str) -> dict:
        ev = {"tipo": tipo, "area_id": area_id, "detalle": detalle,
              "fecha": _ahora().isoformat()}
        self._eventos.append(ev)
        return ev

    def auditoria(self) -> list[dict]:
        return list(self._auditoria)

    def eventos(self, area_id: str | None = None) -> list[dict]:
        return [e for e in self._eventos
                if area_id is None or e["area_id"] == area_id]

    # ------------------------------------------------------- sensores 35.6
    def registrar_sensor(self, sensor: Sensor, usuario: str) -> dict:
        if sensor.sensor_id in self._sensores:
            raise BemeInvalido(f"sensor ya registrado: {sensor.sensor_id}")
        if sensor.variable not in RANGOS_PLAUSIBLES:
            raise BemeInvalido(f"variable sin rango definido: "
                               f"{sensor.variable}")
        if not sensor.activo_id:
            raise BemeInvalido(
                "todo sensor se vincula al Asset Registry (35.6)")
        self._sensores[sensor.sensor_id] = sensor
        self._auditar(usuario, "registrar_sensor", sensor.sensor_id)
        return {"sensor_id": sensor.sensor_id}

    def cambiar_estado_sensor(self, sensor_id: str, estado: str,
                              usuario: str) -> dict:
        if sensor_id not in self._sensores:
            raise BemeInvalido(f"sensor inexistente: {sensor_id}")
        if estado not in ("operativo", "fuera_de_servicio"):
            raise BemeInvalido(f"estado inválido: {estado}")
        self._sensores[sensor_id].estado = estado
        self._auditar(usuario, "estado_sensor", f"{sensor_id} -> {estado}")
        return {"sensor_id": sensor_id, "estado": estado}

    def sensores(self) -> list[dict]:
        return [{"sensor_id": s.sensor_id, "activo_id": s.activo_id,
                 "area_id": s.area_id, "variable": s.variable,
                 "unidad": s.unidad, "estado": s.estado,
                 "calibracion_id": s.calibracion_id}
                for s in self._sensores.values()]

    # ------------------------------------------- zonas ambientales 35.11
    def configurar_zona(self, area_id: str, clasificacion: str,
                        objetivo: CondicionesObjetivo, version: str,
                        usuario: str) -> dict:
        """Configuración versionada: cada cambio es versión nueva y las
        anteriores permanecen (35.11)."""
        versiones = self._versiones_zona.setdefault(area_id, [])
        if any(v["version"] == version for v in versiones):
            raise BemeInvalido(
                f"versión de configuración ya usada en {area_id}: {version}")
        cfg = {"area_id": area_id, "clasificacion": clasificacion,
               "objetivo": objetivo, "version": version,
               "fecha": _ahora().isoformat()}
        versiones.append(cfg)
        self._zonas[area_id] = cfg
        self._auditar(usuario, "configurar_zona", f"{area_id} v{version}")
        return {"area_id": area_id, "version": version}

    def zona(self, area_id: str) -> dict:
        if area_id not in self._zonas:
            raise BemeInvalido(f"zona sin configuración: {area_id}")
        cfg = self._zonas[area_id]
        return {"area_id": area_id, "clasificacion": cfg["clasificacion"],
                "version": cfg["version"],
                "versiones_disponibles":
                    [v["version"] for v in self._versiones_zona[area_id]],
                "objetivo": {k: v for k, v in vars(cfg["objetivo"]).items()
                             if v is not None}}

    # ---------------------------------------------------------- HVAC 35.7
    def registrar_hvac(self, u: UnidadHvac, usuario: str) -> dict:
        if u.hvac_id in self._hvac:
            raise BemeInvalido(f"unidad HVAC ya registrada: {u.hvac_id}")
        if u.parametros and not u.fuente_scada:
            raise BemeInvalido(
                "los parámetros HVAC provienen del SCADA (35.7): la "
                "fuente es obligatoria; el BEME nunca inventa parámetros")
        self._hvac[u.hvac_id] = u
        self._auditar(usuario, "registrar_hvac", u.hvac_id)
        return {"hvac_id": u.hvac_id}

    def hvac(self) -> list[dict]:
        return [{"hvac_id": u.hvac_id, "area_id": u.area_id,
                 "estado": u.estado, "parametros": dict(u.parametros),
                 "fuente_scada": u.fuente_scada}
                for u in self._hvac.values()]

    # --------------------------------------------- mediciones 35.13/35.21
    def registrar_medicion(self, sensor_id: str, valor: float,
                           calidad: str, origen: str,
                           timestamp: str | None = None) -> dict:
        """Validación 35.21 previa a aceptar la medición.

        Devuelve el resultado; las anomalías generan eventos de
        validación, nunca correcciones silenciosas.
        """
        if sensor_id not in self._sensores:
            raise BemeInvalido(f"sensor inexistente: {sensor_id}")
        s = self._sensores[sensor_id]
        if calidad not in CALIDADES:
            raise BemeInvalido(f"calidad desconocida: {calidad}")
        if not origen:
            raise BemeInvalido("toda medición registra su origen (35.13)")
        ts = (datetime.fromisoformat(timestamp) if timestamp else _ahora())
        ahora = _ahora()
        eventos = []
        # estado del sensor (35.21)
        if s.estado != "operativo":
            eventos.append(self._evento(
                "validacion:sensor_fuera_de_servicio", s.area_id,
                f"{sensor_id}: medición recibida de sensor no operativo"))
        # consistencia temporal (35.21)
        if ts > ahora + timedelta(seconds=60):
            eventos.append(self._evento(
                "validacion:timestamp_futuro", s.area_id,
                f"{sensor_id}: {ts.isoformat()}"))
        elif ahora - ts > self._max_antiguedad:
            eventos.append(self._evento(
                "validacion:dato_obsoleto", s.area_id,
                f"{sensor_id}: antigüedad > {self._max_antiguedad}"))
        # rango de plausibilidad (35.21)
        lo, hi = RANGOS_PLAUSIBLES[s.variable]
        fuera_rango = not (lo <= valor <= hi)
        if fuera_rango:
            eventos.append(self._evento(
                "validacion:fuera_de_rango", s.area_id,
                f"{sensor_id}: {valor} fuera de [{lo}, {hi}]"))
        aceptada = (s.estado == "operativo" and calidad == "good"
                    and not fuera_rango and not eventos)
        self._mediciones.append({
            "sensor_id": sensor_id, "area_id": s.area_id,
            "variable": s.variable, "valor": valor, "unidad": s.unidad,
            "calidad": calidad, "origen": origen,
            "timestamp": ts.isoformat(), "aceptada": aceptada})
        # desviación respecto a condiciones objetivo (35.12)
        desviacion = None
        if aceptada and s.area_id in self._zonas:
            desviacion = self._comprobar_objetivo(s, valor)
            if desviacion:
                eventos.append(self._evento(
                    f"alarma:{desviacion['tipo']}", s.area_id,
                    f"{s.variable}={valor}{s.unidad} fuera de objetivo "
                    f"(zona v{self._zonas[s.area_id]['version']})"))
        self._auditar(origen, "medicion",
                      f"{sensor_id}={valor}{s.unidad} "
                      f"({'aceptada' if aceptada else 'rechazada'})")
        return {"sensor_id": sensor_id, "aceptada": aceptada,
                "desviacion": desviacion,
                "eventos": [e["tipo"] for e in eventos]}

    def _comprobar_objetivo(self, s: Sensor, valor: float) -> dict | None:
        obj: CondicionesObjetivo = self._zonas[s.area_id]["objetivo"]
        checks = {
            "temperatura": (obj.temp_min_c, obj.temp_max_c,
                            "desviacion_temperatura"),
            "humedad": (obj.humedad_min_pct, obj.humedad_max_pct,
                        "desviacion_humedad"),
            "presion_diferencial": (obj.presion_min_pa, obj.presion_max_pa,
                                    "perdida_de_presion"),
            "particulas_0_5um_m3": (None, obj.particulas_max_m3,
                                    "calidad_aire"),
        }
        if s.variable not in checks:
            return None
        lo, hi, tipo = checks[s.variable]
        if lo is not None and valor < lo:
            return {"tipo": tipo, "limite": "minimo", "objetivo": lo,
                    "valor": valor}
        if hi is not None and valor > hi:
            return {"tipo": tipo, "limite": "maximo", "objetivo": hi,
                    "valor": valor}
        return None

    # ------------------------------------- presión diferencial 35.8
    def gradiente_presion(self, area_origen: str, area_destino: str
                          ) -> dict:
        """Gradiente entre dos zonas a partir de las últimas mediciones
        aceptadas (35.8); honesto si falta dato de alguna zona."""
        def ultima(area: str) -> dict | None:
            for m in reversed(self._mediciones):
                if (m["area_id"] == area
                        and m["variable"] == "presion_diferencial"
                        and m["aceptada"]):
                    return m
            return None
        mo, md = ultima(area_origen), ultima(area_destino)
        if mo is None or md is None:
            faltan = [a for a, m in ((area_origen, mo), (area_destino, md))
                      if m is None]
            return {"gradiente_pa": None, "area_origen": area_origen,
                    "area_destino": area_destino,
                    "nota": f"sin mediciones aceptadas en: "
                            f"{', '.join(faltan)}"}
        return {"gradiente_pa": round(mo["valor"] - md["valor"], 4),
                "area_origen": area_origen, "area_destino": area_destino,
                "timestamps": [mo["timestamp"], md["timestamp"]]}

    def estabilidad_presion(self, area_id: str, n: int = 10) -> dict:
        """Dispersión (máx−mín) de las últimas n mediciones aceptadas
        de presión (35.8)."""
        vals = [m["valor"] for m in self._mediciones
                if m["area_id"] == area_id
                and m["variable"] == "presion_diferencial"
                and m["aceptada"]][-n:]
        if len(vals) < 2:
            return {"area_id": area_id, "estable": None,
                    "nota": "datos insuficientes"}
        dispersion = max(vals) - min(vals)
        return {"area_id": area_id, "n": len(vals),
                "dispersion_pa": round(dispersion, 4),
                "estable": dispersion <= 5.0,
                "criterio": "dispersión ≤ 5 Pa"}

    # ---------------------------------------------------- estado de zona
    def estado_zona(self, area_id: str) -> dict:
        """Estado ambiental actual vs objetivo (35.11/35.15)."""
        cfg = self.zona(area_id)
        estado: dict = {"area_id": area_id, "version": cfg["version"],
                        "variables": {}}
        for m in self._mediciones:
            if m["area_id"] == area_id and m["aceptada"]:
                estado["variables"][m["variable"]] = {
                    "valor": m["valor"], "unidad": m["unidad"],
                    "timestamp": m["timestamp"]}
        estado["alarmas_activas"] = len(self.eventos(area_id))
        return estado

    def mediciones(self, area_id: str | None = None) -> list[dict]:
        return [dict(m) for m in self._mediciones
                if area_id is None or m["area_id"] == area_id]
