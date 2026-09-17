# -*- coding: utf-8 -*-
r"""
================================================================
 semana05/comparar_anexos.py  -  LA MODIFICACION M2, POR DATO
================================================================
 M2 cambia un DATO que dicta el profesor (el coeficiente sismico) y
 sigue el cambio hasta lo que muestra el panel de Unity. Arma en
 memoria dos anexos de Semana 4 con construir_anexo -- la MISMA funcion
 que escribe data/unity/semana04.json -- uno con los parametros de
 semana03/parametros.json y otro con --cs, y los compara. SIN ESCRIBIR
 NADA en data/ ni en StreamingAssets/.

 Correr (desde la raiz del repo):

   python semana05/comparar_anexos.py                  # lt2, --cs 0.20
   python semana05/comparar_anexos.py lt2 --cs 0.20
   python semana05/comparar_anexos.py lt2 --cs 0.20 --ver-avisos

 Para verlo EN Unity (eso si escribe data/unity/ y StreamingAssets/):

   python semana04/exportar_unity.py lt2 --cs 0.20      # y Stop + Play
   python semana04/exportar_unity.py lt2                # volver a la base

 ----------------------------------------------------------------
 QUE COMPRUEBA (sale con 1 si algo falla)
 ----------------------------------------------------------------
 El caso EX es V = Cs * W repartido en altura (lab_semana03.armar_casos):
 Cs no entra en G ni en Q, y entra LINEAL en EX y EY. El modelo es
 elastico lineal, asi que:

 - G y Q salen IDENTICOS (desplazamientos, f de cada barra, estaciones
   y demandas), bit a bit;
 - EX y EY se escalan por k = Cs nuevo / Cs base. Cota: cada numero
   viene redondeado (fuerzas a 4 decimales, desplazamientos a 8), y
   el escalado multiplica el redondeo de la base por k:
   5e-5 (1 + k) kN en f y w, 5e-9 (1 + k) m; en las estaciones del
   diagrama My(x) lleva ademas x * V_i, la cota del exportador
   5e-5 (2 + x)(1 + k) (ver diferencias());
 - cada combinacion es la suma lambda * caso de SU anexo (con el Cs
   nuevo, la combinacion hereda el sismo nuevo sin tocar nada mas).
   Cota: el redondeo de la combinacion mas el de cada termino,
   5e-5 (1 + sum|lambda|);
 - el anexo base en memoria es el que Unity lee hoy
   (data/unity/semana04.json), si es del mismo edificio y parametros:
   lo que el panel muestra "antes" es de verdad el antes. Si Unity
   tiene otro anexo, avisa y no falla;
 - G de POST /analizar (el modelo del visor, data/unity/<ed>.json) es
   el G del anexo. Q, EX y EY NO lo son (otra fuente de cargas): se
   imprimen para declararlo, no se exigen.

 Despues imprime, para la columna demo y el muro demo del anexo (los
 elige construir_anexo por regla: la columna de mayor axial en G y el
 muro mas largo), las lineas del panel de VisorSemana04 -- P, M, Mn,
 u = M/Mn (el D/C) y PASA -- antes y despues, en todos los casos.

 Ruido: la busqueda de las curvas P-M (comun/capacidad.py) hace que
 OpenSees escriba "failed to converge" por stderr. No cambia los
 resultados (la curva se arma con los puntos que convergen), pero tapa
 la salida: se desvia a un archivo temporal y se cuenta. --ver-avisos
 los deja pasar.
================================================================
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import json
import math
import os
import sys
import tempfile
import time
from decimal import Decimal, ROUND_HALF_UP

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                'comun'))
import rutas                                 # noqa: E402

rutas.entrar(__file__, os.path.join(rutas.RAIZ, 'semana04'))
import trazabilidad                          # noqa: E402
import calcular                              # noqa: E402
import servidor_opensees as motor            # noqa: E402

ex4 = trazabilidad.exportador()              # semana04/exportar_unity.py, POR RUTA
CASOS_BASE = ex4.CASOS_BASE
COTA_REDONDEO_kN = ex4.COTA_REDONDEO                       # 5e-5: 4 decimales
COTA_REDONDEO_m = 0.5 * 10.0 ** -ex4.DECIMALES_DESPLAZAMIENTO   # 5e-9: 8 decimales
MAGNITUDES = ('N', 'Vy', 'Vz', 'T', 'My', 'Mz')
UNITY_ANEXO = os.path.join(rutas.UNITY, 'semana04.json')


# ============================================================
# ARMAR LOS ANEXOS SIN ESCRIBIR
# ============================================================
@contextlib.contextmanager
def desviar_stderr(activo):
    """
    Manda el descriptor 2 (el que usa OpenSees desde C++) a un archivo
    temporal y devuelve la lista donde quedan sus lineas al salir.
    sys.stderr de Python va al mismo descriptor, asi que tambien se
    guarda; una excepcion se imprime DESPUES, con stderr ya devuelto.
    """
    lineas = []
    if not activo:
        yield lineas
        return
    sys.stderr.flush()
    guardado = os.dup(2)
    with tempfile.TemporaryFile(mode='w+b') as tmp:
        os.dup2(tmp.fileno(), 2)
        try:
            yield lineas
        finally:
            sys.stderr.flush()
            os.dup2(guardado, 2)
            os.close(guardado)
            tmp.seek(0)
            lineas.extend(tmp.read().decode('utf-8', 'replace').splitlines())


def armar(edificio, argv, callar):
    """(anexo, contexto, segundos, lineas de stderr)."""
    t0 = time.time()
    with desviar_stderr(callar) as ruido:
        anexo, ctx = ex4.construir_anexo(edificio, argv)
    return anexo, ctx, time.time() - t0, ruido


# ============================================================
# COMO LO ESCRIBE EL PANEL (VisorSemana04.Panel.cs)
# ============================================================
def F(v, formato):
    """
    VisorSemana04.Panel.F: v.ToString(formato, InvariantCulture) con v
    float de 32 bits. .NET redondea los digitos de la forma corta del
    float, con la mitad hacia afuera (como panel() de reanalisis_demo).
    """
    decimales = len(formato.split('.')[1]) if '.' in formato else 0
    try:
        import numpy as np
        corto = np.format_float_positional(np.float32(v), unique=True, trim='-')
    except ImportError:                                  # sin numpy: doble
        corto = repr(float(v))
    q = Decimal(corto).quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)
    return format(q, 'f')


def lineas_del_panel(d, e, fam):
    """Las dos lineas de '--- demanda / capacidad ---' del panel."""
    cual = (' (|%s|, en su plano)' % e['momento_en_el_plano']) if e['tipo'] == 'muro' else ''
    l1 = 'P %s kN   M %s kN*m%s   extremo %s' % (F(d['P'], '0.0'), F(d['M'], '0.0'),
                                                  cual, d['extremo'])
    if d['u'] >= 9999.0:
        l2 = 'fuera de la curva P-M (u = 9999)'
    else:
        l2 = 'Mn %s kN*m   u %s   %s' % (F(d['Mn'], '0.0'), F(d['u'], '0.000'),
                                         'PASA' if d['pasa'] else 'NO PASA')
    return ['familia %d: %s' % (fam['indice'], fam['clave']), l1, l2]


# ============================================================
# COMPARACIONES
# ============================================================
def por_id(lista):
    return {int(x['id']): x for x in lista}


def diferencias(a, b, k=1.0):
    """
    b contra k*a, dos bloques de caso. Devuelve
    {'m': (cociente, error, cota, donde), 'kN': (...), 'max_m', 'max_kN'}
    con el peor error/cota y el peor error absoluto.

    Cotas, por su causa: b y a vienen redondeados, a lo mas 5e-5 kN
    (5e-9 m) cada uno, y el de a queda multiplicado por k:
      - desplazamientos, f y w:  redondeo * (1 + k);
      - estaciones (N, V, T, My, Mz en x): se calculan con f ya
        redondeado y se redondean otra vez, y My y Mz llevan x*V_i, que
        multiplica el redondeo de V_i por x. Es la cota con que el
        exportador exige que el diagrama llegue a f_j, en cada x y con
        sum|lambda| = 1 + k: ex4.cota_de_cierre(x, 1 + k).
    Mas 4 eps del tamano de los terminos (ex4.FACTOR_COMA_FLOTANTE).
    """
    eps = ex4.FACTOR_COMA_FLOTANTE
    salida = {'m': (0.0, 0.0, 0.0, None), 'kN': (0.0, 0.0, 0.0, None),
              'max_m': 0.0, 'max_kN': 0.0}

    def anotar(tipo, vb, va, cota, donde):
        error = abs(vb - k * va)
        cota = cota + eps * (abs(vb) + abs(k * va))
        salida['max_' + tipo] = max(salida['max_' + tipo], error)
        if error / cota > salida[tipo][0]:
            salida[tipo] = (error / cota, error, cota, donde)

    da, db = por_id(a['desplazamientos']), por_id(b['desplazamientos'])
    ea, eb = por_id(a['esfuerzos']), por_id(b['esfuerzos'])
    if set(da) != set(db) or set(ea) != set(eb):
        salida['m'] = salida['kN'] = (math.inf, math.inf, 0.0, 'nodos o elementos distintos')
        return salida
    for nid, x in da.items():
        for c in ('ux', 'uy', 'uz', 'rx', 'ry', 'rz'):
            anotar('m', db[nid][c], x[c], COTA_REDONDEO_m * (1 + k), (nid, c))
    for eid, x in ea.items():
        y = eb[eid]
        if x['x'] != y['x']:
            salida['kN'] = (math.inf, math.inf, 0.0, (eid, 'estaciones distintas'))
            return salida
        for c in ('f', 'w'):
            for i, (va, vb) in enumerate(zip(x[c], y[c])):
                anotar('kN', vb, va, COTA_REDONDEO_kN * (1 + k), (eid, c, i))
        for i, xs in enumerate(x['x']):
            cotas = ex4.cota_de_cierre(xs, 1 + k)
            for j, c in enumerate(MAGNITUDES):
                anotar('kN', y[c][i], x[c][i], cotas[j], (eid, c, 'x = %.2f' % xs))
    return salida


def demandas_iguales(a, b):
    """Cuantas demandas difieren en algo (P, M, Mn, u, pasa, extremo)."""
    da, db = por_id(a['demandas']), por_id(b['demandas'])
    if set(da) != set(db):
        return -1
    return sum(1 for i in da if da[i] != db[i])


def combinacion_menos_suma(anexo, combo):
    """
    Peor |combinacion - sum lambda * caso| dentro de UN anexo, en f y en
    desplazamientos. Devuelve (peor_m, peor_kN, sum|lambda|).
    """
    casos = {c['nombre']: c for c in anexo['casos']}
    lambdas = dict(zip(CASOS_BASE, combo['factores']))
    activos = {c: l for c, l in lambdas.items() if l != 0.0}
    base_d = {c: por_id(casos[c]['desplazamientos']) for c in activos}
    base_e = {c: por_id(casos[c]['esfuerzos']) for c in activos}
    pm = pk = 0.0
    for d in combo['desplazamientos']:
        for k in ('ux', 'uy', 'uz', 'rx', 'ry', 'rz'):
            suma = sum(l * base_d[c][int(d['id'])][k] for c, l in activos.items())
            pm = max(pm, abs(d[k] - suma))
    for s in combo['esfuerzos']:
        for i, v in enumerate(s['f']):
            suma = sum(l * base_e[c][int(s['id'])]['f'][i] for c, l in activos.items())
            pk = max(pk, abs(v - suma))
    return pm, pk, sum(abs(l) for l in activos.values())


def flask_contra_anexo(edificio, ctx, check):
    """
    Lo que resuelve POST /analizar (el modelo del visor, data/unity/<ed>.json,
    el que Unity manda al editar) contra los casos base del anexo. Es la
    limitacion que se declara en MODIFICACIONES.md: los dos arman G igual,
    pero Q y el sismo salen de fuentes distintas (el visor: la Q del plano
    y el sismo del perfil del edificio; el anexo: semana03/parametros.json).
    Solo G se exige igual. Cota: cada lado viene redondeado a 8 decimales
    por el servidor, 2 * 5e-9 m.
    """
    ruta = rutas.unity(edificio)
    if not os.path.isfile(ruta):
        print('    [AVISO] no existe %s: no se compara con /analizar'
              % os.path.relpath(ruta, rutas.RAIZ))
        return
    with open(ruta, encoding='utf-8') as f:
        modelo_u = json.load(f)
    with motor._lock_opensees:
        rf = motor.construir_y_resolver(copy.deepcopy(modelo_u))
    flask = {c['nombre']: c for c in rf.get('casos') or []}
    casos_u = {c['nombre']: c for c in modelo_u.get('casos_de_carga') or []}
    print()
    print('  /analizar (%s, lo que manda Unity) CONTRA LOS CASOS BASE DEL ANEXO'
          % os.path.relpath(ruta, rutas.RAIZ))
    print('    (max = mayor componente en mm; peor dif = mayor |u /analizar - u anexo| en m)')
    print('    %-4s  %-32s | %-32s   %9s | %9s   %s'
          % ('caso', 'aplicada /analizar [Fx,Fy,Fz]', 'aplicada anexo [Fx,Fy,Fz] kN',
             'max /anal', 'max anexo', 'peor dif'))
    peor_G = math.inf
    for c in CASOS_BASE:
        if c not in flask or c not in ctx['resultados']:
            print('    %-4s  (falta en uno de los dos)' % c)
            continue
        a = por_id(ctx['resultados'][c]['desplazamientos'])
        b = por_id(flask[c]['desplazamientos'])
        peor = (max(abs(float(a[i][k]) - float(b[i][k]))
                    for i in a for k in ('ux', 'uy', 'uz'))
                if set(a) == set(b) else math.inf)
        ea = calcular.equilibrio(ctx['modelo'], ctx['arm']['casos'][c],
                                 ctx['resultados'][c])['aplicada_kN']
        eb = calcular.equilibrio(modelo_u, casos_u[c], flask[c])['aplicada_kN']
        print('    %-4s  [%8.2f, %8.2f, %10.2f] | [%8.2f, %8.2f, %10.2f]   %9.5f | %9.5f   %.1e'
              % (c, *eb, *ea, flask[c]['max_desplazamiento'] * 1000,
                 ctx['resultados'][c]['max_desplazamiento'] * 1000, peor))
        if c == 'G':
            peor_G = peor
    check(peor_G <= 2 * COTA_REDONDEO_m,
          'G de /analizar = G del anexo (Q, EX y EY no: ver la tabla)',
          'peor %.1e m <= %.1e' % (peor_G, 2 * COTA_REDONDEO_m))


# ============================================================
def main(argv=None):
    ap = argparse.ArgumentParser(
        description='M2: el anexo de Semana 4 con otro coeficiente sismico, en memoria.')
    ap.add_argument('edificio', nargs='?', default='lt2',
                    help='lt2, ingenieria o conjunto (por defecto lt2)')
    ap.add_argument('--cs', type=float, default=0.20,
                    help='coeficiente sismico del anexo nuevo (por defecto 0.20)')
    ap.add_argument('--ver-avisos', action='store_true',
                    help='no desviar los avisos de OpenSees de la busqueda P-M')
    args = ap.parse_args(argv)

    print('=' * 78)
    print('  M2 POR DATO  %s   anexo base  vs  anexo con --cs %.2f   (en memoria)'
          % (args.edificio.upper(), args.cs))
    print('=' * 78)
    base, ctx0, t0, ruido0 = armar(args.edificio, [], not args.ver_avisos)
    nuevo, ctx1, t1, ruido1 = armar(args.edificio, ['--cs', repr(args.cs)],
                                    not args.ver_avisos)
    cs0, cs1 = ctx0['p']['coef_sismico'], ctx1['p']['coef_sismico']
    k = cs1 / cs0
    print('  construir_anexo (semana04/exportar_unity.py): base %.1f s, nuevo %.1f s'
          % (t0, t1))
    if not args.ver_avisos:
        n_avisos = sum(1 for l in ruido0 + ruido1 if 'converge' in l.lower())
        print('  avisos de OpenSees desviados: %d lineas (%d con "converge"), '
              'de la busqueda de curvas P-M; --ver-avisos los muestra'
              % (len(ruido0) + len(ruido1), n_avisos))

    fallos = []

    def check(cond, texto, detalle=''):
        print('    [%s] %s%s' % ('OK  ' if cond else 'FALLA', texto,
                                 ('   ' + detalle) if detalle else ''))
        if not cond:
            fallos.append(texto)

    # ---------------------------------------------------------- el dato
    print()
    print('  EL DATO QUE CAMBIA  (info.parametros del anexo, lo que Unity deserializa)')
    for a, b in zip(base['info']['parametros'], nuevo['info']['parametros']):
        marca = '   <-- cambia' if a != b else ''
        print('    %-58s | %s%s' % (a, b, marca) if a != b else '    %s' % a)
    print('    corte basal V = Cs * W:  %.2f kN  ->  %.2f kN   (x %.4f)'
          % (ctx0['arm']['V'], ctx1['arm']['V'], ctx1['arm']['V'] / ctx0['arm']['V']))

    # ---------------------------------------------------------- casos
    c0 = {c['nombre']: c for c in base['casos']}
    c1 = {c['nombre']: c for c in nuevo['casos']}
    print()
    print('  MAXIMO POR CASO  (max_desplazamiento_mm del anexo: la NORMA del desplazamiento)')
    for nombre in c0:
        m0, m1 = c0[nombre]['max_desplazamiento_mm'], c1[nombre]['max_desplazamiento_mm']
        n0 = sum(1 for d in c0[nombre]['demandas'] if not d['pasa'])
        n1 = sum(1 for d in c1[nombre]['demandas'] if not d['pasa'])
        print('    %-18s %10.4f -> %10.4f mm  (x %.4f)   NO PASA %3d -> %3d de %d'
              % (nombre, m0, m1, m1 / m0 if m0 else 0.0, n0, n1, len(c1[nombre]['demandas'])))

    # ---------------------------------------------------------- comprobaciones
    print()
    print('  COMPROBACIONES')
    check(list(c0) == list(c1)
          and [e['id'] for e in base['elementos']] == [e['id'] for e in nuevo['elementos']]
          and len(base['familias']) == len(nuevo['familias']),
          'mismos casos, elementos y familias P-M',
          '%d casos, %d elementos, %d familias'
          % (len(c1), len(nuevo['elementos']), len(nuevo['familias'])))
    for nombre in ('G', 'Q'):
        dif = diferencias(c0[nombre], c1[nombre])
        nd = demandas_iguales(c0[nombre], c1[nombre])
        check(dif['max_m'] == 0.0 and dif['max_kN'] == 0.0 and nd == 0,
              '%s identico (no depende de Cs)' % nombre,
              'peor %.1e m, %.1e kN; demandas distintas %d' % (dif['max_m'], dif['max_kN'], nd))
    for nombre in ('EX', 'EY'):
        dif = diferencias(c0[nombre], c1[nombre], k)
        check(dif['m'][0] <= 1.0 and dif['kN'][0] <= 1.0,
              '%s nuevo = %.4g * %s base' % (nombre, k, nombre),
              'peor error/cota: %.2f en m (%.1e en %s), %.2f en kN (%.1e <= %.1e en %s)'
              % (dif['m'][0], dif['m'][1], dif['m'][3],
                 dif['kN'][0], dif['kN'][1], dif['kN'][2], dif['kN'][3]))
    for anexo, etiqueta in ((base, 'base'), (nuevo, 'nuevo')):
        # El peor se elige por cociente error / cota: cada combinacion
        # tiene su propia cota (su sum|lambda|).
        peor = (-1.0, 0.0, 0.0, 0.0, '')
        for combo in anexo['casos']:
            if combo['tipo'] != 'combinacion':
                continue
            pm, pk, sl = combinacion_menos_suma(anexo, combo)
            cociente = max(pm / (COTA_REDONDEO_m * (1 + sl)),
                           pk / (COTA_REDONDEO_kN * (1 + sl)))
            if cociente > peor[0]:
                peor = (cociente, pm, pk, COTA_REDONDEO_kN * (1 + sl), combo['nombre'])
        check(0.0 <= peor[0] <= 1.0,
              'anexo %s: cada combinacion = sum lambda * casos' % etiqueta,
              'peor %s: %.1e m, %.1e kN <= %.1e = 5e-5 (1 + sum|lambda|); error/cota %.2f'
              % (peor[4], peor[1], peor[2], peor[3], peor[0]))

    # ---------------------------------------------------------- Unity hoy
    if os.path.isfile(UNITY_ANEXO):
        with open(UNITY_ANEXO, encoding='utf-8') as f:
            hoy = json.load(f)
        mismo = (hoy['info'].get('edificio') == args.edificio
                 and hoy['info'].get('parametros') == base['info']['parametros'])
        if not mismo:
            print('    [AVISO] data/unity/semana04.json es de %r con otros parametros: el '
                  '"antes" de Unity no es este. Exportar: python semana04/exportar_unity.py %s'
                  % (hoy['info'].get('edificio'), args.edificio))
        else:
            h = {c['nombre']: c for c in hoy['casos']}
            distintos = [n for n in c0 if n not in h
                         or h[n]['max_desplazamiento_mm'] != c0[n]['max_desplazamiento_mm']
                         or demandas_iguales(h[n], c0[n]) != 0]
            check(not distintos,
                  'el anexo base es el que Unity lee hoy (data/unity/semana04.json)',
                  'maximos y demandas de los %d casos iguales' % len(c0) if not distintos
                  else 'difieren: %s' % ', '.join(distintos))

    # ---------------------------------------------------------- Flask vs anexo
    flask_contra_anexo(args.edificio, ctx0, check)

    # ---------------------------------------------------------- el panel
    info = nuevo['info']
    elementos = por_id(nuevo['elementos'])
    for etiqueta, eid in (('COLUMNA DEMO', info['columna_demo']), ('MURO DEMO', info['muro_demo'])):
        print()
        e = elementos.get(eid)
        if e is None or e['familia'] < 0:
            print('  %s %s: sin enfierradura, no hay demanda-capacidad' % (etiqueta, eid))
            continue
        fam = nuevo['familias'][e['familia']]
        print('  %s %d  (%s %s, familia %d)   D/C = u = M / Mn(P)'
              % (etiqueta, eid, e['tipo'], e['seccion'], e['familia']))
        print('    caso                P antes -> despues     M antes -> despues'
              '      Mn antes -> despues      u antes -> despues')
        peor_caso, peor_u = None, -1.0
        for nombre in c1:
            d0 = por_id(c0[nombre]['demandas']).get(eid)
            d1 = por_id(c1[nombre]['demandas']).get(eid)
            if d0 is None or d1 is None:
                continue
            if d1['u'] > peor_u:
                peor_caso, peor_u = nombre, d1['u']
            print('    %-18s %9.1f -> %9.1f  %9.1f -> %9.1f  %8.1f -> %8.1f  %6.3f -> %6.3f  %s'
                  % (nombre, d0['P'], d1['P'], d0['M'], d1['M'], d0['Mn'], d1['Mn'],
                     d0['u'], d1['u'], 'PASA' if d1['pasa'] else 'NO PASA'))
        for nombre in dict.fromkeys([info['caso_por_defecto'], peor_caso]):
            d0 = por_id(c0[nombre]['demandas'])[eid]
            d1 = por_id(c1[nombre]['demandas'])[eid]
            print('    panel de Unity, caso %s%s:' % (nombre, ' (el que abre el visor)'
                                                      if nombre == info['caso_por_defecto']
                                                      else ' (el mayor u con el Cs nuevo)'))
            for a, b in zip(lineas_del_panel(d0, e, fam), lineas_del_panel(d1, e, fam)):
                if b == a:
                    print('      igual   %s' % a)
                else:
                    print('      antes   %s' % a)
                    print('      despues %s' % b)

    print()
    print('  No se escribio nada en data/ ni en StreamingAssets/.')
    if fallos:
        print('  FALLARON %d comprobaciones' % len(fallos))
        return 1
    print('  TODO OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
