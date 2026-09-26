"""Página de resultados con el formato de la «tabla de construcción» del PDF de candidatos.

Uso: python3 -m scripts.tabla_resultados  ->  resultados/tabla_resultados.html (fragmento) y .csv
Cifras del modelo calibrado con ventaja in-sample y costes de futuros, en 400 días (~18 meses),
1 R = 1.000 $ sobre 100.000 $ como en el PDF. EV/reto = Topstep 50K RTA ON (in-sample / mitad).
"""
import json

import numpy as np
import pandas as pd

from fondeo.modelo import FAMILIAS, Params, simular
from fondeo.topstep import INSTRUMENTOS
from scripts.barrido_rr import neta

N_DIAS = 400
FILAS = [  # id, familia, sl, k, tipo
    ("Z10", "ts24_xau", 0.35, 0.25, "original"), ("Z10-b", "ts24_xau", 0.35, 0.10, "bajado"),
    ("Z13", "ts24_xau", 0.50, 0.15, "original"), ("Z13-b", "ts24_xau", 0.50, 0.10, "bajado"),
    ("Z13-o", "ts24_xau", 0.50, 0.20, "optimizado"),
    ("N02", "ts12_nq", 0.35, 0.25, "original"), ("N02-b", "ts12_nq", 0.35, 0.10, "bajado"),
    ("N02-o", "ts12_nq", 0.35, 0.35, "optimizado"),
    ("Z05", "hora_xau", 0.50, 0.25, "original"), ("Z05-b", "hora_xau", 0.50, 0.10, "bajado"),
    ("Z05-o", "hora_xau", 0.50, 0.50, "optimizado"),
    ("Z08", "hora_xau", 0.35, 0.25, "original"), ("Z08-o", "hora_xau", 0.35, 0.50, "optimizado"),
]
TXT = {
    "ts24_xau": ("Turtle Soup + SMA", "XAUUSD", "SMA200 · N24 · combinado", "02:00-14:55<br>08:00-20:55"),
    "ts12_nq": ("Turtle Soup + SMA", "US100", "SMA200 · N12 · combinado", "09:30-14:55<br>15:30-20:55"),
    "hora_xau": ("Hora + SMA", "XAUUSD", "SMA200 · cada 30 min · alcistas", "02:00-14:30<br>08:00-20:30"),
}


