"""Bounded local tool routing for explicit owner commands in Leon chat."""
from contextlib import closing
from datetime import datetime, timedelta
import json
import re
import threading
import time
from zoneinfo import ZoneInfo

_ACTIONS = {'shopper.create', 'shopper.update', 'shopper.pause', 'shopper.resume', 'shopper.search',
            'shopper.hold', 'shopper.status', 'calendar.read', 'mail.read', 'memory.save', 'memory.search',
            'tasks.create', 'tasks.status', 'clarify'}


def may_be_action(content: str) -> bool:
    text = content.casefold()
    shopping = bool(re.search(r'\b(shopper|marktplaats|vinted|ddr[345]|ram|deals?|aanbiedingen?|verkoper)\b', text))
    commands = bool(re.search(r'\b(zoek|zoeken|volg|regelen?|vind|pauze|pauzeer|stop|hervat|reageer|budget|status|hoe|update|verander|wacht|alleen|liever|voorkeur)\b', text))
    return (shopping and commands) or bool(re.search(
        r'\b(agenda|afspraken|gmail|mail|geheugen)\b|\b(onthoud|bewaar|taken|opdrachten)\b', text))


def calendar_time(value: dict) -> str:
    if 'date' in value:
        return value['date'] + ' (hele dag)'
    date_time = value.get('date_time', value.get('dateTime', ''))
    return datetime.fromisoformat(date_time.replace('Z', '+00:00')).astimezone(ZoneInfo('Europe/Amsterdam')).strftime('%d-%m %H:%M')


def validate_authority(decision: dict, content: str) -> dict:
    """Writes require the current owner command; a model cannot invent a budget."""
    action, args = decision['action'], decision['args']
    text = content.casefold()
    write_verbs = {
        'shopper.create': r'\b(zoek|zoeken|vind|volg|regel|maak)\b',
        'shopper.update': r'\b(zoek|budget|verander|pas|update|alleen|liever|voorkeur|wacht|ook)\b',
        'shopper.pause': r'\b(stop|pauze|pauzeer|stoppen|pauzeren)\b',
        'shopper.resume': r'\b(hervat|hervatten|doorgaan|verder)\b',
        'shopper.search': r'\b(zoek|zoeken|vind|kijk)\b',
        'shopper.hold': r'\b(wacht|pauze|pauzeer|niet|hold)\b',
    }
    if action in write_verbs and not re.search(write_verbs[action], text):
        return {'action':'clarify','args':{'question':'Wil je de zoekopdracht aanpassen, of alleen de voortgang weten?'}}
    if action in {'shopper.create', 'shopper.update'} and 'max_total_cents' in args:
        amounts = re.findall(r'(?:€\s*|eur(?:o)?\s*)(\d+(?:[.,]\d{1,2})?)|(\d+(?:[.,]\d{1,2})?)\s*(?:euro|eur|€)', text)
        budgets = {round(float((a or b).replace(',', '.')) * 100) for a, b in amounts}
        budgets |= {round(float(v.replace(',', '.')) * 100) for v in re.findall(r'(?:budget|maximaal|max|onder|tot)\s+(\d+(?:[.,]\d{1,2})?)\b(?!\s*(?:gb|modules|sticks))', text)}
        if type(args['max_total_cents']) is not int or args['max_total_cents'] not in budgets:
            return {'action':'clarify', 'args':{'question':'Wat is je maximale totaalprijs inclusief verzending, in euro?'}}
    if action == 'memory.save' and not re.search(r'\b(onthoud|bewaar|sla|opslaan)\b', text):
        return {'action':'clarify','args':{'question':'Wil je dat ik dit in je geheugen bewaar?'}}
    if action == 'tasks.create' and not re.search(r'\b(maak|plan|zet|bewaar|voeg|regel|doe)\b', text):
        return {'action':'tasks.status','args':{}}
    return decision


