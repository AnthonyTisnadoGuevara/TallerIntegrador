import { API_URL } from "./config.js";

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const data = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const message = isJson ? data.detail || data.message : data;
    throw new Error(message || `HTTP ${response.status}`);
  }

  return data;
}

export async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, options);
  return parseResponse(response);
}

export function apiGet(path) {
  return apiRequest(path);
}

export function apiPost(path, body) {
  return apiRequest(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
}

export function apiPut(path, body) {
  return apiRequest(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
}

export function apiDelete(path) {
  return apiRequest(path, { method: "DELETE" });
}

export function apiUpload(path, formData) {
  return apiRequest(path, {
    method: "POST",
    body: formData
  });
}
