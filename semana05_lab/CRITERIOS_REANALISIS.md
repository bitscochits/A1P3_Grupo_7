# Cuándo hay que reanalizar, y cuándo no

> El LAB de la Semana 5 pide dos cosas que van juntas: modificar el
> modelo **e indicar cuándo eso exige reanálisis**. Esta es la respuesta,
> y el criterio sale de una sola ecuación. Cada fila de la tabla está
> comprobada con el motor del repo, no razonada en el aire; los números
> están abajo.

---

## 1. La regla, en una línea

El modelo es **lineal elástico**:

```
K · u = F
```

`K` es la rigidez (geometría, secciones, material, apoyos) y `F` las
cargas. De ahí salen las reglas que deciden todo:

- **Si `K` cambia**, los resultados guardados son de **otra estructura**.
  Sumarlos no significa nada: hay que **reanalizar**.
- **Si `K` no cambia**, la respuesta es lineal en las cargas:
  `K·(u₁ + u₂) = F₁ + F₂`. Se pueden **escalar y sumar** casos ya
  resueltos sin volver a OpenSees. Eso es la superposición.
- **Si `K` no cambia pero `F` sí**, la pregunta correcta no es "¿cambió
  F?" sino **"¿el `F` nuevo es combinación de los casos que ya se
  resolvieron?"**. Todo Q ×1.5 lo es (`λQ = 1.5`). El sismo con el doble
  de `Cs` lo es (`λEX = 2`). La carga de **una** viga **no** lo es,
  porque nadie resolvió un caso base con carga solo ahí. Bastaría
  resolver ese caso unitario una vez para que también fuera
  superposición: **reanalizar es resolver un caso base nuevo**, no
  "volver a correr porque algo cambió".

Dónde vive cada cosa en el código:

| | dónde se arma | con qué |
| --- | --- | --- |
| `K` | `comun/servidor_opensees.py` `construir_modelo()` | `ops.element('elasticBeamColumn', …, A, E, G, J, Iy, Iz, transf)`, `ops.fix()`, `ops.node()`, `ops.rigidDiaphragm()` |
| `F` | `comun/servidor_opensees.py` `aplicar_cargas()` | `ops.load()` (nodal) y `ops.eleLoad(… '-beamUniform')` (repartida) |
| `EX`, `EY` | `semana03/lab_semana03.py` `armar_casos()` | `F_i = Cs · W_i · patrón(z_i)` por piso, con `W_i = G_i + f·q·Q̂_i` |

---

## 2. La tabla

| Lo que el usuario cambia | ¿cambia `K`? | ¿cambia `F`? | ¿vale superponer? | **¿reanálisis?** | ¿hay que rehacer la curva P-M? |
| --- | :---: | :---: | :---: | :---: | :---: |
| **λ de un caso base** (los sliders) | no | no | **sí** | **no** | no |
| Escalar **un caso completo** (todo Q ×1.5) | no | sí | **sí**, es `λQ = 1.5` | **no** | no |
| **Coeficiente sísmico `Cs`** | no | sí, pero **proporcional**: `EX(Cs′) = (Cs′/Cs)·EX(Cs)` | **sí**, es `λEX = Cs′/Cs` | **no** | no |
| **`q`** (fracción de Q en el peso sísmico) o el **patrón en altura** | no | sí, y cambia la **forma** de `F_i` piso a piso | no: ningún caso base tiene esa forma | **sí** (es otro caso base) | no |
| Intensidad de carga **en una barra o zona** | no | sí | no: no hay un caso base resuelto solo ahí | **sí** | no |
| **Área tributaria** de una viga | no | sí: la parte de losa de G y de Q; el peso propio `A·γ` no; y EX/EY si se rehace el sismo, porque `W_i` cambia | no | **sí** | no |
| **Activar / desactivar** un elemento | **sí** | sí: se van sus cargas repartidas (peso propio **y** la losa que bajaba por ella); el peso nodal de columnas y muros se queda | no | **sí** | no |
| **Apoyo** (restricciones de un nodo) | **sí** | no | no | **sí** | no |
| **Sección** de una barra | **sí** | debería (su peso); la app **no** lo actualiza (§4) | no | **sí** | **sí**, si la barra tiene fierro |
| **Material uniforme** (`f′c` del modelo → `E`, `G` en todo) | sí, `K → αK` | no | no hace falta | **para los esfuerzos, no**: `u → u/α` exacto; esfuerzos, reacciones y D/C **no cambian** | sí, si cambia `f′c` (la curva usa `fpc_MPa`) |
| **Material de una sección** o de un cuerpo (`E`, `G`, `fpc_MPa` por sección) | **sí**, no uniforme | no | no | **sí** | sí, si cambia su `f′c` |
| Mover un nodo | **sí** (largos, direcciones, el brazo del nodo en su diafragma) | sí: `w·L` cambia con `L`; la losa (`q·A/L`) y el peso nodal habría que recalcularlos y la app **no** lo hace | no | **sí** | no |

