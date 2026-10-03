# -*- coding: utf-8 -*-
r"""
================================================================
 semana06/proyeccion_terreno.py
   EL MODELO DIBUJADO SOBRE LA FOTO REAL: LA VIGA 100164 EN TERRENO
================================================================
 La foto del cielo que se uso como imagen de referencia el 30-09
 (semana06_lab/marcador/foto_vigas_100352.jpg) muestra la viga 100164
 entre la X de cinta (nodo 100352) y la columna blanca (nodo 100359).

 exportar_ar.camara_de_la_foto ajusta desde donde se tomo la foto con
 3 puntos y 2 rectas del modelo (config_ar_viga_100164.json). Este
 script usa ESA camara para proyectar el modelo del conjunto sobre la
 foto y deja la imagen en evidencia/terreno/: si el registro es bueno,
 las vigas dibujadas caen sobre las reales. Ademas mide lo que NO entro
 al ajuste: donde cae el nodo 100359 contra la columna blanca.

 No es la app (la app usa MindAR y su propia camara): es la prueba de
 que la pose de la foto en el edificio, que es lo que la app usa como
 registro en sitio, calza con la estructura real.

   python semana06/proyeccion_terreno.py            # comprueba (asi corre en la suite)
   python semana06/proyeccion_terreno.py --salida   # + evidencia/terreno/proyeccion_viga_100164.{jpg,txt}
================================================================
"""
from __future__ import annotations

import io
import json
import math
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
LAB = os.path.join(RAIZ, 'semana06_lab')
sys.path.insert(0, os.path.join(RAIZ, 'comun'))
sys.path.insert(0, LAB)
import exportar_ar as ex                       # noqa: E402

CONFIG = os.path.join(LAB, 'config_ar_viga_100164.json')
DATOS = os.path.join(LAB, 'web', 'datos', 'ar_viga_100164.json')
SALIDA = os.path.join(AQUI, 'evidencia', 'terreno')
RADIO_DIBUJO = 9.0          # m en planta desde el centro de la viga: lo que entra en la foto


