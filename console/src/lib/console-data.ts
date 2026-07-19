/**
 * Radiopharma OS Console — capa de datos.
 *
 * Intenta leer de los microservicios reales (Data Lake :8003, Telemetry :8006)
 * con el token JWT configurado; si no son alcanzables, cae al dataset de
 * demostración (determinista) para previsualización.
 */

export interface Batch {
  batch_id: string;
  created_at: string;
  created_by: string;
  reaction_id: string;
  target_id: string;
  product_nuclide: string;
  beam: { beam_energy_mev: number; current_ua: number; irradiation_time_min: number };
  results: { eob_activity_gbq: number; eob_activity_gbq_uncertainty: number; saturation_factor: number };
  status: string;
  release_status: string;
  released_by?: string | null;
  release_reason?: string | null;
  released_at?: string | null;
  record_hash: string;
  integrity_ok: boolean;
}

export interface QcRule { parameter: string; measured: number | string; status: string; limits?: string; detail?: string }

export interface QcReport {
  qc_id: string; batch_id: string; created_at: string; created_by: string;
  product: string; nuclide: string; overall_status: string;
  rules: QcRule[]; record_hash: string; integrity_ok: boolean;
}

export interface Signature { signature_id: string; meaning: string; signed_by: string; signed_at: string; signature_hash: string }

export interface AuditEvent { timestamp: string; actor: string; action: string; detail: string }

export interface Ebr {
  ebr_id: string; generated_at: string;
  signatures: Signature[]; audit_trail: AuditEvent[];
  integrity: { algorithm: string; document_hash: string };
}

export interface TelemetryPoint { t: number; v: number }  // t: minutos desde inicio
export interface SeriesStat { series: string; count: number; mean: number; minimum: number; maximum: number; stddev: number }
export interface TelemetrySeries { series: string; unit: string; points: TelemetryPoint[] }

export interface ServiceHealth { key: string; name: string; port: number; status: "ok" | "down"; version: string; latency_ms: number }

export interface TrendPoint {
  batch_id: string; created_at: string; eob_activity_gbq: number;
  eob_per_uah: number; saturation_yield_mbq_ua: number;
  status: string; release_status: string;
  warning: boolean; out_of_control: boolean;
}
export interface EobTrend {
  reaction_id: string | null; n_batches: number; points: TrendPoint[];
  mean: number | null; std: number | null;
  ucl: number | null; lcl: number | null; uwl: number | null; lwl: number | null;
  slope_pct_per_day: number | null; r_squared: number | null;
  direction: "stable" | "improving" | "declining";
  alerts: string[];
}

export interface ConsoleData {
  mode: "live" | "demo";
  fetched_at: string;
  batches: Batch[];
  qc: Record<string, QcReport[]>;
  ebr: Record<string, Ebr>;
  telemetry: Record<string, TelemetrySeries[]>;
  telemetry_stats: Record<string, SeriesStat[]>;
  trends: Record<string, EobTrend>;
  services: ServiceHealth[];
}

export interface ConsoleConfig {
  dlUrl: string; telUrl: string; token: string;
  authUrl: string; yeUrl: string; ndsUrl: string; qcUrl: string;
}

const CFG_VERSION = "2"; // 2 = defaults relativos (proxy nginx same-origin)

