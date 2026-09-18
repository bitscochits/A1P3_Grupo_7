# Semana 5 — Guion de la demostración

Dura **unos 16 minutos**, más 5 de preparación. Está ordenado por criterio
de la rúbrica (20 pts). Cada bloque dice **cuánto dura**, **qué hacer**,
**qué se ve**, **qué decir** y **qué hacer si algo sale mal**. Los rótulos
entre comillas son los de la app, que no lleva tildes.

Los números vienen de la captura automática del 17-09
(`semana05/capturas/registro.txt`, comparada con Python en
`evidencia/unity_vs_python.txt`: 486 filas, 0 FALLA) y de los scripts que
se nombran al lado. Las fotos de [`capturas/`](capturas/) muestran lo que
se debería ver en cada paso.

**Orden en vivo.** La modificación (bloque 4) va **después** de la
superposición y de la carga móvil, aunque en la rúbrica esté antes. Borrar
la columna 69 deja desactualizados el anexo, E1..E3 y la carga móvil, y la
única forma de recuperarlos es cerrar y abrir la app.

Hazla completa dos veces antes, en voz alta.

---

## 0. Antes de que llegue el profesor (5 min)

Unity y la app cerrados. En una terminal, desde la carpeta del repo:

```powershell
.\.venv\Scripts\python.exe comun\verificar_todo.py
```

Tiene que terminar en `41 de 41 EN OK` (entre 2 y 8 min el 17-09). Si algo falla,
**no improvises**: la salida dice qué script falló y por qué.

```powershell
.\.venv\Scripts\python.exe comun\lanzar_unity.py sincronizar lt2     # resumen: igual 12
```

En una **segunda terminal**, que queda abierta toda la demo:

```powershell
.\.venv\Scripts\python.exe semana05\servidor_s5.py
```

Espera a que arme la base del LT2 (unos 2 s). Después, en la primera:

```powershell
Invoke-RestMethod http://localhost:5000/ping      # estado: vivo
.\.venv\Scripts\python.exe comun\lanzar_unity.py app lt2
```

Deja Excel cerrado y una **tercera terminal** libre para el bloque 4 (M2).

**Si algo sale mal:**

- La app dice "Sin modelo cargado": repite `sincronizar lt2`.
- La cabecera avisa que el anexo es "de otro modelo": alguien exportó otro
  edificio. Corre `semana04\exportar_unity.py lt2`,
  `semana03\exportar_unity.py lt2` y `sincronizar lt2`, y abre la app de
  nuevo.
- El puerto 5000 está ocupado: `netstat -ano | findstr :5000` muestra el
  PID. Cierra ese proceso (o usa `--puerto 5057` y cambia la URL en
  Modificar y en Superposicion).

---

## 1. Viewer estructural — 5 pts (5 min)

### 1a. Vista general y navegación (1 min)

**Qué hacer:** nada, la app abre así. Arrastrar orbita, el botón derecho
mueve, la rueda hace zoom y **F** encuadra. En **Vista**, "Tecnica" y
después "Realista".

**Qué se ve** (fotos 01 y 02): cabecera `LT2 232 nodos, 378 elementos`,
`Caso activo S3 1.00 G + 0.50 Q + 1.00 EX`, `Desp. max 19.78 mm` y
`NO PASA 2/69` en rojo. El edificio aparece con losas por piso, columnas y
vigas con su sección (la columna en salmón), y el pasto a la cota −7.97,
al pie de las columnas. La técnica es la vista de trabajo de siempre, con
la columna azul.

**Qué decir:**

> "Es el LT2 desde sus planos: 232 nodos y 378 elementos. Lo que se ve
> arriba es el caso activo, que manda sobre todo el panel. El suelo está a
> −7.97, que es donde arrancan las columnas: ahí están los 16 apoyos. Va
> declarado en el perfil del edificio y solo dibuja. Las losas también son
> dibujo: son los polígonos de área tributaria que ya usa la carga."

### 1b. ¿Dónde está? (1 min)

**Qué hacer:** pestaña **Elemento** → "Ir a ID" `5` → "Elemento" → "Su
piso".

