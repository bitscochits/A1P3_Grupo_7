# -*- coding: utf-8 -*-
r"""
================================================================
 semana05/test_contrato_semana05.py  -  LA SUPERPOSICION CONTRA EL C#
================================================================
 Compara lo que Python le manda a Unity en la Semana 5 con los campos
 publicos de las clases [System.Serializable] que lo leen:

   data/unity/superposicion_<ed>.json   AnexoSuperposicionS5 (sin servidor)
   POST /combinar                       RespuestaCombinar     (con servidor)
   GET  /estados                        RespuestaEstados
   el cuerpo que Unity manda a /combinar PeticionCombinar

 y, por dentro, CasoS4, DespNodo, EsfuerzosS4, DemandaS4 y
 EquilibrioCaso (semana05/CONTRATO.md §3 y §6).

 Correr:
   python semana05/test_contrato_semana05.py          (LT2)
   python semana05/test_contrato_semana05.py ingenieria

 Las respuestas del servidor salen de servidor_s5.app.test_client():
 sin red y sin puerto, pero por el mismo codigo que atiende a Unity.

 ----------------------------------------------------------------
 POR QUE EN LAS DOS DIRECCIONES (igual que semana04/test_contrato_semana04.py)
 ----------------------------------------------------------------
 JsonUtility no avisa nada. Una clave sin campo C# se descarta; un
 campo C# sin clave se queda en 0, "" o null, y el panel muestra
 Mn = 0 o una deformada plana sin que nadie sospeche. Por eso (b) se
 exige en CADA objeto, no solo en el primero.

 ----------------------------------------------------------------
 PEND, NO FALLA
 ----------------------------------------------------------------
 Las clases de la Semana 5 las escribe U3 en paralelo
 (VisorSemana04.Superposicion.cs). Si el archivo o una clase todavia
 no existe, se marca PEND y no se compara: no es un error del
 contrato, es trabajo que falta. Lo mismo con la clave 'equilibrio'
 que agrega P2 (calcular.equilibrio de la combinacion, la unica suma
 de reacciones valida): si la clase no tiene el campo, JsonUtility la
 ignora sin romper nada, y queda PEND hasta que U3 lo agregue.
 Un campo C# que el JSON NO trae si es FALLA: es el fallo silencioso.
================================================================
"""
from __future__ import annotations

import filecmp
import importlib.util
import io
import json
import math
import os
import re
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_AQUI), 'comun'))
import rutas                                 # noqa: E402
rutas.entrar(__file__, os.path.join(rutas.RAIZ, 'semana04'),
             os.path.join(rutas.RAIZ, 'semana03'))

import superposicion as sp                   # noqa: E402

SCRIPTS = os.path.join(rutas.UNITY_PROYECTO, 'Assets', 'Scripts')
CS_SUPERPOSICION = os.path.join(SCRIPTS, 'VisorSemana04.Superposicion.cs')   # U3
CS_VISOR = os.path.join(SCRIPTS, 'VisorSemana04.cs')                          # U3
CS_MODELO = os.path.join(SCRIPTS, 'ModeloEstructural.cs')                     # W1
FUENTES_CS = (CS_SUPERPOSICION, CS_VISOR, CS_MODELO)

LARGO_F = 12
ESTACIONES = ('x', 'N', 'Vy', 'Vz', 'T', 'My', 'Mz')

# Claves que P2 agrega a lo que fija el contrato ("no se cambia; se
# agrega"). Sin campo C# son inofensivas: PEND, no FALLA.
AGREGADAS = {('RespuestaCombinar', 'equilibrio'), ('EstadoS5', 'equilibrio')}

fallos = []
pendientes = []


def check(cond, msg, detalle=''):
    print('  [%s] %s' % ('OK  ' if cond else 'FALLA', msg))
    for linea in ([detalle] if isinstance(detalle, str) else detalle):
        if linea:
            print('         %s' % linea)
    if not cond:
        fallos.append(msg)
    return cond


