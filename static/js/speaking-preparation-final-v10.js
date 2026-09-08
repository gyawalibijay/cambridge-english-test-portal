(function () {
  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn, { once: true });
    } else {
      fn();
    }
  }

  function visible(el) {
    if (!el) return false;
    const s = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return s.display !== 'none' &&
      s.visibility !== 'hidden' &&
      r.width > 0 &&
      r.height > 0;
  }

  function cleanText(el) {
    return ((el && (el.value || el.textContent)) || '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function onSpeakingRunner() {
    return /\/attempt\/\d+\/speaking\/?$/.test(location.pathname);
  }

  function partOrder() {
    const runner =
      document.getElementById('runner') ||
      document.querySelector('[data-part-order]');

    const raw = Number(
      runner &&
      (
        runner.dataset.partOrder ||
        runner.getAttribute('data-part-order')
      )
    );

    if (raw >= 1 && raw <= 5) return raw;

    const body = (document.body.innerText || '').toLowerCase();

    if (body.includes('part 5') || body.includes('40 seconds')) return 5;
    if (body.includes('part 4')) return 4;
    if (body.includes('part 3') || body.includes('read the sentence out loud')) return 3;
    if (body.includes('part 2') || body.includes('20 seconds to answer')) return 2;
    return 1;
  }

  function prepSeconds() {
    const runner =
      document.getElementById('runner') ||
      document.querySelector('[data-preparation-seconds]');

    const raw = Number(
      runner &&
      (
        runner.dataset.preparationSeconds ||
        runner.getAttribute('data-preparation-seconds')
      )
    );

    if (Number.isFinite(raw) && raw > 0) return raw;

    /*
      Client/source requirement:
      Parts 1-4 use the configured short preparation countdown.
      Part 5 uses 40 seconds.
    */
    return partOrder() === 5 ? 40 : 4;
  }

  function findListenButton() {
    return Array.from(
      document.querySelectorAll(
        'button,a,input[type="button"],input[type="submit"]'
      )
    ).find(el => {
      if (!visible(el)) return false;
      const t = cleanText(el).toLowerCase();
      return (
        t === 'listen' ||
        t.includes('playing') ||
        t.includes('listen')
      );
    }) || null;
  }

  function findNowRecordLabel() {
    return Array.from(
      document.querySelectorAll('p,div,span,h1,h2,h3,h4')
    ).find(el => {
      if (!visible(el)) return false;
      return cleanText(el).toLowerCase() === 'now record your answer';
    }) || null;
  }

  function findNativePrepNumber() {
    return (
      document.getElementById('prepNumber') ||
      Array.from(
        document.querySelectorAll('[data-prep-number],.prep-number')
      )[0] ||
      null
    );
  }

  function findNativePrepRing() {
    return (
      document.getElementById('prepRing') ||
      Array.from(
        document.querySelectorAll('[data-prep-ring],.prep-ring')
      )[0] ||
      null
    );
  }

  function findNativeSpeakButton() {
    return (
      document.getElementById('earlySpeakButton') ||
      Array.from(
        document.querySelectorAll(
          'button,input[type="button"],input[type="submit"],a'
        )
      ).find(el => cleanText(el).toLowerCase() === 'speak') ||
      null
    );
  }

  function buildUI(anchor) {
    const root = document.createElement('div');
    root.className = 'sp10-prep';

    root.innerHTML = `
      <div class="sp10-prep-label">Start speaking in</div>
      <div class="sp10-ring-wrap">
        <svg class="sp10-ring" viewBox="0 0 106 106" aria-hidden="true">
          <circle class="sp10-track" cx="53" cy="53" r="43"></circle>
          <circle class="sp10-progress" cx="53" cy="53" r="43"></circle>
        </svg>
        <div class="sp10-value">4</div>
      </div>
      <button type="button" class="sp10-speak">Speak</button>
    `;

    const parent = anchor.parentNode;
    parent.insertBefore(root, anchor.nextSibling);

    return {
      root,
      value: root.querySelector('.sp10-value'),
      progress: root.querySelector('.sp10-progress'),
      speak: root.querySelector('.sp10-speak')
    };
  }

  function clockSetup(progress) {
    const radius = 43;
    const circumference = 2 * Math.PI * radius;

    progress.style.strokeDasharray = String(circumference);
    progress.style.strokeDashoffset = String(circumference);

    return circumference;
  }

  function animateSmoothSecond(progress, circumference, fromFraction, toFraction) {
    const started = performance.now();
    const duration = 970;

    function frame(now) {
      const t = Math.min(1, (now - started) / duration);
      const f = fromFraction + (toFraction - fromFraction) * t;
      progress.style.strokeDashoffset =
        String(circumference * (1 - f));

      if (t < 1) requestAnimationFrame(frame);
    }

    requestAnimationFrame(frame);
  }

  function install() {
    if (!onSpeakingRunner()) return;

    document.body.setAttribute('data-speaking-prep-v10', '1');

    const anchor = findNowRecordLabel();
    if (!anchor) return;

    const ui = buildUI(anchor);
    const circumference = clockSetup(ui.progress);

    const nativeNumber = findNativePrepNumber();
    const nativeRing = findNativePrepRing();
    const nativeSpeak = findNativeSpeakButton();
    const listen = findListenButton();

    if (nativeNumber) nativeNumber.classList.add('sp10-native-hidden');
    if (nativeRing) nativeRing.classList.add('sp10-native-hidden');

    let total = prepSeconds();
    let previous = total;
    let fallbackInterval = null;
    let fallbackStarted = false;
    let lastPlayingState = false;

    ui.value.textContent = String(total);

    function setVisual(value) {
      const current = Math.max(0, Math.min(total, Number(value) || 0));

      ui.value.textContent = String(current);

      const oldFraction =
        total > 0
          ? (total - previous) / total
          : 0;

      const newFraction =
        total > 0
          ? (total - current) / total
          : 1;

      animateSmoothSecond(
        ui.progress,
        circumference,
        oldFraction,
        newFraction
      );

      previous = current;
    }

    function show() {
      ui.root.classList.add('is-visible');
    }

    function hide() {
      ui.root.classList.remove('is-visible');
    }

    function syncNativeNumber() {
      if (!nativeNumber) return false;

      const n = Number(
        cleanText(nativeNumber)
      );

      if (!Number.isFinite(n)) return false;

      show();
      setVisual(n);
      return true;
    }

    function triggerNativeSpeak() {
      if (nativeSpeak && nativeSpeak !== ui.speak) {
        nativeSpeak.click();
      }
    }

    ui.speak.addEventListener('click', function () {
      if (fallbackInterval) {
        clearInterval(fallbackInterval);
        fallbackInterval = null;
      }

      triggerNativeSpeak();
      hide();
    });

    function startFallbackCountdown() {
      if (fallbackStarted) return;
      fallbackStarted = true;

      total = prepSeconds();
      previous = total;
      setVisual(total);
      show();

      let remaining = total;

      fallbackInterval = setInterval(function () {
        remaining -= 1;
        setVisual(remaining);

        if (remaining <= 0) {
          clearInterval(fallbackInterval);
          fallbackInterval = null;

          /*
            If the native runner has a Speak control, use it.
            Otherwise the visual countdown simply ends and does not
            interfere with the recorder.
          */
          triggerNativeSpeak();
          hide();
        }
      }, 1000);
    }

    if (nativeNumber) {
      const observer = new MutationObserver(function () {
        syncNativeNumber();
      });

      observer.observe(
        nativeNumber,
        {
          childList: true,
          subtree: true,
          characterData: true
        }
      );
    }

    if (listen) {
      const observer = new MutationObserver(function () {
        const t = cleanText(listen).toLowerCase();
        const isPlaying = t.includes('playing');

        /*
          When playback ends, the button changes away from "Playing...".
          Start the visible preparation countdown at that exact point.
        */
        if (lastPlayingState && !isPlaying) {
          if (!syncNativeNumber()) {
            startFallbackCountdown();
          }
        }

        if (isPlaying) hide();

        lastPlayingState = isPlaying;
      });

      observer.observe(
        listen,
        {
          childList: true,
          subtree: true,
          characterData: true,
          attributes: true,
          attributeFilter: ['value','class','disabled']
        }
      );

      lastPlayingState =
        cleanText(listen).toLowerCase().includes('playing');
    }

    /*
      Audio element route: more reliable when the prompt uses a real audio file.
    */
    document.querySelectorAll('audio').forEach(function (audio) {
      audio.addEventListener('play', hide);

      audio.addEventListener('ended', function () {
        if (!syncNativeNumber()) {
          startFallbackCountdown();
        }
      });
    });

    /*
      If the native prep timer is already running when this patch loads,
      display it immediately.
    */
    if (nativeNumber) {
      const n = Number(cleanText(nativeNumber));

      if (Number.isFinite(n) && n > 0) {
        syncNativeNumber();
      }
    }
  }

  ready(install);
})();
