# -*- coding: utf-8 -*-
r"""
================================================================
 semana05/exportar_excel.py  -  EL LIBRO DE RESULTADOS DE UN EDIFICIO
================================================================
 Escribe data/excel/<ed>_resultados.xlsx: los resultados del
 laboratorio (casos G, Q, EX, EY y las combinaciones de
 semana03/parametros.json) en un Excel que se abre con doble clic.

 Correr (desde la raiz del repo):

   .venv\Scripts\python.exe semana05\exportar_excel.py lt2
   .venv\Scripts\python.exe semana05\exportar_excel.py lt2 ingenieria conjunto
   .venv\Scripts\python.exe semana05\exportar_excel.py lt2 --cs 0.20
   .venv\Scripts\python.exe semana05\exportar_excel.py lt2 --salida C:\temp

 Los parametros (--cs, --q, --fq, --patron, --k, --comb, --uso,
 --combinacion) son los de semana03/parametros.py y van al anexo tal
 cual. Otras opciones de este script:

   --salida <carpeta>   escribe <carpeta>\<ed>_resultados.xlsx en vez
                        de data\excel\ (para probar sin tocar git)
   --ver-avisos         deja pasar los avisos de OpenSees de la busqueda
                        de curvas P-M (por defecto se desvian y se cuentan)

 Comprobar despues:

   .venv\Scripts\python.exe semana05\test_excel.py lt2

 ----------------------------------------------------------------
 DE DONDE SALEN LOS NUMEROS
 ----------------------------------------------------------------
 De semana04/exportar_unity.construir_anexo(ed, argv): los mismos que
 muestra el visor de Unity cuando el anexo se exporto con los mismos
 parametros. NO de data/unity/semana04.json, que guarda solo el ultimo
 edificio exportado. El libro lo arma comun/excel.py (escribir_libro_anexo,
 la firma de semana05/CONTRATO.md seccion c); este archivo es solo la
 linea de comandos.

 data/excel/ va a git y el libro es DETERMINISTA (mismos datos, mismos
 bytes): regenerarlo sin cambios no deja diff. Si se exporta con
 parametros que no son los de parametros.json, el libro versionado deja
 de ser el de la entrega: el script lo avisa.

 El lanzador copia el del edificio activo a
 unity/Assets/StreamingAssets/resultados.xlsx (comun/lanzar_unity.py
 sincronizar <ed>): este script no escribe en StreamingAssets.
================================================================
"""
from __future__ import annotations

import contextlib
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                'comun'))
import rutas                                 # noqa: E402

rutas.entrar(__file__)
import excel                                 # noqa: E402

# Las opciones de ESTE script; todo lo demas va a parametros.cargar
# (que ignora lo que no conoce).
OPCIONES_CON_VALOR = ('--salida',)
OPCIONES_SOLAS = ('--ver-avisos',)


@contextlib.contextmanager
def desviar_stderr(activo):
    r"""
    Manda el descriptor 2 (el que usa OpenSees desde C++) a un archivo
    temporal y devuelve la lista donde quedan sus lineas al salir. La
    busqueda de curvas P-M escribe cientos de "failed to converge" que
    no cambian el resultado (la curva se arma con los puntos que
    convergen) y taparian el resumen. Mismo patron que
    semana05/comparar_anexos.py.
    """
    lineas = []
    if not activo:
        yield lineas
        return
    sys.stderr.flush()
    guardado = os.dup(2)
    fallo = False
    with tempfile.TemporaryFile(mode='w+b') as tmp:
        os.dup2(tmp.fileno(), 2)
        try:
            yield lineas
        except BaseException:
            fallo = True
            raise
        finally:
            sys.stderr.flush()
            os.dup2(guardado, 2)
            os.close(guardado)
            tmp.seek(0)
            lineas.extend(tmp.read().decode('utf-8', 'replace').splitlines())
            # Si algo fallo, lo ultimo que dijo OpenSees puede ser la causa:
            # desviado y descartado, el error quedaria sin explicacion.
            if fallo and lineas:
                sys.stderr.write('  (ultimas lineas desviadas de stderr)\n    %s\n'
                                 % '\n    '.join(lineas[-30:]))
                sys.stderr.flush()


