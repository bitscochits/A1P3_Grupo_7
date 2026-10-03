# -*- coding: utf-8 -*-
r"""
================================================================
 semana06_lab/servir.py
   LA APP DE AR, SERVIDA AL TELEFONO
================================================================
 Safari solo deja usar la camara en una pagina SEGURA: https, o
 http://localhost en el mismo equipo. El telefono no es "localhost", asi
 que para el iPhone hace falta https. Este script:

   1. genera (una vez) un certificado autofirmado para las IP del PC, con
      el openssl que trae Git for Windows, en semana06_lab/.cert/ (fuera
      de git);
   2. sirve semana06_lab/web por https en el puerto 8443.

 En el iPhone: Safari -> https://<IP del PC>:8443 -> "Mostrar detalles"
 -> "visitar este sitio web" (el aviso es porque el certificado lo firma
 este PC y no una autoridad). Despues pide permiso para la camara.

   python semana06_lab/servir.py            # https, para el telefono
   python semana06_lab/servir.py --http     # http://localhost:8080, para probar en el PC

 Tambien acepta POST /guardar?nombre=targets.mind SOLO desde el propio
 PC: lo usa web/herramientas/compilar.html para dejar la imagen compilada
 en web/ (ver marcador/compilar_marcador.py).
================================================================
"""
from __future__ import annotations

import argparse
import functools
import http.server
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import time
import urllib.parse

AQUI = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(AQUI, 'web')
CERT = os.path.join(AQUI, '.cert')
# targets.mind (la columna 200037) y targets_<conjunto>.mind (cada viga en terreno).
PERMITIDO = re.compile(r'^targets(_[a-z0-9_]+)?\.mind$')


def ips_locales():
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except socket.gaierror:
        pass
    # La IP de salida (la de la red WiFi), sin mandar nada.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(i for i in ips if not i.startswith('127.') and not i.startswith('169.254.'))


def buscar_openssl():
    for c in (shutil.which('openssl'), r'C:\Program Files\Git\usr\bin\openssl.exe',
              r'C:\Program Files\Git\mingw64\bin\openssl.exe'):
        if c and os.path.exists(c):
            return c
    return None


def certificado(ips):
    os.makedirs(CERT, exist_ok=True)
    crt, key = os.path.join(CERT, 'cert.pem'), os.path.join(CERT, 'key.pem')
    marca = os.path.join(CERT, 'ips.txt')
    san = ','.join(['DNS:localhost', 'IP:127.0.0.1'] + ['IP:%s' % i for i in ips])
    # Se rehace si cambio la IP del PC o si le queda poco: dura 60 dias.
    if (os.path.exists(crt) and os.path.exists(marca) and open(marca).read() == san
            and time.time() - os.path.getmtime(crt) < 50 * 86400):
        return crt, key
    openssl = buscar_openssl()
    if not openssl:
        raise SystemExit('No encuentro openssl (viene con Git for Windows). Instala Git o usa --http.')
    subprocess.run([openssl, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '60',
                    '-keyout', key, '-out', crt, '-subj', '/CN=Grupo 7 LAB AR',
                    '-addext', 'subjectAltName=' + san], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with open(marca, 'w') as fh:
        fh.write(san)
    return crt, key


class Manejador(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json',
                      '.mind': 'application/octet-stream', '.wasm': 'application/wasm'}

    def end_headers(self):
        # Sin cache: si se reexporta ar.json, el telefono ve lo nuevo.
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def do_POST(self):
        partes = urllib.parse.urlparse(self.path)
        nombre = urllib.parse.parse_qs(partes.query).get('nombre', [''])[0]
        if partes.path != '/guardar' or not PERMITIDO.match(nombre) or self.client_address[0] != '127.0.0.1':
            self.send_error(403)
            return
        largo = int(self.headers.get('Content-Length', 0))
        datos = self.rfile.read(largo)
        with open(os.path.join(WEB, nombre), 'wb') as fh:
            fh.write(datos)
        print('  guardado web/%s (%d bytes)' % (nombre, len(datos)))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'ok')


def main(argv=None):
    sys.stdout.reconfigure(line_buffering=True)      # que las instrucciones salgan al tiro
    ap = argparse.ArgumentParser(description='Sirve la app de AR')
    ap.add_argument('--http', action='store_true', help='http en localhost (pruebas en el PC)')
    ap.add_argument('--puerto', type=int)
    args = ap.parse_args(argv)

    manejador = functools.partial(Manejador, directory=WEB)
    if args.http:
        puerto = args.puerto or 8080
        srv = http.server.ThreadingHTTPServer(('127.0.0.1', puerto), manejador)
        print('  http://localhost:%d   (solo este PC; Ctrl+C para parar)' % puerto)
    else:
        puerto = args.puerto or 8443
        ips = ips_locales()
        crt, key = certificado(ips)
        srv = http.server.ThreadingHTTPServer(('0.0.0.0', puerto), manejador)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(crt, key)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
        print('=' * 64)
        print('  APP DE AR (semana06_lab/web), por https')
        print('=' * 64)
        for ip in ips:
            print('  En el iPhone (mismo WiFi):  https://%s:%d' % (ip, puerto))
        print('  Safari avisa que el certificado no es de confianza: "Mostrar detalles"')
        print('  -> "visitar este sitio web". Despues acepta la camara.')
        print('  Ctrl+C para parar.')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
