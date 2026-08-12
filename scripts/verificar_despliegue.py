#!/usr/bin/env python3
"""Verificación post-despliegue Fase 1 — plataforma honesta.

Consulta los endpoints /status REALES de los conectores de cada servicio y
reporta: servicios caídos, marcadores honestos activos (no_configurado /
fallo_conexion / sin_runtime / no_demostrable) y conectores registrados.
No inventa nada: lo que no responde se reporta como caído.
Uso:  python3 scripts/verificar_despliegue.py [host_base]
"""
import json
import sys
import urllib.request
import urllib.error

MARCADORES = ("no_configurado", "no_configurada", "fallo_conexion",
              "sin_runtime", "sin_modelos", "no_demostrable", "no_inyectado")

PUNTOS = [
    ("nuclear-data :8001  conectores EXFOR/SRIM/NNDC", "http://{h}:8001/api/v1/connectors/status"),
    ("process      :8007  OSRM logistics",             "http://{h}:8007/api/v1/osrm/status"),
    ("surrogate    :8008  BentoML serving",            "http://{h}:8008/api/v1/serving/status"),
    ("surrogate    :8008  GenAI embeddings/LLM",       "http://{h}:8008/api/v1/genai/status"),
    ("surrogate    :8008  extractor documental 45.7",  "http://{h}:8008/api/v1/rag/extractor-status"),
    ("telemetry    :8006  SCADA RTMSIL cap.31",        "http://{h}:8006/api/v1/scada/status"),
]


def _buscar_marcadores(obj, ruta=""):
    """Recorre el JSON real y devuelve [(ruta, valor)] con marcadores honestos."""
    hallados = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            hallados += _buscar_marcadores(v, f"{ruta}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hallados += _buscar_marcadores(v, f"{ruta}[{i}]")
    elif isinstance(obj, str) and obj in MARCADORES:
        hallados.append((ruta, obj))
    elif obj is False and any(m in ruta for m in ("embedding_neuronal", "conectado", "configurado")):
        hallados.append((ruta, obj))
    return hallados


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    caidos, pendientes, operativos = [], [], []
    for nombre, plantilla in PUNTOS:
        url = plantilla.format(h=host)
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                datos = json.loads(r.read().decode())
        except Exception as e:
            caidos.append(f"{nombre}  →  SIN RESPUESTA ({type(e).__name__}: {e})")
            continue
        marcas = _buscar_marcadores(datos)
        if marcas:
            pendientes.append((nombre, marcas))
        else:
            operativos.append(nombre)

    print("=" * 70)
    print("VERIFICACIÓN DE DESPLIEGUE — Radiopharma OS Fase 1 (estado REAL)")
    print("=" * 70)
    print(f"\nServicios caídos: {len(caidos)}")
    for c in caidos:
        print(f"  ✗ {c}")
    print(f"\nConectores con marcadores honestos pendientes: {len(pendientes)}")
    for nombre, marcas in pendientes:
        print(f"  ! {nombre}")
        for ruta, valor in marcas:
            print(f"      {ruta} = {valor}")
    print(f"\nBloques plenamente operativos: {len(operativos)}")
    for o in operativos:
        print(f"  ✓ {o}")
    print()
    if caidos:
        sys.exit(2)
    if pendientes:
        print("Estado honesto: faltan conexiones por cablear — ver docs/despliegue_fase1.md")
        sys.exit(1)
    print("Despliegue completo: sin marcadores pendientes en los puntos verificados.")


if __name__ == "__main__":
    main()
