# -*- coding: utf-8 -*-
r"""
================================================================
 lanzar_unity.py  -  ABRIR EL VISOR DESDE PYTHON
================================================================
 Permite disparar la visualizacion Unity desde el notebook o la
 consola, para que todo el laboratorio se corra de una sola pasada:

     modelo OpenSees -> JSON -> visor Unity

 Modos (el edificio es opcional y por defecto el LT2):

   app [ed]           compila (una vez) la app de Windows y la
                      ejecuta. No necesita el editor abierto y arranca
                      en segundos. Es el modo para la DEMO.
   editor [ed]        abre el proyecto en el editor de Unity. Sirve
                      para trabajar en el visor, no para mostrarlo: hay
                      que apretar Play a mano.
   sincronizar [ed]   SOLO copia a StreamingAssets todo lo que el visor
                      lee de ese edificio (modelo, anexos 3 y 4,
                      superposicion, carga movil, Excel). NUNCA abre
                      Unity. Con --seco dice que copiaria sin escribir.
   build [ed]         compila la app de Windows (batch; --forzar la
                      rehace aunque exista).
   web [ed]           compila el build Web en build/web (batch).
   android [ed]       compila el APK si el editor tiene el modulo; si
                      no, lo dice y sale SIN abrir Unity.
   servidor           levanta el servidor de reanalisis (puerto 5000).

 Opciones: --seco (sincronizar, build, web, android: dice lo que haria
 sin escribir ni abrir nada), --destino CARPETA (sincronizar: copia ahi
 en vez de a las StreamingAssets), --forzar, --pantalla-completa.

 Los modos build, web y android corren Unity en batch y necesitan el
 editor CERRADO: con el proyecto abierto en otro Unity, el batch sale
 con error. Desde el editor abierto se usa el menu Laboratorio.

 ----------------------------------------------------------------
 POR QUE NO SE PUEDE "APRETAR PLAY" DESDE PYTHON
 ----------------------------------------------------------------
 El modo Play del editor es interactivo: -batchmode y Play son
 incompatibles. Por eso, para ver el modelo sin tocar el editor, se
 compila una app standalone; eso SI se puede hacer sin interfaz y
 luego ejecutarla es un proceso normal.
================================================================
"""
import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import time

# La raiz la sabe comun/rutas.py, que la busca subiendo hasta la marca
# del repo (CLAUDE.md: nunca contar dirname). Este archivo vive en
# comun/, la misma carpeta que rutas.py, y es lo unico que se deduce de
# su ubicacion.
_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)
import rutas                                 # noqa: E402

_RAIZ = rutas.RAIZ

PROYECTO_UNITY = rutas.UNITY_PROYECTO
CARPETA_BUILD = os.path.join(_RAIZ, 'build')
APP = os.path.join(CARPETA_BUILD, 'LaboratorioEstructural.exe')
CARPETA_WEB = os.path.join(CARPETA_BUILD, 'web')
APK = os.path.join(CARPETA_BUILD, 'android', 'LaboratorioEstructural.apk')

# Que edificio se muestra. Por defecto el LT2 (el de la demo). Se cambia
# con un argumento:
#
#     python comun/lanzar_unity.py app conjunto
#
# El nombre del archivo DENTRO de Unity no cambia nunca: lo fija la
# escena (ver nombre_que_lee_el_visor), y lo que se elige aca es cual de
# los data/unity/*.json se le copia encima.
EDIFICIO = 'lt2'
JSON_MODELO = rutas.unity(EDIFICIO)


# La clase C# del visor PRINCIPAL, el que dibuja la estructura. Hace
# falta nombrarla porque la escena tiene mas de un visor.
CLASE_DEL_VISOR = 'VisorEstructura'


def nombre_que_lee_el_visor(por_defecto='modelo_unity.json',
                            clase=CLASE_DEL_VISOR):
    r"""
    El archivo que el visor abre de StreamingAssets, LEIDO DE LA ESCENA.

    `VisorEstructura.nombreArchivo` tiene un valor por defecto en el C#,
    pero la escena lo pisa; y desde VisorSemana03 la escena tiene DOS
    campos 'nombreArchivo'. Tomar el primero copiaba el modelo encima del
    anexo del otro visor -- sin ningun error, la app arrancaba y
    mostraba un edificio viejo. Por eso se busca el que pertenece a la
    clase pedida: cada MonoBehaviour declara la suya en
    'm_EditorClassIdentifier' justo antes de sus campos. Si la clase no
    aparece, se cae al primero en vez de no abrir nada.
    """
    escena = os.path.join(PROYECTO_UNITY, 'Assets', 'Scenes',
                          'SampleScene.unity')
    primero = None
    try:
        with open(escena, encoding='utf-8', errors='replace') as f:
            actual = ''
            for linea in f:
                if 'm_EditorClassIdentifier:' in linea:
                    actual = linea.split('::')[-1].strip()
                elif 'nombreArchivo:' in linea:
                    n = linea.split('nombreArchivo:', 1)[1].strip()
                    if not n:
                        continue
                    if primero is None:
                        primero = n
                    if actual == clase:
                        return n
    except OSError:
        pass
    # Si la clase pedida no aparece -- alguien la renombro -- se cae al
    # primero, que es lo que se hacia antes, en vez de no abrir nada.
    return primero or por_defecto


