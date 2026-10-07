# -*- coding: utf-8 -*-
r"""
================================================================
 edificios/conjunto/bajar_osm.py  -  CALLES, ESTACIONAMIENTOS Y AREAS VERDES
================================================================
 Para poner autos estacionados y arboles DONDE ESTAN en el campus (y no
 al azar sobre el pasto), edificios/conjunto/entorno.py necesita saber
 donde estan los estacionamientos, sus pasillos, las calles, los
 edificios y las areas verdes. Eso esta en OpenStreetMap. Este script lo
 baja UNA vez y deja en el repo solo lo que cae en la zona del relieve:

     sitio/osm_campus.json

 Despues entorno.py lee ese archivo: no necesita internet.

 ----------------------------------------------------------------
 LA FUENTE
 ----------------------------------------------------------------
 OpenStreetMap, por la Overpass API (overpass-api.de), las 'way' con
 amenity, highway, building, landuse, leisure o natural dentro de un
 rectangulo en lon/lat que cubre la zona del relieve (la de
 topografia.py) mas un margen. Licencia ODbL: se puede usar nombrando
 la fuente, "(c) OpenStreetMap contributors" (va en el JSON y el visor
 la muestra en el panel).

 La zona se arma con topografia.armar(): la misma georreferencia del
 relieve, asi los autos y el relieve no pueden quedar corridos entre si.

   python edificios/conjunto/bajar_osm.py               # baja y escribe
   python edificios/conjunto/bajar_osm.py --margen 40   # margen en m
================================================================
"""
from __future__ import annotations

import argparse
import contextlib
import datetime
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(_AQUI)), 'comun'))
sys.path.insert(0, _AQUI)
import rutas                                   # noqa: E402,F401
import topografia                              # noqa: E402

SALIDA = os.path.join(topografia.SITIO, 'osm_campus.json')
OVERPASS = 'https://overpass-api.de/api/interpreter'
ATRIBUCION = '(c) OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright)'
CLAVES = ('amenity', 'highway', 'building', 'landuse', 'leisure', 'natural', 'parking', 'service',
          'surface', 'barrier', 'name', 'lanes', 'width')


def rectangulo(margen):
    """(sur, oeste, norte, este) en grados que cubre la zona del relieve + margen."""
    f = topografia.Fallas()
    with contextlib.redirect_stdout(io.StringIO()):
        r = topografia.armar(f)
    if f.lista:
        raise SystemExit('topografia.armar() fallo: %s' % f.lista)
    g = r['geo']
    xs = [p[0] for p in r['zona']]
    ys = [p[1] for p in r['zona']]
    esquinas = [(x, y) for x in (min(xs) - margen, max(xs) + margen)
                for y in (min(ys) - margen, max(ys) + margen)]
    ll = [g.lonlat(x, y) for x, y in esquinas]
    return (min(p[1] for p in ll), min(p[0] for p in ll), max(p[1] for p in ll), max(p[0] for p in ll))


def bajar(bbox):
    s, o, n, e = bbox
    caja = '%.6f,%.6f,%.6f,%.6f' % (s, o, n, e)
    consulta = ('[out:json][timeout:90];('
                + ''.join('way[%s](%s);' % (k, caja)
                          for k in ('amenity', 'highway', 'building', 'landuse', 'leisure', 'natural'))
                + ');out body geom;')
    datos = urllib.parse.urlencode({'data': consulta}).encode('ascii')
    # Overpass responde 504/429 cuando esta cargado: se reintenta con espera.
    for intento in range(4):
        pedido = urllib.request.Request(OVERPASS, data=datos,
                                        headers={'User-Agent': 'A1P1-Grupo7-visor/1.0 (curso UAndes)'})
        try:
            with urllib.request.urlopen(pedido, timeout=120) as resp:
                return consulta, json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as ex:
            if ex.code not in (429, 502, 503, 504) or intento == 3:
                raise
            print('  Overpass respondio %d; reintento en %d s' % (ex.code, 15 * (intento + 1)))
            time.sleep(15 * (intento + 1))


def main(argv=None):
    ap = argparse.ArgumentParser(description='Baja de OpenStreetMap lo que rodea al edificio')
    ap.add_argument('--margen', type=float, default=30.0, help='m alrededor de la zona del relieve')
    a = ap.parse_args(argv)
    bbox = rectangulo(a.margen)
    print('  rectangulo (sur, oeste, norte, este): %.6f %.6f %.6f %.6f' % bbox)
    consulta, d = bajar(bbox)
    vias = []
    for el in d.get('elements', []):
        if el.get('type') != 'way' or 'geometry' not in el:
            continue
        t = el.get('tags', {})
        vias.append({'id': el['id'],
                     'tags': {k: t[k] for k in CLAVES if k in t},
                     'lonlat': [[round(p['lon'], 7), round(p['lat'], 7)] for p in el['geometry']]})
    vias.sort(key=lambda v: v['id'])
    out = {
        'fuente': 'OpenStreetMap, por la Overpass API (%s)' % OVERPASS,
        'atribucion': ATRIBUCION,
        'bajado': datetime.date.today().isoformat(),
        'consulta': consulta,
        'rectangulo_sur_oeste_norte_este': [round(v, 6) for v in bbox],
        '_por_que': ('Donde estan los estacionamientos (amenity=parking), sus pasillos (highway=service), '
                     'las calles, los edificios y las areas verdes alrededor del edificio, para que '
                     'edificios/conjunto/entorno.py ponga autos y arboles donde corresponde. Solo dibujo.'),
        'vias': vias,
    }
    with io.open(SALIDA, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(',', ':'))
    print('  -> %s: %d vias (%.0f KB)' % (os.path.relpath(SALIDA, rutas.RAIZ).replace(os.sep, '/'),
                                         len(vias), os.path.getsize(SALIDA) / 1024))
    return 0


if __name__ == '__main__':
    sys.exit(main())
