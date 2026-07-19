import { Activity, CheckCircle2, FlaskConical, ShieldCheck, XCircle, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ConsoleData } from "@/lib/console-data";
import { estadoColor, fmtTs } from "@/lib/format";

function Kpi({ icon, label, value, sub }: { icon: React.ReactNode; label: string; value: string; sub: string }) {
  return (
    <Card className="border-slate-800 bg-[#0d1420]">
      <CardContent className="flex items-center gap-4 p-5">
        <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-cyan-500/10 text-cyan-400">{icon}</div>
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
          <p className="text-2xl font-semibold text-slate-100">{value}</p>
          <p className="text-xs text-slate-500">{sub}</p>
        </div>
      </CardContent>
    </Card>
  );
}

export default function Overview({ data, onSelectBatch }: { data: ConsoleData; onSelectBatch: (id: string) => void }) {
  const vivos = data.batches.filter((b) => b.status === "completed");
  const liberados = vivos.filter((b) => b.release_status === "released");
  const eobTotal = liberados.reduce((a, b) => a + b.results.eob_activity_gbq, 0);
  const qcReports = Object.values(data.qc).flat();
  const qcPass = qcReports.length
    ? Math.round((100 * qcReports.filter((q) => q.overall_status === "pass").length) / qcReports.length)
    : 0;
  const serviciosOk = data.services.filter((s) => s.status === "ok").length;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kpi icon={<FlaskConical className="h-5 w-5" />} label="Lotes registrados"
             value={String(vivos.length)} sub={`${liberados.length} liberados GMP`} />
        <Kpi icon={<Zap className="h-5 w-5" />} label="Actividad EOB liberada"
             value={`${eobTotal.toFixed(1)} GBq`} sub="suma de lotes liberados" />
        <Kpi icon={<ShieldCheck className="h-5 w-5" />} label="QC conforme"
             value={`${qcPass} %`} sub={`${qcReports.length} informes QC`} />
        <Kpi icon={<Activity className="h-5 w-5" />} label="Microservicios"
             value={`${serviciosOk}/6`} sub="salud de plataforma" />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="border-slate-800 bg-[#0d1420] lg:col-span-2">
          <CardHeader><CardTitle className="text-sm text-slate-300">Lotes recientes</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {data.batches.map((b) => (
              <button key={b.batch_id} onClick={() => onSelectBatch(b.batch_id)}
                      className="flex w-full items-center gap-3 rounded-lg border border-slate-800 bg-slate-900/40 px-4 py-3 text-left hover:border-cyan-800">
                <span className="font-mono text-sm text-cyan-300">{b.batch_id}</span>
                <span className="rounded bg-slate-800 px-2 py-0.5 text-xs font-semibold text-slate-200">{b.product_nuclide}</span>
                <span className="text-xs text-slate-500">{b.beam.beam_energy_mev} MeV · {b.beam.current_ua} µA</span>
                <span className="flex-1" />
                <span className="text-sm text-slate-300">{b.results.eob_activity_gbq.toFixed(1)} GBq</span>
                <span className={`text-xs font-semibold uppercase ${estadoColor[b.release_status] ?? "text-slate-400"}`}>
                  {b.release_status}
                </span>
              </button>
            ))}
          </CardContent>
        </Card>

        <Card className="border-slate-800 bg-[#0d1420]">
          <CardHeader><CardTitle className="text-sm text-slate-300">Salud de microservicios</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {data.services.map((s) => (
              <div key={s.key} className="flex items-center gap-3 rounded-lg border border-slate-800/70 px-3 py-2">
                {s.status === "ok"
                  ? <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  : <XCircle className="h-4 w-4 text-red-400" />}
                <div className="flex-1">
                  <p className="text-sm text-slate-200">{s.name}</p>
                  <p className="text-xs text-slate-500">
                    {s.port ? `:${s.port}` : "proxy"} · v{s.version}
                  </p>
                </div>
                <Badge variant="outline" className="border-slate-700 text-xs text-slate-400">
                  {s.status === "ok" ? `${s.latency_ms} ms` : "caído"}
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
      <p className="text-xs text-slate-600">Datos al {fmtTs(data.fetched_at)} · modo {data.mode === "live" ? "en vivo (microservicios)" : "demostración"}.</p>
    </div>
  );
}
