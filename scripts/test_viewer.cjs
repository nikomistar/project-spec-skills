// DOM-stub checks for the viewer; run with Node, no dependencies.
// The viewer's real script runs against a tiny fake DOM, so these checks
// exercise the shipped code (navigation, pages, gaps, map, search, copy,
// changes, requests, Markdown), not a copy of it.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const template = fs.readFileSync(path.join(__dirname, '../viewer/viewer.html'), 'utf8');
const scriptStart = template.lastIndexOf('<script>');
const scriptEnd = template.lastIndexOf('</script>');
assert.ok(scriptStart >= 0 && scriptEnd > scriptStart, 'viewer script must exist');
const script = template.slice(scriptStart + '<script>'.length, scriptEnd);

// --- static guarantees -----------------------------------------------------
assert.equal(template.split('__KNOWLEDGE_DATA__').length - 1, 1, 'exactly one data placeholder');
// The one <link> allowed is the favicon, and only as an inline data: image.
assert.ok(!/<script[^>]+\bsrc=|<link[^>]+\bhref=(?!"data:image\/svg\+xml,)|\bfetch\(|XMLHttpRequest|\.innerHTML|insertAdjacentHTML|outerHTML/.test(template),
  'no external loads or raw HTML injection');

// --- fake DOM --------------------------------------------------------------
class FakeEl {
  constructor(tag) {
    this.tagName = String(tag).toUpperCase();
    this.children = [];
    this.attrs = {};
    this.dataset = {};
    this.listeners = {};
    this.style = {};
    this.className = '';
    this.hidden = false;
    this.value = '';
  }
  get tag() { return this.tagName.toLowerCase(); }
  get textContent() { return this.children.map(c => (c.text !== undefined ? c.text : c.textContent)).join(''); }
  set textContent(v) { this.children = [{ text: String(v) }]; }
  get lastChild() { return this.children[this.children.length - 1]; }
  append(...nodes) { for (const n of nodes) this.children.push(typeof n === 'string' ? { text: n } : n); }
  replaceChildren(...nodes) { this.children = []; this.append(...nodes); }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return this.attrs[k]; }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  fire(type, event = {}) { (this.listeners[type] || []).forEach(fn => fn({ preventDefault() {}, ...event })); }
  click() { this.fire('click'); }
}
function walk(root, visit) {
  for (const c of root.children) {
    if (c instanceof FakeEl) { visit(c); walk(c, visit); }
  }
}
function findAll(root, pred) { const out = []; walk(root, e => { if (pred(e)) out.push(e); }); return out; }
function cls(e) { return String(e.className || e.attrs.class || ''); }
const has = (e, name) => cls(e).split(' ').includes(name);
const text = e => e.textContent;

function memory() {
  const map = new Map();
  return { map, getItem: k => (map.has(k) ? map.get(k) : null), setItem: (k, v) => { map.set(k, String(v)); } };
}

// Loads the viewer with a payload. `hash` plays the address bar; `storage` plays this browser's localStorage.
function load(payload, { hash, storage = memory(), timers = false } = {}) {
  const registry = new Map();
  const copied = [];
  const waiting = [];
  const document = {
    baseURI: 'http://127.0.0.1:8757/',
    title: '',
    createElement: tag => new FakeEl(tag),
    createElementNS: (ns, tag) => new FakeEl(tag),
    createTextNode: value => ({ text: String(value) }),
    getElementById: () => ({ textContent: JSON.stringify(payload) }),
    querySelector(sel) {
      if (!registry.has(sel)) registry.set(sel, new FakeEl('div'));
      return registry.get(sel);
    },
    querySelectorAll: () => [],
  };
  const ctx = vm.createContext({
    document, URL, Map, Set,
    localStorage: storage,
    navigator: { clipboard: { writeText: value => { copied.push(value); return { then: ok => ok() }; } } },
    location: hash == null ? undefined : { hash, href: 'http://127.0.0.1:8757/' + hash },
    // `timers` gives the page a clock that only moves when the test says so
    ...(timers ? { setTimeout: fn => waiting.push(fn), clearTimeout: id => { waiting[id - 1] = null; } } : {}),
  });
  vm.runInContext(script, ctx);
  const q = sel => document.querySelector(sel);
  const buttons = (root, pred = () => true) => findAll(root, e => e.tag === 'button' && pred(e));
  const v = {
    q, copied, storage, document,
    tick: () => waiting.splice(0).forEach(fn => fn && fn()),
    page: () => q('#view'),
    h1: () => (findAll(q('#view'), e => e.tag === 'h1')[0] || {}).textContent,
    nav: () => buttons(q('#nav-links')).map(b => b.children.map(text)),
    go: label => buttons(q('#nav-links'), b => b.children[0].textContent === label)[0].click(),
    tree: () => buttons(q('#tree'), b => has(b, 'tree-row')).map(b => b.children[0].textContent),
    treeRow: title => buttons(q('#tree'), b => has(b, 'tree-row') && b.children[0].textContent === title)[0],
    twist: title => buttons(q('#tree'), b => has(b, 'twist') && b.attrs['aria-label'].endsWith(' ' + title))[0],
    crumbs: () => q('#crumbs').children.map(text),
    btn: (root, label) => buttons(root, b => b.textContent === label)[0],
    pill: (root, label) => buttons(root, b => has(b, 'pill') && b.children[0].text === label)[0],
    tab: (root, label) => buttons(root, b => has(b, 'tab') && b.children[0].text === label)[0],
    select: label => findAll(q('#view'), e => e.tag === 'select' && e.attrs['aria-label'] === label)[0],
    rows: () => findAll(q('#view'), e => has(e, 'row')),
    rowTitles: () => findAll(q('#view'), e => has(e, 'row')).map(r => findAll(r, e => has(e, 'grow'))[0].children[0].textContent),
    folds: () => findAll(q('#view'), e => e.tag === 'summary').map(text),
    chips: () => findAll(q('#view'), e => has(e, 'chip')).map(text),
    related: () => findAll(q('#view'), e => cls(e) === 'recent').filter(l => l.children[0].textContent === 'Related').flatMap(l => l.children.slice(1).filter(c => !c.hidden).map(text)),
    article: () => findAll(q('#view'), e => cls(e) === 'article')[0],
    search(query, kind = 'open') {
      if (kind === 'open') q('#open-search').click();
      q('#palette-input').value = query;
      q('#palette-input').fire('input');
      return v.results();
    },
    results: () => findAll(q('#palette-results'), e => cls(e) === 'result'),
    resultNames: () => v.results().map(r => findAll(r, e => has(e, 'grow'))[0].children[0].textContent),
    groups: () => findAll(q('#palette-results'), e => cls(e) === 'eyebrow').map(text),
    // Opens any page by its title through search, the way a reader would.
    open(title) {
      const hit = v.search(title).find(r => findAll(r, e => has(e, 'grow'))[0].children[0].textContent === title);
      assert.ok(hit, 'search finds: ' + title);
      hit.click();
      assert.equal(v.h1(), title);
    },
    graphLabels: () => findAll(q('#graph'), e => e.attrs.role === 'button').map(e => e.attrs['aria-label']),
    graphNode: label => findAll(q('#graph'), e => e.attrs['aria-label'] === label)[0],
  };
  return v;
}

// --- sample payloads --------------------------------------------------------
const node = (over) => ({
  id: over.id, path: over.path, title: over.title, type: over.type, status: '', areas: ['areas/a'],
  updated: '2026-11-01', body: '', tags: [], stale: false, kind: '', recheck: '', recheckedBy: '',
  recheckedOn: '', decision: '', decidedBy: '', decidedOn: '', state: '', gap: '', layer: '', ...over,
});
const gap = (id, title, over) => node({ id, title, type: 'gap', layer: 'gap', path: `gaps/${id}.md`, kind: 'product-gap', recheck: 'not-checked', decision: 'open', ...over });
const spec = (id, title, type, areas, over) => node({ id, title, type, layer: 'spec', status: 'current', path: `${type}s/${id}.md`, areas, ...over });

const parcel = () => ({
  title: 'Parcel Desk',
  nodes: [
    node({ id: 'idx', title: 'Index page', type: 'index', layer: 'nav', status: 'current', path: '00-index.md', areas: [] }),
    node({ id: 'run1', title: 'Run one', type: 'run', layer: 'nav', status: 'current', path: 'runs/run1.md', areas: [] }),
    spec('pickups', 'Pickups', 'area', [], { summary: 'How a pickup is cancelled.', body: '# Pickups\n\nArea map text.' }),
    spec('access', 'Access', 'area', [], { summary: 'Who may change a pickup.' }),
    spec('cancel', 'Cancelling a pickup', 'note', ['pickups'], {
      summary: 'A customer can cancel a pickup until it is packed.', sources: ['src/pickups.py'], updated: '2026-11-14',
      body: '# Cancelling a pickup\n\n`cancel_pickup` checks [[notes/owner|the owner]] first.',
    }),
    spec('responses', 'Responses', 'note', ['pickups'], { body: '# Responses\n\nErrors become status codes.' }),
    spec('owner', 'Owner check', 'note', ['access'], { summary: 'Only the owner may change a pickup.' }),
    spec('old', 'Old rule', 'note', ['pickups'], { status: 'superseded' }),
    gap('g-open', 'Packed pickups', { state: 'needs-decision', areas: ['pickups'], priority: 'P1', body: '# Packed pickups\n\n## Current behavior\n\nRefused.' }),
    gap('g-done', 'Closed question', { state: 'done', decision: 'done', areas: ['pickups'] }),
  ],
  edges: [
    { source: 'pickups', target: 'cancel' }, { source: 'pickups', target: 'responses' }, { source: 'access', target: 'owner' },
    { source: 'cancel', target: 'owner' }, { source: 'g-open', target: 'cancel' }, { source: 'g-done', target: 'cancel' },
    { source: 'run1', target: 'cancel' },
  ],
});

