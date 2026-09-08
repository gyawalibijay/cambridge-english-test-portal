(function () {
  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn, { once: true });
    } else {
      fn();
    }
  }

  const tidy = s => ((s || '').replace(/\s+/g, ' ').trim());
  const low = el => tidy((el && (el.value || el.textContent)) || '').toLowerCase();

  function visible(el) {
    if (!el) return false;
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return cs.display !== 'none' &&
      cs.visibility !== 'hidden' &&
      r.width > 0 &&
      r.height > 0;
  }

  function all(sel) {
    return Array.from(document.querySelectorAll(sel));
  }

  function exactText(rx, selectors='p,div,span,h1,h2,h3,h4,strong,label') {
    return all(selectors).find(el => visible(el) && rx.test(tidy(el.textContent || ''))) || null;
  }

  function buttonBy(rx) {
    return all('button,a,input[type="button"],input[type="submit"]').find(el =>
      visible(el) && rx.test(tidy(el.value || el.textContent || ''))
    ) || null;
  }

  function getStage() {
    return document.getElementById('runner') ||
      document.querySelector('[data-attempt-id]') ||
      document.querySelector('main') ||
      document.body;
  }

  function findProgress() {
    return all('span,div,strong').find(el =>
      visible(el) && /^\d+\s*\/\s*\d+$/.test(tidy(el.textContent || ''))
    ) || null;
  }

  function findClock() {
    // Prefer known runner timer IDs/classes.
    for (const s of ['#sessionTimer','.session-timer','.reference-session-time','[data-session-timer]']) {
      const el = document.querySelector(s);
      if (el && visible(el)) return el;
    }

    // Find visible mm:ss near top.
    const items = all('span,div,strong,time').filter(el =>
      visible(el) && /^\d{1,2}:\d{2}$/.test(tidy(el.textContent || ''))
    );
    items.sort((a,b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
    return items[0] || null;
  }

  function createStatus(stage, progress, clock) {
    if (!stage || !progress || !clock) return;

    let status = stage.querySelector('.csp-v14-status');
    if (!status) {
      status = document.createElement('div');
      status.className = 'csp-v14-status';
      stage.insertBefore(status, stage.firstChild);
    }

    progress.classList.add('csp-v14-progress');

    const clockBox = document.createElement('span');
    clockBox.className = 'csp-v14-clock';
    clockBox.innerHTML =
      '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"></circle><path d="M12 8v4l3 2"></path></svg>';

    // Move the real timer node so its native JS keeps updating it.
    clockBox.appendChild(clock);

    status.appendChild(progress);
    status.appendChild(clockBox);
  }

  function markCore(stage) {
    const instruction = exactText(/^listen and answer the question$/i);
    if (instruction) instruction.classList.add('csp-v14-task-title');

    const hiddenQuestion = all('p,div,span').find(el =>
      /written question is hidden/i.test(tidy(el.textContent || ''))
    );
    if (hiddenQuestion) hiddenQuestion.classList.add('csp-v14-hidden-question');

    const listen = buttonBy(/^(listen|playing\.\.\.|playing)$/i);
    if (listen) {
      listen.classList.add('csp-v14-listen');
      if (/playing/i.test(low(listen))) listen.classList.add('is-playing');

      let wrap = listen.parentElement;
      if (wrap && wrap !== stage) wrap.classList.add('csp-v14-listen-wrap');
    }

    const answerTitle = exactText(/^now record your answer$/i);
    if (answerTitle) answerTitle.classList.add('csp-v14-answer-title');

    const stateTitle = all('p,div,span,strong').find(el => {
      const t = tidy(el.textContent || '');
      return visible(el) && (
        /^start speaking in$/i.test(t) ||
        /^you have\s+\d+\s+seconds?\s+to answer$/i.test(t)
      );
    });
    if (stateTitle) stateTitle.classList.add('csp-v14-state-title');

    const prepNumber =
      document.getElementById('prepNumber') ||
      all('div,span,strong').find(el =>
        visible(el) &&
        /^\d{1,2}$/.test(tidy(el.textContent || '')) &&
        parseFloat(getComputedStyle(el).fontSize || '0') >= 28
      );

    if (prepNumber) {
      prepNumber.classList.add('csp-v14-count-number');
      const parent = prepNumber.parentElement;
      if (parent) parent.classList.add('csp-v14-round','csp-v14-ring');
    }

    const speak = buttonBy(/^speak$/i);
    if (speak) speak.classList.add('csp-v14-action');

    const done = buttonBy(/^done$/i);
    if (done) done.classList.add('csp-v14-action');

    const recording = all('p,div,span').find(el =>
      visible(el) && /^recording$/i.test(tidy(el.textContent || ''))
    );
    if (recording) recording.classList.add('csp-v14-recording');

    const thanks = exactText(/^(thanks for your answer|thank you for your answer)$/i);
    if (thanks) thanks.classList.add('csp-v14-thanks');

    const retry = buttonBy(/^retry$/i);
    const submit = buttonBy(/^submit$/i);

    if (retry) retry.classList.add('csp-v14-retry');
    if (submit) submit.classList.add('csp-v14-submit');

    if (retry && submit) {
      const parent = retry.parentElement;
      if (parent && submit.parentElement === parent) {
        parent.classList.add('csp-v14-post-actions');
      }
    }

    all('audio').forEach(a => a.classList.add('csp-v14-audio'));
  }

  function hideDebugUI(stage) {
    // Text not present in the supplied reference video.
    const phrases = [
      /microphone ready/i,
      /microphone will be checked before recording/i,
      /live microphone level/i,
      /written question is hidden/i
    ];

    all('p,div,span,label,small').forEach(el => {
      const t = tidy(el.textContent || '');
      if (!t) return;

      if (phrases.some(rx => rx.test(t))) {
        el.classList.add('csp-v14-debug-hidden');
      }
    });

    // The supplied reference does not show microphone level bars.
    stage.querySelectorAll('progress,[role="progressbar"]').forEach(el => {
      el.classList.add('csp-v14-mic-bar');
    });
  }

  function normalize() {
    if (!/\/attempt\/\d+\/speaking\/?$/.test(location.pathname)) return;

    document.body.classList.add('cambridge-video-speaking');

    const stage = getStage();
    if (!stage) return;
    stage.classList.add('csp-v14-stage');

    const progress = findProgress();
    const clock = findClock();

    // Only rearrange status once.
    if (progress && clock && !stage.querySelector('.csp-v14-status')) {
      createStatus(stage, progress, clock);
    }

    markCore(stage);
    hideDebugUI(stage);
  }

  ready(function () {
    normalize();

    // Runner changes state dynamically: Listen -> Prep -> Recording -> Replay.
    const observer = new MutationObserver(function () {
      requestAnimationFrame(normalize);
    });

    observer.observe(document.body, {
      subtree:true,
      childList:true,
      characterData:true,
      attributes:true,
      attributeFilter:['class','disabled','value','style']
    });
  });
})();
