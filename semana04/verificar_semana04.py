# -*- coding: utf-8 -*-
r"""
================================================================
 semana04/verificar_semana04.py  -  EL ANEXO DEL VISOR CONTRA OPENSEES
================================================================
 Arma el anexo de la Semana 4 EN MEMORIA, con la misma funcion que lo
 escribe (exportar_unity.construir_anexo), sin escribir ningun archivo,
 y lo compara contra OpenSees, contra el modelo, contra lo que dibuja
 Unity y contra la capacidad. Unity solo muestra: si un numero del
 panel esta mal, tiene que caerse aca y no en la defensa.

 Correr:
   python semana04/verificar_semana04.py                   ingenieria
   python semana04/verificar_semana04.py lt2
   python semana04/verificar_semana04.py conjunto --cs 0.20 --k 2

 Los flags son los de semana03/parametros.py. Siete bloques; cada uno
 imprime QUE compara, el peor valor, la cota y DE DONDE sale la cota:

   [1] reconstruccion   estacion(L) = f_j y estacion(0) = -f_i
   [2] superposicion    cada combinacion = sum(lambda * caso base)
   [3] corrida explicita 1.2G+1.0Q+1.4EX resuelta de verdad
   [4] E y A del panel  N = E A / L * alargamiento, en G
   [5] trazabilidad     id -> GameObject -> resultados -> familia P-M
   [6] signos           voladizos y viga simple resueltos aca, y una
                        seccion de fibras que dice que fibra tracciona
   [7] u = 9999         P fuera de la curva de su familia
   [8] muros            el momento del plano es el mayor bajo sismo, y
                        es el que usa la demanda

 ----------------------------------------------------------------
 LAS COTAS SALEN DE SU CAUSA
 ----------------------------------------------------------------
 El servidor redondea fuerzas a 4 decimales y desplazamientos a 8; el
 anexo vuelve a redondear lo que escribe. Cada comparacion suma esos
 medios ultimos decimales, escalados por lo que multiplica a cada
 valor, y un termino de coma flotante de 4 eps por el tamano de los
 terminos (el FACTOR_COMA_FLOTANTE del exportador). Los decimales se
 MIDEN sobre los datos con combinar.decimales_de: si alguien cambia un
 redondeo, esta verificacion lo dice en vez de pasar o fallar a ciegas.
 Nada se relaja para que pase (CLAUDE.md, regla 2).
================================================================
"""
from __future__ import annotations

import importlib.util
import io
import json
import math
import os
import re
import sys
import tempfile
import time

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_AQUI), 'comun'))
import rutas                                 # noqa: E402
rutas.entrar(__file__, os.path.join(rutas.RAIZ, 'semana03'))


def _cargar_exportador():
    r"""
    semana04/exportar_unity.py cargado POR RUTA. semana03/ tiene un
    modulo con el mismo nombre y el exportador de semana04 pone semana03
    al frente de sys.path: 'import exportar_unity' traeria el de la
    Semana 3 sin ningun error.
    """
    ruta = os.path.join(_AQUI, 'exportar_unity.py')
    spec = importlib.util.spec_from_file_location('exportar_semana04', ruta)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['exportar_semana04'] = mod
    spec.loader.exec_module(mod)
    return mod


eu = _cargar_exportador()

import capacidad                             # noqa: E402
import combinar                              # noqa: E402
import contrato                              # noqa: E402
import demanda_capacidad as dc               # noqa: E402
import lab_semana03 as lab                   # noqa: E402
import parametros                            # noqa: E402
import servidor_opensees as motor            # noqa: E402

CASOS = eu.CASOS_BASE
COMP = ('N', 'Vy', 'Vz', 'T', 'My', 'Mz')
CAMPOS_U = combinar.CAMPOS['desplazamientos']
COMBINACION_EXPLICITA = '1.2G+1.0Q+1.4EX'
FACTORES_EXPLICITA = {'G': 1.2, 'Q': 1.0, 'EX': 1.4, 'EY': 0.0}
FP = eu.FACTOR_COMA_FLOTANTE
VISOR_CS = os.path.join(rutas.UNITY_PROYECTO, 'Assets', 'Scripts', 'VisorEstructura.cs')
# La regla con que VisorEstructura.Redibujar nombra cada barra; se busca
# literal en el C#, fuera de comentarios.
LITERAL_NOMBRE = '"Elem_" + e.id + "_" + e.tipo'

# Medio ultimo decimal de lo que escribe el anexo: el redondeo que se
# agrega al comparar valores del anexo entre si o contra OpenSees.
R_ANEXO_F = 0.5 * 10.0 ** -eu.DECIMALES_FUERZA
R_ANEXO_X = 0.5 * 10.0 ** -eu.DECIMALES_ESTACION
R_ANEXO_U = 0.5 * 10.0 ** -eu.DECIMALES_DESPLAZAMIENTO


# ============================================================
# UTILIDADES
# ============================================================
class Informe(object):
    """Junta lo que no calza; cada comprobacion imprime una linea."""

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


def por_id(lista):
    return {int(x['id']): x for x in lista}


def medio_decimal(valores):
    """
    Medio ultimo decimal con que viene escrita una familia de valores,
    medido con combinar.decimales_de (la misma que mide el redondeo del
    servidor). 0 si son todos enteros o no hay valores.
    """
    vals = [float(v) for v in valores if not isinstance(v, bool)]
    d = combinar.decimales_de({'v': [{'f': vals}]}, 'v', None)
    return 0.5 * 10.0 ** -d if d else 0.0


def activos_de(caso):
    lam = dict(zip(CASOS, [float(v) for v in caso['factores']]))
    return lam, {c: l for c, l in lam.items() if l != 0.0}


class SilenciarStderr(object):
    r"""
    Desvia el stderr de C (descriptor 2) a un archivo temporal mientras
    corre OpenSees. capacidad.momento_curvatura empuja cada curva M-phi
    hasta que el analisis deja de converger y lo anota en su 'motivo';
    OpenSees ademas imprime un WARNING por cada una. Se cuentan y se
    informan en una linea; si hay una excepcion, se muestran enteros.
    """

    def __enter__(self):
        sys.stderr.flush()
        self.tmp = tempfile.TemporaryFile(mode='w+b')
        self.copia = os.dup(2)
        os.dup2(self.tmp.fileno(), 2)
        return self

    def __exit__(self, tipo, valor, traza):
        sys.stderr.flush()
        os.dup2(self.copia, 2)
        os.close(self.copia)
        self.tmp.seek(0)
        self.texto = self.tmp.read().decode('utf-8', 'replace')
        self.tmp.close()
        self.avisos = self.texto.count('failed to converge')
        if tipo is not None:
            sys.stderr.write(self.texto)
        return False


