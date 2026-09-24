# Qué revisar para que los NO PASA tengan sentido

> ## 24-09, EN CURSO: la losa colaborante (viga T)
>
> Pedro pregunto que se podria "inventar" para que Ingenieria dejara de
> deformarse raro, y de la lista eligio lo unico que **no inventa ninguna
> dimension**: que la viga trabaje con su ala de losa (ACI 318-08 8.12.2).
> Hoy los dos modelos cargan la losa SOBRE la viga pero no dejan que la
> losa la AYUDE: cada viga entra a OpenSees como un rectangulo bw x h.
>
> **La regla ya esta escrita y verificada**: `comun/losa_colaborante.py`, en
> la suite. Usa el espesor de losa que cada edificio ya declara y los tres
> topes de ACI (`L/4`, `8 hf` por lado, y el ancho tributario, que es la
> media distancia al alma vecina y hace que una viga de borde se acote sola).
> Medido sobre las vigas reales:
>
> | | vigas | Iz mediana | rango | que tope manda |
> | --- | --- | --- | --- | --- |
> | LT2 | 219 | **x1.39** | x1.00 a x1.88 | `L/4` en las 219 |
> | Ingenieria | 301 | **x1.81** | x1.32 a x2.30 | `L/4` en 261, tributario en 40 |
>
> El ala ayuda casi el doble a Ingenieria, que es lo que corresponde: un alma
> de 0.30 gana mas ala que una de 0.60. O sea que cierra parte de la
> diferencia entre los dos cuerpos **sin tocar una sola dimension**.
>
> **Lo que se cambia y lo que no.** Solo `Iz`. El area se deja RECTANGULAR a
> proposito: los dos modelos sacan el peso propio de la viga de `A * gamma` y
> el peso de la losa ya entra aparte como carga tributaria; si el area
> llevara el ala, la losa pesaria dos veces y el equilibrio cerraria igual,
> sin avisar. `Iy` y `J` tampoco: el ala casi no ayuda en planta ni a
> torsion, y dejarlos es el lado seguro.
>
> **Lo que falta: conectarla.** El ala depende de la luz (`b_eff <= L/4`) y
> las luces van de 0.35 a 10.00 m, asi que NO sirve una seccion por tipo:
> cada viga necesita la suya. Eso pide, en los DOS edificios, que el modelo
> calcule `Iz` por viga y que el exportador emita una seccion por luz
> distinta (hoy el nombre de seccion y el `tipo` son el mismo string en
> Ingenieria, `export_unity.py:219`, asi que ademas hay que separarlos).
> **No se hizo a medias a proposito**: con el ala en un cuerpo y no en el
> otro, comparar los dos edificios dejaria de significar nada. Mientras
> tanto el modelo no cambio: el repo sigue consistente y la suite verde.
>
> ---
>
> ## 23-09, HECHO: el pilar de Ingenieria (70x70 del plano, Ø22 de norma)
>
> **Donde quedo el mapa D/C, en tres pasos medidos sobre el conjunto con las
> 15 combinaciones:**
>
> | | NO PASA de 3105 filas | elementos |
> | --- | --- | --- |
> | como estaba (0.50x0.50, Ø16) | 282 | 75 |
> | con la seccion del plano (0.70x0.70, Ø16) | 167 | 49 |
> | **+ el diametro minimo de norma (Ø22)** | **119** | **32** |
>
> **Y lo que queda ya casi no son columnas** (item 5, medido el 24-09 con
> `comun/nucleos.py`, que agrupa las patas de UN piso de un nucleo):
>
> | | filas | elementos | que le pasa al GRUPO |
> | --- | --- | --- | --- |
> | pata de un nucleo **comprimido** | **92** (77 %) | 24 | la traccion de la pata es el par interno |
> | pata de un nucleo traccionado **dentro** de su `As*fy` | **11** (9 %) | 6 | el grupo aguanta su traccion |
> | pata de un nucleo **por sobre** su `As*fy` | **0** | 0 | — |
> | muros que NO son pata de nada | 9 | 5 | — |
> | columnas de Ingenieria | 7 | 2 | — |
>
> **Ni un solo grupo esta sobrepasado en axial.** Las 103 filas de pata salen
> enteras de mirar la pata sola: el nucleo resiste el volcamiento como un par
> de axiales entre sus patas, y la traccionada se compara despues contra su
> propio `As*fy` como si esa traccion fuera carga externa. **El diametro no
> puede bajar esto**: se arregla con la seccion de fibras del nucleo completo
> (biaxial, porque 12 de los 17 grupos tienen muros cruzados; 1-2 dias).
>
> Lo que queda SIN coartada son **16 filas en 7 elementos**, todas en
> `0.9G +- 1.4E`: los muros `200014`, `200015`, `200030` y `200031` del LT2
> (todos `M 0.30x1.45`, u de 1.007 a 2.126), el `100465` de Ingenieria
> (u 1.302) y las columnas `100042` y `100043` (u 1.198 y 1.149).
>
> Mientras tanto, el dato **lo dice**: cada fila de demanda viaja con
> `nucleo_patas`, `nucleo_P`, `nucleo_Asfy` y `nucleo_estado`, y la ficha P-M
> del visor escribe "Pata de un nucleo de N muros: el grupo esta COMPRIMIDO
> (X kN)...". El veredicto `pasa` NO cambia: revisar pata por pata es un
> procedimiento aceptado y el ala traccionada tiene que llevar su traccion
> con su propio fierro. Lo que cambia es que el mapa deja de presentar como
> falta de capacidad lo que es un reparto interno.
>
> ### El pilar: 0.70 x 0.70 del plano
>
> **Es el hallazgo mas grande de toda la lista, y no estaba en ella. Ya esta
> adoptado**, con la lamina como origen: Pedro conto 18 pilares en la
> **lamina 2017_67-103** y los vio todos de 70x70.
>
> **Efecto en el conjunto, ya en los datos: 282 -> 167 NO PASA de 3105 filas.**
> Columnas de Ingenieria 126 -> 55 filas / 19 elementos; muros de Ingenieria
> 132 -> 88 / 20; el LT2 no se toca (24 / 10). El desplazamiento maximo de los
> 15 casos baja de 53.91 a 39.10 mm, y por eso la escala grafica de la
> deformada pasa de x83 a x110.
>
> **Numeros de control nuevos** (CLAUDE.md seccion 8, AGENTS.md,
> `edificios/conjunto/README.md`): Ingenieria `G = 52 600.50 kN` (era
> 50 652.2; el peso propio de las columnas sube 1 948.3 kN) y conjunto
> `G = 86 749.48 kN`, que sigue siendo **exactamente** la suma de los dos
> cuerpos (diferencia 0.0000 kN: la junta sigue libre).
>
> **Como quedo declarado.** No como constante: en
> `edificios/ingenieria/perfiles/ingenieria_2017_67.json`, bloque `secciones`,
> con su `origen`. De paso se declararon ahi tambien las vigas, la losa y el
> `f'c`, que tenian el mismo problema, marcadas con `_supuesto: true`.
> `benchmark_3d.py` las LEE de ahi y ya no las tiene escritas; si falta una,
> el KeyError dice cual (antes un default silencioso escondia el 0.50).
>
> - **El conteo calza**: el modelo tiene exactamente **18 columnas por piso**
>   (21 posiciones en planta x 5 niveles = los 82 *elementos*). Lo que no
>   calza es el **tamano**.
> - **De donde sale el 0.50**: `edificios/ingenieria/benchmark_3d.py:409`,
>   `col_b, col_h = 0.50, 0.50`. Es una **constante pelada**, sin `origen`,
>   sin `_supuesto` y sin referencia a ninguna lamina, bajo un encabezado
>   "MATERIAL AND SECTION DATA". Lo mismo las vigas (`0.30x0.60`,
>   `0.30x0.80`), la losa (`0.25`) y el `f'c = 28`. El perfil
>   `perfiles/ingenieria_2017_67.json` solo declara `_que_es`, `unidades` y
>   `terreno`: **ninguna dimension de Ingenieria es trazable al plano**. Es
>   exactamente lo que CLAUDE.md seccion 5 dice que no puede pasar.
> - **Medido** (23-09) rehaciendo el pipeline entero de Ingenieria con
>   `col_b, col_h = 0.70, 0.70` --armar + calcular + exportar, asi que el
>   peso propio tambien cambia-- y despues **restaurado**: no se adopto nada.
>
>   | | 0.50 x 0.50 (hoy) | 0.70 x 0.70 |
>   | --- | --- | --- |
>   | NO PASA de Ingenieria, 15 combinaciones | 258 filas | **145** |
>   | de esas, columnas | 126 filas / 38 elem | **56 / 19** |
>   | de esas, muros | 132 filas / 27 elem | **89 / 21** |
>   | UZ maximo bajo G | 22.30 mm | **19.04 mm** |
>   | desplazamiento lateral EY | 33.16 mm | **20.63 mm** (-38 %) |
>   | desplazamiento lateral EX | 6.88 mm | **5.98 mm** (-13 %) |
>
> - **Y el diametro dejo de ser libre, y por eso se cambio** (23-09, con el
>   OK de Pedro): con 16 barras Ø16 en una columna de 70x70 la cuantia cae a
>   **0.66 %**, por debajo del minimo de norma (ACI 318-08 10.9.1, ρ >= 1 %),
>   o sea una columna que la norma no admite. El menor admisible es **Ø22**
>   (ρ = 1.24 %) y es el que quedo declarado en el perfil. **La justificacion
>   es el minimo de norma sobre la seccion leida del plano, no "para que
>   pase"**: es la unica que se sostiene en una defensa, y ademas no deja el
>   mapa en cero (quedan 7 filas de columna y 112 de muro). El diametro sigue
>   marcado como supuesto: el 2017_67 no tiene cuadro de pilares.
>
>   | Ø en 70x70 | ρ | NO PASA de 1230 |
>   | --- | --- | --- |
>   | Ø16 | 0.66 % | 56 (cuantia ilegal) |
>   | Ø18 | 0.83 % | 31 (cuantia ilegal) |
>   | **Ø22** | **1.24 %** | **7** |
>   | Ø25 | 1.60 % | 1 |
>   | Ø28 | 2.01 % | 0 |
>
> - **Ademas explica la otra queja**: "Ingenieria se deforma raro, mucho mas
>   que el LT2". Con 70x70 el lateral en Y baja un 38 %.
> - **Que falta para adoptarlo**: que el plano lo confirme (una lamina de
>   planta o un corte de pilar del 2017_67 con la dimension), y que Eduardo
>   lo cambie en su carpeta **con su `origen` al lado**. De paso, las vigas,
>   la losa y el `f'c` tienen el mismo problema de procedencia.
>
> ---
>
> ## ESTADO AL 23-09: la respuesta, y lo que se hizo
>
> Pedro pidió cerrar el **por qué no pasan los casos**. Se cerró, y el
> resultado cabe en una tabla. Con las **15 combinaciones** (las 9 de antes
> más las 6 que faltaban, ítem 1b, ya implementadas) y la capacidad tomada
> por el **peor de los dos sentidos** (ítem 10, ya implementado), el conjunto
> da **282 NO PASA de 3105 comprobaciones (9.1 %) en 75 elementos de 207**:
>
> | causa | filas | elementos | qué es |
> | --- | --- | --- | --- |
> | muros que son **pata de un núcleo**, revisados solos (ítem 5) | **156** (55 %) | 37 | un **procedimiento** del chequeo |
> | columnas de Ingeniería, familia única con **Ø16 supuesto** (ítem 6) | **126** (45 %) | 38 | un **dato que no está en el plano** |
> | cualquier otra cosa | **0** | 0 | — |
>
> O sea: **ninguna de las 282 fallas dice "el edificio no resiste"**. Las 282
> están enteras en esos dos cubos: revisamos una pata de núcleo contra su
> propio `As·fy`, y no sabemos el diámetro del fierro de los pilares del
> 2017_67. No queda **ni un** muro suelto ni una columna del LT2 que falle.
>
> El grupo de núcleo se define estricto: muros unidos por una cadena de
> brazos rígidos **sin viga ni columna en el medio** (de los 183 brazos del
> conjunto, 96 llegan a un nudo con viga o columna y no unen núcleo). Con esa
> regla, **77 de los 96 muros son pata de un núcleo**, en 36 grupos.
>
> **Las dos mediciones que lo cierran** (23-09, sobre el anexo del conjunto
> de 15 casos):
>
> - **Las patas de núcleo.** 39 de las 43 banderas `u = 9999` son pata de un
>   grupo unido por brazos rígidos, y **33 de ellas pertenecen a un grupo que
>   está en COMPRESIÓN NETA**. La tracción que saca a esa pata de su curva es
>   el par interno del núcleo, no carga que el grupo tenga que tomar. En las
>   6 que quedan el grupo sí está traccionado, pero muy lejos de su `As·fy`
>   de grupo (el `100478`: −324 kN contra ~2580 kN del grupo, un 13 %).
> - **El diámetro.** Las 1230 filas de la familia de columnas de Ingeniería,
>   rehechas solo cambiando el diámetro y con las 15 combinaciones:
>
>   | diámetro | As (cm²) | ρ | NO PASA de 1230 |
>   | --- | --- | --- | --- |
>   | **Ø16 (el supuesto de hoy)** | 32.17 | 1.29 % | **126** |
>   | Ø18 | 40.72 | 1.63 % | 89 |
>   | Ø22 | 60.82 | 2.43 % | 32 |
>   | Ø25 | 78.54 | 3.14 % | 8 |
>   | Ø28 | 98.52 | 3.94 % | 1 |
>
>   Un 16Ø22 (ρ = 2.43 %) es tan plausible como el 16Ø16 en un pilar de
>   50 × 50. **No se puede elegir para que pase**: hay que leerlo del plano.
>
> ### Lo que cambió en el código el 23-09
>
> - **Ítem 1b HECHO.** `semana03/parametros.json` declara ahora **11**
>   combinaciones: se agregaron `1.2G+1.0Q−1.4EX`, `1.2G+1.0Q−1.4EY`,
>   `0.9G±1.4EX` y `0.9G±1.4EY`. El anexo pasó de 9 a 15 casos y la
>   autoverificación de equilibrio cierra en los 15. Efecto medido: los
>   elementos que fallan pasan de 52 a 75.
> - **Ítem 10 HECHO.** `capacidad.interaccion()` corre la sección **y su
>   espejo** (`capacidad.espejo`) y se queda con el **mínimo** de los dos
>   `Mn`, que es lo que corresponde comparar con la `|M|` de la demanda. Se
>   salta la segunda corrida cuando el fierro es simétrico
>   (`capacidad.fierro_simetrico`). Efecto medido **con las mismas 9
>   combinaciones de antes**: 110 → **111** NO PASA, los mismos 52
>   elementos. Volteó **un** veredicto, exactamente el `200045` en EX que
>   había predicho la revisión adversarial del 18-09.
>
> ### Lo que se DESCARTÓ el 23-09: el ítem 4 estaba equivocado
>
> El ítem 4 decía que la rama de tracción de la curva P-M "tiene un solo
> punto" y que densificarla arreglaría los `u > 15`. **Es falso, y
> densificarla sería inflar la capacidad.** Demostrado sobre el muro
> `200012` (`As·fy` = 5882.5 kN, `M0` = 9108.7 kN·m en flexión pura):
>
> | f | P = f·P_tracción | la recta de 2 puntos | `(As·fy − \|P\|)·jd` |
> | --- | --- | --- | --- |
> | 0.90 | −5294.3 | 910.9 | 910.9 |
> | 0.70 | −4117.8 | 2732.6 | 2732.6 |
> | 0.50 | −2941.3 | 4554.3 | 4554.3 |
>
> Coinciden **al último decimal**: con el acero sin endurecer, la interacción
> entre tracción pura y flexión pura **es** lineal, así que la recta de dos
> puntos ya es la rama nominal. Lo que da la corrida de fibras en esa zona
> (6670 kN·m en vez de 911) sale entero del endurecimiento de `Steel01`, que
> lleva el acero a `ε_s = 0.10` ≈ 1.47 `fy`: no es capacidad nominal. Los
> `u > 15` **no son un artefacto de muestreo**; son el axial, y el axial es
> el ítem 5.
>
> ### Lo que sigue abierto, y de quién es
>
> | qué | quién | efecto medido |
> | --- | --- | --- |
> | El Ø longitudinal de los pilares del 2017_67 | Eduardo + el plano | 126 filas |
> | Revisar el núcleo como grupo y no pata por pata (sección compuesta) | `comun/`, 1-2 días | 142 filas |
> | El pilar en (43.02, 55.20) (ítem 3) | el plano | las 7 fallas sin sismo |
> | Los muros de Ingeniería sobre ±0.00 (ítem 2) | Eduardo | parte de las 142 |
> | El nivel del `cs` (ítem 1) | el profesor | escala todo |
> | φ y el chequeo de corte (ítem 9) | decisión | ambos en contra |
> | Los 11 muros del LT2 sin curva (ítem 8) | Pedro + el plano | omisión, optimista |
>
> **Lo que sigue abajo es la lista del 18-09, tal como se escribió**, con sus
> números de 9 combinaciones. Se conserva porque es el registro de cómo se
> llegó acá; donde un ítem ya se hizo o se descartó, lo dice este bloque.

