export function getFormData(formOrId) {
  const form = typeof formOrId === "string"
    ? document.getElementById(formOrId)
    : formOrId;

  return form ? Object.fromEntries(new FormData(form).entries()) : {};
}

export function requireValue(value, message = "Campo requerido") {
  if (String(value ?? "").trim()) return null;
  return message;
}

export function resetForm(formOrId) {
  const form = typeof formOrId === "string"
    ? document.getElementById(formOrId)
    : formOrId;

  form?.reset();
}
