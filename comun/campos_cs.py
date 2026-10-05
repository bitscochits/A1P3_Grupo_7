# -*- coding: utf-8 -*-
r"""
================================================================
 comun/campos_cs.py  -  LOS CAMPOS PUBLICOS DE LAS CLASES DE UN .cs
================================================================
 JsonUtility de Unity ignora SIN AVISAR una clave del JSON que no tiene
 campo en la clase C# (CLAUDE.md, seccion 6). Para comprobarlo hay que
 saber que campos tiene cada clase: esta es la unica definicion de esa
 lectura. La usan comun/test_contrato_unity.py (el modelo) y
 edificios/conjunto/topografia.py (el relieve del sitio).

     clases = campos_de_clases('unity/Assets/Scripts/ModeloEstructural.cs')
     clases['Nodo']   ->  {'id', 'x', 'y', 'z', ...}
================================================================
"""
from __future__ import annotations

import re


def campos_de_clases(ruta):
    """{nombre de clase: set de campos publicos} de un archivo .cs."""
    with open(ruta, encoding='utf-8') as f:
        src = f.read()

    # Fuera comentarios, para no confundir ejemplos de las notas con
    # codigo real.
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    src = re.sub(r'//[^\n]*', '', src)

    clases = {}
    for m in re.finditer(r'class\s+(\w+)\s*\{', src):
        nombre = m.group(1)
        # Recorta hasta cerrar la llave de la clase.
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
        cuerpo = src[i:j]

        campos = set()
        # public <tipo> a, b, c;   (ignora propiedades con { get; })
        for d in re.finditer(
                r'public\s+[\w<>\[\]\.]+\s+([\w\s,]+?)\s*(?:=[^;]*)?;', cuerpo):
            grupo = d.group(1)
            if '(' in grupo:
                continue
            for nom in grupo.split(','):
                nom = nom.strip()
                if nom and re.fullmatch(r'\w+', nom):
                    campos.add(nom)
        clases[nombre] = campos
    return clases
