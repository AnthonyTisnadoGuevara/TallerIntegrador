from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side


COLOR_DARK = "1E3A8A"
COLOR_BLUE = "DBEAFE"
COLOR_GREEN = "DCFCE7"
COLOR_RED = "FEE2E2"
COLOR_YELLOW = "FEF3C7"
COLOR_PURPLE = "EDE9FE"
COLOR_GRAY = "F8FAFC"
COLOR_BORDER = "CBD5E1"


def valor_excel(valor: Any) -> Any:
    if isinstance(valor, (dict, list)):
        return str(valor)
    if valor is None:
        return ""
    return valor


def aplicar_estilo_titulo(ws, rango: str, texto: str) -> None:
    ws.merge_cells(rango)
    celda = ws[rango.split(":")[0]]
    celda.value = texto
    celda.fill = PatternFill("solid", fgColor=COLOR_DARK)
    celda.font = Font(bold=True, color="FFFFFF", size=16)
    celda.alignment = Alignment(horizontal="center", vertical="center")


def aplicar_estilo_tabla(ws, min_row: int, max_row: int, min_col: int, max_col: int) -> None:
    border = Border(
        left=Side(style="thin", color=COLOR_BORDER),
        right=Side(style="thin", color=COLOR_BORDER),
        top=Side(style="thin", color=COLOR_BORDER),
        bottom=Side(style="thin", color=COLOR_BORDER),
    )

    for row in ws.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col):
        for cell in row:
            cell.border = border
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    for cell in ws[min_row]:
        cell.fill = PatternFill("solid", fgColor=COLOR_DARK)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def ajustar_ancho_columnas(ws) -> None:
    for idx, column_cells in enumerate(ws.columns, start=1):
        max_length = max(
            len(str(cell.value)) if cell.value is not None else 0
            for cell in column_cells
        )
        ws.column_dimensions[get_column_letter(idx)].width = min(max(max_length + 2, 14), 58)


def colorear_estado(cell) -> None:
    estado = str(cell.value or "").lower()
    if estado in {"completo", "completado", "atendida", "verde"}:
        cell.fill = PatternFill("solid", fgColor=COLOR_GREEN)
    elif estado in {"pendiente", "incompleto", "rojo", "activa"}:
        cell.fill = PatternFill("solid", fgColor=COLOR_RED)
    elif estado in {"observado", "en_proceso", "amarillo"}:
        cell.fill = PatternFill("solid", fgColor=COLOR_YELLOW)


def colorear_prioridad(cell) -> None:
    prioridad = str(cell.value or "").lower()
    if prioridad in {"alta", "critica", "crítica"}:
        cell.fill = PatternFill("solid", fgColor=COLOR_RED)
    elif prioridad == "media":
        cell.fill = PatternFill("solid", fgColor=COLOR_YELLOW)
    elif prioridad == "baja":
        cell.fill = PatternFill("solid", fgColor=COLOR_GREEN)


def agregar_filtros_y_congelar(ws, min_row: int = 1) -> None:
    ws.freeze_panes = f"A{min_row + 1}"
    ws.auto_filter.ref = ws.dimensions


def crear_hoja_sin_datos(ws, mensaje: str) -> None:
    ws.append([mensaje])
    ws["A1"].font = Font(italic=True, color="64748B")


def agregar_tabla(ws, encabezados: list[str], filas: list[list[Any]], sin_datos: str = "Sin datos disponibles") -> None:
    ws.append(encabezados)
    if filas:
        for fila in filas:
            ws.append([valor_excel(valor) for valor in fila])
    else:
        ws.append([sin_datos] + [""] * (len(encabezados) - 1))

    aplicar_estilo_tabla(ws, 1, ws.max_row, 1, len(encabezados))
    agregar_filtros_y_congelar(ws)
    ajustar_ancho_columnas(ws)


