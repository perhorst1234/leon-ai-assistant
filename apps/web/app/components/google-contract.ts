export const GOOGLE_TIMEZONE = 'Europe/Amsterdam';
export const GOOGLE_PREVIEW_LIMIT = 10;

export type GoogleStatus = {
  enabled: boolean;
  configured: boolean;
  scopes: { calendar: boolean; mail: boolean };
};

export type CalendarDraft = { start: string; end: string };
export type CalendarPreviewItem = {
  id: string;
  summary: string;
  start: string;
  end: string;
  allDay: boolean;
  sourceRef: string;
};
export type MailPreviewItem = {
  id: string;
  from: string;
  subject: string;
  date: string;
  sourceRef: string;
};

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function localParts(date: Date, timeZone: string) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone, year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
  }).formatToParts(date);
  return Object.fromEntries(parts.filter(part => part.type !== 'literal').map(part => [part.type, Number(part.value)]));
}

function localInput(date: Date) {
  const part = localParts(date, GOOGLE_TIMEZONE);
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${part.year}-${pad(part.month)}-${pad(part.day)}T${pad(part.hour)}:${pad(part.minute)}`;
}

function parseLocal(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
  if (!match) throw new Error('Kies een geldige datum en tijd.');
  const [, year, month, day, hour, minute] = match.map(Number);
  const wallTime = Date.UTC(year, month - 1, day, hour, minute);
  if (new Date(wallTime).getUTCFullYear() !== year || new Date(wallTime).getUTCMonth() !== month - 1
    || new Date(wallTime).getUTCDate() !== day || hour > 23 || minute > 59) {
    throw new Error('Kies een geldige datum en tijd.');
  }
  return { year, month, day, hour, minute, wallTime };
}

function localToUtc(value: string): Date {
  const { wallTime } = parseLocal(value);
  const offsetAt = (timestamp: number) => {
    const part = localParts(new Date(timestamp), GOOGLE_TIMEZONE);
    return Date.UTC(part.year, part.month - 1, part.day, part.hour, part.minute, part.second) - timestamp;
  };
  let timestamp = wallTime - offsetAt(wallTime);
  timestamp = wallTime - offsetAt(timestamp);
  const result = new Date(timestamp);
  if (localInput(result) !== value) throw new Error('Deze lokale tijd bestaat niet in Europe/Amsterdam.');
  return result;
}

function addLocalDays(value: string, days: number) {
  const date = new Date(parseLocal(value).wallTime + days * 86400000);
  const pad = (part: number) => String(part).padStart(2, '0');
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}T${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}`;
}

export function defaultCalendarDraft(now = new Date()): CalendarDraft {
  if (!Number.isFinite(now.getTime())) throw new Error('Ongeldige huidige datum.');
  const start = localInput(now);
  return { start, end: addLocalDays(start, 7) };
}

export function buildCalendarPreviewPayload(draft: CalendarDraft) {
  const localDuration = parseLocal(draft.end).wallTime - parseLocal(draft.start).wallTime;
  const start = localToUtc(draft.start);
  const end = localToUtc(draft.end);
  const duration = end.getTime() - start.getTime();
  if (duration <= 0) throw new Error('De eindtijd moet na de starttijd liggen.');
  if (localDuration > 7 * 86400000) throw new Error('Kies een periode van maximaal zeven lokale dagen.');
  return { start: start.toISOString(), end: end.toISOString(), timezone: GOOGLE_TIMEZONE, limit: GOOGLE_PREVIEW_LIMIT };
}

export function formatGoogleDate(value: string, allDay = false) {
  if (!value) return 'Onbekend';
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  const date = dateOnly
    ? new Date(Date.UTC(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3])))
    : new Date(value);
  if (!Number.isFinite(date.getTime())) return value;
  return new Intl.DateTimeFormat('nl-NL', {
    timeZone: dateOnly ? 'UTC' : GOOGLE_TIMEZONE,
    dateStyle: 'medium', ...(allDay || dateOnly ? {} : { timeStyle: 'short' }),
  }).format(date);
}

export function normalizeGoogleStatus(value: unknown): GoogleStatus {
  const data = record(value); const scopes = record(data?.scopes);
  if (data?.ok !== true || typeof data.enabled !== 'boolean' || typeof data.configured !== 'boolean'
    || typeof scopes?.calendar !== 'boolean' || typeof scopes.mail !== 'boolean') {
    throw new Error('Onverwachte Google-status.');
  }
  return { enabled: data.enabled, configured: data.configured, scopes: { calendar: scopes.calendar, mail: scopes.mail } };
}

function previewItems(value: unknown) {
  const data = record(value);
  if (data?.ok !== true || !Array.isArray(data.items)) throw new Error('Onverwacht Google-voorbeeld.');
  if (data.items.length > GOOGLE_PREVIEW_LIMIT) throw new Error('Google-voorbeeld overschrijdt de limiet.');
  return data.items;
}

export function normalizeCalendarPreview(value: unknown): CalendarPreviewItem[] {
  return previewItems(value).map((raw, index) => {
    const item = record(raw); const start = record(item?.start); const end = record(item?.end);
    const startValue = start?.date_time ?? start?.date; const endValue = end?.date_time ?? end?.date;
    if (typeof item?.id !== 'string' || typeof item.summary !== 'string' || typeof item.all_day !== 'boolean'
      || typeof item.source_ref !== 'string' || typeof startValue !== 'string' || typeof endValue !== 'string') {
      throw new Error(`Onverwachte agenda-afspraak op positie ${index + 1}.`);
    }
    return { id: item.id, summary: item.summary || 'Afspraak zonder titel', start: startValue, end: endValue, allDay: item.all_day, sourceRef: item.source_ref };
  });
}

export function normalizeMailPreview(value: unknown): MailPreviewItem[] {
  return previewItems(value).map((raw, index) => {
    const item = record(raw);
    if (typeof item?.id !== 'string' || typeof item.from !== 'string' || typeof item.subject !== 'string'
      || typeof item.date !== 'string' || typeof item.source_ref !== 'string') {
      throw new Error(`Onverwacht mailbericht op positie ${index + 1}.`);
    }
    return { id: item.id, from: item.from || 'Onbekende afzender', subject: item.subject || 'Zonder onderwerp', date: item.date, sourceRef: item.source_ref };
  });
}
