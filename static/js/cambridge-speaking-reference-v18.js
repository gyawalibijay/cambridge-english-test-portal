(function () {
  'use strict';

  const PATH_RE = /\/attempt\/\d+\/speaking\/?$/;
  const tidy = value => (value || '').replace(/\s+/g, ' ').trim();

  function progressSource(runner) {
    const native = runner && runner.querySelector('.reference-progress');
    if (
      native &&
      !native.closest('#cambridgeV18Topbar') &&
      /^\d+\s*\/\s*\d+$/.test(tidy(native.textContent))
    ) {
      return native;
    }
    return null;
  }

  function progressPercent(text) {
    const match = tidy(text).match(/^(\d+)\s*\/\s*(\d+)$/);
    if (!match) return 0;
    const current = Number(match[1]);
    const total = Number(match[2]) || 1;
    return Math.max(0, Math.min(100, (current / total) * 100));
  }

  function syncProgress(runner, bar) {
    const source = progressSource(runner);
    if (!source) return;
    const text = tidy(source.textContent);
    const percent = progressPercent(text);
    const fill = bar.querySelector('.v18-progress-fill');
    const label = bar.querySelector('.v18-progress-text');
    fill.style.width = percent + '%';
    label.style.width = percent + '%';
    label.textContent = text;
    source.classList.add('v18-original-progress');
  }

  function ensureTopbar(runner) {
    let bar = document.getElementById('cambridgeV18Topbar');
    if (!bar) {
      bar = document.createElement('div');
      bar.id = 'cambridgeV18Topbar';
      bar.innerHTML = `
        <div class="v18-progress-track" aria-label="Question progress">
          <div class="v18-progress-fill"></div>
          <span class="v18-progress-text">1/4</span>
        </div>
        <div class="v18-session" aria-label="Part time remaining">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="12" r="9"></circle>
            <path d="M12 7v5l3 2"></path>
          </svg>
          <span class="v18-session-text">--:--</span>
        </div>
        <div class="v18-module-pill">Speaking</div>
      `;
      runner.insertBefore(bar, runner.firstChild);
    }

    syncProgress(runner, bar);

    const nativeTimer = document.getElementById('sessionTimer');
    if (nativeTimer && !nativeTimer.closest('#cambridgeV18Topbar')) {
      const visibleTimer = bar.querySelector('.v18-session-text');
      const value = tidy(nativeTimer.textContent);
      if (value) visibleTimer.textContent = value;
      const parent = nativeTimer.parentElement;
      if (parent && parent.children.length <= 4) {
        parent.classList.add('v18-original-clock-wrap');
      } else {
        nativeTimer.classList.add('v18-original-progress');
      }
    }
  }

  function start() {
    if (!PATH_RE.test(location.pathname)) return;
    const runner = document.getElementById('runner');
    if (!runner) return;

    document.body.classList.add('cambridge-speaking-reference-v18');
    const shell = runner.closest('section') || runner.closest('main') || runner.parentElement;
    if (shell) shell.classList.add('v18-shell');
    ensureTopbar(runner);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, {once:true});
  } else {
    start();
  }
  window.addEventListener('pageshow', start);
})();