**Qué se ve** (foto 09): la columna 5 con aristas cian, sola en su piso,
con los apoyos verdes. En "Identificacion y ubicacion": `tipo columna`,
`seccion P 0.70x0.70`, `nodos 5 -> 21`, `largo 3.960 m`, `nodo 5 (32.35,
18.18, -7.97) APOYO [1 1 1 1 1 1] empotrado` y `piso cota -7.97 m, nivel 1
de 6`.

**Qué decir:** "Selecciono por clic o por id. El panel da los nodos, las
coordenadas de OpenSees y en qué piso está. 'Su piso' deja solo ese nivel."

### 1c. ¿Cómo está apoyado? (0.5 min)

**Qué hacer:** en la misma sección, botón "Nodo 5".

**Qué se ve** (foto 10): `Nodo 5` con `EMPOTRADO` en verde,
`[ux uy uz rx ry rz] = [1 1 1 1 1 1] (fijo)`, "Empotrado: los 6 grados de
libertad restringidos" y "Fuera de todo diafragma: se mueve solo con sus
barras". El cubo verde es el símbolo del empotramiento. En **Capas** →
"Control de calidad" está la leyenda: cubo empotrado, placa en terreno
`[0 0 1 1 1 0]`, rombo para otra combinación y esfera para el maestro de
diafragma. El LT2 tiene 16 empotramientos y ningún apoyo en terreno.

### 1d. ¿Qué lo carga? (1 min)

**Qué hacer:** **Caso** → "Casos del anexo (Semana 4)" → `G`. **Elemento**
→ "Ir a ID" `92` → "Elemento" → "Que lo carga (losa, peso propio y total en G)".

**Qué se ve** (foto 11): `A_trib 12.500 m2 (1 entrada(s), 2 pano(s))`,
`q_G 6.30 kN/m2 de losa -> 78.75 kN`, `w_losa 15.749 kN/m`, `w_pp 12.000
kN/m de peso propio de la barra`, `= w_G 27.749 kN/m, la w total que
recibe OpenSees en G`, `wz en G -27.749` y `Q wz -12.258 kN/m`. El paño
tributario sale en naranjo sobre la losa. Con "Diagramas de esfuerzos" y
`wz`, el diagrama dice `wz = -27.7 kN/m`. La cabecera dice `PASAN 69/69`.

**Qué decir:**

> "La viga recibe 12.5 m² de losa. A 6.30 kN/m² son 78.75 kN, repartidos
> en 5 m: 15.749 kN/m. Más el peso propio de la viga, 0.60 por 0.80 por 25,
> que son 12.000 kN/m, dan los 27.749 que recibe `beamUniform` y que dice
> el diagrama. Los tres números los escribe Python, leídos de lo que el
> modelo le pasó a OpenSees; Unity no suma nada."

### 1e. ¿Cómo se deforma? (0.5 min)

**Qué hacer:** **Caso** → `S3` y, en "Deformada", "Caso activo: S3".
**Elemento** → "Ir a ID" `207` → "Nodo".

**Qué se ve** (foto 12): la deformada ×300, con los muros inclinados y
continuos, y la posición original en líneas oscuras. "Desplazamiento, caso
activo S3": `ux 18.190 mm`, `uy -0.919 mm`, `uz -7.705 mm` y las tres
rotaciones.

**Qué decir:** "El nodo 207 está en el techo. En S3 se va 18 mm en x, que
es el sentido del sismo. La escala ×300 es solo gráfica: el número es el
de OpenSees."

### 1f. ¿Qué fuerzas tiene? (0.5 min)

**Qué hacer:** "Ir a ID" `92` → "Elemento". En **Caso** → "Diagramas",
magnitud `My` y "la seleccionada".

**Qué se ve** (foto 13): el diagrama de My en azul y naranjo, y la tabla
`extremo i / extremo j`: `Vz 216.14 / 373.63`, `T 17.66 / 17.66`,
`My -562.78 / 911.65`, con `*` en los que mandan en una viga_x. Abajo:
`max |My| = 911.65 kN*m en x = 5.00 m (9 estaciones)` y `wz -31.499 kN/m`.

