import { useEffect, useMemo, useState } from "react";
import { Plane, Radar, Route, Truck } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { ConsoleConfig, ConsoleData } from "@/lib/console-data";
import { listFacilities, reachabilityLogistics, routeLogistics,
         type FacilityItem, type LogisticsRoute, type Reachability } from "@/lib/actions";

interface Props {
  data: ConsoleData;
  cfg: ConsoleConfig;
  selected: string;
}

const DEMO_FACILITIES: FacilityItem[] = [
  { facility_id: "cyclotron_main", name: "Ciclotrón central (demo)", kind: "cyclotron", lat: 40.4168, lon: -3.7038, validated: false },
  { facility_id: "hosp_norte", name: "Hospital Norte (demo)", kind: "hospital", lat: 40.4807, lon: -3.6930, validated: false },
  { facility_id: "hosp_sur", name: "Hospital Sur (demo)", kind: "hospital", lat: 40.3457, lon: -3.8249, validated: false },
  { facility_id: "hosp_lejano", name: "Hospital Costa (demo, pierna aérea)", kind: "hospital", lat: 39.4699, lon: -0.3763, validated: false },
];

const LEG_STYLE: Record<string, string> = {
  road: "text-cyan-300",
  tdg_buffer: "text-amber-300",
  flight: "text-violet-300",
  courier: "text-emerald-300",
};
const LEG_LABEL: Record<string, string> = {
  road: "Carretera", tdg_buffer: "Buffer TDG", flight: "Vuelo", courier: "Mensajería",
};

