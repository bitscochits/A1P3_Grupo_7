# -*- coding: utf-8 -*-
r"""
================================================================
 semana05/compilar_unity.py  -  COMPILAR LOS C# SIN ABRIR UNITY
================================================================
 Compila Assembly-CSharp (unity/Assets/**, fuera de las carpetas
 Editor) y Assembly-CSharp-Editor (unity/Assets/**/Editor/**) con el
 dotnet que trae la instalacion de Unity, y dice cuantos errores CS
 hay y en que archivo. No abre Unity, no usa batchmode y NO escribe
 nada dentro del repositorio.

 Correr:
   .venv\Scripts\python.exe semana05\compilar_unity.py
   .venv\Scripts\python.exe semana05\compilar_unity.py --solo unity\Assets\Scripts\PanelUI.cs
   .venv\Scripts\python.exe semana05\compilar_unity.py --solo A.cs B.cs --avisos

 Codigo de salida:
   0  compila (o, con --solo, tus archivos no tienen errores CS)
   1  hay errores CS: cualquiera sin --solo; con --solo, solo si estan
      en los archivos pedidos
   2  no se pudo verificar: faltan los .csproj o el dotnet, fallo la
      herramienta (MSB/NETSDK), el ensamblado de un archivo pedido no
      se llego a compilar, o una ruta de --solo no es un .cs existente
      dentro de unity/Assets (si no, sus errores saldrian como ajenos y
      el OK seria por vacio)

 LO QUE NO REVISA
   Los .csproj son los del EDITOR: definen UNITY_EDITOR y referencian
   UnityEditor.dll tambien en Assembly-CSharp. Un script de Scripts/
   que use UnityEditor sin '#if UNITY_EDITOR', o codigo dentro de
   '#if UNITY_ANDROID' / '#if UNITY_WEBGL' / '#if !UNITY_EDITOR',
   compila aca y recien falla al construir la app. Para eso: no usar
   UnityEditor fuera de Assets/Editor, y la build de la integracion.

 ----------------------------------------------------------------
 POR QUE EXISTE
 ----------------------------------------------------------------
 En la Semana 5 varios agentes editan los C# a la vez con Unity
 cerrado. Sin compilar, un error de tipeo en un archivo recien se ve
 al abrir Unity -- y en Unity un solo error CS bloquea TODOS los
 scripts (Add Component, Play, la build). Con esto cada uno compila lo
 suyo en unos segundos y sin pisar a nadie.

 ----------------------------------------------------------------
 COMO LO HACE
 ----------------------------------------------------------------
 1. Copia unity/Assembly-CSharp.csproj y Assembly-CSharp-Editor.csproj
    a un directorio temporal NUEVO (tempfile.mkdtemp). Cada corrida
    tiene el suyo: dos agentes compilando a la vez no comparten obj/.
 2. Vuelve absolutas las rutas relativas (Assets\, Library\,
    Packages\) de los Include y los HintPath. Las de salida
    (Temp\obj, Temp\bin) quedan relativas A PROPOSITO: asi caen en el
    temporal y no en unity/Temp.
 3. Cambia la lista fija de <Compile> por comodines. Los .csproj los
    genera Unity con los .cs que existian la ultima vez que se abrio;
    un archivo nuevo no estaria en la lista y no se compilaria -- el
    peor caso: "compila" porque no se mira.
 4. dotnet build del csproj del editor, que por su ProjectReference
    compila primero Assembly-CSharp.

 Los .csproj NO estan en git (.gitignore: *.csproj): los regenera
 Unity al abrir el proyecto. Si faltan, se dice como generarlos.

 ----------------------------------------------------------------
 CON --solo
 ----------------------------------------------------------------
 Los errores en los archivos pedidos hacen salir con 1. Los de otros
 archivos se imprimen como AVISO: probablemente son de otro agente
 que esta a mitad de su edicion. Ojo con dos casos que no son tuyos
 pero te afectan:
   - un error ajeno puede arrastrar errores en tu archivo (un tipo
     que dejo de existir): se ven como tuyos, y hay que leerlos;
   - si Assembly-CSharp no compila, Assembly-CSharp-Editor no se
     compila. Si pediste un archivo del editor, sale con 2.
================================================================
"""
from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_AQUI), 'comun'))
import rutas                                 # noqa: E402