# ============================================================
# [1] RECONSTRUCCION
# ============================================================
def bloque_1(anexo, ctx, inf):
    titulo('[1] RECONSTRUCCION: estacion(L) = f_j y estacion(0) = -f_i, '
           'en cada caso y elemento')
    resultados = ctx['resultados']
    nodos = por_id(ctx['modelo']['nodos'])
    largos = {int(e['id']): lab.largo(e, nodos) for e in ctx['modelo']['elementos']}
    w_base = {c: eu.cargas_por_elemento(ctx['arm']['casos'][c]) for c in CASOS}
    f_base = {c: {int(x['id']): [float(v) for v in x['f']]
                  for x in resultados[c]['fuerzas_elementos']} for c in CASOS}

    r_srv = medio_decimal(v for c in CASOS for f in f_base[c].values() for v in f)
    r_est = medio_decimal(v for caso in anexo['casos'] for s in caso['esfuerzos']
                          for k in COMP + ('f',) for v in s[k])
    print('  Las estaciones del panel salen de f_i y w por equilibrio; en x = L')
    print('  tienen que dar f_j, que OpenSees calculo por su lado. La cota es la del')
    print('  exportador, eu.cota_de_cierre(L, sum|lambda|, magnitudes):')
    print('    N, Vy, Vz, T   5e-5 * 2 * sum|lambda|      (f_i y f_j del servidor)')
    print('    My, Mz         5e-5 * (2 + L) * sum|lambda| (ademas x * V_i)')
    print('    + 4 eps * tamano de los terminos            (coma flotante)')
    print('  mas 2 * %.0e porque aca se comparan dos valores YA ESCRITOS por el'
          % R_ANEXO_F)
    print('  anexo (la estacion y f_j), cada uno redondeado a %d decimales.'
          % eu.DECIMALES_FUERZA)
    inf.check(r_srv == eu.COTA_REDONDEO == anexo['info']['cota_redondeo_kN'],
              'redondeo del servidor medido en f = %.1e = eu.COTA_REDONDEO = '
              'info.cota_redondeo_kN (%g)' % (r_srv, anexo['info']['cota_redondeo_kN']))
    inf.check(r_est <= R_ANEXO_F,
              'el anexo escribe f y estaciones con a lo mas %d decimales (medido: '
              'medio decimal %.1e)' % (eu.DECIMALES_FUERZA, r_est))

    peores = {}
    malos, mal_x, n = [], [], 0
    n_carg = anexo['info']['n_estaciones_cargada']
    for caso in anexo['casos']:
        lam, activos = activos_de(caso)
        suma = sum(abs(l) for l in activos.values())
        # Cargada o no se decide con combinar.combinar_cargas, no con el
        # exportador: es la carga que OpenSees recibiria combinada.
        w_comb = {int(x['elemento']): x for x in
                  combinar.combinar_cargas(ctx['datos'], lam)['cargas_distribuidas']}
        for s in caso['esfuerzos']:
            eid = int(s['id'])
            L = largos[eid]
            mag = [0.0] * 6
            for c, l in activos.items():
                m_c = eu.magnitudes_de_cierre(f_base[c][eid],
                                              w_base[c].get(eid, (0.0, 0.0, 0.0)), L)
                mag = [a + abs(l) * b for a, b in zip(mag, m_c)]
            cotas = [c + 2.0 * R_ANEXO_F for c in eu.cota_de_cierre(L, suma, mag)]
            for k, comp in enumerate(COMP):
                for extremo, calc, ref in (('x = L', s[comp][-1], s['f'][6 + k]),
                                           ('x = 0', s[comp][0], -s['f'][k])):
                    err = abs(float(calc) - float(ref))
                    q = err / cotas[k]
                    n += 1
                    clave = (comp, extremo)
                    # Con error 0 en todos se muestra la cota mas chica.
                    ant = peores.get(clave, (-1.0, 0.0, math.inf))
                    if q > ant[0] or (q == ant[0] == 0.0 and cotas[k] < ant[2]):
                        peores[clave] = (q, err, cotas[k], caso['nombre'], eid)
                    if q > 1.0:
                        malos.append('%s elem %d %s en %s: %.2e > %.2e'
                                     % (caso['nombre'], eid, comp, extremo, err, cotas[k]))

            wv = w_comb.get(eid)
            cargada = wv is not None and any(float(wv[k]) != 0.0 for k in ('wx', 'wy', 'wz'))
            xs = [float(x) for x in s['x']]
            cuantas = n_carg if cargada else 2
            ok = (len(xs) == cuantas and all(len(s[k]) == cuantas for k in COMP)
                  and all(abs(x - L * i / (cuantas - 1)) <= R_ANEXO_X + FP * L
                          for i, x in enumerate(xs)))
            if not ok:
                mal_x.append('%s elem %d: %d estaciones (esperadas %d), L = %.4f, x = %s'
                             % (caso['nombre'], eid, len(xs), cuantas, L, xs[:3]))

    print()
    print('  %-4s %-6s %10s %10s %8s   %s' % ('', '', 'peor err', 'su cota',
                                             'err/cota', 'donde'))
    for comp in COMP:
        for extremo in ('x = L', 'x = 0'):
            q, err, cota, nombre, eid = peores[(comp, extremo)]
            print('  %-4s %-6s %10.2e %10.2e %8.3f   %s, elemento %d'
                  % (comp, extremo, err, cota, q, nombre, eid))
    print('  (en x = 0 la formula es -f_i sin ninguna operacion: el error es 0 exacto)')
    inf.check(not malos, '%d comparaciones (%d casos x %d elementos x 6 esfuerzos x '
              '2 extremos) dentro de su cota' % (n, len(anexo['casos']),
                                                 len(anexo['elementos'])), malos[:6])
    peor_exp = max(ctx['cierre'].items(), key=lambda kv: kv[1][0])
    inf.check(peor_exp[1][0] <= 1.0,
              'la autoverificacion del exportador (antes de redondear) cerro: peor '
              '%.3f en %s, elemento %d, %s' % (peor_exp[1][0], peor_exp[0],
                                              peor_exp[1][1], peor_exp[1][2]))
    inf.check(not mal_x, 'estaciones equiespaciadas de 0 a L: %d si la combinacion '
              'trae carga repartida, 2 si no (cota %.0e del redondeo de x)'
              % (n_carg, R_ANEXO_X), mal_x[:6])


