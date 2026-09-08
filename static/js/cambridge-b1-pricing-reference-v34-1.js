(() => {
  "use strict";

  document.documentElement.classList.add("b1x-v341-js");

  const pad = value => String(Math.max(0, value)).padStart(2, "0");

  function countdown(timer) {
    const end = Date.parse(timer.dataset.offerEnd || "");
    const d = timer.querySelector("[data-b1-days]");
    const h = timer.querySelector("[data-b1-hours]");
    const m = timer.querySelector("[data-b1-minutes]");
    const s = timer.querySelector("[data-b1-seconds]");
    const copy = timer.querySelector("[data-offer-copy]");

    if (!Number.isFinite(end)) {
      timer.classList.add("is-expired");
      if (copy) copy.textContent = "Offer timing is unavailable.";
      return;
    }

    let interval = null;

    const draw = () => {
      let remaining = end - Date.now();

      if (remaining <= 0) {
        remaining = 0;
        timer.classList.add("is-expired");
        if (copy) copy.textContent = "This offer has ended.";
        if (interval) clearInterval(interval);
      }

      const total = Math.floor(remaining / 1000);
      if (d) d.textContent = pad(Math.floor(total / 86400));
      if (h) h.textContent = pad(Math.floor((total % 86400) / 3600));
      if (m) m.textContent = pad(Math.floor((total % 3600) / 60));
      if (s) s.textContent = pad(total % 60);
    };

    draw();
    interval = setInterval(draw, 1000);
  }

  function reveal(root) {
    const items = [...root.querySelectorAll("[data-v341-reveal]")];
    if (!items.length) return;

    if (
      matchMedia("(prefers-reduced-motion: reduce)").matches ||
      !("IntersectionObserver" in window)
    ) {
      items.forEach(item => item.classList.add("is-v341-visible"));
      return;
    }

    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-v341-visible");
        observer.unobserve(entry.target);
      });
    }, {threshold:.11, rootMargin:"0px 0px -5% 0px"});

    items.forEach((item, index) => {
      item.style.transitionDelay = `${Math.min(index, 5) * 65}ms`;
      observer.observe(item);
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const root = document.querySelector(".b1x-pricing-ref-v34-1");
    if (!root) return;

    root.querySelectorAll("[data-b1-offer-timer]").forEach(countdown);
    reveal(root);
  });
})();
