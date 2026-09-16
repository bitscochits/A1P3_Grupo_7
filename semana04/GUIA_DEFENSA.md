# Semana 4 — Guía de estudio y defensa

Todo lo que dice esta guía está comprobado con los scripts de la carpeta;
donde hay un número, al lado está de dónde sale. Para la demostración,
[`GUION_DEMO.md`](GUION_DEMO.md); para los comandos,
[`COMANDOS.md`](COMANDOS.md).

---

## 0. Cómo estudiar esto en un día

1. **§1 y §2** (20 min): qué pide la semana y la regla que no se rompe.
2. **§3** (20 min): el camino de un número de OpenSees a la pantalla.
   Es la trazabilidad, y vale 2 puntos.
3. **§4 y §5** (40 min): cómo sale un diagrama y de qué lado se dibuja.
   Es lo más técnico y lo más fácil de preguntar.
4. **§6** (30 min): ejes locales, y **el error de los muros** que se
   encontró esta semana. Es la mejor historia de la defensa.
5. **§7 y §8** (30 min): demanda-capacidad y combinaciones.
6. **El guion de la demo** (1 h): hacerla entera, en voz alta, dos veces.
7. **§10, preguntas** (1 h): contestarlas sin mirar.

La defensa no es "funciona": el profesor elige a cualquiera y pide que lo
explique. Una demo que funciona y no se sabe explicar **no cuenta como
lograda**.

---

## 1. Qué pide la semana

**Convertir Unity en un postprocesador estructural** conectado a
resultados de OpenSees ya verificados. Postprocesador quiere decir que
Unity **no analiza**: lee resultados y los muestra.

| criterio | pts | qué hay que poder mostrar |
| --- | --- | --- |
| Resultados conectados | 3 | al hacer clic en una barra: ID, nodos, sección, material, ejes locales, restricciones, N, Vy/Vz, T, My/Mz |
| Diagramas / deformada | 2 | deformada, un diagrama de momento, uno de axial o corte |
| Capas estructurales | 2 | áreas tributarias, cargas, apoyos (y prender y apagar cada una) |
| Demanda-capacidad | 1 | curva P-M de una columna **y** de un muro, con su punto de demanda y el caso activo identificado |
| Defensa / trazabilidad | 2 | elementTag de OpenSees ↔ objeto de Unity ↔ resultados ↔ sección/capacidad |

**Qué ya existía antes de esta semana** (conviene decirlo: muestra que se
construyó sobre lo verificado):

- áreas tributarias, apoyos, diafragmas, ejes locales e IDs — `VisorQA.cs`
- flechas de carga y deformada sísmica — `VisorSemana03.cs`
- la deformada del caso G — `VisorEstructura.cs`
- las curvas P-M y la demanda — `semana03/`, pero **solo en Python**

**Qué agrega la Semana 4:** llevar a Unity los esfuerzos internos, los
diagramas, el material, las restricciones y la demanda-capacidad, y
demostrar que cada número de la pantalla es el de OpenSees.

---

## 2. La regla que no se rompe

```
planos → Python/OpenSees CALCULA → JSON transporta → Unity DIBUJA
```

**Unity no calcula estructura.** Ni esfuerzos, ni combinaciones, ni
capacidad. Recibe los números ya hechos y los dibuja.

**Por qué importa, y es una buena respuesta en la defensa:** si Unity
calculara, habría **dos** implementaciones de la misma mecánica — una en
Python, verificada, y otra en C# que nadie verifica. Tarde o temprano se
separan y la pantalla muestra algo distinto de lo que se comprobó. Con una
sola, lo que se verifica en Python **es** lo que se ve.

Lo único que hace Unity con los números: escalarlos para que se vean,
buscar el máximo para ponerle una etiqueta, y armar las mallas.

---

## 3. El camino de un número (la trazabilidad)

Tomemos el momento de la columna 18. Recorre esto:

