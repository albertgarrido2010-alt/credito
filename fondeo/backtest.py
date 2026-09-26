"""Backtest con velas reales de las familias preseleccionadas (Turtle Soup + SMA y Hora + SMA).

Reglas (página 8 del PDF de candidatos):
  * Turtle Soup + SMA: en cada ventana de 30 min, la primera vela M5 que perfora el mínimo de las N
    anteriores y cierra por encima de él, con cierre > SMA(200) → compra a la apertura siguiente
    (espejo en ventas si es «combinado»).
  * Hora + SMA: cada 30 min, si el cierre de la última vela M5 está por encima de la SMA(200) → compra al
    cierre (solo compras si es «alcistas»).
  * SL = sl·ATR diario (ATR 14 de la sesión anterior), TP = k·SL. SL primero si SL y TP caben en la misma
    vela. El TP (límite) exige que el precio lo pase 1 tick. Cierre forzado a las 15:55 NY.
    Una operación abierta a la vez.

Datos: CSV con columnas `time,open,high,low,close` (UTC) en M1 o M5, o descarga de Dukascopy
(`descargar_dukascopy`), que necesita acceso de red a datafeed.dukascopy.com.

El resultado (`operaciones`) se puede pasar a `a_biblioteca` y usar en el simulador de Topstep en lugar
del modelo.
"""
from __future__ import annotations

import lzma
import struct
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .modelo import MAXT, Biblioteca

NY = "America/New_York"
SIMBOLOS_DUKAS = {"XAU": ("XAUUSD", 1000.0), "NQ": ("USATECHIDXUSD", 1000.0), "ES": ("USA500IDXUSD", 1000.0)}


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------
def descargar_dukascopy(activo: str, desde: date, hasta: date, carpeta: str | Path = "datos") -> Path:
    """Descarga velas M1 (BID) día a día de Dukascopy y las guarda en un CSV."""
    import requests

    sym, escala = SIMBOLOS_DUKAS[activo]
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    salida = carpeta / f"{sym}_M1_{desde}_{hasta}.csv"
    filas = []
    d = desde
    while d <= hasta:
        url = (f"https://datafeed.dukascopy.com/datafeed/{sym}/{d.year}/{d.month - 1:02d}/"
               f"{d.day:02d}/BID_candles_min_1.bi5")
        r = requests.get(url, timeout=30)
        if r.status_code == 200 and r.content:
            raw = lzma.decompress(r.content)
            base = pd.Timestamp(d, tz="UTC")
            for off in range(0, len(raw), 24):
                t, o, c, lo, hi, _v = struct.unpack(">5if", raw[off:off + 24])
                filas.append((base + pd.Timedelta(seconds=t), o / escala, hi / escala, lo / escala, c / escala))
        d += timedelta(days=1)
    df = pd.DataFrame(filas, columns=["time", "open", "high", "low", "close"])
    df.to_csv(salida, index=False)
    return salida


