# -*- coding: utf-8 -*-
r"""
================================================================
 semana05/verificar_superposicion.py  -  E1..E3 CONTRA OPENSEES
================================================================
 Para cada estado de semana05/estados_s5.json (E1 = 1.0G+1.0Q,
 E2 = 1.2G+1.6Q, E3 = 1.2G+1.0Q-1.4EX) pone lado a lado cuatro vias:

   (1) la corrida EXPLICITA: combinar.resolver_explicito, OpenSees con
       la carga combinada. Es la referencia.
   (2) superposicion.caso_combinado: la suma lineal de los casos base,
       la que usa el servidor.
   (3) POST /combinar de servidor_s5.py, por app.test_client() (sin
       red): lo que recibe Unity con servidor.
   (4) data/unity/superposicion_<ed>.json: lo que lee Unity sin
       servidor (exe).

 y compara, en TODO el modelo:

   - los 6 GDL de todos los nodos y el desplazamiento maximo
   - las 12 fuerzas localForce de todas las barras
   - las estaciones N, Vy, Vz, T, My, Mz de todas las barras contra
     exportar_unity.esfuerzos_internos con la f EXPLICITA y la carga
     combinada por otro camino (combinar.combinar_cargas)
   - las reacciones de todos los apoyos y el equilibrio con
     calcular.equilibrio, la unica suma de reacciones valida
   - la demanda-capacidad (P, M, M fuera de plano, extremo, Mn, u, pasa)
     de las barras con fierro contra demanda_capacidad.demanda +
     capacidad_en sobre la f explicita, y contra
     demanda_capacidad.revisar(..., lambdas)

 Ademas: (3) y (4) tienen que ser IDENTICAS a (2) bit a bit (mismo
 calculo, solo viajan por JSON), y E2 identico al caso '1.2G+1.6Q' del
 anexo de la Semana 4. Los elementos de control (columna, muro, viga,
 nodo) quedan con sus numeros en la evidencia para compararlos con lo
 que muestra Unity.

 Correr:
   python semana05/verificar_superposicion.py lt2
   python semana05/verificar_superposicion.py ingenieria
   python semana05/verificar_superposicion.py lt2 --cs 0.20   (flags de parametros.py)

 Escribe SOLO semana05/evidencia/:
   superposicion_<ed>.json          todo: cotas, cocientes, identidades,
                                    equilibrio y control por estado
   superposicion_<ed>.csv           la tabla de cocientes (estado, via, familia)
   superposicion_<ed>_control.csv   los numeros de los elementos de control
                                    (columna demo, muro demo, viga, nodo y los
                                    que NO PASAN) al lado de la explicita: lo
                                    que la integracion compara con Unity
 Sale con 1 si algo no calza.

 ----------------------------------------------------------------
 LAS COTAS SE MIDEN
 ----------------------------------------------------------------
 El servidor redondea desplazamientos a 8 decimales y fuerzas a 4, y
 cada via vuelve a redondear lo que entrega. Nada de eso se supone: el
 numero de decimales se MIDE sobre los datos (combinar.decimales_de) y
 de ahi sale el medio ultimo decimal r de cada fuente:

   e_lin = r_base * sum|lambda| + r_explicita
           cada caso base esta a r de su valor real y la suma lo escala
           por su lambda; la explicita tambien viene redondeada
   cota  = e_lin + r_via + 4 eps * tamano
           + el redondeo de lo que escribe la via, + la coma flotante

 Estaciones My y Mz: e_lin (1 + x), porque x V_i multiplica por x el
 error de V_i. Demanda: P y M de muro e_lin, M de columna sqrt(2) e_lin
 (hypot de dos valores con error), Mn = pendiente del tramo de la
 curva * e_lin, u = (dM + u dMn) / (Mn - dMn). Si el extremo que manda
 o el pasa/no pasa quedan dentro de la cota, se informan como
 INDECIDIBLES POR REDONDEO, no como falla.
================================================================
"""
from __future__ import annotations

import csv
import filecmp
import io
import json
import math
import os
import sys
import time

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_AQUI), 'comun'))
import rutas                                 # noqa: E402
rutas.entrar(__file__, os.path.join(rutas.RAIZ, 'semana04'),
             os.path.join(rutas.RAIZ, 'semana03'))

import superposicion as sp                   # noqa: E402  (carga el exportador por ruta)
import calcular                              # noqa: E402
import capacidad                             # noqa: E402
import combinar                              # noqa: E402
import demanda_capacidad as dc               # noqa: E402
import trazabilidad                          # noqa: E402

eu = sp.eu
CASOS = sp.CASOS
CAMPOS_U = combinar.CAMPOS['desplazamientos']
CAMPOS_R = combinar.CAMPOS['reacciones']
COMP = ('N', 'Vy', 'Vz', 'T', 'My', 'Mz')
FP = eu.FACTOR_COMA_FLOTANTE
U_FUERA = 9999.0
EVIDENCIA = os.path.join(_AQUI, 'evidencia')

VIAS = {
    '1': 'combinar.resolver_explicito (OpenSees con la carga combinada, la referencia)',
    '2': 'superposicion.caso_combinado (suma lineal de los casos base)',
    '3': 'POST /combinar de servidor_s5.py por app.test_client()',
    '4': 'data/unity/superposicion_<ed>.json (precalculado, exe sin servidor)',
}

FAMILIAS = ('desplazamientos', 'max_desplazamiento_mm', 'fuerzas f', 'estaciones x',
            'estaciones N..Mz', 'D/C P', 'D/C M', 'D/C M fuera de plano', 'D/C Mn',
            'D/C u', 'D/C = dc.revisar')

# Por que dos familias quedan en 1.000 o casi, y no es un aviso: en las
# dos la unica diferencia posible es el redondeo con que la via ESCRIBE,
# y un valor que cae justo en el medio de dos decimales la alcanza entera.
NOTAS_COCIENTES = [
    'estaciones x = 1.000: una estacion k L / 8 puede tener un decimal mas de los que el anexo '
    'escribe; si ese decimal es un 5, el error es exactamente el medio ultimo decimal. Es el '
    'redondeo mismo, no un desvio (el caso concreto se imprime abajo).',
    'D/C = dc.revisar ~ 0.99: dc.revisar arma el mismo punto con las mismas fuerzas base, asi '
    'que solo difiere el redondeo de salida (u a 6 decimales, P, M y Mn a 4); entre todos los '
    'elementos con fierro por 5 campos siempre hay uno pegado al medio decimal.',
]


def detalle_de_x(b, donde):
    """'elemento 355 x[4]' -> el largo, la x exacta y la escrita, para la nota."""
    partes = (donde or '').split()
    if len(partes) != 3 or partes[0] != 'elemento' or not partes[2].startswith('x['):
        return None
    eid, i = int(partes[1]), int(partes[2][2:-1])
    L = b['largos'][eid]
    xs = eu.estaciones(L, True)
    if i >= len(xs):
        xs = eu.estaciones(L, False)
    x = xs[i]
    return ('elemento %d: L = %.10g m, x[%d] = %.10g exacta, escrita %r; error %.3e'
            % (eid, L, i, x, round(x, eu.DECIMALES_ESTACION),
               abs(round(x, eu.DECIMALES_ESTACION) - x)))


