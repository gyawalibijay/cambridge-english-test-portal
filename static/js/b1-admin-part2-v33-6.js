/* B1 READY ADMIN — PART 2/3 — CONTENT STUDIO V33.6 */
(() => {
  "use strict";

  const path = location.pathname.toLowerCase();
  const qs = (s, root=document) => root.querySelector(s);
  const qsa = (s, root=document) => [...root.querySelectorAll(s)];

  const pageType = () => {
    const rules = [
      ["question", "/admin/question_bank/question/"],
      ["stimulus", "/admin/question_bank/stimulus/"],
      ["course-material", "/admin/academy/coursematerial/"],
      ["test-material", "/admin/academy/testmaterial/"],
      ["mock-test", "/admin/assessments/mocktest/"],
      ["test-section", "/admin/assessments/testsection/"],
      ["test-part", "/admin/assessments/testpart/"],
    ];
    for (const [name, prefix] of rules) {
      if (path.startsWith(prefix)) return name;
    }
    return "";
  };

  const isChangeForm = () => document.body.classList.contains("change-form");
  const isChangeList = () => document.body.classList.contains("change-list");

  const guides = {
    "question": {
      kicker: "QUESTION BANK · CONTENT STUDIO",
      title: "Build the exact question the student should receive.",
      text: "Choose the skill first, then add student content, audio/timing and marking rules. Existing Practice and Mock Test runners keep using the same database records.",
      steps: ["Choose skill", "Add prompt/source", "Check audio & timing", "Save + preview"],
    },
    "stimulus": {
      kicker: "SHARED SOURCE · CONTENT STUDIO",
      title: "Manage reusable passages, recordings and source material.",
      text: "Use Stimulus when several questions share the same Listening track, Reading passage, image or scenario. Question-specific audio can still override shared audio.",
      steps: ["Choose program/type", "Add source content", "Upload shared media", "Attach to questions"],
    },
    "course-material": {
      kicker: "LEARNING MATERIALS · CONTENT STUDIO",
      title: "Publish lessons and resources without guessing which field to use.",
      text: "Choose the resource type, add the lesson content, attach the relevant file/audio/link, preview it, then publish only when it is ready for students.",
      steps: ["Choose type", "Add lesson content", "Attach resource", "Publish"],
    },
    "test-material": {
      kicker: "TEST SOURCE MATERIAL · CONTENT STUDIO",
      title: "Prepare reviewed material before it becomes Question Bank content.",
      text: "Use the fields that match the selected skill. Keep transcripts/source notes private, verify media, and mark Question Bank Ready only after review.",
      steps: ["Choose skill", "Add source/task", "Attach audio/files", "Review readiness"],
    },
    "mock-test": {
      kicker: "ASSESSMENTS · CONTENT STUDIO",
      title: "Build the mock-test structure from the top down.",
      text: "Create the Mock Test first, then its Sections, Parts and question placements. Publishing should happen only after every required part contains questions.",
      steps: ["Create test", "Add sections", "Add parts/questions", "Publish"],
    },
    "test-section": {
      kicker: "ASSESSMENTS · CONTENT STUDIO",
      title: "Configure one skill section of a mock test.",
      text: "Set the skill, order and duration, then manage its Test Parts. Keep student instructions clear and timing consistent.",
      steps: ["Choose mock", "Set skill/order", "Set duration", "Add parts"],
    },
    "test-part": {
      kicker: "ASSESSMENTS · CONTENT STUDIO",
      title: "Control timing, prompt behavior and question placement.",
      text: "This is where Speaking preparation/response timing, prompt visibility and recording behavior are configured for a part.",
      steps: ["Choose section", "Set prompt rules", "Set timing", "Attach questions"],
    },
  };

  const injectGuide = () => {
    const type = pageType();
    const guide = guides[type];
    if (!guide || qs(".b1-content-guide")) return;

    const contentMain = qs("#content-main");
    if (!contentMain) return;

    const el = document.createElement("section");
    el.className = "b1-content-guide";
    el.innerHTML = `
      <div class="b1-content-guide-main">
        <span class="b1-content-guide-kicker"></span>
        <h2></h2>
        <p></p>
      </div>
      <div class="b1-content-guide-steps"></div>
    `;
    qs(".b1-content-guide-kicker", el).textContent = guide.kicker;
    qs("h2", el).textContent = guide.title;
    qs("p", el).textContent = guide.text;

    const steps = qs(".b1-content-guide-steps", el);
    guide.steps.forEach((step, index) => {
      const item = document.createElement("span");
      item.className = "b1-guide-step";
      item.innerHTML = `<b>${index + 1}</b><span></span>`;
      qs("span", item).textContent = step;
      steps.appendChild(item);
    });

    contentMain.insertBefore(el, contentMain.firstChild);
  };

  const skillContent = {
    speaking: {
      icon: "S",
      title: "Speaking question",
      text: "Recommended: upload the approved question voice, usually keep prompt text hidden when the real format is audio-only, then verify preparation and response times.",
    },
    listening: {
      icon: "L",
      title: "Listening question / material",
      text: "Make sure real audio exists. Use question audio for a unique clip or link a Stimulus when several questions share one recording.",
    },
    reading: {
      icon: "R",
      title: "Reading content",
      text: "Use prompt text for the question and Stimulus/passage content for shared source material. Check answer options and automatic marking before publishing.",
    },
    writing: {
      icon: "W",
      title: "Writing task",
      text: "Use prompt/scenario text, confirm minimum/maximum word settings and evaluator configuration. Audio is normally not required.",
    },
    general: {
      icon: "G",
      title: "General learning material",
      text: "Choose the material type that matches what students receive, then preview the resource and publish when ready.",
    }
  };

  const injectSkillHelper = () => {
    if (!isChangeForm()) return;

    const skill = qs("#id_skill");
    if (!skill) return;

    let helper = qs(".b1-skill-helper");
    if (!helper) {
      helper = document.createElement("div");
      helper.className = "b1-skill-helper";
      const guide = qs(".b1-content-guide");
      if (guide) guide.insertAdjacentElement("afterend", helper);
      else qs("#content-main")?.insertBefore(helper, qs("#content-main")?.firstChild || null);
    }

    const render = () => {
      const value = String(skill.value || "general").toLowerCase();
      const data = skillContent[value] || skillContent.general;

      helper.className = `b1-skill-helper is-${value}`;
      helper.innerHTML = `
        <span class="b1-skill-helper-icon"></span>
        <div><strong></strong><p></p></div>
      `;
      qs(".b1-skill-helper-icon", helper).textContent = data.icon;
      qs("strong", helper).textContent = data.title;
      qs("p", helper).textContent = data.text;
    };

    skill.addEventListener("change", render);
    render();
  };

  const fileKind = name => {
    const lower = String(name || "").toLowerCase();
    if (/\.(mp3|wav|m4a|ogg|aac|flac)$/i.test(lower)) return "audio";
    if (/\.(mp4|mov|m4v|avi|mkv|webm)$/i.test(lower)) return "video";
    if (/\.(jpg|jpeg|png|webp|gif|avif|svg)$/i.test(lower)) return "image";
    if (/\.(pdf|doc|docx|ppt|pptx|xls|xlsx|txt|csv|zip)$/i.test(lower)) return "document";
    return "file";
  };

  const humanSize = bytes => {
    const units = ["B","KB","MB","GB"];
    let value = Number(bytes || 0);
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) {
      value /= 1024;
      unit += 1;
    }
    return `${value.toFixed(unit ? 1 : 0)} ${units[unit]}`;
  };

  const enhanceFiles = () => {
    if (!isChangeForm()) return;

    qsa('input[type="file"]').forEach(input => {
      if (input.dataset.b1ContentV336 === "1" || input.closest(".b1-upload-zone")) return;
      input.dataset.b1ContentV336 = "1";

      const zone = document.createElement("div");
      zone.className = "b1-upload-zone";

      input.parentNode.insertBefore(zone, input);
      zone.appendChild(input);

      const copy = document.createElement("div");
      copy.className = "b1-upload-copy";
      copy.innerHTML = "<b>Upload:</b> choose a file or drag one here. You can preview it before saving.";
      zone.appendChild(copy);

      const previewFile = file => {
        zone.querySelector(".b1-local-preview")?.remove();
        if (!file) return;

        const kind = fileKind(file.name);
        const preview = document.createElement("div");
        preview.className = "b1-local-preview";

        if (["audio","video","image"].includes(kind)) {
          const url = URL.createObjectURL(file);
          let media;
          if (kind === "audio") {
            media = document.createElement("audio");
            media.controls = true;
            media.preload = "metadata";
          } else if (kind === "video") {
            media = document.createElement("video");
            media.controls = true;
            media.preload = "metadata";
          } else {
            media = document.createElement("img");
            media.alt = "";
          }
          media.src = url;
          preview.appendChild(media);
        }

        const meta = document.createElement("div");
        meta.className = "b1-local-preview-meta";
        meta.innerHTML = `
          <span class="b1-file-type-chip"></span>
          <b></b>
          <small></small>
        `;
        qs(".b1-file-type-chip", meta).textContent = kind.toUpperCase();
        qs("b", meta).textContent = file.name;
        qs("small", meta).textContent = `${humanSize(file.size)} · not uploaded until you save`;
        preview.appendChild(meta);

        zone.appendChild(preview);
      };

      input.addEventListener("change", () => previewFile(input.files?.[0]));

      ["dragenter","dragover"].forEach(name => zone.addEventListener(name, event => {
        event.preventDefault();
        zone.classList.add("is-dragging");
      }));

      ["dragleave","drop"].forEach(name => zone.addEventListener(name, event => {
        event.preventDefault();
        zone.classList.remove("is-dragging");
      }));

      zone.addEventListener("drop", event => {
        const file = event.dataTransfer?.files?.[0];
        if (!file) return;
        try {
          const dt = new DataTransfer();
          dt.items.add(file);
          input.files = dt.files;
          previewFile(file);
        } catch (_) {
          previewFile(file);
        }
      });
    });
  };

  const addPathLabel = () => {
    if (!isChangeForm() && !isChangeList()) return;
    const h1 = qs("#content h1");
    if (!h1 || qs(".b1-path-label", h1.parentElement)) return;
    const type = pageType();
    if (!type) return;

    const label = document.createElement("span");
    label.className = "b1-path-label";
    label.textContent = type.replaceAll("-", " ");
    h1.insertAdjacentElement("afterend", label);
  };

  const highlightRequiredFields = () => {
    if (!isChangeForm()) return;
    qsa(".form-row").forEach(row => {
      const required = qs("label.required", row);
      if (required) row.dataset.b1Required = "1";
    });
  };

  document.addEventListener("DOMContentLoaded", () => {
    injectGuide();
    injectSkillHelper();
    enhanceFiles();
    addPathLabel();
    highlightRequiredFields();
  });
})();
