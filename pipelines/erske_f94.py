#!/usr/bin/env python3
"""
F94 — Cap. 45: Enterprise RAG & Scientific Knowledge Engine (ERSKE)
Radiopharma OS — EDS Volumen VIII (Enterprise Intelligence & AI Twin)

Reglas canónicas:
- 45.3: administra conocimiento documental; NO sustituye los documentos
  originales ni los sistemas institucionales. Los originales no se modifican.
- 45.8: la versión del modelo de embeddings queda registrada junto con el
  índice (reproducibilidad). Modelo declarado: hashing TF (determinista,
  stdlib) — embeddings neuronales son compatibilidad futura (45.26).
- 45.10/45.11: los fragmentos recuperados permanecen vinculados a sus
  fuentes originales; cada respuesta puede asociarse a la documentación.
- 45.21: antes de indexar se verifica integridad, formato, metadatos y
  duplicados; los inconsistentes permanecen en revisión.
- 45.23: cada consulta registra usuario, documentos recuperados, fecha,
  versión del índice y parámetros (jsonl md5, ALCOA+).
- 45.4/45.13: la recuperación permanece desacoplada del razonamiento.
"""
import hashlib, json, math, os, re, sys
from datetime import datetime, timezone

FASE = "fase94"
EV_DIR = "/mnt/agents/work/evidencia_v072/fase94"
EV_BASE = "/mnt/agents/work/evidencia_v072"
REPO = "/mnt/agents/work/rpos25"

EMBEDDING_MODEL = {"id": "hashing-tfidf-v1", "dims": 256,
                   "tipo": "hashing_trick_determinista_stdlib",
                   "declarado": "no neuronal; embeddings densos = compatibilidad futura (45.26)"}
FORMATOS = {".txt", ".md", ".json"}

STOP = set("de la el en y a los del se las por un para con no una su al es lo como más o "
           "pero sus le ya o este sí porque esta entre cuando muy sin sobre también me "
           "hasta hay donde quien desde todo nos durante todos uno les ni contra otros "
           "ese eso ante ellos e esto mí antes algunos qué unos yo otro otras otra él "
           "tanto esa estos mucho quienes nada muchos cual poco ella estar estas algunas "
           "algo nosotros the and of to in is are for with that this on".split())


def tokens(texto):
    return [t for t in re.findall(r"[a-záéíóúñü0-9_]+", texto.lower())
            if len(t) > 2 and t not in STOP]


# --- 45.6/45.12 Document Registry ---------------------------------------------------
def registrar_documento(registro, doc_id, titulo, ruta, tipo, dominio, autor, version="1.0"):
    return {"id": doc_id, "titulo": titulo, "ruta": ruta, "tipo": tipo,
            "dominio": dominio, "autor": "radiopharma_os", "version": version,
            "fecha_utc": datetime.now(timezone.utc).isoformat(),
            "origen": ruta, "idioma": "es", "estado": "registrado"}


# --- 45.21 Validation Engine ----------------------------------------------------------
def validar_documento(doc, contenido, registro):
    errores = []
    if not contenido or not contenido.strip():
        errores.append("integridad:contenido_vacio")
    ext = os.path.splitext(doc["ruta"])[1].lower()
    if ext not in FORMATOS:
        errores.append(f"formato_no_soportado:{ext}")
    if not doc.get("titulo") or not doc.get("dominio"):
        errores.append("metadatos_incompletos")
    md5 = hashlib.md5(contenido.encode()).hexdigest()
    for d in registro:
        if d.get("md5") == md5:
            errores.append(f"duplicado_de:{d['id']}")
            break
    doc["md5"] = md5
    doc["estado"] = "en_revision" if errores else "registrado"
    return errores


# --- 45.7 Document Parser (originales sin modificación) ---------------------------------
def parsear(contenido, tam_fragmento=420):
    """Fragmenta texto plano/markdown/json en chunks con solape ligero."""
    texto = re.sub(r"\s+", " ", contenido).strip()
    frags, i = [], 0
    while i < len(texto):
        frags.append(texto[i:i + tam_fragmento])
        i += tam_fragmento - 60
    return [f for f in frags if len(f) > 40]


# --- 45.8 Embedding Manager (determinista, reproducible) ---------------------------------
def embed(texto):
    v = [0.0] * EMBEDDING_MODEL["dims"]
    toks = tokens(texto)
    for t in toks:
        h = int(hashlib.md5(t.encode()).hexdigest(), 16)
        v[h % EMBEDDING_MODEL["dims"]] += 1.0
    norma = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norma for x in v]


def coseno(a, b):
    return sum(x * y for x, y in zip(a, b))