# ============================================================
# UTILIDADES
# ============================================================
class Informe(object):
    """Junta lo que no calza y lo pendiente; cada comprobacion imprime una linea."""

    def __init__(self):
        self.fallas = []
        self.pendientes = []

    def check(self, ok, que, detalle=()):
        print('  [%s] %s' % ('OK  ' if ok else 'FALLA', que))
        for linea in ([detalle] if isinstance(detalle, str) else detalle):
            if linea:
                print('         %s' % linea)
        if not ok:
            self.fallas.append(que)
        return ok

    def pendiente(self, que):
        print('  [PEND] %s' % que)
        self.pendientes.append(que)


class Peor(object):
    """El peor error/cota de una familia de valores, y donde fue."""

    def __init__(self):
        self.n = 0
        self.fuera = 0
        self.cociente = 0.0
        self.err = 0.0
        self.cota = 0.0
        self.donde = None

    def ver(self, err, cota, donde):
        self.n += 1
        err = abs(err)
        c = err / cota if cota > 0 else (0.0 if err == 0 else math.inf)
        if c > 1.0:
            self.fuera += 1
        if self.n == 1 or c > self.cociente:
            self.cociente, self.err, self.cota, self.donde = c, err, cota, donde

    @property
    def calza(self):
        # Una familia sin valores no se aprueba por vacio.
        return self.n > 0 and self.fuera == 0

    def fila(self):
        return {'n_comparados': self.n, 'peor_abs': self.err, 'cota_en_el_peor': self.cota,
                'cociente': self.cociente, 'donde': texto_donde(self.donde),
                'fuera_de_cota': self.fuera, 'calza': self.calza}


def texto_donde(donde):
    if donde is None:
        return ''
    return ' '.join(str(x) for x in donde)


def por_id(lista):
    return {int(x['id']): x for x in lista}


def medio(valores):
    """Medio ultimo decimal MEDIDO de una familia (trazabilidad, sobre combinar.decimales_de)."""
    return trazabilidad.medio_ultimo_decimal(valores)


def r_de(resultado, clave, campos):
    """Medio ultimo decimal de una familia de un resultado del servidor."""
    d = combinar.decimales_de(resultado, clave, campos)
    return 0.5 * 10.0 ** -d if d else 0.0


def diferencias(a, b, ruta='$'):
    r"""
    (hojas comparadas, primera diferencia o None), exacto. Sirve para
    las vias que tienen que ser el MISMO calculo que (2): un float que
    viaja por json.dumps/loads vuelve bit a bit (repr de Python).
    """
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return 0, '%s: claves %s' % (ruta, sorted(set(a) ^ set(b)))
        n = 0
        for k in a:
            m, d = diferencias(a[k], b[k], '%s.%s' % (ruta, k))
            n += m
            if d:
                return n, d
        return n, None
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return 0, '%s: largo %d contra %d' % (ruta, len(a), len(b))
        n = 0
        for i, (x, y) in enumerate(zip(a, b)):
            m, d = diferencias(x, y, '%s[%d]' % (ruta, i))
            n += m
            if d:
                return n, d
        return n, None
    if type(a) is not type(b) or a != b:
        return 1, '%s: %r contra %r' % (ruta, a, b)
    return 1, None


def momentos_de_extremos(f, tipo, plano):
    r"""
    El M de cada extremo con la regla de demanda_capacidad.demanda
    (columna hypot(My, Mz), muro |M del plano|). Solo para decidir si el
    extremo que manda esta dentro del redondeo; la demanda misma la
    calcula dc.demanda.
    """
    if tipo == 'muro':
        k = 4 if plano == 'My' else 5
        return abs(f[k]), abs(f[6 + k])
    return math.hypot(f[4], f[5]), math.hypot(f[10], f[11])


def pendiente_cerca(curva, P, e):
    """Mayor |dMn/dP| de los tramos de la curva que tocan [P - e, P + e]."""
    pts = sorted(((float(p['P_kN']), float(p['M_kNm'])) for p in curva), key=lambda t: t[0])
    s = 0.0
    for (p1, m1), (p2, m2) in zip(pts, pts[1:]):
        if p2 < P - e or p1 > P + e:
            continue
        if abs(p2 - p1) < 1e-9:
            continue
        s = max(s, abs((m2 - m1) / (p2 - p1)))
    return s, pts[0][0], pts[-1][0]


def u_de(M, Mn):
    return M / Mn if Mn > 1e-9 else U_FUERA


# ============================================================
# LA REFERENCIA DE UN ESTADO
# ============================================================
def referencia(b, lam, nombre):
    r"""
    Todo lo que sale de la corrida explicita y lo que se necesita para
    las cotas. Nada de esto usa superposicion.caso_combinado.
    """
    ctx = b['ctx']
    datos, resultados = ctx['datos'], ctx['resultados']
    activos = {c: l for c, l in lam.items() if l != 0.0}
    suma = sum(abs(l) for l in activos.values())

    t = time.time()
    exp = combinar.resolver_explicito(datos, lam, nombre)
    t_exp = time.time() - t

    carga = combinar.combinar_cargas(datos, lam, nombre)
    r = {
        'exp': exp, 't': t_exp, 'activos': activos, 'suma': suma, 'carga': carga,
        'f': {int(x['id']): [float(v) for v in x['f']] for x in exp['fuerzas_elementos']},
        'u': {int(x['id']): [float(x[k]) for k in CAMPOS_U] for x in exp['desplazamientos']},
        'f_base': {c: {int(x['id']): [float(v) for v in x['f']]
                       for x in resultados[c]['fuerzas_elementos']} for c in activos},
        'u_base': {c: {int(x['id']): [float(x[k]) for k in CAMPOS_U]
                       for x in resultados[c]['desplazamientos']} for c in activos},
        # La carga repartida combinada por OTRO camino que bloque_caso.
        'w': eu.cargas_por_elemento(carga),
    }

    def e_lin(clave, campos):
        r_base = max((r_de(resultados[c], clave, campos) for c in activos), default=0.0)
        return r_base * suma + r_de(exp, clave, campos), r_base

    r['e_u'], r['r_base_u'] = e_lin('desplazamientos', CAMPOS_U)
    r['e_f'], r['r_base_f'] = e_lin('fuerzas_elementos', None)
    r['e_r'], r['r_base_r'] = e_lin('reacciones', CAMPOS_R)
    r['r_exp_r'] = r_de(exp, 'reacciones', CAMPOS_R)

    u_max = 0.0
    for nid, v in r['u'].items():
        u_max = max(u_max, math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2))
    r['max_mm'] = 1000.0 * u_max

    # Demanda-capacidad con la f explicita.
    curvas = ctx['curvas']
    r['dc'] = {}
    for e in b['anexo']['elementos']:
        fam = int(e['familia'])
        if fam < 0:
            continue
        eid = int(e['id'])
        f = r['f'][eid]
        plano = e['momento_en_el_plano'] or None
        d = dc.demanda(f, e['tipo'], plano)
        Mn = dc.capacidad_en(d['P_kN'], curvas[fam])
        Mi, Mj = momentos_de_extremos(f, e['tipo'], plano)
        r['dc'][eid] = {'d': d, 'Mn': Mn, 'u': u_de(d['M_kNm'], Mn), 'fam': fam,
                        'tipo': e['tipo'], 'plano': plano, 'Mi': Mi, 'Mj': Mj}
    return r


