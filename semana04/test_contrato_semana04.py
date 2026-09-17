# -*- coding: utf-8 -*-
r"""
================================================================
 semana04/test_contrato_semana04.py  -  EL JSON DE SEMANA 4 CONTRA EL C#
================================================================
 Compara las claves de data/unity/semana04.json con los campos
 publicos de las clases [System.Serializable] que las leen en Unity
 (VisorSemana04.cs y DespNodo de ModeloEstructural.cs).

 Correr:
   python semana04/test_contrato_semana04.py
   python semana04/test_contrato_semana04.py ruta/a/otro_anexo.json

 ----------------------------------------------------------------
 POR QUE EN LAS DOS DIRECCIONES
 ----------------------------------------------------------------
 JsonUtility no avisa nada:

   clave del JSON sin campo C#   se descarta. Inofensivo para el
                                 visor, pero es un dato que Python
                                 calculo y nadie muestra: casi siempre
                                 un nombre mal escrito.
   campo C# sin clave del JSON   se queda en 0, "" o null. El panel
                                 muestra Mn = 0 o una deformada plana
                                 y nadie sospecha. ESTE es el fallo
                                 silencioso, y por eso (b) mira TODOS
                                 los objetos, no solo el primero: una
                                 clave que falta en uno solo ya deja un
                                 elemento con su valor por defecto.

 Ademas lo que JsonUtility tampoco sabe leer y tampoco avisa: arreglos
 de arreglos (los deja vacios), null, un numero en un campo string, un
 decimal en un campo int. Y los largos que el visor da por supuestos
 al dibujar: f de 12, estaciones del mismo largo, curvas P-M parejas.

 Lo que Unity de verdad leyo lo comprueba verificar_unity_semana04.py,
 corriendo el editor. Este test no necesita Unity.
================================================================
"""
from __future__ import annotations

import filecmp
import json
import os
import re
import sys

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_AQUI), 'comun'))
import rutas                                 # noqa: E402

JSON = os.path.join(rutas.UNITY, 'semana04.json')
STREAMING = os.path.join(rutas.STREAMING, 'semana04.json')
SCRIPTS = os.path.join(rutas.UNITY_PROYECTO, 'Assets', 'Scripts')
CS_VISOR = os.path.join(SCRIPTS, 'VisorSemana04.cs')
CS_MODELO = os.path.join(SCRIPTS, 'ModeloEstructural.cs')

# Los largos que el contrato fija (exportar_unity.py): f es localForce
# en i y en j, factores son (lG, lQ, lEX, lEY), vecxz un vector y cada
# restriccion los 6 GDL del nodo.
LARGO_F = 12
LARGO_FACTORES = 4
LARGO_VECXZ = 3
LARGO_RESTR = 6
ESTACIONES = ('x', 'N', 'Vy', 'Vz', 'T', 'My', 'Mz')
CURVA = ('P', 'Mn', 'Mmax', 'de')

# int de C# es de 32 bits y float de 32: un valor fuera de rango no da
# error en JsonUtility, da basura.
INT32 = (-2 ** 31, 2 ** 31 - 1)
FLOAT32_MAX = 3.4028234663852886e38

fallos = []


def check(cond, msg, detalle=''):
    print('  [%s] %s' % ('OK  ' if cond else 'FALLA', msg))
    if detalle:
        print('         %s' % detalle)
    if not cond:
        fallos.append(msg)
    return cond


# ============================================================
# EL C#: CAMPOS PUBLICOS Y SU TIPO
# ============================================================
def campos_de_clases(ruta):
    r"""
    {clase: {campo: tipo}} de un .cs. Es comun/test_contrato_unity.py
    campos_de_clases, copiada aca y no importada porque ese modulo corre
    todos sus checks al importarse. Mismo recorte de comentarios, misma
    llave de cierre por profundidad y misma expresion para
    'public <tipo> a, b;' (las propiedades con get quedan fuera). Lo
    unico agregado: guarda el tipo, para el chequeo [4].
    """
    with open(ruta, encoding='utf-8') as f:
        src = f.read()
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    src = re.sub(r'//[^\n]*', '', src)

    clases = {}
    for m in re.finditer(r'class\s+(\w+)\s*\{', src):
        i = m.end() - 1
        prof, j = 0, i
        while j < len(src):
            if src[j] == '{':
                prof += 1
            elif src[j] == '}':
                prof -= 1
                if prof == 0:
                    break
            j += 1
        campos = {}
        for d in re.finditer(
                r'public\s+([\w<>\[\]\.]+)\s+([\w\s,]+?)\s*(?:=[^;]*)?;', src[i:j]):
            if '(' in d.group(2):
                continue
            for nom in d.group(2).split(','):
                nom = nom.strip()
                if nom and re.fullmatch(r'\w+', nom):
                    campos[nom] = d.group(1)
        clases[m.group(1)] = campos
    return clases


