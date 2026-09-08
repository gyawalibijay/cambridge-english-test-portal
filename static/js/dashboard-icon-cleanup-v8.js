(function () {
  function clean() {
    document
      .querySelectorAll(
        '.sf-ref-nav-icon,.sf-ref-nav-icon-v7'
      )
      .forEach(el => el.remove());

    document
      .querySelectorAll(
        '[data-ref6-icon],[data-icon-repair-v7]'
      )
      .forEach(el => {
        el.removeAttribute('data-ref6-icon');
        el.removeAttribute('data-icon-repair-v7');
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener(
      'DOMContentLoaded',
      clean,
      { once: true }
    );
  } else {
    clean();
  }
})();
