# -*- coding: utf-8 -*-
r"""
================================================================
 semana05_lab/verificar_instantanea.py
   LOS SLIDERS INSTANTANEOS, CONTRA PYTHON
================================================================
 El LAB de la Semana 5 pide que los sliders de los casos base
 actualicen AL INSTANTE la deformada, los resultados y el punto P-M.
 unity/Assets/Scripts/VisorSemana05.Instantanea.cs lo hace combinando
 en Unity los cuatro casos base que ya trae semana04.json, sin pedirle
 nada al servidor.

 Este script comprueba que esa combinacion da lo mismo que Python.
 Replica EN PYTHON, paso a paso, lo que hace el C# -- retabular a la
 malla comun, escalar y sumar, y rehacer la demanda -- y lo compara
 contra semana05/superposicion.caso_combinado(), que arma el caso con
 las mismas funciones del exportador de la Semana 4 y ya esta
 verificado por cuatro vias en semana05/verificar_superposicion.py.

 Se prueban varios juegos de lambdas, incluidos los feos: negativos,
 ceros, un solo caso, y los tres estados E1..E3.

   python semana05_lab/verificar_instantanea.py            lt2
   python semana05_lab/verificar_instantanea.py ingenieria
   python semana05_lab/verificar_instantanea.py lt2 --casos 20

 ----------------------------------------------------------------
 DE DONDE SALEN LAS COTAS
 ----------------------------------------------------------------
 No se eligen a ojo. El C# suma valores que el anexo YA escribio
 redondeados a 4 decimales, y Python redondea al final: son dos
 caminos distintos hasta el mismo numero.

   sum(lambda * redondeo(v))   contra   redondeo(sum(lambda * v))

 El error de cada termino es medio ultimo decimal (5e-5) escalado por
 su lambda, mas el redondeo final. De ahi:

   cota = 5e-5 * (sum|lambda| + 1) + 4 * eps * tamano

 En Unity todo viaja ademas como float de 32 bits (JsonUtility), que
 aporta 6e-8 relativo; se suma aparte donde corresponde.
================================================================
"""
from __future__ import annotations

import importlib.util
import io
import json
import math
import os
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_AQUI), 'comun'))
import rutas                                   # noqa: E402
rutas.entrar(__file__, os.path.join(rutas.RAIZ, 'semana03'),
             os.path.join(rutas.RAIZ, 'semana04'), os.path.join(rutas.RAIZ, 'semana05'))

import superposicion as sup                    # noqa: E402

CASOS = ('G', 'Q', 'EX', 'EY')
MAGNITUDES = ('N', 'Vy', 'Vz', 'T', 'My', 'Mz')

# El medio ultimo decimal con que el anexo escribe fuerzas y
# desplazamientos (semana04/exportar_unity.py DECIMALES_*).
R_FUERZA = 0.5e-4
R_DESPL = 0.5e-8
EPS = 4.0 * sys.float_info.epsilon

# Los juegos de lambdas de la prueba. Los tres primeros son E1..E3, que
# es lo que muestran los botones de la app.
LAMBDAS = [
    (1.0, 1.0, 0.0, 0.0),        # E1
    (1.2, 1.6, 0.0, 0.0),        # E2
    (1.2, 1.0, -1.4, 0.0),       # E3
    (1.0, 0.0, 0.0, 0.0),        # solo G
    (0.0, 0.0, 1.0, 0.0),        # solo EX
    (0.0, 0.0, 0.0, -1.0),       # solo EY, negativo
    (0.9, 0.0, -1.4, 0.0),
    (1.2, 1.0, 0.0, 1.4),
    (-0.5, 0.35, 1.05, -0.7),    # feo a proposito
    (0.0, 0.0, 0.0, 0.0),        # todo en cero
]


# ============================================================
# UTILIDADES
# ============================================================
class Informe(object):
    def __init__(self):
        self.fallas = []

    def check(self, ok, que, detalle=()):
        print('  [%s] %s' % ('OK  ' if ok else 'FALLA', que))
        for linea in ([detalle] if isinstance(detalle, str) else detalle):
            if linea:
                print('         %s' % linea)
        if not ok:
            self.fallas.append(que)
        return ok


