const API_URL = "http://127.0.0.1:8000";
let silabosGlobal = [];
let paginaActual = 1;
const SILABOS_POR_PAGINA = 10;

document.addEventListener("DOMContentLoaded", () => {
  cargarDatos();

  const form = document.getElementById("formSilabo");
  form.addEventListener("submit", registrarSilabo);
});

document.addEventListener("click", function(event) {
  if (!event.target.closest(".acciones-dropdown")) {
    document.querySelectorAll(".acciones-menu").forEach((menu) => {
      menu.classList.add("hidden");
      menu.classList.remove("open-up");
    });
  }
});

async function cargarDatos() {
  await cargarDashboard();
  await cargarSilabos();
}

function normalizarEnlaceArchivo(enlace) {
  if (typeof enlace !== "string" || !enlace.trim()) return "";

  try {
    const url = new URL(enlace.trim());
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch (error) {
    return "";
  }
}

async function cargarDashboard() {
  try {
    const response = await fetch(`${API_URL}/api/dashboard/silabos`);
    if (!response.ok) {
      throw new Error("No se pudo obtener el dashboard");
    }

    let result = await response.json();
    if (Array.isArray(result)) {
      result = result[0] ?? {};
    }

    let data = result.data ?? result;
    if (Array.isArray(data)) {
      data = data[0] ?? {};
    }

    document.getElementById("totalSilabos").textContent = data.total_silabos ?? 0;
    document.getElementById("silabosCompletos").textContent = data.silabos_completos ?? 0;
    document.getElementById("silabosObservados").textContent = data.silabos_observados ?? 0;
    document.getElementById("silabosPendientes").textContent = data.silabos_pendientes ?? 0;
    document.getElementById("cumplimientoPromedio").textContent = `${data.cumplimiento_promedio ?? 0}%`;
  } catch (error) {
    console.error("Error al cargar dashboard:", error);
  }
}

async function cargarSilabos() {
  const tbody = document.getElementById("tablaSilabos");
  const paginacion = document.getElementById("paginacionSilabos");

  try {
    const response = await fetch(`${API_URL}/api/silabos/`);
    if (!response.ok) {
      throw new Error("No se pudo obtener el listado de silabos");
    }

    const result = await response.json();
    silabosGlobal = Array.isArray(result.data) ? result.data : [];
    paginaActual = 1;
    renderizarTablaSilabos();
  } catch (error) {
    console.error("Error al cargar silabos:", error);
    tbody.innerHTML = `<tr><td colspan="7">Error al cargar datos. Revisa si el backend esta encendido.</td></tr>`;
    if (paginacion) paginacion.innerHTML = "";
  }
}

function renderizarTablaSilabos() {
  const tbody = document.getElementById("tablaSilabos");
  const paginacion = document.getElementById("paginacionSilabos");
  tbody.innerHTML = "";

  if (silabosGlobal.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7">No hay silabos registrados.</td></tr>`;
    if (paginacion) paginacion.innerHTML = "";
    return;
  }

  const totalPaginas = Math.ceil(silabosGlobal.length / SILABOS_POR_PAGINA);
  paginaActual = Math.min(Math.max(paginaActual, 1), totalPaginas);

  const inicio = (paginaActual - 1) * SILABOS_POR_PAGINA;
  const fin = Math.min(inicio + SILABOS_POR_PAGINA, silabosGlobal.length);
  const silabosPagina = silabosGlobal.slice(inicio, fin);

  silabosPagina.forEach((silabo) => {
    const tr = document.createElement("tr");
    const archivoUrl = normalizarEnlaceArchivo(silabo.archivo_url);
    const botonArchivo = archivoUrl
      ? `<a class="btn btn-primary archivo-btn" href="${archivoUrl}" target="_blank" rel="noopener noreferrer">Ver archivo</a>`
      : `<button class="btn btn-disabled" disabled>Sin archivo</button>`;

    tr.innerHTML = `
      <td>${silabo.ciclo}</td>
      <td>${silabo.codigo_asignatura}</td>
      <td>${silabo.asignatura}</td>
      <td><span class="estado ${silabo.estado}">${silabo.estado}</span></td>
      <td>${silabo.porcentaje_cumplimiento}%</td>
      <td>${archivoUrl ? "Disponible" : "Sin archivo"}</td>
      <td>
        <div class="acciones-compactas">
          ${botonArchivo}
          <button class="btn btn-success" onclick="analizarSilaboIA('${silabo.id}')">Analizar IA</button>
          <div class="acciones-dropdown">
            <button class="btn btn-secondary btn-actions" onclick="event.stopPropagation(); toggleMenuAcciones('${silabo.id}')">Acciones &#9662;</button>
            <div id="menu-acciones-${silabo.id}" class="acciones-menu hidden">
              <div class="menu-section">
                <span class="menu-label">Consulta</span>
                <button class="menu-item" onclick="verValidacion('${silabo.id}')">Ver validaci&oacute;n</button>
                <button class="menu-item" onclick="verHistorial('${silabo.id}')">Ver historial</button>
                <button class="menu-item" onclick="verAnalisisSilabo('${silabo.id}')">Ver an&aacute;lisis</button>
              </div>
              <div class="menu-divider"></div>
              <div class="menu-section">
                <span class="menu-label">Gesti&oacute;n</span>
                <button class="menu-item" onclick="validarDocumento('${silabo.id}')">Validar documento</button>
                <button class="menu-item" onclick="seleccionarArchivo('${silabo.id}')">Subir archivo</button>
                <button class="menu-item" onclick="cambiarEstado('${silabo.id}')">Cambiar estado</button>
                <button class="menu-item" onclick="editarSilabo('${silabo.id}')">Editar</button>
              </div>
              <div class="menu-divider"></div>
              <button class="menu-item menu-danger" onclick="eliminarSilabo('${silabo.id}')">Eliminar</button>
            </div>
          </div>
        </div>
      </td>
    `;

    tbody.appendChild(tr);
  });

  if (paginacion) {
    paginacion.innerHTML = `
      <span class="paginacion-info">Mostrando ${inicio + 1} - ${fin} de ${silabosGlobal.length} s&iacute;labos</span>
      <div class="paginacion-controles">
        <button class="btn btn-secondary" onclick="cambiarPaginaSilabos(${paginaActual - 1})" ${paginaActual === 1 ? "disabled" : ""}>Anterior</button>
        <span class="paginacion-info">P&aacute;gina ${paginaActual} de ${totalPaginas}</span>
        <button class="btn btn-secondary" onclick="cambiarPaginaSilabos(${paginaActual + 1})" ${paginaActual === totalPaginas ? "disabled" : ""}>Siguiente</button>
      </div>
    `;
  }
}

function cambiarPaginaSilabos(nuevaPagina) {
  const totalPaginas = Math.ceil(silabosGlobal.length / SILABOS_POR_PAGINA);
  if (nuevaPagina < 1 || nuevaPagina > totalPaginas) return;
  paginaActual = nuevaPagina;
  renderizarTablaSilabos();
}

function toggleMenuAcciones(id) {
  const menu = document.getElementById(`menu-acciones-${id}`);
  if (!menu) return;

  document.querySelectorAll(".acciones-menu").forEach((item) => {
    if (item !== menu) {
      item.classList.add("hidden");
      item.classList.remove("open-up");
    }
  });

  menu.classList.toggle("hidden");

  if (!menu.classList.contains("hidden")) {
    menu.classList.remove("open-up");
    const rect = menu.getBoundingClientRect();
    if (rect.bottom > window.innerHeight) {
      menu.classList.add("open-up");
    }
  } else {
    menu.classList.remove("open-up");
  }
}

async function registrarSilabo(event) {
  event.preventDefault();

  const data = {
    semestre_academico: document.getElementById("semestre").value,
    facultad: document.getElementById("facultad").value,
    programa_estudios: document.getElementById("programa").value,
    asignatura: document.getElementById("asignatura").value,
    codigo_asignatura: document.getElementById("codigo").value,
    ciclo: Number(document.getElementById("ciclo").value),
    modalidad: document.getElementById("modalidad").value,
    creditos: Number(document.getElementById("creditos").value) || null,
    total_horas_semestrales: Number(document.getElementById("horasSemestrales").value) || null,
    total_horas_semanales: Number(document.getElementById("horasSemanales").value) || null,
    fecha_inicio: document.getElementById("fechaInicio").value || null,
    fecha_culminacion: document.getElementById("fechaFin").value || null,
    duracion_semanas: Number(document.getElementById("duracion").value) || null,
    docente_responsable: document.getElementById("docente").value,
    correo_docente: document.getElementById("correo").value,
    estado: "pendiente",
    porcentaje_cumplimiento: 0,
    observacion_general: document.getElementById("observacion").value
  };

  try {
    const response = await fetch(`${API_URL}/api/silabos/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(data)
    });

    if (!response.ok) {
      throw new Error("Error al registrar el sílabo");
    }

    alert("Sílabo registrado correctamente");
    event.target.reset();
    await cargarDatos();
  } catch (error) {
    alert("No se pudo registrar el sílabo");
    console.error(error);
  }
}

async function verValidacion(id) {
  try {
    const response = await fetch(`${API_URL}/api/silabos/${id}/validacion`);
    const result = await response.json();

    const detalle = document.getElementById("detalleSilabo");

    let html = `
      <h3>${result.silabo.asignatura}</h3>
      <p><strong>Código:</strong> ${result.silabo.codigo_asignatura}</p>
      <p><strong>Estado:</strong> ${result.silabo.estado}</p>
      <p><strong>Cumplimiento:</strong> ${result.silabo.porcentaje_cumplimiento}%</p>
      <h4>Validación de secciones</h4>
      <ul>
    `;

    result.validacion.forEach((item) => {
      html += `
        <li>
          ${item.cumple ? "✅" : "❌"}
          <strong>${item.seccion}</strong>: ${item.observacion}
        </li>
      `;
    });

    html += `</ul>`;
    detalle.innerHTML = html;
  } catch (error) {
    console.error("Error al consultar validación:", error);
  }
}

async function verHistorial(id) {
  try {
    const response = await fetch(`${API_URL}/api/silabos/${id}/historial`);
    const result = await response.json();

    const detalle = document.getElementById("detalleSilabo");

    let html = `
      <h3>Historial: ${result.silabo.asignatura}</h3>
      <p><strong>Estado actual:</strong> ${result.silabo.estado_actual}</p>
      <ul>
    `;

    result.historial.forEach((item) => {
      html += `
        <li>
          <strong>${item.estado_anterior}</strong> → <strong>${item.estado_nuevo}</strong><br>
          ${item.observacion}<br>
          <small>${item.created_at}</small>
        </li>
      `;
    });

    html += `</ul>`;
    detalle.innerHTML = html;
  } catch (error) {
    console.error("Error al consultar historial:", error);
  }
}

async function validarDocumento(id) {
  try {
    const response = await fetch(`${API_URL}/api/silabos/${id}/validar-documento`, {
      method: "POST"
    });

    const result = await response.json();

    if (!response.ok) {
      alert(result.detail || "No se pudo validar el documento");
      return;
    }

    alert(`Documento validado. Cumplimiento: ${result.porcentaje_cumplimiento}%`);
    await cargarDatos();
    await verValidacion(id);
  } catch (error) {
    alert("Error al validar documento");
    console.error(error);
  }
}

async function eliminarSilabo(id) {
  const confirmar = confirm("¿Seguro que deseas eliminar este sílabo?");

  if (!confirmar) return;

  try {
    const response = await fetch(`${API_URL}/api/silabos/${id}`, {
      method: "DELETE"
    });

    if (!response.ok) {
      throw new Error("Error al eliminar el sílabo");
    }

    alert("Sílabo eliminado correctamente");
    await cargarDatos();
  } catch (error) {
    alert("No se pudo eliminar el sílabo");
    console.error(error);
  }
}
function seleccionarArchivo(id) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".pdf,.doc,.docx";

  input.onchange = async () => {
    const archivo = input.files[0];

    if (!archivo) return;

    await subirArchivoSilabo(id, archivo);
  };

  input.click();
}

async function subirArchivoSilabo(id, archivo) {
  const formData = new FormData();
  formData.append("archivo", archivo);

  try {
    const response = await fetch(`${API_URL}/api/silabos/${id}/archivo`, {
      method: "POST",
      body: formData
    });

    const result = await response.json();

    if (!response.ok) {
      alert(result.detail || "No se pudo subir el archivo");
      return;
    }

    alert("Archivo subido correctamente");
    await cargarDatos();
  } catch (error) {
    alert("Error al subir el archivo");
    console.error(error);
  }
}
let silaboIdEstadoActual = null;
let silaboIdEdicionActual = null;
let resolverConfirmacion = null;

function mostrarModal(modalId) {
  document.getElementById(modalId).classList.remove("hidden");
  document.body.classList.add("modal-open");
}

function ocultarModal(modalId) {
  document.getElementById(modalId).classList.add("hidden");
  document.body.classList.remove("modal-open");
}

function mostrarNotificacion(mensaje, tipo = "info") {
  let contenedor = document.getElementById("notificaciones");
  if (!contenedor) {
    contenedor = document.createElement("div");
    contenedor.id = "notificaciones";
    contenedor.className = "notificaciones";
    document.body.appendChild(contenedor);
  }

  const notificacion = document.createElement("div");
  notificacion.className = `notificacion notificacion-${tipo}`;
  notificacion.textContent = mensaje;
  contenedor.appendChild(notificacion);

  setTimeout(() => {
    notificacion.remove();
  }, 3500);
}

function mostrarToast(mensaje, tipo = "info") {
  mostrarNotificacion(mensaje, tipo);
}

function abrirModalConfirmacion({ titulo, mensaje, textoConfirmar = "Aceptar", tipo = "primary" }) {
  document.getElementById("confirmacionTitulo").textContent = titulo;
  document.getElementById("confirmacionMensaje").textContent = mensaje;

  const botonConfirmar = document.getElementById("confirmacionAceptar");
  botonConfirmar.textContent = textoConfirmar;
  botonConfirmar.className = `btn btn-${tipo}`;

  mostrarModal("modalConfirmacion");

  return new Promise((resolve) => {
    resolverConfirmacion = resolve;
  });
}

function cerrarModalConfirmacion(resultado = false) {
  ocultarModal("modalConfirmacion");

  if (resolverConfirmacion) {
    resolverConfirmacion(resultado);
    resolverConfirmacion = null;
  }
}

function cambiarEstado(id) {
  abrirModalCambioEstado(id);
}

function abrirModalCambioEstado(id) {
  silaboIdEstadoActual = id;
  document.getElementById("estadoNuevo").value = "pendiente";
  document.getElementById("estadoObservacion").value = "";
  mostrarModal("modalEstado");
}

function cerrarModalCambioEstado() {
  silaboIdEstadoActual = null;
  ocultarModal("modalEstado");
}

async function guardarCambioEstado() {
  if (!silaboIdEstadoActual) return;

  const id = silaboIdEstadoActual;
  const nuevoEstado = document.getElementById("estadoNuevo").value;
  const observacion = document.getElementById("estadoObservacion").value.trim();
  const estadosValidos = ["pendiente", "completo", "observado", "incompleto"];

  if (!estadosValidos.includes(nuevoEstado)) {
    alert("Estado inválido. Use: pendiente, completo, observado o incompleto.");
    return;
  }

  try {
    const response = await fetch(`${API_URL}/api/silabos/${id}/estado`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        estado: nuevoEstado,
        observacion_general: observacion || "Cambio de estado desde el frontend."
      })
    });

    const result = await response.json();
    if (!response.ok) {
      alert(result.detail || "No se pudo actualizar el estado");
      return;
    }

    cerrarModalCambioEstado();
    alert("Estado actualizado correctamente");
    await cargarDatos();
    await verHistorial(id);
  } catch (error) {
    alert("Error al actualizar el estado");
    console.error(error);
  }
}

async function editarSilabo(id) {
  await abrirModalEditarSilabo(id);
}

async function abrirModalEditarSilabo(id) {
  try {
    const response = await fetch(`${API_URL}/api/silabos/${id}`);
    const result = await response.json();

    if (!response.ok) {
      alert(result.detail || "No se pudo obtener el sílabo");
      return;
    }

    const silabo = result.data;
    silaboIdEdicionActual = id;
    document.getElementById("editarAsignatura").value = silabo.asignatura ?? "";
    document.getElementById("editarCodigo").value = silabo.codigo_asignatura ?? "";
    document.getElementById("editarCiclo").value = silabo.ciclo ?? "";
    document.getElementById("editarCreditos").value = silabo.creditos ?? "";
    document.getElementById("editarDocente").value = silabo.docente_responsable ?? "";
    document.getElementById("editarCorreo").value = silabo.correo_docente ?? "";
    document.getElementById("editarArchivoUrl").value = silabo.archivo_url ?? "";
    document.getElementById("editarObservacion").value = silabo.observacion_general ?? "";
    mostrarModal("modalEditarSilabo");
  } catch (error) {
    alert("Error al editar el sílabo");
    console.error(error);
  }
}

function cerrarModalEditarSilabo() {
  silaboIdEdicionActual = null;
  ocultarModal("modalEditarSilabo");
}

async function guardarEdicionSilabo() {
  if (!silaboIdEdicionActual) return;

  const id = silaboIdEdicionActual;
  const asignatura = document.getElementById("editarAsignatura").value.trim();
  const codigo = document.getElementById("editarCodigo").value.trim();
  const ciclo = document.getElementById("editarCiclo").value;
  const creditos = document.getElementById("editarCreditos").value;
  const docente = document.getElementById("editarDocente").value.trim();
  const correo = document.getElementById("editarCorreo").value.trim();
  const archivoUrl = document.getElementById("editarArchivoUrl").value.trim();
  const observacion = document.getElementById("editarObservacion").value.trim();
  const numeroCiclo = Number(ciclo);
  const numeroCreditos = creditos ? Number(creditos) : null;

  if (!asignatura || !codigo || !ciclo) {
    alert("Complete asignatura, código y ciclo.");
    return;
  }

  if (!Number.isInteger(numeroCiclo) || numeroCiclo < 1 || numeroCiclo > 10) {
    alert("El ciclo debe ser un número entre 1 y 10.");
    return;
  }

  if (numeroCreditos !== null && (!Number.isFinite(numeroCreditos) || numeroCreditos < 0)) {
    alert("Los créditos deben ser un número válido.");
    return;
  }

  if (archivoUrl && !normalizarEnlaceArchivo(archivoUrl)) {
    alert("Ingrese un enlace válido de Google Drive o Supabase Storage.");
    return;
  }

  const datosActualizados = {
    asignatura,
    codigo_asignatura: codigo,
    ciclo: numeroCiclo,
    creditos: numeroCreditos,
    docente_responsable: docente,
    correo_docente: correo,
    archivo_url: archivoUrl,
    observacion_general: observacion
  };

  try {
    const response = await fetch(`${API_URL}/api/silabos/${id}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(datosActualizados)
    });

    const result = await response.json();
    if (!response.ok) {
      alert(result.detail || "No se pudo actualizar el sílabo");
      return;
    }

    cerrarModalEditarSilabo();
    alert("Información del sílabo actualizada correctamente");
    await cargarDatos();
    await verHistorial(id);
  } catch (error) {
    alert("Error al editar el sílabo");
    console.error(error);
  }
}

