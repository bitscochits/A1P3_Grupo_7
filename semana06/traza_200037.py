# -*- coding: utf-8 -*-
r"""
================================================================
 semana06/traza_200037.py
   UN ELEMENTO REAL, DE LA LAMINA AL TELEFONO: LA COLUMNA 200037
================================================================
 La evidencia del punto 4 de reports/semana06.md. Cada eslabon se
 comprueba contra el anterior con una cota que sale de su causa:

   [1] PLANO      la planta 2024_22-101 dibuja el pilar donde el modelo
                  del LT2 pone su elemento 37, con la seccion del modelo;
                  la elevacion 2024_22-305 da su enfierradura.
   [2] CALCE      el conjunto lo corre (dx, dy) de edificios/conjunto/
                  calce.json y le suma 200000 al tag: 37 -> 200037.
   [3] OPENSEES   el conjunto resuelto AHORA, leyendo localForce SIN el
                  redondeo del servidor, contra lo que trae la app
                  (semana06_lab/web/datos/ar.json). Y la combinacion de
                  la app corrida como UN caso de carga.
   [4] DEMANDA    P, M, Mn y u rehechos desde esas fuerzas con la regla de
                  demanda_capacidad, contra los de la app; cual gobierna.
   [5] PANEL      lo que escribe el panel del telefono (ar.js), con su
                  mismo formato.
   [6] JUNTA      el LT2 solo y el LT2 dentro del conjunto dan lo mismo.

 La parte modelo -> OpenSees -> JSON -> float32 de Unity la hace
 semana04/trazabilidad.py conjunto 200037 (LA CADENA CALZA).

   python semana06/traza_200037.py
   python semana06/traza_200037.py --salida     # + evidencia/traza_200037.txt
================================================================
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
import math
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'comun'))
import rutas                                   # noqa: E402
rutas.entrar(__file__, os.path.join(rutas.RAIZ, 'semana03'))

import openseespy.opensees as ops              # noqa: E402
import combinar                                # noqa: E402
import contrato                                # noqa: E402
import servidor_opensees as motor              # noqa: E402
import lab_semana03 as lab                     # noqa: E402
import parametros                              # noqa: E402
import demanda_capacidad as dc                 # noqa: E402

from precision_ar import Tee, ruta_rel         # noqa: E402

EID = 200037
AR_JSON = os.path.join(rutas.RAIZ, 'semana06_lab', 'web', 'datos', 'ar.json')
CALCE = os.path.join(rutas.EDIFICIOS, 'conjunto', 'calce.json')
PASO_DE_TAG = 100000          # edificios/conjunto/armar.py: (i + 1) * PASO_DE_TAG
CASOS = ('G', 'Q', 'EX', 'EY')
R_F, R_U = 0.5e-4, 0.5e-8     # el servidor escribe 4 decimales en kN y 8 en m
EPS = sys.float_info.epsilon
COMPONENTES = ('N', 'Vy', 'Vz', 'T', 'My', 'Mz')


class Informe(object):
    def __init__(self):
        self.fallas = []

    def check(self, ok, que, *detalle):
        print('  [%s] %s' % ('OK  ' if ok else 'FALLA', que))
        for d in detalle:
            print('         %s' % d)
        if not ok:
            self.fallas.append(que)
        return ok


def titulo(t):
    print()
    print(t)
    print('-' * min(len(t), 78))


def leer(ruta):
    with io.open(ruta, encoding='utf-8') as fh:
        return json.load(fh)


# ============================================================
# [1] PLANO y [2] CALCE
# ============================================================
def plano_y_calce(inf, conj):
    titulo('[1] PLANO: la lamina dibuja lo que el modelo del LT2 usa')
    geo = leer(rutas.geometria('lt2'))
    lt2 = leer(rutas.modelo('lt2'))
    nl = {int(n['id']): n for n in lt2['nodos']}
    e_lt2 = next(e for e in lt2['elementos'] if int(e['id']) == EID - 2 * PASO_DE_TAG)
    ni, nj = nl[int(e_lt2['n1'])], nl[int(e_lt2['n2'])]
    lam = geo['lamina_de_referencia']
    cerca = [p for p in geo['plantas'][lam]['pilares']
             if math.hypot(p['x'] - ni['x'], p['y'] - ni['y']) < 0.5]
    inf.check(len(cerca) == 1 and cerca[0]['contorno_cerrado']
              and abs(cerca[0]['x'] - ni['x']) < 1e-9 and abs(cerca[0]['y'] - ni['y']) < 1e-9,
              'planta %s: un pilar de contorno cerrado en (%.4f, %.4f) m = el elemento %d del LT2 '
              '(nodos %d -> %d)' % (lam, cerca[0]['x'], cerca[0]['y'], int(e_lt2['id']),
                                    int(e_lt2['n1']), int(e_lt2['n2'])))
    p = cerca[0]
    sec = next(s for s in lt2['secciones'] if s['nombre'] == e_lt2['seccion'])
    inf.check(abs(p['b'] - 0.70) < 1e-9 and abs(p['h'] - 0.70) < 1e-9
              and abs(sec['A'] - p['b'] * p['h']) < 1e-9,
              'seccion del contorno %.2f x %.2f m (rotulo "%s") = la del modelo, %s (A = %.2f m2)'
              % (p['b'], p['h'], p['etiqueta'], e_lt2['seccion'], sec['A']))
    ejes = {(k, x['nombre']): x['coord'] for k in ('X', 'Y') for x in geo['ejes'][k]}
    print('         el contorno esta a (%+.4f, %+.4f) m del cruce de los ejes C y 2: la posicion sale '
          'del dibujo del pilar, no del cruce de ejes' % (p['x'] - ejes[('X', 'C')], p['y'] - ejes[('Y', '2')]))

    ec = next(e for e in conj['elementos'] if int(e['id']) == EID)
    enf = ec['enfierradura']
    fuente = enf['fuente']
    elev = [x for x in geo['enfierradura']['pilares']
            if x['lamina'] == fuente['lamina'] and x['elevacion'] == fuente['elevacion']
            and abs(x['cota'] - ni['z']) < 1e-6]
    elev = min(elev, key=lambda x: math.hypot(x['x'] - ni['x'], x['y'] - ni['y']))
    textos = ' '.join(ll['texto'] for ll in elev['llamadas'])
    trabas = sum(t['cantidad'] for t in enf['trabas']) + sum(t['cantidad'] for t in enf['trabas_longitudinales'])
    lon = enf['longitudinal']
    inf.check(elev['rotulo'] == 'P.70x70' and trabas == sum(ll['cantidad'] for ll in elev['llamadas']
                                                            if ll['tipo'] in ('T', 'TL')),
              'elevacion %s, %s, cota %.2f: "%s  %s" (residuo de la asignacion %.4f m, en el dato)'
              % (fuente['lamina'], fuente['elevacion'], elev['cota'], elev['rotulo'], textos,
                 fuente['residuo_m']))
    inf.check(lon['cantidad'] == 4 * lon['por_cara'] - 4 and lon['por_cara'] == 2 + trabas // 2,
              'fierro longitudinal: %d trabas (T + TL), cada una amarra una barra intermedia en dos '
              'caras opuestas -> %d intermedias + 2 esquinas = %d por cara -> 4 x %d - 4 = %d barras'
              % (trabas, trabas // 2, lon['por_cara'], lon['por_cara'], lon['cantidad']),
              'diametro D%.0f: %s. rho = %.2f %%'
              % (lon['diametro_mm'], lon['origen'],
                 100 * lon['cantidad'] * math.pi * (lon['diametro_mm'] / 2000.0) ** 2 / sec['A']))

    titulo('[2] CALCE: el conjunto corre el LT2 y le renumera los tags')
    c = leer(CALCE)['edificios']['lt2']
    nc = {int(n['id']): n for n in conj['nodos']}
    ok = True
    for n_lt2 in (int(e_lt2['n1']), int(e_lt2['n2'])):
        a, b = nl[n_lt2], nc[n_lt2 + 2 * PASO_DE_TAG]
        d = max(abs(a['x'] + c['dx'] - b['x']), abs(a['y'] + c['dy'] - b['y']), abs(a['z'] - b['z']))
        ok = ok and d < 1e-9
    inf.check(ok and int(ec['n1']) == int(e_lt2['n1']) + 2 * PASO_DE_TAG
              and int(ec['n2']) == int(e_lt2['n2']) + 2 * PASO_DE_TAG and abs(c['giro_grados']) < 1e-12,
              'calce.json: dx = %.3f, dy = %+.3f, sin giro; tag + %d: elemento %d -> %d, nodos %d -> %d y '
              '%d -> %d' % (c['dx'], c['dy'], 2 * PASO_DE_TAG, int(e_lt2['id']), EID, int(e_lt2['n1']),
                            int(ec['n1']), int(e_lt2['n2']), int(ec['n2'])),
              '(%.4f %+.3f, %.4f %+.3f) = (%.4f, %.4f): el nodo %d del conjunto'
              % (ni['x'], c['dx'], ni['y'], c['dy'], nc[int(ec['n1'])]['x'], nc[int(ec['n1'])]['y'],
                 int(ec['n1'])))
    s_c = next(s for s in conj['secciones'] if s['nombre'] == ec['seccion'])
    E35 = 4700.0 * math.sqrt(35.0) * 1000.0
    inf.check(abs(s_c['E'] - E35) < 1e-3 and s_c.get('fpc_MPa') == 35,
              'la seccion del conjunto lleva su propio hormigon: E = %.2f kPa = 4700 sqrt(35) 1000, '
              'fpc 35 MPa (el material del conjunto dice %s MPa y la seccion lo pisa)'
              % (s_c['E'], conj['material'].get('fpc_MPa')))
    return ec


# ============================================================
# [3] OPENSEES SIN REDONDEAR, contra la app
# ============================================================
def opensees(inf, conj, ar):
    titulo('[3] OPENSEES, resuelto ahora y SIN el redondeo del servidor, contra la app')
    p = parametros.cargar([])
    with contextlib.redirect_stdout(io.StringIO()):
        arm = lab.armar_casos(conj, p)
    casos = arm['casos']
    datos = copy.deepcopy(conj)
    datos['casos_de_carga'] = [casos[c] for c in CASOS]
    with contextlib.redirect_stdout(io.StringIO()):
        coords, _avisos, _restr = motor.construir_modelo(datos)
    e = next(x for x in conj['elementos'] if int(x['id']) == EID)
    ni, nj = int(e['n1']), int(e['n2'])
    inf.check(list(ops.eleNodes(EID)) == [ni, nj],
              'dentro de OpenSees, eleNodes(%d) = [%d, %d]: el tag del JSON es el de OpenSees'
              % (EID, ni, nj))
    nodos = set(coords)
    elems = {int(x['id']) for x in datos['elementos']}

    previo = [None]

    def resolver(caso, tag):
        if previo[0] is not None:
            ops.remove('loadPattern', previo[0])
        ops.reset()
        ops.setTime(0.0)
        with contextlib.redirect_stdout(io.StringIO()):
            motor.aplicar_cargas(caso, tag, nodos, elems)
        if motor.resolver_caso() != 0:
            raise SystemExit('OpenSees no resolvio %s' % caso.get('nombre'))
        previo[0] = tag
        return (list(ops.eleResponse(EID, 'localForce')),
                [ops.nodeDisp(ni, k) for k in range(1, 7)] + [ops.nodeDisp(nj, k) for k in range(1, 7)])

    res = {c: resolver(casos[c], 100 + i) for i, c in enumerate(CASOS)}
    por_nombre = {c['nombre']: c for c in ar['casos']}
    peor = 0.0
    for c in CASOS:
        f_ar = por_nombre[c]['esfuerzos'][str(EID)]['f']
        peor = max(peor, max(abs(a - b) for a, b in zip(f_ar, res[c][0])))
    inf.check(peor <= R_F + 4 * EPS * 1e4,
              'casos base G, Q, EX y EY: max |app - OpenSees| = %.2e kN o kN m (cota %.0e: el '
              'servidor escribe 4 decimales)' % (peor, R_F))

    nombre = ar['info']['caso_por_defecto']
    lam = dict(zip(CASOS, por_nombre[nombre]['factores']))
    suma_l = sum(abs(v) for v in lam.values())
    f_sup = [sum(lam[c] * res[c][0][k] for c in CASOS) for k in range(12)]
    u_sup = [sum(lam[c] * res[c][1][k] for c in CASOS) for k in range(12)]
    caso_c = combinar.combinar_cargas(dict(datos, casos_de_carga=[casos[c] for c in CASOS]), lam, 'COMB')
    f_exp, u_exp = resolver(caso_c, 200)
    d_f = max(abs(a - b) for a, b in zip(f_sup, f_exp))
    d_u = max(abs(a - b) for a, b in zip(u_sup, u_exp))
    inf.check(d_f <= R_F and d_u <= R_U,
              '%s corrida como UN caso de carga contra la suma de los casos: %.1e kN y %.1e m '
              '(bajo el paso del servidor, %.0e / %.0e: el modelo es lineal)' % (nombre, d_f, d_u, R_F, R_U))

    C = por_nombre[nombre]
    f_ar = C['esfuerzos'][str(EID)]['f']
    cota = R_F * (suma_l + 1)
    d_ar = max(abs(a - b) for a, b in zip(f_ar, f_sup))
    k_peor = max(range(12), key=lambda k: abs(f_ar[k] - f_sup[k]))
    inf.check(d_ar <= cota + 4 * EPS * 1e4,
              '%s: max |app - OpenSees| = %.2e en %s_%s (cota 0.5e-4 x (%.1f + 1) = %.2e: cada caso '
              'redondeado por su factor, mas el redondeo de la combinacion)'
              % (nombre, d_ar, COMPONENTES[k_peor % 6], 'ij'[k_peor // 6], suma_l, cota))
    print('         %-10s %s' % ('', ''.join('%12s' % c for c in COMPONENTES)))
    for etq, v in (('OpenSees i', f_sup[:6]), ('app i', f_ar[:6]),
                   ('OpenSees j', f_sup[6:]), ('app j', f_ar[6:])):
        print('         %-10s %s' % (etq, ''.join('%12.4f' % x for x in v)))
    u_ar = C['desplazamientos'][str(ni)] + C['desplazamientos'][str(nj)]
    d_ud = max(abs(a - b) for a, b in zip(u_ar, u_sup))
    inf.check(d_ud <= R_U * (suma_l + 1),
              'desplazamientos de %d y %d: max |app - OpenSees| = %.2e m (cota %.1e); techo ux = %.2f mm'
              % (ni, nj, d_ud, R_U * (suma_l + 1), 1000 * u_sup[6]),
              'entre los dos extremos hay %.2f mm en %.2f m: con la combinacion MAYORADA y la gravedad '
              'adentro, NO es la deriva de NCh433' % (1000 * (u_sup[6] - u_sup[0]),
                                                      coords[nj][2] - coords[ni][2]))
    return nombre, f_sup


# ============================================================
# [4] DEMANDA, [5] PANEL, [6] JUNTA
# ============================================================
def demanda(inf, ar, nombre, f_sup):
    titulo('[4] DEMANDA Y CAPACIDAD: desde esas fuerzas, con la regla del repo')
    e = next(x for x in ar['elementos'] if x['id'] == EID)
    fam = ar['familias'][str(e['familia'])]
    curva = [{'P_kN': P, 'M_kNm': M} for P, M in zip(fam['P'], fam['Mn'])]
    d = dc.demanda(f_sup, tipo='columna')
    Mn = dc.capacidad_en(d['P_kN'], curva)
    u = d['M_kNm'] / Mn
    app = next(c for c in ar['casos'] if c['nombre'] == nombre)['demandas'][str(EID)]
    inf.check(abs(u - app['u']) <= 0.5e-6 + 1e-9 and d['extremo'] == app['extremo'],
              '%s: extremo %s, P = %.4f kN, M = sqrt(My^2 + Mz^2) = sqrt(%.2f^2 + %.2f^2) = %.4f kN m, '
              'Mn(P) = %.4f, u = %.6f = app %.6f' % (nombre, d['extremo'], d['P_kN'], abs(d['My']),
                                                    abs(d['Mz']), d['M_kNm'], Mn, u, app['u']),
              'familia %s: %s' % (e['familia'], fam['refuerzo']))
    filas = []
    for c in ar['casos']:
        dd = c['demandas'][str(EID)]
        filas.append((dd['u'], c['nombre'], dd))
    diseno = [x for x in filas if x[1] not in CASOS and x[1] != 'S3']
    u_g, n_g, dd = max(diseno, key=lambda x: x[0])
    inf.check(u_g < 1.0,
              'de las %d combinaciones mayoradas gobierna %s: P = %.1f kN, M = %.1f kN m, Mn = %.1f kN m, '
              'u = %.3f, PASA' % (len(diseno), n_g, dd['P'], dd['M'], dd['Mn'], u_g),
              'Mn nominal, sin phi: con phi = 0.65 (ACI 318-08, columna con estribos) u = %.3f; '
              'sigue pasando' % (u_g / 0.65))
    return app


def panel(ar, nombre, app):
    titulo('[5] PANEL: lo que escribe el telefono (web/ar.js, actualizarPanel)')
    e = next(x for x in ar['elementos'] if x['id'] == EID)
    C = next(c for c in ar['casos'] if c['nombre'] == nombre)
    s = C['esfuerzos'][str(EID)]
    print('  elementTag %d | %s %s   (%s)' % (e['id'], e['tipo'], e['seccion'], nombre))
    for m in COMPONENTES:
        print('    %-3s %10.1f %10.1f' % (m, s[m][0], s[m][-1]))
    for n in (e['n1'], e['n2']):
        u = C['desplazamientos'][str(n)]
        print('    u nodo %d [mm]: %.2f / %.2f / %.2f' % (n, 1000 * u[0], 1000 * u[1], 1000 * u[2]))
    print('    Demanda (extremo %s): P %.1f kN, M %.1f kN m; Mn(P) %.1f kN m; u = M/Mn %.3f %s'
          % (app['extremo'], app['P'], app['M'], app['Mn'], app['u'], 'PASA' if app['pasa'] else 'NO PASA'))
    print('    %s' % e['tag_opensees'])
    print('  (esfuerzos internos del anexo: N = -f[0], asi que la compresion sale negativa en el panel')
    print('   y positiva como P de la demanda: %.1f y %.1f son el mismo axial)' % (s['N'][0], app['P']))


def junta(inf):
    titulo('[6] JUNTA LIBRE: el LT2 solo y dentro del conjunto dan lo mismo bajo G')
    lt2 = next(x for x in contrato.cargar_resultados('lt2', 'G')['fuerzas_elementos']
               if int(x['id']) == EID - 2 * PASO_DE_TAG)
    conj = next(x for x in contrato.cargar_resultados('conjunto', 'G')['fuerzas_elementos']
                if int(x['id']) == EID)
    fa, fb = lt2['f'], conj['f']
    inf.check(fa == fb,
              'data/resultados/lt2_G.json elemento %d = conjunto_G.json elemento %d en las 12 '
              'componentes: N_i = %.4f kN' % (EID - 2 * PASO_DE_TAG, EID, fa[0]))
    ing = next((x for x in contrato.cargar_resultados('ingenieria', 'G')['fuerzas_elementos']
                if int(x['id']) == EID - 2 * PASO_DE_TAG), None)
    if ing:
        fi = ing['f']
        print('         el tag %d tambien existe en Ingenieria y es OTRA columna (N_i = %.4f kN): por eso '
              'el conjunto suma 100000 y 200000' % (EID - 2 * PASO_DE_TAG, fi[0]))


def correr():
    inf = Informe()
    print('=' * 78)
    print('  SEMANA 6: LA COLUMNA %d, DE LA LAMINA AL TELEFONO' % EID)
    print('=' * 78)
    conj = contrato.cargar_modelo('conjunto')
    ar = leer(AR_JSON)
    print('  app  %s (%s)' % (ruta_rel(AR_JSON), ar['info']['resultados_de']))
    plano_y_calce(inf, conj)
    nombre, f_sup = opensees(inf, conj, ar)
    app = demanda(inf, ar, nombre, f_sup)
    panel(ar, nombre, app)
    junta(inf)
    print()
    print('=' * 78)
    if inf.fallas:
        print('  FALLA: %d' % len(inf.fallas))
    else:
        print('  LA COLUMNA %d DE LA APP ES LA DE LA LAMINA, CON LOS NUMEROS DE OPENSEES' % EID)
        print('  (que calce con la columna FISICA en obra no se ha comprobado: falta el iPhone en sitio)')
    print('=' * 78)
    return not inf.fallas


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--salida', action='store_true', help='escribe evidencia/traza_200037.txt')
    a = ap.parse_args(argv)
    buf = io.StringIO()
    with contextlib.redirect_stdout(Tee(sys.stdout, buf) if a.salida else sys.stdout):
        ok = correr()
    if a.salida:
        ruta = os.path.join(AQUI, 'evidencia', 'traza_200037.txt')
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with io.open(ruta, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(buf.getvalue())
        print('  escrito %s' % ruta_rel(ruta))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