export function loadConfig(): ConsoleConfig {
  // Por defecto la consola usa prefijos relativos de mismo origen: en
  // docker-compose nginx los proxifica a cada microservicio (/dl -> data-lake:8003,
  // etc.), sin CORS ni configuración. Para desarrollo contra servicios sueltos,
  // sobreescribir con URLs absolutas (p. ej. http://localhost:8003) en Ajustes.
  if (localStorage.getItem("rpos.cfgver") !== CFG_VERSION) {
    // Migración v0.13 -> v0.14: descarta URLs absolutas guardadas (localhost:800X)
    // para que tomen efecto los nuevos defaults relativos; conserva token y sesión.
    for (const k of ["dlUrl", "telUrl", "authUrl", "yeUrl", "ndsUrl", "qcUrl"])
      localStorage.removeItem(`rpos.${k}`);
    localStorage.setItem("rpos.cfgver", CFG_VERSION);
  }
  return {
    dlUrl: localStorage.getItem("rpos.dlUrl") || "/dl",
    telUrl: localStorage.getItem("rpos.telUrl") || "/tel",
    token: localStorage.getItem("rpos.token") || "",
    authUrl: localStorage.getItem("rpos.authUrl") || "/auth",
    yeUrl: localStorage.getItem("rpos.yeUrl") || "/ye",
    ndsUrl: localStorage.getItem("rpos.ndsUrl") || "/nds",
    qcUrl: localStorage.getItem("rpos.qcUrl") || "/qc",
  };
}
export function saveConfig(c: ConsoleConfig) {
  localStorage.setItem("rpos.dlUrl", c.dlUrl);
  localStorage.setItem("rpos.telUrl", c.telUrl);
  localStorage.setItem("rpos.token", c.token);
  localStorage.setItem("rpos.authUrl", c.authUrl);
  localStorage.setItem("rpos.yeUrl", c.yeUrl);
  localStorage.setItem("rpos.ndsUrl", c.ndsUrl);
  localStorage.setItem("rpos.qcUrl", c.qcUrl);
}

/* ------------------------------------------------------------------ live */
const SERVICES = [
  { key: "nds", name: "Nuclear Data", cfgKey: "ndsUrl" },
  { key: "ye", name: "Yield Engine", cfgKey: "yeUrl" },
  { key: "dl", name: "Data Lake", cfgKey: "dlUrl" },
  { key: "auth", name: "Auth Service", cfgKey: "authUrl" },
  { key: "qc", name: "QC Engine", cfgKey: "qcUrl" },
  { key: "tel", name: "Telemetry", cfgKey: "telUrl" },
] as const;

export function serviceLabel(url: string): string {
  if (url.startsWith("/")) return url;
  try { return `:${new URL(url).port}`; } catch { return url; }
}

async function probe(name: string, key: string, base: string): Promise<ServiceHealth> {
  const t0 = performance.now();
  const port = base.startsWith("/") ? 0 : Number(serviceLabel(base).replace(":", "")) || 0;
  try {
    const ctrl = new AbortController();
    const to = setTimeout(() => ctrl.abort(), 2500);
    const r = await fetch(`${base}/health`, { signal: ctrl.signal });
    clearTimeout(to);
    const j = await r.json();
    return { key, name, port, status: "ok", version: j.version ?? "—", latency_ms: Math.round(performance.now() - t0) };
  } catch {
    return { key, name, port, status: "down", version: "—", latency_ms: 0 };
  }
}

