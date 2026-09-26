"""Turtle Soup del usuario (US100/USTEC, M5) implementado tal cual su especificación, y barrido de RR.

Reglas (del prompt del usuario, sin cambios):
  1. Régimen por vela: cierre < SMA20 -> solo TS alcistas (compra); cierre > SMA20 -> solo TS bajistas (venta).
  2. TS alcista: low < low_anterior y close > low_anterior. TS bajista: high > high_anterior y close < high_anterior.
  3. Gap: si open < low_anterior u open > high_anterior, TS inválido.
  4. Velas gatillo de 15:30 a 15:55 (hora de Madrid); máximo 1 operación al día (la primera válida).
  5. Entrada al cierre de la gatillo; SL fijo en ticks (tick = 0,25 puntos); TP = RR × SL; SL primero si ambos en
     la misma vela; cierre forzado al cierre de la última vela <= 20:00.
  6. Riesgo 100 € por operación: pnl = distancia recorrida / distancia SL × 100.
Sin comisiones ni deslizamiento.

Uso: python3 -m scripts.turtle_soup_usuario   (datos/USTEC_M5_*.csv exportado de MT5, hora servidor = NY + 7)
"""
import numpy as np
import pandas as pd

from fondeo.modelo import racha_max

CSV = "datos/USTEC_M5_2025-10_2026-09.csv"
DESDE, HASTA = "2025-10-06", "2026-09-18"   # periodo del informe del usuario (248 sesiones)
TICK = 0.25
RIESGO = 100.0
# Los datos del usuario venían en UTC+2 FIJO (así se reproduce su informe: acierto de B 59,8 %, PnL +4.106 €
# frente a +4.209 €). Con Europe/Madrid real (15:30 = apertura de NY todo el año) el resultado es otro: ver informe.
ZONA = "Etc/GMT-2"
# Horario de la regla en la zona usada: gatillo 15:30-15:55 y cierre 20:00 (hora de los datos del usuario).
# Con zona="America/New_York" y NY_ABIERTA: 09:30-09:55 y 14:00, que es lo que hace el EA de MT5.
HORARIO = (15 * 60 + 30, 15 * 60 + 55, 20 * 60)
NY_ABIERTA = (9 * 60 + 30, 9 * 60 + 55, 14 * 60)


def cargar(ruta=CSV, zona=ZONA):
    d = pd.read_csv(ruta, sep="\t")
    d.columns = [c.strip("<>").lower() for c in d.columns]
    t = pd.to_datetime(d["date"] + " " + d["time"]) - pd.Timedelta(hours=7)  # servidor -> Nueva York
    t = t.dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT").dt.tz_convert(zona)
    d = d.assign(t=t).dropna(subset=["t"]).reset_index(drop=True)
    d["sma20"] = d["close"].rolling(20).mean()
    d["dia"] = d["t"].dt.date
    d["min"] = d["t"].dt.hour * 60 + d["t"].dt.minute
    return d


def senales(d, horario=None):
    horario = horario or HORARIO
    lo_a, hi_a = d["low"].shift(), d["high"].shift()
    gap = (d["open"] < lo_a) | (d["open"] > hi_a)
    larga = (d["low"] < lo_a) & (d["close"] > lo_a) & (d["close"] < d["sma20"]) & ~gap
    corta = (d["high"] > hi_a) & (d["close"] < hi_a) & (d["close"] > d["sma20"]) & ~gap
    ventana = (d["min"] >= horario[0]) & (d["min"] <= horario[1])
    return larga & ventana, corta & ventana


def backtest(d, sl_ticks=400, rr=1.25, modo="combinado", desde=DESDE, hasta=HASTA, horario=None):
    horario = horario or HORARIO
    larga, corta = senales(d, horario)
    if modo == "alcistas":
        corta = corta & False
    elif modo == "bajistas":
        larga = larga & False
    rango = (d["t"] >= pd.Timestamp(desde, tz=d["t"].dt.tz)) & (d["t"] < pd.Timestamp(hasta, tz=d["t"].dt.tz) + pd.Timedelta(days=1))
    cand = d[(larga | corta) & rango]
    primeras = cand.groupby("dia").head(1).index
    o, h, l, c = (d[x].to_numpy() for x in ("open", "high", "low", "close"))
    mins, dias = d["min"].to_numpy(), d["dia"].to_numpy()
    dist = sl_ticks * TICK
    ops = []
    for i in primeras:
        dr = 1 if larga[i] else -1
        px = c[i]
        stop, tp = px - dr * dist, px + dr * rr * dist
        j, salida, tipo, ult, mae = i + 1, None, 1, i, 0.0
        while j < len(d) and dias[j] == dias[i] and mins[j] <= horario[2]:
            mae = min(mae, max((l[j] - px) if dr > 0 else (px - h[j]), -dist) / dist)
            toca_sl = l[j] <= stop if dr > 0 else h[j] >= stop
            toca_tp = h[j] >= tp if dr > 0 else l[j] <= tp
            if toca_sl:
                salida, tipo = stop, 2
                break
            if toca_tp:
                salida, tipo = tp, 3
                break
            ult = j
            j += 1
        if salida is None:
            salida = c[ult]
        pnl = dr * (salida - px) / dist * RIESGO
        ops.append((d["t"][i], d["t"][min(j, len(d) - 1)], dr, px, salida, tipo, pnl, mae))
    return pd.DataFrame(ops, columns=["entrada", "hora_salida", "dir", "precio", "salida", "tipo", "pnl", "mae"])


