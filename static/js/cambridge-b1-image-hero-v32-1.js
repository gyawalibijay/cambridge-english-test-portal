(() => {
  'use strict';

  const hero = document.querySelector('.b1x-image-hero-v32-1');
  if (!hero) return;

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    hero.classList.add('is-ready');
    return;
  }

  const ys = [15, 25, 20, 15, 15];
  const items = [...hero.querySelectorAll('.b1x-image-hero-v32-1__motion')];

  items.forEach((item, index) => {
    item.style.setProperty('--hero-delay', `${Number(item.dataset.heroDelay || 0)}ms`);
    item.style.setProperty('--hero-y', `${ys[index] || 15}px`);
  });

  hero.classList.add('b1x-image-hero-v32-1--motion');
  requestAnimationFrame(() => {
    requestAnimationFrame(() => hero.classList.add('is-ready'));
  });
})();
