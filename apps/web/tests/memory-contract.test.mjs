import assert from 'node:assert/strict';
import test from 'node:test';
import { buildMemoryCreatePayload, normalizeMemorySearchResponse } from '../app/components/memory-contract.ts';

test('new memory uses a backend-supported working type', () => {
  const payload = buildMemoryCreatePayload({
    content: '  Onthoud dit  ', source: '  gebruiker  ', confidence: '0.7', review_note: '  gecontroleerd  ',
  });
  assert.deepEqual(payload, {
    content: 'Onthoud dit', memory_type: 'working', source: 'gebruiker', confidence: 0.7, review_note: 'gecontroleerd',
  });
  assert.notEqual(payload.memory_type, 'semantic');
});

test('search reads the retrieval results envelope and preserves provenance', () => {
  const items = normalizeMemorySearchResponse({ retrieval: { results: [{
    id: 'memory-1', kind: 'memory', excerpt: 'Gaia gebruikt Nederlands', memory_type: 'preference',
    confidence: 0.9, status: 'active', source_ref: { source: 'owner interview' },
  }, {
    id: 'source-1', kind: 'source_record', excerpt: 'Installatie-instructies', source_type: 'repo_doc',
    confidence: 0.8, status: 'active', source_ref: { title: 'Installatie', source_ref: 'docs/install.md' },
  }] } });
  assert.deepEqual(items.map(item => ({ id: item.id, content: item.content, source: item.source, kind: item.kind })), [
    { id: 'memory-1', content: 'Gaia gebruikt Nederlands', source: 'owner interview', kind: 'memory' },
    { id: 'source-1', content: 'Installatie-instructies', source: 'Installatie', kind: 'source_record' },
  ]);
});

test('search rejects the obsolete top-level items shape and malformed matches', () => {
  assert.throws(() => normalizeMemorySearchResponse({ items: [] }), /Onverwacht zoekantwoord/);
  assert.throws(() => normalizeMemorySearchResponse({ retrieval: { results: [{ id: 'memory-1', kind: 'memory' }] } }), /zoekresultaat/);
});
