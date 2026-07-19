"""
Tests del conector OPC-UA: modelo del servidor simulado y adquisición
end-to-end (servidor OPC-UA real + lectura por browse path + loop de
conector con envío simulado).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipelines"))

from opcua_connector import OpcUaSource, _cargar_mapa, run_connector
from opcua_server_sim import CyclotronModel, NODE_PATHS, crear_servidor


# ---------------- modelo del simulador ----------------

def test_modelo_rampa_y_meseta():
    m = CyclotronModel(corriente=40.0, seed=1)
    primera = m.step(1.0)                      # t=1 s: rampa ≈ 0
    assert primera["beam_current_ua"] < 5.0    # haz aún subiendo
    for _ in range(400):                       # t≈400 s: meseta
        ultima = m.step(1.0)
    assert 38.0 < ultima["beam_current_ua"] < 41.0
    assert 335.0 < ultima["target_pressure_psi"] < 355.0
    assert 10.0 < ultima["cooling_flow_lpm"] < 13.5
    assert ultima["beam_energy_mev"] == 16.5


def test_modelo_excursion_cae_caudal():
    m = CyclotronModel(corriente=40.0, excursion=True, periodo_min=1.0,
                       seed=1)
    min_caudal, max_presion = 99.0, 0.0
    for _ in range(60):                        # un ciclo completo (1 min)
        muestra = m.step(1.0)
        min_caudal = min(min_caudal, muestra["cooling_flow_lpm"])
        max_presion = max(max_presion, muestra["target_pressure_psi"])
    assert min_caudal < 9.0                    # fallo de enfriamiento
    assert max_presion > 355.0                 # consecuencia térmica


# ---------------- servidor + cliente OPC-UA ----------------

def _run(coro):
    return asyncio.run(coro)


def test_servidor_y_lectura_end_to_end():
    async def go():
        modelo = CyclotronModel(corriente=40.0, seed=1)
        server, nodos = await crear_servidor(14841, modelo)
        async with server:
            await nodos["beam_current_ua"].set_value(37.25)
            await nodos["target_pressure_psi"].set_value(345.1)
            await nodos["cooling_flow_lpm"].set_value(12.05)
            src = OpcUaSource("opc.tcp://localhost:14841/rpos",
                              _cargar_mapa(None))
            await src.connect()
            puntos = await src.read_sample("B-OPC")
            await src.close()
            return puntos

    puntos = _run(go())
    por_serie = {p["series"]: p["value"] for p in puntos}
    assert set(por_serie) == set(NODE_PATHS)
    assert por_serie["beam_current_ua"] == 37.25
    assert por_serie["target_pressure_psi"] == 345.1
    assert all(p["tags"]["batch_id"] == "B-OPC" for p in puntos)
    assert all(p["tags"]["source"] == "opcua" for p in puntos)


def test_run_connector_loop_completo(monkeypatch):
    enviados: list[dict] = []

    def _fake_flush(puntos, token):
        enviados.extend(puntos)
        return len(puntos)

    monkeypatch.setattr("opcua_connector._flush", _fake_flush)

    async def go():
        modelo = CyclotronModel(corriente=40.0, seed=1)
        server, nodos = await crear_servidor(14842, modelo)
        async with server:
            async def actualiza():
                for _ in range(30):
                    muestra = modelo.step(0.05)
                    for s, v in muestra.items():
                        await nodos[s].set_value(v)
                    await asyncio.sleep(0.05)
            tarea = asyncio.create_task(actualiza())
            n = await run_connector("opc.tcp://localhost:14842/rpos",
                                    _cargar_mapa(None), "B-OPC", "tok",
                                    intervalo=0.05, duracion_min=0.02)
            tarea.cancel()
            return n

    n = _run(go())
    assert n == len(enviados) > 0
    series = {p["series"] for p in enviados}
    assert series == set(NODE_PATHS)
    # a 20 Hz durante ~1.2 s → docenas de muestras por serie
    assert len(enviados) >= 20
