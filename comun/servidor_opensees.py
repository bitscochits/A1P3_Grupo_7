#!/usr/bin/env python3
"""
================================================================
SERVIDOR OPENSEES <-> UNITY
================================================================
Puente entre Unity (frontend visual) y OpenSees (motor de calculo).

FLUJO:
  1. Unity modela el edificio (nodos, barras, muros, cargas)
  2. Unity envia todo como JSON via HTTP POST a este servidor
  3. Este servidor construye el modelo en OpenSees y lo resuelve
  4. Devuelve JSON con desplazamientos, reacciones y esfuerzos
  5. Unity dibuja la deformada

Como correrlo:
  python servidor_opensees.py
  -> queda escuchando en http://localhost:5000

Endpoints:
  POST /analizar   -> recibe modelo, devuelve resultados, el equilibrio
                      de cada caso y la ruta del Excel del reanalisis
  GET  /ping       -> chequear que el servidor vive

En la Semana 5 el servidor de la demo es semana05/servidor_s5.py: importa
'app' de este archivo (los dos endpoints de arriba) y le agrega /combinar
y /estados, en el mismo puerto 5000.

Unidades esperadas: m, kN, kPa (consistentes)

QUE SOPORTA
  - Barras (vigas, columnas, diagonales) de cualquier seccion y
    orientacion. La geomTransf se elige por GEOMETRIA, no por etiqueta.
  - Orientacion explicita de seccion por elemento con "vecxz"
    (necesario para muros: hacia donde apunta su eje fuerte).
  - Apoyos por grado de libertad (empotrado, rotula, deslizante...).
  - Diafragmas rigidos de piso.
  - Brazos rigidos / rigidLink (muro como columna ancha).
  - Varios casos de carga en UNA sola peticion (G, Q, EX, EY),
    resueltos sobre el mismo modelo.

QUE NO SOPORTA (todavia)
  - Analisis no lineal / Fiber Sections.
  - Elementos de area (shell). Los muros van como barra equivalente.
================================================================
"""

from flask import Flask, request, jsonify
from werkzeug.exceptions import BadRequest, HTTPException, RequestEntityTooLarge as Pesado
import argparse
import openseespy.opensees as ops
import math
import os
import re
import sys
import threading
import traceback

_AQUI = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)

# Tope al tamano de la peticion. Sin esto, un POST gigante se carga
# entero en memoria antes de que nadie lo mire.
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024   # 32 MB

# Mostrar el traceback completo en la respuesta HTTP. Apagado por
# defecto: el traceback incluye rutas ABSOLUTAS del disco, o sea el
# nombre de usuario y la estructura de carpetas de quien lo corre.
# Con esto apagado el error igual se ve completo en la consola.
MOSTRAR_TRACEBACK = os.environ.get('OPENSEES_DEBUG', '') == '1' 

# OpenSees es un SINGLETON global: ops.wipe() borra EL modelo, no "un"
# modelo. Flask atiende peticiones en hilos concurrentes, asi que dos
# /analizar simultaneos se pisarian entre si (uno hace wipe mientras el
# otro construye). Este lock serializa el acceso al motor.
_lock_opensees = threading.Lock()

# Dos /analizar seguidos escriben el MISMO libro (results/excel/
# reanalisis_<ed>.xlsx). Escribirlo fuera del lock de OpenSees deja que
# el motor atienda al siguiente mientras tanto, pero dos escrituras a la
# vez sobre el mismo archivo en Windows fallan al reemplazarlo.
_lock_excel = threading.Lock()

# Access-Control-Allow-Origin: * en todas las respuestas, para que el
# build Web de Unity (que corre en el navegador, en otro origen) pueda
# leerlas. Lo que se abre: una pagina cualquiera abierta en el navegador
# de este equipo puede LEER la respuesta, que trae la ruta absoluta del
# Excel (con el nombre de usuario). Mandar el POST ya podia sin esto.
# OPENSEES_CORS=0 lo apaga.
PERMITIR_CORS = os.environ.get('OPENSEES_CORS', '1') != '0'


