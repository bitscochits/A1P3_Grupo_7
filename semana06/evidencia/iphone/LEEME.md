# Evidencia del iPhone

`semana06/verificar_semana06.py` deja la fila **AR** en PARCIAL mientras
esta carpeta no tenga capturas, y la pasa sola a OK cuando aparece una
(`.jpg`, `.png`, `.heic`, `.mp4` o `.mov`).

## Lo que hay (prueba del 30-09, Safari en un iPhone del grupo)

| archivo | qué muestra | qué NO muestra |
|---|---|---|
| `01_iphone_safari_imagen_detectada_200037.jpg` | Captura de pantalla **del teléfono**: Safari con la app servida por `servir.py` ("No seguro": el certificado lo firma el PC), la barra en verde **"imagen detectada"** con la pose estimada (**1.01 m, inclinación 30°**) y el panel con **`elementTag 200037 · columna lt2:P 0.70x0.70`**. El sector de la columna aparece encima del marcador, con los tags de las barras del sector | El marcador estaba en la **pantalla del notebook**, de pie, y no impreso sobre una mesa. Por eso el sector se ve en planta (el modo maqueta supone la imagen acostada) y la pose de 1.01 m no es la real: la pantalla no mide 20 cm. Sirve como prueba de sesión AR, detección, anchor y tag en el teléfono, **no** como medición de error. El panel está plegado: no se ven P, M, Mn ni u |

Ese mismo día, en el **edificio**, se probó en el teléfono, en modo
*sitio*, la viga **100161** con una foto de su fondo como imagen de
referencia (`config_ar_viga_100161.json`). La app la reconoció, y ahí se
probó el **calce a mano**. De esa prueba no se guardó una captura
de pantalla. La foto de la viga 100164 y el modelo dibujado encima con la
cámara ajustada están en [`../terreno/`](../terreno/).

## Lo que falta capturar

1. **Maqueta, captura de pantalla del iPhone**, con el marcador **impreso
   y acostado** sobre la mesa: la barra con "imagen detectada" y el panel
   de `elementTag 200037` **desplegado** en `1.2G+1.0Q+1.4EX`. Tiene que
   mostrar P 3701.8 kN, M 507.6 kN·m, Mn 1721.9 kN·m y u 0.295 PASA (los de
   `python semana06/traza_200037.py`, bloque [5]).
2. **En sitio, captura de pantalla** con la viga 100164 o la 100161 sobre
   la real (elegir el elemento en la pantalla de inicio de la app).
3. **Focal, con una cinta.** El teléfono de frente al marcador impreso, a
   30, 50 y 80 cm. Anotar lo que dice "pose:" en la tabla de abajo.
4. **Regla vertical (maqueta).** El techo dibujado de la columna tiene que
   quedar a 7.92 cm de la mesa.

| distancia con cinta [cm] | "pose:" de la app [m] | razón app / cinta |
|---|---|---|
| 30 | | |
| 50 | | |
| 80 | | |

Si la razón da ≈ 1.00, la focal que supone MindAR sirve para este teléfono.
Si da ≈ 1.27 o ≈ 1.69, se confirma la fila 7 del §3 del informe.
