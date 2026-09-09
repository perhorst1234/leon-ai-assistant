'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';
import type { RefObject } from 'react';
import ConnectedWork from './components/connected-work';
import ConnectedChat from './components/connected-chat';
import type { ChatRequest } from './components/connected-chat';
import { AnimatePresence, MotionConfig, motion } from 'motion/react';
import {
  Activity,
  ArrowRight,
  ArrowUp,
  AudioLines,
  Bot,
  Box,
  Brain,
  CalendarClock,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleUserRound,
  Clock3,
  CloudSun,
  Command,
  Cpu,
  Database,
  GitBranch,
  Globe2,
  Home,
  Lightbulb,
  Link2,
  LockKeyhole,
  Mail,
  MessageCircle,
  Orbit,
  Pause,
  Play,
  Printer,
  RefreshCw,
  Rocket,
  Search,
  Server,
  Settings2,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  SunMedium,
  Timer,
  Users,
  Wallet,
  WandSparkles,
  X,
  Zap,
} from 'lucide-react';

const spaces = [
  { id: 'today', label: 'Vandaag', icon: Home },
  { id: 'chat', label: 'Chat', icon: MessageCircle },
  { id: 'flows', label: 'Werk', icon: GitBranch },
  { id: 'memory', label: 'Memory', icon: Brain },
] as const;

type SpaceId = (typeof spaces)[number]['id'];
type GaiaState = 'idle' | 'thinking' | 'acting' | 'listening';

const spaceCopy: Record<SpaceId, { lead: string; detail: string }> = {
  today: {
    lead: 'Goedemorgen, Per.',
    detail: 'Je dag voelt rustig. Ik heb twee dingen alvast voor je voorbereid.',
  },
  chat: {
    lead: 'Waar denk je aan?',
    detail: 'Begin met een gedachte. Ik maak er samen met jou iets bruikbaars van.',
  },
  flows: {
    lead: 'Werk dat doorloopt.',
    detail: 'Volg het einddoel, de voortgang, agents en approvals van iedere lange missie.',
  },
  memory: {
    lead: 'Ik onthoud de lijn.',
    detail: 'Projecten, voorkeuren en eerdere keuzes vormen hier één levend geheugen.',
  },
};

const stateCopy: Record<GaiaState, string> = {
  idle: 'Gaia is aanwezig',
  thinking: 'Gaia denkt mee',
  acting: 'Gaia voert uit',
  listening: 'Gaia luistert',
};

const memoryNodes = [
  { id: 'per', label: 'Per', detail: 'Je persoonlijke context', icon: CircleUserRound, x: 50, y: 48, size: 'large' },
  { id: 'gaia', label: 'Gaia', detail: 'Living AI companion', icon: Orbit, x: 29, y: 25, size: 'medium' },
  { id: 'design', label: 'Design', detail: 'Apple · Arc · AI-native', icon: WandSparkles, x: 72, y: 24, size: 'medium' },
  { id: 'home', label: 'Home', detail: 'Home Assistant & ESP32', icon: Home, x: 79, y: 62, size: 'small' },
  { id: 'build', label: 'Bouwen', detail: 'Prototypes en systemen', icon: GitBranch, x: 27, y: 70, size: 'small' },
  { id: 'preference', label: 'Voorkeur', detail: 'Mooi, slim en niet onnodig', icon: Lightbulb, x: 54, y: 79, size: 'small' },
] as const;

const missionSteps = [
  { title: 'Scope vastgezet', detail: 'Einddoel, grenzen en approvals', state: 'done' },
  { title: 'Bronnen onderzocht', detail: 'Agent-, memory- en toolpatronen', state: 'done' },
  { title: 'Interface bouwen', detail: 'Mission control en agents', state: 'active' },
  { title: 'Kwaliteitsronde', detail: 'Responsive, toetsenbord en contrast', state: 'waiting' },
  { title: 'Publiceren', detail: 'Preview opleveren en overdracht', state: 'waiting' },
] as const;

const agentCatalog = [
  { id: 'manager', name: 'Manager', role: 'Budget & risico', detail: 'Leest financiële context; iedere geldactie wacht op jou.', icon: Wallet, permission: 'Approval bij geld' },
  { id: 'planner', name: 'Planner', role: 'Dag & routines', detail: 'Verbindt agenda, mail, to-do’s, vakanties en je ritme.', icon: CalendarClock, permission: 'Persoonlijke context' },
  { id: 'shopper', name: 'Shopper', role: 'Deals & tickets', detail: 'Onderzoekt aanbod en stelt berichten of aankopen eerst voor.', icon: ShoppingBag, permission: 'Approval bij aankoop' },
  { id: 'server', name: 'Server Manager', role: 'Infra & herstel', detail: 'Bewaakt processen, containers, updates en terugkerende fouten.', icon: Server, permission: 'Approval bij wijziging' },
  { id: 'reference', name: '3D Reference', role: 'Beeld naar model', detail: 'Zoekt modellen of maakt een 360°-referentieset.', icon: Box, permission: 'Bronnen vermelden' },
  { id: 'printer', name: 'Print Watcher', role: 'Printkwaliteit', detail: 'Volgt Fluidd en camera; meldt wanneer calibratie nodig is.', icon: Printer, permission: 'Stoppen mag, wijzigen vraagt' },
  { id: 'scheduler', name: 'Model Scheduler', role: 'GPU & VRAM', detail: 'Plant lokale modellen slim over GPU, RAM en opslag.', icon: Cpu, permission: 'Resource-limieten' },
  { id: 'value', name: 'Value Engine', role: 'Nut & onderzoek', detail: 'Bepaalt of een nieuwe tool de bouwtijd en kosten waard is.', icon: Lightbulb, permission: 'Review voor installatie' },
] as const;

type AgentId = (typeof agentCatalog)[number]['id'];
type ReviewKind = 'approval' | 'learning';

