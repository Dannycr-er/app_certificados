"""
CAPA SERVICIOS · carga_excel.py
Lee los dos Excel (desde la carpeta insumos o desde un archivo subido) y los guarda en la base.
"""
from pathlib import Path

import pandas as pd

from models import datos

CARPETA_PROYECTO = Path(__file__).resolve().parent.parent

COLUMNAS_ESTUDIANTES = ["Identificacion", "Nombre_Completo", "Correo", "Programa", "Cohorte"]
COLUMNAS_EVALUACIONES = ["Identificacion", "Programa", "Modulo", "Nota", "Asistencia_Pct", "Fecha_Cierre"]


def carpeta_insumos():
    """Busca la carpeta insumos sin importar mayúsculas (insumos, Insumos, INSUMOS)."""
    for hijo in CARPETA_PROYECTO.iterdir():
        if hijo.is_dir() and hijo.name.lower() == "insumos":
            return hijo
    return CARPETA_PROYECTO / "insumos"


def _buscar(nombre):
    carpeta = carpeta_insumos()
    for archivo in carpeta.iterdir():
        if archivo.name.lower() == nombre.lower():
            return archivo
    raise FileNotFoundError(f"No encontré {nombre} en la carpeta {carpeta.name}")


def _leer(origen, columnas, nombre):
    tabla = pd.read_excel(origen, dtype={"Identificacion": str})
    faltan = [c for c in columnas if c not in tabla.columns]
    if faltan:
        raise ValueError(f"Al archivo {nombre} le faltan las columnas: {', '.join(faltan)}")
    tabla = tabla[columnas].copy()
    tabla["Identificacion"] = tabla["Identificacion"].astype(str).str.strip()
    return tabla


def leer_excel(origen_maestro=None, origen_evaluaciones=None):
    """Si no se entregan archivos, usa los de la carpeta insumos."""
    maestro = _leer(origen_maestro or _buscar("Maestro_Estudiantes.xlsx"),
                    COLUMNAS_ESTUDIANTES, "Maestro_Estudiantes")
    evaluaciones = _leer(origen_evaluaciones or _buscar("Registro_Evaluaciones.xlsx"),
                         COLUMNAS_EVALUACIONES, "Registro_Evaluaciones")
    return maestro, evaluaciones


_cache = {"clave": None, "datos": None}


def _convertir(maestro, evaluaciones):
    """Convierte las dos tablas de pandas en las listas de diccionarios que usan
    el resto de la app. Es el mismo formato venga de donde venga el Excel."""
    estudiantes = [
        {
            "identificacion": r.Identificacion,
            "nombre_completo": str(r.Nombre_Completo),
            "correo": str(r.Correo),
            "programa": str(r.Programa),
            "cohorte": str(r.Cohorte),
        }
        for r in maestro.itertuples(index=False)
    ]
    filas = [
        {
            "identificacion": r.Identificacion,
            "programa": str(r.Programa),
            "modulo": str(r.Modulo),
            "nota": float(r.Nota),
            "asistencia_pct": float(r.Asistencia_Pct),
            "fecha_cierre": str(r.Fecha_Cierre)[:10],
        }
        for r in evaluaciones.itertuples(index=False)
    ]
    return estudiantes, filas


def datos_desde_excel(origen_maestro=None, origen_evaluaciones=None):
    """Lee los Excel y devuelve (estudiantes, evaluaciones) sin pasar por ninguna base.

    - Sin archivos: lee los de la carpeta insumos y usa una caché para no
      leerlos en cada visita.
    - Con archivos: lee esos archivos (pueden ser BytesIO con lo que subió el
      administrador) y NO usa la caché, porque cada subida es distinta.
    """
    if origen_maestro is None and origen_evaluaciones is None:
        ruta_maestro = _buscar("Maestro_Estudiantes.xlsx")
        ruta_evaluaciones = _buscar("Registro_Evaluaciones.xlsx")
        clave = (ruta_maestro.stat().st_mtime, ruta_evaluaciones.stat().st_mtime)
        if _cache["clave"] == clave and _cache["datos"] is not None:
            return _cache["datos"]

        maestro, evaluaciones = leer_excel(ruta_maestro, ruta_evaluaciones)
        resultado = _convertir(maestro, evaluaciones)
        _cache.update(clave=clave, datos=resultado)
        return resultado

    # Si se pasan archivos, leer_excel los usa directamente; si falta uno,
    # completa con el de insumos (aunque la ruta /cargar exige los dos).
    maestro, evaluaciones = leer_excel(origen_maestro, origen_evaluaciones)
    return _convertir(maestro, evaluaciones)


def cargar_a_la_base(origen_maestro=None, origen_evaluaciones=None):
    maestro, evaluaciones = leer_excel(origen_maestro, origen_evaluaciones)
    filas_est = [
        (r.Identificacion, str(r.Nombre_Completo), str(r.Correo), str(r.Programa), str(r.Cohorte))
        for r in maestro.itertuples(index=False)
    ]
    filas_eva = [
        (r.Identificacion, str(r.Programa), str(r.Modulo), float(r.Nota),
         float(r.Asistencia_Pct), str(r.Fecha_Cierre)[:10])
        for r in evaluaciones.itertuples(index=False)
    ]
    datos.guardar_datos(filas_est, filas_eva)
    return len(filas_est), len(filas_eva)


def asegurar_datos():
    """Si la base está vacía (por ejemplo, la primera vez), carga los Excel de insumos."""
    n_est, n_eva = datos.contar_filas()
    if n_est == 0 and n_eva == 0:
        return cargar_a_la_base()
    return n_est, n_eva
