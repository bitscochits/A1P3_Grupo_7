# -*- coding: utf-8 -*-
r"""
================================================================
 semana04/trazabilidad.py  -  UN ELEMENTO, DE OPENSEES A UNITY
================================================================
 Imprime la cadena completa de UN elemento, sacada de Python y no
 del JSON, y despues la compara contra data/unity/semana04.json para
 decir si cada numero calza con lo que Unity lee:

   (a) OpenSees    el 'element elasticBeamColumn' tal como se lo pasa
                   comun/servidor_opensees.py al motor -- capturado en
                   la llamada, no reescrito aca -- y lo que el motor
                   guardo (su rigidez basica)
   (b) modelo      tipo, seccion, nodos con coordenadas, restricciones
                   y diafragma, ejes locales
   (c) Unity       el GameObject "Elem_<id>_<tipo>" y su DatoElemento
   (d) resultados  f del caso pedido y N, V, T, M en i y en j
   (e) capacidad   familia, curva P-M y la demanda con su u

 Correr:
   python semana04/trazabilidad.py ingenieria 18
   python semana04/trazabilidad.py ingenieria 427 --caso 1.2G+1.0Q+1.4EX
   python semana04/trazabilidad.py lt2 1 --cs 0.20
   python semana04/trazabilidad.py conjunto 200005

 Los flags son los de semana03/parametros.py (--q, --cs, --patron,
 --combinacion ...) mas --caso NOMBRE. Sin --caso, el caso por
 defecto de los parametros (S3), que es el que abre el visor.

 CONTRA QUE SE COMPARA. Si data/unity/semana04.json es de este
 edificio y con estos parametros, contra el archivo: es lo que Unity
 lee. Si no, contra el anexo que armaria semana04/exportar_unity.py
 (construir_anexo) en memoria, pasado por json.dumps/loads, SIN
 escribirlo: el StreamingAssets es compartido y pisarlo cambiaria lo
 que esta abriendo el visor.

 ----------------------------------------------------------------
 POR QUE SE CAPTURA LA LLAMADA A OPENSEES EN VEZ DE REARMARLA
 ----------------------------------------------------------------
 El servidor decide tres cosas por elemento que no estan escritas en
 el contrato: el E y el G (el del material o el propio de la
 seccion), el vecxz (por geometria) y el ORDEN de las inercias (las
 cruza en los no verticales). Rearmar esas reglas aca seria una
 segunda copia que puede divergir en silencio. En cambio se envuelve
 ops.element y ops.geomTransf mientras construir_modelo() corre, y se
 anota exactamente lo que recibio el motor. Despues se le pregunta al
 propio OpenSees su rigidez basica (EA/L, 4EIz/L, 4EIy/L, GJ/L): es
 el dato que de verdad usa para resolver.

 Las funciones de este modulo las reutiliza verificar_semana04.py: la
 regla del nombre del GameObject, la captura de OpenSees y las cotas
 de redondeo medidas. No cambiarles el nombre sin mirar alla.
================================================================
"""
from __future__ import annotations

import importlib.util
import io
import json
import math
import os
import re
import struct
import sys
import tempfile

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_AQUI), 'comun'))
import rutas                                 # noqa: E402
rutas.entrar(__file__, os.path.join(rutas.RAIZ, 'semana03'))

import capacidad                             # noqa: E402
import combinar                              # noqa: E402
import contrato                              # noqa: E402
import servidor_opensees as motor            # noqa: E402
import lab_semana03 as lab                   # noqa: E402
import parametros                            # noqa: E402
import demanda_capacidad as dc               # noqa: E402

ANEXO = os.path.join(rutas.UNITY, 'semana04.json')
VISOR_CS = os.path.join(rutas.UNITY_PROYECTO, 'Assets', 'Scripts',
                        'VisorEstructura.cs')
# La regla con que VisorEstructura.Redibujar nombra cada barra. Se
# busca LITERAL en el C#: si alguien la cambia alla, objeto_unity del
# anexo deja de apuntar a un GameObject que exista y nada falla.
LITERAL_NOMBRE = '"Elem_" + e.id + "_" + e.tipo'
COMPONENTES = ('N', 'Vy', 'Vz', 'T', 'My', 'Mz')
EPS64 = sys.float_info.epsilon


# ============================================================
# EL EXPORTADOR DE SEMANA 4, POR RUTA
# ============================================================
def exportador():
    r"""
    semana04/exportar_unity.py cargado POR RUTA.

    No se puede hacer 'import exportar_unity': semana03/ tiene un
    modulo con el mismo nombre, y lab_semana03 y demanda_capacidad
    ponen semana03/ al principio de sys.path al importarse. El import
    por nombre traeria el de la Semana 3 sin ningun error, y cada
    funcion que se le pida faltaria o haria otra cosa.
    """
    nombre = 'exportar_unity_semana04'
    if nombre in sys.modules:
        return sys.modules[nombre]
    ruta = os.path.join(_AQUI, 'exportar_unity.py')
    if not os.path.isfile(ruta):
        raise SystemExit('falta %s: lo escribe la API del contrato de la '
                         'Semana 4' % os.path.relpath(ruta, rutas.RAIZ))
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = mod
    spec.loader.exec_module(mod)
    return mod


# ============================================================
# COTAS MEDIDAS
# ============================================================
def a_float32(x):
    """El valor que queda en un float de C#: el double mas cercano."""
    return struct.unpack('<f', struct.pack('<f', float(x)))[0]


