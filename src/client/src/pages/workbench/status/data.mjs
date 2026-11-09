const count=v=>typeof v==='number'&&Number.isFinite(v)&&v>=0?v:null;
/** Pure presentation of evidence; no timer implies a marketplace action. */
export function deriveStatus(data,job,now=Date.now()){
 if(!data)return {state:'empty',action:'emptyAction',stale:false,metrics:{products:null,issues:null,stock:null}};
 const captured=Date.parse(data.captured_at);const stale=!Number.isFinite(captured)||now-captured>86400000||captured>now+60000;
 const stamp=Date.parse(job?.updated_at||job?.started_at);const same=job?.store_id===data.store_id;
 const active=same&&job?.status==='running'&&Number.isFinite(stamp)&&now-stamp>=0&&now-stamp<=120000;
 const ended=Date.parse(job?.finished_at||job?.updated_at||job?.started_at);
 const failed=same&&job?.status==='failed'&&Number.isFinite(ended)&&ended>=captured&&ended<=now+60000;
 const issues=count(data.metrics?.issues);
 const state=failed?'recovery':active?'working':stale?'stale':issues?'attention':'waiting';
 return {state,action:active?(job.stage==='collection'?'readingAction':'reviewingAction'):failed?'recoveryAction':stale?'staleAction':issues?'attentionAction':'waitingAction',stale,
  metrics:{products:count(data.metrics?.products),issues,stock:count(data.metrics?.stock)}};
}

/** Prefer the freshest saved evidence, preserving an explicit valid choice. */
export function chooseStore(rows,preferred){
 if(rows.some(r=>r.store_id===preferred))return preferred;
 return [...rows].sort((a,b)=>(Date.parse(b.captured_at)||0)-(Date.parse(a.captured_at)||0))[0]?.store_id||'';
}

/** A server acknowledgement must be internally consistent before showing paused. */
export function validMonitoringControl(value){
 return !!value&&Number.isInteger(value.revision)&&value.revision>=0&&typeof value.paused==='boolean'&&
  (value.paused?['pausing','paused'].includes(value.state):value.state==='enabled');
}

/** Late responses cannot undo a newer acknowledgement from another controller. */
export function mergeMonitoringControl(current,incoming){
 if(!validMonitoringControl(incoming))throw Error('Invalid control acknowledgement');
 return validMonitoringControl(current)&&current.revision>incoming.revision?current:incoming;
}

/** Browser assistance never changes the main API monitoring state. */
export function browserNotice(task,store){
 if(!task||task.store_id!==store||task.kind!=='fbe_inventory'||!Number.isInteger(task.revision)||task.revision<0||!/^[a-f0-9]{32}$/.test(task.task_id))return null;
 const keys={queued:'browserQueued',running:'browserRunning',waiting_verification:'browserVerification',waiting_login:'browserLogin',waiting_browser:'browserUnavailable',waiting_retry:'browserRetry',needs_review:'browserReview',paused:'browserPaused',complete:'browserComplete'};
 const message=keys[task.state];if(!message)return null;
 return {message,action:task.state==='running'?null:['waiting_verification','waiting_login'].includes(task.state)?'browserContinue':task.state==='complete'?'browserAgain':'browserRetryAction'};
}
