/* B1 READY ADMIN V33.8.1 — CRUD / FILTERS / FORMS */
(() => {
  "use strict";

  const body = document.body;
  const path = location.pathname;
  const params = new URLSearchParams(location.search);
  const qs = (selector, root=document) => root.querySelector(selector);
  const qsa = (selector, root=document) => [...root.querySelectorAll(selector)];

  const isList = body.classList.contains("change-list");
  const isForm = body.classList.contains("change-form");

  /* ---------------- Filter UX ---------------- */

  const countActiveFilters = () => {
    let count = 0;
    params.forEach((value, key) => {
      if (!value) return;
      if (["q","o","ot","p","all"].includes(key)) return;
      count += 1;
    });
    return count;
  };

  const createFilterControls = () => {
    if (!isList) return;

    const changelist = qs("#changelist");
    const filter = qs("#changelist-filter");
    const main = qs("#content-main");

    if (!changelist || !main || qs(".b1-list-controlbar")) return;

    const active = countActiveFilters();

    const bar = document.createElement("div");
    bar.className = "b1-list-controlbar";
    bar.innerHTML = `
      <div class="b1-list-controlbar-left">
        <button type="button" class="b1-filter-toggle">
          <span>Filters</span>
          <span class="b1-filter-count">${active}</span>
        </button>
        ${active ? '<a class="b1-filter-clear" href="' + location.pathname + '">Clear filters</a>' : ''}
      </div>
      <div class="b1-list-controlbar-right">
        <span class="b1-list-help">Use View, Edit or Delete from the Manage column.</span>
      </div>
    `;

    main.insertBefore(bar, changelist);

    if (!filter) {
      qs(".b1-filter-toggle", bar)?.remove();
      return;
    }

    const backdrop = document.createElement("div");
    backdrop.className = "b1-filter-backdrop";
    document.body.appendChild(backdrop);

    const toggle = qs(".b1-filter-toggle", bar);

    const isDrawer = () => window.innerWidth <= 1180;

    const closeFilter = () => {
      body.classList.remove("b1-filter-open");
      toggle?.setAttribute("aria-expanded", "false");
    };

    toggle?.setAttribute("aria-expanded", "false");

    toggle?.addEventListener("click", () => {
      if (isDrawer()) {
        const open = !body.classList.contains("b1-filter-open");
        body.classList.toggle("b1-filter-open", open);
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
      } else {
        body.classList.toggle("b1-filter-collapsed");
      }
    });

    backdrop.addEventListener("click", closeFilter);

    document.addEventListener("keydown", event => {
      if (event.key === "Escape") closeFilter();
    });

    window.addEventListener("resize", () => {
      if (!isDrawer()) closeFilter();
    });
  };

  /* ---------------- View-only mode ---------------- */

  const formListUrl = () => {
    const match = path.match(/^(.*\/admin\/[^/]+\/[^/]+\/)/);
    return match ? match[1] : "/admin/";
  };

  const cleanChangeUrl = () => {
    const url = new URL(location.href);
    url.searchParams.delete("view");
    return url.pathname + (url.searchParams.toString() ? "?" + url.searchParams.toString() : "");
  };

  const deleteUrl = () => {
    const match = path.match(/^(.*\/)([^/]+)\/change\/$/);
    if (!match) return "";
    return `${match[1]}${match[2]}/delete/`;
  };

  const installViewMode = () => {
    if (!isForm || params.get("view") !== "1") return;

    body.classList.add("b1-view-mode");

    qsa("input, select, textarea, button").forEach(el => {
      if (el.closest(".b1-view-banner")) return;
      if (el.type === "hidden") return;
      el.disabled = true;
    });

    const main = qs("#content-main");
    if (!main || qs(".b1-view-banner")) return;

    const banner = document.createElement("section");
    banner.className = "b1-view-banner";
    banner.innerHTML = `
      <span class="b1-view-banner-icon">V</span>
      <div>
        <strong>View-only mode</strong>
        <p>This record is locked for safe review. Use Edit record when you want to make changes.</p>
      </div>
      <a href="${cleanChangeUrl()}">Edit record</a>
    `;

    main.insertBefore(banner, main.firstChild);
  };

  /* ---------------- Professional form toolbar ---------------- */

  const installFormToolbar = () => {
    if (!isForm) return;

    const main = qs("#content-main");
    if (!main || qs(".b1-form-toolbar")) return;

    const toolbar = document.createElement("div");
    toolbar.className = "b1-form-toolbar";

    const left = document.createElement("div");
    left.className = "b1-form-toolbar-left";

    const back = document.createElement("a");
    back.href = formListUrl();
    back.textContent = "← Back to list";
    left.appendChild(back);

    const right = document.createElement("div");
    right.className = "b1-form-toolbar-right";

    if (params.get("view") !== "1" && /\/change\/$/.test(path)) {
      const view = document.createElement("a");
      view.className = "is-primary";
      view.href = path + "?view=1";
      view.textContent = "View record";
      right.appendChild(view);
    }

    if (/\/change\/$/.test(path)) {
      const del = deleteUrl();
      if (del) {
        const link = document.createElement("a");
        link.className = "is-danger";
        link.href = del;
        link.textContent = "Delete record";
        right.appendChild(link);
      }
    }

    toolbar.append(left, right);

    const guide = qs(".b1-content-guide", main);
    if (guide) {
      guide.insertAdjacentElement("afterend", toolbar);
    } else {
      main.insertBefore(toolbar, main.firstChild);
    }
  };

  /* ---------------- Form polish ---------------- */

  const labelFileInputs = () => {
    if (!isForm) return;

    qsa('input[type="file"]').forEach(input => {
      const zone = input.closest(".b1-upload-zone");
      if (!zone) return;

      const label = input.closest(".form-row")?.querySelector("label");
      if (label) {
        zone.dataset.fieldLabel = label.textContent.trim().replace(/\s+/g, " ");
      }
    });
  };

  const markLongTextFields = () => {
    if (!isForm) return;

    qsa("textarea").forEach(el => {
      const row = el.closest(".form-row");
      if (row) row.classList.add("b1-long-text-row");
    });
  };

  /* ---------------- Search shortcut ---------------- */

  const installSearchShortcut = () => {
    if (!isList) return;
    document.addEventListener("keydown", event => {
      if (
        event.key === "/" &&
        !["INPUT","TEXTAREA","SELECT"].includes(document.activeElement?.tagName)
      ) {
        const search = qs("#searchbar");
        if (search) {
          event.preventDefault();
          search.focus();
        }
      }
    });
  };

  document.addEventListener("DOMContentLoaded", () => {
    createFilterControls();
    installFormToolbar();
    installViewMode();
    labelFileInputs();
    markLongTextFields();
    installSearchShortcut();
  });
})();