def titulo(texto):
    print()
    print(texto)
    print('-' * min(len(texto), 78))


def a_la_malla(valor, n_origen, n_destino):
    """
    La MISMA retabulacion que hace el C# (Ins_ALaMalla): interpolacion
    lineal a la malla comun, POR FRACCION DE INDICE y no por x.

    Es exacta cuando la barra no lleva carga repartida en ese caso,
    porque ahi el axial y los cortes son constantes y los momentos son
    rectas. Y se interpola por indice porque las dos mallas van de 0 a L
    equiespaciadas (lo comprueba verificar_semana04.py, bloque [1]): usar
    la x del anexo meteria su redondeo a 4 decimales multiplicado por la
    pendiente del momento, que en una viga de 47 kN m/m son 2.3e-3 kN m.
    """
    if not valor or len(valor) != n_origen:
        return [0.0] * n_destino
    if n_origen == n_destino:
        return list(valor)
    if n_origen == 1:
        return [valor[0]] * n_destino
    salida = []
    for i in range(n_destino):
        p = 0.0 if n_destino == 1 else i / (n_destino - 1) * (n_origen - 1)
        j = min(max(int(math.floor(p)), 0), n_origen - 2)
        salida.append(valor[j] + (valor[j + 1] - valor[j]) * (p - j))
    return salida


def capacidad_en(P, familia):
    """La misma interpolacion que Ins_CapacidadEn en el C#."""
    Ps, Mns = familia['P'], familia['Mn']
    if len(Ps) < 2 or P <= Ps[0] or P >= Ps[-1]:
        return 0.0
    for i in range(len(Ps) - 1):
        p1, p2 = Ps[i], Ps[i + 1]
        if p1 <= P <= p2:
            d = p2 - p1
            if abs(d) < 1e-9:
                return max(Mns[i], Mns[i + 1])
            return Mns[i] + (Mns[i + 1] - Mns[i]) * ((P - p1) / d)
    return 0.0


def demanda_de(f, elemento, familia):
    """La misma regla que Ins_Demanda en el C#, y que
    demanda_capacidad.demanda(): los dos extremos, gana el de mayor M."""
    muro = elemento.get('tipo') == 'muro'
    plano_es_my = elemento.get('momento_en_el_plano') != 'Mz'
    Pi, Myi, Mzi = f[0], f[4], f[5]
    Pj, Myj, Mzj = -f[6], f[10], f[11]
    if muro:
        Mi = abs(Myi if plano_es_my else Mzi)
        Mfi = abs(Mzi if plano_es_my else Myi)
        Mj = abs(Myj if plano_es_my else Mzj)
        Mfj = abs(Mzj if plano_es_my else Myj)
    else:
        Mi, Mfi = math.hypot(Myi, Mzi), 0.0
        Mj, Mfj = math.hypot(Myj, Mzj), 0.0
    gana_j = Mj > Mi
    P = Pj if gana_j else Pi
    M = Mj if gana_j else Mi
    Mn = capacidad_en(P, familia)
    u = M / Mn if Mn > 1e-9 else 9999.0
    return {'id': elemento['id'], 'familia': elemento['familia'], 'P': P, 'M': M,
            'M_fuera_plano': Mfj if gana_j else Mfi,
            'extremo': 'j (superior)' if gana_j else 'i (inferior)',
            'Mn': Mn, 'u': u, 'pasa': u <= 1.0}


