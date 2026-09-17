# AGENTS.md — Registro de uso de agentes de IA

> Documenta cómo el grupo usa agentes de IA en el proyecto. Es parte de
> la evaluación del curso: lo que importa no es que la IA haya escrito
> código, sino **qué propuso, qué se revisó y qué se corrigió**.

---

## Agentes en uso

| Agente | Para qué | Quién |
|---|---|---|
| Claude Code (Opus / Fable) | modelado desde planos, verificaciones, capacidad, superposición, consolidación del repo | Pedro |
| Claude Code | edificio de Ingeniería, Parte D y visor de Semana 3 | Eduardo |
| Claude Code | scripts de Semana 3, guía de estudio | Monse |

## Criterios de aceptación

1. **Verificación numérica** contra un valor conocido o una propiedad
   que tiene que cumplirse (equilibrio, simetría, conservación).
2. **Equilibrio**: carga aplicada = reacciones, error relativo < 1e-6,
   separado por grado de libertad en los nodos de diafragma.
3. **No romper la arquitectura**: OpenSees calcula, Unity muestra.
4. **Código entendible**: cualquier integrante debe poder explicarlo.
5. **Sin cambios al contrato JSON** sin acuerdo del grupo.
6. **Lo supuesto se declara** en `perfiles/*.json`, con su razón.

## Ciclo de trabajo

```
Issue → Plan → Build → Test (python comun/verificar_todo.py) → Review → Merge
```

Un buen encargo tiene criterio de aceptación: *"leer el fierro de los
40 pilares del LT2; cada uno debe emparejar con un solo elemento del
modelo y el conteo debe cerrar con los rótulos del plano"*. Uno malo:
*"haz la enfierradura"*.

---

## Registro semanal

### Semana 1 — benchmark
- **Tarea:** marco 3D de prueba en OpenSees, validado contra SAP2000.
- **Verificación:** UZ techo = −0.0635 mm (SAP: −0.06375, 0.4 %).
  Equilibrio 0.000000.
- **Corrección:** el agente leía el momento con `eleForce` (ejes
  globales) como si fuera local; en vigas en Y parecía "torsión". Se
  detectó por simetría: vigas X e Y deben dar esfuerzos locales
  idénticos.

### Semana 2 — los dos edificios desde sus planos
- **Tarea:** ingestor de DXF reutilizable, modelo del LT2 y del edificio
  de Ingeniería, unión por la junta de dilatación, áreas tributarias a
  45°, cuatro casos de carga, visor Unity.
- **Corrección 1 — "en Z no hay calce".** El agente afirmó que los dos
  cuerpos compartían cotas comparando la *lista documentada* de niveles
  del edificio de Ingeniería, no su modelo, que estaba en alturas
  relativas. El cuerpo quedó flotando 7.97 m: su base caía en el
  segundo piso del otro. El equilibrio no lo vio (junta libre, cada
  cuerpo cierra solo). Se vio **mirándolo en Unity**. Corregido con
  `dz = −7.97` y una verificación de cotas en `conjunto/armar.py`.
- **Corrección 2 — ΔX medido al eje, no a la cara.** El LT2 quedó 12.5 cm
  metido en la junta. `armar.py` ahora mide caras y avisa si la
  separación no es la declarada.
- **Corrección 3 — el visor mostraba un archivo viejo.** El lanzador
  copiaba a `modelo_unity.json` y la escena abría
  `modelo_unity_edificio.json`. Varias rondas de "arreglos" sin efecto
  hasta leer `Player.log`. Ahora el nombre se lee de la escena.

### Semana 3 — casos base, superposición, capacidad HA
- **Tarea:** Q y EX/EY, superposición verificada contra corrida
  explícita, Fiber Section de columna y muro, curvas P-M, punto de
  demanda de cualquier elemento, verificación RC contra cálculo a mano.
