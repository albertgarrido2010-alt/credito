# Estrategias con acierto > 70 %: preselección, barrido de RR y rachas para Topstep

Fecha: 26-09-2026 · Base: `Candidatos_Agresivos_Fondeo` (in-sample 2025-03 → 2026-09, CFD M5),
`Reglas_FTMO_Topstep` y capturas de topstep.com/topstep-prop (opción «No activation fee»).

## 1. Resumen

- **Bajar el RR sube el acierto, pero no mejora el resultado en ninguna familia.** Pasar de 1:0,25 a 1:0,10
  sube el acierto 12-15 puntos (hasta el 87-90 %), pero la esperanza por operación cae a la mitad o menos.
  El EV por reto en Topstep 50K baja entre un 40 % y un 80 %. Con 1:0,12 o menos y la mitad de la ventaja
  in-sample, la esperanza por operación queda en ≈ 0 (entre −0,005 y +0,003 R).
- **Lo que sí mejora es lo contrario en la familia de tendencia (Hora + SMA, oro): bajar el acierto.**
  Z05 pasa de 1:0,25 (74,8 % de acierto, +981 $/reto) a 1:0,50 (63,1 %, +1.571 $/reto).
- **Preseleccionadas** (7 de las 12 con acierto > 70 %, en 3 familias): Z10, Z12 y Z13 (Turtle Soup oro), N02 y
  N04 (Turtle Soup Nasdaq), Z05 y Z08 (Hora + SMA oro). **Descartadas:** S02, S04 y S05 (en futuros ES los
  costes se comen el 11-17 % del TP y la ventaja queda en 0 o negativa) y Z16 y Z17 (PF 1,01-1,02, sin ventaja).
- **Mejor RR por familia:** Turtle Soup oro 1:0,25 con SL 0,35 ATR (**Z10** tal cual); Nasdaq 1:0,25-0,35 con
  SL 0,35 (**N02** o algo más de TP); Hora oro **1:0,35-0,50 con SL 0,50**.
- **Cartera en Topstep 50K** (las tres familias a la vez, RTA ON), EV por reto con la mitad de la ventaja
  in-sample:

| Cartera | EV por reto | Aprueba |
|---|---|---|
| RR bajado (acierto 85-88 %) | +158 $ | 30 % |
| RR original (Z13 + Z05 + N02) | +368 $ | 37 % |
| **RR optimizado** (Z10 + Hora SL 0,50 · 1:0,50 + Nasdaq SL 0,35 · 1:0,35) | **+563 $** | **43 %** |

Con la cartera optimizada: mediana de 26 días hábiles para aprobar y ~1.600 $ cobrados en 6 meses por
cuenta aprobada.

- **Rachas** (muestra de 18 meses, estrategias del PDF): 2-3 stops seguidos (3-5 en el peor 5 %), 3-5
  pérdidas seguidas (5-7) y 15-25 TPs seguidos (21-38). Con RR 1:0,10: 1-2 stops seguidos (2-3) y 32-51 TPs
  seguidos. Tablas en los apartados 4 y 5.
- **Aviso importante:** ninguna de las 12 tiene una ventaja estadísticamente demostrada (t ≤ 2,0, optimizadas
  en el mismo periodo). Sin ventaja real, el EV por reto queda en ≈ 0 o negativo con cualquier RR. Antes de
  pagar retos hay que hacer el backtest con velas reales (apartado 7), que no he podido descargar desde este
  entorno.

## 2. Método

1. **Datos.** No hay velas: la red de este entorno solo deja salir a GitHub y PyPI (datafeed.dukascopy.com,
   Yahoo, Stooq, histdata… bloqueados). Todo se ha hecho con las cifras de tu PDF.
2. **Modelo calibrado con tu PDF** (`fondeo/modelo.py`). Tras la entrada, el precio (en ATR) es un paseo
   aleatorio con deriva: un rebote inicial que se apaga (reversión) más una deriva persistente (tendencia). La
   operación sale por SL, TP, tiempo o cierre de las 15:55 NY, con monitorización continua (como una vela M5) y
   una operación a la vez. Cada familia (misma señal, distinto SL/RR) se calibra con sus estrategias del PDF:
   salidas T/SL/TP, esperanza y operaciones al día.
3. **Validación dejando una fuera.** Se calibra sin una estrategia y se predice esa:

   | Estrategia predicha | Acierto modelo / PDF | T/SL/TP modelo | T/SL/TP PDF |
   |---|---|---|---|
   | Z07 (1:0,50, desde Z10/Z12/Z13) | 65,3 % / 64,0 % | 27/17/56 | 27/18/54 |
   | Z10 (1:0,25) | 79,1 % / 77,4 % | 12/10/77 | 13/12/76 |
   | Z12 (1:0,25) | 74,3 % / 72,6 % | 23/7/70 | 23/9/68 |
   | Z13 (1:0,15) | 83,6 % / 82,2 % | 13/5/82 | 13/6/81 |
   | Z01 (1:0,50, desde Z05/Z08) | 65,2 % / 64,9 % | 20/22/59 | 20/20/60 |
   | Z05 (1:0,25) | 73,9 % / 73,7 % | 19/10/71 | 19/11/71 |
   | Z08 (1:0,25) | 77,7 % / 77,4 % | 10/14/76 | 11/13/76 |

   El modelo acierta el cambio de RR entre 1:0,15 y 1:0,50 con 0-2 puntos de error. Por debajo de 1:0,15 es
   extrapolación.
