#!/usr/bin/env python3
"""
Radiopharma OS - Pipeline eBR: Electronic Batch Record + firmas electrónicas

Cierra el ciclo documental GMP sobre un lote:

    Data Lake (lote + QC + liberación) -> eBR consolidado
    -> firmas performed_by / reviewed_by / approved_by (21 CFR Part 11)
    -> verificación de integridad

Uso:
    # Emitir el eBR (documento consolidado, JSON)
    python pipelines/ebr_cli.py --batch B-20260718-XXXX \
        --usuario operador.ciclotron --password *** --emitir --salida ebr.json

    # Firmar (realizó / revisó / aprobó)
    python pipelines/ebr_cli.py --batch B-20260718-XXXX \
        --usuario operador.ciclotron --password *** --firmar performed_by
    python pipelines/ebr_cli.py --batch B-20260718-XXXX \
        --usuario supervisor.turno --password *** --firmar reviewed_by
    python pipelines/ebr_cli.py --batch B-20260718-XXXX \
        --usuario qa.jefe --password *** --firmar approved_by

    # Verificar integridad del lote, informes QC y firmas
    python pipelines/ebr_cli.py --batch B-20260718-XXXX \
        --usuario auditor --password *** --verificar

    # Descargar la copia archivable en PDF (archivo regulatorio)
    python pipelines/ebr_cli.py --batch B-20260718-XXXX \
        --usuario qa.jefe --password *** --pdf ebr_lote.pdf
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import httpx

DL_URL = os.environ.get("DATA_LAKE_URL", "http://localhost:8003")
AUTH_URL = os.environ.get("AUTH_URL", "http://localhost:8004")
TIMEOUT = httpx.Timeout(30.0)


def login(username: str, password: str) -> str:
    with httpx.Client(timeout=TIMEOUT) as http:
        r = http.post(f"{AUTH_URL}/api/v1/auth/login",
                      json={"username": username, "password": password})
        r.raise_for_status()
        return r.json()["access_token"]


def get_ebr(batch_id: str, token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=TIMEOUT) as http:
        r = http.get(f"{DL_URL}/api/v1/batches/{batch_id}/ebr", headers=headers)
        r.raise_for_status()
        return r.json()


def sign(batch_id: str, username: str, password: str, meaning: str,
         token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=TIMEOUT) as http:
        r = http.post(f"{DL_URL}/api/v1/batches/{batch_id}/signatures",
                      json={"username": username, "password": password,
                            "meaning": meaning}, headers=headers)
        r.raise_for_status()
        return r.json()


def verify(batch_id: str, token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=TIMEOUT) as http:
        r = http.get(f"{DL_URL}/api/v1/batches/{batch_id}/ebr/verify",
                     headers=headers)
        r.raise_for_status()
        return r.json()


def download_pdf(batch_id: str, token: str, salida: str) -> int:
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=TIMEOUT) as http:
        r = http.get(f"{DL_URL}/api/v1/batches/{batch_id}/ebr/pdf",
                     headers=headers)
        r.raise_for_status()
        with open(salida, "wb") as fh:
            fh.write(r.content)
        conformidad = r.headers.get("X-PDF-Conformance", "PDF")
        print(f"  conformidad declarada: {conformidad}")
        return len(r.content)


def print_ebr_summary(doc: dict) -> None:
    b = doc["batch"]
    print(f"eBR {doc['ebr_id']}  (generado {doc['generated_at']})")
    print(f"  Lote {b['batch_id']} · {b['reaction_id']} · {b['product_nuclide']} "
          f"· EOB {b['results']['eob_activity_gbq']:.2f} GBq")
    print(f"  Estado: {b['status']} · liberación: {b['release_status']}"
          + (f" por {b['released_by']}" if b.get("released_by") else ""))
    print(f"  Informes QC: {len(doc['qc_reports'])} · Firmas: {len(doc['signatures'])}")
    for s in doc["signatures"]:
        print(f"    [{s['meaning']:12s}] {s['signed_by']} @ {s['signed_at']}")
    print(f"  Pista de auditoría: {len(doc['audit_trail'])} eventos")
    for e in doc["audit_trail"]:
        print(f"    {e['timestamp']}  {e['actor']:20s}  {e['action']}")
    print(f"  Integridad del documento: {doc['integrity']['algorithm']} "
          f"{doc['integrity']['document_hash'][:16]}…")


def main() -> int:
    ap = argparse.ArgumentParser(description="Pipeline eBR + firmas electrónicas")
    ap.add_argument("--batch", required=True, help="batch_id")
    ap.add_argument("--usuario", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--emitir", action="store_true", help="emitir eBR consolidado")
    ap.add_argument("--salida", default=None, help="archivo JSON de salida del eBR")
    ap.add_argument("--firmar", default=None,
                    choices=["performed_by", "reviewed_by", "approved_by"],
                    help="firmar el lote con el significado indicado")
    ap.add_argument("--verificar", action="store_true",
                    help="verificar integridad de lote + QC + firmas")
    ap.add_argument("--pdf", default=None, metavar="ARCHIVO",
                    help="descargar la copia archivable del eBR (PDF/A-2b)")
    args = ap.parse_args()

    if not (args.emitir or args.firmar or args.verificar or args.pdf):
        print("ERROR: indica al menos una acción "
              "(--emitir, --firmar, --verificar, --pdf)", file=sys.stderr)
        return 2

    token = login(args.usuario, args.password)

    if args.pdf:
        n = download_pdf(args.batch, token, args.pdf)
        print(f"eBR archivable guardado en {args.pdf} ({n} bytes)")

    if args.firmar:
        sig = sign(args.batch, args.usuario, args.password, args.firmar, token)
        print(f"Firma registrada: [{sig['meaning']}] por {sig['signed_by']} "
              f"-> {sig['signature_hash'][:16]}… "
              f"(sobre registro {sig['record_hash_signed'][:12]}…)")

    if args.emitir:
        doc = get_ebr(args.batch, token)
        print_ebr_summary(doc)
        if args.salida:
            with open(args.salida, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, indent=2, ensure_ascii=False)
            print(f"eBR guardado en {args.salida}")

    if args.verificar:
        result = verify(args.batch, token)
        estado = "OK" if result["all_ok"] else "FALLO"
        print(f"Verificación de {result['batch_id']}: {estado}")
        for c in result["checks"]:
            marca = "OK " if c["ok"] else "FALLO"
            extra = ""
            if "bound_record_current" in c:
                extra = (" (registro vigente)" if c["bound_record_current"]
                         else " (OBSOLETA: el registro cambió tras la firma)")
            print(f"  [{marca}] {c['item']}{extra}")
        return 0 if result["all_ok"] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
