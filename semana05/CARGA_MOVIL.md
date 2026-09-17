# Semana 5 — Sidequest: carga móvil sobre un eje de vigas del LT2

Una carga vertical **P = 100 kN** recorre las seis vigas continuas del eje
y = 18.18 en la cota +3.91 del LT2. Python la resuelve en OpenSees
**posición por posición**, verifica cada una y escribe un JSON; Unity
**muestra** la posición que se elige (deformada, flecha, recorrido,
reparto, conservación). Unity no calcula nada y no interpola.

Todos los números de este documento están copiados de la salida de
`python semana05/carga_movil.py lt2`, corrida el 16-09 en la rama
`semana05` (guardada entera en `semana05/evidencia/carga_movil_lt2.txt` y,
con los números sin desplazamientos, en
`semana05/evidencia/carga_movil_lt2.json`). Las funciones se nombran por su
nombre en `semana05/carga_movil.py`.

```bash
python semana05/carga_movil.py lt2                       # verifica, y solo si todo cierra escribe
python semana05/carga_movil.py lt2 --no-escribir         # solo verifica
python semana05/carga_movil.py lt2 --P 50 --divisiones 3 # otra P u otra cantidad de posiciones
python comun/lanzar_unity.py sincronizar lt2             # copia data/unity/carga_movil_lt2.json a StreamingAssets
```

Sale con **0** si todo cierra; con **1** si falla cualquier verificación, y
entonces **no escribe nada** (ni el JSON, ni su copia, ni la evidencia).
Comprobado forzando una falla (criterio de desplazamiento en 0): salió con
1, listó `[g]`, `[h]` y los dos `[e]`, y las fechas de los tres archivos no
cambiaron.

| sale | dónde | tamaño |
|---|---|---|
| el anexo que lee Unity | `data/unity/carga_movil_lt2.json` | 742 301 bytes (30 posiciones) |
| su copia | `unity/Assets/StreamingAssets/carga_movil.json` | idéntica (md5 `3c6cf8451f059d0af22cb9a8dc5a4f6a`) |
| la evidencia | `semana05/evidencia/carga_movil_lt2.json` y `.txt` | sin desplazamientos ni reacciones |

Tiempo: 36 corridas de OpenSees sobre el modelo del edificio construido una
vez (30 posiciones + 3 de `[f]`, 1 de `[h]` y 2 de "por qué no"), 0.0131 s por
corrida; `[e]` e `[i]` resuelven aparte sus propios modelos (la viga partida y
la biempotrada aislada) y no entran en esa cuenta. 0.6 s el script entero.

---

## 1. La regla física

**Dónde va la carga.** Sobre una línea recta de vigas de un piso, dada por
su cota, el eje a lo largo del cual corre y la coordenada fija del otro eje
(`RECORRIDOS['lt2']`, con su `_por_que`). Las vigas se **buscan por
geometría** (`recorrido()`), no se escriben a mano; si la cadena tiene un
hueco el script se niega. El modelo resuelto se compara con el que dibuja
Unity (`comparar_con_unity()`): *232 nodos y 378 elementos iguales*.

| viga | sección | nodos | L (m) |
|---|---|---|---|
| 203 | V 0.60x0.80 | 101 → 121 | 3.750 |
| 204 | V 0.60x0.80 | 121 → 102 | 3.750 |
| 205 | V 0.60x0.80 | 102 → 116 | 5.000 |
| 206 | V 0.60x0.80 | 116 → 103 | 5.000 |
| 207 | V 0.60x0.80 | 103 → 119 | 5.000 |
| 208 | V 0.60x0.80 | 119 → 122 | 5.225 |

27.725 m en total. Lo que llega a cada nodo (`que_llega_a()`): 101, 102 y
103 tienen **columna**; 121, 116 y 119 son **cruces de vigas sin columna**
(`viga_x, viga_y`); 122 es la cara del muro (`brazo`). Se eligió este eje
porque alterna nodos rígidos y flexibles: el reparto cambia de una viga a la
siguiente y la deformada se ve.

**Cómo se aplica.** En cada posición la carga actúa sobre **una** viga, en
su abscisa local a = xL·L medida desde n1:

```python
ops.eleLoad('-ele', eid, '-type', '-beamPoint', Py, Pz, xL, Px)
```

Las componentes locales son el producto punto de la carga global
(0, 0, −P) con los versores de la barra, con la misma regla que el
`geomTransf` del servidor (`carga_local()`, `contrato.ejes_locales`). En
estas vigas localZ = (0, 0, 1): **Pz = −100, Py = Px = 0**.