def metricas(ops):
    p = ops["pnl"]
    eq = p.cumsum()
    dd = (eq.cummax().clip(lower=0) - eq).max()
    g, l = p[p > 0].sum(), -p[p < 0].sum()
    dias = p.groupby(ops["entrada"].dt.date).sum()
    return dict(ops=len(ops), acierto=(p > 0).mean(), pf=g / l if l else np.inf, pnl=p.sum(), dd=dd,
                rf=p.sum() / dd if dd else np.inf, p_t=(ops.tipo == 1).mean(), p_sl=(ops.tipo == 2).mean(),
                p_tp=(ops.tipo == 3).mean(),
                meses_pos=(p.groupby(ops["entrada"].dt.tz_localize(None).dt.to_period("M")).sum() > 0).mean(),
                peor_dia=dias.min() / RIESGO,
                racha_sl=racha_max((ops.tipo == 2).to_numpy()), racha_perd=racha_max((p <= 0).to_numpy()),
                racha_tp=racha_max((ops.tipo == 3).to_numpy()), racha_gan=racha_max((p > 0).to_numpy()))


def mensual(ops):
    return ops["pnl"].groupby(ops["entrada"].dt.tz_localize(None).dt.to_period("M")).sum()


def barrido(d, sl_ticks=450, rrs=None):
    rrs = rrs or [round(1.00 - 0.05 * i, 2) for i in range(19)]
    filas = []
    for rr in rrs:
        o = backtest(d, sl_ticks, rr)
        m = metricas(o)
        filas.append(dict(rr=rr, **m))
    return pd.DataFrame(filas)


def biblioteca(d, ops, rr, recorte=0.0):
    """Días reales (con y sin operación) en el formato del simulador de Topstep. `recorte` resta esa fracción
    de la esperanza media a cada operación (0,5 = escenario con la mitad de la ventaja)."""
    from fondeo.modelo import MAXT, N_FRANJAS, Biblioteca, franja
    ini = pd.Timestamp(DESDE, tz=d["t"].dt.tz)
    fin = pd.Timestamp(HASTA, tz=d["t"].dt.tz) + pd.Timedelta(days=1)
    dias = sorted(d[(d["t"] >= ini) & (d["t"] < fin) & (d["min"] == 15 * 60 + 30)]["dia"].unique())
    pos = {x: k for k, x in enumerate(dias)}
    nd = len(dias)
    r_all = ops["pnl"].to_numpy() / RIESGO
    r_all = r_all - recorte * r_all.mean()
    R = np.full((nd, MAXT), np.nan)
    T = np.zeros((nd, MAXT), np.int8)
    M = np.zeros((nd, MAXT))
    TI = np.zeros((nd, MAXT), np.int32)
    TO = np.zeros((nd, MAXT), np.int32)
    MINF = np.zeros((nd, N_FRANJAS))
    n = np.zeros(nd, np.int32)
    for k, fila in enumerate(ops.itertuples()):
        di = pos.get(fila.entrada.date())
        if di is None:
            continue
        ny_in = fila.entrada.tz_convert("America/New_York")
        ny_out = fila.hora_salida.tz_convert("America/New_York")
        R[di, 0], T[di, 0], M[di, 0] = r_all[k], fila.tipo, fila.mae
        TI[di, 0], TO[di, 0] = ny_in.hour * 60 + ny_in.minute, ny_out.hour * 60 + ny_out.minute
        n[di] = 1
        fo = int(franja(TO[di, 0]))
        MINF[di, fo] = min(fila.mae, r_all[k])
        MINF[di, fo + 1:] = r_all[k]
    return Biblioteca(R, T, M, TI, TO, n, np.ones(nd), 450 * TICK / 350.0, rr, MINF, 0)


def ev_topstep(d, ops, rr):
    """EV por reto en Topstep 50K (RTA ON) remuestreando los días reales; mejor riesgo por operación."""
    from fondeo.topstep import CUENTAS, INSTRUMENTOS, Pierna, combine, xfa
    ins, cu = INSTRUMENTOS["NQ"], CUENTAS["50K"]
    out = {}
    for esc, rec in (("in-sample", 0.0), ("mitad", 0.5)):
        bib = biblioteca(d, ops, rr, rec)
        x = max((xfa([Pierna(bib, ins, rx * cu.mll)], cu, n=3000, umbral_retiro=um * cu.mll)
                 for rx in (0.10, 0.20, 0.30) for um in (1.0, 1.5)), key=lambda v: v["cobro_medio"])
        out[esc] = max(c["p_aprueba"] * x["cobro_medio"] - c["coste_medio"]
                       for c in (combine([Pierna(bib, ins, rc * cu.mll)], cu, n=3000)
                                 for rc in (0.15, 0.25, 0.35, 0.50, 0.75)))
    return out


