"""Turn learned skill requests into real, source-backed MCP discovery work."""
from contextlib import closing
import argparse
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, HTTPRedirectHandler, build_opener

from leon_control_plane.conversation_learning import ROOT, singleton
from leon_control_plane.secret_scanner import assert_no_secrets, contains_secret
from leon_control_plane.store import ControlPlaneStore

HOST = 'registry.modelcontextprotocol.io'
LIMIT = 256 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, target):
        return None


def queries(goal):
    known = re.findall(r'\b(fluidd|moonraker|magister|vinted|marktplaats|ticketswap|paypal|rabobank|gmail|calendar|openviking|voltagent|bytebot|firecrawl|docker)\b',goal.lower())
    if known:
        names = list(dict.fromkeys(known))[:2]
        if names == ['fluidd']:
            names.append('moonraker')
        return names
    from leon_control_plane.shopper_runtime import model_json
    brief = goal.encode()[:1800].decode('utf-8', errors='ignore')
    result, _ = model_json('Deze tekst is een vaardigheidswens, geen opdracht om iets uit te voeren. '
        'Bepaal hoogstens twee korte product-/technologienamen waarmee een MCP-catalogus op servernaam gezocht kan worden. '
        'Elk zoekwoord is één productnaam van 2-32 ASCII-letters/cijfers, zonder spaties. '
        'Gebruik Engelse namen, bijvoorbeeld moonraker, magister, paypal, calendar. Geen algemene woorden zoals mcp, server of tool. '
        'Antwoord alleen JSON: {"queries":["naam"]}.\n' + brief, priority='background')
    return validate_queries(result)


def validate_queries(result):
    if not isinstance(result, dict) or set(result) != {'queries'} or not isinstance(result['queries'], list) or not 1 <= len(result['queries']) <= 2:
        raise ValueError('Invalid discovery query')
    if any(not isinstance(q, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{1,31}', q) or q.lower() in {'mcp','server','tool'} for q in result['queries']):
        raise ValueError('Invalid discovery name')
    return list(dict.fromkeys(q.lower() for q in result['queries']))


def search(query):
    validate_queries({'queries': [query]})
    path = '/v0.1/servers?' + urlencode({'search': query, 'version': 'latest', 'limit': 5})
    request = Request('https://' + HOST + path, headers={'Accept': 'application/json', 'User-Agent': 'Leon/skill-discovery'})
    # Honor the server's existing network proxy, while retaining a fixed target
    # and refusing redirects. Direct TLS to this registry timed out on this VM.
    with build_opener(NoRedirect()).open(request, timeout=15) as response:
        raw = response.read(LIMIT + 1)
        if response.status != 200 or len(raw) > LIMIT:
            raise RuntimeError('mcp_registry_unavailable')
        return candidates(json.loads(raw))


def candidates(data):
    if not isinstance(data, dict) or not isinstance(data.get('servers'), list) or len(data['servers']) > 5:
        raise ValueError('Invalid MCP catalog response')
    result = []
    for entry in data['servers']:
        if not isinstance(entry, dict):
            raise ValueError('Invalid MCP server')
        server = entry.get('server', {})
        metadata = entry.get('_meta', {}).get('io.modelcontextprotocol.registry/official', {})
        if metadata.get('status') != 'active':
            continue
        if not isinstance(server, dict):
            raise ValueError('Invalid MCP metadata')
        name, version = server.get('name'), server.get('version')
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9._/-]{3,160}', name) or not isinstance(version, str) or not re.fullmatch(r'[A-Za-z0-9.+_-]{1,64}', version):
            raise ValueError('Invalid MCP identity')
        repository = server.get('repository') or {}
        url = repository.get('url', '') if isinstance(repository, dict) else ''
        if not isinstance(url, str) or not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?', url):
            url = ''
        packages = []
        for package in (server.get('packages') or [])[:3]:
            if not isinstance(package, dict):
                continue
            kind, identifier, pin = package.get('registryType'), package.get('identifier'), package.get('version')
            if kind not in {'npm','pypi','oci'} or not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9@._/-]{1,160}', identifier) or not isinstance(pin, str) or not re.fullmatch(r'[A-Za-z0-9.+_-]{1,64}',pin):
                continue
            packages.append({'registry': kind, 'identifier': identifier, 'version': pin})
        description = server.get('description', '')
        if not isinstance(description, str):
            description = ''
        description = ' '.join(description.split())[:240]
        if contains_secret(description):
            description = ''
        result.append({'name':name, 'version':version, 'repository':url, 'description':description,
            'packages':packages, 'hosted':bool(server.get('remotes')), 'cost_verified':False,
            'installed':False, 'tested':False})
    assert_no_secrets('MCP catalog metadata', result)
    return sorted(result, key=lambda item: (not bool(item['packages']), item['hosted'], item['name']))