NOMBRE_EN_UNITY = nombre_que_lee_el_visor()
STREAMING = os.path.join(rutas.STREAMING, NOMBRE_EN_UNITY)


def elegir_edificio(nombre):
    """Cambia cual data/unity/<nombre>.json se le copia al visor."""
    global EDIFICIO, JSON_MODELO
    # En minusculas, como info.edificio de los anexos (ver main).
    nombre = nombre.lower()
    EDIFICIO = nombre
    JSON_MODELO = rutas.unity(nombre)
    return JSON_MODELO


# Los data/unity/*.json que NO son un edificio: anexos y precalculos.
# Pasados como edificio, el visor recibiria un anexo como si fuera el
# modelo y arrancaria vacio sin decir por que.
_PREFIJOS_NO_EDIFICIO = ('semana', 'superposicion_', 'carga_movil_')


def edificios_disponibles():
    """Los <ed> que tienen data/unity/<ed>.json."""
    try:
        nombres = os.listdir(rutas.UNITY)
    except OSError:
        return []
    return sorted(f[:-5] for f in nombres
                  if f.endswith('.json')
                  and not f.startswith(_PREFIJOS_NO_EDIFICIO))


# ============================================================
# 1. ENCONTRAR EL EDITOR DE UNITY
# ============================================================
def buscar_unity(version=None):
    """
    Busca Unity.exe. Si se pide una version concreta, solo devuelve
    esa; si no, la que coincida con ProjectVersion.txt del proyecto,
    y como ultimo recurso la mas nueva instalada.

    Mezclar versiones de Unity en un proyecto de grupo es una fuente
    clasica de conflictos (Unity reescribe assets al abrirlos con otra
    version), asi que por defecto se exige la del proyecto.
    """
    if version is None:
        version = version_del_proyecto()

    bases = [
        r"C:\Program Files\Unity\Hub\Editor",
        r"C:\Program Files\Unity\Editor",
        os.path.expandvars(r"%LOCALAPPDATA%\Unity\Hub\Editor"),
    ]

    candidatos = []
    for base in bases:
        if not os.path.isdir(base):
            continue
        for nombre in sorted(os.listdir(base), reverse=True):
            exe = os.path.join(base, nombre, 'Editor', 'Unity.exe')
            if os.path.exists(exe):
                candidatos.append((nombre, exe))
        exe = os.path.join(base, 'Unity.exe')
        if os.path.exists(exe):
            candidatos.append(('?', exe))

    if not candidatos:
        raise FileNotFoundError(
            "No encontre Unity.exe. Instala Unity desde Unity Hub.")

    if version:
        for nombre, exe in candidatos:
            if nombre == version:
                return exe
        disponibles = ", ".join(n for n, _ in candidatos)
        raise FileNotFoundError(
            f"El proyecto pide Unity {version} y no esta instalada.\n"
            f"Instaladas: {disponibles}\n"
            f"Instalala desde Unity Hub, o pasa version='<otra>' "
            f"asumiendo el riesgo de que Unity migre los assets.")

    return candidatos[0][1]


def version_del_proyecto():
    """Lee la version exacta que declara el proyecto."""
    ruta = os.path.join(PROYECTO_UNITY, 'ProjectSettings',
                        'ProjectVersion.txt')
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding='utf-8') as f:
        for linea in f:
            if linea.startswith('m_EditorVersion:'):
                return linea.split(':', 1)[1].strip()
    return None


def unity_abierto():
    """
    True si parece que un editor de Unity tiene ESTE proyecto abierto.

    Unity crea unity/Temp/UnityLockfile al abrir el proyecto, lo tiene
    abierto mientras corre y lo borra al cerrarse. Un batch contra un
    proyecto abierto falla despues de cargar Unity entero (minutos), asi
    que conviene decirlo antes. Si el archivo quedo de un cierre brusco
    se puede abrir, y entonces no cuenta como abierto.
    (No comprobado con el editor abierto en esta maquina: si Unity no
    bloqueara el archivo, esto da False y el batch falla como antes.)
    """
    lock = os.path.join(PROYECTO_UNITY, 'Temp', 'UnityLockfile')
    if not os.path.exists(lock):
        return False
    try:
        with open(lock, 'ab'):
            pass
        return False
    except OSError:
        return True


