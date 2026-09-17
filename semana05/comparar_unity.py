# -*- coding: utf-8 -*-
r"""
================================================================
 semana05/comparar_unity.py  -  LO QUE MUESTRA UNITY CONTRA PYTHON
================================================================
 CapturaSemana05.cs (la app de Windows abierta con -capturarS5
 <carpeta>) deja un registro.txt con lineas "DATO clave = valor": los
 numeros que Unity CARGO y MUESTRA, escritos con G9 (el float de 32
 bits exacto que tenia en memoria). Este script los cruza con lo que
 Python dejo como referencia:

   [1] superposicion  E1..E3 precalculados y E3 pedido a POST /combinar
                      contra semana05/evidencia/superposicion_<ed>_control.csv
   [2] M1             nodo 186, maximos, barras del nodo y equilibrio por
                      eje contra la SALIDA de
                      semana05/reanalisis_demo.py lt2 --borrar-elemento 69
                      --nodo 186 --elemento 337 --float32 (se corre aca)
   [3] carga movil    las posiciones registradas contra
                      semana05/evidencia/carga_movil_<ed>.json
   [4] preguntas      lo que el panel contesta (area tributaria, cargas,
                      desplazamiento, esfuerzos, demanda) contra los JSON
                      de data/unity que Unity leyo
   [5] registro       fotos, errores del log, ids de control iguales a
                      los de semana05/estados_s5.json, Excel encontrado,
                      anexo marcado desactualizado despues de la M1

 Correr (desde la raiz del repo):

   python semana05/comparar_unity.py semana05/capturas/registro.txt
   python semana05/comparar_unity.py semana05/capturas/registro.txt \
          --salida semana05/evidencia/unity_vs_python.txt
   python semana05/comparar_unity.py <registro> --sin-servidor
          (la captura se hizo sin servidor: LIBRE y M1 no se exigen)

 Sale con 1 si algo no calza o falta un dato que deberia estar. No
 escribe nada salvo --salida.

 ----------------------------------------------------------------
 LAS TOLERANCIAS SE MIDEN CONTRA SU CAUSA (CLAUDE.md, regla 3)
 ----------------------------------------------------------------
 Unity guarda cada numero como float de 32 bits (JsonUtility) y el
 registro lo escribe exacto. Entre ese float y el numero de Python hay
 estas causas, y la tolerancia de cada fila es la suma de las que
 aplican (la columna "causa" dice cuales):

   f32      la separacion entre floats de 32 bits vecinos en ese valor,
            numpy.spacing(float32(v)): JsonUtility redondea el decimal
            del JSON al float mas cercano (a lo mas medio ulp; se toma
            uno entero porque el valor de Python tambien pasa por
            float64 al leerlo).
   ref      la diferencia MEDIDA entre la referencia de Python y el
            archivo que Unity leyo de verdad (el CSV y la evidencia de la
            carga movil los escribe otro paso que data/unity/*.json).
            Hoy es 0 en todo lo que calza al decimal.
   impr     medio ultimo digito del numero tal como lo imprime
            reanalisis_demo.py (%.5f -> 5e-6, %.3f -> 5e-4,
            %.1e -> medio digito de la mantisa).
   ent32    solo M1: Unity manda el modelo en float32 y la demo lo emula
            con --float32. Lo que eso mueve cada numero se MIDE corriendo
            la demo tambien sin --float32 (la diferencia entre las dos
            corridas).
   srv      solo M1: el servidor redondea lo que devuelve
            (servidor_opensees.py: desplazamientos a 8 decimales en m,
            fuerzas y reacciones a 4 en kN). Unity y la demo resuelven
            cada uno su propio float32 y cada resultado pasa por su propio
            redondeo, asi que pueden quedar a un escalon entero: 1e-8 m en
            un desplazamiento, 1e-4 kN en una fuerza, y en una suma de
            reacciones un escalon por cada nodo con restriccion.
================================================================
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                'comun'))
import rutas                                 # noqa: E402

SEMANA05 = os.path.join(rutas.RAIZ, 'semana05')
EVIDENCIA = os.path.join(SEMANA05, 'evidencia')

SALIDA = []


def decir(texto=''):
    print(texto)
    SALIDA.append(texto)


# ============================================================
# LECTURA
# ============================================================
def leer_registro(ruta):
    """{clave: texto} de las lineas 'DATO clave = valor' y las lineas de
    aviso (AVISO pestana, AVISO reflexion, ERROR)."""
    datos, avisos = {}, []
    with open(ruta, encoding='utf-8') as f:
        for linea in f:
            linea = linea.rstrip('\n')
            if linea.startswith('DATO '):
                clave, _, valor = linea[5:].partition(' = ')
                datos[clave.strip()] = valor
            elif linea.startswith(('AVISO', 'ERROR')):
                avisos.append(linea)
    return datos, avisos


def num(texto):
    return float(texto)


def vector(texto):
    return [float(x) for x in texto.split(',')] if texto else []


def ulp32(v):
    """Separacion entre floats de 32 bits vecinos en |v|."""
    return float(np.spacing(np.float32(abs(v))))


def medio_digito(texto):
    """Medio ultimo digito de un numero impreso: '-3.64515' -> 5e-6,
    '2.0e-04' -> 5e-6, '34148' -> 0.5."""
    t = texto.strip().lower()
    m = re.fullmatch(r'[-+]?\d*(?:\.(\d*))?(?:e([-+]?\d+))?', t)
    if not m:
        return 0.0
    dec = len(m.group(1) or '')
    exp = int(m.group(2) or 0)
    return 0.5 * 10.0 ** (exp - dec)


# ============================================================
# TABLA
# ============================================================
class Tabla:
    def __init__(self, titulo):
        self.titulo = titulo
        self.filas = []

    def numero(self, nombre, unity, python, tol, causa):
        """unity y python en las mismas unidades; ok si |dif| <= tol."""
        dif = abs(unity - python)
        ok = dif <= tol
        self.filas.append((nombre, '%.9g' % unity, '%.9g' % python, '%.2e' % dif,
                           '%.2e' % tol, causa, ok))
        return ok

    def texto(self, nombre, unity, python, causa='igual'):
        ok = str(unity) == str(python)
        self.filas.append((nombre, str(unity), str(python), '', '', causa, ok))
        return ok

    def falta(self, nombre, que):
        self.filas.append((nombre, '(falta)', str(que), '', '', 'registro', False))

    def imprimir(self):
        decir()
        decir('=' * 118)
        decir('  ' + self.titulo)
        decir('=' * 118)
        if not self.filas:
            decir('  (sin filas)')
            return 0
        decir('  %-50s %-17s %-17s %-9s %-9s %-10s %s'
              % ('dato', 'Unity', 'Python', '|dif|', 'tol', 'causa', ''))
        malas = 0
        for nombre, u, p, dif, tol, causa, ok in self.filas:
            if not ok:
                malas += 1
            decir('  %-50s %-17s %-17s %-9s %-9s %-10s %s'
                  % (nombre[:50], u[:17], p[:17], dif, tol, causa, 'ok' if ok else 'FALLA'))
        decir('  -> %d filas, %d FALLA' % (len(self.filas), malas))
        return malas


def comparar(tabla, datos, clave, python, tol_extra=0.0, causa='f32', escala=1.0, nombre=None):
    """Una fila numerica: datos[clave]*escala contra python, tol = ulp32
    del valor de Unity (en la escala) + tol_extra."""
    nombre = nombre or clave
    if clave not in datos or datos[clave] == '':
        tabla.falta(nombre, python)
        return False
    u = num(datos[clave])
    tol = ulp32(u) * abs(escala) + tol_extra
    return tabla.numero(nombre, u * escala, float(python), tol, causa)


def comparar_texto(tabla, datos, clave, python, nombre=None):
    nombre = nombre or clave
    if clave not in datos:
        tabla.falta(nombre, python)
        return False
    return tabla.texto(nombre, datos[clave], python)


# ------------------------------------------------------------
# LA CABECERA DE CADA FOTO: DE DONDE DICE QUE SALE LO QUE SE VE
# ------------------------------------------------------------
# VisorQA escribe en la cabecera la FUENTE de lo que se ve en 3D (anexo o
# superposicion, reanalisis del servidor, carga movil) con sus numeros, y
# CapturaSemana05 la registra por foto (foto.<nombre>.cabecera.fuente y
# .texto). La foto de la M1 decia "Caso activo LIBRE ... 24.63 mm" junto a
# un nodo que bajaba 21.60 mm: estas filas lo impiden.
#
# Un numero de la cabecera es TEXTO ya redondeado por C# ("0.00"). La
# tolerancia se mide igual que en las filas numericas: el valor de Python
# +- la suma de sus causas; si ese intervalo cruza un limite de redondeo,
# valen los dos textos (causa 'fmt').
def textos_redondeados(valor, decimales, tol):
    """Los textos con 'decimales' que puede escribir C# para valor +- tol."""
    fmt = '%%.%df' % decimales
    return sorted({fmt % x for x in (valor - tol, valor, valor + tol)})


