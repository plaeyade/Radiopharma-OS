import { useState } from "react";
import { Play, ShieldAlert, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { checkDeviations, registerDeviation, simulateRun,
         type DeviationCheckResult } from "@/lib/actions";
import type { ConsoleConfig, ConsoleData, TelemetrySeries } from "@/lib/console-data";
import { roleRank, type Session } from "@/lib/session";

const COLORES: Record<string, string> = {
  beam_current_ua: "#22d3ee",
  target_pressure_psi: "#f59e0b",
  cooling_flow_lpm: "#34d399",
};

const NOMBRE: Record<string, string> = {
  beam_current_ua: "Corriente de haz",
  target_pressure_psi: "Presión de blanco",
  cooling_flow_lpm: "Caudal de enfriamiento",
};

interface Props {
  data: ConsoleData; cfg: ConsoleConfig; session: Session | null;
  selected: string; onSelect: (id: string) => void; onChanged: () => void;
}

export default function TelemetrySection({ data, cfg, session, selected, onSelect, onChanged }: Props) {
  const [busy, setBusy] = useState(false);
  const [conExcursion, setConExcursion] = useState(false);
  const [checking, setChecking] = useState(false);
  const [registrando, setRegistrando] = useState(false);
  const [resultado, setResultado] = useState<DeviationCheckResult | null>(null);
  const batch = data.batches.find((x) => x.batch_id === selected) ?? data.batches[0];
  const series: TelemetrySeries[] = (batch && data.telemetry[batch.batch_id]) || [];
  const stats = (batch && data.telemetry_stats[batch.batch_id]) || [];
  const operativo = data.mode === "live" && session && roleRank(session.role) >= 1;

  const simular = async () => {
    if (!batch) return;
    setBusy(true);
    try {
      const n = await simulateRun(cfg, cfg.token, batch.batch_id,
                                  batch.beam.irradiation_time_min,
                                  batch.beam.current_ua, conExcursion);
      toast.success(`Corrida simulada: ${n} puntos ingeridos`
                    + (conExcursion ? " (con excursión de enfriamiento)" : ""));
      setResultado(null);
      onChanged();
    } catch (e) {
      toast.error(`Error: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const verificar = async () => {
    if (!batch) return;
    setChecking(true);
    try {
      const r = await checkDeviations(cfg, cfg.token, batch.batch_id);
      setResultado(r);
      if (r.clean) toast.success("Sin desviaciones de proceso en la corrida");
      else toast.warning(`${r.events.length} desviación(es) de proceso detectada(s)`);
    } catch (e) {
      toast.error(`Error: ${(e as Error).message}`);
    } finally {
      setChecking(false);
    }
  };

  const registrarEnDl = async () => {
    if (!batch || !resultado || resultado.events.length === 0) return;
    setRegistrando(true);
    try {
      for (const ev of resultado.events) {
        await registerDeviation(cfg, cfg.token, batch.batch_id, ev.description);
      }
      toast.success(`${resultado.events.length} evento(s) registrados en el Data Lake — `
                    + "quedan en la pista de auditoría del eBR");
      onChanged();
    } catch (e) {
      toast.error(`Error: ${(e as Error).message}`);
    } finally {
      setRegistrando(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="text-sm text-slate-400">Lote:</span>
        <Select value={batch?.batch_id} onValueChange={onSelect}>
          <SelectTrigger className="w-72 border-slate-700 bg-[#0d1420] font-mono text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="border-slate-700 bg-[#0d1420]">
            {data.batches.map((x) => (
              <SelectItem key={x.batch_id} value={x.batch_id} className="font-mono text-xs">
                {x.batch_id} · {x.product_nuclide}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="flex-1" />
        <label className="flex cursor-pointer items-center gap-1.5 text-xs text-slate-400"
               title="Inyecta un fallo de enfriamiento al 60-66 % de la corrida (para probar la detección de desviaciones)">
          <input type="checkbox" checked={conExcursion}
                 onChange={(e) => setConExcursion(e.target.checked)}
                 className="accent-amber-500" />
          con excursión
        </label>
        <Button size="sm" onClick={() => void simular()} disabled={!operativo || busy}
                title={!operativo ? "Requiere modo en vivo + sesión" :
                       "Genera la corrida sintética con los parámetros del lote"}
                className="bg-cyan-600 text-white hover:bg-cyan-500 disabled:opacity-40">
          <Play className="mr-1 h-3.5 w-3.5" />
          {busy ? "Simulando…" : "Simular corrida"}
        </Button>
        <Button size="sm" variant="outline" onClick={() => void verificar()}
                disabled={!operativo || checking || series.length === 0}
                title="Evalúa la corrida contra los límites de proceso (pack cyclotron_generic)"
                className="border-slate-700 text-slate-300 hover:bg-slate-800 disabled:opacity-40">
          {checking ? "Evaluando…" : "Verificar desviaciones"}
        </Button>
      </div>

      {resultado && (
        <Card className={resultado.clean
          ? "border-emerald-900/60 bg-emerald-950/20"
          : "border-amber-900/60 bg-amber-950/20"}>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              {resultado.clean
                ? <><ShieldCheck className="h-4 w-4 text-emerald-400" />
                    <span className="text-emerald-300">Corrida sin desviaciones de proceso</span></>
                : <><ShieldAlert className="h-4 w-4 text-amber-400" />
                    <span className="text-amber-300">
                      {resultado.events.length} desviación(es) de proceso detectada(s)
                    </span></>}
              <Badge variant="outline" className="ml-2 border-slate-700 text-xs text-slate-400">
                pack {resultado.pack} · {resultado.evaluated_points} puntos evaluados
              </Badge>
              {!resultado.clean && (
                <Button size="sm" className="ml-auto bg-amber-600 text-white hover:bg-amber-500"
                        disabled={registrando} onClick={() => void registrarEnDl()}
                        title="Registra cada desviación como evento de auditoría del lote (append-only, ALCOA+)">
                  {registrando ? "Registrando…" : "Registrar en Data Lake (eBR)"}
                </Button>
              )}
            </CardTitle>
          </CardHeader>
          {!resultado.clean && (
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow className="border-slate-800">
                    <TableHead>Serie</TableHead><TableHead>Lado</TableHead>
                    <TableHead>Extremo</TableHead><TableHead>Límite</TableHead>
                    <TableHead>Puntos</TableHead><TableHead>Inicio</TableHead>
                    <TableHead>Fin</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {resultado.events.map((ev, i) => (
                    <TableRow key={i} className="border-slate-800">
                      <TableCell style={{ color: COLORES[ev.series] ?? "#22d3ee" }}>
                        {NOMBRE[ev.series] ?? ev.series}
                      </TableCell>
                      <TableCell>{ev.side === "low" ? "▼ bajo" : "▲ alto"}</TableCell>
                      <TableCell>{ev.extreme_value.toFixed(2)} {ev.unit}</TableCell>
                      <TableCell>{ev.limit} {ev.unit}</TableCell>
                      <TableCell>{ev.n_points}</TableCell>
                      <TableCell className="text-xs text-slate-400">
                        {new Date(ev.started_at).toLocaleTimeString()}</TableCell>
                      <TableCell className="text-xs text-slate-400">
                        {new Date(ev.ended_at).toLocaleTimeString()}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <p className="mt-2 text-xs text-slate-500">
                GMP: las desviaciones de proceso deben documentarse. Al registrarlas
                quedan en la pista de auditoría del lote (visibles en el eBR y su
                PDF/A) con actor y sello de tiempo de servidor.
              </p>
            </CardContent>
          )}
        </Card>
      )}

      {series.length === 0 ? (
        <Card className="border-slate-800 bg-[#0d1420]">
          <CardContent className="py-10 text-center text-slate-500">
            Sin telemetría registrada para este lote. En producción llega del
            Operational Twin (InfluxDB); en vivo, usa «Simular corrida».
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-3">
            {series.map((s) => (
              <Card key={s.series} className="border-slate-800 bg-[#0d1420]">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-slate-300">
                    {NOMBRE[s.series] ?? s.series}
                    <span className="ml-1 text-xs text-slate-500">({s.unit})</span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={180}>
                    <LineChart data={s.points} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
                      <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
                      <XAxis dataKey="t" stroke="#475569" fontSize={10}
                             tickFormatter={(v) => `${v}m`} />
                      <YAxis stroke="#475569" fontSize={10} domain={["auto", "auto"]} />
                      <Tooltip
                        contentStyle={{ background: "#0d1420", border: "1px solid #1e293b", fontSize: 12 }}
                        labelFormatter={(v) => `t = ${v} min`}
                        formatter={(v) => [`${v} ${s.unit}`, NOMBRE[s.series] ?? s.series]} />
                      <Line type="monotone" dataKey="v" dot={false}
                            stroke={COLORES[s.series] ?? "#22d3ee"} strokeWidth={1.8} />
                    </LineChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card className="border-slate-800 bg-[#0d1420]">
            <CardHeader><CardTitle className="text-sm text-slate-300">Resumen estadístico de la corrida</CardTitle></CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow className="border-slate-800">
                    <TableHead>Serie</TableHead><TableHead>Puntos</TableHead>
                    <TableHead>Media</TableHead><TableHead>Mín</TableHead>
                    <TableHead>Máx</TableHead><TableHead>σ</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {stats.map((s) => (
                    <TableRow key={s.series} className="border-slate-800">
                      <TableCell style={{ color: COLORES[s.series] ?? "#22d3ee" }}>
                        {NOMBRE[s.series] ?? s.series}
                      </TableCell>
                      <TableCell>{s.count}</TableCell>
                      <TableCell>{s.mean.toFixed(2)}</TableCell>
                      <TableCell>{s.minimum.toFixed(2)}</TableCell>
                      <TableCell>{s.maximum.toFixed(2)}</TableCell>
                      <TableCell>{s.stddev.toFixed(3)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
