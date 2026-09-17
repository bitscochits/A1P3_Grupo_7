# -*- coding: utf-8 -*-
r"""
Verifica que el JSON que genera Python calce con las clases C# que lo
leen en Unity.

POR QUE EXISTE ESTE TEST
JsonUtility (el parser de Unity) NO avisa cuando un campo no calza:
simplemente deja la variable en su valor por defecto. Una clave mal
escrita no da error ni warning, solo un modelo que se dibuja raro. Un
'uz' mal escrito da deformada plana; un 'area' mal escrito da areas
tributarias en cero. Y como no hay excepcion, se descubre tarde.

Este test compara los campos declarados en los .cs contra las claves
reales del JSON exportado.

Correr:  python comun/test_contrato_unity.py [lt2 | ingenieria | conjunto]
"""
import json
import os
import re
import sys

# Este archivo vive en comun/, al lado de rutas.py: no se cuenta dirname
# para llegar a la raiz (CLAUDE.md, "Rutas"); la raiz la da rutas.
_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _AQUI)
import rutas                             # noqa: E402
_RAIZ = rutas.RAIZ

# El edificio se elige por linea de comandos: el contrato es el mismo
# para todos y por eso este test vive en comun/.
EDIFICIO = sys.argv[1] if len(sys.argv) > 1 else 'lt2'
JSON = rutas.unity(EDIFICIO)
CS = os.path.join(_RAIZ, 'unity', 'Assets', 'Scripts', 'ModeloEstructural.cs')

fallos = []


def check(cond, msg, detalle=""):
    print(f"  [{'OK  ' if cond else 'FALLA'}] {msg}")
    if detalle:
        print(f"         {detalle}")
    if not cond:
        fallos.append(msg)


# ============================================================
# Parseo simple del C#: campos publicos de cada clase serializable
# ============================================================
def campos_de_clases(ruta):
    with open(ruta, encoding='utf-8') as f:
        src = f.read()

    # Fuera comentarios, para no confundir ejemplos de las notas con
    # codigo real.
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    src = re.sub(r'//[^\n]*', '', src)

    clases = {}
    for m in re.finditer(r'class\s+(\w+)\s*\{', src):
        nombre = m.group(1)
        # Recorta hasta cerrar la llave de la clase.
        i = m.end() - 1
        prof, j = 0, i
        while j < len(src):
            if src[j] == '{':
                prof += 1
            elif src[j] == '}':
                prof -= 1
                if prof == 0:
                    break
            j += 1
        cuerpo = src[i:j]

        campos = set()
        # public <tipo> a, b, c;   (ignora propiedades con { get; })
        for d in re.finditer(
                r'public\s+[\w<>\[\]\.]+\s+([\w\s,]+?)\s*(?:=[^;]*)?;', cuerpo):
            grupo = d.group(1)
            if '(' in grupo:
                continue
            for nom in grupo.split(','):
                nom = nom.strip()
                if nom and re.fullmatch(r'\w+', nom):
                    campos.add(nom)
        clases[nombre] = campos
    return clases


print("Leyendo contrato...")
if not os.path.exists(JSON):
    print(f"No existe {JSON}. Corre primero: python src/exportar_unity.py")
    sys.exit(1)

with open(JSON, encoding='utf-8') as f:
    datos = json.load(f)

clases = campos_de_clases(CS)
print(f"  clases C# encontradas: {len(clases)}")


# ============================================================
print("\n[1] Cada clave del JSON tiene su campo en C#")
# ============================================================
def comparar(nombre_clase, muestra, ignorar=()):
    """Toda clave del JSON debe existir como campo publico en el C#."""
    if nombre_clase not in clases:
        check(False, f"la clase {nombre_clase} existe en el C#")
        return
    campos = clases[nombre_clase]
    faltan = [k for k in muestra
              if k not in campos and k not in ignorar]
    check(not faltan,
          f"{nombre_clase}: todas las claves del JSON estan en el C#",
          f"sin campo C#: {faltan}" if faltan else "")


