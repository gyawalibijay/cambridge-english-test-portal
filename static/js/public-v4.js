document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector("[data-public-menu-toggle]");
  const menu = document.querySelector("[data-public-menu]");
  const menuIcon = document.querySelector("[data-public-menu-icon]");

  function closeMenu() {
    if (menu) menu.classList.remove("open");
    if (menuIcon) menuIcon.textContent = "☰";
  }

  function openMenu() {
    if (menu) menu.classList.add("open");
    if (menuIcon) menuIcon.textContent = "✕";
  }

  if (toggle && menu) {
    toggle.addEventListener("click", () => {
      if (menu.classList.contains("open")) closeMenu();
      else openMenu();
    });

    menu.querySelectorAll("a").forEach((a) => {
      a.addEventListener("click", () => {
        if (window.innerWidth <= 680) closeMenu();
      });
    });

    window.addEventListener("resize", () => {
      if (window.innerWidth > 680) {
        menu.classList.remove("open");
        if (menuIcon) menuIcon.textContent = "☰";
      }
    });
  }

  document.querySelectorAll("[data-faq-button]").forEach((button) => {
    button.addEventListener("click", () => {
      const item = button.closest(".pub4-faq-item");
      if (item) item.classList.toggle("open");
    });
  });
});
