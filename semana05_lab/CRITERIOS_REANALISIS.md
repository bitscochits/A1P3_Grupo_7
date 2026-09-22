# Cuándo hay que reanalizar, y cuándo no

> El LAB de la Semana 5 pide dos cosas que van juntas: modificar el
> modelo **e indicar cuándo eso exige reanálisis**. Esta es la respuesta,
> y el criterio sale de una sola ecuación.

---

## 1. La regla, en una línea

El modelo es **lineal elástico**:

```
K · u = F
```

`K` es la rigidez (geometría, secciones, material, apoyos) y `F` las
cargas. De ahí salen las dos reglas que deciden todo:

- **Si `K` no cambia**, la respuesta es lineal en las cargas:
  `K·(u₁ + u₂) = F₁ + F₂`. Se pueden **escalar y sumar** casos ya
  resueltos sin volver a OpenSees. Eso es la superposición.
- **Si `K` cambia**, los resultados guardados son de **otra estructura**.
  Sumarlos no significa nada: hay que **reanalizar**.

Dónde vive cada cosa en el código:

| | dónde se arma | con qué |
| --- | --- | --- |
| `K` | `comun/servidor_opensees.py` `construir_modelo()` | `ops.element('elasticBeamColumn', …, A, E, G, J, Iy, Iz, transf)`, `ops.fix()`, `ops.node()`, `ops.rigidDiaphragm()` |
| `F` | `comun/servidor_opensees.py` `aplicar_cargas()` | `ops.load()` (nodal) y `ops.eleLoad(… '-beamUniform')` (repartida) |

---

## 2. La tabla

| Lo que el usuario cambia | ¿cambia `K`? | ¿cambia `F`? | ¿vale superponer? | **¿reanálisis?** | ¿hay que rehacer la curva P-M? |
| --- | :---: | :---: | :---: | :---: | :---: |
| **λ de un caso base** (los sliders) | no | no | **sí** | **no** | no |
| Escalar **un caso completo** (todo Q ×1.5) | no | sí | **sí**, es `λQ = 1.5` | **no** | no |
| Intensidad de carga **en una barra o zona** | no | sí | no | **sí** | no |
| **Área tributaria** de una viga | no | sí | no | **sí** | no |
| **Activar / desactivar** un elemento | **sí** | sí (su peso) | no | **sí** | no |
| **Apoyo** (restricciones de un nodo) | **sí** | no | no | **sí** | no |
| **Sección** de una barra | **sí** | sí (su peso) | no | **sí** | **sí** |
| **Material** (`E`, `G`) | **sí** | no | no | **sí** | sí, si cambia `f'c` |
| Mover un nodo | **sí** | sí (largo y peso) | no | **sí** | no |
| Coeficiente sísmico `Cs`, `q`, patrón | no | sí | no | **sí** (es otro caso base) | no |

Las dos columnas de la derecha no son la misma pregunta, y ahí se cae
mucha gente: **la capacidad no sale de `K·u = F`**. La curva P-M la
calcula `comun/capacidad.py` con una sección de fibras, y depende de la
geometría de la sección, del fierro y del `f'c`. Cambiar una sección
obliga a las dos cosas: reanalizar *y* recalcular su curva.

---

## 3. Los tres casos que conviene tener claros

**a) Mover un slider no es modificar el modelo.** Es elegir otra
combinación de casos que OpenSees ya resolvió. Por eso los sliders de
`VisorSemana05.Instantanea.cs` responden en menos de un milisegundo y
funcionan sin servidor: solo escalan y suman. Y por eso están
*verificados* contra Python en vez de dados por buenos
(`verificar_instantanea.py`).

**b) Escalar todo un caso sí es superposición; escalar una viga, no.**
Multiplicar el caso Q completo por 1.5 es exactamente `λQ = 1.5`: es una
combinación de casos resueltos. Pero subir la carga de **una sola viga**
no lo es, porque no existe un caso base "carga solo en esa viga" ya
resuelto. `F` cambia en una dirección que nadie calculó, y hay que
reanalizar.

