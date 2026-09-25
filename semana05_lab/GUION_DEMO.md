# LAB Semana 5 — Guion de la demostración

Dura **unos 10 minutos** y está ordenado por los cinco criterios de la
rúbrica, para que cada bloque sume a la vista del profesor. Cada uno dice
**qué hacer**, **qué se ve** y **qué decir**.

Hazla completa dos veces antes, en voz alta. El edificio es el **LT2**.

> **El orden importa.** Los sliders, la P-M y el mapa D/C usan el anexo
> del modelo **original**. En cuanto se borra una barra (M1) el anexo
> queda marcado como desactualizado y no hay vuelta atrás sin reabrir la
> app. Por eso las modificaciones que cambian `K` van **al final**.

---

## La noche anterior (una vez)

```powershell
python comun\verificar_todo.py               # 44 de 44 EN OK; tarda 2 a 8 min, reexporta anexos y abre Unity en batch
```

No la corras cinco minutos antes: reexporta y deja el LT2 en
StreamingAssets, pero tarda. Con Unity cerrado.

## Antes de que llegue el profesor (5 min)

```powershell
python comun\lanzar_unity.py sincronizar lt2   # deja el LT2 en StreamingAssets (232 nodos, 378 elementos)
python semana05\servidor_s5.py                 # terminal aparte, se deja abierta
python comun\lanzar_unity.py app lt2
```

El servidor no hace falta para los sliders instantáneos ni para el mapa
D/C, pero sí para el caso **LIBRE** (la referencia de Python) y para el
reanálisis del criterio 2. Déjalo prendido: arranca en 2 s y precalienta
la base de los cuatro casos al partir.

Deja una **segunda terminal** en la carpeta del repo: se usa al final.

---

## 1. Interactividad — 2 pts (2 min)

**Qué hacer**, en este orden:

1. **Navegar**: arrastrar para orbitar, rueda para acercar, `F` para
   encuadrar todo, `C` para centrar la selección.
2. **Seleccionar**: clic en una viga → se abre la pestaña **Elemento**
   con su ID, nodos, sección, material, ejes locales y esfuerzos.
3. **Capas**: pestaña **Capas** → prender y apagar apoyos, ejes locales,
   áreas tributarias, diafragmas.
4. **Cambiar combinación**: pestaña **Caso** → *Casos del anexo (Semana
   4)* → apretar `1.2G+1.6Q`.
5. **Respuesta combinada**: con esa combinación puesta, prender la
   deformada y los diagramas.
6. **Demanda-capacidad**: apretar **Columna demo (5)** (abajo de la
   pestaña Caso) → en **Elemento**, la curva P-M de la columna con su
   punto de demanda. Volver a **Caso** y desplegar *Mapa demanda /
   capacidad*: el edificio pintado por `u = M/Mn`.

> "Todo lo que se ve viene de un JSON que calculó Python. El visor no
> resuelve nada: dibuja, filtra y pregunta."

---

## 2. Superposición en Unity — 2 pts (2 min)

**Qué hacer:** pestaña **Caso** → sección **Superposicion (Semana 5)** →
bajar el panel hasta el bloque **`--- Superposicion INSTANTANEA en Unity
(Semana 5) ---`**. Está **debajo** de *Factores libres (servidor
Python)*, que tiene otros cuatro sliders (`lambda G = …`): esos son los
del servidor, no estos. Los instantáneos se llaman `G`, `Q`, `EX`, `EY`
y tienen debajo los botones `E1`, `E2`, `E3` y `todo en cero`.

Mover `EX` de un lado a otro. Después `G`.

**Qué se ve:** la deformada, los diagramas y el mapa D/C se mueven
**mientras arrastras**, sin esperar nada. La cabecera cambia (`Desp. max`,
`NO PASA n/69`). La última línea del bloque dice en cuántos milisegundos
combinó, con cuántas barras y nodos, y cuántas combinaciones van.

**Qué decir:**

> "El modelo es lineal y elástico, así que la respuesta a una suma de
> cargas es la suma de las respuestas. Los cuatro casos base ya los
> resolvió OpenSees; el visor solo los escala y los suma —y rehace la
> demanda, que no es lineal—. No está resolviendo la estructura: eso se
> hace una vez, en Python. Tarda entre uno y cuatro milisegundos."

**Si preguntan cómo saben que no miente:** apretar **`E3
1.2G+1.0Q-1.4EX`** en los sliders instantáneos y mirar la cabecera:
`24.63 mm`, `NO PASA 4/69 (1 fuera de curva)`. Subir hasta *Estados de la
entrega* y apretar **`E3`** (precalculado por Python): la misma cabecera.
El mismo caso por dos caminos.