```
1. OpenSees       ops.element('elasticBeamColumn', 18, ...)      el tag es 18
                  ops.eleResponse(18, 'localForce')              12 números
2. Python         semana04/exportar_unity.py                     arma el JSON
3. JSON           semana04.json → casos[..].esfuerzos[id=18]     el id es 18
4. Unity (datos)  JsonUtility → EsfuerzosS4 con id = 18
5. Unity (objeto) GameObject "Elem_18_columna"
                  con el componente DatoElemento.idElemento = 18
6. Capacidad      su sección → familia P-M 0 → curva y punto de demanda
```

**La clave es que es el mismo número en los cuatro lados.** El `18` que
OpenSees usa como tag es el `id` del JSON, es el `idElemento` del componente
que Unity pega a la barra, y está en el nombre del objeto. No hay tabla de
traducción: por eso no se puede desalinear.

**Cómo se demuestra en vivo:**

1. En Unity, clic en la columna 18 (o el botón **Columna demo (18)**). Al
   final del panel, el bloque `--- trazabilidad ---`:

   ```
   OpenSees    element elasticBeamColumn 18 158 263 A=0.2500 E=2.4870e+07 ...
   Unity       GameObject "Elem_18_columna"  DatoElemento.idElemento = 18  OK
   Resultados  semana04.json casos[S3].esfuerzos[id=18].f
               f_i [...]
               f_j [...]
   Seccion     "columna" -> familia P-M 0 (...)
   Modelo      nodos y seccion del anexo calzan con el modelo del visor: OK
   ```

   El `OK` de la línea Unity **lo comprueba Unity en ese momento**, sobre
   el objeto que tocaste: que se llame como dice el JSON y que su
   `DatoElemento` tenga ese id.
2. En la terminal: `python semana04\trazabilidad.py ingenieria 18`
   imprime la misma cadena **desde Python** — la línea de OpenSees, el
   modelo, el objeto de Unity, los resultados y la capacidad — y compara
   cada número con el que Unity lee del JSON. Termina en
   `LA CADENA CALZA`.

**Y cómo se sabe que Unity lee lo que Python escribe:** `JsonUtility`, el
lector de Unity, **no avisa** cuando un campo no calza — lo deja en cero y
sigue. Un momento que se llama distinto en C# y en Python daría un
diagrama plano, sin ningún error. Por eso hay dos pruebas:

- `test_contrato_semana04.py` compara los nombres de los campos en C#
  contra las claves del JSON, **en las dos direcciones**.
- `verificar_unity_semana04.py` abre Unity sin interfaz, le hace leer el
  JSON de verdad, y compara lo que leyó contra lo que Python escribió.
  Termina en `UNITY LEE EL ANEXO DE SEMANA 4 TAL COMO PYTHON LO ESCRIBIO`.

---

## 4. Cómo sale un diagrama de momento

### Lo que da OpenSees

`eleResponse(tag, 'localForce')` da **12 números** por barra: las fuerzas
**sobre** la barra en sus dos extremos, en **ejes locales**:

```
[ N_i  Vy_i  Vz_i  T_i  My_i  Mz_i   N_j  Vy_j  Vz_j  T_j  My_j  Mz_j ]
```

**Por qué `localForce` y no `eleForce`:** `eleForce` los da en ejes
**globales**. Para una viga que corre en Y, su momento de gravedad caería
en la casilla "Mx global" y se leería como torsión. (Fue un error real de
la Semana 1.)

### Lo que falta: el medio de la barra

OpenSees da los extremos. Una viga con carga repartida tiene el momento
máximo **en el medio**, y ahí no hay dato. Se reconstruye cortando la barra
en un punto `x` y haciendo equilibrio del pedazo de la izquierda:

```
N(x)  = −(N_i  + wx·x)
Vy(x) = −(Vy_i + wy·x)
Vz(x) = −(Vz_i + wz·x)
T(x)  = −T_i
My(x) = −(My_i + x·Vz_i + wz·x²/2)
Mz(x) = −(Mz_i − x·Vy_i − wy·x²/2)
```

