# -*- coding: utf-8 -*-
r"""
================================================================
 semana04/verificar_unity_semana04.py  -  LO QUE UNITY LEYO DE VERDAD
================================================================
 test_contrato_semana04.py compara NOMBRES: claves del JSON contra
 campos del C#, leyendo el .cs como texto. Eso no prueba que Unity
 lea bien los NUMEROS. Aca se abre el editor en modo batch, se le hace
 deserializar semana04.json con sus propias clases
 (VerificarAnexoSemana04.Verificar, en unity/Assets/Editor) y se
 compara lo que escribio -- build/verificacion_unity_semana04.json --
 campo a campo contra el anexo.

 Correr:
   python semana04/verificar_unity_semana04.py              abre Unity en batch
   python semana04/verificar_unity_semana04.py --comparar build/verificacion_unity_semana04.json
                                                            solo compara un reporte

 Codigos de salida: 0 todo calza, 1 algo no calza o Unity fallo,
 2 Unity ya esta abierto (el proyecto no se puede abrir dos veces:
 el batch se cae sin decir por que, o espera el lock para siempre).

 ----------------------------------------------------------------
 LA TOLERANCIA SE MIDE: DE DONDE SALE CADA PEDAZO
 ----------------------------------------------------------------
 Entre el anexo y el reporte hay dos redondeos, y nada mas:

   1. JsonUtility guarda cada numero en un float de C# (32 bits):
      el float mas cercano, a lo mas medio intervalo entre floats
      vecinos = 2^-24 |a| ~ 6e-8 |a|   (trazabilidad.medio_ulp32).
   2. El C# escribe ese float como texto con algun formato. Si es de
      ida y vuelta (JsonUtility.ToJson, "R", "G9") el texto devuelve
      EXACTAMENTE el mismo float: float32(b) == float32(a), sin cota.
      Si escribe menos digitos (ToString() comun da 7), el texto se
      corre a lo mas medio ultimo digito, y los digitos se MIDEN en el
      reporte: el mayor numero de significativos entre todos sus
      numeros (G7 borra ceros finales: 4130.5298 sale '4130.53', y
      medido valor por valor aparentaria tres decimales).

 Asi que un valor calza si float32(b) == float32(a), o si
 |b - a| <= medio_ulp32(a) + medio_digito(b) (con el piso doble de
 trazabilidad.calza). No hay un 1e-6 elegido.

 Y el 1e-6 max(1, |a|) sirve de CONTROL de resolucion: con 7 digitos
 significativos el peor caso es 6e-8 + 5e-7 = 5.6e-7 relativo, bajo
 1e-6; y bajo |a| = 1 un piso absoluto de 1e-6 es cien veces menor
 que el ultimo decimal que escribe el anexo (4 decimales en fuerzas,
 estaciones y curvas). Si la cota medida de algun valor lo supera, el
 reporte trae tan pocos digitos que no puede distinguir un error de
 Unity de su propio redondeo, y eso se dice como falla: no se aprueba
 un reporte que no puede fallar.

 ----------------------------------------------------------------
 QUE BLOQUES ESPERA DEL REPORTE
 ----------------------------------------------------------------
 Los escalares (edificio, caso_por_defecto, columna_demo, muro_demo,
 n_casos, n_elementos, n_familias, nombres_casos, errores) y cinco
 bloques, cada uno el objeto C# tal como JsonUtility lo lleno:

   esfuerzos_columna_demo   EsfuerzosS4 de columna_demo en caso_por_defecto
   demanda_columna_demo     DemandaS4 de columna_demo en caso_por_defecto
   demanda_muro_demo        DemandaS4 de muro_demo en caso_por_defecto
   familia_columna_demo     FamiliaPM de columna_demo (clave, P, Mn, Mmax)
   elemento_columna_demo    ElementoS4 de columna_demo
   elemento_muro_demo       ElementoS4 de muro_demo (prueba momento_en_el_plano)

 Si el reporte no trae un bloque o un campo, se dice cual y que trae
 en cambio: un campo ausente NO se da por bueno.
================================================================
"""
from __future__ import annotations

import io
import json
import math
import os
import subprocess
import sys
import time

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_AQUI), 'comun'))
import rutas                                 # noqa: E402
rutas.entrar(__file__)

# Las cotas medidas viven en trazabilidad.py y las usa tambien
# verificar_semana04.py: una sola definicion del redondeo de float32.
import trazabilidad as tz                    # noqa: E402

