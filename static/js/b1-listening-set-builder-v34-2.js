(() => {
  "use strict";

  const DRAFT_KEY="b1-listening-builder-draft-v346";
  const params=new URLSearchParams(window.location.search);

  if(params.get("saved")==="1"){
    localStorage.removeItem(DRAFT_KEY);
  }

  const root=document.querySelector("[data-listening-builder]");
  if(!root)return;

  const form=root.querySelector("[data-listening-form]");
  const partSelect=root.querySelector("[data-part-select]");
  const patternSelect=root.querySelector("[data-pattern-select]");
  const partHelp=root.querySelector("[data-part-help]");
  const patternHelp=root.querySelector("[data-pattern-help]");
  const patternLabel=root.querySelector("[data-pattern-label]");
  const patternSummary=root.querySelector("[data-pattern-summary]");
  const audioCards=[...root.querySelectorAll("[data-audio-card]")];
  const questionCards=[...root.querySelectorAll("[data-question-card]")];
  const countInput=root.querySelector("[data-question-count]");
  const addTrack=root.querySelector("[data-add-track]");
  const addQuestion=root.querySelector("[data-add-question]");
  const errorBox=root.querySelector("[data-builder-error]");
  const errorText=root.querySelector("[data-builder-error-text]");
  const draftStatus=root.querySelector("[data-draft-status]");
  const clearDraft=root.querySelector("[data-clear-draft]");
  const serverDraftNode=document.getElementById("b1-listening-server-draft");

  const parts={
    1:"Part number classifies where the task belongs; it does not lock the task pattern.",
    2:"Choose the task pattern from the actual material for this Set.",
    3:"The same Part number may be prepared with a different supported pattern when your source material requires it.",
    4:"The administrator controls the task pattern independently.",
    5:"Follow the actual audio/question source rather than a hard-coded software assumption."
  };

  const patterns={
    short_single:{
      kind:"single",
      label:"Short recording → choose one answer / reply",
      help:"Three answer choices are shown. Exactly one is marked correct. The student selects one.",
      summary:"Best for a short recording followed by three selectable replies or answers."
    },
    long_single:{
      kind:"single",
      label:"One recording → several multiple-choice questions",
      help:"Several questions can all select the same audio track. Each question has three choices and one correct answer.",
      summary:"Use one shared recording and point several questions to that same track."
    },
    completion:{
      kind:"short",
      label:"Gap / note / sentence completion",
      help:"The student types the missing word, number or short answer.",
      summary:"Use accepted-answer marking instead of answer-choice cards."
    },
    ordering:{
      kind:"ordering",
      label:"Ordering / sequence",
      help:"The student puts supplied items into the correct sequence.",
      summary:"Enter the items and the complete correct order."
    }
  };

  let visibleTracks=3;
  let visibleQuestions=1;
  let busy=false;

  function showError(message,element){
    errorText.textContent=message;
    errorBox.hidden=false;
    errorBox.scrollIntoView({behavior:"smooth",block:"center"});
    if(element){
      setTimeout(()=>element.scrollIntoView({behavior:"smooth",block:"center"}),180);
    }
  }

  function clearError(){
    errorText.textContent="";
    errorBox.hidden=true;
  }

  function enableCard(card,enabled){
    card.querySelectorAll("input,select,textarea,button").forEach(el=>{
      el.disabled=!enabled;
    });
  }

  function setPanel(panel,active){
    panel.hidden=!active;
    panel.querySelectorAll("input,select,textarea").forEach(el=>{
      el.disabled=!active;
    });
  }

  function currentPattern(){
    return patterns[patternSelect.value]||patterns.short_single;
  }

  function renderPattern(){
    const pattern=currentPattern();
    patternHelp.textContent=pattern.help;
    patternLabel.textContent=pattern.label;
    patternSummary.textContent=pattern.summary;

    questionCards.forEach((card,index)=>{
      if(index>=visibleQuestions)return;
      setPanel(card.querySelector("[data-single-panel]"),pattern.kind==="single");
      setPanel(card.querySelector("[data-short-panel]"),pattern.kind==="short");
      setPanel(card.querySelector("[data-order-panel]"),pattern.kind==="ordering");
    });

    saveDraft();
  }

  function showTracks(count){
    visibleTracks=Math.max(3,Math.min(audioCards.length,count));

    audioCards.forEach((card,index)=>{
      const show=index<visibleTracks;
      card.hidden=!show;
      const input=card.querySelector('input[type="file"]');
      if(input)input.disabled=!show;
    });

    questionCards.forEach((card,index)=>{
      if(index>=visibleQuestions)return;
      const select=card.querySelector("[data-track-select]");
      if(!select)return;

      [...select.options].forEach(option=>{
        option.disabled=Number(option.value)>visibleTracks;
      });

      if(Number(select.value)>visibleTracks){
        select.value="1";
      }
    });
  }

  function defaultTrack(index){
    const pattern=currentPattern();

    if(pattern.kind!=="single"||patternSelect.value==="long_single"){
      return "1";
    }

    return String(Math.min(index+1,3));
  }

  function showQuestions(count,applyDefaults=false){
    visibleQuestions=Math.max(1,Math.min(questionCards.length,count));
    countInput.value=String(visibleQuestions);

    questionCards.forEach((card,index)=>{
      const show=index<visibleQuestions;
      card.hidden=!show;
      enableCard(card,show);

      if(!show)return;

      const select=card.querySelector("[data-track-select]");
      if(applyDefaults&&select){
        select.value=defaultTrack(index);
      }
    });

    renderPattern();
  }

  function serializeDraft(){
    const data={};

    [...form.elements].forEach(el=>{
      if(!el.name||el.type==="file"||el.type==="submit")return;

      if(el.type==="radio"){
        if(el.checked)data[el.name]=el.value;
        return;
      }

      if(el.type==="checkbox"){
        data[el.name]=el.checked?"__checked__":"__unchecked__";
        return;
      }

      data[el.name]=el.value;
    });

    data.__visibleTracks=String(visibleTracks);
    data.__visibleQuestions=String(visibleQuestions);
    return data;
  }

  function saveDraft(){
    if(busy)return;
    try{
      localStorage.setItem(DRAFT_KEY,JSON.stringify(serializeDraft()));
    }catch(_error){}
  }

  function restoreDraft(data){
    if(!data||typeof data!=="object"||!Object.keys(data).length)return false;

    const wantedQuestions=Math.max(
      1,
      Math.min(
        questionCards.length,
        Number(data.question_count||data.__visibleQuestions||1)
      )
    );

    let wantedTracks=Math.max(
      3,
      Math.min(
        audioCards.length,
        Number(data.__visibleTracks||3)
      )
    );

    for(let i=1;i<=wantedQuestions;i+=1){
      wantedTracks=Math.max(
        wantedTracks,
        Number(data[`q${i}_track`]||1)
      );
    }

    showTracks(wantedTracks);
    showQuestions(wantedQuestions,false);

    Object.entries(data).forEach(([name,value])=>{
      if(name.startsWith("__"))return;

      const controls=[...form.querySelectorAll(`[name="${CSS.escape(name)}"]`)];
      controls.forEach(el=>{
        if(el.type==="radio"){
          el.checked=String(el.value)===String(value);
        }else if(el.type==="checkbox"){
          el.checked=value==="__checked__"||value==="on"||value===true;
        }else if(el.type!=="file"){
          el.value=value;
        }
      });
    });

    renderPattern();
    return true;
  }

  function validate(){
    clearError();
    countInput.value=String(visibleQuestions);

    const pattern=currentPattern();

    for(let index=0;index<visibleQuestions;index+=1){
      const q=index+1;
      const card=questionCards[index];
      const trackSelect=card.querySelector("[data-track-select]");
      const track=Number(trackSelect.value||0);

      if(!track||track>visibleTracks){
        showError(`Question ${q}: choose the audio track used by this question.`,card);
        return false;
      }

      const audioInput=audioCards[track-1]?.querySelector('input[type="file"]');

      if(!audioInput||!audioInput.files.length){
        showError(
          `Question ${q}: Track ${track} is selected, but no audio file is attached to Track ${track}.`,
          audioCards[track-1]||card
        );
        return false;
      }

      if(pattern.kind==="single"){
        const options=[
          ...card.querySelectorAll('[data-single-panel] input[type="text"]')
        ];

        if(options.length!==3||options.some(el=>!el.value.trim())){
          showError(
            `Question ${q}: enter all 3 answer choices. The student will select only one of them.`,
            card
          );
          return false;
        }

        const correct=card.querySelector(
          '[data-single-panel] input[type="radio"]:checked'
        );

        if(!correct){
          showError(
            `Question ${q}: mark exactly 1 of the 3 choices as the correct answer.`,
            card
          );
          return false;
        }
      }

      if(pattern.kind==="short"){
        const answer=card.querySelector('[name$="_short_answer"]');

        if(!answer?.value.trim()){
          showError(`Question ${q}: enter the accepted answer.`,card);
          return false;
        }
      }

      if(pattern.kind==="ordering"){
        const items=card.querySelector('[name$="_ordering_items"]');
        const order=card.querySelector('[name$="_correct_order"]');

        if(!items?.value.trim()||!order?.value.trim()){
          showError(
            `Question ${q}: enter the ordering items and their complete correct order.`,
            card
          );
          return false;
        }
      }
    }

    return true;
  }

  function setBusy(state){
    busy=state;
    form.querySelectorAll('button[type="submit"]').forEach(button=>{
      button.disabled=state;
    });
  }

  partSelect.addEventListener("change",()=>{
    partHelp.textContent=parts[Number(partSelect.value||1)]||parts[1];
    saveDraft();
  });

  patternSelect.addEventListener("change",()=>{
    renderPattern();

    questionCards.forEach((card,index)=>{
      if(index>=visibleQuestions)return;
      const select=card.querySelector("[data-track-select]");
      if(select)select.value=defaultTrack(index);
    });

    saveDraft();
  });

  addTrack.addEventListener("click",()=>{
    if(visibleTracks<audioCards.length){
      showTracks(visibleTracks+1);
      saveDraft();
    }
  });

  addQuestion.addEventListener("click",()=>{
    if(visibleQuestions>=questionCards.length)return;

    visibleQuestions+=1;
    const card=questionCards[visibleQuestions-1];
    showQuestions(visibleQuestions,false);

    const select=card.querySelector("[data-track-select]");
    if(select)select.value=defaultTrack(visibleQuestions-1);

    renderPattern();
    saveDraft();
  });

  questionCards.forEach((card,index)=>{
    card.querySelector("[data-remove-question]")?.addEventListener("click",()=>{
      if(visibleQuestions<=1||index!==visibleQuestions-1){
        showError("Remove the last visible question first.",card);
        return;
      }

      card.hidden=true;
      enableCard(card,false);
      visibleQuestions-=1;
      countInput.value=String(visibleQuestions);
      saveDraft();
    });
  });

  form.addEventListener("input",saveDraft);
  form.addEventListener("change",saveDraft);

  clearDraft?.addEventListener("click",()=>{
    localStorage.removeItem(DRAFT_KEY);
    draftStatus.hidden=true;
  });

  form.addEventListener("submit",async event=>{
    event.preventDefault();

    if(busy)return;
    if(!validate())return;

    saveDraft();
    setBusy(true);

    const data=new FormData(form);

    if(event.submitter?.name){
      data.set(event.submitter.name,event.submitter.value);
    }

    try{
      const response=await fetch(window.location.href,{
        method:"POST",
        body:data,
        headers:{
          "X-Requested-With":"XMLHttpRequest"
        },
        credentials:"same-origin"
      });

      let payload={};
      let parsedJson=false;
      try{
        payload=await response.json();
        parsedJson=true;
      }catch(_error){}

      if(!response.ok||!payload.ok){
        let fallback="The server could not save this Listening Part. Your entered data has been kept on this page.";

        if(!parsedJson){
          if(response.status===413){
            fallback="The audio upload is larger than the server currently accepts (HTTP 413). Nothing was cleared. Reduce/compress the audio or increase the server upload limit.";
          }else if(response.status===403){
            fallback="Your admin session or security token was rejected (HTTP 403). Nothing was cleared. Refresh the page, sign in again if requested, then reselect the audio files and save.";
          }else if(response.status>=500){
            fallback=`The server returned HTTP ${response.status} before it could send the normal Listening save response. Nothing was cleared. Please send this exact HTTP code if it happens again.`;
          }else if(response.status){
            fallback=`The Listening save request returned HTTP ${response.status}. Nothing was cleared.`;
          }
        }

        showError(payload.error||fallback);
        setBusy(false);
        return;
      }

      localStorage.removeItem(DRAFT_KEY);
      window.location.href=payload.redirect;

    }catch(error){
      console.error(error);
      showError(
        "Network/server connection problem. Nothing on this page has been cleared; please check the connection and try Save again."
      );
      setBusy(false);
    }
  });

  partHelp.textContent=parts[Number(partSelect.value||1)]||parts[1];
  showTracks(3);
  showQuestions(1,true);

  let serverDraft={};
  try{
    serverDraft=JSON.parse(serverDraftNode?.textContent||"{}");
  }catch(_error){}

  let restored=false;

  if(Object.keys(serverDraft).length){
    restored=restoreDraft(serverDraft);
  }else if(params.get("saved")!=="1"){
    try{
      const localDraft=JSON.parse(localStorage.getItem(DRAFT_KEY)||"{}");
      restored=restoreDraft(localDraft);
    }catch(_error){}
  }

  if(restored){
    draftStatus.hidden=false;
  }

  partHelp.textContent=parts[Number(partSelect.value||1)]||parts[1];
  renderPattern();
})();
