# Guía: usar el modelo en Unity (paso a paso, desde cero)

Hay **tres flujos**. El A no necesita Python corriendo; el B y el C sí.

> Semana 5: las dos modificaciones de la entrega (M1, borrar una columna
> desde Unity; M2, cambiar el coeficiente sísmico) están paso a paso y con
> sus números en `semana05/MODIFICACIONES.md`.

| | qué hace | necesita el servidor |
|---|---|---|
| **A — Visor** | dibuja la estructura y la deformada de G | ❌ |
| **B — Recálculo en vivo** | cualquier caso (G, Q, EX, EY), reanálisis | ✅ |
| **C — Editar** | mover nodos, crear/borrar barras, cambiar secciones | ✅ |

Empieza por el A. Si no ves el marco en pantalla, el B no te va a servir de nada.

---

# FLUJO A — Solo visualizar

## PASO 0 — Generar el JSON

En la raíz del repo, con el entorno activo (`.\setup.ps1` la primera vez):

```bash
python comun\lanzar_unity.py app lt2
```

Eso **no arma ni resuelve nada**: copia a `StreamingAssets/` lo que ya está
en `data/` para ese edificio (modelo, anexos de las semanas 3 y 4,
superposición, carga móvil, Excel), con el nombre que la escena espera, y
abre la app de Windows (la compila la primera vez). Es el modo
`sincronizar` más abrir la app (`comun/lanzar_unity.py`, `abrir_visor`).
Cambiá `lt2` por `ingenieria` o `conjunto` para otro edificio, y agregá
`--pantalla-completa` si querés verlo grande.

Si el modelo cambió, primero hay que regenerar `data/` con los pasos
sueltos:

```bash
python edificios\lt2\armar.py            # geometría -> modelo
python comun\calcular.py lt2              # modelo -> resultados
python edificios\lt2\exportar_unity.py    # -> data/unity/lt2.json
```

Antes de mirar nada en Unity conviene `python comun\verificar_todo.py`:
si ahí algo falla, no tiene sentido llevarlo al visor.

> Ojo: la suite corre `semana03/exportar_unity.py lt2` y
> `semana04/exportar_unity.py lt2` (entradas "anexo Unity semana 3/4" de
> `comun/verificar_todo.py`), y esos exportadores copian el anexo a
> `StreamingAssets/`. Si estabas mirando otro edificio, la suite te deja
> los anexos del LT2 (lo dice al final). El modelo, `superposicion.json`,
> `carga_movil.json` y `resultados.xlsx` no los toca: esos se copian con
> `python comun\lanzar_unity.py sincronizar lt2`.

---

## PASO 1 — Abrir el proyecto

El proyecto Unity **ya está en el repositorio**, en la carpeta `unity/`.
No hay que crearlo ni copiar scripts a mano.

1. Abre **Unity Hub** → **Add** → **Add project from disk**
2. Elige la carpeta `unity/` del repositorio
3. Ábrelo

La primera vez tarda varios minutos: Unity reconstruye su caché
(`Library/`, unos 2 GB). Eso **no** está en el repo a propósito — son
40.000 archivos regenerables. Lo versionado son 73 archivos, 0,3 MB.

Al abrir, la escena `SampleScene` ya trae los objetos `Visor` y
`Analizador` armados y cableados.

---

## PASO 2 — Actualizar el JSON

Cada vez que cambies el modelo en Python:

1. Regenera `data/` (pasos sueltos del PASO 0).
2. Copia a `StreamingAssets/`, sin abrir Unity:

```bash
python comun\lanzar_unity.py sincronizar lt2   # solo copia; --seco dice qué copiaría
```

> Es el error más común: cambias el modelo, no copias el JSON, y Unity
> sigue mostrando el anterior. El lanzador **solo copia**: si no
> regeneraste `data/`, copia lo viejo.

---

## PASO 3 — Los scripts

Ya están en `unity/Assets/Scripts/`, y esa es **la única copia**:

```
ModeloEstructural.cs      clases de datos
VisorEstructura.cs        dibuja
AnalizadorEstructural.cs  habla con el servidor
CamaraOrbital.cs          navegar
EditorEstructura.cs       seleccionar y editar
```