# ============================================================
# [2] SUPERPOSICION
# ============================================================
def bloque_2(anexo, ctx, inf):
    titulo('[2] SUPERPOSICION: cada combinacion = sum(lambda * caso base), '
           'rehecha aca')
    p, resultados = ctx['p'], ctx['resultados']

    # La lista esperada sale de parametros.json, no del exportador.
    esperados, vistos = [], set()
    for c in CASOS:
        esperados.append((c, 'caso', [1.0 if k == c else 0.0 for k in CASOS]))
        vistos.add(c)
    for combo in list(p['combinaciones']) + [p['combinacion']]:
        if combo['nombre'] not in vistos:
            vistos.add(combo['nombre'])
            lam = parametros.factores(combo)
            esperados.append((combo['nombre'], 'combinacion', [lam[k] for k in CASOS]))
    hay = [(c['nombre'], c['tipo'], [float(v) for v in c['factores']])
           for c in anexo['casos']]
    inf.check(hay == esperados, 'los %d casos del anexo, en orden, con tipo y '
              'factores [lG lQ lEX lEY], son los de parametros.json' % len(esperados),
              [] if hay == esperados else ['anexo %s' % hay, 'esperado %s' % esperados])
    inf.check(anexo['info']['caso_por_defecto'] == p['combinacion']['nombre'],
              'caso_por_defecto = %s, la combinacion activa de los parametros'
              % anexo['info']['caso_por_defecto'])

    f_base = {c: por_id(resultados[c]['fuerzas_elementos']) for c in CASOS}
    u_base = {c: por_id(resultados[c]['desplazamientos']) for c in CASOS}
    r_mm = medio_decimal(c['max_desplazamiento_mm'] for c in anexo['casos'])
    print('  Referencia: combinar.combinar_resultados(resultados del servidor, lambda),')
    print('  otra implementacion de la suma que la del exportador (dc.combinar).')
    print('  El anexo escribe esa suma redondeada: la diferencia es a lo mas su medio')
    print('  ultimo decimal, f %.0e kN y u %.0e m, + 4 eps * sum|lambda| |valor|.'
          % (R_ANEXO_F, R_ANEXO_U))
    print('  max_desplazamiento_mm: norma de (ux, uy, uz) rehecha, cota %.0e mm '
          '(medida).' % r_mm)
    print()
    print('  %-18s %6s %10s %10s %10s %10s %9s  %s'
          % ('', 'sum|l|', 'peor f', 'cota f', 'peor u', 'cota u', 'umax mm', ''))
    no_cierran = []
    for caso in anexo['casos']:
        lam, activos = activos_de(caso)
        ref = combinar.combinar_resultados(resultados, lam)
        f_ref = {int(x['id']): x['f'] for x in ref['fuerzas_elementos']}
        u_ref = por_id(ref['desplazamientos'])
        esf, desp = por_id(caso['esfuerzos']), por_id(caso['desplazamientos'])
        ids_ok = set(esf) == set(f_ref) and set(desp) == set(u_ref)

        peor_f = (0.0, 0.0, R_ANEXO_F)
        for eid, s in (esf.items() if ids_ok else ()):
            for k, v in enumerate(s['f']):
                mag = sum(abs(l) * abs(float(f_base[c][eid]['f'][k]))
                          for c, l in activos.items())
                err, cota = abs(float(v) - f_ref[eid][k]), R_ANEXO_F + FP * mag
                if err / cota > peor_f[0]:
                    peor_f = (err / cota, err, cota)
        peor_u = (0.0, 0.0, 0.0)
        u_max = 0.0
        for nid, d in (desp.items() if ids_ok else ()):
            for k in CAMPOS_U:
                mag = sum(abs(l) * abs(float(u_base[c][nid][k])) for c, l in activos.items())
                err, cota = abs(float(d[k]) - u_ref[nid][k]), R_ANEXO_U + FP * mag
                if err / cota > peor_u[0]:
                    peor_u = (err / cota, err, cota)
            u_max = max(u_max, math.sqrt(sum(u_ref[nid][k] ** 2 for k in ('ux', 'uy', 'uz'))))
        u_max_mm = 1000.0 * u_max
        ok_mm = abs(caso['max_desplazamiento_mm'] - u_max_mm) <= r_mm + FP * u_max_mm
        suma = sum(abs(l) for l in activos.values())
        ok = ids_ok and peor_f[0] <= 1.0 and peor_u[0] <= 1.0 and ok_mm
        print('  %-18s %6.2f %10.2e %10.2e %10.2e %10.2e %9.4f  %s'
              % (caso['nombre'], suma, peor_f[1], peor_f[2], peor_u[1], peor_u[2],
                 caso['max_desplazamiento_mm'], 'ok' if ok else '<-- NO CALZA'))
        if not ok:
            no_cierran.append('%s: ids %s, f %.3f, u %.3f, umax %.4f contra %.4f'
                              % (caso['nombre'], ids_ok, peor_f[0], peor_u[0],
                                 caso['max_desplazamiento_mm'], u_max_mm))
    inf.check(not no_cierran, 'los %d casos: las 12 fuerzas de cada elemento, los 6 '
              'GDL de cada nodo y el desplazamiento maximo = la suma rehecha'
              % len(anexo['casos']), no_cierran)


# ============================================================
# [3] CONTRA UNA CORRIDA EXPLICITA
# ============================================================
def bloque_3(anexo, ctx, inf):
    titulo('[3] CORRIDA EXPLICITA: %s resuelta en OpenSees con la carga combinada'
           % COMBINACION_EXPLICITA)
    caso = next((c for c in anexo['casos'] if c['nombre'] == COMBINACION_EXPLICITA), None)
    if not inf.check(caso is not None, '%s esta en el anexo' % COMBINACION_EXPLICITA):
        return
    lam, activos = activos_de(caso)
    inf.check(lam == FACTORES_EXPLICITA, 'sus factores son %s' % caso['factores'])
    datos, arm = ctx['datos'], ctx['arm']
    inf.check(datos['casos_de_carga'] == list(arm['casos'].values()),
              'los casos que se combinan son los de la semana (lab.armar_casos: %s), '
              'no los de data/modelo' % ', '.join(c['nombre'] for c in datos['casos_de_carga']))

    carga = combinar.combinar_cargas(datos, lam, COMBINACION_EXPLICITA)
    t = time.time()
    explicito = combinar.resolver_explicito(datos, lam, COMBINACION_EXPLICITA)
    print('  combinar.resolver_explicito: %d cargas nodales y %d repartidas combinadas, '
          'resuelto en %.1f s' % (len(carga['cargas_nodales']),
                                  len(carga['cargas_distribuidas']), time.time() - t))
    inf.check(explicito.get('ok', False), 'OpenSees resolvio la corrida explicita')
    algebraico = combinar.combinar_resultados(ctx['resultados'], lam)
    piso = {'fuerzas_elementos': combinar.piso_de_redondeo(
                ctx['resultados'], lam, 'fuerzas_elementos', None),
            'desplazamientos': combinar.piso_de_redondeo(
                ctx['resultados'], lam, 'desplazamientos', CAMPOS_U)}
    print('  cota = combinar.piso_de_redondeo = 0.5 10^-d (sum|lambda| + 1) = %.2e kN '
          'y %.2e m' % (piso['fuerzas_elementos'], piso['desplazamientos']))
    print('  (d medido en los resultados; el +1 porque la explicita tambien viene')
    print('   redondeada), + 4 eps * tamano. Contra el ANEXO se suma su propio')
    print('   redondeo: %.0e kN y %.0e m.' % (R_ANEXO_F, R_ANEXO_U))

    def valores(res, clave):
        if clave == 'fuerzas_elementos':
            return {int(x['id']): [float(v) for v in x['f']] for x in res[clave]}
        return {int(x['id']): [float(x[k]) for k in CAMPOS_U] for x in res[clave]}

    anexo_res = {'fuerzas_elementos': [{'id': s['id'], 'f': s['f']} for s in caso['esfuerzos']],
                 'desplazamientos': caso['desplazamientos']}
    print()
    print('  %-17s %6s %11s %11s %11s %11s  %s'
          % ('', 'valores', 'superpos.', 'cota', 'anexo', 'cota', 'peor en'))
    for clave, r_anx in (('fuerzas_elementos', R_ANEXO_F), ('desplazamientos', R_ANEXO_U)):
        exp, alg, anx = (valores(explicito, clave), valores(algebraico, clave),
                         valores(anexo_res, clave))
        base = {c: valores(ctx['resultados'][c], clave) for c in activos}
        ids_ok = set(exp) == set(alg) == set(anx)
        n, peor_a, peor_x = 0, (0.0, 0.0, 0.0, None), (0.0, 0.0, 0.0, None)
        for i in (exp if ids_ok else ()):
            for k, e in enumerate(exp[i]):
                n += 1
                mag = abs(e) + sum(abs(l) * abs(base[c][i][k]) for c, l in activos.items())
                c_a = piso[clave] + FP * mag
                c_x = c_a + r_anx
                err_a, err_x = abs(alg[i][k] - e), abs(anx[i][k] - e)
                if err_a / c_a > peor_a[0]:
                    peor_a = (err_a / c_a, err_a, c_a, (i, k))
                if err_x / c_x > peor_x[0]:
                    peor_x = (err_x / c_x, err_x, c_x, (i, k))
        print('  %-17s %6d %11.3e %11.3e %11.3e %11.3e  %s / %s'
              % (clave, n, peor_a[1], peor_a[2], peor_x[1], peor_x[2], peor_a[3], peor_x[3]))
        inf.check(ids_ok and peor_a[0] <= 1.0 and peor_x[0] <= 1.0,
                  '%s: superposicion y anexo = corrida explicita (peores %.3f y %.3f '
                  'de su cota)' % (clave, peor_a[0], peor_x[0]))