def pendiente(msg, detalle=''):
    print('  [PEND] %s' % msg)
    if detalle:
        print('         %s' % detalle)
    pendientes.append(msg)


def _lista(nombres, tope=8):
    nombres = sorted(nombres)
    return ', '.join(nombres[:tope]) + (' ...' if len(nombres) > tope else '')


# ============================================================
# LO QUE YA ESTA ESCRITO EN EL TEST DE LA SEMANA 4
# ============================================================
def _test_semana04():
    r"""
    semana04/test_contrato_semana04.py cargado POR RUTA, para usar sus
    campos_de_clases, tipo_calza y arreglos_anidados sin copiarlas (una
    sola definicion de como se lee un .cs). No corre nada al cargarse:
    sus checks estan dentro de main().
    """
    nombre = 'test_contrato_semana04_por_ruta'
    if nombre in sys.modules:
        return sys.modules[nombre]
    ruta = os.path.join(rutas.RAIZ, 'semana04', 'test_contrato_semana04.py')
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = mod
    spec.loader.exec_module(mod)
    return mod


t4 = _test_semana04()


# ============================================================
# COMPARAR UN FLUJO DE OBJETOS CONTRA SUS CLASES
# ============================================================
def comparar_clases(titulo, objetos, clases, sin_clave_valida=()):
    r"""
    objetos = {clase C#: [objetos del JSON que JsonUtility vuelca en ella]}.
    (a) toda clave tiene campo, (b) todo campo tiene clave en CADA objeto,
    y cada valor cabe en el tipo del campo. sin_clave_valida: pares
    (clase, campo) que el contrato dice que NO viajan en este flujo.
    """
    print()
    print('  -- %s --' % titulo)
    for clase, lista in objetos.items():
        if clase not in clases:
            pendiente('%s: la clase %s no existe todavia en el C#' % (titulo, clase))
            continue
        if not check(bool(lista), '%s: %s tiene objetos para compararla' % (titulo, clase)):
            continue
        campos = set(clases[clase])
        union = set().union(*(set(o) for o in lista))
        interseccion = set(lista[0]).intersection(*(set(o) for o in lista[1:]))

        sobran = union - campos
        agregadas = {c for c in sobran if (clase, c) in AGREGADAS}
        sobran -= agregadas
        for c in sorted(agregadas):
            pendiente('%s: %s.%s viaja (agregada por P2) y no tiene campo C#: JsonUtility la '
                      'ignora' % (titulo, clase, c))
        faltan = campos - interseccion - {c for (k, c) in sin_clave_valida if k == clase}

        print('    %-22s %7d objetos, %2d claves, %2d campos publicos'
              % (clase, len(lista), len(union), len(campos)))
        check(not sobran, '%s: %s (a) las claves del JSON tienen campo C#' % (titulo, clase),
              'sin campo C#: %s' % _lista(sobran) if sobran else '')
        detalle = ''
        if faltan:
            detalle = 'sin clave en el JSON: %s' % ', '.join(
                '%s (falta en %d de %d)' % (c, sum(1 for o in lista if c not in o), len(lista))
                for c in sorted(faltan))
        check(not faltan, '%s: %s (b) los %d campos C# tienen clave en todos los objetos'
              % (titulo, clase, len(campos)), detalle)

        malos, revisados = {}, 0
        for o in lista:
            for campo, tipo in clases[clase].items():
                if campo not in o:
                    continue
                revisados += 1
                motivo = t4.tipo_calza(tipo, o[campo], clases)
                if motivo and campo not in malos:
                    malos[campo] = '%s %s: %s (id %s)' % (tipo, campo, motivo, o.get('id', '-'))
        check(not malos, '%s: %s, %d valores caben en el tipo de su campo'
              % (titulo, clase, revisados),
              '; '.join(malos[c] for c in sorted(malos)) if malos else '')


