"""Barrido de RR (TP:SL) de las familias preseleccionadas + simulación Topstep.

Uso: python3 -m scripts.barrido_rr   (requiere resultados/calibracion.json)
Salida: resultados/barrido_rr.csv (una fila por familia · SL · RR · escenario de ventaja · cuenta)
"""
import csv
import json
from dataclasses import replace
from multiprocessing import Pool

import numpy as np

from fondeo.modelo import FAMILIAS, Biblioteca, Params, rachas, simular
from fondeo.topstep import CUENTAS, INSTRUMENTOS, Pierna, coste_r, combine, xfa

K_GRID = [0.08, 0.10, 0.12, 0.15, 0.20, 0.25, 0.35, 0.50]
SL_FAM = {"ts24_xau": [0.35, 0.50], "ts12_nq": [0.35, 0.50], "hora_xau": [0.35, 0.50], "ts12_es": [0.35]}
# Estrategias del PDF que son un punto de esta rejilla
ORIGEN = {("ts24_xau", 0.35, 0.50): "Z07", ("ts24_xau", 0.35, 0.25): "Z10", ("ts24_xau", 0.50, 0.25): "Z12",
          ("ts24_xau", 0.50, 0.15): "Z13", ("ts12_nq", 0.35, 0.25): "N02", ("ts12_nq", 0.50, 0.15): "N04",
          ("hora_xau", 0.35, 0.50): "Z01", ("hora_xau", 0.35, 0.25): "Z08", ("hora_xau", 0.50, 0.25): "Z05",
          ("ts12_es", 0.35, 0.25): "S02"}
EDGES = {"in-sample": 1.0, "mitad": 0.5, "sin ventaja": 0.0}
RIESGO_COMBINE = [0.10, 0.15, 0.25, 0.35, 0.50, 0.75]   # × MLL por operación
RIESGO_XFA = [0.05, 0.10, 0.15, 0.20, 0.30]
UMBRAL_XFA = [0.0, 0.5, 1.0, 1.5, 2.0]                     # × MLL de saldo mínimo para pedir retiro
N_DIAS_MUESTRA = 400                               # ~18 meses, como el PDF
N_SIMS = 2000


def neta(bib: Biblioteca, ins, sl) -> Biblioteca:
    """Copia de la biblioteca con el resultado neto de costes de futuros (ATR típico)."""
    c = np.select([bib.tipo == 3, bib.tipo == 2, bib.tipo == 1],
                  [coste_r(ins, sl, 3), coste_r(ins, sl, 2), coste_r(ins, sl, 1)], 0.0)
    return replace(bib, r=bib.r - c)


def dd_max(bib: Biblioteca, n_dias: int, reps: int = 300, seed: int = 9):
    rng = np.random.default_rng(seed)
    dia = np.nansum(bib.r, axis=1)
    out = []
    for _ in range(reps):
        eq = np.cumsum(dia[rng.integers(0, len(dia), n_dias)])
        out.append((np.maximum.accumulate(np.maximum(eq, 0)) - eq).max())
    return float(np.median(out)), float(np.percentile(out, 95))


def tarea(args):
    clave, p_dict, e_in, sl, k, esc = args
    fam = FAMILIAS[clave]
    ins = INSTRUMENTOS[fam.activo]
    p = Params(**p_dict)
    edge = e_in * EDGES[esc]
    bib = simular(fam, sl, k, p, n_dias=24000, seed=31, edge=edge, tp_extra_atr=ins.tick / ins.atr)
    bn = neta(bib, ins, sl)
    s = bn.resumen()
    n_ops = int(round(s["ops_dia"] * N_DIAS_MUESTRA))
    ra = rachas(bn, n_ops, n_rep=300)
    dd50, dd95 = dd_max(bn, N_DIAS_MUESTRA)
    base = dict(familia=clave, activo=ins.nombre, sl=sl, k=k, rr=f"1:{k:.2f}", escenario=esc,
                origen=ORIGEN.get((clave, sl, k), ""),
                wr=s["wr"], p_t=s["p_t"], p_sl=s["p_sl"], p_tp=s["p_tp"], ev_r=s["ev_r"], pf=s["pf"],
                ops_dia=s["ops_dia"], ev_dia_r=s["ev_r"] * s["ops_dia"], dur_min=s["dur_min"],
                benef_18m_r=s["ev_r"] * n_ops, dd_18m_r=dd50, dd_18m_r_p95=dd95,
                racha_sl=ra["sl"][0], racha_sl_p95=ra["sl"][1], racha_perd=ra["perd"][0],
                racha_perd_p95=ra["perd"][1], racha_tp=ra["tp"][0], racha_tp_p95=ra["tp"][1],
                racha_gan=ra["gan"][0], racha_gan_p95=ra["gan"][1],
                racha_dias_perd=ra["dias_perd"][0], racha_dias_perd_p95=ra["dias_perd"][1],
                coste_tp_r=coste_r(ins, sl, 3))
    filas = []
    for nc in ("50K", "100K"):
        cu = CUENTAS[nc]
        # cuenta financiada: mejor riesgo y umbral de retiro
        mejor_x = None
        for rx in RIESGO_XFA:
            for um in UMBRAL_XFA:
                x = xfa([Pierna(bib, ins, rx * cu.mll)], cu, rta=True, n=N_SIMS, umbral_retiro=um * cu.mll)
                if mejor_x is None or x["cobro_medio"] > mejor_x[2]["cobro_medio"]:
                    mejor_x = (rx, um, x)
        rx, um, x = mejor_x
        mejor = None
        for rc in RIESGO_COMBINE:
            c = combine([Pierna(bib, ins, rc * cu.mll)], cu, rta=True, n=N_SIMS)
            ev = c["p_aprueba"] * x["cobro_medio"] - c["coste_medio"]
            if mejor is None or ev > mejor["ev_intento"]:
                mejor = dict(cuenta=nc, riesgo_combine=rc * cu.mll, p_aprueba=c["p_aprueba"],
                             p_quema=c["p_quema"], dias_aprobar=c["dias_mediana"],
                             p_aprueba_20d=c["p_aprueba_20d"], coste_intento=c["coste_medio"],
                             riesgo_xfa=rx * cu.mll, umbral_retiro=um * cu.mll,
                             cobro_xfa=x["cobro_medio"], retiros_xfa=x["retiros_medios"],
                             p_1_retiro=x["p_1_retiro"], p_3_retiros=x["p_3_retiros"],
                             ev_intento=ev, roi=ev / c["coste_medio"])
        filas.append({**base, **mejor})
    print(clave, sl, k, esc, "wr %.3f ev %.4f | 50K EV %.0f ROI %.2f" %
          (s["wr"], s["ev_r"], filas[0]["ev_intento"], filas[0]["roi"]), flush=True)
    return filas


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--cal", default="resultados/calibracion.json")
    ap.add_argument("--out", default="resultados/barrido_rr.csv")
    ap.add_argument("--familias", nargs="*")
    ap.add_argument("--procesos", type=int, default=4)
    args = ap.parse_args()
    cal = json.load(open(args.cal))
    tareas = []
    for clave, sls in SL_FAM.items():
        if clave not in cal or (args.familias and clave not in args.familias):
            continue
        for esc in EDGES:
            for sl in sls:
                for k in K_GRID:
                    tareas.append((clave, cal[clave]["params"], cal[clave]["edge_in_sample"], sl, k, esc))
    with Pool(args.procesos) as pool:
        res = pool.map(tarea, tareas, chunksize=1)
    filas = [f for r in res for f in r]
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        for r in filas:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})


if __name__ == "__main__":
    main()