def agregar_kpi(ws, fila: int, columna: int, titulo: str, valor: Any, color: str) -> None:
    ws.cell(fila, columna, titulo)
    ws.cell(fila + 1, columna, valor_excel(valor))
    for cell in (ws.cell(fila, columna), ws.cell(fila + 1, columna)):
        cell.fill = PatternFill("solid", fgColor=color)
        cell.border = Border(
            left=Side(style="thin", color=COLOR_BORDER),
            right=Side(style="thin", color=COLOR_BORDER),
            top=Side(style="thin", color=COLOR_BORDER),
            bottom=Side(style="thin", color=COLOR_BORDER),
        )
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.cell(fila, columna).font = Font(bold=True, color="0F172A")
    ws.cell(fila + 1, columna).font = Font(bold=True, color="0F172A", size=14)


def agregar_grafico_barras(ws, datos: list[tuple[str, int]], titulo: str, posicion: str) -> None:
    if not datos:
        return
    start_row = ws.max_row + 2
    ws.cell(start_row, 1, "Indicador")
    ws.cell(start_row, 2, "Valor")
    for idx, (label, value) in enumerate(datos, start=start_row + 1):
        ws.cell(idx, 1, label)
        ws.cell(idx, 2, int(value or 0))

    chart = BarChart()
    chart.title = titulo
    chart.y_axis.title = "Valor"
    chart.x_axis.title = "Indicador"
    data_ref = Reference(ws, min_col=2, min_row=start_row, max_row=start_row + len(datos))
    cats_ref = Reference(ws, min_col=1, min_row=start_row + 1, max_row=start_row + len(datos))
    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats_ref)
    chart.height = 7
    chart.width = 12
    ws.add_chart(chart, posicion)


def agregar_grafico_pastel(ws, datos: list[tuple[str, int]], titulo: str, posicion: str) -> None:
    if not datos:
        return
    start_row = ws.max_row + 2
    ws.cell(start_row, 1, "Categoría")
    ws.cell(start_row, 2, "Valor")
    for idx, (label, value) in enumerate(datos, start=start_row + 1):
        ws.cell(idx, 1, label)
        ws.cell(idx, 2, int(value or 0))

    chart = PieChart()
    chart.title = titulo
    data_ref = Reference(ws, min_col=2, min_row=start_row, max_row=start_row + len(datos))
    labels_ref = Reference(ws, min_col=1, min_row=start_row + 1, max_row=start_row + len(datos))
    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(labels_ref)
    chart.height = 7
    chart.width = 10
    ws.add_chart(chart, posicion)


def aplicar_colores_por_encabezado(ws) -> None:
    encabezados = {cell.value: cell.column for cell in ws[1]}
    for nombre in ("Estado", "Color"):
        col = encabezados.get(nombre)
        if col:
            for column in ws.iter_cols(min_col=col, max_col=col, min_row=2, max_row=ws.max_row):
                for cell in column:
                    colorear_estado(cell)
    for nombre in ("Prioridad", "Nivel"):
        col = encabezados.get(nombre)
        if col:
            for column in ws.iter_cols(min_col=col, max_col=col, min_row=2, max_row=ws.max_row):
                for cell in column:
                    colorear_prioridad(cell)


