/**
 * Sesión de la consola: token JWT del Auth Service + identidad decodificada.
 */

export interface Session {
  token: string;
  username: string;
  role: string;
  exp: number;
}

const ROLE_RANK: Record<string, number> = { operador: 1, supervisor: 2, calidad: 3, admin: 4 };

export function roleRank(role: string): number {
  return ROLE_RANK[role] ?? 0;
}

export function decodeSession(token: string): Session | null {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return {
      token,
      username: payload.sub ?? "",
      role: payload.role ?? "operador",
      exp: payload.exp ?? 0,
    };
  } catch {
    return null;
  }
}

export function loadSession(): Session | null {
  const token = localStorage.getItem("rpos.session") ?? "";
  if (!token) return null;
  const s = decodeSession(token);
  if (!s || s.exp * 1000 < Date.now()) {
    localStorage.removeItem("rpos.session");
    return null;
  }
  return s;
}

export function saveSession(token: string): Session | null {
  const s = decodeSession(token);
  if (s) localStorage.setItem("rpos.session", token);
  return s;
}

export function clearSession() {
  localStorage.removeItem("rpos.session");
}
