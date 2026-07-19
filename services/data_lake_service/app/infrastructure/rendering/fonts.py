"""Fuentes TrueType incrustables para documentos archivables (PDF/A).

Las fuentes base-14 de PDF (Helvetica, Courier) no se incrustan en el
archivo y por tanto violan PDF/A. Aquí se registran las DejaVu
(Bitstream Vera license, ver assets/fonts/LICENSE-DejaVu.txt), que
reportlab subsetea e incrusta automáticamente (FontFile2), y con
cobertura unicode para µA, ±, ¹⁸F, →, ✓, etc.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_ASSETS = Path(__file__).resolve().parents[2] / "assets" / "fonts"

SANS = "DVS"
SANS_BOLD = "DVS-Bold"
SANS_OBLIQUE = "DVS-Oblique"
MONO = "DVSMono"

_registradas = False


def registrar_fuentes() -> None:
    """Registra las DejaVu una sola vez por proceso (idempotente).

    Además se registran *alias* con los nombres base-14 (Helvetica, Courier):
    reportlab emite un reset de estado de texto `BT /F1 12 Tf ET` al abrir
    cada página, que referencia Helvetica aunque no dibuje texto. Con el
    alias, esa referencia también resuelve a una TrueType incrustada y el
    documento queda conforme con PDF/A-2b sin excepciones.
    """
    global _registradas
    if _registradas:
        return
    ttf = {
        SANS: "DejaVuSans.ttf",
        SANS_BOLD: "DejaVuSans-Bold.ttf",
        SANS_OBLIQUE: "DejaVuSans-Oblique.ttf",
        MONO: "DejaVuSansMono.ttf",
        # alias base-14 → DejaVu (quedan incrustadas, BaseFont DejaVu*)
        "Helvetica": "DejaVuSans.ttf",
        "Helvetica-Bold": "DejaVuSans-Bold.ttf",
        "Helvetica-Oblique": "DejaVuSans-Oblique.ttf",
        "Courier": "DejaVuSansMono.ttf",
    }
    for nombre, archivo in ttf.items():
        pdfmetrics.registerFont(TTFont(nombre, str(_ASSETS / archivo)))
    pdfmetrics.registerFontFamily(
        SANS, normal=SANS, bold=SANS_BOLD, italic=SANS_OBLIQUE, boldItalic=SANS_BOLD)
    _registradas = True
