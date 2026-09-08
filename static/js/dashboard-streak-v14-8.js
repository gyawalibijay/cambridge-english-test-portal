/* DASHBOARD_STREAK_V14_8 */
(() => {
  const milestones=[7,14,30,50,100,200,365];
  const rangeFor=streak=>{
    for(const target of milestones){
      if(streak<target){
        const previous=milestones.filter(v=>v<=streak).pop()||0;
        return {previous,target};
      }
    }
    const previous=Math.floor(streak/100)*100;
    return {previous,target:Math.max(previous+100,streak+1)};
  };

  document.querySelectorAll('.streak-v148[data-streak]').forEach(card=>{
    const streak=Math.max(0,parseInt(card.dataset.streak||'0',10)||0);
    const label=card.querySelector('[data-streak-next]');
    const bar=card.querySelector('[data-streak-progress]');
    if(!label||!bar)return;
    const {previous,target}=rangeFor(streak);
    const remaining=Math.max(0,target-streak);
    const pct=Math.max(0,Math.min(100,((streak-previous)/Math.max(1,target-previous))*100));
    label.textContent=remaining===1?`1 more day to ${target}`:`${remaining} more days to ${target}`;
    requestAnimationFrame(()=>{bar.style.width=`${pct}%`});
  });
})();
