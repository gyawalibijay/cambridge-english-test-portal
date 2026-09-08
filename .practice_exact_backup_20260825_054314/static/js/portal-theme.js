(() => {
  const storageKey = "portal-theme-v2";
  const root = document.documentElement;

  function systemTheme() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function getTheme() {
    return localStorage.getItem(storageKey) || systemTheme();
  }

  function iconSvg(theme) {
    if (theme === "dark") {
      return `
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path d="M12 4.75a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0V5.5a.75.75 0 0 1 .75-.75ZM12 17.25a.75.75 0 0 1 .75.75v1.5a.75.75 0 0 1-1.5 0V18a.75.75 0 0 1 .75-.75ZM5.99 6.99a.75.75 0 0 1 1.06 0l1.06 1.06a.75.75 0 1 1-1.06 1.06L5.99 8.05a.75.75 0 0 1 0-1.06Zm10.9 10.9a.75.75 0 0 1 1.06 0l1.06 1.06a.75.75 0 1 1-1.06 1.06l-1.06-1.06a.75.75 0 0 1 0-1.06ZM4.75 12a.75.75 0 0 1 .75-.75H7a.75.75 0 0 1 0 1.5H5.5a.75.75 0 0 1-.75-.75Zm12.25 0a.75.75 0 0 1 .75-.75h1.5a.75.75 0 0 1 0 1.5h-1.5A.75.75 0 0 1 17 12ZM7.05 14.89a.75.75 0 0 1 1.06 1.06l-1.06 1.06a.75.75 0 0 1-1.06-1.06l1.06-1.06Zm10.9-10.9a.75.75 0 0 1 1.06 1.06l-1.06 1.06a.75.75 0 1 1-1.06-1.06l1.06-1.06ZM12 8a4 4 0 1 1 0 8a4 4 0 0 1 0-8Z" fill="currentColor"/>
        </svg>`;
    }

    return `
      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M14.53 3.49a.75.75 0 0 1 .9.92a7.2 7.2 0 0 0 8.02 8.95a.75.75 0 0 1 .76 1.14A10.5 10.5 0 1 1 13.39 2.74a.75.75 0 0 1 1.14.75Z" fill="currentColor"/>
      </svg>`;
  }

  function render(theme) {
    root.dataset.theme = theme;

    document.querySelectorAll("[data-theme-icon]").forEach((node) => {
      node.innerHTML = iconSvg(theme);
    });

    document.querySelectorAll("[data-theme-label]").forEach((node) => {
      node.textContent = theme === "dark" ? "Light mode" : "Dark mode";
    });

    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.setAttribute(
        "aria-label",
        theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
      );
      button.setAttribute(
        "title",
        theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
      );
    });
  }

  function setTheme(theme) {
    localStorage.setItem(storageKey, theme);
    render(theme);
  }

  function toggle() {
    setTheme(root.dataset.theme === "dark" ? "light" : "dark");
  }

  window.portalTheme = { getTheme, setTheme, toggle };

  render(getTheme());

  document.addEventListener("DOMContentLoaded", () => {
    render(getTheme());
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      if (!button.dataset.themeBound) {
        button.dataset.themeBound = "1";
        button.addEventListener("click", toggle);
      }
    });
  });
})();
