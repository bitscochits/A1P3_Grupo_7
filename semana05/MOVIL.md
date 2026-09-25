# Semana 5 — Preparación móvil

El punto 6 del enunciado pide dejar la app preparada para un teléfono:
requisitos, un teléfono compatible identificado y un build móvil inicial.
Este documento dice qué se decidió, qué pide Unity 6.5, cómo revisar un
teléfono, qué código ya está listo (con archivo y línea) y los pasos
exactos para cuando se decida hacer el build.

**El build móvil inicial NO se hizo.** Fue una decisión de prioridad, no un
bloqueo técnico.

---

## 1. La decisión

Pedro, 16-09:

- **Windows primero.** La demo y la entrega corren en la app de Windows
  (`build/LaboratorioEstructural.exe`).
- **El móvil es la última prioridad.** Se prepara el código, pero el build
  va al final y solo si alcanza.
- **No instalar Android.** El módulo "Android Build Support" pesa varios
  GB y pide permisos de administrador.

Estado del editor el 17-09 (`C:/Program Files/Unity/Hub/Editor/6000.5.10f1/Editor/Data/PlaybackEngines`):
solo `WebGLSupport` y `windowsstandalonesupport`. El lanzador lo confirma
sin abrir Unity:

```powershell
.\.venv\Scripts\python.exe comun\lanzar_unity.py android lt2 --seco
```
```
ERROR: El editor de Unity no tiene el modulo para android (falta PlaybackEngines/AndroidPlayer). No se abrio Unity ni se copio nada.
Para instalarlo (baja varios GB): Unity Hub > Installs > 6000.5.10f1 > Add modules.
```

Sale con código 1. El módulo Web **sí** está instalado, pero el build Web
tampoco se hizo (no existe `build/web`).

---

## 2. Requisitos de Unity 6.5 (6000.5) para el teléfono

Consultados el 17-09 en la documentación oficial de Unity:

- [System requirements for Unity 6.5](https://docs.unity3d.com/6000.5/Documentation/Manual/system-requirements.html)
- [Android requirements and compatibility](https://docs.unity3d.com/6000.5/Documentation/Manual/android-requirements-and-compatibility.html)
- [iOS requirements and compatibility](https://docs.unity3d.com/6000.5/Documentation/Manual/ios-requirements-and-compatibility.html)

| | Android | iOS / iPadOS | Web (navegador del teléfono) |
| --- | --- | --- | --- |
| Sistema | Android 8.0 "Oreo" (API 26) o más | iOS 15 o más | iOS Safari 15 o más; Chrome 58 o más |
| CPU | ARMv7 con Neon (32 bits) o ARM64 | SoC A8 o superior | — |
| Gráficos | OpenGL ES 3.0+ o Vulkan (ES 1.x y 2.0 no) | Metal | WebGL 2.0 |
| RAM | 1 GB o más | por confirmar (la página no la da) | por confirmar |
| Otros | Android nativo (no emulador ni contenedor); texturas ETC/ASTC | Compilar exige un Mac con Xcode 16 o más | Desde iOS Safari 18.2 hay un límite de memoria mayor |
| Módulos del editor | Android Build Support con OpenJDK 17 y Android SDK & NDK Tools (Unity Hub instala SDK API 36 y NDK r27c) | iOS Build Support, en un Mac | Web Build Support (**instalado**) |

Lo que decide el proyecto dentro de esos rangos, comprobado en
`unity/ProjectSettings/ProjectSettings.asset`:

| ajuste | valor | línea |
| --- | --- | --- |
| `AndroidMinSdkVersion` | 26 (Android 8.0) | :182 |
| `AndroidTargetArchitectures` | 2 = ARM64 | :274 |
| `scriptingBackend: Android` | 1 = IL2CPP | :839 |
| `iOSTargetOSVersionString` | 15.0 | :200 |
| `insecureHttpOption` | 2 = HTTP permitido (servidor en la red local) | :945 |
| `applicationIdentifier: Android` | el de la plantilla (`com.UnityTechnologies.com.unity.template.urpblank`); `ConstruirAndroid` lo cambia al compilar | :172 |
| `webGLCompressionFormat` / `webGLDecompressionFallback` | 0 = Brotli / 0 = sin fallback; `ConstruirWeb` lo cambia a `Disabled` al compilar | :818 / :822 |

**iOS queda descartado:** no hay Mac en el grupo, y sin Mac no se puede
compilar.

**Tamaño del módulo Android:** 1.19 GB de descarga y 5.19 GB en disco,
según `unity install-modules --list` en la auditoría del 16-09 (no se
volvió a medir).

---

## 3. Cómo identificar un teléfono compatible

**Los teléfonos del grupo (25-09): los tres son iPhone.** Eduardo y Monse
tienen un iPhone 16 y Pedro un iPhone 16 Pro Max, los tres con iOS 26.5.2.

| dato | mínimo para el build **Web** | iPhone 16 | iPhone 16 Pro Max |
| --- | --- | --- | --- |
| sistema | Safari con WebGL 2 (iOS 15 o más) | iOS 26.5.2 | iOS 26.5.2 |
| procesador | 64 bits | Apple A18 | Apple A18 Pro |
| GPU / API | WebGL 2.0 (sobre Metal en iOS) | GPU Apple de 5 núcleos | GPU Apple de 6 núcleos |
| RAM | ~1 GB libre para la pestaña (el build pesa 70 MB en disco) | 8 GB | 8 GB |
| pantalla | — (el panel escala por dpi) | 2556 × 1179, 460 ppi | 2868 × 1320, 460 ppi |

**Qué significa para el build:**

- **El APK de Android no sirve**: ninguno tiene Android. Por eso no se
  instaló el módulo de Android.
- **Una app nativa de iOS no se puede compilar aquí**: Unity genera un
  proyecto de Xcode, y firmarlo e instalarlo exige un **Mac** con Xcode y
  una cuenta de desarrollador de Apple. No hay Mac en el grupo.
- **El camino que sí sirve es el build Web en Safari**, y es el que se hizo
  (§6.1): la misma app, compilada a WebAssembly, servida desde el PC por la
  red local. No se instala nada en el teléfono.

Con esto los tres teléfonos quedan **compatibles con el build Web**. Lo que
falta confirmar en cada uno es que la app abra y se pueda tocar (§6.3).

### Sin cables

- **Ajustes → Acerca del teléfono**: modelo, versión de Android y RAM. En
  muchas marcas la RAM y el procesador están en "Especificaciones" o
  "Información de software" (la ruta cambia según el fabricante).
- **Chrome del teléfono → `chrome://gpu`**: busca `WebGL2: Hardware
  accelerated` y la línea `GL_VERSION` (tiene que decir OpenGL ES 3.x). En
  la misma página sale el renderer (la GPU).
- **Dentro de la app**, una vez instalada: **Vista** → "Tamano del texto y
  equipo" muestra `SystemInfo.deviceModel`, sistema operativo, GPU y API
  gráfica, RAM, pantalla, dpi y escala del panel (`VisorQA.cs:2095`).

### Con `adb` (depuración USB activada)

`adb` viene con Android SDK Platform-Tools, que hoy **no** está instalado.

```powershell
adb devices                                          # el telefono tiene que aparecer como 'device'
adb shell getprop ro.product.model                   # modelo
adb shell getprop ro.build.version.release           # version de Android
adb shell getprop ro.build.version.sdk               # API: 26 o mas
adb shell getprop ro.product.cpu.abilist             # tiene que incluir arm64-v8a
adb shell dumpsys SurfaceFlinger | findstr GLES      # GPU y version de OpenGL ES
adb shell pm list features | findstr vulkan          # soporte de Vulkan
adb shell cat /proc/meminfo | findstr MemTotal       # RAM
adb shell wm size                                    # resolucion
adb shell wm density                                 # densidad (dpi)
```

---

## 4. Qué ya está listo en el código

Cada punto se comprobó con grep sobre el árbol del 17-09.

| qué | dónde | por qué importa en móvil |
| --- | --- | --- |
| **Lectura de StreamingAssets con `UnityWebRequest`** | `unity/Assets/Scripts/LectorStreaming.cs:111` (`Leer`), `:114` (`UnityWebRequest.Get`). La usan `VisorEstructura.cs:246`, `VisorSemana03.cs:341`, `VisorSemana04.cs:343`, `VisorSemana04.Superposicion.cs:310` y `VisorCargaMovil.cs:318` | En Android, StreamingAssets vive **dentro** del `.apk` (`jar:file://...!/assets/`) y en Web es una URL: `File.ReadAllText` diría "no encontré el archivo". Queda un `CargarJSON()` síncrono (`VisorEstructura.cs:261-272`) solo por compatibilidad: el arranque usa el asíncrono |
| **Cámara táctil** | `unity/Assets/Scripts/CamaraOrbital.cs:59` (`gradosPorPantallaTactil = 180`), `:170` (con dedos en pantalla manda el táctil), `:244` (`ManejarTactil`), `:303` (pinza = zoom), `:308` (paneo con dos dedos) | Un dedo orbita; dos dedos hacen pinza y paneo. Se evita que el mouse simulado orbite dos veces |
| **Escala del panel por DPI** | `unity/Assets/Scripts/PanelUI.cs:93` (`EsMovil`), `:126-132` (`Escala()`: dpi/160 en móvil, dpi/96 en PC, acotada a 0.8-3.5), `:144` (`AltoBoton` 40 en móvil, 26 en PC) | Botones del tamaño de un dedo y texto legible a 400+ dpi. En Windows se midió 120 dpi → escala 1.25 (`capturas/registro.txt`) |
| **Build Web** | `unity/Assets/Editor/ConstruirApp.cs:93` (`ConstruirWeb`), `:107` (compresión `Disabled`) | Sin compresión, cualquier servidor estático (`python -m http.server`) sirve el build por HTTP. Con Brotli sin fallback no carga |
| **Build Android que avisa** | `ConstruirApp.cs:114` (`ConstruirAndroid`), `:118` (chequea el módulo **antes** de tocar nada), `:127` (`cl.uandes.grupo7.laboratorio`, `:59`), `:128` (IL2CPP), `:129` (ARM64), `:132` (horizontal), `:135` (`.apk`, no `.aab`) | Sin el módulo sale con 1 y dice cómo instalarlo. Con el módulo compila sin cambiar nada del proyecto a mano |
| **HTTP a la red local** | `ConstruirApp.cs:202` (`insecureHttpOption = AlwaysAllowed` en toda build); `ProjectSettings.asset:945` | El servidor corre en el PC por `http://`, sin certificado |
| **Lanzador** | `comun/lanzar_unity.py:551-560` (destinos windows, web y android), `:567` (`modulo_instalado`: mira `PlaybackEngines` sin abrir Unity), `:707` (`construir_web`, imprime cómo servirlo) | `lanzar_unity.py web` y `android` con `--seco` dicen qué harían |
| **Servidor en la red local** | `semana05/servidor_s5.py:197` (`--lan`: escucha en 0.0.0.0); `comun/servidor_opensees.py:90` (`PERMITIR_CORS`) y `:683` (cabeceras CORS en toda respuesta, también en `/combinar`) | El teléfono pide a la IP del PC. El build Web corre en otro origen y necesita CORS |
| **URL del servidor editable** | Modificar: `EditorEstructura.cs:1145` (campo URL de `/analizar`); Superposición: `VisorSemana04.Superposicion.cs:760` (campo URL, guardado en `PlayerPrefs`) | En el teléfono, `localhost` es el propio teléfono: hay que escribir `http://<IP del PC>:5000` |

---

## 5. Qué funcionaría en el teléfono y qué no

Es análisis de código: **nada de esto se probó en un teléfono**.

| función | sin servidor | con `servidor_s5.py --lan` | nota |
| --- | --- | --- | --- |
| Modelo, capas, filtro de piso, vista realista o técnica | sí | sí | todo viene de StreamingAssets. La luz ambiente Trilight de la realista solo se probó en Windows |
| Casos del anexo, diagramas, P-M, mapa D/C y críticos | sí | sí | `semana04.json` va dentro del build |
| E1..E3 precalculados | sí | sí | `superposicion.json` |
| Carga móvil | sí | sí | `carga_movil.json` |
| Selección por toque | sí (por confirmar) | sí (por confirmar) | `VisorQA.LeerClick` usa `GetMouseButtonUp(0)` (`VisorQA.cs:431`) y Unity simula el mouse con el primer dedo |
| **Superposición LIBRE** (sliders) | **no** | sí | necesita `POST /combinar`: Unity no suma casos (regla de oro) |
| **Reanálisis M1** | **no** | sí | necesita `POST /analizar`: OpenSees corre en el PC |
| "Abrir Excel de resultados" | **no** | **no** | `LectorStreaming.RutaExcelResultados` devuelve `null` en Android y Web (`LectorStreaming.cs:74`): StreamingAssets no es una carpeta |
| "Abrir Excel de este reanalisis" | **no** | **no** | el archivo queda en el PC (`results/excel/`) |
| Mover un nodo en altura | **no** | **no** | necesita Shift (`EditorEstructura.cs:495`) |
| Actualizar datos sin recompilar | — | — | en Windows y Web basta `lanzar_unity.py sincronizar <ed>`; en Android los JSON van dentro del `.apk` y hay que recompilar |

---

## 6. Pasos exactos cuando se decida

Siempre con Unity y la app **cerrados**: los builds corren Unity en batch.

### 6.1 Build Web (el módulo ya está instalado)

> **Hecho el 25-09, con el conjunto.** `lanzar_unity.py web conjunto`:
> 24 min de compilación, `build\web` de 70.2 MB (`web.wasm` 44 MB,
> `web.data` 12 MB). Abierto en Chrome de escritorio desde la IP de la red
> local: carga el modelo (558 nodos, 937 elementos), los 3 estados de
> superposición y la carga móvil, sin excepciones.
>
> **El primer build tenía un error que solo aparece en Web y Android:**
> `Can't add component because class 'SphereCollider' doesn't exist!`
> (558 veces, un nodo cada una) y lo mismo con `CapsuleCollider` (531
> barras). Esos builds quitan del motor las clases que ninguna escena usa
> ("Strip Engine Code"), y los colisionadores los agrega
> `GameObject.CreatePrimitive` por código. Sin ellos no se puede
> seleccionar nada tocando la pantalla. Lo arregla
> `unity/Assets/link.xml`, que le pide a Unity conservarlos; con él, el
> build nuevo da 0 de esos errores. El build de Windows no quita código
> del motor, por eso ahí nunca se vio.
>
> **Falta:** abrirlo en un iPhone del grupo (Safari) y revisar lo de §6.3.

```powershell
.\.venv\Scripts\python.exe comun\lanzar_unity.py sincronizar lt2
.\.venv\Scripts\python.exe comun\lanzar_unity.py web lt2 --seco      # revisar lo que haria
.\.venv\Scripts\python.exe comun\lanzar_unity.py web lt2             # build\web\index.html, log build\unity_build_web.log
```

Servirlo y abrirlo desde el teléfono (mismo WiFi que el PC):

```powershell
ipconfig                                                           # anotar la IPv4 del PC
cd build\web
..\..\.venv\Scripts\python.exe -m http.server 8080 --bind 0.0.0.0
```

En el navegador del teléfono: `http://<IPv4 del PC>:8080`. Windows puede
preguntar si deja pasar a Python por el firewall: hay que aceptar solo
para redes privadas. Para LIBRE y M1, en otra terminal:

```powershell
.\.venv\Scripts\python.exe semana05\servidor_s5.py --lan
```

y en la app, escribir `http://<IPv4 del PC>:5000` en **Caso** →
Superposición → URL, y `http://<IPv4 del PC>:5000/analizar` en
**Modificar**. `--lan` no se usa en una red pública.

### 6.2 Build Android (necesita instalar el módulo)

1. **Instalar** (lo hace una persona, no un agente: pide UAC y varios
   GB). Unity Hub → Installs → 6000.5.10f1 → Add modules → "Android Build
   Support" con "OpenJDK" y "Android SDK & NDK Tools".
2. **Comprobar:**

   ```powershell
   .\.venv\Scripts\python.exe comun\lanzar_unity.py android lt2 --seco   # ya no debe decir 'falta PlaybackEngines/AndroidPlayer'
   ```

3. **Compilar:**

   ```powershell
   .\.venv\Scripts\python.exe comun\lanzar_unity.py sincronizar lt2
   .\.venv\Scripts\python.exe comun\lanzar_unity.py android lt2          # build\android\LaboratorioEstructural.apk
   ```

   El log queda en `build\unity_build_android.log`. El APK lleva dentro
   los JSON del momento: si se regeneran, hay que recompilar.

4. **Instalar en el teléfono.** Con depuración USB activada:
   `adb install -r build\android\LaboratorioEstructural.apk`. La ruta de
   `adb` dentro del módulo instalado está por confirmar. La otra forma es
   copiar el `.apk` al teléfono y abrirlo, permitiendo "instalar apps
   desconocidas" para el explorador de archivos.
5. **Servidor** (para LIBRE y M1): `servidor_s5.py --lan` y las URLs con
   la IP del PC, igual que en Web.
6. **Anotar** el teléfono en la tabla de §3 y sacar una captura de
   **Vista** → "Tamano del texto y equipo" como evidencia.

### 6.3 Qué revisar en el primer arranque

- Que cargue el modelo: la cabecera tiene que decir `LT2 232 nodos, 378
  elementos`. Si dice "Sin modelo cargado", falló la lectura de
  StreamingAssets.
- Que un dedo orbite, que la pinza haga zoom y que un toque seleccione.
- Que el panel se lea. Si no, ajustar con "A-" / "A+" en **Vista**.
- Con el servidor prendido: "Probar conexion" en Modificar y "Conectar
  (GET /estados)" en Superposición.
