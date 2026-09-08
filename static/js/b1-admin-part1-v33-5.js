/* B1 READY ADMIN — PART 1/3 — V33.5 */
(() => {
  "use strict";

  const body = document.body;
  const sidebar = document.getElementById("b1-admin-sidebar");
  const toggle = document.querySelector("[data-b1-sidebar-toggle]");
  const closeEls = document.querySelectorAll("[data-b1-sidebar-close]");
  const search = document.getElementById("b1-sidebar-search");

  const closeSidebar = () => {
    body.classList.remove("b1-sidebar-open");
    toggle?.setAttribute("aria-expanded", "false");
  };

  const openSidebar = () => {
    body.classList.add("b1-sidebar-open");
    toggle?.setAttribute("aria-expanded", "true");
  };

  toggle?.addEventListener("click", () => {
    if (body.classList.contains("b1-sidebar-open")) closeSidebar();
    else openSidebar();
  });

  closeEls.forEach(el => el.addEventListener("click", closeSidebar));

  document.addEventListener("keydown", event => {
    if (event.key === "Escape") closeSidebar();

    if (
      event.key === "/" &&
      search &&
      !["INPUT","TEXTAREA","SELECT"].includes(document.activeElement?.tagName)
    ) {
      event.preventDefault();
      search.focus();
    }
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth > 780) closeSidebar();
  });

  // Active sidebar item.
  const current = location.pathname.replace(/\/+$/, "/");
  const links = [...document.querySelectorAll(".b1-nav-link, .b1-dynamic-model")];

  let best = null;
  let bestLength = -1;

  links.forEach(link => {
    try {
      const url = new URL(link.href, location.origin);
      const path = url.pathname.replace(/\/+$/, "/");

      if (
        path !== "/admin/" &&
        current.startsWith(path) &&
        path.length > bestLength
      ) {
        best = link;
        bestLength = path.length;
      }

      if (current === "/admin/" && path === "/admin/") {
        best = link;
        bestLength = path.length;
      }
    } catch (_) {}
  });

  best?.classList.add("is-active");

  // Sidebar search.
  const navSections = [...document.querySelectorAll(".b1-nav-section")];
  const dynamicApps = [...document.querySelectorAll(".b1-dynamic-app")];

  const normalize = value => String(value || "").toLowerCase().trim();

  const runSearch = () => {
    if (!search) return;
    const query = normalize(search.value);

    document.querySelectorAll(".b1-nav-link").forEach(link => {
      const show = !query || normalize(link.textContent).includes(query);
      link.style.display = show ? "" : "none";
    });

    navSections.forEach(section => {
      const visible = [...section.querySelectorAll(".b1-nav-link")]
        .some(link => link.style.display !== "none");
      section.style.display = !query || visible ? "" : "none";
    });

    dynamicApps.forEach(app => {
      const models = [...app.querySelectorAll(".b1-dynamic-model")];
      let appVisible = false;

      models.forEach(model => {
        const show = !query || normalize(model.textContent).includes(query) ||
          normalize(app.querySelector(".b1-dynamic-app-title")?.textContent).includes(query);
        model.style.display = show ? "" : "none";
        if (show) appVisible = true;
      });

      app.style.display = !query || appVisible ? "" : "none";
    });

    if (query) {
      document.querySelector(".b1-all-modules")?.setAttribute("open", "");
    }
  };

  search?.addEventListener("input", runSearch);

  // Close mobile drawer after choosing a navigation item.
  sidebar?.querySelectorAll("a").forEach(link => {
    link.addEventListener("click", () => {
      if (window.innerWidth <= 780) closeSidebar();
    });
  });
})();
