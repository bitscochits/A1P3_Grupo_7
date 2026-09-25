# -*- coding: utf-8 -*-
r"""
================================================================
 semana05_lab/verificar_instantanea.py
   LOS SLIDERS INSTANTANEOS, CONTRA PYTHON
================================================================
 El LAB de la Semana 5 pide que los sliders de los casos base
 actualicen AL INSTANTE la deformada, los resultados y el punto P-M.
 unity/Assets/Scripts/VisorSemana05.Instantanea.cs lo hace combinando
 en Unity los cuatro casos base que ya trae semana04.json, sin pedirle
 nada al servidor.

 Este script comprueba que esa combinacion da lo mismo que Python, por
 DOS caminos, y conviene tener claro que prueba cada uno:

   [3] LA REPLICA.  Repite EN PYTHON, paso a paso y con la misma
       aritmetica de 32 bits, lo que hace el C# -- retabular a la malla
       comun, escalar y sumar, rehacer la demanda -- y lo compara contra
       semana05/superposicion.caso_combinado(), que arma el caso con las
       funciones del exportador de la Semana 4 y ya esta verificado por
       cuatro vias en semana05/verificar_superposicion.py. Prueba que el
       ALGORITMO es correcto, sobre 10 juegos de lambdas, incluidos los
       feos: negativos, ceros, un solo caso, y los tres estados E1..E3.
       No prueba que el C# ejecute ese algoritmo.

   [4] EL REGISTRO (--registro <registro.txt>).  CapturaSemana05 mueve
       los sliders en la app real (paso D2) y deja en registro.txt los
       numeros que Unity CALCULO Y DIBUJO -- float de 32 bits, formato
       G9 --: version, milisegundos, desplazamientos del nodo de
       control, extremos de las barras de control, demandas y conteos.
       Aca se cruzan con Python. Esto si prueba lo que hace el C#, y de
       paso que el SEGUNDO movimiento del slider tambien reemplaza el
       caso (el error que hubo con tipo = "combinacion").

   python semana05_lab/verificar_instantanea.py lt2
   python semana05_lab/verificar_instantanea.py lt2 --registro semana05/capturas/registro.txt
   python semana05_lab/verificar_instantanea.py lt2 --casos 3

 ----------------------------------------------------------------
 DE DONDE SALEN LAS COTAS
 ----------------------------------------------------------------
 No se eligen a ojo: cada termino tiene una causa medible.

 1. El REDONDEO DEL ANEXO.  El C# suma valores que semana04.json YA
    escribio redondeados (4 decimales las fuerzas, 8 los
    desplazamientos), y Python redondea al final. Son dos caminos
    distintos hasta el mismo numero:

      sum(lambda * redondeo(v))   contra   redondeo(sum(lambda * v))

    El error de cada termino es medio ultimo decimal escalado por su
    lambda, mas el redondeo final:  R * (sum|lambda| + 1).

 2. LA ARITMETICA DE 32 BITS.  Unity guarda y opera en float
    (JsonUtility, Mathf): cada operacion redondea a 2^-24 = 6e-8
    relativo. Por cada termino lambda*v hay hasta 7 redondeos (el valor
    al cargarse, tres al interpolarlo a la malla comun, el lambda, el
    producto y la suma), mas uno por cada suma parcial, y M = hypot
    agrega cuatro: menos de 14 en total. Se toma K_F32 = 16 y se
    multiplica por la ESCALA de la suma, sum|lambda_c| * |v_c|, que la
    replica calcula junto con el valor:  K_F32 * 2^-24 * escala.

    No es despreciable: en P = 5400 kN son 5e-3 kN, cien veces el
    redondeo del anexo. Sin este termino el registro de Unity se sale de
    la cota entre 1.4 y 6 veces sin que nadie se haya equivocado.

 3. Mn sale de interpolar en la curva P-M: su error es el de P por la
    pendiente de la curva, que en la nariz es del orden de 0.05 kN m
    por kN. Se acota con la pendiente maxima medida.

 4. "Instantaneo" tambien se mide: la combinacion tiene que caber en un
    cuadro de pantalla a 60 Hz (16.7 ms). Mas que eso ya no es
    instantaneo, y se dice.
================================================================
"""
from __future__ import annotations

