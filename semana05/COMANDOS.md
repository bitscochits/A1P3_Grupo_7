# Chuleta — Semana 5, en orden

Desde la carpeta del repo, en PowerShell. Todos los comandos usan el Python
del proyecto (`.\.venv\Scripts\python.exe`), que es el que tiene OpenSees,
Flask y openpyxl. Si activaste el entorno, `python` sirve igual.

Cada comando se comprobó el 17-09 contra su `--help` o, en los scripts que
no usan argparse (`superposicion.py`, `verificar_superposicion.py`,
`exportar_excel.py`, `test_excel.py`, `test_contrato_semana05.py`), contra
la lectura de su `main`. Los modos `web` y `android` del lanzador se
probaron con `--seco`.

**Regla de Unity:** una sola instancia a la vez (editor o app). La suite,
`build`, `web` y `android` abren Unity en batch y fallan si hay otro Unity
abierto.

---

## 1. Antes de empezar: la suite

```powershell
.\.venv\Scripts\python.exe comun\verificar_todo.py
```

Tiene que terminar en `41 de 41 EN OK`. El 17-09 tardó entre 131 s y 8 min con Unity
cerrado. La entrada más lenta es `excel s5` (57.8 s) y la única que abre
Unity es `JsonUtility real s4` (12.4 s). Sin las entradas lentas:

```powershell
.\.venv\Scripts\python.exe comun\verificar_todo.py --rapido
```

Al terminar dice `(la suite dejo semana04.json en 'lt2' ...)`. Es lo que
se busca: la demo es del LT2.

## 2. Los anexos del LT2 en Unity

```powershell
.\.venv\Scripts\python.exe semana04\exportar_unity.py lt2
.\.venv\Scripts\python.exe semana03\exportar_unity.py lt2
.\.venv\Scripts\python.exe comun\lanzar_unity.py sincronizar lt2
```

`sincronizar` solo copia: modelo, anexos 3 y 4, superposición, carga móvil
y Excel, a `unity\Assets\StreamingAssets` y a
`build\LaboratorioEstructural_Data\StreamingAssets`. Nunca abre Unity. Con
todo al día termina en `resumen: igual 12`. Para ver qué copiaría sin
escribir, agrega `--seco`.

Abrir la app (sincroniza antes de abrir):

```powershell
.\.venv\Scripts\python.exe comun\lanzar_unity.py app lt2
.\.venv\Scripts\python.exe comun\lanzar_unity.py app lt2 --pantalla-completa
```

Para trabajar en el visor, en vez de la app: `comun\lanzar_unity.py editor lt2` y Play.

## 3. El servidor de la Semana 5 (terminal aparte)

```powershell
.\.venv\Scripts\python.exe semana05\servidor_s5.py
```

Puerto 5000, solo este equipo. Trae `/ping`, `/analizar`, `/combinar` y
`/estados`. Al arrancar arma en segundo plano la base del LT2, que toma
unos 2 s. Opciones: `--lan` (red local, para un teléfono), `--puerto N`,
`--sin-precalentar`, y cualquier flag de `semana03/parametros.py` (por
ejemplo `--cs 0.20`). `comun\lanzar_unity.py servidor` levanta este mismo
script.

Comprobar que está vivo, desde otra terminal:

```powershell
Invoke-RestMethod http://localhost:5000/ping          # estado: vivo
```

Se cierra con Ctrl+C en su terminal.

## 4. M1: borrar la columna 69 y reanalizar

En la app, con el servidor prendido: "Ir a ID" `69` → "Elemento" → pestaña
**Modificar** → "Borrar barra  (Supr)" → "Recalcular en el servidor
(Enter)". Detalle en [`MODIFICACIONES.md`](MODIFICACIONES.md).

Lo mismo desde Python, sin Unity y sin escribir en `data/`:

```powershell
.\.venv\Scripts\python.exe semana05\reanalisis_demo.py lt2 --borrar-elemento 69 --nodo 186 --elemento 337
```

Termina en `TODO OK`. En G, el UZ del nodo 186 pasa de −3.64515 a
−21.59875 mm, y el panel escribe `"UZ -21.5988 mm"`.

Contra el servidor vivo, mandando el modelo en float32 como lo manda
JsonUtility:

```powershell
.\.venv\Scripts\python.exe semana05\reanalisis_demo.py lt2 --borrar-elemento 69 --nodo 186 --float32 --url http://localhost:5000/analizar
```

