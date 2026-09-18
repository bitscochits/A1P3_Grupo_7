# -*- coding: utf-8 -*-
r"""
Verifica que el JSON que genera Python calce con las clases C# que lo
leen en Unity.

POR QUE EXISTE ESTE TEST
JsonUtility (el parser de Unity) NO avisa cuando un campo no calza:
simplemente deja la variable en su valor por defecto. Una clave mal
escrita no da error ni warning, solo un modelo que se dibuja raro. Un
'uz' mal escrito da deformada plana; un 'area' mal escrito da areas
tributarias en cero. Y como no hay excepcion, se descubre tarde.

Este test compara los campos declarados en los .cs contra las claves
reales del JSON exportado.

Correr:  python comun/test_contrato_unity.py [lt2 | ingenieria | conjunto]
"""
import json
import os
import re
import sys

# Este archivo vive en comun/, al lado de rutas.py: no se cuenta dirname
# para llegar a la raiz (CLAUDE.md, "Rutas"); la raiz la da rutas.
_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _AQUI)
import rutas                             # noqa: E402
_RAIZ = rutas.RAIZ

# El edificio se elige por linea de comandos: el contrato es el mismo
# para todos y por eso este test vive en comun/.
EDIFICIO = sys.argv[1] if len(sys.argv) > 1 else 'lt2'
JSON = rutas.unity(EDIFICIO)
CS = os.path.join(_RAIZ, 'unity', 'Assets', 'Scripts', 'ModeloEstructural.cs')

fallos = []


def check(cond, msg, detalle=""):
    print(f"  [{'OK  ' if cond else 'FALLA'}] {msg}")
    if detalle:
        print(f"         {detalle}")
    if not cond:
        fallos.append(msg)


# ============================================================
# Parseo simple del C#: campos publicos de cada clase serializable
# ============================================================
def campos_de_clases(ruta):
    with open(ruta, encoding='utf-8') as f:
        src = f.read()

    # Fuera comentarios, para no confundir ejemplos de las notas con
    # codigo real.
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    src = re.sub(r'//[^\n]*', '', src)

    clases = {}
    for m in re.finditer(r'class\s+(\w+)\s*\{', src):
        nombre = m.group(1)
        # Recorta hasta cerrar la llave de la clase.
        i = m.end() - 1
        prof, j = 0, i
        while j < len(src):
            if src[j] == '{':
                prof += 1
            elif src[j] == '}':
                prof -= 1
                if prof == 0:
                    break
            j += 1
        cuerpo = src[i:j]

        campos = set()
        # public <tipo> a, b, c;   (ignora propiedades con { get; })
        for d in re.finditer(
                r'public\s+[\w<>\[\]\.]+\s+([\w\s,]+?)\s*(?:=[^;]*)?;', cuerpo):
            grupo = d.group(1)
            if '(' in grupo:
                continue
            for nom in grupo.split(','):
                nom = nom.strip()
                if nom and re.fullmatch(r'\w+', nom):
                    campos.add(nom)
        clases[nombre] = campos
    return clases


print("Leyendo contrato...")
if not os.path.exists(JSON):
    print(f"No existe {JSON}. Corre primero: python src/exportar_unity.py")
    sys.exit(1)

with open(JSON, encoding='utf-8') as f:
    datos = json.load(f)

clases = campos_de_clases(CS)
print(f"  clases C# encontradas: {len(clases)}")


# ============================================================
print("\n[1] Cada clave del JSON tiene su campo en C#")
# ============================================================
def comparar(nombre_clase, muestra, ignorar=()):
    """Toda clave del JSON debe existir como campo publico en el C#."""
    if nombre_clase not in clases:
        check(False, f"la clase {nombre_clase} existe en el C#")
        return
    campos = clases[nombre_clase]
    faltan = [k for k in muestra
              if k not in campos and k not in ignorar]
    check(not faltan,
          f"{nombre_clase}: todas las claves del JSON estan en el C#",
          f"sin campo C#: {faltan}" if faltan else "")


# ----------------------------------------------------------------
# CLAVES QUE EL C# NO NECESITA, A PROPOSITO
# ----------------------------------------------------------------
# comparar() revisa en una sola direccion: que cada clave del JSON
# tenga su campo en el C#. Una clave SIN campo no rompe el dibujo
# (JsonUtility la ignora sin quejarse), pero es un dato que Unity no
# ve y que PIERDE si vuelve a escribir el modelo con JsonUtility.ToJson
# (el reanalisis y 'Guardar JSON' del editor). La direccion contraria
# -- un campo C# sin clave, que queda en su valor por defecto -- no la
# cubre este bloque: en parte la cubre [2], que exige datos en los
# campos que el visor usa, y para el anexo de la Semana 4 la cubre
# semana04/test_contrato_semana04.py, que revisa las dos direcciones.
#
# Estas claves se dejan fuera del C# a proposito; son datos de analisis
# o de procedencia que Unity no dibuja:
#
#   enfierradura                                 el fierro, para la capacidad
#   E, G, E_del_cuerpo, fpc_MPa, b_h_deducidos  el hormigon por cuerpo del
#                                               conjunto; Unity no calcula
#   incluye_peso_propio                          separa losa de peso propio
#   forma                                        procedencia del poligono
#   cuerpos, extra                               de que edificios se armo;
#                                                la ficha del modelo
#
# area_tributaria y w_gravedad SI estan en el C# desde la Semana 5: el
# inspector muestra el area total de la viga, que en Ingenieria reparte
# en varias entradas de areas_tributarias.
NO_VAN_AL_CSHARP = {
    'ModeloEstructural': ('resumen',),
    'InfoModelo': ('cuerpos', 'extra'),
    'Elemento': ('enfierradura',),
    'Seccion': ('E', 'G', 'E_del_cuerpo', 'fpc_MPa', 'b_h_deducidos'),
    'AreaTributaria': ('forma',),
    'CasoDeCarga': ('incluye_peso_propio',),
}