El modelo es **el del servidor**: `servidor_opensees.construir_modelo` una
vez, y en cada posición el mismo ciclo de `/analizar` (quitar el patrón
anterior, `reset`, `setTime(0)`, patrón nuevo, `resolver_caso`,
`extraer_resultados`), en la clase `Motor`.

**Posiciones.** 5 por viga, en xL = (k + ½)/5 = 0.1, 0.3, 0.5, 0.7, 0.9
(`posiciones()`): **30 posiciones**. Ninguna cae sobre un nodo: ahí la carga
la comparten todas las barras que llegan y "el reparto de la viga" deja de
tener sentido. Lo que pasa al cruzar un nodo lo cubre la verificación `[f]`.

**P = 100 kN es de demostración, no normativa** (declarado en el JSON,
`_P_kN_por_que`): con 100 kN la mayor flecha bajo la carga del recorrido es
−0.964 mm y la deformada se ve con la escala x1600. El modelo es lineal: otra
P escala todo por P/100 y se recalcula con `--P`.

**Por qué `-beamPoint` y no repartir a mano.** Con funciones de forma
lineales (P(1−ξ) y Pξ como cargas nodales) la resultante se conserva, pero
se borra la flexión local. Medido a mitad de la viga 205:

| | lineal | beamPoint (exacto) |
|---|---|---|
| M bajo la carga (kN·m) | −5.66 | −83.52 |
| uz del nodo 102 (mm) | −0.0553 | −0.0623 |
| uz del nodo 116 (mm) | −0.4472 | −0.4899 |

---

## 2. El reparto: lo que la viga le entrega a cada extremo

Lo que la viga cargada le entrega a sus nodos es el **corte de
`localForce`** en cada extremo, Vz_i y Vz_j (fuerzas de los nodos sobre la
barra; positivas hacia arriba). Por equilibrio de la barra:

```
Vz_i + Vz_j + Pz = 0                         (en las 30 posiciones: error 0.0e+00 kN)
Vz_j = P·a/L  +  (My_i + My_j)/L             Vz_i = P − Vz_j
       palanca    momentos de extremo
```

- La **palanca** es la viga simplemente apoyada: a mitad de vano, 50/50.
- Las **fuerzas nodales equivalentes** que OpenSees ensambla son las de
  **empotramiento perfecto** (`empotramiento()`, comprobadas contra OpenSees
  en `[i]`): V_i = P b²(3a+b)/L³, V_j = P a²(a+3b)/L³, M_i = −P a b²/L²,
  M_j = P a² b/L². A mitad de vano también son 50/50.
- El reparto **real** se aparta de las dos porque los extremos no son
  iguales. El término (My_i + My_j)/L lo ponen los momentos de extremo, y
  esos dependen de lo que hay en cada nodo: un nodo con columna retiene el
  giro y casi no baja; uno sin columna cuelga de la viga transversal, baja y
  gira. **La carga se va hacia el extremo rígido.** `[d]` comprueba que la
  descomposición cierra con los valores redondeados (peor error/cota 0.783).

**El ejemplo para la defensa: P a mitad de la viga 205** (posición 12):

| | nodo 102 (columna) | nodo 116 (sin columna) |
|---|---|---|
| palanca | 50.0 kN | 50.0 kN |
| empotramiento perfecto | 50.0 kN | 50.0 kN |
| My de `localForce` | −110.4838 kN·m | −27.5241 kN·m |
| **real (Vz de `localForce`)** | **77.6016 kN (77.6 %)** | **22.3984 kN (22.4 %)** |

(My_i + My_j)/L = (−110.4838 − 27.5241)/5 = −27.6016 kN, y
50 − 27.6016 = 22.3984 = Vz_j. El panel lo dice así: *"palanca 50.0 / 50.0
kN; los momentos de extremo (My_i + My_j)/L = −27.60 kN corren 27.6 kN hacia
el nodo 102"*.

El patrón se repite en todo el recorrido: en las vigas cuyo nodo j no tiene
columna (203, 205, 207) la carga se carga hacia i; en las que empiezan en un
nodo sin columna (204, 206, 208) se carga hacia j. Cerca de un nodo sin
columna el reparto se acerca a la mitad (205 en xL = 0.9: 50.6 % a i; 206 en
xL = 0.1: 49.7 % a i), porque ese nodo reparte a las dos columnas vecinas.

