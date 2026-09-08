(() => {
  'use strict';

  const page = document.querySelector('.b1x-page');
  if (!page) return;

  const root = document.documentElement;
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const coarsePointer = window.matchMedia('(pointer: coarse)');
  const header = document.querySelector('[data-b1-header]');
  const progress = document.querySelector('[data-b1-progress]');
  const menu = document.querySelector('[data-b1-menu]');
  const menuToggle = document.querySelector('[data-b1-menu-toggle]');
  const hero = document.querySelector('[data-b1-parallax]');
  const stickyCta = document.querySelector('[data-b1-sticky-cta]');
  const finalSection = document.querySelector('.b1x-final');
  const driftItems = [...document.querySelectorAll('[data-b1-drift]')];
  const navigationLinks = [...document.querySelectorAll('.b1x-nav a[href^="#"]')];
  let frameRequested = false;

  root.classList.add('b1x-js');
  requestAnimationFrame(() => page.classList.add('is-ready'));

  const closeMenu = () => {
    if (!menu || !menuToggle) return;
    menu.classList.remove('is-open');
    menuToggle.setAttribute('aria-expanded', 'false');
    menuToggle.setAttribute('aria-label', 'Open navigation');
    page.style.overflow = '';
  };

  if (menu && menuToggle) {
    menuToggle.addEventListener('click', () => {
      const open = !menu.classList.contains('is-open');
      menu.classList.toggle('is-open', open);
      menuToggle.setAttribute('aria-expanded', String(open));
      menuToggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
      page.style.overflow = open ? 'hidden' : '';
    });
    menu.addEventListener('click', event => {
      if (event.target.closest('a')) closeMenu();
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') closeMenu();
    });
    window.addEventListener('resize', () => {
      if (window.innerWidth > 960) closeMenu();
    }, { passive: true });
  }

  const revealItems = [...document.querySelectorAll('.b1x-reveal')];
  revealItems.forEach(item => {
    const delay = Math.min(420, Number(item.dataset.delay || 0));
    item.style.setProperty('--b1x-delay', delay + 'ms');
  });

  if (reducedMotion.matches || !('IntersectionObserver' in window)) {
    revealItems.forEach(item => item.classList.add('is-visible'));
  } else {
    const revealObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-visible');
        revealObserver.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -55px' });
    revealItems.forEach(item => revealObserver.observe(item));
  }

  const systemSteps = [...document.querySelectorAll('[data-system-step]')];
  if (systemSteps.length && 'IntersectionObserver' in window && !reducedMotion.matches) {
    const systemObserver = new IntersectionObserver(entries => {
      const visible = entries
        .filter(entry => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      systemSteps.forEach(step => step.classList.toggle('is-active', step === visible.target));
    }, { threshold: [0.4, 0.62, 0.82], rootMargin: '-18% 0px -26%' });
    systemSteps.forEach(step => systemObserver.observe(step));
  }

  const counters = [...document.querySelectorAll('[data-b1-count]')];
  const finishCounter = element => {
    if (element.firstChild) element.firstChild.nodeValue = element.dataset.b1Count;
  };
  if (counters.length && !reducedMotion.matches && 'IntersectionObserver' in window) {
    const counterObserver = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        const element = entry.target;
        const target = Number(element.dataset.b1Count || 0);
        const started = performance.now();
        const duration = 1250;
        const tick = now => {
          const elapsed = Math.min(1, (now - started) / duration);
          const eased = 1 - Math.pow(1 - elapsed, 3);
          if (element.firstChild) element.firstChild.nodeValue = String(Math.round(target * eased));
          if (elapsed < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
        counterObserver.unobserve(element);
      });
    }, { threshold: 0.7 });
    counters.forEach(element => {
      if (element.firstChild) element.firstChild.nodeValue = '0';
      counterObserver.observe(element);
    });
  } else {
    counters.forEach(finishCounter);
  }

  const accordionButtons = [...document.querySelectorAll('[data-b1-accordion] button[aria-controls]')];
  const openPanel = (button, panel) => {
    button.setAttribute('aria-expanded', 'true');
    panel.hidden = false;
    if (reducedMotion.matches) {
      panel.style.height = 'auto';
      panel.style.opacity = '1';
      return;
    }
    panel.style.height = '0px';
    panel.style.opacity = '0';
    panel.style.transition = 'height 340ms cubic-bezier(.2,.7,.2,1), opacity 240ms ease';
    requestAnimationFrame(() => {
      panel.style.height = panel.scrollHeight + 'px';
      panel.style.opacity = '1';
    });
    panel.addEventListener('transitionend', event => {
      if (event.propertyName === 'height' && button.getAttribute('aria-expanded') === 'true') {
        panel.style.height = 'auto';
      }
    }, { once: true });
  };
  const closePanel = (button, panel) => {
    button.setAttribute('aria-expanded', 'false');
    if (reducedMotion.matches) {
      panel.hidden = true;
      panel.style.height = '';
      panel.style.opacity = '';
      return;
    }
    panel.style.height = panel.scrollHeight + 'px';
    panel.style.opacity = '1';
    panel.style.transition = 'height 300ms cubic-bezier(.2,.7,.2,1), opacity 190ms ease';
    requestAnimationFrame(() => {
      panel.style.height = '0px';
      panel.style.opacity = '0';
    });
    panel.addEventListener('transitionend', event => {
      if (event.propertyName !== 'height') return;
      panel.hidden = true;
      panel.style.height = '';
      panel.style.opacity = '';
    }, { once: true });
  };
  accordionButtons.forEach(button => {
    button.addEventListener('click', () => {
      const panel = document.getElementById(button.getAttribute('aria-controls'));
      if (!panel) return;
      const shouldOpen = button.getAttribute('aria-expanded') !== 'true';
      accordionButtons.forEach(other => {
        if (other === button || other.getAttribute('aria-expanded') !== 'true') return;
        const otherPanel = document.getElementById(other.getAttribute('aria-controls'));
        if (otherPanel) closePanel(other, otherPanel);
      });
      if (shouldOpen) openPanel(button, panel);
      else closePanel(button, panel);
    });
  });

  const updateScrollEffects = () => {
    frameRequested = false;
    const scrollTop = window.scrollY;
    const scrollRange = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    if (header) header.classList.toggle('is-scrolled', scrollTop > 14);
    if (progress) progress.style.transform = 'scaleX(' + Math.min(1, scrollTop / scrollRange) + ')';

    if (stickyCta && hero) {
      const revealAfter = Math.max(360, hero.offsetTop + hero.offsetHeight * 0.72);
      const hideBefore = finalSection
        ? finalSection.offsetTop - window.innerHeight * 0.58
        : document.documentElement.scrollHeight;
      const showSticky = scrollTop > revealAfter && scrollTop < hideBefore;
      stickyCta.classList.toggle('is-visible', showSticky);
      stickyCta.setAttribute('aria-hidden', String(!showSticky));
      const stickyLink = stickyCta.querySelector('a');
      if (stickyLink) stickyLink.tabIndex = showSticky ? 0 : -1;
      page.classList.toggle('has-sticky-cta', showSticky);
    }

    if (!reducedMotion.matches && window.innerWidth > 700) {
      if (hero) hero.style.setProperty('--b1x-parallax', Math.min(42, scrollTop * 0.055) + 'px');
      driftItems.forEach(item => {
        const rect = item.getBoundingClientRect();
        if (rect.bottom < 0 || rect.top > window.innerHeight) return;
        const centerOffset = (rect.top + rect.height / 2 - window.innerHeight / 2) / window.innerHeight;
        item.style.setProperty('--b1x-drift', Math.max(-18, Math.min(18, centerOffset * -20)) + 'px');
      });
    }

    let activeId = '';
    navigationLinks.forEach(link => {
      const target = document.querySelector(link.getAttribute('href'));
      if (target && target.getBoundingClientRect().top <= 150) activeId = link.getAttribute('href');
    });
    navigationLinks.forEach(link => link.classList.toggle('is-active', link.getAttribute('href') === activeId));
  };

  const scheduleScrollEffects = () => {
    if (frameRequested) return;
    frameRequested = true;
    requestAnimationFrame(updateScrollEffects);
  };
  updateScrollEffects();
  window.addEventListener('scroll', scheduleScrollEffects, { passive: true });
  window.addEventListener('resize', scheduleScrollEffects, { passive: true });

  if (!reducedMotion.matches && !coarsePointer.matches) {
    document.querySelectorAll('[data-b1-magnetic]').forEach(button => {
      button.addEventListener('pointermove', event => {
        const rect = button.getBoundingClientRect();
        const x = (event.clientX - rect.left - rect.width / 2) * 0.075;
        const y = (event.clientY - rect.top - rect.height / 2) * 0.09;
        button.style.transform = 'translate(' + x + 'px, ' + y + 'px)';
      });
      button.addEventListener('pointerleave', () => {
        button.style.transform = '';
      });
    });
  }

  if (typeof reducedMotion.addEventListener === 'function') {
    reducedMotion.addEventListener('change', () => window.location.reload());
  }
})();
