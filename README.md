# Laboratorio Estructural Digital — Grupo 7

Modelo estructural del **Edificio de Ingeniería de la UAndes**, hecho
desde sus planos, resuelto con OpenSees, verificado numéricamente y
visualizado en Unity. Curso *Métodos Computacionales en Obras Civiles*,
2026-02.

El edificio son **dos cuerpos** construidos en dos etapas y separados por
una junta de dilatación:

| cuerpo | planos | carpeta | quién |
|---|---|---|---|
| Ingeniería (antiguo) | `2017_67` | `edificios/ingenieria/` | Eduardo |
| LT2 (nuevo) | `2024_22` | `edificios/lt2/` | Pedro |
| los dos unidos | `calce.json` | `edificios/conjunto/` | común |

Semana 3 (`semana03/`): Monse.

---

## 1. El flujo, en una línea

```
planos DXF → geometría → modelo → resultados → Unity
                  ↓         ↓          ↓
             perfiles/   contrato   verificaciones
```

Cuatro etapas, cada una un JSON en `data/`. **OpenSees calcula, el JSON
es la fuente de verdad, Unity solo muestra.**

```
edificios/<ed>/planos/extraer.py   →  data/geometria/<ed>.json    lo que dice el plano
edificios/<ed>/armar.py            →  data/modelo/<ed>.json       el contrato neutro
comun/calcular.py <ed>             →  data/resultados/<ed>_<caso>.json
edificios/<ed>/exportar_unity.py   →  data/unity/<ed>.json        lo que dibuja Unity
```

`<ed>` es `lt2`, `ingenieria` o `conjunto`. Los dos edificios se unen en
`data/modelo/`, donde ya hablan el mismo idioma.

## 2. Cómo correrlo

Todo se corre **desde la carpeta del repo** y **con el Python del
proyecto** (`.venv`), que es el que tiene OpenSees. `python` a secas es
el del computador y falla con `No module named 'openseespy'`.

```powershell
cd A1P1.0_Grupo_7                            # desde la carpeta que lo contiene
.\setup.ps1                                  # SOLO la primera vez: crea .venv e instala
.\.venv\Scripts\Activate.ps1                 # cada terminal nueva; el prompt queda con (.venv)
python comun\verificar_todo.py               # ¿está todo bien?  (41 comprobaciones, entre 2 y 8 min el 17-09, Unity cerrado)
python comun\lanzar_unity.py app conjunto --pantalla-completa   # verlo
```

Si `Activate.ps1` responde que la ejecución de scripts está
deshabilitada, antes: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.
Sin activar, en lugar de `python` va `.\.venv\Scripts\python.exe`.

Cada script se puede correr solo y explica qué hace en su cabecera.
Los parámetros que dicta el profesor (`--q`, `--cs`, `--fq`, `--patron`,
`--k`, `--fracciones`, `--comb`) van por línea de comandos al
**laboratorio** y a la **demanda**, que resuelven los casos con ellos:

```powershell
python semana03\lab_semana03.py lt2 --q 2.5 --cs 0.15 --comb 1.2 1.6 1.0 0.3
python semana03\lab_semana03.py --patron manual --fracciones 5 10 20 30 35
python semana03\demanda_capacidad.py lt2 9 --grafico     # cualquier columna o muro
```

`comun\combinar.py` **no** usa `--q` ni `--cs`: combina los casos ya
guardados en `data/resultados/` y solo toma `--comb` o `--combinacion`.
Sirve para probar la superposición, no para cambiar las cargas.

La suite abre Unity en batch en una entrada (`JsonUtility real s4`), así
que hay que correrla con Unity y la app cerrados. Deja los anexos del visor
en el **LT2**, el edificio de la demo, y al final lo dice.

### Semana 5: la demo del LT2

Detalle y orden completo en `semana05/COMANDOS.md`. Lo mínimo:

