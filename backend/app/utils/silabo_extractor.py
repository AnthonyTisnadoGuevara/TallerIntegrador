import re
import unicodedata
from datetime import datetime
from typing import Optional


def _normalizar_texto(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto or "")
    texto = "".join(caracter for caracter in texto if unicodedata.category(caracter) != "Mn")
    return texto


def _limpiar_valor(valor: Optional[str]) -> Optional[str]:
    if valor is None:
        return None
    valor = re.sub(r"\s+", " ", valor).strip(" \t\r\n:-|")
    return valor or None


def _buscar_campo(texto: str, etiquetas: list[str], max_len: int = 120) -> Optional[str]:
    etiquetas_regex = "|".join(re.escape(etiqueta) for etiqueta in etiquetas)
    patron = re.compile(
        rf"(?im)^\s*(?:{etiquetas_regex})\s*[:\-|]?\s*(.+?)\s*$"
    )
    for match in patron.finditer(texto):
        valor = _limpiar_valor(match.group(1))
        if valor and len(valor) <= max_len:
            return valor
    return None


def _normalizar_entero(valor: Optional[str], minimo: int = 0, maximo: Optional[int] = None) -> Optional[int]:
    if not valor:
        return None
    match = re.search(r"-?\d+", str(valor))
    if not match:
        return None
    numero = int(match.group(0))
    if numero < minimo:
        return None
    if maximo is not None and numero > maximo:
        return None
    return numero


def _normalizar_ciclo(valor: Optional[str]) -> Optional[int]:
    if not valor:
        return None

    numero = _normalizar_entero(valor, minimo=1, maximo=10)
    if numero is not None:
        return numero

    romanos = {
        "I": 1,
        "II": 2,
        "III": 3,
        "IV": 4,
        "V": 5,
        "VI": 6,
        "VII": 7,
        "VIII": 8,
        "IX": 9,
        "X": 10,
    }
    valor_limpio = _normalizar_texto(valor).upper()
    match = re.search(r"\b(I|II|III|IV|V|VI|VII|VIII|IX|X)\b", valor_limpio)
    if match:
        return romanos.get(match.group(1))
    return None


def _normalizar_fecha(valor: Optional[str]) -> Optional[str]:
    if not valor:
        return None

    patrones = [
        r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b",
        r"\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b",
    ]

    for indice, patron in enumerate(patrones):
        match = re.search(patron, valor)
        if not match:
            continue

        try:
            if indice == 0:
                dia, mes, anio = match.groups()
                anio = f"20{anio}" if len(anio) == 2 else anio
            else:
                anio, mes, dia = match.groups()
            fecha = datetime(int(anio), int(mes), int(dia))
            return fecha.strftime("%Y-%m-%d")
        except ValueError:
            return None

    return None


def _buscar_codigo_asignatura(texto: str) -> Optional[str]:
    patrones = [
        r"\b[A-Z]{2,5}[A-Z0-9]*-\d{2,4}[A-Z]?\b",
        r"\bC\d{2}-[A-Z0-9]{1,6}\b",
    ]
    texto_mayus = _normalizar_texto(texto).upper()
    for patron in patrones:
        match = re.search(patron, texto_mayus)
        if match:
            return match.group(0)
    return None


def extraer_datos_silabo_desde_texto(texto: str) -> dict:
    texto = texto or ""
    texto_sin_acentos = _normalizar_texto(texto)

    asignatura = _buscar_campo(
        texto_sin_acentos,
        ["asignatura", "curso", "nombre de la asignatura", "nombre del curso"],
    )
    codigo_asignatura = _buscar_campo(
        texto_sin_acentos,
        ["codigo", "codigo de asignatura", "codigo del curso", "codigo de curso"],
        max_len=40,
    )
    codigo_detectado = _buscar_codigo_asignatura(codigo_asignatura or texto_sin_acentos)

    ciclo = _normalizar_ciclo(
        _buscar_campo(texto_sin_acentos, ["ciclo", "semestre"], max_len=40)
    )
    modalidad = _buscar_campo(texto_sin_acentos, ["modalidad"], max_len=60)
    creditos = _normalizar_entero(
        _buscar_campo(texto_sin_acentos, ["creditos", "numero de creditos"], max_len=40),
        minimo=0,
    )
    total_horas_semestrales = _normalizar_entero(
        _buscar_campo(texto_sin_acentos, ["total horas semestrales", "horas semestrales"], max_len=40),
        minimo=0,
    )
    total_horas_semanales = _normalizar_entero(
        _buscar_campo(texto_sin_acentos, ["total horas semanales", "horas semanales"], max_len=40),
        minimo=0,
    )
    duracion_semanas = _normalizar_entero(
        _buscar_campo(texto_sin_acentos, ["duracion", "duracion en semanas", "semanas"], max_len=50),
        minimo=1,
    )

    fecha_inicio = _normalizar_fecha(
        _buscar_campo(texto_sin_acentos, ["fecha inicio", "fecha de inicio", "inicio"], max_len=80)
    )
    fecha_culminacion = _normalizar_fecha(
        _buscar_campo(
            texto_sin_acentos,
            ["fecha culminacion", "fecha de culminacion", "fecha fin", "fecha de termino", "termino"],
            max_len=80,
        )
    )

    if not fecha_inicio or not fecha_culminacion:
        fechas = []
        for patron in (r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b"):
            fechas.extend(re.findall(patron, texto_sin_acentos))
        fechas_normalizadas = [_normalizar_fecha(fecha) for fecha in fechas]
        fechas_normalizadas = [fecha for fecha in fechas_normalizadas if fecha]
        if not fecha_inicio and fechas_normalizadas:
            fecha_inicio = fechas_normalizadas[0]
        if not fecha_culminacion and len(fechas_normalizadas) > 1:
            fecha_culminacion = fechas_normalizadas[1]

    correo_match = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", texto, re.IGNORECASE)
    correo_docente = correo_match.group(0) if correo_match else None

    docente_responsable = _buscar_campo(
        texto_sin_acentos,
        ["docente responsable", "docente", "profesor", "responsable de la asignatura"],
        max_len=120,
    )
    if docente_responsable and correo_docente:
        docente_responsable = _limpiar_valor(docente_responsable.replace(correo_docente, ""))

    return {
        "asignatura": asignatura,
        "codigo_asignatura": codigo_detectado,
        "ciclo": ciclo,
        "modalidad": modalidad,
        "creditos": creditos,
        "total_horas_semestrales": total_horas_semestrales,
        "total_horas_semanales": total_horas_semanales,
        "fecha_inicio": fecha_inicio,
        "fecha_culminacion": fecha_culminacion,
        "duracion_semanas": duracion_semanas,
        "docente_responsable": docente_responsable,
        "correo_docente": correo_docente,
    }
