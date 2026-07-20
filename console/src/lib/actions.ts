/**
 * Acciones operativas de la consola (modo en vivo): replican los pipelines CLI
 * desde el navegador — registrar lote, evaluar QC, liberar, firmar eBR,
 * simular telemetría.
 */
import type { AlertItem, ConsoleConfig } from "./console-data";

const T = 15000;

async function req<T>(method: string, url: string, token?: string, body?: unknown): Promise<T> {
  const ctrl = new AbortController();
  const to = setTimeout(() => ctrl.abort(), T);
  try {
    const r = await fetch(url, {
      method,
      signal: ctrl.signal,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!r.ok) {
      const txt = await r.text().catch(() => "");
      let msg = txt;
      try { msg = JSON.parse(txt).detail ?? txt; } catch { /* texto plano */ }
      throw new Error(`${r.status}: ${msg}`);
    }
    return (await r.json()) as T;
  } finally {
    clearTimeout(to);
  }
}

/* ------------------------------------------------------------- catálogos */
export interface ReactionDef { id: string; notation: string; product_nuclide: string; targets: string[] }

export const REACTIONS: ReactionDef[] = [
  { id: "o18_p_n_f18", notation: "¹⁸O(p,n)¹⁸F", product_nuclide: "18F", targets: ["h2_18o", "o2_18"] },
  { id: "n14_p_a_c11", notation: "¹⁴N(p,α)¹¹C", product_nuclide: "11C", targets: ["n2_gas"] },
  { id: "n15_p_n_o15", notation: "¹⁵N(p,n)¹⁵O", product_nuclide: "15O", targets: ["n15_gas"] },
  { id: "zn68_p_n_ga68", notation: "⁶⁸Zn(p,n)⁶⁸Ga", product_nuclide: "68Ga", targets: ["zn68"] },
];

export const TARGET_ES: Record<string, string> = {
  h2_18o: "[¹⁸O]H₂O enriquecida",
  o2_18: "[¹⁸O]O₂ gaseoso",
  n2_gas: "N₂ + 0.5 % O₂ (gas)",
  n15_gas: "[¹⁵N]N₂ gaseoso",
  zn68: "Blanco sólido ⁶⁸Zn",
};

/* ---------------------------------------------------------------- login */
export interface LoginTokens {
  access_token: string; refresh_token?: string | null;
  expires_in_min: number; refresh_expires_in_min?: number | null;
}
export interface LoginResult extends Partial<LoginTokens> {
  mfa_required?: boolean; mfa_token?: string;
}

export async function login(cfg: ConsoleConfig, username: string, password: string): Promise<LoginResult> {
  // Si el usuario tiene MFA activo devuelve {mfa_required, mfa_token}
  return req<LoginResult>("POST", `${cfg.authUrl}/api/v1/auth/login`,
    undefined, { username, password });
}

/* ------------------------------------------------------- MFA TOTP ------- */
export async function verifyMfa(cfg: ConsoleConfig, mfaToken: string,
                                code: string): Promise<LoginTokens> {
  return req<LoginTokens>("POST", `${cfg.authUrl}/api/v1/auth/mfa/verify`,
    undefined, { mfa_token: mfaToken, code });
}

export interface MfaEnrollResult { secret: string; otpauth_uri: string }

export async function mfaEnroll(cfg: ConsoleConfig, token: string): Promise<MfaEnrollResult> {
  return req<MfaEnrollResult>("POST", `${cfg.authUrl}/api/v1/auth/mfa/enroll`, token);
}

export async function mfaConfirm(cfg: ConsoleConfig, token: string,
                                 code: string): Promise<{ recovery_codes: string[] }> {
  return req<{ recovery_codes: string[] }>(
    "POST", `${cfg.authUrl}/api/v1/auth/mfa/confirm`, token, { code });
}

export async function mfaDisable(cfg: ConsoleConfig, token: string,
                                 code: string): Promise<void> {
  await req("POST", `${cfg.authUrl}/api/v1/auth/mfa/disable`, token, { code });
}

/* ----------------------------------------------------------- nuevo lote */
export interface NewBatchInput {
  reaction_id: string; target_id: string;
  beam_energy_mev: number; current_ua: number; irradiation_time_min: number;
}

export async function registerBatch(cfg: ConsoleConfig, token: string, input: NewBatchInput): Promise<{ batch_id: string }> {
  // 1) Yield Engine: física de producción
  const prod = await req<Record<string, unknown>>("POST", `${cfg.yeUrl}/api/v1/production`, undefined, {
    reaction_id: input.reaction_id, target_id: input.target_id,
    beam_energy_mev: input.beam_energy_mev, current_ua: input.current_ua,
    irradiation_time_min: input.irradiation_time_min,
  });
  // 2) NDS: linaje (sha256 del dataset)
  const datasets = await req<Array<{ id: string; sha256?: string }>>("GET", `${cfg.ndsUrl}/api/v1/datasets`);
  const sha = datasets.find((d) => d.id === prod.dataset_id)?.sha256 ?? null;
  // 3) Data Lake: registro ALCOA+
  return req("POST", `${cfg.dlUrl}/api/v1/batches`, token, {
    reaction_id: input.reaction_id, target_id: input.target_id,
    product_nuclide: prod.product_nuclide,
    beam: {
      beam_energy_mev: input.beam_energy_mev, current_ua: input.current_ua,
      irradiation_time_min: input.irradiation_time_min,
    },
    results: {
      saturation_yield_mbq_ua: prod.saturation_yield_mbq_ua,
      eob_activity_gbq: prod.eob_activity_gbq,
      eob_activity_gbq_uncertainty: prod.eob_activity_gbq_uncertainty,
      saturation_factor: prod.saturation_factor,
      relative_uncertainty: prod.relative_uncertainty,
    },
    lineage: {
      dataset_id: prod.dataset_id, dataset_sha256: sha,
      stopping_source: prod.stopping_source,
    },
  });
}

/* ------------------------------------------------------------------- QC */
export interface QcInput {
  product: string; nuclide: string;
  measurements: Record<string, number>;
}

export async function evaluateQc(cfg: ConsoleConfig, token: string, batchId: string, input: QcInput): Promise<{ overall_status: string }> {
  const evaluation = await req<{
    overall_status: string;
    rule_evaluations: unknown[];
    half_life_fit?: unknown;
  }>("POST", `${cfg.qcUrl}/api/v1/qc/evaluate`, undefined, {
    product: input.product, nuclide: input.nuclide, measurements: input.measurements,
  });
  await req("POST", `${cfg.dlUrl}/api/v1/batches/${batchId}/qc-reports`, token, {
    product: input.product, nuclide: input.nuclide,
    overall_status: evaluation.overall_status,
    rules: evaluation.rule_evaluations,
    half_life_fit: evaluation.half_life_fit ?? null,
  });
  return evaluation;
}

export async function releaseBatch(cfg: ConsoleConfig, token: string, batchId: string,
                                   decision: "released" | "rejected", reason: string): Promise<void> {
  await req("POST", `${cfg.dlUrl}/api/v1/batches/${batchId}/release`, token,
    { decision, reason });
}

/* ------------------------------------------------------------------ eBR */
export async function signEbr(cfg: ConsoleConfig, token: string, batchId: string,
                              username: string, password: string, meaning: string): Promise<void> {
  await req("POST", `${cfg.dlUrl}/api/v1/batches/${batchId}/signatures`, token,
    { username, password, meaning });
}

/* ------------------------------------------------------------ telemetría */
function rng(seed: number) { let s = seed; return () => ((s = (s * 16807) % 2147483647) / 2147483647); }

export async function simulateRun(cfg: ConsoleConfig, token: string, batchId: string,
                                  duracionMin: number, corriente: number,
                                  excursion = false): Promise<number> {
  const rand = rng(Date.now() % 100000);
  const gauss = () => (rand() + rand() + rand() + rand() - 2) * 0.6;
  const n = Math.max(2, Math.round(duracionMin * 6));
  const t0 = Date.now() - duracionMin * 60000;
  const points: Array<{ series: string; ts: string; value: number; tags: Record<string, string> }> = [];
  for (let i = 0; i < n; i++) {
    const frac = i / (n - 1);
    const ts = new Date(t0 + frac * duracionMin * 60000).toISOString();
    const rampa = Math.min(1, frac / 0.05);
    let caudal = 12 + 0.4 * Math.sin(frac * Math.PI * 4) + gauss() * 0.09;
    let presion = 320 + 25 * rampa + gauss() * 1.3;
    if (excursion && frac >= 0.60 && frac <= 0.66) {
      caudal = 8.5 + gauss() * 0.14;                       // fallo de enfriamiento
      presion += 18 * Math.sin(((frac - 0.60) / 0.06) * Math.PI);  // consecuencia térmica
    }
    const vals: Array<[string, number]> = [
      ["beam_current_ua", corriente * rampa * (1 - 0.01 * frac) + gauss() * 0.25],
      ["target_pressure_psi", presion],
      ["cooling_flow_lpm", caudal],
    ];
    for (const [series, v] of vals) {
      points.push({ series, ts, value: +v.toFixed(3), tags: { batch_id: batchId } });
    }
  }
  let written = 0;
  for (let i = 0; i < points.length; i += 500) {
    const r = await req<{ written: number }>("POST", `${cfg.telUrl}/api/v1/telemetry/points`,
      token, { points: points.slice(i, i + 500) });
    written += r.written;
  }
  return written;
}

/* ---------------------------------------------- desviaciones de proceso */
export interface DeviationEvent {
  series: string; started_at: string; ended_at: string; n_points: number;
  extreme_value: number; limit: number; side: "low" | "high"; unit: string;
  description: string;
}
export interface DeviationCheckResult {
  batch_id: string; pack: string; evaluated_points: number;
  clean: boolean; events: DeviationEvent[];
}

export async function checkDeviations(cfg: ConsoleConfig, token: string,
                                      batchId: string): Promise<DeviationCheckResult> {
  return req<DeviationCheckResult>(
    "POST", `${cfg.telUrl}/api/v1/telemetry/batches/${batchId}/deviation-check`,
    token, { pack: "cyclotron_generic" });
}

export async function registerDeviation(cfg: ConsoleConfig, token: string,
                                        batchId: string, detail: string): Promise<void> {
  await req("POST", `${cfg.dlUrl}/api/v1/batches/${batchId}/events`, token,
    { action: "process_deviation", detail });
}

/* ------------------------------------------------- quemado multizona 1D */
export interface BurnupZoneResult {
  index: number; e_in_mev: number; e_out_mev: number; production_weight: number;
  burnup_xs_mb: number; flux_attenuation: number; burnup_rate_s: number;
  depletion_fraction: number;
}
export interface BurnupProfileResult {
  reaction_id: string; product_nuclide: string; beam_energy_mev: number;
  current_ua: number; irradiation_time_min: number; beam_spot_cm2: number;
  burnup_xs_max_mb: number; n_zones: number; zones: BurnupZoneResult[];
  burnup_rate_max_s: number; depletion_weighted: number; depletion_max: number;
  eob_no_burnup_gbq: number; eob_with_burnup_gbq: number; loss_gbq: number;
  model: string;
}

export async function burnupProfile(cfg: ConsoleConfig, input: {
  reaction_id: string; target_id: string; beam_energy_mev: number;
  current_ua: number; irradiation_time_min: number; n_zones?: number;
}): Promise<BurnupProfileResult> {
  return req<BurnupProfileResult>(
    "POST", `${cfg.yeUrl}/api/v1/production/burnup-multizone`, undefined,
    { beam_spot_cm2: 1.0, n_zones: input.n_zones ?? 10, ...input });
}

/* ---------------------------------------------------------------- alertas */
export async function listAlerts(cfg: ConsoleConfig, token: string,
                                 onlyUnacked = false): Promise<AlertItem[]> {
  return req<AlertItem[]>("GET",
    `${cfg.dlUrl}/api/v1/alerts?limit=50${onlyUnacked ? "&only_unacked=true" : ""}`, token);
}

export async function ackAlert(cfg: ConsoleConfig, token: string,
                               alertId: string): Promise<AlertItem> {
  return req<AlertItem>("POST", `${cfg.dlUrl}/api/v1/alerts/${alertId}/ack`, token);
}

/* ------------------------------------------------------- process twin */
export interface ProcessStepResult {
  name: string; duration_min: number; efficiency: number;
  activity_in_gbq: number; activity_after_decay_gbq: number;
  activity_out_gbq: number;
}
export interface ProcessSimulation {
  protocol_id: string; nuclide: string; half_life_min: number;
  eob_activity_gbq: number; eos_activity_gbq: number;
  total_time_min: number; overall_decay_factor: number;
  overall_efficiency: number; dose_per_patient_gbq: number;
  patient_doses: number; validated: boolean;
  steps: ProcessStepResult[];
}

export async function simulateProcess(cfg: ConsoleConfig, protocolId: string,
                                      eobGbq: number): Promise<ProcessSimulation> {
  return req<ProcessSimulation>(
    "POST", `${cfg.processUrl}/api/v1/process/simulate`, undefined,
    { protocol_id: protocolId, eob_activity_gbq: eobGbq });
}

export async function registerProcessSimEvent(cfg: ConsoleConfig, token: string,
                                              batchId: string, detail: string): Promise<void> {
  await req("POST", `${cfg.dlUrl}/api/v1/batches/${batchId}/events`, token,
    { action: "proceso_simulado", detail });
}

/* ---------------------------------------------------- process twin F2 */
export interface ScheduledStep {
  name: string; start: string; end: string; activity_out_gbq: number;
}
export interface ProcessSchedule {
  protocol_id: string; nuclide: string;
  eos_target_gbq: number; eob_required_gbq: number;
  dose_time: string; beam_start: string; setup_min: number;
  irradiation_time_min: number; eob_time: string;
  total_lead_time_min: number; patient_doses: number;
  validated: boolean; steps: ScheduledStep[];
}

export async function scheduleProcess(cfg: ConsoleConfig, input: {
  protocol_id: string; dose_time: string; irradiation_time_min: number;
  setup_min?: number; eos_target_gbq?: number; target_doses?: number;
}): Promise<ProcessSchedule> {
  return req<ProcessSchedule>(
    "POST", `${cfg.processUrl}/api/v1/process/schedule`, undefined, input);
}

export interface StepBottleneck {
  name: string; loss_gbq: number; decay_loss_gbq: number;
  efficiency_loss_gbq: number; eos_gain_1min_faster_gbq: number;
  eos_gain_1pp_efficiency_gbq: number;
}
export interface ProcessBottleneck {
  protocol_id: string; nuclide: string; eob_activity_gbq: number;
  eos_activity_gbq: number; total_loss_gbq: number;
  dominant_loss_step: string; steps: StepBottleneck[];
}

export async function bottleneckProcess(cfg: ConsoleConfig, protocolId: string,
                                        eobGbq: number): Promise<ProcessBottleneck> {
  return req<ProcessBottleneck>(
    "POST", `${cfg.processUrl}/api/v1/process/bottleneck`, undefined,
    { protocol_id: protocolId, eob_activity_gbq: eobGbq });
}

/* ---------------------------------------------------- process twin F3 */
export interface DoseSlot {
  label: string; time: string; dose_gbq: number;
  inventory_before_gbq: number; feasible: boolean;
  inventory_after_gbq: number;
}
export interface DoseCalendar {
  protocol_id: string; nuclide: string; half_life_min: number;
  eos_activity_gbq: number; eos_time: string;
  required_eos_gbq: number; patients_served: number;
  patients_total: number; total_drawn_gbq: number;
  remaining_after_last_gbq: number; validated: boolean;
  slots: DoseSlot[];
}

export async function doseCalendar(cfg: ConsoleConfig, input: {
  protocol_id: string; eos_activity_gbq: number; eos_time: string;
  appointments: Array<{ time: string; dose_gbq?: number; label?: string }>;
}): Promise<DoseCalendar> {
  return req<DoseCalendar>(
    "POST", `${cfg.processUrl}/api/v1/process/dose-calendar`, undefined, input);
}

/* ---------------------------------------------------- logistics twin */
export interface FacilityItem {
  facility_id: string; name: string; kind: string;
  lat: number; lon: number; validated: boolean;
}
export interface RouteLeg {
  kind: string; origin: string; destination: string;
  duration_min: number; distance_km: number;
}
export interface LogisticsRoute {
  mode: string; origin: string; destination: string;
  legs: RouteLeg[]; total_minutes: number; total_distance_km: number;
  eos_activity_gbq: number; arrival_activity_gbq: number;
  decay_factor: number; patient_doses_on_arrival: number;
  routing_source: string; validated: boolean; notes: string[];
}

export interface DroneItem {
  drone_id: string; name: string; drone_class: string;
  cruise_kmh: number; range_km: number; max_payload_kg: number;
  validated: boolean; note: string; source: string;
}

export async function listDrones(cfg: ConsoleConfig): Promise<DroneItem[]> {
  const r = await fetch(`${cfg.processUrl}/api/v1/logistics/drones`);
  if (!r.ok) throw new Error(`drones ${r.status}`);
  return r.json();
}
export interface ReachBand {
  minutes: number; radius_km: number; arrival_activity_gbq: number;
}
export interface FacilityReach {
  facility_id: string; name: string; kind: string;
  travel_minutes: number; distance_km: number;
  arrival_activity_gbq: number; feasible_one_dose: boolean;
}
export interface Reachability {
  origin: string; nuclide: string; eos_activity_gbq: number;
  half_life_min: number; max_delivery_minutes_one_dose: number;
  bands: ReachBand[]; facilities: FacilityReach[];
  routing_source: string; validated: boolean;
}

export async function listFacilities(cfg: ConsoleConfig): Promise<FacilityItem[]> {
  const r = await fetch(`${cfg.processUrl}/api/v1/logistics/facilities`);
  if (!r.ok) throw new Error(`facilities ${r.status}`);
  return r.json();
}

export async function routeLogistics(cfg: ConsoleConfig, input: {
  origin_id: string; dest_id: string; protocol_id: string;
  eos_activity_gbq: number; mode: string;
  drone_id?: string; shielding_kg?: number;
}): Promise<LogisticsRoute> {
  return req<LogisticsRoute>(
    "POST", `${cfg.processUrl}/api/v1/logistics/route`, undefined, input);
}

export async function reachabilityLogistics(cfg: ConsoleConfig, input: {
  origin_id: string; protocol_id: string; eos_activity_gbq: number;
}): Promise<Reachability> {
  return req<Reachability>(
    "POST", `${cfg.processUrl}/api/v1/logistics/reachability`, undefined, input);
}

/* ------------------------------------------- física: burnup 2D + térmico */
export interface RadialRingResult {
  index: number; r_in_cm: number; r_out_cm: number; r_mean_cm: number;
  flux_rel: number; production_weight: number; burnup_rate_s: number;
  depletion_fraction: number;
}
export interface Burnup2DResult {
  reaction_id: string; product_nuclide: string; beam_energy_mev: number;
  current_ua: number; irradiation_time_min: number; beam_spot_cm2: number;
  beam_sigma_cm: number; spot_radius_cm: number; n_rings: number;
  burnup_xs_max_mb: number; burnup_xs_eff_mb: number;
  flux_peak_cm2_s: number; flux_mean_cm2_s: number; peak_factor: number;
  rings: RadialRingResult[];
  burnup_rate_max_s: number; depletion_weighted: number; depletion_max: number;
  eob_ideal_gbq: number; eob_1d_gbq: number; eob_2d_gbq: number;
  loss_vs_ideal_gbq: number; loss_vs_1d_gbq: number; model: string;
}

export async function burnup2d(cfg: ConsoleConfig, input: {
  reaction_id: string; target_id: string; beam_energy_mev: number;
  current_ua: number; irradiation_time_min: number; beam_spot_cm2: number;
  beam_sigma_cm: number; n_rings?: number;
}): Promise<Burnup2DResult> {
  return req<Burnup2DResult>(
    "POST", `${cfg.yeUrl}/api/v1/production/burnup-2d`, undefined,
    { n_rings: 20, ...input });
}

export interface ThermalResult {
  beam_power_w: number; spot_area_cm2: number;
  heat_flux_mean_w_cm2: number; heat_flux_peak_w_cm2: number;
  peak_factor: number; delta_t_conduction_k: number; delta_t_film_k: number;
  t_peak_k: number; t_mean_k: number; t_limit_k: number; margin_k: number;
  within_limit: boolean; max_current_ua: number; model: string;
}

export async function thermalTarget(cfg: ConsoleConfig, input: {
  beam_energy_mev: number; current_ua: number; beam_spot_cm2: number;
  target_thickness_cm: number; conductivity_w_cm_k: number;
  film_coeff_w_cm2_k: number; coolant_temp_k: number; t_limit_k: number;
  beam_sigma_cm?: number | null;
}): Promise<ThermalResult> {
  return req<ThermalResult>(
    "POST", `${cfg.yeUrl}/api/v1/thermal/target`, undefined, input);
}

export interface ElmerStatus {
  available: boolean; cmd: string; version: string | null; solver: string;
}

export async function elmerStatus(cfg: ConsoleConfig): Promise<ElmerStatus> {
  return req<ElmerStatus>("GET", `${cfg.yeUrl}/api/v1/elmer/status`);
}

export interface ElmerCompareResult {
  t_peak_fem_k: number; t_mean_fem_k: number;
  t_peak_reduced_k: number; t_mean_reduced_k: number;
  peak_rel_diff: number; fem_conservative_bound_ok: boolean;
  solver: string; model: string;
}

export async function elmerCompare(cfg: ConsoleConfig, input: {
  beam_energy_mev: number; current_ua: number; beam_spot_cm2: number;
  target_thickness_cm: number; conductivity_w_cm_k: number;
  film_coeff_w_cm2_k: number; coolant_temp_k: number;
  beam_sigma_cm?: number | null;
}): Promise<ElmerCompareResult> {
  return req<ElmerCompareResult>(
    "POST", `${cfg.yeUrl}/api/v1/elmer/thermal/compare`, undefined, input);
}
