import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { createDemoState } from './state.mjs';
import { demoReply } from './reply.mjs';

test('demo document denies network connections and form submission', () => {
  const html = readFileSync(new URL('./index.html', import.meta.url), 'utf8');
  assert.match(html, /connect-src 'none'/);
  assert.match(html, /form-action 'none'/);
  assert.match(html, /object-src 'none'/);
});

test('workbench demo replies identify synthetic scope and never claim a model or platform write', () => {
  const data = createDemoState().request('GET', '/emag/stores/demo-ro/workspace');
  const reply = demoReply(data);
  assert.match(reply, /演示回复/);
  assert.ok(reply.includes('demo-ro'));
  assert.ok(reply.includes('demo-v1'));
  assert.match(reply, /不连接/);
  assert.match(reply, /未执行/);
});

test('demo exposes only synthetic stores and resets after reload', () => {
  const demo = createDemoState();
  assert.equal(demo.request('GET', '/emag/stores')[0].store_id, 'demo-ro');
  const board = demo.request('GET', '/emag/stores/demo-ro');
  assert.ok(board.issues.length >= 2);
  assert.equal(board.source, 'synthetic-demo');
  demo.request('POST', '/emag/stores/demo-ro/issues/demo-price', {
    snapshot_id: 'demo-v1', state: 'proposed', revision: 0, note: 'Check costs',
  });
  assert.equal(demo.request('GET', '/emag/stores/demo-ro').issues[0].state, 'proposed');
  assert.equal(createDemoState().request('GET', '/emag/stores/demo-ro').issues[0].state, 'pending');
});

test('drafts are memory-only and unsupported calls fail closed', () => {
  const demo = createDemoState();
  demo.request('POST', '/emag/stores/demo-ro/drafts', {
    snapshot_id: 'demo-v1', kind: 'listing', product_id: '101', title: 'Demo title', body: 'Demo body',
  });
  assert.equal(demo.request('GET', '/emag/stores/demo-ro/workspace').drafts.length, 1);
  assert.equal(createDemoState().request('GET', '/emag/stores/demo-ro/workspace').drafts.length, 0);
  assert.throws(() => demo.request('POST', '/emag/stores/demo-ro/products/publish', {}));
  assert.throws(() => demo.request('GET', 'https://example.invalid/real-store'));
});

test('demo rejects stale state and empty notes', () => {
  const demo = createDemoState();
  assert.throws(() => demo.request('POST', '/emag/stores/demo-ro/issues/demo-price', {
    snapshot_id: 'demo-v1', state: 'proposed', revision: 9, note: 'wrong revision',
  }));
  assert.throws(() => demo.request('POST', '/emag/stores/demo-ro/issues/demo-price', {
    snapshot_id: 'demo-v1', state: 'proposed', revision: 0, note: ' ',
  }));
});

test('demo cannot review against the same snapshot', () => {
  const demo = createDemoState();
  for (const [revision, state] of ['proposed', 'approved', 'executed'].entries()) {
    demo.request('POST', '/emag/stores/demo-ro/issues/demo-price', {
      snapshot_id: 'demo-v1', state, revision, note: 'demo',
    });
  }
  assert.throws(() => demo.request('POST', '/emag/stores/demo-ro/issues/demo-price', {
    snapshot_id: 'demo-v1', review_snapshot_id: 'demo-v1', state: 'reviewed', revision: 3, note: 'demo',
  }), /新快照/);
  assert.equal(demo.request('GET', '/emag/stores/demo-ro').issues[0].state, 'executed');
});

test('canonical platform demo preserves exact source identity and metrics', () => {
 const demo=createDemoState();
 const stores=demo.request('GET','/operations/stores');
 assert.equal(stores[0].platform,'emag');
 const overview=demo.request('GET','/operations/stores/demo-ro/overview');
 assert.equal(overview.source,'synthetic-demo');
 assert.equal(overview.snapshot_id,'demo-v1');
 assert.deepEqual(overview.metrics,{products:3,issues:2,stock:11});
 assert.equal(overview.collection,null);
 assert.throws(()=>demo.request('GET','/operations/stores/other/overview'));
});
