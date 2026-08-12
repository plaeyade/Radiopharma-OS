"""Conectores GenAI — embeddings neuronales (45.8/45.9) y LLM (45.20)
para el Enterprise RAG & Scientific Knowledge Engine.

El motor RAG del MVP indexa léxicamente (TF-IDF, honesto en 45.9). Este
módulo añade la capa semántica y generativa REAL:

- **Embedding Manager (45.8)**: embeddings neuronales vía HTTP real
  (API compatible OpenAI: ``POST {endpoint}/v1/embeddings``). Cada
  índice semántico registra proveedor y versión del modelo para
  reproducibilidad (45.8).
- **Vector Index semántico (45.9)**: similitud coseno real sobre los
  vectores reales devueltos por el proveedor.
- **Retrieval semántico (45.10)**: los documentos recuperados permanecen
  vinculados a sus fuentes originales.
- **LLM (45.20)**: generación vía ``POST {endpoint}/v1/chat/completions``
  con el contexto recuperado REALMENTE inyectado; la respuesta registra
  los documentos utilizados (45.11/45.23). La recuperación permanece
  separada del razonamiento (45.4/45.13).
- Sin proveedor configurado o sin sonda exitosa → ``no_configurado`` /
  ``fallo_conexion`` y 503: ni el embedding ni la respuesta se inventan.

Proveedores versionados (nunca se sobrescriben); endpoint http(s)
obligatorio; auditoría ALCOA+ en todas las operaciones.
El cliente HTTP es inyectable (pruebas); en producción se usa httpx.
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

GENAI_VERSION = "genai-connector-1.0.0"

TIPOS_PROVEEDOR = ("embeddings", "llm")


class GenAiInvalido(ValueError):
    """Proveedor, índice o solicitud inválida."""


class SinProveedor(RuntimeError):
    """Sin proveedor GenAI configurado/conectado → 503 honesto."""


@dataclass
class Proveedor:
    proveedor_id: str
    tipo: str
    endpoint: str
    modelo: str
    version: int
    responsable: str
    registrado_en: str


class GenAiConnector:
    """Conectores de embeddings y LLM para el ERSKE (cap. 45)."""

    def __init__(self, rag_engine=None, fabrica_http=None,
                 timeout_s: float = 30.0) -> None:
        # rag_engine: RagEngine inyectado (documentos y registro de citas)
        self._rag = rag_engine
        self._fabrica_http = fabrica_http
        self._timeout_s = timeout_s
        self._proveedores: dict[str, list[Proveedor]] = {}
        self._vivos: dict[str, Proveedor] = {}
        self._ultimo_estado: dict[str, dict] = {}
        self._indices: list[dict] = []      # versiones del índice semántico
        self._vectores: dict[str, list[float]] = {}  # documento_id → vector
        self._auditoria: list[dict] = []

    # ------------------------------------------------------------ núcleo
    def _ahora(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _auditar(self, accion: str, detalle: dict, actor: str,
                 resultado: str = "ok") -> None:
        self._auditoria.append({
            "evento_id": str(uuid.uuid4()),
            "accion": accion,
            "detalle": detalle,
            "actor": actor,
            "resultado": resultado,
            "timestamp": self._ahora(),
            "version_motor": GENAI_VERSION,
        })

    def auditoria(self) -> list[dict]:
        return list(self._auditoria)

    def _http(self):
        if self._fabrica_http is not None:
            return self._fabrica_http()
        import httpx
        return httpx.Client(timeout=self._timeout_s)

    # ---------------------------------------------- proveedores (versionados)
    def registrar_proveedor(self, proveedor_id: str, tipo: str,
                            endpoint: str, modelo: str,
                            responsable: str) -> Proveedor:
        """Alta o nueva versión de la configuración; nunca se sobrescribe."""
        if tipo not in TIPOS_PROVEEDOR:
            raise GenAiInvalido(
                f"tipo inválido {tipo}; tipos: {list(TIPOS_PROVEEDOR)}")
        if not all([proveedor_id, endpoint, modelo, responsable]):
            raise GenAiInvalido(
                "proveedor_id, endpoint, modelo y responsable "
                "obligatorios; sin endpoint el modelo sería una simulación")
        if not endpoint.startswith(("http://", "https://")):
            raise GenAiInvalido("endpoint debe ser URL http(s)")
        versiones = self._proveedores.setdefault(proveedor_id, [])
        p = Proveedor(proveedor_id, tipo, endpoint.rstrip("/"), modelo,
                      len(versiones) + 1, responsable, self._ahora())
        versiones.append(p)
        self._vivos.pop(proveedor_id, None)
        self._auditar("proveedor_registrado",
                      {"proveedor_id": proveedor_id, "tipo": tipo,
                       "modelo": modelo, "version": p.version},
                      responsable)
        return p

    def proveedores(self) -> list[dict]:
        return [{"proveedor_id": v[-1].proveedor_id, "tipo": v[-1].tipo,
                 "modelo": v[-1].modelo, "endpoint": v[-1].endpoint,
                 "version": v[-1].version,
                 "estado": self._ultimo_estado.get(
                     v[-1].proveedor_id, {}).get("estado", "no_sondeado")}
                for v in self._proveedores.values()]

    def historial_proveedor(self, proveedor_id: str) -> list[dict]:
        return [{"version": p.version, "endpoint": p.endpoint,
                 "modelo": p.modelo, "responsable": p.responsable,
                 "registrado_en": p.registrado_en}
                for p in self._proveedores.get(proveedor_id, [])]

    def _vigente(self, proveedor_id: str) -> Proveedor:
        versiones = self._proveedores.get(proveedor_id)
        if not versiones:
            raise GenAiInvalido(f"proveedor desconocido: {proveedor_id}")
        return versiones[-1]

    def _post(self, proveedor: Proveedor, ruta: str, cuerpo: dict) -> dict:
        with self._http() as http:
            resp = http.post(proveedor.endpoint + ruta, json=cuerpo,
                             headers={"Content-Type": "application/json"})
        if resp.status_code >= 400:
            raise ConnectionError(f"HTTP {resp.status_code}")
        return resp.json()

    def sondear(self, proveedor_id: str, actor: str = "sistema") -> dict:
        """Sonda REAL con una petición mínima al modelo declarado."""
        p = self._vigente(proveedor_id)
        try:
            if p.tipo == "embeddings":
                salida = self._post(p, "/v1/embeddings",
                                    {"model": p.modelo, "input": "sonda"})
                if not salida.get("data"):
                    raise ConnectionError("respuesta sin data")
                detalle_ok = (f"modelo {p.modelo} operativo, dimensión "
                              f"{len(salida['data'][0]['embedding'])}")
            else:
                salida = self._post(p, "/v1/chat/completions", {
                    "model": p.modelo,
                    "messages": [{"role": "user", "content": "sonda"}],
                    "max_tokens": 1})
                if not salida.get("choices"):
                    raise ConnectionError("respuesta sin choices")
                detalle_ok = f"modelo {p.modelo} operativo"
            self._vivos[proveedor_id] = p
            estado = {"estado": "conectado", "detalle": detalle_ok,
                      "sondeado_en": self._ahora()}
            resultado = "ok"
        except Exception as exc:
            self._vivos.pop(proveedor_id, None)
            estado = {"estado": "fallo_conexion",
                      "detalle": f"{type(exc).__name__}: {exc}",
                      "sondeado_en": self._ahora()}
            resultado = "fallo"
        self._ultimo_estado[proveedor_id] = estado
        self._auditar("proveedor_sondeado",
                      {"proveedor_id": proveedor_id, "tipo": p.tipo,
                       "estado": estado["estado"],
                       "detalle": estado["detalle"]}, actor, resultado)
        return {"proveedor_id": proveedor_id, **estado}

    def _vivo(self, proveedor_id: str, tipo: str, actor: str) -> Proveedor:
        p = self._vigente(proveedor_id)
        if p.tipo != tipo:
            raise GenAiInvalido(
                f"el proveedor {proveedor_id} es {p.tipo}, no {tipo}")
        if proveedor_id not in self._vivos:
            self._auditar("operacion_rechazada",
                          {"proveedor_id": proveedor_id,
                           "motivo": "sin conexión viva"}, actor, "fallo")
            raise SinProveedor(
                f"proveedor {proveedor_id} sin conexión viva; sondee "
                "primero — ni el embedding ni la respuesta se inventan")
        return p

    # --------------------------------------- embeddings (45.8/45.9)
    def generar_embedding(self, proveedor_id: str, texto: str,
                          actor: str = "sistema") -> dict:
        """Embedding neuronal REAL (45.8)."""
        p = self._vivo(proveedor_id, "embeddings", actor)
        if not texto:
            raise GenAiInvalido("texto obligatorio")
        try:
            salida = self._post(p, "/v1/embeddings",
                                {"model": p.modelo, "input": texto})
            vector = [float(x) for x in salida["data"][0]["embedding"]]
        except SinProveedor:
            raise
        except Exception as exc:
            self._vivos.pop(proveedor_id, None)
            raise SinProveedor(
                f"fallo del proveedor de embeddings: "
                f"{type(exc).__name__}: {exc}") from exc
        self._auditar("embedding_generado",
                      {"proveedor_id": proveedor_id, "modelo": p.modelo,
                       "dimension": len(vector)}, actor)
        return {"proveedor_id": proveedor_id, "modelo": p.modelo,
                "vector": vector, "dimension": len(vector),
                "generado_en": self._ahora()}

    @staticmethod
    def _coseno_vec(a: list[float], b: list[float]) -> float:
        num = sum(x * y for x, y in zip(a, b))
        da = math.sqrt(sum(x * x for x in a))
        db = math.sqrt(sum(y * y for y in b))
        return num / (da * db) if da and db else 0.0

    def construir_indice_semantico(self, proveedor_id: str,
                                   actor: str) -> dict:
        """Indexa TODOS los documentos del RAG con embeddings reales
        (45.8/45.9). Cada índice registra proveedor y modelo — el índice
        anterior nunca se borra (reproducibilidad 45.8)."""
        p = self._vivo(proveedor_id, "embeddings", actor)
        if self._rag is None:
            raise SinProveedor(
                "RagEngine no inyectado: no hay documentos que indexar")
        documentos = self._rag.documentos()
        if not documentos:
            raise GenAiInvalido(
                "sin documentos en el registro RAG (45.6); el índice "
                "semántico no se construye sobre nada")
        vectores: dict[str, list[float]] = {}
        for d in documentos:
            if d.get("estado") == "obsoleto":
                continue
            texto = (self._rag.contenido_documento(d["documento_id"])
                     .get("contenido_texto") or d.get("titulo") or "")
            if not texto:
                continue
            emb = self.generar_embedding(proveedor_id, texto, actor)
            vectores[d["documento_id"]] = emb["vector"]
        if not vectores:
            raise GenAiInvalido(
                "ningún documento con contenido indexable")
        self._vectores = vectores
        indice = {"indice_id": str(uuid.uuid4()),
                  "version": len(self._indices) + 1,
                  "proveedor_id": proveedor_id, "modelo": p.modelo,
                  "documentos": len(vectores),
                  "dimension": len(next(iter(vectores.values()))),
                  "construido_en": self._ahora(), "actor": actor}
        self._indices.append(indice)
        self._auditar("indice_semantico_construido",
                      {"indice_id": indice["indice_id"],
                       "documentos": indice["documentos"],
                       "modelo": p.modelo}, actor)
        return indice

    def buscar_semantico(self, proveedor_id: str, consulta: str,
                         k: int = 5, actor: str = "sistema") -> dict:
        """Retrieval semántico REAL (45.10): coseno sobre vectores
        reales; resultados vinculados a sus fuentes (45.10/45.11)."""
        if not self._indices:
            raise GenAiInvalido(
                "sin índice semántico; constrúyalo primero (45.9)")
        p = self._vivo(proveedor_id, "embeddings", actor)
        emb = self.generar_embedding(proveedor_id, consulta, actor)
        q = emb["vector"]
        if self._rag is None:
            raise SinProveedor("RagEngine no inyectado")
        docs = {d["documento_id"]: d for d in self._rag.documentos()}
        puntajes = sorted(
            ((self._coseno_vec(q, v), doc_id)
             for doc_id, v in self._vectores.items() if doc_id in docs),
            reverse=True)[:k]
        resultados = [{"documento_id": doc_id,
                       "similitud_semantica": round(s, 6),
                       "titulo": docs[doc_id].get("titulo"),
                       "fuente_original": docs[doc_id].get("origen")
                                          or doc_id}
                      for s, doc_id in puntajes]
        self._auditar("busqueda_semantica",
                      {"consulta": consulta[:120], "k": k,
                       "resultados": len(resultados),
                       "indice_version": self._indices[-1]["version"]},
                      actor)
        return {"consulta": consulta,
                "indice_version": self._indices[-1]["version"],
                "modelo": p.modelo,
                "resultados": resultados,
                "nota": ("similitud SEMÁNTICA real (45.9) sobre "
                         "embeddings neuronales; complementa el índice "
                         "léxico TF-IDF del MVP")}

    # --------------------------------------------------- LLM (45.20)
    def generar_respuesta_rag(self, proveedor_llm: str, consulta: str,
                              documentos: list[str], usuario: str) -> dict:
        """Generación RAG (45.20): el contexto son documentos REALES del
        registro (45.6), recuperados antes del razonamiento (45.4/45.13);
        la respuesta registra los documentos utilizados (45.11/45.23)."""
        p = self._vivo(proveedor_llm, "llm", usuario)
        if self._rag is None:
            raise SinProveedor("RagEngine no inyectado")
        if not consulta or not usuario:
            raise GenAiInvalido(
                "consulta y usuario obligatorios (45.23)")
        contexto = []
        for doc_id in documentos:
            try:
                d = self._rag.contenido_documento(doc_id)
            except ValueError:
                raise GenAiInvalido(
                    f"documento no registrado: {doc_id}; el contexto RAG "
                    "nunca se inventa (45.11)") from None
            contexto.append(d)
        mensajes = [
            {"role": "system",
             "content": ("Responde SOLO con base en el contexto documental"
                         " proporcionado. Si el contexto no es suficiente"
                         ", dilo explícitamente.")},
            {"role": "user",
             "content": (f"Contexto:\n" + "\n---\n".join(
                 f"[{d['documento_id']}] {d.get('titulo', '')}\n"
                 f"{d.get('contenido_texto', '')}" for d in contexto)
                 + f"\n\nPregunta: {consulta}")}]
        try:
            salida = self._post(p, "/v1/chat/completions", {
                "model": p.modelo, "messages": mensajes})
            respuesta = salida["choices"][0]["message"]["content"]
        except SinProveedor:
            raise
        except Exception as exc:
            self._vivos.pop(proveedor_llm, None)
            raise SinProveedor(
                f"fallo del proveedor LLM: {type(exc).__name__}: {exc}"
                ) from exc
        respuesta_id = str(uuid.uuid4())
        # 45.11: la respuesta queda asociada a la documentación utilizada
        cita = self._rag.registrar_cita(respuesta_id, documentos, usuario)
        self._auditar("respuesta_rag_generada",
                      {"respuesta_id": respuesta_id,
                       "proveedor_id": proveedor_llm, "modelo": p.modelo,
                       "documentos": documentos}, usuario)
        return {"respuesta_id": respuesta_id, "consulta": consulta,
                "respuesta": respuesta, "modelo": p.modelo,
                "documentos_utilizados": documentos,
                "cita": cita,
                "generada_en": self._ahora(),
                "nota": ("generación asistida por recuperación real "
                         "(45.20); la recuperación permanece separada "
                         "del razonamiento (45.4)")}

    # -------------------------------------------------- estado honesto
    def estado(self) -> dict:
        return {"version_motor": GENAI_VERSION,
                "proveedores": self.proveedores(),
                "indices_semanticos": self._indices,
                "rag_engine": ("inyectado" if self._rag is not None
                               else "no_inyectado"),
                "nota": ("embeddings y generación REALES vía HTTP; sin "
                         "proveedor conectado las operaciones devuelven "
                         "503 — ni el embedding ni la respuesta se "
                         "inventan (45.8/45.20)")}