# Las claves de TODOS los objetos de cada lista, no solo las del primero:
# en Ingenieria el primer elemento es una columna y solo los muros traen
# largo/espesor/dir_largo; en el conjunto solo las entradas del LT2
# traen qG, w y luz. Mirar el primero dejaba esas claves sin revisar.
def claves(lista):
    todas = set()
    for o in lista:
        todas |= set(o.keys())
    return sorted(todas)


comparar('ModeloEstructural', datos.keys(),
         ignorar=NO_VAN_AL_CSHARP['ModeloEstructural'])
comparar('Nodo', claves(datos['nodos']))
comparar('Elemento', claves(datos['elementos']),
         ignorar=NO_VAN_AL_CSHARP['Elemento'])
comparar('Seccion', claves(datos['secciones']),
         ignorar=NO_VAN_AL_CSHARP['Seccion'])
comparar('Diafragma', claves(datos['diafragmas']))
comparar('AreaTributaria', claves(datos['areas_tributarias']),
         ignorar=NO_VAN_AL_CSHARP['AreaTributaria'])
# Los poligonos tributarios son opcionales: un modelo puede exportar el
# AREA de cada viga pero todavia no el poligono, porque sus panos no
# vienen de una grilla sino de las caras del grafo de vigas. Si no hay
# poligonos se dice; no se aprueba por vacio.
_vert = [v for t in datos['areas_tributarias'] for v in t['vertices']]
if _vert:
    comparar('VerticePlanta', claves(_vert))
else:
    print("  [--  ] VerticePlanta: no hay poligonos tributarios exportados "
          "(el visor no dibuja esa capa)")
comparar('CasoDeCarga', claves(datos['casos_de_carga']),
         ignorar=NO_VAN_AL_CSHARP['CasoDeCarga'])
comparar('CargaDistribuida',
         claves([c for caso in datos['casos_de_carga']
                 for c in caso.get('cargas_distribuidas', [])]))
_nodales = [c for caso in datos['casos_de_carga'] for c in caso.get('cargas_nodales', [])]
if _nodales:
    comparar('CargaNodal', claves(_nodales))
comparar('InfoModelo', datos['info'].keys(),
         ignorar=NO_VAN_AL_CSHARP['InfoModelo'])


# ============================================================
print("\n[2] Los campos que Unity necesita SI traen datos")
# ============================================================
# Un campo presente pero vacio es igual de malo que uno ausente: se
# dibuja "algo" y parece que funciona.
e0 = datos['elementos'][0]
check(e0.get('localX') and len(e0['localX']) == 3,
      "los elementos traen ejes locales calculados")
check(any(n['fijo'] for n in datos['nodos']),
      "hay nodos marcados como apoyo")
check(len(datos['diafragmas']) > 0, "hay diafragmas exportados")
check(len(datos['areas_tributarias']) > 0, "hay areas tributarias exportadas")

