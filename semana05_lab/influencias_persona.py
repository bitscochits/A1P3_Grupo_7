# -*- coding: utf-8 -*-
r"""
================================================================
 semana05_lab/influencias_persona.py
   LA DEFORMADA QUE PRODUCE LA PERSONA, AL INSTANTE
================================================================
 La pestana Persona (unity/Assets/Scripts/VisorPersona.cs) deja caminar
 una carga por cualquier losa del edificio y dice a que elemento le
 llega. Este script hace que ademas se vea lo que esa carga le HACE al
 edificio -- la deformada entera y la flecha de la viga cargada --
 mientras camina, sin servidor y sin que Unity calcule nada.

 ----------------------------------------------------------------
 LA IDEA: casos unitarios y linealidad
 ----------------------------------------------------------------
 El modelo es elastico lineal. Una carga puntual P en la abscisa a de
 una viga (Euler-Bernoulli, prismatica) le entrega a sus dos nodos las
 FUERZAS NODALES EQUIVALENTES, que son P por las funciones de forma de
 Hermite evaluadas en alfa = a/L:

     en n1:  Fz = -P N1(alfa)      M = P L N2(alfa) (z x d)
     en n2:  Fz = -P N3(alfa)      M = P L N4(alfa) (z x d)

 (d = versor de la viga en planta; z x d = (-dy, dx, 0) es el eje de
 giro de la flexion). Con esas cargas OpenSees da los desplazamientos
 nodales EXACTOS de eleLoad -beamPoint: es lo que hace por dentro. Asi
 que basta resolver UNA vez, en OpenSees, cada carga unitaria posible
 -- Fz = 1 kN hacia abajo, Mx = 1 kN m y My = 1 kN m en cada nodo que
 puede recibir a la persona -- y la deformada de la persona en
 cualquier punto es la suma de a lo mas SEIS de esos casos con esos
 pesos. Es lo mismo que los sliders instantaneos del LAB 5 (combinar
 casos ya resueltos), con pesos que dependen de donde esta parada.

 DENTRO de la viga cargada, ademas, esta la flecha de la viga
 biempotrada (carga_movil.flecha_biempotrada). Python exporta su
 flexibilidad L^3/(E I) y el C# solo evalua la forma ADIMENSIONAL

     uz_local = -P (L^3/EI) phi(xi, alfa)

 que es a la carga puntual lo que las funciones de forma son a los
 nodos: el E y la I no entran al C#. Las dos copias (pesos y phi) se
 leen del C# y se comparan con las de aca en el bloque [3].

 ----------------------------------------------------------------
 LA REGLA DE DONDE CAE (supuestos, declarados abajo en SUPUESTOS)
 ----------------------------------------------------------------
 - A QUE ELEMENTO: el dueno de la region tributaria donde esta parada,
   la misma regla que ya usa VisorPersona (y el modelo para la losa).
 - EN QUE PUNTO DE UNA VIGA: la proyeccion de la persona sobre su eje.
 - UN MURO: la losa que apoya directo en un muro llega a su nodo de
   esa cota como carga puntual (ModeloLT2.area_trib_nodal); la persona,
   igual.

 ----------------------------------------------------------------
 EL ARCHIVO (data/unity/influencias_<ed>.json)
 ----------------------------------------------------------------
 Un caso por (nodo, gdl). Sus desplazamientos se guardan solo en el
 GRUPO de nodos conectados donde esta el nodo (en el conjunto, el LT2 y
 el cuerpo antiguo no se tocan: la junta es libre, y fuera del grupo
 la respuesta es CERO exacto, bloque [5]). Cada caso va como enteros
 de 16 bits en base64 con dos escalas (traslaciones y giros): un error
 de a lo mas medio paso, que el bloque [1] lleva a la cota. En float
 serian 2.5 veces mas bytes para dibujar lo mismo.

 Correr:
   python semana05_lab/influencias_persona.py lt2           resuelve, verifica y escribe
   python semana05_lab/influencias_persona.py conjunto
   python semana05_lab/influencias_persona.py lt2 --verificar
        no resuelve los casos: lee el JSON escrito y lo compara contra
        OpenSees en posiciones al azar (es lo que corre la suite)

 QUE COMPRUEBA (termina con 1 si algo falla, y entonces NO escribe):
   [1] la suma de casos = OpenSees resolviendo la carga directo
       (eleLoad -beamPoint o carga nodal), en todos los GDL de todos los
       nodos, en posiciones al azar: (a) sin cuantizar, al decimal del
       servidor; (b) como lo suma Unity (enteros + float32), dentro de
       la cota que dan el medio paso y la aritmetica de 32 bits;
   [2] la flecha bajo la carga que muestra el panel (Hermite + phi) =
       la de carga_movil.desplazamiento_en con la solucion directa;
   [3] los pesos y phi del C# (VisorPersona.Deformada.cs) son los de aca;
   [4] cada clave del JSON tiene su campo C# y al reves;
   [5] cada region tributaria tiene receptor, y fuera de su grupo un
       caso vale cero;
   [6] la escala de dibujo lleva el peor caso a LARGO_DIBUJO_M.
   [8] LOS MOMENTOS: los esfuerzos de extremo (localForce) de la viga
       cargada y de las barras que tocan sus nodos, sumados como Unity
       (casos + empotramiento perfecto de la viga cargada) = OpenSees
       directo; y el momento bajo la carga;
   [9] el empotramiento y M(x) del C# son carga_movil.empotramiento y
       carga_movil.esfuerzos_con_puntual.

 LOS MOMENTOS (05-10)
   Cada caso guarda tambien los esfuerzos de extremo de las barras que
   muestra algun receptor que lo usa: la viga y las que llegan a sus
   dos nodos (columnas y vigas vecinas). Sumados con los mismos pesos dan
   k u de cada barra, exacto; la viga cargada lleva ademas sus fuerzas
   de empotramiento perfecto, que son P por las mismas N1..N4. A lo largo
   de una barra sin carga M es lineal entre sus extremos; en la cargada
   tiene el quiebre de P bajo la carga (esfuerzos_con_puntual).
================================================================
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import math
import os
import random
import re
import sys
import time

import numpy as np

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(_AQUI)
sys.path.insert(0, os.path.join(_RAIZ, 'comun'))
sys.path.insert(0, os.path.join(_RAIZ, 'semana05'))

import rutas                                 # noqa: E402
rutas.en_sys_path(rutas.COMUN)

import openseespy.opensees as ops            # noqa: E402

import contrato                              # noqa: E402
import servidor_opensees as motor            # noqa: E402
import carga_movil                           # noqa: E402
from campos_cs import campos_de_clases       # noqa: E402

GENERADO_POR = 'semana05_lab/influencias_persona.py'
SCRIPTS_CS = os.path.join(rutas.UNITY_PROYECTO, 'Assets', 'Scripts')
CS_PERSONA = os.path.join(SCRIPTS_CS, 'VisorPersona.Deformada.cs')

# ------------------------------------------------------------
# LO DECLARADO
# ------------------------------------------------------------
# La carga y el largo de dibujo son los de la pestana Carga movil, para
# que las dos pestanas se puedan comparar a la misma escala.
P_POR_DEFECTO = carga_movil.P_POR_DEFECTO            # kN
LARGO_DIBUJO_M = carga_movil.LARGO_DIBUJO_M          # m

SUPUESTOS = {
    'receptor': ('El elemento dueno de la region tributaria donde esta parada: la regla del '
                 'modelo para la losa, la misma que ya aplica VisorPersona.'),
    'punto_en_la_viga': ('La proyeccion de la persona sobre el eje de la viga, acotada a [0, L]. '
                         'La losa reparte la carga G pareja (q A / L) porque es un AREA; un punto '
                         'no tiene area, y le llega a la viga cerca de donde esta. La regla '
                         'pareja haria que caminar a lo largo de una viga no cambie nada.'),
    'muro': ('La losa que apoya directo en un muro llega a su nodo de esa cota como carga '
             'puntual (edificios/lt2/modelo_lt2.py, area_trib_nodal): la persona tambien.'),
    'P': ('%g kN hacia abajo por defecto, la misma P de la pestana Carga movil; el panel la '
          'cambia (una persona son 0.80 kN y su deformada no se ve a ninguna escala util).'
          % P_POR_DEFECTO),
}

GDL = ('Fz', 'Mx', 'My')
# El vector de carga de cada caso unitario, (fx, fy, fz, mx, my, mz).
CARGA_UNITARIA = {
    'Fz': (0.0, 0.0, -1.0, 0.0, 0.0, 0.0),     # 1 kN hacia abajo
    'Mx': (0.0, 0.0, 0.0, 1.0, 0.0, 0.0),      # 1 kN m
    'My': (0.0, 0.0, 0.0, 0.0, 1.0, 0.0),      # 1 kN m
}

ENTERO = 32767                 # el mayor de cada escala se guarda como +-32767
EPS32 = 2.0 ** -24             # redondeo relativo de un float
K_F32 = 8                      # redondeos por termino en la suma de Unity (ver cota())
TAG_BASE = 8000
N_PRUEBAS = 24
SEMILLA = 20261005

RESOLUCION_U = carga_movil.RESOLUCION_U   # 1e-8 m y rad: el decimal del servidor
RESOLUCION_F = carga_movil.RESOLUCION_F   # 1e-4 kN y kN m

# Los momentos se dibujan con el mayor |M| (carga a media viga, en las
# barras que se dibujan) llevado a este largo, como la deformada.
LARGO_MOMENTO_M = 1.2
# localForce = [N, Vy, Vz, T, My, Mz] en i y en j: fuerzas y momentos
IDX_F = [0, 1, 2, 6, 7, 8]
IDX_M = [3, 4, 5, 9, 10, 11]
# Las barras que se dibujan con diagrama (los muros y brazos no: un muro
# es una placa y un brazo rigido no es una barra que se vea).
NO_DIBUJAR = ('muro', 'brazo', 'brazo_rigido')

# Las clases C# que leen cada parte del JSON (bloque [4]).
CLASES_CS = {
    'InfluenciasPersona': None,
    'InfoInfluencias': 'info',
    'GrupoInfluencias': 'grupos',
    'CasoInfluencia': 'casos',
    'ReceptorPersona': 'receptores',
}


def salida_unity(ed):
    return rutas.unity('influencias_' + ed)


# ============================================================
# AVISOS
# ============================================================
class Fallas:
    def __init__(self):
        self.lista = []

    def check(self, cond, msg, detalle=''):
        print('  [%s] %s' % ('OK  ' if cond else 'FALLA', msg))
        if detalle:
            print('         ' + detalle)
        if not cond:
            self.lista.append(msg)
        return cond


# ============================================================
# LAS FORMULAS (la definicion; el C# las copia y [3] lo comprueba)
# ============================================================
def hermite(a):
    """N1..N4 de Hermite en alfa, con N2 y N4 SIN el factor L."""
    return (1 - 3 * a * a + 2 * a ** 3,
            a - 2 * a * a + a ** 3,
            3 * a * a - 2 * a ** 3,
            -a * a + a ** 3)


def pesos(rec, alfa, P):
    """
    [(nodo, gdl, peso)] de la carga P (kN, hacia abajo) en alfa del
    receptor. Los casos unitarios son Fz = 1 kN HACIA ABAJO y momentos
    de 1 kN m, asi que el peso de Fz es +P N.
    """
    if rec['tipo'] == 'nodo':
        return [(rec['nodo'], 'Fz', P)]
    N1, N2, N3, N4 = hermite(alfa)
    L, nx, ny = rec['L'], -rec['dy'], rec['dx']          # z x d
    return [(rec['n1'], 'Fz', P * N1), (rec['n1'], 'Mx', P * L * N2 * nx),
            (rec['n1'], 'My', P * L * N2 * ny),
            (rec['n2'], 'Fz', P * N3), (rec['n2'], 'Mx', P * L * N4 * nx),
            (rec['n2'], 'My', P * L * N4 * ny)]


def forma_local(xi, alfa):
    """
    phi(xi, alfa): la flecha de la viga biempotrada con la carga en alfa,
    dividida por P L^3 / (E I). Es carga_movil.flecha_biempotrada sin
    unidades; [3] comprueba que son la misma.
    """
    if xi > alfa:
        xi, alfa = 1.0 - xi, 1.0 - alfa
    return (1 - alfa) ** 2 * xi * xi * (3 * alfa - (1 + 2 * alfa) * xi) / 6.0


def uz_en(rec, ui, uj, xi, alfa, P):
    """
    uz (m) en xi de la viga cargada en alfa: Hermite de los nodos en el
    plano vertical de la viga (la pendiente dz/dx = -(z x d) . giro) mas
    la flecha local. Es la componente vertical de
    carga_movil.desplazamiento_en, que [2] usa de referencia.
    """
    N1, N2, N3, N4 = hermite(xi)
    nx, ny, L = -rec['dy'], rec['dx'], rec['L']
    gi = nx * ui[3] + ny * ui[4]
    gj = nx * uj[3] + ny * uj[4]
    return (N1 * ui[2] - N2 * L * gi + N3 * uj[2] - N4 * L * gj
            - P * rec['flex'] * forma_local(xi, alfa))


def empotramiento_local(rec, alfa, P):
    """
    Lo que la carga P en alfa le agrega al localForce de SU viga: las
    fuerzas de empotramiento perfecto, P por N1..N4 (indices Vz_i, My_i,
    Vz_j, My_j). Es carga_movil.empotramiento con Pz = -P ([9]).
    """
    N1, N2, N3, N4 = hermite(alfa)
    L = rec['L']
    return {2: P * N1, 4: -P * L * N2, 8: P * N3, 10: -P * L * N4}


def my_en(f, x, a, P):
    """My(x) de la barra con extremos f; P (kN, hacia abajo) en a si es la
    cargada, 0 si no. Es esfuerzos_con_puntual con Pz = -P ([9])."""
    return -(f[4] + x * f[2] - P * max(0.0, x - a))


def mz_en(f, x):
    """Mz(x): sin carga en y local, lineal entre extremos."""
    return -(f[5] - x * f[1])


def flecha_bajo_carga(rec, ui, uj, alfa, P):
    """uz (m) del punto cargado (el nodo, si es un muro)."""
    if rec['tipo'] == 'nodo':
        return ui[2]
    return uz_en(rec, ui, uj, alfa, alfa, P)


# ============================================================
# LO QUE PUEDE RECIBIR A LA PERSONA
# ============================================================
def incidentes(modelo):
    inc = {}
    for e in modelo['elementos']:
        for n in (int(e['n1']), int(e['n2'])):
            inc.setdefault(n, []).append(int(e['id']))
    return inc


def receptores(vista, modelo, s4, fallas):
    """Un receptor por (elemento, cota) de las areas tributarias del visor."""
    nodos = {int(n['id']): n for n in modelo['nodos']}
    elems = {int(e['id']): e for e in modelo['elementos']}
    inc = incidentes(modelo)
    salida, malos = {}, []
    for a in vista['areas_tributarias']:
        eid, z = int(a['elemento']), float(a['z'])
        clave = (eid, round(z, 2))
        if clave in salida:
            continue
        e = elems.get(eid)
        if e is None:
            malos.append('%d: no esta en el modelo' % eid)
            continue
        n1, n2 = int(e['n1']), int(e['n2'])
        pi, pj = carga_movil._xyz(nodos[n1]), carga_movil._xyz(nodos[n2])
        if abs(pi[2] - pj[2]) < 0.01:
            if abs(pi[2] - z) > 0.02:
                malos.append('%d: la viga esta en z = %.2f y su area en %.2f' % (eid, pi[2], z))
                continue
            base, L = carga_movil.ejes_de(e, nodos)
            (Px, Py, Pz), _ = carga_movil.carga_local(base, 1.0)
            if abs(Px) > 1e-9 or abs(Py) > 1e-9:
                malos.append('%d: la vertical no cae en su eje local z' % eid)
                continue
            k = carga_movil.rigidez(modelo, e, nodos, s4)
            if base['wz'][2] < 1.0 - 1e-9:
                malos.append('%d: su z local no apunta hacia arriba' % eid)
                continue
            salida[clave] = {
                'elemento': eid, 'z': round(z, 4), 'tipo': 'viga', 'nodo': 0,
                'n1': n1, 'n2': n2, 'L': L,
                'flex': L ** 3 / (k['E'] * k['Iy_pasa']),
                'dx': (pj[0] - pi[0]) / L, 'dy': (pj[1] - pi[1]) / L,
                # las barras cuyos momentos se muestran: la viga y las que
                # llegan a sus dos nodos
                'elementos_m': sorted(set(inc[n1]) | set(inc[n2])),
            }
        else:
            en_z = [n for n in (n1, n2) if abs(nodos[n]['z'] - z) < 0.02]
            if len(en_z) != 1:
                malos.append('%d: el muro no tiene un nodo en z = %.2f' % (eid, z))
                continue
            salida[clave] = {'elemento': eid, 'z': round(z, 4), 'tipo': 'nodo', 'nodo': en_z[0],
                             'n1': n1, 'n2': n2, 'L': 0.0, 'flex': 0.0, 'dx': 0.0, 'dy': 0.0,
                             'elementos_m': sorted(inc[en_z[0]])}
    fallas.check(not malos, '[5] cada region tributaria del visor tiene a donde mandar la carga '
                 '(%d receptores: %d vigas, %d muros)'
                 % (len(salida), sum(r['tipo'] == 'viga' for r in salida.values()),
                    sum(r['tipo'] == 'nodo' for r in salida.values())),
                 '; '.join(malos[:5]))
    return [salida[k] for k in sorted(salida)]


def casos_necesarios(recs):
    casos = set()
    for r in recs:
        if r['tipo'] == 'nodo':
            casos.add((r['nodo'], 'Fz'))
        else:
            for n in (r['n1'], r['n2']):
                for g in GDL:
                    casos.add((n, g))
    return sorted(casos, key=lambda c: (c[0], GDL.index(c[1])))


def grupos_conectados(modelo):
    """Los nodos que se tocan por elementos o diafragmas (union-find)."""
    padre = {int(n['id']): int(n['id']) for n in modelo['nodos']}

    def raiz(a):
        while padre[a] != a:
            padre[a] = padre[padre[a]]
            a = padre[a]
        return a

    def unir(a, b):
        ra, rb = raiz(a), raiz(b)
        if ra != rb:
            padre[max(ra, rb)] = min(ra, rb)

    for e in modelo['elementos']:
        unir(int(e['n1']), int(e['n2']))
    for d in modelo.get('diafragmas', []):
        for n in d['nodos']:
            unir(int(d['nodo_maestro']), int(n))
    for br in modelo.get('brazos_rigidos', []):
        unir(int(br['maestro']), int(br['esclavo']))
    por_raiz = {}
    for n in sorted(padre):
        por_raiz.setdefault(raiz(n), []).append(n)
    return sorted(por_raiz.values(), key=lambda g: g[0])


# ============================================================
# EL SOLVER: el modelo del servidor, construido una vez
# ============================================================
class Solver:
    """El ciclo de carga_movil.Motor (remove, reset, patron, resolver_caso),
    con momentos en las cargas nodales y sin extraer esfuerzos."""

    def __init__(self, modelo):
        self.coords, self.avisos, self.restr = motor.construir_modelo(modelo)
        self.ids = [int(n['id']) for n in modelo['nodos']]
        self.tag, self.previo = TAG_BASE, None

    def resolver(self, nodales=(), puntuales=()):
        if self.previo is not None:
            ops.remove('loadPattern', self.previo)
        ops.reset()
        ops.setTime(0.0)
        self.tag += 1
        ops.timeSeries('Linear', self.tag)
        ops.pattern('Plain', self.tag, self.tag)
        for nid, f in nodales:
            ops.load(int(nid), *[float(v) for v in f])
        for eid, Px, Py, Pz, xL in puntuales:
            ops.eleLoad('-ele', int(eid), '-type', '-beamPoint',
                        float(Py), float(Pz), float(xL), float(Px))
        self.previo = self.tag
        if motor.resolver_caso() != 0:
            raise SystemExit('OpenSees no convergio')
        return {n: np.array(ops.nodeDisp(n), dtype=float) for n in self.ids}

    def fuerzas(self, elementos):
        """localForce de esas barras, del ultimo caso resuelto."""
        return {int(e): np.array(ops.eleResponse(int(e), 'localForce'), dtype=float) for e in elementos}


# ============================================================
# CODIFICAR Y DECODIFICAR (lo mismo que hace el C#)
# ============================================================
def codificar(U):
    """U (n, 6) -> (escala_t, escala_r, base64 de int16 little-endian)."""
    st = float(np.abs(U[:, :3]).max()) / ENTERO
    sr = float(np.abs(U[:, 3:]).max()) / ENTERO
    q = np.zeros(U.shape, dtype=np.int64)
    if st > 0:
        q[:, :3] = np.rint(U[:, :3] / st)
    if sr > 0:
        q[:, 3:] = np.rint(U[:, 3:] / sr)
    assert np.abs(q).max() <= ENTERO
    return st, sr, base64.b64encode(q.astype('<i2').tobytes()).decode('ascii')


def codificar_f(F):
    """F (k, 12) de localForce -> (escala_f, escala_m, base64 de int16)."""
    sf = float(np.abs(F[:, IDX_F]).max()) / ENTERO if F.size else 0.0
    sm = float(np.abs(F[:, IDX_M]).max()) / ENTERO if F.size else 0.0
    q = np.zeros(F.shape, dtype=np.int64)
    if sf > 0:
        q[:, IDX_F] = np.rint(F[:, IDX_F] / sf)
    if sm > 0:
        q[:, IDX_M] = np.rint(F[:, IDX_M] / sm)
    assert q.size == 0 or np.abs(q).max() <= ENTERO
    return sf, sm, base64.b64encode(q.astype('<i2').tobytes()).decode('ascii')


def decodificar_f(caso, f32=True):
    k = len(caso['elementos'])
    q = np.frombuffer(base64.b64decode(caso['fuerzas']), dtype='<i2').reshape(k, 12)
    tipo = np.float32 if f32 else float
    F = q.astype(tipo)
    F[:, IDX_F] *= tipo(caso['escala_f'])
    F[:, IDX_M] *= tipo(caso['escala_m'])
    return F


def decodificar(caso, n, f32=True):
    """El caso como (n, 6). f32: como lo deja Unity (float del JSON y producto en float)."""
    q = np.frombuffer(base64.b64decode(caso['datos']), dtype='<i2').reshape(n, 6)
    if f32:
        st, sr = np.float32(caso['escala_t']), np.float32(caso['escala_r'])
        U = q.astype(np.float32)
        U[:, :3] *= st
        U[:, 3:] *= sr
        return U
    U = q.astype(float)
    U[:, :3] *= caso['escala_t']
    U[:, 3:] *= caso['escala_r']
    return U


class Datos:
    """El JSON ya armado, indexado como lo indexa el C#."""

    def __init__(self, js):
        self.js = js
        self.grupos = [g['nodos'] for g in js['grupos']]
        self.indice = [{n: i for i, n in enumerate(g)} for g in self.grupos]
        self.casos = {(c['nodo'], c['gdl']): c for c in js['casos']}
        self._cache = {}

    def U(self, nodo, gdl, f32=True):
        c = self.casos[(nodo, gdl)]
        k = (nodo, gdl, f32)
        if k not in self._cache:
            self._cache[k] = decodificar(c, len(self.grupos[c['grupo']]), f32)
        return c['grupo'], self._cache[k]

    def F(self, nodo, gdl, f32=True):
        """{barra: localForce[12]} de un caso."""
        c = self.casos[(nodo, gdl)]
        k = ('F', nodo, gdl, f32)
        if k not in self._cache:
            M = decodificar_f(c, f32)
            self._cache[k] = {e: M[i] for i, e in enumerate(c['elementos'])}
        return self._cache[k]