def shopper_service():
    from leon_control_plane.shopper_service import ShopperService, ROOT
    return ShopperService(ROOT / '.runtime/shopper.sqlite')


def route(content: str, history: list[str], state: dict) -> dict:
    from leon_control_plane.shopper_runtime import model_json
    watches = [{'id': w['id'], 'query': w['query'], 'budget_cents': w['max_total_cents'],
                'min_ram_gb': w['min_ram_gb'], 'enabled': w['enabled']} for w in state.get('watches', [])[:5]]
    prompt = (
        'Je bent Leons toolrouter voor de eigenaar. Alleen de laatste gebruikersopdracht geeft bevoegdheid; '
        'geschiedenis helpt verwijzingen begrijpen. Kies één actie uit: ' + ', '.join(sorted(_ACTIONS)) + '. '
        'JSON exact {"action":"...","args":{...}}. Geen shell, URLs, aankopen of betalingsacties. '
        'shopper.create args: query,max_total_cents,min_ram_gb,preferred_ram_gb,max_ram_sticks,platform '
        '(both is standaard: Marktplaats én Vinted). Budget ontbreekt? clarify args:{question:"Wat is je maximale totaalprijs?"}. '
        'shopper.update args:watch_id + uitsluitend expliciet gewijzigde velden (query,max_total_cents,min_ram_gb,preferred_ram_gb,max_ram_sticks,wait_days). '
        'shopper.pause/resume/search/hold args:{watch_id:"..."}. hold betekent verkopersgesprek niet beantwoorden. '
        'shopper.status/tasks.status args:{}. calendar.read args:{period:"today|tomorrow|week"}. mail.read args:{}. '
        'memory.save/search args:{text:"..."}. tasks.create args:{title:"...",goal:"..."}. '
        'Gebruik uitsluitend bekende watch_ids. Bij meerdere mogelijke taken vraag welke met clarify. '
        'Geen RAM-opdracht? RAM-velden zijn 0. Vraag verduidelijking bij niet-ondersteunde actie. '
        'Een prijs in euro wordt centen: EUR50 = 5000. Nooit zelf een budget bedenken.\n'
        + json.dumps({'watches': watches, 'previous_owner_messages': history[-2:], 'current_owner_command': content}, ensure_ascii=False)
    )
    if len(prompt.encode()) > 4096:
        prompt = prompt[:prompt.index('\n')] + '\n' + json.dumps({'watches': watches[:2], 'current_owner_command': content[:1000]}, ensure_ascii=False)
    decision, _ = model_json(prompt)
    if not isinstance(decision, dict) or set(decision) != {'action', 'args'} or decision['action'] not in _ACTIONS or not isinstance(decision['args'], dict):
        raise ValueError('Unsupported tool decision')
    return decision