Lista priorizada, en orden de **cuánto mueve el D/C × cuánta confianza hay en
la medición**. Todo lo que dice "medido" se midió el 18-09 sobre el **anexo
del CONJUNTO** (`info.edificio = "conjunto"`, 937 elementos, 207 con curva
P-M, 9 casos, 1863 comprobaciones) y sobre `data/modelo/conjunto.json`. Nada
de esto cambió código ni datos: es una lista de revisión.

> ### ANTES DE CORRER NADA: el anexo que hay en disco es el del LT2
>
> El anexo vive en **un solo archivo**, `data/unity/semana04.json`, y guarda
> el edificio que se exportó al final. Cuando se corrió la suite por lo del
> terreno (ítem 11), `comun/verificar_todo.py` volvió a exportar los anexos
> **con `lt2`** y pisó el del conjunto: hoy ese archivo trae
> `info.edificio = "lt2"`, 378 elementos, 69 con curva, 621 comprobaciones y
> 8 NO PASA. Es la trampa que `verificar_todo._avisar_anexos()` avisa y que
> está en `CLAUDE.md` §6.
>
> Con el archivo así, los comandos de más abajo **o se caen**
> (`KeyError: 100599`, porque los nodos de Ingeniería no existen en el LT2)
> **o contestan en silencio otra cosa** (el del ítem 4 imprime "2 banderas"
> en vez de 19). Para reproducir cualquier número de esta lista hay que
> rehacer primero el anexo del conjunto:
>
> ```powershell
> .\.venv\Scripts\python.exe semana04\exportar_unity.py conjunto
> ```
>
> (escribe `data/unity/semana04.json` y su copia en StreamingAssets; para
> volver a dejar la demo del LT2, el mismo comando con `lt2`). Comprobado el
> 18-09 corriendo los comandos tal como están escritos. Los tres que **no**
> dependen del anexo —el del ítem 7 (lee `data/modelo/conjunto.json`), el
> `comun\sismo.py conjunto EY --detalle` del ítem 2 y los `Select-String` de
> los ítems 9 y 11— funcionan hoy y dan lo que dicen.
>
> **Alternativa que no escribe nada** (agregada en la revisión adversarial
> del 18-09, comprobada): el anexo del conjunto se puede armar **en
> memoria** con `construir_anexo()` de `semana04/exportar_unity.py`, que es
> lo mismo que exporta el comando de arriba pero sin tocar `data/` ni
> StreamingAssets (tarda unos 5 s). En cualquiera de los comandos de abajo,
> reemplazar `json.load(open('data/unity/semana04.json',encoding='utf-8'))`
> por
>
> ```
> (__import__('sys').path.__setitem__(slice(0,0),['semana04','comun','semana03']) or __import__('exportar_unity').construir_anexo('conjunto')[0])
> ```
>
> El orden de la ruta importa: `semana03/` también tiene un
> `exportar_unity.py`, y si va primero el import toma ese y falla con
> `AttributeError: ... construir_anexo`. Con esa sustitución el comando del
> ítem 4 da "19 banderas u=9999; en traccion: 19" sin reexportar nada.

La reconstrucción de las combinaciones que se usa más abajo reproduce el
anexo **exacto** (S3 11, 1.4G 3, 1.2G+1.6Q 4, 1.2G+1.0Q+1.4EX 21,
1.2G+1.0Q+1.4EY 36), así que las sensibilidades son comparables entre sí.

---

## Resumen para Pedro

1. **No falla casi todo.** Fallan 110 de 1863 comprobaciones (5.9 %), en 52
   elementos de 207. Lo que da la impresión de "falla en todas partes" es que
   7 de los 9 casos tienen al menos un NO PASA, no que falle mucho.
2. **El 93 % de las fallas es de Ingeniería**: 51 filas de columna + 51 de
   muro, contra 8 filas de muro del LT2. Tus 40 columnas del LT2 **no fallan
   en ningún caso**; de tus 29 muros con fierro fallan 4.
3. **Las fallas dependen casi linealmente de un número que nadie justificó.**
   Con `cs = 0.10` hay 75 NO PASA en las 5 combinaciones; con 0.05 hay 30 y
   con 0.20 hay 146. El `cs` lo pone el profesor y en el código **no hay
   ningún R** (ni factor de importancia, ni corte mínimo). Ojo: eso **no**
   quiere decir que el sismo esté inflado. Si 0.10 es el `C` de NCh433 (que
   ya viene dividido por R), la demanda está bien y hasta le falta el `I`;
   ver ítem 1.
4. **Falta la mitad de las combinaciones sísmicas** (hallazgo de la
   revisión adversarial). El repo solo mayora el sismo en **un** sentido
   (`+1.4EX`, `+1.4EY`) y no tiene `0.9G ± 1.4E`, que NCh3171 exige y que es
   la que manda en tracción de muros. Con las 6 que faltan, los elementos
   que fallan pasan de **48 a 74**, y los muros del LT2 que fallan de
   **4 a 10**. Es el lado **optimista** más grande que se midió (ítem 1b).
5. **Solo 7 fallas no dependen del sismo**, y salen de un nudo de la
   parrilla de Ingeniería en (43.02, 55.20) que no tiene columna debajo en
   ningún piso. Ahí dos vigas en Y de 7.5 y 8.9 m descargan ~286 kN (bajo G)
   sobre una viga en X 0.30×0.60 que queda trabajando como viga de
   **transferencia de 10 m** entre dos columnas, y esa viga le mete 488 kN·m
   al nudo de techo de la columna 100080. El momento **sí** lo produce
   carga: es el camino de carga de un nudo sin apoyo. Si el plano pone un
   pilar ahí, al modelo le falta el pilar y las 7 fallas son artefacto; si
   no lo pone, son reales (ítem 3).
6. **Los números escandalosos son de dos clases distintas.** Los cuatro
   `u > 15` sí salen de que la curva P-M tiene **un solo punto** en toda la
   zona de tracción (ítem 4), pero al rehacerlos con la corrida exacta el
   resultado **depende del sentido del momento** en los muros del LT2 con el
   fierro descentrado (el 200012 da `u` 0.10 en un sentido y 436 en el
   otro). Los 19 `u = 9999` **no** son de muestreo: son demandas cuya
   tracción neta **supera la capacidad a tracción de todo el fierro** de la
   sección, entre 1.07 y 2.09 veces `As·fy` (medido en las 19). Ahí no hay
   curva que interpolar, y densificar el muestreo no las mueve: lo que hay
   que mirar es el axial, y el mecanismo es el del ítem 5 (patas de núcleo;
   comprobado que las 19 son patas de un núcleo unido por brazos), no el del
   ítem 4.
7. **El cálculo de hoy es optimista por un lado y pesimista por otro.**
   Optimista: sismo en un solo sentido y sin `0.9G ± 1.4E` (ítem 1b), sin
   ningún chequeo de corte, 11 muros sin revisar y, en menor medida, sin φ.
   Pesimista: momento en el eje del nudo, patas de núcleo revisadas solas y
   la rama de tracción de dos puntos. **Indeterminado**: el nivel del sismo
   (si el 0.10 ya trae R o no, ítem 1). Antes de decir "el edificio falla"
   hay que cerrar los tres.
8. **Lo del suelo: HECHO el 18-09** (ítem 11). El suelo va donde arrancan
   las columnas: el LT2 declara −7.97 y el perfil nuevo de Ingeniería su
   0.00 local, que calzado es la misma cota, así que el conjunto no se cae.
   Lo que quedaba abierto, los 39 apoyos de Ingeniería en −4.01 dibujados
   3.96 m sobre el suelo, también se hizo el 18-09: el terreno va en dos
   niveles (una terraza en −4.01, ítem 11). Efecto en el D/C: cero,
   medido.

---

## La foto: de dónde salen los 110 NO PASA

| dónde | filas NO PASA | de cuántas | elementos distintos |
| --- | --- | --- | --- |
| Ingeniería, columnas (1 sola familia) | 51 | 738 | 27 de 82 |
| Ingeniería, muros (fallan 8 de sus 27 familias) | 51 | 504 | 21 de 56 |
| LT2, muros | 8 | 261 | 4 de 29 |
| LT2, columnas | **0** | 360 | 0 de 40 |

Por caso: G 0, Q 0, EX 9, EY 26, S3 11, 1.4G 3, 1.2G+1.6Q 4,
1.2G+1.0Q+1.4EX 21, 1.2G+1.0Q+1.4EY 36.

Solo 13 de las 54 familias de curva dan fallas, y dos de ellas
(`ingenieria:columna` con 51 filas y `ingenieria:muro_3` con 12) son el 57 %
del total.