# ============================================================
# CONTRATO DE ENTRADA (lo que Unity manda)
# ============================================================
# {
#   "material": {"fpc_MPa": 25, "poisson": 0.2},
#
#   "nodos": [
#       {"id": 1, "x": 0.0, "y": 0.0, "z": 0.0, "fijo": true},
#       {"id": 2, "x": 4.0, "y": 0.0, "z": 0.0,
#        "restricciones": [1,1,1,0,0,0]},      <- rotula (solo traslaciones)
#       ...
#   ]
#   "fijo": true equivale a "restricciones": [1,1,1,1,1,1] (empotrado).
#   El orden es [ux, uy, uz, rx, ry, rz]; 1 = restringido, 0 = libre.
#
#   "secciones": acepta DICCIONARIO o LISTA.
#     dict :  {"columna": {"A":0.09,"Iy":6.75e-4,"Iz":6.75e-4,"J":1.14e-3}}
#     lista:  [{"nombre":"columna","A":0.09,"Iy":6.75e-4,
#               "Iz":6.75e-4,"J":1.14e-3}, ...]
#   Usa LISTA si el JSON lo produce o consume Unity: JsonUtility no sabe
#   leer diccionarios con claves arbitrarias.
#
#   "elementos": [
#       {"id":1,"n1":1,"n2":2,"seccion":"columna","tipo":"columna"},
#       {"id":9,"n1":3,"n2":4,"seccion":"muro","tipo":"muro",
#        "vecxz":[1,0,0]},                     <- orienta el eje fuerte
#       ...
#   ],
#
#   "diafragmas": [                            <- opcional
#       {"nodo_maestro": 100, "nodos": [5,6,7,8], "perpendicular": 3}
#   ],
#   perpendicular = 3 -> diafragma horizontal (lo normal).
#   Los DOF fuera del plano del nodo maestro (uz, rx, ry) se restringen
#   solos, porque el diafragma no los toca y quedarian sueltos.
#
#   "brazos_rigidos": [                        <- opcional
#       {"maestro": 10, "esclavo": 11, "tipo": "beam"}
#   ],
#   tipo "beam" = traslaciones Y rotaciones solidarias (brazo rigido).
#   tipo "bar"  = solo traslaciones (biela).
#
#   --- CARGAS: dos formas ---
#
#   (a) UN caso (formato original):
#   "cargas_nodales":      [{"nodo":5,"fx":0,"fy":0,"fz":-44.75}],
#   "cargas_distribuidas": [{"elemento":9,"wy":0,"wz":-11.19,"wx":0}]
#
#   (b) VARIOS casos en una peticion:
#   "casos_de_carga": [
#       {"nombre":"G",
#        "cargas_distribuidas":[{"elemento":5,"wy":0,"wz":-11.19,"wx":0}]},
#       {"nombre":"EX",
#        "cargas_nodales":[{"nodo":5,"fx":50.0}]}
#   ]
#   Se resuelven todos sobre el MISMO modelo ya ensamblado.
#
# ============================================================
# CONTRATO DE RESPUESTA
# ============================================================
# Todo en LISTAS, no diccionarios: JsonUtility de Unity no sabe leer
# diccionarios con claves numericas.
#
# Con UN caso (forma (a)) la respuesta es plana:
# {
#   "ok": true,
#   "error": "",
#   "avisos": [],            <- etiquetas que no calzan con la geometria
#                               (no son errores; el modelo si se resolvio)
#   "max_desplazamiento": 6.35e-05,
#   "desplazamientos": [
#       {"id":5,"ux":0.0,"uy":0.0,"uz":-6.35e-05,
#        "rx":0.0,"ry":0.0,"rz":0.0}, ...
#   ],
#   "reacciones": [          <- solo nodos con alguna restriccion
#       {"id":1,"fx":0.0,"fy":0.0,"fz":44.75,
#        "mx":0.0,"my":0.0,"mz":0.0}, ...
#   ],
#   "fuerzas_elementos": [        <- EJES LOCALES de cada barra
#       {"id":1,"f":[N_i,Vy_i,Vz_i,T_i,My_i,Mz_i,
#                    N_j,Vy_j,Vz_j,T_j,My_j,Mz_j]}, ...
#   ]
# }
#
# Con VARIOS casos (forma (b)) se agrega "casos", una LISTA:
# {
#   "ok": true, "error": "", "avisos": [],
#   "casos": [
#       {"nombre":"G","max_desplazamiento":...,"desplazamientos":[...],
#        "reacciones":[...],"fuerzas_elementos":[...],
#        "equilibrio": {"aplicada_kN":[3], "reaccion_kN":[3],
#                       "error_kN":[3], "cargas_sin_convertir":0,
#                       "nodos_en_diafragma":216, "confiable":true}},
#       {"nombre":"EX", ...}
#   ]
# }
# "equilibrio" es calcular.equilibrio() tal cual: separa las reacciones
# POR GRADO DE LIBERTAD. Sumar la lista "reacciones" entera dobla el
# corte basal (los nodos de diafragma traen la fuerza de la restriccion,
# que es interna). Solo viene en la forma multi-caso; la plana no cambia.
#
# /analizar agrega en la raiz (no construir_y_resolver):
#   "excel":       ruta ABSOLUTA de results/excel/reanalisis_<ed>.xlsx, o null
#   "excel_error": por que no hay Excel, o null
#
# "max_desplazamiento" es la mayor COMPONENTE |ux|, |uy| o |uz| de algun
# nodo (el anexo de Semana 4 usa la norma).
#
# Unidades de salida: m (desplazamientos), kN y kN*m (esfuerzos).


