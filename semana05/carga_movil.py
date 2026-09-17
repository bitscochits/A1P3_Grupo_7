# -*- coding: utf-8 -*-
r"""
================================================================
 semana05/carga_movil.py  -  UNA CARGA PUNTUAL QUE RECORRE UN EJE DE VIGAS
================================================================
 Precalcula en OpenSees una carga vertical P que avanza por una linea
 de vigas continuas de un piso, verifica cada posicion y deja todo en
 data/unity/carga_movil_<ed>.json (y su copia en StreamingAssets/
 carga_movil.json) para que VisorCargaMovil.cs lo MUESTRE. Unity no
 calcula nada: elige una posicion ya resuelta y la dibuja.

 Correr:
   python semana05/carga_movil.py lt2
   python semana05/carga_movil.py lt2 --P 50 --divisiones 3
   python semana05/carga_movil.py lt2 --no-escribir      solo verificar

 Sale con 0 si todo cierra y escribio; con 1 si algo no cierra, y en
 ese caso NO escribe nada (ni el JSON, ni la copia, ni la evidencia).

 ----------------------------------------------------------------
 LA REGLA FISICA
 ----------------------------------------------------------------
 En cada posicion la carga actua sobre UNA viga del recorrido, en su
 abscisa local a = xL*L medida desde n1, con

     ops.eleLoad('-ele', eid, '-type', '-beamPoint', Py, Pz, xL, Px)

 Las componentes locales salen de los versores de la barra (la misma
 regla que geomTransf, contrato.ejes_locales): P hacia abajo es el
 vector global (0, 0, -P), y su componente en cada eje local es el
 producto punto. En las vigas horizontales del LT2 localZ = (0,0,1):
 Pz = -P y Py = Px = 0.

 El elemento es Euler-Bernoulli: OpenSees convierte la carga en sus
 fuerzas de empotramiento perfecto y resuelve EXACTO. No se reparte a
 mano a los nodos con funciones de forma lineales (P(1-xi), P xi):
 conservan la resultante pero borran la flexion local -- el script lo
 mide (bloque "por que no").

 ----------------------------------------------------------------
 EL REPARTO: POR QUE NO ES 50/50
 ----------------------------------------------------------------
 Lo que la viga le entrega a cada extremo es el corte de localForce,
 Vz_i y Vz_j (fuerzas de los nodos SOBRE la barra). Por equilibrio de
 la barra (momentos en torno a i, eje local y):

     Vz_j = P a/L + (My_i + My_j)/L          Vz_i = P - Vz_j

 El primer termino es la palanca de una viga simplemente apoyada (a
 mitad de vano: 50/50). El segundo lo ponen los MOMENTOS DE EXTREMO,
 y esos dependen de lo que hay en cada nodo: un nodo con columna
 retiene el giro y no baja; uno sin columna (el 116 del LT2, un cruce
 de vigas) cuelga de la viga transversal, baja y gira. La carga se va
 hacia el extremo rigido. Se informa tambien la referencia de
 empotramiento perfecto (las "fuerzas nodales equivalentes" que
 OpenSees ensambla): la diferencia con Vz real la explican los
 desplazamientos de los nodos.

 ----------------------------------------------------------------
 LO QUE SE VERIFICA
 ----------------------------------------------------------------
 En cada posicion (sobre los valores REDONDEADOS como el servidor,
 que son los que viajan al visor):
   [a] conservacion: sum Rz = P, con la regla de calcular.equilibrio
       (por grado de libertad, sin maestros). Cota: n_apoyos * 5e-5 kN
       (cada reaccion viene redondeada a 4 decimales) + coma flotante.
   [b] horizontales: sum Rx y sum Ry = 0 con la misma cota.
   [c] la viga cargada: Vz_i + Vz_j + Pz = 0 y el cierre en x = L con
       el termino del salto H(x-a), contra la cota_de_cierre de la
       Semana 4 (semana04/exportar_unity.py) -- la misma que usa el
       anexo de diagramas.
   [d] la explicacion del reparto cierra: Vz_j - palanca = (My_i+My_j)/L.
 Globales (en memoria, sin redondeo; criterio: indistinguible en el
 JSON, 1e-8 m y 1e-4 kN, los decimales que escribe el servidor):
   [e] beamPoint contra la viga PARTIDA con un nodo bajo la carga y
       carga nodal (subdividir de semana03/verificar_viga_partida.py):
       desplazamientos de todos los nodos, corte y momento bajo la carga,
       la flecha bajo la carga que se calcula aca y la ELASTICA de la
       viga cargada que dibuja el visor (en los 9 nodos interiores).
   [f] continuidad en un nodo: beamPoint en xL=1 de una viga, en xL=0
       de la siguiente y carga nodal en el nodo comun.
   [g] reciprocidad de Betti entre dos puntos del recorrido.
   [h] superposicion: dos posiciones en una corrida = suma de las dos.
   [i] fuerzas de empotramiento perfecto: la formula de texto contra
       OpenSees en una viga biempotrada aislada.
   [j] el JSON contra las clases C# de VisorCargaMovil.cs, en las dos
       direcciones (JsonUtility ignora sin avisar lo que no calza).
 Si cualquiera falla, no se escribe nada.
================================================================
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import io
import json
import math
import os
import re
import shutil
import sys
import time

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_AQUI), 'comun'))

import rutas                                 # noqa: E402
rutas.en_sys_path(rutas.COMUN)

import openseespy.opensees as ops            # noqa: E402

import calcular                              # noqa: E402
import contrato                              # noqa: E402
import servidor_opensees as motor            # noqa: E402

GENERADO_POR = 'semana05/carga_movil.py'
SCRIPTS_CS = os.path.join(rutas.UNITY_PROYECTO, 'Assets', 'Scripts')
CS_VISOR = os.path.join(SCRIPTS_CS, 'VisorCargaMovil.cs')
CS_MODELO = os.path.join(SCRIPTS_CS, 'ModeloEstructural.cs')
EVIDENCIA = os.path.join(rutas.RAIZ, 'semana05', 'evidencia')


def salida_unity(ed):
    return os.path.join(rutas.UNITY, 'carga_movil_%s.json' % ed)


STREAMING = os.path.join(rutas.STREAMING, 'carga_movil.json')

# ------------------------------------------------------------
# LO DECLARADO (no sale del plano: se elige y se dice por que)
# ------------------------------------------------------------
P_POR_DEFECTO = 100.0
DIVISIONES_POR_DEFECTO = 5

# El recorrido de cada edificio: una linea recta de vigas de un piso,
# dada por su cota, el eje global a lo largo del cual corre y la
# coordenada fija del otro eje. Los elementos se BUSCAN por geometria
# (recorrido()), no se escriben aca.
RECORRIDOS = {
    'lt2': {
        'z': 3.91, 'eje': 'x', 'coord': 18.1793,
        '_por_que': ('Primer piso (+3.91), eje y = 18.18: seis vigas V 0.60x0.80 '
                     'continuas de la columna del nodo 101 a la cara del muro del '
                     'nodo 122. Alterna nodos con columna (101, 102, 103) y cruces '
                     'de viga sin columna (121, 116, 119), asi que el reparto cambia '
                     'de una viga a otra y la deformada se ve. Es el que propuso la '
                     'auditoria y se confirmo contra data/modelo/lt2.json.'),
    },
    'conjunto': {
        'z': 3.91, 'eje': 'x', 'coord': 55.0833,
        '_por_que': ('El MISMO recorrido del LT2 visto en el marco del conjunto, '
                     'para que el edificio unido muestre lo mismo que el cuerpo '
                     'suelto. El conjunto usa el marco de Ingenieria, y el calce '
                     'del LT2 (edificios/conjunto/calce.json: dx -35.082, dy 36.904, '
                     'dz 0) mueve el eje y = 18.1793 a 18.1793 + 36.904 = 55.0833; '
                     'la cota no cambia. Son los mismos 7 nodos, renumerados '
                     '200101, 200121, 200116, 200102, 200119, 200103 y 200122 '
                     '(200000 + id del LT2), comprobado contra '
                     'data/unity/conjunto.json.'),
    },
}

# Criterio de "indistinguible" para las verificaciones globales: los
# decimales que escribe el servidor (extraer_resultados redondea
# desplazamientos a 8 y fuerzas a 4). Dos resultados que difieren menos
# que eso son el mismo numero en el JSON que ve el visor.
RESOLUCION_U = 1e-8          # m y rad
RESOLUCION_F = 1e-4          # kN y kN*m

# La deformada se dibuja con la mayor traslacion del recorrido llevada a
# este largo. Es solo grafico y fijo para TODAS las posiciones: si cada
# posicion tuviera su escala, la animacion mostraria "respirar" a la
# estructura sin que cambie nada.
LARGO_DIBUJO_M = 1.5

TAG_BASE = 7000


# ============================================================
# MODULOS HERMANOS, CARGADOS POR RUTA
# ============================================================
def _por_ruta(nombre, ruta):
    """
    semana04/exportar_unity.py y semana03/exportar_unity.py tienen el
    mismo nombre: un 'import exportar_unity' traeria cualquiera de los
    dos segun sys.path, sin error (semana04/trazabilidad.exportador
    explica el caso). Se cargan por ruta con un nombre propio.
    """
    if nombre in sys.modules:
        return sys.modules[nombre]
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = mod
    spec.loader.exec_module(mod)
    return mod


def exportador_s4():
    return _por_ruta('exportar_unity_semana04',
                     os.path.join(rutas.RAIZ, 'semana04', 'exportar_unity.py'))


def viga_partida():
    return _por_ruta('verificar_viga_partida_s3',
                     os.path.join(rutas.RAIZ, 'semana03', 'verificar_viga_partida.py'))


# ============================================================
# SALIDA: pantalla y registro
# ============================================================
REGISTRO = []


def decir(texto=''):
    print(texto)
    REGISTRO.append(texto)


FALLOS = []


def check(cond, msg, detalle=''):
    decir('  [%s] %s' % ('OK  ' if cond else 'FALLA', msg))
    if detalle:
        decir('         %s' % detalle)
    if not cond:
        FALLOS.append(msg)
    return bool(cond)


# ============================================================
# GEOMETRIA DEL RECORRIDO
# ============================================================
def _xyz(n):
    return (float(n['x']), float(n['y']), float(n['z']))


def ejes_de(e, nodos):
    """Versores locales y largo con la regla del solver (contrato.py)."""
    pi, pj = _xyz(nodos[int(e['n1'])]), _xyz(nodos[int(e['n2'])])
    vecxz = e.get('vecxz') or contrato.vecxz_por_defecto(pi, pj)
    base, L = contrato.ejes_locales(pi, pj, [float(v) for v in vecxz])
    return base, L


def recorrido(modelo, z, eje, coord, tol=0.02):
    """
    Las vigas colineales de la cota z sobre la linea eje = coord,
    encadenadas por sus nodos y ordenadas a lo largo del eje. Error si
    la cadena tiene un hueco: una carga movil no salta de viga.
    Devuelve {elementos, sentidos, nodos, largo_m, desde, hasta}.
    """
    k = {'x': 0, 'y': 1}[eje]
    otro = 1 - k
    nodos = {int(n['id']): n for n in modelo['nodos']}
    tramos = []
    for e in modelo['elementos']:
        if not str(e.get('tipo', '')).startswith('viga'):
            continue
        a, b = _xyz(nodos[int(e['n1'])]), _xyz(nodos[int(e['n2'])])
        if abs(a[2] - z) > tol or abs(b[2] - z) > tol:
            continue
        if abs(a[otro] - coord) > tol or abs(b[otro] - coord) > tol:
            continue
        L = math.dist(a, b)
        if L < 1e-9 or abs(b[k] - a[k]) < 0.999 * L:
            continue
        sentido = 1 if b[k] > a[k] else -1
        inicio, fin = (int(e['n1']), int(e['n2'])) if sentido > 0 else (int(e['n2']), int(e['n1']))
        tramos.append((min(a[k], b[k]), int(e['id']), sentido, inicio, fin, L))
    if not tramos:
        raise SystemExit('no hay vigas en z=%.2f, %s, coordenada %.4f'
                         % (z, eje, coord))
    tramos.sort()
    for t0, t1 in zip(tramos, tramos[1:]):
        if t0[4] != t1[3]:
            raise SystemExit('el recorrido tiene un hueco entre las vigas %d y %d '
                             '(nodos %d y %d)' % (t0[1], t1[1], t0[4], t1[3]))
    cadena = [tramos[0][3]] + [t[4] for t in tramos]
    return {
        'elementos': [t[1] for t in tramos],
        'sentidos': [t[2] for t in tramos],
        'nodos': cadena,
        'largos': [t[5] for t in tramos],
        'largo_m': sum(t[5] for t in tramos),
    }


def que_llega_a(modelo, nid):
    """Los tipos de barra que llegan a un nodo, para describirlo."""
    tipos = sorted({str(e.get('tipo', '')) for e in modelo['elementos']
                    if nid in (int(e['n1']), int(e['n2']))})
    return tipos


def posiciones(modelo, rec, divisiones):
    """
    Las posiciones de la carga: en cada viga, xL = (k + 1/2)/divisiones
    desde el inicio del recorrido. Ninguna cae sobre un nodo: ahi la carga
    la comparten todas las barras que llegan y "el reparto de la viga" no
    es una pregunta con sentido. Lo que pasa al cruzar un nodo lo cubre
    la verificacion de continuidad [f].
    """
    nodos = {int(n['id']): n for n in modelo['nodos']}
    por_id = {int(e['id']): e for e in modelo['elementos']}
    salida, s0 = [], 0.0
    for eid, sentido, L in zip(rec['elementos'], rec['sentidos'], rec['largos']):
        e = por_id[eid]
        pi, pj = _xyz(nodos[int(e['n1'])]), _xyz(nodos[int(e['n2'])])
        for k in range(divisiones):
            t = (k + 0.5) / divisiones          # fraccion en el sentido del recorrido
            xL = t if sentido > 0 else 1.0 - t  # fraccion desde n1, la de OpenSees
            salida.append({
                'elemento': eid, 'xL': xL, 'a': xL * L, 'L': L,
                's': s0 + t * L,
                'punto': tuple(pi[c] + xL * (pj[c] - pi[c]) for c in range(3)),
            })
        s0 += L
    return salida


# ============================================================
# EL MOTOR: el modelo del servidor, construido UNA vez
# ============================================================
class Motor:
    """
    Construye el modelo con servidor_opensees.construir_modelo (lo mismo
    que /analizar) y resuelve un patron de carga a la vez con el ciclo
    del servidor: remove del patron anterior, reset, setTime(0), patron
    nuevo, resolver_caso, extraer_resultados.
    """

    def __init__(self, modelo):
        self.modelo = modelo
        t0 = time.time()
        self.coords, self.avisos, self.restr = motor.construir_modelo(modelo)
        self.t_construir = time.time() - t0
        self.tag = TAG_BASE
        self.tag_previo = None
        self.n_resueltos = 0
        self.t_resolver = 0.0
        self.ids_nodos = [int(n['id']) for n in modelo['nodos']]
        self.ids_elem = [int(e['id']) for e in modelo['elementos']]

    def resolver(self, puntuales=(), nodales=()):
        """
        puntuales: [(eid, Px, Py, Pz, xL)] en ejes locales.
        nodales:   [(nid, fx, fy, fz)] globales.
        Devuelve (res redondeado como el servidor, memoria sin redondeo).
        """
        t0 = time.time()
        if self.tag_previo is not None:
            ops.remove('loadPattern', self.tag_previo)
        ops.reset()
        ops.setTime(0.0)
        self.tag += 1
        ops.timeSeries('Linear', self.tag)
        ops.pattern('Plain', self.tag, self.tag)
        for eid, Px, Py, Pz, xL in puntuales:
            ops.eleLoad('-ele', int(eid), '-type', '-beamPoint',
                        float(Py), float(Pz), float(xL), float(Px))
        for nid, fx, fy, fz in nodales:
            ops.load(int(nid), float(fx), float(fy), float(fz), 0.0, 0.0, 0.0)
        self.tag_previo = self.tag

        ok = motor.resolver_caso()
        if ok != 0:
            raise SystemExit('OpenSees no convergio (analyze = %d)' % ok)
        res = motor.extraer_resultados(self.modelo, self.restr)
        memoria = {
            'u': {n: [ops.nodeDisp(n, i) for i in range(1, 7)] for n in self.ids_nodos},
            'R': {n: [ops.nodeReaction(n, i) for i in range(1, 7)] for n in self.restr},
            'f': {e: list(ops.eleResponse(e, 'localForce')) for e in self.ids_elem},
        }
        self.n_resueltos += 1
        self.t_resolver += time.time() - t0
        return res, memoria


def carga_local(base, P):
    """
    (Px, Py, Pz) locales de una carga P hacia abajo, y su vector global.
    Global = (0, 0, -P); cada componente local es su producto punto con
    el versor.
    """
    g = (0.0, 0.0, -float(P))
    loc = [sum(g[c] * base[k][c] for c in range(3)) for k in ('wx', 'wy', 'wz')]
    return tuple(loc), g


# ============================================================
# ESFUERZOS Y DESPLAZAMIENTOS DENTRO DE LA VIGA CARGADA
# ============================================================
def esfuerzos_con_puntual(f, Px, Py, Pz, a, xs):
    """
    semana04 esfuerzos_internos (sin carga repartida) mas el salto de la
    carga puntual en x = a, con H(x-a) = 1 si x > a:

        N(x)  = -(N_i  + Px H)
        Vy(x) = -(Vy_i + Py H)            Vz(x) = -(Vz_i + Pz H)
        My(x) = -(My_i + x Vz_i + Pz (x-a) H)
        Mz(x) = -(Mz_i - x Vy_i - Py (x-a) H)

    Es la misma forma que la uniforme con w x -> P H y w x^2/2 ->
    P (x-a) H: la resultante de la carga a la izquierda del corte y su
    brazo. En x = a (H = 0) el momento no salta, asi que M bajo la carga
    es el mismo por los dos lados.
    """
    Ni, Vyi, Vzi, Ti, Myi, Mzi = [float(v) for v in f[:6]]
    out = {'N': [], 'Vy': [], 'Vz': [], 'T': [], 'My': [], 'Mz': []}
    for x in xs:
        H = 1.0 if x > a else 0.0
        out['N'].append(-(Ni + Px * H))
        out['Vy'].append(-(Vyi + Py * H))
        out['Vz'].append(-(Vzi + Pz * H))
        out['T'].append(-Ti)
        out['My'].append(-(Myi + x * Vzi + Pz * (x - a) * H))
        out['Mz'].append(-(Mzi - x * Vyi - Py * (x - a) * H))
    return out


def cierre_en_L(f, Px, Py, Pz, a, L, s4):
    """
    (peor error/cota, componente) de esfuerzo(L) contra f_j, con la
    cota_de_cierre de la Semana 4 (el redondeo del servidor) y las
    magnitudes de los terminos, incluidos los de la carga.
    """
    en_L = esfuerzos_con_puntual(f, Px, Py, Pz, a, [L])
    mag = s4.magnitudes_de_cierre(f, (0.0, 0.0, 0.0), L)
    b = L - a
    mag = [mag[0] + abs(Px), mag[1] + abs(Py), mag[2] + abs(Pz), mag[3],
           mag[4] + abs(Pz) * b, mag[5] + abs(Py) * b]
    cotas = s4.cota_de_cierre(L, 1.0, mag)
    peor = (0.0, 'N', 0.0, 0.0)
    for k, nombre in enumerate(('N', 'Vy', 'Vz', 'T', 'My', 'Mz')):
        err = abs(en_L[nombre][0] - float(f[6 + k]))
        c = err / cotas[k] if cotas[k] > 0 else (0.0 if err == 0 else math.inf)
        if c >= peor[0]:
            peor = (c, nombre, err, cotas[k])
    return peor


def rigidez(modelo, e, nodos, s4):
    """E, Iy, Iz tal como los recibe ops.element (la replica citada de la
    Semana 4, que lleva las lineas del servidor)."""
    secciones = {s['nombre']: s for s in modelo['secciones']}
    return s4.rigidez_como_el_servidor(e, secciones[e['seccion']],
                                       _xyz(nodos[int(e['n1'])]),
                                       _xyz(nodos[int(e['n2'])]),
                                       modelo.get('material', {}))


def flecha_biempotrada(P, a, L, x, EI):
    """
    Flecha en x de una viga biempotrada con una carga P (con signo) en a:

        x <= a:  P b^2 x^2 (3 a L - (3 a + b) x) / (6 E I L^3)
        x >= a:  la misma con x -> L - x y a <-> b

    En x = a da P a^3 b^3 / (3 E I L^3). Es la solucion particular que se
    suma a la interpolacion de Hermite de los nodos.
    """
    b = L - a
    if x <= a:
        return P * b * b * x * x * (3 * a * L - (3 * a + b) * x) / (6.0 * EI * L ** 3)
    xp = L - x
    return P * a * a * xp * xp * (3 * b * L - (3 * b + a) * xp) / (6.0 * EI * L ** 3)


def desplazamiento_en(base, L, k, ui, uj, x, carga=None):
    """
    Traslacion global (m) del punto x (m desde n1) de una barra, desde los
    6 GDL de sus nodos. Exacto para el elemento Euler-Bernoulli elastico:

      axial      u(xi) lineal                (sin carga axial en el tramo)
      local y    v(xi) Hermite con dv/dx = +rz_local
      local z    w(xi) Hermite con dw/dx = -ry_local
                 (girar +ry lleva el eje x hacia -z)

    y si la barra tiene la carga puntual, carga = (Py, Pz) en x mismo o
    (Py, Pz, a) en otro punto, la flecha de la viga biempotrada
    (flecha_biempotrada), en y con E Iz y en z con E Iy. Se comprueba contra
    los nodos de la viga partida en [e] y con Betti en [g].
    """
    ex, ey, ez = base['wx'], base['wy'], base['wz']

    def dot(v, w):
        return sum(v[c] * w[c] for c in range(3))

    ti, tj = ui[:3], uj[:3]
    ri, rj = ui[3:], uj[3:]
    xi = x / L
    N1 = 1 - 3 * xi ** 2 + 2 * xi ** 3
    N2 = xi - 2 * xi ** 2 + xi ** 3
    N3 = 3 * xi ** 2 - 2 * xi ** 3
    N4 = -xi ** 2 + xi ** 3
    u = (1 - xi) * dot(ex, ti) + xi * dot(ex, tj)
    v = (N1 * dot(ey, ti) + N2 * L * dot(ez, ri)
         + N3 * dot(ey, tj) + N4 * L * dot(ez, rj))
    w = (N1 * dot(ez, ti) - N2 * L * dot(ey, ri)
         + N3 * dot(ez, tj) - N4 * L * dot(ey, rj))
    if carga is not None:
        Py, Pz = carga[0], carga[1]
        a_carga = carga[2] if len(carga) > 2 else x
        v += flecha_biempotrada(Py, a_carga, L, x, k['E'] * k['Iz_pasa'])
        w += flecha_biempotrada(Pz, a_carga, L, x, k['E'] * k['Iy_pasa'])
    return [u * ex[c] + v * ey[c] + w * ez[c] for c in range(3)]


# Estaciones de la elastica de la viga cargada: los decimos de L (los
# nodos de la viga partida de [e], que la verifican) mas el punto de la
# carga. Solo para DIBUJAR la curva: el visor las escala, no interpola.
DECIMOS_ELASTICA = 10


def elastica(pi, pj, base, L, k, ui, uj, Py, Pz, a):
    """[{xL, x, y, z, ux, uy, uz}] de la viga cargada, en m."""
    # Redondeado antes de juntar: 1 - 0.7 no es 0.3 en coma flotante, y el
    # punto de la carga saldria repetido con largo cero.
    xs = sorted({round(i / DECIMOS_ELASTICA, 9) for i in range(DECIMOS_ELASTICA + 1)}
                | {round(a / L, 9)})
    salida = []
    for t in xs:
        u = desplazamiento_en(base, L, k, ui, uj, t * L, carga=(Py, Pz, a))
        salida.append({
            'xL': round(t, 6),
            'x': round(pi[0] + t * (pj[0] - pi[0]), 4),
            'y': round(pi[1] + t * (pj[1] - pi[1]), 4),
            'z': round(pi[2] + t * (pj[2] - pi[2]), 4),
            'ux': round(u[0], 8), 'uy': round(u[1], 8), 'uz': round(u[2], 8),
        })
    return salida


def empotramiento(Pz, a, L):
    """
    Fuerzas de empotramiento perfecto de una carga Pz (local, negativa
    hacia abajo) en a, con la convencion de localForce (fuerzas de los
    nodos sobre la barra): son las "fuerzas nodales equivalentes" que
    OpenSees ensambla con el signo cambiado. Se comprueban en [i].
    """
    P = -Pz
    b = L - a
    return {'V_i': P * b * b * (3 * a + b) / L ** 3,
            'V_j': P * a * a * (a + 3 * b) / L ** 3,
            'My_i': -P * a * b * b / L ** 2,
            'My_j': P * a * a * b / L ** 2}


# ============================================================
# CONSERVACION CON LA REGLA DE calcular.equilibrio
# ============================================================
def pesos_de_reaccion(modelo, restr):
    """
    {nodo: (cuenta_x, cuenta_y, cuenta_z)} segun calcular.equilibrio,
    sin copiar la regla: se le pasa una reaccion unitaria de a un nodo
    y se lee que sumo. Asi la cota (cuantos valores redondeados entran)
    y la suma en memoria usan la MISMA definicion que el resto del repo.
    """
    vacio = {'nombre': 'conteo', 'cargas_nodales': [], 'cargas_distribuidas': []}
    pesos = {}
    for nid in restr:
        fila = {'id': nid, 'fx': 1.0, 'fy': 1.0, 'fz': 1.0, 'mx': 0.0, 'my': 0.0, 'mz': 0.0}
        eq = calcular.equilibrio(modelo, vacio, {'reacciones': [fila]})
        pesos[nid] = tuple(int(round(v)) for v in eq['reaccion_kN'])
    return pesos


def conservacion(modelo, res, memoria, carga_global, pesos, s4):
    """El equilibrio del contrato (claves de calcular.equilibrio) con la
    carga puntual SUMADA a 'aplicada_kN', y el veredicto con su cota."""
    vacio = {'nombre': 'MOVIL', 'cargas_nodales': [], 'cargas_distribuidas': []}
    eq = calcular.equilibrio(modelo, vacio, res)
    aplicada = [eq['aplicada_kN'][i] + carga_global[i] for i in range(3)]
    reaccion = eq['reaccion_kN']
    error = [aplicada[i] + reaccion[i] for i in range(3)]

    n = [sum(p[i] for p in pesos.values()) for i in range(3)]
    en_memoria = [sum(pesos[nid][i] * memoria['R'][nid][i] for nid in pesos) for i in range(3)]
    err_mem = [aplicada[i] + en_memoria[i] for i in range(3)]
    tam = [abs(aplicada[i]) + sum(abs(float(r[k])) for r in res['reacciones'])
           for i, k in enumerate(('fx', 'fy', 'fz'))]
    cota = [n[i] * s4.COTA_REDONDEO + s4.FACTOR_COMA_FLOTANTE * tam[i] for i in range(3)]
    return {
        'equilibrio': {
            'aplicada_kN': [round(v, 4) for v in aplicada],
            'reaccion_kN': [round(v, 4) for v in reaccion],
            'error_kN': [round(v, 8) for v in error],
            'cargas_sin_convertir': eq['cargas_sin_convertir'],
            'nodos_en_diafragma': eq['nodos_en_diafragma'],
            'confiable': eq['confiable'],
        },
        'error': error, 'cota': cota, 'n': n, 'err_mem': err_mem,
        'reaccion': reaccion,
    }


# ============================================================
# UNA POSICION
# ============================================================
def bloque_posicion(i, pos, P, modelo, mot, pesos, s4, nodos, por_id):
    e = por_id[pos['elemento']]
    base, L = ejes_de(e, nodos)
    (Px, Py, Pz), g = carga_local(base, P)
    res, mem = mot.resolver(puntuales=[(pos['elemento'], Px, Py, Pz, pos['xL'])])

    # --- conservacion ---
    cons = conservacion(modelo, res, mem, g, pesos, s4)

    # --- la viga cargada, con f redondeado como el servidor ---
    f = next(x['f'] for x in res['fuerzas_elementos'] if int(x['id']) == pos['elemento'])
    a = pos['a']
    Vi, Vj = float(f[2]), float(f[8])
    Myi, Myj = float(f[4]), float(f[10])
    suma_V = Vi + Vj + Pz
    cierre = cierre_en_L(f, Px, Py, Pz, a, L, s4)
    M_carga = esfuerzos_con_puntual(f, Px, Py, Pz, a, [a])['My'][0]

    palanca_j = -Pz * a / L
    palanca_i = -Pz - palanca_j
    momentos = (Myi + Myj) / L
    emp = empotramiento(Pz, a, L)
    # [d] Vz_j - palanca = (My_i + My_j)/L: mezcla Vz_j y los dos
    # momentos redondeados (el ultimo dividido por L).
    err_explica = abs((Vj - palanca_j) - momentos)
    cota_explica = s4.COTA_REDONDEO * (1.0 + 2.0 / L) + s4.FACTOR_COMA_FLOTANTE * (
        abs(Vj) + abs(palanca_j) + (abs(Myi) + abs(Myj)) / L)

    # --- desplazamientos ---
    k = rigidez(modelo, e, nodos, s4)
    u_carga = desplazamiento_en(base, L, k, mem['u'][int(e['n1'])], mem['u'][int(e['n2'])],
                                a, carga=(Py, Pz))
    curva = elastica(_xyz(nodos[int(e['n1'])]), _xyz(nodos[int(e['n2'])]), base, L, k,
                     mem['u'][int(e['n1'])], mem['u'][int(e['n2'])], Py, Pz, a)
    maximo, nodo_max = 0.0, -1
    uz_min, nodo_uz = 0.0, -1
    for d in res['desplazamientos']:
        norma = math.sqrt(d['ux'] ** 2 + d['uy'] ** 2 + d['uz'] ** 2)
        if norma > maximo:
            maximo, nodo_max = norma, int(d['id'])
        if d['uz'] < uz_min:
            uz_min, nodo_uz = d['uz'], int(d['id'])

    cumple_z = abs(cons['error'][2]) <= cons['cota'][2]
    cumple_h = (abs(cons['error'][0]) <= cons['cota'][0]
                and abs(cons['error'][1]) <= cons['cota'][1])
    cota_V = 2 * s4.COTA_REDONDEO + s4.FACTOR_COMA_FLOTANTE * (abs(Vi) + abs(Vj) + abs(Pz))
    cumple_V = abs(suma_V) <= cota_V
    cumple_cierre = cierre[0] <= 1.0
    cumple_explica = err_explica <= cota_explica
    cumple = cumple_z and cumple_h and cumple_V and cumple_cierre and cumple_explica

    n_i, n_j = int(e['n1']), int(e['n2'])
    pct_i = 100.0 * Vi / (-Pz) if Pz else 0.0
    explicacion = ('palanca %.1f / %.1f kN; los momentos de extremo (My_i + My_j)/L = %+.2f kN '
                   'corren %.1f kN hacia el nodo %d'
                   % (palanca_i, palanca_j, momentos, abs(momentos),
                      n_i if momentos < 0 else n_j))

    bloque = {
        'indice': i,
        'elemento': pos['elemento'],
        'xL': round(pos['xL'], 6),
        'a_m': round(a, 4),
        'L_m': round(L, 4),
        's_m': round(pos['s'], 4),
        'x': round(pos['punto'][0], 4),
        'y': round(pos['punto'][1], 4),
        'z': round(pos['punto'][2], 4),
        'Px_local_kN': round(Px, 4),
        'Py_local_kN': round(Py, 4),
        'Pz_local_kN': round(Pz, 4),
        'max_desplazamiento_mm': round(maximo * 1000.0, 4),
        'nodo_max_desplazamiento': nodo_max,
        'uz_min_mm': round(uz_min * 1000.0, 4),
        'nodo_uz_min': nodo_uz,
        'u_carga_m': [round(v, 8) for v in u_carga],
        'uz_bajo_carga_mm': round(u_carga[2] * 1000.0, 4),
        'M_bajo_carga_kNm': round(M_carga, 4),
        'elastica': curva,
        'desplazamientos': res['desplazamientos'],
        'reacciones': res['reacciones'],
        'equilibrio': cons['equilibrio'],
        'reparto': {
            'nodo_i': n_i,
            'nodo_j': n_j,
            'llega_a_i': ', '.join(que_llega_a(modelo, n_i)),
            'llega_a_j': ', '.join(que_llega_a(modelo, n_j)),
            'V_i_kN': round(Vi, 4),
            'V_j_kN': round(Vj, 4),
            'porcentaje_i': round(pct_i, 2),
            'porcentaje_j': round(100.0 - pct_i, 2),
            'palanca_i_kN': round(palanca_i, 4),
            'palanca_j_kN': round(palanca_j, 4),
            'empotrado_V_i_kN': round(emp['V_i'], 4),
            'empotrado_V_j_kN': round(emp['V_j'], 4),
            'empotrado_My_i_kNm': round(emp['My_i'], 4),
            'empotrado_My_j_kNm': round(emp['My_j'], 4),
            'My_i_kNm': round(Myi, 4),
            'My_j_kNm': round(Myj, 4),
            'momentos_sobre_L_kN': round(momentos, 4),
            'f': [round(float(v), 4) for v in f],
            'explicacion': explicacion,
        },
        'conservacion': {
            'P_kN': round(P, 4),
            'suma_Rz_kN': round(cons['reaccion'][2], 4),
            'error_kN': round(cons['error'][2], 8),
            'cota_kN': round(cons['cota'][2], 8),
            'apoyos_z': cons['n'][2],
            'suma_Rx_kN': round(cons['reaccion'][0], 4),
            'suma_Ry_kN': round(cons['reaccion'][1], 4),
            'cota_horizontal_kN': round(max(cons['cota'][0], cons['cota'][1]), 8),
            'apoyos_xy': max(cons['n'][0], cons['n'][1]),
            'error_en_memoria_kN': float('%.3e' % cons['err_mem'][2]),
            'suma_V_mas_Pz_kN': round(suma_V, 8),
            'cierre_cociente': round(cierre[0], 6),
            'cierre_componente': cierre[1],
            'cumple': bool(cumple),
        },
    }
    detalle = {
        'mem': mem, 'res': res, 'Pz': Pz, 'Py': Py, 'Px': Px, 'base': base, 'L': L,
        'rigidez': k, 'cumple_z': cumple_z, 'cumple_h': cumple_h,
        'cumple_V': cumple_V, 'cumple_cierre': cumple_cierre,
        'cumple_explica': cumple_explica, 'err_explica': err_explica,
        'cota_explica': cota_explica, 'cons': cons, 'cierre': cierre,
        'cota_V': cota_V,
    }
    return bloque, detalle


# ============================================================
# VERIFICACIONES GLOBALES
# ============================================================
def _max_dif_u(m1, m2, nodos_ids, gdl=range(6)):
    peor, donde = 0.0, None
    for n in nodos_ids:
        for i in gdl:
            d = abs(m1['u'][n][i] - m2['u'][n][i])
            if d > peor:
                peor, donde = d, (n, i)
    return peor, donde


def _max_dif_R(m1, m2):
    peor = 0.0
    for n in m1['R']:
        for i in range(6):
            peor = max(peor, abs(m1['R'][n][i] - m2['R'][n][i]))
    return peor


def _en(bloques, detalles, eid, xL):
    for b, d in zip(bloques, detalles):
        if b['elemento'] == eid and abs(b['xL'] - xL) < 1e-9:
            return b, d
    return None, None


def global_viga_partida(modelo, P, eid, fracciones, s4, globales):
    """
    [e] La viga eid partida en 10 tramos (subdividir de la Semana 3): hay
    un nodo en cada decimo, y la carga NODAL en el que corresponde tiene
    que dar lo mismo que beamPoint en el modelo sin partir. Resuelve
    todo sobre modelos propios, asi que va despues de las posiciones.
    """
    vp = viga_partida()
    nodos = {int(n['id']): n for n in modelo['nodos']}
    por_id = {int(e['id']): e for e in modelo['elementos']}
    e = por_id[eid]
    base, L = ejes_de(e, nodos)
    (Px, Py, Pz), g = carga_local(base, P)
    k = rigidez(modelo, e, nodos, s4)

    veces = 10
    partido = vp.subdividir(modelo, [eid], veces)
    ids_orig = [int(n['id']) for n in modelo['nodos']]
    max_nodo = max(ids_orig)

    for xL in fracciones:
        paso = int(round(xL * veces))
        if abs(paso / veces - xL) > 1e-12:
            raise SystemExit('xL = %g no cae en un nodo de la viga partida en %d' % (xL, veces))
        a = xL * L

        m_base = Motor(modelo)
        _res_b, mem_b = m_base.resolver(puntuales=[(eid, Px, Py, Pz, xL)])
        f_b = mem_b['f'][eid]
        M_b = esfuerzos_con_puntual(f_b, Px, Py, Pz, a, [a])['My'][0]
        u_b = desplazamiento_en(base, L, k, mem_b['u'][int(e['n1'])], mem_b['u'][int(e['n2'])],
                                a, carga=(Py, Pz))

        m_part = Motor(partido)
        nodo_carga = max_nodo + paso
        # El nodo nuevo de la fraccion 'paso': subdividir los numera en
        # orden desde n1. Se confirma por coordenadas, no se supone.
        pn = next(n for n in partido['nodos'] if int(n['id']) == nodo_carga)
        esperado = [float(nodos[int(e['n1'])][c]) + xL * (float(nodos[int(e['n2'])][c])
                    - float(nodos[int(e['n1'])][c])) for c in 'xyz']
        if max(abs(float(pn[c]) - esperado[i]) for i, c in enumerate('xyz')) > 1e-9:
            raise SystemExit('el nodo %d de la viga partida no esta en xL = %g' % (nodo_carga, xL))
        _res_p, mem_p = m_part.resolver(nodales=[(nodo_carga, g[0], g[1], g[2])])

        du, donde = _max_dif_u(mem_b, mem_p, ids_orig)
        dR = _max_dif_R(mem_b, mem_p)
        # Momento bajo la carga en la partida: el tramo que TERMINA en el
        # nodo cargado, esfuerzo interno en j = +f_j.
        tramo = next(x for x in partido['elementos'] if int(x['n2']) == nodo_carga)
        M_p = float(mem_p['f'][int(tramo['id'])][10])
        tramo_i = next(x for x in partido['elementos']
                       if int(x['id']) == eid)            # el que conserva n1
        V_p = float(mem_p['f'][int(tramo_i['id'])][2])
        V_b = float(f_b[2])
        du_carga = max(abs(u_b[c] - mem_p['u'][nodo_carga][c]) for c in range(3))

        # La elastica que dibuja el visor: en cada decimo de la viga sin
        # partir (Hermite + biempotrada con la carga en a) contra el nodo de
        # la partida que esta ahi. Cubre los dos lados de la carga.
        du_curva, peor_t = 0.0, None
        ui_b, uj_b = mem_b['u'][int(e['n1'])], mem_b['u'][int(e['n2'])]
        for t in range(1, veces):
            nid = max_nodo + t
            pt = next(n for n in partido['nodos'] if int(n['id']) == nid)
            en_t = [float(nodos[int(e['n1'])][c]) + t / veces * (float(nodos[int(e['n2'])][c])
                    - float(nodos[int(e['n1'])][c])) for c in 'xyz']
            if max(abs(float(pt[c]) - en_t[i]) for i, c in enumerate('xyz')) > 1e-9:
                raise SystemExit('el nodo %d de la viga partida no esta en xL = %g' % (nid, t / veces))
            u_t = desplazamiento_en(base, L, k, ui_b, uj_b, t / veces * L, carga=(Py, Pz, a))
            d = max(abs(u_t[c] - mem_p['u'][nid][c]) for c in range(3))
            if d >= du_curva:
                du_curva, peor_t = d, t / veces

        ok = (du <= RESOLUCION_U and dR <= RESOLUCION_F and abs(M_b - M_p) <= RESOLUCION_F
              and abs(V_b - V_p) <= RESOLUCION_F and du_carga <= RESOLUCION_U
              and du_curva <= RESOLUCION_U)
        check(ok, '[e] beamPoint = viga %d partida en %d con carga nodal en el nodo %d (xL = %.2f)'
              % (eid, veces, nodo_carga, xL),
              'max |du| %.1e m en %s de %d nodos; max |dR| %.1e kN; M bajo la carga %.4f / %.4f '
              'kN*m (dif %.1e); V_i %.4f / %.4f; flecha bajo la carga %.6f / %.6f mm (dif %.1e m); '
              'elastica en los %d nodos interiores de la partida: max |du| %.1e m (xL = %.1f)'
              % (du, donde, len(ids_orig), dR, M_b, M_p, abs(M_b - M_p), V_b, V_p,
                 u_b[2] * 1000, mem_p['u'][nodo_carga][2] * 1000, du_carga,
                 veces - 1, du_curva, peor_t))
        globales.append({
            'nombre': 'beamPoint contra viga partida',
            'detalle': 'viga %d, xL = %.2f, partida en %d, carga nodal en el nodo %d'
                       % (eid, xL, veces, nodo_carga),
            'max_dif_desplazamiento_m': du, 'max_dif_reaccion_kN': dR,
            'M_beamPoint_kNm': round(M_b, 6), 'M_partida_kNm': round(M_p, 6),
            'uz_bajo_carga_calculada_mm': round(u_b[2] * 1000, 6),
            'uz_nodo_partida_mm': round(mem_p['u'][nodo_carga][2] * 1000, 6),
            'dif_bajo_carga_m': du_carga,
            'max_dif_elastica_m': du_curva,
            'criterio': 'desplazamientos <= %g m, fuerzas <= %g kN' % (RESOLUCION_U, RESOLUCION_F),
            'cumple': bool(ok)})


def global_continuidad(mot, modelo, P, rec, globales):
    """[f] Cruzar un nodo: fin de una viga, inicio de la siguiente y la
    carga nodal en el nodo comun son la misma carga."""
    nodos = {int(n['id']): n for n in modelo['nodos']}
    por_id = {int(e['id']): e for e in modelo['elementos']}
    # El primer nodo interior del recorrido que no tiene columna: donde
    # la pregunta importa (el que cuelga).
    candidatos = [i for i in range(1, len(rec['nodos']) - 1)
                  if not any(t in ('columna', 'muro') for t in que_llega_a(modelo, rec['nodos'][i]))]
    i = candidatos[0] if candidatos else 1
    nid = rec['nodos'][i]
    e1, e2 = por_id[rec['elementos'][i - 1]], por_id[rec['elementos'][i]]
    xL1 = 1.0 if int(e1['n2']) == nid else 0.0
    xL2 = 0.0 if int(e2['n1']) == nid else 1.0
    b1, _ = ejes_de(e1, nodos)
    b2, _ = ejes_de(e2, nodos)
    (px1, py1, pz1), g = carga_local(b1, P)
    (px2, py2, pz2), _ = carga_local(b2, P)
    _r, m1 = mot.resolver(puntuales=[(int(e1['id']), px1, py1, pz1, xL1)])
    _r, m2 = mot.resolver(puntuales=[(int(e2['id']), px2, py2, pz2, xL2)])
    _r, m3 = mot.resolver(nodales=[(nid, g[0], g[1], g[2])])
    ids = list(m1['u'])
    d12, _ = _max_dif_u(m1, m2, ids)
    d13, _ = _max_dif_u(m1, m3, ids)
    dR = max(_max_dif_R(m1, m2), _max_dif_R(m1, m3))
    ok = max(d12, d13) <= RESOLUCION_U and dR <= RESOLUCION_F
    check(ok, '[f] continuidad en el nodo %d: viga %d xL=%g = viga %d xL=%g = carga nodal'
          % (nid, int(e1['id']), xL1, int(e2['id']), xL2),
          'uz(%d) = %.4f / %.4f / %.4f mm; max |du| %.1e y %.1e m; max |dR| %.1e kN'
          % (nid, m1['u'][nid][2] * 1000, m2['u'][nid][2] * 1000, m3['u'][nid][2] * 1000,
             d12, d13, dR))
    globales.append({
        'nombre': 'continuidad al cruzar un nodo',
        'detalle': 'nodo %d (%s): viga %d en xL=%g, viga %d en xL=%g y carga nodal'
                   % (nid, ', '.join(que_llega_a(modelo, nid)), int(e1['id']), xL1,
                      int(e2['id']), xL2),
        'uz_nodo_mm': round(m3['u'][nid][2] * 1000, 6),
        'max_dif_desplazamiento_m': max(d12, d13), 'max_dif_reaccion_kN': dR,
        'criterio': 'desplazamientos <= %g m, fuerzas <= %g kN' % (RESOLUCION_U, RESOLUCION_F),
        'cumple': bool(ok)})


def global_betti(bloques, detalles, modelo, s4, globales, A, B):
    """
    [g] Betti con la misma P en dos puntos interiores A y B:
    u(A | P en B) . e_P = u(B | P en A) . e_P. El desplazamiento en un
    punto interior sale de desplazamiento_en (Hermite): la prueba cubre
    la simetria del solver y esa interpolacion.
    """
    nodos = {int(n['id']): n for n in modelo['nodos']}
    por_id = {int(e['id']): e for e in modelo['elementos']}
    bA, dA = _en(bloques, detalles, *A)
    bB, dB = _en(bloques, detalles, *B)
    if bA is None or bB is None:
        check(False, '[g] Betti: no estan las posiciones %s y %s' % (A, B))
        return
    eA, eB = por_id[A[0]], por_id[B[0]]
    # desplazamiento en A cuando la carga esta en B (A no esta cargado)
    uA_B = desplazamiento_en(dA['base'], dA['L'], dA['rigidez'],
                             dB['mem']['u'][int(eA['n1'])], dB['mem']['u'][int(eA['n2'])],
                             A[1] * dA['L'])
    uB_A = desplazamiento_en(dB['base'], dB['L'], dB['rigidez'],
                             dA['mem']['u'][int(eB['n1'])], dA['mem']['u'][int(eB['n2'])],
                             B[1] * dB['L'])
    # P es la misma y vertical: el trabajo reciproco se reduce a uz.
    dif = abs(uA_B[2] - uB_A[2])
    rel = dif / max(abs(uA_B[2]), 1e-30)
    ok = dif <= RESOLUCION_U
    check(ok, '[g] Betti: uz en %d xL=%.2f con P en %d xL=%.2f = al reves'
          % (A[0], A[1], B[0], B[1]),
          '%.12e / %.12e m, dif %.1e m (%.1e relativo)' % (uA_B[2], uB_A[2], dif, rel))
    globales.append({
        'nombre': 'reciprocidad de Betti',
        'detalle': 'puntos viga %d xL=%.2f y viga %d xL=%.2f' % (A[0], A[1], B[0], B[1]),
        'uz_A_por_B_m': uA_B[2], 'uz_B_por_A_m': uB_A[2],
        'dif_m': dif, 'dif_relativa': rel,
        'criterio': 'dif <= %g m' % RESOLUCION_U, 'cumple': bool(ok)})


def global_superposicion(mot, bloques, detalles, globales, A, B):
    """[h] Las dos cargas en una sola corrida = la suma de las dos corridas."""
    bA, dA = _en(bloques, detalles, *A)
    bB, dB = _en(bloques, detalles, *B)
    _r, mAB = mot.resolver(puntuales=[
        (A[0], dA['Px'], dA['Py'], dA['Pz'], A[1]),
        (B[0], dB['Px'], dB['Py'], dB['Pz'], B[1])])
    peor_u = max(abs(mAB['u'][n][i] - dA['mem']['u'][n][i] - dB['mem']['u'][n][i])
                 for n in mAB['u'] for i in range(6))
    peor_R = max(abs(mAB['R'][n][i] - dA['mem']['R'][n][i] - dB['mem']['R'][n][i])
                 for n in mAB['R'] for i in range(6))
    peor_f = max(abs(mAB['f'][e][i] - dA['mem']['f'][e][i] - dB['mem']['f'][e][i])
                 for e in mAB['f'] for i in range(12))
    ok = peor_u <= RESOLUCION_U and peor_R <= RESOLUCION_F and peor_f <= RESOLUCION_F
    check(ok, '[h] superposicion: %d xL=%.2f + %d xL=%.2f en una corrida = suma de las dos'
          % (A[0], A[1], B[0], B[1]),
          'max |du| %.1e m, max |dR| %.1e kN, max |df| %.1e kN (todos los nodos, apoyos y barras)'
          % (peor_u, peor_R, peor_f))
    globales.append({
        'nombre': 'superposicion de dos posiciones',
        'detalle': 'viga %d xL=%.2f y viga %d xL=%.2f' % (A[0], A[1], B[0], B[1]),
        'max_dif_desplazamiento_m': peor_u, 'max_dif_reaccion_kN': peor_R,
        'max_dif_fuerza_kN': peor_f,
        'criterio': 'desplazamientos <= %g m, fuerzas <= %g kN' % (RESOLUCION_U, RESOLUCION_F),
        'cumple': bool(ok)})


def global_por_que_no(mot, modelo, P, bloques, detalles, globales, eid):
    """
    Dos atajos que NO se usan, medidos (informativo, no bloquea):
      - funciones de forma lineales: P(1-xi) y P xi como cargas nodales;
      - interpolar entre dos posiciones vecinas en vez de resolver.
    """
    nodos = {int(n['id']): n for n in modelo['nodos']}
    por_id = {int(e['id']): e for e in modelo['elementos']}
    e = por_id[eid]
    base, L = ejes_de(e, nodos)
    (Px, Py, Pz), g = carga_local(base, P)
    b5, d5 = _en(bloques, detalles, eid, 0.5)

    # --- lineal ---
    xi = 0.5
    _r, mlin = mot.resolver(nodales=[(int(e['n1']), 0, 0, g[2] * (1 - xi)),
                                     (int(e['n2']), 0, 0, g[2] * xi)])
    f = mlin['f'][eid]
    M_lin = esfuerzos_con_puntual(f, 0, 0, 0, xi * L, [xi * L])['My'][0]
    M_ex = esfuerzos_con_puntual(d5['mem']['f'][eid], Px, Py, Pz, xi * L, [xi * L])['My'][0]
    n_i, n_j = int(e['n1']), int(e['n2'])
    decir('  [--] funciones de forma lineales en la viga %d a mitad: M bajo la carga %.2f kN*m '
          'contra %.2f exacto' % (eid, M_lin, M_ex))
    decir('       uz(%d) %.4f contra %.4f mm; uz(%d) %.4f contra %.4f mm'
          % (n_i, mlin['u'][n_i][2] * 1000, d5['mem']['u'][n_i][2] * 1000,
             n_j, mlin['u'][n_j][2] * 1000, d5['mem']['u'][n_j][2] * 1000))

    # --- interpolar ---
    # Lo que se veria si el visor mezclara dos posiciones vecinas: el
    # promedio de sus DIAGRAMAS y de sus DEFORMADAS en el punto intermedio
    # (no solo el numero "M bajo la carga", que es suave y engana: el
    # diagrama tiene el quiebre donde esta la carga, y al promediar dos
    # quiebres en otros puntos se aplana el pico).
    bajo = [(b, d) for b, d in zip(bloques, detalles) if b['elemento'] == eid]
    bajo.sort(key=lambda bd: bd[0]['xL'])
    (b1, d1), (b2, d2) = bajo[1], bajo[2]
    xm = (b1['xL'] + b2['xL']) / 2.0
    _r, mm = mot.resolver(puntuales=[(eid, Px, Py, Pz, xm)])
    M_real = esfuerzos_con_puntual(mm['f'][eid], Px, Py, Pz, xm * L, [xm * L])['My'][0]
    M_int = (b1['M_bajo_carga_kNm'] + b2['M_bajo_carga_kNm']) / 2.0
    err_pct = 100.0 * abs(M_int - M_real) / max(abs(M_real), 1e-12)
    M_diag = [esfuerzos_con_puntual(d['mem']['f'][eid], Px, Py, Pz, b['xL'] * L, [xm * L])['My'][0]
              for b, d in ((b1, d1), (b2, d2))]
    M_diag_int = (M_diag[0] + M_diag[1]) / 2.0
    err_diag = 100.0 * abs(M_diag_int - M_real) / max(abs(M_real), 1e-12)
    k = rigidez(modelo, e, nodos, exportador_s4())
    uz_def = [desplazamiento_en(base, L, k, d['mem']['u'][n_i], d['mem']['u'][n_j], xm * L,
                                carga=(Py, Pz, b['xL'] * L))[2] for b, d in ((b1, d1), (b2, d2))]
    uz_int = (uz_def[0] + uz_def[1]) / 2.0
    uz_real = desplazamiento_en(base, L, k, mm['u'][n_i], mm['u'][n_j], xm * L, carga=(Py, Pz))[2]
    err_uz = 100.0 * abs(uz_int - uz_real) / max(abs(uz_real), 1e-30)
    decir('  [--] interpolar entre xL=%.2f y %.2f de la viga %d, carga en xL=%.2f:'
          % (b1['xL'], b2['xL'], eid, xm))
    decir('       M bajo la carga (el numero) %.2f interpolado contra %.2f resuelto kN*m (%.1f %%)'
          % (M_int, M_real, err_pct))
    decir('       diagrama My en esa seccion %.2f promediado contra %.2f resuelto kN*m (%.1f %%)'
          % (M_diag_int, M_real, err_diag))
    decir('       deformada uz en ese punto %.4f promediada contra %.4f resuelta mm (%.1f %%)'
          % (uz_int * 1000, uz_real * 1000, err_uz))
    globales.append({
        'nombre': 'por que no funciones de forma lineales',
        'detalle': 'viga %d a mitad de vano, P(1-xi) y P xi como cargas nodales' % eid,
        'M_lineal_kNm': round(M_lin, 4), 'M_exacto_kNm': round(M_ex, 4),
        'uz_i_lineal_mm': round(mlin['u'][n_i][2] * 1000, 6),
        'uz_i_exacto_mm': round(d5['mem']['u'][n_i][2] * 1000, 6),
        'uz_j_lineal_mm': round(mlin['u'][n_j][2] * 1000, 6),
        'uz_j_exacto_mm': round(d5['mem']['u'][n_j][2] * 1000, 6),
        'informativo': True})
    globales.append({
        'nombre': 'por que no interpolar entre posiciones',
        'detalle': 'viga %d, xL=%.2f entre %.2f y %.2f' % (eid, xm, b1['xL'], b2['xL']),
        'M_interpolado_kNm': round(M_int, 4), 'M_resuelto_kNm': round(M_real, 4),
        'error_pct': round(err_pct, 2),
        'M_diagrama_promediado_kNm': round(M_diag_int, 4), 'error_diagrama_pct': round(err_diag, 2),
        'uz_promediada_mm': round(uz_int * 1000, 6), 'uz_resuelta_mm': round(uz_real * 1000, 6),
        'error_uz_pct': round(err_uz, 2), 'informativo': True})


def global_empotramiento(P, globales):
    """
    [i] La formula de empotramiento perfecto contra OpenSees: una viga
    aislada biempotrada de 5 m con la carga en xL = 0.3. Borra el modelo
    del edificio (ops.wipe), por eso va al final.
    """
    L, xL = 5.0, 0.3
    a = xL * L
    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 6)
    ops.node(1, 0.0, 0.0, 0.0)
    ops.node(2, L, 0.0, 0.0)
    ops.fix(1, 1, 1, 1, 1, 1, 1)
    # El ux del nodo 2 queda LIBRE: con los 12 GDL fijos el sistema tiene
    # 0 ecuaciones y LAPACK aborta el proceso (DGBSV, parametro 9 ilegal).
    # No cambia nada de lo que se mide: la carga no tiene componente axial
    # y en el elemento elastico lineal el axial no se acopla con la flexion.
    ops.fix(2, 0, 1, 1, 1, 1, 1)
    ops.geomTransf('Linear', 1, 0.0, 0.0, 1.0)
    ops.element('elasticBeamColumn', 1, 1, 2, 0.48, 2.5e7, 1.0e7, 0.03, 0.0256, 0.0144, 1)
    ops.timeSeries('Linear', 1)
    ops.pattern('Plain', 1, 1)
    ops.eleLoad('-ele', 1, '-type', '-beamPoint', 0.0, -P, xL, 0.0)
    motor.resolver_caso()
    f = ops.eleResponse(1, 'localForce')
    emp = empotramiento(-P, a, L)
    difs = [abs(f[2] - emp['V_i']), abs(f[8] - emp['V_j']),
            abs(f[4] - emp['My_i']), abs(f[10] - emp['My_j'])]
    ok = max(difs) <= RESOLUCION_F
    check(ok, '[i] empotramiento perfecto: formula = OpenSees (biempotrada L=5, xL=0.3)',
          'V_i %.4f / %.4f, V_j %.4f / %.4f, My_i %.4f / %.4f, My_j %.4f / %.4f; peor %.1e'
          % (f[2], emp['V_i'], f[8], emp['V_j'], f[4], emp['My_i'], f[10], emp['My_j'],
             max(difs)))
    globales.append({
        'nombre': 'fuerzas de empotramiento perfecto',
        'detalle': 'viga biempotrada aislada L = 5 m, P = %g kN en xL = 0.3' % P,
        'opensees': [round(f[2], 6), round(f[8], 6), round(f[4], 6), round(f[10], 6)],
        'formula': [round(emp['V_i'], 6), round(emp['V_j'], 6),
                    round(emp['My_i'], 6), round(emp['My_j'], 6)],
        'max_dif': max(difs), 'criterio': '<= %g' % RESOLUCION_F, 'cumple': bool(ok)})


# ============================================================
# [j] EL JSON CONTRA LAS CLASES C#
# ============================================================
def campos_de_clases(ruta):
    """{clase: {campo: tipo}} de un .cs. Es la de
    semana04/test_contrato_semana04.py (comentarios fuera, llave de cierre
    por profundidad, 'public <tipo> a, b;' sin propiedades)."""
    with io.open(ruta, encoding='utf-8') as f:
        src = f.read()
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    src = re.sub(r'//[^\n]*', '', src)
    clases = {}
    for m in re.finditer(r'class\s+(\w+)\s*\{', src):
        i = m.end() - 1
        prof, j = 0, i
        while j < len(src):
            if src[j] == '{':
                prof += 1
            elif src[j] == '}':
                prof -= 1
                if prof == 0:
                    break
            j += 1
        campos = {}
        for d in re.finditer(
                r'public\s+([\w<>\[\]\.]+)\s+([\w\s,]+?)\s*(?:=[^;]*)?;', src[i:j]):
            if '(' in d.group(2):
                continue
            for nom in d.group(2).split(','):
                nom = nom.strip()
                if nom and re.fullmatch(r'\w+', nom):
                    campos[nom] = d.group(1)
        clases[m.group(1)] = campos
    return clases


def _tipo_calza(tipo, valor):
    if tipo == 'int':
        return isinstance(valor, int) and not isinstance(valor, bool)
    if tipo == 'float':
        return isinstance(valor, (int, float)) and not isinstance(valor, bool) \
            and math.isfinite(valor)
    if tipo == 'bool':
        return isinstance(valor, bool)
    if tipo == 'string':
        return isinstance(valor, str)
    if tipo.endswith('[]'):
        return isinstance(valor, list) and all(_tipo_calza(tipo[:-2], v) for v in valor)
    if tipo.startswith('List<'):
        return isinstance(valor, list) and all(isinstance(v, dict) for v in valor)
    return isinstance(valor, dict)


def verificar_contrato_cs(anexo):
    if not os.path.isfile(CS_VISOR):
        check(False, '[j] falta %s' % os.path.relpath(CS_VISOR, rutas.RAIZ))
        return
    clases = campos_de_clases(CS_MODELO)
    clases.update(campos_de_clases(CS_VISOR))
    posiciones_ = anexo['posiciones']
    objetos = {
        'AnexoCargaMovil': [anexo],
        'InfoMovil': [anexo['info']],
        'RecorridoMovil': [anexo['recorrido']],
        'VerificacionMovil': anexo['info']['verificaciones'],
        'PosicionMovil': posiciones_,
        'PuntoElasticaMovil': [pt for p in posiciones_ for pt in p['elastica']],
        'RepartoMovil': [p['reparto'] for p in posiciones_],
        'ConservacionMovil': [p['conservacion'] for p in posiciones_],
        'EquilibrioCaso': [p['equilibrio'] for p in posiciones_],
        'DespNodo': [d for p in posiciones_ for d in p['desplazamientos']],
        'ReacNodo': [r for p in posiciones_ for r in p['reacciones']],
    }
    malos = []
    for clase, objs in objetos.items():
        campos = clases.get(clase)
        if campos is None:
            malos.append('no existe la clase C# %s' % clase)
            continue
        claves = set()
        for o in objs:
            claves |= set(o)
            for c in campos:
                if c not in o:
                    malos.append('%s.%s no viene en el JSON' % (clase, c))
                    break
        for c in sorted(claves - set(campos)):
            malos.append('clave "%s" sin campo en %s' % (c, clase))
        for o in objs[:50]:
            for c, t in campos.items():
                if c in o and not _tipo_calza(t, o[c]):
                    malos.append('%s.%s es %s y el JSON trae %r' % (clase, c, t, type(o[c]).__name__))
        # arreglos de arreglos: JsonUtility los deja vacios sin avisar
        for o in objs[:5]:
            for c, v in o.items():
                if isinstance(v, list) and v and isinstance(v[0], list):
                    malos.append('%s.%s es un arreglo de arreglos' % (clase, c))
    malos = sorted(set(malos))
    check(not malos, '[j] el JSON calza con las clases C# en las dos direcciones '
          '(%d clases, %d objetos)' % (len(objetos), sum(len(v) for v in objetos.values())),
          '; '.join(malos[:8]))


# ============================================================
# EL MODELO QUE DIBUJA UNITY ES ESTE
# ============================================================
def comparar_con_unity(modelo, ed):
    """Los ids y coordenadas de data/unity/<ed>.json (lo que dibuja el
    visor) tienen que ser los del modelo que se resolvio: si no, la
    deformada se pegaria a otros nodos sin ningun error."""
    ruta = rutas.unity(ed)
    try:
        with io.open(ruta, encoding='utf-8') as f:
            vista = json.load(f)
    except (OSError, ValueError) as ex:
        check(False, 'no pude leer %s: %s' % (os.path.relpath(ruta, rutas.RAIZ), ex))
        return
    a = {int(n['id']): _xyz(n) for n in modelo['nodos']}
    b = {int(n['id']): _xyz(n) for n in vista.get('nodos', [])}
    distintos = [n for n in a if n not in b or max(abs(a[n][c] - b[n][c]) for c in range(3)) > 1e-6]
    ea = {int(e['id']): (int(e['n1']), int(e['n2'])) for e in modelo['elementos']}
    eb = {int(e['id']): (int(e['n1']), int(e['n2'])) for e in vista.get('elementos', [])}
    check(set(a) == set(b) and not distintos and ea == eb,
          'el modelo resuelto es el que dibuja Unity (%s): %d nodos y %d elementos iguales'
          % (os.path.relpath(ruta, rutas.RAIZ), len(a), len(ea)),
          '' if not distintos else 'nodos distintos: %s' % distintos[:10])

    en_escena = os.path.join(rutas.STREAMING, 'modelo_unity_edificio.json')
    try:
        with io.open(en_escena, encoding='utf-8') as f:
            esc = json.load(f)
        ids = {int(n['id']) for n in esc.get('nodos', [])}
        if ids != set(a):
            decir('  [AVISO] StreamingAssets/modelo_unity_edificio.json no tiene los nodos de %s: '
                  'sincroniza con  python comun/lanzar_unity.py sincronizar %s' % (ed, ed))
    except (OSError, ValueError):
        decir('  [AVISO] no pude leer StreamingAssets/modelo_unity_edificio.json')


# ============================================================
def main(argv=None):
    ap = argparse.ArgumentParser(description='Carga movil precalculada para el visor.')
    ap.add_argument('edificio', choices=sorted(RECORRIDOS))
    ap.add_argument('--P', type=float, default=P_POR_DEFECTO,
                    help='carga vertical hacia abajo, kN (defecto %g)' % P_POR_DEFECTO)
    ap.add_argument('--divisiones', type=int, default=DIVISIONES_POR_DEFECTO,
                    help='posiciones por viga (defecto %d)' % DIVISIONES_POR_DEFECTO)
    ap.add_argument('--no-escribir', action='store_true',
                    help='verificar sin escribir nada')
    args = ap.parse_args(argv)
    ed, P = args.edificio, float(args.P)
    if P <= 0 or args.divisiones < 1:
        raise SystemExit('P tiene que ser positiva y divisiones >= 1')

    t0 = time.time()
    s4 = exportador_s4()
    modelo = contrato.cargar_modelo(ed)
    nodos = {int(n['id']): n for n in modelo['nodos']}
    por_id = {int(e['id']): e for e in modelo['elementos']}
    decl = RECORRIDOS[ed]
    rec = recorrido(modelo, decl['z'], decl['eje'], decl['coord'])
    lista = posiciones(modelo, rec, args.divisiones)

    decir('=' * 76)
    decir('  CARGA MOVIL   %s   P = %g kN hacia abajo' % (ed.upper(), P))
    decir('=' * 76)
    decir('  recorrido: cota %.2f, %s, %s = %.4f; %d vigas, %.3f m'
          % (decl['z'], 'a lo largo de ' + decl['eje'], 'y' if decl['eje'] == 'x' else 'x',
             decl['coord'], len(rec['elementos']), rec['largo_m']))
    for eid, L in zip(rec['elementos'], rec['largos']):
        e = por_id[eid]
        decir('    viga %d  %s  nodos %d -> %d  L = %.3f m' % (eid, e['seccion'], int(e['n1']),
                                                            int(e['n2']), L))
    for nid in rec['nodos']:
        decir('    nodo %d: %s' % (nid, ', '.join(que_llega_a(modelo, nid))))
    decir('  posiciones: %d (%d por viga, xL = (k + 1/2)/%d)'
          % (len(lista), args.divisiones, args.divisiones))
    decir()

    comparar_con_unity(modelo, ed)

    mot = Motor(modelo)
    pesos = pesos_de_reaccion(modelo, mot.restr)
    n_apoyos = [sum(p[i] for p in pesos.values()) for i in range(3)]
    decir('  apoyos que cuentan (regla de calcular.equilibrio): %d en Fx, %d en Fy, %d en Fz; '
          'de %d nodos con reaccion' % (n_apoyos[0], n_apoyos[1], n_apoyos[2], len(mot.restr)))
    decir()

    bloques, detalles = [], []
    for i, pos in enumerate(lista):
        b, d = bloque_posicion(i, pos, P, modelo, mot, pesos, s4, nodos, por_id)
        bloques.append(b)
        detalles.append(d)

    # --- tabla ---
    decir('  %3s %5s %5s %7s | %8s %8s %6s | %8s %8s | %10s %8s %6s | %9s %8s %8s'
          % ('i', 'viga', 'xL', 's m', 'V_i kN', 'V_j kN', '% i', 'palanca', 'emp.',
             'SumRz kN', 'err kN', 'cierre', 'uz min mm', 'uz P mm', 'M P kNm'))
    for b, d in zip(bloques, detalles):
        r, c = b['reparto'], b['conservacion']
        decir('  %3d %5d %5.2f %7.3f | %8.3f %8.3f %6.1f | %8.3f %8.3f | %10.4f %8.1e %6.3f | '
              '%9.4f %8.4f %8.2f %s'
              % (b['indice'], b['elemento'], b['xL'], b['s_m'], r['V_i_kN'], r['V_j_kN'],
                 r['porcentaje_i'], r['palanca_i_kN'], r['empotrado_V_i_kN'],
                 c['suma_Rz_kN'], abs(c['error_kN']), c['cierre_cociente'],
                 b['uz_min_mm'], b['uz_bajo_carga_mm'], b['M_bajo_carga_kNm'],
                 '' if c['cumple'] else '<-- NO CUMPLE'))
    decir()

    peor_z = max(bloques, key=lambda b: abs(b['conservacion']['error_kN']) /
                 b['conservacion']['cota_kN'])
    peor_h = max(detalles, key=lambda d: max(abs(d['cons']['error'][0]), abs(d['cons']['error'][1])))
    peor_mem = max(abs(d['cons']['err_mem'][2]) for d in detalles)
    peor_cierre = max(detalles, key=lambda d: d['cierre'][0])
    peor_V = max(abs(b['conservacion']['suma_V_mas_Pz_kN']) for b in bloques)
    peor_expl = max(d['err_explica'] / d['cota_explica'] for d in detalles)

    decir('  VERIFICACION POR POSICION (valores redondeados como el servidor)')
    check(all(d['cumple_z'] for d in detalles),
          '[a] conservacion: SumRz = P en las %d posiciones' % len(bloques),
          'peor |error| %.1e kN en la posicion %d, cota %.1e kN (%d apoyos x 5e-5 + coma '
          'flotante); en memoria, sin redondeo, peor %.1e kN'
          % (abs(peor_z['conservacion']['error_kN']), peor_z['indice'],
             peor_z['conservacion']['cota_kN'], n_apoyos[2], peor_mem))
    check(all(d['cumple_h'] for d in detalles),
          '[b] horizontales: SumRx = SumRy = 0',
          'peor |SumRx| %.1e, |SumRy| %.1e kN; cota %.1e kN (%d apoyos)'
          % (abs(peor_h['cons']['error'][0]), abs(peor_h['cons']['error'][1]),
             max(peor_h['cons']['cota'][0], peor_h['cons']['cota'][1]),
             max(n_apoyos[0], n_apoyos[1])))
    check(all(d['cumple_V'] for d in detalles) and all(d['cumple_cierre'] for d in detalles),
          '[c] viga cargada: Vz_i + Vz_j + Pz = 0 y cierre en x = L con el salto H(x-a)',
          'peor |Vz_i+Vz_j+Pz| %.1e kN (cota %.1e); peor cierre %.3f de la cota en %s '
          '(error %.1e, cota %.1e)'
          % (peor_V, detalles[0]['cota_V'], peor_cierre['cierre'][0], peor_cierre['cierre'][1],
             peor_cierre['cierre'][2], peor_cierre['cierre'][3]))
    check(all(d['cumple_explica'] for d in detalles),
          '[d] el reparto se explica: V_j - palanca = (My_i + My_j)/L',
          'peor error / cota %.3f' % peor_expl)
    decir()

    decir('  VERIFICACIONES GLOBALES (en memoria)')
    globales = []
    eid_demo = rec['elementos'][len(rec['elementos']) // 2 - 1]      # la del medio
    global_continuidad(mot, modelo, P, rec, globales)
    xs_viga = sorted(b['xL'] for b in bloques if b['elemento'] == eid_demo)
    A = (eid_demo, xs_viga[len(xs_viga) // 2])
    otra = rec['elementos'][min(len(rec['elementos']) - 1, rec['elementos'].index(eid_demo) + 2)]
    xs_otra = sorted(b['xL'] for b in bloques if b['elemento'] == otra)
    B = (otra, xs_otra[1] if len(xs_otra) > 1 else xs_otra[0])
    global_betti(bloques, detalles, modelo, s4, globales, A, B)
    global_superposicion(mot, bloques, detalles, globales, A, B)
    if args.divisiones >= 3 and any(abs(b['xL'] - 0.5) < 1e-9 for b in bloques
                                    if b['elemento'] == eid_demo):
        global_por_que_no(mot, modelo, P, bloques, detalles, globales, eid_demo)
    t_posiciones = mot.t_resolver
    n_resueltos = mot.n_resueltos
    fracciones = [x for x in (0.3, 0.5) if any(abs(b['xL'] - x) < 1e-9 for b in bloques
                                               if b['elemento'] == eid_demo)]
    global_viga_partida(modelo, P, eid_demo, fracciones, s4, globales)
    global_empotramiento(P, globales)

    # --- escala grafica fija ---
    mayor = max(max(b['max_desplazamiento_mm'] for b in bloques),
                max(math.sqrt(sum(v * v for v in b['u_carga_m'])) * 1000 for b in bloques))
    escala = LARGO_DIBUJO_M * 1000.0 / mayor if mayor > 0 else 1.0
    escala = float('%.2g' % escala)
    peor_uz = min(bloques, key=lambda b: b['uz_bajo_carga_mm'])

    verificaciones = []
    for g in globales:
        if g.get('informativo'):
            continue
        verificaciones.append({'nombre': g['nombre'], 'detalle': g['detalle'],
                               'criterio': g['criterio'], 'cumple': g['cumple']})
    verificaciones[0:0] = [
        {'nombre': 'conservacion SumRz = P', 'detalle': 'peor |error| %.1e kN en %d posiciones; '
         'en memoria %.1e kN' % (abs(peor_z['conservacion']['error_kN']), len(bloques), peor_mem),
         'criterio': '%d apoyos x 5e-5 kN + coma flotante' % n_apoyos[2],
         'cumple': all(d['cumple_z'] for d in detalles)},
        {'nombre': 'horizontales SumRx = SumRy = 0',
         'detalle': 'peor %.1e kN' % max(abs(peor_h['cons']['error'][0]), abs(peor_h['cons']['error'][1])),
         'criterio': '%d apoyos x 5e-5 kN' % max(n_apoyos[0], n_apoyos[1]),
         'cumple': all(d['cumple_h'] for d in detalles)},
        {'nombre': 'viga cargada: Vz_i + Vz_j + Pz = 0 y cierre en x = L',
         'detalle': 'peor cierre %.3f de la cota' % peor_cierre['cierre'][0],
         'criterio': 'cota_de_cierre de semana04/exportar_unity.py',
         'cumple': all(d['cumple_V'] and d['cumple_cierre'] for d in detalles)},
    ]

    anexo = {
        'info': {
            'edificio': ed,
            'descripcion': ('Carga puntual vertical que recorre un eje de vigas continuas, '
                            'resuelta en OpenSees posicion por posicion (eleLoad -beamPoint). '
                            'El visor elige una posicion y la dibuja; no interpola.'),
            'unidades': 'm, kN; momentos kN*m; desplazamientos m y rad; *_mm en mm',
            'generado_por': GENERADO_POR,
            'comando': 'python semana05/carga_movil.py %s --P %g --divisiones %d'
                       % (ed, P, args.divisiones),
            'convencion': [
                'P positiva hacia abajo; carga global (0, 0, -P)',
                'Px, Py, Pz locales = producto punto con localX, localY, localZ',
                'f = eleResponse(localForce) de la viga cargada: fuerzas de los nodos SOBRE la barra',
                'V_i, V_j = Vz de f en i y j: lo que la viga le entrega a cada nodo',
                'palanca: P b/L y P a/L (viga simplemente apoyada)',
                'empotrado: fuerzas de empotramiento perfecto (las nodales equivalentes)',
                'V_j = palanca_j + (My_i + My_j)/L',
                'M_bajo_carga = My(a) = -(My_i + a Vz_i); My < 0 tracciona abajo',
                'equilibrio: calcular.equilibrio con la carga puntual sumada a aplicada_kN',
                'u_carga_m: traslacion global del punto cargado (Hermite + flecha biempotrada)',
            ],
            'n_posiciones': len(bloques),
            'escala_deformada': escala,
            '_escala_por_que': ('solo grafica: %.4f mm, el mayor desplazamiento del recorrido, '
                                'se dibuja como %.1f m; la misma para todas las posiciones'
                                % (mayor, LARGO_DIBUJO_M)),
            'max_desplazamiento_recorrido_mm': round(mayor, 4),
            'uz_bajo_carga_min_mm': peor_uz['uz_bajo_carga_mm'],
            'indice_uz_bajo_carga_min': peor_uz['indice'],
            'apoyos_z': n_apoyos[2],
            'cota_redondeo_kN': s4.COTA_REDONDEO,
            'verificaciones': verificaciones,
        },
        'P_kN': P,
        '_P_kN_por_que': ('Magnitud de DEMOSTRACION, no normativa: con %g kN la mayor flecha '
                          'bajo la carga del recorrido es %.3f mm y la deformada se ve con la '
                          'escala x%g. El modelo es lineal: otra P escala todo en P/%g '
                          '(se recalcula con --P).' % (P, peor_uz['uz_bajo_carga_mm'], escala, P)),
        'recorrido': {
            'elementos': rec['elementos'],
            'nodos': rec['nodos'],
            'largos_m': [round(L, 4) for L in rec['largos']],
            'largo_m': round(rec['largo_m'], 4),
            'z': decl['z'],
            'eje': decl['eje'],
            'coord': decl['coord'],
            'divisiones': args.divisiones,
            'descripcion': ('cota %.2f, eje %s = %.2f: vigas %s, del nodo %d al %d (%.2f m)'
                            % (decl['z'], 'y' if decl['eje'] == 'x' else 'x', decl['coord'],
                               ', '.join(str(x) for x in rec['elementos']), rec['nodos'][0],
                               rec['nodos'][-1], rec['largo_m'])),
            '_por_que': decl['_por_que'],
        },
        'posiciones': bloques,
    }

    decir()
    verificar_contrato_cs(anexo)

    decir()
    decir('  resueltas %d corridas de OpenSees: construir %.3f s, resolver y extraer %.4f s '
          'por corrida' % (n_resueltos, mot.t_construir, t_posiciones / max(n_resueltos, 1)))
    decir('  escala grafica fija: x%g (%.4f mm -> %.1f m)' % (escala, mayor, LARGO_DIBUJO_M))

    if FALLOS:
        decir()
        decir('  NO SE ESCRIBE NADA: %d verificacion(es) fallaron:' % len(FALLOS))
        for f in FALLOS:
            decir('    - %s' % f)
        return 1

    if args.no_escribir:
        decir()
        decir('  todo cierra; --no-escribir: no se escribio nada')
        return 0

    texto = json.dumps(anexo, separators=(',', ':'), ensure_ascii=False)
    destino = rutas.asegurar(salida_unity(ed))
    with io.open(destino, 'w', encoding='utf-8') as f:
        f.write(texto)
    copiado = os.path.isdir(os.path.dirname(STREAMING))
    if copiado:
        shutil.copy2(destino, STREAMING)

    # --- evidencia: lo mismo sin los desplazamientos, y la salida ---
    evid = {
        'comando': anexo['info']['comando'],
        'fecha': time.strftime('%Y-%m-%d %H:%M:%S'),
        'P_kN': P,
        'recorrido': anexo['recorrido'],
        'apoyos_que_cuentan': {'Fx': n_apoyos[0], 'Fy': n_apoyos[1], 'Fz': n_apoyos[2]},
        'criterios': {
            'conservacion': 'n_apoyos x %g kN + 4 eps x tamano' % s4.COTA_REDONDEO,
            'cierre': 'semana04/exportar_unity.py cota_de_cierre',
            'globales_desplazamiento_m': RESOLUCION_U,
            'globales_fuerza_kN': RESOLUCION_F,
        },
        'escala_deformada': escala,
        'posiciones': [{k: v for k, v in b.items()
                        if k not in ('desplazamientos', 'reacciones', 'elastica')}
                       for b in bloques],
        'globales': globales,
        'tiempos_s': {'construir': round(mot.t_construir, 4),
                      'por_corrida': round(t_posiciones / max(n_resueltos, 1), 5),
                      'total': round(time.time() - t0, 2)},
        'bytes_json_unity': len(texto.encode('utf-8')),
    }
    ruta_ev = rutas.asegurar(os.path.join(EVIDENCIA, 'carga_movil_%s.json' % ed))
    with io.open(ruta_ev, 'w', encoding='utf-8') as f:
        json.dump(evid, f, indent=1, ensure_ascii=False)

    decir()
    decir('  %.1f KB, %d posiciones, %.1f s en total'
          % (len(texto.encode('utf-8')) / 1024.0, len(bloques), time.time() - t0))
    decir('  -> %s' % os.path.relpath(destino, rutas.RAIZ))
    if copiado:
        decir('  -> %s' % os.path.relpath(STREAMING, rutas.RAIZ))
    decir('  -> %s' % os.path.relpath(ruta_ev, rutas.RAIZ))
    ruta_txt = os.path.join(EVIDENCIA, 'carga_movil_%s.txt' % ed)
    decir('  -> %s' % os.path.relpath(ruta_txt, rutas.RAIZ))
    with io.open(ruta_txt, 'w', encoding='utf-8') as f:
        f.write('\n'.join(REGISTRO) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