- **Corrección 1 — la verificación de losa acusaba 194 barras.** El
  agente dividía la carga distribuida de G por el área tributaria sin
  descontar el **peso propio** de la barra, que viaja sumado. Se
  comprobó la hipótesis (16 vigas con `wz = 12.0` exacto = 0.48·25) y
  se declaró `incluye_peso_propio` en el caso.
- **Corrección 2 — el módulo elástico del conjunto.** Comparando el LT2
  dentro del conjunto contra el LT2 solo, los desplazamientos salían
  1.1180× mayores en los cinco pisos: √(28/35) = 0.8944. El contrato
  tiene un material y el merge se quedaba con el del primer cuerpo.
  Arreglado con `E`/`G` por sección; `verificar_conjunto.py` impide que
  vuelva.
- **Corrección 3 — "el vecino más cercano".** Para leer el fierro de un
  pilar el agente tomaba la llamada más cercana al rótulo, que es la de
  la **viga** del nudo (`34ED Ø10a10`). Se descubrió renderizando la
  elevación. La búsqueda quedó direccional.
- **Corrección 4 — la cota de redondeo.** La superposición "no cerraba"
  a 2.0e-8 contra una cota de 1.8e-8: faltaba el redondeo de la
  corrida explícita (+1 en Σ|λ|). Con la cota correcta el peor de 45
  casos da 1.000× la cota, no más.
- **Corrección 5 — caché de curvas P-M.** Indexada por número de barras
  y estribo, sin la sección: un muro de 1.45 m se comparaba contra la
  curva de uno de 7.95 m. Tres colisiones.
- **Corrección 6 — el merge de Eduardo.** Su Claude resolvió
  `capacidad_ha.py` a favor de la versión vieja (218 líneas) y perdió su
  propia Parte D (469); y restauró la versión del lanzador que toma el
  primer `nombreArchivo`, que con dos visores es el equivocado. Ambas
  detectadas corriendo la suite sobre el árbol mergeado. (Después su
  exportador se reescribió sobre `comun/capacidad.py` y `capacidad_ha.py`
  se borró del todo: una sola definición de la sección.)
- **Lo que el agente propuso y el grupo aceptó con reparos:** deducir
  el número de barras longitudinales del pilar desde el estribo (una
  traba = una barra intermedia). Es coherente con el plano pero es una
  inferencia; el diámetro sigue siendo supuesto y está declarado así.
- **Lo que el agente no forzó:** 9 de 40 muros quedan sin fierro porque
  sus llamadas `L:` marcan empalmes, no pisos; inventar la regla habría
  sido adivinar. `armar.py` los enumera.

### Semana 3 (avance) — casos base y curvas de interacción
- **Tarea:** las diez secciones del avance en `reports/semana03.md`,
  incluida la curva P-M de muro, que no existía.
- **Corrección 7 — el agente atribuyó a NCh433 un reparto de ASCE 7.**
  Al hacer configurable el patrón en altura documentó, en **cuatro
  archivos**, que `k = 2` era "el límite superior de NCh433 / ASCE 7".
  La forma de potencia `F_i ∝ W_i·h_i^k` es de **ASCE 7 §12.8.3**;
  NCh433 6.2.6 **no usa exponente**, usa
  `A_k = √(1−Z_(k−1)/H) − √(1−Z_k/H)`. El error era plausible —las dos
  concentran fuerza arriba— y por eso pasó la primera lectura. Se
  corrigió la atribución y se implementó el reparto real
  (`--patron nch433`), comprobado a mano en el último nivel
  (`A₅ = 0.4472` → 42.08 %). Al implementarlo apareció que `A_k` debe ir
  por **altura distinta** y no por índice: en el conjunto, con dos
  diafragmas por cota, "el anterior de la lista" daba `A = 0` al segundo
  de cada par.