# --- 45.9 Vector Index -------------------------------------------------------------------
class Indice:
    def __init__(self):
        self.fragmentos = []  # {doc_id, frag_idx, texto, vector, dominio}
        self.modelo = EMBEDDING_MODEL["id"]
        self.version = "1.0"

    def agregar(self, doc, fragmentos):
        for i, fr in enumerate(fragmentos):
            self.fragmentos.append({"doc_id": doc["id"], "frag_idx": i, "texto": fr,
                                    "dominio": doc["dominio"], "vector": embed(fr)})

    def md5(self):
        blob = json.dumps([f["vector"] for f in self.fragmentos]).encode()
        return hashlib.md5(blob).hexdigest()


# --- 45.10 Retrieval Engine ---------------------------------------------------------------
def recuperar(indice, consulta, k=3, filtro_dominio=None):
    q = embed(consulta)
    resultados = []
    for f in indice.fragmentos:
        if filtro_ok(f, filtro_dominio):
            resultados.append((coseno(q, f["vector"]), f))
    resultados.sort(key=lambda x: -x[0])
    return [{"doc_id": f["doc_id"], "frag_idx": f["frag_idx"], "dominio": f["dominio"],
             "score": round(s, 4), "fragmento": f["texto"][:260]}
            for s, f in resultados[:k] if s > 0]


def filtro_ok(f, filtro):
    return filtro is None or f["dominio"] == filtro


# --- 45.11 Citation Manager ------------------------------------------------------------------
def citar(resultados, registro):
    docs = {d["id"]: d for d in registro}
    citas = []
    for r in resultados:
        d = docs.get(r["doc_id"], {})
        citas.append({"fragmento": r["frag_idx"], "score": r["score"],
                      "fuente": {"doc_id": r["doc_id"], "titulo": d.get("titulo"),
                                 "version": d.get("version"), "origen": d.get("origen")}})
    return citas


# --- Construcción del corpus desde evidencia real -------------------------------------------
def construir_corpus():
    docs, contenidos = [], {}
    candidatos = [
        ("evid_f82_blindajes", "Blindajes oncología Zumaya (LINAC/HDR/GK/PET/SPECT/I-131)",
         "fase82/blindajes_zumaya_f82.json", "proteccion_radiologica"),
        ("evid_f83_blindaje_ciclotron", "Blindaje ciclotrón Zumaya (NCRP-144, 18 MeV 300 µA)",
         "fase83/blindaje_ciclotron_f83.json", "proteccion_radiologica"),
        ("evid_f86_utilidades", "Planta auxiliar 5.12: utilidades y costos por lote",
         "fase86/utilidades_completas_f86.json", "proceso"),
        ("evid_f87_stae", "STAE cap.27: control estadístico SPC/Mann-Kendall/Cpk",
         "fase87/stae_f87.json", "calidad"),
        ("evid_f88_beme", "BEME cap.35: zonas, cascada de presión, sensores, alarmas",
         "fase88/beme_f88.json", "facility"),
        ("evid_f89_iil", "IIL cap.26: instrumentos HPLC/GC/TLC, normalización MBq",
         "fase89/iil_f89.json", "calidad"),
        ("evid_f90_ffsae", "FFSAE cap.40: escenarios financieros, VPN/TIR, riesgos",
         "fase90/ffsae_f90.json", "economico"),
        ("evid_f91_malme", "MALME cap.42: ciclo de vida de modelos IA",
         "fase91/malme_f91.json", "ia"),
        ("evid_f92_madse", "MADSE cap.43: agentes especializados y consenso",
         "fase92/madse_f92.json", "ia"),
        ("evid_f93_kgsie", "KGSIE cap.44: grafo de conocimiento, ontología",
         "fase93/kgsie_f93.json", "ia"),
    ]
    for doc_id, titulo, rel, dominio in candidatos:
        ruta = os.path.join(EV_BASE, rel)
        if not os.path.exists(ruta):
            continue
        with open(ruta, encoding="utf-8") as fh:
            contenido = fh.read()
        doc = registrar_documento(None, doc_id, titulo, ruta, "evidencia_json", dominio,
                                  "rpos_pipeline")
        docs.append(doc)
        contenidos[doc_id] = contenido
    for md in ("runtimes_cientificos.md",):
        ruta = os.path.join(REPO, "docs", md)
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as fh:
                contenido = fh.read()
            doc = registrar_documento(None, f"doc_{md[:-3]}", md, ruta, "markdown",
                                      "ingenieria", "rpos")
            docs.append(doc)
            contenidos[doc["id"]] = contenido
    return docs, contenidos