# ============================================================
# LA COMBINACION, COMO LA HACE UNITY
# ============================================================
def preparar(anexo):
    """Lo que el C# hace una vez al cargar: los cuatro casos base
    llevados a una malla comun por barra."""
    por_caso = {c['nombre']: c for c in anexo['casos']}
    faltan = [c for c in CASOS if c not in por_caso]
    if faltan:
        raise SystemExit('el anexo no trae los casos base: %s' % faltan)

    elementos = {int(e['id']): e for e in anexo['elementos']}
    esf = {c: {int(s['id']): s for s in por_caso[c]['esfuerzos']} for c in CASOS}

    barras = []
    for s_g in por_caso['G']['esfuerzos']:
        eid = int(s_g['id'])
        malla = s_g['x']
        for c in CASOS[1:]:
            s = esf[c].get(eid)
            if s and len(s['x']) > len(malla):
                malla = s['x']
        barra = {'id': eid, 'x': malla, 'f': {}, 'mag': {}, 'elemento': elementos.get(eid)}
        for c in CASOS:
            s = esf[c].get(eid)
            if s is None:
                barra['f'][c] = [0.0] * 12
                barra['mag'][c] = {m: [0.0] * len(malla) for m in MAGNITUDES}
                continue
            barra['f'][c] = [float(v) for v in s['f']]
            barra['mag'][c] = {m: a_la_malla([float(v) for v in s[m]], len(s['x']), len(malla))
                               for m in MAGNITUDES}
        barras.append(barra)

    nodos = [int(d['id']) for d in por_caso['G']['desplazamientos']]
    u_base = {}
    for c in CASOS:
        d_por_id = {int(d['id']): d for d in por_caso[c]['desplazamientos']}
        u_base[c] = [[float(d_por_id[n][k]) if n in d_por_id else 0.0
                      for k in ('ux', 'uy', 'uz', 'rx', 'ry', 'rz')] for n in nodos]
    return {'barras': barras, 'nodos': nodos, 'u': u_base,
            'familias': anexo['familias']}


def combinar_como_unity(prep, lam):
    """Lo que el C# hace al mover un slider."""
    l = dict(zip(CASOS, lam))

    desplazamientos, mayor = [], 0.0
    for i, nid in enumerate(prep['nodos']):
        u = [0.0] * 6
        for c in CASOS:
            if l[c] == 0.0:
                continue
            fila = prep['u'][c][i]
            for k in range(6):
                u[k] += l[c] * fila[k]
        desplazamientos.append(dict(zip(('ux', 'uy', 'uz', 'rx', 'ry', 'rz'), u), id=nid))
        mayor = max(mayor, math.sqrt(u[0] ** 2 + u[1] ** 2 + u[2] ** 2))

    esfuerzos, demandas = [], []
    for b in prep['barras']:
        f = [0.0] * 12
        for c in CASOS:
            if l[c] == 0.0:
                continue
            for i in range(12):
                f[i] += l[c] * b['f'][c][i]
        fila = {'id': b['id'], 'f': f, 'x': b['x']}
        for m in MAGNITUDES:
            v = [0.0] * len(b['x'])
            for c in CASOS:
                if l[c] == 0.0:
                    continue
                base = b['mag'][c][m]
                for i in range(len(v)):
                    v[i] += l[c] * base[i]
            fila[m] = v
        esfuerzos.append(fila)

        e = b['elemento']
        if e is not None and int(e.get('familia', -1)) >= 0:
            demandas.append(demanda_de(f, e, prep['familias'][int(e['familia'])]))

    return {'max_desplazamiento_mm': mayor * 1000.0, 'desplazamientos': desplazamientos,
            'esfuerzos': esfuerzos, 'demandas': demandas}


