# -*- coding: utf-8 -*-
r"""
================================================================
 semana05/superposicion.py  -  LA COMBINACION CON LAMBDAS LIBRES
================================================================
 Arma, para CUALQUIER juego de factores (lambda_G, lambda_Q,
 lambda_EX, lambda_EY), el mismo bloque que el anexo de la Semana 4
 trae por cada combinacion declarada: desplazamientos de todos los
 nodos, esfuerzos de todas las barras con sus estaciones y la demanda
 sobre la curva P-M de cada elemento con fierro. Es lo que devuelve
 POST /combinar (servidor_s5.py) y lo que queda precalculado para
 E1..E3 en data/unity/superposicion_<ed>.json.

 Correr:
   python semana05/superposicion.py lt2                  E1..E3 en pantalla
   python semana05/superposicion.py lt2 --lambdas 0.9 0 -1.4 0
   python semana05/superposicion.py lt2 --exportar       escribe el precalculado
   python semana05/superposicion.py ingenieria --cs 0.20 (flags de parametros.py)

 ----------------------------------------------------------------
 NO SE REIMPLEMENTA NADA
 ----------------------------------------------------------------
 La base son los cuatro casos de la semana resueltos UNA vez con
 semana04/exportar_unity.construir_anexo (lab_semana03.armar_casos +
 lab_semana03.resolver, las familias P-M, los elementos). La
 combinacion es exportar_unity.bloque_caso, la misma funcion que arma
 los nueve casos del anexo: suma lineal de f, u y w con
 demanda_capacidad.combinar, estaciones con esfuerzos_internos y la
 demanda con demanda_capacidad.demanda + capacidad_en. Por eso E2
 (1.2G+1.6Q, que ya es un caso del anexo) tiene que salir identico al
 del anexo, y verificar_superposicion.py lo exige.

 ----------------------------------------------------------------
 POR QUE LA D/C VIENE CALCULADA Y NO SE SUMA EN UNITY
 ----------------------------------------------------------------
 u, f y las estaciones son lineales en lambda; la demanda-capacidad
 no: el extremo que manda cambia, M de una columna es hypot(My, Mz) y
 Mn depende de P. Sumar lambda * u_caso daria otro numero (la tabla de
 no linealidad de verificar_superposicion.py lo muestra con el muro y
 la columna de control). Regla de oro: Python calcula, Unity muestra.

 ----------------------------------------------------------------
 AUTOVERIFICACION
 ----------------------------------------------------------------
 bloque_caso devuelve el peor cociente de cierre (esfuerzo(L) contra
 f_j de OpenSees, sobre la cota de redondeo). Si pasa de 1, este
 modulo NO entrega el caso: lanza CasoNoCierra, igual que el
 exportador de la Semana 4 no escribe.
================================================================
"""
from __future__ import annotations

import io
import json
import math
import os
import shutil
import sys
import time

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_AQUI), 'comun'))
import rutas                                 # noqa: E402
rutas.entrar(__file__, os.path.join(rutas.RAIZ, 'semana04'),
             os.path.join(rutas.RAIZ, 'semana03'))

import calcular                              # noqa: E402
import combinar                              # noqa: E402
import trazabilidad                          # noqa: E402

# El exportador de Semana 4 POR RUTA: semana03/ tiene otro
# exportar_unity.py y un import por nombre traeria ese sin avisar
# (trazabilidad.exportador lo explica).
eu = trazabilidad.exportador()

CASOS = eu.CASOS_BASE
ESTADOS = os.path.join(_AQUI, 'estados_s5.json')
STREAMING = os.path.join(rutas.STREAMING, 'superposicion.json')
GENERADO_POR = 'semana05/superposicion.py'
NOMBRE_LIBRE = 'LIBRE'
TIPO = 'superposicion'


class CasoNoCierra(RuntimeError):
    """El caso combinado no cierra con OpenSees: no se entrega."""


def ruta_precalculado(edificio):
    """data/unity/superposicion_<ed>.json (el lanzador lo copia a StreamingAssets)."""
    return os.path.join(rutas.UNITY, 'superposicion_%s.json' % edificio)


# ============================================================
# ESTADOS Y LAMBDAS
# ============================================================
def cargar_estados(ruta=ESTADOS):
    """estados_s5.json tal cual, con sus '_por_que'."""
    with io.open(ruta, encoding='utf-8') as f:
        return json.load(f)


def sin_explicacion(valor):
    """Quita las claves '_...': son para quien lee el JSON, no para Unity
    (JsonUtility las ignoraria, pero el test de contrato las marcaria como
    claves sin campo C#)."""
    if isinstance(valor, dict):
        return {k: sin_explicacion(v) for k, v in valor.items() if not k.startswith('_')}
    if isinstance(valor, list):
        return [sin_explicacion(v) for v in valor]
    return valor