- **Corrección 8 — una carga viva sin fuente, arrastrada a todo el
  laboratorio.** El modelo traía `w_live_val = 2.0` en `benchmark_3d.py`
  sin comentario ni referencia, y el agente la adoptó como defecto sin
  cuestionarla. Contra **NCh1537 Of.2009 Tabla 4** está por debajo de
  cualquier uso del edificio (salas de clases 3.0, pasillos 4.0). Se
  cambió el defecto a 3.0, la tabla vive en `parametros.json` con
  `--uso`, y `validar()` rechaza un uso y un `q` que no calcen. Al
  verificarlo salió una incoherencia **que el agente había introducido**:
  `demanda_capacidad.py` leía la demanda de `data/resultados/` —el Q a
  2.0— así que `--q` no la movía, y el informe habría dicho 3.0 con la
  tabla a 2.0 sin que nada avisara.
- **Corrección 9 — proponer arreglar algo que no estaba malo.** Ante las
  vigas hundidas del visor, la hipótesis compartida fue que estaban
  partidas y formaban rótula, y la propuesta era unirlas. Antes de tocar
  el modelo se comprobó refinando la malla: 2, 4, 8 y 16 tramos dan
  `uz = −8.8524 mm` **idéntico al cuarto decimal**. La causa es la viga
  secundaria que aterriza ahí con su losa (85 % de la flecha), y la
  flecha es `L/1527`. Probar la solución propuesta la descartó sola:
  una columna bajo ese nodo **empeora** (6.55 → 7.08 mm).
- **Lo que el agente propuso y el grupo aceptó con reparos:** asignar el
  armado de los 56 muros de Ingeniería **por espesor**, y no muro por
  muro. Las once elevaciones dan 66 bloques con espesor y mallas, pero
  el calce elevación→planta pediría resolver ejes secundarios que el
  modelo no conoce. Se aceptó porque los cuatro espesores del modelo son
  exactamente los cuatro de los bloques y en dos el conteo coincide
  (15 cm: 4 y 4; 25 cm: 10 y 10, con la misma malla en los diez), y
  porque el respaldo de cada elección queda escrito en el JSON del
  perfil ("16 de 30 bloques"). No es una lectura muro por muro como la
  del LT2, y está declarado así.
- **Un error de aritmética del agente, en el informe:** dio la rigidez
  inicial como `0.64 EIg` con `EIg = 51 800 kN·m²`. Es `129 532` y
  `0.25 EIg`. Al revisarlo salió algo mejor que el número: la sección
  fisura en `φ = 5.28e-04` y el cuarto punto del análisis cae en
  `5.60e-04`, así que esa "rigidez inicial" es la secante **justo en la
  fisuración** — por eso 0.25 y no 1.0, y por eso cerca del 0.35 de viga
  y lejos del 0.70 de columna, que es lo correcto a `P = 0`.

### Semana 4 — Unity como postprocesador
- **Tarea:** llevar a Unity los esfuerzos de OpenSees ya verificados
  (panel por elemento, diagramas, deformada por caso, P-M de columna y
  muro con el caso activo) y demostrar la trazabilidad. Todo en
  `semana04/`.