```powershell
python comun\lanzar_unity.py sincronizar lt2        # modelo, anexos, superposición, carga móvil y Excel a StreamingAssets
python semana05\servidor_s5.py                      # otra terminal: /analizar, /combinar, /estados en el puerto 5000
python comun\lanzar_unity.py app lt2                # la app de Windows
python semana05\reanalisis_demo.py lt2 --borrar-elemento 69 --nodo 186 --elemento 337   # M1 sin Unity
python semana05\comparar_anexos.py lt2 --cs 0.20    # M2 sin escribir nada
python semana05\exportar_excel.py lt2               # el Excel de resultados
python semana05_lab\verificar_instantanea.py lt2 --registro semana05\capturas\registro.txt   # LAB S5: lo que Unity combino al mover los sliders, contra Python
```

**Dónde está el Excel:** `data/excel/<ed>_resultados.xlsx`, versionado
(`lt2`, `ingenieria` y `conjunto`). El lanzador copia el del edificio
activo a `unity/Assets/StreamingAssets/resultados.xlsx`, que es el que abre
el botón "Abrir Excel de resultados" de la app. Cada reanálisis del
servidor escribe `results/excel/reanalisis_<ed>.xlsx`, que no va a git.
En la hoja Reacciones **no se suma la columna entera**: se filtran las
filas con "Cuenta en ..." = sí, o el corte basal sale al doble.

## 3. Mapa del repo — qué hace cada archivo

> Versión de una hoja, para imprimir: `reports/mapa_del_repo.md`.

### `comun/` — lo que sirve para cualquier edificio

| archivo | qué hace |
|---|---|
| `rutas.py` | El único que sabe dónde está cada carpeta. Encuentra la raíz subiendo hasta la marca del repo. |
| `contrato.py` | Define el modelo neutro (`data/modelo/`): qué es estructura y qué es vista, `validar()` caza cargas huérfanas, `separar()` sella el área tributaria en cada elemento. |
| `servidor_opensees.py` | El motor: construye el modelo en OpenSees y resuelve los casos. También es el servidor Flask para reanálisis desde Unity: `/analizar` devuelve el equilibrio de `calcular.equilibrio` y escribe el Excel del reanálisis. |
| `excel.py` | Escritor genérico de libros `.xlsx` (openpyxl): LEEME, Resumen, Nodos, Desplazamientos, Elementos, Esfuerzos, Reacciones con "Cuenta en", Demanda-capacidad, Curvas P-M y Supuestos. |
| `calcular.py` | Etapa 3: lee `data/modelo/`, resuelve G, Q, EX, EY y escribe `data/resultados/`. `equilibrio()` separa reacciones de restricciones **por grado de libertad**. |
| `combinar.py` | Superposición `R = ΣλR` y su prueba contra una corrida explícita, sobre todos los GDL. La tolerancia es la **cota de redondeo** del servidor, medida. |
| `sismo.py` | Un caso lateral: carga aplicada, corte basal, sentido de la deformada, torsión de piso (cociente NCh433) y centro de rigidez. |
| `capacidad.py` | Fiber Section desde el modelo: M-φ, curva P-M nominal (ε_c = 0.003) y máxima, confinamiento de Mander desde el estribo real, sensibilidad, dibujo de la discretización. Columna o muro. |
| `verificar_tributarias.py` | La losa que se aplica es la que se dibuja: área sellada = polígonos = carga, con el q implícito constante por piso. |
| `test_contrato_unity.py <ed>` | Cada clave del JSON tiene su campo en el C#. `JsonUtility` no avisa si falta. También los datos de **dibujo del muro**: `dir_largo` presente y unitario, `b = espesor` / `h = largo`, y en el conjunto iguales a los del cuerpo de origen. |
| `verificar_todo.py` | Corre toda la suite (41 entradas) y resume. `--rapido` salta las lentas. |
| `lanzar_unity.py app <ed>` | Copia a `StreamingAssets/` con el nombre **que la escena declara** y abre el visor. Otros modos: `sincronizar` (solo copia), `build`, `web`, `android` (avisa si falta el módulo), `editor` y `servidor`. |

### `edificios/lt2/` — el LT2, desde sus planos `2024_22`