UNITY = rutas.UNITY_PROYECTO
SEP = '\\'

# (ensamblado, csproj, comodin de inclusion, comodin de exclusion)
# Es la regla de Unity para los scripts sin .asmdef: todo lo que esta
# bajo una carpeta 'Editor' va al ensamblado del editor; el resto, al
# del juego. Hoy no hay .asmdef ni Plugins en Assets (comprobado).
ENSAMBLADOS = (
    ('Assembly-CSharp', 'Assembly-CSharp.csproj',
     r'Assets\**\*.cs', r'Assets\**\Editor\**\*.cs'),
    ('Assembly-CSharp-Editor', 'Assembly-CSharp-Editor.csproj',
     r'Assets\**\Editor\**\*.cs', ''),
)

VERSION_POR_DEFECTO = '6000.5.10f1'

# archivo(linea,col): error CS0103: mensaje [proyecto]
# Tambien sin posicion: 'CSC : error CS2001: ...' o un .targets de MSBuild.
PATRON = re.compile(
    r'^\s*(?P<origen>.*?)'
    r'(?:\((?P<linea>\d+),(?P<col>\d+)(?:,\d+,\d+)?\))?'
    r'\s*:\s*(?P<nivel>error|warning)\s+(?P<codigo>[A-Za-z]+\d+)\s*:\s*'
    r'(?P<mensaje>.*?)'
    r'(?:\s+\[(?P<proyecto>[^\]]+)\])?\s*$')


# ============================================================
# HERRAMIENTAS
# ============================================================
def version_de_unity():
    """La version que declara el proyecto (ProjectVersion.txt)."""
    ruta = os.path.join(UNITY, 'ProjectSettings', 'ProjectVersion.txt')
    try:
        with io.open(ruta, encoding='utf-8') as f:
            for linea in f:
                if linea.startswith('m_EditorVersion:'):
                    return linea.split(':', 1)[1].strip()
    except OSError:
        pass
    return VERSION_POR_DEFECTO


def buscar_dotnet(explicito=None):
    """El dotnet.exe de la instalacion de Unity de la version del proyecto.

    Se usa ESE y no uno del sistema: trae el SDK con el que se probaron
    los .csproj que genera Unity (netstandard2.1, analizadores de Unity),
    y no exige instalar nada.
    """
    if explicito:
        return explicito if os.path.isfile(explicito) else None
    version = version_de_unity()
    bases = [r'C:\Program Files\Unity\Hub\Editor',
             os.path.expandvars(r'%LOCALAPPDATA%\Unity\Hub\Editor'),
             r'C:\Program Files\Unity\Editor']
    for base in bases:
        for sub in ((version, 'Editor'), ('',)):
            exe = os.path.join(base, *sub, 'Data', 'DotNetSdk', 'dotnet.exe')
            if os.path.isfile(exe):
                return exe
    return None


def _escapar_msbuild(ruta):
    """MSBuild interpreta % $ @ ; ' en los atributos: se escapan."""
    for c in '%$@;\'':
        ruta = ruta.replace(c, '%%%02X' % ord(c))
    return ruta


def preparar_csproj(texto, carpeta_unity, incluir, excluir):
    """El csproj de Unity, listo para compilar desde otra carpeta."""
    base = _escapar_msbuild(os.path.abspath(carpeta_unity).rstrip('\\/')) + SEP

    # 1) La lista fija de .cs se reemplaza por comodines.
    texto = re.sub(r'[ \t]*<Compile Include="[^"]*"\s*/>\r?\n?', '', texto)
    compilar = '    <Compile Include="%s%s"%s />\n' % (
        base, incluir, (' Exclude="%s%s"' % (base, excluir)) if excluir else '')
    ancla = '<Import Project="Sdk.targets"'
    if ancla not in texto:
        raise ValueError('el csproj no tiene %s: formato de Unity desconocido' % ancla)
    texto = texto.replace(ancla, '<ItemGroup>\n' + compilar + '  </ItemGroup>\n  ' + ancla, 1)

    # 2) Rutas relativas al proyecto de Unity -> absolutas.
    texto = re.sub(r'(Include=")((?:Assets|Library|Packages)\\)',
                   lambda m: m.group(1) + base + m.group(2), texto)
    texto = re.sub(r'(<HintPath>)((?:Assets|Library|Packages)\\)',
                   lambda m: m.group(1) + base + m.group(2), texto)
    return texto


