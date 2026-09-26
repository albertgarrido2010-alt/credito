"""Turtle Soup manual (MNQ, M5) del «Informe_Backtest_TurtleSoup_1»: comprobación y barrido de RR a la baja.

Datos del informe (06-10-2025 → 18-09-2026, 248 sesiones, 219 señales fijas, 100 € de riesgo por operación,
sin comisiones ni deslizamiento) y del mapa de calor SL × RR (81 celdas leídas por color, validadas contra
las tres celdas que el informe da exactas: resultados/manual_mapa_*.csv).

Modelo: el mismo de barreras de fondeo/modelo.py pero con SL en ticks y señales fijas (no cambian con el RR,
igual que en la optimización del informe). Se calibra con las 81 celdas de beneficio y los tres aciertos
conocidos, y se predice la Estrategia B (SL 450 ticks) con RR 1,00 → 0,10.

Uso: python3 -m scripts.estrategia_manual  ->  resultados/manual_barrido.csv, manual_params.json
"""
import json

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from fondeo.modelo import racha_max

N_SEN = 219
SESIONES = 248
RIESGO = 100.0
MAPA = pd.read_csv("resultados/manual_mapa_pnl.csv", index_col=0)
SLS = MAPA.index.to_numpy(float)
RRS = MAPA.columns.to_numpy(float)
ACIERTOS = {(400, 1.25): 0.5342, (200, 2.50): 0.3699, (450, 1.00): 0.5982}
# costes Topstep por operación en ticks de MNQ (0,50 $/tick): 1 $ comisión = 2 ticks, 1 tick de entrada,
# 1 tick más en stop o salida a mercado; el TP límite exige pasar 1 tick.
COSTE_TP, COSTE_OTRO, TICK_TP = 3.0, 4.0, 1.0
DT = 5 / 60   # velas M5 (con el puente browniano dentro de cada vela)
# medias de ganadora / perdedora en R que salen del PF, el acierto y el PnL del informe
MEDIAS = {(400, 1.25): (1.158, 0.942), (200, 2.50): (2.401, 0.999), (450, 1.00): (0.939, 0.920)}


def caminos(p, n=6000, seed=3):
    """Caminos en ticks: (mínimo y máximo del puente por vela, valor final, horizonte en velas).
    p = (sigma ticks/√h, a ticks/h, theta h, b ticks/h, dispersión de volatilidad, horizonte máx. h)."""
    sigma, a, theta, b, vsd, hmax = p
    rng = np.random.default_rng(seed)
    pasos = max(int(hmax / DT), 3)
    h = rng.integers(2, pasos + 1, n)
    v = np.exp(rng.normal(0, vsd, n) - vsd ** 2 / 2)
    var = (sigma * v) ** 2 * DT
    t = np.arange(pasos)[:, None] * DT
    mu = (a * np.exp(-t / theta) + b) * DT
    dx = mu + np.sqrt(var) * rng.standard_normal((pasos, n))
    x1 = np.cumsum(dx, axis=0)
    x0 = np.vstack([np.zeros((1, n)), x1[:-1]])
    d2 = (x1 - x0) ** 2
    mn = 0.5 * (x0 + x1 - np.sqrt(d2 - 2 * var * np.log(rng.random((pasos, n)))))
    mx = 0.5 * (x0 + x1 + np.sqrt(d2 - 2 * var * np.log(rng.random((pasos, n)))))
    viva = np.arange(pasos)[:, None] < h[None, :]
    mn = np.where(viva, mn, np.inf)
    mx = np.where(viva, mx, -np.inf)
    xh = x1[h - 1, np.arange(n)]
    return mn, mx, xh


def primera(mask):
    hay = mask.any(axis=0)
    return np.where(hay, mask.argmax(axis=0), 10 ** 9)


