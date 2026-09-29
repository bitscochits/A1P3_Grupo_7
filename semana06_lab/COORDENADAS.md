# LAB Semana 6 — Las coordenadas, de OpenSees al teléfono

> Lo que el enunciado pide explicar en la defensa: coordenadas OpenSees,
> Unity y AR; escala, rotación y traslación; el anchor; qué corre en el
> teléfono y qué se calculó antes. Todo con un ejemplo real: la columna
> **200037** y sus nodos **200062** (abajo) y **200103** (arriba).

---

## 1. Los cuatro sistemas

| sistema | ejes | origen | unidades | quién lo usa |
| --- | --- | --- | --- | --- |
| **OpenSees** | `x`, `y` horizontales, **`z` arriba**; sistema **derecho** | el de los planos, calzado para el conjunto | m, kN | Python, `data/modelo/conjunto.json`, el anexo |
| **Unity** | `x`, **`y` arriba**, `z`; sistema **izquierdo** | el mismo | m | el visor de Windows (Semanas 3–5) |
| **Marcador** | `x` = derecha de la imagen, `y` = arriba de la imagen, `z` = sale de la imagen hacia quien la mira; **derecho** | el centro de la imagen | m | `exportar_ar.py` (la pose de la imagen en el edificio) |
| **Anchor de AR** | los mismos ejes del marcador | el centro de la imagen | **anchos de imagen**: 1 unidad = el ancho impreso (0.20 m) | MindAR y three.js en el teléfono |

**OpenSees → Unity** (lo que hace `VisorEstructura.cs` desde la Semana 1):
`Unity(x, y, z) = OpenSees(x, z, y)`. Se intercambian `y` y `z` para que la
vertical quede en `y`, y ese intercambio **invierte la mano**: por eso Unity
es izquierdo y OpenSees derecho. El nodo 200103, `(−2.73, 55.0833, 3.91)`
en OpenSees, está en `(−2.73, 3.91, 55.0833)` en Unity.

**OpenSees → marcador → anchor** (lo que hace este lab). La app de AR no
pasa por Unity: va directo de OpenSees al marcador, porque las dos cosas
que definen el marcador (la cara de la columna y la vertical) están en el
modelo.

---

## 2. La pose del marcador en el edificio (la calcula Python)

La imagen se pega **plana y derecha** en la cara `+x` de la columna 200037,
con su centro a 1.40 m del nodo inferior. `exportar_ar.py` escribe dónde
queda, en coordenadas de OpenSees:

- **centro** `c = (−2.38, 55.0833, 1.35)` m: el eje de la columna
  `(−2.73, 55.0833)` + medio ancho `0.35 m` hacia `+x` + la altura
  `−0.05 + 1.40`.
- **ejes**: `z = (1, 0, 0)` (la normal de la cara), `y = (0, 0, 1)` (el
  arriba del edificio), `x = y × z = (0, 1, 0)`. Ortonormales y derechos:
  `verificar_ar.py` [3a] lo comprueba.

---

## 3. La transformación: rotación, traslación y escala

Para cada punto `p` del modelo, en metros de OpenSees:

```
q = Rᵀ (p − c)                 marcador, en metros        (traslación, después rotación)
a = (escala / ancho) · q       anchor, en anchos de imagen (escala)
```

`R` tiene por columnas los ejes del marcador; `Rᵀ` los tiene por filas. En
una sola matriz de 4×4, la que arma `matrizModeloAAnchor` en `web/ar.js`:

```
M = S(k) · Rᵀ · T(−c),   k = escala / ancho_m

en sitio (escala 1, ancho 0.20 m → k = 5):
    [ 0  5  0 | −275.4165 ]      fila 1: 5·ejes.x,  −5·(ejes.x · c)
    [ 0  0  5 |   −6.7500 ]      fila 2: 5·ejes.y,  −5·(ejes.y · c)
    [ 5  0  0 |   11.9000 ]      fila 3: 5·ejes.z,  −5·(ejes.z · c)
```

- **Traslación**: `−c`, lleva el centro de la imagen al origen.
- **Rotación**: `Rᵀ`, pasa de los ejes del edificio a los de la imagen.
- **Escala**: `k`, pasa de metros a anchos de imagen, y en la maqueta
  además achica 1:50.

**Ejemplo, en sitio.** El nodo 200103 (arriba de la columna):

| | x | y | z |
| --- | --- | --- | --- |
| OpenSees (m) | −2.73 | 55.0833 | 3.91 |
| `p − c` (m) | −0.35 | 0 | 2.56 |
| marcador `q` (m) | 0 | **2.56** | **−0.35** |
| anchor `a` (anchos) | 0 | 12.8 | −1.75 |