async function analizarSilaboIA(id) {
  try {
    const confirmar = await abrirModalConfirmacion({
      titulo: "Analizar sílabo con IA",
      mensaje: "¿Deseas analizar este sílabo con el agente curricular?",
      textoConfirmar: "Analizar IA",
      tipo: "success"
    });

    if (!confirmar) return;

    mostrarNotificacion("Analizando sílabo, espere unos segundos...", "info");

    const response = await fetch(`${API_URL}/api/agentes/analizar-silabo/${id}`, {
      method: "POST"
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "No se pudo analizar el sílabo.");
    }

    mostrarNotificacion("Análisis generado correctamente.", "success");
    await verAnalisisSilabo(id);
  } catch (error) {
    console.error("Error al analizar sílabo:", error);
    alert("Error al analizar el sílabo: " + error.message);
  }
}

async function verAnalisisSilabo(id) {
  try {
    const response = await fetch(`${API_URL}/api/agentes/analisis-silabo/${id}`);
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "No se pudo obtener el análisis.");
    }

    const analisis = result.data && result.data.length > 0 ? result.data[0] : null;

    if (!analisis) {
      alert("Este sílabo todavía no tiene análisis. Presiona primero 'Analizar IA'.");
      return;
    }

    abrirModalAnalisis(analisis);
  } catch (error) {
    console.error("Error al obtener análisis:", error);
    alert("Error al obtener análisis: " + error.message);
  }
}

