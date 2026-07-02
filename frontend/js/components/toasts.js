export function showToast(message, type = "info") {
  if (typeof window.mostrarToast === "function") {
    window.mostrarToast(message, type);
    return;
  }

  console[type === "error" ? "error" : "log"](message);
}

export function showSuccess(message) {
  showToast(message, "success");
}

export function showError(message) {
  showToast(message, "error");
}

export function showWarning(message) {
  showToast(message, "warning");
}