def medio_ulp32(x):
    r"""
    Lo mas que se mueve un double al guardarlo en float32: medio
    intervalo entre floats vecinos. Con mantisa de 24 bits el intervalo
    en |x| en [2^(e-1), 2^e) es 2^(e-24), asi que el error relativo es a
    lo mas 2^-24 = 6e-8.
    """
    f = abs(a_float32(x))
    if f == 0.0:
        return 2.0 ** -150
    _m, e = math.frexp(f)
    return 2.0 ** (e - 24) / 2.0


def medio_digito_de_texto(texto):
    """Medio ultimo digito de un numero ESCRITO: '2.4870e+07' -> 5e2."""
    s = str(texto).strip().lower()
    exp = 0
    if 'e' in s:
        s, e = s.split('e', 1)
        exp = int(e)
    dec = len(s.split('.', 1)[1]) if '.' in s else 0
    return 0.5 * 10.0 ** (exp - dec)


def medio_ultimo_decimal(valores):
    r"""
    Con cuantos decimales viene escrita una FAMILIA de valores, como
    medio ultimo decimal. Reutiliza combinar.decimales_de, que es la
    que mide el redondeo del servidor. Se mide sobre la familia entera
    y no valor por valor: 0.25 tiene dos decimales porque es 0.25, no
    porque este redondeado.
    """
    vals = [float(v) for v in valores if not isinstance(v, bool)]
    d = combinar.decimales_de({'v': [{'f': vals}]}, 'v', None)
    return 0.5 * 10.0 ** -d if d else 0.0


def calza(a, b, cota):
    """|a - b| <= cota, con el piso de la aritmetica doble encima."""
    return abs(float(a) - float(b)) <= cota + 2.0 * EPS64 * max(
        abs(float(a)), abs(float(b)))


# ============================================================
# OPENSEES: LO QUE RECIBE EL MOTOR
# ============================================================
def capturar_opensees(datos):
    r"""
    Corre servidor_opensees.construir_modelo(datos) anotando cada
    geomTransf y cada elasticBeamColumn TAL COMO LLEGAN al motor.

    Devuelve {'elementos': {id: {n1, n2, A, E, G, J, Iy, Iz, transf,
    vecxz}}, 'restringidos': {nodo: [6]}, 'coords', 'avisos'}. Iy e Iz
    son las de la POSICION en que el servidor las pasa. El modelo queda
    armado en OpenSees, para poder preguntarle su rigidez.
    """
    ops = motor.ops
    original_elem, original_transf = ops.element, ops.geomTransf
    transf, elementos = {}, {}

    def geom(*a):
        transf[int(a[1])] = tuple(float(v) for v in a[2:5])
        return original_transf(*a)

    def elem(*a):
        if a[0] == 'elasticBeamColumn':
            eid, n1, n2, A, E, G, J, Iy, Iz, t = a[1:11]
            elementos[int(eid)] = {
                'n1': int(n1), 'n2': int(n2), 'A': float(A), 'E': float(E),
                'G': float(G), 'J': float(J), 'Iy': float(Iy),
                'Iz': float(Iz), 'transf': int(t)}
        return original_elem(*a)

    ops.element, ops.geomTransf = elem, geom
    try:
        coords, avisos, restringidos = motor.construir_modelo(datos)
    finally:
        ops.element, ops.geomTransf = original_elem, original_transf
    for d in elementos.values():
        d['vecxz'] = transf[d['transf']]
    return {'elementos': elementos, 'restringidos': restringidos,
            'coords': coords, 'avisos': avisos}


def rigidez_basica(eid):
    r"""
    La rigidez basica 6x6 que OpenSees guarda para el elemento, en el
    orden [axial, flexion z (2), flexion y (2), torsion]. Hay que
    llamarla con el modelo de capturar_opensees() todavia armado.
    """
    k = motor.ops.eleResponse(int(eid), 'basicStiffness')
    return {'EA_L': k[0], '4EIz_L': k[7], '4EIy_L': k[21], 'GJ_L': k[35]}


# ============================================================
# UNITY: EL NOMBRE DEL GAMEOBJECT
# ============================================================
def nombre_objeto(e):
    """El nombre que le pone VisorEstructura.Redibujar a la barra."""
    return 'Elem_%d_%s' % (int(e['id']), e['tipo'])


def regla_de_nombre_en_visor():
    r"""
    (numero de linea, linea) donde VisorEstructura.cs nombra la barra
    con LITERAL_NOMBRE, o (None, None). Los comentarios se vacian
    conservando los saltos de linea, para que un ejemplo en una nota no
    cuente como codigo.
    """
    with io.open(VISOR_CS, encoding='utf-8') as f:
        src = f.read()
    src = re.sub(r'/\*.*?\*/', lambda m: '\n' * m.group(0).count('\n'),
                 src, flags=re.S)
    for i, linea in enumerate(src.splitlines(), 1):
        codigo = linea.split('//', 1)[0]
        if LITERAL_NOMBRE in codigo and '.name' in codigo:
            return i, codigo.strip()
    return None, None


# ============================================================
# EL MODELO
# ============================================================
def maestro_de_nodo(modelo):
    """{nodo: nodo maestro del diafragma al que pertenece}."""
    salida = {}
    for d in modelo.get('diafragmas', []):
        m = int(d['nodo_maestro'])
        salida[m] = m
        for n in d.get('nodos', []):
            salida.setdefault(int(n), m)
    return salida