def foto_que_contiene(datos, trozo):
    """El nombre de la foto cuyo nombre contiene 'trozo', o None."""
    for k in datos:
        m = re.match(r'foto\.(.+)\.cabecera\.fuente$', k)
        if m and trozo in m.group(1):
            return m.group(1)
    return None


def filas_cabecera(tabla, datos, trozo, fuente, piezas):
    """fuente: texto igual. piezas: [(etiqueta, [textos validos])], cada una
    tiene que estar en el texto de la cabecera (basta uno de sus textos)."""
    foto = foto_que_contiene(datos, trozo)
    if foto is None:
        tabla.falta('cabecera de la foto *%s*' % trozo, fuente)
        return
    n = foto.split('_')[0]
    comparar_texto(tabla, datos, 'foto.%s.cabecera.fuente' % foto, fuente,
                   nombre='cabecera foto %s fuente' % n)
    texto = datos.get('foto.%s.cabecera.texto' % foto, '')
    for etiqueta, validos in piezas:
        hallado = next((v for v in validos if v in texto), None)
        tabla.texto('cabecera foto %s "%s"' % (n, etiqueta), hallado or texto, hallado or validos[0],
                    'fmt' if len(validos) > 1 else 'contiene')


# ============================================================
# [1] SUPERPOSICION
# ============================================================
def valor_json_de_fila(caso, fila):
    """El numero de data/unity/superposicion_<ed>.json (lo que leyo
    Unity) que corresponde a una fila del CSV de control, o None."""
    etq, mag = fila['etiqueta'], fila['magnitud']
    ident = int(fila['id']) if fila['id'] else None
    if etq == 'estado':
        if mag == 'max_desplazamiento_mm':
            return caso['max_desplazamiento_mm']
        return None
    if etq in ('columna', 'muro', 'no pasa'):
        d = next((x for x in caso['demandas'] if x['id'] == ident), None)
        return d.get(mag) if d and mag in ('P', 'M', 'Mn', 'u') else None
    if etq == 'viga':
        s = next((x for x in caso['esfuerzos'] if x['id'] == ident), None)
        if s is None:
            return None
        if mag == 'My(0)':
            return s['My'][0]
        if mag == 'My(L)':
            return s['My'][-1]
        if mag.startswith('max|My|'):
            k = max(range(len(s['My'])), key=lambda i: (abs(s['My'][i]), -i))
            return s['My'][k]
        return None
    if etq == 'nodo':
        d = next((x for x in caso['desplazamientos'] if x['id'] == ident), None)
        comp = mag.split()[0]
        return d.get(comp) if d else None
    return None