# ============================================================
# [4] E Y A SON LOS DE OPENSEES
# ============================================================
def bloque_4(anexo, ctx, inf):
    titulo('[4] E y A DEL PANEL SON LOS DE OPENSEES: N(0) = E A / L * alargamiento, en G')
    modelo = ctx['modelo']
    nodos = por_id(modelo['nodos'])
    coords = {i: (float(n['x']), float(n['y']), float(n['z'])) for i, n in nodos.items()}
    G = next(c for c in anexo['casos'] if c['nombre'] == 'G')
    esf, desp = por_id(G['esfuerzos']), por_id(G['desplazamientos'])
    wx_G = {int(x['elemento']): float(x['wx']) for x in
            combinar.combinar_cargas(ctx['datos'], {'G': 1.0})['cargas_distribuidas']}
    elems = anexo['elementos']
    r_u = medio_decimal(d[k] for d in G['desplazamientos'] for k in CAMPOS_U)
    r_N = medio_decimal(s['N'][0] for s in G['esfuerzos'])
    r_E = medio_decimal(e['E_kPa'] for e in elems)
    r_L = medio_decimal(e['L'] for e in elems)
    raiz = 2.0 * math.sqrt(3.0)
    print('  N(0) es el N interno del panel en x = 0 (traccion +); alargamiento =')
    print('  (u_j - u_i) . x_local con x_local de contrato.ejes_locales y el vecxz del')
    print('  anexo; E_kPa, A y L del anexo. Cota propagada del redondeo:')
    print('    (E A / L) 2 sqrt(3) r_u   dos nodos, tres componentes, r_u = %.0e m' % r_u)
    print('    + r_N                    N_i del servidor, r_N = %.0e kN' % r_N)
    print('    + |N| (r_E/E + r_L/L)    E y L escritos por el anexo, r_E = %.0e kPa, '
          'r_L = %.0e m' % (r_E, r_L))
    print('  Columna "L geom": la cota del enunciado sola, con el L sin redondear.')

    por_tipo, malos, saltados = {}, [], {'brazo rigido': 0, 'carga axial wx': 0}
    for e in elems:
        eid = int(e['id'])
        if e['es_brazo_rigido']:
            saltados['brazo rigido'] += 1
            continue
        if wx_G.get(eid, 0.0) != 0.0:
            saltados['carga axial wx'] += 1
            continue
        n1, n2 = int(e['n1']), int(e['n2'])
        ejes, _L = contrato.ejes_locales(coords[n1], coords[n2], [float(v) for v in e['vecxz']])
        alarg = sum((float(desp[n2][k]) - float(desp[n1][k])) * ejes['wx'][m]
                    for m, k in enumerate(('ux', 'uy', 'uz')))
        E, A, L = float(e['E_kPa']), float(e['A']), float(e['L'])
        N_os = float(esf[eid]['N'][0])
        k_ax = E * A / L
        N_el = k_ax * alarg
        cota = k_ax * raiz * r_u + r_N + abs(N_el) * (r_E / E + r_L / L) + FP * (abs(N_os) + abs(N_el))
        L_g = lab.largo(e, nodos)
        k_g = E * A / L_g
        cota_g = k_g * raiz * r_u + r_N + abs(N_os) * r_E / E + FP * (abs(N_os) + abs(k_g * alarg))
        q, q_g = abs(N_os - N_el) / cota, abs(N_os - k_g * alarg) / cota_g
        t = por_tipo.setdefault(e['tipo'], {'n': 0, 'util': 0, 'q': -1.0, 'q_g': 0.0, 'd': None})
        t['n'] += 1
        # Un N menor que diez veces su cota no dice nada de E A: se cuenta aparte.
        t['util'] += abs(N_os) >= 10.0 * cota
        t['q_g'] = max(t['q_g'], q_g)
        if q > t['q']:
            t['q'], t['d'] = q, (eid, N_os, N_el, abs(N_os - N_el), cota)
        if q > 1.0 or q_g > 1.0:
            malos.append('elem %d (%s): N %.4f contra EA/L*d %.4f, err %.2e, cota %.2e, '
                         'con L geom %.3f' % (eid, e['tipo'], N_os, N_el, abs(N_os - N_el),
                                              cota, q_g))
    print()
    print('  %-12s %4s %6s %8s %8s   %s' % ('tipo', 'n', '|N|>10c', 'err/cota', 'L geom',
                                           'peor: elemento, N(0), EA/L*d, err, cota'))
    for tipo, t in sorted(por_tipo.items()):
        print('  %-12s %4d %6d %8.3f %8.3f   %d, %.3f, %.3f, %.2e, %.2e'
              % ((tipo, t['n'], t['util'], t['q'], t['q_g']) + t['d']))
    mudos = sorted(tipo for tipo, t in por_tipo.items() if t['util'] == 0)
    if mudos:
        print('  %s: ningun |N| llega a 10 veces su cota (en el diafragma rigido no se'
              % ', '.join(mudos))
        print('  alargan), asi que calzan pero no dicen nada de su E A.')
    print('  fuera: %d brazos rigidos (rigidez x100, no es la del panel), %d con carga '
          'axial repartida' % (saltados['brazo rigido'], saltados['carga axial wx']))
    inf.check(not malos, '%d elementos: el N de OpenSees es E A / L del anexo por el '
              'alargamiento' % sum(t['n'] for t in por_tipo.values()), malos[:6])


# ============================================================
# [5] TRAZABILIDAD
# ============================================================
def linea_del_nombre_en_visor():
    """(numero, texto) de la linea de VisorEstructura.cs que nombra la barra
    con LITERAL_NOMBRE, fuera de comentarios; (None, None) si no esta."""
    if not os.path.isfile(VISOR_CS):
        return None, None
    with io.open(VISOR_CS, encoding='utf-8') as fh:
        src = fh.read()
    src = re.sub(r'/\*.*?\*/', lambda m: '\n' * m.group(0).count('\n'), src, flags=re.S)
    for i, linea in enumerate(src.splitlines(), 1):
        codigo = linea.split('//', 1)[0]
        if LITERAL_NOMBRE in codigo and '.name' in codigo:
            return i, codigo.strip()
    return None, None