UNITY_EXE = r'C:/Program Files/Unity/Hub/Editor/6000.5.10f1/Editor/Unity.exe'
METODO = 'VerificarAnexoSemana04.Verificar'
BUILD = os.path.join(rutas.RAIZ, 'build')
LOG = os.path.join(BUILD, 'unity_verificar_s4.log')
REPORTE = os.path.join(BUILD, 'verificacion_unity_semana04.json')
# Un 'build/...' relativo en el C# se resuelve contra el directorio de
# trabajo de Unity, que en batch es el PROYECTO (unity/), no la raiz del
# repo. Se busca en los dos lados y se dice donde aparecio.
REPORTE_EN_PROYECTO = os.path.join(rutas.UNITY_PROYECTO, 'build',
                                   'verificacion_unity_semana04.json')
ANEXO = os.path.join(rutas.STREAMING, 'semana04.json')

# Importar el proyecto la primera vez puede tardar varios minutos.
TIMEOUT_S = 1800

RESOLUCION_REL = 1e-6

ESCALARES = ('edificio', 'caso_por_defecto', 'columna_demo', 'muro_demo')
CONTEOS = (('n_casos', 'casos'), ('n_elementos', 'elementos'), ('n_familias', 'familias'))
CAMPOS_FAMILIA = ('clave', 'P', 'Mn', 'Mmax')

fallos = []


def check(cond, msg, detalle=''):
    print('  [%s] %s' % ('OK  ' if cond else 'FALLA', msg))
    if detalle:
        for linea in str(detalle).split('\n'):
            print('         %s' % linea)
    if not cond:
        fallos.append(msg)
    return cond


class Numero(float):
    """Un float leido del reporte que recuerda su texto: de ahi se mide
    cuantos digitos escribio Unity."""

    def __new__(cls, texto):
        n = float.__new__(cls, texto)
        n.texto = texto
        return n


def leer_reporte(ruta):
    with io.open(ruta, encoding='utf-8-sig') as f:
        return json.load(f, parse_float=Numero)


# ============================================================
# COMPARACION DE UN VALOR
# ============================================================
class Cuenta:
    """Lo que se imprime de un bloque: cuantos valores, cuantos iguales
    al float32 exacto, el peor error y cuanto se acerco a su cota."""

    def __init__(self):
        self.n = 0
        self.identicos = 0
        self.peor_error = 0.0
        self.peor_cociente = 0.0
        self.peor_resolucion = 0.0
        self.diferencias = []

    def resumen(self):
        return ('%d valores, %d con float32 identico, peor |b-a| = %.3g, '
                'peor error/cota = %.3f, peor cota/(1e-6 max(1,|a|)) = %.3f'
                % (self.n, self.identicos, self.peor_error, self.peor_cociente,
                   self.peor_resolucion))


def significativos(texto):
    """Digitos significativos escritos en un numero: '-4.13e+03' -> 3."""
    s = str(texto).strip().lower().lstrip('+-').split('e', 1)[0].replace('.', '')
    return len(s.lstrip('0'))


def digitos_del_reporte(valor):
    """
    Cuantos digitos significativos usa el C# para escribir, medido sobre
    TODOS los numeros con decimales del reporte: el mayor. Se mide en la
    familia y no valor por valor porque un formato como G7 borra los
    ceros del final: 4130.5298 sale '4130.53', y ese texto aparenta
    tres decimales cuando el redondeo fue en el septimo digito.
    """
    if isinstance(valor, Numero):
        return significativos(valor.texto)
    if isinstance(valor, dict):
        valor = list(valor.values())
    if isinstance(valor, list):
        return max([digitos_del_reporte(v) for v in valor] or [0])
    return 0


# Lo fija comparar_reporte al leer el reporte; 0 = sin medir.
DIGITOS = {'reporte': 0}


def cota_float(a, b):
    """
    Cuanto puede discrepar b (leido del reporte) de a (el anexo) por los
    dos redondeos del encabezado: el float32 de JsonUtility y los
    digitos con que el C# escribio el reporte. Del segundo se toma lo
    menor entre el medio ultimo digito del propio texto (cota segura
    para cualquier formato) y el de los D digitos medidos en la familia
    (el de un formato de digitos significativos, que es lo que escriben
    JsonUtility.ToJson, "R", "G9" y ToString()).
    """
    texto = getattr(b, 'texto', None)
    digito = 0.0
    if texto is not None and float(b) != 0.0:
        digito = tz.medio_digito_de_texto(texto)
        d = DIGITOS['reporte']
        if d > 0:
            exponente = math.floor(math.log10(abs(float(b))))
            digito = min(digito, 0.5 * 10.0 ** (exponente - d + 1))
    return tz.medio_ulp32(a) + digito