def casos_y_factores(p):
    """[(nombre, {G, Q, EX, EY})]: los cuatro casos y las combinaciones."""
    salida = [(c, {k: (1.0 if k == c else 0.0) for k in dc.CASOS})
              for c in dc.CASOS]
    combos = list(p['combinaciones'])
    if p['combinacion'].get('nombre') not in [c['nombre'] for c in combos]:
        combos.append(p['combinacion'])
    return salida + [(c['nombre'], parametros.factores(c)) for c in combos]


def _v(v):
    return ' '.join('%d' % x for x in v)


class AvisosDeOpenSees(object):
    r"""
    Junta lo que OpenSees escribe en stderr mientras corre el bloque.

    La curva P-M sale de momento-curvatura hasta la falla, y Newton se
    atasca justo en el peak del hormigon: OpenSees imprime 'analyze
    failed' y capacidad.momento_curvatura lo rescata con ModifiedNewton
    y pasos chicos (comun/capacidad.py, el bloque 'rescatado'). Son
    avisos esperados, pero en una defensa en vivo tapan la salida. No
    se esconden: se cuentan y se dice de donde vienen.

    OpenSees escribe desde C++ al DESCRIPTOR 2, no a sys.stderr, asi que
    hay que redirigir el descriptor y no el objeto de Python.
    """

    def __enter__(self):
        sys.stderr.flush()
        self._tmp = tempfile.TemporaryFile()
        self._copia = os.dup(2)
        os.dup2(self._tmp.fileno(), 2)
        return self

    def __exit__(self, *exc):
        sys.stderr.flush()
        os.dup2(self._copia, 2)
        os.close(self._copia)
        self._tmp.seek(0)
        self.texto = self._tmp.read().decode('utf-8', 'replace')
        self._tmp.close()
        self.fallos = self.texto.count('analyze failed')
        return False

    def resumen(self):
        if not self.texto.strip():
            return None
        return ('OpenSees aviso %d vez(ces) "analyze failed" dentro de '
                'capacidad.interaccion: es el M-phi que se atasca en el peak '
                'del hormigon; se rescata con ModifiedNewton y, si no, el '
                'motivo queda en la curva' % self.fallos)


def explicar_restriccion(edificio, nid, r, maestro):
    r"""
    Por que un nodo tiene esas restricciones, en palabras. r es la lista
    [ux uy uz rx ry rz] que el servidor le pasa a ops.fix; maestro es el
    nodo maestro de su diafragma o None.
    """
    r = [int(v) for v in r]
    if not any(r):
        return 'libre' + ('' if maestro is None else
                          ': ux, uy y rz los manda el diafragma rigido')
    if all(r):
        return 'empotrado: apoyo en la fundacion'
    if r == [0, 0, 1, 1, 1, 0]:
        if maestro == nid:
            return ('nodo maestro del diafragma: el servidor fija los GDL '
                    'fuera del plano del piso (uz, rx, ry)')
        texto = ('fija uz, rx, ry, los GDL que el diafragma NO toca; ux, uy '
                 'y rz los sigue mandando el piso rigido')
        # En el conjunto los nodos de Ingenieria se renumeran en 100000.
        de_ingenieria = (edificio == 'ingenieria' or
                         (edificio == 'conjunto' and 100000 <= nid < 200000))
        if de_ingenieria and maestro is not None:
            texto += ('. Es la losa del nivel 1 apoyada en el terreno donde '
                      'no hay subterraneo (edificios/ingenieria/'
                      'benchmark_3d.py, lineas 1015-1045): real, no un error')
        return texto
    return 'apoyo parcial [%s]' % _v(r)


def ancho_y_espesor(s):
    """(b, h) de la seccion; los muros de Ingenieria declaran espesor/largo."""
    return (float(s.get('b') or s.get('espesor') or 0.0),
            float(s.get('h') or s.get('largo') or 0.0))


def momento_en_el_plano(o):
    r"""
    'My' o 'Mz': el momento que flexiona un muro EN SU PLANO, leido de
    las inercias que de verdad recibe OpenSees. Flexion alrededor del
    eje local y la resiste Iy; la inercia grande es la del plano del
    muro. No depende de como cada edificio eligio el vecxz: el LT2 da
    la normal (Iz grande) e Ingenieria la direccion del largo (Iy
    grande).
    """
    return 'My' if o['Iy'] > o['Iz'] else 'Mz'


def fpc_de_E(E_kPa):
    """El f'c (MPa) que corresponde a un Ec = 4700 sqrt(f'c) 1000 kPa."""
    return (float(E_kPa) / 4.7e6) ** 2


def _tabla_de_comparacion(filas):
    """Imprime (etiqueta, python, json, cota) y devuelve cuantas no calzan."""
    malas = 0
    print('    %-28s %19s %19s %19s  %s' % ('', 'Python', 'JSON',
                                            'Unity (float32)', ''))
    for etiqueta, py, js, cota in filas:
        if isinstance(py, (str, bool)) or py is None or js is None:
            ok = (py == js)
            print('    %-28s %19s %19s %19s  %s'
                  % (etiqueta, py, js, js, 'calza' if ok else 'NO CALZA'))
        else:
            u32 = a_float32(js)
            ok = calza(py, u32, cota + medio_ulp32(js))
            print('    %-28s %19.10g %19.10g %19.10g  %s'
                  % (etiqueta, py, js, u32, 'calza' if ok else
                     'NO CALZA (dif %.2e, cota %.2e)' % (abs(py - u32), cota)))
        if not ok:
            malas += 1
    return malas


