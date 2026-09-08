/* B1 READY ADMIN V33.4 */
(() => {
  "use strict";

  const norm = value => String(value || "").trim().toLowerCase();

  const initModuleSearch = () => {
    const input = document.getElementById("b1-admin-module-search");
    const grid = document.getElementById("b1-admin-app-grid");
    if (!input || !grid) return;

    const cards = [...grid.querySelectorAll(".b1-app-card")];
    input.addEventListener("input", () => {
      const q = norm(input.value);

      cards.forEach(card => {
        const rows = [...card.querySelectorAll(".b1-model-row")];
        let visibleRows = 0;

        rows.forEach(row => {
          const haystack = norm(`${row.dataset.b1Search || ""} ${row.textContent || ""}`);
          const show = !q || haystack.includes(q);
          row.classList.toggle("b1-search-hidden", !show);
          if (show) visibleRows += 1;
        });

        const appHaystack = norm(`${card.dataset.b1Search || ""} ${card.querySelector("h3")?.textContent || ""}`);
        const appMatches = !q || appHaystack.includes(q);

        if (q && appMatches) {
          rows.forEach(row => row.classList.remove("b1-search-hidden"));
          visibleRows = rows.length;
        }
        card.classList.toggle("b1-search-hidden", !!q && visibleRows === 0);
      });
    });
  };

  const extensionKind = name => {
    const ext = (norm(name).match(/\.[a-z0-9]+$/) || [""])[0];
    if ([".mp3",".wav",".m4a",".ogg",".aac",".flac",".webm"].includes(ext)) return "audio";
    if ([".mp4",".mov",".m4v",".avi",".mkv"].includes(ext)) return "video";
    if ([".jpg",".jpeg",".png",".gif",".webp",".svg",".avif"].includes(ext)) return "image";
    if ([".pdf",".doc",".docx",".ppt",".pptx",".xls",".xlsx",".txt",".csv",".zip"].includes(ext)) return "document";
    return "file";
  };

  const enhanceFileInputs = () => {
    document.querySelectorAll('input[type="file"]').forEach(input => {
      if (input.dataset.b1v334 === "1" || input.closest(".b1-file-drop")) return;
      input.dataset.b1v334 = "1";

      const wrapper = document.createElement("div");
      wrapper.className = "b1-file-drop";
      input.parentNode.insertBefore(wrapper, input);
      wrapper.appendChild(input);

      const helper = document.createElement("div");
      helper.className = "b1-file-help";
      helper.textContent = "Choose a file or drag it here. Preview it before saving.";
      wrapper.appendChild(helper);

      const render = () => {
        wrapper.querySelector(".b1-v334-selected")?.remove();
        const file = input.files?.[0];
        if (!file) return;

        const kind = extensionKind(file.name);
        const selected = document.createElement("div");
        selected.className = "b1-v334-selected b1-file-preview";

        const meta = document.createElement("div");
        meta.innerHTML = `<span class="b1-file-chip">${kind.toUpperCase()}</span>
          <strong style="display:block;margin-top:6px;font-size:8px;word-break:break-word"></strong>
          <small style="display:block;margin-top:3px;color:#7e8ca2;font-size:7px"></small>`;
        meta.querySelector("strong").textContent = file.name;
        meta.querySelector("small").textContent = `${(file.size / 1048576).toFixed(1)} MB · saves when the form is submitted`;

        if (["image","audio","video"].includes(kind)) {
          const url = URL.createObjectURL(file);
          let media;
          if (kind === "image") {
            media = document.createElement("img");
            media.src = url;
            media.alt = "";
          } else if (kind === "audio") {
            media = document.createElement("audio");
            media.src = url;
            media.controls = true;
          } else {
            media = document.createElement("video");
            media.src = url;
            media.controls = true;
          }
          selected.appendChild(media);
        }
        selected.appendChild(meta);
        wrapper.appendChild(selected);
      };

      input.addEventListener("change", render);

      ["dragenter","dragover"].forEach(type => wrapper.addEventListener(type, e => {
        e.preventDefault();
        wrapper.classList.add("is-dragging");
      }));
      ["dragleave","drop"].forEach(type => wrapper.addEventListener(type, e => {
        e.preventDefault();
        wrapper.classList.remove("is-dragging");
      }));
      wrapper.addEventListener("drop", e => {
        const files = e.dataTransfer?.files;
        if (!files?.length) return;
        try {
          const dt = new DataTransfer();
          dt.items.add(files[0]);
          input.files = dt.files;
          render();
        } catch (_) {}
      });
    });
  };

  document.addEventListener("DOMContentLoaded", () => {
    initModuleSearch();
    enhanceFileInputs();
  });
})();