// --- overview, tree, pages and knowing where you are --------------------------
{
  const v = load(parcel());
  assert.equal(v.q('#project-title').textContent, 'Parcel Desk');
  assert.equal(v.q('#header-note').textContent, 'Spec');
  assert.deepEqual(v.nav(), [['Overview', ''], ['Recent changes', ''], ['Gaps', '1 waiting'], ['Map', '']]);
  // the tree lists areas; an area opens to its features, without index, runs, gaps or superseded notes
  assert.deepEqual(v.tree(), ['Access', 'Pickups']);
  v.twist('Pickups').click();
  assert.deepEqual(v.tree(), ['Access', 'Pickups', 'Cancelling a pickup', 'Responses']);
  assert.equal(v.twist('Pickups').attrs['aria-expanded'], 'true');
  v.twist('Pickups').click();
  assert.deepEqual(v.tree(), ['Access', 'Pickups']);
  // overview: one card per area with its summary, how much is in it and the names of its features;
  // the features' own lines are on the area page, and gaps are only a quiet count
  const home = v.page().textContent;
  for (const t of ['Parcel Desk', 'How a pickup is cancelled.', 'Cancelling a pickup', '1 open question'])
    assert.ok(home.includes(t), 'overview shows: ' + t);
  for (const t of ['A customer can cancel a pickup until it is packed.', 'cancel_pickup', 'src/pickups.py', 'Old rule', 'Run one', 'Index page', 'Packed pickups'])
    assert.ok(!home.includes(t), 'overview hides: ' + t);
  const cards = findAll(v.page(), e => has(e, 'area-card'));
  assert.deepEqual(cards.map(c => c.children[0].textContent), ['Access', 'Pickups']);
  assert.deepEqual(v.crumbs(), ['Parcel Desk']);
  assert.equal(v.q('#back').disabled, true);
  assert.equal(v.q('#copy-ai').hidden, true, 'nothing to copy on the overview');
  assert.equal(v.q('#copy-link').hidden, true, 'no address to copy without a window');

  // a feature page: summary, then the text as written, sources folded, where you are shown three ways
  v.btn(v.page(), 'Cancelling a pickup').click();
  assert.equal(v.h1(), 'Cancelling a pickup');
  assert.deepEqual(v.crumbs(), ['Parcel Desk', '/', 'Pickups', '/', 'Cancelling a pickup']);
  assert.deepEqual(v.tree(), ['Access', 'Pickups', 'Cancelling a pickup', 'Responses'], 'the tree opens to the page');
  assert.equal(v.treeRow('Cancelling a pickup').attrs['aria-current'], 'page');
  assert.equal(v.treeRow('Cancelling a pickup').textContent, 'Cancelling a pickup1 open');
  assert.deepEqual(findAll(v.page(), e => cls(e) === 'lead').map(text), ['A customer can cancel a pickup until it is packed.']);
  assert.deepEqual(v.folds(), ['Closed questions (1)', 'Source files (1)'], 'a closed question is one fold away, not in the list of open ones');
  assert.deepEqual(v.chips(), [], 'related pages are not a block in the text');
  assert.deepEqual(v.related(), ['Owner check'], 'related pages beside the text, not the own area or a run');
  assert.deepEqual(v.rowTitles(), ['Packed pickups', 'Closed question'], 'the open question, then the closed one inside its fold');
  assert.ok(v.page().textContent.includes('notes/cancel.md'));
  assert.equal(findAll(v.page(), e => e.tag === 'h1').length, 1, 'the duplicate title heading is dropped');
  const rail = findAll(v.page(), e => cls(e) === 'rail')[0];
  assert.ok(rail.textContent.includes('You came from the overview. Back returns there.'));
  assert.deepEqual(findAll(rail, e => cls(e) === 'now').map(text), ['Cancelling a pickup']);
  assert.equal(v.q('#copy-ai').hidden, false);
  assert.equal(v.q('#back').disabled, false);
  assert.equal(v.q('#forward').disabled, true);

  // a link in the text moves on; Back and Forward walk the trail
  findAll(v.article(), e => cls(e) === 'wiki')[0].click();
  assert.equal(v.h1(), 'Owner check');
  assert.deepEqual(v.crumbs(), ['Parcel Desk', '/', 'Access', '/', 'Owner check']);
  assert.ok(findAll(v.page(), e => cls(e) === 'rail')[0].textContent.includes('You came from Cancelling a pickup.'));
  assert.deepEqual(findAll(v.page(), e => cls(e) === 'recent')[0].children.slice(1).map(text), ['Cancelling a pickup']);
  v.q('#back').click();
  assert.equal(v.h1(), 'Cancelling a pickup');
  assert.equal(v.q('#forward').disabled, false);
  v.q('#forward').click();
  assert.equal(v.h1(), 'Owner check');
  v.q('#back').click();
  v.q('#back').click();
  assert.deepEqual(v.crumbs(), ['Parcel Desk']);
  assert.equal(v.q('#back').disabled, true);
  // going somewhere new drops the forward trail
  v.treeRow('Access').click();
  assert.equal(v.q('#forward').disabled, true);
  assert.equal(v.h1(), 'Access');
  assert.ok(v.btn(v.page(), 'Owner check'));

  // a feature without a summary shows its text directly; an area folds its own text
  assert.equal(v.twist('Pickups').attrs['aria-expanded'], 'true', 'an area stays open after you leave it');
  v.treeRow('Responses').click();
  assert.deepEqual(v.folds(), []);
  assert.ok(v.page().textContent.includes('Errors become status codes.'));
  v.treeRow('Pickups').click();
  assert.deepEqual(v.folds(), ['More about this area']);
  assert.ok(v.btn(v.page(), 'Cancelling a pickup') && v.btn(v.page(), 'Responses') && !v.btn(v.page(), 'Old rule'));
  assert.deepEqual(v.crumbs(), ['Parcel Desk', '/', 'Pickups']);

  // a reference note shows its table even though it has a summary
  const ref = load({ title: 'Ref', nodes: [
    spec('a', 'Area', 'area', []),
    spec('jobs', 'Background jobs', 'note', ['a'], { summary: 'Two jobs, both on a schedule.', body: '# Background jobs\n\nEvery job registered in `worker.ts`: 2.\n\n| Job | Starts | Does |\n| --- | --- | --- |\n| digest | daily at 06:00 UTC | emails the digest |\n| purge | hourly | deletes expired links |' }),
  ], edges: [] }, { hash: '#/page/notes/jobs' });
  assert.deepEqual(findAll(ref.page(), e => e.tag === 'td').map(text).slice(0, 3), ['digest', 'daily at 06:00 UTC', 'emails the digest']);
  assert.deepEqual(ref.folds(), [], 'the table is not folded away');
  assert.equal(findAll(ref.page(), e => cls(e) === 'lead')[0].textContent, 'Two jobs, both on a schedule.');

  // a feature note with numbered rules: the number is marked, and searching for it finds the page
  const rules = load({ title: 'Rules', nodes: [
    spec('a', 'Area', 'area', []),
    spec('profile', 'Profile', 'note', ['a'], { summary: 'Where a person sets their name.', body: '# Profile\n\nWhere a person sets their name.\n\n## Business rules\n\n| ID | Rule |\n| --- | --- |\n| BR-PROFILE-01 | A name has 1 to 120 characters. |\n| Other | Not a number. |' }),
  ], edges: [] }, { hash: '#/page/notes/profile' });
  assert.deepEqual(findAll(rules.page(), e => e.tag === 'td' && cls(e) === 'rule-id').map(text), ['BR-PROFILE-01']);
  assert.deepEqual(rules.search('br-profile-01').length ? rules.resultNames() : [], ['Profile']);

  // a gap reached from a page
  v.treeRow('Cancelling a pickup').click();
  v.btn(v.page(), 'Packed pickups').click();
  assert.equal(v.h1(), 'Packed pickups');
  assert.deepEqual(v.crumbs(), ['Parcel Desk', '/', 'Gaps', '/', 'Packed pickups']);
  assert.deepEqual(v.chips(), [], 'the pages it is about are beside the text, not a block in it');
  assert.deepEqual(findAll(v.page(), e => cls(e) === 'recent')[0].children.map(text), ['This gap is about', 'Cancelling a pickup', 'Pickups · area']);
  assert.ok(findAll(v.page(), e => has(e, 'gap-facts'))[0].textContent.includes('Needs decision'));
  assert.ok(v.page().textContent.includes('Refused.'));
  assert.equal(v.document.title, 'Packed pickups · Parcel Desk');
}

// --- the address opens a page directly ---------------------------------------------
{
  const v = load(parcel(), { hash: '#/page/notes/owner' });
  assert.equal(v.h1(), 'Owner check');
  assert.equal(v.q('#copy-link').hidden, false);
  v.q('#copy-link').click();
  assert.deepEqual(v.copied, ['http://127.0.0.1:8757/#/page/notes/owner']);
  assert.equal(v.q('#toast').textContent, 'Link copied');
  assert.equal(load(parcel(), { hash: '#/gaps' }).h1(), 'Gaps');
  assert.equal(load(parcel(), { hash: '#/page/notes/nothing' }).h1(), 'Parcel Desk', 'an unknown page falls back to the overview');
  assert.equal(load(parcel(), { hash: '#/whatever' }).h1(), 'Parcel Desk');
}

