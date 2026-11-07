import {useEffect,useRef,useState} from 'react';
import StatusHome from './StatusHome';
import {useLocation,useSearchParams} from 'react-router-dom';
import {chooseStore} from './data.mjs';
import {api} from '../../../api/client';
type Props={demo?:boolean;onSettings?:()=>void;onLogout?:()=>void;canInspect?:boolean};
export default function StatusWorkbench({demo=false,...props}:Props){
 const [query]=useSearchParams();const location=useLocation();const enabled=location.pathname==='/workbench';
 const [stores,setStores]=useState<{store_id:string}[]>([]),[store,setStore]=useState(query.get('store')||''),[data,setData]=useState<any>(null),[job,setJob]=useState<any>(null),[listError,setListError]=useState(''),[error,setError]=useState(''),[loading,setLoading]=useState(true),[refresh,setRefresh]=useState(0);
 const generation=useRef(0);
 useEffect(()=>{let alive=true;setLoading(true);setListError('');api.get('/emag/stores').then(r=>{if(!alive)return;if(!Array.isArray(r.data))throw Error('Invalid store list');const rows=r.data.filter((s:any)=>typeof s?.store_id==='string');setStores(rows);setStore(s=>chooseStore(rows,s));if(!rows.length){setData(null);setJob(null);setLoading(false);}}).catch(()=>{if(alive){setStores([]);setStore('');setData(null);setJob(null);setListError('unavailable');setLoading(false);}});return()=>{alive=false;};},[refresh]);
 useEffect(()=>{const epoch=++generation.current;let active=true;let timer:ReturnType<typeof setTimeout>|undefined;let pending=false;const controllers=new Set<AbortController>();setData(null);setJob(null);setError('');
  async function read(){if(!enabled||!store||!active||pending||document.hidden)return;pending=true;setLoading(true);const controller=new AbortController();controllers.add(controller);try{const root=`/emag/stores/${encodeURIComponent(store)}`;const [workspace,receipt]=await Promise.all([api.get(root+'/workspace',{signal:controller.signal}),api.get(root+'/job',{signal:controller.signal}).catch(e=>{if(e?.response?.status===404)return null;throw e;})]);if(!active||epoch!==generation.current)return;
   if(workspace.data?.store_id!==store||!Array.isArray(workspace.data.offers)||!Array.isArray(workspace.data.issues))throw Error('Invalid evidence');setData(workspace.data);setJob(receipt?.data||null);setError('');
  }catch{if(active&&epoch===generation.current){setData(null);setJob(null);setError('unavailable');}}finally{controllers.delete(controller);pending=false;if(active&&epoch===generation.current){setLoading(false);timer=setTimeout(()=>void read(),30000);}}}
  const visibility=()=>{if(document.hidden){clearTimeout(timer);return;}clearTimeout(timer);void read();};
  if(store)void read();else setLoading(false);document.addEventListener('visibilitychange',visibility);
  return()=>{active=false;generation.current++;clearTimeout(timer);controllers.forEach(c=>c.abort());document.removeEventListener('visibilitychange',visibility);};
 },[store,refresh,enabled]);
 return <StatusHome {...props} active={enabled} demo={demo} data={data?.store_id===store?data:null} job={job} stores={stores} store={store} onStore={setStore} loading={loading} error={listError||error} onRefresh={()=>setRefresh(v=>v+1)}/>;
}