```powershell
.\.venv\Scripts\python.exe -c "import json,collections; d=json.load(open('data/unity/semana04.json',encoding='utf-8')); E={e['id']:e for e in d['elementos']}; c=collections.Counter(); [c.__setitem__((('lt2' if E[x['id']]['seccion'].startswith('lt2:') else 'ing'), E[x['id']]['tipo']), c[(('lt2' if E[x['id']]['seccion'].startswith('lt2:') else 'ing'), E[x['id']]['tipo'])]+1) for k in d['casos'] for x in k['demandas'] if not x['pasa']]; print(dict(c), 'total', sum(c.values()))"
```

---

## La lista, en orden

> **Sobre el orden (revisión adversarial del 18-09).** Se agregó el ítem
> **1b** (combinaciones que faltan), que mueve más elementos que cualquier
> otro y es barato de cerrar. Y el **ítem 6** está más abajo de lo que
> merece: con un Ø22 —un supuesto tan plausible como el Ø16, ρ = 2.4 %—
> las fallas de columna de Ingeniería bajan de 51 a 10. Si hay que elegir
> qué leer del plano primero, es el diámetro de los pilares (ítem 6) y el
> pilar en (43.02, 55.20) (ítem 3), antes que los ítems 4 y 5, que cambian
> magnitudes y no el conteo. No se renumeró para no romper las referencias
> cruzadas.

### 1. El `cs = 0.10` entra crudo: sin R, sin I y sin corte mínimo

**Qué revisar.** De dónde sale el coeficiente sísmico y con qué se compara.
Es la perilla que más mueve el mapa y hoy no tiene justificación escrita.

**Por qué se sospecha.** `semana03/parametros.json` declara
`sismo.coeficiente = 0.1` y su propio comentario dice: *el enunciado da como
ejemplo el 0.20 de g que NCh433 asocia a la zona del edificio; 0.10 es el
valor de trabajo actual; hay que reemplazarlo por el que pida el profesor*.
El corte basal es literalmente `V = cs · W` (`semana03/lab_semana03.py:374`)
y un grep de `R`, `minora` o factor de reducción en `comun/`, `semana03/`,
`semana04/` y `semana05/` no devuelve **nada**.

**Evidencia medida.** Filas NO PASA de las 5 combinaciones del repo
(5 × 207 = 1035 comprobaciones), escalando EX/EY (exacto: el modelo es
lineal y `V = cs·W` escala el patrón completo):

| cs | NO PASA | 1.4G | 1.2G+1.6Q | S3 | +1.4EX | +1.4EY |
| --- | --- | --- | --- | --- | --- | --- |
| 0.025 | 16 | 3 | 4 | 1 | 5 | 3 |
| 0.050 | 30 | 3 | 4 | 4 | 9 | 10 |
| 0.075 | 55 | 3 | 4 | 8 | 15 | 25 |
| **0.100 (hoy)** | **75** | 3 | 4 | 11 | 21 | 36 |
| 0.150 | 113 | 3 | 4 | 18 | 27 | 61 |
| 0.200 | 146 | 3 | 4 | 24 | 37 | 78 |

Las 7 filas de gravedad (1.4G y 1.2G+1.6Q) **no se mueven**: son el piso
irreducible del mapa y son el ítem 3 de esta lista.

**Efecto esperado en el D/C.** Es el mayor de todos: el conteo va de 30 a 146
dentro del rango razonable de `cs`, y de ese número dependen 103 de las 110
filas.

**Hacia qué lado empuja: NO está establecido** (corregido en la revisión
adversarial del 18-09; antes esta línea decía "PESIMISTA" y no se sostiene).
`cs` es un dato de entrada y el repo no dice qué representa, así que hay dos
lecturas y empujan al revés:

- si `0.10` pretende ser el **coeficiente de diseño** `C` de NCh433 —el que ya
  viene dividido por `R`—, entonces `1.4·C·W` es exactamente lo que pide
  NCh3171 y no falta ninguna reducción. Para un edificio rígido de muros el
  `C` de la norma queda casi siempre pegado a su **tope** `C_max`, que es
  función de `R`, así que un valor del orden de 0.10 es perfectamente
  posible como valor **ya reducido**; volver a dividirlo por `R` sería
  reducir dos veces;
- si `0.10` es un `A0/g` crudo (el comentario del archivo apunta a eso: habla
  del "0.20 de g que NCh433 asocia a la zona"), entonces sí falta el `R` y la
  demanda está inflada.

Los números inclinan hacia la **primera** lectura (agregado en la revisión
adversarial; confirmar contra el ejemplar de la norma): ninguna zona de
NCh433 tiene `A0 = 0.10 g` —las tres zonas son 0.20, 0.30 y 0.40 g—, y
Santiago (Las Condes) es **zona 2, `A0 = 0.30 g`**, no el 0.20 que cita el
comentario de `parametros.json` (ese es el de la zona 1). En cambio, para
muros de hormigón armado (`R = 7`) el tope de la Tabla 6.4 es
`C_max = 0.35·S·A0/g`, que en zona 2 da **0.105** con suelo B (`S = 1.0`),
0.110 con suelo C y 0.126 con suelo D; y el mínimo es `A0·S/6g ≈ 0.05`. O
sea, 0.10 calza casi exacto con el `C` **ya reducido** de un edificio de
muros en Santiago, y con esa lectura lo que falta es el `I = 1.2`
(demanda +20 %), no el `R`.

Y hay un factor que va en la dirección **contraria** y que no está en ninguna
parte: el **coeficiente de importancia `I`**, que multiplica al corte basal
(`Q0 = C·I·P`). Un edificio universitario es de los que la norma clasifica en
la categoría de "gran cantidad de personas / uso público", con `I = 1.2`: si
se aplicara, la demanda **subiría** un 20 %. O sea, de las dos cosas que
faltan, una (`R`) puede estar haciendo el mapa pesimista y la otra (`I`) lo
está haciendo optimista. **Hasta saber qué es el 0.10, la dirección de este
ítem es indeterminada**, y por eso es el número que hay que preguntarle al
profesor antes que cualquier otra cosa.

**Cómo comprobarlo.**
```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path[:0]=['semana04','comun','semana03']; import exportar_unity as ex; C=('S3','1.4G','1.2G+1.6Q','1.2G+1.0Q+1.4EX','1.2G+1.0Q+1.4EY'); [print('cs', cs, 'NO PASA en las 5 combinaciones:', sum(sum(1 for x in c['demandas'] if not x['pasa']) for c in ex.construir_anexo('conjunto', ['--cs', cs])[0]['casos'] if c['nombre'] in C)) for cs in ('0.05', '0.10', '0.20')]"
.\.venv\Scripts\python.exe -c "import re,io; t=io.open('semana03/parametros.json',encoding='utf-8').read(); i=t.find('_coeficiente'); print(t[i-40:i+400])"
```
El primero rearma el conjunto con cada `cs` **en memoria** (no escribe
nada) y da 30 / 75 / 146, comprobado el 18-09. Corregido en la revisión
adversarial: antes aquí iba `semana03\demanda_capacidad.py lt2 --todas --cs
0.05`, que **no mide esto**: sin `--comb`, `--todas` revisa `G + Q` sin
sismo (`semana03/demanda_capacidad.py:393-394`), así que el `--cs` no cambia
nada de lo que imprime, y además corre el LT2 solo y no el conjunto.
Lo que falta y no está en el repo: la zona sísmica (`A0`), el tipo de suelo,
el `R` y el coeficiente de importancia `I`. Dónde se lee cada uno en
NCh433 Of.1996 Mod.2009 —corregido el 18-09, antes esta línea mandaba a
buscarlo todo en "6.2.3 y Tabla 6.4", y ahí no está el `R`—:

| dato | dónde |
| --- | --- |
| corte basal `Q0 = C·I·P` y la fórmula de `C` | §6.2.3 |
| tope `C_max` (función de `R`) | Tabla 6.4 |
| mínimo `C ≥ A0·S/6g` | §6.2.3.1.2 |
| `R` y `R0` por sistema estructural | Tabla 5.1 |
| coeficiente de importancia `I` por categoría de ocupación | Tabla 6.1 |
| `A0` por zona sísmica | cap. 4 (zonificación) |
| parámetros del suelo (`S`, `T'`, `n`, `p`) | **DS61 MINVU 2011**, que reemplazó la clasificación de suelos original de NCh433 |

(Confirmar la numeración exacta contra el ejemplar de la norma antes de
citarla en el informe; lo que no cambia es que el `R` **no** sale de §6.2.3
ni de la Tabla 6.4 —esa es el tope de `C`— y que el suelo de un proyecto
posterior a 2011 se clasifica con el DS61.) Todo esto se lee de la norma y
del enunciado, no del código.

**Costo.** Cambiar el número es gratis (`--cs`). Lo que cuesta es la
justificación: dejar escrito en `parametros.json` de dónde sale, y en el
informe que el mapa se compara con demanda mayorada contra capacidad
nominal. Medio día, casi todo de escritura.

**De quién es.** `semana03/parametros.json` es compartido: decisión de Pedro,
avisar. El texto del informe, Pedro.

---

### 1b. El sismo se mayora en un solo sentido y falta `0.9G ± 1.4E`

*(Agregado en la revisión adversarial del 18-09: no estaba en la lista.)*

**Qué revisar.** Que las combinaciones del mapa sean las de NCh3171. Hoy
`semana03/parametros.json:113-154` declara cinco: `S3`, `1.4G`,
`1.2G+1.6Q`, `1.2G+1.0Q+1.4EX` y `1.2G+1.0Q+1.4EY`. Faltan dos cosas que la
norma pide:

- el sismo en **los dos sentidos** (`±EX`, `±EY`). En un modelo lineal
  `−E` no es la misma demanda: cambia el signo del axial sísmico, así que
  la pata de núcleo que hoy está comprimida pasa a traccionada y al revés;
- **`0.9G ± 1.4E`**, la combinación con gravedad mínima, que es la que
  manda en tracción de muros y de columnas de borde.

La propia Semana 5 ya lo sabe: `semana05/estados_s5.json` deja mover EX y
EY "de −1.4 a 1.4 porque el sismo actúa en los dos sentidos", y
`semana05/test_contrato_semana05.py:440` prueba un `0.9G − 1.0EY`. Pero el
anexo y el mapa D/C no los usan.

**Evidencia medida.** Recombinando los casos base del anexo del conjunto
(el mismo método que reproduce las 5 de hoy exactas):

| combinación que falta | NO PASA | de ellas `u = 9999` |
| --- | --- | --- |
| 1.2G+1.0Q−1.4EX | 13 | 3 |
| 1.2G+1.0Q−1.4EY | 44 | 3 |
| 0.9G+1.4EX | 15 | 7 |
| 0.9G−1.4EX | 18 | 5 |
| 0.9G+1.4EY | 34 | 2 |
| 0.9G−1.4EY | 43 | 4 |

En la envolvente, los **elementos** que fallan pasan de **48 a 74**
(columnas de Ingeniería 24 → 37, muros de Ingeniería 20 → 27, muros del
LT2 **4 → 10**; las 40 columnas del LT2 siguen sin fallar). Los seis muros
nuevos del LT2 son 200014 (u 1.72), 200015 (2.12), 200016 (tracción, 9999:
es la pata que hoy está comprimida con +9962 kN en el ítem 5), 200030
(1.08), 200031 (1.01) y 200032 (2.60).

**Efecto esperado en el D/C.** +26 elementos que fallan (+54 %). Es el
mayor efecto **optimista** medido en toda la lista, y no depende de ningún
dato del plano: es una omisión de la revisión. Interactúa con el ítem 10
(curva de un solo signo): con `−E` el momento cambia de signo, y en los
muros con el fierro descentrado eso importa.

**Cómo comprobarlo** (no escribe nada):
```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path[:0]=['semana04','comun','semana03']; import exportar_unity as ex, demanda_capacidad as dc; d=ex.construir_anexo('conjunto')[0]; E={e['id']:e for e in d['elementos']}; F=[[{'P_kN':p,'M_kNm':m} for p,m in zip(f['P'],f['Mn'])] for f in d['familias']]; B={c['nombre']:{x['id']:x['f'] for x in c['esfuerzos']} for c in d['casos'] if c['nombre'] in ('G','Q','EX','EY')}; fam={x['id']:x['familia'] for x in d['casos'][0]['demandas']}; u=lambda l,i:(lambda dm:(lambda Mn: dm['M_kNm']/Mn if Mn>1e-9 else 9999)(dc.capacidad_en(dm['P_kN'],F[fam[i]])))(dc.demanda(dc.combinar({c:B[c][i] for c in l},l),E[i]['tipo'],E[i]['momento_en_el_plano'] or None)); L5=[{'G':1,'Q':.5,'EX':1},{'G':1.4},{'G':1.2,'Q':1.6},{'G':1.2,'Q':1,'EX':1.4},{'G':1.2,'Q':1,'EY':1.4}]; L6=[{'G':1.2,'Q':1,'EX':-1.4},{'G':1.2,'Q':1,'EY':-1.4},{'G':.9,'EX':1.4},{'G':.9,'EX':-1.4},{'G':.9,'EY':1.4},{'G':.9,'EY':-1.4}]; f=lambda LL:sum(1 for i in fam if max(u(l,i) for l in LL)>1); print('elementos que fallan: 5 combinaciones', f(L5), '; con las 6 que faltan', f(L5+L6))"
```
Da `48 ; 74` (comprobado el 18-09).

