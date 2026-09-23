# Semana 5 — Viewer estructural, reanálisis y superposición en Unity

Todo lo de la entrega de la Semana 5 está en esta carpeta, o apunta desde
acá a donde vive. Para la demostración en vivo, empieza por
[`GUION_DEMO.md`](GUION_DEMO.md). Los comandos están en
[`COMANDOS.md`](COMANDOS.md) y la evaluación de las seis preguntas del
visor, en [`UX.md`](UX.md). El informe para Canvas es
[`reports/semana05.md`](../reports/semana05.md).

La semana pide que Unity deje de ser solo un postprocesador y pase a ser un
**viewer estructural**. Tiene que dejar navegar, seleccionar e inspeccionar,
modificar el modelo y pedir el reanálisis, superponer casos con factores
elegidos y responder preguntas de ingeniería. Además hay que dejar la app
preparada para móvil. La regla de oro no cambia: **Unity no calcula
estructura**. Todo número que se ve en pantalla lo calculó Python y llegó
por JSON o por el servidor.

Decisiones que ordenan todo lo demás (Pedro, 16-09):

- **Edificio de la demo: LT2.**
- **Windows primero.** El móvil es la última prioridad y Android no se
  instaló ([`MOVIL.md`](MOVIL.md)).
- **Excel con openpyxl**, versionado y abrible desde Unity.

---

## Qué hay en esta carpeta

| archivo | qué hace |
| --- | --- |
| [`GUION_DEMO.md`](GUION_DEMO.md) | La demostración ordenada por criterio de la rúbrica: minutos, qué hacer, qué se ve, qué decir y qué hacer si algo falla. |
| [`COMANDOS.md`](COMANDOS.md) | Los comandos en el orden en que se usan, con el Python del `.venv`. |
| [`UX.md`](UX.md) | Las seis preguntas del visor: dónde se contestan, con qué captura, veredicto y fricción que queda. Antes y después del panel y del realismo. |
| [`MOVIL.md`](MOVIL.md) | Preparación móvil: la decisión, los requisitos de Unity 6.5, cómo identificar un teléfono, qué código ya está listo y los pasos del build cuando se decida. |
| [`MODIFICACIONES.md`](MODIFICACIONES.md) | M1 (borrar la columna 69 desde Unity) y M2 (`--cs 0.20`) seguidas en cinco pasos: interfaz o dato → modelo → OpenSees → resultados → Unity. |
| [`CARGA_MOVIL.md`](CARGA_MOVIL.md) | La carga móvil: regla física, reparto, conservación y lo que muestra Unity. |
| [`APP_AUTONOMA.md`](APP_AUTONOMA.md) | Evaluación (sin construir) de una app autónoma "como un videojuego". |
| [`CONTRATO.md`](CONTRATO.md) | El contrato entre piezas: API C# (§2 y §10), servidor (§3), Excel (§4), JSON de carga móvil (§5) y de superposición (§6), StreamingAssets (§7), materiales y pestañas (§8). |
| `servidor_s5.py` | **El** servidor de la semana, en el puerto 5000. Importa `/ping` y `/analizar` de `comun/servidor_opensees.py` y agrega `POST /combinar` (superposición con λ libres) y `GET /estados`. Con `--lan` escucha en la red local. |
| `superposicion.py` | Combina G, Q, EX y EY con cualquier juego de λ usando las mismas funciones del anexo de la Semana 4, y rehace la demanda-capacidad entera (no es lineal). `--exportar` escribe E1..E3 precalculados. |
| `estados_s5.json` | E1 = 1.0G+1.0Q, E2 = 1.2G+1.6Q, E3 = 1.2G+1.0Q−1.4EX y los rangos de los sliders. Una sola copia, la leen los tres scripts de la superposición. |
| `verificar_superposicion.py` | E1..E3 por cuatro vías (corrida explícita de OpenSees, suma lineal, `POST /combinar` y el precalculado) con cotas medidas contra el redondeo. |
| `test_contrato_semana05.py` | El JSON de superposición y las respuestas de `/combinar` y `/estados` contra los campos del C#, en las dos direcciones. |
| `exportar_excel.py` · `test_excel.py` | Escriben `data/excel/<ed>_resultados.xlsx` con `comun/excel.py`, y lo releen celda a celda contra la fuente. |
| `carga_movil.py` | Precalcula en OpenSees 30 posiciones de una carga de 100 kN sobre las vigas 203-208 (cota 3.91), verifica cada una y escribe `data/unity/carga_movil_lt2.json` y su copia en StreamingAssets. |
| `reanalisis_demo.py` | M1 sin abrir Unity: aplica la misma edición que el editor, reanaliza y muestra antes y después. No escribe en `data/`. |
| `comparar_anexos.py` | M2 sin escribir nada: arma en memoria el anexo con `--cs 0.20` y lo compara con el de la entrega. |
| `compilar_unity.py` | Compila los C# con el dotnet de Unity, sin abrir Unity. |
| `comparar_unity.py` | Cruza el `registro.txt` de `CapturaSemana05` (lo que Unity cargó y muestra, en float32 exacto) con Python. |
| `capturas/` | 25 fotos (`01`…`22`, más `14b`, `18b` y `18c`) y `registro.txt`, tomadas sin intervención por `build/LaboratorioEstructural.exe -capturarS5` con el servidor prendido (22-09, 1600×900). |
| `evidencia/` | `superposicion_lt2.json/.csv/_control.csv` (y los de Ingeniería), `carga_movil_lt2.json/.txt` y `unity_vs_python.txt` (488 filas, 0 FALLA). |