function useCompactLayout() {
  const [compact, setCompact] = useState(false);

  useEffect(() => {
    const media = window.matchMedia('(max-width: 700px)');
    const update = () => setCompact(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);

  return compact;
}

function BreathingField({ state }: { state: GaiaState }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const context = canvas.getContext('2d');
    if (!context) return;

    let frame = 0;
    let width = 0;
    let height = 0;
    let dpr = 1;
    const pointer = { x: -9999, y: -9999 };
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const palette: Record<GaiaState, [number, number, number]> = {
      idle: [180, 205, 255],
      thinking: [196, 171, 255],
      acting: [124, 229, 245],
      listening: [180, 248, 218],
    };

    const resize = () => {
      const bounds = canvas.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = bounds.width;
      height = bounds.height;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = (timestamp: number) => {
      context.clearRect(0, 0, width, height);
      const step = width < 700 ? 34 : 42;
      const speed = state === 'thinking' ? 0.00055 : state === 'acting' ? 0.00072 : 0.00035;
      const t = reduceMotion ? 0.6 : timestamp * speed;
      const cols = Math.ceil(width / step) + 2;
      const rows = Math.ceil(height / step) + 2;
      const [red, green, blue] = palette[state];

      for (let row = -1; row < rows; row += 1) {
        for (let col = -1; col < cols; col += 1) {
          const x = col * step + (row % 2) * 2;
          const y = row * step;
          const waveA = Math.sin(col * 0.42 + t * 2.1);
          const waveB = Math.cos(row * 0.5 - t * 1.55);
          const radial = Math.sin(Math.hypot(col - cols * 0.54, row - rows * 0.48) * 0.36 - t * 2.7);
          const pointerDistance = Math.hypot(x - pointer.x, y - pointer.y);
          const pointerLift = Math.max(0, 1 - pointerDistance / 190);
          const energy = (waveA + waveB + radial + 3) / 6;
          const stateLift = state === 'acting' ? 1.4 : state === 'thinking' ? 0.7 : 0;
          const size = 1.25 + energy * 4 + pointerLift * 3 + stateLift;
          const alpha = 0.13 + energy * 0.21 + pointerLift * 0.2;

          context.beginPath();
          context.arc(x, y, size, 0, Math.PI * 2);
          context.fillStyle = `rgba(${red}, ${green}, ${blue}, ${alpha})`;
          context.fill();
        }
      }

      if (!reduceMotion) frame = window.requestAnimationFrame(draw);
    };

    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();
    draw(0);

    const onPointerMove = (event: PointerEvent) => {
      pointer.x = event.clientX;
      pointer.y = event.clientY;
    };
    const onPointerLeave = () => {
      pointer.x = -9999;
      pointer.y = -9999;
    };

    window.addEventListener('pointermove', onPointerMove, { passive: true });
    document.documentElement.addEventListener('pointerleave', onPointerLeave);

    return () => {
      observer.disconnect();
      window.cancelAnimationFrame(frame);
      window.removeEventListener('pointermove', onPointerMove);
      document.documentElement.removeEventListener('pointerleave', onPointerLeave);
    };
  }, [state]);

  return <canvas ref={canvasRef} className="breathing-field" aria-hidden="true" />;
}

function SpaceSwitcher({
  active,
  onChange,
  onSettings,
}: {
  active: SpaceId;
  onChange: (id: SpaceId) => void;
  onSettings: () => void;
}) {
  return (
    <nav className="space-switcher" aria-label="Gaia ruimtes">
      <div className="switcher-mark" aria-hidden="true">
        <Orbit size={17} strokeWidth={1.8} />
      </div>
      <div className="switcher-tabs">
        {spaces.map((space) => {
          const Icon = space.icon;
          const selected = active === space.id;
          return (
            <button
              className="switcher-tab"
              key={space.id}
              type="button"
              aria-label={`${space.label} openen`}
              aria-current={selected ? 'page' : undefined}
              onClick={() => onChange(space.id)}
            >
              {selected && (
                <motion.span
                  className="switcher-bubble"
                  layoutId="space-bubble"
                  transition={{ type: 'spring', bounce: 0, duration: 0.42 }}
                />
              )}
              <Icon size={15} strokeWidth={selected ? 2 : 1.6} aria-hidden="true" />
              <span>{space.label}</span>
            </button>
          );
        })}
      </div>
      <button className="switcher-icon" type="button" aria-label="Instellingen openen" onClick={onSettings}>
        <Settings2 size={17} strokeWidth={1.7} />
      </button>
    </nav>
  );
}

function DropZones({ visible }: { visible: boolean }) {
  const zones = [
    { id: 'explain', label: 'Leg dit uit', icon: MessageCircle },
    { id: 'flow', label: 'Maak een flow', icon: GitBranch },
    { id: 'remember', label: 'Onthoud dit', icon: Brain },
  ];

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className="drop-zones"
          initial={{ opacity: 0, filter: 'blur(8px)', transform: 'translate(-50%, 10px)' }}
          animate={{ opacity: 1, filter: 'blur(0px)', transform: 'translate(-50%, 0px)' }}
          exit={{ opacity: 0, filter: 'blur(5px)', transform: 'translate(-50%, 6px)' }}
          transition={{ duration: 0.22, ease: [0.23, 1, 0.32, 1] }}
        >
          {zones.map((zone) => {
            const Icon = zone.icon;
            return (
              <div className="drop-zone" data-dropzone={zone.id} key={zone.id}>
                <Icon size={16} strokeWidth={1.7} />
                <span>{zone.label}</span>
              </div>
            );
          })}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function GaiaCompanion({
  active,
  state,
  compact,
  settingsOpen,
  constraintsRef,
  onDragging,
  onDropAction,
}: {
  active: SpaceId;
  state: GaiaState;
  compact: boolean;
  settingsOpen: boolean;
  constraintsRef: RefObject<HTMLElement | null>;
  onDragging: (dragging: boolean) => void;
  onDropAction: (action?: string) => void;
}) {
  const [actionsOpen, setActionsOpen] = useState(false);
  const desktopPositions: Record<SpaceId, { left: string; top: string; scale: number }> = {
    today: { left: '54%', top: '49%', scale: 0.72 },
    chat: { left: '80%', top: '32%', scale: 0.58 },
    flows: { left: '68%', top: '50%', scale: 0.5 },
    memory: { left: '15%', top: '34%', scale: 0.6 },
  };
  const compactPositions: Record<SpaceId, { left: string; top: string; scale: number }> = {
    today: { left: '50%', top: '31%', scale: 0.3 },
    chat: { left: '84%', top: '19%', scale: 0.36 },
    flows: { left: '82%', top: '20%', scale: 0.28 },
    memory: { left: '82%', top: '20%', scale: 0.38 },
  };
  const position = settingsOpen
    ? compact
      ? { left: '18%', top: '20%', scale: 0.36 }
      : { left: '28%', top: '48%', scale: 0.84 }
    : compact
      ? compactPositions[active]
      : desktopPositions[active];

  return (
    <motion.div
      className="companion-stage"
      style={{ left: position.left, top: position.top }}
      animate={{ scale: position.scale }}
      transition={{ type: 'spring', bounce: 0, duration: 0.58 }}
      aria-label={stateCopy[state]}
    >
      <div className="companion-orbit orbit-one" aria-hidden="true" />
      <div className="companion-orbit orbit-two" aria-hidden="true" />
      <motion.div
        className="companion-shadow"
        animate={{ scaleX: state === 'thinking' ? 0.7 : state === 'acting' ? 1.15 : 1, opacity: state === 'listening' ? 0.3 : 0.2 }}
        transition={{ type: 'spring', bounce: 0, duration: 0.4 }}
        aria-hidden="true"
      />
      <motion.button
        className="companion-drag"
        type="button"
        aria-label="Open snelle acties voor Gaia"
        aria-expanded={actionsOpen}
        aria-controls="gaia-quick-actions"
        drag
        dragConstraints={constraintsRef}
        dragElastic={0.1}
        dragMomentum
        dragSnapToOrigin
        whileDrag={{ scale: 1.045, cursor: 'grabbing' }}
        onDragStart={() => onDragging(true)}
        onClick={() => setActionsOpen((open) => !open)}
        onDragEnd={(_, info) => {
          onDragging(false);
          const target = document
            .elementsFromPoint(info.point.x, info.point.y)
            .map((element) => element.closest<HTMLElement>('[data-dropzone]'))
            .find(Boolean);
          onDropAction(target?.dataset.dropzone);
        }}
      >
        <div className={`companion companion-${state}`}>
          <span className="companion-aurora" aria-hidden="true" />
          <span className="companion-face">
            <span className="companion-eye eye-left" />
            <span className="companion-eye eye-right" />
            <span className="companion-smile" />
          </span>
          <span className="companion-foot foot-left" aria-hidden="true" />
          <span className="companion-foot foot-right" aria-hidden="true" />
        </div>
      </motion.button>
      <AnimatePresence>
        {actionsOpen && (
          <motion.div
            id="gaia-quick-actions"
            className="companion-quick-actions"
            initial={{ opacity: 0, transform: 'translate(-50%, 8px) scale(0.96)' }}
            animate={{ opacity: 1, transform: 'translate(-50%, 0px) scale(1)' }}
            exit={{ opacity: 0, transform: 'translate(-50%, 5px) scale(0.98)' }}
            transition={{ duration: 0.18, ease: [0.23, 1, 0.32, 1] }}
          >
            <button type="button" onClick={() => { onDropAction('explain'); setActionsOpen(false); }}><MessageCircle size={15} /> Leg dit uit</button>
            <button type="button" onClick={() => { onDropAction('flow'); setActionsOpen(false); }}><GitBranch size={15} /> Maak een werkplan</button>
            <button type="button" onClick={() => { onDropAction('remember'); setActionsOpen(false); }}><Brain size={15} /> Onthoud dit</button>
          </motion.div>
        )}
      </AnimatePresence>
      <div className="companion-status">
        <span className="status-pulse" aria-hidden="true" />
        {stateCopy[state]}
      </div>
    </motion.div>
  );
}

function TodayView({
  onOpenChat,
  onOpenWork,
  onApprove,
  onReviewLearning,
}: {
  onOpenChat: () => void;
  onOpenWork: () => void;
  onApprove: () => void;
  onReviewLearning: () => void;
}) {
  return (
    <div className="space-view today-view today-command-center">
      <header className="today-intro">
        <div>
          <h1>Goedemorgen, Per.</h1>
          <p>Gaia werkt door. Jij hoeft alleen te kijken waar je aandacht echt nodig is.</p>
        </div>
        <time dateTime="2026-08-27T09:42:00+02:00"><span>do 27 aug</span><strong>09:42</strong></time>
      </header>

      <section className="active-mission" aria-label="Actieve lange missie">
        <div className="mission-topline">
          <span className="live-indicator"><span /> actief sinds 07:14</span>
          <span className="prototype-chip">voorbeeld</span>
        </div>
        <div className="mission-title-row">
          <div>
            <h2>Gaia OS bouwen</h2>
            <p>Een publiceerbare AI-companion frontend waarin lange agents begrijpelijk en bestuurbaar blijven.</p>
          </div>
          <span className="mission-percent">64<small>%</small></span>
        </div>
        <div className="mission-progress" aria-label="64 procent voltooid"><motion.span initial={{ width: 0 }} animate={{ width: '64%' }} transition={{ duration: 0.8, ease: [0.23, 1, 0.32, 1] }} /></div>
        <div className="mission-now">
          <span><Activity size={15} /><small>Nu</small><strong>Mission control bouwen</strong></span>
          <span><Timer size={15} /><small>Verwacht</small><strong>nog 2u 18m</strong></span>
          <span><Users size={15} /><small>Team</small><strong>3 agents actief</strong></span>
        </div>
        <button className="mission-open" type="button" onClick={onOpenWork}>Open werkcockpit <ArrowRight size={16} /></button>
      </section>

      <aside className="today-side-stack" aria-label="Aandacht van Per">
        <section className="attention-panel approval-panel">
          <div className="panel-symbol amber"><LockKeyhole size={17} /></div>
          <div className="attention-copy">
            <div><strong>Jouw keuze nodig</strong><span>Manager</span></div>
            <p>Checkout van €42,80 staat klaar. Gaia voert niets uit zonder jouw approval.</p>
            <div className="approval-actions">
              <button type="button" className="approve-button" onClick={onApprove}>Bekijk & keur goed</button>
              <span>geen betaling gedaan</span>
            </div>
          </div>
        </section>

        <section className="attention-panel learning-panel">
          <div className="panel-symbol violet"><RefreshCw size={17} /></div>
          <div className="attention-copy">
            <div><strong>Learning inbox</strong><span>22:00</span></div>
            <p>Value Engine stelde een weather-repair skill voor na twee mislukte toolcalls.</p>
            <button type="button" className="text-action" onClick={onReviewLearning}>Review vanavond <ChevronRight size={15} /></button>
          </div>
        </section>
      </aside>

      <div className="today-ribbon" aria-label="Vandaag in het kort">
        <span><SunMedium size={16} /><small>Amsterdam</small><strong>21° · droog</strong></span>
        <span><CalendarDays size={16} /><small>Volgende</small><strong>Focusblok · 10:30</strong></span>
        <span><Bot size={16} /><small>Agents</small><strong>1 wacht op approval</strong></span>
        <button type="button" onClick={onOpenChat}>Vraag Gaia <ArrowUp size={14} /></button>
      </div>
    </div>
  );
}

function ChatView({
  prompt,
  responseReady,
  onPlan,
}: {
  prompt: string;
  responseReady: boolean;
  onPlan: () => void;
}) {
  const shownPrompt = prompt || 'Kan ik morgen na school buiten barbecueën?';
  return (
    <div className="space-view chat-view">
      <section className="conversation-space" aria-label="Gesprek met Gaia">
        <header className="view-heading">
          <span className="view-icon"><MessageCircle size={17} /></span>
          <div>
            <h1>Gesprek</h1>
            <p>Context blijft zichtbaar terwijl je verder denkt.</p>
          </div>
        </header>

        <div className="user-thought">
          <span className="thought-avatar">P</span>
          <p>{shownPrompt}</p>
        </div>

        <AnimatePresence mode="wait" initial={false}>
          {responseReady ? (
            <motion.div
              className="gaia-response"
              key="answer"
              initial={{ opacity: 0, filter: 'blur(8px)', transform: 'translateY(10px)' }}
              animate={{ opacity: 1, filter: 'blur(0px)', transform: 'translateY(0px)' }}
              transition={{ duration: 0.3, ease: [0.23, 1, 0.32, 1] }}
            >
              <p>
                Ja. Tussen <strong>17:30 en 20:00</strong> lijkt het droog, en je agenda is vanaf 17:00 vrij. Ik zou rond 18:00 beginnen.
              </p>
              <button type="button" className="inline-action" onClick={onPlan}>
                Maak er een plan van <ArrowRight size={15} />
              </button>
            </motion.div>
          ) : (
            <motion.div className="thinking-line" key="thinking" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <span /><span /><span />
              <p>Ik combineer weer, agenda en je voorkeuren…</p>
            </motion.div>
          )}
        </AnimatePresence>
      </section>

      <aside className="tool-experience" aria-label="Gecombineerde toolresultaten">
        <div className="tool-header">
          <div>
            <span>Context voor morgen</span>
            <small>synthetische voorbeelddata</small>
          </div>
          <span className="tool-confidence">92% zeker</span>
        </div>
        <div className="weather-scene">
          <div>
            <CloudSun size={27} strokeWidth={1.45} />
            <span><strong>21°</strong><small>zacht en droog</small></span>
          </div>
          <div className="weather-hours">
            {['17', '18', '19', '20'].map((hour, index) => (
              <span key={hour}><small>{hour}:00</small><i style={{ height: `${28 + index * 6}px` }} /></span>
            ))}
          </div>
        </div>
        <div className="context-row">
          <span className="context-icon"><CalendarDays size={16} /></span>
          <span><small>Agenda</small><strong>Vrij vanaf 17:00</strong></span>
          <Check size={15} className="row-check" />
        </div>
        <div className="context-row">
          <span className="context-icon"><Lightbulb size={16} /></span>
          <span><small>Persoonlijke context</small><strong>Je kiest liever vroeg dan laat</strong></span>
          <Check size={15} className="row-check" />
        </div>
      </aside>
    </div>
  );
}

function FlowsView({
  activeStep,
  onRun,
  paused,
  onTogglePause,
  automaticAgents,
  selectedAgents,
  onSelectAgents,
  onApprove,
}: {
  activeStep: number;
  onRun: () => void;
  paused: boolean;
  onTogglePause: () => void;
  automaticAgents: boolean;
  selectedAgents: AgentId[];
  onSelectAgents: () => void;
  onApprove: () => void;
}) {
  const teamIds: AgentId[] = automaticAgents ? ['planner', 'value', 'server'] : selectedAgents;
  const team = teamIds.map((id) => agentCatalog.find((agent) => agent.id === id)).filter(Boolean) as (typeof agentCatalog)[number][];
  const simulatedProgress = activeStep < 0 ? 64 : Math.min(68, 64 + activeStep);
  return (
    <div className="space-view work-view">
      <header className="work-header">
        <div>
          <h1>Gaia OS bouwen</h1>
          <p>Een lange missie die na onderbrekingen veilig verdergaat.</p>
        </div>
        <div className="work-actions">
          <button type="button" className="secondary-control" onClick={onSelectAgents}><Users size={16} /> Kies agents</button>
          <button type="button" className="pause-control" data-paused={paused || undefined} onClick={onTogglePause}>
            {paused ? <Play size={16} fill="currentColor" /> : <Pause size={16} fill="currentColor" />}
            {paused ? 'Hervat' : 'Pauzeer'}
          </button>
        </div>
      </header>

      <div className="work-layout">
        <section className="mission-console" aria-label="Missievoortgang">
          <div className="console-status">
            <span className="live-indicator"><span /> {paused ? 'gepauzeerd' : 'werkt door'}</span>
            <span>gestart 07:14 · checkpoint 12:06</span>
          </div>
          <div className="console-goal">
            <div>
              <h2>Einddoel</h2>
              <p>Een publiceerbare frontend waarin Per binnen vijf seconden ziet wat Gaia doet, waarom, door wie en wanneer het klaar is.</p>
            </div>
            <span className="console-eta"><small>verwacht klaar</small><strong>14:24</strong><em>nog 2u 18m</em></span>
          </div>
          <div className="console-progress-row">
            <span><strong>{simulatedProgress}%</strong><small>voltooid</small></span>
            <div className="mission-progress"><motion.span animate={{ width: `${simulatedProgress}%` }} transition={{ duration: 0.55, ease: [0.23, 1, 0.32, 1] }} /></div>
          </div>

          <ol className="mission-timeline">
            {missionSteps.map((step, index) => {
              const live = step.state === 'active';
              const done = step.state === 'done';
              return (
                <li key={step.title} data-state={step.state}>
                  <span className="timeline-marker">{done ? <Check size={14} /> : live ? <Activity size={14} /> : index + 1}</span>
                  <span><strong>{step.title}</strong><small>{step.detail}</small></span>
                  {live && <span className="timeline-live">nu</span>}
                </li>
              );
            })}
          </ol>

          <button className="trace-action" type="button" onClick={onRun} disabled={activeStep >= 0 && activeStep < 4}>
            <RefreshCw size={15} className={activeStep >= 0 && activeStep < 4 ? 'spin-slow' : undefined} />
            {activeStep >= 0 && activeStep < 4 ? 'Checkpoint wordt getest' : 'Simuleer volgende checkpoint'}
          </button>
        </section>

        <aside className="work-sidebar" aria-label="Missiecontrole">
          <section className="agent-ensemble">
            <div className="sidebar-heading"><span><Bot size={16} /> Agentteam</span><button type="button" onClick={onSelectAgents}>Wijzig</button></div>
            <div className="agent-stack" aria-label={`${team.length} actieve agents`}>
              {team.slice(0, 4).map((agent, index) => {
                const Icon = agent.icon;
                return <span key={agent.id} style={{ zIndex: 4 - index }} aria-label={agent.name}><Icon size={15} /></span>;
              })}
              <strong>{automaticAgents ? `Automatisch · ${team.length} agents` : `Handmatig · ${team.length} agents`}</strong>
            </div>
            <p>{automaticAgents ? 'Planner bewaakt het doel, Value Engine toetst nut en Server Manager voert de technische checks uit.' : team.map((agent) => agent.name).join(', ') || 'Kies minimaal één specialist voor deze missie.'}</p>
            <span className="selection-reason"><Sparkles size={13} /> {automaticAgents ? 'gekozen op taak, risico en beschikbare tools' : 'jouw vaste team voor deze missie'}</span>
          </section>

          <section className="approval-gate">
            <div className="sidebar-heading"><span><ShieldCheck size={16} /> Approval gate</span><span className="gate-count">1</span></div>
            <p>Een externe fontlicentie van €42,80 is voorgesteld. Betaling blijft geblokkeerd.</p>
            <button type="button" onClick={onApprove}>Review actie <ArrowRight size={14} /></button>
          </section>

          <section className="resilience-log">
            <div className="sidebar-heading"><span><RefreshCw size={16} /> Hervatbaar</span><CheckCircle2 size={16} /></div>
            <p>Doel, plan, toolresultaten en laatste checkpoint zijn opgeslagen. Gaia kan na uitval hier verder.</p>
            <div><span>12:06</span><strong>UI-state veilig opgeslagen</strong></div>
            <div><span>12:04</span><strong>Bronnen gevalideerd</strong></div>
          </section>
        </aside>
      </div>
    </div>
  );
}

function MemoryView({
  selected,
  onSelect,
}: {
  selected: string;
  onSelect: (id: string) => void;
}) {
  const [sourceVisible, setSourceVisible] = useState(false);
  const selectedNode = memoryNodes.find((node) => node.id === selected) ?? memoryNodes[0];
  return (
    <div className="space-view memory-view">
      <header className="view-heading memory-heading">
        <span className="view-icon"><Brain size={17} /></span>
        <div>
          <h1>Levend geheugen</h1>
          <p>Geen losse feiten, maar verbonden context met een reden om te bestaan.</p>
        </div>
      </header>

      <section className="memory-graph" aria-label="Gaia memory graph">
        <svg className="memory-lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <path d="M50 48 L29 25 M50 48 L72 24 M50 48 L79 62 M50 48 L27 70 M50 48 L54 79 M29 25 L72 24 M27 70 L54 79" />
        </svg>
        {memoryNodes.map((node) => {
          const Icon = node.icon;
          const isSelected = node.id === selected;
          return (
            <motion.button
              className="memory-node"
              data-size={node.size}
              data-selected={isSelected || undefined}
              style={{ left: `${node.x}%`, top: `${node.y}%` }}
              key={node.id}
              type="button"
              onClick={() => { onSelect(node.id); setSourceVisible(false); }}
              animate={{ scale: isSelected ? 1.08 : 1 }}
              transition={{ type: 'spring', bounce: 0, duration: 0.35 }}
              aria-label={`${node.label}: ${node.detail}`}
            >
              <Icon size={node.size === 'large' ? 22 : 17} strokeWidth={1.55} />
              <span>{node.label}</span>
            </motion.button>
          );
        })}
      </section>

      <aside className="memory-inspector">
        <div className="inspector-topline">
          <span className="memory-type"><Database size={14} /> semantisch</span>
          <span>8 verbindingen</span>
        </div>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={selectedNode.id}
            initial={{ opacity: 0, filter: 'blur(5px)', transform: 'translateY(6px)' }}
            animate={{ opacity: 1, filter: 'blur(0px)', transform: 'translateY(0px)' }}
            exit={{ opacity: 0, filter: 'blur(4px)', transform: 'translateY(-4px)' }}
            transition={{ duration: 0.2, ease: [0.23, 1, 0.32, 1] }}
          >
            <h2>{selectedNode.label}</h2>
            <p>{selectedNode.detail}</p>
            <div className="memory-fact">
              <Sparkles size={15} />
              <span>Gaia gebruikt dit alleen wanneer het je huidige taak duidelijk beter maakt.</span>
            </div>
          </motion.div>
        </AnimatePresence>
        <button className="inspector-link" type="button" aria-expanded={sourceVisible} onClick={() => setSourceVisible((visible) => !visible)}>Bekijk herkomst <Link2 size={14} /></button>
        {sourceVisible && <div className="provenance-note" role="status">Ontstaan uit 3 expliciete keuzes in deze Gaia-conceptsessie.</div>}
      </aside>
    </div>
  );
}

function AgentPicker({
  open,
  automatic,
  selected,
  onSetAutomatic,
  onToggle,
  onDone,
  onClose,
}: {
  open: boolean;
  automatic: boolean;
  selected: AgentId[];
  onSetAutomatic: () => void;
  onToggle: (id: AgentId) => void;
  onDone: () => void;
  onClose: () => void;
}) {
  const sheetRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    openerRef.current = document.activeElement as HTMLElement | null;
    const focusTimer = window.requestAnimationFrame(() => closeRef.current?.focus());
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab' || !sheetRef.current) return;
      const focusable = Array.from(sheetRef.current.querySelectorAll<HTMLElement>('button:not([disabled]), [tabindex]:not([tabindex="-1"])'));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      window.cancelAnimationFrame(focusTimer);
      document.removeEventListener('keydown', onKeyDown);
      openerRef.current?.focus();
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.button className="settings-dismiss" type="button" aria-label="Agentkiezer sluiten" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
          <motion.aside
            ref={sheetRef}
            className="agent-picker"
            role="dialog"
            aria-modal="true"
            aria-labelledby="agent-picker-title"
            initial={{ opacity: 0, filter: 'blur(12px)', transform: 'translateY(28px) scale(0.985)' }}
            animate={{ opacity: 1, filter: 'blur(0px)', transform: 'translateY(0px) scale(1)' }}
            exit={{ opacity: 0, filter: 'blur(8px)', transform: 'translateY(18px) scale(0.99)' }}
            transition={{ duration: 0.3, ease: [0.23, 1, 0.32, 1] }}
          >
            <header>
              <div><h2 id="agent-picker-title">Stel het agentteam samen</h2><p>Laat Gaia per fase kiezen, of combineer zelf meerdere specialisten.</p></div>
              <button ref={closeRef} type="button" className="close-button" onClick={onClose} aria-label="Sluiten"><X size={17} /></button>
            </header>

            <button className="auto-agent" data-selected={automatic || undefined} type="button" onClick={onSetAutomatic}>
              <span className="auto-agent-icon"><Sparkles size={18} /></span>
              <span><strong>Automatisch team</strong><small>Aanbevolen · Gaia kiest drie agents en wisselt per fase</small></span>
              <span className="selection-dot">{automatic && <Check size={14} />}</span>
            </button>

            <div className="agent-grid">
              {agentCatalog.map((agent) => {
                const Icon = agent.icon;
                const isSelected = !automatic && selected.includes(agent.id);
                return (
                  <button key={agent.id} className="agent-option" data-selected={isSelected || undefined} type="button" aria-pressed={isSelected} onClick={() => onToggle(agent.id)}>
                    <span className="agent-option-icon"><Icon size={17} /></span>
                    <span><strong>{agent.name}</strong><small>{agent.role}</small></span>
                    <p>{agent.detail}</p>
                    <em>{agent.permission}</em>
                    <span className="selection-dot">{isSelected && <Check size={14} />}</span>
                  </button>
                );
              })}
            </div>

            <footer className="agent-safety-note">
              <div><span><Wallet size={15} /> Geld</span><span><Mail size={15} /> Mail</span><span><Globe2 size={15} /> Externe acties</span></div>
              <p>blijven zichtbaar en approval-gated in dit frontendconcept.</p>
              <button className="agent-done" type="button" onClick={onDone} disabled={!automatic && selected.length === 0}>{automatic ? 'Gebruik automatisch team' : `Gebruik ${selected.length} agents`}</button>
            </footer>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function ReviewSheet({
  open,
  kind,
  onClose,
  onDecision,
}: {
  open: boolean;
  kind: ReviewKind;
  onClose: () => void;
  onDecision: (accepted: boolean) => void;
}) {
  const sheetRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const approval = kind === 'approval';

  useEffect(() => {
    if (!open) return;
    openerRef.current = document.activeElement as HTMLElement | null;
    const focusTimer = window.requestAnimationFrame(() => closeRef.current?.focus());
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab' || !sheetRef.current) return;
      const focusable = Array.from(sheetRef.current.querySelectorAll<HTMLElement>('button:not([disabled]), [tabindex]:not([tabindex="-1"])'));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      window.cancelAnimationFrame(focusTimer);
      document.removeEventListener('keydown', onKeyDown);
      openerRef.current?.focus();
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.button className="settings-dismiss" type="button" aria-label="Review sluiten" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
          <motion.aside
            ref={sheetRef}
            className="review-sheet"
            role="dialog"
            aria-modal="true"
            aria-labelledby="review-sheet-title"
            initial={{ opacity: 0, filter: 'blur(12px)', transform: 'translateY(24px) scale(0.985)' }}
            animate={{ opacity: 1, filter: 'blur(0px)', transform: 'translateY(0px) scale(1)' }}
            exit={{ opacity: 0, filter: 'blur(8px)', transform: 'translateY(14px) scale(0.99)' }}
            transition={{ duration: 0.28, ease: [0.23, 1, 0.32, 1] }}
          >
            <header>
              <span className={`review-symbol ${approval ? 'amber' : 'violet'}`}>{approval ? <LockKeyhole size={20} /> : <RefreshCw size={20} />}</span>
              <div><h2 id="review-sheet-title">{approval ? 'Review financiële actie' : 'Review skillvoorstel'}</h2><p>{approval ? 'Gaia wacht. Er is nog niets gekocht of betaald.' : 'Gaia leert alleen wat jij expliciet toevoegt.'}</p></div>
              <button ref={closeRef} type="button" className="close-button" onClick={onClose} aria-label="Sluiten"><X size={17} /></button>
            </header>

            <section className="review-summary">
              <div>
                <span>{approval ? 'Externe fontlicentie' : 'weather-repair'}</span>
                <strong>{approval ? '€42,80' : 'Tool reliability skill'}</strong>
              </div>
              <span className="prototype-chip">voorbeeld</span>
            </section>

            <section className="review-details">
              {approval ? (
                <>
                  <div><CheckCircle2 size={16} /><span><strong>Doet na approval</strong><small>Opent een mock checkout en registreert de keuze in deze missie.</small></span></div>
                  <div><ShieldCheck size={16} /><span><strong>Blijft geblokkeerd</strong><small>Geen echte betaling, opgeslagen betaalmethode of automatische herhaling.</small></span></div>
                  <div><RefreshCw size={16} /><span><strong>Terugdraaibaar prototype</strong><small>Deze demo verandert alleen de zichtbare interface-status.</small></span></div>
                </>
              ) : (
                <>
                  <div><Activity size={16} /><span><strong>Aanleiding</strong><small>Twee weather-calls faalden; Gaia wil retry- en herstelpatronen onderzoeken.</small></span></div>
                  <div><CalendarClock size={16} /><span><strong>Gepland om 22:00</strong><small>Value Engine schrijft eerst een voorstel; GLM 5.2 via Colibri is alleen voorbeeldconfiguratie.</small></span></div>
                  <div><LockKeyhole size={16} /><span><strong>Beperkte scope</strong><small>Alleen weather-tool logs en tests. Installatie vraagt opnieuw jouw approval.</small></span></div>
                </>
              )}
            </section>

            <footer className="review-actions">
              <button type="button" className="review-decline" onClick={() => onDecision(false)}>{approval ? 'Afwijzen' : 'Sla over'}</button>
              <button type="button" className="review-accept" onClick={() => onDecision(true)}>{approval ? 'Goedkeuren als voorbeeld' : 'Voeg toe aan 22:00'} <ArrowRight size={15} /></button>
            </footer>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function SettingsSheet({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const sheetRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const [initiative, setInitiative] = useState(62);
  const [curiosity, setCuriosity] = useState(74);
  const [quietMode, setQuietMode] = useState(true);
  const [sound, setSound] = useState(false);

  useEffect(() => {
    if (!open) return;
    openerRef.current = document.activeElement as HTMLElement | null;
    const focusTimer = window.requestAnimationFrame(() => closeRef.current?.focus());
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab' || !sheetRef.current) return;
      const focusable = Array.from(sheetRef.current.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      window.cancelAnimationFrame(focusTimer);
      document.removeEventListener('keydown', onKeyDown);
      openerRef.current?.focus();
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.button
            className="settings-dismiss"
            type="button"
            aria-label="Instellingen sluiten"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          <motion.aside
            ref={sheetRef}
            className="settings-sheet"
            role="dialog"
            aria-modal="true"
            aria-labelledby="gaia-settings-title"
            initial={{ opacity: 0, filter: 'blur(12px)', transform: 'translateX(36px) scale(0.98)' }}
            animate={{ opacity: 1, filter: 'blur(0px)', transform: 'translateX(0px) scale(1)' }}
            exit={{ opacity: 0, filter: 'blur(8px)', transform: 'translateX(22px) scale(0.99)' }}
            transition={{ duration: 0.3, ease: [0.23, 1, 0.32, 1] }}
          >
            <header>
              <div>
                <span className="settings-symbol"><Settings2 size={18} /></span>
                <span><h2 id="gaia-settings-title">Hoe Gaia aanvoelt</h2><p>Veranderingen zijn direct zichtbaar.</p></span>
              </div>
              <button ref={closeRef} type="button" className="close-button" onClick={onClose} aria-label="Sluiten"><X size={17} /></button>
            </header>

            <section className="settings-group">
              <div className="setting-label"><span>Initiatief</span><strong>{initiative}%</strong></div>
              <input style={{ background: `linear-gradient(90deg, #a99aff 0 ${initiative}%, rgba(255, 255, 255, 0.12) ${initiative}% 100%)` }} type="range" min="0" max="100" value={initiative} onChange={(event) => setInitiative(Number(event.target.value))} aria-label="Gaia initiatief" />
              <p>Hoe snel Gaia zelf een relevante volgende stap voorstelt.</p>
            </section>
            <section className="settings-group">
              <div className="setting-label"><span>Nieuwsgierigheid</span><strong>{curiosity}%</strong></div>
              <input style={{ background: `linear-gradient(90deg, #a99aff 0 ${curiosity}%, rgba(255, 255, 255, 0.12) ${curiosity}% 100%)` }} type="range" min="0" max="100" value={curiosity} onChange={(event) => setCuriosity(Number(event.target.value))} aria-label="Gaia nieuwsgierigheid" />
              <p>Hoe diep Gaia verbanden onderzoekt voor ze je aandacht vraagt.</p>
            </section>

            <div className="setting-toggle-row">
              <span><strong>Rustige modus</strong><small>Minder beweging tijdens focusblokken</small></span>
              <button className="toggle" data-on={quietMode || undefined} type="button" role="switch" aria-label="Rustige modus" aria-checked={quietMode} onClick={() => setQuietMode((value) => !value)}><span /></button>
            </div>
            <div className="setting-toggle-row">
              <span><strong>Subtiel geluid</strong><small>Alleen bij afronding en bevestiging</small></span>
              <button className="toggle" data-on={sound || undefined} type="button" role="switch" aria-label="Subtiel geluid" aria-checked={sound} onClick={() => setSound((value) => !value)}><span /></button>
            </div>

            <div className="settings-footnote">
              <ShieldCheck size={16} />
              <p>Autonome acties blijven voorbeelden tot je backend en toestemmingsregels zijn aangesloten.</p>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function PromptIsland({
  value,
  onChange,
  onSubmit,
  state,
  onVoice,
  inputRef,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  state: GaiaState;
  onVoice: () => void;
  inputRef: RefObject<HTMLInputElement | null>;
}) {
  const working = state === 'thinking' || state === 'acting';
  return (
    <form className="prompt-island" onSubmit={onSubmit} data-state={state}>
      <button type="button" className="prompt-tool" aria-label={state === 'listening' ? 'Stop met luisteren' : 'Spraakmodus starten'} onClick={onVoice}>
        <AudioLines size={18} strokeWidth={1.7} />
      </button>
      <label className="sr-only" htmlFor="gaia-prompt">Vraag Gaia iets</label>
      <input
        ref={inputRef}
        id="gaia-prompt"
        name="prompt"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={state === 'listening' ? 'Ik luister…' : working ? 'Gaia maakt de context compleet…' : 'Wat zullen we samen doen?'}
        autoComplete="off"
        disabled={working}
      />
      <kbd>⌘ K</kbd>
      <button className="send-button" type="submit" aria-label="Verstuur naar Gaia" disabled={working || !value.trim()}>
        <AnimatePresence initial={false} mode="wait">
          <motion.span
            key={working ? 'working' : 'send'}
            initial={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }}
            animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }}
            exit={{ opacity: 0, scale: 0.25, filter: 'blur(4px)' }}
            transition={{ type: 'spring', duration: 0.3, bounce: 0 }}
          >
            {working ? <Orbit className="working-icon" size={18} strokeWidth={1.8} /> : <ArrowUp size={18} strokeWidth={2} />}
          </motion.span>
        </AnimatePresence>
      </button>
    </form>
  );
}

function CommandDock({ active, onOpenChat }: { active: SpaceId; onOpenChat: () => void }) {
  const status = active === 'today' ? 'Voorbeeldmissie' : active === 'flows' ? 'Lokale taken · opgeslagen checkpoints' : 'Voorbeeldgeheugen';
  return (
    <div className="command-dock">
      <span><span className="status-pulse" />{status}</span>
      <button type="button" onClick={onOpenChat}><Command size={16} /> Nieuwe opdracht <kbd>⌘ K</kbd></button>
    </div>
  );
}

export default function HomePage() {
  const shellRef = useRef<HTMLElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const timersRef = useRef<number[]>([]);
  const toastTimerRef = useRef<number | null>(null);
  const compact = useCompactLayout();
  const [activeSpace, setActiveSpace] = useState<SpaceId>('today');
  const [gaiaState, setGaiaState] = useState<GaiaState>('idle');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [agentPickerOpen, setAgentPickerOpen] = useState(false);
  const [reviewKind, setReviewKind] = useState<ReviewKind | null>(null);
  const [dragging, setDragging] = useState(false);
  const [prompt, setPrompt] = useState('');
  const [lastPrompt, setLastPrompt] = useState('');
  const [responseReady, setResponseReady] = useState(true);
  const [chatRequest, setChatRequest] = useState<ChatRequest | null>(null);
  const [chatDemo, setChatDemo] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [activeFlowStep, setActiveFlowStep] = useState(-1);
  const [selectedMemory, setSelectedMemory] = useState('per');
  const [automaticAgents, setAutomaticAgents] = useState(true);
  const [selectedAgents, setSelectedAgents] = useState<AgentId[]>(['planner', 'value', 'server']);
  const [missionPaused, setMissionPaused] = useState(false);
  const overlayOpen = settingsOpen || agentPickerOpen || reviewKind !== null;

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setActiveSpace('chat');
        window.setTimeout(() => inputRef.current?.focus(), 80);
      }
      if (event.key === 'Escape') {
        setSettingsOpen(false);
        setAgentPickerOpen(false);
        setReviewKind(null);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  useEffect(() => () => {
    timersRef.current.forEach((timer) => window.clearTimeout(timer));
    if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
  }, []);

  const showToast = (message: string) => {
    setToast(message);
    if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    toastTimerRef.current = window.setTimeout(() => setToast(null), 2600);
  };

  const submitPromptText = (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) return;

    timersRef.current.forEach((timer) => window.clearTimeout(timer));
    timersRef.current = [];
    setLastPrompt(trimmed);
    setChatRequest({ id: Date.now(), content: trimmed });
    setResponseReady(false);
    setActiveSpace('chat');
    setSettingsOpen(false);
    setAgentPickerOpen(false);
    setReviewKind(null);
    setGaiaState('thinking');
    timersRef.current.push(
      window.setTimeout(() => setGaiaState('acting'), 1050),
      window.setTimeout(() => {
        setGaiaState('idle');
        setResponseReady(true);
        showToast('Context samengebracht');
      }, 1950),
    );
  };

  const submitPrompt = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    submitPromptText(prompt);
  };

  const runFlow = () => {
    timersRef.current.forEach((timer) => window.clearTimeout(timer));
    timersRef.current = [];
    setActiveFlowStep(0);
    setGaiaState('acting');
    [1, 2, 3, 4].forEach((step, index) => {
      timersRef.current.push(window.setTimeout(() => {
        setActiveFlowStep(step);
        if (step === 4) {
          setGaiaState('idle');
          showToast('Voorbeeldflow afgerond — niets extern uitgevoerd');
        }
      }, 620 * (index + 1)));
    });
  };

  const handleDropAction = (action?: string) => {
    if (!action) {
      showToast('Sleep Gaia naar een van de magnetische zones');
      return;
    }
    if (action === 'explain') {
      setActiveSpace('chat');
      setLastPrompt('Leg uit wat ik hier zie en waarom dit relevant is.');
      setResponseReady(true);
      showToast('Uitlegmodus geopend');
    }
    if (action === 'flow') {
      setActiveSpace('flows');
      showToast('Werkcockpit geopend');
    }
    if (action === 'remember') {
      setActiveSpace('memory');
      setSelectedMemory('preference');
      showToast('Context gemarkeerd voor geheugen');
    }
  };

  const switchSpace = (space: SpaceId) => {
    setActiveSpace(space);
    setSettingsOpen(false);
    setAgentPickerOpen(false);
    setReviewKind(null);
    if (gaiaState !== 'idle') setGaiaState('idle');
  };

  const openChatCommand = () => {
    switchSpace('chat');
    window.setTimeout(() => inputRef.current?.focus(), 80);
  };

  return (
    <MotionConfig reducedMotion="user">
    <main className="gaia-shell" ref={shellRef} data-state={gaiaState} data-space={activeSpace}>
      <a className="skip-link" href="#gaia-primary">Ga naar hoofdinhoud</a>
      <BreathingField state={gaiaState} />
      <div className="ambient-light ambient-violet" aria-hidden="true" />
      <div className="ambient-light ambient-cyan" aria-hidden="true" />

      <button className="brand-lockup" aria-label="Gaia vandaag openen" type="button" onClick={() => switchSpace('today')}>
        <span className="brand-glyph"><Sparkles size={16} strokeWidth={1.8} /></span>
        <span>Gaia</span>
      </button>

      <SpaceSwitcher active={activeSpace} onChange={switchSpace} onSettings={() => { setAgentPickerOpen(false); setReviewKind(null); setSettingsOpen(true); }} />

      <button className="profile-button" type="button" aria-label="Profiel en instellingen openen" onClick={() => { setAgentPickerOpen(false); setReviewKind(null); setSettingsOpen(true); }}>
        <CircleUserRound size={19} strokeWidth={1.6} />
        <span>Per</span>
      </button>

      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          id="gaia-primary"
          tabIndex={-1}
          className="space-transition"
          key={activeSpace}
          initial={{ opacity: 0, filter: 'blur(10px)', transform: 'scale(0.985)' }}
          animate={{ opacity: overlayOpen ? 0.28 : 1, filter: overlayOpen ? 'blur(5px)' : 'blur(0px)', transform: 'scale(1)' }}
          exit={{ opacity: 0, filter: 'blur(7px)', transform: 'scale(0.99)' }}
          transition={{ duration: 0.28, ease: [0.23, 1, 0.32, 1] }}
          aria-hidden={overlayOpen || undefined}
          inert={overlayOpen || undefined}
        >
          {activeSpace === 'today' && (
            <TodayView
              onOpenChat={openChatCommand}
              onOpenWork={() => switchSpace('flows')}
              onApprove={() => setReviewKind('approval')}
              onReviewLearning={() => setReviewKind('learning')}
            />
          )}
          {activeSpace === 'chat' && (
            <ConnectedChat
              request={chatRequest}
              draft={prompt}
              onDraftChange={setPrompt}
              onSubmitRequest={submitPromptText}
              onClearDraft={() => setPrompt('')}
              onModeChange={setChatDemo}
              demo={<ChatView
                prompt={lastPrompt}
                responseReady={responseReady}
                onPlan={() => {
                  switchSpace('flows');
                  showToast('Een visuele planflow staat klaar');
                }}
              />}
            />
          )}
          {activeSpace === 'flows' && (
            <ConnectedWork demo={<FlowsView
              activeStep={activeFlowStep}
              onRun={runFlow}
              paused={missionPaused}
              onTogglePause={() => {
                setMissionPaused((value) => !value);
                showToast(missionPaused ? 'Missie hervat vanaf checkpoint' : 'Missie veilig gepauzeerd');
              }}
              automaticAgents={automaticAgents}
              selectedAgents={selectedAgents}
              onSelectAgents={() => { setReviewKind(null); setAgentPickerOpen(true); }}
              onApprove={() => setReviewKind('approval')}
            />} />
          )}
          {activeSpace === 'memory' && <MemoryView selected={selectedMemory} onSelect={setSelectedMemory} />}
        </motion.div>
      </AnimatePresence>

      <GaiaCompanion
        active={activeSpace}
        state={gaiaState}
        compact={compact}
        settingsOpen={overlayOpen}
        constraintsRef={shellRef}
        onDragging={setDragging}
        onDropAction={handleDropAction}
      />
      <DropZones visible={dragging} />

      {activeSpace === 'chat' && chatDemo ? (
        <PromptIsland
          value={prompt}
          onChange={setPrompt}
          onSubmit={submitPrompt}
          state={gaiaState}
          onVoice={() => setGaiaState((state) => state === 'listening' ? 'idle' : 'listening')}
          inputRef={inputRef}
        />
      ) : activeSpace !== 'chat' ? <CommandDock active={activeSpace} onOpenChat={openChatCommand} /> : null}

      <SettingsSheet open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <AgentPicker
        open={agentPickerOpen}
        automatic={automaticAgents}
        selected={selectedAgents}
        onClose={() => setAgentPickerOpen(false)}
        onSetAutomatic={() => setAutomaticAgents(true)}
        onToggle={(id) => {
          setAutomaticAgents(false);
          setSelectedAgents((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
        }}
        onDone={() => {
          setAgentPickerOpen(false);
          showToast(automaticAgents ? 'Gaia kiest drie agents per fase' : `${selectedAgents.length} agents aan deze missie gekoppeld`);
        }}
      />
      <ReviewSheet
        open={reviewKind !== null}
        kind={reviewKind ?? 'approval'}
        onClose={() => setReviewKind(null)}
        onDecision={(accepted) => {
          const kind = reviewKind;
          setReviewKind(null);
          if (kind === 'approval') showToast(accepted ? 'Voorbeeldapproval geregistreerd — niets betaald' : 'Actie afgewezen en geblokkeerd');
          if (kind === 'learning') showToast(accepted ? 'Voorstel toegevoegd aan de review van 22:00' : 'Skillvoorstel overgeslagen');
        }}
      />

      <AnimatePresence>
        {toast && (
          <motion.div
            className="gaia-toast"
            role="status"
            initial={{ opacity: 0, filter: 'blur(7px)', transform: 'translate(-50%, 8px) scale(0.97)' }}
            animate={{ opacity: 1, filter: 'blur(0px)', transform: 'translate(-50%, 0px) scale(1)' }}
            exit={{ opacity: 0, filter: 'blur(4px)', transform: 'translate(-50%, 5px) scale(0.98)' }}
            transition={{ duration: 0.22, ease: [0.23, 1, 0.32, 1] }}
          >
            <Check size={15} /> {toast}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="prototype-note">{activeSpace === 'flows' ? 'Werk: live backend of expliciet ontwerpvoorbeeld' : activeSpace === 'chat' ? (chatDemo ? 'Chat: expliciet ontwerpvoorbeeld' : 'Chat: verbonden met Leon') : 'Interactief concept · voorbeelddata'}</div>
    </main>
    </MotionConfig>
  );
}