# ----------------------------------------------------------------
# CLAVES QUE EL C# NO NECESITA, A PROPOSITO
# ----------------------------------------------------------------
# comparar() revisa en una sola direccion: que cada clave del JSON
# tenga su campo en el C#. Una clave SIN campo no rompe el dibujo
# (JsonUtility la ignora sin quejarse), pero es un dato que Unity no
# ve y que PIERDE si vuelve a escribir el modelo con JsonUtility.ToJson
# (el reanalisis y 'Guardar JSON' del editor). La direccion contraria
# -- un campo C# sin clave, que queda en su valor por defecto -- no la
# cubre este bloque: en parte la cubre [2], que exige datos en los
# campos que el visor usa, y para el anexo de la Semana 4 la cubre
# semana04/test_contrato_semana04.py, que revisa las dos direcciones.
#
# Estas claves se dejan fuera del C# a proposito; son datos de analisis
# o de procedencia que Unity no dibuja:
#
#   enfierradura                                 el fierro, para la capacidad
#   E, G, E_del_cuerpo, fpc_MPa, b_h_deducidos  el hormigon por cuerpo del
#                                               conjunto; Unity no calcula
#   incluye_peso_propio                          separa losa de peso propio
#   forma                                        procedencia del poligono
#   cuerpos, extra                               de que edificios se armo;
#                                                la ficha del modelo
#
# area_tributaria y w_gravedad SI estan en el C# desde la Semana 5: el
# inspector muestra el area total de la viga, que en Ingenieria reparte
# en varias entradas de areas_tributarias.
NO_VAN_AL_CSHARP = {
    'ModeloEstructural': ('resumen',),
    'InfoModelo': ('cuerpos', 'extra'),
    'Elemento': ('enfierradura',),
    'Seccion': ('E', 'G', 'E_del_cuerpo', 'fpc_MPa', 'b_h_deducidos'),
    'AreaTributaria': ('forma',),
    'CasoDeCarga': ('incluye_peso_propio',),
}

# Las claves de TODOS los objetos de cada lista, no solo las del primero:
# en Ingenieria el primer elemento es una columna y solo los muros traen
# largo/espesor/dir_largo; en el conjunto solo las entradas del LT2
# traen qG, w y luz. Mirar el primero dejaba esas claves sin revisar.
def claves(lista):
    todas = set()
    for o in lista:
        todas |= set(o.keys())
    return sorted(todas)


comparar('ModeloEstructural', datos.keys(),
         ignorar=NO_VAN_AL_CSHARP['ModeloEstructural'])
comparar('Nodo', claves(datos['nodos']))
comparar('Elemento', claves(datos['elementos']),
         ignorar=NO_VAN_AL_CSHARP['Elemento'])
comparar('Seccion', claves(datos['secciones']),
         ignorar=NO_VAN_AL_CSHARP['Seccion'])
comparar('Diafragma', claves(datos['diafragmas']))
comparar('AreaTributaria', claves(datos['areas_tributarias']),
         ignorar=NO_VAN_AL_CSHARP['AreaTributaria'])
# Los poligonos tributarios son opcionales: un modelo puede exportar el
# AREA de cada viga pero todavia no el poligono, porque sus panos no
# vienen de una grilla sino de las caras del grafo de vigas. Si no hay
# poligonos se dice; no se aprueba por vacio.
_vert = [v for t in datos['areas_tributarias'] for v in t['vertices']]
if _vert:
    comparar('VerticePlanta', claves(_vert))
else:
    print("  [--  ] VerticePlanta: no hay poligonos tributarios exportados "
          "(el visor no dibuja esa capa)")
comparar('CasoDeCarga', claves(datos['casos_de_carga']),
         ignorar=NO_VAN_AL_CSHARP['CasoDeCarga'])
comparar('CargaDistribuida',
         claves([c for caso in datos['casos_de_carga']
                 for c in caso.get('cargas_distribuidas', [])]))
_nodales = [c for caso in datos['casos_de_carga'] for c in caso.get('cargas_nodales', [])]
if _nodales:
    comparar('CargaNodal', claves(_nodales))
comparar('InfoModelo', datos['info'].keys(),
         ignorar=NO_VAN_AL_CSHARP['InfoModelo'])


# ============================================================
print("\n[2] Los campos que Unity necesita SI traen datos")
# ============================================================
# Un campo presente pero vacio es igual de malo que uno ausente: se
# dibuja "algo" y parece que funciona.
e0 = datos['elementos'][0]
check(e0.get('localX') and len(e0['localX']) == 3,
      "los elementos traen ejes locales calculados")
check(any(n['fijo'] for n in datos['nodos']),
      "hay nodos marcados como apoyo")
