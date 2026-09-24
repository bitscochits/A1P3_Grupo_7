"""
================================================================
  nucleos.py - los muros que son PATA de un nucleo
================================================================
  Un nucleo (caja de ascensores, de escalera) se modela como varias
  COLUMNAS ANCHAS unidas en cada piso por brazos rigidos (CLAUDE.md
  seccion 4). Asi resiste el volcamiento como un PAR de axiales entre
  sus patas: una se comprime y la otra se tracciona.

  Despues, la revision de demanda/capacidad compara cada pata SOLA
  contra su propia curva P-M. La traccionada se pasa casi siempre, y
  cuando la traccion neta supera el As*fy de esa pata el cociente ni
  siquiera existe: la demanda cae fuera de la curva y se informa
  u = 9999.

  ESO NO MIDE QUE EL NUCLEO FALLE. La traccion que saca a la pata de
  su curva es el PAR INTERNO del grupo, no carga externa que el grupo
  tenga que tomar. Medido sobre el conjunto (24-09, 15 combinaciones),
  de las 119 filas que no pasan, 103 son patas de nucleo:

      92 (77 % del total)  el grupo esta en COMPRESION NETA
      11 ( 9 %)            traccionado, pero DENTRO de su As*fy
       0 ( 0 %)            el grupo se pasa de su propio As*fy

  O sea: ni un solo grupo esta sobrepasado en axial. Las 103 salen de
  mirar la pata sola. Las 16 que quedan no son patas: 9 filas en 5
  muros sueltos y 7 en 2 columnas.

  ----------------------------------------------------------------
  LO QUE ESTE MODULO NO HACE
  ----------------------------------------------------------------
  NO cambia ningun veredicto. `pasa` se sigue decidiendo con la curva
  de la pata, porque revisar pata por pata es un procedimiento
  aceptado (asi revisan los "piers" los programas comerciales) y
  porque el ala traccionada de un nucleo tiene que llevar su traccion
  con su propio fierro tambien en la seccion compuesta.

  Lo que hace es DECIR de donde viene ese axial, para que el mapa no
  presente como una falla de capacidad lo que es un reparto interno.
  La revision de verdad --una seccion de fibras del nucleo completo,
  con flexion biaxial porque 12 de los 17 grupos que fallan tienen
  muros cruzados a 0 y 90 grados-- es harina de otro costal y esta
  anotada como pendiente en semana05/QUE_REVISAR.md, item 5.

  ----------------------------------------------------------------
  COMO SE ARMA UN GRUPO
  ----------------------------------------------------------------
  Muros unidos por una cadena de brazos rigidos SIN viga ni columna
  en el medio. La condicion del medio importa: un brazo tambien va
  del baricentro del muro a sus caras, donde llega una viga, y sin
  ella el recorrido se escapa por el marco y termina uniendo medio
  edificio (87 de 96 muros en un solo grupo en vez de 77 en 36).

  Uso:  python comun/nucleos.py <edificio>
================================================================
"""
from __future__ import annotations

import collections
import json
import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _AQUI)
import contrato                                # noqa: E402
import rutas                                   # noqa: E402

# Los tipos de barra que ATRAVIESAN un grupo. 'brazo' es el nombre del
# LT2 y 'brazo_rigido' el de Ingenieria: son lo mismo (CLAUDE.md 4).
BRAZOS = ('brazo', 'brazo_rigido')

# Lo que CORTA el grupo: si una punta del brazo tiene una de estas, ese
# brazo va del muro a su cara y no a otra pata.
CORTAN = ('viga_x', 'viga_y', 'viga', 'columna', 'pilar_metal',
          'viga_metal', 'diagonal')

COMPRIMIDO = 'comprimido'
TRACCION_DENTRO = 'traccion_dentro'
TRACCION_FUERA = 'traccion_fuera'