import io
import json
import math
import os
import re
import struct
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_AQUI), 'comun'))
import rutas                                   # noqa: E402
rutas.entrar(__file__, os.path.join(rutas.RAIZ, 'semana03'),
             os.path.join(rutas.RAIZ, 'semana04'), os.path.join(rutas.RAIZ, 'semana05'))

import superposicion as sup                    # noqa: E402

CASOS = ('G', 'Q', 'EX', 'EY')
MAGNITUDES = ('N', 'Vy', 'Vz', 'T', 'My', 'Mz')
GDL = ('ux', 'uy', 'uz', 'rx', 'ry', 'rz')

# El medio ultimo decimal con que el anexo escribe fuerzas y
# desplazamientos (semana04/exportar_unity.py DECIMALES_*).
R_FUERZA = 0.5e-4
R_DESPL = 0.5e-8
EPS = 4.0 * sys.float_info.epsilon

# La aritmetica de Unity: float de 32 bits.
EPS32 = 2.0 ** -24
K_F32 = 16
U_FUERA_DE_CURVA = 9999.0       # PanelUI.U_FUERA_DE_CURVA
MS_INSTANTANEO = 1000.0 / 60.0  # un cuadro a 60 Hz

# Los juegos de lambdas de la prueba. Los tres primeros son E1..E3, que
# es lo que ponen los botones de la app.
LAMBDAS = [
    (1.0, 1.0, 0.0, 0.0),        # E1
    (1.2, 1.6, 0.0, 0.0),        # E2
    (1.2, 1.0, -1.4, 0.0),       # E3
    (1.0, 0.0, 0.0, 0.0),        # solo G
    (0.0, 0.0, 1.0, 0.0),        # solo EX
    (0.0, 0.0, 0.0, -1.0),       # solo EY, negativo
    (0.9, 0.0, -1.4, 0.0),
    (1.2, 1.0, 0.0, 1.4),
    (-0.5, 0.35, 1.05, -0.7),    # feo a proposito
    (0.0, 0.0, 0.0, 0.0),        # todo en cero
]


# ============================================================
# UTILIDADES
# ============================================================
def f32(x):
    """El float de 32 bits mas cercano: lo que Unity tiene en memoria
    despues de cada operacion."""
    return struct.unpack('<f', struct.pack('<f', float(x)))[0]


class Peor(object):
    """El valor con MENOS holgura respecto de su cota (err - cota mayor).
    Se imprime siempre, pase o no: asi se ve cuanto margen queda."""

    def __init__(self):
        self.margen, self.err, self.cota, self.donde = None, 0.0, 0.0, ''

    def ver(self, err, cota, donde):
        m = err - cota
        if self.margen is None or m > self.margen:
            self.margen, self.err, self.cota, self.donde = m, err, cota, donde

    @property
    def ok(self):
        return self.margen is None or self.margen <= 0.0

    def __str__(self):
        return 'peor %.2e en %s, cota %.2e' % (self.err, self.donde or '-', self.cota)


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


def titulo(texto):
    print()
    print(texto)
    print('-' * min(len(texto), 78))


def a_la_malla(valor, n_origen, n_destino):
    """
    La MISMA retabulacion que hace el C# (Ins_ALaMalla): interpolacion
    lineal a la malla comun, POR FRACCION DE INDICE y no por x, y en
    float de 32 bits.

    Es exacta cuando la barra no lleva carga repartida en ese caso,
    porque ahi el axial y los cortes son constantes y los momentos son
    rectas. Y se interpola por indice porque las dos mallas van de 0 a L
    equiespaciadas (lo comprueba verificar_semana04.py, bloque [1]):
    usar la x del anexo meteria su redondeo a 4 decimales -- hasta 5e-5
    m -- multiplicado por la pendiente del momento, que es el corte: en
    la viga 337 bajo G llega a 272 kN, o sea hasta 1.4e-2 kN m (se
    midieron 1.1e-2 antes de corregirlo).
    """
    if not valor or len(valor) != n_origen:
        return [0.0] * n_destino
    if n_origen == n_destino:
        return list(valor)
    if n_origen == 1:
        return [valor[0]] * n_destino
    salida = []
    for i in range(n_destino):
        p = 0.0 if n_destino == 1 else f32(f32(i / (n_destino - 1)) * (n_origen - 1))
        j = min(max(int(math.floor(p)), 0), n_origen - 2)
        frac = f32(p - j)
        salida.append(f32(valor[j] + f32(f32(valor[j + 1] - valor[j]) * frac)))
    return salida