El servidor deja `results\excel\reanalisis_lt2.xlsx` (botón "Abrir Excel
de este reanalisis").

## 5. M2: coeficiente sísmico 0.20, y volver a la base

Ver el efecto antes, sin escribir nada (4.7 s en la suite):

```powershell
.\.venv\Scripts\python.exe semana05\comparar_anexos.py lt2 --cs 0.20
```

Aplicarlo. Los tres anexos llevan el **mismo** `--cs`: si la superposición
queda con otro, el visor avisa que sus parámetros no son los de
`semana04.json`.

```powershell
.\.venv\Scripts\python.exe semana04\exportar_unity.py lt2 --cs 0.20
.\.venv\Scripts\python.exe semana03\exportar_unity.py lt2 --cs 0.20
.\.venv\Scripts\python.exe semana05\superposicion.py lt2 --cs 0.20 --exportar
.\.venv\Scripts\python.exe comun\lanzar_unity.py app lt2        # cerrar la app antes: lee los JSON al arrancar
```

Si se va a usar LIBRE, hay que reiniciar el servidor con el mismo dato:
`semana05\servidor_s5.py --cs 0.20`.

**Volver a la base** al terminar (sin flags = `semana03/parametros.json`):

```powershell
.\.venv\Scripts\python.exe semana04\exportar_unity.py lt2
.\.venv\Scripts\python.exe semana03\exportar_unity.py lt2
.\.venv\Scripts\python.exe semana05\superposicion.py lt2 --exportar
.\.venv\Scripts\python.exe comun\lanzar_unity.py sincronizar lt2 --seco
```

El `--seco` imprime el md5 de origen de cada archivo. Los de la entrega
(17-09) son: `semana04.json` 7ad6a421…, `semana03.json` e48189e8… y
`superposicion.json` 48153dfd…. Si alguno no coincide, `git diff --stat
data/unity` dice cuál cambió. Después, `sincronizar lt2` sin `--seco` y
servidor sin `--cs`.

No regeneres el Excel con `--cs 0.20`: `data/excel/` va a git, y el script
avisa si el libro no usa los parámetros de la entrega.

## 6. Superposición

```powershell
.\.venv\Scripts\python.exe semana05\superposicion.py lt2                        # E1..E3 en pantalla
.\.venv\Scripts\python.exe semana05\superposicion.py lt2 --lambdas 0.9 0 -1.4 0 # cualquier juego G Q EX EY
.\.venv\Scripts\python.exe semana05\superposicion.py lt2 --exportar             # escribe el precalculado y su copia
```

Cómo se sabe que está bien:

```powershell
.\.venv\Scripts\python.exe semana05\verificar_superposicion.py lt2      # 4 vias contra la corrida explicita (5.6 s)
.\.venv\Scripts\python.exe semana05\verificar_superposicion.py ingenieria
.\.venv\Scripts\python.exe semana05\test_contrato_semana05.py           # JSON y /combinar contra el C# (181 OK)
```

En la app: **Caso** → "Superposicion (Semana 5)" → E1, E2 o E3 (sin
servidor). En "Factores libres (servidor Python)", "Conectar (GET
/estados)" y después mover los sliders o apretar "Combinar en Python".

## 7. Excel: generar y abrir

```powershell
.\.venv\Scripts\python.exe semana05\exportar_excel.py lt2                     # data\excel\lt2_resultados.xlsx
.\.venv\Scripts\python.exe semana05\exportar_excel.py lt2 ingenieria conjunto # los tres
.\.venv\Scripts\python.exe semana05\test_excel.py lt2                         # celda a celda contra la fuente
.\.venv\Scripts\python.exe comun\lanzar_unity.py sincronizar lt2               # copia a StreamingAssets\resultados.xlsx
Invoke-Item data\excel\lt2_resultados.xlsx                                     # abrirlo desde Windows
```

`test_excel.py lt2 ingenieria conjunto` tardó 57.8 s en la suite. Si Excel
tiene el libro abierto, el exportador no puede reemplazarlo y lo dice:
ciérralo primero. En la app, el botón azul "Abrir Excel de resultados"
de la cabecera abre `StreamingAssets\resultados.xlsx`.

## 8. Carga móvil

```powershell
.\.venv\Scripts\python.exe semana05\carga_movil.py lt2 --no-escribir   # verifica las 30 posiciones, no escribe (1.1 s)
.\.venv\Scripts\python.exe semana05\carga_movil.py lt2                 # escribe data\unity\carga_movil_lt2.json y la copia
.\.venv\Scripts\python.exe comun\lanzar_unity.py sincronizar lt2
```

Opciones: `--P 50` (kN, por defecto 100) y `--divisiones 3` (posiciones
por viga, por defecto 5). En la app: pestaña **Carga movil** → "Mostrar la
carga movil".

## 9. Capturas de la Semana 5 y comparación con Python

Con la app **cerrada** y el servidor prendido. Si no, LIBRE y M1 quedan
como no hechas. La captura usa la build que exista. Si cambiaste C#,
primero haz el paso 10.

