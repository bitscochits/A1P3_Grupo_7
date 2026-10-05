# -*- coding: utf-8 -*-
r"""
================================================================
 comun/recursos_realistas.py  -  LAS TEXTURAS Y EL CIELO DE LA VISTA REALISTA
================================================================
 La vista realista del visor usa recursos descargados (CC0) que viven en
 unity/Assets/Resources/Ambiente/ (los arma, en el editor,
 unity/Assets/Editor/RecursosRealistas.cs; los usa
 AmbienteVisor.Recursos.cs). Este script hace lo que no se ve a simple
 vista y falla en silencio:

   [1] EL SOL DEL CIELO. El HDRI trae su sol en algun lugar del
       panorama, y la luz direccional de la vista realista esta en otro
       (AmbienteVisor.SOL_REALISTA). Sin girar el cielo, las sombras van
       para un lado y el sol se ve en otro. Se lee el .hdr (Radiance
       RGBE), se busca el pixel mas brillante, y se calcula el giro del
       Skybox/Panoramic que lo pone en el rumbo de la luz. Queda en
       Texturas/cielo/sol.json, que lee RecursosRealistas.cs.
   [2] LAS LICENCIAS. Cada recurso tiene su FUENTE.txt y dice CC0.
   [3] LOS MAPAS NORMALES importados como NormalMap (textureType 1 en el
       .meta). Importado como imagen comun, el relieve sale al reves y
       nadie lo nota.
   [4] LOS MATERIALES apuntan a esas texturas (por GUID) y el del
       hormigon tiene el keyword _NORMALMAP; el cielo tiene el giro de
       sol.json.

 Correr:
   python comun/recursos_realistas.py              escribe sol.json y verifica
   python comun/recursos_realistas.py --verificar  solo verifica (la suite)
================================================================
"""
from __future__ import annotations

import io
import json
import math
import os
import re
import sys

import numpy as np

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _AQUI)
import rutas                                 # noqa: E402

AMBIENTE = os.path.join(rutas.UNITY_PROYECTO, 'Assets', 'Resources', 'Ambiente')
TEXTURAS = os.path.join(AMBIENTE, 'Texturas')
CS_AMBIENTE = os.path.join(rutas.UNITY_PROYECTO, 'Assets', 'Scripts', 'AmbienteVisor.cs')
ITEMS = ('hormigon_visto', 'hormigon_losa', 'pasto', 'tierra', 'acero')
# Tolerancia del giro: el sol del HDRI es un disco de unos 0.5 grados y
# se toma el pixel mas brillante de un panorama de 2048 px de ancho
# (0.18 grados por pixel); el material guarda el giro como float.
TOL_GIRO_GRADOS = 0.5


# ============================================================
# EL HDR
# ============================================================
def leer_hdr(ruta):
    """Radiance .hdr (RGBE, con o sin RLE) -> array (alto, ancho, 3) float32."""
    with io.open(ruta, 'rb') as f:
        datos = f.read()
    i = 0
    while True:                                   # cabecera hasta la linea vacia
        j = datos.index(b'\n', i)
        linea = datos[i:j]
        i = j + 1
        if linea.strip() == b'':
            break
    j = datos.index(b'\n', i)
    m = re.match(rb'-Y (\d+) \+X (\d+)', datos[i:j])
    if not m:
        raise ValueError('orientacion no soportada: %r' % datos[i:j])
    alto, ancho = int(m.group(1)), int(m.group(2))
    i = j + 1
    img = np.zeros((alto, ancho, 4), dtype=np.uint8)
    buf = memoryview(datos)
    for y in range(alto):
        if ancho >= 8 and buf[i] == 2 and buf[i + 1] == 2 and (buf[i + 2] << 8 | buf[i + 3]) == ancho:
            i += 4
            for c in range(4):                    # RLE nuevo: canal por canal
                x = 0
                while x < ancho:
                    n = buf[i]
                    i += 1
                    if n > 128:
                        n -= 128
                        img[y, x:x + n, c] = buf[i]
                        i += 1
                    else:
                        img[y, x:x + n, c] = np.frombuffer(buf[i:i + n], dtype=np.uint8)
                        i += n
                    x += n
        else:                                     # sin RLE
            img[y] = np.frombuffer(buf[i:i + 4 * ancho], dtype=np.uint8).reshape(ancho, 4)
            i += 4 * ancho
    e = img[:, :, 3].astype(np.int32)
    f = np.where(e > 0, np.ldexp(1.0, e - 136), 0.0).astype(np.float32)
    return img[:, :, :3].astype(np.float32) * f[:, :, None]