def apply(store, request_id: str, decision: dict, shopper) -> str:
    action, args = decision['action'], decision['args']
    if action == 'clarify':
        question = args.get('question', 'Welke opdracht bedoel je precies?')
        if set(args) - {'question'} or not isinstance(question, str) or len(question) > 400:
            raise ValueError('Invalid clarification')
        return question
    if action.startswith('shopper.'):
        if action == 'shopper.create':
            allowed = {'query', 'max_total_cents', 'min_ram_gb', 'preferred_ram_gb', 'max_ram_sticks', 'platform'}
            if set(args) - allowed or not {'query', 'max_total_cents'}.issubset(args):
                return 'Wat moet ik zoeken en wat is je maximale totaalprijs inclusief verzending?'
            watch = shopper.create({'request_id': request_id, **args, 'platform': args.get('platform', 'both'),
                                    'automatic_messages': args.get('platform', 'both') != 'vinted',
                                    'required_terms': ['ddr3'] if 'ddr3' in args['query'].casefold() else [],
                                    'excluded_terms': ['ddr4', 'sodimm', 'so-dimm', 'gezocht'] if 'ddr3' in args['query'].casefold() else []})
            shopper.start(watch['id'])
            return f"Ik volg {watch['query']} tot €{watch['max_total_cents']/100:.2f} inclusief verzending. Ik zoek op {'Marktplaats en Vinted' if watch['platform']=='both' else watch['platform']}. Je ziet mijn voortgang en leads in Werk."
        if action == 'shopper.status':
            if args:
                raise ValueError('Unexpected status fields')
            watches = shopper.state()['watches']
            if not watches:
                return 'Ik heb nog geen zoekopdracht. Wat zoek je en wat wil je maximaal uitgeven?'
            lines = []
            for w in watches[:5]:
                result = (w.get('latest_run') or {}).get('result') or {}
                lines.append(f"{w['query']}: {'actief' if w['enabled'] else 'gepauzeerd'}, {len(result.get('matches', []))} leads in de laatste zoekronde" + (f", {w['held_contacts']} gesprek op pauze" if w.get('held_contacts') else '') + '.')
            return '\n'.join(lines) + '\nAlle details staan in Werk.'
        watch_id = args.get('watch_id')
        if watch_id not in {w['id'] for w in shopper.state()['watches']}:
            raise ValueError('Unknown owner watch')
        if action == 'shopper.update':
            shopper.edit(watch_id, {k: v for k, v in args.items() if k != 'watch_id'})
            return 'Zoekopdracht aangepast. Ik houd je nieuwe eisen aan; de actuele status staat in Werk.'
        if set(args) != {'watch_id'}:
            raise ValueError('Unexpected watch command fields')
        if action == 'shopper.hold':
            shopper.hold(watch_id)
            return 'Het laatst benaderde gesprek staat op pauze. Ik stuur daar geen reactie; de zoekopdracht blijft actief.'
        if action == 'shopper.search':
            shopper.start(watch_id)
            return 'Een nieuwe zoekronde is gestart. Ik werk de leads in Werk bij zodra die klaar is.'
        shopper.set_enabled(watch_id, action == 'shopper.resume')
        return 'Zoekopdracht hervat.' if action == 'shopper.resume' else 'Zoekopdracht gepauzeerd. Ik zoek en reageer daarvoor niet meer automatisch.'
    if action in {'calendar.read', 'mail.read'}:
        from leon_control_plane.google_api import preview, status
        from leon_control_plane.server import parse_selected_env_values
        keys = {'GOOGLE_READONLY_ENABLED','GOOGLE_ACCESS_TOKEN','GOOGLE_REFRESH_TOKEN','GOOGLE_CLIENT_ID','GOOGLE_CLIENT_SECRET','GOOGLE_GRANTED_SCOPES','GOOGLE_CREDENTIALS_FILE'}
        values = parse_selected_env_values(keys)
        if not status(store, values)['configured']:
            return 'Google heeft nog geen Agenda/Gmail-toegang gegeven. Open Vandaag en klik op Google verbinden; daarna kan ik je afspraken hier tonen.'
        if action == 'mail.read':
            if args:
                raise ValueError('Unexpected mail fields')
            data = preview(store, values, 'mail', {'limit': 5})
            return '\n'.join(f"• {item.get('subject', '(Geen onderwerp)')} — {item.get('from', '')}" for item in data['items']) or 'Geen recente mail gevonden.'
        if set(args) != {'period'} or args['period'] not in {'today', 'tomorrow', 'week'}:
            raise ValueError('Unknown calendar period')
        now = datetime.now(ZoneInfo('Europe/Amsterdam'))
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1 if args['period']=='tomorrow' else 0)
        end = start + timedelta(days=7 if args['period']=='week' else 1)
        data = preview(store, values, 'calendar', {'start': start.isoformat(), 'end': end.isoformat(), 'timezone': 'Europe/Amsterdam', 'limit': 10})
        return '\n'.join(f"• {item['summary']} — {calendar_time(item['start'])}" for item in data['items']) or 'Geen afspraken in deze periode.'
    if action.startswith('memory.'):
        if set(args) != {'text'} or not isinstance(args['text'], str) or not 1 <= len(args['text']) <= 1000:
            raise ValueError('Invalid memory text')
        if action == 'memory.save':
            store.create_memory_item({'content':args['text'],'memory_type':'working','source':'chat','confidence':1.0}, actor_type='user',actor_id='leon-chat')
            return 'Opgeslagen in je geheugen.'
        found = store.retrieve_memory(query=args['text'], limit=5)
        return '\n'.join('• '+item.get('excerpt','')[:200] for item in found.get('results',[])[:5]) or 'Geen passend geheugen gevonden.'
    if action == 'tasks.create':
        if set(args) != {'title', 'goal'} or any(not isinstance(v, str) or not 1 <= len(v) <= 500 for v in args.values()):
            raise ValueError('Invalid task')
        store.create_task(title=args['title'], goal=args['goal'], risk_level='low')
        return f"Opdracht opgeslagen: {args['title']}. Je kunt hem in Werk volgen. Uitvoering is nog niet gestart."
    if action == 'tasks.status':
        if args:
            raise ValueError('Unexpected task status fields')
        with closing(store.connect()) as conn:
            rows = conn.execute("SELECT title,status FROM tasks WHERE title<>'Chat conversation' ORDER BY rowid DESC LIMIT 8").fetchall()
        return '\n'.join(f"• {r['title']}: {r['status']}" for r in rows) or 'Nog geen opdrachten opgeslagen.'
    raise ValueError('Unsupported action')


