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
        man = json.loads(self._manifiesto.read_text())
        man.setdefault("promociones", [])
        man.setdefault("activas", {})
        return man

    def _escribir(self, man: dict) -> None:
        self._manifiesto.write_text(
            json.dumps(man, indent=2, ensure_ascii=False))

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
        self._escribir(man)
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
                self._escribir(man)
                return {"tabla": t, "calibracion": cal}
        raise TablaExternaInvalida(
            f"tabla desconocida: {material} v{version}")

    # ------------------------------------------------------------------
    # Promoción a proveedor activo (EDS 19.10)
    #
    # Una tabla externa SOLO se convierte en proveedor activo del
    # material después de una calibración con veredicto `calibrada`, y
    # cada promoción/reversión se registra append-only con motivo —
    # el historial nunca se sobrescribe (ALCOA+). El cómputo declara en
    # cada respuesta qué proveedor y fuente usó realmente.
    # ------------------------------------------------------------------

    def promover(self, material: str, version: int, motivo: str,
                 registrado_por: str) -> dict:
        """Promueve una tabla CALIBRADA a proveedor activo del material."""
        if not motivo.strip():
            raise TablaExternaInvalida("la promoción exige motivo")
        entrada = self.obtener(material, version)
        if entrada["estado"] != "calibrada":
            raise TablaExternaInvalida(
                f"solo se promueve una tabla calibrada: {material} "
                f"v{version} está en estado '{entrada['estado']}' — "
                f"calibrar primero contra el proveedor vigente (19.10); "
                f"una tabla sin calibrar jamás entra en el cómputo")
        filas = self.leer_filas(entrada)      # verifica sha256 (ALCOA+)
        man = self._leer()
        promocion = {
            "accion": "promovida",
            "material": material, "version": version,
            "fuente": entrada["fuente"], "sha256": entrada["sha256"],
            "rango_mev": [filas[0][0], filas[-1][0]],
            "motivo": motivo.strip(),
            "registrado_por": registrado_por.strip() or "desconocido",
            "registrada_en": datetime.now(timezone.utc).isoformat(),
        }
        man["promociones"].append(promocion)
        man["activas"][material] = version
        self._escribir(man)
        return {"promocion": promocion,
                "nota_honestidad": (
                    "proveedor activo cambiado con motivo registrado; el "
                    "historial de promociones es append-only y el cómputo "
                    "declara esta fuente en cada resultado (19.10)")}

    def revertir(self, material: str, motivo: str,
                 registrado_por: str) -> dict:
        """Revoca la promoción vigente: vuelve el proveedor base (ATIMA)."""
        if not motivo.strip():
            raise TablaExternaInvalida("la reversión exige motivo")
        man = self._leer()
        version = man["activas"].get(material)
        if version is None:
            raise TablaExternaInvalida(
                f"no hay promoción vigente para '{material}' — nada que "
                f"revertir (el proveedor base sigue activo)")
        entrada = self.obtener(material, version)
        reversion = {
            "accion": "revertida_a_proveedor_base",
            "material": material, "version": version,
            "fuente": entrada["fuente"], "sha256": entrada["sha256"],
            "motivo": motivo.strip(),
            "registrado_por": registrado_por.strip() or "desconocido",
            "registrada_en": datetime.now(timezone.utc).isoformat(),
        }
        man["promociones"].append(reversion)
        del man["activas"][material]
        self._escribir(man)
        return {"reversion": reversion}

    def activa(self, material: str) -> dict | None:
        """Tabla promovida vigente del material, o None si no la hay."""
        version = self._leer()["activas"].get(material)
        if version is None:
            return None
        return self.obtener(material, version)

    def promociones(self) -> list[dict]:
        """Historial append-only de promociones y reversiones."""
        return list(self._leer()["promociones"])

    def interpolar(self, material: str, energia_mev: float) -> float:
        """Poder de frenado de la tabla PROMOVIDA, interpolación real.

        Fuera del rango registrado de la tabla → error honesto: nunca se
        extrapola una tabla externa fuera de su rango validado (49.11).
        """
        entrada = self.activa(material)
        if entrada is None:
            raise TablaExternaInvalida(
                f"sin tabla promovida para '{material}'")
        filas = self.leer_filas(entrada)      # verifica sha256 (ALCOA+)
        if not (filas[0][0] <= energia_mev <= filas[-1][0]):
            raise TablaExternaInvalida(
                f"energía {energia_mev} MeV fuera del rango validado de "
                f"la tabla promovida [{filas[0][0]}, {filas[-1][0]}] MeV "
                f"— nunca se extrapola una tabla externa (49.11)")
        for (e0, s0), (e1, s1) in zip(filas, filas[1:]):
            if e0 <= energia_mev <= e1:
                f = (energia_mev - e0) / (e1 - e0)
                return s0 + f * (s1 - s0)
        return filas[-1][1]

    def alcance_g_cm2(self, material: str, energia_mev: float) -> float:
        """Alcance CSDA de la tabla promovida: R = ∫ dE/S(E) real.

        Integración trapezoidal sobre los puntos REALES registrados,
        desde la energía mínima de la tabla hasta ``energia_mev``.
        """
        entrada = self.activa(material)
        if entrada is None:
            raise TablaExternaInvalida(
                f"sin tabla promovida para '{material}'")
        filas = self.leer_filas(entrada)      # verifica sha256 (ALCOA+)
        if not (filas[0][0] <= energia_mev <= filas[-1][0]):
            raise TablaExternaInvalida(
                f"energía {energia_mev} MeV fuera del rango validado de "
                f"la tabla promovida [{filas[0][0]}, {filas[-1][0]}] MeV "
                f"— nunca se extrapola una tabla externa (49.11)")
        puntos = [(e, s) for e, s in filas if e <= energia_mev]
        e_fin, s_fin = puntos[-1]
        if e_fin < energia_mev:
            s_e = self.interpolar(material, energia_mev)
            puntos.append((energia_mev, s_e))
        rango = 0.0
        for (e0, s0), (e1, s1) in zip(puntos, puntos[1:]):
            rango += 0.5 * (1.0 / s0 + 1.0 / s1) * (e1 - e0)
        return rango
