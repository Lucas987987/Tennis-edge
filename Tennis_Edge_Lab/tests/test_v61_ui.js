const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const lab = path.join(__dirname, '..');
const script = fs.readFileSync(path.join(lab, 'research_v61.js'), 'utf8');

function fixture() {
  const elements = new Map();
  const calls = [];
  const element = id => {
    if (!elements.has(id)) {
      elements.set(id, {
        innerHTML: '',
        textContent: '',
        value: '',
        disabled: false,
        options: [{ value: '', textContent: 'Tous' }],
        listeners: {},
        addEventListener(name, callback) { this.listeners[name] = callback; },
        replaceChildren(first) { this.options = first ? [first] : []; },
        append(option) { this.options.push(option); },
      });
    }
    return elements.get(id);
  };
  const segment = (book, reason, roi) => ({
    market: 'match', book, circuit: 'ATP', horizon: '1h', selection: 'favori',
    predicates: [{
      dimension: 'tranche_cote', operator: 'range', value: '4,00 ≤ cote < 8,00',
      interval: { lower: 4, upper: 8 },
    }],
    rejection_reasons: [reason], primary_rejection_reason: reason,
    unique_matches: 60, distinct_days: 20, wins: 31, mean_odds: 2.4,
    roi_pct: roi, roi_ci95: [-5, 15], pnl_units: 2,
    clv_mean_pct: 1, clv_n: 40, p_nominal: .3, p_holm: .9,
  });
  const pages = {
    './live/archive/bookmakers_sets_v61/current/match/page-00001.json': {
      schema_version: 1, market: 'match', page: 1, segments: [
        segment('book-a', 'effectif', 4), segment('book-b', 'Holm', -2),
      ],
    },
    './live/archive/bookmakers_sets_v61/current/match/page-00002.json': {
      schema_version: 1, market: 'match', page: 2, segments: [
        segment('book-c', 'IC95', 3),
      ],
    },
  };
  const audit = {
    schema_version: 1, segment_count: 3, tested_segments: 3,
    generated_at: '2026-10-12T00:00:00Z', source_hash_sha256: 'source-hash',
    archive: {
      manifest: 'live/archive/bookmakers_sets_v61/current/manifest.json',
      source_snapshot_sha256: 'source-snapshot',
    },
    rejection_counts_multiple_causes: { Holm: 1, effectif: 1, IC95: 1 },
    rejection_counts_by_bookmaker: { 'book-a': {}, 'book-b': {}, 'book-c': {} },
    rejection_counts_by_circuit: { ATP: {} },
    rejection_counts_by_horizon: { '1h': {} },
    rejection_counts_by_primary_reason: { Holm: {}, effectif: {}, IC95: {} },
    markets: {
      match: { best_positive: [], worst_negative: [] },
      set1: { best_positive: [], worst_negative: [] },
      set2: { best_positive: [], worst_negative: [] },
    },
  };
  const manifest = {
    source_snapshot_sha256: 'source-snapshot',
    markets: {
      match: {
        segment_count: 3, compressed_jsonl: 'Tennis_Edge_Lab/live/archive/match.jsonl.gz',
        compressed_sha256: 'archive-hash',
        pages: [
          'Tennis_Edge_Lab/live/archive/bookmakers_sets_v61/current/match/page-00001.json',
          'Tennis_Edge_Lab/live/archive/bookmakers_sets_v61/current/match/page-00002.json',
        ],
      },
      set1: {
        pages: [], segment_count: 0,
        compressed_jsonl: 'Tennis_Edge_Lab/live/archive/set1.jsonl.gz',
        compressed_sha256: 'empty-archive-hash',
      },
      set2: { pages: [], segment_count: 0 },
    },
  };
  const prospective = {
    schema_version: 1, total_frozen: 1, ledger_tip: 'ledger-tip',
    policy_version: 'candidate-watch-admission-1.0', planned_checkpoints_days: [30, 60, 90],
    candidates: [{
      candidate_id: 'candidate-signature',
      market: 'match', book: 'book-a', horizon: '1h', selection: 'favori',
      criteria: [{ dimension: 'circuit', value: 'ATP' }],
      predicates: [{ dimension: 'tranche_cote', interval: { lower: 4, upper: 8 }, value: '4,00 ≤ cote < 8,00' }],
      freeze_date_utc: '2026-10-01', eligible_after_utc: '2026-10-02',
      discovery_period: { start: '2026-08-01', end: '2026-09-30' },
      source_snapshot_sha256: 'source-snapshot', source_commit: 'commit-sha',
      state: 'observation exploratoire',
      historical_context: { roi_pct: -8, roi_ci95: [-20, 4], clv_mean_pct: -2, pnl_units: -4 },
      checkpoints: [],
    }],
  };
  const responses = {
    './live/bookmakers_sets_audit.json': audit,
    './live/candidate_watch_v61_prospective.json': prospective,
    './live/archive/bookmakers_sets_v61/current/manifest.json': manifest,
    ...pages,
  };
  const tabs = ['v61Audit', 'v61Candidates'].map(name => ({
    dataset: { tab: name }, addEventListener(event, callback) { this.click = callback; },
  }));
  const context = {
    document: {
      getElementById: element,
      createElement: () => ({ value: '', textContent: '' }),
      querySelectorAll: () => tabs,
    },
    fetch: async url => {
      const key = Object.keys(responses).find(candidate => url.startsWith(candidate));
      calls.push(key || url);
      if (!key) return { ok: false, status: 404 };
      return { ok: true, json: async () => responses[key] };
    },
  };
  vm.runInNewContext(script, context);
  return { element, calls, tabs };
}

