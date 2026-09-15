"""Importador de tablas "Stopping/Range" exportadas de SRIM (Fase 25).

La plataforma NUNCA ejecuta ni simula SRIM (software propietario, sin
licencia aquí — política canónica). Lo que sí hace este módulo es parsear
la tabla REAL que el usuario exporta de su propia instalación de SRIM
(SRIM → "Stopping/Range Tables" → archivo en "/SRIM Outputs") para
registrarla como tabla externa versionada con fuente citada (EDS 19.10,
regla 49.11: ninguna eficiencia/poder de frenado sin fuente).

Formato real del archivo (documentado en el manual oficial SRIM-2013,
cap. 8, srim.org/SRIM/SRIM 08.pdf):

    Ion=Hydrogen, Mass=1.008
    Tgt=H+O(Solid), Density=1 g/cm3
    Stopping Units=MeV/(mg/cm2)
    Energy(keV)   S(Elec)   S(Nuc)
    1.020E+00   1.751E-01   3.921E-02
    ...

Unidades de salida de SRIM (SR.IN, línea 14): solo se aceptan las de
frenado MÁSICO (4, 5, 6) convertibles a MeV·cm²/g sin ambigüedad:
  (4) keV/(ug/cm2)  == MeV/(mg/cm2)   → ×1000
  (5) MeV/(mg/cm2)                      → ×1000
  (6) keV/(mg/cm2) == eV/(ug/cm2) == MeV/(g/cm2) → ×1
Las basadas en longitud (1: eV/Angstrom, 2: keV/micron, 3: MeV/mm), en
átomos (7) o reducidas L.S.S. (8) se RECHAZAN: convertirlas exigiría
densidad/supuestos que no trae el archivo — preferimos `no_convertible`
honesto antes que una cifra inventada.

El poder de frenado total registrado es S_elec + S_nuc (convención
física estándar, declarada en el propio manual).
"""
from __future__ import annotations

import re


class SrimFormatoInvalido(ValueError):
    """El texto no es una tabla Stopping/Range de SRIM válida."""


_RE_ION = re.compile(r"^Ion\s*=\s*(?P<ion>[A-Za-z]+)\s*,\s*Mass\s*=\s*(?P<mass>[0-9.]+)")
_RE_TGT = re.compile(r"^Tgt\s*=\s*(?P<tgt>.+?)(?:\((?P<fase>Solid|Gas)\))?,\s*Density\s*=\s*(?P<dens>[0-9.Ee+-]+)\s*g/cm3")
_RE_UNITS = re.compile(r"^Stopping Units\s*=\s*(?P<u>.+?)\s*$")
_RE_NUM = re.compile(
    r"^\s*(?P<e>[0-9.]+E[+-][0-9]+)\s+(?P<se>[0-9.]+E[+-][0-9]+)\s+(?P<sn>[0-9.]+E[+-][0-9]+)\s*$",
    re.IGNORECASE)

# factor a MeV·cm²/g para las unidades másicas aceptadas
_UNIDADES_ACEPTADAS = {
    "keV/(ug/cm2)": 1000.0,   # (4) ≡ MeV/(mg/cm2)
    "MeV/(mg/cm2)": 1000.0,   # (5)
    "keV/(mg/cm2)": 1.0,      # (6) ≡ MeV/(g/cm2)
    "eV/(ug/cm2)": 1.0,       # (6) ≡ MeV/(g/cm2)
    "MeV/(g/cm2)": 1.0,       # (6)
}


def parse_srim_table(texto: str) -> dict:
    """Parsea una tabla Stopping/Range real exportada de SRIM.

    Devuelve {"ion", "masa_ion_u", "blanco", "densidad_g_cm3",
              "unidades_originales", "filas": [[E_MeV, S_MeV_cm2_g], ...]}
    con el poder de frenado total (electrónico + nuclear).
    Lanza SrimFormatoInvalido ante cualquier desviación — nunca rellena
    ni interpola huecos del archivo.
    """
    if not texto or not texto.strip():
        raise SrimFormatoInvalido("archivo vacío")

    ion = masa = blanco = densidad = unidades = None
    filas: list[list[float]] = []
    for linea in texto.splitlines():
        linea = linea.rstrip()
        if not linea.strip():
            continue
        m = _RE_ION.match(linea.strip())
        if m:
            ion, masa = m.group("ion"), float(m.group("mass"))
            continue
        m = _RE_TGT.match(linea.strip())
        if m:
            blanco, densidad = m.group("tgt").strip(), float(m.group("dens"))
            continue
        m = _RE_UNITS.match(linea.strip())
        if m:
            unidades = m.group("u")
            continue
        m = _RE_NUM.match(linea)
        if m:
            filas.append([float(m.group("e")), float(m.group("se")),
                          float(m.group("sn"))])
            continue
        # líneas de cabecera/separador conocidas se toleran; lo demás, no
        if linea.strip().startswith(("Energy", "dE/dx", "---", "===",
                                     "Stopping/Range", "SRIM")):
            continue
        if filas:
            # basura DESPUÉS de empezar la tabla = archivo corrupto
            raise SrimFormatoInvalido(
                f"línea irreconocible dentro de la tabla: {linea!r}")

    if ion is None or unidades is None:
        raise SrimFormatoInvalido(
            "faltan cabeceras obligatorias (Ion= / Stopping Units=)")
    if unidades not in _UNIDADES_ACEPTADAS:
        raise SrimFormatoInvalido(
            f"unidad '{unidades}' no_convertible: solo se aceptan unidades "
            "de frenado másico (MeV/(mg/cm2), keV/(mg/cm2), keV/(ug/cm2), "
            "eV/(ug/cm2), MeV/(g/cm2)); las basadas en longitud/átomos/LSS "
            "exigirían supuestos que el archivo no trae")
    if len(filas) < 3:
        raise SrimFormatoInvalido(
            f"tabla con {len(filas)} filas (<3): insuficiente para una "
            "tabla de frenado registrable")

    factor = _UNIDADES_ACEPTADAS[unidades]
    out: list[list[float]] = []
    e_prev = -1.0
    for e_kev, se, sn in filas:
        if e_kev <= 0 or se < 0 or sn < 0:
            raise SrimFormatoInvalido("valores no físicos en la tabla")
        if e_kev <= e_prev:
            raise SrimFormatoInvalido("energías no monótonas — archivo corrupto")
        e_prev = e_kev
        out.append([e_kev / 1000.0, (se + sn) * factor])  # MeV, MeV·cm²/g

    return {
        "ion": ion,
        "masa_ion_u": masa,
        "blanco": blanco,
        "densidad_g_cm3": densidad,
        "unidades_originales": unidades,
        "filas": out,
        "nota_honestidad": (
            "tabla REAL exportada de la instalación SRIM del usuario; "
            "S_total = S_elec + S_nuc (convención del manual SRIM-2013); "
            "la plataforma nunca ejecuta ni simula SRIM"),
    }
