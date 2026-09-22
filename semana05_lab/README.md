# Semana 5 — LAB: interacción, modificación y experiencia estructural

Esta carpeta es **la entrega del LAB** (10 puntos). Es una entrega
distinta del **avance** de la misma semana (20 puntos), que está en
[`semana05/`](../semana05/) y la armó Pedro: el viewer estructural, el
Excel, el realismo, la carga móvil y la preparación móvil.

Casi todo lo que el LAB pide **ya existe** en ese trabajo. Esta carpeta
hace dos cosas:

1. **Mapear** cada criterio del LAB a dónde se demuestra, para que
   cualquiera del grupo pueda defenderlo sin buscar.
2. **Cerrar lo que faltaba** para este enunciado en concreto: los
   sliders que responden *al instante* y la tabla de criterios de
   reanálisis.

| archivo | qué es |
| --- | --- |
| [`CRITERIOS_REANALISIS.md`](CRITERIOS_REANALISIS.md) | Cuándo hay que reanalizar y cuándo no, derivado de `K·u = F`. Es el criterio 5 de la rúbrica. |
| [`GUION_DEMO.md`](GUION_DEMO.md) | La demostración en vivo, ordenada por los cinco criterios. |
| `verificar_instantanea.py` | Comprueba que la combinación que hace Unity al mover un slider es la misma que calcula Python, en 10 juegos de λ. |

Y en Unity:

| archivo | qué es |
| --- | --- |
| `unity/Assets/Scripts/VisorSemana05.Instantanea.cs` | Los cuatro sliders que combinan **en el momento y sin servidor**, y rehacen la demanda-capacidad. |

---

## Dónde está cada criterio

| criterio | pts | dónde se demuestra | cómo se sabe que está bien |
| --- | :---: | --- | --- |
| **Interactividad** | 2 | Navegar (arrastrar, rueda, `F`, `C`). Seleccionar barra o nodo → pestaña **Elemento**. Capas en **Capas** (apoyos por tipo, ejes locales, áreas tributarias, diafragmas). Combinación en **Caso**. Respuesta combinada: deformada + diagramas. Demanda-capacidad: curva P-M en Elemento y **Mapa D/C**. | `semana05/comparar_unity.py` bloque [4] (56 filas, 0 falla) · `semana05/UX.md` · fotos 01–14b |
| **Modificación del modelo** | 2 | **Cuatro** de las seis de la lista. **M1** *activar/desactivar elemento*: pestaña **Modificar** → borrar la barra 69 → *Recalcular*. **M2** *intensidad de carga*: `--cs 0.20` → reexportar → reabrir. **M3** *sección*: la viga 337 pasa a `V 0.30x0.80`. **M4** *apoyo*: el nodo 2 pasa de empotrado a rótula. | `semana05/reanalisis_demo.py` (las cuatro, reproducibles y en la suite) · `comparar_anexos.py` · `semana05/MODIFICACIONES.md` · fotos 21–22 |
| **Superposición en Unity** | 2 | **Caso → Superposición**: los cuatro sliders λG, λQ, λEX, λEY actualizan deformada, esfuerzos y P-M **al instante** (< 1 ms, sin servidor). E1–E3 precalculados y LIBRE por servidor quedan como referencia. | `verificar_instantanea.py` (10 juegos de λ) · `semana05/verificar_superposicion.py` (4 vías) |
| **Demanda-capacidad dinámica** | 2 | El punto (P, M) se mueve con los sliders, y con él `Mn`, `u` y el `pasa / no pasa`. El **Mapa D/C** repinta el edificio y actualiza el conteo. | `verificar_instantanea.py`: `P`, `M`, `Mn`, el extremo que manda y `pasa` coinciden con Python en las 69 barras con fierro |
| **Defensa / criterios de reanálisis** | 2 | La tabla de [`CRITERIOS_REANALISIS.md`](CRITERIOS_REANALISIS.md), y en la app el aviso de anexo desactualizado tras editar. | `semana04/verificar_semana04.py` [3] y `semana05/verificar_superposicion.py` respaldan la superposición |
| *SQ4 (recomendado)* | — | Carga móvil: pestaña **Carga movil**, 30 posiciones sobre el eje de vigas 203–208, con reparto y conservación. **No** está asociada al movimiento del usuario (ver abajo). | `semana05/CARGA_MOVIL.md` · fotos 19–20 |

---

## Lo que agregó este LAB, y por qué

### Los sliders instantáneos

El enunciado es exigente: *"los sliders deben actualizar
**instantáneamente** la deformada, los resultados y el punto P-M"*.

Lo que había antes era el caso **LIBRE**, que manda los λ a
`POST /combinar` y espera la respuesta de Python. Es correcto y sigue
siendo la referencia, pero tiene `timeoutCombinar = 90 s` y su primera
petición arma la base de los cuatro casos en el servidor: decenas de
segundos. Y sin servidor, no funciona.