4. **Futuros Topstep** (`fondeo/topstep.py`): micros (MGC, MNQ, MES), 1 $ de comisión ida y vuelta, 1 tick de
   deslizamiento en entrada, stop y salida a mercado. El TP (límite) exige que el precio lo pase 1 tick.
   Contratos enteros según el ATR del día.
5. **Topstep Monte Carlo:** Combine (MLL arrastrado al cierre y comprobado en tiempo real con flotante,
   consistencia 55 %, DLL con RTA ON) y cuenta financiada XFA durante 6 meses (suelo en 0 tras el primer retiro,
   retiros de 5 días ≥ 150 $ o 3 días con el mejor ≤ 40 %, 50 % del saldo con tope doble por RTA, reparto 90 %).
   **EV por reto** = P(aprobar) × cobro medio en la XFA − coste del reto (cuota × meses). Se prueba cada RR con
   su mejor riesgo por operación.
6. **Tres escenarios de ventaja:** in-sample (la del PDF), la mitad y sin ventaja. El in-sample casi seguro es
   optimista; el escenario «mitad» es el más realista para decidir.

## 3. Preselección de las 12 con acierto > 70 %

| ID | Activo | RR | Acierto | PF | EV/op (R) | t | RF | Meses + | Coste futuros / TP | EV/op futuros (R) | Veredicto |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Z10 | Oro | 1:0,25 | 77,4 % | 1,14 | +0,022 | 1,7 | 2,6 | 68 % | 4 % | +0,029 | **Sí** (la mejor de su familia) |
| Z13 | Oro | 1:0,15 | 82,2 % | 1,19 | +0,018 | 2,0 | 2,2 | 63 % | 5 % | +0,022 | **Sí** |
| Z12 | Oro | 1:0,25 | 72,6 % | 1,15 | +0,022 | 1,7 | 1,6 | 74 % | 3 % | +0,026 | **Sí** (misma familia) |
| Z05 | Oro | 1:0,25 | 73,7 % | 1,12 | +0,019 | 1,8 | 3,1 | 74 % | 3 % | +0,023 | **Sí** |
| Z08 | Oro | 1:0,25 | 77,4 % | 1,07 | +0,011 | 1,2 | 1,5 | 63 % | 4 % | +0,018 | Sí, pero peor que Z05/Z01 |
| N02 | Nasdaq | 1:0,25 | 77,1 % | 1,15 | +0,023 | 1,6 | 2,0 | 63 % | 3 % | +0,032 | **Sí** |
| N04 | Nasdaq | 1:0,15 | 81,2 % | 1,13 | +0,013 | 1,3 | 1,7 | 68 % | 4 % | +0,019 | Sí (misma familia que N02) |
| S02 | S&P | 1:0,25 | 75,7 % | 1,07 | +0,012 | 0,8 | 1,0 | 53 % | 11 % | +0,000 | No: costes ES |
| S04 | S&P | 1:0,35 | 72,6 % | 1,05 | +0,010 | 0,6 | 0,6 | 53 % | 14 % | −0,010 | No |
| S05 | S&P | 1:0,20 | 78,8 % | 1,01 | +0,001 | 0,1 | 0,1 | 53 % | 17 % | −0,012 | No |
| Z16 | Oro | 1:0,25 | 77,6 % | 1,02 | +0,003 | 0,3 | 0,2 | 53 % | 5 % | +0,011 | No: sin ventaja |
| Z17 | Oro | 1:0,25 | 76,3 % | 1,01 | +0,002 | 0,2 | 0,2 | 47 % | 5 % | +0,009 | No: sin ventaja |

- EV/op = beneficio ÷ operaciones ÷ 1.000 $. t = esperanza ÷ error estándar: con t < 2 no se puede
  distinguir de la suerte, y menos después de optimizar en el mismo periodo.
- «EV/op futuros» sustituye el coste CFD que implica el PDF (~0,006 ATR por operación) por el de los micros
  de Topstep. En oro y Nasdaq los micros salen más baratos que el CFD; en el S&P, más caros.
- Z10/Z12/Z13 son **la misma estrategia** (Turtle Soup N24 + SMA200 en oro) con distinto SL y RR, igual que
  N02/N04 y Z05/Z08 (con Z01). Por eso el barrido se hace por familia: Z13 ya es «Z12 con el RR bajado».

## 4. Rachas de stops y de TPs (estrategias del PDF)

Rachas más largas en una muestra del tamaño del PDF (18 meses): mediana y, entre paréntesis, el peor 5 %.
«Pérdidas» incluye las salidas por tiempo en negativo; «ganadoras», las salidas por tiempo en positivo.