> Antes estaban duplicados: una copia en la raíz del repo y otra dentro
> de Unity. Divergieron —la de Unity se quedó sin el arreglo del shader
> y sin el campo `auxiliar`— y nadie se enteró hasta que
> `test_contrato_unity.py` lo detectó. Ahora hay una sola.

Desde las semanas 3 a 5 hay más (`VisorQA`, `VisorSemana03`,
`VisorSemana04*`, `PanelUI`, `EventosVisor`...); la escena ya los trae
puestos.

---

## PASO 4 — Crear el objeto Visor

La escena del repo **ya lo trae** (PASO 1). Esto es para armarla desde una
escena vacía:

1. En **Hierarchy**, click derecho → **Create Empty**.
2. Renómbralo `Visor`.
3. Con `Visor` seleccionado, en el **Inspector** → **Add Component**.
4. Escribe `VisorEstructura` y selecciónalo.

En el Inspector aparecen sus campos: `nombreArchivo`, `radioNodo`,
colores, `mostrarDeformada`, `factorEscala` y las **capas visibles**
(nodos, columnas, vigas, muros).

---

## PASO 5 — Play

Presiona **▶**. Deberías ver el edificio (con el LT2: columnas, vigas y
muros sobre sus apoyos).

En la Console debe decir, para el LT2:
`Modelo cargado: 232 nodos, 378 elementos, 4 casos.`
(los números de control de `CLAUDE.md`; el texto lo escribe
`VisorEstructura.cs`).

**Si no ves nada**, mira la Console:

| mensaje | causa |
|---|---|
| "No encontré el archivo" | falta el PASO 2, o el nombre no calza |
| "El JSON no trae nodos" | el JSON es de un formato viejo; regenéralo |
| nada, pantalla vacía | la cámara está lejos — ver PASO 6 |

---

## PASO 6 — Mover la cámara

En la ventana **Scene**:

- **Click derecho + arrastrar** = girar
- **Rueda** = zoom
- **Click rueda + arrastrar** = desplazar
- Selecciona `Visor` y presiona **F** para centrar en él

---

## PASO 7 — Ver la deformada

1. Selecciona `Visor`.
2. Marca **Mostrar Deformada** en el Inspector.

Se redibuja al instante (también en pleno Play). La estructura sale en
amarillo, exagerada ×300. Como es gravedad, las vigas se curvan hacia
abajo. Cambia **Factor Escala** para exagerar más o menos.

Esta deformada es la del caso **G**, precalculada y guardada en el JSON.
Para los otros casos necesitas el Flujo B.

---

# FLUJO B — Recálculo en vivo

## PASO 8 — Levantar el servidor

En una terminal aparte, **déjala abierta**:

```bash
python semana05\servidor_s5.py
```

Es **el** servidor de la Semana 5: el `/analizar` de
`comun/servidor_opensees.py` más `/combinar` y `/estados`, en el mismo
puerto. `python comun\lanzar_unity.py servidor` levanta ese mismo, y
`python comun\servidor_opensees.py` sigue sirviendo solo para `/analizar`.

Debe quedar escuchando en `http://localhost:5000`, y decir
*"Solo accesible desde este equipo"*. Para conectar desde el celular
(fase de AR) hay que agregarle `--lan`, y solo en una red de confianza. Compruébalo en el
navegador: `http://localhost:5000/ping` debe responder
`{"estado":"vivo","motor":"OpenSees"}`.

---

## PASO 9 — Crear el objeto Analizador

Igual que el Visor, la escena del repo **ya lo trae**, cableado. Desde una
escena vacía:

1. En **Hierarchy**, click derecho → **Create Empty**.
2. Renómbralo `Analizador`.
3. **Add Component** → `AnalizadorEstructural`.
4. Conectarlo al Visor:

```
a. Click en  Analizador   en Hierarchy   <- debe quedar SELECCIONADO
b. El Inspector muestra "Analizador Estructural (Script)"
   con un campo  Visor  que dice "None (Visor Estructura)"
c. Arrastra  Visor  desde Hierarchy  hasta ese campo
```

