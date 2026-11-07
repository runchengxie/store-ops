import axios from "axios";

export const api = axios.create({
  baseURL: "/api",
  withCredentials: true,
  timeout: 30000,
});

// If a request returns 401, redirect to login.
api.interceptors.response.use(
  (resp) => resp,
  (err) => {
    if (err.response && err.response.status === 401) {
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    // Auto bug-fix hook: a 5xx means a feature/tool operation failed on the
    // server. Hand it to the repair sink (a no-op unless the feature is on for
    // an admin). Lazy import to avoid a load-order cycle with autofix.ts.
    const status = err.response?.status;
    if (status && status >= 500) {
      import("./autofix").then(({ reportApiError }) => {
        reportApiError({
          endpoint: err.config?.url || "",
          method: (err.config?.method || "").toUpperCase(),
          status,
          detail:
            err.response?.data?.detail ||
            (typeof err.response?.data === "string" ? err.response.data : "") ||
            err.message ||
            "",
        });
      });
    }
    return Promise.reject(err);
  },
);

export type AuthUser = { username: string; role: "admin" | "user"; permissions?: string[]; position?: string };

export async function login(username: string, password: string) {
  const { data } = await api.post<AuthUser>("/auth/login", { username, password });
  return data;
}

export async function register(email: string, password: string) {
  const { data } = await api.post<{ ok: boolean; message: string }>("/auth/register", { email, password });
  return data;
}

export async function logout() {
  await api.post("/auth/logout");
}

export async function me() {
  const { data } = await api.get<AuthUser>("/auth/me");
  return data;
}

// --- Admin: user management ---

export type ManagedUser = {
  id: number;
  email: string;
  role: string;
  status: "pending" | "active" | "suspended";
  created_at: number;
  approved_at: number | null;
  position?: string;
  permissions?: string[];
};

export type PermModule = { key: string; label: string; sensitive: boolean };
export type PermissionsCatalog = { modules: PermModule[]; positions: Record<string, string[]> };

/**
 * 保证"该是数组的就是数组"。
 *
 * 后端正常时当然是数组，但**降级路径、代理错误页、鉴权跳转**都可能塞回别的东西 ——
 * 而调用方紧接着就是 `.map` / `.filter` / `.length`，一炸就被错误边界换成整页
 * 「页面渲染出错」，只能刷新。用户报的"偶尔渲染失败"就是这一类。
 * 收在 API 层比在每个页面里各写一遍 `?? []` 可靠：新页面天然就是安全的。
 */
function asArray<T>(v: unknown): T[] {
  return Array.isArray(v) ? (v as T[]) : [];
}

export async function adminListUsers() {
  const { data } = await api.get<ManagedUser[]>("/auth/admin/users");
  return asArray<ManagedUser>(data);
}

export async function adminSetUserStatus(uid: number, status: "active" | "suspended" | "pending") {
  const { data } = await api.post(`/auth/admin/users/${uid}/status`, { status });
  return data;
}

export async function adminResetUserPassword(uid: number, newPassword: string) {
  const { data } = await api.post(`/auth/admin/users/${uid}/reset-password`, { new_password: newPassword });
  return data;
}

export async function adminDeleteUser(uid: number) {
  const { data } = await api.delete(`/auth/admin/users/${uid}`);
  return data;
}

export async function adminPermissionsCatalog() {
  const { data } = await api.get<PermissionsCatalog>("/auth/admin/permissions-catalog");
  return data;
}

export async function adminSetUserPermissions(uid: number, position: string, permissions: string[]) {
  const { data } = await api.post(`/auth/admin/users/${uid}/permissions`, { position, permissions });
  return data as { ok: boolean; position: string; permissions: string[] };
}

export type MonitorSnapshot = {
  cpu: {
    percent: number;
    count: number;
    load_1m: number;
    load_5m: number;
    load_15m: number;
  };
  memory: {
    total: number;
    used: number;
    available: number;
    percent: number;
    percent_used_raw: number;
  };
  disk: {
    total: number;
    used: number;
    free: number;
    percent: number;
    total_hardware: number;
    percent_hardware: number;
    mount: string;
  };
  network: {
    bytes_sent_total: number;
    bytes_recv_total: number;
    bytes_sent_rate: number;
    bytes_recv_rate: number;
    interface: string;
  };
  uptime_seconds: number;
};

export type ServiceStatus = {
  name: string;
  active: boolean;
  sub_state?: string;
  description: string;
  category: "critical" | "on-demand" | "optional";
  impact: string;
};

export async function monitorSnapshot() {
  const { data } = await api.get<MonitorSnapshot>("/monitor/snapshot");
  return data;
}

export async function monitorServices() {
  const { data } = await api.get<ServiceStatus[]>("/monitor/services");
  return data;
}

export async function monitorLogs(n = 20) {
  const { data } = await api.get<{ lines: string[] }>("/monitor/logs", { params: { n } });
  return data;
}

// --- Process Management ---

export type ProcessInfo = {
  pid: number;
  name: string;
  status: string;
  cpu_percent: number;
  memory_percent: number;
  memory_mb: number;
  cpu_time: number;
  description: string;
  category: "critical" | "on-demand" | "optional";
  impact: string;
  can_stop: boolean;
  username: string;
  service?: string;
};

export async function monitorProcesses() {
  const { data } = await api.get<ProcessInfo[]>("/monitor/processes");
  return asArray<ProcessInfo>(data);
}

export async function stopProcess(pid?: number, service?: string) {
  const { data } = await api.post<{ ok: boolean; error?: string }>("/monitor/processes/stop", { pid, service });
  return data;
}

export async function startProcess(service: string) {
  const { data } = await api.post<{ ok: boolean; error?: string }>("/monitor/processes/start", { service });
  return data;
}

// --- GBrain knowledge base ---

export type BrainStats = {
  raw: string;
  pages: number;
  chunks: number;
  embedded: number;
  links: number;
  tags: number;
  timeline: number;
  by_type: Record<string, number>;
};

export type BrainOverview = {
  brain_root: string;
  gbrain_bin: string;
  openai_configured: boolean;   // back-compat: now true for any configured embedding provider
  embed_configured?: boolean;
  embed_provider?: string;       // "ollama" | "zhipu" | "openai" | ...
  embed_model?: string;          // provider:model
  search_mode: string;
  doctor_status: string;
  git_dirty: boolean;
  git_status: string;
  stats: BrainStats;
  ready?: {
    db_ready: boolean;
    embed_ready: boolean;
    version_compatible: boolean;
    actions: string[];
    hint: string;
  };
};

export type BrainSearchItem = {
  score: number;
  slug: string;
  snippet: string;
};

export type BrainSearchResponse = {
  query: string;
  mode: "search" | "query";
  raw: string;
  items: BrainSearchItem[];
};

export type BrainFileItem = {
  path: string;
  name: string;
  size: number;
  mtime: number;
  category: string;
  summary: string;
};

export type BrainFilesResponse = {
  root: string;
  total: number;
  files: BrainFileItem[];
};

export async function brainOverview() {
  const { data } = await api.get<BrainOverview>("/brain/overview");
  return data;
}

export async function brainDoctor() {
  const { data } = await api.get<any>("/brain/doctor", { timeout: 120000 });
  return data;
}

export async function brainSearch(query: string, mode: "search" | "query" = "search") {
  const { data } = await api.post<BrainSearchResponse>(
    "/brain/search",
    { query, mode },
    { timeout: 90000 },
  );
  return data;
}

export async function brainGetPage(slug: string) {
  const { data } = await api.post<{ slug: string; content: string }>("/brain/page", { slug });
  return data;
}

export async function brainFiles() {
  const { data } = await api.get<BrainFilesResponse>("/brain/files");
  return data;
}

export async function brainFileRead(path: string) {
  const { data } = await api.get<{ path: string; content: string; size: number }>(
    "/brain/file",
    { params: { path } },
  );
  return data;
}

export async function brainFileWrite(path: string, content: string) {
  const { data } = await api.put<{ ok: boolean; path: string; size: number }>(
    "/brain/file",
    { path, content },
  );
  return data;
}

export async function brainFileDelete(path: string) {
  const { data } = await api.delete<{ ok: boolean; path: string }>("/brain/file", { params: { path } });
  return data;
}

export async function brainImport() {
  const { data } = await api.post<{ ok: boolean; raw: string; git_status: string }>(
    "/brain/import",
    {},
    { timeout: 180000 },
  );
  return data;
}

export type BrainUploadItem = {
  id: string;
  source_file: string;
  saved_path: string;
  category: string;
  size: number;
  import_status: string;
  warnings: string[];
  created_at: string;
};

export type BrainUploadResponse = {
  id: string;
  saved_path: string;
  category: string;
  size: number;
  analysis?: {
    title: string;
    directory: string;
    tags: string[];
    summary: string;
    content_type: string;
    confidence: number;
    source: string;
    warnings?: string[];
  };
  markdown_preview?: string;
  import_status: string;
  import_raw?: string;
  warnings?: string[];
  card_id?: string;
  source?: string;
};

export async function brainUpload(file: File, category: string, title: string, importAfterSave = true) {
  const form = new FormData();
  form.append("file", file);
  form.append("category", category);
  form.append("title", title);
  form.append("import_after_save", String(importAfterSave));
  const { data } = await api.post<BrainUploadResponse>("/brain/upload", form, {
    timeout: 180000,
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function brainIngestText(text: string, importAfterSave = true) {
  const { data } = await api.post<BrainUploadResponse>(
    "/brain/ingest/text",
    { text, import_after_save: importAfterSave },
    { timeout: 180000 },
  );
  return data;
}

export async function brainIngestUrl(url: string, importAfterSave = true) {
  const { data } = await api.post<BrainUploadResponse>(
    "/brain/ingest/url",
    { url, import_after_save: importAfterSave },
    { timeout: 300000 },  // fetch + one model round-trip can run long on big pages
  );
  return data;
}

export async function brainUploads(limit = 50) {
  const { data } = await api.get<{ uploads: BrainUploadItem[] }>("/brain/uploads", { params: { limit } });
  return data;
}

export type BrainChatStatus = {
  configured: boolean;
  provider: string;
  base_url: string;
  model: string;
  hermes_bin?: string;
  mode?: string;
};

export type BrainChatSession = {
  id: string;
  title: string;
  mode: "knowledge" | "general" | string;
  created_at: string;
  updated_at: string;
  archived: boolean;
  last_message_preview: string;
};

export type BrainChatMessage = {
  id: string;
  session_id: string;
  role: "user" | "assistant" | "system" | string;
  content: string;
  citations: BrainSearchItem[];
  created_at: string;
};

export async function brainChatStatus() {
  const { data } = await api.get<BrainChatStatus>("/brain/chat/status");
  return data;
}

// One-time, idempotent migration of legacy brain_chat transcripts into the
// agent's native session store, so the dock and the workbench chat share one
// history. Safe to call on every chat mount.
export async function brainChatMigrateToAgent() {
  const { data } = await api.post<{ ok: boolean; migrated: number; skipped: number; total: number }>(
    "/brain/chat/migrate-to-agent", {}, { timeout: 120000 },
  );
  return data;
}

export async function brainChatSessions() {
  const { data } = await api.get<{ sessions: BrainChatSession[] }>("/brain/chat/sessions");
  return data;
}

export async function brainChatCreate(title?: string, mode: "knowledge" | "general" = "knowledge") {
  const { data } = await api.post<{ session: BrainChatSession; messages: BrainChatMessage[] }>("/brain/chat/sessions", { title, mode });
  return data;
}

export async function brainChatGet(sessionId: string) {
  const { data } = await api.get<{ session: BrainChatSession; messages: BrainChatMessage[] }>(`/brain/chat/sessions/${sessionId}`);
  return data;
}

export async function brainChatUpdate(sessionId: string, body: { title?: string; archived?: boolean }) {
  const { data } = await api.patch<{ session: BrainChatSession; messages: BrainChatMessage[] }>(`/brain/chat/sessions/${sessionId}`, body);
  return data;
}

export async function brainChatSend(sessionId: string, content: string) {
  const { data } = await api.post<{
    user_message: BrainChatMessage;
    assistant_message: BrainChatMessage;
    citations: BrainSearchItem[];
    model: BrainChatStatus;
  }>(`/brain/chat/sessions/${sessionId}/messages`, { content }, { timeout: 240000 });
  return data;
}

export type BrainChatStreamEvent =
  | { type: "start"; user_message: BrainChatMessage | null; citations: BrainSearchItem[]; regenerated: boolean }
  | { type: "token"; text: string }
  | { type: "done"; assistant_message: BrainChatMessage; truncated?: boolean; engine?: string; citations_count?: number }
  | { type: "error"; detail: string };

/** Stream a hermes answer over SSE. Calls onEvent for each event; resolves when the stream ends. */
export async function brainChatSendStream(
  sessionId: string,
  body: { content?: string; regenerate?: boolean; category?: string | null },
  onEvent: (evt: BrainChatStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch(`/api/brain/chat/sessions/${encodeURIComponent(sessionId)}/messages/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ content: body.content ?? "", regenerate: body.regenerate ?? false, category: body.category ?? null }),
    signal,
  });
  if (!resp.ok || !resp.body) {
    const text = await resp.text().catch(() => "");
    throw new Error(`HTTP ${resp.status}: ${text}`);
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      try {
        onEvent(JSON.parse(line.slice(5).trim()) as BrainChatStreamEvent);
      } catch {
        /* ignore malformed / heartbeat */
      }
    }
  }
}

export async function brainChatDeleteMessage(messageId: string) {
  const { data } = await api.delete<{ deleted: boolean; id: string }>(`/brain/chat/messages/${encodeURIComponent(messageId)}`);
  return data;
}

// --- Token Usage ---

/** total_tokens = 输入 + 输出 + 缓存读 + 缓存写。缓存也是 token，不计就没法跨工具比。 */
export type TokenDayStat = {
  day: string; sessions: number; input_tokens: number; output_tokens: number;
  total_tokens: number; cache_read_tokens: number; cache_write_tokens: number; cost_usd: number;
};
export type TokenWeekStat = {
  week: string; sessions: number; input_tokens: number; output_tokens: number;
  total_tokens: number; cache_read_tokens: number; cache_write_tokens: number; cost_usd: number;
};
export type TokenMonthStat = {
  month: string; sessions: number; input_tokens: number; output_tokens: number;
  total_tokens: number; cache_read_tokens: number; cache_write_tokens: number; cost_usd: number;
};
export type TokenModelStat = {
  model: string; sessions: number; total_tokens: number; cost_usd: number;
};
export type TokenAgentStat = {
  agent: string; sessions: number; input_tokens: number; output_tokens: number;
  total_tokens: number; cache_read_tokens: number; cache_write_tokens: number;
  cost_usd: number; credits: number; sources: string[];
};
export type TokenCoverageStat = {
  source: string; path: string; status: string; sessions: number; total_tokens: number; credits: number;
};
export type TokenTotals = {
  sessions: number; input_tokens: number; output_tokens: number;
  cache_read_tokens: number; cache_write_tokens: number;
  total_tokens: number; cost_usd: number;
};
export type TokenUsageData = {
  totals?: TokenTotals;
  daily: TokenDayStat[]; weekly: TokenWeekStat[];
  monthly: TokenMonthStat[]; models: TokenModelStat[];
  agents: TokenAgentStat[];
  today_agents: TokenAgentStat[];
  coverage: TokenCoverageStat[];
  timezone: string;
};

export async function monitorTokenUsage() {
  const { data } = await api.get<TokenUsageData>("/monitor/token-usage");
  return data;
}

/* ── 能力市场（门道社区的 Skill 来源）───────────────────────────────── */

export type MarketAttribution = {
  /** original = 作者本人上传；shared = 用户分享自己发现的好 Skill */
  origin?: "original" | "shared";
  original_author?: string;
  source_url?: string;
  license?: string;
};

export type MarketItem = MarketAttribution & {
  slug: string;
  title: string;
  summary?: string;
  /** 中文简介。技能库里绝大多数 SKILL.md 本来就写了，界面优先用它。 */
  summary_zh?: string;
  category?: string;
  class?: string;
  latest?: string;
  install_count?: number;
};

export type MarketCapability = {
  kind: string;
  detail: string;
  severity: "info" | "warn" | "block";
  where?: string;
};

export type MarketManifest = {
  class: string;
  files: string[];
  total_bytes: number;
  installable: boolean;
  blockers: string[];
  capabilities: MarketCapability[];
  /** 说人话的那一段，界面直接渲染它 */
  human_summary: string;
};

export type MarketPreview = {
  slug: string;
  version: string;
  /** 分享类必须在界面上标出来源 —— 只存在数据库里的署名等于没保留 */
  attribution?: MarketAttribution;
  integrity: { ok: boolean; problems: string[] };
  manifest: MarketManifest;
  sha256: string;
  /** 用户确认的是这份指纹；install 会核对，防止"看的是 A、装的是 B" */
  confirm_token: string;
};

export type MarketStatus = {
  enabled: boolean;
  /** 是否允许一键安装含可执行脚本的 B 类技能。默认 false；关着时仍可下载自装。 */
  allow_class_b?: boolean;
  url: string;
  installed: Record<string, { version: string; sha256: string; class: string }>;
};

export async function marketStatus() {
  const { data } = await api.get<MarketStatus>("/skill-market/status");
  return data;
}

export async function marketBrowse(params: { q?: string; category?: string; sort?: string }) {
  const { data } = await api.get<{ total: number; items: MarketItem[] }>(
    "/skill-market/skills", { params });
  return data;
}

export async function marketPreview(slug: string, version: string) {
  const { data } = await api.post<MarketPreview>("/skill-market/preview", { slug, version });
  return data;
}

export async function marketInstall(slug: string, version: string, confirm_token: string) {
  const { data } = await api.post("/skill-market/install", { slug, version, confirm_token });
  return data;
}

export type MarketDetail = MarketItem & {
  body_md?: string;
  versions?: { version: string; sha256: string; size_bytes: number; published_at: string }[];
};

export async function marketDetail(slug: string) {
  const { data } = await api.get<MarketDetail>(
    `/skill-market/skills/${slug}/detail`);
  return data;
}

/** 安装包的直链。**A/B 类都给** —— 这是"不一键装"和"完全不能用"之间的那条路：
 *  下下来自己看一眼脚本，自己决定要不要放进技能库。 */
export function marketDownloadUrl(slug: string, version: string) {
  return `/api/skill-market/skills/${slug}/${version || "1.0.0"}/download`;
}

export async function marketUninstall(slug: string) {
  const { data } = await api.post("/skill-market/uninstall", { slug });
  return data;
}

export type FindingEvidence = {
  metric: string;
  value: unknown;
  unit?: string;
  target?: string;
  source?: string;
  as_of?: string;
  note?: string;
};

export type FindingAction = {
  type: string;
  target?: string;
  detail?: string;
  /** 执行前提/阈值，如「点击≥15 且 0 单」。没有它就无法判断该不该照做。 */
  guardrail?: string;
  reversible?: boolean;
  confidence?: number;
};

export type Finding = {
  id?: string;
  severity?: "critical" | "high" | "medium" | "low";
  title: string;
  reasoning?: string;
  evidence?: FindingEvidence[];
  actions?: FindingAction[];
  priority_score?: number;
};

export type FindingList = {
  findings: Finding[];
  data_notes?: string;
  /** 完全没给证据的结论 id —— 用户最该能一眼看出的就是"这条凭什么"。 */
  unsupported?: string[];
};