export async function fetchConsole(cfg: ConsoleConfig): Promise<ConsoleData> {
  const headers = { Authorization: `Bearer ${cfg.token}` };
  const services = await Promise.all(
    SERVICES.map((s) => probe(s.name, s.key, cfg[s.cfgKey])));
  try {
    const ctrl = new AbortController();
    const to = setTimeout(() => ctrl.abort(), 4000);
    const r = await fetch(`${cfg.dlUrl}/api/v1/batches?limit=20`, { headers, signal: ctrl.signal });
    clearTimeout(to);
    if (!r.ok) throw new Error(String(r.status));
    const batches: Batch[] = await r.json();
    const qc: ConsoleData["qc"] = {};
    const ebr: ConsoleData["ebr"] = {};
    const telemetry: ConsoleData["telemetry"] = {};
    const telemetry_stats: ConsoleData["telemetry_stats"] = {};
    await Promise.all(batches.slice(0, 8).map(async (b) => {
      try {
        const rq = await fetch(`${cfg.dlUrl}/api/v1/batches/${b.batch_id}/qc-reports`, { headers });
        if (rq.ok) qc[b.batch_id] = await rq.json();
        const re = await fetch(`${cfg.dlUrl}/api/v1/batches/${b.batch_id}/ebr`, { headers });
        if (re.ok) ebr[b.batch_id] = await re.json();
        const rs = await fetch(`${cfg.telUrl}/api/v1/telemetry/batches/${b.batch_id}/summary`, { headers });
        if (rs.ok) {
          const s = await rs.json();
          telemetry_stats[b.batch_id] = s.series ?? [];
          // puntos diezmados LTTB por serie (forma preservada, carga acotada)
          const seriesArr: TelemetrySeries[] = [];
          for (const st of (s.series ?? []) as SeriesStat[]) {
            const rp = await fetch(`${cfg.telUrl}/api/v1/telemetry/query?series=${st.series}&batch_id=${b.batch_id}&limit=100000&max_points=400&method=lttb`, { headers });
            if (rp.ok) {
              const pts = await rp.json();
              const t0 = pts.length ? new Date(pts[0].ts).getTime() : 0;
              seriesArr.push({
                series: st.series,
                unit: unitOf(st.series),
                points: pts.map((p: { ts: string; value: number }) => ({
                  t: +(((new Date(p.ts).getTime()) - t0) / 60000).toFixed(2),
                  v: p.value,
                })),
              });
            }
          }
          if (seriesArr.length) telemetry[b.batch_id] = seriesArr;
        }
      } catch { /* lote parcial */ }
    }));
    // trending EOB por reacción (control chart GMP)
    const trends: ConsoleData["trends"] = {};
    const reactions = [...new Set(batches.map((b) => b.reaction_id))];
    await Promise.all(reactions.slice(0, 4).map(async (rx) => {
      try {
        const rt = await fetch(`${cfg.dlUrl}/api/v1/analytics/eob-trend?reaction_id=${rx}&limit=50`, { headers });
        if (rt.ok) trends[rx] = await rt.json();
      } catch { /* sin trending */ }
    }));
    return { mode: "live", fetched_at: new Date().toISOString(), batches, qc, ebr, telemetry, telemetry_stats, trends, services };
  } catch {
    return demoData(services);
  }
}

export function unitOf(series: string): string {
  if (series.includes("current")) return "µA";
  if (series.includes("pressure")) return "psi";
  if (series.includes("flow")) return "L/min";
  return "";
}

/* ------------------------------------------------------------------ demo */
function rng(seed: number) { let s = seed; return () => ((s = (s * 16807) % 2147483647) / 2147483647); }

function demoTelemetry(batch: string, duracionMin: number, corriente: number): TelemetrySeries[] {
  const rand = rng(42);
  const gauss = () => (rand() + rand() + rand() + rand() - 2) * 0.6;
  const mk = (series: string, unit: string, f: (frac: number) => number): TelemetrySeries => {
    const pts: TelemetryPoint[] = [];
    const n = Math.round(duracionMin * 6);
    for (let i = 0; i < n; i++) pts.push({ t: +((duracionMin * i) / (n - 1)).toFixed(2), v: +f(i / (n - 1)).toFixed(3) });
    return { series, unit, points: pts };
  };
  void batch;
  return [
    mk("beam_current_ua", "µA", (x) => corriente * Math.min(1, x / 0.05) * (1 - 0.01 * x) + gauss() * 0.25),
    mk("target_pressure_psi", "psi", (x) => 320 + 25 * Math.min(1, x / 0.05) + gauss() * 1.3),
    mk("cooling_flow_lpm", "L/min", (x) => 12 + 0.4 * Math.sin(x * Math.PI * 4) + gauss() * 0.09),
  ];
}

function statsOf(series: string, pts: TelemetryPoint[]): SeriesStat {
  const vals = pts.map((p) => p.v);
  const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
  const sd = Math.sqrt(vals.reduce((a, v) => a + (v - mean) ** 2, 0) / vals.length);
  return { series, count: vals.length, mean: +mean.toFixed(3), minimum: Math.min(...vals), maximum: Math.max(...vals), stddev: +sd.toFixed(3) };
}