**Costo.** Bajo: seis entradas más en `"combinaciones"` de
`semana03/parametros.json` y reexportar. El anexo pasa de 9 a 15 casos
(+60 % de tamaño en `data/unity/semana04.json`) y Unity los lee de la lista,
pero hay que revisar que el panel y `comparar_unity.py` no supongan 9 casos
fijos. Hay que actualizar los conteos publicados en `reports/semana04.md` y
`reports/semana05.md`.

**De quién es.** `semana03/parametros.json` es compartido: decisión de
Pedro, avisar.

---

### 2. Ingeniería se queda con el 8 % del largo de muro sobre el nivel ±0.00

**Qué revisar.** Que la tabla de "en qué pisos existe cada muro" siga siendo
la de las plantas, y **declarar la deriva medida en el informe**. Esto no es
un error: es lo que hace fallar 44 de las 51 filas de columna y buena parte
de las 51 de muro, y hoy no está dicho en ninguna parte.

**Por qué se sospecha.** `edificios/ingenieria/benchmark_3d.py:611-639`
declara que *cada muro sube solo hasta donde lo muestran las plantas* y que
*sobre el nivel ±0.00 solo sobrevive el núcleo de escalera/ascensor*, porque
los muros de la fundación incluyen los **muros de contención** del
subterráneo, que existen solo bajo tierra. O sea: está decidido a propósito
y contrastado contra la planta de cielo de cada piso. Lo que no está hecho
es mirar la consecuencia.

**Evidencia medida.** Largo total de muro y rigidez, por cota de arranque:

| cota (conjunto / ing) | muros | largo de muro | Σ E·I en Y |
| --- | --- | --- | --- |
| −7.97 / 0.00 | 19 | 117.39 m | 3.863e9 |
| −4.01 / 3.96 | 16 | 90.04 m | 1.099e9 |
| −0.05 / 7.92 | **7** | **18.51 m** | **2.045e7** |
| +3.91 / 11.88 | 7 | 18.51 m | 2.045e7 |
| +7.87 / 15.84 | 7 | 18.51 m | 2.045e7 |

La rigidez lateral en Y cae **54 veces** en un piso. Deriva de entrepiso
medida con el caso **E solo** (sin 1.4 y sin gravedad), que es como la
controla NCh433 §5.9: en el **centro de masa** no más de 0.002·h (5.9.2), y
en cualquier punto de la planta no más de la del centro de masa + 0.001·h
(5.9.3):

| deriva | −7.97→−4.01 | −4.01→−0.05 | −0.05→3.91 | 3.91→7.87 | 7.87→11.83 |
| --- | --- | --- | --- | --- | --- |
| EY, Ing., centro de masa (límite 0.002) | 0.00002 | 0.00008 | **0.00205** | **0.00255** | 0.00149 |
| EY, Ing., punto más desplazado | 0.00002 | 0.00014 | **0.00343** | 0.00348 | 0.00212 |
| límite 5.9.3 de ese punto (CM + 0.001) | 0.00102 | 0.00108 | 0.00305 | 0.00355 | 0.00249 |
| EY, LT2, punto más desplazado | 0.00035 | 0.00081 | 0.00100 | 0.00102 | 0.00096 |
| EX, Ing., punto más desplazado | 0.00002 | 0.00005 | 0.00052 | 0.00071 | 0.00070 |

(Corregida en la revisión adversarial del 18-09. "Punto más desplazado" =
máximo de `|Δu|/h` sobre todos los elementos verticales del cuerpo en ese
entrepiso; "centro de masa" = el `u` del diafragma llevado al centroide de
las cargas G de las barras del piso con `u_i = u_m + rz·(x_i − x_m)`. La
tabla anterior daba 0.00333 / 0.00407 / 0.00186 para EY en Ingeniería sin
decir dónde se midió, y no se pudo reproducir con ninguna de las dos
definiciones. También comparaba contra 0.002 una fila de
`1.2G+1.0Q+1.4EY`, y eso no corresponde: la deriva de NCh433 se revisa con
el sismo de diseño sin mayorar y sin la gravedad. Ojo además con
`comun/sismo.py --detalle`: lo que rotula "u del centro de masa" es el `u`
del **nodo maestro** (`comun/sismo.py:254` y `:282`), que no está en el
centro de masa.)

Leído así, Ingeniería en Y **sí** se pasa, pero mucho menos de lo que se
decía: en el centro de masa, 1.03 y 1.28 veces el límite en los entrepisos
−0.05→3.91 y 3.91→7.87; en el punto más desplazado, 1.12 veces el permitido
solo en el primero de ellos. No es "2 a 2.9 veces".

Y las 51 filas de columna que fallan están **todas** en esos tres pisos
altos (17 + 14 + 20); en los dos pisos bajos, cero. Los muros que fallan son
justamente los 7 que suben (`muro_1, 2, 3, 17, 18, 19, 20`) más `muro_13`.
El propio `comun/sismo.py conjunto EY` ya grita: "torsión EXTREMA" en 8 de
10 pisos, con `u_max/u_prom` entre 1.539 y 1.714.

**Efecto esperado en el D/C.** Es la explicación estructural de ~80 de las
110 filas. No es un botón que las apague: si el plano dice que arriba solo
hay el núcleo, **el edificio de verdad tiene un piso blando en Y** y eso es
el hallazgo del informe. La magnitud de la deriva (1.03 a 1.28 veces el
límite en el centro de masa, tabla de arriba) está calculada con el `cs`
del ítem 1, cuyo nivel no está declarado, y con la fuerza aplicada en el
nodo maestro y no en el centro de masa, así que **no es todavía un
incumplimiento de norma**: es un indicador.

**Cómo comprobarlo.**
```powershell
.\.venv\Scripts\python.exe comun\sismo.py conjunto EY --detalle
.\.venv\Scripts\python.exe -c "import json,collections; d=json.load(open('data/unity/semana04.json',encoding='utf-8')); m=json.load(open('data/modelo/conjunto.json',encoding='utf-8')); N={n['id']:n for n in m['nodos']}; t=collections.Counter(); [t.__setitem__(round(min(N[e['n1']]['z'],N[e['n2']]['z']),2), t[round(min(N[e['n1']]['z'],N[e['n2']]['z']),2)]+max(e['b'],e['h'])) for e in d['elementos'] if e['tipo']=='muro' and e['seccion'].startswith('ingenieria:') and abs(N[e['n2']]['z']-N[e['n1']]['z'])>0.5]; [print(f'z={z:7.2f} (ing {z+7.97:5.2f}): {t[z]:7.2f} m de muro') for z in sorted(t)]"
```
En el plano: las plantas de cielo de los pisos 2.º, 3.º y 4.º del 2017_67,
para confirmar que sobre ±0.00 solo están las 12 corridas del núcleo.

**Ojo, un detalle que no cuadra:** la tabla del comentario de
`benchmark_3d.py:619-621` dice "largo presente 168.3 / 105.0 / 78.8 / 13.1 /
13.1 / 13.1 m" y el modelo trae 117.39 / 90.04 / 18.51 / 18.51 / 18.51.
Puede ser diferencia de definición (largo en la **planta** contra largo en el
**piso**), pero hay que cuadrarlo antes de citar cualquiera de los dos.
(Revisión adversarial: con ninguna de las dos lecturas cuadra. Si cada
columna del comentario es la losa que **corona** el piso, el modelo trae
117.39 contra 105.0, 90.04 contra 78.8 y 18.51 contra 13.1 m: siempre más,
y +41 % arriba. Y arriba el modelo tiene **7** muros donde el comentario
habla de **12 corridas**. Si el modelo tuviera más muro que el plano sobre
±0.00, el piso blando real sería peor que el modelado.)

**Costo.** Cero si es solo declararlo (media jornada de informe, con esta
tabla). Alto si al mirar la planta faltan muros: agregarlos al perfil,
rearmar Ingeniería y el conjunto, reexportar y correr la suite.

**De quién es.** Eduardo (`edificios/ingenieria/`). Hay que avisarle: es el
hallazgo más importante de su cuerpo.

---

### 3. La parrilla de Ingeniería: nudos de piso sin ninguna columna debajo, que inventan momento

**Qué revisar.** Si en `(43.02, 55.20)` y en los otros nudos colgados el
plano 2017_67 pone pilar, o si esas vigas son secundarias apoyadas en otra
viga (y entonces no van empotradas). Son las **únicas 7 fallas que no
dependen del sismo**.

**Por qué se sospecha.** Hay nudos de piso a los que no llega ningún
elemento vertical, en ningún piso de su misma vertical. Las vigas que
llegan ahí descargan su reacción sobre las vigas que cruzan, y esas quedan
trabajando como vigas de transferencia del doble de luz, con una diferencia
de flecha de casi 19 mm entre el nudo colgado y sus columnas.

**Evidencia medida.** Nudo `100599` en (43.02, 55.20, 11.83):
`uz = −22.303 mm` bajo G, **ningún** elemento vertical, y cero verticales en
su misma (x, y) en cualquier piso. Sus dos vecinos a 5 m sí tienen columna:
`100592` con −5.226 mm y `100606` con −3.461 mm. La viga `100245`
(`viga_x` 0.30 × 0.60, L = 5.00 m, w = −23.875 kN/m) sale con
`My = −480.4` en un extremo y `+488.4` en el otro bajo **G sola**, cuando
`w·L²/12 = 49.7 kN·m`. Ese momento entra directo al nudo de techo de la
columna `100080`, que es la peor del edificio en gravedad.

*Corregido en la revisión adversarial: antes decía "flecha diferencial
pura, no carga", y no es así.* El 49.7 compara contra la luz equivocada.
Al nudo 100599 llegan las vigas en Y `100380` (7.5 m) y `100381` (8.9 m),
que le descargan 127.5 + 158.6 ≈ **286 kN** bajo G; ese nudo no tiene
columna, así que la línea en X 38.02 → 48.02 (`100242` + `100245`) trabaja
como **una viga de 10 m con 286 kN en el centro**, y los reparte hacia las
dos columnas (cortes 152 y 134 kN en el nudo). Una viga empotrada de 10 m
con esa carga da `P·L/8 + w·L²/12 = 358 + 199 ≈ 556 kN·m` en los apoyos y
`≈ 457` al centro; el modelo da 577 / 488 en los apoyos y 481 al centro.
O sea: el momento **sí** lo produce carga, es el camino de carga de un nudo
sin apoyo, y la flecha de 22 mm es su consecuencia, no su causa.

Las 7 fallas sin sismo, todas columnas, todas en el último piso
(cota ing 15.84) y todas en el extremo **`j (superior)`**, el nudo de techo,
donde no hay columna arriba con la que repartir el momento:

| caso | id | P (kN) | M (kN·m) | Mn | u |
| --- | --- | --- | --- | --- | --- |
| 1.4G | 100080 | 900.1 | 423.1 | 358.4 | 1.181 |
| 1.4G | 100066 | 426.6 | 327.6 | 307.3 | 1.066 |
| 1.4G | 100081 | 481.4 | 315.7 | 313.5 | 1.007 |
| 1.2G+1.6Q | 100080 | 1089.6 | 513.6 | 374.0 | 1.373 |
| 1.2G+1.6Q | 100066 | 514.5 | 412.5 | 317.2 | 1.300 |
| 1.2G+1.6Q | 100081 | 572.8 | 382.6 | 323.8 | 1.182 |
| 1.2G+1.6Q | 100079 | 471.3 | 315.1 | 312.4 | 1.009 |

Y un indicio (no una prueba): clasificando las 82 columnas de Ingeniería
según tengan o no un vecino colgado con más de 5 mm de diferencia de
flecha, en 1.2G+1.6Q fallan 3 de las 48 "con vecino colgado", 1 de las 8
intermedias y **0 de las 26 limpias** (u mediana 0.427 contra 0.189). Con 4
fallas en 82 columnas, que ninguna caiga entre las 26 limpias tiene
probabilidad ≈ 0.21 por azar, así que el conteo solo no prueba nada; lo que
sí separa es la mediana.

**Efecto esperado en el D/C.** Depende de lo que diga el plano, y por eso
**no** es pesimista sin más (corregido en la revisión adversarial):

- si en (43.02, 55.20) **hay pilar**, al modelo le falta y los 7 NO PASA de
  gravedad se van completos; además baja la parte de gravedad de las 68
  filas que combinan G con sismo (S3, +1.4EX, +1.4EY). Ahí es **PESIMISTA**;