def combinar(datos, rec, alfa, P, f32=True):
    """{nodo: u[6]} como lo arma el C#: suma de a lo mas seis casos."""
    tipo = np.float32 if f32 else float
    suma = {}
    for nodo, gdl, w in pesos(rec, alfa, P):
        g, U = datos.U(nodo, gdl, f32)
        w = tipo(w)
        for n, i in datos.indice[g].items():
            prev = suma.get(n)
            suma[n] = (U[i] * w) if prev is None else (prev + U[i] * w)
    return suma


def combinar_f(datos, rec, alfa, P, f32=True):
    """{barra: localForce[12]} de las barras del receptor, como el C#: la
    suma de los casos y, en la viga cargada, su empotramiento."""
    tipo = np.float32 if f32 else float
    out = {e: np.zeros(12, dtype=tipo) for e in rec['elementos_m']}
    for nodo, gdl, w in pesos(rec, alfa, P):
        F = datos.F(nodo, gdl, f32)
        w = tipo(w)
        for e in rec['elementos_m']:
            out[e] = out[e] + F[e] * w
    if rec['tipo'] == 'viga':
        f = out[rec['elemento']]
        for i, v in empotramiento_local(rec, alfa, P).items():
            f[i] = f[i] + tipo(v)
    return out


def cota_f(datos, rec, alfa, P):
    """La cota de combinar_f, con las mismas causas que cota()."""
    out = {e: np.zeros(12) for e in rec['elementos_m']}
    for nodo, gdl, w in pesos(rec, alfa, P):
        c = datos.casos[(nodo, gdl)]
        F = datos.F(nodo, gdl, f32=False)
        paso = np.zeros(12)
        paso[IDX_F] = 0.5 * c['escala_f']
        paso[IDX_M] = 0.5 * c['escala_m']
        for e in rec['elementos_m']:
            out[e] += abs(w) * (paso + K_F32 * EPS32 * np.abs(F[e]))
    if rec['tipo'] == 'viga':
        for i, v in empotramiento_local(rec, alfa, P).items():
            out[rec['elemento']][i] += K_F32 * EPS32 * abs(v)
    return out


