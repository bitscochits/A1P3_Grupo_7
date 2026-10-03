# -*- coding: utf-8 -*-
r"""
================================================================
 semana06_lab/verificar_ar.py
   LA APP DE AR, CRITERIO POR CRITERIO
================================================================
 Un bloque por criterio de la rubrica, cada uno con numeros:

   [1] ELEMENTO / ID     cada elementTag y nodeTag de web/datos/ar.json
                         existe en data/modelo/conjunto.json con los mismos
                         nodos, tipo y seccion; y la linea de OpenSees del
                         anexo nombra ese mismo tag y esos mismos nodos.
   [2] RESULTADO         cada numero de la app (esfuerzos por estacion,
                         desplazamientos, demanda y curva P-M) es IDENTICO
                         al del anexo de OpenSees: la app no calcula.
   [3] REGISTRO          la pose del marcador (ejes ortonormales y derechos,
                         en la cara de la columna, a la altura declarada) y
                         la transformacion modelo -> anchor: la de web/ar.js,
                         corrida en Chrome, contra la de exportar_ar.py.
   [4] IMAGE TRACKING    se genera un VIDEO SINTETICO de la imagen impresa,
                         vista desde una pose CONOCIDA con la camara que
                         supone MindAR, y se le da a Chrome como si fuera la
                         camara. La app tiene que detectar la imagen y
                         recuperar esa pose: distancia e inclinacion.

   python semana06_lab/verificar_ar.py
   python semana06_lab/verificar_ar.py --sin-navegador     # solo [1] y [2]
================================================================
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'comun'))
import rutas                                   # noqa: E402

sys.path.insert(0, AQUI)
import exportar_ar as ex                       # noqa: E402

AR = os.path.join(AQUI, 'web', 'datos', 'ar.json')
CONFIG = ex.CONFIG                    # main() los cambia con --config (otro conjunto de datos)
MARCADOR = os.path.join(AQUI, 'web', 'marcador.png')
PUERTO = 8093
NAVEGADORES = (r'C:\Program Files\Google\Chrome\Application\chrome.exe',
               r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
               r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
EPS = 4.0 * sys.float_info.epsilon


class Informe(object):
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


def titulo(t):
    print()
    print(t)
    print('-' * min(len(t), 78))


# ============================================================
# [1] y [2]
# ============================================================
def bloque_ids(ar, modelo, anexo, inf):
    titulo('[1] ELEMENTO / ID: los tags de la app son los de OpenSees')
    E = {e['id']: e for e in modelo['elementos']}
    N = {n['id']: n for n in modelo['nodos']}
    A = {e['id']: e for e in anexo['elementos']}
    malos = []
    for e in ar['elementos']:
        m = E.get(e['id'])
        if m is None or (m['n1'], m['n2'], m['tipo'], m['seccion']) != (e['n1'], e['n2'], e['tipo'], e['seccion']):
            malos.append('elemento %s' % e['id'])
            continue
        linea = A[e['id']]['tag_opensees']
        if not linea.startswith('element elasticBeamColumn %d %d %d ' % (e['id'], e['n1'], e['n2'])):
            malos.append('tag_opensees de %d: %s' % (e['id'], linea[:60]))
        if e['tag_opensees'] != linea:
            malos.append('la app lleva otra linea de OpenSees para %d' % e['id'])
    inf.check(not malos, '%d elementos: mismo elementTag, nodos, tipo y seccion que el modelo; la linea '
              '"element elasticBeamColumn <tag> <n1> <n2>" del anexo nombra los mismos' % len(ar['elementos']), malos[:5])
    malos = [n['id'] for n in ar['nodos'] if n['id'] not in N or
             (N[n['id']]['x'], N[n['id']]['y'], N[n['id']]['z']) != (n['x'], n['y'], n['z'])]
    inf.check(not malos, '%d nodos: mismo nodeTag y las mismas x, y, z de OpenSees' % len(ar['nodos']), malos[:5])
    obj = E[ar['objetivo']]
    tipo_ok = {'abajo': obj['tipo'].startswith('viga'), 'foto': True}.get(ar['marcador']['cara'], obj['tipo'] == 'columna')
    inf.check(ar['marcador']['elemento'] == ar['objetivo'] and tipo_ok,
              'el marcador esta en el elemento %d (%s %s), el mismo que muestra la app'
              % (obj['id'], obj['tipo'], obj['seccion']))


def bloque_resultados(ar, anexo, inf):
    titulo('[2] RESULTADO ESTRUCTURAL: cada numero de la app es el de OpenSees')
    en = {e['id'] for e in ar['elementos']}
    nn = {n['id'] for n in ar['nodos']}
    casos_a = {c['nombre']: c for c in anexo['casos']}
    inf.check([c['nombre'] for c in ar['casos']] == [c['nombre'] for c in anexo['casos']],
              'los %d casos del anexo, en el mismo orden' % len(ar['casos']))
    n_num, distintos = 0, []
    for c in ar['casos']:
        ca = casos_a[c['nombre']]
        for s in ca['esfuerzos']:
            if s['id'] in en:
                mine = c['esfuerzos'][str(s['id'])]
                for k in ('x', 'f') + ex.MAGNITUDES:
                    n_num += len(s[k])
                    if mine[k] != s[k]:
                        distintos.append('%s %s %s' % (c['nombre'], s['id'], k))
        for d in ca['desplazamientos']:
            if d['id'] in nn:
                n_num += 6
                if c['desplazamientos'][str(d['id'])] != [d[k] for k in ('ux', 'uy', 'uz', 'rx', 'ry', 'rz')]:
                    distintos.append('%s nodo %s' % (c['nombre'], d['id']))
        for d in ca['demandas']:
            if d['id'] in en:
                n_num += 6
                if c['demandas'][str(d['id'])] != {k: d[k] for k in ('P', 'M', 'Mn', 'u', 'pasa', 'extremo')}:
                    distintos.append('%s demanda %s' % (c['nombre'], d['id']))
    for k, f in ar['familias'].items():
        fa = anexo['familias'][int(k)]
        n_num += len(fa['P']) + len(fa['Mn'])
        if (f['P'], f['Mn']) != (fa['P'], fa['Mn']):
            distintos.append('familia %s' % k)
    inf.check(not distintos, '%d numeros (esfuerzos, desplazamientos, demandas y curvas P-M) identicos al '
              'anexo, bit a bit' % n_num, distintos[:5])
    obj = str(ar['objetivo'])
    d = next(c for c in ar['casos'] if c['nombre'] == ar['info']['caso_por_defecto'])['demandas'].get(obj)
    if d:
        print('         ej.: %s en %s: P = %.1f kN, M = %.1f kN m, Mn = %.1f kN m, u = %.3f, %s'
              % (obj, ar['info']['caso_por_defecto'], d['P'], d['M'], d['Mn'], d['u'], 'PASA' if d['pasa'] else 'NO PASA'))


# ============================================================
# [3] REGISTRO
# ============================================================
def bloque_pose(ar, modelo, inf):
    titulo('[3a] REGISTRO: la pose del marcador en el modelo')
    for nombre, pose in (('sitio', ar['marcador']), ('maqueta', ar['marcador']['maqueta'])):
        x, y, z = pose['ejes']['x'], pose['ejes']['y'], pose['ejes']['z']
        orto = max(abs(ex.punto(x, x) - 1), abs(ex.punto(y, y) - 1), abs(ex.punto(z, z) - 1),
                   abs(ex.punto(x, y)), abs(ex.punto(y, z)), abs(ex.punto(x, z)))
        cz = ex.cruz(x, y)
        mano = max(abs(cz[i] - z[i]) for i in range(3))
        inf.check(orto <= EPS and mano <= EPS, '%s: ejes ortonormales (%.1e) y derechos, x cruz y = z (%.1e)'
                  % (nombre, orto, mano))
    N = {n['id']: n for n in modelo['nodos']}
    E = {e['id']: e for e in modelo['elementos']}
    obj = E[ar['objetivo']]
    m = ar['marcador']
    if m['cara'] == 'abajo':
        return pose_en_viga(ar, m, obj, N, inf)
    if m['cara'] == 'foto':
        return pose_por_foto(ar, m, obj, N, inf)
    n1 = N[obj['n1']]
    d = ex.resta(m['centro'], [n1['x'], n1['y'], m['centro'][2]])
    dist_cara = ex.punto(d, m['ejes']['z'])
    lateral = math.hypot(*[d[i] - dist_cara * m['ejes']['z'][i] for i in range(3)])
    inf.check(abs(dist_cara - m['medio_ancho_columna_m']) <= 1e-6 and lateral <= 1e-6,
              'sitio: el centro de la imagen esta en la cara %s, a %.3f m del eje de la columna (medio ancho), '
              'centrado en la cara' % (m['cara'], dist_cara))
    z0 = min(N[obj['n1']]['z'], N[obj['n2']]['z'])
    inf.check(abs(m['centro'][2] - z0 - m['altura_centro_m']) <= 1e-6 and m['ejes']['y'] == [0.0, 0.0, 1.0],
              'sitio: centro a %.2f m sobre el nodo inferior (z = %.2f) y el arriba de la imagen es +z de OpenSees'
              % (m['altura_centro_m'], z0))
    mq = m['maqueta']
    inf.check(mq['centro'] == [n1['x'], n1['y'], z0] and mq['ejes']['z'] == [0.0, 0.0, 1.0],
              'maqueta: origen en la base de la columna y +z de OpenSees saliendo de la imagen')


def pose_en_viga(ar, m, obj, N, inf):
    """[3a] para una foto en el FONDO de una viga: se rehace desde la
    geometria del modelo, sin llamar a exportar_ar.pose_en_viga."""
    a, b = N[obj['n1']], N[obj['n2']]
    pa, pb = [a['x'], a['y'], a['z']], [b['x'], b['y'], b['z']]
    L = math.dist(pa, pb)
    u = [(pb[i] - pa[i]) / L for i in range(3)]
    c = m['centro']
    d = ex.resta(c, pa)
    lateral = math.hypot(d[0] - ex.punto(d, u) * u[0], d[1] - ex.punto(d, u) * u[1])
    inf.check(lateral <= 1e-6, 'sitio: el centro de la foto esta sobre el eje de la viga %d en planta '
              '(a %.1e m)' % (obj['id'], lateral))
    nc = m['nodo_cruce']
    E_ar = {e['id']: e for e in ar['elementos']}
    perp = E_ar.get(m['viga_perpendicular'])
    comparten = perp is not None and nc in (obj['n1'], obj['n2']) and nc in (perp['n1'], perp['n2'])
    s = math.hypot(c[0] - N[nc]['x'], c[1] - N[nc]['y'])
    inf.check(comparten and abs(s - m['distancia_al_nodo_m']) <= 1e-6 and 0 < s < L,
              'sitio: la foto esta a %.3f m del nodo %d, donde la viga %d se cruza con la %d (dentro de L = %.2f m)'
              % (s, nc, obj['id'], m['viga_perpendicular'], L))
    h = next(e['h'] for e in ar['elementos'] if e['id'] == obj['id'])
    inf.check(abs(c[2] - (a['z'] - h / 2.0)) <= 1e-6 and m['ejes']['z'] == [0.0, 0.0, -1.0],
              'sitio: en el fondo de la viga (z = %.2f = eje %.2f - h/2 %.2f) y la normal de la foto mira hacia abajo'
              % (c[2], a['z'], h / 2.0))
    y = m['ejes']['y']
    cuerpo = obj['id'] // 100000
    nivel = [n for t, n in N.items() if t // 100000 == cuerpo and abs(n['z'] - a['z']) < 1e-6]
    g = [sum(n['x'] for n in nivel) / len(nivel), sum(n['y'] for n in nivel) / len(nivel)]
    hacia = (g[0] - c[0]) * y[0] + (g[1] - c[1]) * y[1]
    esperado = {'interior': hacia > 0, 'exterior': hacia < 0}.get(m['arriba_de_la_imagen'], True)
    inf.check(abs(y[2]) <= EPS and abs(ex.punto(y, u)) <= EPS and esperado,
              'sitio: el arriba de la foto es horizontal, perpendicular a la viga y mira al %s'
              % m['arriba_de_la_imagen'])
    abajo = max(n['z'] for t, n in N.items() if t // 100000 == cuerpo and n['z'] < a['z'] - 1e-3)
    mq = m['maqueta']
    inf.check(mq['centro'] == [c[0], c[1], abajo] and mq['ejes']['z'] == [0.0, 0.0, 1.0],
              'maqueta: origen en el piso de abajo (z = %.2f), bajo la foto, y +z de OpenSees saliendo de ella' % abajo)


def pose_por_foto(ar, m, obj, N, inf):
    """[3a] para una foto en diagonal: se reproyecta cada punto medido con la
    camara que ajusto exportar_ar, con numpy aparte, y se mira la
    comprobacion que NO entro al ajuste."""
    import numpy as np
    with open(CONFIG, encoding='utf-8') as fh:
        foto = json.load(fh)['foto']
    cam = m['camara']
    C, f = np.array(cam['C']), cam['f_px']
    W, H = foto['tamano_px']
    # La rotacion, desde los ejes publicados: filas = derecha, abajo y adelante de la camara.
    R = np.array([m['ejes']['x'], [-v for v in m['ejes']['y']], [-v for v in m['ejes']['z']]])

    def px(X):
        Xc = R @ (np.array(X, float) - C)
        return np.array([f * Xc[0] / Xc[2] + W / 2, f * Xc[1] / Xc[2] + H / 2]), Xc[2]

    # Cota: los puntos se midieron a mano en la foto ampliada 4x (+-2 px por
    # coordenada, hasta 2.8 px en diagonal) y la focal es la nominal del
    # telefono, sin corregir distorsion del lente (~1 px en el centro de la foto).
    cota = 2 * math.hypot(2, 2) + 1
    peor = 0.0
    for p in foto['puntos']:
        q, z = px(p['m'])
        peor = max(peor, float(np.hypot(*(q - np.array(p['px'])))))
    for r in foto.get('rectas', []):
        a, b = np.array(r['px'][0], float), np.array(r['px'][1], float)
        n = np.array([-(b - a)[1], (b - a)[0]]) / np.linalg.norm(b - a)
        for X in r['m']:
            q, _ = px(X)
            peor = max(peor, abs(float((q - a) @ n)))
    inf.check(peor <= cota, 'foto: %d puntos y %d rectas reproyectados con la camara ajustada (peor %.1f px, cota %.1f px; '
              'error medio del ajuste %.1f px)' % (len(foto['puntos']), len(foto.get('rectas', [])), peor, cota, cam['rms_px']))
    hs = {e['id']: e['h'] for e in ar['elementos']}
    for p in [pp for pp in foto['puntos'] if 'nodo' in pp] + [foto['comprobacion']]:
        n = N[p['nodo']]
        ok = abs(p['m'][0] - n['x']) < 1e-9 and abs(p['m'][1] - n['y']) < 1e-9 and abs(p['m'][2] - (n['z'] - hs[obj['id']] / 2)) < 1e-9
        inf.check(ok, 'foto: el punto del nodo %d esta en sus x, y del modelo y en el fondo de la viga (z = %.2f)'
                  % (p['nodo'], p['m'][2]))
    c = foto['comprobacion']
    q, _ = px(c['m'])
    err = float(np.hypot(*(q - np.array(c['px']))))
    inf.check(err <= c['tolerancia_px'], 'foto: COMPROBACION que no entro al ajuste: el nodo %d cae en %s px, a %.1f px de la '
              'columna blanca %s (tolerancia %d px)' % (c['nodo'], np.round(q, 0).tolist(), err, c['px'], c['tolerancia_px']))
    _, zc = px(m['centro'])
    inf.check(abs(zc - cam['profundidad_m']) <= 1e-4 and abs(m['ancho_m'] - (foto['recorte'][2] - foto['recorte'][0]) * zc / f) <= 1e-4,
              'foto: la imagen es el plano de la foto a %.2f m (la profundidad de la X), de %.3f m de ancho' % (zc, m['ancho_m']))
    mq = m['maqueta']
    inf.check(mq['ejes']['z'] == [0.0, 0.0, 1.0], 'maqueta: +z de OpenSees saliendo de la foto acostada')


def bloque_giro(consola, inf):
    """[3c] El giroscopio (al perder la imagen): el signo de cada giro. Un
    error de convencion -- un eje cambiado, un angulo con el signo al
    reves -- haria que el modelo se mueva CON el telefono en vez de quedarse
    fijo, y en la pantalla solo se ve "raro"."""
    titulo('[3c] GIROSCOPIO: al girar el telefono, el modelo se queda fijo en el espacio')
    lineas = [l for l in consola if l.startswith('AR_GIRO ')]
    if not inf.check(bool(lineas), 'ar.js publico la prueba del giroscopio (AR_GIRO)'):
        return
    g = json.loads(lineas[-1][len('AR_GIRO '):])
    s, c = math.sin(math.radians(10)), math.cos(math.radians(10))
    cota = 1e-12                                   # ~10 operaciones en doble precision
    for nombre, esperado, que in (('base', [0, 0, -1], 'sin girar, el punto sigue al frente'),
                                  ('izquierda10', [s, 0, -c], 'girar 10 grados a la izquierda lo corre a la derecha'),
                                  ('arriba10', [0, -s, -c], 'levantar la camara 10 grados lo baja')):
        err = max(abs(g[nombre][i] - esperado[i]) for i in range(3))
        inf.check(err <= cota, '%s: %s (%s; error %.1e)' % (nombre, que, [round(v, 4) for v in g[nombre]], err))


def bloque_transformacion(ar, consola, inf):
    titulo('[3b] REGISTRO: la transformacion de ar.js (en Chrome) contra la de Python')
    lineas = [l for l in consola if l.startswith('AR_TRANSFORM ')]
    if not inf.check(bool(lineas), 'ar.js corrio y publico su transformacion (AR_TRANSFORM)'):
        return
    js = json.loads(lineas[-1][len('AR_TRANSFORM '):])
    for modo in ('sitio', 'maqueta'):
        pose = ar['marcador'] if modo == 'sitio' else ar['marcador']['maqueta']
        esc = ar['modos'][modo]['escala']
        peor, donde = 0.0, ''
        for n in ar['nodos']:
            py = ex.a_anchor([n['x'], n['y'], n['z']], dict(pose, ancho_m=ancho_de(ar, modo)), esc)
            j = js[modo]['puntos'][str(n['id'])]
            err = max(abs(py[i] - j[i]) for i in range(3))
            if err > peor:
                peor, donde = err, 'nodo %d' % n['id']
        # La cota: los dos hacen las mismas ~10 operaciones en doble
        # precision sobre coordenadas de hasta ~60 m / 0.2 m = 300 anchos.
        cota = 64 * EPS * 300
        inf.check(peor <= cota, '%s: %d nodos, Python = ar.js (peor %.1e anchos en %s, cota %.1e)'
                  % (modo, len(ar['nodos']), peor, donde or '-', cota))
        c = js[modo]['puntos']['centro_marcador']
        inf.check(max(abs(v) for v in c) <= cota, '%s: el centro de la pose cae en el origen del anchor %s'
                  % (modo, [round(v, 12) for v in c]))
    # Una lectura fisica: en sitio, la columna mide su alto en anchos.
    obj = next(e for e in ar['elementos'] if e['id'] == ar['objetivo'])
    a = js['sitio']['puntos'][str(obj['n1'])]
    b = js['sitio']['puntos'][str(obj['n2'])]
    alto = math.dist(a, b) * ar['marcador']['ancho_m']
    inf.check(abs(alto - obj['L']) <= 1e-9, 'sitio: el elemento mide %.3f m en el anchor x ancho, igual que en '
              'OpenSees (L = %.3f m): escala 1:1' % (alto, obj['L']))
    q = js['maqueta']['puntos']
    alto_m = math.dist(q[str(obj['n1'])], q[str(obj['n2'])]) * ancho_de(ar, 'maqueta')
    inf.check(abs(alto_m - obj['L'] * ar['modos']['maqueta']['escala']) <= 1e-9,
              'maqueta: el elemento mide %.1f cm sobre la mesa = %.2f m x %g' % (alto_m * 100, obj['L'],
                                                                              ar['modos']['maqueta']['escala']))


# ============================================================
# [4] IMAGE TRACKING con un video sintetico
# ============================================================
W_VIDEO, H_VIDEO = 640, 480
FOVY = math.radians(45.0)            # lo que supone MindAR (controller.js)


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def mat(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0]))] for i in range(len(a))]


def ancho_de(ar, modo):
    """Cada modo con SU imagen: la maqueta puede usar el marcador impreso
    (0.20 m) aunque en sitio la imagen sea una foto del lugar (ar.js anchoDe)."""
    pose = ar['marcador'] if modo == 'sitio' else ar['marcador']['maqueta']
    return pose.get('ancho_m') or ar['marcador']['ancho_m']


def generar_video(ruta, ancho_m, dist, incl_deg, giro_deg, cuadros=45, imagen=MARCADOR):
    """La imagen impresa vista desde una camara con la pose dada, con los
    intrinsecos de MindAR, escrita como video .y4m (lo que Chrome acepta
    como camara falsa). Devuelve la pose verdadera."""
    import numpy as np
    from PIL import Image
    src = np.asarray(Image.open(imagen).convert('RGB'), dtype=np.float32)
    H0, W0 = src.shape[:2]
    alto_m = ancho_m * H0 / W0
    f = (H_VIDEO / 2) / math.tan(FOVY / 2)
    K = np.array([[f, 0, W_VIDEO / 2], [0, f, H_VIDEO / 2], [0, 0, 1]])
    # Camara de frente (convencion OpenCV: x derecha, y abajo, z adelante):
    # x del marcador -> x, y (arriba) -> -y, z (hacia la camara) -> -z.
    R0 = [[1, 0, 0], [0, -1, 0], [0, 0, -1]]
    R = np.array(mat(R0, mat(rot_x(math.radians(incl_deg)), rot_z(math.radians(giro_deg)))))
    t = np.array([0.0, 0.0, dist])
    # pixel de la imagen (u, v) -> punto del marcador (X, Y, 0) en metros
    A = np.array([[ancho_m / W0, 0, -ancho_m / 2], [0, -alto_m / H0, alto_m / 2], [0, 0, 1]])
    Hm = K @ np.column_stack([R[:, 0], R[:, 1], t]) @ A
    Hinv = np.linalg.inv(Hm)
    uu, vv = np.meshgrid(np.arange(W_VIDEO), np.arange(H_VIDEO))
    p = Hinv @ np.stack([uu.ravel(), vv.ravel(), np.ones(uu.size)])
    us, vs = p[0] / p[2], p[1] / p[2]
    dentro = (us >= 0) & (us < W0 - 1) & (vs >= 0) & (vs < H0 - 1) & (p[2] > 0)
    rng = np.random.default_rng(7)
    fondo = (150 + 12 * rng.standard_normal((H_VIDEO * W_VIDEO, 3))).clip(0, 255)
    img = fondo.copy()
    u0, v0 = us[dentro].astype(int), vs[dentro].astype(int)
    du, dv = (us[dentro] - u0)[:, None], (vs[dentro] - v0)[:, None]
    img[dentro] = (src[v0, u0] * (1 - du) * (1 - dv) + src[v0, u0 + 1] * du * (1 - dv) +
                   src[v0 + 1, u0] * (1 - du) * dv + src[v0 + 1, u0 + 1] * du * dv)
    rgb = img.reshape(H_VIDEO, W_VIDEO, 3)
    y = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    cb = 128 - 0.168736 * rgb[..., 0] - 0.331264 * rgb[..., 1] + 0.5 * rgb[..., 2]
    cr = 128 + 0.5 * rgb[..., 0] - 0.418688 * rgb[..., 1] - 0.081312 * rgb[..., 2]
    sub = lambda c: c.reshape(H_VIDEO // 2, 2, W_VIDEO // 2, 2).mean(axis=(1, 3))
    planos = [y.clip(0, 255).astype(np.uint8), sub(cb).clip(0, 255).astype(np.uint8), sub(cr).clip(0, 255).astype(np.uint8)]
    with open(ruta, 'wb') as fh:
        fh.write(b'YUV4MPEG2 W%d H%d F30:1 Ip A1:1 C420jpeg\n' % (W_VIDEO, H_VIDEO))
        for _ in range(cuadros):
            fh.write(b'FRAME\n')
            for pl in planos:
                fh.write(pl.tobytes())
    ancho_px = f * ancho_m / dist
    return {'dist_m': dist, 'incl_deg': incl_deg, 'giro_deg': giro_deg, 'R': R.tolist(), 'ancho_px': ancho_px,
            'lado_corto_px': f * min(ancho_m, alto_m) / dist}


def bloque_tracking(ar, nav, inf):
    titulo('[4] IMAGE TRACKING: video sintetico con pose conocida -> la pose que estima la app')
    # Las distancias escalan con el ancho de la imagen, para que ocupe lo
    # mismo en el cuadro (~200-260 px) sea el marcador de 0.20 m o una foto
    # mas grande: las cotas de abajo salen de ese tamano en pixeles, y con
    # la imagen mas ancha que el cuadro no quedan esquinas que ubicar.
    # Se prueba CADA modo con SU imagen: la maqueta con el marcador impreso
    # y, si en sitio se usa una foto del lugar, en sitio con la foto.
    web = lambda nombre: os.path.join(AQUI, 'web', nombre)
    modos = [('maqueta', web(ar['marcador']['maqueta'].get('imagen', 'marcador.png')))]
    if ar['marcador'].get('imagen', 'marcador.png') != 'marcador.png':
        modos.append(('sitio', web(ar['marcador']['imagen'])))
    pruebas = []
    for modo, imagen in modos:
        k = ancho_de(ar, modo) / 0.20
        pruebas += [(modo, imagen, d * k, i, g) for d, i, g in ((0.45, 0.0, 0.0), (0.55, 30.0, 0.0), (0.60, 40.0, 20.0))]
    carpeta = tempfile.mkdtemp(prefix='ar_video_')
    try:
        for modo, imagen, dist, incl, giro in pruebas:
            video = os.path.join(carpeta, 'pose.y4m')
            verdad = generar_video(video, ancho_de(ar, modo), dist, incl, giro, imagen=imagen)
            consola = navegador(nav, 'index.html?prueba=1&iniciar=%s&datos=%s' % (modo, os.path.basename(AR)), 60, video=video, esperar='AR_POSE', minimo=6)
            poses_js = [json.loads(l[len('AR_POSE '):]) for l in consola if l.startswith('AR_POSE ')]
            etiqueta = '%s (%s), d = %.2f m, inclinacion %g, giro %g' % (modo, os.path.basename(imagen), dist, incl, giro)
            if not inf.check(len(poses_js) >= 3, '%s: la app DETECTA la imagen (%d poses publicadas)'
                             % (etiqueta, len(poses_js))):
                continue
            ult = poses_js[-3:]                              # ya sin el arranque del filtro
            d_est = sum(p['dist_m'] for p in ult) / len(ult)
            i_est = sum(p['giro_deg'] for p in ult) / len(ult)
            # Orientacion completa: los ejes del anchor en la camara de three.js
            # (x derecha, y ARRIBA, z HACIA ATRAS) contra los verdaderos (OpenCV).
            e = ult[-1]['m']
            eje = lambda c: [e[4 * c], e[4 * c + 1], e[4 * c + 2]]
            R = verdad['R']
            peor_ang = 0.0
            for c in range(3):
                v = eje(c)
                nv = math.sqrt(sum(a * a for a in v))
                ver = [R[0][c], -R[1][c], -R[2][c]]
                cosang = max(-1.0, min(1.0, sum(v[i] * ver[i] for i in range(3)) / nv))
                peor_ang = max(peor_ang, math.degrees(math.acos(cosang)))
            # Cotas desde el pixel: la imagen ocupa ancho_px en el cuadro y
            # MindAR ubica sus esquinas a ~1 px; eso mueve la distancia en
            # d * 1/ancho_px por lado y el angulo en atan(2/ancho_px) por
            # esquina. Se dejan 3 px de margen (esquinas en varias escalas).
            # El angulo lo fija el LADO CORTO: el giro en torno al eje largo
            # se lee en cuanto se corren las esquinas a lo largo del corto.
            # En el marcador impreso (1000 x 1010 px) es el ancho; en la foto
            # de la viga (960 x 514) es el alto, 138 px de 258.
            px = 3.0
            cota_d = dist * px / verdad['ancho_px']
            cota_a = math.degrees(math.atan(2 * px / verdad['lado_corto_px'])) * 2
            inf.check(abs(d_est - dist) <= cota_d,
                      '%s: distancia estimada %.3f m (verdad %.3f, error %.1f mm, cota %.1f mm; la imagen ocupa %.0f px)'
                      % (etiqueta, d_est, dist, abs(d_est - dist) * 1000, cota_d * 1000, verdad['ancho_px']))
            inf.check(abs(i_est - incl) <= cota_a and peor_ang <= cota_a,
                      '%s: inclinacion estimada %.1f deg (verdad %g) y los tres ejes a %.1f deg de los verdaderos '
                      '(cota %.1f deg)' % (etiqueta, i_est, incl, peor_ang, cota_a))
    finally:
        shutil.rmtree(carpeta, ignore_errors=True)


# ============================================================
# EL NAVEGADOR
# ============================================================
def buscar_navegador():
    return next((n for n in NAVEGADORES if os.path.exists(n)), None)


def navegador(nav, pagina, segundos, video=None, esperar=None, minimo=1):
    """Abre la pagina en Chrome sin ventana y devuelve lo que la app
    escribio en la consola (las lineas con prefijo AR_)."""
    perfil = tempfile.mkdtemp(prefix='ar_chrome_')
    log = os.path.join(perfil, 'consola.txt')
    args = [nav, '--headless=new', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
            '--autoplay-policy=no-user-gesture-required', '--enable-logging=stderr', '--v=0',
            '--user-data-dir=' + perfil]
    if video:
        args += ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
                 '--use-file-for-fake-video-capture=' + video]
    args.append('http://localhost:%d/%s' % (PUERTO, pagina))
    with open(log, 'wb') as fh:
        p = subprocess.Popen(args, stdout=fh, stderr=subprocess.STDOUT)
        t0 = time.time()
        while time.time() - t0 < segundos:
            time.sleep(2)
            if esperar:
                with open(log, 'rb') as g:
                    if g.read().decode('utf-8', 'replace').count(esperar) >= minimo:
                        break
        p.kill()
        p.wait()
    with open(log, 'rb') as g:
        texto = g.read().decode('utf-8', 'replace')
    shutil.rmtree(perfil, ignore_errors=True)
    lineas = []
    for m in re.finditer(r'CONSOLE:\d+\] "(.*?)", source:', texto):
        lineas.append(m.group(1))
    return lineas


# ============================================================
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--sin-navegador', action='store_true', help='solo los bloques [1], [2] y [3a]')
    ap.add_argument('--config', default=ex.CONFIG,
                    help='otro conjunto de datos, p. ej. semana06_lab/config_ar_viga_100164.json')
    args = ap.parse_args(argv)
    global AR, CONFIG
    CONFIG = os.path.abspath(args.config)
    AR = ex.salida_de(CONFIG)

    print('=' * 78)
    print('  LA APP DE AR, CRITERIO POR CRITERIO')
    print('=' * 78)
    with io.open(AR, encoding='utf-8') as fh:
        ar = json.load(fh)
    modelo = ex.cargar_modelo()
    anexo, de_donde = ex.cargar_anexo()
    print('  app       %s (%s, elemento %d, %d elementos)' % (os.path.relpath(AR, rutas.RAIZ), ar['info']['edificio'],
                                                           ar['objetivo'], len(ar['elementos'])))
    print('  anexo     %s' % de_donde)
    inf = Informe()
    bloque_ids(ar, modelo, anexo, inf)
    bloque_resultados(ar, anexo, inf)
    bloque_pose(ar, modelo, inf)

    if not args.sin_navegador:
        nav = buscar_navegador()
        if not inf.check(nav is not None, 'hay Chrome o Edge para correr ar.js'):
            pass
        else:
            srv = subprocess.Popen([sys.executable, os.path.join(AQUI, 'servir.py'), '--http', '--puerto', str(PUERTO)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                time.sleep(1.5)
                consola = navegador(nav, 'index.html?prueba=1&datos=' + os.path.basename(AR), 40, esperar='AR_TRANSFORM')
                errores = [l for l in consola if 'Uncaught' in l or 'Error' in l]
                inf.check(not errores, 'ar.js carga sin errores de JavaScript', errores[:3])
                bloque_transformacion(ar, consola, inf)
                bloque_giro(consola, inf)
                bloque_tracking(ar, nav, inf)
            finally:
                srv.kill()

    print()
    print('=' * 78)
    if inf.fallas:
        print('  NO CALZA (%d):' % len(inf.fallas))
        for f in inf.fallas:
            print('    - %s' % f)
        print('=' * 78)
        return 1
    if args.sin_navegador:
        print('  MISMO ELEMENTO Y MISMOS NUMEROS DE OPENSEES; POSE BIEN DEFINIDA (sin navegador: falta [3b] y [4])')
    else:
        print('  LA APP DE AR MUESTRA EL MISMO ELEMENTO Y LOS MISMOS NUMEROS DE OPENSEES, BIEN REGISTRADOS')
    print('=' * 78)
    return 0


if __name__ == '__main__':
    sys.exit(main())