# El suelo del visor (AmbienteVisor) va en info.cota_terreno, y el suelo
# va DONDE ARRANCA LA ESTRUCTURA: la z de los apoyos mas bajos, de donde
# salen las primeras columnas. No se compara con un numero fijo (cada
# cuerpo tiene su datum), sino con lo que dicen los nodos del JSON.
if 'cota_terreno' in datos['info']:
    _cota = datos['info']['cota_terreno']
    _es_apoyo = (lambda n: not n.get('auxiliar')
                 and (n.get('fijo') or any(n.get('restricciones') or [])))
    _zs = [n['z'] for n in datos['nodos'] if _es_apoyo(n)]
    _z0 = min(_zs) if _zs else min(n['z'] for n in datos['nodos'])
    _n_ap = sum(1 for z in _zs if abs(z - _z0) <= 0.01)
    # Cuantas columnas arrancan ahi, que es como se mira en la foto.
    _porz = {n['id']: n['z'] for n in datos['nodos']}
    _cols = sum(1 for e in datos['elementos']
                if e.get('tipo') == 'columna'
                and abs(min(_porz.get(e['n1'], 1e9),
                            _porz.get(e['n2'], 1e9)) - _z0) <= 0.01)
    # 0.01 m = AjustesVista.TOLERANCIA_COTA, la del visor; las cotas de
    # los perfiles y las z de los nodos traen 2 decimales.
    check(isinstance(_cota, (int, float)) and _cota > -9000
          and abs(_cota - _z0) <= 0.01,
          "info.cota_terreno (%s m) esta donde arranca la estructura" % _cota,
          "%d apoyo(s) y %d columna(s) arrancan en z = %+.2f m"
          % (_n_ap, _cols, _z0))
    # LOS NIVELES DEL TERRENO (info.terrenos, semana05/CONTRATO.md). Tener
    # la cota en el arranque NO garantiza que todos los apoyos caigan
    # sobre el suelo: los 39 "apoyo en terreno" [0 0 1 1 1 0] de
    # Ingenieria estan 3.96 m mas arriba, porque su planta de fundaciones
    # rotula dos N.R. (-7.97 y -4.01: fundacion escalonada,
    # benchmark_3d.py:280). Desde el 18-09 el terreno viaja en NIVELES: la
    # base (esta cota, el mas bajo, sin region: todo el plano) y cada
    # TERRAZA con su region en planta. La trampa era un suelo plano sobre
    # un terreno escalonado (CLAUDE.md seccion 6): el guardia es que CADA
    # apoyo no auxiliar quede SOBRE un nivel, o sea que su z sea la de un
    # nivel cuya region lo contiene (0.01 m), y se cuenta por nivel.
    _terr = datos['info'].get('terrenos')
    if _terr is None:
        _arriba = [z for z in _zs if z - _z0 > 0.01]
        if _arriba:
            print("  [PEND] %d de %d apoyo(s) quedan SOBRE el suelo dibujado "
                  "(a %s m de la cota) y el JSON no trae info.terrenos: el "
                  "visor dibuja un solo plano"
                  % (len(_arriba), len(_zs),
                     ', '.join('%.2f' % a for a in
                               sorted({round(z - _z0, 2) for z in _arriba}))))
    else:
        comparar('NivelTerreno', claves(_terr))
        _vt = [v for t in _terr for v in (t.get('vertices') or [])]
        if _vt:
            comparar('VerticePlanta', claves(_vt))
        _bases = [t for t in _terr if not t.get('vertices')]
        _terrazas = [t for t in _terr if t.get('vertices')]
        check(len(_bases) == 1 and abs(_bases[0]['z'] - _cota) <= 0.01
              and all(t['z'] > _cota + 0.01 and len(t['vertices']) >= 3
                      for t in _terrazas),
              "info.terrenos: UNA base sin region en info.cota_terreno y "
              "cada terraza mas arriba, con su poligono",
              "; ".join('%s %+.2f m (%s)' % (t['nombre'], t['z'],
                                              '%d vertices' % len(t['vertices'])
                                              if t.get('vertices') else 'todo el plano')
                        for t in _terr))

        def _en_poligono(x, y, poli, tol=1e-6):
            """Dentro o sobre el borde (a menos de tol)."""
            dentro = False
            for k in range(len(poli)):
                (ax, ay), (bx, by) = poli[k - 1], poli[k]
                lx, ly = bx - ax, by - ay
                if (abs(lx * (y - ay) - ly * (x - ax))
                        <= tol * max((lx * lx + ly * ly) ** 0.5, 1.0)
                        and min(ax, bx) - tol <= x <= max(ax, bx) + tol
                        and min(ay, by) - tol <= y <= max(ay, by) + tol):
                    return True
                if (ay > y) != (by > y) and x < ax + (y - ay) * lx / ly:
                    dentro = not dentro
            return dentro

        _polis = [(t, [(float(v['x']), float(v['y'])) for v in t['vertices']])
                  for t in _terrazas]
        _por_nivel = {}                # (z, nombre) -> [apoyos, bajo terraza]
        _flotan, _enterrados = [], []
        for n in datos['nodos']:
            if not _es_apoyo(n):
                continue
            contienen = [_bases[0]] + [t for t, p in _polis
                                       if _en_poligono(n['x'], n['y'], p)]
            sobre = [t for t in contienen if abs(n['z'] - t['z']) <= 0.01]
            if not sobre:
                (_flotan if n['z'] > max(t['z'] for t in contienen)
                 else _enterrados).append('%s (%.2f, %.2f, %+.2f)'
                                          % (n['id'], n['x'], n['y'], n['z']))
                continue
            nivel = max(sobre, key=lambda t: t['z'])
            cuenta = _por_nivel.setdefault((nivel['z'], nivel['nombre']), [0, 0])
            cuenta[0] += 1
            # Sobre la base pero dentro de la huella de una terraza: la
            # cara de la terraza lo taparia, y el visor se la recorta
            # alrededor (HuecoDelSuelo.CalcularTerraza).
            if any(t['z'] > nivel['z'] + 0.01 for t in contienen):
                cuenta[1] += 1
        check(not _flotan and not _enterrados,
              "cada apoyo no auxiliar queda SOBRE un nivel del terreno (su z "
              "= la del nivel cuya region lo contiene, 0.01 m)",
              "; ".join('%d en %+.2f (%s)' % (c[0], z, nom)
                        for (z, nom), c in sorted(_por_nivel.items()))
              + ("; FLOTANDO: %s" % _flotan[:6] if _flotan else "")
              + ("; ENTERRADOS: %s" % _enterrados[:6] if _enterrados else ""))
        for (z, nom), c in sorted(_por_nivel.items()):
            if c[1]:
                print("  [--  ] %d de los %d apoyos de %s (%+.2f m) caen bajo la "
                      "huella de una terraza: bajan a la base, y el visor les "
                      "recorta la terraza alrededor para que se vean"
                      % (c[1], c[0], nom, z))

        # Los apoyos de una terraza que estan SOBRE estructura que baja
        # (a menos de HuecoDelSuelo.HOLGURA_TERRAZA de su eje en planta):
        # el visor los deja sobre el muro o la columna, sin tierra
        # alrededor, para no tapar lo de abajo. Se informa con la misma
        # geometria que ReunirGeometria (AmbienteVisor.cs) y la constante
        # del C#, leida de la fuente: una sola definicion.
        _src_av = open(os.path.join(os.path.dirname(CS), 'AmbienteVisor.cs'),
                       encoding='utf-8').read()
        _m = re.search(r'const\s+double\s+HOLGURA_TERRAZA\s*=\s*([0-9.]+)', _src_av)
        check(_m is not None or not _terrazas,
              "AmbienteVisor.cs dibuja las terrazas (HuecoDelSuelo.HOLGURA_TERRAZA)")
        if _m and _terrazas:
            _holg = float(_m.group(1))
            _pn = {n['id']: n for n in datos['nodos']}

            def _dist_seg(x, y, s):
                ax, ay, bx, by = s
                lx, ly = bx - ax, by - ay
                l2 = lx * lx + ly * ly
                u = 0.0 if l2 < 1e-12 else max(0.0, min(1.0, ((x - ax) * lx + (y - ay) * ly) / l2))
                return ((x - ax - u * lx) ** 2 + (y - ay - u * ly) ** 2) ** 0.5

            for t, p in _polis:
                lim = t['z'] - 0.01
                segs = [(q['x'], q['y'], q['x'], q['y'])
                        for q in datos['nodos'] if q['z'] < lim]
                for e in datos['elementos']:
                    a, b = _pn.get(e['n1']), _pn.get(e['n2'])
                    if a is None or b is None or min(a['z'], b['z']) >= lim:
                        continue
                    dl = e.get('dir_largo') or []
                    if e.get('tipo') == 'muro' and len(dl) >= 2 and e.get('largo', 0) > 0.01:
                        h = 0.5 * e['largo'] / max((dl[0] ** 2 + dl[1] ** 2) ** 0.5, 1e-9)
                        cx, cy = 0.5 * (a['x'] + b['x']), 0.5 * (a['y'] + b['y'])
                        segs.append((cx - dl[0] * h, cy - dl[1] * h, cx + dl[0] * h, cy + dl[1] * h))
                    else:
                        segs.append((a['x'], a['y'], b['x'], b['y']))
                suyos = [n for n in datos['nodos'] if _es_apoyo(n)
                         and abs(n['z'] - t['z']) <= 0.01 and _en_poligono(n['x'], n['y'], p)]
                sobre_est = [n['id'] for n in suyos
                             if segs and min(_dist_seg(n['x'], n['y'], s) for s in segs) < _holg]
                print("  [--  ] %s: %d de sus %d apoyos estan sobre estructura que "
                      "baja a la base (a menos de %.2f m, HOLGURA_TERRAZA): el visor "
                      "los deja sobre ella; los otros %d, sobre la tierra de la terraza"
                      % (t['nombre'], len(sobre_est), len(suyos), _holg,
                         len(suyos) - len(sobre_est)))
    # Nada bajo la cota = el suelo no tapa nada y HuecoDelSuelo.Calcular()
    # entra por su rama sin estampas (un cuadro de suelo, sin paredes ni
    # fondo). Si algun dia hay estructura mas abajo, el hueco la destapa:
    # por eso se informa y no se exige.
    _bajo = sum(1 for n in datos['nodos'] if n['z'] < _cota - 0.01)
    print("  [--  ] %d nodo(s) bajo la cota: %s"
          % (_bajo, "el suelo no tapa nada y el visor no cava" if not _bajo
             else "AmbienteVisor cava el hueco para que se vean"))
