/* Single owner of the part clock. Preparation is excluded; recordings are unchanged. */
(function () {
  'use strict';
  const runner = document.getElementById('runner');
  if (!runner || runner.dataset.sessionClockBound === '1') return;
  runner.dataset.sessionClockBound = '1';
  const part = Number(runner.dataset.partOrder || 1);
  const duration = (part === 5 ? 110 : 300) * 1000;
  const attempt = runner.dataset.attemptId;
  const key = `upskill-speaking-clock:${attempt}:part:${part}`;
  const legacyKey = `upskill-speaking-v22:${attempt}:part:${part}`;
  const now = () => Date.now();
  const clamp = value => Math.max(0, Math.min(duration, value));
  let remaining = duration;
  let lastAt = now();
  let phase = runner.dataset.clockPhase || 'promptPanel';
  let interval = null;

  try {
    const saved = JSON.parse(sessionStorage.getItem(key) || 'null');
    if (saved && Number.isFinite(saved.remainingMs) && Number.isFinite(saved.savedAt)) {
      remaining = clamp(saved.remainingMs - (saved.phase === 'preparePanel' ? 0 : Math.max(0, lastAt - saved.savedAt)));
    } else {
      const legacy = sessionStorage.getItem(legacyKey);
      if (legacy !== null && Number.isFinite(Number(legacy))) {
        remaining = clamp(Number(legacy) - lastAt);
      }
    }
  } catch (_) { /* Denied storage must not block microphone or submission. */ }

  function persist() {
    try {
      sessionStorage.setItem(key, JSON.stringify({remainingMs: remaining, savedAt: lastAt, phase}));
    } catch (_) { /* Clock still works in memory. */ }
  }

  function settle() {
    const current = now();
    if (phase !== 'preparePanel') remaining = clamp(remaining - Math.max(0, current - lastAt));
    lastAt = current;
  }

  function paint() {
    const seconds = Math.ceil(remaining / 1000);
    const text = String(Math.floor(seconds / 60)).padStart(2, '0') + ':' + String(seconds % 60).padStart(2, '0');
    [document.getElementById('sessionTimer'), document.querySelector('#cambridgeV18Topbar .v18-session-text')].forEach(el => {
      if (el && el.textContent !== text) el.textContent = text;
    });
  }

  function tick() { settle(); paint(); persist(); }
  function start() {
    tick();
    if (interval === null) interval = setInterval(tick, 250);
  }

  document.addEventListener('speaking:panelchange', event => {
    if (!event.detail || !event.detail.panelId) return;
    settle();
    phase = event.detail.panelId;
    runner.dataset.clockPhase = phase;
    persist();
    paint();
  });
  window.addEventListener('pagehide', () => {
    tick();
    if (interval !== null) clearInterval(interval);
    interval = null;
  });
  window.addEventListener('pageshow', start);
  start();
})();
