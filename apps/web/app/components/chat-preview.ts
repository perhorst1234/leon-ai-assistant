type PreviewTurn = { role: 'user' | 'assistant'; content: string };
type PreviewInput = { included_messages: number | Array<unknown> };
type ChatMessageInput = { role: 'user' | 'assistant'; content: string; status?: string };

export function previewStillMatches(preview: PreviewInput, messages: ChatMessageInput[]) {
  if (!Array.isArray(preview.included_messages)) return true;
  const turns = messages.filter(message => message.role === 'user' || message.status === 'complete')
    .map(message => ({ role: message.role, content: message.content }));
  const priorTurns = preview.included_messages.slice(0, -1) as PreviewTurn[];
  const context = turns.slice(-priorTurns.length);
  return priorTurns.length === context.length && priorTurns.every((turn, index) =>
    turn.role === context[index].role && turn.content === context[index].content);
}
