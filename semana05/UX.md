# Semana 5 — UX estructural: las seis preguntas del visor

El punto 5 del enunciado pide que el visor conteste seis preguntas sobre
cualquier elemento: **dónde está, cómo está apoyado, qué lo carga, cómo se
deforma, qué fuerzas tiene y cuánta capacidad tiene**. Acá se evalúa cada
una con la captura que la muestra, un veredicto y la fricción que todavía
queda.

**De dónde sale la evaluación.** Las 23 fotos de [`capturas/`](capturas/)
las tomó `build/LaboratorioEstructural.exe -capturarS5` el 17-09
(10:10-10:12) sin intervención y con el servidor prendido. El edificio es
el LT2, a 1600×900 y 120 dpi, con el panel a escala 1.25 y 500 px de ancho
(`registro.txt`: `panel.rect`). Las fotos se miraron una por una después
de los arreglos del corrector visual. Lo que el panel **escribe** no se
evalúa a ojo: `comparar_unity.py` lo cruza con Python y el bloque [4]
(preguntas) da 58 filas, 0 FALLA (`evidencia/unity_vs_python.txt`).

Veredictos: **se contesta** (el panel y el 3D lo dejan claro), **se
contesta con fricción** (el dato está y es correcto, pero algo de la
pantalla estorba) y **no se contesta**.

---

## 1. Resumen

| pregunta | dónde se contesta | captura | veredicto | fricción que queda |
| --- | --- | --- | --- | --- |
| ¿Dónde está? | Elemento → "Identificacion y ubicacion"; aristas cian; "Su piso"; "Centrar (C)" | `capturas/09_donde_esta_columna_5.jpg` | Se contesta | "Ir a ID" no se sincroniza con la selección; tabla alineada con espacios en fuente proporcional |
| ¿Cómo está apoyado? | Nodo → "Como esta apoyado" y "Diafragma"; símbolo por tipo; leyenda en Capas | `capturas/10_como_esta_apoyado_nodo_5.jpg` | Se contesta | La columna demo se ve como jaula negra de enfierradura; el LT2 no tiene apoyos en terreno, así que su símbolo no aparece |
| ¿Qué lo carga? | Elemento → "Que lo carga (losa, peso propio y total en G)"; paño en naranjo; diagrama `wz` | `capturas/11_que_lo_carga_viga_92_area_tributaria_y_w_G.jpg` | Se contesta | Ninguna de dato: `w_losa 15.749` + `w_pp 12.000` = `w_G 27.749 kN/m`, los tres escritos y los tres de Python; etiquetas 3D sin fondo |
| ¿Cómo se deforma? | Nodo → "Desplazamiento, caso activo"; deformada con posición original en líneas oscuras | `capturas/12_como_se_deforma_S3_nodo_207.jpg` | Se contesta | El marcador del nodo seleccionado casi no se ve en la vista general; las losas se esconden con la deformada |
| ¿Qué fuerzas tiene? | Elemento → "Esfuerzos, caso activo" (tabla i/j con `*`); diagrama 3D | `capturas/13_que_fuerzas_tiene_viga_92_My_S3.jpg` | Se contesta | Etiquetas `My i` / `My j` grises, grandes y sin fondo sobre el hormigón |
| ¿Cuánta capacidad tiene? | Elemento → "Demanda / capacidad" y "Curva P-M"; Caso → mapa D/C y críticos | `capturas/14_capacidad_columna_5_PM_y_mapa_DC_1.2G+1.0Q+1.4EX.jpg`, `capturas/14b_mapa_DC_leyenda_y_criticos_1.2G+1.0Q+1.4EX.jpg` | Se contesta con fricción | Los 4 que NO PASA son interiores y los tapan muros verdes: se llega por la lista de críticos, no mirando |

