(() => {
  if (window.__upskillStudentTopActions1412) return;
  window.__upskillStudentTopActions1412 = true;

  const menuItems = [];

  document.querySelectorAll('[data-portal-actions]').forEach(group => {
    const pairs = [
      ['[data-portal-notification-trigger]', '[data-portal-notification-popover]'],
      ['[data-portal-profile-trigger]', '[data-portal-profile-popover]'],
    ];

    pairs.forEach(([triggerSelector, popoverSelector]) => {
      const trigger = group.querySelector(triggerSelector);
      const popover = group.querySelector(popoverSelector);
      if (!trigger || !popover) return;

      menuItems.push({
        trigger,
        popover,
        originalParent: popover.parentNode,
        originalNext: popover.nextSibling,
        open: false,
      });
    });
  });

  const restorePopover = item => {
    const { popover, originalParent, originalNext } = item;
    if (!originalParent || !popover) return;

    if (originalNext && originalNext.parentNode === originalParent) {
      originalParent.insertBefore(popover, originalNext);
    } else {
      originalParent.appendChild(popover);
    }

    popover.classList.remove('portal-floating-popover');
    popover.removeAttribute('data-placement');
    popover.style.removeProperty('position');
    popover.style.removeProperty('top');
    popover.style.removeProperty('left');
    popover.style.removeProperty('right');
    popover.style.removeProperty('visibility');
    popover.style.removeProperty('max-height');
    popover.style.removeProperty('overflow-y');
  };

  const closeItem = item => {
    item.open = false;
    item.trigger.setAttribute('aria-expanded', 'false');
    item.popover.hidden = true;
    restorePopover(item);
  };

  const closeAll = except => {
    menuItems.forEach(item => {
      if (item !== except && item.open) closeItem(item);
    });
  };

  const place = item => {
    if (!item.open) return;

    const { trigger, popover } = item;
    const gap = 10;
    const edge = 12;
    const rect = trigger.getBoundingClientRect();

    // CRITICAL FIX:
    // Move the popup out of the animated/transformed dashboard header.
    // A transformed ancestor changes how position:fixed is calculated.
    // Appending to document.body makes viewport coordinates reliable.
    if (popover.parentNode !== document.body) document.body.appendChild(popover);

    popover.classList.add('portal-floating-popover');
    popover.hidden = false;
    popover.style.position = 'fixed';
    popover.style.right = 'auto';
    popover.style.visibility = 'hidden';
    popover.style.top = '0px';
    popover.style.left = '0px';
    popover.style.maxHeight = `${Math.max(160, window.innerHeight - edge * 2)}px`;
    popover.style.overflowY = 'auto';

    const width = Math.min(
      Math.max(popover.getBoundingClientRect().width || 258, 230),
      Math.max(230, window.innerWidth - edge * 2)
    );
    popover.style.width = `${width}px`;

    const measured = popover.getBoundingClientRect();
    const height = measured.height;
    const left = Math.min(
      Math.max(edge, rect.right - width),
      Math.max(edge, window.innerWidth - width - edge)
    );

    let top = rect.bottom + gap;
    let placement = 'bottom';

    if (top + height > window.innerHeight - edge) {
      const above = rect.top - gap - height;
      if (above >= edge) {
        top = above;
        placement = 'top';
      } else {
        top = Math.max(edge, Math.min(top, window.innerHeight - height - edge));
      }
    }

    popover.dataset.placement = placement;
    popover.style.left = `${Math.round(left)}px`;
    popover.style.top = `${Math.round(top)}px`;
    popover.style.visibility = 'visible';
  };

  const openItem = item => {
    closeAll(item);
    item.open = true;
    item.trigger.setAttribute('aria-expanded', 'true');
    place(item);
  };

  menuItems.forEach(item => {
    item.trigger.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      if (item.open) closeItem(item);
      else openItem(item);
    });

    item.popover.addEventListener('click', event => {
      event.stopPropagation();
    });
  });

  document.addEventListener('click', event => {
    if (event.target.closest('[data-portal-actions]')) return;
    closeAll();
  });

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') closeAll();
  });

  let raf = 0;
  const reposition = () => {
    if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = 0;
      menuItems.forEach(item => {
        if (item.open) place(item);
      });
    });
  };

  window.addEventListener('resize', reposition, { passive: true });
  window.addEventListener('scroll', reposition, { passive: true });
  document.addEventListener('scroll', reposition, { passive: true, capture: true });

  // Close before page navigation/cache restore so no portal node is stranded.
  window.addEventListener('pagehide', () => closeAll());
})();