# ============================================================
# UNA VIA CONTRA LA REFERENCIA
# ============================================================
def comparar_via(b, lam, ref, caso):
    """{familia: Peor} y lo indecidible por redondeo."""
    peores = {k: Peor() for k in FAMILIAS if k != 'D/C = dc.revisar'}
    indecidibles = []
    activos, suma = ref['activos'], ref['suma']

    # --- desplazamientos ---
    r_u = medio(v for d in caso['desplazamientos'] for v in (d[k] for k in CAMPOS_U))
    desp = por_id(caso['desplazamientos'])
    ids_ok = set(desp) == set(ref['u'])
    for nid, v_exp in (ref['u'].items() if ids_ok else ()):
        for k, campo in enumerate(CAMPOS_U):
            mag = abs(v_exp[k]) + sum(abs(l) * abs(ref['u_base'][c][nid][k])
                                      for c, l in activos.items())
            peores['desplazamientos'].ver(float(desp[nid][campo]) - v_exp[k],
                                          ref['e_u'] + r_u + FP * mag, ('nodo', nid, campo))
    if not ids_ok:
        peores['desplazamientos'].ver(math.inf, 0.0, ('ids de nodos distintos',))

    r_mm = medio([caso['max_desplazamiento_mm']])
    peores['max_desplazamiento_mm'].ver(
        caso['max_desplazamiento_mm'] - ref['max_mm'],
        1000.0 * math.sqrt(3.0) * (ref['e_u'] + r_u) + r_mm + FP * ref['max_mm'],
        ('mm',))

    # --- fuerzas y estaciones ---
    esf = por_id(caso['esfuerzos'])
    r_f = medio(v for s in caso['esfuerzos'] for v in s['f'])
    r_est = medio(v for s in caso['esfuerzos'] for k in COMP for v in s[k])
    r_x = medio(v for s in caso['esfuerzos'] for v in s['x'])
    ids_ok = set(esf) == set(ref['f'])
    if not ids_ok:
        peores['fuerzas f'].ver(math.inf, 0.0, ('ids de barras distintos',))
    for eid, f_exp in (ref['f'].items() if ids_ok else ()):
        s = esf[eid]
        for k in range(12):
            mag = abs(f_exp[k]) + sum(abs(l) * abs(ref['f_base'][c][eid][k])
                                      for c, l in activos.items())
            peores['fuerzas f'].ver(float(s['f'][k]) - f_exp[k],
                                    ref['e_f'] + r_f + FP * mag, ('elemento', eid, 'f[%d]' % k))

        L = b['largos'][eid]
        w = ref['w'].get(eid, (0.0, 0.0, 0.0))
        xs = eu.estaciones(L, any(v != 0.0 for v in w))
        if len(xs) != len(s['x']) or any(len(s[k]) != len(xs) for k in COMP):
            peores['estaciones x'].ver(math.inf, 0.0, ('elemento', eid, 'cantidad de estaciones'))
            continue
        internos = eu.esfuerzos_internos(f_exp, w, xs)
        mags = eu.magnitudes_de_cierre(f_exp, w, L)
        for c, l in activos.items():
            m_c = eu.magnitudes_de_cierre(ref['f_base'][c][eid],
                                          b['cargas_base'][c].get(eid, (0.0, 0.0, 0.0)), L)
            mags = [a + abs(l) * m for a, m in zip(mags, m_c)]
        for i, x in enumerate(xs):
            peores['estaciones x'].ver(float(s['x'][i]) - x, r_x + FP * L,
                                       ('elemento', eid, 'x[%d]' % i))
            for k, nombre in enumerate(COMP):
                e = ref['e_f'] * (1.0 + x) if nombre in ('My', 'Mz') else ref['e_f']
                peores['estaciones N..Mz'].ver(
                    float(s[nombre][i]) - internos[nombre][i], e + r_est + FP * mags[k],
                    ('elemento', eid, '%s(x=%.4f)' % (nombre, x)))

    # --- demanda-capacidad ---
    dem = por_id(caso['demandas'])
    r_dc = medio(v for d in caso['demandas'] for v in (d['P'], d['M'], d['M_fuera_plano'], d['Mn']))
    r_uu = medio(d['u'] for d in caso['demandas'] if d['u'] < U_FUERA)
    if set(dem) != set(ref['dc']):
        peores['D/C P'].ver(math.inf, 0.0, ('ids con fierro distintos',))
    curvas = b['ctx']['curvas']
    for eid, rd in ref['dc'].items():
        v = dem.get(eid)
        if v is None:
            continue
        d, e = rd['d'], ref['e_f']
        dM = math.sqrt(2.0) * e if rd['tipo'] != 'muro' else e
        mag = FP * (1.0 + suma) * (abs(d['P_kN']) + d['M_kNm'] + rd['Mn'] + 1.0)
        if int(v['familia']) != rd['fam']:
            peores['D/C P'].ver(math.inf, 0.0, ('elemento', eid, 'familia'))
            continue
        if v['extremo'] != d['extremo']:
            if abs(rd['Mi'] - rd['Mj']) <= 2.0 * dM:
                indecidibles.append('elemento %d: extremo (M_i %.4f, M_j %.4f)'
                                    % (eid, rd['Mi'], rd['Mj']))
                continue
            peores['D/C M'].ver(math.inf, 0.0, ('elemento', eid, 'extremo'))
            continue
        peores['D/C P'].ver(v['P'] - d['P_kN'], e + r_dc + mag, ('elemento', eid, 'P'))
        peores['D/C M'].ver(v['M'] - d['M_kNm'], dM + r_dc + mag, ('elemento', eid, 'M'))
        peores['D/C M fuera de plano'].ver(
            v['M_fuera_plano'] - (d['M_fuera_de_plano_kNm'] or 0.0),
            (e if rd['tipo'] == 'muro' else 0.0) + r_dc + mag, ('elemento', eid, 'M fuera'))
        s, P_min, P_max = pendiente_cerca(curvas[rd['fam']], d['P_kN'], e)
        dMn = s * e
        peores['D/C Mn'].ver(v['Mn'] - rd['Mn'], dMn + r_dc + mag, ('elemento', eid, 'Mn'))

        cerca_del_borde = min(abs(d['P_kN'] - P_min), abs(d['P_kN'] - P_max)) <= e
        if v['u'] >= U_FUERA and rd['u'] >= U_FUERA:
            peores['D/C u'].ver(0.0, 1.0, ('elemento', eid, 'u fuera de curva'))
        elif (v['u'] >= U_FUERA) != (rd['u'] >= U_FUERA):
            if cerca_del_borde or rd['Mn'] <= dMn + 1e-9:
                indecidibles.append('elemento %d: fuera de curva (P %.4f, curva %.4f..%.4f)'
                                    % (eid, d['P_kN'], P_min, P_max))
            else:
                peores['D/C u'].ver(math.inf, 0.0, ('elemento', eid, 'u 9999 en una sola'))
        else:
            den = rd['Mn'] - dMn
            if den <= 0.0:
                indecidibles.append('elemento %d: Mn %.4f dentro de su cota' % (eid, rd['Mn']))
            else:
                cota_u = (dM + rd['u'] * dMn) / den + r_uu + FP * 4.0 * rd['u']
                peores['D/C u'].ver(v['u'] - rd['u'], cota_u, ('elemento', eid, 'u'))
                if v['pasa'] != (rd['u'] <= 1.0):
                    if abs(rd['u'] - 1.0) <= cota_u:
                        indecidibles.append('elemento %d: pasa con u = %.6f' % (eid, rd['u']))
                    else:
                        peores['D/C u'].ver(math.inf, 0.0, ('elemento', eid, 'pasa'))
    return peores, indecidibles