| archivo | qué hace |
|---|---|
| `perfiles/lt2_2024_22.json` | Todo lo específico del edificio y todo lo **supuesto**, declarado con su razón: capas, ventana, cargas, sismo, dinteles, diámetro del longitudinal. |
| `planos/extraer.py` | Orquesta la lectura de los DXF y escribe `data/geometria/lt2.json` + una auditoría. |
| `planos/lectura.py` | Abre una lámina, explota los bloques, deja todo en metros. |
| `planos/ejes.py` `niveles.py` `muros.py` `pilares.py` `vigas.py` `losas.py` | Cada uno saca una cosa de la lámina. `muros.py` une los muros partidos por un cruce. |
| `planos/alineacion.py` | Registra plantas entre sí por los ejes que comparten; alinea fachadas casi colineales. |
| `planos/enfierradura.py` | El fierro desde las elevaciones: estribos y trabas de los 40 pilares, malla y barras de borde de los muros, con la referencia cruzada `VER ELEV. EJE X`. |
| `planos/perfil.py` `inventario.py` | Lee el perfil; inventaría capas y láminas. |
| `malla.py` | Corta las vigas en sus intersecciones reales y engancha los muros con brazos rígidos. |
| `panos.py` | Encuentra los paños como caras del grafo de vigas y reparte la losa a 45° (Sutherland–Hodgman). |
| `modelo_lt2.py` | Arma el modelo en OpenSees: secciones, diafragmas, brazos, las tres vías de carga, sismo por nivel. |
| `armar.py` | Etapa 2: geometría → `data/modelo/lt2.json`, pegando la enfierradura a cada elemento. |
| `exportar_unity.py` | Etapa 4: `data/unity/lt2.json` con ejes locales, polígonos tributarios y los cuatro casos. |
| `verificar_lt2.py` | 13 verificaciones del modelo: secciones a mano, equilibrio, orientación de muros, linealidad, diafragma, brazos, huecos, losa piso a piso, casos, derivas NCh433. |
| `tests/` | `test_planos.py` (la lectura del DXF), `test_reanalisis.py` (el servidor con el LT2). |

### `edificios/ingenieria/` — el cuerpo antiguo, planos `2017_67`

| archivo | qué hace |
|---|---|
| `planos_v2.py` | Lee los DXF: ejes con quiebre de globo, muros por línea y por hatch, registro entre láminas. |
| `benchmark_3d.py` | El modelo: grilla de pórticos, subterráneo como zona, fundación escalonada, voladizos metálicos, muros como columna ancha. |
| `enfierradura.py` | Armadura de las 82 columnas, trazable a la lámina típica. |
| `armar.py` `export_unity.py` | Etapas 2 y 4 de este edificio. |
| `verificar_planos.py` | El modelo contra los DXF, a 1 cm. |
| `tests/test_contrato_unity.py` | Round-trip: el JSON exportado da lo mismo que el modelo en memoria. |

### `edificios/conjunto/` — los dos cuerpos

| archivo | qué hace |
|---|---|
| `calce.json` | La transformación entre los dos planos (`dx`, `dy`, `dz`), medida sobre ejes compartidos, y la junta declarada. |
| `armar.py` | Une los dos `data/modelo/`: aplica el calce, renumera, sella `E`/`G` por cuerpo, y **mide** que la junta sea la declarada y las cotas coincidan. |
| `exportar_unity.py` | Junta los polígonos de los dos cuerpos con el mismo calce. |
| `verificar_conjunto.py` | Con la junta libre, cada cuerpo dentro del conjunto debe dar **exactamente** lo mismo que solo. |

### `semana03/` — casos base, superposición y capacidad

