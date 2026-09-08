/* B1 READY ADMIN V33.9.1 — Cambridge Question Workspace */
(() => {
  "use strict";

  const body = document.body;
  const path = location.pathname;
  const params = new URLSearchParams(location.search);
  const qs = (s, root=document) => root.querySelector(s);
  const qsa = (s, root=document) => [...root.querySelectorAll(s)];

  const QUESTION_LIST = "/admin/question_bank/question/";
  const isQuestionList = path === QUESTION_LIST;
  const isQuestionForm =
    path.startsWith(QUESTION_LIST) &&
    (path.endsWith("/add/") || path.endsWith("/change/"));

  /* Remove any V33.8 filter drawer state/classes that may remain. */
  const removeOldFilterUi = () => {
    body.classList.remove("b1-filter-open", "b1-filter-collapsed");
    qsa(".b1-filter-backdrop").forEach(el => el.remove());
  };

  const skillIcon = skill => ({
    Reading: "R",
    Listening: "L",
    Speaking: "S",
    Writing: "W",
  }[skill] || skill.charAt(0));

  const skillText = skill => ({
    Reading: "Passage, prompt, options and answer.",
    Listening: "Audio/stimulus, prompt, options and answer.",
    Speaking: "Prompt/audio, preparation and response timing.",
    Writing: "Task prompt, instructions and marking limits.",
  }[skill] || "");

  const urlWithSkill = skill => {
    const url = new URL(location.origin + QUESTION_LIST);
    url.searchParams.set("b1_skill", skill);
    return url.pathname + url.search;
  };

  const addWithSkill = skill =>
    `${QUESTION_LIST}add/?skill=${encodeURIComponent(skill)}`;

  const installQuestionWorkspace = () => {
    if (!isQuestionList || qs(".b1-question-workspace")) return;

    body.classList.add("b1-question-list");

    const main = qs("#content-main");
    const changelist = qs("#changelist");
    if (!main || !changelist) return;

    const current = params.get("b1_skill") || "";

    const section = document.createElement("section");
    section.className = "b1-question-workspace";

    const cards = ["Reading","Listening","Speaking","Writing"].map(skill => `
      <article class="b1-skill-workspace-card ${current.toLowerCase() === skill.toLowerCase() ? "is-active" : ""}">
        <span>${skillIcon(skill)}</span>
        <strong>${skill}</strong>
        <small>${skillText(skill)}</small>
        <div class="b1-skill-workspace-actions">
          <a class="b1-skill-view" href="${urlWithSkill(skill)}">View ${skill}</a>
          <a class="b1-skill-add" href="${addWithSkill(skill)}">+ Add</a>
        </div>
      </article>
    `).join("");

    section.innerHTML = `
      <div class="b1-question-workspace-head">
        <div>
          <span class="b1-question-workspace-kicker">QUESTION WORKSPACE</span>
          <h2>Prepare Cambridge questions by skill, Part and Set.</h2>
          <p>
            Pick one of the four skills. The question list now keeps only the
            useful classification columns, while Part / Set placement is managed
            from the question form.
          </p>
        </div>
        <span class="b1-cambridge-mode">Cambridge only</span>
      </div>

      <div class="b1-skill-workspace-grid">${cards}</div>

      <div class="b1-question-workspace-footer">
        <p>IELTS and UKVI records are not deleted — they are simply hidden from this admin workflow for now.</p>
        <a class="b1-show-all-questions" href="${QUESTION_LIST}">All Cambridge questions</a>
      </div>
    `;

    main.insertBefore(section, changelist);
  };

  const getSkillSelect = () => {
    const candidates = [
      "#id_skill",
      "#id_test_skill",
      "#id_section_type",
      "#id_skill_type",
    ];

    for (const selector of candidates) {
      const el = qs(selector);
      if (el) return el;
    }

    return null;
  };

  const selectedSkill = () => {
    const select = getSkillSelect();
    if (!select) return params.get("skill") || "";

    const option = select.options?.[select.selectedIndex];
    return (option?.textContent || select.value || "").trim();
  };

  const normalizedSkill = value => {
    const text = String(value || "").toLowerCase();
    for (const skill of ["Reading","Listening","Speaking","Writing"]) {
      if (text.includes(skill.toLowerCase())) return skill;
    }
    return "";
  };

  const helpForSkill = skill => {
    const data = {
      Reading: [
        ["1", "Place it correctly", "Choose the Reading Part and Set in Part / Set placement."],
        ["2", "Add source content", "Use the passage/stimulus field when the question belongs to shared reading content."],
        ["3", "Check answer", "Confirm options, answer key and student-visible wording before saving."],
      ],
      Listening: [
        ["1", "Choose Part + Set", "Assign the Listening Part / Set before publishing."],
        ["2", "Attach audio", "Use shared Stimulus audio when several questions use the same recording."],
        ["3", "Test playback", "Preview the uploaded audio and confirm the correct answer before saving."],
      ],
      Speaking: [
        ["1", "Choose Part + Set", "Place the question in the correct Speaking Part / Set."],
        ["2", "Check prompt mode", "Confirm whether students hear audio, see text, or both."],
        ["3", "Check timing", "Verify preparation seconds, response seconds and recording requirements."],
      ],
      Writing: [
        ["1", "Choose Part + Set", "Assign the Writing task to its correct Part / Set."],
        ["2", "Write task clearly", "Add the scenario/instruction exactly as the student should receive it."],
        ["3", "Check marking rules", "Confirm word limits, rubric/evaluation settings and task visibility."],
      ],
    };
    return data[skill] || [
      ["1", "Choose skill", "Start with Reading, Listening, Speaking or Writing."],
      ["2", "Add question", "Enter only student-facing content and necessary source media."],
      ["3", "Place + review", "Assign Part / Set and preview before considering it ready."],
    ];
  };

  const renderBuilderHelp = section => {
    const skill = normalizedSkill(selectedSkill());
    const items = helpForSkill(skill);

    const tabs = qsa(".b1-builder-skill-tabs a", section);
    tabs.forEach(tab => {
      tab.classList.toggle(
        "is-active",
        tab.dataset.skill.toLowerCase() === skill.toLowerCase()
      );
    });

    const help = qs(".b1-builder-help", section);
    help.innerHTML = items.map(([n,title,text]) => `
      <div>
        <span>STEP ${n}</span>
        <strong>${title}</strong>
        <small>${text}</small>
      </div>
    `).join("");
  };

  const installQuestionBuilder = () => {
    if (!isQuestionForm || qs(".b1-question-builder")) return;

    const main = qs("#content-main");
    if (!main) return;

    const section = document.createElement("section");
    section.className = "b1-question-builder";

    const tabs = ["Reading","Listening","Speaking","Writing"].map(skill => `
      <a href="${addWithSkill(skill)}" data-skill="${skill}">${skill}</a>
    `).join("");

    section.innerHTML = `
      <div class="b1-question-builder-top">
        <div>
          <span class="b1-question-builder-kicker">CAMBRIDGE QUESTION BUILDER</span>
          <h3>Question → source/media → Part / Set → review.</h3>
          <p>
            Program is restricted to Cambridge for this workflow. Use the placement
            section below the form to connect the question to its correct Part and Set.
          </p>
        </div>
        <span class="b1-cambridge-mode">Cambridge only</span>
      </div>

      <div class="b1-builder-skill-tabs">${tabs}</div>
      <div class="b1-builder-help"></div>
    `;

    const guide = qs(".b1-content-guide", main);
    if (guide) {
      guide.insertAdjacentElement("afterend", section);
    } else {
      main.insertBefore(section, main.firstChild);
    }

    renderBuilderHelp(section);

    const select = getSkillSelect();
    select?.addEventListener("change", () => renderBuilderHelp(section));
  };

  document.addEventListener("DOMContentLoaded", () => {
    removeOldFilterUi();
    installQuestionWorkspace();
    installQuestionBuilder();
  });
})();
