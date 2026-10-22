"""
CAPA SERVICIOS · generador_pdf.py
Crea el certificado en PDF (A4 horizontal) con la librería fpdf2.
Todo se genera en memoria: no se escribe en el disco (Vercel no deja escribir).

Diseño institucional con los colores de la Academia:
- Azul marino #14213D
- Dorado #B8923D
"""
import io
import zipfile
from datetime import date

from fpdf import FPDF

AZUL = (20, 33, 61)       # #14213D
DORADO = (184, 146, 61)   # #B8923D
GRIS = (88, 94, 102)
CREMA = (249, 247, 242)

ANCHO = 297  # ancho de una hoja A4 horizontal, en milímetros
ALTO = 210   # alto de una hoja A4 horizontal, en milímetros

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _fecha_hoy():
    hoy = date.today()
    return f"{hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}"


def _codigo(resultado):
    """Código sencillo para identificar el documento."""
    return f"AH-{date.today().year}-{resultado['identificacion']}"


def _seguro(texto):
    """Evita que un carácter raro rompa el PDF con las fuentes básicas."""
    return str(texto).encode("latin-1", "replace").decode("latin-1")


def _texto_centrado(pdf, y, texto, tamano, estilo="", color=AZUL, alto=8, ancho=257):
    """Escribe una línea centrada en la hoja."""
    pdf.set_font("Helvetica", estilo, tamano)
    pdf.set_text_color(*color)
    pdf.set_xy((ANCHO - ancho) / 2, y)
    pdf.cell(ancho, alto, texto, align="C")


def _fuente_ajustada(pdf, texto, estilo, tamano_max, ancho_max, tamano_min=9):
    """Baja el tamaño de la letra hasta que el texto quepa en el ancho indicado.
    Se usa para nombres y programas largos, sin cortar el texto."""
    tamano = tamano_max
    pdf.set_font("Helvetica", estilo, tamano)
    while tamano > tamano_min and pdf.get_string_width(texto) > ancho_max:
        tamano -= 0.5
        pdf.set_font("Helvetica", estilo, tamano)
    return tamano


def _marco(pdf):
    """Dibuja el marco doble: azul marino por fuera y dorado por dentro."""
    pdf.set_draw_color(*AZUL)
    pdf.set_line_width(2.2)
    pdf.rect(8, 8, ANCHO - 16, ALTO - 16)

    pdf.set_draw_color(*DORADO)
    pdf.set_line_width(0.8)
    pdf.rect(13, 13, ANCHO - 26, ALTO - 26)

    pdf.set_draw_color(*AZUL)
    pdf.set_line_width(0.25)
    pdf.rect(16.5, 16.5, ANCHO - 33, ALTO - 33)


def _encabezado(pdf, codigo):
    """Monograma, nombre de la institución y código del certificado."""
    # Monograma "AH" dentro de un círculo azul con anillo dorado.
    pdf.set_fill_color(*AZUL)
    pdf.circle(34, 32, 12.5, style="F")
    pdf.set_draw_color(*DORADO)
    pdf.set_line_width(0.9)
    pdf.circle(34, 32, 12.5, style="D")

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*DORADO)
    pdf.set_xy(24, 28.5)
    pdf.cell(20, 7, "AH", align="C")

    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*AZUL)
    pdf.set_xy(53, 21)
    pdf.cell(170, 8, "ACADEMIA HORIZONTE")

    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*GRIS)
    pdf.set_xy(53, 30)
    pdf.cell(185, 5, "Universidad Fundepos · Técnico en IA Empresarial")

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*DORADO)
    pdf.set_xy(190, 21)
    pdf.cell(88, 5, "CERTIFICADO OFICIAL", align="R")

    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(*GRIS)
    pdf.set_xy(170, 28)
    pdf.cell(108, 5, f"Código {codigo}", align="R")

    # Línea dorada que separa el encabezado del cuerpo del certificado.
    pdf.set_draw_color(*DORADO)
    pdf.set_line_width(0.6)
    pdf.line(53, 40, 278, 40)


def _metrica(pdf, x, y, ancho, etiqueta, valor):
    """Dibuja una cajita con una etiqueta pequeña y un valor grande."""
    pdf.set_fill_color(*CREMA)
    pdf.rect(x, y, ancho, 15, style="F")

    pdf.set_draw_color(*DORADO)
    pdf.set_line_width(0.9)
    pdf.line(x, y, x + ancho, y)

    pdf.set_font("Helvetica", "B", 6.5)
    pdf.set_text_color(*GRIS)
    pdf.set_xy(x, y + 2)
    pdf.cell(ancho, 4, etiqueta, align="C")

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*AZUL)
    pdf.set_xy(x, y + 6.5)
    pdf.cell(ancho, 7, valor, align="C")


def _firma(pdf, centro_x, cargo):
    """Línea y cargo para la firma institucional."""
    pdf.set_draw_color(*AZUL)
    pdf.set_line_width(0.5)
    pdf.line(centro_x - 32, 173, centro_x + 32, 173)

    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(*GRIS)
    pdf.set_xy(centro_x - 40, 175.5)
    pdf.cell(80, 4, cargo, align="C")


