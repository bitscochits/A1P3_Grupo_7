# -*- coding: utf-8 -*-
r"""
================================================================
 semana06_lab/marcador/compilar_marcador.py
   las imagenes de web/imagenes.json -> web/targets.mind
================================================================
 MindAR no busca la imagen tal cual: busca sus PUNTOS CARACTERISTICOS a
 varias escalas, que se calculan una vez y quedan en targets.mind. El
 compilador de MindAR es JavaScript y corre en un navegador, asi que este
 script abre web/herramientas/compilar.html en Chrome (o Edge) sin
 ventana, contra el servidor local, y espera a que deje targets.mind.

   python semana06_lab/marcador/compilar_marcador.py            # la columna 200037
   python semana06_lab/marcador/compilar_marcador.py --config semana06_lab/config_ar_viga_100164.json
================================================================
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(AQUI)
PUERTO = 8091
NAVEGADORES = (r'C:\Program Files\Google\Chrome\Application\chrome.exe',
               r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
               r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
               r'C:\Program Files\Microsoft\Edge\Application\msedge.exe')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default=os.path.join(LAB, 'config_ar.json'))
    args = ap.parse_args(argv)
    sys.path.insert(0, LAB)
    import exportar_ar                                    # la misma regla que usa al exportar
    with open(args.config, encoding='utf-8') as fh:
        tgt = exportar_ar.targets_de(json.load(fh))
    DESTINO = os.path.join(LAB, 'web', tgt['archivo'])
    nav = next((n for n in NAVEGADORES if os.path.exists(n)), None)
    if not nav:
        raise SystemExit('No encuentro Chrome ni Edge: abre a mano '
                         'http://localhost:8080/herramientas/compilar.html con servir.py --http')
    antes = os.path.getmtime(DESTINO) if os.path.exists(DESTINO) else 0
    srv = subprocess.Popen([sys.executable, os.path.join(LAB, 'servir.py'), '--http', '--puerto', str(PUERTO)],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    perfil = tempfile.mkdtemp(prefix='compilar_ar_')
    try:
        time.sleep(1.5)
        # Las imagenes del conjunto de datos, en su orden: la posicion es
        # el indice de addAnchor(i) en ar.js (0 = el marcador impreso).
        nombres, salida = tgt['imagenes'], tgt['archivo']
        faltan = [n for n in nombres if not os.path.exists(os.path.join(LAB, 'web', n))]
        if faltan:
            raise SystemExit('faltan en web/: %s (las fotos las recorta exportar_ar.py --config ...)' % faltan)
        imagenes = ','.join('../' + n for n in nombres)
        chrome = subprocess.Popen([nav, '--headless=new', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
                                   '--user-data-dir=' + perfil,
                                   'http://localhost:%d/herramientas/compilar.html?img=%s&nombre=%s' % (PUERTO, imagenes, salida)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t0 = time.time()
        while time.time() - t0 < 240:
            if os.path.exists(DESTINO) and os.path.getmtime(DESTINO) > antes:
                time.sleep(0.5)
                break
            time.sleep(1)
        chrome.kill()
    finally:
        srv.kill()
        shutil.rmtree(perfil, ignore_errors=True)
    if not (os.path.exists(DESTINO) and os.path.getmtime(DESTINO) > antes):
        raise SystemExit('No se genero %s en 240 s' % tgt['archivo'])
    print('ok %s (%d bytes, %.0f s)' % (os.path.relpath(DESTINO, os.path.dirname(LAB)),
                                        os.path.getsize(DESTINO), time.time() - t0))


if __name__ == '__main__':
    main()
