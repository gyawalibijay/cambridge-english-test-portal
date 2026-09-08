(() => {
  "use strict";
  const timer = document.querySelector('[data-full-mock-timer="1"]');
  if (!timer) return;
  const url = timer.dataset.fullMockTimerUrl || "";
  if (!url) return;

  let initialMs = null;
  let beganAt = 0;
  let stopped = false;
  let tickId = null;

  const format = ms => {
    const seconds = Math.max(0, Math.ceil(ms / 1000));
    return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  };

  const paint = ms => {
    const text = format(ms);
    if (timer.id === "sectionTimer") timer.textContent = `◷ ${text}`;
    else {
      const span = timer.querySelector("span");
      if (span) span.textContent = text;
      else timer.textContent = text;
    }
    if (timer.id === "sessionTimer") {
      document.querySelectorAll("#cambridgeV18Topbar .v18-session-text").forEach(el => { el.textContent = text; });
    }
    timer.classList.toggle("is-warning", ms > 0 && ms <= 60_000);
    timer.classList.toggle("is-expired", ms <= 0);
  };

  const disablePage = () => {
    document.querySelectorAll("form input, form textarea, form select, form button").forEach(el => { el.disabled = true; });
    document.querySelectorAll("audio").forEach(audio => { try { audio.pause(); } catch (_) {} });
  };

  const authoritativeRefresh = async () => {
    try {
      const response = await fetch(url, { credentials: "same-origin", cache: "no-store", headers: { "X-Requested-With": "XMLHttpRequest" } });
      const data = await response.json();
      if (data.next_url) {
        window.location.replace(data.next_url);
        return;
      }
      if (data.active && Number.isFinite(Number(data.remaining_ms))) {
        initialMs = Math.max(0, Number(data.remaining_ms));
        beganAt = performance.now();
        stopped = false;
        tick();
      }
    } catch (_) {
      window.location.reload();
    }
  };

  const expire = () => {
    if (stopped) return;
    stopped = true;
    if (tickId) clearTimeout(tickId);
    paint(0);
    disablePage();
    window.setTimeout(authoritativeRefresh, 450);
  };

  const tick = () => {
    if (stopped || initialMs === null) return;
    const remaining = Math.max(0, initialMs - Math.max(0, performance.now() - beganAt));
    paint(remaining);
    if (remaining <= 0) return expire();
    tickId = window.setTimeout(tick, 250);
  };

  authoritativeRefresh();
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && !stopped) authoritativeRefresh();
  });
})();