- si **no hay pilar**, el camino de carga es real: las 7 fallas son del
  edificio, y lo que falla primero es la viga de 10 m 0.30 × 0.60, que
  lleva 577 kN·m bajo G sola y **no se revisa** (ver "Las vigas" en lo que
  no se pudo medir). Ahí el mapa es **OPTIMISTA**, porque la falla está en
  un elemento que no pinta.

Articular las vigas en la columna no es una salida: en un marco de
hormigón vaciado en sitio la viga llega monolítica, y articularla solo
mueve el momento de la columna al tramo de la viga.

**Cómo comprobarlo.**
```powershell
.\.venv\Scripts\python.exe -c "import json; d=json.load(open('data/unity/semana04.json',encoding='utf-8')); m=json.load(open('data/modelo/conjunto.json',encoding='utf-8')); N={n['id']:n for n in m['nodos']}; g=[c for c in d['casos'] if c['nombre']=='G'][0]; U={x['id']:x for x in g['desplazamientos']}; S={x['id']:x for x in g['esfuerzos']}; print('nodo 100599 uz =', U[100599]['uz']*1000, 'mm'); print('viga 100245 My extremos =', S[100245]['My'][0], S[100245]['My'][-1], ' w =', S[100245]['w'][2], ' wL2/12 =', abs(S[100245]['w'][2])*25/12)"
```
En el plano: la planta del piso 4.º del 2017_67, coordenadas
(43.02, 55.20) y las otras intersecciones de la parrilla que quedan sin
pilar. Si el plano pone pilar, **falta un pilar en el modelo**; si son vigas
secundarias apoyadas en la viga en X, el camino de carga del modelo es el
real y lo que hay que mirar es esa viga en X (sección y fierro), no los
empotramientos.

**Costo.** Diagnóstico: hecho. Arreglo: si falta un pilar, agregarlo al
perfil y rearmar (medio día); si no hay pilar, la viga de transferencia
necesita su sección real del plano y una revisión de vigas, que hoy no
existe.

**De quién es.** Eduardo (`edificios/ingenieria/benchmark_3d.py`, la
parrilla y las secciones de viga están en las líneas 409-410 y 590-616).

---

### 4. La rama de tracción de la curva P-M tiene UN solo punto: de ahí salen los `u > 15` (los `u = 9999` no)

**Qué revisar.** Densificar el muestreo de la curva en tracción y dejar de
informar `9999` como si fuera un cociente. Es lo que hace que el mapa se vea
catastrófico.

**Por qué se sospecha.** `comun/capacidad.py:753-755` muestrea la curva en
diez niveles de axial, **todos ≥ 0** (`0.0` a `0.80` de `P_compresion`), y
`comun/capacidad.py:757` agrega un único punto en tracción, la tracción pura
`(P = −As·fy, M = 0)`. Entre ese punto y `P = 0` la capacidad es una **recta
de dos puntos**, y la demanda sísmica de los muros cae justo ahí. Fuera del
rango, `semana03/demanda_capacidad.py:209` devuelve `Mn = 0` y
`semana04/exportar_unity.py:562` lo convierte en `u = 9999`.

**Evidencia medida.** Las 54 familias tienen 12 puntos y **exactamente 1**
con `P < 0`. Los 19 `u = 9999` del anexo están los **19 en tracción**, cero
en compresión. `P_traccion_pura = As·fy` exacto (familia 36: As = 51.91 cm²
→ −2180.1 kN). La zona es hipersensible: el elemento 200012 en
1.2G+1.0Q+1.4EX está a `P = −5874.7` contra una tracción pura de −5882.5
(99.9 % del camino) y da `Mn = 12.1` → `u = 51.653`; un 1 % más de tracción
lo saca de la curva y un 5 % menos lo deja en `u ≈ 1.34`. O sea 38 veces de
cambio en `u` por un 5 % de `P`.

**Efecto esperado en el D/C.** *(Corregido en la revisión adversarial del
18-09; antes decía que densificar "borra todas las magnitudes absurdas" y
que "4 de los 19 `9999` pasan a `u < 1`".)* Rehaciendo la corrida M-φ al
`P` exacto de cada demanda, con la sección tal cual y espejada:

| elemento | caso | `u` publicado | `u` exacto | `u` exacto, sentido contrario |
| --- | --- | --- | --- | --- |
| 200012 | 1.2G+1.0Q+1.4EX | 51.653 | 0.100 | **435.6** |
| 200028 | S3 | 17.620 | 0.196 | 2.047 |
| 100508 | 1.2G+1.0Q+1.4EY | 23.956 | 5.407 | 7.107 |
| 100493 | EY | 15.689 | 3.637 | 4.767 |

- En los dos muros de Ingeniería (fierro casi centrado) el `u` baja de
  16-24 a 3.6-7.1 y **siguen fallando**: ahí el mapa exagera el tamaño de
  la falla, no su existencia.
- En los dos del LT2 (fierro descentrado, ítem 7) el resultado depende del
  **sentido** del momento: 0.10 en uno y 436 en el otro. Como el sismo va
  en los dos sentidos (ítem 1b), densificar la curva sola **no** los
  arregla: hay que densificar **y** revisar los dos sentidos (ítem 10).
- Los 19 `u = 9999` no se mueven con el muestreo: están **fuera** de la
  curva, con tracción más allá de `−As·fy`. Lo de "4 de los 19 pasan a
  `u < 1`" se reprodujo (100479 y 200028 en EX, 100478 en S3, 200028 en
  +1.4EX), pero ese `Mn` existe solo porque la corrida de fibras lleva el
  acero con endurecimiento (`Steel01`, 1 %) hasta `ε_s = 0.10`, o sea a
  ~1.47 `fy`: no es una capacidad nominal. En el sentido contrario esos
  mismos cuatro dan `u` de 1.005 a 964.

El conteo cambia poco (el lente de capacidad midió 110 → 100 con el `Mn`
exacto, contando esos cuatro falsos `u < 1`).

**Cómo comprobarlo.**
```powershell
.\.venv\Scripts\python.exe -c "import json,collections; d=json.load(open('data/unity/semana04.json',encoding='utf-8')); print('puntos con P<0 por familia:', collections.Counter(sum(1 for p in f['P'] if p<0) for f in d['familias'])); n=[(k['nombre'],x['id'],x['P']) for k in d['casos'] for x in k['demandas'] if x['u']>=9999]; print(len(n),'banderas u=9999; en traccion:',sum(1 for _,_,p in n if p<0),'; en compresion:',sum(1 for _,_,p in n if p>0))"
```
`capacidad.interaccion()` ya acepta `niveles=`, así que se puede probar sin
tocar la función.

**Costo.** Bajo: agregar fracciones negativas de `P_traccion` a los
`niveles`. Son ~6 corridas más por familia, y una corrida de M-φ tarda
0.056 s: +20 s para las 54 familias del conjunto. Lo que cuesta es que
cambia números ya publicados, así que hay que reexportar los anexos y
actualizar `reports/semana04.md` y `reports/semana05.md`. Y el rótulo: donde
hoy dice `9999` tiene que decir "muro en tracción neta por encima de su
fierro", con el `As` que haría falta.

**De quién es.** `comun/capacidad.py` y `semana03/` son compartidos: avisar
antes de tocar.

---

### 5. Los muros de núcleo se revisan pata por pata contra su propio `As·fy`

**Qué revisar.** Que un muro que es **una pata de un núcleo** no se compare
solo: el axial que lo saca de la curva es un par interno del grupo, no carga
externa.

**Por qué se sospecha.** Un núcleo se modela como varias columnas anchas
unidas en cada piso por brazos rígidos (`CLAUDE.md` §4). Así resiste el
volcamiento como un **par de axiales** entre sus patas. Después cada pata se
compara sola contra su curva, y la traccionada siempre se pasa.

**Evidencia medida.** El núcleo NE del LT2 son tres patas unidas por una
cadena de brazos rígidos (`200135`, `200136`, `200137`, de 1.3 a 1.6 m, sin
ninguna viga en sus puntas):

| | 200012 (4.85, 59.24) | 200013 (6.17, 60.80) | 200016 (7.50, 60.73) | grupo |
| --- | --- | --- | --- | --- |
| P en 1.2G+1.0Q+1.4EX (P > 0 compresión) | −5874.7 (tracción) | −1053.2 (tracción) | +9962.3 | **+3034.4 → compresión** |

(Signo de la suma corregido en la revisión adversarial: la fila está en la
convención de demandas, `P > 0` compresión, así que el grupo suma **+**3034.4.
El −3034.4 es la misma suma en la convención de esfuerzos, `N > 0`
tracción, que es la que imprime el comando de abajo.) Comprobado además que
**las 19** banderas `u = 9999` son patas de un núcleo unido por brazos: en
Ingeniería los grupos `muro_2/3/18/19` y `muro_1/17/20`, y en el LT2
`200012/13/16` y `200028/29/32`; y que los grupos medidos en
1.2G+1.0Q+1.4EX están en compresión neta (`muro_2/3/18/19` en el piso que
arranca en −0.05: +2133.3 kN; `muro_1/17/20`: +1441.9; `200012/13/16`:
+3034.4).

O sea: el grupo está en **compresión neta de 3034 kN** y una de sus patas se
informa a 99.9 % de su tracción pura con `u = 51.653`. Lo mismo en
Ingeniería: `100478`/`100479` (`muro_17`, `As·fy = −860.3 kN`) llegan a
`P = −1442.9` y `−1513.2`; `100494` (`muro_18`, −1187.5) a −1271.7.

**Efecto esperado en el D/C.** Son las 19 banderas `u = 9999` y los peores
`u` de los dos cuerpos. Revisado como grupo, el `u` de la pata 200012 baja
de 51.65 a del orden de 1.6 (estimación de brazo de palanca del lente de
contraste, **no medido con una sección compuesta**). **PESIMISTA en la
magnitud**: el `u = 51.65` o `9999` de una pata no mide nada. Pero ojo con
el alcance (matiz de la revisión adversarial): revisar pata por pata es un
procedimiento de diseño aceptado (así diseñan los programas comerciales los
"piers"), y el ala traccionada de un núcleo tiene que llevar su tracción con
su propio fierro también en la sección compuesta. La estimación de grupo
**sigue sin pasar** (`u ≈ 1.6`): el grupo cambia el tamaño de la falla, no
necesariamente su existencia.

**Cómo comprobarlo.**
```powershell
.\.venv\Scripts\python.exe -c "import json; d=json.load(open('data/unity/semana04.json',encoding='utf-8')); c=[k for k in d['casos'] if k['nombre']=='1.2G+1.0Q+1.4EX'][0]; S={x['id']:x for x in c['esfuerzos']}; pat=(200012,200013,200016); [print(' pata',p,'N =',S[p]['N'][0]) for p in pat]; print(' suma del grupo =', round(sum(S[p]['N'][0] for p in pat),1))"
```
Da `+5874.7 / +1053.2 / −9962.3` y suma `−3034.4` (en el bloque de
esfuerzos, `N > 0` es tracción; en el de demandas la convención es la
contraria, `P < 0` es tracción). Y para verlo en el modelo: los brazos
`200135`, `200136` y `200137` son los que unen las tres patas.

**Costo.** Barato como aviso: una bandera `pata_de_nucleo` en el dato y una
línea en el panel que diga "este muro es pata de un núcleo, el chequeo pata
por pata no aplica". 2 a 3 horas. Caro de verdad: definir los grupos y armar
la sección de fibras del núcleo completo, 1 a 2 días.

**De quién es.** El dato es de cada cuerpo (Pedro para el LT2, Eduardo para
Ingeniería); la revisión por grupo es `comun/`, avisar.

---

### 6. El Ø16 de las 82 columnas de Ingeniería es el único dato supuesto, y mueve 51 filas

**Qué revisar.** El diámetro longitudinal real de los pilares del 2017_67, o
la justificación del supuesto con la sensibilidad al lado.

**Por qué se sospecha.** *(23-09: ya no es una constante; el diámetro vive
en `perfiles/ingenieria_2017_67.json`, `secciones.columna.fierro`, y desde el
23-09 es Ø22, el mínimo de norma sobre la sección de 70×70 — ver el bloque
de estado al principio. Lo que sigue es como estaba el 18-09.)*
`edificios/ingenieria/enfierradura.py` tenía
`DIAMETRO_LONGITUDINAL_MM = 16.0  # unico dato supuesto`. El dato lo declara
en el JSON (`origen: "numero y disposicion medidos de la lamina 2017_67-000;
diametro SUPUESTO"`, `_procedencia: "El proyecto 2017_67 NO tiene cuadro de
pilares: se revisaron sus 38 laminas"`). Las **82 columnas comparten una sola
familia** con ρ = 1.287 %, y el plano usa Ø16, Ø18, Ø22, Ø25 y Ø28.