def _sello(pdf):
    """Sello circular dorado en el centro de las firmas."""
    centro_x, centro_y = 148.5, 166

    pdf.set_draw_color(*DORADO)
    pdf.set_line_width(1.1)
    pdf.circle(centro_x, centro_y, 11, style="D")
    pdf.set_line_width(0.5)
    pdf.circle(centro_x, centro_y, 8.7, style="D")

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*AZUL)
    pdf.set_xy(centro_x - 10, centro_y - 4.5)
    pdf.cell(20, 5, "AH", align="C")

    pdf.set_font("Helvetica", "B", 4.8)
    pdf.set_text_color(*DORADO)
    pdf.set_xy(centro_x - 15.5, centro_y + 1.5)
    pdf.cell(31, 3, "CERTIFICADO OFICIAL", align="C")


def crear_pdf(resultado):
    """Crea el certificado de un estudiante y devuelve los bytes del PDF."""
    nombre = _seguro(resultado["nombre"])
    programa = _seguro(resultado["programa"])
    cohorte = _seguro(resultado["cohorte"])
    identificacion = _seguro(resultado["identificacion"])
    codigo = _codigo(resultado)

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(False)
    pdf.set_title(f"Certificado de {resultado['tipo']} · {nombre}")
    pdf.set_author("Academia Horizonte")
    pdf.set_subject(f"Certificado de {resultado['tipo']} · {programa}")
    pdf.set_creator("Academia Horizonte")
    pdf.add_page()

    _marco(pdf)
    _encabezado(pdf, codigo)

    # Título principal y tipo de certificado.
    _texto_centrado(pdf, 49, "CERTIFICADO", 26, "B", AZUL, alto=12)
    _texto_centrado(pdf, 62, f"DE {resultado['tipo'].upper()}", 14, "B", DORADO, alto=7)

    pdf.set_draw_color(*DORADO)
    pdf.set_line_width(0.5)
    pdf.line(118, 73, 179, 73)
    pdf.set_fill_color(*DORADO)
    pdf.circle(115.5, 73, 0.9, style="F")
    pdf.circle(181.5, 73, 0.9, style="F")

    # Nombre del estudiante, con tamaño ajustado si es muy largo.
    _texto_centrado(pdf, 79, "Se otorga el presente certificado a", 10.5, "I", GRIS, alto=7)
    tamano_nombre = _fuente_ajustada(pdf, nombre, "B", 24, 245)
    _texto_centrado(pdf, 87, nombre, tamano_nombre, "B", AZUL, alto=13)

    pdf.set_draw_color(*DORADO)
    pdf.set_line_width(0.6)
    pdf.line(70, 104, 227, 104)
    _texto_centrado(pdf, 106, f"Identificación {identificacion}", 8.5, "", GRIS, alto=5)

    # Frase según el tipo de certificado y programa cursado.
    if resultado["tipo"] == "Aprobación":
        accion = "por haber aprobado el programa"
    else:
        accion = "por su participación en el programa"
    _texto_centrado(pdf, 113, accion, 10.5, "", GRIS, alto=6)

    tamano_programa = _fuente_ajustada(pdf, programa, "B", 16, 240)
    _texto_centrado(pdf, 120, programa, tamano_programa, "B", AZUL, alto=8)
    _texto_centrado(
        pdf, 130,
        f"Cohorte {cohorte}   ·   {resultado['modulos']} módulos completados",
        9, "", DORADO, alto=5,
    )

    # Tres cajitas con las cifras del estudiante.
    ancho_caja = 50
    separacion = 6
    inicio_x = (ANCHO - (3 * ancho_caja + 2 * separacion)) / 2
    _metrica(pdf, inicio_x, 139, ancho_caja, "PROMEDIO", f"{resultado['promedio']:.2f}")
    _metrica(pdf, inicio_x + ancho_caja + separacion, 139, ancho_caja,
             "ASISTENCIA", f"{resultado['asistencia']:.2f} %")
    _metrica(pdf, inicio_x + 2 * (ancho_caja + separacion), 139, ancho_caja,
             "MÓDULOS", f"{resultado['modulos']}")

    # Firmas y sello institucional.
    _firma(pdf, 86, "Coordinación Académica")
    _firma(pdf, 211, "Dirección Académica")
    _sello(pdf)

    # Pie de página con la fecha y el código de verificación.
    _texto_centrado(pdf, 188, f"Emitido el {_fecha_hoy()} · Código {codigo}",
                    7.5, "", GRIS, alto=4)
    _texto_centrado(pdf, 192,
                    "Documento generado automáticamente. Verificable con la identificación del estudiante.",
                    6.5, "I", GRIS, alto=4)

    return bytes(pdf.output())


def nombre_archivo(resultado):
    limpio = "".join(c if c.isalnum() else "_" for c in resultado["nombre"])
    return f"Certificado_{limpio}_{resultado['identificacion']}.pdf"


def crear_zip(resultados):
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as z:
        for r in resultados:
            z.writestr(nombre_archivo(r), crear_pdf(r))
    memoria.seek(0)
    return memoria
