export function formatDate(value) {
  if (!value) return "";
  return new Date(value).toLocaleDateString("es-PE");
}

export function formatDateTime(value) {
  if (!value) return "";
  return new Date(value).toLocaleString("es-PE");
}

export function escapeHTML(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

export function debounce(callback, wait = 300) {
  let timeoutId;
  return (...args) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => callback(...args), wait);
  };
}

export function getBadgeClass(value) {
  return String(value ?? "")
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9_-]/g, "");
}

export function safeText(value, fallback = "Sin información") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

export function parseNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}
