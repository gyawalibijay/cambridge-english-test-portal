(() => {
  "use strict";

  const timer = document.getElementById("sectionTimer");
  if (!timer) return;

  const fmt = (seconds) => {
    const safe = Math.max(0, Math.ceil(Number(seconds) || 0));
    const minutes = Math.floor(safe / 60);
    const secs = safe % 60;
    return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  };

  const paint = (seconds) => {
    const safe = Math.max(0, Math.ceil(Number(seconds) || 0));
    timer.textContent = `◷ ${fmt(safe)}`;
    timer.classList.toggle("is-warning", safe > 0 && safe <= 60);
    timer.classList.toggle("is-expired", safe <= 0);
  };

  /*
   * Listening uses a SERVER-OWNED Part deadline.
   *
   * The server sends the remaining milliseconds at render time, and
   * performance.now() measures elapsed time locally. The browser's clock,
   * timezone, or a manually changed system time cannot extend the deadline.
   */
  if (timer.dataset.listeningTimer === "1") {
    const initialMs = Number(timer.dataset.remainingMs || 0);

    if (!Number.isFinite(initialMs) || initialMs < 0) {
      timer.textContent = "◷ --:--";
      return;
    }

    const began = performance.now();
    let expiredHandled = false;
    let timeoutId = null;

    const tick = () => {
      if (expiredHandled) return;

      const elapsedMs = Math.max(0, performance.now() - began);
      const remainingMs = Math.max(0, initialMs - elapsedMs);
      const remainingSeconds = Math.ceil(remainingMs / 1000);

      paint(remainingSeconds);

      if (remainingMs <= 0) {
        expiredHandled = true;

        if (timeoutId) {
          window.clearTimeout(timeoutId);
        }

        const form = document.querySelector(".exam-question-card form");
        if (form) {
          form.querySelectorAll("input,button,select,textarea").forEach((el) => {
            el.disabled = true;
          });
        }

        /*
         * The GET after reload is authoritative. Django records any
         * unanswered questions in the expired Listening Part as timed out,
         * then redirects to the next Part or completion page.
         */
        window.setTimeout(() => {
          window.location.reload();
        }, 650);

        return;
      }

      timeoutId = window.setTimeout(tick, 250);
    };

    tick();

    document.addEventListener("visibilitychange", () => {
      if (!document.hidden && !expiredHandled) {
        if (timeoutId) {
          window.clearTimeout(timeoutId);
        }
        tick();
      }
    });

    return;
  }

  /*
   * Preserve the pre-existing generic objective timer for non-Listening
   * objective questions.
   */
  const configured = Number(timer.dataset.seconds || 0);
  const started = Date.parse(timer.dataset.started || "");

  if (!configured) {
    timer.textContent = "Practice";
    return;
  }

  const tickGeneric = () => {
    const elapsed = Number.isFinite(started)
      ? (Date.now() - started) / 1000
      : 0;

    paint(configured - elapsed);
  };

  tickGeneric();
  window.setInterval(tickGeneric, 1000);
})();
