"""Informe cap. 19 — Biblioteca Universal de Radionúclidos.

Estructura completa por radionúclido (19.5): información nuclear
(reacción, energía umbral, sección eficaz, vida media, modos de
decaimiento, emisiones), física (blanco: material/enriquecimiento/
espesor/geometría — sólidos, líquidos y gaseosos 19.9), química
(precursor/síntesis/purificación/eficiencia 19.14), clínica
(indicaciones/dosis/ventana temporal/logística 19.15) y económica.

Biblioteca versionada (19.17): cada radionúclido registra identificador,
versión, fecha, bibliografía, autor e historial — las modificaciones
NUNCA sobrescriben versiones anteriores. Incorporación de nuevos
radionúclidos sin modificar el software principal (19.16).

Integraciones honestas: EXFOR 19.12 — los datos experimentales tienen
PRIORIDAD sobre los modelos teóricos y conservan referencia/versión/
fecha/fuente; SRIM 19.10 y TALYS 19.11 reportan su estado real; NNDC
19.13 alimenta los motores clínicos y logísticos.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

LIBRARY_VERSION = "1.0.0"
CATEGORIAS = ("PET", "SPECT", "terapeutico")
TIPOS_BLANCO = ("solido", "liquido", "gaseoso")
LN2 = math.log(2)


class BibliotecaInvalida(ValueError):
    pass


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class VersionRadionuclido:
    version: int
    fecha: str
    autor: str
    bibliografia: list[str]
    nuclear: dict[str, Any]
    fisica: dict[str, Any]
    quimica: dict[str, Any]
    clinica: dict[str, Any]
    economica: dict[str, Any]
    historial: str  # descripción del cambio


class RadionuclideLibrary:
    """Biblioteca Universal versionada de radionúclidos (cap. 19)."""

    def __init__(self, datos_exfor_estado: str = "no_configurado",
                 datos_srim_estado: str = "atima_en_yield_engine",
                 datos_talys_estado: str = "talys_en_nds"):
        self._radionuclidos: dict[str, list[VersionRadionuclido]] = {}
        self._datos_experimentales: dict[str, list[dict[str, Any]]] = {}
        self._estado_integraciones = {
            "srim": datos_srim_estado,
            "talys": datos_talys_estado,
            "exfor": datos_exfor_estado,
            "nndc": "integrado (decay repository)",
        }
        self._auditoria: list[dict[str, Any]] = []
        self._categorias: dict[str, str] = {}

    # ---------------- auditoría ALCOA+ ----------------
    def _auditar(self, accion: str, detalle: dict[str, Any], actor: str) -> None:
        self._auditoria.append({
            "evento_id": str(uuid.uuid4()),
            "accion": accion,
            "detalle": detalle,
            "actor": actor,
            "timestamp": _ahora(),
            "version_motor": LIBRARY_VERSION,
        })

    def auditoria(self) -> list[dict[str, Any]]:
        return list(self._auditoria)

    def estado_integraciones(self) -> dict[str, Any]:
        """19.10-19.13: estado REAL de cada integración."""
        return {**self._estado_integraciones,
                "nota": "cada integración reporta su estado real; EXFOR otorga "
                        "prioridad a los datos experimentales registrados (19.12)"}

    # ---------------- validación de estructura 19.5 ----------------
    @staticmethod
    def _validar_estructura(nuclear: dict[str, Any], fisica: dict[str, Any],
                            quimica: dict[str, Any], clinica: dict[str, Any],
                            economica: dict[str, Any]) -> None:
        req_nuclear = ["reaccion", "energia_umbral_mev", "vida_media_s",
                       "modos_decaimiento", "emisiones"]
        req_fisica = ["material_blanco", "tipo_blanco", "enriquecimiento",
                      "espesor", "geometria"]
        req_quimica = ["precursor", "sintesis", "purificacion", "eficiencia"]
        req_clinica = ["indicaciones", "dosis_habitual_mbq", "ventana_horas",
                       "logistica"]
        req_economica = ["costo", "rendimiento", "recuperacion", "rentabilidad"]
        for nombre, datos, reqs in (("nuclear", nuclear, req_nuclear),
                                    ("fisica", fisica, req_fisica),
                                    ("quimica", quimica, req_quimica),
                                    ("clinica", clinica, req_clinica),
                                    ("economica", economica, req_economica)):
            if not isinstance(datos, dict):
                raise BibliotecaInvalida(f"sección {nombre} obligatoria (19.5)")
            faltantes = [r for r in reqs if r not in datos]
            if faltantes:
                raise BibliotecaInvalida(f"sección {nombre} incompleta: faltan "
                                         f"{faltantes} (19.5)")
        if fisica["tipo_blanco"] not in TIPOS_BLANCO:
            raise BibliotecaInvalida(f"tipo_blanco debe ser uno de {TIPOS_BLANCO} (19.9)")
        if nuclear["vida_media_s"] <= 0:
            raise BibliotecaInvalida("vida_media_s debe ser positiva")
        if not 0 < quimica["eficiencia"] <= 1:
            raise BibliotecaInvalida("eficiencia química en (0, 1]")

    # ---------------- incorporación 19.16 + versionado 19.17 ----------------
    def incorporar(self, nuclide: str, categoria: str, nuclear: dict[str, Any],
                   fisica: dict[str, Any], quimica: dict[str, Any],
                   clinica: dict[str, Any], economica: dict[str, Any],
                   bibliografia: list[str], autor: str,
                   historial: str = "incorporación inicial") -> dict[str, Any]:
        if not nuclide or not autor:
            raise BibliotecaInvalida("nuclide y autor son obligatorios (19.17)")
        if categoria not in CATEGORIAS:
            raise BibliotecaInvalida(f"categoria debe ser una de {CATEGORIAS}")
        if not bibliografia:
            raise BibliotecaInvalida("bibliografía obligatoria (19.17)")
        self._validar_estructura(nuclear, fisica, quimica, clinica, economica)
        key = nuclide.lower()
        versiones = self._radionuclidos.setdefault(key, [])
        version = len(versiones) + 1  # nunca sobrescribe (19.17)
        versiones.append(VersionRadionuclido(
            version, _ahora(), autor, list(bibliografia), dict(nuclear),
            dict(fisica), dict(quimica), dict(clinica), dict(economica), historial))
        self._categorias[key] = categoria
        self._auditar("radionuclido_incorporado" if version == 1
                      else "radionuclido_nueva_version",
                      {"nuclide": key, "categoria": categoria, "version": version,
                       "historial": historial}, autor)
        return {"nuclide": key, "categoria": categoria, "version": version}

    def catalogo(self, categoria: str | None = None) -> list[dict[str, Any]]:
        salida = []
        for key in sorted(self._radionuclidos):
            v = self._radionuclidos[key][-1]
            entrada = {"nuclide": key, "version_vigente": v.version,
                       "vida_media_s": v.nuclear["vida_media_s"],
                       "reaccion": v.nuclear["reaccion"],
                       "blanco": v.fisica["material_blanco"],
                       "revisiones": len(self._radionuclidos[key])}
            if categoria is None or self._categoria(key) == categoria:
                salida.append(entrada)
        return salida

    def _categoria(self, key: str) -> str | None:
        return self._categorias.get(key)

    def radionuclido(self, nuclide: str, version: int | None = None) -> dict[str, Any]:
        key = nuclide.lower()
        versiones = self._radionuclidos.get(key)
        if not versiones:
            raise BibliotecaInvalida(f"radionúclido no registrado en la biblioteca: "
                                     f"{nuclide}")
        v = versiones[-1] if version is None else next(
            (x for x in versiones if x.version == version), None)
        if v is None:
            raise BibliotecaInvalida(f"versión {version} no registrada para {nuclide}")
        return {"nuclide": key, "categoria": self._categoria(key),
                "version": v.version, "fecha": v.fecha, "autor": v.autor,
                "bibliografia": list(v.bibliografia), "nuclear": dict(v.nuclear),
                "fisica": dict(v.fisica), "quimica": dict(v.quimica),
                "clinica": dict(v.clinica), "economica": dict(v.economica),
                "historial": v.historial, "revisiones": len(versiones)}

    # ---------------- datos experimentales EXFOR 19.12 ----------------
    def registrar_datos_experimentales(self, nuclide: str, tipo: str,
                                       datos: list[dict[str, Any]], referencia: str,
                                       version_datos: str, fecha: str, fuente: str,
                                       autor: str) -> dict[str, Any]:
        self.radionuclido(nuclide)  # debe existir en la biblioteca
        if not all([tipo, referencia, version_datos, fecha, fuente, autor]) \
                or not datos:
            raise BibliotecaInvalida("tipo, datos, referencia, version_datos, fecha, "
                                     "fuente y autor son obligatorios (19.12)")
        registro = {"registro_id": str(uuid.uuid4()), "tipo": tipo, "datos": datos,
                    "referencia": referencia, "version_datos": version_datos,
                    "fecha": fecha, "fuente": fuente, "registrado_en": _ahora(),
                    "prioridad": "experimental — prevalece sobre modelos teóricos "
                                 "(19.12)"}
        self._datos_experimentales.setdefault(nuclide.lower(), []).append(registro)
        self._auditar("datos_experimentales", {"nuclide": nuclide.lower(),
                      "tipo": tipo, "referencia": referencia}, autor)
        return dict(registro)

    def datos_experimentales(self, nuclide: str) -> list[dict[str, Any]]:
        self.radionuclido(nuclide)
        return [dict(r) for r in self._datos_experimentales.get(nuclide.lower(), [])]

    # ---------------- modelado radioquímico 19.14 ----------------
    def actividad_eos(self, nuclide: str, actividad_eob_gbqe: float,
                      horas_sintesis: float = 0.0) -> dict[str, Any]:
        """Actividad estimada al End Of Synthesis:
        A_EOS = A_EOB · e^(−λ·t_síntesis) · eficiencia · (1 − pérdidas)
              · rendimiento_purificación · factor_formulación.
        Fórmula documentada; parámetros desde la versión vigente (19.14).
        """
        r = self.radionuclido(nuclide)
        if actividad_eob_gbqe <= 0:
            raise BibliotecaInvalida("actividad_eob_gbqe debe ser positiva")
        q = r["quimica"]
        vida = r["nuclear"]["vida_media_s"]
        lam = LN2 / vida
        perdidas = q.get("perdidas", 0.0)
        rend_pur = q.get("rendimiento_purificacion", 1.0)
        factor_form = q.get("factor_formulacion", 1.0)
        decaimiento = math.exp(-lam * horas_sintesis * 3600)
        a_eos = actividad_eob_gbqe * decaimiento * q["eficiencia"] \
            * (1 - perdidas) * rend_pur * factor_form
        return {"nuclide": r["nuclide"], "version_biblioteca": r["version"],
                "actividad_eob_gbqe": actividad_eob_gbqe,
                "horas_sintesis": horas_sintesis,
                "factor_decaimiento": round(decaimiento, 6),
                "eficiencia": q["eficiencia"], "perdidas": perdidas,
                "rendimiento_purificacion": rend_pur,
                "factor_formulacion": factor_form,
                "actividad_eos_gbqe": round(a_eos, 6),
                "formula": "A_EOS = A_EOB·e^(−λt)·eficiencia·(1−pérdidas)"
                           "·rend_purificación·factor_formulación (19.14)"}

    # ---------------- modelado clínico 19.15 ----------------
    def ventana_clinica(self, nuclide: str) -> dict[str, Any]:
        r = self.radionuclido(nuclide)
        c = r["clinica"]
        vida = r["nuclear"]["vida_media_s"]
        lam = LN2 / vida
        ventana_h = c["ventana_horas"]
        fraccion = math.exp(-lam * ventana_h * 3600)
        return {"nuclide": r["nuclide"], "version_biblioteca": r["version"],
                "vida_media_s": vida, "ventana_horas": ventana_h,
                "fraccion_restante_en_ventana": round(fraccion, 6),
                "indicaciones": c["indicaciones"],
                "dosis_habitual_mbq": c["dosis_habitual_mbq"],
                "logistica": c["logistica"],
                "nota": "programación clínica del Operational Twin (19.15); "
                        "λ desde la vida media de la biblioteca"}
