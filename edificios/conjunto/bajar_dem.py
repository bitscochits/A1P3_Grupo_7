# -*- coding: utf-8 -*-
r"""
================================================================
 edificios/conjunto/bajar_dem.py  -  LAS COTAS DEL TERRENO DEL SITIO
================================================================
 El recorrido 'Topo Uandes' de Google Earth (sitio/topo_uandes.kmz) dice
 DONDE se quiere el relieve, pero no las cotas: Google Earth guarda un
 trazo pegado al terreno con altura 0 en todos sus puntos. Las cotas
 salen de un modelo digital de elevacion publico, y este script las baja
 UNA vez y deja en el repo solo la ventana del campus:

     sitio/dem_copernicus_glo30.json     (unas decenas de celdas)

 Despues edificios/conjunto/topografia.py lee ese archivo: el relieve no
 necesita internet ni librerias nuevas.

 ----------------------------------------------------------------
 LA FUENTE
 ----------------------------------------------------------------
 Copernicus DEM GLO-30 (ESA / Airbus, datos TanDEM-X de 2011 a 2015),
 una celda por segundo de arco (~31 m en N-S y ~26 m en E-O a esta
 latitud). Es un modelo de SUPERFICIE: incluye arboles y edificios que
 existian entonces, y es anterior al LT2 (planos 2024) y probablemente
 al edificio antiguo (planos 2017). Se lee del bucket publico de la ESA
 en AWS (copernicus-dem-30m), un GeoTIFF 'cloud optimized' por grado:
 se pide por HTTP solo el bloque que cubre la ventana.

 ----------------------------------------------------------------
 EL FORMATO, SIN GDAL
 ----------------------------------------------------------------
 TIFF con bloques de 1024 x 1024, float32, compresion deflate (zlib) y
 predictor 3 (punto flotante, Nota Tecnica 3 de TIFF): cada fila viene
 con sus bytes en planos (primero el byte mas significativo de todas las
 muestras, despues el siguiente...) y diferenciados uno contra el
 anterior. Se deshace con una suma acumulada modulo 256 y reordenando.
 La georreferencia sale de ModelTiepoint, ModelPixelScale y
 GTRasterTypeGeoKey (celda como area o como punto).

   python edificios/conjunto/bajar_dem.py              # baja y escribe
   python edificios/conjunto/bajar_dem.py --margen 150 # margen en m
================================================================
"""
from __future__ import annotations

import argparse
import datetime
import io
import json
import math
import os
import re
import struct
import sys
import zipfile
import zlib

import numpy as np

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(_AQUI)), 'comun'))
import rutas                                   # noqa: E402

SITIO = os.path.join(_AQUI, 'sitio')
KMZ_TOPO = os.path.join(SITIO, 'topo_uandes.kmz')
SALIDA = os.path.join(SITIO, 'dem_copernicus_glo30.json')
BUCKET = 'https://copernicus-dem-30m.s3.amazonaws.com'
ATRIBUCION = ('Copernicus DEM GLO-30: (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space '
              'GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights '
              'reserved.')


# ============================================================
# KMZ de Google Earth
# ============================================================
def leer_kmz(ruta):
    """{'poligonos': [[(lon, lat), ...]], 'lineas': [[(lon, lat), ...]]} del
    primer doc.kml del KMZ. Las alturas se descartan: Google Earth las deja
    en 0 en un trazo pegado al terreno."""
    with zipfile.ZipFile(ruta) as z:
        kml = next(n for n in z.namelist() if n.lower().endswith('.kml'))
        texto = z.read(kml).decode('utf-8')

    def coords(bloque):
        c = re.search(r'<coordinates>(.*?)</coordinates>', bloque, re.S).group(1).split()
        return [tuple(float(v) for v in p.split(',')[:2]) for p in c]

    poligonos = [coords(b) for b in re.findall(r'<Polygon>(.*?)</Polygon>', texto, re.S)]
    lineas = [coords(b) for b in re.findall(r'<LineString>(.*?)</LineString>', texto, re.S)]
    return {'poligonos': poligonos, 'lineas': lineas}


# ============================================================
# GeoTIFF por HTTP, de a pedazos
# ============================================================
TIPOS = {1: ('B', 1), 2: ('c', 1), 3: ('H', 2), 4: ('I', 4), 11: ('f', 4), 12: ('d', 8), 16: ('Q', 8)}