else:
    print("  [--  ] info.cota_terreno no viene: el visor pone el suelo en "
          "el apoyo mas bajo, con aviso en la consola")

t0 = datos['areas_tributarias'][0]
check(t0['area'] > 0, "las areas tributarias traen area")

# Los POLIGONOS son opcionales en un modelo y obligatorios en el
# del P1L2. Aca la planta no viene de una grilla: los panos son las
# caras del grafo de vigas, y recortar el poligono tributario de cada
# tramo dentro de un pano irregular todavia no esta hecho.
#
# Se declara PENDIENTE, no se aprueba por vacio: si algun dia se
# exportan poligonos, todos los chequeos de abajo se activan solos y
# vuelven a proteger contra el bug de los tamanos mezclados.
HAY_POLIGONOS = any(t['vertices'] for t in datos['areas_tributarias'])
if not HAY_POLIGONOS:
    print("  [PEND] no se exportan poligonos tributarios: el visor no dibuja")
    print("         esa capa. El area y la carga por viga SI estan.")


# ------------------------------------------------------------
# Los poligonos NO miden todos lo mismo: una viga interior toma un
# TRAPECIO de un pano (4 vertices) y un TRIANGULO del otro (3).
# Sin 'tamanos', Unity partia los vertices por division entera
# (7 / 2 = 3) y dibujaba lineas cruzadas que no existen. Este bloque
# existe para que ese bug no vuelva.
# ------------------------------------------------------------
if HAY_POLIGONOS:
    sin_tam = [t['elemento'] for t in datos['areas_tributarias']
               if t['vertices'] and not t.get('tamanos')]
    check(not sin_tam,
          "toda area tributaria declara el tamano de cada poligono",
          f"sin 'tamanos': {len(sin_tam)}" if sin_tam else "")

descuadres = [t['elemento'] for t in datos['areas_tributarias']
              if sum(t.get('tamanos', [])) != len(t['vertices'])]
check(not descuadres,
      "sum(tamanos) = cantidad de vertices",
      f"descuadrados: {descuadres[:5]}" if descuadres else "")

degenerados = [t['elemento'] for t in datos['areas_tributarias']
               if any(k < 3 for k in t.get('tamanos', []))]
