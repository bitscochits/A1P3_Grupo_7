# Semana 5 — El contrato entre paquetes

Lo que un paquete puede usar de otro, con qué nombre exacto y quién es el
dueño. Lo escribió el paquete **W1** antes de que empezaran los paquetes
paralelos, y todo lo que aparece acá como API C# **existe y compila** en la
rama `semana05` desde W1 (comprobado con `semana05/compilar_unity.py`; ver §9).

Reglas para leerlo:

- Si necesitas algo de otro paquete y no está acá, **no lo agregues en su
  archivo**: pídelo (`pedidos_a_otros`) y trabaja con lo que hay.
- Si cambias algo que está acá (un nombre, una clave, una firma), rompes a
  otro paquete. No se cambia; se agrega.
- "Dueño" = el único paquete que edita ese archivo en la fase paralela.

```
Python calcula ──► JSON (data/, StreamingAssets/) ──► Unity muestra
      ▲                                                   │
      └──── servidor_s5.py :5000  ◄── HTTP (/analizar, /combinar, /estados)
```

---

## 1. Quién es dueño de qué (h)

Solo editas los archivos de tu fila. `semana05/compilar_unity.py`,
`semana05/CONTRATO.md` y los archivos de W1 no los edita nadie en la fase
paralela.

| paquete | archivos exclusivos |
| --- | --- |
| **W1** (hecho) | `semana05/compilar_unity.py`, `semana05/CONTRATO.md`, `unity/Assets/Scripts/ModeloEstructural.cs`, `EventosVisor.cs`, `LectorStreaming.cs`, `IPanelIncrustable.cs`, `PanelUI.cs`, `VisorSemana04.Hooks.cs`, `comun/test_contrato_unity.py`; sincronizó `data/unity/semana03.json`, `semana04.json` y `StreamingAssets/semana03.json`, `semana04.json`, `modelo_unity_edificio.json` (LT2) |
| **P1** | `comun/excel.py` (W1 dejó un stub con las firmas), `semana05/exportar_excel.py`, `semana05/test_excel.py`, `comun/rutas.py` (W1 agregó `EXCEL`, `EXCEL_REANALISIS`, `excel_resultados()`, `excel_reanalisis()`), `requirements.txt`, `setup.ps1`, `data/excel/` |
| **P2** | `semana05/superposicion.py`, `semana05/servidor_s5.py`, `semana05/estados_s5.json`, `semana05/verificar_superposicion.py`, `semana05/test_contrato_semana05.py`, `semana05/evidencia/superposicion_*`, `data/unity/superposicion_lt2.json`, `unity/Assets/StreamingAssets/superposicion.json` |
| **P3** | `comun/servidor_opensees.py`, `test_servidor.py`, `edificios/lt2/tests/test_reanalisis.py`, `semana05/reanalisis_demo.py`, `semana05/comparar_anexos.py`, `semana05/MODIFICACIONES.md`, `GUIA_unity_paso_a_paso.md` |
| **P4** | `semana05/carga_movil.py`, `semana05/CARGA_MOVIL.md`, `semana05/evidencia/carga_movil_*`, `data/unity/carga_movil_lt2.json`, `unity/Assets/StreamingAssets/carga_movil.json`, `unity/Assets/Scripts/VisorCargaMovil.cs` |
| **U1** | `unity/Assets/Scripts/VisorEstructura.cs`, `VisorSemana03.cs`, `CamaraOrbital.cs` (W1 agregó stubs, §2.2) |
| **U2a** | `unity/Assets/Scripts/VisorQA.cs`, `CapturaSemana04.cs` |
| **U2b** | `unity/Assets/Scripts/VisorSemana04.Panel.cs`, `VisorSemana04.PM.cs`, `VisorSemana04.Mapa.cs` |
| **U3** | `unity/Assets/Scripts/VisorSemana04.cs`, `VisorSemana04.Diagramas.cs`, `VisorSemana04.Superposicion.cs` |
| **U4** | `unity/Assets/Scripts/AmbienteVisor.cs`, `edificios/lt2/perfiles/lt2_2024_22.json`, `edificios/lt2/exportar_unity.py`, `edificios/conjunto/exportar_unity.py`, `data/unity/lt2.json`, `data/unity/conjunto.json` |
| **U5** | `unity/Assets/Scripts/EditorEstructura.cs`, `AnalizadorEstructural.cs` |
| **U6** | `unity/Assets/Editor/ConstruirApp.cs`, `comun/lanzar_unity.py` |
| **U7** | `unity/Assets/Scenes/SampleScene.unity`, `unity/Assets/Editor/ConfigurarEscena.cs`, `unity/Assets/Settings/PC_RPAsset.asset`, `unity/Assets/Settings/Mobile_RPAsset.asset` |
| **D0** | `semana05/APP_AUTONOMA.md` |
| D1 (después) | `semana05/README.md`, `COMANDOS.md`, `GUION_DEMO.md`, `UX.md`, `verificar_visor_s5.py`, `comun/verificar_todo.py`, `README.md`, `CLAUDE.md` |
| I1 (integración) | `semana05/capturas/`, `semana05/capturas_s4/`, `unity/Assets/Scripts/CapturaSemana05.cs` (decisión 11), los `.meta` nuevos, resincronizar `data/unity/semana0*.json` y `StreamingAssets/` |
| U8 / D2 (después) | `semana05/MOVIL.md`, `semana05/capturas_movil/` / `reports/semana05.md`, `AGENTS.md` |

Nadie crea `.meta` a mano: los genera Unity al abrirse en la integración.

---

## 2. API C# (a)

Todo vive en el namespace global y en `Assembly-CSharp`. Se compila con:

```
.venv\Scripts\python.exe semana05\compilar_unity.py --solo <tus .cs>
```

Sale con 1 solo si hay errores CS en tus archivos; los de otros se listan
como AVISO (otros están editando). Código 2 = no se pudo verificar.

- Las rutas de `--solo` van relativas a la raíz del repo
  (`unity\Assets\Scripts\PanelUI.cs`); un nombre suelto (`PanelUI.cs`) vale
  si hay uno solo en `unity/Assets`. Una ruta que no es un `.cs` existente
  dentro de `unity/Assets` sale con **2**: antes daba OK sin haber mirado el
  archivo (todos sus errores salían como ajenos).
- Compila con los `.csproj` **del editor** (`UNITY_EDITOR` definido y
  `UnityEditor.dll` referenciado también en `Assembly-CSharp`): no ve lo que
  solo falla al construir la app (`using UnityEditor` fuera de
  `Assets/Editor` sin `#if UNITY_EDITOR`, código dentro de `#if UNITY_WEBGL`,
  `#if UNITY_ANDROID` o `#if !UNITY_EDITOR`). Eso lo prueba la build de I1.
- No dejes `.cs` de prueba dentro de `unity/Assets`: los comodines los
  compilan para todos.

### 2.1 Lo que agregó W1

#### `EventosVisor` (estático) — `EventosVisor.cs`

Quien se suscribe en `OnEnable`/`Start` se desuscribe en
`OnDisable`/`OnDestroy`. Cada suscriptor se llama en su propio `try/catch`:
uno que falla no corta a los demás. **Nadie llama a
`VisorEstructura.Redibujar()` dentro de un suscriptor de `Redibujado` o
`MaterialesCambiados`** (lazo infinito).