Fuera de la carpeta, lo que la semana agregó o cambió:

| archivo | qué hace |
| --- | --- |
| `comun/excel.py` | Escritor genérico de libros (reutilizable). Hojas: LEEME, Resumen, Nodos, Desplazamientos, Elementos, Esfuerzos, Reacciones (con "Cuenta en Fx/Fy" y "Cuenta en Fz"), Demanda-capacidad, Curvas P-M y Supuestos. |
| `data/excel/<ed>_resultados.xlsx` | El Excel **versionado** de cada edificio. El del LT2 pesa 0.65 MB y tiene 10 hojas. |
| `results/excel/reanalisis_<ed>.xlsx` | Lo escribe el servidor después de cada `/analizar`. Está en `.gitignore`. |
| `data/unity/superposicion_lt2.json` · `data/unity/carga_movil_lt2.json` | E1..E3 precalculados y la carga móvil, que funcionan sin servidor. |
| `comun/servidor_opensees.py` | `/analizar` devuelve el equilibrio de `calcular.equilibrio` y la ruta del Excel del reanálisis, con CORS para el build Web. |
| `comun/lanzar_unity.py` | Modos nuevos `sincronizar <ed>` (copia modelo, anexos, superposición, carga móvil y Excel a las dos StreamingAssets), `web`, `android` (sale con 1 si falta el módulo, sin abrir Unity) y `servidor` (levanta `servidor_s5.py`). |
| `comun/verificar_todo.py` | Pasa de 34 a 41 entradas. Los exportadores de los anexos corren con `lt2` y la suite avisa qué edificio dejó. |
| `edificios/lt2/perfiles/lt2_2024_22.json` | `terreno.z = -7.97` (donde arrancan las columnas: sus 16 apoyos), con su `_por_que`. Viaja en `info.cota_terreno` de `data/unity/lt2.json`. El informe entregado dice `-4.01`, `provisorio`: era el valor de la entrega, cambiado después (18-09). |
| `edificios/ingenieria/perfiles/ingenieria_2017_67.json` | Nuevo (18-09): `terreno.z = 0.0`, el arranque de este cuerpo (29 apoyos, 10 columnas), que con el `dz` del calce es el mismo `-7.97`. Antes no declaraba cota y el visor caía a su respaldo, que daba el mismo número. Y `terreno.terrazas`: la **terraza oriente** en `z = 3.96` (−4.01 calzada), el segundo N.R. de su planta de fundaciones, con la zona declarada como criterio (los apoyos de esa z, `margen_m = 0.35`, menos el subterráneo de `benchmark_3d.sobre_subterraneo`). |
| `edificios/*/export*_unity.py` · `edificios/conjunto/exportar_unity.py` | Desde el 18-09 escriben `info.terrenos` (el terreno en niveles, `CONTRATO.md` §11) además de `cota_terreno`: el LT2 su base; Ingeniería la base y la terraza, con la región armada en `terrenos()`; el conjunto las junta calzadas (`terrenos_del_conjunto()`), y ya no aborta porque los cuerpos tengan niveles distintos. |