def comparar_valor(ruta, a, b, cuenta):
    """Compara un valor del anexo con el del reporte; anota en cuenta."""
    if isinstance(a, bool) or isinstance(b, bool):
        if a is not b:
            cuenta.diferencias.append('%s: anexo %r, Unity %r' % (ruta, a, b))
        cuenta.n += 1
        return
    if isinstance(a, str) or isinstance(b, str):
        if a != b:
            cuenta.diferencias.append('%s: anexo %r, Unity %r' % (ruta, a, b))
        cuenta.n += 1
        return
    if isinstance(a, list) or isinstance(b, list):
        if not (isinstance(a, list) and isinstance(b, list)) or len(a) != len(b):
            cuenta.diferencias.append('%s: anexo largo %s, Unity largo %s' % (
                ruta, len(a) if isinstance(a, list) else '(no es lista)',
                len(b) if isinstance(b, list) else '(no es lista)'))
            return
        for i, (x, y) in enumerate(zip(a, b)):
            comparar_valor('%s[%d]' % (ruta, i), x, y, cuenta)
        return
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        cuenta.diferencias.append('%s: anexo %r, Unity %r (tipos distintos)' % (ruta, a, b))
        return

    cuenta.n += 1
    if isinstance(a, int) and not isinstance(b, float):
        # Un int de C# no redondea: tiene que ser el mismo entero.
        if int(a) != int(b):
            cuenta.diferencias.append('%s: anexo %d, Unity %d' % (ruta, a, b))
        else:
            cuenta.identicos += 1
        return

    a, b_f = float(a), b
    error = abs(a - float(b_f))
    cuenta.peor_error = max(cuenta.peor_error, error)
    if tz.a_float32(a) == tz.a_float32(float(b_f)):
        cuenta.identicos += 1
        return
    cota = cota_float(a, b_f)
    control = RESOLUCION_REL * max(1.0, abs(a))
    cuenta.peor_cociente = max(cuenta.peor_cociente, error / cota if cota > 0 else 0.0)
    cuenta.peor_resolucion = max(cuenta.peor_resolucion, cota / control)
    if not tz.calza(a, b_f, cota):
        cuenta.diferencias.append('%s: anexo %r, Unity %s, |b-a| = %.3g > cota %.3g'
                                  % (ruta, a, getattr(b_f, 'texto', b_f), error, cota))
    elif cota > control:
        cuenta.diferencias.append(
            '%s: el reporte escribio %s, con cota %.3g > 1e-6 max(1,|a|) = %.3g: '
            'muy pocos digitos para distinguir un error de Unity' % (
                ruta, getattr(b_f, 'texto', b_f), cota, control))


def comparar_bloque(nombre, descripcion, esperado, reporte, campos=None):
    """
    Un bloque del reporte contra su objeto del anexo, campo a campo. Un
    campo que el reporte no trae es una FALLA con nombre y apellido.
    """
    print()
    print('  %s  <-  %s' % (nombre, descripcion))
    if esperado is None:
        print('  [--  ] el anexo no tiene ese objeto: no hay nada que comparar')
        return
    if nombre not in reporte:
        check(False, 'el reporte trae el bloque %r' % nombre,
              'claves del reporte: %s' % ', '.join(sorted(reporte)))
        return
    bloque = reporte[nombre]
    if not check(isinstance(bloque, dict), 'el bloque %r es un objeto' % nombre):
        return
    campos = list(campos or esperado.keys())
    faltan = [c for c in campos if c not in bloque]
    check(not faltan, 'el bloque %r trae los %d campos esperados' % (nombre, len(campos)),
          'no trae: %s  (trae: %s)' % (', '.join(faltan), ', '.join(sorted(bloque)))
          if faltan else '')
    cuenta = Cuenta()
    for c in campos:
        if c in bloque:
            comparar_valor('%s.%s' % (nombre, c), esperado[c], bloque[c], cuenta)
    diferencias = cuenta.diferencias
    check(not diferencias, '%s: lo que Unity leyo calza con el anexo' % nombre,
          cuenta.resumen() + ('\n' + '\n'.join(diferencias[:10]) if diferencias else '')
          + ('\n... y %d mas' % (len(diferencias) - 10) if len(diferencias) > 10 else ''))


# ============================================================
# EL REPORTE ENTERO CONTRA EL ANEXO
# ============================================================
def _por_id(lista, eid):
    return next((o for o in lista if o.get('id') == eid), None)


