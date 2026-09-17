# Semana 5 — Modificación y reanálisis: M1 y M2

Dos modificaciones completas del LT2, cada una seguida en cinco pasos
**interfaz o dato → modelo → OpenSees → resultados → Unity**. Todos los
números están copiados de la salida de los scripts que se nombran al lado
(corridos el 16-09 en la rama `semana05`); ninguno viene de un informe ni
de memoria. Las referencias `archivo:línea` son de ese día: si una línea se
movió, el nombre de la función al lado sigue valiendo.

| | qué se modifica | por dónde entra | cómo vuelve a Unity |
|---|---|---|---|
| **M1** | se borra la columna 69 | la pestaña **Modificar** de Unity | en vivo: `POST /analizar` → OpenSees → la respuesta se dibuja |
| **M2** | coeficiente sísmico 0.10 → 0.20 | un dato por línea de comandos (`--cs 0.20`) | se re-exporta el anexo de la Semana 4 y se reinicia Play |

Scripts que lo reproducen sin abrir Unity y **sin escribir en `data/`**:

```bash
python semana05/reanalisis_demo.py lt2 --borrar-elemento 69 --nodo 186 --elemento 337
python semana05/reanalisis_demo.py lt2 --borrar-elemento 69 --nodo 186 --float32 --url http://localhost:5000/analizar
python semana05/comparar_anexos.py lt2 --cs 0.20
```

y sus pruebas:

```bash
python test_servidor.py                          # bloques 8, 9 y 10: equilibrio y Excel
python edificios/lt2/tests/test_reanalisis.py    # bloques [4] y [5]: la M1 por HTTP
```

---

## M1 — Borrar la columna 69 desde Unity (automática)

La columna 69 es una `P 0.70x0.70` del LT2 entre los nodos 144 (z 7.87 m)
y 186 (z 11.83 m), L = 3.96 m. El nodo que se sigue es el 186, arriba de la
columna; la viga vecina que se muestra es la 337 (`viga_x V 0.60x0.80`,
nodos 207 → 186).

### Para la demo

```bash
python semana05/servidor_s5.py            # terminal 1, dejar abierta (puerto 5000)
python comun/lanzar_unity.py app lt2      # o Play en el editor
```

En Unity: seleccionar la barra 69 (click, o "Ir a ID" en el panel) →
pestaña **Modificar** → *"Borrar barra (Supr)"* → **Enter** (o
*"Recalcular en el servidor (Enter)"*).

### Paso 1 — Interfaz: la edición

`EditorEstructura.BorrarElementoPorId(69)` (`unity/Assets/Scripts/EditorEstructura.cs:727`,
lo mismo que el botón y la tecla Supr, `:544`) llama a `BorrarElemento`
(`:740`): quita la barra de `Modelo.elementos` y, con
`QuitarCargasDeElemento` (`:788`), las cargas **distribuidas** que la
nombran en cada caso. No toca nodos ni cargas **nodales**. Después
`MarcarModificado` (`:639`) avisa `EventosVisor.ModeloEditado`.

`semana05/reanalisis_demo.py` hace la misma edición en memoria
(`borrar_elemento`, `reanalisis_demo.py:92`). Su salida:

```
borrar 69: columna P 0.70x0.70, nodos 144 (z 7.87) -> 186 (z 11.83), L = 3.96 m
cargas distribuidas quitadas: 0  (G 0, Q 0, EX 0, EY 0)
PESO PROPIO QUE QUEDA APLICADO: A*gamma*L = 0.49*25*3.96 = 48.51 kN,
  que viaja como carga NODAL de G, mitad en cada extremo (edificios/lt2/exportar_unity.py).
  BorrarElemento no toca cargas nodales: siguen fz = -24.255 kN en 186 y -48.510 en 144
  (24.255 de cada uno eran de esta barra).
```

