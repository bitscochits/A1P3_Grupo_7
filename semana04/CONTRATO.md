# Semana 4 — El contrato entre Python y Unity

Qué viaja de OpenSees a la pantalla, con qué nombre, de dónde sale cada
número y quién lo usa. Si una clave cambia en un lado y no en el otro,
**Unity no avisa**: por eso este documento y las pruebas del final.

```
OpenSees (localForce, nodeDisp)
   │  semana03/lab_semana03.py   armar_casos() + resolver(): G, Q, EX, EY en memoria
   ▼
semana04/exportar_unity.py      combinaciones, esfuerzos internos, material, capacidad
   │  escribe data/unity/semana04.json  (+ copia en unity/Assets/StreamingAssets/)
   ▼
unity/Assets/Scripts/VisorSemana04*.cs   JsonUtility → dibuja, no calcula
   │
   ▼
VisorQA.cs                      panel, selección, deformada
```

---

## 1. Las reglas de `JsonUtility`

`JsonUtility` es el lector de JSON de Unity. **Falla en silencio**: si una
clave del JSON no calza con un campo de la clase C#, deja el campo en su
valor por defecto (0, `null`, `false`) y sigue. Un `My` mal escrito no da
error: da un diagrama plano.

Además no lee:

- **arreglos anidados** (`float[][]`): cada lista va dentro de una clase;
- **diccionarios**: se usan listas con un `id`;
- **propiedades**: solo campos públicos.

Por eso cada clase C# tiene exactamente los campos del JSON, uno por línea.

---

## 2. Las clases

Todas en `unity/Assets/Scripts/VisorSemana04.cs`. `DespNodo` es la que ya
existía en `ModeloEstructural.cs`.

### `AnexoSemana04` — la raíz

| campo | tipo | qué es |
| --- | --- | --- |
| `info` | `InfoSemana04` | de qué edificio es y cómo se generó |
| `casos` | `List<CasoS4>` | G, Q, EX, EY y las 5 combinaciones, en ese orden |
| `elementos` | `List<ElementoS4>` | **todos** los elementos del modelo |
| `familias` | `List<FamiliaPM>` | una curva P-M por familia de sección con fierro |

### `InfoSemana04`

| campo | tipo | qué es |
| --- | --- | --- |
| `edificio` | string | `ingenieria`, `lt2` o `conjunto` |
| `descripcion`, `unidades` | string | m, kN, kPa; momentos kN·m; desplazamientos m y rad |
| `parametros` | string[] | las líneas de `parametros.describir(p)`: q, Cs, patrón, combinación |
| `convencion` | string[] | la convención de esfuerzos y de dibujo, en texto |
| `generado_por` | string | `semana04/exportar_unity.py` |
| `caso_por_defecto` | string | el caso con que abre el visor: la combinación por defecto, `S3` |
| `columna_demo` | int | columna con fierro de mayor axial bajo G (**18** en Ingeniería) |
| `muro_demo` | int | muro con fierro más largo (**537** en Ingeniería) |
| `n_estaciones_cargada` | int | 9 |
| `cota_redondeo_kN` | float | `5e-5`: el redondeo del servidor, medio de la cuarta decimal |

### `CasoS4` — un caso o una combinación

| campo | tipo | qué es |
| --- | --- | --- |
| `nombre` | string | `G`, `Q`, `EX`, `EY`, `S3`, `1.4G`, `1.2G+1.6Q`, `1.2G+1.0Q+1.4EX`, `1.2G+1.0Q+1.4EY` |
| `tipo` | string | `caso` o `combinacion` |
| `descripcion` | string | p. ej. `1.00 G + 0.50 Q + 1.00 EX` |
| `factores` | float[4] | `[λG, λQ, λEX, λEY]` |
| `max_desplazamiento_mm` | float | el mayor `√(ux² + uy² + uz²)` de sus nodos |
| `desplazamientos` | `List<DespNodo>` | `id, ux, uy, uz, rx, ry, rz` de todos los nodos |
| `esfuerzos` | `List<EsfuerzosS4>` | uno por elemento |
| `demandas` | `List<DemandaS4>` | solo los elementos con fierro |