def lambdas_de(pedido):
    r"""
    {G, Q, EX, EY} como float desde un dict. Una clave ausente vale 0 (un
    caso que no entra). Lanza ValueError con el motivo si un factor no es
    un numero finito: un NaN o un infinito no dan error en la suma, dan
    un caso lleno de NaN que Unity dibujaria como nada.
    """
    if not isinstance(pedido, dict):
        raise ValueError('los factores tienen que venir en un objeto {G, Q, EX, EY}')
    salida = {}
    for c in CASOS:
        v = pedido.get(c, 0.0)
        # bool es int en Python: true no es un factor.
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError('el factor %s tiene que ser un numero, vino %r' % (c, v))
        v = float(v)
        if not math.isfinite(v):
            raise ValueError('el factor %s tiene que ser finito, vino %r' % (c, v))
        salida[c] = v
    return salida


def texto_combinacion(lambdas):
    """'1.20 G + 1.00 Q - 1.40 EX'. parametros.como_texto escribiria
    '+ -1.40 EX' con un factor negativo; esto pone el signo."""
    partes = []
    for c in CASOS:
        v = float(lambdas.get(c, 0.0))
        if abs(v) <= 1e-12:
            continue
        if not partes:
            partes.append('%s%.2f %s' % ('-' if v < 0 else '', abs(v), c))
        else:
            partes.append('%s %.2f %s' % ('-' if v < 0 else '+', abs(v), c))
    return ' '.join(partes) if partes else '(nula)'


# ============================================================
# LA BASE: LOS CUATRO CASOS RESUELTOS UNA VEZ
# ============================================================
def base(edificio, argv=(), silenciar=True):
    r"""
    Todo lo que hace falta para combinar sin volver a OpenSees.

    Usa construir_anexo entero (unos 2 s en el LT2 y en Ingenieria) y no
    una copia de sus primeras lineas: asi la base es por construccion la
    del anexo que Unity ya tiene abierto, con los mismos parametros, y el
    anexo queda a mano para comparar E2 con su caso.

    Toca OpenSees (resolver y las curvas P-M): quien la llame desde un
    servidor tiene que tomar el lock del motor.
    """
    argv = list(argv or ())
    t0 = time.time()
    avisos = trazabilidad.AvisosDeOpenSees() if silenciar else None
    if avisos is not None:
        with avisos:
            anexo, ctx = eu.construir_anexo(edificio, argv)
    else:
        anexo, ctx = eu.construir_anexo(edificio, argv)

    modelo = ctx['modelo']
    nodos = {int(n['id']): n for n in modelo['nodos']}
    largos = {int(e['id']): eu.lab.largo(e, nodos) for e in modelo['elementos']}
    return {
        'edificio': edificio,
        'argv': argv,
        'anexo': anexo,
        'ctx': ctx,
        # Las repartidas de cada caso base, como las arma construir_anexo.
        'cargas_base': {c: eu.cargas_por_elemento(ctx['arm']['casos'][c]) for c in CASOS},
        'familia_de': {int(e['id']): int(e['familia']) for e in anexo['elementos']},
        'largos': largos,
        'parametros': list(anexo['info']['parametros']),
        'ids_nodos': sorted(nodos),
        'segundos': time.time() - t0,
        'avisos_opensees': avisos.resumen() if avisos is not None else None,
    }


# ============================================================
# UN CASO COMBINADO
# ============================================================
def caso_combinado(b, lambdas, nombre=NOMBRE_LIBRE, tipo=TIPO, descripcion=None):
    r"""
    Un CasoS4 completo para esos factores (ver semana05/CONTRATO.md §3):
    nombre, tipo, descripcion, factores [G, Q, EX, EY],
    max_desplazamiento_mm, desplazamientos de todos los nodos, esfuerzos
    de todas las barras con estaciones y demandas de las barras con fierro.

    Devuelve (caso, peor_cierre) con peor_cierre = (cociente, id, comp).
    """
    lambdas = lambdas_de(lambdas)
    ctx = b['ctx']
    caso, _cargas, peor = eu.bloque_caso(
        nombre, tipo, descripcion if descripcion is not None else texto_combinacion(lambdas),
        lambdas, ctx['resultados'], b['anexo']['elementos'], b['cargas_base'],
        b['familia_de'], ctx['curvas'], b['largos'])

    if not caso['desplazamientos']:
        # Con todos los lambda en cero bloque_caso no recorre ningun caso
        # y deja la lista vacia. La combinacion nula es u = 0 en todos los
        # nodos (K u = 0), y Unity espera la lista COMPLETA: un nodo que
        # falta se dibuja sin mover, pero un visor que cuenta nodos no
        # sabria que es a proposito.
        caso['desplazamientos'] = [
            {'id': i, 'ux': 0.0, 'uy': 0.0, 'uz': 0.0, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0}
            for i in b['ids_nodos']]

    if peor[0] > 1.0:
        raise CasoNoCierra(
            '%s (%s) no cierra con OpenSees: elemento %d, %s, error %.3f veces la cota '
            'de redondeo. No se entrega.' % (nombre, texto_combinacion(lambdas),
                                              peor[1], peor[2], peor[0]))
    return caso, peor