# ============================================================
# 2. SINCRONIZAR StreamingAssets
# ============================================================
# Todo lo que el visor lee de StreamingAssets, con nombres FIJOS, y de
# donde sale en el repo (semana05/CONTRATO.md §7). Cada tupla:
#   (origen, nombre en StreamingAssets, obligatorio, regla de edificio)
# Reglas de edificio, mirando info.edificio del JSON:
#   'debe_decir'  el nombre del origen no dice de que edificio es
#                 (semana04.json es "el ultimo exportado"): solo se copia
#                 si info.edificio es el pedido.
#   'si_dice'     el nombre ya lo dice (superposicion_lt2.json): se copia
#                 salvo que info.edificio diga OTRO.
#   None          no es JSON (el Excel): manda el nombre.
#
# POR QUE NO SE COPIA UN ANEXO DE OTRO EDIFICIO: el de Semana 4 apaga
# los diagramas si no calza con el modelo, y el de Semana 3 ni avisa.
# Si no se copia, en StreamingAssets queda el que habia, que puede ser
# el correcto de una sincronizacion anterior.
def archivos_del_edificio(ed):
    return [
        (rutas.unity(ed), NOMBRE_EN_UNITY, True, 'si_dice'),
        (rutas.unity('semana03'), 'semana03.json', False, 'debe_decir'),
        (rutas.unity('semana04'), 'semana04.json', False, 'debe_decir'),
        (rutas.unity('superposicion_' + ed), 'superposicion.json', False, 'si_dice'),
        (rutas.unity('carga_movil_' + ed), 'carga_movil.json', False, 'si_dice'),
        (rutas.excel_resultados(ed), 'resultados.xlsx', False, None),
    ]


# Quien escribe cada origen, para que el aviso diga como regenerarlo.
_QUIEN_LO_GENERA = {
    'semana03.json': 'python semana03/exportar_unity.py {ed}',
    'semana04.json': 'python semana04/exportar_unity.py {ed}',
    'superposicion.json': 'lo escribe semana05/superposicion.py',
    'carga_movil.json': 'lo escribe semana05/carga_movil.py',
    'resultados.xlsx': 'python semana05/exportar_excel.py {ed}',
}


def carpetas_streaming():
    """
    Las StreamingAssets que hay que mantener al dia: la del proyecto
    (siempre) y la de cada build que exista.

    La app compilada lee SU copia, no la del proyecto: sin copiar ahi
    seguiria mostrando lo que tenia al compilarse. Windows y Web la
    tienen como carpeta suelta, asi que basta con copiar; en Android
    queda dentro del .apk y hay que recompilar.
    """
    carpetas = [rutas.STREAMING]
    for sa in (os.path.join(CARPETA_BUILD, 'LaboratorioEstructural_Data',
                            'StreamingAssets'),
               os.path.join(CARPETA_WEB, 'StreamingAssets')):
        if os.path.isdir(sa):
            carpetas.append(sa)
    return carpetas


def _edificio_del_anexo(ruta):
    """El edificio que dice un JSON (info.edificio), o None si no dice."""
    try:
        with io.open(ruta, encoding='utf-8') as fh:
            ed = (json.load(fh).get('info') or {}).get('edificio')
        return ed or None
    except Exception:
        return None


def _md5(ruta):
    h = hashlib.md5()
    with open(ruta, 'rb') as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b''):
            h.update(bloque)
    return h.hexdigest()


def _copiar_atomico(origen, destino):
    """
    Copia a un temporal al lado y lo renombra encima del destino.

    Asi un visor que lee justo en ese momento ve el archivo viejo o el
    nuevo, nunca uno a medio escribir (JsonUtility fallaria con un
    error que no dice nada del copiado). El temporal empieza con '.' y
    termina en '.tmp': Unity ignora esos nombres y no le crea .meta si
    el editor esta abierto.
    """
    carpeta = os.path.dirname(destino)
    os.makedirs(carpeta, exist_ok=True)
    tmp = os.path.join(carpeta, '.' + os.path.basename(destino) + '.tmp')
    shutil.copyfile(origen, tmp)
    try:
        os.replace(tmp, destino)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _rel(ruta):
    """Relativa al repo si esta dentro; si no (--destino afuera), absoluta."""
    try:
        rel = os.path.relpath(ruta, _RAIZ)
    except ValueError:              # otra unidad de disco
        return ruta
    return ruta if rel.startswith('..') else rel


