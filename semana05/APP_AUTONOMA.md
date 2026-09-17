# App autónoma "como un videojuego": qué haría falta

> Semana 5, paquete **D0**. **Solo evaluación: no se construye nada.**
> Escrito el 16-09-2026 para Pedro (revisado a las 14:45 y, por un revisor
> independiente, cerca de las 15:00: el motor de la Semana 5 también
> necesita openpyxl, §4).
>
> - **Citas `archivo:línea`**: son del commit `f357eb6` (la base de la rama
>   `semana05`), porque en la Semana 5 hay varios agentes editando esos mismos
>   archivos y los números de línea se mueven. Se comprueban con
>   `git show f357eb6:<archivo> | grep -n "<texto>"`.
> - Si una cita dice **"(rama semana05)"**, es del árbol de trabajo del 16-09
>   a las 14:45, a medio integrar: esas líneas se van a mover y ese código
>   **todavía no está compilado ni probado en Unity**. Por eso van con el
>   nombre de la función o del texto, para encontrarlas con `grep`.
> - **Números medidos**: salen de comandos que corrí hoy y van con su comando
>   en el §4.
> - **Horas**: son **estimaciones**, no mediciones. Casi todas vienen de la
>   auditoría del 16-09 y las revisé contra lo que medí.

---

## 0. En corto

- **Hoy** ya existe un `.exe` de Windows que abre el visor sin el editor de
  Unity. Para **recalcular**, eso sí, hay que tener Python con OpenSees
  corriendo aparte en otra consola, y el edificio se elige copiando archivos
  **antes** de abrir la app.
- En un videojuego, el motor viaja **dentro** del juego. Aquí el "motor" es
  Python + OpenSees. Para que la app sea autónoma hay que **empaquetar ese
  motor** y hacer que la app lo prenda y lo apague sola. La regla de oro no
  cambia: Python sigue calculando y Unity sigue mostrando (CLAUDE.md:27-30).
- **En Windows es viable.** Medí que el motor necesita flask, openseespy y,
  desde la Semana 5 (el Excel de cada reanálisis), openpyxl: unos 24 MB.
  openpyxl carga además numpy y Pillow si están instalados, pero funciona
  sin ellos, así que hay que dejarlos fuera del paquete (son otros 70 MB).
  `opensees.pyd` no pide runtimes raros (§4).
- La Semana 5 ya adelanta piezas sueltas (URL del servidor editable en el
  panel, errores del reanálisis en pantalla, CORS, un comando que sincroniza
  los datos de un edificio; §2.1), pero **ninguna** hace que la app prenda
  el motor sola. Eso sigue faltando entero (F1).
- **Mínimo útil** ("doble clic, abre y reanaliza"): **14-23 h** (estimación).
  **App completa en Windows**: **37-59 h** (estimación), es decir 1 a 1.5
  semanas de una persona.
- **Móvil**: como visor de resultados precalculados, **sí**. Con reanálisis
  contra un servidor, **media**. Con OpenSees dentro del teléfono, **no**.
- **Recomendación**: no hacerla en la Semana 5. Si se hace, que sea por
  etapas, empezando por el mínimo útil (§7 y §8).

---

## 1. Qué significa "autónoma" aquí

Una persona con un PC Windows **sin Python ni Unity** tiene que poder hacer
esto:

1. Instalar (o descomprimir) y hacer doble clic.
2. Elegir el edificio dentro de la app.
3. Ver los resultados, modificar y **reanalizar**.
4. Ver los errores en pantalla, no en una consola.
5. Cerrar la app sin que quede nada corriendo.

```
HOY
  consola 1: python servidor_opensees.py  <--HTTP :5000-->  LaboratorioEstructural.exe
             (en la Semana 5: python semana05/servidor_s5.py, decisión 4)
  consola 2: python comun/lanzar_unity.py app lt2   (copia los JSON ANTES de abrir)

META
  Laboratorio.exe --lanza/cierra--> motor.exe (Python + OpenSees empaquetado)
        |                                  |
        +---- datos por edificio ----------+   (dentro del paquete)
```

---

## 2. Qué existe hoy (comprobado)