# ============================================================
# UTILIDADES
# ============================================================
def normalizar_secciones(secciones):
    """
    Acepta 'secciones' como DICCIONARIO o como LISTA y devuelve siempre
    un diccionario {nombre: {A, Iy, Iz, J}}.

        dict:  {"columna": {"A":..., "Iy":..., "Iz":..., "J":...}}
        lista: [{"nombre":"columna", "A":..., "Iy":..., "Iz":..., "J":...}]

    La forma de LISTA existe por Unity: JsonUtility no sabe leer ni
    escribir diccionarios con claves arbitrarias, asi que del lado de
    Unity todo tiene que ser lista. Sin esto habria que armar el JSON a
    mano con StringBuilder (que es justo de donde salio el bug de la
    coma decimal) o instalar Newtonsoft.
    """
    if isinstance(secciones, dict):
        return secciones

    if not isinstance(secciones, list):
        raise ValueError("'secciones' debe ser un diccionario o una lista")

    out = {}
    for i, s in enumerate(secciones):
        nombre = s.get('nombre')
        if not nombre:
            raise ValueError(f"secciones[{i}] no tiene 'nombre'. En la forma "
                             f"de lista cada seccion debe traerlo.")
        if nombre in out:
            raise ValueError(f"La seccion '{nombre}' esta definida dos veces")
        faltan = [k for k in ('A', 'Iy', 'Iz', 'J') if k not in s]
        if faltan:
            raise ValueError(f"La seccion '{nombre}' no trae {faltan}")
        out[nombre] = {k: float(s[k]) for k in ('A', 'Iy', 'Iz', 'J')}
        # E y G POR SECCION, opcionales. Sin esto no se puede tener
        # acero y hormigon en el mismo modelo: el voladizo metalico del
        # oriente son tubos con E = 200 GPa contra los 24.9 del
        # hormigon, y calcularlo con el E global lo deja 8 veces mas
        # flexible de lo que es.
        for k in ('E', 'G'):
            if k in s and s[k]:
                out[nombre][k] = float(s[k])
    return out