> **El Inspector siempre muestra el objeto seleccionado.** El campo
> `visor` pertenece al *Analizador*, así que el Analizador tiene que
> estar seleccionado para poder llenarlo. Si arrastras con el `Visor`
> seleccionado, Unity marca "prohibido" — y con razón: ahí no hay
> ningún campo que lo acepte.
>
> Se arrastra **desde Hierarchy hacia el Inspector**, nunca el archivo
> `.cs` desde Project.

**Si el arrastre no funciona igual**, déjalo vacío: el script busca el
Visor solo con `FindObjectOfType`. Asignarlo a mano es más explícito,
pero no es obligatorio.

**Si aparece el cursor de "prohibido"** con el Analizador seleccionado,
entonces el objeto `Visor` no tiene el componente `VisorEstructura`
puesto — el campo solo acepta objetos que lo tengan.

---

## PASO 10 — Play

En la escena del repo el Analizador **no** analiza al darle Play
(`analizarAlIniciar: 0` en `SampleScene.unity`): el análisis sale con
**Enter** o con el botón *"Recalcular en el servidor (Enter)"* de la
pestaña **Modificar**. Manda el modelo completo y recibe los 4 casos. En
la Console:

```
Respuesta OK: 4 caso(s) [G, Q, EX, EY]
[G] Max desplazamiento = ... mm (mayor componente)
[G] Equilibrio de G (calcular.equilibrio), kN
     aplicada   reaccion      error
Fx ...
```

El equilibrio **lo calcula Python** (`calcular.equilibrio`, viaja en la
respuesta como `equilibrio` de cada caso) y Unity solo lo muestra, en la
Console y en la pestaña Modificar. Con el LT2 sin editar, G da aplicada
Fz = −34 148.98 kN y reacción +34 148.98 kN (`python test_servidor.py`,
bloque 9).

> Hasta la Semana 4 este log **sumaba todas las reacciones**. Con
> diafragmas eso está mal: en un nodo de diafragma `nodeReaction` trae la
> fuerza interna de la restricción. En el LT2, EX, la suma de todas da
> Fx = −7266.13 kN con 3633.06 kN aplicados; separada por grado de
> libertad da −3633.06 (`python test_servidor.py`, bloque 9). Nunca
> sumes la lista de reacciones entera.

---

## PASO 11 — Cambiar de caso

En la pestaña **Modificar**, bajo *"Caso mostrado"*, un botón por caso
(G, Q, EX, EY). Cambiar `casoActivo` en el Inspector **no** redibuja
(no hay `OnValidate`): solo sirve para elegir el caso antes de analizar.

Desde código, sin volver a consultar al servidor:

```csharp
analizador.MostrarCaso("EX");
```

Los 4 casos ya están en memoria. **No se vuelve a pedir nada** — es
instantáneo.

> Q, EX y EY del servidor son los del modelo del visor
> (`data/unity/lt2.json`: la Q del plano y el sismo del perfil), **no**
> los del anexo de la Semana 4 (`semana03/parametros.json`). Solo G
> coincide. Las combinaciones y la superposición con λ vienen del anexo
> y de `/combinar`, no de acá.

---

# FLUJO C — Editar y recalcular

## PASO 12 — Cámara y editor

Son dos scripts más: `CamaraOrbital.cs` y `EditorEstructura.cs`. Ya
están en `Assets/Scripts/` (PASO 3) y la escena del repo los trae
puestos: `CamaraOrbital` en la **Main Camera** y `EditorEstructura` en el
mismo objeto **`Analizador`** (lo arma `Assets/Editor/ConfigurarEscena.cs`).
Desde una escena vacía:

1. Selecciona la **Main Camera** → Add Component → `CamaraOrbital`.
2. Selecciona `Analizador` → Add Component → `EditorEstructura`.
3. Arrastra `Visor` y `Analizador` desde Hierarchy a sus campos.
   (También puedes dejarlos vacíos: se buscan solos.)

