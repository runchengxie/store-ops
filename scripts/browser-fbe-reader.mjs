/** Fixed, read-only MCP reader. Never accepts tool names, URLs or scripts as input. */
import {pathToFileURL} from 'node:url';
import path from 'node:path';
import {readInventory} from './browser-fbe-contract.mjs';
const id=process.argv[2];
import {acquireBrowserLease} from './browser-fbe-lease.mjs';
let answer={state:'waiting_browser'},client,lease,stage='configuration';
const timer=setTimeout(()=>{process.stdout.write(JSON.stringify({state:'waiting_browser'}));process.exit(1);},135000);
try{
 if(!/^[a-f0-9]{32}$/.test(id||''))throw Error('Invalid task');
 stage='exclusive_reader';
 lease=await acquireBrowserLease();
 const root=process.env.IVYEA_OPS_BROWSER_SDK_ROOT;
 if(!root||!path.isAbsolute(root))throw Error('Missing SDK');
 const {Client}=await import(pathToFileURL(path.join(root,'dist/esm/client/index.js')).href);
 const {StreamableHTTPClientTransport}=await import(pathToFileURL(path.join(root,'dist/esm/client/streamableHttp.js')).href);
 client=new Client({name:'store-ops-fbe-readonly',version:'1.0'},{capabilities:{}});
 // Existing extension bridge is loopback only; no token is copied to this worker.
 stage='connect';
 await client.connect(new StreamableHTTPClientTransport(new URL('http://127.0.0.1:8931/mcp')));
 const call=async(name,args)=>{
  stage=name;
  const r=await client.callTool({name,arguments:args},undefined,{timeout:15000});
  if(r.isError)throw Error('Browser unavailable');
  const text=(r.content||[]).filter(c=>c.type==='text').map(c=>c.text).join('\n');
  if(text.length>1500000)throw Error('Snapshot too large');
  return text;
 };
 answer=await readInventory(call,{id,account:process.env.IVYEA_OPS_BROWSER_ACCOUNT,resume:process.env.IVYEA_OPS_BROWSER_RESUME_FROM});
}catch{
 process.stderr.write('Browser check stopped at '+stage+'\n');
 answer={state:'waiting_browser'};
}finally{
 if(client)try{await client.close();}catch{}
 if(lease)await new Promise(resolve=>lease.close(resolve));
 clearTimeout(timer);
}
process.stdout.write(JSON.stringify(answer));