def capacidad_en(P, familia):
    """La misma interpolacion que Ins_CapacidadEn en el C#, en float."""
    Ps, Mns = familia['P'], familia['Mn']
    if len(Ps) < 2 or P <= Ps[0] or P >= Ps[-1]:
        return 0.0
    for i in range(len(Ps) - 1):
        p1, p2 = Ps[i], Ps[i + 1]
        if p1 <= P <= p2:
            d = f32(p2 - p1)
            if abs(d) < 1e-9:
                return max(Mns[i], Mns[i + 1])
            return f32(Mns[i] + f32(f32(Mns[i + 1] - Mns[i]) * f32(f32(P - p1) / d)))
    return 0.0


def demanda_de(f, elemento, familia):
    """La misma regla que Ins_Demanda en el C#, y que
    demanda_capacidad.demanda(): los dos extremos, gana el de mayor M."""
    muro = elemento.get('tipo') == 'muro'
    plano_es_my = elemento.get('momento_en_el_plano') != 'Mz'
    Pi, Myi, Mzi = f[0], f[4], f[5]
    Pj, Myj, Mzj = f32(-f[6]), f[10], f[11]

    def hyp(a, b):
        return f32(math.sqrt(f32(f32(a * a) + f32(b * b))))

    if muro:
        Mi = abs(Myi if plano_es_my else Mzi)
        Mfi = abs(Mzi if plano_es_my else Myi)
        Mj = abs(Myj if plano_es_my else Mzj)
        Mfj = abs(Mzj if plano_es_my else Myj)
    else:
        Mi, Mfi = hyp(Myi, Mzi), 0.0
        Mj, Mfj = hyp(Myj, Mzj), 0.0
    gana_j = Mj > Mi
    P = Pj if gana_j else Pi
    M = Mj if gana_j else Mi
    Mn = capacidad_en(P, familia)
    u = f32(M / Mn) if Mn > 1e-9 else U_FUERA_DE_CURVA
    return {'id': elemento['id'], 'familia': elemento['familia'], 'P': P, 'M': M,
            'M_fuera_plano': Mfj if gana_j else Mfi,
            'extremo': 'j (superior)' if gana_j else 'i (inferior)',
            'Mn': Mn, 'u': u, 'pasa': u <= 1.0}


# ============================================================
# LA COMBINACION, COMO LA HACE UNITY
# ============================================================
def preparar(anexo):
    """Lo que el C# hace una vez al cargar: los cuatro casos base
    llevados a una malla comun por barra. Todo en float de 32 bits, que
    es como JsonUtility lo deja en memoria."""
    por_caso = {c['nombre']: c for c in anexo['casos']}
    faltan = [c for c in CASOS if c not in por_caso]
    if faltan:
        raise SystemExit('el anexo no trae los casos base: %s' % faltan)

    elementos = {int(e['id']): e for e in anexo['elementos']}
    esf = {c: {int(s['id']): s for s in por_caso[c]['esfuerzos']} for c in CASOS}

    barras = []
    for s_g in por_caso['G']['esfuerzos']:
        eid = int(s_g['id'])
        malla = s_g['x']
        for c in CASOS[1:]:
            s = esf[c].get(eid)
            if s and len(s['x']) > len(malla):
                malla = s['x']
        barra = {'id': eid, 'x': malla, 'f': {}, 'mag': {}, 'elemento': elementos.get(eid)}
        for c in CASOS:
            s = esf[c].get(eid)
            if s is None:
                barra['f'][c] = [0.0] * 12
                barra['mag'][c] = {m: [0.0] * len(malla) for m in MAGNITUDES}
                continue
            barra['f'][c] = [f32(v) for v in s['f']]
            barra['mag'][c] = {m: a_la_malla([f32(v) for v in s[m]], len(s['x']), len(malla))
                               for m in MAGNITUDES}
        barras.append(barra)

    nodos = [int(d['id']) for d in por_caso['G']['desplazamientos']]
    u_base = {}
    for c in CASOS:
        d_por_id = {int(d['id']): d for d in por_caso[c]['desplazamientos']}
        u_base[c] = [[f32(d_por_id[n][k]) if n in d_por_id else 0.0 for k in GDL] for n in nodos]

    familias = []
    for fam in anexo['familias']:
        f2 = dict(fam)
        f2['P'] = [f32(v) for v in fam['P']]
        f2['Mn'] = [f32(v) for v in fam['Mn']]
        familias.append(f2)
    return {'barras': barras, 'nodos': nodos, 'u': u_base, 'familias': familias}