| i | viga | xL | s (m) | V_i (kN) | V_j (kN) | % a i | palanca i/j (kN) | empotrada i/j (kN) | (My_i+My_j)/L (kN) |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 203 | 0.10 | 0.375 | 96.048 | 3.952 | 96.0 | 90.0 / 10.0 | 97.2 / 2.8 | -6.048 |
| 1 | 203 | 0.30 | 1.125 | 86.986 | 13.014 | 87.0 | 70.0 / 30.0 | 78.4 / 21.6 | -16.986 |
| 2 | 203 | 0.50 | 1.875 | 74.796 | 25.204 | 74.8 | 50.0 / 50.0 | 50.0 / 50.0 | -24.796 |
| 3 | 203 | 0.70 | 2.625 | 61.191 | 38.809 | 61.2 | 30.0 / 70.0 | 21.6 / 78.4 | -31.191 |
| 4 | 203 | 0.90 | 3.375 | 47.883 | 52.117 | 47.9 | 10.0 / 90.0 | 2.8 / 97.2 | -37.883 |
| 5 | 204 | 0.10 | 4.125 | 47.491 | 52.509 | 47.5 | 90.0 / 10.0 | 97.2 / 2.8 | +42.509 |
| 6 | 204 | 0.30 | 4.875 | 34.653 | 65.347 | 34.6 | 70.0 / 30.0 | 78.4 / 21.6 | +35.347 |
| 7 | 204 | 0.50 | 5.625 | 22.297 | 77.703 | 22.3 | 50.0 / 50.0 | 50.0 / 50.0 | +27.703 |
| 8 | 204 | 0.70 | 6.375 | 11.669 | 88.331 | 11.7 | 30.0 / 70.0 | 21.6 / 78.4 | +18.331 |
| 9 | 204 | 0.90 | 7.125 | 4.016 | 95.984 | 4.0 | 10.0 / 90.0 | 2.8 / 97.2 | +5.984 |
| 10 | 205 | 0.10 | 8.000 | 96.878 | 3.122 | 96.9 | 90.0 / 10.0 | 97.2 / 2.8 | -6.878 |
| 11 | 205 | 0.30 | 9.000 | 88.981 | 11.019 | 89.0 | 70.0 / 30.0 | 78.4 / 21.6 | -18.981 |
| 12 | 205 | 0.50 | 10.000 | 77.602 | 22.398 | 77.6 | 50.0 / 50.0 | 50.0 / 50.0 | -27.602 |
| 13 | 205 | 0.70 | 11.000 | 64.294 | 35.706 | 64.3 | 30.0 / 70.0 | 21.6 / 78.4 | -34.294 |
| 14 | 205 | 0.90 | 12.000 | 50.614 | 49.386 | 50.6 | 10.0 / 90.0 | 2.8 / 97.2 | -40.614 |
| 15 | 206 | 0.10 | 13.000 | 49.686 | 50.314 | 49.7 | 90.0 / 10.0 | 97.2 / 2.8 | +40.314 |
| 16 | 206 | 0.30 | 14.000 | 35.988 | 64.012 | 36.0 | 70.0 / 30.0 | 78.4 / 21.6 | +34.012 |
| 17 | 206 | 0.50 | 15.000 | 22.634 | 77.366 | 22.6 | 50.0 / 50.0 | 50.0 / 50.0 | +27.366 |
| 18 | 206 | 0.70 | 16.000 | 11.173 | 88.827 | 11.2 | 30.0 / 70.0 | 21.6 / 78.4 | +18.827 |
| 19 | 206 | 0.90 | 17.000 | 3.155 | 96.845 | 3.1 | 10.0 / 90.0 | 2.8 / 97.2 | +6.845 |
| 20 | 207 | 0.10 | 18.000 | 97.048 | 2.952 | 97.0 | 90.0 / 10.0 | 97.2 / 2.8 | -7.048 |
| 21 | 207 | 0.30 | 19.000 | 89.519 | 10.481 | 89.5 | 70.0 / 30.0 | 78.4 / 21.6 | -19.519 |
| 22 | 207 | 0.50 | 20.000 | 78.704 | 21.296 | 78.7 | 50.0 / 50.0 | 50.0 / 50.0 | -28.704 |
| 23 | 207 | 0.70 | 21.000 | 66.049 | 33.950 | 66.0 | 30.0 / 70.0 | 21.6 / 78.4 | -36.050 |
| 24 | 207 | 0.90 | 22.000 | 52.998 | 47.002 | 53.0 | 10.0 / 90.0 | 2.8 / 97.2 | -42.998 |
| 25 | 208 | 0.10 | 23.023 | 52.684 | 47.316 | 52.7 | 90.0 / 10.0 | 97.2 / 2.8 | +37.316 |
| 26 | 208 | 0.30 | 24.067 | 38.594 | 61.406 | 38.6 | 70.0 / 30.0 | 78.4 / 21.6 | +31.406 |
| 27 | 208 | 0.50 | 25.113 | 24.548 | 75.452 | 24.6 | 50.0 / 50.0 | 50.0 / 50.0 | +25.452 |
| 28 | 208 | 0.70 | 26.157 | 12.181 | 87.819 | 12.2 | 30.0 / 70.0 | 21.6 / 78.4 | +17.819 |
| 29 | 208 | 0.90 | 27.203 | 3.129 | 96.871 | 3.1 | 10.0 / 90.0 | 2.8 / 97.2 | +6.871 |

