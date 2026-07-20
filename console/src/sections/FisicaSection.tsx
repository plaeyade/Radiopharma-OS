import { useEffect, useMemo, useState } from "react";
import { Atom, Flame, Grid3X3, Thermometer } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ConsoleConfig } from "@/lib/console-data";
import { burnup2d, elmerCompare, elmerStatus, thermalTarget, REACTIONS, TARGET_ES,
         type Burnup2DResult, type ElmerStatus, type ThermalResult } from "@/lib/actions";

interface Props { cfg: ConsoleConfig }

function Num({ label, value, onChange, step = "any", hint }: {
  label: string; value: string; onChange: (v: string) => void; step?: string; hint?: string;
}) {
  return (
    <div className="space-y-1">
      <Label className="text-xs text-slate-400">{label}</Label>
      <Input value={value} onChange={(e) => onChange(e.target.value)}
             type="number" step={step} className="h-8 bg-slate-900/60" />
      {hint && <p className="text-[10px] text-slate-500">{hint}</p>}
    </div>
  );
}

function Stat({ label, value, sub, tone = "text-slate-100" }: {
  label: string; value: string; sub?: string; tone?: string;
}) {
  return (
    <div className="rounded-md border border-slate-800 bg-slate-900/60 p-3">
      <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`text-lg font-semibold ${tone}`}>{value}</p>
      {sub && <p className="text-[10px] text-slate-500">{sub}</p>}
    </div>
  );
}

