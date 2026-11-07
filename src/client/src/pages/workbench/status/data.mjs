const count=v=>typeof v==='number'&&Number.isFinite(v)&&v>=0?v:null;
/** Pure presentation of evidence; no timer implies a marketplace action. */
export function deriveStatus(data,job,now=Date.now()){
 if(!data)return {state:'empty',action:'emptyAction',stale:false,metrics:{products:null,issues:null,stock:null}};
 const captured=Date.parse(data.captured_at);const stale=!Number.isFinite(captured)||now-captured>86400000||captured>now+60000;
 const stamp=Date.parse(job?.updated_at||job?.started_at);const same=job?.store_id===data.store_id;
 const active=same&&job?.status==='running'&&Number.isFinite(stamp)&&now-stamp>=0&&now-stamp<=120000;
 const ended=Date.parse(job?.finished_at||job?.updated_at||job?.started_at);
 const failed=same&&job?.status==='failed'&&Number.isFinite(ended)&&ended>=captured&&ended<=now+60000;
 const issues=Array.isArray(data.issues)?data.issues.length:null;
 const state=failed?'recovery':active?'working':stale?'stale':issues?'attention':'waiting';
 return {state,action:active?(job.stage==='collection'?'readingAction':'reviewingAction'):failed?'recoveryAction':stale?'staleAction':issues?'attentionAction':'waitingAction',stale,
  metrics:{products:Array.isArray(data.offers)?data.offers.length:null,issues,stock:count(data.commercial_summary?.inventory?.general_stock_total)}};
}

/** Prefer the freshest saved evidence, preserving an explicit valid choice. */
export function chooseStore(rows,preferred){
 if(rows.some(r=>r.store_id===preferred))return preferred;
 return [...rows].sort((a,b)=>(Date.parse(b.captured_at)||0)-(Date.parse(a.captured_at)||0))[0]?.store_id||'';
}
