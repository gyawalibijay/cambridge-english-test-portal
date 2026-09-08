(() => {
  'use strict';

  const page = document.querySelector('.b1x-page');
  if (!page) return;

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const methodCards = [...document.querySelectorAll('[data-b1-method-stack] [data-system-step]')];
  const promiseCards = [...document.querySelectorAll('[data-b1-promise-card]')];
  const premiumCta = document.querySelector('[data-b1-premium-cta]');
  const clamp = (min, value, max) => Math.max(min, Math.min(max, value));
  let animationFrame = 0;

  page.classList.add('b1x-v22-ready');

  const updateStack = (cards, prefix, desktopStart, desktopStep) => {
    if (!cards.length) return;
    let current = cards[0];
    let closest = Number.POSITIVE_INFINITY;

    cards.forEach((card, index) => {
      const rect = card.getBoundingClientRect();
      const trigger = window.innerHeight * (window.innerWidth > 700 ? .78 : .86);
      const distance = Math.abs(rect.top - (window.innerWidth > 700 ? desktopStart + index * desktopStep : window.innerHeight * .46));
      const progress = reducedMotion.matches ? 1 : clamp(0, (trigger - rect.top) / Math.max(190, window.innerHeight * .34), 1);
      const scale = .982 + progress * .018;
      const y = (1 - progress) * (window.innerWidth > 700 ? 26 : 16);

      card.style.setProperty(`--b1x-${prefix}-scale`, scale.toFixed(4));
      card.style.setProperty(`--b1x-${prefix}-y`, `${y.toFixed(2)}px`);
      if (distance < closest) {
        closest = distance;
        current = card;
      }
    });

    cards.forEach(card => card.classList.toggle('is-current', card === current));
  };

  const update = () => {
    animationFrame = 0;
    updateStack(methodCards, 'method', 104, 16);
    updateStack(promiseCards, 'promise', 102, 17);
  };

  const schedule = () => {
    if (animationFrame) return;
    animationFrame = requestAnimationFrame(update);
  };

  update();
  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', schedule, { passive: true });
  window.addEventListener('load', schedule, { once: true });

  if (premiumCta && !reducedMotion.matches && window.matchMedia('(pointer:fine)').matches) {
    premiumCta.addEventListener('pointermove', event => {
      const rect = premiumCta.getBoundingClientRect();
      const x = ((event.clientX - rect.left) / rect.width - .5) * 10;
      const y = ((event.clientY - rect.top) / rect.height - .5) * 8;
      premiumCta.style.setProperty('--b1x-cta-x', `${x.toFixed(2)}px`);
      premiumCta.style.setProperty('--b1x-cta-y', `${y.toFixed(2)}px`);
    });
    premiumCta.addEventListener('pointerleave', () => {
      premiumCta.style.setProperty('--b1x-cta-x', '0px');
      premiumCta.style.setProperty('--b1x-cta-y', '0px');
    });
  }
})();