`w = (wx, wy, wz)` es la carga repartida en ejes locales. Se calcula en 9
puntos si la barra tiene carga repartida (el momento es una parábola), y en
2 si no (es una recta). N positivo es tracción.

Esa misma `w` viaja en el anexo y se puede **dibujar sobre la barra**, con
las magnitudes `wy` y `wz`: la causa al lado del efecto. El bloque [1] exige
que la `w` escrita sea la combinación de las de los casos base, o sea la
misma que usan estas fórmulas para cerrar contra `f_j`.

### Por qué se sabe que está bien — la frase de la defensa

> **Se reconstruye desde el extremo *i* y se exige llegar exactamente al
> extremo *j* que calculó OpenSees.**

Si la fórmula, el signo o el eje de la carga estuvieran mal, al llegar a
`x = L` no daría el `f_j` de OpenSees. En Ingeniería son **60 372
comparaciones** (9 casos × 559 elementos × 6 esfuerzos × 2 extremos), y
todas caen dentro de su cota (`verificar_semana04.py`, bloque [1]). Los
peores, medidos contra su propia cota:

| | peor error | su cota | error / cota | dónde |
| --- | --- | --- | --- | --- |
| N, Vy, T | 0 | 2.0e-4 | 0 | — |
| Vz | 2.0e-4 | 2.4e-4 | 0.83 | 1.4G, elemento 368 |
| My | 6.0e-4 | 7.65e-4 | 0.78 | 1.4G, elemento 292 |
| Mz | 4.0e-4 | 5.17e-4 | 0.77 | 1.4G, elemento 46 |

¿Por qué no da cero? **Por el redondeo.** El servidor entrega las fuerzas
con 4 decimales, o sea con un error de hasta `5e-5` cada una. El momento en
`L` suma `My_i`, `L·Vz_i` y `My_j`, así que en un caso base su error puede
llegar a `5e-5·(2 + L)`; en N, V y T, que juntan solo `f_i` y `f_j`, a
`5e-5·2`. En una combinación cada caso entra multiplicado por su factor, así
que la cota se multiplica por `Σ|λ|` (1.4 en `1.4G`). Y como el bloque
compara dos números **ya escritos** en el JSON, cada uno redondeado otra vez
a 4 decimales, suma `2·5e-5`:

```
N, Vy, Vz, T:   5e-5 · 2 · Σ|λ|        + 1e-4
My, Mz:         5e-5 · (2 + L) · Σ|λ|  + 1e-4
```

Esa es la forma correcta de verificar: la tolerancia no se elige, **se
explica por su causa**. Y el exportador lo comprueba antes de escribir: si
una barra no cierra, **no escribe el archivo**.

### Un ejemplo para hacer a mano

Viga simplemente apoyada, `L = 6 m`, carga `w = 10 kN/m` hacia abajo
(`wz = −10`). Cada apoyo empuja hacia arriba con `wL/2 = 30 kN`, así que
`Vz_i = +30` y `My_i = 0`. En el centro, `x = 3`:

```
My(3) = −(0 + 3·30 + (−10)·3²/2) = −(90 − 45) = −45 kN·m
```

Y `wL²/8 = 10·36/8 = 45`. **Coincide, con signo negativo**: en esta
convención el momento que hace "sonreír" a la viga (tracción abajo) es
negativo. El bloque [6] resuelve esta misma viga en OpenSees y da
`My(L/2) = −45.0000`.

---

## 5. De qué lado se dibuja

Un diagrama dibujado al revés **se ve igual de razonable** y está mal. Por
eso la convención no se eligió: se derivó por equilibrio y se comprobó
aparte.

**Se dibuja del lado traccionado**, que es la convención de hormigón
armado: el diagrama queda del lado donde va el fierro que trabaja.