def esperados(anexo):
    """Los seis objetos del anexo que el reporte tiene que repetir."""
    info = anexo['info']
    defecto = next((c for c in anexo['casos'] if c['nombre'] == info['caso_por_defecto']), None)
    col, muro = info['columna_demo'], info['muro_demo']
    elemento = _por_id(anexo['elementos'], col)
    fam = elemento.get('familia', -1) if elemento else -1
    return defecto, [
        ('esfuerzos_columna_demo', 'EsfuerzosS4 de la columna %s en %s' % (col, info['caso_por_defecto']),
         _por_id(defecto['esfuerzos'], col) if defecto else None, None),
        ('demanda_columna_demo', 'DemandaS4 de la columna %s en %s' % (col, info['caso_por_defecto']),
         _por_id(defecto['demandas'], col) if defecto else None, None),
        ('demanda_muro_demo', 'DemandaS4 del muro %s en %s' % (muro, info['caso_por_defecto']),
         _por_id(defecto['demandas'], muro) if defecto else None, None),
        ('familia_columna_demo', 'FamiliaPM %s de la columna %s' % (fam, col),
         anexo['familias'][fam] if 0 <= fam < len(anexo['familias']) else None, CAMPOS_FAMILIA),
        ('elemento_columna_demo', 'ElementoS4 de la columna %s' % col, elemento, None),
        ('elemento_muro_demo', 'ElementoS4 del muro %s' % muro,
         _por_id(anexo['elementos'], muro), None),
    ]


def comparar_reporte(reporte, anexo):
    info = anexo['info']
    print()
    print('[1] lo que Unity dice que leyo: escalares, conteos y nombres de caso')
    if not check(isinstance(reporte, dict), 'el reporte es un objeto JSON'):
        return
    DIGITOS['reporte'] = digitos_del_reporte(reporte)
    print('    el C# escribio el reporte con hasta %d digitos significativos (medido en'
          % DIGITOS['reporte'])
    print('    todos sus numeros con decimales): de ahi sale el medio digito de cada cota')
    errores = reporte.get('errores')
    check(errores is not None, 'el reporte trae el campo errores',
          '' if errores is not None else 'claves del reporte: %s' % ', '.join(sorted(reporte)))
    check(not errores, 'Unity no reporto errores al leer el anexo',
          '\n'.join(str(e) for e in errores) if errores else '')

    cuenta = Cuenta()
    faltan = []
    for clave in ESCALARES:
        if clave in reporte:
            comparar_valor(clave, info[clave], reporte[clave], cuenta)
        else:
            faltan.append(clave)
    for clave, lista in CONTEOS:
        if clave in reporte:
            comparar_valor(clave, len(anexo[lista]), reporte[clave], cuenta)
        else:
            faltan.append(clave)
    if 'nombres_casos' in reporte:
        comparar_valor('nombres_casos', [c['nombre'] for c in anexo['casos']],
                       reporte['nombres_casos'], cuenta)
    else:
        faltan.append('nombres_casos')
    check(not faltan, 'el reporte trae los %d escalares esperados'
          % (len(ESCALARES) + len(CONTEOS) + 1),
          'no trae: %s  (trae: %s)' % (', '.join(faltan), ', '.join(sorted(reporte)))
          if faltan else '')
    print('    anexo: %s, %s por defecto, columna %s, muro %s, %d casos, %d elementos, '
          '%d familias' % (info['edificio'], info['caso_por_defecto'], info['columna_demo'],
                           info['muro_demo'], len(anexo['casos']), len(anexo['elementos']),
                           len(anexo['familias'])))
    check(not cuenta.diferencias, 'escalares: Unity leyo lo mismo que el anexo',
          '\n'.join(cuenta.diferencias))

    print()
    print('[2] los objetos de la columna y el muro demo, campo a campo')
    print('    calza si float32(b) == float32(a), o |b-a| <= medio_ulp32(a) + medio digito')
    print('    escrito de b; y esa cota tiene que quedar bajo 1e-6 max(1, |a|)')
    _defecto, bloques = esperados(anexo)
    for nombre, descripcion, objeto, campos in bloques:
        comparar_bloque(nombre, descripcion, objeto, reporte, campos)


# ============================================================
# UNITY EN BATCH
# ============================================================
def unity_abierto():
    """True si hay un Unity.exe corriendo (tasklist de Windows)."""
    try:
        r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Unity.exe', '/NH'],
                           capture_output=True, text=True, errors='replace')
    except OSError:
        return False
    return 'unity.exe' in (r.stdout or '').lower()