El panel es `OnGUI`, así que **no hay que armar ningún Canvas** ni
arrastrar prefabs. Con `VisorQA` en la escena, el editor es la pestaña
**Modificar** del panel; sin `VisorQA`, un panel propio a la derecha.

---

## PASO 12b — Activar el Input viejo (una sola vez)

La plantilla 3D de Unity 6 viene configurada con el **Input System
nuevo**, y `CamaraOrbital` / `EditorEstructura` usan la API clásica
`UnityEngine.Input`. Sin este cambio, al darle Play sale:

```
InvalidOperationException: You are trying to read Input using the
UnityEngine.Input class, but you have switched active Input handling
to Input System package in Player Settings.
```

1. **Edit → Project Settings**
2. Panel **Player** → despliega **Other Settings**
3. **Active Input Handling** → **Both**
4. Acepta el reinicio que pide Unity

Con **Both** conviven las dos APIs. Es un ajuste de proyecto: se hace
una vez y queda guardado en `ProjectSettings/ProjectSettings.asset`
(`activeInputHandler: 2`), así que a quien clone el repo después ya le
llega listo.

---

## PASO 13 — Controles

| acción | control |
|---|---|
| Orbitar | click izquierdo + arrastrar |
| Paner | click derecho + arrastrar |
| Zoom | rueda |
| Encuadrar todo | **F** |
| Seleccionar | click sobre un nodo o barra |
| Mover en planta | arrastrar el nodo **ya seleccionado** |
| Mover en altura | **Shift** + arrastrar |
| Deseleccionar | **Esc** |
| Borrar | **Supr** |
| Recalcular | **Enter** |

Un click corto selecciona; si arrastras, orbita. Por eso hay que
seleccionar el nodo **primero** y arrastrarlo **después**.

---

## PASO 14 — El ciclo de trabajo

1. Mueve un nodo, cambia una sección o borra una barra (**Supr** o
   *"Borrar barra"*).
2. **Enter** (o *"Recalcular en el servidor"*) → `POST /analizar`.
3. La deformada nueva aparece sola: al llegar la respuesta,
   `AnalizadorEstructural` enciende `mostrarDeformada` antes de aplicar
   los desplazamientos. La pestaña Modificar muestra el máximo, la tabla
   de equilibrio y *"Abrir Excel de este reanalisis"*
   (`results/excel/reanalisis_<ed>.xlsx`).

Al editar, la deformada anterior se borra: ya no corresponde a esa
geometría. Supr, Enter y Esc no actúan si el foco está en un campo de
texto (antes, borrar un carácter en X borraba el nodo).

Lo que **no** se recalcula en vivo es el anexo de la Semana 4
(diagramas, combinaciones, P-M): al editar, `VisorSemana04` lo marca
**desactualizado**, apaga los diagramas y lo dice en el aviso. Para eso
hay que re-exportar (`python semana04\exportar_unity.py lt2`) y reiniciar
Play.

**Guardar JSON** escribe `modelo_editado.json` en `persistentDataPath`
(la ruta completa sale en la Console). Sirve para **reenviarlo** al
motor y compararlo:

```bash
python semana05\reanalisis_demo.py lt2 --desde "<ruta>\modelo_editado.json" --nodo 186
```

**No** lo copies a `StreamingAssets/` como modelo de partida: `JsonUtility`
solo escribe los campos que declara `ModeloEstructural.cs`, y la
enfierradura no está entre ellos. El modelo de partida sale siempre de
Python (PASO 0).

---

## Borrar cosas: por qué no basta con quitarlas

Si borras una barra y dejas su carga distribuida, **OpenSees no falla**:
emite un warning por consola y descarta la carga. El análisis "funciona"
con menos carga de la que crees, y el equilibrio **cierra igual** porque
la carga descartada nunca entró.

Por eso al borrar, el editor limpia también:

- al borrar una **barra**: sus cargas distribuidas;
- al borrar un **nodo**: sus cargas nodales, las barras que llegaban a
  él (con sus cargas) y las referencias en diafragmas y brazos rígidos.

