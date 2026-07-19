/**
 * Acciones operativas de la consola (modo en vivo): replican los pipelines CLI
 * desde el navegador — registrar lote, evaluar QC, liberar, firmar eBR,
 * simular telemetría.
 */
import type { ConsoleConfig } from "./console-data";

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
