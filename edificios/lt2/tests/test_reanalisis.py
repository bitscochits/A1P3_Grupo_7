# -*- coding: utf-8 -*-
r"""
Verifica que REANALIZAR el modelo desde el JSON reproduzca el MISMO
resultado que calculo Python.

POR QUE EXISTE
Cuando se modifica el modelo desde Unity (mover un nodo, cambiar una
seccion, borrar una barra) el reanalisis lo hace el servidor Flask, que
reconstruye el modelo A PARTIR DEL JSON. Si el JSON no describe
exactamente el mismo problema que resolvio modelo_lt2.py, el
servidor devuelve numeros distintos a los del informe y NADIE SE ENTERA:
no hay error, solo resultados un poco distintos.

Dos formas reales en que eso paso en este proyecto:

1. El caso G exportado traia solo la carga de losa, sin el peso propio
   de vigas, columnas y muros. Daba 10.04 mm donde Python daba 11.78.

2. Las inercias se exportaban ya cruzadas, y el servidor -- que cruza
   segun la geometria del elemento -- las cruzaba UNA SEGUNDA VEZ.
   Daba 12.17 mm.

EN EL LT2 HAY DOS COSAS MAS QUE ESTE TEST CUIDA
Los MUROS van como columna ancha con su `vecxz` propio, y los BRAZOS
RIGIDOS van como elementos de seccion grande. Las dos cosas dependen
de que el servidor lea el `vecxz` exportado en vez de deducirlo, y de
que la seccion del brazo viaje completa. Si cualquiera de las dos se
pierde, el edificio se ablanda y el numero cambia sin avisar.

Ambos errores son invisibles sin esta comparacion.

SEMANA 5: LA MODIFICACION M1 DE PUNTA A PUNTA POR HTTP
Ademas de reproducir el modelo sin tocar, el test hace lo que hace la
demo en Unity: borra la columna 69 (nodos 144 -> 186) con la misma
edicion que EditorEstructura (semana05/reanalisis_demo.borrar_elemento),
manda el modelo COMO LO MANDA JsonUtility (float32, solo los campos de
ModeloEstructural.cs) y exige los numeros de referencia de la M1 y el
equilibrio confiable que ahora trae la respuesta. Tambien que la
respuesta traiga 'excel' y 'excel_error' (semana05/CONTRATO.md, seccion b).

Correr:  python edificios/lt2/tests/test_reanalisis.py
         (necesita flask; si no esta, el test se salta y lo dice)
"""
import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

_AQUI = os.path.dirname(os.path.abspath(__file__))
_RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(_AQUI)))
sys.path.insert(0, os.path.join(_RAIZ, 'comun'))
import rutas                             # noqa: E402
_RAIZ = rutas.RAIZ

JSON = rutas.unity('lt2')
SERVIDOR = os.path.join(rutas.COMUN, 'servidor_opensees.py')
DEMO = os.path.join(rutas.RAIZ, 'semana05', 'reanalisis_demo.py')
PUERTO = 5099
TOL = 1e-7          # m. El JSON redondea a 9 decimales.

# M1: borrar la columna 69. Referencia medida con
#   python semana05/reanalisis_demo.py lt2 --borrar-elemento 69 --nodo 186
# (el 16-09, igual en doble precision y con --float32 --url). El servidor
# da 8 decimales en m: 1e-4 mm es un orden por encima de esa resolucion
# y de la diferencia float32/doble, que no se vio en el 8o decimal.
ELEMENTO_M1, NODO_M1 = 69, 186
UZ186_G_ANTES_mm = -3.64515
UZ186_G_DESPUES_mm = -21.59875
MAX_G_DESPUES_mm = 21.59875
TOL_M1_mm = 1e-4
G_CONTROL_kN = 34148.98          # CLAUDE.md, numeros de control

fallos = []


def check(cond, msg, detalle=""):
    print(f"  [{'OK  ' if cond else 'FALLA'}] {msg}")
    if detalle:
        print(f"         {detalle}")
    if not cond:
        fallos.append(msg)


try:
    import flask  # noqa: F401
except ImportError:
    print("Flask no esta instalado: se salta el test de reanalisis.")
    print("  .venv\\Scripts\\python.exe -m pip install flask")
    sys.exit(0)

if not os.path.exists(JSON):
    print(f"No existe {JSON}. Corre antes: python src/exportar_unity.py")
    sys.exit(1)