# ============================================================
# CONSTRUCCION DEL MODELO
# ============================================================
def construir_modelo(data):
    """
    Ensambla el modelo completo en OpenSees (nodos, apoyos, elementos,
    diafragmas, brazos rigidos). NO aplica cargas ni resuelve.

    Devuelve (coords, avisos, nodos_restringidos).
    """
    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 6)

    # --- Material ---
    mat = data.get('material', {})
    fpc = mat.get('fpc_MPa', 25.0)
    poisson = mat.get('poisson', 0.2)
    Ec = 4700.0 * math.sqrt(fpc) * 1000.0    # kPa
    Gc = Ec / (2.0 * (1.0 + poisson))
    ops.uniaxialMaterial('Elastic', 1, Ec)

    avisos = []

    # --- Nodos ---
    coords = {}
    for nd in data['nodos']:
        nid = int(nd['id'])
        xyz = (float(nd['x']), float(nd['y']), float(nd['z']))
        coords[nid] = xyz
        ops.node(nid, *xyz)

    # --- Apoyos ---
    # "fijo": true  -> empotrado.  "restricciones": [6 enteros] -> a medida.
    nodos_restringidos = {}
    for nd in data['nodos']:
        nid = int(nd['id'])
        # Lista VACIA = ausente. JsonUtility de Unity serializa SIEMPRE
        # todos los campos, asi que un nodo sin restricciones explicitas
        # llega como "restricciones": []. Sin esto, reventaria.
        r = nd.get('restricciones') or None
        if r is None:
            r = [1, 1, 1, 1, 1, 1] if nd.get('fijo', False) else None
        if r is None:
            continue
        if len(r) != 6:
            raise ValueError(f"Nodo {nid}: 'restricciones' debe tener 6 "
                             f"valores [ux,uy,uz,rx,ry,rz], vinieron {len(r)}")
        r = [int(v) for v in r]
        if any(v not in (0, 1) for v in r):
            raise ValueError(f"Nodo {nid}: 'restricciones' solo acepta 0 o 1")
        if any(r):
            ops.fix(nid, *r)
            nodos_restringidos[nid] = r

    # --- Elementos ---
    # La transformacion geometrica se elige por la GEOMETRIA del
    # elemento, no por su etiqueta 'tipo'. Antes era:
    #     transf = 1 if el['tipo'] == 'columna' else 2
    # y eso reventaba con cualquier elemento vertical que no se llamara
    # exactamente "columna" (un muro, por ejemplo): recibia
    # vecxz=(0,0,1), PARALELO a su eje, y OpenSees moria con
    # "Error initializing coordinate transformation".
    sec = normalizar_secciones(data['secciones'])
    transfs = {}          # vecxz -> tag, para no redefinir transformaciones
    prox_transf = [1]

    def tag_transf(vecxz):
        clave = tuple(round(v, 9) for v in vecxz)
        if clave not in transfs:
            t = prox_transf[0]
            prox_transf[0] += 1
            ops.geomTransf('Linear', t, *clave)
            transfs[clave] = t
        return transfs[clave]

    for el in data['elementos']:
        eid = int(el['id'])
        n1, n2 = int(el['n1']), int(el['n2'])

        if n1 not in coords or n2 not in coords:
            raise ValueError(f"Elemento {eid} referencia un nodo inexistente "
                             f"(n1={n1}, n2={n2})")

        p1, p2 = coords[n1], coords[n2]
        dx, dy, dz = (p2[0]-p1[0], p2[1]-p1[1], p2[2]-p1[2])
        L = math.sqrt(dx*dx + dy*dy + dz*dz)
        if L < 1e-9:
            raise ValueError(f"Elemento {eid} tiene largo cero "
                             f"(nodos {n1} y {n2} coinciden)")

        proy_horiz = math.sqrt(dx*dx + dy*dy)
        es_vertical = (proy_horiz / L) < 1e-6

        # vecxz define el plano local x-z y NO puede ser paralelo al eje
        # del elemento. Para un vertical, (0,0,1) lo es -> se usa (1,0,0).
        # Para cualquier otro, (0,0,1) sirve y ademas deja el eje local z
        # en el plano vertical, que es lo que queremos para que la
        # gravedad flecte "hacia abajo" en ejes locales.
        # Idem: "vecxz": [] desde Unity significa "sin override".
        vecxz = el.get('vecxz') or None
        if vecxz is not None:
            if len(vecxz) != 3:
                raise ValueError(f"Elemento {eid}: 'vecxz' debe tener 3 "
                                 f"componentes, vinieron {len(vecxz)}")
            vecxz = (float(vecxz[0]), float(vecxz[1]), float(vecxz[2]))
            norma = math.sqrt(sum(v*v for v in vecxz))
            if norma < 1e-9:
                raise ValueError(f"Elemento {eid}: vecxz es el vector nulo")
            cx = dy*vecxz[2] - dz*vecxz[1]
            cy = dz*vecxz[0] - dx*vecxz[2]
            cz = dx*vecxz[1] - dy*vecxz[0]
            if math.sqrt(cx*cx + cy*cy + cz*cz) / (L * norma) < 1e-6:
                raise ValueError(
                    f"Elemento {eid}: el vecxz {vecxz} es paralelo al eje del "
                    f"elemento. Elige otro (para un elemento vertical usa "
                    f"(1,0,0); para uno horizontal, (0,0,1)).")
        else:
            vecxz = (1.0, 0.0, 0.0) if es_vertical else (0.0, 0.0, 1.0)

        transf = tag_transf(vecxz)

        # Cruce de inercias: SOLO para elementos no verticales.
        # Con vecxz=(0,0,1) el eje local z queda en el plano vertical, asi
        # que la flexion por gravedad es alrededor del eje local y -> hay
        # que poner la inercia de gravedad en la posicion Iy.
        # En un elemento vertical no existe "flexion por gravedad": las
        # inercias van derechas y la seccion se orienta con vecxz.
        if el['seccion'] not in sec:
            raise ValueError(f"Elemento {eid} usa la seccion "
                             f"'{el['seccion']}', que no esta definida")
        s_el = sec[el['seccion']]
        if es_vertical:
            Iy_pass, Iz_pass = s_el['Iy'], s_el['Iz']
        else:
            Iy_pass = s_el['Iz']   # inercia de gravedad -> posicion Iy
            Iz_pass = s_el['Iy']   # inercia lateral    -> posicion Iz

        # Aviso si la etiqueta no calza con la geometria: no es error
        # (manda la geometria), pero delata datos mal importados del DXF.
        tipo = el.get('tipo', '')
        if tipo == 'columna' and not es_vertical:
            avisos.append(f"Elemento {eid} dice tipo='columna' pero NO es "
                          f"vertical; se trato como barra inclinada/horizontal.")
        elif tipo.startswith('viga') and es_vertical:
            avisos.append(f"Elemento {eid} dice tipo='{tipo}' pero ES "
                          f"vertical; se trato como elemento vertical.")

        # La seccion puede traer su propio material (ver
        # normalizar_secciones); si no, usa el del modelo.
        E_el = s_el.get('E', Ec)
        G_el = s_el.get('G', Gc if 'E' not in s_el
                        else E_el / (2.0 * (1.0 + 0.3)))
        ops.element('elasticBeamColumn', eid, n1, n2,
                    s_el['A'], E_el, G_el, s_el['J'],
                    Iy_pass, Iz_pass, transf)

    # --- Brazos rigidos (rigidLink) ---
    # Es el mecanismo para modelar un muro como "columna ancha": la barra
    # equivalente va en el eje del muro, y las vigas que llegan a sus
    # CARAS se conectan con brazos rigidos. Sin esto el muro se comporta
    # como si tuviera espesor cero.
    for br in data.get('brazos_rigidos', []):
        m, e = int(br['maestro']), int(br['esclavo'])
        if m not in coords or e not in coords:
            raise ValueError(f"Brazo rigido {m}->{e} referencia un nodo "
                             f"inexistente")
        if m == e:
            raise ValueError(f"Brazo rigido invalido: maestro y esclavo son "
                             f"el mismo nodo ({m})")
        tipo_br = br.get('tipo', 'beam')
        if tipo_br not in ('beam', 'bar'):
            raise ValueError(f"Brazo rigido {m}->{e}: tipo debe ser "
                             f"'beam' o 'bar', vino '{tipo_br}'")
        ops.rigidLink(tipo_br, m, e)

    # --- Diafragmas rigidos ---
    for i, dia in enumerate(data.get('diafragmas', [])):
        maestro = int(dia['nodo_maestro'])
        esclavos = [int(n) for n in dia['nodos'] if int(n) != maestro]
        perp = int(dia.get('perpendicular', 3))

        if maestro not in coords:
            raise ValueError(f"Diafragma {i}: el nodo maestro {maestro} no "
                             f"existe. Crealo en 'nodos' (normalmente en el "
                             f"centro de masa del piso).")
        faltan = [n for n in esclavos if n not in coords]
        if faltan:
            raise ValueError(f"Diafragma {i}: nodos inexistentes {faltan}")
        if not esclavos:
            raise ValueError(f"Diafragma {i}: no tiene nodos esclavos")
        if perp not in (1, 2, 3):
            raise ValueError(f"Diafragma {i}: 'perpendicular' debe ser "
                             f"1, 2 o 3 (vino {perp})")

        # Todos los nodos del diafragma deben estar en el mismo plano.
        ejes = {1: 0, 2: 1, 3: 2}[perp]
        cota_m = coords[maestro][ejes]
        fuera = [n for n in esclavos
                 if abs(coords[n][ejes] - cota_m) > 1e-6]
        if fuera:
            raise ValueError(
                f"Diafragma {i}: los nodos {fuera} no estan en el mismo plano "
                f"que el maestro {maestro}. Un diafragma rigido exige que "
                f"todos compartan la cota.")

        ops.rigidDiaphragm(perp, maestro, *esclavos)

        # El diafragma solo ata los DOF EN SU PLANO (para perp=3: ux, uy,
        # rz). Los de fuera del plano (uz, rx, ry) del nodo maestro quedan
        # sueltos: si el maestro no tiene elementos conectados, la matriz
        # queda singular. Se restringen, salvo que el usuario ya los haya
        # restringido a mano.
        if maestro not in nodos_restringidos:
            fuera_plano = {3: [0, 0, 1, 1, 1, 0],
                           2: [0, 1, 0, 1, 0, 1],
                           1: [1, 0, 0, 0, 1, 1]}[perp]
            ops.fix(maestro, *fuera_plano)
            nodos_restringidos[maestro] = fuera_plano
            avisos.append(
                f"Diafragma {i}: se restringieron los DOF fuera del plano del "
                f"nodo maestro {maestro} para evitar una matriz singular.")

    return coords, avisos, nodos_restringidos