check(len(datos['diafragmas']) > 0, "hay diafragmas exportados")
check(len(datos['areas_tributarias']) > 0, "hay areas tributarias exportadas")

# El suelo del visor (AmbienteVisor) va en info.cota_terreno. Si la clave
# falta, JsonUtility deja -9999 sin avisar y el visor pone el suelo en el
# apoyo mas bajo: un subterraneo quedaria sobre el terreno. No todo
# edificio la declara (su perfil decide), asi que su ausencia se dice.
if 'cota_terreno' in datos['info']:
    _cota = datos['info']['cota_terreno']
    check(isinstance(_cota, (int, float)) and _cota > -9000,
          "info.cota_terreno es una cota real (%s m): ahi va el suelo" % _cota)
else:
    print("  [--  ] info.cota_terreno no viene: el visor pone el suelo en "
          "el apoyo mas bajo, con aviso en la consola")

t0 = datos['areas_tributarias'][0]
check(t0['area'] > 0, "las areas tributarias traen area")

# Los POLIGONOS son opcionales en un modelo y obligatorios en el
# del P1L2. Aca la planta no viene de una grilla: los panos son las
# caras del grafo de vigas, y recortar el poligono tributario de cada
# tramo dentro de un pano irregular todavia no esta hecho.
#
# Se declara PENDIENTE, no se aprueba por vacio: si algun dia se
# exportan poligonos, todos los chequeos de abajo se activan solos y
# vuelven a proteger contra el bug de los tamanos mezclados.
HAY_POLIGONOS = any(t['vertices'] for t in datos['areas_tributarias'])
if not HAY_POLIGONOS:
    print("  [PEND] no se exportan poligonos tributarios: el visor no dibuja")
    print("         esa capa. El area y la carga por viga SI estan.")


# ------------------------------------------------------------
# Los poligonos NO miden todos lo mismo: una viga interior toma un
# TRAPECIO de un pano (4 vertices) y un TRIANGULO del otro (3).
# Sin 'tamanos', Unity partia los vertices por division entera
# (7 / 2 = 3) y dibujaba lineas cruzadas que no existen. Este bloque
# existe para que ese bug no vuelva.
# ------------------------------------------------------------
if HAY_POLIGONOS:
    sin_tam = [t['elemento'] for t in datos['areas_tributarias']
               if t['vertices'] and not t.get('tamanos')]
    check(not sin_tam,
          "toda area tributaria declara el tamano de cada poligono",
          f"sin 'tamanos': {len(sin_tam)}" if sin_tam else "")

descuadres = [t['elemento'] for t in datos['areas_tributarias']
              if sum(t.get('tamanos', [])) != len(t['vertices'])]
check(not descuadres,
      "sum(tamanos) = cantidad de vertices",
      f"descuadrados: {descuadres[:5]}" if descuadres else "")

degenerados = [t['elemento'] for t in datos['areas_tributarias']
               if any(k < 3 for k in t.get('tamanos', []))]
check(not degenerados,
      "ningun poligono tiene menos de 3 vertices")

mal_contados = [t['elemento'] for t in datos['areas_tributarias']
                if len(t.get('tamanos', [])) != t['n_poligonos']]
check(not mal_contados,
      "len(tamanos) = n_poligonos")

# El caso que estaba roto tiene que existir de verdad en los datos; si
# no, este test estaria pasando por vacio.
# Solo tiene sentido si el exportador CONCATENA los poligonos de una
# viga (LT2). El de Ingenieria emite uno por entrada y ahi no hay nada
# que mezclar: no es un fallo, es otro formato.
CONCATENA = any(t.get('n_poligonos', 1) > 1 for t in datos['areas_tributarias'])
if HAY_POLIGONOS and not CONCATENA:
    print("  [--  ] este exportador emite un poligono por entrada: no aplica "
          "el chequeo de trapecio + triangulo")
if HAY_POLIGONOS and CONCATENA:
    mixtos = [t for t in datos['areas_tributarias']
              if len(set(t.get('tamanos', []))) > 1]
    check(len(mixtos) > 0,
          "hay vigas con poligonos de distinto tamano (el caso que fallaba)",
          f"{len(mixtos)} vigas mezclan trapecio y triangulo")