| magnitud | fibra traccionada | la curva se desplaza |
| --- | --- | --- |
| `My > 0` | la de `+z` local | `+My · z_local` |
| `Mz < 0` | la de `+y` local | `−Mz · y_local` |

**Por qué `Mz` lleva signo menos y `My` no:** con la regla de la mano
derecha, los dos momentos positivos no traccionan el mismo lado de su eje:
`My > 0` tracciona la fibra de `+z`; `Mz > 0` tracciona la de `−y`. Para
que los dos queden del lado traccionado, `My` se dibuja hacia `+z_local`
tal cual, y `Mz` con el signo cambiado hacia `+y_local`.

**Cómo se comprobó, sin confiar en la derivación** (bloque [6]): se arma un
voladizo en OpenSees con una **sección de fibras** y se lee la tensión de
las fibras en el empotramiento.

| carga | momento en el empotramiento | fibra en tracción | tensión |
| --- | --- | --- | --- |
| `wz = −q` | `My = +180` | la de `+z` | +12 579.5 kPa |
| `wy = −q` | `Mz = −180` | la de `+y` | +20 965.8 kPa |

Las dos filas son exactamente la tabla de arriba. **Comprobación rápida
con una viga:** en un voladizo con carga hacia abajo, el empotramiento
tiene la fibra de **arriba** traccionada; ahí `My > 0` y `+My · z_local`
apunta hacia arriba. ✔

Corte, axial y torsión no tienen "lado traccionado": se dibujan en una
dirección fija (`Vy` en `y_local`, los demás en `z_local`) y se **colorea
por signo**.

---

## 6. Ejes locales, y el error de los muros

Cada barra tiene sus propios ejes, y los esfuerzos están en ellos:

- **x local** va del nodo *i* al *j*.
- **z local** sale de un vector de referencia, `vecxz`.
- **y local** = z × x.

La regla del `vecxz`, que es la misma en Python y en el servidor:

| barra | `vecxz` | resultado |
| --- | --- | --- |
| vertical (columna) | `(1, 0, 0)` | z local = X global, y local = −Y global |
| horizontal (viga) | `(0, 0, 1)` | z local vertical: la gravedad da `My` y `Vz` |
| muro del LT2 | su normal | la inercia grande queda en `Iz`: el plano es `Mz` |
| muro de Ingeniería | la dirección de su largo | la inercia grande queda en `Iy`: el plano es `My` |

**Una trampa que conviene conocer:** para las barras que no son verticales,
el servidor le pasa las inercias a OpenSees **cruzadas** (`Iy ↔ Iz`). No es
un error: el contrato guarda en `Iz` la inercia de gravedad (`b·h³/12`), y
con z local vertical la flexión de gravedad es alrededor del eje *y*, que
OpenSees resiste con `Iy`. Un muro es vertical, así que sus inercias pasan
**sin cruzar**.

### El error que se encontró esta semana

Hasta la Semana 3, la demanda de **todo** muro tomaba `M = |Mz|`. Se había
comprobado con el muro 9 del LT2 (bajo EY, `Mz = 9661`, `My = 24 kN·m`) y
se dio por regla. **Pero los dos cuerpos modelaron sus muros distinto:** el
LT2 les da como `vecxz` su normal, e Ingeniería la dirección de su largo.

Al escribir la trazabilidad se compararon las inercias que **de verdad
recibe OpenSees**, y los 56 muros de Ingeniería tienen `Iy > Iz`. Su
momento del plano es `My`; el `Mz` que se estaba usando era el de **fuera**
de plano:

| muro 537, bajo EY | `My` | `Mz` |
| --- | --- | --- |
| en el extremo que manda | **30 352.4** | 24.8 |
| lo que decía la Semana 3 | — | 45.7 (se usaba este) |

El informe entregado de la Semana 3 decía que ese muro trabajaba al 0.8 %.
Con el eje correcto trabaja al **2.9 % bajo G** y al **50 % bajo EY**.

**Cómo quedó corregido, y por qué no puede volver:**