def combinar_como_unity(prep, lam):
    """Lo que el C# hace al mover un slider, con su aritmetica. Devuelve
    tambien la ESCALA de cada suma, sum|lambda_c|*|v_c|, que es lo que
    multiplica el error de 32 bits."""
    l = {c: f32(v) for c, v in zip(CASOS, lam)}

    desplazamientos, esc_u, mayor = [], {}, 0.0
    for i, nid in enumerate(prep['nodos']):
        u, e = [0.0] * 6, [0.0] * 6
        for c in CASOS:
            if l[c] == 0.0:
                continue
            fila = prep['u'][c][i]
            for k in range(6):
                u[k] = f32(u[k] + f32(l[c] * fila[k]))
                e[k] += abs(l[c] * fila[k])
        desplazamientos.append(dict(zip(GDL, u), id=nid))
        esc_u[nid] = dict(zip(GDL, e))
        norma = f32(math.sqrt(f32(f32(f32(u[0] * u[0]) + f32(u[1] * u[1])) + f32(u[2] * u[2]))))
        mayor = max(mayor, norma)

    esfuerzos, demandas, esc_f, esc_m = [], [], {}, {}
    for b in prep['barras']:
        f, ef = [0.0] * 12, [0.0] * 12
        for c in CASOS:
            if l[c] == 0.0:
                continue
            for i in range(12):
                f[i] = f32(f[i] + f32(l[c] * b['f'][c][i]))
                ef[i] += abs(l[c] * b['f'][c][i])
        fila = {'id': b['id'], 'f': f, 'x': b['x']}
        em = {}
        for m in MAGNITUDES:
            v, e = [0.0] * len(b['x']), [0.0] * len(b['x'])
            for c in CASOS:
                if l[c] == 0.0:
                    continue
                base = b['mag'][c][m]
                for i in range(len(v)):
                    v[i] = f32(v[i] + f32(l[c] * base[i]))
                    e[i] += abs(l[c] * base[i])
            fila[m] = v
            em[m] = e
        esfuerzos.append(fila)
        esc_f[b['id']] = ef
        esc_m[b['id']] = em

        e4 = b['elemento']
        if e4 is not None and int(e4.get('familia', -1)) >= 0:
            demandas.append(demanda_de(f, e4, prep['familias'][int(e4['familia'])]))

    return {'max_desplazamiento_mm': f32(mayor * 1000.0), 'desplazamientos': desplazamientos,
            'esfuerzos': esfuerzos, 'demandas': demandas,
            'escala': {'u': esc_u, 'f': esc_f, 'm': esc_m}}


def cota_f32(escala):
    return K_F32 * EPS32 * escala


def escala_demanda(esc_f, d):
    """La escala de P y de M de una demanda, segun el extremo que gano."""
    j = d['extremo'].startswith('j')
    eP = esc_f[6] if j else esc_f[0]
    eM = (esc_f[10] + esc_f[11]) if j else (esc_f[4] + esc_f[5])
    return eP, eM


def conteos(demandas):
    no_pasan = sum(1 for d in demandas if not d['pasa'])
    fuera = sum(1 for d in demandas if float(d['u']) >= U_FUERA_DE_CURVA)
    return no_pasan, fuera, len(demandas)


def norma_maxima_mm(desplazamientos):
    return max(math.sqrt(float(d['ux']) ** 2 + float(d['uy']) ** 2 + float(d['uz']) ** 2)
               for d in desplazamientos) * 1000.0