**Evidencia medida.** Rehaciendo la curva de la familia 0 solo con otro
diámetro y reevaluando sus 738 comprobaciones:

| diámetro | As (cm²) | ρ | NO PASA de las 738 | total de las 1863 |
| --- | --- | --- | --- | --- |
| **Ø16 (hoy)** | 32.17 | 1.29 % | **51** | **110** |
| Ø18 | 40.72 | 1.63 % | 39 | 98 |
| Ø22 | 60.82 | 2.43 % | 10 | 69 |
| Ø25 | 78.54 | 3.14 % | 2-3 | 61-62 |
| Ø28 | 98.52 | 3.94 % | 0 | 59 |

(Revisión adversarial: rehecho con las barras en la misma posición, da
51 / 39 / 10 / **2** / 0; el 3 de la primera versión puede ser de haber
corrido la barra más gruesa hacia adentro. No cambia la lectura.)

**Efecto esperado en el D/C.** Es el mayor botón único del lado de la
capacidad: hasta −51 filas. *Corregido en la revisión adversarial*: antes
decía que para apagar las fallas "hay que llegar a ρ = 2.4-3.9 %, fuera del
rango normal de una columna (1-2 %)" y que el diámetro "no explica" las
fallas. El rango de norma es 1 % a 8 % (ACI 318-08 §10.9.1, la edición que
cita el repo) y 1 % a 6 % en marcos especiales (§21.6.3.1); en la práctica
2-3 % es corriente en pilares de 50 × 50. Un **16Ø22 (ρ = 2.43 %) es tan
plausible como el 16Ø16**, y con él las fallas de columna bajan de **51 a
10**. O sea: el diámetro **puede explicar** la mayoría de las fallas de
columna, y por eso leerlo del plano es de lo primero que hay que hacer (ver
la nota sobre el orden). Lo que no se puede es elegirlo "para que pase":
sin respaldo del plano, un diámetro alto es **OPTIMISTA**.

Corrección importante respecto de lo que se dijo antes: esta familia aporta
**51** de las 110 filas, no 85. Las 85 eran todas las fallas finitas de
Ingeniería, muros incluidos.

**Cómo comprobarlo.**
```powershell
.\.venv\Scripts\python.exe comun\capacidad.py ingenieria 18 --pm
.\.venv\Scripts\python.exe -c "import json,io; print(io.open('edificios/ingenieria/enfierradura.py',encoding='utf-8').read().splitlines()[68])"
```
En el plano: buscar el cuadro o la llamada de fierro longitudinal de pilar
en las 38 láminas del 2017_67 (el archivo dice que ya se revisaron y no
está). Si sigue siendo supuesto, **la tabla de arriba va en el informe**: es
la pregunta que van a hacer en la defensa.

**Costo.** Una línea si se decide otro supuesto, más rearmar Ingeniería y el
conjunto y reexportar. Barato.

**De quién es.** Eduardo (`edificios/ingenieria/`), y el plano.

---

### 7. El fierro de los muros del LT2: la abscisa `s` no está en el marco del muro

**Qué revisar.** En qué marco viene la coordenada `s` de las barras de
borde. Hay muros donde las barras quedan repartidas **en más ancho que el
muro**, lo que es geométricamente imposible.

**Por qué se sospecha.** `comun/capacidad.py:352` hace
`y = max(-L/2, min(L/2, float(b['s'])))`: supone que `s` ya viene centrada
en el muro y **recorta en silencio** lo que cae fuera, apilándolo contra la
cara. Si `s` viene en el marco de la lámina y no del muro, el fierro queda
descentrado y con recubrimiento cero en el canto.

**Evidencia medida.** De los 85 muros con barras de borde, **23 tienen al
menos una barra recortada y 24 tienen el grupo descentrado más de 2 % de L;
los 23 y los 24 son del LT2** (los 56 muros de Ingeniería reciben su fierro
por espesor, no por bloques con `s`, y ninguno se recorta). En **8 muros el
span de `s` supera el largo del muro**:

| elemento | L (m) | span de `s` (m) | recortadas | y_g barras de borde | y_g sección completa |
| --- | --- | --- | --- | --- | --- |
| 200014 | 1.450 | **1.750** | 5 de 7 | +3.4 % de L/2 | +9.9 % |
| 200015 / 200030 / 200031 | 1.450 | **1.710** | 3 de 5 | +44.8 % | +26.9 / +21.3 / +21.3 % |
| 200062 / 200063 | 1.450 | **1.710** | 2 de 3 | +35.2 % | +11.5 % |
| **200029** | 2.895 | **3.063** | 3 de 8 | +0.4 % | +8.9 % |
| **200045** | 2.895 | **3.193** | 2 de 6 | −25.3 % | −3.0 % |

Y dos que no superan el largo pero tienen el grupo muy corrido:

| elemento | L (m) | span de `s` (m) | recortadas | y_g barras de borde | y_g sección completa |
| --- | --- | --- | --- | --- | --- |
| **200012** | 2.820 | 2.786 | 10 de 25 | −38.3 % | **−29.2 %** |
| **200028** | 2.820 | 2.786 | 3 de 6 | −41.7 % | **−21.9 %** |

(Tablas corregidas en la revisión adversarial: la anterior decía "8 muros"
pero listaba seis de ellos más el 200012 y el 200028, que **no** superan el
largo, y dejaba afuera el 200029, el 200062 y el 200063. El comando de abajo
da exactamente estos 8. La columna "sección completa" es el centroide de
**todo** el acero, malla incluida, que es lo que ve la curva P-M.) En negrita
los cuatro que fallan: los cuatro tienen barras recortadas, pero solo dos
(200012 y 200028) quedan con el acero realmente descentrado; en el 200045 el
−25 % de los bordes lo compensa la malla y queda en −3 %.
Encima de esto siguen abiertos los dos hallazgos de la Semana 4 §9: el
extractor lee `CANT` en vez de `NUM` (181 barras de borde donde el plano da
411) y hay 66 de esas 181 asignaciones que no son del muro (36 horizontales
de dintel y 30 de la elevación perpendicular).

**Efecto esperado en el D/C.** Sobre las 8 filas del LT2. Los dos errores
van en **direcciones opuestas** y por eso hay que arreglarlos juntos: con
`NUM` solo, el LT2 baja de 4 a 1 muro que falla; con `NUM` y sin las barras
ajenas ni los recuentos, quedan 3 (medido por el lente de fierro). El
recorte y el descentrado son lo que después hace que la curva de un solo
signo (ítem 10) importe.

**Cómo comprobarlo.**
```powershell
.\.venv\Scripts\python.exe -c "import json; m=json.load(open('data/modelo/conjunto.json',encoding='utf-8')); S={s['nombre']:s for s in m['secciones']}; mal=[]; [mal.append((e['id'], round(float(e.get('largo') or S[e['seccion']]['largo']),3), round(max(float(x['s']) for x in e['enfierradura']['barras_de_borde'])-min(float(x['s']) for x in e['enfierradura']['barras_de_borde']),3))) for e in m['elementos'] if (e.get('enfierradura') or {}).get('barras_de_borde')]; mal=[t for t in mal if t[2]>t[1]+1e-6]; print(len(mal),'muros con span(s) > L:',mal)"
```

**Costo.** Bajo en `capacidad.py`: cambiar el recorte silencioso por un
error explícito, como ya hace `desde_elemento()` cuando falta el fierro. El
arreglo de fondo está aguas arriba, en el extractor de elevaciones, y es la
misma pasada que el `CANT`/`NUM`.

**De quién es.** Pedro (`edificios/lt2/planos/enfierradura.py`,
`pegar_enfierradura_muros()`); el guardia, `comun/`, avisar.

---

### 8. Once muros del LT2 no se revisan, y uno de ellos sería el peor del edificio

**Qué revisar.** Que un muro sin curva P-M **no se lea como un muro sano**.
Hoy no tienen fila de demanda: no cuentan ni como PASA ni como NO PASA, y en
el mapa van en gris junto a las barras sin fierro.

**Por qué se sospecha.** El anexo arma familias solo con los elementos que
traen fierro (`semana04/exportar_unity.py:351`), lo mismo que
`semana03/demanda_capacidad.py:314-316` (`_lista`) y `:336` (`_todas`,
`'enfierradura' in e`), y `capacidad.desde_elemento()` se cae con "no trae
enfierradura" (`comun/capacidad.py:260`). (Citas corregidas en la revisión
adversarial: antes decía `:311` y `:335`, que son otras líneas.) Los 11 son 10 `M 0.60x2.92` del eje A' (ya declarado en la
Semana 4 §9) **más uno que no está en la lista de abiertos**: el `200013`.

**Evidencia medida.** Los 11 verticales sin familia y su demanda:

- **`200013`** (`M 0.30x2.89`, en 6.17/60.80, cota −7.97): es la pata base
  del **mismo núcleo** cuyos pisos 2 y 3 (`200029` y `200045`) sí fallan con
  `u = 2.212` y `1.248`. Su momento del plano en 1.2G+1.0Q+1.4EX es
  **9988.9 kN·m**, contra 7373.6 del peor muro **del LT2** que sí se revisa
  en esa combinación (el 200029; en todo el conjunto el mayor es el 100449
  de Ingeniería, con 44 795.8, que es mucho más largo). Con la curva de su
  hermano de arriba daría **u = 4.63**; con la del siguiente, 6.04. Sería el
  mayor `u` del LT2 fuera de los dos casos en tracción del ítem 4 (200012 y
  200028), cuyo `u` publicado no significa nada. (Precisado en la revisión
  adversarial.)
- Los 10 `M 0.60x2.92` llegan a **10277.2 kN·m** (`200010`) y 9997.9
  (`200011`) en 1.2G+1.0Q+1.4EY, y no se revisan.

**Efecto esperado en el D/C.** +1 falla casi segura y grande (el 200013; el
4.63 es con la curva prestada de su hermano, ver lo que no se pudo medir) y
10 muros que hoy no se miran. **El conteo de hoy es OPTIMISTA por omisión**: el
LT2 revisa 29 de sus 40 muros.

**Cómo comprobarlo.**
```powershell
.\.venv\Scripts\python.exe -c "import json; d=json.load(open('data/unity/semana04.json',encoding='utf-8')); m=json.load(open('data/modelo/conjunto.json',encoding='utf-8')); N={n['id']:n for n in m['nodos']}; [print(e['id'], e['seccion'], (round(N[e['n1']]['x'],2),round(N[e['n1']]['y'],2),round(N[e['n1']]['z'],2))) for e in d['elementos'] if e['tipo'] in ('muro','columna') and e.get('familia',-1)<0 and abs(N[e['n2']]['z']-N[e['n1']]['z'])>0.5]"
```
En el plano: la elevación del eje del núcleo NE del LT2 en la cota −7.97
(al eje 1' le falta la malla de ese nivel), y el armado de los
`M 0.60x2.92` del eje A' (lámina 303, texto suelto y cortes).

**Costo.** Bajo el aviso: que el mapa y el panel cuenten y nombren los
elementos **sin curva** que están entre los más demandados, en rojo y no en
gris. Medio día. El fierro en sí es la pasada del ítem 7.

**De quién es.** Pedro (`edificios/lt2/`), y el panel es `unity/`.

---

### 9. No hay φ y no hay ningún chequeo de corte: los dos van en contra

**Qué revisar.** Decidir y **escribir** qué es el cociente que se muestra.
Hoy se compara demanda mayorada contra capacidad **nominal**, que es un lado
seguro incompleto.

**Por qué se sospecha.** Un grep de φ, `minora` o factor de reducción en
`comun/`, `semana03/`, `semana04/` y `semana05/` no devuelve nada (las
coincidencias de "phi" son la curvatura del M-φ). Un grep de `Vn`,
`capacidad_corte` o `verificar_corte` en todo el repo: **cero archivos**.
`reports/semana05.md` ya lo declara con estas palabras: "Nominal y sin φ".

**Evidencia medida.** Aplicando un φ = 0.75 plano sobre `Mn` (orden de
magnitud de ACI 318-08 §9.3.2 —21.2.2 en la edición 2014/2019—, entre 0.65
y 0.90), las filas NO PASA de las 5 combinaciones pasan de **75 a 122**
(+63 %). Cortantes que hoy nadie chequea: muro `100426` con V = 2430.4 kN en
1.2G+1.0Q+1.4EX.

*Matiz de la revisión adversarial, medido:* el φ plano de 0.75 exagera. El
φ de flexión depende de la deformación del acero: 0.90 si la sección está
controlada por tracción, 0.65 si por compresión (0.75 es el φ de **corte**).
De las 75 filas que fallan hoy, **24 están en tracción** y **49 bajo el 30 %
de su compresión pura**, o sea casi todas en la zona controlada por
tracción o de transición; solo 2 están más arriba. Con φ = 0.90 el conteo va
de 75 a **84** (+12 %); con 0.75, 122; con 0.65, 152. Y además el `Mn` del
repo ya sale 5-8 % bajo el de Whitney en las columnas (tabla pesimista de
más abajo), así que en la zona de tracción el `Mn` del repo queda muy cerca
de un `φ·Mn` de ACI. La omisión de φ es real pero **chica** comparada con
el ítem 1b; el orden correcto es 84 a 122, no 122.

**Efecto esperado en el D/C.** **AGREGA fallas**, no las quita: de +9 a +47
filas según el φ que corresponda. Del lado de la capacidad es el contrapeso
del ítem 1 (cuya dirección está indeterminada). En muros cortos traccionados
el corte suele mandar **antes** que la flexión, así que la revisión que
falta —el corte— puede ser la que importa.

**Cómo comprobarlo.**
```powershell
Select-String -Path comun\*.py,semana03\*.py,semana04\*.py,semana05\*.py -Pattern 'minora|factor_reduccion|\bVn\b|capacidad_corte'
```
No imprime nada: no existen. El cortante del muro sí está calculado y
guardado, solo que no se compara contra nada:
```powershell
.\.venv\Scripts\python.exe -c "import json; d=json.load(open('data/unity/semana04.json',encoding='utf-8')); c=[k for k in d['casos'] if k['nombre']=='1.2G+1.0Q+1.4EX'][0]; S={x['id']:x for x in c['esfuerzos']}; print('muro 100426: Vy =', S[100426]['Vy'][0], ' Vz =', S[100426]['Vz'][0], 'kN')"
```

**Costo.** Bajo si se declara como decisión y se rotula en el visor: "el
mapa muestra Mu/Mn nominal, sin φ". Medio si se quiere φ de verdad (hay que
sacar la deformación del acero de la corrida de fibras). El corte es trabajo
nuevo, no un arreglo.