# ------------------------------------------------------------
# Muros: sin largo/espesor el visor los dibuja como columnas flacas.
# ------------------------------------------------------------
muros = [e for e in datos['elementos'] if e['tipo'] == 'muro']
if muros:
    sin_geom = [m['id'] for m in muros
                if m.get('largo', 0) <= 0 or m.get('espesor', 0) <= 0]
    check(not sin_geom,
          "los muros traen largo y espesor para dibujarlos",
          f"sin geometria: {len(sin_geom)}" if sin_geom else "")

    sin_vec = [m['id'] for m in muros
               if not m.get('vecxz') or len(m['vecxz']) < 3]
    check(not sin_vec,
          "los muros traen vecxz (orientacion de su eje fuerte)")


# ============================================================
print("\n[3] Coherencia numerica de lo exportado")
# ============================================================
# w, luz y qG por poligono los emite el exportador del LT2. Sin ellos
# la conservacion w*L = q*A se comprueba en comun/verificar_tributarias.py
# a partir del modelo, que es donde aplica a cualquier edificio.
#
# El conjunto mezcla: las entradas del LT2 traen la carga y las de
# Ingenieria no. Por eso se revisan las que la traen y las otras se
# declaran PENDIENTES, en vez de saltarse el chequeo entero (lo que
# hacia antes) o de aprobarlas por vacio: en Unity esos campos quedan
# en 0 y el inspector escribiria un "w*L = q*A" de 0 = 0.
CARGA = ('w', 'luz', 'qG')
con_carga = [t for t in datos['areas_tributarias'] if all(k in t for k in CARGA)]
sin_carga = [t for t in datos['areas_tributarias'] if not all(k in t for k in CARGA)]
if con_carga:
    peor = 0.0
    for t in con_carga:
        peor = max(peor, abs(t['w'] * t['luz'] - t['qG'] * t['area']))
    check(peor < 1e-3,
          f"en el JSON se cumple w*L = q*A viga por viga "
          f"({len(con_carga)} entradas con carga)",
          f"peor error {peor:.3e} kN")
    en_cero = [t['elemento'] for t in con_carga
               if not (t['qG'] > 0 and t['w'] > 0 and t['luz'] > 0)]
    check(not en_cero,
          "las entradas que traen qG, w y luz los traen distintos de cero",
          f"en cero: {en_cero[:5]}" if en_cero else "")
if sin_carga:
    print(f"  [PEND] {len(sin_carga)} de {len(datos['areas_tributarias'])} "
          f"entradas de area tributaria no traen qG, w ni luz:")
    print("         en Unity quedan en 0 y el inspector no puede mostrar la")
    print("         carga por viga. Falta en el exportador de ese edificio; la")
    print("         conservacion se verifica en comun/verificar_tributarias.py")
if not datos['areas_tributarias']:
    print("  [--  ] no hay areas tributarias exportadas")


# ------------------------------------------------------------
# El AREA de una viga, en sus dos lugares. Ingenieria (y el conjunto)
# reparten una viga en varias entradas -- un trapecio por pano -- y
# ademas sellan el total en el elemento, 'area_tributaria'. El
# inspector de Unity (ModeloEstructural.AreaTributariaTotal) lee el
# total si esta y si no suma las entradas: tienen que ser el mismo
# numero, o el panel diria distinto segun el edificio.
#
# Cota medida contra sus dos causas:
#  - el redondeo del exportador: un valor con d decimales viene
#    redondeado a d o mas, asi que se aleja del real a lo sumo
#    0.5*10^-d. Con n entradas mas el total son n+1 redondeos. d es el
#    maximo de decimales que muestran los valores de esa viga. En
#    Ingenieria el total y las entradas salen de DOS cuentas distintas
#    del mismo pano -- el total con Lx, Ly del pano
#    (benchmark_3d.tributarias) y cada entrada con la formula del
#    cordon sobre su poligono -- redondeadas cada una a 4 decimales
#    (edificios/ingenieria/export_unity.py:176 y :435). Pueden caer a
#    los dos lados del redondeo: la viga 128 da 8.3971 contra 8.3972,
#    una unidad, que es justo la cota con n = 1.
#  - la coma flotante de esas cuentas antes de redondear: la formula
#    del cordon suma productos de coordenadas, con error de hasta
#    k * c^2 * eps (k vertices, c la mayor coordenada). Por redondeo se
#    suma 4 * k * c^2 * eps, con los k y c que trae el JSON.
def _decimales(v):
    import decimal
    exp = decimal.Decimal(repr(float(v))).normalize().as_tuple().exponent
    return max(0, -int(exp))


