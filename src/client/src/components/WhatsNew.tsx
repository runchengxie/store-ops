import type { ReactNode } from "react";
import AppDialog from "./AppDialog";

export type Release = {
  /** 公告 id。一经发布不要改 —— 它就是"看过没有"的那把钥匙。 */
  id: string;
  title: string;
  date: string;
  /** true = 只弹给管理员（讲的是管理员才看得到的板块）。 */
  adminOnly?: boolean;
  body: ReactNode;
};

/** 最新的排在最前。目前只弹最新这一条。 */
export const RELEASES: Release[] = [{
 id: "2026-11-platform-core", title: "店铺工作台与 eMAG 平台能力", date: "2026-11-08", adminOnly: true,
 body: <><p className="wn-lead">店铺工作台按平台读取快照、采集时间和证据版本。当前注册的平台为 eMAG。</p><p>原 Amazon 与领星入口已下线。历史记录和私有配置保留；明确引用已下线能力的任务会在分发前停止。</p></>,
}];

const LS_KEY = "ivyea-ops.whatsnew";

/**
 * 这个浏览器以前用过这个站吗？
 *
 * 用来把"升级上来的老用户"和"刚装好第一次打开"分开。判据是这个站自己写下的那些
 * 使用痕迹 —— 主题、上次停在哪个标签、看过哪些引导、领星板块的界面状态。
 * 任意一个存在，就说明这不是第一次打开。
 *
 * **宁可漏弹也不要误弹**：清过站点数据、换了浏览器的老用户会被当成新用户而错过这
 * 条通知，代价是他自己去驾驶舱里找一下；反过来给全新安装的人开局甩一个必须点掉的
 * 弹窗，代价是第一印象。
 */
function looksLikeReturningUser(): boolean {
  const marks = [
    "ivyea-ops-home-tab",      // 用过驾驶舱
    "ivyea-ops.theme",         // 换过主题
    "ivyea-ops.shell",         // 切过外壳模式
    "ivyea-tour:/dashboard",   // 看过驾驶舱引导
    "ivyea-tour:/console",     // 看过任务台引导
  ];
  try {
    return marks.some((k) => localStorage.getItem(k) !== null);
  } catch {
    return false;   // 读不到 localStorage（隐私模式）→ 当作新用户，不打扰
  }
}

function readSeen(): string[] {
  try { return JSON.parse(localStorage.getItem(LS_KEY) || "[]"); } catch { return []; }
}

function markSeen(id: string): void {
  try {
    const seen = readSeen();
    if (!seen.includes(id)) localStorage.setItem(LS_KEY, JSON.stringify([...seen, id]));
  } catch { /* 写不进去就下次再弹，不影响使用 */ }
}

/**
 * 现在该弹哪一条？没有就返回 null。
 *
 * 全新安装时**不弹但要记成已读** —— 否则等他用一阵子、浏览器里有了痕迹之后，
 * 这条早就过时的搬家通知会突然冒出来。
 */
export function pendingRelease(isAdmin: boolean): Release | null {
  const seen = readSeen();
  const candidates = RELEASES.filter((r) => !seen.includes(r.id) && (!r.adminOnly || isAdmin));
  if (candidates.length === 0) return null;
  if (!looksLikeReturningUser()) {
    for (const r of candidates) markSeen(r.id);
    return null;
  }
  return candidates[0];
}

export default function WhatsNew({ release, onClose }: { release: Release; onClose: () => void }) {
  const done = () => { markSeen(release.id); onClose(); };
  return (
    <AppDialog title={release.title} icon="✦" width={680} dismissible={false} onClose={done}>
      {/* 正文自己滚，按钮固定在下边 —— **这不是排版偏好，是能不能关掉的问题**：
          .app-dialog-body 是 overflow:hidden，正文一长就被直接切掉、滚都滚不动，
          而这个弹窗唯一的出口就是那个按钮。 */}
      <div className="wn">
        <div className="wn-scroll">
          <div className="wn-date">更新于 {release.date}</div>
          {release.body}
        </div>
        <div className="wn-actions">
          <button className="cp-btn primary" onClick={done}>知道了</button>
        </div>
      </div>
    </AppDialog>
  );
}