**De quién es.** Decisión de Pedro; el texto, el informe; el rótulo,
`unity/`.

---

### 10. La curva P-M es de un solo signo y la demanda usa `|M|`

**Qué revisar.** En los muros con el fierro descentrado hay **dos**
capacidades, una por sentido, y el sismo va en los dos. Hoy se informa una.

**Por qué se sospecha.** `comun/capacidad.py` impone curvatura positiva y
guarda `abs(M)`; `semana03/demanda_capacidad.py:190` hace
`d['M_kNm'] = abs(d[plano])`. Correcto en una sección simétrica; los muros
del LT2 no lo son (ítem 7).

**Evidencia medida.** Rehaciendo la curva con la sección espejada (`y → −y`)
al `P` exacto de la demanda:

| elemento | caso | Mn informado | Mn espejado | u informado | u espejado |
| --- | --- | --- | --- | --- | --- |
| 200029 | 1.2G+1.0Q+1.4EX | 3333.0 | 3885.9 | 2.212 | 1.897 |
| **200045** | 1.2G+1.0Q+1.4EX | 3622.6 | 3362.2 | **1.248** | **1.344** |
| 200012 | 1.2G+1.0Q+1.4EX | 12.1 | 8.6 | 51.653 | 73.240 |

El `Mn` correcto para comparar con `|M|` es el **mínimo de los dos
sentidos**. En el 200045 el valor publicado es el optimista.

**Efecto esperado en el D/C.** *(Medido de nuevo en la revisión
adversarial sobre las 259 filas de muro del LT2 con `Mn > 0`; antes decía
"±14 %", "±10 %" y "la mitad", que no coincidían entre sí.)* La razón
`Mn espejado / Mn publicado` va de 0.705 a 1.553 (p10 0.868, mediana 1.030,
p90 1.317). El publicado es el **optimista en 79 de 259 filas (30 %)**, y
tomar el mínimo de los dos sentidos cambia **un** veredicto: el 200045 en
EX, de 0.979 a 1.063. **Optimista para un tercio de las filas**, y pesa más
cuando se agreguen las combinaciones con `−E` del ítem 1b, que dan vuelta
el signo del momento. (Los `Mn` espejados de la tabla de arriba salen de
interpolar la curva espejada; con la corrida exacta al `P` de la demanda
dan 4002.4, 3375.9 y 1.4.)

**Cómo comprobarlo.** Correr `capacidad.interaccion()` dos veces, con la
sección y con `sec.barras = [(-y, z, a) for (y, z, a) in sec.barras]`, y
comparar al `P` de la demanda.

**Costo.** Medio: duplica el tiempo de las curvas (+30 s para el conjunto) y
cambia los `Mn` publicados de los muros.

**De quién es.** `comun/capacidad.py`, avisar.

---

### 11. La cota del terreno: lo que preguntaste

> **YA ESTÁ HECHO (18-09, después de escribir esto).** Pedro eligió la
> salida 2: el suelo va donde arrancan las columnas. El LT2 declara
> `terreno.z = -7.97` (`provisorio: false`) e Ingeniería estrena
> `edificios/ingenieria/perfiles/ingenieria_2017_67.json` con su `0.00`
> local, que con el `dz = -7.97` del calce es la **misma** cota: el
> conjunto no se cae y queda en −7.97. Los tres JSON reexportados, 41 de
> 41 en la suite, y `comun/test_contrato_unity.py` ahora exige que la
> cota sea la de los apoyos más bajos (lt2 16 apoyos / 8 columnas,
> Ingeniería 29 / 10, conjunto 45 / 18). Lo que sigue abierto es lo de
> abajo: los **39 apoyos en terreno de Ingeniería quedan dibujados 3.96 m
> sobre el suelo** (medido en `data/unity/conjunto.json`), porque el
> terreno real tiene dos N.R. y el visor dibuja un plano. En Ingeniería
> sola no cambió nada: ya dibujaba el suelo en 0.00 por el respaldo.
> `reports/semana05.md` (entregado) sigue diciendo −4.01, `provisorio`.

> **Y LO DE ABAJO TAMBIÉN (18-09, más tarde): la salida 3.** El terreno
> viaja en niveles (`info.terrenos`, `semana05/CONTRATO.md` §11): la base en
> −7.97 y una **terraza** en −4.01 (3.96 del datum de Ingeniería) bajo sus
> 39 apoyos en terreno. La región sale de la misma definición con que
> `benchmark_3d.py` crea esos apoyos (`sobre_subterraneo()`, recortada a la
> caja de los 39 más 0.35 m), el visor la dibuja como pasto con muros de
> tierra (`AmbienteVisor.Terrazas.cs`) y recorta alrededor de lo que baja a
> la base. `comun/test_contrato_unity.py` cuenta los apoyos por nivel: LT2
> 16 en −7.97; Ingeniería 29 en 0.00 y 39 en 3.96; conjunto 45 en −7.97 y
> 39 en −4.01; ninguno flotando ni enterrado. El exportador del conjunto ya
> no aborta por niveles distintos (`terrenos_del_conjunto()`, que reemplazó
> a `cota_terreno_del_conjunto()`); la cita `:262-267` de abajo es del
> código de antes.

> *Revisión adversarial del 18-09: lo que sigue hasta "Costo" es el
> análisis **anterior** al cambio y queda como registro de por qué se
> decidió. Comprobado hoy: `lt2_2024_22.json:197-199` dice `z: -7.97`,
> `provisorio: false`; `data/unity/lt2.json` y `conjunto.json` traen
> `cota_terreno = -7.97` e `ingenieria.json` `0.0` (su datum local). La
> salida 2 de abajo resultó **más simple** de lo que se decía: Ingeniería
> declara su suelo en su propio 0.00, que calzado es −7.97, así que los dos
> cuerpos **no** difieren 3.96 m y el exportador no se cae. Lo que sí queda
> son los 39 apoyos en −4.01 dibujados sobre el suelo.*

**Qué revisar.** Hay que **decidirlo entre los dos cuerpos**, no cambiarlo
de a poco, porque el exportador del conjunto está hecho para caerse si no
coinciden.

**Lo que decía el dato antes del cambio.**
`edificios/lt2/perfiles/lt2_2024_22.json:197-199` declaraba
`terreno.z = -4.01` con `provisorio: true`, y su propia justificación
argumentaba contra tu premisa:

- en −7.97 están los 16 empotramientos del LT2, y con el suelo ahí *"el
  subterráneo se vería como un piso sobre tierra"*, mientras la descripción
  del perfil dice "1 subterráneo + 4 pisos";
- lo confirma el cuerpo vecino: los **39 apoyos en terreno de Ingeniería
  están todos en −4.01**, porque al oriente del eje H el terreno está en esa
  cota, y su planta de fundaciones rotula **dos N.R.: −7.97 y −4.01**
  (fundación escalonada);
- lo que no calza, y por eso es provisorio: la rampa rotula cotas hasta
  −2.81, o sea el terreno puede tener pendiente. Ninguna lámina rotula el
  N.T.N.

**El problema de fondo.** Lo que pediste son **dos cotas distintas para dos
cuerpos separados por una junta de 5 cm**, y el visor dibuja **un solo plano
horizontal**. `edificios/conjunto/exportar_unity.py:262-267` (en el commit
`66e4698`; hoy ya no existe) estaba escrito para **abortar** si los dos cuerpos declaran terrenos que difieren más de 0.01 m:
*"si al calzarlos declaran cotas distintas, uno de los dos supuestos está
mal"*. Antes del cambio solo el LT2 declaraba, así que el conjunto copiaba su −4.01. Si se
pone −7.97 en el LT2 y nada en Ingeniería, el conjunto dibujará el suelo en
−7.97 y los 39 apoyos de Ingeniería quedarán **flotando 3.96 m**.

**Efecto en el D/C: CERO, medido.** Ningún módulo de cálculo lee
`cota_terreno`: solo la leen los exportadores de Unity (hoy tres: el del
LT2, el del conjunto y `edificios/ingenieria/export_unity.py:52`),
`comun/test_contrato_unity.py:214` y `semana05/comparar_unity.py:737`.
Cambiarla mueve el dibujo y no mueve un número.

**Pero sí tiene una consecuencia para la defensa.** Si el piso −7.97/−4.01
del LT2 es un subterráneo (lo que dice el perfil), entonces al modelo le
falta el **empotramiento lateral del terreno** en ese piso, que hoy resiste
el 100 % del corte basal del LT2 con 8 columnas y 8 muros. Si tu premisa es
la correcta y ahí está el suelo, ese piso está sobre tierra y no falta nada.
Medido: la deriva de ese piso (0.00048 en EX) es **menor** que la de los
pisos de arriba (0.00107), así que el apoyo del terreno no cambiaría mucho;
pero la frase del informe cambia.

**Cómo comprobarlo.**
```powershell
.\.venv\Scripts\python.exe -c "import json; [print(f, json.load(open('data/unity/%s.json'%f,encoding='utf-8'))['info'].get('cota_terreno'), 'z minimo:', min(n['z'] for n in json.load(open('data/unity/%s.json'%f,encoding='utf-8'))['nodos'])) for f in ('lt2','ingenieria','conjunto')]"
Select-String -Path comun\calcular.py,comun\capacidad.py,semana03\demanda_capacidad.py -Pattern cota_terreno
```
(lo segundo no imprime nada: ningún cálculo la usa).

**Las tres salidas posibles.**
1. Dejar −4.01 y decir en el informe que el piso bajo del LT2 es
   subterráneo, y que falta el empotramiento lateral. Era lo que había y
   estaba argumentado.
2. Poner −7.97 (tu premisa) y **agregarle a Ingeniería su propio `terreno`**
   para que no quede en el aire. **Es la que se eligió** (18-09); en su
   datum local Ingeniería declara 0.00, que calzado es la misma −7.97, así
   que el conjunto no se cae (la versión anterior de esta línea decía que
   los dos iban a diferir 3.96 m, y no fue así).
3. Terreno escalonado, que es lo que probablemente dice la realidad (dos
   N.R. en la planta de fundaciones). El visor no lo soporta: usa un plano
   horizontal. Es trabajo nuevo en `unity/`.

**Costo.** Opción 1: cero, solo texto. Opción 2: un número en el perfil del
LT2, un bloque `terreno` nuevo en el de Ingeniería y decidir qué hace
`cota_terreno_del_conjunto()`; media jornada y hay que reexportar. Opción 3:
un día en `unity/`.

**De quién es.** El perfil del LT2 es de Pedro; el de Ingeniería, de
Eduardo; `AmbienteVisor` es `unity/`, compartido.

---

## Optimista o pesimista: hacia qué lado empuja cada cosa

Pedro necesita saber si el edificio falla o si el cálculo está mal
calibrado. Hoy hay cosas de los dos lados y **no se compensan por elemento**.

*(Tablas corregidas en la revisión adversarial del 18-09: el sismo pasó a
"indeterminado", la parrilla y la rama de tracción quedaron condicionadas,
y se agregaron las combinaciones que faltan.)*

| **INDETERMINADO** hasta saber qué es el 0.10 | cuánto, medido |
| --- | --- |
| Sismo `V = cs·W` ×1.4 sin R ni I declarados (ítem 1): pesimista si 0.10 es `A0/g` sin reducir; optimista (falta `I = 1.2`) si es el `C` ya reducido, que es lo que sugieren los números de NCh433 | de 30 a 146 filas según `cs` |