def cota(datos, rec, alfa, P):
    """
    Por GDL, lo mas que puede separarse lo que suma Unity de la suma
    exacta de los casos sin cuantizar:
      - el MEDIO PASO de cada caso (0.5 escala), por su |peso|;
      - la aritmetica de 32 bits: la escala al leerse, el entero por la
        escala, el peso, el producto y la suma: menos de K_F32 = 8
        redondeos de 2^-24 por termino, sobre |peso * u|.
    """
    out = {}
    for nodo, gdl, w in pesos(rec, alfa, P):
        c = datos.casos[(nodo, gdl)]
        g, U = datos.U(nodo, gdl, f32=False)
        paso = np.array([c['escala_t']] * 3 + [c['escala_r']] * 3) * 0.5
        for n, i in datos.indice[g].items():
            t = abs(w) * (paso + K_F32 * EPS32 * np.abs(U[i]))
            out[n] = t if n not in out else out[n] + t
    return out


# ============================================================
# ARMAR
# ============================================================
def armar(ed, modelo, vista, s4, fallas):
    t0 = time.time()
    recs = receptores(vista, modelo, s4, fallas)
    casos = casos_necesarios(recs)
    grupos = grupos_conectados(modelo)
    grupo_de = {n: g for g, ns in enumerate(grupos) for n in ns}
    print('  %d casos unitarios en %d nodos; %d grupo(s) de nodos conectados (%s)'
          % (len(casos), len({c[0] for c in casos}), len(grupos),
             ', '.join(str(len(g)) for g in grupos)))

    # Las barras de cada caso: las que muestra algun receptor que lo usa.
    barras = {c: set() for c in casos}
    for r in recs:
        for nodo, gdl, _w in pesos(r, 0.5, 1.0):
            barras[(nodo, gdl)] |= set(r['elementos_m'])

    sol = Solver(modelo)
    salida, fuera = [], 0.0
    for k, (nodo, gdl) in enumerate(casos):
        u = sol.resolver(nodales=[(nodo, CARGA_UNITARIA[gdl])])
        g = grupo_de[nodo]
        U = np.array([u[n] for n in grupos[g]])
        otros = [np.abs(u[n]).max() for n in u if grupo_de[n] != g]
        if otros:
            fuera = max(fuera, max(otros))
        st, sr, datos = codificar(U)
        ids = sorted(barras[(nodo, gdl)])
        f = sol.fuerzas(ids)
        F = np.array([f[e] for e in ids]).reshape(len(ids), 12)
        sf, sm, fuerzas = codificar_f(F)
        salida.append({'nodo': nodo, 'gdl': gdl, 'grupo': g,
                       'escala_t': st, 'escala_r': sr, 'datos': datos,
                       'elementos': ids, 'escala_f': sf, 'escala_m': sm, 'fuerzas': fuerzas,
                       '_U': U, '_F': F})
        if (k + 1) % 200 == 0:
            print('    %d de %d (%.0f s)' % (k + 1, len(casos), time.time() - t0), flush=True)
    t_casos = time.time() - t0
    fallas.check(fuera == 0.0, '[5] fuera de su grupo, cada caso vale CERO exacto (la junta es libre)',
                 'mayor |u| fuera del grupo: %.3e' % fuera)

    js = {
        'info': {
            'edificio': ed,
            'n_nodos': len(vista['nodos']),
            'n_elementos': len(vista['elementos']),
            'generado_por': GENERADO_POR,
            'unidades': ('casos: Fz = 1 kN hacia abajo, Mx = My = 1 kN m, en ejes OpenSees; '
                         'desplazamientos en m y giros en rad; flex en m/kN'),
            'P_por_defecto_kN': P_POR_DEFECTO,
            'escala_deformada': 0.0,
            'largo_dibujo_m': LARGO_DIBUJO_M,
            'escala_momento': 0.0,
            'largo_momento_m': LARGO_MOMENTO_M,
            'n_casos': len(salida),
            'segundos_opensees': round(t_casos, 1),
            '_por_que': ('Cada caso es UNA carga unitaria resuelta por OpenSees. La deformada de la '
                         'persona es la suma de a lo mas seis, con los pesos de Hermite de donde '
                         'esta parada, mas la flecha biempotrada dentro de la viga cargada: Unity '
                         'combina, no resuelve. Los datos de cada caso son int16 en base64 por '
                         'escala_t (traslaciones) y escala_r (giros), solo de los nodos de su grupo. '
                         'fuerzas: localForce de las barras de elementos (int16 por escala_f y '
                         'escala_m); la viga cargada suma su empotramiento perfecto. escala_momento '
                         'en m por kN m.'),
            '_supuesto_receptor': SUPUESTOS['receptor'],
            '_supuesto_punto_en_la_viga': SUPUESTOS['punto_en_la_viga'],
            '_supuesto_muro': SUPUESTOS['muro'],
            '_supuesto_P': SUPUESTOS['P'],
        },
        'grupos': [{'nodos': g} for g in grupos],
        'casos': salida,
        'receptores': recs,
    }
    return js, sol