class ActionRunner:
    def __init__(self, store):
        self.store = store

    def start(self, message):
        now = time.time()
        with closing(self.store.connect()) as conn, conn:
            conn.execute('INSERT OR IGNORE INTO chat_actions VALUES(?,?,?,?,?,?)', (message['id'], message['request_id'], 'queued', now, None, None))
            changed = conn.execute("UPDATE chat_actions SET status='routing',updated_at=? WHERE message_id=? AND status='queued'", (now, message['id'])).rowcount
            if not changed:
                stale = conn.execute('SELECT status,updated_at FROM chat_actions WHERE message_id=?', (message['id'],)).fetchone()
                if stale['status'] in {'routing', 'applying'} and now - stale['updated_at'] > 300:
                    conn.execute("UPDATE chat_actions SET status='unknown' WHERE message_id=?", (message['id'],))
                    conn.execute("UPDATE chat_messages SET status='unknown',content='Opdracht onderbroken; controleer Werk. Ik herhaal een onzekere actie niet.' WHERE id=?", (message['id'],))
                return
        threading.Thread(target=self.execute, args=(dict(message),), daemon=True).start()

    def execute(self, message):
        try:
            with closing(self.store.connect()) as conn:
                rows = conn.execute("SELECT content FROM chat_messages WHERE conversation_id=? AND role='user' AND created_at<? ORDER BY created_at DESC LIMIT 2", (message['conversation_id'], message['created_at'])).fetchall()
            shopper = shopper_service()
            decision = validate_authority(route(message['request_content'], [r['content'][:500] for r in reversed(rows)], shopper.state()), message['request_content'])
            with closing(self.store.connect()) as conn, conn:
                conn.execute("UPDATE chat_actions SET status='applying',operation=?,updated_at=? WHERE message_id=?", (json.dumps(decision), time.time(), message['id']))
            text = apply(self.store, message['request_id'], decision, shopper)
            status = 'complete'
        except Exception:
            text, status = 'Ik kon deze opdracht niet afronden. Er is geen bevestigde uitvoering; controleer Werk of geef de opdracht specifieker.', 'error'
        with closing(self.store.connect()) as conn, conn:
            conn.execute('UPDATE chat_actions SET status=?,result=?,updated_at=? WHERE message_id=?', (status, json.dumps({'text': text}), time.time(), message['id']))
            conn.execute('UPDATE chat_messages SET status=?,content=?,updated_at=? WHERE id=?', (status, text, time.time(), message['id']))