**Qué decir:** "Los extremos salen de `localForce` y el medio se
reconstruye por equilibrio. El exportador exige llegar al extremo *j* de
OpenSees, y si una barra no cierra no escribe el archivo."

### 1g. ¿Cuánta capacidad tiene? (0.5 min)

**Qué hacer:** **Caso** → `1.2G+1.0Q+1.4EX`. **Elemento** → "Ir a ID" `5`
→ "Demanda / capacidad" y "Curva P-M". Después **Caso** → "Mapa demanda /
capacidad" → "Pintar el edificio por u (caso activo)".

**Qué se ve** (fotos 14 y 14b): `P 6301.0 kN M 374.0 kN*m extremo i
(inferior)`, `Mn 1748.4 kN*m u 0.214 PASA`, la curva P-M con el punto rojo
del caso activo y `estribo EØ12a10`. En el mapa: `NO PASA 4/69 (1 fuera de
curva)` con 64 verdes, 1 amarillo, 3 rojos, 1 morado y 309 grises (sin
fierro). En "Criticos del caso activo" están el 28 (fuera de curva), el 12
(u 2.228), el 29 (2.130) y el 45 (1.214).

**Qué decir:** "u es M sobre Mn a ese P, nominal y sin φ, calculado en
Python. Unity solo pinta. Los que no pasan son muros interiores. Con 'Ir'
voy a cada uno."

**Si algo sale mal (bloque 1):**

- No se ve la selección: puede estar en otro piso. Usa "Todos los pisos"
  y "Centrar (C)".
- No hay diagrama: con deformada, carga móvil o mapa D/C las losas se
  esconden, pero el diagrama necesita "Diagramas de esfuerzos" prendido y
  un caso del anexo activo.
- Los números del panel no calzan con esta guía: mira el caso activo en
  la cabecera. Cada número es del caso activo.

---

## 2. Superposición y demanda-capacidad — 4 pts (3 min)

**Qué hacer:** **Caso** → "Superposicion (Semana 5)" → `E1`, `E2`, `E3`.

**Qué se ve** (fotos 15-17):

| estado | cabecera | equilibrio (aplicada, kN) |
| --- | --- | --- |
| E1 = 1.00 G + 1.00 Q | `Desp. max 8.79 mm`, `PASAN 69/69` | Fz −41696.66 |
| E2 = 1.20 G + 1.60 Q | `Desp. max 11.34 mm`, `PASAN 69/69` | Fz −53055.07 |
| E3 = 1.20 G + 1.00 Q − 1.40 EX | `Desp. max 24.63 mm`, `NO PASA 4/69 (1 fuera de curva)` | [−5309.20, 0.00, −48526.46] |

El texto de origen dice "precalculado por semana05/superposicion.py
(StreamingAssets/superposicion.json), sin servidor". En E3 el error de
equilibrio es `[0.0002, -0.0003, -0.0003]`. No pasan el 16 (fuera de
curva), el 15 (u 1.462), el 14 (1.230) y el 29 (1.077).

**Qué hacer después:** "Factores libres (servidor Python)" → "Conectar
(GET /estados)". Los sliders a G 1.20, Q 1.00, EX −1.40 y EY 0.

