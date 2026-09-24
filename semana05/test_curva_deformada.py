"""
================================================================
  test_curva_deformada.py - la barra dibujada se dobla como la barra
================================================================
  Hasta la Semana 5 el visor dibujaba cada barra como un PALO RECTO
  entre sus dos nodos deformados. Una viga cargada cuyos extremos
  cuelgan de nudos que casi no bajan quedaba igual de recta, y una
  columna entre dos pisos que se corren distinto solo se INCLINABA,
  cuando en la realidad entra en doble curvatura.

  Lo que faltaba no era calcular: eran los GIROS de los nudos, que ya
  venian en cada desplazamiento (rx, ry, rz) y nadie usaba. Con ellos,
  la forma de la barra son las funciones de forma del propio elemento
  -- las MISMAS con que OpenSees interpola entre sus dos nodos --, que
  en este repo ya estaban escritas y verificadas en
  `semana05/carga_movil.py` (`desplazamiento_en`, para el recorrido de
  la carga movil).

  Este test cuida las cuatro cosas que pueden salir mal:

  [1] LA FORMULA. Sin carga dentro del vano, la elastica de una barra
      es EXACTAMENTE una cubica, asi que la interpolacion tiene que dar
      la solucion analitica al decimal, no parecida. Se prueba con un
      voladizo con carga en la punta resuelto por OpenSees, en tres
      orientaciones (en X, en Y y vertical) para que si la
      transformacion de ejes locales estuviera mal alguna falle.

  [2] LA TRANSCRIPCION AL C#. La formula quedo escrita DOS veces: en
      Python (carga_movil) y en C# (VisorEstructura.CurvaDe), porque el
      visor tiene que dibujar tambien los casos que el servidor resuelve
      en vivo. Dos copias divergen en silencio: un signo cambiado curva
      la viga hacia ARRIBA y nadie se entera. Aca se LEEN las lineas del
      C#, se traducen a Python y se evaluan contra la funcion de Python
      con numeros al azar.

  [3] LOS DATOS. La curva necesita rx/ry/rz en cada desplazamiento y los
      ejes locales de cada barra. Si el exportador deja de emitirlos, el
      visor no falla: dibuja palos rectos, que es justo lo que se venia
      a arreglar.

  [4] EL MODELO REAL. Que la curva arranque y termine EXACTAMENTE en sus
      dos nodos (si no, dos barras seguidas se separarian en el nudo), y
      que la viga que mas se aparta de la recta de sus nodos cuelgue
      hacia ABAJO bajo gravedad.

  LO QUE LA CURVA NO DIBUJA (y no es un error)
  La interpolacion sale de los GDL de los nodos. La flecha que la carga
  repartida produce DENTRO del vano no esta en ningun GDL nodal, asi que
  no aparece: en la viga 92 del LT2 (8.90 m, 0.60x0.80, 27.749 kN/m) son
  0.64 mm sobre 6.80 mm de nodo, un 9 %. Agregarla pedirea E, I y la
  carga del caso en C#, que es calculo estructural y va en Python
  (CLAUDE.md seccion 2); el unico sitio donde se suma es el recorrido de
  la carga movil, y lo suma Python (`flecha_biempotrada`).

  Uso:  python semana05/test_curva_deformada.py [lt2|ingenieria|conjunto]
================================================================
"""
from __future__ import annotations

import io
import json
import os
import random
import re
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_AQUI), 'comun'))
sys.path.insert(0, _AQUI)
import rutas                                          # noqa: E402
from contrato import ejes_locales                      # noqa: E402
from carga_movil import desplazamiento_en             # noqa: E402

CS = os.path.join(rutas.RAIZ, 'unity', 'Assets', 'Scripts', 'VisorEstructura.cs')

fallos = []


def check(cond, msg, detalle=''):
    print(f"  [{'OK  ' if cond else 'FALLA'}] {msg}")
    if detalle:
        print(f"         {detalle}")
    if not cond:
        fallos.append(msg)


def base_de(wx, wy, wz):
    return {'wx': wx, 'wy': wy, 'wz': wz}