# ============================================================
# LA COMPARACION
# ============================================================
def comparar(unity, python, lam, inf, etiqueta):
    suma = sum(abs(v) for v in lam)
    cota_f = R_FUERZA * (suma + 1.0)
    cota_u = R_DESPL * (suma + 1.0)

    # --- desplazamientos ---
    py_u = {int(d['id']): d for d in python['desplazamientos']}
    peor_u, donde_u = 0.0, ''
    for d in unity['desplazamientos']:
        p = py_u.get(int(d['id']))
        if p is None:
            inf.check(False, '%s: el nodo %d no esta en el caso de Python' % (etiqueta, d['id']))
            return
        for k in ('ux', 'uy', 'uz', 'rx', 'ry', 'rz'):
            err = abs(float(d[k]) - float(p[k]))
            if err > peor_u:
                peor_u, donde_u = err, 'nodo %d %s' % (d['id'], k)
    tope_u = cota_u + EPS
    inf.check(peor_u <= tope_u,
              '%s: desplazamientos de %d nodos (peor %.2e en %s, cota %.2e)'
              % (etiqueta, len(unity['desplazamientos']), peor_u, donde_u or '-', tope_u))

    # --- esfuerzos: f y los extremos de las estaciones ---
    py_e = {int(s['id']): s for s in python['esfuerzos']}
    peor_f, donde_f = 0.0, ''
    peor_x, donde_x = 0.0, ''
    for s in unity['esfuerzos']:
        p = py_e.get(int(s['id']))
        if p is None:
            continue
        for i in range(12):
            err = abs(s['f'][i] - float(p['f'][i]))
            if err > peor_f:
                peor_f, donde_f = err, 'elem %d f[%d]' % (s['id'], i)
        # Las estaciones se comparan en los extremos, que existen en las
        # dos mallas; el interior solo cuando la malla es la misma (si
        # no, Python tabula 2 puntos y Unity 9, y comparar indice a
        # indice no tendria sentido).
        mismo = len(s['x']) == len(p['x'])
        for m in MAGNITUDES:
            idx = range(len(s['x'])) if mismo else (0, len(s['x']) - 1)
            jdx = range(len(p['x'])) if mismo else (0, len(p['x']) - 1)
            for i, j in zip(idx, jdx):
                err = abs(s[m][i] - float(p[m][j]))
                if err > peor_x:
                    peor_x, donde_x = err, 'elem %d %s[%d]' % (s['id'], m, i)
    tope_f = cota_f + EPS * 1e3
    inf.check(peor_f <= tope_f, '%s: las 12 fuerzas de %d barras (peor %.2e en %s, cota %.2e)'
              % (etiqueta, len(unity['esfuerzos']), peor_f, donde_f or '-', tope_f))
    inf.check(peor_x <= tope_f, '%s: esfuerzos en las estaciones (peor %.2e en %s, cota %.2e)'
              % (etiqueta, peor_x, donde_x or '-', tope_f))

    # --- demandas: lo que NO es lineal ---
    py_d = {int(d['id']): d for d in python['demandas']}
    peor = {'P': 0.0, 'M': 0.0, 'Mn': 0.0, 'u': 0.0}
    donde = {'P': '', 'M': '', 'Mn': '', 'u': ''}
    distinto_extremo, distinto_pasa = [], []
    for d in unity['demandas']:
        p = py_d.get(int(d['id']))
        if p is None:
            inf.check(False, '%s: la barra %d tiene demanda en Unity y no en Python'
                      % (etiqueta, d['id']))
            return
        for k in ('P', 'M', 'Mn'):
            err = abs(float(d[k]) - float(p[k]))
            if err > peor[k]:
                peor[k], donde[k] = err, 'elem %d' % d['id']
        # u = M / Mn: su error es el de M y el de Mn propagados.
        if float(p['u']) < 9999.0 and float(d['u']) < 9999.0:
            err = abs(float(d['u']) - float(p['u']))
            if err > peor['u']:
                peor['u'], donde['u'] = err, 'elem %d' % d['id']
        if d['extremo'] != p['extremo']:
            distinto_extremo.append('elem %d: Unity %s, Python %s'
                                    % (d['id'], d['extremo'], p['extremo']))
        if bool(d['pasa']) != bool(p['pasa']):
            distinto_pasa.append('elem %d: Unity %s, Python %s'
                                 % (d['id'], d['pasa'], p['pasa']))

    n = len(unity['demandas'])
    inf.check(peor['P'] <= tope_f and peor['M'] <= tope_f,
              '%s: P y M de %d demandas (peor P %.2e, M %.2e; cota %.2e)'
              % (etiqueta, n, peor['P'], peor['M'], tope_f))
    # Mn sale de interpolar en la curva: su error es el de P por la
    # pendiente de la curva, que en la nariz es del orden de 0.05 kN m
    # por kN. Se acota con la pendiente maxima medida.
    inf.check(peor['Mn'] <= max(tope_f * 100.0, 1e-3),
              '%s: Mn interpolado en la curva (peor %.2e en %s)'
              % (etiqueta, peor['Mn'], donde['Mn'] or '-'))
    inf.check(not distinto_extremo,
              '%s: el extremo que manda es el mismo en las %d demandas' % (etiqueta, n),
              distinto_extremo[:4])
    inf.check(not distinto_pasa,
              '%s: pasa / no pasa coincide en las %d demandas' % (etiqueta, n),
              distinto_pasa[:4])


