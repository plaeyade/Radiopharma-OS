"""Consulta directa a GAMMA-AI (motor científico del ecosistema) con citas verificables.

Dos caminos, ambos con evidencia `gamma/evidencia@1` que aquí se verifica recalculando el SHA-256 de
cada fragmento y el `source_id` del documento:
- En vivo: `gamma ecosistema servir` → GET {GAMMA_URL}/v1/ecosistema/evidencia?q=&k=&revision=
- Sin servicio: paquete `gamma/paquete_evidencia@1` generado por GAMMA y versionado en
  `pipelines/fixtures/gamma_evidencia_produccion.json` (consultas en
  `pipelines/fixtures/gamma_consultas_produccion.json`).

Toda evidencia de GAMMA es experimental y no apta para firma: respalda las fichas con la fuente,
la página y el fragmento, pero no las valida. Sólo stdlib.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request

CONTRATO_EVIDENCIA = "gamma/evidencia@1"
CONTRATO_PAQUETE = "gamma/paquete_evidencia@1"
ESTADO = "experimental_sin_validacion_clinica"
MAX_TEXTO = 1200
PAQUETE_DEF = pathlib.Path(__file__).resolve().parent / "fixtures" / "gamma_evidencia_produccion.json"


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def verificar_evidencia(ev: dict) -> tuple[list[dict], list[str]]:
    """Devuelve (citas verificadas, errores). Una cita que no verifica no se devuelve."""
    errores = []
    if not isinstance(ev, dict):
        return [], ["la evidencia no es un objeto"]
    if ev.get("contrato") != CONTRATO_EVIDENCIA:
        errores.append(f"contrato debe ser {CONTRATO_EVIDENCIA}")
    if ev.get("estado") != ESTADO or ev.get("no_apto_para_firma") is not True:
        errores.append("la evidencia de GAMMA no puede declararse validada ni apta para firma")
    citas = []
    for i, c in enumerate(ev.get("citas") or [], 1):
        doc, texto = str(c.get("sha256_documento", "")), str(c.get("texto", ""))
        motivo = None
        if len(doc) != 64 or c.get("source_id") != f"source_{doc[:32]}":
            motivo = "documento o source_id inválido"
        elif not texto.strip() or len(texto) > MAX_TEXTO:
            motivo = "texto vacío o demasiado largo"
        elif _sha(texto) != c.get("fragmento_sha256"):
            motivo = "el texto no coincide con su hash: fue alterado después de salir de GAMMA"
        if motivo:
            errores.append(f"cita {i}: {motivo}")
        else:
            citas.append(c)
    return (citas if not errores else []), errores


class PaqueteGamma:
    def __init__(self, datos: dict):
        if not isinstance(datos, dict) or datos.get("contrato") != CONTRATO_PAQUETE:
            raise ValueError(f"no es un paquete {CONTRATO_PAQUETE}")
        self.incluye_en_revision = bool(datos.get("incluye_en_revision"))
        self.fuentes = datos.get("fuentes") or {}
        self.generado_utc = datos.get("generado_utc")
        self.consultas = {}
        self.errores = []
        for c in datos.get("consultas") or []:
            citas, err = verificar_evidencia(c.get("evidencia"))
            self.errores += [f"{c.get('id')}: {e}" for e in err]
            self.consultas[str(c["id"])] = {"seccion": c.get("seccion", ""),
                                             "consulta": c["evidencia"].get("consulta", ""), "citas": citas}

    @classmethod
    def cargar(cls, ruta: pathlib.Path | None = None) -> PaqueteGamma:
        return cls(json.loads((ruta or PAQUETE_DEF).read_text(encoding="utf-8")))

    def referencias(self, consulta_id: str, maximo: int = 2) -> list[dict]:
        """Referencias legibles y verificables para una ficha."""
        c = self.consultas.get(consulta_id)
        if not c:
            return []
        return [referencia(x, self.fuentes, self.incluye_en_revision) for x in c["citas"][:maximo]]


def referencia(cita: dict, fuentes: dict, en_revision: bool) -> dict:
    f = fuentes.get(cita["source_id"], {})
    nombre = f.get("titulo") or cita["source_id"]
    if f.get("emisor"):
        nombre += f" ({f['emisor']})"
    return {
        "fuente": nombre,
        "pagina": cita.get("pagina"),
        "fragmento": cita["texto"],
        "source_id": cita["source_id"],
        "fragmento_sha256": cita["fragmento_sha256"],
        "en_revision": en_revision,
        "texto": f"{nombre}{', p. ' + str(cita['pagina']) if cita.get('pagina') else ''}: «{cita['texto']}» "
                 f"[GAMMA {cita['source_id']}; SHA-256 {cita['fragmento_sha256'][:12]}…; experimental, no apta para firma]",
    }


def consultar(consulta: str, k: int = 3, revision: bool = False, url: str | None = None,
              timeout: float = 8.0, abrir=urllib.request.urlopen) -> tuple[list[dict], list[str]]:
    """Consulta en vivo. Sin GAMMA_URL o si el servicio no responde, devuelve el error (no lanza)."""
    base = (url if url is not None else os.environ.get("GAMMA_URL", "")).rstrip("/")
    if not base:
        return [], ["GAMMA no configurado (GAMMA_URL)"]
    q = urllib.parse.urlencode({"q": consulta, "k": k, "revision": int(revision)})
    try:
        with abrir(f"{base}/v1/ecosistema/evidencia?{q}", timeout=timeout) as r:
            ev = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return [], [f"GAMMA no disponible: {exc}"]
    return verificar_evidencia(ev)
