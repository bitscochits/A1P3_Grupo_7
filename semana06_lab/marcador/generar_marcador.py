# -*- coding: utf-8 -*-
r"""
================================================================
 semana06_lab/marcador/generar_marcador.py
   LA IMAGEN DE REFERENCIA Y EL PDF PARA IMPRIMIRLA
================================================================
 El image tracking reconoce la imagen por sus ESQUINAS (puntos de
 contraste fuerte que no se repiten). Se compararon cuatro candidatas
 compilandolas con MindAR (puntos de deteccion / de seguimiento):

   captura del visor, conjunto, sin agrandar   281 / 27 + 11   <- esta
   captura del visor, LT2                      338 / 31 + 10
   planta del conjunto dibujada del modelo     234 / 13 + 6    (grilla repetida)
   vista 3D del modelo con IDs                 184 /  9 + 7
   (y la primera: una captura AGRANDADA        ... / 21 + 12, borrosa)

 La captura del visor tiene texto, la curva P-M y el edificio: muchas
 esquinas nitidas y nada simetrico. Se usa la del conjunto, que es el
 edificio de este lab, y SIN reescalar (reescalar la vuelve borrosa y
 pierde esquinas). El contenido de la foto no importa para el tracking:
 es la textura que se reconoce. Lo que dice que elemento es, es el rotulo.

 Deja:
   marcador.png            lo que se compila a web/targets.mind
   marcador_imprimir.pdf   la imagen a EXACTAMENTE ancho_impreso_m (A4, 100 %)
   ../web/marcador.png     la misma, para compilar y para verla

   python semana06_lab/marcador/generar_marcador.py
   python semana06_lab/marcador/compilar_marcador.py     # despues: targets.mind
================================================================
"""
import io
import json
import os
import shutil

from PIL import Image, ImageDraw, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(AQUI)
RAIZ = os.path.dirname(LAB)
FOTO = os.path.join(RAIZ, 'semana05_lab', 'capturas_conjunto',
                    '14_capacidad_columna_200005_PM_y_mapa_DC_0.9G-1.4EX.jpg')
RECORTE = (10, 90, 930, 860)      # 920 x 770 px de la captura de 1600 x 900: panel + edificio
ANCHO, ALTO_ROTULO = 1000, 200


def fuente(tam, negrita=False):
    try:
        return ImageFont.truetype(os.path.join(r'C:\Windows\Fonts', 'arialbd.ttf' if negrita else 'arial.ttf'), tam)
    except OSError:
        return ImageFont.load_default()


def main():
    with io.open(os.path.join(LAB, 'config_ar.json'), encoding='utf-8') as fh:
        cfg = json.load(fh)
    ancho_m = float(cfg['ancho_impreso_m'])
    elem = cfg['elemento']

    foto = Image.open(FOTO).convert('RGB').crop(RECORTE)          # sin reescalar
    alto = 40 + foto.size[1] + ALTO_ROTULO
    img = Image.new('RGB', (ANCHO, alto), 'white')
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, ANCHO - 1, alto - 1], outline='black', width=20)
    x0 = (ANCHO - foto.size[0]) // 2
    img.paste(foto, (x0, 40))
    d.rectangle([x0, 40, x0 + foto.size[0], 40 + foto.size[1]], outline='black', width=5)
    y = 40 + foto.size[1] + 22
    d.text((48, y), 'GRUPO 7 · LAB AR', font=fuente(56, True), fill='black')
    d.text((48, y + 70), 'columna %d · cara %s · %.0f cm' % (elem, cfg['cara'], ancho_m * 100),
           font=fuente(40), fill=(30, 58, 95))
    # Figura asimetrica: la imagen no se confunde consigo misma girada.
    d.polygon([(ANCHO - 190, y + 6), (ANCHO - 60, y + 6), (ANCHO - 60, y + 120)], fill=(200, 100, 30))
    d.rectangle([ANCHO - 190, y + 78, ANCHO - 130, y + 120], fill=(30, 58, 95))

    png = os.path.join(AQUI, 'marcador.png')
    img.save(png)
    shutil.copyfile(png, os.path.join(LAB, 'web', 'marcador.png'))

    # PDF a tamano exacto: A4 a 300 dpi, la imagen de ancho_m y una regla
    # de 10 cm para comprobar que la impresora no escalo.
    dpi = 300
    a4 = (int(8.2677 * dpi), int(11.6929 * dpi))
    hoja = Image.new('RGB', a4, 'white')
    px = int(round(ancho_m / 0.0254 * dpi))
    py = int(round(px * alto / ANCHO))
    arriba = int(1.2 / 2.54 * dpi)
    hoja.paste(img.resize((px, py), Image.LANCZOS), ((a4[0] - px) // 2, arriba))
    dh = ImageDraw.Draw(hoja)
    y0 = arriba + py + int(1.0 / 2.54 * dpi)
    diez = int(round(10 / 2.54 * dpi))
    x1 = (a4[0] - diez) // 2
    dh.line([x1, y0, x1 + diez, y0], fill='black', width=4)
    for k in range(11):
        xx = x1 + int(round(k / 2.54 * dpi))
        dh.line([xx, y0 - (30 if k % 5 == 0 else 18), xx, y0], fill='black', width=3)
    f = fuente(38)
    dh.text((x1, y0 + 18), 'esta linea mide 10 cm: si no, la impresora escalo', font=f, fill='black')
    txt = ['Imprimir al 100 % ("tamano real", sin "ajustar a la pagina").',
           'La imagen tiene que medir %.1f cm de ANCHO (el borde negro, de lado a lado).' % (ancho_m * 100),
           'Si mide otra cosa: cambiar ancho_impreso_m en semana06_lab/config_ar.json',
           'y correr python semana06_lab/exportar_ar.py.',
           'EN SITIO: pegarla plana y derecha en la cara %s de la columna %d,' % (cfg['cara'], elem),
           'con su centro a %.2f m sobre el piso.' % cfg['altura_centro_m'],
           'MAQUETA: dejarla plana sobre la mesa.']
    for i, t in enumerate(txt):
        dh.text((int(2 / 2.54 * dpi), y0 + 100 + i * 54), t, font=f, fill='black')
    pdf = os.path.join(AQUI, 'marcador_imprimir.pdf')
    hoja.save(pdf, 'PDF', resolution=dpi)
    print('ok', png, '(%dx%d px)' % img.size)
    print('ok', pdf, '(imagen de %.1f x %.1f cm a %d dpi)' % (ancho_m * 100, ancho_m * 100 * alto / ANCHO, dpi))


if __name__ == '__main__':
    main()
