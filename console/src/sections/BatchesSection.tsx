import { useState } from "react";
import { Flame, Plus } from "lucide-react";
import { toast } from "sonner";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { burnupProfile, REACTIONS, registerBatch, TARGET_ES, type BurnupProfileResult } from "@/lib/actions";
import type { Batch, ConsoleConfig, ConsoleData } from "@/lib/console-data";
import { badgeVariant, estadoColor, fmtTs, shortHash } from "@/lib/format";
import { roleRank, type Session } from "@/lib/session";

interface Props {
  data: ConsoleData; cfg: ConsoleConfig; session: Session | null;
  selected: string; onSelect: (id: string) => void; onChanged: () => void;
}

export default function BatchesSection({ data, cfg, session, selected, onSelect, onChanged }: Props) {
  const b = data.batches.find((x) => x.batch_id === selected) ?? data.batches[0];
  const operativo = data.mode === "live" && session && roleRank(session.role) >= 1;

  return (
    <div className="grid gap-4 lg:grid-cols-5">
      <Card className="border-slate-800 bg-[#0d1420] lg:col-span-3">
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle className="text-sm text-slate-300">Registro de lotes (ALCOA+, inmutable)</CardTitle>
          <NewBatchDialog cfg={cfg} disabled={!operativo} onDone={onChanged} />
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow className="border-slate-800">
                <TableHead>Lote</TableHead><TableHead>Núclido</TableHead>
                <TableHead>EOB (GBq)</TableHead><TableHead>Estado</TableHead>
                <TableHead>Liberación</TableHead><TableHead>Integridad</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.batches.map((x) => (
                <TableRow key={x.batch_id} onClick={() => onSelect(x.batch_id)}
                          className={`cursor-pointer border-slate-800 ${x.batch_id === b?.batch_id ? "bg-cyan-500/5" : ""}`}>
                  <TableCell className="font-mono text-xs text-cyan-300">{x.batch_id}</TableCell>
                  <TableCell><Badge variant="outline" className="border-slate-700">{x.product_nuclide}</Badge></TableCell>
                  <TableCell>{x.results.eob_activity_gbq.toFixed(2)}</TableCell>
                  <TableCell className={estadoColor[x.status]}>{x.status}</TableCell>
                  <TableCell><Badge variant={badgeVariant(x.release_status)}>{x.release_status}</Badge></TableCell>
                  <TableCell className={x.integrity_ok ? "text-emerald-400" : "text-red-400"}>
                    {x.integrity_ok ? "✓ hash" : "✗ fallo"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {b && (
        <Card className="border-slate-800 bg-[#0d1420] lg:col-span-2">
          <CardHeader>
            <CardTitle className="font-mono text-sm text-cyan-300">{b.batch_id}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Fila k="Reacción / blanco" v={`${b.reaction_id} · ${b.target_id}`} />
            <Fila k="Registrado" v={`${fmtTs(b.created_at)} por ${b.created_by}`} />
            <Fila k="Haz" v={`${b.beam.beam_energy_mev} MeV · ${b.beam.current_ua} µA · ${b.beam.irradiation_time_min} min`} />
            <Fila k="Actividad EOB" v={`${b.results.eob_activity_gbq.toFixed(2)} ± ${b.results.eob_activity_gbq_uncertainty.toFixed(2)} GBq`} />
            <Fila k="Factor saturación" v={b.results.saturation_factor.toFixed(4)} />
            <Fila k="Hash del registro" v={<span className="font-mono text-xs">{shortHash(b.record_hash, 20)}</span>} />
            <Fila k="Liberación" v={
              <span className={estadoColor[b.release_status]}>
                {b.release_status}{b.released_by ? ` por ${b.released_by}` : ""}
              </span>} />
            {b.release_reason && <Fila k="Motivo" v={b.release_reason} />}
            <p className="pt-2 text-xs text-slate-600">
              Registro inmutable ALCOA+: sin edición ni borrado; las correcciones
              se hacen por anulación controlada con motivo.
            </p>
          </CardContent>
        </Card>
      )}
      <BurnupCard cfg={cfg} b={b} live={data.mode === "live"} />
    </div>
  );
}

/* ------------------------------------------- quemado del blanco (1D) ---- */
function BurnupCard({ cfg, b, live }: { cfg: ConsoleConfig; b: Batch | undefined; live: boolean }) {
  const [res, setRes] = useState<BurnupProfileResult | null>(null);
  const [busy, setBusy] = useState(false);

  const calcular = async () => {
    if (!b) return;
    setBusy(true);
    try {
      const r = await burnupProfile(cfg, {
        reaction_id: b.reaction_id, target_id: b.target_id,
        beam_energy_mev: b.beam.beam_energy_mev, current_ua: b.beam.current_ua,
        irradiation_time_min: b.beam.irradiation_time_min, n_zones: 10,
      });
      setRes(r);
    } catch (e) {
      toast.error(`Error en el cálculo: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const lossPct = res && res.eob_no_burnup_gbq > 0
    ? (100 * res.loss_gbq) / res.eob_no_burnup_gbq : 0;
  const chart = res?.zones.map((z) => ({
    zona: `${z.e_in_mev.toFixed(1)}`,
    ppm: +(z.depletion_fraction * 1e6).toFixed(3),
    peso: +(z.production_weight * 100).toFixed(1),
  })) ?? [];

  return (
    <Card className="border-slate-800 bg-[#0d1420] lg:col-span-5">
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="text-sm text-slate-300">
          Quemado del blanco · perfil axial 1D (Burnup Engine multizona)
        </CardTitle>
        <Button size="sm" variant="outline" disabled={!live || !b || busy}
                onClick={() => void calcular()}
                title={live ? "Calcula con los parámetros del lote seleccionado"
                            : "Requiere modo en vivo (Yield Engine accesible)"}
                className="border-slate-700">
          <Flame className="mr-1 h-3.5 w-3.5" />
          {busy ? "Calculando…" : "Calcular perfil"}
        </Button>
      </CardHeader>
      <CardContent>
        {!res && (
          <p className="text-xs text-slate-500">
            Depleción del núclido blanco resuelta en 10 capas axiales a lo largo
            del haz: σ_b(E) paramétrica con umbral, atenuación exponencial del
            flujo y Bateman con término de quemado por capa. Con n_zones=1
            reproduce el modelo de grupo único.
          </p>
        )}
        {res && (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-4">
              <Stat k="EOB sin quemado" v={`${res.eob_no_burnup_gbq.toFixed(2)} GBq`} />
              <Stat k="EOB con quemado" v={`${res.eob_with_burnup_gbq.toFixed(2)} GBq`} />
              <Stat k="Pérdida por quemado"
                    v={`${lossPct.toExponential(2)} %`}
                    tone={lossPct > 0.5 ? "text-amber-400" : "text-emerald-400"} />
              <Stat k="Depleción local máx (entrada)"
                    v={`${(res.depletion_max * 1e6).toFixed(2)} ppm`} />
            </div>
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chart} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="zona" tick={{ fill: "#64748b", fontSize: 11 }}
                         label={{ value: "E entrada capa (MeV)", position: "insideBottom", offset: -2, fill: "#475569", fontSize: 10 }} />
                  <YAxis tick={{ fill: "#64748b", fontSize: 11 }}
                         label={{ value: "depleción (ppm)", angle: -90, position: "insideLeft", fill: "#475569", fontSize: 10 }} />
                  <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }}
                           formatter={(v: number, name: string) =>
                             name === "ppm" ? [`${v} ppm`, "depleción"] : [`${v} %`, "peso producción"]} />
                  <Bar dataKey="ppm" fill="#f59e0b" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="text-xs text-slate-600">
              {res.reaction_id} · {res.n_zones} capas · σ_b,máx {res.burnup_xs_max_mb} mb ·
              el quemado es máximo a la entrada del blanco (mayor energía) y casi
              nulo cerca del umbral — perfil de entrada para el futuro acoplamiento 2D (Elmer FEM).
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Stat({ k, v, tone }: { k: string; v: string; tone?: string }) {
  return (
    <div className="rounded-md border border-slate-800 bg-slate-900/40 p-3">
      <div className="text-xs text-slate-500">{k}</div>
      <div className={`text-lg font-semibold ${tone ?? "text-slate-200"}`}>{v}</div>
    </div>
  );
}

function Fila({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b border-slate-800/60 pb-1.5">
      <span className="text-slate-500">{k}</span>
      <span className="text-right text-slate-200">{v}</span>
    </div>
  );
}

/* ------------------------------------------------------- nuevo lote ---- */
function NewBatchDialog({ cfg, disabled, onDone }:
  { cfg: ConsoleConfig; disabled: boolean; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [rxn, setRxn] = useState(REACTIONS[0].id);
  const [target, setTarget] = useState(REACTIONS[0].targets[0]);
  const [energy, setEnergy] = useState("16.5");
  const [current, setCurrent] = useState("37");
  const [time, setTime] = useState("60");
  const [busy, setBusy] = useState(false);
  const reaccion = REACTIONS.find((r) => r.id === rxn)!;

  const submit = async () => {
    setBusy(true);
    try {
      const r = await registerBatch(cfg, cfg.token, {
        reaction_id: rxn, target_id: target,
        beam_energy_mev: +energy, current_ua: +current, irradiation_time_min: +time,
      });
      toast.success(`Lote registrado: ${r.batch_id}`);
      setOpen(false);
      onDone();
    } catch (e) {
      toast.error(`Error al registrar: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" disabled={!!disabled}
                title={disabled ? "Requiere modo en vivo + sesión iniciada" : ""}
                className="bg-cyan-600 text-white hover:bg-cyan-500 disabled:opacity-40">
          <Plus className="mr-1 h-3.5 w-3.5" /> Nuevo lote
        </Button>
      </DialogTrigger>
      <DialogContent className="border-slate-700 bg-[#0d1420] text-slate-200">
        <DialogHeader><DialogTitle>Registrar lote de irradiación</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div>
            <Label>Reacción</Label>
            <Select value={rxn} onValueChange={(v) => {
              setRxn(v);
              setTarget(REACTIONS.find((r) => r.id === v)!.targets[0]);
            }}>
              <SelectTrigger className="border-slate-700 bg-slate-900"><SelectValue /></SelectTrigger>
              <SelectContent className="border-slate-700 bg-slate-900">
                {REACTIONS.map((r) => (
                  <SelectItem key={r.id} value={r.id}>{r.notation}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Blanco</Label>
            <Select value={target} onValueChange={setTarget}>
              <SelectTrigger className="border-slate-700 bg-slate-900"><SelectValue /></SelectTrigger>
              <SelectContent className="border-slate-700 bg-slate-900">
                {reaccion.targets.map((t) => (
                  <SelectItem key={t} value={t}>{TARGET_ES[t] ?? t}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div><Label>Energía (MeV)</Label>
              <Input value={energy} onChange={(e) => setEnergy(e.target.value)}
                     className="border-slate-700 bg-slate-900" /></div>
            <div><Label>Corriente (µA)</Label>
              <Input value={current} onChange={(e) => setCurrent(e.target.value)}
                     className="border-slate-700 bg-slate-900" /></div>
            <div><Label>Tiempo (min)</Label>
              <Input value={time} onChange={(e) => setTime(e.target.value)}
                     className="border-slate-700 bg-slate-900" /></div>
          </div>
          <p className="text-xs text-slate-500">
            Flujo: Yield Engine (EOB físico) → Nuclear Data (linaje del dataset) →
            Data Lake (registro ALCOA+ inmutable, atribuido a tu sesión).
          </p>
          <Button onClick={() => void submit()} disabled={busy}
                  className="w-full bg-cyan-600 hover:bg-cyan-500">
            {busy ? "Calculando y registrando…" : "Calcular y registrar"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