def filas_tabla(d):
    """Filas TSM (reales) para la tabla de resultados del PDF."""
    filas = []
    sesiones = len(biblioteca(d, backtest(d, 450, 1.0), 1.0).n)
    for rr in [round(1.00 - 0.05 * i, 2) for i in range(19)]:
        o = backtest(d, 450, rr)
        m = metricas(o)
        ev = ev_topstep(d, o, rr)
        filas.append(dict(id="TSM-B" if rr == 1.0 else f"TSM-B {rr:.2f}".replace(".", ","), rr=rr, ops=m["ops"],
                          ops_dia=m["ops"] / sesiones, wr=m["acierto"], pf=m["pf"], beneficio=m["pnl"] * 10,
                          dd=m["dd"] * 10, rf=m["rf"], meses=m["meses_pos"], t=m["p_t"], s=m["p_sl"], tp=m["p_tp"],
                          peor=m["peor_dia"], ev_in=ev["in-sample"], ev_mitad=ev["mitad"], familia="manual", sl=450,
                          k=rr, tipo="manual", estimado=False))
        print(filas[-1]["id"], f"{100 * m['acierto']:.1f} % {m['pnl']:+.0f} € EV/reto {ev['in-sample']:+.0f} / {ev['mitad']:+.0f}",
              flush=True)
    pd.DataFrame(filas).to_csv("resultados/manual_tabla.csv", index=False)


if __name__ == "__main__":
    import sys

    if "--tabla" in sys.argv:
        filas_tabla(cargar())
        sys.exit()
    d = cargar()
    informe = {"Combinado 400/1,25": (219, 0.5342, 3938.75, 924.5), "Alcistas 400/1,25": (124, 0.5726, 2923.75, 764.0),
               "Bajistas 400/1,25": (126, 0.4762, 968.50, 751.5), "A 200/2,50": (219, 0.3699, 5654.00, 1479.5),
               "B 450/1,00": (219, 0.5982, 4208.89, 600.0)}
    confs = {"Combinado 400/1,25": (400, 1.25, "combinado"), "Alcistas 400/1,25": (400, 1.25, "alcistas"),
             "Bajistas 400/1,25": (400, 1.25, "bajistas"), "A 200/2,50": (200, 2.5, "combinado"),
             "B 450/1,00": (450, 1.0, "combinado")}
    filas = []
    for nom, (sl, rr, modo) in confs.items():
        m = metricas(backtest(d, sl, rr, modo))
        r = informe[nom]
        filas.append(dict(variante=nom, ops=m["ops"], ops_informe=r[0], acierto=m["acierto"], acierto_informe=r[1],
                          pnl=m["pnl"], pnl_informe=r[2], dd=m["dd"], dd_informe=r[3], pf=m["pf"]))
        print(f"{nom:20} ops {m['ops']:4} ({r[0]}) · acierto {100 * m['acierto']:.2f} % ({100 * r[1]:.2f}) · "
              f"PnL {m['pnl']:+.2f} € ({r[2]:+.2f}) · DD {m['dd']:.1f} ({r[3]}) · PF {m['pf']:.2f}")
    pd.DataFrame(filas).to_csv("resultados/tsu_reproduccion.csv", index=False)
    # por estación: verano (ventana = apertura NY) / invierno (ventana = 08:30 NY)
    o = backtest(d, 450, 1.0)
    ny = o["entrada"].dt.tz_convert("America/New_York")
    verano = ny.dt.hour * 60 + ny.dt.minute >= 9 * 60 + 30
    for nom, m in (("verano (09:30 NY)", verano), ("invierno (08:30 NY)", ~verano)):
        x = o[m]
        print(f"B {nom}: ops {len(x)} acierto {100 * (x.pnl > 0).mean():.1f} % PnL {x.pnl.sum():+.0f} €")
    dm = cargar(zona="Europe/Madrid")
    mm = metricas(backtest(dm, 450, 1.0))
    print(f"B con hora de Madrid real (siempre apertura NY): acierto {100 * mm['acierto']:.1f} % PnL {mm['pnl']:+.0f} € DD {mm['dd']:.0f}")
    b = barrido(d)
    b.to_csv("resultados/tsu_barrido_rr.csv", index=False)
    bm = barrido(dm)
    bm.to_csv("resultados/tsu_barrido_rr_madrid.csv", index=False)
    pd.set_option("display.width", 250)
    print(b[["rr", "ops", "acierto", "pf", "pnl", "dd", "rf", "p_t", "p_sl", "p_tp", "meses_pos", "peor_dia",
             "racha_sl", "racha_perd", "racha_tp"]].round(3).to_string(index=False))
    print("Madrid real:")
    print(bm[["rr", "acierto", "pnl", "dd"]].round(3).to_string(index=False))
