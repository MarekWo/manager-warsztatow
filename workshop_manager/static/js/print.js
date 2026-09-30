// The "Drukuj" button on print pages (no inline scripts: the site enforces CSP).
document.querySelectorAll("[data-print]").forEach((button) => {
  button.addEventListener("click", () => window.print());
});