def sincronizar(ed=None, seco=False, carpetas=None, verbose=True):
    """
    Copia a StreamingAssets todo lo del edificio `ed` (por defecto el
    elegido con elegir_edificio). No abre Unity.

    seco     : no escribe nada; dice que copiaria (y compara md5).
    carpetas : destinos; por defecto carpetas_streaming().

    Solo copia lo que cambio (md5 distinto): un archivo igual no se
    reescribe. Un origen que falta o que es de otro edificio NO borra
    ni pisa lo que haya en el destino.

    Devuelve una lista de registros (dict) por archivo y carpeta, con
    'estado' en: 'copiado', 'igual', 'se copiaria', 'no copiado',
    'error'.
    """
    ed = ed or EDIFICIO
    if carpetas is None:
        carpetas = carpetas_streaming()

    registros = []
    for origen, nombre, obligatorio, regla in archivos_del_edificio(ed):
        motivo = None
        ed_origen = None
        if not os.path.exists(origen):
            motivo = 'falta el origen'
        elif regla is not None:
            ed_origen = _edificio_del_anexo(origen)
            if ed_origen is not None and ed_origen != ed:
                motivo = "es de '%s', no de '%s'" % (ed_origen, ed)
            elif ed_origen is None and regla == 'debe_decir':
                motivo = 'no dice de que edificio es (info.edificio)'
        md5_origen = _md5(origen) if motivo is None else None

        for carpeta in carpetas:
            destino = os.path.join(carpeta, nombre)
            md5_destino = _md5(destino) if os.path.isfile(destino) else None
            reg = {'nombre': nombre, 'origen': origen, 'destino': destino,
                   'carpeta': carpeta, 'obligatorio': obligatorio,
                   'edificio_origen': ed_origen, 'motivo': motivo,
                   'md5_origen': md5_origen, 'md5_destino': md5_destino}
            if motivo is not None:
                reg['estado'] = 'no copiado'
            elif md5_destino == md5_origen:
                reg['estado'] = 'igual'
            elif seco:
                reg['estado'] = 'se copiaria'
            else:
                try:
                    _copiar_atomico(origen, destino)
                    reg['estado'] = 'copiado'
                    reg['md5_destino'] = _md5(destino)
                except OSError as e:
                    reg['estado'] = 'error'
                    reg['motivo'] = '%s (si es el Excel, esta abierto?)' % e
            registros.append(reg)

    if verbose:
        _imprimir_sincronizacion(ed, registros, carpetas, seco)
    return registros


def sincronizacion_fallida(registros, solo_modelo=False):
    """True si el modelo no quedo copiado (falta, es de otro edificio o
    no se pudo escribir) o, sin solo_modelo, si algun archivo no se pudo
    escribir.

    solo_modelo es para abrir o compilar: un Excel abierto en otra
    ventana no deberia impedir ver el edificio (se avisa igual). El modo
    'sincronizar', que existe solo para copiar, falla con cualquier
    error de escritura.
    """
    return any((r['obligatorio'] or not solo_modelo) and r['estado'] == 'error'
               or (r['obligatorio'] and r['estado'] == 'no copiado')
               for r in registros)


def _imprimir_sincronizacion(ed, registros, carpetas, seco):
    print("  Sincronizar '%s'%s" % (ed, "  (EN SECO: no se escribe nada)" if seco else ''))
    for i, c in enumerate(carpetas, 1):
        print("    [%d] %s" % (i, _rel(c)))
    indice = {c: i for i, c in enumerate(carpetas, 1)}

    por_nombre = []
    for r in registros:
        if not por_nombre or por_nombre[-1][0] != r['nombre']:
            por_nombre.append((r['nombre'], []))
        por_nombre[-1][1].append(r)

    avisos = []
    for nombre, regs in por_nombre:
        r0 = regs[0]
        print("  %s  <-  %s" % (nombre, _rel(r0['origen'])))
        if r0['motivo'] is not None and r0['estado'] == 'no copiado':
            print("      NO SE COPIA: %s" % r0['motivo'])
        else:
            print("      md5 origen %s" % r0['md5_origen'])
        for r in regs:
            n = indice.get(r['carpeta'], '?')
            if r['estado'] == 'no copiado':
                if r['md5_destino'] is None:
                    queda = 'no hay ninguno'
                else:
                    ed_dest = (_edificio_del_anexo(r['destino'])
                               if nombre.endswith('.json') else None)
                    queda = 'queda el que habia%s' % (
                        " (de '%s')" % ed_dest if ed_dest else '')
                print("      [%s] %s" % (n, queda))
            elif r['estado'] == 'error':
                print("      [%s] ERROR al escribir: %s" % (n, r['motivo']))
            elif r['estado'] == 'igual':
                print("      [%s] igual" % n)
            else:
                antes = r['md5_destino'] if r['estado'] == 'se copiaria' else None
                print("      [%s] %s%s" % (n, r['estado'],
                                            '' if r['estado'] == 'copiado'
                                            else '  (hoy %s)' % (antes or 'no existe')))
        if r0['estado'] == 'no copiado':
            como = _QUIEN_LO_GENERA.get(nombre)
            avisos.append((nombre, r0['obligatorio'], r0['motivo'],
                           como.format(ed=ed) if como else None))

    cuenta = {}
    for r in registros:
        cuenta[r['estado']] = cuenta.get(r['estado'], 0) + 1
    print("  resumen: " + ", ".join('%s %d' % (k, cuenta[k]) for k in
                                    ('copiado', 'se copiaria', 'igual',
                                     'no copiado', 'error') if k in cuenta))

    for nombre, obligatorio, motivo, como in avisos:
        print()
        if obligatorio:
            print("  ERROR: el modelo %s no se copio: %s." % (nombre, motivo))
            print("         Corre antes edificios/%s/exportar_unity.py" % ed)
        else:
            print("  OJO: %s no se copio (%s)." % (nombre, motivo))
            if 'semana0' in nombre:
                print("       El visor de Semana 4 apaga los diagramas cuando el anexo no")
                print("       calza con el modelo; el de Semana 3 no avisa.")
            if como:
                print("       Para tenerlo: %s" % como)
    print("  (este paso solo copia archivos: Unity no se abre)")