### En Unity (`unity/Assets/`)

| archivo | qué hace |
| --- | --- |
| `Scripts/EventosVisor.cs` | Eventos estáticos entre visores (`ModeloCargado`, `Redibujado`, `ModeloEditado`, `PedirCentrar`, `SeleccionCambio`, `VistaCambio`, `MaterialesCambiados`) y `AjustesVista` (realista, suelo, losas, filtro de piso). |
| `Scripts/PanelUI.cs` | Estilos IMGUI escalados por DPI (`Escala()`, `Px()`), secciones plegables, casillas, `TextoDemanda` ("PASAN 69/69" o "NO PASA n/m") y `TextoPlano` (`%%C` → Ø al mostrar). |
| `Scripts/IPanelIncrustable.cs` | La interfaz con la que el editor y la carga móvil se vuelven pestañas del panel. |
| `Scripts/LectorStreaming.cs` | Lee StreamingAssets con `UnityWebRequest` (sirve en Windows, Android y Web) y abre el Excel de resultados con el programa del sistema. |
| `Scripts/VisorQA.cs` | El panel: cabecera fija, botón "Abrir Excel de resultados", pestañas Vista \| Capas \| Caso \| Elemento \| Modificar \| Carga movil, inspector de elemento y de nodo, "Ir a ID", filtro de piso y apoyos por tipo. |
| `Scripts/AmbienteVisor.cs` | Vista realista o técnica: suelo en `cota_terreno` con el hueco de la excavación, cielo, luz y texturas procedurales. Sigue el protocolo de materiales (`CONTRATO.md` §8). |
| `Scripts/AmbienteVisor.Terrazas.cs` | Nuevo (18-09): cada nivel de `info.terrenos` sobre la base es una **terraza** de pasto con muros de tierra hasta la base, sin collider, recortada alrededor de lo que baja (`HuecoDelSuelo.CalcularTerraza`). |
| `Scripts/AmbienteVisor.Losas.cs` | Losas **de dibujo** en la realista, sacadas de los 243 polígonos de `areas_tributarias`. Sin collider y fuera de `ObjetosDeElementos`. |
| `Scripts/VisorEstructura.cs` | Carga asíncrona, secciones b×h en la realista, fantasma de lo que queda fuera del piso filtrado y muros cizallados en la deformada. |
| `Scripts/VisorSemana04.Superposicion.cs` | E1..E3 precalculados y el caso LIBRE pedido a `POST /combinar` con cuatro sliders. |
| `Scripts/VisorSemana04.Mapa.cs` | Mapa demanda/capacidad (verde, amarillo, rojo, morado y gris) con conteos, lista de críticos y "Ver el caso con mas NO PASA". |
| `Scripts/VisorSemana04.Hooks.cs` | Puntos de extensión del anexo: `RegistrarCasoExterno` y `ContarDemandas` (el mismo NO PASA n/m en la cabecera y en la leyenda). |
| `Scripts/VisorSemana04.cs` · `.Panel.cs` · `.PM.cs` · `.Diagramas.cs` | El anexo de la Semana 4, que ahora se marca **desactualizado** tras una edición. La curva P-M también se dibuja dentro de la pestaña Elemento. |
| `Scripts/EditorEstructura.cs` · `Scripts/AnalizadorEstructural.cs` | La pestaña Modificar: borrar, crear y mover, "Recalcular en el servidor (Enter)", casos G/Q/EX/EY del reanálisis, tabla de equilibrio que envía Python y "Abrir Excel de este reanalisis". |
| `Scripts/VisorCargaMovil.cs` | La pestaña Carga movil: posición, Play, reparto, conservación y la deformada de esa posición, todo leído del JSON. |
| `Scripts/CamaraOrbital.cs` | Táctil (un dedo orbita, dos hacen pinza y paneo) y encuadre que descuenta el panel. |
| `Scripts/CapturaSemana05.cs` | Con `-capturarS5 <carpeta>` saca las 25 fotos y escribe `registro.txt`. Sin ese argumento no hace nada. |
| `Scripts/CapturaSemana04.cs` · `Scripts/VisorSemana03.cs` · `Scripts/ModeloEstructural.cs` | Scroll de la foto 01 de la S4, lectura asíncrona con aviso de "otro modelo" y los campos nuevos del contrato (`cota_terreno`, `EquilibrioCaso`, `excel`). |
| `Editor/ConstruirApp.cs` · `Editor/ConfigurarEscena.cs` | Builds de Windows, Web (compresión `Disabled`) y Android (avisa si falta el módulo), y el montaje reproducible de la escena. |
| `StreamingAssets/` | `modelo_unity_edificio.json`, `semana03.json`, `semana04.json`, `superposicion.json`, `carga_movil.json` y `resultados.xlsx`, todos del LT2 (los copia `lanzar_unity.py sincronizar lt2`). |

