// Synthetic common-port responses for the real App. No platform connector runs.
export function platformReply(path:string,method?:string){
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
 return {store_id:store,platform:'emag',platform_label:'eMAG',marketplace:'RO',currency:'RON',timezone:'Europe/Bucharest',snapshot_id:store+'-v1',captured_at:new Date(Date.now()-60000).toISOString(),source:'synthetic common adapter',coverage:['synthetic'],limitations:['Test only'],metrics:{products:store==='second-ro'?2:1,issues:1,stock:null},collection:{store_id:store,status:failed?'failed':running?'running':'complete',stage:'collection',started_at:new Date(((window as any).__statusFrozenJobTime||Date.now())-(scenario==='old-running'?3600000:10000)).toISOString()}};
}