| ID | RR | Ops | Acierto | % SL | Stops seguidos | Pérdidas seguidas | TPs seguidos | Ganadoras seguidas | Peor día (PDF) |
|---|---|---|---|---|---|---|---|---|---|
| Z13 | 1:0,15 | 849 | 82,2 % | 6 % | 2 (3) | 3 (5) | 25 (38) | 27 (40) | −1,6 R |
| N04 | 1:0,15 | 722 | 81,2 % | 6 % | 2 (3) | 4 (5) | 22 (33) | 25 (37) | −1,9 R |
| S05 | 1:0,20 | 642 | 78,8 % | 10 % | 2 (4) | 4 (5) | 20 (30) | 21 (33) | −2,1 R |
| Z16 | 1:0,25 | 941 | 77,6 % | 14 % | 3 (4) | 4 (6) | 21 (31) | 22 (32) | −3,2 R |
| Z10 | 1:0,25 | 850 | 77,4 % | 12 % | 3 (4) | 4 (6) | 20 (30) | 21 (31) | −2,6 R |
| Z08 | 1:0,25 | 1.739 | 77,4 % | 13 % | 3 (5) | 5 (6) | 23 (33) | 24 (34) | −2,6 R |
| N02 | 1:0,25 | 715 | 77,1 % | 11 % | 3 (4) | 4 (6) | 18 (26) | 20 (30) | −2,1 R |
| Z17 | 1:0,25 | 1.725 | 76,3 % | 14 % | 3 (5) | 5 (7) | 22 (31) | 23 (33) | −3,2 R |
| S02 | 1:0,25 | 690 | 75,7 % | 12 % | 3 (4) | 4 (6) | 18 (26) | 19 (28) | −2,1 R |
| Z05 | 1:0,25 | 1.217 | 73,7 % | 11 % | 3 (4) | 5 (7) | 18 (25) | 20 (28) | −2,6 R |
| Z12 | 1:0,25 | 727 | 72,6 % | 9 % | 2 (4) | 5 (7) | 15 (21) | 17 (25) | −2,0 R |
| S04 | 1:0,35 | 650 | 72,6 % | 17 % | 3 (5) | 5 (6) | 15 (22) | 17 (24) | −2,5 R |

Cómo se calcula: con las proporciones exactas del PDF (TP, SL, tiempo +/−) en 2.000 muestras de ese mismo
número de operaciones, suponiendo operaciones independientes. El PDF no trae la secuencia real de
operaciones. Las rachas del barrido (apartado 5) salen del modelo, que respeta el orden dentro del día.

Qué significa para Topstep 50K (MLL 2.000 $): con 500 $ por operación, el peor 5 % de rachas de stops
(3-5 × 500 $ = 1.500-2.500 $) ya toca el MLL. Con una sola estrategia compensa arriesgarlo (el reto solo cuesta
la cuota), pero en cartera varias rachas pueden coincidir y el óptimo baja a 300-400 $ por operación y
estrategia (apartado 6).

## 5. Barrido de RR (TP:SL)

Por familia y SL: el RR del PDF está marcado con su ID. EV/reto = Topstep 50K, RTA ON, mejor riesgo por
operación. Rachas: mediana / peor 5 % en 18 meses. Días perdedores seguidos: peor 5 %.

### Resumen: RR original frente a RR bajado y al mejor RR

Acierto y EV/op salen del modelo con costes de futuros; por eso difieren un poco de los del PDF.

| ID | RR original · acierto · EV/op · EV/reto (in-sample / mitad) | RR 1:0,10 · acierto · EV/op · EV/reto | Mejor RR · acierto · EV/op · EV/reto |
|---|---|---|---|
| Z10 | 1:0,25 · 77,5 % · +0,029 · +705 / +164 $ | 90,2 % · +0,013 · +286 / +53 $ | **1:0,25** (se queda) |
| Z12 | 1:0,25 · 71,7 % · +0,022 · +383 / +140 $ | 86,9 % · +0,011 · +225 / +31 $ | 1:0,20-0,50, casi plano (1:0,25 vale) |
| Z13 | 1:0,15 · 81,2 % · +0,017 · +356 / +84 $ | 86,9 % · +0,011 · +225 / +31 $ | 1:0,20-0,25 (subir el RR) |
| N02 | 1:0,25 · 76,0 % · +0,031 · +684 / +153 $ | 89,5 % · +0,015 · +301 / +69 $ | 1:0,25-0,35 · 69-76 % |
| N04 | 1:0,15 · 79,5 % · +0,019 · +312 / +73 $ | 85,9 % · +0,014 · +240 / +47 $ | 1:0,20-0,50 · 57-74 % |
| Z05 | 1:0,25 · 74,8 % · +0,027 · +981 / +247 $ | 87,7 % · +0,007 · +292 / +89 $ | **1:0,50 · 63,1 % · +0,055 · +1.571 / +321 $** |
| Z08 | 1:0,25 · 78,3 % · +0,020 · +657 / +138 $ | 90,0 % · +0,003 · +142 / +14 $ | 1:0,50 = Z01 · 65,5 % · +1.145 / +274 $ |

**Por qué bajar el RR no ayuda:** con un TP más corto aciertas más, pero cada acierto vale menos y el
stop sigue igual de lejos. La ventaja de estas señales está en los primeros movimientos (Turtle Soup) o en la
tendencia (Hora + SMA); cortar el TP deja parte de esa ventaja sin cobrar, y la comisión y el tick del TP pesan
más cuanto más pequeño es el TP. Con 1:0,08 los costes ya son el 9-13 % del TP en oro y Nasdaq. En Topstep además hace falta
llegar al objetivo: con menos esperanza por día se tarda más, se pagan más meses y hay más días para que el
MLL arrastrado te pille.

**Por qué en Hora + SMA conviene subirlo:** la calibración de esa familia sale sin rebote y con deriva
persistente a favor (tendencia). Cuanto más lejos el TP, más tendencia se cobra. Es lo mismo que ya decía tu
PDF: Z01 (1:0,50) gana 2,5 veces más que Z08 (1:0,25) con la misma señal. Ojo: es una estrategia solo de
compras en oro durante una subida histórica del oro; parte de la ventaja puede ser simplemente ir largo en
oro.

Leyenda: EV/op en R neto de costes de futuros · Benef./DD = beneficio y drawdown máximo en R en 18 meses (1 R = riesgo por operación) · Stops/Pérd./TPs seg. = rachas más largas (mediana / peor 5 %) · Aprueba y Días = Combine 50K con el riesgo que maximiza el EV in-sample.