check(not degenerados,
      "ningun poligono tiene menos de 3 vertices")

mal_contados = [t['elemento'] for t in datos['areas_tributarias']
                if len(t.get('tamanos', [])) != t['n_poligonos']]
check(not mal_contados,
      "len(tamanos) = n_poligonos")

# El caso que estaba roto tiene que existir de verdad en los datos; si
# no, este test estaria pasando por vacio.
# Solo tiene sentido si el exportador CONCATENA los poligonos de una
# viga (LT2). El de Ingenieria emite uno por entrada y ahi no hay nada
# que mezclar: no es un fallo, es otro formato.
CONCATENA = any(t.get('n_poligonos', 1) > 1 for t in datos['areas_tributarias'])
if HAY_POLIGONOS and not CONCATENA:
    print("  [--  ] este exportador emite un poligono por entrada: no aplica "
          "el chequeo de trapecio + triangulo")
if HAY_POLIGONOS and CONCATENA:
    mixtos = [t for t in datos['areas_tributarias']
              if len(set(t.get('tamanos', []))) > 1]
    check(len(mixtos) > 0,
          "hay vigas con poligonos de distinto tamano (el caso que fallaba)",
          f"{len(mixtos)} vigas mezclan trapecio y triangulo")

# ------------------------------------------------------------
# Muros: sin largo/espesor el visor los dibuja como columnas flacas.
# ------------------------------------------------------------
muros = [e for e in datos['elementos'] if e['tipo'] == 'muro']
if muros:
    sin_geom = [m['id'] for m in muros
                if m.get('largo', 0) <= 0 or m.get('espesor', 0) <= 0]
    check(not sin_geom,
          "los muros traen largo y espesor para dibujarlos",
          f"sin geometria: {len(sin_geom)}" if sin_geom else "")

    sin_vec = [m['id'] for m in muros
               if not m.get('vecxz') or len(m['vecxz']) < 3]
    check(not sin_vec,
          "los muros traen vecxz (orientacion de su eje fuerte)")

    # ------------------------------------------------------------
    # dir_largo: hacia donde corre el LARGO del muro en planta.
    #
    # Es lo que orienta la placa en VisorEstructura.CrearPlacaMuro. Si
    # no viene, el visor lo DEDUCE de vecxz con la regla del LT2 (el
    # largo perpendicular a vecxz, que ahi es la normal del muro), y en
    # Ingenieria vecxz ya corre A LO LARGO: el muro sale girado 90
    # grados (CLAUDE.md seccion 4, "vecxz"). Cada cuerpo lo emite con
    # SU convencion y nadie lo deduce.
    # ------------------------------------------------------------
    sin_dir = [m['id'] for m in muros
               if not m.get('dir_largo') or len(m['dir_largo']) < 2]
    check(not sin_dir,
          "los muros traen dir_largo (el visor no tiene que deducirlo)",
          f"sin dir_largo: {len(sin_dir)} ({sin_dir[:5]})" if sin_dir else "")

    # Unitario, con la cota MEDIDA contra su causa (CLAUDE.md 7.3): el
    # exportador del LT2 arma el versor dividiendo el delta en planta
    # del muro por su 'largo' declarado (modelo_lt2.py, "normal al muro
    # en planta"). Coordenadas y largo vienen del plano con 4 decimales,
    # asi que la norma se aleja de 1 hasta 1e-4/largo; los componentes
    # se redondean despues a 6 decimales, que agrega 1e-6. El muro 12
    # del LT2 da 0.999965 con largo 2.8202 (1e-4/2.8202 = 3.5e-5).
    no_unitarios = []
    for m in muros:
        dl = m.get('dir_largo') or []
        if len(dl) < 2:
            continue
        norma = (float(dl[0]) ** 2 + float(dl[1]) ** 2) ** 0.5
        cota = 1e-4 / max(float(m.get('largo', 0.0)), 1e-9) + 1e-6
        if abs(norma - 1.0) > cota:
            no_unitarios.append((m['id'], round(norma, 6), round(cota, 8)))
    check(not no_unitarios,
          "dir_largo es unitario dentro del redondeo del plano "
          "(1e-4 m sobre el largo del muro)",
          f"fuera de cota: {no_unitarios[:5]}" if no_unitarios else "")

    # La SECCION y el ELEMENTO tienen que contar lo mismo. Una seccion
    # que declara 'largo'/'espesor' y tambien 'b'/'h' los tiene que
    # llevar en la convencion del contrato: b = espesor (ancho),
    # h = largo (canto). Las dos lecturas dan el MISMO A, Iy y Iz, asi
    # que cruzarlas no se nota en ningun numero: los muros de Ingenieria
    # viajaban con b = 9.65 m y h = 0.30 m en el conjunto porque ahi se
    # dedujeron de las inercias con la regla del LT2 (la inercia grande
    # de un muro esta en Iz en el LT2 y en Iy en Ingenieria).
    cruzadas = []
    for s in datos['secciones']:
        if not (s.get('largo', 0) > 1e-3 and s.get('espesor', 0) > 1e-3):
            continue
        if not (s.get('b', 0) > 1e-3 and s.get('h', 0) > 1e-3):
            continue
        if (abs(s['b'] - s['espesor']) > 1e-3
                or abs(s['h'] - s['largo']) > 1e-3):
            cruzadas.append('%s (b %.4g/esp %.4g, h %.4g/largo %.4g)'
                            % (s['nombre'], s['b'], s['espesor'],
                               s['h'], s['largo']))
    check(not cruzadas,
          "en las secciones con los dos pares, b = espesor y h = largo",
          f"cruzadas: {cruzadas[:3]}" if cruzadas else "")


