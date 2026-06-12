const API_URL = ["localhost", "127.0.0.1"].includes(window.location.hostname)
  ? "http://127.0.0.1:8000"
  : "https://tallerintegrador.onrender.com";
console.log("[API_URL]", API_URL);
let silabosGlobal = [];
let paginaActual = 1;
const SILABOS_POR_PAGINA = 10;
let trazabilidadDataGlobal = [];
let brechasDataGlobal = [];
let accionesMejoraGlobal = [];
let alertasInteligentesGlobal = [];
let macroprocesoAccionesActual = null;
let macroprocesoRegistroAccionActual = null;
let reporteIntegralActual = null;
let evidenciasMacroprocesosGlobal = {
  planificacion_estrategica: [],
  gestion_academica: []
};
let evidenciaMacroprocesoActual = null;
let macroprocesoHistorialIAActual = null;

const MACROPROCESOS_CONFIG = {
  planificacion_estrategica: {
    sectionKey: "planificacion",
    dashboardId: "dashboardPlanificacion",
    containerId: "evidenciasPlanificacion",
    searchId: "buscarPlanificacion",
    estadoId: "estadoPlanificacion",
    prioridadId: "prioridadPlanificacion",
    columns: ["codigo", "titulo", "responsable", "mes_programado", "prioridad", "estado", "avance", "acciones"],
    summaryCards: ["total", "pendientes", "en_proceso", "completadas", "avance_promedio"]
  },
  gestion_academica: {
    sectionKey: "gestionAcademica",
    dashboardId: "dashboardGestionAcademica",
    containerId: "evidenciasGestionAcademica",
    searchId: "buscarGestionAcademica",
    estadoId: "estadoGestionAcademica",
    prioridadId: "prioridadGestionAcademica",
    columns: ["codigo", "titulo", "tipo_evidencia", "responsable", "prioridad", "estado", "avance", "acciones"],
    summaryCards: ["total", "pendientes", "en_proceso", "completadas", "observadas", "avance_promedio"]
  }
};

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  let data = null;

  try {
    data = await response.json();
  } catch {
    data = {};
  }

  if (!response.ok) {
    throw new Error(data.detail || data.message || `Error HTTP ${response.status}`);
  }

  return data;
}