def sol_del_hdri(img):
    """(fila, columna, phi' en grados, elevacion en grados) del pixel mas
    brillante. phi' es el angulo con que Skybox/Panoramic muestrea ese
    pixel: u = 0.5 - atan2(z, x) / 2pi (ToRadialCoords de Unity)."""
    lum = 0.2126 * img[:, :, 0] + 0.7152 * img[:, :, 1] + 0.0722 * img[:, :, 2]
    fila, col = np.unravel_index(int(np.argmax(lum)), lum.shape)
    alto, ancho = lum.shape
    u = (col + 0.5) / ancho
    latitud = math.pi * (fila + 0.5) / alto        # 0 en el cenit (fila 0 = arriba)
    phi = 2 * math.pi * (0.5 - u)
    return int(fila), int(col), math.degrees(phi), 90.0 - math.degrees(latitud), float(lum.max())


def sol_realista():
    """(pitch, yaw) de la luz en la vista realista, leidos del C#."""
    src = io.open(CS_AMBIENTE, encoding='utf-8').read()
    m = re.search(r'SOL_REALISTA\s*=\s*new Vector3\(([-\d.]+)f,\s*([-\d.]+)f,\s*([-\d.]+)f\)', src)
    return float(m.group(1)), float(m.group(2))


def giro_para(phi_hdri_grados, pitch, yaw):
    """
    _Rotation (grados) del Skybox/Panoramic que pone el sol del HDRI en
    el rumbo de la luz. El shader muestrea la direccion girada:
    x' + i z' = e^{i alfa} (x + i z), asi que phi' = phi + alfa. La luz
    viaja en su forward (Euler(pitch, yaw)); el sol esta en -forward.
    """
    p, y = math.radians(pitch), math.radians(yaw)
    fx, fz = math.sin(y) * math.cos(p), math.cos(y) * math.cos(p)
    phi_sol = math.degrees(math.atan2(-fz, -fx))
    return (phi_hdri_grados - phi_sol) % 360.0, phi_sol


# ============================================================
# LO QUE VERIFICA
# ============================================================
def guid_de(ruta):
    with io.open(ruta + '.meta', encoding='utf-8') as f:
        return re.search(r'guid: ([0-9a-f]{32})', f.read()).group(1)