### `EsfuerzosS4` — una barra en un caso

| campo | tipo | qué es |
| --- | --- | --- |
| `id` | int | el elementTag |
| `f` | float[12] | `eleResponse(tag, 'localForce')`: `[N Vy Vz T My Mz]` en *i* y en *j*, fuerzas **sobre** la barra en ejes locales. En una combinación, `Σ λ·f` |
| `w` | float[3] | `(wx, wy, wz)` en ejes locales, kN/m: la carga repartida que recibe `beamUniform`, combinada con los mismos `λ`. Es la que cierra el diagrama, y el visor la dibuja como magnitud `wy`/`wz` |
| `x` | float[] | estaciones desde el nodo *i*, de 0 a L. **9** si la barra tiene carga repartida en ese caso, **2** si no |
| `N`, `Vy`, `Vz`, `T`, `My`, `Mz` | float[] | esfuerzos **internos** en cada estación (§3) |

### `DemandaS4` — el punto sobre la curva

| campo | tipo | qué es |
| --- | --- | --- |
| `id`, `familia` | int | la barra y el índice de su curva |
| `P` | float | kN, **compresión positiva** |
| `M` | float | kN·m. Columna: `√(My² + Mz²)`. Muro: el momento **de su plano**, `|My|` o `|Mz|` según `elementos[].momento_en_el_plano` |
| `M_fuera_plano` | float | muro: el otro de los dos; columna: 0 |
| `extremo` | string | `i (inferior)` o `j (superior)`: gana el de mayor M |
| `Mn` | float | capacidad nominal a ese `P`, interpolada en la curva |
| `u` | float | `M / Mn`; **9999** si `Mn = 0`, que es un `P` fuera del rango de la curva |
| `pasa` | bool | `u ≤ 1` |

Las funciones son las del informe de la Semana 3:
`demanda_capacidad.demanda(f, tipo, plano)` y `demanda_capacidad.capacidad_en(P, curva)`.

**Cuál es el momento del plano de un muro lo dicen sus inercias**, no una
regla fija: `demanda_capacidad.momento_en_el_plano(Iy, Iz)` da `My` si
`Iy > Iz` y `Mz` si no. Un muro es vertical y el servidor le pasa `Iy` e
`Iz` sin cruzarlas, así que la inercia grande es la de su plano. Los dos
cuerpos eligieron distinto el `vecxz` de sus muros:

| edificio | `vecxz` del muro | inercia grande | momento del plano | ejemplo bajo EY |
| --- | --- | --- | --- | --- |
| LT2 | la normal | `Iz` | `Mz` | muro 9: `Mz` 9661, `My` 24 kN·m |
| Ingeniería | el largo | `Iy` | `My` | muro 537: `My` 30 352, `Mz` 46 kN·m |

`demanda()` **no tiene valor por defecto** para un muro: sin `plano` lanza
un error. Hasta la Semana 3 tomaba siempre `|Mz|`, que en Ingeniería es el
de **fuera** de plano (ver `reports/semana04.md`).

### `ElementoS4` — los datos fijos de cada barra