def grupos(modelo):
    """
    {id de muro: [ids del grupo]} para los muros que son pata de un
    nucleo. Un muro que no comparte grupo con ningun otro NO aparece.
    """
    elementos = modelo.get('elementos', [])
    corta = set()
    for e in elementos:
        if e.get('tipo') in CORTAN:
            corta.add(e['n1'])
            corta.add(e['n2'])

    padre = {}

    def raiz(a):
        while padre.setdefault(a, a) != a:
            a = padre[a]
        return a

    def unir(a, b):
        ra, rb = raiz(a), raiz(b)
        if ra != rb:
            padre[ra] = rb

    for e in elementos:
        if e.get('tipo') not in BRAZOS:
            continue
        if e['n1'] in corta or e['n2'] in corta:
            continue
        unir(e['n1'], e['n2'])

    # UN GRUPO ES UN PISO DE UN NUCLEO, no el nucleo entero.
    #
    # Un muro comparte nodo con los del piso de ARRIBA y con los de
    # ABAJO, asi que agrupar por nodo juntaba las patas de dos pisos y
    # la suma de axiales doblaba el grupo (grupos de 8 que eran 4 + 4).
    # Lo que tiene sentido sumar es el axial de las patas de UN piso:
    # eso es lo que el nucleo baja por ese tramo. Por eso la clave
    # lleva, ademas del nudo por el que se conectan, las dos cotas del
    # muro: solo se agrupan patas que cubren el MISMO tramo.
    nodos = {int(x['id']): x for x in modelo.get('nodos', [])}

    def cota(nid):
        n = nodos.get(int(nid))
        return round(float(n['z']), 2) if n else None

    por_clave = collections.defaultdict(set)
    for e in elementos:
        if e.get('tipo') != 'muro':
            continue
        z1, z2 = cota(e['n1']), cota(e['n2'])
        if z1 is None or z2 is None:
            continue
        tramo = (min(z1, z2), max(z1, z2))
        # Se conecta por cualquiera de sus dos nudos; el tramo decide
        # que no se mezclen pisos.
        for nid in (e['n1'], e['n2']):
            por_clave[(raiz(nid), tramo)].add(e['id'])

    # Un muro puede aparecer por su nudo de abajo y por el de arriba;
    # se queda con el grupo MAYOR, que es el que tiene a todas sus
    # companeras de piso, y despues se cierra para que la relacion sea
    # simetrica (si i esta con j, j esta con i).
    mejor = {}
    for miembros in por_clave.values():
        if len(miembros) < 2:
            continue
        for i in miembros:
            if i not in mejor or len(miembros) > len(mejor[i]):
                mejor[i] = miembros
    salida = {}
    for i, miembros in mejor.items():
        lista = sorted(m for m in miembros if mejor.get(m) is miembros)
        if len(lista) > 1:
            salida[i] = lista
    return {i: v for i, v in salida.items() if i in v}


def estado(P_grupo, asfy_grupo):
    """
    Que le pasa al grupo en axial. Convencion de las demandas:
    P > 0 es COMPRESION.
    """
    if P_grupo > 0:
        return COMPRIMIDO
    return TRACCION_DENTRO if -P_grupo <= asfy_grupo else TRACCION_FUERA


def asfy_de(modelo, ids, cache=None):
    """
    Suma de As*fy (kN) de esos muros: la traccion que el grupo puede
    tomar con su propio fierro. Un muro sin enfierradura aporta 0 y se
    cuenta aparte, para no inventarle acero al grupo.
    """
    import capacidad
    total, sin_fierro = 0.0, []
    for i in ids:
        if cache is not None and i in cache:
            v = cache[i]
        else:
            try:
                v = -capacidad.desde_elemento(modelo, i).P_traccion
            except BaseException:
                v = None
            if cache is not None:
                cache[i] = v
        if v is None:
            sin_fierro.append(i)
        else:
            total += v
    return total, sin_fierro


def bloque(modelo, ids, P_por_elemento, cache=None):
    """
    El dato que viaja con cada fila de demanda de una pata:
    de que grupo es, cuanto axial tiene el grupo entero en ESE caso, y
    cuanto puede tomar con su fierro. None si el muro no es pata.
    """
    if not ids:
        return None
    P = sum(P_por_elemento.get(i, 0.0) for i in ids)
    asfy, sin_fierro = asfy_de(modelo, ids, cache)
    return {
        'patas': len(ids),
        'P_kN': round(P, 4),
        'Asfy_kN': round(asfy, 4),
        'estado': estado(P, asfy),
        'sin_fierro': len(sin_fierro),
    }