def main(argv=None):
    import numpy as np
    salida = '--salida' in (sys.argv[1:] if argv is None else argv)
    from PIL import Image, ImageDraw

    cfg = json.load(io.open(CONFIG, encoding='utf-8'))
    foto = cfg['foto']
    cam = ex.camara_de_la_foto(foto)
    proyectar, p = cam['proyectar'], cam['p']
    ar = json.load(io.open(DATOS, encoding='utf-8'))
    N = {n['id']: n for n in ar['nodos']}
    obj = next(e for e in ar['elementos'] if e['id'] == ar['objetivo'])
    cx = (N[obj['n1']]['x'] + N[obj['n2']]['x']) / 2
    cy = (N[obj['n1']]['y'] + N[obj['n2']]['y']) / 2

    im = Image.open(os.path.join(LAB, foto['archivo'])).convert('RGB')
    d = ImageDraw.Draw(im, 'RGBA')
    W, H = im.size

    def tramo(a, b, color, ancho=2):
        """Una arista 3D, partida en 40 trozos: se dibuja solo lo que esta
        delante de la camara y cerca de la foto."""
        pts = [np.array(a) + (np.array(b) - np.array(a)) * t for t in np.linspace(0, 1, 41)]
        uv, z = proyectar(p, pts)
        for i in range(40):
            if z[i] > 0.2 and z[i + 1] > 0.2 and all(-W < c < 2 * W for c in (uv[i][0], uv[i + 1][0])) \
                    and all(-H < c < 2 * H for c in (uv[i][1], uv[i + 1][1])):
                d.line([tuple(uv[i]), tuple(uv[i + 1])], fill=color, width=ancho)

    dibujadas = []
    for e in ar['elementos']:
        a, b = N[e['n1']], N[e['n2']]
        if min(math.hypot(n['x'] - cx, n['y'] - cy) for n in (a, b)) > RADIO_DIBUJO:
            continue
        A, B = np.array([a['x'], a['y'], a['z']]), np.array([b['x'], b['y'], b['z']])
        es_obj = e['id'] == obj['id']
        if e['tipo'].startswith('viga'):
            # el FONDO de la viga dibujada: eje - h/2, y +-b/2 a cada lado
            u = (B - A) / np.linalg.norm(B - A)
            lat = np.array([-u[1], u[0], 0.0]) * (e['b'] / 2)
            baja = np.array([0, 0, -e['h'] / 2])
            color = (255, 140, 30, 255) if es_obj else (80, 200, 255, 220)
            for s in (+1, -1):
                tramo(A + baja + s * lat, B + baja + s * lat, color, 4 if es_obj else 2)
            tramo(A + baja, B + baja, (color[0], color[1], color[2], 120), 1)
            dibujadas.append(e['id'])
            uv, z = proyectar(p, [(A + B) / 2 + baja])
            if z[0] > 0.2 and 0 <= uv[0][0] < W and 0 <= uv[0][1] < H:
                d.rectangle([uv[0][0] - 2, uv[0][1] - 9, uv[0][0] + 7 * len(str(e['id'])) + 4, uv[0][1] + 9],
                            fill=(0, 0, 0, 170))
                d.text((uv[0][0] + 2, uv[0][1] - 6), str(e['id']), fill=color)
        elif e['tipo'] in ('columna', 'pilar_metal', 'muro'):
            tramo(A, B, (120, 255, 140, 230), 3)
            dibujadas.append(e['id'])

    # lo que se midio en la foto (circulos) y la comprobacion que no entro al ajuste (cruz)
    for q in foto['puntos']:
        u, v = q['px']
        d.ellipse([u - 7, v - 7, u + 7, v + 7], outline=(255, 255, 0, 255), width=3)
    c = foto['comprobacion']
    uv, _ = proyectar(p, [c['m']])
    pu, pv = uv[0]
    err = math.hypot(pu - c['px'][0], pv - c['px'][1])
    d.line([pu - 10, pv - 10, pu + 10, pv + 10], fill=(255, 60, 60, 255), width=3)
    d.line([pu - 10, pv + 10, pu + 10, pv - 10], fill=(255, 60, 60, 255), width=3)
    d.rectangle([0, 0, W, 50], fill=(0, 0, 0, 170))
    d.text((8, 6), 'Modelo del conjunto proyectado con la camara de la foto (PnP, %d puntos + %d rectas, %.1f px RMS)'
           % (len(foto['puntos']), len(foto.get('rectas', [])), cam['rms_px']), fill=(255, 255, 255))
    d.text((8, 22), 'naranjo: viga %d (fondo); celeste: otras vigas; verde: columnas; amarillo: medidos; '
           'rojo: nodo %d (no entro al ajuste)' % (obj['id'], c['nodo']), fill=(255, 255, 255))

    img = os.path.join(SALIDA, 'proyeccion_viga_100164.jpg')
    if salida:
        os.makedirs(SALIDA, exist_ok=True)
        im.save(img, quality=90)

    R, C = cam['R'], cam['C']
    lineas = [
        'PROYECCION DEL MODELO SOBRE LA FOTO REAL (semana06/proyeccion_terreno.py)',
        'foto              %s (%d x %d px)' % (foto['archivo'], W, H),
        'focal             %.1f px (%g mm equivalentes, supuesto: camara 1x del iPhone)' % (cam['f'], foto['focal_mm_equivalente']),
        'camara ajustada   C = (%.3f, %.3f, %.3f) m, mira hacia (%.3f, %.3f, %.3f)' % (tuple(C) + tuple(R[2])),
        'ajuste            %d puntos + %d rectas, error medio %.2f px; residuos %s'
        % (len(foto['puntos']), len(foto.get('rectas', [])), cam['rms_px'], cam['residuos_px']),
        'COMPROBACION      nodo %d (no entro al ajuste) cae en (%.1f, %.1f) px; la columna blanca esta en %s: %.1f px'
        % (c['nodo'], pu, pv, c['px'], err),
        'a la profundidad de ese nodo, %.1f px son %.1f cm' % (err, 100 * err * float(np.linalg.norm(np.array(c['m']) - C)) / cam['f']),
        'elementos dibujados %d: %s' % (len(dibujadas), ', '.join(str(i) for i in sorted(dibujadas))),
        'imagen            %s' % os.path.relpath(img, RAIZ),
    ]
    if salida:
        with io.open(os.path.join(SALIDA, 'proyeccion_viga_100164.txt'), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('\n'.join(lineas) + '\n')
    print('\n'.join(lineas))
    ok = err <= c['tolerancia_px'] and cam['rms_px'] <= 3.0
    print('\n  %s' % ('LA VIGA DEL MODELO CAE SOBRE LA REAL (comprobacion dentro de %d px)' % c['tolerancia_px'] if ok
                      else 'NO CALZA'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
