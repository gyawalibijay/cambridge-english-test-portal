(function () {
  'use strict';

  const PATH_RE = /\/attempt\/(\d+)\/speaking\/?$/;
  const UPDATE_EVERY_MS = 250;

  function matchAttempt() {
    return location.pathname.match(PATH_RE);
  }

  function getRunner() {
    return document.getElementById('runner');
  }

  function getPartOrder() {
    const runner = getRunner();

    const value = Number(
      runner?.getAttribute('data-v20-part-order') ||
      runner?.getAttribute('data-part-order')
    );

    if (Number.isFinite(value) && value >= 1 && value <= 5) {
      return value;
    }

    const total = Number(
      runner?.getAttribute('data-v20-part-total')
    );

    return total === 1 ? 5 : 1;
  }

  function partDurationSeconds(partOrder) {
    return partOrder === 5 ? 110 : 300;
  }

  function stateKey() {
    const match = matchAttempt();
    const attemptId = match ? match[1] : 'unknown';
    return `upskill-speaking-v21:${attemptId}:part:${getPartOrder()}`;
  }

  function getOrCreateDeadline() {
    const key = stateKey();
    const durationMs = partDurationSeconds(getPartOrder()) * 1000;

    let deadline = Number(sessionStorage.getItem(key));

    if (!Number.isFinite(deadline) || deadline <= 0) {
      deadline = Date.now() + durationMs;
      sessionStorage.setItem(key, String(deadline));
    }

    return { key, deadline, durationMs };
  }

  function formatTime(ms) {
    const totalSeconds = Math.max(0, Math.ceil(ms / 1000));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;

    return (
      String(minutes).padStart(2, '0') +
      ':' +
      String(seconds).padStart(2, '0')
    );
  }

  function visibleTimerNode() {
    return document.querySelector(
      '#cambridgeV18Topbar .v18-session-text'
    );
  }

  function hideNativeTimer() {
    const native = document.getElementById('sessionTimer');

    if (!native) return;

    /*
      Do NOT change its value.
      The old/native runner may keep updating it internally.
      We simply keep it out of the visible UI so it cannot cause flicker.
    */
    const parent = native.parentElement;

    if (
      parent &&
      !parent.closest('#cambridgeV18Topbar') &&
      parent.children.length <= 5
    ) {
      parent.style.setProperty('display', 'none', 'important');
    } else if (!native.closest('#cambridgeV18Topbar')) {
      native.style.setProperty('display', 'none', 'important');
    }
  }

  function hideDuplicateCounter() {
    const runner = getRunner();
    const topbar = document.getElementById('cambridgeV18Topbar');

    if (!runner) return;

    runner.querySelectorAll('div,span,strong').forEach(function (el) {
      if (topbar && topbar.contains(el)) return;

      const text = (el.textContent || '')
        .replace(/\s+/g, '')
        .trim();

      if (!/^\d+\/\d+$/.test(text)) return;

      const meaningfulChildren = Array.from(
        el.children || []
      ).filter(function (child) {
        const tag = (child.tagName || '').toLowerCase();
        return !['svg', 'path', 'circle'].includes(tag);
      });

      if (meaningfulChildren.length === 0) {
        el.style.setProperty('display', 'none', 'important');
      }
    });
  }

  function disableLeaveWarning() {
    window.onbeforeunload = null;
    window.__speaking_beforeunload_disabled = null;

    const submit = document.getElementById('submitButton');

    if (submit && submit.dataset.v21Bound !== '1') {
      submit.dataset.v21Bound = '1';

      submit.addEventListener(
        'click',
        function () {
          window.onbeforeunload = null;
          window.__speaking_beforeunload_disabled = null;
        },
        true
      );
    }
  }

  function start() {
    if (!matchAttempt()) return;

    hideNativeTimer();
    hideDuplicateCounter();
    disableLeaveWarning();

    const state = getOrCreateDeadline();
    let intervalId = null;
    let stopped = false;

    function paint() {
      if (stopped) return;

      const node = visibleTimerNode();

      if (!node) {
        return;
      }

      const remaining = state.deadline - Date.now();

      node.textContent = formatTime(remaining);

      if (remaining <= 0) {
        node.textContent = '00:00';
        stopped = true;

        if (intervalId !== null) {
          clearInterval(intervalId);
        }
      }
    }

    /*
      Paint once immediately, then use ONE interval.
      No requestAnimationFrame loop, no native timer writes,
      no V18 timer mirroring = no competing values/flicker.
    */
    paint();
    intervalId = window.setInterval(paint, UPDATE_EVERY_MS);

    const observer = new MutationObserver(function () {
      hideNativeTimer();
      hideDuplicateCounter();
      disableLeaveWarning();

      /*
        If V18 rebuilds the visible topbar during a state change,
        immediately repaint the correct timer into the new node.
      */
      paint();
    });

    observer.observe(document.body, {
      subtree: true,
      childList: true
    });

    window.addEventListener('pagehide', function () {
      if (intervalId !== null) {
        clearInterval(intervalId);
      }
      observer.disconnect();
    }, { once: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      start,
      { once: true }
    );
  } else {
    start();
  }
})();