# ============================================================
# [3] LA REPLICA CONTRA PYTHON
# ============================================================
def comparar(unity, python, lam, inf, etiqueta):
    suma = sum(abs(v) for v in lam)
    cota_u = R_DESPL * (suma + 1.0)
    cota_f = R_FUERZA * (suma + 1.0)
    esc = unity['escala']

    # --- desplazamientos ---
    py_u = {int(d['id']): d for d in python['desplazamientos']}
    peor_u = Peor()
    for d in unity['desplazamientos']:
        p = py_u.get(int(d['id']))
        if p is None:
            inf.check(False, '%s: el nodo %d no esta en el caso de Python' % (etiqueta, d['id']))
            return
        for k in GDL:
            peor_u.ver(abs(float(d[k]) - float(p[k])),
                       cota_u + cota_f32(esc['u'][int(d['id'])][k]) + EPS,
                       'nodo %d %s' % (d['id'], k))
    inf.check(peor_u.ok, '%s: desplazamientos de %d nodos (%s)'
              % (etiqueta, len(unity['desplazamientos']), peor_u))

    # --- esfuerzos: f y los extremos de las estaciones ---
    py_e = {int(s['id']): s for s in python['esfuerzos']}
    peor_f, peor_x = Peor(), Peor()
    for s in unity['esfuerzos']:
        p = py_e.get(int(s['id']))
        if p is None:
            continue
        for i in range(12):
            peor_f.ver(abs(s['f'][i] - float(p['f'][i])),
                       cota_f + cota_f32(esc['f'][s['id']][i]) + EPS,
                       'elem %d f[%d]' % (s['id'], i))
        # Las estaciones se comparan en los extremos, que existen en las
        # dos mallas; el interior solo cuando la malla es la misma (si
        # no, Python tabula 2 puntos y Unity 9, y comparar indice a
        # indice no tendria sentido).
        mismo = len(s['x']) == len(p['x'])
        for m in MAGNITUDES:
            idx = range(len(s['x'])) if mismo else (0, len(s['x']) - 1)
            jdx = range(len(p['x'])) if mismo else (0, len(p['x']) - 1)
            for i, j in zip(idx, jdx):
                peor_x.ver(abs(s[m][i] - float(p[m][j])),
                           cota_f + cota_f32(esc['m'][s['id']][m][i]) + EPS,
                           'elem %d %s[%d]' % (s['id'], m, i))
    inf.check(peor_f.ok, '%s: las 12 fuerzas de %d barras (%s)'
              % (etiqueta, len(unity['esfuerzos']), peor_f))
    inf.check(peor_x.ok, '%s: esfuerzos en las estaciones (%s)' % (etiqueta, peor_x))

    # --- demandas: lo que NO es lineal ---
    comparar_demandas(unity['demandas'], python['demandas'], esc['f'], cota_f, inf, etiqueta)


def comparar_demandas(dem_unity, dem_python, esc_f, cota_f, inf, etiqueta):
    py_d = {int(d['id']): d for d in dem_python}
    peor = {'P': Peor(), 'M': Peor(), 'Mn': Peor()}
    distinto_extremo, distinto_pasa = [], []
    for d in dem_unity:
        p = py_d.get(int(d['id']))
        if p is None:
            inf.check(False, '%s: la barra %d tiene demanda en Unity y no en Python'
                      % (etiqueta, d['id']))
            return
        eP, eM = escala_demanda(esc_f[int(d['id'])], d)
        topes = {'P': cota_f + cota_f32(eP) + EPS,
                 'M': cota_f + cota_f32(eM) + EPS,
                 # Mn: el error de P por la pendiente maxima de la curva.
                 'Mn': max((cota_f + cota_f32(eP)) * 100.0, 1e-3)}
        for k in ('P', 'M', 'Mn'):
            peor[k].ver(abs(float(d[k]) - float(p[k])), topes[k], 'elem %d' % d['id'])
        if d['extremo'] != p['extremo']:
            distinto_extremo.append('elem %d: Unity %s, Python %s'
                                    % (d['id'], d['extremo'], p['extremo']))
        if bool(d['pasa']) != bool(p['pasa']):
            distinto_pasa.append('elem %d: Unity %s, Python %s'
                                 % (d['id'], d['pasa'], p['pasa']))

    n = len(dem_unity)
    inf.check(peor['P'].ok and peor['M'].ok,
              '%s: P y M de %d demandas (P: %s; M: %s)' % (etiqueta, n, peor['P'], peor['M']))
    inf.check(peor['Mn'].ok, '%s: Mn interpolado en la curva (%s)' % (etiqueta, peor['Mn']))
    inf.check(not distinto_extremo,
              '%s: el extremo que manda es el mismo en las %d demandas' % (etiqueta, n),
              distinto_extremo[:4])
    inf.check(not distinto_pasa,
              '%s: pasa / no pasa coincide en las %d demandas' % (etiqueta, n),
              distinto_pasa[:4])


