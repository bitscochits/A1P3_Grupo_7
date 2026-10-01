# -*- coding: utf-8 -*-
r"""
================================================================
 semana06/precision_ar.py
   CUANTO SE EQUIVOCA EL REGISTRO DE LA AR: UNA ESTIMACION SIMPLE
================================================================
 La idea en tres lineas. Un error de angulo dtheta en la pose mueve un
 punto que esta a r del centro de la imagen en unos r * dtheta. Un
 error de escala eps (la distancia que estima MindAR, o el ancho
 impreso) lo mueve eps * r. Sobre eso se suma lo que corre la imagen
 entera (como se pego) y los sesgos (a que nivel esta el nodo).

 Todo se calcula con la MISMA transformacion que usa la app
 (exportar_ar.a_anchor, que verificar_ar.py [3b] compara con ar.js a
 2.8e-14): la matriz no aporta error, todo el error es fisico.

   [1] BRAZO        a que distancia del centro de la imagen esta cada nodo
   [2] FUENTES      cada fuente, exacta, perturbando la pose del marcador
   [3] PRESUPUESTO  suma cuadratica y peor caso, en sitio y en maqueta
   [4] FOCAL        lo que el ensayo [4] no puede ver: MindAR supone 45
                    grados de campo vertical, y el iPhone no es eso
   [5] PRUEBA       lo que hay que medir en el iPhone, con lo que debe dar

 El error del tracking NO se escribe aca: se lee de la salida de
 semana06_lab/verificar_ar.py [4] (video sintetico con pose conocida),
 guardada en semana06/evidencia/verificar_ar.txt.

   python semana06/precision_ar.py              # lee evidencia/verificar_ar.txt
   python semana06/precision_ar.py --medir      # corre verificar_ar.py y guarda su salida
   python semana06/precision_ar.py --fov 60     # otro campo de vision supuesto del iPhone
   python semana06/precision_ar.py --salida     # + evidencia/precision_ar.txt
================================================================
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import os
import re
import subprocess
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'comun'))
import rutas                                   # noqa: E402

LAB = os.path.join(rutas.RAIZ, 'semana06_lab')
sys.path.insert(0, LAB)
import exportar_ar as ex                       # noqa: E402

AR_JSON = os.path.join(LAB, 'web', 'datos', 'ar.json')
EVIDENCIA = os.path.join(AQUI, 'evidencia')
MEDICION = os.path.join(EVIDENCIA, 'verificar_ar.txt')

TECHO, BASE = 200103, 200062          # los nodos de la columna 200037
REGLA = (200064, 200078)              # nodos sobre la mesa para la prueba de la regla
ESCALA = {'sitio': 1.0, 'maqueta': 0.02}

# SUPUESTOS de este presupuesto (no son mediciones: la prueba [5] los mide)
IMPRESION = 0.01        # la impresora achica o agranda un 1 % (19.8 cm en vez de 20.0)
COLOCACION_M = 0.005    # la imagen pegada 5 mm corrida
COLOCACION_GRADOS = 1.0 # y girada 1 grado en su plano
SESGOS_M = (0.05, 0.10) # nivel del nodo contra el piso terminado: 5 a 10 cm
                        # (la cota -0.05 es un nivel de losa de 15 cm de
                        # espesor, lt2_2024_22.json; el piso terminado no
                        # esta en el modelo)

# La camara que supone MindAR (semana06_lab/web/vendor/mindar/
# controller-mGt1s8dJ.js:55189): h = 45 grados, f = (alto/2)/tan(h/2),
# fija, sea cual sea el telefono.
FOV_MINDAR = 45.0
# Donde se para quien mira en sitio para ver la columna entera.
DIST_SITIO = 1.5
# La pantalla del iPhone 16 (vertical): 1179 x 2556 px, 460 ppi.
PANTALLA = (1179, 2556)
PPI = 460.0


def ruta_rel(ruta):
    return os.path.relpath(ruta, rutas.RAIZ).replace(os.sep, '/')


def titulo(t):
    print()
    print(t)
    print('-' * min(len(t), 78))


def rot(eje, grados):
    """Rotacion de Rodrigues alrededor de un eje (no hace falta unitario)."""
    a = math.radians(grados)
    e = np.asarray(eje, float)
    e = e / np.linalg.norm(e)
    K = np.array([[0, -e[2], e[1]], [e[2], 0, -e[0]], [-e[1], e[0], 0]])
    return np.eye(3) + math.sin(a) * K + (1 - math.cos(a)) * K @ K


# ============================================================
# ENTRADAS
# ============================================================
def cargar():
    with io.open(AR_JSON, encoding='utf-8') as fh:
        ar = json.load(fh)
    m = ar['marcador']
    poses = {'sitio': {'centro': m['centro'], 'ejes': m['ejes'], 'ancho_m': m['ancho_m']},
             'maqueta': {'centro': m['maqueta']['centro'], 'ejes': m['maqueta']['ejes'],
                         'ancho_m': m['ancho_m']}}
    nodos = {int(n['id']): [n['x'], n['y'], n['z']] for n in ar['nodos']}
    return ar, poses, nodos


def dibujado(nodos, pose, modo):
    """Cada nodo en el sistema de la imagen, en METROS DEL DIBUJO: el
    anchor de MindAR (1 = el ancho impreso) por el ancho impreso."""
    return {i: np.array(ex.a_anchor(p, pose, ESCALA[modo])) * pose['ancho_m']
            for i, p in nodos.items()}


RE_DIST = re.compile(r'd = ([\d.]+) m.*distancia estimada ([\d.]+) m \(verdad ([\d.]+), '
                     r'error ([\d.]+) mm.*ocupa (\d+) px')
RE_EJES = re.compile(r'd = ([\d.]+) m.*los tres ejes a ([\d.]+) deg')


def tracking_medido():
    """El error de pose de verificar_ar.py [4], leido de su salida."""
    if not os.path.isfile(MEDICION):
        raise SystemExit('falta %s: correr  python semana06/precision_ar.py --medir'
                         % ruta_rel(MEDICION))
    with io.open(MEDICION, encoding='utf-8') as fh:
        texto = fh.read()
    if 'FALLA' in texto or 'IMAGE TRACKING' not in texto:
        raise SystemExit('%s no es una corrida completa y sana de verificar_ar.py'
                         % ruta_rel(MEDICION))
    dist = [(float(a), float(b), float(c), float(d), int(e)) for a, b, c, d, e in RE_DIST.findall(texto)]
    ejes = [float(b) for _a, b in RE_EJES.findall(texto)]
    if not dist or len(dist) != len(ejes):
        raise SystemExit('no se pudo leer el bloque [4] de %s' % MEDICION)
    return {'poses': dist, 'ejes': ejes,
            'grados': max(ejes),
            'escala': max(d[3] / 1000.0 / d[2] for d in dist),
            'px': (min(d[4] for d in dist), max(d[4] for d in dist))}


def medir():
    os.makedirs(EVIDENCIA, exist_ok=True)
    r = subprocess.run([sys.executable, os.path.join(LAB, 'verificar_ar.py')], cwd=rutas.RAIZ,
                       capture_output=True, text=True, encoding='utf-8', errors='replace',
                       timeout=900)
    with io.open(MEDICION, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(r.stdout)
    print('  verificar_ar.py: exit %d; salida en %s' % (r.returncode, ruta_rel(MEDICION)))
    if r.returncode != 0:
        raise SystemExit(r.stdout[-2000:] + r.stderr[-2000:])


# ============================================================
# [1] y [2]: brazo y fuentes, exactas
# ============================================================
def fuentes(q, modo, trk):
    r"""
    Corrimiento de un punto dibujado en q (m, sistema de la imagen) por
    cada fuente. Las de escala valen eps * |q|: si MindAR estima la
    distancia un eps de mas, dibuja el modelo como si fuera un eps mas
    chico alrededor del centro de la imagen (la proyeccion no cambia al
    escalar todo), y lo mismo pasa si la imagen impresa es un eps mas
    chica de lo declarado.
    """
    r = float(np.linalg.norm(q))
    angulo = max(float(np.linalg.norm(rot(e, trk['grados']) @ q - q))
                 for e in ((1, 0, 0), (0, 1, 0), (0, 0, 1)))
    f = [('tracking, angulo (%.1f grados)' % trk['grados'], angulo),
         ('tracking, distancia (%.2f %%)' % (100 * trk['escala']), trk['escala'] * r),
         ('impresion (%.0f %%, supuesto)' % (100 * IMPRESION), IMPRESION * r)]
    if modo == 'sitio':
        f += [('colocacion, corrimiento (%.0f mm, supuesto)' % (1000 * COLOCACION_M), COLOCACION_M),
              ('colocacion, giro (%.0f grado, supuesto)' % COLOCACION_GRADOS,
               float(np.linalg.norm(rot((0, 0, 1), COLOCACION_GRADOS) @ q - q)))]
    return f


def presupuesto(nodos, poses, trk, salida):
    unidad = {'sitio': (100.0, 'cm'), 'maqueta': (1000.0, 'mm')}
    res = {}
    for modo in ('sitio', 'maqueta'):
        q = dibujado(nodos, poses[modo], modo)
        lejos = max(q, key=lambda i: np.linalg.norm(q[i]))
        k, u = unidad[modo]
        titulo('[1] BRAZO, %s (escala %g): distancia al centro de la imagen, dibujada'
               % (modo.upper(), ESCALA[modo]))
        for i, que in ((BASE, 'base de la columna'), (TECHO, 'techo de la columna'),
                       (lejos, 'el mas lejano del sector')):
            print('  nodo %d (%s): q = (%s) m, |q| = %.4f m'
                  % (i, que, ', '.join('%.3f' % v for v in q[i]), np.linalg.norm(q[i])))

        titulo('[2] FUENTES y [3] PRESUPUESTO, %s (en %s)' % (modo.upper(), u))
        filas = {}
        for i in (TECHO, lejos):
            filas[i] = fuentes(q[i], modo, trk)
        print('  %-44s %12s %12s' % ('fuente', 'nodo %d' % TECHO, 'nodo %d' % lejos))
        for j, (nombre, _v) in enumerate(filas[TECHO]):
            print('  %-44s %12.2f %12.2f' % (nombre, k * filas[TECHO][j][1], k * filas[lejos][j][1]))
        out = {}
        for i in (TECHO, lejos):
            v = [x for _n, x in filas[i]]
            rss, peor = math.sqrt(sum(x * x for x in v)), sum(v)
            out[i] = {'rss': rss, 'peor': peor, 'r': float(np.linalg.norm(q[i]))}
        print('  %-44s %12.2f %12.2f' % ('suma cuadratica (RSS)', k * out[TECHO]['rss'], k * out[lejos]['rss']))
        print('  %-44s %12.2f %12.2f' % ('peor caso (suma directa)', k * out[TECHO]['peor'], k * out[lejos]['peor']))
        if modo == 'sitio':
            # EXTRAPOLACION, no medicion: en el ensayo la camara estaba a
            # 0.45-0.60 m; en sitio, a DIST_SITIO. Con la misma camara la
            # imagen se ve d_ensayo / DIST_SITIO veces mas chica, y el error
            # de angulo de un ajuste de pose crece como 1 / (tamano en px).
            extra = max(g * DIST_SITIO / d for (d, *_r), g in zip(trk['poses'], trk['ejes']))
            menor = min(g * DIST_SITIO / d for (d, *_r), g in zip(trk['poses'], trk['ejes']))
            print('  %-44s %12s %12s' % ('EXTRAPOLADO a %.1f m (no medido): angulo' % DIST_SITIO,
                                         '%.1f-%.1f' % (k * out[TECHO]['r'] * math.radians(menor),
                                                        k * out[TECHO]['r'] * math.radians(extra)),
                                         '%.1f-%.1f' % (k * out[lejos]['r'] * math.radians(menor),
                                                        k * out[lejos]['r'] * math.radians(extra))))
            print('  %-44s %12s' % ('  (%.1f a %.1f grados en vez de %.1f)' % (menor, extra, trk['grados']), ''))
            for s in SESGOS_M:
                print('  %-44s %12.2f %12.2f'
                      % ('RSS con sesgo de nivel de %.0f cm' % (100 * s),
                         k * math.hypot(out[TECHO]['rss'], s), k * math.hypot(out[lejos]['rss'], s)))
                print('  %-44s %12.2f %12.2f'
                      % ('peor caso con sesgo de %.0f cm' % (100 * s),
                         k * (out[TECHO]['peor'] + s), k * (out[lejos]['peor'] + s)))
        res[modo] = {'q': q, 'lejos': lejos, 'out': out}
    return res


# ============================================================
# [4] FOCAL: una camara de verdad contra la que supone MindAR
# ============================================================
def proyectar(f, X):
    W, H = PANTALLA
    u = np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1.0]]) @ X
    return u[:2] / u[2]


def escenario(modo, dist, grados):
    """(R, t): del sistema de la imagen (m) a la camara (x derecha, y
    abajo, z adelante), para una camara a 'dist' del centro de la imagen."""
    if modo == 'sitio':
        # de frente a la cara de la columna, a la altura del centro de la
        # imagen, levantada 'grados' para ver el techo
        C = np.array([0.0, 0.0, dist])
        zc = np.array([0.0, math.sin(math.radians(grados)), -math.cos(math.radians(grados))])
        xc = np.array([1.0, 0.0, 0.0])
    else:
        # la imagen en la mesa, mirada desde arriba con 'grados' de elevacion
        el = math.radians(grados)
        C = np.array([0.0, -dist * math.cos(el), dist * math.sin(el)])
        zc = np.array([0.0, 0.0, 0.04]) - C
        zc /= np.linalg.norm(zc)
        xc = np.cross(zc, [0.0, 0.0, 1.0])
        xc /= np.linalg.norm(xc)
    yc = np.cross(zc, xc)
    R = np.vstack([xc, yc, zc])
    return R, -R @ C


def rejilla(ancho, n=9):
    """Puntos de la imagen impresa (marcador.png: 1000 x 1010 px)."""
    alto = ancho * 1010.0 / 1000.0
    return [np.array([x, y, 0.0]) for x in np.linspace(-ancho / 2, ancho / 2, n)
            for y in np.linspace(-alto / 2, alto / 2, n)]


def ajustar_pose(f, uv, Q, R0, t0, iteraciones=80):
    r"""
    La pose que minimiza la reproyeccion de los puntos de la imagen con
    la focal f: es lo que hace MindAR con SU focal. Gauss-Newton con
    jacobiano numerico, arrancando de la pose verdadera.
    """
    def residuo(x):
        R = (rot(x[:3], math.degrees(np.linalg.norm(x[:3])))
             if np.linalg.norm(x[:3]) > 1e-15 else np.eye(3)) @ R0
        return np.concatenate([proyectar(f, R @ q + t0 + x[3:]) - u for q, u in zip(Q, uv)]), R

    x = np.zeros(6)
    for _ in range(iteraciones):
        r, _R = residuo(x)
        J = np.zeros((r.size, 6))
        for k in range(6):
            dx = np.zeros(6)
            dx[k] = 1e-7
            J[:, k] = (residuo(x + dx)[0] - r) / 1e-7
        paso = np.linalg.lstsq(J, -r, rcond=None)[0]
        x = x + paso
        if np.linalg.norm(paso) < 1e-13:
            break
    r, R = residuo(x)
    return R, t0 + x[3:], float(np.sqrt(np.mean(r ** 2)))


def error_focal(q, ancho, R, t, f_real, razon):
    """px de pantalla entre donde esta cada punto y donde lo dibuja una
    app que cree que la focal es razon * f_real."""
    Q = rejilla(ancho)
    uv = [proyectar(f_real, R @ p + t) for p in Q]
    Ra, ta, rms = ajustar_pose(f_real * razon, uv, Q, R, t * razon)
    W, H = PANTALLA
    err = {}
    for i, p in q.items():
        Xc = R @ p + t
        if Xc[2] <= 0.05:
            continue
        verdad = proyectar(f_real, Xc)
        if 0 <= verdad[0] <= W and 0 <= verdad[1] <= H:
            err[i] = float(np.linalg.norm(proyectar(f_real * razon, Ra @ p + ta) - verdad))
    return err, float(np.linalg.norm(ta) / np.linalg.norm(t)), rms


def control_focal(f_real, razon):
    r"""
    La simulacion contra la formula cerrada, de frente: un punto a X en
    el plano de la imagen y n detras de el, con la camara a d. La app
    estima la distancia como razon * d y dibuja el punto en
    f X / (d + n / razon); de verdad esta en f X / (d + n).
    """
    d, X, n = 1.5, 0.30, 0.35
    R = np.array([[1.0, 0, 0], [0, -1.0, 0], [0, 0, -1.0]])
    t = np.array([0.0, 0.0, d])
    err, _dist, _rms = error_focal({1: np.array([0.0, X, -n])}, 0.20, R, t, f_real, razon)
    formula = f_real * X * abs(1.0 / (d + n / razon) - 1.0 / (d + n))
    return err[1], formula


def focal(res, poses, fov):
    titulo('[4] FOCAL: MindAR supone %.0f grados de campo vertical; el iPhone, %.0f en el '
           'lado largo (SUPUESTO)' % (FOV_MINDAR, fov))
    W, H = PANTALLA
    f_real = (H / 2) / math.tan(math.radians(fov / 2))
    corto = 2 * math.degrees(math.atan(math.tan(math.radians(fov / 2)) * W / H))
    # El alto del video es el lado largo si el video viene vertical, o el
    # corto (4:3) si viene apaisado: MindAR pone sus 45 grados en el alto.
    fov_43 = 2 * math.degrees(math.atan(math.tan(math.radians(fov / 2)) * 0.75))
    razones = [('video apaisado (alto = lado corto, %.1f grados)' % fov_43,
                math.tan(math.radians(fov_43 / 2)) / math.tan(math.radians(FOV_MINDAR / 2))),
               ('video vertical (alto = lado largo, %.0f grados)' % fov,
                math.tan(math.radians(fov / 2)) / math.tan(math.radians(FOV_MINDAR / 2)))]
    print('  pantalla %d x %d px, %.0f ppi: f = %.1f px; el lado corto ve %.1f grados'
          % (W, H, PPI, f_real, corto))
    ok = []
    s, formula = control_focal(f_real, razones[0][1])
    ok.append(abs(s - formula) <= 1e-6 * max(formula, 1.0))
    print('  [%s] control: de frente, simulacion %.3f px = formula cerrada %.3f px'
          % ('OK  ' if ok[-1] else 'FALLA', s, formula))
    salida = {}
    for modo, dist, grados in (('sitio', DIST_SITIO, 25.0), ('maqueta', 0.5, 45.0)):
        q = res[modo]['q']
        R, t = escenario(modo, dist, grados)
        print('  %s: camara a %.2f m del centro de la imagen, %g grados' % (modo, dist, grados))
        for nombre, razon in razones:
            err, dist_app, rms = error_focal(q, poses[modo]['ancho_m'], R, t, f_real, razon)
            peor = max(err, key=err.get)
            techo = ('%.1f px' % err[TECHO]) if TECHO in err else 'fuera de cuadro'
            print('    f_MindAR / f_real = %.3f, %s:' % (razon, nombre))
            print('      techo %d: %s; peor visible %.1f px (nodo %d) = %.1f mm de pantalla; '
                  'la app dice %.3f veces la distancia real (ajuste rms %.2f px)'
                  % (TECHO, techo, err[peor], peor, err[peor] * 25.4 / PPI, dist_app, rms))
            salida.setdefault(modo, []).append((razon, err.get(TECHO), err[peor], peor, dist_app))
    return all(ok), salida


# ============================================================
# [5] LA PRUEBA EN EL TELEFONO
# ============================================================
def prueba(res, razones_focal):
    titulo('[5] PRUEBA EN EL iPHONE: lo que hay que medir y lo que tiene que dar')
    qm = res['maqueta']['q']
    print('  a) FOCAL, con una cinta: el telefono de frente a la imagen a 30, 50 y 80 cm; la barra')
    print('     "pose:" tiene que decir lo mismo que la cinta. Si dice %s veces lo medido, la'
          % ' o '.join('%.2f' % r for r in razones_focal))
    print('     fila [4] se confirma y esa razon es la correccion.')
    print('  b) TEMBLOR: el telefono apoyado 10 s, grabando la pantalla; la dispersion de "pose:".')
    print('  c) MAQUETA, con una regla, desde el centro de la imagen (en el plano de la mesa):')
    for i in REGLA:
        if i in qm:
            print('     nodo %d: x = %.1f cm, y = %.1f cm (z = %.2f cm: sobre la mesa, sin paralaje)'
                  % (i, 100 * qm[i][0], 100 * qm[i][1], 100 * qm[i][2]))
    print('     y con una regla VERTICAL (la unica que ve la focal): el techo %d a %.2f cm de la mesa.'
          % (TECHO, 100 * qm[TECHO][2]))
    qs = res['sitio']['q']
    print('  d) SITIO: confirmar primero en obra cual es la columna (ver reports/semana06.md, punto 3);')
    print('     cinta en las dos aristas de la cara +x a 0.5, 1.0 y 2.0 m sobre el centro de la imagen;')
    print('     la caja dibujada (0.70 m) tiene que calzar con ellas. La base dibujada esta %.2f m bajo'
          % -qs[BASE][1])
    print('     el centro de la imagen: la distancia entre esa base y el piso real es el sesgo de nivel.')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--medir', action='store_true', help='corre verificar_ar.py y guarda su salida')
    ap.add_argument('--fov', type=float, default=70.0,
                    help='campo de vision del iPhone en el lado largo, en grados (supuesto)')
    ap.add_argument('--salida', action='store_true', help='escribe evidencia/precision_ar.txt')
    a = ap.parse_args(argv)

    if a.medir:
        medir()
    buf = io.StringIO()
    with contextlib.redirect_stdout(Tee(sys.stdout, buf) if a.salida else sys.stdout):
        ok = correr(a.fov)
    if a.salida:
        os.makedirs(EVIDENCIA, exist_ok=True)
        ruta = os.path.join(EVIDENCIA, 'precision_ar.txt')
        with io.open(ruta, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(buf.getvalue())
        print('  escrito %s' % ruta_rel(ruta))
    return 0 if ok else 1


class Tee(object):
    def __init__(self, *destinos):
        self.destinos = destinos

    def write(self, s):
        for d in self.destinos:
            d.write(s)

    def flush(self):
        for d in self.destinos:
            d.flush()


def correr(fov):
    print('=' * 78)
    print('  SEMANA 6: PRECISION DEL REGISTRO DE LA AR (estimacion simple)')
    print('=' * 78)
    ar, poses, nodos = cargar()
    trk = tracking_medido()
    print('  app       %s (%s, elemento %d, %d nodos)'
          % (ruta_rel(AR_JSON), ar['info']['edificio'], ar['marcador']['elemento'],
             len(nodos)))
    print('  tracking  %s, bloque [4]: VIDEO SINTETICO con la camara que supone MindAR,'
          % ruta_rel(MEDICION))
    for (d, est, verdad, e_mm, px), grados in zip(trk['poses'], trk['ejes']):
        print('            a %.2f m: distancia %.3f m (error %.1f mm), ejes a %.1f grados, imagen de %d px'
              % (d, est, e_mm, grados, px))
    print('            -> se usa el peor: %.1f grados y %.2f %% de la distancia'
          % (trk['grados'], 100 * trk['escala']))
    res = presupuesto(nodos, poses, trk, None)
    ok, focales = focal(res, poses, fov)
    prueba(res, [x[0] for x in focales['sitio']])
    print()
    print('=' * 78)
    s, m = res['sitio']['out'], res['maqueta']['out']
    print('  SITIO:   techo de la columna %.1f cm RSS (%.1f cm con 5 cm de sesgo de nivel); nodo %d a %.1f m: %.1f cm'
          % (100 * s[TECHO]['rss'], 100 * math.hypot(s[TECHO]['rss'], SESGOS_M[0]),
             res['sitio']['lejos'], s[res['sitio']['lejos']]['r'], 100 * s[res['sitio']['lejos']]['rss']))
    print('  MAQUETA: techo de la columna %.1f mm RSS; nodo %d a %.1f cm: %.1f mm'
          % (1000 * m[TECHO]['rss'], res['maqueta']['lejos'], 100 * m[res['maqueta']['lejos']]['r'],
             1000 * m[res['maqueta']['lejos']]['rss']))
    print('  SIN la focal [4] y SIN confirmar la columna en obra. Nada de esto se midio en un iPhone.')
    print('=' * 78)
    return ok


if __name__ == '__main__':
    sys.exit(main())
