# Semana 4 — Guion de la demostración

Dura **unos 10 minutos**. Está ordenado como la rúbrica, para que cada
bloque sume puntos a la vista del profesor. Cada bloque dice **qué hacer**,
**qué se ve** y **qué decir**. Los rótulos entre comillas son los de la app.

Hazla completa dos veces antes, en voz alta. Las capturas de
[`capturas/`](capturas/) muestran lo que se debería ver en cada paso.

---

## Antes de que llegue el profesor (5 min)

En una terminal, desde la carpeta del repo:

```powershell
python comun\verificar_todo.py
```

Tiene que terminar en `N de N EN OK`. Si algo falla, **no improvises**: la
salida dice qué script y por qué.

```powershell
python semana04\exportar_unity.py ingenieria
python semana03\exportar_unity.py ingenieria
python comun\lanzar_unity.py editor ingenieria
```

Los dos exportadores tienen que ser del **mismo** edificio que abre el
lanzador. El de la Semana 4 se comprueba: si no calza, el panel avisa que
el anexo es de otro modelo y no dibuja diagramas. El de la Semana 3 no se
comprueba, así que se exportan siempre juntos.

Unity abre → `Assets/Scenes/SampleScene` → **Play**.

Deja una **segunda terminal** abierta en la carpeta del repo: se usa en el
bloque 5.

---

## 1. Resultados conectados — 3 pts (3 min)

**Qué hacer:** en el panel de la izquierda, sección `--- Semana 4 ---`,
botón **"Columna demo (18)"**. La cámara va a la columna y queda
seleccionada.

**Qué se ve** (panel, bajando):

- `ELEMENTO  18`, con su tipo, sección y los nodos `158` y `263`
- `--- ejes locales (OpenSees) ---` con `local x`, `local y`, `local z`
- `=========== SEMANA 4 ===========`
  - `--- material ---`: f'c 28 MPa, E 24 870 MPa, G 10 363 MPa, ν 0.20
  - `--- seccion ---`: A, J, Iy, Iz
  - `--- condiciones [ux uy uz rx ry rz] ---`: la restricción de cada
    nodo y su diafragma
  - `--- esfuerzos, caso activo S3 ---`: N, Vy, Vz, T, My, Mz en el
    extremo *i* y en el *j*, con `*` en los que mandan para una columna,
    y el máximo de cada momento con su `x`
  - `--- demanda / capacidad ---` y `--- trazabilidad ---` (bloques 4 y 5)

**Qué decir:**

> "Al hacer clic en la barra, Unity muestra los resultados de OpenSees de
> ese elemento, del caso activo: S3, que es 1.0 G + 0.5 Q + 1.0 EX. La
> tabla son los esfuerzos internos en *i* y en *j*, en ejes locales, que
> salen de los doce de `localForce`; los doce tal cual están abajo, en
> trazabilidad. Unity no calcula nada; los lee del JSON que arma Python."

**Si comparan la tabla con `f_i`:** en el extremo *i* tienen el signo
cambiado. `f` son las fuerzas que los nodos le hacen a la barra; la tabla
es el esfuerzo interno, con N positivo en tracción. En *j* coinciden.

**Cambiar de caso:** botones `G`, `Q`, `EX`, `EY` y las combinaciones, en
la misma sección. El activo lleva `>` delante. El panel cambia sus números
en el momento.

**Si preguntan por un `[0 0 1 1 1 0]` en un nodo del nivel 1:** es el
apoyo en el terreno. Ese nivel está a la cota −4.01 y, donde no hay
subterráneo debajo, la losa se apoya en el suelo. Se restringen `uz`, `rx`
y `ry`; `ux`, `uy` y `rz` los maneja el diafragma: si se fijaran también,
el piso entero quedaría inmóvil.

---

## 2. Diagramas y deformada — 2 pts (2 min)

**Diagrama de momento:**

1. Toggle **"Diagramas de esfuerzos"** prendido, magnitud **`My`**.
2. **"todas las visibles"**, y con el filtro de piso (`+` junto a
   "Todos", arriba) baja a `Piso: 2`. Se lee mejor que el edificio
   entero.
