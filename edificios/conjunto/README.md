# El conjunto — los dos cuerpos unidos

Los dos modelos describen **el mismo edificio en dos etapas**: comparten
las seis cotas de piso (−7.97 a +11.83, 3.96 m entre niveles) y los
ejes numerados 1, 2 y 3, y los separa una junta de dilatación justo
después de la caja de ascensores del LT2. Cada plano refiere el otro
cuerpo como "etapa anterior" / "etapa nueva".

```
python edificios\conjunto\armar.py           une data/modelo/lt2 + ingenieria
python comun\calcular.py conjunto            resuelve G, Q, EX, EY
python edificios\conjunto\exportar_unity.py  data/unity/conjunto.json
python edificios\conjunto\verificar_conjunto.py
python comun\lanzar_unity.py app conjunto --pantalla-completa
```

## `calce.json` — la transformación entre los dos planos

Cada juego de planos está dibujado en su propio marco. `calce.json`
declara, por cuerpo, `dx`, `dy`, `dz` y el giro, **con cómo se midió
cada uno**:

| | valor | de dónde sale |
|---|---|---|
| `dy` | 36.904 | medido sobre los ejes 1, 2 y 3, que ambos planos comparten; los tres dan lo mismo a cuatro decimales |
| `dz` | −7.97 | Ingeniería está en alturas relativas, el LT2 en cotas reales |
| `dx` | −35.082 | **derivado** de las caras: cara este del LT2 + junta declarada = cara oeste de Ingeniería |
| junta | 0.05 m, libre | supuesto; `armar.py` mide la separación real y avisa si no es la declarada |

`dx` depende del modelo del otro cuerpo y ya cambió dos veces; no hace
falta acordarse porque `armar.py` mide las caras en cada corrida.

## Qué hace `armar.py`

1. Lee los dos `data/modelo/`, aplica el calce y renumera nodos,
   elementos y secciones con un corrimiento por cuerpo, tocando los
   siete sitios donde vive un tag.
2. **Sella `E` y `G` en cada sección** con el hormigón de su propio
   cuerpo. El contrato tiene un solo `material`; sin esto el LT2
   (G35) corría con los 28 MPa del otro, un 10.6 % más blando, y el
   equilibrio cerraba igual.
3. **Mide** que las caras queden a la junta declarada, que los cuerpos
   no se solapen y que compartan las cotas de piso.
4. La junta es **libre**: ningún elemento la cruza; los dos cuerpos se
   resuelven independientes dentro del mismo modelo.

## El invariante que lo vigila

Con la junta libre, cada cuerpo dentro del conjunto tiene que dar
**exactamente** lo mismo que resuelto solo. `verificar_conjunto.py` lo
compara GDL por GDL: el LT2 da 0.00e+00 en los cuatro casos; Ingeniería
queda dentro del redondeo del servidor (7e-8 m sobre 33 mm, con el 84 %
de los GDL exactos). Es la verificación que el equilibrio no puede
hacer, y la que atrapó el error del módulo elástico.

## Números

558 nodos, 937 elementos, 10 diafragmas, 47 secciones.
G = 97 885.36 kN = 34 148.98 (LT2) + 63 736.38 (Ingeniería).
Separación cara a cara 0.050 m. 705 polígonos tributarios.

## El relieve del sitio (`sitio/`, `topografia.py`)

El terreno natural alrededor del edificio, para el visor. **Solo dibujo**:
ningún cálculo lo usa.

```
python edificios\conjunto\bajar_dem.py             una vez: baja la ventana del DEM al repo
python edificios\conjunto\topografia.py            data/unity/topografia_<ed>.json + sitio/topografia_planta.png
python edificios\conjunto\topografia.py --verificar
python comun\lanzar_unity.py sincronizar conjunto   lo copia a StreamingAssets/topografia.json
```

| entrada | qué aporta |
|---|---|
| `sitio/topo_uandes.kmz` | la **zona**, trazada en Google Earth. Sin cotas: Google Earth guarda un trazo pegado al terreno con altura 0 |
| `sitio/techo_edificio_antiguo.kmz` | el techo del cuerpo antiguo en la foto (el LT2 todavía no aparece): de él salen el **giro** y la **posición** |
| `sitio/dem_copernicus_glo30.json` | las **cotas**: Copernicus DEM GLO-30 (celda de ~30 m, 2011-2015), solo la ventana del campus |
| `sitio/sitio.json` | los supuestos, con su porqué |

Cómo se ubica: el lado largo del techo de la foto da el rumbo de +x
(71.9°, hacia el ENE); su centro cae en el centro del techo del modelo
(entre ejes, x 8.02 a 58.02, y 47.70 a 64.10); y el DEM se corre en vertical
por mínimos cuadrados sobre los 84 apoyos en terreno. Lo que comprueba
`topografia.py`: el techo de la foto mide lo del modelo más el borde de la
losa (+1.29 y +1.70 m), el terreno sube hacia +x a lo largo del edificio
como sus terrazas (921.7 → 927.5 m), el calce vertical deja un residuo rms
de 1.22 m, y las claves del JSON son los campos de
`AmbienteVisor.Topografia.cs`.

En Unity: Capas > Vista > "Relieve del sitio". Con el relieve a la vista se
apaga el plano del suelo (no las terrazas), y el edificio queda en un hueco
con taludes hasta la cota del terreno del modelo.

![El relieve en la app, desde el suroeste](sitio/capturas/relieve_1_iso_suroeste.jpg)

![De cerca: el edificio en la ladera](sitio/capturas/relieve_4_cerca.jpg)

Las fotos las saca la app sola: `build\LaboratorioEstructural.exe -capturarRelieve <carpeta>`
(`unity/Assets/Scripts/CapturaRelieve.cs`), con su `registro.txt`. La
figura en planta, con curvas cada 1 m, el techo de la foto y los nodos de
los dos cuerpos, es `sitio/topografia_planta.png`.