def _normal(ruta):
    return os.path.normcase(os.path.normpath(os.path.abspath(ruta)))


def resolver_solo(rutas_pedidas):
    """Las rutas de --solo, absolutas, o None si alguna no sirve.

    Acepta relativas al repo o al cwd, y un nombre suelto ('PanelUI.cs')
    si hay UN solo .cs con ese nombre en unity/Assets.

    Una ruta que no es un .cs existente dentro de unity/Assets NO se
    acepta: ningun error del compilador calzaria con ella, todos
    saldrian como "ajenos" y el veredicto seria OK sin haber mirado el
    archivo (aprobar por vacio). Pasaba con '--solo PanelUI.cs' desde la
    raiz del repo."""
    assets = _normal(os.path.join(UNITY, 'Assets'))
    salida, malas = [], []
    for r in rutas_pedidas:
        candidatas = [r] if os.path.isabs(r) else [os.path.join(rutas.RAIZ, r), r]
        elegida = next((c for c in candidatas if os.path.isfile(c)), None)
        if elegida is None and not os.path.isabs(r) and os.path.basename(r) == r:
            hallados = [os.path.join(d, r) for d, _, archivos in os.walk(assets)
                        if r in archivos]
            if len(hallados) == 1:
                elegida = hallados[0]
            elif len(hallados) > 1:
                malas.append('%s: hay %d con ese nombre en unity/Assets; da la ruta'
                             % (r, len(hallados)))
                continue
        if elegida is None:
            malas.append('%s: no existe' % r)
            continue
        normal = _normal(elegida)
        if not normal.lower().endswith('.cs'):
            malas.append('%s: no es un .cs' % r)
        elif not normal.startswith(assets + os.sep):
            malas.append('%s: no esta dentro de unity/Assets (no se compila)' % r)
        else:
            salida.append(normal)
    if malas:
        for m in malas:
            print('  --solo: ' + m)
        return None
    return salida


def ensamblado_de_archivo(ruta_normal):
    """A que ensamblado va un .cs, con la misma regla de los comodines:
    una carpeta 'Editor' DENTRO de Assets (no en la ruta del repo)."""
    assets = _normal(os.path.join(UNITY, 'Assets'))
    rel = os.path.relpath(ruta_normal, assets) if ruta_normal.startswith(assets + os.sep) \
        else ruta_normal
    partes = rel.split(os.sep)[:-1]
    return 'Assembly-CSharp-Editor' if 'editor' in [p.lower() for p in partes] \
        else 'Assembly-CSharp'


# ============================================================
# COMPILAR
# ============================================================
def compilar(dotnet, carpeta, verbose=False):
    """dotnet build en la carpeta temporal. Devuelve (codigo, lineas, segundos)."""
    csproj_editor = os.path.join(carpeta, ENSAMBLADOS[1][1])
    cmd = [dotnet, 'build', csproj_editor, '-nologo',
           '-v', 'n' if verbose else 'q',
           '-nodeReuse:false', '-tl:off', '-clp:NoSummary;ForceNoAlign']
    env = dict(os.environ,
               DOTNET_CLI_TELEMETRY_OPTOUT='1', DOTNET_NOLOGO='1',
               DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1',
               MSBUILDDISABLENODEREUSE='1',
               # Mensajes en ingles: el formato 'error CS' se lee igual,
               # pero asi los textos se pueden buscar en la documentacion.
               DOTNET_CLI_UI_LANGUAGE='en')
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=carpeta, env=env, capture_output=True,
                          timeout=900)
    texto = (proc.stdout or b'').decode('utf-8', errors='replace') + '\n' + \
        (proc.stderr or b'').decode('utf-8', errors='replace')
    return proc.returncode, texto.splitlines(), time.time() - t0


