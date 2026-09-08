(() => {
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const toggle = document.querySelector('[data-public-menu-toggle]');
  const menu = document.querySelector('[data-public-menu]');

  if (toggle && menu) {
    toggle.addEventListener('click', () => {
      const open = menu.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      toggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
      const icon = toggle.querySelector('[data-public-menu-icon]');
      if (icon) icon.textContent = open ? '×' : '☰';
    });

    menu.addEventListener('click', event => {
      if (!event.target.closest('a') || window.innerWidth > 860) return;
      menu.classList.remove('is-open');
      toggle.setAttribute('aria-expanded', 'false');
      const icon = toggle.querySelector('[data-public-menu-icon]');
      if (icon) icon.textContent = '☰';
    });
  }

  const reveals = [...document.querySelectorAll('.up-reveal')];
  reveals.forEach(node => {
    const delay = Number(node.dataset.delay || 0);
    node.style.setProperty('--delay', `${Math.min(400, delay)}ms`);
  });

  if (reducedMotion || !('IntersectionObserver' in window)) {
    reveals.forEach(node => node.classList.add('is-visible'));
  } else {
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -30px' });
    reveals.forEach(node => observer.observe(node));
  }

  const cards = [...document.querySelectorAll('[data-tilt-card]')];
  const follower = document.querySelector('[data-cursor-follower]');
  const followerText = follower ? follower.querySelector('span') : null;
  const canTilt = !reducedMotion && window.matchMedia('(hover: hover) and (pointer: fine)').matches;

  if (!canTilt) return;

  cards.forEach(card => {
    card.addEventListener('pointermove', event => {
      const rect = card.getBoundingClientRect();
      const x = (event.clientX - rect.left) / rect.width;
      const y = (event.clientY - rect.top) / rect.height;
      const rotateY = (x - 0.5) * 8;
      const rotateX = (0.5 - y) * 7;
      card.style.setProperty('--x', `${x * 100}%`);
      card.style.setProperty('--y', `${y * 100}%`);
      card.style.transform = `rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-5px)`;

      if (follower) {
        follower.style.left = `${event.clientX}px`;
        follower.style.top = `${event.clientY}px`;
      }
    });

    card.addEventListener('pointerenter', () => {
      if (!follower) return;
      if (followerText) followerText.textContent = card.dataset.cursor || 'Explore';
      const accent = getComputedStyle(card).getPropertyValue('--card-accent').trim();
      follower.style.background = accent || '';
      follower.classList.add('is-visible');
    });

    card.addEventListener('pointerleave', () => {
      card.style.transform = '';
      if (follower) follower.classList.remove('is-visible');
    });
  });
})();
