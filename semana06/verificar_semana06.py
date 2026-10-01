# -*- coding: utf-8 -*-
r"""
================================================================
 semana06/verificar_semana06.py
   QA FINAL ESTRUCTURAL DEL CONJUNTO: LA TABLA DEL INFORME, EN VIVO
================================================================
 La tabla del punto 5 de reports/semana06.md no se escribe a mano:
 sale de aca. Cada fila corre su prueba sobre el CONJUNTO (los dos
 cuerpos, 558 nodos y 937 elementos) con las funciones del repo --
 ninguna regla se copia -- y decide su estado con un criterio que
 esta escrito en el codigo, al lado de su causa:

   OK       la prueba corrio y cumple su criterio.
   PARCIAL  cumple lo que se puede comprobar, pero hay algo abierto
            que la misma prueba MIDE y dice cuanto vale. El dia que se
            arregle, la fila pasa sola a OK.
   FALLA    no cumple. El script termina con codigo 1.

 Las diez filas del enunciado:

   Equilibrio G, Equilibrio Q     calcular.equilibrio sobre los casos
   Corte basal EX, Corte basal EY del anexo que muestra Unity, con la
                                  cota del redondeo del servidor
   Superposicion                  combinar.verificar en las 11
                                  combinaciones, contra OpenSees
                                  resuelto con la carga combinada
   M-phi                          columna 200037 contra Whitney y la
                                  seccion fisurada a mano
   P-M columna                    familia de 200037: extremos, anexo =
                                  capacidad.interaccion, demanda
   P-M muro                       100537 (antiguo) y 200009 (LT2)
   IDs Unity                      contrato JSON <-> C# y el mismo tag en
                                  modelo, visor, anexo y GameObject
   AR                             semana06_lab/verificar_ar.py, y si hay
                                  evidencia del iPhone

   python semana06/verificar_semana06.py
   python semana06/verificar_semana06.py --salida       # + evidencia/qa_semana06.md
   python semana06/verificar_semana06.py --ar-completo  # la AR con el tracking en Chrome
================================================================
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import datetime
import importlib.util
import io
import json
import math
import os
import re
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), 'comun'))
import rutas                                   # noqa: E402
rutas.entrar(__file__, os.path.join(rutas.RAIZ, 'semana03'))

import calcular                                # noqa: E402
import capacidad                               # noqa: E402
import combinar                                # noqa: E402
import contrato                                # noqa: E402
import servidor_opensees as motor              # noqa: E402
import lab_semana03 as lab                     # noqa: E402
import parametros                              # noqa: E402
import demanda_capacidad as dc                 # noqa: E402
import verificar_rc as vrc                     # noqa: E402


def por_ruta(nombre, *partes):
    """Un modulo cargado por RUTA. semana03/ y semana04/ tienen archivos
    con el mismo nombre, y el import por nombre traeria el equivocado sin
    ningun error (CLAUDE.md, la trampa de exportar_unity)."""
    if nombre in sys.modules:
        return sys.modules[nombre]
    spec = importlib.util.spec_from_file_location(
        nombre, os.path.join(rutas.RAIZ, *partes))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = mod
    spec.loader.exec_module(mod)
    return mod


traz = por_ruta('trazabilidad_semana04', 'semana04', 'trazabilidad.py')
ex_ar = por_ruta('exportar_ar_semana06', 'semana06_lab', 'exportar_ar.py')

EDIFICIO = 'conjunto'
CASOS = ('G', 'Q', 'EX', 'EY')
COLUMNA = 200037
MUROS = (100537, 200009)
EVIDENCIA = os.path.join(AQUI, 'evidencia')
IPHONE = os.path.join(EVIDENCIA, 'iphone')
EPS = sys.float_info.epsilon

# El servidor escribe las fuerzas con 4 decimales (CLAUDE.md, Resultados):
# cada reaccion llega con hasta medio ultimo digito de error.
R_KN = 0.5e-4
# calcular.equilibrio devuelve error_kN redondeado a 8 decimales.
R_EQ = 0.5e-8

# Los numeros de control viven en CLAUDE.md, seccion 8, con 2 decimales. Se
# leen de ahi y no se copian: cuando cambia una seccion (las vigas de
# Ingenieria, el 29-09) cambian ahi, y una copia aca quedaria vieja.
CLAUDE = os.path.join(rutas.RAIZ, 'CLAUDE.md')
CONTROL = {'lt2': 'LT2', 'ingenieria': 'Ingeniería', 'conjunto': 'conjunto'}

# Whitney y las fibras no son el mismo modelo (bloque rectangular contra
# la parabola de Concrete01 con Mander), asi que no coinciden al
# redondeo. El umbral de 2 % no se eligio a ojo: se imprime al lado lo
# que mueve Mn el error de dato mas chico que tiene que detectar (un
# diametro menos, 25 -> 22 mm), y el umbral queda muy por debajo.
TOL_MODELOS = 0.02
# Lo que declara comun/capacidad.py junto a FIBRAS_NUCLEO: "entre 20 y
# 40 el momento maximo cambia menos de 0.5%". Se le toma la palabra.
TOL_MALLADO = 0.005

# S3 (1.0G + 0.5Q + 1.0EX) es la combinacion de servicio heredada de la
# Semana 3, no una de NCh3171. Las otras 10 de semana03/parametros.json
# son las mayoradas: con esas se busca la que gobierna.
NO_DE_DISENO = ('S3',)


# ============================================================
# SALIDA
# ============================================================
class Fila(object):
    """Una fila de la tabla: sus chequeos, lo abierto y el numero clave."""

    def __init__(self, prueba, comando):
        self.prueba = prueba
        self.comando = comando
        self.fallas = []
        self.abiertos = []
        self.numero = ''
        self.criterio = ''
        self.segundos = 0.0

    def check(self, ok, que, *detalle):
        print('  [%s] %s' % ('OK  ' if ok else 'FALLA', que))
        for d in detalle:
            print('         %s' % d)
        if not ok:
            self.fallas.append(que)
        return ok

    def abierto(self, que, *detalle):
        print('  [PARC] %s' % que)
        for d in detalle:
            print('         %s' % d)
        self.abiertos.append(que)

    @staticmethod
    def info(que):
        print('         %s' % que)

    @property
    def estado(self):
        if self.fallas:
            return 'FALLA'
        return 'PARCIAL' if self.abiertos else 'OK'


def ruta_rel(ruta):
    return os.path.relpath(ruta, rutas.RAIZ).replace(os.sep, '/')


def celda(texto):
    """Texto para una celda de tabla markdown: un | suelto la parte."""
    return texto.replace('|', '\|')


def titulo(t):
    print()
    print(t)
    print('-' * min(len(t), 78))


def rel(a, b):
    return abs(a - b) / max(abs(b), 1e-12)


def filas_que_cuentan(modelo, reacciones):
    r"""
    Cuantas filas de reaccion entran en Fx, Fy y Fz, preguntandoselo a
    calcular.equilibrio: con 1 kN en cada fila y ninguna carga, la
    'reaccion' que devuelve es el conteo. La regla (quien cuenta en cada
    grado de libertad) sigue teniendo una sola definicion. Es el mismo
    truco de semana05/verificar_superposicion.filas_que_cuentan.
    """
    unos = {'reacciones': [{'id': r['id'], 'fx': 1.0, 'fy': 1.0, 'fz': 1.0}
                           for r in reacciones]}
    cuenta = calcular.equilibrio(
        modelo, {'cargas_nodales': [], 'cargas_distribuidas': []}, unos)
    return [int(round(v)) for v in cuenta['reaccion_kN']]


# ============================================================
# CONTEXTO: el conjunto y los casos del anexo, resueltos una vez
# ============================================================
def contexto():
    modelo = contrato.cargar_modelo(EDIFICIO)
    p = parametros.cargar([])
    with contextlib.redirect_stdout(io.StringIO()):
        arm = lab.armar_casos(modelo, p)
    casos = {n: arm['casos'][n] for n in CASOS}
    datos = copy.deepcopy(modelo)
    datos['casos_de_carga'] = [casos[n] for n in CASOS]
    with contextlib.redirect_stdout(io.StringIO()), traz.AvisosDeOpenSees():
        s = motor.construir_y_resolver(datos)
    if not s.get('ok'):
        raise SystemExit('OpenSees no resolvio los casos del anexo del conjunto')
    res = {r['nombre']: r for r in s['casos']}
    anexo, origen = ex_ar.cargar_anexo()
    origen = origen.replace(os.sep, '/')
    return {'modelo': modelo, 'p': p, 'arm': arm, 'casos': casos,
            'res': res, 'anexo': anexo, 'origen_anexo': origen}


# ============================================================
# EQUILIBRIO G Y Q
# ============================================================
def numeros_de_control():
    """{edificio: G} de la seccion 8 de CLAUDE.md ('LT2 `G = 34 148.98 kN`')."""
    with io.open(CLAUDE, encoding='utf-8') as fh:
        texto = fh.read()
    control = {}
    for ed, rotulo in CONTROL.items():
        m = re.search(r'%s `G = ([\d ]+\.\d+) kN`' % rotulo, texto)
        if not m:
            raise SystemExit('CLAUDE.md no tiene el numero de control de G de %s' % rotulo)
        control[ed] = float(m.group(1).replace(' ', ''))
    return control


def caso_g(edificio):
    """El caso G guardado en el modelo de un cuerpo."""
    modelo = contrato.cargar_modelo(edificio)
    return next(c for c in modelo['casos_de_carga'] if c['nombre'] == 'G')


def fila_equilibrio(ctx, nombre):
    f = Fila('Equilibrio %s' % nombre, 'python semana06/verificar_semana06.py')
    modelo, caso, res = ctx['modelo'], ctx['casos'][nombre], ctx['res'][nombre]
    eq = calcular.equilibrio(modelo, caso, res)
    nx, ny, nz = filas_que_cuentan(modelo, res['reacciones'])
    a, r, e = eq['aplicada_kN'], eq['reaccion_kN'], eq['error_kN']
    cota = [n * R_KN + R_EQ for n in (nx, ny, nz)]
    f.check(eq['confiable'], 'calcular.equilibrio convirtio todas las cargas '
            '(%d sin convertir)' % eq['cargas_sin_convertir'])
    f.check(all(abs(e[i]) <= cota[i] for i in range(3)),
            'aplicada %.4f kN, reaccion %.4f kN, error %.2e kN (cota del '
            'redondeo %.2e: %d apoyos x 0.5e-4)' % (a[2], r[2], abs(e[2]), cota[2], nz),
            'en x e y: error %.1e / %.1e kN (cotas %.1e / %.1e)'
            % (abs(e[0]), abs(e[1]), cota[0], cota[1]))
    if nombre == 'G':
        # El conjunto es la suma de sus cuerpos: el G de cada uno sale de su
        # propio modelo, y los tres tienen que ser el numero de control.
        control = numeros_de_control()
        g = {ed: -calcular.equilibrio(contrato.cargar_modelo(ed), caso_g(ed),
                                      {'reacciones': []})['aplicada_kN'][2]
             for ed in ('lt2', 'ingenieria')}
        g['conjunto'] = -a[2]
        f.check(all(abs(g[ed] - control[ed]) <= 0.005 for ed in g)
                and abs(g['conjunto'] - g['lt2'] - g['ingenieria']) <= 0.005,
                'G = %.2f kN = %.2f (Ingenieria) + %.2f (LT2), cada cuerpo desde su propio '
                'modelo; los tres son los numeros de control de CLAUDE.md'
                % (g['conjunto'], g['ingenieria'], g['lt2']))
    else:
        f.info('Q del anexo: q = %.1f kN/m2 uniforme por area tributaria '
               '(semana03/parametros.json), el que muestra Unity' % ctx['p']['q_Q'])
    f.numero = 'error %.1e kN de %.2f kN (cota %.1e)' % (abs(e[2]), -a[2], cota[2])
    f.criterio = '|aplicada + reaccion| <= apoyos que cuentan x 0.5e-4 kN'
    return f


# ============================================================
# CORTE BASAL EX Y EY
# ============================================================
def fila_corte(ctx, nombre):
    f = Fila('Corte basal %s' % nombre, 'python semana06/verificar_semana06.py')
    modelo, p, arm = ctx['modelo'], ctx['p'], ctx['arm']
    caso, res = ctx['casos'][nombre], ctx['res'][nombre]
    i = 0 if nombre == 'EX' else 1
    eq = calcular.equilibrio(modelo, caso, res)
    n = filas_que_cuentan(modelo, res['reacciones'])
    a, r, e = eq['aplicada_kN'], eq['reaccion_kN'], eq['error_kN']
    cota = n[i] * R_KN + R_EQ
    f.check(abs(e[i]) <= cota,
            'carga lateral %.4f kN, corte en los apoyos %.4f kN, error %.2e kN '
            '(cota %.2e: %d apoyos fuera de diafragma x 0.5e-4)'
            % (a[i], r[i], abs(e[i]), cota, n[i]))

    # El peso sismico, controlado por fuera de armar_casos: G y Q se
    # suman de sus propios casos y V tiene que ser Cs * (G + fQ * Q).
    G = -calcular.equilibrio(modelo, ctx['casos']['G'], ctx['res']['G'])['aplicada_kN'][2]
    Q = -calcular.equilibrio(modelo, ctx['casos']['Q'], ctx['res']['Q'])['aplicada_kN'][2]
    W = G + p['fraccion_Q_sismica'] * Q
    V = sum(float(c.get('fx' if i == 0 else 'fy', 0.0)) for c in caso['cargas_nodales'])
    cota_v = len(caso['cargas_nodales']) * 4 * EPS * W
    f.check(abs(V - p['coef_sismico'] * W) <= max(cota_v, 5e-5),
            'V = %.4f kN = Cs x W = %.2f x (%.4f + %.2f x %.4f) = %.2f x %.4f'
            % (V, p['coef_sismico'], G, p['fraccion_Q_sismica'], Q, p['coef_sismico'], W),
            'G y Q sumados de sus propios casos: no se pierde peso al repartirlo por nivel')

    # El reparto en altura: el patron declarado (potencia, k = 1) es
    # F_i proporcional a W_i * h_i. El equilibrio no ve un reparto
    # equivocado mientras el total se conserve.
    k = p['k_patron']
    cte = [F / (w * h ** k) for F, w, h in zip(arm['fuerzas'], arm['pesos_sismicos'],
                                               arm['alturas']) if w * h > 0]
    desvio = max(rel(c, cte[0]) for c in cte)
    f.check(desvio <= 1e-12,
            'reparto %s k = %g: F_i / (W_i h_i^k) = %.7f en los %d diafragmas '
            '(desvio %.1e)' % (p['patron'], k, cte[0], len(cte), desvio))

    todo = sum(float(x.get('fx' if i == 0 else 'fy', 0.0)) for x in res['reacciones'])
    f.info('sumar la columna entera de reacciones daria %.2f kN (x%.2f): los nodos '
           'de diafragma reaccionan tambien a su restriccion, y no se hace' % (todo, abs(todo / r[i])))
    disco = rutas.resultados(EDIFICIO, nombre)
    if os.path.isfile(disco):
        c_mod = next(c for c in modelo['casos_de_carga'] if c['nombre'] == nombre)
        eq_m = calcular.equilibrio(modelo, c_mod, contrato.cargar_resultados(EDIFICIO, nombre))
        f.info('el %s guardado en data/modelo (el que imprime comun/sismo.py) aplica %.3f kN '
               'y tambien cierra (error %.1e kN): otro peso sismico, ver reports/semana06.md'
               % (nombre, eq_m['aplicada_kN'][i], abs(eq_m['error_kN'][i])))
    f.numero = 'V = %.2f kN = 0.10 W; error %.1e kN (cota %.1e)' % (a[i], abs(e[i]), cota)
    f.criterio = '|V + corte| <= apoyos x 0.5e-4; V = Cs(G + fQ Q); F_i ~ W_i h_i'
    return f


# ============================================================
# SUPERPOSICION
# ============================================================
def fila_superposicion(ctx):
    f = Fila('Superposicion', 'python comun/combinar.py conjunto')
    modelo, p = ctx['modelo'], ctx['p']
    peor = (0.0, None)
    n_comp = pasa_margen = 0
    for comb in p['combinaciones']:
        lam = {c: float(comb.get(c, 0.0)) for c in CASOS}
        with contextlib.redirect_stdout(io.StringIO()), traz.AvisosDeOpenSees():
            v = combinar.verificar(EDIFICIO, lam, modelo=modelo)
        suma = sum(abs(x) for x in lam.values())
        for familia, inf in v['informe'].items():
            n_comp += 1
            # La cota de combinar.py (piso_de_redondeo) mas la coma
            # flotante de sumar con esos factores. Sin el margen de 5 %
            # que combinar.py elige a mano (combinar.py, verificar()).
            cota = inf['piso_de_redondeo'] + 4 * EPS * suma * max(inf['escala'], 1.0)
            cociente = inf['peor_absoluto'] / cota if cota else 0.0
            if inf['peor_absoluto'] > inf['piso_de_redondeo']:
                pasa_margen += 1
            if cociente > peor[0]:
                peor = (cociente, '%s, %s: %.2e contra %.2e'
                        % (comb['nombre'], familia, inf['peor_absoluto'], cota))
            if inf['peor_absoluto'] > cota:
                f.check(False, '%s %s: %.3e > cota %.3e'
                        % (comb['nombre'], familia, inf['peor_absoluto'], cota))
    f.check(not f.fallas,
            '%d combinaciones x 3 familias (desplazamientos, reacciones, fuerzas '
            'localForce) = %d comparaciones con OpenSees resuelto con la carga '
            'combinada, todas dentro del redondeo del servidor + coma flotante'
            % (len(p['combinaciones']), n_comp),
            'peor cociente error/cota = %.6f (%s)' % peor)
    if pasa_margen:
        f.info('%d de %d pasan el piso de redondeo solo por coma flotante (menos de 1 '
               'ulp): combinar.py los deja pasar con un margen de 5 %% elegido a mano; '
               'aca se usa la cota medida' % (pasa_margen, n_comp))
    f.numero = '%d/%d dentro de la cota; peor %.3f de la cota' % (n_comp - len(f.fallas), n_comp, peor[0])
    f.criterio = '|suma - explicita| <= 0.5x10^-d (sum|lambda| + 1) + 4 eps sum|lambda| |valor|'
    return f


# ============================================================
# M-PHI
# ============================================================
def seccion_fisurada(sec):
    r"""
    A MANO: seccion fisurada elastica con P = 0, primera fluencia de la
    barra mas traccionada. Equilibrio de momentos estaticos para kd,
    y M respecto del eje neutro (con P = 0 da igual el punto). Las
    barras comprimidas con (n - 1), porque desplazan hormigon.
    """
    Ec = 4700.0 * math.sqrt(sec.fpc / 1000.0) * 1000.0
    n = sec.Es / Ec
    capas = vrc._capas(sec)
    b = sec.b

    def estatico(kd):
        s = b * kd ** 2 / 2.0
        for d, A in capas:
            s += ((n - 1) if d < kd else n) * A * (kd - d)
        return s

    lo, hi = 1e-6, sec.h
    for _ in range(200):
        m = 0.5 * (lo + hi)
        if estatico(m) < 0:
            lo = m
        else:
            hi = m
    kd = 0.5 * (lo + hi)
    I_cr = b * kd ** 3 / 3.0 + sum(((n - 1) if d < kd else n) * A * (kd - d) ** 2
                                   for d, A in capas)
    phi_y = (sec.fy / sec.Es) / (capas[-1][0] - kd)
    return {'kd': kd, 'n': n, 'Ec': Ec, 'EI_cr': Ec * I_cr, 'phi_y': phi_y,
            'My': Ec * I_cr * phi_y, 'fc_arriba_MPa': Ec * phi_y * kd / 1000.0}


def con_barras(sec, diametro_nuevo_m):
    """La misma seccion con otro diametro en todas las barras."""
    otra = copy.copy(sec)
    otra.barras = []
    for y, z, a in sec.barras:
        d = math.sqrt(4.0 * a / math.pi)
        otra.barras.append((y, z, a * (diametro_nuevo_m / d) ** 2))
    return otra


def fila_mphi(ctx):
    f = Fila('M-phi', 'python comun/capacidad.py conjunto 200037 --sensibilidad')
    sec = capacidad.desde_elemento(ctx['modelo'], COLUMNA)
    with traz.AvisosDeOpenSees():
        r20 = capacidad.momento_curvatura(sec, P=0.0)
        r40 = capacidad.momento_curvatura(sec, P=0.0, nf=40)
    print('    columna %d, %s, f\'c %.0f MPa, %d barras, As %.2f cm2'
          % (COLUMNA, sec.nombre, sec.fpc / 1000.0, len(sec.barras), sec.As * 1e4))

    w = vrc.flexion_pura(sec)
    d_mn = rel(r20['M_aci'], w['M_kNm'])
    w22 = vrc.flexion_pura(con_barras(sec, 0.022))
    f.check(d_mn <= TOL_MODELOS,
            'Mn (hormigon a 0.003) fibras %.1f contra Whitney a mano %.1f kN m: %.2f %% '
            '(umbral %.0f %%)' % (r20['M_aci'], w['M_kNm'], 100 * d_mn, 100 * TOL_MODELOS),
            'el umbral detecta un diametro menos: con D22 Whitney da %.1f kN m (%+.1f %%)'
            % (w22['M_kNm'], 100 * (w22['M_kNm'] / w['M_kNm'] - 1)))

    h = seccion_fisurada(sec)
    k_fib = r20['rigidez_inicial_kNm2']
    d_ei = rel(k_fib, h['EI_cr'])
    f.check(d_ei <= TOL_MODELOS,
            'rigidez fisurada: pendiente inicial de la curva %.0f contra Ec I_cr a mano '
            '%.0f kN m2: %.2f %%' % (k_fib, h['EI_cr'], 100 * d_ei),
            'a mano: n = %.2f, kd = %.4f m, primera fluencia phi_y = %.5f 1/m, My = %.1f kN m '
            '(fc arriba %.1f MPa)' % (h['n'], h['kd'], h['phi_y'], h['My'], h['fc_arriba_MPa']))

    d_nf = rel(r20['M_max'], r40['M_max'])
    f.check(d_nf <= TOL_MALLADO,
            'mallado: M_max con 20 fibras %.1f contra 40 fibras %.1f kN m: %.2f %% '
            '(lo que declara capacidad.py: < 0.5 %%)' % (r20['M_max'], r40['M_max'], 100 * d_nf))

    termina = r20['motivo_termino']
    f.check('eps_su' in termina or 'eps_cu' in termina,
            'la curva la corta el material, no el analisis: %s' % termina,
            'M_max %.1f kN m en phi %.4f 1/m; ductilidad de curvatura phi_u / phi_y(a mano) = %.0f'
            % (r20['M_max'], r20['phi_en_M_max'], r20['phi'][-1] / h['phi_y']))
    f.numero = 'Mn %.1f vs Whitney %.1f kN m (%.1f %%); EI_cr %.1f %%' % (
        r20['M_aci'], w['M_kNm'], 100 * d_mn, 100 * d_ei)
    f.criterio = 'fibras vs a mano <= 2 %; 20 vs 40 fibras <= 0.5 %'
    return f


# ============================================================
# P-M: lo comun a columna y muro
# ============================================================
def familia_del_anexo(anexo, eid):
    e = next(x for x in anexo['elementos'] if x['id'] == eid)
    return e, next(fa for fa in anexo['familias'] if fa['indice'] == e['familia'])


def demandas_del_anexo(ctx, eid, tipo, plano):
    r"""
    (caso, P, M, Mn, u) de eid en cada caso del anexo, rehechos con la
    regla de demanda_capacidad sobre los esfuerzos del anexo, y la u que
    guardo el anexo. Tienen que ser la misma: una sola definicion.
    """
    e, fam = familia_del_anexo(ctx['anexo'], eid)
    curva = [{'P_kN': P, 'M_kNm': M} for P, M in zip(fam['P'], fam['Mn'])]
    filas = []
    for caso in ctx['anexo']['casos']:
        fz = next(x for x in caso['esfuerzos'] if x['id'] == eid)
        d = dc.demanda(fz['f'], tipo=tipo, plano=plano)
        Mn = dc.capacidad_en(d['P_kN'], curva)
        u = d['M_kNm'] / Mn if Mn > 0 else float('inf')
        guardada = next(x for x in caso['demandas'] if x['id'] == eid)
        filas.append({'caso': caso['nombre'], 'P': d['P_kN'], 'M': d['M_kNm'],
                      'fuera': d.get('M_fuera_de_plano_kNm'), 'Mn': Mn, 'u': u,
                      'u_anexo': guardada['u'], 'pasa': guardada['pasa']})
    return filas


def curva_igual_al_anexo(f, sec, fam):
    """La curva del anexo es la de capacidad.interaccion, al redondeo."""
    with traz.AvisosDeOpenSees():
        pts = capacidad.interaccion(sec)
    pts = sorted(pts, key=lambda q: q['P_kN'])
    peor = max(max(abs(a['P_kN'] - P), abs(a['M_kNm'] - M))
               for a, P, M in zip(pts, fam['P'], fam['Mn']))
    cota = 0.5e-4 * (1 + 1e-9)
    f.check(len(pts) == len(fam['P']) and peor <= cota,
            'la curva del anexo (familia %d, %d puntos) = capacidad.interaccion: '
            'peor %.1e (el anexo escribe 4 decimales)' % (fam['indice'], len(pts), peor))
    return pts


def fila_pm_columna(ctx):
    f = Fila('P-M columna', 'python semana03/verificar_rc.py conjunto 200037')
    sec = capacidad.desde_elemento(ctx['modelo'], COLUMNA)
    e, fam = familia_del_anexo(ctx['anexo'], COLUMNA)
    print('    familia %d: %s (%d columnas)' % (fam['indice'], fam['refuerzo'], len(fam['elementos'])))
    pts = curva_igual_al_anexo(f, sec, fam)

    t = min(pts, key=lambda q: q['P_kN'])
    f.check(rel(t['P_kN'], -vrc.traccion_pura(sec)) <= 1e-9,
            'traccion pura: fibras %.1f = -As fy %.1f kN (sin hipotesis distintas)'
            % (t['P_kN'], -vrc.traccion_pura(sec)))
    p0 = min(pts, key=lambda q: abs(q['P_kN']))
    w = vrc.flexion_pura(sec)
    f.check(rel(p0['M_kNm'], w['M_kNm']) <= TOL_MODELOS,
            'flexion pura: fibras %.1f contra Whitney %.1f kN m (%.2f %%)'
            % (p0['M_kNm'], w['M_kNm'], 100 * rel(p0['M_kNm'], w['M_kNm'])))

    bal = vrc.balanceado(sec)
    with traz.AvisosDeOpenSees():
        rb = capacidad.momento_curvatura(sec, P=bal['P_kN'])
        desnuda = copy.copy(sec)
        desnuda.estribo = {}
        desnuda.trabas_x = desnuda.trabas_y = 0
        rd = capacidad.momento_curvatura(desnuda, P=bal['P_kN'])
    Mb = rb['M_aci'] or rb['M_max']
    Md = rd['M_aci'] or rd['M_max']
    f.check(Mb <= bal['M_kNm'],
            'balanceado (P = %.0f kN): fibras %.1f bajo Whitney %.1f kN m (%.1f %%), del lado seguro'
            % (bal['P_kN'], Mb, bal['M_kNm'], 100 * (bal['M_kNm'] / Mb - 1)),
            'sin confinar las fibras dan %.1f (%.1f %%): el confinamiento explica esa parte y el '
            'resto es el bloque de Whitney con axial alto' % (Md, 100 * (bal['M_kNm'] / Md - 1)))
    f.info('compresion pura: fibras %.1f kN = f\'c(Ag - As) + fy As; ACI con 0.85 da %.1f'
           % (max(q['P_kN'] for q in pts), vrc.compresion_pura(sec)))

    filas = demandas_del_anexo(ctx, COLUMNA, 'columna', None)
    peor_u = max(abs(x['u'] - x['u_anexo']) for x in filas)
    f.check(peor_u <= 0.5e-6 + 1e-9,
            'la u de los 15 casos, rehecha con demanda_capacidad sobre los esfuerzos del anexo, '
            '= la del anexo (peor %.1e; el anexo escribe 6 decimales)' % peor_u)
    diseno = [x for x in filas if x['caso'] not in NO_DE_DISENO and x['caso'] not in CASOS]
    g = max(diseno, key=lambda x: x['u'])
    f.check(g['u'] < 1.0,
            'gobierna %s: P = %.1f kN, M = %.1f kN m, Mn = %.1f kN m, u = %.3f, PASA'
            % (g['caso'], g['P'], g['M'], g['Mn'], g['u']),
            'Mn nominal, sin phi; M = resultante sqrt(My2 + Mz2) contra una curva uniaxial')
    f.numero = 'extremos exactos; flexion %.1f %%; u = %.3f en %s' % (
        100 * rel(p0['M_kNm'], w['M_kNm']), g['u'], g['caso'])
    f.criterio = 'traccion = -As fy; flexion vs Whitney <= 2 %; anexo = interaccion; u rehecha = anexo'
    return f


def fila_pm_muro(ctx):
    f = Fila('P-M muro', 'python semana03/verificar_rc.py conjunto 100537 (y 200009)')
    modelo = ctx['modelo']
    numeros = []
    for eid in MUROS:
        e = next(x for x in modelo['elementos'] if int(x['id']) == eid)
        sec = capacidad.desde_elemento(modelo, eid)
        _ea, fam = familia_del_anexo(ctx['anexo'], eid)
        plano = dc.momento_en_el_plano_de(modelo, e)
        print('    muro %d, %s, %.2f x %.2f m, f\'c %.0f MPa, %d barras, As %.2f cm2, '
              'momento del plano %s' % (eid, sec.nombre, sec.b, sec.h, sec.fpc / 1000.0,
                                        len(sec.barras), sec.As * 1e4, plano))
        pts = curva_igual_al_anexo(f, sec, fam)

        filas = demandas_del_anexo(ctx, eid, 'muro', plano)
        ey = next(x for x in filas if x['caso'] == 'EY')
        f.check(ey['M'] > 10 * ey['fuera'],
                '%d: el momento del plano (%s, por inercias) es el grande: en EY %.1f contra %.1f '
                'kN m fuera del plano' % (eid, plano, ey['M'], ey['fuera']))
        t = min(pts, key=lambda q: q['P_kN'])
        f.check(rel(t['P_kN'], -vrc.traccion_pura(sec)) <= 1e-9,
                '%d: traccion pura fibras %.1f = -As fy %.1f kN'
                % (eid, t['P_kN'], -vrc.traccion_pura(sec)))

        # Flexion pura, desarmada. verificar_rc compara Whitney en UN
        # sentido contra el menor de los dos de las fibras; aca se toma
        # el mismo sentido y se sacan, de a una, las dos cosas que las
        # separan: el mallado y el endurecimiento de Steel01.
        otra = capacidad.espejo(sec)
        with traz.AvisosDeOpenSees():
            m20 = [capacidad.momento_curvatura(s, P=0.0)['M_aci'] for s in (sec, otra)]
            m40 = [capacidad.momento_curvatura(s, P=0.0, nf=40)['M_aci'] for s in (sec, otra)]
            k = 0 if m20[0] <= m20[1] else 1
            s_k = (sec, otra)[k]
            plano_ = copy.copy(s_k)
            plano_.endurecimiento = 0.0
            m40_se = capacidad.momento_curvatura(plano_, P=0.0, nf=40)['M_aci']
        w_dir = vrc.flexion_pura(sec)['M_kNm']
        w_k = vrc.flexion_pura(s_k)['M_kNm']
        f.info('%d flexion pura, como la imprime verificar_rc: Whitney %.1f contra fibras %.1f '
               'kN m (%+.1f %%)' % (eid, w_dir, min(m20), 100 * (w_dir / min(m20) - 1)))
        f.info('  en el sentido que manda (%s): 20 fibras %.1f -> 40 fibras %.1f -> sin '
               'endurecimiento %.1f; Whitney %.1f'
               % ('directo' if k == 0 else 'espejado', m20[k], m40[k], m40_se, w_k))
        resid = rel(m40_se, w_k)
        f.check(resid <= TOL_MODELOS,
                '%d: con el mismo sentido, sin endurecimiento y con 40 fibras, fibras = Whitney '
                'al %.2f %%' % (eid, 100 * resid))
        mall = rel(m20[k], m40[k])
        if mall > TOL_MALLADO:
            f.abierto('%d: el mallado de 20 fibras no alcanza en un muro de %.2f m: a P = 0 '
                      'sobreestima Mn en %.1f %% contra 40 (capacidad.py declara < 0.5 %%)'
                      % (eid, sec.h, 100 * mall))
        endu = rel(m40[k], m40_se)
        if endu > TOL_MODELOS:
            f.abierto('%d: cerca de P = 0 la curva incluye el endurecimiento de Steel01 (+%.1f %%): '
                      'no es la capacidad nominal de ACI' % (eid, 100 * endu))

        diseno = [x for x in filas if x['caso'] not in NO_DE_DISENO and x['caso'] not in CASOS]
        g = max(diseno, key=lambda x: x['u'])
        with traz.AvisosDeOpenSees():
            fina = capacidad.interaccion(sec, nf=40)
        Mn_f = dc.capacidad_en(g['P'], fina)
        f.check(g['u'] < 1.0 and g['M'] / Mn_f < 1.0,
                '%d gobierna %s: P = %.1f kN, M = %.1f kN m, Mn = %.1f, u = %.3f (con 40 fibras '
                '%.3f), PASA' % (eid, g['caso'], g['P'], g['M'], g['Mn'], g['u'], g['M'] / Mn_f))
        peor_u = max(abs(x['u'] - x['u_anexo']) for x in filas if math.isfinite(x['u']))
        f.check(peor_u <= 0.5e-6 + 1e-9,
                '%d: u rehecha = u del anexo en los 15 casos (peor %.1e)' % (eid, peor_u))
        numeros.append('%d u = %.3f (%.3f fino)' % (eid, g['u'], g['M'] / Mn_f))
    f.numero = '; '.join(numeros)
    f.criterio = 'extremos exactos; plano por inercias; fibras = Whitney con las mismas hipotesis <= 2 %'
    return f


# ============================================================
# IDS UNITY
# ============================================================
def correr(args, timeout=900):
    t = time.time()
    r = subprocess.run([sys.executable] + args, cwd=rutas.RAIZ, capture_output=True,
                       text=True, encoding='utf-8', errors='replace', timeout=timeout)
    return r.returncode, r.stdout + r.stderr, time.time() - t


def fila_ids(ctx):
    f = Fila('IDs Unity', 'python comun/test_contrato_unity.py conjunto')
    rc, out, seg = correr(['comun/test_contrato_unity.py', EDIFICIO])
    f.check(rc == 0 and 'SANO' in out,
            'comun/test_contrato_unity.py conjunto: exit %d en %.1f s, "%s"'
            % (rc, seg, 'EL CONTRATO JSON <-> UNITY ESTA SANO' if 'SANO' in out else 'sin cierre'))

    modelo = ctx['modelo']
    with io.open(rutas.unity(EDIFICIO), encoding='utf-8') as fh:
        visor = json.load(fh)
    nm = {int(n['id']): (n['x'], n['y'], n['z']) for n in modelo['nodos']}
    nv = {int(n['id']): (n['x'], n['y'], n['z']) for n in visor['nodos']}
    dxyz = max((max(abs(a - b) for a, b in zip(nm[i], nv[i])) for i in nm if i in nv), default=0.0)
    f.check(set(nm) == set(nv) and dxyz == 0.0,
            'nodos: %d en el modelo y %d en el visor, mismos tags, max |dxyz| = %.1e m'
            % (len(nm), len(nv), dxyz))
    clave = lambda e: (int(e['n1']), int(e['n2']), e['tipo'], e['seccion'])
    em = {int(e['id']): clave(e) for e in modelo['elementos']}
    ev = {int(e['id']): clave(e) for e in visor['elementos']}
    distintos = [i for i in em if ev.get(i) != em[i]]
    f.check(set(em) == set(ev) and not distintos,
            'elementos: %d en el modelo y %d en el visor, mismos tags, nodos, tipo y seccion'
            % (len(em), len(ev)))

    linea, codigo = traz.regla_de_nombre_en_visor()
    f.check(linea is not None,
            'el visor nombra cada barra con %s (VisorEstructura.cs:%s)' % (traz.LITERAL_NOMBRE, linea))
    anexo = ctx['anexo']['elementos']
    mal_obj = [e['id'] for e in anexo if e['objeto_unity'] != 'Elem_%d_%s' % (e['id'], e['tipo'])]
    mal_tag = [e['id'] for e in anexo if not e['tag_opensees'].startswith(
        'element elasticBeamColumn %d %d %d ' % (e['id'], e['n1'], e['n2']))]
    f.check({e['id'] for e in anexo} == set(em) and not mal_obj and not mal_tag,
            'anexo: %d elementos; objeto_unity = Elem_<tag>_<tipo> y tag_opensees = "element '
            'elasticBeamColumn <tag> <n1> <n2>" en todos' % len(anexo),
            'ej.: %s | %s' % next((e['objeto_unity'], e['tag_opensees'][:52])
                                  for e in anexo if e['id'] == COLUMNA))
    f.numero = '%d nodos y %d elementos: mismo tag en modelo, visor, anexo y GameObject' % (len(nm), len(em))
    f.criterio = 'contrato sano; 0 diferencias de tag, nodos, tipo, seccion y coordenadas'
    return f


# ============================================================
# AR
# ============================================================
def evidencia_del_iphone():
    if not os.path.isdir(IPHONE):
        return []
    return sorted(n for n in os.listdir(IPHONE)
                  if n.lower().endswith(('.jpg', '.jpeg', '.png', '.heic', '.mp4', '.mov')))


def fila_ar(ctx, completo):
    args = ['semana06_lab/verificar_ar.py'] + ([] if completo else ['--sin-navegador'])
    f = Fila('AR', 'python ' + ' '.join(args))
    rc, out, seg = correr(args)
    bloques = '[1] a [4]' if completo else '[1], [2] y [3a]'
    f.check(rc == 0 and 'FALLA' not in out,
            'semana06_lab/verificar_ar.py %s: exit %d en %.1f s' % (bloques, rc, seg),
            '[1] mismos elementTag/nodeTag que OpenSees; [2] cada numero de la app = anexo, '
            'bit a bit; %s' % ('[3] pose y transformacion de ar.js = Python; [4] tracking con '
                               'video sintetico' if completo else
                               '[3a] pose del marcador (ar.js y el tracking: --ar-completo)'))
    for linea in out.splitlines():
        if 'numeros' in linea and 'identicos' in linea:
            f.info(linea.strip().replace('[OK  ] ', ''))
        if completo and 'distancia estimada' in linea:
            f.info(linea.strip().replace('[OK  ] ', ''))
    fotos = evidencia_del_iphone()
    if fotos:
        f.check(True, 'evidencia del iPhone en %s: %s'
                % (ruta_rel(IPHONE), ', '.join(fotos)))
    else:
        f.abierto('sin prueba en un iPhone: %s no tiene capturas. Todo lo anterior corre en '
                  'Chrome de escritorio' % ruta_rel(IPHONE))
    f.numero = ('app = OpenSees bit a bit; pose del marcador'
                + ('; ar.js = Python; tracking sintetico' if completo else '')
                + ('' if fotos else '; sin iPhone'))
    f.criterio = 'verificar_ar.py sin FALLA; una captura del telefono en evidencia/iphone/'
    return f


# ============================================================
def tabla(filas):
    ancho = max(len(x.prueba) for x in filas)
    print()
    print('=' * 78)
    print('  QA FINAL ESTRUCTURAL: CONJUNTO (%s)' % datetime.date.today().isoformat())
    print('=' * 78)
    for x in filas:
        print('  %-*s  %-7s  %s' % (ancho, x.prueba, x.estado, x.numero))
    print('=' * 78)


def git(*args):
    try:
        return subprocess.run(['git'] + list(args), cwd=rutas.RAIZ, capture_output=True,
                              text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ''


def escribir(filas, ctx, segundos):
    os.makedirs(EVIDENCIA, exist_ok=True)
    ruta = os.path.join(EVIDENCIA, 'qa_semana06.md')
    sucio = git('status', '--porcelain', '--', '.', ':!unity/Library', ':!unity/Temp',
                ':!unity/Logs', ':!unity/obj', ':!semana06/evidencia')
    lineas = [
        '# QA final estructural del conjunto',
        '',
        'Generado por `python semana06/verificar_semana06.py --salida` el %s, sobre el '
        'commit `%s`%s, en %.0f s. No se edita a mano.'
        % (datetime.datetime.now().strftime('%Y-%m-%d %H:%M'), git('rev-parse', '--short', 'HEAD'),
           ' con cambios sin commitear' if sucio else '', segundos),
        '',
        'Modelo: `data/modelo/conjunto.json` (%d nodos, %d elementos). Anexo: %s.'
        % (len(ctx['modelo']['nodos']), len(ctx['modelo']['elementos']), ctx['origen_anexo']),
        '',
        '| Prueba | Estado | Número | Criterio | Comando |',
        '|---|---|---|---|---|',
    ]
    for x in filas:
        lineas.append('| %s | **%s** | %s | %s | `%s` |'
                      % (x.prueba, x.estado, celda(x.numero), celda(x.criterio), x.comando))
    abiertos = [(x.prueba, a) for x in filas for a in x.abiertos]
    if abiertos:
        lineas += ['', '**Lo abierto** (lo que deja una fila en PARCIAL, medido por la misma prueba):', '']
        lineas += ['- %s: %s' % pa for pa in abiertos]
    fallas = [(x.prueba, a) for x in filas for a in x.fallas]
    if fallas:
        lineas += ['', '**FALLAS:**', '']
        lineas += ['- %s: %s' % pa for pa in fallas]
    with io.open(ruta, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lineas) + '\n')
    print('  escrito %s' % ruta_rel(ruta))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--salida', action='store_true',
                    help='escribe semana06/evidencia/qa_semana06.md')
    ap.add_argument('--ar-completo', action='store_true',
                    help='corre verificar_ar.py entero, con el tracking en Chrome')
    a = ap.parse_args(argv)
    t0 = time.time()

    print('=' * 78)
    print('  SEMANA 6: QA FINAL ESTRUCTURAL, EN VIVO')
    print('=' * 78)
    ctx = contexto()
    print('  modelo  data/modelo/conjunto.json (%d nodos, %d elementos)'
          % (len(ctx['modelo']['nodos']), len(ctx['modelo']['elementos'])))
    print('  anexo   %s (%d casos)' % (ctx['origen_anexo'], len(ctx['anexo']['casos'])))
    print('  casos   G, Q, EX y EY del anexo (lab_semana03.armar_casos), resueltos ahora')

    pasos = [('Equilibrio G', lambda: fila_equilibrio(ctx, 'G')),
             ('Equilibrio Q', lambda: fila_equilibrio(ctx, 'Q')),
             ('Corte basal EX', lambda: fila_corte(ctx, 'EX')),
             ('Corte basal EY', lambda: fila_corte(ctx, 'EY')),
             ('Superposicion', lambda: fila_superposicion(ctx)),
             ('M-phi', lambda: fila_mphi(ctx)),
             ('P-M columna', lambda: fila_pm_columna(ctx)),
             ('P-M muro', lambda: fila_pm_muro(ctx)),
             ('IDs Unity', lambda: fila_ids(ctx)),
             ('AR', lambda: fila_ar(ctx, a.ar_completo))]
    filas = []
    for nombre, hacer in pasos:
        titulo(nombre.upper())
        t = time.time()
        x = hacer()
        x.segundos = time.time() - t
        filas.append(x)

    tabla(filas)
    if a.salida:
        escribir(filas, ctx, time.time() - t0)
    fallas = [x.prueba for x in filas if x.estado == 'FALLA']
    if fallas:
        print('  FALLA: %s' % ', '.join(fallas))
        return 1
    parciales = [x.prueba for x in filas if x.estado == 'PARCIAL']
    print('  %d OK y %d PARCIAL%s, 0 FALLA (%.0f s)'
          % (len(filas) - len(parciales), len(parciales),
             (' (%s)' % ', '.join(parciales)) if parciales else '', time.time() - t0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
