export type AutonomyStatus = 'idle' | 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled' | string;
export type AutonomyRun = { id: string; status: AutonomyStatus; started_at?: string; ended_at?: string; action_count: number; failure_count: number; proposal_count: number; source_count: number; change_count: number; cost_estimate: { currency: string; estimated_min: string; estimated_max: string; provider_calls_made: boolean } };
export type BriefSection = { id: string; title: string; summary: string; items: unknown[] };
export type PartialFailureSuggestion = { action: string; summary: string };
export type PartialFailureDisclosure = { visible_to_user: boolean; has_partial_failure: boolean; status: string; failure_count: number; recovery_suggestions: PartialFailureSuggestion[] };
export type AutonomyBrief = { run_id: string; status: AutonomyStatus; generated_at: string; generated_by: string; partial_failure_disclosure: PartialFailureDisclosure | null; sections: BriefSection[] };
export type AutonomyOverview = { status: AutonomyStatus; latest_run_id: string; latest_run: AutonomyRun | null; morning_brief: AutonomyBrief | null; bounded: true; limit: number };
export const AUTONOMY_RUN_BODY = { allowed_risk_classes: ['R1', 'R2'], budget_mode: 'economy', local_gpu_ready: false, requested_actions: ['index_new_sources'] } as const;
const text = (value: unknown) => typeof value === 'string' ? value : '';
const count = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? Math.max(0, Math.floor(value)) : 0;
function normalizePartialFailure(value: unknown): PartialFailureDisclosure | null {
  if (!value || typeof value !== 'object') return null;
  const source = value as Record<string, unknown>;
  const suggestions = Array.isArray(source.recovery_suggestions) ? source.recovery_suggestions.slice(0, 6).flatMap(item => {
    if (!item || typeof item !== 'object') return [];
    const suggestion = item as Record<string, unknown>;
    return [{ action: text(suggestion.action).slice(0, 80), summary: text(suggestion.summary).slice(0, 300) }];
  }) : [];
  const visible = source.visible_to_user === true;
  return { visible_to_user: visible, has_partial_failure: source.has_partial_failure === true, status: text(source.status).slice(0, 80), failure_count: count(source.failure_count), recovery_suggestions: visible ? suggestions : [] };
}
export function normalizeAutonomyOverview(value: unknown): AutonomyOverview {
  const root = value && typeof value === 'object' ? value as Record<string, unknown> : {};
  const source = root.autonomy && typeof root.autonomy === 'object' ? root.autonomy as Record<string, unknown> : root;
  const raw = Array.isArray(source.latest_runs) ? source.latest_runs[0] : null;
  const item = raw && typeof raw === 'object' ? raw as Record<string, unknown> : null;
  const cost = item?.cost_estimate && typeof item.cost_estimate === 'object' ? item.cost_estimate as Record<string, unknown> : {};
  const latestRun = item && text(item.id) ? { id: text(item.id), status: text(item.status) || 'idle', ...(text(item.started_at) ? { started_at: text(item.started_at) } : {}), ...(text(item.ended_at) ? { ended_at: text(item.ended_at) } : {}), action_count: count(item.action_count), failure_count: count(item.failure_count), proposal_count: count(item.proposal_count), source_count: count(item.source_count), change_count: count(item.change_count), cost_estimate: { currency: text(cost.currency), estimated_min: text(cost.estimated_min), estimated_max: text(cost.estimated_max), provider_calls_made: cost.provider_calls_made === true } } : null;
  const rawBrief = source.morning_brief && typeof source.morning_brief === 'object' ? source.morning_brief as Record<string, unknown> : null;
  const sections = Array.isArray(rawBrief?.sections) ? rawBrief.sections.filter((section): section is Record<string, unknown> => !!section && typeof section === 'object').slice(0, 12).map(section => ({ id: text(section.id), title: text(section.title), summary: text(section.summary), items: Array.isArray(section.items) ? section.items.slice(0, 5) : [] })) : [];
  const brief = rawBrief ? { run_id: text(rawBrief.run_id), status: text(rawBrief.status) || 'idle', generated_at: text(rawBrief.generated_at), generated_by: text(rawBrief.generated_by), partial_failure_disclosure: normalizePartialFailure(rawBrief.partial_failure_disclosure), sections } : null;
  return { status: text(source.status) || latestRun?.status || 'idle', latest_run_id: text(source.latest_run_id) || latestRun?.id || '', latest_run: latestRun, morning_brief: brief, bounded: true, limit: count(source.limit) };
}