def crear_reporte_silabos_excel(
    resumen: dict,
    silabos: list[dict],
    analisis: list[dict],
    trazabilidad: list[dict],
    brechas: list[dict],
    acciones: list[dict],
) -> BytesIO:
    wb = Workbook()
    wb.remove(wb.active)

    ws = wb.create_sheet("Resumen Ejecutivo")
    aplicar_estilo_titulo(ws, "A1:I1", "REPORTE DE GESTIÓN DE SÍLABOS")
    ws["A2"] = "Sistema de Monitoreo del Plan de Mejora Continua - ISIA"
    ws["A3"] = f"Fecha de generación: {resumen.get('fecha_generacion', '')}"
    ws["A2"].font = Font(bold=True, color="334155")
    kpis = [
        ("Total de sílabos", resumen.get("total_silabos"), COLOR_BLUE),
        ("Completos", resumen.get("silabos_completos"), COLOR_GREEN),
        ("Incompletos", resumen.get("silabos_incompletos"), COLOR_RED),
        ("Observados", resumen.get("silabos_observados"), COLOR_YELLOW),
        ("Pendientes", resumen.get("silabos_pendientes"), COLOR_RED),
        ("Cumplimiento", f"{resumen.get('cumplimiento_promedio', 0)}%", COLOR_GREEN),
        ("Análisis IA", resumen.get("total_analisis_ia"), COLOR_PURPLE),
        ("Brechas", resumen.get("total_brechas_curriculares"), COLOR_YELLOW),
        ("Acciones", resumen.get("total_acciones_mejora"), COLOR_BLUE),
    ]
    for idx, (titulo, valor, color) in enumerate(kpis, start=1):
        agregar_kpi(ws, 5, idx, titulo, valor, color)
    ajustar_ancho_columnas(ws)

    ws_silabos = wb.create_sheet("Sílabos")
    agregar_tabla(
        ws_silabos,
        ["ID", "Semestre académico", "Facultad", "Programa de estudios", "Asignatura", "Código", "Ciclo", "Modalidad", "Créditos", "Horas semestrales", "Horas semanales", "Docente", "Correo", "Estado", "Porcentaje de cumplimiento", "Observación", "Archivo URL", "Fecha de registro", "Fecha de actualización"],
        [[item.get("id"), item.get("semestre_academico"), item.get("facultad"), item.get("programa_estudios"), item.get("asignatura"), item.get("codigo_asignatura"), item.get("ciclo"), item.get("modalidad"), item.get("creditos"), item.get("total_horas_semestrales"), item.get("total_horas_semanales"), item.get("docente_responsable"), item.get("correo_docente"), item.get("estado"), item.get("porcentaje_cumplimiento"), item.get("observacion_general"), item.get("archivo_url"), item.get("created_at"), item.get("updated_at")] for item in silabos],
    )
    aplicar_colores_por_encabezado(ws_silabos)

    ws_analisis = wb.create_sheet("Análisis IA")
    agregar_tabla(
        ws_analisis,
        ["ID", "Sílabo ID", "Asignatura", "Modelo usado", "Nivel de cumplimiento", "Resumen", "Recomendaciones", "Fecha de análisis"],
        [[item.get("id"), item.get("silabo_id"), item.get("asignatura"), item.get("modelo_usado"), item.get("nivel_cumplimiento") or item.get("nivel_riesgo"), item.get("resumen"), item.get("recomendaciones") or item.get("sugerencias"), item.get("created_at")] for item in analisis],
        "Sin análisis IA registrados.",
    )

    ws_traz = wb.create_sheet("Trazabilidad Curricular")
    agregar_tabla(
        ws_traz,
        ["ID", "Curso origen", "Curso destino", "Ciclo origen", "Ciclo destino", "Tipo de relación", "Nivel de coherencia", "Observación", "Recomendación", "Fecha"],
        [[item.get("id"), item.get("asignatura_origen") or item.get("curso_origen"), item.get("asignatura_destino") or item.get("curso_destino"), item.get("ciclo_origen"), item.get("ciclo_destino"), item.get("tipo_relacion"), item.get("nivel_coherencia"), item.get("observacion"), item.get("sugerencia") or item.get("recomendacion"), item.get("created_at")] for item in trazabilidad],
        "Sin trazabilidad curricular registrada.",
    )

    ws_brechas = wb.create_sheet("Brechas Curriculares")
    agregar_tabla(
        ws_brechas,
        ["ID", "Tipo de brecha", "Descripción", "Prioridad", "Curso relacionado", "Ciclo", "Recomendación", "Estado", "Fecha"],
        [[item.get("id"), item.get("tipo_brecha"), item.get("descripcion"), item.get("prioridad"), item.get("asignatura") or item.get("curso_relacionado"), item.get("ciclo"), item.get("recomendacion"), item.get("estado"), item.get("created_at")] for item in brechas],
    )
    aplicar_colores_por_encabezado(ws_brechas)

    ws_acciones = wb.create_sheet("Acciones de Mejora")
    agregar_tabla(
        ws_acciones,
        ["ID", "Título", "Descripción", "Prioridad", "Estado", "Responsable", "Origen", "Fecha programada", "Fecha de creación"],
        [[item.get("id"), item.get("titulo"), item.get("descripcion"), item.get("prioridad"), item.get("estado"), item.get("responsable"), item.get("origen_tipo"), item.get("fecha_limite") or item.get("fecha_programada"), item.get("created_at")] for item in acciones],
    )
    aplicar_colores_por_encabezado(ws_acciones)

    ws_graficos = wb.create_sheet("Gráficos")
    aplicar_estilo_titulo(ws_graficos, "A1:H1", "GRÁFICOS DEL REPORTE DE SÍLABOS")
    agregar_grafico_pastel(ws_graficos, [("Completos", resumen.get("silabos_completos", 0)), ("Pendientes", resumen.get("silabos_pendientes", 0)), ("Observados", resumen.get("silabos_observados", 0)), ("Incompletos", resumen.get("silabos_incompletos", 0))], "Distribución de sílabos por estado", "A4")
    agregar_grafico_barras(ws_graficos, [("Total de sílabos", resumen.get("total_silabos", 0)), ("Análisis IA", resumen.get("total_analisis_ia", 0)), ("Brechas curriculares", resumen.get("total_brechas_curriculares", 0)), ("Acciones de mejora", resumen.get("total_acciones_mejora", 0))], "Indicadores principales", "L4")
    acciones_estado = {
        "Pendientes": sum(1 for item in acciones if item.get("estado") == "pendiente"),
        "En proceso": sum(1 for item in acciones if item.get("estado") == "en_proceso"),
        "Completadas": sum(1 for item in acciones if item.get("estado") in {"atendida", "completada", "completado"}),
    }
    agregar_grafico_barras(ws_graficos, list(acciones_estado.items()), "Acciones de mejora por estado", "A22")

    archivo = BytesIO()
    wb.save(archivo)
    archivo.seek(0)
    return archivo


