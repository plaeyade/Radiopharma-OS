"""
Tests del backend InfluxDB 2.x con un servidor simulado (MockTransport):
verifica el protocolo de línea de escritura y el parseo del CSV de Flux.
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone

import httpx

from app.domain.entities import TelemetryPoint
from app.infrastructure.influx.influx_telemetry_store import (
    InfluxTelemetryStore, _parse_csv)

T0 = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- servidor falso
class FakeInflux:
    """InfluxDB mínimo en memoria: write (línea) + query (Flux -> CSV)."""

    def __init__(self):
        self.lines: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "pass"})
        if request.url.path == "/api/v2/write":
            body = request.content.decode()
            self.lines.extend([ln for ln in body.splitlines() if ln])
            return httpx.Response(204)
        if request.url.path == "/api/v2/query":
            flux = json.loads(request.read().decode())["query"]
            if "schema.measurements" in flux:
                return httpx.Response(200, text=self._csv_measurements())
            m_serie = re.search(r'r\._measurement == "([^"]+)"', flux)
            m_batch = re.search(r'r\.batch_id == "([^"]+)"', flux)
            return httpx.Response(200, text=self._csv_data(
                m_serie.group(1) if m_serie else None,
                m_batch.group(1) if m_batch else None))
        return httpx.Response(404)

    # ---- datos guardados como líneas: serie,tag=v value=X ts_ms
    def _registros(self):
        regs = []
        for ln in self.lines:
            head, rest = ln.rsplit(" value=", 1)
            valor, ts_ms = rest.rsplit(" ", 1)
            partes = head.split(",", 1)
            serie = (partes[0].replace("\\,", ",").replace("\\ ", " ")
                     .replace("\\=", "="))
            tags = {}
            if len(partes) > 1:
                for kv in partes[1].split(","):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        tags[k.replace("\\=", "=")] = v.replace("\\=", "=")
            regs.append((serie, tags, float(valor), int(ts_ms)))
        return regs

    _CSV_HEAD = (
        "#group,false,false,true,true,false,false,true,true,true\n"
        "#datatype,string,long,dateTime:RFC3339,double,string,string,string\n"
        "#default,_result,,,,,,\n"
        ",result,table,_time,_value,_field,_measurement,batch_id\n")

    def _csv_data(self, serie, batch):
        filas = []
        for s, tags, valor, ts_ms in self._registros():
            if serie and s != serie:
                continue
            if batch and tags.get("batch_id") != batch:
                continue
            ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            filas.append(f",,0,{ts.isoformat().replace('+00:00', 'Z')},"
                         f"{valor},value,{s},{tags.get('batch_id', '')}")
        return self._CSV_HEAD + "\n".join(filas) + "\n"

    def _csv_measurements(self):
        series = sorted({s for s, *_ in self._registros()})
        return ("#group,false,false\n#datatype,string,long\n"
                "#default,_result,\n,result,table,_value\n"
                + "".join(f",,0,{s}\n" for s in series))


def _store(fake: FakeInflux) -> InfluxTelemetryStore:
    return InfluxTelemetryStore(
        "http://influx-falso", "tok", "org", "telemetry",
        transport=httpx.MockTransport(fake.handler))


# ---------------------------------------------------------------- tests
def test_write_protocolo_de_linea():
    fake = FakeInflux()
    store = _store(fake)
    p = TelemetryPoint(series="beam_current_ua", ts=T0, value=40.25,
                       tags=(("batch_id", "B-1"),))
    n = run(store.write([p]))
    assert n == 1
    esperado_ts = int(T0.timestamp() * 1000)
    assert fake.lines == [
        f"beam_current_ua,batch_id=B-1 value=40.25 {esperado_ts}"]


def test_write_escapa_espacios_y_comas():
    fake = FakeInflux()
    store = _store(fake)
    p = TelemetryPoint(series="cooling flow", ts=T0, value=1.0,
                       tags=(("zone", "hall 1, norte"),))
    run(store.write([p]))
    assert fake.lines[0].startswith(
        "cooling\\ flow,zone=hall\\ 1\\,\\ norte value=1.0 ")


def test_query_parsea_csv_flux():
    fake = FakeInflux()
    store = _store(fake)
    pts = [TelemetryPoint(series="beam_current_ua",
                          ts=T0 + timedelta(minutes=i), value=40.0 + i,
                          tags=(("batch_id", "B-9"),)) for i in range(3)]
    pts.append(TelemetryPoint(series="target_pressure_psi", ts=T0, value=331.0,
                              tags=(("batch_id", "B-9"),)))
    run(store.write(pts))

    todo = run(store.query())
    assert len(todo) == 4
    assert todo[0].ts <= todo[-1].ts          # ordenado por tiempo

    solo_serie = run(store.query(series="beam_current_ua"))
    assert len(solo_serie) == 3
    assert solo_serie[0].tags_dict()["batch_id"] == "B-9"

    con_tag = run(store.query(tags={"batch_id": "B-9"}))
    assert len(con_tag) == 4
    assert run(store.count(series="target_pressure_psi")) == 1


def test_list_series_desde_schema():
    fake = FakeInflux()
    store = _store(fake)
    run(store.write([
        TelemetryPoint(series="b_series", ts=T0, value=1.0),
        TelemetryPoint(series="a_series", ts=T0, value=2.0)]))
    assert run(store.list_series()) == ["a_series", "b_series"]


def test_parse_csv_vacio():
    assert _parse_csv("#solo anotaciones\n") == []
