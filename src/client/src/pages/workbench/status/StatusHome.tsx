import {useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {ArrowUpRight,ChevronLeft,ChevronRight,Pause,Play,SlidersHorizontal,Sparkles} from 'lucide-react';
import {deriveStatus} from './data.mjs';
import en from './en.json';import zh from './zh-CN.json';
import './status.css';
type Props={active?:boolean;data:any;job:any;stores:{store_id:string}[];store:string;onStore:(v:string)=>void;loading:boolean;error:string;onRefresh:()=>void;demo?:boolean;onSettings?:()=>void;onLogout?:()=>void;canInspect?:boolean};
export default function StatusHome({data,job,stores,store,onStore,loading,error,onRefresh,demo=false,onSettings,onLogout,canInspect=true,active=true}:Props){
 const [locale,setLocale]=useState<'en'|'zh-CN'>(()=>{try{return localStorage.getItem('store.status.locale')==='zh-CN'?'zh-CN':'en';}catch{return 'en';}});
 const c:Record<string,string>=locale==='en'?en:zh;const t=(key:string,values:Record<string,string|number>={})=>Object.entries(values).reduce((s,[k,v])=>s.replaceAll('{'+k+'}',String(v)),c[key]||key);
 const [index,setIndex]=useState(0),[paused,setPaused]=useState(false),[reduced,setReduced]=useState(()=>window.matchMedia('(prefers-reduced-motion: reduce)').matches),[visible,setVisible]=useState(!document.hidden),[,setNow]=useState(Date.now());
 useEffect(()=>{const media=window.matchMedia('(prefers-reduced-motion: reduce)');const update=()=>setReduced(media.matches);const visibility=()=>{setVisible(!document.hidden);setNow(Date.now());};media.addEventListener('change',update);document.addEventListener('visibilitychange',visibility);return()=>{media.removeEventListener('change',update);document.removeEventListener('visibilitychange',visibility);};},[]);
 useEffect(()=>{setIndex(0);},[store]);
 useEffect(()=>{if(!visible||!active)return;setNow(Date.now());const timer=setInterval(()=>setNow(Date.now()),10000);return()=>clearInterval(timer);},[visible,active]);
 const slides=demo?['readProducts','checkPrices','checkStock','prepareReview']:['factsProducts','factsIssues','factsStock'];
 useEffect(()=>{if(paused||reduced||!visible||!active||!data)return;const timer=setInterval(()=>setIndex(i=>(i+1)%slides.length),6000);return()=>clearInterval(timer);},[paused,reduced,visible,active,!!data,demo,slides.length]);
 const result=deriveStatus(data,job,Date.now());const state=error?'offline':loading&&!data?'loading':result.state;
 const title=demo?'demoTitle':state;const action=demo?slides[index]:error?'offlineAction':loading&&!data?'loadingAction':result.action;
 const format=(value:number|null)=>value===null?'—':new Intl.NumberFormat(locale).format(value);
 let date=t('unknown');if(data&&Number.isFinite(Date.parse(data.captured_at)))date=new Intl.DateTimeFormat(locale,{dateStyle:'medium',timeStyle:'short',timeZone:'Europe/Bucharest'}).format(new Date(data.captured_at));
 return <main className="status-home" data-testid="status-home" data-state={state} data-paused={paused||reduced||!visible||!active}>
  <header className="status-header"><Link to="/workbench" className="status-brand"><span className="status-brand-symbol" aria-hidden="true">s<span>o</span></span><span>{t('brand')}</span></Link><div className="status-header-actions">
   {stores.length>1&&<label className="status-store"><span>{t('store')}</span><select aria-label={t('store')} value={store} onChange={e=>onStore(e.target.value)}>{stores.map((s,i)=><option key={s.store_id} value={s.store_id}>{t('storeNumber',{n:i+1})}</option>)}</select></label>}
   <select className="status-language" aria-label={t('language')} value={locale} onChange={e=>{const v=e.target.value as 'en'|'zh-CN';setLocale(v);try{localStorage.setItem('store.status.locale',v);}catch{}}}><option value="en">EN</option><option value="zh-CN">中文</option></select>
   <details className="status-menu"><summary aria-label={t('showMenu')}><SlidersHorizontal size={18}/></summary><nav>{canInspect&&<><Link to="/dashboard">{t('details')}<ArrowUpRight size={13}/></Link><Link to="/tools">{t('tools')}<ArrowUpRight size={13}/></Link></>}{!demo&&<Link to="/console">{t('conversation')}<ArrowUpRight size={13}/></Link>}{onSettings&&<button onClick={onSettings}>{t('settings')}</button>}{onLogout&&<button onClick={onLogout}>{t('logout')}</button>}</nav></details>
  </div></header>
  {demo&&<aside className="status-demo"><span>{t('demo')}</span><p>{t('demoNote')}</p></aside>}
  <section className="status-hero"><p className="status-eyebrow">{t('eyebrow')}</p><div className={'status-orb '+(demo||state==='working'?'status-orb-active':'')} aria-hidden="true"><div className="status-orb-halo"/><div className="status-orb-core"><span/><span/><span/></div><div className="status-orb-satellite"/></div>
   <div className="status-title-line"><span className={'status-indicator status-indicator-'+state}/><span>{demo?'DEMO':state==='working'?'LIVE':'eMAG'}</span></div>
   <h1>{t(title)}</h1><p className="status-hero-description" key={action}>{t(action)}</p>
   {error&&<button className="status-primary" onClick={onRefresh}>{t('refresh')}<ChevronRight size={16}/></button>}
   {!demo&&data&&['attention','recovery','stale'].includes(state)&&canInspect&&<Link className="status-primary" to={`/emag?store=${encodeURIComponent(store)}`}>{t('openReview')}<ChevronRight size={16}/></Link>}
  </section>
  {data&&!error&&<section className="status-evidence"><div className="status-metrics">{(['products','issues','stock'] as const).map(key=><article key={key}><p>{t(key)}</p><strong aria-label={result.metrics[key]===null?t('unknown'):undefined}>{format(result.metrics[key])}</strong><span className="status-metric-rule"/></article>)}</div>
   <div className="status-carousel" aria-label={t('latest')}><div className="status-carousel-icon"><Sparkles size={21}/></div><div className="status-slide" key={index}><p className="status-slide-kicker">{demo?t('step',{n:index+1,total:slides.length}):t('latest')}</p><h2>{t(slides[index])}</h2><p>{t(slides[index]+'Body')}</p></div><div className="status-carousel-controls"><button aria-label={t('previous')} onClick={()=>{setPaused(true);setIndex(i=>(i+slides.length-1)%slides.length);}}><ChevronLeft size={16}/></button><button aria-label={paused?t('play'):t('pause')} aria-pressed={paused||reduced} disabled={reduced} onClick={()=>setPaused(v=>!v)}>{paused||reduced?<Play size={15}/>:<Pause size={15}/>}</button><button aria-label={t('next')} onClick={()=>{setPaused(true);setIndex(i=>(i+1)%slides.length);}}><ChevronRight size={16}/></button></div></div>
   <p className="status-source">{!demo&&<>{t('lastChecked')} {date} · </>}{t('notLive')}{!demo&&result.stale&&<span>{t('staleBadge')}</span>}</p>
  </section>}
  {!data&&!loading&&!error&&<p className="status-empty">{t('emptyHelp')}</p>}
  <footer className="status-footer"><span>{t('safe')}</span><span>{t('footer')}</span></footer>
 </main>;
}