class CogRemoto(object):
    """Lo minimo de un GeoTIFF 'cloud optimized' para leer una ventana."""

    def __init__(self, url):
        import requests
        self.url = url
        self.sesion = requests.Session()
        cab = self._bytes(0, 65535)
        if cab[:4] != b'II*\x00':
            raise SystemExit('%s no es un TIFF little-endian clasico' % url)
        self._cab = cab
        off = struct.unpack('<I', cab[4:8])[0]
        n = struct.unpack('<H', cab[off:off + 2])[0]
        self.tags = {}
        for k in range(n):
            e = cab[off + 2 + 12 * k: off + 14 + 12 * k]
            tag, typ, cnt = struct.unpack('<HHI', e[:8])
            fmt, tam = TIPOS[typ]
            total = tam * cnt
            datos = e[8:8 + total] if total <= 4 else self._en(struct.unpack('<I', e[8:12])[0], total)
            self.tags[tag] = (datos.decode('latin-1').rstrip('\x00') if typ == 2
                              else list(struct.unpack('<%d%s' % (cnt, fmt), datos)))
        self.ancho, self.alto = self.tags[256][0], self.tags[257][0]
        self.tw, self.th = self.tags[322][0], self.tags[323][0]
        comp, pred = self.tags[259][0], self.tags.get(317, [1])[0]
        bits, fmt_muestra = self.tags[258][0], self.tags.get(339, [1])[0]
        if (comp, pred, bits, fmt_muestra) != (8, 3, 32, 3):
            raise SystemExit('formato no previsto: compresion %d, predictor %d, %d bits, tipo %d'
                             % (comp, pred, bits, fmt_muestra))
        self.offsets, self.cuentas = self.tags[324], self.tags[325]
        self.escala = self.tags[33550]                    # sx, sy, sz
        self.amarre = self.tags[33922]                    # i, j, k, x, y, z
        claves = self.tags.get(34735, [])
        geo = {claves[4 + 4 * i]: claves[4 + 4 * i + 3] for i in range(claves[3])} if claves else {}
        # GTRasterTypeGeoKey (1025): 1 = la celda es un area (el amarre es su
        # esquina), 2 = es un punto (el amarre es su centro).
        self.celda_es_area = geo.get(1025, 1) == 1

    def _bytes(self, a, b):
        r = self.sesion.get(self.url, headers={'Range': 'bytes=%d-%d' % (a, b)}, timeout=120)
        if r.status_code not in (200, 206):
            raise SystemExit('HTTP %d al pedir %s' % (r.status_code, self.url))
        return r.content

    def _en(self, off, n):
        if off + n <= len(self._cab):
            return self._cab[off:off + n]
        return self._bytes(off, off + n - 1)

    def centro(self, i, j):
        """(lon, lat) del centro de la celda columna i, fila j."""
        medio = 0.5 if self.celda_es_area else 0.0
        return (self.amarre[3] + (i - self.amarre[0] + medio) * self.escala[0],
                self.amarre[4] - (j - self.amarre[1] + medio) * self.escala[1])

    def indice(self, lon, lat):
        """(i, j) continuos de un punto: el inverso de centro()."""
        medio = 0.5 if self.celda_es_area else 0.0
        return ((lon - self.amarre[3]) / self.escala[0] + self.amarre[0] - medio,
                (self.amarre[4] - lat) / self.escala[1] + self.amarre[1] - medio)

    def bloque(self, bi, bj):
        """El bloque (bi, bj) decodificado: th x tw float32."""
        k = bj * ((self.ancho + self.tw - 1) // self.tw) + bi
        crudo = zlib.decompress(self._bytes(self.offsets[k], self.offsets[k] + self.cuentas[k] - 1))
        a = np.frombuffer(crudo, dtype=np.uint8).reshape(self.th, self.tw * 4)
        # Predictor 3: la diferencia es byte a byte a lo largo de la fila
        # entera (en uint8 la suma acumulada da la vuelta modulo 256)...
        a = np.cumsum(a, axis=1, dtype=np.uint8)
        # ...y los bytes vienen en planos: el mas significativo primero.
        planos = a.reshape(self.th, 4, self.tw).transpose(0, 2, 1).copy()
        return planos.view('>f4').reshape(self.th, self.tw).astype(np.float64)

    def ventana(self, i0, i1, j0, j1):
        """Celdas [j0, j1] x [i0, i1] (inclusive), leyendo solo sus bloques."""
        z = np.empty((j1 - j0 + 1, i1 - i0 + 1))
        cache = {}
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1):
                clave = (i // self.tw, j // self.th)
                if clave not in cache:
                    cache[clave] = self.bloque(*clave)
                z[j - j0, i - i0] = cache[clave][j % self.th, i % self.tw]
        return z, sorted(cache)


def nombre_del_bloque(lon, lat):
    """El GeoTIFF de 1 grado que contiene el punto (esquina SO en el nombre)."""
    la, lo = math.floor(lat), math.floor(lon)
    return 'Copernicus_DSM_COG_10_%s%02d_00_%s%03d_00_DEM' % (
        'S' if la < 0 else 'N', abs(la), 'W' if lo < 0 else 'E', abs(lo))


def main(argv=None):
    ap = argparse.ArgumentParser(description='Baja la ventana del DEM Copernicus GLO-30 del sitio')
    ap.add_argument('--margen', type=float, default=120.0,
                    help='margen alrededor del recorrido de Google Earth, en metros')
    a = ap.parse_args(argv)

    linea = leer_kmz(KMZ_TOPO)['lineas'][0]
    lons = [p[0] for p in linea]
    lats = [p[1] for p in linea]
    lat_c = 0.5 * (min(lats) + max(lats))
    dlat = a.margen / 111320.0
    dlon = a.margen / (111320.0 * math.cos(math.radians(lat_c)))
    caja = (min(lons) - dlon, max(lons) + dlon, min(lats) - dlat, max(lats) + dlat)

    nombre = nombre_del_bloque(0.5 * (caja[0] + caja[1]), lat_c)
    if nombre_del_bloque(caja[0], caja[2]) != nombre or nombre_del_bloque(caja[1], caja[3]) != nombre:
        raise SystemExit('la ventana cruza el borde de un grado: falta leer dos archivos')
    url = '%s/%s/%s.tif' % (BUCKET, nombre, nombre)
    print('  DEM  %s' % url)
    cog = CogRemoto(url)
    i_a, j_a = cog.indice(caja[0], caja[3])
    i_b, j_b = cog.indice(caja[1], caja[2])
    i0, i1 = int(math.floor(i_a)), int(math.ceil(i_b))
    j0, j1 = int(math.floor(j_a)), int(math.ceil(j_b))
    z, bloques = cog.ventana(i0, i1, j0, j1)
    lons_c = [cog.centro(i, j0)[0] for i in range(i0, i1 + 1)]
    lats_c = [cog.centro(i0, j)[1] for j in range(j0, j1 + 1)]
    print('  celda %s, %d x %d celdas (bloques %s), cotas %.1f a %.1f m'
          % ('area' if cog.celda_es_area else 'punto', z.shape[1], z.shape[0], bloques,
             z.min(), z.max()))

    salida = {
        '_que_es': ('Ventana del Copernicus DEM GLO-30 alrededor del recorrido topo_uandes.kmz. La '
                    'lee edificios/conjunto/topografia.py; la escribe bajar_dem.py.'),
        'fuente': 'Copernicus DEM GLO-30 (ESA/Airbus, TanDEM-X 2011-2015), modelo de superficie',
        'atribucion': ATRIBUCION,
        'url': url,
        'bajado': datetime.date.today().isoformat(),
        'celda_es_area': cog.celda_es_area,
        'paso_grados': [cog.escala[0], cog.escala[1]],
        'indices': {'i0': i0, 'i1': i1, 'j0': j0, 'j1': j1},
        'lon': [round(v, 9) for v in lons_c],
        'lat': [round(v, 9) for v in lats_c],
        '_z': 'z[fila][columna], filas de norte a sur (como lat), en metros sobre el geoide EGM2008',
        'z': [[round(float(v), 3) for v in fila] for fila in z],
    }
    os.makedirs(SITIO, exist_ok=True)
    with io.open(SALIDA, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(salida, fh, ensure_ascii=False, indent=1)
    print('  -> %s' % os.path.relpath(SALIDA, rutas.RAIZ).replace(os.sep, '/'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