/** Logistics Twin: rutas terrestre/aérea con decaimiento en tránsito. */
export default function LogisticaSection({ data, cfg, selected }: Props) {
  const [facilities, setFacilities] = useState<FacilityItem[]>(DEMO_FACILITIES);
  const [destId, setDestId] = useState<string>("hosp_norte");
  const [mode, setMode] = useState<string>("road");
  const [route, setRoute] = useState<LogisticsRoute | null>(null);
  const [reach, setReach] = useState<Reachability | null>(null);
  const [busy, setBusy] = useState(false);

  const batch = data.batches.find((b) => b.batch_id === selected);
  const eos = batch?.results?.eob_activity_gbq ?? 0;
  const protoId = "fdg_18f";
  const origin = facilities.find((f) => f.kind === "cyclotron") ?? facilities[0];
  const hospitales = useMemo(
    () => facilities.filter((f) => f.kind === "hospital"), [facilities]);

  useEffect(() => {
    listFacilities(cfg).then(setFacilities).catch(() => { /* demo */ });
  }, [cfg]);

  const doRoute = async () => {
    if (!origin || !(eos > 0)) {
      toast.error("Selecciona un lote con actividad EOB");
      return;
    }
    setBusy(true);
    try {
      setRoute(await routeLogistics(cfg, {
        origin_id: origin.facility_id, dest_id: destId,
        protocol_id: protoId, eos_activity_gbq: eos, mode }));
    } catch (e) {
      setRoute(null);
      toast.error(`Ruta falló: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const doReach = async () => {
    if (!origin || !(eos > 0)) {
      toast.error("Selecciona un lote con actividad EOB");
      return;
    }
    setBusy(true);
    try {
      setReach(await reachabilityLogistics(cfg, {
        origin_id: origin.facility_id, protocol_id: protoId,
        eos_activity_gbq: eos }));
    } catch (e) {
      toast.error(`Alcanzabilidad falló: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card className="border-slate-800 bg-slate-900/60">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm text-slate-200">
            <Route className="h-4 w-4 text-cyan-400" />
            Ruta de distribución (EOS del lote {selected || "—"}: {eos.toFixed(1)} GBq)
            <Badge variant="outline" className="border-amber-700 text-amber-400">
              instalaciones demo — coordenadas sin validar
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-4">
          <div>
            <Label className="text-xs text-slate-400">Destino</Label>
            <Select value={destId} onValueChange={setDestId}>
              <SelectTrigger className="h-8 border-slate-700 bg-slate-900 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="border-slate-700 bg-slate-900">
                {hospitales.map((f) => (
                  <SelectItem key={f.facility_id} value={f.facility_id} className="text-xs">
                    {f.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs text-slate-400">Modo</Label>
            <Select value={mode} onValueChange={setMode}>
              <SelectTrigger className="h-8 border-slate-700 bg-slate-900 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="border-slate-700 bg-slate-900">
                <SelectItem value="road" className="text-xs">
                  <span className="flex items-center gap-1"><Truck className="h-3 w-3" />Terrestre</span>
                </SelectItem>
                <SelectItem value="air" className="text-xs">
                  <span className="flex items-center gap-1"><Plane className="h-3 w-3" />Aéreo (TDG + vuelo)</span>
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-end">
            <Button size="sm" onClick={doRoute} disabled={busy}
                    className="h-8 w-full bg-cyan-700 hover:bg-cyan-600">
              Calcular ruta
            </Button>
          </div>
          <div className="flex items-end">
            <Button size="sm" variant="outline" onClick={doReach} disabled={busy}
                    className="h-8 w-full border-slate-700 text-xs">
              <Radar className="mr-1 h-3.5 w-3.5" />Alcanzabilidad
            </Button>
          </div>
        </CardContent>
      </Card>

      {route && (
        <Card className="border-slate-800 bg-slate-900/60">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-slate-200">
              {route.origin} → {route.destination}
              <span className="ml-2 text-xs font-normal text-slate-500">
                ({route.routing_source})
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="grid gap-3 md:grid-cols-4">
              <div className="rounded border border-slate-800 p-3">
                <p className="text-xs text-slate-500">Tiempo total</p>
                <p className="text-xl font-semibold text-slate-200">
                  {route.total_minutes.toFixed(0)} min
                </p>
                <p className="text-xs text-slate-500">{route.total_distance_km.toFixed(0)} km</p>
              </div>
              <div className="rounded border border-slate-800 p-3">
                <p className="text-xs text-slate-500">Actividad a la llegada</p>
                <p className="text-xl font-semibold text-cyan-300">
                  {route.arrival_activity_gbq.toFixed(2)} GBq
                </p>
                <p className="text-xs text-slate-500">
                  de {route.eos_activity_gbq.toFixed(1)} GBq (×{route.decay_factor.toFixed(3)})
                </p>
              </div>
              <div className="rounded border border-slate-800 p-3">
                <p className="text-xs text-slate-500">Dosis en destino</p>
                <p className="text-xl font-semibold text-emerald-300">
                  {route.patient_doses_on_arrival}
                </p>
              </div>
              <div className="rounded border border-slate-800 p-3">
                <p className="text-xs text-slate-500">Modo</p>
                <p className="text-xl font-semibold text-slate-200">
                  {route.mode === "air" ? "Aéreo" : "Terrestre"}
                </p>
              </div>
            </div>
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-left text-slate-500">
                  <th className="py-1.5 pr-2">Pierna</th>
                  <th className="py-1.5 pr-2">Trayecto</th>
                  <th className="py-1.5 pr-2 text-right">Duración</th>
                  <th className="py-1.5 text-right">Distancia</th>
                </tr>
              </thead>
              <tbody>
                {route.legs.map((l, i) => (
                  <tr key={i} className="border-b border-slate-800/60 text-slate-300">
                    <td className={`py-1.5 pr-2 ${LEG_STYLE[l.kind] ?? ""}`}>
                      {LEG_LABEL[l.kind] ?? l.kind}
                    </td>
                    <td className="py-1.5 pr-2">{l.origin} → {l.destination}</td>
                    <td className="py-1.5 pr-2 text-right">{l.duration_min.toFixed(0)} min</td>
                    <td className="py-1.5 text-right">{l.distance_km.toFixed(1)} km</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {reach && (
        <Card className="border-slate-800 bg-slate-900/60">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-slate-200">
              Alcanzabilidad desde {reach.origin}
              <span className="ml-2 text-xs font-normal text-slate-500">
                presupuesto para 1 dosis: {reach.max_delivery_minutes_one_dose.toFixed(0)} min
                (T½ {reach.half_life_min} min)
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-left text-slate-500">
                  <th className="py-1 pr-2">Hospital</th>
                  <th className="py-1 pr-2 text-right">Ruta</th>
                  <th className="py-1 pr-2 text-right">Llegada</th>
                  <th className="py-1 text-right">¿1 dosis?</th>
                </tr>
              </thead>
              <tbody>
                {reach.facilities.map((f) => (
                  <tr key={f.facility_id} className="border-b border-slate-800/60 text-slate-300">
                    <td className="py-1 pr-2">{f.name}</td>
                    <td className="py-1 pr-2 text-right">{f.travel_minutes.toFixed(0)} min</td>
                    <td className="py-1 pr-2 text-right text-cyan-300">
                      {f.arrival_activity_gbq.toFixed(2)} GBq
                    </td>
                    <td className={`py-1 text-right ${f.feasible_one_dose ? "text-emerald-400" : "text-red-400"}`}>
                      {f.feasible_one_dose ? "sí" : "no"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-left text-slate-500">
                  <th className="py-1 pr-2 text-right">Banda</th>
                  <th className="py-1 pr-2 text-right">Radio aprox.</th>
                  <th className="py-1 text-right">Actividad a esa hora</th>
                </tr>
              </thead>
              <tbody>
                {reach.bands.map((b) => (
                  <tr key={b.minutes} className="border-b border-slate-800/60 text-slate-300">
                    <td className="py-1 pr-2 text-right">{b.minutes} min</td>
                    <td className="py-1 pr-2 text-right">{b.radius_km.toFixed(0)} km</td>
                    <td className="py-1 text-right text-cyan-300">
                      {b.arrival_activity_gbq.toFixed(2)} GBq
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
