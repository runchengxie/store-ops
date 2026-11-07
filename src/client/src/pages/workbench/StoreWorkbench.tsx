import {useAuth} from '../../App';
import {logout} from '../../api/client';
import {openSettings} from '../../components/SettingsDialog';
import StatusWorkbench from './status/StatusWorkbench';

/** Authentication and private settings stay outside the shared demo display. */
export default function StoreWorkbench(){
 const viewer=useAuth();
 return <StatusWorkbench canInspect={viewer.role==='admin'} onSettings={()=>openSettings()} onLogout={()=>{void logout().then(()=>{location.href='/login';});}}/>;
}
