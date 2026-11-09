/** Parse only evidence from the known inventory accessibility contract. */
export function classify(text, account) {
 if(typeof text!=='string'||text.length>1500000||!account||/\btruncated\b/i.test(text))return {state:'needs_review'};
 const url=text.match(/^- Page URL: (\S+)/m)?.[1];
 let u;try{u=new URL(url);}catch{return {state:'needs_review'};}
 if(u.protocol!=='https:'||!['marketplace.emag.ro','auth.emag.net'].includes(u.hostname))return {state:'needs_review'};
 const snapshot=text.split('### Snapshot')[1]||'';
 // A generic access denial never implies a CAPTCHA.
 if(/(?:^|\n)\s*- (?:heading|checkbox|textbox) "[^"\n]*(?:verify you are human|I am not a robot|verifica.{0,15}(?:robot|uman)|captcha)/i.test(snapshot)||/\/(?:captcha|challenge)(?:\/|$)/.test(u.pathname))return {state:'waiting_verification'};
 if(u.hostname==='auth.emag.net'||/^\/login(?:\/|$)/.test(u.pathname))return {state:'waiting_login'};
 if(u.pathname!=='/fulfillment/inventory')return {state:'needs_review'};
 const beforeHeading=snapshot.split(/- heading "Stocuri FBE"/)[0];
 const sellers=[...beforeHeading.matchAll(/^\s*- link "([^"\n]*)eMAG\.ro[^"\n]*"/gm)];
 if(sellers.length!==1||sellers[0][1].replace(/\p{Co}/gu,'').trim()!==account)return {state:'needs_review'};
 if(/- progressbar\b/.test(snapshot))return {state:'waiting_retry'};
 if(!snapshot.includes('heading "Stocuri FBE"')||!snapshot.includes('table "Offers fbe table"')||!snapshot.includes('columnheader "Stoc"'))return {state:'needs_review'};
 if(!/```yaml\n[\s\S]*?\n```/.test(snapshot))return {state:'needs_review'};
 const table=snapshot.slice(snapshot.indexOf('- table "Offers fbe table"'));
 const starts=[...table.matchAll(/^(\s*)- row(?: "[^"\n]*")?(?: \[[^\n]*\])?:\s*$/gm)];
 const rows=[];
 for(let i=0;i<starts.length;i++){
  const block=table.slice(starts[i].index,starts[i+1]?.index??table.length);
  if(block.includes('columnheader'))continue;
  const id=block.match(/\bID:\s*([0-9]{1,20})(?:\s|"|$)/)?.[1];
  if(!id||rows.some(r=>r.id===id))return {state:'needs_review'};
  const quantity=block.match(/- '?cell "Disponibile:\s*([^"\n]+)"/)?.[1].trim();
  if(quantity===undefined||!/^([0-9]+|-)$/.test(quantity))return {state:'needs_review'};
  // Only an explicit unavailable marker is unknown; malformed cells are errors.
  const stock=quantity==='-'?null:Number(quantity);
  if(stock!==null&&(!Number.isSafeInteger(stock)||stock>100000000))return {state:'needs_review'};
  rows.push({id,stock});
 }
 if(!rows.length||rows.length>100)return {state:'needs_review'};
 return {state:'complete',coverage:'visible_page',rows};
}

/** A resumed human challenge is inspected first; new checks always navigate fresh. */
export async function readInventory(call,{id,account,resume}){
 const marker='store_ops_check='+id;
 const url='https://marketplace.emag.ro/fulfillment/inventory?'+marker;
 const tabs=await call('browser_tabs',{action:'list'});
 const existing=tabs.split('\n').find(line=>line.includes(marker)&&line.includes('https://marketplace.emag.ro/fulfillment/inventory'));
 const index=existing?.match(/^- (\d+):/)?.[1];
 if(index!==undefined)await call('browser_tabs',{action:'select',index:Number(index)});
 else await call('browser_tabs',{action:'new'});
 const humanResume=index!==undefined&&['waiting_verification','waiting_login'].includes(resume);
 if(!humanResume)await call('browser_navigate',{url});
 let text=await call('browser_snapshot',{});
 let answer=classify(text,account);
 if(humanResume&&answer.state==='complete'){
  await call('browser_navigate',{url});
  text=await call('browser_snapshot',{});
  answer=classify(text,account);
 }
 if(answer.state==='waiting_retry'||text.includes('- progressbar')){
  await call('browser_wait_for',{time:3});
  text=await call('browser_snapshot',{});
  answer=classify(text,account);
 }
 return answer;
}