def escala_de_dibujo(datos, recs, P):
    """La mayor traslacion con la carga a media viga (o en el nodo del
    muro), en todo el edificio y en el punto cargado; la escala la lleva
    a LARGO_DIBUJO_M, con 2 cifras como el anexo de la Semana 4."""
    peor, donde = 0.0, None
    for r in recs:
        alfa = 0.5
        u = combinar(datos, r, alfa, P, f32=False)
        m = max(float(np.linalg.norm(v[:3])) for v in u.values())
        if r['tipo'] == 'viga':
            m = max(m, abs(flecha_bajo_carga(r, u[r['n1']], u[r['n2']], alfa, P)))
        if m > peor:
            peor, donde = m, r['elemento']
    bruta = LARGO_DIBUJO_M / peor
    cifras = 10 ** (math.floor(math.log10(bruta)) - 1)
    return round(bruta / cifras) * cifras, peor, donde


def escala_de_momentos(datos, recs, P, dibujables):
    """El mayor |M| de las barras que se dibujan, con la carga a media viga;
    la escala (m por kN m) lo lleva a LARGO_MOMENTO_M, con 2 cifras."""
    peor, donde = 0.0, None
    for r in recs:
        alfa = 0.5
        F = combinar_f(datos, r, alfa, P, f32=False)
        for e, f in F.items():
            if e not in dibujables:
                continue
            L = dibujables[e]
            cargada = r['tipo'] == 'viga' and e == r['elemento']
            for k in range(11):
                x = L * k / 10.0
                m = max(abs(my_en(f, x, alfa * L, P if cargada else 0.0)), abs(mz_en(f, x)))
                if m > peor:
                    peor, donde = m, e
            if cargada:
                m = abs(my_en(f, alfa * L, alfa * L, P))
                if m > peor:
                    peor, donde = m, e
    bruta = LARGO_MOMENTO_M / peor
    cifras = 10 ** (math.floor(math.log10(bruta)) - 1)
    return round(bruta / cifras) * cifras, peor, donde