# ============================================================
# CARGAS Y SOLUCION
# ============================================================
def aplicar_cargas(caso, tag, nodos_validos=None, elementos_validos=None):
    """
    Define el patron de carga 'tag' con las cargas del caso.

    Valida que cada carga apunte a algo que existe. Sin esto, OpenSees
    solo emite un WARNING por consola y DESCARTA la carga en silencio:
    el analisis "funciona" pero con menos carga de la que crees, y el
    equilibrio cierra igual porque la carga descartada nunca entro.
    Editando el modelo en Unity (borrar una barra deja su carga
    huerfana) eso pasaria constantemente.
    """
    nombre = caso.get('nombre', 'el caso')

    ops.timeSeries('Linear', tag)
    ops.pattern('Plain', tag, tag)

    for c in caso.get('cargas_nodales', []):
        if nodos_validos is not None and int(c['nodo']) not in nodos_validos:
            raise ValueError(
                f"En '{nombre}': hay una carga sobre el nodo {c['nodo']}, "
                f"que no existe. Si lo borraste, borra tambien su carga.")

    for c in caso.get('cargas_distribuidas', []):
        if elementos_validos is not None and int(c['elemento']) not in elementos_validos:
            raise ValueError(
                f"En '{nombre}': hay una carga sobre el elemento "
                f"{c['elemento']}, que no existe. Si lo borraste, borra "
                f"tambien su carga.")

    for c in caso.get('cargas_nodales', []):
        ops.load(int(c['nodo']),
                 float(c.get('fx', 0.0)), float(c.get('fy', 0.0)),
                 float(c.get('fz', 0.0)), float(c.get('mx', 0.0)),
                 float(c.get('my', 0.0)), float(c.get('mz', 0.0)))

    for c in caso.get('cargas_distribuidas', []):
        ops.eleLoad('-ele', int(c['elemento']), '-type', '-beamUniform',
                    float(c.get('wy', 0.0)), float(c.get('wz', 0.0)),
                    float(c.get('wx', 0.0)))