| campo | tipo | qué es |
| --- | --- | --- |
| `id`, `n1`, `n2` | int | tag y nodos |
| `tipo`, `seccion` | string | |
| `momento_en_el_plano` | string | muro: `My` o `Mz`, el que se compara con la curva; `""` en el resto |
| `L` | float | largo, m |
| `objeto_unity` | string | `Elem_<id>_<tipo>`: el nombre que le pone `VisorEstructura.Redibujar` |
| `tag_opensees` | string | la línea `element elasticBeamColumn` con A, E, G, J, Iy, Iz **en el orden en que el servidor se los pasa** y el `vecxz` |
| `material` | string | p. ej. `hormigon f'c 28 MPa, Ec = 4700 sqrt(f'c)` |
| `fpc_MPa` | float | 0 si la sección trae su propio E (acero) |
| `E_kPa`, `G_kPa` | float | los que usa el servidor para **esta** barra |
| `poisson` | float | `E/(2G) − 1`: 0.2 hormigón, 0.3 acero |
| `gamma` | float | kN/m³ |
| `A`, `Iy`, `Iz`, `J`, `b`, `h` | float | de la sección del contrato. En vigas y columnas `Iz = b·h³/12`, la de gravedad. En los muros de Ingeniería `b` = espesor y `h` = largo, y `b·h³/12` —la del plano— está en `Iy` |
| `vecxz` | float[3] | el que usa el servidor |
| `restr_n1`, `restr_n2` | int[6] | `[ux uy uz rx ry rz]` que el servidor fija en cada nodo, incluidos los del maestro de diafragma |
| `diafragma_n1`, `diafragma_n2` | int | el nodo maestro del diafragma del nodo, −1 si ninguno |
| `es_brazo_rigido` | bool | |
| `condiciones` | string | resumen legible |
| `cargada` | bool | tiene carga repartida en G o Q |
| `familia` | int | índice en `familias`, −1 sin fierro |
| `resultados` | string | de dónde salen sus esfuerzos |

### `FamiliaPM` — una curva

| campo | tipo | qué es |
| --- | --- | --- |
| `indice`, `clave` | int, string | `clave` es la firma legible: sección, b, h, barras, As, estribo, malla |
| `tipo`, `seccion` | string | `columna` o `muro` |
| `b`, `h`, `As_cm2`, `cuantia_pct` | float | |
| `refuerzo`, `fuente` | string | el fierro y la lámina de donde sale |
| `P`, `Mn`, `Mmax` | float[] | puntos de `capacidad.interaccion(sec)`: axial, momento nominal (hormigón a 0.003) y momento máximo del M-φ (0 en los extremos) |
| `de` | string[] | de dónde sale cada punto |
| `elementos` | int[] | los ids de la familia |

Una familia agrupa las barras con **la misma firma** —
`demanda_capacidad.firma_de_seccion(e, sec)`—: misma sección y mismo
fierro dan la misma curva, así que se calcula una vez.

---

## 3. La convención de esfuerzos

`f` son las fuerzas **sobre** la barra en sus extremos. Los esfuerzos
**internos** a una distancia `x` del nodo *i* salen del equilibrio del
tramo `[0, x]`, con `w = (wx, wy, wz)` la carga repartida en ejes locales:

```
N(x)  = −(N_i  + wx·x)                 tracción positiva
Vy(x) = −(Vy_i + wy·x)
Vz(x) = −(Vz_i + wz·x)
T(x)  = −T_i
My(x) = −(My_i + x·Vz_i + wz·x²/2)
Mz(x) = −(Mz_i − x·Vy_i − wy·x²/2)
```

**Cómo se sabe que está bien:** en `x = L` tiene que dar exactamente
`f_j`, el extremo *j* que calculó OpenSees. Se comprobó en los tres
edificios, en todos los elementos y en los cuatro casos base; el peor error
es `5.0e-4` en momento, que es lo que explica el redondeo a 4 decimales del
servidor: `5e-5·(2 + L)` con `L` hasta 10 m. El exportador lo vuelve a
comprobar antes de escribir, y si una barra no cierra **no escribe el
archivo**.

Consecuencia que conviene tener presente: una viga simplemente apoyada con
carga hacia abajo tiene **My negativo** en el tramo (`−wL²/8` en el centro).

El servidor aplica la carga con `beamUniform`, que recibe `wy, wz, wx`
**en ese orden**.

---

## 4. La convención de dibujo

Los momentos se dibujan **del lado traccionado**:

| magnitud | fibra traccionada | la curva se desplaza |
| --- | --- | --- |
| `My > 0` | la de `+z` local | `+My · z_local` |
| `Mz < 0` | la de `+y` local | `−Mz · y_local` |