def largos_dibujables(modelo):
    """{barra: L} de las que llevan diagrama."""
    nodos = {int(n['id']): carga_movil._xyz(n) for n in modelo['nodos']}
    out = {}
    for e in modelo['elementos']:
        if e.get('tipo') in NO_DIBUJAR:
            continue
        a, b = nodos[int(e['n1'])], nodos[int(e['n2'])]
        out[int(e['id'])] = math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))
    return out


# ============================================================
# VERIFICAR CONTRA OPENSEES
# ============================================================
def posiciones_al_azar(recs, n):
    rnd = random.Random(SEMILLA)
    vigas = [r for r in recs if r['tipo'] == 'viga']
    muros = [r for r in recs if r['tipo'] == 'nodo']
    lista = []
    for k in range(n):
        if muros and k % 6 == 5:
            lista.append((rnd.choice(muros), 0.0))
            continue
        r = rnd.choice(vigas)
        # los bordes van a proposito: en alfa = 0 y 1 la carga cae en un nodo
        alfa = (0.0, 1.0)[k % 2] if k % 8 == 3 else rnd.random()
        lista.append((r, alfa))
    return lista


def directo(sol, modelo, rec, alfa, P):
    if rec['tipo'] == 'nodo':
        return sol.resolver(nodales=[(rec['nodo'], (0, 0, -P, 0, 0, 0))])
    nodos = {int(n['id']): n for n in modelo['nodos']}
    e = next(x for x in modelo['elementos'] if int(x['id']) == rec['elemento'])
    base, _ = carga_movil.ejes_de(e, nodos)
    (Px, Py, Pz), _ = carga_movil.carga_local(base, P)
    return sol.resolver(puntuales=[(rec['elemento'], Px, Py, Pz, alfa)])