def bloque_5(edificio, anexo, ctx, inf):
    titulo('[5] TRAZABILIDAD: elementTag <-> objeto Unity <-> resultados <-> '
           'seccion y capacidad')
    modelo = ctx['modelo']
    elems, m_elems = por_id(anexo['elementos']), por_id(modelo['elementos'])
    familias = anexo['familias']

    # --- lo que dibuja Unity ---
    ruta_u = rutas.unity(edificio)
    u_elems, u_nodos = {}, set()
    if inf.check(os.path.isfile(ruta_u), 'existe %s' % os.path.relpath(ruta_u, rutas.RAIZ)):
        with io.open(ruta_u, encoding='utf-8') as fh:
            vista = json.load(fh)
        u_elems, u_nodos = por_id(vista['elementos']), {int(n['id']) for n in vista['nodos']}
    faltan = sorted(set(elems) - set(u_elems))
    distintos = sorted(eid for eid, e in elems.items() if eid in u_elems and any(
        e[c] != u_elems[eid][c] for c in ('n1', 'n2', 'seccion', 'tipo')))
    inf.check(not faltan and not distintos and set(elems) == set(m_elems),
              'los %d ElementoS4 = los del modelo, y cada uno existe en %s con los '
              'mismos n1, n2, seccion y tipo' % (len(elems), os.path.basename(ruta_u)),
              ['faltan en Unity: %s' % faltan[:8] if faltan else '',
               'distintos: %s' % distintos[:8] if distintos else ''])
    linea, texto = linea_del_nombre_en_visor()
    inf.check(linea is not None, 'VisorEstructura.cs linea %s: %s' % (linea, texto)
              if linea else 'VisorEstructura.cs nombra la barra con %s' % LITERAL_NOMBRE)
    mal_nombre = sorted(eid for eid, e in elems.items()
                        if e['objeto_unity'] != 'Elem_%d_%s' % (eid, e['tipo'])
                        or not e['tag_opensees'].startswith('element elasticBeamColumn %d %d %d '
                                                            % (eid, e['n1'], e['n2'])))
    ej = elems[anexo['info']['columna_demo']] if anexo['info']['columna_demo'] in elems \
        else anexo['elementos'][0]
    inf.check(not mal_nombre, 'objeto_unity == "Elem_<id>_<tipo>" y tag_opensees empieza con '
              'el mismo id y nodos, en los %d' % len(elems),
              ['ej. %s <-> %s' % (ej['objeto_unity'], ej['tag_opensees'])]
              + (['distintos: %s' % mal_nombre[:8]] if mal_nombre else []))

    # --- resultados: cada id apunta a algo que existe ---
    con_fierro = {eid for eid, e in elems.items() if e['familia'] >= 0}
    ids_nodos = {int(n['id']) for n in modelo['nodos']}
    malos = []
    for c in anexo['casos']:
        ids_e = [int(s['id']) for s in c['esfuerzos']]
        ids_d = [int(d['id']) for d in c['demandas']]
        ids_u = {int(d['id']) for d in c['desplazamientos']}
        if len(ids_e) != len(set(ids_e)) or set(ids_e) != set(elems):
            malos.append('%s: esfuerzos no son los %d elementos' % (c['nombre'], len(elems)))
        if len(ids_d) != len(set(ids_d)) or set(ids_d) != con_fierro or any(
                d['familia'] != elems[int(d['id'])]['familia'] for d in c['demandas']):
            malos.append('%s: demandas no son los %d con familia' % (c['nombre'], len(con_fierro)))
        if ids_u != ids_nodos or (u_nodos and not ids_u <= u_nodos):
            malos.append('%s: desplazamientos no son los nodos del modelo y de Unity' % c['nombre'])
    inf.check(not malos, 'en los %d casos: esfuerzos de los %d elementos, demandas de los '
              '%d con familia (y la misma familia), desplazamientos de los %d nodos'
              % (len(anexo['casos']), len(elems), len(con_fierro), len(ids_nodos)), malos[:6])

    # --- familias = firmas de demanda_capacidad ---
    firma_de = {eid: dc.firma_de_seccion(me, capacidad.desde_elemento(modelo, eid))
                for eid, me in m_elems.items() if me.get('enfierradura')}
    fams_de_firma, firmas_de_fam, malas = {}, {}, []
    for eid, firma in firma_de.items():
        fams_de_firma.setdefault(firma, set()).add(elems[eid]['familia'])
        firmas_de_fam.setdefault(elems[eid]['familia'], set()).add(firma)
    if set(firma_de) != con_fierro:
        malas.append('con enfierradura %d, con familia %d' % (len(firma_de), len(con_fierro)))
    malas += ['firma %s en familias %s' % (f[0], sorted(v)) for f, v in fams_de_firma.items()
              if len(v) != 1]
    for i, fam in enumerate(familias):
        if fam['indice'] != i or sorted(fam['elementos']) != sorted(
                eid for eid in con_fierro if elems[eid]['familia'] == i):
            malas.append('familia %d: indice o lista de elementos distinta' % i)
        if len(firmas_de_fam.get(i, ())) != 1:
            malas.append('familia %d junta %d firmas' % (i, len(firmas_de_fam.get(i, ()))))
    inf.check(not malas, '%d elementos con fierro en %d familias = %d firmas de '
              'demanda_capacidad.firma_de_seccion, una a una'
              % (len(firma_de), len(familias), len(fams_de_firma)), malas[:6])

    for etiqueta, tipo in (('columna_demo', 'columna'), ('muro_demo', 'muro')):
        demo_pm(edificio, etiqueta, tipo, anexo, ctx, inf)