function escaparHtml(valor) {
  return String(valor ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderLista(valor) {
  if (!valor) return "<p class='text-muted'>Sin información registrada.</p>";

  if (typeof valor === "string") {
    try {
      valor = JSON.parse(valor);
    } catch {
      return `<p>${escaparHtml(valor)}</p>`;
    }
  }

  if (Array.isArray(valor) && valor.length > 0) {
    return `<ul>${valor.map((item) => `<li>${escaparHtml(typeof item === "object" ? JSON.stringify(item) : item)}</li>`).join("")}</ul>`;
  }

  return "<p class='text-muted'>Sin información registrada.</p>";
}

function renderTextoAnalisis(valor) {
  return valor
    ? `<p>${escaparHtml(valor)}</p>`
    : "<p class='text-muted'>Sin información registrada.</p>";
}

function abrirModalAnalisis(analisis) {
  const riesgo = String(analisis.nivel_riesgo ?? "sin dato").toLowerCase();
  const riesgoClase = ["bajo", "medio", "alto"].includes(riesgo) ? riesgo : "sin-dato";
  const fecha = analisis.created_at
    ? new Date(analisis.created_at).toLocaleString()
    : "Sin fecha registrada";

  document.getElementById("tituloModalAnalisis").textContent = "Análisis curricular del sílabo";
  document.getElementById("contenidoAnalisis").innerHTML = `
    <div class="analisis-section analisis-summary">
      <div>
        <span class="section-label">Nivel de riesgo</span>
        <span class="risk-badge risk-${riesgoClase}">${escaparHtml(riesgo)}</span>
      </div>
      <div>
        <span class="section-label">Modelo usado</span>
        <p>${escaparHtml(analisis.modelo_usado ?? "Sin modelo registrado")}</p>
      </div>
      <div>
        <span class="section-label">Fecha de análisis</span>
        <p>${escaparHtml(fecha)}</p>
      </div>
    </div>

    <div class="analisis-section">
      <h3>Resumen</h3>
      ${renderTextoAnalisis(analisis.resumen)}
    </div>
    <div class="analisis-section">
      <h3>Competencias detectadas</h3>
      ${renderLista(analisis.competencias_detectadas)}
    </div>
    <div class="analisis-section">
      <h3>Contenidos detectados</h3>
      ${renderLista(analisis.contenidos_detectados)}
    </div>
    <div class="analisis-section">
      <h3>Resultados de aprendizaje</h3>
      ${renderLista(analisis.resultados_aprendizaje)}
    </div>
    <div class="analisis-section">
      <h3>Secciones faltantes</h3>
      ${renderLista(analisis.secciones_faltantes)}
    </div>
    <div class="analisis-section">
      <h3>Sugerencias</h3>
      ${renderLista(analisis.sugerencias)}
    </div>
    <div class="analisis-section">
      <h3>Observación general</h3>
      ${renderTextoAnalisis(analisis.observacion_general)}
    </div>
  `;

  mostrarModal("modalAnalisis");
}

function cerrarModalAnalisis() {
  document.getElementById("modalAnalisis").classList.add("hidden");
  document.body.classList.remove("modal-open");
}

async function analizarTrazabilidadCurricular() {
  try {
    mostrarToast("Analizando trazabilidad curricular con LangGraph...", "info");

    const response = await fetch(`${API_URL}/api/agentes/analizar-trazabilidad-curricular`, {
      method: "POST"
    });
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "No se pudo generar la trazabilidad curricular.");
    }

    mostrarToast(
      `Trazabilidad generada: ${result.total_relaciones} relaciones y ${result.total_brechas} brechas.`,
      "success"
    );

    await verTrazabilidadCurricular();
  } catch (error) {
    console.error("Error al analizar trazabilidad:", error);
    mostrarToast("Error al analizar trazabilidad: " + error.message, "error");
  }
}