document.addEventListener("DOMContentLoaded", async () => {
  if (typeof protegerPagina === "function") {
    const sesionValida = await protegerPagina();
    if (sesionValida === false) return;
  }

  await cargarDatos();

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

async function mostrarMacroproceso(nombre) {
  const macroprocesosView = document.getElementById("macroprocesosView");
  const modulos = {
    planificacion: document.getElementById("macroPlanificacion"),
    gestionAcademica: document.getElementById("macroGestionAcademica"),
    gestionSilabos: document.getElementById("macroGestionSilabos")
  };

  if (macroprocesosView) {
    macroprocesosView.classList.add("hidden");
  }

  document.querySelectorAll(".macro-module").forEach((seccion) => {
    seccion.classList.add("hidden");
  });

  if (modulos[nombre]) {
    modulos[nombre].classList.remove("hidden");
  }

  if (nombre === "planificacion") {
    await cargarVistaMacroproceso("planificacion_estrategica");
  }

  if (nombre === "gestionAcademica") {
    await cargarVistaMacroproceso("gestion_academica");
  }

  window.scrollTo({ top: 0, behavior: "smooth" });
}

function volverMacroprocesos() {
  document.querySelectorAll(".macro-module").forEach((seccion) => {
    seccion.classList.add("hidden");
  });

  const macroprocesosView = document.getElementById("macroprocesosView");
  if (macroprocesosView) {
    macroprocesosView.classList.remove("hidden");
  }

  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function cargarVistaMacroproceso(macroproceso) {
  const config = MACROPROCESOS_CONFIG[macroproceso];
  if (!config) return;

  const contenedor = document.getElementById(config.containerId);
  if (contenedor) {
    contenedor.innerHTML = `<p class="text-muted">Cargando evidencias...</p>`;
  }

  try {
    const response = await fetch(`${API_URL}/api/macroprocesos/evidencias?macroproceso=${encodeURIComponent(macroproceso)}`);
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "No se pudo cargar las evidencias del macroproceso.");
    }

    evidenciasMacroprocesosGlobal[macroproceso] = Array.isArray(result.data) ? result.data : [];
    await cargarAlertasActivasMacroproceso(macroproceso);
    renderDashboardMacroproceso(macroproceso);
    renderEvidenciasMacroproceso(macroproceso);
  } catch (error) {
    console.error("Error al cargar macroproceso:", error);
    mostrarToast("Error al cargar evidencias: " + error.message, "error");
    if (contenedor) {
      contenedor.innerHTML = `<p class="text-muted">No se pudieron cargar las evidencias.</p>`;
    }
  }
}

function calcularResumenMacroproceso(evidencias) {
  const total = evidencias.length;
  const avancePromedio = total
    ? Math.round(evidencias.reduce((sum, item) => sum + Number(item.avance || 0), 0) / total)
    : 0;

  return {
    total,
    pendientes: contarPorCampo(evidencias, "estado", "pendiente"),
    en_proceso: contarPorCampo(evidencias, "estado", "en_proceso"),
    completadas: contarPorCampo(evidencias, "estado", "completado"),
    observadas: contarPorCampo(evidencias, "estado", "observado"),
    avance_promedio: avancePromedio
  };
}

function renderDashboardMacroproceso(macroproceso) {
  const config = MACROPROCESOS_CONFIG[macroproceso];
  const contenedor = document.getElementById(config.dashboardId);
  if (!contenedor) return;

  const resumen = calcularResumenMacroproceso(evidenciasMacroprocesosGlobal[macroproceso] || []);
  const titulos = {
    total: "Total de evidencias",
    pendientes: "Pendientes",
    en_proceso: "En proceso",
    completadas: "Completadas",
    observadas: "Observadas",
    avance_promedio: "Avance promedio"
  };

  contenedor.innerHTML = config.summaryCards.map((clave) => {
    const valor = clave === "avance_promedio" ? `${resumen[clave]}%` : resumen[clave];
    const clase = clave === "pendientes"
      ? "danger"
      : clave === "en_proceso"
        ? "warning"
        : clave === "completadas"
          ? "success"
          : "";

    return `
      <div class="card ${clase}">
        <h3>${escaparHtml(titulos[clave])}</h3>
        <p>${escaparHtml(valor)}</p>
      </div>
    `;
  }).join("");
}

function obtenerEvidenciasFiltradas(macroproceso) {
  const config = MACROPROCESOS_CONFIG[macroproceso];
  const evidencias = evidenciasMacroprocesosGlobal[macroproceso] || [];
  const busqueda = normalizarValor(document.getElementById(config.searchId)?.value || "");
  const estado = document.getElementById(config.estadoId)?.value || "";
  const prioridad = document.getElementById(config.prioridadId)?.value || "";

  return evidencias.filter((item) => {
    const texto = normalizarValor(`${item.titulo || ""} ${item.responsable || ""}`);
    const coincideBusqueda = !busqueda || texto.includes(busqueda);
    const coincideEstado = !estado || item.estado === estado;
    const coincidePrioridad = !prioridad || item.prioridad === prioridad;
    return coincideBusqueda && coincideEstado && coincidePrioridad;
  });
}

function renderEvidenciasMacroproceso(macroproceso) {
  const config = MACROPROCESOS_CONFIG[macroproceso];
  const contenedor = document.getElementById(config.containerId);
  if (!contenedor) return;

  const evidencias = obtenerEvidenciasFiltradas(macroproceso);
  if (evidencias.length === 0) {
    contenedor.innerHTML = `<p class="text-muted">No se encontraron evidencias con los filtros aplicados.</p>`;
    return;
  }

  contenedor.innerHTML = evidencias.map((item) => renderEvidenceCard(item, config.columns)).join("");
}

function renderEvidenceCard(evidencia, columnas) {
  const avance = Math.min(100, Math.max(0, Number(evidencia.avance || 0)));
  const id = escaparAtributo(evidencia.id);
  const archivoUrl = normalizarEnlaceArchivo(evidencia.archivo_url);
  const nombreArchivo = archivoUrl ? obtenerNombreArchivoEvidencia(archivoUrl) : "";
  const alerta = obtenerAlertaActivaEvidencia(evidencia.id);
  const detalleSecundario = columnas.includes("tipo_evidencia")
    ? `<p><span>Tipo de evidencia</span><strong>${escaparHtml(evidencia.tipo_evidencia || "-")}</strong></p>`
    : `<p><span>Mes programado</span><strong>${escaparHtml(evidencia.mes_programado || "-")}</strong></p>`;
  const validarButton = archivoUrl
    ? `<button class="btn btn-primary" type="button" onclick="validarEvidenciaIA('${id}')">Validar evidencia con IA</button>`
    : `<button class="btn btn-secondary" type="button" onclick="mostrarToast('Primero suba un archivo de sustento para validar esta evidencia.', 'warning')">Validar evidencia con IA</button>`;

  return `
    <article class="evidence-card evidence-card-modern priority-${escaparAtributo(evidencia.prioridad || "media")}">
      <div class="evidence-card-header evidence-card-top">
        <div class="evidence-title-group">
          <span class="evidence-code">${escaparHtml(evidencia.codigo || "-")}</span>
          <h3>${escaparHtml(evidencia.titulo || "Evidencia")}</h3>
        </div>
        <div class="evidence-badges">
          ${renderBadge(evidencia.prioridad || "media")}
          <span class="badge badge-estado-${escaparAtributo(evidencia.estado || "pendiente")}">${escaparHtml(formatearTexto(evidencia.estado || "pendiente"))}</span>
        </div>
      </div>

      <div class="evidence-card-body">
        ${alerta ? renderBadgeAlertaEvidencia(alerta) : ""}
        <p><span>Responsable</span><strong>${escaparHtml(evidencia.responsable || "Sin responsable")}</strong></p>
        ${detalleSecundario}
        <p><span>Origen</span><strong>${escaparHtml(evidencia.origen_documento || "-")}</strong></p>
      </div>

      <div class="evidence-file-panel ${archivoUrl ? "has-file" : "no-file"}">
        <div>
          <span class="section-label">Sustento documental</span>
          <strong>${archivoUrl ? "Archivo registrado" : "Sin archivo de sustento"}</strong>
          <small>${archivoUrl ? escaparHtml(nombreArchivo) : "Suba un PDF o DOCX para validar la evidencia con IA."}</small>
        </div>
        ${archivoUrl
          ? `<button class="btn btn-info evidence-file-badge" type="button" onclick="verArchivoEvidencia('${escaparAtributo(archivoUrl)}')">Ver evidencia</button>`
          : `<span class="no-file-warning">Pendiente de carga</span>`}
      </div>

      <div class="progress-block evidence-progress">
        <div class="progress-meta">
          <span>Avance</span>
          <strong>${avance}%</strong>
        </div>
        <div class="progress-bar">
          <span style="width: ${avance}%"></span>
        </div>
      </div>

      <div class="evidence-actions evidence-actions-primary">
        <button class="btn btn-info" type="button" onclick="abrirModalEvidenciaMacroproceso('${id}', 'detalle')">Ver detalle</button>
        <button class="btn btn-warning" type="button" onclick="abrirModalEvidenciaMacroproceso('${id}', 'estado')">Cambiar estado</button>
        ${validarButton}
      </div>
      <div class="evidence-actions evidence-actions-secondary">
        <button class="btn btn-secondary" type="button" onclick="abrirModalEvidenciaMacroproceso('${id}', 'avance')">Editar avance</button>
        <button class="btn btn-secondary" type="button" onclick="abrirModalEvidenciaMacroproceso('${id}', 'observacion')">Agregar observaci&oacute;n</button>
        <button class="btn btn-success evidence-upload-btn" type="button" onclick="subirArchivoEvidenciaMacroproceso('${id}')">Subir evidencia</button>
        <button class="btn btn-secondary" type="button" onclick="verUltimaValidacionEvidenciaIA('${id}')">Ver &uacute;ltima validaci&oacute;n IA</button>
        <button class="btn btn-secondary" type="button" onclick="verHistorialEvidenciaMacroproceso('${id}')">Ver historial</button>
        <button class="btn btn-secondary" type="button" onclick="generarAccionDesdeEvidencia('${id}')">Generar acci&oacute;n</button>
      </div>
    </article>
  `;
}

function obtenerAlertaActivaEvidencia(evidenciaId) {
  return alertasInteligentesGlobal.find((alerta) =>
    alerta.estado === "activa"
    && alerta.origen_id === evidenciaId
    && String(alerta.origen_tipo || "").includes("evidencia")
  );
}

function renderBadgeAlertaEvidencia(alerta) {
  const nivel = alerta.nivel_alerta || "media";
  const texto = nivel === "critica" ? "Alerta critica" : "Alerta activa";
  return `<span class="alert-badge alert-${escaparAtributo(nivel)}">${escaparHtml(texto)}</span>`;
}

function obtenerNombreArchivoEvidencia(url) {
  try {
    const pathname = new URL(url).pathname;
    const nombre = decodeURIComponent(pathname.split("/").pop() || "Archivo de sustento");
    return nombre.replace(/^[a-f0-9-]{8,}_/i, "") || "Archivo de sustento";
  } catch {
    return "Archivo de sustento";
  }
}

function buscarEvidenciaMacroproceso(id) {
  return Object.values(evidenciasMacroprocesosGlobal)
    .flat()
    .find((item) => item.id === id);
}

function abrirModalEvidenciaMacroproceso(id, modo = "detalle") {
  const evidencia = buscarEvidenciaMacroproceso(id);
  if (!evidencia) {
    mostrarToast("No se encontr? la evidencia seleccionada.", "warning");
    return;
  }

  evidenciaMacroprocesoActual = evidencia;
  const esSoloDetalle = modo === "detalle";
  const avance = Math.min(100, Math.max(0, Number(evidencia.avance || 0)));

  document.getElementById("tituloModalEvidencia").textContent = esSoloDetalle
    ? "Detalle de evidencia"
    : "Actualizar evidencia";
  document.getElementById("detalleEvidenciaMacroproceso").innerHTML = `
    <div class="evidence-detail-grid">
      <div><span>Código</span><strong>${escaparHtml(evidencia.codigo || "-")}</strong></div>
      <div><span>Estado</span><strong>${escaparHtml(formatearTexto(evidencia.estado || "-"))}</strong></div>
      <div><span>Prioridad</span><strong>${escaparHtml(formatearTexto(evidencia.prioridad || "-"))}</strong></div>
      <div><span>Avance</span><strong>${avance}%</strong></div>
    </div>
    <h3>${escaparHtml(evidencia.titulo || "Evidencia")}</h3>
    <p><strong>Descripción:</strong> ${escaparHtml(evidencia.descripcion || "Sin descripción registrada.")}</p>
    <p><strong>Tipo de evidencia:</strong> ${escaparHtml(evidencia.tipo_evidencia || "-")}</p>
    <p><strong>Responsable:</strong> ${escaparHtml(evidencia.responsable || "Sin responsable")}</p>
    <p><strong>Mes programado:</strong> ${escaparHtml(evidencia.mes_programado || "-")}</p>
    <p><strong>Origen:</strong> ${escaparHtml(evidencia.origen_documento || "-")}</p>
    <p><strong>Observación:</strong> ${escaparHtml(evidencia.observacion || "Sin observación registrada.")}</p>
  `;

  document.getElementById("editorEvidenciaMacroproceso").classList.toggle("hidden", esSoloDetalle);
  document.getElementById("botonGuardarEvidencia").classList.toggle("hidden", esSoloDetalle);
  document.getElementById("evidenciaEstado").value = evidencia.estado || "pendiente";
  document.getElementById("evidenciaAvance").value = avance;
  document.getElementById("evidenciaObservacion").value = evidencia.observacion || "";

  if (!esSoloDetalle) {
    const focoPorModo = {
      estado: "evidenciaEstado",
      avance: "evidenciaAvance",
      observacion: "evidenciaObservacion"
    };
    setTimeout(() => document.getElementById(focoPorModo[modo] || "evidenciaEstado")?.focus(), 100);
  }

  mostrarModal("modalEvidenciaMacroproceso");
}

function cerrarModalEvidenciaMacroproceso() {
  evidenciaMacroprocesoActual = null;
  ocultarModal("modalEvidenciaMacroproceso");
}

async function guardarEvidenciaMacroproceso() {
  if (!evidenciaMacroprocesoActual) return;

  const avance = Number(document.getElementById("evidenciaAvance").value);
  if (!Number.isFinite(avance) || avance < 0 || avance > 100) {
    mostrarToast("El avance debe estar entre 0 y 100.", "warning");
    return;
  }

  const payload = {
    estado: document.getElementById("evidenciaEstado").value,
    avance,
    observacion: document.getElementById("evidenciaObservacion").value.trim()
  };

  try {
    const response = await fetch(`${API_URL}/api/macroprocesos/evidencias/${evidenciaMacroprocesoActual.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "No se pudo actualizar la evidencia.");
    }

    const macroproceso = evidenciaMacroprocesoActual.macroproceso;
    cerrarModalEvidenciaMacroproceso();
    mostrarToast("Evidencia actualizada correctamente.", "success");
    await cargarVistaMacroproceso(macroproceso);
  } catch (error) {
    console.error("Error al actualizar evidencia:", error);
    mostrarToast("Error al actualizar evidencia: " + error.message, "error");
  }
}

function verArchivoEvidencia(url) {
  const archivoUrl = normalizarEnlaceArchivo(url);
  if (!archivoUrl) {
    mostrarToast("La evidencia no tiene un enlace válido.", "warning");
    return;
  }
  window.open(archivoUrl, "_blank", "noopener");
}

function subirArchivoEvidenciaMacroproceso(evidenciaId) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".pdf,.docx,.xlsx,.png,.jpg,.jpeg";
  input.onchange = async () => {
    const archivo = input.files?.[0];
    if (!archivo) return;
    await enviarArchivoEvidenciaMacroproceso(evidenciaId, archivo);
  };
  input.click();
}

async function enviarArchivoEvidenciaMacroproceso(evidenciaId, archivo) {
  const evidencia = buscarEvidenciaMacroproceso(evidenciaId);
  const formData = new FormData();
  formData.append("archivo", archivo);

  try {
    mostrarToast("Subiendo evidencia documental...", "info");
    const response = await fetch(`${API_URL}/api/macroprocesos/evidencias/${evidenciaId}/archivo`, {
      method: "POST",
      body: formData
    });
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "No se pudo subir la evidencia documental.");
    }

    mostrarToast("Evidencia documental subida correctamente.", "success");
    if (evidencia?.macroproceso) {
      await cargarVistaMacroproceso(evidencia.macroproceso);
    }
  } catch (error) {
    console.error("Error al subir evidencia documental:", error);
    mostrarToast("No se pudo subir la evidencia documental.", "error");
  }
}

async function verHistorialEvidenciaMacroproceso(evidenciaId) {
  try {
    const response = await fetch(`${API_URL}/api/macroprocesos/evidencias/${evidenciaId}/historial`);
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "No se pudo obtener el historial.");
    }

    abrirModalHistorialEvidencia(result.historial || []);
  } catch (error) {
    console.error("Error al cargar historial de evidencia:", error);
    mostrarToast("No se pudo cargar el historial de la evidencia.", "error");
  }
}

function abrirModalHistorialEvidencia(historial) {
  const contenedor = document.getElementById("contenidoHistorialEvidencia");
  if (!Array.isArray(historial) || historial.length === 0) {
    contenedor.innerHTML = `<p class="text-muted">No hay cambios registrados para esta evidencia.</p>`;
  } else {
    contenedor.innerHTML = historial.map((item) => `
      <article class="history-item">
        <div class="history-item-header">
          <strong>${escaparHtml(item.campo_modificado || "-")}</strong>
          <span>${escaparHtml(item.created_at ? new Date(item.created_at).toLocaleString() : "Sin fecha")}</span>
        </div>
        <p><strong>Valor anterior:</strong> ${escaparHtml(item.valor_anterior ?? "-")}</p>
        <p><strong>Valor nuevo:</strong> ${escaparHtml(item.valor_nuevo ?? "-")}</p>
        <p><strong>Observación:</strong> ${escaparHtml(item.observacion || "-")}</p>
      </article>
    `).join("");
  }
  mostrarModal("modalHistorialEvidencia");
}

function cerrarModalHistorialEvidencia() {
  ocultarModal("modalHistorialEvidencia");
}

async function validarEvidenciaIA(evidenciaId) {
  const evidencia = buscarEvidenciaMacroproceso(evidenciaId);
  if (!normalizarEnlaceArchivo(evidencia?.archivo_url)) {
    mostrarToast("Primero suba un archivo de sustento para validar esta evidencia.", "warning");
    return;
  }

  try {
    mostrarToast("Validando evidencia documental con IA...", "info");
    const result = await fetchJson(`${API_URL}/api/macroprocesos/evidencias/${evidenciaId}/validar-ia`, {
      method: "POST"
    });

    mostrarToast("Validacion IA generada correctamente.", "success");
    abrirModalValidacionEvidenciaIA(result.data || {});
  } catch (error) {
    console.error("Error al validar evidencia con IA:", error);
    mostrarToast("Error al validar evidencia: " + error.message, "error");
  }
}

async function verUltimaValidacionEvidenciaIA(evidenciaId) {
  try {
    const result = await fetchJson(`${API_URL}/api/macroprocesos/evidencias/${evidenciaId}/validacion-ia`);

    if (!result.data) {
      mostrarToast("Esta evidencia todavia no tiene validaciones IA.", "info");
      return;
    }

    abrirModalValidacionEvidenciaIA(result.data);
  } catch (error) {
    console.error("Error al obtener validacion IA:", error);
    mostrarToast("No se pudo obtener la validacion IA.", "error");
  }
}

function abrirModalValidacionEvidenciaIA(validacion) {
  const contenedor = document.getElementById("contenidoValidacionEvidenciaIA");
  if (!contenedor) return;

  const nivel = String(validacion.nivel_validez || "sin-dato").toLowerCase();
  const nivelClase = ["alto", "medio", "bajo"].includes(nivel) ? nivel : "sin-dato";
  const pertinencia = String(validacion.pertinencia || "sin dato").replaceAll("_", " ");
  const fecha = validacion.created_at
    ? new Date(validacion.created_at).toLocaleString()
    : "Sin fecha registrada";

  contenedor.innerHTML = `
    <div class="analisis-section validation-summary">
      <div>
        <span class="section-label">Nivel de validez</span>
        <span class="ia-validity-badge validity-${escaparAtributo(nivelClase)}">${escaparHtml(formatearTexto(nivel))}</span>
      </div>
      <div>
        <span class="section-label">Pertinencia</span>
        <strong>${escaparHtml(formatearTexto(pertinencia))}</strong>
      </div>
      <div>
        <span class="section-label">Fecha</span>
        <strong>${escaparHtml(fecha)}</strong>
      </div>
    </div>
    <div class="analisis-section">
      <h3>Resumen</h3>
      ${renderTextoAnalisis(validacion.resumen)}
    </div>
    <div class="validation-detail-grid">
      <div class="analisis-section">
        <h3>Elementos detectados</h3>
        ${renderLista(validacion.elementos_detectados)}
      </div>
      <div class="analisis-section">
        <h3>Elementos faltantes</h3>
        ${renderLista(validacion.elementos_faltantes)}
      </div>
      <div class="analisis-section">
        <h3>Observaciones</h3>
        ${renderLista(validacion.observaciones)}
      </div>
      <div class="analisis-section">
        <h3>Recomendaciones</h3>
        ${renderLista(validacion.recomendaciones)}
      </div>
    </div>
    <div class="analisis-section">
      <h3>Acci&oacute;n sugerida</h3>
      ${renderTextoAnalisis(validacion.accion_sugerida)}
    </div>
    <div class="analisis-section">
      <h3>Modelo usado</h3>
      <p>${escaparHtml(validacion.modelo_usado || "-")}</p>
    </div>
  `;

  mostrarModal("modalValidacionEvidenciaIA");
}

function cerrarModalValidacionEvidenciaIA() {
  ocultarModal("modalValidacionEvidenciaIA");
}

async function cargarAlertasActivasMacroproceso(macroproceso) {
  try {
    const result = await fetchJson(`${API_URL}/api/macroprocesos/alertas?macroproceso=${encodeURIComponent(macroproceso)}&estado=activa`);

    const otrasAlertas = alertasInteligentesGlobal.filter((item) => item.macroproceso !== macroproceso);
    alertasInteligentesGlobal = otrasAlertas.concat(result.alertas || []);
  } catch (error) {
    console.error("Error al cargar alertas del macroproceso:", error);
  }
}

async function generarAlertasInteligentes() {
  try {
    mostrarNotificacion("Generando alertas inteligentes...", "info");

    const url = `${API_URL}/api/macroprocesos/alertas/generar`;
    console.log("[Frontend Alertas] API_URL:", API_URL);
    console.log("[Frontend Alertas] Llamando a:", url);

    const data = await fetchJson(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      }
    });
    console.log("[Frontend Alertas] Respuesta:", data);

    mostrarNotificacion(
      `Alertas generadas correctamente. Creadas: ${data.alertas_creadas || 0}. Existentes: ${data.alertas_existentes || 0}.`,
      "success"
    );

    await cargarSemaforoMacroprocesos();

    if (typeof cargarAlertasInteligentes === "function") {
      await cargarAlertasInteligentes();
    }
  } catch (error) {
    console.error("[Frontend Alertas] Error:", error);
    mostrarNotificacion(error.message || "No se pudieron generar alertas inteligentes.", "error");
  }
}

async function cargarAlertasInteligentes() {
  try {
    const url = `${API_URL}/api/macroprocesos/alertas?estado=activa`;
    console.log("[Frontend Alertas] Llamando a:", url);

    const data = await fetchJson(url);
    console.log("[Frontend Alertas] Respuesta:", data);

    alertasInteligentesGlobal = data.alertas || [];
    renderAlertasInteligentes(alertasInteligentesGlobal);
    refrescarBadgesAlertasEvidencias();
    return alertasInteligentesGlobal;
  } catch (error) {
    console.error("[Frontend Alertas] Error:", error);
    mostrarNotificacion(error.message || "No se pudieron cargar las alertas inteligentes.", "error");
    return [];
  }
}

async function verAlertasInteligentes() {
  await cargarAlertasInteligentes();
  mostrarModal("modalAlertasInteligentes");
}

function refrescarBadgesAlertasEvidencias() {
  if (!document.getElementById("macroPlanificacion")?.classList.contains("hidden")) {
    renderEvidenciasMacroproceso("planificacion_estrategica");
  }
  if (!document.getElementById("macroGestionAcademica")?.classList.contains("hidden")) {
    renderEvidenciasMacroproceso("gestion_academica");
  }
}

function renderAlertasInteligentes(alertas) {
  const contenedor = document.getElementById("contenidoAlertasInteligentes");
  if (!contenedor) return;

  if (!Array.isArray(alertas) || alertas.length === 0) {
    contenedor.innerHTML = `<p class="text-muted">No hay alertas activas.</p>`;
    return;
  }

  contenedor.innerHTML = alertas.map((alerta) => {
    const nivel = alerta.nivel_alerta || "media";
    const fecha = alerta.created_at ? new Date(alerta.created_at).toLocaleString() : "Sin fecha";
    return `
      <article class="alert-card alert-${escaparAtributo(nivel)}">
        <div class="alert-card-header">
          <span class="alert-badge alert-${escaparAtributo(nivel)}">${escaparHtml(formatearTexto(nivel))}</span>
          <span class="evidence-code">${escaparHtml(formatearTexto(alerta.macroproceso || "-"))}</span>
        </div>
        <h3>${escaparHtml(alerta.titulo || "Alerta inteligente")}</h3>
        <p><strong>Descripcion:</strong> ${escaparHtml(alerta.descripcion || "-")}</p>
        <p><strong>Recomendacion:</strong> ${escaparHtml(alerta.recomendacion || "-")}</p>
        <p><strong>Fecha:</strong> ${escaparHtml(fecha)}</p>
        <div class="alert-actions">
          <button class="btn btn-success" type="button" onclick="actualizarAlertaInteligente('${escaparAtributo(alerta.id)}', 'atendida')">Marcar como atendida</button>
          <button class="btn btn-secondary" type="button" onclick="actualizarAlertaInteligente('${escaparAtributo(alerta.id)}', 'descartada')">Descartar</button>
        </div>
      </article>
    `;
  }).join("");
}

async function actualizarAlertaInteligente(alertaId, estado) {
  try {
    await fetchJson(`${API_URL}/api/macroprocesos/alertas/${alertaId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ estado })
    });

    mostrarToast("Alerta actualizada correctamente.", "success");
    await cargarSemaforoCumplimiento();
    await verAlertasInteligentes();
  } catch (error) {
    console.error("Error al actualizar alerta:", error);
    mostrarToast("No se pudo actualizar la alerta.", "error");
  }
}

