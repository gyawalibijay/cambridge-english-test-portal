(() => {
  'use strict';

  const page = document.querySelector('.b1x-page');
  if (!page) return;

  document.documentElement.classList.add('b1x-js');

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const header = document.querySelector('[data-b1-header]');
  const menu = document.querySelector('[data-b1-menu]');
  const menuToggle = document.querySelector('[data-b1-menu-toggle]');

  const setHeaderState = () => {
    if (header) header.classList.toggle('is-scrolled', window.scrollY > 18);
  };
  setHeaderState();
  window.addEventListener('scroll', setHeaderState, { passive: true });

  const closeMenu = () => {
    if (!menu || !menuToggle) return;
    menu.classList.remove('is-open');
    menuToggle.setAttribute('aria-expanded', 'false');
    menuToggle.setAttribute('aria-label', 'Open navigation');
    document.body.style.overflow = '';
  };

  if (menu && menuToggle) {
    menuToggle.addEventListener('click', () => {
      const open = !menu.classList.contains('is-open');
      menu.classList.toggle('is-open', open);
      menuToggle.setAttribute('aria-expanded', String(open));
      menuToggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
      document.body.style.overflow = open ? 'hidden' : '';
    });

    menu.addEventListener('click', event => {
      if (event.target.closest('a')) closeMenu();
    });

    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') closeMenu();
    });

    window.addEventListener('resize', () => {
      if (window.innerWidth > 820) closeMenu();
    });
  }

  const revealItems = [...document.querySelectorAll('.b1x-reveal')];
  revealItems.forEach(item => {
    const delay = Math.min(360, Number(item.dataset.delay || 0));
    item.style.setProperty('--b1x-delay', `${delay}ms`);
  });

  if (reducedMotion || !('IntersectionObserver' in window)) {
    revealItems.forEach(item => item.classList.add('is-visible'));
  } else {
    const revealObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        revealObserver.unobserve(entry.target);
      });
    }, { threshold: 0.09, rootMargin: '0px 0px -35px' });
    revealItems.forEach(item => revealObserver.observe(item));
  }

  const systemSteps = [...document.querySelectorAll('[data-system-step]')];
  if (systemSteps.length && 'IntersectionObserver' in window) {
    const systemObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        systemSteps.forEach(step => step.classList.remove('is-active'));
        entry.target.classList.add('is-active');
      });
    }, { threshold: 0.62, rootMargin: '-12% 0px -20%' });
    systemSteps.forEach(step => systemObserver.observe(step));
  } else if (systemSteps[0]) {
    systemSteps[0].classList.add('is-active');
  }

  const accordions = [...document.querySelectorAll('[data-b1-accordion] button[aria-controls]')];

  const finishOpen = panel => {
    panel.style.height = 'auto';
    panel.style.opacity = '1';
  };

  const openPanel = (button, panel) => {
    button.setAttribute('aria-expanded', 'true');
    panel.hidden = false;
    if (reducedMotion) {
      finishOpen(panel);
      return;
    }
    panel.style.height = '0px';
    panel.style.opacity = '0';
    panel.style.transition = 'height 300ms cubic-bezier(.2,.7,.2,1), opacity 220ms ease';
    requestAnimationFrame(() => {
      panel.style.height = `${panel.scrollHeight}px`;
      panel.style.opacity = '1';
    });
    panel.addEventListener('transitionend', event => {
      if (event.propertyName === 'height' && button.getAttribute('aria-expanded') === 'true') finishOpen(panel);
    }, { once: true });
  };

  const closePanel = (button, panel) => {
    button.setAttribute('aria-expanded', 'false');
    if (reducedMotion) {
      panel.hidden = true;
      panel.style.height = '';
      panel.style.opacity = '';
      return;
    }
    panel.style.height = `${panel.scrollHeight}px`;
    panel.style.opacity = '1';
    panel.style.transition = 'height 280ms cubic-bezier(.2,.7,.2,1), opacity 180ms ease';
    requestAnimationFrame(() => {
      panel.style.height = '0px';
      panel.style.opacity = '0';
    });
    panel.addEventListener('transitionend', event => {
      if (event.propertyName !== 'height' || button.getAttribute('aria-expanded') !== 'false') return;
      panel.hidden = true;
      panel.style.height = '';
      panel.style.opacity = '';
    }, { once: true });
  };

  accordions.forEach(button => {
    const panel = document.getElementById(button.getAttribute('aria-controls'));
    if (!panel) return;
    button.addEventListener('click', () => {
      const shouldOpen = button.getAttribute('aria-expanded') !== 'true';
      accordions.forEach(otherButton => {
        if (otherButton === button || otherButton.getAttribute('aria-expanded') !== 'true') return;
        const otherPanel = document.getElementById(otherButton.getAttribute('aria-controls'));
        if (otherPanel) closePanel(otherButton, otherPanel);
      });
      if (shouldOpen) openPanel(button, panel);
      else closePanel(button, panel);
    });
  });

  if (!reducedMotion && window.matchMedia('(min-width: 900px)').matches) {
    const parallax = document.querySelector('[data-b1-parallax]');
    let ticking = false;
    const updateParallax = () => {
      if (!parallax) return;
      const rect = parallax.getBoundingClientRect();
      const offset = Math.max(-15, Math.min(15, (window.innerHeight / 2 - rect.top - rect.height / 2) * 0.035));
      parallax.style.setProperty('--b1x-parallax', `${offset}px`);
      ticking = false;
    };
    window.addEventListener('scroll', () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(updateParallax);
    }, { passive: true });
    updateParallax();

    document.querySelectorAll('[data-b1-magnetic]').forEach(button => {
      button.addEventListener('pointermove', event => {
        const rect = button.getBoundingClientRect();
        const x = (event.clientX - rect.left - rect.width / 2) * 0.08;
        const y = (event.clientY - rect.top - rect.height / 2) * 0.1;
        button.style.transform = `translate(${x}px, ${y}px)`;
      });
      button.addEventListener('pointerleave', () => {
        button.style.transform = '';
      });
    });
  }
})();
