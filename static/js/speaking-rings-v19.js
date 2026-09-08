(function () {
  'use strict';

  const PATH_RE = /\/attempt\/\d+\/speaking\/?$/;

  function isPanelVisible(panel) {
    if (!panel) return false;

    if (panel.classList.contains('hidden')) return false;

    const style = getComputedStyle(panel);
    if (style.display === 'none' || style.visibility === 'hidden') return false;

    const rect = panel.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function integerText(el) {
    if (!el) return null;
    const match = String(el.textContent || '').trim().match(/^(\d+)$/);
    return match ? Number(match[1]) : null;
  }

  function totalFromRecordingLabel(panel, fallback) {
    if (!panel) return fallback;

    const text = (panel.textContent || '').replace(/\s+/g, ' ');
    const match = text.match(/you have\s+(\d+)\s+seconds?\s+to answer/i);

    if (match) {
      const value = Number(match[1]);
      if (Number.isFinite(value) && value > 0) return value;
    }

    return fallback;
  }

  class RingAnimator {
    constructor(panelId, ringId, numberId, kind) {
      this.panel = document.getElementById(panelId);
      this.ring = document.getElementById(ringId);
      this.number = document.getElementById(numberId);
      this.kind = kind;

      this.active = false;
      this.startedAt = 0;
      this.totalSeconds = 0;
      this.startRemaining = 0;
      this.baseDegrees = 0;
      this.lastVisibleNumber = null;
    }

    reset() {
      this.active = false;
      this.startedAt = 0;
      this.totalSeconds = 0;
      this.startRemaining = 0;
      this.baseDegrees = 0;
      this.lastVisibleNumber = null;

      if (this.ring) {
        this.ring.style.setProperty('--v19-angle', '0deg');
      }
    }

    begin(now) {
      const shown = integerText(this.number);
      if (!Number.isFinite(shown) || shown <= 0) return false;

      let total = shown;

      if (this.kind === 'recording') {
        total = totalFromRecordingLabel(this.panel, shown);
      }

      if (!Number.isFinite(total) || total <= 0) total = shown;

      /*
        If V19 starts after the native countdown has already begun,
        derive the initial visual position from the displayed remaining
        number instead of jumping back to zero.
      */
      this.totalSeconds = total;
      this.startRemaining = Math.min(shown, total);
      this.baseDegrees =
        ((total - this.startRemaining) / total) * 360;

      this.startedAt = now;
      this.lastVisibleNumber = shown;
      this.active = true;

      return true;
    }

    frame(now) {
      if (!this.panel || !this.ring || !this.number) return;

      if (!isPanelVisible(this.panel)) {
        if (this.active) this.reset();
        return;
      }

      if (!this.active && !this.begin(now)) return;

      const shown = integerText(this.number);

      /*
        The server/native runner owns the number and the actual timer.
        If it jumps unexpectedly (retry, state restart, etc.), resync.
      */
      if (
        Number.isFinite(shown) &&
        Number.isFinite(this.lastVisibleNumber) &&
        shown > this.lastVisibleNumber
      ) {
        this.reset();
        this.begin(now);
      }

      if (Number.isFinite(shown)) {
        this.lastVisibleNumber = shown;
      }

      const elapsedSeconds = Math.max(
        0,
        (now - this.startedAt) / 1000
      );

      const degreesPerSecond = 360 / this.totalSeconds;

      const angle = Math.max(
        0,
        Math.min(
          360,
          this.baseDegrees + elapsedSeconds * degreesPerSecond
        )
      );

      this.ring.style.setProperty(
        '--v19-angle',
        `${angle.toFixed(3)}deg`
      );
    }
  }

  function start() {
    if (!PATH_RE.test(location.pathname)) return;

    const prep = new RingAnimator(
      'preparePanel',
      'prepRing',
      'prepNumber',
      'preparation'
    );

    const recording = new RingAnimator(
      'recordPanel',
      'recordRing',
      'recordNumber',
      'recording'
    );

    function loop(now) {
      prep.frame(now);
      recording.frame(now);
      requestAnimationFrame(loop);
    }

    requestAnimationFrame(loop);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once:true });
  } else {
    start();
  }
})();