function cerrarModalAlertasInteligentes() {
  ocultarModal("modalAlertasInteligentes");
}

async function cargarSemaforoMacroprocesos() {
  await cargarSemaforoCumplimiento();
}

async function cargarSemaforoCumplimiento() {
  const contenedor = document.getElementById("semaforoCumplimiento");
  if (!contenedor) return;

  contenedor.innerHTML = `<p class="text-muted">Cargando semaforo de cumplimiento...</p>`;
  try {
    const result = await fetchJson(`${API_URL}/api/macroprocesos/semaforo`);

    renderSemaforoCumplimiento(result.semaforos || []);
  } catch (error) {
    console.error("Error al cargar semaforo:", error);
    contenedor.innerHTML = `<p class="text-muted">No se pudo cargar el semaforo de cumplimiento.</p>`;
  }
}

function renderSemaforoCumplimiento(semaforos) {
  const contenedor = document.getElementById("semaforoCumplimiento");
  if (!contenedor) return;

  if (!Array.isArray(semaforos) || semaforos.length === 0) {
    contenedor.innerHTML = `<p class="text-muted">No hay datos para el semaforo.</p>`;
    return;
  }

  contenedor.innerHTML = semaforos.map((item) => `
    <article class="traffic-light-card traffic-${escaparAtributo(item.color || "yellow")}">
      <div class="traffic-light-header">
        <span class="traffic-light-dot traffic-${escaparAtributo(item.color || "yellow")}"></span>
        <div>
          <h3>${escaparHtml(item.nombre || formatearTexto(item.macroproceso))}</h3>
          <p>${escaparHtml(item.mensaje || "-")}</p>
        </div>
      </div>
      <div class="traffic-light-metrics">
        <span>Avance <strong>${escaparHtml(item.avance_promedio ?? 0)}%</strong></span>
        <span>Cr&iacute;ticas <strong>${escaparHtml(item.alertas_criticas ?? 0)}</strong></span>
        <span>Altas <strong>${escaparHtml(item.alertas_altas ?? 0)}</strong></span>
        <span>Riesgo IA <strong>${escaparHtml(formatearTexto(item.riesgo_ia || "sin_datos"))}</strong></span>
      </div>
    </article>
  `).join("");
}

async function verHistorialAnalisisIA(macroproceso) {
  macroprocesoHistorialIAActual = macroproceso;
  document.getElementById("comparacionHistorialIA").classList.add("hidden");
  document.getElementById("detalleHistorialIA").classList.add("hidden");
  document.getElementById("contenidoHistorialIA").innerHTML = `<p class="text-muted">Cargando historial IA...</p>`;
  mostrarModal("modalHistorialIA");

  try {
    const result = await fetchJson(`${API_URL}/api/macroprocesos/analisis-ia/historial?macroproceso=${encodeURIComponent(macroproceso)}&limit=10`);

    renderHistorialAnalisisIA(result.historial || []);
  } catch (error) {
    console.error("Error al cargar historial IA:", error);
    mostrarToast("No se pudo cargar el historial IA.", "error");
  }
}

function renderHistorialAnalisisIA(historial) {
  const contenedor = document.getElementById("contenidoHistorialIA");
  if (!Array.isArray(historial) || historial.length === 0) {
    contenedor.innerHTML = `<p class="text-muted">No hay análisis IA registrados todavía.</p>`;
    return;
  }

  contenedor.innerHTML = historial.map((item) => {
    const riesgo = String(item.nivel_riesgo || "sin-dato").toLowerCase();
    const riesgoClase = ["bajo", "medio", "alto"].includes(riesgo) ? riesgo : "sin-dato";
    return `
      <article class="ia-history-card">
        <div class="history-item-header">
          <strong>${escaparHtml(formatearTexto(item.tipo_analisis || "-"))}</strong>
          <span>${escaparHtml(item.created_at ? new Date(item.created_at).toLocaleString() : "Sin fecha")}</span>
        </div>
        <div class="evidence-badges">
          <span class="ia-risk-badge risk-badge risk-${escaparAtributo(riesgoClase)}">${escaparHtml(riesgo)}</span>
          <span class="evidence-code">${escaparHtml(formatearTexto(item.macroproceso || "-"))}</span>
        </div>
        <p><strong>Modelo:</strong> ${escaparHtml(item.modelo_usado || "-")}</p>
        <p>${escaparHtml(item.resumen || "Sin resumen registrado.")}</p>
        <div class="evidence-actions">
          <button class="btn btn-info" type="button" onclick="verDetalleAnalisisIA('${escaparAtributo(item.id)}')">Ver detalle</button>
        </div>
      </article>
    `;
  }).join("");
}

async function verDetalleAnalisisIA(analisisId) {
  try {
    const data = await fetchJson(`${API_URL}/api/macroprocesos/analisis-ia/historial/${analisisId}`);

    renderDetalleAnalisisIA(data);
  } catch (error) {
    console.error("Error al cargar detalle IA:", error);
    mostrarToast("No se pudo cargar el detalle del análisis IA.", "error");
  }
}

function renderDetalleAnalisisIA(analisis) {
  const detalle = document.getElementById("detalleHistorialIA");
  const data = analisis.resultado_json || {};
  detalle.classList.remove("hidden");
  detalle.innerHTML = `
    <div class="analisis-section">
      <h3>Detalle del análisis</h3>
      <p><strong>Fecha:</strong> ${escaparHtml(analisis.created_at ? new Date(analisis.created_at).toLocaleString() : "Sin fecha")}</p>
      <p><strong>Modelo usado:</strong> ${escaparHtml(analisis.modelo_usado || data.modelo_usado || "-")}</p>
      <p><strong>Resumen:</strong> ${escaparHtml(analisis.resumen || data.resumen || data.resumen_general || "-")}</p>
    </div>
    <div class="analisis-section">
      <h3>Riesgos</h3>
      ${renderListaPlanificacion(data.riesgos || data.hallazgos_integrados || [])}
    </div>
    <div class="analisis-section">
      <h3>Recomendaciones</h3>
      ${renderListaPlanificacion(data.recomendaciones || data.recomendaciones_comite || [])}
    </div>
    <div class="analisis-section">
      <h3>Acciones sugeridas</h3>
      ${renderAccionesPlanificacion(data.acciones_sugeridas || data.acciones_prioritarias || [])}
    </div>
    <div class="analisis-section">
      <h3>Observación general</h3>
      <p>${escaparHtml(data.observacion_general || "-")}</p>
    </div>
    <div class="analisis-section">
      <h3>Resultado estructurado</h3>
      <pre class="ia-json-detail">${escaparHtml(JSON.stringify(data, null, 2))}</pre>
    </div>
  `;
}

async function compararUltimosAnalisisIA() {
  if (!macroprocesoHistorialIAActual) return;

  try {
    const result = await fetchJson(`${API_URL}/api/macroprocesos/analisis-ia/comparar?macroproceso=${encodeURIComponent(macroprocesoHistorialIAActual)}`);

    const comparacion = result.comparacion || {};
    const contenedor = document.getElementById("comparacionHistorialIA");
    contenedor.classList.remove("hidden");
    contenedor.innerHTML = `
      <h3>Comparación de últimos análisis</h3>
      <p><strong>Riesgo anterior:</strong> ${escaparHtml(comparacion.riesgo_anterior || "-")}</p>
      <p><strong>Riesgo actual:</strong> ${escaparHtml(comparacion.riesgo_actual || "-")}</p>
      <p><strong>Cambio:</strong> ${escaparHtml(formatearTexto(comparacion.cambio_riesgo || "sin_datos"))}</p>
      <p>${escaparHtml(comparacion.resumen || "Sin resumen de comparación.")}</p>
    `;
  } catch (error) {
    console.error("Error al comparar análisis IA:", error);
    mostrarToast("No se pudo comparar el historial IA.", "error");
  }
}

function cerrarModalHistorialIA() {
  macroprocesoHistorialIAActual = null;
  ocultarModal("modalHistorialIA");
}