Lo que **no** limpia, a propósito: las cargas nodales de los extremos de
una barra borrada. En el LT2 el peso propio de columnas y muros viaja
como carga **nodal** de G (mitad en cada extremo,
`edificios/lt2/exportar_unity.py`), así que borrar la columna 69 deja
48.51 kN aplicados, 24.255 kN en cada extremo
(`python semana05\reanalisis_demo.py lt2 --borrar-elemento 69 --nodo 186`).
El editor lo avisa al borrar.

Y el servidor además lo valida y lo rechaza con un mensaje explícito, por
si el JSON llega mal armado desde otro lado.

---

# Errores frecuentes

| síntoma | causa |
|---|---|
| **"You are trying to read Input using the UnityEngine.Input class"** | falta el PASO 12b: Active Input Handling → Both. |
| **"the script class cannot be found"** | hay un error de compilación en ALGÚN script. El error real está en `unity/Logs/Editor.log`, busca `error CS`. |
| **Todo se ve MAGENTA/rosado** | no se encontró el shader. Pasa en URP (plantilla 3D de Unity 6, se reconoce por el `Global Volume` en la escena). `VisorEstructura` ya elige el shader según el pipeline; si lo ves rosado, tu copia del script está desactualizada. |
| **El edificio se ve acostado** | el swap de ejes. OpenSees usa Z vertical, Unity usa Y. Está centralizado en `Ejes.AUnity()` — un solo lugar que revisar. |
| **La deformada sale plana** | un campo del C# no calza con el JSON. `JsonUtility` **no avisa**: deja el campo en 0. Corre `python comun\test_contrato_unity.py lt2`. |
| **"No pude conectar con el servidor"** | falta el PASO 8, o cerraste la terminal. `http://localhost:5000/ping` lo confirma. |
| **"El servidor rechazó el modelo (HTTP 400)"** | el mensaje trae el motivo real (sección inexistente, nodo que no existe, `vecxz` paralelo...). Léelo, es explícito. |
| **Unity muestra datos viejos** | no copiaste el JSON de nuevo a StreamingAssets tras regenerarlo: `python comun\lanzar_unity.py sincronizar lt2`. O corriste `verificar_todo.py` mirando otro edificio: deja los anexos del LT2 (ver PASO 0). |
| **El panel dice que el anexo está desactualizado** | editaste el modelo: los diagramas y el P-M de la Semana 4 son del modelo original. No es un error; ver PASO 14. |
| **La clase no aparece en Add Component** | hay un error de compilación en ALGÚN script (bloquea todos), o el nombre del archivo no coincide con el de la clase. |
| **El click no selecciona nada** | los objetos necesitan Collider. `CreatePrimitive` los trae; si cambiaste el dibujo, revísalo. |
| **Arrastrar el nodo orbita la cámara** | hay que seleccionarlo primero con un click corto, y arrastrarlo después. |
| **No deja arrastrar un objeto a un campo** | el Inspector muestra el objeto SELECCIONADO: para llenar un campo del Analizador, selecciona el Analizador. Y el objeto arrastrado debe tener el componente de ese tipo. |
| **Warnings `[modelo] Elemento N dice tipo=...`** | la etiqueta no calza con la geometría. El modelo se resolvió igual (manda la geometría), pero delata datos mal importados del DXF. |

---

# El punto de los ejes

- **OpenSees**: Z es vertical (convención de ingeniería).
- **Unity**: Y es vertical (convención de videojuego).
- **Conversión**: `Unity(x, z_opensees, y_opensees)`.

Está en un solo lugar, `Ejes.AUnity()` en `ModeloEstructural.cs`. Si el
edificio se ve acostado, ahí es.

---

# Resumen del flujo

```
python comun\lanzar_unity.py app lt2     # 1. copia data/ -> StreamingAssets y abre la app
python semana05\servidor_s5.py          # 2. dejar corriendo (flujos B y C)
```

Cada vez que toques el modelo en Python: **regenerá `data/`** (PASO 0,
pasos sueltos) y **repetí el paso 1**; el lanzador solo copia. Lee de la
escena qué archivo abre el visor, así que no hay que acordarse de ningún
nombre.
