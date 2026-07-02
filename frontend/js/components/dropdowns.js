export function closeDropdowns(exceptId = null) {
  document.querySelectorAll(".dropdown-menu, .menu-acciones").forEach((menu) => {
    if (!exceptId || menu.id !== exceptId) menu.classList.add("hidden");
  });
}

export function toggleDropdown(id) {
  const menu = document.getElementById(id);
  if (!menu) return;

  const isHidden = menu.classList.contains("hidden");
  closeDropdowns(id);
  menu.classList.toggle("hidden", !isHidden);
}