def operar(cam, sl, rr, costes=False):
    """Resultado en R de cada operación, tipo (1 tiempo, 2 SL, 3 TP) y peor flotante."""
    mn, mx, xh = cam
    tp = rr * sl + (TICK_TP if costes else 0.0)
    i_sl = primera(mn <= -sl)
    i_tp = primera(mx >= tp)
    tipo = np.where((i_sl <= i_tp) & (i_sl < 10 ** 9), 2, np.where(i_tp < 10 ** 9, 3, 1))
    r = np.where(tipo == 2, -1.0, np.where(tipo == 3, rr, np.clip(xh / sl, -1, rr)))
    if costes:
        r = r - np.where(tipo == 3, COSTE_TP, COSTE_OTRO) / sl
    return r, tipo


def params(z):
    return (float(np.exp(z[0])), float(z[1]), float(np.exp(z[2])), float(z[3]),
            float(np.exp(z[4])), float(np.exp(z[5])))


def perdida(z):
    p = params(z)
    if p[5] > 30 or p[4] > 1.5:
        return 1e6
    cam = caminos(p)
    err = 0.0
    for i, sl in enumerate(SLS):
        for j, rr in enumerate(RRS):
            r, _ = operar(cam, sl, rr)
            err += ((r.mean() * N_SEN * RIESGO - MAPA.iloc[i, j]) / 700.0) ** 2
    for (sl, rr), wr in ACIERTOS.items():
        r, _ = operar(cam, sl, rr)
        err += (((r > 0).mean() - wr) / 0.02) ** 2
        err += ((r.mean() * N_SEN * RIESGO - MAPA.loc[sl, str(rr)]) / 300.0) ** 2
        mw, ml = MEDIAS[(sl, rr)]
        err += ((r[r > 0].mean() - mw) / 0.05) ** 2 + ((-r[r <= 0].mean() - ml) / 0.05) ** 2
    return err