Las dos columnas de la derecha no son la misma pregunta, y ahí se cae
mucha gente: **la capacidad no sale de `K·u = F`**. La curva P-M la
calcula `comun/capacidad.py` con una sección de fibras, y depende de la
geometría de la sección, del fierro y del `f′c`. Cambiar una sección con
fierro obliga a las dos cosas: reanalizar *y* recalcular su curva.

### Los números detrás de la tabla (LT2, motor del repo, 2026-09-22)

- **`Cs` es un λ.** Con `Cs = 0.10` el corte basal es `V = 3792.28 kN`;
  con `0.20`, `7584.56`: cociente `2.0000000000`. En **todos** los nodos
  `max|u(0.20) − 2·u(0.10)| = 1e-8 m` y en todas las barras
  `max|f(0.20) − 2·f(0.10)| = 1e-4 kN`: exactamente **un paso del
  redondeo** con que el servidor escribe (8 decimales en m, 4 en kN). La
  forma del vector no se mueve: las fracciones `F_i/V` de abajo arriba
  son `0.075 0.139 0.208 0.276 0.301` con los dos `Cs`.
- **`q` y el patrón sí cambian la forma.** Con `--q 6.0` las fracciones
  pasan a `0.075 0.138 0.208 0.276 0.304`; con `--patron nch433`, a
  `0.121 0.126 0.150 0.194 0.409`. Ningún `λ` sobre EX produce eso: es
  otro caso base.
- **Material uniforme.** `f′c` 35 → 140 MPa (`E ×2`, `G ×2` en todo el
  modelo): `max|u₂ − u/2| = 5e-9 m` en los cuatro casos (medio paso del
  redondeo), `Δf = 0.0 kN` y `ΔR = 0.0 kN`. El mismo `E ×2` **solo** en
  las `V 0.60x0.80` (180 barras): `Δu` hasta 3.75 mm y `Δf` hasta 884 kN.
- **Activar / desactivar.** La viga 337 tiene `L = 5.0 m` y
  `wz_G = −26.278 kN/m`: borrarla quita 131 kN de G, de los que **71 son
  la losa y el muerto** que bajaban por ella (en rigor habría que
  repartirlos a las vecinas) y 60 su peso propio; y 37 kN de Q. La
  columna 69 (la M1) no lleva repartidas: sus 48.5 kN nodales se quedan.
- **Área tributaria.** El `wz_G` de la 337 es `12.0` de peso propio
  (`A·γ = 0.48·25`) más `14.278` de losa y muerto: cambiar el área mueve
  la segunda parte, no la primera.

---

## 3. Los cuatro casos que conviene tener claros

**a) Mover un slider no es modificar el modelo.** Es elegir otra
combinación de casos que OpenSees ya resolvió. Por eso los sliders de
`VisorSemana05.Instantanea.cs` responden en **0.8 a 4.2 ms** (medidos en
la app: `semana05/capturas/registro.txt`, `ins.*.ms`) y funcionan sin
servidor: solo escalan y suman. Y por eso están *verificados* contra
Python en vez de dados por buenos (`verificar_instantanea.py`).

**b) Escalar todo un caso sí es superposición; escalar una viga, no.**
Multiplicar el caso Q completo por 1.5 es exactamente `λQ = 1.5`: es una
combinación de casos resueltos. Pero subir la carga de **una sola viga**
no lo es, porque no existe un caso base "carga solo en esa viga" ya
resuelto. `F` cambia en una dirección que nadie calculó, y hay que
reanalizar. Si se resolviera ese caso unitario una vez, pasaría a ser
superposición: **el criterio no es que cambie `F`, es que `F` salga del
espacio de los casos resueltos.**

**c) Doblar `Cs` es la trampa perfecta, y conviene caer en ella a
propósito.** Se ve como "otra carga" y da la tentación de reanalizar.
Pero `F_i = Cs·W_i·patrón_i` es proporcional a `Cs`, así que
`EX(0.20) = 2·EX(0.10)` y con el slider en `λEX = 2` ya está. El repo lo
rehace en Python igual (`semana05/comparar_anexos.py lt2 --cs 0.20`) y
que dé lo mismo a un paso de redondeo **es la prueba de que el modelo es
lineal**: el reanálisis ahí no era necesario, era una comprobación. Lo
que sí exige otro caso base es `q` o el patrón, porque cambian la forma.

**d) El aviso tiene que estar en la pantalla, no en la cabeza de nadie.**
Cuando el modelo se edita, el visor marca el anexo como desactualizado y
lo dice en la cabecera; los casos precalculados, **los sliders
instantáneos** y la carga móvil son del modelo **anterior**, y cada uno
lo avisa en su bloque. El que los mire tiene que saberlo.

