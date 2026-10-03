# Semana 6 — AVANCE: validación AR y cierre técnico

El informe es [`reports/semana06.md`](../reports/semana06.md). En esta
carpeta están los tres scripts que producen sus números y la evidencia que
dejan. El LAB de la semana, la app de AR, está en
[`semana06_lab/`](../semana06_lab/).

El edificio es el **conjunto**: los dos cuerpos en un solo modelo,
`data/modelo/conjunto.json`, con 558 nodos y 937 elementos. El elemento de
la AR es la **columna 200037**.

| script | punto del informe | qué hace | tarda |
|---|---|---|---|
| [`verificar_semana06.py`](verificar_semana06.py) | §5 QA final | Corre en vivo las diez filas de la tabla (equilibrio G y Q, corte basal EX y EY, superposición, M-phi, P-M de columna y de muro, IDs Unity y AR). Cada fila tiene su criterio escrito en el código. Termina con código 1 si una fila da FALLA | 6 s |
| [`traza_200037.py`](traza_200037.py) | §4 Resultados | Sigue la columna 200037 desde la lámina 2024_22-101 y la elevación 305: calce, OpenSees resuelto sin redondeo, lo que trae la app y lo que escribe el panel del teléfono | 3 s |
| [`proyeccion_terreno.py`](proyeccion_terreno.py) | §3.1 y §4.1 | Dibuja el modelo del conjunto sobre la foto real de la viga 100164 con la cámara que se ajusta de esa foto (PnP), y comprueba que el nodo 100359, que no entra al ajuste, caiga en su columna (7.3 px = 2.4 cm). Con `--salida` deja la imagen y el texto en `evidencia/terreno/` | 2 s |
| [`precision_ar.py`](precision_ar.py) | §3 Precisión | Arma el presupuesto de error del registro, en sitio y en maqueta. Estima el error de la focal supuesta y describe la prueba a hacer en el iPhone. El error del tracking lo lee de `evidencia/verificar_ar.txt` | 2 s |

```powershell
python semana06\verificar_semana06.py                 # la tabla del §5
python semana06\verificar_semana06.py --ar-completo   # con el tracking de la AR en Chrome
python semana06\traza_200037.py                       # el §4
python semana06\precision_ar.py                       # el §3
python semana06\precision_ar.py --medir               # vuelve a medir el tracking (Chrome, 30 s)
python semana06\proyeccion_terreno.py --salida        # el §4.1: la viga 100164 sobre la foto real
```

Con `--salida`, cada script deja su evidencia en [`evidencia/`](evidencia/):
`qa_semana06.md`, `traza_200037.txt`, `precision_ar.txt` y `terreno/`. Los cuatro corren
en la suite (`python comun\verificar_todo.py`) sin `--salida`, así que la
suite no escribe evidencia.

**Estados de la tabla.**

- **OK**: la prueba corrió y cumple su criterio.
- **PARCIAL**: cumple lo que se puede comprobar, pero hay algo abierto que
  la misma prueba mide. Hoy es una fila (antes eran dos):
  - **P-M muro**: el mallado de 20 fibras no alcanza en muros largos, y la
    curva cerca de P = 0 incluye el endurecimiento del acero.
  - **AR**: estuvo en PARCIAL hasta el 02-10, por falta de una prueba en
    un iPhone. Pasó sola a OK al aparecer la captura del teléfono en
    [`evidencia/iphone/`](evidencia/iphone/LEEME.md).

  Cuando se arregle lo que falta, la fila de P-M muro pasa sola a OK.
- **FALLA**: no cumple.

**Requisitos.** Los de `requirements.txt`. `precision_ar.py --medir` y
`verificar_semana06.py --ar-completo` necesitan además Chrome o Edge y
Pillow. Pillow llega como dependencia de matplotlib.
