"""Simulador Monte Carlo de Topstep: Trading Combine + Express Funded Account (XFA).

Reglas (capturas de topstep.com/topstep-prop del 25-09-2026, opción «No activation fee», y
Reglas_FTMO_Topstep.txt):
  * Combine: objetivo, MLL arrastrado con el saldo de CIERRE, fijo al llegar al saldo inicial, comprobado
    en tiempo real con flotante; consistencia 55 % (objetivo efectivo = max(objetivo, mejor día / 0,55));
    con RTA ON, límite diario (DLL) que corta el día sin quemar la cuenta; tope de contratos.
  * XFA: saldo 0, suelo −MLL arrastrado al cierre hasta 0; fijo en 0 tras el primer retiro; escalado de
    contratos por saldo; retiro con 5 días ≥ 150 $ o 3 días con el mejor ≤ 40 % del neto; retiro máx.
    50 % del saldo con tope (doble con RTA); reparto 90 %.
  * Coste del reto = cuota mensual × meses empezados (el reinicio mensual va incluido al renovar).
Todo en micros (MGC, MNQ, MES). Comisión y deslizamiento: 1 tick en entrada, stop y salida a mercado; el
TP es límite y exige que el precio lo pase 1 tick (se modela en la biblioteca con `tp_extra_atr`).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .modelo import Biblioteca

DIAS_MES = 21


@dataclass(frozen=True)
class Cuenta:
    nombre: str
    mll: float
    objetivo: float
    dll: float                 # solo con RTA ON
    cuota_rta: float           # $/mes con RTA ON
    cuota: float               # $/mes con RTA OFF
    micros_max: int            # tope del Combine
    tope_retiro: float         # por retiro sin RTA (con RTA se dobla)
    escalado_xfa: tuple        # ((saldo mínimo, micros máx.), ...)


CUENTAS = {
    "50K": Cuenta("50K", 2000, 3000, 1000, 85, 95, 50, 3000, ((0, 20), (1500, 30), (2000, 50))),
    # [A CONFIRMAR] escalado XFA de 100K/150K y tope de retiro de 150K
    "100K": Cuenta("100K", 3000, 6000, 2000, 129, 149, 100, 4000,
                   ((0, 30), (1500, 40), (2000, 50), (3000, 100))),
    "150K": Cuenta("150K", 4500, 9000, 3000, 199, 229, 150, 5000,
                   ((0, 30), (1500, 40), (2000, 50), (3000, 100), (4500, 150))),
}


@dataclass(frozen=True)
class Instrumento:
    nombre: str
    usd_punto: float     # $ por punto y contrato
    tick: float          # puntos
    comision_rt: float   # $ ida y vuelta por contrato [A CONFIRMAR]
    atr: float           # ATR diario típico en puntos (supuesto; se varía ±25 % por día)


INSTRUMENTOS = {
    "XAU": Instrumento("MGC", 10.0, 0.10, 1.0, 80.0),
    "NQ": Instrumento("MNQ", 2.0, 0.25, 1.0, 350.0),
    "ES": Instrumento("MES", 5.0, 0.25, 1.0, 70.0),
}
ATR_SD = 0.25


def coste_r(ins: Instrumento, sl_atr: float, tipo: int) -> float:
    """Coste de una operación en R con el ATR típico (para tablas). tipo: 1 tiempo, 2 SL, 3 TP."""
    sl_usd = sl_atr * ins.atr * ins.usd_punto
    ticks = 1 + (0 if tipo == 3 else 1)
    return (ins.comision_rt + ticks * ins.tick * ins.usd_punto) / sl_usd


@dataclass
class Pierna:
    """Una estrategia dentro de la cuenta: su biblioteca de días, el instrumento y el riesgo por operación."""
    bib: Biblioteca
    ins: Instrumento
    riesgo: float  # $ por operación objetivo (1 R)


def _dia(pierna: Pierna, rng, n: int, micros_cap):
    """Simula un día de una pierna para n cuentas. Devuelve (pnl $, mínimo intradía $, n ops, micros)."""
    b, ins = pierna.bib, pierna.ins
    d = rng.integers(0, b.r.shape[0], n)
    atr = ins.atr * np.exp(rng.normal(0, ATR_SD, n) - ATR_SD ** 2 / 2)
    sl_usd = b.sl * atr * ins.usd_punto                      # $ de riesgo por micro
    c = np.floor(pierna.riesgo / sl_usd)
    c = np.where((c == 0) & (sl_usd <= 1.5 * pierna.riesgo), 1, c)
    c = np.minimum(c, micros_cap)
    tipo = b.tipo[d]
    hay = tipo > 0
    r = np.where(hay, b.r[d], 0.0)
    ticks = np.where(tipo == 3, 1, 2) * hay
    coste = c[:, None] * (ins.comision_rt * hay + ticks * ins.tick * ins.usd_punto)
    escala = (c * sl_usd)[:, None]
    pnl = r * escala - coste
    acum_antes = np.cumsum(pnl, axis=1) - pnl
    bajo = acum_antes + np.where(hay, b.mae[d], 0.0) * escala - c[:, None] * ins.comision_rt * hay
    return pnl, np.minimum(bajo.min(axis=1), 0.0), hay.sum(axis=1), c


def _dia_cuenta(piernas, rng, n, micros_cap, dll, dist):
    """Suma las piernas de un día. Aplica el DLL (corta el día) y detecta la quema (MLL en tiempo real).
    Con varias piernas, el mínimo intradía es la suma de mínimos (cota conservadora)."""
    pnl_tot = np.zeros(n)
    bajo_tot = np.zeros(n)
    nops = np.zeros(n)
    for p in piernas:
        pnl, bajo, k, _ = _dia(p, rng, n, micros_cap)
        pnl_tot += pnl.sum(axis=1)
        bajo_tot += bajo
        nops += k
    quema = bajo_tot <= -dist
    if dll is not None:
        # si el DLL queda por encima del suelo, el DLL cierra el día antes de que se queme la cuenta
        dll_antes = dist > dll
        pnl_tot = np.where(dll_antes & (bajo_tot <= -dll), -dll, pnl_tot)
        quema &= ~dll_antes
    return pnl_tot, quema, nops


def combine(piernas, cuenta: Cuenta, rta: bool = True, n: int = 4000, max_dias: int = 126, seed: int = 1):
    rng = np.random.default_rng(seed)
    bal = np.zeros(n)
    suelo = np.full(n, -cuenta.mll)
    mejor = np.zeros(n)
    vivo = np.ones(n, bool)
    aprobado = np.zeros(n, bool)
    dias = np.zeros(n, int)
    dll = cuenta.dll if rta else None
    for _ in range(max_dias):
        act = vivo & ~aprobado
        if not act.any():
            break
        pnl, quema, _ = _dia_cuenta(piernas, rng, n, cuenta.micros_max, dll, bal - suelo)
        pnl = np.where(act, pnl, 0.0)
        quema &= act
        dias += act
        bal = np.where(quema, suelo, bal + pnl)
        vivo &= ~quema
        mejor = np.maximum(mejor, pnl)
        suelo = np.where(act & vivo, np.minimum(np.maximum(suelo, bal - cuenta.mll), 0.0), suelo)
        objetivo = np.maximum(cuenta.objetivo, mejor / 0.55)
        aprobado |= act & vivo & (bal >= objetivo)
    cuota = cuenta.cuota_rta if rta else cuenta.cuota
    coste = cuota * np.ceil(np.maximum(dias, 1) / DIAS_MES)
    return dict(
        p_aprueba=aprobado.mean(), p_quema=(~vivo).mean(), p_sin_acabar=(vivo & ~aprobado).mean(),
        dias_mediana=float(np.median(dias[aprobado])) if aprobado.any() else np.nan,
        p_aprueba_20d=(aprobado & (dias <= 20)).mean(),
        coste_medio=coste.mean(),
    )


def _micros_xfa(cuenta: Cuenta, bal):
    cap = np.full(bal.shape, cuenta.escalado_xfa[0][1], float)
    for umbral, m in cuenta.escalado_xfa:
        cap = np.where(bal >= umbral, m, cap)
    return cap


def xfa(piernas, cuenta: Cuenta, rta: bool = True, n: int = 4000, horizonte: int = 126,
        umbral_retiro: float = 0.0, seed: int = 2):
    """Cuenta financiada desde saldo 0. Retira en cuanto se cumplen las condiciones y el saldo ≥ umbral."""
    rng = np.random.default_rng(seed)
    bal = np.zeros(n)
    suelo = np.full(n, -cuenta.mll)
    vivo = np.ones(n, bool)
    primer = np.zeros(n, bool)
    cobrado = np.zeros(n)
    n_ret = np.zeros(n, int)
    dias_150 = np.zeros(n, int)
    dias_op = np.zeros(n, int)
    neto = np.zeros(n)
    mejor = np.zeros(n)
    dia_quema = np.full(n, horizonte)
    tope = cuenta.tope_retiro * (2 if rta else 1)
    dll = cuenta.dll if rta else None
    for dia in range(horizonte):
        if not vivo.any():
            break
        cap = _micros_xfa(cuenta, bal)
        pnl = np.zeros(n)
        quema = np.zeros(n, bool)
        nops = np.zeros(n)
        # el tope de contratos depende del saldo: se agrupa por tope
        for c in np.unique(cap[vivo]):
            m = vivo & (cap == c)
            p, q, k = _dia_cuenta(piernas, rng, n, c, dll, bal - suelo)
            pnl = np.where(m, p, pnl)
            quema = np.where(m, q, quema)
            nops = np.where(m, k, nops)
        pnl = np.where(vivo, pnl, 0.0)
        bal = np.where(quema, suelo, bal + pnl)
        dia_quema = np.where(quema & vivo, dia, dia_quema)
        vivo &= ~quema
        suelo = np.where(primer, 0.0, np.minimum(np.maximum(suelo, bal - cuenta.mll), 0.0))
        dias_150 += vivo & (pnl >= 150)
        dias_op += vivo & (nops > 0)
        neto += pnl
        mejor = np.maximum(mejor, pnl)
        ok = (dias_150 >= 5) | ((dias_op >= 3) & (neto > 0) & (mejor <= 0.4 * neto))
        ok &= vivo & (bal > 0) & (bal >= umbral_retiro)
        importe = np.where(ok, np.minimum(0.5 * bal, tope), 0.0)
        bal -= importe
        cobrado += 0.9 * importe
        n_ret += ok
        primer |= ok
        suelo = np.where(primer, 0.0, suelo)
        for arr in (dias_150, dias_op):
            arr[ok] = 0
        neto[ok] = 0.0
        mejor[ok] = 0.0
    return dict(
        cobro_medio=cobrado.mean(), retiros_medios=n_ret.mean(),
        p_1_retiro=(n_ret >= 1).mean(), p_3_retiros=(n_ret >= 3).mean(),
        p_viva_final=vivo.mean(), cobro_p50=float(np.median(cobrado)),
    )
