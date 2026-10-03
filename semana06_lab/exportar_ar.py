# -*- coding: utf-8 -*-
r"""
================================================================
 semana06_lab/exportar_ar.py
   EL MODELO Y SUS RESULTADOS, PARA LA APP DE REALIDAD AUMENTADA
================================================================
 La regla de oro sigue igual: Python/OpenSees calcula, el JSON
 transporta y el telefono muestra. Este script es el ultimo paso de
 Python: toma el modelo del edificio (el conjunto: los dos cuerpos en un
 solo modelo) y el anexo con los resultados de OpenSees, se queda con el
 SECTOR alrededor del elemento donde se pega la imagen de referencia, y
 escribe semana06_lab/web/datos/ar.json.

 Lo que viaja, todo en coordenadas y unidades de OpenSees (m, kN):

   marcador   donde esta la imagen en el edificio: su centro y sus tres
              ejes (x a la derecha de la imagen, y hacia arriba, z
              saliendo de la columna hacia quien la mira), y su ancho
              impreso. Es la POSE del marcador en el modelo.
   nodos      x, y, z de OpenSees, con el MISMO tag del modelo.
   elementos  el sector, con el MISMO elementTag que OpenSees.
   casos      los 15 del anexo: desplazamientos de los nodos del sector,
              esfuerzos por estacion (N, Vy, Vz, T, My, Mz), y la
              demanda-capacidad de los que tienen fierro.
   familias   la curva P-M de cada seccion del sector con fierro.
   tributaria los poligonos del area tributaria de las vigas del sector.

 En el telefono no se resuelve nada: se transforma (OpenSees -> marcador
 -> anchor de AR) y se dibuja. La transformacion esta escrita en
 web/ar.js y comprobada contra la de aca por verificar_ar.py.

   python semana06_lab/exportar_ar.py                # usa config_ar.json
   python semana06_lab/exportar_ar.py --elemento 200069 --cara -y
================================================================
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import os
import sys
import time

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_AQUI), 'comun'))
import rutas                                   # noqa: E402

EDIFICIO = 'conjunto'
CONFIG = os.path.join(_AQUI, 'config_ar.json')
SALIDA = os.path.join(_AQUI, 'web', 'datos', 'ar.json')
MAGNITUDES = ('N', 'Vy', 'Vz', 'T', 'My', 'Mz')
CARAS = {'+x': (1.0, 0.0, 0.0), '-x': (-1.0, 0.0, 0.0), '+y': (0.0, 1.0, 0.0), '-y': (0.0, -1.0, 0.0)}
# Estos no son elementos del edificio sino recursos del modelo (brazos que
# unen el eje de un muro con sus caras). Se dejan fuera del dibujo.
NO_SE_DIBUJAN = ('brazo', 'brazo_rigido')
DEC = 6


# ============================================================
# ALGEBRA MINIMA (sin numpy: el mismo codigo que se lee en ar.js)
# ============================================================
def resta(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def punto(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cruz(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def unitario(a):
    n = math.sqrt(punto(a, a))
    return [a[0] / n, a[1] / n, a[2] / n]


def a_marcador(p, marcador):
    """Un punto de OpenSees (m) en el sistema de la imagen (m):
    q = R^T (p - c), con R = [ex ey ez] en columnas."""
    d = resta(p, marcador['centro'])
    return [punto(d, marcador['ejes']['x']), punto(d, marcador['ejes']['y']), punto(d, marcador['ejes']['z'])]


def a_anchor(p, marcador, escala):
    """Lo mismo, en unidades del anchor de MindAR: 1 unidad = el ancho
    impreso de la imagen. Es lo que hace ar.js (matrizModeloAAnchor)."""
    q = a_marcador(p, marcador)
    k = escala / marcador['ancho_m']
    return [q[0] * k, q[1] * k, q[2] * k]


# ============================================================
# ENTRADAS
# ============================================================
def cargar_modelo():
    with io.open(rutas.modelo(EDIFICIO), encoding='utf-8') as fh:
        return json.load(fh)


def cargar_anexo():
    """El anexo del conjunto. Si el de disco es de otro edificio (la suite
    deja el LT2), se arma en memoria con el mismo codigo que lo exporta."""
    ruta = os.path.join(rutas.UNITY, 'semana04.json')
    with io.open(ruta, encoding='utf-8') as fh:
        anexo = json.load(fh)
    en_disco = anexo['info']['edificio']
    if en_disco == EDIFICIO:
        return anexo, os.path.relpath(ruta, rutas.RAIZ)
    # semana03/ TAMBIEN tiene un exportar_unity.py: semana04/ tiene que ir
    # primero en la ruta, o se importa ese y no tiene construir_anexo.
    rutas.entrar(__file__, os.path.join(rutas.RAIZ, 'semana03'))
    s4 = os.path.join(rutas.RAIZ, 'semana04')
    if s4 in sys.path:
        sys.path.remove(s4)
    sys.path.insert(0, s4)
    sys.modules.pop('exportar_unity', None)
    import exportar_unity as eu                # noqa: E402
    with open(os.devnull, 'w') as dn, contextlib.redirect_stdout(dn):
        anexo, _ = eu.construir_anexo(EDIFICIO)
    return anexo, 'semana04/exportar_unity.construir_anexo(%r) en memoria (el de disco era %s)' % (
        EDIFICIO, en_disco)


def cargar_tributarias():
    ruta = rutas.unity(EDIFICIO)
    with io.open(ruta, encoding='utf-8') as fh:
        return json.load(fh).get('areas_tributarias', [])


# ============================================================
# EL MARCADOR EN EL MODELO
# ============================================================
def pose_del_marcador(elemento, nodos, anexo_elem, cfg):
    """Centro y ejes de la imagen pegada en una cara de la columna."""
    if elemento['tipo'] not in ('columna', 'pilar_metal'):
        raise SystemExit('el elemento %s es %s: la imagen va en una columna'
                         % (elemento['id'], elemento['tipo']))
    n1, n2 = nodos[elemento['n1']], nodos[elemento['n2']]
    if abs(n1['x'] - n2['x']) > 1e-6 or abs(n1['y'] - n2['y']) > 1e-6:
        raise SystemExit('la columna %s no es vertical' % elemento['id'])
    cara = cfg['cara']
    normal = list(CARAS[cara])
    # Medio ancho de la seccion en la direccion de la normal, con la misma
    # convencion con que ar.js dibuja la barra: h a lo largo del eje local
    # z y b del y (en una viga, h es el alto y z la vertical). En una
    # columna cuadrada da lo mismo.
    b, h = float(anexo_elem['b']), float(anexo_elem['h'])
    local_z = elemento.get('localZ') or [1.0, 0.0, 0.0]
    medio = (h if abs(punto(normal, local_z)) > 0.5 else b) / 2.0
    z_base = min(n1['z'], n2['z'])
    centro = [n1['x'] + normal[0] * medio, n1['y'] + normal[1] * medio, z_base + float(cfg['altura_centro_m'])]
    ez = normal                        # sale de la imagen hacia quien la mira
    ey = [0.0, 0.0, 1.0]               # arriba de la imagen = arriba del edificio
    ex = cruz(ey, ez)                  # derecha de la imagen: sistema derecho
    # MAQUETA: la misma imagen, acostada sobre una mesa. Ahi la normal de
    # la imagen es la vertical, asi que el arriba del edificio (+z de
    # OpenSees) tiene que salir de la imagen. El origen es la base de la
    # columna, para que el sector se pare sobre la imagen.
    base = [n1['x'], n1['y'], z_base]
    mz = [0.0, 0.0, 1.0]
    mx = ex                             # la derecha de la imagen, igual que en sitio
    my = cruz(mz, mx)
    maqueta = {'centro': [round(v, DEC) for v in base], 'ejes': {'x': mx, 'y': my, 'z': mz},
               '_por_que': ('Imagen acostada sobre la mesa: su normal (z) es la vertical del '
                            'edificio, x es la misma derecha que en sitio y y = z cruz x. El origen '
                            'es la base de la columna: el sector se para sobre la imagen.')}
    return {
        'elemento': elemento['id'],
        'cara': cara,
        'centro': [round(v, DEC) for v in centro],
        'ejes': {'x': ex, 'y': ey, 'z': ez},
        'maqueta': maqueta,
        'ancho_m': float(cfg['ancho_impreso_m']),
        'altura_centro_m': float(cfg['altura_centro_m']),
        'medio_ancho_columna_m': medio,
        '_por_que': ('Centro de la imagen = eje de la columna + medio ancho de la seccion en la '
                     'direccion de la cara + altura sobre el nodo inferior. Ejes: z = normal de la '
                     'cara (sale de la imagen), y = +z de OpenSees (arriba), x = y cruz z (sistema '
                     'derecho). Todo en coordenadas de OpenSees, metros.'),
    }


# conjunto/armar.py: el cuerpo i del conjunto lleva sus tags + (i+1)*100000,
# asi que tag // 100000 dice de que cuerpo es un nodo o una barra.
PASO_DE_TAG = 100000


def pose_en_viga(elemento, nodos, elems, anexo_elem, cfg):
    """Centro y ejes de una FOTO del fondo de una viga, tomada desde abajo.

    La imagen de referencia no tiene por que ser un marcador impreso: puede
    ser una foto de una parte del elemento con detalle (aca, el fondo de la
    viga con un access point). Se ubica con lo que se mide en terreno:

      - transversal: la foto se recorta justo a los dos bordes del fondo de
        la viga, asi que su centro cae en el eje de la viga y su ancho real
        sale del ancho de la viga (b) medido en pixeles;
      - a lo largo: la viga perpendicular con que se cruza y la distancia
        desde la CARA de esa viga al centro de la foto;
      - en altura: el fondo de la viga dibujada, eje - h/2 (ar.js dibuja la
        barra centrada en su eje, con h en la vertical);
      - giro: hacia donde queda el arriba de la foto ('interior' = hacia el
        centro del cuerpo en ese nivel, 'exterior', o una de CARAS).
    """
    if not str(elemento['tipo']).startswith('viga'):
        raise SystemExit('el elemento %s es %s: la cara "abajo" es de una viga'
                         % (elemento['id'], elemento['tipo']))
    n1, n2 = nodos[elemento['n1']], nodos[elemento['n2']]
    if abs(n1['z'] - n2['z']) > 1e-6:
        raise SystemExit('la viga %s no es horizontal' % elemento['id'])
    ref = cfg['referencia']
    perp = elems[int(ref['viga_perpendicular'])]
    comunes = {elemento['n1'], elemento['n2']} & {perp['n1'], perp['n2']}
    if len(comunes) != 1:
        raise SystemExit('las vigas %s y %s no se cruzan en un nodo' % (elemento['id'], perp['id']))
    nc = comunes.pop()
    otro = elemento['n2'] if nc == elemento['n1'] else elemento['n1']
    pc, po = nodos[nc], nodos[otro]
    p_c = [pc['x'], pc['y'], pc['z']]
    eje = unitario(resta([po['x'], po['y'], po['z']], p_c))     # desde el cruce, a lo largo de la viga
    b_perp = float(anexo_elem[perp['id']]['b'])
    h = float(anexo_elem[elemento['id']]['h'])
    s = b_perp / 2.0 + float(ref['distancia_desde_su_cara_m'])
    largo = math.dist(p_c, [po['x'], po['y'], po['z']])
    if not 0.0 < s < largo:
        raise SystemExit('la foto quedaria a %.2f m del nodo %d, fuera de la viga (L = %.2f m)' % (s, nc, largo))
    centro = [p_c[0] + eje[0] * s, p_c[1] + eje[1] * s, p_c[2] - h / 2.0]

    cuerpo = elemento['id'] // PASO_DE_TAG
    mismos = [n for t, n in nodos.items() if t // PASO_DE_TAG == cuerpo]
    en_nivel = [n for n in mismos if abs(n['z'] - p_c[2]) < 1e-6]
    g = [sum(n['x'] for n in en_nivel) / len(en_nivel), sum(n['y'] for n in en_nivel) / len(en_nivel), p_c[2]]
    lateral = [-eje[1], eje[0], 0.0]                            # horizontal, perpendicular a la viga
    arriba = cfg.get('arriba_de_la_imagen', 'interior')
    if arriba in ('interior', 'exterior'):
        hacia_g = punto(resta(g, centro), lateral)
        if abs(hacia_g) < 1e-6:
            raise SystemExit('el centro del cuerpo cae sobre la linea de la viga: diga +x, -x, +y o -y')
        ey = lateral if (hacia_g > 0) == (arriba == 'interior') else [-v for v in lateral]
    else:
        ey = list(CARAS[arriba])
        if abs(punto(ey, eje)) > 1e-6:
            raise SystemExit('el arriba de la foto (%s) tiene que ser perpendicular a la viga' % arriba)
    ez = [0.0, 0.0, -1.0]              # sale de la foto hacia abajo, hacia quien la mira
    ex = cruz(ey, ez)                  # derecha de la foto: sistema derecho

    # MAQUETA: la foto acostada sobre la mesa; el sector se para sobre ella
    # desde el piso de abajo, que es donde esta quien mira la viga.
    z_abajo = max(n['z'] for n in mismos if n['z'] < p_c[2] - 1e-3)
    base = [centro[0], centro[1], z_abajo]
    mz = [0.0, 0.0, 1.0]
    mx = ex
    my = cruz(mz, mx)
    maqueta = {'centro': [round(v, DEC) for v in base], 'ejes': {'x': mx, 'y': my, 'z': mz},
               '_por_que': ('Foto acostada sobre la mesa: su normal (z) es la vertical del edificio, '
                            'x es la misma derecha que en sitio y y = z cruz x. El origen es el punto '
                            'del piso de abajo bajo la foto: el sector se para sobre ella.')}
    return {
        'elemento': elemento['id'],
        'cara': 'abajo',
        'centro': [round(v, DEC) for v in centro],
        'ejes': {'x': ex, 'y': ey, 'z': ez},
        'maqueta': maqueta,
        'ancho_m': float(cfg['ancho_impreso_m']),
        'nodo_cruce': nc,
        'viga_perpendicular': perp['id'],
        'distancia_al_nodo_m': s,
        'medio_alto_viga_m': h / 2.0,
        'arriba_de_la_imagen': arriba,
        '_por_que': ('Centro de la foto = nodo del cruce con la viga %d + (medio ancho de esa viga + %.2f m) '
                     'a lo largo de la viga %d, en su fondo (eje - h/2). Ejes: z = abajo (sale de la foto '
                     'hacia quien la mira), y = el arriba de la foto (%s), x = y cruz z. OpenSees, metros.'
                     % (perp['id'], float(ref['distancia_desde_su_cara_m']), elemento['id'], arriba)),
    }


def camara_de_la_foto(foto):
    """Desde donde y hacia donde se tomo la foto (PnP), con puntos y rectas
    de la foto cuya posicion en el modelo se conoce.

    Camara de la foto (convencion OpenCV: x derecha, y ABAJO, z adelante),
    con la focal del telefono (35 mm equivalente sobre la diagonal) y el
    centro optico en el centro de la foto:
        u = f Xc/Zc + W/2,  v = f Yc/Zc + H/2,  Xc = R (X - C)
    Se ajustan R y C por minimos cuadrados (Levenberg-Marquardt): cada
    punto aporta su error en pixeles; cada recta, la distancia de dos de
    sus puntos 3D proyectados a la recta medida en la foto. La focal NO se
    ajusta: con puntos casi en un plano, distancia y zoom se compensan y el
    ajuste libre se va a un teleobjetivo lejano (medido: f = 6214 px a 14 m,
    bajo tierra). Devuelve R, C, f y los residuos."""
    import numpy as np
    W, H = foto['tamano_px']
    f = float(foto['focal_mm_equivalente']) / 43.27 * math.hypot(W, H)
    pts = [(p['px'], p['m']) for p in foto['puntos']]
    rectas = [(r['px'][0], r['px'][1], r['m']) for r in foto.get('rectas', [])]

    def rot(w):
        th = float(np.linalg.norm(w))
        if th < 1e-12:
            return np.eye(3)
        k = w / th
        K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
        return np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * K @ K

    def proyectar(p, X):
        Xc = (rot(p[:3]) @ (np.asarray(X, float) - p[3:6]).T).T
        return np.column_stack([f * Xc[:, 0] / Xc[:, 2] + W / 2, f * Xc[:, 1] / Xc[:, 2] + H / 2]), Xc[:, 2]

    def residuos(p):
        uv, z = proyectar(p, [m for _px, m in pts])
        r = (uv - np.array([px for px, _m in pts], float)).ravel().tolist()
        for a, b, ms in rectas:
            q, zq = proyectar(p, ms)
            a = np.array(a, float); d = np.array(b, float) - a
            n = np.array([-d[1], d[0]]) / np.linalg.norm(d)
            r += [float((qq - a) @ n) for qq in q]
            z = np.concatenate([z, zq])
        return np.array(r + [0.0 if zz > 0 else 1e3 for zz in z])     # todo delante de la camara

    def lm(p):
        lam = 1e-2
        for _ in range(500):
            r = residuos(p)
            J = np.zeros((len(r), 6))
            for i in range(6):
                dp = np.zeros(6); dp[i] = 1e-6 * max(1.0, abs(p[i]))
                J[:, i] = (residuos(p + dp) - r) / dp[i]
            A, g = J.T @ J, J.T @ r
            paso = np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-9), -g)
            if (residuos(p + paso) ** 2).sum() < (r ** 2).sum():
                p, lam = p + paso, lam * 0.3
                if np.linalg.norm(paso) < 1e-11:
                    break
            else:
                lam *= 10
        return p

    def desde_R(R):
        th = math.acos(max(-1.0, min(1.0, (np.trace(R) - 1) / 2)))
        if th < 1e-12:
            return np.zeros(3)
        return th / (2 * math.sin(th)) * np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])

    # Arranques: la camara 2 m bajo los puntos y 2.5 m al costado, en 8
    # direcciones, mirando a ellos con el arriba de la foto hacia arriba.
    centro = np.mean([m for _px, m in pts], axis=0)
    n_pts = 2 * len(pts) + 2 * len(rectas)
    mejor = None
    for k in range(8):
        a = 2 * math.pi * k / 8
        C = centro + np.array([2.5 * math.cos(a), 2.5 * math.sin(a), -2.0])
        fw = (centro - C) / np.linalg.norm(centro - C)
        rw = np.cross(fw, [0.0, 0.0, 1.0]); rw /= np.linalg.norm(rw)
        R0 = np.vstack([rw, np.cross(fw, rw), fw])
        p = lm(np.concatenate([desde_R(R0), C]))
        r = residuos(p)
        rms = math.sqrt(float((r[:n_pts] ** 2).mean()))
        if mejor is None or rms < mejor[0]:
            mejor = (rms, p, r[:n_pts])
    rms, p, r = mejor
    return {'R': rot(p[:3]), 'C': p[3:6], 'f': f, 'W': W, 'H': H, 'rms_px': rms,
            'residuos_px': [round(float(v), 2) for v in r], 'proyectar': proyectar, 'p': p}


def pose_por_foto(elemento, nodos, cfg):
    """La imagen de referencia es una FOTO CUALQUIERA del lugar, tomada en
    diagonal: no hace falta que sea de frente ni de una superficie plana
    conocida. MindAR la trata como un plano; ese plano es el de la foto
    misma (perpendicular a su eje optico), puesto a la profundidad del
    primer punto declarado, que es donde esta la estructura que importa.
    Visto desde cerca de donde se tomo, calza; al alejarse de ese punto
    aparece el paralaje de lo que no esta a esa profundidad."""
    import numpy as np
    foto = cfg['foto']
    cam = camara_de_la_foto(foto)
    R, C, f, W, H = cam['R'], cam['C'], cam['f'], cam['W'], cam['H']
    x0, y0, x1, y1 = foto['recorte']
    _uv, z = cam['proyectar'](cam['p'], [foto['puntos'][0]['m']])
    d = float(z[0])                                                    # profundidad del plano
    uc, vc = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    centro = C + d * (R.T @ np.array([(uc - W / 2) / f, (vc - H / 2) / f, 1.0]))
    ex = [float(v) for v in R.T @ np.array([1.0, 0.0, 0.0])]           # derecha de la foto
    ey = [float(v) for v in R.T @ np.array([0.0, -1.0, 0.0])]          # arriba de la foto
    ez = [float(v) for v in R.T @ np.array([0.0, 0.0, -1.0])]          # hacia quien la mira
    ancho = (x1 - x0) * d / f

    cuerpo = elemento['id'] // PASO_DE_TAG
    z_viga = nodos[elemento['n1']]['z']
    z_abajo = max(n['z'] for t, n in nodos.items() if t // PASO_DE_TAG == cuerpo and n['z'] < z_viga - 1e-3)
    a, b = nodos[elemento['n1']], nodos[elemento['n2']]
    base = [(a['x'] + b['x']) / 2.0, (a['y'] + b['y']) / 2.0, z_abajo]
    mx = [ex[0], ex[1], 0.0]
    nx = math.hypot(mx[0], mx[1]); mx = [mx[0] / nx, mx[1] / nx, 0.0]
    mz = [0.0, 0.0, 1.0]
    # La maqueta NO usa la foto: la foto mide 2.9 m en el cielo y sobre la
    # mesa no hay cielo. Usa el MARCADOR IMPRESO (indice 0 de targets.mind),
    # acostado en la mesa, con su ancho real.
    maqueta = {'centro': [round(v, DEC) for v in base], 'ejes': {'x': mx, 'y': cruz(mz, mx), 'z': mz},
               '_por_que': ('Marcador impreso acostado sobre la mesa: z es la vertical del edificio, x la derecha '
                            'de la foto del cielo llevada a la horizontal (el edificio queda orientado igual que '
                            'en sitio). El origen es el piso de abajo, bajo el centro del elemento: el sector se '
                            'para sobre el marcador.')}
    return {
        'elemento': elemento['id'],
        'cara': 'foto',
        'centro': [round(float(v), DEC) for v in centro],
        'ejes': {'x': ex, 'y': ey, 'z': ez},
        'maqueta': maqueta,
        'ancho_m': round(ancho, DEC),
        'camara': {'C': [round(float(v), 4) for v in C], 'f_px': round(f, 2), 'mira_hacia': [round(float(v), 4) for v in R[2]],
                   'profundidad_m': round(d, 4), 'rms_px': round(cam['rms_px'], 3), 'residuos_px': cam['residuos_px']},
        '_por_que': ('Pose de la camara de la foto por PnP con %d puntos y %d rectas del modelo (error medio %.1f px); '
                     'la imagen es el plano de la foto a %.2f m (la profundidad del primer punto), %.3f m de ancho. '
                     'Ejes: x derecha de la foto, y arriba, z hacia quien la mira. OpenSees, metros.'
                     % (len(foto['puntos']), len(foto.get('rectas', [])), cam['rms_px'], d, ancho)),
    }


def targets_de(cfg):
    """El archivo de imagenes que busca MindAR EN SITIO para este conjunto de
    datos. Cada modo busca UNA sola imagen: en sitio la foto del lugar, en la
    maqueta el marcador impreso (targets.mind). Con la foto del access point
    y el marcador en el mismo archivo, la foto dejaba de detectarse a 40
    grados + 20 de giro (verificar_ar.py [4], medido 3 veces; sola, si)."""
    return cfg.get('targets') or {'archivo': 'targets.mind', 'imagenes': ['marcador.png']}


def indice_de(archivo, cfg):
    nombres = targets_de(cfg)['imagenes']
    if archivo not in nombres:
        raise SystemExit('%s no esta en targets.imagenes del config: agregarla y compilar' % archivo)
    return nombres.index(archivo)


def recortar_foto(cfg):
    """web/<imagen_web> = el recorte declarado de la foto: lo que MindAR
    busca en sitio (su indice en targets.mind lo da web/imagenes.json)."""
    from PIL import Image
    foto = cfg['foto']
    im = Image.open(os.path.join(_AQUI, foto['archivo']))
    if list(im.size) != list(foto['tamano_px']):
        raise SystemExit('la foto mide %s px y config dice %s' % (im.size, foto['tamano_px']))
    destino = os.path.join(_AQUI, 'web', foto['imagen_web'])
    nuevo = im.convert('RGB').crop(tuple(foto['recorte']))
    antes = Image.open(destino).convert('RGB') if os.path.exists(destino) else None
    if antes is None or antes.size != nuevo.size or antes.tobytes() != nuevo.tobytes():
        nuevo.save(destino)
        print('  web/%s cambio: correr marcador/compilar_marcador.py para rehacer targets.mind' % foto['imagen_web'])


def imagenes_por_modo(pose, cfg):
    """Cada modo con SU imagen. En sitio, la foto del lugar si la hay; en la
    maqueta, el marcador impreso si 'maqueta_con' lo pide (una foto del cielo
    no se puede poner sobre una mesa con su tamano real)."""
    if 'foto' in cfg:
        pose['imagen'] = cfg['foto']['imagen_web']
        pose['targets'] = targets_de(cfg)['archivo']
        pose['indice'] = indice_de(cfg['foto']['imagen_web'], cfg)
    if 'maqueta_con' in cfg:
        maq = cfg['maqueta_con']
        pose['maqueta']['imagen'] = os.path.basename(maq['imagen'])
        pose['maqueta']['targets'] = maq['targets']
        pose['maqueta']['indice'] = 0
        pose['maqueta']['ancho_m'] = float(maq['ancho_m'])
    return pose


# ============================================================
# EL SECTOR
# ============================================================
def sector(modelo, objetivo, radio, marcador=None):
    """Las barras con algun extremo a menos de `radio` (en planta) y entre
    dos cotas. Columna: su eje y sus dos pisos. Viga: el punto donde esta
    la imagen, y del piso de abajo (donde se para quien la mira) a la viga."""
    nodos = {int(n['id']): n for n in modelo['nodos']}
    n1, n2 = nodos[objetivo['n1']], nodos[objetivo['n2']]
    z_abajo, z_arriba = min(n1['z'], n2['z']), max(n1['z'], n2['z'])
    cx, cy = n1['x'], n1['y']
    if marcador is not None and marcador['cara'] == 'abajo':
        cx, cy = marcador['centro'][0], marcador['centro'][1]
        z_abajo = marcador['maqueta']['centro'][2]
    if marcador is not None and marcador['cara'] == 'foto':
        cx, cy = marcador['maqueta']['centro'][0], marcador['maqueta']['centro'][1]
        z_abajo = marcador['maqueta']['centro'][2]
    tol = 1e-3
    elegidos = []
    for e in modelo['elementos']:
        if e['tipo'] in NO_SE_DIBUJAN:
            continue
        a, b = nodos[e['n1']], nodos[e['n2']]
        cerca = any(math.hypot(p['x'] - cx, p['y'] - cy) <= radio + tol for p in (a, b))
        dentro = (z_abajo - tol <= min(a['z'], b['z'])) and (max(a['z'], b['z']) <= z_arriba + tol)
        if cerca and dentro:
            elegidos.append(e)
    ids_nodos = sorted({e['n1'] for e in elegidos} | {e['n2'] for e in elegidos})
    return elegidos, ids_nodos


def salida_de(config):
    """config_ar.json -> web/datos/ar.json; config_ar_<x>.json -> web/datos/ar_<x>.json."""
    base = os.path.splitext(os.path.basename(config))[0]
    resto = base[len('config_ar'):] if base.startswith('config_ar') else '_' + base
    return os.path.join(_AQUI, 'web', 'datos', 'ar%s.json' % resto)


# ============================================================
def main(argv=None):
    ap = argparse.ArgumentParser(description='Exporta el sector y sus resultados para la app de AR')
    ap.add_argument('--elemento', type=int)
    ap.add_argument('--cara', choices=sorted(CARAS))
    ap.add_argument('--altura', type=float, help='altura del centro de la imagen sobre el nodo inferior (m)')
    ap.add_argument('--ancho', type=float, help='ancho impreso de la imagen (m)')
    ap.add_argument('--config', default=CONFIG,
                    help='otro conjunto de datos, p. ej. config_ar_viga_100164.json (sale en web/datos/ar_viga_100164.json)')
    ap.add_argument('--salida')
    args = ap.parse_args(argv)
    args.salida = args.salida or salida_de(args.config)

    with io.open(args.config, encoding='utf-8') as fh:
        cfg = json.load(fh)
    for k, v in (('elemento', args.elemento), ('cara', args.cara),
                 ('altura_centro_m', args.altura), ('ancho_impreso_m', args.ancho)):
        if v is not None:
            cfg[k] = v

    t0 = time.time()
    modelo = cargar_modelo()
    anexo, de_donde = cargar_anexo()
    nodos = {int(n['id']): n for n in modelo['nodos']}
    elems = {int(e['id']): e for e in modelo['elementos']}
    anexo_elem = {int(e['id']): e for e in anexo['elementos']}
    obj_id = int(cfg['elemento'])
    if obj_id not in elems:
        raise SystemExit('el elemento %d no existe en data/modelo/%s.json' % (obj_id, EDIFICIO))
    objetivo = elems[obj_id]
    if 'foto' in cfg:
        recortar_foto(cfg)
    if cfg.get('cara') == 'foto':
        marcador = pose_por_foto(objetivo, nodos, cfg)
    elif cfg.get('cara') == 'abajo':
        marcador = pose_en_viga(objetivo, nodos, elems, anexo_elem, cfg)
    else:
        marcador = pose_del_marcador(objetivo, nodos, anexo_elem[obj_id], cfg)
    marcador = imagenes_por_modo(marcador, cfg)
    elegidos, ids_nodos = sector(modelo, objetivo, float(cfg['radio_sector_m']), marcador)
    ids_elem = [e['id'] for e in elegidos]
    en_sector = set(ids_elem)

    # --- geometria, con los tags del modelo ---
    salida_nodos = [{'id': i, 'x': nodos[i]['x'], 'y': nodos[i]['y'], 'z': nodos[i]['z'],
                     'restricciones': nodos[i].get('restricciones')} for i in ids_nodos]
    salida_elem = []
    for e in elegidos:
        ae = anexo_elem.get(e['id'], {})
        salida_elem.append({
            'id': e['id'], 'tipo': e['tipo'], 'seccion': e['seccion'], 'n1': e['n1'], 'n2': e['n2'],
            'b': ae.get('b'), 'h': ae.get('h'), 'L': ae.get('L'),
            'localY': e.get('localY'), 'localZ': e.get('localZ'),
            'familia': ae.get('familia', -1),
            'momento_en_el_plano': ae.get('momento_en_el_plano', ''),
            'tag_opensees': ae.get('tag_opensees'),
            'area_tributaria_m2': e.get('area_tributaria'),
        })

    # --- resultados de OpenSees, caso por caso, solo del sector ---
    casos = []
    for c in anexo['casos']:
        desp = {str(d['id']): [d['ux'], d['uy'], d['uz'], d['rx'], d['ry'], d['rz']]
                for d in c['desplazamientos'] if d['id'] in set(ids_nodos)}
        esf = {}
        for s in c['esfuerzos']:
            if s['id'] in en_sector:
                esf[str(s['id'])] = {'x': s['x'], 'f': s['f'], 'w': s.get('w'),
                                     **{m: s[m] for m in MAGNITUDES}}
        dem = {str(d['id']): {k: d[k] for k in ('P', 'M', 'Mn', 'u', 'pasa', 'extremo')}
               for d in c['demandas'] if d['id'] in en_sector}
        casos.append({'nombre': c['nombre'], 'tipo': c.get('tipo'), 'descripcion': c.get('descripcion'),
                      'factores': c.get('factores'), 'desplazamientos': desp, 'esfuerzos': esf,
                      'demandas': dem})

    fams = sorted({e['familia'] for e in salida_elem if e['familia'] is not None and e['familia'] >= 0})
    familias = {str(k): {'clave': anexo['familias'][k]['clave'], 'P': anexo['familias'][k]['P'],
                         'Mn': anexo['familias'][k]['Mn'], 'refuerzo': anexo['familias'][k].get('refuerzo')}
                for k in fams}

    tributarias = [t for t in cargar_tributarias() if t['elemento'] in en_sector]

    # El diagrama que se ve al abrir: el momento que MAS trabaja en el
    # elemento de la imagen, en el caso por defecto. En las vigas de
    # Ingenieria la gravedad flecta en My (vecxz vertical) y en las del LT2
    # en Mz; con Mz fijo, la viga 100161 abria con el diagrama en cero.
    caso_def = cfg.get('caso_por_defecto') or anexo['info'].get('caso_por_defecto')
    c_def = next((c for c in casos if c['nombre'] == caso_def), casos[0])
    e_def = c_def['esfuerzos'].get(str(obj_id))
    magnitud_def = 'Mz'
    if e_def:
        magnitud_def = max(('Mz', 'My'), key=lambda m: max(abs(v) for v in e_def[m]))

    ar = {
        'info': {
            'edificio': EDIFICIO,
            'generado_por': 'semana06_lab/exportar_ar.py',
            'config': os.path.basename(args.config),
            'resultados_de': de_donde,
            'unidades': 'OpenSees: m, kN, kN*m, rad. Anchor de MindAR: 1 unidad = ancho impreso de la imagen',
            'regla_de_oro': 'Todo numero estructural de este archivo lo calculo OpenSees (anexo de la Semana 4). '
                            'El telefono solo transforma coordenadas y dibuja.',
            'ejes_opensees': 'x, y horizontales, z vertical hacia arriba; sistema derecho',
            'mapeo_unity': 'Unity(x, y, z) = OpenSees(x, z, y): y de Unity es la vertical. Cambiar y por z '
                           'invierte la mano: Unity es un sistema izquierdo (VisorEstructura.cs).',
            'mapeo_anchor': 'anchor = (escala / ancho_m) * R^T (p - centro), R = [ejes.x ejes.y ejes.z] del marcador',
            'escala_deformada': anexo['info'].get('escala_deformada'),
            'caso_por_defecto': cfg.get('caso_por_defecto') or anexo['info'].get('caso_por_defecto'),
            'modo_por_defecto': cfg.get('modo_por_defecto', 'maqueta'),
            'magnitud_por_defecto': magnitud_def,
            'radio_exportado': float(cfg['radio_sector_m']),
            'radio_por_defecto': float(cfg.get('radio_por_defecto', cfg['radio_sector_m'])),
        },
        'modos': cfg['modos'],
        'marcador': marcador,
        'objetivo': obj_id,
        'nodos': salida_nodos,
        'elementos': salida_elem,
        'familias': familias,
        'tributarias': tributarias,
        'casos': casos,
    }
    os.makedirs(os.path.dirname(args.salida), exist_ok=True)
    with io.open(args.salida, 'w', encoding='utf-8') as fh:
        json.dump(ar, fh, ensure_ascii=False, separators=(',', ':'))

    tam = os.path.getsize(args.salida)
    print('=' * 70)
    print('  AR: %s, elemento %d (%s, %s), cara %s' % (EDIFICIO, obj_id, objetivo['tipo'], objetivo['seccion'], marcador['cara']))
    print('=' * 70)
    print('  resultados de   %s' % de_donde)
    print('  marcador        centro %s m (OpenSees), ancho %.3f m' % (marcador['centro'], marcador['ancho_m']))
    print('                  ejes x %s  y %s  z %s' % (marcador['ejes']['x'], marcador['ejes']['y'], marcador['ejes']['z']))
    print('  sector          %d elementos, %d nodos, %d areas tributarias' % (len(salida_elem), len(salida_nodos), len(tributarias)))
    tipos = {}
    for e in salida_elem:
        tipos[e['tipo']] = tipos.get(e['tipo'], 0) + 1
    print('                  %s' % ', '.join('%s %d' % kv for kv in sorted(tipos.items())))
    print('  casos           %d; familias P-M %d' % (len(casos), len(familias)))
    print('  -> %s (%.0f KB, %.1f s)' % (os.path.relpath(args.salida, rutas.RAIZ), tam / 1024, time.time() - t0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