def demo_pm(edificio, etiqueta, tipo, anexo, ctx, inf):
    r"""
    La columna o el muro de demostracion: su curva en el anexo es la de
    capacidad.interaccion sobre SU seccion (no solo la del primer elemento
    de la familia), y su demanda es la de demanda_capacidad.revisar.
    """
    info, elems = anexo['info'], por_id(anexo['elementos'])
    eid = int(info[etiqueta])
    if not inf.check(eid in elems and elems[eid]['tipo'] == tipo and elems[eid]['familia'] >= 0,
                     '%s = %d es de tipo %s y tiene familia P-M' % (etiqueta, eid, tipo)):
        return
    e = elems[eid]
    fam = anexo['familias'][e['familia']]
    with SilenciarStderr():
        sec = capacidad.desde_elemento(ctx['modelo'], eid)
        curva = capacidad.interaccion(sec)
        res = dc.revisar(edificio, eid, modelo=ctx['modelo'], resultados=ctx['resultados'])
    print()
    print('  %s -> %s -> %s' % (etiqueta, e['objeto_unity'], e['tag_opensees']))
    print('    seccion %s, familia %d (%d elementos, la curva se calculo con el %d): %s'
          % (e['seccion'], e['familia'], len(fam['elementos']), fam['elementos'][0], fam['clave']))
    peor = [0.0, 0.0, 0.0]
    ok = len(curva) == len(fam['P'])
    for i, pt in enumerate(curva if ok else ()):
        pares = ((pt['P_kN'], fam['P'][i]), (pt['M_kNm'], fam['Mn'][i]),
                 (pt.get('M_max_kNm', 0.0), fam['Mmax'][i]))
        for k, (a, b) in enumerate(pares):
            err = abs(float(a) - float(b))
            peor[k] = max(peor[k], err)
            ok = ok and err <= R_ANEXO_F + FP * abs(float(a)) and pt.get('de', '') == fam['de'][i]
    inf.check(ok, '%s %d: familia del anexo (%d puntos) == capacidad.interaccion(capacidad.'
              'desde_elemento(modelo, %d)) (peor dif P %.1e, Mn %.1e, Mmax %.1e; cota %.0e, '
              'el redondeo del anexo)' % (etiqueta, eid, len(fam['P']), eid, peor[0], peor[1],
                                          peor[2], R_ANEXO_F))

    casos = {c['nombre']: c for c in anexo['casos']}
    r_u = medio_decimal(d['u'] for c in anexo['casos'] for d in c['demandas'])
    print('    %-6s %10s %10s %10s %9s %-13s | revisar(): %s'
          % ('caso', 'P [kN]', 'M [kNm]', 'Mn [kNm]', 'u', 'extremo', 'P, M, Mn, u'))
    bien = True
    for nombre in list(CASOS) + [info['caso_por_defecto']]:
        x = next(y for y in casos[nombre]['demandas'] if int(y['id']) == eid)
        d = res['puntos'].get(nombre)
        if d is None:          # el caso activo: revisar no lo trae, se muestra
            print('    %-6s %10.1f %10.1f %10.1f %9.3f %-13s | caso activo del visor'
                  % (nombre, x['P'], x['M'], x['Mn'], x['u'], x['extremo']))
            continue
        u_ref = d['utilizacion'] if math.isfinite(d['utilizacion']) else 9999.0
        pares = ((x['P'], d['P_kN']), (x['M'], d['M_kNm']),
                 (x['M_fuera_plano'], d['M_fuera_de_plano_kNm'] or 0.0),
                 (x['Mn'], d['M_capacidad_kNm']))
        ok = (all(abs(float(a) - float(b)) <= R_ANEXO_F + FP * abs(float(b)) for a, b in pares)
              and abs(float(x['u']) - u_ref) <= r_u + FP * u_ref
              and x['extremo'] == d['extremo'] and x['pasa'] == d['pasa'])
        bien = bien and ok
        print('    %-6s %10.1f %10.1f %10.1f %9.3f %-13s | %.4f, %.4f, %.4f, %.6f %s'
              % (nombre, x['P'], x['M'], x['Mn'], x['u'], x['extremo'], d['P_kN'], d['M_kNm'],
                 d['M_capacidad_kNm'], u_ref, 'calza' if ok else '<-- NO CALZA'))
    inf.check(bien, '%s %d: P, M, M fuera de plano, Mn, u, extremo y pasa de G, Q, EX, EY '
              '== demanda_capacidad.revisar (cota %.0e en fuerzas, %.0e en u)'
              % (etiqueta, eid, R_ANEXO_F, r_u))


# ============================================================
# [6] SIGNOS, CON MODELOS CHICOS
# ============================================================
L_S, Q_S, B_S, H_S, E_S = 6.0, 10.0, 0.30, 0.50, 2.5e7


def barra_en_servidor(restr_i, restr_j, wy, wz):
    """Una barra de L_S m a lo largo de X global, resuelta con el servidor."""
    data = {
        'material': {'fpc_MPa': 25.0, 'poisson': 0.2},
        'secciones': [{'nombre': 'r', 'A': B_S * H_S, 'Iy': H_S * B_S ** 3 / 12.0,
                       'Iz': B_S * H_S ** 3 / 12.0, 'J': 0.0026}],
        'nodos': [{'id': 1, 'x': 0.0, 'y': 0.0, 'z': 0.0, 'restricciones': restr_i},
                  {'id': 2, 'x': L_S, 'y': 0.0, 'z': 0.0, 'restricciones': restr_j}],
        'elementos': [{'id': 1, 'n1': 1, 'n2': 2, 'seccion': 'r', 'tipo': 'viga'}],
        'cargas_distribuidas': [{'elemento': 1, 'wx': 0.0, 'wy': wy, 'wz': wz}],
    }
    salida = motor.construir_y_resolver(data)
    return ([float(v) for v in salida['fuerzas_elementos'][0]['f']],
            por_id(salida['desplazamientos'])[2], salida['ok'])


def voladizo_de_fibras(wy, wz):
    r"""
    El mismo voladizo en OpenSees puro, SIN el servidor ni las formulas:
    6 dispBeamColumn de 1 m con una seccion de fibras elastica (b en y
    local, h en z local), el mismo vecxz (0,0,1) y la misma -beamUniform.
    Devuelve la tension de las fibras extremas y la fuerza de la seccion
    en el primer punto de Gauss del elemento del empotramiento.
    """
    import openseespy.opensees as ops
    n = int(L_S)
    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 6)
    for i in range(n + 1):
        ops.node(i + 1, L_S * i / n, 0.0, 0.0)
    ops.fix(1, 1, 1, 1, 1, 1, 1)
    ops.uniaxialMaterial('Elastic', 1, E_S)
    ops.section('Fiber', 1, '-GJ', 1.0e6)
    ops.patch('rect', 1, 10, 10, -B_S / 2.0, -H_S / 2.0, B_S / 2.0, H_S / 2.0)
    ops.geomTransf('Linear', 1, 0.0, 0.0, 1.0)
    ops.beamIntegration('Legendre', 1, 1, 3)
    for i in range(n):
        ops.element('dispBeamColumn', i + 1, i + 1, i + 2, 1, 1)
    ops.timeSeries('Linear', 1)
    ops.pattern('Plain', 1, 1)
    for i in range(n):
        ops.eleLoad('-ele', i + 1, '-type', '-beamUniform', wy, wz, 0.0)
    ops.system('BandGeneral')
    ops.numberer('RCM')
    ops.constraints('Plain')
    ops.integrator('LoadControl', 1.0)
    ops.algorithm('Linear')
    ops.analysis('Static')
    if ops.analyze(1) != 0:
        raise RuntimeError('el voladizo de fibras no convergio')
    tension = {}
    for nombre, (y, z) in (('+z', (0.0, H_S / 2.0)), ('-z', (0.0, -H_S / 2.0)),
                           ('+y', (B_S / 2.0, 0.0)), ('-y', (-B_S / 2.0, 0.0))):
        r = ops.eleResponse(1, 'section', 1, 'fiber', y, z, 'stressStrain')
        if not r:
            raise RuntimeError('eleResponse(section, fiber, %g, %g) vino vacio' % (y, z))
        tension[nombre] = float(r[0])
    fuerza = ops.eleResponse(1, 'section', 1, 'force')      # [P, Mz, My, T]
    x_ip = float(ops.sectionLocation(1)[0])                  # elemento de 1 m
    return tension, {'Mz': float(fuerza[1]), 'My': float(fuerza[2])}, x_ip


