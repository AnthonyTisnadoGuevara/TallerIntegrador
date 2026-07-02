export function showSection(sectionId) {
  document.querySelectorAll(".section, .view, [data-section]").forEach((section) => {
    section.classList.add("hidden");
  });
  document.getElementById(sectionId)?.classList.remove("hidden");
}

export function setLoading(elementOrId, isLoading, text = "Cargando...") {
  const element = typeof elementOrId === "string"
    ? document.getElementById(elementOrId)
    : elementOrId;

  if (!element) return;
  element.toggleAttribute("disabled", Boolean(isLoading));
  element.dataset.originalText ||= element.textContent;
  element.textContent = isLoading ? text : element.dataset.originalText;
}

export function clearContainer(elementOrId) {
  const element = typeof elementOrId === "string"
    ? document.getElementById(elementOrId)
    : elementOrId;

  if (element) element.innerHTML = "";
}

export function renderEmptyState(message = "No hay información disponible.") {
  return `<div class="empty-state">${message}</div>`;
}

export function toggleSidebar() {
  document.querySelector(".sidebar")?.classList.toggle("open");
}

export function handleResponsiveMenu() {
  document.querySelector(".sidebar")?.classList.remove("open");
}
