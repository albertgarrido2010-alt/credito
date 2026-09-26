"""Barrido de RR con velas reales.

Ejemplo:
  python3 -m scripts.backtest_real --csv datos/XAUUSD_M1.csv --familia ts24_xau --sl 0.5 --k 0.10 0.15 0.25
  python3 -m scripts.backtest_real --dukascopy XAU 2025-03-01 2026-09-24 --familia hora_xau --sl 0.5 --k 0.25 0.5
"""
import argparse
from datetime import date

import pandas as pd

from fondeo.backtest import REGLAS, a_biblioteca, cargar, descargar_dukascopy, operaciones
from fondeo.modelo import FAMILIAS, racha_max
from fondeo.topstep import CUENTAS, INSTRUMENTOS, Pierna, combine, xfa


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    ap.add_argument("--dukascopy", nargs=3, metavar=("ACTIVO", "DESDE", "HASTA"))
    ap.add_argument("--familia", required=True, choices=list(REGLAS))
    ap.add_argument("--sl", type=float, required=True)
    ap.add_argument("--k", type=float, nargs="+", required=True)
    ap.add_argument("--cuenta", default="50K")
    ap.add_argument("--riesgo", type=float, default=0.25, help="× MLL por operación en el Combine")
    args = ap.parse_args()

    ruta = args.csv
    if args.dukascopy:
        act, d0, d1 = args.dukascopy
        ruta = descargar_dukascopy(act, date.fromisoformat(d0), date.fromisoformat(d1))
    m5 = cargar(ruta)
    ins = INSTRUMENTOS[FAMILIAS[args.familia].activo]
    filas = []
    cu = CUENTAS[args.cuenta]
    for k in args.k:
        ops = operaciones(m5, REGLAS[args.familia], args.sl, k, tick=ins.tick)
        if ops.empty:
            continue
        coste = ops["tipo"].map({3: 1, 2: 2, 1: 2}) * ins.tick * ins.usd_punto + ins.comision_rt
        r_neto = ops["r"] - coste / (ops["sl_pts"] * ins.usd_punto)
        dias = pd.Series(r_neto.values, index=ops["entrada"].dt.date).groupby(level=0).sum()
        eq = r_neto.cumsum()
        bib = a_biblioteca(ops, args.sl, k)
        c = combine([Pierna(bib, ins, args.riesgo * cu.mll)], cu, n=4000)
        x = xfa([Pierna(bib, ins, 0.1 * cu.mll)], cu, n=4000, umbral_retiro=cu.mll)
        filas.append(dict(
            rr=f"1:{k:.2f}", ops=len(ops), ops_dia=len(ops) / m5.index.normalize().nunique(),
            acierto=(r_neto > 0).mean(), p_sl=(ops.tipo == 2).mean(), p_tp=(ops.tipo == 3).mean(),
            ev_r=r_neto.mean(), pf=r_neto[r_neto > 0].sum() / -r_neto[r_neto < 0].sum(),
            benef_r=eq.iloc[-1], dd_r=(eq.cummax().clip(lower=0) - eq).max(),
            stops_seguidos=racha_max((ops.tipo == 2).to_numpy()), perd_seguidas=racha_max((r_neto <= 0).to_numpy()),
            tps_seguidos=racha_max((ops.tipo == 3).to_numpy()), gan_seguidas=racha_max((r_neto > 0).to_numpy()),
            dias_perd_seguidos=racha_max((dias < 0).to_numpy()),
            aprueba=c["p_aprueba"], dias_aprobar=c["dias_mediana"], cobro_xfa=x["cobro_medio"],
            ev_intento=c["p_aprueba"] * x["cobro_medio"] - c["coste_medio"]))
    print(pd.DataFrame(filas).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