def bloque_superposicion(datos, ed, exigir_libre):
    tabla = Tabla('[1] SUPERPOSICION: Unity contra semana05/evidencia/superposicion_%s_control.csv' % ed)
    ruta_csv = os.path.join(EVIDENCIA, 'superposicion_%s_control.csv' % ed)
    ruta_json = rutas.unity('superposicion_%s' % ed)
    with open(ruta_csv, encoding='utf-8') as f:
        filas = list(csv.DictReader(f))
    with open(ruta_json, encoding='utf-8') as f:
        precalculado = {e['nombre']: e for e in json.load(f)['estados']}

    origenes = [('pre', None)]
    ref_libre = datos.get('sup.libre.estado_de_referencia', 'E3')
    if datos.get('sup.libre.hecho') == 'True':
        origenes.append(('libre', ref_libre))
    elif exigir_libre:
        tabla.falta('sup.libre.hecho', 'True (E3 por POST /combinar)')

    for origen, solo in origenes:
        for estado in sorted({f_['estado'] for f_ in filas}):
            if solo and estado != solo:
                continue
            p = 'sup.%s.%s' % (origen, estado)
            caso = precalculado[estado]['caso']
            no_pasa_csv = []
            for fila in filas:
                if fila['estado'] != estado:
                    continue
                etq, mag, ident, v = fila['etiqueta'], fila['magnitud'], fila['id'], fila['valor_unity_json']
                if mag.startswith('sum lambda'):
                    continue            # tabla de no linealidad: Unity no la muestra
                vj = valor_json_de_fila(caso, fila)
                ref = abs(float(v) - vj) if vj is not None and _es_numero(v) else 0.0
                causa = 'f32+ref'
                if etq == 'estado':
                    if mag == 'max_desplazamiento_mm':
                        comparar(tabla, datos, p + '.max_desplazamiento_mm', float(v), ref, causa)
                        # La cabecera de su foto sigue diciendo el caso del anexo.
                        trozo = '_superposicion_%s_%s' % (estado, 'precalculado' if origen == 'pre' else 'LIBRE')
                        tol = ulp32(float(v)) + ref
                        filas_cabecera(tabla, datos, trozo, 'anexo',
                                       [('Desp. max', ['Desp. max %s mm' % t
                                                       for t in textos_redondeados(float(v), 2, tol)])])
                    elif mag.startswith('no_pasan'):
                        comparar_texto(tabla, datos, p + '.no_pasan', str(int(float(v))))
                        m = re.search(r'de (\d+) con fierro', mag)
                        if m:
                            comparar_texto(tabla, datos, p + '.con_fierro', m.group(1))
                elif etq in ('columna', 'muro'):
                    clave = '%s.elem.%s.%s' % (p, ident, mag)
                    if mag in ('extremo', 'pasa'):
                        comparar_texto(tabla, datos, clave, v)
                    else:
                        comparar(tabla, datos, clave, float(v), ref, causa)
                elif etq == 'viga':
                    if mag == 'My(0)':
                        comparar(tabla, datos, '%s.elem.%s.My_i' % (p, ident), float(v), ref, causa)
                    elif mag == 'My(L)':
                        comparar(tabla, datos, '%s.elem.%s.My_j' % (p, ident), float(v), ref, causa)
                    elif mag.startswith('max|My|'):
                        comparar(tabla, datos, '%s.elem.%s.My_max_abs_valor' % (p, ident), float(v), ref, causa)
                        x = re.search(r'x = (-?[\d.]+)', mag)
                        if x:
                            comparar(tabla, datos, '%s.elem.%s.My_max_abs_x' % (p, ident), float(x.group(1)),
                                     medio_digito(x.group(1)), 'f32+impr')
                elif etq == 'nodo':
                    comp = mag.split()[0]
                    comparar(tabla, datos, '%s.nodo.%s.%s_m' % (p, ident, comp), float(v), ref, causa)
                elif etq == 'no pasa':
                    no_pasa_csv.append(int(ident))
                    comparar(tabla, datos, '%s.no_pasa.%s.u' % (p, ident), float(v), ref, causa)
            ids_unity = datos.get(p + '.no_pasa.ids')
            if ids_unity is None:
                tabla.falta(p + '.no_pasa.ids', no_pasa_csv)
            else:
                tabla.texto(p + '.no_pasa.ids', ids_unity, ','.join(str(i) for i in sorted(no_pasa_csv)))

            # El equilibrio que el panel muestra, contra el JSON que lo trae.
            eq = precalculado[estado].get('equilibrio') or {}
            for k in ('aplicada_kN', 'reaccion_kN', 'error_kN'):
                clave = '%s.equilibrio.%s' % (p, k)
                if clave not in datos:
                    tabla.falta(clave, eq.get(k))
                    continue
                u = vector(datos[clave])
                for i, eje in enumerate(('Fx', 'Fy', 'Fz')):
                    tabla.numero('%s[%s]' % (clave, eje), u[i], eq[k][i], ulp32(u[i]), 'f32')
    return tabla.imprimir()