def bloque_6(inf):
    titulo('[6] CONVENCION DE SIGNOS: modelos chicos resueltos con '
           'servidor_opensees.construir_y_resolver')
    ejes, _L = contrato.ejes_locales((0.0, 0.0, 0.0), (L_S, 0.0, 0.0), (0.0, 0.0, 1.0))
    print('  barra de %.0f m a lo largo de X, q = %.0f kN/m. Ejes locales (contrato.ejes_locales'
          % (L_S, Q_S))
    print('  con vecxz (0,0,1)): x = %s, y = %s, z = %s. Asi wz < 0 va hacia -Z (abajo)'
          % (ejes['wx'], ejes['wy'], ejes['wz']))
    print('  y wy < 0 hacia -Y. Cotas: eu.cota_de_cierre y el redondeo del servidor, %.0e.'
          % eu.COTA_REDONDEO)
    fijo, libre = [1] * 6, [0] * 6
    xs = eu.estaciones(L_S, True)
    r = eu.COTA_REDONDEO
    modelos = (('voladizo wz = -q', fijo, libre, 0.0, -Q_S),
               ('voladizo wy = -q', fijo, libre, -Q_S, 0.0),
               ('simple wz = -q', [1, 1, 1, 1, 0, 0], [0, 1, 1, 0, 0, 0], 0.0, -Q_S))
    internos = {}
    for nombre, ri, rj, wy, wz in modelos:
        f, u2, ok = barra_en_servidor(ri, rj, wy, wz)
        w = (0.0, wy, wz)
        esf = eu.esfuerzos_internos(f, w, xs)
        internos[nombre] = (f, w)
        q, comp = eu.cociente_de_cierre(f, w, L_S, 1.0, eu.magnitudes_de_cierre(f, w, L_S))
        print()
        print('  %s: f = [%s]' % (nombre, ', '.join('%.4f' % v for v in f)))
        inf.check(ok and q <= 1.0, '%s: esfuerzos_internos(x = L) reproduce f_j (peor %.3f de la '
                  'cota, en %s)' % (nombre, q, comp))
        if nombre == 'voladizo wz = -q':
            M0, ref = esf['My'][0], Q_S * L_S ** 2 / 2.0
            inf.check(M0 > 0 and abs(M0 - ref) <= r + FP * ref and u2['uz'] < 0,
                      'My(0) = %+.4f > 0 en el empotramiento = q L^2/2 = %.4f (cota %.0e, My_i '
                      'redondeado); la punta baja, uz = %.3e m' % (M0, ref, r, u2['uz']),
                      'fibra superior traccionada: el visor dibuja +My hacia +z local (arriba)')
        elif nombre == 'voladizo wy = -q':
            M0, ref = esf['Mz'][0], -Q_S * L_S ** 2 / 2.0
            inf.check(M0 < 0 and abs(M0 - ref) <= r + FP * abs(ref) and u2['uy'] < 0,
                      'Mz(0) = %+.4f < 0 en el empotramiento = -q L^2/2 = %.4f (cota %.0e); la '
                      'punta va a -Y, uy = %.3e m' % (M0, ref, r, u2['uy']),
                      'fibra +y traccionada: el visor dibuja -Mz hacia +y local')
        else:
            i_c = xs.index(L_S / 2.0)
            Mc, ref = esf['My'][i_c], -Q_S * L_S ** 2 / 8.0
            cota = r * (1.0 + L_S / 2.0) + FP * (abs(ref) + abs(f[4]) + L_S / 2.0 * abs(f[2]))
            inf.check(abs(Mc - ref) <= cota and all(esf['My'][i] < 0 for i in range(1, len(xs) - 1)),
                      'My(L/2) = %+.4f = -q L^2/8 = %.4f (cota %.1e = 5e-5 (1 + L/2): My_i y '
                      'Vz_i redondeados); My < 0 en todo el tramo' % (Mc, ref, cota),
                      'fibra inferior traccionada: +My * z_local lo dibuja hacia abajo')
    bloque_6_fibras(internos, inf)


def bloque_6_fibras(internos, inf):
    print()
    print('  Prueba INDEPENDIENTE de las formulas: el mismo voladizo en OpenSees puro con')
    print('  dispBeamColumn y una seccion de fibras elastica; se lee la tension de las')
    print('  fibras extremas en el primer punto de Gauss junto al empotramiento.')
    for nombre, clave, mas, menos in (('voladizo wz = -q', 'My', '+z', '-z'),
                                      ('voladizo wy = -q', 'Mz', '+y', '-y')):
        f, w = internos[nombre]
        try:
            tension, seccion, x_ip = voladizo_de_fibras(w[1], w[2])
        except Exception as ex:           # noqa: BLE001 - se informa y cuenta como falla
            inf.check(False, '%s: no se pudo leer la fibra (%s): sin esa lectura no hay prueba '
                      'independiente de que lado tracciona' % (nombre, ex))
            continue
        formula = eu.esfuerzos_internos(f, w, [x_ip])[clave][0]
        exacto = (1.0 if clave == 'My' else -1.0) * Q_S * (L_S - x_ip) ** 2 / 2.0
        inf.check(tension[mas] > 0 > tension[menos],
                  '%s: fibra %s en traccion (%+.1f kPa) y %s en compresion (%+.1f kPa), en '
                  'x = %.4f m' % (nombre, mas, tension[mas], menos, tension[menos], x_ip))
        inf.check(seccion[clave] * formula > 0,
                  '%s: %s de la seccion de fibras = %+.2f y %s(x) de la formula = %+.2f: mismo '
                  'signo (exacto %+.2f)' % (nombre, clave, seccion[clave], clave, formula, exacto),
                  'OpenSees: %s > 0 tracciona +z, %s < 0 tracciona +y; el anexo usa esa misma '
                  'convencion' % ('My', 'Mz'))


# ============================================================
# [7] u = 9999
# ============================================================
def bloque_7(anexo, inf):
    titulo('[7] DEMANDAS CON u = 9999: su P cae fuera de la curva de su familia')
    familias, elems = anexo['familias'], por_id(anexo['elementos'])
    rango = {i: (min(f['P']), max(f['P'])) for i, f in enumerate(familias)}
    # P y los extremos de la curva vienen escritos a 4 decimales: un P a
    # menos de 2 medios decimales del borde no se puede ubicar de que lado.
    r = 2.0 * R_ANEXO_F
    print('  dc.capacidad_en devuelve Mn = 0 si P <= P min o P >= P max de la curva, y el')
    print('  exportador pone u = 9999 cuando Mn <= 1e-9. Se exige que cada u = 9999 tenga')
    print('  Mn = 0 y P fuera de [P min, P max] de SU familia (a %.0e, dos redondeos), y' % r)
    print('  al reves, que ningun P claramente fuera tenga un u finito.')
    por_elem, malos, inversos, n = {}, [], [], 0
    for c in anexo['casos']:
        for d in c['demandas']:
            n += 1
            lo, hi = rango[d['familia']]
            P = float(d['P'])
            if float(d['u']) >= 9999.0:
                if not (P <= lo + r or P >= hi - r) or float(d['Mn']) != 0.0:
                    # Que puntos de la curva rodean a P: si Mn = 0 adentro, la
                    # curva tiene un cero interior y ahi esta la causa.
                    fam = familias[d['familia']]
                    pts = sorted(zip(fam['P'], fam['Mn'], fam['de']))
                    par = next(((a, b) for a, b in zip(pts, pts[1:]) if a[0] <= P <= b[0]),
                               (pts[0], pts[-1]))
                    malos.append('%s elem %d: P %.1f dentro de [%.1f, %.1f] con Mn %.1f; la '
                                 'curva de la familia %d entre P %.1f (Mn %.1f, %s) y P %.1f '
                                 '(Mn %.1f, %s)' % (c['nombre'], d['id'], P, lo, hi, d['Mn'],
                                                    d['familia'], par[0][0], par[0][1], par[0][2],
                                                    par[1][0], par[1][1], par[1][2]))
                por_elem.setdefault(int(d['id']), []).append((c['nombre'], P))
            elif P < lo - r or P > hi + r:
                inversos.append('%s elem %d: P %.1f fuera de [%.1f, %.1f] con u %.3f'
                                % (c['nombre'], d['id'], P, lo, hi, d['u']))
    print()
    for eid, lista in sorted(por_elem.items()):
        e = elems[eid]
        lo, hi = rango[e['familia']]
        nombre, P = min(lista, key=lambda t: t[1]) if lista[0][1] < lo + r else \
            max(lista, key=lambda t: t[1])
        lado = ('traccion mas alla de la traccion pura' if P < lo + r
                else 'compresion mas alla de la compresion pura')
        print('  elemento %d (%s %s, familia %d): P de la curva en [%.1f, %.1f]; u = 9999 en %s'
              % (eid, e['tipo'], e['seccion'], e['familia'], lo, hi,
                 ', '.join(x for x, _p in lista)))
        print('      peor %s: P = %.1f kN, %s (%.1f kN afuera)'
              % (nombre, P, lado, (lo - P) if P < lo + r else (P - hi)))
    inf.check(not malos, '%d de %d demandas con u = 9999, en %d elementos: todas con Mn = 0 y '
              'P fuera de la curva de su familia' % (sum(len(v) for v in por_elem.values()), n,
                                                    len(por_elem)), malos[:6])
    inf.check(not inversos, 'ninguna demanda con P fuera de la curva tiene u finito', inversos[:6])