| lo que hace el D/C **PESIMISTA** (el edificio se ve peor de lo que es) | cuánto, medido |
| --- | --- |
| Momento de la parrilla de Ingeniería, **si** el plano pone pilar en (43.02, 55.20) | los 7 NO PASA de gravedad (si no hay pilar, son reales) |
| Muros de núcleo revisados pata por pata contra `As·fy` | la magnitud de las 19 banderas `u = 9999`; el grupo tampoco pasa (`u ≈ 1.6`, estimado) |
| Rama de tracción de la curva con un solo punto, en muros con fierro centrado | `u` 23.96 → 5.4 y 15.69 → 3.6 (siguen fallando) |
| Momento tomado en el eje del nudo y no en la cara | −17.5 a −20 % en las columnas |
| `Mn` leído a ε = 0.003 en el borde del núcleo y no en la fibra extrema | `Mn` de columna 5-8 % bajo |
| Fierro de muro leído de menos en el LT2 (`CANT` en vez de `NUM`) | `Mn` hasta +97 % con el arreglo |

| lo que hace el D/C **OPTIMISTA** (el edificio se ve mejor de lo que es) | cuánto, medido |
| --- | --- |
| **Sismo en un solo sentido y sin `0.9G ± 1.4E`** (ítem 1b) | **48 → 74 elementos que fallan**; LT2 4 → 10 muros |
| Ningún chequeo de corte, en ninguna parte | sin medir; V = 2430 kN en el muro 100426 |
| Ninguna viga revisada | la viga de 10 m del ítem 3 lleva 577 kN·m bajo G sola |
| 11 muros del LT2 sin curva: no se revisan | el 200013 daría `u` 4.6 a 6.0 |
| Capacidad nominal, sin ningún φ | 75 → 84 filas con φ = 0.90 (el de tracción controlada); 122 con 0.75 plano |
| Curva de un solo signo con fierro descentrado | 30 % de las filas de muro del LT2; 200045: 1.248 → 1.344; el 200012, al mismo `P`, da `u` 0.10 en un sentido y 436 en el otro |
| Barras ajenas pegadas como borde en el LT2 | `Mn` hasta −33 % al quitarlas |
| Puntas `L:3+3` de Ingeniería (laterales de viga) | `Mn` −7 % a −42 % al quitarlas |
| 20 fibras para un muro de 15 m igual que para un pilar de 0.50 m | `Mn` de muro largo 2-4.5 % alto |
| Compresión pura con `f'c` entero y sin el tope 0.80 de ACI | curva 43-46 % sobre el tope (casi ninguna demanda llega ahí) |

**Lo que hay que poder decir en la defensa:** hoy el mapa compara **demanda
mayorada, con un sismo cuyo nivel (reducido o no por R) no está declarado y
en un solo sentido**, contra **capacidad nominal sin minorar**, y no revisa
corte ni vigas. Es un indicador de dónde mirar, y así lo declara
`reports/semana04.md` §9. Decirlo al revés sería el error.

---

## Lo que YA se descartó, con números

- **"Lo rompió el conjunto / la unión de los dos cuerpos."** No. Comparando
  elemento por elemento y caso por caso contra los anexos de los cuerpos
  sueltos: **0 cambios de veredicto en el LT2** (69 × 9) y 2 marginales en
  Ingeniería, los dos hacia mejor (u 1.012 → 0.994 y 1.007 → 0.995).
- **"Volvió el `f'c` único del conjunto (el LT2 a 28 MPa)."** No. Las 54
  curvas P-M son **idénticas punto a punto** entre cuerpo suelto y conjunto
  (peor diferencia 0.0000 kN·m). `data/modelo/conjunto.json` trae 13
  secciones con `fpc_MPa = 35` y 31 con 28; el `E_kPa` del anexo es
  27 805 575 en los 69 elementos del LT2 y 24 870 062 en los 138 de
  Ingeniería. Comprobado además desde la curva: el extremo de compresión de
  la familia 0 es 8261.1 kN = 28 MPa exacto. **Queda una trampa dormida:**
  `comun/capacidad.py:306` hace `float(propio or ...)`, y en Python
  `0.0 or 28.0` da 28.0, así que una sección con `fpc_MPa = 0` caería al
  material del modelo en silencio. Hoy no hay ninguna (0 de 47), pero el
  anexo escribe `fpc_MPa: 0.0` en los 207 elementos con fierro.
- **"El `fpc_MPa = 0.0` del anexo bajó las capacidades."** No. Es la marca de
  "el E y el G son propios de la sección" (`semana04/exportar_unity.py:298`).
  La capacidad lee el `fpc` de la sección del contrato y las curvas salen con
  35 y 28 donde corresponde. Lo único malo es que el panel de Unity no
  muestra el `f'c` justo en el modelo donde hay dos hormigones.
- **"Los muros se comparan con el momento fuera de plano" (el error de la
  Semana 4).** No, el guardia funciona: los 56 muros de Ingeniería traen
  `momento_en_el_plano = "My"` y los 29 del LT2 `"Mz"`, consistente con sus
  inercias, y en los muros que fallan el momento del plano es de 20 a 1000
  veces el de fuera de plano.
- **"Demandas fuera de la curva por compresión."** No: los 19 `u = 9999`
  están los **19 en tracción**; 0 de 1863 tienen `P` por encima del extremo
  de compresión de su curva.
- **"Falta el nivel del suelo en el patrón del sismo del LT2."** No. La cota
  base es el `z` mínimo de todos los nodos: −7.97 en el LT2 (justo donde
  arrancan columnas y muros) y 0.00 en Ingeniería, que tras el calce queda
  también en −7.97. Las alturas del patrón salen 3.96 / 7.92 / 11.88 /
  15.84 / 19.80 m en los dos cuerpos.
- **"Las derivas están enormes en todas partes."** No. En X ningún nivel de
  ningún cuerpo pasa de 0.00113 (límite 0.002), y el LT2 en Y tampoco
  (peor 0.00102 en EY). El problema es **solo Ingeniería en Y**, y solo en
  sus tres pisos altos.
- **"El LT2 falla masivamente."** No. Sus 40 columnas pasan en los 9 casos,
  **0 de 360 comprobaciones**. De sus 261 comprobaciones de muro fallan 8,
  en 4 elementos, y ninguna en G, Q, EY, 1.4G, 1.2G+1.6Q ni
  1.2G+1.0Q+1.4EY.
- **"Las inercias brutas inflan la demanda."** No, y va al revés: agrietar
  con los factores de ACI (vigas 0.35, pilares 0.70, muros 0.70)
  **empeora** el D/C (los NO PASA del núcleo NE pasan de 3 a 7, y la
  tracción del 200012 de −5355.9 a −8006.3 kN).
- **"El peso propio está aplicado dos veces."** No. El único `eleLoad` de
  `comun/servidor_opensees.py` es la línea 514 y no hay `ops.mass` ni
  gravedad propia: G aplicada −34 148.9792 kN contra reacción por GDL
  +34 148.9791, error 1.41e-04 kN.
- **"El cociente biaxial de las columnas infla el `u`."** Poco. En las 51
  filas de columna que fallan, la razón `min/max(My, Mz)` tiene mediana
  0.170 y p90 0.677: en la gran mayoría manda un solo eje.
- **"La discretización explica las fallas de las columnas."** No. En el
  elemento 100042 el `Mn(P=0)` va 255.5 / 256.5 / 256.6 / 256.7 para 8 / 20
  / 40 / 60 fibras: 0.06 % entre 20 y 60. El problema de las 20 fibras
  existe, pero es de los muros largos.
- **"El confinamiento infla el `Mn` de las columnas que fallan."** No, y va
  al revés: medido con estribo contra sin estribo, el confinamiento **resta**
  entre 1.5 % y 3.9 % del `Mn` en el punto nominal, porque a ε = 0.003 el
  núcleo confinado va a mitad de camino.
- **"El benchmark de Semana 1 se rompió."** No: corrido hoy, `UZ` techo
  −0.06348 mm = referencia, y contra SAP2000 (−0.06375) sigue en 0.42 %.

---

## Lo que no se pudo medir

- **Cuánto de la torsión de EY es real y cuánto la mete el punto de
  aplicación de la carga.** La fuerza de cada nivel se aplica en el nodo
  maestro del diafragma, que no está en el centro de masa: la excentricidad
  medida llega a 9.35 m en Ingeniería (18.6 % del ancho) y 5.29 m en el LT2.
  Separarlo exige volver a resolver EY aplicando la fuerza en el centro de
  masa, y eso escribe en `data/resultados/`. *(Revisión adversarial: con el
  centro de masa tomado como el centroide de las cargas G de las barras de
  cada piso, la distancia maestro–CM da 1.2 a 1.9 m en Ingeniería sobre
  ±0.00 (3.95 m en −4.01) y 0.7 a 1.1 m en el LT2. El 9.35 m no se
  reproduce con esa definición; hay que decir cuál se usó antes de
  citarlo. Y NCh433 pide además una torsión accidental, que el repo no
  aplica.)*
- **El efecto del `φ` elemento por elemento.** El 75 → 122 de arriba usa un
  `φ = 0.75` plano; con `φ = 0.90`, el de las secciones controladas por
  tracción, que es donde están casi todas las fallas, da 84. El `φ` de
  verdad depende de la deformación del acero en el punto nominal, que hay
  que sacar de la corrida de fibras.
- **El corte.** No existe en el repo. Habría que escribir el `Vn` de muro y
  de columna para saber cuánto falla; en muros cortos traccionados es
  probable que mande antes que la flexión.
- **Las vigas.** 730 de los 937 elementos no tienen ninguna revisión, y
  **ninguna viga se revisa a flexión**. Hay vigas de Ingeniería de 10 m con
  0.30 × 0.60 (L/h = 16.7) que llegan a 410 kN·m bajo G sola y a 714 kN·m en
  1.2G+1.6Q; un 0.30 × 0.60 con un fierro razonable da del orden de 300-320.
  (La línea en X del ítem 3, dos vigas de 5 m sin apoyo en el medio, llega
  a 577 kN·m bajo G sola en el apoyo de 38.02.) Es probable que sea el
  problema más grande del edificio y no aparece en ningún NO PASA. Falta
  extraer el fierro de vigas.
- **El `u` real del `200013`** (el muro sin curva del ítem 8): sin inventarle
  una enfierradura no se puede cerrar. Lo medido es su demanda
  (9988.9 kN·m); el 4.63 es con la curva de su hermano.
- **La capacidad del núcleo como grupo.** El `u ≈ 1.6` del 200012 revisado
  en grupo es una estimación de brazo de palanca, no una sección de fibras
  compuesta.
- **Si el plano respalda lo que dice el modelo.** No se abrió ningún DXF. Que
  los muros de Ingeniería se corten sobre ±0.00, que las vigas de 10 m sean
  0.30 × 0.60 y que en (43.02, 55.20) no haya pilar son hechos **medidos en
  el modelo**. Si eso es lo que dice el plano o es un error de extracción es
  exactamente lo que hay que ir a mirar, y es lo que decide si los ítems 2 y
  3 son hallazgos del edificio o del código.
- **Dos marcos de coordenadas.** Los informes citan el mismo muro en dos
  sitios distintos porque el conjunto desplaza el LT2 en
  (−35.082, +36.904): el `200013` está en (6.17, 60.80) en el conjunto y en
  (41.255, 23.899) en el modelo del LT2 suelto. No es una contradicción, pero
  conviene decir siempre en qué marco se está.

---

## Aparte: las dos cosas que pediste que no son del D/C

1. **La cota del terreno**: **HECHO el 18-09** (ítem 11). El suelo quedó
   en −7.97 en el LT2 y en el conjunto, y en el 0.00 local de Ingeniería,
   que calzado es la misma cota. El dibujo de los 39 apoyos de Ingeniería
   en −4.01 se resolvió después, el mismo 18-09: terreno en dos niveles, con
   una terraza en −4.01 (ítem 11). Efecto en el D/C: cero, medido.
2. **Las columnas en color salmón** (con las losas tal cual están):
   **HECHO el 18-09**, en `unity/Assets/Scripts/AmbienteVisor.cs`, un solo
   color: `C_COLUMNA` pasó de `(0.74, 0.73, 0.70)` a `(0.87, 0.69, 0.63)`,
   la misma luminancia (0.72) y saturación 0.28. Solo la categoría
   `"columna"` de la **vista realista**; losas (`C_LOSA`), vigas y muros
   intactos, y la vista técnica igual (ahí cada renderer vuelve a su
   material registrado). No hubo que tocar el protocolo del mapa D/C
   (`semana05/CONTRATO.md` §8): el color entra por `MaterialRealista()`,
   que es del propio `AmbienteVisor`, y el aviso
   `EventosVisor.AvisarMaterialesCambiados()` sigue donde estaba.