La columna no tenía carga repartida (0 quitadas): su peso propio es nodal
(`edificios/lt2/exportar_unity.py:392-397`, "mitad del peso en cada
extremo"). Ver **Limitaciones**.

### Paso 2 — Modelo: lo que viaja

`AnalizadorEstructural.EnviarModelo` (`AnalizadorEstructural.cs:219`)
serializa `visor.Modelo` con `JsonUtility.ToJson` (`:254`) y lo manda por
`POST` (`:309-313`) a `urlServidor`, con `?edificio=<ed del anexo>` cuando
el modelo no trae `info.edificio` (`UrlConEdificio`, `:293`; hoy
`data/unity/lt2.json` no lo trae).

`JsonUtility` escribe **floats de 32 bits** y solo los campos que declara
`ModeloEstructural.cs`. La demo lo emula con `--float32`
(`esquema_csharp` lee los campos del C#, `reanalisis_demo.py:113`;
`como_jsonutility`, `:183`). El test comprueba que la edición deja
`377 elementos, 232 nodos` (de 378 y 232).

### Paso 3 — OpenSees

`comun/servidor_opensees.py`, `analizar` (`:759`) →
`construir_y_resolver` (`:598`, llamado en `:774`): arma el modelo una vez
y resuelve los cuatro casos (`ops.analyze(1)`, `:528`); reacciones con
`nodeReaction` (`:555`) y fuerzas con `eleResponse(..., 'localForce')`
(`:568`). Nuevo en la Semana 5: el equilibrio de **cada caso**,
`r['equilibrio'] = equilibrio_del_caso(...)` (`:658`), que es
`calcular.equilibrio` (`comun/calcular.py:65`) tal cual, importado dentro de
la función por el ciclo de imports (`:578`). Después escribe el Excel
(`escribir_excel`, `:731`, llamado en `:781`) dentro de un `try` que atrapa
`BaseException`: un Excel que falla no rompe `/analizar`.

Salida de `reanalisis_demo.py` (en proceso): `todos los casos convergen,
antes y despues`; por HTTP (`--float32 --url`): `resuelto: antes 0.8 s,
despues 0.9 s`.

### Paso 4 — Resultados

De `python semana05/reanalisis_demo.py lt2 --borrar-elemento 69 --nodo 186 --elemento 337`
(la corrida `--float32 --url` da los mismos desplazamientos y esfuerzos a
la precisión impresa, salvo el máximo de EY antes: 15.25720 en vez de
15.25721 mm; en el equilibrio, Q aplicada −11361.002 en vez de −11361.003
kN y los errores cambian en el último dígito, siempre bajo la cota):

**Nodo 186** (mm; entre comillas, lo que escribe el panel del editor con
`"0.####"` sobre un float):

| caso | comp. | antes | después | panel antes → después |
|---|---|---|---|---|
| G | UZ | −3.64515 | −21.59875 | "UZ -3.6452 mm" → "UZ -21.5988 mm" |
| G | UX | 1.06778 | 1.16758 | "UX 1.0678 mm" → "UX 1.1676 mm" |
| Q | UZ | −1.41122 | −6.29423 | "UZ -1.4112 mm" → "UZ -6.2942 mm" |
| EX | UX | 16.31498 | 16.54456 | "UX 16.315 mm" → "UX 16.5446 mm" |
| EY | UY | 6.81593 | 6.87101 | "UY 6.8159 mm" → "UY 6.871 mm" |

**Máximo por caso** (`max_desplazamiento`: la mayor **componente**):

| caso | antes | después | |
|---|---|---|---|
| G | 6.71145 | 21.59875 mm | ×3.22 |
| Q | 2.90516 | 6.29423 mm | ×2.17 |
| EX | 16.41508 | 16.65065 mm | ×1.01 |
| EY | 15.25721 | 15.34956 mm | ×1.01 |

**Viga 337** (`viga_x V 0.60x0.80`, 207 → 186), caso G, ejes locales:
Vz_i −140.941 → 67.579 kN; My_i / My_j 457.871 / 575.311 →
268.933 / −278.347 kN·m. La viga 314 (`viga_y`, 183 → 186), que ahora
salva el vano sin apoyo: My −132.169 / 103.871 → −871.713 / −810.304 kN·m.

**Equilibrio por caso** (`calcular.equilibrio`, reacciones separadas por
grado de libertad):

| caso | aplicada antes = después (kN) | peor error antes / después | cota |
|---|---|---|---|
| G | [0.000, 0.000, −34148.979] | 2.0e-04 / 2.0e-04 | 1.1e-03 |
| Q | [0.000, 0.000, −11361.003] | 1.2e-04 / 1.0e-04 | 1.1e-03 |
| EX | [3633.063, 0.000, 0.000] | 2.1e-04 / 2.0e-04 | 1.1e-03 |
| EY | [0.000, 3633.063, 0.000] | 1.0e-04 / 9.0e-05 | 1.1e-03 |

La cota es su causa: cada reacción viene redondeada a 4 decimales
(5e-5 kN × 21 reacciones) más 1e-9 relativo del residuo del solver. La
carga de G **no cambia** (−34148.979 antes y después): la columna solo
tenía peso nodal, que se queda. El "antes" reproduce la deformada G
precalculada del JSON: `peor 6.0e-09 m en (192, 'ux')`.

**Excel**: con `--url`, el servidor escribe
`results/excel/reanalisis_lt2.xlsx` (los dos pedidos, antes y después,
escriben el mismo libro: queda el del después). Hojas y resumen, leídos con
`python -c "import sys; sys.path.insert(0,'comun'); import excel; print(excel.estructura('results/excel/reanalisis_lt2.xlsx')['hojas'])"`
y `excel.leer`: `LEEME, Resumen, Nodos, Desplazamientos, Elementos,
Esfuerzos, Reacciones`; en Resumen, G: aplicada Fz −34148.979, reacción
34148.979, "Equilibrio confiable" sí, origen "servidor", mayor componente
21.59875 mm, |u| máx 21.63042 mm en el nodo 186.

La misma M1 por HTTP con el modelo como lo manda `JsonUtility` está fijada
en `edificios/lt2/tests/test_reanalisis.py` bloque [5]:
`antes: UZ186 (G) = -3.64515 mm`, `despues: UZ186 (G) = -21.59875 mm`,
`despues: maximo G = 21.59875 mm` (tolerancia 1e-4 mm) y
`G aplicada no cambia: -34148.9790 -> -34148.9790 kN`.

### Paso 5 — Unity

`AnalizadorEstructural.ProcesarRespuesta` (`:456`) lee la respuesta con
`JsonUtility.FromJson<RespuestaServidor>` (`:461`; `CasoResultado.equilibrio`
y `RespuestaServidor.excel` en `ModeloEstructural.cs:532` y `:562`) y
`ElegirCaso` (`:538`) enciende `visor.mostrarDeformada` **antes** de
`AplicarDeformada` (`:561-562`): la deformada aparece sola. En la Console
(`:567-569`): `[G] Max desplazamiento = ... mm (mayor componente)` y la tabla
`Equilibrio de G (calcular.equilibrio), kN`; en la pestaña Modificar, la
misma tabla, un botón por caso y *"Abrir Excel de este reanalisis"*. Al
seleccionar el nodo 186 el panel escribe `UZ {Mm(d.uz)} mm`
(`EditorEstructura.cs:1330`, formato `"0.####"`, `:996`); la viga,
`My {My_i} / {My_j} kN*m` (`:1403`).

Al editar, `VisorSemana04.AlEditarModelo` (`VisorSemana04.cs:527`) marca el
anexo de la Semana 4 **desactualizado**: `AnexoCalzaConElModelo = false`
(`:532`) apaga los diagramas y el aviso dice que los casos de
`semana04.json`, E1..E3 y LIBRE son del modelo original.

**Qué no se comprobó**: Unity estuvo cerrado en esta fase. Lo del lado
Unity sale de leer el C# y de la emulación de `JsonUtility` (float32 y
campos de `ModeloEstructural.cs`), que el test pasa por HTTP. Los textos
entre comillas del panel son la emulación de `ToString("0.####")` de un
float. El registro desde el exe queda para `CapturaSemana05` (integración).

