"""Tests del extractor documental REAL (45.7): PDF (pypdf) + OCR (Tesseract)."""
from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.presentation.routers import rag_api
from app.domain.rag_engine import RagEngine


@pytest.fixture()
def client():
    rag_api.init(RagEngine())
    return TestClient(app)


def _pdf_minimo(texto: str) -> bytes:
    """PDF 1.4 mínimo pero REAL con xref correcto y texto Helvetica."""
    stream = f"BT /F1 18 Tf 72 720 Td ({texto}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
         b" /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"),
        b"<< /Length " + str(len(stream)).encode() +
        b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, cuerpo in enumerate(objs, start=1):
        offsets.append(len(pdf))
        pdf += f"{i} 0 obj\n".encode() + cuerpo + b"\nendobj\n"
    xref_pos = len(pdf)
    n = len(objs) + 1
    pdf += f"xref\n0 {n}\n".encode()
    pdf += b"0000000000 65535 f \n"
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n".encode()
    pdf += (f"trailer\n<< /Size {n} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF").encode()
    return bytes(pdf)


def test_extraccion_pdf_real(client):
    pdf = _pdf_minimo("F18 vida media 109.77 minutos")
    r = client.post("/api/v1/rag/documents/parse", json={
        "nombre_archivo": "ficha_f18.pdf",
        "contenido_b64": base64.b64encode(pdf).decode()})
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert "109.77" in cuerpo["texto"]
    assert cuerpo["formato"] == "pdf"
    assert cuerpo["paginas"] == 1
    assert len(cuerpo["sha256_original"]) == 64
    assert cuerpo["extractor"] == "document-extractor-1.0.0"


def test_pdf_ilegible_error_real(client):
    r = client.post("/api/v1/rag/documents/parse", json={
        "nombre_archivo": "roto.pdf",
        "contenido_b64": base64.b64encode(b"%PDF-1.4 garbage").decode()})
    assert r.status_code == 422
    assert "PDF" in r.json()["detail"]


def test_ocr_imagen_real(client):
    """OCR REAL con Tesseract sobre una imagen generada con PIL."""
    from PIL import Image, ImageDraw, ImageFont
    import io
    img = Image.new("RGB", (900, 120), "white")
    draw = ImageDraw.Draw(img)
    try:
        fuente = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
    except Exception:
        fuente = ImageFont.load_default()
    draw.text((10, 30), "RADIOPHARMA 45", fill="black", font=fuente)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    r = client.post("/api/v1/rag/documents/parse", json={
        "nombre_archivo": "etiqueta.png",
        "contenido_b64": base64.b64encode(buf.getvalue()).decode()})
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert "RADIOPHARMA" in cuerpo["texto"].upper()
    assert cuerpo["ocr_utilizado"] is True


def test_documento_pdf_indexable_en_rag(client):
    """El texto extraído del PDF alimenta el índice y la recuperación."""
    pdf = _pdf_minimo("TALYS calcula secciones eficaces de reaccion")
    parse = client.post("/api/v1/rag/documents/parse", json={
        "nombre_archivo": "manual_talys.pdf",
        "contenido_b64": base64.b64encode(pdf).decode()})
    assert parse.status_code == 201
    r = client.post("/api/v1/rag/documents", json={
        "documento_id": "doc-talys", "titulo": "Manual TALYS",
        "tipo": "manual", "contenido_texto": parse.json()["texto"],
        "version": "1.0", "origen": "physics-lab", "usuario": "doc"})
    assert r.status_code == 201, r.text
    # segundo documento: con n=1 el TF-IDF anula los pesos (log(1)=0)
    r = client.post("/api/v1/rag/documents", json={
        "documento_id": "doc-hvac", "titulo": "Manual HVAC",
        "tipo": "manual", "contenido_texto": "presión en cascada de "
        "zonas calientes y caudales de renovación",
        "version": "1.0", "origen": "facility", "usuario": "doc"})
    assert r.status_code == 201
    rec = client.post("/api/v1/rag/retrieve", json={
        "consulta": "secciones eficaces", "k": 3, "usuario": "fisico1"})
    assert rec.status_code == 200
    assert any(x["documento_id"] == "doc-talys"
               for x in rec.json()["resultados"])


def test_estado_extractor_honesto(client):
    r = client.get("/api/v1/rag/extractor-status")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["pypdf"] is True
    assert "eng" in cuerpo["tesseract_idiomas"]
    assert cuerpo["poppler"] is True
    assert "nunca se rellenan" in cuerpo["nota"]
