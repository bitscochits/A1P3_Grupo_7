# -*- coding: utf-8 -*-
r"""
================================================================
 comun/verificar_todo.py  -  TODA LA SUITE, DE UNA
================================================================
 Corre cada verificacion y cada test del repo y dice cual paso.

 Correr:
   python comun/verificar_todo.py            todo
   python comun/verificar_todo.py --rapido   sin los que tardan mas de un minuto
   python comun/verificar_todo.py --solo sismo combinar

 Es el comando para antes de un commit y para el dia de la
 demostracion. Si aca sale todo en OK, el repo esta como se entrega.

 Cada entrada es un script que ya existe y que se puede correr solo:
 este archivo no verifica nada por su cuenta, solo los llama en orden
 y resume. Asi la lista de abajo es tambien el indice de que se
 comprueba y donde.
================================================================
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
import time

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _AQUI)
import rutas                                 # noqa: E402

# (etiqueta, [argumentos], es lento)
SUITE = [
    # --- el modelo de cada edificio, contra si mismo y contra el plano
    ('planos LT2',            ['edificios/lt2/tests/test_planos.py'], False),
    ('modelo LT2',            ['edificios/lt2/verificar_lt2.py'], True),
    ('planos Ingenieria',     ['edificios/ingenieria/verificar_planos.py'], False),
    ('conjunto = cuerpos',    ['edificios/conjunto/verificar_conjunto.py'], False),
    # --- lo que cruza los edificios
    ('losa aplicada = dibujada', ['comun/verificar_tributarias.py'], False),
    ('sismo lt2',             ['comun/sismo.py', 'lt2'], False),
    ('sismo ingenieria',      ['comun/sismo.py', 'ingenieria'], False),
    ('sismo conjunto',        ['comun/sismo.py', 'conjunto'], False),
    ('superposicion lt2',     ['comun/combinar.py', 'lt2'], False),
    ('superposicion ingenieria', ['comun/combinar.py', 'ingenieria'], False),
    ('superposicion conjunto', ['comun/combinar.py', 'conjunto'], True),
    # --- el contrato con Unity y el servidor
    ('contrato Unity lt2',    ['comun/test_contrato_unity.py', 'lt2'], False),
    ('contrato Unity ingenieria', ['comun/test_contrato_unity.py', 'ingenieria'], False),
    ('contrato Unity conjunto', ['comun/test_contrato_unity.py', 'conjunto'], False),
    ('round-trip Ingenieria', ['edificios/ingenieria/tests/test_contrato_unity.py'], False),
    ('servidor',              ['test_servidor.py'], False),
    ('reanalisis',            ['edificios/lt2/tests/test_reanalisis.py'], False),
    # --- semana 3
    ('parametros',            ['semana03/parametros.py'], False),
    ('lab semana 3 ingenieria', ['semana03/lab_semana03.py'], False),
    ('lab semana 3 lt2',      ['semana03/lab_semana03.py', 'lt2'], False),
    ('capacidad ingenieria',  ['comun/capacidad.py', 'ingenieria', '18', '--pm'], False),
    ('capacidad lt2',         ['comun/capacidad.py', 'lt2', '1', '--pm'], False),
    ('RC a mano lt2',         ['semana03/verificar_rc.py', 'lt2'], True),
    ('demanda/capacidad lt2', ['semana03/demanda_capacidad.py', 'lt2', '--todas'], False),
    ('demanda/capacidad ingenieria',
                              ['semana03/demanda_capacidad.py', 'ingenieria', '--todas'], False),
    # Los exportadores de los anexos copian a StreamingAssets: van con
    # 'lt2', el edificio de la demo (decision 1 de la Semana 5). Sin
    # edificio exportaban ingenieria y la suite dejaba el visor con anexos
    # de otro edificio que superposicion.json (LT2).
    ('anexo Unity semana 3',  ['semana03/exportar_unity.py', 'lt2'], False),
    # El nodo va explicito: es el caso que cita reports/semana03.md, y
    # sin argumento el script toma el primero del edificio, que puede
    # cambiar si el modelo se rearma.
    ('viga partida no es rotula',
     ['semana03/verificar_viga_partida.py', 'ingenieria', '373'], False),
    # --- semana 4: el anexo del visor, sus esfuerzos contra OpenSees,
    # su contrato con el C# y lo que Unity lee de verdad. El ultimo abre
    # el editor en batch: es lento y sale con 2 si Unity ya esta abierto.
    ('anexo Unity semana 4',  ['semana04/exportar_unity.py', 'lt2'], False),
    ('esfuerzos y signos s4', ['semana04/verificar_semana04.py'], False),
    ('esfuerzos s4 lt2',      ['semana04/verificar_semana04.py', 'lt2'], False),
    ('esfuerzos s4 conjunto', ['semana04/verificar_semana04.py', 'conjunto'], False),
    ('contrato JSON-C# s4',   ['semana04/test_contrato_semana04.py'], False),
    ('trazabilidad s4',       ['semana04/trazabilidad.py', 'ingenieria', '18'], False),
    ('JsonUtility real s4',   ['semana04/verificar_unity_semana04.py'], True),
    # --- semana 5: superposicion con lambdas, servidor, Excel, carga movil
    # y las modificaciones M1/M2. Ninguno escribe en data/ ni en
    # StreamingAssets (verificar_superposicion deja su evidencia en
    # semana05/evidencia/; los demas escriben en temporales o en results/).
    ('superposicion s5 lt2',  ['semana05/verificar_superposicion.py', 'lt2'], False),
    ('superposicion s5 ingenieria',
                              ['semana05/verificar_superposicion.py', 'ingenieria'], False),
    ('contrato JSON-C# s5',   ['semana05/test_contrato_semana05.py'], False),
    ('excel s5',              ['semana05/test_excel.py', 'lt2', 'ingenieria', 'conjunto'], True),
    ('carga movil s5',        ['semana05/carga_movil.py', 'lt2', '--no-escribir'], False),
    ('M1 borrar columna 69',  ['semana05/reanalisis_demo.py', 'lt2', '--borrar-elemento', '69',
                               '--nodo', '186', '--elemento', '337'], False),
    ('M2 cs 0.20',            ['semana05/comparar_anexos.py', 'lt2', '--cs', '0.20'], False),
    # LAB de la semana 5: los sliders que Unity combina al instante dan
    # lo mismo que Python (10 juegos de lambda, incluidos negativos).
    ('sliders instantaneos',  ['semana05_lab/verificar_instantanea.py', 'lt2',
                               '--registro', 'semana05/capturas/registro.txt'], False),
    # Las otras dos modificaciones de la lista del LAB, que la pestana
    # Modificar ya permite: cambiar una seccion y soltar un apoyo. Las
    # dos cambian K, asi que el equilibrio tiene que seguir cerrando.
    ('M3 seccion de una viga', ['semana05/reanalisis_demo.py', 'lt2',
                                '--seccion', '337', 'V 0.30x0.80', '--nodo', '186'], False),
    ('M4 soltar un apoyo',    ['semana05/reanalisis_demo.py', 'lt2',
                               '--apoyo', '2', '1', '1', '1', '0', '0', '0',
                               '--nodo', '186'], False),
]


def correr(args):
    t0 = time.time()
    # El hijo escribe a un pipe, y en Windows un pipe sale con la pagina de
    # codigos del sistema (cp1252), no con UTF-8: un 'φ' en un print tumbaba
    # test_excel.py con UnicodeEncodeError y la entrada salia FALLA fuera de
    # una terminal que ya tuviera PYTHONIOENCODING. Se lee como UTF-8 abajo,
    # asi que el hijo tiene que escribir UTF-8 (igual que comparar_unity.py).
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    r = subprocess.run([sys.executable] + [os.path.join(rutas.RAIZ, args[0])]
                       + args[1:], cwd=rutas.RAIZ, capture_output=True,
                       text=True, encoding='utf-8', errors='replace', env=env)
    return r.returncode == 0, time.time() - t0, (r.stdout + r.stderr)


def _avisar_anexos():
    """Que edificio quedo en los anexos del visor.

    La suite corre los exportadores de los anexos con 'lt2' (el edificio
    de la demo) y copian a StreamingAssets: si alguien estaba mirando
    otro edificio en Unity, se los acaba de pisar y el visor apagaria los
    diagramas. Mejor decirlo que dejarlo en silencio.
    """
    import json
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sa = os.path.join(raiz, 'unity', 'Assets', 'StreamingAssets')
    for nombre in ('semana03.json', 'semana04.json'):
        try:
            with io.open(os.path.join(sa, nombre), encoding='utf-8') as fh:
                ed = (json.load(fh).get('info') or {}).get('edificio')
        except Exception:
            continue
        if ed:
            print("  (la suite dejo %s en '%s'; si mirabas otro edificio, "
                  "vuelve a exportarlo)" % (nombre, ed))


def main(argv):
    rapido = '--rapido' in argv
    solo = None
    if '--solo' in argv:
        solo = [a.lower() for a in argv[argv.index('--solo') + 1:]
                if not a.startswith('--')]

    print('=' * 70)
    print('  SUITE COMPLETA   (%s)' % rutas.RAIZ)
    print('=' * 70)
    fallaron, n = [], 0
    for etiqueta, args, lento in SUITE:
        if rapido and lento:
            continue
        if solo and not any(s in (etiqueta + ' ' + args[0]).lower() for s in solo):
            continue
        n += 1
        ok, dt, salida = correr(args)
        print('  %-30s %-4s %5.1fs   %s'
              % (etiqueta, 'OK' if ok else 'FALLA', dt, ' '.join(args)))
        if not ok:
            fallaron.append((etiqueta, args, salida))

    print('=' * 70)
    # Despues de correr, no antes: es lo que la suite DEJO.
    _avisar_anexos()
    if fallaron:
        print('  FALLARON %d de %d' % (len(fallaron), n))
        for etiqueta, args, salida in fallaron:
            print()
            print('--- %s   (%s)' % (etiqueta, ' '.join(args)))
            print('\n'.join('    ' + l for l in salida.strip().splitlines()[-12:]))
        return 1
    print('  %d de %d EN OK' % (n, n))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
