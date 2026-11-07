import React from 'react';
import ReactDOM from 'react-dom/client';
import { MemoryRouter, NavLink, Navigate, Route, Routes, useLocation, Link } from 'react-router-dom';
import { AxiosError } from 'axios';
import { api } from '../src/api/client';
import EmagOperations from '../src/pages/workbench/EmagOperations';
import EmagWorkspace from '../src/pages/workbench/EmagWorkspace';
import { createDemoState } from './state.mjs';
import './style.css';
import StatusWorkbench from '../src/pages/workbench/status/StatusWorkbench';

const state = createDemoState();
api.defaults.adapter = async config => {
  try {
    const body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data;
    const data = state.request((config.method || 'get').toUpperCase(), config.url || '', body || {});
    return { data, status: 200, statusText: 'OK', headers: {}, config };
  } catch (error) {
    const message = error instanceof Error ? error.message : '演示中无法执行此操作。';
    throw new AxiosError(message, 'ERR_DEMO', config, undefined,
      { data: { detail: message }, status: 409, statusText: 'Demo unavailable', headers: {}, config });
  }
};

const pages = [
  ['/dashboard', '运营驾驶舱', '◫'], ['/emag', 'eMAG 巡检', '◎'],
  ['/market', '市场调研', '⌕'], ['/playbook', '打法推荐', '◇'],
  ['/listing', 'Listing 工作台', '▤'], ['/tools', '分析工具', '▦'],
] as const;

function DemoShell() {
  const location = useLocation();
  const compact = location.pathname === "/workbench";
  return <>
    {compact&&<StatusWorkbench demo />}
    {!compact && <>
    <div className="demo-layout">
      <Link className="demo-return" to="/workbench">← 返回店铺工作台</Link>
      <aside className="demo-sidebar">
        <div className="brand"><span className="brand-mark">i</span><span>ivyeaops<small>模拟工作台</small></span></div>
        <div className="sidebar-label">模拟工作区</div>
        <nav aria-label="演示导航">{pages.map(([path, label, icon]) => <NavLink key={path} to={path} className={({isActive}) => isActive ? 'nav-item active' : 'nav-item'}><span aria-hidden="true">{icon}</span>{label}</NavLink>)}</nav>
        <a className="docs-link" href="../zh-CN/index.html">查看项目文档 ↗</a>
      </aside>
      <div className="demo-body">
        <header className="demo-header"><div><span className="header-kicker">ivyeaops / EMAG</span><strong>运营工作台</strong></div><div className="header-actions"><a href="../zh-CN/index.html">使用文档</a><button onClick={() => window.location.reload()}>重置演示</button></div></header>
        <div className="demo-notice" role="status"><span className="notice-dot"/><div><strong>模拟演示</strong><span>所有商品、订单与操作均为虚构数据。修改只保存在当前页面，刷新即重置。</span></div></div>
        <div className="demo-content"><Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace/>}/>
          <Route path="/emag" element={<EmagOperations/>}/>
          <Route path="/dashboard" element={<EmagWorkspace mode="dashboard"/>}/>
          <Route path="/market" element={<EmagWorkspace mode="market"/>}/>
          <Route path="/playbook" element={<EmagWorkspace mode="playbook"/>}/>
          <Route path="/listing" element={<EmagWorkspace mode="listing"/>}/>
          <Route path="/tools" element={<EmagWorkspace mode="tools"/>}/>
          <Route path="*" element={<Navigate to="/dashboard" replace/>}/>
        </Routes></div>
      </div>
    </div>
    </>}
  </>;
}

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><MemoryRouter initialEntries={['/workbench']}><DemoShell/></MemoryRouter></React.StrictMode>);
