"""Dashboard operativo Streamlit (Informe 18.11, Fase 7; EDS 6.18).

Ejecución:  streamlit run dashboard/streamlit_app.py

Paneles (6.17/6.18):
  - Producción (Yield Engine, con optimización física);
  - Síntesis y QC Release (recomendación técnica 25.12);
  - Inventario con decaimiento y KPIs operativos/económicos;
  - Telemetría por lote (vía Telemetry Service — nunca el PLC
    directamente, 6.18);
  - Estado honesto de plataforma (solvers y runtimes).

El módulo es importable sin el runtime Streamlit (tests): toda la
lógica de datos vive en ``data_client``.
"""
from __future__ import annotations

import importlib.util

STREAMLIT_DISPONIBLE = importlib.util.find_spec("streamlit") is not None

PANELES = [
    {"id": "produccion", "titulo": "Producción (Physics Twin)",
     "fuente": "Yield Engine API"},
    {"id": "optimizacion", "titulo": "Optimización física (41.9)",
     "fuente": "Yield Engine API",
     "nota": "recomendación, nunca decisión automática"},
    {"id": "qc", "titulo": "QC Release (cap. 25)", "fuente": "QC Engine API",
     "nota": "recomendación técnica; la liberación final sigue el flujo "
             "organizativo (25.12)"},
    {"id": "inventario", "titulo": "Inventario con decaimiento",
     "fuente": "Process Service API"},
    {"id": "kpis", "titulo": "Indicadores operativos y económicos",
     "fuente": "Process Service API (38.12)"},
    {"id": "telemetria", "titulo": "Telemetría por lote",
     "fuente": "Telemetry Service (InfluxDB/SQLite)",
     "nota": "Streamlit no consulta directamente el PLC (6.18)"},
    {"id": "plataforma", "titulo": "Estado de plataforma",
     "fuente": "health de los servicios",
     "nota": "estado honesto de solvers y runtimes"},
    # -------------------------------------------------- fase 4: producción
    # clínica
    {"id": "conectores", "titulo": "Conectores externos (fases 1-2)",
     "fuente": "status real de NDS/TEL/PROCESS/SURROGATE",
     "nota": "marcadores honestos no_configurado/fallo_conexion visibles"},
    {"id": "pq", "titulo": "Calificación PQ (14.9)",
     "fuente": "QC Engine — ejecutor PQ real (fase 3)"},
    {"id": "produccion_clinica", "titulo": "Producción clínica (lotes/eBR)",
     "fuente": "Data Lake API",
     "nota": "requiere JWT real; el dashboard nunca elude la "
             "autenticación (cap. 47/48)"},
]


def main() -> None:  # pragma: no cover - requiere runtime Streamlit
    if not STREAMLIT_DISPONIBLE:
        raise RuntimeError(
            "runtime Streamlit no instalado: el dashboard se despliega "
            "con docker-compose.dashboards.yml (Fase 7); su lógica de "
            "datos se valida sin runtime en pipelines/test_dashboards.py")
    import streamlit as st

    from dashboard import data_client as dc

    st.set_page_config(page_title="Radiopharma OS — Dashboard",
                       layout="wide")
    st.title("Radiopharma OS — Dashboard operativo (Fase 7)")
    st.caption("Datos desde las APIs de los microservicios; Streamlit no "
               "consulta directamente el PLC (EDS 6.18).")

    tabs = st.tabs([p["titulo"] for p in PANELES])

    with tabs[0]:
        st.header("Producción — Yield Engine")
        c1, c2, c3 = st.columns(3)
        e = c1.number_input("Energía (MeV)", 4.0, 18.0, 16.5)
        i = c2.number_input("Corriente (µA)", 1.0, 100.0, 37.0)
        t = c3.number_input("Irradiación (min)", 1.0, 480.0, 60.0)
        if st.button("Calcular producción"):
            r = dc.produccion_ye("o18_p_n_f18", "h2_18o", e, i, t)
            st.metric("Actividad EOB", f"{r['eob_activity_gbq']:.2f} GBq")
            st.json(r)

    with tabs[1]:
        st.header("Optimización física (recomendación, 41.9)")
        p = st.number_input("Potencia máxima del haz (W)", 100.0, 3000.0,
                            1500.0)
        if st.button("Optimizar"):
            st.json(dc.optimizacion_ye("o18_p_n_f18", "h2_18o", p))

    with tabs[2]:
        st.header("QC Release (cap. 25)")
        st.info("La recomendación es técnica; la liberación final sigue "
                "el flujo organizativo (25.12).")

    with tabs[3]:
        st.header("Inventario")
        if st.button("Refrescar lotes"):
            st.dataframe(dc.inventario_lotes())

    with tabs[4]:
        st.header("Indicadores")
        col1, col2 = st.columns(2)
        if col1.button("KPIs operativos"):
            st.json(dc.kpis_operativos())
        precio = col2.number_input("Precio por dosis (EUR)", 0.0, 1000.0,
                                   300.0)
        if col2.button("KPIs económicos"):
            st.json(dc.kpis_economicos(precio))

    with tabs[5]:
        st.header("Telemetría por lote")
        batch = st.text_input("batch_id", "")
        if batch and st.button("Resumen del lote"):
            st.json(dc.telemetria_batch(batch))

    with tabs[6]:
        st.header("Estado honesto de plataforma")
        st.json(dc.estado_plataforma())

    with tabs[7]:
        st.header("Conectores externos — estado real")
        st.caption("Marcadores honestos visibles: no_configurado / "
                   "fallo_conexion / sin_runtime.")
        if st.button("Refrescar conectores"):
            for nombre, res in dc.estado_conectores().items():
                with st.expander(nombre, expanded=not res["ok"]):
                    st.json(res)

    with tabs[8]:
        st.header("Calificación PQ — Informe 14.9")
        if st.button("Protocolos PQ"):
            st.json(dc.protocolos_pq())
        comp = st.text_input("componente_id", "plataforma_base")
        if comp and st.button("Estado de calificación"):
            st.json(dc.estado_calificacion(comp))

    with tabs[9]:
        st.header("Producción clínica — lotes y eBR")
        st.caption("Requiere JWT real del auth-service (47.10).")
        token = st.text_input("JWT", "", type="password")
        if st.button("Listar lotes clínicos"):
            st.json(dc.lotes_clinicos(token))
        batch = st.text_input("batch_id para verificar eBR", "")
        if batch and st.button("Verificar eBR"):
            st.json(dc.verificar_ebr(batch, token))


if __name__ == "__main__":  # pragma: no cover
    main()
