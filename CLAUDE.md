# CLAUDE.md — Lo que un agente tiene que saber antes de tocar este repo

> Contexto para Claude Code y cualquier otro agente de IA. Léelo entero
> antes de editar. El **flujo** del repo, archivo por archivo, está en
> `README.md`; acá van las reglas, las convenciones y las trampas que ya
> costaron tiempo. `AGENTS.md` es el registro de uso de IA que pide el
> curso.
>
> Repo: https://github.com/bitscochits/A1P3_Grupo_7 · Grupo 7 ·
> Métodos Computacionales en Obras Civiles, UAndes, 2026-02.

---

## 1. Qué es esto

Un laboratorio estructural digital del Edificio de Ingeniería de la
UAndes: **dos cuerpos** (el antiguo, planos `2017_67`; el nuevo LT2,
planos `2024_22`) separados por una junta de dilatación, modelados
desde sus planos DXF, resueltos con OpenSees, verificados
numéricamente y mostrados en Unity. No se evalúa realismo gráfico; se
evalúa corrección, verificación, trazabilidad y **que cada integrante
pueda explicar cualquier parte**.

## 2. La regla de oro

```
planos DXF → Python/OpenSees CALCULA → JSON es la fuente de verdad → Unity MUESTRA
```

Nunca lógica de cálculo estructural en C#. Si hay que calcular algo,
va en Python y viaja por JSON. Unity dibuja, y como mucho edita datos
que vuelven a Python para recalcular.

## 3. El pipeline de cuatro etapas

```
edificios/<ed>/planos/   →  data/geometria/<ed>.json     lo que DICE el plano
edificios/<ed>/armar.py  →  data/modelo/<ed>.json        el contrato neutro
comun/calcular.py        →  data/resultados/<ed>_<caso>.json
edificios/<ed>/exportar_unity.py → data/unity/<ed>.json   lo que dibuja el visor
```

`<ed>` es `lt2`, `ingenieria` o `conjunto`. **`data/modelo/` es donde
los dos edificios hablan el mismo idioma** y donde `conjunto/armar.py`
los une: aplica el calce, renumera tags y respeta la junta libre.
`comun/calcular.py` no sabe de qué edificio se trata.

**Una carpeta = un dueño.** `edificios/lt2/` y `edificios/ingenieria/`
se editan por separado; `comun/` y `unity/` son compartidos y se avisa
antes de tocarlos. Nada específico de un edificio va en código: va en
`edificios/<ed>/perfiles/*.json` (capas, ventanas, supuestos).

## 4. Convenciones que no se rompen

| Convención | Regla | Dónde vive |
|---|---|---|
| **Ejes** | OpenSees: Z vertical. Unity: Y vertical. `Unity(x, z, y)`. | `VisorEstructura.cs` |
| **Unidades** | m, kN, kPa. `Ec = 4700·√f'c·1000`. | todo el repo |
| **Inercias** | En el contrato `Iz` es la de **gravedad** (`b·h³/12`), `Iy` la lateral. En los muros de Ingeniería (`b` = espesor, `h` = largo) la grande, `b·h³/12`, está en `Iy`. El servidor las **cruza** solo en elementos no verticales (`vecxz=(0,0,1)` deja el local *z* vertical: la gravedad flecta en `My`, que resiste `Iy`). | `servidor_opensees.py` |
| **`vecxz`** | Se elige por **geometría**, nunca por la etiqueta `tipo`. Vertical → `(1,0,0)`; si no → `(0,0,1)`. Un muro trae el suyo: en el LT2 su normal (inercia grande en `Iz`), en Ingeniería su largo (inercia grande en `Iy`); el momento del plano se elige por inercias. | `servidor_opensees.py` |
| **Fuerzas internas** | `eleResponse(tag,'localForce')`, **nunca** `eleForce` (que es global). Vector `[N,Vy,Vz,T,My,Mz]` por extremo. | `calcular.py`, `demanda_capacidad.py` |
| **Reacciones** | `nodeReaction` en un nodo de diafragma incluye la fuerza de la restricción, que es interna. Se separa **por grado de libertad**: en horizontal solo cuentan nodos fuera de todo diafragma; en vertical, cualquier restringido salvo el maestro. Sumar todo **dobla el corte basal**. | `calcular.equilibrio()` |
| **Diafragma rígido** | `constraints('Transformation')`. Los GDL fuera del plano del maestro se fijan. El piso se traslada **y gira**: `ux_i = ux_m − rz·(y_i−y_m)`. | `servidor_opensees.py` |
| **Muro** | Una barra en su eje baricéntrico (columna ancha) + brazos rígidos como barras ×100 hasta las caras. **No** `rigidLink` (pelea con el diafragma). | `malla.py`, `modelo_lt2.py` |
| **Hormigón por sección** | `E`, `G` y `fpc_MPa` opcionales en cada sección pisan al material del modelo: el solver usa `E`/`G`, la capacidad `fpc_MPa`. Es lo que permite juntar un cuerpo G35 con uno G28. | `conjunto/armar.py`, `capacidad._fpc_kPa()` |
| **Rutas** | Solo `comun/rutas.py` sabe dónde está cada cosa; encuentra la raíz subiendo hasta la marca del repo. **Nunca** contar `dirname`. | `rutas.py` |
| **Resultados** | El servidor **redondea**: desplazamientos a 8 decimales, fuerzas a 4. Nada se puede comparar por debajo de eso. | `combinar.py` |