function demoData(services: ServiceHealth[]): ConsoleData {
  const mkBatch = (id: string, nuclide: string, reaction: string, target: string,
                   e: number, ua: number, min: number, eob: number, unc: number,
                   status: string, rel: string, by: string | null, day: string): Batch => ({
    batch_id: id, created_at: `${day}T00:13:59+00:00`, created_by: "operador.ciclotron",
    reaction_id: reaction, target_id: target, product_nuclide: nuclide,
    beam: { beam_energy_mev: e, current_ua: ua, irradiation_time_min: min },
    results: { eob_activity_gbq: eob, eob_activity_gbq_uncertainty: unc, saturation_factor: 0.3154 },
    status, release_status: rel,
    released_by: by, release_reason: by ? "Liberado conforme a QC" : null,
    released_at: by ? `${day}T00:14:10+00:00` : null,
    record_hash: "c1bea014dd2be0f1".padEnd(64, "0"), integrity_ok: true,
  });

  const batches = [
    mkBatch("B-20260718-215B7A9F", "18F", "o18_p_n_f18", "h2_18o", 16.5, 37, 60, 108.95, 8.1, "completed", "released", "qa.jefe", "2026-07-18"),
    mkBatch("B-20260719-C8DF8D6C", "11C", "n14_p_a_c11", "n2_gas", 16.0, 40, 30, 188.69, 18.5, "completed", "released", "qa.jefe", "2026-07-19"),
    mkBatch("B-20260719-7F3E21AA", "68Ga", "zn68_p_n_ga68", "zn68", 14.5, 25, 60, 146.12, 10.0, "completed", "pending", null, "2026-07-19"),
    mkBatch("B-20260717-9E1B04D2", "15O", "n15_p_n_o15", "n15_gas", 16.0, 20, 5, 96.0, 9.4, "voided", "pending", null, "2026-07-17"),
  ];

  const qc: ConsoleData["qc"] = {
    "B-20260718-215B7A9F": [{
      qc_id: "QC-20260718-9A344701", batch_id: "B-20260718-215B7A9F",
      created_at: "2026-07-18T00:14:10+00:00", created_by: "operador.ciclotron",
      product: "fdg", nuclide: "18F", overall_status: "pass",
      rules: [
        { parameter: "ph", measured: 6.8, status: "pass", limits: "[4.5, 8.5]" },
        { parameter: "radiochemical_purity", measured: 0.985, status: "pass", limits: "≥ 0.95" },
        { parameter: "radionuclidic_purity", measured: 0.9999, status: "pass", limits: "≥ 0.999" },
        { parameter: "kryptofix_222", measured: 1.8, status: "pass", limits: "≤ 2.2 g/L" },
        { parameter: "endotoxins_eu_ml", measured: 5.0, status: "pass", limits: "≤ 17.5 EU/mL" },
        { parameter: "acetonitrile_mg_dose", measured: 2.0, status: "pass", limits: "≤ 4.1 mg/dosis" },
      ],
      record_hash: "aa11bb22".padEnd(64, "0"), integrity_ok: true,
    }],
    "B-20260719-C8DF8D6C": [{
      qc_id: "QC-20260719-6D76E361", batch_id: "B-20260719-C8DF8D6C",
      created_at: "2026-07-19T00:27:28+00:00", created_by: "operador.ciclotron",
      product: "generic_pet", nuclide: "11C", overall_status: "pass",
      rules: [
        { parameter: "radionuclidic_purity", measured: 0.99999, status: "pass", limits: "≥ 0.999" },
        { parameter: "radiochemical_purity", measured: 0.99, status: "pass", limits: "≥ 0.95" },
      ],
      record_hash: "cc33dd44".padEnd(64, "0"), integrity_ok: true,
    }],
  };

  const sig = (meaning: string, by: string, at: string): Signature => ({
    signature_id: crypto.randomUUID?.() ?? String(Math.random()),
    meaning, signed_by: by, signed_at: at,
    signature_hash: "495cc81c1f142185".padEnd(64, "a"),
  });
  const ebrTrail = (day: string, b: string): AuditEvent[] => [
    { timestamp: `${day}T00:13:59Z`, actor: "operador.ciclotron", action: "batch_registered", detail: `reacción · blanco · hash ${b.slice(0, 12)}…` },
    { timestamp: `${day}T00:14:10Z`, actor: "operador.ciclotron", action: "qc_report_registered", detail: "resultado global: pass" },
    { timestamp: `${day}T00:14:10Z`, actor: "qa.jefe", action: "batch_released", detail: "Liberado conforme a QC" },
    { timestamp: `${day}T00:14:21Z`, actor: "operador.ciclotron", action: "signature_performed_by", detail: "firma 495cc81c1f14…" },
    { timestamp: `${day}T00:14:22Z`, actor: "supervisor.turno", action: "signature_reviewed_by", detail: "firma 236129a47b0b…" },
    { timestamp: `${day}T00:14:22Z`, actor: "qa.jefe", action: "signature_approved_by", detail: "firma 9645e94cc716…" },
  ];
  const mkEbr = (day: string, id: string): Ebr => ({
    ebr_id: "266278fd-4e17-4229-a858-1984d194d285",
    generated_at: `${day}T00:14:33Z`,
    signatures: [
      sig("performed_by", "operador.ciclotron", `${day}T00:14:21Z`),
      sig("reviewed_by", "supervisor.turno", `${day}T00:14:22Z`),
      sig("approved_by", "qa.jefe", `${day}T00:14:22Z`),
    ],
    audit_trail: ebrTrail(day, id),
    integrity: { algorithm: "sha256", document_hash: "127fd273a64cd20a".padEnd(64, "f") },
  });
  const ebr: ConsoleData["ebr"] = {
    "B-20260718-215B7A9F": mkEbr("2026-07-18", "B-20260718-215B7A9F"),
    "B-20260719-C8DF8D6C": mkEbr("2026-07-19", "B-20260719-C8DF8D6C"),
  };

  const tel11 = demoTelemetry("B-20260719-C8DF8D6C", 30, 40);
  const tel18 = demoTelemetry("B-20260718-215B7A9F", 60, 37);
  const telemetry: ConsoleData["telemetry"] = {
    "B-20260719-C8DF8D6C": tel11,
    "B-20260718-215B7A9F": tel18,
  };
  const telemetry_stats: ConsoleData["telemetry_stats"] = {
    "B-20260719-C8DF8D6C": tel11.map((s) => statsOf(s.series, s.points)),
    "B-20260718-215B7A9F": tel18.map((s) => statsOf(s.series, s.points)),
  };

  // trending demo: 10 corridas 18F estables con un punto en zona de aviso
  const rnd = rng(42);
  const pts: TrendPoint[] = [];
  for (let i = 0; i < 10; i++) {
    const eob = 108.9 + (i === 6 ? 1.9 : (rnd() - 0.5) * 1.1);
    pts.push({
      batch_id: `B-202607${String(9 + i).padStart(2, "0")}-DEMO${String(i).padStart(4, "0")}`,
      created_at: `2026-07-${String(9 + i).padStart(2, "0")}T00:13:59+00:00`,
      eob_activity_gbq: +eob.toFixed(2), eob_per_uah: +(eob / 37).toFixed(3),
      saturation_yield_mbq_ua: 9336.8, status: "completed",
      release_status: "released", warning: i === 6, out_of_control: false,
    });
  }
  const mean = 2.955, std = 0.019;
  const trends: ConsoleData["trends"] = {
    o18_p_n_f18: {
      reaction_id: "o18_p_n_f18", n_batches: pts.length, points: pts,
      mean, std, ucl: mean + 3 * std, lcl: mean - 3 * std,
      uwl: mean + 2 * std, lwl: mean - 2 * std,
      slope_pct_per_day: 0.04, r_squared: 0.01, direction: "stable",
      alerts: ["B-20260715-DEMO0006 en zona de aviso (2σ): 2.99 GBq/µA·h"],
    },
  };

  return {
    mode: "demo", fetched_at: new Date().toISOString(),
    batches, qc, ebr, telemetry, telemetry_stats, trends,
    services: services.every((s) => s.status === "down")
      ? SERVICES.map((s, i) => ({ key: s.key, name: s.name, port: 0,
                                  status: "ok" as const, version: "0.1.0",
                                  latency_ms: 3 + i * 2 }))
      : services,
  };
}
