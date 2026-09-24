"""
================================================================
  losa_colaborante.py - la viga trabaja con su ala de losa
================================================================
  Hasta el 24-09 los dos modelos cargaban la losa SOBRE la viga y no
  dejaban que la losa la AYUDARA a resistir: cada viga entraba a
  OpenSees como un rectangulo bw x h. Eso es fisicamente inconsistente
  --el hormigon de la losa y el de la viga se vacian juntos-- y es la
  razon de fondo de que las flechas de gravedad salieran grandes.

  Esto NO inventa ninguna dimension: usa el espesor de losa que cada
  edificio ya declara en su perfil, y la regla de ancho efectivo de
  ACI 318-08 8.12.2. Por eso se puede adoptar sin respaldo de plano,
  al reves que el ancho de una viga o el diametro de una barra.

  ----------------------------------------------------------------
  LA REGLA  (ACI 318-08 8.12.2, viga con losa a los dos lados)
  ----------------------------------------------------------------
      b_eff <= L / 4                     un cuarto de la luz
      ala por lado <= 8 hf               ocho espesores de losa
      ala por lado <= media distancia libre al alma vecina

  Los dos primeros se aplican tal cual. El tercero se aplica con el
  ANCHO TRIBUTARIO de la viga, que es justamente la media distancia a
  sus vecinas: asi el ala nunca se pasa de la losa que esa viga
  realmente tiene, y dos vigas vecinas no se reparten dos veces el
  mismo hormigon. En una viga de BORDE el tributario ya es de un solo
  lado, o sea que la regla se acota sola sin tener que distinguirla.

  Medido en los dos edificios: manda casi siempre L/4, porque
  8 hf = 2.00 m y los tributarios son de 2 a 3 m.

  ----------------------------------------------------------------
  QUE SE CAMBIA Y QUE NO
  ----------------------------------------------------------------
  SOLO la inercia de gravedad, Iz. No el area.

  El area se deja RECTANGULAR a proposito: los dos modelos sacan el
  peso propio de la viga de A * gamma (modelo_lt2.py, benchmark_3d.py),
  y el peso de la losa ya entra por separado como carga tributaria. Si
  el area incluyera el ala, la losa pesaria DOS VECES y el equilibrio
  cerraria igual, sin avisar. Iy y J tampoco: el ala casi no ayuda a
  la flexion en planta (que ademas toma el diafragma) ni a la torsion,
  y dejarlos es el lado seguro.

  Uso:  python comun/losa_colaborante.py [lt2|ingenieria|conjunto]
================================================================
"""
from __future__ import annotations

import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _AQUI)

# ACI 318-08 8.12.2
FRACCION_LUZ = 4.0          # b_eff <= L / 4
ESPESORES_POR_LADO = 8.0    # ala por lado <= 8 hf


def ancho_efectivo(bw, h, hf, L, b_trib=None):
    """
    El ancho de ala que ACI deja usar para ESTA viga, en m.

    b_trib es el ancho tributario TOTAL de la viga (su area tributaria
    dividida por su luz). Si no se sabe, no se aplica ese tope: los
    otros dos siguen acotando, y el resultado es mayor o igual, o sea
    hay que pasarlo cuando se tenga.
    """
    bw, hf, L = float(bw), float(hf), float(L)
    if bw <= 0 or hf <= 0 or L <= 0:
        return bw
    topes = [L / FRACCION_LUZ, bw + 2.0 * ESPESORES_POR_LADO * hf]
    if b_trib:
        topes.append(float(b_trib))
    # Nunca menos que el alma: una viga muy corta se queda sin ala.
    return max(bw, min(topes))


def inercia_T(bw, h, hf, b_eff):
    """
    Inercia de gravedad de la seccion T respecto de su centro de
    gravedad, en m4. Con b_eff = bw devuelve la del rectangulo.
    """
    bw, h, hf, b_eff = float(bw), float(h), float(hf), float(b_eff)
    rect = bw * h ** 3 / 12.0
    ala = b_eff - bw
    if ala <= 1e-9 or hf <= 1e-9 or hf >= h:
        return rect
    # y se mide desde la fibra INFERIOR; el ala esta arriba.
    Aw, Af = bw * h, ala * hf
    yw, yf = h / 2.0, h - hf / 2.0
    yg = (Aw * yw + Af * yf) / (Aw + Af)
    return (rect + Aw * (yw - yg) ** 2
            + ala * hf ** 3 / 12.0 + Af * (yf - yg) ** 2)


