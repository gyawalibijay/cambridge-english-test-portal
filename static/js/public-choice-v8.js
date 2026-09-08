(() => {
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const finePointer = window.matchMedia('(hover:hover) and (pointer:fine)').matches;

  const menuToggle = document.querySelector('[data-public-menu-toggle]');
  const menu = document.querySelector('[data-public-menu]');

  if (menuToggle && menu) {
    menuToggle.addEventListener('click', () => {
      const open = menu.classList.toggle('is-open');
      menuToggle.setAttribute('aria-expanded', String(open));
      const icon = menuToggle.querySelector('[data-public-menu-icon]');
      if (icon) icon.textContent = open ? '×' : '☰';
    });

    menu.addEventListener('click', event => {
      if (!event.target.closest('a') || window.innerWidth > 900) return;
      menu.classList.remove('is-open');
      menuToggle.setAttribute('aria-expanded', 'false');
      const icon = menuToggle.querySelector('[data-public-menu-icon]');
      if (icon) icon.textContent = '☰';
    });
  }

  const revealNodes = [...document.querySelectorAll('.pub8-reveal')];
  revealNodes.forEach(node => {
    const delay = Math.max(0, Math.min(360, Number(node.dataset.delay || 0)));
    node.style.setProperty('--delay', `${delay}ms`);
  });

  if (reducedMotion || !('IntersectionObserver' in window)) {
    revealNodes.forEach(node => node.classList.add('is-visible'));
  } else {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -24px' });
    revealNodes.forEach(node => observer.observe(node));
  }

  if (!finePointer) return;

  const pointer = document.querySelector('[data-cursor-follower]');
  const pointerLabel = pointer ? pointer.querySelector('.pointer-label') : null;
  const pointerCore = pointer ? pointer.querySelector('.pointer-core') : null;
  let raf = null;
  let mouseX = -100;
  let mouseY = -100;

  const paintPointer = () => {
    raf = null;
    if (!pointer) return;
    pointer.style.left = `${mouseX}px`;
    pointer.style.top = `${mouseY}px`;
  };

  document.addEventListener('pointermove', event => {
    mouseX = event.clientX;
    mouseY = event.clientY;
    if (pointer) pointer.classList.add('is-visible');
    if (!raf) raf = requestAnimationFrame(paintPointer);
  }, { passive: true });

  document.addEventListener('pointerleave', () => {
    if (pointer) pointer.classList.remove('is-visible');
  });

  if (pointer) {
    document.querySelectorAll('a,button').forEach(link => {
      link.addEventListener('pointerenter', () => pointer.classList.add('is-link'));
      link.addEventListener('pointerleave', () => pointer.classList.remove('is-link'));
    });
  }

  const cards = [...document.querySelectorAll('[data-tilt-card]')];

  cards.forEach(card => {
    card.addEventListener('pointerenter', () => {
      if (!pointer) return;
      pointer.classList.add('is-card');
      pointer.classList.remove('is-ielts', 'is-uk-interview');

      const program = card.dataset.program || '';
      if (program === 'ielts') pointer.classList.add('is-ielts');
      if (program === 'uk-interview') pointer.classList.add('is-uk-interview');

      if (pointerLabel) pointerLabel.textContent = card.dataset.cursor || 'Explore';
      if (pointerCore) pointerCore.textContent =
        program === 'ielts' ? '◎' :
        program === 'uk-interview' ? '↗' : '✦';
    });

    card.addEventListener('pointermove', event => {
      if (reducedMotion) return;
      const rect = card.getBoundingClientRect();
      const x = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
      const y = Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height));
      const rotateY = (x - 0.5) * 8;
      const rotateX = (0.5 - y) * 6;

      card.style.setProperty('--x', `${x * 100}%`);
      card.style.setProperty('--y', `${y * 100}%`);
      card.style.transform =
        `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-5px) scale(1.012)`;
    });

    card.addEventListener('pointerleave', () => {
      card.style.transform = '';
      if (!pointer) return;
      pointer.classList.remove('is-card', 'is-ielts', 'is-uk-interview');
      if (pointerLabel) pointerLabel.textContent = 'Explore';
      if (pointerCore) pointerCore.textContent = '↗';
    });
  });
})();