async function generarAccionDesdeEvidencia(evidenciaId) {
  try {
    const result = await fetchJson(`${API_URL}/api/macroprocesos/evidencias/${evidenciaId}/generar-accion`, {
      method: "POST"
    });

    mostrarToast(result.message || "Acción de mejora generada correctamente.", "success");
    await cargarDashboardAccionesMejora();
  } catch (error) {
    console.error("Error al generar acción desde evidencia:", error);
    mostrarToast("No se pudo generar la acción de mejora.", "error");
  }
}

async function generarAccionesDesdeEvidenciasMacroproceso(macroproceso) {
  try {
    const result = await fetchJson(`${API_URL}/api/macroprocesos/${macroproceso}/generar-acciones-desde-evidencias`, {
      method: "POST"
    });

    const creadas = result.acciones_creadas || 0;
    const existentes = result.acciones_existentes || 0;
    mostrarToast(`Se crearon ${creadas} acciones de mejora. Ya existían ${existentes}.`, creadas > 0 ? "success" : "info");
    await cargarDashboardAccionesMejora();
    await verAccionesMacroproceso(macroproceso);
  } catch (error) {
    console.error("Error al generar acciones desde evidencias:", error);
    mostrarToast("No se pudieron generar acciones de mejora desde evidencias.", "error");
  }
}

function abrirModalRegistroAccionMacroproceso(macroproceso) {
  macroprocesoRegistroAccionActual = macroproceso;
  limpiarFormularioAccionMacroproceso();
  poblarEvidenciasAccionMacroproceso(macroproceso);

  const titulo = document.getElementById("tituloModalRegistroAccionMacroproceso");
  if (titulo) {
    titulo.textContent = `Registrar acci\u00f3n - ${nombreMacroproceso(macroproceso)}`;
  }

  mostrarModal("modalRegistroAccionMacroproceso");
}

function cerrarModalRegistroAccionMacroproceso() {
  macroprocesoRegistroAccionActual = null;
  limpiarFormularioAccionMacroproceso();
  ocultarModal("modalRegistroAccionMacroproceso");
}

function limpiarFormularioAccionMacroproceso() {
  const form = document.getElementById("formAccionMacroproceso");
  if (form) form.reset();

  const prioridad = document.getElementById("accionMacroPrioridad");
  if (prioridad) prioridad.value = "media";

  const estado = document.getElementById("accionMacroEstado");
  if (estado) estado.value = "pendiente";
}

function poblarEvidenciasAccionMacroproceso(macroproceso) {
  const select = document.getElementById("accionMacroEvidencia");
  if (!select) return;

  const evidencias = evidenciasMacroprocesosGlobal[macroproceso] || [];
  select.innerHTML = `<option value="">Sin evidencia relacionada</option>`;

  evidencias.forEach((evidencia) => {
    const option = document.createElement("option");
    option.value = evidencia.id || "";
    option.textContent = `${evidencia.codigo || "Sin c\u00f3digo"} - ${evidencia.titulo || "Sin t\u00edtulo"}`;
    select.appendChild(option);
  });
}

function obtenerEvidenciaMacroprocesoPorId(macroproceso, evidenciaId) {
  const evidencias = evidenciasMacroprocesosGlobal[macroproceso] || [];
  return evidencias.find((item) => item.id === evidenciaId) || null;
}