---

## 3. Conservación

**La regla.** La de `calcular.equilibrio`, por grado de libertad (en
horizontal solo cuentan los nodos fuera de todo diafragma; en vertical
cualquier restringido salvo el maestro). No se copia: `pesos_de_reaccion()`
le pasa a `calcular.equilibrio` una reacción unitaria por nodo y lee qué
sumó. Resultado: **16 apoyos cuentan en Fx, Fy y Fz, de 21 nodos con
reacción**.

**La trampa.** `calcular.equilibrio` solo suma `cargas_nodales` y
`cargas_distribuidas`: una carga `-beamPoint` no la ve y reportaría un error
falso igual a P. `conservacion()` le **suma la carga puntual a
`aplicada_kN`** explícitamente, y así viaja en `equilibrio` de cada posición
(aplicada = [0, 0, −100]).

**La cota** (se mide, no se elige): cada reacción viene redondeada a 4
decimales (±5e-5 kN), así que la suma de 16 puede errar hasta
16 × 5e-5 = **8.0e-4 kN**, más 4 ε por el tamaño de los términos. Se verifica
sobre los valores **redondeados**, que son los que viajan al visor, y además
en memoria, sin redondeo.

| verificación por posición | resultado en las 30 |
|---|---|
| `[a]` ΣRz = P | peor \|error\| **2.0e-04 kN** (posición 0), cota 8.0e-04 kN; en memoria peor **3.7e-09 kN** |
| `[b]` ΣRx = ΣRy = 0 | peor \|ΣRx\| 1.0e-04, \|ΣRy\| 2.0e-04 kN; cota 8.0e-04 kN |
| `[c]` Vz_i + Vz_j + Pz = 0 | peor 0.0e+00 kN (cota 1.0e-04) |
| `[c]` cierre en x = L con el salto H(x−a) | peor **0.783 de la cota** en My (error 2.3e-04, cota 2.9e-04 kN·m), con `cota_de_cierre` de `semana04/exportar_unity.py` |
| `[d]` V_j − palanca = (My_i + My_j)/L | peor error/cota 0.783 |

El cierre `[c]` reconstruye los esfuerzos dentro de la viga cargada
(`esfuerzos_con_puntual()`: la forma de la Semana 4 con el término de la
carga, Vz(x) = −(Vz_i + Pz·H), My(x) = −(My_i + x·Vz_i + Pz·(x−a)·H)) y exige
llegar al f_j de OpenSees.