def resolver_caso():
    """Analisis estatico lineal de un paso. Devuelve 0 si convergio."""
    ops.wipeAnalysis()
    ops.system('BandGeneral')      # mas robusto que BandSPD con eleLoad
    ops.numberer('RCM')
    ops.constraints('Transformation')   # necesario para diafragmas/rigidLink
    ops.integrator('LoadControl', 1.0)
    ops.algorithm('Linear')
    ops.analysis('Static')
    ok = ops.analyze(1)
    ops.reactions()
    return ok


def extraer_resultados(data, nodos_restringidos):
    """Lee desplazamientos, reacciones y esfuerzos del estado actual."""
    res = {
        'desplazamientos': [],
        'reacciones': [],
        'fuerzas_elementos': [],
    }
    max_disp = 0.0

    for nd in data['nodos']:
        nid = int(nd['id'])
        d = [ops.nodeDisp(nid, i) for i in range(1, 7)]
        res['desplazamientos'].append({
            'id': nid,
            'ux': round(d[0], 8), 'uy': round(d[1], 8), 'uz': round(d[2], 8),
            'rx': round(d[3], 8), 'ry': round(d[4], 8), 'rz': round(d[5], 8),
        })
        m = max(abs(d[0]), abs(d[1]), abs(d[2]))
        if m > max_disp:
            max_disp = m

        if nid in nodos_restringidos:
            r = [ops.nodeReaction(nid, i) for i in range(1, 7)]
            res['reacciones'].append({
                'id': nid,
                'fx': round(r[0], 4), 'fy': round(r[1], 4), 'fz': round(r[2], 4),
                'mx': round(r[3], 4), 'my': round(r[4], 4), 'mz': round(r[5], 4),
            })

    for el in data['elementos']:
        eid = int(el['id'])
        # localForce, NO eleForce: eleForce() devuelve las fuerzas en ejes
        # GLOBALES. Para una viga que corre en Y su momento de gravedad
        # saldria en la casilla Mx global -- se leeria como torsion y el
        # diagrama de momentos quedaria sin sentido.
        f = ops.eleResponse(eid, 'localForce')
        res['fuerzas_elementos'].append({
            'id': eid,
            'f': [round(v, 4) for v in f],
        })

    res['max_desplazamiento'] = round(max_disp, 8)
    return res


def equilibrio_del_caso(data, caso, r, avisos):
    """
    calcular.equilibrio(data, caso, r) tal cual, o None con un aviso si
    revienta: un chequeo que falla no puede tumbar un analisis que si se
    resolvio.

    El import va ACA ADENTRO porque calcular.py importa este archivo
    (import servidor_opensees as motor): arriba del todo seria un ciclo.
    """
    if _AQUI not in sys.path:
        sys.path.insert(0, _AQUI)
    try:
        import calcular
        return calcular.equilibrio(data, caso, r)
    except Exception as e:
        avisos.append("No se pudo calcular el equilibrio de '%s': %s"
                      % (caso.get('nombre', '?'), e))
        return None