// --- gap queue ----------------------------------------------------------------
const queue = {
  title: 'Sample vault',
  nodes: [
    node({ id: 'idx', title: 'Index page', type: 'index', layer: 'nav', status: 'current', path: '00-index.md' }),
    node({ id: 'areas/a', title: 'Area A', type: 'area', layer: 'spec', status: 'current', path: 'areas/a.md', areas: ['areas/a'] }),
    node({ id: 'areas/other', title: 'Other area', type: 'area', layer: 'spec', status: 'current', path: 'areas/other.md', areas: ['areas/other'] }),
    node({ id: 'note-a', title: 'Note A', type: 'note', layer: 'spec', status: 'current', path: 'notes/a.md' }),
    gap('g-recheck', 'Gap recheck', { state: 'needs-recheck', priority: 'P1' }),
    gap('g-decision', 'Gap decision', { state: 'needs-decision', recheck: 'confirmed', recheckedBy: 'agent', recheckedOn: '2026-11-05', kind: 'verification-gap' }),
    gap('g-accepted', 'Gap accepted', { state: 'accepted', decision: 'accepted', decidedBy: 'Ann', decidedOn: '2026-11-10', recheck: 'confirmed', recheckedBy: 'Bob', recheckedOn: '2026-11-08' }),
    gap('g-deferred', 'Gap deferred', { state: 'deferred', decision: 'deferred', decidedBy: 'Ann', decidedOn: '2026-11-11', kind: 'product-plan' }),
    gap('g-rejected', 'Gap rejected', { state: 'rejected', decision: 'rejected', decidedBy: 'Ann', decidedOn: '2026-11-12' }),
    gap('g-done', 'Gap done', { state: 'done', decision: 'done', kind: 'conflict' }),
    gap('g-dup', 'Gap duplicate', { state: 'duplicate', decision: 'duplicate' }),
    // state missing: must be derived from decision and recheck
    gap('g-derive', 'Gap derived', { state: '', priority: 'medium', recheck: 'not-reproduced', recheckedBy: 'Cy', recheckedOn: '2026-11-09' }),
    // recheck outdated (explicit value) and a rechecked gap whose sources changed (flag only)
    gap('g-outdated', 'Gap outdated', { state: '', priority: 'Low', recheck: 'outdated', recheckedBy: 'Dee', recheckedOn: '2026-10-01', recheckOutdated: true }),
    gap('g-outflag', 'Gap flagged', { state: 'needs-decision', priority: 'high', recheck: 'confirmed', recheckedBy: 'Eve', recheckedOn: '2026-10-02', recheckOutdated: true }),
    // legacy gap: none of the new fields, status still set
    { id: 'g-legacy', path: 'gaps/legacy.md', title: 'Legacy gap', type: 'gap', status: 'unverified', areas: ['areas/a'], body: 'old', tags: ['product-gap'] },
    node({ id: 'plan-1', title: 'Plan A', type: 'plan', layer: 'gap', status: 'planned', path: 'plans/p.md', gap: 'g-accepted' }),
  ],
  edges: [
    { source: 'areas/a', target: 'note-a' }, { source: 'g-recheck', target: 'note-a' }, { source: 'g-accepted', target: 'note-a' },
    { source: 'g-legacy', target: 'note-a' }, { source: 'g-accepted', target: 'plan-1' }, { source: 'plan-1', target: 'note-a' },
    { source: 'idx', target: 'g-recheck' }, { source: 'g-outflag', target: 'note-a' },
  ],
};
{
  const v = load(queue);
  assert.deepEqual(v.nav()[2], ['Gaps', '6 waiting'], 'recheck (3, one derived from legacy fields) + decision (3)');
  v.go('Gaps');
  assert.equal(v.h1(), 'Gaps');
  assert.deepEqual(v.crumbs(), ['Sample vault', '/', 'Gaps']);
  const counts = () => findAll(v.page(), e => has(e, 'tab')).map(text);
  assert.deepEqual(counts(), ['Open8', 'Needs recheck3', 'Needs decision3', 'Accepted1', 'Deferred1', 'History3'], 'the queue is the open work; closed gaps are under History');
  assert.equal(v.rowTitles().length, 8, 'no closed gap in the queue');
  // waiting states come first, each with the most urgent gap first (P1 before low, a gap without a priority last)
  assert.deepEqual(v.rowTitles().slice(0, 6), ['Gap recheck', 'Gap outdated', 'Legacy gap', 'Gap flagged', 'Gap derived', 'Gap decision']);
  v.tab(v.page(), 'Needs decision').click();
  assert.deepEqual(v.rowTitles(), ['Gap flagged', 'Gap derived', 'Gap decision']);
  assert.ok(v.page().textContent.includes('waiting for a person to accept, reject or defer'));
  const flagged = v.rows().find(r => r.textContent.startsWith('Gap flagged'));
  assert.ok(flagged.textContent.includes('Recheck outdated'));
  assert.ok(flagged.textContent.includes('Rechecked by Eve on 2026-10-02'));
  // the states are tabs; the filters and the order have a row of their own
  assert.equal(findAll(v.page(), e => has(e, 'pill')).length, 0, 'no pills on the queue');
  assert.deepEqual(findAll(findAll(v.page(), e => has(e, 'filters'))[0], e => e.tag === 'select').map(s => s.attrs['aria-label']), ['Area', 'Kind', 'Priority', 'Order']);
  // History: what is closed, the most recently closed first
  v.tab(v.page(), 'History').click();
  assert.deepEqual(v.rowTitles(), ['Gap rejected', 'Gap done', 'Gap duplicate']);
  assert.ok(v.page().textContent.includes('kept for the reason behind a rule'));
  v.tab(v.page(), 'Open').click();
  v.select('Kind').value = 'product-plan';
  v.select('Kind').fire('change');
  assert.deepEqual(v.rowTitles(), ['Gap deferred']);
  assert.deepEqual(counts(), ['Open1', 'Deferred1'], 'counts follow the other filters, and empty states are left out');
  v.select('Kind').value = '';
  v.select('Kind').fire('change');
  v.select('Area').value = 'areas/other';
  v.select('Area').fire('change');
  assert.deepEqual(v.rowTitles(), []);
  assert.ok(v.page().textContent.includes('No gaps match'));
  v.select('Area').value = '';
  v.select('Area').fire('change');
  // the priorities the queue has, most urgent first, and the gaps that have none
  assert.deepEqual(findAll(v.select('Priority'), e => e.tag === 'option').map(o => [o.value, o.textContent]),
    [['', 'All priorities'], ['high', 'High priority'], ['p1', 'P1 priority'], ['medium', 'Medium priority'], ['low', 'Low priority'], ['none', 'No priority']]);
  v.select('Priority').value = 'low';
  v.select('Priority').fire('change');
  assert.deepEqual(v.rowTitles(), ['Gap outdated'], 'the value is matched whatever its capitals');
  assert.deepEqual(counts(), ['Open1', 'Needs recheck1']);
  v.select('Priority').value = 'none';
  v.select('Priority').fire('change');
  assert.equal(v.rowTitles().length, 4, 'the open gaps without a priority; three more are closed');
  assert.ok(!v.rowTitles().includes('Gap recheck'));
  v.select('Priority').value = '';
  v.select('Priority').fire('change');

  // no gap of this queue has a topic, so there is nothing to pick
  assert.equal(v.select('Topic'), undefined);

  // a gap page: who rechecked and decided, in words
  v.btn(v.page(), 'Gap derived').click();
  const facts = () => findAll(v.page(), e => has(e, 'gap-facts'))[0].textContent;
  assert.ok(facts().includes('Not reproduced (no longer holds) by Cy on 2026-11-09'));
  assert.ok(facts().includes('Needs decision'));
  v.q('#back').click();
  assert.equal(v.h1(), 'Gaps', 'Back returns to the queue');
  v.btn(v.page(), 'Gap outdated').click();
  assert.ok(facts().includes('Outdated (last by Dee on 2026-10-01)'));
  assert.ok(v.page().textContent.includes('Recheck outdated'));
  v.q('#back').click();
  v.btn(v.page(), 'Legacy gap').click();
  assert.ok(facts().includes('Needs recheck'));
  assert.ok(v.page().textContent.includes('Product gap'), 'the old category tag is still shown');
  // an accepted gap leads to its plan and back
  v.q('#back').click();
  v.btn(v.page(), 'Gap accepted').click();
  assert.ok(facts().includes('Accepted by Ann on 2026-11-10'));
  findAll(v.page(), e => cls(e) === 'wiki' && e.textContent === 'Plan A')[0].click();
  assert.equal(v.h1(), 'Plan A');
  assert.deepEqual(v.crumbs(), ['Sample vault', '/', 'Gaps', '/', 'Gap accepted', '/', 'Plan A']);
  assert.ok(findAll(v.page(), e => cls(e) === 'wiki' && e.textContent === 'Gap accepted')[0]);
}

// What a gap is about (its topic) is a filter of the queue; who may use a feature is shown under its title.
{
  const v = load({
    title: 'Sample vault',
    nodes: [
      node({ id: 'areas/a', title: 'Area A', type: 'area', layer: 'spec', status: 'current', path: 'areas/a.md', areas: ['areas/a'] }),
      node({ id: 'users', title: 'Users', type: 'note', layer: 'spec', status: 'current', path: 'notes/users.md', access: ['admin', 'owner'] }),
      node({ id: 'profile', title: 'Profile', type: 'note', layer: 'spec', status: 'current', path: 'notes/profile.md' }),
      gap('g-role', 'Role change', { topic: 'security', kind: 'conflict' }),
      gap('g-empty', 'Empty list', { topic: 'ui' }),
      gap('g-own', 'Own word', { topic: 'billing' }),
      gap('g-plain', 'Plain gap', {}),
    ],
    edges: [{ source: 'areas/a', target: 'users' }, { source: 'areas/a', target: 'profile' }],
  });
  v.go('Gaps');
  assert.deepEqual(findAll(findAll(v.page(), e => has(e, 'filters'))[0], e => e.tag === 'select').map(s => s.attrs['aria-label']), ['Area', 'Kind', 'Topic', 'Order']);
  assert.deepEqual(findAll(v.select('Topic'), e => e.tag === 'option').map(o => [o.value, o.textContent]),
    [['', 'All topics'], ['security', 'Security'], ['ui', 'UI'], ['billing', 'Billing'], ['none', 'No topic']],
    'the topics the queue has, in the order the format lists them, a value of its own last');
  assert.ok(v.rows().find(r => r.textContent.startsWith('Role change')).textContent.includes('Security · Conflict'), 'the topic leads the line under the title');
  v.select('Topic').value = 'security';
  v.select('Topic').fire('change');
  assert.deepEqual(v.rowTitles(), ['Role change']);
  assert.deepEqual(findAll(v.page(), e => has(e, 'tab')).map(text), ['Open1', 'Needs recheck1'], 'the counts follow the topic');
  v.select('Topic').value = 'none';
  v.select('Topic').fire('change');
  assert.deepEqual(v.rowTitles(), ['Plain gap']);
  v.select('Topic').value = '';
  v.select('Topic').fire('change');
  v.btn(v.page(), 'Role change').click();
  assert.ok(findAll(v.page(), e => has(e, 'gap-facts'))[0].textContent.includes('TopicSecurity'));
  v.open('Users');
  assert.ok(findAll(v.page(), e => has(e, 'metarow'))[0].textContent.includes('Access: admin, owner'));
  v.open('Profile');
  assert.ok(!v.page().textContent.includes('Access:'), 'a page that does not say who may use it shows nothing');
}

