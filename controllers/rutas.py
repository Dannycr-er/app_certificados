"""
CAPA CONTROLADOR · rutas.py
Recibe los clics del usuario (peticiones), llama al modelo y a los servicios,
y entrega la vista. Aquí no se calcula nada.
"""
import io
import os
import secrets
from functools import wraps
from urllib.parse import unquote

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   send_file, session, url_for)

from models import certificados, datos
from services import carga_excel, exportador_excel, generador_pdf

# Tipo de archivo que espera el navegador para un Excel moderno (.xlsx).
EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

rutas = Blueprint("rutas", __name__)


# ---------------------------------------------------------------------------
# Entrada a la app · usuarios y contraseñas
# ---------------------------------------------------------------------------
# Las credenciales NO se escriben en el código: se leen de variables de entorno
# (el archivo .env en su computadora, o Environment Variables en Vercel).
# Si falta alguna, se usan estos valores de demostración y la pantalla de
# entrada muestra un aviso para que nadie se confunda.
DEMO_ADMIN = ("admin@academia.demo", "Admin1234")
DEMO_USUARIO = ("usuario@academia.demo", "Usuario1234")


def _credenciales():
    """Devuelve los usuarios permitidos y cuáles están en modo demostración.
    Cada usuario es una tupla: (correo, clave, rol)."""
    demo = []

    def _usuario(nombre_correo, nombre_clave, demo_par, rol):
        """Lee un usuario de las variables de entorno. Si falta el correo o la
        clave, usa el par de demostración y lo anota para avisar en pantalla."""
        correo = (os.environ.get(nombre_correo) or "").strip()
        clave = os.environ.get(nombre_clave) or ""
        if not correo or not clave:
            usuario = (demo_par[0], demo_par[1], rol)
            demo.append(usuario)
            return usuario
        return (correo.lower(), clave, rol)

    usuarios = [
        _usuario("ADMIN_CORREO", "ADMIN_CLAVE", DEMO_ADMIN, "admin"),
        _usuario("USUARIO_CORREO", "USUARIO_CLAVE", DEMO_USUARIO, "usuario"),
    ]
    return usuarios, demo


def _buscar_usuario(correo, clave):
    """Compara el correo y la contraseña con los usuarios permitidos.
    Devuelve el rol si coincide, o None si las credenciales son incorrectas."""
    correo = (correo or "").strip().lower()
    clave = clave or ""
    for correo_valido, clave_valida, rol in _credenciales()[0]:
        # compare_digest compara sin revelar información por el tiempo de respuesta.
        # Se pasan como bytes para aceptar correos o claves con tildes.
        if secrets.compare_digest(correo.encode("utf-8"), correo_valido.encode("utf-8")) and \
                secrets.compare_digest(clave.encode("utf-8"), clave_valida.encode("utf-8")):
            return rol
    return None


def requiere_login(vista):
    """Decorador: si no hay una sesión iniciada, manda a la pantalla de entrada."""
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if not session.get("correo"):
            return redirect(url_for("rutas.login"))
        return vista(*args, **kwargs)
    return envoltura


def solo_admin(vista):
    """Decorador: solo deja pasar al rol "admin". A los demás les responde 403."""
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if session.get("rol") != "admin":
            abort(403)
        return vista(*args, **kwargs)
    return envoltura


@rutas.errorhandler(403)
def sin_permiso(_error):
    """Muestra una página amable cuando alguien entra a una sección de administrador."""
    # El código HTTP sigue siendo 403, para que el navegador sepa que no hay permiso.
    return render_template("sin_permiso.html"), 403


@rutas.app_errorhandler(413)
def archivo_muy_grande(_error):
    """Aviso amable cuando la subida supera MAX_CONTENT_LENGTH (4 MB)."""
    flash("El archivo es demasiado grande: el máximo es 4 MB en total. "
          "Vercel rechaza las peticiones de más de 4.5 MB.", "error")
    return redirect(url_for("rutas.tablero") + "#panel-admin")