def objetos_de_casos(casos):
    return {
        'CasoS4': casos,
        'DespNodo': [d for c in casos for d in c.get('desplazamientos') or []],
        'EsfuerzosS4': [e for c in casos for e in c.get('esfuerzos') or []],
        'DemandaS4': [d for c in casos for d in c.get('demandas') or []],
    }


def texto_sin_no_finitos(texto, que):
    r"""json.dumps y jsonify escriben NaN e Infinity sin quejarse; no son
    JSON y JsonUtility no los lee."""
    hallados = [t for t in ('NaN', 'Infinity') if re.search(r'[:\[,]\s*-?%s' % t, texto)]
    check(not hallados, '%s: sin NaN ni Infinity en el texto' % que,
          'aparece: %s' % ', '.join(hallados) if hallados else '')


def revisar_caso(caso, que, nombre, lambdas, referencia):
    r"""Lo que el visor da por supuesto de un CasoS4 de superposicion."""
    factores = [lambdas[c] for c in sp.CASOS]
    check(caso.get('nombre') == nombre and caso.get('tipo') == sp.TIPO,
          '%s: nombre = %r y tipo = %r' % (que, caso.get('nombre'), caso.get('tipo')),
          'se esperaba nombre %r, tipo %r' % (nombre, sp.TIPO)
          if (caso.get('nombre'), caso.get('tipo')) != (nombre, sp.TIPO) else '')
    check(caso.get('factores') == factores,
          '%s: factores = [G, Q, EX, EY] = %s' % (que, factores),
          'vino %s' % caso.get('factores') if caso.get('factores') != factores else '')
    check(caso.get('descripcion') == sp.texto_combinacion(lambdas),
          '%s: descripcion = %r' % (que, caso.get('descripcion')))
    esf = caso.get('esfuerzos') or []
    malos = [e.get('id') for e in esf if len(e.get('f') or []) != LARGO_F]
    check(not malos, '%s: f de %d en los %d esfuerzos' % (que, LARGO_F, len(esf)),
          'ids: %s' % malos[:8] if malos else '')
    malos = [e.get('id') for e in esf if len({len(e.get(k) or []) for k in ESTACIONES}) != 1]
    check(not malos, '%s: %s del mismo largo en cada barra' % (que, ', '.join(ESTACIONES)),
          'ids: %s' % malos[:8] if malos else '')
    if referencia is None:
        return
    for clave, bloque in (('desplazamientos', 'nodos'), ('esfuerzos', 'barras'),
                          ('demandas', 'barras con fierro')):
        ids = [int(x['id']) for x in caso.get(clave) or []]
        quiero = referencia[clave]
        check(sorted(ids) == quiero and len(set(ids)) == len(ids),
              '%s: %s de los mismos %d %s que el anexo de Semana 4, sin repetir'
              % (que, clave, len(quiero), bloque),
              'vinieron %d (%d distintos)' % (len(ids), len(set(ids)))
              if sorted(ids) != quiero else '')
    familias = {int(d.get('familia', -1)) for d in caso.get('demandas') or []}
    fuera = sorted(f for f in familias if not 0 <= f < referencia['n_familias'])
    check(not fuera, '%s: toda familia citada por una demanda existe en el anexo (%d familias)'
          % (que, referencia['n_familias']), 'fuera: %s' % fuera if fuera else '')


def revisar_equilibrio(eq, que):
    if eq is None:
        check(False, '%s: trae equilibrio' % que)
        return
    largos = [len(eq.get(k) or []) for k in ('aplicada_kN', 'reaccion_kN', 'error_kN')]
    check(largos == [3, 3, 3] and eq.get('confiable') is True,
          '%s: equilibrio con aplicada/reaccion/error de 3 y confiable = true' % que,
          'largos %s, confiable %r' % (largos, eq.get('confiable'))
          if largos != [3, 3, 3] or eq.get('confiable') is not True else '')


