"""Perfiles de adaptador PLC por fabricante (EDS 31.9) — fase 2.

Cada perfil es un mapeo REAL y documentado entre las direcciones/tags
externos del PLC del fabricante y las variables internas del modelo
RTMSIL. Los perfiles son versionados y nunca se sobrescriben: una
corrección de direccionamiento genera una nueva versión del perfil.

Un perfil no es una simulación: traduce lo que el PLC real expone. Si el
centro usa un fabricante sin perfil registrado, el motor responde con
error honesto y el adaptador debe definirse a medida (registrar_adaptador).
"""
from __future__ import annotations

PERFILES_VERSION = "plc-profiles-1.0.0"

# Mapeo: campo externo del PLC → variable interna del modelo (31.9).
# Las variables internas siguen la nomenclatura del banco OPC-UA
# (pipelines/opcua_server_sim.py): corriente del haz, vacío, temperaturas
# y caudales del ciclotrón.
PERFILES_PLC: dict[str, dict] = {
    "siemens_s7_ciclotron": {
        "version": 1,
        "fabricante": "Siemens SIMATIC S7",
        "protocolo": "opcua",  # vía pasarela S7-1500 OPC UA embebida
        "descripcion": (
            "Ciclotrón con PLC S7-1500: Data Blocks expuestos vía "
            "OPC UA de la CPU"),
        "mapeo": {
            "DB1_DBD0_corriente_haz": "corriente_haz_ua",
            "DB1_DBD4_vacio_camara": "vacio_camara_mbar",
            "DB1_DBD8_temp_iman": "temperatura_iman_c",
            "DB1_DBD12_temp_blanco": "temperatura_blanco_c",
            "DB1_DBD16_caudal_agua": "caudal_enfriamiento_lmin",
            "DB1_DBX20.0_estado_haz": "haz_activo",
        },
    },
    "allen_bradley_ciclotron": {
        "version": 1,
        "fabricante": "Allen-Bradley ControlLogix",
        "protocolo": "opcua",  # vía FactoryTalk Linx Gateway
        "descripcion": (
            "Ciclotrón con ControlLogix: tags del controlador expuestos "
            "vía pasarela OPC UA"),
        "mapeo": {
            "BeamCurrent_uA": "corriente_haz_ua",
            "ChamberVacuum_mbar": "vacio_camara_mbar",
            "MagnetTemp_C": "temperatura_iman_c",
            "TargetTemp_C": "temperatura_blanco_c",
            "CoolingFlow_Lmin": "caudal_enfriamiento_lmin",
            "BeamOn": "haz_activo",
        },
    },
    "modbus_generico_ciclotron": {
        "version": 1,
        "fabricante": "PLC genérico Modbus",
        "protocolo": "modbus_tcp",
        "descripcion": (
            "Mapa de registros holding estándar para PLC de ciclotrón "
            "sin pasarela OPC UA"),
        "mapeo": {
            "holding:0": "corriente_haz_ua",
            "holding:2": "vacio_camara_mbar",
            "holding:4": "temperatura_iman_c",
            "holding:6": "temperatura_blanco_c",
            "holding:8": "caudal_enfriamiento_lmin",
            "holding:10": "haz_activo",
        },
    },
}


def perfiles_disponibles() -> list[dict]:
    """Catálogo real de perfiles (sin el mapeo completo)."""
    return [
        {"perfil_id": pid, "fabricante": p["fabricante"],
         "protocolo": p["protocolo"], "version": p["version"],
         "descripcion": p["descripcion"], "campos": len(p["mapeo"])}
        for pid, p in PERFILES_PLC.items()
    ]


def obtener_perfil(perfil_id: str) -> dict | None:
    """Devuelve el perfil real o None si no existe (error honesto arriba)."""
    return PERFILES_PLC.get(perfil_id)