def comparar_con_revisar(b, lam, caso):
    r"""
    La demanda de la via contra demanda_capacidad.revisar(..., lambdas):
    otra forma de armar el mismo punto (fuerzas_por_caso + combinar +
    demanda + capacidad_en, con las fuerzas base SIN redondear la suma).
    Solo puede diferir en el redondeo de salida de la via.
    """
    ctx = b['ctx']
    p = Peor()
    r_dc = medio(v for d in caso['demandas'] for v in (d['P'], d['M'], d['M_fuera_plano'], d['Mn']))
    r_uu = medio(d['u'] for d in caso['demandas'] if d['u'] < U_FUERA)
    elementos = por_id(b['anexo']['elementos'])
    with trazabilidad.AvisosDeOpenSees():
        for v in caso['demandas']:
            eid = int(v['id'])
            res = dc.revisar(b['edificio'], eid, lambdas=lam,
                             curva=ctx['curvas'][elementos[eid]['familia']],
                             modelo=ctx['modelo'], resultados=ctx['resultados'])
            d = res['puntos']['COMB']
            u = d['utilizacion'] if math.isfinite(d['utilizacion']) else U_FUERA
            mag = FP * (abs(d['P_kN']) + d['M_kNm'] + d['M_capacidad_kNm'] + u + 1.0)
            for campo, a, ref, r in (('P', v['P'], d['P_kN'], r_dc), ('M', v['M'], d['M_kNm'], r_dc),
                                     ('M_fuera_plano', v['M_fuera_plano'],
                                      d['M_fuera_de_plano_kNm'] or 0.0, r_dc),
                                     ('Mn', v['Mn'], d['M_capacidad_kNm'], r_dc),
                                     ('u', v['u'], u, r_uu if u < U_FUERA else 0.0)):
                p.ver(float(a) - float(ref), r + mag, ('elemento', eid, campo))
            if v['extremo'] != d['extremo'] or v['pasa'] != d['pasa']:
                p.ver(math.inf, 0.0, ('elemento', eid, 'extremo/pasa'))
    return p


# ============================================================
# REACCIONES Y EQUILIBRIO
# ============================================================
def filas_que_cuentan(datos, reacciones):
    r"""
    Cuantas filas de reaccion entran en Fx, Fy y Fz segun
    calcular.equilibrio, preguntandoselo a la misma funcion: con una
    reaccion de 1 kN en cada fila y ninguna carga, la 'reaccion' que
    devuelve es el conteo. Asi la regla sigue teniendo una sola definicion.
    """
    unos = {'reacciones': [{'id': r['id'], 'fx': 1.0, 'fy': 1.0, 'fz': 1.0,
                            'mx': 0.0, 'my': 0.0, 'mz': 0.0} for r in reacciones]}
    cuenta = calcular.equilibrio(datos, {'cargas_nodales': [], 'cargas_distribuidas': []}, unos)
    return [int(round(v)) for v in cuenta['reaccion_kN']]


def bloque_reacciones(b, lam, ref, inf, via_eq):
    """Reacciones superpuestas contra la explicita y el equilibrio de las dos."""
    ctx = b['ctx']
    datos = ctx['datos']
    exp = ref['exp']
    sup = combinar.combinar_resultados(ctx['resultados'], lam)
    base_r = {c: por_id(ctx['resultados'][c]['reacciones']) for c in ref['activos']}

    p = Peor()
    a, e = por_id(sup['reacciones']), por_id(exp['reacciones'])
    if set(a) != set(e):
        p.ver(math.inf, 0.0, ('ids de apoyos distintos',))
    else:
        for nid, fila in e.items():
            for campo in CAMPOS_R:
                mag = abs(float(fila[campo])) + sum(abs(l) * abs(float(base_r[c][nid][campo]))
                                                    for c, l in ref['activos'].items())
                p.ver(float(a[nid][campo]) - float(fila[campo]), ref['e_r'] + FP * mag,
                      ('nodo', nid, campo))

    n = filas_que_cuentan(datos, exp['reacciones'])
    eq_exp = calcular.equilibrio(datos, ref['carga'], exp)
    eq_sup = sp.equilibrio_combinado(b, lam)
    r_eq = 0.5e-8        # error_kN sale con 8 decimales (calcular.equilibrio)
    r_salida = 0.5e-4    # aplicada_kN y reaccion_kN salen con 4
    malos = []
    filas = []
    for i, eje in enumerate(('Fx', 'Fy', 'Fz')):
        tam = FP * (abs(eq_exp['aplicada_kN'][i]) + sum(abs(float(r[CAMPOS_R[i]]))
                                                         for r in exp['reacciones'])) * (1 + ref['suma'])
        cota_exp = n[i] * ref['r_exp_r'] + r_eq + tam
        cota_sup = n[i] * ref['r_base_r'] * ref['suma'] + r_eq + tam
        cota_reac = n[i] * ref['e_r'] + 2.0 * r_salida + tam
        err_reac = eq_sup['reaccion_kN'][i] - eq_exp['reaccion_kN'][i]
        filas.append({'eje': eje, 'filas_que_cuentan': n[i],
                      'aplicada_kN': eq_exp['aplicada_kN'][i],
                      'reaccion_explicita_kN': eq_exp['reaccion_kN'][i],
                      'error_explicita_kN': eq_exp['error_kN'][i], 'cota_explicita_kN': cota_exp,
                      'reaccion_superpuesta_kN': eq_sup['reaccion_kN'][i],
                      'error_superpuesta_kN': eq_sup['error_kN'][i], 'cota_superpuesta_kN': cota_sup,
                      'dif_reacciones_kN': err_reac, 'cota_dif_kN': cota_reac})
        for que, err, cota in (('explicita', eq_exp['error_kN'][i], cota_exp),
                               ('superpuesta', eq_sup['error_kN'][i], cota_sup),
                               ('reaccion superpuesta - explicita', err_reac, cota_reac)):
            if abs(err) > cota:
                malos.append('%s %s: %.3e > cota %.3e' % (que, eje, err, cota))
    malos += ['aplicada distinta: %s contra %s' % (eq_sup['aplicada_kN'], eq_exp['aplicada_kN'])
              ] if eq_sup['aplicada_kN'] != eq_exp['aplicada_kN'] else []
    if not (eq_exp['confiable'] and eq_sup['confiable']):
        malos.append('calcular.equilibrio no es confiable: %d cargas sin convertir'
                     % eq_exp['cargas_sin_convertir'])

    # La trampa, a la vista: la suma de TODAS las filas.
    directa = [sum(float(r[c]) for r in exp['reacciones']) for c in ('fx', 'fy', 'fz')]

    print('  %-34s %6d valores   peor %.3e   cota %.3e   cociente %.3f   %s'
          % ('reacciones (superposicion vs 1)', p.n, p.err, p.cota, p.cociente,
             texto_donde(p.donde)))
    print('  equilibrio (calcular.equilibrio; filas que cuentan Fx %d, Fy %d, Fz %d):'
          % tuple(n))
    for f in filas:
        print('    %s aplicada %13.4f   explicita: reaccion %13.4f error %+.2e (cota %.2e)   '
              'superpuesta: error %+.2e (cota %.2e)'
              % (f['eje'], f['aplicada_kN'], f['reaccion_explicita_kN'], f['error_explicita_kN'],
                 f['cota_explicita_kN'], f['error_superpuesta_kN'], f['cota_superpuesta_kN']))
    print('    (sumar TODAS las filas daria Fx %.4f, Fy %.4f, Fz %.4f: los nodos de diafragma'
          % tuple(directa))
    print('     traen la fuerza interna de la restriccion; por eso solo calcular.equilibrio)')

    iguales = []
    for via, eq in via_eq.items():
        if eq is None:
            continue
        n_v, dif = diferencias(eq, eq_sup)
        iguales.append((via, dif))
    inf.check(p.calza and not malos and all(d is None for _v, d in iguales),
              'reacciones de los %d apoyos (x6) = explicita; equilibrio de la explicita y de la '
              'superpuesta dentro de su cota; "equilibrio" de %s = calcular.equilibrio superpuesto'
              % (len(e), ', '.join('(%s)' % v for v, _d in iguales) or '-'),
              malos + ['(%s): %s' % (v, d) for v, d in iguales if d])
    return {'reacciones': dict(p.fila(), familia='reacciones', via='superposicion'),
            'equilibrio': filas, 'suma_directa_de_todas_las_filas_kN': directa,
            'equilibrio_superpuesto': eq_sup, 'equilibrio_explicito': eq_exp}