// The first page says what was checked: the map, each review with its last run, and the reviews not run yet.
// The queue finds gaps by the words in them without replacing the field you type in.
{
  const run = (id, path, over) => node({ id, title: id, type: 'run', layer: 'nav', status: 'current', path, areas: [], ...over });
  const v = load({
    title: 'Sample vault',
    map: { finished: 3, inProgress: 1, notStarted: 0 },
    nodes: [
      node({ id: 'areas/a', title: 'Area A', type: 'area', layer: 'spec', status: 'current', path: 'areas/a.md', areas: ['areas/a'] }),
      node({ id: 'users', title: 'Users', type: 'note', layer: 'spec', status: 'current', path: 'notes/users.md' }),
      run('sec-old', 'runs/2026-10-01-review-security.md', { updated: '2026-10-01', body: '- [x] Users\n' }),
      run('sec-new', 'runs/2026-11-02-review-security.md', { updated: '2026-11-02', body: '## Features\n\n- [x] Users\n- [x] Orders\n' }),
      run('val', 'runs/val.md', { review: 'validation', status: 'partial', updated: '2026-11-03', body: '- [x] Users\n- [ ] Orders\n' }),
      run('texts', 'runs/2026-11-04-review-texts.md', { updated: '2026-11-04', body: 'No checklist.' }),
      run('other', 'runs/2026-11-05-orders-review.md', { updated: '2026-11-05', body: '- [x] Orders\n' }),
      gap('g-role', 'Role change', { topic: 'security', review: 'abuse', body: '# Role change\n\n## Gap\n\nA member saves the profile form.' }),
      gap('g-closed', 'Closed leak', { topic: 'security', state: 'done', decision: 'done' }),
      gap('g-job', 'Job retry', { topic: 'ops', body: '# Job retry\n\n## Gap\n\nThe digest job is not retried.' }),
      gap('g-plain', 'Profile photo', {}),
    ],
    edges: [{ source: 'areas/a', target: 'users' }],
  });
  const block = () => findAll(v.page(), e => has(e, 'reviews'))[0];
  const row = name => findAll(block(), e => has(e, 'row')).find(r => findAll(r, e => e.tag === 'b')[0].textContent === name);
  assert.deepEqual(findAll(block(), e => has(e, 'row')).map(r => findAll(r, e => e.tag === 'b')[0].textContent),
    ['Map', 'Security', 'Abuse', 'Validation', 'Data', 'Logic', 'Flows', 'API', 'UI', 'Failure paths', 'Texts'], 'the map, the nine reviews the skill has, then a topic of the person\'s own');
  assert.ok(text(row('Map')).includes('3 of 4 features finished (75%)'));
  assert.ok(text(row('Map')).includes('1 in progress'));
  assert.ok(v.btn(row('Map'), 'Copy request to continue'), 'an unfinished map offers the request that continues it');
  assert.ok(text(row('Security')).includes('Last run 2026-11-02'), 'the newest run of a topic');
  assert.ok(text(row('Security')).includes('2 of 2 features'));
  assert.ok(v.btn(row('Security'), '1 open gap'), 'closed gaps are not counted');
  assert.ok(text(row('Validation')).includes('Started 2026-11-03'));
  assert.ok(text(row('Validation')).includes('1 of 2 features, not finished'));
  assert.ok(text(row('Data')).includes('Not run yet'));
  assert.ok(v.btn(row('Failure paths'), '1 open gap'), 'the gaps of a failure review have the topic ops');
  assert.ok(text(row('Abuse')).includes('Not run yet') && v.btn(row('Abuse'), '1 open gap'), 'the gaps of an abuse review have the topic security');
  assert.ok(text(row('Texts')).includes('Last run 2026-11-04'), 'a run page named <date>-review-<topic> is a review; one that only ends in -review is not');
  v.btn(row('Data'), 'Copy request').click();
  assert.ok(v.copied.at(-1).startsWith('Use the project-knowledge skill in review mode: review the product for data. Go by the inventory file'));
  v.btn(row('API'), 'Copy request').click();
  assert.ok(v.copied.at(-1).includes('review the product for its API.'));
  // the run page is one press away
  v.btn(row('Security'), 'Last run 2026-11-02').click();
  assert.equal(v.h1(), 'sec-new');
  v.q('#back').click();
  // a gap that names the review that wrote it is counted for that review and found by it
  v.btn(row('Abuse'), '1 open gap').click();
  assert.equal(v.select('Found by').value, 'abuse');
  assert.equal(v.select('Topic').value, '', 'two reviews share a topic, so the topic is not the filter');
  assert.deepEqual(v.rowTitles(), ['Role change']);
  v.q('#back').click();
  // and so are the gaps of the topic
  v.btn(row('Security'), '1 open gap').click();
  assert.equal(v.h1(), 'Gaps');
  assert.equal(v.select('Topic').value, 'security');
  assert.deepEqual(v.rowTitles(), ['Role change']);
  v.select('Topic').value = '';
  v.select('Topic').fire('change');
  assert.equal(v.rowTitles().length, 3);

  // words: every word must be in the gap's title, file or text
  const words = () => findAll(v.page(), e => e.tag === 'input' && e.attrs['aria-label'] === 'Words')[0];
  const field = words();
  field.value = 'digest retried';
  field.fire('input');
  assert.deepEqual(v.rowTitles(), ['Job retry'], 'found by the words in its text');
  assert.equal(words(), field, 'the field you type in is not replaced');
  assert.deepEqual(findAll(v.page(), e => has(e, 'tab')).map(text), ['Open1', 'Needs recheck1'], 'the counts follow the words');
  field.value = 'PROFILE';
  field.fire('input');
  assert.deepEqual(v.rowTitles(), ['Profile photo', 'Role change'], 'in the title of one and the text of the other, whatever the capitals');
  field.value = 'nothing-like-this';
  field.fire('input');
  assert.ok(v.page().textContent.includes('No gaps match'));
  v.btn(v.page(), 'Clear the filters').click();
  assert.equal(v.rowTitles().length, 3);
  assert.equal(words().value, '');
}

// A spec with errors is shown all the same, and lists every one of them: on the first page that there are some,
// under Recent changes each of them, grouped by page, with a request for an agent that names them all.
{
  const v = load({
    title: 'Sample vault',
    vaultPath: 'project-spec',
    errors: [
      'notes/users.md: rule BR-USERS-03 is numbered twice (on this page); give the newer rule the next free one',
      'notes/users.md: missing wikilink absent',
      'notes/unread.md: missing frontmatter',
      'Invalid source snapshot: expected object of note source maps',
    ],
    nodes: [node({ id: 'users', title: 'Users', type: 'note', layer: 'spec', status: 'current', path: 'notes/users.md' })],
    edges: [],
  });
  const card = id => findAll(v.page(), e => e.id === id)[0];
  assert.deepEqual(v.nav()[1], ['Recent changes', '4 errors']);
  assert.ok(text(card('errors-note')).includes('The spec has 4 errors'));
  v.btn(card('errors-note'), 'Show them').click();
  const rows = findAll(card('errors'), e => has(e, 'row'));
  assert.ok(text(card('errors')).startsWith('The spec has 4 errors'));
  assert.deepEqual(rows.map(r => findAll(r, e => e.tag === 'li').map(text)), [
    ['rule BR-USERS-03 is numbered twice (on this page); give the newer rule the next free one', 'missing wikilink absent'],
    ['missing frontmatter'],
    ['Invalid source snapshot: expected object of note source maps'],
  ], 'every error, grouped by its page');
  assert.ok(text(rows[1]).includes('Not shown') && text(rows[1]).includes('notes/unread.md'), 'a page that could not be read is named');
  assert.ok(text(rows[2]).includes('The whole spec'));
  v.btn(card('errors'), 'Copy for AI').click();
  assert.ok(v.copied.at(-1).startsWith('Use the project-knowledge skill. Its check command reports these errors'));
  assert.ok(v.copied.at(-1).includes('- project-spec/notes/users.md: missing wikilink absent\n- project-spec/notes/unread.md: missing frontmatter\n- Invalid source snapshot'));
  v.btn(rows[0], 'Users').click();
  assert.ok(v.page().textContent.includes('Users'), 'the page with the error opens');
}

// A vault without an inventory file or any review still says what can be checked.
{
  const v = load({ title: 'Sample vault', nodes: [node({ id: 'users', title: 'Users', type: 'note', layer: 'spec', status: 'current', path: 'notes/users.md' })], edges: [] });
  const rows = findAll(findAll(v.page(), e => has(e, 'reviews'))[0], e => has(e, 'row'));
  assert.deepEqual(rows.map(r => findAll(r, e => e.tag === 'b')[0].textContent), ['Security', 'Abuse', 'Validation', 'Data', 'Logic', 'Flows', 'API', 'UI', 'Failure paths']);
  assert.ok(rows.every(r => text(r).includes('Not run yet')));
}

// --- map: one frame per area -----------------------------------------------------
{
  const v = load({
    title: 'Clusters',
    nodes: [
      node({ id: 'idx', title: 'Index page', type: 'index', layer: 'nav', status: 'current', path: '00-index.md', areas: [] }),
      node({ id: 'run1', title: 'Run one', type: 'run', layer: 'nav', status: 'current', path: 'runs/run1.md', areas: [] }),
      spec('a', 'Area A', 'area', []), spec('b', 'Area B', 'area', []),
      spec('a1', 'A one', 'note', ['a']), spec('a2', 'A two', 'note', ['a']), spec('b1', 'B one', 'note', ['b', 'a']),
      gap('g-b', 'Gap in B', { state: 'needs-recheck', areas: ['b'] }),
      node({ id: 'plan-b', title: 'Plan B', type: 'plan', layer: 'gap', status: 'planned', path: 'plans/b.md', gap: 'g-b', areas: ['b'] }),
    ],
    edges: [
      { source: 'idx', target: 'a' }, { source: 'idx', target: 'b' }, { source: 'run1', target: 'a1' },
      { source: 'a', target: 'a1' }, { source: 'a', target: 'a2' }, { source: 'b', target: 'b1' },
      { source: 'a', target: 'b1' },   // second area of b1: a real cross-area relation
      { source: 'a1', target: 'a2' },  // inside one area
      { source: 'a2', target: 'b1' },  // across areas
      { source: 'g-b', target: 'b1' },
    ],
  });
  assert.equal(v.q('#mapview').hidden, true);
  v.go('Map');
  assert.equal(v.q('#mapview').hidden, false);
  assert.equal(v.q('#view').hidden, true);
  assert.equal(v.q('#map-title').textContent, 'Spec map');
  const svg = v.q('#graph');
  const frames = () => findAll(svg, e => cls(e) === 'cluster');
  const xy = label => v.graphNode(label).attrs.transform.match(/-?[\d.]+/g).map(Number);
  const inside = (label, f) => {
    const [x, y] = xy(label), fx = +f.attrs.x, fy = +f.attrs.y;
    return x > fx && x < fx + +f.attrs.width && y > fy && y < fy + +f.attrs.height;
  };
  // spec pages only: index, run, gap and plan pages are not drawn
  assert.deepEqual(v.graphLabels().sort(), ['A one', 'A two', 'Area A', 'Area B', 'B one']);
  assert.equal(frames().length, 2);
  const frameOf = label => frames().filter(f => inside(label, f));
  for (const label of ['Area A', 'A one', 'A two', 'Area B', 'B one']) assert.equal(frameOf(label).length, 1, label + ' sits in exactly one frame');
  assert.equal(frameOf('A one')[0], frameOf('Area A')[0]);
  assert.equal(frameOf('B one')[0], frameOf('Area B')[0]);
  assert.notEqual(frameOf('Area A')[0], frameOf('Area B')[0]);
  const [f1, f2] = frames().map(f => ({ x: +f.attrs.x, y: +f.attrs.y, w: +f.attrs.width, h: +f.attrs.height }));
  assert.ok(f1.x + f1.w <= f2.x || f2.x + f2.w <= f1.x || f1.y + f1.h <= f2.y || f2.y + f2.h <= f1.y, 'frames do not overlap');
  // lines: a1-a2 (plain), a2-b1 and a-b1 (cross); membership is the frame, not a line
  const lines = () => findAll(svg, e => e.tag === 'line');
  assert.equal(lines().length, 3);
  assert.equal(lines().filter(l => cls(l) === 'cross').length, 2);
  // the area filter narrows the map
  const areaSelect = () => findAll(v.q('#map-controls'), e => e.tag === 'select')[0];
  areaSelect().value = 'b';
  areaSelect().fire('change');
  assert.deepEqual(v.graphLabels().sort(), ['Area B', 'B one']);
  areaSelect().value = '';
  areaSelect().fire('change');
  // the gap layer: gaps and plans, with the spec pages they refer to as context
  v.pill(v.q('#map-controls'), 'Gaps').click();
  assert.equal(v.q('#map-title').textContent, 'Gap map');
  assert.deepEqual(v.graphLabels().sort(), ['B one', 'Gap in B (Needs recheck)', 'Plan B (Plan)']);
  assert.ok(cls(v.graphNode('B one')).includes('context'));
  assert.ok(cls(v.graphNode('Gap in B (Needs recheck)')).includes('st-needs-recheck'));
  assert.equal(findAll(v.graphNode('Plan B (Plan)'), e => e.tag === 'rect').length, 1, 'plans are squares');
  assert.deepEqual(findAll(svg, e => cls(e) === 'cluster-label').map(text), ['Area B'], 'a frame without its area page gets a plain label');
  // a node opens its page; Back returns to the map
  v.graphNode('Gap in B (Needs recheck)').click();
  assert.equal(v.h1(), 'Gap in B');
  assert.equal(v.q('#mapview').hidden, true);
  v.q('#back').click();
  assert.equal(v.q('#mapview').hidden, false);
}