- `demanda_capacidad.momento_en_el_plano(Iy, Iz)` elige `My` si `Iy > Iz`
  y `Mz` si no. Es la inercia que resiste cada flexión: la grande es la
  del plano del muro.
- `demanda()` **no tiene valor por defecto** para un muro: sin `plano`
  lanza un error. Un default silencioso fue justo lo que escondió esto.
- El eje viaja en el JSON (`elementos[].momento_en_el_plano`) y Unity lo
  muestra: `M 40969.1 kN*m (|My|, en su plano)`. Unity no lo decide.
- Bloque [8] de `verificar_semana04.py`, **sin mirar las inercias**: bajo
  EX y EY, el momento declarado del plano tiene que ser el mayor de los
  dos. Se cumple en los **96 muros** de los dos cuerpos; el más justo lo
  supera 5.2 veces. Si se fuerza la regla vieja (`Mz`), la prueba falla.

**Cómo contarlo en la defensa:** "La regla estaba comprobada, pero en un
solo edificio. La verificación de esta semana la probó en el otro y no se
cumplía. Ahora el eje sale de las inercias, se prueba con la respuesta de
OpenSees en los 96 muros, y la función no deja pedir la demanda de un muro
sin decir el eje."

**Y el cambio de ejes con Unity:** OpenSees usa Z vertical y Unity usa Y.
`Unity(x, z, y)`. Si el edificio se ve acostado, es esto.

---

## 7. Demanda-capacidad

### La curva P-M

Sale de la **Fiber Section** de `comun/capacidad.py`: la sección cortada en
fibras de hormigón confinado, recubrimiento y acero. Cada punto de la curva
es un análisis momento-curvatura con una compresión fija. Se calcula **en
Python** y viaja al JSON como una lista de puntos; Unity solo la dibuja.

Hay **28 familias** de sección con fierro en Ingeniería, para 138
elementos (82 columnas y 56 muros): se calcula una curva por familia, no
una por elemento. Dos barras con la misma sección y el mismo fierro tienen
la misma curva.

En la ventana: **azul grueso** es `Mn` nominal (hormigón a 0.003),
**celeste fino** el momento máximo del M-φ, **gris** los otros casos y
**rojo** el caso activo.

### El punto de demanda

`(P, M)` sale de los 12 números de `localForce`:

- `P` es la axial, **positiva en compresión**.
- **Columna:** `M = √(My² + Mz²)`, el resultante, porque una columna
  cuadrada con fierro perimetral resiste parecido en cualquier dirección.
- **Muro:** `M` es **solo el de su plano** (§6). Un muro de 0.30 × 16.85 m
  tiene 3 000 veces más inercia en su plano que fuera de él; componer los
  dos diría que aguanta fuera de plano lo mismo que dentro, y es falso.
- Se miran los dos extremos y gana el de mayor momento.

**Utilización** `u = M / Mn`, con `Mn` la capacidad **a ese mismo P**. Si
`u ≤ 1`, el punto cae dentro de la curva. Es **nominal**, sin factores φ.

### Números de referencia (Ingeniería)

| | columna 18 | muro 537 |
| --- | --- | --- |
| sección | 0.50 × 0.50 m | 0.30 × 16.85 m, 182 barras |
| cuantía | 1.29 % | 0.28 % |
| G | P 3385.9, M 34.6, **u 0.089** | P 3250.2, M 2243.1, **u 0.029** |
| EY | P 58.3, M 38.7, u 0.147 | P 283.0, M 30 352.4, **u 0.504** |
| S3 (caso por defecto) | P 3904.8, M 40.6, Mn 355.9, **u 0.114** | P 3884.0, M 5556.4, Mn 82 428.5, **u 0.067** |
| 1.2G+1.0Q+1.4EY | P 5171.4, M 99.6, u 0.439 | P 5237.2, M 40 969.1, Mn 90 780.2, **u 0.451** |

