export function deriveStatus(data:any,job:any,now?:number):{state:string;action:string;stale:boolean;metrics:{products:number|null;issues:number|null;stock:number|null}};
export function chooseStore(rows:{store_id:string;captured_at?:string}[],preferred:string):string;
export function validMonitoringControl(value:any):boolean;
export function mergeMonitoringControl(current:any,incoming:any):any;

export function browserNotice(task:any,store:string):{message:string;action:string|null}|null;
