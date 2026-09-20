import assert from 'node:assert/strict';
import test from 'node:test';
import { buildResearchFields, buildResearchRunBody, normalizeResearch } from '../lib/research-contract.ts';

test('normalizes bounded provider results and preview gate', () => {
  const value = normalizeResearch({
    provider: 'firecrawl', status: 'preview_ready', risk: 'R1', execution_allowed: true,
    preview_fingerprint: 'fingerprint', preview_id: 'connector-check-1',
    results: Array.from({ length: 7 }, (_, index) => ({ title: `Source ${index}`, url: `https://example.com/${index}`, secret: 'drop' })),
  });
  assert.equal(value.sources.length, 5);
  assert.equal(value.executionAllowed, true);
  assert.equal(value.previewId, 'connector-check-1');
  assert.equal('secret' in value.sources[0], false);
});

test('builds exact preview and run request contract', () => {
  const fields = buildResearchFields('  bounded query ', ' Example.com,docs.example.com ', 9);
  assert.deepEqual(fields, { query: 'bounded query', allowed_domains: ['example.com', 'docs.example.com'], max_results: 5 });
  assert.deepEqual(buildResearchRunBody(fields, normalizeResearch({ preview_fingerprint: 'fp', preview_id: 'preview-1', execution_allowed: true })), {
    ...fields, preview_fingerprint: 'fp', preview_id: 'preview-1',
  });
});

test('malformed response cannot unlock execution', () => {
  const value = normalizeResearch({ ok: true, execution_allowed: 'true', results: [{ url: 42 }] });
  assert.equal(value.executionAllowed, false);
  assert.deepEqual(value.sources, []);
});