@rutas.route("/login", methods=["GET", "POST"])
def login():
    """Pantalla de entrada: pide correo y contraseña y guarda el usuario en la sesión."""
    # Si ya entró, no tiene sentido mostrarle otra vez el formulario.
    if session.get("correo"):
        return redirect(url_for("rutas.tablero"))

    error = None
    if request.method == "POST":
        rol = _buscar_usuario(request.form.get("correo"), request.form.get("clave"))
        if rol:
            session.clear()  # sesión nueva, para no reutilizar datos de una anterior
            session["correo"] = request.form.get("correo", "").strip().lower()
            session["rol"] = rol
            return redirect(url_for("rutas.tablero"))
        # Mensaje genérico: no decimos si falló el correo o la contraseña.
        error = "Correo o contraseña incorrectos."

    _usuarios, demo = _credenciales()
    return render_template("login.html", error=error, demo=demo)


@rutas.route("/salir")
def salir():
    """Borra la sesión y devuelve a la pantalla de entrada."""
    session.clear()
    return redirect(url_for("rutas.login"))


def _datos():
    """Estudiantes y evaluaciones: de los Excel si no hay base, o de la base de datos."""
    if datos.sin_base_de_datos():
        return carga_excel.datos_desde_excel()
    carga_excel.asegurar_datos()
    return datos.leer_estudiantes(), datos.leer_evaluaciones()


def _resultados():
    estudiantes, evaluaciones = _datos()
    return certificados.calcular_resultados(estudiantes, evaluaciones)


def _vista_tablero(estudiantes, evaluaciones, origen, datos_subidos=False):
    """Calcula los resultados y entrega el tablero.

    Se usa tanto para los datos de fábrica como para los Excel que sube el
    administrador. Así las reglas del negocio viven solo en models/certificados.py.
    """
    resultados, contadores, inconsistencias = certificados.calcular_resultados(
        estudiantes, evaluaciones
    )
    return render_template(
        "tablero.html",
        resultados=resultados,
        contadores=contadores,
        inconsistencias=inconsistencias,
        motor=datos.nombre_motor(),
        supabase=datos.usa_supabase(),
        n_est=len(estudiantes),
        n_eva=len(evaluaciones),
        origen=origen,
        datos_subidos=datos_subidos,
    )


@rutas.route("/")
@requiere_login
def tablero():
    try:
        estudiantes, evaluaciones = _datos()
        return _vista_tablero(estudiantes, evaluaciones, origen="Datos de fábrica")
    except Exception as error:  # se muestra el error en pantalla, en lenguaje sencillo
        return render_template("error.html", error=error, motor=datos.nombre_motor()), 500