# ============================================================
# EL JSON: TODOS LOS OBJETOS DE CADA CLASE
# ============================================================
def objetos_por_clase(anexo):
    """
    {clase C#: [objetos del JSON que JsonUtility vuelca en ella]}. Es el
    mapa de AnexoSemana04: raiz -> info, casos[] -> desplazamientos[],
    esfuerzos[], demandas[]; elementos[]; familias[].
    """
    casos = anexo.get('casos') or []
    return {
        'AnexoSemana04': [anexo],
        'InfoSemana04': [anexo.get('info') or {}],
        'CasoS4': casos,
        'DespNodo': [d for c in casos for d in c.get('desplazamientos') or []],
        'EsfuerzosS4': [e for c in casos for e in c.get('esfuerzos') or []],
        'DemandaS4': [d for c in casos for d in c.get('demandas') or []],
        'ElementoS4': anexo.get('elementos') or [],
        'FamiliaPM': anexo.get('familias') or [],
    }


def tipo_calza(tipo, valor, clases):
    """
    None si JsonUtility puede volcar 'valor' en un campo C# de 'tipo';
    si no, el motivo. Los tipos son los que usa el contrato: int, float,
    string, bool, T[] y List<T>, y las clases del propio contrato.
    """
    if valor is None:
        return 'null (JsonUtility lo deja en su valor por defecto)'
    m = re.fullmatch(r'List<(\w+)>', tipo) or re.fullmatch(r'(\w+)\[\]', tipo)
    if m:
        if not isinstance(valor, list):
            return 'se esperaba un arreglo'
        for v in valor:
            motivo = tipo_calza(m.group(1), v, clases)
            if motivo:
                return 'elemento del arreglo: ' + motivo
        return None
    if tipo in ('int', 'long'):
        if isinstance(valor, bool) or not isinstance(valor, int):
            return 'se esperaba un entero, vino %r' % (valor,)
        if tipo == 'int' and not INT32[0] <= valor <= INT32[1]:
            return 'fuera del rango de int32: %d' % valor
        return None
    if tipo in ('float', 'double'):
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            return 'se esperaba un numero, vino %r' % (valor,)
        if tipo == 'float' and abs(valor) > FLOAT32_MAX:
            return 'fuera del rango de float32: %r' % valor
        return None
    if tipo == 'string':
        return None if isinstance(valor, str) else 'se esperaba texto, vino %r' % (valor,)
    if tipo == 'bool':
        return None if isinstance(valor, bool) else 'se esperaba bool, vino %r' % (valor,)
    if tipo in clases:
        return None if isinstance(valor, dict) else 'se esperaba un objeto %s' % tipo
    return 'tipo C# %s no previsto por este test' % tipo


def arreglos_anidados(valor, ruta='$', salida=None, tope=5):
    """Rutas donde hay un arreglo dentro de otro: JsonUtility no los lee."""
    salida = [] if salida is None else salida
    if len(salida) >= tope:
        return salida
    if isinstance(valor, dict):
        for k, v in valor.items():
            arreglos_anidados(v, '%s.%s' % (ruta, k), salida, tope)
    elif isinstance(valor, list):
        for i, v in enumerate(valor):
            if isinstance(v, list):
                salida.append('%s[%d]' % (ruta, i))
            else:
                arreglos_anidados(v, '%s[%d]' % (ruta, i), salida, tope)
    return salida