**c) El aviso tiene que estar en la pantalla, no en la cabeza de nadie.**
Cuando el modelo se edita, el visor marca el anexo como desactualizado y
lo dice en la cabecera: *"Modelo editado (borrar elemento 69). Mostrando
el reanálisis del servidor (G, Q, EX, EY); el anexo S4 y E1–E3 siguen
siendo del modelo original."* Los casos precalculados, los sliders y la
carga móvil son del modelo **anterior**, y el que los mire tiene que
saberlo.

---

## 4. Lo que el reanálisis de la app SÍ y NO rehace

El reanálisis que se pide desde Unity (pestaña **Modificar** →
*"Recalcular en el servidor"*) manda el modelo editado a
`POST /analizar`, que vuelve a armar `K`, aplica `F` y resuelve los
cuatro casos base. Eso es correcto, pero tiene dos límites declarados:

1. **El peso propio no se recalcula.** Las cargas del caso G ya vienen
   sumadas en el modelo (`incluye_peso_propio: true`, 220 cargas
   repartidas en el LT2). Si se cambia una sección desde Unity, `K` se
   actualiza pero su peso sigue siendo el de la sección vieja. Para que
   el peso también cambie hay que rehacer el modelo con
   `edificios/<ed>/armar.py`.
2. **Las curvas P-M y el anexo no se rehacen.** El reanálisis devuelve
   desplazamientos, esfuerzos y reacciones; la demanda-capacidad sigue
   apoyada en las curvas del anexo. Si el cambio toca una sección, esa
   curva queda obsoleta y hay que reexportar
   (`semana04/exportar_unity.py <ed>`).

Las dos están en `semana05/MODIFICACIONES.md` como limitaciones 1 y 2,
y no se esconden: es mejor decirlas que mostrar un número que ya no
corresponde.

---

## 5. Cómo se demuestra en vivo

| pregunta | qué hacer | qué se ve |
| --- | --- | --- |
| "¿Esto necesita reanálisis?" (slider) | mover λG o λEX | todo responde al instante; abajo dice en cuántos ms combinó y con cuántas barras |
| "¿Y esto?" (borrar una barra) | pestaña **Modificar** → borrar la 69 | la cabecera avisa que el anexo quedó desactualizado; hay que apretar *Recalcular* |
| "¿Cómo sabes que el slider no miente?" | apretar *"Combinar en Python"* con los mismos λ | el servidor devuelve el mismo caso; y `verificar_instantanea.py` lo comprueba con 10 juegos de λ |
| "¿Y si cambio una sección?" | — | cambia `K` **y** la curva P-M: reanálisis *y* reexportar el anexo (§4) |

---

## 6. Por qué se puede confiar en la superposición

No es un supuesto: está medido. `comun/combinar.py` documenta por qué
vale y cuándo dejaría de valer (material no lineal, P-Δ, contacto), y
hay dos verificaciones que lo comprueban contra OpenSees:

- `semana04/verificar_semana04.py` bloque **[3]**: la combinación
  `1.2G+1.0Q+1.4EX` se resuelve **de verdad** en OpenSees, con las cargas
  ya combinadas, y se compara contra la suma. Cierra dentro del redondeo
  del servidor.
- `semana05/verificar_superposicion.py`: E1, E2 y E3 por **cuatro vías**
  —corrida explícita, suma lineal, `POST /combinar` y el precalculado—
  con cotas medidas.

Y del lado de Unity, `semana05_lab/verificar_instantanea.py` compara la
combinación que hace el visor contra la de Python en 10 juegos de λ,
incluidos negativos y el nulo: desplazamientos, las 12 fuerzas, los
esfuerzos a lo largo de la barra, `P`, `M`, `Mn`, el extremo que manda y
`pasa / no pasa`.
