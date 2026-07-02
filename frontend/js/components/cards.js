import { escapeHTML } from "../utils.js";

export function renderCard({ title = "", body = "", footer = "", className = "" } = {}) {
  return `
    <article class="card ${escapeHTML(className)}">
      ${title ? `<h3>${escapeHTML(title)}</h3>` : ""}
      ${body}
      ${footer ? `<footer>${footer}</footer>` : ""}
    </article>
  `;
}