def verificar(js, modelo, sol, s4, fallas, n_pruebas, sin_cuantizar=None):
    datos = Datos(js)
    recs = js['receptores']
    P = P_POR_DEFECTO
    peor_a, peor_b, peor_b_rel, peor_f = 0.0, 0.0, 0.0, 0.0
    detalle_b, detalle_f = '', ''
    nodos = {int(n['id']): n for n in modelo['nodos']}
    elems = {int(e['id']): e for e in modelo['elementos']}
    peor_fa, peor_fb, peor_mc = 0.0, 0.0, 0.0
    detalle_fb, detalle_mc = '', ''
    for rec, alfa in posiciones_al_azar(recs, n_pruebas):
        u_d = directo(sol, modelo, rec, alfa, P)
        f_d = sol.fuerzas(rec['elementos_m'])
        mayor = max(float(np.abs(v[:3]).max()) for v in u_d.values())
        # [8] los esfuerzos de extremo
        if sin_cuantizar is not None:
            suma = {e: np.zeros(12) for e in rec['elementos_m']}
            for nodo, gdl, w in pesos(rec, alfa, P):
                c = sin_cuantizar[(nodo, gdl)]
                fila = {e: i for i, e in enumerate(c['elementos'])}
                for e in rec['elementos_m']:
                    suma[e] += w * c['_F'][fila[e]]
            if rec['tipo'] == 'viga':
                for i, v in empotramiento_local(rec, alfa, P).items():
                    suma[rec['elemento']][i] += v
            for e in rec['elementos_m']:
                peor_fa = max(peor_fa, float(np.abs(suma[e] - f_d[e]).max()))
        f_u = combinar_f(datos, rec, alfa, P, f32=True)
        cf = cota_f(datos, rec, alfa, P)
        for e in rec['elementos_m']:
            err = np.abs(f_u[e].astype(float) - f_d[e])
            c = cf[e] + 1e-12
            j = int(np.argmax(err / c))
            if err[j] / c[j] > peor_fb:
                peor_fb = float(err[j] / c[j])
                detalle_fb = ('peor: carga en %d alfa %.3f, barra %d, %s: error %.2e contra cota %.2e'
                              % (rec['elemento'], alfa, e, ('N_i Vy_i Vz_i T_i My_i Mz_i N_j Vy_j Vz_j '
                                                            'T_j My_j Mz_j').split()[j],
                                 float(err[j]), float(c[j])))
        if rec['tipo'] == 'viga':
            a = alfa * rec['L']
            ref = carga_movil.esfuerzos_con_puntual(f_d[rec['elemento']], 0.0, 0.0, -P, a, [a])['My'][0]
            got = my_en(f_u[rec['elemento']].astype(float), a, a, P)
            cc = cf[rec['elemento']]
            c = cc[4] + a * cc[2] + K_F32 * EPS32 * abs(ref) + 1e-12
            if abs(got - ref) / c > peor_mc:
                peor_mc = abs(got - ref) / c
                detalle_mc = ('peor: viga %d, alfa %.3f: M bajo la carga %.4f contra %.4f kN m'
                              % (rec['elemento'], alfa, got, ref))
        # (a) sin cuantizar: la linealidad, al decimal del servidor
        if sin_cuantizar is not None:
            suma = {}
            for nodo, gdl, w in pesos(rec, alfa, P):
                c = sin_cuantizar[(nodo, gdl)]
                for i, n in enumerate(js['grupos'][c['grupo']]['nodos']):
                    suma[n] = suma.get(n, 0.0) + w * c['_U'][i]
            for n, v in u_d.items():
                peor_a = max(peor_a, float(np.abs(suma.get(n, np.zeros(6)) - v).max()))
        # (b) como lo suma Unity, contra su cota
        u_u = combinar(datos, rec, alfa, P, f32=True)
        cotas = cota(datos, rec, alfa, P)
        for n, v in u_d.items():
            got = u_u.get(n, np.zeros(6, dtype=np.float32)).astype(float)
            err = np.abs(got - v)
            c = cotas.get(n, np.zeros(6)) + 1e-15
            j = int(np.argmax(err / c))
            r = float(err[j] / c[j])
            if r > peor_b:
                peor_b = r
                detalle_b = ('peor: elemento %d, alfa %.3f, nodo %d, gdl %s: error %.2e contra cota %.2e'
                             % (rec['elemento'], alfa, n, ('ux', 'uy', 'uz', 'rx', 'ry', 'rz')[j],
                                float(err[j]), float(c[j])))
            peor_b_rel = max(peor_b_rel, float(err[:3].max()) / mayor if mayor > 0 else 0.0)
        # [2] la flecha bajo la carga
        if rec['tipo'] == 'viga':
            e = elems[rec['elemento']]
            base, L = carga_movil.ejes_de(e, nodos)
            k = carga_movil.rigidez(modelo, e, nodos, s4)
            (Px, Py, Pz), _ = carga_movil.carga_local(base, P)
            for xi in (alfa, 0.25, 0.5, 0.75):
                ref = carga_movil.desplazamiento_en(base, L, k, list(u_d[rec['n1']]),
                                                    list(u_d[rec['n2']]), xi * L,
                                                    carga=(Py, Pz, alfa * L))[2]
                got = uz_en(rec, u_u[rec['n1']].astype(float), u_u[rec['n2']].astype(float),
                            xi, alfa, P)
                N1, N2, N3, N4 = hermite(xi)
                ci, cj = cotas[rec['n1']], cotas[rec['n2']]
                c = (N1 * ci[2] + abs(N2) * L * (ci[3] + ci[4]) + N3 * cj[2]
                     + abs(N4) * L * (cj[3] + cj[4]) + K_F32 * EPS32 * abs(ref) + 1e-15)
                r = abs(got - ref) / c
                if r > peor_f:
                    peor_f = r
                    detalle_f = ('peor: viga %d, carga en alfa %.3f, punto xi %.3f: %.6f mm contra '
                                 '%.6f mm (cota %.1e m)' % (rec['elemento'], alfa, xi, got * 1000,
                                                            ref * 1000, c))
    if sin_cuantizar is not None:
        fallas.check(peor_a <= RESOLUCION_U,
                     '[1a] la suma de casos = OpenSees directo (beamPoint o nodal), sin cuantizar, '
                     'en %d posiciones' % n_pruebas,
                     'peor diferencia %.2e (m o rad); el servidor escribe 1e-8' % peor_a)
    fallas.check(peor_b <= 1.0,
                 '[1b] lo que suma Unity (int16 + float32) = OpenSees directo, dentro de su cota, '
                 'en todos los GDL de todos los nodos (%d posiciones)' % n_pruebas,
                 '%s; cociente %.3f; el error mayor es el %.4f %% del mayor desplazamiento'
                 % (detalle_b, peor_b, 100 * peor_b_rel))
    fallas.check(peor_f <= 1.0,
                 '[2] la elastica de la viga cargada (Hermite + phi; bajo la carga y en 1/4, 1/2, '
                 '3/4) = carga_movil.desplazamiento_en con la solucion directa',
                 '%s; cociente %.3f' % (detalle_f, peor_f))
    if sin_cuantizar is not None:
        fallas.check(peor_fa <= RESOLUCION_F,
                     '[8a] los esfuerzos de extremo (casos + empotramiento) = localForce de OpenSees '
                     'directo, sin cuantizar', 'peor diferencia %.2e (kN o kN m); el servidor escribe '
                     '1e-4' % peor_fa)
    fallas.check(peor_fb <= 1.0,
                 '[8b] los esfuerzos de extremo como los suma Unity = localForce directo, dentro de su '
                 'cota (la viga cargada y las barras de sus nodos)', '%s; cociente %.3f'
                 % (detalle_fb, peor_fb))
    fallas.check(peor_mc <= 1.0,
                 '[8c] el momento bajo la carga = carga_movil.esfuerzos_con_puntual con localForce directo',
                 '%s; cociente %.3f' % (detalle_mc, peor_mc))


# ============================================================
# [3] LA COPIA EN C#
# ============================================================
def _a_python(expr):
    e = ' '.join(expr.split())
    e = re.sub(r'(\d)f\b', r'\1', e)
    return e