def _es_numero(t):
    try:
        float(t)
        return True
    except (TypeError, ValueError):
        return False


# ============================================================
# [2] M1
# ============================================================
def correr_demo(ed, float32):
    cmd = [sys.executable, os.path.join(SEMANA05, 'reanalisis_demo.py'), ed,
           '--borrar-elemento', '69', '--nodo', '186', '--elemento', '337']
    if float32:
        cmd.append('--float32')
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    r = subprocess.run(cmd, cwd=rutas.RAIZ, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env=env)
    return r.returncode, r.stdout + r.stderr, ' '.join(cmd[1:])


NUMERO = r'(-?\d+\.\d+)'


def parsear_demo(texto):
    """{clave: texto impreso} de la salida de reanalisis_demo.py."""
    out = {}
    for m in re.finditer(r'^ {4}(\w+)\s+(UX|UY|UZ)\s+' + NUMERO + r'\s+' + NUMERO + r'\s', texto, re.M):
        caso, comp = m.group(1), m.group(2).lower()
        out['antes.%s.nodo.186.%s_mm' % (caso, comp)] = m.group(3)
        out['despues.%s.nodo.186.%s_mm' % (caso, comp)] = m.group(4)
    for m in re.finditer(r'^ {4}(\w+)\s+' + NUMERO + r' ->\s+' + NUMERO + r' mm', texto, re.M):
        out['antes.%s.max_mm' % m.group(1)] = m.group(2)
        out['despues.%s.max_mm' % m.group(1)] = m.group(3)
    ini = texto.find('BARRAS EN EL NODO')
    fin = texto.find('EQUILIBRIO POR CASO')
    barra = None
    for linea in texto[ini:fin].splitlines():
        m = re.match(r'^ {4}(\d+)\s+\S+', linea)
        if m:
            barra = m.group(1)
            continue
        m = re.match(r'^ {6}(antes|despues)\s+N\s+' + NUMERO + r'\s+Vz\s+' + NUMERO
                     + r'\s+My\s+' + NUMERO + r'\s+/\s+' + NUMERO, linea)
        if m and barra:
            fase = m.group(1)
            for nombre, g in (('N_i', 2), ('Vz_i', 3), ('My_i', 4), ('My_j', 5)):
                out['%s.G.elem.%s.%s' % (fase, barra, nombre)] = m.group(g)
    for m in re.finditer(r'^ {4}(\w+)\s+(antes|despues)\s+\[\s*' + NUMERO + r',\s*' + NUMERO + r',\s*'
                         + NUMERO + r'\]\s+\[\s*' + NUMERO + r',\s*' + NUMERO + r',\s*' + NUMERO
                         + r'\]\s+(\d\.\de[-+]\d+)', texto, re.M):
        caso, fase = m.group(1), m.group(2)
        for i, eje in enumerate(('Fx', 'Fy', 'Fz')):
            out['%s.%s.aplicada.%s' % (fase, caso, eje)] = m.group(3 + i)
            out['%s.%s.reaccion.%s' % (fase, caso, eje)] = m.group(6 + i)
        out['%s.%s.peor_error' % (fase, caso)] = m.group(9)
    out['_todo_ok'] = 'TODO OK' in texto
    return out