| evento | firma | avisa (con `Avisar*`) | escuchan |
| --- | --- | --- | --- |
| `ModeloCargado` | `Action` | `VisorEstructura` (U1), una vez, después del primer `Redibujar` y con `Listo = true` | `CamaraOrbital` encuadra (U1), `AmbienteVisor` (U4), `VisorQA` (U2a) |
| `Redibujado` | `Action` | `VisorEstructura.Redibujar()` al terminar (U1). `AvisarRedibujado()` avisa **después** `MaterialesCambiados` | `AmbienteVisor` registra el material técnico y aplica la vista (U4); `VisorQA` refresca capas (U2a) |
| `ModeloEditado` | `Action<string motivo>` | `EditorEstructura.MarcarModificado` (U5), p. ej. `"borrar elemento 69"` | `VisorSemana04` marca el anexo desactualizado (U3); `VisorQA` aviso ámbar en la cabecera (U2a); `VisorCargaMovil` se apaga con aviso (P4) |
| `PedirCentrar` | `Action<Vector3 centro, float tamano>` | `VisorQA` "Ir a ID"/"Centrar" (U2a), lista de críticos del mapa (U2b), `VisorCargaMovil` (P4) | `CamaraOrbital` (U1). `centro` en coordenadas **Unity** (`Ejes.AUnity`); `tamano` en m; `tamano <= 0` = sin cambiar el zoom |
| `SeleccionCambio` | `Action<string tipo, int id>` | `VisorQA` (U2a), **única fuente de selección** | `EditorEstructura` (U5) sincroniza su selección; quien quiera. `tipo` = `EventosVisor.TIPO_ELEMENTO` (`"elemento"`), `TIPO_NODO` (`"nodo"`) o `TIPO_NINGUNO` (`""`, id `-1`) |
| `VistaCambio` | `Action` | quien cambie `AjustesVista` (la pestaña Vista de `VisorQA`, U2a) | `VisorEstructura` redibuja con el filtro de piso (U1); `AmbienteVisor` (U4); `VisorSemana04.Refrescar` (U3) |
| `MaterialesCambiados` | `Action` | `AvisarRedibujado()` (automático) y `AmbienteVisor` al terminar de aplicar una vista (U4) | mapa D/C (U2b). Protocolo en §8 |

W1 ya dejó en `VisorEstructura.cs` las llamadas `AvisarModeloCargado()` (en
`Start`) y `AvisarRedibujado()` (al final de `Redibujar`, y también en el
`return` de `Modelo.elementos == null`, que ya destruyó y rehízo los nodos;
el `return` de `Modelo == null` no avisa porque no tocó ningún objeto). U1
las conserva al pasar `Start` a corrutina.

#### `AjustesVista` (estático) — `EventosVisor.cs`

| miembro | valor por defecto | qué es |
| --- | --- | --- |
| `bool realista` | `true` | vista realista (texturas) o técnica (colores por tipo). Decisión 7 |
| `bool suelo` | `true` | dibujar el suelo en `info.cota_terreno` |
| `float cotaVisible` | `float.NaN` | filtro de piso: NaN = todos; si no, la cota z OpenSees del piso |
| `const float TOLERANCIA_COTA` | `0.01f` | la de `VisorQA.CotasDelModelo` |
| `bool HayFiltroDePiso` | | `!float.IsNaN(cotaVisible)` |
| `bool EnCotaVisible(float z)` | | un punto (nodo, apoyo, etiqueta) pasa el filtro |
| `bool ElementoEnCotaVisible(float zA, float zB)` | | una barra pasa si la **menor** de sus dos cotas es la visible: la losa y lo que nace de ella. Es la regla que ya usaban los diagramas de la Semana 4 (`VisorSemana04.Diagramas.cs:224`, `Mathf.Min(a.z, b.z)`), y con ella ninguna cota queda sin barras (con la mayor, la más baja tiene 0: −7.97 del LT2 y del conjunto, 0.00 de Ingeniería; con la menor 16, 45 y 29, contado en `data/unity/*.json`). Una sola regla para visor (U1), diagramas (U3), mapa D/C (U2b) y capas QA (U2a): hoy `VisorQA` dibuja ejes locales (`VisorQA.cs:458`) e IDs (`:536`) si **cualquiera** de los dos nodos está en la cota; U2a los cambia a esta |

Quien cambia un campo llama a `EventosVisor.AvisarVistaCambio()`.

#### `LectorStreaming` (estático) — `LectorStreaming.cs`

| firma | qué hace |
| --- | --- |
| `string UrlDe(string nombre)` | URL de `StreamingAssets/<nombre>`; sin esquema arma `file:///` escapado (la ruta del repo tiene espacios). Un `nombre` que ya es URL (`://`) o ruta absoluta se usa tal cual |
| `IEnumerator Leer(string nombre, Action<string> ok, Action<string> error)` | `UnityWebRequest.Get`; llama exactamente uno de los dos, una vez. Uso: `StartCoroutine(LectorStreaming.Leer("semana04.json", t => ..., e => ...))`. Funciona en Windows, Android (`jar:file://`) y Web |
| `const string EXCEL_RESULTADOS` | `"resultados.xlsx"` |
| `string RutaExcelResultados(string edificio)` | `StreamingAssets/resultados.xlsx` si existe; en el editor, si no, `data/excel/<edificio>_resultados.xlsx` del repo; si no, `null` |
| `bool AbrirArchivo(string ruta, out string error)` | abre con el programa del sistema (`Application.OpenURL`) |

Botones de Excel (decisión 6): **U2a** pone "Abrir Excel de resultados" en la
pestaña Vista (o la cabecera) con
`RutaExcelResultados(s4.Anexo.info.edificio)` + `AbrirArchivo`. **U5** pone
"Abrir Excel de este reanálisis" en su panel con la ruta de
`RespuestaServidor.excel` (§3).

#### `IPanelIncrustable` — `IPanelIncrustable.cs`

```csharp
public interface IPanelIncrustable
{
    string TituloPestana { get; }
    bool PanelPropio { get; set; }
    void DibujarPanel();
}
```

Protocolo en §8.

#### `PanelUI` (estático) — `PanelUI.cs`

- `void Preparar()` — **primera línea de cada `OnGUI`** que use los estilos
  (copian de `GUI.skin`, que solo existe dentro de `OnGUI`). Reconstruye solo
  si cambió la escala.
- `float Escala()` (dpi/96 en PC, dpi/160 en móvil; sin dpi, alto/1080;
  acotada 0.8–3.5, por `EscalaUsuario`), `float EscalaUsuario { get; set; }`
  (PlayerPrefs `panel_escala`), `float Px(float)`, `float AltoBoton`,
  `bool EsMovil`, `float UmbralArrastre()` = `max(5, 0.08·Screen.dpi)` px (la
  usan `CamaraOrbital` U1 y `EditorEstructura` U5).
- Estilos (`GUIStyle`, `null` hasta el primer `Preparar`): `Texto`, `Tenue`,
  `Titulo`, `Seccion`, `Boton`, `BotonActivo`, `Caja`, `Aviso`, `Pasa`,
  `NoPasa`, `Mono` (ancho fijo si la plataforma tiene una fuente así; si no,
  igual a `Texto`).
- Controles: `bool Plegable(string clave, string titulo, bool abiertoPorDefecto)`
  (el cambio se aplica en el siguiente Layout), `void FijarPlegable(string clave, bool abierto)`,
  `void Insignia(bool pasa)`, `void Insignia(string texto, GUIStyle estilo)`,
  `bool Opcion(bool activo, string texto, params GUILayoutOption[])` (el activo
  lleva `"> "`), `void Fila(string etiqueta, string valor)`.