def construir_y_resolver(data):
    """
    Construye el modelo UNA vez y resuelve todos los casos de carga
    sobre el.
    """
    coords, avisos, restringidos = construir_modelo(data)

    # Normalizar: siempre trabajamos con una lista de casos.
    casos = data.get('casos_de_carga')
    multi = casos is not None
    if not multi:
        casos = [{
            'nombre': data.get('nombre_caso', 'unico'),
            'cargas_nodales': data.get('cargas_nodales', []),
            'cargas_distribuidas': data.get('cargas_distribuidas', []),
        }]

    nodos_validos = set(coords)
    elementos_validos = {int(e['id']) for e in data['elementos']}

    resultados_casos = []
    todo_ok = True
    tag_previo = None

    for i, caso in enumerate(casos):
        tag = 100 + i
        nombre = caso.get('nombre', f'caso_{i+1}')

        # Volver al estado inicial antes de cada caso. Sin esto:
        #  - reset() : los desplazamientos del caso anterior se acumulan.
        #  - setTime(0): el timeSeries Linear escala por el tiempo, y cada
        #    analyze(1) lo incrementa. En el 2do caso el factor seria 2.
        #  - remove(loadPattern): si no, las cargas del caso anterior
        #    siguen actuando y se superponen.
        if tag_previo is not None:
            ops.remove('loadPattern', tag_previo)
        ops.reset()
        ops.setTime(0.0)

        aplicar_cargas(caso, tag, nodos_validos, elementos_validos)
        tag_previo = tag

        ok = resolver_caso()
        if ok != 0:
            todo_ok = False

        r = extraer_resultados(data, restringidos)
        r['nombre'] = nombre
        r['ok'] = (ok == 0)
        resultados_casos.append(r)

    salida = {'ok': todo_ok, 'error': '', 'avisos': avisos}

    if multi:
        # El equilibrio de cada caso, con la regla por grado de libertad
        # de calcular.equilibrio. Antes Unity sumaba la lista de
        # reacciones entera y en el LT2 EX le daba Fx = -7266.13 kN con
        # 3633.06 aplicados: parecia un modelo roto y era la suma mal
        # hecha. Asi hay una sola definicion y Unity solo la muestra.
        for caso, r in zip(casos, resultados_casos):
            r['equilibrio'] = equilibrio_del_caso(data, caso, r, avisos)
        salida['casos'] = resultados_casos
    else:
        # Forma plana original, para no romper el cliente existente.
        r = resultados_casos[0]
        salida.update({
            'max_desplazamiento': r['max_desplazamiento'],
            'desplazamientos': r['desplazamientos'],
            'reacciones': r['reacciones'],
            'fuerzas_elementos': r['fuerzas_elementos'],
        })

    return salida


# ============================================================
# ENDPOINTS HTTP
# ============================================================

@app.route('/ping', methods=['GET'])
def ping():
    """Chequeo de vida. Unity puede llamar esto para ver si el server esta."""
    return jsonify({'estado': 'vivo', 'motor': 'OpenSees'})


@app.after_request
def _cabeceras_cors(respuesta):
    """Ver PERMITIR_CORS. Content-Type en Allow-Headers porque un POST
    con application/json hace que el navegador pregunte antes (OPTIONS)."""
    if PERMITIR_CORS:
        respuesta.headers['Access-Control-Allow-Origin'] = '*'
        respuesta.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        respuesta.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return respuesta


def edificio_del_modelo(data, del_pedido=None):
    """
    El nombre que lleva el libro: info.edificio si viene no vacio; si no,
    el parametro ?edificio= del pedido; si no, 'modelo'.

    Va a un nombre de archivo, asi que solo se aceptan letras, digitos,
    '_' y '-'. Un "../../algo" venido por la red escribiria fuera de
    results/excel/; en vez de limpiarlo a medias se descarta entero.
    JsonUtility manda info.edificio = "" cuando el JSON no lo traia.
    """
    info = data.get('info') if isinstance(data, dict) else None
    for candidato in ((info or {}).get('edificio') if isinstance(info, dict) else None,
                      del_pedido):
        if isinstance(candidato, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,40}',
                                                        candidato.strip()):
            return candidato.strip()
    return 'modelo'


def modelo_como_lista(data):
    """
    El modelo con 'secciones' en la forma de LISTA, la que manda Unity y
    la que declara el contrato del Excel (semana05/CONTRATO.md, seccion
    c). El servidor acepta tambien el diccionario (normalizar_secciones),
    y un modelo que se resolvio no puede quedarse sin libro por eso: con
    el diccionario el escritor fallaba con "'str' object has no attribute
    'get'" (test_servidor.py, bloque 10). Copia superficial: 'data' no se
    toca.
    """
    secciones = data.get('secciones')
    if not isinstance(secciones, dict):
        return data
    copia = dict(data)
    copia['secciones'] = [dict(s, nombre=nombre) for nombre, s in secciones.items()]
    return copia


def escribir_excel(data, resultados, edificio):
    """
    (ruta, None) si escribio results/excel/reanalisis_<edificio>.xlsx, o
    (None, motivo) si no.

    Atrapa BaseException y no solo Exception: el escritor carga codigo
    del laboratorio que corta con SystemExit, y un SystemExit dentro de
    un hilo de Flask mataria la peticion sin respuesta. Un Excel que no
    se pudo escribir NUNCA rompe /analizar: el analisis ya esta hecho y
    Unity lo necesita igual.
    """
    try:
        if _AQUI not in sys.path:
            sys.path.insert(0, _AQUI)
        import rutas
        import excel                     # comun/excel.py (paquete P1)
        with _lock_excel:
            ruta = excel.escribir_libro_reanalisis(
                modelo_como_lista(data), resultados, rutas.excel_reanalisis(edificio))
        return os.path.abspath(str(ruta)), None
    except BaseException as e:           # noqa: B902 -- ver docstring
        if isinstance(e, KeyboardInterrupt):
            raise
        traceback.print_exc()
        return None, '%s: %s' % (type(e).__name__, e)