P en kN, M en kN·m. Salen de `data/unity/semana04.json`, y el bloque [5]
comprueba que los de G, Q, EX y EY son los mismos de
`demanda_capacidad.revisar()`.

### Los que no pasan, y por qué

| elemento | caso | qué pasa |
| --- | --- | --- |
| **columna 80** | S3 | `u = 1.226`. Es de **último piso**: poco axial y el momento entero de las vigas del techo. Ya salía en la Semana 3 bajo G + Q (`u = 1.122`). |
| **muro 427** | 1.2G+1.0Q+1.4EX | `P = −3510 kN` de **tracción**, más que la tracción pura de su sección (−1649 kN = fy·As). Con esa axial no queda momento resistente: `Mn = 0` y `u` no se define; el JSON lo marca con `u = 9999`, que es una bandera, no un cociente. |
| **muro 508** | 1.2G+1.0Q+1.4EY | `u = 36`. Muro **corto** (2.35 m) traccionado: `P = −1108 kN`, casi en la tracción pura (−1188), donde la curva ya casi no tiene momento (`Mn = 105`), y el sismo le pide 3814 kN·m. |

En total, en Ingeniería no pasan **10** demandas en S3 y **36** en
`1.2G+1.0Q+1.4EY`. Bajo cargas de gravedad solas no pasa ningún muro.

**Qué quiere decir esto, sin exagerar:** es capacidad nominal contra un
sismo con coeficiente supuesto (`Cs = 0.10`) repartido en un modelo
elástico. De los 13 muros que no pasan en `1.2G+1.0Q+1.4EY`, 7 están
traccionados (entre ellos los cuatro de 2.35 m) y 6 comprimidos. Lo que
muestra es **dónde** mirar: muros que el sismo tracciona o carga más
—varios de ellos cortos— y columnas del techo con un detalle típico. No es un diseño.

### Qué quiere decir "caso activo"

La demanda depende de qué carga se está mirando. En Unity hay **un solo
caso activo**, y cambia a la vez los esfuerzos del panel, los diagramas, el
punto sobre la curva y la deformada. El nombre del caso aparece en el
título de la ventana P-M — `P-M elemento 537 (muro) caso activo:
1.2G+1.0Q+1.4EY` —: así queda **identificado**, que es lo que pide el
enunciado.

---

## 8. Casos y combinaciones

Casos base: **G** (peso propio y losa), **Q** (sobrecarga, NCh1537: 3.0
kN/m², salas de clases), **EX** y **EY** (sismo). Combinaciones, de
`semana03/parametros.json`:

| nombre | fórmula |
| --- | --- |
| S3 | 1.0 G + 0.5 Q + 1.0 EX |
| 1.4G | 1.4 G |
| 1.2G+1.6Q | 1.2 G + 1.6 Q |
| 1.2G+1.0Q+1.4EX | 1.2 G + 1.0 Q + 1.4 EX |
| 1.2G+1.0Q+1.4EY | 1.2 G + 1.0 Q + 1.4 EY |

**Se combinan en Python, sumando.** Esfuerzos, desplazamientos y cargas se
multiplican por su factor y se suman. Vale porque el modelo es **lineal
elástico** (`K·u = F` con `K` fija): la respuesta a una suma de cargas es la
suma de las respuestas.

**Y se comprobó** (bloque [3]): `1.2G+1.0Q+1.4EX` se resuelve **de verdad**
en OpenSees, con las cargas ya combinadas, y se compara con la suma. Fuerzas
y desplazamientos calzan dentro del redondeo (el peor, 0.957 de su cota).

**La curva P-M, en cambio, no se combina**: es no lineal. Por eso lo que se
combina es la **demanda**, y la capacidad se lee de la curva.

---

## 9. Material, sección y restricciones