def separar_argumentos(argv):
    r"""
    (edificios, parametros, opciones). Los edificios son las palabras
    del principio que no empiezan con '-'; desde la primera bandera todo
    es de parametros.py, salvo las opciones de este script. Asi un
    '--comb 1.2 1.0 1.4 0' no se confunde con un edificio.
    """
    argv = list(argv)
    edificios = []
    while argv and not argv[0].startswith('-'):
        edificios.append(argv.pop(0))
    parametros, opciones = [], {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in OPCIONES_CON_VALOR:
            if i + 1 >= len(argv):
                raise SystemExit('%s necesita un valor' % a)
            opciones[a] = argv[i + 1]
            i += 2
            continue
        if a in OPCIONES_SOLAS:
            opciones[a] = True
        else:
            parametros.append(a)
        i += 1
    return edificios, parametros, opciones


def resumen_del_libro(ruta):
    r"""Lo que conviene ver en la terminal: filas por hoja y, por caso,
    los numeros de la hoja Resumen (releidos del archivo escrito)."""
    libro = excel.leer(ruta)
    print('  hojas: %s' % ', '.join('%s (%d)' % (h, len(f) - 1) for h, f in libro.items()))
    filas = libro['Resumen']
    enc = filas[0]

    def col(titulo):
        return enc.index(titulo)

    print('  %-16s %11s %11s %9s %11s %11s %8s %9s'
          % ('caso', 'error Fx', 'error Fz', '|u| mm', 'Vx kN', 'Vy kN', 'NO PASA', 'peor D/C'))
    for f in filas[1:]:
        peor = f[col('Peor D/C [-]')]
        print('  %-16s %11.2e %11.2e %9.3f %11.2f %11.2f %8d %9s'
              % (f[col('Caso')], f[col('Error Fx [kN]')], f[col('Error Fz [kN]')],
                 f[col('|u| máx [mm]')], f[col('Corte basal Vx [kN]')],
                 f[col('Corte basal Vy [kN]')], f[col('NO PASA')],
                 '-' if peor is None else '%.3f' % peor))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    edificios, parametros, opciones = separar_argumentos(argv)
    if not edificios or any(e not in excel.EDIFICIOS for e in edificios):
        print(__doc__)
        malos = [e for e in edificios if e not in excel.EDIFICIOS]
        raise SystemExit('edificio %s: use %s' % (', '.join(malos) or '(ninguno)',
                                                  ', '.join(excel.EDIFICIOS)))
    salida = opciones.get('--salida')
    callar = not opciones.get('--ver-avisos', False)

    fallos = 0
    for ed in edificios:
        ruta = (os.path.join(os.path.abspath(salida), '%s_resultados.xlsx' % ed) if salida
                else rutas.excel_resultados(ed))
        print('=' * 78)
        print('  EXCEL DE RESULTADOS  %s   %s' % (ed.upper(), ' '.join(parametros)))
        print('=' * 78)
        t0 = time.time()
        try:
            with desviar_stderr(callar) as ruido:
                escrita = excel.escribir_libro_anexo(ed, ruta, parametros)
        except PermissionError as e:
            # El mensaje ya dice que hay que cerrar Excel; sin traceback.
            print('  ERROR: %s' % e)
            fallos += 1
            continue
        segundos = time.time() - t0
        print('  escrito    %s' % escrita)
        print('  pesa       %.2f MB, en %.1f s' % (os.path.getsize(escrita) / 1e6, segundos))
        if callar and ruido:
            print('  avisos de OpenSees desviados: %d lineas (busqueda de curvas P-M); '
                  '--ver-avisos los muestra' % len(ruido))
        resumen_del_libro(escrita)
        if parametros and not salida:
            print('  AVISO: data/excel/ va a git y este libro NO usa los parametros de '
                  'semana03/parametros.json (%s). Para volver al de la entrega: %s %s'
                  % (' '.join(parametros), excel.COMANDO_CLI, ed))
        print('  comprobar: .venv\\Scripts\\python.exe semana05\\test_excel.py %s' % ed)
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(main())
