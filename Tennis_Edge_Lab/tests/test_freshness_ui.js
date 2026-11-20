const assert = require('node:assert/strict');
const test = require('node:test');
const { liveState, age } = require('../freshness.js');

test('un rapport ok devient ancien quand son âge dépasse le seuil', () => {
  const now = Date.parse('2026-10-14T12:00:00Z');
  const entry = { state: 'ok', generated_at: '2026-10-13T00:00:00Z', max_age_hours: 12 };
  assert.equal(liveState(entry, now), 'ancien');
  assert.equal(liveState({ ...entry, generated_at: '2026-10-14T10:00:00Z' }, now), 'ok');
});

test('un état pending, error ou absent n\'est jamais requalifié en ok', () => {
  const now = Date.now();
  for (const state of ['pending', 'error', 'missing', 'not_published', 'ancien_conserve']) {
    assert.equal(liveState({ state, generated_at: new Date(now).toISOString(), max_age_hours: 99 }, now), state);
  }
});

test('age formate heures et jours', () => {
  const now = Date.parse('2026-10-14T12:00:00Z');
  assert.equal(age('2026-10-14T10:00:00Z', now), '2.0 h');
  assert.equal(age('2026-10-10T12:00:00Z', now), '4.0 j');
  assert.equal(age('n/a', now), '—');
});