| archivo | qué hace |
|---|---|
| `parametros.json` `parametros.py` | Lo que define el profesor: q, coeficiente sísmico, patrón en altura, combinaciones. Con override por CLI. `q_Q` sale de NCh1537 Of.2009 Tabla 4 (`--uso`); el patrón puede ser `potencia` (ASCE 7 12.8.3), `nch433` (art. 6.2.6) o `manual`. Un `q` sin fila de la tabla queda marcado como dictado, y un JSON que declare uso y `q` que no calzan no arranca. |
| `lab_semana03.py <ed>` | Partes A, B y C sobre cualquier edificio: arma Q, EX y EY en memoria con los parámetros del profesor y delega en `sismo.py` y `combinar.py`. |
| `verificar_rc.py <ed> <elem>` | Fibras contra cálculo a mano (Whitney, β₁, balanceado). Cada diferencia explicada. |
| `demanda_capacidad.py <ed> <elem>` | El (P, M) de cualquier columna o muro sobre su curva; `--todas` para todos; `--mphi` las M-φ a los axiales de su demanda. Arma Q, EX y EY con los parámetros de la Semana 3 y los resuelve en la corrida, así que acepta `--uso`, `--q`, `--cs` y `--patron`: la demanda es la del edificio que se acaba de verificar, no la de un `data/resultados/` con otro q. |
| `verificar_viga_partida.py <ed> <nodo>` | Refina una viga partida en 2, 4, 8 y 16 tramos y muestra que la flecha no cambia: el nodo compartido no es una rótula, y lo que la hunde es la losa que trae la viga perpendicular. |
| `exportar_unity.py` + `unity/.../VisorSemana03.cs` | Flechas de carga, deformada sísmica y jaula de armadura en Unity, sobre la sección de `comun/capacidad.py`. |
| `reports/semana03.md` | El informe del avance, con todos los números salidos de correr los scripts. |
| `GUIA_SEMANA3.md` | Guía de estudio para la defensa. |

### `semana04/` — Unity como postprocesador

Todo lo de la entrega está en la carpeta; **para estudiar, empezar por
`semana04/README.md`**.

| archivo | qué hace |
|---|---|
| `exportar_unity.py <ed>` | Resuelve G, Q, EX, EY con los parámetros de la Semana 3, combina, reconstruye N, Vy, Vz, T, My, Mz a lo largo de cada barra y verifica que lleguen a `f_j` de OpenSees; agrega material, restricciones, familias P-M y demandas. Escribe `data/unity/semana04.json` y su copia en `StreamingAssets`. |
| `verificar_semana04.py <ed>` | Reconstrucción, superposición, una combinación contra corrida explícita, E·A contra OpenSees, trazabilidad, signos con una sección de fibras, `u = 9999` y el momento del plano de los muros. |
| `test_contrato_semana04.py` · `verificar_unity_semana04.py` | Nombres JSON ↔ C# en las dos direcciones, y Unity leyendo el JSON de verdad con `JsonUtility`. |
| `trazabilidad.py <ed> <elem>` | La cadena de un elemento: línea de OpenSees → modelo → objeto de Unity → resultados → sección y capacidad, contra el JSON. |
| `GUIA_DEFENSA.md` · `GUION_DEMO.md` · `COMANDOS.md` · `CONTRATO.md` | Guía de estudio, guion de la demo, chuleta y contrato Python ↔ Unity. |
| `reports/semana04.md` | El informe de la entrega. |

### `semana05/` — viewer estructural, reanálisis y superposición

Todo lo de la entrega está en la carpeta; **para la demo, empezar por
`semana05/README.md`** y `semana05/GUION_DEMO.md`.

| archivo | qué hace |
|---|---|
| `servidor_s5.py` | El servidor de la semana (puerto 5000): `/ping` y `/analizar` de `comun/servidor_opensees.py`, más `POST /combinar` (λ libres) y `GET /estados`. `--lan` para un teléfono. |
| `superposicion.py` · `estados_s5.json` · `verificar_superposicion.py` | Combinación con cualquier λ usando las funciones del anexo, con la D/C rehecha entera; E1..E3 precalculados en `data/unity/superposicion_lt2.json`; y E1..E3 contra una corrida explícita de OpenSees. |
| `exportar_excel.py` · `test_excel.py` | `data/excel/<ed>_resultados.xlsx` y su comparación celda a celda con la fuente. |
| `carga_movil.py` | 30 posiciones de 100 kN sobre las vigas 203-208 del LT2, resueltas y verificadas en Python; Unity solo elige cuál mostrar. |
| `reanalisis_demo.py` · `comparar_anexos.py` | M1 (borrar la columna 69) y M2 (`--cs 0.20`) sin Unity y sin escribir en `data/`. |
| `compilar_unity.py` · `comparar_unity.py` | Compila los C# sin abrir Unity; cruza el registro de `CapturaSemana05` con Python (486 filas, 0 FALLA). |
| `README.md` · `GUION_DEMO.md` · `COMANDOS.md` · `UX.md` · `MOVIL.md` · `MODIFICACIONES.md` · `CARGA_MOVIL.md` · `APP_AUTONOMA.md` · `CONTRATO.md` | Mapa de la entrega, guion, chuleta, las seis preguntas del visor, preparación móvil, M1/M2, carga móvil, evaluación de app autónoma y contrato entre piezas. |
| `capturas/` · `evidencia/` | 23 fotos y `registro.txt` de la app; salidas de verificación. |
| `reports/semana05.md` | El informe de la entrega. |