**Veredicto general.** Las seis preguntas se contestan con números salidos
de Python, en un solo lugar (pestaña Elemento) y para el caso activo que
dice la cabecera. Frente a la Semana 4, el 3D ahora acompaña: se ve la
sección real, el piso y la selección. Las dos fricciones que más pesan
son de lectura, no de dato: los críticos del mapa, que no se ven desde
afuera, y "Ir a ID", que no sigue a la selección. La carga de la viga
(15.749 contra 27.7) y la cabecera durante la M1 y la carga móvil se
arreglaron al cierre (§6): el bloque escribe losa, peso propio y total, y
la cabecera nombra la fuente de lo que se ve.

---

## 2. Pregunta por pregunta

### 2.1 ¿Dónde está? — `capturas/09_donde_esta_columna_5.jpg`

**Panel:** `Elemento 5` `PASA`, `columna P 0.70x0.70`, y en
"Identificacion y ubicacion": `nodos 5 -> 21`, `largo 3.960 m`, `nodo 5
(32.35, 18.18, -7.97) APOYO [1 1 1 1 1 1] empotrado`, `nodo 21 (32.35,
18.18, -4.01)` y `piso cota -7.97 m, nivel 1 de 6 contando desde abajo (su
nodo mas bajo)`. Botones "Nodo 5" y "Nodo 21" para saltar a cada extremo.

**3D:** con "Su piso" queda solo el subterráneo (−7.97). La columna 5
tiene aristas cian, los apoyos son cubos verdes y se ve la excavación con
sus paredes de tierra. La cámara la deja a la derecha del panel.

**Veredicto:** se contesta.

**Fricción:**

- El campo "Ir a ID" sigue diciendo `5` aunque se seleccione otra cosa
  (en las fotos 11 y 13 dice 5 con la viga 92 seleccionada).
- `tipo / seccion / nodos / largo` se alinean con espacios en una fuente
  proporcional, así que los valores no quedan en columna.
- Con secciones sólidas hay que usar "Su piso" para ver algo del
  subterráneo.

### 2.2 ¿Cómo está apoyado? — `capturas/10_como_esta_apoyado_nodo_5.jpg`

**Panel:** `Nodo 5` `EMPOTRADO`. "Donde esta" da las coordenadas de
OpenSees `(32.352, 18.179, -7.970) m` y las de Unity `(32.35, -7.97, 18.18)
(Y vertical)`. "Como esta apoyado" da `[ux uy uz rx ry rz] = [1 1 1 1 1 1]
(fijo)` y "Empotrado: los 6 grados de libertad restringidos (no se
traslada ni gira)". "Diafragma" dice "Fuera de todo diafragma: se mueve
solo con sus barras". Además están "Barras que llegan (1)".

**3D:** cubo verde en el pie y los ejes del nodo en cian. En **Capas** →
"Control de calidad", la leyenda: cubo empotrado, placa en terreno
`[0 0 1 1 1 0]`, rombo para otra combinación y esfera para el maestro de
diafragma.

**Veredicto:** se contesta. El texto explica la restricción en palabras,
que era lo que faltaba en la Semana 4.

**Fricción:**

- La columna 5 es la columna demo y lleva la jaula de enfierradura en
  sitio: en las fotos 09 y 10 se ve negra y rayada, y no como hormigón.
- El LT2 tiene 16 empotramientos y ningún apoyo en terreno, así que la
  placa de la leyenda no se puede mostrar con este edificio (Ingeniería
  sí los tiene).

### 2.3 ¿Qué lo carga? — `capturas/11_que_lo_carga_viga_92_area_tributaria_y_w_G.jpg`

**Panel** (caso G), bloque "Que lo carga (losa, peso propio y total en G)",
en el orden en que se arma la carga:

```
A_trib    12.500 m2   (1 entrada(s), 2 pano(s))
q_G       6.30 kN/m2 de losa  ->  78.75 kN
w_losa    15.749 kN/m sobre la barra (luz 5.00 m)
w_pp      12.000 kN/m de peso propio de la barra
= w_G     27.749 kN/m, la w total que recibe OpenSees en G
wz en G   -27.749 kN/m (casos_de_carga; diagrama wz)
Q         wz -12.258 kN/m (Q del modelo, la de /analizar)
```

(`registro.txt`, foto 11; `VisorQA.cs:939` `TextoTributaria`). Más abajo,
en "Esfuerzos", aparece `carga repartida (beamUniform) wz -27.749 kN/m`.

**De dónde salen.** `w_pp` y `= w_G` no se calculan en C#: son
`w_peso_propio` y `w_total_G` de la entrada tributaria, que escribe
`edificios/lt2/exportar_unity.py:657` (`en_G`) leyendo lo que el modelo le
pasó a `eleLoad` en G, por origen (`ModeloLT2.repartidas`,
`modelo_lt2.py:1388` para el peso propio `A·γ` y `:1411` para la losa
`q·A/L`). Van en la entrada y no en el elemento porque son dibujo (no entran
a `data/modelo/lt2.json`) y el LT2 tiene una entrada por barra. El
exportador exige, barra por barra, losa + peso propio = `wz` de G exportado
(220 barras, peor diferencia 0.0e+00 kN/m), y `test_contrato_unity.py lt2`
exige `w + w_peso_propio = w_total_G` en 204 entradas (peor 3.6e-15 kN/m) y
`w_total_G = −wz` de G (peor 0.0). Un muro no lleva el desglose: su losa y
su peso propio entran como cargas nodales, y el bloque lo dice. En
Ingeniería (sin el dato) el bloque lo dice en una línea tenue.

**3D:** el paño tributario de la viga en naranjo, los bordes de los demás
paños en líneas naranjas sobre la losa, la viga en cian y el diagrama `wz`
con sus etiquetas.

**Veredicto:** se contesta. 0.60 × 0.80 × 25 = 12.000 kN/m de peso propio
más 15.749 de losa dan los 27.749 del diagrama, y ahora los tres números
están escritos. `comparar_unity.py` [4] compara `w` (15.749323),
`w_peso_propio` (12) y `w_total_G` (27.749323) de lo que leyó Unity contra
`data/unity/lt2.json`. La Q que muestra es la del modelo del visor (plano de
cargas, 4.90 kN/m²), no la del anexo (q_Q = 3, −7.5 kN/m en esta viga).

**Fricción:**

- Las etiquetas `wz i` / `wz j` son grises, grandes y sin fondo, y quedan
  montadas sobre las vigas.
- "Ir a ID" dice 5.
- El peso propio es el del modelo exportado: si se cambia la sección en
  Unity, `w_pp` no cambia (limitación del informe).

### 2.4 ¿Cómo se deforma? — `capturas/12_como_se_deforma_S3_nodo_207.jpg`

**Panel** (caso S3, `1.00 G + 0.50 Q + 1.00 EX`): `ux 18.190 mm`, `uy
-0.919 mm`, `uz -7.705 mm`, `rx -3.185e-04`, `ry -2.387e-04` y `rz
2.721e-05 rad`. La cabecera dice `Desp. max 19.78 mm`.

**3D:** la deformada ×300 del edificio entero. Los muros quedan inclinados
y continuos entre pisos (en la primera captura se partían en escalera) y
la posición original va en líneas oscuras finas.

**Veredicto:** se contesta. El sentido del sismo (+x) se lee de inmediato.

**Fricción:**

- El marcador del nodo 207 es un punto cian que casi no se distingue en la
  vista general.
- Las losas se esconden con la deformada (no la siguen) y el edificio
  vuelve a leerse como pórtico.
- La escala ×300 está en la pestaña Caso y no en la cabecera.

### 2.5 ¿Qué fuerzas tiene? — `capturas/13_que_fuerzas_tiene_viga_92_My_S3.jpg`