def sincronizar_json(verbose=True):
    """
    Copia a StreamingAssets (del proyecto y de las builds que existan)
    el modelo del edificio elegido y todo lo que el visor lee de el.

    Asi la app muestra SIEMPRE el ultimo modelo calculado sin tener que
    recompilarla. Si se omite este paso, el visor sigue mostrando el
    modelo viejo y no avisa: parece que los cambios no tuvieron efecto.

    Devuelve las rutas donde quedo el modelo (como antes).
    """
    registros = sincronizar(EDIFICIO, verbose=verbose)
    modelo = [r for r in registros if r['obligatorio']]
    if any(r['estado'] == 'no copiado' for r in modelo):
        motivo = modelo[0]['motivo']
        if motivo == 'falta el origen':
            raise FileNotFoundError(
                f"No existe {JSON_MODELO}. Corre antes exportar_unity.py")
        raise RuntimeError(f"No se copio {JSON_MODELO}: {motivo}")
    errores = [r for r in modelo if r['estado'] == 'error']
    if errores:
        raise RuntimeError("No se pudo escribir %s: %s"
                           % (errores[0]['destino'], errores[0]['motivo']))
    return [r['destino'] for r in modelo]


# Lo que existia antes de la Semana 5, para el notebook o un script que
# todavia lo llame. Ahora los anexos viajan con todo lo demas en
# sincronizar(); esto solo conserva la firma y lo que devolvia.
ANEXOS = ('semana03.json', 'semana04.json')


def sincronizar_anexos(verbose=True):
    """Sincroniza el edificio elegido y devuelve los anexos que NO
    calzan con el: lista de (anexo, edificio que dice el anexo)."""
    registros = sincronizar(EDIFICIO, verbose=verbose)
    no_calzan = []
    for r in registros:
        par = (r['nombre'], r['edificio_origen'])
        if (r['nombre'] in ANEXOS and r['estado'] == 'no copiado'
                and r['edificio_origen'] is not None and par not in no_calzan):
            no_calzan.append(par)
    return no_calzan


# ============================================================
# 3. CORRER UNITY EN BATCH
# ============================================================
# Cada destino de compilacion:
#   metodo de ConstruirApp, -buildTarget, carpeta del modulo en
#   <Editor>/Data/PlaybackEngines, lo que deja la build, log.
DESTINOS = {
    'windows': ('ConstruirApp.Construir', 'StandaloneWindows64',
                'WindowsStandaloneSupport', APP, 'unity_build.log'),
    'web': ('ConstruirApp.ConstruirWeb', 'WebGL',
            'WebGLSupport', os.path.join(CARPETA_WEB, 'index.html'),
            'unity_build_web.log'),
    'android': ('ConstruirApp.ConstruirAndroid', 'Android',
                'AndroidPlayer', APK, 'unity_build_android.log'),
}


class FaltaModulo(RuntimeError):
    """El editor no tiene el modulo de la plataforma pedida."""


def modulo_instalado(carpeta_modulo, version=None):
    """True si <Editor>/Data/PlaybackEngines/<carpeta_modulo> existe.

    Es donde Unity Hub instala cada 'Build Support'. Mirarlo desde
    Python evita abrir Unity (minutos) solo para que diga que falta.
    """
    unity = buscar_unity(version)
    motores = os.path.join(os.path.dirname(unity), 'Data', 'PlaybackEngines')
    # Sin distinguir mayusculas: Unity Hub instala 'WebGLSupport' pero
    # 'windowsstandalonesupport' (asi estan en 6000.5.10f1). Windows no
    # distingue, pero la comparacion explicita no depende de eso.
    try:
        instalados = {n.lower() for n in os.listdir(motores)
                      if os.path.isdir(os.path.join(motores, n))}
    except OSError:
        return False
    return carpeta_modulo.lower() in instalados


