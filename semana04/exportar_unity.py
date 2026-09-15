# -*- coding: utf-8 -*-
r"""
================================================================
 semana04/exportar_unity.py  -  LO QUE EL VISOR MUESTRA DE SEMANA 4
================================================================
 Deja en data/unity/semana04.json -- y una copia en StreamingAssets --
 todo lo que VisorSemana04.cs necesita para responder "que es este
 elemento y cuanto le llega": sus datos de OpenSees, sus esfuerzos
 internos a lo largo de la barra en cada caso y combinacion, y su
 punto de demanda sobre la curva P-M de su familia. Ya resuelto.

 Correr:
   python semana04/exportar_unity.py                 ingenieria
   python semana04/exportar_unity.py lt2 --cs 0.20 --k 2
   python semana04/exportar_unity.py conjunto --combinacion 1.4G

 Acepta los mismos parametros que lab_semana03.py y exporta lo que el
 laboratorio corre con ellos. No lee data/resultados/: esos traen el
 Q de la Semana 2 (2.0 kN/m2) y el informe usa el q de NCh1537.

 ----------------------------------------------------------------
 LA REGLA DEL REPOSITORIO
 ----------------------------------------------------------------
 OpenSees calcula, Unity muestra. Aca se calculan los esfuerzos
 internos, se combinan los casos y se pone la demanda sobre la
 capacidad; el visor solo escala esos numeros para dibujarlos. Nada
 se reimplementa: los casos son los de lab_semana03.armar_casos(),
 la seccion la de capacidad.desde_elemento(), la familia la de
 demanda_capacidad.firma_de_seccion() y la demanda la de
 demanda_capacidad.demanda() -- la misma cadena que el informe.

 ----------------------------------------------------------------
 DE f A LOS DIAGRAMAS
 ----------------------------------------------------------------
 OpenSees entrega doce numeros por barra (localForce): las fuerzas
 que los nudos le hacen AL elemento en sus extremos. Con la carga
 uniforme local w = (wx, wy, wz) del caso, el equilibrio de un trozo
 [0, x] da los esfuerzos internos en cualquier punto:

     N(x)  = -(N_i + wx x)            traccion positiva
     Vy(x) = -(Vy_i + wy x)           Vz(x) = -(Vz_i + wz x)
     T(x)  = -T_i
     My(x) = -(My_i + x Vz_i + wz x^2/2)
     Mz(x) = -(Mz_i - x Vy_i - wy x^2/2)

 En x = L eso tiene que devolver f_j, que OpenSees calculo por su
 lado. Es la AUTOVERIFICACION: si algun elemento de algun caso no
 cierra dentro de lo que explica el redondeo del servidor, no se
 escribe nada. Ver cociente_de_cierre().

 Una barra sin carga repartida tiene diagramas lineales y basta con
 sus dos extremos; con carga, el momento es una parabola y se
 muestrea en nueve puntos.

 ----------------------------------------------------------------
 TRAZABILIDAD
 ----------------------------------------------------------------
 Cada elemento lleva su 'tag_opensees' -- la linea element con los
 E, G e inercias EN EL ORDEN en que el servidor se los pasa a
 OpenSees -- y su 'objeto_unity', el nombre que le pone
 VisorEstructura.Redibujar. Asi se sigue un id desde el plano hasta
 el panel sin adivinar nada.

 Los nombres de las claves son el contrato con VisorSemana04.cs:
 JsonUtility ignora EN SILENCIO lo que no calza.
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
_RAIZ = os.path.dirname(_AQUI)
sys.path.insert(0, os.path.join(_RAIZ, 'comun'))
sys.path.insert(0, os.path.join(_RAIZ, 'semana03'))

import capacidad                             # noqa: E402
import contrato                              # noqa: E402
import demanda_capacidad as dc               # noqa: E402
import lab_semana03 as lab                   # noqa: E402
import parametros                            # noqa: E402
import rutas                                 # noqa: E402

SALIDA = os.path.join(rutas.UNITY, 'semana04.json')
STREAMING = os.path.join(rutas.STREAMING, 'semana04.json')

CASOS_BASE = ('G', 'Q', 'EX', 'EY')
N_ESTACIONES_CARGADA = 9

# El servidor redondea las fuerzas a 4 decimales (extraer_resultados):
# cada valor de f puede estar corrido hasta 5e-5 de lo que calculo
# OpenSees. Es la unica fuente de desacuerdo entre esfuerzo(L) y f_j.
COTA_REDONDEO = 5e-5

# Los mismos decimales que el servidor: escribir mas seria inventar
# precision que no existe.
DECIMALES_FUERZA = 4
DECIMALES_ESTACION = 4
DECIMALES_DESPLAZAMIENTO = 8

ORIGEN_RESULTADOS = ('lab_semana03.resolver() en memoria, mismos parametros '
                     'que reports/semana03.md')

CONVENCION = [
    'f = eleResponse(tag, localForce): [N,Vy,Vz,T,My,Mz] en i y en j, fuerzas '
    'SOBRE el elemento en ejes locales',
    'w = (wx, wy, wz) carga uniforme en ejes locales (eleLoad -beamUniform)',
    'N(x) = -(N_i + wx x), traccion positiva',
    'Vy(x) = -(Vy_i + wy x);  Vz(x) = -(Vz_i + wz x);  T(x) = -T_i',
    'My(x) = -(My_i + x Vz_i + wz x^2/2);  Mz(x) = -(Mz_i - x Vy_i - wy x^2/2)',
    'en x = L cada esfuerzo devuelve f_j, a la cota de redondeo del servidor',
    'viga simplemente apoyada con wz < 0: My < 0 en el tramo',
    'dibujo del lado traccionado: My en +My*z_local, Mz en -Mz*y_local',
    'Vz en +Vz*z_local, Vy en +Vy*y_local, N y T en +valor*z_local',
    'demanda: P positivo en compresion; columna M = hypot(My, Mz); '
    'muro M = |My| o |Mz|, el de su plano (elemento.momento_en_el_plano)',
]


# ============================================================
# ESFUERZOS INTERNOS
# ============================================================
def estaciones(L, cargada):
    """Donde se evalua la barra: 9 puntos si hay carga repartida (el
    momento es una parabola), los dos extremos si no (es lineal)."""
    L = float(L)
    if not cargada:
        return [0.0, L]
    n = N_ESTACIONES_CARGADA - 1
    return [L * i / n for i in range(n + 1)]


def esfuerzos_internos(f, w, xs):
    """
    Los esfuerzos internos en cada x, por equilibrio del trozo [0, x]
    con las fuerzas del extremo i y la carga uniforme w = (wx, wy, wz).
    Ver el encabezado para las formulas y su convencion de signos.
    """
    Ni, Vyi, Vzi, Ti, Myi, Mzi = [float(v) for v in f[:6]]
    wx, wy, wz = [float(v) for v in w]
    salida = {'N': [], 'Vy': [], 'Vz': [], 'T': [], 'My': [], 'Mz': []}
    for x in xs:
        x = float(x)
        salida['N'].append(-(Ni + wx * x))
        salida['Vy'].append(-(Vyi + wy * x))
        salida['Vz'].append(-(Vzi + wz * x))
        salida['T'].append(-Ti)
        salida['My'].append(-(Myi + x * Vzi + wz * x * x / 2.0))
        salida['Mz'].append(-(Mzi - x * Vyi - wy * x * x / 2.0))
    return salida


def cargas_por_elemento(caso):
    """{id: (wx, wy, wz)} con las distribuidas del caso. Si un elemento
    trae mas de una entrada se suman: OpenSees las aplica todas."""
    salida = {}
    for c in caso.get('cargas_distribuidas', []):
        t = int(c['elemento'])
        wx, wy, wz = salida.get(t, (0.0, 0.0, 0.0))
        salida[t] = (wx + float(c.get('wx', 0.0)),
                     wy + float(c.get('wy', 0.0)),
                     wz + float(c.get('wz', 0.0)))
    return salida


def magnitudes_de_cierre(f, w, L):
    """
    El tamano de los terminos que entran a esfuerzo(L) - f_j, por
    componente: |f_i| + |f_j| + lo que aporta la carga y, en los
    momentos, x*V_i. Sirve para acotar el error de coma flotante.
    """
    f = [abs(float(v)) for v in f]
    wx, wy, wz = [abs(float(v)) for v in w]
    return [f[0] + f[6] + wx * L,
            f[1] + f[7] + wy * L,
            f[2] + f[8] + wz * L,
            f[3] + f[9],
            f[4] + f[10] + L * f[2] + wz * L * L / 2.0,
            f[5] + f[11] + L * f[1] + wy * L * L / 2.0]


# Cada numero decimal redondeado que no es representable en binario, y
# cada suma o producto de la formula y de la combinacion, se corre a lo
# mas eps/2 de su tamano. Hay menos de ocho de esos por componente, asi
# que 4 eps por la magnitud acota esa parte. Se midio en el conjunto: el
# elemento 100103 bajo G cierra Vz con error 1e-4 + 3.3e-15, justo el
# redondeo mas la representacion binaria de 35.4688, que no es exacta.
FACTOR_COMA_FLOTANTE = 4.0 * sys.float_info.epsilon


def cota_de_cierre(L, suma_lambdas, magnitudes=None):
    """
    Cuanto puede discrepar esfuerzo(L) de f_j sin que nadie se haya
    equivocado, por componente [N, Vy, Vz, T, My, Mz].

    Lo que manda es el redondeo del servidor: N, V y T mezclan dos
    valores redondeados (el de i y el de j); My y Mz ademas llevan
    x*V_i, que multiplica su redondeo por L. En una combinacion cada
    caso aporta el suyo escalado por su lambda.

    Encima, si se da la magnitud de los terminos (sumada por caso con
    |lambda|), la coma flotante: del orden de 1e-14 contra 1e-4, no
    esconde nada, pero sin ella un error de EXACTAMENTE dos redondeos
    marca 1.000000000003 y detiene la exportacion.
    """
    corto = COTA_REDONDEO * 2.0 * suma_lambdas
    largo = COTA_REDONDEO * (2.0 + L) * suma_lambdas
    cotas = [corto, corto, corto, corto, largo, largo]
    if magnitudes is not None:
        cotas = [c + FACTOR_COMA_FLOTANTE * m for c, m in zip(cotas, magnitudes)]
    return cotas


def cociente_de_cierre(f, w, L, suma_lambdas, magnitudes=None):
    """(peor error/cota, componente) de un elemento en x = L."""
    en_L = esfuerzos_internos(f, w, [L])
    cotas = cota_de_cierre(L, suma_lambdas, magnitudes)
    peor = (0.0, 'N')
    for k, nombre in enumerate(('N', 'Vy', 'Vz', 'T', 'My', 'Mz')):
        error = abs(en_L[nombre][0] - float(f[6 + k]))
        c = error / cotas[k] if cotas[k] > 0 else (0.0 if error == 0 else math.inf)
        if c > peor[0]:
            peor = (c, nombre)
    return peor


# ============================================================
# LO QUE EL SERVIDOR LE PASA A OPENSEES
# ============================================================
def restricciones_como_el_servidor(modelo):
    """
    {nodo: [ux,uy,uz,rx,ry,rz]} de los nodos que el servidor fija. Es la
    regla de comun/servidor_opensees.py construir_modelo, lineas 245-264
    (lista a medida, o 'fijo' sin lista = empotrado) y 419-429 (los GDL
    fuera del plano del maestro de un diafragma, si nadie los fijo).
    Replicada y no importada porque alli vive en linea, junto a ops.fix.
    """
    restr = {}
    for nd in modelo['nodos']:
        r = nd.get('restricciones') or None
        if r is None:
            r = [1, 1, 1, 1, 1, 1] if nd.get('fijo', False) else None
        if r is not None and any(int(v) for v in r):
            restr[int(nd['id'])] = [int(v) for v in r]
    for d in modelo.get('diafragmas', []):
        m = int(d['nodo_maestro'])
        if m not in restr:
            restr[m] = {3: [0, 0, 1, 1, 1, 0], 2: [0, 1, 0, 1, 0, 1],
                        1: [1, 0, 0, 0, 1, 1]}[int(d.get('perpendicular', 3))]
    return restr


def rigidez_como_el_servidor(e, seccion, pi, pj, material):
    """
    E, G, vecxz e inercias de UN elemento tal como los recibe
    ops.element en comun/servidor_opensees.py construir_modelo:

      lineas 226-230  material global: Ec = 4700 sqrt(f'c) 1000 kPa,
                      Gc = Ec / (2 (1 + nu))
      lineas 302-329  vertical por geometria (proyeccion horizontal / L
                      < 1e-6); vecxz propio o (1,0,0) vertical, (0,0,1) no
      lineas 343-347  inercias cruzadas SOLO si no es vertical
      lineas 361-363  E y G de la seccion si los trae; sin G, nu = 0.3

    El servidor lo calcula en linea dentro del bucle, sin una funcion
    que se pueda llamar, asi que se replica aca citando las lineas.
    """
    fpc = float(material.get('fpc_MPa', 25.0))
    nu = float(material.get('poisson', 0.2))
    Ec = 4700.0 * math.sqrt(fpc) * 1000.0
    Gc = Ec / (2.0 * (1.0 + nu))

    dx, dy, dz = (pj[0] - pi[0], pj[1] - pi[1], pj[2] - pi[2])
    L = math.sqrt(dx * dx + dy * dy + dz * dz)
    vertical = (math.sqrt(dx * dx + dy * dy) / L) < 1e-6
    vecxz = e.get('vecxz') or None
    if vecxz is not None:
        vecxz = (float(vecxz[0]), float(vecxz[1]), float(vecxz[2]))
    else:
        vecxz = (1.0, 0.0, 0.0) if vertical else (0.0, 0.0, 1.0)

    Iy, Iz = float(seccion['Iy']), float(seccion['Iz'])
    Iy_pasa, Iz_pasa = (Iy, Iz) if vertical else (Iz, Iy)

    propio = bool(seccion.get('E'))
    E = float(seccion['E']) if propio else Ec
    if seccion.get('G'):
        G = float(seccion['G'])
    else:
        G = Gc if not propio else E / (2.0 * (1.0 + 0.3))
    return {'E': E, 'G': G, 'poisson': E / (2.0 * G) - 1.0,
            'fpc_MPa': 0.0 if propio else fpc, 'propio': propio,
            'vertical': vertical, 'vecxz': vecxz, 'L': L,
            'Iy_pasa': Iy_pasa, 'Iz_pasa': Iz_pasa}


def _texto_vecxz(v):
    return '(%s)' % ','.join('%g' % c for c in v)


def _texto_restr(r):
    return '[%s]' % ' '.join(str(v) for v in r)


# ============================================================
# FAMILIAS P-M
# ============================================================
def _fuente(fe):
    fu = fe.get('fuente') or {}
    partes = []
    if fu.get('lamina'):
        partes.append('lamina %s' % fu['lamina'])
    if fu.get('elevacion'):
        partes.append(str(fu['elevacion']))
    if fu.get('eje'):
        partes.append('eje %s' % fu['eje'])
    return ', '.join(partes) or '(sin fuente declarada)'


def _refuerzo(e, sec):
    fe = e.get('enfierradura') or {}
    if fe.get('tipo') == 'muro':
        mv = (fe.get('malla_vertical') or {}).get('texto') or '-'
        return ('malla vertical %s en %d capas + %d barras de borde (%d barras)'
                % (mv, int(fe.get('capas', 2)), len(fe.get('barras_de_borde') or []),
                   len(sec.barras)))
    lon = fe.get('longitudinal') or {}
    return ('%d D%g (%s por cara), estribo %s'
            % (len(sec.barras), float(lon.get('diametro_mm', 0.0)),
               lon.get('por_cara', '?'), (sec.estribo or {}).get('texto', '-')))


def _clave_legible(firma):
    seccion, b, h, n, As, estribo, malla = firma
    return ('%s | %.2f x %.2f m | %d barras | As = %.2f cm2 | estribo %s | malla %s'
            % (seccion, b, h, n, As * 1e4, estribo or '-', malla or '-'))


def bloque_familias(modelo):
    """
    Una curva por familia de enfierradura, en orden de aparicion por id.
    Agrupa con demanda_capacidad.firma_de_seccion, la misma clave que usa
    el informe (--todas): dos elementos con la misma firma comparten curva.
    """
    con_fierro = sorted((e for e in modelo['elementos'] if e.get('enfierradura')),
                        key=lambda e: int(e['id']))
    familias, indice_de, familia_de, secciones, curvas = [], {}, {}, {}, {}
    for e in con_fierro:
        eid = int(e['id'])
        sec = capacidad.desde_elemento(modelo, eid)
        secciones[eid] = sec
        firma = dc.firma_de_seccion(e, sec)
        if firma not in indice_de:
            i = len(familias)
            indice_de[firma] = i
            puntos = capacidad.interaccion(sec)
            curvas[i] = puntos
            familias.append({
                'indice': i,
                'clave': _clave_legible(firma),
                'tipo': e.get('tipo', ''),
                'seccion': e.get('seccion', ''),
                'b': round(sec.b, 4),
                'h': round(sec.h, 4),
                'As_cm2': round(sec.As * 1e4, 4),
                'cuantia_pct': round(100.0 * sec.cuantia, 4),
                'refuerzo': _refuerzo(e, sec),
                'fuente': _fuente(e['enfierradura']),
                'P': [round(float(p['P_kN']), DECIMALES_FUERZA) for p in puntos],
                'Mn': [round(float(p['M_kNm']), DECIMALES_FUERZA) for p in puntos],
                'Mmax': [round(float(p.get('M_max_kNm', 0.0)), DECIMALES_FUERZA)
                         for p in puntos],
                'de': [str(p.get('de', '')) for p in puntos],
                'elementos': [],
            })
        familia_de[eid] = indice_de[firma]
        familias[indice_de[firma]]['elementos'].append(eid)
    return familias, familia_de, secciones, curvas


# ============================================================
# ELEMENTOS
# ============================================================
def bloque_elementos(modelo, cargas, familia_de):
    """Lo fijo de cada elemento: ids, seccion, material, ejes, apoyos."""
    nodos = {int(n['id']): (float(n['x']), float(n['y']), float(n['z']))
             for n in modelo['nodos']}
    secciones = {s['nombre']: s for s in modelo['secciones']}
    material = modelo.get('material', {})
    restr = restricciones_como_el_servidor(modelo)
    de_nodo = lab.indice_de_diafragma(modelo)
    maestros = [int(d['nodo_maestro']) for d in modelo.get('diafragmas', [])]

    def maestro_de(n):
        i = de_nodo.get(n)
        return maestros[i] if i is not None else -1

    salida = []
    for e in sorted(modelo['elementos'], key=lambda e: int(e['id'])):
        eid, n1, n2 = int(e['id']), int(e['n1']), int(e['n2'])
        tipo = e.get('tipo', '')
        s = secciones[e['seccion']]
        k = rigidez_como_el_servidor(e, s, nodos[n1], nodos[n2], material)

        if k['propio']:
            texto_mat = 'E y G propios de la seccion'
            if s.get('E_del_cuerpo'):
                texto_mat += ' (cuerpo %s)' % s['E_del_cuerpo']
        else:
            texto_mat = "hormigon f'c %g MPa, Ec = 4700 sqrt(f'c)" % k['fpc_MPa']

        es_brazo = tipo in ('brazo', 'brazo_rigido')
        r1, r2 = restr.get(n1, [0] * 6), restr.get(n2, [0] * 6)
        d1, d2 = maestro_de(n1), maestro_de(n2)
        condiciones = []
        for nombre, n, r, d in (('n1', n1, r1, d1), ('n2', n2, r2, d2)):
            if any(r):
                condiciones.append('%s %d: %s %s' % (
                    nombre, n, 'empotrado' if all(r) else 'apoyo', _texto_restr(r)))
            if d >= 0:
                condiciones.append('%s %d: diafragma rigido, maestro %d' % (nombre, n, d))
        if es_brazo:
            condiciones.append('brazo rigido: barra de rigidez x100 hasta la cara del muro')
        if not condiciones:
            condiciones.append('nodos libres: sin apoyo ni diafragma')

        cargada = any(any(v != 0.0 for v in cargas[c].get(eid, (0.0, 0.0, 0.0)))
                      for c in ('G', 'Q'))

        salida.append({
            'id': eid, 'n1': n1, 'n2': n2,
            'tipo': tipo, 'seccion': e['seccion'],
            # El momento que se compara con la curva: el de inercia mayor.
            'momento_en_el_plano': (dc.momento_en_el_plano(s['Iy'], s['Iz'])
                                    if tipo == 'muro' else ''),
            'L': round(k['L'], DECIMALES_ESTACION),
            'objeto_unity': 'Elem_%d_%s' % (eid, tipo),
            'tag_opensees': ('element elasticBeamColumn %d %d %d A=%.4f E=%.4e '
                             'G=%.4e J=%.3e Iy=%.3e Iz=%.3e vecxz=%s'
                             % (eid, n1, n2, float(s['A']), k['E'], k['G'],
                                float(s['J']), k['Iy_pasa'], k['Iz_pasa'],
                                _texto_vecxz(k['vecxz']))),
            'material': texto_mat,
            'fpc_MPa': k['fpc_MPa'],
            'E_kPa': round(k['E'], 4), 'G_kPa': round(k['G'], 4),
            'poisson': round(k['poisson'], 6),
            'gamma': float(s.get('gamma', material.get('gamma', 25.0))),
            'A': float(s['A']), 'Iy': float(s['Iy']), 'Iz': float(s['Iz']),
            'J': float(s['J']),
            # Los muros de Ingenieria declaran largo/espesor en vez de h/b.
            'b': float(s.get('b') or s.get('espesor') or 0.0),
            'h': float(s.get('h') or s.get('largo') or 0.0),
            'vecxz': list(k['vecxz']),
            'restr_n1': r1, 'restr_n2': r2,
            'diafragma_n1': d1, 'diafragma_n2': d2,
            'es_brazo_rigido': es_brazo,
            'condiciones': '; '.join(condiciones),
            'cargada': cargada,
            'familia': familia_de.get(eid, -1),
            'resultados': ORIGEN_RESULTADOS,
        })
    return salida


# ============================================================
# CASOS Y COMBINACIONES
# ============================================================
def lista_de_combinaciones(p):
    """
    Los casos base y despues las combinaciones de parametros.json, en su
    orden. Si la combinacion activa no esta entre ellas (--comb a mano)
    se agrega al final: el caso por defecto tiene que existir en el anexo.
    """
    salida = [(c, 'caso', None, {k: (1.0 if k == c else 0.0) for k in CASOS_BASE})
              for c in CASOS_BASE]
    nombres = set(CASOS_BASE)
    for combo in list(p['combinaciones']) + [p['combinacion']]:
        if combo['nombre'] in nombres:
            continue
        nombres.add(combo['nombre'])
        salida.append((combo['nombre'], 'combinacion', parametros.como_texto(combo),
                       parametros.factores(combo)))
    return salida


def bloque_caso(nombre, tipo, descripcion, factores, resultados, elementos,
                cargas_base, familias_de, curvas, largos):
    """
    Un caso o una combinacion: desplazamientos, esfuerzos y demandas.
    La combinacion se arma con demanda_capacidad.combinar -- la suma
    lineal que ya usa el informe -- sobre f, desplazamientos y w.
    Devuelve (bloque, cargas combinadas, peor cierre (cociente, id, comp)).
    """
    activos = {c: l for c, l in factores.items() if l != 0.0}
    suma_lambdas = sum(abs(l) for l in activos.values())

    # --- desplazamientos ---
    por_nodo = {}
    for c in activos:
        for d in resultados[c]['desplazamientos']:
            por_nodo.setdefault(int(d['id']), {})[c] = [
                float(d[k]) for k in ('ux', 'uy', 'uz', 'rx', 'ry', 'rz')]
    desplazamientos, maximo = [], 0.0
    for nid in sorted(por_nodo):
        u = dc.combinar(por_nodo[nid], activos)
        maximo = max(maximo, math.sqrt(u[0] ** 2 + u[1] ** 2 + u[2] ** 2))
        desplazamientos.append(dict(
            [('id', nid)] + [(k, round(v, DECIMALES_DESPLAZAMIENTO))
                             for k, v in zip(('ux', 'uy', 'uz', 'rx', 'ry', 'rz'), u)]))

    # --- cargas repartidas combinadas ---
    cargas = {}
    for c, l in activos.items():
        for eid, w in cargas_base[c].items():
            cargas.setdefault(eid, {})[c] = list(w)
    cargas = {eid: tuple(dc.combinar(por_caso, activos)) for eid, por_caso in cargas.items()}

    # --- esfuerzos y demandas ---
    fuerzas = {c: {int(x['id']): x['f'] for x in resultados[c]['fuerzas_elementos']}
               for c in activos}
    esfuerzos, demandas = [], []
    peor = (0.0, -1, 'N')
    for e in elementos:
        eid = e['id']
        f = dc.combinar({c: [float(v) for v in fuerzas[c][eid]] for c in activos}, activos)
        w = cargas.get(eid, (0.0, 0.0, 0.0))
        L = largos[eid]
        xs = estaciones(L, any(v != 0.0 for v in w))
        internos = esfuerzos_internos(f, w, xs)

        magnitudes = [0.0] * 6
        for c, l in activos.items():
            m_c = magnitudes_de_cierre(fuerzas[c][eid],
                                       cargas_base[c].get(eid, (0.0, 0.0, 0.0)), L)
            magnitudes = [a + abs(l) * b for a, b in zip(magnitudes, m_c)]
        cociente, comp = cociente_de_cierre(f, w, L, suma_lambdas, magnitudes)
        if cociente > peor[0]:
            peor = (cociente, eid, comp)

        fila = {'id': eid,
                'f': [round(v, DECIMALES_FUERZA) for v in f],
                'x': [round(x, DECIMALES_ESTACION) for x in xs]}
        for k in ('N', 'Vy', 'Vz', 'T', 'My', 'Mz'):
            fila[k] = [round(v, DECIMALES_FUERZA) for v in internos[k]]
        esfuerzos.append(fila)

        fam = familias_de.get(eid, -1)
        if fam >= 0:
            d = dc.demanda(f, e['tipo'], e['momento_en_el_plano'] or None)
            Mn = dc.capacidad_en(d['P_kN'], curvas[fam])
            # El mismo umbral que demanda_capacidad.revisar.
            u = d['M_kNm'] / Mn if Mn > 1e-9 else 9999.0
            demandas.append({
                'id': eid, 'familia': fam,
                'P': round(d['P_kN'], DECIMALES_FUERZA),
                'M': round(d['M_kNm'], DECIMALES_FUERZA),
                'M_fuera_plano': round(d['M_fuera_de_plano_kNm'] or 0.0, DECIMALES_FUERZA),
                'extremo': d['extremo'],
                'Mn': round(Mn, DECIMALES_FUERZA),
                'u': round(u, 6),
                'pasa': u <= 1.0,
            })

    bloque = {
        'nombre': nombre,
        'tipo': tipo,
        'descripcion': descripcion,
        'factores': [factores[c] for c in CASOS_BASE],
        'max_desplazamiento_mm': round(maximo * 1000.0, 4),
        'desplazamientos': desplazamientos,
        'esfuerzos': esfuerzos,
        'demandas': demandas,
    }
    return bloque, cargas, peor


# ============================================================
def construir_anexo(edificio, argv=()):
    """
    El anexo completo en memoria, sin escribir nada. Devuelve
    (anexo, contexto); el contexto trae lo intermedio para que las
    verificaciones no tengan que rehacerlo.
    """
    p = parametros.cargar(list(argv))
    modelo = contrato.cargar_modelo(edificio)
    arm = lab.armar_casos(modelo, p)
    datos, resultados = lab.resolver(modelo, arm['casos'])

    cargas_base = {c: cargas_por_elemento(arm['casos'][c]) for c in CASOS_BASE}
    familias, familia_de, secciones, curvas = bloque_familias(modelo)
    elementos = bloque_elementos(modelo, cargas_base, familia_de)

    nodos = {int(n['id']): n for n in modelo['nodos']}
    por_id = {int(e['id']): e for e in modelo['elementos']}
    largos = {eid: lab.largo(e, nodos) for eid, e in por_id.items()}

    casos, cargas, combinaciones, cierre = [], {}, [], {}
    for nombre, tipo, texto, factores in lista_de_combinaciones(p):
        descripcion = texto if texto is not None else \
            arm['casos'][nombre].get('descripcion', '')
        bloque, w, peor = bloque_caso(nombre, tipo, descripcion, factores, resultados,
                                      elementos, cargas_base, familia_de, curvas, largos)
        casos.append(bloque)
        cargas[nombre] = w
        cierre[nombre] = peor
        if tipo == 'combinacion':
            combinaciones.append((nombre, factores))

    # Las demo: las del informe de semana 3, elegidas por regla y no a mano.
    axial_G = {int(x['id']): abs(float(x['f'][0]))
               for x in resultados['G']['fuerzas_elementos']}
    columnas = [eid for eid in secciones if por_id[eid].get('tipo') == 'columna']
    muros = [eid for eid in secciones if por_id[eid].get('tipo') == 'muro']
    columna_demo = max(sorted(columnas), key=lambda i: axial_G.get(i, 0.0), default=-1)
    muro_demo = max(sorted(muros), key=lambda i: secciones[i].h, default=-1)

    anexo = {
        'info': {
            'edificio': edificio,
            'descripcion': 'Anexo de Semana 4 para el visor: esfuerzos internos por '
                           'caso y combinacion, datos OpenSees de cada elemento y '
                           'demanda-capacidad P-M',
            'unidades': 'm, kN, kPa; momentos kN*m; desplazamientos m y rad',
            'parametros': [l.strip() for l in parametros.describir(p).split('\n')],
            'convencion': CONVENCION,
            'generado_por': 'semana04/exportar_unity.py',
            'caso_por_defecto': p['combinacion']['nombre'],
            'columna_demo': columna_demo,
            'muro_demo': muro_demo,
            'n_estaciones_cargada': N_ESTACIONES_CARGADA,
            'cota_redondeo_kN': COTA_REDONDEO,
        },
        'casos': casos,
        'elementos': elementos,
        'familias': familias,
    }
    contexto = {
        'modelo': modelo, 'p': p, 'arm': arm, 'datos': datos,
        'resultados': resultados, 'combinaciones': combinaciones,
        'cargas': cargas, 'secciones': secciones, 'curvas': curvas,
        'cierre': cierre,
    }
    return anexo, contexto


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    edificio = 'ingenieria'
    if argv and not argv[0].startswith('-'):
        edificio = argv.pop(0)

    t0 = time.time()
    anexo, ctx = construir_anexo(edificio, argv)
    t_calculo = time.time() - t0
    info = anexo['info']

    print('=' * 72)
    print('  ANEXO DE SEMANA 4 PARA UNITY   %s' % edificio.upper())
    print('=' * 72)
    print(parametros.describir(ctx['p']))
    print()
    n_base = sum(1 for c in anexo['casos'] if c['tipo'] == 'caso')
    print('  casos      %d (%d base + %d combinaciones): %s'
          % (len(anexo['casos']), n_base, len(anexo['casos']) - n_base,
             ', '.join(c['nombre'] for c in anexo['casos'])))
    print('  elementos  %d, %d con carga repartida en G o Q'
          % (len(anexo['elementos']), sum(1 for e in anexo['elementos'] if e['cargada'])))
    print('  familias   %d curvas P-M para %d elementos con enfierradura'
          % (len(anexo['familias']), len(ctx['secciones'])))

    defecto = next(c for c in anexo['casos'] if c['nombre'] == info['caso_por_defecto'])
    demandas = {d['id']: d for d in defecto['demandas']}
    for etiqueta, eid in (('columna', info['columna_demo']), ('muro', info['muro_demo'])):
        d = demandas.get(eid)
        if d is None:
            print('  %-8s   (ninguna con enfierradura)' % etiqueta)
            continue
        fam = anexo['familias'][d['familia']]
        print('  %-8s   %d  familia %d (%s), en %s: P = %.1f kN, M = %.1f kN m, '
              'Mn = %.1f, u = %.3f %s'
              % (etiqueta + '_demo', eid, d['familia'], fam['seccion'],
                 defecto['nombre'], d['P'], d['M'], d['Mn'], d['u'],
                 'ok' if d['pasa'] else 'NO PASA'))

    print()
    print('  autoverificacion: esfuerzo(L) contra f_j de OpenSees, error / cota')
    print('  (cota = 5e-5 (2 + L) en My, Mz y 5e-5 * 2 en N, V, T, por sum|lambda|,')
    print('   + 4 eps por el tamano de los terminos: la coma flotante)')
    malos = []
    for c in anexo['casos']:
        cociente, eid, comp = ctx['cierre'][c['nombre']]
        print('    %-18s peor %.3f   elemento %5d, %s   %s'
              % (c['nombre'], cociente, eid, comp, 'ok' if cociente <= 1.0 else '<-- NO CIERRA'))
        if cociente > 1.0:
            malos.append(c['nombre'])
    if malos:
        print()
        print('  NO SE ESCRIBE NADA: %s no cierran con OpenSees' % ', '.join(malos))
        return 1

    texto = json.dumps(anexo, separators=(',', ':'), ensure_ascii=False)
    rutas.asegurar(SALIDA)
    with io.open(SALIDA, 'w', encoding='utf-8') as f:
        f.write(texto)
    copiado = os.path.isdir(os.path.dirname(STREAMING))
    if copiado:
        shutil.copy2(SALIDA, STREAMING)

    print()
    print('  %.2f MB, calculado en %.1f s'
          % (os.path.getsize(SALIDA) / 1048576.0, t_calculo))
    print('  -> %s' % os.path.relpath(SALIDA, rutas.RAIZ))
    if copiado:
        print('  -> %s' % os.path.relpath(STREAMING, rutas.RAIZ))
    return 0


if __name__ == '__main__':
    sys.exit(main())