`Vz`, `N` y `T` se dibujan en `z_local`, `Vy` en `y_local`, y **el color
dice el signo**. Las magnitudes `wy` y `wz` —la carga repartida, kN/m— se
dibujan como los cortes, en su eje local y **hacia donde empuja la carga** (azul positivo, rojo negativo; en N, tracción y compresión).

Los ejes locales los toma Unity de `Elemento.localY` y `localZ` del modelo
base (`data/unity/<edificio>.json`), que salen de `contrato.ejes_locales`:
la misma regla que usa el servidor. La conversión a Unity es el cambio de
siempre, `Unity(x, z, y)`.

---

## 5. Qué hace cada lado con cada campo

| dato | lo produce | lo usa en Unity |
| --- | --- | --- |
| `casos[].esfuerzos[].x`, `N`…`Mz` | `esfuerzos_internos()` | los diagramas 3D, los valores *i*/*j* del panel y su máximo |
| `casos[].esfuerzos[].f` | `localForce`, combinado | la sección Trazabilidad del panel |
| `casos[].desplazamientos` | `nodeDisp`, combinado | la deformada del modo "Caso activo (S4)" |
| `casos[].demandas` | `demanda()` + `capacidad_en()` | el punto rojo de la ventana P-M y el panel |
| `familias[]` | `capacidad.interaccion()` | la curva de la ventana P-M |
| `elementos[]` | modelo + reglas del servidor | material, sección, condiciones y trazabilidad del panel |
| `elementos[].objeto_unity` | la regla de `VisorEstructura` | se compara **en vivo** con el nombre del objeto seleccionado |
| `elementos[].n1`, `n2`, `seccion` | modelo | se comparan con el modelo del visor al cargar: si no calzan, el anexo es de otro edificio y no se dibuja nada |
| `info.caso_por_defecto` | `parametros.json` | el caso con que abre |
| `info.columna_demo`, `muro_demo` | exportador | los botones "Columna demo" y "Muro demo" |

**Lo que Unity hace con los números:** escalarlos para dibujarlos, buscar el
mayor para ponerle etiqueta, y armar mallas y texto. **Nada más.**

---

## 6. La API de Python

`semana04/exportar_unity.py`:

| función | qué hace |
| --- | --- |
| `construir_anexo(edificio, argv)` | arma el anexo **en memoria** y devuelve `(anexo, contexto)`; no escribe nada |
| `esfuerzos_internos(f, w, xs)` | las fórmulas de §3 |
| `estaciones(L, cargada)` | 9 o 2 puntos |
| `cargas_por_elemento(caso)` | `{id: (wx, wy, wz)}` sumando las repartidas |
| `rigidez_como_el_servidor(...)` | E, G, `vecxz`, inercias en el orden de OpenSees, replicando `servidor_opensees.py` |
| `restricciones_como_el_servidor(modelo)` | los GDL que fija el servidor, incluido el maestro de diafragma |
| `main(argv)` | escribe el JSON y su copia |

**Trampa:** `semana03/exportar_unity.py` y `semana04/exportar_unity.py` se
llaman igual, y el de la Semana 4 agrega `semana03/` al `sys.path`. Quien lo
importe tiene que hacerlo **por ruta** (`importlib`), no con
`import exportar_unity`.

---

## 7. Lo que vigila el contrato

| script | qué comprueba |
| --- | --- |
| `semana04/exportar_unity.py` | antes de escribir: cada barra cierra en `x = L` contra `f_j` |
| `semana04/test_contrato_semana04.py` | nombres C# contra claves JSON **en las dos direcciones**, sin arreglos anidados, largos consistentes |
| `semana04/verificar_unity_semana04.py` | abre Unity sin interfaz (`Editor/VerificarAnexoSemana04.cs`), le hace leer el JSON y compara lo leído contra lo escrito |
| `semana04/verificar_semana04.py` | reconstrucción, superposición, una combinación contra corrida explícita, E·A contra OpenSees, trazabilidad, signos |
| `semana04/trazabilidad.py <ed> <elem>` | la cadena completa de un elemento desde Python, contra lo que lee Unity |

Todos corren en `python comun\verificar_todo.py`.
