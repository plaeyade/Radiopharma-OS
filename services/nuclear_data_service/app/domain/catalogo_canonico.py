"""Informe cap. 19 — Catálogo canónico semilla.

Radionúclidos PET (19.6), SPECT (19.7) y terapéuticos (19.8) con la
estructura completa 19.5. Vidas medias: valores de referencia públicos
de la literatura nuclear estándar (cada entrada conserva su bibliografía
19.17). Cualquier dato experimental registrado posteriormente prevalece
sobre el modelo (19.12).
"""

from __future__ import annotations

from typing import Any

MIN_S = 60.0
H_S = 3600.0
D_S = 86400.0

BIBLIO_BASE = ["NuDat 3.0 (NNDC/BNL)", "IAEA LiveChart of Nuclides"]


def _entrada(vida_s: float, reaccion: str, umbral: float, blanco: str,
             tipo_blanco: str, enriquecimiento: str, espesor: str, geometria: str,
             precursor: str, sintesis: str, purificacion: str, eficiencia: float,
             indicaciones: list[str], dosis_mbq: float, ventana_h: float,
             logistica: str, modos: list[str], emisiones: list[str],
             perdidas: float = 0.05, rend_pur: float = 0.95,
             factor_form: float = 0.98, costo: str = "medio") -> dict[str, Any]:
    return {
        "nuclear": {"reaccion": reaccion, "energia_umbral_mev": umbral,
                    "vida_media_s": vida_s, "modos_decaimiento": modos,
                    "emisiones": emisiones},
        "fisica": {"material_blanco": blanco, "tipo_blanco": tipo_blanco,
                   "enriquecimiento": enriquecimiento, "espesor": espesor,
                   "geometria": geometria},
        "quimica": {"precursor": precursor, "sintesis": sintesis,
                    "purificacion": purificacion, "eficiencia": eficiencia,
                    "perdidas": perdidas, "rendimiento_purificacion": rend_pur,
                    "factor_formulacion": factor_form},
        "clinica": {"indicaciones": indicaciones, "dosis_habitual_mbq": dosis_mbq,
                    "ventana_horas": ventana_h, "logistica": logistica},
        "economica": {"costo": costo, "rendimiento": "estándar de producción",
                      "recuperacion": "estándar", "rentabilidad": "operativa"},
    }


