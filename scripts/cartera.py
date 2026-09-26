"""Cartera Topstep: una estrategia por familia en la misma cuenta, con el RR original y con el RR elegido.

Uso: python3 -m scripts.cartera   (requiere resultados/calibracion.json y resultados/barrido_rr.csv)
Salida: resultados/cartera.csv
"""
import csv
import json
from multiprocessing import Pool

import numpy as np
import pandas as pd

from fondeo.modelo import FAMILIAS, Params, simular
from fondeo.topstep import CUENTAS, INSTRUMENTOS, Pierna, combine, xfa

EDGES = {"in-sample": 1.0, "mitad": 0.5, "sin ventaja": 0.0}
RIESGO = [0.08, 0.10, 0.15, 0.20, 0.25, 0.35]   # × MLL por operación y pierna
RIESGO_XFA = [0.06, 0.10, 0.15, 0.20]
UMBRAL = [0.5, 1.0, 1.5]
N = 4000

# RR original del PDF (una por familia; la que mejor sale de cada familia en el informe)
ORIGINAL = {"ts24_xau": (0.50, 0.15), "hora_xau": (0.50, 0.25), "ts12_nq": (0.35, 0.25)}
# Mismo SL con el TP a la mitad o menos: acierto 85-88 %
BAJADO = {"ts24_xau": (0.50, 0.10), "hora_xau": (0.50, 0.12), "ts12_nq": (0.35, 0.12)}


def elegir_rr(barrido: pd.DataFrame) -> dict:
    """Por familia, el (SL, RR) con más EV por intento en 50K; se exige que siga siendo el mejor o casi
    (≥ 80 % del máximo) con la mitad de ventaja, para no elegir un punto frágil."""
    out = {}
    for fam in ORIGINAL:
        d = barrido[(barrido.familia == fam) & (barrido.cuenta == "50K")]
        a = d[d.escenario == "in-sample"].set_index(["sl", "k"])["ev_intento"]
        m = d[d.escenario == "mitad"].set_index(["sl", "k"])["ev_intento"]
        puntaje = (a / a.abs().max()).clip(lower=-1) + (m / m.abs().max()).clip(lower=-1)
        out[fam] = tuple(puntaje.idxmax())
    return out


def _bibs(cal, config, edge_esc):
    bibs = []
    for fam, (sl, k) in config.items():
        f = FAMILIAS[fam]
        ins = INSTRUMENTOS[f.activo]
        c = cal[fam]
        bib = simular(f, sl, k, Params(**c["params"]), n_dias=12000, seed=41,
                      edge=c["edge_in_sample"] * EDGES[edge_esc], tp_extra_atr=ins.tick / ins.atr)
        bibs.append((bib, ins))
    return bibs


def tarea(args):
    cal, nombre, config, esc, nc, rta = args
    cu = CUENTAS[nc]
    bibs = _bibs(cal, config, esc)
    piernas = lambda frac: [Pierna(b, ins, frac * cu.mll) for b, ins in bibs]
    mejor_x = max(((rx, um, xfa(piernas(rx), cu, rta=rta, n=N, umbral_retiro=um * cu.mll))
                   for rx in RIESGO_XFA for um in UMBRAL), key=lambda t: t[2]["cobro_medio"])
    rx, um, x = mejor_x
    filas = []
    for rc in RIESGO:
        c = combine(piernas(rc), cu, rta=rta, n=N)
        ev = c["p_aprueba"] * x["cobro_medio"] - c["coste_medio"]
        filas.append(dict(cartera=nombre, config=" + ".join(f"{f}(SL {s}, 1:{k})" for f, (s, k) in config.items()),
                          escenario=esc, cuenta=nc, rta="ON" if rta else "OFF", riesgo_pierna=rc * cu.mll,
                          p_aprueba=c["p_aprueba"], p_quema=c["p_quema"], dias_aprobar=c["dias_mediana"],
                          p_aprueba_20d=c["p_aprueba_20d"], coste_intento=c["coste_medio"],
                          riesgo_xfa=rx * cu.mll, umbral_retiro=um * cu.mll, cobro_xfa=x["cobro_medio"],
                          retiros_xfa=x["retiros_medios"], p_1_retiro=x["p_1_retiro"],
                          p_3_retiros=x["p_3_retiros"], ev_intento=ev, roi=ev / c["coste_medio"]))
    best = max(filas, key=lambda f: f["ev_intento"])
    print(nombre, esc, nc, "RTA", best["rta"], "P %.3f EV %.0f ROI %.2f" % (best["p_aprueba"], best["ev_intento"], best["roi"]),
          flush=True)
    return filas


def main():
    cal = json.load(open("resultados/calibracion.json"))
    barrido = pd.read_csv("resultados/barrido_rr.csv")
    elegido = elegir_rr(barrido)
    print("RR elegido:", elegido)
    carteras = {"RR original (Z13 + Z05 + N02)": ORIGINAL, "RR bajado (acierto 85-88 %)": BAJADO,
                "RR optimizado": elegido}
    tareas = [(cal, n, c, esc, nc, rta) for n, c in carteras.items() for esc in EDGES
              for nc in ("50K", "100K") for rta in (True, False)]
    with Pool(4) as p:
        res = p.map(tarea, tareas, chunksize=1)
    filas = [f for r in res for f in r]
    with open("resultados/cartera.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        for r in filas:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
    json.dump({k: list(v) for k, v in elegido.items()}, open("resultados/rr_elegido.json", "w"), indent=2)


if __name__ == "__main__":
    main()
