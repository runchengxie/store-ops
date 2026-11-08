import {useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {ArrowUpRight,ChevronRight,Pause,SlidersHorizontal} from 'lucide-react';
import {deriveStatus} from './data.mjs';
import {resolveStatusLocale,withStatusLanguage} from './locale.mjs';
import en from './en.json';import zh from './zh-CN.json';
import './status.css';
type Props={active?:boolean;data:any;job:any;stores:{store_id:string}[];store:string;onStore:(v:string)=>void;loading:boolean;error:string;onRefresh:()=>void;demo?:boolean;onSettings?:()=>void;onLogout?:()=>void;canInspect?:boolean;onControl?:(paused:boolean)=>void;controlPending?:boolean;controlError?:string};
export default function StatusHome({data,job,stores,store,onStore,loading,error,onRefresh,demo=false,onSettings,onLogout,canInspect=true,active=true,onControl,controlPending=false,controlError=''}:Props){
 const [locale,setLocale]=useState<'en'|'zh-CN'>(()=>{let saved=null;try{saved=localStorage.getItem('store.status.locale');}catch{}return resolveStatusLocale(location.search,saved,navigator.languages||[navigator.language]);});
 useEffect(()=>{document.documentElement.lang=locale;},[locale]);
 const c:Record<string,string>=locale==='en'?en:zh;const t=(key:string,values:Record<string,string|number>={})=>Object.entries(values).reduce((s,[k,v])=>s.replaceAll('{'+k+'}',String(v)),c[key]||key);
 const [index,setIndex]=useState(0),[paused,setPaused]=useState(false),[reduced,setReduced]=useState(()=>window.matchMedia('(prefers-reduced-motion: reduce)').matches),[visible,setVisible]=useState(!document.hidden),[,setNow]=useState(Date.now());
 useEffect(()=>{const media=window.matchMedia('(prefers-reduced-motion: reduce)');const update=()=>setReduced(media.matches);const visibility=()=>{setVisible(!document.hidden);setNow(Date.now());};media.addEventListener('change',update);document.addEventListener('visibilitychange',visibility);return()=>{media.removeEventListener('change',update);document.removeEventListener('visibilitychange',visibility);};},[]);
 useEffect(()=>{setIndex(0);},[store]);
 useEffect(()=>{if(!visible||!active)return;setNow(Date.now());const timer=setInterval(()=>setNow(Date.now()),10000);return()=>clearInterval(timer);},[visible,active]);
 const slides=['readProducts','checkPrices','checkStock','prepareReview'];
 useEffect(()=>{if(!demo||paused||reduced||!visible||!active||!data)return;const timer=setInterval(()=>setIndex(i=>(i+1)%slides.length),6000);return()=>clearInterval(timer);},[paused,reduced,visible,active,!!data,demo,slides.length]);
 const result=deriveStatus(data,job,Date.now());const state=error?'offline':loading&&!data?'loading':result.state;
 const control=demo?{state:paused?'paused':'enabled',paused}:data?.control;
 const takeoverPaused=control?.state==='paused';const pausing=control?.state==='pausing';
 const title=pausing?'pausing':takeoverPaused?'paused':demo?'demoTitle':state;const action=takeoverPaused?'pausedAction':pausing?'pausingAction':demo?slides[index]:error?'offlineAction':loading&&!data?'loadingAction':result.action;
 const format=(value:number|null)=>value===null?'—':new Intl.NumberFormat(locale).format(value);
 let date=t('unknown');if(data&&Number.isFinite(Date.parse(data.captured_at))){try{date=new Intl.DateTimeFormat(locale,{dateStyle:'medium',timeStyle:'short',timeZone:data.timezone||'UTC'}).format(new Date(data.captured_at));}catch{}}
 return <main className="status-home" data-testid="status-home" data-state={state} data-paused={takeoverPaused||pausing||reduced||!visible||!active}>
  <header className="status-header"><Link to="/workbench" className="status-brand"><span className="status-brand-symbol" aria-hidden="true">s<span>o</span></span><span>{t('brand')}</span></Link><div className="status-header-actions">
   {stores.length>1&&<label className="status-store"><span>{t('store')}</span><select aria-label={t('store')} value={store} onChange={e=>onStore(e.target.value)}>{stores.map((s,i)=><option key={s.store_id} value={s.store_id}>{t('storeNumber',{n:i+1})}</option>)}</select></label>}
   <select className="status-language" aria-label={t('language')} value={locale} onChange={e=>{const v=e.target.value as 'en'|'zh-CN';setLocale(v);try{localStorage.setItem('store.status.locale',v);}catch{}try{history.replaceState(history.state,'',withStatusLanguage(location.href,v));}catch{}}}><option value="en">EN</option><option value="zh-CN">中文</option></select>
   <details className="status-menu"><summary aria-label={t('showMenu')}><SlidersHorizontal size={18}/></summary><nav>{canInspect&&<><Link to="/dashboard">{t('details')}<ArrowUpRight size={13}/></Link><Link to="/tools">{t('tools')}<ArrowUpRight size={13}/></Link></>}{!demo&&<Link to="/console">{t('conversation')}<ArrowUpRight size={13}/></Link>}{onSettings&&<button onClick={onSettings}>{t('settings')}</button>}{onLogout&&<button onClick={onLogout}>{t('logout')}</button>}</nav></details>
  </div></header>
  {demo&&<aside className="status-demo"><span>{t('demo')}</span><p>{t('demoNote')}</p></aside>}
  <section className="status-hero"><div className="status-forward-wrap"><button type="button" className="status-forward" aria-label={t(control?.paused?'resumeTakeover':'pauseTakeover')} aria-pressed={!!control?.paused} aria-busy={controlPending} disabled={controlPending||(!demo&&(!onControl||!control))} title={t(control?.paused?'resumeTakeover':'pauseTakeover')} onClick={()=>{if(demo)setPaused(v=>!v);else onControl?.(!control?.paused);}} data-resting={takeoverPaused||reduced||!visible||!active}>
    {takeoverPaused?<Pause className="status-forward-paused" size={62} strokeWidth={1.7}/>:<svg viewBox="0 0 160 100" aria-hidden="true"><defs><linearGradient id="status-forward-fill" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#a3c9b3"/><stop offset="1" stopColor="#386f5d"/></linearGradient></defs><path className="status-forward-arrow" d="M24 16 Q20 13 20 19 V81 Q20 87 25 84 L74 54 Q80 50 74 46 Z"/><path className="status-forward-arrow" d="M82 16 Q78 13 78 19 V81 Q78 87 83 84 L132 54 Q138 50 132 46 Z"/></svg>}
   </button></div>
   {!demo&&<div className="status-title-line"><span className={'status-indicator status-indicator-'+state}/><span>{state==='working'&&!control?.paused?'LIVE':data?.platform_label||'store-ops'}</span></div>}
   <h1>{t(title)}</h1><p className="status-hero-description" key={action}>{t(action)}</p>
   {controlError&&<p className="status-control-error" role="alert">{t('controlError')}</p>}
   {error&&<button className="status-primary" onClick={onRefresh}>{t('refresh')}<ChevronRight size={16}/></button>}
   {!demo&&data&&['attention','recovery','stale'].includes(state)&&canInspect&&<Link className="status-primary" to={`/emag?store=${encodeURIComponent(store)}`}>{t('openReview')}<ChevronRight size={16}/></Link>}
  </section>
  {data&&!error&&<section className="status-evidence"><div className="status-metrics">{(['products','issues','stock'] as const).map(key=><article key={key}><p>{t(key)}</p><strong aria-label={result.metrics[key]===null?t('unknown'):undefined}>{format(result.metrics[key])}</strong><span className="status-metric-rule"/></article>)}</div>

   {!demo&&<p className="status-source">{t('lastChecked')} {date}{result.stale&&<span>{t('staleBadge')}</span>}</p>}
  </section>}
  {!data&&!loading&&!error&&<p className="status-empty">{t('emptyHelp')}</p>}

 </main>;
}
