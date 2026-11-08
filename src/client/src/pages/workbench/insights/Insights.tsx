import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../../App';
import { api } from '../../../api/client';
import { resolveStatusLocale, withStatusLanguage } from '../status/locale.mjs';
import en from './en.json';
import zh from './zh-CN.json';
import './insights.css';
type Data = Record<string, any>;
export default function Insights() {
    const { role } = useAuth();
    const [locale, setLocale] = useState<'en' | 'zh-CN'>(() => { let saved = null; try {
        saved = localStorage.getItem('store.status.locale');
    }
    catch { } return resolveStatusLocale(location.search, saved, []); });
    const c: Record<string, string> = locale === 'en' ? en : zh;
    const t = (key: string) => c[key] || key;
    const [tab, setTab] = useState('knowledge'), [index, setIndex] = useState<Data | null>(null), [q, setQ] = useState(''), [search, setSearch] = useState<Data | null>(null), [detail, setDetail] = useState<Data | null>(null), [stores, setStores] = useState<Data[]>([]), [store, setStore] = useState(''), [decision, setDecision] = useState<Data | null>(null), [product, setProduct] = useState(''), [file, setFile] = useState<File | null>(null), [preflight, setPreflight] = useState<Data | null>(null), [promotion, setPromotion] = useState<Data | null>(null), [error, setError] = useState(''), [busy, setBusy] = useState(false), [refresh, setRefresh] = useState(0);
    const [inputs, setInputs] = useState({ discount_pct: '0', voucher_pct: '0', stacking: 'unknown', commission_reduction_pct: '0', support_ex_vat_ron: '', extra_cost_ron: '' });
    const searchEpoch = useRef(0), storeEpoch = useRef(0), operationEpoch = useRef(0), detailEpoch = useRef(0);
    useEffect(() => () => { ++searchEpoch.current; ++storeEpoch.current; ++operationEpoch.current; ++detailEpoch.current; }, []);
    const fail = (e: any) => setError(e?.response?.status === 409 ? 'stale' : 'error');
    useEffect(() => { document.documentElement.lang = locale; }, [locale]);
    useEffect(() => { if (role !== 'admin')
        return; let live = true; api.get('/emag/knowledge/status').then(r => { if (live)
        setIndex(r.data); }).catch(e => { if (live)
        fail(e); }); api.get('/emag/stores').then(r => { if (!live)
        return; setStores(r.data); setStore((s: string) => s || r.data[0]?.store_id || ''); }).catch(e => { if (live)
        fail(e); }); return () => { live = false; }; }, [role]);
    useEffect(() => { const epoch = ++storeEpoch.current; ++operationEpoch.current; setDecision(null); setProduct(''); setPreflight(null); setPromotion(null); setBusy(false); if (role !== 'admin' || !store)
        return; api.get(`/emag/stores/${encodeURIComponent(store)}/decision-support`).then(r => { if (epoch !== storeEpoch.current)
        return; setDecision(r.data); setProduct(String(r.data.products[0]?.id ?? '')); }).catch(e => { if (epoch === storeEpoch.current)
        fail(e); }); }, [role, store, refresh]);
    async function runSearch(e?: React.FormEvent) { e?.preventDefault(); if (!q.trim() || role !== 'admin')
        return; const epoch = ++searchEpoch.current; setDetail(null); setSearch(null); setError(''); try {
        const r = await api.get('/emag/knowledge/search', { params: { q: q.trim(), limit: 5 } });
        if (epoch === searchEpoch.current)
            setSearch(r.data);
    }
    catch (e) {
        if (epoch === searchEpoch.current)
            fail(e);
    } }
    async function source(result: Data) { const epoch = searchEpoch.current; const detailRequest = ++detailEpoch.current; setDetail(null); try {
        const r = await api.get(`/emag/knowledge/sources/${encodeURIComponent(result.source_id)}`, { params: { revision: search?.revision } });
        if (epoch === searchEpoch.current && detailRequest === detailEpoch.current)
            setDetail(r.data);
    }
    catch (e) {
        if (epoch === searchEpoch.current)
            fail(e);
    } }
    async function operation(kind: 'preflight' | 'promotion') { if (!decision || role !== 'admin')
        return; const epoch = ++operationEpoch.current; setError(''); if (kind === 'preflight' && (!file || !file.name.toLowerCase().endsWith('.xlsx') || file.size > 5 * 1024 * 1024)) {
        setError('invalidFile');
        return;
    } setBusy(true); try {
        let r;
        if (kind === 'preflight') {
            const form = new FormData();
            form.append('snapshot_id', decision.snapshot_id);
            form.append('file', file!);
            r = await api.post(`/emag/stores/${encodeURIComponent(store)}/preflight`, form);
        }
        else
            r = await api.post(`/emag/stores/${encodeURIComponent(store)}/promotion-check/${encodeURIComponent(product)}`, { ...inputs, snapshot_id: decision.snapshot_id, extra_cost_ron: inputs.extra_cost_ron === '' ? null : inputs.extra_cost_ron, support_ex_vat_ron: inputs.support_ex_vat_ron === '' ? null : inputs.support_ex_vat_ron });
        if (epoch === operationEpoch.current)
            (kind === 'preflight' ? setPreflight : setPromotion)(r.data);
    }
    catch (e) {
        if (epoch === operationEpoch.current)
            fail(e);
    }
    finally {
        if (epoch === operationEpoch.current)
            setBusy(false);
    } }
    const lines = (values: any[]) => values?.map((x, i) => <li key={i}>{typeof x === 'string' ? x : JSON.stringify(x)}</li>);
    const field = (key: keyof typeof inputs, label: string) => <label>{t(label)}<input type="number" min="0" max={key.endsWith('pct') ? '100' : undefined} step="any" value={inputs[key]} onChange={e => { setInputs(v => ({ ...v, [key]: e.target.value })); setPromotion(null); ++operationEpoch.current; setBusy(false); }}/></label>;
    return <main className="emag-insights" data-testid="emag-insights"><header><div><Link to="/workbench">{t('back')}</Link><h1>{t('title')}</h1></div><select aria-label={t('language')} value={locale} onChange={e => { const v = e.target.value as 'en' | 'zh-CN'; setLocale(v); try {
        localStorage.setItem('store.status.locale', v);
        history.replaceState(history.state, '', withStatusLanguage(location.href, v));
    }
    catch { } }}><option value="en">EN</option><option value="zh-CN">中文</option></select></header>
 {role !== 'admin' ? <p role="alert">{t('permission')}</p> : <><p>{t('localOnly')}</p><nav aria-label={t('title')}>{['knowledge', 'suggestions', 'preflight', 'promotion'].map(key => <button key={key} aria-pressed={tab === key} onClick={() => setTab(key)}>{t(key)}</button>)}</nav>{error && <p role="alert">{t(error)}</p>}
 {tab === 'knowledge' ? <section><form onSubmit={runSearch}><label>{t('query')}<input maxLength={500} value={q} onChange={e => { setQ(e.target.value); ++searchEpoch.current; setDetail(null); }}/></label><button disabled={!q.trim()}>{t('search')}</button></form>{index?.available === false && <p>{t('noIndex')}</p>}{search?.available === false && <p>{t('noIndex')}</p>}{search?.available && search.results.length === 0 && <p>{t('empty')}</p>}{search?.results?.map((r: Data) => <article key={r.chunk_id}><h2>{r.title}</h2><p>{r.excerpt}</p><p>{t('trust')}: {r.trust} · {t('date')}: {r.date || t('unknown')}</p><p>{t('locator')}: {r.locator}</p><button onClick={() => source(r)}>{t('details')}</button>{r.conflicts?.length > 0 && <details><summary>{t('conflicts')}</summary><ul>{lines(r.conflicts)}</ul></details>}</article>)}{detail && <article data-testid="source-detail"><h2>{detail.title}</h2><p>{t('revision')}: {detail.revision} · {detail.source_hash}</p><p>{t('trust')}: {detail.trust} · {t('date')}: {detail.date || t('unknown')}</p><p>{t('historical')}</p><ul>{lines(detail.conflicts)}</ul>{detail.chunks?.map((x: Data) => <blockquote key={x.chunk_id}><p>{x.excerpt}</p><cite>{x.locator}</cite></blockquote>)}</article>}</section> : <section><label>{t('store')}<select value={store} onChange={e => setStore(e.target.value)}>{stores.map(s => <option key={s.store_id}>{s.store_id}</option>)}</select></label>{!stores.length && <p>{t('noStores')}</p>}{store && !decision && <p>{t('loading')}</p>}{decision && <><p>{t('snapshot')}: {decision.snapshot_id} · {decision.captured_at}</p><button onClick={() => setRefresh(v => v + 1)}>{t('refresh')}</button>
 {tab === 'suggestions' && <>{!decision.cards?.length && <p>{t('noCards')}</p>}{decision.cards?.map((card: Data) => <article key={card.id}><h2>{decision.products?.find((p: Data) => String(p.id) === String(card.product_id))?.name || card.product_id}</h2><p>{t(card.title_key)}</p><p>{t('stock')}: {card.stock ?? t('unknown')} · {t('priority')}: {t(card.priority)}</p><details><summary>{t('evidence')}</summary><ul>{lines(card.evidence)}</ul><h3>{t('checks')}</h3><ul>{lines(card.checks)}</ul></details><button onClick={() => { setQ(card.knowledge_query); setTab('knowledge'); }}>{t('knowledge')}</button></article>)}</>}
 {tab === 'preflight' && <><label>{t('file')}<input type="file" accept=".xlsx" onChange={e => { setFile(e.target.files?.[0] || null); setPreflight(null); ++operationEpoch.current; setBusy(false); }}/></label><button disabled={!file || busy} onClick={() => operation('preflight')}>{t('upload')}</button>{preflight && <article><h2>{t(preflight.status)}</h2><p>{preflight.file_name} · {preflight.row_count}</p><p>{JSON.stringify(preflight.layout)}</p><ul>{preflight.issues?.map((x: Data, i: number) => <li key={i}>{t('row')}: {x.row ?? t('unknown')} · {t('field')}: {x.field || x.column || t('unknown')} · {t('status')}: {x.severity} / {x.code}<p>{JSON.stringify(x.details)}</p></li>)}</ul>{preflight.truncated && <p>{t('bounded')}</p>}</article>}</>}
 {tab === 'promotion' && <><label>{t('product')}<select value={product} onChange={e => { setProduct(e.target.value); setPromotion(null); ++operationEpoch.current; setBusy(false); }}>{decision.products?.map((p: Data) => <option key={p.id} value={p.id}>{p.name} ({p.id})</option>)}</select></label>{!product && <p>{t('noProducts')}</p>}<div className="insights-fields">{field('discount_pct', 'discount')}{field('extra_cost_ron', 'extra')}</div><details><summary>{t('advanced')}</summary><div className="insights-fields">{field('voucher_pct', 'voucher')}{field('commission_reduction_pct', 'commission')}{field('support_ex_vat_ron', 'support')}<label>{t('stacking')}<select value={inputs.stacking} onChange={e => { setInputs(v => ({ ...v, stacking: e.target.value })); setPromotion(null); ++operationEpoch.current; setBusy(false); }}><option value="unknown">{t('unknown')}</option><option value="sequential">{t('sequential')}</option></select></label></div></details><button disabled={!product || busy} onClick={() => operation('promotion')}>{t('calculate')}</button>{promotion && <article data-testid="promotion-result"><h2>{t(promotion.status)}</h2>{promotion.missing?.length > 0 && <><h3>{t('missing')}</h3><ul>{lines(promotion.missing)}</ul><Link to="/tools">{t('tools')}</Link></>}<ul>{lines(promotion.warnings)}</ul><h3>{t('scenarios')}</h3>{promotion.scenarios?.map((s: Data, i: number) => <details key={i} open><summary>{s.kind}</summary><p>{s.sale_price_ex_vat_ron}</p><p>{t('before')}: {s.economics?.contribution_ron ?? t('unknown')}</p><p>{t('after')}: {s.contribution_with_assumed_support_ron ?? t('unknown')}</p><pre>{JSON.stringify(s.economics, null, 2)}</pre></details>)}</article>}</>}
 </>}</section>}</>}
 </main>;
}