# ------------------------------------------------------------
# EL CONJUNTO NO REDIBUJA: ARRASTRA
#
# Los datos de dibujo del muro los emite cada cuerpo con su convencion
# y el conjunto solo les corre el tag (armar.PASO_DE_TAG). Si alguna vez
# el conjunto los recalculara con una regla propia, la regla seria la de
# UNO de los dos cuerpos y los muros del otro saldrian girados: es
# exactamente el error que este bloque vigila.
#
# El calce de hoy mueve los cuerpos pero NO los gira (giro_grados = 0 en
# edificios/conjunto/calce.json), asi que las direcciones tienen que
# salir IDENTICAS. Si algun dia se declara un giro, armar._remapear gira
# vecxz y dir_largo con el cuerpo (lo hace ya) y comparar por igualdad
# dejaria de tener sentido: ahi este bloque compara solo el TAMANO, que
# no gira, y lo dice.
# ------------------------------------------------------------
if muros and EDIFICIO == 'conjunto':
    print("\n[2b] Los muros del conjunto traen lo de su cuerpo de origen")
    sys.path.insert(0, rutas.edificio('conjunto'))
    import armar as _armar_conjunto          # noqa: E402

    with open(_armar_conjunto.CALCE, encoding='utf-8') as f:
        _calce = json.load(f)['edificios']

    del_conjunto = {e['id']: e for e in datos['elementos']}
    cuerpos = (datos['info'].get('cuerpos') or [])
    comparados, difieren, ausentes = 0, [], []
    for i, cuerpo in enumerate(cuerpos):
        base = (i + 1) * _armar_conjunto.PASO_DE_TAG
        giro = float((_calce.get(cuerpo) or {}).get('giro_grados', 0.0))
        DIBUJO = ('dir_largo', 'largo', 'espesor', 'vecxz')
        if abs(giro) > 1e-9:
            DIBUJO = ('largo', 'espesor')
            print(f"  [--  ] {cuerpo}: el calce lo gira {giro:+.1f} grados, "
                  f"asi que dir_largo y vecxz NO pueden salir iguales "
                  f"(los gira armar._remapear); se comparan largo y espesor")
        ruta_cuerpo = rutas.unity(cuerpo)
        if not os.path.exists(ruta_cuerpo):
            print(f"  [--  ] {cuerpo}: no hay data/unity/{cuerpo}.json con "
                  f"que comparar (exportalo y vuelve a correr)")
            continue
        with open(ruta_cuerpo, encoding='utf-8') as f:
            suyo = json.load(f)
        for m in [e for e in suyo['elementos'] if e['tipo'] == 'muro']:
            c = del_conjunto.get(m['id'] + base)
            if c is None:
                ausentes.append('%s %s -> %s' % (cuerpo, m['id'],
                                                 m['id'] + base))
                continue
            comparados += 1
            for k in DIBUJO:
                if c.get(k) != m.get(k):
                    difieren.append('%s %s %s: cuerpo %s, conjunto %s'
                                    % (cuerpo, m['id'], k, m.get(k),
                                       c.get(k)))
    check(not ausentes,
          "cada muro de cada cuerpo tiene su elemento en el conjunto",
          f"sin elemento: {ausentes[:5]}" if ausentes else "")
    check(comparados == len(muros),
          "se comparan TODOS los muros del conjunto, no una parte",
          f"{comparados} comparados de {len(muros)} muros del conjunto")
    check(not difieren,
          f"dir_largo, largo, espesor y vecxz calzan con el cuerpo de "
          f"origen ({comparados} muros)",
          '; '.join(difieren[:4]) if difieren else "")


# ============================================================
print("\n[3] Coherencia numerica de lo exportado")
# ============================================================
# w, luz y qG por poligono los emite el exportador del LT2. Sin ellos
# la conservacion w*L = q*A se comprueba en comun/verificar_tributarias.py
# a partir del modelo, que es donde aplica a cualquier edificio.
#
# El conjunto mezcla: las entradas del LT2 traen la carga y las de
# Ingenieria no. Por eso se revisan las que la traen y las otras se
# declaran PENDIENTES, en vez de saltarse el chequeo entero (lo que
# hacia antes) o de aprobarlas por vacio: en Unity esos campos quedan
# en 0 y el inspector escribiria un "w*L = q*A" de 0 = 0.
CARGA = ('w', 'luz', 'qG')
con_carga = [t for t in datos['areas_tributarias'] if all(k in t for k in CARGA)]
sin_carga = [t for t in datos['areas_tributarias'] if not all(k in t for k in CARGA)]
if con_carga:
    peor = 0.0
    for t in con_carga:
        peor = max(peor, abs(t['w'] * t['luz'] - t['qG'] * t['area']))
    check(peor < 1e-3,
          f"en el JSON se cumple w*L = q*A viga por viga "
          f"({len(con_carga)} entradas con carga)",
          f"peor error {peor:.3e} kN")
    en_cero = [t['elemento'] for t in con_carga
               if not (t['qG'] > 0 and t['w'] > 0 and t['luz'] > 0)]
    check(not en_cero,
          "las entradas que traen qG, w y luz los traen distintos de cero",
          f"en cero: {en_cero[:5]}" if en_cero else "")
