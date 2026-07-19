import { useMemo, useState } from "react";
import { ArrowRight, Beaker, ClipboardCheck, Users } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { ConsoleConfig, ConsoleData } from "@/lib/console-data";
import type { Session } from "@/lib/session";
import { registerProcessSimEvent, simulateProcess, type ProcessSimulation } from "@/lib/actions";

interface Props {
  data: ConsoleData;
  cfg: ConsoleConfig;
  session: Session | null;
  selected: string;
  onSelect: (batch: string) => void;
  onChanged: () => void;
}

/** Process Twin: cascada EOB -> EOS con decaimiento y eficiencias por paso. */
export default function ProcesoSection({ data, cfg, session, selected, onSelect, onChanged }: Props) {
  const [protocolId, setProtocolId] = useState<string>(data.protocols[0]?.protocol_id ?? "");
  const [eobTxt, setEobTxt] = useState<string>("");
  const [sim, setSim] = useState<ProcessSimulation | null>(null);
  const [busy, setBusy] = useState(false);

  const batch = data.batches.find((b) => b.batch_id === selected);
  const proto = data.protocols.find((p) => p.protocol_id === protocolId)
    ?? data.protocols[0];

  // EOB del lote seleccionado (autorrelleno editable)
  const eobLote = batch?.results?.eob_activity_gbq;
  const eob = useMemo(() => {
    const manual = parseFloat(eobTxt);
    return Number.isFinite(manual) && manual > 0 ? manual : (eobLote ?? 0);
  }, [eobTxt, eobLote]);

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
          <div className="flex items-end">
            <Button size="sm" onClick={doSimulate} disabled={busy || !proto}
                    className="h-8 w-full bg-cyan-700 hover:bg-cyan-600">
              Simular cascada
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
    </div>
  );
}