def metricas(bib, reps=300, seed=5):
    rng = np.random.default_rng(seed)
    dia = np.nansum(bib.r, axis=1)
    dd, peor, meses = [], [], []
    for _ in range(reps):
        x = dia[rng.integers(0, len(dia), N_DIAS)]
        eq = np.cumsum(x)
        dd.append((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max())
        peor.append(x.min())
        meses.append((x[: N_DIAS // 21 * 21].reshape(-1, 21).sum(axis=1) > 0).mean())
    return np.median(dd), np.median(peor), np.mean(meses)


def main():
    cal = json.load(open("resultados/calibracion.json"))
    b = pd.read_csv("resultados/barrido_rr.csv")
    b = b[b.cuenta == "50K"]
    filas = []
    for cid, fam, sl, k, tipo in FILAS:
        c = cal[fam]
        f = FAMILIAS[fam]
        ins = INSTRUMENTOS[f.activo]
        bib = neta(simular(f, sl, k, Params(**c["params"]), n_dias=24000, seed=31, edge=c["edge_in_sample"],
                           tp_extra_atr=ins.tick / ins.atr), ins, sl)
        s = bib.resumen()
        dd, peor, meses = metricas(bib)
        ops = s["ops_dia"] * N_DIAS
        ben = s["ev_r"] * ops * 1000
        ev = {e: b[(b.familia == fam) & (b.sl == sl) & (b.k == k) & (b.escenario == e)].ev_intento.iloc[0]
              for e in ("in-sample", "mitad")}
        filas.append(dict(id=cid, tipo=tipo, familia=fam, sl=sl, k=k, ops=ops, ops_dia=s["ops_dia"], wr=s["wr"],
                          pf=s["pf"], beneficio=ben, dd=dd * 1000, rf=ben / (dd * 1000), meses=meses,
                          t=s["p_t"], s=s["p_sl"], tp=s["p_tp"], peor=peor, ev_in=ev["in-sample"],
                          ev_mitad=ev["mitad"]))
        print(cid, round(s["wr"], 3), round(ben), flush=True)
    df = pd.DataFrame(filas).sort_values("beneficio", ascending=False)
    df.to_csv("resultados/tabla_resultados.csv", index=False)
    open("resultados/tabla_resultados.html", "w").write(html(df))


def n(x, d=0):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def html(df):
    cab = ["ID", "Familia", "Activo", "Señal / filtro", "NY / España", "SL (ATRd)", "RR", "Ops", "Ops/día",
           "% acierto", "PF", "Beneficio", "% benef.", "DD máx.", "% DD", "RF", "Meses +", "T/SL/TP",
           "Peor día", "EV/reto 50K<br>in-s. / mitad"]
    clase = {"original": "", "bajado": "baj", "optimizado": "opt"}
    tr = []
    for r in df.itertuples():
        fam, act, sen, hor = TXT[r.familia]
        tr.append(
            f"<tr class='{clase[r.tipo]}'><td class='id'>{r.id}</td><td>{fam}</td><td>{act}</td><td>{sen}</td>"
            f"<td>{hor}</td><td>{n(r.sl, 2)}</td><td class='am b'>{n(r.k, 2)}</td><td>{n(r.ops)}</td>"
            f"<td>{n(r.ops_dia, 1)}</td><td class='am b'>{n(100 * r.wr, 1)} %</td><td>{n(r.pf, 2)}</td>"
            f"<td>{'+' if r.beneficio >= 0 else ''}{n(r.beneficio)} $</td>"
            f"<td class='ve b'>{'+' if r.beneficio >= 0 else ''}{n(r.beneficio / 1000, 1)} %</td>"
            f"<td>-{n(r.dd)} $</td><td class='ro b'>-{n(r.dd / 1000, 1)} %</td><td>{n(r.rf, 1)}</td>"
            f"<td>{n(100 * r.meses)} %</td><td>{n(100 * r.t)}/{n(100 * r.s)}/{n(100 * r.tp)} %</td>"
            f"<td>{n(r.peor, 1)} R</td><td class='b'>{'+' if r.ev_in >= 0 else ''}{n(r.ev_in)} / "
            f"{'+' if r.ev_mitad >= 0 else ''}{n(r.ev_mitad)} $</td></tr>")
    return f"""<div class='hoja'>
<h1 class='tr'>Resultados — tabla de construcción (RR original, bajado y optimizado)</h1>
<p class='sub'>Modelo calibrado con el PDF de candidatos · ventaja in-sample · costes de futuros Topstep (micros) ·
400 días (~18 meses) · riesgo 1 % (1.000 $) por operación · cuenta 100.000 $</p>
<table class='tr'><thead><tr>{''.join(f'<th>{c}</th>' for c in cab)}</tr></thead><tbody>{''.join(tr)}</tbody></table>
<ul class='notas'>
<li>ID sin sufijo = RR del PDF · <b>-b</b> = RR bajado a 1:0,10 (fondo gris) · <b>-o</b> = mejor RR del barrido (fondo azul).
Z = oro (XAUUSD / MGC), N = Nasdaq 100 (US100 / MNQ). RR = TP:SL de 1 R.</li>
<li>Beneficio, DD, meses positivos y peor día: mediana de 300 muestras de 400 días del modelo. No son un backtest con velas reales.</li>
<li>EV/reto = Topstep 50K RTA ON con el mejor riesgo: P(aprobar) × cobro en la XFA (6 meses) − coste del reto, con la ventaja in-sample y con la mitad.</li>
</ul></div>"""


if __name__ == "__main__":
    main()