# ================================================================
# [1] La formula: contra la elastica exacta de un voladizo
# ================================================================
def voladizo(direccion):
    """
    Resuelve en OpenSees un voladizo de UNA barra con carga en la punta
    y devuelve (L, EI, ui, uj, base, P) para interpolar su elastica.

    'direccion' es hacia donde corre la barra: 'x', 'y' o 'z'. La carga
    va siempre perpendicular a ella, para que la barra flecte.
    """
    import openseespy.opensees as ops

    L, E, P = 6.0, 25_000_000.0, 10.0          # m, kPa, kN
    b, h = 0.30, 0.50
    A, Iz, Iy = b * h, b * h ** 3 / 12.0, h * b ** 3 / 12.0
    J = Iy + Iz
    G = E / 2.4

    punta = {'x': (L, 0.0, 0.0), 'y': (0.0, L, 0.0), 'z': (0.0, 0.0, L)}[direccion]
    # La carga, perpendicular a la barra. En la barra vertical se
    # empuja en X; en las horizontales, hacia abajo.
    carga = {'x': (0.0, 0.0, -P), 'y': (0.0, 0.0, -P), 'z': (P, 0.0, 0.0)}[direccion]
    # vecxz con la misma regla del servidor: vertical -> (1,0,0).
    vecxz = (1.0, 0.0, 0.0) if direccion == 'z' else (0.0, 0.0, 1.0)

    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 6)
    ops.node(1, 0.0, 0.0, 0.0)
    ops.node(2, *punta)
    ops.fix(1, 1, 1, 1, 1, 1, 1)
    ops.geomTransf('Linear', 1, *vecxz)
    ops.element('elasticBeamColumn', 1, 1, 2, A, E, G, J, Iy, Iz, 1)
    ops.timeSeries('Linear', 1)
    ops.pattern('Plain', 1, 1)
    ops.load(2, carga[0], carga[1], carga[2], 0.0, 0.0, 0.0)
    ops.system('BandGeneral')
    ops.numberer('RCM')
    ops.constraints('Transformation')
    ops.integrator('LoadControl', 1.0)
    ops.algorithm('Linear')
    ops.analysis('Static')
    ops.analyze(1)

    ui = [ops.nodeDisp(1, i) for i in range(1, 7)]
    uj = [ops.nodeDisp(2, i) for i in range(1, 7)]
    ops.wipe()
    # Los ejes locales NO se deducen aca: salen de la misma funcion del
    # contrato con que los sella el exportador, con el mismo vecxz que
    # se le dio a geomTransf. Si divergieran, divergiria el dibujo.
    base, _ = ejes_locales((0.0, 0.0, 0.0), punta, list(vecxz))
    # La carga se puso SIEMPRE a lo largo del local z, asi que la
    # resiste Iy (My). Es la convencion de CLAUDE.md seccion 4: con
    # vecxz = (0,0,1) el local z queda vertical y la gravedad flecta
    # en My. Si se pusiera Iz, las dos barras horizontales fallan.
    return L, E * Iy, ui, uj, base, P


def bloque_1():
    print("\n[1] La interpolacion = la elastica exacta del voladizo")
    for direccion in ('x', 'y', 'z'):
        L, EI, ui, uj, base, P = voladizo(direccion)
        peor, donde = 0.0, 0.0
        for k in range(11):
            x = L * k / 10.0
            # Elastica exacta de un voladizo con carga en la punta:
            #   v(x) = P x^2 (3L - x) / (6 EI)
            exacta = P * x * x * (3 * L - x) / (6.0 * EI)
            d = desplazamiento_en(base, L, None, ui, uj, x)
            # La flecha es la componente perpendicular a la barra, con
            # el signo de la carga: en x e y va hacia -z; en z, hacia +x.
            calc = -d[2] if direccion != 'z' else d[0]
            peor = max(peor, abs(calc - exacta))
            if abs(calc - exacta) >= peor:
                donde = x
        # La punta flecta P L^3 / 3EI; se pide 1e-9 m sobre eso (1 nm).
        punta = P * L ** 3 / (3.0 * EI)
        check(peor < 1e-9,
              f"barra en {direccion}: 11 estaciones calzan con P x^2 (3L-x) / 6EI",
              f"peor {peor:.3e} m en x = {donde:.2f} m; flecha de punta {punta * 1000:.4f} mm")