# ============================================================
# [4] EL REGISTRO DE LA APP REAL CONTRA PYTHON
# ============================================================
_DATO = re.compile(r'^DATO (\S+) = (.*)$')


def leer_registro(ruta):
    reg = {}
    with io.open(ruta, encoding='utf-8') as fh:
        for linea in fh:
            m = _DATO.match(linea.rstrip('\r\n'))
            if m:
                reg[m.group(1)] = m.group(2)
    return reg


def _flt(reg, clave):
    return float(reg[clave])


def comparar_registro(reg, ruta, b, prep, inf):
    """Los numeros que Unity escribio al mover los sliders (paso D2 de
    CapturaSemana05), contra Python y contra la replica."""
    juegos = [k for k in ('E1', 'E2', 'E3', 'feo') if ('ins.%s.lambdas' % k) in reg]
    if not inf.check(bool(juegos),
                     'el registro %s trae el paso D2 (sliders instantaneos)' % os.path.relpath(ruta, rutas.RAIZ),
                     () if juegos else
                     'no hay lineas "ins.*": la app que capturo no tenia el paso, o la seccion no corrio. '
                     'Vuelve a capturar: build/LaboratorioEstructural.exe -capturarS5 semana05/capturas'):
        return

    ids = [int(reg[k]) for k in ('control.columna', 'control.muro', 'control.viga') if k in reg]
    nodo = int(reg['control.nodo']) if 'control.nodo' in reg else None
    print('  barras de control %s, nodo %s, juegos %s' % (ids, nodo, juegos))

    # --- la version: cada juego tiene que haber REEMPLAZADO el caso ---
    antes = int(reg.get('ins.version_antes', '0'))
    versiones = [int(reg['ins.%s.version' % k]) for k in juegos]
    inf.check(versiones == [antes + i + 1 for i in range(len(juegos))],
              'la version sube 1 en cada juego: %s -> %s (el segundo movimiento del slider tambien reemplaza)'
              % (antes, versiones))
    if 'ins.version_despues' in reg and 'ins.combinaciones_pedidas' in reg:
        inf.check(int(reg['ins.version_despues']) - antes == int(reg['ins.combinaciones_pedidas']),
                  'se combino exactamente %s veces' % reg['ins.combinaciones_pedidas'])
    for k in juegos:
        inf.check(reg.get('ins.%s.caso_activo' % k) == 'INSTANT' and reg.get('ins.%s.tipo' % k) == 'superposicion',
                  '%s: el caso activo es INSTANT y su tipo "superposicion" (activo %s, tipo %s)'
                  % (k, reg.get('ins.%s.caso_activo' % k), reg.get('ins.%s.tipo' % k)))
    origenes_mal = [k for k in juegos if 'Unity' not in reg.get('ins.%s.origen' % k, '')]
    inf.check(not origenes_mal, 'el panel dice que INSTANT se combino en Unity, no en Python',
              ['%s: %s' % (k, reg.get('ins.%s.origen' % k, '')[:100]) for k in origenes_mal])

    # --- instantaneo: dentro de un cuadro ---
    ms = [_flt(reg, 'ins.%s.ms' % k) for k in juegos]
    inf.check(max(ms) <= MS_INSTANTANEO,
              'cada combinacion cabe en un cuadro a 60 Hz: %s ms (tope %.1f)'
              % (', '.join('%.2f' % v for v in ms), MS_INSTANTANEO))

    # --- los numeros, juego por juego ---
    peor_replica = 0.0
    for k in juegos:
        lam = tuple(float(v) for v in reg['ins.%s.lambdas' % k].split(','))
        etiqueta = 'registro %s l = (%s)' % (k, ', '.join('%g' % v for v in lam))
        caso, _ = sup.caso_combinado(b, dict(zip(CASOS, lam)))
        replica = combinar_como_unity(prep, lam)
        esc = replica['escala']
        suma = sum(abs(v) for v in lam)
        cota_u = R_DESPL * (suma + 1.0)
        cota_f = R_FUERZA * (suma + 1.0)
        p = 'ins.%s' % k

        # desplazamiento maximo (la norma, como la cabecera del anexo)
        u_max_py = norma_maxima_mm(caso['desplazamientos'])
        u_max_un = _flt(reg, p + '.max_desplazamiento_mm')
        esc_max = max(sum(e.values()) for e in esc['u'].values()) * 1000.0
        tope = cota_u * 1000.0 + cota_f32(esc_max) + EPS
        inf.check(abs(u_max_un - u_max_py) <= tope,
                  '%s: desplazamiento maximo %.4f mm (Python %.4f, cota %.1e)'
                  % (etiqueta, u_max_un, u_max_py, tope))

        # el nodo de control
        if nodo is not None:
            py_u = {int(d['id']): d for d in caso['desplazamientos']}[nodo]
            re_u = {int(d['id']): d for d in replica['desplazamientos']}[nodo]
            peor = Peor()
            for g in ('ux', 'uy', 'uz'):
                v = _flt(reg, '%s.nodo.%d.%s_m' % (p, nodo, g))
                peor.ver(abs(v - float(py_u[g])), cota_u + cota_f32(esc['u'][nodo][g]) + EPS, g)
                peor_replica = max(peor_replica, abs(v - float(re_u[g])) / max(abs(v), 1e-12))
            inf.check(peor.ok, '%s: nodo %d ux, uy, uz (%s)' % (etiqueta, nodo, peor))

        # los extremos de las barras de control
        py_e = {int(s['id']): s for s in caso['esfuerzos']}
        re_e = {int(s['id']): s for s in replica['esfuerzos']}
        peor = Peor()
        for eid in ids:
            if ('%s.elem.%d.N_i' % (p, eid)) not in reg:
                continue
            for m in MAGNITUDES:
                for lado, i in (('i', 0), ('j', -1)):
                    v = _flt(reg, '%s.elem.%d.%s_%s' % (p, eid, m, lado))
                    peor.ver(abs(v - float(py_e[eid][m][i])),
                             cota_f + cota_f32(esc['m'][eid][m][i]) + EPS,
                             'elem %d %s_%s' % (eid, m, lado))
                    peor_replica = max(peor_replica, abs(v - float(re_e[eid][m][i])) / max(abs(v), 1e-6))
        inf.check(peor.ok, '%s: extremos N..Mz de las barras %s (%s)' % (etiqueta, ids, peor))

        # las demandas de las barras de control
        dem = []
        for eid in ids:
            if ('%s.elem.%d.P' % (p, eid)) not in reg:
                continue
            dem.append({'id': eid, 'P': _flt(reg, '%s.elem.%d.P' % (p, eid)),
                        'M': _flt(reg, '%s.elem.%d.M' % (p, eid)),
                        'Mn': _flt(reg, '%s.elem.%d.Mn' % (p, eid)),
                        'u': _flt(reg, '%s.elem.%d.u' % (p, eid)),
                        'extremo': reg['%s.elem.%d.extremo' % (p, eid)],
                        'pasa': reg['%s.elem.%d.pasa' % (p, eid)] == 'True'})
        if dem:
            comparar_demandas(dem, caso['demandas'], esc['f'], cota_f, inf, etiqueta)

        # los conteos de la cabecera
        np_py, fu_py, tot_py = conteos(caso['demandas'])
        np_un = int(reg[p + '.no_pasan'])
        fu_un = int(reg[p + '.fuera_de_curva'])
        tot_un = int(reg[p + '.con_fierro'])
        inf.check((np_un, fu_un, tot_un) == (np_py, fu_py, tot_py),
                  '%s: la cabecera cuenta NO PASA %d/%d (%d fuera de curva); Python %d/%d (%d)'
                  % (etiqueta, np_un, tot_un, fu_un, np_py, tot_py, fu_py))

    print('  la replica de Python y el registro de Unity difieren a lo mas %.1e relativo'
          % peor_replica + ' (la aritmetica de 32 bits esta bien emulada si es ~1e-7)')