---

## M2 — Coeficiente sísmico 0.10 → 0.20 (por dato)

El enunciado deja el sismo en manos del profesor. M2 cambia **un dato**,
el coeficiente sísmico, y lo sigue hasta el panel de la Semana 4: la
columna demo 5 y el muro demo 9 (los elige `construir_anexo` por regla: la
columna de mayor axial en G y el muro más largo).

### Para la demo

Esto **sí escribe** `data/unity/semana04.json` y su copia en
`StreamingAssets/`:

```bash
python semana04/exportar_unity.py lt2 --cs 0.20     # y en Unity: Stop + Play
python semana04/exportar_unity.py lt2               # al terminar: volver a la base
```

Para verlo antes, sin escribir nada: `python semana05/comparar_anexos.py lt2 --cs 0.20`.

### Paso 1 — Dato

`--cs 0.20` → `semana03/parametros.py:177-179`
(`p['coef_sismico'] = v`). Queda escrito en `info.parametros` del anexo,
que Unity deserializa:

```
coeficiente sismico = 0.1000                               | coeficiente sismico = 0.2000   <-- cambia
```

### Paso 2 — Modelo: el caso EX

`lab_semana03.armar_casos` (`semana03/lab_semana03.py:337`) arma
`V = p['coef_sismico'] * sum(pesos)` (`:374`) y lo reparte en altura con
el patrón (potencia k = 1). G y Q no dependen de Cs.