- Claves de `Plegable` con prefijo de paquete: `qa.`, `s4.`, `mapa.`, `sup.`,
  `editor.`, `movil.`.
- Colores: `ColorTexto`, `ColorTenue`, `ColorFondo`, `ColorSeccion`,
  `ColorBoton`, `ColorBotonEncima`, `ColorAcento`, `ColorAviso`, `ColorPasa`,
  `ColorNoPasa`.
- Demanda/capacidad, una sola definición para el mapa (U2b), su leyenda y el
  inspector (U2a): `Color ColorDemandaCapacidad(bool conFamilia, float u, bool pasa)`
  → gris sin familia; morado `u >= U_FUERA_DE_CURVA` (9999); rojo `!pasa`;
  amarillo `u >= UMBRAL_DC_CERCA` (0.7); verde el resto. Lee `u` y `pasa`
  del JSON, no revisa nada.
- Sin `GUI.matrix`: los `Rect` siguen en píxeles reales (los hit-tests de
  `MouseSobreUI`/`MouseSobrePanel` no cambian).

#### `VisorSemana04.Hooks.cs` (partial de `VisorSemana04`)

| miembro | quién lo implementa / usa |
| --- | --- |
| `[NonSerialized] public int versionCasos` | lo sube **solo** la implementación de `RegistrarCasoExterno` (U3); lo leen las firmas de caché: P-M (U2b), diagramas (U3), mapa (U2b) |
| `partial void Hook_DibujarSuperposicion()` | implementa U3 en `VisorSemana04.Superposicion.cs`; lo llama U2b **una vez** dentro de `DibujarControles` |
| `public void RegistrarCasoExterno(CasoS4 caso)` | público, **ya existe**: valida `caso != null` y nombre, y delega en `partial void Hook_RegistrarCasoExterno(CasoS4 caso)`, que **implementa U3 en `VisorSemana04.cs`** (agrega o reemplaza por nombre en `Anexo.casos`, rearma `casoPorNombre`/`esfuerzos`/`demandas`, `versionCasos++`, y si es el caso activo re-aplica deformada y redibuja). **Nadie declara otro `RegistrarCasoExterno`** |
| `partial void Hook_DibujarPMEnLinea()` / `public void DibujarPMEnLinea()` | implementa U2b en `PM.cs`; llama U2a en la pestaña Elemento |
| `public static void ContarDemandas(CasoS4, out int noPasan, out int fueraDeCurva, out int total)` | cabecera "NO PASA n/m" (U2a) y leyenda del mapa (U2b): el mismo número |

Miembros privados nuevos en los partial con prefijo de su archivo: `Sup_`
(Superposicion), `Mapa_` (Mapa), `Pnl_` (Panel), `PM_` (PM).

#### `ModeloEstructural.cs`

| cambio | detalle |
| --- | --- |
| `Elemento.area_tributaria`, `Elemento.w_gravedad` (float) | los traen Ingeniería y conjunto; en el LT2 quedan en 0 (no los exporta por elemento). Viajan de vuelta al servidor con `ToJson` |
| `InfoModelo.edificio` (string) | `"lt2"`, `"ingenieria"`, `"conjunto"`; hoy ningún JSON lo trae (vacío) |
| `InfoModelo.cota_terreno = -9999f` | cota z OpenSees del terreno; `< -9000` = no viene: `AmbienteVisor` pone el suelo en el apoyo más bajo con `LogWarning` (ajuste del coordinador a la decisión 7; ver §10) |
| clase `EquilibrioCaso` | `float[] aplicada_kN`, `float[] reaccion_kN`, `float[] error_kN`, `int cargas_sin_convertir`, `int nodos_en_diafragma`, `bool confiable`: las claves de `comun/calcular.equilibrio` |
| `CasoResultado.equilibrio` | `EquilibrioCaso`. "Vino" se pregunta: `c.equilibrio != null && c.equilibrio.aplicada_kN != null && c.equilibrio.aplicada_kN.Length == 3` |
| `RespuestaServidor.excel`, `RespuestaServidor.excel_error` (string) | §3. Preguntar con `string.IsNullOrEmpty` |
| `List<AreaTributaria> TributariasDe(int)` | todas las entradas de la viga; lista vacía, nunca null |
| `float AreaTributariaTotal(int)` | `elemento.area_tributaria` si es > 0; si no, suma de sus entradas (el test de contrato comprueba que coinciden) |
| `Elemento ElementoPorId(int)` | índice que se rehace si cambia la cantidad de elementos |
| `InvalidarIndice()` | ahora también limpia elementos y tributarias. **U5 lo llama después de toda edición** de nodos, elementos o secciones |
| `TributariaDe(int)` | sin cambios (devuelve una entrada), por compatibilidad |

### 2.2 API existente por dueño

**`VisorEstructura` (U1)** — la estructura.

| miembro | uso |
| --- | --- |
| `ModeloEstructural Modelo { get; }` | el modelo cargado; el mismo objeto que se manda al servidor |
| `bool Listo { get; }` *(W1)* | `WaitUntil(() => visor != null && visor.Listo)` para quien llega tarde a `ModeloCargado` |
| `IReadOnlyDictionary<int, GameObject> ObjetosDeElementos`, `ObjetosDeNodos` *(W1)* | todos los objetos dibujados por id; no redibujar mientras se recorre |
| `GameObject ObjetoDeElemento(int id)`, `ObjetoDeNodo(int id)` | `null` si la capa está apagada o el id no existe. El `Renderer` es `go.GetComponent<Renderer>()` |
| `Vector3 PosicionActual(Nodo n)` *(W1)* | dónde está dibujado el nodo ahora (con deformada si está puesta), en coordenadas Unity |
| `void AplicarDeformada(List<DespNodo>)`, `bool mostrarDeformada`, `float factorEscala`, `void LimpiarDeformada()`, `bool HayDeformada`, `void UsarDeformadaPrecalculada()`, `void Redibujar()` | deformada, §2.3 |
| `static Shader ShaderCompatible()` | el shader que no sale magenta en URP; para todo material nuevo |
| `verNodos`, `verNodosAuxiliares`, `verColumnas`, `verVigas`, `verMuros`, `verBrazos`, `verPerfiles` | capas; después de cambiarlas, `Redibujar()` |

U1 agrega: `Start` como corrutina con `LectorStreaming`, filtro de piso con
`AjustesVista.EnCotaVisible`/`ElementoEnCotaVisible` al escuchar `VistaCambio`.

**`CamaraOrbital` (U1)** — `Vector3 centro`, `float distancia`,
`EncuadrarTodo()`, `MirarA(Vector3)`, `bool bloqueada`, `bool HuboArrastre`, y
*(W1)* `VistaPlanta()`, `VistaElevX()` (mira hacia +Y OpenSees), `VistaElevY()`
(hacia +X), `VistaIso()`. U1 agrega la suscripción a `PedirCentrar` y el
táctil.

**`VisorQA` (U2a)** — `SeleccionarElemento(int id)` (existe; lo usan los
botones de demo y la lista de críticos), `bool MouseSobreUI()`,
`bool NivelVisible(float z)`. U2a agrega pestañas, `SeleccionCambio`,
cabecera y botón de Excel.

**`VisorSemana04` (núcleo U3, panel U2b)** — lo que se lee desde afuera:

| miembro | qué es |
| --- | --- |
| `AnexoSemana04 Anexo { get; }` | el anexo leído; `Anexo.info.edificio` dice de qué edificio es |
| `string casoActivo` (campo), `CasoS4 CasoActivo()` | el caso que manda sobre panel, diagramas, P-M y deformada "Caso activo" |
| `void ElegirCaso(string nombre)` | cambia el caso activo (diferir si se llama desde `OnGUI`). U3: no retorna temprano si el caso es el mismo pero `versionCasos` cambió |
| `event Action CambioCasoActivo` | lo escucha `VisorQA` |
| `void Seleccionar(int id)`, `int Seleccionado { get; }` | selección de barra para diagramas y P-M |
| `ElementoS4 ElementoPorId(int)`, `EsfuerzosS4 EsfuerzosDe(int)` (caso activo), `DemandaS4 DemandaDe(int id, string caso)` | lectura del anexo |
| `void AplicarDeformadaDelCaso()`, `void QuitarDeformada()`, `void EnfocarElemento(int)` | deformada del caso activo y cámara |
| `string Aviso { get; }`, `bool AnexoCalzaConElModelo { get; }` | U3 los pone en "desactualizado" al llegar `ModeloEditado` |
| `void Refrescar()`, `void Redibujar()`, `MotivoSinDiagrama`, `AvisoDeLectura`, `MAGNITUDES`, `magnitud`, `mostrarDiagramas`, `soloSeleccionado`, `mostrarPM` | diagramas |
| `void DibujarControles()` (U2b) | lo llama `VisorQA` en la pestaña Caso: casos base (`tipo == "caso"`), combinaciones (`tipo == "combinacion"`), `Hook_DibujarSuperposicion()`, diagramas, mapa D/C y botones de demo. Los casos `tipo == "superposicion"` (LIBRE, E1..E3) **no** los dibuja el panel: los dibuja U3 en el hook |
| `string DescribirElemento(int)` (U2b) | texto del inspector; **congelado** (§2.5) |
| `bool MouseSobreVentana(Vector2)` | la ventana P-M no deja pasar clicks |

**`EditorEstructura` (U5)** — `bool MouseSobrePanel()` (con `PanelPropio == false`
devuelve `false`), implementa `IPanelIncrustable` con
`TituloPestana = "Modificar"`, avisa `ModeloEditado`. Con `PanelPropio == false`
deja de hacer su propio raycast de selección y toma la de `SeleccionCambio`
(selección única, decisión 9); sigue manejando el arrastre del nodo
seleccionado y las teclas (solo si `GUIUtility.keyboardControl == 0`).

**`AnalizadorEstructural` (U5)** — `string urlServidor`
(`http://localhost:5000/analizar`), `EnviarModelo()`, `bool MostrarCaso(string)`,
`List<string> CasosDisponibles()`, `DespNodo DesplazamientoDe(int)`,
`FuerzaElemento FuerzaDe(int)`, `bool Ocupado`.

**`AmbienteVisor` (U4)** — se crea solo con
`[RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]`; no
expone API: todo por eventos y `AjustesVista`. Suelo **sin collider**.

**`VisorCargaMovil` (P4)** — se crea solo igual que `AmbienteVisor`;
implementa `IPanelIncrustable` con `TituloPestana = "Carga movil"`. Lee
`carga_movil.json` con `LectorStreaming` (§5).

**`ConstruirApp` (U6)** — `static void Construir()` no cambia de nombre
(`lanzar_unity.py` llama `ConstruirApp.Construir`).

### 2.3 Dibujar una deformada desde un conjunto de desplazamientos

El formato es **`List<DespNodo>`**: `{id, ux, uy, uz, rx, ry, rz}` por nodo,
traslaciones en **m** y giros en **rad**, en ejes **OpenSees** (Z vertical). Es
el mismo de `CasoS4.desplazamientos`, `CasoResultado.desplazamientos` y
`PosicionMovil.desplazamientos`.

```csharp
visor.mostrarDeformada = true;          // sin esto no se ve
visor.factorEscala = escala;            // opcional; solo grafico
visor.AplicarDeformada(desplazamientos); // ya llama a Redibujar()
```

- Un nodo que no está en la lista se dibuja en su posición original. Se
  espera la lista **completa** (todos los nodos del modelo).
- `AplicarDeformada` reemplaza la deformada anterior entera (no acumula).
- Para quitarla: `visor.LimpiarDeformada(); visor.Redibujar();` — **solo si la
  puso tu script** (patrón `deformadaPuesta` de `VisorSemana04`). La última que
  se aplica manda; nadie re-aplica la suya sin que el usuario la pida.
- Fuentes de deformada: `VisorQA` (Sin / Cargas G / Sismo EX, EY / Caso activo),
  `VisorSemana04.AplicarDeformadaDelCaso`, `AnalizadorEstructural.MostrarCaso`,
  `VisorCargaMovil`.

### 2.4 El objeto y el renderer de un elemento

```csharp
GameObject go = visor.ObjetoDeElemento(id);      // null si no se dibuja
Renderer r = go != null ? go.GetComponent<Renderer>() : null;
foreach (var kv in visor.ObjetosDeElementos) { int id = kv.Key; Renderer rr = kv.Value.GetComponent<Renderer>(); }
```

Los objetos se destruyen y se crean de nuevo en cada `Redibujar()`: no guardar
referencias entre redibujos (escuchar `Redibujado`/`MaterialesCambiados`).
Cambiar `sharedMaterial` de estos renderers: solo según §8.

### 2.5 Lo que no se toca

| qué | por qué |
| --- | --- |
| campos privados `VisorQA.scroll` (Vector2), `VisorQA.refrescar` (bool), `CamaraOrbital.pitch`, `CamaraOrbital.yaw` (float) | `CapturaSemana04.cs` los lee por reflexión |
| **todo miembro público que ya existe** (en la fase paralela no se renombra ni se borra; se agrega al lado) | otro paquete lo usa en SU archivo, y el error saldría en el archivo del otro (para `--solo` del que rompe es "ajeno"). Los que no están en §2.2: `VisorQA.soloNivel` (`VisorSemana04.Diagramas.cs`, U3); de `VisorSemana03` (U1) `Anexo`, `Redibujar`, `aplicarDeformada`, `casoCarga`, `casoDeformada`, `cargasConLaDeformada`, `mostrarCargas`, `mostrarArmadura`, `enfierrarTodas`, `jaulaDetalle` (`VisorQA` y `CapturaSemana04`, U2a); `AnalizadorEstructural.casoActivo` (U2a); los campos `visor`, `camara`, `orbital`, `analizador`, `analizarAlIniciar` que asigna `ConfigurarEscena` (U7) |
| el texto de `VisorSemana04.DescribirElemento` | va a `registro.txt` y se cruza con `semana04/trazabilidad.py` |
| el literal `JsonUtility.FromJson<AnexoSemana04>` en `VisorSemana04.cs` | lo exige `semana04/test_contrato_semana04.py` |
| las clases de contrato de `VisorSemana04.cs` y `ModeloEstructural.cs`; no agregar clases nuevas a `VisorSemana04.cs` | los tests las leen como texto (un campo por línea, sin métodos) |
| nombres `Elem_<id>_<tipo>`, `Nodo_<id>`, `NodoAux_<id>` y `DatoElemento`/`DatoNodo` | `objeto_unity` se compara en vivo en el inspector |
| `nombreArchivo` de la escena; `ConstruirApp.Construir` | `lanzar_unity.nombre_que_lee_el_visor()` y el build |
| el log `Modelo cargado: N nodos, M elementos` de `VisorEstructura.CargarJSON` | se busca en el logcat del móvil |