if sin_carga:
    print(f"  [PEND] {len(sin_carga)} de {len(datos['areas_tributarias'])} "
          f"entradas de area tributaria no traen qG, w ni luz:")
    print("         en Unity quedan en 0 y el inspector no puede mostrar la")
    print("         carga por viga. Falta en el exportador de ese edificio; la")
    print("         conservacion se verifica en comun/verificar_tributarias.py")
if not datos['areas_tributarias']:
    print("  [--  ] no hay areas tributarias exportadas")


# ------------------------------------------------------------
# El AREA de una viga, en sus dos lugares. Ingenieria (y el conjunto)
# reparten una viga en varias entradas -- un trapecio por pano -- y
# ademas sellan el total en el elemento, 'area_tributaria'. El
# inspector de Unity (ModeloEstructural.AreaTributariaTotal) lee el
# total si esta y si no suma las entradas: tienen que ser el mismo
# numero, o el panel diria distinto segun el edificio.
#
# Cota medida contra sus dos causas:
#  - el redondeo del exportador: un valor con d decimales viene
#    redondeado a d o mas, asi que se aleja del real a lo sumo
#    0.5*10^-d. Con n entradas mas el total son n+1 redondeos. d es el
#    maximo de decimales que muestran los valores de esa viga. En
#    Ingenieria el total y las entradas salen de DOS cuentas distintas
#    del mismo pano -- el total con Lx, Ly del pano
#    (benchmark_3d.tributarias) y cada entrada con la formula del
#    cordon sobre su poligono -- redondeadas cada una a 4 decimales
#    (edificios/ingenieria/export_unity.py:219 y :488). Pueden caer a
#    los dos lados del redondeo: la viga 128 da 8.3971 contra 8.3972,
#    una unidad, que es justo la cota con n = 1.
#  - la coma flotante de esas cuentas antes de redondear: la formula
#    del cordon suma productos de coordenadas, con error de hasta
#    k * c^2 * eps (k vertices, c la mayor coordenada). Por redondeo se
#    suma 4 * k * c^2 * eps, con los k y c que trae el JSON.
def _decimales(v):
    import decimal
    exp = decimal.Decimal(repr(float(v))).normalize().as_tuple().exponent
    return max(0, -int(exp))


entradas_de = {}
for t in datos['areas_tributarias']:
    entradas_de.setdefault(t['elemento'], []).append(float(t['area']))
elem_de = {e['id']: e for e in datos['elementos']}
con_total = {eid: v for eid, v in entradas_de.items()
             if 'area_tributaria' in elem_de.get(eid, {})}
if con_total:
    _c = max([abs(float(v)) for t in datos['areas_tributarias']
              for p in t['vertices'] for v in (p['x'], p['y'])]
             + [abs(float(n[k])) for n in datos['nodos'] for k in ('x', 'y')])
    _k = max([k for t in datos['areas_tributarias'] for k in t.get('tamanos', [])] + [3])
    flotante = 4 * _k * _c * _c * sys.float_info.epsilon
    peor_q, peor_id, fuera = 0.0, None, []
    for eid, areas in con_total.items():
        total = float(elem_de[eid]['area_tributaria'])
        d = max(_decimales(a) for a in areas + [total])
        cota = (len(areas) + 1) * (0.5 * 10.0 ** -d + flotante)
        q = abs(sum(areas) - total) / cota
        if q > peor_q:
            peor_q, peor_id = q, eid
        if q > 1.0:
            fuera.append(eid)
    sin_entradas = [e['id'] for e in datos['elementos']
                    if float(e.get('area_tributaria') or 0.0) > 0.0
                    and e['id'] not in entradas_de]
    varias = sum(1 for v in con_total.values() if len(v) > 1)
    check(not fuera and not sin_entradas,
          f"suma de las entradas de cada viga = elemento.area_tributaria "
          f"({len(con_total)} vigas, {varias} con mas de una entrada)",
          f"peor error/cota {peor_q:.6f} (viga {peor_id})"
          + (f"; fuera de cota: {fuera[:5]}" if fuera else "")
          + (f"; con area y sin entradas: {sin_entradas[:5]}" if sin_entradas else ""))
elif entradas_de:
    print(f"  [--  ] los elementos no traen area_tributaria: el area de la viga "
          f"es la suma de sus entradas (a lo sumo "
          f"{max(len(v) for v in entradas_de.values())} por viga en este edificio)")

r = datos.get('resumen') or {}
if 'error_equilibrio_kN' in r:
    check(r['error_equilibrio_kN'] < 1e-6,
          "el resumen reporta equilibrio cerrado",
          f"error {r['error_equilibrio_kN']:.3e} kN")
else:
    print("  [--  ] el resumen de este edificio no trae error_equilibrio_kN; "
          "el equilibrio lo verifica comun/calcular.py")

ids = [e['id'] for e in datos['elementos']]
check(len(ids) == len(set(ids)), "los elementTag son unicos")
ids_n = [n['id'] for n in datos['nodos']]
check(len(ids_n) == len(set(ids_n)), "los nodeTag son unicos")

nodos_set = set(ids_n)
huerfanos = [e['id'] for e in datos['elementos']
             if e['n1'] not in nodos_set or e['n2'] not in nodos_set]
check(not huerfanos,
      "todos los elementos referencian nodos existentes",
      f"huerfanos: {huerfanos[:5]}" if huerfanos else "")

