"""
Verificación formal PDF/A con veraPDF (validador de referencia ISO 19005).

El gate interno `pdfa.validate_pdfa2b` hace comprobaciones estructurales;
veraPDF es el validador de referencia del PDF Association: su veredicto es
el que aguanta una inspección. Aquí se integra como subproceso (CLI) con
parseo del informe JSON.

Si el ejecutable no está disponible (dev sin Docker), el resultado lo indica
con available=False y la plataforma sigue operando con el gate interno.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass


@dataclass(frozen=True)
class VeraPdfResult:
    available: bool                       # ejecutable veraPDF presente
    compliant: bool | None = None         # veredicto formal (None si no corrió)
    profile: str = ""                     # perfil validado (PDF/A-2B…)
    failed_rules: tuple[str, ...] = ()
    summary: str = ""
    error: str = ""


def _parse_report(data: dict) -> VeraPdfResult:
    """Extrae el veredicto del informe JSON de veraPDF.

    Soporta el esquema actual (veraPDF ≥1.26: campo `compliant` y
    `statement` en validationResult) y el antiguo (`details.status`).
    """
    jobs = data.get("report", {}).get("jobs", [])
    if not jobs:
        return VeraPdfResult(available=True, compliant=None,
                             error="informe veraPDF sin jobs")
    results = jobs[0].get("validationResult", [])
    if not results:
        # PDF no parseable por veraPDF (corrupto) → no conforme
        exc = (jobs[0].get("itemDetails", {}).get("exception")
               or "veraPDF no pudo validar el documento")
        return VeraPdfResult(available=True, compliant=False, error=str(exc))
    vr = results[0]
    details = vr.get("details", {})
    profile = vr.get("profileName", "")
    # veredicto: esquema nuevo (bool) o antiguo (status "passed")
    compliant = vr.get("compliant")
    if compliant is None:
        compliant = str(details.get("status", "")).lower() == "passed"
    failed: list[str] = []
    for rule in details.get("ruleSummaries", []) or []:
        estado = str(rule.get("ruleStatus", rule.get("status", ""))).lower()
        if estado == "failed":
            failed.append(
                f"{rule.get('specification', '')} {rule.get('clause', '')} "
                f"(test {rule.get('testNumber', '')}): "
                f"{rule.get('description', '')}")
    statement = vr.get("statement") or details.get("status", "")
    summary = (f"{profile}: {statement} "
               f"({details.get('passedRules', '?')} reglas OK, "
               f"{details.get('failedRules', '?')} fallidas)")
    return VeraPdfResult(available=True, compliant=bool(compliant),
                         profile=profile, failed_rules=tuple(failed[:10]),
                         summary=summary)


def validate_with_verapdf(pdf_bytes: bytes,
                          cmd: str | None = None,
                          timeout_s: int = 120) -> VeraPdfResult:
    """Ejecuta veraPDF sobre los bytes dados. available=False si falta el CLI."""
    exe = cmd or os.environ.get("VERAPDF_CMD", "verapdf")
    if shutil.which(exe) is None:
        return VeraPdfResult(available=False,
                             error=f"ejecutable no encontrado: {exe}")
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
        fh.write(pdf_bytes)
        tmp_path = fh.name
    try:
        proc = subprocess.run(
            [exe, "--format", "json", tmp_path],
            capture_output=True, timeout=timeout_s, check=False)
        out = proc.stdout.decode("utf-8", "replace")
        if proc.returncode != 0 and not out.strip():
            return VeraPdfResult(
                available=True, compliant=None,
                error=f"veraPDF rc={proc.returncode}: "
                      f"{proc.stderr.decode('utf-8', 'replace')[:300]}")
        return _parse_report(json.loads(out))
    except subprocess.TimeoutExpired:
        return VeraPdfResult(available=True, compliant=None,
                             error=f"veraPDF superó {timeout_s} s")
    except json.JSONDecodeError as exc:
        return VeraPdfResult(available=True, compliant=None,
                             error=f"informe veraPDF no parseable: {exc}")
    finally:
        os.unlink(tmp_path)
