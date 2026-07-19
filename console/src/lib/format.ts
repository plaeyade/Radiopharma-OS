export const fmtTs = (iso?: string | null) =>
  iso ? iso.replace("T", " ").replace(/(\+\d\d:\d\d|Z)$/, " UTC").slice(0, 25) : "—";

export const shortHash = (h?: string | null, n = 12) => (h ? `${h.slice(0, n)}…` : "—");

export const estadoColor: Record<string, string> = {
  pass: "text-emerald-400",
  released: "text-emerald-400",
  completed: "text-emerald-400",
  fail: "text-red-400",
  rejected: "text-red-400",
  voided: "text-red-400",
  pending: "text-amber-400",
  warning: "text-amber-400",
};

export const badgeVariant = (v: string): "default" | "secondary" | "destructive" | "outline" => {
  if (["pass", "released", "completed", "ok"].includes(v)) return "default";
  if (["fail", "rejected", "voided", "down"].includes(v)) return "destructive";
  if (["pending", "warning"].includes(v)) return "secondary";
  return "outline";
};

export const MEANING_ES: Record<string, string> = {
  performed_by: "Realizado por",
  reviewed_by: "Revisado por",
  approved_by: "Aprobado por",
};