---

## 3. Demanda-capacidad dinámica — 2 pts (2 min)

**Qué hacer:** con la **Columna demo (5)** seleccionada, en la pestaña
**Caso** desplegar **Curva P-M** (está justo debajo de los sliders
instantáneos). Mover `EX` de 0 a 1.4 y de vuelta; después `G` hacia
negativo.

**Qué se ve:** el punto rojo **recorre la curva**: con `EX` se corre en
momento; con `G` negativo la columna pasa a **tracción** y el punto baja
del eje. Cambian `Mn`, `u = M/Mn` y el `PASA / NO PASA`. Con *Mapa
demanda / capacidad* desplegado, el edificio se repinta y el conteo de
la cabecera cambia.

**Qué decir:**

> "La demanda-capacidad **no** es lineal, así que no se suma: se rehace.
> Del vector de fuerzas ya combinado salen P y M —mirando los dos
> extremos y quedándose con el de mayor momento— y `Mn` se interpola en
> la curva P-M, que la calculó Python con una sección de fibras. Lo único
> que hace Unity es la aritmética, y está comprobada contra Python."

**Un detalle que conviene soltar:** en un muro no se usa el momento
resultante sino solo el de **su plano**, porque fuera de plano la
capacidad es órdenes de magnitud menor. Cuál de los dos es se decide por
las inercias, y viaja en el JSON. **Muro demo (9)** lo muestra.

**Si preguntan por el `NO PASA 4/69`:** los cuatro son **muros** (14, 15,
16 y 29 en E3; el 16 con `u = 9999`, que quiere decir que `P` cayó fuera
del rango de su curva). Las **40 columnas del LT2 pasan en los 15 casos**.
La armadura de esos muros no está completa en los planos que tenemos —o
viene en texto y cortes que el extractor no lee—, así que su `Mn` sale
con menos fierro del que probablemente hay. Está registrado en
`AGENTS.md` (Semana 4: el atributo `CANT` vale 1 en 660 de 780 bloques;
los M 0.60x2.92 van sin fierro). El NO PASA marca **dónde falta
información**, no que el muro falle; y por eso se muestra en vez de
esconderse.

---

## 4. Modificación del modelo — 2 pts (2 min)

El enunciado pide **al menos dos** de las seis. Hay **cuatro**, dos en
vivo y dos por comando. Cada una viene con la pregunta *¿esto necesita
reanálisis?*, que es lo que el criterio 5 premia.

**M3 — sección, en vivo:** pestaña **Elemento** → `Ir a ID` 337 →
*Elemento* (la viga queda seleccionada) → pestaña **Modificar** →
*Cambiar sección* → `V 0.30x0.80` → *"Recalcular en el servidor
(Enter)"* → de vuelta en **Elemento**, `Ir a ID` 186 → *Nodo*.

**Qué se ve:** la cabecera avisa que el modelo se editó; el servidor
devuelve los cuatro casos del modelo nuevo con la tabla de equilibrio;
el `UZ` del nodo 186 pasa de −3.6452 a −3.6092 mm.

> Este camino desde la app se ejerció **por script** (`reanalisis_demo.py
> --seccion`, en la suite), no en una captura: **ensáyalo una vez** antes.
> Si algo se traba, la M1 de abajo está fotografiada (21–22) y la M3 sale
> igual por comando: `python semana05\reanalisis_demo.py lt2 --seccion 337
> "V 0.30x0.80" --nodo 186`.

> "Cambió `K`: hay que reanalizar. Y ojo: la carga aplicada **no**
> cambió aunque la viga sea la mitad, porque el peso propio viene sumado
> en las cargas del modelo. Está declarado, no escondido."

**M1 — desactivar un elemento, en vivo:** **Modificar** → seleccionar la
columna **69** → *Borrar barra* → *Recalcular*. Queda 377 elementos, la
tabla de equilibrio cierra (`Fz −34 148.98 / 34 148.98`).

> "Cambió `K` otra vez: reanálisis obligatorio."

**M2 — intensidad de carga (dato) y M4 — apoyo**, por comando si preguntan
por más de la lista:

```powershell
python semana05\comparar_anexos.py lt2 --cs 0.20
python semana05\reanalisis_demo.py lt2 --apoyo 2 1 1 1 0 0 0 --nodo 186
```

