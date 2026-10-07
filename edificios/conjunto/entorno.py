# -*- coding: utf-8 -*-
r"""
================================================================
 edificios/conjunto/entorno.py  -  VENTANAS, AUTOS Y ARBOLES, PARA EL VISOR
================================================================
 Lo que rodea a la estructura en la vista realista, para que se lea
 como un edificio en su campus y no como un esqueleto en un potrero:

   - VENTANAS entre pisos, en cada vano de fachada: un antepecho ciego,
     el vidrio y su marco con montantes;
   - AUTOS estacionados en los estacionamientos de verdad del campus;
   - ARBOLES en las islas de esos estacionamientos, a lo largo de las
     calles y en las areas verdes;
   - el PISO: asfalto de estacionamientos, pasillos y calles, veredas y
     las lineas de cada puesto, pegado a la malla del relieve.

 Unity solo DIBUJA (AmbienteVisor.Entorno.cs). Nada de esto entra al
 calculo: el modelo no tiene fachada, ni autos, ni arboles.

 Entradas:
   data/unity/<ed>.json                  la geometria que dibuja el visor
   data/unity/topografia_<ed>.json       el relieve (topografia.py)
   edificios/conjunto/sitio/entorno.json los supuestos, con su por que
   edificios/conjunto/sitio/osm_campus.json   OpenStreetMap (bajar_osm.py)
   edificios/conjunto/sitio/modelos/     los OBJ de Kenney (CC0)
 Salidas:
   data/unity/entorno_<ed>.json          ventanas y objetos de cada edificio
   unity/Assets/Resources/Entorno/modelos.json   las mallas de autos y arboles
   edificios/conjunto/sitio/entorno_planta.png   la planta, para mirarla

 ----------------------------------------------------------------
 LAS VENTANAS (de la geometria del modelo, nada a mano)
 ----------------------------------------------------------------
 Un piso va de una cota de losa a la siguiente. En cada cota, una viga
 es de FACHADA si a un lado hay losa (los poligonos de area tributaria,
 los mismos que dibuja AmbienteVisor.Losas.cs) y al otro no hay nada en
 10 m. Sobre esa viga, y bajo la viga del piso de arriba que corre por
 la misma linea, va un vano: entre las caras de los pilares de sus
 extremos, sin lo que tapan los muros, desde la cara de la losa (el
 mismo criterio de Losas.cs: eje + medio canto tipico + 1 cm) hasta la
 cara inferior de la viga de arriba. El piso mas bajo (sin losa) usa
 las vigas de fachada de la primera losa. Un vano con el suelo de
 afuera sobre su alfeizar esta enterrado y no lleva ventana.

 ----------------------------------------------------------------
 LOS AUTOS Y LOS ARBOLES (de OpenStreetMap, sobre el relieve)
 ----------------------------------------------------------------
 Se ubican en coordenadas del conjunto con la MISMA georreferencia del
 relieve (topografia.armar), y su cota sale de la MISMA malla que dibuja
 AmbienteVisor.Topografia.cs (los dos triangulos de cada celda de 4 m),
 asi que no flotan ni se entierran. Cada auto se inclina con el plano
 que pasa por sus cuatro ruedas. Los sorteos (que estacionamiento esta
 ocupado, que modelo, que color) usan una semilla fija: el dibujo es
 siempre el mismo y --verificar puede compararlo.

 ----------------------------------------------------------------
 QUE COMPRUEBA (termina con 1 si algo falla)
 ----------------------------------------------------------------
   [1] los modelos: medidas de cada auto, frente hacia +z, todas las
       caras con material;
   [2] las ventanas de cada edificio, de nuevo y por otro camino: del
       lado de afuera no hay losa en 10 m, ningun vidrio cruza un muro ni
       un pilar, y cada uno queda entre la losa y la viga de arriba;
   [3] los autos: dentro de su estacionamiento, sin chocar entre ellos
       ni con un pasillo, con las ruedas sobre la malla del relieve;
   [4] los arboles: sobre el relieve, lejos del edificio, fuera de
       calles, canchas, edificios y estacionamientos ocupados; y el
       piso, cada vertice a su elevacion sobre la malla del relieve;
   [5] las claves del JSON = los campos de AmbienteVisor.Entorno.cs;
   [6] con --verificar, que lo escrito en disco sea lo que se arma hoy.

   python edificios/conjunto/entorno.py               # escribe los JSON y la figura
   python edificios/conjunto/entorno.py --verificar   # no escribe: compara
================================================================
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import os
import random
import sys

import numpy as np

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(_AQUI)), 'comun'))
sys.path.insert(0, _AQUI)
import rutas                                   # noqa: E402
from campos_cs import campos_de_clases         # noqa: E402
import topografia as T                         # noqa: E402

SITIO = T.SITIO
CONFIG = os.path.join(SITIO, 'entorno.json')
OSM = os.path.join(SITIO, 'osm_campus.json')
MODELOS = os.path.join(SITIO, 'modelos')
SALIDA_MODELOS = os.path.join(rutas.UNITY_PROYECTO, 'Assets', 'Resources', 'Entorno', 'modelos.json')
FIGURA = os.path.join(SITIO, 'entorno_planta.png')
EDIFICIOS = T.EDIFICIOS
CS = os.path.join(T.SCRIPTS_CS, 'AmbienteVisor.Entorno.cs')
CLASES_CS = {'EntornoJson': None, 'InfoEntorno': 'info', 'VentanaFachada': 'ventanas', 'ObjetoSitio': 'objetos',
             'PavimentoEntorno': 'pavimentos'}
CLASES_CS_MODELOS = {'ModelosEntornoJson': None, 'InfoModelosEntorno': 'info', 'MaterialEntorno': 'materiales',
                     'ModeloEntorno': 'modelos'}

# Las mismas constantes de dibujo de AmbienteVisor (C#): si cambian alla,
# cambian aca.
TOL_EN_COTA = 0.05          # AmbienteVisor.TOL_EN_COTA
SOBRE_EL_CANTO = 0.01       # AmbienteVisor.Losas.cs, SOBRE_EL_CANTO
TOL_COTA = 0.01             # AjustesVista.TOLERANCIA_COTA

ATRIB_MODELOS = ('Autos: Car Kit 3.1 y arboles: Nature Kit 2.1, de Kenney (www.kenney.nl), CC0 1.0. '
                 'Estirados a medidas reales y recoloreados (edificios/conjunto/sitio/modelos/LICENCIA.md).')

# ------------------------------------------------------------
# Materiales de dibujo (sRGB). 'por_objeto': el color lo pone cada
# auto (pintura) o cada arbol (hojas).
# ------------------------------------------------------------
MATERIALES = [
    {'nombre': 'pintura', 'color': [0.6, 0.6, 0.6, 1.0], 'suavidad': 0.62, 'metalico': 0.25, 'por_objeto': True},
    {'nombre': 'vidrio_auto', 'color': [0.05, 0.06, 0.07, 1.0], 'suavidad': 0.92, 'metalico': 0.0, 'por_objeto': False},
    {'nombre': 'plastico', 'color': [0.10, 0.10, 0.11, 1.0], 'suavidad': 0.30, 'metalico': 0.0, 'por_objeto': False},
    {'nombre': 'oscuro', 'color': [0.06, 0.06, 0.06, 1.0], 'suavidad': 0.30, 'metalico': 0.0, 'por_objeto': False},
    {'nombre': 'gris', 'color': [0.55, 0.56, 0.58, 1.0], 'suavidad': 0.50, 'metalico': 0.30, 'por_objeto': False},
    {'nombre': 'faro', 'color': [0.92, 0.90, 0.82, 1.0], 'suavidad': 0.85, 'metalico': 0.0, 'por_objeto': False},
    {'nombre': 'freno', 'color': [0.62, 0.05, 0.04, 1.0], 'suavidad': 0.70, 'metalico': 0.0, 'por_objeto': False},
    {'nombre': 'caucho', 'color': [0.04, 0.04, 0.04, 1.0], 'suavidad': 0.15, 'metalico': 0.0, 'por_objeto': False},
    {'nombre': 'llanta', 'color': [0.62, 0.63, 0.65, 1.0], 'suavidad': 0.60, 'metalico': 0.70, 'por_objeto': False},
    {'nombre': 'hojas', 'color': [0.27, 0.38, 0.16, 1.0], 'suavidad': 0.12, 'metalico': 0.0, 'por_objeto': True},
    {'nombre': 'corteza', 'color': [0.30, 0.24, 0.18, 1.0], 'suavidad': 0.08, 'metalico': 0.0, 'por_objeto': False},
    {'nombre': 'marco', 'color': [0.22, 0.23, 0.24, 1.0], 'suavidad': 0.45, 'metalico': 0.60, 'por_objeto': False},
    {'nombre': 'antepecho', 'color': [0.78, 0.77, 0.73, 1.0], 'suavidad': 0.10, 'metalico': 0.0, 'por_objeto': False},
    {'nombre': 'vidrio_fachada', 'color': [0.30, 0.40, 0.45, 0.38], 'suavidad': 0.93, 'metalico': 0.0,
     'por_objeto': False},
    # El piso: el visor les pone la textura del hormigon de losa con este color.
    {'nombre': 'asfalto', 'color': [0.36, 0.36, 0.37, 1.0], 'suavidad': 0.15, 'metalico': 0.0, 'por_objeto': False},
    {'nombre': 'vereda', 'color': [0.86, 0.85, 0.82, 1.0], 'suavidad': 0.10, 'metalico': 0.0, 'por_objeto': False},
    {'nombre': 'linea', 'color': [0.90, 0.90, 0.88, 1.0], 'suavidad': 0.20, 'metalico': 0.0, 'por_objeto': False},
]

# Cuanto sobre la malla del relieve va cada piso (m): lo justo para que no
# pelee en profundidad con el pasto a 300 m de la camara (precision ~1 cm).
ELEVACION = {'asfalto': 0.05, 'vereda': 0.06, 'linea': 0.08}
ANCHO_LINEA = 0.12
# Triangulos mas chicos que esto no van al JSON (ver sin_degenerados): un
# cm2 en los autos y medio en los arboles, 1 cm2 en el piso, que va al cm.
AREA_MIN_M2 = 1e-4
AREA_MIN_PISO_M2 = 1e-4
ANCHO_VEREDA = 2.0

# Que parte de un auto es cada color de la textura de Kenney (8 x 4
# franjas: (fila, columna)). Mirado en una vista 3D de cada modelo: la
# fila 1 es la pintura (una franja por modelo), (3, 0) los vidrios,
# (2, 3) el plastico de abajo y del techo, (2, 2) lo negro, (2, 6) las
# patentes y espejos, (3, 1) los focos delanteros y (3, 2) los traseros.
# En las ruedas, (2, 2) es el neumatico y lo demas la llanta.
PARTE_CARROCERIA = {(2, 3): 'plastico', (2, 2): 'oscuro', (3, 0): 'vidrio_auto', (2, 6): 'gris',
                    (3, 1): 'faro', (3, 2): 'freno'}
FILA_PINTURA = 1


class Fallas(T.Fallas):
    pass


def leer_json(ruta):
    with io.open(ruta, encoding='utf-8') as f:
        return json.load(f)


def rel(ruta):
    return os.path.relpath(ruta, rutas.RAIZ).replace(os.sep, '/')


def r3(v):
    return round(float(v), 3)


def r4(v):
    return round(float(v), 4)


# ============================================================
# 1. LOS MODELOS (OBJ de Kenney -> mallas en ejes de Unity)
# ============================================================
def leer_obj(ruta):
    """Vertices, coordenadas de textura y caras [(grupo, material, vi, ti)]."""
    V, Tx, F = [], [], []
    grupo, mat = None, None
    for linea in io.open(ruta, encoding='utf-8'):
        p = linea.split()
        if not p:
            continue
        if p[0] == 'v':
            V.append([float(c) for c in p[1:4]])
        elif p[0] == 'vt':
            Tx.append([float(c) for c in p[1:3]])
        elif p[0] in ('g', 'o'):
            grupo = p[1] if len(p) > 1 else None
        elif p[0] == 'usemtl':
            mat = p[1]
        elif p[0] == 'f':
            vi, ti = [], []
            for t in p[1:]:
                c = t.split('/')
                vi.append(int(c[0]) - 1)
                ti.append(int(c[1]) - 1 if len(c) > 1 and c[1] else -1)
            F.append((grupo, mat, vi, ti))
    return np.array(V, float), (np.array(Tx, float) if Tx else None), F


def franja(uv):
    """(fila, columna) de la franja de color de la textura de Kenney."""
    col = min(7, max(0, int(uv[0] * 8)))
    fila = min(3, max(0, int((1.0 - uv[1]) * 4)))
    return fila, col


def a_unity(v):
    """OBJ (mano derecha, Y arriba) -> Unity (mano izquierda): espejo en x."""
    return np.array([-v[0], v[1], v[2]])


def area3(t):
    """Area de un triangulo [x0, y0, z0, x1, ..., z2]."""
    a, b, c = np.array(t[0:3]), np.array(t[3:6]), np.array(t[6:9])
    return 0.5 * float(np.linalg.norm(np.cross(b - a, c - a)))


def sin_degenerados(planos, decimales, area_min):
    """Los triangulos (9 numeros cada uno) redondeados como van al JSON, sin
    los de area casi nula. Kenney trae algunos (los 7 autos: 2 a 7 por pieza)
    y el recorte del piso deja astillas: Unity les calcula una normal nula,
    al girarlos y escalarlos alguno pinta un par de pixeles con esa normal
    (NaN en la luz) y el bloom de la vista realista lo infla a un disco
    blanco de metros. Devuelve (lista plana, cuantos se sacaron)."""
    out, fuera = [], 0
    for k in range(0, len(planos) - 8, 9):
        t = [round(float(x), decimales) for x in planos[k:k + 9]]
        if area3(t) < area_min:
            fuera += 1
            continue
        out.extend(t)
    return out, fuera


def triangulos(F):
    """Cada cara en abanico; con el espejo se invierte el orden."""
    for g, m, vi, ti in F:
        for k in range(1, len(vi) - 1):
            yield g, m, (vi[0], vi[k + 1], vi[k]), (ti[0], ti[k + 1], ti[k])


def modelo_auto(m):
    V, Tx, F = leer_obj(os.path.join(MODELOS, 'autos', m['nombre'] + '.obj'))
    U = np.array([a_unity(v) for v in V])
    mn, mx = U.min(0), U.max(0)
    centro = np.array([0.5 * (mn[0] + mx[0]), mn[1], 0.5 * (mn[2] + mx[2])])
    U = U - centro
    s = np.array([m['ancho_m'] / (mx[0] - mn[0]), m['alto_m'] / (mx[1] - mn[1]), m['largo_m'] / (mx[2] - mn[2])])
    # Cada rueda se escala pareja (con la escala de la altura) en su centro,
    # que se corre con la carroceria: asi sigue redonda.
    nuevo = U * s
    centros = {}
    for g, mat, vi, ti in F:
        if g and g.startswith('wheel'):
            centros.setdefault(g, set()).update(vi)
    frente = []
    for g, idx in centros.items():
        idx = sorted(idx)
        c = 0.5 * (U[idx].min(0) + U[idx].max(0))
        for i in idx:
            d = U[i] - c
            nuevo[i] = c * s + np.array([d[0] * s[0], d[1] * s[1], d[2] * s[1]])
        if 'front' in g:
            frente.append(c[2])
    # La rueda de repuesto (suv: 'wheel-back') sale atras de la carroceria y,
    # escalada pareja, acorta el largo: se corrige al final, igual en todo
    # el auto (las ruedas quedan a lo mas 2 % fuera de redondas).
    tam = nuevo.max(0) - nuevo.min(0)
    nuevo = nuevo * (np.array([m['ancho_m'], m['alto_m'], m['largo_m']]) / tam)
    pintura = {}
    for g, mat, vi, ti in F:
        if g == 'body':
            fr = franja(Tx[ti].mean(0))
            if fr[0] == FILA_PINTURA:
                pintura[fr] = pintura.get(fr, 0) + 1
    franja_pintura = max(pintura, key=pintura.get) if pintura else None
    partes, sin_parte = {}, 0
    for g, mat, (a, b, c), (ta, tb, tc) in triangulos(F):
        fr = franja((Tx[ta] + Tx[tb] + Tx[tc]) / 3.0)
        if g and g.startswith('wheel'):
            parte = 'caucho' if fr == (2, 2) else 'llanta'
        elif fr == franja_pintura:
            parte = 'pintura'
        else:
            parte = PARTE_CARROCERIA.get(fr)
            if parte is None:
                sin_parte += 1
                parte = 'gris'
        partes.setdefault(parte, []).extend(nuevo[[a, b, c]].reshape(-1).tolist())
    tam = nuevo.max(0) - nuevo.min(0)
    fuera = 0
    for k in list(partes):
        partes[k], n = sin_degenerados(partes[k], 3, AREA_MIN_M2)
        fuera += n
    return {
        'nombre': m['nombre'], 'tipo': 'auto',
        'largo_m': r3(tam[2]), 'ancho_m': r3(tam[0]), 'alto_m': r3(tam[1]),
        'partes': [{'material': k, 'vertices': v} for k, v in sorted(partes.items())],
    }, {'frente_z': frente, 'sin_parte': sin_parte, 'franja_pintura': franja_pintura,
        'triangulos': sum(len(v) // 9 for v in partes.values()), 'degenerados': fuera}


def modelo_arbol(m):
    V, Tx, F = leer_obj(os.path.join(MODELOS, 'arboles', m['nombre'] + '.obj'))
    U = np.array([a_unity(v) for v in V])
    alto = U[:, 1].max() - U[:, 1].min()
    # El pie del tronco (lo de corteza en el 10 % de abajo) va al origen.
    tronco = sorted({i for g, mat, vi, ti in F if mat and mat.startswith('wood') for i in vi
                     if U[i, 1] - U[:, 1].min() < 0.1 * alto})
    base = U[tronco].mean(0) if tronco else U.mean(0)
    U = (U - np.array([base[0], U[:, 1].min(), base[2]])) / alto        # alto 1: la escala es la altura
    partes = {}
    for g, mat, (a, b, c), _ in triangulos(F):
        parte = 'hojas' if mat and mat.startswith('leaf') else 'corteza'
        partes.setdefault(parte, []).extend(U[[a, b, c]].reshape(-1).tolist())
    tam = U.max(0) - U.min(0)
    fuera = 0
    for k in list(partes):
        # Alto 1: el area minima se escala con el arbol mas alto (15 m).
        partes[k], n = sin_degenerados(partes[k], 4, AREA_MIN_M2 / 15.0 ** 2)
        fuera += n
    return {
        'nombre': m['nombre'], 'tipo': 'arbol',
        'largo_m': r3(tam[2]), 'ancho_m': r3(tam[0]), 'alto_m': r3(tam[1]),
        'partes': [{'material': k, 'vertices': v} for k, v in sorted(partes.items())],
    }, {'triangulos': sum(len(v) // 9 for v in partes.values()), 'degenerados': fuera}


def armar_modelos(conf, f):
    print('\n[1] Los modelos (Kenney, CC0)')
    modelos = []
    for m in conf['autos']['modelos']:
        mod, d = modelo_auto(m)
        modelos.append(mod)
        ok = (abs(mod['largo_m'] - m['largo_m']) < 0.01 and abs(mod['ancho_m'] - m['ancho_m']) < 0.01
              and abs(mod['alto_m'] - m['alto_m']) < 0.01)
        f.check(ok and d['frente_z'] and min(d['frente_z']) > 0 and d['sin_parte'] == 0
                and d['franja_pintura'] is not None,
                'auto %-17s %.2f x %.2f x %.2f m (pedido %.2f x %.2f x %.2f), frente hacia +z, %d triangulos, '
                'pintura en la franja %s, %d caras sin material, %d degenerados sacados'
                % (m['nombre'], mod['largo_m'], mod['ancho_m'], mod['alto_m'], m['largo_m'], m['ancho_m'],
                   m['alto_m'], d['triangulos'], d['franja_pintura'], d['sin_parte'], d['degenerados']))
    for m in conf['arboles']['modelos']:
        mod, d = modelo_arbol(m)
        modelos.append(mod)
        mats = {p['material'] for p in mod['partes']}
        f.check(abs(mod['alto_m'] - 1.0) < 1e-3 and mats == {'hojas', 'corteza'},
                'arbol %-24s alto 1 (la escala es la altura), copa %.2f x %.2f, %d triangulos, hojas y corteza, '
                '%d degenerados sacados' % (m['nombre'], mod['ancho_m'], mod['largo_m'], d['triangulos'],
                                            d['degenerados']))
    return {
        'info': {
            'fuente': ATRIB_MODELOS,
            'generado_por': 'edificios/conjunto/entorno.py',
            '_por_que': ('Solo DIBUJO: autos y arboles de la vista realista, en ejes de Unity (y arriba, el '
                         'frente del auto hacia +z), con el pie en el origen. Los vertices van de a tres por '
                         'triangulo (caras planas, el estilo del modelo). Los autos en metros; los arboles con '
                         'alto 1: la escala de cada uno es su altura.'),
        },
        'materiales': MATERIALES,
        'modelos': modelos,
    }


# ============================================================
# 2. EL RELIEVE QUE DIBUJA UNITY
# ============================================================
class Relieve(object):
    """La cara de arriba de AmbienteVisor.Topografia.cs, de un topografia_<ed>.json:
    una celda es terreno si sus 4 nodos tienen cota y su centro no cae en un
    hueco, y se dibuja con los triangulos (a, d, c) y (a, c, b)."""

    def __init__(self, t):
        self.x0, self.y0, self.paso = float(t['x0']), float(t['y0']), float(t['paso'])
        self.nx, self.ny = int(t['nx']), int(t['ny'])
        self.z = np.array(t['z'], float).reshape(self.ny, self.nx)
        self.huecos = t['huecos']
        con = self.z > float(t['sin_dato']) * 0.5
        self.terreno = np.zeros((self.ny - 1, self.nx - 1), bool)
        for j in range(self.ny - 1):
            for i in range(self.nx - 1):
                xc, yc = self.x0 + (i + 0.5) * self.paso, self.y0 + (j + 0.5) * self.paso
                self.terreno[j, i] = (con[j, i] and con[j, i + 1] and con[j + 1, i] and con[j + 1, i + 1]
                                      and not self.en_hueco(xc, yc))

    def en_hueco(self, x, y, margen=0.0):
        return any(h['x1'] - margen <= x <= h['x2'] + margen and h['y1'] - margen <= y <= h['y2'] + margen
                   for h in self.huecos)

    def cota(self, x, y):
        fi, fj = (x - self.x0) / self.paso, (y - self.y0) / self.paso
        i, j = int(math.floor(fi)), int(math.floor(fj))
        if i < 0 or j < 0 or i >= self.nx - 1 or j >= self.ny - 1 or not self.terreno[j, i]:
            return None
        s, t = fi - i, fj - j
        za, zb = self.z[j, i], self.z[j, i + 1]
        zc, zd = self.z[j + 1, i + 1], self.z[j + 1, i]
        if t >= s:
            return float(za + t * (zd - za) + s * (zc - zd))
        return float(za + s * (zb - za) + t * (zc - zb))


# ============================================================
# Geometria en planta
# ============================================================
def en_poligono(p, poli):
    """Rayo hacia +x (sirve para poligonos no convexos)."""
    x, y = p
    dentro = False
    n = len(poli)
    for k in range(n):
        x1, y1 = poli[k]
        x2, y2 = poli[(k + 1) % n]
        if (y1 > y) != (y2 > y):
            xc = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xc > x:
                dentro = not dentro
    return dentro


def dist_segmento(p, a, b):
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def dist_polilinea(p, linea):
    return min(dist_segmento(p, linea[k], linea[k + 1]) for k in range(len(linea) - 1))


def rectangulo(c, u, a, b):
    """Las 4 esquinas de un rectangulo de centro c, eje largo u (unitario),
    largo a (en u) y ancho b."""
    n = (-u[1], u[0])
    return [(c[0] + su * u[0] * a / 2 + sn * n[0] * b / 2, c[1] + su * u[1] * a / 2 + sn * n[1] * b / 2)
            for su, sn in ((1, 1), (-1, 1), (-1, -1), (1, -1))]


def se_cruzan(R1, R2):
    """Dos rectangulos (4 esquinas cada uno) se cruzan: ejes separadores."""
    for R in (R1, R2):
        for k in range(2):
            ex, ey = R[k + 1][0] - R[k][0], R[k + 1][1] - R[k][1]
            ax = (-ey, ex)
            p1 = [q[0] * ax[0] + q[1] * ax[1] for q in R1]
            p2 = [q[0] * ax[0] + q[1] * ax[1] for q in R2]
            if max(p1) <= min(p2) + 1e-9 or max(p2) <= min(p1) + 1e-9:
                return False
    return True


def area_firmada(poli):
    return 0.5 * sum(poli[k][0] * poli[(k + 1) % len(poli)][1] - poli[(k + 1) % len(poli)][0] * poli[k][1]
                     for k in range(len(poli)))


# ============================================================
# 3. LAS VENTANAS (de cada edificio, en sus coordenadas)
# ============================================================
def poligonos_de_losa(visor):
    """{cota al cm: [poligono]} de areas_tributarias (cada entrada puede
    traer varios poligonos: 'tamanos')."""
    out = {}
    for a in visor.get('areas_tributarias', []):
        vs = [(v['x'], v['y']) for v in a['vertices']]
        tam = a.get('tamanos') or [len(vs)]
        k = 0
        for n in tam:
            poli = vs[k:k + n]
            k += n
            if len(poli) >= 3:
                out.setdefault(int(round(a['z'] * 100)), []).append(poli)
    return out


def hay_losa(p, polis):
    return any(en_poligono(p, q) for q in polis)


def canto_tipico(visor, secs, N, z):
    """AmbienteVisor.Losas.CantoTipico: el h de seccion mas repetido entre
    las barras con los dos nodos en z (sin muros ni brazos); empate, el mayor."""
    cuenta = {}
    for e in visor['elementos']:
        if e['tipo'] in ('muro', 'brazo', 'brazo_rigido'):
            continue
        a, b = N.get(e['n1']), N.get(e['n2'])
        if a is None or b is None or abs(a['z'] - z) > TOL_EN_COTA or abs(b['z'] - z) > TOL_EN_COTA:
            continue
        s = secs.get(e['seccion'])
        if s is None or not (s.get('b', 0) > 0.001 and s.get('h', 0) > 0.001):
            continue
        h = round(float(s['h']), 6)
        cuenta[h] = cuenta.get(h, 0) + 1
    mejor, n = 0.0, 0
    for h, c in cuenta.items():
        if c > n or (c == n and h > mejor):
            mejor, n = h, c
    return mejor


def vigas_en(visor, secs, N, z):
    """Barras horizontales con perfil en la cota z (sin muros, brazos ni diagonales)."""
    out = []
    for e in visor['elementos']:
        if e['tipo'] in ('muro', 'brazo', 'brazo_rigido', 'diagonal'):
            continue
        a, b = N.get(e['n1']), N.get(e['n2'])
        if a is None or b is None or abs(a['z'] - z) > TOL_COTA or abs(b['z'] - z) > TOL_COTA:
            continue
        L = math.hypot(b['x'] - a['x'], b['y'] - a['y'])
        s = secs.get(e['seccion'], {})
        if L < 0.3:
            continue
        out.append({'id': e['id'], 'a': (a['x'], a['y']), 'b': (b['x'], b['y']), 'L': L,
                    'h': float(s.get('h', 0.0)), 'bw': float(s.get('b', 0.0))})
    return out


def verticales(visor, secs, N):
    """Columnas y muros con su planta (para recortar los vanos)."""
    cols, muros = [], []
    for e in visor['elementos']:
        a, b = N.get(e['n1']), N.get(e['n2'])
        if a is None or b is None:
            continue
        if math.hypot(b['x'] - a['x'], b['y'] - a['y']) > 0.01 or abs(b['z'] - a['z']) < 0.5:
            continue
        z1, z2 = sorted((a['z'], b['z']))
        s = secs.get(e['seccion'], {})
        if e['tipo'] == 'muro':
            largo, esp = float(e.get('largo') or 0), float(e.get('espesor') or 0)
            if largo < 0.01 or esp < 0.01:
                largo, esp = float(s.get('largo') or 0), float(s.get('espesor') or 0)
            d = e.get('dir_largo') or (e.get('vecxz') or [1, 0])[:2]
            nd = math.hypot(d[0], d[1]) or 1.0
            muros.append({'id': e['id'], 'c': (a['x'], a['y']), 'z1': z1, 'z2': z2, 'd': (d[0] / nd, d[1] / nd),
                          'largo': largo, 'esp': esp})
        elif e['tipo'] not in ('brazo', 'brazo_rigido', 'diagonal'):
            cols.append({'id': e['id'], 'c': (a['x'], a['y']), 'z1': z1, 'z2': z2, 'b': float(s.get('b', 0.0)),
                         'h': float(s.get('h', 0.0)), 'ly': e.get('localY'), 'lz': e.get('localZ')})
    return cols, muros


def medio_ancho_columna(c, u):
    """Medio ancho de la columna a lo largo de u, como la dibuja
    VisorEstructura.CrearPerfil (h a lo largo de localZ, b de localY)."""
    if c['ly'] and c['lz']:
        return 0.5 * (c['h'] * abs(c['lz'][0] * u[0] + c['lz'][1] * u[1])
                      + c['b'] * abs(c['ly'][0] * u[0] + c['ly'][1] * u[1]))
    return 0.5 * max(c['b'], c['h'])


def restar(intervalos, a, b):
    out = []
    for x0, x1 in intervalos:
        if b <= x0 or a >= x1:
            out.append((x0, x1))
            continue
        if a > x0:
            out.append((x0, a))
        if b < x1:
            out.append((b, x1))
    return out


def lado_de_fachada(v, polis, conf):
    """+1 / -1: hacia que lado de la viga (normal izquierda) esta AFUERA; 0 si no es de fachada."""
    ux, uy = (v['b'][0] - v['a'][0]) / v['L'], (v['b'][1] - v['a'][1]) / v['L']
    n = (-uy, ux)
    lados = {}
    for sgn in (1, -1):
        con = sin = 0
        for t in (0.2, 0.5, 0.8):
            px, py = v['a'][0] + ux * v['L'] * t, v['a'][1] + uy * v['L'] * t
            con += any(hay_losa((px + sgn * n[0] * d, py + sgn * n[1] * d), polis)
                       for d in conf['muestras_con_losa_m'])
            sin += all(not hay_losa((px + sgn * n[0] * d, py + sgn * n[1] * d), polis)
                       for d in conf['muestras_sin_losa_m'])
        lados[sgn] = (con > 0, sin == 3)
    if lados[1][0] and lados[-1][1]:
        return -1
    if lados[-1][0] and lados[1][1]:
        return 1
    return 0


class Suelo(object):
    """El suelo que se ve afuera de una fachada: el relieve; en su hueco,
    la terraza que lo cubra o el fondo de la excavacion."""

    def __init__(self, relieve, visor):
        self.relieve = relieve
        info = visor['info']
        self.fondo = float(info.get('cota_terreno', -9999.0))
        self.terrazas = [((float(t['z'])), [(v['x'], v['y']) for v in t['vertices']])
                         for t in info.get('terrenos', []) if t.get('vertices')]

    def cota(self, x, y):
        z = self.relieve.cota(x, y) if self.relieve is not None else None
        if z is not None:
            return z
        for zt, poli in self.terrazas:
            if en_poligono((x, y), poli):
                return zt
        return self.fondo


def armar_ventanas(visor, suelo, conf):
    N = {n['id']: n for n in visor['nodos']}
    secs = {s['nombre']: s for s in visor['secciones']}
    losas = poligonos_de_losa(visor)
    cotas = sorted(losas)
    base = float(visor['info'].get('cota_terreno', -9999.0))
    pisos = []
    if base > -9000 and int(round(base * 100)) < cotas[0]:
        pisos.append((base, cotas[0] / 100.0, None))
    for k in range(len(cotas) - 1):
        pisos.append((cotas[k] / 100.0, cotas[k + 1] / 100.0, cotas[k]))
    cols, muros = verticales(visor, secs, N)
    ventanas, descartes = [], {'enterrada': 0, 'angosta': 0, 'sin_viga_arriba': 0}
    for zb, zt, clave_b in pisos:
        clave_t = int(round(zt * 100))
        # Las vigas de fachada se buscan en la losa del piso (en el piso sin
        # losa, en la de arriba).
        clave_ref = clave_b if clave_b is not None else clave_t
        z_ref = clave_ref / 100.0
        polis = losas[clave_ref]
        arriba = vigas_en(visor, secs, N, zt)
        z_piso = zb + 0.5 * canto_tipico(visor, secs, N, zb) + SOBRE_EL_CANTO if clave_b is not None else zb
        zm = 0.5 * (zb + zt)
        cols_p = [c for c in cols if c['z1'] < zm < c['z2']]
        muros_p = [m for m in muros if m['z1'] < zm < m['z2']]
        for v in vigas_en(visor, secs, N, z_ref):
            lado = lado_de_fachada(v, polis, conf)
            if lado == 0:
                continue
            ux, uy = (v['b'][0] - v['a'][0]) / v['L'], (v['b'][1] - v['a'][1]) / v['L']
            nx, ny = -uy * lado, ux * lado
            # La viga de arriba por la misma linea: el tramo que se solapa.
            tramos = []
            for w in arriba:
                wx, wy = (w['b'][0] - w['a'][0]) / w['L'], (w['b'][1] - w['a'][1]) / w['L']
                if abs(wx * uy - wy * ux) > 0.02:
                    continue
                if max(dist_segmento(w['a'], (v['a'][0] - ux * 1e3, v['a'][1] - uy * 1e3),
                                     (v['a'][0] + ux * 1e3, v['a'][1] + uy * 1e3)),
                       dist_segmento(w['b'], (v['a'][0] - ux * 1e3, v['a'][1] - uy * 1e3),
                                     (v['a'][0] + ux * 1e3, v['a'][1] + uy * 1e3))) > 0.05:
                    continue
                s1 = (w['a'][0] - v['a'][0]) * ux + (w['a'][1] - v['a'][1]) * uy
                s2 = (w['b'][0] - v['a'][0]) * ux + (w['b'][1] - v['a'][1]) * uy
                a, b = max(0.0, min(s1, s2)), min(v['L'], max(s1, s2))
                if b - a > 0.05:
                    tramos.append((a, b, w['h']))
            if not tramos:
                descartes['sin_viga_arriba'] += 1
                continue
            for a, b, h_arriba in tramos:
                libres = [(a, b)]
                for c in cols_p:
                    if dist_segmento(c['c'], v['a'], v['b']) > 0.05 + 1e-9:
                        continue
                    sc = (c['c'][0] - v['a'][0]) * ux + (c['c'][1] - v['a'][1]) * uy
                    m = medio_ancho_columna(c, (ux, uy))
                    libres = restar(libres, sc - m, sc + m)
                for mu in muros_p:
                    d = mu['d']
                    sc = (mu['c'][0] - v['a'][0]) * ux + (mu['c'][1] - v['a'][1]) * uy
                    dn = abs((mu['c'][0] - v['a'][0]) * (-uy) + (mu['c'][1] - v['a'][1]) * ux)
                    paralelo = abs(d[0] * uy - d[1] * ux) < 0.15
                    if paralelo and dn < 0.5 * mu['esp'] + 0.45:
                        libres = restar(libres, sc - 0.5 * mu['largo'], sc + 0.5 * mu['largo'])
                    elif not paralelo and dn < 0.5 * mu['largo'] + 0.05:
                        # Un muro que llega de canto a la fachada.
                        libres = restar(libres, sc - 0.5 * mu['esp'], sc + 0.5 * mu['esp'])
                for s0, s1 in libres:
                    ancho = s1 - s0
                    if ancho < conf['ancho_minimo_m']:
                        descartes['angosta'] += 1
                        continue
                    z_tope = zt - 0.5 * h_arriba
                    alto = z_tope - z_piso
                    if alto < 1.5:
                        descartes['angosta'] += 1
                        continue
                    antepecho = min(conf['antepecho_m'], alto - 1.0)
                    off = conf['plano_afuera_del_eje_m']
                    x0 = v['a'][0] + ux * s0 + nx * off
                    y0 = v['a'][1] + uy * s0 + ny * off
                    suelo_afuera = max(suelo.cota(x0 + ux * ancho * t + nx * d, y0 + uy * ancho * t + ny * d)
                                       for t in (0.15, 0.5, 0.85) for d in conf['afuera_para_el_suelo_m'])
                    if suelo_afuera > z_piso + antepecho - 0.05:
                        descartes['enterrada'] += 1
                        continue
                    ventanas.append({
                        'piso': r3(zb), 'x': r3(x0), 'y': r3(y0), 'z': r3(z_piso),
                        'ux': r4(ux), 'uy': r4(uy), 'nx': r4(nx), 'ny': r4(ny),
                        'ancho': r3(ancho), 'alto': r3(alto), 'antepecho': r3(antepecho),
                        'divisiones': int(math.ceil(ancho / conf['pano_max_m'] - 1e-9)),
                    })
    return ventanas, descartes, {'losas': losas, 'cols': cols, 'muros': muros, 'pisos': pisos}


def comprobar_ventanas(ed, ventanas, aux, conf, f):
    """Por otro camino: cada vano, ya armado, contra la losa, los pilares y los muros."""
    losas = aux['losas']
    lejos = conf['muestras_sin_losa_m']
    mal_afuera = mal_muro = mal_col = mal_alto = 0
    area = 0.0
    for v in ventanas:
        zb = v['piso']
        zt = next(t for b, t, _ in aux['pisos'] if abs(b - zb) < 1e-6)
        clave = int(round(zb * 100)) if int(round(zb * 100)) in losas else int(round(zt * 100))
        u, n = (v['ux'], v['uy']), (v['nx'], v['ny'])
        for t in (0.1, 0.5, 0.9):
            p = (v['x'] + u[0] * v['ancho'] * t, v['y'] + u[1] * v['ancho'] * t)
            if any(hay_losa((p[0] + n[0] * d, p[1] + n[1] * d), losas[clave]) for d in lejos):
                mal_afuera += 1
                break
        # El vidrio, como segmento en planta un poco hacia adentro del borde:
        seg = [(v['x'] + u[0] * 0.02, v['y'] + u[1] * 0.02),
               (v['x'] + u[0] * (v['ancho'] - 0.02), v['y'] + u[1] * (v['ancho'] - 0.02))]
        zm = 0.5 * (zb + zt)
        rv = rectangulo(((seg[0][0] + seg[1][0]) / 2, (seg[0][1] + seg[1][1]) / 2), u,
                        math.hypot(seg[1][0] - seg[0][0], seg[1][1] - seg[0][1]), 0.02)
        for m in aux['muros']:
            if m['z1'] < zm < m['z2'] and se_cruzan(rv, rectangulo(m['c'], m['d'], m['largo'], m['esp'])):
                mal_muro += 1
                break
        for c in aux['cols']:
            if c['z1'] < zm < c['z2']:
                ma = medio_ancho_columna(c, u)
                mb = medio_ancho_columna(c, (-u[1], u[0]))
                if se_cruzan(rv, rectangulo(c['c'], u, 2 * ma, 2 * mb)):
                    mal_col += 1
                    break
        if not (v['alto'] > 1.5 and v['z'] >= zb - 1e-6 and v['z'] + v['alto'] <= zt + 1e-6
                and 0 <= v['antepecho'] < v['alto']):
            mal_alto += 1
        area += v['ancho'] * (v['alto'] - v['antepecho'])
    f.check(ventanas and mal_afuera == 0,
            '%s: %d vanos con ventana; del lado de afuera ninguno tiene losa en %.0f m' % (ed, len(ventanas), max(lejos)))
    f.check(mal_muro == 0 and mal_col == 0,
            '%s: ningun vidrio cruza un muro (%d) ni un pilar (%d) de su piso' % (ed, mal_muro, mal_col))
    f.check(mal_alto == 0, '%s: cada vano queda entre su losa y la viga de arriba, con el antepecho adentro (%d fuera)'
            % (ed, mal_alto))
    return area


# ============================================================
# 4. EL SITIO (OpenStreetMap en coordenadas del conjunto)
# ============================================================
ANCHO_CALLE = {'tertiary': 8.0, 'tertiary_link': 6.0, 'residential': 7.0, 'living_street': 6.0,
               'service': 5.0, 'unclassified': 6.0, 'footway': 2.0, 'path': 1.5, 'steps': 2.0}


def sitio_osm(geo):
    d = leer_json(OSM)

    def m(ll):
        return [geo.a_modelo(*geo.local.a_metros(lon, lat)) for lon, lat in ll]
    s = {'estacionamientos': [], 'pasillos': [], 'calles': [], 'edificios': [], 'verdes': [], 'canchas': [],
         'otros': [], 'atribucion': d['atribucion']}
    for v in d['vias']:
        t = v['tags']
        pts = m(v['lonlat'])
        cerrado = len(pts) > 3 and v['lonlat'][0] == v['lonlat'][-1]
        if cerrado:
            pts = pts[:-1]
        if 'highway' in t:
            if t.get('service') == 'parking_aisle':
                s['pasillos'].append(pts)
            else:
                s['calles'].append((t['highway'], pts))
        elif t.get('amenity') == 'parking' and cerrado:
            s['estacionamientos'].append(pts)
        elif 'building' in t and cerrado:
            s['edificios'].append(pts)
        elif t.get('leisure') == 'pitch' and cerrado:
            s['canchas'].append(pts)
        elif (t.get('landuse') == 'grass' or t.get('leisure') == 'park' or t.get('natural') == 'heath') and cerrado:
            s['verdes'].append(pts)
        elif cerrado and (t.get('landuse') == 'construction' or t.get('natural') == 'water'
                          or t.get('leisure') == 'swimming_pool' or t.get('amenity') == 'fountain'):
            # Ojo: amenity=university es el campus ENTERO, no un lugar sin arboles.
            s['otros'].append(pts)
    # Un 'service' que corre dentro de un estacionamiento tambien es pasillo.
    calles = []
    for tipo, pts in s['calles']:
        if tipo == 'service' and any(en_poligono(pts[len(pts) // 2], e) for e in s['estacionamientos']):
            s['pasillos'].append(pts)
        else:
            calles.append((tipo, pts))
    s['calles'] = calles
    return s


def sorteo(rng, items, clave='peso'):
    r = rng.random() * sum(i[clave] for i in items)
    for i in items:
        r -= i[clave]
        if r <= 0:
            return i
    return items[-1]


def plano_bajo(relieve, puntos):
    """Plano z = a x + b y + c por minimos cuadrados sobre las cotas de la
    malla en esos puntos; None si alguno cae fuera del terreno."""
    zs = [relieve.cota(*p) for p in puntos]
    if any(z is None for z in zs):
        return None
    A = np.array([[p[0], p[1], 1.0] for p in puntos])
    sol, *_ = np.linalg.lstsq(A, np.array(zs), rcond=None)
    desv = max(abs(A[k] @ sol - zs[k]) for k in range(len(zs)))
    return sol, desv


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def armar_autos(sitio, relieve, conf, rng):
    ca = conf['autos']
    ancho, largo, medio = ca['ancho_estacionamiento_m'], ca['largo_estacionamiento_m'], ca['medio_pasillo_m']
    puestos = []
    for k_e, est in enumerate(sitio['estacionamientos']):
        pasillos = [p for p in sitio['pasillos'] if any(en_poligono(q, est) for q in p)]
        for k_p, pas in enumerate(pasillos):
            for k_s in range(len(pas) - 1):
                a, b = pas[k_s], pas[k_s + 1]
                L = math.hypot(b[0] - a[0], b[1] - a[1])
                if L < ancho:
                    continue
                u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
                n = (-u[1], u[0])
                n_puestos = int((L - 0.5) // ancho)
                s0 = 0.5 * (L - n_puestos * ancho) + 0.5 * ancho
                for lado in (1, -1):
                    fila = []
                    for k in range(n_puestos):
                        s = s0 + k * ancho
                        c = (a[0] + u[0] * s + lado * n[0] * (medio + largo / 2),
                             a[1] + u[1] * s + lado * n[1] * (medio + largo / 2))
                        frente = (lado * n[0], lado * n[1])
                        R = rectangulo(c, frente, largo, ancho)
                        if not all(en_poligono(q, est) for q in R):
                            continue
                        if any(relieve.cota(*q) is None for q in R + [c]):
                            continue
                        if relieve.en_hueco(c[0], c[1], 2.0):
                            continue
                        if any(min(dist_polilinea(q, p) for p in sitio['pasillos']) < medio - 0.3 for q in R):
                            continue
                        if any(se_cruzan(R, p['R']) for p in puestos):
                            continue
                        pl = plano_bajo(relieve, R)
                        if pl is None or math.hypot(pl[0][0], pl[0][1]) > ca['pendiente_max']:
                            continue
                        p = {'c': c, 'frente': frente, 'R': R, 'est': k_e}
                        puestos.append(p)
                        fila.append(p)
                    # Islas con arbol: una cada 'arbol_cada' de la fila.
                    for k, p in enumerate(fila):
                        p['isla'] = (k % ca['arbol_cada'] == ca['arbol_cada'] // 2)
    autos, islas = [], []
    for p in puestos:
        if p['isla']:
            islas.append(p)
            continue
        if rng.random() >= ca['ocupacion']:
            continue
        m = sorteo(rng, ca['modelos'])
        col = sorteo(rng, ca['colores'])
        # De punta (75 %) o de reversa; un poco corrido y girado, como de verdad.
        sentido = 1.0 if rng.random() < 0.75 else -1.0
        giro = math.radians((rng.random() - 0.5) * 6.0)
        f0 = (p['frente'][0] * sentido, p['frente'][1] * sentido)
        fr = (f0[0] * math.cos(giro) - f0[1] * math.sin(giro), f0[0] * math.sin(giro) + f0[1] * math.cos(giro))
        lat = (-fr[1], fr[0])
        corr = (rng.random() - 0.5) * 0.3
        c = (p['c'][0] + lat[0] * corr, p['c'][1] + lat[1] * corr)
        ruedas = [(c[0] + sf * fr[0] * 0.36 * m['largo_m'] + sl * lat[0] * 0.42 * m['ancho_m'],
                   c[1] + sf * fr[1] * 0.36 * m['largo_m'] + sl * lat[1] * 0.42 * m['ancho_m'])
                  for sf in (1, -1) for sl in (1, -1)]
        pl = plano_bajo(relieve, ruedas)
        if pl is None:
            continue
        (pa, pb, pc), desv = pl
        arriba = unit([-pa, -pb, 1.0])
        f3 = np.array([fr[0], fr[1], pa * fr[0] + pb * fr[1]])
        f3 = unit(f3 - (f3 @ arriba) * arriba)
        z = pa * c[0] + pb * c[1] + pc + ELEVACION['asfalto']
        autos.append({'tipo': 'auto', 'modelo': m['nombre'], 'x': c[0], 'y': c[1], 'z': z,
                      'frente': f3.tolist(), 'arriba': arriba.tolist(), 'escala': 1.0,
                      'color': list(col['rgb']), '_largo': m['largo_m'], '_ancho': m['ancho_m'], '_desv': desv,
                      '_puesto': p})
    return autos, islas, puestos


def armar_arboles(sitio, relieve, conf, rng, puestos, islas, autos):
    ca = conf['arboles']
    candidatos = []
    # Las islas de los estacionamientos: el arbol en la cabecera del puesto.
    for p in islas:
        candidatos.append(('isla', (p['c'][0] + p['frente'][0] * 1.2, p['c'][1] + p['frente'][1] * 1.2)))
    # El borde de los estacionamientos, por fuera.
    for est in sitio['estacionamientos']:
        signo = 1.0 if area_firmada(est) > 0 else -1.0
        for k in range(len(est)):
            a, b = est[k], est[(k + 1) % len(est)]
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if L < 1.0:
                continue
            u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
            afuera = (u[1] * signo, -u[0] * signo)
            s = 0.5 * ca['borde_estacionamiento_cada_m']
            while s < L:
                candidatos.append(('borde', (a[0] + u[0] * s + afuera[0] * ca['borde_estacionamiento_afuera_m'],
                                             a[1] + u[1] * s + afuera[1] * ca['borde_estacionamiento_afuera_m'])))
                s += ca['borde_estacionamiento_cada_m']
    # Filas a los dos lados de las calles.
    for tipo, pts in sitio['calles']:
        if tipo not in ('residential', 'tertiary', 'tertiary_link', 'living_street', 'service', 'unclassified'):
            continue
        off = 0.5 * ANCHO_CALLE.get(tipo, 6.0) + ca['afuera_de_la_calle_m']
        acum = 0.5 * ca['por_calles_cada_m']
        for k in range(len(pts) - 1):
            a, b = pts[k], pts[k + 1]
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if L < 1e-6:
                continue
            u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
            s = acum
            while s < L:
                for lado in (1, -1):
                    candidatos.append(('calle', (a[0] + u[0] * s - lado * u[1] * off,
                                                 a[1] + u[1] * s + lado * u[0] * off)))
                s += ca['por_calles_cada_m']
            acum = s - L
    # Las areas verdes: una grilla con un corrimiento al azar.
    paso = ca['en_areas_verdes_cada_m']
    for ver in sitio['verdes']:
        xs, ys = [p[0] for p in ver], [p[1] for p in ver]
        x = math.floor(min(xs) / paso) * paso
        while x < max(xs):
            y = math.floor(min(ys) / paso) * paso
            while y < max(ys):
                q = (x + (rng.random() - 0.5) * 10.0, y + (rng.random() - 0.5) * 10.0)
                if en_poligono(q, ver):
                    candidatos.append(('verde', q))
                y += paso
            x += paso

    # Grupos sueltos en el terreno libre: una grilla con corrimiento al azar,
    # y se queda donde un ruido suave (periodo ~60 m) pasa un umbral, asi
    # salen bosquetes y claros en vez de un huerto parejo.
    paso = ca['libre_cada_m']
    fases = [(rng.random() * 2 * math.pi, rng.random() * 2 * math.pi, rng.random() * 2 * math.pi)
             for _ in range(3)]

    def ruido(x, y):
        v = 0.0
        for k, (a1, a2, a3) in enumerate(fases):
            w = 2 * math.pi / (60.0 / (k + 1))
            v += (math.sin(w * x + a1) * math.cos(w * 0.8 * y + a2) + math.sin(w * 0.6 * (x + y) + a3)) / (k + 1)
        return v / 3.0
    x = math.floor(relieve.x0 / paso) * paso
    while x < relieve.x0 + (relieve.nx - 1) * relieve.paso:
        y = math.floor(relieve.y0 / paso) * paso
        while y < relieve.y0 + (relieve.ny - 1) * relieve.paso:
            q = (x + (rng.random() - 0.5) * 0.8 * paso, y + (rng.random() - 0.5) * 0.8 * paso)
            if ruido(*q) > ca['libre_umbral']:
                candidatos.append(('libre', q))
            y += paso
        x += paso

    rects_autos = [rectangulo((a['x'], a['y']), (a['frente'][0], a['frente'][1]), a['_largo'], a['_ancho'])
                   for a in autos]
    aceptados = []
    for tipo, q in candidatos:
        if len(aceptados) >= ca['maximo']:
            break
        alrededor = [(q[0] + dx, q[1] + dy) for dx, dy in ((0.4, 0), (-0.4, 0), (0, 0.4), (0, -0.4))]
        cotas = [relieve.cota(*p) for p in [q] + alrededor]
        if any(z is None for z in cotas):
            continue
        if relieve.en_hueco(q[0], q[1], ca['lejos_del_edificio_m']):
            continue
        if any(en_poligono(q, e) or dist_polilinea(q, e + e[:1]) < 1.5 for e in sitio['edificios']):
            continue
        if any(en_poligono(q, c) for c in sitio['canchas'] + sitio['otros']):
            continue
        if tipo != 'isla' and any(en_poligono(q, e) for e in sitio['estacionamientos']):
            continue
        if any(dist_polilinea(q, pts) < 0.5 * ANCHO_CALLE.get(t, 6.0) + 1.0 for t, pts in sitio['calles']):
            continue
        if any(dist_polilinea(q, pas) < 3.5 for pas in sitio['pasillos']):
            continue
        # El tronco (0.8 m) no puede caer en un auto: el cuadro va alineado con
        # cada auto, que es como estan las filas.
        if any(se_cruzan(rectangulo(q, (a['frente'][0], a['frente'][1]), 0.8, 0.8), R)
               for a, R in zip(autos, rects_autos)):
            continue
        if tipo == 'libre' and relieve.en_hueco(q[0], q[1], ca['libre_lejos_del_edificio_m']):
            continue
        if any(math.hypot(q[0] - a['x'], q[1] - a['y']) < ca['separacion_min_m'] for a in aceptados):
            continue
        modelos = ca['modelos'] if tipo != 'isla' else [m for m in ca['modelos'] if 'pine' not in m['nombre']
                                                          and m['nombre'] != 'tree_tall']
        m = sorteo(rng, modelos)
        alto = m['alto_m'][0] + rng.random() * (m['alto_m'][1] - m['alto_m'][0])
        rgb = list(ca['color_pino']) if 'pine' in m['nombre'] else list(sorteo(rng, ca['colores_hoja'])['rgb'])
        ang = rng.random() * 2.0 * math.pi
        aceptados.append({'tipo': 'arbol', 'modelo': m['nombre'], 'x': q[0], 'y': q[1], 'z': min(cotas) - 0.05,
                          'frente': [math.cos(ang), math.sin(ang), 0.0], 'arriba': [0.0, 0.0, 1.0],
                          'escala': alto, 'color': rgb, '_donde': tipo})
    return aceptados


def comprobar_sitio(sitio, relieve, conf, autos, arboles, f):
    ca = conf['autos']
    print('\n[3] Los autos (estacionamientos y pasillos de OpenStreetMap)')
    fuera = choques = pasillo = flotan = 0
    rects = []
    for a in autos:
        R = rectangulo((a['x'], a['y']), (a['frente'][0], a['frente'][1]), a['_largo'], a['_ancho'])
        if not any(all(en_poligono(q, e) for q in R) for e in sitio['estacionamientos']):
            fuera += 1
        if any(se_cruzan(R, S) for S in rects):
            choques += 1
        rects.append(R)
        if any(min(dist_polilinea(q, p) for p in sitio['pasillos']) < ca['medio_pasillo_m'] - 0.6 for q in R):
            pasillo += 1
        if a['_desv'] > 0.05:
            flotan += 1
    pend = max((math.degrees(math.acos(min(1.0, a['arriba'][2]))) for a in autos), default=0.0)
    f.check(len(autos) > 0 and fuera == 0,
            '%d autos, cada uno entero dentro de un estacionamiento (%d fuera)' % (len(autos), fuera))
    f.check(choques == 0 and pasillo == 0,
            'ningun auto choca con otro (%d) ni se mete al pasillo (%d)' % (choques, pasillo))
    f.check(flotan == 0, 'las 4 ruedas de cada auto a menos de 5 cm de la malla del relieve (peor %.1f cm; '
            'inclinacion maxima %.1f grados)' % (100 * max((a['_desv'] for a in autos), default=0), pend))
    print('\n[4] Los arboles')
    ca = conf['arboles']
    sin_suelo = cerca = en_calle = juntos = 0
    for k, t in enumerate(arboles):
        z = relieve.cota(t['x'], t['y'])
        if z is None or not (z - 0.5 <= t['z'] <= z):
            sin_suelo += 1
        if relieve.en_hueco(t['x'], t['y'], ca['lejos_del_edificio_m'] - 1e-6):
            cerca += 1
        if any(dist_polilinea((t['x'], t['y']), pts) < 0.5 * ANCHO_CALLE.get(tp, 6.0)
               for tp, pts in sitio['calles']) or any(en_poligono((t['x'], t['y']), c) for c in sitio['canchas']) \
                or any(en_poligono((t['x'], t['y']), e) for e in sitio['edificios']):
            en_calle += 1
        if any(math.hypot(t['x'] - s['x'], t['y'] - s['y']) < ca['separacion_min_m'] - 1e-6 for s in arboles[:k]):
            juntos += 1
    donde = {}
    for t in arboles:
        donde[t['_donde']] = donde.get(t['_donde'], 0) + 1
    f.check(len(arboles) > 0 and sin_suelo == 0,
            '%d arboles (%s), con el pie en la malla del relieve (%d no)'
            % (len(arboles), ', '.join('%d %s' % (v, k) for k, v in sorted(donde.items())), sin_suelo))
    f.check(cerca == 0 and en_calle == 0 and juntos == 0,
            'ninguno a menos de %.0f m de un cuerpo (%d), en una calle, cancha o edificio (%d), ni a menos de '
            '%.0f m de otro (%d)' % (ca['lejos_del_edificio_m'], cerca, en_calle, ca['separacion_min_m'], juntos))


# ============================================================
# 4b. EL PISO: ASFALTO, VEREDAS Y LINEAS, PEGADOS AL RELIEVE
# ============================================================
# Cada pieza (un triangulo del estacionamiento, el tramo de una calle, una
# linea de estacionamiento) se recorta contra los triangulos de la malla
# del relieve, y cada trozo toma el plano de SU triangulo: el piso queda
# exactamente sobre el pasto (mas ELEVACION), sin hundirse entre dos nodos
# de la malla ni flotar.
def antihorario(poli):
    return poli if area_firmada(poli) > 0 else poli[::-1]


def orejas(poli):
    """Triangula un poligono simple (corte de orejas). Triangulos antihorarios."""
    p = []
    for q in antihorario(poli):
        if not p or math.hypot(q[0] - p[-1][0], q[1] - p[-1][1]) > 1e-6:
            p.append(q)
    if len(p) > 1 and math.hypot(p[0][0] - p[-1][0], p[0][1] - p[-1][1]) < 1e-6:
        p.pop()
    tris = []

    def cruz(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    while len(p) > 3:
        n = len(p)
        for k in range(n):
            a, b, c = p[k - 1], p[k], p[(k + 1) % n]
            if cruz(a, b, c) <= 1e-12:
                continue
            if any(cruz(a, b, q) >= 0 and cruz(b, c, q) >= 0 and cruz(c, a, q) >= 0
                   for q in p if q not in (a, b, c)):
                continue
            tris.append([a, b, c])
            del p[k]
            break
        else:
            break                           # degenerado: lo que queda no tiene orejas
    if len(p) == 3 and cruz(*p) > 1e-12:
        tris.append(p)
    return tris


def recortar(sujeto, recorte):
    """Sutherland-Hodgman: el poligono 'sujeto' dentro del convexo antihorario 'recorte'."""
    salida = list(sujeto)
    for k in range(len(recorte)):
        if not salida:
            break
        a, b = recorte[k], recorte[(k + 1) % len(recorte)]
        ex, ey = b[0] - a[0], b[1] - a[1]

        def adentro(q):
            return ex * (q[1] - a[1]) - ey * (q[0] - a[0]) >= -1e-12

        def corte(p1, p2):
            dx, dy = p2[0] - p1[0], p2[1] - p1[1]
            den = dx * ey - dy * ex
            t = ((a[0] - p1[0]) * ey - (a[1] - p1[1]) * ex) / den if abs(den) > 1e-15 else 0.0
            return (p1[0] + t * dx, p1[1] + t * dy)
        entrada, salida = salida, []
        for j in range(len(entrada)):
            p1, p2 = entrada[j - 1], entrada[j]
            if adentro(p2):
                if not adentro(p1):
                    salida.append(corte(p1, p2))
                salida.append(p2)
            elif adentro(p1):
                salida.append(corte(p1, p2))
    return salida


def drapear(relieve, pieza, dz, salida):
    """Agrega a 'salida' (x, y, z de a tres por triangulo) la pieza convexa
    recortada contra los triangulos de la malla del relieve. Devuelve el area."""
    pieza = antihorario(pieza)
    xs, ys = [q[0] for q in pieza], [q[1] for q in pieza]
    i0 = max(0, int(math.floor((min(xs) - relieve.x0) / relieve.paso)))
    i1 = min(relieve.nx - 2, int(math.floor((max(xs) - relieve.x0) / relieve.paso)))
    j0 = max(0, int(math.floor((min(ys) - relieve.y0) / relieve.paso)))
    j1 = min(relieve.ny - 2, int(math.floor((max(ys) - relieve.y0) / relieve.paso)))
    area = 0.0
    for j in range(j0, j1 + 1):
        for i in range(i0, i1 + 1):
            if not relieve.terreno[j, i]:
                continue
            x0, y0, h = relieve.x0 + i * relieve.paso, relieve.y0 + j * relieve.paso, relieve.paso
            za, zb = relieve.z[j, i], relieve.z[j, i + 1]
            zc, zd = relieve.z[j + 1, i + 1], relieve.z[j + 1, i]
            # Los dos triangulos que dibuja Unity: (a, d, c) y (a, c, b).
            for tri in (((x0, y0, za), (x0, y0 + h, zd), (x0 + h, y0 + h, zc)),
                        ((x0, y0, za), (x0 + h, y0 + h, zc), (x0 + h, y0, zb))):
                trozo = recortar(antihorario([(q[0], q[1]) for q in tri]), pieza)
                if len(trozo) < 3 or area_firmada(trozo) < 1e-4:
                    continue
                (ax, ay, az), (bx, by, bz), (cx, cy, cz) = tri
                n = np.cross([bx - ax, by - ay, bz - az], [cx - ax, cy - ay, cz - az])
                area += area_firmada(trozo)
                for k in range(1, len(trozo) - 1):
                    for q in (trozo[0], trozo[k], trozo[k + 1]):
                        z = az - (n[0] * (q[0] - ax) + n[1] * (q[1] - ay)) / n[2] + dz
                        salida.extend((float(q[0]), float(q[1]), float(z)))
    return area


def tira(a, b, ancho):
    """El rectangulo de ancho 'ancho' a lo largo de a-b."""
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    if L < 1e-6:
        return None
    nx, ny = -(b[1] - a[1]) / L * ancho / 2, (b[0] - a[0]) / L * ancho / 2
    return [(a[0] - nx, a[1] - ny), (b[0] - nx, b[1] - ny), (b[0] + nx, b[1] + ny), (a[0] + nx, a[1] + ny)]


def octogono(c, r):
    return [(c[0] + r * math.cos(k * math.pi / 4), c[1] + r * math.sin(k * math.pi / 4)) for k in range(8)]


def armar_pisos(sitio, relieve, puestos):
    """{material: [x, y, z, ...]} y cuanto se dibujo."""
    pisos = {'asfalto': [], 'vereda': [], 'linea': []}
    resumen = {'asfalto_m2': 0.0, 'vereda_m2': 0.0, 'lineas': 0}
    for est in sitio['estacionamientos']:
        for t in orejas(est):
            resumen['asfalto_m2'] += drapear(relieve, t, ELEVACION['asfalto'], pisos['asfalto'])
    tramos = [(2 * 3.0, pas, 'asfalto') for pas in sitio['pasillos']]      # el pasillo de 6 m
    for tipo, pts in sitio['calles']:
        if tipo in ('footway', 'path', 'steps', 'pedestrian'):
            tramos.append((ANCHO_VEREDA, pts, 'vereda'))
        elif tipo in ANCHO_CALLE:
            tramos.append((ANCHO_CALLE[tipo], pts, 'asfalto'))
    for ancho, pts, mat in tramos:
        clave = mat + '_m2'
        for k in range(len(pts) - 1):
            r = tira(pts[k], pts[k + 1], ancho)
            if r:
                resumen[clave] += drapear(relieve, r, ELEVACION[mat], pisos[mat])
        for q in pts[1:-1]:                 # las uniones entre tramos
            drapear(relieve, octogono(q, ancho / 2), ELEVACION[mat], pisos[mat])
    # Las lineas que separan los puestos: los dos lados largos de cada uno
    # (los compartidos, una vez).
    hechas = set()
    for p in puestos:
        f, c = p['frente'], p['c']
        n = (-f[1], f[0])
        for lado in (1, -1):
            m = (c[0] + lado * n[0] * 1.25, c[1] + lado * n[1] * 1.25)
            clave = (round(m[0], 1), round(m[1], 1))
            if clave in hechas:
                continue
            hechas.add(clave)
            a = (m[0] - f[0] * 2.4, m[1] - f[1] * 2.4)
            b = (m[0] + f[0] * 2.4, m[1] + f[1] * 2.4)
            drapear(relieve, tira(a, b, ANCHO_LINEA), ELEVACION['linea'], pisos['linea'])
            resumen['lineas'] += 1
    return pisos, resumen


def comprobar_pisos(pisos, resumen, relieve, f):
    """Cada vertice del piso, a su elevacion sobre la malla (con el redondeo
    a 1 cm del JSON: a lo mas 5 mm en z y 5 mm en planta por la pendiente)."""
    peor, fuera = 0.0, 0
    for mat, v in pisos.items():
        for k in range(0, len(v), 3):
            x, y, z = round(v[k], 2), round(v[k + 1], 2), round(v[k + 2], 2)
            zr = None
            for dx, dy in ((0, 0), (1e-3, 1e-3), (-1e-3, 1e-3), (1e-3, -1e-3), (-1e-3, -1e-3)):
                zr = relieve.cota(x + dx, y + dy)
                if zr is not None:
                    break
            if zr is None:
                fuera += 1
                continue
            peor = max(peor, abs(z - ELEVACION[mat] - zr))
    f.check(fuera == 0 and peor < 0.01,
            'el piso (%.0f m2 de asfalto, %.0f m2 de veredas y %d lineas de estacionamiento) va sobre la malla '
            'del relieve, cada vertice a su elevacion (peor %.1f mm con el redondeo del JSON; %d fuera)'
            % (resumen['asfalto_m2'], resumen['vereda_m2'], resumen['lineas'], 1000 * peor, fuera))


# ============================================================
# 5. EL JSON DE CADA EDIFICIO
# ============================================================
def para_edificio(ed, visor, topo, conf, objetos_conj, pisos, d, f):
    relieve = Relieve(topo)
    suelo = Suelo(relieve, visor)
    ventanas, descartes, aux = armar_ventanas(visor, suelo, conf['ventanas'])
    por_piso = {}
    for v in ventanas:
        por_piso[v['piso']] = por_piso.get(v['piso'], 0) + 1
    print('  %s: %s; sin ventana: %d enterrados, %d angostos, %d sin viga arriba'
          % (ed, ', '.join('piso %.2f: %d' % kv for kv in sorted(por_piso.items())), descartes['enterrada'],
             descartes['angosta'], descartes['sin_viga_arriba']))
    area = comprobar_ventanas(ed, ventanas, aux, conf['ventanas'], f)
    objetos = []
    for o in objetos_conj:
        x, y, z = o['x'] - d[0], o['y'] - d[1], o['z'] - d[2]
        objetos.append({'tipo': o['tipo'], 'modelo': o['modelo'], 'x': r3(x), 'y': r3(y), 'z': r3(z),
                        'frente': [r4(c) for c in o['frente']], 'arriba': [r4(c) for c in o['arriba']],
                        'escala': r3(o['escala']), 'color': [r3(c) for c in o['color']]})
    # Los objetos del sitio, en las coordenadas de este edificio, siguen
    # sobre SU relieve (el mismo, corrido por el calce).
    mal = sum(1 for o in objetos if relieve.cota(o['x'], o['y']) is None
              or abs(relieve.cota(o['x'], o['y']) + (0.0 if o['tipo'] == 'arbol' else ELEVACION['asfalto'])
                     - o['z']) > (0.6 if o['tipo'] == 'arbol' else 0.06))
    f.check(mal == 0, '%s: los %d autos y arboles caen sobre el relieve de este edificio (%d no)'
            % (ed, len(objetos), mal))
    cv = conf['ventanas']
    return {
        'info': {
            'edificio': ed,
            'n_nodos': len(visor['nodos']),
            'n_elementos': len(visor['elementos']),
            'generado_por': 'edificios/conjunto/entorno.py',
            'fuente_sitio': 'Estacionamientos, pasillos, calles y areas verdes: ' + SITIO_ATRIB,
            'modelos': ATRIB_MODELOS,
            'marco_m': cv['marco_m'],
            'profundidad_marco_m': cv['profundidad_marco_m'],
            'espesor_antepecho_m': cv['espesor_antepecho_m'],
            'n_ventanas': len(ventanas),
            'n_autos': sum(1 for o in objetos if o['tipo'] == 'auto'),
            'n_arboles': sum(1 for o in objetos if o['tipo'] == 'arbol'),
            'area_vidrio_m2': round(area, 1),
            '_por_que': ('Solo DIBUJO. Ventanas: en cada vano de fachada entre la cara de la losa y la viga de '
                         'arriba, entre las caras de los pilares y sin lo que tapan los muros (el antepecho y '
                         'el marco son supuestos: edificios/conjunto/sitio/entorno.json). Autos y arboles: '
                         'donde estan los estacionamientos, calles y areas verdes en OpenStreetMap, sobre la '
                         'misma malla del relieve. Ningun calculo lo usa.'),
        },
        'ventanas': ventanas,
        'objetos': objetos,
        'pavimentos': [{'material': mat, 'vertices': sin_degenerados([v - d[k % 3] for k, v in enumerate(vs)], 2,
                                                                     AREA_MIN_PISO_M2)[0]}
                       for mat, vs in sorted(pisos.items()) if vs],
    }


SITIO_ATRIB = '(c) OpenStreetMap contributors, ODbL 1.0'


def constante_cs(archivo, nombre):
    """El valor de 'const float <nombre> = <v>f;' en un .cs de Scripts."""
    import re
    with io.open(os.path.join(T.SCRIPTS_CS, archivo), encoding='utf-8') as fh:
        m = re.search(r'const\s+float\s+%s\s*=\s*([-0-9.]+)f\s*;' % nombre, fh.read())
    return float(m.group(1)) if m else None


def contrato_cs(js, modelos, f):
    print('\n[5] El contrato con AmbienteVisor.Entorno.cs')
    # Las constantes de dibujo que se copiaron del C#, leidas del C#: si
    # alguien las cambia alla, las ventanas dejan de calzar con las losas.
    for archivo, nombre, valor in (('AmbienteVisor.Losas.cs', 'SOBRE_EL_CANTO', SOBRE_EL_CANTO),
                                   ('AmbienteVisor.cs', 'TOL_EN_COTA', TOL_EN_COTA)):
        cs = constante_cs(archivo, nombre)
        f.check(cs is not None and abs(cs - valor) < 1e-9,
                '%s = %s en %s y %s aca' % (nombre, cs, archivo, valor))
    if not os.path.isfile(CS):
        f.check(False, 'existe %s' % rel(CS))
        return
    clases = campos_de_clases(CS)
    pares = [(js, CLASES_CS), (modelos, CLASES_CS_MODELOS)]
    for raiz, mapa in pares:
        for clase, clave in mapa.items():
            muestra = raiz if clave is None else (raiz[clave][0] if isinstance(raiz[clave], list) else raiz[clave])
            en_cs = clases.get(clase, set())
            sin_campo = sorted(set(muestra) - en_cs)
            sin_clave = sorted(en_cs - set(muestra))
            f.check(clase in clases and not sin_campo and not sin_clave,
                    'JSON <-> C#: %s%s' % (clase, '' if not (sin_campo or sin_clave) else
                                          ' (claves sin campo %s, campos sin clave %s)' % (sin_campo, sin_clave)))
    parte = modelos['modelos'][0]['partes'][0]
    en_cs = clases.get('ParteModelo', set())
    f.check(set(parte) == en_cs, 'JSON <-> C#: ParteModelo')
    mats_cs = set(MATERIALES_EN_CS())
    usados = ({p['material'] for m in modelos['modelos'] for p in m['partes']}
              | {'marco', 'antepecho', 'vidrio_fachada'} | {p['material'] for p in js['pavimentos']})
    f.check(usados <= {m['nombre'] for m in MATERIALES} and mats_cs <= {m['nombre'] for m in MATERIALES},
            'cada material que usan los modelos y las ventanas esta en la paleta (%d)' % len(MATERIALES))


def MATERIALES_EN_CS():
    """Los nombres de material que el C# pide por nombre (entre comillas)."""
    import re
    with io.open(CS, encoding='utf-8') as fh:
        src = fh.read()
    return re.findall(r'MatEntorno\("(\w+)"', src)


