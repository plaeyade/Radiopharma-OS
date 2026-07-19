"""
Render PDF del Electronic Batch Record para archivo regulatorio.

Genera la copia archivable, legible por humanos, del eBR consolidado:
lote + informes QC + firmas electrónicas + pista de auditoría + bloque
de integridad. Pensada como insumo del sistema de archivo documental.

Todas las fuentes son TrueType incrustadas (DejaVu, ver fonts.py) —
requisito de PDF/A-2b; la conversión y declaración de conformidad se
aplica en pdfa.py.
"""
from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

from ...domain.entities import EbrDocument
from .fonts import MONO, SANS, SANS_BOLD, SANS_OBLIQUE, registrar_fuentes

registrar_fuentes()

_M = 18 * mm                       # margen
_AZUL = colors.HexColor("#1a3a5c")
_GRIS = colors.HexColor("#f0f2f5")
_GRIS2 = colors.HexColor("#8a94a6")
_VERDE = colors.HexColor("#1d7a3d")
_ROJO = colors.HexColor("#b3261e")

_S = {
    "titulo": ParagraphStyle("titulo", fontName=SANS_BOLD,
                             fontSize=15, textColor=_AZUL, spaceAfter=2),
    "sub": ParagraphStyle("sub", fontName=SANS, fontSize=9,
                          textColor=_GRIS2, spaceAfter=8),
    "h": ParagraphStyle("h", fontName=SANS_BOLD, fontSize=11,
                        textColor=_AZUL, spaceBefore=10, spaceAfter=4),
    "celda": ParagraphStyle("celda", fontName=SANS, fontSize=8,
                            leading=10),
    "celda_b": ParagraphStyle("celda_b", fontName=SANS_BOLD, fontSize=8,
                              leading=10),
    "mono": ParagraphStyle("mono", fontName=MONO, fontSize=7.2,
                           leading=9.2),
    "pie": ParagraphStyle("pie", fontName=SANS_OBLIQUE, fontSize=7.5,
                          textColor=_GRIS2, spaceBefore=10),
}

_ESTILO_TABLA = TableStyle([
    # FONTNAME global: cualquier celda de texto plano (p. ej. "") también usa
    # fuente incrustada — una Helvetica base-14 rompería la conformidad PDF/A.
    ("FONTNAME", (0, 0), (-1, -1), SANS),
    ("BACKGROUND", (0, 0), (-1, 0), _AZUL),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), SANS_BOLD),
    ("FONTSIZE", (0, 0), (-1, -1), 8),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _GRIS]),
    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8cfd8")),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ("TOPPADDING", (0, 0), (-1, -1), 3),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
])


def _p(texto, estilo="celda") -> Paragraph:
    txt = str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(txt, _S[estilo])


def _tabla(encabezado: list[str], filas: list[list], anchos: list[float]) -> Table:
    estilo_hd = ParagraphStyle("hd", fontName=SANS_BOLD, fontSize=8)
    data = [[Paragraph(f'<font color="white">{h}</font>', estilo_hd)
             for h in encabezado]]
    for fila in filas:
        data.append([c if isinstance(c, Paragraph) else _p(c) for c in fila])
    t = Table(data, colWidths=anchos, repeatRows=1)
    t.setStyle(_ESTILO_TABLA)
    return t


def _marca_estado(valor: str) -> Paragraph:
    v = (valor or "").lower().split()[0] if valor else ""
    color = "#1d7a3d" if v in ("pass", "released", "completed") else (
        "#b3261e" if v in ("fail", "rejected", "voided") else "#8a6d1d")
    txt = str(valor).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(f'<font color="{color}"><b>{txt}</b></font>', _S["celda"])