**Material.** Hormigón con `Ec = 4700·√f'c` en MPa. Ingeniería usa
`f'c = 28 MPa`, así que `Ec = 24 870 MPa` y `G = E / 2.4 = 10 363 MPa`
(ν = 0.2). Los tubos de acero del voladizo traen su propio `E`. **El E que
muestra el panel es el que usa OpenSees:** el bloque [4] toma el axial de
OpenSees de 455 barras y comprueba que es `E·A/L` por el alargamiento, con
el E y el A del panel.

**Restricciones.** Cada nodo tiene 6 grados de libertad: `[ux uy uz rx ry
rz]`, con `1` = restringido. Un empotramiento es `[1 1 1 1 1 1]`. Se
muestran como lista, no como "se ve empotrado".

**El `[0 0 1 1 1 0]` de algunos nodos del nivel 1:** ese nivel está a la
cota −4.01 y, donde no hay subterráneo debajo, la losa se apoya en el
terreno. Se restringen `uz`, `rx` y `ry`; `ux`, `uy` y `rz` los maneja el
diafragma — si se fijaran también, el piso entero quedaría inmóvil.

**Diafragma rígido.** Los nodos de cada losa quedan atados a un nodo
maestro: el piso se traslada y gira como un cuerpo. **El nodo maestro no es
un apoyo** aunque tenga restricciones (las de fuera del plano, que el
diafragma no toca).

**Brazos rígidos.** Un muro se modela como una barra en su eje, más brazos
muy rígidos hasta sus caras. Sus esfuerzos existen pero son un artificio
numérico: no se diseña con ellos, y no se les dibuja diagrama.

---

## 10. Preguntas de defensa

**¿Unity calcula algo?**
No. Recibe los esfuerzos, las combinaciones y las curvas ya calculadas en
Python, y los dibuja. Ver §2.

**¿De dónde sale el momento en el medio de la viga, si OpenSees da los
extremos?**
Se reconstruye por equilibrio desde el extremo *i* con la carga repartida.
Y se verifica: llega al *j* de OpenSees en todos los elementos. Ver §4.

**¿Por qué el error no es cero?**
Porque el servidor redondea las fuerzas a 4 decimales y el JSON vuelve a
redondear. La cota sale de esa causa —en los momentos
`5e-5·(2 + L)·Σ|λ| + 1e-4`— y cada una de las 60 372 comparaciones cae
dentro de la suya. Ver §4.

**¿Cómo sabes que el diagrama está del lado correcto?**
Se derivó por equilibrio y se comprobó con una sección de fibras en
OpenSees: con `My > 0` la fibra de `+z` está en tracción. Ver §5.

**¿Por qué una viga se mira en My?**
Porque su z local es vertical (`vecxz = (0,0,1)`): la gravedad la flecta
alrededor de *y*, y eso es `My`. Ver §6.

**¿Y un muro?**
En el momento de su plano, que es el del eje de **inercia mayor**: `My` en
Ingeniería, `Mz` en el LT2. Ver §6.

**¿Qué error encontraron esta semana?**
Que la demanda de los muros de Ingeniería usaba el momento de fuera de
plano, por una regla (`Mz`) comprobada solo en el LT2. Cómo se encontró,
cómo se corrigió y la prueba que impide que vuelva: §6.

**¿Por qué la demanda de un muro no es el momento resultante?**
Porque fuera de su plano el muro es mucho menos rígido y resistente: su
inercia fuera de plano es entre 35 y casi 6 000 veces menor según el muro
(3 155 en el 537), y la curva P-M del anexo es la del plano fuerte.
Componer los dos momentos lo compararía contra esa curva y diría que
resiste fuera de plano lo que resiste dentro.

**¿Qué significa u = 9999?**
Que el `P` de la demanda cae fuera de la curva (en estos casos, tracción
mayor que la tracción pura): `Mn = 0` y el cociente no existe. Es una
bandera. El bloque [7] comprueba que todo 9999 tenga de verdad un `P`
fuera de la curva, y al revés.