### 2.6 Convenciones

- Clases `[Serializable]` nuevas con sufijo de paquete para no chocar en el
  namespace global: U3 `PeticionCombinar`, `RespuestaCombinar`,
  `RespuestaEstados`, `*S5`; P4 `*Movil`. Reusar `DespNodo`, `ReacNodo`,
  `EquilibrioCaso`, `CasoS4` (no redefinir).
- `FindObjectsByType<T>()` **sin** `FindObjectsSortMode` (en Unity 6.5 esa
  sobrecarga es obsoleta: CS0618).
- Nada de cálculo estructural en C#: ni sumas de superposición, ni
  interpolación de Mn, ni repartos, ni sumas de reacciones (decisión 2).
- Materiales nuevos cacheados por color con `VisorEstructura.ShaderCompatible()`.

---

## 3. Servidor (b)

**Un solo servidor, puerto 5000**: `python semana05/servidor_s5.py [--lan] [--puerto 5000]`.
`servidor_s5.py` (P2) hace `from servidor_opensees import app` y le agrega
`/combinar` y `/estados`; `/ping` y `/analizar` siguen siendo los de
`comun/servidor_opensees.py` (P3). Todas las respuestas son JSON, también los
errores: `{"ok": false, "error": "..."}` con HTTP 400 (pedido inválido) o 500
(excepción). Unity lee el cuerpo también en `ProtocolError`. Se recomienda
`Access-Control-Allow-Origin: *` para el build Web. Los errores que arma Flask
sin pasar por una ruta (404 ruta inexistente, 405 método equivocado, p. ej.
`GET /combinar`) también salen como `{"ok": false, "error": "405 Method Not
Allowed: ..."}` (`servidor_opensees._error_http_en_json`, agregado al cierre).

### `POST /analizar` (P3)

Pedido: el modelo (`JsonUtility.ToJson(ModeloEstructural)`), como hoy.
Respuesta: la de hoy **más**:

| clave | dónde | tipo | qué es |
| --- | --- | --- | --- |
| `equilibrio` | en cada elemento de `casos` (forma multi-caso) | objeto | `calcular.equilibrio(data, caso, r)` tal cual: `aplicada_kN` [3], `reaccion_kN` [3], `error_kN` [3], `cargas_sin_convertir` int, `nodos_en_diafragma` int, `confiable` bool. Import de `calcular` dentro de la función (ciclo de imports) |
| `excel` | raíz | string o `null` | ruta **absoluta** del libro escrito con `excel.escribir_libro_reanalisis(data, respuesta, rutas.excel_reanalisis(ed))` |
| `excel_error` | raíz | string o `null` | por qué no hay Excel; escribir el libro dentro de `try/except BaseException`: un fallo del Excel **no** rompe `/analizar` |

`ed` para el nombre del libro: `data["info"]["edificio"]` si viene no vacío;
si no, el parámetro `?edificio=`; si no, `"modelo"`. La forma plana (un caso sin
`casos_de_carga`) no cambia. C#: `RespuestaServidor.excel`, `.excel_error`,
`CasoResultado.equilibrio` (§2.1).

### `POST /combinar` (P2)

Pedido (`PeticionCombinar`, U3):

```json
{"edificio": "lt2", "G": 1.2, "Q": 1.0, "EX": -1.4, "EY": 0.0}
```

Respuesta (`RespuestaCombinar`, U3):

```json
{"ok": true, "error": "", "edificio": "lt2",
 "parametros": ["q_Q = 3.0000 kN/m2 ...", "..."],
 "caso": { CasoS4 },
 "equilibrio": { EquilibrioCaso }}
```