# ================================================================
# [2] La copia en C# es la misma formula
# ================================================================
def cuerpo_de_curvade():
    """El texto del metodo CurvaDe() de VisorEstructura.cs."""
    src = io.open(CS, encoding='utf-8').read()
    i = src.find('Vector3[] CurvaDe(')
    if i < 0:
        return ''
    j = src.find('\n    static Vector3 EjeLocal', i)
    return src[i:j if j > 0 else len(src)]


def expresion_de(cuerpo, patron):
    """Como expresion(), pero para una asignacion que no declara tipo
    (torsion[k] = ...): el C# la escribe sin 'float' delante."""
    m = re.search(patron + r'\s*=\s*(.*?);', cuerpo, re.S)
    if not m:
        return None
    e = ' '.join(m.group(1).split())
    e = e.replace('Vector3.Dot', 'dot').replace('(float)', '')
    return re.sub(r'(\d)f\b', r'\1', e)


def expresion(cuerpo, nombre):
    """
    La expresion C# que se le asigna a 'nombre', ya traducida a Python:
    se le quitan el tipo, los sufijos f de los numeros y los
    Vector3.Dot(a, b) se vuelven dot(a, b).
    """
    m = re.search(r'float\s+' + nombre + r'\s*=\s*(.*?);', cuerpo, re.S)
    if not m:
        return None
    e = ' '.join(m.group(1).split())
    e = e.replace('Vector3.Dot', 'dot').replace('(float)', '')
    e = re.sub(r'(\d)f\b', r'\1', e)
    return e


def bloque_2():
    print("\n[2] La formula del C# es la misma que la de Python")
    cuerpo = cuerpo_de_curvade()
    check(bool(cuerpo), "VisorEstructura.cs tiene el metodo CurvaDe()")
    if not cuerpo:
        return

    def dot(v, w):
        return sum(v[c] * w[c] for c in range(3))

    rnd = random.Random(20260923)
    peor, faltan, peor_tor = 0.0, [], [0.0]
    for _ in range(200):
        # Una base ortonormal cualquiera y GDL cualesquiera: si un
        # signo estuviera cambiado, no se salva por casualidad.
        L = rnd.uniform(1.0, 12.0)
        ex, ey, ez = _base_al_azar(rnd)
        ti = [rnd.uniform(-0.05, 0.05) for _ in range(3)]
        tj = [rnd.uniform(-0.05, 0.05) for _ in range(3)]
        ri = [rnd.uniform(-0.01, 0.01) for _ in range(3)]
        rj = [rnd.uniform(-0.01, 0.01) for _ in range(3)]
        xi = rnd.random()
        entorno = {'dot': dot, 'ex': ex, 'ey': ey, 'ez': ez, 'L': L, 'xi': xi,
                   'ti': ti, 'tj': tj, 'ri': ri, 'rj': rj}
        for nombre in ('N1', 'N2', 'N3', 'N4', 'u', 'v', 'w'):
            e = expresion(cuerpo, nombre)
            if e is None:
                if nombre not in faltan:
                    faltan.append(nombre)
                continue
            entorno[nombre] = eval(e, {'__builtins__': {}}, entorno)   # noqa: S307
        if faltan:
            break
        # Lo mismo, con la funcion de Python: su resultado es global, asi
        # que se proyecta de vuelta sobre los ejes locales.
        g = desplazamiento_en(base_de(ex, ey, ez), L, None,
                              list(ti) + list(ri), list(tj) + list(rj), xi * L)
        for nombre, eje in (('u', ex), ('v', ey), ('w', ez)):
            peor = max(peor, abs(entorno[nombre] - dot(eje, g)))
        # LA TORSION. No sale de desplazamiento_en (no es una traslacion):
        # es el giro sobre el propio eje, que en una barra prismatica sin
        # torque repartido va LINEAL entre sus dos nudos. Se compara la
        # linea del C# contra esa recta. Lleva el factorEscala, que en el
        # C# es un campo; se evalua con 1.0, que es lo que mide la forma.
        e_tor = expresion_de(cuerpo, r'torsion\[k\]')
        if e_tor is None:
            if 'torsion' not in faltan:
                faltan.append('torsion')
        else:
            entorno['factorEscala'] = 1.0
            calc = eval(e_tor, {'__builtins__': {}}, entorno)      # noqa: S307
            recta = (1 - xi) * dot(ex, ri) + xi * dot(ex, rj)
            peor_tor[0] = max(peor_tor[0], abs(calc - recta))

    check(not faltan, "el C# define N1..N4, u, v y w",
          f"no encontre: {faltan}" if faltan else "")
    if not faltan:
        check(peor < 1e-12,
              "200 tiros al azar: el C# da lo mismo que carga_movil.desplazamiento_en",
              f"peor diferencia {peor:.3e} m")
        check(peor_tor[0] < 1e-12,
              "y su torsion es la recta entre los giros axiales de los dos nudos",
              f"peor diferencia {peor_tor[0]:.3e} rad")


