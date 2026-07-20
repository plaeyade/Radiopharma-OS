import { useMemo, useState } from "react";
import { Activity, ClipboardCheck, Gavel } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Textarea } from "@/components/ui/textarea";
import { evaluateQc, qcSpc, releaseBatch, type SpcChartResult } from "@/lib/actions";
import type { ConsoleConfig, ConsoleData } from "@/lib/console-data";
import { badgeVariant, estadoColor, fmtTs, shortHash } from "@/lib/format";
import { roleRank, type Session } from "@/lib/session";

const PACKS: Record<string, { label: string; params: string[] }> = {
  fdg: {
    label: "FDG (monografía USP/EP — verificar vigente)",
    params: ["ph", "radiochemical_purity", "radionuclidic_purity",
             "kryptofix_222", "endotoxins_eu_ml", "acetonitrile_mg_dose"],
  },
  generic_pet: {
    label: "PET genérico",
    params: ["radiochemical_purity", "radionuclidic_purity"],
  },
};

const DEFAULTS: Record<string, string> = {
  ph: "6.8", radiochemical_purity: "0.985", radionuclidic_purity: "0.9999",
  kryptofix_222: "1.8", endotoxins_eu_ml: "5.0", acetonitrile_mg_dose: "2.0",
};

interface Props {
  data: ConsoleData; cfg: ConsoleConfig; session: Session | null;
  selected: string; onSelect: (id: string) => void; onChanged: () => void;
}

