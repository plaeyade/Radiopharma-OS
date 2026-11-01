# Depuración 2026-10-31 (v3.17.0)

Estado previo completo: rama `archivo/pre-depuracion-2026-10-31` (c589352).

## Qué se corrigió

| Problema | Efecto | Corrección |
| --- | --- | --- |
| Pruebas de Yield Engine registraban tablas de stopping de prueba en `data/stopping/external` (versionado) | El manifiesto llegó a 85 tablas, 84 de pruebas (`ejecutado_en: "test"`, `agua_test`) y 84 CSV basura; la suite tardaba 33 s | `tests/conftest.py` redirige `YE_STOPPING_EXTERNAL` y `YE_CALIBRATION_STORE` a un temporal; manifiesto con la única tabla real (agua v1, NIST PSTAR); suite en 5,5 s |
| Pruebas de Process Service escribían en `data/costos/corridas.json` | +434 líneas por corrida | `RPOS_COSTOS_CORRIDAS` + `tests/conftest.py` |
| 158 rutas fijas `/mnt/agents/...` (entorno del agente que generó las fases) | 95 de 205 pruebas de pipelines fallaban fuera de ese entorno | Raíz única `RPOS_AGENTS_ROOT` (por defecto `/mnt/agents`); las pruebas ejecutaban los pipelines desde la copia `…/work/rpos25` y ahora desde este repo |
| Pruebas de fase sin evidencia | Fallos indistinguibles de errores reales | `pipelines/conftest.py`: raíz temporal; lo que falta bajo ella se OMITE con motivo; calificación de entorno (OQ/IQ, DWSIM) marcada; `RPOS_REQUIRE_EVIDENCIA=1` lo exige todo |
| Dependencias importadas y ausentes del lock | 18 pruebas con `ModuleNotFoundError` | `requirements-lock.txt` + `services/surrogate_service/requirements.txt`; Dockerfile de surrogate instala Tesseract (antes la imagen no podía extraer PDF/DOCX ni hacer OCR) |
| `out/*.log` versionados | Ruido en cada corrida | Fuera de git e ignorados |
| `nuclear_data_service/app/domain/mesh_volume_viz.py` | Sin importadores (F35) | Retirado |
| Orden de recolección: paquete `app` de otro servicio en `sys.modules` | `test_artifacts` fallaba sólo en suite completa | Purga de `app.*` antes de importar |

## Resultado

`make test`: 1.325 pasan, 0 fallan; 84 omitidas con motivo (evidencia externa o calificación de entorno).
Antes, fuera del entorno original: 101 + servicios con 21 fallos/errores y 95 en pipelines.

CI nuevo: `.github/workflows/ci.yml` (no había).

## Hallazgo abierto

F86 (`utilidades_completas_f86.py`) se rompe con `TypeError` si F85 no tiene resultados DWSIM
(runtime ausente); debería declarar «pendiente» como hacen las demás fases.

## Usar la evidencia real

```bash
export RPOS_AGENTS_ROOT=/ruta/a/la/raiz   # contiene work/evidencia_v072, upload/, work/sci_runtime …
RPOS_REQUIRE_EVIDENCIA=1 make test
```
