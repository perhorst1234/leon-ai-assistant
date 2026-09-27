"""Free public concert discovery; no account, booking or paid providers."""
from contextlib import closing
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

from leon_control_plane.code_worker import transition
from leon_control_plane.secret_scanner import assert_no_secrets

SOURCE='https://www.ticketswap.nl/concert-tickets/l/netherlands'
LIMIT=1024*1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class Events(HTMLParser):
    def __init__(self):
        super().__init__();self.href=None;self.parts=[];self.rows=[]

    def handle_starttag(self,tag,attrs):
        if tag=='a':
            value=dict(attrs).get('href','');p=urlsplit(value)
            self.href=value if p.scheme=='https' and p.netloc=='www.ticketswap.nl' and p.path.startswith('/concert-tickets/') and p.path.count('/')==2 and not p.query and not p.fragment else None
            self.parts=[]

    def handle_data(self,value):
        if self.href and sum(map(len,self.parts))<1000:self.parts.append(value[:1000])

    def handle_endtag(self,tag):
        if tag=='a' and self.href:
            text=' '.join(' '.join(self.parts).split())[:400]
            if text and len(self.rows)<40:self.rows.append({'url':self.href,'description':text})
            self.href=None


def fetch():
    try:
        with build_opener(NoRedirect()).open(Request(SOURCE,headers={'User-Agent':'LeonAssistant/1.0'}),timeout=15) as response:
            if response.status!=200 or 'text/html' not in response.headers.get('Content-Type',''):raise ValueError()
            data=response.read(LIMIT+1)
        if len(data)>LIMIT:raise ValueError()
        return data.decode('utf-8')
    except Exception:raise ValueError('ticketswap_public_search_unavailable') from None


def search(query='',*,reader=fetch):
    if not isinstance(query,str) or len(query)>120:raise ValueError('Invalid concert query')
    assert_no_secrets('Concert query',query)
    html=reader()
    if not isinstance(html,str) or len(html.encode())>LIMIT:raise ValueError('Invalid concert response')
    parser=Events();parser.feed(html)
    unique={item['url']:item for item in parser.rows}
    rows=[item for item in unique.values() if query.casefold() in item['description'].casefold()][:6]
    assert_no_secrets('Public concert results',rows)
    if not unique:raise ValueError('ticketswap_public_search_unavailable')
    return {'source':SOURCE,'query':query,'events':rows,'cost_microusd':0,
            'scope':'public_netherlands_concert_overview','prices_verified':False}


def execute(store,request_id,query='',*,reader=fetch):
    store.initialize()
    marker='ticketswap-search:'+request_id
    with closing(store.connect()) as c:
        row=c.execute('SELECT id,status,result FROM tasks WHERE EXISTS(SELECT 1 FROM json_each(source_refs_json) WHERE value=?)',(marker,)).fetchone()
    if row and row['status']=='done':return row['result']
    task_id=row['id'] if row else store.create_task(title='TicketSwap: '+(query or 'voorbeeldconcerten'),
        goal='Lees actuele openbare concertlinks in Nederland. Geen aankoop, reservering of betaalde API.',
        owner='Leon Shopper',risk_level='low',source_refs=[marker],actor_type='system',actor_id='ticketswap-search')
    transition(store,task_id,'active')
    try:data=search(query,reader=reader)
    except ValueError:
        message='TicketSwap is nu niet leesbaar. De zoekopdracht staat in Werk; beschikbaarheid is niet bevestigd.'
        transition(store,task_id,'blocked',blocked_reason=message);return message
    text='TicketSwap — openbare concerten in Nederland:\n'
    text+='\n'.join('• '+item['description']+'\n'+item['url'] for item in data['events']) or 'Geen match op de openbare overzichtspagina; dit is geen volledige TicketSwap-zoekopdracht.'
    text+='\nPrijs en type ticket zijn nog niet gecontroleerd. Dit is een gratis zoekresultaat; er is niets gekocht of gereserveerd.\nBron: '+SOURCE
    transition(store,task_id,'done',result=text,verification_note='Werkelijke openbare HTML gelezen; alleen evenementlinks, geen prijzen of aankoop.')
    return text
