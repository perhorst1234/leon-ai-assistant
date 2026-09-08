export type ModelDraft = { task_id: string; prompt: string; max_output_tokens: number; max_cost_microusd: number };
export type ModelPreview = { model: string; reserved_microusd: number; max_cost_microusd: number; prompt_bytes: number; execution_allowed: false; provider_calls_made: false };
export type ModelReply = { job?: { id: string; request_id: string } | null; preview?: ModelPreview };
export type ModelRequest = (resource: string, body?: unknown, requestId?: string) => Promise<ModelReply>;
type Storage = Pick<globalThis.Storage, 'getItem' | 'setItem' | 'removeItem'>;
const pendingKey = 'leon.model.pending-request.v1';

export function usdToMicrousd(value: string): number {
  const normalized = value.trim().replace(',', '.');
  if (!/^\d{1,2}(\.\d{1,6})?$/.test(normalized)) throw new Error('Gebruik een bedrag in USD met maximaal zes decimalen.');
  const [whole, fraction = ''] = normalized.split('.');
  const micros = Number(whole) * 1e6 + Number(fraction.padEnd(6, '0'));
  if (micros < 1 || micros > 1e6) throw new Error('Kies een maximum groter dan nul en hoogstens $1 per aanvraag.');
  return micros;
}

export function readPending(storage: Storage): string | null {
  const id = storage.getItem(pendingKey);
  if (id !== null && !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) {
    throw new Error('De bewaarde aanvraag-id is ongeldig; controleer eerst de bestaande taken.');
  }
  return id;
}

export async function recoverModel(storage: Storage, request: ModelRequest) {
  const id = readPending(storage);
  if (!id) return null;
  const result = await request('jobs', undefined, id);
  if (result.job?.id && result.job.request_id === id) {
    storage.removeItem(pendingKey);
    return result.job;
  }
  // Absence is not proof that an earlier in-flight request cannot still commit.
  // Keep the same UUID for a user-initiated retry, including after reload.
  return null;
}

export async function submitModel(draft: ModelDraft, reviewed: ModelDraft, approved: boolean,
  storage: Storage, request: ModelRequest, newId = () => crypto.randomUUID()) {
  if (!approved || JSON.stringify(draft) !== JSON.stringify(reviewed)) throw new Error('Bekijk en keur deze exacte tekst en limieten eerst goed.');
  const id = readPending(storage) ?? newId();
  // Store only the UUID, never the prompt, dashboard token or API key.
  // If storage fails, do not send something that cannot be recovered safely.
  storage.setItem(pendingKey, id);
  const result = await request('model', { ...reviewed, request_id: id, approve_external_text: true });
  if (!result.job?.id || result.job.request_id !== id) throw new Error('Verzending niet bevestigd. Controleer de bewaarde aanvraag voordat je opnieuw probeert.');
  storage.removeItem(pendingKey);
  return result.job;
}