# ============================================================
def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2 or argv[0].startswith('-'):
        print(__doc__)
        return 1
    edificio, resto = argv[0], argv[2:]
    try:
        eid = int(argv[1])
    except ValueError:
        raise SystemExit('el segundo argumento es el numero de elemento')
    caso_pedido = None
    if '--caso' in resto:
        i = resto.index('--caso')
        if i + 1 >= len(resto):
            raise SystemExit('--caso necesita un nombre')
        caso_pedido = resto[i + 1]
        resto = resto[:i] + resto[i + 2:]

    p = parametros.cargar(resto)
    modelo = contrato.cargar_modelo(edificio)
    elementos = {int(e['id']): e for e in modelo['elementos']}
    if eid not in elementos:
        raise SystemExit('el elemento %d no existe en %s' % (eid, edificio))
    e = elementos[eid]
    nodos = {int(n['id']): n for n in modelo['nodos']}
    secciones = {s['nombre']: s for s in modelo['secciones']}
    sec_c = secciones[e['seccion']]

    casos = dict(casos_y_factores(p))
    caso_pedido = caso_pedido or p['combinacion']['nombre']
    if caso_pedido not in casos:
        raise SystemExit('no hay caso %r. Hay: %s'
                         % (caso_pedido, ', '.join(casos)))
    lambdas = casos[caso_pedido]

    eu = exportador()
    arm = lab.armar_casos(modelo, p)
    datos, resultados = lab.resolver(modelo, arm['casos'])

    print('=' * 78)
    print('  TRAZABILIDAD   %s, elemento %d, caso %s'
          % (edificio, eid, caso_pedido))
    print('=' * 78)
    print(parametros.describir(p))

    # ------------------------------------------------------------ (a)
    cap = capturar_opensees(datos)
    o = cap['elementos'][eid]
    k = rigidez_basica(eid)
    pi = cap['coords'][o['n1']]
    pj = cap['coords'][o['n2']]
    ejes, L = contrato.ejes_locales(pi, pj, o['vecxz'])
    print()
    print('(a) OPENSEES   capturado en la llamada de '
          'servidor_opensees.construir_modelo()')
    print('    ops.geomTransf(\'Linear\', %d, %r, %r, %r)'
          % ((o['transf'],) + o['vecxz']))
    print('    ops.element(\'elasticBeamColumn\', tag, iNode, jNode, A, E, G, '
          'J, Iy, Iz, transfTag)')
    print('    ops.element(\'elasticBeamColumn\', %d, %d, %d, %r, %r, %r, %r, '
          '%r, %r, %d)'
          % (eid, o['n1'], o['n2'], o['A'], o['E'], o['G'], o['J'],
             o['Iy'], o['Iz'], o['transf']))
    # Segunda lectura de las mismas reglas: la replica citada del
    # exportador. Si la captura y la replica no dicen lo mismo, el anexo
    # esta mostrando un elemento distinto del que resolvio OpenSees.
    k_eu = eu.rigidez_como_el_servidor(e, sec_c, pi, pj, modelo['material'])
    replica = [('E', k_eu['E'], o['E']), ('G', k_eu['G'], o['G']),
               ('Iy', k_eu['Iy_pasa'], o['Iy']),
               ('Iz', k_eu['Iz_pasa'], o['Iz'])] + [
        ('vecxz[%d]' % i, k_eu['vecxz'][i], o['vecxz'][i]) for i in range(3)]
    distintos = [n for n, a, b in replica if not calza(a, b, 0.0)]
    print('    %s: vertical=%s  %s'
          % ('elemento vertical (proyeccion horizontal / L < 1e-6)'
             if k_eu['vertical'] else 'elemento NO vertical',
             k_eu['vertical'],
             'la replica del exportador (rigidez_como_el_servidor) da lo '
             'mismo' if not distintos else
             'la replica del exportador NO CALZA en %s' % ', '.join(distintos)))
    if k_eu['vertical'] or float(sec_c['Iy']) == float(sec_c['Iz']):
        print('    inercias en su posicion: Iy e Iz del contrato van donde '
              'OpenSees las espera')
    else:
        print('    inercias CRUZADAS: en la posicion Iy va la Iz del contrato '
              '(gravedad, b h^3/12), porque')
        print('    el elemento no es vertical y vecxz=(0,0,1) deja el z local '
              'vertical')
    print('    E y G: %s' % ('propios de la seccion %r' % e['seccion']
                            if 'E' in sec_c else
                            'del material, Ec = 4700 sqrt(%g) * 1000 kPa'
                            % float(modelo['material']['fpc_MPa'])))
    print('    lo que OpenSees guardo (eleResponse basicStiffness):')
    print('      EA/L = %.6g   4EIz/L = %.6g   4EIy/L = %.6g   GJ/L = %.6g'
          % (k['EA_L'], k['4EIz_L'], k['4EIy_L'], k['GJ_L']))
    print('      de vuelta: E*A %.6g (pasado %.6g)  E*Iz %.6g (%.6g)  '
          'E*Iy %.6g (%.6g)  G*J %.6g (%.6g)'
          % (k['EA_L'] * L, o['E'] * o['A'], k['4EIz_L'] * L / 4,
             o['E'] * o['Iz'], k['4EIy_L'] * L / 4, o['E'] * o['Iy'],
             k['GJ_L'] * L, o['G'] * o['J']))

    # ------------------------------------------------------------ (b)
    maestros = maestro_de_nodo(modelo)
    print()
    print('(b) MODELO   data/modelo/%s.json' % edificio)
    b_s, h_s = ancho_y_espesor(sec_c)
    print('    tipo %s, seccion %s: A=%.6g Iy=%.6g (lateral) Iz=%.6g '
          '(gravedad) J=%.6g  b=%.3g h=%.3g m'
          % (e['tipo'], e['seccion'], sec_c['A'], sec_c['Iy'], sec_c['Iz'],
             sec_c['J'], b_s, h_s))
    restr_eu = eu.restricciones_como_el_servidor(modelo)
    for extremo, nid in (('i', o['n1']), ('j', o['n2'])):
        n = nodos[nid]
        m = maestros.get(nid)
        r = cap['restringidos'].get(nid, [0] * 6)
        print('    nodo %s = %-6d (%9.3f, %9.3f, %8.3f)  [ux uy uz rx ry rz] = '
              '[%s]  %s'
              % (extremo, nid, n['x'], n['y'], n['z'], _v(r),
                 'diafragma de maestro %d' % m if m is not None
                 else 'sin diafragma'))
        print('        %s' % explicar_restriccion(edificio, nid, r, m))
        if list(r) != list(restr_eu.get(nid, [0] * 6)):
            print('        OJO: restricciones_como_el_servidor da [%s]'
                  % _v(restr_eu.get(nid, [0] * 6)))
    print('    L = %.6f m;  vecxz = (%g, %g, %g) %s'
          % ((L,) + o['vecxz'] + ('del elemento' if e.get('vecxz')
                                  else 'por geometria',)))
    for eje in ('wx', 'wy', 'wz'):
        print('    %s local = (%+.6f, %+.6f, %+.6f)'
              % ((eje[1],) + tuple(ejes[eje])))
    if e['tipo'] in ('brazo', 'brazo_rigido'):
        print('    brazo rigido: barra x100 hasta la cara del muro, no '
              'rigidLink')

    # ------------------------------------------------------------ (c)
    unity = {}
    if os.path.isfile(rutas.unity(edificio)):
        with io.open(rutas.unity(edificio), encoding='utf-8') as f:
            unity = {int(x['id']): x for x in json.load(f)['elementos']}
    eu_el = unity.get(eid)
    linea, texto = regla_de_nombre_en_visor()
    print()
    print('(c) UNITY   data/unity/%s.json -> VisorEstructura' % edificio)
    if eu_el is None:
        print('    el elemento NO esta en data/unity/%s.json: Unity no lo '
              'dibuja' % edificio)
    else:
        print('    GameObject "%s"   DatoElemento.idElemento = %d'
              % (nombre_objeto(eu_el), int(eu_el['id'])))
        print('    n1 %s, n2 %s, tipo %s, seccion %s: %s con el modelo'
              % (eu_el['n1'], eu_el['n2'], eu_el['tipo'], eu_el['seccion'],
                 'iguales' if all(eu_el[c] == e[c] for c in
                                  ('n1', 'n2', 'tipo', 'seccion'))
                 else 'DISTINTOS'))
    print('    regla en VisorEstructura.cs linea %s: %s'
          % (linea, texto or 'NO ENCONTRADA (%s)' % LITERAL_NOMBRE))

    # ------------------------------------------------------------ (d)
    por_caso = dc.fuerzas_por_caso(resultados, eid)
    f = dc.combinar(por_caso, lambdas)
    w = [0.0, 0.0, 0.0]
    for c, lam in lambdas.items():
        wc = eu.cargas_por_elemento(arm['casos'][c]).get(eid, (0.0, 0.0, 0.0))
        for i in range(3):
            w[i] += lam * wc[i]
    cargada = any(abs(v) > 0.0 for v in w)
    xs = eu.estaciones(L, cargada)
    esf = eu.esfuerzos_internos(f, tuple(w), xs)
    desp = {int(d['id']): d for d in combinar.combinar_resultados(
        resultados, lambdas)['desplazamientos']}
    print()
    print('(d) RESULTADOS   lab_semana03.resolver() en memoria; caso %s = %s'
          % (caso_pedido, parametros.como_texto(lambdas)))
    print('    f (localForce, sobre el elemento, ejes locales):')
    print('      i: ' + '  '.join('%s=%.4f' % (c, v)
                                  for c, v in zip(COMPONENTES, f[:6])))
    print('      j: ' + '  '.join('%s=%.4f' % (c, v)
                                  for c, v in zip(COMPONENTES, f[6:])))
    print('    w local combinado (wx, wy, wz) = (%.4f, %.4f, %.4f) kN/m;  '
          '%d estaciones' % (w[0], w[1], w[2], len(xs)))
    print('    esfuerzos INTERNOS (N traccion +; My > 0 tracciona +z; '
          'Mz < 0 tracciona +y):')
    print('      %-10s' % 'x [m]' + ''.join('%12s' % c for c in COMPONENTES))
    for idx in sorted({0, len(xs) // 2, len(xs) - 1}):
        print('      %-10.4f' % xs[idx]
              + ''.join('%12.4f' % esf[c][idx] for c in COMPONENTES))
    # El cierre: las formulas evaluadas en x = L tienen que devolver f_j,
    # que OpenSees calculo por su lado. La cota es la del exportador,
    # medida contra su causa (redondeo del servidor por caso, x*V_i en
    # los momentos, y la coma flotante), no elegida a ojo.
    activos = {c: lam for c, lam in lambdas.items() if lam != 0.0}
    suma_lambdas = sum(abs(lam) for lam in activos.values())
    magnitudes = [0.0] * 6
    for c, lam in activos.items():
        wc = eu.cargas_por_elemento(arm['casos'][c]).get(eid, (0.0, 0.0, 0.0))
        m_c = eu.magnitudes_de_cierre(por_caso[c], wc, L)
        magnitudes = [a + abs(lam) * b for a, b in zip(magnitudes, m_c)]
    cotas = eu.cota_de_cierre(L, suma_lambdas, magnitudes)
    cociente, peor = eu.cociente_de_cierre(f, tuple(w), L, suma_lambdas,
                                           magnitudes)
    print('    cierre en x = L: las formulas en x = L tienen que devolver f_j, '
          'que OpenSees calculo aparte')
    print('      cota = 5e-5 * 2 (N, V, T) o 5e-5 * (2 + L) (My, Mz), por '
          'sum|lambda| = %g, + 4 eps * magnitud' % suma_lambdas)
    for k, c in enumerate(COMPONENTES):
        err = abs(esf[c][-1] - f[6 + k])
        print('      %-3s  esfuerzo(L) = %12.5f   f_j = %12.5f   error %.2e   '
              'cota %.2e  %s' % (c, esf[c][-1], f[6 + k], err, cotas[k],
                                 'ok' if err <= cotas[k] else 'NO CIERRA'))
    print('      peor error/cota = %.3f en %s  -> %s'
          % (cociente, peor, 'cierra' if cociente <= 1.0 else 'NO CIERRA'))
    for extremo, nid in (('i', o['n1']), ('j', o['n2'])):
        d = desp[nid]
        print('    u nodo %s: ux %.3e  uy %.3e  uz %.3e  rx %.3e  ry %.3e  '
              'rz %.3e' % (extremo, d['ux'], d['uy'], d['uz'], d['rx'],
                           d['ry'], d['rz']))

    # ------------------------------------------------------------ (e)
    print()
    print('(e) SECCION Y CAPACIDAD')
    demanda = curva = firma = None
    if not e.get('enfierradura'):
        print('    sin enfierradura: no tiene curva P-M (familia -1)')
    else:
        sec = capacidad.desde_elemento(modelo, eid)
        firma = dc.firma_de_seccion(e, sec)
        miembros = sorted(
            int(x['id']) for x in modelo['elementos']
            if x.get('enfierradura') and dc.firma_de_seccion(
                x, capacidad.desde_elemento(modelo, int(x['id']))) == firma)
        with AvisosDeOpenSees() as avisos:
            curva = capacidad.interaccion(sec)
        demanda = dc.demanda(f, e['tipo'],
                             dc.momento_en_el_plano_de(modelo, e)
                             if e['tipo'] == 'muro' else None)
        Mn = dc.capacidad_en(demanda['P_kN'], curva)
        demanda['Mn'] = Mn
        # El mismo umbral que demanda_capacidad.revisar y el exportador.
        demanda['u'] = demanda['M_kNm'] / Mn if Mn > 1e-9 else 9999.0
        print('\n'.join('    ' + x for x in sec.resumen().splitlines()))
        if avisos.resumen():
            print('    (%s)' % avisos.resumen())
        # f'c de la capacidad contra el E con que se resolvio: si la
        # seccion trae E propio (conjunto), el f'c que le corresponde es
        # (E / 4700 / 1000)^2. La cota es lo que mueve el redondeo a 4
        # decimales del E escrito: d f'c = 2 f'c dE / E.
        if sec_c.get('E'):
            fpc_E = fpc_de_E(sec_c['E'])
            cota_fpc = 2.0 * fpc_E * 5e-5 / float(sec_c['E']) + 1e-9
            fpc_cap = sec.fpc / 1000.0
            if abs(fpc_cap - fpc_E) > cota_fpc:
                print('    OJO: la seccion se resuelve con E = %.1f kPa, que '
                      "es f'c = %.2f MPa, pero la curva usa f'c = %.2f MPa"
                      % (float(sec_c['E']), fpc_E, fpc_cap))
                print("         (comun/capacidad.py toma el f'c de "
                      "modelo['material'], uno solo para todo el conjunto)")
        print('    familia (demanda_capacidad.firma_de_seccion): %s' % (firma,))
        print('    %d elementos la comparten: %s%s'
              % (len(miembros), miembros[:12],
                 ' ...' if len(miembros) > 12 else ''))
        print('    curva (capacidad.interaccion):')
        for pt in curva:
            print('      P = %10.1f kN   Mn = %9.1f kN m   %s'
                  % (pt['P_kN'], pt['M_kNm'], pt['de']))
        print('    demanda en %s: P = %.1f kN, M = %.1f kN m%s, extremo %s'
              % (caso_pedido, demanda['P_kN'], demanda['M_kNm'],
                 ('' if demanda['M_fuera_de_plano_kNm'] is None else
                  ', fuera de plano %.1f' % demanda['M_fuera_de_plano_kNm']),
                 demanda['extremo']))
        P_min = min(float(pt['P_kN']) for pt in curva)
        P_max = max(float(pt['P_kN']) for pt in curva)
        if Mn > 1e-9:
            print('    Mn(P) = %.1f kN m  ->  u = M / Mn = %.3f  %s'
                  % (Mn, demanda['u'],
                     'pasa' if demanda['u'] <= 1 else 'NO PASA (nominal, sin phi)'))
        elif demanda['P_kN'] < P_min:
            print('    NO PASA, y no por flexion: P = %.1f kN es TRACCION y '
                  'supera la traccion pura' % demanda['P_kN'])
            print('    de la seccion (%.1f kN = fy * As). Con esa axial no '
                  'queda momento resistente,' % P_min)
            print('    Mn = 0 y M / Mn no se define. El anexo lo marca con u = '
                  '9999: es una bandera, no un cociente.')
        elif demanda['P_kN'] > P_max:
            print('    NO PASA, y no por flexion: P = %.1f kN supera la '
                  'compresion pura (%.1f kN).' % (demanda['P_kN'], P_max))
            print('    Mn = 0 y M / Mn no se define; el anexo lo marca con '
                  'u = 9999.')
        else:
            print('    Mn(P) = 0 dentro de la curva: u no se define (anexo: '
                  '9999)')
        if e['tipo'] == 'muro':
            # Dos lecturas independientes del mismo eje: las inercias que
            # recibe OpenSees (el elementTag) y la seccion del modelo que
            # usa demanda_capacidad.
            eje = momento_en_el_plano(o)
            usado = demanda['plano']
            fuera = 'Mz' if usado == 'My' else 'My'
            print('    muro: OpenSees recibe Iy = %.4g e Iz = %.4g, asi que el '
                  'momento EN SU PLANO es %s' % (o['Iy'], o['Iz'], eje))
            print('    demanda_capacidad compara |%s| con la curva; |%s| es el '
                  'fuera de plano y se informa aparte' % (usado, fuera))
            if eje != usado:
                print('    OJO: el elementTag dice %s y demanda_capacidad usa %s'
                      % (eje, usado))

    # ------------------------------------------------ contra el JSON
    print()
    anexo, motivo = None, None
    mias = [x.strip() for x in parametros.describir(p).split('\n')]
    if not os.path.isfile(ANEXO):
        motivo = 'data/unity/semana04.json no existe'
    else:
        with io.open(ANEXO, encoding='utf-8') as fh:
            anexo = json.load(fh)
        if anexo['info']['edificio'] != edificio:
            motivo = ('data/unity/semana04.json es de %s, no de %s'
                      % (anexo['info']['edificio'], edificio))
        elif [x.strip() for x in anexo['info'].get('parametros', [])] != mias:
            motivo = ('data/unity/semana04.json se exporto con otros '
                      'parametros: %s'
                      % ' | '.join(anexo['info'].get('parametros', [])))
    if motivo is None:
        print('CONTRA data/unity/semana04.json (lo que lee VisorSemana04; '
              'la copia de StreamingAssets es la misma)')
    else:
        print('CONTRA EL ANEXO EN MEMORIA: %s.' % motivo)
        print('    Se arma con construir_anexo(%r) y se pasa por json.dumps/'
              'loads, sin escribirlo:' % edificio)
        print('    es lo que Unity leeria si se exportara %s. El archivo '
              'compartido no se toca.' % edificio)
        with AvisosDeOpenSees() as avisos_anexo:
            anexo, _ctx = eu.construir_anexo(edificio, resto)
        anexo = json.loads(json.dumps(anexo, separators=(',', ':')))
        if avisos_anexo.resumen():
            print('    (%s)' % avisos_anexo.resumen())
    el = next((x for x in anexo['elementos'] if int(x['id']) == eid), None)
    if el is None:
        print('    el elemento %d NO esta en el anexo' % eid)
        return 1

    def cota_campo(lista, campo):
        return medio_ultimo_decimal(v for x in lista for v in (
            x[campo] if isinstance(x[campo], list) else [x[campo]]))

    filas = [('objeto_unity', nombre_objeto(eu_el or e), el['objeto_unity'], 0),
             ('tipo', e['tipo'], el['tipo'], 0),
             ('seccion', e['seccion'], el['seccion'], 0),
             ('n1', o['n1'], el['n1'], 0), ('n2', o['n2'], el['n2'], 0)]
    # tag_opensees es TEXTO: cada numero se compara contra lo capturado en
    # ops.element con medio ultimo digito escrito de cota.
    m_tag = re.match(r'element elasticBeamColumn (\d+) (\d+) (\d+) ',
                     el['tag_opensees'])
    filas.append(('tag: tag n1 n2',
                  '%d %d %d' % (eid, o['n1'], o['n2']),
                  ' '.join(m_tag.groups()) if m_tag else el['tag_opensees'], 0))
    pares = dict(re.findall(r'(\w+)=([^\s]+)', el['tag_opensees']))
    for clave in ('A', 'E', 'G', 'J', 'Iy', 'Iz'):
        if clave in pares:
            filas.append(('tag: %s (posicion OpenSees)' % clave, o[clave],
                          float(pares[clave]),
                          medio_digito_de_texto(pares[clave])))
        else:
            filas.append(('tag: %s' % clave, 'escrito', 'falta', 0))
    # El vecxz va con '%g': seis cifras SIGNIFICATIVAS, no decimales fijos.
    # '1' no esta redondeado a la unidad; la cota es media sexta cifra.
    vec_txt = pares.get('vecxz', '()').strip('()').split(',')
    for i in range(3):
        t = vec_txt[i] if i < len(vec_txt) else None
        v = float(t) if t else None
        cota_g = (0.5 * 10.0 ** (math.floor(math.log10(abs(v))) - 5)
                  if v else 0.0)
        filas.append(('tag: vecxz[%d]' % i, o['vecxz'][i], v, cota_g))
    for campo, py in (('L', L), ('E_kPa', o['E']), ('G_kPa', o['G']),
                      ('A', float(sec_c['A'])), ('Iy', float(sec_c['Iy'])),
                      ('Iz', float(sec_c['Iz'])), ('J', float(sec_c['J']))):
        filas.append((campo, py, el[campo], cota_campo(anexo['elementos'], campo)))
    for i in range(3):
        filas.append(('vecxz[%d]' % i, o['vecxz'][i], el['vecxz'][i],
                      cota_campo(anexo['elementos'], 'vecxz')))
    for extremo, nid in (('restr_n1', o['n1']), ('restr_n2', o['n2'])):
        filas.append((extremo, _v(cap['restringidos'].get(nid, [0] * 6)),
                      _v(el[extremo]), 0))
    filas.append(('diafragma_n1', maestros.get(o['n1'], -1),
                  el['diafragma_n1'], 0))
    filas.append(('diafragma_n2', maestros.get(o['n2'], -1),
                  el['diafragma_n2'], 0))

    caso = next((c for c in anexo['casos'] if c['nombre'] == caso_pedido), None)
    if caso is None:
        print('    el caso %s no esta en el anexo' % caso_pedido)
    else:
        s = next(x for x in caso['esfuerzos'] if int(x['id']) == eid)
        cf = cota_campo(caso['esfuerzos'], 'f')
        for i, c in enumerate(COMPONENTES):
            filas.append(('f %s_i' % c, f[i], s['f'][i], cf))
        for i, c in enumerate(COMPONENTES):
            filas.append(('f %s_j' % c, f[6 + i], s['f'][6 + i], cf))
        filas.append(('estaciones', len(xs), len(s['x']), 0))
        for c in COMPONENTES:
            ce = cota_campo(caso['esfuerzos'], c)
            filas.append(('%s(0)' % c, esf[c][0], s[c][0], ce))
            filas.append(('%s(L)' % c, esf[c][-1], s[c][-1], ce))
        dem = next((x for x in caso['demandas'] if int(x['id']) == eid), None)
        if demanda and dem:
            cd = {k: cota_campo(caso['demandas'], k)
                  for k in ('P', 'M', 'M_fuera_plano', 'Mn', 'u')}
            filas += [('demanda P', demanda['P_kN'], dem['P'], cd['P']),
                      ('demanda M', demanda['M_kNm'], dem['M'], cd['M']),
                      ('demanda M fuera de plano',
                       demanda['M_fuera_de_plano_kNm'] or 0.0,
                       dem['M_fuera_plano'], cd['M_fuera_plano']),
                      ('demanda extremo', demanda['extremo'], dem['extremo'], 0),
                      ('Mn', demanda['Mn'], dem['Mn'], cd['Mn']),
                      ('u' if demanda['Mn'] > 1e-9 else
                       'u (9999 = Mn 0, sin cociente)',
                       demanda['u'], dem['u'], cd['u']),
                      ('pasa', demanda['u'] <= 1.0, dem['pasa'], 0)]
        elif demanda or dem:
            filas.append(('tiene demanda', bool(demanda), bool(dem), 0))
    if curva is not None and el['familia'] >= 0:
        fam = anexo['familias'][el['familia']]
        filas.append(('familia %d: elementos' % el['familia'], 'contiene',
                      'contiene' if eid in fam['elementos'] else 'no', 0))
        filas.append(('puntos de la curva', len(curva), len(fam['P']), 0))
        for i, pt in enumerate(curva[:len(fam['P'])]):
            filas.append(('curva P[%d]' % i, pt['P_kN'], fam['P'][i],
                          medio_ultimo_decimal(fam['P'])))
            filas.append(('curva Mn[%d]' % i, pt['M_kNm'], fam['Mn'][i],
                          medio_ultimo_decimal(fam['Mn'])))
    elif curva is not None or el['familia'] >= 0:
        filas.append(('familia', 'con fierro' if curva else -1,
                      el['familia'] if el['familia'] < 0 else 'con fierro', 0))

    malas = _tabla_de_comparacion(filas)
    print()
    print('    cota de cada numero: el redondeo con que el anexo escribe esa '
          'familia de')
    print('    valores (medido) mas medio intervalo float32 (lo que pierde '
          'JsonUtility)')
    print('=' * 78)
    if cociente > 1.0:
        print('  EL ELEMENTO NO CIERRA en x = L (error/cota %.3f en %s)'
              % (cociente, peor))
    if malas:
        print('  %d NUMERO(S) NO CALZAN con lo que lee Unity' % malas)
    if malas or cociente > 1.0:
        return 1
    print('  LA CADENA CALZA: OpenSees -> modelo -> Unity -> resultados -> '
          'capacidad')
    return 0


if __name__ == '__main__':
    sys.exit(main())
