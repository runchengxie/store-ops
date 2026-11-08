import {useEffect,useRef,useState} from 'react';
import StatusHome from './StatusHome';
import {useLocation,useSearchParams} from 'react-router-dom';
import {chooseStore,validMonitoringControl,mergeMonitoringControl} from './data.mjs';
import {api} from '../../../api/client';
type Props={demo?:boolean;onSettings?:()=>void;onLogout?:()=>void;canInspect?:boolean};
export default function StatusWorkbench({demo=false,...props}:Props){
 const [query]=useSearchParams();const location=useLocation();const enabled=location.pathname==='/workbench';
 const [stores,setStores]=useState<{store_id:string}[]>([]),[store,setStore]=useState(query.get('store')||''),[data,setData]=useState<any>(null),[job,setJob]=useState<any>(null),[listError,setListError]=useState(''),[error,setError]=useState(''),[loading,setLoading]=useState(true),[refresh,setRefresh]=useState(0);
 const generation=useRef(0);const controlInFlight=useRef(false);
 const [controlPending,setControlPending]=useState(false),[controlError,setControlError]=useState('');
 async function changeControl(paused:boolean){
  if(controlInFlight.current||!data?.control||data.store_id!==store)return;
  const epoch=generation.current;const selected=store;controlInFlight.current=true;setControlPending(true);setControlError('');
  try{const response=await api.post(`/operations/stores/${encodeURIComponent(selected)}/control`,{paused,revision:data.control.revision});
   if(!validMonitoringControl(response.data))throw Error('Invalid control acknowledgement');
   if(epoch===generation.current)setData((current:any)=>current?.store_id===selected?{...current,control:mergeMonitoringControl(current.control,response.data)}:current);
  }catch{if(epoch===generation.current)setControlError('unavailable');}
  finally{controlInFlight.current=false;setControlPending(false);}
 }
 useEffect(()=>{let alive=true;setLoading(true);setListError('');api.get('/operations/stores').then(r=>{if(!alive)return;if(!Array.isArray(r.data))throw Error('Invalid store list');const rows=r.data.filter((s:any)=>typeof s?.store_id==='string');setStores(rows);setStore(s=>chooseStore(rows,s));if(!rows.length){setData(null);setJob(null);setLoading(false);}}).catch(()=>{if(alive){setStores([]);setStore('');setData(null);setJob(null);setListError('unavailable');setLoading(false);}});return()=>{alive=false;};},[refresh]);
 useEffect(()=>{const epoch=++generation.current;let active=true;let timer:ReturnType<typeof setTimeout>|undefined;let pending=false;const controllers=new Set<AbortController>();setData(null);setJob(null);setError('');setControlError('');
  async function read(){if(!enabled||!store||!active||pending||document.hidden)return;pending=true;setLoading(true);const controller=new AbortController();controllers.add(controller);try{const response=await api.get(`/operations/stores/${encodeURIComponent(store)}/overview`,{signal:controller.signal});if(!active||epoch!==generation.current)return;
   const view=response.data;if(view?.control&&!validMonitoringControl(view.control))throw Error('Invalid control state');if(view?.store_id!==store||typeof view.platform!=='string'||!view.metrics||!Number.isInteger(view.metrics.products)||view.metrics.products<0||!Number.isInteger(view.metrics.issues)||view.metrics.issues<0)throw Error('Invalid evidence');setData((current:any)=>current?.store_id===view.store_id&&current.control?.revision>view.control?.revision?{...view,control:current.control}:view);setJob(view.collection||null);setError('');
  }catch{if(active&&epoch===generation.current){setData(null);setJob(null);setError('unavailable');}}finally{controllers.delete(controller);pending=false;if(active&&epoch===generation.current){setLoading(false);timer=setTimeout(()=>void read(),30000);}}}
  const visibility=()=>{if(document.hidden){clearTimeout(timer);return;}clearTimeout(timer);void read();};
  if(store)void read();else setLoading(false);document.addEventListener('visibilitychange',visibility);
  return()=>{active=false;generation.current++;clearTimeout(timer);controllers.forEach(c=>c.abort());document.removeEventListener('visibilitychange',visibility);};
 },[store,refresh,enabled]);
 useEffect(()=>{if(!enabled||data?.store_id!==store||data?.control?.state!=='pausing')return;
  const epoch=generation.current;let alive=true;let pending=false;const controller=new AbortController();
  const timer=setInterval(async()=>{if(pending||document.hidden)return;pending=true;try{
   const response=await api.get(`/operations/stores/${encodeURIComponent(store)}/overview`,{signal:controller.signal});
   if(!alive||epoch!==generation.current)return;const view=response.data;
   if(view?.store_id!==store||!validMonitoringControl(view.control))throw Error('Invalid control acknowledgement');
   setData((current:any)=>current?.store_id===store&&view.control.revision>=current.control.revision?{...current,control:view.control}:current);setControlError('');
  }catch{if(alive&&epoch===generation.current)setControlError('unavailable');}finally{pending=false;}},2000);
  return()=>{alive=false;clearInterval(timer);controller.abort();};
 },[enabled,store,data?.store_id,data?.control?.state]);
 return <StatusHome {...props} active={enabled} demo={demo} data={data?.store_id===store?data:null} job={job} stores={stores} store={store} onStore={setStore} loading={loading} error={listError||error} onRefresh={()=>setRefresh(v=>v+1)} onControl={changeControl} controlPending={controlPending} controlError={controlError}/>;
}