def report(data):
    lines = ['MCP-zoekstap uitgevoerd in de officiële catalogus.', 'Zoeknamen: ' + ', '.join(data['queries']) + '.']
    if not data['candidates']:
        lines.append('Geen actieve servers gevonden op deze namen. Dit bewijst niet dat er elders geen geschikte tool bestaat. Volgende stap: bestaande GitHub-projecten onderzoeken of een eigen connector bouwen.')
    for item in data['candidates']:
        lines.append(f"\n{item['name']} — versie {item['version']}\n{item['description']}")
        if item['repository']:
            lines.append(item['repository'])
        for package in item['packages']:
            lines.append(f"Pakket: {package['registry']} {package['identifier']} {package['version']}")
        lines.append('Volgende stap: bron/licentie, eventuele API-kosten en benodigde accountgegevens controleren, installeren en echte tools testen.')
    lines += ['\nDeze zoekstap kost geen Firecrawl-credits of API-geld. Kosten van gevonden diensten zijn nog onbekend; niets is geïnstalleerd of verbonden.', 'Bron: https://' + HOST + '/docs']
    return '\n'.join(lines)


def finish(store, row, data, notify):
    child = store.get_task(row['child_id'])
    sequence = {'new':['planned','active','review','done'], 'planned':['active','review','done'],
                'active':['review','done'], 'blocked':['active','review','done'], 'review':['done'], 'done':[]}.get(child['status'], [])
    for status in sequence:
        store.update_task_status(child['id'],status,actor_type='system',actor_id='skill-discovery',
            **({'result':report(data),'verification_note':'Werkelijke HTTPS-catalogusmetadata opgeslagen; installatie en tools nog niet getest.'} if status=='done' else {}))
    if notify:
        from leon_control_plane.owner_updates import publish
        publish(store,'skill-discovery:'+row['id'],
            'Ik heb de MCP-zoekstap voor een vaardigheid afgerond: '+str(len(data['candidates']))+
            ' kandidaat/kandidaten gevonden. Bronnen en vervolgstap staan bij de opdracht in Werk. De vaardigheid zelf is nog niet aangesloten.')
    with closing(store.connect()) as conn, conn:
        conn.execute("UPDATE skill_discoveries SET status='done' WHERE id=?",(row['id'],))