def transcripcion(fallas):
    if not os.path.isfile(CS_PERSONA):
        fallas.check(False, '[3] existe %s' % os.path.relpath(CS_PERSONA, rutas.RAIZ))
        return
    src = io.open(CS_PERSONA, encoding='utf-8').read()
    fun = {}
    for nombre in ('N1', 'N2', 'N3', 'N4'):
        m = re.search(r'static float %s\(float a\)\s*\{\s*return (.*?);\s*\}' % nombre, src, re.S)
        fun[nombre] = _a_python(m.group(1)) if m else None
    m = re.search(r'static float FormaLocal\(float xi, float alfa\)\s*\{(.*?)\n    \}', src, re.S)
    cuerpo_phi = m.group(1) if m else ''
    m_swap = re.search(r'if \(xi > alfa\) \{ xi = 1f - xi; alfa = 1f - alfa; \}', cuerpo_phi)
    m_ret = re.search(r'return (.*?);', cuerpo_phi, re.S)
    sumas = re.findall(r'Sumar\(r\.(n1|n2), GDL_(FZ|MX|MY), (.*?)\);', src)
    m_fl = re.search(r'static float UzEn\(ReceptorPersona r, DespNodo di, DespNodo dj, float xi, '
                     r'float a, float P\)\s*\{\s*return (.*?);\s*\}', src, re.S)
    ok = all(fun.values()) and m_swap and m_ret and len(sumas) == 6 and m_fl
    if not fallas.check(bool(ok), '[3] el C# tiene N1..N4, FormaLocal, los seis Sumar() y UzEn',
                        'N: %s, swap %s, return %s, Sumar %d, UzEn %s'
                        % ({k: bool(v) for k, v in fun.items()}, bool(m_swap), bool(m_ret),
                           len(sumas), bool(m_fl))):
        return
    entorno = {}
    for nombre, cuerpo in fun.items():
        exec('def %s(a):\n    return %s\n' % (nombre, cuerpo), entorno)
    exec('def FormaLocal(xi, alfa):\n    if xi > alfa:\n        xi, alfa = 1 - xi, 1 - alfa\n'
         '    return %s\n' % _a_python(m_ret.group(1)), entorno)
    rnd = random.Random(SEMILLA)
    peor_n, peor_phi, peor_w, peor_fl = 0.0, 0.0, 0.0, 0.0
    for _ in range(300):
        a, xi = rnd.random(), rnd.random()
        ref = hermite(a)
        for i, nombre in enumerate(('N1', 'N2', 'N3', 'N4')):
            peor_n = max(peor_n, abs(entorno[nombre](a) - ref[i]))
        peor_phi = max(peor_phi, abs(entorno['FormaLocal'](xi, a) - forma_local(xi, a)))
        # forma_local es flecha_biempotrada sin unidades
        L, EI, P = 2 + 8 * rnd.random(), 1e5 * (1 + rnd.random()), 1 + 99 * rnd.random()
        fb = carga_movil.flecha_biempotrada(P, a * L, L, xi * L, EI)
        peor_phi = max(peor_phi, abs(fb - P * L ** 3 / EI * forma_local(xi, a)) / (P * L ** 3 / EI))
        # los seis pesos
        ang = 2 * math.pi * rnd.random()
        r = {'tipo': 'viga', 'n1': 1, 'n2': 2, 'L': L, 'dx': math.cos(ang), 'dy': math.sin(ang),
             'flex': L ** 3 / EI}
        ref_w = {(n, g): w for n, g, w in pesos(r, a, P)}
        loc = dict(entorno, a=a, P=P, r=type('R', (), {'L': L, 'dx': r['dx'], 'dy': r['dy'],
                                                       'flex': r['flex']}))
        for nodo, g, expr in sumas:
            got = eval(_a_python(expr), loc)
            want = ref_w[(1 if nodo == 'n1' else 2, {'FZ': 'Fz', 'MX': 'Mx', 'MY': 'My'}[g])]
            peor_w = max(peor_w, abs(got - want) / max(1.0, abs(want)))
        # la elastica que se dibuja y la flecha del panel
        ui = [rnd.uniform(-1e-3, 1e-3) for _ in range(6)]
        uj = [rnd.uniform(-1e-3, 1e-3) for _ in range(6)]
        D = type('D', (), {})
        di, dj = D(), D()
        for o, u in ((di, ui), (dj, uj)):
            o.ux, o.uy, o.uz, o.rx, o.ry, o.rz = u
        loc.update(di=di, dj=dj, xi=xi)
        got = eval(_a_python(m_fl.group(1)), loc)
        want = uz_en(r, ui, uj, xi, a, P)
        peor_fl = max(peor_fl, abs(got - want) / max(1e-3, abs(want)))
    # [9] el empotramiento y M(x)
    emp = re.findall(r'f\[(2|4|8|10)\] \+= (.*?);', src)
    m_my = re.search(r'static float MyEn\(float\[\] f, float x, float a, float P\)\s*\{\s*return (.*?);\s*\}',
                     src, re.S)
    m_mz = re.search(r'static float MzEn\(float\[\] f, float x\)\s*\{\s*return (.*?);\s*\}', src, re.S)
    if fallas.check(len(emp) == 4 and m_my and m_mz,
                    '[9] el C# tiene las cuatro lineas del empotramiento, MyEn y MzEn',
                    'empotramiento %d lineas, MyEn %s, MzEn %s' % (len(emp), bool(m_my), bool(m_mz))):
        peor_e, peor_m = 0.0, 0.0
        for _ in range(300):
            a, P = rnd.random(), 1 + 99 * rnd.random()
            L = 2 + 8 * rnd.random()
            r = {'tipo': 'viga', 'L': L}
            loc = dict(entorno, a=a, P=P, r=type('R', (), {'L': L}))
            ref = empotramiento_local(r, a, P)
            cm = carga_movil.empotramiento(-P, a * L, L)
            ref_cm = {2: cm['V_i'], 4: cm['My_i'], 8: cm['V_j'], 10: cm['My_j']}
            for idx, expr in emp:
                got = eval(_a_python(expr), loc)
                peor_e = max(peor_e, abs(got - ref[int(idx)]) / max(1.0, abs(ref[int(idx)])),
                             abs(ref[int(idx)] - ref_cm[int(idx)]) / max(1.0, abs(ref_cm[int(idx)])))
            f = [rnd.uniform(-100, 100) for _ in range(12)]
            x = L * rnd.random()
            aa = L * a
            loc.update(f=f, x=x, a=aa)
            ex_my = _a_python(m_my.group(1)).replace('Mathf.Max', 'max')
            ex_mz = _a_python(m_mz.group(1))
            ref_s = carga_movil.esfuerzos_con_puntual(f, 0.0, 0.0, -P, aa, [x])
            peor_m = max(peor_m,
                         abs(eval(ex_my, loc) - ref_s['My'][0]) / max(1.0, abs(ref_s['My'][0])),
                         abs(eval(ex_mz, loc) - ref_s['Mz'][0]) / max(1.0, abs(ref_s['Mz'][0])),
                         abs(my_en(f, x, aa, P) - ref_s['My'][0]) / max(1.0, abs(ref_s['My'][0])))
        fallas.check(peor_e < 1e-12 and peor_m < 1e-12,
                     '[9] el empotramiento y M(x) del C# = carga_movil.empotramiento y '
                     'esfuerzos_con_puntual, 300 tiros', 'peor: empotramiento %.1e, M(x) %.1e'
                     % (peor_e, peor_m))
    fallas.check(peor_n < 1e-12 and peor_phi < 1e-12 and peor_w < 1e-12 and peor_fl < 1e-12,
                 '[3] la copia en C# (VisorPersona.Deformada.cs) = estas formulas, 300 tiros al azar',
                 'peor: N %.1e, phi %.1e (y phi = flecha_biempotrada / (P L^3/EI)), pesos %.1e, '
                 'UzEn %.1e' % (peor_n, peor_phi, peor_w, peor_fl))


def cruzar_registro(ruta, js, modelo, sol, fallas):
    """
    [7] Lo que la APP sumo y dibujo (CapturaPersona deja en registro.txt
    las lineas de VisorPersona.Captura_Registro, float en G9) contra
    OpenSees resolviendo esa misma carga directo. La cota es la de [1b]
    mas la impresion en G9 (medio digito en la novena cifra).
    """
    lineas = [l.strip() for l in io.open(ruta, encoding='utf-8') if l.startswith('persona: elemento')]
    if not fallas.check(bool(lineas), '[7] el registro de la app trae lineas de la persona (%s)'
                        % os.path.relpath(ruta, rutas.RAIZ)):
        return
    datos = Datos(js)
    peor, detalle, n_ok = 0.0, '', 0
    for l in lineas:
        cab, *nodos_txt = l.split(' | ')
        t = cab.split()
        kv = {t[i]: t[i + 1] for i in range(1, len(t) - 1, 2)}
        eid, alfa, P = int(kv['elemento']), float(kv['alfa']), float(kv['P'])
        rec = next(r for r in js['receptores'] if r['elemento'] == eid and r['tipo'] == kv['tipo'])
        u_d = directo(sol, modelo, rec, alfa, P)
        cotas = cota(datos, rec, alfa, P)
        esperados = 1 if rec['tipo'] == 'nodo' else 6
        fallas.check(int(kv['casos']) == esperados, '[7] la app sumo %d casos para %s %d (se esperan %d)'
                     % (int(kv['casos']), rec['tipo'], eid, esperados))
        barras_txt = [t for t in nodos_txt if t.startswith('barra ')]
        nodos_txt = [t for t in nodos_txt if t.startswith('nodo ')]
        for nt in nodos_txt:
            v = nt.split()
            nid, got = int(v[1]), np.array([float(c) for c in v[2:8]])
            c = cotas.get(nid, np.zeros(6)) + 5e-9 * np.abs(got) + 1e-15
            r = float((np.abs(got - u_d[nid]) / c).max())
            if r > peor:
                peor, detalle = r, 'elemento %d alfa %.4f nodo %d' % (eid, alfa, nid)
        if barras_txt:
            f_d = sol.fuerzas([int(t.split()[1]) for t in barras_txt])
            cf = cota_f(datos, rec, alfa, P)
            for t in barras_txt:
                v = t.split()
                eid_b, got = int(v[1]), np.array([float(c) for c in v[2:14]])
                c = cf[eid_b] + 5e-9 * np.abs(got) + 1e-12
                r = float((np.abs(got - f_d[eid_b]) / c).max())
                if r > peor:
                    peor, detalle = r, 'localForce de la barra %d (carga en %d)' % (eid_b, eid)
            if 'M_carga' in kv and rec['tipo'] == 'viga':
                a = alfa * rec['L']
                ref = carga_movil.esfuerzos_con_puntual(f_d[eid], 0.0, 0.0, -P, a, [a])['My'][0]
                cc = cf[eid]
                c = cc[4] + a * cc[2] + (K_F32 * EPS32 + 5e-9) * abs(ref) + 1e-12
                r = abs(float(kv['M_carga']) - ref) / c
                if r > peor:
                    peor, detalle = r, 'M bajo la carga en %d: app %s, OpenSees %.6g kN m' \
                        % (eid, kv['M_carga'], ref)
        if rec['tipo'] == 'viga':
            ref = uz_en(rec, u_d[rec['n1']], u_d[rec['n2']], alfa, alfa, P)
            N1, N2, N3, N4 = hermite(alfa)
            ci, cj = cotas[rec['n1']], cotas[rec['n2']]
            c = (N1 * ci[2] + abs(N2) * rec['L'] * (ci[3] + ci[4]) + N3 * cj[2]
                 + abs(N4) * rec['L'] * (cj[3] + cj[4]) + (K_F32 * EPS32 + 5e-9) * abs(ref) + 1e-15)
            r = abs(float(kv['uz_carga']) - ref) / c
            if r > peor:
                peor, detalle = r, 'flecha bajo la carga, elemento %d alfa %.4f: app %s m, OpenSees %.9g m'                     % (eid, alfa, kv['uz_carga'], ref)
        n_ok += 1
    fallas.check(peor <= 1.0, '[7] lo que la app sumo (%d posiciones: nodos de la viga, el que mas se mueve, '
                 'la flecha bajo la carga y, si vienen, los esfuerzos de extremo y el momento bajo la '
                 'carga) = OpenSees directo, dentro de su cota' % n_ok,
                 'peor cociente %.3f (%s)' % (peor, detalle))