@app.route('/analizar', methods=['POST'])
def analizar():
    """
    Recibe el modelo de Unity, lo resuelve, devuelve resultados, y deja
    el Excel del reanalisis en results/excel/.

    Errores: HTTP 400 si el pedido es invalido (JSON roto, falta una
    clave, una seccion inexistente: lo que se arregla cambiando el
    modelo) y 500 si es una falla nuestra. Siempre con cuerpo JSON
    {"ok": false, "error": ...}: Unity lo lee tambien en ProtocolError.
    """
    try:
        data = request.get_json(force=True)
        if not isinstance(data, dict):
            raise ValueError('el cuerpo tiene que ser un objeto JSON con el modelo')
        with _lock_opensees:
            resultados = construir_y_resolver(data)
    except (BadRequest, Pesado, ValueError, KeyError, TypeError) as e:
        return _respuesta_de_error(e, 400)
    except Exception as e:
        return _respuesta_de_error(e, 500)

    edificio = edificio_del_modelo(data, request.args.get('edificio'))
    resultados['excel'], resultados['excel_error'] = escribir_excel(
        data, resultados, edificio)
    return jsonify(resultados)


def _respuesta_de_error(e, codigo):
    # El detalle completo siempre queda en la consola del servidor.
    traceback.print_exc()
    texto = str(e)
    if isinstance(e, KeyError):
        texto = 'falta la clave %s en el modelo' % texto
    elif isinstance(e, BadRequest):
        texto = 'el cuerpo no es JSON valido: %s' % (e.description or texto)
    elif isinstance(e, Pesado):
        # RequestEntityTooLarge NO hereda de BadRequest: sin esto, un
        # modelo por sobre MAX_CONTENT_LENGTH salia como HTTP 500 ("falla
        # nuestra") cuando es el pedido el que hay que achicar.
        texto = ('el modelo pesa mas de %.3g MB (MAX_CONTENT_LENGTH)'
                 % (app.config['MAX_CONTENT_LENGTH'] / (1024 * 1024)))
    salida = {'ok': False, 'error': texto, 'avisos': [],
              'excel': None, 'excel_error': 'no se resolvio el modelo'}
    if MOSTRAR_TRACEBACK:
        salida['traceback'] = traceback.format_exc()
    return jsonify(salida), codigo


@app.errorhandler(HTTPException)
def _error_http_en_json(e):
    """
    Los errores que Flask arma solo, sin pasar por una ruta: 404 (ruta mal
    escrita) y 405 (un GET a /analizar o /combinar). Sin esto salen como
    pagina HTML, y el contrato (semana05/CONTRATO.md, seccion 3) dice que TODA
    respuesta es JSON: Unity lee el cuerpo tambien en ProtocolError y con
    HTML mostraria "JSON ilegible" en vez del motivo. Las redirecciones
    del enrutador (RequestRedirect, codigo 3xx) se dejan pasar tal cual.
    """
    if e.code is None or e.code < 400:
        return e
    return jsonify({'ok': False,
                    'error': '%d %s: %s' % (e.code, e.name, e.description)}), e.code


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description="Servidor OpenSees <-> Unity")
    ap.add_argument('--lan', action='store_true',
                    help="Escuchar en TODA la red local, no solo en este "
                         "equipo. Hace falta para conectar desde el celular "
                         "(AR). No lo uses en una red publica.")
    ap.add_argument('--puerto', type=int, default=5000)
    args = ap.parse_args()

    # Por defecto 127.0.0.1: solo este equipo. Unity corre en la misma
    # maquina, asi que no hace falta mas.
    # Antes era '0.0.0.0' (todas las interfaces): conectado al WiFi de
    # la universidad, cualquiera en esa red podia mandarle peticiones.
    # No podria robar nada -el servidor no ejecuta codigo, y el unico
    # archivo que escribe es results/excel/reanalisis_<ed>.xlsx, con un
    # nombre que edificio_del_modelo limpia- pero si tumbarlo con un
    # modelo enorme.
    host = '0.0.0.0' if args.lan else '127.0.0.1'

    print("=" * 58)
    print("  SERVIDOR OPENSEES <-> UNITY")
    print("=" * 58)
    print(f"  Escuchando en: http://{'0.0.0.0' if args.lan else 'localhost'}"
          f":{args.puerto}")
    if args.lan:
        print("  *** ABIERTO A TODA LA RED LOCAL (--lan) ***")
        print("  Cualquiera en este WiFi puede mandarle peticiones.")
    else:
        print("  Solo accesible desde este equipo.")
        print("  Para conectar desde el celular (AR): --lan")
    print("  POST /analizar  -> enviar modelo, recibir deformaciones,")
    print("                     equilibrio por caso y results/excel/reanalisis_<ed>.xlsx")
    print("  GET  /ping      -> chequear conexion")
    print("=" * 58)
    app.run(host=host, port=args.puerto, debug=False)
