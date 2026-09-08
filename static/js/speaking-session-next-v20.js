(function () {
  'use strict';

  const PATH_RE = /\/attempt\/(\d+)\/speaking\/?$/;

  function getAttemptId() {
    const m = location.pathname.match(PATH_RE);
    return m ? m[1] : 'unknown';
  }

  function getRunner() {
    return document.getElementById('runner');
  }

  function getPartOrder() {
    const runner = getRunner();

    const fromData = Number(
      runner?.getAttribute('data-v20-part-order') ||
      document.querySelector('[data-part-order]')?.getAttribute('data-part-order')
    );

    if (Number.isFinite(fromData) && fromData >= 1 && fromData <= 5) {
      return fromData;
    }

    const total = Number(runner?.getAttribute('data-v20-part-total'));
    return total === 1 ? 5 : 1;
  }

  function partDurationSeconds(partOrder) {
    return partOrder === 5 ? 110 : 300;
  }

  function timerKey() {
    return [
      'upskill-speaking-session-v20',
      getAttemptId(),
      'part',
      getPartOrder()
    ].join(':');
  }

  function createOrReadDeadline() {
    const key = timerKey();
    const durationMs = partDurationSeconds(getPartOrder()) * 1000;

    let deadline = Number(sessionStorage.getItem(key));

    if (!Number.isFinite(deadline) || deadline <= Date.now()) {
      deadline = Date.now() + durationMs;
      sessionStorage.setItem(key, String(deadline));
    }

    return { key, deadline };
  }

  function format(seconds) {
    seconds = Math.max(0, Math.ceil(seconds));
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }

  function writeTimer(value) {
    const nativeTimer = document.getElementById('sessionTimer');
    const mirrorTimer = document.querySelector(
      '#cambridgeV18Topbar .v18-session-text'
    );

    if (nativeTimer) nativeTimer.textContent = value;
    if (mirrorTimer) mirrorTimer.textContent = value;
  }

  function hideDuplicateProgress() {
    const runner = getRunner();
    if (!runner) return;

    const topbar = document.getElementById('cambridgeV18Topbar');

    runner.querySelectorAll('div,span,strong').forEach(el => {
      if (topbar && topbar.contains(el)) return;

      const text = (el.textContent || '').replace(/\s+/g, '').trim();
      if (!/^\d+\/\d+$/.test(text)) return;

      const meaningfulChildren = Array.from(el.children || []).filter(child => {
        const tag = (child.tagName || '').toLowerCase();
        return !['svg','path','circle'].includes(tag);
      });

      if (meaningfulChildren.length === 0) {
        el.style.setProperty('display', 'none', 'important');
      }
    });
  }

  function disableLeaveWarningDuringSubmit() {
    const submit = document.getElementById('submitButton');
    if (!submit || submit.dataset.v20Bound === '1') return;

    submit.dataset.v20Bound = '1';

    submit.addEventListener('click', function () {
      window.onbeforeunload = null;
      window.__speaking_beforeunload_disabled = null;
    }, true);
  }

  function startSessionTimer() {
    const state = createOrReadDeadline();
    let lastPaint = 0;

    function loop(now) {
      if (now - lastPaint >= 200) {
        lastPaint = now;

        const remainingMs = state.deadline - Date.now();
        const remainingSeconds = Math.max(0, remainingMs / 1000);

        writeTimer(format(remainingSeconds));

        if (remainingMs <= 0) return;
      }

      requestAnimationFrame(loop);
    }

    requestAnimationFrame(loop);
  }

  function init() {
    if (!PATH_RE.test(location.pathname)) return;

    hideDuplicateProgress();
    disableLeaveWarningDuringSubmit();
    startSessionTimer();

    const observer = new MutationObserver(function () {
      hideDuplicateProgress();
      disableLeaveWarningDuringSubmit();
    });

    observer.observe(document.body, {
      subtree:true,
      childList:true
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once:true });
  } else {
    init();
  }
})();
