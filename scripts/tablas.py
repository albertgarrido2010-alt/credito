"""Tablas en Markdown a partir de los CSV de resultados.

Uso: python3 -m scripts.tablas > resultados/tablas.md
"""
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


def barrido(b: pd.DataFrame, fam: str, sl: float, cuenta: str = "50K"):
    """Una fila por RR: métricas con la ventaja in-sample y EV por intento en los tres escenarios."""
    d = b[(b.familia == fam) & (b.sl == sl) & (b.cuenta == cuenta)]
    ins = d[d.escenario == "in-sample"].set_index("k").sort_index()
    ev = {e: d[d.escenario == e].set_index("k")["ev_intento"] for e in ("in-sample", "mitad", "sin ventaja")}
    filas = []
    for k, r in ins.iterrows():
        o = r.origen if isinstance(r.origen, str) else ""
        filas.append([f"1:{k:.2f}" + (f" ({o})" if o else ""), pct(r.wr), pct(r.p_sl), f"{r.ev_r:+.3f}",
                      f"{r.ops_dia:.1f}", f"{r.benef_18m_r:+.0f} / {r.dd_18m_r:.0f}",
                      f"{r.racha_sl:.0f} / {r.racha_sl_p95:.0f}", f"{r.racha_perd:.0f} / {r.racha_perd_p95:.0f}",
                      f"{r.racha_tp:.0f} / {r.racha_tp_p95:.0f}", f"{r.racha_dias_perd_p95:.0f}",
                      pct(r.p_aprueba), f"{r.dias_aprobar:.0f}",
                      f"{ev['in-sample'][k]:+.0f}", f"{ev['mitad'][k]:+.0f}", f"{ev['sin ventaja'][k]:+.0f}"])
    cab = ["RR", "Acierto", "% SL", "EV/op (R)", "Ops/día", "Benef. / DD 18 m (R)", "Stops seg. (med/p95)",
           "Pérd. seg. (med/p95)", "TPs seg. (med/p95)", "Días perd. seg. p95", f"Aprueba {cuenta}", "Días",
           "EV/reto $ in-sample", "EV/reto $ mitad", "EV/reto $ sin ventaja"]
    out = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    out += ["| " + " | ".join(f) + " |" for f in filas]
    return "\n".join(out)


def cartera(c: pd.DataFrame):
    """Mejor riesgo por cartera · escenario · cuenta · RTA."""
    idx = c.groupby(["cartera", "escenario", "cuenta", "rta"])["ev_intento"].idxmax()
    d = c.loc[idx]
    orden = {"in-sample": 0, "mitad": 1, "sin ventaja": 2}
    d = d.assign(o=d.escenario.map(orden)).sort_values(["o", "cuenta", "rta", "cartera"])
    cols = ["escenario", "cuenta", "rta", "cartera", lambda r: f"{r.riesgo_pierna:.0f} $",
            lambda r: pct(r.p_aprueba), lambda r: f"{r.dias_aprobar:.0f}", lambda r: pct(r.p_aprueba_20d),
            lambda r: f"{r.coste_intento:.0f} $", lambda r: f"{r.riesgo_xfa:.0f} $ · {r.umbral_retiro:.0f} $",
            lambda r: f"{r.cobro_xfa:.0f} $", lambda r: f"{r.retiros_xfa:.1f}", lambda r: pct(r.p_1_retiro),
            lambda r: f"{r.ev_intento:+.0f} $", lambda r: f"{r.roi:+.1f}"]
    cab = ["Ventaja", "Cuenta", "RTA", "Cartera", "Riesgo/op Combine", "Aprueba", "Días (med.)", "Aprueba ≤ 20 d",
           "Coste/intento", "XFA riesgo · retiro desde", "Cobro XFA (6 m)", "Retiros", "≥ 1 retiro",
           "EV/intento", "ROI"]
    return tabla(d, cols, cab)


def main():
    print("## Preselección\n")
    print(preseleccion())
    print("\n## Rachas (PDF)\n")
    print(rachas_pdf())
    b = pd.read_csv("resultados/barrido_rr.csv")
    for fam in b.familia.unique():
        for sl in sorted(b[b.familia == fam].sl.unique()):
            print(f"\n## {FAMILIAS[fam].nombre} · SL {sl} ATR\n")
            print(barrido(b, fam, sl))
    try:
        c = pd.read_csv("resultados/cartera.csv")
    except FileNotFoundError:
        return
    print("\n## Carteras\n")
    print(cartera(c))


if __name__ == "__main__":
    main()
