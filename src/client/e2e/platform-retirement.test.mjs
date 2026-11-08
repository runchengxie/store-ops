import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
const source = (p) => readFileSync(new URL('../src/' + p, import.meta.url), 'utf8');
test('retired product routes and implementations are removed', () => {
 const app = source('App.tsx');
 assert.doesNotMatch(app, /legacy\/|LingXing|DeepAnalysis|AdAuditPanel/);
 for (const path of ['pages/workbench/Home.tsx','pages/workbench/Market.tsx','pages/workbench/LingXingRedirect.tsx','api/cockpit.ts','api/market.ts']) assert.equal(existsSync(new URL('../src/'+path,import.meta.url)), false, path);
});
test('current eMAG and common infrastructure routes remain', () => {
 const app = source('App.tsx');
 for (const path of ['workbench','console','dashboard','market','playbook','listing','tools','news','approvals','schedules','hub-settings']) assert.match(app,new RegExp('path="'+path+'"'));
 assert.match(app,/path="\*" element={<NotFound/);
});
test('settings no longer exposes retired integration credentials', () => {
 const settings=source('pages/workbench/HubSettings.tsx')+source('api/settings.ts');
 assert.doesNotMatch(settings,/AmazonSection|getAmazonStatus|sorftime_key|sif_key|sellersprite_key/);
});