def _base_al_azar(rnd):
    """Tres versores ortonormales, como los localX/localY/localZ."""
    def norm(v):
        m = sum(c * c for c in v) ** 0.5
        return tuple(c / m for c in v)

    def cruz(a, b):
        return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
                a[0] * b[1] - a[1] * b[0])

    ex = norm([rnd.uniform(-1, 1) for _ in range(3)])
    t = norm([rnd.uniform(-1, 1) for _ in range(3)])
    while abs(sum(ex[c] * t[c] for c in range(3))) > 0.9:
        t = norm([rnd.uniform(-1, 1) for _ in range(3)])
    ez = norm(cruz(ex, t))
    ey = cruz(ez, ex)
    return ex, ey, ez


# ================================================================
# [3] El JSON trae lo que la curva necesita
# ================================================================
def bloque_3(edificio):
    print(f"\n[3] {edificio}.json trae giros y ejes locales")
    ruta = os.path.join(rutas.RAIZ, 'data', 'unity', f'{edificio}.json')
    if not os.path.exists(ruta):
        check(False, f"existe {ruta}")
        return
    m = json.load(io.open(ruta, encoding='utf-8'))

    sin_giro = [n['id'] for n in m['nodos'] if 'rx' not in n or 'ry' not in n or 'rz' not in n]
    check(not sin_giro,
          f"los {len(m['nodos'])} nodos traen rx, ry, rz (la deformada precalculada de G)",
          f"sin giros: {sin_giro[:8]}" if sin_giro else "")

    # Sin ejes locales la barra no se curva: se queda recta y no avisa.
    malos, no_ortos = [], []
    for e in m['elementos']:
        ejes = [e.get('localX'), e.get('localY'), e.get('localZ')]
        if any(v is None or len(v) < 3 for v in ejes):
            malos.append(e['id'])
            continue
        for v in ejes:
            if abs(sum(c * c for c in v) ** 0.5 - 1.0) > 1e-4:
                malos.append(e['id'])
                break
        else:
            x, y, z = ejes
            if (abs(sum(x[c] * y[c] for c in range(3))) > 1e-4
                    or abs(sum(x[c] * z[c] for c in range(3))) > 1e-4
                    or abs(sum(y[c] * z[c] for c in range(3))) > 1e-4):
                no_ortos.append(e['id'])
    check(not malos, f"los {len(m['elementos'])} elementos traen sus 3 ejes locales unitarios",
          f"sin ejes o no unitarios: {malos[:8]}" if malos else "")
    check(not no_ortos, "y los tres son perpendiculares entre si",
          f"no ortogonales: {no_ortos[:8]}" if no_ortos else "")

    # Un giro que sea cero en TODOS los nodos seria un exportador que
    # escribe el campo pero no el dato: la curva volveria a ser recta.
    giro = max((max(abs(n.get('rx', 0.0)), abs(n.get('ry', 0.0)), abs(n.get('rz', 0.0)))
                for n in m['nodos']), default=0.0)
    check(giro > 1e-9, "y algun nodo gira de verdad en G",
          f"mayor giro {giro:.3e} rad")