| i | viga | xL | ΣRz (kN) | error (kN) | cota (kN) | ΣRx / ΣRy (kN) | Vz_i+Vz_j+Pz (kN) | cierre / cota | en memoria (kN) | UZ máx (mm, nodo) | uz bajo P (mm) | My bajo P (kN·m) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 203 | 0.10 | 100.0002 | 2.0e-04 | 8.0e-04 | -0.0000 / 0.0001 | 0.0e+00 | 0.435 (My) | 9.4e-11 | -0.0734 (101) | -0.0817 | -14.94 |
| 1 | 203 | 0.30 | 100.0000 | 0.0e+00 | 8.0e-04 | -0.0001 / -0.0002 | 0.0e+00 | 0.348 (My) | 4.0e-11 | -0.1566 (121) | -0.1463 | -42.40 |
| 2 | 203 | 0.50 | 100.0000 | 0.0e+00 | 8.0e-04 | 0.0002 / -0.0000 | 0.0e+00 | 0.609 (My) | 1.5e-11 | -0.2591 (121) | -0.2507 | -67.76 |
| 3 | 203 | 0.70 | 100.0001 | 1.0e-04 | 8.0e-04 | -0.0000 / 0.0000 | 0.0e+00 | 0.783 (My) | 9.3e-12 | -0.3525 (121) | -0.3508 | -84.20 |
| 4 | 203 | 0.90 | 100.0001 | 1.0e-04 | 8.0e-04 | -0.0001 / 0.0001 | 0.0e+00 | 0.000 (My) | 1.7e-11 | -0.4121 (121) | -0.4118 | -90.05 |
| 5 | 204 | 0.10 | 100.0001 | 1.0e-04 | 8.0e-04 | -0.0002 / -0.0001 | 0.0e+00 | 0.261 (My) | 3.1e-11 | -0.4135 (121) | -0.4144 | -96.48 |
| 6 | 204 | 0.30 | 100.0001 | 1.0e-04 | 8.0e-04 | 0.0001 / 0.0001 | 0.0e+00 | 0.435 (My) | 4.8e-11 | -0.3531 (121) | -0.3513 | -86.55 |
| 7 | 204 | 0.50 | 100.0000 | 0.0e+00 | 8.0e-04 | -0.0001 / -0.0002 | 0.0e+00 | 0.696 (My) | 6.0e-11 | -0.2567 (121) | -0.2466 | -66.79 |
| 8 | 204 | 0.70 | 100.0001 | 1.0e-04 | 8.0e-04 | -0.0001 / -0.0000 | 0.0e+00 | 0.522 (My) | 5.5e-11 | -0.1517 (121) | -0.1418 | -40.50 |
| 9 | 204 | 0.90 | 100.0000 | 0.0e+00 | 8.0e-04 | -0.0001 / 0.0002 | 0.0e+00 | 0.348 (My) | 2.3e-11 | -0.0726 (102) | -0.0803 | -14.74 |
| 10 | 205 | 0.10 | 100.0001 | 1.0e-04 | 8.0e-04 | -0.0001 / -0.0001 | 0.0e+00 | 0.286 (My) | 4.4e-11 | -0.0880 (116) | -0.0897 | -15.23 |
| 11 | 205 | 0.30 | 100.0002 | 2.0e-04 | 8.0e-04 | 0.0001 / 0.0000 | 0.0e+00 | 0.571 (My) | 8.7e-11 | -0.2648 (116) | -0.2256 | -48.77 |
| 12 | 205 | 0.50 | 100.0000 | 0.0e+00 | 8.0e-04 | 0.0001 / 0.0000 | 0.0e+00 | 0.286 (My) | 9.3e-11 | -0.4899 (116) | -0.4598 | -83.52 |
| 13 | 205 | 0.70 | 99.9998 | 2.0e-04 | 8.0e-04 | -0.0000 / -0.0001 | 0.0e+00 | 0.571 (My) | 7.1e-11 | -0.7014 (116) | -0.6941 | -108.67 |
| 14 | 205 | 0.90 | 100.0001 | 1.0e-04 | 8.0e-04 | 0.0000 / -0.0001 | 0.0e+00 | 0.000 (My) | 3.1e-11 | -0.8372 (116) | -0.8375 | -119.62 |
| 15 | 206 | 0.10 | 100.0000 | 0.0e+00 | 8.0e-04 | 0.0001 / -0.0000 | 0.0e+00 | 0.000 (My) | 1.7e-11 | -0.8380 (116) | -0.8390 | -119.76 |
| 16 | 206 | 0.30 | 99.9999 | 1.0e-04 | 8.0e-04 | -0.0000 / 0.0001 | 0.0e+00 | 0.571 (My) | 6.4e-11 | -0.7035 (116) | -0.6981 | -109.15 |
| 17 | 206 | 0.50 | 99.9998 | 2.0e-04 | 8.0e-04 | 0.0001 / -0.0001 | 0.0e+00 | 0.286 (My) | 1.0e-10 | -0.4929 (116) | -0.4644 | -84.20 |
| 18 | 206 | 0.70 | 100.0000 | 0.0e+00 | 8.0e-04 | 0.0000 / 0.0000 | 0.0e+00 | 0.571 (My) | 1.2e-10 | -0.2676 (116) | -0.2289 | -49.39 |
| 19 | 206 | 0.90 | 100.0002 | 2.0e-04 | 8.0e-04 | 0.0001 / 0.0001 | 0.0e+00 | 0.000 (My) | 1.1e-10 | -0.0892 (116) | -0.0915 | -15.38 |
| 20 | 207 | 0.10 | 99.9998 | 2.0e-04 | 8.0e-04 | -0.0001 / 0.0000 | 0.0e+00 | 0.571 (My) | 1.0e-10 | -0.0965 (119) | -0.0920 | -14.86 |
| 21 | 207 | 0.30 | 100.0001 | 1.0e-04 | 8.0e-04 | -0.0002 / 0.0000 | 0.0e+00 | 0.286 (My) | 2.3e-10 | -0.2926 (119) | -0.2344 | -48.27 |
| 22 | 207 | 0.50 | 99.9999 | 1.0e-04 | 8.0e-04 | 0.0000 / 0.0001 | 0.0e+00 | 0.000 (My) | 5.1e-10 | -0.5420 (119) | -0.4861 | -83.41 |
| 23 | 207 | 0.70 | 99.9999 | 1.0e-04 | 8.0e-04 | -0.0000 / 0.0001 | 0.0e+00 | 0.286 (My) | 9.0e-10 | -0.7790 (119) | -0.7496 | -110.03 |
| 24 | 207 | 0.90 | 99.9999 | 1.0e-04 | 8.0e-04 | -0.0001 / 0.0000 | 0.0e+00 | 0.571 (My) | 1.4e-09 | -0.9379 (119) | -0.9296 | -123.65 |
| 25 | 208 | 0.10 | 99.9999 | 1.0e-04 | 8.0e-04 | -0.0001 / -0.0001 | 0.0e+00 | 0.740 (My) | 1.9e-09 | -0.9541 (119) | -0.9635 | -127.27 |
| 26 | 208 | 0.30 | 99.9999 | 1.0e-04 | 8.0e-04 | -0.0002 / -0.0000 | 0.0e+00 | 0.014 (My) | 2.4e-09 | -0.8156 (119) | -0.8255 | -119.81 |
| 27 | 208 | 0.50 | 100.0000 | 0.0e+00 | 8.0e-04 | -0.0001 / 0.0001 | 0.0e+00 | 0.062 (My) | 3.0e-09 | -0.5828 (119) | -0.5555 | -95.49 |
| 28 | 208 | 0.70 | 99.9999 | 1.0e-04 | 8.0e-04 | -0.0001 / 0.0001 | 0.0e+00 | 0.471 (My) | 3.4e-09 | -0.3210 (119) | -0.2566 | -57.91 |
| 29 | 208 | 0.90 | 99.9999 | 1.0e-04 | 8.0e-04 | 0.0000 / 0.0002 | 0.0e+00 | 0.747 (My) | 3.7e-09 | -0.0955 (119) | -0.0638 | -17.50 |

