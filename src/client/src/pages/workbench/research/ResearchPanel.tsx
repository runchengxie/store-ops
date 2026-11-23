import {useEffect,useRef,useState} from 'react';
import {Link} from 'react-router-dom';
import {api} from '../../../api/client';
import {errText} from '../../../lib/errText';
import {safeEvidenceUrl} from '../playbooks/data.mjs';
import {parseResearchCsv} from './data.mjs';
import en from './en.json';
import zh from './zh-CN.json';
import './research.css';
type Payload=Record<string,string|null>;
type Row={record_id:string;revision:number;payload:Payload;actor:string;created_at:string;stale:boolean;match:{status:string;product_ids:string[]}};
type View={snapshot_id:string;records:Row[];history:Row[];truncated:boolean;comparisons:Record<string,any>[];prompts:{record_id:string;pnk:string;reason:string}[]};
const choices:Record<string,string[]>={kind:['opportunity','quote','pinterest_trend'],market:['RO','BG','HU'],currency:['RON','EUR','HUF'],price_basis:['unknown','inclusive_vat','exclusive_vat'],source_type:['manual','official','estimated'],buy_button:['unknown','yes','no'],status:['research','costing','hold','approved']};
const fields=['kind','keyword','trend_region','pnk','name','market','currency','price_basis','price','seller','comparison_key','buy_button','source_url','source_type','observed_at','period_start','period_end','performance_label','status','note'];
const initial=():Payload=>({kind:'opportunity',market:'RO',currency:'RON',price_basis:'unknown',source_type:'manual',buy_button:'unknown',status:'research'});
export default function ResearchPanel({store,snapshotId}:{store:string;snapshotId:string}){
 const [locale,setLocale]=useState<'en'|'zh-CN'>(()=>{try{return localStorage.getItem('emag.research.locale')==='zh-CN'?'zh-CN':'en';}catch{return 'en';}});
 const catalog:Record<string,string>=locale==='en'?en:zh;const t=(k:string)=>catalog[k]||k;
 const [view,setView]=useState<View|null>(null),[payload,setPayload]=useState<Payload>(initial),[editing,setEditing]=useState<Row|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[message,setMessage]=useState('');
 const generation=useRef(0);
 async function load(){const epoch=++generation.current;setView(null);setPayload(initial());setEditing(null);setError('');setMessage('');setBusy(false);try{const r=await api.get(`/emag/stores/${encodeURIComponent(store)}/research`);if(epoch===generation.current)setView(r.data);}catch(e){if(epoch===generation.current)setError(errText(e,t('error')));}}
 useEffect(()=>{void load();return()=>{generation.current++;};},[store,snapshotId]);
 const endpoint=`/emag/stores/${encodeURIComponent(store)}/research`;
 async function persist(rows?:Record<string,string>[]){if(!view||busy)return;const epoch=generation.current;setBusy(true);setError('');setMessage('');try{
  await api.post(rows?endpoint+'/import':endpoint,rows?{snapshot_id:view.snapshot_id,rows}:{snapshot_id:view.snapshot_id,payload,record_id:editing?.record_id||null,revision:editing?.revision||0});
  const r=await api.get(endpoint);if(epoch===generation.current){setView(r.data);setPayload(initial());setEditing(null);setMessage(t('saved'));}
 }catch(e){if(epoch===generation.current)setError(errText(e,t('error')));}finally{if(epoch===generation.current)setBusy(false);}}
 async function importFile(file?:File){if(!file||busy)return;const epoch=generation.current;try{if(file.size>1000000)throw Error('CSV exceeds size limit');const rows=parseResearchCsv(await file.text());if(epoch===generation.current)await persist(rows);}catch(e){if(epoch===generation.current)setError(errText(e,t('error')));}}
 function edit(row:Row){setEditing(row);setPayload({...row.payload});setMessage('');setError('');}
 return <section className="research-panel" data-testid="research-panel"><h2>{t('title')}</h2><label>{t('language')} <select aria-label={t('language')} value={locale} onChange={e=>{const value=e.target.value as 'en'|'zh-CN';setLocale(value);try{localStorage.setItem('emag.research.locale',value);}catch{}}}><option value="en">English</option><option value="zh-CN">简体中文</option></select></label><p>{t('scope')}</p><button disabled={busy} onClick={()=>void load()}>{t('reload')}</button>{error&&<p role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
 {view&&<><p><a href="https://trends.pinterest.com/" target="_blank" rel="noreferrer">{t("openTrends")}</a> · {t("trendHelp")}</p><form onSubmit={e=>{e.preventDefault();void persist();}}><fieldset disabled={busy}><legend>{editing?`${t('edit')} ${editing.revision}`:t('new')}</legend><div className="research-grid">{fields.filter(k=>payload.kind==='pinterest_trend'||!['keyword','trend_region'].includes(k)).map(k=><label key={k}>{t(k)} <small>({k})</small>{choices[k]?<select aria-label={t(k)} value={payload[k]||choices[k][0]} onChange={e=>setPayload(p=>({...p,[k]:e.target.value}))}>{choices[k].map(v=><option key={v} value={v}>{t(v)}</option>)}</select>:k==='note'?<textarea aria-label={t(k)} maxLength={2000} value={payload[k]||''} onChange={e=>setPayload(p=>({...p,[k]:e.target.value}))}/>:<input aria-label={t(k)} maxLength={500} value={payload[k]||''} onChange={e=>setPayload(p=>({...p,[k]:e.target.value}))}/>}</label>)}</div><button type="submit">{t('save')}</button><button type="button" onClick={()=>{setEditing(null);setPayload(initial());}}>{t('new')}</button></fieldset></form>
 <p>{t('importHelp')}</p><label>{t('import')} <input aria-label={t('import')} disabled={busy} type="file" accept=".csv,text/csv" onChange={e=>{void importFile(e.target.files?.[0]);e.target.value='';}}/></label><details><summary>CSV</summary><code>{fields.join(',')}</code></details>
 <h3>{t('prompts')}</h3><ul>{view.prompts.map((p,i)=><li key={i}>{p.pnk}: {t(p.reason)} <Link to="/tools">{t('costLink')}</Link></li>)}</ul>
 {!view.records.length&&<p>{t('empty')}</p>}{view.truncated&&<p role="status">{t('truncated')}</p>}
 {view.records.map(r=><article key={r.record_id}><h3>{r.payload.name} · {r.payload.pnk}</h3><p>{t(String(r.payload.kind))} · {t(String(r.payload.status))} · {t(String(r.payload.source_type))}</p><p>{r.payload.price??t('unknown')} {r.payload.currency} · {t(String(r.payload.price_basis))} · {r.payload.observed_at}</p><p>{t(r.match.status)} {r.match.product_ids.join(', ')} {r.stale&&<strong>{t('stale')}</strong>}</p>{safeEvidenceUrl(r.payload.source_url||'')&&<a href={safeEvidenceUrl(r.payload.source_url||'')!} target="_blank" rel="noreferrer">{t('source')}</a>}{r.payload.kind==='pinterest_trend'&&<p>{r.payload.keyword} · {r.payload.trend_region}</p>}<p>{r.payload.note}</p><button disabled={busy} onClick={()=>edit(r)}>{t('edit')}</button><details><summary>{t('history')}</summary>{view.history.filter(h=>h.record_id===r.record_id).map(h=><div key={h.revision}><p>#{h.revision} · {h.actor} · {h.created_at}</p><pre>{JSON.stringify(h.payload,null,2)}</pre></div>)}</details></article>)}
 <h3>{t('changes')}</h3>{view.comparisons.map((c,i)=><p key={i}>{c.pnk} · {c.market} · {c.seller} · {c.comparison_key} · {t('priceChange')}: {c.price_change} {c.currency} ({t(c.price_basis)}) · {c.before_at} → {c.after_at} {c.buy_button_changed&&t('buttonChanged')} {safeEvidenceUrl(c.source_url)&&<a href={safeEvidenceUrl(c.source_url)!} target="_blank" rel="noreferrer">{t('source')}</a>}</p>)}
 </>}
 </section>;
}