def figura(r, sitio, autos, arboles, ventanas_conj, ruta):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as Pol
    fig, ax = plt.subplots(figsize=(11, 11))
    zona = r['zona']
    ax.add_patch(Pol(zona, closed=True, fc='#eef3e6', ec='#888', lw=0.8, label='zona del relieve'))
    for v in sitio['verdes']:
        ax.add_patch(Pol(v, closed=True, fc='#cfe6b8', ec='none'))
    for c in sitio['canchas']:
        ax.add_patch(Pol(c, closed=True, fc='#a9d18e', ec='#6a9a4a', lw=0.5))
    for e in sitio['estacionamientos']:
        ax.add_patch(Pol(e, closed=True, fc='#ddd', ec='#999', lw=0.6))
    for e in sitio['edificios']:
        ax.add_patch(Pol(e, closed=True, fc='#bbb', ec='#777', lw=0.6))
    for tipo, pts in sitio['calles']:
        ax.plot([p[0] for p in pts], [p[1] for p in pts], '-', color='#555' if tipo != 'footway' else '#bbb',
                lw=2.0 if tipo != 'footway' else 0.7)
    for pts in sitio['pasillos']:
        ax.plot([p[0] for p in pts], [p[1] for p in pts], '--', color='#777', lw=0.8)
    for a in autos:
        R = rectangulo((a['x'], a['y']), (a['frente'][0], a['frente'][1]), a['_largo'], a['_ancho'])
        ax.add_patch(Pol(R, closed=True, fc=tuple(a['color']), ec='k', lw=0.3))
    for t in arboles:
        ax.add_patch(plt.Circle((t['x'], t['y']), 0.28 * t['escala'], fc=tuple(t['color']), ec='none', alpha=0.85))
    for v in ventanas_conj:
        x2, y2 = v['x'] + v['ux'] * v['ancho'], v['y'] + v['uy'] * v['ancho']
        ax.plot([v['x'], x2], [v['y'], y2], '-', color='#2b6f9e', lw=2.2, solid_capstyle='butt')
    for cu in ('antiguo', 'lt2'):
        ns = r['cuerpos'][cu]
        ax.plot([n['x'] for n in ns], [n['y'] for n in ns], '.', color='#c33' if cu == 'lt2' else '#335',
                ms=1.5)
    ax.set_aspect('equal')
    xs, ys = [p[0] for p in zona], [p[1] for p in zona]
    ax.set_xlim(min(xs) - 5, max(xs) + 5)
    ax.set_ylim(min(ys) - 5, max(ys) + 5)
    ax.set_xlabel('x del modelo [m]')
    ax.set_ylabel('y del modelo [m]')
    ax.set_title('Entorno del visor en coordenadas del conjunto: %d autos, %d arboles, %d vanos con ventana\n'
                 'Estacionamientos y calles: (c) OpenStreetMap contributors; modelos: Kenney (CC0)'
                 % (len(autos), len(arboles), len(ventanas_conj)), fontsize=10)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(ruta, dpi=90)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Ventanas, autos y arboles para el visor')
    ap.add_argument('--verificar', action='store_true', help='no escribe: compara con lo que hay en disco')
    a = ap.parse_args(argv)
    print('=' * 70)
    print('  VENTANAS, AUTOS Y ARBOLES (edificios/conjunto/entorno.py)')
    print('=' * 70)
    f = Fallas()
    conf = leer_json(CONFIG)
    modelos = armar_modelos(conf, f)

    ft = T.Fallas()
    with contextlib.redirect_stdout(io.StringIO()):
        r = T.armar(ft)
    f.check(not ft.lista, 'la georreferencia del relieve (topografia.armar) se arma sin fallas')
    sitio = sitio_osm(r['geo'])
    print('  OpenStreetMap: %d estacionamientos, %d pasillos, %d calles, %d edificios, %d areas verdes, %d canchas'
          % (len(sitio['estacionamientos']), len(sitio['pasillos']), len(sitio['calles']), len(sitio['edificios']),
             len(sitio['verdes']), len(sitio['canchas'])))
    topo_conj = leer_json(rutas.unity('topografia_conjunto'))
    relieve_conj = Relieve(topo_conj)
    rng = random.Random(conf['autos']['semilla'])
    autos, islas, puestos = armar_autos(sitio, relieve_conj, conf, rng)
    arboles = armar_arboles(sitio, relieve_conj, conf, rng, puestos, islas, autos)
    print('  %d puestos de estacionamiento (%d islas con arbol), %d ocupados' % (len(puestos), len(islas), len(autos)))
    comprobar_sitio(sitio, relieve_conj, conf, autos, arboles, f)
    pisos, resumen_pisos = armar_pisos(sitio, relieve_conj, puestos)
    comprobar_pisos(pisos, resumen_pisos, relieve_conj, f)

    print('\n[2] Las ventanas de cada edificio')
    salidas, ventanas_conj = {}, []
    for ed in EDIFICIOS:
        visor = leer_json(rutas.unity(ed))
        topo = leer_json(rutas.unity('topografia_' + ed))
        if ed == 'conjunto':
            d = (0.0, 0.0, 0.0)
        else:
            c = r['calce'][ed]
            d = (float(c['dx']), float(c['dy']), float(c.get('dz', 0.0)))
        js = para_edificio(ed, visor, topo, conf, autos + arboles, pisos, d, f)
        salidas[ed] = js
        if ed == 'conjunto':
            ventanas_conj = js['ventanas']
    contrato_cs(salidas['conjunto'], modelos, f)

    print('\n[6] Los archivos')
    archivos = [(SALIDA_MODELOS, modelos)] + [(rutas.unity('entorno_' + ed), js) for ed, js in salidas.items()]
    for ruta, js in archivos:
        if a.verificar:
            igual = os.path.isfile(ruta) and leer_json(ruta) == json.loads(json.dumps(js))
            f.check(igual, '%s es el que se arma ahora' % rel(ruta))
        else:
            os.makedirs(os.path.dirname(ruta), exist_ok=True)
            with io.open(ruta, 'w', encoding='utf-8', newline='\n') as fh:
                json.dump(js, fh, ensure_ascii=False, separators=(',', ':'))
            print('  -> %s (%.0f KB)' % (rel(ruta), os.path.getsize(ruta) / 1024))
    if not a.verificar:
        figura(r, sitio, autos, arboles, ventanas_conj, FIGURA)
        print('  -> %s' % rel(FIGURA))
    print('=' * 70)
    if f.lista:
        print('  FALLA: %d' % len(f.lista))
        for x in f.lista:
            print('   - ' + x)
        return 1
    print('  VENTANAS EN LA FACHADA, AUTOS EN LOS ESTACIONAMIENTOS Y ARBOLES SOBRE EL RELIEVE')
    return 0


if __name__ == '__main__':
    sys.exit(main())