"UZ máx" es el uz más negativo entre los **nodos**; "uz bajo P" es el del
punto cargado, que está dentro de la viga (sección 5). Con la carga cerca de
un nodo sin columna el nodo baja más que el punto cargado (posición 29:
−0.0955 mm en el 119 contra −0.0638 bajo la carga).

---

## 4. Verificaciones globales (en memoria, sin redondeo)

Criterio de "igual": lo que distingue el JSON, **1e-8 m y 1e-4 kN** (los
decimales que escribe el servidor).

| | qué | resultado |
|---|---|---|
| `[e]` | beamPoint contra la **viga 205 partida en 10** (`subdividir` de `semana03/verificar_viga_partida.py`) con **carga nodal** en el nodo que queda bajo la carga, xL = 0.30 (nodo 235) | desplazamientos de los 232 nodos: max \|du\| 1.1e-17 m; reacciones 1.7e-12 kN; M bajo la carga −48.7674 / −48.7674 kN·m; V_i 88.9809 / 88.9809 kN; flecha bajo la carga −0.225601 / −0.225601 mm; **elástica** en los 9 nodos interiores 5.4e-18 m |
| `[e]` | lo mismo en xL = 0.50 (nodo 237) | max \|du\| 1.6e-17 m; reacciones 1.6e-12 kN; M −83.5202 / −83.5202 kN·m; V_i 77.6016 / 77.6016 kN; flecha −0.459834 / −0.459834 mm; elástica 9.2e-18 m |
| `[f]` | **continuidad** al cruzar el nodo 121 (sin columna): viga 203 en xL = 1, viga 204 en xL = 0 y carga nodal en el 121 | uz(121) = −0.4215 mm las tres; max \|du\| 0.0e+00 m; max \|dR\| 0.0e+00 kN |
| `[g]` | **reciprocidad de Betti** entre la viga 205 en xL = 0.50 y la 207 en xL = 0.30 | 2.028955181050e-05 m en los dos sentidos; diferencia 3.5e-19 m (1.7e-14 relativo) |
| `[h]` | **superposición**: las dos cargas de `[g]` en una corrida contra la suma de las dos corridas | max \|du\| 5.1e-17 m, \|dR\| 7.7e-13 kN, \|df\| 1.8e-09 kN, en todos los nodos, apoyos y barras |
| `[i]` | fórmula de **empotramiento perfecto** contra OpenSees (viga biempotrada aislada, L = 5, xL = 0.3) | V_i 78.4000, V_j 21.6000, My_i −73.5000, My_j 31.5000 en los dos; peor 0.0e+00 |
| `[j]` | el JSON contra las clases C# de `VisorCargaMovil.cs` **en las dos direcciones** (JsonUtility ignora sin avisar lo que no calza) | 11 clases, 8052 objetos, sano |

