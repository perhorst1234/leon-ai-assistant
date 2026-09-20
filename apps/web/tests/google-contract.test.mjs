import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildCalendarPreviewPayload, defaultCalendarDraft, formatGoogleDate, normalizeCalendarPreview,
  normalizeGoogleStatus, normalizeMailPreview,
} from '../app/components/google-contract.ts';

test('calendar defaults to seven days in Amsterdam and sends a fixed bounded payload', () => {
  const draft = defaultCalendarDraft(new Date('2026-09-10T08:15:00Z'));
  assert.deepEqual(draft, { start: '2026-09-10T10:15', end: '2026-09-17T10:15' });
  assert.deepEqual(buildCalendarPreviewPayload(draft), {
    start: '2026-09-10T08:15:00.000Z', end: '2026-09-17T08:15:00.000Z', timezone: 'Europe/Amsterdam', limit: 10,
  });
});

test('calendar rejects reversed, oversized, and nonexistent local ranges before sending', () => {
  assert.throws(() => buildCalendarPreviewPayload({ start: '2026-09-10T10:00', end: '2026-09-10T09:00' }), /na de starttijd/);
  assert.throws(() => buildCalendarPreviewPayload({ start: '2026-09-10T10:00', end: '2026-09-18T10:00' }), /maximaal zeven lokale dagen/);
  assert.throws(() => buildCalendarPreviewPayload({ start: '2026-03-29T02:30', end: '2026-03-29T03:30' }), /bestaat niet/);
});

test('seven Amsterdam calendar days remain valid across DST end', () => {
  const draft = defaultCalendarDraft(new Date('2026-10-20T08:00:00Z'));
  assert.deepEqual(draft, { start: '2026-10-20T10:00', end: '2026-10-27T10:00' });
  assert.deepEqual(buildCalendarPreviewPayload(draft), {
    start: '2026-10-20T08:00:00.000Z', end: '2026-10-27T09:00:00.000Z', timezone: 'Europe/Amsterdam', limit: 10,
  });
  assert.throws(() => buildCalendarPreviewPayload({ ...draft, end: '2026-10-27T10:01' }), /zeven lokale dagen/);
});

test('all-day dates render as their calendar date without a timezone day shift', () => {
  const rendered = formatGoogleDate('2026-10-25', true);
  assert.equal(rendered, '25 okt 2026');
});

test('status and private preview metadata normalize exact backend shapes', () => {
  assert.deepEqual(normalizeGoogleStatus({ ok: true, enabled: true, configured: true, scopes: { calendar: true, mail: false } }), {
    enabled: true, configured: true, scopes: { calendar: true, mail: false },
  });
  assert.deepEqual(normalizeCalendarPreview({ ok: true, items: [{
    id: 'event-1', summary: 'Planning', start: { date_time: '2026-09-10T10:00:00+02:00' },
    end: { date_time: '2026-09-10T11:00:00+02:00' }, all_day: false, source_ref: 'google:calendar:event:event-1',
  }] })[0], {
    id: 'event-1', summary: 'Planning', start: '2026-09-10T10:00:00+02:00', end: '2026-09-10T11:00:00+02:00', allDay: false, sourceRef: 'google:calendar:event:event-1',
  });
  assert.deepEqual(normalizeMailPreview({ ok: true, items: [{ id: 'mail-1', from: 'Ada', subject: 'Plan', date: 'today', source_ref: 'google:gmail:message:mail-1' }] })[0], {
    id: 'mail-1', from: 'Ada', subject: 'Plan', date: 'today', sourceRef: 'google:gmail:message:mail-1',
  });
});

test('normalizers reject unconfirmed, oversized, or malformed responses', () => {
  assert.throws(() => normalizeGoogleStatus({ enabled: true }), /Google-status/);
  assert.throws(() => normalizeMailPreview({ ok: true, items: Array(11).fill({}) }), /limiet/);
  assert.throws(() => normalizeCalendarPreview({ ok: true, items: [{ id: 'event-1' }] }), /agenda-afspraak/);
});
