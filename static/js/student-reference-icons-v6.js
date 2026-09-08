(function(){
  const icons = {
    home: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="4" y="4" width="6" height="6" rx="1"></rect>
        <rect x="14" y="4" width="6" height="6" rx="1"></rect>
        <rect x="4" y="14" width="6" height="6" rx="1"></rect>
        <rect x="14" y="14" width="6" height="6" rx="1"></rect>
      </svg>`,
    practice: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="8.5"></circle>
        <circle cx="12" cy="12" r="4.5"></circle>
        <circle cx="12" cy="12" r="1.4"></circle>
      </svg>`,
    mock: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="13" r="7.5"></circle>
        <path d="M9 3h6M12 5.5V8M17.4 7.6l1.5-1.5"></path>
      </svg>`,
    learn: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3 9.5 12 5l9 4.5-9 4.5-9-4.5Z"></path>
        <path d="M6.5 11.3v4.1c2.9 2.1 8.1 2.1 11 0v-4.1M20 10v5"></path>
      </svg>`,
    progress: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 19V9M10 19V5M15 19v-7M20 19V8"></path>
        <path d="M3.5 19.5h18"></path>
      </svg>`,
    certificates: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="9" r="4.5"></circle>
        <path d="m9.5 13-1 7 3.5-2 3.5 2-1-7"></path>
      </svg>`,
    profile: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="8" r="3.5"></circle>
        <path d="M5.5 20c.6-4 3-6.2 6.5-6.2s5.9 2.2 6.5 6.2"></path>
      </svg>`,
    target: `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="8"></circle>
        <circle cx="12" cy="12" r="3"></circle>
      </svg>`
  };

  function normalized(el){
    return (el.textContent || '').replace(/\s+/g,' ').trim().toLowerCase();
  }

  function iconKey(text){
    if(text === 'home' || text.includes('home')) return 'home';
    if(text.includes('mock test')) return 'mock';
    if(text === 'practice' || text.includes('practice')) return 'practice';
    if(text.includes('learn')) return 'learn';
    if(text.includes('progress')) return 'progress';
    if(text.includes('certificate')) return 'certificates';
    if(text.includes('profile')) return 'profile';
    return null;
  }

  function upgradeSidebar(){
    document.querySelectorAll('.sf-sidebar a').forEach(link => {
      const key = iconKey(normalized(link));
      if(!key || link.dataset.ref6Icon === '1') return;

      const old = link.querySelector(
        '.sf-ref-nav-icon,.sf-nav-icon,.sf-side-icon,.icon,.ico'
      );
      if(old) old.remove();

      const holder = document.createElement('span');
      holder.className = 'sf-ref-nav-icon';
      holder.innerHTML = icons[key];
      link.insertBefore(holder, link.firstChild);
      link.dataset.ref6Icon = '1';
    });

    document.querySelectorAll('.sf-sidebar button').forEach(button => {
      if(normalized(button) === 'theme'){
        button.dataset.refThemeButton = '1';
        button.remove();
      }
    });
  }

  function findCardByHeading(label){
    const headings = Array.from(
      document.querySelectorAll(
        '.sf-main h2,.sf-main h3'
      )
    );

    const heading = headings.find(h => normalized(h) === label);
    if(!heading) return null;

    return heading.closest(
      'article,.sf-action-card,.sf-feature-card,.sf-card'
    ) || heading.parentElement;
  }

  function actionIcon(card,key){
    if(!card || card.dataset.ref6Action === '1') return;

    card.classList.add('sf-ref-action-card');

    const existing = card.querySelector(
      '.sf-ref-action-icon,.sf-action-icon,.sf-feature-icon,.icon'
    );
    if(existing) existing.remove();

    const heading = card.querySelector('h2,h3');
    if(!heading) return;

    const holder = document.createElement('div');
    holder.className = 'sf-ref-action-icon';
    holder.innerHTML = icons[key];

    heading.parentNode.insertBefore(holder, heading);
    card.dataset.ref6Action = '1';
  }

  function upgradeDashboard(){
    actionIcon(findCardByHeading('practice'),'practice');
    actionIcon(findCardByHeading('mock test'),'mock');
    actionIcon(findCardByHeading('learn'),'learn');
  }

  function boot(){
    upgradeSidebar();
    upgradeDashboard();
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded',boot,{once:true});
  }else{
    boot();
  }
})();