## 5. Supuestos declarados (no están en el código)

Todo lo que el plano no dice vive en `edificios/<ed>/perfiles/*.json`
con su justificación al lado, para que se vea como supuesto y se pueda
reemplazar sin tocar código:

- **Sismo**: coeficiente basal, fracción de sobrecarga en el peso
  sísmico y patrón en altura. Los define el profesor; se sobreescriben
  por línea de comandos (`--cs`, `--q`, `--patron`, `--comb`).
- **Diámetro longitudinal de los pilares del LT2**: el plano da el
  estribo y las trabas; el número de barras se deduce del estribo (una
  traba amarra una barra) y **solo el diámetro es supuesto** (Ø25).
- **Junta de dilatación**: 5 cm. De ahí sale el `dx` del calce.
- **Dinteles** del LT2 y el hormigón del pilar de Ingeniería (lámina
  típica): declarados, no extraídos.

## 6. Trampas que ya costaron tiempo (y dónde está el guardia)

Todas fallan **en silencio**: el modelo corre, da números, y el error
solo se ve mirando otra cosa.

| Trampa | Guardia |
|---|---|
| El globo de un eje del DXF no está sobre su eje (va con un quiebre). | `verificar_planos.py` |
| Cada lámina/XREF tiene **su propio origen**; la 305 trae dos elevaciones. | `enfierradura.hojas_de_elevacion()` |
| `JsonUtility` ignora sin avisar un campo C# que no calza con el JSON: deformada plana, sin error. | `comun/test_contrato_unity.py` |
| La **escena** pisa el `nombreArchivo` del C#, y hay dos visores: el lanzador debe leer el de `VisorEstructura`. | `lanzar_unity.nombre_que_lee_el_visor()` |
| En la elevación, la llamada de fierro **más cercana** al pilar es la de la viga. La búsqueda es direccional (hacia abajo, dentro del ancho). | `enfierradura.extraer()` |
| `L:n+n` **no** es fierro de muro: la lámina 000 dice `L:` = LATERALES, la piel de una viga (`V. 40/80` → `L:3+3`, `V.F. 20/180` → `L:8+8`). Leído como longitudinal de "machón", le pegó las laterales de la V.F. del eje A' al M 0.60x2.92 y su curva P-M dio Mn = 0 a P = 0. Una elevación sin pilares también tiene muros. | `semana04/verificar_semana04.py lt2` bloque [7] |
| Al unir dos edificios el contrato tiene **un** material: el LT2 corría con 28 MPa (10.6% más blando) y el equilibrio cerraba igual. Lo mismo del lado de la capacidad: sin `fpc_MPa` en la sección, sus curvas P-M salían con 28 (nariz 17–23 % más baja). | `verificar_conjunto.py`, `trazabilidad.py conjunto` |
| Un paño de losa que nunca entró al modelo **no** rompe el equilibrio. | `verificar_tributarias.py` (q implícito por piso) |
| Dos secciones con el mismo número de barras **no** son la misma sección (caché de curvas P-M). | `demanda_capacidad._todas()` |
| Un cociente de torsión sobre un piso que casi no se mueve es ruido. | `sismo.py` |
| Ajustar un umbral "hasta que entre" roba las anotaciones del vecino. Regla: mínima distancia, a uno solo. | `pegar_enfierradura_muros()` |
| El momento **del plano** de un muro no es siempre `Mz`: el LT2 da como `vecxz` la normal (inercia grande en `Iz`) e Ingeniería el largo (grande en `Iy`, momento del plano `My`). Con `|Mz|` fijo, los 56 muros de Ingeniería se comparaban con su momento **fuera** de plano y trabajaban muy por debajo de lo real (el 537 salía al 0.8 % bajo G; es 3 % bajo G y 50 % bajo EY). Se elige por inercias, y `demanda()` no tiene default para muros. | `demanda_capacidad.momento_en_el_plano()`, `verificar_semana04.py` [8] |
| `eleResponse(...,'localForce')` da los extremos; el diagrama del medio se **reconstruye** por equilibrio. Un signo o un eje de carga mal puesto da un diagrama igual de razonable: se exige llegar a `f_j` de OpenSees, y el lado traccionado se prueba con una sección de fibras. | `exportar_unity.py` (no escribe si no cierra), `verificar_semana04.py` [1] y [6] |
| **Sumar la columna de reacciones** (en el Excel o en el log de Unity) dobla el corte basal, porque un nodo de diafragma reacciona también a su restricción. El log de `AnalizadorEstructural` lo hizo hasta la Semana 4, y un Excel invita a hacerlo con un clic. En EX del LT2, la suma filtrada da −3792.28 kN (= equilibrio) y la columna entera −7584.56. | Hoja Reacciones con "Cuenta en Fx/Fy" y "Cuenta en Fz", y `semana05/test_excel.py` (suma filtrada = `calcular.equilibrio`). Unity no suma: muestra la tabla que manda el servidor (`AnalizadorEstructural.TablaEquilibrio`) |
| La **suite exporta los anexos** y los copia a StreamingAssets. Sin edificio exportaba Ingeniería y dejaba la demo del LT2 con "anexo de otro modelo" (sin diagramas). Ahora deja el LT2, así que si estabas mirando otro edificio, te lo pisa. | Las entradas van con `lt2` (decisión 1 de la S5) y `verificar_todo._avisar_anexos()` dice qué edificio dejó. Cada lector compara `info.edificio`. `lanzar_unity.py sincronizar <ed>` vuelve a dejar el que se quiera |
| **Comparar lo que muestra Unity con Python "al decimal"** falla sin que nadie se haya equivocado: `JsonUtility` guarda float32 (en P = 5409.62 kN el paso entre floats es 4.9e-4), la M1 viaja en float32 al servidor, y el servidor **redondea** lo que devuelve (8 decimales en m, 4 en kN), así que Unity y una corrida de Python quedan a un escalón. | `semana05/comparar_unity.py`: la tolerancia de cada fila es la suma de sus causas medidas (`f32`, `ref`, `impr`, `ent32`, `srv`). `reanalisis_demo.py --float32` emula lo que manda Unity |
| El **mapa D/C y la vista realista** cambian los mismos `sharedMaterial`. El que llega último pisa al otro, y al apagar el mapa se "restaura" un material realista como si fuera el técnico. Solo se ven colores equivocados. | Protocolo de `semana05/CONTRATO.md` §8: solo `AmbienteVisor` y el mapa tocan materiales; `AmbienteVisor` registra el técnico en `Redibujado` y termina siempre con `EventosVisor.AvisarMaterialesCambiados()`; el mapa rehace su base en cada aviso sin tomar sus propios materiales. `CapturaSemana05` registra `mapa_pintadas` (378 en la foto 14) |
| **IMGUI**: `OnGUI` corre una vez por evento, y cada evento repite el Layout. Si un clic agrega o quita controles a mitad de evento, salta "Getting control N's position". Además, un `ScrollView` recorta el scroll a lo que cabe **en ese frame**: fijar el scroll antes de que el panel tenga contenido lo deja en 0 sin avisar (la foto 01 de la S4 salió sin la P-M). | `VisorQA`: lo que cambia la cantidad de controles se difiere a `Update`, y el panel se dibuja de una foto tomada en `EventType.Layout`. `CapturaSemana04.Foto()` vuelve a fijar el scroll un frame después. `CapturaSemana05` lleva al registro los errores del log, y `comparar_unity.py` [5] exige `log.errores = 0` |
| La **escena pisa los valores serializados** del C#, no solo `nombreArchivo`: cambiar el default de un campo público no cambia nada si `SampleScene.unity` ya lo guardó. `colorSeleccion` seguía magenta, y `verPerfiles: 0` con `grosorBarra: 0.05` dejaban la vista realista como un andamio de tubos de 5 cm. | Antes de cambiar un default, `grep` del campo en `SampleScene.unity`. Para imponer el valor del código: campo serializado con otro nombre y propiedad pública (`VisorQA.colorSeleccion` sobre `colorResaltado`), o una propiedad que no dependa del campo guardado (`VisorEstructura.DibujaPerfiles`) |
| **Lo que dice el panel puede no ser lo que se ve.** La cabecera leía siempre el caso del anexo: con la carga móvil o tras la M1 decía "LIBRE ... 24.63 mm, NO PASA 4/69" junto a un nodo que bajaba 21.60 mm. Ojo con el rótulo: el "Desp. max" del anexo es la **norma** (ux, uy, uz) y el `max_desplazamiento` del servidor la **mayor componente** (nodo 186: 21.60 contra 21.63 mm). Y la `w` de un área tributaria es **solo la losa**: el `wz` de G suma el peso propio (viga 92: 15.749 contra 27.749 kN/m), y sin el dato parecía un error. | La cabecera nombra la fuente (`VisorQA.FuenteDeLoQueSeVe`, decidida en la foto del Layout; el reanálisis se rotula "Max. componente", como la pestaña Modificar) y `CapturaSemana05` la registra por foto: `comparar_unity.py` exige `anexo`, `reanalisis` o `carga_movil` con sus números. El LT2 exporta `w_peso_propio` y `w_total_G` leídos de lo que el modelo pasó a `eleLoad` (`ModeloLT2.repartidas`) y `test_contrato_unity.py` exige `w + w_peso_propio = w_total_G = −wz` de G |
| Los datos de **DIBUJO del muro** (`dir_largo`, `largo`, `espesor` del elemento) los emite cada cuerpo con **su** convención, y si no viajan el visor los deduce con la del otro: `CrearPlacaMuro` supone que `vecxz` es la normal (LT2), así que un muro de Ingeniería —donde `vecxz` corre a lo largo— sale **girado 90°**. La otra mitad del mismo error es el `b`/`h` de la sección: el conjunto los deducía de `A`, `Iy`, `Iz` con la regla del LT2 (`b=√(12Iy/A)`), y los 27 muros de Ingeniería quedaban **cruzados** (`muro_0` con `b = 9.65 m`, `h = 0.30 m`). No se ve en ningún número: las dos lecturas dan el mismo `A`, `Iy` e `Iz`, y `b·h = A` acepta las dos. | Cada exportador los emite (`edificios/ingenieria/export_unity.py`, `edificios/lt2/exportar_unity.py`) y `conjunto/armar.py` solo les corre el tag; `completar_b_h()` toma `b = espesor`, `h = largo` del propio cuerpo antes de deducir nada. Guardia: `comun/test_contrato_unity.py` bloques [2] (`dir_largo` presente y unitario dentro de 1e-4 m / largo, `b = espesor` y `h = largo`) y [2b] (cada muro del conjunto calza con su cuerpo de origen; el calce no gira) |
| La **exageración de la deformada** era un número fijo, serializado en la escena (`factorEscala: 300`). Un factor fijo no puede servir para dos modelos de tamaños distintos: en el LT2 (caja de 40.4 m de diagonal, peor desplazamiento 27.25 mm) dibuja 8.2 m y se ve un edificio deformado; en el conjunto (89.0 m, 53.91 mm) dibuja 16.2 m —el 82 % de la altura— y se ve una carpa colapsada. No falla ningún número: el modelo está bien y los desplazamientos son los de Python. | La escala la calcula **Python** y viaja en el anexo: `escala_deformada()` de `semana04/exportar_unity.py` lleva el mayor desplazamiento de **todos** los casos al 5 % de la diagonal de la caja envolvente (`FRACCION_DIAGONAL`) y lo manda en `info.escala_deformada` con su `_escala_deformada_por_que`: lt2 x74, ingeniería x56, conjunto x83. Una sola por modelo, para que no salte al cambiar de caso. `VisorQA` la usa de valor por defecto la primera vez que se prende una deformada, ofrece "Volver a la recomendada" y no pisa lo que mueva el usuario (`FijarEscala`); las capturas fijan la suya con `FijarEscalaAMano` y no pasan por el panel. Guardia: `semana04/test_contrato_semana04.py` bloque [7] (> 0, igual a la que calcula el exportador, y escala × desplazamiento = el objetivo declarado ± medio paso del redondeo a 2 cifras) |
| **Los documentos citan `archivo:línea`.** Agregar o quitar líneas en medio de un archivo citado corre todas las citas de abajo sin ningún error, y el informe queda apuntando a otro código. | Antes de editar, `grep "archivo.cs:"` en `reports/` y `semana05/` (ojo con las citas cortas `:NNN` de la misma fila). Código nuevo al final de la clase, reemplazos con el mismo número de líneas, o actualizar cada cita |
| **Un suelo plano sobre un terreno escalonado.** El visor dibujaba UN plano en `info.cota_terreno`, puesto donde arrancan las columnas (−7.97), y la planta de fundaciones de Ingeniería rotula dos N.R. (−7.97 y −4.01): sus 39 apoyos en terreno `[0 0 1 1 1 0]` del nivel 1 quedaban 3.96 m en el aire. El chequeo "la cota está en el apoyo más bajo" daba OK igual. Y la región del nivel alto no se dibuja a ojo: sale de la misma definición con que el modelo crea esos apoyos (`benchmark_3d.sobre_subterraneo`), o se desfasa en silencio el día que cambie el modelo. | El terreno viaja en niveles (`info.terrenos`, `semana05/CONTRATO.md` §11): la base y cada terraza con su región, armada por el exportador del edificio desde su perfil (`terreno.terrazas`; `edificios/ingenieria/export_unity.py` `terrenos()` aborta si un apoyo de esa z queda fuera) y calzada por `terrenos_del_conjunto()`. Guardia: `comun/test_contrato_unity.py` [2], **cada apoyo no auxiliar sobre un nivel** (su z = la del nivel cuya región lo contiene, 0.01 m), contado por nivel: LT2 16 en −7.97; Ingeniería 29 en 0.00 y 39 en 3.96; conjunto 45 en −7.97 y 39 en −4.01. `AmbienteVisor.Terrazas.cs` recorta la terraza alrededor de lo que baja a la base (`HuecoDelSuelo.CalcularTerraza`) |

