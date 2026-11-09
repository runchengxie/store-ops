// Synthetic common-port responses for the real App. No platform connector runs.
export function platformReply(path:string,method?:string,body?:unknown){
 const controls=((window as any).__monitoringControls ||= {});
 const checks=((window as any).__browserChecks ||= {});
 const bm=path.match(/^\/operations\/stores\/([^/]+)\/browser-check$/);
 if(bm&&method==='post')return checks[bm[1]]={task_id:'a'.repeat(32),store_id:bm[1],kind:'fbe_inventory',state:'queued',revision:4};
 const cm=path.match(/^\/operations\/stores\/([^/]+)\/control$/);
 if(cm&&method==='post'){if((window as any).__controlFail)throw Object.assign(new Error('Synthetic control error'),{response:{status:503}});const payload=typeof body==='string'?JSON.parse(body):body as any;const previous=controls[cm[1]]||{paused:false,state:'enabled',revision:0};if(payload.revision!==previous.revision)throw new Error('Conflict');return controls[cm[1]]={paused:payload.paused,state:payload.paused?'paused':'enabled',revision:previous.revision+1};}
 if(method&&method!=='get')return null;
 const params=new URLSearchParams(location.search);const scenario=params.get('statuscase');
 const multi=params.get('wbcase')==='multi';
 if(path==='/operations/stores'){
  if((window as any).__statusListFail)throw Object.assign(new Error('Synthetic list unavailable'),{response:{status:503}});
  if(scenario==='empty')return [];
  return [{store_id:'demo-ro',captured_at:new Date().toISOString(),platform:'emag'},...(multi?[{store_id:'second-ro',platform:'emag'}]:[])];
 }
 const m=path.match(/^\/operations\/stores\/([^/]+)\/overview$/);if(!m)return null;
 if(scenario==='offline')throw Object.assign(new Error('Synthetic unavailable'),{response:{status:503}});
 const store=m[1];const failed=scenario==='failed',running=['active','old-running'].includes(scenario||'');
 const browser=params.get('browsercase');
 const browser_check=checks[store]||(browser?{task_id:'a'.repeat(32),store_id:store,kind:'fbe_inventory',state:browser,revision:3,last_success_at:new Date(Date.now()-3600000).toISOString()}:null);
 return {browser_check,browser_check_available:true,control:controls[store]||{paused:false,state:'enabled',revision:0},store_id:store,platform:'emag',platform_label:'eMAG',marketplace:'RO',currency:'RON',timezone:'Europe/Bucharest',snapshot_id:store+'-v1',captured_at:new Date(Date.now()-60000).toISOString(),source:'synthetic common adapter',coverage:['synthetic'],limitations:['Test only'],metrics:{products:store==='second-ro'?2:1,issues:1,stock:null},collection:{store_id:store,status:failed?'failed':running?'running':'complete',stage:'collection',started_at:new Date(((window as any).__statusFrozenJobTime||Date.now())-(scenario==='old-running'?3600000:10000)).toISOString()}};
}