| pieza | evidencia | nota |
| --- | --- | --- |
| Build de Windows correcta | `build/unity_build.log:8` (`Date: 2026-09-16T00:00:38Z`, el 15-09 a las 21:00 hora local), `:8194` `Build Finished, Result: Success.`, `:8207` `BUILD OK ... (104 MB, 136 s)`, `:8241` `return code 0` | `build/` está ignorada por git (`.gitignore:50`): el log existe solo en este PC. En disco: `build/` ocupa 109 938 721 bytes, unos 110 MB (medido) |
| Script de build | `unity/Assets/Editor/ConstruirApp.cs:41-42` (menú y `Construir()`), `:59` `BuildTarget.StandaloneWindows64`, `:30` una sola escena, `:78` `Exit(1)` si falla | Solo compila Windows |
| Lanzador sin editor | `comun/lanzar_unity.py:332` `abrir_visor` (copia los JSON en `:347` y lanza el exe en `:362`), `:379` `abrir_servidor` (`Popen` del servidor en `:407`); `ver.ps1:45` exporta el LT2, `:55` levanta el servidor y `:69` abre la app | Necesita el `.venv` y una consola |
| Servidor de cálculo | `comun/servidor_opensees.py:42-48` (imports: flask, openseespy y la biblioteca estándar), `:612-615` `/ping`, `:618-632` `/analizar`, `:637-650` `--lan` (por defecto escucha en `127.0.0.1`) | `/ping` sirve para saber si el motor está vivo. En la rama semana05, `/analizar` además llama a `escribir_excel`, que importa `comun/excel.py` y openpyxl dentro de la función (§4) |
| Unity ya sabe pedir un reanálisis | `unity/Assets/Scripts/AnalizadorEstructural.cs:43` `urlServidor = "http://localhost:5000/analizar"`, `:44` timeout de 30 s, `:132-160` POST con `UnityWebRequest`; la escena fija la URL en `SampleScene.unity:216` | En `f357eb6` la URL está fija; en la rama semana05 se puede escribir en el panel (§2.1). En el editor funcionó: `reports/semana02.md:720` "El reanálisis desde Unity **ya funciona**" |
| Guardar el modelo editado | `EditorEstructura.cs:490` (`persistentDataPath`) | |
| Lectura compatible con móvil y Web *(rama semana05, W1)* | `unity/Assets/Scripts/LectorStreaming.cs:111` `Leer(...)` con `UnityWebRequest.Get` (`:114`) | Base para las variantes móviles |
| Panel escalado por DPI *(rama semana05, W1)* | `unity/Assets/Scripts/PanelUI.cs:126` `Escala()`, `:149` `UmbralArrastre()`, `:93` `EsMovil` | Base para las variantes móviles |

### 2.1 Lo que la rama semana05 ya adelanta (en curso, sin compilar ni probar)

Ninguna de estas piezas se hizo para la app autónoma, pero le sirven. A las
14:45 la rama todavía no compilaba entera: otros paquetes estaban a medio
editar.

| pieza | evidencia (rama semana05) | a qué parte de la app le sirve |
| --- | --- | --- |
| URL del servidor editable en el panel, con "Probar conexion" (`/ping`) | `AnalizadorEstructural.cs:77` `URL_POR_DEFECTO`, `:391` `ProbarServidor()`, `:398` `UrlPing()`; `EditorEstructura.cs:1142` (`GUILayout.TextField` de `urlServidor`), `:1145` botón "Probar conexion" | Componente 3 (el lanzador solo tendría que escribir la URL) y variante C |
| Errores del reanálisis en pantalla | `AnalizadorEstructural.cs:120` `UltimoError` (su comentario dice que antes solo iba a `Debug.LogError`); `EditorEstructura.cs:1164-1165` lo muestra en el panel | Componente 6, solo para el reanálisis |
| CORS en el servidor | `servidor_opensees.py:90` `PERMITIR_CORS` (activo salvo `OPENSEES_CORS=0`), `:688` `Access-Control-Allow-Origin` | Variante C con build Web |
| Un solo servidor con `/combinar` y `/estados` | `semana05/servidor_s5.py:142` y `:173` (decisión 4) | Es el servidor que habría que empaquetar (componente 1) |
| Excel del reanálisis | `servidor_opensees.py:731` `escribir_excel`, en `rutas.py:108` `EXCEL_REANALISIS` = `<raíz>/results/excel` | Componente 2; agrava F2 (escribe dentro de la raíz) |
| Sincronizar los datos de un edificio | `lanzar_unity.py:357` `sincronizar(...)` (copia solo lo que cambió y no pisa con un archivo de otro edificio) y `:287` `carpetas_streaming()`, que incluye la StreamingAssets de la build | Componente 4, pero sigue siendo **fuera** de la app |
| Lectores que rechazan datos de otro edificio | `VisorSemana04.Superposicion.cs:355` (compara `sup.info.edificio`), `VisorSemana03.cs:403-404` (en `Comprobar()`, compara `Anexo.info.edificio` con `m.info.edificio`) | Componente 4 |
| Métodos de build Web y Android | `ConstruirApp.cs:92-93` `ConstruirWeb()` con `:107` compresión `Disabled`; `:113-114` `ConstruirAndroid()`; `:163` `Soportado(...)` avisa si falta el módulo | Variantes B y C |

Lo que **no** cambió en la rama: nadie lanza procesos desde Unity (F1), la
raíz se sigue buscando igual (F2), `/analizar` sigue sin rehacer el anexo
(F3), hay una sola escena (F4) y no hay instalador (F6).
`ProjectSettings.asset` sigue con `insecureHttpOption` en 0 (F7), pero al
cierre de la fase paralela `ConstruirApp.Compilar()` (rama semana05) lo fija
en `AlwaysAllowed` antes de cada build; sin probar en un exe.

