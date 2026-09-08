(function () {
  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn, { once:true });
    } else {
      fn();
    }
  }

  const tidy = s => (s || '').replace(/\s+/g,' ').trim();

  function visible(el) {
    if (!el) return false;
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return cs.display !== 'none' &&
      cs.visibility !== 'hidden' &&
      r.width > 0 &&
      r.height > 0;
  }

  function isLeafish(el) {
    if (!el) return false;
    const elementChildren = Array.from(el.children || []).filter(
      c => !['svg','path','circle'].includes(c.tagName?.toLowerCase())
    );
    return elementChildren.length === 0;
  }

  function exactVisible(rx, selector='p,span,label,small,div,strong,h1,h2,h3,h4') {
    return Array.from(document.querySelectorAll(selector))
      .find(el => visible(el) && isLeafish(el) && rx.test(tidy(el.textContent || ''))) || null;
  }

  function button(rx) {
    return Array.from(document.querySelectorAll('button,a,input[type="button"],input[type="submit"]'))
      .find(el => visible(el) && rx.test(tidy(el.value || el.textContent || ''))) || null;
  }

  function addClass(el, cls) {
    if (el) el.classList.add(cls);
  }

  function normalize() {
    if (!/\/attempt\/\d+\/speaking\/?$/.test(location.pathname)) return;

    document.body.classList.add('cambridge-speaking-safe-v15');

    /*
      IMPORTANT:
      Remove dangerous runtime hiding classes from all structural containers.
      V15 never hides a parent based on descendant text.
    */
    document.querySelectorAll(
      '#runner.csp-v14-debug-hidden,main.csp-v14-debug-hidden,.csp-v14-stage.csp-v14-debug-hidden,.attempt-shell.csp-v14-debug-hidden'
    ).forEach(el => el.classList.remove('csp-v14-debug-hidden'));

    // Main task text.
    addClass(exactVisible(/^listen and answer the question$/i), 'v15-task-title');
    addClass(exactVisible(/^now record your answer$/i), 'v15-answer-title');

    // State labels.
    const state = exactVisible(
      /^(start speaking in|you have\s+\d+\s+seconds?\s+to answer)$/i
    );
    addClass(state, 'v15-state-title');

    // Listen.
    const listen = button(/^(listen|playing\.\.\.|playing)$/i);
    if (listen) {
      listen.classList.add('v15-listen');
      if (/playing/i.test(tidy(listen.value || listen.textContent || ''))) {
        listen.classList.add('v15-playing');
      } else {
        listen.classList.remove('v15-playing');
      }
    }

    // Progress badge and timer.
    const progress = Array.from(document.querySelectorAll('span,div,strong'))
      .find(el => visible(el) && isLeafish(el) && /^\d+\s*\/\s*\d+$/.test(tidy(el.textContent || '')));
    addClass(progress, 'v15-progress');

    const clockCandidates = Array.from(document.querySelectorAll('span,div,strong,time'))
      .filter(el => visible(el) && isLeafish(el) && /^\d{1,2}:\d{2}$/.test(tidy(el.textContent || '')));
    clockCandidates.sort((a,b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
    addClass(clockCandidates[0] || null, 'v15-clock');

    // Big countdown number.
    const prepNumber =
      document.getElementById('prepNumber') ||
      Array.from(document.querySelectorAll('span,div,strong'))
        .find(el => {
          if (!visible(el) || !isLeafish(el)) return false;
          if (!/^\d{1,2}$/.test(tidy(el.textContent || ''))) return false;
          return parseFloat(getComputedStyle(el).fontSize || '0') >= 28;
        });

    if (prepNumber) {
      prepNumber.classList.add('v15-big-number');
      const ring = prepNumber.parentElement;
      if (ring) ring.classList.add('v15-ring');
    }

    // Buttons.
    addClass(button(/^speak$/i), 'v15-action');
    addClass(button(/^done$/i), 'v15-action');

    const retry = button(/^retry$/i);
    const submit = button(/^submit$/i);
    addClass(retry, 'v15-retry');
    addClass(submit, 'v15-submit');

    if (retry && submit && retry.parentElement === submit.parentElement) {
      retry.parentElement.classList.add('v15-post-actions');
    }

    // Recording leaf label.
    addClass(exactVisible(/^recording$/i), 'v15-recording');

    /*
      Hide ONLY exact leaf nodes for debug text.
      This is the bug V14 got wrong.
    */
    [
      /^the written question is hidden for this part\.?$/i,
      /^microphone ready$/i,
      /^microphone will be checked before recording\.?$/i,
      /^live microphone level$/i,
    ].forEach(rx => {
      document.querySelectorAll('p,span,label,small,div').forEach(el => {
        if (visible(el) && isLeafish(el) && rx.test(tidy(el.textContent || ''))) {
          el.classList.add('v15-debug-leaf');
        }
      });
    });

    /*
      Tag only progress bars that are adjacent to known microphone debug labels.
      Never hide every progress element globally.
    */
    document.querySelectorAll('.v15-debug-leaf').forEach(label => {
      const parent = label.parentElement;
      if (!parent) return;
      parent.querySelectorAll('progress,[role="progressbar"]').forEach(bar => {
        bar.classList.add('v15-mic-debug');
      });
    });
  }

  ready(function () {
    normalize();

    let queued = false;
    const observer = new MutationObserver(function () {
      if (queued) return;
      queued = true;
      requestAnimationFrame(function () {
        queued = false;
        normalize();
      });
    });

    observer.observe(document.body, {
      subtree:true,
      childList:true,
      characterData:true,
      attributes:true,
      attributeFilter:['class','disabled','value']
    });
  });
})();