Se lee así: el nodo queda **2.56 m sobre el centro de la imagen** y **35 cm
detrás de ella** (dentro de la columna, en su eje). Y la columna entera, de
200062 a 200103, mide `(12.8 − (−7.0)) × 0.20 m = 3.96 m`, igual que en
OpenSees: escala 1:1 (`verificar_ar.py` [3b]).

### El modo maqueta: otra rotación, otra escala

En la sala de la defensa no hay columna: la imagen va **acostada sobre la
mesa**. Ahí su normal apunta hacia arriba, así que la rotación tiene que
poner el **arriba del edificio saliendo de la imagen**: `z = (0, 0, 1)`,
`x = (0, 1, 0)` (la misma derecha), `y = z × x = (−1, 0, 0)`. El origen es la
base de la columna, `(−2.73, 55.0833, −0.05)`, y la escala es 1:50
(`k = 0.02 / 0.20 = 0.1`). El nodo 200103 queda en `(0, 0, 0.396)` anchos:
**7.9 cm sobre la imagen**, que es 3.96 m / 50.

Las dos poses son la misma idea: cambian `c`, `R` y `k`, todas escritas en
`datos/ar.json` y ninguna calculada en el teléfono.

---

## 4. El anchor y la pose de la cámara (lo hace MindAR, en el teléfono)

1. **Sesión AR**: el navegador abre la cámara trasera (`getUserMedia`).
2. **Image tracking**: en cada cuadro, MindAR busca los puntos
   característicos de la imagen, que se calcularon una vez en
   `targets.mind` (`marcador/compilar_marcador.py`).
3. **Pose**: con esos puntos y la cámara que supone (campo de visión
   vertical de 45°, focal `f = (alto/2) / tan 22.5°`), estima la matriz que
   lleva el sistema de la imagen al de la cámara.
4. **Anchor**: `mindar.addAnchor(0)` es un grupo de three.js que MindAR
   mueve con esa matriz en cada cuadro. Todo lo que se cuelga del anchor
   queda **pegado a la imagen**. El modelo cuelga del anchor con la matriz
   `M` del punto 3.

La cadena completa, del punto del edificio a la pantalla:

```
p (OpenSees, m) --M--> anchor (anchos de imagen) --pose de MindAR--> cámara --proyección--> pantalla
     Python                    ar.js                  MindAR, cada cuadro         three.js
```

La barra de arriba de la app muestra la pose: la **distancia** de la
cámara al centro de la imagen, en metros, y su **inclinación**.
`verificar_ar.py` [4] comprueba que es la verdadera: le da a la app un
video de la imagen visto desde poses conocidas y compara. Error de 1 a 3 mm
en distancia y menos de 1.1° en los ejes.

---

## 5. Qué corre en el teléfono y qué se calculó antes

| se calculó ANTES, en el PC (Python / OpenSees) | corre EN EL TELÉFONO (JavaScript) |
| --- | --- |
| El modelo del conjunto (`data/modelo/conjunto.json`) | La cámara y el image tracking (MindAR) |
| Los 15 casos resueltos en OpenSees: esfuerzos por estación, desplazamientos, reacciones | La pose de la imagen en cada cuadro |
| Las curvas P-M con fibras y la demanda de cada columna y muro | La transformación `M`: multiplicar puntos por una matriz |
| La pose de la imagen en el edificio (centro, ejes) y el sector | Dibujar: barras, diagrama escalado, deformada, áreas tributarias, etiquetas |
| La escala de la deformada | Mostrar los números del JSON en el panel y la curva P-M |
| `targets.mind`: los puntos de la imagen | Elegir el caso o la barra que se muestra |

El teléfono **no resuelve la estructura** ni interpola capacidades: todo
número estructural del panel es el del anexo de OpenSees, bit a bit
(`verificar_ar.py` [2]: 23 024 números).

---

## 6. Las fuentes de error del registro (para decirlas de frente)

- **La altura del piso.** El nodo inferior está en el eje de la losa
  (`z = −0.05`), no en el piso terminado. Entre los dos hay medio espesor de
  losa más el pavimento, unos 10 cm: en sitio, el modelo puede quedar esos
  10 cm más abajo o más arriba de lo real. Está declarado en
  `config_ar.json`.
- **El ancho impreso.** Si la impresora escala la imagen, todo sale escalado
  en la misma proporción. El PDF trae una regla de 10 cm para comprobarlo.
- **La pose de MindAR.** Con la imagen ocupando unos 200 px del cuadro, el
  error medido es de 1 a 3 mm en distancia y menos de 1.1° en orientación. A
  1:1, 1° a 3 m de la imagen son unos 5 cm en el techo del piso.
- **El modelo mismo.** La columna está en el eje que dice el plano, no en la
  obra construida.