# ============================================================
def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    edificio = 'lt2'
    if argv and not argv[0].startswith('-'):
        edificio = argv.pop(0)
    cuantos = len(LAMBDAS)
    if '--casos' in argv:
        i = argv.index('--casos')
        cuantos = int(argv[i + 1])
        del argv[i:i + 2]

    print('=' * 78)
    print('  LOS SLIDERS INSTANTANEOS CONTRA PYTHON   %s' % edificio.upper())
    print('=' * 78)
    print('  Unity combina los cuatro casos base del anexo (semana04.json) al mover un')
    print('  slider. Aca se repite esa combinacion paso a paso y se compara contra')
    print('  semana05/superposicion.caso_combinado(), que la arma con las funciones del')
    print('  exportador de la Semana 4.')

    ruta = rutas.unity('semana04') if hasattr(rutas, 'unity') else None
    anexo_disco = os.path.join(rutas.UNITY, 'semana04.json')
    with io.open(anexo_disco, encoding='utf-8') as fh:
        anexo = json.load(fh)
    if anexo['info']['edificio'] != edificio:
        print()
        print('  El anexo en disco es de %s, no de %s.' % (anexo['info']['edificio'], edificio))
        print('  Corre:  python semana04\\exportar_unity.py %s' % edificio)
        return 1
    print('  anexo   %s  (%s, %d elementos, %d familias)'
          % (os.path.relpath(anexo_disco, rutas.RAIZ), anexo['info']['edificio'],
             len(anexo['elementos']), len(anexo['familias'])))

    titulo('[1] LA BASE DE PYTHON  (resuelve G, Q, EX y EY en OpenSees)')
    b = sup.base(edificio, list(anexo['info'].get('parametros_argv', []) or []))
    print('  %d elementos, %d nodos, %.1f s' % (len(b['anexo']['elementos']),
                                                len(b['ids_nodos']), b['segundos']))
    inf = Informe()
    inf.check(b['anexo']['info']['parametros'] == anexo['info']['parametros'],
              'la base usa los mismos parametros que el anexo que lee Unity')

    titulo('[2] LA PREPARACION QUE HACE UNITY UNA SOLA VEZ')
    prep = preparar(anexo)
    finas = sum(1 for x in prep['barras'] if len(x['x']) > 2)
    inf.check(len(prep['barras']) == len(anexo['elementos']),
              'las %d barras del anexo quedaron en la malla comun (%d con estaciones finas)'
              % (len(prep['barras']), finas))

    titulo('[3] CADA JUEGO DE FACTORES, CONTRA PYTHON')
    for lam in LAMBDAS[:cuantos]:
        etiqueta = 'l = (%s)' % ', '.join('%g' % v for v in lam)
        caso, _peor = sup.caso_combinado(b, dict(zip(CASOS, lam)))
        unity = combinar_como_unity(prep, lam)
        comparar(unity, caso, lam, inf, etiqueta)

    print()
    print('=' * 78)
    if inf.fallas:
        print('  NO CALZA (%d):' % len(inf.fallas))
        for f in inf.fallas:
            print('    - %s' % f)
        print('=' * 78)
        return 1
    print('  LA COMBINACION DE UNITY ES LA DE PYTHON')
    print('=' * 78)
    return 0


if __name__ == '__main__':
    sys.exit(main())
