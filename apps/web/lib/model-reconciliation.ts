export type CostProposal = {
  job_id: string; receipt_sha256: string; model: string; input_tokens: number; output_tokens: number;
  accounted_microusd: number; reserved_microusd: number; model_state: string;
  billing_basis: string; retry_allowed: false; task_completed: false;
};
export type CostRequest = (resource: string, body?: unknown, jobId?: string) => Promise<{
  reconciliation?: CostProposal; job?: { id: string; model_state?: string } | null;
}>;

export async function approveReconciliation(jobId: string, proposal: CostProposal, approved: boolean, request: CostRequest) {
  if (!approved || proposal.job_id !== jobId || !/^[a-f0-9]{64}$/.test(proposal.receipt_sha256)
      || proposal.retry_allowed !== false || proposal.task_completed !== false) {
    throw new Error('Bekijk en keur eerst het verbruiksbewijs voor deze opdracht goed.');
  }
  const result = await request('reconciliation', {
    id: jobId, receipt_sha256: proposal.receipt_sha256, approve_cost_reconciliation: true,
  });
  if (result.job?.id !== jobId || result.job.model_state !== 'reconciled') {
    throw new Error('Kostenherstel niet bevestigd. Ververs; opnieuw bevestigen boekt niet dubbel.');
  }
}
