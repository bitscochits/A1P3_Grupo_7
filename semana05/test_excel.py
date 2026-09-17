# -*- coding: utf-8 -*-
r"""
================================================================
 semana05/test_excel.py  -  EL EXCEL DICE LO MISMO QUE PYTHON
================================================================
 Relee el libro que escribe comun/excel.py y lo compara, celda a celda,
 contra la fuente de la que salio. Escribe SOLO en una carpeta temporal:
 no toca data/ ni results/.

 Correr (desde la raiz del repo):

   .venv\Scripts\python.exe semana05\test_excel.py lt2
   .venv\Scripts\python.exe semana05\test_excel.py lt2 ingenieria conjunto
   .venv\Scripts\python.exe semana05\test_excel.py lt2 --cs 0.20
   .venv\Scripts\python.exe semana05\test_excel.py lt2 --rapido

   --rapido          la segunda generacion reusa el anexo (no lo rearma)
   --sin-reanalisis  no prueba el libro de /analizar
   --ver-avisos      deja pasar los avisos de OpenSees (curvas P-M)

 Sale con 1 si algo falla.

 ----------------------------------------------------------------
 QUE COMPRUEBA, POR EDIFICIO
 ----------------------------------------------------------------
 [1] Estructura, leida del XML y no con openpyxl: las hojas y su orden,
     encabezados con unidad, fila 1 congelada, autofiltro sobre todo el
     rango de datos, el formato condicional de D/C (rojo > 1, ambar
     0.9-1), cero formulas, fechas fijas en las propiedades.
 [2] Exactitud contra construir_anexo (el mismo anexo, armado UNA vez
     aca): nodos, desplazamientos (m -> mm, cota del redondeo a 5
     decimales), elementos, esfuerzos en i y j, reacciones, D/C, curvas.
 [3] Independientes del escritor:
     - la suma FILTRADA de la hoja Reacciones ("Cuenta en ..." = si) es
       calcular.equilibrio, con cota 0.5e-4 kN por fila sumada: cada
       reaccion viene redondeada a 4 decimales;
     - la suma de la columna ENTERA no lo es (se imprime, es la trampa);
     - esfuerzo en i = -f_i exacto y en j = +f_j con la cota de cierre
       del exportador (exportar_unity.cota_de_cierre) mas dos redondeos:
       la convencion traccion positiva, contra OpenSees;
     - D/C = M/Mn con la cota del redondeo; estado coherente con D/C;
     - la carga aplicada de una combinacion es la suma lambda * la de
       sus casos, con la cota de un redondeo por termino;
     - el Resumen (NO PASA, peor D/C, |u| max) sale de las otras hojas;
     - ninguna celda con 9999, inf, NaN ni un numero guardado como texto.
 [4] Determinismo: una segunda generacion (por defecto desde cero, con
     escribir_libro_anexo) da el mismo sha256.
 [5] El libro versionado data/excel/<ed>_resultados.xlsx, si se prueba
     con los parametros por defecto: sus celdas son las de la
     generacion de ahora (si no, esta desactualizado: regenerarlo).
 [6] Archivo abierto en Excel: PermissionError con mensaje claro, antes
     de calcular, y sin dejar temporales (solo Windows).
 [7] El libro del reanalisis (escribir_libro_reanalisis) con una
     respuesta REAL de servidor_opensees.construir_y_resolver sobre
     data/unity/<ed>.json: forma multi-caso (equilibrio del servidor) y
     plana (equilibrio calculado al escribir), secciones en diccionario,
     y /analizar por app.test_client() con el libro desviado al temporal.
================================================================
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                'comun'))
import rutas                                 # noqa: E402

rutas.entrar(__file__)
import excel                                 # noqa: E402
import exportar_excel                        # noqa: E402  (desviar_stderr)

HOJAS_ANEXO = ['LEEME', 'Resumen', 'Nodos', 'Desplazamientos', 'Elementos', 'Esfuerzos',
               'Reacciones', 'Demanda-capacidad', 'Curvas P-M', 'Supuestos']
HOJAS_REANALISIS = ['LEEME', 'Resumen', 'Nodos', 'Desplazamientos', 'Elementos', 'Esfuerzos',
                    'Reacciones']
HOJAS_DE_TEXTO = ('LEEME', 'Supuestos')

# Los encabezados que lee una persona (y que cita la hoja LEEME). Si
# cambian, cambia lo que hay que explicar: que el test lo diga.
ENC_DESPLAZAMIENTOS = ['Caso', 'Nodo', 'z [m]', 'ux [mm]', 'uy [mm]', 'uz [mm]', '|u| [mm]',
                       'rx [rad]', 'ry [rad]', 'rz [rad]']
ENC_ESFUERZOS = ['Caso', 'Elemento', 'Tipo', 'Extremo', 'x [m]', 'N [kN]', 'Vy [kN]',
                 'Vz [kN]', 'T [kN·m]', 'My [kN·m]', 'Mz [kN·m]']
ENC_REACCIONES = ['Caso', 'Nodo', 'Fx [kN]', 'Fy [kN]', 'Fz [kN]', 'Mx [kN·m]', 'My [kN·m]',
                  'Mz [kN·m]', 'Nodo en diafragma', 'Cuenta en Fx/Fy', 'Cuenta en Fz']
ENC_DC = ['Caso', 'Elemento', 'Tipo', 'Sección', 'Familia P-M', 'Extremo', 'P [kN]',
          'M [kN·m]', 'M fuera del plano [kN·m]', 'Mn [kN·m]', 'D/C [-]', 'Estado']
MAGNITUDES = ('N', 'Vy', 'Vz', 'T', 'My', 'Mz')

# Cotas, cada una contra su causa (CLAUDE.md 7.3):
REDONDEO_KN = 5e-5              # el servidor redondea fuerzas a 4 decimales
REDONDEO_MM = 5e-6              # el libro redondea mm a 5 decimales (= 8 en m)
REDONDEO_M_EN_MM = 5e-9 * 1000  # el anexo redondea m a 8 decimales
REDONDEO_U = 5e-7               # el anexo redondea u = M/Mn a 6 decimales
REDONDEO_UMAX_MM = 5e-5         # el anexo redondea max_desplazamiento_mm a 4 decimales
COMA_FLOTANTE = 1e-12           # relativo: una suma y un producto de doubles
# openpyxl guarda cada numero con 16 cifras significativas ("%.16g" en
# openpyxl.compat.strings.safe_string): 16.435000000000002 queda 16.435.
# El error relativo es a lo mas 5e-16 mas un ULP al releer; Excel muestra
# 15 cifras. Toda comparacion "exacta" lleva esta cota y nada mas.
CIFRAS_OPENPYXL = 1e-15
FECHA_FIJA_XML = '2026-01-01T00:00:00Z'

fallos = []


def check(cond, msg, detalle=''):
    print('  [%s] %s' % ('OK  ' if cond else 'FALLA', msg))
    for linea in ([detalle] if isinstance(detalle, str) else detalle):
        if linea:
            print('         %s' % linea)
    if not cond:
        fallos.append(msg)
    return cond


def aviso(msg):
    print('  [--  ] %s' % msg)


class Cotejo(object):
    """Cuenta celdas comparadas y guarda las primeras diferencias."""

    def __init__(self):
        self.n = 0
        self.malas = 0
        self.ejemplos = []

    def igual(self, donde, celda, esperado, cota=0.0):
        self.n += 1
        if esperado is None or isinstance(esperado, str):
            ok = celda == esperado
        elif isinstance(celda, bool) or not isinstance(celda, (int, float)):
            ok = False
        else:
            ok = abs(float(celda) - float(esperado)) <= cota + CIFRAS_OPENPYXL * abs(float(esperado))
        if not ok:
            self.malas += 1
            if len(self.ejemplos) < 4:
                self.ejemplos.append('%s: celda %r, fuente %r (cota %g)'
                                     % (donde, celda, esperado, cota))
        return ok

    def informe(self, msg):
        check(self.n > 0 and self.malas == 0,
              '%s: %d celdas, %d distintas' % (msg, self.n, self.malas), self.ejemplos)


def tabla(libro, hoja):
    """(encabezados, [dict por fila]) de una hoja releida."""
    filas = libro[hoja]
    enc = list(filas[0])
    return enc, [dict(zip(enc, list(f) + [None] * (len(enc) - len(f)))) for f in filas[1:]]


def sha256(ruta):
    with open(ruta, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def letra(j):
    from openpyxl.utils import get_column_letter
    return get_column_letter(j)


def cota_float(*valores):
    return COMA_FLOTANTE * max([1.0] + [abs(float(v)) for v in valores])


# ============================================================
# [1] ESTRUCTURA
# ============================================================
def probar_estructura(ruta, libro, esperadas, reglas_dc):
    est = excel.estructura(ruta)
    check(est['hojas'] == esperadas, 'hojas en orden: %s' % ', '.join(est['hojas']),
          '' if est['hojas'] == esperadas else 'se esperaba %s' % esperadas)
    malas = []
    for nombre in est['hojas']:
        h = est['por_hoja'][nombre]
        filas = libro[nombre]
        ncol = len(filas[0])
        if not h['panel'] or h['panel'].get('state') != 'frozen' or h['panel'].get('ySplit') != '1':
            malas.append('%s: fila 1 no congelada (%s)' % (nombre, h['panel']))
        if h['formulas']:
            malas.append('%s: %d formulas' % (nombre, h['formulas']))
        if h['anchos'] != ncol:
            malas.append('%s: %d anchos para %d columnas' % (nombre, h['anchos'], ncol))
        if nombre not in HOJAS_DE_TEXTO:
            ref = 'A1:%s%d' % (letra(ncol), max(2, len(filas)))
            if h['filtro'] != ref:
                malas.append('%s: autofiltro %s, se esperaba %s' % (nombre, h['filtro'], ref))
        for titulo in reglas_dc.get(nombre, []):
            col = letra(filas[0].index(titulo) + 1)
            rango = '%s2:%s%d' % (col, col, max(2, len(filas)))
            esperado = sorted([(rango, 'greaterThan', ['1.0']),
                               (rango, 'between', ['0.9', '1.0'])])
            if sorted(h['reglas']) != esperado:
                malas.append('%s: formato condicional %s, se esperaba %s'
                             % (nombre, h['reglas'], esperado))
    check(not malas, 'fila congelada, autofiltro, anchos, colores de D/C y 0 formulas en '
                     'las %d hojas' % len(est['hojas']), malas)
    core = est['propiedades']
    check(core.count(FECHA_FIJA_XML) == 2,
          'propiedades con fecha fija (created y modified = %s)' % FECHA_FIJA_XML)
    n_enlaces = est['por_hoja']['LEEME']['enlaces']
    check(n_enlaces == len(esperadas) - 1,
          'LEEME enlaza a las otras %d hojas (%d enlaces)' % (len(esperadas) - 1, n_enlaces))


def probar_celdas_limpias(libro):
    r"""Ni 9999, ni inf/NaN, ni numeros guardados como texto."""
    malas, n = [], 0
    for nombre, filas in libro.items():
        for i, f in enumerate(filas[1:], start=2):
            for j, v in enumerate(f):
                n += 1
                donde = '%s!%s%d' % (nombre, letra(j + 1), i)
                if isinstance(v, float) and not math.isfinite(v):
                    malas.append('%s = %r' % (donde, v))
                elif isinstance(v, (int, float)) and not isinstance(v, bool) and v == 9999:
                    malas.append('%s = 9999 (centinela escrito como dato)' % donde)
                elif isinstance(v, str) and nombre not in HOJAS_DE_TEXTO:
                    try:
                        float(v.replace(',', '.'))
                        malas.append('%s = %r: numero guardado como texto' % (donde, v))
                    except ValueError:
                        pass
                if isinstance(v, str) and v.strip().lower() in ('inf', '-inf', 'nan', '9999',
                                                                 '9999.0'):
                    malas.append('%s = %r' % (donde, v))
    check(not malas, 'ninguna celda con 9999, inf, NaN o numero como texto (%d celdas)' % n,
          malas[:5])


# ============================================================
# [2] y [3] EL LIBRO DEL ANEXO CONTRA SU FUENTE
# ============================================================
def equilibrios_independientes(anexo, ctx):
    r"""{caso: (equilibrio, reacciones)} armado aca, sin comun/excel.py."""
    import calcular
    import combinar
    datos, res, casos = ctx['datos'], ctx['resultados'], ctx['arm']['casos']
    salida = {}
    for c in anexo['casos']:
        if c['tipo'] == 'caso':
            caso, r = casos[c['nombre']], res[c['nombre']]
        else:
            activos = {k: float(v) for k, v in zip(excel.CASOS_BASE, c['factores']) if v}
            caso = combinar.combinar_cargas(datos, activos, c['nombre'])
            r = combinar.combinar_resultados(res, activos)
        salida[c['nombre']] = (calcular.equilibrio(datos, caso, r), r['reacciones'])
    return salida


def probar_reacciones(libro, casos, equilibrios, hoja_resumen=None):
    r"""
    Valores fila a fila y la suma FILTRADA contra calcular.equilibrio.
    casos: [nombre]; equilibrios: {nombre: (eq, reacciones)}.
    """
    enc, filas = tabla(libro, 'Reacciones')
    check(enc == ENC_REACCIONES, 'Reacciones: encabezados %s' % enc,
          '' if enc == ENC_REACCIONES else 'se esperaba %s' % ENC_REACCIONES)
    cot = Cotejo()
    por_caso = {}
    for f in filas:
        por_caso.setdefault(f['Caso'], []).append(f)
    peor, lineas = 0.0, []
    for nombre in casos:
        eq, reacciones = equilibrios[nombre]
        propias = por_caso.get(nombre, [])
        cot.igual('%s: filas' % nombre, len(propias), len(reacciones))
        fuente = sorted(reacciones, key=lambda r: int(r['id']))
        for f, r in zip(propias, fuente):
            cot.igual('%s nodo' % nombre, f['Nodo'], int(r['id']))
            for k, col in zip(('fx', 'fy', 'fz', 'mx', 'my', 'mz'), enc[2:8]):
                v = float(r[k])
                cot.igual('%s nodo %s %s' % (nombre, r['id'], col), f[col], v,
                          REDONDEO_KN + cota_float(v))
        total, bruto, n = [0.0] * 3, [0.0] * 3, [0] * 3
        for f in propias:
            for i, (col, cuenta) in enumerate((('Fx [kN]', 'Cuenta en Fx/Fy'),
                                               ('Fy [kN]', 'Cuenta en Fx/Fy'),
                                               ('Fz [kN]', 'Cuenta en Fz'))):
                bruto[i] += f[col]
                if f[cuenta] == excel.SI:
                    total[i] += f[col]
                    n[i] += 1
        for i in range(3):
            cota = REDONDEO_KN * (n[i] + 1) + cota_float(total[i])
            error = abs(total[i] - float(eq['reaccion_kN'][i]))
            peor = max(peor, error / cota)
            if error > cota:
                cot.malas += 1
                cot.ejemplos.append('%s eje %d: filtrada %.6f, equilibrio %.6f, cota %.2e'
                                    % (nombre, i, total[i], eq['reaccion_kN'][i], cota))
            cot.n += 1
        lineas.append('%-16s Fx filtrada %11.4f  equilibrio %11.4f  columna entera %11.4f'
                      % (nombre, total[0], eq['reaccion_kN'][0], bruto[0]))
        lineas.append('%-16s Fz filtrada %11.4f  equilibrio %11.4f  columna entera %11.4f'
                      % ('', total[2], eq['reaccion_kN'][2], bruto[2]))
    cot.informe('Reacciones: valores y suma filtrada = calcular.equilibrio (peor error/cota '
                '%.3f)' % peor)
    for l in lineas:
        print('         %s' % l)
    return por_caso


def probar_anexo(ed, anexo, ctx, ruta, argv):
    import calcular                              # noqa: F401  (import por ruta de comun)
    ex4 = excel._exportador_semana04()
    libro = excel.leer(ruta)
    reglas = {'Resumen': ['Peor D/C [-]'], 'Demanda-capacidad': ['D/C [-]']}
    print('  -- [1] estructura')
    probar_estructura(ruta, libro, HOJAS_ANEXO, reglas)
    probar_celdas_limpias(libro)
    vacios = ['%s columna %d' % (nombre, j + 1) for nombre in HOJAS_ANEXO
              for j, e in enumerate(libro[nombre][0]) if e is None or not str(e).strip()]
    check(not vacios, 'todas las columnas con encabezado (%d columnas)'
          % sum(len(libro[n][0]) for n in HOJAS_ANEXO), vacios[:5])

    print('  -- [2] celdas contra construir_anexo')
    modelo = ctx['modelo']
    nombres = [c['nombre'] for c in anexo['casos']]

    # Nodos
    _enc, filas = tabla(libro, 'Nodos')
    cot = Cotejo()
    fuente = sorted(modelo['nodos'], key=lambda n: int(n['id']))
    cot.igual('filas', len(filas), len(fuente))
    for f, nd in zip(filas, fuente):
        cot.igual('nodo', f['Nodo'], int(nd['id']))
        for k in ('x', 'y', 'z'):
            cot.igual('nodo %s %s' % (nd['id'], k), f['%s [m]' % k], float(nd[k]))
    cot.informe('Nodos (%d)' % len(fuente))

    # Desplazamientos
    enc, filas = tabla(libro, 'Desplazamientos')
    check(enc == ENC_DESPLAZAMIENTOS, 'Desplazamientos: encabezados en mm y rad')
    cot = Cotejo()
    esperadas = sum(len(c['desplazamientos']) for c in anexo['casos'])
    cot.igual('filas', len(filas), esperadas)
    it = iter(filas)
    max_por_caso = {}
    for c in anexo['casos']:
        for d in sorted(c['desplazamientos'], key=lambda d: int(d['id'])):
            f = next(it, None)
            if f is None:
                break
            donde = '%s nodo %s' % (c['nombre'], d['id'])
            cot.igual(donde, f['Caso'], c['nombre'])
            cot.igual(donde, f['Nodo'], int(d['id']))
            for k in ('ux', 'uy', 'uz'):
                v = 1000.0 * float(d[k])
                cot.igual('%s %s' % (donde, k), f['%s [mm]' % k], v, REDONDEO_MM + cota_float(v))
            norma = 1000.0 * math.sqrt(sum(float(d[k]) ** 2 for k in ('ux', 'uy', 'uz')))
            cot.igual('%s |u|' % donde, f['|u| [mm]'], norma, REDONDEO_MM + cota_float(norma))
            for k in ('rx', 'ry', 'rz'):
                cot.igual('%s %s' % (donde, k), f['%s [rad]' % k], float(d[k]))
            m = max_por_caso.get(c['nombre'])
            if m is None or f['|u| [mm]'] > m[0]:
                max_por_caso[c['nombre']] = (f['|u| [mm]'], f['Nodo'])
    cot.informe('Desplazamientos (%d filas = nodos x %d casos; mm con cota %.0e)'
                % (esperadas, len(nombres), REDONDEO_MM))

    # Elementos
    _enc, filas = tabla(libro, 'Elementos')
    cot = Cotejo()
    cot.igual('filas', len(filas), len(anexo['elementos']))
    for f, e in zip(filas, anexo['elementos']):
        donde = 'elemento %s' % e['id']
        cot.igual(donde, f['Elemento'], int(e['id']))
        cot.igual(donde, f['Nodo i'], int(e['n1']))
        cot.igual(donde, f['Nodo j'], int(e['n2']))
        for col, k in (('L [m]', 'L'), ('A [m²]', 'A'), ('Iy [m⁴]', 'Iy'), ('Iz [m⁴]', 'Iz'),
                       ('J [m⁴]', 'J'), ('E [kPa]', 'E_kPa'), ('G [kPa]', 'G_kPa')):
            cot.igual('%s %s' % (donde, col), f[col], float(e[k]))
        cot.igual('%s familia' % donde, f['Familia P-M'],
                  int(e['familia']) if int(e['familia']) >= 0 else None)
        cot.igual('%s seccion' % donde, f['Sección'], e['seccion'])
    cot.informe('Elementos (%d)' % len(anexo['elementos']))

    # Esfuerzos: extremos del anexo, y contra f de OpenSees
    enc, filas = tabla(libro, 'Esfuerzos')
    check(enc == ENC_ESFUERZOS, 'Esfuerzos: encabezados en kN y kN·m')
    cot, cierre = Cotejo(), Cotejo()
    esperadas = 2 * sum(len(c['esfuerzos']) for c in anexo['casos'])
    cot.igual('filas', len(filas), esperadas)
    it = iter(filas)
    peor_cierre = 0.0
    for c in anexo['casos']:
        suma_lambdas = sum(abs(float(v)) for v in c['factores'])
        for s in c['esfuerzos']:
            fi, fj = next(it, None), next(it, None)
            if fi is None or fj is None:
                break
            f = [float(v) for v in s['f']]
            L = float(s['x'][-1])
            cotas = ex4.cota_de_cierre(L, suma_lambdas)
            for fila, extremo, k in ((fi, 'i', 0), (fj, 'j', -1)):
                donde = '%s elemento %s %s' % (c['nombre'], s['id'], extremo)
                cot.igual(donde, fila['Caso'], c['nombre'])
                cot.igual(donde, fila['Elemento'], int(s['id']))
                cot.igual(donde, fila['Extremo'], extremo)
                cot.igual(donde + ' x', fila['x [m]'], float(s['x'][k]))
                for m, col in zip(MAGNITUDES, enc[5:]):
                    cot.igual('%s %s' % (donde, m), fila[col], float(s[m][k]))
            for q, (m, col) in enumerate(zip(MAGNITUDES, enc[5:])):
                cierre.igual('%s %s %s en i' % (c['nombre'], s['id'], m), fi[col], -f[q])
                cota = cotas[q] + 2 * REDONDEO_KN + cota_float(f[6 + q], fj[col])
                error = abs(fj[col] - f[6 + q])
                peor_cierre = max(peor_cierre, error / cota)
                cierre.igual('%s %s %s en j' % (c['nombre'], s['id'], m), fj[col], f[6 + q], cota)
    cot.informe('Esfuerzos (%d filas = barras x casos x 2 extremos)' % esperadas)
    cierre.informe('Esfuerzos contra OpenSees: i = -f_i exacto, j = +f_j dentro de la cota de '
                   'cierre (peor error/cota %.3f)' % peor_cierre)

    # Demanda-capacidad
    enc, filas = tabla(libro, 'Demanda-capacidad')
    check(enc == ENC_DC, 'Demanda-capacidad: encabezados')
    cot, coherente = Cotejo(), Cotejo()
    por_id = {int(e['id']): e for e in anexo['elementos']}
    esperadas = sum(len(c['demandas']) for c in anexo['casos'])
    cot.igual('filas', len(filas), esperadas)
    it = iter(filas)
    dc_por_caso, n_fuera = {}, 0
    peor_u = 0.0
    for c in anexo['casos']:
        for d in c['demandas']:
            f = next(it, None)
            if f is None:
                break
            donde = '%s elemento %s' % (c['nombre'], d['id'])
            fuera = float(d['u']) >= excel.U_FUERA_DE_CURVA
            n_fuera += fuera
            cot.igual(donde, f['Caso'], c['nombre'])
            cot.igual(donde, f['Elemento'], int(d['id']))
            cot.igual(donde, f['Familia P-M'], int(d['familia']))
            cot.igual(donde, f['Extremo'], d['extremo'])
            cot.igual(donde + ' P', f['P [kN]'], float(d['P']))
            cot.igual(donde + ' M', f['M [kN·m]'], float(d['M']))
            cot.igual(donde + ' M fuera', f['M fuera del plano [kN·m]'],
                      float(d['M_fuera_plano']) if por_id[int(d['id'])]['tipo'] == 'muro'
                      else None)
            cot.igual(donde + ' Mn', f['Mn [kN·m]'], None if fuera else float(d['Mn']))
            cot.igual(donde + ' D/C', f['D/C [-]'], None if fuera else float(d['u']))
            dc_por_caso.setdefault(c['nombre'], []).append(f)
            # Independiente: estado coherente con D/C, y D/C = M/Mn.
            if fuera:
                coherente.igual(donde + ' estado', f['Estado'], excel.ESTADO_FUERA)
            else:
                coherente.igual(donde + ' estado', f['Estado'],
                                excel.ESTADO_PASA if f['D/C [-]'] <= 1.0 else excel.ESTADO_NO_PASA)
                Mn, M = f['Mn [kN·m]'], f['M [kN·m]']
                u = M / Mn
                cota = REDONDEO_U + REDONDEO_KN * (1.0 + u) / Mn + cota_float(u)
                peor_u = max(peor_u, abs(f['D/C [-]'] - u) / cota)
                coherente.igual(donde + ' D/C = M/Mn', f['D/C [-]'], u, cota)
    cot.informe('Demanda-capacidad (%d filas; %d con P fuera de la curva van vacias)'
                % (esperadas, n_fuera))
    coherente.informe('Demanda-capacidad: estado coherente y D/C = M/Mn (peor error/cota %.3f)'
                      % peor_u)

    # Curvas P-M
    _enc, filas = tabla(libro, 'Curvas P-M')
    cot = Cotejo()
    esperadas = sum(len(fam['P']) for fam in anexo['familias'])
    cot.igual('filas', len(filas), esperadas)
    it = iter(filas)
    for fam in anexo['familias']:
        for k in range(len(fam['P'])):
            f = next(it, None)
            if f is None:
                break
            donde = 'familia %s punto %d' % (fam['indice'], k + 1)
            cot.igual(donde, f['Familia P-M'], int(fam['indice']))
            cot.igual(donde, f['Punto'], k + 1)
            cot.igual(donde + ' P', f['P [kN]'], float(fam['P'][k]))
            cot.igual(donde + ' Mn', f['Mn [kN·m]'], float(fam['Mn'][k]))
            cot.igual(donde + ' Mmax', f['Mmax [kN·m]'], float(fam['Mmax'][k]))
    cot.informe('Curvas P-M (%d familias, %d puntos)' % (len(anexo['familias']), esperadas))

    print('  -- [3] independientes del escritor')
    equilibrios = equilibrios_independientes(anexo, ctx)
    probar_reacciones(libro, nombres, equilibrios)

    _enc, filas = tabla(libro, 'Resumen')
    cot, cruce = Cotejo(), Cotejo()
    cot.igual('filas', len(filas), len(anexo['casos']))
    aplicada_base = {c['nombre']: equilibrios[c['nombre']][0]['aplicada_kN']
                     for c in anexo['casos'] if c['tipo'] == 'caso'}
    for f, c in zip(filas, anexo['casos']):
        nombre = c['nombre']
        eq = equilibrios[nombre][0]
        cot.igual(nombre, f['Caso'], nombre)
        cot.igual(nombre, f['Descripción'], c['descripcion'])
        for k, v in zip(excel.CASOS_BASE, c['factores']):
            cot.igual('%s λ%s' % (nombre, k), f['λ%s [-]' % k], float(v))
        for i, eje in enumerate(('Fx', 'Fy', 'Fz')):
            cot.igual('%s aplicada %s' % (nombre, eje), f['Aplicada %s [kN]' % eje],
                      float(eq['aplicada_kN'][i]))
            cot.igual('%s reaccion %s' % (nombre, eje), f['Reacción %s [kN]' % eje],
                      float(eq['reaccion_kN'][i]))
            cot.igual('%s error %s' % (nombre, eje), f['Error %s [kN]' % eje],
                      float(eq['error_kN'][i]))
            if c['tipo'] != 'caso':
                suma = sum(float(l) * aplicada_base[k][i]
                           for k, l in zip(excel.CASOS_BASE, c['factores']))
                cota = REDONDEO_KN * (1.0 + sum(abs(float(l)) for l in c['factores'])) \
                    + cota_float(suma)
                cruce.igual('%s aplicada %s = suma lambda * casos' % (nombre, eje),
                            f['Aplicada %s [kN]' % eje], suma, cota)
        cot.igual(nombre + ' |u| max', f['|u| máx [mm]'], float(c['max_desplazamiento_mm']))
        cot.igual(nombre + ' Vx', f['Corte basal Vx [kN]'], abs(float(eq['reaccion_kN'][0])))
        cot.igual(nombre + ' Vy', f['Corte basal Vy [kN]'], abs(float(eq['reaccion_kN'][1])))
        # Del resto de las hojas:
        umax, nodo = max_por_caso[nombre]
        cruce.igual(nombre + ' |u| max = el mayor de Desplazamientos', f['|u| máx [mm]'], umax,
                    REDONDEO_UMAX_MM + REDONDEO_MM + REDONDEO_M_EN_MM * math.sqrt(3.0)
                    + cota_float(umax))
        cruce.igual(nombre + ' nodo del |u| max', f['Nodo del |u| máx'], nodo)
        dcs = dc_por_caso.get(nombre, [])
        cruce.igual(nombre + ' barras D/C', f['Barras revisadas D/C'], len(dcs))
        cruce.igual(nombre + ' NO PASA', f['NO PASA'],
                    sum(1 for d in dcs if d['Estado'] != excel.ESTADO_PASA))
        cruce.igual(nombre + ' fuera', f['P fuera de la curva'],
                    sum(1 for d in dcs if d['Estado'] == excel.ESTADO_FUERA))
        con_dc = [d['D/C [-]'] for d in dcs if d['D/C [-]'] is not None]
        cruce.igual(nombre + ' peor D/C', f['Peor D/C [-]'], max(con_dc) if con_dc else None)
    cot.informe('Resumen contra construir_anexo y calcular.equilibrio (%d casos)'
                % len(anexo['casos']))
    cruce.informe('Resumen contra las otras hojas (|u| max, NO PASA, peor D/C) y aplicada de '
                  'cada combinacion = suma lambda * casos')

    # Textos: lo que una persona necesita leer antes de usar el libro.
    leeme = '\n'.join(str(v) for f in libro['LEEME'] for v in f if v is not None)
    faltan = [t for t in ['NO sumes la columna entera', 'NOMINAL', 'P fuera de la curva',
                          excel.COMANDO_CLI + ' ' + ed, 'test_excel.py %s' % ed, 'mm']
              + list(anexo['info']['parametros'])
              if t not in leeme]
    check(not faltan, 'LEEME: advertencias (reacciones, D/C nominal, fuera de curva), comando '
                      'para regenerar, unidades y los %d parametros'
          % len(anexo['info']['parametros']), ['falta: %r' % t for t in faltan])
    supuestos = '\n'.join(str(v) for f in libro['Supuestos'] for v in f if v is not None)
    cs = 'V = %.4g · W' % ctx['p']['coef_sismico']
    check(cs in supuestos and 'sin factor φ' in supuestos,
          'Supuestos: coeficiente sismico (%s), capacidad nominal sin φ, %d filas'
          % (cs, len(libro['Supuestos']) - 1))
    return libro


# ============================================================
# [6] ARCHIVO ABIERTO
# ============================================================
def abrir_como_excel(ruta):
    r"""
    Abre el archivo como lo hace Excel: lectura, negando la escritura a
    los demas (FILE_SHARE_READ). Devuelve una funcion que lo cierra.
    """
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    h = k32.CreateFileW(ruta, 0x80000000, 0x00000001, None, 3, 0x80, None)
    if h in (None, wintypes.HANDLE(-1).value):
        raise OSError('CreateFileW fallo: %d' % ctypes.get_last_error())
    return lambda: k32.CloseHandle(h)


def probar_archivo_abierto(ed, carpeta):
    if os.name != 'nt':
        aviso('archivo abierto: solo se prueba en Windows')
        return
    ruta = os.path.join(carpeta, 'abierto.xlsx')
    hoja = excel.Hoja('Datos', [excel.Columna('a', 'kN', excel.F_KN)], [[1.5]])
    excel.escribir(ruta, [hoja])

    cerrar = abrir_como_excel(ruta)
    try:
        t0 = time.time()
        try:
            excel.escribir_libro_anexo(ed, ruta)
            check(False, 'abierto en Excel: escribir_libro_anexo tenia que fallar')
        except PermissionError as e:
            segundos = time.time() - t0
            check('abierto' in str(e) and 'Excel' in str(e) and segundos < 2.0,
                  'abierto en Excel (sin permiso de escritura): PermissionError en %.2f s, antes '
                  'de calcular' % segundos, 'mensaje: %s' % e)
    finally:
        cerrar()

    # Abierto por otro programa que SI deja escribir pero no reemplazar:
    # falla el os.replace, y no queda el temporal.
    with open(ruta, 'rb'):
        try:
            excel.escribir(ruta, [hoja])
            check(False, 'abierto sin permiso de borrado: escribir tenia que fallar')
        except PermissionError as e:
            restos = [n for n in os.listdir(carpeta) if n.endswith('.tmp')]
            check('abierto' in str(e) and not restos,
                  'abierto sin permiso de reemplazo: PermissionError al reemplazar y sin '
                  'temporales', 'mensaje: %s' % e)
    excel.escribir(ruta, [hoja])
    check(excel.leer(ruta)['Datos'][1] == [1.5], 'cerrado: se vuelve a escribir')

    # Lo generico: NaN, nombres invalidos, y un texto con '=' no es formula.
    malos = []
    for filas, nombre in (([[float('nan')]], 'Datos'), ([[1.0]], 'a/b'), ([[1.0]], 'x' * 32)):
        try:
            excel.escribir(os.path.join(carpeta, 'malo.xlsx'),
                           [excel.Hoja(nombre, [excel.Columna('a')], filas)])
            malos.append('acepto %r en la hoja %r' % (filas, nombre))
        except ValueError:
            pass
    ruta_f = os.path.join(carpeta, 'formula.xlsx')
    excel.escribir(ruta_f, [excel.Hoja('Datos', [excel.Columna('texto')], [['=SUMA(A1:A9)']])])
    if excel.estructura(ruta_f)['por_hoja']['Datos']['formulas']:
        malos.append("'=SUMA(A1:A9)' quedo como formula")
    check(not malos and not os.path.exists(os.path.join(carpeta, 'malo.xlsx')),
          'generico: NaN y nombres de hoja invalidos -> ValueError sin archivo; "=..." es texto',
          malos)


# ============================================================
# [7] EL LIBRO DEL REANALISIS
# ============================================================
def probar_reanalisis(ed, carpeta):
    fuente = os.path.join(rutas.UNITY, '%s.json' % ed)
    if not os.path.isfile(fuente):
        aviso('reanalisis: no existe %s' % os.path.relpath(fuente, rutas.RAIZ))
        return
    import servidor_opensees as motor
    with open(fuente, encoding='utf-8') as f:
        modelo = json.load(f)
    t0 = time.time()
    respuesta = motor.construir_y_resolver(copy.deepcopy(modelo))
    t_resolver = time.time() - t0
    casos = respuesta.get('casos') or []
    check(respuesta.get('ok') and casos,
          'construir_y_resolver(data/unity/%s.json): ok, %d casos (%s) en %.1f s'
          % (ed, len(casos), ', '.join(c['nombre'] for c in casos), t_resolver))
    if not casos:
        return
    sin_eq = [c['nombre'] for c in casos if not isinstance(c.get('equilibrio'), dict)]
    if sin_eq:
        aviso('la respuesta no trae equilibrio en %s: el libro lo calcula' % ', '.join(sin_eq))

    ruta = excel.escribir_libro_reanalisis(modelo, respuesta,
                                           os.path.join(carpeta, 'reanalisis_%s.xlsx' % ed))
    check(os.path.isabs(ruta) and os.path.isfile(ruta),
          'escribir_libro_reanalisis devuelve la ruta absoluta (%.2f MB)'
          % (os.path.getsize(ruta) / 1e6))
    libro = excel.leer(ruta)
    probar_estructura(ruta, libro, HOJAS_REANALISIS, {})
    probar_celdas_limpias(libro)

    import calcular
    cargas = {c['nombre']: c for c in modelo['casos_de_carga']}
    equilibrios = {}
    for c in casos:
        eq = c.get('equilibrio')
        if not isinstance(eq, dict):
            eq = calcular.equilibrio(modelo, cargas[c['nombre']], c)
        equilibrios[c['nombre']] = (eq, c['reacciones'])

    enc, filas = tabla(libro, 'Desplazamientos')
    cot = Cotejo()
    cot.igual('filas', len(filas), sum(len(c['desplazamientos']) for c in casos))
    it = iter(filas)
    for c in casos:
        for d in sorted(c['desplazamientos'], key=lambda d: int(d['id'])):
            f = next(it, None)
            if f is None:
                break
            for k in ('ux', 'uy', 'uz'):
                v = 1000.0 * float(d[k])
                cot.igual('%s %s %s' % (c['nombre'], d['id'], k), f['%s [mm]' % k], v,
                          REDONDEO_MM + cota_float(v))
            for k in ('rx', 'ry', 'rz'):
                cot.igual('%s %s %s' % (c['nombre'], d['id'], k), f['%s [rad]' % k], float(d[k]))
    cot.informe('reanalisis Desplazamientos (m -> mm)')

    enc, filas = tabla(libro, 'Esfuerzos')
    cot = Cotejo()
    cot.igual('filas', len(filas), 2 * sum(len(c['fuerzas_elementos']) for c in casos))
    it = iter(filas)
    for c in casos:
        for fe in sorted(c['fuerzas_elementos'], key=lambda x: int(x['id'])):
            fi, fj = next(it, None), next(it, None)
            if fi is None or fj is None:
                break
            for q, col in enumerate(enc[5:]):
                cot.igual('%s %s i' % (c['nombre'], fe['id']), fi[col], -float(fe['f'][q]))
                cot.igual('%s %s j' % (c['nombre'], fe['id']), fj[col], float(fe['f'][6 + q]))
    cot.informe('reanalisis Esfuerzos: i = -f_i, j = +f_j de localForce')

    probar_reacciones(libro, [c['nombre'] for c in casos], equilibrios)

    _enc, filas = tabla(libro, 'Resumen')
    cot = Cotejo()
    cot.igual('filas', len(filas), len(casos))
    for f, c in zip(filas, casos):
        eq = equilibrios[c['nombre']][0]
        for i, eje in enumerate(('Fx', 'Fy', 'Fz')):
            cot.igual('%s aplicada %s' % (c['nombre'], eje), f['Aplicada %s [kN]' % eje],
                      float(eq['aplicada_kN'][i]))
            cot.igual('%s reaccion %s' % (c['nombre'], eje), f['Reacción %s [kN]' % eje],
                      float(eq['reaccion_kN'][i]))
        cot.igual(c['nombre'] + ' origen', f['Origen del equilibrio'],
                  'servidor' if isinstance(c.get('equilibrio'), dict)
                  else 'calculado al escribir el libro')
        v = 1000.0 * float(c['max_desplazamiento'])
        cot.igual(c['nombre'] + ' mayor componente', f['Mayor componente [mm]'], v,
                  REDONDEO_MM + cota_float(v))
    cot.informe('reanalisis Resumen: equilibrio del servidor y mayor componente')
    for f in filas:
        print('         %-4s |u| max %.3f mm (mayor componente %.3f)  Vx %.2f  Vy %.2f kN  '
              'error Fz %.1e' % (f['Caso'], f['|u| máx [mm]'], f['Mayor componente [mm]'],
                                 f['Corte basal Vx [kN]'], f['Corte basal Vy [kN]'],
                                 f['Error Fz [kN]']))

    # Forma plana (un caso, sin 'equilibrio'): el libro lo calcula y da lo
    # mismo que el servidor en la multi-caso.
    primero = modelo['casos_de_carga'][0]
    plano = {k: v for k, v in modelo.items() if k != 'casos_de_carga'}
    plano.update(nombre_caso=primero['nombre'], cargas_nodales=primero['cargas_nodales'],
                 cargas_distribuidas=primero['cargas_distribuidas'])
    resp_plana = motor.construir_y_resolver(copy.deepcopy(plano))
    ruta_p = excel.escribir_libro_reanalisis(plano, resp_plana,
                                             os.path.join(carpeta, 'reanalisis_plano.xlsx'))
    _enc, filas_p = tabla(excel.leer(ruta_p), 'Resumen')
    eq = equilibrios[primero['nombre']][0]
    cot = Cotejo()
    cot.igual('filas', len(filas_p), 1)
    for f in filas_p[:1]:
        cot.igual('origen', f['Origen del equilibrio'], 'calculado al escribir el libro')
        for i, eje in enumerate(('Fx', 'Fy', 'Fz')):
            cot.igual('reaccion %s' % eje, f['Reacción %s [kN]' % eje],
                      float(eq['reaccion_kN'][i]), REDONDEO_KN)
    cot.informe('reanalisis forma plana (%s sin equilibrio): lo calcula y coincide con el del '
                'servidor' % primero['nombre'])

    # Secciones como diccionario (el servidor tambien las acepta).
    como_dict = dict(modelo, secciones={s['nombre']: {k: v for k, v in s.items() if k != 'nombre'}
                                        for s in modelo['secciones']})
    hojas = excel.hojas_del_reanalisis(como_dict, respuesta)
    check([h.nombre for h in hojas] == HOJAS_REANALISIS,
          'reanalisis con secciones en diccionario: arma las %d hojas' % len(hojas))

    # POST /analizar de verdad, con el libro desviado al temporal: lo que
    # recibe Unity trae 'excel' con la ruta y 'excel_error' vacio.
    if not hasattr(motor, 'escribir_excel'):
        aviso('servidor_opensees sin escribir_excel: /analizar no se prueba')
        return
    original = rutas.excel_reanalisis
    rutas.excel_reanalisis = lambda nombre: os.path.join(carpeta, 'analizar_%s.xlsx' % nombre)
    try:
        r = motor.app.test_client().post('/analizar', json=modelo)
        cuerpo = r.get_json() or {}
    finally:
        rutas.excel_reanalisis = original
    ruta_srv = cuerpo.get('excel')
    ok = (r.status_code == 200 and not cuerpo.get('excel_error') and ruta_srv
          and os.path.dirname(os.path.abspath(ruta_srv)) == os.path.abspath(carpeta)
          and os.path.isfile(ruta_srv))
    check(ok, 'POST /analizar: HTTP %s, excel = %s, excel_error = %r'
          % (r.status_code, ruta_srv and os.path.basename(ruta_srv), cuerpo.get('excel_error')))
    if ok:
        check(excel.leer(ruta_srv)['Resumen'] == libro['Resumen'],
              '/analizar escribe el mismo Resumen que escribir_libro_reanalisis directo')


# ============================================================
# MAIN
# ============================================================
def separar(argv):
    edificios = []
    argv = list(argv)
    while argv and not argv[0].startswith('-'):
        edificios.append(argv.pop(0))
    propias = {'--rapido', '--sin-reanalisis', '--ver-avisos'}
    opciones = {a for a in argv if a in propias}
    return edificios or ['lt2'], [a for a in argv if a not in propias], opciones


def fotografia(carpeta):
    """{archivo: (tamano, mtime)}: para comprobar que el test no escribe ahi."""
    if not os.path.isdir(carpeta):
        return {}
    return {n: (os.path.getsize(os.path.join(carpeta, n)),
                os.path.getmtime(os.path.join(carpeta, n))) for n in os.listdir(carpeta)}


def probar_edificio(ed, parametros, opciones, carpeta):
    print('=' * 78)
    print('  TEST EXCEL  %s   %s' % (ed.upper(), ' '.join(parametros)))
    print('=' * 78)
    callar = '--ver-avisos' not in opciones
    ex4 = excel._exportador_semana04()
    t0 = time.time()
    with exportar_excel.desviar_stderr(callar):
        anexo, ctx = ex4.construir_anexo(ed, parametros)
    t_anexo = time.time() - t0
    t0 = time.time()
    ruta_a = excel.escribir_libro_desde_anexo(ed, anexo, ctx, os.path.join(carpeta, 'a.xlsx'),
                                              parametros)
    t_escribir = time.time() - t0
    print('  construir_anexo %.1f s; libro escrito en %.1f s (%.2f MB)'
          % (t_anexo, t_escribir, os.path.getsize(ruta_a) / 1e6))
    libro = probar_anexo(ed, anexo, ctx, ruta_a, parametros)

    print('  -- [4] determinismo')
    t0 = time.time()
    ruta_b = os.path.join(carpeta, 'b.xlsx')
    if '--rapido' in opciones:
        excel.escribir_libro_desde_anexo(ed, anexo, ctx, ruta_b, parametros)
        como = 'mismo anexo'
    else:
        with exportar_excel.desviar_stderr(callar):
            devuelta = excel.escribir_libro_anexo(ed, ruta_b, parametros)
        check(devuelta == os.path.abspath(ruta_b), 'escribir_libro_anexo devuelve la ruta absoluta')
        como = 'anexo rearmado desde cero, %.1f s' % (time.time() - t0)
    a, b = sha256(ruta_a), sha256(ruta_b)
    check(a == b, 'dos generaciones, mismo sha256 (%s): %s' % (como, a[:16]))

    print('  -- [5] el libro versionado')
    versionado = rutas.excel_resultados(ed)
    rel = os.path.relpath(versionado, rutas.RAIZ)
    if parametros:
        aviso('%s no se compara: este test corre con %s' % (rel, ' '.join(parametros)))
    elif not os.path.isfile(versionado):
        check(False, '%s no existe: %s %s' % (rel, excel.COMANDO_CLI, ed))
    else:
        otro = excel.leer(versionado)
        distintas = []
        for hoja in HOJAS_ANEXO:
            x, y = otro.get(hoja), libro.get(hoja)
            if x != y:
                distintas.append('%s (%s filas contra %s)' % (hoja, x and len(x), y and len(y)))
        igual_bytes = sha256(versionado) == a
        check(not distintas, '%s al dia: mismas celdas que la generacion de ahora%s'
              % (rel, ', mismos bytes' if igual_bytes else ''),
              ['distintas: %s -> regenerar con %s %s' % (', '.join(distintas),
                                                         excel.COMANDO_CLI, ed)]
              if distintas else '')

    print('  -- [6] archivo abierto')
    probar_archivo_abierto(ed, carpeta)

    if '--sin-reanalisis' not in opciones:
        print('  -- [7] libro del reanalisis')
        probar_reanalisis(ed, carpeta)


def main(argv=None):
    edificios, parametros, opciones = separar(sys.argv[1:] if argv is None else argv)
    malos = [e for e in edificios if e not in excel.EDIFICIOS]
    if malos:
        raise SystemExit('edificio %s: use %s' % (', '.join(malos), ', '.join(excel.EDIFICIOS)))
    antes = {c: fotografia(c) for c in (rutas.EXCEL, rutas.EXCEL_REANALISIS)}
    t0 = time.time()
    for ed in edificios:
        carpeta = tempfile.mkdtemp(prefix='test_excel_%s_' % ed)
        try:
            probar_edificio(ed, parametros, opciones, carpeta)
        finally:
            shutil.rmtree(carpeta, ignore_errors=True)
    despues = {c: fotografia(c) for c in antes}
    check(antes == despues, 'el test no escribio en data/excel/ ni en results/excel/')
    print('=' * 78)
    print('  %s  (%d fallas, %.0f s)' % ('TODO OK' if not fallos else 'HAY FALLAS', len(fallos),
                                         time.time() - t0))
    for f in fallos:
        print('    - %s' % f)
    return 1 if fallos else 0


if __name__ == '__main__':
    # Los mensajes llevan 'φ' y tildes. Corrido a mano con la salida a un
    # archivo o a un pipe, Windows usa cp1252 y el primer print se caia con
    # UnicodeEncodeError: se escribe UTF-8 siempre.
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