async function verTrazabilidadCurricular() {
  try {
    const response = await fetch(`${API_URL}/api/agentes/trazabilidad-curricular`);
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "No se pudo obtener la trazabilidad curricular.");
    }

    abrirModalTrazabilidad(result.data || []);
  } catch (error) {
    console.error("Error al obtener trazabilidad:", error);
    mostrarToast("Error al obtener trazabilidad: " + error.message, "error");
  }
}

async function verBrechasCurriculares() {
  try {
    const response = await fetch(`${API_URL}/api/agentes/brechas-curriculares`);
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "No se pudo obtener las brechas curriculares.");
    }

    abrirModalBrechas(result.data || []);
  } catch (error) {
    console.error("Error al obtener brechas:", error);
    mostrarToast("Error al obtener brechas: " + error.message, "error");
  }
}

function formatearTexto(valor) {
  if (!valor) return "-";
  return String(valor).replaceAll("_", " ");
}

function claseBadge(valor) {
  return formatearTexto(valor)
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function renderBadge(valor) {
  const texto = formatearTexto(valor);
  const clase = claseBadge(valor);
  return `<span class="badge badge-${clase}">${escaparHtml(texto)}</span>`;
}

function abrirModalTrazabilidad(data) {
  const contenedor = document.getElementById("contenidoTrazabilidad");

  if (!Array.isArray(data) || data.length === 0) {
    contenedor.innerHTML = `
      <p class="text-muted">No hay trazabilidad registrada. Primero ejecuta el análisis de trazabilidad curricular.</p>
    `;
    mostrarModal("modalTrazabilidad");
    return;
  }

  const filas = data.map((item) => `
    <tr>
      <td>${escaparHtml(item.ciclo_origen ?? "-")}</td>
      <td>${escaparHtml(item.asignatura_origen ?? "-")}</td>
      <td>${escaparHtml(item.ciclo_destino ?? "-")}</td>
      <td>${escaparHtml(item.asignatura_destino ?? "-")}</td>
      <td>${escaparHtml(formatearTexto(item.tipo_relacion))}</td>
      <td>${renderBadge(item.nivel_coherencia)}</td>
      <td>${escaparHtml(item.observacion ?? "-")}</td>
      <td>${escaparHtml(item.sugerencia ?? "-")}</td>
    </tr>
  `).join("");

  contenedor.innerHTML = `
    <div class="table-modal-wrapper">
      <table class="table-modal">
        <thead>
          <tr>
            <th>Ciclo origen</th>
            <th>Asignatura origen</th>
            <th>Ciclo destino</th>
            <th>Asignatura destino</th>
            <th>Tipo de relación</th>
            <th>Nivel de coherencia</th>
            <th>Observación</th>
            <th>Sugerencia</th>
          </tr>
        </thead>
        <tbody>${filas}</tbody>
      </table>
    </div>
  `;

  mostrarModal("modalTrazabilidad");
}

function cerrarModalTrazabilidad() {
  ocultarModal("modalTrazabilidad");
}

function abrirModalBrechas(data) {
  const contenedor = document.getElementById("contenidoBrechas");

  if (!Array.isArray(data) || data.length === 0) {
    contenedor.innerHTML = `<p class="text-muted">No hay brechas registradas.</p>`;
    mostrarModal("modalBrechas");
    return;
  }

  const filas = data.map((item) => `
    <tr>
      <td>${escaparHtml(item.ciclo ?? "-")}</td>
      <td>${escaparHtml(item.asignatura ?? "-")}</td>
      <td>${escaparHtml(formatearTexto(item.tipo_brecha))}</td>
      <td>${renderBadge(item.prioridad)}</td>
      <td>${escaparHtml(item.descripcion ?? "-")}</td>
      <td>${escaparHtml(item.recomendacion ?? "-")}</td>
      <td>${escaparHtml(formatearTexto(item.estado))}</td>
    </tr>
  `).join("");

  contenedor.innerHTML = `
    <div class="table-modal-wrapper">
      <table class="table-modal">
        <thead>
          <tr>
            <th>Ciclo</th>
            <th>Asignatura</th>
            <th>Tipo de brecha</th>
            <th>Prioridad</th>
            <th>Descripción</th>
            <th>Recomendación</th>
            <th>Estado</th>
          </tr>
        </thead>
        <tbody>${filas}</tbody>
      </table>
    </div>
  `;

  mostrarModal("modalBrechas");
}

function cerrarModalBrechas() {
  ocultarModal("modalBrechas");
}
