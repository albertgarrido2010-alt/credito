"""Modelo de barreras calibrado con el informe de candidatos.

Tras la entrada, el precio (en unidades de ATR diario) sigue
    dX = mu(t) dt + sigma * v_dia * dW,   mu(t) = edge * (a * exp(-t/theta) + b)
con t en horas desde la entrada. `a·exp(-t/θ)` es el rebote inicial (reversión) y `b` la deriva
persistente (tendencia). La operación termina en el SL (-sl), el TP (+k·sl), la salida por tiempo o el
cierre de las 15:55 NY. Los cruces de barrera se detectan con el puente browniano (monitorización
continua, como una vela M5 con máximo y mínimo), SL primero si ambos caben en el mismo minuto.

Las señales se generan por día con la regla de cada familia (una operación abierta a la vez), así que el
número de operaciones al día sale del modelo y cambia con el SL y el RR, igual que en el backtest.

Con esto se calibra cada familia con las configuraciones del PDF (SL y RR distintos de la misma señal)
y se predice qué pasa con otros RR. Es una extrapolación: la prueba definitiva es el backtest con velas
reales (ver backtest.py).
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

MAXT = 16            # operaciones máximas por día que se guardan
DT = 1.0 / 60.0      # paso de 1 minuto (horas)
CIERRE = 15 + 55 / 60  # 15:55 NY
COSTE_PDF_ATR = 0.006  # coste por operación que implica el informe (spread+comisión CFD), en ATR
FRANJA_INI = 120       # las franjas de 30' empiezan a las 02:00 NY (minuto 120 del día)
N_FRANJAS = 28         # 02:00 → 16:00 NY


def franja(minuto_abs):
    """Franja de 30 minutos (0 = 02:00-02:30 NY) de un minuto del día."""
    return np.clip((np.asarray(minuto_abs) - FRANJA_INI) // 30, 0, N_FRANJAS - 1)


@dataclass(frozen=True)
class Familia:
    clave: str
    nombre: str
    activo: str
    tipo: str            # "ts" (1 señal máx. por ventana de 30'), "hora" (comprobación cada 30')
    ini: float           # inicio de la ventana de señales (hora NY)
    fin: float           # último momento de entrada (hora NY)
    tcap: float | None = None  # salida por tiempo (h)


FAMILIAS = {
    "ts24_xau": Familia("ts24_xau", "Turtle Soup N24 + SMA200 · oro", "XAU", "ts", 2.0, 14 + 55 / 60),
    "ts12_nq": Familia("ts12_nq", "Turtle Soup N12 + SMA200 · Nasdaq", "NQ", "ts", 9.5, 14 + 55 / 60),
    "hora_xau": Familia("hora_xau", "Hora + SMA200 alcistas · oro", "XAU", "hora", 2.0, 14.5),
    "ts12_es": Familia("ts12_es", "Turtle Soup N12 + SMA200 · S&P", "ES", "ts", 9.5, 14 + 55 / 60),
}


@dataclass(frozen=True)
class Params:
    sigma: float = 0.13   # ATR / sqrt(h)
    a: float = 0.0        # rebote inicial, ATR/h
    theta: float = 0.5    # h
    b: float = 0.0        # deriva persistente, ATR/h
    q: float = 0.2        # prob. de señal por ventana / comprobación
    vol_sd: float = 0.30  # dispersión lognormal de la volatilidad diaria frente al ATR


@dataclass
class Biblioteca:
    """Días simulados. Arrays [n_dias, MAXT] con NaN/0 de relleno."""
    r: np.ndarray        # resultado en R (sin costes)
    tipo: np.ndarray     # 0 vacío, 1 tiempo, 2 SL, 3 TP
    mae: np.ndarray      # peor flotante de la operación en R (<= 0)
    t_in: np.ndarray     # minuto de entrada desde el inicio de la ventana
    t_out: np.ndarray
    n: np.ndarray        # operaciones por día
    v: np.ndarray        # multiplicador de volatilidad del día
    sl: float
    k: float
    # Peor equity (realizado + flotante, sin costes, en R) de cada franja de 30' del día. Sirve para
    # sumar varias estrategias en la misma cuenta respetando la hora (MLL en tiempo real y DLL).
    min_franja: np.ndarray | None = None
    ini_min: int = 0     # minuto del día (NY) al que corresponde t_in = 0

    # --- agregados --------------------------------------------------------
    def planas(self):
        m = self.tipo > 0
        return self.r[m], self.tipo[m], self.mae[m]

    def resumen(self, coste_r: float = 0.0) -> dict:
        r, tp, _ = self.planas()
        rn = r - coste_r
        g, p = rn[rn > 0].sum(), -rn[rn < 0].sum()
        return dict(
            ops_dia=self.n.mean(),
            wr=(rn > 0).mean(),
            p_t=(tp == 1).mean(), p_sl=(tp == 2).mean(), p_tp=(tp == 3).mean(),
            ev_r=rn.mean(), pf=g / p if p > 0 else np.inf,
            dur_min=(self.t_out - self.t_in)[self.tipo > 0].mean(),
        )


def _senales(fam: Familia, p: Params, n_dias: int, rng) -> np.ndarray:
    """Matriz [minutos, n_dias] con True donde hay señal."""
    n_min = int(round((CIERRE - fam.ini) * 60)) + 1
    sig = np.zeros((n_min, n_dias), bool)
    ult = int(round((fam.fin - fam.ini) * 60))
    if fam.tipo == "ts":
        for w in range(0, ult + 1, 30):
            hay = rng.random(n_dias) < p.q
            off = rng.integers(0, 6, n_dias) * 5  # vela M5 dentro de la ventana
            m = np.minimum(w + off, ult)
            sig[m[hay], np.nonzero(hay)[0]] = True
    elif fam.tipo == "hora":
        for w in range(0, ult + 1, 30):
            sig[w] = rng.random(n_dias) < p.q
    else:
        raise ValueError(fam.tipo)
    return sig


def simular(fam: Familia, sl: float, k: float, p: Params, n_dias: int = 4000, seed: int = 7,
            edge: float = 1.0, tp_extra_atr: float = 0.0) -> Biblioteca:
    """Simula `n_dias` días de la estrategia (familia, SL, RR). `edge` escala la deriva (1 = in-sample).
    `tp_extra_atr` exige que el precio pase el TP (p. ej. 1 tick) para dar la orden límite por llena."""
    rng = np.random.default_rng(seed)
    sig = _senales(fam, p, n_dias, rng)
    n_min = sig.shape[0]
    ult_entrada = int(round((fam.fin - fam.ini) * 60))
    cap = int(round(fam.tcap * 60)) if fam.tcap else 10 ** 9

    v = np.exp(rng.normal(0, p.vol_sd, n_dias) - p.vol_sd ** 2 / 2)
    var = (p.sigma * v) ** 2 * DT
    sd = np.sqrt(var)
    L, U = -sl, k * sl + tp_extra_atr

    R = np.full((n_dias, MAXT), np.nan)
    TIPO = np.zeros((n_dias, MAXT), np.int8)
    MAE = np.zeros((n_dias, MAXT))
    TIN = np.zeros((n_dias, MAXT), np.int32)
    TOUT = np.zeros((n_dias, MAXT), np.int32)
    cnt = np.zeros(n_dias, np.int32)

    abierta = np.zeros(n_dias, bool)
    x = np.zeros(n_dias)
    mae = np.zeros(n_dias)
    edad = np.zeros(n_dias, np.int32)
    tin = np.zeros(n_dias, np.int32)
    idx = np.arange(n_dias)
    realiz = np.zeros(n_dias)
    ini_min = int(round(fam.ini * 60))
    MINF = np.full((n_dias, N_FRANJAS), np.inf)
    MINF[:, : int(franja(ini_min))] = 0.0

    def cerrar(m, res, tipo, minuto):
        d = idx[m]
        c = np.minimum(cnt[d], MAXT - 1)
        R[d, c] = res if np.isscalar(res) else res[m]
        TIPO[d, c] = tipo
        MAE[d, c] = np.maximum(mae[d] / sl, -1.0)
        TIN[d, c] = tin[d]
        TOUT[d, c] = minuto
        cnt[d] += 1
        abierta[d] = False
        realiz[d] += R[d, c]

    for minuto in range(n_min):
        # 1) mover las abiertas
        a_idx = np.nonzero(abierta)[0]
        if a_idx.size:
            t = edad[a_idx] * DT
            mu = edge * (p.a * np.exp(-t / p.theta) + p.b)
            x0 = x[a_idx]
            x1 = x0 + mu * DT + sd[a_idx] * rng.standard_normal(a_idx.size)
            vv = var[a_idx]
            # mínimo y máximo del puente browniano entre x0 y x1
            dlt = (x1 - x0) ** 2
            mn = 0.5 * (x0 + x1 - np.sqrt(dlt - 2 * vv * np.log(rng.random(a_idx.size))))
            mx = 0.5 * (x0 + x1 + np.sqrt(dlt - 2 * vv * np.log(rng.random(a_idx.size))))
            x[a_idx] = x1
            edad[a_idx] += 1
            eq = realiz.copy()
            eq[a_idx] += np.maximum(mn, L) / sl
            f = int(franja(ini_min + minuto))
            MINF[:, f] = np.minimum(MINF[:, f], eq)
            mae[a_idx] = np.minimum(mae[a_idx], mn)
            hsl = np.zeros(n_dias, bool)
            htp = np.zeros(n_dias, bool)
            hsl[a_idx] = mn <= L
            htp[a_idx] = (mx >= U) & ~(mn <= L)
            if hsl.any():
                cerrar(hsl, -1.0, 2, minuto)
            if htp.any():
                cerrar(htp, k, 3, minuto)
            fin = abierta & ((edad >= cap) | (minuto == n_min - 1))
            if fin.any():
                cerrar(fin, x / sl, 1, minuto)
        f = int(franja(ini_min + minuto))
        MINF[:, f] = np.minimum(MINF[:, f], realiz)
        # 2) nuevas entradas
        if minuto <= ult_entrada:
            e = sig[minuto] & ~abierta & (cnt < MAXT)
            if e.any():
                abierta[e] = True
                x[e] = 0.0
                mae[e] = 0.0
                edad[e] = 0
                tin[e] = minuto
    ult_f = int(franja(ini_min + n_min - 1))
    MINF[:, ult_f + 1:] = realiz[:, None]
    return Biblioteca(R, TIPO, MAE, TIN, TOUT, cnt, v, sl, k, MINF.astype(np.float32), ini_min)


# ---------------------------------------------------------------------------
# Rachas
# ---------------------------------------------------------------------------
def racha_max(mask: np.ndarray) -> int:
    """Racha más larga de True consecutivos en un vector 1-D."""
    if not mask.any():
        return 0
    m = np.concatenate(([0], mask.astype(np.int8), [0]))
    d = np.diff(m)
    return int((np.nonzero(d == -1)[0] - np.nonzero(d == 1)[0]).max())


def rachas(bib: Biblioteca, n_ops: int, n_rep: int = 400, seed: int = 3, coste_r: float = 0.0) -> dict:
    """Rachas más largas en muestras de `n_ops` operaciones seguidas (orden real dentro del día,
    días al azar). Devuelve mediana y p95 de: stops seguidos, pérdidas seguidas, TPs seguidos,
    ganancias seguidas y días perdedores seguidos."""
    rng = np.random.default_rng(seed)
    ops_dia = max(bib.n.mean(), 1e-9)
    n_d = int(np.ceil(n_ops / ops_dia * 1.3)) + 5
    out = {k: [] for k in ("sl", "perd", "tp", "gan", "dias_perd")}
    for _ in range(n_rep):
        d = rng.integers(0, bib.r.shape[0], n_d)
        tipo = bib.tipo[d].ravel()
        r = bib.r[d].ravel() - coste_r
        m = tipo > 0
        tipo, r = tipo[m][:n_ops], r[m][:n_ops]
        out["sl"].append(racha_max(tipo == 2))
        out["perd"].append(racha_max(r <= 0))
        out["tp"].append(racha_max(tipo == 3))
        out["gan"].append(racha_max(r > 0))
        dia = np.nansum(bib.r[d] - coste_r * (bib.tipo[d] > 0), axis=1)
        nd = int(round(n_ops / ops_dia))
        dia = dia[bib.n[d] > 0][:nd] if (bib.n[d] > 0).sum() >= nd else dia[:nd]
        out["dias_perd"].append(racha_max(dia < 0))
    return {k: (float(np.median(v)), float(np.percentile(v, 95))) for k, v in out.items()}


# ---------------------------------------------------------------------------
# Calibración
# ---------------------------------------------------------------------------
_NOMBRES = ("sigma", "a", "theta", "b", "q")


def _desempaquetar(z, base: Params, fijos: dict) -> Params:
    libres = [n for n in _NOMBRES if n not in fijos]
    d = dict(fijos)
    for n, val in zip(libres, z):
        if n in ("sigma", "theta"):
            d[n] = float(np.exp(val))
        elif n == "q":
            d[n] = float(1 / (1 + np.exp(-val)))
        else:
            d[n] = float(val)
    return replace(base, **d)


def _empaquetar(p: Params, fijos: dict):
    z = []
    for n in _NOMBRES:
        if n in fijos:
            continue
        val = getattr(p, n)
        z.append(np.log(val) if n in ("sigma", "theta") else np.log(val / (1 - val)) if n == "q" else val)
    return np.array(z)


def perdida(p: Params, fam: Familia, cands, n_dias: int = 2500, detalle: bool = False):
    """Error cuadrático estandarizado frente al PDF (salidas T/SL/TP, esperanza bruta y ops/día)."""
    tot, filas = 0.0, []
    for c in cands:
        bib = simular(fam, c.sl, c.k, p, n_dias=n_dias, seed=11)
        s = bib.resumen()
        ev_bruta = c.ev_r + COSTE_PDF_ATR / c.sl
        se_ev = max(c.ev_r / max(c.t_stat, 0.5), 0.004)
        e = [
            (s["p_t"] - c.p_t) / 0.015, (s["p_sl"] - c.p_sl) / 0.012, (s["p_tp"] - c.p_tp) / 0.015,
            (s["ev_r"] - ev_bruta) / se_ev, (s["ops_dia"] - c.ops_dia) / (0.04 * c.ops_dia),
        ]
        tot += float(np.dot(e, e))
        filas.append((c.id, s, ev_bruta))
    return (tot, filas) if detalle else tot


def calibrar(fam: Familia, cands, inicio: Params, fijos: dict | None = None, iters: int = 250,
             n_dias: int = 2500) -> Params:
    from scipy.optimize import minimize

    fijos = fijos or {}
    f = lambda z: perdida(_desempaquetar(z, inicio, fijos), fam, cands, n_dias)
    res = minimize(f, _empaquetar(inicio, fijos), method="Nelder-Mead",
                   options=dict(maxfev=iters, xatol=1e-3, fatol=1e-2))
    return _desempaquetar(res.x, inicio, fijos)


def rachas_iid(p_sl: float, p_tp: float, wr: float, n_ops: int, n_rep: int = 2000, seed: int = 4) -> dict:
    """Rachas más largas en `n_ops` operaciones independientes con las proporciones del PDF.
    Pérdida = SL o salida por tiempo en negativo (1 − WR); ganancia = TP o salida por tiempo en positivo."""
    rng = np.random.default_rng(seed)
    p_twin = max(wr - p_tp, 0.0)
    p_tloss = max(1 - p_sl - p_tp - p_twin, 0.0)
    probs = np.array([p_sl, p_tloss, p_tp, p_twin])
    probs = probs / probs.sum()
    out = {k: [] for k in ("sl", "perd", "tp", "gan")}
    for _ in range(n_rep):
        x = rng.choice(4, size=n_ops, p=probs)
        out["sl"].append(racha_max(x == 0))
        out["perd"].append(racha_max(x <= 1))
        out["tp"].append(racha_max(x == 2))
        out["gan"].append(racha_max(x >= 2))
    return {k: (float(np.median(v)), float(np.percentile(v, 95))) for k, v in out.items()}
