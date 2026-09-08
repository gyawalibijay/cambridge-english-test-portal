(function () {
  'use strict';

  const PATH_RE = /\/attempt\/(\d+)\/speaking\/?$/;

  function attemptMatch() {
    return location.pathname.match(PATH_RE);
  }

  function getRunner() {
    return document.getElementById('runner');
  }

  function isVisible(el) {
    if (!el || el.classList.contains('hidden')) return false;
    const style = getComputedStyle(el);
    return style.display !== 'none' && style.visibility !== 'hidden';
  }

  function getPartOrder() {
    const runner = getRunner();
    const raw = Number(
      runner?.getAttribute('data-v20-part-order') ||
      runner?.getAttribute('data-part-order')
    );

    if (Number.isFinite(raw) && raw >= 1 && raw <= 5) return raw;

    const total = Number(runner?.getAttribute('data-v20-part-total'));
    return total === 1 ? 5 : 1;
  }

  // Session clock is owned by speaking-session-clock.js.

  function hideNativeTimer() {
    const native = document.getElementById('sessionTimer');

    if (!native || native.closest('#cambridgeV18Topbar')) return;

    const parent = native.parentElement;

    if (parent && parent.children.length <= 5) {
      parent.style.display = 'none';
    } else {
      native.style.display = 'none';
    }
  }

  function hideDuplicateCounter() {
    const runner = getRunner();
    const topbar = document.getElementById('cambridgeV18Topbar');

    if (!runner) return;

    runner.querySelectorAll('div,span,strong').forEach(function (el) {
      if (topbar && topbar.contains(el)) return;

      const text = (el.textContent || '').replace(/\s+/g, '').trim();
      if (!/^\d+\/\d+$/.test(text)) return;

      const children = Array.from(el.children || []).filter(function (child) {
        return !['svg','path','circle'].includes(
          (child.tagName || '').toLowerCase()
        );
      });

      if (children.length === 0) {
        el.style.display = 'none';
      }
    });
  }

  function disableLeaveWarning() {
    window.onbeforeunload = null;
    window.__speaking_beforeunload_disabled = null;

    const submit = document.getElementById('submitButton');

    if (submit && submit.dataset.v22Bound !== '1') {
      submit.dataset.v22Bound = '1';

      submit.addEventListener('click', function () {
        window.onbeforeunload = null;
        window.__speaking_beforeunload_disabled = null;
      }, true);
    }
  }

  class RingController {
    constructor(panelId, ringId, numberId) {
      this.panel = document.getElementById(panelId);
      this.ring = document.getElementById(ringId);
      this.number = document.getElementById(numberId);
      this.wasVisible = false;
      this.running = false;
      this.raf = null;
    }

    start() {
      if (!this.panel || !this.ring || !this.number || this.running) return;

      const seconds = Math.max(
        1,
        parseInt((this.number.textContent || '').trim(), 10) || 1
      );

      const totalMs = seconds * 1000;
      const startedAt = performance.now();

      this.running = true;

      const frame = (now) => {
        if (!this.running || !isVisible(this.panel)) {
          this.running = false;
          this.raf = null;
          return;
        }

        const elapsed = Math.min(totalMs, now - startedAt);
        const angle = (elapsed / totalMs) * 360;

        this.ring.style.setProperty(
          '--v19-angle',
          `${angle.toFixed(2)}deg`
        );

        if (elapsed < totalMs) {
          this.raf = requestAnimationFrame(frame);
        } else {
          this.running = false;
          this.raf = null;
        }
      };

      this.raf = requestAnimationFrame(frame);
    }

    check() {
      const nowVisible = isVisible(this.panel);

      if (nowVisible && !this.wasVisible) {
        this.start();
      }

      if (!nowVisible && this.running) {
        this.running = false;

        if (this.raf !== null) {
          cancelAnimationFrame(this.raf);
        }

        this.raf = null;
      }

      this.wasVisible = nowVisible;
    }
  }

  function start() {
    if (!attemptMatch()) return;


    const preparationRing = new RingController(
      'preparePanel',
      'prepRing',
      'prepNumber'
    );

    const recordingRing = new RingController(
      'recordPanel',
      'recordRing',
      'recordNumber'
    );

    hideNativeTimer();
    hideDuplicateCounter();
    disableLeaveWarning();

    preparationRing.check();
    recordingRing.check();

    /*
      ONE lightweight interval replaces:
      - V19 permanent 60fps loop
      - V20 observer/timer
      - V21 observer/timer

      requestAnimationFrame is used only while an actual circular
      countdown is visible.
    */
    const intervalId = setInterval(function () {
      preparationRing.check();
      recordingRing.check();
      disableLeaveWarning();
    }, 250);

    setTimeout(function () {
      hideNativeTimer();
      hideDuplicateCounter();
    }, 500);

    setTimeout(function () {
      hideNativeTimer();
      hideDuplicateCounter();
    }, 1500);

    window.addEventListener('pagehide', function () {
      clearInterval(intervalId);
    }, { once:true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once:true });
  } else {
    start();
  }
})();