**Y aquí viene la pregunta que ellos quieren oír, con la M2:** *"Subí el
coeficiente sísmico de 0.10 a 0.20. ¿Necesita reanálisis?"*

> "**No.** `F_i = Cs·W_i·patrón_i` es proporcional a `Cs`, así que
> `EX(0.20)` es exactamente `2·EX(0.10)`: es el slider en `λEX = 2`.
> Lo rehacemos en Python igual, y que dé lo mismo a un paso de redondeo
> —`1e-8 m`, `1e-4 kN`— es la **prueba** de que el modelo es lineal.
> Lo que sí sería otro caso base es cambiar `q` o el patrón en altura,
> porque cambian la forma de las fuerzas piso a piso."

La M4 suelta el empotramiento del nodo 2 a rótula: el `UX` bajo EX pasa
de 16.315 a 16.353 mm. Cambia `K`: reanálisis.

---

## 5. Defensa y criterios de reanálisis — 2 pts (2 min)

La pregunta es *¿cuándo hay que volver a resolver?* La respuesta sale de
`K·u = F`, y el matiz que vale puntos es el tercero:

| si cambia… | ¿reanálisis? | por qué |
| --- | --- | --- |
| los factores λ | **no** | `K` es la misma; es superposición |
| todo un caso (Q ×1.5), o `Cs` | **no** | es `λQ = 1.5`, o `λEX = Cs′/Cs` |
| `q` o el patrón en altura | **sí** | otra **forma** de `F`: ningún caso base la tiene |
| la carga de **una** viga | **sí** | no hay un caso base resuelto para eso |
| sección, apoyo, un elemento | **sí** | cambia `K`: lo guardado es de otra estructura |
| el material, **uniforme** | para los esfuerzos **no** | `K → αK`: `u → u/α`, esfuerzos y reacciones iguales |
| una sección con fierro | **sí**, y rehacer su curva P-M | la capacidad no sale de `K·u = F` |

La tabla completa, con los números que la respaldan y los límites
declarados del reanálisis, está en
[`CRITERIOS_REANALISIS.md`](CRITERIOS_REANALISIS.md).

**Cerrar con la verificación**, en la segunda terminal:

```powershell
python semana05_lab\verificar_instantanea.py lt2 --registro semana05\capturas\registro.txt
```

> "Termina en *lo que Unity combinó al mover los sliders es lo de
> Python*. Hace dos cosas: repite el algoritmo del visor en Python, con
> su aritmética de 32 bits, sobre diez juegos de factores —negativos y
> el nulo incluidos—; y cruza contra Python los números que **la app
> real** escribió al mover los sliders: desplazamientos, fuerzas,
> `P`, `M`, `Mn`, el extremo que manda, pasa/no pasa y los conteos de la
> cabecera. Cada tolerancia sale del redondeo del JSON y de los redondeos
> de 32 bits contados, no de un número elegido a ojo."

---

## Si preguntan por el sidequest (SQ4)

Está a medias, y conviene decirlo así: la **carga móvil existe** —
pestaña *Carga movil*, 30 posiciones resueltas en OpenSees sobre el eje
de vigas 203–208, con reparto y conservación verificados— pero **no sigue
al usuario**. Lo que falta es tomar la posición del usuario, encontrar el
panel de losa que la contiene y resaltar sus vigas receptoras. Los datos
están (`areas_tributarias`, 243 áreas con sus polígonos y su viga
dueña); el trabajo no está hecho.

---

## Si algo sale mal en vivo

| síntoma | causa | qué hacer |
| --- | --- | --- |
| no encuentro los sliders instantáneos | están al **final** de *Superposicion (Semana 5)*, debajo de *Factores libres* | bajar el panel; el bloque se llama `--- Superposicion INSTANTANEA en Unity ---` |
| moví el slider y no pasa nada | es el slider equivocado (`lambda G = …` es el de LIBRE, que espera al servidor) | usar los de abajo, `G`, `Q`, `EX`, `EY` |
| LIBRE dice que no hay servidor | falta `servidor_s5.py` | los sliders instantáneos **sí** funcionan sin él |
| la cabecera dice "modelo editado" | quedó una M1 o M3 de una prueba anterior | reabrir la app (el anexo es del modelo original) |
| el panel dice "el anexo es de otro modelo", o `sincronizar` avisa "OJO: semana04.json no se copio (es de 'conjunto')" | los anexos en `data/unity/` son de otro edificio | `python comun\lanzar_unity.py preparar lt2` (reexporta y copia) y reabrir |
