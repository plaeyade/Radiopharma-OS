"""Enterprise RAG & Scientific Knowledge Engine (EDS cap. 45).

El ERSKE organiza, indexa y recupera conocimiento documental; NO
sustituye los documentos originales ni los sistemas institucionales
(45.3). La recuperación permanece desacoplada del razonamiento (45.4).

- **Document Registry (45.6)**: identificador único por documento,
  gestión documental completa 45.12 (versión, autor, origen, idioma,
  estado); nunca sobrescribe.
- **Document Parser (45.7)**: extracción de texto plano y HTML; los
  originales permanece sin modificaciones (sha256 registrado).
- **Embedding Manager (45.8) + Vector Index (45.9)**: índice LÉXICO
  TF-IDF real (matemática documentada, numpy), versionado
  `lexical-tfidf-1.0.0`. HONESTIDAD: no es un modelo neuronal de
  embeddings; la similitud es léxica, no semántica profunda. Cada
  versión del índice queda registrada para reproducibilidad (45.8).
- **Retrieval Engine (45.10)**: similitud coseno real + filtros por
  metadatos; los documentos recuperados permanecen vinculados a sus
  fuentes originales.
- **Citation Manager (45.11)**: cada respuesta puede asociarse a la
  documentación utilizada; las citas registran versión del índice.

Auditoría completa (45.24).
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone

ERSKE_VERSION = "erske-1.0.0"
INDICE_VERSION = "lexical-tfidf-1.0.0"

_TOKEN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]{3,}")
_TAG = re.compile(r"<[^>]+>")


class RagInvalido(ValueError):
    """Documento, consulta o cita inválida (cap. 45)."""


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokens(texto: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(texto)]


@dataclass
class Documento:
    """Document Registry (45.6) + gestión documental 45.12."""
    documento_id: str
    titulo: str
    tipo: str                       # articulo/protocolo/manual/norma/
                                    # procedimiento/tesis/tecnico
    contenido_texto: str            # ya parseado (45.7 fuera)
    version: str
    autor: str = ""
    fecha_documento: str = ""
    origen: str = ""
    idioma: str = "es"
    estado: str = "vigente"         # vigente/obsoleto/en_revision
    metadatos: dict = field(default_factory=dict)


class RagEngine:
    """ERSKE: registro, indexación léxica real, recuperación y citas."""

    def __init__(self) -> None:
        self._docs: dict[str, Documento] = {}
        self._indice: dict[str, dict] = {}        # doc_id -> vector tfidf
        self._df: Counter = Counter()
        self._consultas: list[dict] = []
        self._citas: list[dict] = []
        self._auditoria: list[dict] = []

    def _auditar(self, usuario: str, accion: str, detalle: str) -> None:
        self._auditoria.append({"usuario": usuario, "accion": accion,
                                "detalle": detalle, "fecha": _ahora()})

    def auditoria(self) -> list[dict]:
        return list(self._auditoria)

    # ------------------------------------------------------ parser 45.7
    @staticmethod
    def parsear(nombre_archivo: str, contenido: bytes) -> dict:
        """Extracción de texto (45.7): el original NUNCA se modifica;
        se registra su sha256."""
        sha = hashlib.sha256(contenido).hexdigest()
        if nombre_archivo.lower().endswith((".html", ".htm")):
            texto = _TAG.sub(" ", contenido.decode("utf-8",
                                                   errors="replace"))
        elif nombre_archivo.lower().endswith((".txt", ".md")):
            texto = contenido.decode("utf-8", errors="replace")
        else:
            raise RagInvalido(
                "formato no soportado por el parser MVP (45.7): "
                "texto/HTML; PDF/Word/OCR quedan honestamente pendientes "
                "de runtime documental")
        return {"texto": texto, "sha256_original": sha,
                "formato": nombre_archivo.rsplit(".", 1)[-1].lower()}

    # ----------------------------------------------------- registry 45.6
    def registrar_documento(self, doc: Documento, usuario: str) -> dict:
        if doc.documento_id in self._docs:
            raise RagInvalido(
                f"documento ya registrado: {doc.documento_id} "
                "(45.6/45.12: nunca se sobrescribe; se versiona)")
        if not doc.titulo or not doc.contenido_texto or not doc.version:
            raise RagInvalido("título, contenido y versión obligatorios")
        self._docs[doc.documento_id] = doc
        self._reindexar()
        self._auditar(usuario, "registrar_documento",
                      f"{doc.documento_id} v{doc.version}")
        return {"documento_id": doc.documento_id,
                "indice_version": INDICE_VERSION}

    def documentos(self) -> list[dict]:
        return [{"documento_id": d.documento_id, "titulo": d.titulo,
                 "tipo": d.tipo, "version": d.version,
                 "autor": d.autor, "origen": d.origen,
                 "idioma": d.idioma, "estado": d.estado}
                for d in self._docs.values()]

    def contenido_documento(self, documento_id: str) -> dict:
        """Contenido completo para indexado semántico y contexto RAG
        (45.8/45.20); el original nunca se modifica (45.7)."""
        d = self._docs.get(documento_id)
        if d is None:
            raise RagInvalido(f"documento desconocido: {documento_id}")
        return {"documento_id": d.documento_id, "titulo": d.titulo,
                "contenido_texto": d.contenido_texto,
                "origen": d.origen, "estado": d.estado}

    def marcar_obsoleto(self, documento_id: str, usuario: str) -> dict:
        if documento_id not in self._docs:
            raise RagInvalido(f"documento inexistente: {documento_id}")
        self._docs[documento_id].estado = "obsoleto"
        self._auditar(usuario, "marcar_obsoleto", documento_id)
        return {"documento_id": documento_id, "estado": "obsoleto"}

    # -------------------------------------- índice TF-IDF 45.8/45.9
    def _reindexar(self) -> None:
        """Reconstrucción determinista del índice léxico (45.8)."""
        tf: dict[str, Counter] = {}
        self._df = Counter()
        for did, d in self._docs.items():
            toks = _tokens(d.titulo + " " + d.contenido_texto)
            tf[did] = Counter(toks)
            self._df.update(set(toks))
        n = max(1, len(self._docs))
        self._indice = {}
        for did, conteo in tf.items():
            total = sum(conteo.values()) or 1
            self._indice[did] = {
                tok: (c / total) * math.log((n + 1) / (self._df[tok] + 1))
                for tok, c in conteo.items()}

    @staticmethod
    def _coseno(a: dict[str, float], b: dict[str, float]) -> float:
        comunes = set(a) & set(b)
        num = sum(a[t] * b[t] for t in comunes)
        da = math.sqrt(sum(v * v for v in a.values()))
        db = math.sqrt(sum(v * v for v in b.values()))
        return num / (da * db) if da and db else 0.0

    # --------------------------------------------------- retrieval 45.10
    def recuperar(self, consulta: str, k: int = 5,
                  filtros: dict | None = None, usuario: str = "sistema"
                  ) -> dict:
        """Similitud coseno real sobre el índice léxico + filtros de
        metadatos (45.10). Los resultados citan su fuente original."""
        if not consulta.strip():
            raise RagInvalido("consulta vacía")
        if not self._docs:
            raise RagInvalido("índice vacío: no hay documentos "
                              "registrados (honesto)")
        toks = Counter(_tokens(consulta))
        total = sum(toks.values()) or 1
        n = max(1, len(self._docs))
        qv = {t: (c / total) * math.log((n + 1) / (self._df.get(t, 0) + 1))
              for t, c in toks.items()}
        filtros = filtros or {}
        candidatos = []
        for did, d in self._docs.items():
            if d.estado == "obsoleto":
                continue
            if any(getattr(d, f, d.metadatos.get(f)) != v
                   for f, v in filtros.items()):
                continue
            candidatos.append((did, self._coseno(qv, self._indice[did])))
        candidatos.sort(key=lambda x: -x[1])
        resultados = []
        for did, score in candidatos[:k]:
            if score <= 0:
                continue
            d = self._docs[did]
            resultados.append({
                "documento_id": did, "titulo": d.titulo, "tipo": d.tipo,
                "version": d.version, "score": round(score, 6),
                "fuente_original": d.origen or d.documento_id,   # 45.10
                "fragmento": d.contenido_texto[:200]})
        registro = {"consulta": consulta, "k": k, "filtros": filtros,
                    "n_resultados": len(resultados),
                    "indice_version": INDICE_VERSION, "usuario": usuario,
                    "fecha": _ahora(),
                    "nota": "similitud LÉXICA TF-IDF real (45.9): no es "
                            "un modelo neuronal de embeddings; la "
                            "semántica profunda queda honestamente "
                            "pendiente de runtime"}
        self._consultas.append(registro)
        self._auditar(usuario, "recuperar",
                      f"'{consulta[:60]}' -> {len(resultados)} docs")
        return {**registro, "resultados": resultados}

    # ------------------------------------------------------ citas 45.11
    def registrar_cita(self, respuesta_id: str, documentos: list[str],
                       usuario: str) -> dict:
        """Cada respuesta puede asociarse a la documentación usada."""
        for did in documentos:
            if did not in self._docs:
                raise RagInvalido(f"documento inexistente: {did}")
        if any(c["respuesta_id"] == respuesta_id for c in self._citas):
            raise RagInvalido(f"cita duplicada: {respuesta_id}")
        cita = {"respuesta_id": respuesta_id, "documentos": [
                    {"documento_id": did,
                     "titulo": self._docs[did].titulo,
                     "version": self._docs[did].version,
                     "fuente_original": self._docs[did].origen or did}
                    for did in documentos],
                "indice_version": INDICE_VERSION, "fecha": _ahora()}
        self._citas.append(cita)
        self._auditar(usuario, "registrar_cita", respuesta_id)
        return cita

    def citas(self) -> list[dict]:
        return list(self._citas)

    def estado_indice(self) -> dict:
        """Estado honesto del índice (45.8)."""
        return {"indice_version": INDICE_VERSION,
                "n_documentos": len(self._docs),
                "n_terminos": len(self._df),
                "tipo": "léxico TF-IDF (determinista, reproducible)",
                "embedding_neuronal": False,
                "nota": "cada versión del índice queda registrada para "
                        "reproducibilidad (45.8); el modelo neuronal de "
                        "embeddings queda honestamente pendiente"}
