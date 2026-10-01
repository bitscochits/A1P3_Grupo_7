# Evidencia del iPhone

Esta carpeta está vacía hasta que la AR se pruebe en un teléfono de verdad.
Mientras no tenga capturas, `semana06/verificar_semana06.py` deja la fila
**AR** en PARCIAL, con el aviso "sin prueba en un iPhone". Se pasa sola a OK
cuando aparece aquí una captura (`.jpg`, `.png`, `.heic`, `.mp4` o `.mov`).

Qué capturar (el detalle está en `python semana06/precision_ar.py`, bloque [5]):

1. **Maqueta, captura de pantalla del iPhone.** Tiene que verse la barra
   con "imagen detectada" y el panel de `elementTag 200037` en
   `1.2G+1.0Q+1.4EX` con estos valores: P 3702.0 kN, M 510.2 kN·m,
   Mn 1721.9 kN·m, u 0.296 PASA.
2. **Focal, con una cinta.** El teléfono de frente a la imagen a 30, 50 y
   80 cm. Anotar lo que dice "pose:" en la tabla de abajo.
3. **Regla vertical (maqueta).** El techo dibujado de la columna tiene que
   quedar a 7.92 cm de la mesa.
4. **Sitio (opcional).** Primero confirmar cuál es la columna: la 200037
   está en el piso 2 según los títulos de las láminas. Después, una foto de
   la caja dibujada sobre la columna real, con cinta en sus aristas.

| distancia con cinta [cm] | "pose:" de la app [m] | razón app / cinta |
|---|---|---|
| 30 | | |
| 50 | | |
| 80 | | |

Si la razón da ≈ 1.00, la focal que supone MindAR sirve para este teléfono.
Si da ≈ 1.27 o ≈ 1.69, se confirma la fila 6 del §3 del informe.
