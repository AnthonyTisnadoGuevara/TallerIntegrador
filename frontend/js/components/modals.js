export function openModal(modalOrId) {
  const modal = typeof modalOrId === "string"
    ? document.getElementById(modalOrId)
    : modalOrId;

  modal?.classList.remove("hidden");
}

export function closeModal(modalOrId) {
  const modal = typeof modalOrId === "string"
    ? document.getElementById(modalOrId)
    : modalOrId;

  modal?.classList.add("hidden");
}

export function toggleModal(modalOrId, force) {
  const modal = typeof modalOrId === "string"
    ? document.getElementById(modalOrId)
    : modalOrId;

  modal?.classList.toggle("hidden", force === undefined ? undefined : !force);
}