| clave | tipo | regla |
| --- | --- | --- |
| `ok`, `error` | bool, string | `error` vacío si `ok` |
| `edificio` | string | el pedido. U3 no registra el caso si no es `Anexo.info.edificio` |
| `parametros` | string[] | las líneas de `parametros.describir(p)` con que se armó la base, **iguales** a `semana04.json → info.parametros` si son los mismos parámetros. U3 avisa si difieren (p. ej. anexo exportado con `--cs 0.20`) |
| `equilibrio` | `EquilibrioCaso` (§2.1) | *(agregada por P2)* `calcular.equilibrio` de la combinación, con la misma regla por GDL. U3 la declara en `RespuestaCombinar.equilibrio` y el panel la muestra tal cual (C# no suma reacciones) |
| `caso` | `CasoS4` | **completo**, con la forma del anexo: `nombre = "LIBRE"`, `tipo = "superposicion"`, `descripcion` (p. ej. `1.20 G + 1.00 Q - 1.40 EX`), `factores = [G, Q, EX, EY]`, `max_desplazamiento_mm`, `desplazamientos` (todos los nodos), `esfuerzos` (todas las barras, con estaciones), `demandas` (las barras con fierro; `u = 9999` fuera de la curva) |

Cualquier λ finito es válido (los rangos son de los sliders); uno tan grande que
la combinación desborda (p. ej. `1e300`) responde 400. Unity:
`RegistrarCasoExterno(resp.caso)` y `ElegirCaso("LIBRE")`. Timeout de Unity
≥ 30 s (la primera petición arma la base).

### `GET /estados` (P2)

```json
{"ok": true, "error": "",
 "estados": [{"nombre": "E1", "descripcion": "1.0G + 1.0Q", "lambdas": {"G": 1.0, "Q": 1.0, "EX": 0.0, "EY": 0.0}}],
 "rangos": {"G": {"min": 0.0, "max": 1.6, "paso": 0.05}, "Q": {...}, "EX": {"min": -1.4, "max": 1.4, "paso": 0.05}, "EY": {...}}}
```

Estados de la decisión 3: E1 = 1.0G+1.0Q, E2 = 1.2G+1.6Q, E3 = 1.2G+1.0Q−1.4EX
(los valores los fija P2 en `semana05/estados_s5.json`). Los objetos de
`estados` son `EstadoS5` sin `caso` (en `/estados` no viaja).

---

## 4. `comun/excel.py` (c) — lo implementa P1

W1 dejó el archivo con estas dos firmas y `NotImplementedError`. P1 lo
reemplaza entero **sin cambiar las firmas ni lo que devuelven**.

```python
def escribir_libro_anexo(ed, ruta, argv=None) -> str
def escribir_libro_reanalisis(modelo: dict, respuesta: dict, ruta) -> str
```

Las dos devuelven la **ruta absoluta** del `.xlsx` escrito, crean la carpeta
si falta, escriben de forma atómica y dan un `PermissionError` con mensaje
claro si el archivo está abierto en Excel. En Excel no se calcula nada.

**`escribir_libro_anexo(ed, ruta, argv=None)`**

| parámetro | forma |
| --- | --- |
| `ed` | `"lt2"`, `"ingenieria"` o `"conjunto"` (otro: `ValueError`) |
| `ruta` | destino; el CLI `semana05/exportar_excel.py <ed>` pasa `rutas.excel_resultados(ed)` = `data/excel/<ed>_resultados.xlsx` |
| `argv` | `None` o lista de flags de `semana03/parametros.py` (`["--cs", "0.20"]`) |

Fuente: `construir_anexo(ed, argv)` de `semana04/exportar_unity.py` cargado
**por ruta** (`semana04/trazabilidad.exportador()`), devuelve
`(anexo, contexto)` con `anexo = {info, casos[CasoS4], elementos[ElementoS4], familias[FamiliaPM]}`
(ver `semana04/CONTRATO.md` §2) y `contexto = {modelo, p, arm, datos, resultados, combinaciones, cargas, secciones, curvas, cierre}`;
equilibrio con `calcular.equilibrio` por caso y combinación. Nunca lee
`data/unity/semana04.json`.

**`escribir_libro_reanalisis(modelo, respuesta, ruta)`**

| parámetro | forma |
| --- | --- |
| `modelo` | el dict que Unity manda a `/analizar`: `info`, `material`, `secciones[{nombre, A, Iy, Iz, J, b, h, largo, espesor, E, G}]`, `nodos[{id, x, y, z, fijo, auxiliar, restricciones[6], ux, uy, uz}]`, `elementos[{id, n1, n2, seccion, tipo, vecxz, localX, localY, localZ, largo, espesor, dir_largo, area_tributaria, w_gravedad}]`, `diafragmas[{nodo_maestro, nodos, perpendicular}]`, `brazos_rigidos`, `casos_de_carga[{nombre, descripcion, cargas_nodales[{nodo, fx, fy, fz, mx, my, mz}], cargas_distribuidas[{elemento, wx, wy, wz}]}]`, `areas_tributarias` |
| `respuesta` | lo que devuelve `construir_y_resolver(modelo)` **con** `equilibrio` (P3). Multi-caso: `{ok, error, avisos[str], casos[{nombre, ok, max_desplazamiento, desplazamientos[{id, ux, uy, uz, rx, ry, rz}], reacciones[{id, fx, fy, fz, mx, my, mz}], fuerzas_elementos[{id, f[12]}], equilibrio{...}}]}`. Plana (un caso): `desplazamientos`, `reacciones`, `fuerzas_elementos`, `max_desplazamiento` en la raíz, sin `equilibrio`. Acepta las dos; si falta `equilibrio`, lo calcula con `calcular.equilibrio(modelo, caso, res)` |
| `ruta` | el servidor pasa `rutas.excel_reanalisis(ed)` = `results/excel/reanalisis_<ed>.xlsx` (ignorado por git) |

`JsonUtility.ToJson` escribe **todos** los campos C#, vengan o no en el JSON
original. En el `modelo` que manda Unity, un 0 o un vacío puede ser "no vino":
en el LT2 `elementos[].area_tributaria` y `w_gravedad` llegan en `0` (el área
está en `areas_tributarias`), `info.edificio` en `""`, `info.cota_terreno` en
`-9999`, y `secciones[].E`/`G` en `0` = usa el material del modelo (el
servidor ya los trata así: `servidor_opensees.normalizar_secciones`). El libro
no los escribe como dato (nada de "área tributaria 0 m²").

Unidades de la respuesta: m y rad (desplazamientos), kN y kN·m. `f` es
`localForce`: fuerzas **sobre** la barra en i y j; los esfuerzos internos con
tracción positiva son `-f_i` y `+f_j`. `max_desplazamiento` del servidor es la
mayor **componente**; `max_desplazamiento_mm` del anexo es la **norma**: el libro
dice cuál usa. Reacciones: columnas "cuenta en Fx/Fy/Fz" con la regla de
`calcular.equilibrio`; nunca un total de la columna entera.

Hojas mínimas (decisión 6): LEEME, Resumen, Nodos y Desplazamientos (mm),
Elementos, Esfuerzos (i/j), Reacciones, Demanda-capacidad (solo el del anexo),
Supuestos.

---

## 5. JSON de carga móvil (d) — lo implementa P4

`data/unity/carga_movil_lt2.json` → copia en `StreamingAssets/carga_movil.json`.
Reglas de `JsonUtility`: sin arreglos dentro de arreglos, sin diccionarios, un
campo C# por clave. Clases C# en `VisorCargaMovil.cs` con sufijo `Movil`.

**Nivel superior** (`AnexoCargaMovil`)

| clave | tipo C# | qué es |
| --- | --- | --- |
| `info` | `InfoMovil` | al menos `edificio` (`"lt2"`, se compara con `Anexo.info.edificio`), `descripcion`, `unidades`, `generado_por` (`"semana05/carga_movil.py"`); P4 agrega lo que necesite (escala gráfica fija, convención) |
| `P_kN` | float | la carga, positiva hacia abajo |
| `recorrido` | `RecorridoMovil` | objeto; P4 define su forma (p. ej. `elementos` int[], `nodos` int[], `largo_m`) |
| `posiciones` | `List<PosicionMovil>` | en orden a lo largo del recorrido |

**Cada posición** (`PosicionMovil`)

| clave | tipo C# | qué es |
| --- | --- | --- |
| `indice` | int | su lugar en `posiciones` (0..n−1) |
| `elemento` | int | la viga cargada |
| `xL` | float | abscisa relativa desde `n1`, 0..1 |
| `s_m` | float | distancia desde el inicio del recorrido, m |
| `x`, `y`, `z` | float | punto de aplicación, coordenadas OpenSees, m |
| `max_desplazamiento_mm` | float | máximo de la norma en esa posición |
| `desplazamientos` | `List<DespNodo>` | **todos** los nodos, m y rad: se pasa tal cual a `VisorEstructura.AplicarDeformada` (§2.3) |
| `reacciones` | `List<ReacNodo>` | los nodos restringidos, kN y kN·m. Unity no las suma |
| `equilibrio` | `EquilibrioCaso` | las claves de `calcular.equilibrio`, con la carga puntual **incluida** en `aplicada_kN` (`calcular.equilibrio` solo suma nodales y repartidas: P4 la agrega explícitamente) |
| `reparto` | `RepartoMovil` | objeto; P4 define (p. ej. `nodo_i`, `nodo_j`, `V_i_kN`, `V_j_kN`) |
| `conservacion` | `ConservacionMovil` | objeto; P4 define (p. ej. `suma_Rz_kN`, `error_kN`, `cota_kN`, `cumple`) |

Unity salta entre posiciones precalculadas: **no interpola** (decisión 2).

---

## 6. JSON de superposición precalculada (e) — lo implementa P2

`data/unity/superposicion_lt2.json` → copia en `StreamingAssets/superposicion.json`.
Para que E1..E3 funcionen sin servidor (exe).

```json
{"info": {"edificio": "lt2", "descripcion": "...", "generado_por": "semana05/superposicion.py",
          "parametros": ["...las mismas lineas que semana04.json info.parametros..."]},
 "estados": [{"nombre": "E1", "descripcion": "1.0G + 1.0Q",
              "lambdas": {"G": 1.0, "Q": 1.0, "EX": 0.0, "EY": 0.0},
              "caso": { CasoS4 }}]}
```

| clave | tipo C# (U3) | regla |
| --- | --- | --- |
| `info` | `InfoSuperposicionS5` | `edificio`, `descripcion`, `generado_por`, `parametros` string[] |
| `estados` | `List<EstadoS5>` | E1, E2, E3 en ese orden |
| `estados[].nombre`, `.descripcion` | string | |
| `estados[].lambdas` | `LambdasS5 {float G; float Q; float EX; float EY;}` | |
| `estados[].caso` | `CasoS4` | completo, como en `/combinar`, con `nombre` = el del estado (`"E1"`), `tipo = "superposicion"`, `factores = [G, Q, EX, EY]` |
| `estados[].equilibrio` | `EquilibrioCaso` | *(agregada por P2)* igual que en `/combinar`; U3 la declara en `EstadoS5.equilibrio` |

U3 lo lee con `LectorStreaming`, comprueba `info.edificio` e `info.parametros`
contra el anexo y registra cada `caso` con `RegistrarCasoExterno`.

---

## 7. StreamingAssets (f)

Nombres fijos en `unity/Assets/StreamingAssets/`:

| archivo | lo lee | origen en el repo |
| --- | --- | --- |
| `modelo_unity_edificio.json` | `VisorEstructura` (el nombre lo manda la escena) | `data/unity/<ed>.json` |
| `semana03.json` | `VisorSemana03` | `data/unity/semana03.json` (el último exportado) |
| `semana04.json` | `VisorSemana04` | `data/unity/semana04.json` (el último exportado) |
| `superposicion.json` | `VisorSemana04.Superposicion` (U3) | `data/unity/superposicion_<ed>.json` |
| `carga_movil.json` | `VisorCargaMovil` (P4) | `data/unity/carga_movil_<ed>.json` |
| `resultados.xlsx` | botón "Abrir Excel de resultados" (U2a) | `data/excel/<ed>_resultados.xlsx` |

(`modelo_unity.json` es el de antes; no se usa.)

**`python comun/lanzar_unity.py sincronizar <ed> [--seco] [--destino CARPETA]`**
(U6) solo copia, **nunca abre Unity**. `--seco` dice qué copiaría sin escribir;
`--destino` copia a otra carpeta (pruebas). Solo copia lo que tiene otro md5, y
de forma atómica:

| origen | destino | si falta el origen |
| --- | --- | --- |
| `data/unity/<ed>.json` | `StreamingAssets/<nombre_que_lee_el_visor()>` | error, sale con 1 |
| `data/unity/semana03.json`, `semana04.json` | mismo nombre | aviso; y aviso si su `info.edificio` no es `<ed>` (como `sincronizar_anexos`) |
| `data/unity/superposicion_<ed>.json` | `superposicion.json` | aviso; no borra el que haya |
| `data/unity/carga_movil_<ed>.json` | `carga_movil.json` | aviso; no borra |
| `data/excel/<ed>_resultados.xlsx` | `resultados.xlsx` | aviso; no borra |

Y lo mismo a `build/LaboratorioEstructural_Data/StreamingAssets/` si la build
existe. Cada lector comprueba el edificio del archivo, así que un archivo viejo
de otro edificio se ignora con aviso en vez de mostrarse mal.

---

## 8. Materiales y pestañas (g)

### Protocolo de materiales (decisión 8)

Prioridad visual: **mapa D/C > realista > técnica**.

1. Solo dos cambian `sharedMaterial` de los renderers de la estructura
   (`visor.ObjetosDeElementos` / `ObjetosDeNodos`): `AmbienteVisor` (U4) y el
   mapa D/C (U2b). El resaltado de selección no toca `sharedMaterial`: objeto
   superpuesto (como `VisorQA.Resaltar`) o `MaterialPropertyBlock`
   (`_BaseColor`/`_Color`). U5 cambia el resaltado de `EditorEstructura`, que
   hoy clona el material.
2. `VisorEstructura.Redibujar` crea objetos con el material técnico y avisa
   `AvisarRedibujado()`, que llama **primero** a los suscriptores de
   `Redibujado` y **después** avisa `MaterialesCambiados`.
3. `AmbienteVisor` en `Redibujado` (y en `ModeloCargado`) **registra** el
   material técnico de cada renderer (en ese momento siempre es el técnico),
   aplica realista o técnica según `AjustesVista.realista`, y termina con
   `EventosVisor.AvisarMaterialesCambiados()`. En `VistaCambio` aplica desde lo
   registrado (nunca lee el material actual, que puede ser del mapa) y
   termina igual.
4. El mapa D/C **no** escucha `Redibujado`. Al activarse y en cada
   `MaterialesCambiados`: guarda como base el `sharedMaterial` actual de cada
   renderer **salvo que sea uno de sus propios materiales**, y pinta. Al
   apagarse restaura la base de los renderers que sigan vivos. Así es
   idempotente: recibir `MaterialesCambiados` dos veces no corrompe la base.
5. Materiales cacheados por color; nada de `renderer.material` (crea una copia
   por objeto).

### Pestañas (decisión 9)

- `VisorQA` (U2a) dibuja las pestañas **Vista | Capas | Caso | Elemento** y
  después una por cada `IPanelIncrustable` encontrado, en este orden:
  `"Modificar"` (`EditorEstructura`, U5), `"Carga movil"` (`VisorCargaMovil`,
  P4), y cualquier otro por título.
- Búsqueda: `FindObjectsByType<MonoBehaviour>()` y `is IPanelIncrustable`, en
  `Start` y otra vez cada vez que el usuario cambia de pestaña. A cada uno le
  pone `PanelPropio = false`. Los que se crean con
  `RuntimeInitializeOnLoadMethod(AfterSceneLoad)` ya existen en el `Start` de
  `VisorQA`.
- Un panel incrustable: `DibujarPanel()` solo con `GUILayout` (sin `BeginArea`,
  sin `ScrollView`, sin `GUI.Window`), usa `PanelUI`, difiere a `Update` lo que
  redibuja la escena. Con `PanelPropio == false` su `OnGUI` no dibuja nada y su
  `MouseSobrePanel` devuelve `false`. Con `PanelPropio == true` (sin `VisorQA`
  en la escena) dibuja su propio panel como antes.
- Si no hay panel para una pestaña esperada, `VisorQA` muestra un texto que lo
  dice, no una pestaña vacía.

---

## 9. Lo que W1 dejó comprobado

Salidas de los scripts, en la rama `semana05` al terminar W1:

| comando | resultado |
| --- | --- |
| `.venv\Scripts\python.exe semana05\compilar_unity.py` | `Assembly-CSharp` 0 errores, 3 avisos (CS0618, preexistentes en `VisorQA.cs:124` y `VisorSemana03.cs:266, 453`); `Assembly-CSharp-Editor` 0 errores, 0 avisos |
| un `.cs` temporal que usa toda la API de §2 como la usarían U2a, U2b, U3, U4, U5 y P4 (implementando los tres hooks) | compila con 0 errores; borrado después |
| `.venv\Scripts\python.exe comun\test_contrato_unity.py lt2` | sano; `[--]` el LT2 no trae `area_tributaria` por elemento (a lo sumo 1 entrada por viga) |
| `... test_contrato_unity.py ingenieria` | sano; suma de entradas = `area_tributaria` en 301 vigas (161 con más de una entrada), peor error/cota 0.999999 (viga 128: 8.3971 contra 8.3972); `[PEND]` 462 de 462 entradas sin `qG`, `w`, `luz` |
| `... test_contrato_unity.py conjunto` | sano; 544 vigas, peor error/cota 0.999999 (viga 100128); `[PEND]` 462 de 705 entradas sin `qG`, `w`, `luz` |
| `.venv\Scripts\python.exe semana04\exportar_unity.py lt2` | 9 casos, 378 elementos, 26 curvas P-M para 69 elementos con fierro; todos los casos cierran (peor 0.959) |
| `.venv\Scripts\python.exe semana03\exportar_unity.py lt2` | escrito `data/unity/semana03.json` y su copia |
| `lanzar_unity.elegir_edificio('lt2'); lanzar_unity.sincronizar_json()` | modelo copiado a `StreamingAssets/modelo_unity_edificio.json` (y a la build) |
| `.venv\Scripts\python.exe semana04\test_contrato_semana04.py` | contrato de Semana 4 sano |
| md5 | `StreamingAssets/modelo_unity_edificio.json` = `data/unity/lt2.json` = `9b449599d415abb56e30972ed40dff0b`; `StreamingAssets/semana04.json` con `info.edificio = "lt2"` |

Demandas del anexo LT2 por caso (NO PASA / fuera de curva, de 69): EX 2/1,
S3 2/0, 1.2G+1.0Q+1.4EX 4/1; el resto 0/0.

### 9.1 Revisión independiente de W1

| comprobación | resultado |
| --- | --- |
| `compilar_unity.py --verbose --conservar`: archivos que recibe `csc` | `Assembly-CSharp`: los 17 `.cs` de `Assets/Scripts` (más el de atributos); `Assembly-CSharp-Editor`: los 3 de `Assets/Editor`. Un `.cs` en `Assets/Scripts/Editor/` va al del editor |
| `--solo` con errores inyectados, sobre una COPIA de `Assets` (el repo no se tocó) | 25 escenarios con el código esperado: error propio 1, ajeno 0 con AVISO, archivo del editor con `Assembly-CSharp` roto 2, error que arrastra a otro archivo 0 con AVISO, ruta inexistente o fuera de `unity/Assets` 2, nombre suelto `PanelUI.cs` resuelto; sin `.csproj`, sin dotnet, timeout o `.csproj` de formato raro: 2 |
| 4 compilaciones `--solo` a la vez | las 4 con código 0 en 2.8–2.9 s; ningún archivo nuevo en el repo |
| un `.cs` que usa toda la API de §2 (incluido `FindObjectsByType<MonoBehaviour>()` y los tres hooks implementados) | 0 errores, sin CS0618 |
| `edificios/ingenieria/tests/test_contrato_unity.py` (round-trip con el servidor) | pasa; `UZ(G) = -0.06348 mm` |

Cambios de la revisión: `--solo` ya no aprueba por vacío una ruta mal escrita;
`ElementoEnCotaVisible` usa la cota **menor** (§2.1); `LectorStreaming.UrlDe`
deja pasar una URL; timeout o `.csproj` raro salen con 2 y no con 1.

---

## 10. Lo que agregaron los paquetes (cierre de la fase paralela)

Todo lo de §2 sigue existiendo; esto se **agregó**. Los nombres están
comprobados con grep sobre los `.cs` al cierre (16-09) y el árbol compila con
`semana05/compilar_unity.py` (0 errores en los dos ensamblados).

| dueño | miembro | uso |
| --- | --- | --- |
| U1 `VisorEstructura` | `bool fantasmaFueraDelPiso`, `Color colorFantasma` | con un piso filtrado, lo de otros pisos se dibuja como fantasma gris bajo `FueraDelPiso`: sin collider y **fuera** de `ObjetosDeElementos`. Por eso `ObjetoDeElemento(id)` también da `null` para una barra de otro piso |
| U1 `VisorSemana03` | `string Aviso`, `bool AnexoCalzaConElModelo`, clase `InfoSemana03` | si `semana03.json` es de otro modelo no dibuja nada y lo dice en `Aviso` (`VisorQA` lo muestra en la cabecera) |
| U1 `CamaraOrbital` | `float gradosPorPantallaTactil` | táctil; `PedirCentrar` con `tamano <= 0` no cambia el zoom |
| U2a `VisorQA` | `Rect RectPanel()`, `void ElegirPestana(string)`, `PESTANA_ELEMENTO`, `void SeleccionarNodo(int)`, `void ElegirPiso(int)` (−1 = todos), `Color colorSeleccion` (propiedad) | `RectPanel` lo usa la ventana P-M para abrirse a la derecha del panel: no renombrar |
| U2b `VisorSemana04` (mapa) | `void MostrarMapaDC(bool)`, `bool MapaDCActivo`, `int MapaDCPintadas`, `string CasoConMasNoPasa()` | plegables `s4.casos`, `s4.diagramas`, `s4.pm`, `mapa.dc`, `mapa.criticos` |
| U3 `VisorSemana04` (superposición) | `CombinarEnPython(G, Q, EX, EY)`, `CASO_LIBRE`, `TIPO_SUPERPOSICION`, `EstadosSuperposicion`, `SuperposicionLeida`, `ServidorS5Conectado`, `CombinandoEnPython`, `MensajeCombinar`, `AvisoSuperposicion`, `EsPrecalculado(nombre)`, `OrigenDe(caso)`, `AnexoDesactualizado`, `MotivoDesactualizado` | `AnexoDesactualizado` queda en `true` tras `ModeloEditado` hasta recargar la escena |
| U5 `EditorEstructura` | `void BorrarElementoPorId(int)`, `int NodoSeleccionado`, `int ElementoSeleccionado`, `bool ArrastrandoNodo`, `Color colorResaltado` | `VisorQA.LeerClick` sale si `ArrastrandoNodo`. Con `PanelPropio == false` el editor no dibuja su propio resaltado (lo hace `VisorQA`) |
| U5 `AnalizadorEstructural` | `void Analizar(Action<bool> fin)` (llama `fin` una sola vez), `ResultadoDe(string)`, `CasoMostrado`, `Estado`, `UltimoError`, `EstadoPing`, `Avisos`, `ExcelReanalisis`, `ExcelError`, `Desactualizado`, `HayResultados`, `SegundosUltimoAnalisis`, `ProbarServidor()`, `UrlPing()`, `URL_POR_DEFECTO`, `TieneEquilibrio(c)`, `TablaEquilibrio(c)`, `NotaEquilibrio(c)`, `DescribirEquilibrio(c)` | M1 automatizada: `editor.BorrarElementoPorId(69); analizador.Analizar(ok => ...)`, esperando `Ocupado == false` antes; mirar `Desactualizado` en `fin` |
| P4 `VisorCargaMovil` | `Activar()`, `Apagar()`, `ElegirPosicion(int)`, `Activo`, `Indice`, `CantidadPosiciones`, `Anexo`, `Aviso` | llamar fuera de `OnGUI` |
| U6 `ConstruirApp` | `ConstruirWeb()` (compresión `Disabled`, `build/web`), `ConstruirAndroid()` (avisa y sale con 1 si falta el módulo) | toda build pasa por `Compilar()`, que fija `PlayerSettings.insecureHttpOption = AlwaysAllowed` (HTTP a `localhost` y a la IP del PC; agregado al cierre, sin probar en un exe) |
| U6 `lanzar_unity.py` | modos `web` y `android`, `sincronizar <ed> [--seco] [--destino]` | §7 |

JSON de carga móvil (§5): además de las claves mínimas, `PosicionMovil` trae
`a_m`, `L_m`, `Px/Py/Pz_local_kN`, `nodo_max_desplazamiento`, `uz_min_mm`,
`nodo_uz_min`, `u_carga_m`, `uz_bajo_carga_mm`, `M_bajo_carga_kNm` y `elastica`
(`List<PuntoElasticaMovil>`); `recorrido` = `{elementos, nodos, largos_m,
largo_m, z, eje, coord, divisiones, descripcion, _por_que}`; `info` trae
`escala_deformada` y `verificaciones` (`List<VerificacionMovil>`); arriba va
`_P_kN_por_que`. Las clases están en `VisorCargaMovil.cs` y
`semana05/carga_movil.py` [j] las compara con el JSON.
