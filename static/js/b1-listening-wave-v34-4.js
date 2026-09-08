(() => {
  "use strict";

  if(document.body?.dataset.questionSkill !== "listening") return;

  const normalize = value =>
    (value || "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();

  const card =
    document.querySelector(".exam-question-card") ||
    document.querySelector("#content-main") ||
    document.querySelector("main");

  if(!card) return;

  card.classList.add("b1-listening-reference-card");

  /* ----------------------------------------------------------
     1. Main heading
     ---------------------------------------------------------- */

  const topHeading =
    [...document.querySelectorAll("h1")]
      .find(el => {
        const text = normalize(el.textContent);
        return (
          text.includes("listen and choose") ||
          text.includes("listen and answer") ||
          text === "question"
        );
      });

  if(topHeading){
    topHeading.textContent = "Listen and choose the correct reply";
    topHeading.classList.add("b1-listening-title");

    const parent = topHeading.parentElement;
    if(parent){
      parent.classList.add("b1-listening-reference-title");
    }
  }

  /* ----------------------------------------------------------
     2. Remove duplicate helper copy only on Listening
     ---------------------------------------------------------- */

  const removable = new Set([
    "listen carefully",
    "choose the most appropriate reply.",
    "choose the most appropriate reply",
    "choose the correct reply.",
    "choose the correct reply"
  ]);

  [...card.querySelectorAll("h2,h3,h4,h5,p,strong,b,span,div,label")]
    .forEach(el => {
      if(el.querySelector("input,button,audio,select,textarea")) return;

      const text = normalize(el.textContent);

      if(removable.has(text)){
        el.classList.add("b1-listening-hidden");
      }
    });

  /* ----------------------------------------------------------
     3. Audio player
     ---------------------------------------------------------- */

  const audios = [
    ...card.querySelectorAll(".exam-device audio, audio")
  ];

  const stopOtherAudio = current => {
    audios.forEach(audio => {
      if(audio === current) return;

      audio.pause();

      const button =
        audio
          .closest(".b1-listen-player")
          ?.querySelector(".b1-listen-button");

      if(button){
        button.classList.remove("is-playing");

        const label = button.querySelector("[data-listen-label]");
        if(label) label.textContent = "Listen";
      }
    });
  };

  audios.forEach(audio => {
    let wrapper = audio.closest(".b1-listen-player");
    let button;

    if(!wrapper){
      wrapper = document.createElement("div");
      wrapper.className = "b1-listen-player";

      button = document.createElement("button");
      button.type = "button";
      button.className = "b1-listen-button";
      button.setAttribute("aria-label", "Play listening audio");
      button.innerHTML = `
        <span class="b1-listen-wave" aria-hidden="true">
          <i></i><i></i><i></i><i></i><i></i><i></i><i></i>
        </span>
        <span data-listen-label>Listen</span>
      `;

      audio.parentNode.insertBefore(wrapper, audio);
      wrapper.appendChild(button);
      wrapper.appendChild(audio);
    }else{
      button = wrapper.querySelector(".b1-listen-button");
    }

    if(!button) return;

    audio.classList.add("b1-listen-source");
    audio.removeAttribute("controls");

    const label = button.querySelector("[data-listen-label]");

    /*
      Reference behavior requested:
      idle / paused / ended = "Listen"
      playing = "Listening"
      Do not use a separate replay label in the idle state.
    */
    button.classList.toggle("is-playing", !audio.paused);

    if(label){
      label.textContent = audio.paused ? "Listen" : "Listening";
    }

    if(!button.dataset.b1ReferenceBound){
      button.dataset.b1ReferenceBound = "1";

      button.addEventListener("click", async () => {
        if(audio.paused){
          stopOtherAudio(audio);

          /*
            Starting again from the beginning after the track has ended
            keeps the visual behavior intuitive while still saying Listen.
          */
          if(audio.ended){
            audio.currentTime = 0;
          }

          try{
            await audio.play();
          }catch(error){
            console.error("Listening audio could not play", error);
          }
        }else{
          audio.pause();
        }
      });
    }

    if(!audio.dataset.b1ReferenceBound){
      audio.dataset.b1ReferenceBound = "1";

      audio.addEventListener("play", () => {
        button.classList.add("is-playing");
        if(label) label.textContent = "Listening";
      });

      audio.addEventListener("pause", () => {
        if(audio.ended) return;

        button.classList.remove("is-playing");
        if(label) label.textContent = "Listen";
      });

      audio.addEventListener("ended", () => {
        button.classList.remove("is-playing");
        if(label) label.textContent = "Listen";
      });
    }
  });

  /* ----------------------------------------------------------
     4. Answer choices
     ---------------------------------------------------------- */

  const radios = [
    ...card.querySelectorAll('input[type="radio"]')
  ];

  const optionLabels = [];

  radios.forEach(radio => {
    const label =
      radio.closest("label") ||
      radio.parentElement;

    if(!label) return;

    if(!optionLabels.includes(label)){
      optionLabels.push(label);
    }

    label.classList.add("b1-listening-option");

    /*
      Wrap presentation text so it can be centered independently from
      the hidden native radio. Do not change the input value/name.
    */
    if(!label.querySelector(".b1-listening-option-text")){
      const nodes = [
        ...label.childNodes
      ].filter(node => {
        if(node === radio) return false;

        if(node.nodeType === Node.TEXT_NODE){
          return Boolean(node.textContent.trim());
        }

        if(node.nodeType === Node.ELEMENT_NODE){
          return !node.matches(
            'input[type="radio"], .b1-listening-option-text'
          );
        }

        return false;
      });

      if(nodes.length){
        const span = document.createElement("span");
        span.className = "b1-listening-option-text";

        const first = nodes[0];
        label.insertBefore(span, first);

        nodes.forEach(node => span.appendChild(node));
      }
    }

    const sync = () => {
      label.classList.toggle("is-selected", radio.checked);
    };

    sync();
    radio.addEventListener("change", () => {
      optionLabels.forEach(other =>
        other.classList.remove("is-selected")
      );
      sync();
    });
  });

  if(optionLabels.length){
    /*
      Add one clean divider just above the first choice, like the
      supplied original Listening screen.
    */
    const first = optionLabels[0];

    let group = first.parentElement;

    if(group){
      group.classList.add("b1-listening-options");

      if(
        !group.previousElementSibling ||
        !group.previousElementSibling.classList.contains(
          "b1-listening-divider"
        )
      ){
        const divider = document.createElement("div");
        divider.className = "b1-listening-divider";
        divider.setAttribute("aria-hidden", "true");

        group.parentNode.insertBefore(divider, group);
      }
    }
  }

  /* ----------------------------------------------------------
     5. Progress count styling
     ---------------------------------------------------------- */

  const progressCandidate = [
    ...document.querySelectorAll("span,small,b,strong,div")
  ].find(el => {
    if(el.children.length) return false;

    return /^\s*\d+\s*\/\s*\d+\s*$/.test(
      el.textContent || ""
    );
  });

  if(progressCandidate){
    progressCandidate.classList.add(
      "b1-listening-progress-count"
    );
  }
})();