# ============================================================
# [8] EL MOMENTO DEL PLANO DE UN MURO
# ============================================================
def bloque_8(anexo, inf):
    titulo('[8] MUROS: el momento que se compara con la curva es el de su plano')
    print('  demanda_capacidad.momento_en_el_plano(Iy, Iz) lo elige por inercias. Aca se')
    print('  comprueba con lo que respondio OpenSees, sin mirar las inercias: bajo EX y EY,')
    print('  el momento declarado del plano tiene que ser el mayor de los dos en cada muro.')
    print('  Y la demanda del anexo tiene que haber usado ese: M = max(|M_i|, |M_j|).')
    casos = {c['nombre']: por_id(c['esfuerzos']) for c in anexo['casos']}
    muros = [e for e in anexo['elementos'] if e['tipo'] == 'muro']
    filas, sin_plano, menores = [], [], []
    for e in muros:
        plano = e.get('momento_en_el_plano')
        if plano not in ('My', 'Mz'):
            sin_plano.append('muro %d: momento_en_el_plano = %r' % (e['id'], plano))
            continue
        fuera = 'Mz' if plano == 'My' else 'My'
        m_p = max(abs(v) for c in ('EX', 'EY') for v in casos[c][e['id']][plano])
        m_f = max(abs(v) for c in ('EX', 'EY') for v in casos[c][e['id']][fuera])
        filas.append((m_p / m_f if m_f > 0 else float('inf'), e['id'], plano, m_p, m_f))
        if m_p <= m_f:
            menores.append('muro %d: max |%s| %.1f <= max |%s| %.1f bajo EX y EY'
                           % (e['id'], plano, m_p, fuera, m_f))
    print()
    print('  %d muros: el del plano es My en %d y Mz en %d'
          % (len(muros), sum(1 for f in filas if f[2] == 'My'),
             sum(1 for f in filas if f[2] == 'Mz')))
    for q, eid, plano, m_p, m_f in sorted(filas)[:3]:
        print('    de los mas justos: muro %d, max |%s| = %.1f contra %.1f fuera de plano '
              '(%.1f veces)' % (eid, plano, m_p, m_f, q))
    inf.check(not sin_plano, 'los %d muros traen momento_en_el_plano = My o Mz' % len(muros),
              sin_plano[:6])
    inf.check(filas and not menores, 'en los %d muros el momento del plano es el mayor bajo '
              'EX y EY' % len(filas), menores[:6])

    # La demanda: el M del anexo es el del plano en el extremo que gana.
    elems = por_id(anexo['elementos'])
    r = 2.0 * R_ANEXO_F
    malas, n = [], 0
    for c in anexo['casos']:
        esf = casos[c['nombre']]
        for d in c['demandas']:
            e = elems[int(d['id'])]
            if e['tipo'] != 'muro' or e.get('momento_en_el_plano') not in ('My', 'Mz'):
                continue
            n += 1
            k = 4 if e['momento_en_el_plano'] == 'My' else 5
            f = esf[int(d['id'])]['f']
            m_plano = max(abs(f[k]), abs(f[6 + k]))
            m_otro = abs(f[9 - k]) if abs(f[k]) >= abs(f[6 + k]) else abs(f[15 - k])
            if abs(float(d['M']) - m_plano) > r + FP * m_plano or \
                    abs(float(d['M_fuera_plano']) - m_otro) > r + FP * m_otro:
                malas.append('%s muro %d: M %.4f y fuera %.4f; |%s| da %.4f y el otro %.4f'
                             % (c['nombre'], d['id'], d['M'], d['M_fuera_plano'],
                                e['momento_en_el_plano'], m_plano, m_otro))
    inf.check(n > 0 and not malas, '%d demandas de muro: M = max(|M_i|, |M_j|) del momento de su '
              'plano, y M fuera de plano = el otro en ese extremo (cota %.0e, dos redondeos)'
              % (n, r), malas[:6])


# ============================================================
def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    edificio = 'ingenieria'
    if argv and not argv[0].startswith('-'):
        edificio = argv.pop(0)

    print('=' * 78)
    print('  VERIFICACION DEL ANEXO DE SEMANA 4   %s' % edificio.upper())
    print('=' * 78)
    t0 = time.time()
    with SilenciarStderr() as s:
        anexo, ctx = eu.construir_anexo(edificio, argv)
    print('  exportar_unity.construir_anexo() EN MEMORIA (no escribe archivos): '
          '%.1f s' % (time.time() - t0))
    print('  %d casos (%s), %d elementos, %d familias P-M'
          % (len(anexo['casos']), ', '.join(c['nombre'] for c in anexo['casos']),
             len(anexo['elementos']), len(anexo['familias'])))
    print('  (%d avisos de no convergencia de OpenSees: son el final de cada curva'
          % s.avisos)
    print('   M-phi de capacidad.momento_curvatura, que corta ahi y lo anota)')
    print(parametros.describir(ctx['p']))

    inf = Informe()
    bloques = (
        ('1', lambda: bloque_1(anexo, ctx, inf)),
        ('2', lambda: bloque_2(anexo, ctx, inf)),
        ('3', lambda: bloque_3(anexo, ctx, inf)),
        ('4', lambda: bloque_4(anexo, ctx, inf)),
        ('5', lambda: bloque_5(edificio, anexo, ctx, inf)),
        ('6', lambda: bloque_6(inf)),
        ('7', lambda: bloque_7(anexo, inf)),
        ('8', lambda: bloque_8(anexo, inf)),
    )
    for nombre, bloque in bloques:
        t = time.time()
        bloque()
        print('  (bloque [%s]: %.1f s)' % (nombre, time.time() - t))

    print()
    print('=' * 78)
    if inf.fallas:
        print('  NO CALZA (%d):' % len(inf.fallas))
        for f in inf.fallas:
            print('    - %s' % f)
        print('=' * 78)
        return 1
    print('  TODO CALZA')
    print('=' * 78)
    return 0


if __name__ == '__main__':
    sys.exit(main())
