export type ResearchSource = { title: string; url: string; domain?: string };
export type ResearchData = {
  provider: string;
  status: string;
  risk: string;
  sources: ResearchSource[];
  durationMs?: number;
  error?: string;
  previewFingerprint?: string;
  previewId?: string;
  configured?: boolean;
  executionAllowed: boolean;
};

const text = (value: unknown, fallback = '') => typeof value === 'string' ? value : fallback;

export function normalizeResearch(value: unknown): ResearchData {
  const raw = value && typeof value === 'object' ? value as Record<string, unknown> : {};
  const sources = Array.isArray(raw.sources) ? raw.sources : Array.isArray(raw.results) ? raw.results : [];
  return {
    provider: text(raw.provider, text(raw.provider_name, 'Onbekende provider')),
    status: text(raw.status, raw.ok === true ? 'preview_ready' : 'onbekend'),
    risk: text(raw.risk, text(raw.risk_level, 'R1')),
    durationMs: typeof raw.duration_ms === 'number' ? raw.duration_ms : undefined,
    error: text(raw.error),
    previewFingerprint: text(raw.preview_fingerprint, text(raw.previewFingerprint)),
    previewId: text(raw.preview_id, text(raw.previewId)),
    configured: typeof raw.configured === 'boolean' ? raw.configured : undefined,
    executionAllowed: raw.execution_allowed === true,
    sources: sources.slice(0, 5).map((item) => {
      const source = item && typeof item === 'object' ? item as Record<string, unknown> : {};
      return { title: text(source.title, 'Bron'), url: text(source.url), domain: text(source.domain) || undefined };
    }).filter((source) => source.url),
  };
}

export function buildResearchFields(query: string, domains: string, maxResults: number) {
  return {
    query: query.trim(),
    allowed_domains: domains.split(',').map((domain) => domain.trim().toLowerCase()).filter(Boolean),
    max_results: Math.max(1, Math.min(5, Math.trunc(maxResults))),
  };
}

export function buildResearchRunBody(fields: ReturnType<typeof buildResearchFields>, preview: ResearchData) {
  return { ...fields, preview_fingerprint: preview.previewFingerprint, preview_id: preview.previewId };
}