with open(JSON, encoding='utf-8') as f:
    modelo = json.load(f)

print(f"Modelo: {len(modelo['nodos'])} nodos, "
      f"{len(modelo['elementos'])} elementos")

def cargar_demo():
    """semana05/reanalisis_demo.py cargado por ruta: la edicion y la
    emulacion de JsonUtility tienen UNA definicion, la del script."""
    spec = importlib.util.spec_from_file_location('reanalisis_demo', DEMO)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def analizar(modelo, que):
    """POST /analizar; None (y FALLA) si el servidor no lo acepta."""
    req = urllib.request.Request(
        base + '/analizar', data=json.dumps(modelo).encode('utf-8'),
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode('utf-8', 'replace')
        check(False, f"el servidor acepta {que}", f"HTTP {e.code}: {cuerpo[:300]}")
        return None


def revisar_equilibrio(resp, que):
    """Cada caso trae 'equilibrio' confiable y cerrado a su cota: 5e-5 kN
    por reaccion (redondeo a 4 decimales) + 1e-9 relativo (residuo del
    solver medido: 1.2e-6 kN sobre 3633 kN)."""
    for c in resp.get('casos') or []:
        e = c.get('equilibrio') or {}
        if not e.get('aplicada_kN'):
            check(False, f"{que}: el caso {c.get('nombre')} trae 'equilibrio'")
            continue
        escala = max(abs(v) for v in e['aplicada_kN'])
        cota = 5e-5 * len(c['reacciones']) + 1e-9 * escala
        peor = max(abs(v) for v in e['error_kN'])
        check(e.get('confiable') is True and peor <= cota,
              f"{que}: equilibrio {c['nombre']} confiable y cierra",
              f"aplicada {e['aplicada_kN']}  peor error {peor:.1e} <= {cota:.1e} kN")


def uz_mm(resp, caso, nodo):
    c = next(x for x in resp['casos'] if x['nombre'] == caso)
    return next(float(d['uz']) for d in c['desplazamientos'] if int(d['id']) == nodo) * 1000.0


base = f'http://127.0.0.1:{PUERTO}'
proc = subprocess.Popen([sys.executable, SERVIDOR, '--puerto', str(PUERTO)],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True)
try:
    # ------------------------------------------------------------
    print("\n[1] El servidor responde")
    # ------------------------------------------------------------
    vivo = False
    for _ in range(30):
        try:
            with urllib.request.urlopen(base + '/ping', timeout=2):
                vivo = True
                break
        except Exception:
            time.sleep(1)
    check(vivo, "el servidor levanta y contesta /ping")
    if not vivo:
        sys.exit(1)

    # ------------------------------------------------------------
    print("\n[2] Acepta el modelo completo del edificio")
    # ------------------------------------------------------------
    req = urllib.request.Request(
        base + '/analizar', data=json.dumps(modelo).encode('utf-8'),
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            resp = json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode('utf-8', 'replace')
        check(False, "el servidor acepta el modelo", f"HTTP {e.code}: {cuerpo[:300]}")
        sys.exit(1)

    check(resp.get('ok') is True, "el analisis resuelve",
          resp.get('error', '')[:200])

    casos = resp.get('casos') or []
    desp = (casos[0].get('desplazamientos') if casos
            else resp.get('desplazamientos')) or []
    check(len(desp) > 0, "devuelve desplazamientos",
          f"{len(desp)} nodos")

    # ------------------------------------------------------------
    print("\n[3] Reproduce EXACTAMENTE el analisis de Python")
    # ------------------------------------------------------------
    # La deformada precalculada viaja en los propios nodos del JSON.
    previo = {n['id']: n for n in modelo['nodos']}
    peor, cual = 0.0, None
    comparados = 0
    for d in desp:
        n = previo.get(d['id'])
        if n is None:
            continue
        comparados += 1
        for k in ('ux', 'uy', 'uz'):
            e = abs(float(d[k]) - float(n[k]))
            if e > peor:
                peor, cual = e, (d['id'], k)

    check(comparados > 200, "se comparan todos los nodos",
          f"{comparados} nodos comparados")
    check(peor < TOL,
          "el reanalisis da los mismos desplazamientos que modelo_lt2.py",
          f"peor diferencia {peor:.3e} m en {cual}")

    # Un chequeo de orden de magnitud, por si algun dia el JSON
    # quedara con la deformada en cero y todo "coincidiera".
    uz_max = max(abs(float(n['uz'])) for n in modelo['nodos'])
    check(uz_max > 1e-4,
          "la deformada de referencia no es trivialmente cero",
          f"UZ maximo {uz_max*1000:.3f} mm")

    # ------------------------------------------------------------
    print("\n[4] La respuesta trae el equilibrio y el Excel (Semana 5)")
    # ------------------------------------------------------------
    revisar_equilibrio(resp, "sin editar")
    eG = next((c.get('equilibrio') or {} for c in casos if c['nombre'] == 'G'), {})
    check(abs(float((eG.get('aplicada_kN') or [0, 0, 0])[2]) + G_CONTROL_kN) < 0.005,
          "G aplicada = -34 148.98 kN (numero de control)",
          f"{eG.get('aplicada_kN')}")
    check('excel' in resp and 'excel_error' in resp
          and (resp['excel'] is None) != (resp['excel_error'] is None),
          "la raiz trae 'excel' o 'excel_error' (uno de los dos)",
          f"excel = {resp.get('excel')!r}  excel_error = {str(resp.get('excel_error'))[:90]!r}")
    if resp.get('excel'):
        check(os.path.isfile(resp['excel']), "el Excel existe donde dice", resp['excel'])

    # ------------------------------------------------------------
    print(f"\n[5] M1: borrar la columna {ELEMENTO_M1} como en Unity y reanalizar")
    # ------------------------------------------------------------
    demo = cargar_demo()
    clases = demo.esquema_csharp()
    antes_unity = demo.como_jsonutility(modelo, 'ModeloEstructural', clases)
    editado = json.loads(json.dumps(modelo))
    quitadas = demo.borrar_elemento(editado, ELEMENTO_M1)
    despues_unity = demo.como_jsonutility(editado, 'ModeloEstructural', clases)
    check(len(despues_unity['elementos']) == len(modelo['elementos']) - 1
          and len(despues_unity['nodos']) == len(modelo['nodos']),
          "la edicion quita una barra y ningun nodo",
          f"{len(despues_unity['elementos'])} elementos, {len(despues_unity['nodos'])} nodos; "
          f"cargas distribuidas quitadas {sum(len(v) for v in quitadas.values())}")

    r_antes = analizar(antes_unity, "el modelo como lo manda Unity")
    r_desp = analizar(despues_unity, "el modelo editado")
    if r_antes and r_desp:
        check(r_antes.get('ok') is True and r_desp.get('ok') is True,
              "los dos analisis resuelven")
        ua, ud = uz_mm(r_antes, 'G', NODO_M1), uz_mm(r_desp, 'G', NODO_M1)
        check(abs(ua - UZ186_G_ANTES_mm) <= TOL_M1_mm,
              f"antes: UZ{NODO_M1} (G) = {UZ186_G_ANTES_mm} mm", f"{ua:.5f} mm")
        check(abs(ud - UZ186_G_DESPUES_mm) <= TOL_M1_mm,
              f"despues: UZ{NODO_M1} (G) = {UZ186_G_DESPUES_mm} mm", f"{ud:.5f} mm")
        mG = next(c for c in r_desp['casos'] if c['nombre'] == 'G')['max_desplazamiento'] * 1000
        check(abs(mG - MAX_G_DESPUES_mm) <= TOL_M1_mm,
              f"despues: maximo G = {MAX_G_DESPUES_mm} mm", f"{mG:.5f} mm")
        revisar_equilibrio(r_antes, "antes (float32)")
        revisar_equilibrio(r_desp, "despues")
        fz = [next(c for c in r['casos'] if c['nombre'] == 'G')['equilibrio']['aplicada_kN'][2]
              for r in (r_antes, r_desp)]
        # La columna no tenia carga repartida y su peso propio es nodal:
        # la carga de G no cambia. Es la limitacion que se declara.
        check(abs(fz[1] - fz[0]) <= 2 * 5e-5 and abs(fz[1] + G_CONTROL_kN) < 0.005,
              "G aplicada no cambia: el peso propio de la columna queda aplicado",
              f"{fz[0]:.4f} -> {fz[1]:.4f} kN")

finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()

print("\n" + "=" * 60)
if fallos:
    print(f"FALLARON {len(fallos)}:")
    for f in fallos:
        print("  -", f)
    sys.exit(1)
print("EL REANALISIS REPRODUCE EL MODELO DE PYTHON")
print("=" * 60)