def leer_diagnosticos(lineas):
    """Los error/warning del log, sin repetir (MSBuild los repite)."""
    vistos, salida = set(), []
    for linea in lineas:
        m = PATRON.match(linea)
        if not m:
            continue
        d = m.groupdict()
        proyecto = os.path.basename(d['proyecto'] or '')
        d['ensamblado'] = proyecto[:-len('.csproj')] if proyecto.endswith('.csproj') else ''
        origen = d['origen'].strip()
        d['archivo'] = _normal(origen) if d['linea'] and origen.lower().endswith('.cs') else ''
        if not d['ensamblado'] and d['archivo']:
            d['ensamblado'] = ensamblado_de_archivo(d['archivo'])
        clave = (d['nivel'], d['codigo'], d['archivo'] or origen, d['linea'], d['col'],
                 d['mensaje'], d['ensamblado'])
        if clave in vistos:
            continue
        vistos.add(clave)
        salida.append(d)
    return salida


def _texto(d):
    if d['archivo']:
        # Se muestra la ruta como la escribio el compilador (con sus
        # mayusculas); 'archivo' esta normalizada solo para comparar.
        rel = os.path.relpath(d['origen'].strip(), rutas.RAIZ)
        return '%s(%s,%s): %s %s: %s' % (rel, d['linea'], d['col'], d['nivel'],
                                         d['codigo'], d['mensaje'])
    return '%s: %s %s: %s' % (d['origen'].strip(), d['nivel'], d['codigo'], d['mensaje'])