def _main(argv):
    """
    Informa los grupos y COMPRUEBA dos cosas:

    [1] los invariantes del agrupamiento (si i esta en el grupo de j,
        j esta en el de i; ninguna pata repetida; ningun grupo de 1);
    [2] que los `nucleo_*` del anexo en disco sean los que sale de
        recalcular aca. Dos definiciones del mismo grupo divergen en
        silencio, y la que mentiria es la que lee el visor.
    """
    ed = argv[0] if argv else 'conjunto'
    modelo = contrato.cargar_modelo(ed)
    g = grupos(modelo)
    distintos = {tuple(v) for v in g.values()}
    muros = sum(1 for e in modelo['elementos'] if e.get('tipo') == 'muro')
    fallos = []

    def check(cond, msg, detalle=''):
        print('  [%s] %s' % ('OK  ' if cond else 'FALLA', msg))
        if detalle:
            print('         %s' % detalle)
        if not cond:
            fallos.append(msg)

    print('=' * 64)
    print('  NUCLEOS DE %s' % ed.upper())
    print('=' * 64)
    print('  %d muros; %d son pata de un nucleo, en %d grupos'
          % (muros, len(g), len(distintos)))

    print('\n[1] los grupos son consistentes')
    sueltos = [tuple(v) for v in distintos if len(v) < 2]
    check(not sueltos, 'ningun "grupo" tiene una sola pata', str(sueltos[:3]))
    dobles = [v for v in distintos if len(set(v)) != len(v)]
    check(not dobles, 'ninguna pata aparece dos veces en su grupo', str(dobles[:3]))
    asimetricos = [(i, j) for i, v in g.items() for j in v if i not in g.get(j, ())]
    check(not asimetricos, 'si i esta en el grupo de j, j esta en el de i',
          str(asimetricos[:3]))
    cache = {}
    sin_fierro_total = 0
    for ids in sorted(distintos, key=len, reverse=True):
        _asfy, sin = asfy_de(modelo, ids, cache)
        sin_fierro_total += len(sin)
    print('         %d patas sin enfierradura: aportan 0 al As*fy del grupo, '
          'o sea el grupo se informa MAS traccionado de lo que esta'
          % sin_fierro_total)

    print('\n[2] el anexo en disco trae los mismos grupos')
    ruta = os.path.join(rutas.UNITY, 'semana04.json')
    if not os.path.exists(ruta):
        check(True, 'no hay anexo en disco: nada que comparar')
        return 1 if fallos else 0
    with open(ruta, encoding='utf-8') as f:
        anexo = json.load(f)
    if (anexo.get('info') or {}).get('edificio') != ed:
        check(True, 'el anexo en disco es de %r y esto es %r: no se compara'
              % ((anexo.get('info') or {}).get('edificio'), ed))
        return 1 if fallos else 0

    peor, n, estados = 0.0, 0, collections.Counter()
    for k in anexo['casos']:
        P_de = {x['id']: x['P'] for x in k['demandas']}
        for x in k['demandas']:
            ids = g.get(x['id'])
            esperado_patas = len(ids) if ids else 0
            if x.get('nucleo_patas', 0) != esperado_patas:
                check(False, 'nucleo_patas del elemento %d en %s'
                      % (x['id'], k['nombre']),
                      'anexo %s, recalculado %s'
                      % (x.get('nucleo_patas'), esperado_patas))
                return 1
            if not ids:
                continue
            P = sum(P_de.get(i, 0.0) for i in ids)
            peor = max(peor, abs(P - x['nucleo_P']))
            estados[x['nucleo_estado']] += 1
            n += 1
    # El anexo redondea a DECIMALES_FUERZA = 4, asi que la cota es medio
    # ultimo decimal por cada pata que se suma.
    cota = 0.5e-4 * max(len(v) for v in distintos)
    check(peor <= cota, 'el nucleo_P de las %d filas de pata calza al recalcularlo' % n,
          'peor diferencia %.2e kN, cota por redondeo %.2e' % (peor, cota))
    print('         estados: %s' % dict(estados))
    fuera = estados.get(TRACCION_FUERA, 0)
    print('         %d filas con el grupo POR SOBRE su As*fy%s'
          % (fuera, ' (ninguna: toda la traccion que saca a una pata de su '
             'curva es par interno o cabe en el fierro del grupo)' if not fuera else ''))

    print()
    if fallos:
        print('  %d FALLA(S)' % len(fallos))
        return 1
    print('  TODO OK')
    return 0


if __name__ == '__main__':
    sys.exit(_main(sys.argv[1:]))