# ============================================================
def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    edificio = 'lt2'
    if argv and not argv[0].startswith('-'):
        edificio = argv.pop(0)
    cuantos = len(LAMBDAS)
    if '--casos' in argv:
        i = argv.index('--casos')
        cuantos = int(argv[i + 1])
        del argv[i:i + 2]
    registro = None
    if '--registro' in argv:
        i = argv.index('--registro')
        registro = argv[i + 1]
        del argv[i:i + 2]
        if not os.path.isabs(registro):
            registro = os.path.join(rutas.RAIZ, registro)

    print('=' * 78)
    print('  LOS SLIDERS INSTANTANEOS CONTRA PYTHON   %s' % edificio.upper())
    print('=' * 78)
    print('  Unity combina los cuatro casos base del anexo (semana04.json) al mover un')
    print('  slider. Aca se repite esa combinacion paso a paso, con la aritmetica de 32')
    print('  bits de Unity, y se compara contra semana05/superposicion.caso_combinado().')
    if registro:
        print('  Y con --registro se cruzan ademas los numeros que la app REAL escribio al')
        print('  mover los sliders (CapturaSemana05, paso D2).')

    anexo_disco = os.path.join(rutas.UNITY, 'semana04.json')
    with io.open(anexo_disco, encoding='utf-8') as fh:
        anexo = json.load(fh)
    if anexo['info']['edificio'] != edificio:
        print()
        print('  El anexo en disco es de %s, no de %s.' % (anexo['info']['edificio'], edificio))
        print('  Corre:  python semana04\\exportar_unity.py %s' % edificio)
        return 1
    print('  anexo   %s  (%s, %d elementos, %d familias)'
          % (os.path.relpath(anexo_disco, rutas.RAIZ), anexo['info']['edificio'],
             len(anexo['elementos']), len(anexo['familias'])))

    titulo('[1] LA BASE DE PYTHON  (resuelve G, Q, EX y EY en OpenSees)')
    b = sup.base(edificio, list(anexo['info'].get('parametros_argv', []) or []))
    print('  %d elementos, %d nodos, %.1f s' % (len(b['anexo']['elementos']),
                                                len(b['ids_nodos']), b['segundos']))
    inf = Informe()
    inf.check(b['anexo']['info']['parametros'] == anexo['info']['parametros'],
              'la base usa los mismos parametros que el anexo que lee Unity')

    titulo('[2] LA PREPARACION QUE HACE UNITY UNA SOLA VEZ')
    prep = preparar(anexo)
    finas = sum(1 for x in prep['barras'] if len(x['x']) > 2)
    inf.check(len(prep['barras']) == len(anexo['elementos']),
              'las %d barras del anexo quedaron en la malla comun (%d con estaciones finas)'
              % (len(prep['barras']), finas))

    titulo('[3] LA REPLICA DEL ALGORITMO, JUEGO POR JUEGO, CONTRA PYTHON')
    for lam in LAMBDAS[:cuantos]:
        etiqueta = 'l = (%s)' % ', '.join('%g' % v for v in lam)
        caso, _peor = sup.caso_combinado(b, dict(zip(CASOS, lam)))
        unity = combinar_como_unity(prep, lam)
        comparar(unity, caso, lam, inf, etiqueta)

    if registro:
        titulo('[4] LO QUE LA APP REAL CALCULO AL MOVER LOS SLIDERS, CONTRA PYTHON')
        if not os.path.exists(registro):
            inf.check(False, 'existe el registro %s' % registro)
        else:
            comparar_registro(leer_registro(registro), registro, b, prep, inf)

    print()
    print('=' * 78)
    if inf.fallas:
        print('  NO CALZA (%d):' % len(inf.fallas))
        for f in inf.fallas:
            print('    - %s' % f)
        print('=' * 78)
        return 1
    if registro:
        print('  LO QUE UNITY COMBINO AL MOVER LOS SLIDERS ES LO DE PYTHON')
    else:
        print('  EL ALGORITMO DE LOS SLIDERS DA LO DE PYTHON (falta --registro para la app real)')
    print('=' * 78)
    return 0


if __name__ == '__main__':
    sys.exit(main())
