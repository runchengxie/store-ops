import { useLocation, Link } from 'react-router-dom';
const contexts:Record<string,string>={
  '/console':'默认围绕 eMAG RO 证据工作。对话仍需模型；只读 CLI 和 MCP 不依赖本页开启。',
  '/brain':'可保存 eMAG 政策、PNK/SKU、来源链接与时效。新模板按 RO/RON 编写，现有文件保留。',
  '/agents':'连接外部 agent；使用本机 MCP 的店铺快照和巡检回执工具。市场搜索以已注册的平台能力为准。',
  '/terminal':'在 server 目录手动运行 python -m app.emag_job_cli --store-id <店铺标签>；增加 --from-latest 可离线重放。未注册定时任务。',
  '/servmon':'监控本机服务资源，不代表 eMAG 平台或 API 可用性。任务结果请查看分析工具中的巡检回执。',
  '/freight':'请导入目的地为实际 RO 仓库的报价并核对币种、税费与计费重。已有其他国家线路不能作为罗马尼亚运费。',
  '/users':'管理本机工作台用户与权限。eMAG API 凭证独立存储，不通过此处的用户密码管理。',
  '/image-translate':'支持罗马尼亚语、保加利亚语、匈牙利语。需要已配置的图片模型；翻译后人工检查规格与合规文字，不自动上架。',
};
export default function EmagContext(){const {pathname}=useLocation();const text=contexts[pathname];return text?<aside style={{padding:'10px 20px',fontSize:13,lineHeight:1.6,borderBottom:'1px solid var(--border)',overflowWrap:'anywhere'}}>eMAG · {text} <Link to="/emag">店铺证据</Link></aside>:null;}
