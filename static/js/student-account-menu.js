/* STUDENT_ACCOUNT_MENU_V12_20260901 */
(()=>{
  const menus=[...document.querySelectorAll('[data-student-account-menu]')];
  if(!menus.length)return;
  const close=(menu)=>{const trigger=menu.querySelector('[data-student-account-trigger]');const pop=menu.querySelector('[data-student-account-popover]');if(!trigger||!pop)return;pop.hidden=true;trigger.setAttribute('aria-expanded','false');};
  const closeAll=(except)=>menus.forEach(menu=>{if(menu!==except)close(menu);});
  menus.forEach(menu=>{
    const trigger=menu.querySelector('[data-student-account-trigger]');
    const pop=menu.querySelector('[data-student-account-popover]');
    if(!trigger||!pop)return;
    trigger.addEventListener('click',(event)=>{event.stopPropagation();const opening=pop.hidden;closeAll(menu);pop.hidden=!opening;trigger.setAttribute('aria-expanded',opening?'true':'false');});
    pop.addEventListener('click',event=>event.stopPropagation());
  });
  document.addEventListener('click',()=>closeAll());
  document.addEventListener('keydown',event=>{if(event.key==='Escape')closeAll();});
})();
