import numpy as np
import pandas as pd
import pytest

from fondeo.backtest import REGLAS, a_biblioteca, operaciones
from fondeo.candidatos import POR_ID, winrate_alto
from fondeo.modelo import FAMILIAS, Params, racha_max, simular
from fondeo.topstep import CUENTAS, INSTRUMENTOS, Pierna, combine, xfa


def test_racha_max():
    assert racha_max(np.array([0, 1, 1, 0, 1, 1, 1, 0], bool)) == 3
    assert racha_max(np.zeros(5, bool)) == 0


def test_winrate_alto_son_12():
    ids = {c.id for c in winrate_alto()}
    assert ids == {"S02", "S04", "S05", "N02", "N04", "Z05", "Z08", "Z10", "Z12", "Z13", "Z16", "Z17"}


def test_derivadas_cuadran_con_pdf():
    c = POR_ID["Z13"]
    # beneficio = ganancias brutas - pérdidas brutas
    gan = c.media_ganadora * c.ops * c.wr
    per = c.media_perdedora * c.ops * (1 - c.wr)
    assert gan - per == pytest.approx(c.beneficio / 1000, rel=1e-6)
    assert gan / per == pytest.approx(c.pf, rel=1e-6)


def test_modelo_sin_deriva_no_tiene_ventaja():
    bib = simular(FAMILIAS["ts24_xau"], 0.5, 0.15, Params(sigma=0.11, q=0.1), n_dias=6000, edge=0.0)
    s = bib.resumen()
    assert abs(s["ev_r"]) < 0.01
    assert s["p_sl"] + s["p_tp"] + s["p_t"] == pytest.approx(1.0)
    r = bib.r[bib.tipo > 0]
    assert r.min() >= -1.0 - 1e-9 and r.max() <= 0.15 + 1e-9


def test_bajar_rr_sube_winrate():
    p = Params(sigma=0.11, a=0.05, theta=0.5, q=0.1)
    wr = [simular(FAMILIAS["ts24_xau"], 0.5, k, p, n_dias=3000).resumen()["wr"] for k in (0.5, 0.25, 0.1)]
    assert wr[0] < wr[1] < wr[2]


def test_topstep_sin_operaciones_no_aprueba_ni_quema():
    bib = simular(FAMILIAS["ts24_xau"], 0.5, 0.15, Params(sigma=0.11, q=1e-9), n_dias=200)
    c = combine([Pierna(bib, INSTRUMENTOS["XAU"], 500)], CUENTAS["50K"], n=200, max_dias=30)
    assert c["p_aprueba"] == 0 and c["p_quema"] == 0
    assert c["coste_medio"] == pytest.approx(2 * CUENTAS["50K"].cuota_rta)
    x = xfa([Pierna(bib, INSTRUMENTOS["XAU"], 500)], CUENTAS["50K"], n=200, horizonte=30)
    assert x["cobro_medio"] == 0


def _velas_sinteticas(dias=40, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-05 00:00", periods=dias * 24 * 60, freq="1min", tz="UTC")
    idx = idx[idx.dayofweek < 5]
    ret = rng.normal(0, 0.0004, len(idx))
    c = 3000 * np.exp(np.cumsum(ret))
    o = np.r_[c[0], c[:-1]]
    ruido = np.abs(rng.normal(0, 0.2, len(idx)))
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) + ruido, "low": np.minimum(o, c) - ruido,
                         "close": c}, index=idx)


@pytest.mark.parametrize("fam", ["ts24_xau", "hora_xau"])
def test_backtest_en_velas_sinteticas(fam, tmp_path):
    m1 = _velas_sinteticas()
    ruta = tmp_path / "x.csv"
    m1.rename_axis("time").reset_index().to_csv(ruta, index=False)
    from fondeo.backtest import cargar
    m5 = cargar(ruta)
    ops = operaciones(m5, REGLAS[fam], sl=0.5, k=0.15, tick=0.1)
    assert len(ops) > 20
    assert ops["r"].between(-1.0 - 1e-9, 0.15 + 1e-9).all()
    assert set(ops["tipo"]) <= {1, 2, 3}
    # nunca dos operaciones a la vez
    assert (ops["entrada"].iloc[1:].to_numpy() > ops["salida"].iloc[:-1].to_numpy()).all()
    # salidas antes de las 15:55 NY
    assert (ops["salida"].dt.hour * 60 + ops["salida"].dt.minute <= 15 * 60 + 50).all()
    bib = a_biblioteca(ops, 0.5, 0.15)
    assert bib.n.sum() == len(ops)
