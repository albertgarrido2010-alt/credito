# credito · estrategias agresivas para fondeo de futuros (Topstep)

Análisis de las estrategias con acierto > 70 % del informe de candidatos: preselección, barrido de RR
(TP:SL), rachas y retorno esperado por reto en Topstep (Combine + cuenta financiada XFA).

- `INFORME.md`: resultados y conclusiones.
- `fondeo/candidatos.py`: tabla del PDF de candidatos y métricas derivadas (EV/op, t, media ganadora/perdedora).
- `fondeo/modelo.py`: modelo de barreras (SL/TP/cierre) calibrado con el PDF para mover el RR; rachas.
- `fondeo/topstep.py`: simulador Monte Carlo de Topstep (MLL arrastrado en tiempo real, DLL con RTA,
  consistencia 55 %, escalado XFA, retiros, costes en micros).
- `fondeo/backtest.py`: backtest con velas reales (Turtle Soup + SMA y Hora + SMA) para confirmar el barrido.

```bash
pip install numpy pandas scipy pytest
python3 -m pytest -q tests
python3 -m scripts.calibrar          # resultados/calibracion.json, validacion.csv
python3 -m scripts.barrido_rr        # resultados/barrido_rr.csv
python3 -m scripts.cartera           # resultados/cartera.csv
python3 -m scripts.tablas > resultados/tablas.md
```

Backtest con datos reales (necesita velas M1/M5 en CSV `time,open,high,low,close` en UTC, o acceso a
datafeed.dukascopy.com para `descargar_dukascopy`):

```bash
python3 -m scripts.backtest_real --csv datos/XAUUSD_M1.csv --familia ts24_xau --sl 0.5 --k 0.08 0.10 0.12 0.15 0.20 0.25
```
