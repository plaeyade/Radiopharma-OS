import { useMemo, useState } from "react";
import { AlertTriangle, Minus, TrendingDown, TrendingUp } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ConsoleData, EobTrend } from "@/lib/console-data";
import { REACTIONS } from "@/lib/actions";

interface Props { data: ConsoleData }

const DIRECCION = {
  stable: { texto: "Estable", icono: Minus, clase: "text-emerald-400" },
  improving: { texto: "Creciente", icono: TrendingUp, clase: "text-cyan-400" },
  declining: { texto: "Decreciente", icono: TrendingDown, clase: "text-amber-400" },
} as const;

/** Control chart de EOB normalizado (GBq/µA·h) — trending GMP (APR/PQR). */
export default function TrendsSection({ data }: Props) {
  const reacciones = Object.keys(data.trends);
  const [sel, setSel] = useState<string>(reacciones[0] ?? "");
  const reaccion = reacciones.includes(sel) ? sel : reacciones[0];
  const trend: EobTrend | undefined = reaccion ? data.trends[reaccion] : undefined;

  const puntos = useMemo(() => (trend?.points ?? []).map((p, i) => ({
    i: i + 1,
    valor: +p.eob_per_uah.toFixed(4),
    estado: p.out_of_control ? "fuera" : p.warning ? "aviso" : "ok",
    batch: p.batch_id,
    eob: p.eob_activity_gbq,
    fecha: p.created_at.slice(0, 10),
  })), [trend]);

  if (!trend) {
    return (
      <Card className="border-slate-800 bg-slate-900/60">
        <CardContent className="py-10 text-center text-sm text-slate-400">
          Sin datos de trending — registra lotes para alimentar el control de
          rendimiento (mínimo 2 por reacción).
        </CardContent>
      </Card>
    );
  }

  const dir = DIRECCION[trend.direction];
  const IconoDir = dir.icono;
  const nombreRx = REACTIONS.find((r) => r.id === reaccion)?.notation ?? reaccion;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Select value={reaccion} onValueChange={setSel}>
          <SelectTrigger className="h-8 w-64 border-slate-700 bg-slate-900 text-xs">
            <SelectValue placeholder="Reacción" />
          </SelectTrigger>
          <SelectContent className="border-slate-700 bg-slate-900">
            {reacciones.map((r) => (
              <SelectItem key={r} value={r} className="text-xs">
                {REACTIONS.find((x) => x.id === r)?.notation ?? r}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-xs text-slate-500">{trend.n_batches} lotes en control</span>
        <span className="flex-1" />
        <Badge variant="outline" className={`border-slate-700 ${dir.clase}`}>
          <IconoDir className="mr-1 h-3.5 w-3.5" />
          Tendencia {dir.texto.toLowerCase()}
          {trend.slope_pct_per_day != null &&
            ` · ${trend.slope_pct_per_day >= 0 ? "+" : ""}${trend.slope_pct_per_day.toFixed(2)} %/día`}
        </Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="border-slate-800 bg-slate-900/60">
          <CardHeader className="pb-1"><CardTitle className="text-xs text-slate-400">Rendimiento medio</CardTitle></CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold text-slate-100">
              {trend.mean?.toFixed(3) ?? "—"}
              <span className="ml-1 text-sm font-normal text-slate-400">GBq/µA·h</span>
            </p>
            <p className="text-xs text-slate-500">σ = {trend.std?.toFixed(4) ?? "—"}</p>
          </CardContent>
        </Card>
        <Card className="border-slate-800 bg-slate-900/60">
          <CardHeader className="pb-1"><CardTitle className="text-xs text-slate-400">Límites de control (±3σ)</CardTitle></CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold text-slate-100">
              {trend.lcl?.toFixed(3) ?? "—"} — {trend.ucl?.toFixed(3) ?? "—"}
            </p>
            <p className="text-xs text-slate-500">
              aviso ±2σ: {trend.lwl?.toFixed(3) ?? "—"} — {trend.uwl?.toFixed(3) ?? "—"}
            </p>
          </CardContent>
        </Card>
        <Card className="border-slate-800 bg-slate-900/60">
          <CardHeader className="pb-1"><CardTitle className="text-xs text-slate-400">Puntos fuera de control</CardTitle></CardHeader>
          <CardContent>
            <p className={`text-2xl font-semibold ${puntos.some((p) => p.estado === "fuera") ? "text-red-400" : "text-emerald-400"}`}>
              {puntos.filter((p) => p.estado === "fuera").length}
            </p>
            <p className="text-xs text-slate-500">
              {puntos.filter((p) => p.estado === "aviso").length} en zona de aviso
            </p>
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-800 bg-slate-900/60">
        <CardHeader className="pb-1">
          <CardTitle className="text-sm text-slate-200">
            Gráfico de control — {nombreRx}
          </CardTitle>
          <p className="text-xs text-slate-500">
            EOB normalizado por µA·h de haz, en orden cronológico · líneas:
            media, ±2σ (aviso, ámbar) y ±3σ (control, rojo)
          </p>
        </CardHeader>
        <CardContent>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={puntos} margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
                <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
                <XAxis dataKey="i" tick={{ fontSize: 10, fill: "#64748b" }}
                       label={{ value: "lote (cronológico)", position: "insideBottom", offset: -2, fontSize: 10, fill: "#64748b" }} />
                <YAxis domain={["auto", "auto"]} tick={{ fontSize: 10, fill: "#64748b" }} width={64}
                       tickFormatter={(v: number) => v.toFixed(2)} />
                <Tooltip
                  contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }}
                  formatter={(v: number | string, _n, item) => [
                    `${Number(v).toFixed(3)} GBq/µA·h · EOB ${item.payload.eob} GBq`,
                    item.payload.batch]}
                  labelFormatter={(l) => `Lote #${l} · ${puntos[Number(l) - 1]?.fecha ?? ""}`} />
                {trend.mean != null && (
                  <ReferenceLine y={trend.mean} stroke="#94a3b8" strokeWidth={1.5}
                                 label={{ value: "media", fill: "#94a3b8", fontSize: 10, position: "right" }} />)}
                {trend.uwl != null && (
                  <ReferenceLine y={trend.uwl} stroke="#f59e0b" strokeDasharray="6 4" />)}
                {trend.lwl != null && (
                  <ReferenceLine y={trend.lwl} stroke="#f59e0b" strokeDasharray="6 4" />)}
                {trend.ucl != null && (
                  <ReferenceLine y={trend.ucl} stroke="#ef4444" strokeDasharray="4 4" />)}
                {trend.lcl != null && (
                  <ReferenceLine y={trend.lcl} stroke="#ef4444" strokeDasharray="4 4" />)}
                <Line type="monotone" dataKey="valor" stroke="#22d3ee" strokeWidth={2}
                      dot={(props) => {
                        const { cx, cy, payload } = props as { cx: number; cy: number; payload: { estado: string } };
                        const color = payload.estado === "fuera" ? "#ef4444"
                          : payload.estado === "aviso" ? "#f59e0b" : "#22d3ee";
                        return <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={4} fill={color} stroke="#0f172a" strokeWidth={1.5} />;
                      }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {trend.alerts.length > 0 && (
        <Card className="border-amber-900/60 bg-amber-950/20">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm text-amber-300">
              <AlertTriangle className="h-4 w-4" /> Alertas de tendencia
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-inside list-disc space-y-1 text-xs text-amber-200/90">
              {trend.alerts.map((a, i) => <li key={i}>{a}</li>)}
            </ul>
            <p className="mt-3 text-xs text-slate-500">
              Insumo del trending de la revisión periódica de producto (APR/PQR):
              la deriva del rendimiento debe investigarse antes de que un lote
              caiga fuera de especificación.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
