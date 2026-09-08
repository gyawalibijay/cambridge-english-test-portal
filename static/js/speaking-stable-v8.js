(function () {
  function onReady(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener(
        'DOMContentLoaded',
        fn,
        { once: true }
      );
    } else {
      fn();
    }
  }

  function visible(el) {
    if (!el) return false;
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();

    return (
      style.display !== 'none' &&
      style.visibility !== 'hidden' &&
      rect.width > 0 &&
      rect.height > 0
    );
  }

  function text(el) {
    return (
      (el && (el.value || el.textContent)) ||
      ''
    )
      .replace(/\s+/g, ' ')
      .trim();
  }

  function findRunner() {
    return (
      document.getElementById('runner') ||
      document.querySelector(
        '[data-attempt-id][data-part-order]'
      ) ||
      document.querySelector(
        '[data-attempt-id]'
      )
    );
  }

  function inferPartOrder(runner) {
    const fromData = Number(
      runner &&
      (
        runner.dataset.partOrder ||
        runner.dataset.part
      )
    );

    if (fromData >= 1 && fromData <= 5) {
      return fromData;
    }

    const bodyText = (
      document.body.innerText || ''
    ).toLowerCase();

    if (
      bodyText.includes('speaking part 5') ||
      bodyText.includes('leave a message') ||
      bodyText.includes('40 seconds')
    ) {
      return 5;
    }

    if (
      bodyText.includes('speaking part 4')
    ) {
      return 4;
    }

    if (
      bodyText.includes('speaking part 3') ||
      bodyText.includes(
        'read the sentence out loud'
      )
    ) {
      return 3;
    }

    if (
      bodyText.includes('speaking part 2') ||
      bodyText.includes(
        '20 seconds to answer'
      )
    ) {
      return 2;
    }

    return 1;
  }

  function attemptId(runner) {
    const fromData = (
      runner &&
      (
        runner.dataset.attemptId ||
        runner.dataset.attempt
      )
    );

    if (fromData) return String(fromData);

    const match = location.pathname.match(
      /\/attempt\/(\d+)\//
    );

    return match ? match[1] : 'attempt';
  }

  function findClockElement() {
    // Prefer IDs/classes already used by the runner.
    const preferred = [
      '#sessionTimer',
      '.reference-session-time',
      '.session-timer',
      '.time-remaining',
      '.runner-time',
      '[data-session-timer]'
    ];

    for (const selector of preferred) {
      const el = document.querySelector(selector);
      if (el && visible(el)) return el;
    }

    // Fallback to a small visible MM:SS element near the top.
    const candidates = Array.from(
      document.querySelectorAll(
        'span,div,strong,time'
      )
    ).filter(el => {
      if (!visible(el)) return false;
      return /^\d{2}:\d{2}$/.test(
        text(el)
      );
    });

    candidates.sort(
      (a, b) =>
        a.getBoundingClientRect().top -
        b.getBoundingClientRect().top
    );

    return candidates[0] || null;
  }

  function makeClockDisplay(el) {
    if (!el) return null;

    el.classList.add(
      'speaking-v8-clock'
    );

    // If the element is just the digits, keep it simple.
    // If it is a wrapper, find the actual MM:SS child.
    let digits = el;

    if (
      !/^\d{2}:\d{2}$/.test(
        text(el)
      )
    ) {
      const child = Array.from(
        el.querySelectorAll(
          'span,strong,time,div'
        )
      ).find(node =>
        /^\d{2}:\d{2}$/.test(
          text(node)
        )
      );

      if (child) digits = child;
    }

    if (
      !el.querySelector(
        '.speaking-v8-clock-icon'
      )
    ) {
      const icon = document.createElement(
        'span'
      );

      icon.className =
        'speaking-v8-clock-icon';

      icon.innerHTML = `
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="13" r="8"></circle>
          <path d="M12 9v4l3 2"></path>
        </svg>
      `;

      el.insertBefore(
        icon,
        el.firstChild
      );
    }

    return digits;
  }

  function pad(number) {
    return String(number).padStart(
      2,
      '0'
    );
  }

  function format(seconds) {
    const safe = Math.max(
      0,
      Math.floor(seconds)
    );

    return (
      pad(Math.floor(safe / 60))
      + ':'
      + pad(safe % 60)
    );
  }

  function startClock(
    digits,
    runner,
    part
  ) {
    if (!digits) return;

    const duration =
      part === 5 ? 110 : 300;

    const key =
      'upskill-v8-speaking-clock:'
      + attemptId(runner)
      + ':part-'
      + part;

    const now = Date.now();
    let deadline = Number(
      sessionStorage.getItem(key)
    );

    /*
      If an old broken patch stored 00:00 or an expired value,
      give the currently active part a fresh reference clock.
      Once started, it remains persistent across 1/4 -> 4/4
      within the same browser session.
    */
    if (
      !Number.isFinite(deadline) ||
      deadline <= now ||
      deadline >
        now + duration * 1000 + 15000
    ) {
      deadline =
        now + duration * 1000;

      sessionStorage.setItem(
        key,
        String(deadline)
      );
    }

    function render() {
      const ms = Math.max(
        0,
        deadline - Date.now()
      );

      const seconds =
        ms > 0
          ? Math.ceil(ms / 1000)
          : 0;

      digits.textContent =
        format(seconds);

      if (ms > 0) {
        setTimeout(
          render,
          150
        );
      }
    }

    // Do this immediately so 00:00 never flashes.
    digits.textContent = format(
      Math.max(
        0,
        Math.ceil(
          (deadline - Date.now()) /
          1000
        )
      )
    );

    render();
  }

  function fixButtons() {
    document
      .querySelectorAll(
        'button,input[type="button"],input[type="submit"],a'
      )
      .forEach(el => {
        if (!visible(el)) return;

        const label =
          text(el).toLowerCase();

        if (
          label === 'speak' ||
          label === 'done'
        ) {
          el.classList.add(
            'speaking-v8-action'
          );
        }
      });
  }

  function boot() {
    if (
      !/\/attempt\/\d+\/speaking\/?/.test(
        location.pathname
      )
    ) {
      return;
    }

    document.body.classList.add(
      'speaking-stable-v8'
    );

    const runner = findRunner();
    const part = inferPartOrder(
      runner
    );

    const clock = findClockElement();
    const digits = makeClockDisplay(
      clock
    );

    startClock(
      digits,
      runner,
      part
    );

    fixButtons();

    // Keep buttons correct when runner changes state.
    const observer = new MutationObserver(
      fixButtons
    );

    observer.observe(
      document.body,
      {
        subtree: true,
        childList: true,
        characterData: true,
        attributes: true,
        attributeFilter: [
          'disabled',
          'value',
          'class'
        ]
      }
    );
  }

  onReady(boot);
})();