`VisorSemana05.Instantanea.cs` agrega el caso **INSTANT**, que combina en
Unity los mismos casos base que ya trae `semana04.json` y responde en
**menos de un milisegundo** en el LT2 (378 barras, 232 nodos).

**Por qué esto no rompe la regla de oro.** Unity no resuelve `K·u = F`:
no arma rigidez ni toca el modelo. Hace tres cosas sobre números que
OpenSees ya calculó:

1. **Escalar y sumar** los cuatro casos base. Es la superposición, que
   vale porque `K` es la misma y el modelo es elástico, y que Python
   verificó contra una corrida explícita de OpenSees.
2. **Retabular antes de sumar.** Los casos base no vienen en las mismas
   estaciones: una viga cargada trae 9 puntos en G y Q y solo 2 en EX y
   EY (220 de las 378 barras del LT2). Se interpola linealmente a la
   malla fina, y es **exacto**: sin carga repartida el axial y los
   cortes son constantes y los momentos son rectas.
3. **Rehacer la demanda**, que *no* es lineal y por eso no se suma: del
   `f` combinado salen (P, M) con la misma regla de
   `demanda_capacidad.demanda()`, y `Mn` se interpola en la curva P-M que
   calculó Python con fibras.

**Y no se cree por argumento: se comprueba.**
`verificar_instantanea.py` repite esa combinación en Python y la compara
contra `semana05/superposicion.caso_combinado()` en 10 juegos de λ
—incluidos negativos, un solo caso y el nulo—: desplazamientos, las 12
fuerzas, los esfuerzos a lo largo de la barra, `P`, `M`, `Mn`, el extremo
que manda y `pasa / no pasa`. Todo dentro de la cota del redondeo.

> **Un error que encontró esa verificación.** La primera versión
> interpolaba usando la `x` de cada estación, y fallaba por `1.1e-2`
> kN·m. La causa no era el método: las `x` vienen redondeadas a 4
> decimales en el anexo, y ese error de `2.5e-5 m` multiplicado por la
> pendiente del momento (47 kN·m/m en una viga) da exactamente los
> `2.3e-3` que se veían. Se cambió a interpolar por **fracción de
> índice** —las mallas son equiespaciadas de 0 a L, y el bloque [1] del
> verificador de la Semana 4 lo comprueba—, y el peor error bajó a
> `2.0e-4`, que es el redondeo propagado y nada más.

### La tabla de criterios de reanálisis

`semana05/MODIFICACIONES.md` explica M1 y M2 paso a paso, pero no tenía
la regla general. [`CRITERIOS_REANALISIS.md`](CRITERIOS_REANALISIS.md) la
deriva de `K·u = F` y la lleva a una tabla de nueve filas, con dos
distinciones que el enunciado premia:

- **Escalar un caso completo es superposición** (`λQ = 1.5`), pero
  **subir la carga de una sola viga no lo es**: no existe un caso base
  resuelto para eso.
- **La capacidad no sale de `K·u = F`.** Cambiar una sección obliga a
  reanalizar *y* a recalcular su curva P-M.

---

## Cómo se corre

```powershell
python comun\lanzar_unity.py sincronizar lt2     # deja el LT2 en StreamingAssets
python comun\lanzar_unity.py app lt2             # la app de Windows
python semana05\servidor_s5.py                   # opcional: habilita LIBRE y el reanálisis
```

Los sliders instantáneos y el mapa D/C funcionan **sin** servidor. El
servidor hace falta para el caso LIBRE (la referencia de Python) y para
la M1.

La comprobación del LAB:

```powershell
python semana05_lab\verificar_instantanea.py lt2
python semana05\verificar_superposicion.py lt2
python semana05\compilar_unity.py                # los C# compilan sin abrir Unity
```

---

## Lo que queda corto, dicho de frente

- **SQ4 está a medias.** La carga móvil existe y está bien hecha —30
  posiciones resueltas en OpenSees, con reparto y conservación
  verificados—, pero recorre un **eje fijo de vigas** y el usuario elige
  la posición con un control. El enunciado pide que la carga siga **al
  usuario** y que se identifique el **panel** donde está y las **vigas
  receptoras**. Los datos para hacerlo ya están (`areas_tributarias`
  trae 243 polígonos con vértices y su viga dueña), pero no está
  construido. Es un sidequest *recomendado*, no obligatorio.
- **La modificación cubre cuatro de las seis** de la lista (el enunciado
  pide al menos dos): activar/desactivar elemento, intensidad de carga,
  sección y apoyo. Las cuatro se pueden repetir por script y las cuatro
  están en la suite. Quedan fuera **propiedad material** y **área
  tributaria**: se pueden cambiar editando el modelo, pero no hay control
  en el panel ni guardia que las cubra.
- **El peso propio no sigue a la sección.** Si se cambia una sección
  desde la app, `K` se actualiza pero su peso no, porque las cargas de G
  vienen sumadas en el modelo. Está declarado en
  [`CRITERIOS_REANALISIS.md`](CRITERIOS_REANALISIS.md) §4 y se ve en la
  salida de M3: la carga aplicada no se mueve.
