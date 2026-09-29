# Semana 6 — LAB: AR básica

**Objetivo del enunciado:** relacionar el modelo analítico con un elemento
físico del edificio. Esta carpeta es la entrega completa: una app de
realidad aumentada que corre en el **Safari del iPhone**, reconoce una
imagen pegada en una columna real del Edificio de Ingeniería y muestra
encima esa columna y su sector, con **el mismo elementTag de OpenSees** y
sus **resultados de OpenSees**.

El edificio es el **conjunto** (los dos cuerpos en un solo modelo,
`data/modelo/conjunto.json`). El elemento es la **columna 200037**: la del
primer piso del eje C del cuerpo LT2, `lt2:P 0.70x0.70`, de −0.05 a 3.91 m.

![La app, en modo maqueta](capturas/01_maqueta_vertical_columna_200037.png)

*La app con la cámara viendo la imagen a 42 cm y 35° de inclinación (video
sintético, ver [4] abajo). Arriba: "imagen detectada" y la pose estimada,
que es la verdadera. La columna 200037 en naranjo, parada sobre la imagen a
escala 1:50, con su diagrama de momento; las vigas del sector con sus tags.
Abajo, los números de OpenSees para `1.2G+1.0Q+1.4EX`.*

---

## Por qué es AR web y no una app de Unity