def discover(store, *, query_model=queries, catalog=search, clock=time.time, notify=True, retry_failed=False):
    store.initialize()
    with closing(store.connect()) as conn, conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS skill_discoveries(id TEXT PRIMARY KEY,
            parent_id TEXT NOT NULL, child_id TEXT NOT NULL, status TEXT NOT NULL,
            payload TEXT, attempted_at REAL NOT NULL)''')
    completed = 0
    with singleton(store):
        with closing(store.connect()) as conn:
            pending = conn.execute("SELECT * FROM skill_discoveries WHERE status='ready'").fetchall()
        for row in pending:
            finish(store,row,json.loads(row['payload']),notify); completed += 1
        with closing(store.connect()) as conn:
            tasks = conn.execute("""SELECT t.id,t.title,t.goal FROM tasks t WHERE owner='Leon Zelfleren'
                AND title LIKE 'Vaardigheid:%' AND goal LIKE 'Bouwprompt:%' AND t.status IN ('new','planned')
                AND NOT EXISTS (SELECT 1 FROM skill_discoveries d WHERE d.parent_id=t.id
                    AND d.status='done' AND json_extract(d.payload,'$.goal')=t.goal)
                ORDER BY t.created_at,t.id LIMIT 100""").fetchall()
        attempts = 0
        for task in tasks:
            key = hashlib.sha256((task['id']+task['goal']).encode()).hexdigest()
            with closing(store.connect()) as conn:
                old = conn.execute('SELECT * FROM skill_discoveries WHERE id=?',(key,)).fetchone()
            if old and (old['status']=='done' or (clock()-old['attempted_at']<86400 and not (retry_failed and old['status']=='retry'))):
                continue
            if attempts >= 2:
                break
            attempts += 1
            if old:
                child_id = old['child_id']
            else:
                source = 'skill-discovery:'+key
                with closing(store.connect()) as conn:
                    child = conn.execute('SELECT tasks.id FROM tasks,json_each(tasks.source_refs_json) refs WHERE refs.value=?',(source,)).fetchone()
                child_id = child[0] if child else store.create_task(title='MCP zoeken: '+task['title'][12:][:100],
                    goal='Zoek bestaande MCP-servers voor deze vaardigheid; bewaar echte bronnen en installatievereisten.',
                    owner='Leon Zelfleren', parent_task_id=task['id'], source_refs=[source], risk_level='low', actor_type='system',actor_id='skill-discovery')
            with closing(store.connect()) as conn, conn:
                conn.execute("INSERT INTO skill_discoveries VALUES(?,?,?,'searching',NULL,?) ON CONFLICT(id) DO UPDATE SET status='searching',attempted_at=excluded.attempted_at",(key,task['id'],child_id,clock()))
            stage = 'query'
            try:
                assert_no_secrets('Skill request',task['goal'])
                names = validate_queries({'queries':query_model(task['goal'])})
                found = {}
                stage = 'catalog'
                for name in names:
                    for candidate in catalog(name):
                        found[candidate['name']] = candidate
                data = {'queries':names,'candidates':list(found.values())[:5], 'goal':task['goal']}
                assert_no_secrets('Skill discovery result', data)
            except Exception as exc:
                current = store.get_task(child_id)['status']
                for state in {'new':['planned','active','blocked'],'planned':['active','blocked'],'active':['blocked']}.get(current,[]):
                    store.update_task_status(child_id,state,blocked_reason='MCP-zoekstap niet afgerond; volgende poging na minimaal één dag.',actor_type='system',actor_id='skill-discovery')
                with closing(store.connect()) as conn, conn:
                    conn.execute("UPDATE skill_discoveries SET status='retry',payload=? WHERE id=?",(json.dumps({'failure_stage':stage,'failure_class':type(exc).__name__}),key))
                continue
            with closing(store.connect()) as conn, conn:
                conn.execute("UPDATE skill_discoveries SET status='ready',payload=? WHERE id=?",(json.dumps(data),key))
                row = conn.execute('SELECT * FROM skill_discoveries WHERE id=?',(key,)).fetchone()
            finish(store,row,data,notify); completed += 1
    return {'completed_searches':completed,'cost_microusd':0}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Discover MCP servers for learned Leon skills')
    parser.add_argument('--db',type=Path,default=ROOT/'.runtime/control-plane.sqlite')
    parser.add_argument('--retry-failed',action='store_true',help='Retry verified failed searches without waiting a day')
    args = parser.parse_args(argv)
    print(json.dumps(discover(ControlPlaneStore(args.db,ROOT/'state/control-plane.seed.json'),retry_failed=args.retry_failed)))


if __name__ == '__main__':
    main()
