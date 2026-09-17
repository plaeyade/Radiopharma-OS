"""Salud de Componentes Consumibles del blanco y del ciclotrón (Fase 27).

Extensión del Asset Lifecycle (EDS cap. 34) para piezas sacrificiales
cuya vida útil se mide por USO ACUMULADO REAL — nunca estimado:

- **Havar foil** (ventana del blanco, aleación base Co): vida gestionada
  en µA·h integrados de haz sobre la ventana. Su activación (⁶⁰Co/⁵⁸Co/
  ⁵⁷Co) se cubre en la hoja de ruta MC — módulo Bateman de muros y
  componentes.
- **Fuente de iones**: vida en minutos de arco.
- **Cuerpo de blanco** (Ag/Nb): vida en lotes procesados.

Reglas canónicas aplicadas:

- 49.11: todo umbral exige `fuente_umbral` declarada. Si la fuente no
  es externa (fabricante/norma), el componente queda marcado
  `estado_umbral: declarado_interno_pendiente_fuente` — el tablero lo
  muestra, nunca lo oculta.
- Los contadores SOLO se alimentan de eventos de uso con `origen`
  obligatorio (corrida/irradiación/mantenimiento registrado): un
  componente sin eventos reporta consumo 0 real y proyección
  `sin_historial` — jamás inventada.
- 18.10: la recomendación de reemplazo es soporte a la decisión y se
  etiqueta como tal; el reemplazo es una DECISIÓN OPERATIVA que exige
  `responsable` y `motivo`, y queda registrada append-only (ALCOA+).
- Registros append-only: ni eventos ni reemplazos se sobrescriben
  (33.24/34.24, auditoría en todas las operaciones).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.domain.facility_twin import FacilityTwin

COMPONENT_HEALTH_VERSION = "component-health-1.0.0"

TIPOS_COMPONENTE = ("havar_foil", "fuente_iones", "cuerpo_blanco")

# Unidad de vida permitida por tipo (declaración de ingeniería).
UNIDAD_VIDA_POR_TIPO = {
    "havar_foil": "uA_h",        # µA·h integrados sobre la ventana
    "fuente_iones": "min_arco",  # minutos de arco de la fuente
    "cuerpo_blanco": "lote",     # lotes de irradiación procesados
}

ESTADOS_DESGASTE = ("verde", "ambar", "rojo", "excedido")


class ComponentHealthInvalido(ValueError):
    """Componente, evento de uso o reemplazo inválido."""


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Componente:
    """Pieza sacrificial registrada (nunca sobrescrita)."""
    componente_id: str
    tipo: str                     # TIPOS_COMPONENTE
    serie: str                    # nº de serie de la pieza instalada
    activo_id: str                # activo padre en el Asset Registry
    umbral_vida: float            # en la unidad de vida del tipo
    fuente_umbral: str            # 49.11 — obligatoria, se declara
    motivo: str = ""              # motivo del registro (ALCOA+)
    fuente_externa: bool = False  # False → marcador honesto 49.11
    instalado_en: str = ""        # ts ISO; vacío → ahora


@dataclass
class EventoUso:
    """Consumo REAL con origen obligatorio (append-only)."""
    cantidad: float               # > 0, en la unidad de vida
    origen: str                   # p.ej. "irradiacion RQ-0001 evidencia_v072"
    ts: str = ""


@dataclass
class Reemplazo:
    """Decisión operativa de reemplazo (18.10) — append-only."""
    motivo: str
    responsable: str
    nueva_serie: str
    ts: str = ""


class ComponentHealth:
    """Registro y tablero de desgaste de componentes consumibles."""

    def __init__(self, twin: FacilityTwin) -> None:
        self._twin = twin
        self._componentes: dict[str, dict] = {}
        self._eventos: dict[str, list[dict]] = {}
        self._reemplazos: dict[str, list[dict]] = {}
        self._audit: list[dict] = []

    # ---------------------------------------------------------- util
    def _auditar(self, usuario: str, accion: str, detalle: str) -> None:
        self._audit.append({"ts": _ahora(), "usuario": usuario,
                            "accion": accion, "detalle": detalle})

    def auditoria(self) -> list[dict]:
        return list(self._audit)

    # ------------------------------------------------------ registro
    def registrar_componente(self, c: Componente, usuario: str) -> dict:
        if c.componente_id in self._componentes:
            raise ComponentHealthInvalido(
                f"componente {c.componente_id} ya registrado — "
                "el registro nunca sobrescribe")
        if c.tipo not in TIPOS_COMPONENTE:
            raise ComponentHealthInvalido(
                f"tipo {c.tipo!r} no válido: {TIPOS_COMPONENTE}")
        if c.umbral_vida <= 0:
            raise ComponentHealthInvalido("umbral_vida debe ser > 0")
        if not c.fuente_umbral.strip():
            raise ComponentHealthInvalido(
                "fuente_umbral obligatoria (49.11) — si no hay fuente "
                "externa, declarar la interna y el componente queda "
                "marcado")
        if not c.serie.strip():
            raise ComponentHealthInvalido("serie obligatoria")
        activos = {a["activo_id"] for a in self._twin.activos()}
        if c.activo_id not in activos:
            raise ComponentHealthInvalido(
                f"activo {c.activo_id} inexistente en el Asset Registry")
        reg = {
            "componente_id": c.componente_id,
            "tipo": c.tipo,
            "serie": c.serie,
            "activo_id": c.activo_id,
            "unidad_vida": UNIDAD_VIDA_POR_TIPO[c.tipo],
            "umbral_vida": float(c.umbral_vida),
            "fuente_umbral": c.fuente_umbral,
            "estado_umbral": ("fuente_externa_citada" if c.fuente_externa
                              else "declarado_interno_pendiente_fuente"),
            "motivo": c.motivo,
            "instalado_en": c.instalado_en or _ahora(),
            "version_modelo": COMPONENT_HEALTH_VERSION,
        }
        self._componentes[c.componente_id] = reg
        self._eventos[c.componente_id] = []
        self._reemplazos[c.componente_id] = []
        self._auditar(usuario, "registrar_componente",
                      f"{c.componente_id} ({c.tipo}, serie {c.serie})")
        return dict(reg)

    # ---------------------------------------------------------- uso
    def registrar_uso(self, componente_id: str, e: EventoUso,
                      usuario: str) -> dict:
        comp = self._get(componente_id)
        if e.cantidad <= 0:
            raise ComponentHealthInvalido("cantidad debe ser > 0")
        if not e.origen.strip():
            raise ComponentHealthInvalido(
                "origen obligatorio — el consumo nace de una corrida o "
                "intervención registrada, nunca estimado")
        ev = {"cantidad": float(e.cantidad),
              "unidad": comp["unidad_vida"],
              "origen": e.origen, "ts": e.ts or _ahora()}
        self._eventos[componente_id].append(ev)
        self._auditar(usuario, "registrar_uso",
                      f"{componente_id} +{e.cantidad} "
                      f"{comp['unidad_vida']} ({e.origen})")
        return dict(ev)

    # ------------------------------------------------------ reemplazo
    def registrar_reemplazo(self, componente_id: str, r: Reemplazo,
                            usuario: str) -> dict:
        comp = self._get(componente_id)
        if not r.motivo.strip():
            raise ComponentHealthInvalido("motivo obligatorio (ALCOA+)")
        if not r.responsable.strip():
            raise ComponentHealthInvalido(
                "responsable obligatorio — el reemplazo es una decisión "
                "operativa registrada (18.10)")
        if not r.nueva_serie.strip():
            raise ComponentHealthInvalido("nueva_serie obligatoria")
        rep = {"motivo": r.motivo, "responsable": r.responsable,
               "serie_retirada": comp["serie"],
               "serie_instalada": r.nueva_serie,
               "consumo_al_retiro": self._consumo_total(componente_id),
               "n_eventos_al_retiro": len(self._eventos[componente_id]),
               "ts": r.ts or _ahora()}
        self._reemplazos[componente_id].append(rep)
        # Nueva pieza: el tramo nuevo arranca en cero de forma DECLARADA;
        # los eventos del tramo anterior NO se borran (append-only) — el
        # consumo vigente se calcula restando los retiros registrados.
        comp["serie"] = r.nueva_serie
        comp["instalado_en"] = rep["ts"]
        self._auditar(usuario, "registrar_reemplazo",
                      f"{componente_id}: {rep['serie_retirada']} -> "
                      f"{r.nueva_serie} por {r.responsable}")
        return dict(rep)

    # --------------------------------------------------------- salud
    def _get(self, componente_id: str) -> dict:
        try:
            return self._componentes[componente_id]
        except KeyError:
            raise ComponentHealthInvalido(
                f"componente {componente_id} inexistente")

    def _consumo_total(self, componente_id: str) -> float:
        return sum(e["cantidad"] for e in self._eventos[componente_id])

    def _tramo_vigente(self, componente_id: str) -> list[dict]:
        """Eventos del tramo actual (posteriores al último reemplazo)."""
        reps = self._reemplazos[componente_id]
        inicio = reps[-1]["n_eventos_al_retiro"] if reps else 0
        return self._eventos[componente_id][inicio:]

    def _consumo(self, componente_id: str) -> float:
        return round(sum(e["cantidad"]
                         for e in self._tramo_vigente(componente_id)), 6)

    def salud(self, componente_id: str) -> dict:
        comp = dict(self._get(componente_id))
        consumo = self._consumo(componente_id)
        pct = round(100.0 * consumo / comp["umbral_vida"], 2)
        if pct >= 100.0:
            estado = "excedido"
        elif pct >= 90.0:
            estado = "rojo"
        elif pct >= 70.0:
            estado = "ambar"
        else:
            estado = "verde"
        eventos = self._tramo_vigente(componente_id)
        if eventos:
            media = consumo / len(eventos)
            restante = max(comp["umbral_vida"] - consumo, 0.0)
            proyeccion = round(restante / media, 1)
        else:
            proyeccion = None  # honesto: sin historial no se proyecta
        recomendacion = None
        if estado in ("rojo", "excedido"):
            recomendacion = (
                "RECOMENDACIÓN (soporte a la decisión 18.10 — la "
                "plataforma no decide): planificar reemplazo de "
                f"{componente_id}; la decisión y su registro son del "
                "responsable autorizado")
        return {
            **comp,
            "vida_consumida": consumo,
            "vida_pct": pct,
            "estado_desgaste": estado,
            "eventos_uso": [dict(e) for e in eventos],
            "historial_eventos_total": len(self._eventos[componente_id]),
            "reemplazos": [dict(r) for r in self._reemplazos[componente_id]],
            "eventos_restantes_proyectados": (
                proyeccion if proyeccion is not None else "sin_historial"),
            "recomendacion": recomendacion,
        }

    def tablero(self) -> list[dict]:
        return [self.salud(cid) for cid in self._componentes]