3. Debajo aparece la leyenda: de qué lado se dibuja y cuántos kN·m son
   los 2 m de dibujo. **Los muros tienen escala aparte**: toman momentos
   mucho mayores (en el piso 2, en S3, unas siete veces), y con una sola
   escala las vigas quedarían de centímetros.

**Qué decir:**

> "Es el diagrama de momento de las vigas del piso, dibujado del lado
> traccionado. OpenSees da los extremos; lo del medio se reconstruye por
> equilibrio con la carga repartida, y se verificó que llega al extremo *j*
> de OpenSees en todos los elementos: el error es el redondeo de 4
> decimales del servidor. El lado se comprobó con una sección de fibras."

**Una viga con su parábola:** la **222**, una viga del techo. Filtro de
piso con `+` hasta `Piso: 5` (cota +19,80), capa **IDs** prendida, clic en
la barra 222 y **"la seleccionada"**, en S3. Salen las etiquetas `My i = 278.4 kN*m` y
`My j = 505.0 kN*m` (si el máximo cae en el tramo, sale una tercera con su
`x`): los extremos arriba —tracción arriba, sobre el apoyo— y el tramo
abajo.

**Diagrama de corte o axial:** magnitud **`Vz`** (corte de gravedad) o
**`N`** (axial). El color dice el signo: azul positivo, rojo negativo; en
`N`, positivo es tracción.

**Deformada:** en la sección `--- deformada ---`, botón **"Caso activo
(S4): ..."**. Elige `1.2G+1.0Q+1.4EY` en la sección Semana 4 y la deformada
cambia con él. La escala es solo gráfica.

> "La deformada sale del mismo caso activo que los diagramas y el panel: si
> elijo una combinación, los desplazamientos ya vienen combinados desde
> Python."

---

## 3. Capas estructurales — 2 pts (1 min)

Prender y apagar, una a la vez:

| capa | dónde | qué decir |
| --- | --- | --- |
| **Apoyos** | toggles de arriba | cubos verdes en los nodos con restricciones |
| **Areas tributarias** | toggles de arriba | el polígono de losa que carga cada viga |
| **Flechas de carga** | primero, en `--- deformada ---`, **"Sismo EX"** (sin una deformada de sismo puesta no se dibujan); después, sección Semana 3, `G` `Q` `EX` `EY` | las cargas de cada caso, al costado del edificio |
| **Ejes locales** | toggles de arriba | rojo x, verde y, azul z |
| **Diafragmas** | toggles de arriba | el nodo maestro de cada losa |
| **Diagramas** | sección Semana 4 | los de arriba |

> "Cada capa se prende sola y viene del mismo JSON: nada de esto se dibuja
> a mano."

Al terminar, vuelve la deformada a **"Caso activo (S4)"**.

---

## 4. Demanda-capacidad — 1 pt (2 min)

1. Botón **`S3`** en la sección Semana 4 (el caso activo quedó en otra
   combinación) y **"Columna demo (18)"**, con **"Curva P-M de la
   seleccionada (ventana)"** prendido. El título dice `P-M elemento 18 (columna) caso
   activo: S3`. Abajo: `Mn(P) = 355.9 kN*m  u = M/Mn = 0.114  PASA`.
2. Cambia el caso con los botones: **el punto rojo se mueve**; los grises
   son los otros casos.
3. **"Muro demo (537)"**: la misma ventana con la curva del muro. En S3
   la ventana dice `M = 5556.4 kN*m`, `u = M/Mn = 0.067` y
   `M = |My|, el de su plano`; el panel, `M 5556.4 kN*m (|My|, en su
   plano)`. Con `1.2G+1.0Q+1.4EY`, `M = 40969.1` y `u = M/Mn = 0.451`.

**Qué decir:**

> "La curva sale de la sección de fibras, con el fierro que se leyó del
> plano. El punto rojo es la demanda `(P, M)` del caso activo, sacada de
> `localForce`. En la columna, M es el resultante; en el muro, solo el de su
> plano, que en este edificio es `My`."

**La historia que hay que contar (30 s):**

> "Hasta la semana pasada la demanda de muro tomaba siempre `Mz`, porque
> así era en el LT2. Al verificar la trazabilidad comparamos las inercias
> que recibe OpenSees y en Ingeniería los muros tienen la grande en `Iy`:
> estábamos comparando el momento de fuera de plano. Ahora el eje sale de
> las inercias, y una prueba confirma con la respuesta de OpenSees que es
> el mayor bajo sismo en los 96 muros."

**Si hay tiempo, los que no pasan** (clic en la barra, o el id con los
IDs prendidos):

- **Columna 80** en S3: el punto queda **fuera**, `u 1.226  NO PASA`. Es de
  último piso: poco axial y mucho momento de las vigas del techo, sobre un
  detalle típico igual para las 82 columnas.
- **Muro 427** en `1.2G+1.0Q+1.4EX`: `P fuera de la curva: traccion 3510 kN
  mayor que la traccion pura 1649 kN. NO PASA (u no definido)`.
- **Muro 508** en `1.2G+1.0Q+1.4EY`: `u 36.326  NO PASA`. Muro corto
  (2.35 m) traccionado casi hasta la tracción pura, donde la curva ya no
  tiene momento.

> "Es capacidad nominal, sin factores φ, con un sismo supuesto: muestra
> dónde mirar, no es un diseño."

---

## 5. Trazabilidad — 2 pts (2 min)

**En Unity**, botón **`S3`** y **"Columna demo (18)"**; el final del
panel:

```
--- trazabilidad ---
OpenSees    element elasticBeamColumn 18 158 263 A=0.2500 E=2.4870e+07 ...
Unity       GameObject "Elem_18_columna"  DatoElemento.idElemento = 18  OK
Resultados  semana04.json casos[S3].esfuerzos[id=18].f
            f_i [...]
            f_j [...]