async function guardarAccionMacroproceso(event) {
  event.preventDefault();

  if (!macroprocesoRegistroAccionActual) {
    mostrarToast("No se pudo identificar el macroproceso.", "error");
    return;
  }

  const titulo = document.getElementById("accionMacroTitulo")?.value.trim();
  const descripcion = document.getElementById("accionMacroDescripcion")?.value.trim();
  const responsable = document.getElementById("accionMacroResponsable")?.value.trim();
  const prioridad = document.getElementById("accionMacroPrioridad")?.value || "media";
  const estado = document.getElementById("accionMacroEstado")?.value || "pendiente";
  const fechaLimite = document.getElementById("accionMacroFechaLimite")?.value || null;
  const observacion = document.getElementById("accionMacroObservacion")?.value.trim();
  const evidenciaId = document.getElementById("accionMacroEvidencia")?.value || null;
  const evidencia = evidenciaId
    ? obtenerEvidenciaMacroprocesoPorId(macroprocesoRegistroAccionActual, evidenciaId)
    : null;

  if (!titulo || !descripcion) {
    mostrarToast("Complete los campos obligatorios.", "warning");
    return;
  }

  const payload = {
    macroproceso: macroprocesoRegistroAccionActual,
    origen_tipo: "manual_macroproceso",
    origen_id: evidenciaId || macroprocesoRegistroAccionActual,
    titulo,
    descripcion,
    responsable: responsable || null,
    prioridad,
    estado,
    fecha_limite: fechaLimite,
    observacion: observacion || null,
    evidencia_url: evidencia?.archivo_url || null
  };

  try {
    const macroproceso = macroprocesoRegistroAccionActual;
    await fetchJson(`${API_URL}/api/acciones-mejora/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    mostrarToast("Acci\u00f3n de mejora registrada correctamente.", "success");
    cerrarModalRegistroAccionMacroproceso();
    await cargarDashboardAccionesMejora();
    await verAccionesMacroproceso(macroproceso);
  } catch (error) {
    console.error("Error al registrar acci\u00f3n de macroproceso:", error);
    mostrarToast("No se pudo registrar la acci\u00f3n de mejora: " + error.message, "error");
  }
}

async function analizarPlanificacionIA() {
  try {
    mostrarToast("Analizando planificaci\u00f3n estrat\u00e9gica con IA...", "info");

    const result = await fetchJson(`${API_URL}/api/macroprocesos/planificacion/analizar`, {
      method: "POST"
    });

    abrirModalPlanificacionIA(result.data || {});
    mostrarToast("An\u00e1lisis de planificaci\u00f3n generado correctamente.", "success");
  } catch (error) {
    console.error("Error al analizar planificaci\u00f3n:", error);
    mostrarToast("Error al analizar planificaci\u00f3n: " + error.message, "error");
  }
}

function renderListaPlanificacion(items, vacio = "Sin información registrada.") {
  if (!Array.isArray(items) || items.length === 0) {
    return `<p class="text-muted">${escaparHtml(vacio)}</p>`;
  }

  return `
    <ul>
      ${items.map((item) => `<li>${escaparHtml(item)}</li>`).join("")}
    </ul>
  `;
}

function renderAccionesPlanificacion(acciones) {
  if (!Array.isArray(acciones) || acciones.length === 0) {
    return `<p class="text-muted">Sin acciones sugeridas registradas.</p>`;
  }

  return `
    <div class="planificacion-actions-grid">
      ${acciones.map((accion) => {
        const prioridad = accion.prioridad || "media";
        return `
          <article class="planificacion-action-card priority-${escaparAtributo(prioridad)}">
            <div class="evidence-card-header">
              ${renderBadge(prioridad)}
              <span class="evidence-code">${escaparHtml(accion.evidencia_relacionada || "Sin código")}</span>
            </div>
            <h3>${escaparHtml(accion.titulo || "Acción sugerida")}</h3>
            <p>${escaparHtml(accion.descripcion || "Sin descripción.")}</p>
            <p><strong>Responsable sugerido:</strong> ${escaparHtml(accion.responsable_sugerido || "Por definir")}</p>
          </article>
        `;
      }).join("")}
    </div>
  `;
}

function abrirModalPlanificacionIA(data) {
  const nivelRiesgo = String(data.nivel_riesgo || "medio").toLowerCase();
  const riesgoClase = ["bajo", "medio", "alto"].includes(nivelRiesgo) ? nivelRiesgo : "medio";
  const dashboard = data.dashboard || {};

  document.getElementById("contenidoPlanificacionIA").innerHTML = `
    <div class="analisis-section analisis-summary">
      <div>
        <span class="section-label">Nivel de riesgo</span>
        <span class="risk-badge risk-${escaparAtributo(riesgoClase)}">${escaparHtml(nivelRiesgo)}</span>
      </div>
      <div>
        <span class="section-label">Avance promedio</span>
        <p>${escaparHtml(dashboard.avance_promedio ?? 0)}%</p>
      </div>
      <div>
        <span class="section-label">Modelo usado</span>
        <p>${escaparHtml(data.modelo_usado || "-")}</p>
      </div>
    </div>

    <div class="analisis-section">
      <h3>Resumen</h3>
      <p>${escaparHtml(data.resumen || "Sin resumen generado.")}</p>
    </div>

    <div class="analisis-section">
      <h3>Riesgos detectados</h3>
      ${renderListaPlanificacion(data.riesgos)}
    </div>

    <div class="analisis-section">
      <h3>Evidencias críticas</h3>
      ${renderListaPlanificacion(data.evidencias_criticas, "Sin evidencias críticas registradas.")}
    </div>

    <div class="analisis-section">
      <h3>Recomendaciones</h3>
      ${renderListaPlanificacion(data.recomendaciones)}
    </div>

    <div class="analisis-section">
      <h3>Acciones sugeridas</h3>
      ${renderAccionesPlanificacion(data.acciones_sugeridas)}
    </div>

    <div class="analisis-section">
      <h3>Observación general</h3>
      <p>${escaparHtml(data.observacion_general || "Sin observación general.")}</p>
    </div>
  `;

  mostrarModal("modalPlanificacionIA");
}

function cerrarModalPlanificacionIA() {
  ocultarModal("modalPlanificacionIA");
}

async function analizarGestionAcademicaIA() {
  try {
    mostrarToast("Analizando gestión académica con IA...", "info");

    const result = await fetchJson(`${API_URL}/api/macroprocesos/gestion-academica/analizar`, {
      method: "POST"
    });

    abrirModalGestionAcademicaIA(result.data || {});
    mostrarToast("Análisis de gestión académica generado correctamente.", "success");
  } catch (error) {
    console.error("Error al analizar gestión académica:", error);
    mostrarToast(
      "No se pudo generar el análisis de gestión académica. Revise la conexión con el backend o la configuración del agente.",
      "error"
    );
  }
}

function renderIndicadoresGestionAcademica(indicadores) {
  const items = [
    ["Total de evidencias", indicadores.total_evidencias ?? 0],
    ["Pendientes", indicadores.pendientes ?? 0],
    ["En proceso", indicadores.en_proceso ?? 0],
    ["Completadas", indicadores.completadas ?? 0],
    ["Observadas", indicadores.observadas ?? 0],
    ["Avance promedio", `${indicadores.avance_promedio ?? 0}%`],
    ["Prioridad alta", indicadores.prioridad_alta ?? 0],
    ["Sin sustento documental", indicadores.sin_sustento_documental ?? 0]
  ];

  return `
    <div class="indicator-grid">
      ${items.map(([titulo, valor]) => `
        <div class="summary-card">
          <span>${escaparHtml(titulo)}</span>
          <strong>${escaparHtml(valor)}</strong>
        </div>
      `).join("")}
    </div>
  `;
}

function abrirModalGestionAcademicaIA(data) {
  const indicadores = data.indicadores || {};
  const total = Number(indicadores.total_evidencias ?? 0);
  const nivelRiesgo = String(data.nivel_riesgo || "medio").toLowerCase();
  const riesgoClase = ["bajo", "medio", "alto"].includes(nivelRiesgo) ? nivelRiesgo : "medio";

  if (!total) {
    document.getElementById("contenidoGestionAcademicaIA").innerHTML = `
      <div class="analisis-section">
        <p class="text-muted">No se encontraron evidencias suficientes para analizar la gestión académica.</p>
      </div>
    `;
    mostrarModal("modalGestionAcademicaIA");
    return;
  }

  document.getElementById("contenidoGestionAcademicaIA").innerHTML = `
    <div class="analisis-section analisis-summary">
      <div>
        <span class="section-label">Nivel de riesgo</span>
        <span class="risk-badge risk-${escaparAtributo(riesgoClase)}">${escaparHtml(nivelRiesgo)}</span>
      </div>
      <div>
        <span class="section-label">Avance promedio</span>
        <p>${escaparHtml(indicadores.avance_promedio ?? 0)}%</p>
      </div>
      <div>
        <span class="section-label">Modelo usado</span>
        <p>${escaparHtml(data.modelo_usado || "-")}</p>
      </div>
    </div>

    <div class="analisis-section">
      <h3>Resumen</h3>
      <p>${escaparHtml(data.resumen || "Sin resumen generado.")}</p>
    </div>

    <div class="analisis-section">
      <h3>Indicadores</h3>
      ${renderIndicadoresGestionAcademica(indicadores)}
    </div>

    <div class="analisis-section">
      <h3>Riesgos detectados</h3>
      ${renderListaPlanificacion(data.riesgos)}
    </div>

    <div class="analisis-section">
      <h3>Acuerdos pendientes</h3>
      ${renderListaPlanificacion(data.acuerdos_pendientes, "Sin acuerdos pendientes registrados.")}
    </div>

    <div class="analisis-section">
      <h3>Observaciones académicas</h3>
      ${renderListaPlanificacion(data.observaciones_academicas, "Sin observaciones académicas registradas.")}
    </div>

    <div class="analisis-section">
      <h3>Evidencias críticas</h3>
      ${renderListaPlanificacion(data.evidencias_criticas, "Sin evidencias críticas registradas.")}
    </div>

    <div class="analisis-section">
      <h3>Recomendaciones</h3>
      ${renderListaPlanificacion(data.recomendaciones)}
    </div>

    <div class="analisis-section">
      <h3>Acciones sugeridas</h3>
      ${renderAccionesPlanificacion(data.acciones_sugeridas)}
    </div>

    <div class="analisis-section">
      <h3>Observación general</h3>
      <p>${escaparHtml(data.observacion_general || "Sin observación general.")}</p>
    </div>
  `;

  mostrarModal("modalGestionAcademicaIA");
}

function cerrarModalGestionAcademicaIA() {
  ocultarModal("modalGestionAcademicaIA");
}

async function analizarMejoraContinuaIA() {
  try {
    mostrarToast("Analizando mejora continua con IA...", "info");

    const result = await fetchJson(`${API_URL}/api/macroprocesos/mejora-continua/analizar`, {
      method: "POST"
    });

    abrirModalMejoraContinuaIA(result.data || {});
    mostrarToast("Diagn?stico integral generado correctamente.", "success");
  } catch (error) {
    console.error("Error al analizar mejora continua:", error);
    mostrarToast(
      "No se pudo generar el análisis integral de mejora continua. Revise la conexión con el backend o la configuración del agente coordinador.",
      "error"
    );
  }
}

function renderIndicadoresGenerales(indicadores) {
  const items = [
    ["Macroprocesos", indicadores.total_macroprocesos ?? 0],
    ["Evidencias", indicadores.total_evidencias_macroprocesos ?? 0],
    ["Sílabos", indicadores.total_silabos ?? 0],
    ["Brechas", indicadores.total_brechas ?? 0],
    ["Brechas alta prioridad", indicadores.brechas_alta_prioridad ?? 0],
    ["Acciones de mejora", indicadores.total_acciones_mejora ?? 0],
    ["Acciones pendientes", indicadores.acciones_pendientes ?? 0],
    ["Acciones en proceso", indicadores.acciones_en_proceso ?? 0],
    ["Acciones completadas", indicadores.acciones_completadas ?? 0]
  ];

  return `
    <div class="general-indicator-grid">
      ${items.map(([titulo, valor]) => `
        <div class="summary-card">
          <span>${escaparHtml(titulo)}</span>
          <strong>${escaparHtml(valor)}</strong>
        </div>
      `).join("")}
    </div>
  `;
}

function renderEstadoMacroprocesos(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return `<p class="text-muted">No se encontraron estados por macroproceso.</p>`;
  }

  return `
    <div class="macroprocess-status-grid">
      ${items.map((item) => {
        const riesgo = String(item.nivel_riesgo || "medio").toLowerCase();
        const riesgoClase = ["bajo", "medio", "alto"].includes(riesgo) ? riesgo : "medio";
        return `
          <article class="macroprocess-status-card risk-${escaparAtributo(riesgoClase)}">
            <div class="evidence-card-header">
              <h3>${escaparHtml(item.macroproceso || "Macroproceso")}</h3>
              <span class="risk-badge risk-${escaparAtributo(riesgoClase)}">${escaparHtml(riesgoClase)}</span>
            </div>
            <p><strong>Avance promedio:</strong> ${escaparHtml(item.avance_promedio ?? 0)}%</p>
            ${renderListaPlanificacion(item.hallazgos, "Sin hallazgos registrados.")}
          </article>
        `;
      }).join("")}
    </div>
  `;
}

function renderAccionesPrioritarias(acciones) {
  if (!Array.isArray(acciones) || acciones.length === 0) {
    return `<p class="text-muted">Sin acciones prioritarias registradas.</p>`;
  }

  return `
    <div class="priority-actions-grid">
      ${acciones.map((accion) => {
        const prioridad = accion.prioridad || "media";
        return `
          <article class="priority-action-card priority-${escaparAtributo(prioridad)}">
            <div class="evidence-card-header">
              ${renderBadge(prioridad)}
              <span class="evidence-code">${escaparHtml(accion.macroproceso_relacionado || "Mejora continua")}</span>
            </div>
            <h3>${escaparHtml(accion.titulo || "Acción prioritaria")}</h3>
            <p>${escaparHtml(accion.descripcion || "Sin descripción.")}</p>
            <p><strong>Responsable sugerido:</strong> ${escaparHtml(accion.responsable_sugerido || "Comité académico")}</p>
          </article>
        `;
      }).join("")}
    </div>
  `;
}

function abrirModalMejoraContinuaIA(data) {
  const indicadores = data.indicadores_generales || {};
  const totalDatos = Number(indicadores.total_evidencias_macroprocesos || 0)
    + Number(indicadores.total_silabos || 0)
    + Number(indicadores.total_brechas || 0)
    + Number(indicadores.total_acciones_mejora || 0);
  const nivelRiesgo = String(data.nivel_riesgo_general || "medio").toLowerCase();
  const riesgoClase = ["bajo", "medio", "alto"].includes(nivelRiesgo) ? nivelRiesgo : "medio";

  if (!totalDatos) {
    document.getElementById("contenidoMejoraContinuaIA").innerHTML = `
      <div class="analisis-section">
        <p class="text-muted">No se encontraron datos suficientes para generar el diagn?stico integral.</p>
      </div>
    `;
    mostrarModal("modalMejoraContinuaIA");
    return;
  }

  document.getElementById("contenidoMejoraContinuaIA").innerHTML = `
    <div class="analisis-section analisis-summary">
      <div>
        <span class="section-label">Nivel de riesgo general</span>
        <span class="general-risk-badge risk-badge risk-${escaparAtributo(riesgoClase)}">${escaparHtml(riesgoClase)}</span>
      </div>
      <div>
        <span class="section-label">Macroprocesos</span>
        <p>${escaparHtml(indicadores.total_macroprocesos ?? 3)}</p>
      </div>
      <div>
        <span class="section-label">Modelo usado</span>
        <p>${escaparHtml(data.modelo_usado || "-")}</p>
      </div>
    </div>

    <div class="analisis-section">
      <h3>Resumen general</h3>
      <p>${escaparHtml(data.resumen_general || "Sin resumen generado.")}</p>
    </div>

    <div class="analisis-section">
      <h3>Indicadores generales</h3>
      ${renderIndicadoresGenerales(indicadores)}
    </div>

    <div class="analisis-section">
      <h3>Estado por macroproceso</h3>
      ${renderEstadoMacroprocesos(data.estado_macroprocesos)}
    </div>

    <div class="analisis-section">
      <h3>Macroprocesos críticos</h3>
      ${renderListaPlanificacion(data.macroprocesos_criticos, "Sin macroprocesos críticos registrados.")}
    </div>

    <div class="analisis-section">
      <h3>Hallazgos integrados</h3>
      ${renderListaPlanificacion(data.hallazgos_integrados, "Sin hallazgos integrados registrados.")}
    </div>

    <div class="analisis-section">
      <h3>Evidencias críticas</h3>
      ${renderListaPlanificacion(data.evidencias_criticas, "Sin evidencias críticas registradas.")}
    </div>

    <div class="analisis-section">
      <h3>Acciones prioritarias</h3>
      ${renderAccionesPrioritarias(data.acciones_prioritarias)}
    </div>

    <div class="analisis-section">
      <h3>Recomendaciones para el comité académico</h3>
      ${renderListaPlanificacion(data.recomendaciones_comite, "Sin recomendaciones registradas.")}
    </div>

    <div class="analisis-section">
      <h3>Decisión sugerida</h3>
      <p>${escaparHtml(data.decision_sugerida || "Sin decisión sugerida.")}</p>
    </div>

    <div class="analisis-section">
      <h3>Observación general</h3>
      <p>${escaparHtml(data.observacion_general || "Sin observación general.")}</p>
    </div>
  `;

  mostrarModal("modalMejoraContinuaIA");
}

function cerrarModalMejoraContinuaIA() {
  ocultarModal("modalMejoraContinuaIA");
}

async function exportarReporteIntegral() {
  try {
    mostrarToast("Generando reporte integral...", "info");
    const reporte = await fetchJson(`${API_URL}/api/macroprocesos/reporte-integral`);
    reporteIntegralActual = reporte;
    abrirModalReporteIntegral(reporte);
    mostrarToast("Reporte integral generado correctamente.", "success");
  } catch (error) {
    console.error("Error al generar reporte integral:", error);
    mostrarToast("No se pudo generar el reporte integral: " + error.message, "error");
  }
}

function abrirModalReporteIntegral(reporte) {
  const contenedor = document.getElementById("contenidoReporteIntegral");
  if (!contenedor) return;

  contenedor.innerHTML = renderReporteIntegral(reporte || {});
  mostrarModal("modalReporteIntegral");
}

function cerrarModalReporteIntegral() {
  ocultarModal("modalReporteIntegral");
}

function descargarReporteIntegralJson() {
  if (!reporteIntegralActual) {
    mostrarToast("No hay reporte disponible para descargar.", "warning");
    return;
  }

  const blob = new Blob([JSON.stringify(reporteIntegralActual, null, 2)], {
    type: "application/json;charset=utf-8"
  });
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = "reporte_mejora_continua.json";
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  URL.revokeObjectURL(url);
}

function imprimirReporteIntegral() {
  window.print();
}

function renderReporteIntegral(reporte) {
  const fecha = reporte.fecha_generacion
    ? new Date(reporte.fecha_generacion).toLocaleString()
    : "Sin fecha";

  return `
    <header class="report-header">
      <h1>${escaparHtml(reporte.titulo || "Reporte Integral de Mejora Continua")}</h1>
      <p><strong>Fecha de generaci&oacute;n:</strong> ${escaparHtml(fecha)}</p>
    </header>

    <section class="report-section">
      <h2>Resumen general</h2>
      <div class="report-summary-grid">${renderReporteResumen(reporte.resumen || {})}</div>
    </section>

    <section class="report-section">
      <h2>Sem&aacute;foro por macroproceso</h2>
      <div class="report-card-grid">${renderReporteSemaforo(reporte.semaforo || [])}</div>
    </section>

    <section class="report-section">
      <h2>Evidencias cr&iacute;ticas</h2>
      ${renderReporteLista(reporte.evidencias_criticas || [], renderReporteEvidenciaCritica, "No hay evidencias cr&iacute;ticas registradas.")}
    </section>

    <section class="report-section">
      <h2>Alertas activas</h2>
      ${renderReporteLista(reporte.alertas_activas || [], renderReporteAlerta, "No hay alertas activas.")}
    </section>

    <section class="report-section">
      <h2>Acciones de mejora</h2>
      ${renderReporteLista(reporte.acciones_mejora || [], renderReporteAccion, "No hay acciones de mejora registradas.")}
    </section>

    <section class="report-section">
      <h2>&Uacute;ltimos an&aacute;lisis IA</h2>
      ${renderReporteLista(reporte.ultimos_analisis_ia || [], renderReporteAnalisis, "No hay an&aacute;lisis IA registrados.")}
    </section>

    <section class="report-section">
      <h2>Validaciones documentales IA</h2>
      ${renderReporteLista(reporte.validaciones_documentales || [], renderReporteValidacion, "No hay validaciones documentales registradas.")}
    </section>

    <section class="report-section">
      <h2>Brechas curriculares</h2>
      ${renderReporteLista(reporte.brechas_curriculares || [], renderReporteBrecha, "No hay brechas curriculares registradas.")}
    </section>

    <section class="report-section">
      <h2>Recomendaciones generales</h2>
      ${renderReporteRecomendaciones(reporte.recomendaciones_generales || [])}
    </section>
  `;
}

function renderReporteResumen(resumen) {
  const items = [
    ["Macroprocesos", resumen.total_macroprocesos],
    ["Evidencias", resumen.total_evidencias],
    ["Alertas activas", resumen.total_alertas_activas],
    ["Alertas cr&iacute;ticas", resumen.total_alertas_criticas],
    ["Acciones de mejora", resumen.total_acciones_mejora],
    ["Acciones pendientes", resumen.acciones_pendientes],
    ["Acciones en proceso", resumen.acciones_en_proceso],
    ["Acciones completadas", resumen.acciones_completadas],
    ["An&aacute;lisis IA", resumen.total_analisis_ia],
    ["Validaciones IA", resumen.total_validaciones_ia]
  ];

  return items.map(([titulo, valor]) => `
    <article class="report-card">
      <span>${titulo}</span>
      <strong>${escaparHtml(valor ?? 0)}</strong>
    </article>
  `).join("");
}

function renderReporteSemaforo(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return `<p class="text-muted">No hay informaci&oacute;n de sem&aacute;foro registrada.</p>`;
  }

  return items.map((item) => `
    <article class="report-card report-status-${escaparAtributo(item.color || "amarillo")}">
      <h3>${escaparHtml(item.nombre || nombreMacroproceso(item.macroproceso))}</h3>
      <p><strong>Estado:</strong> ${escaparHtml(formatearTexto(item.color || "-"))}</p>
      <p><strong>Avance:</strong> ${escaparHtml(item.avance_promedio ?? 0)}%</p>
      <p><strong>Alertas cr&iacute;ticas:</strong> ${escaparHtml(item.alertas_criticas ?? 0)}</p>
      <p><strong>Riesgo IA:</strong> ${escaparHtml(formatearTexto(item.riesgo_ia || "sin_datos"))}</p>
      <p>${escaparHtml(item.mensaje || "-")}</p>
    </article>
  `).join("");
}

function renderReporteLista(items, renderer, emptyMessage) {
  if (!Array.isArray(items) || items.length === 0) {
    return `<p class="text-muted">${emptyMessage}</p>`;
  }

  return `<div class="report-card-grid">${items.map(renderer).join("")}</div>`;
}

function renderReporteEvidenciaCritica(item) {
  return `
    <article class="report-card">
      <h3>${escaparHtml(item.codigo || "Evidencia")}: ${escaparHtml(item.titulo || "-")}</h3>
      <p><strong>Macroproceso:</strong> ${escaparHtml(nombreMacroproceso(item.macroproceso))}</p>
      <p><strong>Estado:</strong> ${escaparHtml(formatearTexto(item.estado || "-"))}</p>
      <p><strong>Prioridad:</strong> ${escaparHtml(formatearTexto(item.prioridad || "-"))}</p>
      <p><strong>Avance:</strong> ${escaparHtml(item.avance ?? 0)}%</p>
      <p><strong>Responsable:</strong> ${escaparHtml(item.responsable || "-")}</p>
    </article>
  `;
}

function renderReporteAlerta(item) {
  return `
    <article class="report-card">
      <h3>${escaparHtml(item.titulo || "Alerta inteligente")}</h3>
      <p><strong>Macroproceso:</strong> ${escaparHtml(nombreMacroproceso(item.macroproceso))}</p>
      <p><strong>Nivel:</strong> ${escaparHtml(formatearTexto(item.nivel_alerta || "-"))}</p>
      <p><strong>Descripci&oacute;n:</strong> ${escaparHtml(item.descripcion || "-")}</p>
      <p><strong>Recomendaci&oacute;n:</strong> ${escaparHtml(item.recomendacion || "-")}</p>
    </article>
  `;
}

function renderReporteAccion(item) {
  return `
    <article class="report-card">
      <h3>${escaparHtml(item.titulo || "Acci\u00f3n de mejora")}</h3>
      <p><strong>Origen:</strong> ${escaparHtml(formatearTexto(item.origen_tipo || "-"))}</p>
      <p><strong>Estado:</strong> ${escaparHtml(formatearTexto(item.estado || "-"))}</p>
      <p><strong>Prioridad:</strong> ${escaparHtml(formatearTexto(item.prioridad || "-"))}</p>
      <p><strong>Responsable:</strong> ${escaparHtml(item.responsable || "-")}</p>
      <p><strong>Descripci&oacute;n:</strong> ${escaparHtml(item.descripcion || "-")}</p>
    </article>
  `;
}

function renderReporteAnalisis(item) {
  return `
    <article class="report-card">
      <h3>${escaparHtml(nombreMacroproceso(item.macroproceso))}</h3>
      <p><strong>Tipo:</strong> ${escaparHtml(formatearTexto(item.tipo_analisis || "-"))}</p>
      <p><strong>Riesgo:</strong> ${escaparHtml(formatearTexto(item.nivel_riesgo || "-"))}</p>
      <p><strong>Modelo:</strong> ${escaparHtml(item.modelo_usado || "-")}</p>
      <p>${escaparHtml(item.resumen || "Sin resumen registrado.")}</p>
    </article>
  `;
}

function renderReporteValidacion(item) {
  return `
    <article class="report-card">
      <h3>${escaparHtml(item.evidencia_id || "Evidencia")}</h3>
      <p><strong>Macroproceso:</strong> ${escaparHtml(nombreMacroproceso(item.macroproceso))}</p>
      <p><strong>Nivel de validez:</strong> ${escaparHtml(formatearTexto(item.nivel_validez || "-"))}</p>
      <p><strong>Pertinencia:</strong> ${escaparHtml(formatearTexto(item.pertinencia || "-"))}</p>
      <p>${escaparHtml(item.resumen || "Sin resumen registrado.")}</p>
    </article>
  `;
}

function renderReporteBrecha(item) {
  return `
    <article class="report-card">
      <h3>${escaparHtml(item.asignatura || "Brecha curricular")}</h3>
      <p><strong>Tipo:</strong> ${escaparHtml(formatearTexto(item.tipo_brecha || "-"))}</p>
      <p><strong>Prioridad:</strong> ${escaparHtml(formatearTexto(item.prioridad || "-"))}</p>
      <p><strong>Problema:</strong> ${escaparHtml(item.descripcion || "-")}</p>
      <p><strong>Recomendaci&oacute;n:</strong> ${escaparHtml(item.recomendacion || "-")}</p>
    </article>
  `;
}

function renderReporteRecomendaciones(recomendaciones) {
  if (!Array.isArray(recomendaciones) || recomendaciones.length === 0) {
    return `<p class="text-muted">No hay recomendaciones generales registradas.</p>`;
  }

  return `
    <ul class="report-recommendations">
      ${recomendaciones.map((item) => `<li>${escaparHtml(item)}</li>`).join("")}
    </ul>
  `;
}

async function cargarDatos() {
  await cargarDashboard();
  await cargarSilabos();
  await cargarDashboardAccionesMejora();
  await cargarSemaforoCumplimiento();
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
    const porcentaje = silabo.estado === "completo" && Number(silabo.porcentaje_cumplimiento || 0) === 0
      ? 100
      : Number(silabo.porcentaje_cumplimiento || 0);
    const botonArchivo = archivoUrl
      ? `<a class="btn btn-primary archivo-btn" href="${archivoUrl}" target="_blank" rel="noopener noreferrer">Ver archivo</a>`
      : `<button class="btn btn-disabled" disabled>Sin archivo</button>`;

    tr.innerHTML = `
      <td>${silabo.ciclo}</td>
      <td>${silabo.codigo_asignatura}</td>
      <td>${silabo.asignatura}</td>
      <td><span class="estado ${silabo.estado}">${silabo.estado}</span></td>
      <td>${porcentaje}%</td>
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
                <button class="menu-item" onclick="seleccionarArchivo('${silabo.id}')">Actualizar archivo</button>
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

  const ciclo = Number(document.getElementById("ciclo").value);
  const creditos = obtenerNumeroOpcional("creditos");
  const totalHorasSemestrales = obtenerNumeroOpcional("horasSemestrales");
  const totalHorasSemanales = obtenerNumeroOpcional("horasSemanales");
  const duracionSemanas = Number(document.getElementById("duracion").value);
  const fechaInicio = document.getElementById("fechaInicio").value || null;
  const fechaFin = document.getElementById("fechaFin").value || null;
  const correoDocente = document.getElementById("correo").value.trim();
  const inputArchivoRegistro = document.getElementById("archivoSilaboRegistro");
  const archivoRegistro = inputArchivoRegistro?.files?.[0] || null;

  if (!Number.isInteger(ciclo) || ciclo < 1 || ciclo > 10) {
    mostrarToast("El ciclo debe estar entre 1 y 10.", "error");
    return;
  }

  if (
    creditos === false ||
    totalHorasSemestrales === false ||
    totalHorasSemanales === false ||
    !Number.isFinite(duracionSemanas) ||
    duracionSemanas <= 0
  ) {
    mostrarToast("No se permiten valores negativos en los datos del sílabo.", "error");
    return;
  }

  if (fechaInicio && fechaFin && fechaFin < fechaInicio) {
    mostrarToast("La fecha de culminacion no puede ser menor que la fecha de inicio.", "error");
    return;
  }

  if (correoDocente && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(correoDocente)) {
    mostrarToast("Ingrese un correo docente valido.", "error");
    return;
  }

  const data = {
    semestre_academico: document.getElementById("semestre").value,
    facultad: document.getElementById("facultad").value,
    programa_estudios: document.getElementById("programa").value,
    asignatura: document.getElementById("asignatura").value,
    codigo_asignatura: document.getElementById("codigo").value,
    ciclo,
    modalidad: document.getElementById("modalidad").value,
    creditos,
    total_horas_semestrales: totalHorasSemestrales,
    total_horas_semanales: totalHorasSemanales,
    fecha_inicio: fechaInicio,
    fecha_culminacion: fechaFin,
    duracion_semanas: duracionSemanas,
    docente_responsable: document.getElementById("docente").value,
    correo_docente: correoDocente,
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

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "Error al registrar el sílabo");
    }

    const silaboCreado = Array.isArray(result.data) ? result.data[0] : result.data;
    const silaboId = silaboCreado?.id;

    if (archivoRegistro) {
      if (!silaboId) {
        throw new Error("El silabo se registro, pero no se recibio el ID para subir el archivo.");
      }
      await subirArchivoSilaboConId(silaboId, archivoRegistro);
    }

    mostrarToast("Sílabo registrado correctamente.", "success");
    event.target.reset();
    await cargarDatos();
  } catch (error) {
    console.error(error);
    mostrarToast("No se pudo registrar el sílabo: " + error.message, "error");
  }
}

