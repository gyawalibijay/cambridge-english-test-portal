(() => {
  'use strict';

  const page = document.querySelector('.b1x-page');
  if (!page) return;

  const mqMobile = window.matchMedia('(max-width: 700px)');
  const mqReduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  let raf = 0;

  const clamp = (min, value, max) => Math.max(min, Math.min(max, value));

  const methodCards = [...document.querySelectorAll('[data-b1-method-stack] [data-system-step]')];
  const promiseCards = [...document.querySelectorAll('[data-b1-promise-card]')];
  const problemCards = [...document.querySelectorAll('[data-b1-stack-card]')];
  const problemAnswer = document.querySelector('.b1x-problem-stack > .b1x-problem-answer');

  const setCurrent = (cards, start, step) => {
    if (!cards.length) return;
    let current = cards[0];
    let best = Infinity;

    cards.forEach((card, index) => {
      const rect = card.getBoundingClientRect();
      const focus = start + index * step;
      const distance = Math.abs(rect.top - focus);
      if (distance < best) {
        best = distance;
        current = card;
      }
    });

    cards.forEach(card => card.classList.toggle('is-current', card === current));
  };

  const driveCards = (cards, yVar, scaleVar, triggerRatio = .78) => {
    cards.forEach(card => {
      const rect = card.getBoundingClientRect();
      const trigger = window.innerHeight * triggerRatio;
      const progress = clamp(0, (trigger - rect.top) / Math.max(190, window.innerHeight * .34), 1);
      const y = (1 - progress) * 26;
      const scale = .982 + progress * .018;
      card.style.setProperty(yVar, `${y.toFixed(2)}px`);
      card.style.setProperty(scaleVar, scale.toFixed(4));
    });
  };

  const driveProblem = () => {
    problemCards.forEach(card => {
      const rect = card.getBoundingClientRect();
      const progress = clamp(0, (window.innerHeight * .88 - rect.top) / Math.max(190, window.innerHeight * .46), 1);
      card.style.setProperty('--b1x-v318-problem-y', `${((1 - progress) * 30).toFixed(2)}px`);
      card.style.setProperty('--b1x-v318-problem-scale', (.975 + progress * .025).toFixed(4));
    });

    if (problemAnswer) {
      const rect = problemAnswer.getBoundingClientRect();
      const progress = clamp(0, (window.innerHeight * .88 - rect.top) / Math.max(190, window.innerHeight * .46), 1);
      problemAnswer.style.setProperty('--b1x-v318-answer-y', `${((1 - progress) * 30).toFixed(2)}px`);
      problemAnswer.style.setProperty('--b1x-v318-answer-scale', (.975 + progress * .025).toFixed(4));
    }
  };

  const update = () => {
    raf = 0;
    if (!mqMobile.matches || mqReduced.matches) return;

    /*
      These are the same scroll-driven progress ideas used by the desktop
      premium stack. The smaller sticky offsets only compensate for the
      compact mobile header; the visual behavior remains the same.
    */
    driveCards(methodCards, '--b1x-v318-method-y', '--b1x-v318-method-scale', .78);
    setCurrent(methodCards, 82, 14);

    driveCards(promiseCards, '--b1x-v318-promise-y', '--b1x-v318-promise-scale', .78);
    setCurrent(promiseCards, 82, 16);

    driveProblem();
    setCurrent(problemCards, 82, 14);
  };

  const schedule = () => {
    if (raf) return;
    raf = requestAnimationFrame(update);
  };

  const refresh = () => {
    if (!mqMobile.matches || mqReduced.matches) return;

    /* V31.6 adds a generic reveal transform with !important on mobile.
       The dedicated V31.8 CSS now owns transforms for these stack cards. */
    [...methodCards, ...promiseCards].forEach(card => {
      card.classList.add('is-visible');
      card.style.setProperty('opacity', '1', 'important');
      card.style.setProperty('filter', 'none', 'important');
    });
    schedule();
  };

  refresh();
  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', refresh, { passive: true });
  window.addEventListener('orientationchange', refresh, { passive: true });
  window.addEventListener('load', refresh, { once: true });

  if (mqMobile.addEventListener) mqMobile.addEventListener('change', refresh);
  if (mqReduced.addEventListener) mqReduced.addEventListener('change', refresh);
})();
