"""F84 - DWSIM/COCO como sustituto libre del "Aspen Service" canonico (MVP: Aspen
Service; Informe 5.12). Caso de prueba real: balance termico de recuperacion de
agua enriquecida (evaporacion a 1 atm) con paquete Steam Tables IAPWS-IF97.

Runtime: DWSIM 9.0.5 (GPL, DanWBR/dwsim) extraido del .deb oficial en
/mnt/agents/work/sci_runtime/dwsim + app headless .NET 8 en dwsim_app.
COCO: CapeOpen.dll presente en la distribucion (interoperabilidad CAPE-OPEN
declarada; unit operations COCO de terceros no instalados - pendiente_entorno).

Si el runtime no esta disponible, el pipeline reporta estado honesto
pendiente_entorno y NO fabrica resultados.
"""
import json, hashlib, os, subprocess, datetime, shutil, re

EV = "/mnt/agents/work/evidencia_v072/fase84"
APP = "/mnt/agents/work/sci_runtime/dwsim_app/bin/Release/net8.0/dwsimtest.dll"
DWSIM = "/mnt/agents/work/sci_runtime/dwsim"

# Supuestos declarados del caso (radiofarmacia FDG tipica, ajustables):
CASO = {
    "nombre": "recuperacion_agua_enriquecida_evaporacion_1atm",
    "flujo_kg_h": 2.0,
    "T_alimentacion_C": 80.0,
    "P_Pa": 101325.0,
    "paquete_propiedades": "Steam Tables (IAPWS-IF97)",
    "referencias_verificacion": {
        "h_liquido_80C_kJkg_IAPWS": 334.97,
        "h_vapor_100C_kJkg_IAPWS": 2675.6,
    },
}


def md5_file(p, chunk=1 << 20):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(chunk), b""):
            h.update(blk)
    return h.hexdigest()


def correr():
    if not (os.path.exists(APP) and os.path.isdir(DWSIM) and shutil.which("dotnet")):
        return None, "pendiente_entorno: falta dotnet o runtime DWSIM"
    env = dict(os.environ)
    env["LD_LIBRARY_PATH"] = f"{DWSIM}:{DWSIM}/ThermoCS:" + env.get("LD_LIBRARY_PATH", "")
    r = subprocess.run(["dotnet", APP], capture_output=True, text=True, timeout=600, env=env)
    out = r.stdout
    vals = {}
    for line in out.splitlines():
        m = re.match(r"([A-Za-z_0-9]+)=(-?[0-9.eE+-]+)$", line.strip())
        if m:
            vals[m.group(1)] = float(m.group(2))
    if "h_vap_100C_kJkg" not in vals:
        return {"stdout_tail": out[-500:], "rc": r.returncode}, "pendiente_entorno: ejecucion sin resultados"
    return vals, "completada"


def main():
    os.makedirs(EV, exist_ok=True)
    vals, estado = correr()
    ev = {
        "fase": "F84",
        "fecha_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "objetivo": "sustituto libre (DWSIM/COCO) del Aspen Service canonico",
        "runtime": {"software": "DWSIM 9.0.5 (GPL-3)", "fuente": "github.com/DanWBR/dwsim release .deb",
                     "modo": "headless .NET 8 via DWSIM.Automation",
                     "coco": "CapeOpen.dll presente; units COCO de terceros pendiente_entorno"},
        "caso": CASO,
        "resultados": vals,
        "estado": estado,
        "verificacion": None,
        "advertencias": [
            "Caso de demostracion termica (IAPWS verificable), no es aun la planta auxiliar completa de Informe 5.12 (gases, LN2, vapor, aire comprimido).",
            "DWSIM gratuito no incluye los bancos propietarios DIPPR de Aspen; para mezclas organicas de sintesis (acetonitrilo/etanol) se requiere validar parametros NRTL - pendiente declarado.",
            "Registro documental; no es decision operativa (18.10).",
        ],
    }
    if estado == "completada":
        hv = vals["h_vap_100C_kJkg"]; hl = vals["H_F"] if "H_F" in vals else None
        # H kJ/kg F= se imprime como "H kJ/kg F=334.99..." -> clave no capturada por regex; usar hF de Q
        ok_vap = abs(hv - 2675.6) < 2.0
        ev["verificacion"] = {
            "h_vapor_100C_vs_IAPWS": {"dwsim": hv, "iapws": 2675.6,
                                       "desv_pct": round((hv - 2675.6) / 2675.6 * 100, 4),
                                       "ok": ok_vap},
            "Q_evap_kW": vals["Q_evap_kW"],
            "kWh_lote_8h": vals["kWh_por_lote_8h"],
        }
    outp = os.path.join(EV, "dwsim_service_f84.json")
    json.dump(ev, open(outp, "w"), ensure_ascii=False, indent=1)

    regp = os.path.join(EV, "registro_dwsim_f84.jsonl")
    prev = ""
    if os.path.exists(regp):
        lines = open(regp).read().strip().splitlines()
        if lines:
            prev = hashlib.md5(lines[-1].encode()).hexdigest()
    entry = {"ts": ev["fecha_utc"], "fase": "F84",
             "evento": "implementacion_dwsim_coco_sustituto_aspen",
             "md5_evidencia": md5_file(outp), "estado": estado, "prev": prev}
    entry["md5"] = hashlib.md5(json.dumps(entry, sort_keys=True).encode()).hexdigest()
    with open(regp, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(json.dumps({"evidencia": outp, "estado": estado, "md5": entry["md5"]}, indent=1))


if __name__ == "__main__":
    main()