function obtenerNumeroOpcional(inputId) {
  const valor = document.getElementById(inputId).value;
  if (valor === "") return null;

  const numero = Number(valor);
  if (!Number.isFinite(numero) || numero < 0) return false;

  return numero;
}

function setInputValueIfExists(id, value) {
  const input = document.getElementById(id);
  if (!input) return;
  if (value !== null && value !== undefined && value !== "") {
    input.value = value;
  }
}

async function extraerDatosDesdeArchivoRegistro() {
  const input = document.getElementById("archivoSilaboRegistro");
  const archivo = input?.files?.[0];

  if (!archivo) {
    mostrarToast("Seleccione un archivo DOCX o PDF.", "warning");
    return;
  }

  const formData = new FormData();
  formData.append("archivo", archivo);

  try {
    mostrarToast("Leyendo archivo del silabo...", "info");

    const response = await fetch(`${API_URL}/api/silabos/extraer-datos-archivo`, {
      method: "POST",
      body: formData
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "No se pudo leer el archivo.");
    }

    const data = result.data || {};

    setInputValueIfExists("asignatura", data.asignatura);
    setInputValueIfExists("codigo", data.codigo_asignatura);
    setInputValueIfExists("ciclo", data.ciclo);
    setInputValueIfExists("modalidad", data.modalidad);
    setInputValueIfExists("creditos", data.creditos);
    setInputValueIfExists("horasSemestrales", data.total_horas_semestrales);
    setInputValueIfExists("horasSemanales", data.total_horas_semanales);
    setInputValueIfExists("fechaInicio", data.fecha_inicio);
    setInputValueIfExists("fechaFin", data.fecha_culminacion);
    setInputValueIfExists("duracion", data.duracion_semanas);
    setInputValueIfExists("docente", data.docente_responsable);
    setInputValueIfExists("correo", data.correo_docente);

    mostrarToast("Datos extraidos. Revise y corrija si es necesario.", "success");
  } catch (error) {
    console.error(error);
    mostrarToast("Error al leer archivo: " + error.message, "error");
  }
}