def main(argv):
    verificar = '--verificar' in argv
    fallas = []

    def check(ok, msg, detalle=''):
        print('  [%s] %s' % ('OK  ' if ok else 'FALLA', msg))
        if detalle:
            print('         ' + detalle)
        if not ok:
            fallas.append(msg)

    print('=' * 72)
    print('  RECURSOS DE LA VISTA REALISTA   (%s)' % os.path.relpath(AMBIENTE, rutas.RAIZ))
    print('=' * 72)
    hdr = os.path.join(TEXTURAS, 'cielo', 'cielo_2k.hdr')
    sol_json = os.path.join(TEXTURAS, 'cielo', 'sol.json')
    if os.path.isfile(hdr):
        img = leer_hdr(hdr)
        fila, col, phi, elev, lum = sol_del_hdri(img)
        pitch, yaw = sol_realista()
        giro, phi_luz = giro_para(phi, pitch, yaw)
        print('  el sol del HDRI: pixel (%d, %d) de %dx%d, phi\' %.1f grados, elevacion %.1f grados '
              '(luminancia %.0f)' % (fila, col, img.shape[0], img.shape[1], phi, elev, lum))
        print('  la luz realista: Euler(%.0f, %.0f) -> sol en phi %.1f, elevacion %.0f; giro del cielo %.2f'
              % (pitch, yaw, phi_luz, pitch, giro))
        datos = {'giro_grados': round(giro, 3), 'phi_hdri_grados': round(phi, 3),
                 'elevacion_hdri_grados': round(elev, 2), 'phi_luz_grados': round(phi_luz, 3),
                 'elevacion_luz_grados': pitch,
                 '_por_que': ('Giro del Skybox/Panoramic (_Rotation) que pone el sol del HDRI en el rumbo '
                              'de la luz direccional de la vista realista (AmbienteVisor.SOL_REALISTA). '
                              'Lo calcula comun/recursos_realistas.py; lo aplica Editor/RecursosRealistas.cs.')}
        if not verificar:
            with io.open(sol_json, 'w', encoding='utf-8') as f:
                json.dump(datos, f, indent=1, ensure_ascii=False)
            print('  escrito %s' % os.path.relpath(sol_json, rutas.RAIZ))
        check(os.path.isfile(sol_json) and abs(json.load(io.open(sol_json, encoding='utf-8'))['giro_grados']
                                               - giro) < 1e-3,
              '[1] sol.json tiene el giro que sale del HDRI y de SOL_REALISTA (%.2f grados)' % giro)
        if abs(elev - pitch) > 20:
            print('  (ojo: el sol del HDRI esta a %.0f grados y la luz a %.0f: las sombras no calzan en altura)'
                  % (elev, pitch))
        cielo_mat = os.path.join(AMBIENTE, 'Cielo.mat')
        if os.path.isfile(cielo_mat):
            src = io.open(cielo_mat, encoding='utf-8').read()
            m = re.search(r'- _Rotation: ([-\d.e]+)', src)
            r = float(m.group(1)) if m else float('nan')
            check(m is not None and abs(((r - giro + 180) % 360) - 180) <= TOL_GIRO_GRADOS,
                  '[4] Cielo.mat tiene ese giro (%s) y usa el HDR' % (m.group(1) if m else 'sin _Rotation'),
                  '' if guid_de(hdr) in src else 'Cielo.mat no apunta al .hdr')
        else:
            check(False, '[4] existe Cielo.mat (correr Editor/RecursosRealistas.cs)')
    else:
        check(False, '[1] existe %s' % os.path.relpath(hdr, rutas.RAIZ))

    for item in ITEMS + ('cielo',):
        fuente = os.path.join(TEXTURAS, item, 'FUENTE.txt')
        ok = os.path.isfile(fuente) and 'CC0' in io.open(fuente, encoding='utf-8').read()
        check(ok, '[2] %s: FUENTE.txt dice CC0' % item)
    for item in ITEMS:
        color = os.path.join(TEXTURAS, item, 'color.jpg')
        normal = os.path.join(TEXTURAS, item, 'normal_gl.jpg')
        if not (os.path.isfile(color + '.meta') and os.path.isfile(normal + '.meta')):
            check(False, '[3] %s: sus texturas estan importadas (.meta)' % item)
            continue
        meta = io.open(normal + '.meta', encoding='utf-8').read()
        tipo = re.search(r'textureType: (\d+)', meta)
        check(tipo is not None and tipo.group(1) == '1', '[3] %s: el mapa normal se importa como NormalMap' % item,
              'textureType = %s' % (tipo.group(1) if tipo else '?'))
        mat = os.path.join(AMBIENTE, 'Mat_%s.mat' % item)
        if not os.path.isfile(mat):
            check(False, '[4] existe Mat_%s.mat' % item)
            continue
        src = io.open(mat, encoding='utf-8').read()
        check(guid_de(color) in src and guid_de(normal) in src and '_NORMALMAP' in src,
              '[4] Mat_%s apunta a su color y su normal, con _NORMALMAP' % item)
    perfil = os.path.join(AMBIENTE, 'PerfilRealista.asset')
    check(os.path.isfile(perfil) and all(k in io.open(perfil, encoding='utf-8').read()
                                         for k in ('Tonemapping', 'ColorAdjustments', 'Bloom')),
          '[4] PerfilRealista.asset trae Tonemapping, ColorAdjustments y Bloom')
    print('=' * 72)
    if fallas:
        print('  FALLARON %d' % len(fallas))
        return 1
    print('  TODO OK')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
