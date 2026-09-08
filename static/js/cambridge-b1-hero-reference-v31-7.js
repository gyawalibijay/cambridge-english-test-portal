(() => {
  'use strict';

  const hero = document.querySelector('.b1x-hero-v31-7');
  if (!hero) return;

  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const items = [
    [hero.querySelector('.b1x-proof'), 100, 15],
    [hero.querySelector('h1'), 200, 25],
    [hero.querySelector('.b1x-hero-lead'), 350, 20],
    [hero.querySelector('.b1x-hero-actions'), 500, 15],
    [hero.querySelector('.b1x-hero-features'), 650, 15],
  ].filter(([node]) => node);

  const finish = (node) => {
    node.style.setProperty('opacity', '1', 'important');
    node.style.setProperty('filter', 'none', 'important');
    node.style.setProperty('transform', 'translate3d(0,0,0)', 'important');
  };

  if (reduced) {
    items.forEach(([node]) => finish(node));
    return;
  }

  items.forEach(([node, delay, y]) => {
    node.style.setProperty('opacity', '0', 'important');
    node.style.setProperty('filter', 'blur(3px)', 'important');
    node.style.setProperty('transform', `translate3d(0,${y}px,0)`, 'important');
    node.style.setProperty(
      'transition',
      `opacity .70s cubic-bezier(.22,1,.36,1) ${delay}ms, filter .70s ease ${delay}ms, transform .76s cubic-bezier(.22,1,.36,1) ${delay}ms`,
      'important'
    );
  });

  requestAnimationFrame(() => {
    requestAnimationFrame(() => items.forEach(([node]) => finish(node)));
  });
})();