### `semana05_lab/` — el LAB de la Semana 5 (10 pts)

| archivo | qué hace |
| --- | --- |
| `README.md` | Mapea los cinco criterios del LAB a dónde se demuestra cada uno. |
| `CRITERIOS_REANALISIS.md` | Cuándo hay que reanalizar y cuándo no, derivado de `K·u = F` y comprobado con el motor (doblar `Cs` es `λEX = 2`, no otro caso base). |
| `GUION_DEMO.md` | La demostración de 10 minutos, ordenada por la rúbrica. |
| `verificar_instantanea.py` | Los sliders instantáneos de `VisorSemana05.Instantanea.cs` contra Python: el algoritmo en 10 juegos de λ y, con `--registro`, los números que la app real escribió. |

### `unity/Assets/Scripts/`

`ModeloEstructural.cs` (las clases de datos, fuente de verdad del
contrato) · `VisorEstructura.cs` (dibuja) · `AnalizadorEstructural.cs`
(habla con el servidor) · `EditorEstructura.cs` (pestaña Modificar) ·
`VisorQA.cs` (el panel con pestañas y el inspector) · `PanelUI.cs`
(estilos escalados por DPI) · `EventosVisor.cs` (eventos entre visores y
`AjustesVista`) · `LectorStreaming.cs` (StreamingAssets con
`UnityWebRequest`) · `AmbienteVisor.cs` y `.Losas` (vista realista, suelo
y losas de dibujo) · `VisorSemana03.cs` · `VisorSemana04.cs` y sus partes
`.Diagramas`, `.PM`, `.Panel`, `.Mapa`, `.Superposicion`, `.Hooks` ·
`VisorCargaMovil.cs` · `CapturaSemana04.cs` y `CapturaSemana05.cs`
(capturas sin intervención) · `CamaraOrbital.cs` (mouse y táctil).

### Raíz

`CLAUDE.md` (reglas y trampas para agentes) · `AGENTS.md` (registro de
IA que pide el curso) · `GUIA_unity_paso_a_paso.md` · `benchmark/`
(Semana 1) · `reports/` (informes) · `setup.ps1` · `test_servidor.py`.

## 4. Convenciones que no se rompen

Están en `CLAUDE.md`, sección 4. Las cinco que más se preguntan:

1. **Z vertical en OpenSees, Y en Unity**: `Unity(x, z, y)`.
2. **`Iz` es la inercia de gravedad**; el servidor cruza `Iy`/`Iz` solo en barras no verticales.
3. **`eleResponse(tag,'localForce')`**, nunca `eleForce`.
4. **Un nodo de diafragma reacciona también a su restricción**: se separa por GDL o el corte basal sale al doble.
5. **Lo supuesto se declara en `perfiles/*.json`**, no en el código.

## 5. Números de control

| | |
|---|---|
| LT2 | 232 nodos, 378 elementos, G = 34 148.98 kN |
| Ingeniería | 326 nodos, 559 elementos, G = 50 652.2 kN |
| Conjunto | 558 / 937, G = 84 801.2 kN = la suma; junta 0.050 m cara a cara |
| Torsión LT2 bajo EY | cociente 1.70 — extrema (NCh433 > 1.4); excentricidad 35 % del ancho |
| Columna P.70x70 | Mn(P=0) = 988 kN·m; tracción pura fibras = a mano exacto |
| Benchmark S1 | UZ techo = −0.0635 mm (SAP2000: −0.06375) |