def contrato_cs(js, fallas):
    if not os.path.isfile(CS_PERSONA):
        return
    clases = campos_de_clases(CS_PERSONA)
    for clase, clave in CLASES_CS.items():
        muestra = js if clave is None else (js[clave][0] if isinstance(js[clave], list) else js[clave])
        en_cs = clases.get(clase, set())
        sin_campo = sorted(k for k in set(muestra) - en_cs if k not in ('_U', '_F'))
        sin_clave = sorted(en_cs - set(muestra))
        fallas.check(clase in clases and not sin_campo and not sin_clave,
                     '[4] contrato JSON <-> C#: %s%s' % (clase, '' if not (sin_campo or sin_clave) else
                                                       ' (claves sin campo %s, campos sin clave %s)'
                                                       % (sin_campo, sin_clave)))


# ============================================================
# MAIN
# ============================================================
def main(argv=None):
    ap = argparse.ArgumentParser(description='Casos unitarios para la deformada de la persona.')
    ap.add_argument('edificio', choices=('lt2', 'ingenieria', 'conjunto'))
    ap.add_argument('--verificar', action='store_true',
                    help='no resolver los casos: comparar el JSON escrito contra OpenSees')
    ap.add_argument('--pruebas', type=int, default=N_PRUEBAS)
    ap.add_argument('--registro', metavar='REGISTRO_TXT',
                    help='con --verificar: cruzar lo que escribio CapturaPersona contra OpenSees')
    args = ap.parse_args(argv)
    ed = args.edificio
    t0 = time.time()
    fallas = Fallas()
    s4 = carga_movil.exportador_s4()
    modelo = contrato.cargar_modelo(ed)
    with io.open(rutas.unity(ed), encoding='utf-8') as f:
        vista = json.load(f)
    print('=' * 76)
    print('  DEFORMADA DE LA PERSONA   %s   %s' % (ed.upper(), 'verificar' if args.verificar else 'armar'))
    print('=' * 76)

    if args.verificar:
        ruta = salida_unity(ed)
        if not os.path.isfile(ruta):
            print('  no existe %s: correr sin --verificar' % os.path.relpath(ruta, rutas.RAIZ))
            return 1
        with io.open(ruta, encoding='utf-8') as f:
            js = json.load(f)
        fallas.check(js['info']['n_nodos'] == len(vista['nodos'])
                     and js['info']['n_elementos'] == len(vista['elementos']),
                     'el JSON es de este modelo (%d nodos, %d elementos)'
                     % (js['info']['n_nodos'], js['info']['n_elementos']))
        ahora = receptores(vista, modelo, s4, fallas)
        clave = lambda r: (r['elemento'], r['tipo'], r['nodo'], r['n1'], r['n2'], tuple(r['elementos_m']))
        iguales = (sorted(map(clave, ahora)) == sorted(map(clave, js['receptores']))
                   and all(abs(a['flex'] - b['flex']) <= 1e-9 * max(a['flex'], 1e-30)
                           for a, b in zip(sorted(ahora, key=clave),
                                           sorted(js['receptores'], key=clave))))
        fallas.check(iguales, 'los receptores y su flexibilidad son los del modelo de hoy '
                     '(si cambio una seccion, hay que volver a correrlo sin --verificar)')
        sol = Solver(modelo)
        verificar(js, modelo, sol, s4, fallas, args.pruebas)
        if args.registro:
            cruzar_registro(args.registro, js, modelo, sol, fallas)
        transcripcion(fallas)
        contrato_cs(js, fallas)
        esc, peor, donde = escala_de_dibujo(Datos(js), js['receptores'], P_POR_DEFECTO)
        fallas.check(abs(esc - js['info']['escala_deformada']) <= 1e-9 * esc,
                     '[6] la escala de dibujo es la que se calcula: x%g (%.3f mm con la carga a media '
                     'viga en el elemento %s -> %.2f m)' % (esc, peor * 1000, donde, peor * esc))
        escm, peorm, dondem = escala_de_momentos(Datos(js), js['receptores'], P_POR_DEFECTO,
                                                 largos_dibujables(modelo))
        fallas.check(abs(escm - js['info']['escala_momento']) <= 1e-9 * escm,
                     '[6] la escala de los momentos es la que se calcula: %g m por kN m (%.1f kN m en '
                     'la barra %s -> %.2f m)' % (escm, peorm, dondem, peorm * escm))
    else:
        js, sol = armar(ed, modelo, vista, s4, fallas)
        sin_cuantizar = {(c['nodo'], c['gdl']): c for c in js['casos']}
        datos = Datos(js)
        esc, peor, donde = escala_de_dibujo(datos, js['receptores'], P_POR_DEFECTO)
        js['info']['escala_deformada'] = esc
        print('  escala de dibujo: x%g (el peor, %.3f mm con %g kN a media viga en el elemento %s, '
              'se dibuja %.2f m)' % (esc, peor * 1000, P_POR_DEFECTO, donde, peor * esc))
        escm, peorm, dondem = escala_de_momentos(datos, js['receptores'], P_POR_DEFECTO,
                                                 largos_dibujables(modelo))
        js['info']['escala_momento'] = escm
        print('  escala de momentos: %g m por kN m (el mayor, %.1f kN m en la barra %s, se dibuja '
              '%.2f m)' % (escm, peorm, dondem, peorm * escm))
        verificar(js, modelo, sol, s4, fallas, args.pruebas, sin_cuantizar)
        transcripcion(fallas)
        for c in js['casos']:
            c.pop('_U', None)
            c.pop('_F', None)
        contrato_cs(js, fallas)
        if not fallas.lista:
            ruta = rutas.asegurar(salida_unity(ed))
            with io.open(ruta, 'w', encoding='utf-8') as f:
                json.dump(js, f, ensure_ascii=False, separators=(',', ':'))
            print('  escrito %s (%.1f MB)' % (os.path.relpath(ruta, rutas.RAIZ),
                                             os.path.getsize(ruta) / 1e6))
    print('  (%.0f s)' % (time.time() - t0))
    if fallas.lista:
        print('  FALLARON %d: %s' % (len(fallas.lista), '; '.join(fallas.lista)))
        if not args.verificar:
            print('  NO se escribio nada.')
        return 1
    print('  TODO OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