def bloque_m1(datos, ed, exigir):
    tabla = Tabla('[2] M1 (borrar la columna 69): Unity + POST /analizar contra reanalisis_demo.py --float32')
    if datos.get('m1.hecho') != 'True':
        if exigir:
            tabla.falta('m1.hecho', 'True')
        else:
            decir('\n  [2] M1 no se hizo en la captura (sin servidor): no se compara.')
            return 0
        return tabla.imprimir()

    rc32, texto32, cmd32 = correr_demo(ed, True)
    rc64, texto64, _ = correr_demo(ed, False)
    d32, d64 = parsear_demo(texto32), parsear_demo(texto64)
    decir()
    decir('  referencia: python %s  (rc %d, %s; %d numeros leidos de su salida)'
          % (cmd32, rc32, 'TODO OK' if d32['_todo_ok'] else 'SIN TODO OK', len(d32) - 1))
    decir('  entrada32 medida contra la misma demo sin --float32 (rc %d)' % rc64)
    tabla.texto('reanalisis_demo.py --float32 rc', rc32, 0)
    tabla.texto('reanalisis_demo.py --float32 TODO OK', d32['_todo_ok'], True)

    def ent32(k):
        if k in d32 and k in d64:
            return abs(float(d32[k]) - float(d64[k]))
        return 0.0

    for clave_estado in ('m1.antes.ok', 'm1.despues.ok', 'm1.borrado', 'm1.anexo_desactualizado',
                         'm1.excel_existe'):
        comparar_texto(tabla, datos, clave_estado, 'True')
    comparar_texto(tabla, datos, 'm1.existe_columna', 'False')
    comparar_texto(tabla, datos, 'm1.motivo', 'borrar elemento 69')
    with open(rutas.unity(ed), encoding='utf-8') as f:
        modelo = json.load(f)
    n_elementos = len(modelo['elementos'])
    comparar_texto(tabla, datos, 'm1.elementos_despues', str(n_elementos - 1))

    # srv (ver encabezado): un escalon del redondeo del servidor por lado
    n_restringidos = sum(1 for n in modelo['nodos'] if any(n.get('restricciones') or []))
    srv_desp_mm = 1e-8 * 1000.0
    srv_fuerza = 1e-4
    srv_suma = n_restringidos * 1e-4
    decir('  srv: %d nodos con restriccion -> una suma de reacciones puede moverse %.1e kN'
          % (n_restringidos, srv_suma))

    for k, impreso in sorted(d32.items()):
        if k.startswith('_'):
            continue
        partes = k.split('.')
        fase, caso = partes[0], partes[1]
        base = 'm1.%s.%s' % (fase, caso)
        tol = medio_digito(impreso) + ent32(k)
        causa = 'f32+impr+ent32+srv'
        if '.nodo.186.' in k:
            comp = partes[-1].replace('_mm', '')
            comparar(tabla, datos, '%s.nodo.186.%s_m' % (base, comp), float(impreso),
                     tol + srv_desp_mm, causa, 1000.0)
        elif k.endswith('.max_mm'):
            comparar(tabla, datos, base + '.max_desplazamiento_m', float(impreso),
                     tol + srv_desp_mm, causa, 1000.0)
        elif '.elem.' in k:
            comparar(tabla, datos, 'm1.%s.G.elem.%s.%s' % (fase, partes[3], partes[4]), float(impreso),
                     tol + srv_fuerza, causa)
        elif '.aplicada.' in k or '.reaccion.' in k:
            cual, eje = partes[2], partes[3]
            clave = '%s.equilibrio.%s_kN' % (base, cual)
            if clave not in datos:
                tabla.falta(clave, impreso)
                continue
            u = vector(datos[clave])[('Fx', 'Fy', 'Fz').index(eje)]
            tabla.numero('%s[%s]' % (clave, eje), u, float(impreso), ulp32(u) + tol + srv_suma, causa)
        elif k.endswith('.peor_error'):
            clave = base + '.equilibrio.error_kN'
            if clave not in datos:
                tabla.falta(clave, impreso)
                continue
            u = max(abs(x) for x in vector(datos[clave]))
            tabla.numero(clave + ' (peor |error|)', u, float(impreso), ulp32(u) + tol + srv_suma, causa)
    for caso in ('G', 'Q', 'EX', 'EY'):
        for fase in ('antes', 'despues'):
            comparar_texto(tabla, datos, 'm1.%s.%s.equilibrio.confiable' % (fase, caso), 'True')

    # La cabecera de las fotos de la M1 dice que lo que se ve es el
    # reanalisis del servidor en G (el caso que muestran las fotos 21 y 22),
    # con SU maximo, y que la D/C no se recalculo.
    k = 'despues.G.max_mm'
    if k in d32:
        impreso = d32[k]
        tol = medio_digito(impreso) + ent32(k) + srv_desp_mm + ulp32(float(impreso))
        piezas = [('caso', ['(modelo editado) \u00b7 caso G \u00b7']),
                  ('Max. componente', ['Max. componente %s mm' % t for t in textos_redondeados(float(impreso), 2, tol)]),
                  ('D/C', ['D/C: sin recalcular (anexo del modelo original)'])]
        for trozo in ('_M1_sin_columna_', '_M1_nodo_'):
            filas_cabecera(tabla, datos, trozo, 'reanalisis', piezas)
    else:
        tabla.falta('reanalisis_demo.py ' + k, 'maximo en G despues de la M1')
    return tabla.imprimir()


# ============================================================
# [3] CARGA MOVIL
# ============================================================
CAMPOS_POSICION = ('xL', 'a_m', 'L_m', 's_m', 'x', 'y', 'z', 'Pz_local_kN', 'max_desplazamiento_mm',
                   'uz_min_mm', 'uz_bajo_carga_mm', 'M_bajo_carga_kNm')
ENTEROS_POSICION = ('indice', 'elemento', 'nodo_max_desplazamiento', 'nodo_uz_min')
CAMPOS_REPARTO = ('V_i_kN', 'V_j_kN', 'porcentaje_i', 'porcentaje_j', 'palanca_i_kN', 'palanca_j_kN',
                  'My_i_kNm', 'My_j_kNm', 'momentos_sobre_L_kN')
CAMPOS_CONSERVACION = ('P_kN', 'suma_Rz_kN', 'error_kN', 'cota_kN', 'suma_Rx_kN', 'suma_Ry_kN')