def cola_del_log(n=25):
    if not os.path.isfile(LOG):
        return '(no hay log en %s)' % LOG
    with io.open(LOG, encoding='utf-8', errors='replace') as f:
        lineas = f.read().splitlines()
    claves = ('error', 'exception', 'executemethod', 'verificaranexo', 'aborting')
    utiles = [l for l in lineas if any(c in l.lower() for c in claves)]
    return '\n'.join((utiles or lineas)[-n:])


def correr_unity():
    """Abre el editor en batch. Devuelve (ruta del reporte o None, codigo)."""
    if unity_abierto():
        print('  Unity.exe esta abierto. Cierralo y vuelve a correr: el proyecto no se')
        print('  puede abrir dos veces y el modo batch fallaria o quedaria esperando.')
        return None, 2
    if not os.path.isfile(UNITY_EXE):
        check(False, 'existe el editor %s' % UNITY_EXE)
        return None, 1
    os.makedirs(BUILD, exist_ok=True)
    # Un reporte viejo aprobaria sin que Unity haya corrido: se borra antes.
    for viejo in (REPORTE, REPORTE_EN_PROYECTO):
        if os.path.isfile(viejo):
            os.remove(viejo)
    comando = [UNITY_EXE, '-batchmode', '-quit', '-nographics',
               '-projectPath', rutas.UNITY_PROYECTO, '-logFile', LOG,
               '-executeMethod', METODO]
    print('  %s' % ' '.join('"%s"' % c if ' ' in c else c for c in comando))
    t0 = time.time()
    try:
        r = subprocess.run(comando, cwd=rutas.RAIZ, timeout=TIMEOUT_S)
        codigo = r.returncode
    except subprocess.TimeoutExpired:
        check(False, 'Unity termino antes de %d s' % TIMEOUT_S, cola_del_log())
        return None, 1
    print('  Unity termino en %.0f s con codigo %d   (log: %s)'
          % (time.time() - t0, codigo, os.path.relpath(LOG, rutas.RAIZ)))
    check(codigo == 0, 'Unity salio con codigo 0', '' if codigo == 0 else cola_del_log())
    for ruta in (REPORTE, REPORTE_EN_PROYECTO):
        if os.path.isfile(ruta) and os.path.getmtime(ruta) >= t0 - 1.0:
            if ruta != REPORTE:
                print('  el reporte aparecio en %s (build/ relativo al proyecto)'
                      % os.path.relpath(ruta, rutas.RAIZ))
            return ruta, (0 if codigo == 0 else 1)
    check(False, 'Unity escribio %s' % os.path.relpath(REPORTE, rutas.RAIZ), cola_del_log())
    return None, 1


# ============================================================
def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    print('=' * 72)
    print('  LO QUE UNITY LEYO DE semana04.json, CONTRA EL ANEXO')
    print('=' * 72)
    if not os.path.isfile(ANEXO):
        print('  no existe %s: corre python semana04/exportar_unity.py'
              % os.path.relpath(ANEXO, rutas.RAIZ))
        return 1
    # Unity lee la copia de StreamingAssets; se compara contra ESA.
    with io.open(ANEXO, encoding='utf-8') as f:
        anexo = json.load(f)
    print('  anexo   %s' % os.path.relpath(ANEXO, rutas.RAIZ))

    if '--comparar' in argv:
        i = argv.index('--comparar')
        if i + 1 >= len(argv):
            print('  --comparar necesita la ruta de un reporte')
            return 1
        ruta = os.path.abspath(argv[i + 1])
        print('  reporte %s  (sin abrir Unity)' % ruta)
    else:
        ruta, codigo = correr_unity()
        if ruta is None:
            if codigo == 2:
                return 2
            print('  FALLARON %d: %s' % (len(fallos), '; '.join(fallos)))
            return codigo
    if not os.path.isfile(ruta):
        print('  no existe el reporte %s' % ruta)
        return 1
    try:
        reporte = leer_reporte(ruta)
    except ValueError as err:
        check(False, 'el reporte es JSON valido', str(err))
        reporte = None
    if reporte is not None:
        comparar_reporte(reporte, anexo)

    print()
    print('=' * 72)
    if fallos:
        print('  FALLARON %d:' % len(fallos))
        for f in fallos:
            print('    - %s' % f)
        return 1
    print('  UNITY LEE EL ANEXO DE SEMANA 4 TAL COMO PYTHON LO ESCRIBIO')
    print('=' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())