### 2.2 Coherencia de los datos de la app (medida con md5)

- A media mañana del 16-09, la auditoría encontró la app mezclada: el modelo
  era el del conjunto y los anexos eran de Ingeniería.
- W1 la resincronizó a las 12:46: `modelo_unity_edificio.json` de la app
  coincidía con `data/unity/lt2.json` (`9b449599...`, CONTRATO.md §9).
- Después alguien regeneró `data/unity/lt2.json` (le agregó
  `info.cota_terreno = -4.01`; la última escritura del archivo es de las
  14:44) y desde ahí ya no calzan.
- **Medido a las 14:45, y de nuevo cerca de las 14:50 en la revisión, con el mismo
  resultado:** `data/unity/lt2.json` da `1b3808cf...`, mientras
  que la copia del proyecto (`unity/Assets/StreamingAssets/`) y la de la
  build (`build/LaboratorioEstructural_Data/StreamingAssets/`) siguen en
  `9b449599...`, sin `cota_terreno`. La geometría es la misma (232 nodos y
  378 elementos en las tres). `semana03.json` y `semana04.json` coinciden en
  las tres carpetas y dicen `info.edificio = "lt2"`. La build todavía no
  tiene `superposicion.json`.

**Moraleja:** hoy la coherencia depende de copiar archivos en el momento
justo. El `sincronizar` de la rama (§2.1) lo hace con un comando, pero sigue
siendo un paso aparte, antes de abrir la app.

---

## 3. Qué falta, y por qué impide el "doble clic"

**F1. El cálculo vive fuera de la app.**
- Hace falta el `.venv` (372 128 215 bytes, unos 370 MB, medido) y una
  consola aparte.
- Unity no lanza procesos: `System.Diagnostics` y `Process.Start` aparecen 0
  veces en los `.cs` de `unity/Assets` (grep, rama semana05, 14:45).
- Tampoco hay nada que cierre el servidor al salir: `Application.quitting` y
  `OnApplicationQuit` aparecen 0 veces (el mismo grep).

**F2. `rutas.py` no encuentra la raíz si Python está empaquetado.**
- `comun/rutas.py:66` busca `.git` o `setup.ps1` subiendo por las carpetas
  (`:69-80`). Si no encuentra ninguna, cae a
  `dirname(dirname(__file__))` (`:79`).
- Un paquete instalado no trae `.git` ni `setup.ps1`.
- Además, en `C:\Program Files` no se puede escribir sin permisos de
  administrador. En la rama semana05 el servidor escribe el Excel del
  reanálisis en `<raíz>/results/excel/` (`rutas.py:108`, `EXCEL_REANALISIS`).
  Empaquetado, eso tendría que ir a la carpeta del usuario
  (`%LOCALAPPDATA%`). El modelo editado ya va ahí
  (`EditorEstructura.cs:490`, `persistentDataPath`).

**F3. `/analizar` no rehace "todo".**
- Devuelve solo desplazamientos, reacciones y fuerzas
  (`servidor_opensees.py:591-605`). No rehace los diagramas, el P-M ni la
  demanda/capacidad del anexo de Semana 4. En la rama semana05 sigue igual:
  `construir_anexo` aparece 0 veces en `comun/servidor_opensees.py` y en
  `semana05/servidor_s5.py` (grep); lo nuevo es el Excel y el equilibrio.
- El anexo lo arma `construir_anexo` (`semana04/exportar_unity.py:588`). Esa
  función lee `data/modelo/<ed>.json` (medido, §4), **no** el modelo editado
  en Unity.
- Consecuencia: si el cambio es **por dato** (`--q`, `--cs`, combinación),
  basta con llamar a `construir_anexo` desde el motor. Si el cambio es
  **geométrico** y se hizo en Unity (borrar una columna), hay que traducir el
  modelo de Unity al contrato. Otra opción es marcar el anexo como
  desactualizado, que es lo que decide la Semana 5 (`CONTRATO.md:92`, evento
  `ModeloEditado`).

**F4. El edificio se elige fuera de la app.**
- `lanzar_unity.py:54` fija `EDIFICIO = 'lt2'`, `:106-111` `elegir_edificio`
  solo cambia qué archivo se copia encima, y `:216-225` explica que cada anexo
  es de un solo edificio.