def _correr_unity(metodo, log, timeout=1800, version=None,
                  objetivo='StandaloneWindows64', seco=False):
    """Ejecuta un metodo de Editor sin abrir la interfaz.

    -buildTarget va SIEMPRE: sin el, Unity abre el proyecto en la
    ultima plataforma activa. Despues de un build Web o Android, el
    siguiente de Windows arrancaria en esa plataforma y tendria que
    cambiarla a mitad del metodo, reimportando todo.
    """
    unity = buscar_unity(version)
    cmd = [unity, '-batchmode', '-quit', '-nographics',
           '-projectPath', PROYECTO_UNITY,
           '-buildTarget', objetivo,
           '-logFile', log,
           '-executeMethod', metodo]

    if seco:
        print("  EN SECO: no se abre Unity. Se correria:")
        print("    " + subprocess.list2cmdline(cmd))
        return None, log

    os.makedirs(os.path.dirname(log), exist_ok=True)
    if os.path.exists(log):
        os.remove(log)

    print(f"  Unity: {os.path.basename(os.path.dirname(os.path.dirname(unity)))}")
    print(f"  ejecutando {metodo} ({objetivo}) ... (puede tardar varios minutos)")
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    print(f"  termino en {time.time()-t0:.0f} s (codigo {proc.returncode})")
    return proc.returncode, log


def _errores_del_log(log, n=15):
    """Saca las lineas de error del log de Unity."""
    if not os.path.exists(log):
        return ["(no se genero log)"]
    claves = ('error CS', 'BUILD FALLO', 'Exception', 'Aborting')
    salida = []
    with open(log, encoding='utf-8', errors='replace') as f:
        for linea in f:
            if any(k in linea for k in claves):
                salida.append(linea.rstrip())
    return salida[:n]


def _tamano_mb(ruta):
    if os.path.isfile(ruta):
        return os.path.getsize(ruta) / 1048576
    total = 0
    for base, _, archivos in os.walk(ruta):
        for a in archivos:
            total += os.path.getsize(os.path.join(base, a))
    return total / 1048576


# ============================================================
# 4. API PRINCIPAL
# ============================================================
def construir(destino='windows', version=None, seco=False, timeout=3600):
    """
    Compila la app para 'windows', 'web' o 'android' con Unity en batch.

    Antes de abrir Unity comprueba que el editor tenga el modulo y que
    el proyecto no este abierto en otro Unity, y sincroniza
    StreamingAssets con el edificio elegido (la build copia esa carpeta
    tal cual). Con seco=True no escribe ni abre nada: dice que haria.
    """
    metodo, objetivo, modulo, salida, nombre_log = DESTINOS[destino]

    if not modulo_instalado(modulo, version):
        raise FaltaModulo(
            f"El editor de Unity no tiene el modulo para {destino} "
            f"(falta PlaybackEngines/{modulo}). No se abrio Unity ni se "
            f"copio nada.\n"
            f"Para instalarlo (baja varios GB): Unity Hub > Installs > "
            f"{version or version_del_proyecto()} > Add modules.")
    if not seco and unity_abierto():
        raise RuntimeError(
            "Unity tiene este proyecto abierto (unity/Temp/UnityLockfile): "
            "un batch no puede abrirlo a la vez. Cierralo, o compila desde "
            "el menu Laboratorio del editor.")

    registros = sincronizar(EDIFICIO, seco=seco)
    if sincronizacion_fallida(registros, solo_modelo=True):
        raise RuntimeError("No se compila: el modelo no quedo en "
                           "StreamingAssets (ver arriba).")

    log = os.path.join(CARPETA_BUILD, nombre_log)
    codigo, log = _correr_unity(metodo, log, timeout=timeout, version=version,
                                objetivo=objetivo, seco=seco)
    if seco:
        print(f"  dejaria: {_rel(salida)}   log: {_rel(log)}")
        return salida

    if codigo != 0 or not os.path.exists(salida):
        print("\nLa compilacion FALLO. Errores del log:")
        for e in _errores_del_log(log):
            print("   ", e)
        raise RuntimeError(f"Unity no genero {_rel(salida)}. Log: {log}")

    donde = CARPETA_WEB if destino == 'web' else salida
    print(f"Build lista: {_rel(donde)} ({_tamano_mb(donde):.1f} MB)")
    return salida