async function subirArchivoSilaboConId(silaboId, archivo) {
  const formData = new FormData();
  formData.append("archivo", archivo);

  const response = await fetch(`${API_URL}/api/silabos/${silaboId}/archivo`, {
    method: "POST",
    body: formData
  });

  const result = await response.json();

  if (!response.ok) {
    throw new Error(result.detail || "El silabo se registro, pero no se pudo subir el archivo.");
  }

  return result;
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
          ${item.cumple ? "?" : "?"}
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
          <strong>${item.estado_anterior}</strong> ? <strong>${item.estado_nuevo}</strong><br>
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
      mostrarToast(result.detail || "No se pudo validar el documento.", "error");
      return;
    }

    mostrarToast(`Documento validado. Cumplimiento: ${result.porcentaje_cumplimiento}%.`, "success");
    await cargarDatos();
    await verValidacion(id);
  } catch (error) {
    console.error(error);
    mostrarToast("Error al validar documento.", "error");
  }
}

async function eliminarSilabo(id) {
  const confirmar = await confirmarAccion("¿Seguro que deseas eliminar este sílabo?");

  if (!confirmar) return;

  try {
    const response = await fetch(`${API_URL}/api/silabos/${id}`, {
      method: "DELETE"
    });

    if (!response.ok) {
      throw new Error("Error al eliminar el sílabo");
    }

    mostrarToast("Sílabo eliminado correctamente.", "success");
    await cargarDatos();
  } catch (error) {
    console.error(error);
    mostrarToast("No se pudo eliminar el sílabo.", "error");
  }
}
function seleccionarArchivo(id) {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".docx,.pdf";

  input.onchange = async () => {
    const archivo = input.files[0];

    if (!archivo) return;
    const confirmado = await confirmarAccion("Esto reemplazará el archivo actual del sílabo. ¿Desea continuar?");
    if (!confirmado) return;

    await subirArchivoSilabo(id, archivo);
  };

  input.click();
}

async function subirArchivoSilabo(id, archivo) {
  try {
    await subirArchivoSilaboConId(id, archivo);
    mostrarToast("Archivo del silabo actualizado correctamente.", "success");
    await cargarDatos();
  } catch (error) {
    console.error(error);
    mostrarToast("Error al actualizar el archivo: " + error.message, "error");
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
  mostrarToast(mensaje, tipo);
}

function mostrarToast(mensaje, tipo = "info") {
  let contenedor = document.getElementById("toastContainer");
  if (!contenedor) {
    contenedor = document.createElement("div");
    contenedor.id = "toastContainer";
    contenedor.className = "toast-container";
    document.body.appendChild(contenedor);
  }

  const toast = document.createElement("div");
  toast.className = `toast toast-${tipo}`;
  toast.textContent = mensaje;
  contenedor.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("toast-hide");
    setTimeout(() => toast.remove(), 300);
  }, 3000);
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

function confirmarAccion(mensaje) {
  return abrirModalConfirmacion({
    titulo: "Confirmar acción",
    mensaje,
    textoConfirmar: "Aceptar",
    tipo: "danger"
  });
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
    mostrarToast("Estado inválido. Use: pendiente, completo, observado o incompleto.", "warning");
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
      mostrarToast(result.detail || "No se pudo actualizar el estado.", "error");
      return;
    }

    cerrarModalCambioEstado();
    mostrarToast("Estado actualizado correctamente.", "success");
    await cargarDatos();
    await verHistorial(id);
  } catch (error) {
    mostrarToast("Error al actualizar el estado.", "error");
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
      mostrarToast(result.detail || "No se pudo obtener el sílabo.", "error");
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
    mostrarToast("Error al editar el sílabo.", "error");
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
    mostrarToast("Complete asignatura, código y ciclo.", "warning");
    return;
  }

  if (!Number.isInteger(numeroCiclo) || numeroCiclo < 1 || numeroCiclo > 10) {
    mostrarToast("El ciclo debe ser un número entre 1 y 10.", "warning");
    return;
  }

  if (numeroCreditos !== null && (!Number.isFinite(numeroCreditos) || numeroCreditos < 0)) {
    mostrarToast("Los créditos deben ser un número válido.", "warning");
    return;
  }

  if (archivoUrl && !normalizarEnlaceArchivo(archivoUrl)) {
    mostrarToast("Ingrese un enlace válido de Google Drive o Supabase Storage.", "warning");
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
      mostrarToast(result.detail || "No se pudo actualizar el sílabo.", "error");
      return;
    }

    cerrarModalEditarSilabo();
    mostrarToast("Información del sílabo actualizada correctamente.", "success");
    await cargarDatos();
    await verHistorial(id);
  } catch (error) {
    mostrarToast("Error al editar el sílabo.", "error");
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
    mostrarToast("Error al analizar el sílabo: " + error.message, "error");
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
      mostrarToast("Este sílabo todavía no tiene análisis. Presiona primero 'Analizar IA'.", "warning");
      return;
    }

    abrirModalAnalisis(analisis);
  } catch (error) {
    console.error("Error al obtener análisis:", error);
    mostrarToast("Error al obtener análisis: " + error.message, "error");
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

function normalizarValor(valor) {
  return String(valor ?? "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim();
}

function contarPorCampo(data, campo, valor) {
  const valorNormalizado = normalizarValor(valor);
  return data.filter((item) => normalizarValor(item[campo]) === valorNormalizado).length;
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

function escaparAtributo(valor) {
  return escaparHtml(valor).replaceAll("`", "&#096;");
}

function renderSummaryCard(titulo, valor) {
  return `
    <div class="summary-card">
      <span>${escaparHtml(titulo)}</span>
      <strong>${escaparHtml(valor)}</strong>
    </div>
  `;
}

function abrirModalTrazabilidad(data) {
  trazabilidadDataGlobal = Array.isArray(data) ? data : [];
  prepararFiltrosTrazabilidad();
  renderizarResumenTrazabilidad();
  renderizarTrazabilidadFiltrada();
  mostrarModal("modalTrazabilidad");
}

function cerrarModalTrazabilidad() {
  ocultarModal("modalTrazabilidad");
}

function prepararFiltrosTrazabilidad() {
  const buscar = document.getElementById("buscarTrazabilidad");
  const coherencia = document.getElementById("filtroCoherenciaTrazabilidad");
  const tipo = document.getElementById("filtroTipoTrazabilidad");

  buscar.value = "";
  coherencia.value = "todos";
  tipo.value = "todos";

  buscar.oninput = renderizarTrazabilidadFiltrada;
  coherencia.onchange = renderizarTrazabilidadFiltrada;
  tipo.onchange = renderizarTrazabilidadFiltrada;
}

function renderizarResumenTrazabilidad() {
  const resumen = document.getElementById("resumenTrazabilidad");
  const data = trazabilidadDataGlobal;

  resumen.innerHTML = [
    renderSummaryCard("Total de relaciones", data.length),
    renderSummaryCard("Coherencia alta", contarPorCampo(data, "nivel_coherencia", "alto")),
    renderSummaryCard("Coherencia media", contarPorCampo(data, "nivel_coherencia", "medio")),
    renderSummaryCard("Coherencia baja", contarPorCampo(data, "nivel_coherencia", "bajo")),
    renderSummaryCard("Progresión adecuada", contarPorCampo(data, "tipo_relacion", "progresion_adecuada")),
    renderSummaryCard("Repetición", contarPorCampo(data, "tipo_relacion", "repeticion")),
    renderSummaryCard("Vacío formativo", contarPorCampo(data, "tipo_relacion", "vacio_formativo")),
    renderSummaryCard("Continuidad temática", contarPorCampo(data, "tipo_relacion", "continuidad_tematica"))
  ].join("");
}

function renderizarTrazabilidadFiltrada() {
  const contenedor = document.getElementById("contenidoTrazabilidad");
  const busqueda = normalizarValor(document.getElementById("buscarTrazabilidad").value);
  const filtroCoherencia = document.getElementById("filtroCoherenciaTrazabilidad").value;
  const filtroTipo = document.getElementById("filtroTipoTrazabilidad").value;

  if (trazabilidadDataGlobal.length === 0) {
    contenedor.innerHTML = `
      <p class="text-muted">No hay trazabilidad registrada. Primero ejecuta el análisis de trazabilidad curricular.</p>
    `;
    return;
  }

  const filtrados = trazabilidadDataGlobal.filter((item) => {
    const textoAsignaturas = normalizarValor(`${item.asignatura_origen ?? ""} ${item.asignatura_destino ?? ""}`);
    const coincideBusqueda = !busqueda || textoAsignaturas.includes(busqueda);
    const coincideCoherencia = filtroCoherencia === "todos" || normalizarValor(item.nivel_coherencia) === filtroCoherencia;
    const coincideTipo = filtroTipo === "todos" || normalizarValor(item.tipo_relacion) === filtroTipo;
    return coincideBusqueda && coincideCoherencia && coincideTipo;
  });

  if (filtrados.length === 0) {
    contenedor.innerHTML = `<p class="text-muted">No se encontraron relaciones con los filtros aplicados.</p>`;
    return;
  }

  contenedor.innerHTML = filtrados.map((item) => {
    const coherencia = claseBadge(item.nivel_coherencia);
    return `
      <article class="trace-card trace-${coherencia}">
        <div class="trace-header">
          <span class="cycle-badge">Ciclo ${escaparHtml(item.ciclo_origen ?? "-")} - Ciclo ${escaparHtml(item.ciclo_destino ?? "-")}</span>
          ${renderBadge(item.nivel_coherencia)}
        </div>
        <h3>${escaparHtml(item.asignatura_origen ?? "-")} - ${escaparHtml(item.asignatura_destino ?? "-")}</h3>
        <p><strong>Tipo:</strong> ${escaparHtml(formatearTexto(item.tipo_relacion))}</p>
        <p><strong>Observación:</strong> ${escaparHtml(item.observacion ?? "-")}</p>
        <p><strong>Sugerencia:</strong> ${escaparHtml(item.sugerencia ?? "-")}</p>
      </article>
    `;
  }).join("");
}

function abrirModalBrechas(data) {
  brechasDataGlobal = Array.isArray(data) ? data : [];
  prepararFiltrosBrechas();
  renderizarResumenBrechas();
  renderizarBrechasFiltradas();
  mostrarModal("modalBrechas");
}

function prepararFiltrosBrechas() {
  const buscar = document.getElementById("buscarBrechas");
  const prioridad = document.getElementById("filtroPrioridadBrechas");
  const tipo = document.getElementById("filtroTipoBrechas");
  const tipos = [...new Set(brechasDataGlobal.map((item) => item.tipo_brecha).filter(Boolean))];

  buscar.value = "";
  prioridad.value = "todas";
  tipo.innerHTML = `<option value="todos">Todos los tipos</option>`;
  tipos.forEach((valor) => {
    tipo.innerHTML += `<option value="${escaparAtributo(valor)}">${escaparHtml(formatearTexto(valor))}</option>`;
  });
  tipo.value = "todos";

  buscar.oninput = renderizarBrechasFiltradas;
  prioridad.onchange = renderizarBrechasFiltradas;
  tipo.onchange = renderizarBrechasFiltradas;
}

function renderizarResumenBrechas() {
  const resumen = document.getElementById("resumenBrechas");
  const data = brechasDataGlobal;

  resumen.innerHTML = [
    renderSummaryCard("Total de brechas", data.length),
    renderSummaryCard("Prioridad alta", contarPorCampo(data, "prioridad", "alta")),
    renderSummaryCard("Prioridad media", contarPorCampo(data, "prioridad", "media")),
    renderSummaryCard("Prioridad baja", contarPorCampo(data, "prioridad", "baja")),
    renderSummaryCard("Brechas pendientes", contarPorCampo(data, "estado", "pendiente"))
  ].join("");
}

function renderizarBrechasFiltradas() {
  const contenedor = document.getElementById("contenidoBrechas");
  const busqueda = normalizarValor(document.getElementById("buscarBrechas").value);
  const filtroPrioridad = document.getElementById("filtroPrioridadBrechas").value;
  const filtroTipo = document.getElementById("filtroTipoBrechas").value;

  if (brechasDataGlobal.length === 0) {
    contenedor.innerHTML = `<p class="text-muted">No se detectaron brechas curriculares críticas. Las relaciones analizadas presentan coherencia aceptable.</p>`;
    return;
  }

  const filtrados = brechasDataGlobal.filter((item) => {
    const coincideBusqueda = !busqueda || normalizarValor(item.asignatura).includes(busqueda);
    const coincidePrioridad = filtroPrioridad === "todas" || normalizarValor(item.prioridad) === filtroPrioridad;
    const coincideTipo = filtroTipo === "todos" || normalizarValor(item.tipo_brecha) === normalizarValor(filtroTipo);
    return coincideBusqueda && coincidePrioridad && coincideTipo;
  });

  if (filtrados.length === 0) {
    contenedor.innerHTML = `<p class="text-muted">No se detectaron brechas curriculares críticas con los filtros aplicados.</p>`;
    return;
  }

  contenedor.innerHTML = filtrados.map((item) => {
    const prioridad = claseBadge(item.prioridad);
    return `
      <article class="brecha-card brecha-${prioridad}">
        <div class="brecha-header">
          <span class="cycle-badge">Ciclo ${escaparHtml(item.ciclo ?? "-")}</span>
          <span class="badge badge-${prioridad}">Prioridad ${escaparHtml(formatearTexto(item.prioridad || "-"))}</span>
        </div>
        <h3>${escaparHtml(item.asignatura ?? "-")}</h3>
        <p><strong>Tipo de brecha:</strong> ${escaparHtml(formatearTexto(item.tipo_brecha))}</p>
        <p><strong>Problema detectado:</strong> ${escaparHtml(item.descripcion ?? "-")}</p>
        <p><strong>Recomendaci&oacute;n de mejora:</strong> ${escaparHtml(item.recomendacion ?? "-")}</p>
        <p><strong>Prioridad:</strong> ${escaparHtml(formatearTexto(item.prioridad || "-"))}</p>
        <p><strong>Estado:</strong> ${escaparHtml(formatearTexto(item.estado))}</p>
      </article>
    `;
  }).join("");
}

function cerrarModalBrechas() {
  ocultarModal("modalBrechas");
}

async function generarAccionesDesdeBrechas() {
  try {
    mostrarToast("Generando acciones de mejora desde brechas...", "info");

    const response = await fetch(`${API_URL}/api/acciones-mejora/generar-desde-brechas`, {
      method: "POST"
    });
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "No se pudieron generar las acciones de mejora.");
    }

    mostrarToast(`Acciones generadas: ${result.total_generadas || 0}`, "success");
    await cargarDashboardAccionesMejora();
    await verAccionesMejora();
  } catch (error) {
    console.error("Error al generar acciones:", error);
    mostrarToast("Error al generar acciones: " + error.message, "error");
  }
}

async function cargarDashboardAccionesMejora() {
  try {
    const response = await fetch(`${API_URL}/api/acciones-mejora/dashboard`);
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "No se pudo obtener el dashboard de acciones.");
    }

    const data = result.data || {};
    const contenedor = document.getElementById("dashboardAccionesMejora");
    if (!contenedor) return;

    contenedor.innerHTML = [
      renderSummaryCard("Total acciones", data.total_acciones || 0),
      renderSummaryCard("Pendientes", data.pendientes || 0),
      renderSummaryCard("En proceso", data.en_proceso || 0),
      renderSummaryCard("Atendidas", data.atendidas || 0),
      renderSummaryCard("Prioridad alta", data.prioridad_alta || 0),
      renderSummaryCard("Prioridad media", data.prioridad_media || 0),
      renderSummaryCard("Prioridad baja", data.prioridad_baja || 0)
    ].join("");
  } catch (error) {
    console.error("Error dashboard acciones:", error);
    mostrarToast("Error al cargar dashboard de acciones: " + error.message, "error");
  }
}

