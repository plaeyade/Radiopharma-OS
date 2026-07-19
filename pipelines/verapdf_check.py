#!/usr/bin/env python3
"""
Gate de archivo documental: verificación formal PDF/A de un PDF con veraPDF
(validador de referencia ISO 19005 del PDF Association).

Uso:
    python pipelines/verapdf_check.py ebr.pdf [--cmd verapdf]

Salidas: 0 = CONFORME · 1 = NO CONFORME · 2 = herramienta no disponible/error.
En CI (EDS v2.0, archivo documental): este gate debe pasar para cualquier
eBR antes de archivarlo.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                      / "services" / "data_lake_service"))
from app.infrastructure.rendering.verapdf import validate_with_verapdf  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Verificación formal PDF/A (veraPDF)")
    ap.add_argument("pdf", help="Ruta del PDF a validar")
    ap.add_argument("--cmd", default=None,
                    help="Ejecutable veraPDF (defecto: VERAPDF_CMD o 'verapdf')")
    args = ap.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.is_file():
        print(f"ERROR: no existe {pdf_path}", file=sys.stderr)
        return 2

    r = validate_with_verapdf(pdf_path.read_bytes(), cmd=args.cmd)
    if not r.available:
        print(f"veraPDF no disponible: {r.error}", file=sys.stderr)
        print("Instálalo o usa la imagen: docker run --rm -v $(pwd):/data "
              "verapdf/verapdf /data/archivo.pdf", file=sys.stderr)
        return 2
    if r.compliant is None:
        print(f"Validación no concluyente: {r.error}", file=sys.stderr)
        return 2
    if r.compliant:
        print(f"CONFORME · {r.summary}")
        return 0
    print(f"NO CONFORME · {r.summary}")
    for rule in r.failed_rules:
        print(f"  - {rule}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