### Turtle Soup N24 + SMA200 · oro · SL 0,35 ATR

| RR | Acierto | % SL | EV/op (R) | Ops/día | Benef. / DD 18 m (R) | Stops seg. (med/p95) | Pérd. seg. (med/p95) | TPs seg. (med/p95) | Días perd. seg. p95 | Aprueba 50K | Días | EV/reto $ in-sample | EV/reto $ mitad | EV/reto $ sin ventaja |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1:0,08 | 92,1 % | 4,3 % | +0,009 | 2,5 | +9 / 6 | 2 / 3 | 2 / 3 | 57 / 88 | 5 | 36,1 % | 23 | +174 | -5 | -69 |
| 1:0,10 | 90,2 % | 5,2 % | +0,013 | 2,4 | +12 / 6 | 2 / 3 | 3 / 4 | 47 / 71 | 5 | 37,0 % | 18 | +286 | +53 | -41 |
| 1:0,12 | 88,3 % | 6,1 % | +0,016 | 2,3 | +15 / 6 | 2 / 3 | 3 / 4 | 39 / 58 | 6 | 37,3 % | 15 | +360 | +60 | -41 |
| 1:0,15 | 85,5 % | 7,4 % | +0,020 | 2,2 | +18 / 7 | 2 / 3 | 3 / 4 | 32 / 47 | 6 | 50,4 % | 49 | +499 | +77 | -24 |
| 1:0,20 | 81,2 % | 9,8 % | +0,022 | 2,1 | +19 / 8 | 3 / 4 | 4 / 5 | 23 / 35 | 8 | 47,4 % | 40 | +528 | +139 | +1 |
| 1:0,25 (Z10) | 77,5 % | 11,3 % | +0,029 | 2,0 | +24 / 8 | 3 / 4 | 4 / 6 | 19 / 30 | 8 | 51,1 % | 34 | +705 | +164 | -2 |
| 1:0,35 | 70,7 % | 14,3 % | +0,035 | 1,8 | +25 / 9 | 3 / 4 | 5 / 7 | 13 / 20 | 8 | 47,2 % | 29 | +681 | +144 | +12 |
| 1:0,50 (Z07) | 63,4 % | 17,8 % | +0,038 | 1,6 | +25 / 10 | 3 / 5 | 6 / 9 | 9 / 13 | 10 | 43,9 % | 24 | +605 | +163 | +26 |

### Turtle Soup N24 + SMA200 · oro · SL 0,50 ATR

| RR | Acierto | % SL | EV/op (R) | Ops/día | Benef. / DD 18 m (R) | Stops seg. (med/p95) | Pérd. seg. (med/p95) | TPs seg. (med/p95) | Días perd. seg. p95 | Aprueba 50K | Días | EV/reto $ in-sample | EV/reto $ mitad | EV/reto $ sin ventaja |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1:0,08 | 89,6 % | 2,8 % | +0,011 | 2,3 | +11 / 5 | 2 / 2 | 2 / 4 | 44 / 61 | 5 | 41,3 % | 25 | +236 | +1 | -69 |
| 1:0,10 | 86,9 % | 3,7 % | +0,011 | 2,2 | +10 / 5 | 2 / 3 | 3 / 4 | 34 / 49 | 6 | 38,5 % | 22 | +225 | +31 | -49 |
| 1:0,12 | 84,8 % | 4,2 % | +0,015 | 2,1 | +13 / 6 | 2 / 3 | 3 / 4 | 30 / 45 | 6 | 40,2 % | 18 | +324 | +64 | -34 |
| 1:0,15 (Z13) | 81,2 % | 5,1 % | +0,017 | 2,0 | +13 / 7 | 2 / 3 | 3 / 5 | 23 / 35 | 7 | 38,9 % | 16 | +356 | +84 | -40 |
| 1:0,20 | 76,5 % | 6,3 % | +0,024 | 1,9 | +18 / 7 | 2 / 3 | 4 / 6 | 17 / 25 | 7 | 44,8 % | 30 | +504 | +102 | -9 |
| 1:0,25 (Z12) | 71,7 % | 7,5 % | +0,022 | 1,7 | +15 / 8 | 2 / 3 | 5 / 6 | 13 / 20 | 9 | 37,0 % | 12 | +383 | +140 | +15 |
| 1:0,35 | 65,0 % | 9,3 % | +0,025 | 1,5 | +15 / 8 | 2 / 3 | 6 / 8 | 9 / 13 | 8 | 37,2 % | 11 | +379 | +116 | +50 |
| 1:0,50 | 58,7 % | 11,1 % | +0,028 | 1,3 | +15 / 9 | 2 / 3 | 6 / 9 | 6 / 9 | 10 | 33,6 % | 10 | +336 | +153 | +36 |

### Turtle Soup N12 + SMA200 · Nasdaq · SL 0,35 ATR