entradas_de = {}
for t in datos['areas_tributarias']:
    entradas_de.setdefault(t['elemento'], []).append(float(t['area']))
elem_de = {e['id']: e for e in datos['elementos']}
con_total = {eid: v for eid, v in entradas_de.items()
             if 'area_tributaria' in elem_de.get(eid, {})}
if con_total:
    _c = max([abs(float(v)) for t in datos['areas_tributarias']
              for p in t['vertices'] for v in (p['x'], p['y'])]
             + [abs(float(n[k])) for n in datos['nodos'] for k in ('x', 'y')])
    _k = max([k for t in datos['areas_tributarias'] for k in t.get('tamanos', [])] + [3])
    flotante = 4 * _k * _c * _c * sys.float_info.epsilon
    peor_q, peor_id, fuera = 0.0, None, []
    for eid, areas in con_total.items():
        total = float(elem_de[eid]['area_tributaria'])
        d = max(_decimales(a) for a in areas + [total])
        cota = (len(areas) + 1) * (0.5 * 10.0 ** -d + flotante)
        q = abs(sum(areas) - total) / cota
        if q > peor_q:
            peor_q, peor_id = q, eid
        if q > 1.0:
            fuera.append(eid)
    sin_entradas = [e['id'] for e in datos['elementos']
                    if float(e.get('area_tributaria') or 0.0) > 0.0
                    and e['id'] not in entradas_de]
    varias = sum(1 for v in con_total.values() if len(v) > 1)
    check(not fuera and not sin_entradas,
          f"suma de las entradas de cada viga = elemento.area_tributaria "
          f"({len(con_total)} vigas, {varias} con mas de una entrada)",
          f"peor error/cota {peor_q:.6f} (viga {peor_id})"
          + (f"; fuera de cota: {fuera[:5]}" if fuera else "")
          + (f"; con area y sin entradas: {sin_entradas[:5]}" if sin_entradas else ""))
elif entradas_de:
    print(f"  [--  ] los elementos no traen area_tributaria: el area de la viga "
          f"es la suma de sus entradas (a lo sumo "
          f"{max(len(v) for v in entradas_de.values())} por viga en este edificio)")

r = datos.get('resumen') or {}
if 'error_equilibrio_kN' in r:
    check(r['error_equilibrio_kN'] < 1e-6,
          "el resumen reporta equilibrio cerrado",
          f"error {r['error_equilibrio_kN']:.3e} kN")
else:
    print("  [--  ] el resumen de este edificio no trae error_equilibrio_kN; "
          "el equilibrio lo verifica comun/calcular.py")

ids = [e['id'] for e in datos['elementos']]
check(len(ids) == len(set(ids)), "los elementTag son unicos")
ids_n = [n['id'] for n in datos['nodos']]
check(len(ids_n) == len(set(ids_n)), "los nodeTag son unicos")

nodos_set = set(ids_n)
huerfanos = [e['id'] for e in datos['elementos']
             if e['n1'] not in nodos_set or e['n2'] not in nodos_set]
check(not huerfanos,
      "todos los elementos referencian nodos existentes",
      f"huerfanos: {huerfanos[:5]}" if huerfanos else "")

tags = set(ids)
trib_malas = [t['elemento'] for t in datos['areas_tributarias']
              if t['elemento'] not in tags]
check(not trib_malas,
      "toda area tributaria apunta a un elemento existente")


# ------------------------------------------------------------
# "QUE LO CARGA" COMPLETO: losa + peso propio = lo que recibe OpenSees.
# El panel daba w 15.749 kN/m (solo la losa) y el diagrama wz de G
# -27.749: los 12.000 de peso propio no se explicaban. El LT2 exporta en
# cada entrada de viga o brazo 'w_peso_propio' y 'w_total_G', leidos de
# lo que su modelo le paso a eleLoad (edificios/lt2/exportar_unity.py);
# el conjunto los copia de esas entradas. Aca se exige, entrada por
# entrada:
#   w + w_peso_propio = w_total_G
#   w_total_G = -wz de la carga repartida de G de esa barra en
#               casos_de_carga (lo que manda /analizar a OpenSees)
#
# Cota medida contra el redondeo del exportador: un valor con d decimales
# se aleja del real a lo sumo 0.5*10^-d. La suma lleva tres valores
# redondeados (3 medios escalones) y la comparacion con wz dos. Se agrega
# la coma flotante de la suma: 4*eps*|w_total_G|.
#
# Un muro no lleva estas claves (su losa y su peso propio llegan como
# cargas NODALES, no hay w repartida): se dice. Un edificio que no las
# exporta (Ingenieria) queda PEND, no FALLA ni se aprueba por vacio.
_cs_trib = clases.get('AreaTributaria', set())
check('w_peso_propio' in _cs_trib and 'w_total_G' in _cs_trib,
      "AreaTributaria del C# tiene w_peso_propio y w_total_G")