def construir_app(forzar=False, version=None, seco=False):
    """
    Compila la aplicacion de Windows. Si ya existe y no se fuerza, no
    la vuelve a compilar (la build tarda varios minutos).
    """
    if os.path.exists(APP) and not forzar:
        # En seco tambien: decir "se correria Unity" cuando en realidad
        # no se correria seria mentir sobre lo que hace el modo.
        print(f"La app ya existe: {os.path.relpath(APP, _RAIZ)}"
              + ("  (EN SECO: sin --forzar no se recompilaria)" if seco else ''))
        print("  (usa --forzar, o construir_app(forzar=True), para recompilarla)")
        return APP
    return construir('windows', version=version, seco=seco, timeout=1800)


def construir_web(version=None, seco=False):
    """Compila build/web. Se sirve con cualquier servidor estatico."""
    salida = construir('web', version=version, seco=seco)
    if not seco:
        print("Para abrirlo desde el telefono (misma red):")
        print("    cd build\\web")
        print("    ..\\..\\.venv\\Scripts\\python.exe -m http.server 8080 --bind 0.0.0.0")
        print("  y en el navegador del telefono  http://<IPv4 del PC>:8080")
        print("  ('lanzar_unity.py sincronizar <ed>' actualiza sus datos sin recompilar)")
    return salida


def construir_android(version=None, seco=False):
    """Compila el APK. Sin el modulo Android lanza FaltaModulo sin abrir Unity."""
    return construir('android', version=version, seco=seco)


def abrir_visor(construir_si_falta=True, esperar=False, pantalla_completa=False):
    """
    Lanza el visor. Es lo que se llama desde el notebook.

    construir_si_falta : compila la app la primera vez.
    esperar            : si True, bloquea hasta que se cierre la app.
                         En un notebook conviene False, para poder
                         seguir usando las celdas.
    pantalla_completa  : abre la app ocupando toda la pantalla.

    La pantalla completa se pide con los argumentos ESTANDAR del player
    de Unity (-screen-fullscreen, -screen-width, -screen-height), no
    tocando la escena: asi no hace falta recompilar la app ni cambiar
    los Player Settings, y el mismo build sirve para las dos formas.
    """
    sincronizar_json()

    if not os.path.exists(APP):
        if not construir_si_falta:
            raise FileNotFoundError(
                f"No existe {APP}. Corre construir_app() primero.")
        construir_app()

    cmd = [APP]
    if pantalla_completa:
        cmd += ['-screen-fullscreen', '1',
                '-screen-width', '1920', '-screen-height', '1080']
    print(f"Lanzando {os.path.basename(APP)} ..."
          + ("  (pantalla completa: Alt+Enter o Esc para salir)"
             if pantalla_completa else ""))
    proc = subprocess.Popen(cmd, cwd=CARPETA_BUILD)
    if esperar:
        proc.wait()
    else:
        # Un momento para que alcance a fallar de forma visible si el
        # ejecutable esta roto; si no, el notebook diria "lanzado" aunque
        # la ventana nunca aparezca.
        time.sleep(2.0)
        if proc.poll() is not None:
            raise RuntimeError(
                f"La app se cerro de inmediato (codigo {proc.returncode}). "
                f"Revisa {os.path.join(CARPETA_BUILD, 'unity_build.log')}")
        print("Visor abierto. Controles: arrastrar=orbitar, "
              "derecho=panear, rueda=zoom, F=encuadrar, click=inspeccionar.")
    return proc


def abrir_servidor(puerto=5000):
    r"""
    Levanta el servidor de reanalisis en segundo plano.

    Hace falta SOLO para modificar el modelo desde Unity (cambiar una
    seccion, mover un nodo, borrar una barra) y volver a resolverlo, y
    para la superposicion con lambdas libres. El visor funciona sin el;
    simplemente no se puede reanalizar.

    Por que hace falta un servidor: la app compilada NO puede correr
    OpenSees (es Python). Entonces Unity manda el modelo por HTTP,
    Python lo resuelve y devuelve los desplazamientos. Es la misma
    separacion de siempre -- OpenSees calcula, Unity muestra -- solo que
    ahora en vivo.

    Desde la Semana 5 hay UN servidor en el puerto 5000:
    semana05/servidor_s5.py, que importa el de comun/ (/analizar) y le
    agrega /combinar y /estados. Si todavia no existe, se levanta el de
    comun/, que atiende /analizar como siempre.

    Escucha solo en 127.0.0.1: nadie fuera de este equipo llega.
    """
    candidatos = [os.path.join(_RAIZ, 'semana05', 'servidor_s5.py'),
                  os.path.join(rutas.COMUN, 'servidor_opensees.py')]
    servidor = next((s for s in candidatos if os.path.exists(s)), None)
    if servidor is None:
        raise FileNotFoundError(candidatos[-1])

    try:
        import flask  # noqa: F401
    except ImportError:
        raise RuntimeError(
            "Falta Flask. Instalalo con:\n"
            "    .venv\\Scripts\\python.exe -m pip install flask")

    print(f"Levantando {_rel(servidor)} en localhost:{puerto} ...")
    proc = subprocess.Popen([sys.executable, servidor, '--puerto', str(puerto)])
    time.sleep(2.0)
    if proc.poll() is not None:
        raise RuntimeError(
            f"El servidor se cerro de inmediato (codigo {proc.returncode}). "
            f"Puede que el puerto {puerto} este ocupado.")
    print("Servidor arriba. En el visor, el panel del editor ya puede")
    print("modificar el modelo y pedir un reanalisis.")
    print("Para detenerlo: proc.terminate() o cerrar esta consola.")
    return proc


