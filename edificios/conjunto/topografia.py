# -*- coding: utf-8 -*-
r"""
================================================================
 edificios/conjunto/topografia.py  -  EL RELIEVE DEL SITIO, PARA EL VISOR
================================================================
 Arma la malla del terreno alrededor del edificio y la deja en
 data/unity/topografia_<ed>.json (conjunto, lt2 e ingenieria). Unity
 solo la dibuja (AmbienteVisor.Topografia.cs): nada de esto cambia un
 resultado estructural.

 Entradas (edificios/conjunto/sitio/, con sus supuestos en sitio.json):
   topo_uandes.kmz              la ZONA, trazada en Google Earth
   techo_edificio_antiguo.kmz   el techo del cuerpo antiguo en la foto
   dem_copernicus_glo30.json    las COTAS (bajar_dem.py)

 ----------------------------------------------------------------
 COMO SE UBICA
 ----------------------------------------------------------------
 1. Lat/lon -> metros: este y norte locales alrededor del centro del
    techo, con los radios del elipsoide WGS84 en esa latitud. En 300 m
    el error de esta proyeccion es de milimetros.
 2. El giro: el lado largo del techo en la foto tiene un rumbo; +x del
    modelo va en ese rumbo (sitio.json dice hacia que extremo, y aca se
    comprueba con la pendiente del terreno).
 3. La posicion: el centro del techo de la foto cae en el centro del
    rectangulo del techo del modelo (sitio.json, 'techo_en_el_modelo').
 4. La cota: el DEM se corre en vertical por minimos cuadrados para que
    el terreno calce con los apoyos en terreno del modelo.
 Con eso cada punto (x, y) del modelo tiene su lat/lon, y su cota sale
 del DEM por interpolacion bilineal.

 ----------------------------------------------------------------
 QUE COMPRUEBA (termina con 1 si algo falla)
 ----------------------------------------------------------------
   - el techo de la foto tiene el tamano del techo del modelo (mas el
     borde de la losa), y sus lados largos son paralelos;
   - el terreno sube hacia +x a lo largo del edificio, como las terrazas
     del modelo (si no, el giro esta 180 grados al reves);
   - con --verificar, que los JSON en disco sean los que se arman ahora.

   python edificios/conjunto/topografia.py               # escribe los JSON y la figura
   python edificios/conjunto/topografia.py --verificar   # no escribe: compara
================================================================
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys

import numpy as np

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(_AQUI)), 'comun'))
import rutas                                   # noqa: E402
import contrato                                # noqa: E402
from campos_cs import campos_de_clases         # noqa: E402

sys.path.insert(0, _AQUI)
from bajar_dem import leer_kmz, ATRIBUCION     # noqa: E402

SITIO = os.path.join(_AQUI, 'sitio')
CALCE = os.path.join(_AQUI, 'calce.json')
FIGURA = os.path.join(SITIO, 'topografia_planta.png')
EDIFICIOS = ('conjunto', 'lt2', 'ingenieria')
SCRIPTS_CS = os.path.join(rutas.UNITY_PROYECTO, 'Assets', 'Scripts')
# Que clase C# lee cada parte del JSON (AmbienteVisor.Topografia.cs y,
# para los vertices de planta, ModeloEstructural.cs).
CLASES_CS = {'TopografiaJson': None, 'InfoTopografia': 'info', 'HuecoTopografia': 'huecos',
             'VerticePlanta': 'techo_foto'}
SIN_DATO = -9999.0
# WGS84
A_WGS = 6378137.0
E2_WGS = 6.69437999014e-3


def leer_json(ruta):
    with io.open(ruta, encoding='utf-8') as fh:
        return json.load(fh)


def rel(ruta):
    return os.path.relpath(ruta, rutas.RAIZ).replace(os.sep, '/')


class Fallas(object):
    def __init__(self):
        self.lista = []

    def check(self, ok, que):
        print('  [%s] %s' % ('OK  ' if ok else 'FALLA', que))
        if not ok:
            self.lista.append(que)
        return ok


# ============================================================
# Lat/lon <-> metros locales
# ============================================================
class Local(object):
    """Este/norte en metros alrededor de (lon0, lat0), con los radios de
    curvatura del elipsoide en lat0 (meridiano M y primer vertical N)."""

    def __init__(self, lon0, lat0):
        self.lon0, self.lat0 = lon0, lat0
        s = math.sin(math.radians(lat0))
        w = math.sqrt(1.0 - E2_WGS * s * s)
        self.M = A_WGS * (1.0 - E2_WGS) / w ** 3
        self.N = A_WGS / w
        self.cos0 = math.cos(math.radians(lat0))

    def a_metros(self, lon, lat):
        return (math.radians(lon - self.lon0) * self.N * self.cos0,
                math.radians(lat - self.lat0) * self.M)

    def a_grados(self, e, n):
        return (self.lon0 + math.degrees(e / (self.N * self.cos0)),
                self.lat0 + math.degrees(n / self.M))


def rumbo(de, a):
    """Azimut en grados (desde el norte, hacia el este) del vector de -> a."""
    return math.degrees(math.atan2(a[0] - de[0], a[1] - de[1])) % 360.0


# ============================================================
# La georreferencia: modelo (x, y) <-> metros locales (e, n)
# ============================================================
class Georreferencia(object):
    r"""
    e = e_c + cos(t)·(x - x_c) - sin(t)·(y - y_c)      t = 90 - rumbo de +x
    n = n_c + sin(t)·(x - x_c) + cos(t)·(y - y_c)
    con (x_c, y_c) el centro del techo en el modelo y (e_c, n_c) el de la
    foto. Sin escala: el modelo y Google Earth estan en metros.
    """

    def __init__(self, rumbo_x, centro_modelo, centro_local, local):
        self.rumbo_x = rumbo_x
        self.t = math.radians(90.0 - rumbo_x)
        self.xc, self.yc = centro_modelo
        self.ec, self.nc = centro_local
        self.local = local

    def a_local(self, x, y):
        c, s = math.cos(self.t), math.sin(self.t)
        dx, dy = x - self.xc, y - self.yc
        return self.ec + c * dx - s * dy, self.nc + s * dx + c * dy

    def a_modelo(self, e, n):
        c, s = math.cos(self.t), math.sin(self.t)
        de, dn = e - self.ec, n - self.nc
        return self.xc + c * de + s * dn, self.yc - s * de + c * dn

    def lonlat(self, x, y):
        return self.local.a_grados(*self.a_local(x, y))


class Dem(object):
    """El DEM de la ventana, con interpolacion bilineal en lon/lat."""

    def __init__(self, d):
        self.lon = np.array(d['lon'])
        self.lat = np.array(d['lat'])            # de norte a sur
        self.z = np.array(d['z'])
        self.d = d

    def cota(self, lon, lat):
        fi = (lon - self.lon[0]) / (self.lon[1] - self.lon[0])
        fj = (lat - self.lat[0]) / (self.lat[1] - self.lat[0])
        if not (0 <= fi <= len(self.lon) - 1 and 0 <= fj <= len(self.lat) - 1):
            return None
        i, j = min(int(fi), len(self.lon) - 2), min(int(fj), len(self.lat) - 2)
        u, v = fi - i, fj - j
        z = self.z
        return ((1 - u) * (1 - v) * z[j, i] + u * (1 - v) * z[j, i + 1]
                + (1 - u) * v * z[j + 1, i] + u * v * z[j + 1, i + 1])


# ============================================================
def envolvente(puntos):
    """Envolvente convexa (cadena monotona), antihoraria."""
    p = sorted(set(puntos))
    if len(p) < 3:
        return p

    def cruz(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    abajo, arriba = [], []
    for q in p:
        while len(abajo) >= 2 and cruz(abajo[-2], abajo[-1], q) <= 0:
            abajo.pop()
        abajo.append(q)
    for q in reversed(p):
        while len(arriba) >= 2 and cruz(arriba[-2], arriba[-1], q) <= 0:
            arriba.pop()
        arriba.append(q)
    return abajo[:-1] + arriba[:-1]


def dentro(pto, poli):
    """Punto en poligono convexo antihorario."""
    x, y = pto
    for a, b in zip(poli, poli[1:] + poli[:1]):
        if (b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0]) < -1e-9:
            return False
    return True


def cuerpos_del_conjunto(conj):
    """{'antiguo': nodos, 'lt2': nodos} por el tag (1xxxxx y 2xxxxx)."""
    out = {'antiguo': [], 'lt2': []}
    for n in conj['nodos']:
        if n.get('auxiliar'):
            continue
        tag = int(n['id'])
        out['antiguo' if tag < 200000 else 'lt2'].append(n)
    return out


def armar(fallas):
    perfil = leer_json(os.path.join(SITIO, 'sitio.json'))
    techo_foto = leer_kmz(os.path.join(SITIO, perfil['techo']))['poligonos'][0]
    recorrido = leer_kmz(os.path.join(SITIO, perfil['recorrido']))['lineas'][0]
    dem = Dem(leer_json(os.path.join(SITIO, perfil['dem'])))
    conj = contrato.cargar_modelo('conjunto')
    calce = leer_json(CALCE)['edificios']

    # --- 1. la foto en metros locales, alrededor del centro del techo
    esquinas = techo_foto[:-1] if techo_foto[0] == techo_foto[-1] else techo_foto
    lon0 = sum(p[0] for p in esquinas) / len(esquinas)
    lat0 = sum(p[1] for p in esquinas) / len(esquinas)
    local = Local(lon0, lat0)
    E = [local.a_metros(*p) for p in esquinas]
    lados = [(E[k], E[(k + 1) % 4]) for k in range(4)]
    largos = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in lados]
    k_largo = 0 if largos[0] + largos[2] > largos[1] + largos[3] else 1
    # Rumbo del lado largo, promediando los dos lados opuestos como vectores
    # (el segundo da vuelta: va en sentido contrario en el poligono).
    rs = [rumbo(*lados[k_largo]), (rumbo(*lados[k_largo + 2]) + 180.0) % 360.0]
    vx = sum(math.sin(math.radians(r)) for r in rs)
    vy = sum(math.cos(math.radians(r)) for r in rs)
    r_largo = math.degrees(math.atan2(vx, vy)) % 360.0
    # Hacia que extremo apunta +x: el declarado en sitio.json.
    hacia = {'N': 0, 'NNE': 22.5, 'NE': 45, 'ENE': 67.5, 'E': 90, 'ESE': 112.5, 'SE': 135, 'SSE': 157.5,
             'S': 180, 'SSO': 202.5, 'SO': 225, 'OSO': 247.5, 'O': 270, 'ONO': 292.5, 'NO': 315,
             'NNO': 337.5}[perfil['x_del_modelo_hacia']]
    if math.cos(math.radians(r_largo - hacia)) < 0:
        r_largo = (r_largo + 180.0) % 360.0
    largo_foto = 0.5 * (largos[k_largo] + largos[k_largo + 2])
    ancho_foto = 0.5 * (largos[1 - k_largo] + largos[3 - k_largo])
    paralelo = abs(((rs[0] - rs[1] + 90) % 180) - 90)

    tm = perfil['techo_en_el_modelo']
    print('  techo en la foto: %.2f x %.2f m, lado largo a %.1f grados (los dos lados a %.1f grados '
          'entre si)' % (largo_foto, ancho_foto, r_largo, paralelo))
    print('  techo en el modelo, entre ejes: %.2f x %.2f m' % (tm['x'][1] - tm['x'][0], tm['y'][1] - tm['y'][0]))
    # El rectangulo declarado tiene que existir en el modelo: nodos del
    # cuerpo antiguo en esa z sobre sus cuatro bordes.
    techo_nodos = [n for n in cuerpos_del_conjunto(conj)['antiguo'] if abs(n['z'] - tm['z']) < 0.01]
    bordes = [any(abs(n[c] - v) < 0.01 for n in techo_nodos) for c, v in
              (('x', tm['x'][0]), ('x', tm['x'][1]), ('y', tm['y'][0]), ('y', tm['y'][1]))]
    fallas.check(all(bordes), 'el rectangulo del techo de sitio.json tiene nodos del cuerpo antiguo en '
                 'sus cuatro bordes, en z = %.2f' % tm['z'])
    # La foto mide por fuera de la losa: tiene que ser algo MAS grande que
    # entre ejes, en no mas que el borde de la losa y el trazo a mano.
    d_largo = largo_foto - (tm['x'][1] - tm['x'][0])
    d_ancho = ancho_foto - (tm['y'][1] - tm['y'][0])
    fallas.check(-0.5 <= d_largo <= 3.0 and -0.5 <= d_ancho <= 3.0 and paralelo < 3.0,
                 'el techo de la foto es el del modelo mas el borde: +%.2f m de largo y +%.2f m de ancho '
                 '(se acepta de -0.5 a +3.0 m: medio pilar 0.35 m y el borde de la losa por lado, mas el '
                 'trazo a mano sobre la foto)' % (d_largo, d_ancho))

    geo = Georreferencia(r_largo, (0.5 * (tm['x'][0] + tm['x'][1]), 0.5 * (tm['y'][0] + tm['y'][1])),
                         (0.0, 0.0), local)

    # --- 2. el terreno sube hacia +x a lo largo del edificio?
    cuerpos = cuerpos_del_conjunto(conj)
    xs = [n['x'] for n in cuerpos['antiguo']]
    ym = 0.5 * (tm['y'][0] + tm['y'][1])
    z_oeste = dem.cota(*geo.lonlat(min(xs), ym))
    z_este = dem.cota(*geo.lonlat(max(xs), ym))
    fallas.check(z_este > z_oeste,
                 'el terreno sube hacia +x a lo largo del cuerpo antiguo (%.1f m en x = %.1f, %.1f m en '
                 'x = %.1f), como sus terrazas: el giro no esta al reves' % (z_oeste, min(xs), z_este, max(xs)))

    # --- 3. la cota: calce vertical con los apoyos en terreno
    apoyos = [n for n in conj['nodos'] if not n.get('auxiliar') and any(n.get('restricciones') or [])]
    dif = []
    for n in apoyos:
        z = dem.cota(*geo.lonlat(n['x'], n['y']))
        if z is not None:
            dif.append(z - n['z'])
    dif = np.array(dif)
    desfase = float(dif.mean())
    resid = dif - desfase
    print('  calce vertical: cota DEM = z del modelo + %.2f m (por minimos cuadrados sobre %d apoyos); '
          'residuo: rms %.2f m, de %.2f a %.2f m' % (desfase, len(dif), float(np.sqrt((resid ** 2).mean())),
                                                    float(resid.min()), float(resid.max())))
    fallas.check(len(dif) == len(apoyos), 'los %d apoyos en terreno caen dentro del DEM' % len(apoyos))

    # --- 4. la malla, en coordenadas del conjunto
    zona = envolvente([geo.a_modelo(*local.a_metros(*p)) for p in recorrido])
    paso = float(perfil['paso_m'])
    x0 = math.floor(min(p[0] for p in zona) / paso) * paso
    y0 = math.floor(min(p[1] for p in zona) / paso) * paso
    nx = int(math.ceil((max(p[0] for p in zona) - x0) / paso)) + 1
    ny = int(math.ceil((max(p[1] for p in zona) - y0) / paso)) + 1
    malla = np.full((ny, nx), SIN_DATO)
    for j in range(ny):
        for i in range(nx):
            x, y = x0 + i * paso, y0 + j * paso
            if dentro((x, y), zona):
                z = dem.cota(*geo.lonlat(x, y))
                if z is not None:
                    malla[j, i] = z - desfase
    validos = malla[malla > SIN_DATO / 2]
    print('  malla: %d x %d nodos cada %.1f m (x %.1f a %.1f, y %.1f a %.1f), %d con cota, de %.2f a %.2f m '
          'del modelo' % (nx, ny, paso, x0, x0 + (nx - 1) * paso, y0, y0 + (ny - 1) * paso, validos.size,
                          float(validos.min()), float(validos.max())))

    techo_modelo = [geo.a_modelo(*e) for e in E]
    return {'perfil': perfil, 'geo': geo, 'dem': dem, 'conj': conj, 'calce': calce, 'cuerpos': cuerpos,
            'malla': malla, 'x0': x0, 'y0': y0, 'paso': paso, 'nx': nx, 'ny': ny, 'zona': zona,
            'techo_modelo': techo_modelo, 'desfase': desfase, 'resid': resid, 'r_largo': r_largo,
            'recorrido': [geo.a_modelo(*local.a_metros(*p)) for p in recorrido]}


def para_edificio(r, ed):
    """El JSON de un edificio: la malla y los huecos en SUS coordenadas."""
    calce = r['calce']
    if ed == 'conjunto':
        d = (0.0, 0.0, 0.0)
        cuerpos = ['antiguo', 'lt2']
    else:
        c = calce[ed]
        if abs(float(c.get('giro_grados', 0.0))) > 1e-12:
            raise SystemExit('calce.json gira el cuerpo %s: falta implementar el giro' % ed)
        d = (float(c['dx']), float(c['dy']), float(c.get('dz', 0.0)))
        cuerpos = ['lt2'] if ed == 'lt2' else ['antiguo']
    margen = float(r['perfil']['margen_hueco_m'])
    huecos = []
    for cu in cuerpos:
        ns = r['cuerpos'][cu]
        huecos.append({'x1': round(min(n['x'] for n in ns) - margen - d[0], 3),
                       'y1': round(min(n['y'] for n in ns) - margen - d[1], 3),
                       'x2': round(max(n['x'] for n in ns) + margen - d[0], 3),
                       'y2': round(max(n['y'] for n in ns) + margen - d[1], 3)})
    visor = leer_json(rutas.unity(ed))
    cota_fondo = float(visor['info'].get('cota_terreno', SIN_DATO))
    # Los JSON del visor no traen info.edificio: Unity reconoce su modelo
    # por cuantos nodos y elementos tiene al cargarlo.
    huella = {'n_nodos': len(visor['nodos']), 'n_elementos': len(visor['elementos'])}
    m = r['malla']
    z = [round(float(v) - d[2], 3) if v > SIN_DATO / 2 else SIN_DATO for v in m.reshape(-1)]
    g = r['geo']
    return {
        'info': {
            'edificio': ed,
            'n_nodos': huella['n_nodos'],
            'n_elementos': huella['n_elementos'],
            'generado_por': 'edificios/conjunto/topografia.py',
            'fuente': r['dem'].d['fuente'],
            'atribucion': ATRIBUCION,
            'zona': 'trazada en Google Earth (edificios/conjunto/sitio/%s)' % r['perfil']['recorrido'],
            'rumbo_x_grados': round(g.rumbo_x, 3),
            'lon_centro_techo': round(g.local.lon0, 8),
            'lat_centro_techo': round(g.local.lat0, 8),
            'desfase_vertical_m': round(r['desfase'] - d[2], 3),
            'residuo_rms_m': round(float(np.sqrt((r['resid'] ** 2).mean())), 3),
            '_por_que': ('Solo DIBUJO: el terreno natural (Copernicus GLO-30, celda de ~30 m, anterior a la '
                         'obra) alrededor del edificio, ubicado con el techo del cuerpo antiguo en Google '
                         'Earth y calzado en vertical con los apoyos en terreno. Ningun calculo lo usa. '
                         'Supuestos: edificios/conjunto/sitio/sitio.json.'),
        },
        'x0': round(r['x0'] - d[0], 3),
        'y0': round(r['y0'] - d[1], 3),
        'paso': r['paso'],
        'nx': r['nx'],
        'ny': r['ny'],
        'sin_dato': SIN_DATO,
        'cota_fondo': round(cota_fondo, 3),
        'z': z,
        'huecos': huecos,
        'techo_foto': [{'x': round(p[0] - d[0], 3), 'y': round(p[1] - d[1], 3)} for p in r['techo_modelo']],
    }


def contrato_cs(js, fallas):
    r"""
    Cada clave del JSON tiene su campo en la clase C# que lo lee, y cada
    campo de esas clases viene en el JSON: JsonUtility ignora sin avisar
    una clave sin campo, y un campo sin clave queda en su valor por
    defecto (un relieve plano en z = 0, sin ningun error).
    """
    clases = campos_de_clases(os.path.join(SCRIPTS_CS, 'AmbienteVisor.Topografia.cs'))
    clases.update({k: v for k, v in campos_de_clases(os.path.join(SCRIPTS_CS, 'ModeloEstructural.cs')).items()
                   if k == 'VerticePlanta'})
    for clase, clave in CLASES_CS.items():
        muestra = js if clave is None else (js[clave][0] if isinstance(js[clave], list) else js[clave])
        en_cs = clases.get(clase, set())
        sin_campo = sorted(set(muestra) - en_cs)
        sin_clave = sorted(en_cs - set(muestra))
        fallas.check(clase in clases and not sin_campo and not sin_clave,
                     'contrato JSON <-> C#: %s%s' % (clase, '' if not (sin_campo or sin_clave) else
                                                    ' (claves sin campo %s, campos sin clave %s)'
                                                    % (sin_campo, sin_clave)))


def figura(r, ruta):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    m = np.where(r['malla'] > SIN_DATO / 2, r['malla'], np.nan)
    X = r['x0'] + r['paso'] * np.arange(r['nx'])
    Y = r['y0'] + r['paso'] * np.arange(r['ny'])
    fig, ax = plt.subplots(figsize=(9, 9))
    cf = ax.contourf(X, Y, m, levels=20, cmap='terrain', alpha=0.85)
    cs = ax.contour(X, Y, m, levels=np.arange(np.floor(np.nanmin(m)), np.nanmax(m) + 1, 1.0),
                    colors='k', linewidths=0.4, alpha=0.5)
    ax.clabel(cs, cs.levels[::5], fmt='%.0f', fontsize=7)
    fig.colorbar(cf, ax=ax, shrink=0.7, label='z del modelo [m] (el DEM menos %.2f m)' % r['desfase'])
    for nombre, color in (('antiguo', '#1f3a5f'), ('lt2', '#c8641e')):
        ns = r['cuerpos'][nombre]
        ax.plot([n['x'] for n in ns], [n['y'] for n in ns], '.', ms=2, color=color,
                label='nodos del %s' % ('cuerpo antiguo' if nombre == 'antiguo' else 'LT2'))
    t = r['techo_modelo'] + r['techo_modelo'][:1]
    ax.plot([p[0] for p in t], [p[1] for p in t], '-', color='red', lw=1.6, label='techo trazado en Google Earth')
    rc = r['recorrido']
    ax.plot([p[0] for p in rc], [p[1] for p in rc], '-', color='gray', lw=0.5, alpha=0.6,
            label='recorrido "Topo Uandes"')
    # el norte
    g = r['geo']
    cx, cy = X[-1] - 25, Y[-1] - 25
    nx_, ny_ = g.a_modelo(g.ec, g.nc + 15.0)
    bx, by = g.a_modelo(g.ec, g.nc)
    ax.annotate('N', xy=(cx + nx_ - bx, cy + ny_ - by), xytext=(cx, cy), ha='center',
                arrowprops=dict(arrowstyle='->', lw=1.5), fontsize=12, fontweight='bold')
    ax.set_aspect('equal')
    ax.set_xlabel('x del modelo [m]')
    ax.set_ylabel('y del modelo [m]')
    ax.set_title('Relieve del sitio en coordenadas del conjunto\n+x del modelo a %.1f grados (rumbo); '
                 'Copernicus GLO-30' % r['r_largo'], fontsize=10)
    ax.legend(loc='lower left', fontsize=8)
    fig.tight_layout()
    fig.savefig(ruta, dpi=110)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Relieve del sitio para el visor')
    ap.add_argument('--verificar', action='store_true', help='no escribe: compara con lo que hay en disco')
    a = ap.parse_args(argv)
    print('=' * 70)
    print('  RELIEVE DEL SITIO (edificios/conjunto/topografia.py)')
    print('=' * 70)
    f = Fallas()
    r = armar(f)
    for ed in EDIFICIOS:
        js = para_edificio(r, ed)
        if ed == EDIFICIOS[0]:
            contrato_cs(js, f)
        ruta = rutas.unity('topografia_' + ed)
        if a.verificar:
            igual = os.path.isfile(ruta) and leer_json(ruta) == json.loads(json.dumps(js))
            f.check(igual, '%s es el que se arma ahora' % rel(ruta))
        else:
            with io.open(ruta, 'w', encoding='utf-8', newline='\n') as fh:
                json.dump(js, fh, ensure_ascii=False, separators=(',', ':'))
            print('  -> %s (%.0f KB)' % (rel(ruta), os.path.getsize(ruta) / 1024))
    if not a.verificar:
        figura(r, FIGURA)
        print('  -> %s' % rel(FIGURA))
    print('=' * 70)
    if f.lista:
        print('  FALLA: %d' % len(f.lista))
        return 1
    print('  EL RELIEVE CALZA CON EL TECHO Y CON LAS TERRAZAS DEL MODELO')
    return 0


if __name__ == '__main__':
    sys.exit(main())
