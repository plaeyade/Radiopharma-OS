"""Sistema de Vacío del ciclotrón y líneas de proceso (Fase 28, cap. 34 ext.).

Bombas de vacío y tramos de línea (mangueras/tuberías) como activos con
VARIABLES medidas — nunca simuladas:

- **Bomba de vacío** (primaria mecánica, turbomolecular, criogénica):
  variables `presion_base_pa` (vacío base alcanzado en prueba real),
  `horas_operacion` (acumulado de eventos registrados). Salud contra
  umbrales DECLARADOS con fuente (49.11): degradación del vacío base
  (factor sobre la referencia de puesta en servicio) y horas a
  mantenimiento.
- **Tramo de línea / manguera**: variables `tasa_fuga_mbar_l_s` (prueba
  de fuga registrada — p.ej. helio) y `caida_presion_pa` (medida entre
  extremos). Estado `fuga` cuando supera el umbral declarado.

Reglas canónicas: mediciones SOLO con `origen` obligatorio (telemetría
o prueba registrada); umbrales con fuente declarada — sin fuente
externa quedan marcados `declarado_interno_pendiente_fuente`;
recomendación de intervención como soporte a la decisión (18.10), la
decisión es del responsable; registros append-only ALCOA+.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.facility_twin import FacilityTwin

VACUUM_VERSION = "vacuum-system-1.0.0"

TIPOS_BOMBA = ("primaria_mecanica", "turbomolecular", "criogenica")
TIPOS_TRAMO = ("manguera", "tuberia", "fuelle", "conexion")
VARIABLES_BOMBA = ("presion_base_pa", "horas_operacion")
VARIABLES_TRAMO = ("tasa_fuga_mbar_l_s", "caida_presion_pa")

ESTADOS = ("verde", "ambar", "rojo")


class VacioInvalido(ValueError):
    """Bomba, tramo o medición inválida."""


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class BombaVacio:
    bomba_id: str
    tipo: str                     # TIPOS_BOMBA
    activo_id: str                # padre en Asset Registry
    presion_base_ref_pa: float    # referencia de puesta en servicio
    factor_degradacion: float     # p.ej. 2.0 → rojo si base > 2×ref
    horas_mantenimiento: float    # umbral de horas
    fuente_umbral: str            # 49.11
    fuente_externa: bool = False
    motivo: str = ""


@dataclass
class TramoLinea:
    tramo_id: str
    tipo: str                     # TIPOS_TRAMO
    activo_id: str
    umbral_fuga_mbar_l_s: float   # p.ej. 1e-6
    umbral_caida_presion_pa: float
    fuente_umbral: str
    fuente_externa: bool = False
    motivo: str = ""


@dataclass
class MedicionVacio:
    variable: str                 # según elemento
    valor: float
    origen: str                   # obligatorio — nunca simulado
    ts: str = ""


class VacuumSystem:
    """Registro y tablero del sistema de vacío (append-only)."""

    def __init__(self, twin: FacilityTwin) -> None:
        self._twin = twin
        self._bombas: dict[str, dict] = {}
        self._tramos: dict[str, dict] = {}
        self._mediciones: dict[str, list[dict]] = {}
        self._audit: list[dict] = []

    def _auditar(self, usuario: str, accion: str, detalle: str) -> None:
        self._audit.append({"ts": _ahora(), "usuario": usuario,
                            "accion": accion, "detalle": detalle})

    def auditoria(self) -> list[dict]:
        return list(self._audit)

    def _activo_existe(self, activo_id: str) -> bool:
        return activo_id in {a["activo_id"] for a in self._twin.activos()}

    @staticmethod
    def _marcador(fuente_externa: bool) -> str:
        return ("fuente_externa_citada" if fuente_externa
                else "declarado_interno_pendiente_fuente")

    # ------------------------------------------------------ registro
    def registrar_bomba(self, b: BombaVacio, usuario: str) -> dict:
        if b.bomba_id in self._bombas:
            raise VacioInvalido(
                f"bomba {b.bomba_id} ya registrada — nunca se sobrescribe")
        if b.tipo not in TIPOS_BOMBA:
            raise VacioInvalido(f"tipo {b.tipo!r} no válido: {TIPOS_BOMBA}")
        if b.presion_base_ref_pa <= 0 or b.factor_degradacion <= 1.0 \
                or b.horas_mantenimiento <= 0:
            raise VacioInvalido("umbrales de bomba inválidos")
        if not b.fuente_umbral.strip():
            raise VacioInvalido("fuente_umbral obligatoria (49.11)")
        if not self._activo_existe(b.activo_id):
            raise VacioInvalido(f"activo {b.activo_id} inexistente")
        reg = {"bomba_id": b.bomba_id, "tipo": b.tipo,
               "activo_id": b.activo_id,
               "presion_base_ref_pa": float(b.presion_base_ref_pa),
               "factor_degradacion": float(b.factor_degradacion),
               "horas_mantenimiento": float(b.horas_mantenimiento),
               "fuente_umbral": b.fuente_umbral,
               "estado_umbral": self._marcador(b.fuente_externa),
               "motivo": b.motivo, "registrado_en": _ahora(),
               "version_modelo": VACUUM_VERSION}
        self._bombas[b.bomba_id] = reg
        self._mediciones[b.bomba_id] = []
        self._auditar(usuario, "registrar_bomba",
                      f"{b.bomba_id} ({b.tipo})")
        return dict(reg)

    def registrar_tramo(self, t: TramoLinea, usuario: str) -> dict:
        if t.tramo_id in self._tramos:
            raise VacioInvalido(
                f"tramo {t.tramo_id} ya registrado — nunca se sobrescribe")
        if t.tipo not in TIPOS_TRAMO:
            raise VacioInvalido(f"tipo {t.tipo!r} no válido: {TIPOS_TRAMO}")
        if t.umbral_fuga_mbar_l_s <= 0 or t.umbral_caida_presion_pa <= 0:
            raise VacioInvalido("umbrales de tramo inválidos")
        if not t.fuente_umbral.strip():
            raise VacioInvalido("fuente_umbral obligatoria (49.11)")
        if not self._activo_existe(t.activo_id):
            raise VacioInvalido(f"activo {t.activo_id} inexistente")
        reg = {"tramo_id": t.tramo_id, "tipo": t.tipo,
               "activo_id": t.activo_id,
               "umbral_fuga_mbar_l_s": float(t.umbral_fuga_mbar_l_s),
               "umbral_caida_presion_pa": float(t.umbral_caida_presion_pa),
               "fuente_umbral": t.fuente_umbral,
               "estado_umbral": self._marcador(t.fuente_externa),
               "motivo": t.motivo, "registrado_en": _ahora(),
               "version_modelo": VACUUM_VERSION}
        self._tramos[t.tramo_id] = reg
        self._mediciones[t.tramo_id] = []
        self._auditar(usuario, "registrar_tramo",
                      f"{t.tramo_id} ({t.tipo})")
        return dict(reg)

    # ---------------------------------------------------- mediciones
    def registrar_medicion(self, elemento_id: str, m: MedicionVacio,
                           usuario: str) -> dict:
        es_bomba = elemento_id in self._bombas
        es_tramo = elemento_id in self._tramos
        if not (es_bomba or es_tramo):
            raise VacioInvalido(f"elemento {elemento_id} inexistente")
        validas = VARIABLES_BOMBA if es_bomba else VARIABLES_TRAMO
        if m.variable not in validas:
            raise VacioInvalido(
                f"variable {m.variable!r} no válida para "
                f"{'bomba' if es_bomba else 'tramo'}: {validas}")
        if m.valor < 0:
            raise VacioInvalido("valor debe ser >= 0")
        if not m.origen.strip():
            raise VacioInvalido(
                "origen obligatorio — la medición nace de telemetría o "
                "prueba registrada, nunca simulada")
        med = {"variable": m.variable, "valor": float(m.valor),
               "origen": m.origen, "ts": m.ts or _ahora()}
        self._mediciones[elemento_id].append(med)
        self._auditar(usuario, "registrar_medicion",
                      f"{elemento_id} {m.variable}={m.valor} ({m.origen})")
        return dict(med)

    # --------------------------------------------------------- salud
    @staticmethod
    def _ultima(mediciones: list[dict], variable: str) -> dict | None:
        for m in reversed(mediciones):
            if m["variable"] == variable:
                return m
        return None

    def salud_bomba(self, bomba_id: str) -> dict:
        if bomba_id not in self._bombas:
            raise VacioInvalido(f"bomba {bomba_id} inexistente")
        b = dict(self._bombas[bomba_id])
        meds = self._mediciones[bomba_id]
        base = self._ultima(meds, "presion_base_pa")
        horas = sum(m["valor"] for m in meds
                    if m["variable"] == "horas_operacion")
        estado, causas = "verde", []
        if base is not None:
            factor = base["valor"] / b["presion_base_ref_pa"]
            b["presion_base_actual_pa"] = base["valor"]
            b["factor_actual"] = round(factor, 3)
            if factor >= b["factor_degradacion"]:
                estado, causas = "rojo", causas + [
                    f"vacío base degradado {factor:.2f}× "
                    f"(umbral {b['factor_degradacion']}×)"]
            elif factor >= 0.75 * b["factor_degradacion"]:
                estado, causas = "ambar", causas + [
                    f"vacío base al {factor:.2f}× del umbral"]
        else:
            b["presion_base_actual_pa"] = None
            b["factor_actual"] = "sin_mediciones"
        b["horas_operacion"] = round(horas, 2)
        b["horas_pct"] = round(100.0 * horas / b["horas_mantenimiento"], 2)
        if b["horas_pct"] >= 100.0:
            estado = "rojo"
            causas.append("horas sobre umbral de mantenimiento")
        elif b["horas_pct"] >= 80.0 and estado == "verde":
            estado = "ambar"
            causas.append("horas ≥80 % del umbral")
        b["estado"] = estado
        b["causas"] = causas
        b["recomendacion"] = (
            "RECOMENDACIÓN (soporte a la decisión 18.10 — la plataforma "
            "no decide): " + "; ".join(causas)) if estado == "rojo" else None
        b["mediciones"] = [dict(m) for m in meds]
        return b

    def salud_tramo(self, tramo_id: str) -> dict:
        if tramo_id not in self._tramos:
            raise VacioInvalido(f"tramo {tramo_id} inexistente")
        t = dict(self._tramos[tramo_id])
        meds = self._mediciones[tramo_id]
        fuga = self._ultima(meds, "tasa_fuga_mbar_l_s")
        caida = self._ultima(meds, "caida_presion_pa")
        estado, causas = "verde", []
        if fuga is not None:
            t["tasa_fuga_actual_mbar_l_s"] = fuga["valor"]
            if fuga["valor"] > t["umbral_fuga_mbar_l_s"]:
                estado, causas = "rojo", causas + [
                    f"FUGA {fuga['valor']:.2e} mbar·L/s sobre umbral "
                    f"{t['umbral_fuga_mbar_l_s']:.2e}"]
        else:
            t["tasa_fuga_actual_mbar_l_s"] = None
        if caida is not None:
            t["caida_presion_actual_pa"] = caida["valor"]
            if caida["valor"] > t["umbral_caida_presion_pa"] and \
                    estado == "verde":
                estado, causas = "ambar", causas + [
                    "caída de presión sobre umbral — posible obstrucción "
                    "o fuga incipiente"]
        t["estado"] = estado
        t["causas"] = causas
        t["recomendacion"] = (
            "RECOMENDACIÓN (soporte a la decisión 18.10 — la plataforma "
            "no decide): " + "; ".join(causas)) if estado == "rojo" else None
        t["mediciones"] = [dict(m) for m in meds]
        return t

    def tablero(self) -> dict:
        return {
            "bombas": [self.salud_bomba(bid) for bid in self._bombas],
            "tramos": [self.salud_tramo(tid) for tid in self._tramos],
        }
