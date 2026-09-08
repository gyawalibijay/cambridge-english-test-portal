(() => {
  if (window.__upskillPublicLaunch149) return;
  window.__upskillPublicLaunch149 = true;

  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const fine = window.matchMedia('(pointer: fine)').matches;

  const menu = document.querySelector('[data-public-menu]');
  const menuToggle = document.querySelector('[data-public-menu-toggle]');
  if (menu && menuToggle) {
    menuToggle.addEventListener('click', () => {
      const open = !menu.classList.contains('is-open');
      menu.classList.toggle('is-open', open);
      menuToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      const icon = menuToggle.querySelector('[data-public-menu-icon]');
      if (icon) icon.textContent = open ? '×' : '☰';
    });
    menu.addEventListener('click', e => {
      if (!e.target.closest('a')) return;
      menu.classList.remove('is-open');
      menuToggle.setAttribute('aria-expanded', 'false');
      const icon = menuToggle.querySelector('[data-public-menu-icon]');
      if (icon) icon.textContent = '☰';
    });
  }

  const reveal = [...document.querySelectorAll('[data-reveal]')];
  reveal.forEach((node, index) => {
    node.style.transitionDelay = `${Math.min(index * 70, 280)}ms`;
  });
  if (reduced || !('IntersectionObserver' in window)) {
    reveal.forEach(node => node.classList.add('is-visible'));
  } else {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      });
    }, { threshold: .08, rootMargin: '0px 0px -18px' });
    reveal.forEach(node => observer.observe(node));
  }

  const tiltCards = [...document.querySelectorAll('[data-tilt]')];
  if (!reduced && fine) {
    tiltCards.forEach(card => {
      card.addEventListener('pointermove', event => {
        const rect = card.getBoundingClientRect();
        const x = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
        const y = Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height));
        card.style.setProperty('--ry', `${(x - .5) * 8}deg`);
        card.style.setProperty('--rx', `${(.5 - y) * 6}deg`);
        card.style.setProperty('--mx', `${x * 100}%`);
        card.style.setProperty('--my', `${y * 100}%`);
      });
      card.addEventListener('pointerleave', () => {
        card.style.setProperty('--ry', '0deg');
        card.style.setProperty('--rx', '0deg');
        card.style.setProperty('--mx', '50%');
        card.style.setProperty('--my', '50%');
      });
    });
  }

  if (!fine) return;

  const pointer = document.querySelector('[data-launch-pointer]');
  if (!pointer) return;
  const label = pointer.querySelector('.launch-pointer-label');
  let raf = 0, x = -100, y = -100;

  const paint = () => {
    raf = 0;
    pointer.style.left = `${x}px`;
    pointer.style.top = `${y}px`;
  };

  document.addEventListener('pointermove', event => {
    x = event.clientX; y = event.clientY;
    pointer.classList.add('is-visible');
    if (!raf) raf = requestAnimationFrame(paint);
  }, { passive: true });

  document.addEventListener('pointerleave', () => pointer.classList.remove('is-visible'));

  document.querySelectorAll('[data-pointer-label],a,button,[data-tilt]').forEach(node => {
    node.addEventListener('pointerenter', () => {
      const text = node.dataset.pointerLabel || (node.matches('a,button') ? 'Open' : 'Explore');
      if (label) label.textContent = text;
      pointer.classList.add('is-active');
      pointer.classList.toggle('is-soon', /soon/i.test(text));
    });
    node.addEventListener('pointerleave', () => {
      if (label) label.textContent = 'Explore';
      pointer.classList.remove('is-active', 'is-soon');
    });
  });
})();
