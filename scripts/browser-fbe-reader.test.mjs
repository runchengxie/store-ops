import {test} from 'node:test';
import assert from 'node:assert/strict';
const fixture=`### Page
- Page URL: https://marketplace.emag.ro/fulfillment/inventory
### Snapshot
\`\`\`yaml
- navigation:
  - link "Example Store  eMAG.ro " [ref=e1]:
    - /url: "#"
- heading "Stocuri FBE" [level=1]
- table "Offers fbe table":
  - rowgroup:
    - row [ref=e2]:
      - columnheader "Stoc"
  - rowgroup:
    - row [ref=e3]:
      - 'cell "Demo product Status: Blocat ID: 12345" [ref=e4]':
        - link "Demo product":
          - /url: https://emag.ro/product_details/pd/TEST123
      - 'cell "Disponibile: 18" [ref=e5]':
\`\`\``;
test('reads verified visible inventory without claiming full coverage',async()=>{
 const {classify}=await import('./browser-fbe-contract.mjs');
 assert.deepEqual(classify(fixture,'Example Store'),{state:'complete',coverage:'visible_page',rows:[{id:'12345',stock:18}]});
});
test('wrong account and partial snapshots cannot publish',async()=>{
 const {classify}=await import('./browser-fbe-contract.mjs');
 assert.equal(classify(fixture,'Other Store').state,'needs_review');
 assert.equal(classify(fixture.replace('ID: 12345','ID: -'),'Example Store').state,'needs_review');
 assert.equal(classify(fixture+'\n[Snapshot truncated]','Example Store').state,'needs_review');
 assert.equal(classify(fixture.replace('### Snapshot','### Snapshot\n- progressbar'),'Example Store').state,'waiting_retry');
 assert.equal(classify(fixture.replace('https://marketplace.emag.ro/fulfillment/inventory','https://other.test/fulfillment/inventory'),'Example Store').state,'needs_review');
});
test('challenge and login need a human, unknown errors are not challenges',async()=>{
 const {classify}=await import('./browser-fbe-contract.mjs');
 assert.equal(classify('### Page\n- Page URL: https://marketplace.emag.ro/captcha\n### Snapshot\n- heading "Verify you are human"','Example Store').state,'waiting_verification');
 assert.equal(classify('### Page\n- Page URL: https://marketplace.emag.ro/login\n### Snapshot\n- textbox "Password"','Example Store').state,'waiting_login');
 assert.equal(classify('HTTP 403 Forbidden','Example Store').state,'needs_review');
});

test('rejects prefix account matches, ambiguous quantities and cut-off rows',async()=>{
 const {classify}=await import('./browser-fbe-contract.mjs');
 assert.equal(classify(fixture.replace('Example Store ','Example Store Other Seller '),'Example Store').state,'needs_review');
 for(const value of ['1.234','1,234','1 234','18 units'])assert.equal(classify(fixture.replace('Disponibile: 18','Disponibile: '+value),'Example Store').state,'needs_review');
 assert.equal(classify(fixture.slice(0,fixture.indexOf('ID: 12345')+9),'Example Store').state,'needs_review');
 assert.equal(classify(fixture.replace('Disponibile: 18','Other stock field'),'Example Store').state,'needs_review');
 assert.equal(classify(fixture.replace('Disponibile: 18','Disponibile: -'),'Example Store').rows[0].stock,null);
});
test('exclusive reader lease remains owned independently of Python',async()=>{
 const {acquireBrowserLease}=await import('./browser-fbe-lease.mjs');
 const server=await acquireBrowserLease(0);
 try{await assert.rejects(acquireBrowserLease(server.address().port),{code:'EADDRINUSE'});}
 finally{await new Promise(r=>server.close(r));}
});

test('repeat checks navigate fresh while verification resume inspects first',async()=>{
 const {readInventory}=await import('./browser-fbe-contract.mjs');
 for(const resume of ['complete','waiting_verification']){
  const calls=[];
  const call=async(name,args)=>{calls.push(name);return name==='browser_tabs'&&args.action==='list'?'- 1: [Stocuri FBE](https://marketplace.emag.ro/fulfillment/inventory?store_ops_check='+ 'a'.repeat(32)+')':fixture;};
  assert.equal((await readInventory(call,{id:'a'.repeat(32),account:'Example Store',resume})).state,'complete');
  assert.equal(calls.includes('browser_navigate'),true);
 }
});

test('an unresolved verification is not navigated away on resume',async()=>{
 const {readInventory}=await import('./browser-fbe-contract.mjs');
 const id='a'.repeat(32),calls=[];
 const challenge='### Page\n- Page URL: https://marketplace.emag.ro/captcha\n### Snapshot\n- heading "Verify you are human"';
 const call=async(name,args)=>{calls.push(name);return name==='browser_tabs'&&args.action==='list'?'- 1: [Check](https://marketplace.emag.ro/fulfillment/inventory?store_ops_check='+id+')':challenge;};
 assert.equal((await readInventory(call,{id,account:'Example Store',resume:'waiting_verification'})).state,'waiting_verification');
 assert.equal(calls.includes('browser_navigate'),false);
});