# ============================================================
def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    edificio = argv.pop(0) if argv and not argv[0].startswith('-') else 'lt2'

    print('=' * 72)
    print('  CONTRATO JSON <-> C# DE LA SEMANA 5 (superposicion)   %s' % edificio.upper())
    print('=' * 72)

    # ------------------------------------------------------------
    print()
    print('[0] el C# que lee la superposicion')
    # ------------------------------------------------------------
    clases, origen = {}, {}
    fuente_sup = None
    for ruta in FUENTES_CS:
        rel = os.path.relpath(ruta, rutas.RAIZ)
        if not os.path.isfile(ruta):
            if ruta == CS_SUPERPOSICION:
                pendiente('no existe %s (lo escribe U3)' % rel)
                continue
            check(False, 'existe %s' % rel)
            continue
        propias = t4.campos_de_clases(ruta)
        repetidas = set(propias) & set(clases)
        check(not repetidas, '%s: %d clases, ninguna repite nombre con %s'
              % (os.path.basename(ruta), len(propias),
                 ', '.join(sorted({os.path.basename(origen[c]) for c in repetidas})) or 'las demas'),
              'repetidas: %s' % _lista(repetidas) if repetidas else '')
        for c in propias:
            origen.setdefault(c, ruta)
            clases.setdefault(c, propias[c])
        if ruta == CS_SUPERPOSICION:
            with io.open(ruta, encoding='utf-8') as f:
                fuente_sup = f.read()

    if fuente_sup is not None:
        # El lector tiene que usar ESTAS clases en la raiz: si lee con
        # otra, este test compararia contra algo que nadie usa.
        sin_comentarios = re.sub(r'//[^\n]*', '', re.sub(r'/\*.*?\*/', '', fuente_sup, flags=re.S))
        for raiz in ('AnexoSuperposicionS5', 'RespuestaCombinar', 'RespuestaEstados'):
            if re.search(r'<\s*%s\s*>' % raiz, sin_comentarios):
                check(True, 'VisorSemana04.Superposicion.cs deserializa con <%s>' % raiz)
            else:
                pendiente('VisorSemana04.Superposicion.cs todavia no deserializa con <%s>' % raiz)

    # ------------------------------------------------------------
    print()
    print('[1] PeticionCombinar = lo que lee POST /combinar')
    # ------------------------------------------------------------
    lee_el_servidor = {'edificio'} | set(sp.CASOS)
    if 'PeticionCombinar' not in clases:
        pendiente('la clase PeticionCombinar no existe todavia en el C#')
    else:
        campos = set(clases['PeticionCombinar'])
        check(campos == lee_el_servidor,
              'campos de PeticionCombinar = claves que lee servidor_s5 (%s)'
              % ', '.join(sorted(lee_el_servidor)),
              'solo en C#: %s; solo en el servidor: %s'
              % (_lista(campos - lee_el_servidor) or '-', _lista(lee_el_servidor - campos) or '-')
              if campos != lee_el_servidor else '')

    # La referencia de ids: el anexo de Semana 4 del mismo edificio, que
    # es sobre el que U3 registra los casos.
    referencia, anexo_info = None, None
    for ruta in (os.path.join(rutas.UNITY, 'semana04.json'),
                 os.path.join(rutas.STREAMING, 'semana04.json')):
        if not os.path.isfile(ruta):
            continue
        with io.open(ruta, encoding='utf-8') as f:
            anexo = json.load(f)
        if (anexo.get('info') or {}).get('edificio') != edificio:
            continue
        c0 = anexo['casos'][0]
        referencia = {
            'desplazamientos': sorted(int(d['id']) for d in c0['desplazamientos']),
            'esfuerzos': sorted(int(e['id']) for e in anexo['elementos']),
            'demandas': sorted(int(e['id']) for e in anexo['elementos'] if e['familia'] >= 0),
            'n_familias': len(anexo['familias']),
        }
        anexo_info = (os.path.relpath(ruta, rutas.RAIZ), anexo['info'])
        del anexo
        break
    if referencia is None:
        print('  [--  ] ningun semana04.json es de %r: los ids no se comparan con el anexo'
              % edificio)

    estados = sp.cargar_estados()
    estados_esperados = [(e['nombre'], e['descripcion'], sp.lambdas_de(e['lambdas']))
                         for e in estados['estados']]

    # ------------------------------------------------------------
    print()
    print('[2] data/unity/superposicion_%s.json  ->  AnexoSuperposicionS5' % edificio)
    # ------------------------------------------------------------
    ruta_pre = sp.ruta_precalculado(edificio)
    if not os.path.isfile(ruta_pre):
        if edificio == 'lt2':
            check(False, 'existe %s (python semana05/superposicion.py lt2 --exportar)'
                  % os.path.relpath(ruta_pre, rutas.RAIZ))
        else:
            pendiente('no hay %s: solo el LT2 se precalcula (decision 3)'
                      % os.path.relpath(ruta_pre, rutas.RAIZ))
    else:
        with io.open(ruta_pre, encoding='utf-8') as f:
            texto = f.read()
        pre = json.loads(texto)
        print('  json    %s  (%.2f MB)' % (os.path.relpath(ruta_pre, rutas.RAIZ),
                                          len(texto.encode('utf-8')) / 1048576.0))
        texto_sin_no_finitos(texto, 'precalculado')
        est = pre.get('estados') or []
        casos = [e.get('caso') or {} for e in est]
        objetos = {'AnexoSuperposicionS5': [pre], 'InfoSuperposicionS5': [pre.get('info') or {}],
                   'EstadoS5': est, 'LambdasS5': [e.get('lambdas') or {} for e in est]}
        objetos.update(objetos_de_casos(casos))
        if 'equilibrio' in (clases.get('EstadoS5') or {}):
            objetos['EquilibrioCaso'] = [e.get('equilibrio') or {} for e in est]
        comparar_clases('precalculado', objetos, clases)
        check(not t4.arreglos_anidados(pre), 'precalculado: ningun arreglo dentro de otro')

        info = pre.get('info') or {}
        check(info.get('edificio') == edificio and info.get('generado_por') == sp.GENERADO_POR,
              'info.edificio = %r, info.generado_por = %r'
              % (info.get('edificio'), info.get('generado_por')))
        hay = [(e.get('nombre'), e.get('descripcion'), e.get('lambdas')) for e in est]
        check(hay == estados_esperados, 'estados = E1, E2, E3 de estados_s5.json, en ese orden '
              '(nombre, descripcion, lambdas)', 'vino %s' % hay if hay != estados_esperados else '')
        for e in est:
            if e.get('lambdas') and e.get('caso'):
                revisar_caso(e['caso'], 'precalculado %s' % e.get('nombre'), e.get('nombre'),
                             sp.lambdas_de(e['lambdas']), referencia)
                revisar_equilibrio(e.get('equilibrio'), 'precalculado %s' % e.get('nombre'))
        if anexo_info is not None:
            check(info.get('parametros') == anexo_info[1].get('parametros'),
                  'info.parametros = %s info.parametros (U3 avisa si difieren)' % anexo_info[0],
                  ['precalculado: %s' % info.get('parametros'),
                   'anexo:        %s' % anexo_info[1].get('parametros')]
                  if info.get('parametros') != anexo_info[1].get('parametros') else '')

        ed_sa, _p = sp._edificio_del_anexo_en_streaming()
        if ed_sa == edificio:
            check(os.path.isfile(sp.STREAMING) and filecmp.cmp(ruta_pre, sp.STREAMING, shallow=False),
                  'StreamingAssets/superposicion.json identico byte a byte al precalculado')
        else:
            print('  [--  ] StreamingAssets es de %r: su superposicion.json no se compara' % ed_sa)

    # ------------------------------------------------------------
    print()
    print('[3] POST /combinar y GET /estados (servidor_s5.app.test_client, sin red)')
    # ------------------------------------------------------------
    import servidor_s5                        # noqa: E402  (registra las rutas en la app)
    servidor_s5.ARGV_PARAMETROS[:] = argv
    cliente = servidor_s5.app.test_client()

    http = cliente.get('/estados')
    resp = http.get_json(silent=True) or {}
    check(http.status_code == 200 and resp.get('ok') is True and resp.get('error') == '',
          'GET /estados: HTTP %d, ok = %r, error = %r'
          % (http.status_code, resp.get('ok'), resp.get('error')))
    texto_sin_no_finitos(http.get_data(as_text=True), 'GET /estados')
    est = resp.get('estados') or []
    rangos = resp.get('rangos') or {}
    comparar_clases('GET /estados', {
        'RespuestaEstados': [resp], 'EstadoS5': est,
        'LambdasS5': [e.get('lambdas') or {} for e in est],
        'RangosS5': [rangos], 'RangoS5': [rangos[c] for c in sp.CASOS if c in rangos],
    }, clases, sin_clave_valida={('EstadoS5', 'caso'), ('EstadoS5', 'equilibrio')})
    hay = [(e.get('nombre'), e.get('descripcion'), e.get('lambdas')) for e in est]
    check(hay == estados_esperados, 'GET /estados: E1, E2, E3 de estados_s5.json en ese orden')
    check(all('caso' not in e for e in est), 'GET /estados: los estados no traen caso (CONTRATO §3)')
    malos = []
    for c in sp.CASOS:
        r = rangos.get(c) or {}
        mn, mx, paso = r.get('min'), r.get('max'), r.get('paso')
        if not all(isinstance(v, (int, float)) for v in (mn, mx, paso)) or not (mn < mx and paso > 0):
            malos.append('%s: %r' % (c, r))
            continue
        pasos = (mx - mn) / paso
        if abs(pasos - round(pasos)) > 1e-9:
            malos.append('%s: (max - min) / paso = %.6f no es entero' % (c, pasos))
        for nombre, _d, lam in estados_esperados:
            k = (lam[c] - mn) / paso
            if not mn - 1e-12 <= lam[c] <= mx + 1e-12 or abs(k - round(k)) > 1e-9:
                malos.append('%s: %s = %g no cae en un paso del slider' % (nombre, c, lam[c]))
    check(not malos, 'rangos de G, Q, EX, EY: min < max, paso entero, y E1..E3 caen en un paso '
          'de cada slider', malos)
    if servidor_s5.servidor_opensees.PERMITIR_CORS:
        check(http.headers.get('Access-Control-Allow-Origin') == '*',
              'GET /estados trae Access-Control-Allow-Origin: * (build Web)')

    # Un estado con lambda negativo, uno con EY y la combinacion nula:
    # los tres caminos distintos de bloque_caso.
    pedidos = [('E3', dict(estados_esperados[2][2])),
               ('0.9G - 1.0EY', {'G': 0.9, 'Q': 0.0, 'EX': 0.0, 'EY': -1.0}),
               ('nula', {'G': 0.0, 'Q': 0.0, 'EX': 0.0, 'EY': 0.0})]
    respuestas = []
    for que, lam in pedidos:
        # El cuerpo como lo arma VisorSemana04.Superposicion.cs (Sup_JsonDe):
        # las cinco claves, numeros con '.'.
        cuerpo = json.dumps(dict(edificio=edificio, **lam))
        http = cliente.post('/combinar', data=cuerpo, content_type='application/json')
        resp = http.get_json(silent=True) or {}
        ok = check(http.status_code == 200 and resp.get('ok') is True and resp.get('error') == '',
                   'POST /combinar %s: HTTP %d, ok = %r' % (que, http.status_code, resp.get('ok')),
                   resp.get('error') or '')
        if not ok:
            continue
        texto_sin_no_finitos(http.get_data(as_text=True), 'POST /combinar %s' % que)
        check(resp.get('edificio') == edificio, 'POST /combinar %s: edificio = %r'
              % (que, resp.get('edificio')))
        if anexo_info is not None:
            check(resp.get('parametros') == anexo_info[1].get('parametros'),
                  'POST /combinar %s: parametros = %s info.parametros' % (que, anexo_info[0]))
        revisar_caso(resp.get('caso') or {}, 'POST /combinar %s' % que, sp.NOMBRE_LIBRE,
                     sp.lambdas_de(lam), referencia)
        revisar_equilibrio(resp.get('equilibrio'), 'POST /combinar %s' % que)
        respuestas.append(resp)
        if que == pedidos[0][0] and servidor_s5.servidor_opensees.PERMITIR_CORS:
            check(http.headers.get('Access-Control-Allow-Origin') == '*',
                  'POST /combinar trae Access-Control-Allow-Origin: * (build Web)')
    if respuestas:
        objetos = {'RespuestaCombinar': respuestas}
        objetos.update(objetos_de_casos([r.get('caso') or {} for r in respuestas]))
        if 'equilibrio' in (clases.get('RespuestaCombinar') or {}):
            objetos['EquilibrioCaso'] = [r.get('equilibrio') or {} for r in respuestas]
        comparar_clases('POST /combinar', objetos, clases)
        check(not any(t4.arreglos_anidados(r) for r in respuestas),
              'POST /combinar: ningun arreglo dentro de otro')

    # ------------------------------------------------------------
    print()
    print('[4] los errores tambien son JSON {ok: false, error} (Unity lee el cuerpo)')
    # ------------------------------------------------------------
    malos_pedidos = [
        ('cuerpo que no es JSON', '{"edificio": "lt2", "G": ', 400),
        ('cuerpo que es una lista', '[1.2, 1.0, 0, 0]', 400),
        ('edificio con ruta', json.dumps({'edificio': '../modelo/lt2', 'G': 1.0}), 400),
        ('edificio inexistente', json.dumps({'edificio': 'no_existe', 'G': 1.0}), 400),
        ('factor de texto', json.dumps({'edificio': edificio, 'G': '1.2'}), 400),
        ('factor booleano', json.dumps({'edificio': edificio, 'G': True}), 400),
        ('factor infinito', '{"edificio": "%s", "G": 1e999}' % edificio, 400),
    ]
    for que, cuerpo, codigo in malos_pedidos:
        http = cliente.post('/combinar', data=cuerpo, content_type='application/json')
        resp = http.get_json(silent=True)
        bien = (http.status_code == codigo and isinstance(resp, dict) and resp.get('ok') is False
                and isinstance(resp.get('error'), str) and resp.get('error') != '')
        check(bien, 'POST /combinar con %s: HTTP %d y {ok: false, error: "..."}'
              % (que, http.status_code),
              'error: %s' % (resp or {}).get('error') if bien else 'vino %r' % (resp,))
    if 'RespuestaCombinar' in clases:
        faltan = {'ok', 'error'} - set(clases['RespuestaCombinar'])
        check(not faltan, 'RespuestaCombinar tiene ok y error (lo que Unity mira en un error)',
              'faltan: %s' % _lista(faltan) if faltan else '')

    print()
    print('=' * 72)
    if pendientes:
        print('  PENDIENTE (%d, no falla):' % len(pendientes))
        for p in pendientes:
            print('    - %s' % p)
    if fallos:
        print('  FALLARON %d:' % len(fallos))
        for f in fallos:
            print('    - %s' % f)
        print('=' * 72)
        return 1
    print('  EL CONTRATO JSON <-> C# DE LA SUPERPOSICION ESTA SANO%s'
          % (' (con pendientes)' if pendientes else ''))
    print('=' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())