@rutas.route("/cargar", methods=["GET", "POST"])
@requiere_login
@solo_admin
def cargar():
    """Panel del administrador: procesa los dos Excel EN MEMORIA y recalcula.

    No guarda los archivos ni los resultados: al recargar la app se vuelve a
    los datos de fábrica, porque todavía no hay una base para estas subidas.
    """
    # Si entran por el enlace del menú, los mandamos al panel del tablero.
    if request.method == "GET":
        return redirect(url_for("rutas.tablero") + "#panel-admin")

    maestro = request.files.get("maestro")
    evaluaciones = request.files.get("evaluaciones")
    accion = request.form.get("accion", "ver")

    # 1) Validar que llegaron los dos archivos.
    if (not maestro or not maestro.filename or
            not evaluaciones or not evaluaciones.filename):
        flash("Faltó un archivo: elija el Maestro de estudiantes y el Registro de evaluaciones.", "error")
        return redirect(url_for("rutas.tablero") + "#panel-admin")

    # 2) Validar que sean Excel .xlsx (es el formato que sabe leer la app).
    for archivo, etiqueta in ((maestro, "Maestro de estudiantes"),
                              (evaluaciones, "Registro de evaluaciones")):
        if not archivo.filename.lower().endswith(".xlsx"):
            flash(f"El archivo de {etiqueta} debe ser un Excel con extensión .xlsx.", "error")
            return redirect(url_for("rutas.tablero") + "#panel-admin")

    # 3) Leer los dos archivos EN MEMORIA. Nunca se guardan en el disco.
    #
    # BytesIO es como una hoja de papel que llevamos en la mano: la leemos y
    # la pasamos a la siguiente persona sin archivarla en un cajón (el disco).
    # Así funciona en Vercel, donde el disco es de solo lectura.
    try:
        memoria_maestro = io.BytesIO(maestro.read())
        memoria_evaluaciones = io.BytesIO(evaluaciones.read())
        estudiantes, filas = carga_excel.datos_desde_excel(
            memoria_maestro, memoria_evaluaciones
        )
        # Reutilizamos la misma función de siempre para calcular todo.
        resultados, _contadores, inconsistencias = certificados.calcular_resultados(
            estudiantes, filas
        )
    except Exception:
        flash("No pudimos leer los archivos. Revise que sean Excel .xlsx válidos "
              "y que tengan las columnas correctas.", "error")
        return redirect(url_for("rutas.tablero") + "#panel-admin")

    origen = f"Archivos subidos: {maestro.filename} y {evaluaciones.filename}"

    # 4) Según el botón: mostrar en pantalla o devolver un Excel en memoria.
    if accion == "descargar":
        memoria_excel = exportador_excel.crear_excel(resultados, inconsistencias)
        return send_file(
            memoria_excel,
            mimetype=EXCEL_MIME,
            as_attachment=True,
            download_name="Resultados_datos_subidos.xlsx",
        )

    return _vista_tablero(estudiantes, filas, origen=origen, datos_subidos=True)


@rutas.route("/descargar-resultados")
@requiere_login
@solo_admin
def descargar_resultados():
    """Descarga en Excel los resultados de los datos de fábrica."""
    try:
        resultados, _contadores, inconsistencias = _resultados()
        memoria_excel = exportador_excel.crear_excel(resultados, inconsistencias)
    except Exception:
        flash("No se pudieron preparar los resultados de fábrica. Intente de nuevo.", "error")
        return redirect(url_for("rutas.tablero"))
    return send_file(
        memoria_excel,
        mimetype=EXCEL_MIME,
        as_attachment=True,
        download_name="Resultados_datos_fabrica.xlsx",
    )


def _normalizar(texto):
    """Quita espacios sobrantes y unifica la forma del texto para comparar.
    También sirve si un dato viene como número en vez de texto."""
    return " ".join(str(texto or "").split()).strip()


def _enviar_certificado(identificacion, programa):
    """Busca el resultado del estudiante y devuelve el PDF en memoria."""
    identificacion = _normalizar(identificacion)
    programa = _normalizar(unquote(programa or ""))

    resultados, _c, _i = _resultados()
    for r in resultados:
        if (_normalizar(r["identificacion"]) == identificacion and
                _normalizar(r["programa"]) == programa):
            if not certificados.lleva_certificado(r):
                abort(404)
            return send_file(io.BytesIO(generador_pdf.crear_pdf(r)), mimetype="application/pdf",
                             download_name=generador_pdf.nombre_archivo(r))
    abort(404)


@rutas.route("/certificado")
@requiere_login
def certificado():
    """Ruta principal del certificado, con los datos en la cadena de consulta.
    Es la forma más confiable en Vercel: /certificado?identificacion=...&programa=...
    """
    return _enviar_certificado(
        request.args.get("identificacion", ""),
        request.args.get("programa", ""),
    )


@rutas.route("/certificado/<identificacion>/<path:programa>")
@requiere_login
def certificado_por_ruta(identificacion, programa):
    """Ruta antigua, se mantiene para que los enlaces viejos sigan funcionando."""
    return _enviar_certificado(identificacion, programa)


@rutas.route("/descargar-todos")
@requiere_login
@solo_admin
def descargar_todos():
    resultados, _c, _i = _resultados()
    con_certificado = [r for r in resultados if certificados.lleva_certificado(r)]
    return send_file(generador_pdf.crear_zip(con_certificado), mimetype="application/zip",
                     as_attachment=True, download_name="Certificados_Academia.zip")