---

## Dónde está cada criterio de la rúbrica

| criterio | pts | en la app | en el código | cómo se verifica |
| --- | --- | --- | --- | --- |
| Viewer estructural | 5 | Navegación (arrastrar, rueda, F, C). Selección de barra, nodo o apoyo con inspector en la pestaña **Elemento**. Capas (apoyos por tipo, ejes locales, áreas tributarias, diafragmas). Deformada y diagramas en **Caso**. P-M dentro de Elemento. Filtro de piso en **Vista**. | `VisorQA.cs`, `CamaraOrbital.cs`, `VisorEstructura.cs`, `VisorSemana04.Diagramas.cs`, `VisorSemana04.PM.cs` | `comparar_unity.py` bloque [4]: 58 filas, 0 FALLA. Fotos 01-14b. `test_contrato_semana04.py` (59 OK). |
| Modificación / reanálisis | 4 | **M1**: pestaña **Modificar**, borrar la barra 69 y "Recalcular en el servidor (Enter)". Se ve el UZ del nodo 186 y la tabla de equilibrio. **M2**: `--cs 0.20` → anexo → cerrar y abrir la app. | `EditorEstructura.cs`, `AnalizadorEstructural.cs`, `comun/servidor_opensees.py`, `semana04/exportar_unity.py` | `reanalisis_demo.py` y `comparar_anexos.py` (en la suite), `test_reanalisis.py`, `test_servidor.py`. `comparar_unity.py` bloque [2]: 138 filas, 0 FALLA. Fotos 21-22. |
| Superposición / demanda-capacidad | 4 | **Caso** → "Superposicion (Semana 5)": E1, E2 y E3 sin servidor. "Factores libres (servidor Python)" con cuatro sliders → LIBRE. "Mapa demanda / capacidad" y "Criticos del caso activo". | `semana05/superposicion.py`, `servidor_s5.py`, `VisorSemana04.Superposicion.cs`, `VisorSemana04.Mapa.cs` | `verificar_superposicion.py lt2` y `ingenieria` (en la suite). `test_contrato_semana05.py` (181 OK). `comparar_unity.py` bloque [1]: 136 filas, 0 FALLA. Fotos 14-18. |
| QA / UX | 3 | Las seis preguntas en la pestaña Elemento, la cabecera fija, "Abrir Excel de resultados", la vista Realista o Técnica y la carga móvil. | `VisorQA.cs`, `PanelUI.cs`, `AmbienteVisor*.cs`, `VisorCargaMovil.cs`, `comun/excel.py` | [`UX.md`](UX.md). `comparar_unity.py` bloques [3] (85 filas) y [5] (41 filas). `test_excel.py` (en la suite). 23 fotos. |
| Preparación móvil, IA y gestión | 4 | Vista → "Tamano del texto y equipo" muestra `SystemInfo` y el dpi. En Windows no hay nada más que mostrar. | `LectorStreaming.cs`, `CamaraOrbital.cs` (táctil), `PanelUI.Escala()`, `ConstruirApp.ConstruirWeb/ConstruirAndroid`, `AGENTS.md` | [`MOVIL.md`](MOVIL.md). `lanzar_unity.py android lt2 --seco` sale con 1 y lo dice. Registro de IA en `AGENTS.md`. Rama `semana05`. |