`[j]` se probó con mutaciones sobre copias del `.cs` (fuera del repo): falta
un campo, sobra un campo, cambia un tipo (`int` → `string`) y cambia una
mayúscula (`suma_Rz_kN` → `suma_rz_kN`): las cuatro **detectadas**; el
original, sano.

En `[i]` el ux del nodo 2 queda libre: con los 12 grados de libertad fijos el
sistema tiene 0 ecuaciones y LAPACK aborta el proceso entero (`DGBSV,
parameter number 9 had an illegal value`, visto en la primera corrida). La
carga no tiene componente axial, así que no cambia lo que se mide.

### Por qué Unity no interpola entre posiciones

Medido en la viga 205 con la carga en xL = 0.40, entre las posiciones
precalculadas 0.30 y 0.50 (una corrida extra):

| lo que se promedia | promedio de 0.30 y 0.50 | resuelto en 0.40 | error |
|---|---|---|---|
| el número "M bajo la carga" | −66.14 kN·m | −66.81 kN·m | 1.0 % |
| **el diagrama My** en la sección 0.40 | −43.99 kN·m | −66.81 kN·m | **34.2 %** |
| la deformada uz en ese punto | −0.3258 mm | −0.3361 mm | 3.1 % |

El número "M bajo la carga" es una curva suave y engaña; lo que el visor
dibujaría es el **diagrama**, que tiene el quiebre donde está la carga, y al
promediar dos quiebres en otros puntos se aplana el pico. Por eso Unity
**salta** entre posiciones, cada una una corrida real.

---

## 5. Unity: panel y respuesta visual

`unity/Assets/Scripts/VisorCargaMovil.cs`. Se crea solo
(`[RuntimeInitializeOnLoadMethod(AfterSceneLoad)]`) si la escena tiene un
`VisorEstructura`, y lee `StreamingAssets/carga_movil.json` con
`LectorStreaming` (sirve igual en Windows, Android y Web).

**Dónde está.** Implementa `IPanelIncrustable` con título `"Carga movil"`:
`VisorQA` lo muestra como pestaña. Sin `VisorQA` en la escena dibuja su
propia ventana abajo a la izquierda (`PanelPropio = true` por defecto).

**Antes de mostrar nada comprueba** que el JSON es de este modelo (compara,
no calcula): `info.edificio` contra el del modelo y el del anexo de la Semana
4; que las 6 vigas del recorrido existan; que traiga un desplazamiento por
cada nodo (232) y que todos los ids existan; y que el primer punto de la
elástica esté en el n1 de su viga (±1 cm). Si algo no calza, lo dice en el
panel y no se activa.

**Controles.**

| control | qué hace |
|---|---|
| casilla "Mostrar la carga movil" | activa / apaga |
| slider de posición (entero) y `\|<  <  Play/Pausa  >  >\|` | elige el **índice**; Play avanza uno cada "segundos por paso" (0.1–3 s, 0.6 por defecto) |
| slider de escala y "Escala del recorrido" | solo gráfica; por defecto x1600, la del JSON |
| "Centrar camara" | `EventosVisor.AvisarPedirCentrar` en el punto de la posición del medio de la lista (la 15, s = 13.00 m, tal cual viene: no se promedia) con tamaño = el largo del recorrido, 27.725 m |
| "Verificaciones en Python" (plegable) | las 9 verificaciones del JSON con PASA / NO PASA, el `_por_que` de P y el comando que lo generó |

