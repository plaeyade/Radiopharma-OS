"""
Motor TPMC propio de vacío molecular (F66) — mapa de presión 3D de la cámara.

Molflow+ (CERN) no es accesible desde el entorno (gitlab.cern.ch 403; sin
binario Linux en mirrors). Implementamos el MISMO algoritmo físico —
test-particle Monte Carlo en régimen molecular, descrito en la literatura
del propio Molflow:
  - TPMC-IPAC14: Ady, Kersevan, "Introduction to the Latest Version of the
    Test-particle Monte Carlo Simulator Molflow+", IPAC'14, WEPME038:
    geometría por facetas; moléculas virtuales desde fuentes hasta bombas;
    reemisión difusa (ley del coseno); impingement rate → presión;
    S = A·v_avg/4·s para bombas.
  - TPMC-IPAC19: Ady, Kersevan, IPAC'19, TUPMP037.

VALIDACIÓN CRUZADA PENDIENTE: correr el mismo caso en Molflow+ cuando haya
binario disponible. Estado: `simulacion_teorica`; motor propio validado
contra casos analíticos (conservación Q_in = Q_absorbido, linealidad en Q,
P_boca = Q/S, modulación 4× por posición de bombas).

Geometría (KIUBE-V04, citas params.yaml): cámara cilíndrica r = 548 mm
(T04F2); gap efectivo 132 mm de valle (CALC S09/T04F1 — simplificación
declarada: los 4 valles dominan el volumen de gas; las colinas de 24 mm
quedan subsumidas en el gap efectivo); 4 agujeros de bombeo r = 127 mm a
r = 375 mm en las tapas (T04F2); 2 fuentes de iones en el centro (TUD03).

Todos los flujos son EST declarados (KIUBE no publica datos de vacío):
la magnitud absoluta de P es tan buena como esos EST; la FORMA del mapa
(gradientes radial y azimutal) es robusta.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

R_GAS = 8.314462618  # J/(mol·K)
K_B = 1.380649e-23   # J/K

FUENTES_VACIO = {
    "algoritmo": ("TPMC-IPAC14: Ady & Kersevan, IPAC'14 WEPME038 + "
                  "TPMC-IPAC19: IPAC'19 TUPMP037 (algoritmo Molflow+)"),
    "geometria": ("KIUBE-V04: cámara r=548 mm y agujeros r=127 mm @ r=375 mm "
                  "(T04F2); gap 132 mm (CALC S09/T04F1); fuentes centrales (TUD03)"),
    "flujos": ("EST declarado: desgasificado pared 1e-10 mbar·l/s/cm² (acero "
               "304L sin hornear, orden típico CERN); H₂ fuentes 1e-3 mbar·l/s "
               "total — pendiente_fuente (KIUBE no publica datos de vacío)"),
    "bombeo": ("EST declarado: 4 ODP, coeficiente de captura s=0,25 en la boca "
               "(orden típico para boca difusora sin trampa; pendiente_fuente)"),
}


@dataclass
class CamaraVacio:
    r_pared_mm: float = 548.0
    gap_mm: float = 132.0
    n_bombas: int = 4
    r_bomba_mm: float = 127.0
    r_pos_bomba_mm: float = 375.0
    s_captura: float = 0.25
    q_pared_mbar_l_s_cm2: float = 1e-10
    q_h2_fuentes_total_mbar_l_s: float = 1e-3
    masa_gas_g_mol: float = 18.015
    temperatura_k: float = 303.0

    @property
    def v_media_mm_s(self) -> float:
        return math.sqrt(8 * R_GAS * self.temperatura_k /
                         (math.pi * self.masa_gas_g_mol / 1000.0)) * 1000.0

    @property
    def area_total_cm2(self) -> float:
        r, h = self.r_pared_mm / 10, self.gap_mm / 10
        return 2 * math.pi * r * r + 2 * math.pi * r * h

    @property
    def q_total_mbar_l_s(self) -> float:
        return (self.q_pared_mbar_l_s_cm2 * self.area_total_cm2
                + self.q_h2_fuentes_total_mbar_l_s)

    @property
    def s_efectiva_l_s(self) -> float:
        # S = A · v_avg/4 · s (TPMC-IPAC14); A cm², v cm/s → l/s
        a_cm2 = math.pi * (self.r_bomba_mm / 10) ** 2
        return (self.n_bombas * a_cm2 * (self.v_media_mm_s / 10) / 4
                * self.s_captura / 1000.0)


def _cosina(normales: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Reemisión difusa (ley del coseno) alrededor de cada normal (n,3)."""
    n = len(normales)
    u1 = rng.random(n)
    u2 = rng.random(n)
    r = np.sqrt(u1)
    phi = 2 * np.pi * u2
    ref = np.where(np.abs(normales[:, 0:1]) > 0.9,
                   np.array([[0.0, 1.0, 0.0]]), np.array([[1.0, 0.0, 0.0]]))
    t1 = ref - np.sum(ref * normales, axis=1, keepdims=True) * normales
    t1 /= np.linalg.norm(t1, axis=1, keepdims=True)
    t2 = np.cross(normales, t1)
    d = (r * np.cos(phi))[:, None] * t1 + (r * np.sin(phi))[:, None] * t2 \
        + np.sqrt(np.maximum(1 - u1, 0.0))[:, None] * normales
    return d / np.linalg.norm(d, axis=1, keepdims=True)