Fuera de rúbrica, pedidas por Pedro: (a) Excel, (b) realismo y suelo,
(c) panel ordenado. También está la carga móvil, que es opcional. Las tres
mejoras se ven en las fotos 01-08. La carga móvil se ve en las 19-20.

---

## Cómo se corre

Todo desde la carpeta del repo, con el Python del proyecto. El detalle y
el orden completo están en [`COMANDOS.md`](COMANDOS.md).

```powershell
.\.venv\Scripts\python.exe comun\verificar_todo.py         # 44 de 44 EN OK, 2 a 8 min (17-09, Unity cerrado)
.\.venv\Scripts\python.exe comun\lanzar_unity.py sincronizar lt2
.\.venv\Scripts\python.exe semana05\servidor_s5.py         # terminal aparte, se deja abierta
.\.venv\Scripts\python.exe comun\lanzar_unity.py app lt2   # la app de Windows
```

Sin servidor funcionan el modelo, los casos del anexo, los diagramas, la
P-M, el mapa D/C, E1..E3 y la carga móvil. Con servidor funcionan además
el caso LIBRE y el reanálisis de la M1.

---

## Las decisiones que conviene saber defender

- **La regla de oro también en la superposición.** Unity no suma casos.
  u, f y las estaciones son lineales en λ, pero la demanda-capacidad no lo
  es: el extremo que manda cambia, M de una columna es `hypot(My, Mz)` y
  Mn depende de P. Sumar λ·u daría otro número. Por eso E1..E3 vienen
  precalculados por `superposicion.py` y LIBRE lo combina el servidor.
  Unity pinta lo que le llega. E3 pedido al servidor da lo mismo que el
  precalculado: 24.6285 mm y NO PASA 4/69 en las fotos 17 y 18.
- **Tras editar, el anexo queda desactualizado, y se dice.** Borrar la
  columna 69 cambia la geometría. Los casos de `semana04.json`, E1..E3,
  LIBRE y la carga móvil son del modelo original. Se marcan así, la carga
  móvil se apaga y la cabecera deja **una** línea: "Modelo editado (borrar
  elemento 69). Mostrando el reanalisis del servidor (G, Q, EX, EY); el
  anexo S4 y E1-E3 siguen siendo del modelo original." (foto 21). Rehacer
  el anexo sobre el modelo editado
  exigiría llevar la edición a `data/modelo/` y reexportar
  ([`MODIFICACIONES.md`](MODIFICACIONES.md), limitación 1).
- **Cota del terreno: el suelo va donde arranca la estructura.** Desde el
  18-09 el LT2 declara `-7.97` (sus 16 apoyos, de los que salen 8
  columnas y 8 muros) e Ingeniería su `0.00` local (29 apoyos, 10
  columnas), que con el `dz` del calce es el mismo `-7.97`. Ninguna
  lámina rotula el N.T.N.: la cota se mide en el modelo. **Solo dibuja**:
  ningún cálculo la usa, así que cambiarla mueve el suelo y no cambia
  ningún número. Durante la entrega decía `-4.01`, `provisorio` (así
  quedó en `reports/semana05.md`), y por eso el visor dibujaba una
  excavación para ver los apoyos; con la cota en el arranque ya no hay
  nada bajo el suelo y no se cava.