# ---------------- PET (19.6) ----------------
CATALOGO_PET: dict[str, dict[str, Any]] = {
    "f18": _entrada(109.77 * MIN_S, "18O(p,n)18F", 2.6, "H2-18O", "liquido",
                    ">97 % 18O", "1.5 ml", "blanco de niobio con ventana Havar",
                    "[18F]F−", "fluoración nucleofílica (FDG)",
                    "Sep-Pak QMA/alumina", 0.72,
                    ["oncología PET (FDG)", "neurología", "cardiología"],
                    370.0, 10.0, "distribución regional por decaimiento",
                    ["β+ (96.9 %)", "CE"], ["γ 511 keV"]),
    "c11": _entrada(20.36 * MIN_S, "14N(p,α)11C", 3.2, "N2 + O2 traza", "gaseoso",
                    "natural", "30 cm", "blanco de gas presurizado",
                    "[11C]CO2 / [11C]CH4", "metilación con [11C]CH3I",
                    "HPLC semipreparativa", 0.55,
                    ["neurología PET", "oncología (metionina, colina)"],
                    555.0, 1.5, "solo producción in-situ",
                    ["β+ (99.8 %)"], ["γ 511 keV"], perdidas=0.1, rend_pur=0.9),
    "n13": _entrada(9.97 * MIN_S, "16O(p,α)13N", 5.7, "H2O natural", "liquido",
                    "natural", "1.2 ml", "blanco de titanio",
                    "[13N]NH3", "reducción de Devarda",
                    "destilación", 0.80,
                    ["perfusión miocárdica PET"],
                    555.0, 0.5, "uso inmediato in-situ",
                    ["β+ (100 %)"], ["γ 511 keV"], rend_pur=0.92),
    "o15": _entrada(122.24, "15N(p,n)15O", 3.8, "N2-15", "gaseoso",
                    ">98 % 15N", "20 cm", "blanco de gas",
                    "[15O]O2 / [15O]H2O", "conversión catalítica",
                    "en línea", 0.85,
                    ["perfusión cerebral y miocárdica"],
                    740.0, 0.17, "administración junto al ciclotrón",
                    ["β+ (99.9 %)"], ["γ 511 keV"], rend_pur=0.97),
    "ga68": _entrada(67.7 * MIN_S, "68Zn(p,n)68Ga", 3.7, "Zn-68 electrodepositado",
                     "solido", ">98 % 68Zn", "50 µm sobre Cu",
                     "blanco sólido de cobre",
                     "68GaCl3 en HCl", "marcaje de PSMA/DOTATATE",
                     "columna catiónica", 0.85,
                    ["oncología PET (PSMA, NET)"],
                    185.0, 4.0, "ciclotrón o generador 68Ge/68Ga",
                    ["β+ (89 %)", "CE"], ["γ 511 keV", "γ 1077 keV"]),
    "zr89": _entrada(78.4 * H_S, "89Y(p,n)89Zr", 4.7, "Y-89 lámina", "solido",
                     "natural (monoisotópico)", "250 µm",
                     "blanco sólido de itrio",
                     "89Zr-oxalato", "quelación con desferrioxamina",
                     "HPLC", 0.70,
                    ["inmuno-PET (anticuerpos)"],
                    74.0, 96.0, "envío interinstitucional viable",
                    ["β+ (22.7 %)", "CE"], ["γ 511 keV", "γ 909 keV"],
                    costo="alto"),
    "cu64": _entrada(12.7 * H_S, "64Ni(p,n)64Cu", 2.5, "Ni-64 electrodepositado",
                     "solido", ">95 % 64Ni", "40 µm sobre Au",
                     "blanco sólido",
                     "64CuCl2", "marcaje DOTA/ATSM",
                     "intercambio aniónico", 0.80,
                    ["oncología PET", "teranóstico (par con 67Cu)"],
                    370.0, 24.0, "distribución nocturna viable",
                    ["β+ (17.5 %)", "β− (39 %)", "CE"],
                    ["γ 511 keV", "γ 1346 keV"], costo="alto"),
    "cu61": _entrada(3.34 * H_S, "64Zn(p,α)61Cu", 6.0, "Zn-64", "solido",
                     ">90 % 64Zn", "50 µm", "blanco sólido",
                     "61CuCl2", "marcaje rápido",
                     "intercambio aniónico", 0.75,
                    ["oncología PET"],
                    370.0, 6.0, "uso regional",
                    ["β+ (61 %)", "CE"], ["γ 511 keV", "γ 283/656 keV"]),
    "sc44": _entrada(4.04 * H_S, "44Ca(p,n)44Sc", 3.5, "Ca-44 (CaCO3)", "solido",
                     ">97 % 44Ca", "100 mg", "blanco sólido prensado",
                     "44ScCl3", "marcaje DOTA",
                     "resina DGA", 0.80,
                    ["oncología PET (alternativa a 68Ga)"],
                    370.0, 8.0, "uso regional",
                    ["β+ (94.3 %)", "CE"], ["γ 511 keV", "γ 1157 keV"]),
    "mn52": _entrada(5.59 * D_S, "52Cr(p,n)52Mn", 5.4, "Cr natural/52Cr", "solido",
                     "natural", "200 µm", "blanco sólido",
                     "52MnCl2", "marcaje experimental",
                     "resina de intercambio", 0.65,
                    ["inmuno-PET (investigación)"],
                    185.0, 120.0, "envío de larga distancia viable",
                    ["β+ (29.4 %)", "CE"], ["γ 511 keV", "γ 744/935/1434 keV"],
                    costo="alto"),
    "i124": _entrada(4.18 * D_S, "124Te(p,n)124I", 4.8, "TeO2-124", "solido",
                     ">99 % 124Te", "lecho fundido", "blanco sólido de platino",
                     "Na124I", "destilación en seco",
                     "trampa alcalina", 0.75,
                    ["inmuno-PET", "dosimetría tiroidea"],
                    74.0, 96.0, "envío interinstitucional viable",
                    ["β+ (22.7 %)", "CE"], ["γ 511 keV", "γ 603/1691 keV"],
                    costo="alto"),
}

