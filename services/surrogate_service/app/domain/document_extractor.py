"""Extractor documental REAL (45.7): PDF con capa de texto (pypdf),
PDF escaneado vía render + OCR (poppler + Tesseract) e imágenes (OCR).

Honestidad canónica:
- El texto extraído es REAL; si una página no tiene capa de texto y el
  OCR no está disponible (o no reconoce nada), la página se reporta en
  ``paginas_sin_texto`` — nunca se rellena con contenido inventado.
- Idiomas OCR disponibles se reportan tal cual (tessdata del sistema).
- El original NUNCA se modifica; su sha256 lo registra el parser (45.7).
"""
from __future__ import annotations

import hashlib
import io
import subprocess
import tempfile
import os

EXTRACTOR_VERSION = "document-extractor-1.0.0"


class ExtraccionInvalida(ValueError):
    """Documento malformado o extracción imposible (45.7/45.21)."""


def idiomas_ocr() -> list[str]:
    """Idiomas REALES instalados en el sistema."""
    try:
        salida = subprocess.run(["tesseract", "--list-langs"],
                                capture_output=True, text=True, timeout=10)
        return [l.strip() for l in salida.stdout.splitlines()[1:]
                if l.strip()]
    except Exception:
        return []


def _ocr_imagen_bytes(imagen_bytes: bytes, idioma: str = "eng") -> str:
    """OCR REAL con Tesseract sobre bytes de imagen."""
    import pytesseract
    from PIL import Image
    img = Image.open(io.BytesIO(imagen_bytes))
    return pytesseract.image_to_string(img, lang=idioma).strip()


def _render_pagina_pdf(pdf_path: str, pagina: int) -> bytes | None:
    """Render real de una página a PNG vía poppler (pdftoppm)."""
    with tempfile.TemporaryDirectory() as tmp:
        prefijo = os.path.join(tmp, "pag")
        r = subprocess.run(
            ["pdftoppm", "-f", str(pagina), "-l", str(pagina),
             "-r", "200", "-png", pdf_path, prefijo],
            capture_output=True, timeout=60)
        if r.returncode != 0:
            return None
        for nombre in os.listdir(tmp):
            if nombre.endswith(".png"):
                return open(os.path.join(tmp, nombre), "rb").read()
    return None


def extraer_pdf(contenido: bytes, ocr: bool = True,
                idioma: str = "eng") -> dict:
    """Extracción REAL de un PDF (45.7):
    1) capa de texto con pypdf (real);
    2) páginas sin capa de texto → render + OCR real si `ocr` y el
       runtime están disponibles; si no, se reportan honestamente en
       ``paginas_sin_texto``.
    """
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(contenido))
    except Exception as exc:
        raise ExtraccionInvalida(
            f"PDF ilegible: {type(exc).__name__}: {exc}") from exc
    partes: list[str] = []
    paginas_sin_texto: list[int] = []
    paginas_ocr: list[int] = []
    ocr_disponible = bool(idiomas_ocr()) if ocr else False
    pdf_path = None
    try:
        for i, pagina in enumerate(reader.pages, start=1):
            texto = (pagina.extract_text() or "").strip()
            if texto:
                partes.append(texto)
                continue
            # sin capa de texto: intento OCR REAL
            if ocr_disponible:
                if pdf_path is None:
                    tmp = tempfile.NamedTemporaryFile(
                        suffix=".pdf", delete=False)
                    tmp.write(contenido)
                    tmp.close()
                    pdf_path = tmp.name
                png = _render_pagina_pdf(pdf_path, i)
                if png:
                    try:
                        texto_ocr = _ocr_imagen_bytes(png, idioma)
                    except Exception:
                        texto_ocr = ""
                    if texto_ocr:
                        partes.append(texto_ocr)
                        paginas_ocr.append(i)
                        continue
            paginas_sin_texto.append(i)
    finally:
        if pdf_path and os.path.exists(pdf_path):
            os.unlink(pdf_path)
    if not partes:
        raise ExtraccionInvalida(
            "PDF sin texto extraíble (ni capa de texto ni OCR con "
            "resultado); el contenido NO se inventa — el documento "
            "permanece en revisión (45.21)")
    return {"texto": "\n\n".join(partes),
            "paginas": len(reader.pages),
            "paginas_ocr": paginas_ocr,
            "paginas_sin_texto": paginas_sin_texto,
            "ocr_utilizado": bool(paginas_ocr),
            "idioma_ocr": idioma if paginas_ocr else None,
            "extractor": EXTRACTOR_VERSION}


def extraer_imagen(contenido: bytes, idioma: str = "eng") -> dict:
    """OCR REAL sobre imagen (png/jpg/tiff/bmp)."""
    if not idiomas_ocr():
        raise ExtraccionInvalida(
            "runtime OCR no disponible en el sistema; la extracción no "
            "se simula")
    try:
        texto = _ocr_imagen_bytes(contenido, idioma)
    except Exception as exc:
        raise ExtraccionInvalida(
            f"imagen ilegible para OCR: {type(exc).__name__}: {exc}"
            ) from exc
    if not texto:
        raise ExtraccionInvalida(
            "OCR sin resultado; el contenido NO se inventa — el "
            "documento permanece en revisión (45.21)")
    return {"texto": texto, "paginas": 1, "paginas_ocr": [1],
            "paginas_sin_texto": [], "ocr_utilizado": True,
            "idioma_ocr": idioma, "extractor": EXTRACTOR_VERSION}


def estado_extractor() -> dict:
    return {"version": EXTRACTOR_VERSION,
            "pypdf": _modulo_ok("pypdf"),
            "tesseract_idiomas": idiomas_ocr(),
            "poppler": bool(subprocess.run(
                ["which", "pdftoppm"], capture_output=True).stdout),
            "nota": ("extracción REAL; páginas sin capa de texto ni OCR "
                     "con resultado se reportan en paginas_sin_texto — "
                     "nunca se rellenan")}


def _modulo_ok(nombre: str) -> bool:
    try:
        __import__(nombre)
        return True
    except ImportError:
        return False