- Si no calzan, el visor apaga los diagramas (`VisorSemana04.cs:403`, "El
  anexo es de otro modelo").
- En la rama semana05, `python comun/lanzar_unity.py sincronizar <ed>`
  (§2.1) copia todo lo del edificio de una vez, también a la build. Sigue
  siendo por consola y antes de abrir la app.
- Hay una sola escena (`unity/Assets/Scenes/` solo tiene `SampleScene.unity`).

**F5. Los errores no se ven (en parte resuelto en la rama).**
- En `f357eb6`, `AnalizadorEstructural.cs:153-160` avisa con
  `Debug.LogError`, y `EditorEstructura.cs:485` dice "Mira la Console".
- En el exe, eso termina en
  `%USERPROFILE%\AppData\LocalLow\UANDES\Laboratorio Estructural - Grupo 7\Player.log`.
  El archivo existe (medido; la última escritura es del 09-09), pero nadie lo
  abre. La carpeta sale de `companyName` y `productName`, en
  `ProjectSettings.asset:15-16`.
- En la rama semana05 el error del **reanálisis** ya sale en el panel
  (`UltimoError`, §2.1) y "Mira la Console" ya no aparece en
  `EditorEstructura.cs`. Siguen yendo solo a `Debug.LogError` otros avisos,
  como "No hay VisorEstructura en la escena"
  (`AnalizadorEstructural.cs:179`, rama semana05). Para la app autónoma
  faltarían los errores del **motor** (no arrancó, puerto ocupado, se cayó).

**F6. No hay instalador.**
- No existe ningún `.iss`, y Inno Setup no está instalado (medido).
  PyInstaller tampoco: `import PyInstaller` da `ModuleNotFoundError`.
- `build/` mezcla la app con logs y con dos carpetas `*_DoNotShip` de unos 210 kB
  cada una (medido). Una se llama `My project (1)_...` por `projectName`
  (`ProjectSettings.asset:938`).

**F7. HTTP a localhost desde el exe (no comprobado).**
- `ProjectSettings.asset:945` tiene `insecureHttpOption: 0`, es decir, "Not
  Allowed".
- La referencia de Unity (`InsecureHttpOption`) describe `NotAllowed` como
  "Do not allow UnityWebRequest to use plain text HTTP connections" y no
  menciona ninguna excepción para localhost. Hay además un caso público en el
  Issue Tracker de Unity titulado "WebRequest can't connect to localhost when
  HTTP is used for connection" (no pude leer su estado).
- A favor: en el **editor** el reanálisis contra `localhost` funcionó
  (`reports/semana02.md:720`, del 01-09), con este mismo ajuste en 0 desde el
  commit `4a24549` (28-08). No sé si el editor aplica la regla igual que el
  exe.
- En el exe no hay prueba: en `Player.log` no hay rastro de que haya llamado
  al servidor, solo `Modelo cargado: 558 nodos, 937 elementos, 4 casos.`
  (línea 38).
- Es lo **primero** que hay que probar en la etapa 1. Si falla, se pone
  `AlwaysAllowed` por código en `ConstruirApp`. **Ojo, también afecta a la
  Semana 5:** la M1 registrada desde el exe (decisión 11, `CapturaSemana05`)
  depende de esto.
- Actualización al cierre de la fase paralela (rama semana05): para no
  depender de la prueba, `ConstruirApp.Compilar()` ya fija
  `PlayerSettings.insecureHttpOption = InsecureHttpOption.AlwaysAllowed` en
  toda build (compila con `semana05/compilar_unity.py`). Sigue sin probarse
  en un exe; `ProjectSettings.asset` cambia a 2 recién en la primera build.

---

## 4. Lo que medí para esta evaluación

Todo con `.venv\Scripts\python.exe`, en memoria y sin escribir en el repo
(corridas del 16-09 entre las 14:35 y las 14:45; las filas de la Semana 5 y
las repeticiones son de la revisión, cerca de las 15:00). Los scripts quedaron
fuera del repo; abajo va lo que hace cada uno. Los tiempos son de este PC.

| qué | resultado | cómo |
| --- | --- | --- |
| Tiempo de importar `openseespy.opensees` / `flask` | 0.11 s / 0.20 s | `time.perf_counter()` alrededor de cada `import` |
| Tiempo de importar el servidor entero | 0.35 s (0.11 + 0.20 + 0.03 s del propio servidor) | `import` de una copia de `git show f357eb6:comun/servidor_opensees.py` |
| `/analizar` del LT2 (`construir_y_resolver` con `data/unity/lt2.json`: 232 nodos, 378 elementos, casos G, Q, EX y EY) | **0.05 s** por corrida (0.051-0.054 s en 3 corridas), respuesta de 0.29 MB | la misma copia, llamada directa sin HTTP |
| Anexo completo de Semana 4 (`construir_anexo`) | LT2: **2.0-2.2 s** (9 casos, 378 elementos, 26 familias P-M, 2.03 MB de JSON compacto). Conjunto: **4.1-4.3 s** (9 casos, 937 elementos, 54 familias, 5.07 MB) | `construir_anexo(ed, [])` cargado por ruta, 2 corridas por edificio, repetidas en la revisión (LT2 2.11-2.13 s, conjunto 4.11-4.24 s) |
| Archivos que lee ese pipeline | LT2: `data/modelo/lt2.json` (360.0 kB) y `semana03/parametros.json` (6.4 kB). Conjunto: `data/modelo/conjunto.json` (832.4 kB) y `parametros.json`. **Ningún** archivo del repo abierto para escribir | `sys.addaudithook` sobre el evento `open` |
| Módulos que carga | 10 del repo (`comun/`: calcular, capacidad, combinar, contrato, rutas, servidor_opensees, sismo; `semana03/`: demanda_capacidad, lab_semana03, parametros), más `semana04/exportar_unity.py`. De terceros: flask, werkzeug, jinja2 y sus dependencias (click, blinker, itsdangerous, markupsafe, colorama) y openseespy. **No** carga numpy, ezdxf ni matplotlib | `sys.modules` al terminar |
| Tamaño de esas dependencias | 22 047 772 bytes (unos 22 MB). A eso se suman `python312.dll` (6.9 MB), `vcruntime140*.dll` (0.17 MB) y la parte de la biblioteca estándar que se use (no medida; la carpeta `Lib` completa tiene 61 886 161 bytes, unos 62 MB) | `du -sbc` sobre `site-packages` y la instalación de Python 3.12.10 (`.venv/pyvenv.cfg`) |
| Servidor de la **Semana 5** (rama, `semana05/servidor_s5.py`, que es el que se empaquetaría) | Importarlo tarda 0.34 s y carga los mismos terceros que arriba. `/ping`, `/estados` y `/combinar` (LT2, 2.2 s la primera vez porque arma la base) tampoco cargan más. Pero el Excel que `/analizar` escribe después de resolver carga **openpyxl** y et_xmlfile y, porque openpyxl los importa si están (`openpyxl/compat/numbers.py:8-12`, `openpyxl/drawing/image.py:5-8`), también **numpy**, **Pillow** y defusedxml. Con esos tres bloqueados el libro se escribe igual (7 hojas, 262 kB, el mismo tamaño que con ellos) | revisión: `app.test_client()` sin levantar el puerto, `sys.modules` después de cada paso y un `MetaPathFinder` que bloquea numpy, PIL y defusedxml; escrituras en el repo bloqueadas con `sys.addaudithook` y el Excel escrito en una carpeta temporal |
| Costo del Excel en `/analizar` (rama) | LT2: resolver 0.052-0.055 s y escribir el Excel 0.79-0.90 s (3 corridas). O sea, el reanálisis del LT2 con el servidor de la Semana 5 tarda cerca de 0.9 s en vez de 0.05 s | `excel.escribir_libro_reanalisis` con el resultado de `construir_y_resolver`, salida en una carpeta temporal |
| Tamaño de lo que agrega la Semana 5 | openpyxl + et_xmlfile: 2 005 686 bytes (el motor queda en 24 053 458 bytes, unos 24 MB). Lo opcional, que conviene excluir: numpy 32 547 724 + `numpy.libs` 21 164 112 + PIL 16 029 101 + defusedxml 73 204 = 69 814 141 bytes (unos 70 MB) | `du -sb` sobre cada carpeta de `site-packages` |
| DLL que pide `opensees.pyd` (17 206 272 bytes, x64) | solo `python312.dll`, `KERNEL32.dll`, `imagehlp.dll` y `WSOCK32.dll`. No pide `VCRUNTIME` ni `MSVCP`, así que trae el runtime de C++ enlazado adentro. No tiene importaciones diferidas. Como texto dentro del binario aparecen además `ifcore_msg.dll`, `irc_msg.dll`, `libicaf.dll` y `libmui.dll` (runtime de Intel Fortran): no son importaciones, no están en este PC (ni en `System32` ni en el PATH) y los análisis corrieron igual, así que no hacen falta para el uso normal | lectura de las tablas de importaciones normales y diferidas del PE con un script propio (`dumpbin /dependents` da lo mismo si hay Visual Studio); búsqueda de textos `*.dll` en el binario |
| DLL que pide `python312.dll` | `VCRUNTIME140.dll` (viene en la carpeta de Python) y `api-ms-win-crt-*` (UCRT, parte de Windows 10/11) | el mismo script |
| Plataformas de OpenSeesPy 3.8.0.0 | `.venv/Lib/site-packages/openseespy/opensees/__init__.py:9-12` solo Linux x86_64, `:18-23` Windows AMD64, `:27-30` macOS arm64; cualquier otra: `:37` `is not supported`. `METADATA`: `Platform: Linux / Windows / Mac` | lectura del paquete instalado |
| Licencia de OpenSeesPy | `openseespywin/LICENSE.md`: gratis para investigación, educación y uso interno. La redistribución **comercial** (una app o un servicio en la nube) necesita licencia | lectura del paquete instalado |
| Módulos de Unity 6000.5.10f1 instalados | `PlaybackEngines/` solo tiene `WebGLSupport` y `windowsstandalonesupport` (sin Android) | `ls` |
| Backend de scripts en Windows | Mono: la build trae `MonoBleedingEdge/` (9.1 MB) y `ProjectSettings.asset:838-839` solo declara IL2CPP para Android. `apiCompatibilityLevel: 6` (`:930`) | `ls` y grep |

**Qué significa para la app:**
- El motor es **chico** (unos 24 MB de dependencias) y **no necesita numpy
  ni Pillow**. Pero openpyxl los carga si están, y PyInstaller también
  empaqueta los `import` que están dentro de un `try` (no probado aquí,
  porque PyInstaller no está instalado). Por eso hay que excluirlos a mano
  (`--exclude-module numpy --exclude-module PIL`), o el motor crece unos
  70 MB.
- En el `.venv` importa en 0.35 s. Empaquetado con PyInstaller va a tardar
  más en arrancar (no medido): por eso la app tiene que esperar `/ping`.
- Resolver el LT2 toma 0.05 s. Con el servidor de la Semana 5, que además
  escribe el Excel, el reanálisis tarda cerca de 0.9 s.
- Rehacer el anexo completo tarda entre 2.0 s (LT2) y 4.3 s (conjunto), así
  que la app tiene que mostrar "calculando...", no congelarse.

---

## 5. Componentes, horas, viabilidad y riesgo

Horas-persona **estimadas** (salen de la auditoría y las revisé con el §4).

| # | componente | qué es | horas (estim.) | viabilidad | riesgo |
| --- | --- | --- | --- | --- | --- |
| 1 | **Motor empaquetado** | PyInstaller en modo carpeta (*onedir*) con el servidor de la Semana 5 (`semana05/servidor_s5.py`, decisión 4) y el pipeline de Semana 4. `rutas.py` toma la raíz de una variable (`LAB_RAIZ`) o de `sys.frozen`, y las salidas (el Excel del reanálisis) van a `%LOCALAPPDATA%`. Excluye numpy y Pillow, que openpyxl no necesita (§4) | 6-10 | Alta (dependencias medidas: flask, openseespy y openpyxl, sin runtimes extra) | Medio: el antivirus puede marcar el ejecutable de PyInstaller; falta probar en un PC sin Python |
| 2 | **Recálculo completo** | Endpoint que recibe q, cs y combinación, corre `construir_anexo` y devuelve el anexo, la superposición y el Excel. Tarda 2.0-2.2 s en el LT2 y 4.1-4.3 s en el conjunto (medido) | 6-10 | Alta | Medio: con cambios geométricos hechos en Unity no alcanza (F3). Un anexo de Semana 4 a partir del modelo editado sería otro trabajo (la auditoría lo estimó en unas 9 h) |
| 3 | **Unity lanza y cierra el motor** | `Process.Start` del motor con un puerto libre, esperar `/ping`, escribir la URL con ese puerto en `AnalizadorEstructural.urlServidor` (en `f357eb6` la fija la escena; en la rama semana05 ya es editable, §2.1) y cerrarlo al salir. El motor se apaga solo si muere su proceso padre. Incluye probar F7 | 5-8 | Alta en Windows (Mono) | Medio: procesos huérfanos si la app se cae, puerto ocupado, HTTP bloqueado (F7) |
| 4 | **Datos por edificio y recarga** | Una carpeta por edificio con modelo, `semana03`, `semana04`, superposición, carga móvil y `resultados.xlsx`. Cada lector comprueba `info.edificio` (CONTRATO.md §7) y recarga sin reiniciar | 4-6 | Alta | Medio: los tríos incoherentes ya pasaron hoy (§2.2). El JSON del modelo todavía no trae `info.edificio` (CONTRATO.md §2.1) |
| 5 | **Menú de edificio** | Pantalla de inicio con LT2 / Ingeniería / Conjunto | 5-8 | Alta | Bajo; toca la escena y `VisorEstructura` |
| 6 | **Errores y progreso en pantalla** | Cambiar `Debug.LogError` por avisos en el panel (`PanelUI` ya tiene estilo `Aviso`, rama semana05), con "calculando..." y la opción de reintentar. Suma los errores del motor (no arrancó, puerto ocupado, se cayó) | 4-6 | Alta | Bajo. El error del reanálisis ya sale en el panel en la rama semana05 (F5), así que probablemente cueste menos; no lo descuento porque ese código aún no está probado |
| 7 | **Instalador** | Inno Setup con la app, el motor y los datos, acceso directo y desinstalador. Instala en la carpeta del usuario para no pedir administrador | 3-5 | Alta | Medio: SmartScreen advierte de ejecutables sin firma |
| 8 | **QA y documentación** | Prueba en un PC sin Python, `verificar_todo.py`, contrato JSON-C#, prueba manual completa y guía de uso | 4-6 | Alta | Bajo |
| | **Total Windows** | | **37-59** | **Media-alta** | |
| | **Mínimo útil** = 1 + 3 + 7 | | **14-23** | | |

Tamaño del instalador sin comprimir: **unos 150-210 MB** si se excluyen
numpy y Pillow, y **hasta unos 280 MB** si no. Es una estimación hecha con
piezas medidas:
- la build de Unity: unos 110 MB;
- el motor: entre unos 31 MB (24 MB de dependencias con openpyxl, 7 MB de
  `python312.dll` y `vcruntime140*.dll`, y una parte chica de la biblioteca
  estándar) y unos 93 MB (con los 62 MB de la biblioteca estándar completa);
  numpy, `numpy.libs`, Pillow y defusedxml suman otros 70 MB si PyInstaller
  los arrastra;
- los datos: `data/modelo` pesa 1.6 MB, y el anexo del conjunto 5.07 MB en
  JSON compacto.

La auditoría había estimado 200-300 MB suponiendo que había que llevar
numpy. No hace falta llevarlo, pero entra solo si no se excluye.

---

## 6. Variantes

| variante | qué puede hacer el usuario | qué hay que hacer | horas (estim.) | viabilidad | riesgo principal |
| --- | --- | --- | --- | --- | --- |
| **A. Windows con motor Python empaquetado** | Todo: ver, modificar, reanalizar y abrir el Excel, sin consola | Tabla del §5 | 37-59 (mínimo 14-23) | **Media-alta** | Tiempo de una persona; antivirus y SmartScreen; F7 sin probar |
| **B. Móvil, visor precalculado** (APK o Web) | Ver modelo, casos, combinaciones, E1..E3, P-M y carga móvil **precalculados**. No modifica ni mueve los λ libres | Lo móvil de la Semana 5 (`LectorStreaming`, táctil, escala; build Web o Android) más el menú de edificio del §5 | 6-12 **además** de lo de la Semana 5 (auditoría) | **Alta** | Android: el módulo no está instalado (medido) y Pedro decidió no instalarlo ahora. La auditoría midió con `--dry-run` una descarga de unos 2.4 GB y unos 8.3 GB en disco (no lo repetí). iOS queda descartado porque no hay Mac. Web: Brotli no carga por HTTP (`ProjectSettings.asset:818` y `:822`); el `ConstruirWeb()` de la rama semana05 ya compila sin compresión (§2.1), sin probar |
| **C. Móvil con servidor** (el PC en la red local o la nube) | Lo de B, más reanálisis y λ libres | URL editable (en `f357eb6` fija en `SampleScene.unity:216`; editable en el panel en la rama semana05, §2.1); HTTP permitido (`ProjectSettings.asset:945`, sigue en 0; en la rama semana05 `ConstruirApp` lo fija al compilar) o HTTPS; CORS para Web (lo pide CONTRATO.md §3 y ya está en la rama semana05, §2.1); `--lan` (`servidor_opensees.py:637-650`); hosting con HTTPS si es en la nube | 8-16 más hosting (auditoría) | **Media** | La red de la universidad puede aislar los equipos. Seguridad: `--lan` abre el servidor a toda la red (`servidor_opensees.py:646-649`). Un anexo pesa 2-5 MB por respuesta. En la nube entra la cláusula de licencia de OpenSeesPy si el uso deja de ser educativo |
| **D. OpenSees dentro del teléfono** | Todo, sin red | Compilar OpenSees para Android con el NDK y embeber Python. OpenSeesPy 3.8 no lo soporta (`openseespy/opensees/__init__.py:9-12` exige x86_64 en Linux, y los teléfonos son ARM64). Reescribirlo en C# rompería la regla de oro (CLAUDE.md:30) | 60-120 (auditoría) | **Baja** | Alto; no lo recomiendo |

---

## 7. Recomendación por etapas

**Etapa 0: Semana 5 (en curso, sin costo extra).**
- No se construye la app.
- Lo que la Semana 5 ya está haciendo deja la base:
  - `LectorStreaming` y `PanelUI` (W1);
  - la superposición E1..E3 precalculada, que funciona sin servidor
    (decisión 3);
  - un solo servidor en el puerto 5000 (decisión 4);
  - el Excel (decisión 6);
  - la URL del servidor editable, el error del reanálisis en el panel, CORS,
    `sincronizar` y los métodos de build Web y Android (§2.1).
- Lo único que conviene hacer ya, porque también le sirve a la Semana 5:
  probar F7 (HTTP a `localhost` desde el exe) cuando se registre la M1
  desde el exe.

**Etapa 1: mínimo útil en Windows (14-23 h, estimación).** Componentes 1, 3 y 7; ver el
§8.

**Etapa 2: recálculo completo (6-10 h, estimación).** Componente 2.
- Se da por hecha cuando `--cs 0.20` desde la app da el mismo anexo que el
  CLI (la M2 de la Semana 5).

**Etapa 3: edificio y errores (13-20 h, estimación).** Componentes 4, 5 y 6.
- Se da por hecha cuando se cambia de edificio sin cerrar la app, sin
  diagramas apagados por un anexo ajeno, y cuando un error del motor se ve en
  pantalla.

**Etapa 4: QA y documentación (4-6 h, estimación).** Componente 8.

**Móvil (opcional, al final).**
- Primero la variante B (visor precalculado, 6-12 h estimadas).
- La C solo si hace falta reanalizar desde el teléfono.
- La D, nunca.

Suma de las etapas 1 a 4: 14-23 + 6-10 + 13-20 + 4-6 = **37-59 h**
(estimación).

---

## 8. El mínimo útil: "doble clic, abre y reanaliza"

**Qué incluye**
1. `motor/` hecho con PyInstaller *onedir*, con el servidor de la Semana 5
   (`/ping`, `/analizar`, `/combinar`, `/estados`), `rutas.py` con raíz
   configurable, salidas en la carpeta del usuario y sin numpy ni Pillow
   (§4).
2. Un script C# nuevo (por ejemplo `LanzadorMotor.cs`) que:
   - busca un puerto libre y lanza `motor.exe --puerto N`;
   - espera `/ping` con un límite de tiempo y muestra un aviso si no llega;
   - escribe la URL con ese puerto en `AnalizadorEstructural.urlServidor`
     (el campo que la rama semana05 ya deja editar);
   - cierra el motor al salir.
3. Antes que nada, probar F7 (HTTP a `127.0.0.1` desde el exe).
4. Un instalador de Inno Setup con la app, el motor y los datos del LT2.

**Qué hace el usuario**
1. Instala, abre, borra la columna 69 del LT2 y pulsa "Reanalizar".
2. Ve el mismo UZ del nodo 186 que da Python (la M1 de la Semana 5).
3. Cierra la app. En el Administrador de tareas no debe quedar ningún
   `motor.exe`.

**Qué NO hace todavía**
- No cambia de edificio dentro de la app (solo LT2).
- No rehace el anexo de Semana 4 (lo marca como desactualizado).
- Los errores se ven, pero de forma básica.

**Cómo se da por hecho**
- Se prueba en un PC (o en un usuario de Windows nuevo) **sin Python**.
- Se anota el tamaño del instalador y el tiempo de arranque hasta `/ping`
  (medido en ese PC).

---

## 9. Riesgos

| riesgo | qué pasa | mitigación | evidencia |
| --- | --- | --- | --- |
| HTTP bloqueado en el exe | La app no llega al motor; y en la Semana 5, la M1 desde el exe falla | Probarlo primero (etapa 1); `AlwaysAllowed` desde `ConstruirApp` ya está en la rama semana05 (sin probar en un exe) | `ProjectSettings.asset:945`; F7 |
| Dependencias que se cuelan en el motor | openpyxl (el Excel de `/analizar` en la Semana 5) carga numpy y Pillow si están: el motor pasa de unos 24 MB a unos 94 MB de dependencias | `--exclude-module numpy --exclude-module PIL` en el build del motor, y comprobar que el Excel se sigue escribiendo | §4, filas de la Semana 5 |
| Antivirus o SmartScreen | Marca `motor.exe` o la app sin firma | Carpeta de usuario, onedir (no onefile) y explicarlo en la guía; la firma de código cuesta dinero | No hay instalador ni firma (F6) |
| Procesos huérfanos o puerto ocupado | Queda un motor vivo; el siguiente arranque falla | Puerto libre elegido por la app; el motor se apaga si muere su padre | `lanzar_unity.py:409-412` ya advierte "Puede que el puerto ... este ocupado" |
| Raíz y escritura | El motor no encuentra `data/` o no puede escribir | `LAB_RAIZ`/`sys.frozen`; salidas en `%LOCALAPPDATA%` | `rutas.py:66`, `:79` |
| Datos de otro edificio | Diagramas apagados o números de otro modelo | Carpeta por edificio y cada lector comprueba `info.edificio` | Hoy pasó dos veces (§2.2) |
| Recálculo lento en el conjunto | La app parece colgada unos segundos | Pedido asíncrono (`UnityWebRequest` ya lo es) y aviso "calculando..." | 4.1-4.3 s medidos (§4) |
| Mantener dos pipelines | Cada cambio de Python obliga a re-empaquetar el motor | Un script de build del motor versionado, y QA que compare el motor contra el `.venv` | |
| Licencia de OpenSeesPy | Publicarla fuera del uso educativo necesita licencia | Mantener el uso en el curso o la tesis; preguntar antes de una tienda o un servicio abierto | `openseespywin/LICENSE.md` |
| Código compartido | Los componentes 3 a 6 tocan `unity/`, que también usa Eduardo | Hacerlo después de integrar la Semana 5, en una rama propia | CLAUDE.md §3 y §7.6 |
| Rúbrica | Muchas horas sin puntos directos | Etapas; no antes de cerrar lo evaluado | La matriz de rúbrica de la auditoría tiene 5 criterios que suman 20 puntos, y la app autónoma no es uno de ellos. Lo más cercano es "Preparación móvil, IA y gestión" (4 pts). CLAUDE.md:20-21: se evalúa corrección, verificación y trazabilidad, no realismo. No tengo el enunciado en el repo para compararlo con el original |

---

## 10. Preguntas para Pedro

1. ¿Para quién sería la app: el profesor, los compañeros, la tesis? De eso
   depende si basta con un ZIP portable (menos horas que el instalador) o si
   hace falta instalador.
2. ¿La etapa 1 entra en alguna semana, o queda como plan para después del
   curso?
3. Si algún día se publica fuera del curso: ¿se consulta la licencia de
   OpenSeesPy?