/** Physics Twin: Burnup radial 2D + Thermal Engine + acoplamiento Elmer FEM. */
export default function FisicaSection({ cfg }: Props) {
  // ---- Burnup 2D
  const [rxnId, setRxnId] = useState("o18_p_n_f18");
  const [targetId, setTargetId] = useState("h2_18o");
  const [energy, setEnergy] = useState("18");
  const [current, setCurrent] = useState("75");
  const [time, setTime] = useState("120");
  const [spot, setSpot] = useState("0.5");
  const [sigma, setSigma] = useState("0.1");
  const [rings, setRings] = useState("20");
  const [b2d, setB2d] = useState<Burnup2DResult | null>(null);
  const [busyB, setBusyB] = useState(false);

  // ---- Thermal
  const [tCurrent, setTCurrent] = useState("40");
  const [tThickness, setTThickness] = useState("0.005");
  const [tK, setTK] = useState("0.11");
  const [tH, setTH] = useState("10");
  const [tCool, setTCool] = useState("293.15");
  const [tLimit, setTLimit] = useState("473.15");
  const [tSigma, setTSigma] = useState("");
  const [thermal, setThermal] = useState<ThermalResult | null>(null);
  const [busyT, setBusyT] = useState(false);

  // ---- Elmer
  const [elmer, setElmer] = useState<ElmerStatus | null>(null);

  const rxn = REACTIONS.find((r) => r.id === rxnId) ?? REACTIONS[0];
  const targets = rxn.targets;

  useEffect(() => {
    elmerStatus(cfg).then(setElmer).catch(() => setElmer(null));
  }, [cfg]);

  useEffect(() => {
    if (!targets.includes(targetId)) setTargetId(targets[0]);
  }, [rxnId]); // eslint-disable-line react-hooks/exhaustive-deps

  const chartData = useMemo(() => (b2d?.rings ?? []).map((r) => ({
    r: +r.r_mean_cm.toFixed(3),
    deplecion: +(r.depletion_fraction * 100).toFixed(4),
    flujo: +r.flux_rel.toFixed(4),
  })), [b2d]);

  async function doBurnup() {
    setBusyB(true);
    try {
      const res = await burnup2d(cfg, {
        reaction_id: rxnId, target_id: targetId,
        beam_energy_mev: +energy, current_ua: +current,
        irradiation_time_min: +time, beam_spot_cm2: +spot,
        beam_sigma_cm: +sigma, n_rings: Math.max(1, Math.round(+rings)),
      });
      setB2d(res);
    } catch (e) {
      toast.error("Burnup 2D: " + (e instanceof Error ? e.message : "error"));
    } finally { setBusyB(false); }
  }

  function thermalInput() {
    return {
      beam_energy_mev: +energy, current_ua: +tCurrent, beam_spot_cm2: +spot,
      target_thickness_cm: +tThickness, conductivity_w_cm_k: +tK,
      film_coeff_w_cm2_k: +tH, coolant_temp_k: +tCool, t_limit_k: +tLimit,
      beam_sigma_cm: tSigma.trim() === "" ? null : +tSigma,
    };
  }

  async function doThermal() {
    setBusyT(true);
    try {
      setThermal(await thermalTarget(cfg, thermalInput()));
    } catch (e) {
      toast.error("Térmico: " + (e instanceof Error ? e.message : "error"));
    } finally { setBusyT(false); }
  }

  async function doElmerCompare() {
    try {
      const res = await elmerCompare(cfg, thermalInput());
      toast.success(`FEM: pico ${res.t_peak_fem_k.toFixed(1)} K vs reducido ${res.t_peak_reduced_k.toFixed(1)} K`);
    } catch (e) {
      toast.error("Elmer FEM: " + (e instanceof Error ? e.message : "no disponible"));
    }
  }

  const fmt = (v: number, d = 3) => v.toLocaleString("es-ES", { maximumFractionDigits: d });

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {/* --------------------------------------------- Burnup radial 2D */}
      <Card className="border-slate-800 bg-slate-950/60">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Atom className="h-4 w-4 text-cyan-400" /> Burnup radial 2D — haz gaussiano
            <Badge variant="outline" className="ml-auto text-[10px]">v0.30.0</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label className="text-xs text-slate-400">Reacción</Label>
              <Select value={rxnId} onValueChange={setRxnId}>
                <SelectTrigger className="h-8 bg-slate-900/60"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {REACTIONS.map((r) => (
                    <SelectItem key={r.id} value={r.id}>{r.notation}</SelectItem>))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs text-slate-400">Blanco</Label>
              <Select value={targetId} onValueChange={setTargetId}>
                <SelectTrigger className="h-8 bg-slate-900/60"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {targets.map((t) => (
                    <SelectItem key={t} value={t}>{TARGET_ES[t] ?? t}</SelectItem>))}
                </SelectContent>
              </Select>
            </div>
            <Num label="Energía (MeV)" value={energy} onChange={setEnergy} />
            <Num label="Corriente (µA)" value={current} onChange={setCurrent} />
            <Num label="Irradiación (min)" value={time} onChange={setTime} />
            <Num label="Spot (cm²)" value={spot} onChange={setSpot} />
            <Num label="σ haz (cm)" value={sigma} onChange={setSigma}
                 hint="σ ≫ R → perfil plano (límite 1D)" />
            <Num label="Anillos" value={rings} onChange={setRings} step="1" />
          </div>
          <Button onClick={doBurnup} disabled={busyB} size="sm"
                  className="bg-cyan-600 hover:bg-cyan-500">
            {busyB ? "Calculando…" : "Calcular depleción 2D"}
          </Button>
          {b2d && (
            <>
              <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                <Stat label="EOB ideal" value={`${fmt(b2d.eob_ideal_gbq)} GBq`} sub="sin quemado" />
                <Stat label="EOB 1D" value={`${fmt(b2d.eob_1d_gbq)} GBq`} sub="flujo uniforme" />
                <Stat label="EOB 2D" value={`${fmt(b2d.eob_2d_gbq)} GBq`}
                      sub="gaussiano radial" tone="text-cyan-300" />
                <Stat label="Corrección radial" value={`${fmt(b2d.loss_vs_1d_gbq, 4)} GBq`}
                      sub={`pico ×${fmt(b2d.peak_factor, 2)}`} tone="text-amber-300" />
              </div>
              <div className="h-44">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartData} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="r" tick={{ fontSize: 10, fill: "#64748b" }}
                           label={{ value: "r (cm)", position: "insideBottomRight", fontSize: 10, fill: "#64748b" }} />
                    <YAxis yAxisId="d" tick={{ fontSize: 10, fill: "#64748b" }}
                           label={{ value: "depl. %", angle: -90, position: "insideLeft", fontSize: 10, fill: "#64748b" }} />
                    <YAxis yAxisId="f" orientation="right" domain={[0, 1]} hide />
                    <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", fontSize: 11 }} />
                    <Bar yAxisId="d" dataKey="deplecion" fill="#22d3ee" radius={[2, 2, 0, 0]} name="Depleción %" />
                    <Line yAxisId="f" dataKey="flujo" stroke="#a78bfa" dot={false} strokeWidth={1.5} name="φ/φₚᵢₖₒ" />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
              <p className="text-[10px] text-slate-500">
                Depleción máx. en el eje {(b2d.depletion_max * 100).toFixed(3)} % ·
                ponderada {(b2d.depletion_weighted * 100).toFixed(3)} % ·
                σ_b,eff {fmt(b2d.burnup_xs_eff_mb, 1)} mb · {b2d.model}
              </p>
            </>
          )}
        </CardContent>
      </Card>

      {/* --------------------------------------------- Thermal + Elmer */}
      <div className="space-y-4">
        <Card className="border-slate-800 bg-slate-950/60">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Thermometer className="h-4 w-4 text-amber-400" /> Thermal Engine reducido
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <Num label="Corriente (µA)" value={tCurrent} onChange={setTCurrent}
                   hint={`energía y spot del panel 2D (${energy} MeV, ${spot} cm²)`} />
              <Num label="Espesor (cm)" value={tThickness} onChange={setTThickness}
                   hint="ventana Havar: 0.005" />
              <Num label="k (W/cm·K)" value={tK} onChange={setTK}
                   hint="Havar 0.11 · agua 0.006" />
              <Num label="h (W/cm²·K)" value={tH} onChange={setTH}
                   hint="chorro de agua: 5-20" />
              <Num label="T refrigerante (K)" value={tCool} onChange={setTCool} />
              <Num label="T límite (K)" value={tLimit} onChange={setTLimit} />
              <Num label="σ haz (cm, vacío = uniforme)" value={tSigma} onChange={setTSigma} />
            </div>
            <div className="flex gap-2">
              <Button onClick={doThermal} disabled={busyT} size="sm"
                      className="bg-amber-600 hover:bg-amber-500">
                {busyT ? "Calculando…" : "Evaluar margen térmico"}
              </Button>
            </div>
            {thermal && (
              <>
                <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                  <Stat label="Potencia haz" value={`${fmt(thermal.beam_power_w, 0)} W`} />
                  <Stat label="q'' pico" value={`${fmt(thermal.heat_flux_peak_w_cm2, 0)} W/cm²`}
                        sub={`×${fmt(thermal.peak_factor, 2)} del medio`} />
                  <Stat label="T pico" value={`${fmt(thermal.t_peak_k, 1)} K`}
                        sub={`margen ${fmt(thermal.margin_k, 1)} K`}
                        tone={thermal.within_limit ? "text-emerald-300" : "text-red-400"} />
                  <Stat label="Corriente máx." value={`${fmt(thermal.max_current_ua, 1)} µA`}
                        sub="satura el límite" tone="text-cyan-300" />
                </div>
                <p className={`text-xs ${thermal.within_limit ? "text-emerald-400" : "text-red-400"}`}>
                  {thermal.within_limit
                    ? `Dentro del límite térmico (margen ${fmt(thermal.margin_k, 1)} K).`
                    : `Fuera del límite térmico por ${fmt(-thermal.margin_k, 1)} K — reduce corriente o mejora h.`}
                  {" "}ΔT conducción {fmt(thermal.delta_t_conduction_k, 1)} K ·
                  película {fmt(thermal.delta_t_film_k, 1)} K.
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-slate-950/60">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Grid3X3 className="h-4 w-4 text-violet-400" /> Acoplamiento Elmer FEM
              {elmer && (
                <Badge variant="outline"
                       className={`ml-auto text-[10px] ${elmer.available ? "text-emerald-300" : "text-amber-300"}`}>
                  {elmer.available ? "disponible" : "no instalado"}
                </Badge>)}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-xs text-slate-400">
              {elmer
                ? <>Solver: <span className="text-slate-200">{elmer.solver}</span> · cmd{" "}
                   <code className="text-cyan-300">{elmer.cmd}</code>
                   {elmer.version ? ` · ${elmer.version}` : ""}</>
                : "Consultando estado…"}
            </p>
            <p className="text-[11px] leading-relaxed text-slate-500">
              ElmerFEM resuelve la ecuación del calor 2D axisimétrica del blanco con la
              fuente gaussiana exacta (∫q'''dV = P) y la compara con el modelo reducido
              analítico. Sin binario (<code>ELMER_CMD</code>) el endpoint responde 503
              de forma honesta — nunca se simula un resultado FEM.
            </p>
            <Button onClick={doElmerCompare} size="sm" variant="outline"
                    className="border-violet-700 text-violet-300 hover:bg-violet-950"
                    disabled={!elmer?.available}>
              <Flame className="mr-1.5 h-3.5 w-3.5" /> Comparar FEM vs reducido
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
