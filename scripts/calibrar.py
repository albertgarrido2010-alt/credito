"""Calibra el modelo de barreras de cada familia con las cifras del PDF y valida dejando una fuera.

Uso: python3 -m scripts.calibrar   ->  resultados/calibracion.json y resultados/validacion.csv
"""
import csv
import json
from dataclasses import asdict

import numpy as np

from fondeo.candidatos import POR_ID
from fondeo.modelo import FAMILIAS, Params, calibrar, perdida, simular, COSTE_PDF_ATR

GRUPOS = {
    "ts24_xau": (["Z07", "Z10", "Z12", "Z13"], Params(sigma=0.109, a=0.05, theta=0.5, b=0.0, q=0.106), {}),
    "hora_xau": (["Z01", "Z05", "Z08"], Params(sigma=0.11, a=0.0, theta=0.5, b=0.01, q=0.3), {}),
    "ts12_nq": (["N02", "N04"], Params(sigma=0.2, a=0.08, theta=0.5, b=0.0, q=0.25), {}),
    "ts12_es": (["S02"], Params(sigma=0.2, a=0.05, theta=0.5, b=0.0, q=0.25), {"theta": 0.5, "b": 0.0}),
}


def escala_edge(fam, cands, p):
    """Factor que iguala la esperanza bruta media del modelo a la del PDF (edge=1 -> nivel in-sample)."""
    obj = np.mean([c.ev_r + COSTE_PDF_ATR / c.sl for c in cands])
    sim = np.mean([simular(fam, c.sl, c.k, p, n_dias=6000, seed=21).resumen()["ev_r"] for c in cands])
    e = obj / sim if sim > 0 else 1.0
    # la esperanza es casi lineal en la deriva; un paso de corrección
    sim2 = np.mean([simular(fam, c.sl, c.k, p, n_dias=6000, seed=21, edge=e).resumen()["ev_r"] for c in cands])
    return float(e * obj / sim2) if sim2 > 0 else e


def main():
    out, filas = {}, []
    for clave, (ids, ini, fijos) in GRUPOS.items():
        fam = FAMILIAS[clave]
        cands = [POR_ID[i] for i in ids]
        p = calibrar(fam, cands, ini, fijos, iters=400)
        e = escala_edge(fam, cands, p)
        tot, det = perdida(p, fam, cands, n_dias=6000, detalle=True)
        out[clave] = dict(params=asdict(p), edge_in_sample=e, perdida=tot, ids=ids)
        print(clave, p, "edge", round(e, 3), "loss", round(tot, 2), flush=True)
        for cid, s, evb in det:
            c = POR_ID[cid]
            filas.append(dict(familia=clave, id=cid, modo="ajuste", sl=c.sl, k=c.k,
                              pdf_t=c.p_t, pdf_sl=c.p_sl, pdf_tp=c.p_tp, pdf_wr=c.wr, pdf_ops=c.ops_dia,
                              sim_t=s["p_t"], sim_sl=s["p_sl"], sim_tp=s["p_tp"], sim_wr=s["wr"],
                              sim_ops=s["ops_dia"]))
        # validación dejando una fuera (solo familias con >= 3 configuraciones)
        if len(ids) >= 3:
            for fuera in ids:
                resto = [POR_ID[i] for i in ids if i != fuera]
                p_loo = calibrar(fam, resto, p, fijos, iters=250)
                c = POR_ID[fuera]
                s = simular(fam, c.sl, c.k, p_loo, n_dias=6000, seed=5).resumen()
                filas.append(dict(familia=clave, id=fuera, modo="predicción (fuera del ajuste)", sl=c.sl, k=c.k,
                                  pdf_t=c.p_t, pdf_sl=c.p_sl, pdf_tp=c.p_tp, pdf_wr=c.wr, pdf_ops=c.ops_dia,
                                  sim_t=s["p_t"], sim_sl=s["p_sl"], sim_tp=s["p_tp"], sim_wr=s["wr"],
                                  sim_ops=s["ops_dia"]))
                print("  LOO", fuera, "wr sim %.3f pdf %.3f | T/SL/TP sim %.2f/%.2f/%.2f pdf %.2f/%.2f/%.2f | ops %.2f/%.2f"
                      % (s["wr"], c.wr, s["p_t"], s["p_sl"], s["p_tp"], c.p_t, c.p_sl, c.p_tp, s["ops_dia"], c.ops_dia),
                      flush=True)
    with open("resultados/calibracion.json", "w") as f:
        json.dump(out, f, indent=2)
    with open("resultados/validacion.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        for r in filas:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})


if __name__ == "__main__":
    main()