tags = set(ids)
trib_malas = [t['elemento'] for t in datos['areas_tributarias']
              if t['elemento'] not in tags]
check(not trib_malas,
      "toda area tributaria apunta a un elemento existente")


# ------------------------------------------------------------
# "QUE LO CARGA" COMPLETO: losa + peso propio = lo que recibe OpenSees.
# El panel daba w 15.749 kN/m (solo la losa) y el diagrama wz de G
# -27.749: los 12.000 de peso propio no se explicaban. El LT2 exporta en
# cada entrada de viga o brazo 'w_peso_propio' y 'w_total_G', leidos de
# lo que su modelo le paso a eleLoad (edificios/lt2/exportar_unity.py);
# el conjunto los copia de esas entradas. Aca se exige, entrada por
# entrada:
#   w + w_peso_propio = w_total_G
#   w_total_G = -wz de la carga repartida de G de esa barra en
#               casos_de_carga (lo que manda /analizar a OpenSees)
#
# Cota medida contra el redondeo del exportador: un valor con d decimales
# se aleja del real a lo sumo 0.5*10^-d. La suma lleva tres valores
# redondeados (3 medios escalones) y la comparacion con wz dos. Se agrega
# la coma flotante de la suma: 4*eps*|w_total_G|.
#
# Un muro no lleva estas claves (su losa y su peso propio llegan como
# cargas NODALES, no hay w repartida): se dice. Un edificio que no las
# exporta (Ingenieria) queda PEND, no FALLA ni se aprueba por vacio.
_cs_trib = clases.get('AreaTributaria', set())
check('w_peso_propio' in _cs_trib and 'w_total_G' in _cs_trib,
      "AreaTributaria del C# tiene w_peso_propio y w_total_G")

PESO = ('w_peso_propio', 'w_total_G')
con_peso = [t for t in datos['areas_tributarias'] if all(k in t for k in PESO)]
sin_peso = [t for t in datos['areas_tributarias'] if not all(k in t for k in PESO)]
wz_de_G = {}
for _caso in datos['casos_de_carga']:
    if _caso['nombre'] == 'G':
        for _c in _caso.get('cargas_distribuidas', []):
            wz_de_G[int(_c['elemento'])] = float(_c.get('wz', 0.0))
if con_peso:
    peor_suma = peor_suma_q = peor_wz = peor_wz_q = 0.0
    fuera_suma, fuera_wz, sin_wz = [], [], []
    for t in con_peso:
        w, pp, tot = float(t['w']), float(t['w_peso_propio']), float(t['w_total_G'])
        flot = 4 * sys.float_info.epsilon * abs(tot)
        d = max(_decimales(v) for v in (w, pp, tot))
        err = abs(w + pp - tot)
        q = err / (3 * 0.5 * 10.0 ** -d + flot)
        peor_suma, peor_suma_q = max(peor_suma, err), max(peor_suma_q, q)
        if q > 1.0:
            fuera_suma.append(t['elemento'])
        wz = wz_de_G.get(int(t['elemento']))
        if wz is None:
            sin_wz.append(t['elemento'])
            continue
        d = max(_decimales(tot), _decimales(wz))
        err = abs(-wz - tot)
        q = err / (2 * 0.5 * 10.0 ** -d + flot)
        peor_wz, peor_wz_q = max(peor_wz, err), max(peor_wz_q, q)
        if q > 1.0:
            fuera_wz.append(t['elemento'])
    check(not fuera_suma,
          f"w (losa) + w_peso_propio = w_total_G en cada entrada "
          f"({len(con_peso)} entradas)",
          f"peor error {peor_suma:.1e} kN/m, error/cota {peor_suma_q:.3f}"
          + (f"; fuera de cota: {fuera_suma[:5]}" if fuera_suma else ""))
    check(not fuera_wz and not sin_wz,
          "w_total_G = -wz de la carga repartida de G de la misma barra "
          "(lo que recibe OpenSees)",
          f"peor error {peor_wz:.1e} kN/m, error/cota {peor_wz_q:.3f}"
          + (f"; fuera de cota: {fuera_wz[:5]}" if fuera_wz else "")
          + (f"; sin carga repartida en G: {sin_wz[:5]}" if sin_wz else ""))
if sin_peso:
    _tipo = {e['id']: e.get('tipo', '') for e in datos['elementos']}
    _muros = [t for t in sin_peso if _tipo.get(t['elemento']) == 'muro'
              and int(t['elemento']) not in wz_de_G]
    # Solo cuenta como "muro, no aplica" si el edificio si los exporta.
    if not con_peso:
        _muros = []
    if _muros:
        print(f"  [--  ] {len(_muros)} entradas de muro sin w_peso_propio ni "
              f"w_total_G: su losa y su peso propio llegan como cargas")
        print("         nodales, no hay w repartida que separar")
    _pend = len(sin_peso) - len(_muros)
    if _pend:
        print(f"  [PEND] {_pend} de {len(datos['areas_tributarias'])} "
              f"entradas no traen w_peso_propio ni w_total_G: el panel")
        print("         no puede separar la losa del peso propio (falta en el")
        print("         exportador de ese edificio; el C# los deja en 0 y lo dice)")


# ============================================================
print("\n" + "=" * 60)
if fallos:
    print(f"FALLARON {len(fallos)}:")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("EL CONTRATO JSON <-> UNITY ESTA SANO")
print("=" * 60)