def propiedades(bw, h, hf, L, b_trib=None):
    """
    Todo junto, para quien arma una viga:
      b_eff, Iz (con ala), Iz_rectangular, y cual de los topes mando.
    El AREA no se devuelve a proposito: se queda rectangular (ver la
    cabecera de este modulo).
    """
    b_eff = ancho_efectivo(bw, h, hf, L, b_trib)
    topes = {'L/4': L / FRACCION_LUZ,
             'bw+16hf': bw + 2.0 * ESPESORES_POR_LADO * hf}
    if b_trib:
        topes['tributario'] = float(b_trib)
    manda = min(topes, key=lambda k: topes[k])
    rect = bw * h ** 3 / 12.0
    Iz = inercia_T(bw, h, hf, b_eff)
    return {'b_eff': b_eff, 'Iz': Iz, 'Iz_rectangular': rect,
            'razon': Iz / rect if rect else 1.0, 'manda': manda}


def _main(argv):
    import json
    import math
    import collections
    import rutas
    eds = argv or ['lt2', 'ingenieria']
    fallos = []

    def check(cond, msg, detalle=''):
        print('  [%s] %s' % ('OK  ' if cond else 'FALLA', msg))
        if detalle:
            print('         %s' % detalle)
        if not cond:
            fallos.append(msg)

    print('=' * 64)
    print('  LA LOSA COLABORANTE (ACI 318-08 8.12.2)')
    print('=' * 64)

    print('\n[1] la formula, contra casos con respuesta conocida')
    check(abs(inercia_T(0.3, 0.6, 0.25, 0.3) - 0.3 * 0.6 ** 3 / 12) < 1e-15,
          'sin ala (b_eff = bw) da la inercia del rectangulo')
    check(inercia_T(0.3, 0.6, 0.25, 1.25) > 0.3 * 0.6 ** 3 / 12,
          'con ala da mas que el rectangulo')
    check(abs(ancho_efectivo(0.3, 0.6, 0.25, 5.0) - 1.25) < 1e-12,
          'en una viga de 5.00 m manda L/4 = 1.25 m')
    check(abs(ancho_efectivo(0.3, 0.6, 0.25, 0.4) - 0.3) < 1e-12,
          'en una viga de 0.40 m el ala no baja del alma (b_eff = bw)')
    # Una T simetrica respecto de su centro no existe, pero el caso
    # limite hf -> h tiene que dar el rectangulo de ancho b_eff.
    I = inercia_T(0.3, 0.5, 0.4999999, 1.0)
    check(I > 0, 'el caso limite hf -> h no explota', 'Iz = %.6f' % I)

    for ed in eds:
        ruta = os.path.join(rutas.UNITY, '%s.json' % ed)
        if not os.path.exists(ruta):
            continue
        with open(ruta, encoding='utf-8') as f:
            m = json.load(f)
        N = {n['id']: n for n in m['nodos']}
        S = {s['nombre']: s for s in m['secciones']}
        print('\n[2] %s: que daria el ala en cada viga' % ed)
        manda = collections.Counter()
        razones = []
        for e in m['elementos']:
            if not e['tipo'].startswith('viga') or e['tipo'] == 'viga_metal':
                continue
            s = S.get(e['seccion'])
            if not s or not s.get('b') or not s.get('h'):
                continue
            a, b = N.get(e['n1']), N.get(e['n2'])
            if not a or not b:
                continue
            L = math.dist((a['x'], a['y'], a['z']), (b['x'], b['y'], b['z']))
            At = e.get('area_tributaria') or 0.0
            r = propiedades(s['b'], s['h'], 0.25, L, (At / L) if At and L else None)
            manda[r['manda']] += 1
            razones.append(r['razon'])
        if not razones:
            continue
        razones.sort()
        print('         %d vigas; Iz x%.2f de mediana (de x%.2f a x%.2f)'
              % (len(razones), razones[len(razones) // 2], razones[0], razones[-1]))
        print('         tope que manda: %s' % dict(manda))
        check(razones[0] >= 1.0, '%s: ninguna viga PIERDE inercia con el ala' % ed,
              'la menor razon es x%.4f' % razones[0])

    print()
    if fallos:
        print('  %d FALLA(S)' % len(fallos))
        return 1
    print('  TODO OK')
    return 0


if __name__ == '__main__':
    sys.exit(_main(sys.argv[1:]))