def crear_reporte_integral_excel(reporte: dict, metricas: dict) -> BytesIO:
    wb = Workbook()
    wb.remove(wb.active)
    resumen = reporte.get("resumen", {})
    metricas_data = metricas.get("data", metricas)

    ws = wb.create_sheet("Resumen Ejecutivo")
    aplicar_estilo_titulo(ws, "A1:I1", "REPORTE INTEGRAL DE MEJORA CONTINUA")
    ws["A2"] = "Sistema de Monitoreo del Plan de Mejora Continua - ISIA"
    ws["A3"] = f"Fecha de generación: {reporte.get('fecha_generacion', '')}"
    kpis = [
        ("Macroprocesos", resumen.get("total_macroprocesos"), COLOR_BLUE),
        ("Evidencias", resumen.get("total_evidencias"), COLOR_BLUE),
        ("Alertas activas", resumen.get("total_alertas_activas"), COLOR_YELLOW),
        ("Alertas críticas", resumen.get("total_alertas_criticas"), COLOR_RED),
        ("Acciones", resumen.get("total_acciones_mejora"), COLOR_BLUE),
        ("Pendientes", resumen.get("acciones_pendientes"), COLOR_YELLOW),
        ("Análisis IA", resumen.get("total_analisis_ia"), COLOR_PURPLE),
        ("Validaciones IA", resumen.get("total_validaciones_ia"), COLOR_PURPLE),
    ]
    for idx, (titulo, valor, color) in enumerate(kpis, start=1):
        agregar_kpi(ws, 5, idx, titulo, valor, color)
    ajustar_ancho_columnas(ws)

    hojas = [
        ("Semáforo", ["Macroproceso", "Color", "Avance", "Alertas activas", "Nivel de riesgo", "Estado"], [[item.get("macroproceso"), item.get("color"), item.get("avance_promedio"), item.get("alertas_activas"), item.get("nivel_riesgo"), item.get("estado")] for item in reporte.get("semaforo", [])]),
        ("Evidencias", ["Macroproceso", "Código", "Título", "Responsable", "Estado", "Prioridad", "Avance", "Archivo", "Observación"], [[item.get("macroproceso"), item.get("codigo"), item.get("titulo"), item.get("responsable"), item.get("estado"), item.get("prioridad"), item.get("avance"), item.get("archivo_url"), item.get("observacion")] for item in reporte.get("evidencias", reporte.get("evidencias_criticas", []))]),
        ("Alertas", ["Macroproceso", "Código", "Título", "Nivel", "Estado", "Descripción", "Recomendación"], [[item.get("macroproceso"), item.get("codigo"), item.get("titulo"), item.get("nivel_alerta"), item.get("estado"), item.get("descripcion"), item.get("recomendacion")] for item in reporte.get("alertas_activas", [])]),
        ("Acciones", ["Macroproceso", "Título", "Prioridad", "Estado", "Responsable", "Origen", "Descripción", "Recomendación"], [[item.get("macroproceso"), item.get("titulo"), item.get("prioridad"), item.get("estado"), item.get("responsable"), item.get("origen_tipo"), item.get("descripcion"), item.get("recomendacion")] for item in reporte.get("acciones_mejora", [])]),
        ("Análisis IA", ["Macroproceso", "Tipo", "Nivel de riesgo", "Resumen", "Modelo", "Fecha"], [[item.get("macroproceso"), item.get("tipo_analisis"), item.get("nivel_riesgo"), item.get("resumen"), item.get("modelo_usado"), item.get("created_at")] for item in reporte.get("ultimos_analisis_ia", [])]),
        ("Validaciones", ["Macroproceso", "Evidencia ID", "Nivel", "Pertinencia", "Resumen", "Acción sugerida", "Modelo", "Fecha"], [[item.get("macroproceso"), item.get("evidencia_id"), item.get("nivel_validez"), item.get("pertinencia"), item.get("resumen"), item.get("accion_sugerida"), item.get("modelo_usado"), item.get("created_at")] for item in reporte.get("validaciones_documentales", [])]),
        ("Métricas Finales", ["Indicador", "Valor", "Interpretación"], [[item.get("indicador"), item.get("valor"), item.get("interpretacion")] for item in metricas_data.get("indicadores_clave", [])]),
    ]
    for titulo, encabezados, filas in hojas:
        ws_tabla = wb.create_sheet(titulo)
        agregar_tabla(ws_tabla, encabezados, filas)
        aplicar_colores_por_encabezado(ws_tabla)

    ws_graficos = wb.create_sheet("Gráficos")
    aplicar_estilo_titulo(ws_graficos, "A1:H1", "GRÁFICOS DEL REPORTE INTEGRAL")
    semaforo = reporte.get("semaforo", [])
    agregar_grafico_barras(ws_graficos, [(item.get("macroproceso") or "-", item.get("avance_promedio") or 0) for item in semaforo], "Semáforo por macroproceso", "A4")
    evidencias = reporte.get("evidencias", reporte.get("evidencias_criticas", []))
    estados_evidencias = {estado: sum(1 for item in evidencias if item.get("estado") == estado) for estado in ["pendiente", "en_proceso", "completado", "observado"]}
    agregar_grafico_pastel(ws_graficos, list(estados_evidencias.items()), "Evidencias por estado", "L4")
    alertas = reporte.get("alertas_activas", [])
    alertas_nivel = {nivel: sum(1 for item in alertas if item.get("nivel_alerta") == nivel) for nivel in ["critica", "alta", "media", "baja"]}
    agregar_grafico_barras(ws_graficos, list(alertas_nivel.items()), "Alertas por nivel", "A22")
    acciones = reporte.get("acciones_mejora", [])
    acciones_estado = {estado: sum(1 for item in acciones if item.get("estado") == estado) for estado in ["pendiente", "en_proceso", "atendida", "descartada"]}
    agregar_grafico_barras(ws_graficos, list(acciones_estado.items()), "Acciones por estado", "L22")
    metricas_ia = metricas_data.get("metricas_ia", {})
    agregar_grafico_barras(ws_graficos, [("Análisis IA", metricas_ia.get("analisis_ia_ejecutados", resumen.get("total_analisis_ia", 0))), ("Validaciones IA", metricas_ia.get("validaciones_documentales_ia", resumen.get("total_validaciones_ia", 0)))], "Uso de IA", "A40")

    archivo = BytesIO()
    wb.save(archivo)
    archivo.seek(0)
    return archivo
