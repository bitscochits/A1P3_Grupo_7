# LAB Semana 5 — Guion de la demostración

Dura **unos 10 minutos** y está ordenado por los cinco criterios de la
rúbrica, para que cada bloque sume a la vista del profesor. Cada uno dice
**qué hacer**, **qué se ve** y **qué decir**.

Hazla completa dos veces antes, en voz alta. El edificio es el **LT2**.

---

## Antes de que llegue el profesor (5 min)

```powershell
python comun\verificar_todo.py               # tiene que terminar en N de N EN OK
python comun\lanzar_unity.py sincronizar lt2
python semana05\servidor_s5.py               # terminal aparte, se deja abierta
python comun\lanzar_unity.py app lt2
```

El servidor no hace falta para los sliders ni para el mapa D/C, pero sí
para el caso **LIBRE** (la referencia de Python) y para el reanálisis del
criterio 2. Déjalo prendido.

Deja una **segunda terminal** en la carpeta del repo: se usa al final.

---

## 1. Interactividad — 2 pts (2 min)

**Qué hacer**, en este orden:

1. **Navegar**: arrastrar para orbitar, rueda para acercar, `F` para
   encuadrar todo.
2. **Seleccionar**: clic en una viga → se abre la pestaña **Elemento**
   con su ID, nodos, sección, material, ejes locales y esfuerzos.
3. **Capas**: pestaña **Capas** → prender y apagar apoyos, ejes locales,
   áreas tributarias, diafragmas.
4. **Cambiar combinación**: pestaña **Caso** → apretar `1.2G+1.6Q`.
5. **Respuesta combinada**: con esa combinación puesta, prender la
   deformada y los diagramas.
6. **Demanda-capacidad**: en **Elemento**, la curva P-M de la barra
   seleccionada, con su punto de demanda.

> "Todo lo que se ve viene de un JSON que calculó Python. El visor no
> resuelve nada: dibuja, filtra y pregunta."

---

## 2. Modificación del modelo — 2 pts (2 min)

El enunciado pide **al menos dos** de las seis. Hay **cuatro**, y las
cuatro se repiten con un comando.

**M1 — desactivar un elemento** (en vivo, interfaz): pestaña
**Modificar** → seleccionar la columna **69** → borrar → *"Recalcular en
el servidor (Enter)"*.

**Qué se ve:** la cabecera avisa que el modelo se editó; el servidor
devuelve los cuatro casos del modelo nuevo, con la tabla de equilibrio; el
`UZ` del nodo 186 cambia.

**M2 — intensidad de carga** (dato):

```powershell
python semana05\comparar_anexos.py lt2 --cs 0.20
```

> "El sismo pasa de `Cs = 0.10` a `0.20`. No toco Unity: cambio el dato,
> Python rehace los casos y el visor los lee."

**M3 — sección** y **M4 — apoyo**, si preguntan por más de la lista:

```powershell
python semana05\reanalisis_demo.py lt2 --seccion 337 "V 0.30x0.80" --nodo 186
python semana05\reanalisis_demo.py lt2 --apoyo 2 1 1 1 0 0 0 --nodo 186
```

La primera cambia la viga 337 de `V 0.60x0.80` a `V 0.30x0.80`: el `UZ`
del nodo 186 pasa de −3.6452 a −3.6092 mm. La segunda suelta el
empotramiento del nodo 2 a rótula: el `UX` bajo EX pasa de 16.315 a
16.353 mm. Las dos imprimen el antes y el después, comprueban que el
equilibrio siga cerrando, y **no escriben nada**.

**Dato que conviene soltar en M3:** la carga aplicada **no** cambia, aunque
la viga sea la mitad. El peso propio viene sumado en las cargas del
modelo, así que cambiar la sección desde la app mueve `K` pero no su
peso. Está declarado, no escondido.

**Y aquí viene la pregunta que ellos quieren oír:** *¿esto necesita
reanálisis?* Las dos sí, y por razones distintas: M1 cambia `K` (hay una
barra menos) y M2 cambia `F` (es otro caso base). Ninguna de las dos se
puede resolver escalando lo que ya estaba.

---

## 3. Superposición en Unity — 2 pts (2 min)

**Qué hacer:** pestaña **Caso** → sección **Superposición** → bajar hasta
los cuatro sliders **λG, λQ, λEX, λEY**. Moverlos.