// --- search ------------------------------------------------------------------
{
  const data = parcel();
  data.files = { 'src/pickups.py': { text: 'def cancel_pickup():\n    pass', truncated: false }, 'docs/owner-rules.md': { text: '# Rules', truncated: false } };
  data.vaultPath = 'knowledge/parcel';
  const v = load(data);
  v.q('#open-search').click();
  assert.equal(v.q('#palette').hidden, false);
  assert.deepEqual(v.groups(), ['Areas'], 'before typing: somewhere to start');
  assert.deepEqual(v.resultNames(), ['Access', 'Pickups']);
  // grouped results; a title match ranks above a text match
  v.search('owner', 'typed');
  assert.deepEqual(v.groups(), ['Features', 'Files']);
  assert.deepEqual(v.resultNames(), ['Owner check', 'Cancelling a pickup', 'docs/owner-rules.md']);
  assert.deepEqual(findAll(v.q('#palette-results'), e => e.tag === 'mark').map(text), ['Owner', 'owner']);
  assert.equal(v.results()[0].attrs['aria-selected'], 'true');
  assert.equal(v.results()[0].textContent, 'Owner checkAccess', 'a feature names its area');
  // text inside a cited file is searched too
  v.search('cancel_pickup', 'typed');
  assert.deepEqual(v.resultNames(), ['Cancelling a pickup', 'src/pickups.py']);
  // gaps carry their state; superseded notes do not leak in
  v.search('p', 'typed');
  assert.deepEqual(v.groups(), ['Features', 'Gaps', 'Other pages', 'Files']);
  assert.ok(!v.resultNames().includes('Old rule'));
  assert.ok(v.results().find(r => r.textContent.startsWith('Packed pickups')).textContent.includes('Needs decision'));
  v.pill(v.q('#palette-filters'), 'Gaps').click();
  assert.deepEqual(v.groups(), ['Gaps']);
  assert.deepEqual(v.resultNames(), ['Packed pickups']);
  v.search('e', 'typed');
  assert.deepEqual(v.resultNames(), ['Closed question', 'Packed pickups'], 'the filter stays while you type');
  // arrows move, Enter opens
  v.q('#palette-input').fire('keydown', { key: 'ArrowDown' });
  assert.equal(v.results()[1].attrs['aria-selected'], 'true');
  v.q('#palette-input').fire('keydown', { key: 'ArrowDown' });
  assert.equal(v.results()[0].attrs['aria-selected'], 'true', 'wraps around');
  v.q('#palette-input').fire('keydown', { key: 'ArrowUp' });
  v.q('#palette-input').fire('keydown', { key: 'Enter' });
  assert.equal(v.q('#palette').hidden, true);
  assert.equal(v.h1(), 'Packed pickups');
  // a file opens in the file pane
  v.search('rules');
  v.results()[0].click();
  assert.equal(v.q('#filepane').hidden, false);
  assert.equal(v.q('#file-title').textContent, 'docs/owner-rules.md');
  v.q('#file-close').click();
  assert.equal(v.search('zzz').length, 0);
  assert.ok(v.q('#palette-results').textContent.includes('Nothing matches.'));
  // after reading, the empty search offers what you looked at
  v.search('', 'typed');
  assert.deepEqual(v.groups(), ['Recently viewed']);
  assert.deepEqual(v.resultNames(), ['Packed pickups']);
}

// --- copy for AI: one dialog for everything you ask the agent ------------------------
{
  const data = parcel();
  data.vaultPath = 'knowledge/parcel';
  const storage = memory();
  const v = load(data, { storage });
  const card = () => v.q('#copy-card');
  const preview = () => findAll(card(), e => e.id === 'copy-preview')[0].textContent;
  const hint = () => findAll(card(), e => e.id === 'copy-hint')[0].textContent;
  const field = id => findAll(card(), e => e.id === id)[0];
  const type = (id, value) => { field(id).value = value; field(id).fire('input'); };
  const check = label => findAll(card(), e => has(e, 'check') && e.textContent === label)[0].children[0];
  const intents = () => findAll(findAll(card(), e => e.tag === 'fieldset')[0], e => has(e, 'pill') && !findAll(card(), x => x.id === 'copy-choice').some(c => findAll(c, y => y === e).length)).map(text);
  const tail = ['', 'Gap: knowledge/parcel/gaps/g-open.md', 'Title: Packed pickups', 'State: needs decision · product gap · P1', '',
    'It refers to:', '- knowledge/parcel/notes/cancel.md (Cancelling a pickup)'].join('\n');
  v.open('Packed pickups');
  v.q('#copy-ai').click();
  assert.equal(v.q('#copydlg').hidden, false);
  // a gap: what the agent can do, each choice explained
  assert.deepEqual(intents(), ['Recheck it', 'I checked it myself', 'Record my decision', 'Lay out options', 'Plan it', 'Change the behavior', 'Remove this page']);
  assert.ok(hint().startsWith('The agent reads the code and writes what it found into the gap.'));
  assert.equal(preview(), "Use the project-knowledge skill to re-check this gap against the code. Write the result into the gap's Recheck section and leave the decision to me.\n" + tail);
  assert.equal(field('copy-me'), undefined, 'a recheck by the agent needs no name');
  // your own words go into the request as you type, without redrawing the field
  const note = field('copy-note');
  type('copy-note', 'the packed state in the service');
  assert.ok(preview().includes('\n\nLook at: the packed state in the service\n'));
  assert.equal(field('copy-note'), note, 'the field you type in is not replaced');

  // "I checked it myself": your result, under your name, and the gap closed if that settles it
  v.pill(card(), 'I checked it myself').click();
  assert.ok(hint().startsWith('You already verified this.'));
  assert.deepEqual(findAll(field('copy-choice'), e => has(e, 'pill')).map(e => [e.textContent, e.attrs['aria-pressed']]), [['It is fine now', 'true'], ['Still a gap', 'false']]);
  assert.equal(field('copy-note').value, 'the packed state in the service', 'what you typed survives a change of mind');
  type('copy-note', '');
  assert.ok(preview().startsWith('Use the project-knowledge skill. I re-checked this gap myself and it no longer holds: [what you checked and saw]\n\nRecord my recheck in the gap as not reproduced, under my name ([your name]) and today\'s date'));
  type('copy-note', 'Cancelled a packed pickup on staging; it went through.');
  type('copy-me', 'Vadim');
  assert.equal(preview(), [
    'Use the project-knowledge skill. I re-checked this gap myself and it no longer holds: Cancelled a packed pickup on staging; it went through.',
    '',
    "Record my recheck in the gap as not reproduced, under my name (Vadim) and today's date, with what I found in its Recheck section. If that answers the question, close the gap as done and say why in its Decision section.",
  ].join('\n') + '\n' + tail);
  v.pill(field('copy-choice'), 'Still a gap').click();
  assert.ok(preview().includes('it still holds: Cancelled a packed pickup on staging; it went through.'));
  assert.ok(preview().includes('Record my recheck in the gap as confirmed, under my name (Vadim)') && preview().includes('Leave the decision open.'));

  // "Record my decision": the agent writes down what you decided, nothing more
  v.pill(card(), 'Record my decision').click();
  assert.deepEqual(findAll(field('copy-choice'), e => has(e, 'pill')).map(text), ['Accept', 'Reject', 'Defer']);
  assert.equal(field('copy-me').value, 'Vadim');
  v.pill(field('copy-choice'), 'Defer').click();
  type('copy-note', 'Not before the partner launch.');
  assert.ok(preview().startsWith('Use the project-knowledge skill. I have decided this gap: deferred. Reason: Not before the partner launch.\n\nRecord the decision in the gap under my name (Vadim) with today\'s date'));
  assert.ok(preview().includes('If the gap has not been rechecked yet, tell me before recording it.'));

  // a page that is only noise can be removed; a real question is rejected instead, and the dialog says so
  v.pill(card(), 'Remove this page').click();
  assert.ok(hint().includes('record a decision to reject it instead'));
  type('copy-note', '');
  assert.ok(preview().startsWith('Use the project-knowledge skill to remove this page from the vault: I consider it noise.\n\nDelete the file, remove or reword every link to it on other pages, and run check.'));
  type('copy-note', 'it is about the vault, not the product');
  assert.ok(preview().startsWith('Use the project-knowledge skill to remove this page from the vault: it is about the vault, not the product.'));
  type('copy-note', 'Not before the partner launch.');

  // the other choices, and what to include
  v.pill(card(), 'Plan it').click();
  assert.ok(preview().startsWith('Use the project-knowledge skill to plan this gap. Plan only, do not build it,'));
  assert.ok(preview().includes('Keep in mind: Not before the partner launch.'));
  v.pill(card(), 'Change the behavior').click();
  type('copy-note', '');
  assert.ok(preview().startsWith('I want to change the behavior this page describes.\n\nMake this change: [describe the change]\n\nWhen the code is done, record the change in the spec'),
    'the change comes first, as an order; nothing tells the agent to ask and wait');
  assert.ok(!/question|go-ahead|Ask me/i.test(preview().split('\n\nGap:')[0]));
  assert.ok(preview().includes('If the change answers this gap, close the gap as done there and name the rule that now says it.'), 'asked from a gap, the change closes it');
  type('copy-note', 'add the limit the mobile app has');
  assert.ok(preview().includes('Make this change: add the limit the mobile app has\n\nWhen the code is done'));
  type('copy-note', '');
  check('The 1 spec page it refers to').checked = false;
  check('The 1 spec page it refers to').fire('change');
  assert.ok(!preview().includes('It refers to:'));
  check('Full text of the page').checked = true;
  check('Full text of the page').fire('change');
  assert.ok(preview().endsWith('Text of the page:\n\n## Current behavior\n\nRefused.'));
  findAll(card(), e => e.id === 'copy-do')[0].click();
  assert.deepEqual(v.copied, [preview()], 'the clipboard gets exactly the preview');
  assert.equal(v.q('#toast').textContent, 'Copied. Paste it into your agent.');
  assert.ok(!v.btn(card(), 'Add to a request'), 'there is one way to ask, not two');
  v.btn(card(), 'Close').click();
  assert.equal(v.q('#copydlg').hidden, true);

  // a spec page offers what fits a spec page
  v.open('Cancelling a pickup');
  v.q('#copy-ai').click();
  assert.deepEqual(intents(), ['Change the behavior', 'Ask a question', 'Review one topic', 'Re-read against the code', 'Remove this page']);
  assert.ok(preview().includes('Page: knowledge/parcel/notes/cancel.md'));
  assert.ok(preview().includes('Make this change: ') && !preview().includes('close the gap'), 'a feature page has no gap to close');
  // a review of one topic: security unless another is picked
  v.pill(card(), 'Review one topic').click();
  assert.ok(preview().startsWith('Use the project-knowledge skill in review mode: review what this page covers for security.'));
  v.pill(card(), 'UI').click();
  assert.ok(preview().startsWith('Use the project-knowledge skill in review mode: review what this page covers for its UI.'));
  assert.ok(preview().includes('Write each doubt as its own gap with the topic the guide names, and do not decide any.'));
  assert.ok(preview().includes('Related pages:\n- knowledge/parcel/notes/owner.md (Owner check)'));
  v.pill(card(), 'Ask a question').click();
  type('copy-note', 'What happens to a packed pickup?');
  assert.ok(preview().startsWith('Use the project-knowledge skill to investigate a question about this page.\n\nQuestion: What happens to a packed pickup?'));
  v.btn(card(), 'Close').click();

  // your name is remembered in this browser, nothing else is
  const again = load(data, { storage });
  again.open('Packed pickups');
  again.q('#copy-ai').click();
  again.pill(again.q('#copy-card'), 'I checked it myself').click();
  assert.equal(findAll(again.q('#copy-card'), e => e.id === 'copy-me')[0].value, 'Vadim');
  assert.equal(findAll(again.q('#copy-card'), e => e.id === 'copy-note')[0].value, '');
  // there is no separate request page any more
  assert.equal(load(data, { hash: '#/request' }).h1(), 'Parcel Desk');
}

