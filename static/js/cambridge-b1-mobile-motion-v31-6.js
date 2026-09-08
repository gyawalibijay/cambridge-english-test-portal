(() => {
  'use strict';
  const page = document.querySelector('.b1x-page');
  if (!page || window.innerWidth > 700) return;

  const root = document.documentElement;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (reduced.matches) {
    root.classList.add('b1x-reduced-motion');
    document.querySelectorAll('.b1x-reveal').forEach(node => node.classList.add('is-visible'));
    return;
  }

  root.classList.remove('b1x-reduced-motion');
  const items = [...document.querySelectorAll('.b1x-reveal')];
  if (!items.length) return;

  items.forEach(item => {
    const delay = Math.min(420, Number(item.dataset.delay || 0));
    item.style.setProperty('--b1x-delay', `${delay}ms`);
    const rect = item.getBoundingClientRect();
    if (rect.top > window.innerHeight * 0.88) item.classList.remove('is-visible');
  });

  if (!('IntersectionObserver' in window)) {
    items.forEach(item => item.classList.add('is-visible'));
    return;
  }

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      requestAnimationFrame(() => entry.target.classList.add('is-visible'));
      observer.unobserve(entry.target);
    });
  }, { threshold: 0.10, rootMargin: '0px 0px -24px 0px' });

  items.forEach(item => {
    if (!item.classList.contains('is-visible')) observer.observe(item);
  });
})();
