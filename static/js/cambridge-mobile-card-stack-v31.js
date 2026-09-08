/* Native mobile card stacking; no changes to the existing desktop controller. */
(() => {
  'use strict';

  const page = document.querySelector('.b1x-page');
  if (!page || page.hasAttribute('data-b1-mobile-stack-loaded')) return;
  page.setAttribute('data-b1-mobile-stack-loaded', '31');

  const mobile = window.matchMedia('(max-width: 700px)');
  const motion = window.matchMedia('(prefers-reduced-motion: no-preference)');
  const definitions = [
    ['.b1x-method', '.b1x-method-steps', 'article'],
    ['.b1x-promise', '.b1x-promise-grid', 'article'],
    ['.b1x-real-problem', '.b1x-problem-stack', '.b1x-problem-card, .b1x-problem-answer']
  ];
  const groups = definitions.flatMap(([sectionSelector, groupSelector, cardSelector]) => {
    const section = page.querySelector(sectionSelector);
    const container = section && section.querySelector(groupSelector);
    if (!container) return [];
    const cards = [...container.children].filter(card => card.matches(cardSelector));
    if (cards.length < 2) return [];
    const wrappers = [];
    for (let element = container.parentElement; element && element !== section; element = element.parentElement) {
      wrappers.push(element);
    }
    return [{ section, container, cards, wrappers }];
  });
  if (!groups.length) return;

  const header = page.querySelector('[data-b1-header], .b1x-header');
  const cta = page.querySelector('[data-b1-sticky-cta]');
  let frame = 0;
  let active = false;

  const clear = () => {
    groups.forEach(({ section, container, cards, wrappers }) => {
      section.removeAttribute('data-b1-mobile-stack-region');
      wrappers.forEach(wrapper => wrapper.removeAttribute('data-b1-mobile-stack-wrapper'));
      container.removeAttribute('data-b1-mobile-stack-group');
      container.style.removeProperty('--b1x-mobile-stack-tail');
      delete container.dataset.b1MobileOriginalTail;
      cards.forEach(card => {
        card.removeAttribute('data-b1-mobile-stack-card');
        card.style.removeProperty('--b1x-mobile-stack-top');
        card.style.removeProperty('--b1x-mobile-stack-order');
      });
    });
    active = false;
  };

  const update = () => {
    frame = 0;
    if (!mobile.matches || !motion.matches) {
      if (active) clear();
      return;
    }

    const headerStyle = header && getComputedStyle(header);
    const headerPinned = headerStyle && ['sticky', 'fixed'].includes(headerStyle.position);
    const start = headerPinned ? header.offsetHeight + Math.max(0, parseFloat(headerStyle.top) || 0) + 12 : 12;
    const ctaStyle = cta && getComputedStyle(cta);
    // Reserve space for the existing fixed CTA even before it becomes visible.
    const bottom = ctaStyle && ctaStyle.position === 'fixed' && ctaStyle.display !== 'none'
      ? cta.offsetHeight + Math.max(0, parseFloat(ctaStyle.bottom) || 0) + 16 : 24;
    const viewport = document.documentElement.clientHeight || window.innerHeight;

    // Measure before any writes, so resizing does not alternate layouts per card.
    const measurements = groups.map(group => ({
      ...group,
      height: Math.max(...group.cards.map(card => card.offsetHeight)),
      originalTail: active ? null : parseFloat(getComputedStyle(group.container).paddingBottom) || 0
    }));

    measurements.forEach(({ section, container, cards, wrappers, height, originalTail }) => {
      if (originalTail !== null) container.dataset.b1MobileOriginalTail = String(originalTail);
      const space = viewport - start - bottom - height - 16;
      const step = Math.max(0, Math.min(12, Math.floor(space / (cards.length - 1))));
      section.setAttribute('data-b1-mobile-stack-region', '');
      wrappers.forEach(wrapper => wrapper.setAttribute('data-b1-mobile-stack-wrapper', ''));
      container.setAttribute('data-b1-mobile-stack-group', space >= 0 ? 'sticky' : 'flow');
      const tail = Math.max(Number(container.dataset.b1MobileOriginalTail) || 0, Math.min(144, viewport * 0.18));
      container.style.setProperty('--b1x-mobile-stack-tail', `${Math.round(tail)}px`);
      cards.forEach((card, index) => {
        card.setAttribute('data-b1-mobile-stack-card', '');
        card.style.setProperty('--b1x-mobile-stack-top', `${start + index * step}px`);
        card.style.setProperty('--b1x-mobile-stack-order', String(index + 1));
      });
    });
    active = true;
  };

  const schedule = () => {
    if (!frame) frame = requestAnimationFrame(update);
  };
  const watchMedia = query => {
    if (query.addEventListener) query.addEventListener('change', schedule);
    else query.addListener(schedule);
  };
  watchMedia(mobile);
  watchMedia(motion);
  window.addEventListener('resize', schedule, { passive: true });
  window.addEventListener('pageshow', schedule);
  window.addEventListener('load', schedule, { once: true });
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(schedule);
  if ('ResizeObserver' in window) {
    const sizes = new ResizeObserver(schedule);
    if (header) sizes.observe(header);
    if (cta) sizes.observe(cta);
    groups.forEach(({ cards }) => cards.forEach(card => sizes.observe(card)));
  }
  update();
})();