def equilibrio_combinado(b, lambdas):
    r"""
    calcular.equilibrio de la combinacion: la carga combinada
    (combinar.combinar_cargas) contra las reacciones combinadas
    (combinar.combinar_resultados). Es la UNICA suma de reacciones valida
    (CLAUDE.md, "Reacciones"): en un nodo de diafragma nodeReaction trae la
    fuerza interna de la restriccion, y sumar todas las filas dobla el
    corte. Viaja calculado para que Unity no sume nada.
    """
    lambdas = lambdas_de(lambdas)
    ctx = b['ctx']
    carga = combinar.combinar_cargas(ctx['datos'], lambdas, NOMBRE_LIBRE)
    reacciones = combinar.combinar_resultados(ctx['resultados'], lambdas)
    return calcular.equilibrio(ctx['datos'], carga, reacciones)


def respuesta_combinar(b, lambdas):
    """El cuerpo de POST /combinar con ok = true (CONTRATO.md §3)."""
    caso, _peor = caso_combinado(b, lambdas)
    return {
        'ok': True,
        'error': '',
        'edificio': b['edificio'],
        'parametros': list(b['parametros']),
        'caso': caso,
        # Agregado a lo del contrato (no cambia nada de lo que ya estaba):
        # el equilibrio de la combinacion con la regla de calcular.equilibrio.
        'equilibrio': equilibrio_combinado(b, lambdas),
    }


def respuesta_estados(estados=None):
    """El cuerpo de GET /estados: los estados sin caso y los rangos."""
    estados = estados or cargar_estados()
    return {
        'ok': True,
        'error': '',
        'estados': [sin_explicacion({k: e[k] for k in ('nombre', 'descripcion', 'lambdas')})
                    for e in estados['estados']],
        'rangos': sin_explicacion(estados['rangos']),
    }


# ============================================================
# EL PRECALCULADO PARA EL EXE
# ============================================================
def anexo_superposicion(b, estados=None):
    r"""
    {info, estados[{nombre, descripcion, lambdas, caso, equilibrio}]}
    (CONTRATO.md §6). Cada caso lleva el nombre del estado ("E1"), no
    "LIBRE": asi Unity puede tener los tres registrados a la vez.
    """
    estados = estados or cargar_estados()
    salida = []
    for e in estados['estados']:
        lam = lambdas_de(e['lambdas'])
        caso, _peor = caso_combinado(b, lam, nombre=e['nombre'])
        salida.append({
            'nombre': e['nombre'],
            'descripcion': e['descripcion'],
            'lambdas': {c: lam[c] for c in CASOS},
            'caso': caso,
            'equilibrio': equilibrio_combinado(b, lam),
        })
    return {
        'info': {
            'edificio': b['edificio'],
            'descripcion': 'Estados de superposicion %s precalculados para el visor sin '
                           'servidor: el mismo calculo que POST /combinar '
                           '(exportar_unity.bloque_caso sobre los casos base)'
                           % '..'.join([salida[0]['nombre'], salida[-1]['nombre']])
                           if salida else 'sin estados',
            'generado_por': GENERADO_POR,
            'parametros': list(b['parametros']),
        },
        'estados': salida,
    }


def _edificio_del_anexo_en_streaming():
    """info.edificio del semana04.json que Unity lee, o None si no hay."""
    ruta = os.path.join(rutas.STREAMING, 'semana04.json')
    if not os.path.isfile(ruta):
        return None, None
    with io.open(ruta, encoding='utf-8') as f:
        info = json.load(f).get('info') or {}
    return info.get('edificio'), info.get('parametros')