Los tres integrantes tienen **iPhone** y el grupo **no tiene Mac**. La AR
de Unity (AR Foundation con ARKit) exige compilar una app nativa de iOS en
Xcode, que solo existe en macOS. El camino que sí funciona es **AR en el
navegador**: [MindAR](https://github.com/hiukim/mind-ar-js) hace el image
tracking con la cámara del teléfono y [three.js](https://threejs.org) dibuja.
Las dos librerías van copiadas en `web/vendor/` (con sus licencias MIT), así
que la demo no depende de internet.

La regla de oro no cambia: **Python/OpenSees calcula, el JSON transporta, el
teléfono muestra.** El teléfono solo transforma coordenadas y dibuja.

---

## Dónde está cada criterio

| criterio | pts | qué se muestra | cómo se sabe que está bien |
| --- | :---: | --- | --- |
| **Image tracking** | 2 | La app abre la cámara (sesión AR), reconoce la imagen impresa y lo dice: *"imagen detectada"*. Al taparla: *"buscando la imagen…"*. | `verificar_ar.py` [4]: un video sintético de la imagen, desde tres poses conocidas, dado a Chrome como si fuera la cámara. La app la detecta en las tres. |
| **Registro espacial** | 2 | La **pose** en la barra de arriba (distancia y inclinación de la cámara); el modelo cuelga del **anchor** con la matriz `M` = rotación · traslación · escala. Dos modos: *en sitio* 1:1 con la imagen en la columna, *maqueta* 1:50 con la imagen en la mesa. | [3a] la pose de la imagen en el edificio (ejes ortonormales y derechos, en la cara de la columna, a la altura declarada). [3b] la transformación de `ar.js` = la de Python a 1e-14, y la columna mide 3.960 m a 1:1 y 7.9 cm a 1:50. [4] la pose estimada: 1–3 mm y < 1.1° de error. |
| **Elemento / ID correcto** | 2 | El panel dice `elementTag 200037` y la línea de OpenSees `element elasticBeamColumn 200037 200062 200103 …`. Tocar una barra la selecciona y muestra la suya. | [1] los 21 elementos y 22 nodos de la app tienen el mismo tag, nodos, tipo, sección y coordenadas que el modelo; la línea de OpenSees del anexo nombra el mismo tag y los mismos nodos. |
| **Resultado estructural** | 2 | Para el caso elegido (los 15 de OpenSees): N, V, T, M en los dos extremos; desplazamientos; **curva P-M** con el punto de demanda, Mn, u y PASA / NO PASA; el **diagrama** de la magnitud elegida sobre las barras; la **deformada**; las **áreas tributarias**. | [2] 23 024 números de la app idénticos bit a bit al anexo de OpenSees. |
| **Defensa individual** | 2 | [`COORDENADAS.md`](COORDENADAS.md): los cuatro sistemas, la matriz con un ejemplo numérico, el anchor, qué corre en el teléfono y qué se calculó antes, y las fuentes de error. [`GUION_DEMO.md`](GUION_DEMO.md): la demo en orden. | — |

El resultado de `verificar_ar.py`, completo:

```
[1] 21 elementos y 22 nodos con el mismo tag que OpenSees ............. OK
[2] 23 024 números idénticos al anexo de OpenSees ...................... OK
[3] pose del marcador y transformación ar.js = Python (2.8e-14) ....... OK
[4] d = 0.45 m, 0°:        detecta; distancia 0.451 m, ejes a 1.1° ..... OK
    d = 0.55 m, 30°:       detecta; distancia 0.551 m, ejes a 0.7° ..... OK
    d = 0.60 m, 40° + 20°: detecta; distancia 0.597 m, ejes a 0.9° ..... OK
```

---

## El enunciado, punto por punto

La tabla de arriba sigue la rúbrica. Esta sigue la **lista del
enunciado**, para quien tenga que contestar "¿dónde hace X?" delante del
profesor. Las funciones son de `web/ar.js`.

| # | requisito | dónde, en el código | qué se ve en el teléfono |
| --- | --- | --- | --- |
| 1 | iniciar sesión AR | `iniciar(modo)`: `new MindARThree({...})` y `mindar.start()`, que abre la cámara trasera (`getUserMedia`) | Safari pide la cámara; se ve el video |
| 2 | detectar una imagen de referencia | `imageTargetSrc: 'targets.mind'` (los puntos de `marcador.png`, compilados en el PC); `anchor.onTargetFound` / `onTargetLost` | *"imagen detectada"* en verde; *"buscando la imagen…"* al taparla |
| 3 | obtener pose | MindAR estima en cada cuadro la matriz imagen → cámara; el ciclo de `setAnimationLoop` la lee de `anchor.group.matrix` y la pasa a metros | *"pose: 0.42 m, inclinación 35°"* cambia al mover el teléfono |
| 4 | crear / usar anchor | `mindar.addAnchor(0)` y `anchor.group.add(modelo)`: el modelo queda colgado del sistema de la imagen | el modelo se queda pegado a la imagen al moverse |
| 5 | transformar coordenadas del modelo | `matrizModeloAAnchor(pose, escala, ancho)`: `M = S(k) · Rᵀ · T(−c)`, con `c` y `R` calculados en `exportar_ar.py` | la columna parada sobre la imagen, a 1:50 (maqueta) o 1:1 (en sitio) |
| 6 | mostrar un elemento o sector | `construirBarras()`: la columna 200037 y las 20 barras del sector (radio 6 m, `config_ar.json`) | la columna en naranjo, las vigas y sus tags |
| 7 | mantener el mismo `elementTag` | los tags viajan tal cual del modelo a `datos/ar.json`; `actualizarPanel()` los rotula y muestra la línea `element elasticBeamColumn 200037 …` del anexo | *"elementTag 200037 · columna lt2:P 0.70x0.70"* |
| 8 | mostrar un resultado de OpenSees | `actualizarPanel()` y `dibujarPM()`: `P`, `V`, `M`, `T`, desplazamientos, curva P-M con el punto de demanda, área tributaria; `construirDiagramas()` y `construirDeformada()` | los números del caso elegido, el diagrama sobre las barras y la P-M |

Y los temas de la defensa, en [`COORDENADAS.md`](COORDENADAS.md):

| tema | sección |
| --- | --- |
| coordenadas OpenSees, Unity y AR | §1 (tabla de los cuatro sistemas y `Unity(x, y, z) = OpenSees(x, z, y)`) |
| escala, rotación y traslación | §3 (la matriz `M` con el nodo 200103 como ejemplo, en sitio y en maqueta) |
| anchor | §4 |
| qué corre en el teléfono y qué se calculó antes | §5 |

---

## Los archivos

| archivo | qué es | corre en |
| --- | --- | --- |
| `config_ar.json` | **El único archivo que se toca**: qué columna, en qué cara, a qué altura, de qué ancho se imprime, el radio del sector. | — |
| `exportar_ar.py` | Toma el modelo y el anexo de OpenSees, calcula la pose de la imagen en el edificio y el sector, y escribe `web/datos/ar.json`. | PC (Python) |
| `marcador/generar_marcador.py` | La imagen de referencia y el PDF para imprimirla a 20.0 cm exactos, con una regla de control. | PC |
| `marcador/compilar_marcador.py` | `marcador.png` → `web/targets.mind` (los puntos característicos que busca MindAR). | PC (Chrome sin ventana) |
| `servir.py` | Sirve la app por **https** a la red local (Safari exige https para la cámara), con un certificado que genera para la IP del PC. | PC |
| `web/index.html`, `web/ar.js`, `web/estilo.css` | **La app**: sesión AR, tracking, pose, anchor, transformación y dibujo. | **teléfono** |
| `web/datos/ar.json` | El sector y sus resultados, en coordenadas de OpenSees. | lo lee el teléfono |
| `verificar_ar.py` | Los cuatro bloques de arriba. | PC |
| `COORDENADAS.md`, `GUION_DEMO.md` | La defensa. | — |

---

## Cómo se usa

```powershell
.\.venv\Scripts\python.exe semana06_lab\exportar_ar.py                 # si se cambia config_ar.json
.\.venv\Scripts\python.exe semana06_lab\servir.py                      # deja la terminal abierta
```

El servidor imprime la dirección, por ejemplo `https://192.168.1.13:8443`.
En el iPhone, conectado al **mismo WiFi**:

1. Abrir esa dirección en **Safari**.
2. Safari avisa *"Esta conexión no es privada"*: el certificado lo firmó el
   PC, no una autoridad. **Mostrar detalles → visitar este sitio web**.
3. Elegir **Maqueta** (imagen sobre la mesa) o **En sitio** (imagen en la
   columna) y **permitir la cámara**.
4. Apuntar a la imagen impresa (`marcador/marcador_imprimir.pdf`, al 100 %).

Para cambiar de columna: editar `config_ar.json`, y correr
`exportar_ar.py`, `marcador/generar_marcador.py` (el rótulo cambia) y
`marcador/compilar_marcador.py`.

---

## Lo que queda corto, dicho de frente

- **No se probó todavía en un iPhone.** Todo lo de arriba corre en Chrome de
  escritorio con una cámara sintética. El iPhone usa Safari (WebKit), y el
  primer ensayo en el teléfono es lo que falta. Si Safari no deja la cámara
  con el certificado del PC, el plan B es publicar `web/` en un sitio https
  de verdad (GitHub Pages).
- **La deformada va recta entre nodos** (cada barra es una cuerda). El visor
  de Windows la dibuja curva con las funciones de forma; en AR, con un sector
  chico y a 1:50, la diferencia no se ve.
- **El registro vertical en sitio tiene ~10 cm de incertidumbre**: el nodo
  está en el eje de la losa, no en el piso terminado (`COORDENADAS.md` §6).
- **El sismo del conjunto se reparte entre los dos cuerpos.** El sismo
  pseudoestático del anexo (`semana03/lab_semana03.armar_casos`) calcula
  **un** corte basal `Cs · ΣW` para todo el conjunto y lo reparte en altura
  sobre los niveles de los dos cuerpos, midiendo las alturas desde la base
  más baja. Con la junta libre, cada cuerpo debería llevar su propio
  `Cs · W`. Para la columna 200037, medido el 29-09: `My` sísmico **2.1 %**
  mayor que en el LT2 solo, y en `1.2G+1.0Q+1.4EX` `u = 0.295` contra
  `0.290`. No cambia ningún PASA, pero explica por qué la misma columna da
  números un poco distintos en el visor del LT2 y en esta app. Los
  resultados de `data/resultados/` (los de `comun/sismo.py`) **sí** dan
  cada cuerpo igual que solo: lo comprueba `verificar_conjunto.py`.
- **Datos rehechos el 29-09** con las vigas de Ingeniería en `V 0.60x0.80`
  (las del LT2, corroboradas en plano y terreno). La columna es del LT2,
  así que sus números cambian poco, y solo por el reparto del punto
  anterior: `M` 510 → 508 kN·m, `u` 0.296 → 0.295. La escala de la
  deformada pasó de ×110 a ×160, porque el conjunto entero se deforma
  menos. `verificar_ar.py` pasa entero con los datos nuevos.