def bloque_carga_movil(datos, ed):
    tabla = Tabla('[3] CARGA MOVIL: Unity contra semana05/evidencia/carga_movil_%s.json' % ed)
    with open(os.path.join(EVIDENCIA, 'carga_movil_%s.json' % ed), encoding='utf-8') as f:
        evidencia = json.load(f)
    with open(rutas.unity('carga_movil_%s' % ed), encoding='utf-8') as f:
        leido = json.load(f)
    indices = sorted({int(m.group(1)) for k in datos for m in [re.match(r'movil\.p(\d+)\.indice$', k)] if m})
    comparar_texto(tabla, datos, 'movil.hecho', 'True')
    comparar_texto(tabla, datos, 'movil.posiciones', str(len(evidencia['posiciones'])))
    comparar(tabla, datos, 'movil.P_kN', evidencia['P_kN'], 0.0)
    if not indices:
        tabla.falta('movil.p<i>', 'al menos una posicion')
    for i in indices:
        pe, pl = evidencia['posiciones'][i], leido['posiciones'][i]
        p = 'movil.p%d' % i

        def fila(clave, ve, vl, tol_extra=0.0):
            comparar(tabla, datos, clave, ve, abs(ve - vl) + tol_extra, 'f32+ref')

        for k in ENTEROS_POSICION:
            comparar_texto(tabla, datos, '%s.%s' % (p, k), str(pe[k]))
        comparar_texto(tabla, datos, p + '.indice_mostrado', str(i))
        for k in CAMPOS_POSICION:
            fila('%s.%s' % (p, k), pe[k], pl[k])
        if p + '.u_carga_m' in datos:
            u = vector(datos[p + '.u_carga_m'])
            for j, eje in enumerate(('ux', 'uy', 'uz')):
                tabla.numero('%s.u_carga_m[%s]' % (p, eje), u[j], pe['u_carga_m'][j],
                             ulp32(u[j]) + abs(pe['u_carga_m'][j] - pl['u_carga_m'][j]), 'f32+ref')
        for k in ('nodo_i', 'nodo_j'):
            comparar_texto(tabla, datos, '%s.reparto.%s' % (p, k), str(pe['reparto'][k]))
        for k in CAMPOS_REPARTO:
            fila('%s.reparto.%s' % (p, k), pe['reparto'][k], pl['reparto'][k])
        for k in CAMPOS_CONSERVACION:
            fila('%s.conservacion.%s' % (p, k), pe['conservacion'][k], pl['conservacion'][k])
        comparar_texto(tabla, datos, p + '.conservacion.cumple', str(pe['conservacion']['cumple']))
        # Lo que muestra el panel tiene que cerrar con su propia cota:
        # |suma Rz - P| <= cota, con los numeros que tenia Unity.
        try:
            srz = num(datos[p + '.conservacion.suma_Rz_kN'])
            pk = num(datos[p + '.conservacion.P_kN'])
            cota = num(datos[p + '.conservacion.cota_kN'])
            tabla.numero(p + ' |suma Rz - P| <= cota', abs(srz - pk), 0.0,
                         cota + ulp32(srz) + ulp32(pk), 'cota JSON')
        except KeyError as e:
            tabla.falta(p + ' conservacion', str(e))
        # La deformada que puso el visor es la de esta posicion: el uz del
        # nodo que mas baja, en la lista aplicada, contra el resumen (4 dec.).
        clave = p + '.desplazamiento_nodo_uz_min.uz_m'
        comparar(tabla, datos, clave, pe['uz_min_mm'], medio_digito('%.4f' % pe['uz_min_mm']),
                 'f32+impr', 1000.0, nombre=clave + ' (mm)')
        comparar_texto(tabla, datos, p + '.hay_deformada', 'True')
        # La cabecera de su foto dice "Carga movil" con los numeros de esta
        # posicion (del JSON que leyo Unity), no el caso del anexo.
        P = ('%.2f' % leido['P_kN']).rstrip('0').rstrip('.')
        filas_cabecera(tabla, datos, '_carga_movil_posicion_%d_' % i, 'carga_movil', [
            ('posicion', ['Carga movil \u00b7 posicion %d/%d' % (i + 1, len(leido['posiciones']))]),
            ('x', ['x = %s m' % t for t in textos_redondeados(pl['x'], 2, ulp32(pl['x']))]),
            ('P', ['P = %s kN' % P]),
            ('UZ max', ['UZ max %s mm (nodo %d)' % (t, pl['nodo_uz_min'])
                        for t in textos_redondeados(pl['uz_min_mm'], 3, ulp32(pl['uz_min_mm']))]),
            ('D/C', ['D/C: no se calcula para la carga movil'])])
    return tabla.imprimir()


