# Chuleta — Semana 4, en orden

Desde la carpeta del repo. Si no activaste el entorno, `python` es
`.\.venv\Scripts\python.exe`.

---

**Antes de empezar** — la suite entera, termina en `N de N EN OK`

    python comun\verificar_todo.py

**Dejar Unity con el edificio de la demo** — los dos anexos del mismo edificio

    python semana04\exportar_unity.py ingenieria
    python semana03\exportar_unity.py ingenieria
    python comun\lanzar_unity.py editor ingenieria          y Play

El **edificio va siempre**: sin argumento el lanzador abre el LT2, y con los
anexos de otro edificio el visor apaga los diagramas (el lanzador lo avisa).

**Trazabilidad desde Python** — la misma barra que tocaste en Unity

    python semana04\trazabilidad.py ingenieria 18
    python semana04\trazabilidad.py ingenieria 537 --caso 1.2G+1.0Q+1.4EY
    python semana04\trazabilidad.py ingenieria 427 --caso 1.2G+1.0Q+1.4EX

**Si preguntan cómo se sabe que los números están bien**

    python semana04\verificar_semana04.py          reconstruccion, superposicion, E*A, signos
    python semana04\test_contrato_semana04.py      nombres JSON <-> C#, en las dos direcciones
    python semana04\verificar_unity_semana04.py    Unity lee el JSON de verdad (Unity cerrado)

**Si el profesor dicta parámetros** — se regeneran los DOS anexos con los mismos flags, y se repiten en los comandos de Python

    python semana04\exportar_unity.py ingenieria --cs 0.20 --uso pasillos
    python semana03\exportar_unity.py ingenieria --cs 0.20 --uso pasillos
    python semana04\trazabilidad.py ingenieria 18 --cs 0.20 --uso pasillos
    python semana04\verificar_semana04.py ingenieria --cs 0.20 --uso pasillos

(sin los flags, `trazabilidad.py` avisa que el anexo se exportó con otros parámetros)

**Otro edificio**

    python semana04\exportar_unity.py conjunto
    python semana03\exportar_unity.py conjunto
    python comun\lanzar_unity.py editor conjunto

---

## En la app, sección Semana 4 del panel

| botón | qué hace |
| --- | --- |
| `G` `Q` `EX` `EY` y las combinaciones | cambia el **caso activo**: panel, diagramas, punto P-M y deformada |
| **Diagramas de esfuerzos** | prende los diagramas |
| `My` `Mz` `Vz` `Vy` `N` `T` | la magnitud |
| **la seleccionada** / **todas las visibles** | una barra, o todas las del piso filtrado |
| escala | solo gráfica |
| **Curva P-M de la seleccionada** | la ventana de demanda-capacidad |
| **Columna demo (18)** / **Muro demo (537)** | selecciona y centra la cámara |

En la sección **deformada**: **Caso activo (S4)** muestra la deformada del
caso o la combinación activa.

---

## Los números para tener en la cabeza

| | |
| --- | --- |
| Reconstrucción | llega al extremo *j* de OpenSees dentro de la cota del redondeo del servidor (`5e-5` por fuerza, propagado): peor 6.0e-4 en My, 1.4G, elemento 292, el 0.78 de su cota |
| Columna 18, S3 | P 3904.8 kN, M 40.6 kN·m, Mn 355.9 kN·m, **u 0.114** |
| Muro 537, S3 | P 3884.0 kN, M = \|My\| 5556.4 kN·m, Mn 82 428.5 kN·m, **u 0.067** |
| Muro 537, 1.2G+1.0Q+1.4EY | P 5237.2 kN, M = \|My\| 40 969.1 kN·m, Mn 90 780.2 kN·m, **u 0.451** |
| Columna 80, S3 | **u 1.226, no pasa**: último piso, poco axial, momento del techo |
| Muro 427, 1.2G+1.0Q+1.4EX | **fuera de la curva**: tracción −3510 kN contra −1649 de tracción pura |
| Muro 508, 1.2G+1.0Q+1.4EY | **u 36, no pasa**: muro corto (2.35 m) traccionado, P −1108 kN, casi en la tracción pura |
| No pasan | 10 en S3, 36 en 1.2G+1.0Q+1.4EY — nominal, sin φ |
| Momento del plano de un muro | el de **inercia mayor**: `My` en los 56 de Ingeniería, `Mz` en los 40 del LT2 |

## Cuatro respuestas

- **Unity no calcula**: lee los esfuerzos, las combinaciones y las curvas
  ya hechas en Python, y las dibuja.
- **El diagrama del medio** se reconstruye por equilibrio y se verifica
  contra el extremo *j* de OpenSees en todas las barras.
- **El 18 es el mismo número en los cuatro lados**: tag de OpenSees, id del
  JSON, `DatoElemento` de Unity y nombre del objeto `Elem_18_columna`.
- **JsonUtility no avisa** cuando un campo no calza: por eso el test de
  contrato va en las dos direcciones y otro le hace leer el JSON a Unity.