async function verAccionesMejora() {
  try {
    macroprocesoAccionesActual = null;
    const response = await fetch(`${API_URL}/api/acciones-mejora/`);
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "No se pudieron obtener las acciones de mejora.");
    }

    accionesMejoraGlobal = result.data || [];
    abrirModalAccionesMejora();
  } catch (error) {
    console.error("Error al obtener acciones:", error);
    mostrarToast("Error al obtener acciones: " + error.message, "error");
  }
}

async function verAccionesMacroproceso(macroproceso) {
  try {
    macroprocesoAccionesActual = macroproceso;
    const result = await fetchJson(
      `${API_URL}/api/acciones-mejora/?macroproceso=${encodeURIComponent(macroproceso)}`
    );

    accionesMejoraGlobal = result.data || [];
    abrirModalAccionesMejora();
  } catch (error) {
    console.error("Error al obtener acciones del macroproceso:", error);
    mostrarToast("Error al obtener acciones del macroproceso: " + error.message, "error");
  }
}

function abrirModalAccionesMejora() {
  const titulo = document.getElementById("tituloModalAccionesMejora");
  if (titulo) {
    titulo.textContent = macroprocesoAccionesActual
      ? `Acciones de mejora - ${nombreMacroproceso(macroprocesoAccionesActual)}`
      : "Acciones de mejora continua";
  }

  document.getElementById("buscarAccionesMejora").value = "";
  document.getElementById("filtroEstadoAcciones").value = "todos";
  document.getElementById("filtroPrioridadAcciones").value = "todos";

  document.getElementById("buscarAccionesMejora").oninput = renderizarAccionesMejoraFiltradas;
  document.getElementById("filtroEstadoAcciones").onchange = renderizarAccionesMejoraFiltradas;
  document.getElementById("filtroPrioridadAcciones").onchange = renderizarAccionesMejoraFiltradas;

  renderizarAccionesMejoraFiltradas();
  mostrarModal("modalAccionesMejora");
}

function cerrarModalAccionesMejora() {
  macroprocesoAccionesActual = null;
  ocultarModal("modalAccionesMejora");
}

function nombreMacroproceso(macroproceso) {
  const nombres = {
    planificacion_estrategica: "Planificación Estratégica",
    gestion_academica: "Gestión Académica",
    gestion_silabos: "Gestión de Sílabos",
    mejora_continua: "Mejora continua"
  };
  return nombres[macroproceso] || formatearTexto(macroproceso || "-");
}

function renderizarAccionesMejoraFiltradas() {
  const busqueda = normalizarValor(document.getElementById("buscarAccionesMejora")?.value || "");
  const estado = document.getElementById("filtroEstadoAcciones")?.value || "todos";
  const prioridad = document.getElementById("filtroPrioridadAcciones")?.value || "todos";

  const data = accionesMejoraGlobal.filter((accion) => {
    const texto = normalizarValor(
      `${accion.titulo || ""} ${accion.asignatura || ""} ${accion.responsable || ""} ${accion.descripcion || ""}`
    );
    const coincideBusqueda = !busqueda || texto.includes(busqueda);
    const coincideEstado = estado === "todos" || accion.estado === estado;
    const coincidePrioridad = prioridad === "todos" || accion.prioridad === prioridad;
    return coincideBusqueda && coincideEstado && coincidePrioridad;
  });

  renderizarResumenAcciones(data);
  renderizarTarjetasAcciones(data);
}

function renderizarResumenAcciones(data) {
  const contenedor = document.getElementById("resumenAccionesMejora");
  if (!contenedor) return;

  contenedor.innerHTML = [
    renderSummaryCard("Mostradas", data.length),
    renderSummaryCard("Pendientes", data.filter((accion) => accion.estado === "pendiente").length),
    renderSummaryCard("En proceso", data.filter((accion) => accion.estado === "en_proceso").length),
    renderSummaryCard("Atendidas", data.filter((accion) => accion.estado === "atendida").length)
  ].join("");
}

function renderizarTarjetasAcciones(data) {
  const contenedor = document.getElementById("contenidoAccionesMejora");
  if (!contenedor) return;

  if (data.length === 0) {
    contenedor.innerHTML = `<p class="text-muted">${
      macroprocesoAccionesActual
        ? "No hay acciones de mejora generadas para este macroproceso."
        : "No hay acciones de mejora registradas."
    }</p>`;
    return;
  }

  contenedor.innerHTML = data.map((accion) => {
    const prioridad = accion.prioridad || "media";
    const estado = accion.estado || "pendiente";
    const evidenciaRelacionada = accion.evidencia_relacionada || {};
    const macroproceso = accion.macroproceso || macroprocesoAccionesActual || "-";
    const origenId = accion.origen_id === macroproceso ? "-" : accion.origen_id || "-";
    const cicloBadge = accion.ciclo
      ? `<span class="cycle-badge">Ciclo ${escaparHtml(accion.ciclo)}</span>`
      : "";
    const fechaCreacion = accion.created_at
      ? new Date(accion.created_at).toLocaleString()
      : "Sin fecha";

    return `
      <article class="accion-card accion-prioridad-${escaparAtributo(prioridad)}">
        <div class="accion-header">
          ${cicloBadge}
          <div class="accion-badges">
            ${renderBadge(prioridad)}
            <span class="badge badge-estado-${escaparAtributo(estado)}">${escaparHtml(formatearTexto(estado))}</span>
          </div>
        </div>
        <h3>${escaparHtml(accion.titulo || "Acción de mejora")}</h3>
        <p><strong>Macroproceso:</strong> ${escaparHtml(nombreMacroproceso(macroproceso))}</p>
        <p><strong>Origen:</strong> ${escaparHtml(formatearTexto(accion.origen_tipo || "-"))}</p>
        <p><strong>Evidencia relacionada:</strong> ${escaparHtml(
          evidenciaRelacionada.codigo
            ? `${evidenciaRelacionada.codigo} - ${evidenciaRelacionada.titulo || ""}`
            : origenId
        )}</p>
        <p><strong>Asignatura:</strong> ${escaparHtml(accion.asignatura || "-")}</p>
        <p><strong>Descripci&oacute;n:</strong> ${escaparHtml(accion.descripcion || "-")}</p>
        <p><strong>Recomendaci&oacute;n:</strong> ${escaparHtml(accion.recomendacion || "-")}</p>
        <p><strong>Prioridad:</strong> ${escaparHtml(formatearTexto(prioridad))}</p>
        <p><strong>Estado:</strong> ${escaparHtml(formatearTexto(estado))}</p>
        <p><strong>Responsable:</strong> ${escaparHtml(accion.responsable || "Sin responsable")}</p>
        <p><strong>Fecha l&iacute;mite:</strong> ${escaparHtml(accion.fecha_limite || "No definida")}</p>
        <p><strong>Observaci&oacute;n:</strong> ${escaparHtml(accion.observacion || "-")}</p>
        <p><strong>Fecha de creaci&oacute;n:</strong> ${escaparHtml(fechaCreacion)}</p>
        <div class="accion-actions">
          <button class="btn btn-warning" onclick="actualizarEstadoAccion('${escaparAtributo(accion.id)}', 'en_proceso')">En proceso</button>
          <button class="btn btn-success" onclick="actualizarEstadoAccion('${escaparAtributo(accion.id)}', 'atendida')">Atendida</button>
          <button class="btn btn-secondary" onclick="actualizarEstadoAccion('${escaparAtributo(accion.id)}', 'descartada')">Descartar</button>
          <button class="btn btn-danger" onclick="eliminarAccionMejora('${escaparAtributo(accion.id)}')">Eliminar</button>
        </div>
      </article>
    `;
  }).join("");
}

async function actualizarEstadoAccion(id, estado) {
  try {
    const response = await fetch(`${API_URL}/api/acciones-mejora/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ estado })
    });
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "No se pudo actualizar la acción.");
    }

    mostrarToast("Estado actualizado correctamente.", "success");
    if (macroprocesoAccionesActual) {
      await verAccionesMacroproceso(macroprocesoAccionesActual);
    } else {
      await verAccionesMejora();
    }
    await cargarDashboardAccionesMejora();
  } catch (error) {
    console.error("Error al actualizar acción:", error);
    mostrarToast("Error al actualizar acción: " + error.message, "error");
  }
}

async function eliminarAccionMejora(id) {
  const confirmado = await confirmarAccion("¿Deseas eliminar esta acción de mejora?");
  if (!confirmado) return;

  try {
    const response = await fetch(`${API_URL}/api/acciones-mejora/${id}`, {
      method: "DELETE"
    });
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "No se pudo eliminar la acción.");
    }

    mostrarToast("Acción eliminada correctamente.", "success");
    if (macroprocesoAccionesActual) {
      await verAccionesMacroproceso(macroprocesoAccionesActual);
    } else {
      await verAccionesMejora();
    }
    await cargarDashboardAccionesMejora();
  } catch (error) {
    console.error("Error al eliminar acción:", error);
    mostrarToast("Error al eliminar acción: " + error.message, "error");
  }
}




