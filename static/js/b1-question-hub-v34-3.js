(() => {
  const base="/admin/question_bank/question/";
  if(!location.pathname.startsWith(base) || location.pathname===base) return;

  const target=document.querySelector("#content-main")||document.querySelector("#content");
  if(!target || document.querySelector(".b1qh-global-strip")) return;

  const nav=document.createElement("nav");
  nav.className="b1qh-global-strip";
  nav.innerHTML=`
    <a href="${base}">Question Hub</a>
    <a href="${base}?panel=listening">Listening</a>
    <a href="${base}?panel=reading">Reading</a>
    <a href="${base}?panel=speaking">Speaking</a>
    <a href="${base}?panel=writing">Writing</a>
    <a class="special" href="/admin/listening-sets/">Listening Sets</a>
  `;
  target.insertBefore(nav,target.firstChild);
})();
