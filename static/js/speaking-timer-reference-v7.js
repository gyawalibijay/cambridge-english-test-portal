(function(){
  function norm(s){ return (s || '').replace(/\s+/g,' ').trim(); }
  function lower(s){ return norm(s).toLowerCase(); }
  function isVisible(el){
    if(!el) return false;
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return cs.display !== 'none' && cs.visibility !== 'hidden' && r.width > 0 && r.height > 0;
  }
  function isSpeakingPage(){
    const path = location.pathname.toLowerCase();
    const text = lower(document.body.innerText || '');
    return path.includes('/speaking') || text.includes('start speaking in') || text.includes('now record your answer') || text.includes('seconds to answer');
  }
  function queryAll(sel){ return Array.from(document.querySelectorAll(sel)); }
  function textMatches(el, re){ return el && re.test(norm(el.textContent || '')); }
  function findStateLabel(){
    const rx = /^(start speaking in|you have \d+ seconds to answer)$/i;
    return queryAll('p,div,span,h1,h2,h3,h4,strong').find(el => isVisible(el) && textMatches(el, rx)) || null;
  }
  function findInstruction(){
    return queryAll('p,div,span').find(el => isVisible(el) && /^(now record your answer)$/i.test(norm(el.textContent || '')) ) || null;
  }
  function findTopTimer(){
    return queryAll('div,span,p,strong').find(el => isVisible(el) && /^\d{2}:\d{2}$/.test(norm(el.textContent || '')) ) || null;
  }
  function findProgressBadge(){
    return queryAll('div,span').find(el => isVisible(el) && /^\d+\/\d+$/.test(norm(el.textContent || '')) ) || null;
  }
  function findActionButton(){
    const candidates = queryAll('button,a,input[type="button"],input[type="submit"]');
    for(const el of candidates){
      if(!isVisible(el)) continue;
      const t = lower(el.value || el.textContent || '');
      if(t === 'speak' || t === 'done' || t === 'listen') return el;
    }
    return null;
  }
  function findSourceNumber(){
    const stateEl = findStateLabel();
    const nums = queryAll('div,span,strong,p').filter(el => {
      const t = norm(el.textContent || '');
      return isVisible(el) && /^\d{1,2}$/.test(t);
    });
    if(stateEl){
      const sr = stateEl.getBoundingClientRect();
      nums.sort((a,b)=>{
        const ar = a.getBoundingClientRect();
        const br = b.getBoundingClientRect();
        const da = Math.abs((ar.top + ar.height/2) - (sr.top + sr.height/2));
        const db = Math.abs((br.top + br.height/2) - (sr.top + sr.height/2));
        return da - db;
      });
    }
    return nums.find(el => {
      const fs = parseFloat(getComputedStyle(el).fontSize || '0');
      return fs >= 24;
    }) || nums[0] || null;
  }
  function findSourceGroup(sourceNum){
    if(!sourceNum) return null;
    let el = sourceNum;
    for(let i=0;i<5 && el;i++,el=el.parentElement){
      const r = el.getBoundingClientRect();
      if(r.width >= 70 && r.width <= 200 && r.height >= 70 && r.height <= 200 && Math.abs(r.width - r.height) <= 50){
        return el;
      }
    }
    return sourceNum.parentElement || sourceNum;
  }
  function inferTotal(stateText, currentValue, existingTotal){
    const s = lower(stateText || '');
    const matchAnswer = s.match(/you have\s+(\d+)\s+seconds?\s+to\s+answer/);
    if(matchAnswer) return parseInt(matchAnswer[1],10) || existingTotal || currentValue || 10;
    if(s.includes('start speaking in')){
      if(existingTotal && existingTotal <= 10) return existingTotal;
      if(currentValue && currentValue <= 10) return Math.max(currentValue, 4);
      return 4;
    }
    return existingTotal || currentValue || 10;
  }
  function install(){
    if(!isSpeakingPage()) return;

    const sourceNum = findSourceNumber();
    const stateLabel = findStateLabel();
    const instruction = findInstruction();
    const button = findActionButton();

    if(!sourceNum || !stateLabel || !button) return;

    document.body.classList.add('speaking-ref-v7');

    const panel = (stateLabel.closest('main,section,article,div') || stateLabel.parentElement);
    if(panel) panel.classList.add('spk-v7-panel');

    const shell = document.createElement('div');
    shell.className = 'spk-v7-timer-shell';

    const label = document.createElement('div');
    label.className = 'spk-v7-state-label';
    label.textContent = norm(stateLabel.textContent || '');

    const wrap = document.createElement('div');
    wrap.className = 'spk-v7-ring-wrap';
    wrap.innerHTML = `
      <svg class="spk-v7-ring" viewBox="0 0 126 126" aria-hidden="true">
        <circle class="spk-v7-ring-track" cx="63" cy="63" r="50"></circle>
        <circle class="spk-v7-ring-progress" cx="63" cy="63" r="50"></circle>
      </svg>
      <div class="spk-v7-ring-value">0</div>
    `;

    const valueEl = wrap.querySelector('.spk-v7-ring-value');
    const progressEl = wrap.querySelector('.spk-v7-ring-progress');
    const r = 50;
    const circumference = 2 * Math.PI * r;
    progressEl.style.strokeDasharray = `${circumference}`;
    progressEl.style.strokeDashoffset = `${circumference}`;

    shell.appendChild(label);
    shell.appendChild(wrap);

    let currentButtonClass = 'spk-v7-speak-btn';
    const recordRow = document.createElement('div');
    recordRow.className = 'spk-v7-recording';
    recordRow.innerHTML = '<span class="spk-v7-recording-dot"></span><span>Recording</span>';
    recordRow.style.display = 'none';

    const sourceGroup = findSourceGroup(sourceNum);
    if(sourceGroup) sourceGroup.classList.add('spk-v7-source-hidden');

    const insertAfter = stateLabel;
    insertAfter.parentNode.insertBefore(shell, insertAfter.nextSibling);

    button.classList.remove('btn','button','primary','secondary');
    button.classList.add('spk-v7-speak-btn');
    shell.appendChild(recordRow);
    shell.appendChild(button);

    const topTimer = findTopTimer();
    if(topTimer){
      topTimer.classList.add('spk-v7-top-timer');
      if(!topTimer.querySelector('svg')){
        const icon = document.createElement('span');
        icon.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="13" r="8"></circle><path d="M12 9v4l3 2"></path></svg>';
        topTimer.prepend(icon.firstChild);
      }
    }

    const progressBadge = findProgressBadge();
    if(progressBadge) progressBadge.style.minWidth = '50px';

    let total = inferTotal(label.textContent, parseInt(norm(sourceNum.textContent),10) || 0, null);
    let lastValue = parseInt(norm(sourceNum.textContent),10) || total;
    let anim = null;

    function fractionFor(value){
      if(!total || total <= 0) return 0;
      const safe = Math.max(0, Math.min(total, value));
      return safe / total;
    }

    function setProgress(fraction){
      const f = Math.max(0, Math.min(1, fraction));
      const offset = circumference * (1 - f);
      progressEl.style.strokeDashoffset = String(offset);
    }

    function animateTo(nextValue){
      const startFraction = fractionFor(lastValue);
      const endFraction = fractionFor(nextValue);
      const start = performance.now();
      const duration = 980;
      if(anim) cancelAnimationFrame(anim);
      function step(now){
        const t = Math.min(1, (now - start) / duration);
        const current = startFraction + (endFraction - startFraction) * t;
        setProgress(current);
        if(t < 1){
          anim = requestAnimationFrame(step);
        }
      }
      anim = requestAnimationFrame(step);
      lastValue = nextValue;
    }

    function syncButtonState(){
      const txt = lower(button.value || button.textContent || '');
      button.classList.remove('spk-v7-speak-btn','spk-v7-done-btn');
      if(txt === 'done'){
        currentButtonClass = 'spk-v7-done-btn';
        button.classList.add('spk-v7-done-btn');
      }else{
        currentButtonClass = 'spk-v7-speak-btn';
        button.classList.add('spk-v7-speak-btn');
      }
    }

    function refresh(){
      const stateText = norm(stateLabel.textContent || label.textContent || '');
      label.textContent = stateText;
      const current = parseInt(norm(sourceNum.textContent),10) || 0;
      total = inferTotal(stateText, current, total);
      valueEl.textContent = String(current);
      animateTo(current);
      syncButtonState();

      const isRecording = /you have\s+\d+\s+seconds?\s+to\s+answer/i.test(stateText) || lower(button.value || button.textContent || '') === 'done';
      recordRow.style.display = isRecording ? 'flex' : 'none';
    }

    valueEl.textContent = String(lastValue);
    setProgress(fractionFor(lastValue));
    refresh();

    const mo = new MutationObserver(() => refresh());
    mo.observe(sourceNum, {childList:true, subtree:true, characterData:true});
    mo.observe(stateLabel, {childList:true, subtree:true, characterData:true});
    mo.observe(button, {childList:true, subtree:true, characterData:true, attributes:true, attributeFilter:['value','disabled','class']});

    if(instruction) instruction.style.marginBottom = '10px';
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', install, {once:true});
  }else{
    install();
  }
})();