PESO = ('w_peso_propio', 'w_total_G')
con_peso = [t for t in datos['areas_tributarias'] if all(k in t for k in PESO)]
sin_peso = [t for t in datos['areas_tributarias'] if not all(k in t for k in PESO)]
wz_de_G = {}
for _caso in datos['casos_de_carga']:
    if _caso['nombre'] == 'G':
        for _c in _caso.get('cargas_distribuidas', []):
            wz_de_G[int(_c['elemento'])] = float(_c.get('wz', 0.0))
if con_peso:
    peor_suma = peor_suma_q = peor_wz = peor_wz_q = 0.0
    fuera_suma, fuera_wz, sin_wz = [], [], []
    for t in con_peso:
        w, pp, tot = float(t['w']), float(t['w_peso_propio']), float(t['w_total_G'])
        flot = 4 * sys.float_info.epsilon * abs(tot)
        d = max(_decimales(v) for v in (w, pp, tot))
        err = abs(w + pp - tot)
        q = err / (3 * 0.5 * 10.0 ** -d + flot)
        peor_suma, peor_suma_q = max(peor_suma, err), max(peor_suma_q, q)
        if q > 1.0:
            fuera_suma.append(t['elemento'])
        wz = wz_de_G.get(int(t['elemento']))
        if wz is None:
            sin_wz.append(t['elemento'])
            continue
        d = max(_decimales(tot), _decimales(wz))
        err = abs(-wz - tot)
        q = err / (2 * 0.5 * 10.0 ** -d + flot)
        peor_wz, peor_wz_q = max(peor_wz, err), max(peor_wz_q, q)
        if q > 1.0:
            fuera_wz.append(t['elemento'])
    check(not fuera_suma,
          f"w (losa) + w_peso_propio = w_total_G en cada entrada "
          f"({len(con_peso)} entradas)",
          f"peor error {peor_suma:.1e} kN/m, error/cota {peor_suma_q:.3f}"
          + (f"; fuera de cota: {fuera_suma[:5]}" if fuera_suma else ""))
    check(not fuera_wz and not sin_wz,
          "w_total_G = -wz de la carga repartida de G de la misma barra "
          "(lo que recibe OpenSees)",
          f"peor error {peor_wz:.1e} kN/m, error/cota {peor_wz_q:.3f}"
          + (f"; fuera de cota: {fuera_wz[:5]}" if fuera_wz else "")
          + (f"; sin carga repartida en G: {sin_wz[:5]}" if sin_wz else ""))
if sin_peso:
    _tipo = {e['id']: e.get('tipo', '') for e in datos['elementos']}
    _muros = [t for t in sin_peso if _tipo.get(t['elemento']) == 'muro'
              and int(t['elemento']) not in wz_de_G]
    # Solo cuenta como "muro, no aplica" si el edificio si los exporta.
    if not con_peso:
        _muros = []
    if _muros:
        print(f"  [--  ] {len(_muros)} entradas de muro sin w_peso_propio ni "
              f"w_total_G: su losa y su peso propio llegan como cargas")
        print("         nodales, no hay w repartida que separar")
    _pend = len(sin_peso) - len(_muros)
    if _pend:
        print(f"  [PEND] {_pend} de {len(datos['areas_tributarias'])} "
              f"entradas no traen w_peso_propio ni w_total_G: el panel")
        print("         no puede separar la losa del peso propio (falta en el")
        print("         exportador de ese edificio; el C# los deja en 0 y lo dice)")


# ============================================================
print("\n" + "=" * 60)
if fallos:
    print(f"FALLARON {len(fallos)}:")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("EL CONTRATO JSON <-> UNITY ESTA SANO")
print("=" * 60)