```powershell
$srv = Start-Process .\.venv\Scripts\python.exe -ArgumentList 'semana05\servidor_s5.py' -WorkingDirectory $PWD -PassThru
do { Start-Sleep 1 } until (try { (Invoke-RestMethod http://localhost:5000/ping).estado -eq 'vivo' } catch { $false })
$app = Start-Process .\build\LaboratorioEstructural.exe -WorkingDirectory $PWD -Wait -PassThru `
       -ArgumentList '-capturarS5','semana05\capturas','-screen-width','1600','-screen-height','900','-screen-fullscreen','0'
$app.ExitCode                      # 0 = termino bien; 2 = excepcion (queda escrita en registro.txt)
Stop-Process -Id $srv.Id           # no dejar el servidor corriendo
.\.venv\Scripts\python.exe semana05\comparar_unity.py semana05\capturas\registro.txt --salida semana05\evidencia\unity_vs_python.txt
```

La carpeta de capturas es relativa al directorio de trabajo del exe, por
eso va `-WorkingDirectory $PWD`. El resultado del 17-09 fueron 23 fotos,
`log.errores = 0` y, en la comparación, 144 + 146 + 97 + 58 + 41 = 486
filas, 0 FALLA, `TODO CALZA`. Si la captura se hizo sin servidor, agrega
`--sin-servidor` a `comparar_unity.py`.

Regresión de la Semana 4 con la misma build: `-capturarS4 <carpeta>` y
comparar su `registro.txt` con uno anterior **del mismo edificio**. Tiene
que salir idéntico. El de `semana04\capturas\` es de Ingeniería, así que
antes hay que hacer `build ingenieria --forzar`. El 17-09, con el LT2,
salieron 151 líneas idénticas.

## 10. Build de Windows

Con Unity y la app cerrados:

```powershell
.\.venv\Scripts\python.exe semana05\compilar_unity.py                  # 0 errores en los dos ensamblados, sin abrir Unity
.\.venv\Scripts\python.exe comun\lanzar_unity.py build lt2 --forzar     # build\LaboratorioEstructural.exe
```

La última build del 17-09 tardó 34 s (`BUILD OK`). El log queda en
`build\unity_build.log`. Sin `--forzar`, si la app ya existe no recompila.
Sin edificio, `build` sincroniza el LT2 antes de compilar. Para compilar
con otro edificio en StreamingAssets, hay que nombrarlo (`build ingenieria
--forzar`).

Web y Android (no se hicieron, ver [`MOVIL.md`](MOVIL.md)):

```powershell
.\.venv\Scripts\python.exe comun\lanzar_unity.py web lt2 --seco        # dice que haria: build\web\index.html
.\.venv\Scripts\python.exe comun\lanzar_unity.py android lt2 --seco    # hoy: ERROR falta PlaybackEngines/AndroidPlayer, sale con 1
```

---

## En la app

| pestaña | lo principal |
| --- | --- |
| cabecera | edificio, caso activo, "Desp. max", "PASAN 69/69" o "NO PASA n/m (k fuera de curva)", selección con Ver / Centrar / x, "Abrir Excel de resultados", "Ocultar (H)" |
| **Vista** | Realista \| Tecnica, "Perfiles reales (b x h) en la tecnica", "Losas", "Suelo donde apoya el edificio", cámara (F, Planta, Elev. X, Elev. Y, Iso), filtro de piso, tamaño del texto y equipo |
| **Capas** | estructura (nodos, columnas, vigas, muros, brazos, perfiles, losas), control de calidad (áreas tributarias, apoyos por tipo, diafragmas, ejes locales), Semana 3 (cargas y enfierradura) |
| **Caso** | deformada (escala x1…x1000), casos del anexo (Semana 4), Superposicion (Semana 5), Diagramas, Curva P-M, "Columna demo (5)" y "Muro demo (9)", Mapa demanda / capacidad, Criticos del caso activo |
| **Elemento** | "Ir a ID" + Elemento / Nodo, "Centrar (C)", "Su piso" / "Todos los pisos", "Soltar (Esc)" y las secciones del inspector |
| **Modificar** | URL del servidor, "Recalcular en el servidor  (Enter)", G / Q / EX / EY del reanálisis, equilibrio, "Abrir Excel de este reanalisis", Seleccion, Crear y guardar |
| **Carga movil** | "Mostrar la carga movil", posición (slider, \|< < Play > >\|), "Donde esta la carga", "Reparto a los extremos de la viga", conservación y respuesta |

Teclas: F encuadrar, C centrar la selección, Esc soltar, H ocultar el
panel. En Modificar: Supr borrar, Enter recalcular.