# ================================================================
# [4] Con el modelo real: los extremos calzan y la panza va hacia abajo
# ================================================================
def bloque_4(edificio):
    print("")
    print(f"[4] {edificio}: la curva pasa por los nodos y la viga hace panza abajo")
    ruta = os.path.join(rutas.RAIZ, 'data', 'unity', f'{edificio}.json')
    m = json.load(io.open(ruta, encoding='utf-8'))
    nodos = {n['id']: n for n in m['nodos']}

    def gdl(n):
        return [n.get(k, 0.0) for k in ('ux', 'uy', 'uz', 'rx', 'ry', 'rz')]

    # La barra se dibuja desde curva[0] hasta curva[n]. Si en xi = 0 y
    # xi = 1 la interpolacion no diera EXACTAMENTE el desplazamiento del
    # nodo, dos barras seguidas se separarian en el nudo y el edificio
    # saldria despegado. Es exacto por construccion (N1 = 1, N3 = 0 en un
    # extremo y al reves en el otro) y no depende de ningun umbral.
    peor_extremo, abajo, arriba, mayor = 0.0, 0, 0, (0.0, None)
    for e in m['elementos']:
        a, b = nodos.get(e['n1']), nodos.get(e['n2'])
        if a is None or b is None or not e.get('localX'):
            continue
        L = sum((b[c] - a[c]) ** 2 for c in 'xyz') ** 0.5
        if L < 1e-6:
            continue
        base = base_de(tuple(e['localX']), tuple(e['localY']), tuple(e['localZ']))
        ui, uj = gdl(a), gdl(b)
        for x, esperado in ((0.0, ui), (L, uj)):
            d = desplazamiento_en(base, L, None, ui, uj, x)
            for c in range(3):
                peor_extremo = max(peor_extremo, abs(d[c] - esperado[c]))
        if not e['tipo'].startswith('viga'):
            continue
        # Cuanto se aparta del palo recto entre los dos nodos, en vertical.
        panza = desplazamiento_en(base, L, None, ui, uj, L / 2.0)[2] - (ui[2] + uj[2]) / 2.0
        if panza < 0:
            abajo += 1
        elif panza > 0:
            arriba += 1
        if abs(panza) > abs(mayor[0]):
            mayor = (panza, e['id'])

    # En xi = 0 y xi = 1 la interpolacion proyecta el desplazamiento
    # del nodo sobre los tres ejes locales y lo vuelve a componer, asi
    # que devuelve el mismo vector... si la base fuera exactamente
    # ortonormal. El JSON la trae REDONDEADA a 6 decimales
    # (contrato.sellar_ejes_locales), y ese redondeo es toda la
    # diferencia: como mucho 6 * 5e-7 * |u| por componente.
    cota = 6 * 0.5e-6 * max(
        (sum(n.get(k, 0.0) ** 2 for k in ('ux', 'uy', 'uz')) ** 0.5 for n in m['nodos']),
        default=0.0)
    check(peor_extremo <= cota,
          "la curva arranca y termina en sus dos nodos, dentro del redondeo de los ejes",
          f"peor diferencia {peor_extremo:.3e} m, cota por redondeo {cota:.3e} m")
    check(abajo + arriba > 0, f"hay vigas con panza que medir ({abajo + arriba})")
    # La viga que mas se aparta de la recta de sus nodos es una de
    # centro de vano bajo gravedad: tiene que colgar HACIA ABAJO. Si el
    # termino del giro tuviera el signo cambiado, esta saldria arriba.
    check(mayor[0] < 0,
          f"la viga que mas se aparta ({mayor[1]}) cuelga hacia abajo bajo G",
          f"{mayor[0] * 1000:.3f} mm bajo la recta de sus nodos; "
          f"{abajo} vigas abajo, {arriba} arriba")


# ================================================================
if __name__ == '__main__':
    edificios = sys.argv[1:] or ['lt2']
    print("=" * 64)
    print("  LA CURVA DE LA DEFORMADA")
    print("=" * 64)
    bloque_1()
    bloque_2()
    for ed in edificios:
        bloque_3(ed)
        bloque_4(ed)

    print("\n" + "=" * 64)
    if fallos:
        print(f"  {len(fallos)} FALLA(S)")
        for f in fallos:
            print(f"   - {f}")
        sys.exit(1)
    print("  TODO OK")