# ---------------- SPECT (19.7) ----------------
CATALOGO_SPECT: dict[str, dict[str, Any]] = {
    "tc99m": _entrada(6.01 * H_S, "99Mo/99mTc (generador)", 0.0,
                      "generador 99Mo (alumina)", "solido",
                      "n/a", "columna", "generador cromatográfico",
                      "Na99mTcO4 eluido", "kits liofilizados (MDP, MAG3, HMPAO)",
                      "alúmina", 0.92,
                    ["medicina nuclear general (hueso, renal, cardiología)"],
                    740.0, 8.0, "elución diaria in-situ",
                    ["TI"], ["γ 140.5 keV"], costo="bajo"),
    "i123": _entrada(13.2 * H_S, "124Te(p,2n)123I", 14.0, "TeO2-124", "solido",
                     ">99 % 124Te", "lecho fundido", "blanco sólido",
                     "Na123I", "marcaje MIBG/hippurano",
                     "destilación", 0.80,
                    ["neurología SPECT (DaTSCAN)", "MIBG"],
                    185.0, 24.0, "envío diario viable",
                    ["CE"], ["γ 159 keV"], costo="alto"),
    "in111": _entrada(2.80 * D_S, "112Cd(p,2n)111In", 12.0, "Cd-112", "solido",
                      ">98 % 112Cd", "lámina", "blanco sólido",
                      "111InCl3", "marcaje octreótido/anticuerpos",
                      "intercambio iónico", 0.80,
                    ["SPECT de tumores neuroendocrinos", "marcaje celular"],
                    185.0, 72.0, "envío interinstitucional",
                    ["CE"], ["γ 171/245 keV"], costo="alto"),
    "tl201": _entrada(73.1 * H_S, "203Tl(p,3n)201Pb→201Tl", 19.0, "Tl-203", "solido",
                      ">95 % 203Tl", "lámina", "blanco sólido",
                      "201TlCl", "purificación del hijo 201Pb",
                      "intercambio iónico", 0.70,
                    ["perfusión miocárdica SPECT"],
                    111.0, 96.0, "envío interinstitucional",
                    ["CE"], ["rayos X 69-83 keV", "γ 167 keV"], costo="alto"),
    "ga67": _entrada(78.3 * H_S, "68Zn(p,2n)67Ga", 15.0, "Zn-68", "solido",
                     ">98 % 68Zn", "lámina", "blanco sólido",
                     "67Ga-citrato", "formulación de citrato",
                     "intercambio iónico", 0.75,
                    ["SPECT inflamación/linfoma"],
                    185.0, 72.0, "envío interinstitucional",
                    ["CE"], ["γ 93/185/300 keV"], costo="medio"),
}