```
corte basal V = Cs * W:  3792.28 kN  ->  7584.56 kN   (x 2.0000)
```

### Paso 3 — OpenSees

`lab.resolver` (`lab_semana03.py:389`) llama al **mismo motor** que
`/analizar`: `motor.construir_y_resolver` (`:393`). Llamado desde
`construir_anexo` (`semana04/exportar_unity.py:588`, parámetros en `:594`,
casos en `:596`, resolución en `:597`). Lo que comprueba
`comparar_anexos.py` sobre los dos anexos:

```
[OK  ] G identico (no depende de Cs)   peor 0.0e+00 m, 0.0e+00 kN; demandas distintas 0
[OK  ] Q identico (no depende de Cs)   peor 0.0e+00 m, 0.0e+00 kN; demandas distintas 0
[OK  ] EX nuevo = 2 * EX base   peor error/cota: 0.67 en m (1.0e-08 en (204, 'rx')), 0.72 en kN (6.0e-04 <= 8.3e-04 en (229, 'My', 'x = 3.55'))
[OK  ] EY nuevo = 2 * EY base   peor error/cota: 0.67 en m (1.0e-08 en (39, 'uz')), 0.67 en kN (1.1e-03 <= 1.6e-03 en (88, 'My', 'x = 8.90'))
[OK  ] anexo nuevo: cada combinacion = sum lambda * casos   peor 1.4G: 4.0e-09 m, 4.0e-05 kN <= 1.2e-04 = 5e-5 (1 + sum|lambda|); error/cota 0.33
[OK  ] el anexo base es el que Unity lee hoy (data/unity/semana04.json)   maximos y demandas de los 9 casos iguales
```

Las cotas son su causa: fuerzas redondeadas a 4 decimales y
desplazamientos a 8, en los dos anexos (5e-5·(1 + k) con k = 2); en las
estaciones del diagrama My(x) lleva x·V_i, que multiplica el redondeo por
x (`cota_de_cierre` del exportador). El último check dice que el "antes"
de la tabla es lo que Unity muestra hoy.

### Paso 4 — Resultados

Máximo por caso (`max_desplazamiento_mm` del anexo: la **norma**) y
cuántas barras con fierro no pasan, de 69:

| caso | antes (mm) | después (mm) | NO PASA antes → después |
|---|---|---|---|
| G | 6.7959 | 6.7959 | 0 → 0 |
| Q | 1.9959 | 1.9959 | 0 → 0 |
| EX | 17.2532 | 34.5064 | 2 → 8 |
| EY | 16.5587 | 33.1174 | 0 → 8 |
| S3 (1.0G + 0.5Q + 1.0EX, la que abre el visor) | 19.7760 | 36.1204 | 2 → 5 |
| 1.4G | 9.5142 | 9.5142 | 0 → 0 |
| 1.2G+1.6Q | 11.3393 | 11.3393 | 0 → 0 |
| 1.2G+1.0Q+1.4EX | 27.2455 | 50.2473 | 4 → 10 |
| 1.2G+1.0Q+1.4EY | 22.6660 | 45.6782 | 0 → 7 |

Demanda-capacidad (`bloque_caso`, `semana04/exportar_unity.py:559-562`:
`d = dc.demanda(...)`, `Mn = dc.capacidad_en(P, curva)`, `u = M / Mn`).
Mn cambia porque cambia P, así que u no se duplica exacto.

**Columna demo 5** (`P 0.70x0.70`, familia 1):