# ============================================================
# CONTROL
# ============================================================
def elegir_control(b, caso_e1):
    """Los ids de control por la regla de estados_s5.json (control.reglas)."""
    info = b['anexo']['info']
    tipos = {int(e['id']): e['tipo'] for e in b['anexo']['elementos']}
    vigas = [s for s in caso_e1['esfuerzos'] if tipos[int(s['id'])].startswith('viga')]
    viga = max(vigas, key=lambda s: (max(abs(v) for v in s['My']), -int(s['id'])))
    nodo = max(caso_e1['desplazamientos'],
               key=lambda d: (math.sqrt(d['ux'] ** 2 + d['uy'] ** 2 + d['uz'] ** 2), -int(d['id'])))
    return {'columna': int(info['columna_demo']), 'muro': int(info['muro_demo']),
            'viga': int(viga['id']), 'nodo': int(nodo['id'])}


def control_de_estado(b, lam, ref, caso, ids, curvas_propias):
    """Los numeros de control de un estado: lo que Unity muestra y la explicita al lado."""
    dem = por_id(caso['demandas'])
    esf = por_id(caso['esfuerzos'])
    desp = por_id(caso['desplazamientos'])
    base = {c['nombre']: por_id(c['demandas']) for c in b['anexo']['casos'] if c['tipo'] == 'caso'}
    elementos = por_id(b['anexo']['elementos'])
    salida = {'max_desplazamiento_mm': caso['max_desplazamiento_mm'],
              'max_desplazamiento_mm_explicita': round(ref['max_mm'], 4),
              'no_pasan': sum(1 for d in caso['demandas'] if not d['pasa']),
              'no_pasan_explicita': sum(1 for rd in ref['dc'].values() if not rd['u'] <= 1.0),
              'fuera_de_curva': sum(1 for d in caso['demandas'] if d['u'] >= U_FUERA),
              'con_fierro': len(caso['demandas']),
              # Lo que el mapa D/C de Unity tiene que pintar de rojo, con la
              # u de la corrida explicita al lado.
              'lista_no_pasan': [{'id': d['id'], 'objeto_unity': trazabilidad.nombre_objeto(
                                      elementos[int(d['id'])]),
                                  'P': d['P'], 'M': d['M'], 'Mn': d['Mn'], 'u': d['u'],
                                  'u_explicita': round(ref['dc'][int(d['id'])]['u'], 6)}
                                 for d in caso['demandas'] if not d['pasa']]}
    problemas = []
    for etiqueta in ('columna', 'muro'):
        eid = ids[etiqueta]
        v, rd = dem.get(eid), ref['dc'].get(eid)
        if v is None or rd is None:
            problemas.append('%s %d sin demanda' % (etiqueta, eid))
            continue
        Mn_propia = dc.capacidad_en(rd['d']['P_kN'], curvas_propias[eid])
        s, _a, _b = pendiente_cerca(curvas_propias[eid], rd['d']['P_kN'], ref['e_f'])
        cota_Mn = s * ref['e_f'] + 0.5e-4 + FP * (1 + Mn_propia)
        if abs(Mn_propia - v['Mn']) > cota_Mn:
            problemas.append('%s %d: Mn de su propia curva %.4f contra %.4f de la familia'
                             % (etiqueta, eid, Mn_propia, v['Mn']))
        suma_u = sum(l * base[c][eid]['u'] for c, l in lam.items() if l != 0.0)
        salida[etiqueta] = {
            'id': eid, 'objeto_unity': trazabilidad.nombre_objeto(elementos[eid]),
            'familia': v['familia'], 'plano': rd['plano'] or '',
            'P': v['P'], 'M': v['M'], 'M_fuera_plano': v['M_fuera_plano'],
            'extremo': v['extremo'], 'Mn': v['Mn'], 'u': v['u'], 'pasa': v['pasa'],
            'explicita': {'P': round(rd['d']['P_kN'], 4), 'M': round(rd['d']['M_kNm'], 4),
                          'Mn': round(rd['Mn'], 4), 'u': round(rd['u'], 6),
                          'extremo': rd['d']['extremo']},
            'Mn_de_su_propia_curva': round(Mn_propia, 4),
            'suma_lambda_u_de_los_casos_base': round(suma_u, 6),
        }
    eid = ids['viga']
    s = esf[eid]
    i_max = max(range(len(s['My'])), key=lambda k: abs(s['My'][k]))
    f = ref['f'][eid]
    salida['viga'] = {'id': eid, 'objeto_unity': trazabilidad.nombre_objeto(elementos[eid]),
                      'w': s['w'], 'x': s['x'], 'My': s['My'],
                      'My_0': s['My'][0], 'My_L': s['My'][-1],
                      'max_abs_My': s['My'][i_max], 'x_de_max_abs_My': s['x'][i_max],
                      'explicita': {'My_0': round(-f[4], 4), 'My_L': round(f[10], 4)}}
    nid = ids['nodo']
    d = desp[nid]
    e = ref['u'][nid]
    salida['nodo'] = {'id': nid, 'ux': d['ux'], 'uy': d['uy'], 'uz': d['uz'],
                      'explicita': {'ux': e[0], 'uy': e[1], 'uz': e[2]}}
    return salida, problemas


def filas_de_control(estado, control):
    r"""
    El control de un estado como tabla plana para la integracion: una
    fila por numero que Unity muestra (panel del elemento, P-M, diagrama,
    deformada, cabecera), con el valor del JSON que Unity lee (vias 2 = 3
    = 4, identicas) y el de la corrida explicita al lado.
    """
    filas = []

    def fila(etiqueta, id_, objeto, magnitud, valor, explicita, donde):
        filas.append({'estado': estado, 'etiqueta': etiqueta, 'id': id_, 'objeto_unity': objeto,
                      'magnitud': magnitud, 'valor_unity_json': valor,
                      'valor_explicita': explicita, 'donde_se_ve': donde})

    fila('estado', '', '', 'max_desplazamiento_mm', control['max_desplazamiento_mm'],
         control['max_desplazamiento_mm_explicita'], 'cabecera: Dmax')
    fila('estado', '', '', 'no_pasan (de %d con fierro)' % control['con_fierro'],
         control['no_pasan'], control['no_pasan_explicita'], 'cabecera: NO PASA n/m')
    for etiqueta in ('columna', 'muro'):
        c = control.get(etiqueta)
        if not c:
            continue
        for k in ('P', 'M', 'Mn', 'u', 'extremo'):
            fila(etiqueta, c['id'], c['objeto_unity'], k, c[k], c['explicita'][k],
                 'panel del elemento y ventana P-M')
        fila(etiqueta, c['id'], c['objeto_unity'], 'pasa', c['pasa'], c['explicita']['u'] <= 1.0,
             'panel del elemento y mapa D/C')
        fila(etiqueta, c['id'], c['objeto_unity'], 'sum lambda u_caso (NO es u)',
             c['suma_lambda_u_de_los_casos_base'], c['explicita']['u'],
             'tabla de no linealidad (no se muestra en Unity)')
    v = control['viga']
    fila('viga', v['id'], v['objeto_unity'], 'My(0)', v['My_0'], v['explicita']['My_0'],
         'diagrama My')
    fila('viga', v['id'], v['objeto_unity'], 'My(L)', v['My_L'], v['explicita']['My_L'],
         'diagrama My')
    fila('viga', v['id'], v['objeto_unity'], 'max|My| (x = %.4f)' % v['x_de_max_abs_My'],
         v['max_abs_My'], '', 'diagrama My')
    n = control['nodo']
    for k in ('ux', 'uy', 'uz'):
        fila('nodo', n['id'], '', k + ' (m)', n[k], n['explicita'][k], 'deformada / panel del nodo')
    for d in control['lista_no_pasan']:
        fila('no pasa', d['id'], d['objeto_unity'], 'u', d['u'], d['u_explicita'],
             'mapa D/C en rojo')
    return filas


