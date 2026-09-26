"""Tabla de candidatos del PDF «Candidatos_Agresivos_Fondeo» (in-sample 2025-03 → 2026-09, M5, CFD).

Cifras copiadas tal cual del informe: 1 R = 1.000 $ sobre una cuenta de 100.000 $.
`sl` es el stop en fracción del ATR diario y `k` el TP en fracción del SL (RR 1:k).
`t_sl_tp` son los % de operaciones cerradas por tiempo / stop / take profit.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

R_PDF = 1000.0  # $ por operación en el informe (1 % de 100k)


@dataclass(frozen=True)
class Candidato:
    id: str
    familia: str       # clave de familia (misma señal) -> ver FAMILIAS en modelo.py
    activo: str        # XAU, NQ, ES
    sl: float          # SL en ATR diario
    k: float           # TP / SL
    ops: int
    ops_dia: float
    wr: float          # % acierto (0-1)
    pf: float
    beneficio: float   # $ con 1 R = 1.000 $
    dd: float          # DD máx. en $ (positivo)
    meses_pos: float   # % meses positivos (0-1)
    p_t: float         # % salidas por tiempo (0-1)
    p_sl: float
    p_tp: float
    peor_dia: float    # R (negativo)

    # --- métricas derivadas -------------------------------------------------
    @property
    def ev_r(self) -> float:
        """Esperanza por operación en R (neta de los costes CFD del informe)."""
        return self.beneficio / self.ops / R_PDF

    @property
    def rf(self) -> float:
        return self.beneficio / self.dd

    @property
    def media_ganadora(self) -> float:
        gl = self.beneficio / (self.pf - 1) / R_PDF
        return self.pf * gl / (self.ops * self.wr)

    @property
    def media_perdedora(self) -> float:
        gl = self.beneficio / (self.pf - 1) / R_PDF
        return gl / (self.ops * (1 - self.wr))

    @property
    def t_stat(self) -> float:
        """t de la esperanza (aprox. con dos resultados). < 2 = ventaja no demostrada."""
        w, l, ev = self.media_ganadora, self.media_perdedora, self.ev_r
        sd = math.sqrt(self.wr * w * w + (1 - self.wr) * l * l - ev * ev)
        return ev * math.sqrt(self.ops) / sd

    @property
    def ev_dia(self) -> float:
        return self.ev_r * self.ops_dia


def _c(id, fam, act, sl, k, ops, opd, wr, pf, ben, dd, mp, t, s, tp, pd):
    return Candidato(id, fam, act, sl, k, ops, opd, wr / 100, pf, ben, dd, mp / 100,
                     t / 100, s / 100, tp / 100, pd)


# Páginas 2-4 del PDF. Familia = misma señal y filtros; solo cambian SL y RR.
CANDIDATOS = [
    _c("S01", "fvg_es", "ES", 0.30, 0.50, 747, 1.9, 65.6, 1.05, 9668, 16155, 63, 17, 24, 59, -3.1),
    _c("S02", "ts12_es", "ES", 0.35, 0.25, 690, 1.7, 75.7, 1.07, 8064, 7817, 53, 15, 12, 74, -2.1),
    _c("S04", "z_es", "ES", 0.20, 0.35, 650, 1.6, 72.6, 1.05, 6614, 11158, 53, 13, 17, 70, -2.5),
    _c("S05", "z_es", "ES", 0.30, 0.20, 642, 1.6, 78.8, 1.01, 687, 10274, 53, 14, 10, 77, -2.1),
    _c("N01", "fvg_nq", "NQ", 0.30, 0.50, 744, 1.9, 66.3, 1.12, 24866, 10912, 63, 18, 22, 61, -3.6),
    _c("N02", "ts12_nq", "NQ", 0.35, 0.25, 715, 1.8, 77.1, 1.15, 16339, 8061, 63, 15, 11, 74, -2.1),
    _c("N04", "ts12_nq", "NQ", 0.50, 0.15, 722, 1.8, 81.2, 1.13, 9419, 5696, 68, 15, 6, 79, -1.9),
    _c("Z01", "hora_xau", "XAU", 0.35, 0.50, 1066, 2.7, 64.9, 1.19, 49800, 11706, 79, 20, 20, 60, -3.1),
    _c("Z03", "ts12_xau", "XAU", 0.50, 0.50, 777, 1.9, 60.2, 1.15, 25216, 9443, 63, 38, 14, 47, -2.2),
    _c("Z05", "hora_xau", "XAU", 0.50, 0.25, 1217, 3.0, 73.7, 1.12, 23017, 7400, 74, 19, 11, 71, -2.6),
    _c("Z07", "ts24_xau", "XAU", 0.35, 0.50, 694, 1.7, 64.0, 1.13, 22535, 10534, 68, 27, 18, 54, -3.1),
    _c("Z08", "hora_xau", "XAU", 0.35, 0.25, 1739, 4.3, 77.4, 1.07, 19934, 12883, 63, 11, 13, 76, -2.6),
    _c("Z10", "ts24_xau", "XAU", 0.35, 0.25, 850, 2.1, 77.4, 1.14, 18925, 7408, 68, 13, 12, 76, -2.6),
    _c("Z12", "ts24_xau", "XAU", 0.50, 0.25, 727, 1.8, 72.6, 1.15, 15841, 9894, 74, 23, 9, 68, -2.0),
    _c("Z13", "ts24_xau", "XAU", 0.50, 0.15, 849, 2.1, 82.2, 1.19, 14927, 6819, 63, 13, 6, 81, -1.6),
    _c("Z16", "fvg03_xau", "XAU", 0.30, 0.25, 941, 2.3, 77.6, 1.02, 2967, 14815, 53, 9, 14, 77, -3.2),
    _c("Z17", "fvg01_xau", "XAU", 0.30, 0.25, 1725, 4.3, 76.3, 1.01, 2959, 13420, 47, 12, 14, 75, -3.2),
]

POR_ID = {c.id: c for c in CANDIDATOS}


def winrate_alto(umbral: float = 0.70) -> list[Candidato]:
    return [c for c in CANDIDATOS if c.wr > umbral]