**¿El muro 508 con u = 36 es un error del programa?**
No: es un muro corto traccionado por el sismo, con `P` casi en la tracción
pura, donde la curva casi no tiene momento. El número es grande porque `Mn`
es chico. Es nominal y con un sismo supuesto: dice dónde mirar. Ver §7.

**¿Qué pasa si un campo del JSON se llama distinto en C#?**
Nada visible: `JsonUtility` lo deja en cero y sigue. Por eso hay un test de
contrato en las dos direcciones y otro que hace leer el JSON a Unity de
verdad. Ver §3.

**¿Por qué las combinaciones se pueden sumar y la curva P-M no?**
El modelo es lineal y la sección no: la curva sale de un análisis no lineal
de fibras. Se suma la demanda; la capacidad se lee. Ver §8.

**¿Y si el profesor cambia el coeficiente sísmico?**
`python semana04\exportar_unity.py ingenieria --cs 0.20` regenera todo
—casos, combinaciones, esfuerzos, demandas— con ese valor, y el visor lo
muestra. Los parámetros usados quedan escritos en el JSON.

**Demuestra que el objeto que tocaste es el elemento 18 de OpenSees.**
Clic en la barra → panel de trazabilidad: el nombre del objeto, su
`DatoElemento`, la línea de OpenSees con el tag 18 y el `OK` de Unity.
Luego `python semana04\trazabilidad.py ingenieria 18` muestra los mismos
números desde Python. Ver §3.

---

## 11. Lo que queda abierto (y conviene saber)

- **Resuelto — muro 10 del LT2 y el `f'c` del conjunto.** La curva con
  `Mn = 0` en `P = 0` venía de leer mal el plano: `L:8+8` son las
  *laterales* de la viga de fundación, no fierro de muro, y quedaban
  amontonadas en un borde. Y el conjunto ahora sella `fpc_MPa` por
  sección, así que el LT2 saca sus curvas con 35 MPa. El bloque [7] calza
  en `ingenieria`, `lt2` y `conjunto`, y la suite corre los tres.
- **Fierro de muro del LT2, contado de menos.** En los bloques de barra de
  las elevaciones el número que dibuja el plano (`5 Ø32 L=900`) es el
  atributo `NUM`; el extractor lee `CANT`, que es invisible y vale `1`.
  Pasa en 660 de 780 bloques: los 29 muros armados llevan 181 barras de
  borde donde el plano da 411. Del lado seguro (el `Mn` a `P = 0` del
  muro 12 sube 97 %), pero los números de capacidad de esos muros no son
  los del plano.
- **Barras que no son del muro, pegadas como borde (LT2).** De esas 181
  asignaciones, 36 son barras horizontales (dinteles bajo losa, vigas de
  fundación) y 30 vienen de la elevación perpendicular; 22 bloques entran
  en dos muros. Del lado **inseguro**: quitándolas, el `Mn` baja hasta
  33 % (muro 16).
- **Puntas de muro de Ingeniería.** Las `L:3+3 Ø10` que se ponen en las
  dos puntas de los 56 muros son las laterales de las vigas `V. 60/80`:
  la lámina 2017_67-000 dice `L:` = LATERALES, igual que la del LT2. En el
  muro 537 pesan 7 % del `Mn` a `P = 0`; en los muros cortos, 42 %. El
  plano dibuja en las puntas otras barras contadas (`2 Ø22`, `2 Ø18`).
- **La curva P-M es de un solo signo.** `capacidad.interaccion()` flecta
  hacia un lado y la demanda usa `|M|`. En una sección con el acero
  descentrado la capacidad cambia con el signo (20 a 36 % en varios muros
  del LT2), y para uno de los dos queda del lado inseguro. Parte de esa
  asimetría es de los dos puntos de arriba y de que la malla no queda
  centrada en `_seccion_de_muro`.
- **Los M 0.60x2.92 del LT2 (eje A') van sin fierro.** El plano les da
  cuatro mallas y núcleos de borde de Ø32, en texto suelto y en cortes que
  el extractor no lee; no entran a la revisión P-M.
