const API_URL = "http://127.0.0.1:8000";

document.addEventListener("DOMContentLoaded", () => {
  cargarDatos();

  const form = document.getElementById("formSilabo");
  form.addEventListener("submit", registrarSilabo);
});

async function cargarDatos() {
  await cargarDashboard();
  await cargarSilabos();
}

async function cargarDashboard() {
  try {
    const response = await fetch(`${API_URL}/api/dashboard/silabos`);
    const result = await response.json();
    const data = result.data[0];

    document.getElementById("totalSilabos").textContent = data.total_silabos;
    document.getElementById("silabosCompletos").textContent = data.silabos_completos;
    document.getElementById("silabosObservados").textContent = data.silabos_observados;
    document.getElementById("silabosPendientes").textContent = data.silabos_pendientes;
    document.getElementById("cumplimientoPromedio").textContent = `${data.cumplimiento_promedio}%`;
  } catch (error) {
    console.error("Error al cargar dashboard:", error);
  }
}

async function cargarSilabos() {
  try {
    const response = await fetch(`${API_URL}/api/silabos/`);
    const result = await response.json();
    const silabos = result.data;

    const tbody = document.getElementById("tablaSilabos");
    tbody.innerHTML = "";

    if (silabos.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7">No hay sílabos registrados.</td></tr>`;
      return;
    }

    silabos.forEach((silabo) => {
      const tr = document.createElement("tr");

      tr.innerHTML = `
        <td>${silabo.ciclo}</td>
        <td>${silabo.codigo_asignatura}</td>
        <td>${silabo.asignatura}</td>
        <td><span class="estado ${silabo.estado}">${silabo.estado}</span></td>
        <td>${silabo.porcentaje_cumplimiento}%</td>
        <td>
          ${
            silabo.archivo_url
              ? `<a href="${silabo.archivo_url}" target="_blank">Ver archivo</a>`
              : "Sin archivo"
          }
        </td>
        <td>
          <div class="acciones">
            <button onclick="verValidacion('${silabo.id}')">Validación</button>
            <button class="secondary" onclick="verHistorial('${silabo.id}')">Historial</button>
            <button class="warning" onclick="validarDocumento('${silabo.id}')">Validar doc.</button>
            <button class="danger" onclick="eliminarSilabo('${silabo.id}')">Eliminar</button>
            <button onclick="seleccionarArchivo('${silabo.id}')">Subir archivo</button>
            <button class="warning" onclick="cambiarEstado('${silabo.id}')">Cambiar estado</button>
          </div>
        </td>
      `;

      tbody.appendChild(tr);
    });
  } catch (error) {
    console.error("Error al cargar sílabos:", error);
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
async function cambiarEstado(id) {
  const nuevoEstado = prompt(
    "Ingrese el nuevo estado: pendiente, completo, observado o incompleto"
  );

  if (!nuevoEstado) return;

  const estadosValidos = ["pendiente", "completo", "observado", "incompleto"];

  if (!estadosValidos.includes(nuevoEstado)) {
    alert("Estado inválido. Use: pendiente, completo, observado o incompleto.");
    return;
  }

  const observacion = prompt("Ingrese una observación para el cambio de estado:");

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

    alert("Estado actualizado correctamente");
    await cargarDatos();
    await verHistorial(id);
  } catch (error) {
    alert("Error al actualizar el estado");
    console.error(error);
  }
}