export default function QcSection({ data, cfg, session, selected, onSelect, onChanged }: Props) {
  const batch = data.batches.find((x) => x.batch_id === selected) ?? data.batches[0];
  const reports = (batch && data.qc[batch.batch_id]) || [];
  const operativo = data.mode === "live" && session && roleRank(session.role) >= 1;
  const esCalidad = data.mode === "live" && session && roleRank(session.role) >= 3;

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
        {batch && <Badge variant="outline" className="border-slate-700">{batch.product_nuclide}</Badge>}
        <span className="flex-1" />
        {batch && (
          <>
            <QcDialog cfg={cfg} batchId={batch.batch_id} nuclide={batch.product_nuclide}
                      disabled={!operativo} onDone={onChanged} />
            <ReleaseDialog cfg={cfg} batchId={batch.batch_id}
                           disabled={!esCalidad || batch.release_status !== "pending" || batch.status !== "completed"}
                           onDone={onChanged} />
          </>
        )}
      </div>

      <SpcCard data={data} cfg={cfg} />

      {reports.length === 0 ? (
        <Card className="border-slate-800 bg-[#0d1420]">
          <CardContent className="py-10 text-center text-slate-500">
            Sin informes QC registrados para este lote.
          </CardContent>
        </Card>
      ) : reports.map((r) => (
        <Card key={r.qc_id} className="border-slate-800 bg-[#0d1420]">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <CardTitle className="font-mono text-sm text-cyan-300">{r.qc_id}</CardTitle>
              <p className="text-xs text-slate-500">
                {fmtTs(r.created_at)} · {r.created_by} · pack «{r.product}» · integridad {r.integrity_ok ? "✓" : "✗"}
              </p>
            </div>
            <Badge variant={badgeVariant(r.overall_status)} className="text-sm uppercase">
              {r.overall_status}
            </Badge>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow className="border-slate-800">
                  <TableHead>Parámetro</TableHead><TableHead>Medido</TableHead>
                  <TableHead>Límite / detalle</TableHead><TableHead>Estado</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {r.rules.map((rule) => (
                  <TableRow key={rule.parameter} className="border-slate-800">
                    <TableCell className="text-slate-200">{rule.parameter}</TableCell>
                    <TableCell>{String(rule.measured)}</TableCell>
                    <TableCell className="text-slate-400">{rule.limits ?? rule.detail ?? "—"}</TableCell>
                    <TableCell className={`font-semibold ${estadoColor[rule.status]}`}>{rule.status}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <p className="mt-3 font-mono text-xs text-slate-600">hash {shortHash(r.record_hash, 24)}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

/* -------------------------------------------------------- evaluar QC --- */
function QcDialog({ cfg, batchId, nuclide, disabled, onDone }:
  { cfg: ConsoleConfig; batchId: string; nuclide: string; disabled: boolean; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [pack, setPack] = useState("fdg");
  const [vals, setVals] = useState<Record<string, string>>({ ...DEFAULTS });
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      const measurements = Object.fromEntries(
        PACKS[pack].params.map((p) => [p, parseFloat(vals[p] || "0")]));
      const r = await evaluateQc(cfg, cfg.token, batchId,
                                 { product: pack, nuclide, measurements });
      toast.success(`Informe QC registrado: ${r.overall_status.toUpperCase()}`);
      setOpen(false);
      onDone();
    } catch (e) {
      toast.error(`Error QC: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" disabled={disabled} variant="outline"
                title={disabled ? "Requiere modo en vivo + sesión" : ""}
                className="border-cyan-800 bg-transparent text-cyan-300 hover:bg-cyan-500/10 disabled:opacity-40">
          <ClipboardCheck className="mr-1 h-3.5 w-3.5" /> Evaluar QC
        </Button>
      </DialogTrigger>
      <DialogContent className="border-slate-700 bg-[#0d1420] text-slate-200">
        <DialogHeader><DialogTitle>Evaluar control de calidad</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div>
            <Label>Pack de aceptación</Label>
            <Select value={pack} onValueChange={setPack}>
              <SelectTrigger className="border-slate-700 bg-slate-900"><SelectValue /></SelectTrigger>
              <SelectContent className="border-slate-700 bg-slate-900">
                {Object.entries(PACKS).map(([k, v]) => (
                  <SelectItem key={k} value={k}>{v.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {PACKS[pack].params.map((p) => (
              <div key={p}>
                <Label className="text-xs">{p}</Label>
                <Input value={vals[p] ?? ""} onChange={(e) => setVals({ ...vals, [p]: e.target.value })}
                       className="border-slate-700 bg-slate-900" />
              </div>
            ))}
          </div>
          <Button onClick={() => void submit()} disabled={busy}
                  className="w-full bg-cyan-600 hover:bg-cyan-500">
            {busy ? "Evaluando…" : "Evaluar y persistir informe"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/* ---------------------------------------------------------- liberar ---- */
function ReleaseDialog({ cfg, batchId, disabled, onDone }:
  { cfg: ConsoleConfig; batchId: string; disabled: boolean; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("Liberado conforme a QC");
  const [busy, setBusy] = useState(false);

  const decide = async (decision: "released" | "rejected") => {
    setBusy(true);
    try {
      await releaseBatch(cfg, cfg.token, batchId, decision, reason);
      toast.success(decision === "released" ? "Lote LIBERADO" : "Lote RECHAZADO");
      setOpen(false);
      onDone();
    } catch (e) {
      toast.error(`Error: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" disabled={disabled} variant="outline"
                title={disabled ? "Requiere rol calidad+ y lote pendiente" : ""}
                className="border-emerald-800 bg-transparent text-emerald-300 hover:bg-emerald-500/10 disabled:opacity-40">
          <Gavel className="mr-1 h-3.5 w-3.5" /> Liberar / rechazar
        </Button>
      </DialogTrigger>
      <DialogContent className="border-slate-700 bg-[#0d1420] text-slate-200">
        <DialogHeader><DialogTitle>Decisión de liberación GMP</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div>
            <Label>Motivo (obligatorio para rechazo)</Label>
            <Textarea value={reason} onChange={(e) => setReason(e.target.value)}
                      className="border-slate-700 bg-slate-900" />
          </div>
          <p className="text-xs text-slate-500">
            Regla GMP: liberar exige al menos un informe QC «pass». La decisión es
            irreversible y queda registrada con tu identidad.
          </p>
          <div className="flex gap-3">
            <Button onClick={() => void decide("released")} disabled={busy}
                    className="flex-1 bg-emerald-600 hover:bg-emerald-500">Liberar</Button>
            <Button onClick={() => void decide("rejected")} disabled={busy}
                    variant="destructive" className="flex-1">Rechazar</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}


/* ------------------------------------------------- carta de control SPC ---
 * Trending GMP (EDS 25.17/26.19): historia de un parámetro QC a lo largo
 * de los lotes → Shewhart I + reglas WE/Nelson. Apoyo a la decisión; no
 * sustituye la evaluación técnica. */

const SPC_PARAMS = [
  { id: "ph", label: "pH" },
  { id: "radiochemical_purity", label: "Pureza radioquímica" },
  { id: "radionuclidic_purity", label: "Pureza radionuclídica" },
  { id: "kryptofix_222", label: "Kryptofix 2.2.2" },
  { id: "endotoxins_eu_ml", label: "Endotoxinas" },
  { id: "acetonitrile_mg_dose", label: "Acetonitrilo" },
];

function parseSpec(limits?: string): { low: number | null; high: number | null } {
  if (!limits) return { low: null, high: null };
  const m = limits.match(/\[([^\]]+)\]/);
  if (!m) return { low: null, high: null };
  const [a, b] = m[1].split(",").map((x) => x.trim());
  const num = (x: string) => (x === "None" || x === "" ? null : parseFloat(x));
  return { low: num(a), high: num(b) };
}

function SpcCard({ data, cfg }: { data: ConsoleData; cfg: ConsoleConfig }) {
  const [param, setParam] = useState("ph");
  const [spc, setSpc] = useState<SpcChartResult | null>(null);
  const [busy, setBusy] = useState(false);

  // historia del parámetro a lo largo de todos los lotes con QC
  const history = useMemo(() => {
    const rows: { label: string; value: number; spec?: string }[] = [];
    const sorted = [...data.batches].sort(
      (a, b) => a.created_at.localeCompare(b.created_at));
    for (const b of sorted) {
      for (const r of data.qc[b.batch_id] ?? []) {
        for (const rule of r.rules) {
          if (rule.parameter === param && typeof rule.measured === "number") {
            rows.push({ label: b.batch_id.replace(/^BATCH-/, ""),
                        value: rule.measured, spec: rule.limits });
          }
        }
      }
    }
    return rows;
  }, [data, param]);

  const run = async () => {
    setBusy(true);
    try {
      const spec = parseSpec(history.find((h) => h.spec)?.spec);
      const r = await qcSpc(cfg, {
        values: history.map((h) => h.value),
        labels: history.map((h) => h.label),
        spec_low: spec.low, spec_high: spec.high,
      });
      setSpc(r);
    } catch (e) {
      toast.error(`SPC: ${(e as Error).message}`);
      setSpc(null);
    } finally {
      setBusy(false);
    }
  };

  const chartData = (spc?.points ?? []).map((p) => ({
    label: p.label, value: p.value,
    viol: p.violations.length > 0 ? p.value : null,
    violations: p.violations,
  }));

  return (
    <Card className="border-slate-800 bg-[#0d1420]">
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle className="flex items-center gap-2 text-sm text-slate-200">
          <Activity className="h-4 w-4 text-violet-400" />
          Carta de control SPC — trending entre lotes
          <Badge variant="outline" className="text-[10px]">GMP</Badge>
        </CardTitle>
        <div className="flex items-center gap-2">
          <Select value={param} onValueChange={(v) => { setParam(v); setSpc(null); }}>
            <SelectTrigger className="h-8 w-52 border-slate-700 bg-slate-900 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="border-slate-700 bg-[#0d1420]">
              {SPC_PARAMS.map((p) => (
                <SelectItem key={p.id} value={p.id} className="text-xs">{p.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button size="sm" onClick={run} disabled={busy || history.length < 2}
                  className="h-8 bg-violet-700 hover:bg-violet-600">
            {busy ? "Calculando…" : `Analizar (${history.length} puntos)`}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {history.length < 2 && (
          <p className="text-xs text-slate-500">
            Se necesitan informes QC de al menos 2 lotes para la carta de control
            (este parámetro tiene {history.length}).
          </p>
        )}
        {spc && (
          <>
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-400">
              <span>μ = <b className="text-slate-200">{spc.mean.toPrecision(4)}</b></span>
              <span>σ = <b className="text-slate-200">{spc.sigma.toPrecision(3)}</b></span>
              <span>UCL = <b className="text-amber-300">{spc.ucl.toPrecision(4)}</b></span>
              <span>LCL = <b className="text-amber-300">{spc.lcl.toPrecision(4)}</b></span>
              {spc.cpk !== null && (
                <span>Cpk = <b className={spc.cpk >= 1.33 ? "text-emerald-300" : "text-amber-300"}>
                  {spc.cpk.toFixed(2)}</b></span>)}
              <span className={spc.in_control ? "text-emerald-400" : "text-red-400"}>
                {spc.in_control ? "Proceso en control" : "Deriva detectada — revisar puntos marcados"}
              </span>
            </div>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 8, right: 12, left: -8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="label" tick={{ fontSize: 9, fill: "#64748b" }} />
                  <YAxis tick={{ fontSize: 10, fill: "#64748b" }} domain={["auto", "auto"]} />
                  <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", fontSize: 11 }}
                           formatter={(v: number, _n, item) =>
                             [v, (item?.payload?.violations ?? []).join(" ") || "en control"]} />
                  <ReferenceLine y={spc.mean} stroke="#38bdf8" strokeDasharray="6 3" />
                  <ReferenceLine y={spc.ucl} stroke="#f59e0b" strokeDasharray="4 4" />
                  <ReferenceLine y={spc.lcl} stroke="#f59e0b" strokeDasharray="4 4" />
                  {spc.spec_high !== null && (
                    <ReferenceLine y={spc.spec_high} stroke="#ef4444" strokeWidth={1.5} />)}
                  {spc.spec_low !== null && (
                    <ReferenceLine y={spc.spec_low} stroke="#ef4444" strokeWidth={1.5} />)}
                  <Line type="linear" dataKey="value" stroke="#a78bfa" strokeWidth={1.5}
                        dot={{ r: 3, fill: "#a78bfa" }} connectNulls />
                  <Line type="linear" dataKey="viol" stroke="none"
                        dot={{ r: 5, fill: "#ef4444" }} connectNulls={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className="text-[10px] text-slate-500">
              Reglas WE/Nelson (WE1 ±3σ, WE2 2/3 ±2σ, WE3 4/5 ±1σ, WE4 8 mismo lado, TREND 6) ·
              líneas rojas: límites de especificación · {spc.note}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