def abrir_editor(version=None):
    """
    Abre el proyecto en el editor de Unity (para trabajar en el visor).
    Hay que apretar Play a mano: el modo Play no se puede automatizar
    desde fuera.
    """
    if unity_abierto():
        raise RuntimeError("Unity ya tiene este proyecto abierto; usa esa ventana "
                           "(para actualizar los datos: 'lanzar_unity.py sincronizar').")
    sincronizar_json()
    unity = buscar_unity(version)
    print(f"Abriendo el editor... (tarda ~1 min)")
    print("Cuando cargue: Assets/Scenes/SampleScene -> boton Play")
    return subprocess.Popen([unity, '-projectPath', PROYECTO_UNITY])


# ============================================================
MODOS = ('app', 'editor', 'sincronizar', 'build', 'web', 'android', 'servidor')


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog='lanzar_unity.py',
        description='Abre, sincroniza o compila el visor Unity.')
    ap.add_argument('modo', nargs='?', default='app', choices=MODOS)
    ap.add_argument('edificio', nargs='?', default=None,
                    help='lt2 (por defecto), ingenieria o conjunto')
    ap.add_argument('--pantalla-completa', '--fullscreen', action='store_true',
                    dest='pantalla_completa')
    ap.add_argument('--forzar', action='store_true',
                    help='build: recompilar aunque la app exista')
    ap.add_argument('--seco', action='store_true',
                    help='sincronizar/build/web/android: decir que haria, sin escribir ni abrir Unity')
    ap.add_argument('--destino', metavar='CARPETA',
                    help='sincronizar: copiar a esta carpeta en vez de a las StreamingAssets')
    args = ap.parse_args(argv)

    # Ignorar --seco en 'app' o 'editor' seria peor que fallar: quien lo
    # pide espera que no se escriba ni se abra nada, y esos modos copian a
    # StreamingAssets y lanzan la app o el editor.
    if args.seco and args.modo not in ('sincronizar', 'build', 'web', 'android'):
        ap.error("--seco no sirve con el modo '%s' (solo sincronizar, build, "
                 "web, android)" % args.modo)
    if args.destino and args.modo != 'sincronizar':
        ap.error("--destino solo sirve con el modo 'sincronizar'")

    if args.edificio and args.modo != 'servidor':
        # Los edificios y su info.edificio van en minusculas. En Windows
        # 'LT2' encuentra data/unity/lt2.json igual, pero despues ningun
        # anexo calza ("es de 'lt2', no de 'LT2'") y quedan sin copiar.
        args.edificio = args.edificio.lower()
        ruta = elegir_edificio(args.edificio)
        if (args.edificio.startswith(_PREFIJOS_NO_EDIFICIO)
                or not os.path.exists(ruta)):
            print('No hay un edificio %s (%s).\nHay: %s'
                  % (args.edificio, _rel(ruta), ', '.join(edificios_disponibles())))
            return 1
        print(f"Edificio: {args.edificio}")

    try:
        if args.modo == 'sincronizar':
            carpetas = [os.path.abspath(args.destino)] if args.destino else None
            registros = sincronizar(EDIFICIO, seco=args.seco, carpetas=carpetas)
            return 1 if sincronizacion_fallida(registros) else 0
        if args.modo == 'editor':
            abrir_editor()
        elif args.modo == 'build':
            construir_app(forzar=args.forzar, seco=args.seco)
        elif args.modo == 'web':
            construir_web(seco=args.seco)
        elif args.modo == 'android':
            construir_android(seco=args.seco)
        elif args.modo == 'servidor':
            proc = abrir_servidor()
            try:
                proc.wait()          # queda en primer plano hasta Ctrl+C
            except KeyboardInterrupt:
                proc.terminate()
        else:
            abrir_visor(pantalla_completa=args.pantalla_completa)
    except (FileNotFoundError, RuntimeError) as e:
        print("\nERROR: %s" % e)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
