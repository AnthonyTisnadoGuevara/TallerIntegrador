import os
import tempfile
import requests
from docx import Document


def extraer_texto_docx_desde_url(url: str) -> str:
    """
    Descarga un archivo .docx desde una URL pública y extrae su texto.
    """
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_file:
        temp_file.write(response.content)
        temp_path = temp_file.name

    try:
        document = Document(temp_path)
        textos = []

        for paragraph in document.paragraphs:
            if paragraph.text.strip():
                textos.append(paragraph.text.strip())

        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        textos.append(cell.text.strip())

        return "\n".join(textos)

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def validar_secciones_silabo(texto: str) -> list[dict]:
    """
    Valida si el texto del sílabo contiene las secciones obligatorias.
    """
    texto_normalizado = texto.lower()

    secciones = [
        {
            "seccion": "Datos generales",
            "palabras_clave": ["datos generales", "facultad", "programa", "asignatura", "código"]
        },
        {
            "seccion": "Sumilla",
            "palabras_clave": ["sumilla"]
        },
        {
            "seccion": "Aporte al perfil de egreso",
            "palabras_clave": ["aporte de la asignatura", "perfil de egreso", "competencia"]
        },
        {
            "seccion": "Programación por unidades de aprendizaje",
            "palabras_clave": ["programación por unidades", "unidad", "semanas", "contenidos"]
        },
        {
            "seccion": "Estrategias metodológicas",
            "palabras_clave": ["estrategias metodológicas"]
        },
        {
            "seccion": "Recursos y escenarios de enseñanza-aprendizaje",
            "palabras_clave": ["recursos", "escenarios", "enseñanza", "aprendizaje"]
        },
        {
            "seccion": "Técnicas e instrumentos de evaluación",
            "palabras_clave": ["técnicas", "instrumentos de evaluación", "evaluación"]
        },
        {
            "seccion": "Estrategias de tutoría y apoyo pedagógico",
            "palabras_clave": ["tutoría", "apoyo pedagógico"]
        },
        {
            "seccion": "Bibliografía",
            "palabras_clave": ["bibliografía"]
        }
    ]

    resultados = []

    for item in secciones:
        cumple = any(palabra in texto_normalizado for palabra in item["palabras_clave"])

        resultados.append({
            "seccion": item["seccion"],
            "cumple": cumple,
            "observacion": "Sección identificada en el documento." if cumple else "No se identificó la sección en el documento."
        })

    return resultados