# ============================================================
# [4] LAS PREGUNTAS: contra los JSON que Unity leyo
# ============================================================
def bloque_preguntas(datos, ed):
    tabla = Tabla('[4] PREGUNTAS DEL VISOR: lo que contesta el panel contra data/unity/%s.json y semana04.json' % ed)
    with open(rutas.unity(ed), encoding='utf-8') as f:
        modelo = json.load(f)
    with open(rutas.unity('semana04'), encoding='utf-8') as f:
        anexo = json.load(f)
    casos = {c['nombre']: c for c in anexo['casos']}
    nodos = {n['id']: n for n in modelo['nodos']}

    # Donde esta y como esta apoyado.
    col = anexo['info']['columna_demo']
    elem = next(e for e in modelo['elementos'] if e['id'] == col)
    comparar_texto(tabla, datos, 'ux.donde.seleccion', 'elemento %d' % col)
    comparar_texto(tabla, datos, 'ux.donde.seccion', elem['seccion'])
    for lado in ('n1', 'n2'):
        n = nodos[elem[lado]]
        comparar_texto(tabla, datos, 'ux.donde.%s.id' % lado, str(n['id']))
        if 'ux.donde.%s.xyz_m' % lado in datos:
            u = vector(datos['ux.donde.%s.xyz_m' % lado])
            for j, k in enumerate(('x', 'y', 'z')):
                tabla.numero('ux.donde.%s.%s' % (lado, k), u[j], n[k], ulp32(u[j]), 'f32')
    apoyo = min((nodos[elem['n1']], nodos[elem['n2']]), key=lambda n: n['z'])
    comparar_texto(tabla, datos, 'ux.apoyo.nodo', str(apoyo['id']))
    comparar_texto(tabla, datos, 'ux.apoyo.restricciones', ','.join(str(r) for r in apoyo['restricciones']))
    comparar_texto(tabla, datos, 'ux.apoyo.fijo', str(bool(apoyo.get('fijo'))))

    # Que lo carga.
    if 'ux.carga.viga' in datos:
        viga = int(datos['ux.carga.viga'])
        trib = [t for t in modelo.get('areas_tributarias', []) if t['elemento'] == viga]
        comparar_texto(tabla, datos, 'ux.carga.entradas', str(len(trib)))
        for i, t in enumerate(trib):
            # w es SOLO la losa; w_peso_propio y w_total_G (la w que recibe
            # OpenSees en G) los exporta el LT2 desde lo que su modelo aplico.
            for k, clave in (('area', 'area_m2'), ('qG', 'qG_kN_m2'), ('carga_total', 'carga_total_kN'),
                             ('w', 'w_kN_m'), ('luz', 'luz_m'),
                             ('w_peso_propio', 'w_peso_propio_kN_m'), ('w_total_G', 'w_total_G_kN_m')):
                if k in t:
                    comparar(tabla, datos, 'ux.carga.trib%d.%s' % (i, clave), t[k])
        for c in modelo['casos_de_carga']:
            for q in c.get('cargas_distribuidas') or []:
                if int(q['elemento']) != viga:
                    continue
                clave = 'ux.carga.distribuida.' + c['nombre']
                if clave not in datos:
                    tabla.falta(clave, q)
                    continue
                u = vector(datos[clave])
                for j, k in enumerate(('wx', 'wy', 'wz')):
                    tabla.numero('%s[%s]' % (clave, k), u[j], q.get(k, 0.0), ulp32(u[j]), 'f32')
    else:
        tabla.falta('ux.carga.viga', 'una viga con area tributaria')

    # Como se deforma.
    if 'ux.deforma.caso' in datos and 'ux.deforma.nodo' in datos:
        caso = casos[datos['ux.deforma.caso']]
        nodo = int(datos['ux.deforma.nodo'])
        d = next(x for x in caso['desplazamientos'] if x['id'] == nodo)
        comparar(tabla, datos, 'ux.deforma.max_desplazamiento_mm', caso['max_desplazamiento_mm'])
        for k in ('ux', 'uy', 'uz'):
            comparar(tabla, datos, 'ux.deforma.%s_m' % k, d[k])
        comparar_texto(tabla, datos, 'ux.deforma.hay_deformada', 'True')
    else:
        tabla.falta('ux.deforma', 'caso y nodo')

    # Que fuerzas tiene.
    if 'ux.fuerzas.caso' in datos and 'ux.fuerzas.viga' in datos:
        caso = casos[datos['ux.fuerzas.caso']]
        viga = int(datos['ux.fuerzas.viga'])
        s = next(x for x in caso['esfuerzos'] if x['id'] == viga)
        comparar_texto(tabla, datos, 'ux.fuerzas.estaciones', str(len(s['x'])))
        for k in ('N', 'Vy', 'Vz', 'T', 'My', 'Mz'):
            comparar(tabla, datos, 'ux.fuerzas.%s_i' % k, s[k][0])
            comparar(tabla, datos, 'ux.fuerzas.%s_j' % k, s[k][-1])
        comparar_texto(tabla, datos, 'ux.fuerzas.motivo_sin_diagrama', '')
    else:
        tabla.falta('ux.fuerzas', 'caso y viga')

    # Cuanta capacidad tiene: el caso con mas NO PASA con la regla del
    # visor (el primero de los casos del anexo con mas pasa = false; los
    # E1..E3 van despues en la lista).
    orden = list(anexo['casos'])
    with open(rutas.unity('superposicion_%s' % ed), encoding='utf-8') as f:
        orden += [e['caso'] for e in json.load(f)['estados']]
    mejor, mayor = None, -1
    for c in orden:
        n = sum(1 for d in c.get('demandas') or [] if not d['pasa'])
        if n > mayor:
            mejor, mayor = c['nombre'], n
    comparar_texto(tabla, datos, 'ux.capacidad.caso_con_mas_no_pasa', mejor)
    caso = casos.get(mejor) or next(c for c in orden if c['nombre'] == mejor)
    comparar_texto(tabla, datos, 'ux.capacidad.no_pasan', str(mayor))
    comparar_texto(tabla, datos, 'ux.capacidad.fuera_de_curva',
                   str(sum(1 for d in caso['demandas'] if d['u'] >= 9999)))
    comparar_texto(tabla, datos, 'ux.capacidad.con_fierro', str(len(caso['demandas'])))
    dm = next((d for d in caso['demandas'] if d['id'] == col), None)
    if dm:
        for k in ('P', 'M', 'Mn', 'u'):
            comparar(tabla, datos, 'ux.capacidad.elem.%d.%s' % (col, k), dm[k])
        comparar_texto(tabla, datos, 'ux.capacidad.elem.%d.pasa' % col, str(dm['pasa']))
        comparar_texto(tabla, datos, 'ux.capacidad.elem.%d.extremo' % col, dm['extremo'])
    comparar_texto(tabla, datos, 'ux.capacidad.no_pasa.ids',
                   ','.join(str(d['id']) for d in caso['demandas'] if not d['pasa']))
    comparar_texto(tabla, datos, 'ux.capacidad.mapa_activo', 'True')
    return tabla.imprimir()