| caso | P (kN) | M (kN·m) | Mn (kN·m) | u = D/C | |
|---|---|---|---|---|---|
| S3 | 4860.3 → 4889.6 | 267.7 → 521.1 | 1757.9 → 1757.7 | 0.152 → 0.296 | PASA |
| EX | 29.2 → 58.4 | 253.7 → 507.4 | 1195.8 → 1201.5 | 0.212 → 0.422 | PASA |
| 1.2G+1.0Q+1.4EX | 6301.0 → 6341.9 | 374.0 → 728.8 | 1748.4 → 1745.2 | 0.214 → 0.418 | PASA |

**Muro demo 9** (`M 0.25x7.95`, familia 2, momento en su plano |Mz|):

| caso | P (kN) | M (kN·m) | Mn (kN·m) | u = D/C | |
|---|---|---|---|---|---|
| S3 | 3932.6 → 4577.5 | 2598.9 → 5657.6 | 28689.9 → 30421.8 | 0.091 → 0.186 | PASA |
| EY | −479.1 → −958.2 | 9661.1 → 19322.2 | 15218.0 → 13065.4 | 0.635 → 1.479 | **NO PASA** |
| 1.2G+1.0Q+1.4EY | 3517.2 → 2846.5 | 14069.9 → 27595.5 | 27545.5 → 25605.2 | 0.511 → 1.078 | **NO PASA** |

En el muro, EY lo tracciona (P negativa): al doblar el sismo la tracción
crece, Mn **baja** (15218.0 → 13065.4) y u pasa de 0.635 a 1.479.

### Paso 5 — Unity

`semana04/exportar_unity.py` escribe `data/unity/semana04.json`
(`:713`) y lo copia a `StreamingAssets/` (`:717`). `VisorSemana04` lo lee
**una vez**, en `Start` (`VisorSemana04.cs:331`, `Cargar` en `:406`): hay
que hacer Stop + Play. Al seleccionar la barra, el panel escribe
(`VisorSemana04.Panel.cs:187` y `:190`), según `comparar_anexos.py`:

```
  COLUMNA DEMO 5  (columna P 0.70x0.70, familia 1)   D/C = u = M / Mn(P)
    ...
    panel de Unity, caso S3 (el que abre el visor):
      igual   familia 1: P 0.70x0.70 | 0.70 x 0.70 m | 20 barras | As = 98.17 cm2 | estribo E%%C12a10 | malla -
      antes   P 4860.3 kN   M 267.7 kN*m   extremo i (inferior)
      despues P 4889.6 kN   M 521.1 kN*m   extremo i (inferior)
      antes   Mn 1757.9 kN*m   u 0.152   PASA
      despues Mn 1757.7 kN*m   u 0.296   PASA

  MURO DEMO 9  (muro M 0.25x7.95, familia 2)   D/C = u = M / Mn(P)
    ...
    panel de Unity, caso EY (el mayor u con el Cs nuevo):
      igual   familia 2: M 0.25x7.95 | 0.25 x 7.95 m | 94 barras | As = 92.05 cm2 | estribo - | malla 10a20
      antes   P -479.1 kN   M 9661.1 kN*m (|Mz|, en su plano)   extremo i (inferior)
      despues P -958.2 kN   M 19322.2 kN*m (|Mz|, en su plano)   extremo i (inferior)
      antes   Mn 15218.0 kN*m   u 0.635   PASA
      despues Mn 13065.4 kN*m   u 1.479   NO PASA
```

Los textos son la emulación de `F(v, "0.0")` / `F(v, "0.000")` del panel
sobre floats; con Unity cerrado no se compararon en pantalla. Si
`d.u >= 9999` el panel escribe otro texto (`TextoFueraDeCurva`), que el
script no reproduce: ninguna de estas demandas cae fuera de la curva.

Para que el resto del visor use el mismo Cs: `python semana03/exportar_unity.py lt2 --cs 0.20`
(anexo de la Semana 3) y `python semana05/superposicion.py lt2 --cs 0.20 --exportar`
(E1..E3 precalculados, según el encabezado de ese script). `/combinar`
arma su base con `parametros.json`; su respuesta trae `parametros` y el
visor avisa si no son los de `info.parametros` del anexo
(`semana05/CONTRATO.md`, §3).

---

## Limitaciones (declaradas, no escondidas)

1. **El anexo de la Semana 4 no se recalcula en vivo.** M1 cambia la
   deformada, las fuerzas y el equilibrio que vienen de `/analizar`, pero
   no los diagramas, las combinaciones ni el P-M: al editar, el anexo
   queda marcado **desactualizado** y se apagan sus diagramas
   (`VisorSemana04.cs:527-532`). Para rehacerlo sobre un modelo editado
   habría que llevar la edición a `data/modelo/` y re-exportar.