def cargar(ruta: str | Path) -> pd.DataFrame:
    """CSV (UTC) → velas M5 en hora de Nueva York."""
    df = pd.read_csv(ruta, parse_dates=["time"])
    df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_convert(NY)
    df = df.set_index("time").sort_index()
    m5 = df.resample("5min", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    return m5


def atr_diario(m5: pd.DataFrame, n: int = 14) -> pd.Series:
    """ATR(n) de sesiones 18:00→17:00 NY, desplazado un día (solo información pasada)."""
    sesion = (m5.index + pd.Timedelta(hours=6)).date  # 18:00 NY pasa a ser el inicio del día siguiente
    d = m5.groupby(sesion).agg(high=("high", "max"), low=("low", "min"), close=("close", "last"))
    prev = d["close"].shift()
    tr = pd.concat([d["high"] - d["low"], (d["high"] - prev).abs(), (d["low"] - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean().shift()


# ---------------------------------------------------------------------------
# Señales
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Regla:
    tipo: str               # "ts" o "hora"
    ini: str                # "02:00"
    fin: str                # "14:55"
    n_sma: int = 200
    n_ts: int = 24          # velas del mínimo/máximo (Turtle Soup)
    lados: str = "ambos"    # "ambos" o "largos"
    cierre: str = "15:55"


REGLAS = {
    "ts24_xau": Regla("ts", "02:00", "14:55", n_ts=24, lados="ambos"),
    "ts12_nq": Regla("ts", "09:30", "14:55", n_ts=12, lados="ambos"),
    "ts12_es": Regla("ts", "09:30", "14:55", n_ts=12, lados="ambos"),
    "hora_xau": Regla("hora", "02:00", "14:30", lados="largos"),
}


def _hm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def senales(m5: pd.DataFrame, regla: Regla) -> pd.DataFrame:
    """Columnas `dir` (+1/−1/0) y `entrada` (precio de entrada) por vela señal."""
    c = m5["close"]
    sma = c.rolling(regla.n_sma).mean()
    minuto = m5.index.hour * 60 + m5.index.minute
    en_ventana = (minuto >= _hm(regla.ini)) & (minuto <= _hm(regla.fin))
    d = pd.Series(0, index=m5.index)
    if regla.tipo == "ts":
        mn = m5["low"].shift().rolling(regla.n_ts).min()
        mx = m5["high"].shift().rolling(regla.n_ts).max()
        larga = (m5["low"] < mn) & (c > mn) & (c > sma)
        corta = (m5["high"] > mx) & (c < mx) & (c < sma)
        d[larga] = 1
        if regla.lados == "ambos":
            d[corta & ~larga] = -1
        d[~en_ventana] = 0
        # solo la primera señal de cada ventana de 30 min
        ventana = m5.index.floor("30min")
        primera = (d != 0) & ~((d != 0).groupby(ventana).cumsum() > 1)
        d[~primera] = 0
        entrada = m5["open"].shift(-1)          # apertura siguiente
    else:
        # la vela que cierra en :00/:30 es la que abre en :25/:55
        chequeo = en_ventana & ((m5.index.minute + 5) % 30 == 0)
        d[chequeo & (c > sma)] = 1
        if regla.lados == "ambos":
            d[chequeo & (c < sma)] = -1
        entrada = c
    return pd.DataFrame({"dir": d, "entrada": entrada})


# ---------------------------------------------------------------------------
# Motor
# ---------------------------------------------------------------------------
def operaciones(m5: pd.DataFrame, regla: Regla, sl: float, k: float, tick: float,
                tcap_min: int | None = None) -> pd.DataFrame:
    """Simula las operaciones vela a vela. Devuelve una fila por operación con R, tipo de salida y MAE."""
    sig = senales(m5, regla)
    atr = atr_diario(m5)
    sesion = (m5.index + pd.Timedelta(hours=6)).date
    atr_v = pd.Series(sesion, index=m5.index).map(atr).to_numpy()
    o, h, l, c = (m5[x].to_numpy() for x in ("open", "high", "low", "close"))
    minuto = (m5.index.hour * 60 + m5.index.minute).to_numpy()
    fecha = m5.index.date
    cierre = _hm(regla.cierre) - 5  # la vela 15:50 cierra a las 15:55
    dirs, entradas = sig["dir"].to_numpy(), sig["entrada"].to_numpy()

    filas = []
    i, n = 0, len(m5)
    while i < n - 1:
        if dirs[i] == 0 or np.isnan(atr_v[i]) or np.isnan(entradas[i]):
            i += 1
            continue
        dr, px = dirs[i], entradas[i]
        dist = sl * atr_v[i]
        stop, tp = px - dr * dist, px + dr * k * dist
        # Hora: entrada al cierre de i. Turtle Soup: entrada a la apertura de i+1. En los dos casos la
        # primera vela que puede tocar SL/TP es la i+1.
        j = i + 1
        mae, salida, tipo = 0.0, None, 1
        while j < n and fecha[j] == fecha[i]:
            adv = (l[j] - px) if dr > 0 else (px - h[j])
            mae = min(mae, adv)
            toca_sl = (l[j] <= stop) if dr > 0 else (h[j] >= stop)
            toca_tp = (h[j] >= tp + tick) if dr > 0 else (l[j] <= tp - tick)
            if toca_sl:
                salida, tipo = stop, 2
                break
            if toca_tp:
                salida, tipo = tp, 3
                break
            if minuto[j] >= cierre or (tcap_min and (j - i) * 5 >= tcap_min):
                salida, tipo = c[j], 1
                break
            j += 1
        if salida is None:
            break
        r = dr * (salida - px) / dist
        filas.append(dict(entrada=m5.index[i], salida=m5.index[min(j, n - 1)], dir=dr, precio=px,
                          sl_pts=dist, r=r, tipo=tipo, mae_r=max(mae / dist, -1.0)))
        i = j + 1
    return pd.DataFrame(filas)


def a_biblioteca(ops: pd.DataFrame, sl: float, k: float, dias_habiles: list | None = None) -> Biblioteca:
    """Agrupa las operaciones reales por día en el formato del simulador de Topstep."""
    ops = ops.copy()
    ops["dia"] = ops["entrada"].dt.date
    dias = sorted(set(dias_habiles or ops["dia"]))
    pos = {d: i for i, d in enumerate(dias)}
    nd = len(dias)
    R = np.full((nd, MAXT), np.nan)
    T = np.zeros((nd, MAXT), np.int8)
    M = np.zeros((nd, MAXT))
    TI = np.zeros((nd, MAXT), np.int32)
    TO = np.zeros((nd, MAXT), np.int32)
    cnt = np.zeros(nd, np.int32)
    for fila in ops.itertuples():
        d = pos[fila.dia]
        c = cnt[d]
        if c >= MAXT:
            continue
        R[d, c], T[d, c], M[d, c] = fila.r, fila.tipo, fila.mae_r
        TI[d, c] = fila.entrada.hour * 60 + fila.entrada.minute
        TO[d, c] = fila.salida.hour * 60 + fila.salida.minute
        cnt[d] += 1
    return Biblioteca(R, T, M, TI, TO, cnt, np.ones(nd), sl, k)