def _lista(nombres, tope=8):
    nombres = sorted(nombres)
    return ', '.join(nombres[:tope]) + (' ...' if len(nombres) > tope else '')


# ============================================================
def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ruta_json = os.path.abspath(argv[0]) if argv else JSON

    print('=' * 72)
    print('  CONTRATO JSON <-> C# DE SEMANA 4')
    print('=' * 72)
    for ruta, que in ((ruta_json, 'corre: python semana04/exportar_unity.py'),
                      (CS_VISOR, 'lo escribe el visor de la Semana 4'),
                      (CS_MODELO, 'es el contrato base del visor')):
        if not os.path.isfile(ruta):
            print('  no existe %s (%s)' % (os.path.relpath(ruta, rutas.RAIZ), que))
            return 1
    with open(ruta_json, encoding='utf-8') as f:
        anexo = json.load(f)
    print('  json    %s  (%.2f MB)' % (os.path.relpath(ruta_json, rutas.RAIZ),
                                      os.path.getsize(ruta_json) / 1048576.0))

    # DespNodo es del modelo base; el resto, del visor. Si el visor
    # redefiniera una clase del modelo, la suya es la que compila junto
    # a la otra... o no compila: se avisa.
    del_modelo = campos_de_clases(CS_MODELO)
    del_visor = campos_de_clases(CS_VISOR)
    repetidas = set(del_modelo) & set(del_visor)
    clases = dict(del_modelo)
    clases.update(del_visor)
    print('  c#      %s (%d clases) + %s (%d clases)'
          % (os.path.basename(CS_VISOR), len(del_visor),
             os.path.basename(CS_MODELO), len(del_modelo)))
    check(not repetidas, 'ninguna clase del visor repite nombre con el modelo base',
          'repetidas: %s' % _lista(repetidas) if repetidas else '')

    # El visor tiene que deserializar la RAIZ con AnexoSemana04: si lee
    # con otra clase, este test compararia contra algo que nadie usa.
    with open(CS_VISOR, encoding='utf-8') as f:
        fuente_visor = f.read()
    check('FromJson<AnexoSemana04>' in fuente_visor,
          'VisorSemana04.cs lee el archivo con JsonUtility.FromJson<AnexoSemana04>')

    objetos = objetos_por_clase(anexo)

    # ------------------------------------------------------------
    print()
    print('[1] (a) toda clave del JSON tiene campo C#   (b) todo campo C# tiene clave')
    print('    (b) se exige en CADA objeto: basta uno sin la clave para un valor por defecto')
    # ------------------------------------------------------------
    for clase, lista in objetos.items():
        if not check(clase in clases, '%s existe en el C#' % clase):
            continue
        if not check(bool(lista), '%s: el JSON trae objetos para compararla' % clase):
            continue
        campos = set(clases[clase])
        union = set().union(*(set(o) for o in lista))
        interseccion = set(lista[0]).intersection(*(set(o) for o in lista[1:]))
        sobran = union - campos
        faltan = campos - interseccion
        print('    %-14s %7d objetos, %2d claves, %2d campos publicos'
              % (clase, len(lista), len(union), len(campos)))
        check(not sobran, '%s (a): las %d claves del JSON tienen campo'
              % (clase, len(union)),
              'sin campo C#: %s' % _lista(sobran) if sobran else '')
        detalle = ''
        if faltan:
            ausentes = {c: sum(1 for o in lista if c not in o) for c in faltan}
            detalle = 'sin clave en el JSON: %s' % ', '.join(
                '%s (falta en %d de %d)' % (c, n, len(lista))
                for c, n in sorted(ausentes.items()))
        check(not faltan, '%s (b): los %d campos C# tienen clave en todos los objetos'
              % (clase, len(campos)), detalle)

    # ------------------------------------------------------------
    print()
    print('[2] cada valor cabe en el tipo de su campo C#')
    print('    (un decimal en un int, texto en un float o null no dan error: dan 0)')
    # ------------------------------------------------------------
    for clase, lista in objetos.items():
        if clase not in clases or not lista:
            continue
        malos, revisados = {}, 0
        for o in lista:
            for campo, tipo in clases[clase].items():
                if campo not in o:
                    continue
                revisados += 1
                motivo = tipo_calza(tipo, o[campo], clases)
                if motivo and campo not in malos:
                    malos[campo] = '%s %s: %s (id %s)' % (tipo, campo, motivo, o.get('id', '-'))
        check(not malos, '%s: %d valores revisados contra su tipo' % (clase, revisados),
              '; '.join(malos[c] for c in sorted(malos)) if malos else '')

    # ------------------------------------------------------------
    print()
    print('[3] nada que JsonUtility no sepa leer')
    # ------------------------------------------------------------
    anidados = arreglos_anidados(anexo)
    check(not anidados, 'ningun arreglo dentro de otro arreglo',
          'primeros: %s' % ', '.join(anidados) if anidados else '')

    # ------------------------------------------------------------
    print()
    print('[4] los largos que el visor da por supuestos al dibujar')
    # ------------------------------------------------------------
    esf = objetos['EsfuerzosS4']
    malos = [e.get('id') for e in esf if len(e.get('f') or []) != LARGO_F]
    check(not malos, 'f tiene %d valores en los %d esfuerzos (localForce en i y j)'
          % (LARGO_F, len(esf)), 'ids: %s' % malos[:8] if malos else '')

    malos = [e.get('id') for e in esf
             if len({len(e.get(k) or []) for k in ESTACIONES}) != 1]
    largos = sorted({len(e.get('x') or []) for e in esf})
    check(not malos, '%s del mismo largo en cada esfuerzo (largos presentes: %s)'
          % (', '.join(ESTACIONES), largos), 'ids: %s' % malos[:8] if malos else '')

    n_carg = (anexo.get('info') or {}).get('n_estaciones_cargada')
    raros = [n for n in largos if n not in (2, n_carg)]
    check(not raros, 'las estaciones son 2 (barra sin carga) o n_estaciones_cargada = %s'
          % n_carg, 'largos inesperados: %s' % raros if raros else '')

    fams = objetos['FamiliaPM']
    malos = [f.get('indice') for f in fams if len({len(f.get(k) or []) for k in CURVA}) != 1]
    check(not malos, '%s del mismo largo en las %d familias P-M'
          % (', '.join(CURVA), len(fams)), 'indices: %s' % malos if malos else '')
    vacias = [f.get('indice') for f in fams if len(f.get('P') or []) < 3]
    check(not vacias, 'toda curva P-M tiene al menos 3 puntos',
          'indices: %s' % vacias if vacias else '')

    casos = objetos['CasoS4']
    malos = [c.get('nombre') for c in casos if len(c.get('factores') or []) != LARGO_FACTORES]
    check(not malos, 'factores tiene %d valores (lG lQ lEX lEY) en los %d casos'
          % (LARGO_FACTORES, len(casos)), 'casos: %s' % malos if malos else '')

    elems = objetos['ElementoS4']
    malos = [e.get('id') for e in elems
             if len(e.get('vecxz') or []) != LARGO_VECXZ
             or len(e.get('restr_n1') or []) != LARGO_RESTR
             or len(e.get('restr_n2') or []) != LARGO_RESTR]
    check(not malos, 'vecxz de %d y restr_n1/restr_n2 de %d en los %d elementos'
          % (LARGO_VECXZ, LARGO_RESTR, len(elems)), 'ids: %s' % malos[:8] if malos else '')

    # ------------------------------------------------------------
    print()
    print('[5] las referencias entre bloques apuntan a algo que existe')
    # ------------------------------------------------------------
    info = anexo.get('info') or {}
    ids = {e.get('id') for e in elems}
    nombres = [c.get('nombre') for c in casos]
    check(len(ids) == len(elems), 'los id de elemento son unicos (%d)' % len(elems))
    check(len(set(nombres)) == len(nombres), 'los nombres de caso son unicos: %s'
          % ', '.join(map(str, nombres)))
    check(info.get('caso_por_defecto') in nombres,
          'caso_por_defecto = %s esta entre los casos' % info.get('caso_por_defecto'))
    for clave in ('columna_demo', 'muro_demo'):
        check(info.get(clave) in ids, '%s = %s es un elemento del anexo'
              % (clave, info.get(clave)))
    indices = [f.get('indice') for f in fams]
    check(indices == list(range(len(fams))),
          'familias[i].indice == i (el visor indexa la lista con familia)')
    fuera = sorted({e.get('familia') for e in elems} - set(indices) - {-1})
    fuera += sorted({d.get('familia') for d in objetos['DemandaS4']} - set(indices))
    check(not fuera, 'toda familia citada por un elemento o una demanda existe (o es -1)',
          'fuera de rango: %s' % fuera[:8] if fuera else '')
    ajenos = [c.get('nombre') for c in casos
              if {e.get('id') for e in c.get('esfuerzos') or []} != ids]
    check(not ajenos, 'cada caso trae esfuerzos para exactamente los %d elementos' % len(ids),
          'casos: %s' % ajenos if ajenos else '')

    # ------------------------------------------------------------
    print()
    print('[6] Unity lee la copia de StreamingAssets, no data/unity/')
    # ------------------------------------------------------------
    if argv:
        print('  [--  ] se paso un json a mano: no se compara con StreamingAssets')
    elif not os.path.isfile(STREAMING):
        check(False, 'existe %s' % os.path.relpath(STREAMING, rutas.RAIZ))
    else:
        check(filecmp.cmp(JSON, STREAMING, shallow=False),
              '%s es identico byte a byte a %s'
              % (os.path.relpath(STREAMING, rutas.RAIZ), os.path.relpath(JSON, rutas.RAIZ)))

    # ------------------------------------------------------------
    print()
    print('[7] la escala grafica de la deformada (info.escala_deformada)')
    print('    El visor la usa de valor por defecto: si viene en 0 se queda con la de la')
    print('    escena (x300, que sirve en el LT2 y deja al conjunto como una carpa), y si')
    print('    no calza con el criterio la deformada sale de otro tamano que el declarado.')
    # ------------------------------------------------------------
    # El criterio y sus numeros los pone el exportador: aca no se
    # reimplementan (una sola definicion de cada cosa). Se importa
    # dentro de main porque arrastra OpenSees.
    sys.path.insert(0, _AQUI)
    import exportar_unity as eu              # noqa: E402
    import contrato                          # noqa: E402

    esc = info.get('escala_deformada')
    numero = isinstance(esc, (int, float)) and not isinstance(esc, bool)
    check(numero and esc > 0, 'escala_deformada = %s, mayor que 0' % esc)
    check(isinstance(info.get('_escala_deformada_por_que'), str)
          and len(info.get('_escala_deformada_por_que') or '') > 0,
          'el criterio viaja al lado, en _escala_deformada_por_que',
          (info.get('_escala_deformada_por_que') or '')[:150] + ' ...')
    if numero and esc > 0:
        ref = eu.escala_deformada(contrato.cargar_modelo(info.get('edificio')), casos)
        check(esc == ref['escala'],
              'es la que calcula exportar_unity.escala_deformada para %s: x%g'
              % (info.get('edificio'), ref['escala']),
              'el anexo trae x%s' % esc if esc != ref['escala'] else '')
        # El objetivo declarado, con la tolerancia MEDIDA contra el
        # redondeo: la escala se redondea a 2 cifras (paso), asi que el
        # largo dibujado puede caer hasta medio paso de desplazamiento
        # a cada lado del objetivo.
        mayor_m = max([c.get('max_desplazamiento_mm') or 0.0 for c in casos]) / 1000.0
        dibujado = esc * mayor_m
        tol = ref['paso'] * mayor_m / 2.0 + 1e-9
        check(abs(dibujado - ref['objetivo_m']) <= tol,
              'escala x%g * %.4f mm = %.3f m = el objetivo declarado %.3f m '
              '(+-%.4f m del redondeo a x%g)'
              % (esc, mayor_m * 1000.0, dibujado, ref['objetivo_m'], tol, ref['paso']),
              'el mayor desplazamiento es del caso %s' % ref['caso'])

    print()
    print('=' * 72)
    if fallos:
        print('  FALLARON %d:' % len(fallos))
        for f in fallos:
            print('    - %s' % f)
        return 1
    print('  EL CONTRATO JSON <-> C# DE SEMANA 4 ESTA SANO')
    print('=' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())
