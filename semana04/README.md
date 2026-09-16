# Semana 4 — Unity como postprocesador

Todo lo de la entrega de la Semana 4 está en esta carpeta, o apunta desde
acá a donde vive. **Para estudiar, empieza por
[`GUIA_DEFENSA.md`](GUIA_DEFENSA.md)**; para la demostración en vivo,
[`GUION_DEMO.md`](GUION_DEMO.md); y para tener a mano,
[`COMANDOS.md`](COMANDOS.md).

La semana pide convertir Unity en un **postprocesador estructural**
conectado a los resultados de OpenSees ya verificados. Postprocesador
quiere decir que Unity no analiza: lee resultados y los muestra. Todo el
cálculo sigue en Python.

---

## Qué hay en esta carpeta

| archivo | qué hace |
| --- | --- |
| [`GUIA_DEFENSA.md`](GUIA_DEFENSA.md) | Guía de estudio: qué pide cada punto, cómo funciona, por qué está bien, y las preguntas probables. |
| [`GUION_DEMO.md`](GUION_DEMO.md) | La demostración paso a paso, ordenada como la rúbrica: qué hacer, qué se ve, qué decir. |
| [`COMANDOS.md`](COMANDOS.md) | Los comandos, en el orden en que se usan. |
| [`CONTRATO.md`](CONTRATO.md) | Qué viaja de Python a Unity, con qué nombre, de dónde sale cada número y quién lo usa. |
| `exportar_unity.py` | Arma y resuelve los casos, combina, reconstruye los esfuerzos a lo largo de cada barra, agrega material, restricciones y curvas P-M, y escribe `data/unity/semana04.json` más su copia en `StreamingAssets`. |
| `verificar_semana04.py` | Comprueba los números: reconstrucción contra OpenSees, superposición, una combinación contra corrida explícita, E·A del panel contra OpenSees, trazabilidad, signos con una sección de fibras, las demandas fuera de curva y el momento del plano de los muros. |
| `test_contrato_semana04.py` | Compara los campos del C# contra las claves del JSON, en las dos direcciones. |
| `verificar_unity_semana04.py` | Abre Unity sin interfaz, le hace leer el JSON de verdad y compara lo leído contra lo escrito. |
| `trazabilidad.py` | La cadena completa de un elemento desde Python: OpenSees → modelo → objeto de Unity → resultados → sección y capacidad. |
| `capturas/` | Capturas del visor tomadas sin intervención, las que usa el informe. |

En Unity (`unity/Assets/`):

| archivo | qué hace |
| --- | --- |
| `Scripts/VisorSemana04.cs` | Las clases del contrato y la carga del anexo; caso activo, selección, deformada. |
| `Scripts/VisorSemana04.Diagramas.cs` | Los diagramas 3D de My, Mz, Vz, Vy, N y T, del lado traccionado. |
| `Scripts/VisorSemana04.PM.cs` | La ventana con la curva P-M y los puntos de demanda. |
| `Scripts/VisorSemana04.Panel.cs` | El texto del panel (material, restricciones, esfuerzos, trazabilidad) y los controles. |
| `Scripts/VisorQA.cs` | El panel de siempre, ahora con la sección Semana 4 y el modo de deformada "Caso activo". |
| `Scripts/CapturaSemana04.cs` | Saca las capturas si la app se abre con `-capturarS4`; si no, no hace nada. |
| `Editor/VerificarAnexoSemana04.cs` | Lo que usa `verificar_unity_semana04.py` para leer el JSON con Unity. |

El informe para Canvas es [`reports/semana04.md`](../reports/semana04.md).

---

## Dónde está cada punto de la rúbrica

| criterio | pts | en la app | en el código |
| --- | --- | --- | --- |
| Resultados conectados | 3 | clic en una barra → panel | `VisorSemana04.Panel.cs` `DescribirElemento`; datos de `exportar_unity.py` |
| Diagramas / deformada | 2 | "Diagramas de esfuerzos"; deformada "Caso activo (S4)" | `VisorSemana04.Diagramas.cs`; `exportar_unity.esfuerzos_internos` |
| Capas estructurales | 2 | toggles de apoyos, áreas tributarias, ejes, diafragmas, cargas, enfierradura, diagramas | `VisorQA.cs`, `VisorSemana03.cs`, `VisorSemana04` |
| Demanda-capacidad | 1 | "Columna demo" y "Muro demo" → ventana P-M | `VisorSemana04.PM.cs`; `comun/capacidad.py` y `semana03/demanda_capacidad.py` |
| Defensa / trazabilidad | 2 | sección "trazabilidad" del panel + `trazabilidad.py` | `VisorSemana04.Panel.cs`; `trazabilidad.py` |

---

## Cómo se corre

### Una vez, antes de la demo

```powershell
python comun\verificar_todo.py
```

Corre la suite entera, incluidas las cuatro verificaciones de esta semana.
Tiene que terminar en `N de N EN OK`.

### Dejar Unity con un edificio

```powershell
python semana04\exportar_unity.py ingenieria
python semana03\exportar_unity.py ingenieria
python comun\lanzar_unity.py editor ingenieria
```

El **nombre del edificio va en los tres comandos**: el lanzador sin
argumento abre el LT2, que es lo que hacía antes de que hubiera más de un
edificio. Los dos exportadores tienen que ser del **mismo** edificio que
abre el lanzador (si no lo son, el lanzador lo avisa). El de la Semana 4 se comprueba: si no calza, el panel avisa que
el anexo es de otro modelo y no dibuja diagramas (los ids existirían igual
pero serían otras barras). El de la Semana 3 no se comprueba, así que se
exportan siempre juntos.

El exportador acepta los mismos parámetros que el laboratorio de la
Semana 3 (`--q`, `--uso`, `--cs`, `--k`, `--patron`, `--comb`): si el
profesor dicta otros, se regenera el anexo con ellos y el visor muestra el
edificio con esos parámetros.

### La cadena de un elemento

```powershell
python semana04\trazabilidad.py ingenieria 18
python semana04\trazabilidad.py ingenieria 537 --caso 1.2G+1.0Q+1.4EY
```

---

## Las decisiones que conviene saber defender

- **Unity no calcula.** Los esfuerzos a lo largo de la barra, las
  combinaciones, la curva y la demanda vienen de Python. Si Unity calculara,
  habría dos implementaciones de la misma mecánica y tarde o temprano la
  pantalla mostraría algo distinto de lo que se verificó.
- **El diagrama se reconstruye y se verifica.** OpenSees da los extremos;
  el medio sale del equilibrio con la carga repartida, y tiene que llegar
  exactamente al extremo *j* de OpenSees. Si una barra no cierra, el
  exportador no escribe el archivo.
- **Se dibuja del lado traccionado**: `+My` hacia `+z` local, `−Mz` hacia
  `+y` local.
- **Un solo caso activo** manda sobre el panel, los diagramas, el punto de
  demanda y la deformada, y su nombre está en el título de la ventana P-M.
- **La trazabilidad se comprueba en vivo**: el panel compara el nombre del
  objeto que tocaste y su `DatoElemento` con lo que dice el JSON.
- **El momento de un muro es el de su plano, y cuál es lo dicen sus
  inercias**: `My` en los 56 muros de Ingeniería, `Mz` en los 40 del LT2.
  Hasta la Semana 3 era siempre `Mz`, y en Ingeniería eso comparaba el
  momento de fuera de plano. Se encontró al verificar esta semana; la
  historia está en la guía (§6) y en el informe.