def main():
    z0 = np.array([np.log(270.0), 80.0, np.log(0.7), 0.0, np.log(0.3), np.log(12.0)])
    res = minimize(perdida, z0, method="Nelder-Mead", options=dict(maxfev=500, xatol=1e-3, fatol=1e-2))
    p = params(res.x)
    print("params sigma %.1f ticks/√h  a %.1f ticks/h  theta %.2f h  b %.1f ticks/h  vol_sd %.2f  hmax %.1f h  "
          "pérdida %.1f" % (*p, res.fun))
    json.dump(dict(sigma=p[0], a=p[1], theta=p[2], b=p[3], vol_sd=p[4], hmax=p[5], perdida=res.fun),
              open("resultados/manual_params.json", "w"), indent=2)

    cam = caminos(p, n=40000, seed=11)
    # ajuste: modelo frente al mapa y a los aciertos
    for (sl, rr), wr in ACIERTOS.items():
        r, _ = operar(cam, sl, rr)
        print(f"  SL{sl} RR{rr}: acierto modelo {100 * (r > 0).mean():.1f} % / informe {100 * wr:.1f} % · "
              f"PnL modelo {r.mean() * N_SEN * RIESGO:.0f} € / mapa {MAPA.loc[sl, str(rr)]:.0f} € · "
              f"medias {r[r > 0].mean():.2f}/{-r[r <= 0].mean():.2f} R / informe {MEDIAS[(sl, rr)]}")
    fila_m = [operar(cam, 450, x)[0].mean() * N_SEN * RIESGO for x in RRS]
    print("  fila SL450 modelo:", [round(v) for v in fila_m])
    print("  fila SL450 mapa:  ", [round(v) for v in MAPA.loc[450]])
    fila = MAPA.loc[450]
    rng = np.random.default_rng(1)
    filas = []
    for rr in [1.00, 0.75, 0.50, 0.35, 0.25, 0.15, 0.10]:
        for costes in (False, True):
            r, tipo = operar(cam, 450, rr, costes)
            dd, rsl, rper, rtp = [], [], [], []
            for _ in range(400):
                idx = rng.integers(0, len(r), N_SEN)
                x, tp = r[idx], tipo[idx]
                eq = np.cumsum(x)
                dd.append((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max())
                rsl.append(racha_max(tp == 2)); rper.append(racha_max(x <= 0)); rtp.append(racha_max(tp == 3))
            g, l = r[r > 0].sum(), -r[r < 0].sum()
            real = fila.get(f"{rr}", np.nan) if not costes else np.nan
            filas.append(dict(rr=rr, costes="futuros Topstep" if costes else "sin costes (como el informe)",
                              acierto=(r > 0).mean(), p_t=(tipo == 1).mean(), p_sl=(tipo == 2).mean(),
                              p_tp=(tipo == 3).mean(), ev_r=r.mean(), pf=g / l,
                              pnl_eur=r.mean() * N_SEN * RIESGO, pnl_pct=r.mean() * N_SEN,
                              dd_eur=np.median(dd) * RIESGO, racha_sl=np.median(rsl), racha_sl_p95=np.percentile(rsl, 95),
                              racha_perd=np.median(rper), racha_perd_p95=np.percentile(rper, 95),
                              racha_tp=np.median(rtp), racha_tp_p95=np.percentile(rtp, 95),
                              pnl_mapa_eur=real))
    df = pd.DataFrame(filas)
    df.to_csv("resultados/manual_barrido.csv", index=False)
    pd.set_option("display.width", 250)
    print(df.round(3).to_string(index=False))




# ---------------------------------------------------------------------------
# Filas para la tabla de resultados (ancladas a los datos reales del informe)
# ---------------------------------------------------------------------------
RR_TABLA = [1.00, 0.75, 0.50, 0.35, 0.25, 0.15, 0.10]
RF_MAPA = pd.read_csv("resultados/manual_mapa_rf.csv", index_col=0)
ATR_TICKS = 1400.0  # ATR diario NQ supuesto (350 puntos) para pasar el modelo a unidades de ATR


def logit(x):
    return np.log(x / (1 - x))


def tabla():
    """Beneficio y DD reales con RR 1,00 / 0,75 / 0,50 (informe y mapa); por debajo, la caída relativa del
    modelo desde 0,50. Acierto: el del modelo desplazado (en logit) para que con RR 1,00 dé el 59,82 % real."""
    import json as _j
    from fondeo.modelo import Familia, Params, simular
    from fondeo.topstep import CUENTAS, INSTRUMENTOS, Pierna, combine, xfa
    from scripts.barrido_rr import neta

    pj = _j.load(open("resultados/manual_params.json"))
    p = (pj["sigma"], pj["a"], pj["theta"], pj["b"], pj["vol_sd"], pj["hmax"])
    cam = caminos(p, n=60000, seed=21)
    mod = {rr: operar(cam, 450, rr) for rr in RR_TABLA}
    ev_m = {rr: mod[rr][0].mean() for rr in RR_TABLA}
    wr_m = {rr: (mod[rr][0] > 0).mean() for rr in RR_TABLA}
    rng = np.random.default_rng(2)

    def dd_mod(rr):
        r = mod[rr][0]
        out = []
        for _ in range(400):
            eq = np.cumsum(r[rng.integers(0, len(r), N_SEN)])
            out.append((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max())
        return np.median(out)

    dd_m = {rr: dd_mod(rr) for rr in RR_TABLA}
    off = logit(ACIERTOS[(450, 1.00)]) - logit(wr_m[1.00])
    real = {1.00: (4208.89, 600.0), 0.75: (MAPA.loc[450, "0.75"], MAPA.loc[450, "0.75"] / RF_MAPA.loc[450, "0.75"]),
            0.50: (MAPA.loc[450, "0.5"], MAPA.loc[450, "0.5"] / RF_MAPA.loc[450, "0.5"])}

    # familia equivalente en ATR para el simulador de Topstep (0,88 señales por sesión)
    fam = Familia("manual", "Turtle Soup manual · MNQ", "NQ", "ts", CIERRE_H - pj["hmax"], CIERRE_H - 1 / 12)
    pa = Params(sigma=pj["sigma"] / ATR_TICKS, a=pj["a"] / ATR_TICKS, theta=pj["theta"], b=pj["b"] / ATR_TICKS,
                q=0.036, vol_sd=pj["vol_sd"])
    ins = INSTRUMENTOS["NQ"]
    sl_atr = 450 / ATR_TICKS
    cu = CUENTAS["50K"]
    filas = []
    for rr in RR_TABLA:
        if rr in real:
            pnl, dd = real[rr]
            fuente = "informe" if rr == 1.00 else "mapa del informe"
        else:
            pnl = real[0.50][0] * ev_m[rr] / ev_m[0.50]
            dd = real[0.50][1] * dd_m[rr] / dd_m[0.50]
            fuente = "modelo (desde RR 0,50 real)"
        ev = pnl / N_SEN / RIESGO
        wr = 1 / (1 + np.exp(-(logit(wr_m[rr]) + off))) if rr != 1.00 else ACIERTOS[(450, 1.00)]
        r, tipo = mod[rr]
        perd_media = -r[r <= 0].mean()
        L = (1 - wr) * perd_media
        pf = 1.52 if rr == 1.00 else (ev + L) / L
        # Topstep: biblioteca con la ventaja escalada para dar la misma esperanza (con costes de futuros)
        evt = {}
        for esc, f in (("in-sample", 1.0), ("mitad", 0.5)):
            edge = 1.0
            for _ in range(3):
                bib = simular(fam, sl_atr, rr, pa, n_dias=12000, seed=41, edge=edge, tp_extra_atr=ins.tick * 4 / ATR_TICKS)
                e_sim = bib.resumen()["ev_r"]
                edge *= (f * ev) / e_sim if e_sim > 0 else 1.0
            bib = simular(fam, sl_atr, rr, pa, n_dias=12000, seed=41, edge=edge, tp_extra_atr=ins.tick * 4 / ATR_TICKS)
            mejor_x = max((xfa([Pierna(bib, ins, rx * cu.mll)], cu, n=3000, umbral_retiro=um * cu.mll)
                           for rx in (0.10, 0.20, 0.30) for um in (1.0, 1.5)), key=lambda x: x["cobro_medio"])
            evt[esc] = max(c["p_aprueba"] * mejor_x["cobro_medio"] - c["coste_medio"]
                           for c in (combine([Pierna(bib, ins, rc * cu.mll)], cu, n=3000)
                                     for rc in (0.15, 0.25, 0.35, 0.50, 0.75)))
        filas.append(dict(id="TSM-B" if rr == 1.00 else f"TSM-B {str(rr).replace('.', ',')}", rr=rr, fuente=fuente,
                          ops=N_SEN, ops_dia=N_SEN / SESIONES, wr=wr, wr_estimado=rr != 1.00, pf=pf,
                          beneficio=pnl * 10, dd=dd * 10, rf=pnl / dd, meses=1.0 if rr == 1.00 else np.nan,
                          t=(tipo == 1).mean(), s=(tipo == 2).mean(), tp=(tipo == 3).mean(), peor=np.nan,
                          pnl_eur=pnl, pnl_pct=pnl / RIESGO, coste_pct=(ev_m[rr] - operar(cam, 450, rr, True)[0].mean()) * N_SEN,
                          ev_in=evt["in-sample"], ev_mitad=evt["mitad"], familia="manual", sl=450, k=rr, tipo="manual"))
        print(filas[-1]["id"], f"acierto {100 * wr:.1f} % · PnL {pnl:.0f} € ({pnl / RIESGO:+.1f} %) · DD {dd:.0f} € · "
              f"PF {pf:.2f} · EV/reto {evt['in-sample']:+.0f} / {evt['mitad']:+.0f} $", flush=True)
    pd.DataFrame(filas).to_csv("resultados/manual_tabla.csv", index=False)


CIERRE_H = 15 + 55 / 60


if __name__ == "__main__":
    import sys

    tabla() if "--tabla" in sys.argv else main()