// --- recent changes ---------------------------------------------------------------
{
  const data = parcel();
  data.live = true;
  data.vaultPath = 'knowledge/parcel';
  data.files = { 'src/pickups.py': { text: 'x', truncated: false } };
  data.warnings = ['notes/cancel.md: changed source src/pickups.py', 'gaps/g-open.md: changed source package.json (uncommitted change, not counted)', 'notes/owner.md: something else'];
  data.nodes.find(n => n.id === 'responses').stale = true;
  data.pending = [{ path: 'notes/owner.md', status: 'changed' }, { path: 'gaps/new-one.md', status: 'added' }];
  data.history = [
    { sha: 'c3c3c3c3c3', date: '2026-11-16', subject: 'Third', more: 0, pages: [{ path: 'notes/cancel.md', status: 'changed', was: 'Old line.', now: 'New line.' }] },
    { sha: 'b2b2b2b2b2', date: '2026-11-15', subject: 'Second', more: 4, pages: [{ path: 'gaps/g-open.md', status: 'added' }, { path: 'notes/dropped.md', status: 'removed' }] },
    { sha: 'a1a1a1a1a1', date: '2026-11-14', subject: 'First', more: 0, pages: [{ path: '00-index.md', status: 'added' }] },
  ];
  const storage = memory();
  const v = load(data, { storage });
  assert.equal(v.q('#header-note').textContent, 'Spec · live from disk');
  assert.deepEqual(v.nav()[1], ['Recent changes', '3 to re-read']);
  v.go('Recent changes');
  const card = id => findAll(v.page(), e => e.id === id)[0];
  const titles = root => findAll(root, e => has(e, 'row')).map(r => (findAll(r, e => has(e, 'grow'))[0] || r).children[0].textContent);
  // pages whose sources changed, from the check warnings and the stale flag
  assert.ok(card('rereads').textContent.startsWith('3 pages need re-reading'));
  assert.deepEqual(titles(card('rereads')), ['Packed pickups', 'Cancelling a pickup', 'Responses']);
  assert.ok(card('rereads').textContent.includes('package.json'));
  assert.deepEqual(findAll(card('rereads'), e => cls(e) === 'wiki').map(text), ['src/pickups.py'], 'a cited file that was sent opens in place');
  v.btn(card('rereads'), 'Copy for AI').click();
  assert.equal(v.copied[0], [
    'Use the project-knowledge skill. These pages cite sources that changed since the last review. Re-read each page against its sources, update the text where the code now differs, and accept the fingerprints only for pages you re-read.',
    '',
    '- knowledge/parcel/gaps/g-open.md (changed: package.json)',
    '- knowledge/parcel/notes/cancel.md (changed: src/pickups.py)',
    '- knowledge/parcel/notes/responses.md',
  ].join('\n'));
  assert.equal(v.q('#toast').textContent, 'Copied 3 pages');
  // pages not committed yet
  assert.deepEqual(titles(card('pending')), ['Owner check', 'gaps/new-one.md']);
  assert.ok(card('pending').textContent.includes('New'));
  // history: commits, the pages in each, and what a summary said before and after
  const commits = () => findAll(v.page(), e => e.tag === 'article');
  const subjects = () => commits().map(c => findAll(c, e => e.tag === 'h3')[0].textContent);
  assert.deepEqual(subjects(), ['Third', 'Second', 'First']);
  assert.ok(commits()[0].textContent.startsWith('2026-11-16 · commit c3c3c3c'));
  // one line per commit: the newest starts open, the rest open on demand
  assert.deepEqual(commits().map(c => findAll(c, e => e.tag === 'details')[0].open === true), [true, false, false]);
  assert.deepEqual(commits().map(c => findAll(c, e => e.tag === 'summary')[0].textContent.replace(/^.*?(\d+ pages?)$/, '$1')), ['1 page', '6 pages', '1 page']);
  // what a summary said before and after sits behind "What changed"
  const what = findAll(commits()[0], e => cls(e) === 'what')[0];
  assert.equal(what.children[0].textContent, 'What changed');
  assert.deepEqual(findAll(what, e => has(e, 'wasnow'))[0].children.map(text), ['wasOld line.', 'nowNew line.']);
  // pages are sorted into spec and gaps, each row saying what happened to the page
  assert.deepEqual(titles(commits()[1]), ['notes/dropped.md', 'Packed pickups', 'and 4 more pages']);
  assert.deepEqual(findAll(commits()[1], e => has(e, 'group')).map(text), ['Spec pages · 1', 'Gaps and plans · 1']);
  assert.deepEqual(findAll(commits()[1], e => has(e, 'tag')).map(text), ['Removed', 'New']);
  assert.deepEqual(findAll(commits()[0], e => has(e, 'group')), [], 'no label for a single group');
  assert.ok(commits()[1].textContent.includes('New') && commits()[1].textContent.includes('Removed'));
  assert.deepEqual(titles(commits()[2]), ['Index page']);
  // a page in the history opens
  v.btn(commits()[0], 'Cancelling a pickup').click();
  assert.equal(v.h1(), 'Cancelling a pickup');
  v.q('#back').click();
  v.btn(card('rereads'), 'Responses').click();
  assert.ok(v.page().textContent.includes('Code changed since the last check'));
  v.q('#back').click();
  // filters
  v.pill(v.page(), 'Gaps').click();
  assert.deepEqual(titles(card('rereads')), ['Packed pickups']);
  assert.deepEqual(titles(card('pending')), ['gaps/new-one.md']);
  assert.deepEqual(subjects(), ['Second']);
  assert.deepEqual(titles(commits()[0]), ['Packed pickups'], 'the "more" line belongs to the unfiltered list');
  v.pill(v.page(), 'Spec pages').click();
  assert.deepEqual(subjects(), ['Third', 'Second']);
  assert.ok(!v.pill(v.page(), 'Since my last visit'), 'nothing is new on a first visit');

  // on a later visit, commits newer than the last one seen are marked
  assert.equal(storage.getItem('spec-viewer:Parcel Desk:seen'), '"c3c3c3c3c3"');
  storage.setItem('spec-viewer:Parcel Desk:seen', '"a1a1a1a1a1"');
  data.warnings = [];
  data.nodes.find(n => n.id === 'responses').stale = false;
  const later = load(data, { storage });
  assert.deepEqual(later.nav()[1], ['Recent changes', '2 new']);
  later.go('Recent changes');
  assert.equal(findAll(later.page(), e => e.id === 'rereads').length, 0);
  later.pill(later.page(), 'Since my last visit').click();
  const fresh = findAll(later.page(), e => e.tag === 'article');
  assert.deepEqual(fresh.map(c => findAll(c, e => e.tag === 'h3')[0].textContent), ['Third', 'Second']);
  assert.ok(fresh[0].textContent.includes('· new'));

  // without the serve command there is no history, and the page says so
  const bare = load(parcel());
  bare.go('Recent changes');
  assert.ok(bare.page().textContent.includes('History is shown when the spec is opened with the serve command.'));
  data.history = [];
  const empty = load(data);
  empty.go('Recent changes');
  assert.ok(empty.page().textContent.includes('No Git history was found for this vault.'));
}

