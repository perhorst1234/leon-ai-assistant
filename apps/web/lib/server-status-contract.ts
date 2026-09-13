export type ServerStatus = {
  enabled: boolean; status: string; generated_at?: string;
  os: { system?: string; release?: string; machine?: string; python?: string };
  uptime: { value?: number | string; status?: string };
  load: { value: number[]; status?: string };
  memory: { total_bytes?: number; available_bytes?: number; status?: string };
  disk: Array<{ label?: string; total_bytes?: number; free_bytes?: number; status?: string }>;
  process: { running?: boolean; status?: string };
  health: { status?: string; checks?: Record<string, unknown> };
  permission_check_id?: string;
};

const obj = (value: unknown): Record<string, unknown> => value && typeof value === 'object' ? value as Record<string, unknown> : {};
const text = (value: unknown) => typeof value === 'string' ? value : undefined;
const num = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? value : undefined;
export function normalizeServerStatus(input: unknown): ServerStatus {
  const root = obj(input), os = obj(root.os), uptime = obj(root.uptime), load = obj(root.load), memory = obj(root.memory), process = obj(root.process), health = obj(root.health);
  const disks = Array.isArray(root.disk) ? root.disk : [];
  return { enabled: root.enabled === true, status: text(root.status) ?? 'unavailable', generated_at: text(root.generated_at),
    os: { system: text(os.system), release: text(os.release), machine: text(os.machine), python: text(os.python) },
    uptime: { value: num(uptime.value) ?? text(uptime.value), status: text(uptime.status) },
    load: { value: (Array.isArray(load.value) ? load.value : []).filter((v): v is number => typeof v === 'number').slice(0, 3), status: text(load.status) },
    memory: { total_bytes: num(memory.total_bytes), available_bytes: num(memory.available_bytes), status: text(memory.status) },
    disk: disks.slice(0, 8).map(item => { const d = obj(item); return { label: text(d.label), total_bytes: num(d.total_bytes), free_bytes: num(d.free_bytes), status: text(d.status) }; }),
    process: { running: typeof process.running === 'boolean' ? process.running : undefined, status: text(process.status) },
    health: { status: text(health.status), checks: obj(health.checks) }, permission_check_id: text(root.permission_check_id) };
}