**Texto por posición** (todo leído del JSON): s, viga, xL, a y L, el punto;
**reparto** V_i y V_j con su porcentaje, palanca, empotramiento perfecto,
(My_i + My_j)/L, qué llega a cada nodo y la explicación; **conservación**
ΣRz contra P con PASA / NO PASA, el error y su cota con los 16 apoyos,
ΣRx y ΣRy, Vz_i + Vz_j + Pz y el cierre; **respuesta** UZ máx con su nodo,
|u| máx, uz y My bajo la carga.

**Lo que se dibuja.**

- La **deformada de todo el edificio** con la API del contrato
  (`mostrarDeformada = true`, `factorEscala`, `AplicarDeformada(desplazamientos)`).
  La escala es **una para todo el recorrido**: x1600, que lleva el mayor
  desplazamiento del recorrido (0.9635 mm, posición 25) a 1.5 m. Con una
  escala por posición la animación "respiraría" sin que cambie nada.
- El **recorrido resaltado**: las vigas no cargadas, rectas entre sus nodos
  dibujados (`PosicionActual`), en ámbar y más gruesas que las barras.
- La **viga cargada con su elástica**, no recta: Python exporta los décimos
  de L más el punto de la carga (11 puntos en las 30 posiciones, porque la
  carga cae en un décimo; se juntan redondeados a 1e-9 para que no quede un
  tramo de largo cero, que en una primera versión aparecía una vez) con su
  desplazamiento (Hermite de los nodos más la flecha de la viga biempotrada,
  `desplazamiento_en()`), verificados contra la viga partida en `[e]`. Unity
  solo los escala, igual que `Ejes.PosicionDeformada`.
- La **flecha de P**: cilindro y cono de 2.5 m con la punta en el punto
  cargado desplazado con la misma escala, apuntando como (0, 0, −1) de
  OpenSees llevado con `Ejes.AUnity`.

Nada tiene collider (un click pasa a la barra) ni sombra, y ningún material
de la estructura se toca (protocolo de materiales, CONTRATO.md §8).

**Al apagar** borra su dibujo, quita **su** deformada
(`LimpiarDeformada` + `Redibujar`) y devuelve la escala que había. La
deformada anterior (G, sismo, caso activo) no se re-aplica sola: se pide de
nuevo en su pestaña (CONTRATO.md §2.3).

**Si otra pestaña pone su deformada** mientras la carga está activa, en el
siguiente `Redibujado` el nodo que más se mueve ya no está donde lo pondría
esta posición: la carga móvil se suelta sin borrar la deformada ajena ("la
última manda") y lo avisa. **Si se edita el modelo** (`ModeloEditado`) se
apaga con aviso: los números son del modelo original.

**Compilación.** `python semana05/compilar_unity.py --solo
unity/Assets/Scripts/VisorCargaMovil.cs`: `Assembly-CSharp` 0 errores y
0 avisos, `Assembly-CSharp-Editor` 0 y 0, 0 errores ajenos.

---

## 6. Limitaciones

- **No se probó en Play.** En esta fase Unity está cerrado: el panel se
  verificó compilando y con `[j]` (JSON contra clases), no mirándolo. Las
  capturas y el registro numérico desde el exe quedan para
  `CapturaSemana05.cs` en la integración.
- **P de demostración**: 100 kN, sin combinar con G ni Q y sin demanda P-M.
  Por linealidad cualquier otra P es este resultado por P/100; se recalcula
  con `--P`, no se escala en C#.
- **Un recorrido fijo en Python**: piso, eje y posiciones no se eligen en
  Unity. 30 posiciones discretas (5 por viga), ninguna sobre un nodo;
  cambiar la cantidad es `--divisiones`.
- **Solo sobre vigas**, no sobre la losa: la versión sobre la losa asignaría
  el punto al elemento cuyo polígono tributario lo contiene, y esa regla es
  discontinua en las bisectrices.
- **Los diagramas de la Semana 4 no siguen a la carga**: el panel muestra My
  bajo la carga y el reparto, pero el diagrama de esfuerzos que dibuja
  `VisorSemana04` sigue siendo el de su caso activo.
- **Precisión en Unity**: `JsonUtility` guarda los desplazamientos como
  float (7 cifras); las verificaciones finas se hacen en Python con los
  valores en memoria, no con lo que lee el visor.
- **Si el modelo cambia** (otra exportación del LT2 con otros ids), hay que
  correr de nuevo el script: el visor lo detecta y no se activa, pero no
  recalcula.
