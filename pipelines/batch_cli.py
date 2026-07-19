#!/usr/bin/env python3
"""
Radiopharma OS - Pipeline de lote (Fase 1)

Encadena el flujo completo de un lote de irradiación y lo persiste:

    Yield Engine (cálculo EOB) -> Nuclear Data Service (linaje de datasets)
    -> Data Lake Service (registro inmutable ALCOA+)

Uso:
    python pipelines/batch_cli.py \
        --reaction o18_p_n_f18 --target h2_18o \
        --energy 16.5 --current 37.0 --time 60 --operador operador.ciclotron

Variables de entorno:
    YIELD_ENGINE_URL     (default http://localhost:8002)
    NUCLEAR_DATA_URL     (default http://localhost:8001)
    DATA_LAKE_URL        (default http://localhost:8003; si vacío, no persiste)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import httpx

YE_URL = os.environ.get("YIELD_ENGINE_URL", "http://localhost:8002")
NDS_URL = os.environ.get("NUCLEAR_DATA_URL", "http://localhost:8001")
DL_URL = os.environ.get("DATA_LAKE_URL", "http://localhost:8003")
AUTH_URL = os.environ.get("AUTH_URL", "http://localhost:8004")
TIMEOUT = httpx.Timeout(30.0)


def login(username: str, password: str) -> str:
    """Obtiene un JWT de plataforma del Auth Service."""
    with httpx.Client(timeout=TIMEOUT) as http:
        r = http.post(f"{AUTH_URL}/api/v1/auth/login",
                      json={"username": username, "password": password})
        r.raise_for_status()
        return r.json()["access_token"]


def decay_table(eob_gbq: float, half_life_min: float,
                points_min: tuple[int, ...] = (30, 60, 120, 240)) -> list[dict]:
    """Decaimiento post-EOB para logística de distribución."""
    lam = math.log(2) / half_life_min
    return [{"minutes_after_eob": t,
             "activity_gbq": round(eob_gbq * math.exp(-lam * t), 3)} for t in points_min]


def run_batch(reaction: str, target: str, energy: float, current: float,
              time_min: float, operador: str, persist: bool = True,
              token: str | None = None) -> dict:
    with httpx.Client(timeout=TIMEOUT) as http:
        # 1) cálculo de producción
        prod = http.post(f"{YE_URL}/api/v1/production", json={
            "reaction_id": reaction, "target_id": target,
            "beam_energy_mev": energy, "current_ua": current,
            "irradiation_time_min": time_min}).json()

        # 2) linaje: hash del dataset usado
        datasets = http.get(f"{NDS_URL}/api/v1/datasets").json()
        sha = next((d.get("sha256") for d in datasets
                    if d["id"] == prod["dataset_id"]), None)
        nuclide = prod["product_nuclide"]
        half_life_s = http.get(f"{NDS_URL}/api/v1/nuclides/{nuclide}/decay").json()["half_life_s"]

    report = {
        "reaction_id": reaction, "target_id": target,
        "product_nuclide": nuclide,
        "production": prod,
        "lineage_sha256": sha,
        "decay_post_eob": decay_table(prod["eob_activity_gbq"], half_life_s / 60.0),
    }

    # 3) persistencia ALCOA+ (created_by lo fija el token, no el payload)
    if persist and DL_URL:
        payload = {
            "reaction_id": reaction, "target_id": target,
            "product_nuclide": nuclide,
            "beam": {"beam_energy_mev": energy, "current_ua": current,
                     "irradiation_time_min": time_min},
            "results": {
                "saturation_yield_mbq_ua": prod["saturation_yield_mbq_ua"],
                "eob_activity_gbq": prod["eob_activity_gbq"],
                "eob_activity_gbq_uncertainty": prod["eob_activity_gbq_uncertainty"],
                "saturation_factor": prod["saturation_factor"],
                "relative_uncertainty": prod["relative_uncertainty"]},
            "lineage": {"dataset_id": prod["dataset_id"],
                        "dataset_sha256": sha,
                        "stopping_source": prod["stopping_source"]},
        }
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        with httpx.Client(timeout=TIMEOUT) as http:
            r = http.post(f"{DL_URL}/api/v1/batches", json=payload,
                          headers=headers)
            r.raise_for_status()
            report["batch_record"] = r.json()
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Pipeline de lote Radiopharma OS")
    ap.add_argument("--reaction", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--energy", type=float, required=True, help="MeV")
    ap.add_argument("--current", type=float, required=True, help="µA")
    ap.add_argument("--time", type=float, required=True, help="min de irradiación")
    ap.add_argument("--operador", default="cli.batch",
                    help="solo informativo; la atribución real la fija el JWT")
    ap.add_argument("--usuario", default=None, help="usuario de plataforma (login)")
    ap.add_argument("--password", default=None)
    ap.add_argument("--token", default=None, help="JWT ya emitido (alternativa a login)")
    ap.add_argument("--no-persist", action="store_true")
    args = ap.parse_args()

    token = args.token
    if token is None and args.usuario and not args.no_persist:
        token = login(args.usuario, args.password or "")
    report = run_batch(args.reaction, args.target, args.energy, args.current,
                       args.time, args.operador, persist=not args.no_persist,
                       token=token)
    prod = report["production"]
    print(f"[{report['product_nuclide']}] EOB = {prod['eob_activity_gbq']:.2f} "
          f"± {prod['eob_activity_gbq_uncertainty']:.2f} GBq "
          f"(sat {prod['saturation_yield_gbq_ua']:.2f} GBq/µA)")
    if "batch_record" in report:
        br = report["batch_record"]
        print(f"Lote registrado: {br['batch_id']} | hash {br['record_hash'][:16]}... "
              f"| integridad: {'OK' if br['integrity_ok'] else 'FALLO'}")
    print(json.dumps({"decaimiento_post_eob": report["decay_post_eob"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