## 7. Reglas para el agente

1. **Toda** modificación al modelo o a las cargas termina corriendo
   `python comun/verificar_todo.py`. Si algo falla, se dice con la
   salida; no se relaja la tolerancia para que pase.
2. Cuando una verificación marque algo, **primero** sospechar de la
   verificación y comprobar la hipótesis (así apareció el peso propio
   en la carga distribuida, el +1 de la cota de redondeo y el
   confinamiento en el balanceado).
3. Una tolerancia se **mide** contra su causa (redondeo, muestreo), no
   se elige a ojo.
4. Una sola definición de cada cosa: la sección de fibras que se
   resuelve es la que se dibuja; el `nombreArchivo` lo manda la
   escena; el área tributaria vive en el elemento.
5. Lo leído del plano y lo supuesto se distinguen **en el dato**
   (`origen`, `_supuesto`, `provisorio`), no en la memoria de nadie.
6. No tocar `edificios/<otro>/` sin avisar. Avisar antes de tocar
   `comun/` o `unity/`.
7. Mensajes de commit que digan **por qué** y qué se comprobó, con los
   números.

## 8. Cómo saber si está todo bien

```bash
python comun/verificar_todo.py            # la suite entera
python comun/verificar_todo.py --rapido   # sin los lentos
```

Números de control: LT2 `G = 34 148.98 kN`, 232 nodos / 378 elementos;
Ingeniería `G = 50 652.2 kN`; conjunto `G = 84 801.2 kN` = la suma;
benchmark de Semana 1 `UZ techo = −0.0635 mm`.