- **El terreno en dos niveles (18-09).** El terreno real no es un plano:
  la planta de fundaciones de Ingeniería rotula dos N.R. (−7.97 y −4.01,
  fundación escalonada), y sus 39 apoyos en terreno `[0 0 1 1 1 0]` están
  en −4.01. Con un solo plano en −7.97 se dibujaban 3.96 m en el aire. Ahora
  el suelo viaja en niveles (`info.terrenos`, `CONTRATO.md` §11): la base
  en `cota_terreno` (−7.97, el nivel más bajo, como antes) y una
  **terraza** en −4.01 (3.96 del datum de Ingeniería). Su región no se
  dibujó a ojo: sale de la misma definición con que `benchmark_3d.py`
  crea esos apoyos (el nivel 1 apoya en el terreno donde no tiene el
  subterráneo debajo, `sobre_subterraneo()`), recortada a la caja de los
  39 apoyos más 0.35 m. Resultado, medido con
  `comun/test_contrato_unity.py`: LT2 16 apoyos en −7.97; Ingeniería 29 en
  0.00 y 39 en 3.96; conjunto 45 en −7.97 y 39 en −4.01; ninguno flotando
  ni enterrado. El visor recorta la terraza alrededor de lo que baja a la
  base (11 apoyos de la base caen bajo su huella: el recinto de muros del
  suroeste, las columnas del eje F y dos del eje 1), así que ese recinto
  se ve como un pozo y sus 6 apoyos de −4.01 quedan encima de los muros; los
  otros 33 quedan sobre el pasto de la terraza. **Solo dibuja**: los
  anexos, el D/C y el Excel no cambian.
- **Excel versionado y abrible desde Unity.** `data/excel/` va a git y
  el libro es determinista: con los mismos datos salen los mismos bytes.
  `lanzar_unity.py sincronizar lt2` lo copia a
  `StreamingAssets/resultados.xlsx`, y el botón de la cabecera lo abre. En
  el editor, si falta esa copia, abre el versionado. La hoja Reacciones
  **no se suma entera**: trae las columnas "Cuenta en Fx/Fy" y "Cuenta en
  Fz" con la regla de `calcular.equilibrio`. Sumar la columna completa
  dobla el corte basal. En EX del LT2 la suma filtrada da −3792.2820 kN,
  igual al equilibrio, y la columna entera da −7584.5639.
- **Windows primero.** Pedro decidió que el móvil sea la última
  prioridad y no instalar Android. El código quedó listo para móvil
  (lectura con `UnityWebRequest`, táctil, escala por DPI, métodos de build
  Web y Android), pero **el build móvil inicial no se hizo**, por
  prioridad y no por un bloqueo técnico. Ver [`MOVIL.md`](MOVIL.md).
- **Las losas son solo dibujo.** El modelo no tiene losas como elemento:
  la carga llega a las vigas por área tributaria y la rigidez en planta la
  da el diafragma. En la vista realista se dibujan con los mismos
  polígonos de `areas_tributarias` que ya carga el panel (243 entradas en
  5 cotas). Tienen un espesor de dibujo de 0.15 m y la cara superior en
  z + 0.41, el canto de la V 0.60x0.80. No tienen collider, no están en
  `ObjetosDeElementos` y se esconden con deformada, diagramas, mapa D/C o
  carga móvil, porque no siguen la deformada.
- **Realista dibuja las secciones b×h.** Lo que se dibujaba en el eje
  quedaba dentro de la caja. Por eso las barras que tienen diagrama se
  dibujan delgadas y la selección se marca con las aristas cian. La
  técnica sigue igual que en la Semana 4: el `registro.txt` de la S4 sale
  idéntico byte a byte (151 líneas, LT2).
- **Lo que muestra Unity se compara con Python, no a ojo.**
  `comparar_unity.py` cruza 1053 datos del registro con Python en 486
  filas. Cada tolerancia es la suma de sus causas medidas: `f32` (el float
  de 32 bits de JsonUtility), `ref`, `impr`, `ent32` y `srv` (el redondeo
  del servidor en la M1).
