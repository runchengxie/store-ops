/** Synthetic-only fixtures, never bundled into the public demo. */
export async function insightsReply(path:string,method?:string,data?:any,params?:any){
 const mode=new URLSearchParams(location.search).get('insightscase');if(!mode)return null;
 if(mode==='no-stores'&&path==='/emag/stores')return [];
 if(mode==='multi'&&path==='/emag/stores')return [{store_id:'demo-ro'},{store_id:'second-ro'}];
 const revision='synthetic-index-v1';const source={source_id:'synthetic-source',title:'Synthetic training reference',source_hash:'synthetic-hash',trust:'historical_transcript',date:null,revision,conflicts:['Synthetic conflict: newer instructions must be verified.']};const chunk={chunk_id:'synthetic-chunk',locator:'Lesson 2 / 00:45',excerpt:'Synthetic excerpt <script>must remain plain text</script>.'};
 if(path==='/emag/knowledge/status')return {available:mode!=='no-index',revision,source_count:1,chunk_count:1};
 if(path==='/emag/knowledge/search'){if(params?.q==='slow')await new Promise(r=>setTimeout(r,900));return {available:mode!=='no-index',revision,results:mode==='no-index'?[]:[{...source,...chunk,title:params?.q==='slow'?'Old slow result':source.title}],marketplace_writes:false};}
 if(path.startsWith('/emag/knowledge/sources/')){if(params?.revision!==revision)throw Object.assign(new Error('Synthetic revision mismatch'),{response:{status:409}});return {...source,chunks:[chunk],truncated:false};}
 const match=path.match(/^\/emag\/stores\/([^/]+)\/(decision-support|preflight|promotion-check\/[^/]+)$/);if(!match)return null;
 const store_id=match[1],snapshot_id=store_id+'-snapshot';
 if(match[2]==='decision-support'){if(mode==='multi'&&store_id==='demo-ro')await new Promise(r=>setTimeout(r,700));return {store_id,snapshot_id,captured_at:'2026-11-08T00:00:00Z',products:[{id:1,name:store_id+' synthetic product'}],cards:[{id:'price',product_id:1,title_key:'price_review',reason:'Synthetic observed price blocker',priority:1,stock:5,evidence:[{field:'price_status',value:'invalid'}],checks:[{key:'platform_reason',status:'unknown'}],knowledge_query:'price'}],marketplace_writes:false};}
 if(mode==='stale')throw Object.assign(new Error('Synthetic stale snapshot'),{response:{status:409}});
 if(mode==='error')throw Object.assign(new Error('Synthetic request error'),{response:{status:422}});
 if(match[2]==='preflight')return {store_id,snapshot_id,file_name:data.get('file').name,status:'needs_review',layout:{sheet:'Products',header_row:1,data_start_row:2,fields:['name']},row_count:2,issues:[{code:'missing_required',severity:'review',sheet:'Products',row:2,column:1,field:'name',details:{check:'unknown'}}],truncated:false,marketplace_writes:false};
 const body=typeof data==='string'?JSON.parse(data):data;const complete=body.extra_cost_ron!==null&&mode==='valid';return {store_id,snapshot_id,product_id:1,status:complete?'review_required':'incomplete',price_basis:'exclusive_vat',currency:'RON',cost_revision:complete?'synthetic-cost-v1':null,missing:complete?[]:['purchase_cny','current_cost_revision'],warnings:[{code:'assumptions_require_verification',details:{}}],scenarios:complete?[{kind:'discount',sale_price_ex_vat_ron:'90',economics:{contribution_ron:'12.50'},support_ex_vat_ron:null,contribution_with_assumed_support_ron:null}]:[],marketplace_writes:false};
}