# ============================================================
def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    edificio = 'lt2'
    if argv and not argv[0].startswith('-'):
        edificio = argv.pop(0)
    if not os.path.isfile(rutas.modelo(edificio)):
        raise SystemExit('no existe el modelo %r' % edificio)

    print('=' * 78)
    print('  VERIFICACION DE LA SUPERPOSICION (SEMANA 5)   %s' % edificio.upper())
    print('=' * 78)
    inf = Informe()
    t0 = time.time()
    b = sp.base(edificio, argv)
    ctx = b['ctx']
    print('  base: superposicion.base -> exportar_unity.construir_anexo en %.1f s '
          '(%d nodos, %d barras, %d con fierro)'
          % (b['segundos'], len(b['ids_nodos']), len(b['largos']), len(ctx['secciones'])))
    for linea in b['parametros']:
        print('  %s' % linea)
    print()
    print('  vias:')
    for k, v in VIAS.items():
        print('    (%s) %s' % (k, v))
    print()
    print('  cotas (MEDIDAS: r = medio ultimo decimal de cada fuente, combinar.decimales_de):')
    print('    e_lin = r_base * sum|lambda| + r_explicita;  cota = e_lin + r_via + 4 eps * tamano')
    print('    estaciones My, Mz: e_lin (1 + x);  D/C: P, M muro e_lin; M columna sqrt(2) e_lin;')
    print('    Mn pendiente * e_lin; u (dM + u dMn)/(Mn - dMn);  vias (3) y (4) = (2) exacto')

    estados = sp.cargar_estados()
    inf.check([e['nombre'] for e in estados['estados']] == ['E1', 'E2', 'E3'],
              'estados_s5.json trae E1, E2, E3 en ese orden')
    inf.check(ctx['datos']['casos_de_carga'] == list(ctx['arm']['casos'].values()),
              'lo que se combina son los casos de la semana (lab.armar_casos: %s), no los de '
              'data/modelo' % ', '.join(c['nombre'] for c in ctx['datos']['casos_de_carga']))

    # --- via (3): el servidor, sin red ---
    import servidor_s5                        # noqa: E402  (registra /combinar en la app)
    servidor_s5.ARGV_PARAMETROS[:] = argv
    cliente = servidor_s5.app.test_client()

    # --- via (4): el precalculado ---
    ruta_pre = sp.ruta_precalculado(edificio)
    pre = None
    if os.path.isfile(ruta_pre):
        with io.open(ruta_pre, encoding='utf-8') as f:
            pre = json.load(f)
        print()
        print('  precalculado: %s (%.2f MB)' % (os.path.relpath(ruta_pre, rutas.RAIZ),
                                                os.path.getsize(ruta_pre) / 1048576.0))
        info = pre.get('info') or {}
        inf.check(info.get('edificio') == edificio and info.get('generado_por') == sp.GENERADO_POR,
                  'info.edificio = %r e info.generado_por = %r'
                  % (info.get('edificio'), info.get('generado_por')))
        if not inf.check(info.get('parametros') == b['parametros'],
                         'info.parametros = los de esta corrida (y los de semana04.json)',
                         [] if info.get('parametros') == b['parametros'] else
                         ['precalculado: %s' % info.get('parametros'),
                          'esta corrida: %s' % b['parametros'],
                          'regenerar: python semana05/superposicion.py %s --exportar %s'
                          % (edificio, ' '.join(argv))]):
            pre = None
        else:
            hay = [(e.get('nombre'), e.get('lambdas')) for e in (pre.get('estados') or [])]
            quiero = [(e['nombre'], sp.lambdas_de(e['lambdas'])) for e in estados['estados']]
            inf.check(hay == quiero, 'estados del precalculado = estados_s5.json (nombre y lambdas)')
        ed_sa, _p = sp._edificio_del_anexo_en_streaming()
        if ed_sa == edificio:
            inf.check(os.path.isfile(sp.STREAMING) and filecmp.cmp(ruta_pre, sp.STREAMING,
                                                                     shallow=False),
                      'StreamingAssets/superposicion.json es identico byte a byte al '
                      'precalculado (StreamingAssets es de %s)' % edificio)
        else:
            print('  [--  ] StreamingAssets es de %r: su superposicion.json no se compara' % ed_sa)
    elif edificio == 'lt2':
        inf.check(False, 'existe %s (python semana05/superposicion.py lt2 --exportar)'
                  % os.path.relpath(ruta_pre, rutas.RAIZ))
    else:
        inf.pendiente('no hay %s: solo el LT2 se precalcula (decision 3); la via (4) no se '
                      'compara' % os.path.relpath(ruta_pre, rutas.RAIZ))

    evidencia = {
        'generado_por': 'semana05/verificar_superposicion.py',
        'comando': 'python semana05/verificar_superposicion.py %s' % ' '.join([edificio] + argv),
        'edificio': edificio,
        'parametros': b['parametros'],
        'vias': VIAS,
        'cotas': [
            'r = medio ultimo decimal MEDIDO con combinar.decimales_de (servidor: desplazamientos '
            '8 decimales, fuerzas y reacciones 4; vias: lo que escriben)',
            'e_lin = r_base * sum|lambda| + r_explicita',
            'cota = e_lin + r_via + 4 eps * tamano (eps de coma flotante, FACTOR_COMA_FLOTANTE)',
            'estaciones My, Mz: e_lin (1 + x); N, Vy, Vz, T: e_lin',
            'max_desplazamiento_mm: 1000 sqrt(3) (e_lin_u + r_via_u) + r_mm',
            'D/C: P y M de muro e_lin; M de columna sqrt(2) e_lin; Mn pendiente * e_lin; '
            'u (dM + u dMn) / (Mn - dMn) + r_u',
            'reacciones: e_lin con r de reacciones; equilibrio: filas que cuentan * r + 5e-9',
            'vias (3) y (4) contra (2), y E2 contra el anexo: identidad exacta',
        ],
        'estados': [],
    }
    filas_csv = []
    filas_control = []
    ids_control = None
    curvas_propias = {}

    for est in estados['estados']:
        nombre = est['nombre']
        lam = sp.lambdas_de(est['lambdas'])
        print()
        print('[%s] %s   lambdas G %.2f  Q %.2f  EX %.2f  EY %.2f'
              % (nombre, est['descripcion'], lam['G'], lam['Q'], lam['EX'], lam['EY']))
        print('-' * 78)
        ref = referencia(b, lam, nombre)
        inf.check(ref['exp'].get('ok', False), '(1) OpenSees resolvio la corrida explicita '
                  '(%d cargas nodales y %d repartidas combinadas, %.3f s)'
                  % (len(ref['carga']['cargas_nodales']), len(ref['carga']['cargas_distribuidas']),
                     ref['t']))

        t = time.time()
        caso2, cierre = sp.caso_combinado(b, lam, nombre=nombre)
        t2 = time.time() - t
        eq2 = sp.equilibrio_combinado(b, lam)
        print('  (2) caso_combinado en %.3f s; autoverificacion de bloque_caso: peor cierre %.3f '
              '(elemento %d, %s)' % (t2, cierre[0], cierre[1], cierre[2]))

        t = time.time()
        http = cliente.post('/combinar', json=dict(lam, edificio=edificio))
        t3 = time.time() - t
        resp3 = http.get_json(silent=True) or {}
        caso3 = resp3.get('caso')
        ok3 = inf.check(http.status_code == 200 and resp3.get('ok') is True and caso3 is not None,
                        '(3) POST /combinar respondio HTTP %d, ok = %r en %.3f s%s'
                        % (http.status_code, resp3.get('ok'), t3,
                           ' (incluye armar la base del servidor)' if nombre == 'E1' else ''),
                        resp3.get('error') or '')
        if ok3:
            inf.check(resp3.get('edificio') == edificio and resp3.get('parametros') == b['parametros']
                      and resp3.get('error') == '',
                      '(3) edificio, parametros y error de la respuesta son los esperados')
            inf.check(caso3.get('nombre') == sp.NOMBRE_LIBRE and caso3.get('tipo') == sp.TIPO,
                      '(3) caso.nombre = %r, caso.tipo = %r' % (caso3.get('nombre'), caso3.get('tipo')))

        caso4, eq4 = None, None
        if pre is not None:
            e4 = next((e for e in pre['estados'] if e.get('nombre') == nombre), None)
            caso4 = e4.get('caso') if e4 else None
            eq4 = e4.get('equilibrio') if e4 else None
            inf.check(caso4 is not None, '(4) el precalculado trae el caso de %s' % nombre)

        # --- identidades ---
        identidades = []
        sin_nombre = lambda c: {k: v for k, v in c.items() if k != 'nombre'}   # noqa: E731
        inf.check(caso2['factores'] == [lam[c] for c in CASOS] and caso2['tipo'] == sp.TIPO
                  and caso2['descripcion'] == sp.texto_combinacion(lam),
                  '(2) factores = %s, tipo = %r, descripcion = %r'
                  % (caso2['factores'], caso2['tipo'], caso2['descripcion']))
        for via, caso in (('3', caso3), ('4', caso4)):
            if caso is None:
                continue
            n, dif = diferencias(sin_nombre(caso), sin_nombre(caso2))
            identidades.append({'que': '(%s) = (2)' % via, 'hojas': n, 'primera_diferencia': dif})
            inf.check(dif is None, '(%s) identica a (2), bit a bit: %d valores (salvo el nombre)'
                      % (via, n), dif or '')
        if caso4 is not None:
            inf.check(caso4.get('nombre') == nombre, '(4) caso.nombre = %r' % caso4.get('nombre'))
        del_anexo = next((c for c in b['anexo']['casos']
                          if [float(x) for x in c['factores']] == caso2['factores']), None)
        if del_anexo is not None:
            quitar = ('nombre', 'tipo', 'descripcion')
            n, dif = diferencias({k: v for k, v in del_anexo.items() if k not in quitar},
                                 {k: v for k, v in caso2.items() if k not in quitar})
            identidades.append({'que': "(2) = anexo '%s'" % del_anexo['nombre'], 'hojas': n,
                                'primera_diferencia': dif})
            inf.check(dif is None, "(2) identica al caso '%s' del anexo de Semana 4: %d valores"
                      % (del_anexo['nombre'], n), dif or '')
        else:
            # Que se vea que este control cruzado NO corrio: si parametros.json
            # deja de declarar 1.2G+1.6Q, E2 pierde su comparacion con el anexo
            # y eso no puede pasar en silencio.
            print('  [--  ] ningun caso del anexo de Semana 4 tiene factores %s: sin control '
                  'cruzado con el anexo' % caso2['factores'])

        # --- contra la explicita ---
        inf.check(set(por_id(caso2['desplazamientos'])) == set(b['ids_nodos'])
                  and set(por_id(caso2['esfuerzos'])) == set(b['largos'])
                  and set(por_id(caso2['demandas'])) == set(ref['dc']),
                  '(2) trae los %d nodos, las %d barras y las %d con fierro'
                  % (len(b['ids_nodos']), len(b['largos']), len(ref['dc'])))
        vias = [('2', caso2)] + [(v, c) for v, c in (('3', caso3), ('4', caso4)) if c is not None]
        resultados_via = {}
        for via, caso in vias:
            resultados_via[via] = comparar_via(b, lam, ref, caso)
        rev = comparar_con_revisar(b, lam, caso2)

        print()
        print('  %-24s %7s %11s %11s   %s   %s'
              % ('familia (contra (1))', 'valores', 'peor (2)', 'cota', '  '.join(
                  'cociente (%s)' % v for v, _c in vias), 'donde, en (2)'))
        comparaciones = []
        for fam in FAMILIAS:
            if fam == 'D/C = dc.revisar':
                p2, cocientes = rev, [rev]
            else:
                p2 = resultados_via['2'][0][fam]
                cocientes = [resultados_via[v][0][fam] for v, _c in vias]
            print('  %-24s %7d %11.3e %11.3e   %s   %s'
                  % (fam, p2.n, p2.err, p2.cota,
                     '  '.join('%12.3f' % p.cociente for p in cocientes)
                     + ('  (solo (2))' if fam == 'D/C = dc.revisar' else ''),
                     texto_donde(p2.donde)))
            for (via, _c), p in zip(vias if fam != 'D/C = dc.revisar' else [('2', None)], cocientes):
                fila = dict(p.fila(), estado=nombre, via=via, familia=fam)
                comparaciones.append(fila)
                filas_csv.append(fila)
            inf_ok = all(p.calza for p in cocientes)
            if not inf_ok:
                inf.fallas.append('%s: %s fuera de cota (%s)' % (
                    nombre, fam, ', '.join('(%s) %d de %d' % (v, p.fuera, p.n)
                                           for (v, _c), p in zip(vias, cocientes) if not p.calza)))
        indecidibles = sorted(set(i for v, _c in vias for i in resultados_via[v][1]))
        todas = all(p.calza for v, _c in vias for p in resultados_via[v][0].values()) and rev.calza
        inf.check(todas, '%s: las %d familias calzan en las vias %s (cociente <= 1)'
                  % (nombre, len(FAMILIAS), ', '.join('(%s)' % v for v, _c in vias)))
        print('  indecidibles por redondeo (extremo o pasa dentro de la cota): %d%s'
              % (len(indecidibles), (': ' + '; '.join(indecidibles)) if indecidibles else ''))

        print()
        rea = bloque_reacciones(b, lam, ref, inf, {'2': eq2, '3': resp3.get('equilibrio') if ok3
                                                   else None, '4': eq4})
        rea['reacciones'].update(estado=nombre)
        filas_csv.append(rea['reacciones'])

        # --- control ---
        if ids_control is None:
            ids_control = elegir_control(b, caso2)
            esperados = (estados.get('control', {}).get('esperados') or {}).get(edificio)
            print()
            print('  elementos de control (reglas de estados_s5.json, sobre E1): %s'
                  % ', '.join('%s %d' % kv for kv in ids_control.items()))
            if esperados is not None:
                inf.check(esperados == ids_control,
                          'la regla da los ids declarados en estados_s5.json control.esperados.%s'
                          % edificio, [] if esperados == ids_control else
                          ['declarados %s, la regla da %s' % (esperados, ids_control)])
            with trazabilidad.AvisosDeOpenSees():
                for etiqueta in ('columna', 'muro'):
                    eid = ids_control[etiqueta]
                    curvas_propias[eid] = capacidad.interaccion(
                        capacidad.desde_elemento(ctx['modelo'], eid))
        control, problemas = control_de_estado(b, lam, ref, caso2, ids_control, curvas_propias)
        inf.check(not problemas, '%s: control con la curva P-M propia de la columna y del muro'
                  % nombre, problemas)
        print('  control %s:' % nombre)
        for etiqueta in ('columna', 'muro'):
            c = control.get(etiqueta)
            if c:
                print('    %-7s %4d  P %11.4f  M %11.4f  (%s)  Mn %11.4f  u %s  %s   '
                      'sum lambda u_caso = %.6f'
                      % (etiqueta, c['id'], c['P'], c['M'], c['extremo'], c['Mn'],
                         'fuera de curva' if c['u'] >= U_FUERA else '%.6f' % c['u'],
                         'pasa' if c['pasa'] else 'NO PASA', c['suma_lambda_u_de_los_casos_base']))
        v = control['viga']
        print('    viga    %4d  wz %.4f  My(0) %.4f  My(L) %.4f  max|My| %.4f en x = %.4f'
              % (v['id'], v['w'][2], v['My_0'], v['My_L'], v['max_abs_My'], v['x_de_max_abs_My']))
        n_ = control['nodo']
        print('    nodo    %4d  ux %.8f  uy %.8f  uz %.8f' % (n_['id'], n_['ux'], n_['uy'], n_['uz']))
        print('    max %.4f mm;  NO PASA %d/%d (%d fuera de curva)'
              % (control['max_desplazamiento_mm'], control['no_pasan'], control['con_fierro'],
                 control['fuera_de_curva']))
        for d in control['lista_no_pasan']:
            print('      NO PASA %-18s P %11.4f  M %11.4f  Mn %11.4f  u %s (explicita %s)'
                  % (d['objeto_unity'], d['P'], d['M'], d['Mn'],
                     'fuera de curva' if d['u'] >= U_FUERA else '%.6f' % d['u'],
                     'fuera de curva' if d['u_explicita'] >= U_FUERA else '%.6f' % d['u_explicita']))
        filas_control.extend(filas_de_control(nombre, control))

        evidencia['estados'].append({
            'nombre': nombre, 'descripcion': est['descripcion'], 'lambdas': lam,
            'suma_abs_lambdas': ref['suma'],
            'tiempos_s': {'explicita': round(ref['t'], 4), 'caso_combinado': round(t2, 4),
                          'post_combinar': round(t3, 4)},
            'cierre_bloque_caso': {'cociente': cierre[0], 'elemento': cierre[1],
                                   'componente': cierre[2]},
            'e_lin': {'desplazamientos_m': ref['e_u'], 'fuerzas_kN': ref['e_f'],
                      'reacciones_kN': ref['e_r']},
            'comparaciones': comparaciones + [rea['reacciones']],
            'identidades': identidades,
            'indecidibles_por_redondeo': indecidibles,
            'equilibrio': rea['equilibrio'],
            'suma_directa_de_todas_las_filas_kN': rea['suma_directa_de_todas_las_filas_kN'],
            'control': control,
        })

    # ------------------------------------------------------------
    print()
    print('=' * 78)
    print('  TABLA DE COCIENTES (peor error / cota, la mayor de las vias comparadas)')
    print('  %-24s %s' % ('familia', '  '.join('%8s' % e['nombre'] for e in evidencia['estados'])))
    familias = list(FAMILIAS) + ['reacciones']
    for fam in familias:
        valores = []
        for e in evidencia['estados']:
            cs = [c['cociente'] for c in e['comparaciones'] if c['familia'] == fam]
            valores.append(max(cs) if cs else float('nan'))
        print('  %-24s %s' % (fam, '  '.join('%8.3f' % v for v in valores)))
    notas = list(NOTAS_COCIENTES)
    peores_x = sorted({c['donde'] for e in evidencia['estados'] for c in e['comparaciones']
                       if c['familia'] == 'estaciones x' and c['cociente'] > 0.999})
    notas += [d for d in (detalle_de_x(b, x) for x in peores_x) if d]
    print()
    for nota in notas:
        print('  nota: %s' % nota)

    evidencia['notas_cocientes'] = notas
    evidencia['ids_control'] = ids_control
    evidencia['fallas'] = inf.fallas
    evidencia['pendientes'] = inf.pendientes
    evidencia['resultado'] = 'NO CALZA' if inf.fallas else 'CALZA'
    evidencia['segundos'] = round(time.time() - t0, 1)
    os.makedirs(EVIDENCIA, exist_ok=True)
    ruta_json = os.path.join(EVIDENCIA, 'superposicion_%s.json' % edificio)
    ruta_csv = os.path.join(EVIDENCIA, 'superposicion_%s.csv' % edificio)
    with io.open(ruta_json, 'w', encoding='utf-8') as f:
        json.dump(evidencia, f, ensure_ascii=False, indent=1)
    columnas = ('estado', 'via', 'familia', 'n_comparados', 'peor_abs', 'cota_en_el_peor',
                'cociente', 'fuera_de_cota', 'calza', 'donde')
    with io.open(ruta_csv, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=columnas, extrasaction='ignore')
        w.writeheader()
        for fila in filas_csv:
            w.writerow({k: (('%.6e' % fila[k]) if isinstance(fila.get(k), float) else fila.get(k))
                        for k in columnas})
    ruta_control = os.path.join(EVIDENCIA, 'superposicion_%s_control.csv' % edificio)
    columnas = ('estado', 'etiqueta', 'id', 'objeto_unity', 'magnitud', 'valor_unity_json',
                'valor_explicita', 'donde_se_ve')
    with io.open(ruta_control, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=columnas)
        w.writeheader()
        for fila in filas_control:
            w.writerow(fila)
    print()
    print('  evidencia -> %s' % os.path.relpath(ruta_json, rutas.RAIZ))
    print('            -> %s' % os.path.relpath(ruta_csv, rutas.RAIZ))
    print('            -> %s (%d filas: lo que la integracion compara con Unity)'
          % (os.path.relpath(ruta_control, rutas.RAIZ), len(filas_control)))
    print('  (%.1f s)' % (time.time() - t0))
    print('=' * 78)
    if inf.pendientes:
        print('  PENDIENTE (%d):' % len(inf.pendientes))
        for p in inf.pendientes:
            print('    - %s' % p)
    if inf.fallas:
        print('  NO CALZA (%d):' % len(inf.fallas))
        for f in inf.fallas:
            print('    - %s' % f)
        print('=' * 78)
        return 1
    print('  TODO CALZA: E1..E3 por las vias %s = corrida explicita de OpenSees'
          % ('(2), (3) y (4)' if pre is not None else '(2) y (3)'))
    print('=' * 78)
    return 0


if __name__ == '__main__':
    sys.exit(main())