# ============================================================
# [5] EL REGISTRO MISMO
# ============================================================
def bloque_registro(datos, avisos, ed, carpeta, exigir_servidor):
    tabla = Tabla('[5] REGISTRO: fotos, log, ids de control, Excel, edificio')
    fotos = sorted(f for f in os.listdir(carpeta) if f.lower().endswith(('.jpg', '.png')))
    comparar_texto(tabla, datos, 'fotos', str(len(fotos)))
    comparar_texto(tabla, datos, 'salida', '0')
    comparar_texto(tabla, datos, 'log.errores', '0')
    tabla.texto('lineas AVISO/ERROR en registro.txt', len(avisos), 0)
    comparar_texto(tabla, datos, 'edificio', ed)
    comparar_texto(tabla, datos, 'anexo.calza', 'True')
    comparar_texto(tabla, datos, 'anexo.aviso', '')
    comparar_texto(tabla, datos, 'excel.existe', 'True')
    comparar_texto(tabla, datos, 'superposicion.aviso', '')
    comparar_texto(tabla, datos, 'superposicion.nombres', 'E1(precalculado),E2(precalculado),E3(precalculado)')
    with open(rutas.unity(ed), encoding='utf-8') as f:
        modelo = json.load(f)
    comparar_texto(tabla, datos, 'modelo.nodos', str(len(modelo['nodos'])))
    comparar_texto(tabla, datos, 'modelo.elementos', str(len(modelo['elementos'])))
    cota = (modelo.get('info') or {}).get('cota_terreno')
    if cota is not None:
        comparar(tabla, datos, 'modelo.cota_terreno', cota)
    if exigir_servidor:
        comparar_texto(tabla, datos, 'servidor.responde', 'True')
    with open(os.path.join(SEMANA05, 'estados_s5.json'), encoding='utf-8') as f:
        esperados = json.load(f)['control']['esperados'].get(ed, {})
    for k in ('columna', 'muro', 'viga', 'nodo'):
        if k in esperados:
            comparar_texto(tabla, datos, 'control.' + k, str(esperados[k]))
    # Cada foto salio con la pestana que dice su nombre.
    por_nombre = {'_panel_vista': 'Vista', '_panel_capas': 'Capas', '_panel_caso': 'Caso',
                  '_panel_elemento': 'Elemento', '_panel_modificar': 'Modificar',
                  '_panel_carga_movil': 'Carga movil', '_superposicion_': 'Caso', '_carga_movil_': 'Carga movil',
                  '_M1_': 'Modificar', '_donde_esta_': 'Elemento', '_como_esta_apoyado_': 'Elemento',
                  '_que_lo_carga_': 'Elemento', '_como_se_deforma_': 'Elemento', '_que_fuerzas_': 'Elemento',
                  '_capacidad_': 'Elemento', '_mapa_DC_leyenda': 'Caso', '_vista_general_': 'Vista'}
    for foto in fotos:
        base = os.path.splitext(foto)[0]
        esperada = next((v for k, v in por_nombre.items() if k in base), None)
        if esperada:
            comparar_texto(tabla, datos, 'foto.%s.pestana' % base, esperada)
    for a in avisos[:10]:
        decir('  registro: ' + a)
    return tabla.imprimir()


# ============================================================
def main(argv=None):
    ap = argparse.ArgumentParser(description='Compara el registro de CapturaSemana05 con Python.')
    ap.add_argument('registro', help='registro.txt que dejo CapturaSemana05')
    ap.add_argument('--salida', default=None, help='ademas, escribir la salida en este archivo')
    ap.add_argument('--sin-servidor', action='store_true',
                    help='la captura se hizo sin servidor: no exigir LIBRE ni M1')
    args = ap.parse_args(argv)

    ruta = os.path.abspath(args.registro)
    datos, avisos = leer_registro(ruta)
    ed = datos.get('edificio', 'lt2') or 'lt2'
    exigir = not args.sin_servidor

    decir('=' * 118)
    decir('  UNITY CONTRA PYTHON   registro %s' % os.path.relpath(ruta, rutas.RAIZ))
    decir('  edificio %s; %d datos; equipo %s | %s | %s | RAM %s MB | pantalla %s a %s dpi'
          % (ed, len(datos), datos.get('equipo.cpu', '?'), datos.get('equipo.so', '?'),
             datos.get('equipo.gpu', '?'), datos.get('equipo.ram_mb', '?'),
             datos.get('pantalla', '?'), datos.get('pantalla.dpi', '?')))
    decir('  tolerancia por fila = suma de sus causas (f32, ref, impr, ent32): ver el encabezado del script')
    decir('=' * 118)

    fallas = 0
    fallas += bloque_superposicion(datos, ed, exigir)
    fallas += bloque_m1(datos, ed, exigir)
    fallas += bloque_carga_movil(datos, ed)
    fallas += bloque_preguntas(datos, ed)
    fallas += bloque_registro(datos, avisos, ed, os.path.dirname(ruta), exigir)

    decir()
    decir('=' * 118)
    decir('  %s' % ('TODO CALZA: lo que muestra Unity es lo que calculo Python' if fallas == 0
                    else 'NO CALZA: %d fila(s) con FALLA (ver arriba)' % fallas))
    decir('=' * 118)
    if args.salida:
        destino = os.path.abspath(args.salida)
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(SALIDA) + '\n')
    return 1 if fallas else 0


if __name__ == '__main__':
    sys.exit(main())