def exportar(b, estados=None):
    r"""
    Escribe data/unity/superposicion_<ed>.json y lo copia a
    StreamingAssets/superposicion.json SOLO si el semana04.json de
    StreamingAssets es del mismo edificio. StreamingAssets es de UN
    edificio a la vez (el LT2 en la demo): copiar el de otro pisaria el
    que Unity esta usando, y el visor igual lo ignoraria. En ese caso
    se avisa y se deja al lanzador (comun/lanzar_unity.py sincronizar).
    Devuelve (ruta, copiado, aviso).
    """
    anexo = anexo_superposicion(b, estados)
    texto = json.dumps(anexo, separators=(',', ':'), ensure_ascii=False)
    ruta = ruta_precalculado(b['edificio'])
    rutas.asegurar(ruta)
    # Escritura atomica: Unity (o el lanzador) puede estar leyendolo.
    temporal = ruta + '.tmp'
    with io.open(temporal, 'w', encoding='utf-8') as f:
        f.write(texto)
    os.replace(temporal, ruta)

    aviso = None
    ed_streaming, params_streaming = _edificio_del_anexo_en_streaming()
    copiado = False
    if not os.path.isdir(rutas.STREAMING):
        aviso = 'no existe %s: no se copia' % os.path.relpath(rutas.STREAMING, rutas.RAIZ)
    elif ed_streaming not in (None, b['edificio']):
        aviso = ('StreamingAssets/semana04.json es de %r, no de %r: no se copia. '
                 'Para cambiar de edificio: python comun/lanzar_unity.py sincronizar %s'
                 % (ed_streaming, b['edificio'], b['edificio']))
    else:
        shutil.copy2(ruta, STREAMING)
        copiado = True
        if params_streaming is not None and list(params_streaming) != b['parametros']:
            aviso = ('copiado, pero StreamingAssets/semana04.json se exporto con otros '
                     'parametros: el visor lo va a avisar')
    return ruta, copiado, aviso


# ============================================================
def _resumen(b, lambdas, nombre):
    caso, peor = caso_combinado(b, lambdas, nombre=nombre)
    eq = equilibrio_combinado(b, lambdas)
    dem = caso['demandas']
    no_pasan = sum(1 for d in dem if not d['pasa'])
    fuera = sum(1 for d in dem if d['u'] >= 9999.0)
    print('  %-6s %-24s max %8.4f mm   NO PASA %d/%d (%d fuera de curva)   cierre %.3f'
          % (nombre, caso['descripcion'], caso['max_desplazamiento_mm'], no_pasan,
             len(dem), fuera, peor[0]))
    print('         equilibrio: aplicada [%s] kN, reaccion [%s] kN, error [%s]'
          % (', '.join('%.4f' % v for v in eq['aplicada_kN']),
             ', '.join('%.4f' % v for v in eq['reaccion_kN']),
             ', '.join('%.1e' % v for v in eq['error_kN'])))
    for d in dem:
        if not d['pasa']:
            print('         elemento %4d  P %10.4f  M %10.4f  Mn %10.4f  u %s'
                  % (d['id'], d['P'], d['M'], d['Mn'],
                     'fuera de curva' if d['u'] >= 9999.0 else '%.6f' % d['u']))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    edificio = 'lt2'
    if argv and not argv[0].startswith('-'):
        edificio = argv.pop(0)
    hacer_exportar = '--exportar' in argv
    argv = [a for a in argv if a != '--exportar']
    pedidos = None
    if '--lambdas' in argv:
        i = argv.index('--lambdas')
        try:
            valores = [float(x) for x in argv[i + 1:i + 5]]
        except ValueError:
            raise SystemExit('--lambdas necesita cuatro numeros: G Q EX EY')
        if len(valores) != 4:
            raise SystemExit('--lambdas necesita cuatro numeros: G Q EX EY')
        pedidos = dict(zip(CASOS, valores))
        argv = argv[:i] + argv[i + 5:]
    if not os.path.isfile(rutas.modelo(edificio)):
        raise SystemExit('no existe el modelo %r' % edificio)

    print('=' * 72)
    print('  SUPERPOSICION CON LAMBDAS LIBRES   %s' % edificio.upper())
    print('=' * 72)
    b = base(edificio, argv)
    print('  base: exportar_unity.construir_anexo en %.1f s (%d nodos, %d elementos, '
          '%d con fierro)' % (b['segundos'], len(b['ids_nodos']), len(b['largos']),
                              sum(1 for f in b['familia_de'].values() if f >= 0)))
    if b['avisos_opensees']:
        print('  %s' % b['avisos_opensees'])
    for linea in b['parametros']:
        print('  %s' % linea)
    print()

    estados = cargar_estados()
    t = time.time()
    if pedidos is not None:
        _resumen(b, pedidos, NOMBRE_LIBRE)
    else:
        for e in estados['estados']:
            _resumen(b, e['lambdas'], e['nombre'])
    print('  (combinado en %.3f s, sin volver a OpenSees)' % (time.time() - t))

    if hacer_exportar:
        ruta, copiado, aviso = exportar(b, estados)
        print()
        print('  %.2f MB -> %s' % (os.path.getsize(ruta) / 1048576.0,
                                  os.path.relpath(ruta, rutas.RAIZ)))
        if copiado:
            print('  -> %s' % os.path.relpath(STREAMING, rutas.RAIZ))
        if aviso:
            print('  AVISO: %s' % aviso)
    return 0


if __name__ == '__main__':
    sys.exit(main())
