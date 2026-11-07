// All values in this file are fictional and exist only in the browser's memory.
export function createDemoState() {
  const offers = [
    { id: 101, name: '示例厨房量勺', part_number: 'DEMO-SPOON', part_number_key: 'DEMO-PNK-01', sale_price: 29.9, general_stock: 8, category_id: 101, brand: 'Demo' },
    { id: 102, name: '示例桌面收纳盒', part_number: 'DEMO-BOX', part_number_key: 'DEMO-PNK-02', sale_price: 45, general_stock: 3, category_id: 102, brand: 'Demo' },
    { id: 103, name: '示例硅胶模具', part_number: 'DEMO-MOULD', part_number_key: 'DEMO-PNK-03', sale_price: 35, general_stock: 0, category_id: 101, brand: 'Demo' },
  ];
  const issues = [
    { issue_id: 'demo-price', id: 101, reason: 'invalid_price', name: offers[0].name, part_number: offers[0].part_number, sale_price: 29.9, currency: 'RON', general_stock: 8, platform_status: { value: 2, description: 'Synthetic price review required', errors: 'Check price against costs' }, state: 'pending', revision: 0, history: [] },
    { issue_id: 'demo-doc', id: 103, reason: 'documentation_rejected', name: offers[2].name, part_number: offers[2].part_number, sale_price: 35, currency: 'RON', general_stock: 0, platform_status: [{ value: 8, error_details: [{ code: 'demo:shape', message: 'Choose a product shape' }] }], state: 'pending', revision: 0, history: [] },
  ];
  const drafts = [];
  const records = [];
  const meta = { store_id: 'demo-ro', snapshot_id: 'demo-v1', captured_at: '2026-10-28T00:00:00Z', source: 'synthetic-demo', coverage: ['synthetic offers'], limitations: ['演示数据，不连接真实店铺。刷新页面会重置模拟修改。'] };
  const commercial_summary = { orders_fbe_count: 2, orders_seller_count: 0, returns_fbe_count: 1, returns_seller_count: 0, invoice_count: 2, invoice_amount_unknown: 0, window: { start: '2026-10-01', end: '2026-10-28' }, inventory: { general_stock_total: 11, aging_total: 11, mismatched_skus: 0, aging_bands: { '365+': 1 }, stock_rows_unknown: 0, aging_rows_unknown: 0 }, invoice_totals: [] };
  const summary = { offers: offers.length, invalid_price: 1, invalid_price_with_stock: 1, stock_unknown: 0 };
  const transitions = { pending: 'proposed', proposed: 'approved', approved: 'executed', executed: 'reviewed' };
  function request(method, path, body = {}) {
    let result;
    const platform = { platform: 'emag', platform_label: 'eMAG', marketplace: 'RO', currency: 'RON', timezone: 'Europe/Bucharest' };
    if (method === 'GET' && path === '/operations/stores') result = [{ store_id: meta.store_id, captured_at: meta.captured_at, ...platform }];
    else if (method === 'GET' && path === '/operations/stores/demo-ro/overview') result = { ...meta, ...platform, metrics: { products: offers.length, issues: issues.length, stock: offers.reduce((sum, offer) => sum + offer.general_stock, 0) }, collection: null };
    else if (method === 'GET' && path === '/emag/stores') result = [{ store_id: 'demo-ro' }];
    else if (method === 'GET' && path === '/emag/stores/demo-ro') result = { ...meta, summary, commercial_summary, issues, records };
    else if (method === 'GET' && path === '/emag/stores/demo-ro/workspace') result = { ...meta, summary, commercial_summary, offers, issues, drafts };
    else if (method === 'GET' && path === '/emag/stores/demo-ro/job') result = { status: 'complete', mode: 'existing_snapshot', stage: 'complete', snapshot_id: 'demo-v1', delta_available: false };
    else if (method === 'POST' && path === '/emag/stores/demo-ro/drafts') {
      if (body.snapshot_id !== meta.snapshot_id || !body.title?.trim() || !body.body?.trim()) throw new Error('Invalid demo draft');
      const draft = { draft_id: `demo-draft-${drafts.length + 1}`, kind: body.kind, product_id: body.product_id, title: body.title, body: body.body, created_at: new Date().toISOString(), stale: false };
      drafts.push(draft); result = draft;
    } else if (method === 'POST' && /^\/emag\/stores\/demo-ro\/issues\/demo-(price|doc)$/.test(path)) {
      const issue = issues.find(item => path.endsWith(item.issue_id));
      if (body.state === 'reviewed') throw new Error('复查需要新快照；演示仅提供一份快照。');
      if (!issue || body.snapshot_id !== meta.snapshot_id || body.revision !== issue.revision || body.state !== transitions[issue.state] || !body.note?.trim()) throw new Error('Invalid demo transition');
      issue.state = body.state; issue.revision += 1;
      issue.history.push({ state: body.state, note: body.note, actor: 'demo', at: new Date().toISOString() });
      const existing = records.findIndex(item => item.issue_id === issue.issue_id);
      const record = { ...issue, snapshot_id: meta.snapshot_id, subject: { id: issue.id, part_number: issue.part_number, reason: issue.reason } };
      if (existing >= 0) records.splice(existing, 1);
      records.unshift(record); result = record;
    } else throw new Error('Unsupported demo operation');
    return structuredClone(result);
  }
  return { request };
}