# ============================================================
def main(argv=None):
    ap = argparse.ArgumentParser(
        description='Compila los C# de unity/ con el dotnet de Unity, sin abrir Unity.')
    ap.add_argument('--solo', nargs='+', metavar='RUTA', default=None,
                    help='sale con 1 solo si hay errores CS en estos archivos; '
                         'los demas errores se imprimen como AVISO')
    ap.add_argument('--avisos', action='store_true',
                    help='imprime tambien los warnings (por defecto solo se cuentan, '
                         'salvo los de los archivos de --solo)')
    ap.add_argument('--conservar', action='store_true',
                    help='no borra la carpeta temporal (para mirar el log o el obj/)')
    ap.add_argument('--dotnet', default=None, help='ruta a dotnet.exe (por defecto, el de Unity)')
    ap.add_argument('--verbose', action='store_true', help='log de MSBuild completo')
    args = ap.parse_args(argv)

    print('=' * 72)
    print('  COMPILAR C# DE UNITY SIN ABRIR UNITY')
    print('=' * 72)

    # --- los .csproj ---
    faltan = [c for _, c, _, _ in ENSAMBLADOS if not os.path.isfile(os.path.join(UNITY, c))]
    if faltan:
        print('  NO SE PUEDE COMPILAR: faltan %s en %s'
              % (' y '.join(faltan), os.path.relpath(UNITY, rutas.RAIZ)))
        print('  Los genera Unity y no estan en git (.gitignore: *.csproj). Para crearlos:')
        print('    abrir el proyecto en Unity una vez, o en Unity:')
        print('    Edit > Preferences > External Tools > Regenerate project files')
        return 2

    dotnet = buscar_dotnet(args.dotnet)
    if not dotnet:
        print('  NO SE PUEDE COMPILAR: no encontre dotnet.exe de Unity %s' % version_de_unity())
        print('  (se busca en C:\\Program Files\\Unity\\Hub\\Editor\\<version>\\Editor\\Data\\DotNetSdk;'
              ' o pasa --dotnet <ruta>)')
        return 2

    solo = None
    if args.solo:
        solo = resolver_solo(args.solo)
        if solo is None:
            print('\n  NO VERIFICADO: corrige las rutas de --solo (relativas a la raiz del repo,'
                  ' p. ej. unity\\Assets\\Scripts\\PanelUI.cs)')
            return 2

    carpeta = tempfile.mkdtemp(prefix='compilar_unity_')
    try:
        for _, nombre, incluir, excluir in ENSAMBLADOS:
            with io.open(os.path.join(UNITY, nombre), encoding='utf-8-sig') as f:
                texto = f.read()
            try:
                preparado = preparar_csproj(texto, UNITY, incluir, excluir)
            except ValueError as ex:
                print('\n  NO VERIFICADO: %s: %s' % (nombre, ex))
                return 2
            with io.open(os.path.join(carpeta, nombre), 'w', encoding='utf-8') as f:
                f.write(preparado)

        print('  dotnet     %s' % dotnet)
        print('  temporal   %s' % carpeta)
        try:
            codigo, lineas, segundos = compilar(dotnet, carpeta, args.verbose)
        except (subprocess.TimeoutExpired, OSError) as ex:
            # Sin esto Python sale con 1, que aca significa "hay errores
            # CS": un dotnet colgado pareceria un error de tipeo.
            print('\n  NO VERIFICADO: dotnet build no termino (%s)' % ex)
            return 2
        diags = leer_diagnosticos(lineas)
        compilados = {e: os.path.isfile(os.path.join(carpeta, 'Temp', 'bin', 'Debug', e + '.dll'))
                      for e, _, _, _ in ENSAMBLADOS}
        print('  dotnet build termino en %.1f s (codigo %d)' % (segundos, codigo))
        if args.verbose:
            print('\n'.join(lineas))
    finally:
        if args.conservar:
            print('  (se conserva %s)' % carpeta)
        else:
            shutil.rmtree(carpeta, ignore_errors=True)

    errores_cs = [d for d in diags if d['nivel'] == 'error' and d['codigo'].upper().startswith('CS')]
    errores_otros = [d for d in diags if d['nivel'] == 'error' and not d['codigo'].upper().startswith('CS')]
    avisos = [d for d in diags if d['nivel'] == 'warning']

    def es_mio(d):
        return solo is not None and d['archivo'] in solo

    # ------------------------------------------------------------
    print()
    if solo is not None:
        print('  --solo: %s' % ', '.join(args.solo))
    mios = [d for d in errores_cs if solo is None or es_mio(d)]
    ajenos = [d for d in errores_cs if solo is not None and not es_mio(d)]
    for d in mios:
        print('  ERROR  ' + _texto(d))
    for d in ajenos:
        print('  AVISO (error en archivo ajeno)  ' + _texto(d))
    for d in errores_otros:
        print('  ERROR DE HERRAMIENTA  ' + _texto(d))
    for d in avisos:
        if args.avisos or es_mio(d):
            print('  warning  ' + _texto(d))

    # ------------------------------------------------------------
    print()
    print('  %-24s %8s %8s   %s' % ('ensamblado', 'errores', 'avisos', 'estado'))
    for e, _, _, _ in ENSAMBLADOS:
        n_err = sum(1 for d in errores_cs if d['ensamblado'] == e)
        n_av = sum(1 for d in avisos if d['ensamblado'] == e)
        if compilados[e]:
            estado = 'compilado'
        elif e == 'Assembly-CSharp-Editor' and not compilados['Assembly-CSharp']:
            estado = 'NO COMPILADO (depende de Assembly-CSharp, que fallo)'
        else:
            estado = 'NO COMPILADO'
        print('  %-24s %8d %8d   %s' % (e, n_err, n_av, estado))
    if solo is not None:
        print('  en tus archivos: %d errores; en archivos ajenos: %d (AVISO)'
              % (len(mios), len(ajenos)))

    # ------------------------------------------------------------
    # El veredicto. Un error de herramienta sin errores CS significa que
    # no se compilo nada: no es un "OK".
    if solo is None:
        if errores_cs:
            print('\n  FALLA: %d errores CS' % len(errores_cs))
            return 1
        if errores_otros or not all(compilados.values()):
            print('\n  NO VERIFICADO: la herramienta fallo sin errores CS (ver arriba)')
            return 2
        print('\n  OK: los %d ensamblados compilan sin errores' % len(ENSAMBLADOS))
        return 0

    if mios:
        print('\n  FALLA: %d errores CS en tus archivos' % len(mios))
        return 1
    # Un ensamblado con errores ajenos igual se REVISO entero: Roslyn
    # reporta los errores de todos sus archivos, y en los tuyos no hubo.
    # Lo que no sirve es uno que ni se intento: el del editor cuando
    # Assembly-CSharp falla, o cualquiera si la herramienta se cayo.
    revisados = {e for e in compilados if compilados[e]} | {d['ensamblado'] for d in errores_cs}
    necesarios = {ensamblado_de_archivo(s) for s in solo}
    sin_revisar = sorted(necesarios - revisados)
    if sin_revisar:
        print('\n  NO VERIFICADO: %s no se llego a compilar; tus archivos no se revisaron'
              % ', '.join(sin_revisar))
        return 2
    print('\n  OK: tus archivos no tienen errores CS'
          + ('  (hay %d errores ajenos: AVISO)' % len(ajenos) if ajenos else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
