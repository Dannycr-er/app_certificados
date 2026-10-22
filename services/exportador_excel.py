"""
CAPA SERVICIOS · exportador_excel.py
Arma un archivo Excel con los resultados y lo devuelve EN MEMORIA.
No escribe en el disco: en Vercel el disco es de solo lectura.
"""
import io

import pandas as pd

COLUMNAS_RESULTADOS = [
    "Identificación",
    "Nombre completo",
    "Correo",
    "Programa",
    "Cohorte",
    "Módulos",
    "Promedio",
    "Asistencia (%)",
    "Certificado",
]

COLUMNAS_INCONSISTENCIAS = ["Identificación", "Nombre", "Motivo"]


def _hoja_resultados(resultados):
    """Convierte la lista de resultados en una tabla de pandas."""
    filas = [
        {
            "Identificación": r["identificacion"],
            "Nombre completo": r["nombre"],
            "Correo": r["correo"],
            "Programa": r["programa"],
            "Cohorte": r["cohorte"],
            "Módulos": r["modulos"],
            "Promedio": r["promedio"],
            "Asistencia (%)": r["asistencia"],
            "Certificado": r["tipo"],
        }
        for r in resultados
    ]
    # Se declaran las columnas para que el Excel tenga encabezados aunque no haya filas.
    return pd.DataFrame(filas, columns=COLUMNAS_RESULTADOS)


def _hoja_inconsistencias(inconsistencias):
    """Convierte la lista de inconsistencias en una tabla de pandas."""
    filas = [
        {
            "Identificación": i["identificacion"],
            "Nombre": i["nombre"],
            "Motivo": i["motivo"],
        }
        for i in inconsistencias
    ]
    return pd.DataFrame(filas, columns=COLUMNAS_INCONSISTENCIAS)


def crear_excel(resultados, inconsistencias=None):
    """Devuelve un BytesIO con el Excel listo para enviar al navegador.

    BytesIO es como una hoja de papel que llevamos en la mano: la escribimos y
    la entregamos directamente, sin guardarla en ningún cajón (el disco).
    """
    memoria = io.BytesIO()
    with pd.ExcelWriter(memoria, engine="openpyxl") as escritor:
        _hoja_resultados(resultados).to_excel(
            escritor, index=False, sheet_name="Resultados"
        )
        _hoja_inconsistencias(inconsistencias or []).to_excel(
            escritor, index=False, sheet_name="Inconsistencias"
        )
    memoria.seek(0)  # vuelve al inicio para que send_file lo lea desde el principio
    return memoria
