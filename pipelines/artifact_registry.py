"""Registro de artefactos versionados (EDS 10.17/10.18).

10.17: toda imagen se construye con versión, commit, fecha e
identificador (etiquetas OCI inyectadas por --build-arg).
10.18: los artefactos (imágenes, paquetes, reportes de validación y
calificación) se registran con identificador, versión, hash de
integridad y fecha — el registro es inmutable: nunca se sobrescribe
una entrada.

Uso:  python pipelines/artifact_registry.py [--registry registry.json]
      --add <ruta> [--tipo zip] [--version vX]  |  --verify <ruta>
      --list
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "artifact_registry.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
            capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return "unknown"


def cargar(path: Path = DEFAULT_REGISTRY) -> dict:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"registro": "Radiopharma OS — artifact registry (10.18)",
            "artefactos": []}


def registrar(artefacto: Path, tipo: str, version: str,
              path: Path = DEFAULT_REGISTRY) -> dict:
    """Registra un artefacto con hash; nunca sobrescribe (10.18)."""
    reg = cargar(path)
    artefacto_id = f"{artefacto.name}:{version}"
    if any(a["artefacto_id"] == artefacto_id for a in reg["artefactos"]):
        raise ValueError(
            f"el artefacto {artefacto_id} ya está registrado: el registro "
            "es inmutable (10.18)")
    entrada = {
        "artefacto_id": artefacto_id,
        "tipo": tipo,
        "version": version,
        "sha256": _sha256(artefacto),
        "bytes": artefacto.stat().st_size,
        "commit": _git_commit(),
        "fecha": datetime.now(timezone.utc).isoformat(),
        "nota": "registro inmutable (10.18): las nuevas versiones generan "
                "nuevas entradas; ninguna se sobrescribe",
    }
    reg["artefactos"].append(entrada)
    path.write_text(json.dumps(reg, indent=1, ensure_ascii=False),
                    encoding="utf-8")
    return entrada


def verificar(artefacto: Path, path: Path = DEFAULT_REGISTRY) -> dict:
    """Verifica integridad contra el registro (ALCOA+)."""
    reg = cargar(path)
    digest = _sha256(artefacto)
    coinciden = [a for a in reg["artefactos"]
                 if a["sha256"] == digest and a["tipo"] != "imagen"]
    return {"artefacto": str(artefacto), "sha256": digest,
            "integridad_verificada": bool(coinciden),
            "entradas_coincidentes": [a["artefacto_id"] for a in coinciden]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    ap.add_argument("--add", default=None)
    ap.add_argument("--tipo", default="zip")
    ap.add_argument("--version", default=None)
    ap.add_argument("--verify", default=None)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    path = Path(args.registry)
    if args.add:
        artefacto = Path(args.add)
        version = args.version or _git_commit()
        entrada = registrar(artefacto, args.tipo, version, path)
        print(json.dumps(entrada, indent=1, ensure_ascii=False))
        return 0
    if args.verify:
        res = verificar(Path(args.verify), path)
        print(json.dumps(res, indent=1, ensure_ascii=False))
        return 0 if res["integridad_verificada"] else 1
    reg = cargar(path)
    print(json.dumps([a["artefacto_id"] for a in reg["artefactos"]],
                     indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