**Qué se ve:** la deformada, los diagramas y el punto P-M se mueven
**mientras arrastras el slider**, sin esperar nada. Abajo dice en cuántos
milisegundos combinó y con cuántas barras y nodos.

**Qué decir:**

> "El modelo es lineal y elástico, así que la respuesta a una suma de
> cargas es la suma de las respuestas. Los cuatro casos base ya los
> resolvió OpenSees; el visor solo los escala y los suma. No está
> resolviendo la estructura: eso se hace una vez, en Python."

**Si preguntan cómo saben que no miente:** apretar *"Combinar en
Python"* con los mismos factores. El servidor devuelve el mismo caso.

---

## 4. Demanda-capacidad dinámica — 2 pts (2 min)

**Qué hacer:** con una columna seleccionada y su curva P-M a la vista,
mover `λEX` de 0 a 1.4.

**Qué se ve:** el punto rojo **recorre la curva**: sube en compresión y
se corre en momento. Cambian `Mn`, `u = M/Mn` y el `PASA / NO PASA`.
Prender el **Mapa D/C**: el edificio se repinta y el conteo cambia.

**Qué decir:**

> "La demanda-capacidad **no** es lineal, así que no se suma: se rehace.
> Del vector de fuerzas ya combinado salen P y M —mirando los dos
> extremos y quedándose con el de mayor momento— y `Mn` se interpola en
> la curva P-M, que la calculó Python con una sección de fibras. Lo único
> que hace Unity es la aritmética."

**Un detalle que conviene soltar:** en un muro no se usa el momento
resultante sino solo el de **su plano**, porque fuera de plano la
capacidad es órdenes de magnitud menor. Cuál de los dos es se decide por
las inercias, y viaja en el JSON.

---

## 5. Defensa y criterios de reanálisis — 2 pts (2 min)

La pregunta es *¿cuándo hay que volver a resolver?* La respuesta sale de
`K·u = F`:

| si cambia… | ¿reanálisis? | por qué |
| --- | --- | --- |
| los factores λ | **no** | `K` es la misma; es superposición |
| todo un caso (Q ×1.5) | **no** | es `λQ = 1.5` |
| la carga de **una** viga | **sí** | no hay un caso base resuelto para eso |
| sección, material, apoyo, un elemento | **sí** | cambia `K`: lo guardado es de otra estructura |
| una sección | **sí**, y además rehacer su curva P-M | la capacidad no sale de `K·u = F` |

La tabla completa, con las nueve filas y los dos límites declarados del
reanálisis, está en
[`CRITERIOS_REANALISIS.md`](CRITERIOS_REANALISIS.md).

**Cerrar con la verificación**, en la segunda terminal:

```powershell
python semana05_lab\verificar_instantanea.py lt2
```

> "Termina en *la combinación de Unity es la de Python*. Prueba diez
> juegos de factores, incluidos negativos y el nulo, y compara
> desplazamientos, las doce fuerzas, los esfuerzos a lo largo de la
> barra, P, M, Mn, el extremo que manda y el pasa/no pasa. Cada
> tolerancia sale del redondeo con que se escribe el JSON, no de un
> número elegido a ojo."

---

## Si preguntan por el sidequest (SQ4)

Está a medias, y conviene decirlo así: la **carga móvil existe** —
pestaña *Carga movil*, 30 posiciones resueltas en OpenSees sobre el eje
de vigas 203–208, con reparto y conservación verificados— pero **no sigue
al usuario**. Lo que falta es tomar la posición del usuario, encontrar el
panel de losa que la contiene y resaltar sus vigas receptoras. Los datos
están (`areas_tributarias`, 243 polígonos con su viga dueña); el trabajo
no está hecho.

---

## Si algo sale mal en vivo

| síntoma | causa | qué hacer |
| --- | --- | --- |
| los sliders no aparecen | la sección **Superposición** está plegada | desplegarla; están al final |
| LIBRE dice que no hay servidor | falta `servidor_s5.py` | los sliders instantáneos **sí** funcionan sin él |
| la cabecera dice "modelo editado" | quedó la M1 de una prueba anterior | reabrir la app |
| el panel dice "el anexo es de otro modelo" | se sincronizó otro edificio | `python comun\lanzar_unity.py sincronizar lt2` y reabrir |
