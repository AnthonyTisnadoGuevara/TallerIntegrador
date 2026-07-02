export const IS_LOCAL = ["localhost", "127.0.0.1"].includes(window.location.hostname);

export const API_URL = IS_LOCAL
  ? "http://127.0.0.1:8000"
  : "";

window.API_URL = API_URL;
window.IS_LOCAL = IS_LOCAL;
