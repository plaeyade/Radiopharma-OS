#!/usr/bin/env python3
"""
Radiopharma OS - Pipeline de control de calidad y liberación (Fase 2)

Ciclo GMP completo sobre un lote registrado:

    Data Lake (lote) -> QC Engine (evaluación) -> Data Lake (informe QC)
    -> liberación (calidad) o rechazo

Uso:
    python pipelines/qc_cli.py --batch B-20260718-XXXX --product fdg \
        --nuclide 18F --ph 6.8 --rcp 0.985 --rnp 0.9999 \
        --usuario qc.analista --password *** [--liberar --usuario-calidad qa.jefe --password-calidad ***]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import httpx

QC_URL = os.environ.get("QC_ENGINE_URL", "http://localhost:8005")
DL_URL = os.environ.get("DATA_LAKE_URL", "http://localhost:8003")
AUTH_URL = os.environ.get("AUTH_URL", "http://localhost:8004")
TIMEOUT = httpx.Timeout(30.0)


def login(username: str, password: str) -> str:
    with httpx.Client(timeout=TIMEOUT) as http:
        r = http.post(f"{AUTH_URL}/api/v1/auth/login",
                      json={"username": username, "password": password})
        r.raise_for_status()
        return r.json()["access_token"]


def run_qc(batch_id: str, product: str, nuclide: str,
           measurements: dict, token: str,
           half_life_series: list | None = None) -> dict:
    """Evalúa en el QC Engine y persiste el informe en el Data Lake."""
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=TIMEOUT) as http:
        # 1) lote existe
        r = http.get(f"{DL_URL}/api/v1/batches/{batch_id}", headers=headers)
        r.raise_for_status()
        # 2) evaluación QC
        eval_payload = {"product": product, "nuclide": nuclide,
                        "measurements": measurements}
        if half_life_series:
            eval_payload["half_life_series"] = half_life_series
        r = http.post(f"{QC_URL}/api/v1/qc/evaluate", json=eval_payload)
        r.raise_for_status()
        evaluation = r.json()
        # 3) persistir informe ligado al lote
        report_payload = {
            "product": product, "nuclide": nuclide,
            "overall_status": evaluation["overall_status"],
            "rules": evaluation["rule_evaluations"],
            "half_life_fit": evaluation.get("half_life_fit"),
        }
        r = http.post(f"{DL_URL}/api/v1/batches/{batch_id}/qc-reports",
                      json=report_payload, headers=headers)
        r.raise_for_status()
        return {"evaluation": evaluation, "qc_record": r.json()}


def release(batch_id: str, decision: str, reason: str | None, token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=TIMEOUT) as http:
        r = http.post(f"{DL_URL}/api/v1/batches/{batch_id}/release",
                      json={"decision": decision, "reason": reason},
                      headers=headers)
        r.raise_for_status()
        return r.json()


def main() -> int:
    ap = argparse.ArgumentParser(description="Pipeline QC + liberación GMP")
    ap.add_argument("--batch", required=True, help="batch_id")
    ap.add_argument("--product", required=True, help="pack de reglas (fdg, generic_pet)")
    ap.add_argument("--nuclide", required=True)
    ap.add_argument("--ph", type=float)
    ap.add_argument("--rcp", type=float, help="pureza radioquímica (fracción)")
    ap.add_argument("--rnp", type=float, help="pureza radionuclídica (fracción)")
    ap.add_argument("--kryptofix", type=float)
    ap.add_argument("--endotoxins", type=float)
    ap.add_argument("--acetonitrile", type=float)
    ap.add_argument("--half-life-json", default=None,
                    help="archivo JSON con serie [{time_min, activity}, ...]")
    ap.add_argument("--usuario", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--liberar", action="store_true")
    ap.add_argument("--rechazar", default=None, help="motivo de rechazo")
    ap.add_argument("--usuario-calidad", default=None)
    ap.add_argument("--password-calidad", default=None)
    args = ap.parse_args()

    measurements = {}
    for flag, key in [(args.ph, "ph"), (args.rcp, "radiochemical_purity"),
                      (args.rnp, "radionuclidic_purity"),
                      (args.kryptofix, "kryptofix_222"),
                      (args.endotoxins, "endotoxins_eu_ml"),
                      (args.acetonitrile, "acetonitrile_mg_dose")]:
        if flag is not None:
            measurements[key] = flag

    series = None
    if args.half_life_json:
        series = json.load(open(args.half_life_json))

    token = login(args.usuario, args.password)
    result = run_qc(args.batch, args.product, args.nuclide, measurements,
                    token, series)
    ev = result["evaluation"]
    qc = result["qc_record"]
    print(f"QC {args.batch}: {ev['overall_status'].upper()} -> informe {qc['qc_id']} "
          f"(integridad: {'OK' if qc['integrity_ok'] else 'FALLO'})")
    for rule in ev["rule_evaluations"]:
        print(f"  [{rule['status']:7s}] {rule['parameter']}: {rule['measured']} {rule['detail']}")

    if args.liberar or args.rechazar:
        if not args.usuario_calidad:
            print("ERROR: liberar/rechazar requiere --usuario-calidad", file=sys.stderr)
            return 2
        qa_token = login(args.usuario_calidad, args.password_calidad or "")
        if args.rechazar:
            out = release(args.batch, "rejected", args.rechazar, qa_token)
        else:
            out = release(args.batch, "released", "Liberado conforme a QC", qa_token)
        print(f"Decisión: {out['release_status'].upper()} por {out['released_by']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
