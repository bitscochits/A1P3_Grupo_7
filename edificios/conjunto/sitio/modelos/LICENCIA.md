# Modelos de autos y árboles del visor

Los dibuja la vista realista alrededor del edificio (casilla «Autos y
árboles» en Capas > Vista). Son **solo dibujo**: el modelo estructural no
los ve.

| carpeta | de dónde | licencia |
|---|---|---|
| `autos/` | **Car Kit 3.1**, de Kenney (www.kenney.nl), bajado el 06-10-2026 de https://kenney.nl/assets/car-kit | **CC0 1.0** (dominio público). `autos/License.txt` es el original |
| `arboles/` | **Nature Kit 2.1**, de Kenney (www.kenney.nl), bajado el 06-10-2026 de https://kenney.nl/assets/nature-kit | **CC0 1.0** (dominio público). `arboles/License.txt` es el original |

CC0 no exige nombrar al autor; igual se nombra (en el JSON y en el panel),
como pide Kenney si se puede.

Del paquete se copiaron solo los OBJ que se usan (7 autos, 8 árboles) y la
textura de colores de los autos (`autos/colormap.png`). No se modificaron:
`edificios/conjunto/entorno.py` los lee y deja la versión que dibuja Unity
en `unity/Assets/Resources/Entorno/modelos.json`, con estos cambios:

- **Ejes**: el OBJ es de mano derecha (Y arriba, el auto mira a +Z). Unity
  es de mano izquierda: se pasa con (−x, y, z), que es un espejo, así que se
  invierte el orden de los vértices de cada triángulo (como el AT-ST en
  `semana05_lab/personaje_atst.py`). Los autos son simétricos: el espejo no
  se nota.
- **Tamaño**: los autos de Kenney son de juguete (un sedán mide 1.5 × 2.55,
  la proporción de un auto chocador). Se estiran a las medidas de un auto
  real de cada tipo (`sitio/entorno.json`), y cada rueda se escala pareja
  en su centro para que siga redonda. Los árboles se escalan parejo a su
  altura.
- **Colores**: las caras se agrupan por el color que les toca en la
  textura (pintura, vidrio, plástico, luces, neumático, llanta) y cada grupo
  se dibuja con un material propio de color realista. La pintura de cada
  auto y el verde de cada árbol cambian de uno a otro.