# ---------------- Terapéuticos (19.8) ----------------
CATALOGO_TERAPEUTICOS: dict[str, dict[str, Any]] = {
    "cu67": _entrada(61.8 * H_S, "68Zn(p,2p)67Cu", 20.0, "Zn-68", "solido",
                     ">98 % 68Zn", "lámina", "blanco sólido",
                     "67CuCl2", "marcaje de anticuerpos (radioinmunoterapia)",
                     "intercambio aniónico", 0.70,
                    ["radioinmunoterapia (β−)"],
                    370.0, 72.0, "producción centralizada",
                    ["β− (100 %)"], ["γ 185 keV"], costo="alto"),
    "sc47": _entrada(3.35 * D_S, "48Ca(p,2n)47Sc", 15.0, "Ca-48", "solido",
                     ">95 % 48Ca", "100 mg", "blanco sólido prensado",
                     "47ScCl3", "marcaje DOTA (par teranóstico con 44Sc)",
                     "resina DGA", 0.70,
                    ["terapia β− (teranóstico)"],
                    370.0, 96.0, "envío interinstitucional",
                    ["β− (100 %)"], ["γ 159 keV"], costo="alto"),
    "tb149": _entrada(4.1 * H_S, "152Gd(p,4n)149Tb", 30.0, "Gd-152", "solido",
                      "enriquecido", "lámina", "blanco sólido (producción "
                      "alternativa: spallación + ISOL)",
                      "149Tb", "marcaje de anticuerpos (terapia α)",
                      "separación isotópica", 0.50,
                    ["terapia alfa (investigación)"],
                    37.0, 8.0, "producción centralizada especializada",
                    ["α (16.7 %)", "β+"], ["α 3.97 MeV"], costo="muy alto"),
    "tb152": _entrada(17.5 * H_S, "152Gd(p,n)152Tb", 8.0, "Gd-152", "solido",
                      "enriquecido", "lámina", "blanco sólido",
                      "152Tb", "marcaje DOTA (PET teranóstico)",
                      "separación química", 0.55,
                    ["PET teranóstico (β+)"],
                    185.0, 24.0, "producción centralizada",
                    ["β+ (17 %)", "CE"], ["γ 511 keV"], costo="muy alto"),
    "tb155": _entrada(5.32 * D_S, "155Gd(p,n)155Tb", 6.0, "Gd-155", "solido",
                      "enriquecido", "lámina", "blanco sólido",
                      "155Tb", "marcaje (SPECT teranóstico)",
                      "separación química", 0.60,
                    ["SPECT teranóstico"],
                    185.0, 120.0, "envío viable",
                    ["CE"], ["γ 87/105/180 keV"], costo="muy alto"),
    "tb161": _entrada(6.91 * D_S, "160Gd(n,γ)161Gd→161Tb (reactor) / "
                      "160Gd(d,2n)161Tb", 5.0, "Gd-160", "solido",
                      "enriquecido", "blanco reactor/ciclotrón", "blanco sólido",
                      "161Tb", "marcaje DOTA (terapia β− + Auger)",
                      "separación química", 0.65,
                    ["terapia β− (alternativa a 177Lu)"],
                    3700.0, 168.0, "envío viable",
                    ["β− (100 %)"], ["γ 48.9/74.6 keV"], costo="alto"),
    "ac225": _entrada(9.92 * D_S, "232Th(p,x)225Ac / generador 229Th", 0.0,
                      "Th-232", "solido", "natural", "blanco de torio",
                      "blanco sólido de gran sección",
                      "225Ac(NO3)3", "marcaje PSMA/DOTATOC (terapia α)",
                      "resina DGA", 0.60,
                    ["terapia alfa dirigida (PSMA, NET)"],
                    0.1, 240.0, "producción centralizada (cuando aplique el "
                    "modelo de producción seleccionado)",
                    ["α (cascada)"], ["γ 218/440 keV"], costo="muy alto"),
    "at211": _entrada(7.21 * H_S, "209Bi(α,2n)211At", 29.0, "Bi-209", "solido",
                      "natural", "lámina sobre Al", "blanco sólido (haz α)",
                      "211At", "astatación de anticuerpos",
                      "destilación en seco", 0.65,
                    ["terapia alfa (investigación)"],
                    37.0, 12.0, "uso regional inmediato",
                    ["α (41.8 %)", "CE"], ["rayos X Po 77-92 keV"],
                    costo="muy alto"),
}


def sembrar_catalogo(library) -> dict[str, int]:
    """Incorpora el catálogo canónico como versión 1 de cada radionúclido."""
    from app.domain.radionuclide_library import RadionuclideLibrary
    assert isinstance(library, RadionuclideLibrary)
    conteos = {"PET": 0, "SPECT": 0, "terapeutico": 0}
    for categoria, catalogo in (("PET", CATALOGO_PET),
                                ("SPECT", CATALOGO_SPECT),
                                ("terapeutico", CATALOGO_TERAPEUTICOS)):
        for nuclide, entrada in catalogo.items():
            library.incorporar(
                nuclide, categoria, dict(entrada["nuclear"]),
                dict(entrada["fisica"]), dict(entrada["quimica"]),
                dict(entrada["clinica"]), dict(entrada["economica"]),
                list(BIBLIO_BASE), "biblioteca-canonical-seed",
                historial=f"catálogo canónico {categoria} (19.6-19.8)")
            conteos[categoria] += 1
    return conteos
