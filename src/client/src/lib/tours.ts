import type { TourStep } from "../components/Tour";

/**
 * Interactive tours, keyed by route pathname. Each board's tour auto-runs on the
 * user's first visit (once, remembered in localStorage) and can be replayed via
 * the "?" button in the top bar.
 *
 * Steps target elements by a stable CSS selector (existing class or a
 * `[data-tour="…"]` attribute added on the element); a step without `sel` shows
 * a centered intro card. A selector that matches nothing also renders centered,
 * so steps degrade gracefully.
 *
 * To add a board: add an entry here (+ tag its key element with `data-tour="…"`
 * if it has no stable class).
 */
// 运营驾驶舱的引导。地址从 "/" 搬到了 /dashboard（"/" 现在只做落地分流），
// 两个键都指向同一份步骤，老的 "已看过" 记录也就继续有效。
const DASHBOARD_TOUR: TourStep[] = [
 { title: "store-ops 店铺证据", body: "选择店铺后查看快照、采集时间、来源与限制。未知字段不等于零。" },
];

export const TOURS: Record<string, TourStep[]> = {
  // ── 任务台 ────────────────────────────────────────────────────────────────
  "/console": [
    {
      title: "任务台 · 一个入口把活派出去",
      body: "不用再想「这件事该去哪个板块」。直接说需求，Ivyea 会自己挑技能、调板块能力去拿真实数据，再把结论给你。",
    },
    { sel: ".cc-scenes", title: "不知道说什么？点场景", body: "这些是常见的开场，点一下就把提示词填进输入框，改改就能发。" },
    { sel: ".cc-bar", title: "输入框下面这一行是真开关", body: "工作区 / 审批档位 / 模型，选了就真的按那个跑。审批分三档：默认「只读」只分析绝不动数据；「审批放行」每次写入弹确认卡；「完全放行」这一轮直接执行。技能按对话自动匹配，不用挑。" },
    { sel: '[data-tour="console-new"]', title: "开新任务", body: "换个话题就点「新建任务」，上一轮的上下文不会串进来。" },
    { title: "问答和作图也在这里", body: "不需要工具的纯写作/问答直接问就行。说「画一张主图」会自动调生图链路，出的图就显示在回答里；贴一张图再说怎么改，就是在你这张图上改图。点回答里的图可以拿它接着改。" },
  ],

  // ── 能力市场 ──────────────────────────────────────────────────────────────
  "/capabilities": [
    { title: "能力市场", body: "Agent 能用什么，都摊在这一页：技能、社区市场、MCP、智能体、授权。看得见才谈得上组合。" },
    { sel: ".home-tabs", title: "五类能力", body: "技能=可复用的做法（原「Skill 中心」已并进来）；社区市场=别人做好的方法装过来；MCP=连数据和工具的通道；智能体=主脑模型；授权=数据源密钥状态。" },
    { sel: ".cap-seg", title: "技能的三个动作", body: "同一批技能，三件事：「运行」填参数就跑、「创建」一句话生成、「管理」编辑文件和快照。以前这三块在单独的 Skill 中心里，同一批技能被列了三遍。" },
    { title: "用起来", body: "Agent 内置技能点「在任务台用」会带着它跳回任务台并预选好；自己的技能在「运行」里直接填参数执行。" },
  ],

  // ── 定时任务 ──────────────────────────────────────────────────────────────
  "/schedules": [
    { title: "eMAG 计划准备", body: "当前先手动运行。这里提供最近巡检回执、手动 CLI 命令和未来节奏预览，不会注册或启用自动任务。" },
    { title: "先核对时间", body: "cron 预览使用服务器时区，不能按浏览器时区或罗马尼亚时间直接理解。示例每天09:00还没有被启用。" },
    { title: "下载只是草稿", body: "导出的 JSON 固定停用、未注册；当前没有连接执行该草稿的调度器。离线重放不等于新采集。" },
    { title: "原 Agent 调度器", body: "通用 Agent 任务保留在另一标签，需要可用的模型/Agent；已有任务状态不变，新建表单默认停用。" },
  ],

  // ── 控制台总览（运营驾驶舱）───────────────────────────────────────────────
  "/dashboard": DASHBOARD_TOUR,
  // "/" 现在只是按外壳模式分流的落地跳转，几乎停不住；键留着是为了老的
  // "已看过" 记录（ivyea-tour:/）仍然有效。**必须和 /dashboard 共用同一份步骤** ——
  // 这里以前是手抄的第二份，于是驾驶舱改版之后它还在讲"五个标签页"。
  "/": DASHBOARD_TOUR,

  // ── 系统配置 ───────────────────────────────────────────────────────────────
  "/hub-settings": [
    { title: "系统配置：全站的总开关", body: "这里集中配置模型、数据源、集成路径等。每个区块独立保存，点该区块的「保存」即时生效。新用户重点看下面两处。" },
    { sel: '[data-tour="settings-fallback"]', title: "★ 全局兜底大模型（最重要）", body: "所有板块文本 AI 的统一出口。选一个 provider（推荐 DeepSeek：快、便宜、国内直连）+ 填 Key，全站 AI 立即可用。" },
    { sel: '[data-tour="settings-health"]', title: "健康检查", body: "一眼看清各服务与 AI 链的就绪状态（文本链 / 全局兜底 / 视觉）。配完回这里确认对应项变绿即可。" },
  ],

  // ── 市场调研 ───────────────────────────────────────────────────────────────
  "/market": [{ title: "市场调研", body: "区分本店商品分布与市场需求，记录来源、样本范围和不确定性。" }],

  // ── Listing 工作台 ───────────────────────────────────────────────────────────
  "/listing": [{ title: "Listing 草稿", body: "依据已验证的商品资料生成本地草稿，未核实规格与认证保持未知。" }],

  // ── 打法推荐 ───────────────────────────────────────────────────────────────
  "/playbook": [{ title: "处理计划", body: "按证据版本和异常制定核查计划，采购成本缺失时不推荐售价。" }],

  // ── 分析工具 ───────────────────────────────────────────────────────────────
  "/tools": [{ title: "数据质量分析", body: "检查快照缺失字段、未知库存和巡检回执。" }],

  // 板块已并入运营驾驶舱，这三步的内容并进了 DASHBOARD_TOUR。这里不能留一个

  // ── Skill 中心 ───────────────────────────────────────────────────────────────
  // Skill 中心的引导并进了能力市场（见 "/capabilities"）。

  // AI 问答 / AI 生图的引导跟着板块一起并进了任务台（见 "/console"）。

  // ── 智能体会话 ───────────────────────────────────────────────────────────────
  "/agents": [
    { title: "外部智能体", body: "这里保留 Claude Code / Hermes / Codex 等外部 CLI 的完整会话界面：多会话、流式输出、工具可视化、文件上传（≤300MB）、resume。" },
    { title: "怎么用", body: "左侧新建 / 切换会话，顶部选 provider（claude / hermes / codex），底部输入框发消息。默认 IvyeaAgent 会话和知识库在右下角常驻图标里。" },
    { title: "前提", body: "外部 CLI 是可选增强项；新部署不再要求安装 Hermes/GBrain/Ollama。" },
  ],

  // ── 知识库工作台 ─────────────────────────────────────────────────────────────
  "/brain": [
    { title: "知识库工作台", body: "上传、粘贴、URL 入库、编辑、搜索，以及基于知识库的对话。" },
    { sel: ".tabs", title: "功能标签", body: "对话 / 上传 / 搜索 / 页面 / 模板 / 概览 / 设置。右下角 IvyeaAgent 知识库页可把 ~/brain 迁移到 ~/.ivyea/knowledge。" },
    { title: "配置", body: "不需要任何配置——知识库由内置的 IvyeaAgent 提供，装完即用，语义检索也是自带的。" },
  ],

  // ── 服务器终端 ───────────────────────────────────────────────────────────────
  "/terminal": [
    { title: "服务器终端", body: "浏览器内的真实 PTY 终端，直接在服务器上敲命令。仅管理员、谨慎授权。（仅 Linux；Windows 不支持 PTY。）" },
    { sel: ".terminal-session-list", title: "终端列表", body: "左侧是终端会话列表，可新建 / 切换多终端。" },
    { sel: ".terminal-main", title: "主终端", body: "中间是主终端画面；右侧支持会话快照（定时抓取 tmux 画面，断线也能回看）。" },
  ],

  // ── 服务器监控 ───────────────────────────────────────────────────────────────
  "/servmon": [
    { title: "服务器监控", body: "查看服务器 CPU / 内存 / 磁盘 / 流量 / 进程占用，可对高占用进程执行停止。" },
    { sel: ".proc-table-wrap", title: "进程列表", body: "按占用排序的进程表。对高占用进程可停止——会先提示影响并二次确认，避免误杀。" },
  ],

  // ── 头程比价 ───────────────────────────────────────────────────────────────────
  "/freight": [
    { title: "头程比价", body: "上传货代头程报价 Excel，自动解析成统一表格做横向比价。纯解析、不使用 AI。" },
    { sel: ".fq-input", title: "查仓库报价", body: "上传报价文件后，在这里按仓库代码（如 ONT8）查询，横向对比各货代的头程价格。" },
  ],

  // ── 用户管理 ───────────────────────────────────────────────────────────────────
  "/users": [
    { title: "用户管理", body: "多用户与 RBAC：新增 / 禁用用户、重置密码、按板块授权（带 🔒 的板块默认仅管理员，可在此逐项开放给指定用户）。" },
    { sel: ".cat-table-wrap", title: "用户列表 & 授权", body: "这里列出所有用户。新增用户后，可逐板块勾选授予其访问权限。" },
  ],

  // ── 资讯 ───────────────────────────────────────────────────────────────────────
  "/news": [
    { title: "资讯", body: "每日「AI 行业 + 亚马逊卖家」资讯摘要：现场抓 RSS 源 + 标准 AI 链生成中文摘要（重要度、官方标记、标签），无需外部 cron。" },
    { sel: '[data-tour="news-refresh"]', title: "立即刷新", body: "点这里现场抓取并生成当日摘要。RSS 源可在「系统配置 → 高级 → 资讯 RSS 源」自定义；需至少一个可用文本 AI。" },
  ],
};

/** Whether a board at `pathname` has a tour. */
export function hasTour(pathname: string): boolean {
  return Array.isArray(TOURS[pathname]) && TOURS[pathname].length > 0;
}
