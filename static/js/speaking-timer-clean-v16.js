(function () {
  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn, {once:true});
    } else {
      fn();
    }
  }

  const tidy = s => (s || '').replace(/\s+/g,' ').trim();

  function isLeaf(el) {
    if (!el) return false;
    return Array.from(el.children || []).filter(
      c => !['svg','path','circle'].includes((c.tagName || '').toLowerCase())
    ).length === 0;
  }

  function cleanup() {
    if (!/\/attempt\/\d+\/speaking\/?$/.test(location.pathname)) return;

    /*
      Remove only exact microphone/debug leaf labels.
      Never hide parent runner containers.
    */
    const exact = [
      /^microphone ready$/i,
      /^microphone will be checked before recording\.?$/i,
      /^live microphone level$/i,
      /^checking microphone\.{0,3}$/i,
      /^microphone active$/i
    ];

    document.querySelectorAll('p,span,label,small,div').forEach(el => {
      if (!isLeaf(el)) return;
      const t = tidy(el.textContent || '');
      if (exact.some(rx => rx.test(t))) {
        el.style.setProperty('display','none','important');

        const parent = el.parentElement;
        if (parent) {
          parent.querySelectorAll('progress,[role="progressbar"]').forEach(bar => {
            bar.style.setProperty('display','none','important');
          });
        }
      }
    });

    /*
      Clean known mic-meter elements only.
    */
    document.querySelectorAll(
      '[id*="mic"][id*="level"],' +
      '[class*="mic"][class*="level"],' +
      '[id*="microphone"][id*="status"],' +
      '[class*="microphone"][class*="status"],' +
      '[data-mic-level],' +
      '[data-microphone-status]'
    ).forEach(el => {
      el.style.setProperty('display','none','important');
    });
  }

  ready(function () {
    cleanup();

    let queued = false;
    const observer = new MutationObserver(() => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => {
        queued = false;
        cleanup();
      });
    });

    observer.observe(document.body, {
      subtree:true,
      childList:true,
      characterData:true,
      attributes:true,
      attributeFilter:['class','style','value']
    });
  });
})();
