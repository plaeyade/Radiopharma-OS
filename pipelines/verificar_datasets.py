#!/usr/bin/env python3
"""Verificación de datasets de secciones eficaces contra su fuente oficial.

Principio ALCOA+ (verificabilidad): cada dataset versionado declara su
fuente (`# url:` en la cabecera del CSV); este pipeline la re-descarga
y compara punto a punto con tolerancia declarada. El resultado es un
informe honesto: `verificado`, `discrepancia` o `no_verificable`
(fuente inaccesible — nunca se asume la verificación).

Uso:
    python -m pipelines.verificar_datasets \
        --data services/yield_engine/data \
        --reaccion zn68_p_n_ga68 \
        --fuente-local /tmp/zn68_4.html   # sin red (tests / offline)
        --out out/verificacion_datasets.json
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

TOLERANCIA_ABS = 0.05      # mb / MeV — redondeo de la fuente publicada


def leer_csv_versionado(ruta: Path) -> tuple[list[tuple], dict]:
    filas, cabecera = [], {}
    with open(ruta, newline="") as fh:
        for row in csv.reader(fh):
            if not row:
                continue
            if row[0].startswith("#"):
                m = re.match(r"#\s*(\w+):\s*(.*)", row[0])
                if m:
                    cabecera[m.group(1)] = m.group(2).strip()
                continue
            if row[0] == "energy_MeV":
                continue
            filas.append((float(row[0]), float(row[1]),
                          float(row[2]) if len(row) > 2 and row[2] else None))
    return filas, cabecera


def parsear_tabla_iaea_html(html: str) -> dict[float, tuple[float, float]]:
    """Tabla oficial IAEA-NDS Medical: grupos de columnas (E, σ ± Δσ)."""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I)
    puntos: dict[float, tuple[float, float]] = {}
    for r in rows:
        celdas = [re.sub(r"<[^>]+>", "", c).replace("\xa0", " ").strip()
                  for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>",
                                      r, re.S | re.I)]
        for i in range(0, len(celdas) - 3, 4):
            try:
                e, s, d = (float(celdas[i]), float(celdas[i + 1]),
                           float(celdas[i + 3]))
                puntos[e] = (s, d)
            except (ValueError, IndexError):
                continue
    return puntos


def descargar(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": "RadiopharmaOS-dataset-verifier/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("latin-1")


def verificar_dataset(data_dir: Path, reaction_id: str,
                      fuente_local: Path | None = None) -> dict:
    meta = json.loads((data_dir / "reactions.json").read_text())
    if reaction_id not in meta:
        return {"reaccion": reaction_id, "estado": "no_verificable",
                "motivo": "reacción desconocida en reactions.json"}
    rel = meta[reaction_id]["file"]
    filas, cabecera = leer_csv_versionado(data_dir / rel)
    url = cabecera.get("url")
    resultado = {"reaccion": reaction_id, "dataset": rel, "fuente_url": url,
                 "n_puntos_versionados": len(filas),
                 "verificado_en": datetime.now(timezone.utc).isoformat()}
    if not url:
        resultado.update(estado="no_verificable",
                         motivo="el CSV no declara url de fuente")
        return resultado
    try:
        html = (fuente_local.read_text(encoding="latin-1")
                if fuente_local else descargar(url))
    except Exception as exc:  # red/caída de la fuente → honesto
        resultado.update(estado="no_verificable",
                         motivo=f"fuente inaccesible: {exc}")
        return resultado
    oficial = parsear_tabla_iaea_html(html)
    discrepan, faltan = [], []
    for e, s, d in filas:
        if e not in oficial:
            faltan.append(e)
            continue
        so, do = oficial[e]
        if abs(s - so) > TOLERANCIA_ABS or abs((d or 0) - do) > TOLERANCIA_ABS:
            discrepan.append({"energia_mev": e, "versionado": s,
                              "oficial": so})
    resultado.update(n_puntos_fuente=len(oficial),
                     discrepancias=discrepan,
                     energias_no_en_fuente=faltan)
    if discrepan or faltan:
        resultado["estado"] = "discrepancia"
    else:
        resultado["estado"] = "verificado"
    return resultado


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--reaccion", required=True)
    ap.add_argument("--fuente-local", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    informe = verificar_dataset(args.data, args.reaccion, args.fuente_local)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(informe, indent=2,
                                       ensure_ascii=False))
    print(json.dumps(informe, indent=2, ensure_ascii=False))
    return 0 if informe["estado"] == "verificado" else 1


if __name__ == "__main__":
    raise SystemExit(main())
