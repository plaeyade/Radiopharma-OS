"""Registro de tablas de poder de frenado externas (EDS 19.10).

SRIM es software propietario (solo Windows, sin licencia en esta
plataforma): la plataforma NUNCA ejecuta ni simula SRIM. Lo que sí se
permite — y es el único camino honesto de "configurar SRIM" — es
registrar tablas REALES exportadas por el usuario desde su propia
instalación de SRIM (o de ATIMA/CATIMA), como dato versionado con
fuente, fecha de ejecución y hash de integridad (ALCOA+).

Las tablas registradas NO se usan en el cómputo de rendimientos hasta
una calibración explícita: su estado es `registrada_no_calibrada` —
declarado, nunca asumido.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


class TablaExternaInvalida(ValueError):
    """Tabla externa de poder de frenado inválida."""


class ExternalStoppingTables:
    """Almacén versionado de tablas externas con fuente obligatoria."""

    def __init__(self, directorio: Path) -> None:
        self._dir = Path(directorio)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._manifiesto = self._dir / "manifest.json"
        if not self._manifiesto.exists():
            self._manifiesto.write_text(json.dumps(
                {"tablas": [],
                 "nota": "tablas externas (SRIM/ATIMA exportadas por el "
                         "usuario) — registradas con fuente, nunca "
                         "ejecutadas ni simuladas por la plataforma"},
                indent=2, ensure_ascii=False))

    def _leer(self) -> dict:
        return json.loads(self._manifiesto.read_text())

    def registrar(self, material: str, fuente: str, ejecutado_en: str,
                  descripcion: str, filas: list[list[float]],
                  registrado_por: str) -> dict:
        if not material.strip():
            raise TablaExternaInvalida("material obligatorio")
        if not fuente.strip():
            raise TablaExternaInvalida(
                "fuente obligatoria: la tabla debe declarar de dónde sale "
                "(p. ej. 'SRIM-2013 ejecutado por el usuario, archivo "
                "PROTONS_in_water.txt') — nunca se inventa (49.11)")
        if not ejecutado_en.strip():
            raise TablaExternaInvalida(
                "fecha/entorno de ejecución obligatorio (trazabilidad)")
        if len(filas) < 2:
            raise TablaExternaInvalida("la tabla exige al menos 2 filas")
        energias = [float(f[0]) for f in filas]
        paradas = [float(f[1]) for f in filas]
        if any(e <= 0 for e in energias) or any(s <= 0 for s in paradas):
            raise TablaExternaInvalida(
                "energías y poderes de frenado deben ser positivos")
        if any(b <= a for a, b in zip(energias, energias[1:])):
            raise TablaExternaInvalida(
                "las energías deben ser estrictamente crecientes")

        lineas = [
            f"# fuente: {fuente.strip()}",
            f"# ejecutado_en: {ejecutado_en.strip()}",
            f"# descripcion: {descripcion.strip()}",
            "# registrada_por: " + (registrado_por.strip() or "desconocido"),
            "# registrada_en: " + datetime.now(timezone.utc).isoformat(),
            "energy_MeV,stopping_MeV_cm2_g",
        ] + [f"{e},{s}" for e, s in zip(energias, paradas)]
        contenido = "\n".join(lineas) + "\n"
        sha = hashlib.sha256(contenido.encode()).hexdigest()

        man = self._leer()
        version = sum(1 for t in man["tablas"]
                      if t["material"] == material.strip()) + 1
        nombre = f"{material.strip().lower().replace(' ', '_')}_v{version}.csv"
        (self._dir / nombre).write_text(contenido)
        entrada = {
            "material": material.strip(), "version": version,
            "archivo": nombre, "sha256": sha,
            "fuente": fuente.strip(), "ejecutado_en": ejecutado_en.strip(),
            "descripcion": descripcion.strip(),
            "registrado_por": registrado_por.strip() or "desconocido",
            "registrada_en": datetime.now(timezone.utc).isoformat(),
            "estado": "registrada_no_calibrada",
            "nota_honestidad": (
                "tabla REAL exportada por el usuario y registrada con "
                "fuente e integridad; NO se usa en el cómputo de "
                "rendimientos hasta calibración explícita — la plataforma "
                "nunca ejecuta ni simula SRIM"),
        }
        man["tablas"].append(entrada)
        self._manifiesto.write_text(
            json.dumps(man, indent=2, ensure_ascii=False))
        return entrada

    def listar(self) -> list[dict]:
        return list(self._leer()["tablas"])

    def obtener(self, material: str, version: int) -> dict:
        for t in self._leer()["tablas"]:
            if t["material"] == material and t["version"] == version:
                return t
        raise TablaExternaInvalida(
            f"tabla desconocida: {material} v{version}")

    def leer_filas(self, entrada: dict) -> list[tuple[float, float]]:
        """Filas reales del CSV registrado (con verificación sha256)."""
        ruta = self._dir / entrada["archivo"]
        contenido = ruta.read_text()
        sha = hashlib.sha256(contenido.encode()).hexdigest()
        if sha != entrada["sha256"]:
            raise TablaExternaInvalida(
                f"integridad violada en {entrada['archivo']} "
                f"(sha256 no coincide — ALCOA+)")
        filas = []
        for linea in contenido.splitlines():
            if linea.startswith("#") or linea.startswith("energy_MeV"):
                continue
            e, s = linea.split(",")
            filas.append((float(e), float(s)))
        return filas

    def registrar_calibracion(self, material: str, version: int,
                              comparacion: dict, criterio_max_pct: float,
                              motivo: str, registrado_por: str) -> dict:
        """Registra una calibración (append-only, ALCOA+) y actualiza el
        estado de la tabla según el veredicto.

        ``comparacion`` la computa el llamador contra el proveedor activo
        con datos reales — este almacén jamás genera métricas por su
        cuenta.
        """
        if not motivo.strip():
            raise TablaExternaInvalida("la calibración exige motivo")
        man = self._leer()
        for t in man["tablas"]:
            if t["material"] == material and t["version"] == version:
                cal = {
                    "criterio_max_pct": criterio_max_pct,
                    "comparacion": comparacion,
                    "veredicto": ("calibrada" if comparacion["desv_max_pct"]
                                  <= criterio_max_pct else "rechazada"),
                    "motivo": motivo.strip(),
                    "registrado_por": registrado_por.strip() or "desconocido",
                    "registrada_en": datetime.now(timezone.utc).isoformat(),
                }
                t.setdefault("calibraciones", []).append(cal)
                t["estado"] = ("calibrada" if cal["veredicto"] == "calibrada"
                               else "rechazada_declarada")
                self._manifiesto.write_text(
                    json.dumps(man, indent=2, ensure_ascii=False))
                return {"tabla": t, "calibracion": cal}
        raise TablaExternaInvalida(
            f"tabla desconocida: {material} v{version}")