class EbrPdfRenderer:
    """Renderiza un EbrDocument a bytes PDF (copia archivable)."""

    ANCHO = A4[0] - 2 * _M

    def render(self, doc: EbrDocument) -> bytes:
        buf = BytesIO()
        pdf = BaseDocTemplate(
            buf, pagesize=A4,
            leftMargin=_M, rightMargin=_M, topMargin=_M, bottomMargin=_M,
            title=f"eBR {doc.batch.get('batch_id', '')}",
            author="Radiopharma OS - Data Lake Service",
            subject="Electronic Batch Record (copia archivable)")
        frame = Frame(_M, _M, A4[0] - 2 * _M, A4[1] - 2 * _M, id="main")
        pdf.addPageTemplates([PageTemplate(
            id="ebr", frames=[frame], onPage=self._pie_pagina)])

        story = self._portada(doc)
        story += self._seccion_lote(doc)
        story += self._seccion_qc(doc)
        story += self._seccion_firmas(doc)
        story += self._seccion_auditoria(doc)
        story += self._seccion_integridad(doc)
        pdf.build(story)
        return buf.getvalue()

    # ------------------------------------------------------------- secciones
    def _portada(self, doc: EbrDocument) -> list:
        b = doc.batch
        return [
            Paragraph("Radiopharma OS — Electronic Batch Record", _S["titulo"]),
            Paragraph(
                f"eBR {doc.ebr_id} · generado {doc.generated_at.isoformat()} · "
                f"lote {b.get('batch_id', '')} · {b.get('product_nuclide', '')} "
                f"({b.get('reaction_id', '')})", _S["sub"]),
        ]

    def _seccion_lote(self, doc: EbrDocument) -> list:
        b = doc.batch
        beam, res, lin = b["beam"], b["results"], b["lineage"]
        if b.get("released_by"):
            liberacion = (f"{b['release_status']} por {b['released_by']}"
                          f" — {b.get('release_reason') or ''}")
        else:
            liberacion = "pendiente"
        filas = [
            ["Registrado", f"{b['created_at']} por {b['created_by']}"],
            ["Blanco / producto", f"{b['target_id']} → {b['product_nuclide']}"],
            ["Haz", f"{beam['beam_energy_mev']} MeV · {beam['current_ua']} µA · "
                    f"{beam['irradiation_time_min']} min"
                    + (f" · enriquecimiento {beam['enrichment']}"
                       if beam.get("enrichment") else "")],
            ["Rendimiento saturación", f"{res['saturation_yield_mbq_ua']:.1f} MBq/µA"],
            ["Actividad EOB", f"{res['eob_activity_gbq']:.2f} ± "
                              f"{res['eob_activity_gbq_uncertainty']:.2f} GBq "
                              f"(factor sat. {res['saturation_factor']:.4f})"],
            ["Linaje de datos", f"{lin['dataset_id']} · {lin['stopping_source']}"],
            ["Estado del lote", _marca_estado(b["status"])],
            ["Liberación GMP", _marca_estado(liberacion)],
            ["Hash del registro", _p(b["record_hash"], "mono")],
        ]
        estilo_hd = ParagraphStyle("hd", fontName=SANS_BOLD, fontSize=8)
        data = [[Paragraph('<font color="white"><b>Registro de lote</b></font>',
                           estilo_hd), ""]]
        data += [[_p(k, "celda_b"), v if isinstance(v, Paragraph) else _p(v)]
                 for k, v in filas]
        t = Table(data, colWidths=[self.ANCHO * 0.28, self.ANCHO * 0.72])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), SANS),
            ("SPAN", (0, 0), (1, 0)),
            ("BACKGROUND", (0, 0), (1, 0), _AZUL),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8cfd8")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _GRIS]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return [t]

    def _seccion_qc(self, doc: EbrDocument) -> list:
        out = [Paragraph("Informes de control de calidad", _S["h"])]
        if not doc.qc_reports:
            out.append(_p("Sin informes QC registrados.", "celda"))
            return out
        filas = []
        for r in doc.qc_reports:
            fit = r.get("half_life_fit") or {}
            filas.append([
                _p(r["qc_id"], "mono"), _p(r["product"]), _p(r["nuclide"]),
                _marca_estado(r["overall_status"]),
                _p(f"{r['created_at']} · {r['created_by']}"),
                _p(f"T½ {fit['half_life_min']:.2f} min" if fit.get("half_life_min") else "—"),
            ])
        out.append(_tabla(
            ["ID informe", "Producto", "Núclido", "Resultado", "Registro", "Vida media"],
            filas,
            [self.ANCHO * f for f in (0.22, 0.12, 0.10, 0.12, 0.28, 0.16)]))
        # detalle de reglas de aceptación del último informe
        reglas = (doc.qc_reports[-1].get("rules") or [])
        if reglas:
            filas_r = [[_p(x.get("parameter", "")),
                        _p(f"{x.get('measured', '')}"),
                        _marca_estado(x.get("status", "")),
                        _p(x.get("limits", "") or x.get("detail", ""))]
                       for x in reglas]
            out.append(Spacer(1, 3 * mm))
            out.append(_p("Reglas de aceptación evaluadas (último informe):", "celda_b"))
            out.append(_tabla(["Parámetro", "Medido", "Estado", "Límite / detalle"],
                              filas_r,
                              [self.ANCHO * f for f in (0.28, 0.16, 0.12, 0.44)]))
        return out

    def _seccion_firmas(self, doc: EbrDocument) -> list:
        out = [Paragraph("Firmas electrónicas (21 CFR Part 11)", _S["h"])]
        if not doc.signatures:
            out.append(_p("Documento sin firmas.", "celda"))
            return out
        significados = {"performed_by": "Realizado por", "reviewed_by": "Revisado por",
                        "approved_by": "Aprobado por"}
        filas = [[_p(significados.get(s["meaning"], s["meaning"]), "celda_b"),
                  _p(s["signed_by"]), _p(s["signed_at"]),
                  _p(s["signature_hash"], "mono")] for s in doc.signatures]
        out.append(_tabla(["Significado", "Firmante", "Fecha y hora (UTC)",
                           "Hash de firma (SHA-256)"],
                          filas,
                          [self.ANCHO * f for f in (0.16, 0.18, 0.20, 0.46)]))
        out.append(Paragraph(
            "Cada firma se realizó con re-autenticación del firmante y quedó "
            "vinculada criptográficamente al hash del registro vigente en el "
            "momento de firmar; cualquier cambio posterior la invalida de forma "
            "detectable.", _S["pie"]))
        return out

    def _seccion_auditoria(self, doc: EbrDocument) -> list:
        out = [Paragraph("Pista de auditoría", _S["h"])]
        filas = [[_p(e.timestamp.isoformat()), _p(e.actor),
                  _p(e.action), _p(e.detail)] for e in doc.audit_trail]
        out.append(_tabla(["Fecha y hora (UTC)", "Actor", "Acción", "Detalle"],
                          filas,
                          [self.ANCHO * f for f in (0.20, 0.18, 0.24, 0.38)]))
        return out

    def _seccion_integridad(self, doc: EbrDocument) -> list:
        out = [Paragraph("Integridad del documento", _S["h"])]
        alg = doc.integrity.get("algorithm", "sha256")
        out.append(_p(f"Algoritmo: {alg.upper()}", "celda"))
        out.append(_p(doc.integrity.get("document_hash", ""), "mono"))
        out.append(Paragraph(
            "Verificación independiente disponible en "
            "GET /api/v1/batches/{batch_id}/ebr/verify (lote, informes QC y "
            "firmas). Documento generado electrónicamente; no requiere firma "
            "manuscrita para su validez (21 CFR 11.1).", _S["pie"]))
        return out

    # ---------------------------------------------------------------- página
    @staticmethod
    def _pie_pagina(canvas, doc_):
        canvas.saveState()
        canvas.setFont(SANS, 7)
        canvas.setFillColor(_GRIS2)
        canvas.drawString(_M, 9 * mm,
                          "Radiopharma OS · eBR — copia archivable generada "
                          "electrónicamente")
        canvas.drawRightString(A4[0] - _M, 9 * mm,
                               f"Página {doc_.page}")
        canvas.restoreState()