| RR | Acierto | % SL | EV/op (R) | Ops/día | Benef. / DD 18 m (R) | Stops seg. (med/p95) | Pérd. seg. (med/p95) | TPs seg. (med/p95) | Días perd. seg. p95 | Aprueba 50K | Días | EV/reto $ in-sample | EV/reto $ mitad | EV/reto $ sin ventaja |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1:0,08 | 91,7 % | 3,6 % | +0,011 | 2,1 | +10 / 5 | 2 / 2 | 2 / 3 | 50 / 78 | 5 | 39,0 % | 24 | +220 | +8 | -72 |
| 1:0,10 | 89,5 % | 4,5 % | +0,015 | 2,1 | +12 / 5 | 2 / 3 | 2 / 3 | 43 / 66 | 5 | 39,6 % | 20 | +301 | +69 | -41 |
| 1:0,12 | 87,5 % | 5,3 % | +0,018 | 2,0 | +14 / 6 | 2 / 3 | 3 / 4 | 36 / 55 | 6 | 45,1 % | 34 | +403 | +42 | -30 |
| 1:0,15 | 84,6 % | 6,4 % | +0,021 | 1,9 | +16 / 6 | 2 / 3 | 3 / 4 | 28 / 43 | 6 | 44,5 % | 29 | +505 | +161 | -8 |
| 1:0,20 | 80,0 % | 8,0 % | +0,027 | 1,8 | +19 / 7 | 2 / 3 | 4 / 5 | 22 / 33 | 7 | 53,3 % | 46 | +643 | +154 | +6 |
| 1:0,25 (N02) | 76,0 % | 9,6 % | +0,031 | 1,7 | +22 / 7 | 2 / 3 | 4 / 6 | 18 / 26 | 8 | 51,7 % | 41 | +684 | +153 | +10 |
| 1:0,35 | 69,0 % | 12,4 % | +0,033 | 1,5 | +21 / 9 | 3 / 4 | 5 / 7 | 12 / 17 | 8 | 47,6 % | 34 | +580 | +204 | +42 |
| 1:0,50 | 61,5 % | 14,7 % | +0,038 | 1,4 | +21 / 9 | 3 / 4 | 6 / 9 | 8 / 12 | 10 | 43,6 % | 30 | +482 | +179 | +22 |

### Turtle Soup N12 + SMA200 · Nasdaq · SL 0,50 ATR

| RR | Acierto | % SL | EV/op (R) | Ops/día | Benef. / DD 18 m (R) | Stops seg. (med/p95) | Pérd. seg. (med/p95) | TPs seg. (med/p95) | Días perd. seg. p95 | Aprueba 50K | Días | EV/reto $ in-sample | EV/reto $ mitad | EV/reto $ sin ventaja |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1:0,08 | 88,5 % | 2,2 % | +0,011 | 2,0 | +8 / 5 | 1 / 2 | 3 / 4 | 38 / 58 | 5 | 40,8 % | 30 | +179 | +7 | -88 |
| 1:0,10 | 85,9 % | 2,7 % | +0,014 | 1,9 | +10 / 5 | 1 / 2 | 3 / 4 | 32 / 44 | 6 | 40,9 % | 25 | +240 | +47 | -61 |
| 1:0,12 | 83,4 % | 3,1 % | +0,017 | 1,8 | +12 / 5 | 2 / 2 | 3 / 5 | 26 / 39 | 6 | 41,6 % | 22 | +286 | +53 | -49 |
| 1:0,15 (N04) | 79,5 % | 3,7 % | +0,019 | 1,7 | +13 / 5 | 2 / 2 | 4 / 5 | 21 / 31 | 7 | 42,5 % | 20 | +312 | +73 | -19 |
| 1:0,20 | 74,1 % | 4,6 % | +0,024 | 1,6 | +15 / 6 | 2 / 3 | 4 / 7 | 15 / 22 | 8 | 47,0 % | 35 | +412 | +108 | -29 |
| 1:0,25 | 69,3 % | 5,3 % | +0,024 | 1,5 | +14 / 6 | 2 / 3 | 5 / 7 | 12 / 17 | 9 | 39,1 % | 15 | +358 | +111 | +2 |
| 1:0,35 | 62,5 % | 6,7 % | +0,024 | 1,3 | +12 / 7 | 2 / 3 | 6 / 8 | 8 / 12 | 10 | 35,9 % | 12 | +313 | +101 | +7 |
| 1:0,50 | 57,0 % | 7,5 % | +0,028 | 1,2 | +13 / 8 | 2 / 3 | 7 / 10 | 5 / 8 | 10 | 39,0 % | 24 | +287 | +171 | +4 |

### Hora + SMA200 alcistas · oro · SL 0,35 ATR

| RR | Acierto | % SL | EV/op (R) | Ops/día | Benef. / DD 18 m (R) | Stops seg. (med/p95) | Pérd. seg. (med/p95) | TPs seg. (med/p95) | Días perd. seg. p95 | Aprueba 50K | Días | EV/reto $ in-sample | EV/reto $ mitad | EV/reto $ sin ventaja |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1:0,08 | 91,7 % | 5,5 % | -0,000 | 5,7 | -1 / 14 | 2 / 3 | 3 / 4 | 62 / 94 | 8 | 24,4 % | 10 | +61 | -6 | -42 |
| 1:0,10 | 90,0 % | 6,5 % | +0,003 | 5,4 | +7 / 12 | 2 / 3 | 3 / 4 | 51 / 73 | 9 | 28,5 % | 15 | +142 | +14 | -40 |
| 1:0,12 | 88,0 % | 7,6 % | +0,004 | 5,1 | +9 / 13 | 3 / 4 | 3 / 4 | 44 / 66 | 9 | 29,5 % | 14 | +166 | +37 | -31 |
| 1:0,15 | 85,7 % | 9,2 % | +0,008 | 4,8 | +16 / 12 | 3 / 4 | 3 / 5 | 37 / 52 | 9 | 36,4 % | 12 | +337 | +94 | -10 |
| 1:0,20 | 81,8 % | 11,6 % | +0,014 | 4,3 | +24 / 12 | 3 / 4 | 4 / 5 | 29 / 41 | 10 | 38,5 % | 21 | +459 | +99 | +10 |
| 1:0,25 (Z08) | 78,3 % | 13,7 % | +0,020 | 3,9 | +31 / 12 | 3 / 5 | 4 / 6 | 24 / 32 | 10 | 47,4 % | 37 | +657 | +138 | -8 |
| 1:0,35 | 72,7 % | 16,8 % | +0,034 | 3,4 | +46 / 11 | 4 / 5 | 5 / 7 | 17 / 25 | 9 | 61,1 % | 52 | +1256 | +202 | +23 |
| 1:0,50 (Z01) | 65,5 % | 21,1 % | +0,042 | 2,8 | +47 / 13 | 4 / 6 | 6 / 8 | 11 / 15 | 10 | 55,6 % | 44 | +1145 | +274 | +22 |

