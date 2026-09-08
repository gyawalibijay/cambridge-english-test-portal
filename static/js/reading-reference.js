/* One lightweight timer. The server is authoritative for deadlines and marking. */
(() => {
  "use strict";
  const root = document.querySelector("[data-reading-runner]");
  if (!root) return;
  const clock = root.querySelector("[data-reading-time]");
  const form = root.querySelector("[data-answer-form]");
  const expiry = root.querySelector("[data-expire-form]");
  const input = root.querySelector("[data-word-input]");
  const remaining = Number(root.dataset.remainingMs);
  if (!Number.isFinite(remaining) || remaining < 0) return;
  const began = performance.now();
  const wallBegan = Date.now();
  let least = remaining;
  let submitting = false;
  let interval = null;
  const draftKey = `upskill-reading:${root.dataset.attempt}:${root.dataset.item}`;
  if (input) {
    try { if (!input.value) input.value = sessionStorage.getItem(draftKey) || ""; } catch (_) {}
    input.addEventListener("input", () => {
      try { sessionStorage.setItem(draftKey, input.value); } catch (_) {}
    });
  }
  function tick() {
    // Neither clock adjustments nor a throttled/background tab can add extra time.
    const elapsed = Math.max(performance.now() - began, Date.now() - wallBegan);
    least = Math.min(least, Math.max(0, remaining - elapsed));
    const seconds = Math.ceil(least / 1000);
    clock.textContent = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
    if (seconds === 0 && !submitting) {
      submitting = true;
      clearInterval(interval);
      expiry.requestSubmit();
    }
  }
  form.addEventListener("submit", event => {
    if (submitting) { event.preventDefault(); return; }
    if (input && !input.value.trim()) {
      event.preventDefault();
      input.focus();
      return;
    }
    submitting = true;
    form.setAttribute("aria-busy", "true");
    if (event.submitter) event.submitter.setAttribute("aria-pressed", "true");
    // Do not disable the clicked button: its name/value is the selected answer.
  });
  window.addEventListener("pageshow", event => {
    if (event.persisted) window.location.reload();
  });
  document.addEventListener("visibilitychange", tick);
  window.addEventListener("pagehide", () => clearInterval(interval), {once: true});
  interval = setInterval(tick, 250);
  tick();
})();