test('charge chaque page d’archive à la demande et filtre la page mobile', async () => {
  const { element, calls, tabs } = fixture();
  tabs[0].click();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(calls.filter(value => value.includes('page-')).length, 1);
  assert.match(element('v61AuditRows').innerHTML, /book-a/);
  assert.match(element('v61AuditRows').innerHTML, /4,00 ≤ cote &lt; 8,00/);
  assert.match(element('v61AuditRows').innerHTML, /effectif/);
  assert.match(element('v61CandidateCards').innerHTML, /-8/);
  assert.match(element('v61CandidateCards').innerHTML, /observation exploratoire/);

  element('v61ReasonFilter').value = 'Holm';
  element('v61ReasonFilter').listeners.change();
  assert.doesNotMatch(element('v61AuditRows').innerHTML, /book-a/);
  assert.match(element('v61AuditRows').innerHTML, /book-b/);
  element('v61SampleFilter').value = '61';
  element('v61SampleFilter').listeners.change();
  assert.doesNotMatch(element('v61AuditRows').innerHTML, /book-b/);
  element('v61SampleFilter').value = '0';
  element('v61SampleFilter').listeners.change();

  element('v61Next').listeners.click();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(calls.filter(value => value.includes('page-')).length, 2);
  assert.doesNotMatch(element('v61AuditRows').innerHTML, /book-c/);
  element('v61ReasonFilter').value = '';
  element('v61ReasonFilter').listeners.change();
  assert.match(element('v61AuditRows').innerHTML, /book-c/);
  assert.match(element('v61PageIndicator').textContent, /2\/2/);

  element('v61MarketFilter').value = 'set1';
  element('v61MarketFilter').listeners.change();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.match(element('v61PageIndicator').textContent, /1\/1/);
  assert.match(element('v61ArchiveInfo').textContent, /0 segment/);
  assert.match(element('v61CompressedArchive').href, /set1\.jsonl\.gz/);
});

test('le HTML raccorde la navigation accessible et les exports complets', () => {
  const html = fs.readFileSync(path.join(lab, 'research.html'), 'utf8');
  assert.match(html, /data-tab="v61Audit"/);
  assert.match(html, /data-tab="v61Candidates"/);
  assert.match(html, /v61CompressedArchive/);
  assert.match(html, /research_v61\.js/);
  assert.match(html, /aria-live="polite"/);
});