### Hora + SMA200 alcistas · oro · SL 0,50 ATR

| RR | Acierto | % SL | EV/op (R) | Ops/día | Benef. / DD 18 m (R) | Stops seg. (med/p95) | Pérd. seg. (med/p95) | TPs seg. (med/p95) | Días perd. seg. p95 | Aprueba 50K | Días | EV/reto $ in-sample | EV/reto $ mitad | EV/reto $ sin ventaja |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1:0,08 | 90,1 % | 3,8 % | +0,005 | 4,9 | +11 / 8 | 2 / 3 | 3 / 4 | 50 / 73 | 7 | 31,4 % | 13 | +216 | +43 | -37 |
| 1:0,10 | 87,7 % | 4,7 % | +0,007 | 4,5 | +13 / 9 | 2 / 3 | 3 / 4 | 40 / 58 | 8 | 36,2 % | 22 | +292 | +89 | -16 |
| 1:0,12 | 85,8 % | 5,5 % | +0,011 | 4,2 | +18 / 9 | 2 / 3 | 3 / 4 | 35 / 49 | 8 | 45,5 % | 43 | +448 | +119 | -16 |
| 1:0,15 | 82,9 % | 6,6 % | +0,014 | 3,8 | +22 / 9 | 2 / 4 | 4 / 5 | 29 / 43 | 9 | 46,5 % | 39 | +569 | +160 | +14 |
| 1:0,20 | 78,6 % | 8,0 % | +0,022 | 3,3 | +30 / 9 | 3 / 4 | 4 / 6 | 22 / 31 | 9 | 56,8 % | 47 | +883 | +221 | +5 |
| 1:0,25 (Z05) | 74,8 % | 9,4 % | +0,027 | 3,0 | +32 / 9 | 3 / 4 | 5 / 6 | 17 / 23 | 9 | 56,1 % | 44 | +981 | +247 | +29 |
| 1:0,35 | 68,6 % | 11,7 % | +0,037 | 2,5 | +37 / 9 | 3 / 4 | 5 / 8 | 12 / 17 | 9 | 58,1 % | 39 | +1219 | +323 | +45 |
| 1:0,50 | 63,1 % | 14,0 % | +0,055 | 2,0 | +45 / 9 | 3 / 4 | 6 / 8 | 8 / 12 | 9 | 61,5 % | 36 | +1571 | +321 | +40 |

### Turtle Soup N12 + SMA200 · S&P · SL 0,35 ATR

| RR | Acierto | % SL | EV/op (R) | Ops/día | Benef. / DD 18 m (R) | Stops seg. (med/p95) | Pérd. seg. (med/p95) | TPs seg. (med/p95) | Días perd. seg. p95 | Aprueba 50K | Días | EV/reto $ in-sample | EV/reto $ mitad | EV/reto $ sin ventaja |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1:0,08 | 90,1 % | 4,7 % | -0,015 | 2,0 | -12 / 15 | 2 / 3 | 2 / 3 | 44 / 67 | 5 | 12,0 % | 28 | -95 | -101 | -100 |
| 1:0,10 | 88,0 % | 5,6 % | -0,014 | 2,0 | -11 / 15 | 2 / 3 | 3 / 4 | 36 / 56 | 5 | 14,5 % | 21 | -68 | -87 | -92 |
| 1:0,12 | 86,1 % | 6,3 % | -0,010 | 1,9 | -8 / 14 | 2 / 3 | 3 / 4 | 32 / 50 | 6 | 17,5 % | 18 | -41 | -67 | -80 |
| 1:0,15 | 82,9 % | 7,7 % | -0,009 | 1,9 | -7 / 13 | 2 / 4 | 3 / 5 | 27 / 41 | 6 | 21,2 % | 15 | -12 | -40 | -73 |
| 1:0,20 | 78,4 % | 9,4 % | -0,005 | 1,8 | -4 / 13 | 2 / 4 | 4 / 5 | 20 / 30 | 8 | 22,3 % | 13 | +25 | -22 | -50 |
| 1:0,25 (S02) | 74,5 % | 10,8 % | +0,002 | 1,7 | +1 / 12 | 3 / 4 | 4 / 6 | 16 / 24 | 8 | 27,3 % | 10 | +115 | +3 | -40 |
| 1:0,35 | 67,5 % | 13,3 % | +0,003 | 1,5 | +2 / 13 | 3 / 4 | 5 / 7 | 12 / 18 | 9 | 27,7 % | 9 | +113 | +28 | -4 |
| 1:0,50 | 59,7 % | 16,3 % | +0,001 | 1,4 | +1 / 15 | 3 / 4 | 6 / 9 | 8 / 11 | 10 | 25,4 % | 8 | +94 | +19 | -0 |