2. **El peso propio va horneado en las cargas.** Borrar la columna 69 deja
   sus 48.51 kN aplicados como carga nodal de G (24.255 en cada extremo;
   G aplicada −34148.979 kN antes y después). Del mismo modo, cambiar la
   sección de una viga cambia su rigidez pero no su peso
   (`w = A·γ + q·A/L`, `edificios/lt2/exportar_unity.py:402`), y mover un
   nodo no recalcula áreas tributarias. El editor lo avisa al borrar una
   barra vertical.

3. **Q y el sismo de `/analizar` no son los del anexo.** `/analizar`
   resuelve los casos de `data/unity/lt2.json` (la Q del plano y el sismo
   del perfil); el anexo, los de `semana03/parametros.json`. Solo G
   coincide. De `comparar_anexos.py`:

   ```
   (max = mayor componente en mm; peor dif = mayor |u /analizar - u anexo| en m)
   caso  aplicada /analizar [Fx,Fy,Fz]    | aplicada anexo [Fx,Fy,Fz] kN       max /anal | max anexo   peor dif
   G     [    0.00,     0.00,  -34148.98] | [    0.00,     0.00,  -34148.98]     6.71145 |   6.71145   0.0e+00
   Q     [    0.00,     0.00,  -11361.00] | [    0.00,     0.00,   -7547.68]     2.90516 |   1.99078   1.0e-03
   EX    [ 3633.06,     0.00,       0.00] | [ 3792.28,     0.00,       0.00]    16.41508 |  17.15705   7.4e-04
   EY    [    0.00,  3633.06,       0.00] | [    0.00,  3792.28,       0.00]    15.25721 |  15.93481   6.8e-04
   [OK  ] G de /analizar = G del anexo (Q, EX y EY no: ver la tabla)   peor 0.0e+00 m <= 1.0e-08
   ```

   En la demo en vivo se contrasta **solo G**. La pestaña Modificar lo
   dice ("Q, EX y EY salen del modelo del visor; pueden no coincidir con
   los del anexo de la Semana 4").

4. **`max_desplazamiento` no es lo mismo en los dos lados**: en
   `/analizar` es la mayor componente (G: 6.71145 mm); en el anexo, la
   norma (G: 6.7959 mm). Los dos números son correctos.

5. **M2 necesita Stop + Play**: el anexo se lee solo en `Start`.

6. **"Guardar JSON" sirve para reenviar, no para modelar.** Escribe
   `modelo_editado.json` en `persistentDataPath` con los campos de
   `ModeloEstructural.cs` (sin enfierradura). Se reenvía con
   `python semana05/reanalisis_demo.py lt2 --desde "<ruta>/modelo_editado.json" --nodo 186`,
   que con un modelo sin la columna 69 da `elementos borrados [69]` y el
   mismo UZ186 (−21.59875 mm).

7. **El nombre del Excel depende de `?edificio=`.** Ningún exportador
   escribe `info.edificio` en `data/unity/<ed>.json`; Unity lo toma del
   anexo cargado. Un pedido sin ninguno de los dos escribe
   `results/excel/reanalisis_modelo.xlsx` (es lo que hace
   `test_reanalisis.py`, que manda el JSON crudo).

8. **Ruido en consola**: al construir el anexo, la búsqueda de curvas
   P-M hace que OpenSees imprima "failed to converge" (310 líneas en las
   dos corridas de `comparar_anexos.py`, 124 con "converge"). No cambia
   los resultados; el script las desvía y las cuenta (`--ver-avisos` las
   muestra).

9. **Alternativa no ejecutada: modificar por perfil.** Cambiar
   `edificios/lt2/perfiles/lt2_2024_22.json` y rehacer la cadena
   (`planos/extraer.py --salida data/geometria/lt2.json` → `armar.py` →
   `calcular.py` → exportadores) también es una modificación por dato,
   pero los DXF están fuera del repo, `extraer.py` escribe por defecto en
   otra ruta y cambia los números de control (G = 34 148.98 kN) y archivos
   versionados. Por eso M2 usa un parámetro de `parametros.json`.
