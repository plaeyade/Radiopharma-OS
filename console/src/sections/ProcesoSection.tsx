import { useMemo, useState } from "react";
import { ArrowRight, Beaker, CalendarClock, CalendarRange, ClipboardCheck, Gauge, Plus, Trash2, Users, XCircle, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { ConsoleConfig, ConsoleData } from "@/lib/console-data";
import type { Session } from "@/lib/session";
import { bottleneckProcess, campaignProcess, doseCalendar, registerProcessSimEvent, scheduleProcess, simulateProcess,
         type CampaignPlan, type DoseCalendar, type ProcessBottleneck, type ProcessSchedule, type ProcessSimulation } from "@/lib/actions";

interface Props {
  data: ConsoleData;
  cfg: ConsoleConfig;
  session: Session | null;
  selected: string;
  onSelect: (batch: string) => void;
  onChanged: () => void;
}

const fmtHora = (iso: string) =>
  new Date(iso).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });

/** Process Twin: cascada EOB -> EOS, planificación inversa y cuellos de botella. */
export default function ProcesoSection({ data, cfg, session, selected, onSelect, onChanged }: Props) {
  const [protocolId, setProtocolId] = useState<string>(data.protocols[0]?.protocol_id ?? "");
  const [eobTxt, setEobTxt] = useState<string>("");
  const [sim, setSim] = useState<ProcessSimulation | null>(null);
  const [busy, setBusy] = useState(false);
  // F2: planificación inversa
  const [doseTime, setDoseTime] = useState<string>("");
  const [setupTxt, setSetupTxt] = useState<string>("10");
  const [dosesTxt, setDosesTxt] = useState<string>("");
  const [plan, setPlan] = useState<ProcessSchedule | null>(null);
  // F2: cuello de botella
  const [cuello, setCuello] = useState<ProcessBottleneck | null>(null);
  // F3: calendario multi-paciente
  interface CitaForm { label: string; time: string; dose: string }
  const [citas, setCitas] = useState<CitaForm[]>([
    { label: "P1", time: "", dose: "" },
    { label: "P2", time: "", dose: "" },
    { label: "P3", time: "", dose: "" },
  ]);
  const [cal, setCal] = useState<DoseCalendar | null>(null);
  // F4: plan de campaña (reutiliza las mismas citas)
  const [capTxt, setCapTxt] = useState<string>("40");
  const [prepTxt, setPrepTxt] = useState<string>("30");
  const [turnTxt, setTurnTxt] = useState<string>("240");
  const [camp, setCamp] = useState<CampaignPlan | null>(null);

  const batch = data.batches.find((b) => b.batch_id === selected);
  const proto = data.protocols.find((p) => p.protocol_id === protocolId)
    ?? data.protocols[0];

  // EOB del lote seleccionado (autorrelleno editable)
  const eobLote = batch?.results?.eob_activity_gbq;
  const eob = useMemo(() => {
    const manual = parseFloat(eobTxt);
    return Number.isFinite(manual) && manual > 0 ? manual : (eobLote ?? 0);
  }, [eobTxt, eobLote]);

  // F2: tiempo muerto estimado desde telemetría real de la corrida
  const muerto = useMemo(() => {
    const series = data.telemetry[selected];
    if (!series?.length || !batch) return null;
    const span = Math.max(...series.flatMap((s) => s.points.map((p) => p.t)));
    const nominal = batch.beam.irradiation_time_min;
    const extra = span - nominal;
    return { span, nominal, extra };
  }, [data.telemetry, selected, batch]);

  const doSimulate = async () => {
    if (!proto || !(eob > 0)) {
      toast.error("Selecciona protocolo y una EOB > 0 (lote o valor manual)");
      return;
    }
    setBusy(true);
    try {
      const r = await simulateProcess(cfg, proto.protocol_id, eob);
      setSim(r);
      toast.success(`EOS ${r.eos_activity_gbq.toFixed(2)} GBq · ${r.patient_doses} dosis`);
    } catch (e) {
      toast.error(`Simulación falló: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const doSchedule = async () => {
    if (!proto) return;
    const when = doseTime ? new Date(doseTime) : null;
    if (!when || Number.isNaN(when.getTime())) {
      toast.error("Indica la hora de administración de la dosis");
      return;
    }
    const doses = parseInt(dosesTxt, 10);
    const irr = batch?.beam?.irradiation_time_min ?? 60;
    setBusy(true);
    try {
      const r = await scheduleProcess(cfg, {
        protocol_id: proto.protocol_id,
        dose_time: when.toISOString(),
        irradiation_time_min: irr,
        setup_min: parseFloat(setupTxt) || 0,
        ...(Number.isFinite(doses) && doses > 0
          ? { target_doses: doses }
          : sim ? { eos_target_gbq: sim.eos_activity_gbq } : { eos_target_gbq: 30 }),
      });
      setPlan(r);
      toast.success(`Plan listo: haz a las ${fmtHora(r.beam_start)}, EOB ${r.eob_required_gbq.toFixed(1)} GBq`);
    } catch (e) {
      toast.error(`Planificación falló: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const doBottleneck = async () => {
    if (!proto || !(eob > 0)) {
      toast.error("Selecciona protocolo y EOB > 0 primero");
      return;
    }
    setBusy(true);
    try {
      setCuello(await bottleneckProcess(cfg, proto.protocol_id, eob));
    } catch (e) {
      toast.error(`Análisis falló: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  // F3: calcula el calendario de pacientes (EOS de la simulación)
  const doCalendar = async () => {
    if (!proto) return;
    const eosAct = sim?.eos_activity_gbq ?? 0;
    if (!(eosAct > 0)) {
      toast.error("Simula la cascada primero (EOS necesaria)");
      return;
    }
    const appts = citas
      .filter((c) => c.time)
      .map((c) => ({
        time: new Date(c.time).toISOString(),
        label: c.label || undefined,
        dose_gbq: c.dose ? parseFloat(c.dose) : undefined,
      }));
    if (!appts.length) {
      toast.error("Define al menos una cita con hora");
      return;
    }
    // EOS lista al final de la cascada: dose_time del plan si existe;
    // si no, se asume disponible en la primera cita
    const eosIso = plan
      ? plan.dose_time
      : appts.map((a) => a.time).sort()[0];
    setBusy(true);
    try {
      const r = await doseCalendar(cfg, {
        protocol_id: proto.protocol_id,
        eos_activity_gbq: eosAct,
        eos_time: eosIso,
        appointments: appts,
      });
      setCal(r);
      toast.success(`Calendario: ${r.patients_served}/${r.patients_total} pacientes servidos`);
    } catch (e) {
      toast.error(`Calendario falló: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const setCita = (i: number, patch: Partial<{ label: string; time: string; dose: string }>) =>
    setCitas((prev) => prev.map((c, j) => (j === i ? { ...c, ...patch } : c)));

  const doRegister = async () => {
    if (!sim || !batch || !session) return;
    const detail =
      `Process Twin ${sim.protocol_id}: EOB ${sim.eob_activity_gbq.toFixed(3)} GBq -> ` +
      `EOS ${sim.eos_activity_gbq.toFixed(3)} GBq en ${sim.total_time_min} min ` +
      `(decaimiento x${sim.overall_decay_factor}, eficiencia x${sim.overall_efficiency}); ` +
      `${sim.patient_doses} dosis de ${sim.dose_per_patient_gbq} GBq`;
    try {
      await registerProcessSimEvent(cfg, session.token, batch.batch_id, detail);
      toast.success(`Simulación registrada en el eBR de ${batch.batch_id}`);
      onChanged();
    } catch (e) {
      toast.error(`No se pudo registrar: ${(e as Error).message}`);
    }
  };

  // F4: plan de campaña sobre las mismas citas (no requiere simulación)
  const doCampaign = async () => {
    if (!proto) return;
    const appts = citas
      .filter((c) => c.time)
      .map((c) => ({
        time: new Date(c.time).toISOString(),
        label: c.label || undefined,
        dose_gbq: c.dose ? parseFloat(c.dose) : undefined,
      }));
    if (!appts.length) {
      toast.error("Define al menos una cita con hora");
      return;
    }
    setBusy(true);
    try {
      const r = await campaignProcess(cfg, {
        protocol_id: proto.protocol_id,
        capacity_gbq: parseFloat(capTxt),
        prep_min: parseFloat(prepTxt),
        turnaround_min: parseFloat(turnTxt),
        appointments: appts,
      });
      setCamp(r);
      if (r.unserved.length > 0) {
        toast.warning(`${r.unserved.length} cita(s) no servibles con esta capacidad/turnaround`);
      }
    } catch (e) {
      toast.error(`Campaña falló: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card className="border-slate-800 bg-slate-900/60">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm text-slate-200">
            <Beaker className="h-4 w-4 text-cyan-400" />
            Simulación de proceso EOB → EOS
            {proto && !proto.validated && (
              <Badge variant="outline" className="border-amber-700 text-amber-400">
                parámetros sin validar in-situ
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-4">
          <div>
            <Label className="text-xs text-slate-400">Protocolo</Label>
            <Select value={proto?.protocol_id ?? ""} onValueChange={setProtocolId}>
              <SelectTrigger className="h-8 border-slate-700 bg-slate-900 text-xs">
                <SelectValue placeholder="Protocolo" />
              </SelectTrigger>
              <SelectContent className="border-slate-700 bg-slate-900">
                {data.protocols.map((p) => (
                  <SelectItem key={p.protocol_id} value={p.protocol_id} className="text-xs">
                    {p.name} · T½ {p.half_life_min} min
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs text-slate-400">Lote (EOB de referencia)</Label>
            <Select value={selected} onValueChange={onSelect}>
              <SelectTrigger className="h-8 border-slate-700 bg-slate-900 text-xs">
                <SelectValue placeholder="Lote" />
              </SelectTrigger>
              <SelectContent className="border-slate-700 bg-slate-900">
                {data.batches.map((b) => (
                  <SelectItem key={b.batch_id} value={b.batch_id} className="text-xs">
                    {b.batch_id} · {b.product_nuclide} · {b.results.eob_activity_gbq.toFixed(1)} GBq
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs text-slate-400">EOB (GBq) — editable</Label>
            <Input
              value={eobTxt}
              onChange={(e) => setEobTxt(e.target.value)}
              placeholder={eobLote ? eobLote.toFixed(3) : "GBq al EOB"}
              className="h-8 border-slate-700 bg-slate-900 text-xs" />
          </div>
          <div className="flex items-end gap-2">
            <Button size="sm" onClick={doSimulate} disabled={busy || !proto}
                    className="h-8 flex-1 bg-cyan-700 hover:bg-cyan-600">
              Simular cascada
            </Button>
            <Button size="sm" variant="outline" onClick={doBottleneck}
                    disabled={busy || !proto}
                    className="h-8 border-slate-700 text-xs">
              <Gauge className="mr-1 h-3.5 w-3.5" />Cuellos
            </Button>
          </div>
        </CardContent>
      </Card>

      {sim && (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <Card className="border-slate-800 bg-slate-900/60">
              <CardContent className="pt-4">
                <p className="text-xs text-slate-500">Actividad EOS</p>
                <p className="text-2xl font-semibold text-cyan-300">
                  {sim.eos_activity_gbq.toFixed(2)} <span className="text-sm">GBq</span>
                </p>
                <p className="text-xs text-slate-500">
                  de {sim.eob_activity_gbq.toFixed(2)} GBq EOB en {sim.total_time_min} min
                </p>
              </CardContent>
            </Card>
            <Card className="border-slate-800 bg-slate-900/60">
              <CardContent className="pt-4">
                <p className="text-xs text-slate-500">Decaimiento total</p>
                <p className="text-2xl font-semibold text-slate-200">
                  ×{sim.overall_decay_factor.toFixed(4)}
                </p>
                <p className="text-xs text-slate-500">T½ {sim.half_life_min} min ({sim.nuclide})</p>
              </CardContent>
            </Card>
            <Card className="border-slate-800 bg-slate-900/60">
              <CardContent className="pt-4">
                <p className="text-xs text-slate-500">Eficiencia de proceso</p>
                <p className="text-2xl font-semibold text-slate-200">
                  ×{sim.overall_efficiency.toFixed(4)}
                </p>
                <p className="text-xs text-slate-500">Π η de {sim.steps.length} pasos</p>
              </CardContent>
            </Card>
            <Card className="border-slate-800 bg-slate-900/60">
              <CardContent className="pt-4">
                <p className="flex items-center gap-1 text-xs text-slate-500">
                  <Users className="h-3 w-3" /> Dosis por paciente
                </p>
                <p className="text-2xl font-semibold text-emerald-300">{sim.patient_doses}</p>
                <p className="text-xs text-slate-500">a {sim.dose_per_patient_gbq} GBq/dosis</p>
              </CardContent>
            </Card>
          </div>

          <Card className="border-slate-800 bg-slate-900/60">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center justify-between text-sm text-slate-200">
                Cascada paso a paso
                {session && batch && (
                  <Button size="sm" variant="outline" onClick={doRegister}
                          className="h-7 border-slate-700 text-xs">
                    <ClipboardCheck className="mr-1 h-3.5 w-3.5" />
                    Registrar en eBR de {batch.batch_id}
                  </Button>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-left text-slate-500">
                    <th className="py-1.5 pr-2">Paso</th>
                    <th className="py-1.5 pr-2 text-right">Duración</th>
                    <th className="py-1.5 pr-2 text-right">η</th>
                    <th className="py-1.5 pr-2 text-right">Entrada</th>
                    <th className="py-1.5 pr-2 text-right">Tras decaimiento</th>
                    <th className="py-1.5 text-right">Salida</th>
                  </tr>
                </thead>
                <tbody>
                  {sim.steps.map((s) => (
                    <tr key={s.name} className="border-b border-slate-800/60 text-slate-300">
                      <td className="py-1.5 pr-2 capitalize">{s.name}</td>
                      <td className="py-1.5 pr-2 text-right">{s.duration_min} min</td>
                      <td className="py-1.5 pr-2 text-right">{s.efficiency.toFixed(2)}</td>
                      <td className="py-1.5 pr-2 text-right">{s.activity_in_gbq.toFixed(3)}</td>
                      <td className="py-1.5 pr-2 text-right text-amber-300/80">
                        {s.activity_after_decay_gbq.toFixed(3)}
                      </td>
                      <td className="py-1.5 text-right text-cyan-300">
                        {s.activity_out_gbq.toFixed(3)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-3 flex items-center gap-1 text-xs text-slate-500">
                EOB {sim.eob_activity_gbq.toFixed(2)} GBq
                <ArrowRight className="h-3 w-3" />
                EOS {sim.eos_activity_gbq.toFixed(2)} GBq
                · honestidad de datos: protocolo {sim.validated ? "validado" : "sin validar in-situ"}
              </p>
            </CardContent>
          </Card>
        </>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="border-slate-800 bg-slate-900/60">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm text-slate-200">
              <CalendarClock className="h-4 w-4 text-emerald-400" />
              Planificación inversa (desde hora de dosis)
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-3 gap-2">
              <div className="col-span-1">
                <Label className="text-xs text-slate-400">Hora de dosis</Label>
                <Input type="datetime-local" value={doseTime}
                       onChange={(e) => setDoseTime(e.target.value)}
                       className="h-8 border-slate-700 bg-slate-900 text-xs" />
              </div>
              <div>
                <Label className="text-xs text-slate-400">Dosis objetivo</Label>
                <Input value={dosesTxt} onChange={(e) => setDosesTxt(e.target.value)}
                       placeholder={sim ? `${sim.patient_doses}` : "80"}
                       className="h-8 border-slate-700 bg-slate-900 text-xs" />
              </div>
              <div>
                <Label className="text-xs text-slate-400">Prep. haz (min)</Label>
                <Input value={setupTxt} onChange={(e) => setSetupTxt(e.target.value)}
                       className="h-8 border-slate-700 bg-slate-900 text-xs" />
              </div>
            </div>
            <Button size="sm" onClick={doSchedule} disabled={busy || !proto}
                    className="h-8 bg-emerald-700 hover:bg-emerald-600">
              Planificar hacia atrás
            </Button>
            {muerto && (
              <p className="text-xs text-slate-500">
                Corrida del lote: {muerto.span.toFixed(0)} min de telemetría vs{" "}
                {muerto.nominal} min nominales → tiempo muerto estimado{" "}
                <span className="text-amber-300">{muerto.extra.toFixed(0)} min</span>{" "}
                (rampa + manipulación, medido — no nominal).
              </p>
            )}
            {plan && (
              <div className="space-y-2">
                <p className="text-xs text-slate-400">
                  Haz a las <span className="text-emerald-300">{fmtHora(plan.beam_start)}</span>
                  {" · "}EOB a las <span className="text-cyan-300">{fmtHora(plan.eob_time)}</span>
                  {" con "}<span className="text-cyan-300">{plan.eob_required_gbq.toFixed(2)} GBq</span>
                  {" · "}lead total {plan.total_lead_time_min.toFixed(0)} min
                </p>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 text-left text-slate-500">
                      <th className="py-1 pr-2">Paso</th>
                      <th className="py-1 pr-2 text-right">Inicio</th>
                      <th className="py-1 pr-2 text-right">Fin</th>
                      <th className="py-1 text-right">Act. salida</th>
                    </tr>
                  </thead>
                  <tbody>
                    {plan.steps.map((s) => (
                      <tr key={s.name} className="border-b border-slate-800/60 text-slate-300">
                        <td className="py-1 pr-2 capitalize">{s.name}</td>
                        <td className="py-1 pr-2 text-right">{fmtHora(s.start)}</td>
                        <td className="py-1 pr-2 text-right">{fmtHora(s.end)}</td>
                        <td className="py-1 text-right text-cyan-300">
                          {s.activity_out_gbq.toFixed(2)} GBq
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-slate-900/60">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm text-slate-200">
              <Gauge className="h-4 w-4 text-amber-400" />
              Cuello de botella de la cascada
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!cuello ? (
              <p className="py-6 text-center text-xs text-slate-500">
                Pulsa «Cuellos» con protocolo y EOB seleccionados para cuantificar
                pérdidas y sensibilidades por paso.
              </p>
            ) : (
              <div className="space-y-2">
                <p className="text-xs text-slate-400">
                  Pérdida total {cuello.total_loss_gbq.toFixed(2)} GBq
                  (EOB {cuello.eob_activity_gbq.toFixed(1)} → EOS {cuello.eos_activity_gbq.toFixed(2)}) ·
                  paso dominante:{" "}
                  <span className="capitalize text-amber-300">{cuello.dominant_loss_step}</span>
                </p>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 text-left text-slate-500">
                      <th className="py-1 pr-2">Paso</th>
                      <th className="py-1 pr-2 text-right">Pérdida</th>
                      <th className="py-1 pr-2 text-right">Decaim.</th>
                      <th className="py-1 pr-2 text-right">Efic.</th>
                      <th className="py-1 pr-2 text-right">+EOS/min</th>
                      <th className="py-1 text-right">+EOS/pp η</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cuello.steps.map((s) => (
                      <tr key={s.name}
                          className={`border-b border-slate-800/60 text-slate-300 ${s.name === cuello.dominant_loss_step ? "bg-amber-950/30" : ""}`}>
                        <td className="py-1 pr-2 capitalize">{s.name}</td>
                        <td className="py-1 pr-2 text-right text-amber-300/90">
                          {s.loss_gbq.toFixed(2)}
                        </td>
                        <td className="py-1 pr-2 text-right">{s.decay_loss_gbq.toFixed(2)}</td>
                        <td className="py-1 pr-2 text-right">{s.efficiency_loss_gbq.toFixed(2)}</td>
                        <td className="py-1 pr-2 text-right text-emerald-300/90">
                          +{s.eos_gain_1min_faster_gbq.toFixed(3)}
                        </td>
                        <td className="py-1 text-right text-emerald-300/90">
                          +{s.eos_gain_1pp_efficiency_gbq.toFixed(3)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="text-xs text-slate-500">
                  +EOS/min: ganancia de EOS si el paso fuese 1 min más rápido
                  (idéntica en todos: solo depende de T½). +EOS/pp η: ganancia
                  por 1 punto porcentual de eficiencia — máxima donde η es menor.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-800 bg-slate-900/60">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm text-slate-200">
            <Users className="h-4 w-4 text-violet-400" />
            Calendario de pacientes (fraccionamiento del EOS)
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-2">
            {citas.map((c, i) => (
              <div key={i} className="grid grid-cols-[64px_1fr_96px_32px] items-end gap-2">
                <div>
                  <Label className="text-xs text-slate-400">Paciente</Label>
                  <Input value={c.label} onChange={(e) => setCita(i, { label: e.target.value })}
                         className="h-8 border-slate-700 bg-slate-900 text-xs" />
                </div>
                <div>
                  <Label className="text-xs text-slate-400">Hora de administración</Label>
                  <Input type="datetime-local" value={c.time}
                         onChange={(e) => setCita(i, { time: e.target.value })}
                         className="h-8 border-slate-700 bg-slate-900 text-xs" />
                </div>
                <div>
                  <Label className="text-xs text-slate-400">Dosis (GBq)</Label>
                  <Input value={c.dose} onChange={(e) => setCita(i, { dose: e.target.value })}
                         placeholder={proto ? String(proto.dose_per_patient_gbq) : "0.37"}
                         className="h-8 border-slate-700 bg-slate-900 text-xs" />
                </div>
                <Button size="sm" variant="ghost"
                        onClick={() => setCitas((p) => p.filter((_, j) => j !== i))}
                        disabled={citas.length <= 1}
                        className="h-8 w-8 p-0 text-slate-500 hover:text-red-400">
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <Button size="sm" variant="outline"
                    onClick={() => setCitas((p) => [...p, { label: `P${p.length + 1}`, time: "", dose: "" }])}
                    className="h-8 border-slate-700 text-xs">
              <Plus className="mr-1 h-3.5 w-3.5" />Cita
            </Button>
            <Button size="sm" onClick={doCalendar} disabled={busy || !proto || !sim}
                    className="h-8 bg-violet-700 hover:bg-violet-600">
              Calcular calendario
            </Button>
            {!sim && (
              <span className="self-center text-xs text-slate-500">
                (simula la cascada primero)
              </span>
            )}
          </div>
          {cal && (
            <div className="space-y-2">
              <p className="text-xs text-slate-400">
                Servidos <span className="text-emerald-300">{cal.patients_served}/{cal.patients_total}</span>
                {" · "}extraído {cal.total_drawn_gbq.toFixed(2)} GBq
                {" · "}remanente {cal.remaining_after_last_gbq.toFixed(2)} GBq
                {" · "}EOS mínima para todos:{" "}
                <span className={cal.required_eos_gbq <= cal.eos_activity_gbq
                  ? "text-emerald-300" : "text-red-400"}>
                  {cal.required_eos_gbq.toFixed(2)} GBq
                </span>
              </p>
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-left text-slate-500">
                    <th className="py-1 pr-2">Paciente</th>
                    <th className="py-1 pr-2 text-right">Hora</th>
                    <th className="py-1 pr-2 text-right">Dosis</th>
                    <th className="py-1 pr-2 text-right">Inventario</th>
                    <th className="py-1 pr-2 text-right">Viable</th>
                    <th className="py-1 text-right">Restante</th>
                  </tr>
                </thead>
                <tbody>
                  {cal.slots.map((s, i) => (
                    <tr key={i} className="border-b border-slate-800/60 text-slate-300">
                      <td className="py-1 pr-2">{s.label || `P${i + 1}`}</td>
                      <td className="py-1 pr-2 text-right">{fmtHora(s.time)}</td>
                      <td className="py-1 pr-2 text-right">{s.dose_gbq.toFixed(3)}</td>
                      <td className="py-1 pr-2 text-right">{s.inventory_before_gbq.toFixed(2)}</td>
                      <td className="py-1 pr-2 text-right">
                        {s.feasible
                          ? <CheckCircle2 className="ml-auto h-3.5 w-3.5 text-emerald-400" />
                          : <XCircle className="ml-auto h-3.5 w-3.5 text-red-400" />}
                      </td>
                      <td className="py-1 text-right text-cyan-300">
                        {s.inventory_after_gbq.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs text-slate-500">
                El inventario decae entre administraciones (T½ {cal.half_life_min} min);
                una cita no viable no descuenta actividad.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border-slate-800 bg-slate-900/60 lg:col-span-2">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm text-slate-200">
            <CalendarRange className="h-4 w-4 text-cyan-400" />
            Plan de campaña (demanda → lotes necesarios)
            <Badge variant="outline" className="ml-auto text-[10px]">F4</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-3 gap-2 max-w-xl">
            <div>
              <Label className="text-xs text-slate-400">Capacidad EOS/lote (GBq)</Label>
              <Input value={capTxt} onChange={(e) => setCapTxt(e.target.value)}
                     className="h-8 border-slate-700 bg-slate-900 text-xs" />
            </div>
            <div>
              <Label className="text-xs text-slate-400">Prep. EOS→cita (min)</Label>
              <Input value={prepTxt} onChange={(e) => setPrepTxt(e.target.value)}
                     className="h-8 border-slate-700 bg-slate-900 text-xs" />
            </div>
            <div>
              <Label className="text-xs text-slate-400">Turnaround (min)</Label>
              <Input value={turnTxt} onChange={(e) => setTurnTxt(e.target.value)}
                     className="h-8 border-slate-700 bg-slate-900 text-xs" />
            </div>
          </div>
          <div className="flex gap-2 items-center">
            <Button size="sm" onClick={doCampaign} disabled={busy || !proto}
                    className="h-8 bg-cyan-700 hover:bg-cyan-600">
              Planificar campaña
            </Button>
            <span className="text-xs text-slate-500">
              usa las mismas citas del calendario de pacientes
            </span>
          </div>
          {camp && (
            <div className="space-y-2">
              <p className="text-xs text-slate-400">
                <span className="text-cyan-300">{camp.batches.length} lote(s)</span>
                {" · "}servidas <span className="text-emerald-300">{camp.n_served}/{camp.n_appointments}</span>
                {" · "}EOS total requerida {camp.total_required_eos_gbq.toFixed(2)} GBq
                {" · "}dosis total {camp.total_dose_gbq.toFixed(2)} GBq
                {camp.unserved.length > 0 && (
                  <span className="text-red-400">
                    {" · "}no servibles: {camp.unserved.map((a) => a.label || fmtHora(a.time)).join(", ")}
                  </span>
                )}
              </p>
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-left text-slate-500">
                    <th className="py-1 pr-2">Lote</th>
                    <th className="py-1 pr-2 text-right">EOS</th>
                    <th className="py-1 pr-2 text-right">EOS requerida</th>
                    <th className="py-1 pr-2 text-right">Utilización</th>
                    <th className="py-1 pr-2 text-right">Citas</th>
                    <th className="py-1 text-right">Ventana</th>
                  </tr>
                </thead>
                <tbody>
                  {camp.batches.map((b) => (
                    <tr key={b.index} className="border-b border-slate-800/60 text-slate-300">
                      <td className="py-1 pr-2">#{b.index}</td>
                      <td className="py-1 pr-2 text-right">{fmtHora(b.eos_time)}</td>
                      <td className="py-1 pr-2 text-right text-cyan-300">
                        {b.required_eos_gbq.toFixed(2)} GBq
                      </td>
                      <td className="py-1 pr-2 text-right">
                        <span className={b.utilization > 0.85 ? "text-amber-300" : "text-emerald-300"}>
                          {(b.utilization * 100).toFixed(0)} %
                        </span>
                      </td>
                      <td className="py-1 pr-2 text-right">{b.n_appointments}</td>
                      <td className="py-1 text-right">
                        {fmtHora(b.first_appointment)} – {fmtHora(b.last_appointment)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs text-slate-500">
                La EOS requerida es la inversa exacta con decaimiento entre administraciones
                (T½ {camp.half_life_min} min); el turnaround es la separación mínima entre
                lotes (haz + síntesis + QC del lote anterior).
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