## 6. Topstep: cartera de las tres familias

Una estrategia por familia en la misma cuenta (oro Turtle Soup + oro Hora + Nasdaq Turtle Soup, 5-8
operaciones al día). Una sola estrategia tarda 1-2 meses de mediana en aprobar el Combine; en cartera, bastante
menos. Se comparan tres versiones: el RR original del PDF (Z13 + Z05 + N02), el RR bajado (acierto 85-88 %) y el
RR elegido en el barrido (Z10 + Hora 1:0,50 con SL 0,5 + Nasdaq 1:0,35).

| Ventaja | Cartera | Riesgo/op Combine | Aprueba | Días (med.) | Aprueba ≤ 20 d | Coste/reto | XFA: riesgo · retiro desde | Cobro XFA 6 m | Retiros | ≥ 1 retiro | **EV/reto 50K** | ROI | EV/reto 100K |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| in-sample | RR bajado (acierto 85-88 %) | 400 $ | 70 % | 39 | 8 % | 200 $ | 400 $ · 3000 $ | 3135 $ | 2,2 | 69 % | **+1983 $** | +9,9 | +2478 $ |
| in-sample | RR original (Z13 + Z05 + N02) | 300 $ | 70 % | 42 | 6 % | 217 $ | 400 $ · 3000 $ | 3594 $ | 2,5 | 65 % | **+2281 $** | +10,5 | +3542 $ |
| in-sample | RR optimizado | 300 $ | 69 % | 33 | 14 % | 177 $ | 400 $ · 3000 $ | 3930 $ | 2,6 | 64 % | **+2553 $** | +14,4 | +4195 $ |
| mitad | RR bajado (acierto 85-88 %) | 700 $ | 30 % | 23 | 13 % | 121 $ | 400 $ · 2000 $ | 924 $ | 0,9 | 44 % | **+158 $** | +1,3 | +137 $ |
| mitad | RR original (Z13 + Z05 + N02) | 500 $ | 37 % | 27 | 12 % | 137 $ | 400 $ · 3000 $ | 1363 $ | 0,9 | 40 % | **+368 $** | +2,7 | +424 $ |
| mitad | RR optimizado | 400 $ | 43 % | 26 | 14 % | 142 $ | 400 $ · 3000 $ | 1640 $ | 1,1 | 43 % | **+563 $** | +4,0 | +736 $ |
| sin ventaja | RR bajado (acierto 85-88 %) | 700 $ | 12 % | 23 | 5 % | 112 $ | 400 $ · 1000 $ | 349 $ | 0,6 | 41 % | **-69 $** | -0,6 | -130 $ |
| sin ventaja | RR original (Z13 + Z05 + N02) | 700 $ | 19 % | 16 | 13 % | 99 $ | 400 $ · 2000 $ | 491 $ | 0,5 | 28 % | **-6 $** | -0,1 | -57 $ |
| sin ventaja | RR optimizado | 700 $ | 19 % | 12 | 16 % | 91 $ | 400 $ · 2000 $ | 542 $ | 0,5 | 30 % | **+13 $** | +0,1 | -23 $ |

RTA ON, riesgo por operación y estrategia. RTA OFF da casi lo mismo (el DLL casi nunca salta con estos riesgos) pero cuesta 10 $ más al mes, así que RTA ON sale algo mejor. 100K da más dólares por reto pero menos ROI: con el mismo dinero rinden más varias 50K.

## 7. Tu Turtle Soup (TSM): reproducción y barrido real de RR

Backtest **real**, no modelo: tus reglas tal cual sobre tus velas USTEC M5 (06-10-2025 → 18-09-2026), SL 450 ticks
= 112,5 puntos, 100 € por operación, sin costes (`scripts/turtle_soup_usuario.py`).

- **Reproduce tu informe** tomando la hora de tus datos como **UTC+2 fija**: B da 214 operaciones, 59,81 % de acierto,
  +4.106 € y DD −608 € (tu informe: 219, 59,82 %, +4.209 €, −600 €); Combinado +3.655 € (+3.939 €), Alcistas +3.003 €
  (+2.924 €), Bajistas +1.054 € (+969 €). La diferencia que queda es de fuente de datos (USTEC frente a MNQ).
- **Ojo con la hora:** con UTC+2 fija, tu ventana de 15:30-15:55 es la apertura de Nueva York en verano, pero las
  **08:30 de Nueva York en invierno** (hora de datos macro, antes de la apertura). Las dos partes ganan (verano +2.492 €,
  invierno +1.613 €).
- **Anclada siempre a la apertura de NY** (09:30-09:55 NY, cierre 14:00 NY; lo que hace el EA): B da 53,0 % de acierto,
  **+13,3 %** y DD −1.662 €. Mucho peor que tu versión: buena parte del resultado de tu informe viene de las entradas de
  las 08:30 de NY en invierno.
- **Bajar el RR** sube el acierto pero baja el PnL, igual que en las demás estrategias:

| RR | Acierto | PnL (1 R = 1 %) | DD máx. | PF | Stops / TPs seguidos (máx.) | EV/reto 50K (in-s. / mitad) | **Anclado a la apertura de NY (EA)**: acierto · PnL · DD |
|---|---|---|---|---|---|---|---|
| 1,00 | 59,8 % | +41,1 % | −608 € | 1,52 | 5 / 9 | +2.901 / +684 $ | 53,0 % · +13,3 % · −1.662 € |
| 0,90 | 61,7 % | +37,7 % | −649 € | 1,50 | 5 / 9 | +2.625 / +630 $ | 54,9 % · +11,9 % · −1.360 € |
| 0,80 | 63,6 % | +33,3 % | −529 € | 1,47 | 5 / 9 | +2.246 / +575 $ | 56,7 % · +8,7 % · −1.472 € |
| 0,70 | 66,8 % | +32,0 % | −500 € | 1,48 | 5 / 13 | +2.376 / +577 $ | 59,1 % · +5,5 % · −1.802 € |
| 0,60 | 69,6 % | +26,6 % | −520 € | 1,43 | 4 / 13 | +1.877 / +459 $ | 62,8 % · +5,5 % · −1.467 € |
| 0,50 | 73,8 % | +24,5 % | −550 € | 1,45 | 4 / 13 | +1.605 / +369 $ | 67,0 % · +2,9 % · −1.377 € |
| 0,40 | 78,0 % | +21,2 % | −580 € | 1,47 | 4 / 15 | +1.391 / +351 $ | 73,0 % · +6,8 % · −731 € |
| 0,35 | 80,4 % | +19,6 % | −430 € | 1,48 | 4 / 15 | +1.269 / +324 $ | 76,3 % · +7,6 % · −635 € |
| 0,30 | 81,3 % | +13,6 % | −350 € | 1,35 | 2 / 15 | +622 / +234 $ | 78,6 % · +5,2 % · −590 € |
| 0,25 | 82,2 % | +7,4 % | −401 € | 1,20 | 2 / 15 | +245 / +96 $ | 79,5 % · −0,7 % · −518 € |
| 0,20 | 87,4 % | +11,4 % | −421 € | 1,44 | 2 / 29 | +515 / +122 $ | 83,7 % · +1,7 % · −580 € |
| 0,15 | 90,2 % | +8,9 % | −406 € | 1,45 | 2 / 30 | +293 / +4 $ | 87,9 % · +3,1 % · −406 € |
| 0,10 | 92,1 % | +3,7 % | −411 € | 1,23 | 1 / 36 | −85 / −135 $ | 89,8 % · −1,8 % · −531 € |

EA para MT5: `mt5/TurtleSoup_TSM.mq5`. Opera siempre a la apertura de Nueva York y detecta solo el desfase horario del
broker con la pausa diaria del índice (17:00-18:00 NY), así que se adapta a cualquier broker y a los cambios de horario.

## 8. Qué hacer ahora

1. **Confirmar con velas reales** antes de pagar nada. El código ya está listo:
   ```bash
   python3 -m scripts.backtest_real --csv datos/XAUUSD_M1.csv --familia ts24_xau --sl 0.35 --k 0.10 0.15 0.20 0.25 0.35
   python3 -m scripts.backtest_real --csv datos/XAUUSD_M1.csv --familia hora_xau --sl 0.5 --k 0.25 0.35 0.5
   python3 -m scripts.backtest_real --csv datos/NQ_M1.csv --familia ts12_nq --sl 0.35 --k 0.15 0.25 0.35
   ```
   Para que este entorno descargue los datos solo, añade `datafeed.dukascopy.com` a los dominios permitidos
   de la red del entorno (y usa `--dukascopy XAU 2025-03-01 2026-09-24`), o sube los CSV al repositorio.
2. **Fuera de muestra:** lo más importante. El PDF dice que con datos de 2023-2025 casi todas estas familias
   perdían. Repetir el barrido en 2023-2025 dirá si queda algo de ventaja; si no queda, no hay RR que la salve.
3. **Topstep, configuración que sale del análisis:** cuentas 50K con RTA ON (más barato y tope de retiro
   doble). En el Combine, 300-400 $ por operación y estrategia (0,15-0,20 × MLL; con una sola estrategia el
   óptimo sube a 0,35-0,50 × MLL, porque el reto solo cuesta la cuota). En la XFA, 400 $ por operación y
   estrategia y pedir el retiro con saldo ≥ 3.000 $ (1,5 × MLL), no en cuanto se pueda: así queda colchón
   cuando el suelo se fija en 0. Más riesgo en la XFA sube el cobro medio pero baja la probabilidad de cobrar
   algo. Por ejemplo, Z10 sola pasa del 65 % al 30 % de cuentas con al menos un retiro al subir de 400 $ a
   1.000 $ por operación.
4. **Bots en Topstep:** en tu ordenador y vigilados (nada de VPS), por la API de TopstepX.

## 9. Supuestos a confirmar

- ATR diario típico: oro 80 $, NQ 350 puntos, ES 70 puntos (±25 % por día). Cambia cuántos micros caben por
  operación y el peso de los costes.
- Comisión TopstepX de 1 $ ida y vuelta por micro. Escalado de la XFA de 100K/150K y tope de retiro de 150K.
- El modelo supone días independientes y estrategias independientes entre sí; no modela la correlación entre
  las dos estrategias de oro en el mismo día. En cartera, la equity intradía se suma por franjas de 30 minutos
  (misma hora en las tres), tomando dentro de cada franja el peor punto de cada estrategia: ligeramente
  conservador para el MLL y el DLL.
- Por debajo de 1:0,15 el modelo extrapola: la validación cubre de 1:0,15 a 1:0,50.
- Coste de un reto = cuota × meses empezados (el reinicio va incluido en cada renovación). Horizonte de la XFA:
  6 meses, sin paso a cuenta Live.

Archivos: `resultados/barrido_rr.csv` (todas las combinaciones, 50K y 100K), `resultados/cartera.csv`,
`resultados/validacion.csv`, `resultados/tablas.md`.