**Qué se ve** (foto 18): `Caso activo LIBRE 1.20 G + 1.00 Q - 1.40 EX`,
los mismos 24.63 mm y 4/69. El origen dice "combinado por
semana05/servidor_s5.py (Python, POST http://localhost:5000/combinar) ...
en 0.24 s".

Ahora mueve EX a **+1.40**. Python da 27.2455 mm y `NO PASA 4/69 (1 fuera
de curva)` con los elementos 12, 28, 29 y 45
(`superposicion.py lt2 --lambdas 1.2 1.0 1.4 0`), lo mismo que el caso
`1.2G+1.0Q+1.4EX` del anexo.

**Qué decir:**

> "Unity no suma nada. Los desplazamientos y los esfuerzos sí son lineales
> en λ, pero la demanda-capacidad no: cambia el extremo que manda, M de
> una columna es la raíz de My² + Mz², y Mn depende de P. Por eso la D/C se
> rehace entera en Python con los esfuerzos combinados. Se ve con el signo
> del sismo: con −1.4 EX fallan el 14, el 15, el 16 y el 29, y con +1.4 EX
> el 12, el 28, el 29 y el 45. E1..E3 se verificaron contra una corrida
> explícita de OpenSees con la carga combinada
> (`verificar_superposicion.py`): en E3, 24.6285 mm superpuesto contra
> 24.6286 mm explícito."

**Si algo sale mal:**

- "Conectar" no responde: mira la terminal del servidor y el ping. Sin
  servidor, E1..E3 siguen funcionando. Muestra la foto 18 y la salida de
  `superposicion.py lt2 --lambdas 1.2 1.0 -1.4 0`.
- El primer pedido tarda: la primera vez arma la base (unos 2 s). Después
  cada combinación toma centésimas.
- Aviso "sus parametros no son los de semana04.json": el anexo y la
  superposición se exportaron con distinto `--cs`. Vuelve a la base
  (`COMANDOS.md` §5).

---

## 3. QA / UX — 3 pts (3 min)

### 3a. El panel y el Excel (1 min)

**Qué hacer:** recorre las pestañas Vista, Capas, Caso, Elemento,
Modificar y Carga movil (fotos 03-08). Aprieta "Abrir Excel de resultados".
En Excel, hoja **Reacciones**, filtra "Cuenta en Fx/Fy" = sí.

**Qué se ve:** un solo panel con cabecera fija. Excel abre
`resultados.xlsx` con 10 hojas: LEEME, Resumen, Nodos, Desplazamientos,
Elementos, Esfuerzos, Reacciones, Demanda-capacidad, Curvas P-M y
Supuestos.

**Qué decir:** "Las seis preguntas se contestan en la pestaña Elemento, y
la evaluación con capturas está en `semana05/UX.md`. El Excel está
versionado en `data/excel/` y dice lo mismo que Python celda a celda
(`test_excel.py`). Ojo con la hoja Reacciones: sumar la columna entera
dobla el corte basal. En EX, la suma filtrada da −3792.28 kN y la columna
entera −7584.56. Por eso trae las columnas 'Cuenta en'."

### 3b. Carga móvil (1.5 min)

**Qué hacer:** pestaña **Carga movil** → "Mostrar la carga movil". Mueve
el slider a "Posicion 13 de 30" y después "Play".

**Qué se ve** (fotos 19 y 20): `P = 100 kN hacia abajo, 30 posiciones.
cota 3.91, eje y = 18.18: vigas 203, 204, 205, 206, 207, 208, del nodo 101
al 122 (27.72 m)`. En la posición 13: `Viga 205, xL = 0.50 (a = 2.50 de
L = 5.00 m)`, `V_i nodo 102 77.60 kN (77.6 %)` y `V_j nodo 116 22.40 kN
(22.4 %)`. La cabecera dice "Carga movil · posicion 13/30 · x = 24.85 m ·
P = 100 kN" y "UZ max -0.490 mm (nodo 116)". La conservación da ΣRz = 100 kN, error 0, contra una cota de
8.0e-4 kN.

**Qué decir:**

> "Cada posición es una corrida de OpenSees hecha en Python, y Unity salta
> de una a otra sin interpolar. La carga está al centro de la viga 205,
> pero el reparto no es 50/50 porque la viga es continua: 50 kN salen por
> palanca y los momentos de extremo agregan 27.60 kN al lado del nodo 102.
> Las reacciones suman P con la regla de `calcular.equilibrio`."

### 3c. Realismo y lectura (0.5 min)

**Qué decir:** "Pedro pidió realismo. Hay texturas procedurales, suelo
sin collider y losas de dibujo. Mientras el mapa D/C está prendido el suelo
pasa a neutro para que el verde se lea. Las fricciones que quedan están
anotadas en `UX.md`, por ejemplo que 'Ir a ID' no se sincroniza con la
selección."

**Si algo sale mal:**

- Excel no abre: `Invoke-Item data\excel\lt2_resultados.xlsx` desde la
  terminal. Si "No existe el archivo", `sincronizar lt2`.
- La pestaña Carga movil dice que se apagó: ya se hizo la M1. Cierra y
  abre la app.

---

## 4. Modificación y reanálisis — 4 pts (4 min)

### 4a. M1: borrar la columna 69 desde Unity (2 min)

**Qué hacer:**

1. **Elemento** → "Ir a ID" `186` → "Nodo". **Modificar** → "Recalcular
   en el servidor (Enter)". Queda `OK: 4 caso(s) [G, Q, EX, EY]` y, con
   `G`, el nodo 186 muestra `UZ -3.6452 mm`.
2. "Ir a ID" `69` → "Elemento" (columna P 0.70x0.70, nodos 144 → 186).
   **Modificar** → "Borrar barra  (Supr)" → "Recalcular en el servidor
   (Enter)".

**Qué se ve** (fotos 21 y 22): la cabecera pasa a `377 elementos`, dice
"Reanalisis del servidor (modelo editado) · caso G", "Max. componente 21.60 mm" y
"D/C: sin recalcular (anexo del modelo original)", y muestra una sola línea
de aviso: "Modelo editado (borrar elemento 69). Mostrando el reanalisis del
servidor...". Aparece `OK: 4 caso(s) [G, Q, EX, EY] en 3.1 s`, `Max. componente 21.5988 mm`, y la tabla "Equilibrio de G
(calcular.equilibrio)" con `Fz aplicada -34148.98`, `reaccion 34148.98` y
`error -0.0002`, marcada "Confiable. 216 nodo(s) en diafragma". El nodo 186
queda en `UZ -21.5988 mm`. La deformada G muestra el techo que se hunde
sobre la columna que falta.

**Qué decir:**

> "Unity manda el modelo editado por JSON a Flask, OpenSees lo resuelve y
> Python devuelve desplazamientos, fuerzas y el equilibrio calculado con
> la regla por grado de libertad. El UZ del 186 pasa de −3.6 a −21.6 mm, y
> el máximo en G de 6.7 a 21.6 mm, 3.22 veces. La carga aplicada no cambia:
> los 48.51 kN de peso propio de la columna borrada siguen como carga nodal,
> porque el peso va horneado en las cargas. Es una limitación declarada.
> El anexo de la Semana 4 queda marcado como del modelo original. El
> servidor también escribió `results/excel/reanalisis_lt2.xlsx`."

Botón "Abrir Excel de este reanalisis" si hay tiempo.

**Si algo sale mal:**

- "Recalcular" falla o dice Curl error: el servidor no está. Mira la
  terminal 2 y "Probar conexion". Muestra las fotos 21-22 y corre
  `reanalisis_demo.py lt2 --borrar-elemento 69 --nodo 186 --elemento 337`
  (termina en `TODO OK` con los mismos números).
- HTTP 400: el servidor rechazó el modelo. Lo más probable es que se
  haya arrastrado un nodo por accidente fuera del plano de su diafragma
  (lo advirtió la auditoría y no se reprodujo en Play). Cierra y abre la
  app, y vuelve a empezar la M1.

### 4b. M2: coeficiente sísmico 0.10 → 0.20, por dato (2 min)

**Qué hacer:** cierra la app. En la tercera terminal:

```powershell
.\.venv\Scripts\python.exe semana04\exportar_unity.py lt2 --cs 0.20
.\.venv\Scripts\python.exe semana03\exportar_unity.py lt2 --cs 0.20
.\.venv\Scripts\python.exe semana05\superposicion.py lt2 --cs 0.20 --exportar
.\.venv\Scripts\python.exe comun\lanzar_unity.py app lt2
```

En la app: **Caso** → `S3` → "Columna demo (5)". Después `EY` → "Muro
demo (9)".

**Qué se ve** (salida de `comparar_anexos.py lt2 --cs 0.20`, 17-09):

| | antes (Cs 0.10) | después (Cs 0.20) |
| --- | --- | --- |
| corte basal V = Cs·W | 3792.28 kN | 7584.56 kN (×2.0000) |
| columna 5, S3 | P 4860.3, M 267.7, u 0.152 PASA | P 4889.6, M 521.1, u 0.296 PASA |
| muro 9, EY | P −479.1, M 9661.1, u 0.635 PASA | P −958.2, M 19322.2, u 1.479 **NO PASA** |

**Qué decir:** "El sismo lo dicta el profesor. Cambiar el dato pasa por el
mismo camino: parámetros, casos en OpenSees, anexo y Unity. G y Q no
cambian, EX y EY se duplican dentro del redondeo del servidor
(`comparar_anexos.py` lo comprueba con cota medida), y el muro 9 pasa a no cumplir en
EY porque su axial baja (tracción) y el momento se duplica."

**Al terminar la demo, volver a la base** (`COMANDOS.md` §5).

**Si algo sale mal:** si no hay tiempo para reabrir la app, corre solo
`comparar_anexos.py lt2 --cs 0.20`. No escribe nada, tarda unos 5 s e
imprime la tabla de arriba y el texto que mostraría el panel.

---

## 5. Preparación móvil, IA y gestión — 4 pts (1 min)

**Qué hacer:** en la terminal:

```powershell
.\.venv\Scripts\python.exe comun\lanzar_unity.py android lt2 --seco
```

En la app: **Vista** → "Tamano del texto y equipo".

**Qué se ve:** `ERROR: El editor de Unity no tiene el modulo para android
(falta PlaybackEngines/AndroidPlayer). No se abrio Unity ni se copio nada.`,
con salida 1. En la app se ven el equipo, la GPU, la RAM, la pantalla, el
dpi y la escala del panel (1600×900 a 120 dpi, escala 1.25 en la
captura).

**Qué decir:**

> "Pedro decidió Windows primero y dejar el móvil al final, sin instalar
> Android, así que el build móvil no se hizo. Lo que sí quedó es el código
> preparado: la lectura de StreamingAssets con UnityWebRequest (en Android
> vive dentro del APK), la cámara táctil, la escala por DPI y los métodos
> de build Web y Android. Este último avisa si falta el módulo en vez de
> romper. Los requisitos de Unity 6.5 y cómo revisar un teléfono están en
> `semana05/MOVIL.md`. El uso de IA de la semana está registrado en
> `AGENTS.md`, y el trabajo está en la rama `semana05`."

**Si algo sale mal:** nada que pueda fallar en vivo. Si preguntan por un
teléfono concreto, muestra la tabla "por llenar" de `MOVIL.md` y los
comandos `adb` para completarla.

---

## Cinco respuestas cortas

- **¿Unity calcula algo?** No. Lee los JSON de Python o las respuestas del
  servidor. Ni la superposición, ni la D/C, ni el reparto de la carga
  móvil, ni el equilibrio se calculan en C#.
- **¿Cómo saben que lo que muestra Unity es lo que calculó Python?**
  `CapturaSemana05` escribe lo que Unity tiene en memoria (float32
  exacto) y `comparar_unity.py` lo cruza con Python: 486 filas, 0 FALLA.
  Cada tolerancia es la suma de causas medidas (float32, impresión y el
  redondeo del servidor).
- **¿Por qué −7.97 para el terreno?** Ninguna lámina rotula el N.T.N., así
  que no se supone: se mide en el modelo. En −7.97 están los 16 apoyos del
  LT2 y de ahí arrancan 8 columnas y 8 muros; bajo esa cota no hay ni un
  nodo. Va declarado en el perfil y solo mueve el dibujo. En la entrega
  decía −4.01 (`provisorio`), para leer ese piso como subterráneo: si lo
  fuera, al modelo le faltaría el empotramiento lateral del terreno ahí
  (su deriva en EX, 0.00048, es menor que la de los pisos de arriba,
  0.00107). Pendiente: el terreno tiene dos N.R. (−7.97 y −4.01), y el
  visor dibuja un solo plano, así que los 39 apoyos en terreno de
  Ingeniería quedan 3.96 m sobre el suelo.
- **¿Por qué la hoja Reacciones no se suma entera?** Porque un nodo de
  diafragma reacciona también a su restricción. Sumarlo todo dobla el
  corte basal.
- **¿Qué pasa con el anexo después de editar?** Queda marcado como del
  modelo original, y la cabecera lo dice en una línea. Rehacerlo exige
  llevar la edición a `data/modelo/` y reexportar.
