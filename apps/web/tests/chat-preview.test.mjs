import test from 'node:test';
import assert from 'node:assert/strict';
import { previewStillMatches } from '../app/components/chat-preview.ts';

test('chat preview remains valid across polling when its included context is unchanged', () => {
  const preview = { included_messages: [
    { role: 'user', content: 'Eerdere vraag' },
    { role: 'assistant', content: 'Eerder antwoord' },
    { role: 'user', content: 'Nieuwe vraag' },
  ] };
  assert.equal(previewStillMatches(preview, [
    { role: 'user', content: 'Eerdere vraag', status: 'complete' },
    { role: 'assistant', content: 'Eerder antwoord', status: 'complete' },
  ]), true);
});

test('chat preview becomes invalid when polling reveals a changed assistant context', () => {
  const preview = { included_messages: [
    { role: 'user', content: 'Eerdere vraag' },
    { role: 'assistant', content: 'Eerder antwoord' },
    { role: 'user', content: 'Nieuwe vraag' },
  ] };
  assert.equal(previewStillMatches(preview, [
    { role: 'user', content: 'Eerdere vraag', status: 'complete' },
    { role: 'assistant', content: 'Nieuw antwoord', status: 'complete' },
  ]), false);
});