def simular_mapa_presion(cam: CamaraVacio, n_moleculas: int = 400_000,
                         n_bins_r: int = 20, semilla: int = 42) -> dict:
    """TPMC en la cámara cilíndrica → mapa P(r) por impingement en las tapas.

    Presión: P = Z·kB·T·4/v_avg (isotropía local, TPMC-IPAC14), con Z la
    tasa de impingement física (hits/cm²/s) escalada por Q_real/N_virtual.
    """
    rng = np.random.default_rng(semilla)
    R, H = cam.r_pared_mm, cam.gap_mm
    zh = H / 2.0
    bombas_xy = np.array([
        [cam.r_pos_bomba_mm * math.cos(math.pi / 4 + math.pi / 2 * k),
         cam.r_pos_bomba_mm * math.sin(math.pi / 4 + math.pi / 2 * k)]
        for k in range(cam.n_bombas)])

    q_pared_total = cam.q_pared_mbar_l_s_cm2 * cam.area_total_cm2
    frac_fuente = cam.q_h2_fuentes_total_mbar_l_s / cam.q_total_mbar_l_s

    hits_tapa = np.zeros(n_bins_r, dtype=np.int64)
    area_bin_m2 = np.array([
        math.pi * ((R * (i + 1) / n_bins_r) ** 2 - (R * i / n_bins_r) ** 2)
        for i in range(n_bins_r)]) * 1e-6  # mm²→m²
    absorbidos = 0
    hits_bomba = 0

    lote = 50_000
    restantes = n_moleculas
    while restantes > 0:
        n = min(lote, restantes)
        restantes -= n

        # ---------- emisión ----------
        es_fuente = rng.random(n) < frac_fuente
        pos = np.empty((n, 3))
        vel = np.empty((n, 3))
        nf = int(es_fuente.sum())
        if nf:
            pos[es_fuente] = 0.0
            vv = rng.normal(size=(nf, 3))  # isotrópico (fuente puntual)
            vel[es_fuente] = vv / np.linalg.norm(vv, axis=1)[:, None]
        idxw = np.where(~es_fuente)[0]
        if len(idxw):
            a_tapas = 2 * math.pi * R * R
            a_lat = 2 * math.pi * R * H
            en_tapa = rng.random(len(idxw)) < a_tapas / (a_tapas + a_lat)
            normales = np.empty((len(idxw), 3))
            # tapas
            it = np.where(en_tapa)[0]
            if len(it):
                rr = R * np.sqrt(rng.random(len(it)))
                ph = rng.random(len(it)) * 2 * np.pi
                zz = rng.choice([-zh, zh], len(it))
                pos[idxw[it]] = np.column_stack(
                    [rr * np.cos(ph), rr * np.sin(ph), zz])
                normales[it] = np.column_stack(
                    [np.zeros(len(it)), np.zeros(len(it)), -np.sign(zz)])
            # lateral
            il = np.where(~en_tapa)[0]
            if len(il):
                ph = rng.random(len(il)) * 2 * np.pi
                pos[idxw[il]] = np.column_stack(
                    [R * np.cos(ph), R * np.sin(ph),
                     rng.uniform(-zh, zh, len(il))])
                normales[il] = np.column_stack(
                    [-np.cos(ph), -np.sin(ph), np.zeros(len(il))])
            vel[idxw] = _cosina(normales, rng)

        # ---------- trayectorias ----------
        activas = np.ones(n, dtype=bool)
        while activas.any():
            ia = np.where(activas)[0]
            pa, va = pos[ia], vel[ia]
            a2 = va[:, 0] ** 2 + va[:, 1] ** 2
            b2 = 2 * (pa[:, 0] * va[:, 0] + pa[:, 1] * va[:, 1])
            c2 = pa[:, 0] ** 2 + pa[:, 1] ** 2 - R * R
            disc = np.maximum(b2 * b2 - 4 * a2 * c2, 0.0)
            sq = np.sqrt(disc)
            with np.errstate(divide="ignore", invalid="ignore"):
                t1 = np.where(a2 > 1e-30, (-b2 - sq) / (2 * a2), np.inf)
                t2 = np.where(a2 > 1e-30, (-b2 + sq) / (2 * a2), np.inf)
            t_cil = np.where(t1 > 1e-9, t1, t2)
            t_cil = np.where(t_cil > 1e-9, t_cil, np.inf)
            with np.errstate(divide="ignore", invalid="ignore"):
                t_tap = np.where(np.abs(va[:, 2]) > 1e-30,
                                 (np.sign(va[:, 2]) * zh - pa[:, 2]) / va[:, 2],
                                 np.inf)
            t_tap = np.where(t_tap > 1e-9, t_tap, np.inf)
            t = np.minimum(t_cil, t_tap)
            t = np.where(np.isfinite(t), t, 1e-6)
            hit = pa + t[:, None] * va
            cerca_tapa = t_tap <= t_cil

            # ¿en boca de bomba?
            r2x = hit[:, 0:1] - bombas_xy[None, :, 0]
            r2y = hit[:, 1:2] - bombas_xy[None, :, 1]
            en_bomba = cerca_tapa & ((r2x ** 2 + r2y ** 2)
                                     < cam.r_bomba_mm ** 2).any(axis=1)
            hits_bomba += int(en_bomba.sum())
            absorbe = en_bomba & (rng.random(len(hit)) < cam.s_captura)
            absorbidos += int(absorbe.sum())

            # impingement en tapas → presión
            r_hit = np.hypot(hit[:, 0], hit[:, 1])
            b = np.clip((r_hit[cerca_tapa] / R * n_bins_r).astype(int),
                        0, n_bins_r - 1)
            np.add.at(hits_tapa, b, 1)

            # reemisión coseno en supervivientes
            sob = ~absorbe
            hs = hit[sob]
            if len(hs):
                en_lat = (t_cil <= t_tap)[sob]
                normales = np.empty((len(hs), 3))
                nl = en_lat.sum()
                if nl:
                    normales[en_lat] = np.column_stack(
                        [-hs[en_lat, 0] / R, -hs[en_lat, 1] / R,
                         np.zeros(int(nl))])
                if (~en_lat).any():
                    normales[~en_lat] = np.column_stack(
                        [np.zeros(int((~en_lat).sum())),
                         np.zeros(int((~en_lat).sum())),
                         -np.sign(hs[~en_lat, 2])])
                idx_sob = ia[sob]
                pos[idx_sob] = hs
                vel[idx_sob] = _cosina(normales, rng)
            activas[ia[absorbe]] = False

    # ---------- conversión impingement → presión ----------
    # flujo real: Q [mbar·l/s] → moléculas/s
    n_real_s = cam.q_total_mbar_l_s * 0.1 * 1e-3 / (K_B * cam.temperatura_k)
    escala = n_real_s / n_moleculas          # moléculas reales/s por virtual
    z_m2s = hits_tapa * escala / area_bin_m2
    p_pa = z_m2s * K_B * cam.temperatura_k * 4.0 / (cam.v_media_mm_s / 1000.0)
    p_mbar = p_pa * 10.0

    r_centros = ((np.arange(n_bins_r) + 0.5) * R / n_bins_r).tolist()
    return {
        "r_mm": r_centros,
        "p_mbar": p_mbar.tolist(),
        "hits_tapa": hits_tapa.tolist(),
        "n_moleculas": n_moleculas,
        "absorbidos": absorbidos,
        "hits_bomba": hits_bomba,
        "q_total_mbar_l_s": cam.q_total_mbar_l_s,
        "s_efectiva_l_s": cam.s_efectiva_l_s,
        "p_equilibrio_q_s_mbar": cam.q_total_mbar_l_s / cam.s_efectiva_l_s,
        "camara": {**cam.__dict__, "v_media_mm_s": cam.v_media_mm_s,
                   "area_total_cm2": cam.area_total_cm2},
        "fuentes": FUENTES_VACIO,
        "estado": "simulacion_teorica",
    }
