# -*- coding: utf-8 -*-
r"""
================================================================
 semana05/servidor_s5.py  -  EL SERVIDOR DE LA SEMANA 5
================================================================
 Un solo servidor, un solo puerto (5000). Importa la app Flask de
 comun/servidor_opensees.py, que trae /ping y /analizar tal cual, y le
 agrega la superposicion con lambdas libres:

   POST /analizar   (comun/servidor_opensees.py) reanalisis del modelo
   GET  /ping       (comun/servidor_opensees.py)
   POST /combinar   {"edificio": "lt2", "G": 1.2, "Q": 1.0, "EX": -1.4, "EY": 0}
                    -> {ok, error, edificio, parametros, caso: CasoS4, equilibrio}
   GET  /estados    -> {ok, error, estados [E1..E3 sin caso], rangos de los sliders}

 Correr:
   python semana05/servidor_s5.py                    solo este equipo, puerto 5000
   python semana05/servidor_s5.py --lan              toda la red local (celular)
   python semana05/servidor_s5.py --puerto 5057
   python semana05/servidor_s5.py --cs 0.20          la base con otros parametros
                                                     (flags de semana03/parametros.py)

 Formato exacto de pedidos y respuestas: semana05/CONTRATO.md §3.

 ----------------------------------------------------------------
 QUE HACE /combinar
 ----------------------------------------------------------------
 La primera peticion de un edificio arma su BASE: los cuatro casos
 resueltos en OpenSees y las curvas P-M (semana05/superposicion.base,
 unos 2 s en el LT2). Queda en memoria. Desde ahi cada combinacion es
 superposicion.caso_combinado, suma lineal en Python sin volver a
 OpenSees, y la demanda-capacidad se rehace entera con los f combinados
 porque no es lineal. Unity no suma nada. Medido en el LT2 (16-09):
 0.02 s dentro del servidor con el JSON ya escrito (0.2 MB) y 0.12 s
 desde Invoke-WebRequest con E3; la base, 1.9 a 2.2 s.

 Al arrancar se arma la base del LT2 en segundo plano (la demo es del
 LT2), para que el primer slider no espere; --sin-precalentar lo evita.

 ----------------------------------------------------------------
 POR QUE EL LOCK
 ----------------------------------------------------------------
 OpenSees es un singleton: armar la base resuelve el modelo y corre
 las secciones de fibras. Si un /analizar entra a la vez, uno hace
 ops.wipe() sobre el modelo del otro. Por eso la base se arma con el
 MISMO lock que usa /analizar. Combinar no toca OpenSees y no lo toma.

 Los errores se atrapan con BaseException (salvo Ctrl+C): parametros.py
 y lab_semana03.py cortan con SystemExit, y un SystemExit dentro de un
 hilo de Flask terminaria la peticion sin respuesta. Todo error vuelve
 como JSON {"ok": false, "error": ...}: 400 si el pedido es invalido,
 500 si fallo algo nuestro. Unity lee el cuerpo tambien en ese caso.
================================================================
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import threading
import time
import traceback

_AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_AQUI), 'comun'))
import rutas                                 # noqa: E402
rutas.entrar(__file__)

from flask import jsonify, request           # noqa: E402
from werkzeug.exceptions import BadRequest   # noqa: E402

import servidor_opensees                     # noqa: E402
from servidor_opensees import app            # noqa: E402
import superposicion as sp                   # noqa: E402

PUERTO = 5000
EDIFICIO_DEMO = 'lt2'

# El lock del motor que usa /analizar. Si algun dia no existiera, uno
# propio al menos serializa las bases entre si (y se avisa al arrancar).
LOCK_OPENSEES = getattr(servidor_opensees, '_lock_opensees', None)
_LOCK_PROPIO = LOCK_OPENSEES is None
if _LOCK_PROPIO:
    LOCK_OPENSEES = threading.Lock()

# Flags de parametros.py con que se arma la base (--cs 0.20 ...). Tienen
# que ser los del anexo que Unity tiene abierto: la respuesta trae las
# lineas de 'parametros' y el visor avisa si no son las del anexo.
ARGV_PARAMETROS = []

_bases = {}
_lock_bases = threading.Lock()


class PedidoInvalido(ValueError):
    """Lo que se arregla cambiando el pedido: HTTP 400."""


def edificio_valido(nombre):
    r"""
    El edificio tiene que ser un nombre simple con modelo en data/modelo/.
    Va a una ruta de archivo: un '../algo' venido por la red no pasa.
    """
    if not isinstance(nombre, str) or not re.fullmatch(r'[a-z0-9_]{1,40}', nombre):
        raise PedidoInvalido('edificio tiene que ser un nombre como "lt2", vino %r'
                             % (nombre,))
    if not os.path.isfile(rutas.modelo(nombre)):
        hay = sorted(os.path.splitext(f)[0] for f in os.listdir(rutas.MODELO)
                     if f.endswith('.json'))
        raise PedidoInvalido('no hay modelo %r en data/modelo/. Hay: %s'
                             % (nombre, ', '.join(hay)))
    return nombre


def obtener_base(edificio):
    """(base, recien_armada). Una sola base por edificio, armada una vez."""
    with _lock_bases:
        b = _bases.get(edificio)
        if b is not None:
            return b, False
        with LOCK_OPENSEES:
            b = sp.base(edificio, ARGV_PARAMETROS)
        _bases[edificio] = b
        print('  [base] %s armada en %.1f s (%d nodos, %d elementos)%s'
              % (edificio, b['segundos'], len(b['ids_nodos']), len(b['largos']),
                 ('; ' + b['avisos_opensees']) if b['avisos_opensees'] else ''))
        return b, True


def _error(e, codigo):
    if codigo >= 500:
        traceback.print_exc()
    texto = str(e)
    if isinstance(e, BadRequest):
        texto = 'el cuerpo no es JSON valido: %s' % (e.description or texto)
    elif isinstance(e, SystemExit):
        texto = 'el laboratorio corto: %s' % texto
    return jsonify({'ok': False, 'error': texto}), codigo


@app.route('/combinar', methods=['POST'], endpoint='combinar_s5')
def combinar_s5():
    """POST /combinar: un CasoS4 'LIBRE' para los lambdas pedidos."""
    t0 = time.time()
    try:
        pedido = request.get_json(force=True)
        if not isinstance(pedido, dict):
            raise PedidoInvalido('el cuerpo tiene que ser un objeto JSON '
                                 '{"edificio", "G", "Q", "EX", "EY"}')
        edificio = edificio_valido(pedido.get('edificio', EDIFICIO_DEMO))
        try:
            lambdas = sp.lambdas_de(pedido)
        except ValueError as e:
            raise PedidoInvalido(str(e))
        b, nueva = obtener_base(edificio)
        cuerpo = sp.respuesta_combinar(b, lambdas)
    except (PedidoInvalido, BadRequest, OverflowError) as e:   # lambda ~1e300 desborda: pedido
        return _error(e, 400)
    except BaseException as e:           # noqa: B902 -- ver el encabezado
        if isinstance(e, KeyboardInterrupt):
            raise
        return _error(e, 500)
    # El tiempo incluye escribir el JSON (unos 0.2 MB en el LT2): es lo que
    # espera Unity, no solo la suma.
    respuesta = jsonify(cuerpo)
    print('  POST /combinar %s %s: %.3f s%s'
          % (edificio, cuerpo['caso']['descripcion'], time.time() - t0,
             ' (armando la base)' if nueva else ''))
    return respuesta


@app.route('/estados', methods=['GET'], endpoint='estados_s5')
def estados_s5():
    """GET /estados: E1..E3 (sin caso) y los rangos de los sliders."""
    try:
        return jsonify(sp.respuesta_estados())
    except BaseException as e:           # noqa: B902
        if isinstance(e, KeyboardInterrupt):
            raise
        return _error(e, 500)


def _precalentar(edificio):
    try:
        obtener_base(edificio)
    except BaseException as e:           # noqa: B902
        if isinstance(e, KeyboardInterrupt):
            raise
        print('  [base] no se pudo armar la de %s: %s' % (edificio, e))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='Servidor de la Semana 5: /analizar, /ping, /combinar, /estados',
        allow_abbrev=False)
    ap.add_argument('--lan', action='store_true',
                    help='escuchar en toda la red local (celular). No en una red publica.')
    ap.add_argument('--puerto', type=int, default=PUERTO)
    ap.add_argument('--sin-precalentar', action='store_true',
                    help='no armar la base del LT2 al arrancar')
    args, resto = ap.parse_known_args(argv)

    # Lo que no es de este servidor son flags de parametros.py. Se validan
    # ahora: un --cs mal escrito tiene que cortar al arrancar, no en la
    # primera peticion de Unity.
    sp.eu.parametros.cargar(resto)
    ARGV_PARAMETROS[:] = resto

    host = '0.0.0.0' if args.lan else '127.0.0.1'
    print('=' * 64)
    print('  SERVIDOR DE LA SEMANA 5')
    print('=' * 64)
    print('  Escuchando en: http://%s:%d' % ('0.0.0.0' if args.lan else 'localhost',
                                             args.puerto))
    if args.lan:
        print('  *** ABIERTO A TODA LA RED LOCAL (--lan) ***')
    else:
        print('  Solo accesible desde este equipo (--lan para el celular).')
    print('  POST /analizar  -> reanalisis del modelo editado (servidor_opensees.py)')
    print('  GET  /ping      -> chequear conexion')
    print('  POST /combinar  -> superposicion con lambdas libres')
    print('  GET  /estados   -> E1..E3 y rangos de los sliders')
    print('  parametros de la base: %s' % (' '.join(resto) or 'los de parametros.json'))
    if _LOCK_PROPIO:
        print('  AVISO: servidor_opensees.py ya no expone _lock_opensees; la base y')
        print('         /analizar podrian pisarse en OpenSees')
    print('=' * 64)

    if not args.sin_precalentar:
        threading.Thread(target=_precalentar, args=(EDIFICIO_DEMO,), daemon=True).start()
    app.run(host=host, port=args.puerto, debug=False, threaded=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