Seccion     "columna" -> familia P-M 0 (...)
Modelo      nodos y seccion del anexo calzan con el modelo del visor: OK
```

**Qué decir:**

> "El 18 es el mismo número en los cuatro lados: el tag de OpenSees, el id
> del JSON, el componente `DatoElemento` que Unity le pega a la barra, y el
> nombre del objeto. El OK lo comprueba Unity en este momento, sobre el
> objeto que toqué."

**En la segunda terminal:**

```powershell
python semana04\trazabilidad.py ingenieria 18
python semana04\trazabilidad.py ingenieria 537 --caso 1.2G+1.0Q+1.4EY
```

> "Y desde Python, la misma cadena: la línea de OpenSees, el modelo, el
> objeto de Unity, los `f_i` y `f_j`, la sección y la demanda. Compara cada
> número con lo que Unity lee del JSON y termina en `LA CADENA CALZA`."

**Si preguntan cómo se sabe que Unity lee bien el JSON:** `JsonUtility` no
avisa cuando un campo no calza — lo deja en cero. Por eso hay dos pruebas:
el test de contrato en las dos direcciones, y otra que abre Unity sin
interfaz y le hace leer el archivo de verdad. Las dos están en la suite.

---

## Si algo sale mal en vivo

| síntoma | causa | qué hacer |
| --- | --- | --- |
| el panel de Semana 4 dice "El anexo es de otro modelo" y no hay diagramas | se abrió otro edificio: **el lanzador sin argumento abre el LT2** | cerrar, `python comun\lanzar_unity.py editor ingenieria` y Play; el lanzador avisa cuando los anexos son de otro edificio |
| la sección Semana 4 muestra un AVISO de que falta `semana04.json` y no tiene botones | no se exportó el anexo | lo mismo |
| **no existe la sección `--- Semana 4 ---`** en el panel, y tampoco el botón "Caso activo (S4)" | ese repositorio no tiene la Semana 4: está en `main` o en una rama sin el merge | `git fetch origin` y `git checkout ingenieria-semana03`; reabrir Unity, esperar el import y Play. Definitivo: mergear el PR |
| el panel se corta antes de llegar a la sección Semana 4 | la ventana es chica: los controles de Semana 4 van al final del panel | rueda del mouse con el cursor **encima** del panel; o maximizar la Game view (Shift+Espacio) |
| no se ve el diagrama | toggle apagado, o "la seleccionada" sin barra elegida | prender y hacer clic en una barra |
| el diagrama de un muro no se ve | el de `My` va en su plano, dentro del muro | mirar las etiquetas y la ventana P-M |
| la ventana P-M no abre | la barra no tiene fierro (viga, brazo) | elegir columna o muro |
| todo magenta | shader | Unity abierto sobre otro pipeline: cerrar y abrir con el lanzador |