- **Cómo se trabajó:** un workflow de agentes en paralelo (exportador,
  verificador, contrato, trazabilidad, visor C#). Durante ~5 h los
  agentes murieron varias veces por errores de la API ("the response
  stopped arriving"); el del visor nunca llegó a escribir código. El
  agente principal detuvo el workflow, escribió el C# en cuatro archivos
  parciales (`VisorSemana04*.cs`) y relanzó una verificación más chica,
  con la instrucción de escribir en trozos cortos. Lo que ya habían
  dejado los otros agentes se revisó antes de usarlo.
- **Corrección 10 — una regla fija que valía para un solo edificio.**
  `demanda_capacidad.demanda()` tomaba `|Mz|` como el momento del plano
  de todo muro; en la Semana 3 se había comprobado **solo** con el muro 9
  del LT2. El agente que escribía `trazabilidad.py` comparó las inercias
  que recibe OpenSees y encontró que en Ingeniería los 56 muros traen el
  `vecxz` a lo largo, con la inercia grande en `Iy`: su `Mz` es el de
  **fuera** de plano. Muro 537 bajo EY: `My = 30 352`, `Mz = 46 kN·m`, y
  se usaba el segundo. El informe entregado de la Semana 3 decía que ese
  muro trabajaba al 0.8 %; con el eje correcto es 2.9 % bajo G y 50 %
  bajo EY, y en `1.2G+1.0Q+1.4EY` no pasan 13 muros (7
  traccionados, entre ellos los cuatro de 2.35 m, y 6 comprimidos). Se corrigió eligiendo por inercias
  (`momento_en_el_plano(Iy, Iz)`), sin valor por defecto para muros, y
  con una prueba que no mira las inercias: bajo EX y EY el momento
  declarado del plano es el mayor en los 96 muros de los dos cuerpos
  (el más justo, 5.2 veces). Mutada la regla a `Mz`, la prueba falla.
- **El lado del diagrama no se eligió: se probó dos veces.** Las fórmulas
  de los esfuerzos internos se exigen contra `f_j` de OpenSees (60 372
  comparaciones en Ingeniería, dentro del redondeo) y el lado traccionado
  se comprobó aparte con una sección de fibras: con `My > 0` la fibra de
  `+z` queda en tracción (+12 579.5 kPa).
- **`JsonUtility` no avisa.** Además del test de contrato en las dos
  direcciones, Unity lee el JSON de verdad y se compara campo a campo.
  Esa comparación atrapó primero un error del propio verificador: los
  nombres de bloque que esperaba no eran los del reporte de Unity.
- **Capturas sin intervención:** el primer criterio para elegir "una
  viga con parábola" eligió una viga de 2.5 m con momento monótono. Se
  cambió por la joroba de la parábola, que es lo que se quería mostrar.
- **Una revisión adversarial antes de entregar.** Cinco agentes
  revisaron la guía, el guion, el informe, el código y la coherencia
  entre documentos, y otros cinco intentaron refutar cada hallazgo: de 30
  quedaron 27. Casi todos eran de precisión (una cota de redondeo escrita
  sin `Σ|λ|`, un número de antes de NCh1537, un paso del guion que no
  funcionaba en vivo). Tres llevaron a cambiar código: el panel rotulaba
  `Iz = b·h³/12` también en los muros de Ingeniería, donde es al revés;
  un brazo rígido seleccionado dibujaba diagrama; y la lectura real de
  Unity no probaba el campo nuevo en un muro.
- **Corrección 11 — `L:` no era fierro de muro.** El bloque [7] fallaba
  en `lt2` y `conjunto` por la curva del muro 10 (M 0.60×2.92), con
  `Mn = 0` en `P = 0`. La causa no estaba en la capacidad sino en la
  lectura: en la Semana 3 el agente interpretó `L:8+8%%C10` como el
  longitudinal de un "machón" y lo pegó al muro más cercano. Leyendo el
  DXF se comprobó que la lámina 000 define `L:` = LATERALES y que esas
  llamadas están bajo los rótulos `V.F. 20/120`, `20/160` y `20/180` del
  eje A': eran la piel de las vigas de fundación. Se quitó la rama
  "machón" del extractor; `geometria/lt2.json` y `modelo/lt2.json`
  cambian solo en eso (los muros 10 y 11 quedan sin fierro, 29 de 40).
  Relajar el chequeo o borrar el punto `(0, 0)` lo habría hecho pasar
  inventando un `Mn`.
- **Corrección 12 — el `f'c` del conjunto, del lado de la capacidad.**
  Lo mismo que el módulo elástico de la Semana 3: `conjunto/armar.py`
  sellaba `E` y `G` por cuerpo pero no `f'c`, y `capacidad.py` leía el
  del material del conjunto (28 MPa) también para el LT2 (G35). La nariz
  de sus curvas salía 17 a 23 % más baja. Ahora la sección trae
  `fpc_MPa`; `trazabilidad.py conjunto 200001` da 35 MPa y `Mn(0)` 987.8.
- **Cómo se trabajó la 11 y la 12:** cuatro agentes en paralelo (plano,
  `f'c`, asimetría de la curva, el bloque [7]) y dos revisores que
  intentaron refutarlos; después del arreglo, cuatro más sobre el diff y
  sobre lo que quedaba abierto. Uno de los revisores corrigió al agente
  del plano en dos números (las cotas de los textos y el fierro de la
  punta), sin cambiar la conclusión.
- **Hallazgos que quedan para el grupo, sin corregir:**
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

### Semana 5 — viewer estructural, modificación y superposición interactiva
- **Tarea:** con el LT2 como edificio de la demo:
  - la tabla de las once funciones del viewer;
  - dos modificaciones de punta a punta: M1 borra la columna 69 desde Unity
    y reanaliza por `/analizar`; M2 cambia el dato `--cs 0.20` y se vuelve a
    exportar el anexo;
  - la superposición interactiva E1..E3 y LIBRE, con Python combinando;
  - la carga móvil (sidequest);
  - el panel ordenado y la vista realista con suelo;
  - el Excel de resultados, abrible desde Unity;
  - el código listo para móvil y la evaluación de una app autónoma.

  Todo en `semana05/` y en `reports/semana05.md`.
- **Cómo se trabajó:** un workflow de agentes en fases.
  1. Auditoría en paralelo sobre `f357eb6`: ocho informes y una síntesis con
     matriz de rúbrica y paquetes.
  2. Decisiones del grupo escritas antes de programar: Windows primero,
     móvil al final y sin instalar Android; ningún cálculo en C#; un solo
     servidor en el puerto 5000.
  3. Un agente base escribió `semana05/CONTRATO.md` y la API común de C#.
  4. Trece paquetes en paralelo, cada uno con **archivos exclusivos**: si
     necesitaba otro archivo, lo pedía por escrito en vez de tocarlo.
  5. Un revisor adversarial por paquete: 13 de 13 "ok con arreglos". En la
     implementación trabajaron 28 agentes, con 1 543 llamadas a
     herramientas.
  6. Integración con Unity real: import, regresión de la Semana 4 byte a
     byte, build, 23 fotos y `comparar_unity.py`.
  7. Un agente revisó las fotos buscando lo que no se entiende, otro corrigió
     y al final se corrió la suite completa: 41 de 41.
  8. Revisión adversarial final, de solo lectura, y un corrector que aplicó
     lo de severidad alta y media: la suite fuera de UTF-8, la M2 en el exe,
     la cabecera y "¿Qué lo carga?". Después, nueva build, captura S5
     (456 filas, 0 FALLA) y regresión S4 (mismo md5).
- **Corrección 13 — la escena pisaba el color de la selección.** El C# nuevo
  resaltaba en cian, pero `SampleScene.unity` guardaba `colorSeleccion`
  magenta, y el valor serializado de la escena manda sobre el del código. Es
  la misma trampa que el `nombreArchivo` de la Semana 2. El reporte del
  agente daba el cian por hecho; lo encontró su revisor leyendo el YAML de
  la escena. Arreglo: un campo serializado nuevo (`colorResaltado`), así el
  valor viejo se ignora.
- **Corrección 14 — la huella del Excel dependía del fin de línea.** La hoja
  LEEME guardaba el sha256 de los bytes en disco. Con `core.autocrlf`, git
  entrega los JSON con CRLF en Windows y con LF en otra máquina. Con el
  mismo modelo, `test_excel.py` daba el libro por desactualizado, y al
  regenerarlo quedaba un diff binario. Se normaliza a LF antes del hash: la
  huella del LT2, `95b64364576f89d5`, es la del contenido guardado en git.
- **Corrección 15 — un pedido demasiado grande salía como error del
  servidor.** `RequestEntityTooLarge` no hereda de `BadRequest`, así que
  `/analizar` respondía 500 donde el contrato pide 400. Lo comprobó el
  revisor con `test_client`. Arreglo con un test de regresión que achica el
  tope y exige 400 con cuerpo JSON.
- **Corrección 16 — un número idéntico no prueba una foto.** En la
  integración, el `registro.txt` de la Semana 4 salió idéntico byte a byte
  (283 líneas), pero la foto 01 había perdido la trazabilidad y la curva
  P-M. El inspector se arma en el `Update` siguiente a la selección, y en
  ese frame el scroll se recortaba a 0. Solo se vio comparando las imágenes.
  `CapturaSemana04.cs` vuelve a fijar el scroll un frame después.
- **Corrección 17 — la tolerancia de la M1 no contaba el redondeo del
  servidor.** Unity y la demo en Python resuelven cada uno su modelo en
  float32, y cada respuesta pasa por el redondeo del servidor (8 decimales
  en m, 4 en kN). Pueden quedar a un escalón entero, y en una suma de
  reacciones a un escalón por nodo restringido: 21 × 1e-4 = 2.1e-3 kN. En
  vez de subir la tolerancia hasta que pasara, se buscó la causa y se agregó
  como `srv` en `semana05/comparar_unity.py`. Ejemplo: el máximo de G antes
  de borrar da 6.71146018 mm en Unity y 6.71145 en Python. La diferencia,
  1.02e-05, queda fuera sin `srv` (5.5e-06) y dentro con ella (1.55e-05).
  Resultado: 456 filas y 0 FALLA.
- **Corrección 18 — la primera vista realista no se leía como edificio.** Lo
  encontró la revisión de las 23 fotos.
  - Columnas de 0.70 m y vigas de 0.60×0.80 salían como tubos de 5 cm con
    esferas de 30 cm, porque la escena guardaba `verPerfiles: 0`.
  - No había losas.
  - En la deformada, cada muro se partía en escalera: la placa quedaba
    siempre vertical y ni el pie ni la cabeza seguían a sus nodos.
  - La cabecera decía "NO PASA 0/69" en verde.
  - La foto 14 no mostraba la curva P-M y el estribo salía `E%%C12a10`.

  Se corrigió solo el dibujo:
  - secciones b×h en la vista realista;
  - losas desde los polígonos tributarios;
  - muros como prisma cizallado;
  - "PASAN 69/69";
  - `Ø` al mostrar.

  Después, `comparar_unity.py` y la regresión S4 dieron lo mismo.
- **Corrección 19 — un documento afirmaba más de lo medido.**
  `MODIFICACIONES.md` decía que la corrida en float32 daba "los mismos
  números a la precisión impresa". En el equilibrio no: Q aplicada da
  −11361.002 y no −11361.003, y los peores errores cambian en el último
  dígito. Lo corrigió el revisor de P3 con el diff de las dos salidas.
- **Corrección 20 — la suite daba 41 de 41 solo en la terminal del agente.**
  `test_excel.py` imprime "sin factor φ". `verificar_todo.py` lanza cada
  entrada con la salida a un pipe, y en Windows un pipe usa cp1252 si no
  está `PYTHONIOENCODING`. En una terminal normal, la entrada "excel s5"
  caía con `UnicodeEncodeError` y quedaba en FALLA. El entorno del agente
  define esa variable, así que nadie lo vio hasta la revisión final, que
  corrió sin ella. Arreglo: `verificar_todo.correr` pasa
  `PYTHONIOENCODING=utf-8` al hijo, como ya hacía `comparar_unity.py`, y
  `test_excel.py` reconfigura su salida a UTF-8. Comprobado sin la
  variable: `test_excel.py lt2` salía con 1 y ahora sale con 0 (47 OK).
- **Otros arreglos de los revisores, menores:**
  - Enter en "Ir a ID" no funcionaba en Windows: el campo consume el evento.
  - Los logs de `AmbienteVisor` escribían `-4,01` en un Windows en español.
  - `lanzar_unity.py app lt2 --seco` escribía de verdad.
  - `sincronizar LT2` en mayúsculas copiaba el modelo pero ningún anexo.
  - La evaluación de la app autónoma olvidaba que el motor ahora necesita
    openpyxl: 24 MB y no 22.
- **Lo que queda para el grupo, sin corregir:**
  - La M2 se vio en el exe, pero con captura automática y solo con el muro 9
    en 1.2G+1.0Q+1.4EY (u 1.078 NO PASA). El muro 9 en EY no tiene foto.
  - La captura selecciona y mueve sliders por código; falta probar a mano
    el clic, el arrastre y los sliders.
  - Los polígonos de las losas de dibujo suman 536.94 m² en −4.01, contra
    504.66 m² del campo `area`, y no está explicado.
  - No hay build móvil, no se identificó un teléfono concreto y el táctil
    no se probó en un equipo.

---

## Verificaciones críticas del proyecto

| Qué | Valor | Dónde |
|---|---|---|
| Benchmark, UZ techo bajo G | −0.0635 mm | `benchmark/benchmark_distribuida.py` |
| LT2, G total | 34 148.98 kN, 232 nodos, 378 elementos | `edificios/lt2/verificar_lt2.py` |
| Conjunto, G total | 84 801.2 kN = suma de los cuerpos | `comun/calcular.py conjunto` |
| Cada cuerpo dentro del conjunto = cuerpo solo | 0.00e+00 m en el LT2 | `edificios/conjunto/verificar_conjunto.py` |
| Losa aplicada = losa dibujada | q constante por piso, 0 barras fuera | `comun/verificar_tributarias.py` |
| Corte basal = carga lateral | error < 1e-7 relativo | `comun/sismo.py` |
| Superposición = corrida explícita | ≤ 1.05× la cota de redondeo, 45/45 | `comun/combinar.py` |
| Tracción pura, fibras = a mano | 0.00e+00 | `semana03/verificar_rc.py` |
| Contrato JSON ↔ C# | sin campos huérfanos | `comun/test_contrato_unity.py` |
| Esfuerzos reconstruidos = extremo *j* de OpenSees | 60 372 comparaciones dentro del redondeo | `semana04/verificar_semana04.py` [1] |
| Lado traccionado del diagrama | fibra `+z` en tracción con `My > 0` | `semana04/verificar_semana04.py` [6] |
| Momento del plano de los muros | el mayor bajo EX y EY: 56 de 56 en Ingeniería (en la suite); 96 de 96 con `verificar_semana04.py conjunto` | `semana04/verificar_semana04.py` [8] |
| Unity lee el anexo de Semana 4 | `JsonUtility` real = lo escrito | `semana04/verificar_unity_semana04.py` |
| Superposición E1..E3 = OpenSees explícito | 0 fuera de cota en 22 691 comparaciones por estado (todo el modelo y la D/C); `/combinar` y el precalculado = Python bit a bit en 24 372 valores | `semana05/verificar_superposicion.py lt2` |
| Contrato JSON ↔ C# de la Semana 5 | 181 OK, en las dos direcciones y en cada objeto | `semana05/test_contrato_semana05.py` |
| M1: borrar la columna 69 y reanalizar | UZ nodo 186 (G) −3.64515 → −21.59875 mm; G aplicada −34 148.979 kN antes y después | `semana05/reanalisis_demo.py lt2 --borrar-elemento 69 --nodo 186 --elemento 337` |
| M2: Cs 0.10 → 0.20 | G y Q idénticos; EX nuevo = 2·EX base (error/cota ≤ 0.72); muro 9 en EY u 0.635 → 1.479 | `semana05/comparar_anexos.py lt2 --cs 0.20` |
| Carga móvil: ΣRz = P | peor 2.0e-04 ≤ 8.0e-04 kN en las 30 posiciones; Betti 3.5e-19 m | `semana05/carga_movil.py lt2` |
| Excel = Python | 47 OK en el LT2; la suma filtrada de Reacciones = `calcular.equilibrio` | `semana05/test_excel.py` |
| Unity muestra lo que calculó Python (Semana 5) | 486 filas, 0 FALLA (fuera de la suite: necesita el exe y el servidor) | `semana05/comparar_unity.py semana05/capturas/registro.txt` |

Todo junto: `python comun/verificar_todo.py`.
