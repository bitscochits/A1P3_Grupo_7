# LAB Semana 6 — Guion de la demostración

Unos **8 minutos**, en el orden de la rúbrica. La demo en la sala es en
modo **maqueta** (la imagen sobre la mesa); si el profesor quiere verla en
la columna real, es el mismo flujo con **En sitio**.

---

## Antes (10 min)

1. **Imprimir** `marcador/marcador_imprimir.pdf` al 100 % y **medir** la
   imagen: tiene que tener 20.0 cm de ancho (la regla del PDF mide 10 cm).
   Si mide otra cosa, poner ese ancho en `config_ar.json` y correr
   `exportar_ar.py`.
2. En el PC:
   ```powershell
   .\.venv\Scripts\python.exe semana06_lab\verificar_ar.py      # tiene que terminar en "...BIEN REGISTRADOS"
   .\.venv\Scripts\python.exe semana06_lab\servir.py            # dejarla abierta
   ```
3. En el iPhone, **mismo WiFi**: Safari → `https://<IP que imprime>:8443` →
   *Mostrar detalles → visitar este sitio web* → **Maqueta** → permitir la
   cámara. Probar que detecta la imagen.

---

## 1. Image tracking — 2 pts (1.5 min)

**Qué hacer:** apuntar a la imagen. Taparla con la mano. Destaparla.

**Qué se ve:** *"buscando la imagen…"* → *"imagen detectada"* en verde, y
el modelo aparece pegado a la imagen. Al taparla, desaparece.

> "La app abre una sesión AR: la cámara trasera del teléfono. MindAR busca
> en cada cuadro los puntos característicos de esta imagen, que se
> calcularon una vez en el PC (`targets.mind`). Cuando los encuentra,
> estima la pose."

---

## 2. Registro espacial — 2 pts (2 min)

**Qué hacer:** acercar, alejar e inclinar el teléfono. Mostrar la barra de
arriba.

**Qué se ve:** *"pose: 0.42 m, inclinación 35°"* cambia con el teléfono, y
el modelo se queda **fijo sobre la imagen**, de pie sobre ella.

> "La pose es la matriz que lleva el sistema de la imagen al de la cámara:
> la estima MindAR en cada cuadro. El modelo cuelga del anchor, que es ese
> sistema, con una segunda matriz que armamos nosotros: `M = escala ·
> rotación · traslación`. La traslación lleva la base de la columna al
> centro de la imagen; la rotación pone el arriba del edificio saliendo de
> la imagen; la escala pasa de metros a anchos de imagen y achica 1:50. La
> columna mide 3.96 m en OpenSees y acá 7.9 cm."

**Si preguntan por las coordenadas:** OpenSees tiene `z` arriba y es
derecho; Unity tiene `y` arriba y es izquierdo, `Unity(x, y, z) =
OpenSees(x, z, y)`; el anchor tiene su origen en el centro de la imagen y
mide en anchos de imagen. El ejemplo numérico con el nodo 200103 está en
[`COORDENADAS.md`](COORDENADAS.md) §3.

---

## 3. Elemento / ID correcto — 2 pts (1.5 min)

**Qué hacer:** mostrar el panel. Tocar una viga. Volver a tocar la columna.

**Qué se ve:** *"elementTag 200037 · columna lt2:P 0.70x0.70"* y la línea
`element elasticBeamColumn 200037 200062 200103 A=0.4900 …`. Al tocar una
viga, su tag (por ejemplo 200206) se pone celeste y el panel pasa a ella.

> "El tag es el mismo en el modelo, en OpenSees y en el teléfono: 200037,
> con sus nodos 200062 y 200103. La línea de abajo es literalmente la orden
> de OpenSees con que se creó el elemento. Lo comprueba verificar_ar.py
> para los 21 elementos y 22 nodos del sector."

---

## 4. Resultado estructural — 2 pts (2 min)

**Qué hacer:** elegir `1.2G+1.0Q+1.4EX`. Cambiar el diagrama a `My`.
Prender la deformada. Bajar a la curva P-M. Cambiar a `0.9G+1.4EX`.

**Qué se ve:** N = −3702 kN, My = −499 / 482 kN·m, el punto de demanda en
la curva P-M: P = 3702 kN, M = 508 kN·m, Mn = 1722 kN·m, **u = 0.295,
PASA**. El diagrama de momento sobre la columna y las vigas.

> "Todos estos números los calculó OpenSees en el PC: son los del anexo de
> la Semana 4, bit a bit. El teléfono no resuelve nada: los lee del JSON y
> los dibuja. La curva P-M la calculó Python con una sección de fibras."

---

## 5. Defensa individual — 2 pts

Cualquiera de los tres tiene que poder contestar:

| pregunta | respuesta corta |
| --- | --- |
| ¿Qué corre en el teléfono? | La cámara, el tracking, la pose, la matriz `M` y el dibujo. Nada estructural. |
| ¿Qué se calculó antes? | El modelo, los 15 casos en OpenSees, las curvas P-M, la pose de la imagen en el edificio, el sector y `targets.mind`. |
| ¿Qué es el anchor? | El sistema de coordenadas de la imagen, que MindAR mueve en cada cuadro con la pose. Todo lo que cuelga de él queda pegado a la imagen. |
| ¿Por qué es web y no Unity? | Tenemos iPhone y no Mac: la AR de Unity en iOS exige compilar en Xcode. En el navegador, MindAR hace lo mismo. |
| ¿Cómo sabe dónde está la columna? | La imagen se pega en su cara `+x` a 1.40 m. Python calcula dónde queda eso en el modelo: centro `(−2.38, 55.08, 1.35)` y ejes. |
| ¿Qué error tiene? | La pose: 1–3 mm y < 1.1° (medido con video sintético). En sitio, ~10 cm vertical por el nivel del nodo (eje de losa, no piso). |

---

## Si algo sale mal

| síntoma | qué hacer |
| --- | --- |
| Safari no abre la página | mismo WiFi que el PC; la dirección con **https** y el puerto **8443** |
| no pide la cámara / pantalla negra | Ajustes → Safari → Cámara → Permitir; recargar |
| no detecta la imagen | más luz, sin reflejos, que la imagen ocupe al menos un tercio de la pantalla |
| el modelo sale del tamaño equivocado | la imagen no mide 20 cm: corregir `ancho_impreso_m` |
| el modelo tiembla | acercarse; que la imagen esté plana |