# --- Ejecución de fase ---------------------------------------------------------------------
def run():
    os.makedirs(EV_DIR, exist_ok=True)
    reg = os.path.join(EV_DIR, "registro_erske_f94.jsonl")

    def audit(accion, detalle):
        prev = "0" * 64
        if os.path.exists(reg):
            lines = [l for l in open(reg, encoding="utf-8").read().splitlines() if l.strip()]
            if lines:
                prev = json.loads(lines[-1])["md5"]
        e = {"fecha_utc": datetime.now(timezone.utc).isoformat(),
             "usuario": "rpos_pipeline_f94", "accion": accion, "detalle": detalle,
             "indice_version": "1.0", "prev_md5": prev}
        e["md5"] = hashlib.md5(json.dumps(e, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        with open(reg, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")

    registro = []
    indice = Indice()
    docs, contenidos = construir_corpus()
    eventos = []
    for doc in docs:
        errs = validar_documento(doc, contenidos[doc["id"]], registro)
        if errs:
            eventos.extend(errs)
            continue
        frags = parsear(contenidos[doc["id"]])
        doc["n_fragmentos"] = len(frags)
        indice.agregar(doc, frags)
        registro.append(doc)
    # documento inválido demostrado (45.21): duplicado → revisión
    dup = registrar_documento(None, "evid_f83_duplicado", "duplicado F83",
                              os.path.join(EV_BASE, "fase83/blindaje_ciclotron_f83.json"),
                              "evidencia_json", "proteccion_radiologica", "x")
    errs_dup = validar_documento(dup, contenidos.get("evid_f83_blindaje_ciclotron", ""),
                                 registro)
    eventos.extend(errs_dup)
    audit("indexar", {"docs": len(registro), "fragmentos": len(indice.fragmentos),
                      "eventos_validacion": eventos,
                      "embedding_model": EMBEDDING_MODEL["id"], "indice_md5": indice.md5()})

    consultas = [
        {"q": "¿Qué espesor de losa y muros tiene el búnker del ciclotrón según NCRP-144?",
         "esperado": "evid_f83_blindaje_ciclotron", "dominio": None},
        {"q": "costo de utilidades por lote nitrógeno líquido trampa fría",
         "esperado": "evid_f86_utilidades", "dominio": "proceso"},
        {"q": "¿es viable aumentar producción fdg 24 lotes mes votos consenso precaución agentes",
         "esperado": "evid_f92_madse", "dominio": "ia"},
    ]
    resultados = []
    for c in consultas:
        r = recuperar(indice, c["q"], k=3, filtro_dominio=c["dominio"])
        citas = citar(r, registro)
        top_ok = bool(r) and r[0]["doc_id"] == c["esperado"]
        resultados.append({"consulta": c["q"], "esperado": c["esperado"],
                           "top1_correcto": top_ok, "resultados": r, "citas": citas})
        audit("consultar", {"consulta": c["q"], "docs_recuperados": [x["doc_id"] for x in r],
                            "parametros": {"k": 3, "filtro_dominio": c["dominio"]}})

    # 45.8 Knowledge Export Service
    with open(os.path.join(EV_DIR, "indice_f94.json"), "w", encoding="utf-8") as fh:
        json.dump({"version": indice.version, "modelo": EMBEDDING_MODEL,
                   "n_fragmentos": len(indice.fragmentos), "md5": indice.md5(),
                   "docs": [{"id": d["id"], "titulo": d["titulo"],
                             "n_fragmentos": d.get("n_fragmentos")} for d in registro]},
                  fh, ensure_ascii=False, indent=2)

    out = {
        "fase": FASE, "capitulo_canonico": 45,
        "componentes_45_5": ["Document Registry", "Document Parser", "Embedding Manager",
                             "Vector Index", "Retrieval Engine", "Citation Manager",
                             "Validation Engine", "Knowledge Export Service"],
        "embedding_model_declarado": EMBEDDING_MODEL,
        "documentos_indexados": len(registro),
        "fragmentos": len(indice.fragmentos),
        "indice_md5": indice.md5(),
        "eventos_validacion_45_21": eventos,
        "consultas_demostradas": [
            {"consulta": r["consulta"], "top1_correcto": r["top1_correcto"],
             "top1": r["resultados"][0] if r["resultados"] else None,
             "cita_top1": r["citas"][0] if r["citas"] else None}
            for r in resultados],
        "pendientes_declarados": [
            "Base vectorial/MinIO/PostgreSQL (45.22) pendientes de despliegue.",
            "Embeddings neuronales, Hybrid/Graph RAG: compatibilidad futura (45.26).",
            "Generación con LLM desacoplada (45.4): esta fase cubre recuperación y citación.",
            "PDF/Word/OCR (45.7): parser de texto/md/json implementado; PDF binario pendiente.",
        ],
    }
    with open(os.path.join(EV_DIR, "erske_f94.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print(json.dumps({"docs": len(registro), "fragmentos": len(indice.fragmentos),
                      "top1": [r["top1_correcto"] for r in resultados],
                      "eventos": eventos}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