// --- cited files open inside the viewer ---------------------------------------------
{
  const v = load({
    title: 'Files', live: true, vaultPath: 'knowledge/demo',
    files: {
      'docs/plan.md': { text: '# Plan\n\n| Task | Status |\n| --- | :-- |\n| CJ-01 — notes | Done \\| ok |\n| `a|b` | [[notes/n|N]] | extra |\n\nSee [code](../src/a.py#L2) and [web](https://example.com).', truncated: false },
      'src/a.py': { text: 'one\ntwo\nthree', truncated: true },
    },
    nodes: [
      spec('a', 'Area', 'area', []),
      spec('n', 'N', 'note', ['a'], {
        summary: 'Plain words.', sources: ['src/a.py', 'src/missing.py'],
        body: '[plan](../../../docs/plan.md#L3) and [raw](<../../../src/a.py#L2-L3>) and [gone](../../../docs/none.md) and [up](../../../../outside.md)',
      }),
    ],
    edges: [{ source: 'a', target: 'n' }],
  });
  v.open('N');
  const fileLinks = findAll(v.article(), e => e.tag === 'button' && cls(e) === 'wiki');
  assert.deepEqual(fileLinks.map(text), ['plan', 'raw']);
  assert.deepEqual(findAll(v.article(), e => e.tag === 'a').map(text), ['gone', 'up'], 'files that were not sent stay ordinary links');
  const pane = v.q('#filepane'), body = v.q('#file-body');
  const rows = () => findAll(body, e => has(e, 'ln'));
  const hits = () => rows().filter(e => has(e, 'hit')).map(e => findAll(e, x => cls(x) === 'txt')[0].textContent);
  const actions = () => findAll(v.q('#file-actions'), e => e.tag === 'button');
  // a Markdown document opens rendered, with its table
  fileLinks[0].click();
  assert.equal(pane.hidden, false);
  assert.equal(v.q('#file-title').textContent, 'docs/plan.md');
  assert.equal(v.q('#file-note').textContent, 'Line 3 · Read from disk when this page loaded');
  assert.deepEqual(actions().map(e => [e.textContent, e.attrs['aria-pressed']]), [['Document', 'true'], ['Source lines', 'false']]);
  assert.deepEqual(findAll(body, e => e.tag === 'th').map(text), ['Task', 'Status']);
  assert.deepEqual(findAll(body, e => e.tag === 'td').map(text), ['CJ-01 — notes', 'Done | ok', 'a|b', 'N']);
  // its source lines, with the cited line marked
  actions()[1].click();
  assert.equal(rows().length, 8);
  assert.deepEqual(hits(), ['| Task | Status |']);
  actions()[0].click();
  // links inside the document resolve from the document's own folder
  findAll(body, e => e.tag === 'button' && cls(e) === 'wiki').find(e => e.textContent === 'code').click();
  assert.equal(v.q('#file-title').textContent, 'src/a.py');
  assert.equal(v.q('#file-note').textContent, 'Line 2 · Read from disk when this page loaded · only the beginning of the file is shown');
  assert.deepEqual(rows().map(text), ['1one', '2two', '3three']);
  assert.deepEqual(hits(), ['two']);
  v.q('#file-close').click();
  assert.equal(pane.hidden, true);
  fileLinks[1].click();
  assert.deepEqual(hits(), ['two', 'three']);
  pane.fire('keydown', { key: 'Escape' });
  assert.equal(pane.hidden, true);
  // the page's source list opens the same way
  const sources = findAll(v.page(), e => e.tag === 'details').find(d => d.textContent.startsWith('Source files (2)'));
  assert.deepEqual(findAll(sources, e => e.tag === 'button').map(text), ['src/a.py']);
  assert.ok(sources.textContent.includes('src/missing.py'));
  findAll(sources, e => e.tag === 'button')[0].click();
  assert.equal(v.q('#file-title').textContent, 'src/a.py');
  assert.deepEqual(hits(), []);
}

// --- Markdown rendering ----------------------------------------------------------
function article(body) {
  const v = load({ title: 'Md', nodes: [
    node({ id: 'n', title: 'N', type: 'note', layer: 'spec', status: 'current', path: 'notes/n.md', areas: [], body }),
    node({ id: 'l', title: 'Legacy', type: 'note', layer: 'spec', status: 'current', path: 'notes/legacy.md', areas: [] }),
  ], edges: [] });
  assert.deepEqual(v.tree(), ['Legacy', 'N'], 'notes without an area are still in the tree');
  v.treeRow('N').click();
  return { v, art: v.article() };
}
const pres = art => findAll(art, e => e.tag === 'pre').map(text);

assert.deepEqual(pres(article('````md\n```js\ninner\n```\n````\nafter').art), ['```js\ninner\n```'], 'longer fence wraps shorter one');
assert.deepEqual(pres(article('~~~\ntilde ```\nx\n~~~\n').art), ['tilde ```\nx'], 'tilde fence');
assert.deepEqual(pres(article('```\nx\n~~~\ny\n```').art), ['x\n~~~\ny'], 'other character does not close');
assert.deepEqual(pres(article('````\na\n```\nb\n````').art), ['a\n```\nb'], 'shorter closer does not close');
assert.deepEqual(pres(article('```\nx\n```js\ny\n```').art), ['x\n```js\ny'], 'closer with info string does not close');
assert.deepEqual(pres(article('``` a`b\ntext').art), [], 'backtick in info string is not a fence');
assert.deepEqual(pres(article('~~~ a`b\ntext\n~~~').art), ['text'], 'backtick is fine in a tilde info string');
assert.deepEqual(pres(article('```\nunclosed').art), ['unclosed'], 'unclosed fence still rendered');
assert.deepEqual(pres(article('```js\none\n```\n\ntext\n\n```\ntwo\n```').art), ['one', 'two']);
{
  // wikilink with escaped pipe inside a table row
  const { v, art } = article('| Link | Other |\n| --- | --- |\n| [[notes/legacy\\|Alias]] | [[notes/legacy|Plain]] |');
  const wiki = findAll(art, e => e.tag === 'button' && cls(e) === 'wiki');
  assert.deepEqual(wiki.map(text), ['Alias', 'Plain']);
  wiki[0].click();
  assert.equal(v.h1(), 'Legacy', 'escaped pipe resolves to notes/legacy');
}
{
  // inline formatting and hostile text
  const { art } = article('**[[notes/legacy|label]]** and **[source](https://example.com)** and **`code`**');
  const strongs = findAll(art, e => e.tag === 'strong');
  assert.equal(findAll(strongs[0], e => e.tag === 'button').length, 1);
  assert.equal(findAll(strongs[1], e => e.tag === 'a')[0].href, 'https://example.com/');
  assert.equal(findAll(strongs[2], e => e.tag === 'code').length, 1);
  const hostile = article('<img src=x onerror=alert(1)> [bad](javascript:alert) [ok](mailto:a@b.c)\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\nnot | a table').art;
  assert.equal(findAll(hostile, e => e.tag === 'img').length, 0);
  assert.deepEqual(findAll(hostile, e => e.tag === 'a').map(e => e.href), ['mailto:a@b.c']);
  assert.ok(hostile.textContent.includes('<img src=x onerror=alert(1)>'));
  assert.deepEqual(findAll(hostile, e => e.tag === 'td').map(text), ['1', '2']);
  assert.ok(findAll(hostile, e => e.tag === 'p').some(e => e.textContent === 'not | a table'));
}

// --- a feature with parts: area, feature, part -----------------------------------------
{
  const v = load({
    title: 'Parts',
    nodes: [
      spec('community', 'Community', 'area', []),
      spec('chats', 'Chats', 'note', ['community'], { summary: 'Members talk.', body: 'Parts: [[notes/group-chats|group chats]] and [[notes/direct-chats|direct chats]].' }),
      spec('group-chats', 'Group chats', 'note', ['community'], { parent: 'chats', summary: 'Staff-run rooms.' }),
      spec('direct-chats', 'Direct chats', 'note', ['community'], { parent: 'chats' }),
      spec('follows', 'Follows', 'note', ['community']),
      // not nested: its parent is itself a part, and one names a page that is not there
      spec('deep', 'Deep', 'note', ['community'], { parent: 'group-chats' }),
      spec('lost', 'Lost', 'note', ['community'], { parent: 'nobody' }),
    ],
    edges: [{ source: 'community', target: 'chats' }, { source: 'chats', target: 'group-chats' }, { source: 'chats', target: 'direct-chats' }, { source: 'community', target: 'follows' }],
  });
  v.twist('Community').click();
  assert.deepEqual(v.tree(), ['Community', 'Chats', 'Deep', 'Follows', 'Lost'], 'parts are folded under their feature');
  assert.equal(v.treeRow('Chats').textContent, 'Chats2 parts');
  v.treeRow('Chats').click();
  assert.deepEqual(v.tree(), ['Community', 'Chats', 'Direct chats', 'Group chats', 'Deep', 'Follows', 'Lost']);
  assert.ok(has(v.treeRow('Group chats'), 'part') && !has(v.treeRow('Follows'), 'part'));
  assert.equal(v.treeRow('Chats').textContent, 'Chats', 'the count is gone once the parts are shown');
  v.treeRow('Group chats').click();
  assert.deepEqual(v.crumbs(), ['Parts', '/', 'Community', '/', 'Chats', '/', 'Group chats']);
  assert.deepEqual(v.tree().slice(1, 4), ['Chats', 'Direct chats', 'Group chats'], 'the parts stay open while reading one of them');
  const here = findAll(v.page(), e => cls(e) === 'here-path')[0];
  assert.deepEqual(here.children.map(text), ['Parts', 'Community', 'Chats', 'Group chats']);
  assert.deepEqual(v.related(), [], 'the feature is in the path, not repeated under Related');
  v.treeRow('Follows').click();
  assert.deepEqual(v.tree(), ['Community', 'Chats', 'Deep', 'Follows', 'Lost'], 'and fold again elsewhere');
  // the area page names the parts under their feature
  v.treeRow('Community').click();
  const chats = findAll(v.page(), e => has(e, 'feature')).find(f => f.children[0].textContent === 'Chats');
  assert.ok(chats.textContent.includes('2 parts: Direct chats, Group chats'));
  assert.equal(findAll(v.page(), e => has(e, 'feature')).length, 4, 'a part has no row of its own on the area page');
  v.btn(chats, 'Group chats').click();
  assert.equal(v.h1(), 'Group chats');
}