---

## 4. Lo que el reanálisis de la app SÍ y NO rehace

El reanálisis que se pide desde Unity (pestaña **Modificar** →
*"Recalcular en el servidor"*) manda el modelo editado a
`POST /analizar`, que vuelve a armar `K`, aplica `F` y resuelve los
cuatro casos base. Eso es correcto, pero tiene límites declarados:

1. **El peso propio no sigue a la sección.** Las cargas del caso G ya
   vienen sumadas en el modelo (`incluye_peso_propio: true`, 220 cargas
   repartidas en el LT2). Si se cambia una sección desde Unity, `K` se
   actualiza pero su peso sigue siendo el de la sección vieja. Para que
   el peso también cambie hay que rehacer el modelo con
   `edificios/<ed>/armar.py`. Se ve en la M3: la carga aplicada no se
   mueve.
2. **Las curvas P-M y el anexo no se rehacen.** El reanálisis devuelve
   desplazamientos, esfuerzos y reacciones; la demanda-capacidad sigue
   apoyada en las curvas del anexo. Si el cambio toca una sección con
   fierro, esa curva queda obsoleta y hay que reexportar
   (`semana04/exportar_unity.py <ed>`). En la M3 de la demo no aplica: la
   viga 337 no tiene fierro extraído y no entra a la revisión P-M.
3. **Mover un nodo no recalcula cargas.** Ni las áreas tributarias ni
   el peso nodal de las verticales: solo `K` y el `w·L` de las barras
   que cambian de largo.
4. **Área tributaria y material no tienen control en la app.** Se cambian
   editando el modelo (`armar.py`, `perfiles/*.json`) y reexportando.

Las dos primeras están en `semana05/MODIFICACIONES.md` como limitaciones,
y no se esconden: es mejor decirlas que mostrar un número que ya no
corresponde.

---

## 5. Cómo se demuestra en vivo

| pregunta | qué hacer | qué se ve |
| --- | --- | --- |
| "¿Esto necesita reanálisis?" (slider) | mover `G` o `EX` en *Superposición INSTANTÁNEA en Unity* | todo responde al instante; abajo dice en cuántos ms combinó y con cuántas barras |
| "¿Cómo sabes que el slider no miente?" | apretar **E3** en los sliders instantáneos y luego **E3** en *Estados de la entrega* (precalculado por Python) | la misma cabecera por dos caminos: `24.63 mm`, `NO PASA 4/69 (1 fuera de curva)`. Y en la terminal, `verificar_instantanea.py --registro` cruza lo que la app escribió con Python |
| "¿Y si duplico el sismo?" | — | **no**: es `λEX = 2`; `comparar_anexos.py --cs 0.20` lo mide a un paso de redondeo |
| "¿Y esto?" (borrar una barra) | pestaña **Modificar** → borrar la 69 | la cabecera avisa que el anexo quedó desactualizado; hay que apretar *Recalcular* |
| "¿Y si cambio una sección?" | **Modificar** → viga 337 → *Cambiar sección* → `V 0.30x0.80` → *Recalcular* | cambia `K`: reanálisis; y si la barra tuviera fierro, también su curva P-M (§4) |

---

## 6. Por qué se puede confiar en la superposición

No es un supuesto: está medido. `comun/combinar.py` documenta por qué
vale y cuándo dejaría de valer (material no lineal, P-Δ, contacto), y
hay verificaciones que lo comprueban contra OpenSees:

- `semana04/verificar_semana04.py` bloque **[3]**: la combinación
  `1.2G+1.0Q+1.4EX` se resuelve **de verdad** en OpenSees, con las cargas
  ya combinadas, y se compara contra la suma. Cierra dentro del redondeo
  del servidor.
- `semana05/verificar_superposicion.py`: E1, E2 y E3 por **cuatro vías**
  —corrida explícita, suma lineal, `POST /combinar` y el precalculado—
  con cotas medidas.

Y del lado de Unity, `semana05_lab/verificar_instantanea.py` lo hace por
dos caminos: repite el algoritmo del visor en Python, con su aritmética
de 32 bits, sobre 10 juegos de λ; y con `--registro` cruza contra Python
**los números que la app real escribió** al mover los sliders
(`semana05/capturas/registro.txt`, paso D2 de `CapturaSemana05`):
desplazamientos, extremos de las barras de control, `P`, `M`, `Mn`, el
extremo que manda, `pasa / no pasa` y los conteos de la cabecera. La
auditoría del código encontró que los sliders se congelaban después del
primer movimiento (`tipo = "combinacion"` en vez de `"superposicion"`, y
el hook no reemplazaba el caso); la réplica en Python no podía verlo, y
es ese cruce con la app el que hoy demuestra que no pasa: la versión
sube 1 en cada movimiento.
