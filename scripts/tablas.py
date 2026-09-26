"""Tablas en Markdown a partir de los CSV de resultados.

Uso: python3 -m scripts.tablas > resultados/tablas.md
"""
import json

import pandas as pd

from fondeo.candidatos import winrate_alto
from fondeo.modelo import FAMILIAS, rachas_iid
from fondeo.topstep import INSTRUMENTOS, coste_r

FAM_DE = {"S02": "ts12_es", "N02": "ts12_nq", "N04": "ts12_nq", "Z05": "hora_xau", "Z08": "hora_xau",
          "Z10": "ts24_xau", "Z12": "ts24_xau", "Z13": "ts24_xau"}
ACT = {"ES": "ES", "NQ": "NQ", "XAU": "XAU"}


def pct(x):
    return f"{100 * x:.1f} %"


def tabla(df, cols, cab):
    out = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(str(c(r)) if callable(c) else str(r[c]) for c in cols) + " |")
    return "\n".join(out)


def preseleccion():
    filas = []
    for c in winrate_alto():
        ins = INSTRUMENTOS[ACT[c.activo]]
        c_fut = coste_r(ins, c.sl, 3) + ins.tick / (c.sl * ins.atr)  # comisión+entrada y 1 tick para llenar el TP
        filas.append(dict(id=c.id, activo=c.activo, rr=f"1:{c.k:.2f}", wr=pct(c.wr), pf=f"{c.pf:.2f}",
                          ev=f"{c.ev_r:+.3f}", t=f"{c.t_stat:.1f}", rf=f"{c.rf:.1f}",
                          meses=f"{100 * c.meses_pos:.0f} %", coste=f"{100 * c_fut / c.k:.0f} %",
                          ev_fut=f"{c.ev_r + 0.006 / c.sl - c_fut:+.3f}"))
    df = pd.DataFrame(filas)
    return tabla(df, list(df.columns), ["ID", "Activo", "RR", "Acierto", "PF", "EV/op (R)", "t", "RF",
                                        "Meses +", "Coste futuros / TP", "EV/op futuros (R)"])


def rachas_pdf():
    filas = []
    for c in winrate_alto():
        r = rachas_iid(c.p_sl, c.p_tp, c.wr, c.ops)
        f = lambda k: f"{r[k][0]:.0f} ({r[k][1]:.0f})"
        filas.append(dict(id=c.id, rr=f"1:{c.k:.2f}", ops=c.ops, wr=pct(c.wr), psl=pct(c.p_sl),
                          sl=f("sl"), perd=f("perd"), tp=f("tp"), gan=f("gan"),
                          peor=f"{c.peor_dia:.1f} R"))
    df = pd.DataFrame(filas)
    return tabla(df, list(df.columns), ["ID", "RR", "Ops", "Acierto", "% SL", "Stops seguidos",
                                        "Pérdidas seguidas", "TPs seguidos", "Ganadoras seguidas",
                                        "Peor día (PDF)"])


def barrido(b: pd.DataFrame, fam: str, sl: float, esc: str = "in-sample", cuenta: str = "50K"):
    d = b[(b.familia == fam) & (b.sl == sl) & (b.escenario == esc) & (b.cuenta == cuenta)].sort_values("k")
    cols = [lambda r: f"1:{r.k:.2f}" + (f" **{r.origen}**" if isinstance(r.origen, str) and r.origen else ""),
            lambda r: pct(r.wr), lambda r: f"{r.ev_r:+.4f}", lambda r: f"{r.pf:.2f}",
            lambda r: f"{r.ops_dia:.2f}", lambda r: f"{r.ev_dia_r:+.3f}",
            lambda r: f"{r.benef_18m_r:+.0f} / {r.dd_18m_r:.0f}",
            lambda r: f"{r.racha_sl:.0f} ({r.racha_sl_p95:.0f})", lambda r: f"{r.racha_perd:.0f} ({r.racha_perd_p95:.0f})",
            lambda r: f"{r.racha_tp:.0f} ({r.racha_tp_p95:.0f})",
            lambda r: f"{r.racha_dias_perd:.0f} ({r.racha_dias_perd_p95:.0f})",
            lambda r: pct(r.p_aprueba), lambda r: f"{r.dias_aprobar:.0f}", lambda r: f"{r.cobro_xfa:.0f} $",
            lambda r: f"{r.ev_intento:+.0f} $", lambda r: f"{r.roi:+.2f}"]
    cab = ["RR", "Acierto", "EV/op (R)", "PF", "Ops/día", "EV/día (R)", "Benef./DD 18 m (R)", "Stops seg.",
           "Pérd. seg.", "TPs seg.", "Días perd. seg.", f"Aprueba {cuenta}", "Días", "Cobro XFA",
           "EV/intento", "ROI"]
    return tabla(d, cols, cab)


def main():
    print("## Preselección\n")
    print(preseleccion())
    print("\n## Rachas (PDF)\n")
    print(rachas_pdf())
    try:
        b = pd.read_csv("resultados/barrido_rr.csv")
    except FileNotFoundError:
        return
    for fam in b.familia.unique():
        for sl in sorted(b[b.familia == fam].sl.unique()):
            for esc in ("in-sample", "mitad", "sin ventaja"):
                print(f"\n## {FAMILIAS[fam].nombre} · SL {sl} ATR · ventaja {esc}\n")
                print(barrido(b, fam, sl, esc))


if __name__ == "__main__":
    main()
