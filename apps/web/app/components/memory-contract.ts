export type MemoryListItem = {
  id: string;
  kind?: 'memory' | 'source_record';
  content?: string;
  memory_type?: string;
  source?: string;
  confidence?: number;
  status?: string;
  created_at?: string;
  updated_at?: string;
  review_note?: string;
  sensitivity?: string;
  privacy_level?: string;
};

type MemoryDraft = {
  content: string;
  source: string;
  confidence: string;
  review_note: string;
};

type SearchMatch = {
  id?: unknown;
  kind?: unknown;
  excerpt?: unknown;
  memory_type?: unknown;
  source_type?: unknown;
  source_ref?: unknown;
  confidence?: unknown;
  status?: unknown;
  created_at?: unknown;
  updated_at?: unknown;
};

function object(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

export function buildMemoryCreatePayload(draft: MemoryDraft) {
  return {
    content: draft.content.trim(),
    memory_type: 'working' as const,
    source: draft.source.trim(),
    confidence: Number(draft.confidence),
    review_note: draft.review_note.trim(),
  };
}

export function normalizeMemorySearchResponse(value: unknown): MemoryListItem[] {
  const envelope = object(value);
  const retrieval = object(envelope?.retrieval);
  if (!Array.isArray(retrieval?.results)) throw new Error('Onverwacht zoekantwoord.');

  return retrieval.results.map((raw, index) => {
    const match = object(raw) as SearchMatch | null;
    const sourceRef = object(match?.source_ref);
    if (!match || typeof match.id !== 'string' || !match.id.trim()
      || (match.kind !== 'memory' && match.kind !== 'source_record')
      || typeof match.excerpt !== 'string') {
      throw new Error(`Onverwacht zoekresultaat op positie ${index + 1}.`);
    }
    const confidence = typeof match.confidence === 'number' && Number.isFinite(match.confidence)
      ? match.confidence
      : undefined;
    const source = match.kind === 'memory'
      ? sourceRef?.source
      : sourceRef?.title || sourceRef?.source_ref;
    return {
      id: match.id,
      kind: match.kind,
      content: match.excerpt,
      memory_type: typeof match.memory_type === 'string'
        ? match.memory_type
        : typeof match.source_type === 'string' ? match.source_type : match.kind,
      source: typeof source === 'string' ? source : '',
      confidence,
      status: typeof match.status === 'string' ? match.status : undefined,
      created_at: typeof match.created_at === 'string' ? match.created_at : undefined,
      updated_at: typeof match.updated_at === 'string' ? match.updated_at : undefined,
    };
  });
}