**Panel** (S3): la tabla `extremo i / extremo j` con `N 0.00 / 0.00`,
`* Vy 0.00 / 0.00`, `* Vz 216.14 / 373.63`, `T 17.66 / 17.66`, `* My
-562.78 / 911.65` y `* Mz 0.00 / 0.00`, más "(ejes locales; * = los que
mandan en viga_x)". Abajo: `max |My| = 911.65 kN*m en x = 5.00 m (9
estaciones)` y `wz -31.499 kN/m`.

**3D:** el diagrama de My del lado traccionado, en azul y naranjo, con
`My i = -562.8 kN*m` y `My j = 911.6 kN*m`.

**Veredicto:** se contesta. Sigue siendo la mejor respuesta del visor, como
en la Semana 4. La tabla ahora va en fuente monoespaciada y se lee en
columnas.

**Fricción:** las etiquetas del diagrama tienen el mismo problema que en
2.3, y la cámara queda dentro del edificio, con una columna en primer
plano.

### 2.6 ¿Cuánta capacidad tiene? — `capturas/14_...jpg` y `capturas/14b_...jpg`

**Panel** (caso `1.2G+1.0Q+1.4EX`, columna 5): `familia 1: P 0.70x0.70 |
0.70 x 0.70 m | 20 barras | As = 98.17 cm2 | estribo EØ12a10`, `P 6301.0 kN
M 374.0 kN*m extremo i (inferior)`, `Mn 1748.4 kN*m u 0.214 PASA`. Debajo,
"Curva P-M, caso activo 1.2G+1.0Q+1.4EX" con la curva nominal en azul, la
máxima en celeste, el punto rojo del caso activo y los grises de los otros
casos. Remata con `Mn(P) = 1748.4 kN*m u = M/Mn = 0.214 PASA` en verde.

**Mapa** (14b): `NO PASA 4/69 (1 fuera de curva)` con 64 verdes (u < 0.7),
1 amarillo, 3 rojos, 1 morado (P fuera de la curva) y 309 grises (sin
fierro). Aclara "en la escena: 378 barras pintadas" y trae el botón "Ver el
caso con mas NO PASA: 1.2G+1.0Q+1.4EX (4)". Los críticos son el 28 (fuera
de curva), el 12 (u 2.228), el 29 (2.130) y el 45 (1.214). El suelo pasa a
neutro mientras el mapa está prendido.

**Veredicto:** se contesta con fricción. La columna se lee completa. El
edificio, no: los rojos y el morado son muros interiores y se ven como
manchas chicas detrás de los muros verdes de fachada.

**Fricción:**

- Para llegar a los críticos hay que usar la lista ("Ir"). Mirando el
  edificio no se encuentran.
- u es nominal y sin φ (igual que en la Semana 4). El panel no lo dice
  junto al número.

---

## 3. Lo demás que se muestra

| qué | captura | veredicto | fricción |
| --- | --- | --- | --- |
| Superposición E1..E3 sin servidor | `capturas/15_superposicion_E1_precalculado.jpg`, `16_...E2...`, `17_...E3...` | Se lee: caso, origen ("precalculado por semana05/superposicion.py ... sin servidor"), máximo, NO PASA y equilibrio aplicada/reacción/error | El equilibrio va en texto gris tenue; el mapa D/C sigue prendido desde la foto 14 |
| LIBRE con el servidor | `capturas/18_superposicion_E3_LIBRE_servidor.jpg` | Se lee: cuatro sliders con su rango (G y Q de 0.00 a 1.60, EX y EY de −1.40 a 1.40, paso 0.05), "combinar solo (0.6 s despues de dejar de mover un slider)" y el origen con la hora y 0.28 s | Hay que apretar "Conectar (GET /estados)" antes: sin eso los sliders se ven desactivados |
| Carga móvil | `capturas/19_carga_movil_posicion_12_viga_205.jpg`, `20_carga_movil_posicion_25_viga_208.jpg` | La pestaña mejor ordenada: filas etiqueta-valor para dónde está la carga, reparto y conservación | La cabecera ya sigue a lo que se ve: `Carga movil · posicion 13/30 · x = 24.85 m · P = 100 kN`, `UZ max -0.490 mm (nodo 116)` y, en gris, que la D/C no es de la carga móvil. Queda que los nombres de archivo usan índice base 0 (`posicion_12`) y el panel dice "Posicion 13 de 30" |
| M1 | `capturas/21_M1_sin_columna_69_deformada_G_y_equilibrio.jpg`, `22_M1_nodo_186_UZ_G.jpg` | Una sola línea de aviso, `OK: 4 caso(s) [G, Q, EX, EY] en 3.1 s`, `Max. componente 21.5988 mm`, tabla de equilibrio en monoespaciada y la ruta del Excel del reanálisis | La cabecera dice `Reanalisis del servidor (modelo editado) · caso G`, `Max. componente 21.60 mm` (los 21.5988 del panel, con su mismo rótulo: es la mayor componente, no la norma del `Desp. max` del anexo) y, en gris, `D/C: sin recalcular (anexo del modelo original)`. La línea de aviso, en gris, repite lo del anexo |

---

## 4. Antes y después: el panel

Antes: `semana04/capturas/01_columna_18_panel_PM.jpg` y
`semana04/capturas/04_N_edificio.jpg` (Ingeniería, 1920×1080). Después:
`semana05/capturas/03_panel_vista.jpg` a `08_panel_carga_movil.jpg` (LT2,
1600×900). Los edificios son distintos: lo que se compara es el visor.

| | Semana 4 | Semana 5 |
| --- | --- | --- |
| Paneles | Dos grises semitransparentes, uno a cada lado (toggles y Semana 4 a la izquierda, "MODELO" del editor a la derecha), más la ventana flotante P-M sobre el modelo | Uno solo, oscuro y opaco, a la izquierda. El editor y la carga móvil son pestañas (`IPanelIncrustable`) |
| Cabecera | No había: el caso activo aparecía a media altura, dentro de "Semana 4" | Fija: edificio, nodos y elementos, caso activo con su descripción, `Desp. max`, `PASAN 69/69` en verde o `NO PASA n/m (k fuera de curva)` en rojo, selección con Ver / Centrar / x y "Ocultar (H)" |
| Organización | Texto corrido con separadores `---` y `====`, y un solo scroll | Seis pestañas (Vista \| Capas \| Caso \| Elemento \| Modificar \| Carga movil) con secciones plegables `+` / `-` |
| Texto | 11 px, sin escala | Escalado por DPI (`PanelUI.Escala()`: 120 dpi / 96 = 1.25) con "A-" / "A+" para el usuario; tablas numéricas en monoespaciada |
| Controles | Casillas del skin por defecto, diminutas | Botones de alto uniforme y casillas de 18 px de diseño con visto (`PanelUI.Casilla`) |
| P-M | Ventana flotante que tapaba el modelo | Dentro de la pestaña Elemento, bajo "Demanda / capacidad". La ventana sigue disponible |
| Selección | Dos selecciones, la del panel de la Semana 4 y la del editor, que se contradecían (foto 01: el panel muestra la columna 18 y el editor dice "Nada seleccionado") | Una sola (`EventosVisor.SeleccionCambio`) para barra, nodo o apoyo, con "Ir a ID" |
| Excel | No había | Botón "Abrir Excel de resultados" siempre visible |

**Veredicto:** la misma información, ordenada. Lo que se nota todavía:

- "Abrir Excel de resultados" usa el mismo azul lleno que la pestaña
  activa, y arriba parecen dos cosas seleccionadas.
- El prefijo `> ` en los botones activos (`> Realista`, `> E3`, `> G`)
  sobra: ya van en azul.
- El texto de ayuda va en gris tenue y pequeño.

## 5. Antes y después: el realismo

Antes: `semana04/capturas/04_N_edificio.jpg` y
`01_columna_18_panel_PM.jpg`. Después: `semana05/capturas/01_vista_general_realista_con_suelo.jpg`,
`02_vista_general_tecnica.jpg`, `12_como_se_deforma_S3_nodo_207.jpg` y
`17_superposicion_E3_precalculado.jpg`.

| | Semana 4 | Semana 5 (Realista) |
| --- | --- | --- |
| Suelo | No había: el "piso" era el hemisferio inferior gris del cielo | Pasto procedural hasta el horizonte, a la cota −4.01 (supuesto provisorio), con la excavación del subterráneo, paredes de tierra y fondo en −7.97. Sin collider |
| Estructura | Barras como tubos finos, esferas azules en los nudos, columnas negras (jaula de enfierradura en todas) y muros lila | Columnas y vigas con su sección b×h y textura de hormigón, muros con encofrado y nudos auxiliares chicos |
| Losas | No había | Una losa de dibujo por paño, desde los polígonos de `areas_tributarias` (243 entradas, 5 cotas) |
| Luz | La de la escena | Sol reorientado solo en la realista y luz ambiente neutra, para que las caras que ve la cámara no queden azuladas |
| Deformada | Muros y líneas en amarillo, columnas negras por la jaula (foto 10 de la S4) | Hormigón con la posición original en líneas oscuras. Los muros son cajas cizalladas que siguen a sus nodos |
| Técnica | La única vista | Se conserva igual con "Tecnica" (foto 02). El `registro.txt` de la S4 sale idéntico byte a byte |

**Veredicto:** el edificio ya se lee como edificio (foto 01). Queda:

- Las losas se esconden con la deformada, los diagramas, el mapa D/C y la
  carga móvil (fotos 12, 14b, 17 y 19), porque la transparencia de URP no
  sobrevive a la build.
- El borde del hoyo tiene escalones de 0.5 m (visibles en 09 y 10).
- Las etiquetas 3D no tienen fondo.

---

## 6. Fricción que queda, por prioridad

Ninguna cambia un número. Todas salen del informe de QA visual y de mirar
las fotos del 17-09. Las dos primeras de la lista original se arreglaron al
cierre, con una build nueva y las 23 fotos otra vez (`comparar_unity.py`:
486 filas, 0 FALLA):

- ~~Cabecera que no sigue a lo que se ve~~. La cabecera nombra la fuente de
  lo que se ve en 3D (`VisorQA.cs:2594` `FuenteDeLoQueSeVe`, decidida en la
  foto del Layout): el caso del anexo con su Δmax y su NO PASA (15-18), la
  carga móvil con posición, x, P y UZ max de `carga_movil.json` (19, 20), o
  el reanálisis del servidor con su máximo y "D/C: sin recalcular" (21, 22).
  `CapturaSemana05` registra la fuente de cada foto y `comparar_unity.py` la
  compara con sus números: 28 filas.
- ~~Carga de la viga sin explicar~~. El bloque "Que lo carga" escribe losa,
  peso propio y total en G, los tres de Python (11; §2.3).

Las que quedan no se arreglaron por ser de prioridad baja:

3. Los NO PASA del mapa D/C no se ven desde afuera (14b).
4. "Ir a ID" no se sincroniza con la selección (11, 13).
5. Etiquetas 3D grises sin fondo (11, 13).
6. Botón Excel con el mismo azul que la pestaña activa, y prefijo `> `
   (todas).
7. Marcador del nodo seleccionado chico en la deformada (12).
8. Borde del hoyo en escalones (09, 10).
9. Fotos 19 y 20 nombradas con índice base 0.
10. Solo escritorio: mover un nodo en altura necesita Shift y teclado
    ([`MOVIL.md`](MOVIL.md)).
