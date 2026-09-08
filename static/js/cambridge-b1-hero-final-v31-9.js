(() => {
  'use strict';
  const hero = document.querySelector('.b1x-hero-final-v31-9');
  if (!hero) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    hero.classList.add('is-ready');
    return;
  }
  const items = [...hero.querySelectorAll('.b1x-hero-final-motion-item')];
  const yMap = [15, 25, 20, 15, 15];
  items.forEach((item, index) => {
    item.style.setProperty('--b1x-hero-delay', `${Number(item.dataset.heroDelay || 0)}ms`);
    item.style.setProperty('--b1x-hero-start-y', `${yMap[index] || 15}px`);
  });
  hero.classList.add('b1x-hero-final-motion');
  requestAnimationFrame(() => requestAnimationFrame(() => hero.classList.add('is-ready')));
})();
