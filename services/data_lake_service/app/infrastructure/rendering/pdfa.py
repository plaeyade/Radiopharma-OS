"""Conformidad PDF/A-2b (ISO 19005-2) para documentos archivables.

Convierte el PDF generado por reportlab en un PDF/A-2b autocontenido:

1. **OutputIntent ICC** — perfil sRGB incrustado (assets/color/sRGB.icc,
   generado con littlecms) que fija el espacio de color de salida.
2. **Metadatos XMP** — declaración de conformidad ``pdfaid:part=2`` /
   ``pdfaid:conformance=B`` más Dublin Core (título, creador).
3. **Versión PDF 1.7** — base de ISO 19005-2.

Las fuentes ya van incrustadas desde el renderer (DejaVu subseteada,
ver fonts.py): PDF/A-2b exige que *toda* fuente usada esté incrustada.

`validate_pdfa2b()` es un validador estructural interno (no sustituye a
veraPDF): comprueba los pilares verificables del formato — XMP de
conformidad, OutputIntent con ICC RGB, incrustación de fuentes en todas
las páginas (incl. Type0/CIDFont) y ausencia de cifrado. La validación
formal contra el modelo de ISO 19005-2 se ejecuta con veraPDF en la
ingesta del archivo documental.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pikepdf
from pikepdf import Array, Dictionary, Name

_ICC_PATH = Path(__file__).resolve().parents[2] / "assets" / "color" / "sRGB.icc"
_SRGB_ID = "sRGB IEC61966-2.1"


def to_pdfa2b(pdf_bytes: bytes, *, title: str = "",
              creator: str = "Radiopharma OS — Data Lake Service") -> bytes:
    """Declara un PDF de reportlab como PDF/A-2b y devuelve los bytes."""
    with pikepdf.open(BytesIO(pdf_bytes)) as pdf:
        # 1. OutputIntent con perfil ICC sRGB incrustado
        icc = pdf.make_stream(_ICC_PATH.read_bytes())
        icc["/N"] = 3  # componentes RGB
        oi = pdf.make_indirect(Dictionary(
            S=Name("/GTS_PDFA1"),
            OutputConditionIdentifier=_SRGB_ID,
            Info=_SRGB_ID,
            DestOutputProfile=icc,
        ))
        pdf.Root.OutputIntents = Array([oi])

        # 2. XMP: conformidad PDF/A-2b + Dublin Core
        with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
            meta["pdfaid:part"] = "2"
            meta["pdfaid:conformance"] = "B"
            meta["dc:creator"] = [creator]
            if title:
                meta["dc:title"] = title

        # 3. PDF 1.7 (base de ISO 19005-2) y regrabado normalizado
        out = BytesIO()
        pdf.save(out, min_version="1.7")
        return out.getvalue()


def _fuentes_de(font_dict) -> list:
    """Objetos /Font del diccionario, descendiendo en Type0."""
    out = []
    for f in font_dict.values():
        try:
            if "/DescendantFonts" in f:
                out.extend(f["/DescendantFonts"])
            else:
                out.append(f)
        except Exception:
            continue
    return out


def validate_pdfa2b(pdf_bytes: bytes) -> list[str]:
    """Validación estructural PDF/A-2b. Devuelve hallazgos ([] = conforme)."""
    hallazgos: list[str] = []
    if not pdf_bytes.startswith(b"%PDF-"):
        return ["no es un documento PDF"]
    with pikepdf.open(BytesIO(pdf_bytes)) as pdf:
        if pdf.is_encrypted:
            hallazgos.append("documento cifrado (prohibido en PDF/A)")

        # OutputIntent con ICC RGB
        ois = pdf.Root.get("/OutputIntents", [])
        if not ois:
            hallazgos.append("sin /OutputIntents")
        else:
            oi = ois[0]
            if str(oi.get("/S", "")) != "/GTS_PDFA1":
                hallazgos.append(f"/S de OutputIntent inesperado: {oi.get('/S')}")
            prof = oi.get("/DestOutputProfile")
            if prof is None:
                hallazgos.append("OutputIntent sin perfil ICC incrustado")
            elif int(prof.get("/N", 0)) != 3:
                hallazgos.append("perfil ICC no es RGB de 3 componentes")

        # XMP con declaración de conformidad
        if "/Metadata" not in pdf.Root:
            hallazgos.append("sin metadatos XMP")
        else:
            xmp = bytes(pdf.Root.Metadata.read_bytes()).decode("utf-8", "replace")
            if "pdfaid:part" not in xmp or ">2<" not in xmp:
                hallazgos.append("XMP sin pdfaid:part=2")
            if "pdfaid:conformance" not in xmp or ">B<" not in xmp:
                hallazgos.append("XMP sin pdfaid:conformance=B")

        # Todas las fuentes incrustadas (Type0 y simples)
        for n, page in enumerate(pdf.pages, start=1):
            recursos = page.get("/Resources", {})
            fuentes = recursos.get("/Font", {})
            for f in _fuentes_de(fuentes):
                desc = f.get("/FontDescriptor")
                incrustada = desc is not None and any(
                    k in desc for k in ("/FontFile", "/FontFile2", "/FontFile3"))
                if not incrustada:
                    nombre = f.get("/BaseFont", "?")
                    hallazgos.append(f"fuente no incrustada en página {n}: {nombre}")
    return hallazgos
