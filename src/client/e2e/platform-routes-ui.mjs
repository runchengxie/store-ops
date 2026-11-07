import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import os from 'node:os';import path from 'node:path';
import {WsCDP,chromeArgs,evaluate,waitFor,delay} from './cdp.mjs';
const profile=await mkdtemp(path.join(os.tmpdir(),'platform-routes-'));
const {cdp,chrome}=await WsCDP.launch(chromeArgs(profile));
try {
 const {targetId}=await cdp.send('Target.createTarget',{url:'about:blank'});const {sessionId}=await cdp.send('Target.attachToTarget',{targetId,flatten:true});const send=(method,params={})=>cdp.send(method,params,sessionId);
 await send('Runtime.enable');await send('Page.enable');
 const results=[];
 for(const route of ['/legacy/dashboard','/legacy/market','/legacy/listing','/lingxing','/deep-analysis','/dashboard','/market','/playbook','/listing','/tools','/news','/console','/hub-settings']) {
  await send('Page.navigate',{url:`http://127.0.0.1:5289/?r=${route}`});await delay(1000);
  await waitFor(send,`!!document.querySelector('.main') || document.body.innerText.includes('404') || !!document.querySelector('main')`,'App mount');
  const result=await evaluate(send,`({text:document.body.innerText,bg:getComputedStyle(document.body).backgroundColor,links:[...document.querySelectorAll('a')].map(a=>a.getAttribute('href'))})`);
  assert.doesNotMatch(result.text,/页面渲染出错|Failed to resolve|Internal Server Error/);
  if(route.startsWith('/legacy')||['/lingxing','/deep-analysis'].includes(route)) assert.match(result.text,/404|找不到|不存在/);
  else assert.doesNotMatch(result.text,/404/);
  assert.ok(!result.links.some(link=>link?.startsWith('/legacy/')||link==='/lingxing'));
  results.push({route,bg:result.bg,length:result.text.length});
 }
 console.log(JSON.stringify(results));
} finally {cdp.ws.close();chrome.kill('SIGTERM');await new Promise(r=>chrome.once('exit',r));await rm(profile,{recursive:true,force:true,maxRetries:10,retryDelay:200});}