// --- overview of a big spec, a gap's pages, and the wheel on the map ---------------------
{
  const names = ['Alpha', 'Beta', 'Delta', 'Epsilon', 'Eta', 'Gamma', 'Zeta'];
  const v = load({
    title: 'Big',
    nodes: [
      spec('shop', 'Shop', 'area', [], { summary: 'Buying things.' }),
      spec('empty', 'Empty', 'area', []),
      ...names.map(n => spec(n.toLowerCase(), n, 'note', ['shop'])),
      spec('alpha-part', 'Alpha part', 'note', ['shop'], { parent: 'alpha' }),
      gap('g-about', 'Does it ship?', { state: 'needs-recheck', areas: ['shop'] }),
      gap('g-loose', 'Nobody knows', { state: 'needs-decision', areas: [] }),
    ],
    edges: [{ source: 'shop', target: 'g-about' }, { source: 'g-about', target: 'beta' }, { source: 'g-about', target: 'alpha' }],
  });
  const cards = findAll(v.page(), e => has(e, 'area-card'));
  assert.deepEqual(cards.map(c => c.children[0].textContent), ['Empty', 'Shop']);
  const shop = cards[1];
  assert.ok(shop.textContent.includes('Buying things.') && shop.textContent.includes('8 pages · 1 open question'));
  const listed = findAll(shop, e => has(e, 'names'))[0].children.map(text);
  assert.deepEqual(listed, ['Alpha', 'Beta', 'Delta', 'Epsilon', 'Eta', 'All 7 features'], 'five names, then the way to the rest; parts are not named');
  assert.equal(findAll(cards[0], e => has(e, 'names')).length, 0);
  assert.ok(cards[0].textContent.includes('0 pages'));
  v.btn(shop, 'All 7 features').click();
  assert.equal(v.h1(), 'Shop');
  assert.equal(findAll(v.page(), e => has(e, 'feature')).length, 7, 'the area page still lists every feature');

  // a gap names the features it is about, then its area
  v.go('Gaps');
  v.btn(v.page(), 'Does it ship?').click();
  const lists = () => findAll(v.page(), e => cls(e) === 'recent').map(l => l.children.map(text));
  assert.deepEqual(lists()[0], ['This gap is about', 'Alpha', 'Beta', 'Shop · area']);
  assert.equal(lists()[1][0], 'Recently viewed');
  v.btn(findAll(v.page(), e => cls(e) === 'recent')[0], 'Beta').click();
  assert.equal(v.h1(), 'Beta');
  v.go('Gaps');
  v.btn(v.page(), 'Nobody knows').click();
  assert.ok(!v.page().textContent.includes('This gap is about'), 'nothing to name when the gap links to no page');

  // the wheel zooms the map about the pointer, within limits
  v.go('Map');
  const graph = v.q('#graph');
  graph.getBoundingClientRect = () => ({ left: 0, top: 0, width: 1000, height: 500 });
  const box = () => graph.attrs.viewBox.split(' ').map(Number);
  const [x0, y0, w0, h0] = box();
  let stopped = 0;
  const wheel = (deltaY, clientX, clientY) => graph.fire('wheel', { deltaY, clientX, clientY, preventDefault: () => stopped++ });
  wheel(-50, 1000, 500);
  let [x, y, w, h] = box();
  assert.ok(w < w0 && h < h0, 'scrolling up zooms in');
  assert.ok(Math.abs(x + w - (x0 + w0)) < 1e-6 && Math.abs(y + h - (y0 + h0)) < 1e-6, 'the point under the pointer stays put');
  assert.equal(stopped, 1, 'the page does not scroll while the map zooms');
  wheel(50, 1000, 500);
  assert.ok(box().every((n, i) => Math.abs(n - [x0, y0, w0, h0][i]) < 1e-6), 'and back out again');
  for (let i = 0; i < 40; i++) wheel(-60, 500, 250);
  assert.ok(Math.abs(box()[2] - w0 / 8) < 1e-6, 'zooming in stops at 8x');
  for (let i = 0; i < 80; i++) wheel(60, 500, 250);
  assert.ok(Math.abs(box()[2] - w0 * 4) < 1e-6, 'zooming out stops at 4x');
  wheel(0, 0, 0);
  assert.equal(stopped, 122, 'a sideways scroll is left alone');
}

// --- a built page: a copy for a server, read without the repository -------------------
{
  const page = (extra = {}) => load({
    title: 'Built', built: true, commit: 'abcdef1234567890', generatedAt: '2026-11-17T10:00:00+00:00', vaultPath: 'knowledge/demo',
    nodes: [
      spec('a', 'Area', 'area', []),
      spec('n', 'N', 'note', ['a'], {
        summary: 'Plain words.', sources: ['src/a.py', 'src/dir with space/b.py'],
        body: '[code](../../../src/a.py#L2-L3) and [web](https://example.com/x) and [up](../../../../outside.md)',
      }),
    ],
    edges: [{ source: 'a', target: 'n' }],
    ...extra,
  });
  const sourcesOf = v => findAll(v.page(), e => e.tag === 'details').find(d => d.textContent.startsWith('Source files (2)'));
  // without a code host: file names are text, never links into the site that hosts the page
  let v = page();
  assert.equal(v.q('#header-note').textContent, 'Spec · built 2026-11-17');
  assert.equal(v.q('#header-note').title, 'Built from commit abcdef1234567890');
  v.open('N');
  assert.deepEqual(findAll(v.article(), e => e.tag === 'a').map(a => [a.textContent, a.href]),
    [['web', 'https://example.com/x'], ['up', findAll(v.article(), e => e.tag === 'a')[1].href]], 'only the address and the path outside the repository are links');
  const named = findAll(v.article(), e => e.tag === 'span' && e.title === 'src/a.py');
  assert.deepEqual(named.map(text), ['code']);
  assert.equal(findAll(sourcesOf(v), e => e.tag === 'a' || e.tag === 'button').length, 0);
  assert.ok(sourcesOf(v).textContent.includes('src/a.py'));
  // with a code host: cited files open there, at the cited lines, in a new tab
  v = page({ sourceUrl: 'https://github.com/o/r/blob/abcdef1234567890/' });
  v.open('N');
  const code = findAll(v.article(), e => e.tag === 'a').find(a => a.textContent === 'code');
  assert.equal(code.href, 'https://github.com/o/r/blob/abcdef1234567890/src/a.py#L2-L3');
  assert.deepEqual([code.target, code.rel], ['_blank', 'noopener noreferrer']);
  assert.deepEqual(findAll(sourcesOf(v), e => e.tag === 'a').map(a => a.href),
    ['https://github.com/o/r/blob/abcdef1234567890/src/a.py', 'https://github.com/o/r/blob/abcdef1234567890/src/dir%20with%20space/b.py']);
  // an address that is not http(s) is ignored, and a page that is not built ignores it too
  v = page({ sourceUrl: 'javascript:alert(1)' });
  v.open('N');
  assert.equal(findAll(sourcesOf(v), e => e.tag === 'a').length, 0);
  v = page({ built: false, live: true, sourceUrl: 'https://github.com/o/r/blob/main' });
  v.open('N');
  assert.equal(findAll(sourcesOf(v), e => e.tag === 'a').length, 0);
  // text that was included still opens in place
  v = page({ sourceUrl: 'https://github.com/o/r/blob/main', files: { 'src/a.py': { text: 'one\ntwo\nthree', truncated: false } } });
  v.open('N');
  findAll(v.article(), e => e.tag === 'button' && cls(e) === 'wiki').find(e => e.textContent === 'code').click();
  assert.equal(v.q('#file-note').textContent, 'Lines 2–3 · Copy taken when this page was built');
  v.q('#file-close').click();
  v.go('Recent changes');
  assert.ok(v.page().textContent.includes('No Git history was found for this vault.'));
}

// a long queue comes in portions of 40, and the place is kept until a filter changes
{
  const many = Array.from({ length: 95 }, (_, i) => gap('g-many-' + i, 'Many ' + String(i).padStart(2, '0'), { state: 'needs-recheck', kind: 'product-gap' }));
  const v = load({ ...queue, nodes: [...queue.nodes, ...many] });
  v.go('Gaps');
  const more = () => findAll(v.page(), e => has(e, 'more-row'))[0];
  assert.equal(v.rowTitles().length, 40);
  assert.deepEqual(more().children.map(text), ['Show 40 more', '40 of 103']);
  v.btn(more(), 'Show 40 more').click();
  assert.equal(v.rowTitles().length, 80);
  assert.deepEqual(more().children.map(text), ['Show 23 more', '80 of 103']);
  v.go('Overview');
  v.go('Gaps');
  assert.equal(v.rowTitles().length, 80, 'coming back to the queue keeps the place');
  v.btn(more(), 'Show 23 more').click();
  assert.equal(v.rowTitles().length, 103);
  assert.deepEqual(more().children.map(text), ['103 of 103']);
  v.tab(v.page(), 'Needs recheck').click();
  assert.equal(v.rowTitles().length, 40, 'another filter starts from the first portion');
  v.tab(v.page(), 'History').click();
  assert.equal(more().children.length, 0, 'a list that fits in one portion has no count and no button');
}

// when a gap appeared: on its row and its page, and the queue can list the newest first
{
  const dated = { 'g-decision': '2026-11-12', 'g-recheck': '2026-11-03', 'g-accepted': '2026-10-20' };
  const v = load({ ...queue, nodes: queue.nodes.map(n => (dated[n.id] ? { ...n, added: dated[n.id] } : n)) });
  v.go('Gaps');
  const row = title => v.rows().find(r => r.textContent.startsWith(title)).textContent;
  assert.ok(row('Gap recheck').endsWith('Added 2026-11-03Needs recheck'), row('Gap recheck'));
  assert.ok(!row('Gap derived').includes('Added'), 'no date, no word about it');
  assert.deepEqual(findAll(v.select('Order'), e => e.tag === 'option').map(text), ['Most urgent first', 'Newest first']);
  v.select('Order').value = 'newest';
  v.select('Order').fire('change');
  const order = v.rowTitles();
  assert.deepEqual(order.filter(t => ['Gap decision', 'Gap recheck', 'Gap accepted'].includes(t)), ['Gap decision', 'Gap recheck', 'Gap accepted']);
  assert.ok(order.indexOf('Gap derived') < order.indexOf('Gap decision'), 'a gap with no date is a page not committed yet, so it is the newest');
  v.tab(v.page(), 'History').click();
  assert.deepEqual(findAll(v.select('Order'), e => e.tag === 'option').map(text), ['Last closed first', 'Newest first']);
  v.select('Order').value = 'urgent';
  v.select('Order').fire('change');
  v.tab(v.page(), 'Open').click();
  v.btn(v.page(), 'Gap recheck').click();
  assert.ok(v.page().textContent.includes('Added2026-11-03'), 'the gap page says when it appeared');
}

// a button that copies says so on itself for a moment; the message is kept for screen readers
{
  const v = load(parcel(), { hash: '#/page/notes/owner', timers: true });
  const link = v.q('#copy-link');
  link.textContent = 'Copy link';
  link.className = 'btn';
  link.click();
  assert.equal(link.textContent, 'Link copied');
  assert.ok(has(link, 'said'));
  assert.deepEqual([v.q('#toast').textContent, v.q('#toast').className], ['Link copied', 'toast quiet']);
  link.click();
  assert.equal(link.textContent, 'Link copied', 'pressing again while it says so keeps the real label for later');
  v.tick();
  assert.equal(link.textContent, 'Copy link');
  assert.ok(!has(link, 'said'));
  assert.equal(v.q('#toast').textContent, '');
}

console.log('PASS: viewer navigation, pages, gaps, map, search, copy for AI, changes, cited files, parts, overview cards, built page, Markdown');
