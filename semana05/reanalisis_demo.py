# -*- coding: utf-8 -*-
r"""
================================================================
 semana05/reanalisis_demo.py  -  LA MODIFICACION M1, ANTES Y DESPUES
================================================================
 Hace en memoria lo mismo que la demo en Unity: toma el modelo que
 dibuja el visor (data/unity/<ed>.json), le aplica la edicion que hace
 EditorEstructura al borrar una barra, lo manda al motor y muestra que
 cambio. Sin abrir Unity y SIN ESCRIBIR NADA en data/.

 Correr (desde la raiz del repo):

   python semana05/reanalisis_demo.py lt2 --borrar-elemento 69 --nodo 186
   python semana05/reanalisis_demo.py lt2 --borrar-elemento 69 --nodo 186 --float32
   python semana05/reanalisis_demo.py lt2 --borrar-elemento 69 --nodo 186 \
          --url http://localhost:5000/analizar
   python semana05/reanalisis_demo.py lt2 --seccion 337 "V 0.30x0.80" --nodo 186
   python semana05/reanalisis_demo.py lt2 --apoyo 2 1 1 1 0 0 0 --nodo 186
   python semana05/reanalisis_demo.py lt2 --desde "<modelo_editado.json>" --nodo 186

   --float32   manda los numeros como los manda Unity: JsonUtility lee y
               escribe float de 32 bits y solo los campos que declara
               ModeloEstructural.cs (el esquema se lee de ese archivo).
   --url       en vez de resolver en este proceso, le pega al servidor
               vivo (python semana05/servidor_s5.py). Es el camino
               EXACTO de Unity: POST /analizar con el modelo entero, y
               ?edificio=<ed> si el modelo no trae info.edificio, para
               que el Excel sea results/excel/reanalisis_<ed>.xlsx.
   --desde     el "despues" es un JSON guardado por Unity con el boton
               'Guardar JSON' (persistentDataPath/modelo_editado.json).

 ----------------------------------------------------------------
 QUE HACE EL EDITOR AL BORRAR UNA BARRA
 ----------------------------------------------------------------
 EditorEstructura.BorrarElemento: quita el elemento de la lista y,
 con QuitarCargasDeElemento, las cargas DISTRIBUIDAS que lo nombran en
 cada caso. No toca los nodos (quedan donde estaban), ni las cargas
 NODALES, ni areas_tributarias. Aca se hace exactamente eso.

 La consecuencia que hay que declarar: el peso propio de una columna o
 un muro viaja como carga NODAL en el caso G (mitad en cada extremo,
 edificios/lt2/exportar_unity.py), asi que al borrar la barra su peso
 SIGUE APLICADO. El script lo calcula y lo dice.

 ----------------------------------------------------------------
 QUE COMPRUEBA (sale con 1 si algo falla)
 ----------------------------------------------------------------
 - el "antes" reproduce la deformada G precalculada que trae el JSON
   (la que Unity dibuja sin servidor), a 1e-7 m;
 - todos los casos convergen, antes y despues;
 - el equilibrio de cada caso es confiable y cierra dentro de su cota
   (cada reaccion viene redondeada a 4 decimales: 5e-5 kN por fila, mas
   el residuo del solver, medido en 1.2e-6 kN sobre 3633 kN);
 - la carga aplicada cambia exactamente en las cargas que quito el
   editor (ni mas ni menos).
================================================================
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                'comun'))
import rutas                                 # noqa: E402

rutas.entrar(__file__)
import calcular                              # noqa: E402
import servidor_opensees as motor            # noqa: E402

MODELO_CS = os.path.join(rutas.UNITY_PROYECTO, 'Assets', 'Scripts', 'ModeloEstructural.cs')

# El servidor redondea cada reaccion a 4 decimales (extraer_resultados).
REDONDEO_REACCION_kN = 5e-5
# Residuo del solver sin redondear, medido en el LT2 (EX: 1.2e-6 kN sobre
# 3633 kN, 3e-10). Se toma 1e-9 relativo: tres veces lo medido.
RESIDUO_RELATIVO = 1e-9
# data/unity/<ed>.json guarda la deformada de G con 9 decimales.
TOL_DEFORMADA_m = 1e-7


# ============================================================
# LA EDICION, IGUAL QUE EditorEstructura.cs
# ============================================================
def borrar_elemento(modelo, eid):
    """
    EditorEstructura.BorrarElemento + QuitarCargasDeElemento: fuera el
    elemento y las cargas distribuidas que lo nombran. Devuelve
    {caso: [cargas quitadas]}.
    """
    antes = len(modelo['elementos'])
    modelo['elementos'] = [e for e in modelo['elementos'] if int(e['id']) != eid]
    if len(modelo['elementos']) == antes:
        raise SystemExit('el elemento %d no existe en el modelo' % eid)
    quitadas = {}
    for caso in modelo.get('casos_de_carga') or []:
        dist = caso.get('cargas_distribuidas') or []
        quitadas[caso['nombre']] = [c for c in dist if int(c['elemento']) == eid]
        caso['cargas_distribuidas'] = [c for c in dist if int(c['elemento']) != eid]
    return quitadas


def cambiar_seccion(modelo, eid, nombre):
    """
    EditorEstructura: la barra pasa a otra seccion del catalogo. Cambia
    A, Iy, Iz y J, o sea cambia K: exige reanalisis. El peso propio NO
    se recalcula (las cargas de G ya vienen sumadas en el modelo), y por
    eso la carga aplicada no se mueve; queda declarado en
    semana05_lab/CRITERIOS_REANALISIS.md, seccion 4.
    Devuelve (seccion_antes, seccion_despues) para poder contarlo.
    """
    secciones = {str(x['nombre']): x for x in modelo.get('secciones') or []}
    if nombre not in secciones:
        raise SystemExit('la seccion %r no esta en el modelo. Hay: %s'
                         % (nombre, ', '.join(sorted(secciones))))
    for e in modelo['elementos']:
        if int(e['id']) == eid:
            antes = str(e.get('seccion'))
            e['seccion'] = nombre
            return secciones.get(antes), secciones[nombre]
    raise SystemExit('el elemento %d no existe en el modelo' % eid)


def cambiar_apoyo(modelo, nid, restricciones):
    """
    EditorEstructura: otras restricciones en un nodo. Cambia que grados
    de libertad estan fijos, o sea cambia K: exige reanalisis.
    restricciones son 6 enteros [ux uy uz rx ry rz], 1 = fijo.
    Devuelve (antes, despues).
    """
    if len(restricciones) != 6 or any(v not in (0, 1) for v in restricciones):
        raise SystemExit('--apoyo necesita 6 enteros 0 o 1: [ux uy uz rx ry rz]')
    for n in modelo['nodos']:
        if int(n['id']) == nid:
            antes = list(n.get('restricciones') or ([1] * 6 if n.get('fijo') else [0] * 6))
            n['restricciones'] = list(restricciones)
            # 'fijo' es el atajo de los seis: se mantiene coherente.
            n['fijo'] = all(v == 1 for v in restricciones)
            return antes, list(restricciones)
    raise SystemExit('el nodo %d no existe en el modelo' % nid)


# ============================================================
# LO QUE MANDA UNITY: JsonUtility.ToJson(ModeloEstructural)
# ============================================================
def esquema_csharp(ruta=MODELO_CS):
    """
    {clase: [(campo, tipo, valor por defecto)]} de los campos publicos de
    ModeloEstructural.cs. Se lee del C# y no se copia aca: si alguien
    agrega un campo, la emulacion lo sigue sola.
    """
    with open(ruta, encoding='utf-8') as f:
        src = f.read()
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    src = re.sub(r'//[^\n]*', '', src)
    clases = {}
    for m in re.finditer(r'class\s+(\w+)\s*(?::\s*[\w\.]+\s*)?\{', src):
        i = j = m.end() - 1
        prof = 0
        while j < len(src):
            prof += {'{': 1, '}': -1}.get(src[j], 0)
            if prof == 0:
                break
            j += 1
        cuerpo = src[i + 1:j]
        # solo el nivel superior de la clase: nada dentro de metodos
        plano, prof = [], 0
        for ch in cuerpo:
            if ch == '{':
                prof += 1
            elif ch == '}':
                prof -= 1
            elif prof == 0:
                plano.append(ch)
        campos = []
        for d in re.finditer(r'(\[[^\]]*\]\s*)*public\s+([\w<>\[\]\.]+)\s+([\w\s,]+?)'
                             r'\s*(?:=\s*([^;]*))?;', ''.join(plano)):
            if d.group(1) and 'NonSerialized' in d.group(1):
                continue
            tipo, defecto = d.group(2), (d.group(4) or '').strip()
            for nombre in d.group(3).split(','):
                nombre = nombre.strip()
                if re.fullmatch(r'\w+', nombre):
                    campos.append((nombre, tipo, defecto))
        clases[m.group(1)] = campos
    return clases


def _float32(v):
    """
    Como queda un numero despues de pasar por Unity: JsonUtility lo lee a
    float de 32 bits y al escribirlo usa el decimal mas corto que vuelve a
    ese mismo float. El servidor lee ese decimal como doble.
    """
    try:
        import numpy as np
        return float(np.format_float_positional(np.float32(v), unique=True, trim='0'))
    except ImportError:                              # sin numpy: el valor binario
        import struct
        return struct.unpack('f', struct.pack('f', float(v)))[0]


def _defecto(tipo, texto):
    if texto:
        t = texto.rstrip('fF').strip('"')
        if tipo == 'float':
            return float(t)
        if tipo == 'int':
            return int(t)
        if tipo == 'bool':
            return t == 'true'
        return t
    return {'int': 0, 'float': 0.0, 'bool': False, 'string': ''}.get(tipo)


def como_jsonutility(valor, clase, clases):
    """El dict que resulta de FromJson + ToJson: campos del C#, float32,
    string nulo como "", lista nula como [], objeto nulo con sus defaults."""
    valor = valor if isinstance(valor, dict) else {}
    salida = {}
    for nombre, tipo, defecto in clases[clase]:
        v = valor.get(nombre)
        base = tipo[5:-1] if tipo.startswith('List<') else (tipo[:-2] if tipo.endswith('[]') else None)
        if base is not None:
            v = v if isinstance(v, list) else []
            if base in clases:
                salida[nombre] = [como_jsonutility(x, base, clases) for x in v]
            elif base == 'float':
                salida[nombre] = [_float32(x) for x in v]
            elif base == 'int':
                salida[nombre] = [int(x) for x in v]
            else:
                salida[nombre] = list(v)
        elif tipo in clases:
            salida[nombre] = como_jsonutility(v, tipo, clases)
        elif v is None:
            salida[nombre] = _defecto(tipo, defecto)
        elif tipo == 'float':
            salida[nombre] = _float32(v)
        elif tipo == 'int':
            salida[nombre] = int(v)
        elif tipo == 'bool':
            salida[nombre] = bool(v)
        else:
            salida[nombre] = v if isinstance(v, str) else str(v)
    return salida


# ============================================================
# RESOLVER: en este proceso o por HTTP
# ============================================================
def url_con_edificio(url, modelo, edificio):
    """
    AnalizadorEstructural.UrlConEdificio: si el modelo no trae
    info.edificio (data/unity/lt2.json no lo trae), Unity agrega
    ?edificio=<el del anexo> para que el servidor llame al libro
    results/excel/reanalisis_<ed>.xlsx y no reanalisis_modelo.xlsx.
    """
    info = modelo.get('info') or {}
    if not edificio or info.get('edificio') or 'edificio=' in url:
        return url
    return url + ('&' if '?' in url else '?') + 'edificio=' + urllib.parse.quote(edificio)


def resolver(modelo, url=None, edificio=None):
    """(respuesta, segundos). Con url, POST como AnalizadorEstructural."""
    t0 = time.time()
    if url is None:
        with motor._lock_opensees:
            resp = motor.construir_y_resolver(copy.deepcopy(modelo))
    else:
        url = url_con_edificio(url, modelo, edificio)
        pedido = urllib.request.Request(
            url, data=json.dumps(modelo).encode('utf-8'),
            headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(pedido, timeout=600) as r:
                resp = json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            cuerpo = e.read().decode('utf-8', 'replace')
            raise SystemExit('el servidor respondio HTTP %d: %s' % (e.code, cuerpo[:400]))
        except urllib.error.URLError as e:
            raise SystemExit('no pude conectar con %s (%s). Levanta el servidor: '
                             'python semana05/servidor_s5.py' % (url, e.reason))
    if not resp.get('casos'):
        raise SystemExit('la respuesta no trae "casos": %s' % str(resp.get('error'))[:300])
    # Un servidor viejo no trae el equilibrio: se calcula con la MISMA
    # funcion, para no mezclar dos reglas.
    for caso, r in zip(modelo['casos_de_carga'], resp['casos']):
        if not r.get('equilibrio'):
            r['equilibrio'] = calcular.equilibrio(modelo, caso, r)
    return resp, time.time() - t0


# ============================================================
# FORMATO
# ============================================================
def panel(v, formato='0.####', escala=1.0):
    """
    Como lo escribe el C#: `(v*escala).ToString("0.####")` con v float de
    32 bits (EditorEstructura: d.uz*1000f), sin ceros de mas. .NET
    redondea los DIGITOS DECIMALES del float (su forma corta), con la
    mitad hacia afuera: -3.64515f sale -3.6452, aunque el binario de
    -3.64515f este un pelo por debajo. El servidor manda 8 decimales, asi
    que un desplazamiento en mm cae seguido justo en esa mitad: el ultimo
    digito del panel puede diferir en 1 del de la columna en doble.
    """
    from decimal import Decimal, ROUND_HALF_UP
    dec = formato.count('#')
    try:
        import numpy as np
        x32 = np.float32(_float32(v)) * np.float32(escala)
        corto = np.format_float_positional(x32, unique=True, trim='0')
    except ImportError:
        corto = repr(_float32(v) * escala)
    q = Decimal(corto).quantize(Decimal(1).scaleb(-dec), rounding=ROUND_HALF_UP)
    t = format(q, 'f')
    if '.' in t:
        t = t.rstrip('0').rstrip('.')
    return '0' if t in ('-0', '') else t


def por_id(lista):
    return {int(x['id']): x for x in lista}


def cota_equilibrio(r):
    eq = r['equilibrio']
    escala = max([abs(v) for v in eq['aplicada_kN']] + [1e-9])
    return REDONDEO_REACCION_kN * len(r['reacciones']) + RESIDUO_RELATIVO * escala


def sumar_distribuidas(modelo, caso_nombre, cargas):
    """Resultante global [Fx, Fy, Fz] de unas cargas distribuidas, con la
    misma conversion de ejes que calcular.equilibrio."""
    caso = {'nombre': caso_nombre, 'cargas_nodales': [], 'cargas_distribuidas': cargas}
    return calcular.equilibrio(modelo, caso, {'reacciones': []})['aplicada_kN']


# ============================================================
def main(argv=None):
    ap = argparse.ArgumentParser(
        description='M1: editar el modelo como en Unity, reanalizar y comparar.')
    ap.add_argument('edificio', nargs='?', default='lt2',
                    help='lt2, ingenieria o conjunto (lee data/unity/<ed>.json)')
    ap.add_argument('--borrar-elemento', type=int, action='append', default=[],
                    metavar='ID', help='barra a borrar (se puede repetir)')
    ap.add_argument('--seccion', nargs=2, action='append', default=[],
                    metavar=('ID', 'NOMBRE'),
                    help='M3: la barra ID pasa a la seccion NOMBRE (se puede repetir)')
    ap.add_argument('--apoyo', nargs=7, action='append', default=[],
                    metavar='V',
                    help='M4: NODO y sus 6 restricciones [ux uy uz rx ry rz], 1 = fijo')
    ap.add_argument('--desde', default=None,
                    help='JSON del modelo ya editado (Guardar JSON de Unity)')
    ap.add_argument('--nodo', type=int, default=None,
                    help='nodo a seguir; por defecto el extremo superior de la barra borrada')
    ap.add_argument('--elemento', type=int, action='append', default=[],
                    help='barra extra cuyos esfuerzos mostrar (ademas de las del nodo)')
    ap.add_argument('--float32', action='store_true',
                    help='mandar el modelo como lo manda JsonUtility (float32)')
    ap.add_argument('--url', default=None,
                    help='POST a un servidor vivo, p. ej. http://localhost:5000/analizar')
    args = ap.parse_args(argv)

    if not (args.borrar_elemento or args.seccion or args.apoyo or args.desde):
        ap.error('falta la edicion: --borrar-elemento ID, --seccion ID NOMBRE, '
                 '--apoyo NODO 6 enteros, o --desde <modelo_editado.json>')

    ruta = rutas.unity(args.edificio)
    if not os.path.isfile(ruta):
        raise SystemExit('no existe %s: exportalo con edificios/%s/exportar_unity.py'
                         % (os.path.relpath(ruta, rutas.RAIZ), args.edificio))
    with open(ruta, encoding='utf-8') as f:
        original = json.load(f)

    antes = copy.deepcopy(original)
    quitadas = {}
    ediciones = []
    if args.desde:
        with open(args.desde, encoding='utf-8-sig') as f:
            despues = json.load(f)
    else:
        despues = copy.deepcopy(original)
        for eid in args.borrar_elemento:
            for caso, lista in borrar_elemento(despues, eid).items():
                quitadas.setdefault(caso, []).extend(lista)
        for eid, nombre in args.seccion:
            sa, sd = cambiar_seccion(despues, int(eid), nombre)
            ediciones.append(
                'seccion del elemento %s: %s -> %s  (A %.4f -> %.4f m2, '
                'Iy %.3e -> %.3e, Iz %.3e -> %.3e m4)'
                % (eid, (sa or {}).get('nombre', '?'), nombre,
                   float((sa or {}).get('A', 0.0)), float(sd.get('A', 0.0)),
                   float((sa or {}).get('Iy', 0.0)), float(sd.get('Iy', 0.0)),
                   float((sa or {}).get('Iz', 0.0)), float(sd.get('Iz', 0.0))))
        for fila in args.apoyo:
            nid = int(fila[0])
            r = [int(v) for v in fila[1:]]
            antes_r, despues_r = cambiar_apoyo(despues, nid, r)
            ediciones.append('apoyo del nodo %d: %s -> %s' % (nid, antes_r, despues_r))

    if args.float32:
        clases = esquema_csharp()
        antes = como_jsonutility(antes, 'ModeloEstructural', clases)
        despues = como_jsonutility(despues, 'ModeloEstructural', clases)

    print('=' * 76)
    print('  REANALISIS  %s   (lo que hace Unity: editar -> POST /analizar -> dibujar)'
          % args.edificio.upper())
    print('=' * 76)
    casos = [c['nombre'] for c in original.get('casos_de_carga', [])]
    print('  modelo    %s  (%d nodos, %d elementos, casos %s)'
          % (os.path.relpath(ruta, rutas.RAIZ), len(original['nodos']),
             len(original['elementos']), ', '.join(casos)))
    for c in ediciones:
        print('  edicion   %s' % c)
    if ediciones:
        print('            cambia K -> exige reanalisis '
              '(semana05_lab/CRITERIOS_REANALISIS.md)')
    print('  motor     %s' % ('POST ' + args.url if args.url else
                              'servidor_opensees.construir_y_resolver, en este proceso'))
    print('  numeros   %s' % ('como JsonUtility: float32 y solo los campos de '
                              'ModeloEstructural.cs' if args.float32 else
                              'los del JSON, en doble precision'))

    nodos0 = por_id(original['nodos'])
    elems0 = por_id(original['elementos'])
    elems1 = por_id(despues['elementos'])
    mat = original.get('material', {})
    gamma = float(mat.get('gamma', 25.0))
    secciones = {s['nombre']: s for s in original['secciones']} \
        if isinstance(original['secciones'], list) else original['secciones']

    # ---------------------------------------------------------- la edicion
    print()
    borrados = sorted(set(elems0) - set(elems1))
    agregados = sorted(set(elems1) - set(elems0))
    if args.desde:
        print('  EDICION leida de %s' % args.desde)
        print('    elementos borrados %s, agregados %s' % (borrados or '-', agregados or '-'))
        movidos = [n for n, nd in por_id(despues['nodos']).items()
                   if n in nodos0 and max(abs(float(nd[k]) - float(nodos0[n][k]))
                                          for k in ('x', 'y', 'z')) > 1e-4]
        print('    nodos movidos (> 0.1 mm) %s' % (movidos or '-'))
        cambios = [e for e in elems1 if e in elems0
                   and elems1[e]['seccion'] != elems0[e]['seccion']]
        print('    secciones cambiadas %s' % (cambios or '-'))
    else:
        print('  EDICION  (%s)'
              % ('EditorEstructura: seccion o apoyo' if ediciones
                 else 'EditorEstructura.BorrarElemento + QuitarCargasDeElemento'))
    peso_que_queda = 0.0
    for eid in borrados:
        e = elems0[eid]
        a, b = nodos0[int(e['n1'])], nodos0[int(e['n2'])]
        L = math.dist((a['x'], a['y'], a['z']), (b['x'], b['y'], b['z']))
        print('    borrar %d: %s %s, nodos %d (z %.2f) -> %d (z %.2f), L = %.2f m'
              % (eid, e['tipo'], e['seccion'], a['id'], a['z'], b['id'], b['z'], L))
        n_q = sum(len(v) for v in quitadas.values())
        if not args.desde:
            print('    cargas distribuidas quitadas: %d  (%s)'
                  % (n_q, ', '.join('%s %d' % (c, len(v)) for c, v in quitadas.items())))
        vertical = abs(a['x'] - b['x']) < 1e-6 and abs(a['y'] - b['y']) < 1e-6
        if vertical:
            A = float(secciones[e['seccion']]['A'])
            peso = A * gamma * L
            peso_que_queda += peso
            g = next((c for c in original['casos_de_carga'] if c['nombre'] == 'G'), None)
            nodales = {int(c['nodo']): float(c.get('fz', 0.0))
                       for c in (g or {}).get('cargas_nodales', [])}
            print('    PESO PROPIO QUE QUEDA APLICADO: A*gamma*L = %.4g*%.4g*%.2f = %.2f kN,'
                  % (A, gamma, L, peso))
            print('      que viaja como carga NODAL de G, mitad en cada extremo '
                  '(edificios/lt2/exportar_unity.py).')
            print('      BorrarElemento no toca cargas nodales: siguen fz = %.3f kN en %d '
                  'y %.3f en %d' % (nodales.get(b['id'], 0.0), b['id'],
                                    nodales.get(a['id'], 0.0), a['id']))
            print('      (%.3f de cada uno eran de esta barra).' % (peso / 2.0))

    nodo = args.nodo
    if nodo is None:
        if not borrados:
            ap.error('con --desde hay que decir --nodo')
        e = elems0[borrados[0]]
        n1, n2 = nodos0[int(e['n1'])], nodos0[int(e['n2'])]
        nodo = int(n2['id'] if n2['z'] >= n1['z'] else n1['id'])
    if nodo not in nodos0:
        raise SystemExit('el nodo %d no existe' % nodo)

    # ---------------------------------------------------------- resolver
    r0, t0 = resolver(antes, args.url, args.edificio)
    r1, t1 = resolver(despues, args.url, args.edificio)
    print()
    print('  resuelto: antes %.1f s, despues %.1f s' % (t0, t1))
    if args.url:
        # Los dos pedidos escriben el MISMO libro: queda el del despues.
        for nombre, r in (('antes', r0), ('despues', r1)):
            print('  Excel del servidor (%s): %s' % (nombre, r.get('excel') or
                                                    'no -- %s' % r.get('excel_error')))

    fallos = []

    def check(cond, texto, detalle=''):
        print('    [%s] %s%s' % ('OK  ' if cond else 'FALLA', texto,
                                 ('   ' + detalle) if detalle else ''))
        if not cond:
            fallos.append(texto)

    c0 = {c['nombre']: c for c in r0['casos']}
    c1 = {c['nombre']: c for c in r1['casos']}

    # ---------------------------------------------------------- nodo
    n = nodos0[nodo]
    print()
    print('  NODO %d  (x %.3f, y %.3f, z %.2f)   mm, con los 8 decimales en m del servidor;'
          % (nodo, n['x'], n['y'], n['z']))
    print('    entre comillas, lo que escribe el panel del editor en Unity ("0.####" de un float)')
    print('    caso  comp        antes       despues    panel antes -> despues')
    for caso in casos:
        d0 = por_id(c0[caso]['desplazamientos']).get(nodo)
        d1 = por_id(c1[caso]['desplazamientos']).get(nodo)
        for k in ('ux', 'uy', 'uz'):
            v0 = d0[k] * 1000.0 if d0 else float('nan')
            v1 = d1[k] * 1000.0 if d1 else float('nan')
            print('    %-4s  %-2s  %12.5f  %12.5f    "%s %s mm" -> "%s %s mm"'
                  % (caso, k.upper(), v0, v1,
                     k.upper(), panel(d0[k], escala=1000.0) if d0 else '-',
                     k.upper(), panel(d1[k], escala=1000.0) if d1 else '-'))

    # ---------------------------------------------------------- maximos
    print()
    print('  MAXIMO POR CASO  (max_desplazamiento: la mayor COMPONENTE |ux|,|uy|,|uz|;')
    print('                    en Unity: Console "[caso] Max desplazamiento = ... mm")')
    for caso in casos:
        m0, m1 = c0[caso]['max_desplazamiento'] * 1000, c1[caso]['max_desplazamiento'] * 1000
        print('    %-4s  %10.5f -> %10.5f mm   (x %.2f)' % (caso, m0, m1, m1 / m0 if m0 else 0))

    # ---------------------------------------------------------- barras
    vecinas = sorted({int(e['id']) for e in despues['elementos']
                      if nodo in (int(e['n1']), int(e['n2']))} | set(args.elemento))
    print()
    print('  BARRAS EN EL NODO %d, caso G   (ejes locales; el panel muestra N_i, Vz_i, My_i / My_j)'
          % nodo)
    f0 = por_id(c0['G']['fuerzas_elementos']) if 'G' in c0 else {}
    f1 = por_id(c1['G']['fuerzas_elementos']) if 'G' in c1 else {}
    for eid in vecinas:
        e = elems1[eid] if eid in elems1 else elems0.get(eid)
        if e is None:
            continue
        print('    %d  %s %s  nodos %d -> %d' % (eid, e['tipo'], e['seccion'], e['n1'], e['n2']))
        for nombre, f in (('antes', f0.get(eid)), ('despues', f1.get(eid))):
            if f is None:
                print('      %-7s (no existe)' % nombre)
                continue
            v = f['f']
            print('      %-7s N %10.3f  Vz %9.3f  My %10.3f / %10.3f kN*m   '
                  '"My %s / %s kN*m"'
                  % (nombre, v[0], v[2], v[4], v[10], panel(v[4], '0.###'),
                     panel(v[10], '0.###')))

    # ---------------------------------------------------------- equilibrio
    print()
    print('  EQUILIBRIO POR CASO  (calcular.equilibrio: reacciones por grado de libertad)')
    print('    caso  antes/despues   aplicada [Fx, Fy, Fz] kN          '
          'reaccion [Fx, Fy, Fz] kN          peor error')
    for caso in casos:
        for nombre, r in (('antes', c0[caso]), ('despues', c1[caso])):
            eq = r['equilibrio']
            print('    %-4s  %-7s  [%9.3f, %9.3f, %10.3f]  [%9.3f, %9.3f, %10.3f]  %.1e'
                  % (caso, nombre, *eq['aplicada_kN'], *eq['reaccion_kN'],
                     max(abs(x) for x in eq['error_kN'])))

    # ---------------------------------------------------------- comprobaciones
    print()
    print('  COMPROBACIONES')
    peor, cual = 0.0, None
    if 'G' in c0:
        for d in c0['G']['desplazamientos']:
            nd = nodos0.get(int(d['id']))
            if nd is None or 'ux' not in nd:
                continue
            for k in ('ux', 'uy', 'uz'):
                err = abs(float(d[k]) - float(nd[k]))
                if err > peor:
                    peor, cual = err, (d['id'], k)
        check(peor < TOL_DEFORMADA_m + (2e-8 if args.float32 else 0.0),
              'el "antes" es la deformada G que Unity dibuja sin servidor',
              'peor %.1e m en %s' % (peor, cual))
    check(all(c['ok'] for c in r0['casos']) and all(c['ok'] for c in r1['casos']),
          'todos los casos convergen, antes y despues')
    for caso in casos:
        for nombre, r in (('antes', c0[caso]), ('despues', c1[caso])):
            eq = r['equilibrio']
            peor_eq, cota = max(abs(x) for x in eq['error_kN']), cota_equilibrio(r)
            check(eq['confiable'] and peor_eq <= cota,
                  'equilibrio %s %s confiable y cierra' % (caso, nombre),
                  '%.1e <= %.1e kN' % (peor_eq, cota))
    if not args.desde:
        for caso in casos:
            quitada = sumar_distribuidas(original, caso, quitadas.get(caso, []))
            a0, a1 = c0[caso]['equilibrio']['aplicada_kN'], c1[caso]['equilibrio']['aplicada_kN']
            dif = max(abs((a1[i] - a0[i]) + quitada[i]) for i in range(3))
            # aplicada_kN viene redondeada a 4 decimales: dos lecturas.
            check(dif <= 2 * 5e-5 + 1e-9 * max(abs(v) for v in a0 + [1.0]),
                  'la carga aplicada en %s cambia solo en lo que quito el editor' % caso,
                  'quitado [%.3f, %.3f, %.3f] kN, dif %.1e' % (*quitada, dif))

    print()
    if peso_que_queda:
        print('  OJO: %.2f kN de peso propio de lo borrado siguen aplicados como carga '
              'nodal en G.' % peso_que_queda)
    print('  No se escribio nada en data/.%s'
          % ('  (El servidor escribe su Excel en results/excel/.)' if args.url else ''))
    if fallos:
        print('  FALLARON %d comprobaciones' % len(fallos))
        return 1
    print('  TODO OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
